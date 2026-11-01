# Performance — rules

> **Scope:** latency, throughput and resource efficiency of a single service and its request paths: measuring and profiling, percentiles and tail latency, queueing basics, the usual hotspots, I/O efficiency (batching, connection reuse, protocols, payloads, streaming), runtime tuning (Go GC/GOMAXPROCS, Node event loop), benchmarks, load testing, budgets, runtime choice by workload. **Hands off to:** capacity planning, scale-out, sharding, the knee as a capacity number → SCALE · cache design → CACHE · indexes, query plans, transactions → DATA · pagination and response contract shape → API · timeouts, backpressure, load shedding → RES · goroutine/worker pools and locking correctness → CONC · metrics, tracing, SLO alerting → OBS · ReDoS, decompression bombs → SEC.

## Best practices

`PERF-BP-1` — **Set a target and measure before optimising.** Unguided optimisation burns time on code that is not on the critical path. How: write the goal as "p99 < X ms at Y RPS" (or throughput/cost), reproduce under that load, read a trace to find which span dominates, then profile that process; change one thing, re-measure, keep the before/after numbers.

`PERF-BP-2` — **Profile with the right profile type.** CPU profiles do not show waiting. How: Go: `net/http/pprof` on an internal-only port, `go tool pprof -http=: profile?seconds=30` for CPU, `heap` (inuse vs alloc_space), `goroutine`, `mutex`/`block` (enable with `runtime.SetMutexProfileFraction`/`SetBlockProfileRate`), `go tool trace` for scheduler/GC latency. Node: `node --cpu-prof`/`--heap-prof`, `0x` or Chrome DevTools flame graphs, `clinic doctor` to classify (event loop vs I/O vs GC). Read flame graphs by width (time), not height.

`PERF-BP-3` — **See OBS-BP-7 (canonical mechanism).** Use aggregatable latency distributions for fleet percentiles.

`PERF-BP-4` — **Design for tail latency in fan-out.** A request touching N backends sees the slowest one: with 100 calls each having a 1% chance of hitting p99, ~63% of requests do. How: minimise fan-out width, parallelise independent calls, set per-call deadlines, use hedged requests for idempotent reads after the p95 (RES), keep GC pauses and queueing low on leaf services.

`PERF-BP-5` — **Use Little's law to size concurrency.** In-flight = throughput × latency (L = λW). How: 2,000 RPS × 50 ms = 100 concurrent requests, so a pool of 10 DB connections serving 20 ms queries caps that path at ~500 queries/s; size pools, worker counts and semaphores from it, and note that rising latency raises required concurrency (the start of collapse; limits → RES, CONC).

`PERF-BP-6` — **Remove N+1 and chatty I/O.** Per-item round trips scale latency linearly with data size. How: load related rows in one query (`WHERE id = ANY($1)`, joins, ORM eager loading: GORM `Preload`, Prisma `include`, TypeORM `relations`), DataLoader-style batching for GraphQL resolvers, bulk downstream endpoints; look for "query count per request" in traces.

`PERF-BP-7` — **Batch and pipeline writes and remote calls.** Each round trip costs 0.2–1 ms in-zone, tens of ms cross-region. How: multi-row `INSERT`, Postgres `COPY` (pgx `CopyFrom`, `pg-copy-streams`) for bulk loads, Redis pipelines/`MGET`, Kafka producer `linger.ms`/batch size, pgx `SendBatch`; cap batch size (e.g. 500–5,000 rows) to bound memory and lock time.

`PERF-BP-8` — **Reuse connections; multiplex with HTTP/2 where it pays.** New TCP+TLS costs 1–3 RTTs plus handshake CPU, and churn exhausts ephemeral ports. How: one shared HTTP client per process; Go: reuse `http.Client`, raise `Transport.MaxIdleConnsPerHost` (default 2) to the expected per-host concurrency, always drain and close bodies. Node: `fetch`/undici and Node ≥19 `http.globalAgent` keep alive by default, tune undici `Agent` `connections`. Server side: idle/keep-alive timeout longer than the load balancer's (e.g. 65 s vs ALB 60 s) to avoid sporadic 502s. HTTP/2 (gRPC) between services carries many streams per connection: balance per request at L7 (Envoy, gRPC client-side LB), since one long-lived connection pins to one pod behind an L4 balancer; HTTP/3/QUIC at the edge avoids TCP head-of-line blocking on lossy links.

`PERF-BP-9` — **Keep payloads small.** Bytes cost serialisation CPU, memory and transfer time. How: return only needed fields (sparse fieldsets, GraphQL selection, protobuf), no embedded base64 blobs (presigned URLs instead), cap list sizes (API), compress text payloads above ~1 KB at the edge (gzip 4–6, brotli 4–5 or zstd for dynamic; higher levels only for precompressed static), skip compression for images/video/archives.

