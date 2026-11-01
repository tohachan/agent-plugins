# Scalability — rules

> **Scope:** growing capacity with load and data: capacity estimation, vertical vs horizontal, stateless scale-out, autoscaling, read vs write scaling, partitioning and resharding, hot keys, connection ceilings, fan-out, CQRS read models, multi-region, cells, cost curves, finding the knee. **Hands off to:** per-request speed, profiling and load-test tooling → PERF · cache design, invalidation, stampedes → CACHE · schema, indexes, transactions, replica consistency semantics → DATA · broker partitions and consumer groups → MSG · timeouts, load shedding, backpressure → RES · cross-shard/cross-region write consistency, projections → IDEM · service boundaries → ARCH · deploy topology, IaC → OPS · capacity dashboards and SLOs → OBS.

## Best practices

`SCALE-BP-1` — **Estimate before designing, and write the arithmetic down.** Prevents designs that are 100× over or under. How: avg RPS = DAU × actions/user/day ÷ 86,400 (≈10⁵; 1M req/day ≈ 12 RPS); peak = avg × 3–10 (diurnal ×2–3, launches/campaigns ×10); storage = rows/day × bytes/row × replicas × retention; egress = RPS × response size. Size for 2–3× projected peak; plan the redesign point at ~10×.

`SCALE-BP-2` — **Derive instance counts from measured per-instance capacity.** Guessed capacity hides the real bottleneck. How: instances = peak RPS ÷ (knee RPS per instance × 0.6–0.7 target utilisation), then add N+1 per AZ so losing a zone does not overload the rest; re-measure after major releases (SCALE-BP-19).

`SCALE-BP-3` — **Keep the request tier stateless.** Any instance must serve any request and be killable at any time. How: sessions in Redis/DB or signed short-lived tokens (SEC); uploads and generated files in object storage via presigned URLs; rate limits, locks, dedupe sets and job schedules in a shared store or a single scheduler; in-process caches only as disposable accelerators (CACHE).

`SCALE-BP-4` — **Autoscale on the signal that saturates first.** CPU stays at 20% while an I/O-bound service drowns. How: CPU target 50–70% for CPU-bound; in-flight requests or RPS per pod for I/O-bound (Knative concurrency target, KEDA Prometheus scaler); consumer lag or oldest-message age for workers (KEDA Kafka/SQS/RabbitMQ scalers); `minReplicas` ≥ 2–3 spread across zones; scale up fast (stabilization 0–60 s), scale down slowly (5–10 min, the HPA default is 300 s).

`SCALE-BP-5` — **Know what autoscaling cannot do.** Reaction time = scrape interval (15–60 s) + decision + node provisioning (1–5 min with Cluster Autoscaler/Karpenter) + image pull + startup + warm-up, so it follows ramps of minutes, not spikes of seconds. How: keep headroom, pre-scale for known events, shed load at the edge (RES), cap `maxReplicas` by the downstream budget (SCALE-BP-13); adding pods never fixes a saturated database.

`SCALE-BP-6` — **Scale reads with the cheapest lever first.** Replicas and caches add staleness you must handle. How: query/index fix (DATA, PERF) → cache hot keys (CACHE) → read replicas for lag-tolerant reads → read models (SCALE-BP-15). Route read-after-write to the primary (sticky for N seconds after a write, or wait for an LSN/GTID token); alert on replica lag and stop routing to a replica beyond a threshold.

`SCALE-BP-7` — **Reduce writes before partitioning them.** A tuned single Postgres/MySQL primary on NVMe sustains tens of thousands of simple writes/s; most "need to shard" cases are write amplification. How: batch and coalesce writes, move counters/likes to aggregated or Redis increments flushed periodically, append-only instead of update-in-place for hot rows, async for non-critical writes, then split functionally (DB per bounded context, ARCH), and only then shard.

`SCALE-BP-8` — **Pick the shard key from access patterns.** A wrong key makes every query scatter-gather and every transaction distributed. How: high cardinality, even load (not just even count), present in nearly every hot query, and keeps a business transaction on one shard; colocate related rows (Citus distributed tables on the same key, Redis hash tags `{tenant:42}`); never a monotonically increasing key (auto-increment, timestamp) on a range-partitioned distributed store.

