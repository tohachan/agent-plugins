# Concurrency — rules

> **Scope:** correctness and liveness of code that runs at the same time: shared mutable state, races, locks, atomics, channels, bounded parallelism, cancellation, leaks, deadlocks, distributed locks and leases, DB-level claiming of work, the Node.js event loop, and stopping workers cleanly. **Hands off to:** isolation levels, version-column mechanics and lock internals → DATA; broker delivery semantics and job frameworks → MSG; making a repeated operation safe (keys, dedup) → IDEM; timeouts, retries, HTTP draining → RES; hot keys and partitioning → SCALE; CPU/latency profiling → PERF.

## Best practices

`CONC-BP-1` — **Every piece of mutable state has exactly one documented owner.** Why: unowned state is where races live. How: the guarding mutex is a field next to the data it guards with a comment ("mu guards a, b"), or the state lives inside one goroutine, or it lives in the DB and code never caches it for decisions.

`CONC-BP-2` — **Keep critical sections short and free of I/O.** Why: a lock held across a network call turns downstream latency into contention for every caller and invites deadlock. How: copy what you need under the lock, unlock, then call; `defer mu.Unlock()` immediately after `Lock()` in short functions.

`CONC-BP-3` — **Use atomics only for single independent values.** Why: two atomics updated separately can be observed half-updated. How: Go typed atomics (`atomic.Int64`, `atomic.Bool`, `atomic.Pointer[T]`) for counters/flags/snapshot swaps; anything with an invariant across fields uses a mutex.

`CONC-BP-4` — **Use `RWMutex` only for measured read-heavy state.** Why: RWMutex is slower than Mutex for short sections and a recursive `RLock` deadlocks once a writer is waiting. How: start with `sync.Mutex`; switch after a benchmark shows read contention; never re-acquire `RLock` on the same path.

`CONC-BP-5` — **Bound every fan-out.** Why: one goroutine/promise per input item turns a large input into memory blow-up and a self-inflicted DDoS on the DB or downstream. How: Go `errgroup.WithContext` + `g.SetLimit(n)` or `semaphore.Weighted`; Node `p-limit(n)`; size `n` from the downstream capacity (DB pool size, provider rate limit), not CPU count, for I/O work.

`CONC-BP-6` — **Every goroutine has an owner that can stop it and waits for it.** Why: goroutines without exit paths leak memory and file descriptors and keep running after shutdown. How: pass `ctx`; loop with `select { case <-ctx.Done(): return; … }`; the starter holds a `WaitGroup`/`errgroup` and calls `Wait()`; detect leaks in tests with `go.uber.org/goleak`.

`CONC-BP-7` — **Propagate cancellation end to end.** Why: work for a client that already gave up wastes capacity exactly when you are overloaded. How: Go derives from `r.Context()` and passes `ctx` to every DB/HTTP call and every blocking channel op; Node passes an `AbortSignal` (`AbortSignal.any([req.signal, AbortSignal.timeout(ms)])`) to `fetch`, DB drivers and child tasks. Timeout values → RES.

`CONC-BP-8` — **Resolve check-then-act and read-modify-write in the data store, atomically.** Why: in-app checks race across goroutines, awaits and replicas. How: `UPDATE stock SET qty = qty - $1 WHERE sku = $2 AND qty >= $1` and test rows-affected; `INSERT … ON CONFLICT`; unique constraints; `INCRBY`/Lua in Redis. Never `SELECT` then `UPDATE` with a value computed in the app.

`CONC-BP-9` — **Use optimistic concurrency for human-paced edits.** Why: lost updates when two editors save. How: `UPDATE … SET …, version = version + 1 WHERE id = $1 AND version = $2`; 0 rows → conflict; machine paths retry 3× with jitter, user paths return 409/412 (ETag/If-Match contract → API; column mechanics → DATA).

`CONC-BP-10` — **Take row locks in a fixed global order with a lock timeout.** Why: two transactions locking A→B and B→A deadlock; Postgres aborts one only after `deadlock_timeout` (1s), holding connections meanwhile. How: sort IDs before `SELECT … FOR UPDATE`; set `lock_timeout` (e.g. 2–5s) per transaction; keep locked transactions < 100ms and free of external calls.

`CONC-BP-11` — **Claim DB-backed work with `FOR UPDATE SKIP LOCKED` or a lease column.** Why: plain `SELECT … WHERE status='pending'` hands the same job to every poller. How: `UPDATE jobs SET status='running', locked_by=$w, locked_until=now()+'5 min' WHERE id IN (SELECT id FROM jobs WHERE status='pending' AND run_at<=now() ORDER BY run_at LIMIT 50 FOR UPDATE SKIP LOCKED) RETURNING *`; a reaper re-queues expired leases; partial index on `(run_at) WHERE status='pending'`; jobs must tolerate re-execution (IDEM).

