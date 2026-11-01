# Data storage & transactions — rules

> **Scope:** choosing and modelling data stores, indexes and query plans, transactions and isolation, DB-level locking, connection pooling, DB-side pagination and N+1, schema migrations and backfills, deletes and retention, multi-tenancy, replicas, backups, key choice. **Hands off to:** in-process locks and worker coordination → CONC; idempotency keys, outbox, sagas, cross-service consistency → IDEM; caches in front of the DB → CACHE; sharding and partition strategy for growth → SCALE; query latency budgets and profiling → PERF; encryption, injection, row access control as a security boundary → SEC; running migrations in the deploy pipeline → OPS; ownership of data between services → ARCH; API pagination contract → API.

## Best practices

`DATA-BP-1` — **Enforce invariants in the schema.** Why: application checks race and get bypassed by scripts and new services. How: `NOT NULL`, `FOREIGN KEY` (with an index on the referencing column), `UNIQUE` (including composite and partial), `CHECK (amount >= 0)`, exclusion constraints for overlapping ranges; map constraint violations (`23505`, `23503`) to 409/422.

`DATA-BP-2` — **Normalise the write model; denormalise only with a named sync mechanism.** Why: duplicated facts drift. How: 3NF for transactional tables; denormalised copies (counters, summaries, search docs, JSON snapshots) maintained by the same transaction, a trigger, or CDC with a documented lag; keep immutable snapshots (order line price at purchase time) as deliberate history, not denormalisation.

`DATA-BP-3` — **Design composite indexes from the queries: equality columns first, then range, then sort.** Why: a wrong column order makes the index unusable for the range/sort. How: for `WHERE tenant_id=? AND status=? AND created_at>? ORDER BY created_at` use `(tenant_id, status, created_at)`; covering via `INCLUDE (…)` (Postgres) or trailing columns for index-only scans; partial indexes for skewed predicates (`WHERE status='pending'`, `WHERE deleted_at IS NULL`); drop unused indexes (`pg_stat_user_indexes.idx_scan = 0`) since each one taxes writes.

`DATA-BP-4` — **Verify hot queries with real plans and track them continuously.** Why: plans change with data distribution; a seq scan appears at 10M rows, not in dev. How: `EXPLAIN (ANALYZE, BUFFERS)` on production-sized data; `pg_stat_statements` / MySQL `performance_schema` top-N by total time; `auto_explain` or slow log at ~200–500 ms; watch row-estimate errors >10× (stale stats → `ANALYZE`, extended statistics).

`DATA-BP-5` — **Keep transactions short and free of network I/O.** Why: open transactions hold locks and, in Postgres, block vacuum (bloat) and pin a pooled connection. How: no HTTP/gRPC/broker calls inside; compute first, then open tx, write, commit; target < 100 ms; set `idle_in_transaction_session_timeout` (e.g. 60 s). Publishing events atomically with the write → outbox (IDEM).

`DATA-BP-6` — **Choose isolation per invariant and know which anomalies remain.** Why: Read Committed allows lost updates and write skew; Repeatable Read in Postgres prevents lost update (aborts) and phantoms but not write skew; MySQL InnoDB RR does not abort lost updates on plain reads. How: document the level per critical flow; use Serializable (Postgres SSI) for multi-row invariants such as "at least one on-call doctor" or "no double booking", and retry the whole transaction on `40001`/`40P01` with a small bounded loop (3–5 tries, jittered).

`DATA-BP-7` — **See CONC-BP-8 (canonical mechanism).** Use rows-affected to distinguish accepted and rejected conditional writes.

`DATA-BP-8` — **See CONC-BP-9 (canonical mechanism).** Store and check the version in the write predicate.

`DATA-BP-9` — **See CONC-BP-10 (canonical mechanism).** Apply the lock order and wait budget inside the DB transaction.

`DATA-BP-10` — **Size connection pools from the database's limit down, and bound waits.** Why: N instances × per-instance pool > `max_connections` causes connection storms; unbounded pools amplify overload. How: total = instances × pool ≤ ~80% of DB limit (minus admin/replication slots); per-instance pool ≈ 2–4 × DB cores / instances as a starting point, then measure; set max lifetime (~30 min, shorter than LB/proxy idle cut) and idle timeout; acquire timeout of a few seconds; PgBouncer/RDS Proxy in transaction mode for many small clients or serverless (then avoid session state: session advisory locks, `SET`, `LISTEN`).

