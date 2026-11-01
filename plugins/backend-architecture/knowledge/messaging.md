# Queues & messaging

> **Scope:** brokers and logs (RabbitMQ, SQS/SNS, Kafka, NATS JetStream, Pub/Sub), commands vs events, delivery semantics, acks, retries, DLQs, ordering and partitioning, consumer groups, backpressure, message schemas and payload design, publishing reliably, background and scheduled jobs, lag monitoring, fan-out. **Hands off to:** consumer dedup, idempotency keys, outbox/inbox table design, sagas → IDEM; retry budgets, circuit breakers on downstream calls inside handlers → RES; worker pool sizing and in-process concurrency → CONC; partition count and throughput planning → SCALE; tracing across async hops, alert routing → OBS; webhook delivery contract → API; outbox/jobs tables at the DB level → DATA; broker auth and payload encryption → SEC; service boundaries and event ownership → ARCH.

## Contents
- Key decisions
- Best practices (MSG-BP-1…19)
- Bad practices (MSG-BAD-1…15)
- Anti-patterns (MSG-AP-1…7)
- Audit checklist (MSG-CHK-1…20)
- Go / Node.js notes

## Key decisions

| Decision | Options | Choose … when | Trade-off |
| --- | --- | --- | --- |
| Broker model | queue (RabbitMQ, SQS, NATS core/work-queue) / log (Kafka, Kinesis, Redpanda, JetStream streams, Pulsar) | Queue for task distribution with per-message ack, routing, delays and individual retries; log for event streams with multiple independent consumers, replay, ordering per key and high throughput (100k+ msg/s) | Queues delete on ack (no replay); logs block a partition on a poison message and need consumer-side retry topics |
| Message intent | command (one owner consumes, "do X") / event (fact, "X happened", any number of subscribers) | Command when the sender needs a specific action and owns the outcome; event when the producer must not know consumers | Commands couple to the receiver; events need schema governance and discoverability |
| Delivery guarantee | at-most-once / at-least-once / effectively-once | At-least-once + idempotent consumers as the default; at-most-once for explicitly loss-tolerant flows, including user-requested OTP resend when loss is accepted and duplicate automatic sends are worse; effectively-once via Kafka transactions only for Kafka→Kafka stream processing | At-least-once requires dedup (IDEM); Kafka EOS adds latency and does not cover external side effects |
| Ordering | none / per key (partition / FIFO message group) / global | Per key (order id, account id) when state transitions per entity must apply in order; global almost never (single partition = no parallelism) | Ordering limits parallelism to the number of keys/partitions and makes one bad message block its key |
| Event payload | thin (id + type, consumer calls back) / fat (full state snapshot) / delta (changed fields) | Fat (event-carried state transfer) by default for decoupling and replay; thin for very large or highly sensitive data; delta only with ordered, gap-free delivery | Fat events grow schemas and duplicate data; thin events create callback load and read-your-write races |
| Publishing reliably | direct publish after commit / transactional outbox / CDC from the DB log | Outbox (or CDC) whenever a DB write and a message must both happen; direct publish only for messages with no corresponding state change | Outbox adds a relay and a table to maintain; CDC adds Debezium/connector ops |
| Background jobs | broker + workers / DB-backed job queue (River, pg-boss, graphile-worker, Oban-style) / Redis-backed (BullMQ, Asynq) / workflow engine (Temporal, Step Functions) | DB-backed when jobs are enqueued in the same transaction as business writes and volume is moderate (≤ ~1–5k jobs/s); Redis-backed for high-volume ephemeral jobs; workflow engine for long, multi-step processes with timers and compensation | Redis-backed loses jobs if Redis is not durable; workflow engines add a platform and determinism constraints |
| Schema format | JSON (+ JSON Schema) / Avro / Protobuf with a registry | JSON for low volume and few consumers; Avro/Protobuf + registry (Confluent, Apicurio, Buf BSR) for Kafka with many consumers or long retention | Binary formats need registry ops and codegen; JSON drifts without enforcement |

