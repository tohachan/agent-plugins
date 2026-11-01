# Idempotency & consistency

> **Scope:** making repeated requests and messages safe (idempotency keys, natural idempotency, idempotent consumers), keeping state consistent across a DB and a broker or across services (outbox, CDC, sagas, 2PC), the consistency guarantees a system promises to readers, ordering and causality, reconciliation, ledgers, and side effects at third parties. **Hands off to:** retry policy, timeouts and backoff → RES; broker delivery guarantees, partitioning and DLQs → MSG; isolation levels, constraints and transaction mechanics → DATA; races and locks → CONC; HTTP method semantics and error contracts → API; replica lag and partitioning → SCALE.

## Contents
- Key decisions
- Best practices (IDEM-BP-1…20)
- Bad practices (IDEM-BAD-1…16)
- Anti-patterns (IDEM-AP-1…9)
- Audit checklist (IDEM-CHK-1…20)
- Go / Node.js notes

## Key decisions

| Decision | Options | Choose … when | Trade-off |
| --- | --- | --- | --- |
| How a write becomes idempotent | natural (unique business key, upsert, conditional state transition) / client idempotency key / server-generated token issued before the write | Natural when the entity has a stable business identity (order per cart, payment per invoice); client key for create-style POSTs with side effects; server token for flows where clients cannot generate keys reliably | Natural is cheapest but needs a real business key; keys need storage, TTL and in-progress handling; tokens add a round-trip |
| Where idempotency records live | same DB/transaction as the business write / Redis / separate store | Same DB whenever possible — record and effect commit atomically; Redis only for non-critical dedup or where effect is itself idempotent | Same-DB adds rows and vacuum load; Redis can lose keys on failover/eviction and is not atomic with the DB write |
| How DB state and events stay in sync | transactional outbox + relay / CDC from WAL (Debezium) / listen-to-yourself (consume own event to update DB) | Outbox for explicit domain events with a stable schema; CDC when many tables or legacy code must emit changes without code changes; listen-to-yourself when the event is the source of truth (event sourcing) | Outbox needs a relay and cleanup; CDC couples consumers to table schemas unless combined with an outbox table; listen-to-yourself makes the write path async |
| Cross-service business transaction | single service owns it (redraw boundaries) / orchestrated saga / choreographed saga / 2PC/XA | Redraw boundaries first; orchestration for ≥ 3 steps, branching or need for one place to see state; choreography for 2–3 loosely coupled reactions; 2PC only inside one vendor's system that supports it natively | Sagas give up isolation (need semantic locks/countermeasures); orchestration adds a coordinator; choreography hides the flow; 2PC blocks on coordinator failure |
| Consistency promised to readers | strong (linearizable) / read-your-writes / monotonic reads / bounded staleness / eventual | Strong for balances, inventory decisions, auth changes; read-your-writes for any UI that shows what the user just changed; eventual for feeds, search, analytics | Stronger reads go to the primary or wait for replication, costing latency and scale |
| Ordering scope | none / per-entity (partition key = entity ID) / global | Per-entity covers almost every business need; global only for small, single-partition streams | Global ordering caps throughput at one consumer; per-entity needs a key on every message and versioned updates |
| How drift is detected | none / periodic reconciliation against source of truth / continuous checks (invariants, sums) | Reconciliation whenever money, inventory or a third-party system of record is involved | Reconciliation is extra code and queries but is the only control that catches unknown bugs |
| Money representation | mutable balance column / double-entry ledger with immutable entries, balance derived or cached | Ledger whenever real money, credits or quotas are involved and audit matters | Ledger needs more rows and a balance projection; mutable balance cannot explain itself |

## Best practices

`IDEM-BP-1` — **Require a stable operation identity for retriable side effects.** Use a client key or a natural business key enforced durably; a header is not mandatory when equivalent natural idempotency exists. Scope keys by authenticated tenant/caller and operation; persist this scope in the unique key and every lookup.

`IDEM-BP-2` — **Commit local idempotency state and the local effect atomically.** Store operation scope, request fingerprint and final result with the business write in one transaction. Replays return the documented original outcome; mismatched payloads are rejected. External effects cannot join this transaction: use persisted intent and recovery (IDEM-BP-13).

