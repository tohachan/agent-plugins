# Resilience — rules

> **Scope:** keeping a service up and correct when its dependencies, its own instances or a whole failure domain misbehave: timeouts and deadlines, retries, circuit breakers, bulkheads, load shedding, rate limiting, backpressure, degradation, health checks, draining, redundancy, dependency SLAs, failure testing, and recovery dynamics (thundering herds, hedging, metastable failures). **Hands off to:** making retried writes safe → IDEM; worker shutdown, cancellation plumbing and bounded fan-out → CONC; broker redelivery and DLQs → MSG; capacity planning and autoscaling → SCALE; cache stampede protection → CACHE; SLOs, alerts and dashboards → OBS; abuse-oriented rate limiting and auth → SEC; deploy strategy and rollbacks → OPS; error/status contracts → API.

## Best practices

`RES-BP-1` — **Bound each outbound operation and its retries by an effective deadline.** Follow caller contexts/signals, wrappers, client and proxy configuration end to end. An HTTP client with zero Timeout can be correct when every call has an enforced deadline. Choose connect/per-attempt/overall budgets from measured latency and caller needs; handle streaming/long-lived calls explicitly. Bound pool waits and DB/cache calls too.

`RES-BP-2` — **Propagate deadlines and spend a timeout budget, inner shorter than outer.** Why: a downstream that keeps working after the edge timed out wastes capacity during overload. How: derive child contexts from the request deadline (`context.WithTimeout(ctx, …)` never longer than the remaining budget); gRPC propagates deadlines automatically; for HTTP pass the remaining budget in a header (e.g. `X-Request-Timeout-Ms`) and honour it; edge timeout > sum of sequential inner timeouts including retries; stop work and return early when remaining budget < expected latency.

`RES-BP-3` — **Retry only transient failures of idempotent operations.** Why: retrying a non-idempotent POST duplicates side effects; retrying 400/401/422 is pointless load. How: retry connection errors, 502/503/504, 429 (honouring `Retry-After`), gRPC `UNAVAILABLE`/`RESOURCE_EXHAUSTED`; retry writes only with an idempotency key (IDEM); never retry `DEADLINE_EXCEEDED` past the caller's deadline.

`RES-BP-4` — **Back off exponentially with full jitter and a small attempt cap.** Why: synchronized retries arrive as waves that re-crash a recovering dependency. How: `sleep = random(0, min(cap, base × 2^attempt))`, base 100ms, cap 10s for background work, ~1s for interactive paths; 2–3 attempts total for online requests; total retry time bounded by the deadline (RES-BP-2).

`RES-BP-5` — **Enforce a retry budget per client.** Why: with per-request caps, a fully down dependency still receives 3× normal load. How: allow retries only while retries ≤ 10–20% of recent requests (token bucket refilled by successes, as in gRPC retry throttling and Envoy `retry_budget`); stop retrying entirely when the budget is empty.

`RES-BP-6` — **Retry at one layer only.** Why: retries multiply: 3 attempts at each of 4 layers = 3⁴ = 81 calls to the bottom dependency per user request. How: pick the layer closest to the failing dependency; other layers fail fast and return `503`/`UNAVAILABLE` with a "do not retry" signal (e.g. non-retryable status, or a header); audit mesh, SDK and app config together.

`RES-BP-7` — **Wrap slow or flaky dependencies in a circuit breaker that also counts timeouts.** Why: without one, every request pays the full timeout while the dependency is down, exhausting the caller. How: open on failure rate ≥ 50% over a rolling window with a minimum volume (e.g. ≥ 20 requests in 10s) or on slow-call rate; open state fails fast to a fallback for 5–30s; half-open admits a few probes (1–5); breaker per dependency and ideally per endpoint/host, not global.

`RES-BP-8` — **Isolate dependencies with bulkheads.** Why: one slow dependency consuming every connection or goroutine takes down unrelated endpoints. How: separate HTTP connection pools/agents per dependency with `MaxConnsPerHost`/`connections` caps; per-dependency concurrency limits (semaphore sized to dependency capacity, CONC); separate DB pools or deployments for batch vs interactive traffic; separate worker pools per queue priority.