`PERF-BP-10` — **Stream large or unbounded responses.** Buffering whole result sets multiplies memory per request and delays first byte. How: Go: `rows.Next()` writing to an `http.ResponseWriter` with `json.Encoder`/`http.Flusher` per chunk; Node: `pipeline(dbCursorStream, transform, res)` with backpressure honoured (`stream.pipeline`, never ignoring `write()` returning false). For very large exports, generate asynchronously to object storage (SCALE-BP-12).

`PERF-BP-11` — **See DATA-BP-11 (canonical mechanism).** Confirm query cost and stable ordering for the actual pagination workload.

`PERF-BP-12` — **Match runtime parallelism to the container's CPU.** Oversubscribed runtimes get throttled by the CFS quota and spike tail latency. How: Go ≥1.25 sets GOMAXPROCS from the cgroup CPU limit automatically; on older Go use `go.uber.org/automaxprocs`. Node: one process per ≤1 vCPU pod; size `UV_THREADPOOL_SIZE` (default 4) when using fs/dns.lookup/crypto/zlib heavily. Watch `container_cpu_cfs_throttled_periods_total`; consider CPU requests without hard limits for latency-critical services where the platform allows.

`PERF-BP-13` — **Reduce allocations before tuning the GC.** Allocation rate drives GC CPU and pause-related tail latency. How: read `alloc_space` profiles; preallocate slices/maps with capacity, reuse buffers (`sync.Pool` for large short-lived buffers), avoid `[]byte`↔`string` round trips and `fmt.Sprintf` in hot loops (`strconv`, `strings.Builder`), check escapes with `go build -gcflags=-m`; in Node avoid per-request closures/object churn in hot paths, reuse `Buffer`s, avoid megamorphic object shapes.

`PERF-BP-14` — **Set GOMEMLIMIT in containers; tune GOGC deliberately.** Without a limit the Go heap can grow to ~2× live heap at `GOGC=100` and the pod is OOM-killed before GC reacts. How: `GOMEMLIMIT` ≈ 80–90% of the container memory limit (leave room for non-heap: stacks, cgo, mmap); raise `GOGC` (200–400) only when GC CPU > ~10–20% and memory allows; avoid `GOGC=off` + limit on services whose live heap can approach the limit (GC thrash). Go 1.26 enables the Green Tea collector by default; re-benchmark GC-heavy services on upgrade.

`PERF-BP-15` — **See CONC-BP-16 (canonical mechanism).** Measure event-loop delay alongside the hot-path profile.

`PERF-BP-16` — **Make serialisation and logging cheap.** Reflection-based JSON and verbose logging often top CPU profiles of CRUD services. How: Go: `encoding/json` reflects per call; for hot paths consider `goccy/go-json`/`bytedance/sonic`, code-generated encoders, `encoding/json/v2` (GOEXPERIMENT=jsonv2 since 1.25) or protobuf; Node: schema-compiled serialisers (Fastify response schemas via `fast-json-stringify`). Logging: structured, levelled, allocation-light (`slog` with a static level, `zap`, `zerolog`; `pino` with transports in a worker), no per-request debug logs in production, sample high-volume info logs (OBS).

`PERF-BP-17` — **Benchmark micro-optimisations statistically.** Single runs are noise; JIT and compiler eliminate unused results. How: Go: `go test -bench=. -benchmem -count=10 > new.txt` then `benchstat old.txt new.txt` (accept only significant deltas), use `b.Loop()` (Go 1.24+) or sink results to defeat dead-code elimination, `b.ReportAllocs()`. Node: `mitata` or `tinybench` with warm-up, consume results, compare across several runs; pin CPU frequency/noisy neighbours off in CI runners or use relative comparisons on the same machine.

`PERF-BP-18` — **Load test with an open model and correct for coordinated omission.** Closed-loop generators wait for slow responses and stop sending, so stalls never appear in the latency numbers. How: k6 `constant-arrival-rate`/`ramping-arrival-rate` executors (enough `preAllocatedVUs`, watch `dropped_iterations`), `vegeta attack -rate=`, `wrk2 -R`; avoid judging tail latency with `ab`, `hey`, plain `wrk` or k6 VU-based executors; use production-like data and run the generator outside the system under test.

`PERF-BP-19` — **Pick the runtime by workload and team, not benchmarks.** Most backend time is spent waiting on I/O, where Go and Node are both adequate. How: Node/TypeScript for I/O-bound APIs, BFFs, real-time gateways and teams sharing code with the frontend; Go for CPU-mixed work, high concurrency with predictable p99, low memory per instance, infra/proxy-like services and static binaries; Rust/C++ when GC pauses or per-request CPU dominate (codecs, proxies, trading); JVM for large-team ecosystems needing mature tooling; Python where the work is ML/data libraries (native code underneath). Do not split a stack just for speed without profiling evidence.

