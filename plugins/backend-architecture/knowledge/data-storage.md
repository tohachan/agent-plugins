# Data storage & transactions

> **Scope:** choosing and modelling data stores, indexes and query plans, transactions and isolation, DB-level locking, connection pooling, DB-side pagination and N+1, schema migrations and backfills, deletes and retention, multi-tenancy, replicas, backups, key choice. **Hands off to:** in-process locks and worker coordination → CONC; idempotency keys, outbox, sagas, cross-service consistency → IDEM; caches in front of the DB → CACHE; sharding and partition strategy for growth → SCALE; query latency budgets and profiling → PERF; encryption, injection, row access control as a security boundary → SEC; running migrations in the deploy pipeline → OPS; ownership of data between services → ARCH; API pagination contract → API.

## Contents
- Key decisions
- Best practices (DATA-BP-1…20)
- Bad practices (DATA-BAD-1…16)
- Anti-patterns (DATA-AP-1…7)
- Audit checklist (DATA-CHK-1…20)
- Go / Node.js notes

## Key decisions

| Decision | Options | Choose … when | Trade-off |
| --- | --- | --- | --- |
| Primary store | relational (PostgreSQL, MySQL) / document (MongoDB, DynamoDB documents) / key-value (Redis, DynamoDB) / wide-column (Cassandra, ScyllaDB, Bigtable) / search (OpenSearch, Elasticsearch) | Relational by default: multi-entity invariants, ad-hoc queries, joins, transactions. Document when aggregates are read/written whole and cross-aggregate queries are rare. KV/wide-column when access patterns are known up front, writes are massive (>~50k/s) and you partition by key. Search only as a derived index | Non-relational stores push joins, constraints and many transactions into the application; search engines are not durable systems of record |
| Isolation level | Read Committed / Repeatable Read (snapshot) / Serializable | RC default plus explicit locks or atomic updates for hot invariants; RR for consistent multi-statement reads (reports); Serializable when invariants span rows (write skew) and you can retry on `40001` | Higher isolation means more aborts and retry logic; lower isolation needs per-case locking discipline |
| Concurrency control on rows | atomic conditional UPDATE / optimistic (version column) / pessimistic (`SELECT … FOR UPDATE`) | Atomic UPDATE for counters and balances; optimistic for low-contention edits, long user think time; pessimistic for short, high-contention critical sections | Optimistic wastes work under contention; pessimistic risks lock waits and deadlocks |
| Primary key | bigint identity / UUIDv7 / UUIDv4 / natural key | bigint for single-DB internal keys (8 bytes, densest indexes); UUIDv7 when IDs are generated in app or across shards and must be time-ordered; UUIDv4 only as a secondary opaque token; natural key only if truly immutable | UUIDs are 16 bytes per index entry; v4 randomises B-tree inserts; bigint leaks counts if exposed (expose an opaque ID instead) |
| Read scaling | bigger primary / read replicas / cache (CACHE) / CQRS read model | Replicas when reads dominate and tolerate seconds of lag; cache for hot keys; read model when query shapes differ fundamentally from writes | Replicas add lag and routing logic; caches add invalidation |
| Multi-tenancy | shared tables with `tenant_id` / schema per tenant / database per tenant | Shared for many small tenants (>1k); schema-per-tenant for tens to low hundreds with customisation; DB-per-tenant for regulated or very large tenants needing isolation, PITR and placement per tenant | Shared needs strict tenant scoping (RLS); per-tenant multiplies migrations and connections |
| Delete semantics | hard delete / soft delete (`deleted_at`) / archive table / time partitions | Hard delete + audit log by default and for erasure (GDPR); soft delete when users need undo or legal hold; partitions for time-based retention of high-volume data | Soft deletes leak into every query and unique index; hard deletes need FK strategy |
| Migration approach | in-place change / expand-and-contract / online schema tool (gh-ost, pt-osc, pgroll) | Expand/contract for any change visible to running code; online tools for MySQL table rewrites or when the DB cannot do it online | More deploys and temporary dual logic, in exchange for zero downtime |

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

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| DATA-CHK-1 | Are key invariants enforced by constraints? (DATA-BP-1, DATA-BAD-4) | Read migrations/`schema.prisma`/`*.sql` for UNIQUE, FK, CHECK on emails, external IDs, order numbers, balances. grep app code for `SELECT` followed by `INSERT` on the same key. Fail: uniqueness or non-negativity only checked in code | High |
| DATA-CHK-2 | Are hot queries indexed and plans verified? (DATA-BP-3, DATA-BP-4, DATA-BAD-1, DATA-BAD-2) | `pg_stat_statements` top 20 by `total_exec_time`; `EXPLAIN (ANALYZE, BUFFERS)` for them; `pg_stat_user_tables.seq_scan` on large tables; FK columns without indexes; grep `LIKE '%`, `lower(`, `DATE(` in WHERE. Fail: seq scan on > ~100k-row table on a request path | Medium (High if it already breaches latency SLO) |
| DATA-CHK-3 | Are read-modify-write paths protected? (DATA-BP-7, DATA-BP-8, DATA-BAD-3) | Find balance/stock/counter/status updates. Go: load struct → mutate → `db.Save(&x)` (GORM saves all columns), `UPDATE … SET qty = $1` computed in code; Node: `findUnique` then `update({ data: { qty: x.qty - 1 } })`, `entity.save()`. Fail: no `FOR UPDATE`, version check or atomic expression | High (Critical for money/inventory) |
| DATA-CHK-4 | Is the isolation level known and correct for multi-row invariants? (DATA-BP-6) | grep `sql.LevelSerializable`, `BeginTx(ctx, &sql.TxOptions`, `isolationLevel` (Prisma/TypeORM/Knex), `SET TRANSACTION ISOLATION`; DB defaults. Fail: write-skew-prone invariant (bookings, quotas, limits) under RC/RR with no lock; or Serializable with no `40001` retry | High |
| DATA-CHK-5 | Are transactions short, I/O-free and always closed? (DATA-BP-5, DATA-BAD-5, DATA-BAD-6) | Go: code between `BeginTx`/`db.Transaction(func` and `Commit` calling `http.`, gRPC clients, `Publish`; missing `defer tx.Rollback()`. Node: `$transaction(async`, `knex.transaction`, `BEGIN` blocks with `await fetch`/`axios`/producer `send`; `pool.connect()` without `release()` in `finally`. DB: `pg_stat_activity` state `idle in transaction`. Fail: any such pattern | High |
| DATA-CHK-6 | Are pools sized against the DB limit? (DATA-BP-10, DATA-BAD-7) | Go: `sql.Open` without `SetMaxOpenConns`/`SetConnMaxLifetime`; `pgxpool` `MaxConns`. Node: `new Pool(` `max`, Prisma `connection_limit` in URL, Knex `pool: {min,max}`, Sequelize `pool`. Multiply by max replicas (HPA `maxReplicas`) and compare to `max_connections`. Fail: product exceeds ~80% of limit or pool unbounded | High |
| DATA-CHK-7 | Are statement, lock and idle-tx timeouts set? (DATA-BP-13) | DB parameter group / `postgresql.conf` / `ALTER ROLE … SET statement_timeout`; connection strings `statement_timeout`, `options=-c`; MySQL `max_execution_time`. Fail: all 0 (unlimited) for the app role | Medium |
| DATA-CHK-8 | Are lists paginated by keyset on a unique key? (DATA-BP-11, DATA-BAD-9) | grep `OFFSET`, `.Offset(`, `skip:`, `.skip(`; `ORDER BY` on non-unique column alone; `COUNT(*)` per page. Fail: deep offset on large tables or unstable sort | Medium |
| DATA-CHK-9 | Are relations loaded in batches? (DATA-BP-12, DATA-BAD-8) | Loops containing queries: Go `for … { db.Query`/`First(`; Node `for (…) { await prisma.`, `.map(async … findUnique)`; enable query logging and count queries per request on a list endpoint. Fail: count grows with page size | Medium |
| DATA-CHK-10 | Are migrations versioned, reviewed and not auto-applied by the ORM? (DATA-AP-2) | Migration dir (`migrations/`, `prisma/migrations`, `db/migrate`); grep `AutoMigrate(`, `synchronize: true`, `sequelize.sync(`, `prisma db push` in deploy scripts. Fail: ORM sync in production | High |
| DATA-CHK-11 | Are DDL changes online and lock-bounded? (DATA-BP-15, DATA-BAD-10) | Read recent migrations for `CREATE INDEX` without `CONCURRENTLY`, `ALTER COLUMN … TYPE`, `ADD … NOT NULL`/FK without `NOT VALID`, no `lock_timeout`; migration tooling wrapping each file in a tx (blocks `CONCURRENTLY`). Fail on tables > ~1M rows or hot tables | High |
| DATA-CHK-12 | Are schema changes expand/contract-safe for rolling deploys? (DATA-BP-14, DATA-BAD-12) | Diff migrations against code in the same PR: drops/renames of columns still referenced by the previous release. Fail: destructive change shipped with the code switch | High |
| DATA-CHK-13 | Are backfills batched and resumable? (DATA-BP-16, DATA-BAD-11) | Data migration scripts: single `UPDATE`/`DELETE` without `LIMIT`/range; no checkpoint; no throttle on replica lag | Medium (High on large hot tables) |
| DATA-CHK-14 | Is replica usage lag-aware? (DATA-BP-17, DATA-BAD-13) | Read/write routing: Go separate `*sql.DB` for replica, `dbresolver`; Node Prisma `readReplicas` extension, TypeORM `replication`, Knex read config. Check post-write reads and writes based on replica reads; lag alerts. Fail: write decision taken on replica data | Medium (High if it drives money/state) |
| DATA-CHK-15 | Are backups PITR-capable and restore-tested? (DATA-BP-18) | Terraform/console: `backup_retention_period`, `deletion_protection`, PITR enabled, cross-account copies; runbook with last restore date. Fail: no PITR, retention < 7 days, or no restore in the last 6–12 months | High (Critical if no backups) |
| DATA-CHK-16 | Is every tenant query scoped? (DATA-BP-19) | Repository code for queries lacking `tenant_id`; RLS policies (`CREATE POLICY`, `ENABLE ROW LEVEL SECURITY`); PK/index leading column. Fail: any tenant table reachable without tenant predicate on a user path | Critical |
| DATA-CHK-17 | Do keys suit the engine and exposure? (DATA-BAD-14) | Schema PK types: `uuid DEFAULT gen_random_uuid()` / `uuid.New()` / `crypto.randomUUID()` as InnoDB clustered PK or on very large tables; sequential bigint IDs exposed in URLs on enumerable resources (SEC). Fail: v4 clustered PK on high-insert table | Low (Medium at scale) |
| DATA-CHK-18 | Do soft deletes and retention work? (DATA-BP-20, DATA-BAD-15, DATA-AP-6) | `deleted_at` columns with plain UNIQUE; queries missing the filter; GORM `gorm.DeletedAt`, Prisma middleware/extensions for soft delete; largest tables (`pg_total_relation_size`) and their purge jobs. Fail: no retention on growing PII or event tables | Medium |
| DATA-CHK-19 | Is the store a fit for its access patterns? (DATA-AP-3, DATA-AP-4, DATA-AP-1) | Data stores in infra; multi-document transactions or app-side joins in Mongo/DynamoDB code; search engine as only copy; several services' credentials to one schema. Fail: invariants or ownership impossible to enforce | Medium |
| DATA-CHK-20 | Is money stored exactly? (DATA-BAD-16) | Column types `float`, `double`, `real` for amounts; Prisma `Float`, GORM `float64` fields named `amount`/`price` | High |
| DATA-CHK-21 | Do documented retention and deletion obligations match the implemented purge and ingestion behaviour? (DATA-BP-21, DATA-BP-20, SEC-BP-19) | Find the obligation sources (specs, ADRs, privacy policy, retention register, contracts) and each store holding the data; for each, the job or TTL that enforces it, its predicate, and whether any code path ever produces rows matching it; sync/import paths that load already-expired records; audit and journal stores. "Verified" requires citing both the obligation and the mechanism that covers it. Fail: an obligation with no enforcing code, a dead predicate, or an ingestion path that bypasses it | High (legal/regulatory) |