`DATA-BP-11` — **Paginate in the database with keyset (seek) queries on a unique, indexed sort key.** Why: `OFFSET n` reads and discards n rows; non-unique sorts duplicate/skip rows across pages. How: `WHERE (created_at, id) < ($1, $2) ORDER BY created_at DESC, id DESC LIMIT 50` with index `(created_at DESC, id DESC)` (prefix with `tenant_id` when scoped); row-value comparison in Postgres/MySQL 8; avoid exact `COUNT(*)` on large tables (use estimates or cap).

`DATA-BP-12` — **Load relations in sets, not per row.** Why: N+1 turns one request into hundreds of round trips; latency scales with page size. How: `WHERE id = ANY($1)` / `IN (…)` batch, joins, ORM eager loading (`Preload`, `include`, `relations`), DataLoader in GraphQL; assert query counts in tests for hot endpoints.

`DATA-BP-13` — **Set server-side time limits for statements, locks and idle transactions.** Why: one runaway query or forgotten transaction takes the database down for everyone. How: role- or connection-level `statement_timeout` (e.g. 5–30 s for OLTP roles), `lock_timeout`, `idle_in_transaction_session_timeout`; MySQL `max_execution_time`, `innodb_lock_wait_timeout`; plus client context deadlines (RES); separate role/pool for analytics with longer limits.

`DATA-BP-14` — **Ship schema changes as expand → migrate → contract, each step compatible with the running code.** Why: during a rolling deploy old and new code run together; a rename or drop breaks one of them. How: add nullable column/new table → dual write → backfill → switch reads → stop old writes → drop in a later release; never rename in place; migrations forward-only and backward-compatible with N−1 code.

`DATA-BP-15` — **Run DDL online with lock timeouts.** Why: `ALTER TABLE` waiting for an `ACCESS EXCLUSIVE` lock queues all reads behind it — an outage in seconds. How: Postgres: `SET lock_timeout = '3s'` and retry; `CREATE INDEX CONCURRENTLY` (outside a tx; check for `INVALID` indexes after failure); `ADD CONSTRAINT … NOT VALID` then `VALIDATE CONSTRAINT`; `NOT NULL` via validated `CHECK` first (PG12+ uses it); `ADD COLUMN … DEFAULT const` is metadata-only from PG11. MySQL: `ALGORITHM=INSTANT/INPLACE, LOCK=NONE` or gh-ost. Lint migrations with `squawk` or `strong_migrations`-style checks.

`DATA-BP-16` — **Backfill and bulk-modify in small, resumable, throttled batches.** Why: a single `UPDATE` of 50M rows holds locks, bloats WAL/undo, spikes replica lag and cannot be resumed. How: iterate by primary-key range (`WHERE id > $last ORDER BY id LIMIT 5000`), commit per batch, sleep or throttle on replica lag (e.g. pause above 5 s), checkpoint progress, make each batch idempotent.

`DATA-BP-17` — **See IDEM-BP-14 (canonical mechanism).** Inspect replica routing and lag-aware admission for each query class.

`DATA-BP-18` — **See OPS-BP-15 (canonical mechanism).** For the chosen DB verify PITR configuration, restore evidence and the actual recoverable point.

`DATA-BP-19` — **Scope every tenant-owned row and index by tenant.** Why: one missing `WHERE tenant_id` leaks data across customers. How: `tenant_id` on every tenant table, leading column in composite PKs/indexes; Postgres Row-Level Security with `current_setting('app.tenant_id')` set per transaction (`SET LOCAL`) as defence in depth; repository layer that requires a tenant parameter; tests with two tenants.

`DATA-BP-20` — **Define retention per table and implement it cheaply.** Why: unbounded tables degrade indexes, vacuum, backups and cost, and keep personal data past legal limits. How: retention period per data class; time-partition high-volume tables (logs, events, outbox) and `DROP`/detach old partitions instead of `DELETE`; erase or anonymise PII on schedule; soft deletes, if used, get a partial unique index `WHERE deleted_at IS NULL` and a purge job.

`DATA-BP-21` — **Tie every retention or deletion obligation to code that covers all ingestion paths.** Why: a purge job whose predicate real data never reaches, or an import that loads records already past retention, satisfies a reviewer while violating the obligation. How: cite the obligation's source (policy, ADR, contract, regulation) next to the enforcing job; apply it at ingestion (sync, import and backfill do not store data already past its period) and on schedule; test each ingestion path with a record just past the limit; give audit/journal stores their own owner-run anonymisation or deletion; report the counts purged.