`RES-BP-9` — **Shed load early, cheaply and by priority.** Why: accepting work you cannot finish within its deadline makes every request slow (goodput collapse). How: cap in-flight requests per instance (e.g. 2–4× the concurrency the instance sustains at target latency) and reject excess with `503` + `Retry-After` before parsing bodies; drop requests whose deadline already passed or that waited in queue longer than a threshold (CoDel-style, e.g. 100ms); adaptive limits (AIMD/gradient on latency) when load varies; shed low-priority classes first.

`RES-BP-10` — **Rate-limit per client at the edge and protect each dependency's quota.** Why: one tenant or bug-looping client consumes shared capacity; exceeding a provider quota gets you banned or throttled. How: token bucket/GCRA keyed by API key/tenant (e.g. 100 req/s, burst 200), enforced at the gateway or with a Redis-backed limiter for global limits (atomic Lua or `redis-cell`), failing open with a local fallback limiter if Redis is down; respond `429` with `Retry-After` (and `RateLimit-*` headers); client-side limiters for outbound provider quotas. Abuse/brute-force limits → SEC.

`RES-BP-11` — **Propagate backpressure instead of buffering.** Why: unbounded in-memory queues turn overload into OOM kills and long tail latency. How: bounded channels/queues with explicit reject or block-with-deadline; consumers pull at their pace (broker prefetch/`max.poll.records` sized to processing capacity, MSG); Node streams with `pipeline()` respecting `write()` return values; HTTP/2 and gRPC flow control left at defaults rather than disabled.

`RES-BP-12` — **Design degraded modes and fallbacks per feature, and test them.** Why: users prefer a page without recommendations to an error page; untested fallbacks fail when needed. How: classify each dependency as critical or optional per endpoint; optional → fallback (stale cache with `stale-if-error`, default value, hidden widget) under a short timeout; critical → fail fast with a clear error; feature flags/kill switches to turn off expensive features under load; fallbacks must not call another dependency that is likely failing for the same reason.

`RES-BP-13` — **Liveness checks the process only; readiness checks the ability to serve; startup gates slow boots.** Why: liveness that checks the DB restarts every pod when the DB blips — a restart storm on top of an outage. How: liveness = event loop/goroutine scheduler responsive, no deadlock (cheap handler, no I/O), `failureThreshold` 3+, `periodSeconds` 10; readiness = warm-up done, not draining, local resources available (pool not exhausted), optionally critical dependencies — but avoid failing readiness on a shared dependency all pods use (whole fleet goes unready → total outage instead of partial errors); startup probe with `failureThreshold × periodSeconds` ≥ worst boot time.

`RES-BP-14` — **Drain gracefully on shutdown.** Why: pods killed mid-request drop in-flight calls, and endpoints keep receiving traffic for seconds after SIGTERM. How: on SIGTERM fail readiness, keep serving for the endpoint-propagation delay (`preStop` sleep 5–15s, or k8s native `sleep` action), then stop accepting, finish in-flight requests (`http.Server.Shutdown`/`server.close()`), close idle keep-alives, flush telemetry; `terminationGracePeriodSeconds` ≥ preStop + longest request + margin (default 30s is often too short with long requests). Workers → CONC-BP-19.

`RES-BP-15` — **Select failure domains and spare capacity from the availability/recovery requirement.** Single-zone, multi-zone and multi-region designs have different accepted outage/cost trade-offs; three zones are not mandatory for every production service. For a required zone-loss scenario, prove surviving capacity, routing and data failover meet the target. Use disruption budgets for supported voluntary disruptions and test failures they do not cover.

`RES-BP-16` — **Know each dependency's SLA and design for the composite.** Why: under an independence assumption, serial hard-dependency availabilities multiply: five independent hard dependencies at 99.9% give about 99.5%; real failures are often correlated. How: list dependencies per critical path with their SLO, timeout, retry policy, fallback; your SLO must not exceed what the critical path permits unless optional dependencies degrade gracefully; remove hard dependencies from critical paths (cache, async, fallback); SLO definitions → OBS.