`SCALE-BP-9` — **Decouple logical partitions from physical nodes.** Resharding should move whole partitions, not rehash every row. How: fixed, generous logical shard count (e.g. 1,024–16,384; Redis Cluster uses 16,384 slots) mapped to nodes via a directory or consistent hashing with virtual nodes / rendezvous hashing; adding a node moves ~1/N of keys instead of ~all.

`SCALE-BP-10` — **Run rebalancing and resharding as an online, throttled, reversible migration.** Big-bang moves cause outages and data loss. How: copy (snapshot + CDC or double-write) → backfill → verify (row counts, checksums) → switch reads → switch writes → keep the old copy until verified → clean up; throttle copy I/O; use platform tooling where it exists (Vitess Reshard/MoveTables, Citus shard rebalancer, DynamoDB adaptive capacity); rehearse on a production-sized clone.

`SCALE-BP-11` — **Treat hot keys and whales as a design input.** One celebrity, tenant or SKU can saturate a shard while the cluster average looks idle. How: measure per-key/per-tenant load (top-k sampling, `redis-cli --hotkeys`, DynamoDB contributor insights); split hot write keys into N sub-keys (`key#0..key#15`) and aggregate on read; cache hot reads with request coalescing (CACHE); place whales on dedicated shards via the directory; apply per-key/per-tenant quotas (SCALE-BP-20).

`SCALE-BP-12` — **Move work that the response does not need off the request path.** Synchronous side work sets your peak capacity to the slowest dependency. How: enqueue (MSG) emails, webhooks, thumbnails, exports, search indexing; return 202 with a status resource; consumers scale on lag (SCALE-BP-4); set an SLO on queue age so "async" does not become "never".

`SCALE-BP-13` — **See DATA-BP-10 (canonical mechanism).** Include maximum replicas, processes, rollout surge, batch jobs and failover reserve in the total.

`SCALE-BP-14` — **Choose fan-out per audience size.** Pure push explodes on celebrities; pure pull makes every read expensive. How: fan-out on write to precomputed inboxes for normal accounts (bounded by a follower threshold, e.g. 10k–100k), fan-out on read for accounts above it, merge at read time; process push fan-out asynchronously in batches.

`SCALE-BP-15` — **Serve divergent read shapes from rebuildable read models (CQRS).** Analytical, search and feed queries on the OLTP primary compete with writes. How: project changes via outbox or CDC (Debezium) into a denormalised store (Elasticsearch/OpenSearch, ClickHouse, Redis, a materialised table); expose and alert on projection lag; keep a full rebuild path from the source of truth; ordering and dedupe of projections → IDEM, MSG.

`SCALE-BP-16` — **Go multi-region only with stated RPO/RTO and a data-ownership model.** "Active-active" without one silently loses writes. How: start multi-AZ; active-passive with async replication (RPO = replication lag, typically seconds), tested promotion runbook, low DNS TTL or global LB; active-active with a home region per tenant/user (geo-partitioning) so each row has one writer; multi-writer only for commutative/CRDT data (IDEM). Data residency: pin by partition key, and check that backups, logs, analytics and search replicas obey the same pinning (SEC).

`SCALE-BP-17` — **Use cells to cap blast radius at large scale.** One bad deploy, poison tenant or overload should hit 1/N of customers. How: N identical, independent stacks (compute + data) each serving a subset of tenants behind a thin, highly available router; fixed maximum cell size validated by load test; grow by adding cells, not enlarging them; deploy cell by cell (OPS); migrate tenants between cells with the SCALE-BP-10 procedure.

`SCALE-BP-18` — **Model cost per unit and watch the superlinear terms.** Cost often scales faster than traffic. How: track cost per 1k requests, per tenant, per GB stored; watch cross-AZ traffic (~$0.01/GB each way on AWS), NAT gateway processing, internet egress, per-request managed services, log/metric cardinality, idle replicas; prefer zone-local routing where safe, ARM instances (~20% lower price per vCPU), spot for stateless and batch, rightsizing from utilisation data.

`SCALE-BP-19` — **See PERF-BP-18 (canonical mechanism).** Measure saturation on representative data and the operating headroom below it.

`SCALE-BP-20` — **Bound everything that grows with users or data.** Unbounded per-tenant work turns one customer's growth into everyone's outage. How: per-tenant/API-key quotas and rate limits (RES), max page size, max batch size, max fan-out per request, max items per tenant where the product allows, storage quotas; alert on tenants approaching limits.

## Bad practices

