# Observability — rules

> **Scope:** the signals that tell you what production is doing and why: structured logs, metrics, distributed traces, profiles, error tracking; SLIs/SLOs and error budgets; alerting, dashboards, runbooks, postmortems; audit vs debug logging. **Hands off to:** health/readiness semantics and degradation → RES; probe and rollout wiring → OPS; PII classification, secret handling and audit-log tamper-proofing → SEC; queue mechanics behind lag signals → MSG; latency budgets and profiling-driven optimisation → PERF; autoscaling on these signals → SCALE.

## Best practices

`OBS-BP-1` — **Emit structured JSON logs with a fixed core schema.** Free text cannot be filtered or aggregated reliably. How: every line carries `ts` (RFC 3339, UTC), `level`, `msg` (a constant string, not interpolated), `service`, `version`, `env`, `trace_id`, `span_id`, plus typed fields (`order_id`, `duration_ms`); write to stdout and let the platform ship it.

`OBS-BP-2` — **Use levels with operational meaning and change them at runtime.** Otherwise ERROR is noise and DEBUG is absent when needed. How: ERROR = needs a human or broke a request; WARN = degraded but handled (retry succeeded, fallback used); INFO = one line per business event or request at the boundary; DEBUG off in prod but switchable per service/module without redeploy (admin endpoint, config watch, or `LOG_LEVEL` via flag service).

`OBS-BP-3` — **Correlate every signal by trace ID.** Without it, jumping from an alert to the exact log lines takes minutes of guessing. How: OTel context in the request context; log handler reads `trace_id`/`span_id` from it; error tracker events and exemplars on histograms carry the same ID; return `traceparent` or a `X-Request-Id` to clients for support tickets. Also stamp every signal with build identity: `build_info{version,commit,runtime_version} 1` gauge, `service.version` OTel resource attribute, deploy annotations on dashboards.

`OBS-BP-4` — **Redact at the source with an allowlist.** Logs and traces get copied to vendors, laptops and tickets; one leaked token is a breach (→ SEC). How: log typed structs with explicit fields rather than whole requests; never log `Authorization`, cookies, passwords, full PAN, raw request bodies; redaction hook in the logger (`pino` `redact`, slog `ReplaceAttr`) and a Collector `redaction`/`transform` processor as a second net.

`OBS-BP-5` — **Budget log volume and sample the repetitive part.** Volume is the dominant observability cost: 5 k rps × 1 KB per request log = ~432 GB/day. How: no per-request INFO on hot paths when access logs already exist; rate-limit identical messages (zap sampler, custom slog handler: first N per second then 1/M); keep 100% of ERROR and audit; set an ingest budget per service and alert on breach.

`OBS-BP-6` — **Instrument every service with RED, every resource and bounded pool with USE.** These two cover nearly all "is it the service or the thing under it" questions, and most outages start as a pool quietly hitting its limit. How: RED = request rate, errors, duration histogram per route template and status class; USE = utilisation, saturation, errors for CPU (incl. cgroup throttling), memory, DB and HTTP client pools (in-use, idle, wait count, wait duration), worker semaphores, Go goroutines, Node event-loop delay/utilisation, file descriptors; alert on rising pool wait time, not on CPU.

`OBS-BP-7` — **Record latency as histograms with buckets bracketing the SLO.** Averages hide the tail and percentiles cannot be averaged across pods. How: Prometheus histogram with buckets e.g. 5ms…10s including the exact SLO threshold (e.g. 0.3 s) or a native/exponential histogram; query `histogram_quantile(0.99, sum by (le, route) (rate(..._bucket[5m])))`.

`OBS-BP-8` — **Control label cardinality and follow standard naming.** Series count = product of label values; one `user_id` label can create millions of series and take down Prometheus; inconsistent names break cross-service dashboards. How: labels only from bounded sets (route template not raw path, status class, method, outcome enum); never IDs, emails, URLs, error messages; budget e.g. < 1–5 k series per metric per instance; alert on `prometheus_tsdb_head_series` growth, drop attributes with OTel views. Names: snake_case, base units (`_seconds`, `_bytes`), counters end in `_total`; OTel semconv names (`http.server.request.duration`, attributes `http.route`, `http.response.status_code`).