`IDEM-BP-3` — **Same key with a different payload is a client error.** Why: silently returning the first result for a different request hides client bugs, and re-executing breaks the guarantee. How: fingerprint mismatch → `422 Unprocessable Content` with a clear error code; never overwrite the record.

`IDEM-BP-4` — **Specify how concurrent attempts and abandoned work are resolved.** With a single DB transaction, a conflicting insert may wait for the other transaction; it cannot inspect an uncommitted in-progress row. Bound the wait, then replay the committed result or retry after a known rollback. A separately committed claim/state machine needs owner identity, lease recovery and fencing/conditional transitions; lease expiry alone does not prove the old effect stopped. See PostgreSQL isolation in sources.md.

`IDEM-BP-5` — **Set key TTL longer than the longest client retry window.** Why: a key that expires before the last retry lets a duplicate through. How: TTL ≥ max client retry horizon including queued/offline clients — typically 24h, 7 days for mobile/offline sync or batch importers; purge with a scheduled delete in batches; document the window in the API contract.

`IDEM-BP-6` — **Prefer natural idempotency enforced by the database.** Why: constraints hold across every code path, replica and retry; app checks do not (CONC). How: unique constraints on business keys (`UNIQUE(order_id)` on payments, `UNIQUE(source, external_id)` on imports); `INSERT … ON CONFLICT DO NOTHING/UPDATE`; state transitions as conditional updates (`UPDATE orders SET status='paid' WHERE id=$1 AND status='pending'`); `PUT` with full representation; absolute sets (`SET qty = 5`) instead of deltas where the domain allows.

`IDEM-BP-7` — **Deduplicate the effect atomically at its owner.** An inbox unique on `(consumer, event_id)` and the local business effect commit together; acknowledge only after durable success. A natural unique business key or provably idempotent state transition also works. Event IDs cover republishing; stream identity + topic/partition/offset covers replay of the same Kafka record only. Retention must cover the actual replay horizon, including operator redrive. External effects require IDEM-BP-13.

`IDEM-BP-8` — **Use an outbox when a DB change and downstream business event must both survive.** Insert event ID, aggregate ID, aggregate sequence and payload in the business transaction. The relay publishes at least once and marks sent only after acknowledgement; consumers deduplicate. If order matters, serialize relay publication per aggregate/ordered lane or enforce sequence/gap handling at the consumer. `SKIP LOCKED` plus a partition key does not prevent two relays publishing version 2 before 1. Test crashes around publish/mark-sent, concurrent relays and recovery. Monitor oldest pending age and clean up safely.

`IDEM-BP-9` — **Run CDC as a production system, not a side script.** Why: a stalled Debezium connector holds the Postgres replication slot and WAL grows until the disk fills; schema changes break consumers. How: monitor slot lag (`pg_replication_slots`, `confirmed_flush_lsn`) with an alert; set `max_slot_wal_keep_size`; heartbeat table for low-traffic DBs; publish from an outbox table rather than raw tables to decouple schema; plan snapshot/re-snapshot procedures.

`IDEM-BP-10` — **Model distributed workflows as persisted state machines with explicit failure recovery.** Define forward steps, compensations where meaningful, idempotent retries, timeouts and stuck-flow handling. Place irreversible actions after avoidable failure points where possible; later failures still need forward recovery or manual resolution. A saga does not supply isolation (IDEM-BP-11). Choose a durable engine or orchestrator/outbox from requirements, not step count.

`IDEM-BP-11` — **Compensate for the lack of isolation in sagas with semantic locks and commutative updates.** Why: other transactions see intermediate states (dirty reads, lost updates across steps). How: pending states (`order.status='APPROVAL_PENDING'`, `reservation.status='HELD'` with expiry) that other flows respect; commutative operations (debit/credit entries instead of overwrite); re-read and re-validate values before the pivot step.

`IDEM-BP-12` — **Reuse a persisted operation identity at external providers.** Derive the provider key from the durable operation, not the retry attempt; honor the provider/API version's replay semantics and retention. A provider without idempotency or lookup cannot promise exactly-once side effects across unknown outcomes; document duplicate-versus-loss trade-offs and escalation/reconciliation. See sources.md for verified Stripe API distinctions.