`SCALE-BAD-1` — **Sticky sessions used to keep session state in memory.** Losing a pod logs users out, load is uneven, scale-in is blocked. → Instead: external session store or tokens (SCALE-BP-3).

`SCALE-BAD-2` — **User uploads or generated files written to the container filesystem or an `emptyDir`.** Files vanish on reschedule and are invisible to other replicas. → Instead: object storage with presigned URLs (SCALE-BP-3).

`SCALE-BAD-3` — **Per-process rate limiters, counters or dedupe sets treated as global.** With N replicas the limit is N× higher and dedupe misses. → Instead: shared store (Redis) or gateway limits (SCALE-BP-3, SCALE-BP-20).

`SCALE-BAD-4` — **See MSG-BP-16 (canonical mechanism).** Inspect all replicas and scheduler claims; durable idempotency is still needed.

`SCALE-BAD-5` — **HPA on CPU for an I/O-bound service.** CPU stays low while latency and in-flight requests explode, so it never scales. → Instead: concurrency/RPS or lag signals (SCALE-BP-4).

`SCALE-BAD-6` — **`maxReplicas` raised without connection math.** Scale-out exhausts `max_connections` ("sorry, too many clients already") and the autoscaler turns a spike into an outage. → Instead: SCALE-BP-13.

`SCALE-BAD-7` — **`minReplicas: 1` or scale-to-zero on a latency-sensitive API.** Cold starts on first request, no zone redundancy, every deploy is a gap. → Instead: ≥2–3 replicas across zones (SCALE-BP-4).

`SCALE-BAD-8` — **`hash(key) % nodeCount` for placement.** Adding or removing one node remaps almost every key: mass cache misses or a full data reshuffle. → Instead: SCALE-BP-9.

`SCALE-BAD-9` — **Monotonic key (auto-increment, timestamp, UUIDv1) as partition key on a distributed range-partitioned store.** All inserts land on the last partition. → Instead: hashed or high-cardinality key (SCALE-BP-8).

`SCALE-BAD-10` — **See IDEM-BP-14 (canonical mechanism).** Inspect create-then-read routing and replica progress; do not promise consistency from a fixed timer.

`SCALE-BAD-11` — **Scatter-gather across all shards on a hot path.** Latency equals the slowest shard and load multiplies by shard count. → Instead: better shard key (SCALE-BP-8) or a read model (SCALE-BP-15).

`SCALE-BAD-12` — **Unbounded fan-out inside a request** (loop over all followers/members sending writes or calls). One large account produces a multi-minute request and a write storm. → Instead: async batched fan-out (SCALE-BP-12, SCALE-BP-14).

`SCALE-BAD-13` — **Global sequence or counter row as the ID/number source in a sharded or multi-region system.** It becomes a serialization point and a cross-region round trip. → Instead: locally generated IDs (UUIDv7, ULID, Snowflake-style) hashed for placement.

`SCALE-BAD-14` — **Load testing against an empty database or from one laptop.** Indexes fit in memory, the generator saturates first, the knee is fiction. → Instead: SCALE-BP-19 with production-sized data and a distributed generator.

## Anti-patterns

`SCALE-AP-1` — **Scaling the stateless tier to fix a stateful bottleneck.**
- Symptoms: incident playbook says "add pods"; DB CPU or connections at 100% while app pods multiply; latency worsens after scale-out.
- Why it hurts: more clients means more contention, more connections and more retries against the real bottleneck.
- Way out: identify the saturated resource (USE), cap app concurrency to downstream capacity (SCALE-BP-13, RES), then reduce or redistribute that resource's load (SCALE-BP-6, SCALE-BP-7).

`SCALE-AP-2` — **Premature sharding.**
- Symptoms: custom shard router for a database of tens of GB; cross-shard joins re-implemented in application code; migrations run per shard by hand.
- Why it hurts: permanent complexity, distributed transactions and operational toil for capacity a single primary would provide.
- Way out: vertical scale, replicas, native table partitioning, functional split; when real limits are measured, move to a managed sharding layer (Vitess, Citus) or distributed SQL rather than a homegrown router.

`SCALE-AP-3` — **"Stateless" service that is not.**
- Symptoms: works with one replica, flaky with two; local caches without invalidation, in-memory job queues, WebSocket rooms tracked per process, files on local disk, per-pod schedulers.
- Why it hurts: correctness depends on routing luck; scale-in and deploys lose work.
- Way out: inventory process-local state, externalise anything correctness depends on, add a pub/sub backplane for connection fan-out, test with ≥2 replicas in CI or staging.