## Best practices

`MSG-BP-1` — **Acknowledge only durable success, preserving unfinished work.** RabbitMQ manual ack/SQS delete follows committed processing. Kafka commits advance the whole partition: commit only the processed prefix with no earlier unfinished records; completion of offset 3 cannot justify committing unfinished 1/2. Sequential per-partition processing or a completion tracker is required under parallelism. Handle rebalance ownership before committing. See sources.md for kafka-go semantics.

`MSG-BP-2` — **See IDEM-BP-7 (canonical mechanism).** Check durable business effects at the consumer, including schema and downstream API contracts.

`MSG-BP-3` — **See IDEM-BP-8 (canonical mechanism).** For broker publication, verify relay acknowledgement, replay identity and required ordering.

`MSG-BP-4` — **Retry transient failures with exponential backoff and jitter, outside the hot path, with a cap.** Why: immediate requeue spins on a failing dependency and starves other messages. How: classify errors (transient vs permanent); delays e.g. 1 s, 5 s, 30 s, 2 min, 10 min, max 5–10 attempts; SQS: change visibility per attempt; RabbitMQ: delayed retry queues via TTL + DLX or quorum-queue `delivery-limit`; Kafka: retry topics (`orders.retry.1m`, `.10m`) then DLT so the main partition keeps flowing.

`MSG-BP-5` — **Route exhausted and permanently failing messages to a DLQ, alert on it, and support redrive.** Why: without a DLQ poison messages loop forever or are silently dropped. How: SQS redrive policy `maxReceiveCount` 3–10; RabbitMQ `x-dead-letter-exchange`; Kafka DLT with headers for original topic/partition/offset, error, attempt count; alert on DLQ depth > 0 or age; documented redrive tool (SQS `StartMessageMoveTask`) once the bug is fixed; DLQ retention ≥ the main queue's (SQS max 14 days).

`MSG-BP-6` — **Fail fast on poison messages.** Why: an undeserialisable or invalid message retried with backoff wastes the retry budget and, on a log, blocks the partition. How: validate schema on receive; deserialisation/validation errors go straight to DLQ with no retries; catch panics/exceptions per message so one message cannot crash the consumer loop.

`MSG-BP-7` — **Set visibility/ack timeouts above p99 processing time and extend for long work.** Why: a timeout shorter than processing makes the message visible again → concurrent duplicate processing. How: SQS visibility timeout above the measured processing/retry budget, extended by `ChangeMessageVisibility` when needed (Lambda integrations have separate service-specific guidance); Kafka `max.poll.interval.ms` > worst-case batch time (else the consumer is kicked and partitions rebalance); RabbitMQ `consumer_timeout` (default 30 min) > max processing; long jobs → split or use a workflow engine.

`MSG-BP-8` — **Choose partition/message-group keys for the ordering you need, and check for skew.** Why: wrong keys break per-entity ordering; skewed keys create a hot partition that lags while others idle. How: key = aggregate id (`order_id`, `account_id`); SQS FIFO `MessageGroupId` per entity (never one constant group); size partitions for peak consumer parallelism (adding Kafka partitions later remaps keys); monitor per-partition lag.

`MSG-BP-9` — **Bound in-flight work with prefetch/batch limits and pause on overload.** Why: unbounded prefetch pulls thousands of messages into memory and causes long redelivery storms on crash. How: RabbitMQ `basic.qos` prefetch ~10–100 per consumer tuned to processing time; Kafka `max.poll.records`, `fetch.max.bytes`, pause/resume partitions when a downstream is slow; SQS `MaxNumberOfMessages` ≤ 10 with long polling (`WaitTimeSeconds=20`); worker concurrency bounded (CONC) and aligned with downstream limits (DB pool size).

`MSG-BP-10` — **Handle consumer group rebalances safely.** Why: rebalances revoke partitions mid-batch; uncommitted work is redone, committed-but-unfinished work is lost. How: commit processed offsets in the revocation callback; cooperative-sticky assignor (or Kafka 4.x KIP-848 consumer protocol) to avoid stop-the-world rebalances; static membership (`group.instance.id`) for rolling restarts; graceful shutdown that stops polling, drains in-flight, commits, then exits within the pod termination grace period.