`IDEM-BP-13` — **Persist intent and distinguish three outcomes.** Known not applied: retry the same logical operation after a proved rollback/rejection. Confirmed applied: replay/reconcile its result. Unknown (timeout, disconnected commit or ambiguous 5xx): retain identity and pending/unknown state, query authoritative status or safely retry under the provider's idempotency contract. Never clear the identity merely because time elapsed. Test crashes before/after the external effect and before recording its result; recovery jobs must follow the same protocol.

`IDEM-BP-14` — **Define read consistency per flow and prove routing meets it.** For read-your-writes use the authoritative primary or a commit/version token and wait until the replica has applied it. Routing to primary for a fixed time is only a heuristic unless lag is bounded. Primary reads alone do not protect concurrent invariants: use the transaction isolation/constraints in DATA-BP-6 and CONC-BP-8.

`IDEM-BP-15` — **Distinguish replaceable snapshots from ordered deltas.** A full state snapshot may replace an older version with `WHERE version < incoming_version`. Noncommutative deltas/transitions require the expected predecessor, gap detection and buffer/refetch/recovery; skipping version 1 to apply delta 2 can lose effects. Partition keys preserve broker order within the configured partition, not application causality or parallel relay order. Test reordered input and partition/routing changes.

`IDEM-BP-16` — **Reconcile every system of record you depend on.** Why: bugs, partial failures and provider-side changes cause drift no other control detects. How: scheduled job compares your state with the source of truth (provider settlement reports, ledger sums vs balances, orders vs payments) over a sliding window (e.g. daily over last 3 days); mismatches create tickets or automatic fixes with an audit trail; metric `reconciliation_mismatches` with an alert on > 0 for money.

`IDEM-BP-17` — **Use an immutable ledger when this system owns balances requiring reconstruction.** Double-entry entries, reversals and reconciliation support financial accounting; enforce balanced postings and update any balance projection atomically. Store exact amounts and currency (integer minor units or decimal), never binary float arithmetic for monetary calculations. Product prices and provider-owned payment statuses do not alone require an internal double-entry ledger.

`IDEM-BP-18` — **Treat "exactly-once" as effectively-once: at-least-once delivery + idempotent effect.** Why: no network protocol delivers exactly once to an external side effect; vendor "exactly-once" (Kafka EOS) only covers read-process-write within that broker. How: design every effect for duplicates (IDEM-BP-6/7); use Kafka transactions only for Kafka→Kafka pipelines and still dedup at sinks that are DBs or APIs.

`IDEM-BP-19` — **Carry causality metadata on events.** Why: debugging and correct ordering across services need to know what caused what. How: `event_id`, `causation_id` (the event/command that triggered it), `correlation_id` (the whole flow), `occurred_at`, aggregate `version`; use versions or vector-like per-source sequences for ordering, not wall-clock timestamps from different hosts. Trace propagation → OBS.

`IDEM-BP-20` — **Accept webhooks durably and process according to the provider contract.** Verify the signature over the required raw representation (SEC-BP-12). Persist event identity, payload and pending work before acknowledging; a stored ID alone is not recoverable work. Apply business effects and completion markers atomically (IDEM-BP-7), with retry/recovery. For unordered delivery use authoritative refetch or version/transition rules (IDEM-BP-15). Verify the provider/API version retry and ordering guarantees instead of assuming all providers retry for days.

`IDEM-BP-21` — **Model long-running workflows as explicit state machines and check liveness.** Why: rules that are each correct can combine into a state nobody may leave — a waiting state whose only actor is refused after another actor's step, or a gate requiring input that no one may still provide — silently blocking downstream steps such as closing a period. How: list states, transitions and the actor or job allowed for each; for every non-terminal state name at least one actor or job that can move it forward under the current rules, and the signal (task, notification, dashboard) that reaches them; scenario tests over combinations of rules, not only single transitions; a journaled operator escape hatch.

## Bad practices

`IDEM-BAD-1` — **Idempotency check as `SELECT` then `INSERT` without a unique constraint.** Concurrent duplicates both pass the check. → Instead: unique key + `ON CONFLICT` (IDEM-BP-4, IDEM-BP-6).

