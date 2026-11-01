# Concurrency — audit checklist

> **Scope:** correctness and liveness of code that runs at the same time: shared mutable state, races, locks, atomics, channels, bounded parallelism, cancellation, leaks, deadlocks, distributed locks and leases, DB-level claiming of work, the Node.js event loop, and stopping workers cleanly. **Hands off to:** isolation levels, version-column mechanics and lock internals → DATA; broker delivery semantics and job frameworks → MSG; making a repeated operation safe (keys, dedup) → IDEM; timeouts, retries, HTTP draining → RES; hot keys and partitioning → SCALE; CPU/latency profiling → PERF.

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| CONC-CHK-1 | Do Go tests run with the race detector in CI? | CI files (`.github/workflows`, `.gitlab-ci.yml`, `Makefile`) for `go test -race`. Fail: absent, or tests never run handlers concurrently. Verifies CONC-BP-15. | Medium |
| CONC-CHK-2 | Is all shared mutable state guarded? | Go: struct fields of type `map[`/slice on long-lived structs (services, caches, registries) accessed from handlers or goroutines; confirm a `sync.Mutex` guards every access. Package-level `var` maps. Fail: any unguarded write path. CONC-BAD-1, CONC-BP-1. | High |
| CONC-CHK-3 | Does every goroutine have a stop and wait path? | Grep `go func(`, `go ` + call; for each confirm ctx passed and a `WaitGroup`/`errgroup`/`Wait()` owner. `goleak` in tests; `go_goroutines` metric flat over days. Fail: fire-and-forget in handlers, no ctx in loops. CONC-BP-6, CONC-BAD-2, CONC-AP-6. | High |
| CONC-CHK-4 | Is fan-out bounded? | Go: `errgroup.Group` without `SetLimit`, `go` inside `for … range`. Node: `Promise.all(`/`Promise.allSettled(` over `.map(` of request/DB-derived arrays; absence of `p-limit`. Fail: bound is input size. CONC-BP-5, CONC-BAD-6. | High |
| CONC-CHK-5 | Do handlers propagate the request context/signal? | Go: `context.Background()`/`context.TODO()` outside `main`/tests; DB/HTTP calls without ctx (`db.Query(` vs `QueryContext`). Node: `fetch`/DB calls without `signal`. Fail: downstream work survives client cancel. CONC-BP-7. | Medium |
| CONC-CHK-6 | Is I/O kept out of critical sections? | Read code between `mu.Lock()` and `Unlock()`: any `http.`, `db.`, `rdb.`, channel send, or logging to network sink. Fail: any I/O under lock on a request path. CONC-BP-2, CONC-BAD-3. | Medium |
| CONC-CHK-7 | Are check-then-act and read-modify-write done atomically in the store? | Find `SELECT`/`findOne`/`findUnique` followed by `UPDATE`/`save`/`update` of a computed value (balances, stock, counters, status); look for `ON CONFLICT`, `WHERE qty >=`, `version`, `FOR UPDATE`. Fail: computed value written without condition. CONC-BP-8, CONC-BAD-7. | Critical if money/stock, else High |
| CONC-CHK-8 | Are multi-row locks taken in a consistent order with `lock_timeout`? | Grep `FOR UPDATE`, `FOR NO KEY UPDATE`; check IDs sorted before locking; `lock_timeout`/`statement_timeout` set on role or tx. Postgres logs for `deadlock detected`. CONC-BP-10, CONC-BAD-16. | Medium |
| CONC-CHK-9 | Do DB-backed queues claim rows safely? | Grep `SKIP LOCKED`, `status = 'pending'`, `locked_until`. Fail: select-then-update without lock; no lease expiry/reaper. CONC-BP-11, CONC-AP-5. | High |
| CONC-CHK-10 | Are distributed locks leases with safe release, and is correctness backed by fencing or constraints? | Grep `SETNX`, `SET .* NX`, `redlock`, `redsync`, `concurrency.NewMutex` (etcd), `Lease`. Confirm atomic acquire with TTL, token-checked release, renewal, and what protects the resource if two holders overlap. Fail: lock is the only guard on a money/data write. CONC-BP-12, CONC-BP-13, CONC-AP-1, CONC-BAD-9, CONC-BAD-10. | High |
| CONC-CHK-11 | Are advisory locks transaction-scoped when a pooler is used? | Grep `pg_advisory_lock` vs `pg_advisory_xact_lock`; check `pgbouncer.ini`/RDS Proxy `pool_mode = transaction`. Fail: session locks behind transaction pooling. CONC-BP-14, CONC-BAD-11. | High |
| CONC-CHK-12 | Do scheduled jobs execute once across replicas? | Grep `cron.New`, `robfig/cron`, `gocron`, `node-cron`, `agenda`, `setInterval(` in server entrypoints; compare with Deployment `replicas`/HPA. Fail: in-process scheduler with >1 replica and no claim/lock. CONC-AP-4. | High |
| CONC-CHK-13 | Is in-process coordination ever relied on across instances? | Module-level `Map`/`Set`/flags, `async-mutex`, `sync.Mutex` guarding "one per user/order" logic; replicas > 1 or PM2/cluster. Fail: per-entity exclusivity relies on memory. CONC-AP-2, CONC-BAD-14. | High |
| CONC-CHK-14 | Is the Node event loop free of sync and CPU-heavy work? | Grep `Sync(` (`readFileSync`, `execSync`, `pbkdf2Sync`, `scryptSync`, `hashSync`, `gzipSync`) outside startup; image/PDF/crypto/compression/large `JSON.parse` in handlers; check for event-loop delay metric and its p99. Fail: sync API on request path or lag p99 > 100ms. CONC-BP-16, CONC-BAD-12. | High |
| CONC-CHK-15 | Is CPU work offloaded in Node? | Grep `worker_threads`, `piscina`, `workerpool`; `UV_THREADPOOL_SIZE` if heavy fs/crypto/zlib/dns.lookup. Fail: sustained CPU work on main thread. CONC-BP-16. | Medium |
| CONC-CHK-16 | Are promises awaited and state re-checked after awaits? | ESLint config for `no-floating-promises`/`no-misused-promises`; handlers that read state, `await`, then write based on the earlier read. Fail: floating promises or stale-read writes. CONC-BP-17, CONC-BAD-13. | Medium |
| CONC-CHK-17 | Do workers shut down gracefully within the grace period? | Go: `signal.NotifyContext`, consumer loop exits on ctx, `Wait()` before exit. Node: `process.on('SIGTERM'`, consumer `close()`. k8s `terminationGracePeriodSeconds` ≥ longest job or jobs resumable; leases released. Fail: SIGTERM kills mid-job with no hand-back. CONC-BP-19. | Medium |
| CONC-CHK-18 | Is mutex hygiene enforced? | `go vet ./...` in CI (copylocks); value receivers on types with `sync.Mutex`; `wg.Add` inside goroutines; channels closed by receivers. CONC-BAD-4, CONC-BAD-5, CONC-BAD-15. | Low |
| CONC-CHK-19 | Is contention visible and bounded on hot paths? | Go mutex/block profiles enabled in pprof; Postgres `pg_stat_activity` wait events `Lock:*`, `pg_locks`; single counter rows or global lock keys. Fail: hot path serialises on one lock/row. CONC-BP-18, CONC-AP-3, CONC-AP-8. | Medium |
| CONC-CHK-20 | Are non-concurrency-safe handles kept to one goroutine/task, and values handed off not mutated afterwards? | Go: `pgx.Conn`/`pgx.Tx`/`*sql.Tx` captured in `go func(` or errgroup closures; slices/maps sent on channels and then appended to. Node: one transaction client (`tx`) used inside `Promise.all` (pg queues on one connection; some drivers error or interleave). Fail: shared tx or post-send mutation. CONC-BP-20. | High |

## Also scan for (rules not cited above)

Bodies: `knowledge/conc/rules.md`, looked up by ID.

- CONC-BAD-8 — Channel send or receive without a `ctx.Done()` case
- CONC-AP-7 — Channels as a general-purpose lock
- CONC-AP-9 — See DATA-BP-5 (canonical mechanism)
