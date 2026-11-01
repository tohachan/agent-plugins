# Performance — audit checklist

> **Scope:** latency, throughput and resource efficiency of a single service and its request paths: measuring and profiling, percentiles and tail latency, queueing basics, the usual hotspots, I/O efficiency (batching, connection reuse, protocols, payloads, streaming), runtime tuning (Go GC/GOMAXPROCS, Node event loop), benchmarks, load testing, budgets, runtime choice by workload. **Hands off to:** capacity planning, scale-out, sharding, the knee as a capacity number → SCALE · cache design → CACHE · indexes, query plans, transactions → DATA · pagination and response contract shape → API · timeouts, backpressure, load shedding → RES · goroutine/worker pools and locking correctness → CONC · metrics, tracing, SLO alerting → OBS · ReDoS, decompression bombs → SEC.

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| `PERF-CHK-1` | Are latency targets defined as percentiles per critical endpoint, and measured from histograms? | SLO docs, dashboards, metric types (`histogram`, `Summary`), `prometheus.NewHistogramVec`, `prom-client` `Histogram`. Fail: only averages or no per-route latency. PERF-BP-1, BP-3, BAD-2 | Medium |
| `PERF-CHK-2` | Is profiling available safely in production? | Go: `_ "net/http/pprof"` imported (must be on an internal port, not the public mux), continuous profiler agent. Node: `--cpu-prof` usage, profiler agent. Fail: no way to profile production, or pprof exposed publicly (also SEC). PERF-BP-2 | Low |
| `PERF-CHK-3` | Are there N+1 queries or RPCs in loops on hot paths? | Go: `for ... range` containing `db.Query`/`QueryRow`/`.First(`/client calls. Node: `for (... of ...) { await` with DB/HTTP inside, `.map(async` followed by per-item queries, GraphQL resolvers without DataLoader. Confirm with trace query counts. PERF-BP-6, BAD-3, AP-2 | High |
| `PERF-CHK-4` | Are HTTP clients shared and connections reused? | Go: `http.Client{` or `http.Transport{` inside handlers/functions called per request, `http.DefaultClient` with no timeout, missing `defer resp.Body.Close()` and drain, `MaxIdleConnsPerHost` unset under high per-host concurrency. Node: `new Agent(` per call, `keepAlive: false`, `axios.create` per request. PERF-BP-8, BAD-4 | Medium |
| `PERF-CHK-5` | Do server keep-alive/idle timeouts exceed the load balancer's? | Go `http.Server{IdleTimeout:` (falls back to `ReadTimeout`), Node `server.keepAliveTimeout` (default 5 s) and `headersTimeout`, LB idle timeout (ALB default 60 s). Fail: server timeout < LB timeout (intermittent 502s). PERF-BP-8 | Medium |
| `PERF-CHK-6` | Are list endpoints bounded and paginated efficiently? | `OFFSET` with user-controlled page numbers on large tables, missing `LIMIT`, `COUNT(*)` per request, `limit` param without max. Check `EXPLAIN` for deep pages. PERF-BP-11, BAD-5 | Medium |
| `PERF-CHK-7` | Are large payloads streamed instead of buffered? | Go: `io.ReadAll(r.Body)`/`io.ReadAll(resp.Body)` without `http.MaxBytesReader`/`io.LimitReader`, building full slices before `json.Marshal`. Node: `await res.text()`/`json()` on large downloads, `fs.readFile` for uploads/exports, `.findMany()` without `take`. PERF-BP-10, BAD-6 | Medium |
| `PERF-CHK-8` | Is the Node event loop protected from sync and CPU-heavy work? | Grep `Sync(` in request code (`readFileSync`, `pbkdf2Sync`, `scryptSync`, `gzipSync`), `bcrypt.hashSync`, image/PDF libs in handlers, large `JSON.parse`. Check event loop delay metric exists. Fail: sync work on request paths or no ELD visibility on a CPU-mixed service. PERF-BP-15, BAD-8 | High |
| `PERF-CHK-9` | Is runtime parallelism aligned with container CPU? | Go version in `go.mod` (<1.25 needs `automaxprocs`), `GOMAXPROCS` env; k8s CPU limits vs requests; CFS throttling metrics; Node: `cluster`/PM2 inside small pods, `UV_THREADPOOL_SIZE`. PERF-BP-12 | Medium |
| `PERF-CHK-10` | Is Go memory bounded by `GOMEMLIMIT` and Node heap sized to the container? | Deployment env `GOMEMLIMIT`, `debug.SetMemoryLimit`; Node `--max-old-space-size` vs memory limit (must leave room for off-heap buffers), `NODE_OPTIONS`. Fail: Go service with memory limit but no GOMEMLIMIT and OOMKilled history; Node heap flag ≥ container limit. PERF-BP-14, BAD-11 | Medium |
| `PERF-CHK-11` | Are there memory or goroutine/listener leaks? | Memory graphs trending up between deploys; Go goroutine count growth, `goleak` in tests; Node `MaxListenersExceededWarning` in logs, module-level growing collections, heap snapshots diff. PERF-BAD-12 | High |
| `PERF-CHK-12` | Are hot-path allocations, serialisation and regex compilation under control? | Profiles showing `encoding/json`, `runtime.mallocgc`, `gcBgMarkWorker` high; `regexp.MustCompile`/`regexp.Compile` inside functions, Node `new RegExp(` in loops; `fmt.Sprintf` in tight loops. PERF-BP-13, BP-16, BAD-7 | Low |
| `PERF-CHK-13` | Is lock contention measured and avoided on hot shared state? | Go: package-level `sync.Mutex` guarding maps used per request, mutex/block profile; Node: N/A for JS state, but check synchronous queues in-process. PERF-BAD-9 | Medium |
| `PERF-CHK-14` | Is logging volume and cost proportionate? | Log level config in prod, body logging middleware (`morgan('combined')` plus body dumps, `httputil.DumpRequest`), `console.log` in hot paths (synchronous to TTY/files), log bill. PERF-BP-16, BAD-10 | Low |
| `PERF-CHK-15` | Are payloads lean and compression configured sensibly? | Response sizes in access logs/traces, `SELECT *` serialised to clients, base64 blobs in JSON, compression middleware level (`compression({ level: 9 })`, `gzip.BestCompression`), compression of already-compressed content, edge compression config. PERF-BP-9, BAD-14 | Low |
| `PERF-CHK-16` | Do load tests use an open model, realistic data, and report percentiles? | k6 scripts: executor type (`constant-arrival-rate` vs `vus`/`iterations`), `dropped_iterations`, thresholds; vegeta/wrk2 rate flags; dataset size. Fail: closed-loop tool for tail latency claims, or no load test for critical paths. PERF-BP-18, BAD-13, AP-4 | Medium |
| `PERF-CHK-17` | Are microbenchmarks statistically sound? | `_test.go` `Benchmark*` functions with result sinks/`b.Loop`, `-count` and benchstat in CI or docs; Node bench scripts with warm-up. Fail: single-run numbers used to justify changes. PERF-BP-17 | Low |
| `PERF-CHK-18` | Are performance budgets enforced to catch regressions? | CI config for k6 thresholds, benchstat gates, query-count assertions; release checklist with load test. Fail: none for latency-critical services. PERF-BP-20, AP-7 | Medium |
| `PERF-CHK-19` | Is internal RPC efficient for its volume? | High-volume service-to-service JSON over HTTP/1.1 without keep-alive; gRPC behind an L4 balancer (all traffic to one pod); per-call TLS handshakes. PERF-BP-8 | Low |

