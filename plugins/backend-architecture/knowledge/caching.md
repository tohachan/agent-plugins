# Caching

> **Scope:** application caches (in-process, Redis/Valkey/Memcached, two-tier), caching patterns, TTLs and invalidation, stampede and hot-key protection, key design and serialisation, cache–DB consistency, eviction and memory, HTTP caching and CDN, behaviour when the cache fails. **Hands off to:** DB indexes and query tuning before caching → DATA; timeouts/circuit breakers on the cache client → RES; idempotency records and dedup stores (not caches) → IDEM; distributed locks for correctness → CONC; cache cluster sizing and sharding → SCALE; latency budgets and profiling → PERF; caching of personalised/auth data and cache poisoning → SEC; hit-ratio dashboards → OBS; API cache-related contract (ETag on writes) → API.

## Contents
- Key decisions
- Best practices (CACHE-BP-1…18)
- Bad practices (CACHE-BAD-1…14)
- Anti-patterns (CACHE-AP-1…6)
- Audit checklist (CACHE-CHK-1…18)
- Go / Node.js notes

## Key decisions

| Decision | Options | Choose … when | Trade-off |
| --- | --- | --- | --- |
| Cache at all? | no cache (fix query/index) / cache | Cache only when the source is measured as the bottleneck or too costly, data tolerates staleness for a stated window, and the hit ratio will be meaningful (> ~80% for the keyed set) | Every cache adds staleness, invalidation code, a failure mode and memory cost |
| Pattern | cache-aside / read-through / write-through / write-behind / refresh-ahead | Cache-aside by default; read-through when a library owns loading (consistent coalescing); write-through when reads must see writes immediately and writes are modest; write-behind only for loss-tolerant aggregates (counters, analytics); refresh-ahead for a small set of hot, expensive keys | Write-through doubles write latency; write-behind risks losing writes on cache failure |
| Placement | in-process / distributed (Redis, Valkey, Memcached) / two-tier (L1 local + L2 shared) / CDN/edge | In-process for small, hot, rarely changing data and sub-ms needs; distributed when many instances must share and memory per instance is limited; two-tier for hot keys at high RPS; CDN for public, cacheable HTTP responses and assets | L1 diverges across instances and needs invalidation broadcast or short TTL; distributed adds a network hop (~0.2–1 ms) |
| Freshness | TTL only / TTL + explicit delete / event-driven (CDC) invalidation / versioned keys | TTL only when staleness ≤ TTL is acceptable; delete-after-write when a single service owns writes; CDC when many writers or other services change the data; versioned keys for bulk/namespace invalidation | Explicit invalidation must cover every write path; CDC adds pipeline lag and ops |
| Stampede protection | singleflight / distributed lock / probabilistic early refresh / stale-while-revalidate | singleflight always (per instance); add distributed lock or SWR when instances × concurrent misses can overload the source; early refresh for expensive hot keys | Locks add latency for waiters; serving stale needs an explicit staleness bound |
| Eviction | `allkeys-lru` / `allkeys-lfu` / `volatile-*` / `noeviction` | `allkeys-lfu` or `-lru` for pure cache; `noeviction` only for a Redis that is not a cache (queues, locks) — in a separate instance | Mixing durable data and cache in one Redis makes eviction delete durable data |
| What to cache | entity by id / query or list result / computed aggregate / rendered response | Entity by id by default (simple invalidation by key); list/query results only with short TTL or versioned namespace; aggregates when computation dominates; rendered responses at the HTTP/CDN layer for public content | List and query caches are invalidated by any member's change, so they are the main source of staleness bugs |
| L1 coherence (two-tier) | short L1 TTL only / pub-sub invalidation broadcast / Redis client-side caching (tracking) | Short TTL (1–5 s) when brief divergence is acceptable; broadcast or tracking when L1 holds longer-lived data that must change promptly | Broadcast can drop messages (keep a TTL backstop); tracking needs RESP3-capable clients |
| Serialisation | JSON / MessagePack / protobuf / compressed | JSON for small values and debuggability; protobuf/MessagePack plus compression (lz4/zstd) for large or very hot values | Binary formats need schema/version handling; compression costs CPU |

## Best practices