`CONC-BP-12` — **Treat a distributed lock as a lease and protect the resource with a fencing token.** Why: a holder paused by GC, a stalled VM or a partition keeps acting after its lease expired and another holder took over. How: lock service issues a monotonically increasing token (etcd revision, ZooKeeper zxid, DB sequence); every write to the protected resource carries it and the resource rejects tokens lower than the highest seen (`WHERE fence_token < $new`). TTL ≥ 3× renewal interval; renew at TTL/3; abort work when renewal fails.

`CONC-BP-13` — **Use Redis locks only for efficiency (avoiding duplicate work), never for correctness.** Why: Redis replication is async and Redlock depends on bounded clock drift and pauses; neither is guaranteed. How: `SET key token NX PX ttl` (single atomic call) and release with a compare-and-delete Lua script; when a double execution would corrupt data, use DB constraints/fencing (BP-8, BP-12).

`CONC-BP-14` — **Use transaction-scoped Postgres advisory locks.** Why: session locks (`pg_advisory_lock`) leak to the wrong client behind PgBouncer in transaction mode and survive panics on pooled connections. How: `pg_advisory_xact_lock(hashtext('tenant:'||$1))` inside the transaction that does the work; `pg_try_advisory_xact_lock` for "skip if busy" singletons.

`CONC-BP-15` — **Run the Go race detector in CI on tests that actually exercise concurrency.** Why: data races in Go are undefined behaviour (torn interface/slice reads → crashes, silent corruption) and rarely show in review. How: `go test -race ./...` in CI (expect ~2–10× slower, 5–10× memory); add tests that run handlers in parallel (`t.Parallel()`, `-count=20`); `testing/synctest` for time-dependent code.

`CONC-BP-16` — **Keep the Node.js event loop free.** Why: one 200ms synchronous task delays every in-flight request on that process, health checks included. How: no `*Sync` APIs after startup; CPU work > ~10ms to a `worker_threads` pool (piscina); stream large payloads instead of `JSON.parse` on multi-MB bodies; alert on event-loop delay p99 > ~100ms (`perf_hooks.monitorEventLoopDelay`).

`CONC-BP-17` — **Treat every `await` as a point where other requests run.** Why: state read before an `await` may be stale after it — Node's version of check-then-act. How: re-check after the await, or make the whole step one atomic DB/Redis operation; for in-process per-key serialisation use an async mutex (`async-mutex`) keyed by entity, knowing it does not cover other replicas.

`CONC-BP-18` — **Spread contention instead of serialising on one hot spot.** Why: a single counter row, map lock or Redis key caps throughput at 1/critical-section time. How: striped locks (hash key into N mutexes); sharded counters summed on read; batching writes per interval; detect with Go mutex/block profiles (`runtime.SetMutexProfileFraction`) and `pg_stat_activity` wait events (`Lock:tuple`). Data partitioning → SCALE.

`CONC-BP-19` — **See MSG-BP-10, RES-BP-14 (canonical mechanism).** Stop worker intake, drain under a deadline, then hand back unfinished work or let durable leases recover.

`CONC-BP-20` — **Transfer ownership explicitly and never share non-concurrency-safe handles.** Why: a slice/map sent on a channel and then mutated by the sender, or one connection used by two goroutines, corrupts data without any lock in sight. How: after sending, the sender stops touching the value (or sends a copy: `slices.Clone`, `maps.Clone`); `pgx.Conn`, `*sql.Tx`, `pgx.Tx`, `bufio.Writer`, `math/rand.Rand`, protobuf builders are single-goroutine — use a pool (`pgxpool`, `*sql.DB`) or one handle per goroutine; a DB transaction is never fanned out across goroutines or `Promise.all`.

## Bad practices

`CONC-BAD-1` — **Plain Go `map` written from several goroutines.** The runtime aborts with `fatal error: concurrent map writes` — not recoverable by `recover`, the whole process dies. → Instead: mutex-guarded map or `sync.Map` for append-mostly keys (CONC-BP-1).

`CONC-BAD-2` — **`go func()` in a handler that uses the request context or no context.** With `r.Context()` the work is cancelled when the response is written; with `context.Background()` it is unbounded, unobserved and lost on deploy. → Instead: do it in the request, or enqueue durably (MSG/outbox) (CONC-BP-6, CONC-AP-6).