`RES-BP-17` — **Recover gently: jitter reconnects, warm up slowly, cap recovery traffic.** Why: after an outage, every client reconnects and replays at once (thundering herd) and re-crashes the dependency. How: jittered reconnect backoff (RES-BP-4) in every client including WebSocket/SSE; load balancer slow start (Envoy `slow_start_config`, ALB slow start 30–120s) for new instances; half-open breakers admit few probes; queue consumers resume with bounded concurrency; cache warm-up before taking traffic (CACHE).

`RES-BP-18` — **Hedge only idempotent reads, after a percentile delay, under a budget.** Why: tail latency from a single slow replica hurts fan-out requests; naive hedging doubles load. How: send a second request after the p95 latency of that call if the first has not answered; cancel the loser; cap hedges at ~5% extra load; never hedge writes or calls without cancellation.

`RES-BP-19` — **Break metastable loops: make overload self-limiting.** Why: a trigger (spike, deploy, cache flush) can push a system into a state sustained by its own retries, timeouts and cold caches even after the trigger is gone. How: retry budgets (RES-BP-5), deadline-aware shedding (RES-BP-9), drop work already timed out upstream, LIFO or bounded-wait queues under overload, cache-miss request coalescing (CACHE); runbook levers to cut load (disable retries, shed a priority class, block a client) without a deploy.

`RES-BP-20` — **Test failure handling regularly in production-like conditions.** Why: timeouts, breakers and fallbacks that were never exercised are usually misconfigured. How: fault injection in CI/staging (Toxiproxy latency/reset, mesh fault injection: 5% aborts, 2s delays); game days and chaos experiments (Chaos Mesh, Litmus, AWS FIS: kill pods, drop an AZ, slow the DB) with a hypothesis, blast-radius limit and abort condition; load tests that include a dependency failure.

## Bad practices

`RES-BAD-1` — **An outbound path with no effective time bound.** Inspect the complete call chain: client defaults alone do not prove a missing deadline. Confirm that callers/wrappers propagate and enforce a finite budget for this operation; see RES-BP-1.

`RES-BAD-2` — **`context.Background()` or a fresh unbounded context for downstream calls inside a handler.** Drops the caller's deadline and cancellation. → Instead: RES-BP-2.

`RES-BAD-3` — **Retry loop without backoff or jitter** (`for i := 0; i < 5; i++ { … }`, `retry(5)` with fixed delay). Synchronised hammering of a failing dependency. → Instead: RES-BP-4.

`RES-BAD-4` — **Retrying non-idempotent writes or all errors.** Duplicate side effects; retries on 4xx waste capacity. → Instead: RES-BP-3, IDEM-BP-1.

`RES-BAD-5` — **Liveness probe that checks DB, Redis or downstream services.** A dependency blip restarts the whole fleet, turning a partial outage into a total one and adding cold-start load. → Instead: RES-BP-13.

`RES-BAD-6` — **Same endpoint and thresholds for liveness and readiness; no startup probe for slow boots.** Pods killed during warm-up (CrashLoopBackOff) or never removed from rotation while unhealthy. → Instead: RES-BP-13.

`RES-BAD-7` — **No SIGTERM handling or no preStop delay.** In-flight requests cut; 502s on every deploy as the LB still routes to terminating pods. → Instead: RES-BP-14.

`RES-BAD-8` — **Node `server.keepAliveTimeout` (default 5s) below the load balancer idle timeout (ALB default 60s).** The LB reuses a socket the server just closed → sporadic 502s. → Instead: `keepAliveTimeout` > LB idle timeout (e.g. 65s) and `headersTimeout` > `keepAliveTimeout`.

`RES-BAD-9` — **Unbounded in-memory queue or buffer in front of a slow dependency.** Latency grows unboundedly, then OOM. → Instead: RES-BP-9, RES-BP-11.

`RES-BAD-10` — **One shared connection pool/agent for all dependencies, or an unbounded one.** One slow dependency starves the others, or opens thousands of sockets. → Instead: RES-BP-8.