`MSG-BP-11` — **Version message schemas and enforce compatibility.** Why: a producer deploy that changes a field breaks every consumer, including ones replaying old data. How: schema registry with BACKWARD or FULL compatibility per subject; additive changes only (new optional fields, defaults); protobuf field numbers never reused; breaking change → new event type/topic (`order.placed.v2`) with dual-publish during migration; consumers ignore unknown fields.

`MSG-BP-12` — **Give every message a standard envelope.** Why: dedup, tracing, debugging and replay need metadata independent of the payload. How: CloudEvents-style attributes — `id` (UUIDv7), `type`, `source`, `time`, `subject`/aggregate id, `specversion`/schema version, `traceparent` (W3C, OBS), `correlation_id`, optional `causation_id`; keep the payload a self-contained fact named in past tense.

`MSG-BP-13` — **Design event payloads for consumers that were not written yet.** Why: thin events trigger callback storms and race the producer's replicas; payloads leaking internal schema couple everyone. How: default to event-carried state (the aggregate snapshot or the business-relevant fields) with an aggregate `version` so consumers can drop stale ones; exclude secrets and minimise PII (SEC); keep messages small (Kafka default max ~1 MB, SQS up to 1 MiB, subject to queue configuration (verified source in sources.md)) — large data goes to object storage with a reference (claim-check).

`MSG-BP-14` — **Make producers durable and explicit about acknowledgement.** Why: fire-and-forget publish loses messages on broker failover or network errors. How: Kafka `acks=all`, `enable.idempotence=true` (default in modern clients), `min.insync.replicas=2` with replication factor 3; RabbitMQ publisher confirms + `mandatory` flag, quorum queues (classic mirrored queues are removed in 4.x), persistent messages; check publish errors and retry with backoff.

`MSG-BP-15` — **Monitor lag by age, not just count, and alert on SLO.** Why: depth alone does not say whether processing is late; a stuck consumer often shows zero errors. How: Kafka consumer lag per partition (offsets and time-lag via Burrow/kafka-lag-exporter or the platform); SQS `ApproximateAgeOfOldestMessage`; RabbitMQ ready/unacked counts and consumer count; alert when oldest-message age exceeds the processing SLO (e.g. > 5 min), when consumers = 0, and on DLQ depth (OBS).

`MSG-BP-16` — **Coordinate scheduled work and tolerate duplicate/missed triggers.** Use one scheduler or durable unique schedule claims, but do not assume the scheduler guarantees exactly-once execution. Jobs must be idempotent; catch up from a durable successful watermark. CronJob concurrency policies control overlap within their scope, not all duplicate side effects.

`MSG-BP-17` — **Give background jobs uniqueness, timeouts, retries and retention.** Why: duplicate enqueues, hung jobs and ever-growing job tables are the common failure modes. How: unique job keys (e.g. `send-invoice:{invoice_id}`); per-job timeout; retry with backoff (MSG-BP-4) and a terminal failed state; prune completed jobs (keep 1–7 days); enqueue in the same DB transaction when the job library is DB-backed (removes the dual write).

`MSG-BP-18` — **Fan out with pub/sub topology, one queue/consumer group per subscriber.** Why: a single shared queue for multiple subscribers makes them compete for messages; per-subscriber retries and DLQs need isolation. How: SNS → SQS per subscriber (with raw delivery and filter policies), RabbitMQ fanout/topic exchange → queue per service, Kafka topic → consumer group per service; each subscriber owns its DLQ and retry policy.

`MSG-BP-19` — **Use asynchronous messaging for request/response only with correlation, timeouts and an async contract.** Why: a caller blocking on a reply queue inherits all broker latency and failure modes with none of the decoupling. How: prefer direct RPC (gRPC/HTTP with RES policies) for synchronous needs; when replies must be async, use `correlation_id` + reply-to, a reply deadline, and expose 202 + status (API-BP-10) instead of holding the HTTP request open.