`IDEM-BAD-2` — **Committing a completed local dedup marker separately from its local effect.** A crash can leave an effect without its marker or a marker without its effect. Commit them together (IDEM-BP-2/7). A persisted external-operation intent is deliberately separate and must remain pending/unknown until recovery establishes its result (IDEM-BP-13); do not mistake that intent for proof of completion.

`IDEM-BAD-3` — **Treating 5xx/timeouts as proof that a key can be released.** An effect or commit may have succeeded despite the error. Apply the three-outcome protocol in IDEM-BP-13. Release/re-execute only after proving no effect and no active attempt; preserve unknown operations for recovery. Error replay is API-specific: Stripe v1 saves executed 500 responses; v2 differs (sources.md).

`IDEM-BAD-4` — **Key TTL of minutes, or keys in Redis with eviction (`allkeys-lru`).** Late retries and evicted keys bypass dedup. → Instead: IDEM-BP-5; durable store or `noeviction`.

`IDEM-BAD-5` — **Server generates the idempotency key per request.** A new key on every retry dedups nothing. → Instead: the caller generates it once per logical operation (IDEM-BP-1).

`IDEM-BAD-6` — **Using transport identity to deduplicate a broader business operation.** Kafka offsets remain stable for a record across consumer rebalances. A stream-scoped topic/partition/offset can deduplicate that record, but a republished event has a new offset; use a stable event/business ID when that failure is in scope. Delivery tags are not durable business IDs. See IDEM-BP-7 and sources.md.

`IDEM-BAD-7` — **Publishing to the broker inside the DB transaction before commit, or after commit without an outbox.** Before: consumers see events for rolled-back data. After: crash loses the event. → Instead: IDEM-BP-8.

`IDEM-BAD-8` — **Third-party call without an idempotency key, or with a fresh key per retry.** Double charges, double SMS. → Instead: IDEM-BP-12.

`IDEM-BAD-9` — **Marking an external operation failed on timeout.** It may have succeeded; the customer is charged and the order is cancelled. → Instead: IDEM-BP-13.

`IDEM-BAD-10` — **Increment/decrement messages applied without dedup** (`balance += amount` per event). Each redelivery changes state. → Instead: dedup table, or absolute/versioned updates (IDEM-BP-7, IDEM-BP-15).

`IDEM-BAD-11` — **Inexact monetary arithmetic or unexplained balance changes.** Use exact decimal/integer representation. A ledger is appropriate when the system owns balances/settlements needing reconstruction; an ordinary product price or provider-owned payment status does not itself require double-entry bookkeeping. For owned financial balances see IDEM-BP-17.

`IDEM-BAD-12` — **Ordering by `created_at` from different hosts.** Clock skew of tens of ms reorders causally related events. → Instead: per-aggregate versions (IDEM-BP-15, IDEM-BP-19).

`IDEM-BAD-13` — **Reading from a replica to validate a write** (check balance or uniqueness on a lagging replica). Decisions on stale data. → Instead: IDEM-BP-14.

`IDEM-BAD-14` — **Saga compensation that can fail permanently with no retry or alert.** Partial state is left forever. → Instead: idempotent, retried compensations with a stuck-saga alert (IDEM-BP-10).

`IDEM-BAD-15` — **Idempotency keys looked up globally, not per tenant/caller.** A guessed or reused key from another client replays someone else's stored response — a data leak and a wrong result. → Instead: unique on `(tenant_id, key)` and filter every lookup by the authenticated caller (IDEM-BP-1).

`IDEM-BAD-16` — **Outbox, inbox and idempotency tables never purged.** Unbounded growth, slow relay scans, autovacuum pressure on the hottest write path. → Instead: delete published outbox rows (or partition by day and drop partitions) and expire inbox/key rows after their retention window (IDEM-BP-5, IDEM-BP-7).

## Anti-patterns

`IDEM-AP-1` — **Dual write.** Symptoms: `db.Commit()` followed by `producer.Send()`/`cache.Set()`/`search.Index()`/`http.Post()` in the same handler; "sometimes the event is missing" or "the index has orders that don't exist". Why it hurts: there is no atomicity across two systems; every crash, timeout or deploy between the writes creates permanent divergence. Way out: outbox or CDC for everything downstream of the DB (IDEM-BP-8/9); reconciliation to repair existing drift.