`PERF-BP-20` — **Enforce performance budgets in CI.** Regressions arrive one innocent commit at a time. How: per-endpoint budgets (p95 latency, query count, payload size, allocations/op) as k6 `thresholds`, benchstat comparisons against the main branch, query-count assertions in integration tests; fail the build or flag the PR on breach; periodic full load test before major releases (SCALE-BP-19).

## Bad practices

`PERF-BAD-1` — **Optimising from intuition.** Effort goes to cold code; real bottleneck untouched. → Instead: PERF-BP-1, PERF-BP-2.

`PERF-BAD-2` — **Averages in dashboards and SLOs.** A 40 ms mean hides a 4 s p99. → Instead: PERF-BP-3.

`PERF-BAD-3` — **Query or RPC inside a loop over results (N+1).** Request time grows with data. → Instead: PERF-BP-6.

`PERF-BAD-4` — **New HTTP client/transport per request, or bodies not drained/closed.** Go: `&http.Client{}` or `&http.Transport{}` in a handler; unclosed `resp.Body` prevents reuse and leaks connections. Node: `new https.Agent()` per call, `keepAlive: false`. → Instead: PERF-BP-8.

`PERF-BAD-5` — **`OFFSET` pagination on large, deep-paged tables, and `COUNT(*)` per page.** → Instead: PERF-BP-11.

`PERF-BAD-6` — **Loading entire result sets or files into memory** (`SELECT *` without limit, `io.ReadAll` on unbounded bodies, `fs.readFile` of uploads, `await res.json()` on huge payloads). Memory spikes, GC storms, OOM. → Instead: PERF-BP-10, bounds (SEC for body size limits).

`PERF-BAD-7` — **Compiling regexes or templates per request.** Go `regexp.MustCompile` inside a handler, Node `new RegExp(` in hot loops, re-parsing templates. → Instead: compile once at init; for untrusted patterns or backtracking risk see SEC (ReDoS).

`PERF-BAD-8` — **Synchronous or CPU-heavy work on the Node event loop** (`fs.readFileSync`, `crypto.pbkdf2Sync`, `zlib.gzipSync`, big `JSON.parse`, `bcrypt.hashSync`). Every concurrent request stalls. → Instead: PERF-BP-15.

`PERF-BAD-9` — **One global mutex around hot shared state.** Throughput flatlines as cores grow; mutex profile hot. → Instead: shard the lock/map, `sync.RWMutex` for read-mostly, atomics, or per-goroutine state merged later (correctness → CONC).

`PERF-BAD-10` — **Logging at debug level, or logging full request/response bodies, in production hot paths.** CPU, allocation and log-bill blowups, plus PII risk (SEC). → Instead: PERF-BP-16.

`PERF-BAD-11` — **Go service in a memory-limited container without `GOMEMLIMIT`.** OOM kills under load spikes although live heap fits. → Instead: PERF-BP-14.

`PERF-BAD-12` — **Unbounded in-process caches/maps and leaked goroutines, timers or listeners.** Memory climbs until OOM, restarts mask it. Go: maps without eviction, goroutines blocked on channels nobody reads, `time.After` in long loops (pre-1.23 timer leaks). Node: module-level arrays/maps, `emitter.on` per request without `off`, closures retained by `setInterval`. → Instead: bounded LRU with TTL (CACHE), context cancellation, heap/goroutine profiles compared over time.

`PERF-BAD-13` — **Benchmarking once, on a laptop, with a closed-loop tool.** Noise and coordinated omission produce wrong conclusions. → Instead: PERF-BP-17, PERF-BP-18.

`PERF-BAD-14` — **Compressing everything at maximum level in the app.** Brotli 11 or gzip 9 on dynamic responses burns CPU for marginal savings; compressing JPEGs/zips wastes CPU entirely. → Instead: PERF-BP-9.

## Anti-patterns

`PERF-AP-1` — **Chatty service graph.**
- Symptoms: one user request fans into dozens of sequential internal calls; traces look like staircases; latency is the sum of hops.
- Why it hurts: latency adds up and tail latency compounds per hop (PERF-BP-4); every hop pays serialisation and connection overhead.
- Way out: parallelise independent calls, add bulk/composite endpoints, move data next to the consumer (read models, SCALE-BP-15), or merge services split along the wrong boundary (ARCH).