`OBS-BP-9` — **Propagate trace context across every hop, including messages.** Traces that stop at the producer hide where async latency and failures happen. How: W3C `traceparent`/`tracestate` (+ `baggage` sparingly, never PII) on HTTP/gRPC; inject into Kafka record headers, AMQP headers, SQS message attributes, job payload metadata; consumers start a span linked (span links) to the producer context, especially for batch consumption.

`OBS-BP-10` — **Make spans useful: semantic attributes, status, events.** A trace of unnamed spans says nothing. How: span names are low-cardinality (`GET /orders/{id}`, `orders.reserve_stock`); set `db.system.name`, `db.operation.name`, `messaging.system`, `messaging.destination.name`, `peer.service`; record errors with `RecordError` + status Error; add domain attributes (`tenant.tier`, `order.items_count`) but no PII.

`OBS-BP-11` — **Use tail sampling to keep what matters.** Random head sampling at 1% drops 99% of the errors you need. How: Collector tier with `loadbalancing` exporter by trace ID → `tail_sampling` policies: keep 100% status Error, keep latency > p99 threshold, keep specific tenants/routes, probabilistic 1–10% for the rest; set `decision_wait` above your longest normal trace.

`OBS-BP-12` — **Define SLIs as good/total events measured close to the user, and SLOs per user journey.** CPU or "pod up" says nothing about user experience. How: availability SLI = non-5xx, non-timeout responses / valid requests (exclude 4xx caused by the client; count own 429s as bad if they hit legitimate traffic); latency SLI = requests faster than threshold / total; measured at the load balancer or server edge; SLO e.g. 99.9% over 28 days, documented with owner. Error budget = 1 − SLO (99.9% → ~43 min/30 d) backed by a written policy: budget exhausted → freeze risky launches and prioritise reliability work; review burn weekly. An SLO without consequences is just a dashboard.

`OBS-BP-13` — **Page on multi-window burn rate, ticket on slow burn.** Static error-rate thresholds either flap or fire too late. How: for a 30-day SLO, page when 2% of budget burns in 1 h (burn rate 14.4) or 5% in 6 h (rate 6), each confirmed by a short window (5 m / 30 m); ticket when 10% burns in 3 days (rate 1) with a 6 h short window; every alert has `runbook_url`, owner, severity labels.

`OBS-BP-14` — **See MSG-BP-15 (canonical mechanism).** Connect queue-age/lag signals to the business processing SLO and alert owner.

`OBS-BP-15` — **Instrument business metrics next to technical ones.** A 200 OK service that stopped creating orders is down. How: counters like `orders_created_total`, `payments_failed_total{reason}` with bounded labels; alert on drop vs same hour last week (e.g. < 50%) and on zero for N minutes during business hours.

`OBS-BP-16` — **Separate audit logs from debug logs.** Audit records are evidence (who did what to which resource, when, from where, with what result); debug logs are disposable. How: dedicated event type/stream, never sampled or level-filtered, append-only storage with retention per compliance (often 1–7 years) and restricted access (→ SEC); debug/app logs 7–30 days.

`OBS-BP-17` — **Keep one dashboard per service, as code, with a fixed layout.** On-call needs the same shape everywhere. How: row 1 SLOs and burn; row 2 RED per route; row 3 dependencies (latency/errors per downstream); row 4 USE and saturation; row 5 queues and business metrics; deploy annotations; versioned in Git (Grafana JSON/Jsonnet/Terraform), linked from alerts.