`IDEM-AP-2` — **Distributed transaction via 2PC/XA across services or heterogeneous stores.** Symptoms: XA data sources, `PREPARE TRANSACTION` orchestration in app code, a "transaction coordinator" service. Why it hurts: participants hold locks while waiting for the coordinator; a coordinator crash blocks them indefinitely; most brokers and SaaS APIs cannot participate; availability becomes the product of all participants'. Way out: redraw boundaries so one service owns the invariant; otherwise saga + outbox (IDEM-BP-10).

`IDEM-AP-3` — **Exactly-once by configuration.** Symptoms: design docs claiming "Kafka exactly-once" or "SQS FIFO dedup" means consumers need no idempotency; consumers write to Postgres or call APIs. Why it hurts: guarantees end at the broker boundary (FIFO dedup window is 5 minutes); duplicates reach the DB/API after crashes and rebalances. Way out: IDEM-BP-18 with idempotent sinks.

`IDEM-AP-4` — **Choreography spaghetti.** Symptoms: > 3 services reacting to each other's events to complete one business flow; no component knows the flow's state; cyclic event dependencies; failures discovered by customer support. Why it hurts: no place to see, time out or compensate a stuck flow. Way out: an orchestrator (or durable workflow engine) owning the saga state; keep events for notification, commands for steps.

`IDEM-AP-5` — **Saga without isolation countermeasures.** Symptoms: steps commit final-looking states immediately; other flows act on them (ship before payment confirmed, sell reserved stock). Why it hurts: compensation arrives after others acted on intermediate data — anomalies that cannot be undone. Way out: semantic locks, pending states, pivot step ordering (IDEM-BP-11).

`IDEM-AP-6` — **Idempotency middleware that caches responses in memory/Redis around a non-transactional handler.** Symptoms: generic middleware keyed on header, stores response after handler returns, no in-progress state, no fingerprint. Why it hurts: concurrent duplicates execute twice; crash after effect loses the record; different payloads with same key return wrong data. Way out: key insert as first step of the handler's DB transaction with in-progress/fingerprint handling (IDEM-BP-2/3/4).

`IDEM-AP-7` — **Mutable balance as source of truth.** Symptoms: `accounts.balance` updated by many code paths; no entries table, or an "audit log" written separately; support fixes balances with SQL. Why it hurts: no way to prove or rebuild the number; races and retries corrupt it silently. Way out: introduce a ledger, backfill opening-balance entries, make balance a projection, reconcile (IDEM-BP-16/17).

`IDEM-AP-8` — **Eventual consistency everywhere, by accident.** Symptoms: reads served from replicas, caches and search indexes with no documented staleness bound; users re-submit forms because they don't see their changes; business checks run against projections. Why it hurts: duplicates and wrong decisions that look like random bugs. Way out: classify reads by required guarantee and route accordingly (IDEM-BP-14).