`CACHE-BP-1` — **Define per data type: the source of truth, allowed staleness and invalidation path.** Why: caching without a staleness budget produces correctness bugs nobody can classify. How: a short table in the design (e.g. product details ≤ 60 s stale, price ≤ 0 s → not cached or versioned, user permissions ≤ 5 s); the cache is always reconstructible from the source.

`CACHE-BP-2` — **Use cache-aside with fill-on-miss and invalidate (delete), not update, on write.** Why: writing the new value into the cache races with concurrent fills and leaves stale data; delete is idempotent. How: read → miss → load from DB → `SET key val EX ttl`; write path → commit DB transaction → `DEL key`. For racy fills use `SET … NX` or a version/`GET`-compare so an older load does not overwrite after a delete; add a short TTL as the backstop.

`CACHE-BP-3` — **Every entry has a TTL, with jitter.** Why: TTL-less keys live forever after a missed invalidation; identical TTLs for keys filled together expire together (synchronized miss storm). How: base TTL from the staleness budget, ±10–20% random jitter; longer TTL + explicit invalidation for stable data; a max TTL policy even for "immutable" data.

`CACHE-BP-4` — **Coalesce concurrent misses for the same key.** Why: a popular key expiring sends N concurrent requests to the DB (cache stampede / dog-piling). How: per-process `singleflight` (Go `golang.org/x/sync/singleflight`, Node a `Map<key, Promise>` of in-flight loads); across instances a short lock (`SET lock:k token NX PX 3000`, waiters poll briefly or serve stale) or a library with built-in coalescing.

`CACHE-BP-5` — **Refresh hot, expensive keys before they expire.** Why: even with coalescing, the first miss pays full latency and the source sees bursts. How: probabilistic early expiration (XFetch: refresh when `now - delta * beta * ln(rand()) >= expiry`), or stale-while-revalidate (store soft TTL + hard TTL; serve stale beyond soft TTL while one background refresh runs).

`CACHE-BP-6` — **Cache negative results briefly.** Why: lookups for non-existent IDs (bots, typos, enumeration) bypass the cache and hit the DB every time. How: store a sentinel ("not found") with a short TTL (30–60 s) and invalidate it on create; for high-volume enumeration, a Bloom filter of existing IDs in front.

`CACHE-BP-7` — **Design keys as namespaced, versioned and fully qualified.** Why: collisions across services/tenants leak data; schema changes deserialise old values incorrectly. How: `svc:entity:v3:{tenant}:{id}`; include every input that changes the value (tenant, locale, currency, permissions scope, feature flag variant); bump the version segment on value-schema change; keep keys short and bounded (hash long query strings).

`CACHE-BP-8` — **Treat the cache as optional: on cache errors fall back to the source with protection, never fail the request by default.** Why: a Redis outage should cost latency, not availability — but a 0% hit ratio can also melt the DB. How: tight client timeouts on cache ops (e.g. 50–100 ms, RES); circuit breaker around the cache; on failure read through to the source behind a concurrency limit/load shedding and serve stale L1 where possible; decide per endpoint whether to degrade or shed.

`CACHE-BP-9` — **Keep the DB and cache consistent with post-commit invalidation, and prefer CDC when writers are many.** Why: deleting before commit lets a concurrent reader refill with old data; services that write the table directly skip your invalidation. How: delete after commit (optionally delete again after ~500 ms–1 s — "delayed double delete" — for replica-lag fills); for multi-writer data, invalidate from the change stream (Debezium/logical replication, DynamoDB Streams) or via the outbox (IDEM), with retries.

`CACHE-BP-10` — **See IDEM-BP-14 (canonical mechanism).** Cache fills must satisfy the data freshness contract; filling from a lagging replica can extend stale state.

`CACHE-BP-11` — **Identify hot keys and spread them.** Why: one key on one Redis shard caps throughput at that node (~100k+ ops/s single-threaded commands) and saturates its network. How: monitor (`redis-cli --hotkeys` with LFU policy, client-side counters); L1 in-process copy with 1–5 s TTL; key replication (`k#0..k#N` random read, write all); split big values; Redis 6+ client-side caching (tracking) for invalidation-backed L1.

`CACHE-BP-12` — **Bound value size and serialisation cost.** Why: big values (> ~100 KB) block single-threaded Redis, saturate network, and cost CPU to (de)serialise on every hit — sometimes more than the DB query saved. How: cache the projection the caller needs, not whole aggregates; cap value size (alert > 512 KB); compress above ~1–4 KB; use hashes for partial reads; measure serialisation time in profiles (PERF).