`CONC-BAD-3` — **Mutex held across a network call, DB query or channel send.** Callers queue behind the slowest dependency; a blocked send under a lock deadlocks. → Instead: CONC-BP-2.

`CONC-BAD-4` — **Copying a struct that contains a `sync.Mutex` (value receivers, passing by value).** Each copy has its own lock, so nothing is protected. → Instead: pointer receivers; `go vet` copylocks check in CI.

`CONC-BAD-5` — **`wg.Add(1)` inside the goroutine it counts.** `Wait()` may return before the goroutine registers. → Instead: `Add` before `go`, or Go 1.25 `wg.Go(func(){…})`, or errgroup.

`CONC-BAD-6` — **Unbounded fan-out: `go` per item, `Promise.all(items.map(…))` over user- or DB-sized arrays.** 10k items → 10k concurrent queries, pool exhaustion, timeouts, provider bans. → Instead: CONC-BP-5.

`CONC-BAD-7` — **Read-modify-write through the app: load row, compute, save.** Concurrent requests overwrite each other (lost update); ORMs hide this behind `entity.save()`. → Instead: atomic statement or version check (CONC-BP-8, CONC-BP-9).

`CONC-BAD-8` — **Channel send or receive without a `ctx.Done()` case.** If the other side has gone, the goroutine blocks forever (leak). → Instead: `select { case ch <- v: case <-ctx.Done(): return ctx.Err() }` (CONC-BP-6).

`CONC-BAD-9` — **Redis lock taken with `SETNX` followed by a separate `EXPIRE`, or released with plain `DEL`.** A crash between the two calls leaves a lock that never expires; `DEL` releases someone else's lock after your TTL expired. → Instead: `SET NX PX` + token compare-and-delete (CONC-BP-13).

`CONC-BAD-10` — **Lock TTL shorter than worst-case work, with no renewal and no fencing.** Two holders run at once after expiry. → Instead: CONC-BP-12.

`CONC-BAD-11` — **Session-level advisory locks behind a transaction-mode pooler.** Lock and unlock land on different server connections; locks leak or are held by an unrelated client. → Instead: CONC-BP-14.

`CONC-BAD-12` — **Synchronous or CPU-heavy calls on the Node request path** (`fs.readFileSync`, `execSync`, `crypto.pbkdf2Sync`, `bcrypt.hashSync`, `zlib.*Sync`, sharp/PDF rendering inline, catastrophic-backtracking regex). Event-loop stall for all clients. → Instead: CONC-BP-16.

`CONC-BAD-13` — **Floating promises (async call without `await`/`catch`).** Errors become unhandled rejections, which crash the process by default since Node 15, and work escapes cancellation and shutdown. → Instead: await or explicitly track; enable `@typescript-eslint/no-floating-promises`.

`CONC-BAD-14` — **Module-level mutable state used for coordination** (a `Map` of "in progress" IDs, a `let busy = false` flag, a package-level Go var). Wrong as soon as there are 2 replicas or PM2/cluster workers. → Instead: coordinate in the DB (CONC-BP-8, CONC-BP-11).

`CONC-BAD-15` — **Closing a channel from the receiver or from several senders.** Send on closed channel panics. → Instead: exactly one sender (or the coordinator after `wg.Wait()`) closes.

`CONC-BAD-16` — **Locking multiple rows in request-dependent order.** Batch updates arriving in different orders deadlock under load. → Instead: CONC-BP-10.

## Anti-patterns

`CONC-AP-1` — **Redlock (or any Redis lock) as a correctness guarantee.** Symptoms: "only one worker charges the card because we hold a Redlock"; no fencing token reaches the DB or API being protected. Why it hurts: process pauses, clock jumps and failover with async replication let two holders act at once; Redlock gives no token the resource can check. Way out: move the invariant into the resource (unique constraint, conditional update, idempotency key — IDEM); if a lock is still needed, use etcd/ZooKeeper/DB leases with fencing (CONC-BP-12).

`CONC-AP-2` — **In-process lock as cross-instance guard.** Symptoms: `sync.Mutex`/`async-mutex`/a JS `Set` protecting "one at a time per user"; works in dev with one replica, duplicates appear after scaling out or during rolling deploys (old and new pods overlap). Why it hurts: the guarantee silently disappears with replica count. Way out: DB atomic statements, row locks or advisory xact locks (CONC-BP-8, CONC-BP-14).

`CONC-AP-3` — **The big lock.** Symptoms: one global mutex, one distributed lock key (`lock:orders`), or `LOCK TABLE` around a hot path; throughput flat while CPU idle; latency grows linearly with load. Why it hurts: throughput = 1 / hold time, independent of hardware. Way out: lock per entity, striping, or replace with atomic statements (CONC-BP-18).