`RES-BAD-11` — **Circuit breaker that ignores timeouts or is shared across unrelated endpoints/hosts.** Never opens on slowness, or one bad endpoint opens the breaker for everything. → Instead: RES-BP-7.

`RES-BAD-12` — **Rate limit counters kept per instance while presented as a global limit.** Effective limit = limit × replicas and changes with autoscaling. → Instead: RES-BP-10.

`RES-BAD-13` — **Fallback that calls another remote dependency or silently returns wrong data.** Correlated failure, or a correctness bug (e.g. "price = 0", "authorized = true" on error). → Instead: RES-BP-12; fail closed on authorization (SEC).

`RES-BAD-14` — **All replicas in one AZ or one node; no PodDisruptionBudget.** A node drain or AZ event takes the service down. → Instead: RES-BP-15.

`RES-BAD-15` — **Clients reconnecting on a fixed interval** (WebSocket reconnect every 1s, consumers restarting immediately). Synchronised reconnect storm after recovery. → Instead: RES-BP-17.

`RES-BAD-16` — **Connection pools with no max lifetime or health validation.** After a DB failover, proxy restart or LB IP change, pooled connections keep pointing at the old or dead endpoint until each fails a request; long-lived HTTP/2 or gRPC connections pin traffic to a few backends. → Instead: `MaxConnLifetime` 30–60 min with jitter, `MaxConnIdleTime`, health check on borrow/period (pgxpool `HealthCheckPeriod`), gRPC `MaxConnectionAge` on servers so clients rebalance (RES-BP-15).

## Anti-patterns

`RES-AP-1` — **Retry amplification stack.** Symptoms: retries configured in the SDK, the app's HTTP wrapper, the service mesh and the edge client; dependency traffic spikes to multiples of normal during incidents. Why it hurts: exponential load multiplication exactly when the dependency is weakest; turns blips into metastable outages. Way out: inventory every retry layer, keep one (RES-BP-6), add retry budgets (RES-BP-5).

`RES-AP-2` — **Timeouts inverted or missing in the chain.** Symptoms: gateway 30s, service A 60s, client of B 0/none; edge times out while inner calls continue and retry. Why it hurts: abandoned work consumes capacity; users retry on top of it. Way out: budgeted, propagated deadlines (RES-BP-1, RES-BP-2), inner < outer, verified per hop.

`RES-AP-3` — **Deep health checks as a cascading failure detector.** Symptoms: `/health` that calls the DB, Redis and three downstream services' `/health`, used for liveness and readiness, sometimes recursively across services. Why it hurts: one dependency failure marks every service unhealthy; orchestrators restart or remove everything simultaneously; health traffic itself loads dependencies. Way out: shallow liveness, local readiness, dependency status exposed as metrics and alerts (OBS), not as probe failures (RES-BP-13).

`RES-AP-4` — **Synchronous call chain as architecture.** Symptoms: request path traverses 4+ services synchronously, each a hard dependency; availability and latency are products/sums of all hops. Why it hurts: composite availability falls with every hop (RES-BP-16) and tail latencies add. Way out: collapse chatty services (ARCH), cache reference data, move non-essential steps async via queue/outbox (MSG, IDEM), make optional calls degradable.

`RES-AP-5` — **Queue as shock absorber without limits.** Symptoms: "we put a queue in front so we can't be overloaded"; unbounded broker backlog, no age-based alerting, consumers autoscale into the DB. Why it hurts: overload becomes hours of delay, then expired/irrelevant work processed later and the DB overloaded by scaled consumers. Way out: bounded backlog or TTL on messages, consumer concurrency capped by downstream capacity, alert on oldest-message age (RES-BP-11, MSG).

`RES-AP-6` — **Fallback that is never exercised.** Symptoms: fallback branches with no tests or metrics; first activation during an incident throws, returns wrong shapes or overloads a secondary path (e.g. falling back from cache to DB at full traffic). Why it hurts: the safety net fails exactly when needed and can make the incident worse. Way out: metric per fallback activation, regular fault injection (RES-BP-20), size the fallback path for full load or shed instead.