`IDEM-AP-9` — **Compensation by deletion.** Symptoms: saga rollbacks and corrections implemented as `DELETE` or overwriting rows (delete the order, reset the status, zero the balance) instead of recording a reversing fact. Why it hurts: the history needed for audit, reconciliation and support disappears; consumers that already reacted to the original event receive nothing they can act on. Way out: compensations as new records and events (`OrderCancelled`, refund entry, reservation released) with causation IDs (IDEM-BP-17, IDEM-BP-19).

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| IDEM-CHK-1 | Do create/charge endpoints that clients retry accept and enforce an idempotency key? | Grep `Idempotency-Key`, `idempotency`, `X-Request-Id` used as key; list POST routes that create orders/payments/transfers. Fail: money/order-creating POST with no key and no natural unique key. IDEM-BP-1, IDEM-BAD-5. | Critical if money, else High |
| IDEM-CHK-2 | Is the key stored atomically with the effect, unique-constrained, scoped per tenant? | Migrations for `idempotency` table and `UNIQUE (tenant_id, key)`; handler code: key insert inside the same `tx`/`$transaction` as the effect. Fail: Redis-only, separate tx, or select-then-insert. IDEM-BP-2, IDEM-BAD-1, IDEM-BAD-2, IDEM-AP-6. | High |
| IDEM-CHK-3 | Are concurrent attempts, payload conflicts and abandoned work handled? | Inspect unique key/fingerprint, transaction visibility and wait/recovery policy. Test parallel retries and owner crash. A visible in-progress row is not required for a single-transaction design. IDEM-BP-3, IDEM-BP-4. | High |
| IDEM-CHK-4 | Does retention cover replay, and are failed/unknown outcomes distinguished? | Compare client/operator retry horizons with cleanup; inspect ambiguous error recovery and the provider contract. Do not infer safety from HTTP status or impose 24h on every API. IDEM-BP-5, IDEM-BAD-3. | Medium |
| IDEM-CHK-5 | Are business invariants enforced by unique constraints/conditional updates? | Migrations for `UNIQUE` on business keys (external IDs, one-payment-per-order); `ON CONFLICT`; `WHERE status = 'pending'` in transitions. Fail: uniqueness only checked in code. IDEM-BP-6. | High |
| IDEM-CHK-6 | Are consumer effects idempotent over the promised replay scope? | Inspect actual schema constraints and transaction boundaries, not only handler code. Test broker replay and business-event republication separately; record missing schema as unverified. IDEM-BP-7, IDEM-BAD-6. | High |
| IDEM-CHK-7 | Is there any dual write between DB and broker/cache/index/HTTP? | In handlers/services: `Commit()`/`$transaction` followed by `Produce`/`Publish`/`sendMessage`/`queue.add`/`index`/HTTP call; or publish inside tx before commit. Fail: any for business events. IDEM-AP-1, IDEM-BAD-7. | High |
| IDEM-CHK-8 | Is outbox recovery and required ordering correct? | Inspect relay claiming, publish/mark-sent window, per-aggregate serialization or sequence recovery, retention and pending-age alert. Test competing relays publishing the same aggregate. IDEM-BP-8. | High if ordering/loss affects invariants, else Medium |
| IDEM-CHK-9 | Is CDC replication-slot lag bounded and alerted? | Debezium connector config, Postgres `max_slot_wal_keep_size`, alerts on `pg_replication_slots` lag/WAL size, heartbeat config. Fail: no alert (disk-full outage risk). IDEM-BP-9. | High |
| IDEM-CHK-10 | Do multi-service flows have a saga with persisted state, idempotent retried compensations and stuck-flow alerts? | Workflow engine (Temporal/Step Functions) or saga table; compensation handlers per step; timeout/alert on sagas older than SLA. Fail: steps chained by events with no compensation or visibility. IDEM-BP-10, IDEM-BAD-14, IDEM-AP-4. | High |
| IDEM-CHK-11 | Do saga intermediate states block conflicting actions? | Pending/held statuses with expiry; other flows check them; pivot step last. Fail: an irreversible step has no justified recovery path for failures that can follow it. IDEM-BP-11, IDEM-AP-5. | High |
| IDEM-CHK-12 | Is 2PC/XA avoided? | Grep `XA`, `PREPARE TRANSACTION`, `JtaTransactionManager`-style coordinators, "distributed transaction" in docs. Fail: cross-service 2PC on request path. IDEM-AP-2. | Medium |
| IDEM-CHK-13 | Do outgoing side-effect calls carry deterministic idempotency keys and record intent first? | Payment/email/SMS client code: `Idempotency-Key`/`idempotencyKey` option set from a stored ID; status row written before the call; recovery job queries provider for `requested` rows. Fail: no key, random key per attempt, timeout → failed. IDEM-BP-12, IDEM-BP-13, IDEM-BAD-8, IDEM-BAD-9. | Critical if money, else High |
| IDEM-CHK-14 | Are read-consistency needs met (read-your-writes; invariant checks on primary)? | DB routing config (read replica DSNs, Prisma `readReplicas`, pgx pools); which queries in write paths hit replicas; cache reads used for decisions. Fail: invariant check on replica/cache. IDEM-BP-14, IDEM-BAD-13, IDEM-AP-8. | High |
| IDEM-CHK-15 | Are ordering guarantees correct for the event semantics? | Determine snapshot vs delta; inspect producer and relay order, routing changes and consumer sequence predicates. A less-than version check alone does not protect ordered deltas. IDEM-BP-15. | High if invariant violated, else Medium |
| IDEM-CHK-16 | Is there reconciliation against each external system of record? | Scheduled jobs comparing with provider reports/ledger sums; mismatch metric and alert. Fail: none where money or inventory sync with a third party. IDEM-BP-16. | High |
| IDEM-CHK-17 | Are owned financial balances exact and reconstructable? | First establish whether this service owns a ledger/balance or merely prices/provider statuses. Inspect entries, immutable corrections, concurrency control and reconciliation when a ledger is required. Missing ledger is not a finding on a price catalogue. IDEM-BP-17, IDEM-BAD-11. | High; Critical for evidenced severe corruption |
| IDEM-CHK-18 | Do docs or code rely on "exactly-once" without idempotent sinks? | Design docs, Kafka `enable.idempotence`/`transactional.id` with DB sinks, SQS FIFO dedup relied on beyond 5 min. Fail: idempotency omitted because of broker guarantees. IDEM-BP-18, IDEM-AP-3. | High |
| IDEM-CHK-19 | Are incoming webhooks deduplicated and processed order-independently? | Webhook routes (grep `webhook`, `stripe-signature`, `constructEvent`); unique on provider event ID; fast 2xx then async processing; re-fetch of current object state. Fail: synchronous heavy processing, no dedup, or status set straight from event in arrival order. IDEM-BP-20. | High (Critical if it moves money) |
| IDEM-CHK-20 | Are idempotency/outbox/inbox records scoped to the caller and purged on schedule? | Key lookup `WHERE` clauses include tenant/user; cleanup jobs or partition drops for outbox/inbox/key tables; table sizes and dead-tuple counts (`pg_stat_user_tables`). Fail: global key lookup (cross-tenant replay) or unbounded tables. IDEM-BAD-15, IDEM-BAD-16. | Medium (High if cross-tenant) |
| IDEM-CHK-21 | Can every non-terminal workflow state be left, and does no combination of rules strand an item? | Workflow/status enums, transition guards, readiness or "waits on" computations, refusals that apply after another actor's step (submit, lock, freeze, approve), close/finish gates requiring every item to be ready. For each waiting state: who may act, whether that action is still allowed after the preceding steps, and who is told. Fail: a reachable state with no permitted actor or job, recoverable only by a manual reopen. IDEM-BP-21. | Medium (High if it blocks a mandatory deadline or closure) |

