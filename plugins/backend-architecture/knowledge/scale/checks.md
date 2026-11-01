# Scalability — audit checklist

> **Scope:** growing capacity with load and data: capacity estimation, vertical vs horizontal, stateless scale-out, autoscaling, read vs write scaling, partitioning and resharding, hot keys, connection ceilings, fan-out, CQRS read models, multi-region, cells, cost curves, finding the knee. **Hands off to:** per-request speed, profiling and load-test tooling → PERF · cache design, invalidation, stampedes → CACHE · schema, indexes, transactions, replica consistency semantics → DATA · broker partitions and consumer groups → MSG · timeouts, load shedding, backpressure → RES · cross-shard/cross-region write consistency, projections → IDEM · service boundaries → ARCH · deploy topology, IaC → OPS · capacity dashboards and SLOs → OBS.

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| `SCALE-CHK-1` | Is there a written capacity estimate (peak RPS, data growth, headroom) and a per-instance capacity figure? | Design docs, ADRs, README, runbooks. Fail: no numbers, peak unknown, or replica counts not traceable to a measurement. SCALE-BP-1, BP-2, AP-7 | Medium |
| `SCALE-CHK-2` | Is the request tier stateless (sessions, files, in-memory state)? | Go: package-level `map[`/`sync.Map` holding sessions or user state, `sessions.NewFilesystemStore`, `os.WriteFile`/`os.Create` for user content. Node: `express-session` without `store:` (MemoryStore), module-level `new Map()` used as state, `multer({ dest` / `diskStorage`. k8s: `sessionAffinity: ClientIP`, ingress cookie affinity, `emptyDir`/`hostPath` for uploads. Confirm the state matters for correctness. SCALE-BP-3, BAD-1, BAD-2, AP-3 | High |
| `SCALE-CHK-3` | Are rate limits, counters, locks and dedupe shared across replicas when they must be global? | Go: `golang.org/x/time/rate` limiter used as the API limit, in-memory dedupe maps. Node: `express-rate-limit` / `rate-limiter-flexible` with memory store. Fail if replicas > 1 and the limit/dedupe is meant to be global. SCALE-BAD-3 | Medium |
| `SCALE-CHK-4` | Are scheduled effects safe under duplicate/missed triggers and changing replica count? | Go: `robfig/cron`, `time.NewTicker` started in `main`. Node: `node-cron`, `setInterval` in server bootstrap. Check Deployment replicas and whether a lock/leader election exists. Fail if side-effecting jobs (billing, emails) run per replica. SCALE-BAD-4 | High |
| `SCALE-CHK-5` | Does autoscaling use a signal matching the bottleneck, with sane bounds? | HPA/KEDA `ScaledObject`/Knative manifests: Check measured saturation signal, consumer lag, startup delay, topology and scale-down behavior against requirements; replica counts are not universal thresholds. SCALE-BP-4, BP-5, BAD-5, BAD-7 | Medium |
| `SCALE-CHK-6` | Does maxReplicas × processes × pool size fit under the DB connection limit with reserve? | Go: `SetMaxOpenConns` (unset = unlimited in `database/sql`), pgxpool `MaxConns` (default max(4, NumCPU)). Node: `new Pool({ max` (default 10), Prisma `connection_limit` (default 2×CPUs+1), Knex `pool.max`, PM2/cluster instance count. Compare with `max_connections` / proxy limits. Fail if the sum exceeds the limit or pools are unbounded. SCALE-BP-13, BAD-6 | High |
| `SCALE-CHK-7` | If a transaction-mode pooler is used, is the app free of session-level features? | Grep `SET ` (not `SET LOCAL`), `pg_advisory_lock(` (non-xact), `LISTEN`, temp tables; pgx statement cache vs PgBouncer < 1.21 or `max_prepared_statements = 0`; Prisma URL `pgbouncer=true`. Fail if session state is relied on across transactions. SCALE-BP-13 | High |
| `SCALE-CHK-8` | Are replica reads lag-tolerant, with read-after-write routed to the primary? | Replica DSNs, GORM `dbresolver`, Prisma `readReplicas`, Sequelize `replication`, Knex read/write split. Trace create-then-read flows. Check replica-lag alerting. SCALE-BP-6, BAD-10 | Medium |
| `SCALE-CHK-9` | Is the partition/shard key high-cardinality, evenly loaded and present in hot queries? | Partitioning DDL, Citus `create_distributed_table`, DynamoDB/Cassandra key schema, Kafka message keys, Redis key patterns. Fail: low-cardinality key (status, country), monotonic key on a distributed store, hot queries lacking the key. SCALE-BP-8, BAD-9, BAD-11 | High |
| `SCALE-CHK-10` | Is key → node placement stable when nodes are added or removed? | Grep `% len(nodes)`, `% shards.length`, `crc32.ChecksumIEEE(...) %`, `hash % n`. A hit is a lead: fail only if the divisor is the physical node count. SCALE-BP-9, BAD-8 | Medium |
| `SCALE-CHK-11` | Are hot keys and large tenants measured and mitigated? | Per-tenant/per-key metrics, top-N dashboards, throttling metrics, `redis-cli --hotkeys`/`--bigkeys` output, tenant placement directory. Fail: no per-tenant visibility on a multi-tenant system or known whales on shared shards with no quota. SCALE-BP-11, BP-20, AP-4 | Medium |
| `SCALE-CHK-12` | Are non-essential side effects offloaded from the request path? | Go: `smtp.SendMail`, webhook `http.Post`, image/PDF generation inside handlers. Node: `await transporter.sendMail`, `sharp(`, `puppeteer` in route handlers. Confirm the response does not need the result. SCALE-BP-12 | Medium |
| `SCALE-CHK-13` | Is per-request fan-out bounded? | Go: `for _, f := range followers` with DB/RPC inside, goroutine per item without limit (no `errgroup.SetLimit`). Node: `Promise.all(list.map(` over user-sized lists without `p-limit`. Fail if size is driven by user data with no cap or async path. SCALE-BP-14, BAD-12 | High |
| `SCALE-CHK-14` | Are heavy reads (reports, search, exports) kept off the OLTP primary? | Report/search endpoints, `LIKE '%`, large `GROUP BY` on primary DSN, BI tools pointed at the primary, `pg_stat_statements` top by total time. SCALE-BP-15, AP-5 | Medium |
| `SCALE-CHK-15` | Are RPO/RTO, failover and data residency defined and tested? | DR docs, Terraform regions, cross-region replicas, bucket replication, backup locations, last failover drill date; residency requirements vs where logs/backups/search replicas live. Fail: no tested failover, or residency-bound data replicated out of region. SCALE-BP-16, AP-6 | High |
| `SCALE-CHK-16` | Are per-tenant / per-client limits in place (page size, batch, quotas)? | Handler limit clamps, gateway quota config, API docs. Fail: client-controlled `limit` without max, unbounded batch endpoints, no tenant quotas on shared infra. SCALE-BP-20 | Medium |
| `SCALE-CHK-17` | Has the knee been measured with production-like data, and is the operating point below it? | k6/Gatling/Locust/vegeta scripts and results, dataset size used, saturating resource identified. Fail: no load test for critical paths or tests against empty data. SCALE-BP-19, BAD-14 | Medium |
| `SCALE-CHK-18` | Is cost per unit known and are superlinear costs controlled? | Cost dashboards, tagging per service/tenant, cross-AZ and NAT traffic, log volume, idle replicas. Fail: no unit cost or a cost line growing faster than traffic without explanation. SCALE-BP-18 | Low |
| `SCALE-CHK-19` | Are IDs generated without a central serialization point? | Shared `nextval` across shards/regions, Redis `INCR` global counters for IDs, ticket tables. SCALE-BAD-13 | Low |

