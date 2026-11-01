# Queues & messaging — rules

> **Scope:** brokers and logs (RabbitMQ, SQS/SNS, Kafka, NATS JetStream, Pub/Sub), commands vs events, delivery semantics, acks, retries, DLQs, ordering and partitioning, consumer groups, backpressure, message schemas and payload design, publishing reliably, background and scheduled jobs, lag monitoring, fan-out. **Hands off to:** consumer dedup, idempotency keys, outbox/inbox table design, sagas → IDEM; retry budgets, circuit breakers on downstream calls inside handlers → RES; worker pool sizing and in-process concurrency → CONC; partition count and throughput planning → SCALE; tracing across async hops, alert routing → OBS; webhook delivery contract → API; outbox/jobs tables at the DB level → DATA; broker auth and payload encryption → SEC; service boundaries and event ownership → ARCH.

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

## Go / Node.js notes

- Go consumers scale with goroutines cheaply, but a goroutine per message breaks ordering and offset bookkeeping; use a worker pool per partition or keyed workers, and apply MSG-BP-1 for commit safety across parallel processing. franz-go and confluent-kafka-go are the most complete Kafka clients; segmentio/kafka-go's `ReadMessage` auto-commits, use `FetchMessage` + `CommitMessages` for at-least-once.
- Go RabbitMQ: use `rabbitmq/amqp091-go` (the maintained fork of `streadway/amqp`); it does not reconnect automatically — handle `NotifyClose` and re-declare topology, channels are not safe for concurrent publishing.
- Go job systems: River (Postgres, transactional enqueue with pgx), Asynq (Redis), Temporal Go SDK for workflows. Go `context` cancellation must flow into handlers so shutdown and visibility deadlines are honoured.
- Node is single-threaded: CPU-heavy handlers block heartbeats (KafkaJS session timeouts, BullMQ lock renewal) and trigger rebalances/stalled jobs — move CPU work to worker threads or separate services; tune `lockDuration`/`sessionTimeout` to real processing times.
- For Node Kafka clients (KafkaJS, `@confluentinc/kafka-javascript`, `@platformatic/kafka`), verify current maintenance, supported broker protocol, rebalance behavior and deployment constraints from the installed version and upstream before recommending a migration.
- Node RabbitMQ: `amqplib` lacks automatic reconnection — wrap with `amqp-connection-manager` or `rabbitmq-client`; use confirm channels for publishing. BullMQ requires Redis `maxmemory-policy noeviction` and AOF for job durability.
- Node handlers must `await` the full processing before returning in `eachMessage`/`eachBatch` or the client commits early; for SQS use `sqs-consumer` (deletes only after the handler resolves) or the Lambda event source with `ReportBatchItemFailures` for partial batch failure.
- Both stacks: OpenTelemetry messaging semantic conventions propagate `traceparent` through headers; inject on produce and extract on consume (OBS).