## Bad practices

`DATA-BAD-1` — **Missing index for a hot filter, join or foreign key.** Seq scans grow linearly with the table; unindexed FKs make parent deletes lock and scan the child table. → Instead: DATA-BP-3, DATA-BP-4.

`DATA-BAD-2` — **Non-sargable predicates on indexed columns** (`WHERE lower(email)=…`, `DATE(created_at)=…`, `LIKE '%term'`, implicit casts such as comparing varchar to number). Index ignored. → Instead: expression index, range predicates (`created_at >= d AND < d+1`), trigram/full-text index or search (DATA-BP-3).

`DATA-BAD-3` — **Read-modify-write without a lock, version or atomic statement.** Two requests read `balance=100`, both write their result; one update disappears. → Instead: DATA-BP-7, DATA-BP-8, DATA-BP-9.

`DATA-BAD-4` — **Check-then-insert uniqueness in application code** (`SELECT` then `INSERT` if absent). Concurrent requests both pass the check, creating duplicates. → Instead: unique constraint + `ON CONFLICT` (DATA-BP-1, DATA-BP-7).

`DATA-BAD-5` — **Network calls inside a transaction.** Payment gateway latency becomes lock-hold time; a timeout leaves the remote side done and the local side rolled back. → Instead: DATA-BP-5; cross-system atomicity → IDEM.

`DATA-BAD-6` — **Transaction not rolled back on every error path.** Connection returns to the pool "idle in transaction", holding locks until timeout. → Instead: `defer tx.Rollback()` right after `BeginTx` in Go; `try/finally` with `ROLLBACK` and `client.release()` in Node; DATA-BP-13.

`DATA-BAD-7` — **Default or unbounded pool settings.** Go `database/sql` opens unlimited connections by default; 50 pods × node-pg default 10 = 500 connections against a 400 limit. → Instead: DATA-BP-10.

`DATA-BAD-8` — **Query per item in a loop (N+1).** 1 + N round trips per request. → Instead: DATA-BP-12.

`DATA-BAD-9` — **Unbounded result sets** (`SELECT *` without `LIMIT`, loading whole tables into memory for export). OOMs and long locks as data grows. → Instead: DATA-BP-11, streaming cursors for exports; explicit column lists.

`DATA-BAD-10` — **Blocking DDL on a large, busy table** (`CREATE INDEX` without `CONCURRENTLY`, `ALTER TABLE … TYPE`, adding FK/NOT NULL validated in one step, no `lock_timeout`). Writes or reads stall for minutes. → Instead: DATA-BP-15.

`DATA-BAD-11` — **Single-statement mass backfill or delete.** Replica lag spikes, WAL/binlog floods, rollback takes as long as the run. → Instead: DATA-BP-16.

`DATA-BAD-12` — **Rename or drop of a column in the same release as the code change.** Old pods still running during rollout fail. → Instead: DATA-BP-14.

`DATA-BAD-13` — **Read-after-write against a replica.** User saves, list reloads from a lagging replica, item "disappears"; worse, a follow-up write is based on stale data. → Instead: DATA-BP-17; never base writes on replica reads.

`DATA-BAD-14` — **Random UUIDv4 as clustered primary key** (InnoDB, SQL Server) or as the sole index on huge append tables. Random page splits, cache-unfriendly inserts, 2–3× index growth. → Instead: bigint or UUIDv7 (Key decisions; DATA-BP-1).

`DATA-BAD-15` — **Soft delete without partial unique index and default filtering.** Users cannot re-register a deleted email; queries forget `deleted_at IS NULL` and show deleted data. → Instead: DATA-BP-20.

`DATA-BAD-16` — **Money as float/double columns.** Rounding errors accumulate in sums and comparisons. → Instead: `numeric(19,4)` or integer minor units plus currency (API-BP-17).

## Anti-patterns

`DATA-AP-1` — **Integration database (shared DB across services).**
- Symptoms: several services read/write the same tables; migrations need cross-team sign-off; one service's query slows others.
- Why it hurts: schema becomes a public contract no one can change; no ownership of invariants; coupled deploys and failures.
- Way out: one owning service per table; others use its API, events (MSG) or a published read model/CDC stream; migrate readers first, then revoke grants.