`CACHE-BP-13` — **Size memory and pick the eviction policy explicitly.** Why: default `noeviction` makes writes fail at `maxmemory`; no `maxmemory` lets the OS OOM-kill Redis. How: `maxmemory` at ~70–80% of node RAM (leave fork/COW and fragmentation headroom), `maxmemory-policy allkeys-lfu` (or `-lru`) for caches; separate instances for cache vs durable uses (locks, queues, rate limiters, sessions); in-process caches bounded by entries or bytes (ristretto, otter, lru-cache `max`/`maxSize`).

`CACHE-BP-14` — **Scope caches by authorization.** Why: caching a response keyed only by URL serves one user's data to another. How: include user/tenant/permission scope in the key; never put personalised responses in shared caches/CDN without `Cache-Control: private`; scrub secrets/PII from cached values when possible (SEC).

`CACHE-BP-15` — **Set HTTP caching semantics deliberately on every cacheable response.** Why: absent headers leave behaviour to heuristic caching and proxies. How: static assets with content hash in filename → `Cache-Control: public, max-age=31536000, immutable`; HTML/API reads → `no-cache` + `ETag` (revalidate, 304) or short `max-age` + `stale-while-revalidate`; personal → `private`; secrets/tokens → `no-store`; `Vary` on headers that change the body (`Accept-Encoding`, `Accept-Language`) but not on high-cardinality headers.

`CACHE-BP-16` — **Use the CDN with explicit cache keys, `s-maxage`, and a purge path.** Why: CDN defaults may include all query params or cookies (no hits) or ignore them (wrong content). How: whitelist cache-key params; `s-maxage`/`CDN-Cache-Control` separate from browser TTL; surrogate keys/tags for targeted purge on publish; `stale-if-error` to ride out origin failures; origin shielding to collapse misses.

`CACHE-BP-17` — **Warm caches before traffic cutover and after flushes.** Why: a cold cache after deploy, region failover or `FLUSHALL` sends full load to the DB. How: pre-load top-N keys from access logs; ramp traffic gradually; avoid global key-version bumps at peak; rate-limit the refill.

`CACHE-BP-18` — **Instrument hit ratio, latency, evictions and memory per keyspace.** Why: a cache with a 20% hit ratio adds latency and cost for little gain; rising evictions precede stampedes. How: hit/miss counters per key prefix, p99 cache op latency, `evicted_keys`, `used_memory`, `connected_clients`, error rate; alert on hit-ratio drops (OBS).

## Bad practices

`CACHE-BAD-1` — **Keys without TTL.** A missed invalidation is permanent; memory grows until eviction or OOM. → Instead: CACHE-BP-3.

`CACHE-BAD-2` — **Same fixed TTL on keys filled at the same time** (bulk warm-up, cron-filled reports). Synchronized mass expiry hits the DB. → Instead: jitter (CACHE-BP-3).

`CACHE-BAD-3` — **Cache update instead of delete on write, or delete before commit.** Races leave the stale value cached until TTL. → Instead: CACHE-BP-2, CACHE-BP-9.

`CACHE-BAD-4` — **No timeout on cache calls and errors propagated to the user.** A slow or down Redis turns every request into an error or a long hang. → Instead: CACHE-BP-8.

`CACHE-BAD-5` — **Unbounded in-process map used as a cache.** Memory grows until the container is OOM-killed; no TTL means stale data forever. → Instead: bounded LRU/LFU with TTL (CACHE-BP-13).

`CACHE-BAD-6` — **Cache key missing a value-shaping input** (tenant, locale, role, currency). Users see other tenants' or the wrong locale's data. → Instead: CACHE-BP-7, CACHE-BP-14.

`CACHE-BAD-7` — **`KEYS *` or full scans for invalidation in production.** `KEYS` blocks Redis for seconds on large keyspaces. → Instead: versioned namespaces (CACHE-BP-7), tracked key sets, or `SCAN` offline only.

`CACHE-BAD-8` — **Caching huge blobs or entire result sets** (whole catalog JSON, unbounded lists). Network saturation, Redis latency spikes, deserialisation CPU. → Instead: CACHE-BP-12.