## Go / Node.js notes

- **Transactions in code.** Go: pass `pgx.Tx`/`*sql.Tx` explicitly so the key insert, effect and outbox insert share one tx; avoid helpers that open their own connection. Node: Prisma interactive `$transaction(async tx => …)` and Knex/Drizzle transactions — every call inside must use `tx`, not the global client (a common silent dual write).
- **Fingerprints.** Canonicalise JSON before hashing (sorted keys, normalised numbers); Go `encoding/json` on a `map` sorts keys, structs keep field order; in Node use a stable stringify (`safe-stable-stringify`/`fast-json-stable-stringify`), since `JSON.stringify` follows insertion order.
- **Money types.** Go: `int64` minor units or `shopspring/decimal`/`cockroachdb/apd`; scan Postgres `numeric` into a decimal, not `float64`. Node: `bigint` or `decimal.js`/`dinero.js`; `pg` returns `numeric` and `bigint` columns as strings by default — keep them strings/decimals, do not `Number()` them.
- **Outbox/CDC tooling.** Debezium (Kafka Connect or Debezium Server) works for both stacks; Go has `watermill` (with SQL outbox/forwarder), Node has relays built on pg-boss/Graphile Worker or custom `SKIP LOCKED` pollers.
- **Durable sagas.** Temporal and Restate have first-class Go and TypeScript SDKs; workflow code must be deterministic (no `time.Now()`/`Date.now()`/random outside SDK APIs), activities must be idempotent.
- **Provider SDKs.** Configure the installed SDK explicitly: retry defaults vary by SDK, version and client construction. Supply the same persisted operation key for application retries and recovery; verify the provider/API version contract (sources.md).