`DATA-AP-2` — **ORM as the schema designer.**
- Symptoms: TypeORM `synchronize: true`, GORM `AutoMigrate` at startup in production, no reviewed migration files, generated queries never inspected.
- Why it hurts: uncontrolled locking DDL at deploy, missing constraints and indexes, accidental drops, N+1 hidden behind lazy loading.
- Way out: versioned migration files (goose, Atlas, golang-migrate, Prisma Migrate, Knex/Drizzle migrations) reviewed and linted; log/inspect SQL of hot paths; constraints declared explicitly.

`DATA-AP-3` — **Entity-Attribute-Value or "JSON bag" generic schema.**
- Symptoms: `attributes(entity_id, key, value text)` or one `data jsonb` column holding most fields; types and constraints enforced nowhere.
- Why it hurts: no constraints, painful queries, poor plans, every consumer re-validates.
- Way out: real columns for queried and invariant-bearing fields; `jsonb` only for genuinely sparse, opaque extras, with GIN/expression indexes on the paths actually queried.

`DATA-AP-4` — **Store chosen by fashion, not access pattern.**
- Symptoms: relational data with joins and transactions forced into MongoDB/DynamoDB; or a search cluster used as primary storage; multiple stores for a small team.
- Why it hurts: invariants reimplemented in code, consistency bugs, operational load per store.
- Way out: list access patterns and invariants first; consolidate on a relational store where it fits; keep specialised stores as derived projections fed by CDC.

`DATA-AP-5` — **Naive table-as-queue.**
- Symptoms: workers poll `SELECT … WHERE status='new' LIMIT 1` then `UPDATE`, without `SKIP LOCKED`; double processing; the jobs table grows forever and bloats.
- Why it hurts: duplicate work, lock contention, vacuum pressure, no retry/backoff semantics.
- Way out: `FOR UPDATE SKIP LOCKED` claims with lease timestamps and retention, or a proven library (River, graphile-worker, pg-boss), or a broker (MSG).

`DATA-AP-6` — **Unbounded append-only tables with no lifecycle.**
- Symptoms: `events`, `audit_log`, `outbox`, `sessions` with hundreds of millions of rows, `DELETE … WHERE created_at <` jobs that never finish.
- Why it hurts: bloated indexes and backups, slow vacuum, retention/privacy violations.
- Way out: time partitioning with partition drop, archive to object storage, retention policy per class (DATA-BP-20).

`DATA-AP-7` — **Lock-everything consistency.**
- Symptoms: every request opens Serializable or takes `LOCK TABLE`/advisory global locks "to be safe"; heavy use of in-app mutexes around DB writes.
- Why it hurts: throughput collapses under contention; the locks do not hold across instances anyway (CONC).
- Way out: identify the specific invariant; use constraints, atomic statements, row locks or targeted Serializable with retries (DATA-BP-6…9).

## Go / Node.js notes

- Go `database/sql` defaults: `MaxOpenConns` 0 (unlimited), `MaxIdleConns` 2 (causes connection churn under load), no lifetime — always set all three plus `SetConnMaxIdleTime`. `pgxpool` defaults `MaxConns` to max(4, NumCPU), which is often too small for I/O-bound services.
- Go: always pass `ctx` (`QueryContext`, `ExecContext`) so request deadlines cancel queries; `rows.Close()` and `rows.Err()` are mandatory, a leaked `*sql.Rows` pins a connection.
- GORM traps: `Save` writes every column (silent lost update), `Updates(struct)` skips zero values, `AutoMigrate` is not a migration tool; `sqlc` (SQL-first, typed) makes queries reviewable.
- Node `pg.Pool` default `max: 10`, `idleTimeoutMillis: 10000`, and `connectionTimeoutMillis: 0` (waits forever) — set an acquire timeout. Prisma `connection_limit` defaults to `num_physical_cpus * 2 + 1` per client instance; one `PrismaClient` per process.
- Node `pg` returns `int8`/`numeric` as strings by default (correct for precision; do not blindly `parseInt`); Prisma maps `BigInt`/`Decimal` to non-JSON-serialisable types.
- Prisma interactive transactions default to `timeout: 5000` ms and `maxWait: 2000` ms; long work inside them fails — consistent with DATA-BP-5. Nested writes are transactional; independent `await`s are not.
- Serverless Node (Lambda, Vercel) multiplies connections per concurrent invocation — use RDS Proxy, PgBouncer, Prisma Accelerate or HTTP-based drivers (Neon/PlanetScale).
- Migration tooling: Go — goose, golang-migrate, Atlas (declarative with lint); Node — Prisma Migrate, Drizzle Kit, Knex, node-pg-migrate. Check whether each wraps files in a transaction before using `CREATE INDEX CONCURRENTLY`.