`CACHE-BAD-9` — **Caching errors or empty responses with the normal TTL.** A transient DB error is served for minutes. → Instead: never cache errors; short TTL for negative results only (CACHE-BP-6).

`CACHE-BAD-10` — **Shared Redis with `noeviction` holding both cache and durable data.** At `maxmemory` writes fail everywhere; switching to an eviction policy deletes locks/sessions. → Instead: separate instances (CACHE-BP-13).

`CACHE-BAD-11` — **Personalised API responses cacheable by intermediaries** (`public` or no `Cache-Control` on authenticated endpoints, CDN caching with `Authorization` ignored). Data leakage between users. → Instead: CACHE-BP-14, CACHE-BP-15.

`CACHE-BAD-12` — **Fingerprinted assets served with short TTL, or unfingerprinted assets with `immutable`.** Wasted bandwidth, or users stuck on old JS after deploy. → Instead: CACHE-BP-15.

`CACHE-BAD-13` — **Cache client per request** (`redis.createClient()` / `redis.NewClient` inside handler). Connection storms, file descriptor exhaustion, TLS handshake cost on every call. → Instead: one shared client per process with a bounded pool.

`CACHE-BAD-14` — **Non-atomic cache read-modify-write** (`GET` counter, increment in code, `SET`). Lost updates under concurrency. → Instead: `INCR`/`HINCRBY`, Lua/`MULTI`, or keep the counter in the DB (DATA-BP-7).

## Anti-patterns

`CACHE-AP-1` — **Cache as source of truth.**
- Symptoms: data written only to Redis (carts, balances, quotas, workflow state) with no durable copy; restarts or evictions lose business data; AOF/RDB treated as the backup.
- Why it hurts: eviction, failover with async replication and `FLUSHALL` lose committed writes.
- Way out: persist to a durable store and cache from it; if Redis must hold state, run it as a database (separate instance, `noeviction`, AOF `everysec` or managed durable variant such as MemoryDB) and accept it is no longer a cache.

`CACHE-AP-2` — **Caching to hide a broken query.**
- Symptoms: a 3 s query "fixed" with a 10 min cache; the first request after expiry still times out; DB falls over when the cache is flushed.
- Why it hurts: the system's real capacity is the uncached path; every miss or outage exposes it.
- Way out: fix the query/index/model first (DATA, PERF); cache only paths that are already acceptable uncached at miss rates you will see.

`CACHE-AP-3` — **Cache-everything layer.**
- Symptoms: a generic decorator/middleware caches every repository call or HTTP response; many keyspaces with < 50% hit ratio; invalidation bugs reported as "random stale data".
- Why it hurts: memory and latency cost without benefit; impossible to reason about staleness per data type.
- Way out: cache by explicit decision per data type (CACHE-BP-1); remove low-hit keyspaces based on metrics (CACHE-BP-18).

`CACHE-AP-4` — **Invalidation scattered across write paths.**
- Symptoms: `DEL product:*` calls sprinkled in handlers, admin tools, batch jobs; other services write the same table without invalidating.
- Why it hurts: every new write path is a stale-data bug; correctness depends on discipline.
- Way out: centralise invalidation in the repository/write model, or drive it from CDC/outbox events (CACHE-BP-9); short TTL as safety net.

`CACHE-AP-5` — **Cache-dependent availability (thundering herd on recovery).**
- Symptoms: DB sized for the cached load only; a cache node failure or deploy flush causes a DB outage; recovery itself causes a second outage.
- Why it hurts: the cache became a hidden hard dependency with no fallback capacity.
- Way out: protected fallback (CACHE-BP-8), coalescing (CACHE-BP-4), warm-up (CACHE-BP-17), replicated cache clusters, and capacity planning for a realistic miss rate (SCALE).