`OBS-BP-18` — **Write runbooks per alert and blameless postmortems per incident.** Knowledge in one engineer's head is an outage multiplier. How: runbook = what the alert means, impact, first checks (queries, dashboards), mitigations (rollback, flag off, scale), escalation; postmortem for every SEV1/2 within ~5 working days: timeline, impact in SLO terms, contributing factors, action items with owners and due dates tracked to closure.

`OBS-BP-19` — **See PERF-BP-2 (canonical mechanism).** Choose on-demand or continuous profiling from incident/optimization needs; protect endpoints and measure overhead.

`OBS-BP-20` — **Send unhandled and unexpected errors to an error tracker tagged with release and trace.** Logs show that errors happen; a tracker groups them, flags new ones per release and gives full stack traces. How: Sentry/vendor APM/OTel exception events; `release` = git SHA, `environment`, `trace_id`; upload source maps (Node/TS) in CI; scrub with `beforeSend`; alert on new issue types in a fresh release, not on every event.

## Bad practices

`OBS-BAD-1` — **Printf-style logging (`log.Printf`, `console.log`) in services.** Unparseable, no levels, no correlation; costly regex extraction. → Instead: structured logger with schema (OBS-BP-1, OBS-BP-3).

`OBS-BAD-2` — **Logging secrets, tokens or whole request/response bodies.** Credentials and PII land in a third-party log store with broad access. → Instead: allowlisted fields and redaction (OBS-BP-4).

`OBS-BAD-3` — **Interpolating variables into the message string.** `"failed for user 123"` makes every line unique, breaking grouping and log-derived counts. → Instead: constant `msg`, variables as fields (OBS-BP-1).

`OBS-BAD-4` — **Log-and-rethrow at every layer.** One failure produces 5 ERROR lines and inflates error rates. → Instead: log once where the error is handled; wrap and return elsewhere (OBS-BP-2).

`OBS-BAD-5` — **DEBUG enabled permanently in production.** Volume and cost explode, real signals drown. → Instead: INFO default with runtime level switch (OBS-BP-2, OBS-BP-5).

`OBS-BAD-6` — **Raw path or IDs as metric labels.** `/users/8812/orders` as a label value creates unbounded series and OOMs the TSDB. → Instead: route templates, bounded enums (OBS-BP-8).

`OBS-BAD-7` — **Average latency or gauges of "last request duration".** Hides tail latency; a gauge only shows whichever request ran last before the scrape. → Instead: histograms (OBS-BP-7).

`OBS-BAD-8` — **Averaging per-pod p99s.** Mathematically meaningless; understates tail latency. → Instead: aggregate buckets, then compute quantile (OBS-BP-7).

`OBS-BAD-9` — **Health-check and metrics-scrape requests logged and counted in SLIs.** Probe traffic every few seconds per pod dominates logs and inflates availability. → Instead: exclude probe routes from access logs and SLI counters (OBS-BP-12).

`OBS-BAD-10` — **Outbound HTTP or message publish without context propagation.** Trace breaks at each hop; manual `http.Client{}` or raw broker clients bypass instrumentation. → Instead: instrumented transports and header injection (OBS-BP-9).

`OBS-BAD-11` — **Alerts without runbook, owner or clear action.** On-call acks and ignores; real incidents get missed. → Instead: actionable alert definition (OBS-BP-13, OBS-BP-18).

`OBS-BAD-12` — **Swallowed errors (`_ = err`, empty `catch {}`) and unhandled promise rejections.** Failures never reach logs, traces or the error tracker. → Instead: handle or return; global handlers report then exit (OBS-BP-3).

`OBS-BAD-13` — **Telemetry exporter blocking or crashing the request path.** Synchronous log shipping or an unbounded exporter queue causes latency or OOM when the backend is down. → Instead: stdout + agent, batch processors with bounded queues and drop-on-full.

`OBS-BAD-14` — **pprof/debug endpoints on the public listener.** Leaks internals and lets anyone trigger expensive profiles. → Instead: separate internal port, network policy (OBS-BP-19, → SEC).