`CONC-AP-4` — **Every replica runs the scheduler.** Symptoms: `robfig/cron`, `node-cron`, `setInterval` jobs inside the API deployment with `replicas > 1`; duplicate emails, double billing runs at :00. Why it hurts: N replicas = N executions, and the count changes with autoscaling. Way out: a single scheduler (k8s CronJob with `concurrencyPolicy: Forbid`, or one dispatcher) that enqueues jobs claimed via SKIP LOCKED; leader election (k8s Lease) only as a last resort; jobs idempotent (IDEM).

`CONC-AP-5` — **Status-flag polling queue without row claiming.** Symptoms: `SELECT … WHERE status='new'` then `UPDATE … SET status='processing'` in separate statements; or `FOR UPDATE` without `SKIP LOCKED` so pollers serialise. Why it hurts: double processing or one-at-a-time throughput; stuck `processing` rows after crashes. Way out: CONC-BP-11 with lease expiry and a reaper.

`CONC-AP-6` — **Fire-and-forget background work in the web process.** Symptoms: `go sendEmail(...)`, un-awaited promises, in-memory job arrays; "occasionally emails don't go out" after deploys. Why it hurts: no durability, no retry, no backpressure, invisible to shutdown. Way out: durable queue or outbox (MSG, IDEM) and dedicated workers with CONC-BP-19.

`CONC-AP-7` — **Channels as a general-purpose lock.** Symptoms: state shared between goroutines through webs of `select` over many channels, `chan struct{}` used as mutexes, goroutines that only forward. Why it hurts: deadlocks and leaks that only appear under specific interleavings; hard to reason about. Way out: mutex for shared state, channels for ownership transfer and pipelines with one closer and ctx on every op.

`CONC-AP-8` — **Optimistic retry loop under heavy contention.** Symptoms: version-conflict retries with no cap or backoff on a hot row (counter, popular item stock); CPU and DB load rise while success rate falls. Why it hurts: livelock — everybody retries, few commit. Way out: pessimistic lock or atomic statement for hot rows; cap retries (3) with jitter; split the hot row (CONC-BP-18).

`CONC-AP-9` — **See DATA-BP-5 (canonical mechanism).** Inspect transaction duration and external calls; long-lived snapshots/locks can exhaust pools and obstruct cleanup.

## Go / Node.js notes

- **Model.** Go runs goroutines in parallel on `GOMAXPROCS` threads with preemption, so real data races exist and corrupt memory; Go 1.25+ sets `GOMAXPROCS` from the container CPU limit (earlier versions need `go.uber.org/automaxprocs`). Node runs JS on one thread: no data races in JS (except `SharedArrayBuffer`), but logical races at every `await` and stalls from any CPU work.
- **Go version traps.** Per-iteration loop variables since Go 1.22 (check the `go` directive in `go.mod` — older modules still share the variable across goroutines); unstopped `time.After`/timers are collectable since 1.23; `sync.WaitGroup.Go` and GA `testing/synctest` since 1.25.
- **Go toolkit.** `golang.org/x/sync/errgroup` (`SetLimit`, `TryGo`), `x/sync/semaphore`, `x/sync/singleflight` (request coalescing → CACHE), `sync.OnceValue`, `go.uber.org/goleak`, etcd `clientv3/concurrency` (session leases + revision as fencing token), `go-redsync` (efficiency locks only).
- **Node toolkit.** `p-limit`/`p-queue` for bounded concurrency, `async-mutex` for per-process serialisation, `piscina` for worker pools, `AbortController`/`AbortSignal.any`/`AbortSignal.timeout` for cancellation; job queues (BullMQ, pg-boss, Graphile Worker) → MSG.
- **libuv threadpool.** Node runs `fs`, `dns.lookup`, `crypto.pbkdf2/scrypt`, and `zlib` on a pool of 4 threads by default; under load these queue invisibly. Raise `UV_THREADPOOL_SIZE` (e.g. 16–64, set before startup) or move the work.
- **Multi-process Node.** PM2 cluster, `node:cluster` and multiple pods each have their own memory; worker threads share nothing except via `postMessage` (structured clone) or `SharedArrayBuffer` + `Atomics`. Any coordination that must hold across them belongs in the DB/Redis.
- **Choosing.** Prefer Go when a service fans out heavily, streams long-lived connections, or mixes CPU and I/O; Node is fine for I/O-bound APIs if CPU spikes are offloaded and event-loop delay is monitored.