`RES-AP-7` — **Autoscaling as the overload strategy.** Symptoms: no concurrency limits or shedding; plan is "HPA will add pods"; scale-up takes minutes while latency and errors spike; new pods add DB connections to a saturated DB. Why it hurts: scaling is slower than spikes and moves the bottleneck to a shared dependency. Way out: admission control and shedding per instance (RES-BP-9), pool caps sized to DB limits, autoscaling as the second line (SCALE).

`RES-AP-8` — **Metastable retry storm left to self-heal.** Symptoms: incident trigger removed (deploy rolled back, spike over) but error rate stays high until a manual action like restarting everything or blocking traffic; retries and timeouts dominate traffic. Why it hurts: the system stays down without a cause in sight. Way out: RES-BP-19 levers and runbooks; RES-BP-5 budgets; recovery ramp (RES-BP-17).

`RES-AP-9` — **Hidden shared single point of failure.** Symptoms: one Redis (or one DB, one NAT gateway, one config service) quietly serves sessions, rate limiting, locks, cache and queues for many services; "redundant" services all depend on it; its outage takes down everything at once. Why it hurts: redundancy at the service tier is cancelled by a shared dependency; blast radius is the whole platform. Way out: dependency inventory per critical path (RES-BP-16); split by criticality (separate instances for sessions vs cache), make it highly available (replicas + failover, multi-AZ), and decide fail-open vs fail-closed per use (e.g. rate limiter fails open with local limits, sessions fail closed).

## Go / Node.js notes

- **Go HTTP client.** `http.Client.Timeout` bounds the whole exchange including body read; for streaming use per-request ctx deadlines plus `Transport.ResponseHeaderTimeout`. Set `DialContext` (`net.Dialer{Timeout: 2s}`), `TLSHandshakeTimeout`, `MaxConnsPerHost`, and raise `MaxIdleConnsPerHost` (default 2) to avoid connection churn under load. Always drain and close `resp.Body`.
- **Go HTTP server.** Set `ReadHeaderTimeout` (e.g. 5s), `ReadTimeout`/`WriteTimeout` or per-handler `http.TimeoutHandler`/`http.ResponseController` deadlines, `IdleTimeout` > LB idle; `srv.Shutdown(ctx)` waits for in-flight handlers but not hijacked/streaming connections — track those yourself.
- **Node HTTP client.** Global `fetch` is undici: no total timeout, 300s `headersTimeout`/`bodyTimeout` defaults; use `AbortSignal.timeout(ms)` combined with the request signal via `AbortSignal.any`. axios needs `timeout` and, for connect-phase hangs, also a `signal`. Use a dedicated `undici.Agent`/`http.Agent` per dependency with `connections`/`maxSockets`.
- **Node HTTP server.** Defaults: `requestTimeout` 300s, `headersTimeout` 60s, `keepAliveTimeout` 5s; tune to the LB (RES-BAD-8). `server.close()` stops accepting but waits for keep-alive sockets — call `server.closeIdleConnections()` (Node 18.2+) and set a hard exit timer below the grace period.
- **Event-loop health.** A blocked Node event loop fails liveness and readiness together and drops every connection on that process; liveness should therefore be cheap and thresholds tolerant, with CPU work offloaded (CONC-BP-16). Use `@fastify/under-pressure` or equivalent to shed load on event-loop delay/heap thresholds.
- **Libraries.** Go: `failsafe-go` (retry, breaker, bulkhead, hedge, budget), `sony/gobreaker`, `cenkalti/backoff/v5`, `golang.org/x/time/rate`, `platinummonkey/go-concurrency-limits` (adaptive limits). Node: `cockatiel` (retry/breaker/bulkhead/timeout policies), `opossum`, `p-retry`, `rate-limiter-flexible`, `@godaddy/terminus`.
- **gRPC.** Both stacks support service-config retry/hedging policies with built-in throttling (`retryThrottling`); prefer them over hand-rolled loops and keep mesh retries off for the same routes. Go propagates deadlines through `ctx` automatically; Node requires passing `deadline` in call options explicitly.