## Bad practices

`MSG-BAD-1` — **Auto-ack or ack before processing.** Crash after ack loses the message. → Instead: MSG-BP-1.

`MSG-BAD-2` — **Kafka auto-commit with asynchronous processing** (records handed to goroutines/promises, offset committed on next poll). Offsets advance past unprocessed records; a crash loses them. → Instead: commit after processing per partition (MSG-BP-1, MSG-BP-10).

`MSG-BAD-3` — **Publishing inside the DB transaction, or right after commit without an outbox.** Message sent but transaction rolls back (ghost event), or commit succeeds and publish fails (lost event). → Instead: MSG-BP-3.

`MSG-BAD-4` — **Immediate infinite requeue** (`nack(requeue=true)` with no limit, rethrowing in a loop). Hot loop, CPU burn, log floods, other messages starve. → Instead: MSG-BP-4, MSG-BP-5.

`MSG-BAD-5` — **No DLQ, or a DLQ nobody watches.** Failures disappear or accumulate until retention deletes them. → Instead: MSG-BP-5, MSG-BP-15.

`MSG-BAD-6` — **Visibility/ack timeout shorter than processing time.** Same message processed concurrently by two workers; duplicates even with low failure rates. → Instead: MSG-BP-7.

`MSG-BAD-7` — **Single constant partition key or FIFO group** ("orders" for everything). All traffic serialised through one consumer. → Instead: MSG-BP-8.

`MSG-BAD-8` — **Random or missing key where per-entity order matters.** `order.cancelled` processed before `order.created`. → Instead: MSG-BP-8; consumers also check aggregate version (MSG-BP-13).

`MSG-BAD-9` — **Unbounded prefetch/concurrency** (RabbitMQ prefetch 0, `Promise.all` over a whole batch, a goroutine per message). Memory blow-up and downstream overload. → Instead: MSG-BP-9.

`MSG-BAD-10` — **Producer ignores publish errors or callbacks** (`producer.send(...)` not awaited, Go async producer `Errors()` channel never read). Silent loss. → Instead: MSG-BP-14.

`MSG-BAD-11` — **Breaking payload change deployed in place.** Consumers crash or misread; replay of historical data breaks. → Instead: MSG-BP-11.

`MSG-BAD-12` — **Exceptions/panics escape the handler.** One bad message kills the consumer loop; the orchestrator restarts it and it dies on the same message (crash loop). → Instead: MSG-BP-6.

`MSG-BAD-13` — **In-process cron in every replica** (`robfig/cron`, `node-cron`, `setInterval` in the web process). Jobs run N times; stop running during scale-to-zero. → Instead: MSG-BP-16.

`MSG-BAD-14` — **Oversized messages** (full documents, images, large arrays). Broker limits rejected at runtime, slow consumers, memory pressure. → Instead: claim-check (MSG-BP-13).

`MSG-BAD-15` — **No graceful shutdown in consumers.** SIGTERM kills in-flight work; redeliveries on every deploy; Kafka rebalance storms. → Instead: MSG-BP-10.

## Anti-patterns

`MSG-AP-1` — **Request/reply over queues as synchronous RPC.**
- Symptoms: HTTP handler publishes to a queue then blocks on a temporary reply queue; timeouts tuned in seconds; temporary queues per request.
- Why it hurts: latency and failures of RPC plus broker overhead; timeouts leave orphan work that still executes; hard to trace.
- Way out: direct RPC with RES policies for synchronous needs; otherwise make the API async (202 + status, API-BP-10) and let the reply update state (MSG-BP-19).

`MSG-AP-2` — **See IDEM-AP-1 (canonical mechanism).** Inspect the DB/broker commit window and recovery; publishing adjacent to commit does not make the writes atomic.