`CACHE-AP-6` — **See CONC-AP-1 (canonical mechanism).** For correctness-sensitive cache locks verify resource-side fencing or a durable invariant.

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| CACHE-CHK-1 | Is every cache write given a TTL with jitter? (CACHE-BP-3, CACHE-BAD-1, CACHE-BAD-2) | Go: `Set(ctx, k, v, 0)` (go-redis, 0 = no expiry), constant TTLs; Node ioredis/node-redis: `set(k, v)` without `'EX'`/`{ EX }`, `hset` without `expire`. In Redis: `INFO keyspace` `expires` vs `keys`; sample `TTL` = -1. Fail: significant share of cache keys without TTL | Medium |
| CACHE-CHK-2 | Are concurrent misses coalesced? (CACHE-BP-4, CACHE-BP-5) | Go: `singleflight`, `groupcache`; Node: in-flight promise map, `async-cache-dedupe`, `cache-manager` wrappers. Check hot, expensive keys specifically. Fail: none on keys whose miss costs > ~100 ms or hits a shared DB under high RPS | High |
| CACHE-CHK-3 | Is invalidation post-commit and complete across write paths? (CACHE-BP-2, CACHE-BP-9, CACHE-BAD-3, CACHE-AP-4) | Find all writers of cached tables (grep table name, ORM model updates, other repos/services); check `Del` placement relative to `Commit`/`$transaction` end; look for `Set` of new value on write. Fail: a write path with no invalidation and TTL > staleness budget | High (Critical for prices, permissions, balances) |
| CACHE-CHK-4 | Does the service survive the cache being down or slow? (CACHE-BP-8, CACHE-BAD-4, CACHE-AP-5) | Go go-redis `ReadTimeout`/`WriteTimeout`/`DialTimeout`/`PoolTimeout`; Node ioredis `commandTimeout`, `maxRetriesPerRequest` (default 20), `enableOfflineQueue` (default true — commands queue indefinitely while disconnected). Check error handling on `Get` (`redis.Nil` vs other errors). Test: block Redis in staging. Fail: requests error or hang | High |
| CACHE-CHK-5 | Is a cache holding the only copy of business data? (CACHE-AP-1) | Redis writes with no DB write in the same flow (carts, sessions with state, counters billed later); Redis persistence config; architecture docs. Fail: loss on eviction/failover | Critical |
| CACHE-CHK-6 | Are keys namespaced, versioned and fully scoped? (CACHE-BP-7, CACHE-BAD-6, CACHE-BP-14) | Key-building functions (`fmt.Sprintf("user:%s"`, template strings); compare inputs of the cached function vs key components (tenant, locale, role). Fail: missing a value-shaping input | High (Critical if cross-tenant/user leak) |
| CACHE-CHK-7 | Is memory bounded and eviction policy correct? (CACHE-BP-13, CACHE-BAD-5, CACHE-BAD-10) | Redis `CONFIG GET maxmemory*`, ElastiCache parameter group, Helm values; in-process: Go `map[`+`sync.Mutex` caches without size bound, `sync.Map` caches; Node module-level `new Map()`/object caches, `lru-cache` without `max`/`maxSize`/`ttl`. Fail: unbounded or `noeviction` on a cache, or mixed cache+durable instance | Medium (High if mixed) |
| CACHE-CHK-8 | Are negative lookups cached briefly and errors never cached? (CACHE-BP-6, CACHE-BAD-9) | Miss path: what is stored on `ErrNoRows`/`null`; what on DB error. Fail: errors cached, or enumeration traffic always reaching DB | Medium |
| CACHE-CHK-9 | Are hot keys identified and mitigated? (CACHE-BP-11) | Redis `--hotkeys`, slowlog, per-shard CPU/network in metrics; config/feature-flag/homepage keys read on every request. Fail: one shard near saturation or a single key on every request with no L1 | Medium |
| CACHE-CHK-10 | Are value sizes and serialisation cost bounded? (CACHE-BP-12, CACHE-BAD-8) | `redis-cli --bigkeys`/`--memkeys`, `MEMORY USAGE`; profiles showing `json.Marshal`/`JSON.parse` of cache values; cached full lists. Fail: values > ~512 KB on hot paths | Medium |
| CACHE-CHK-11 | Are dangerous commands avoided? (CACHE-BAD-7) | grep `Keys(ctx`, `.keys(`, `FLUSHALL`, `FLUSHDB` in app code; `rename-command` / ACLs. Fail: `KEYS` on request or scheduled path | Medium |
| CACHE-CHK-12 | Are atomic operations used for counters and compound updates? (CACHE-BAD-14) | Get-then-Set patterns on numeric values; rate limiters implemented with GET/SET. Fail: non-atomic RMW on shared counters | Medium |
| CACHE-CHK-13 | Is the client a shared, pooled singleton? (CACHE-BAD-13) | Go `redis.NewClient(` inside handlers/funcs called per request, `PoolSize`; Node `createClient(`/`new Redis(` outside module scope. Fail: client per request | Medium |
| CACHE-CHK-14 | Are authenticated responses protected from shared caches? (CACHE-BAD-11, CACHE-BP-14) | Response headers on auth endpoints (`curl -I` with token): need `private` or `no-store`; CDN config (CloudFront cache policies, Fastly VCL, Cloudflare rules) ignoring `Authorization`/cookies. Fail: personalised body cacheable publicly | Critical |
| CACHE-CHK-15 | Are HTTP cache headers deliberate for assets and API reads? (CACHE-BP-15, CACHE-BAD-12) | Static file server config (`http.FileServer`, `express.static` `maxAge`/`immutable`, nginx `expires`), build output hashing; `ETag`/`Last-Modified`/304 handling on read-heavy GETs | Low |
| CACHE-CHK-16 | Is the CDN configured with explicit keys, purge and stale-if-error? (CACHE-BP-16) | Terraform/CDN config: cache key query/header/cookie whitelist, `s-maxage`, purge integration in publish/deploy pipeline, origin shield. Fail: cookie in cache key (0% hit) or no purge path for mutable content | Low (Medium if origin depends on it) |
| CACHE-CHK-17 | Are hit ratio, evictions and cache latency monitored? (CACHE-BP-18, CACHE-AP-3) | Metrics/dashboards for hit/miss per prefix, `evicted_keys`, `used_memory`, cache p99. Fail: no hit-ratio metric for any cache | Medium |
| CACHE-CHK-18 | Is the cache used for correctness locks or masking a slow query? (CACHE-AP-2, CACHE-AP-6) | grep `SetNX`, `SET … NX`, `redlock`, `redsync`, `Redlock` guarding money/inventory; cached queries whose uncached latency exceeds the SLO. Fail: correctness depends on the Redis lock, or miss path breaches SLO | High |