`OBS-BAD-15` — **Error-ratio alerts with no traffic floor.** At 3 a.m. one failure out of 4 requests is a 25% error rate and pages someone for nothing. → Instead: burn-rate alerts with a minimum request count (`and sum(rate(..._total[5m])) > N`) or synthetic traffic for low-volume paths (OBS-BP-13).

`OBS-BAD-16` — **A span per loop iteration, row or cache call.** A single request produces thousands of spans: exporter queues overflow, traces get truncated, cost multiplies. → Instead: one span per batch/operation with count attributes, span events for notable items (OBS-BP-10).

## Anti-patterns

`OBS-AP-1` — **Logs as the only signal.** Symptoms: no `/metrics`, no tracing; dashboards built from log queries; "grep in Kibana" is the incident procedure. Why it hurts: expensive at volume, slow queries during incidents, no SLOs, no burn-rate alerts. Way out: add RED metrics and OTel tracing at the framework middleware first, then derive SLOs; cut per-request INFO logs once metrics cover them.

`OBS-AP-2` — **Cause-based paging (alert on everything).** Symptoms: pages for CPU > 80%, single pod restart, any ERROR line, disk at 70%; > 2 pages per shift; alerts routinely auto-resolve. Why it hurts: alert fatigue, missed real incidents, burnout. Way out: classify every alert: user-visible symptom → page via burn rate; cause → ticket or dashboard; delete alerts nobody acted on in 30 days.

`OBS-AP-3` — **Dashboard sprawl without SLOs.** Symptoms: dozens of hand-made dashboards per service, none says "healthy or not"; incident starts with "which dashboard?". Why it hurts: slow diagnosis, divergent truths. Way out: one standard dashboard per service generated from code (OBS-BP-17), SLO panel at the top, archive the rest.

`OBS-AP-4` — **Metrics as an analytics store.** Symptoms: labels with `user_id`, `tenant_id` (unbounded), `email`, `sku`; TSDB memory climbing; scrape timeouts. Why it hurts: cardinality explosion takes down monitoring exactly when needed; cost scales with users. Way out: move per-entity questions to logs/traces/event analytics (columnar store), keep metrics aggregated; bounded tiers instead of IDs.

`OBS-AP-5` — **Trace islands.** Symptoms: traces end at the API or at the producer; consumers start new root traces; trace view shows only one service. Why it hurts: async latency and failure causality invisible; tail sampling cannot see whole traces. Way out: propagation in message headers and job metadata, span links for batches, Collector-level checks on orphan root spans.

`OBS-AP-6` — **Synthetic-ping availability.** Symptoms: "uptime" = an external check hitting `/health` every minute; SLO reports 100% while users get 5xx on checkout. Why it hurts: measures the probe path, not user journeys. Way out: request-based SLIs from real traffic (OBS-BP-12); keep synthetics only as a supplement for low-traffic paths.

`OBS-AP-7` — **Vendor SDK scattered through domain code.** Symptoms: vendor tracer/statsd calls in business logic across hundreds of files; switching vendors is a quarter-long project. Why it hurts: lock-in, inconsistent naming, no shared context. Way out: OTel API behind middleware and thin helpers; vendor only as Collector exporter.

`OBS-AP-8` — **Postmortem theatre.** Symptoms: postmortems name a person or "human error", action items lack owners or stay open for months, the same incident recurs. Why it hurts: no learning, hidden risks, people stop reporting. Way out: blameless template, contributing-factor analysis, tracked actions reviewed in ops meeting, recurrence tagging.

`OBS-AP-9` — **Unmonitored monitoring.** Symptoms: no alert fires when Prometheus, the Collector or Alertmanager is down or a scrape target disappears; `up == 0` not alerted; no dead man's switch; exporter queues drop data silently. Why it hurts: silence is read as health, and the outage you find is discovered by customers. Way out: always-firing watchdog alert routed to an external dead-man service, alerts on `up == 0` / `absent()` for critical jobs, Collector self-metrics (`otelcol_exporter_send_failed_*`, queue size) alerted, monitoring stack in a separate failure domain from what it watches.