`MSG-AP-3` — **Event notification that forces callbacks (thin-event storm).**
- Symptoms: events carry only an id; every consumer immediately calls the producer's API; producer load spikes with each event; consumers read stale data from producer replicas.
- Why it hurts: temporal coupling returns; producer availability gates all consumers; fan-out multiplies read load.
- Way out: event-carried state transfer with versioning (MSG-BP-13), or a published read model.

`MSG-AP-4` — **Commands disguised as events (passive-aggressive events).**
- Symptoms: `SendWelcomeEmailRequested`, `ChargeCardEvent` published to a topic that exactly one known service must handle; producer breaks if that consumer misbehaves.
- Why it hurts: hidden coupling — the producer depends on an outcome it pretends not to know; no clear owner for failure.
- Way out: explicit command to the owning service's queue/API with a reply/status, or a real fact event (`UserRegistered`) and let the email service decide.

`MSG-AP-5` — **Distributed monolith via event chains.**
- Symptoms: business process spread across 5–10 services reacting to each other's events with no owner; nobody can answer "where is order X?"; changes ripple across teams.
- Why it hurts: invisible workflow, impossible error handling and compensation, cyclic dependencies.
- Way out: orchestrate long processes explicitly (saga orchestrator or workflow engine, IDEM/ARCH); keep choreography for loosely related reactions.

`MSG-AP-6` — **Broker as database.**
- Symptoms: Kafka topics with infinite retention used as the only system of record and queried by scanning; RabbitMQ queues holding messages for weeks as storage.
- Why it hurts: no queries, no indexes, painful corrections (GDPR erasure, fixing bad data), queues degrade with depth.
- Way out: persist state in a database; use compacted topics only as changelogs with a rebuildable materialised view.

`MSG-AP-7` — **Blocking retries inside the consumer.**
- Symptoms: handler sleeps and retries a downstream call for minutes; partitions stall; visibility timeouts expire and duplicates appear.
- Why it hurts: head-of-line blocking, duplicate processing, rebalances from exceeded poll intervals.
- Way out: short bounded in-handler retries (≤ a few seconds), then delayed retry queues/topics and DLQ (MSG-BP-4).