## Go / Node.js notes

- Go in-process caches share memory across goroutines: `ristretto` (admission policy, cost-bounded) and `otter` (S3-FIFO, high throughput) are the mainstream bounded choices; avoid hand-rolled `map`+`RWMutex` without bounds or TTL. Large pointer-heavy caches add GC scan cost — `bigcache`/`freecache` store bytes off the GC's radar at the price of serialisation.
- Go `singleflight` dedups per process only; `DoChan` lets callers respect their own `ctx` deadline while the shared load continues. Use `context.WithoutCancel` for the shared load so one cancelled caller does not abort it for all.
- go-redis v9 (`redis/go-redis`) defaults: `PoolSize` 10 × GOMAXPROCS, `ReadTimeout` 3 s — usually too long for a cache; set ~50–200 ms. `redis.Nil` means miss, any other error is a cache failure.
- Node in-process caches live per worker/process: PM2 cluster or multiple pods mean N divergent copies; `lru-cache` v10+ requires `max` or `maxSize` (or `ttl` with `ttlAutopurge`) and supports `fetchMethod` with built-in coalescing and stale-while-revalidate.
- Node ioredis defaults (`maxRetriesPerRequest: 20`, offline queue on) make a Redis outage look like hanging requests; for caches set `maxRetriesPerRequest: 1`, `enableOfflineQueue: false`, `commandTimeout` ~100 ms. node-redis v4+ needs explicit `socket.reconnectStrategy` and `disableOfflineQueue`.
- Node `JSON.parse` of large cached values runs on the event loop and blocks every request on that process; keep values small or use streaming/binary formats for big ones.
- Go HTTP caching: `net/http` has no response cache; set `Cache-Control`/`ETag` yourself and use `http.ServeContent` (handles `If-None-Match`/`If-Modified-Since` → 304). Node: Express sets weak ETags by default (`app.set('etag')`), Fastify needs `@fastify/etag` and `@fastify/caching`.
- Both stacks: cache-library wrappers (`eko/gocache`, Node `cache-manager`) make it easy to add caching without a staleness budget or metrics — check that each use maps to a CACHE-BP-1 decision.
- Valkey (Linux Foundation fork after Redis's 2024 licence change) is protocol-compatible and the default on several managed offerings; client libraries above work unchanged.