## Also scan for (rules not cited above)

Bodies: `knowledge/scale/rules.md`, looked up by ID.

- SCALE-BAD-1 — Sticky sessions used to keep session state in memory
- SCALE-BAD-2 — User uploads or generated files written to the container filesystem or an `emptyDir`
- SCALE-BAD-5 — HPA on CPU for an I/O-bound service
- SCALE-BAD-6 — `maxReplicas` raised without connection math
- SCALE-BAD-7 — `minReplicas: 1` or scale-to-zero on a latency-sensitive API
- SCALE-BAD-8 — `hash(key) % nodeCount` for placement
- SCALE-BAD-9 — Monotonic key (auto-increment, timestamp, UUIDv1) as partition key on a distributed range-partitioned store
- SCALE-BAD-10 — See IDEM-BP-14 (canonical mechanism)
- SCALE-BAD-11 — Scatter-gather across all shards on a hot path
- SCALE-BAD-12 — Unbounded fan-out inside a request
- SCALE-BAD-14 — Load testing against an empty database or from one laptop
- SCALE-AP-1 — Scaling the stateless tier to fix a stateful bottleneck
- SCALE-AP-2 — Premature sharding
- SCALE-AP-3 — "Stateless" service that is not
- SCALE-AP-4 — Hot partitions and noisy neighbours by design
- SCALE-AP-5 — The OLTP primary as the reporting and search engine
- SCALE-AP-6 — Active-active by default
- SCALE-AP-7 — Autoscaler as the capacity plan
- SCALE-AP-8 — Big-bang resharding