## Audit checklist

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
| MSG-CHK-1 | Are messages acked/committed only after successful processing? (MSG-BP-1, MSG-BAD-1, MSG-BAD-2) | Go: amqp091 `Consume(…, autoAck true`, `d.Ack` before work; segmentio/kafka-go `ReadMessage` (commits on read with GroupID), franz-go `AutoCommit` with async handoff; Sarama `MarkMessage` before processing. Node: amqplib `noAck: true`; KafkaJS `eachMessage` handing off to un-awaited promises with `autoCommit`; SQS `deleteMessage` before handler. Fail: ack precedes durable success | Critical |
| MSG-CHK-2 | Are consumers idempotent? (MSG-BP-2) | For each handler with side effects (DB writes, payments, emails): dedup table/unique key, conditional update, or idempotency key to downstream. Fail: duplicate delivery produces duplicate effect → see IDEM checks | High (Critical for money) |
| MSG-CHK-3 | Are DB writes and publishes atomic via outbox/CDC? (MSG-BP-3, MSG-BAD-3, MSG-AP-2) | grep `outbox`; find `Publish`/`Produce`/`send(`/`sendMessage` near `Commit`/`$transaction`/`tx.`. Fail: publish adjacent to commit with no outbox, for messages tied to state changes | High |
| MSG-CHK-4 | Do retries back off with a cap, separate from the main flow? (MSG-BP-4, MSG-BAD-4, MSG-AP-7) | `Nack(false, true)`/`nack(msg, false, true)` without limit; `time.Sleep`/`setTimeout` loops in handlers; retry topics/queues in infra; quorum queue `x-delivery-limit`. Fail: unbounded immediate requeue or minute-long in-handler sleeps | High |
| MSG-CHK-5 | Is there a monitored DLQ with a redrive path? (MSG-BP-5, MSG-BAD-5) | Terraform: `redrive_policy`, `maxReceiveCount`; RabbitMQ policies/`x-dead-letter-exchange`; Kafka DLT topic + producer; alerts on DLQ depth; runbook for redrive. Fail: no DLQ or no alert | High |
| MSG-CHK-6 | Are poison messages isolated without killing the consumer? (MSG-BP-6, MSG-BAD-12) | Go: `recover()` per message, unmarshal errors → DLQ; Node: try/catch around per-message handler, `unhandledRejection` behaviour. Test with a malformed message in staging. Fail: crash loop or partition stuck | High |
| MSG-CHK-7 | Do visibility/ack/poll timeouts exceed processing p99? (MSG-BP-7, MSG-BAD-6) | SQS `visibility_timeout_seconds` vs handler p99 (and Lambda timeout: visibility should be ≥ 6× function timeout); Kafka `max.poll.interval.ms` (default 300 s) vs batch time, KafkaJS `sessionTimeout`; RabbitMQ `consumer_timeout`. Fail: timeout < p99 or no heartbeat for long jobs | High |
| MSG-CHK-8 | Are keys chosen for required ordering and free of skew? (MSG-BP-8, MSG-BAD-7, MSG-BAD-8) | Producer key arguments (`Key:`, `key:`, `MessageGroupId`, `routingKey`); per-partition lag/throughput metrics. Fail: constant key, or missing key where state transitions per entity must be ordered | Medium (High if out-of-order corrupts state) |
| MSG-CHK-9 | Is in-flight work bounded? (MSG-BP-9, MSG-BAD-9) | Go: `ch.Qos(` missing or 0, `go handle(msg)` without semaphore/errgroup limit; Node: amqplib `prefetch(` missing, `Promise.all(messages.map(`, KafkaJS `partitionsConsumedConcurrently`; compare concurrency × instances with DB pool (DATA-CHK-6). Fail: unbounded | Medium |
| MSG-CHK-10 | Do consumers shut down gracefully and handle rebalances? (MSG-BP-10, MSG-BAD-15) | Go: `signal.NotifyContext`, consumer `Close()`, drain then commit; Node: `process.on('SIGTERM'` → `consumer.disconnect()`; k8s `terminationGracePeriodSeconds` vs drain time; Kafka `partition.assignment.strategy`, `group.instance.id`. Fail: no SIGTERM handling | Medium |
| MSG-CHK-11 | Are producers durable and errors handled? (MSG-BP-14, MSG-BAD-10) | Kafka `acks` (Sarama `RequiredAcks = WaitForAll`, kafka-go `RequiredAcks: RequireAll`, KafkaJS `acks: -1`), topic `min.insync.replicas`, RF; RabbitMQ `ConfirmSelect`/`createConfirmChannel`, `DeliveryMode: Persistent`, quorum queues; un-awaited `send(`. Fail: fire-and-forget on business events | High |
| MSG-CHK-12 | Are message schemas versioned with enforced compatibility? (MSG-BP-11, MSG-BAD-11) | Schema registry config, `.avsc`/`.proto` in repo, compatibility mode; JSON payloads built ad hoc (`map[string]any`, object literals) without a schema; CI checks. Fail: no schema for events with > 1 consumer | Medium |
| MSG-CHK-13 | Do messages carry an envelope with id, type, version, time and trace context? (MSG-BP-12) | Message structs/headers: `id`, `type`, `traceparent`, `correlation_id`; OpenTelemetry messaging instrumentation. Fail: no unique id (dedup impossible) | Medium |
| MSG-CHK-14 | Are payloads self-sufficient, small and free of secrets? (MSG-BP-13, MSG-AP-3, MSG-BAD-14) | Sample events: id-only events followed by consumer HTTP callbacks; payload sizes vs limits; tokens/PII in payloads. Fail: callback storm risk or secrets in events | Medium |
| MSG-CHK-15 | Is lag monitored by age and alerted? (MSG-BP-15) | Dashboards/alerts: Kafka consumer group lag, SQS `ApproximateAgeOfOldestMessage`, RabbitMQ `messages_ready`, consumer count = 0. Fail: no lag alert on business-critical consumers | High |
| MSG-CHK-16 | Do scheduled jobs run once per tick and catch up safely? (MSG-BP-16, MSG-BAD-13) | Go: `robfig/cron`, `time.NewTicker` in main service; Node: `node-cron`, `cron`, `setInterval`, `agenda`; k8s `CronJob` `concurrencyPolicy`; job uses watermark vs fixed window. Fail: in-process cron with > 1 replica and no leader election/lock | Medium (High if it moves money or sends messages) |
| MSG-CHK-17 | Do background jobs have uniqueness, timeouts, retries, retention? (MSG-BP-17) | Go: River/Asynq options (`UniqueOpts`, `asynq.Unique`, `Timeout`, `MaxRetry`); Node BullMQ `jobId`, `attempts`, `backoff`, `removeOnComplete`, worker `lockDuration`; Redis persistence for Redis-backed queues (CACHE-AP-1). Fail: Redis-backed jobs on a non-durable Redis for business-critical work | Medium (High if job loss loses business actions) |
| MSG-CHK-18 | Is fan-out one queue/group per subscriber? (MSG-BP-18) | Infra: SNS subscriptions, exchanges/bindings, consumer `groupId`/`GroupID` reuse across different services. Fail: two services share a group/queue and split messages | High |
| MSG-CHK-19 | Is request/reply over queues avoided in synchronous paths? (MSG-BP-19, MSG-AP-1) | grep `ReplyTo`, `replyTo`, `correlationId`, exclusive/auto-delete queues created in request handlers. Fail: HTTP handler blocks on broker reply | Medium |
| MSG-CHK-20 | Are commands vs events and process ownership clear? (MSG-AP-4, MSG-AP-5, MSG-AP-6) | Event names (imperative vs past tense), topic catalogue/AsyncAPI docs, chains of handlers across services for one business process; topics with infinite retention used as storage. Fail: no owner for a multi-service process | Medium |