## Also scan for (rules not cited above)

Bodies: `knowledge/perf/rules.md`, looked up by ID.

- PERF-BAD-1 — Optimising from intuition
- PERF-BAD-2 — Averages in dashboards and SLOs
- PERF-BAD-3 — Query or RPC inside a loop over results (N+1)
- PERF-BAD-4 — New HTTP client/transport per request, or bodies not drained/closed
- PERF-BAD-5 — `OFFSET` pagination on large, deep-paged tables, and `COUNT(*)` per page
- PERF-BAD-6 — Loading entire result sets or files into memory
- PERF-BAD-7 — Compiling regexes or templates per request
- PERF-BAD-8 — Synchronous or CPU-heavy work on the Node event loop
- PERF-BAD-10 — Logging at debug level, or logging full request/response bodies, in production hot paths
- PERF-BAD-11 — Go service in a memory-limited container without `GOMEMLIMIT`
- PERF-BAD-13 — Benchmarking once, on a laptop, with a closed-loop tool
- PERF-BAD-14 — Compressing everything at maximum level in the app
- PERF-AP-1 — Chatty service graph
- PERF-AP-2 — ORM-shaped data access on hot paths
- PERF-AP-3 — See CACHE-AP-2 (canonical mechanism)
- PERF-AP-4 — Throughput benchmarks as the performance story
- PERF-AP-5 — Rewrite for speed
- PERF-AP-6 — Kitchen-sink request path
- PERF-AP-7 — Tuning knobs without a feedback loop
