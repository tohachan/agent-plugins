# Caching — rules

> **Scope:** application caches (in-process, Redis/Valkey/Memcached, two-tier), caching patterns, TTLs and invalidation, stampede and hot-key protection, key design and serialisation, cache–DB consistency, eviction and memory, HTTP caching and CDN, behaviour when the cache fails. **Hands off to:** DB indexes and query tuning before caching → DATA; timeouts/circuit breakers on the cache client → RES; idempotency records and dedup stores (not caches) → IDEM; distributed locks for correctness → CONC; cache cluster sizing and sharding → SCALE; latency budgets and profiling → PERF; caching of personalised/auth data and cache poisoning → SEC; hit-ratio dashboards → OBS; API cache-related contract (ETag on writes) → API.

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