## Go / Node.js notes

- Go consumers scale with goroutines cheaply, but a goroutine per message breaks ordering and offset bookkeeping; use a worker pool per partition or keyed workers, and apply MSG-BP-1 for commit safety across parallel processing. franz-go and confluent-kafka-go are the most complete Kafka clients; segmentio/kafka-go's `ReadMessage` auto-commits, use `FetchMessage` + `CommitMessages` for at-least-once.
- Go RabbitMQ: use `rabbitmq/amqp091-go` (the maintained fork of `streadway/amqp`); it does not reconnect automatically — handle `NotifyClose` and re-declare topology, channels are not safe for concurrent publishing.
- Go job systems: River (Postgres, transactional enqueue with pgx), Asynq (Redis), Temporal Go SDK for workflows. Go `context` cancellation must flow into handlers so shutdown and visibility deadlines are honoured.
- Node is single-threaded: CPU-heavy handlers block heartbeats (KafkaJS session timeouts, BullMQ lock renewal) and trigger rebalances/stalled jobs — move CPU work to worker threads or separate services; tune `lockDuration`/`sessionTimeout` to real processing times.
- For Node Kafka clients (KafkaJS, `@confluentinc/kafka-javascript`, `@platformatic/kafka`), verify current maintenance, supported broker protocol, rebalance behavior and deployment constraints from the installed version and upstream before recommending a migration.
- Node RabbitMQ: `amqplib` lacks automatic reconnection — wrap with `amqp-connection-manager` or `rabbitmq-client`; use confirm channels for publishing. BullMQ requires Redis `maxmemory-policy noeviction` and AOF for job durability.
- Node handlers must `await` the full processing before returning in `eachMessage`/`eachBatch` or the client commits early; for SQS use `sqs-consumer` (deletes only after the handler resolves) or the Lambda event source with `ReportBatchItemFailures` for partial batch failure.
- Both stacks: OpenTelemetry messaging semantic conventions propagate `traceparent` through headers; inject on produce and extract on consume (OBS).