`PERF-AP-2` — **ORM-shaped data access on hot paths.**
- Symptoms: lazy-loaded relations, `SELECT *` everywhere, hundreds of queries per request, entities serialised directly to JSON.
- Why it hurts: hidden N+1, over-fetching, and serialisation of fields nobody needs.
- Way out: explicit eager loading or hand-written queries for hot paths (sqlc in Go, Kysely/Drizzle in Node), DTO projections, query-count budgets (PERF-BP-20).

`PERF-AP-3` — **See CACHE-AP-2 (canonical mechanism).** Measure the uncached query and failure path before adding a cache.

`PERF-AP-4` — **Throughput benchmarks as the performance story.**
- Symptoms: "handles 50k RPS" with no latency distribution, no data volume, closed-loop tool, generator on the same host.
- Why it hurts: hides queueing and tail latency, the thing users feel; capacity plans built on it fail at peak.
- Way out: open-model tests reporting latency percentiles at a fixed rate (PERF-BP-18), on production-like data.

`PERF-AP-5` — **Rewrite for speed.**
- Symptoms: proposal to port a service to Go/Rust "because it is slow", no profile attached; the slow part is the database or a downstream call.
- Why it hurts: months of work, new bugs, unchanged latency.
- Way out: profile and trace first (PERF-BP-1); move only proven CPU-bound hotspots to a worker pool or a dedicated service (PERF-BP-15, PERF-BP-19).

`PERF-AP-6` — **Kitchen-sink request path.**
- Symptoms: the handler validates, writes, sends emails, calls analytics, recomputes aggregates and renders a large response in one synchronous flow.
- Why it hurts: latency and failure rate are the sum of everything; the critical path cannot be optimised in isolation.
- Way out: identify the minimum work the response needs; defer the rest (SCALE-BP-12) and precompute the aggregates (materialised views, denormalised columns updated on write).

`PERF-AP-7` — **Tuning knobs without a feedback loop.**
- Symptoms: copied `GOGC`, pool sizes, `--max-old-space-size`, thread pool sizes and timeouts with no comments or measurements; nobody knows why the values are what they are.
- Why it hurts: settings fight each other (e.g. heap flag above the container limit) and silently go stale.
- Way out: document each knob's rationale next to it, derive from measurements (PERF-BP-5, PERF-BP-14), re-validate in the regression suite (PERF-BP-20).

## Go / Node.js notes

- Concurrency model: Go runs goroutines on all cores with a preemptive scheduler, so a CPU-heavy request slows others only proportionally. Node runs JS on one thread; any synchronous CPU work blocks all requests on that process (PERF-BP-15). libuv's threadpool (default 4) serves `fs`, `dns.lookup`, `crypto.pbkdf2/scrypt`, `zlib`, and saturates silently.
- Profiling: Go has first-class built-in profilers (`pprof`, `trace`, PGO via `default.pgo` giving ~2–7% CPU gains). Node relies on V8 profiles (`--cpu-prof`, `--heap-prof`, `--inspect` + DevTools, `0x`); clinic.js is useful but sees little maintenance, so prefer the built-in flags for current Node versions.
- GC: Go GC is concurrent and non-moving with sub-millisecond pauses; its cost shows up as CPU and assist latency proportional to allocation rate (knobs: GOGC, GOMEMLIMIT). V8 is generational; large old-space heaps cause longer major GCs; `--max-old-space-size` sets the old-space ceiling; do not rely on the default heap sizing in containers, set it explicitly with headroom for Buffers, which live off-heap.
- HTTP clients: Go `http.Transport` defaults to `MaxIdleConnsPerHost: 2` and no timeouts on `DefaultClient`; Node `fetch` (undici) keeps alive and pools by default, undici `request` is faster than `fetch` for hot internal calls.
- JSON: Go `encoding/json` is reflection-based and relatively slow; `encoding/json/v2` is opt-in via GOEXPERIMENT in 1.25+. V8's `JSON.parse`/`stringify` are fast native code but synchronous on the main thread, so size is the risk, not speed.
- DB drivers: pgx (native protocol, batch, `CopyFrom`, statement cache) outperforms `lib/pq`; in Node, `pg` with `pg-cursor`/`pg-query-stream` for streaming, `postgres` (porsager) for pipelining. Prisma's query engine adds per-query overhead; profile before using it on high-QPS paths.
- Memory per connection/request: idle goroutines start with ~2–8 KB stacks; Node per-request closures and promise chains are heavier, so Node needs more memory per concurrent request at very high concurrency.
- Leak tooling: Go `goleak` in tests, `pprof` heap diffs (`-base`), goroutine dumps; Node heap snapshots (`--heapsnapshot-signal=SIGUSR2`, `v8.writeHeapSnapshot()`) compared in DevTools.