`SCALE-AP-4` — **Hot partitions and noisy neighbours by design.**
- Symptoms: one tenant/key/shard dominates load; p99 bad for everyone sharing it; throttling errors (DynamoDB `ProvisionedThroughputExceeded`, Kafka partition lag on one partition) while the cluster average is low.
- Why it hurts: capacity is bounded by the hottest unit, not the average; one customer degrades all.
- Way out: SCALE-BP-11, per-tenant quotas (SCALE-BP-20), directory-based placement for whales, cells (SCALE-BP-17).

`SCALE-AP-5` — **The OLTP primary as the reporting and search engine.**
- Symptoms: dashboards, exports, `LIKE '%term%'` search and multi-join aggregates on the primary; long-running queries blocking vacuum; "we added a replica for reports" that lags for hours.
- Why it hurts: read shapes fight the write path for CPU, I/O and locks; capacity of the whole system is set by its worst report.
- Way out: CQRS read models via CDC into a search/OLAP store (SCALE-BP-15).

`SCALE-AP-6` — **Active-active by default.**
- Symptoms: "both regions accept writes" with async bidirectional replication; no stated conflict resolution; last-write-wins discovered in an incident; region-local ID sequences colliding.
- Why it hurts: silent lost updates and divergence, very hard to repair after the fact.
- Way out: home region per entity (geo-partitioning) or active-passive; reserve multi-writer for commutative data with explicit merge rules (IDEM).

`SCALE-AP-7` — **Autoscaler as the capacity plan.**
- Symptoms: no estimates, no load tests, very high `maxReplicas`; incidents during spikes because scaling lags; surprise bills.
- Why it hurts: autoscaling reacts too slowly for spikes and scales into downstream ceilings.
- Way out: SCALE-BP-1, SCALE-BP-2, SCALE-BP-5, SCALE-BP-19, plus load shedding (RES).

`SCALE-AP-8` — **Big-bang resharding.**
- Symptoms: plan requires a maintenance window, a full rehash and a one-way cutover; no verification or rollback step.
- Why it hurts: long downtime, high risk of data loss, and the next reshard is just as painful.
- Way out: logical partitions plus online, verified, reversible moves (SCALE-BP-9, SCALE-BP-10).

## Go / Node.js notes

- Process model: one Go process uses all cores it is given (GOMAXPROCS, see PERF-BP-12), so run one process per pod and size by CPU. A Node process uses one core for JS; scale with more pods of ≤1 vCPU rather than `cluster`/PM2 inside a pod, and remember every extra process multiplies the DB pool (SCALE-BP-13).
- `database/sql`: `SetMaxOpenConns` defaults to unlimited and `SetMaxIdleConns` to 2 (connection churn under load); set both, plus `SetConnMaxLifetime` (e.g. 5–30 min) so connections rebalance across PgBouncer/proxy instances and replicas.
- Node pools: `pg.Pool` `max` 10 by default; Prisma `connection_limit` defaults to 2×physical CPUs+1 per client instance; on Lambda/serverless each concurrent execution holds its own pool, so use RDS Proxy, a serverless driver (Neon, PlanetScale) or `max: 1`.
- Distributed state libraries: Go `scs` with Redis/pgx stores, `go-redis/redis_rate`; Node `connect-redis` for `express-session`, `rate-limiter-flexible` with a Redis store. `express-session` MemoryStore leaks and is per-process.
- Placement libraries: go-redis `Ring` uses rendezvous hashing; `buraksezer/consistent` for bounded-load consistent hashing in Go; `hashring` in Node. Redis Cluster clients route by 16,384 slots; use hash tags to colocate multi-key operations.
- Long-lived connections (WebSocket/SSE): Go holds 100k+ idle connections per instance cheaply (goroutine stacks start at a few KB); Node handles many with `ws`/uWebSockets.js but per-connection JS objects cost more. Both need a pub/sub backplane (Redis, NATS) for cross-instance broadcast, and L4 balancing of long-lived connections drifts uneven after scale-out, so cap connection age or rebalance.
- Scale-in safety: on SIGTERM, Go `http.Server.Shutdown(ctx)`, Node `server.close()` plus closing keep-alive/WebSocket connections; add a `preStop` delay so endpoints are removed before shutdown (details → OPS, RES).