## Go / Node.js notes

- Go `database/sql` defaults: `MaxOpenConns` 0 (unlimited), `MaxIdleConns` 2 (causes connection churn under load), no lifetime — always set all three plus `SetConnMaxIdleTime`. `pgxpool` defaults `MaxConns` to max(4, NumCPU), which is often too small for I/O-bound services.
- Go: always pass `ctx` (`QueryContext`, `ExecContext`) so request deadlines cancel queries; `rows.Close()` and `rows.Err()` are mandatory, a leaked `*sql.Rows` pins a connection.
- GORM traps: `Save` writes every column (silent lost update), `Updates(struct)` skips zero values, `AutoMigrate` is not a migration tool; `sqlc` (SQL-first, typed) makes queries reviewable.
- Node `pg.Pool` default `max: 10`, `idleTimeoutMillis: 10000`, and `connectionTimeoutMillis: 0` (waits forever) — set an acquire timeout. Prisma `connection_limit` defaults to `num_physical_cpus * 2 + 1` per client instance; one `PrismaClient` per process.
- Node `pg` returns `int8`/`numeric` as strings by default (correct for precision; do not blindly `parseInt`); Prisma maps `BigInt`/`Decimal` to non-JSON-serialisable types.
- Prisma interactive transactions default to `timeout: 5000` ms and `maxWait: 2000` ms; long work inside them fails — consistent with DATA-BP-5. Nested writes are transactional; independent `await`s are not.
- Serverless Node (Lambda, Vercel) multiplies connections per concurrent invocation — use RDS Proxy, PgBouncer, Prisma Accelerate or HTTP-based drivers (Neon/PlanetScale).
- Migration tooling: Go — goose, golang-migrate, Atlas (declarative with lint); Node — Prisma Migrate, Drizzle Kit, Knex, node-pg-migrate. Check whether each wraps files in a transaction before using `CREATE INDEX CONCURRENTLY`.