## Go / Node.js notes

- **Loggers:** Go has `log/slog` in the stdlib (JSON handler; `ReplaceAttr` for redaction; `otelslog` bridge adds trace IDs when you pass `ctx` via `InfoContext`); zap/zerolog for zero-alloc hot paths. Node: `pino` is the default choice (JSON, `redact`, child loggers, transports in a worker thread); `winston` is slower and easier to misconfigure; `console.log` is synchronous for files and (on Linux) pipes, so heavy logging blocks the event loop, while async destinations buffer in memory if the sink stalls — bound them.
- **Context:** Go propagates trace context only through explicit `context.Context` — any `context.Background()` in a handler breaks the trace (grep for it). Node relies on `AsyncLocalStorage`; callback-style libraries or custom thenables can lose context, and OTel must be loaded before instrumented modules (`node --import ./instrumentation.mjs` for ESM, `--require` for CJS).
- **Metrics:** Go `prometheus/client_golang` (`promauto`, default Go runtime and process collectors; `runtime/metrics` gives scheduler latency); OTel Go metrics SDK with Prometheus exporter also works. Node `prom-client` with `collectDefaultMetrics()` (event-loop lag, heap, GC); in `cluster` mode each worker has its own registry — use `AggregatorRegistry` or per-worker scraping.
- **Saturation signals differ:** Go saturates on goroutine count, mutex contention and GC/CPU throttling (`go_goroutines`, mutex profile, `GOMAXPROCS` vs CPU limit); Node saturates on event-loop delay and utilisation (`performance.eventLoopUtilization()`, p99 delay > ~100 ms is a red flag) and libuv threadpool (default 4, `UV_THREADPOOL_SIZE`).
- **Profiling:** Go has first-class pprof (CPU, heap, goroutine, mutex, block); importing `net/http/pprof` registers on `http.DefaultServeMux` silently — serve it on a separate internal server. Node: `--cpu-prof`, `--heapsnapshot-signal=SIGUSR2`, `@pyroscope/nodejs` or `@datadog/pprof`; heap snapshots pause the process, never take them on a serving pod without draining it.
- **Fatal paths:** Go `log.Fatal`/`os.Exit` skip deferred flushes — the last spans and logs are lost; flush the tracer provider on shutdown. Node: register `unhandledRejection` and `uncaughtException` to report and then exit (do not continue in an unknown state); call `sdk.shutdown()` on SIGTERM so batch exporters flush.
- **Instrumentation coverage:** Node auto-instrumentation patches `http`, `undici`/`fetch`, `pg`, `ioredis`, `kafkajs`, Express/Fastify at load time — broad coverage for free, but version mismatches fail silently (check the instrumentation package supports the library major). Go has no monkey-patching: every server, client, DB driver and broker client must be wrapped explicitly (`otelhttp`, `otelgrpc`, `otelpgx`, `otelsarama`/franz-go `kotel`), or use eBPF auto-instrumentation (OBI/Beyla) for coarse spans — so audit Go for unwrapped clients one by one.
- **Container CPU:** Go before 1.25 sets `GOMAXPROCS` to host cores, not the cgroup limit — causing CFS throttling that looks like random p99 spikes; check Go version or `automaxprocs`, and alert on `container_cpu_cfs_throttled_periods_total` ratio. Node is single-threaded per process, so throttling shows directly as event-loop delay.
- **Logs via OTel:** both stacks can export logs over OTLP (Go `otelslog` bridge, Node `@opentelemetry/winston-transport`/pino instrumentation), but stdout JSON + node/Collector agent remains the most robust path — the app never blocks on a log backend and logs survive SDK misconfiguration.
- **Serverless/short jobs:** Node on Lambda and Go CLIs/cron jobs exit before periodic exporters flush; call `ForceFlush`/`forceFlush()` before returning, and push metrics (OTLP) rather than relying on scrape.
