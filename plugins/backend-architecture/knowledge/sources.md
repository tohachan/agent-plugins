# Sources and applicability

Load only the row relevant to a decision. Stable rule IDs describe mechanisms; product defaults, limits and SDK behavior must match the actual deployment. URLs below are primary sources, not a certification of every statement in an area file.

## Verified facts (2026-11-01)

| Rules / fact | Applicable scope | Source |
| --- | --- | --- |
| IDEM-BAD-3, IDEM-BP-12/13: API v1 replays saved executed responses including 500; API v2 has different recovery/replay behavior | Stripe API version matters; inspect the integration version and provider retention | [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests) |
| IDEM-BP-4: conflict handling and visibility depend on isolation; an uncommitted claim is not generally readable by another transaction | PostgreSQL 18; verify deployed isolation/version | [Transaction isolation](https://www.postgresql.org/docs/18/transaction-iso.html) |
| MSG-BP-1: kafka-go CommitMessages advances a partition to the highest supplied offset, including earlier records | kafka-go v0.4.51 reference; consult installed version | [kafka-go explicit commits](https://pkg.go.dev/github.com/segmentio/kafka-go@v0.4.51#hdr-Explicit_Commits) |
| IDEM-BAD-6: a record offset identifies its position within a partition; rebalance reassigns partition ownership, not record identity | Kafka 4.1 consumer reference | [Kafka consumer offsets](https://kafka.apache.org/41/javadoc/org/apache/kafka/clients/consumer/KafkaConsumer.html) |
| MSG-BP-13: SQS SendMessage supports up to 1 MiB; configured queue limit may be lower | AWS SQS service/API at verification date; integrations may impose lower limits | [SendMessage](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_SendMessage.html) |

Parallel outbox reordering and snapshot-versus-delta handling are protocol reasoning, not vendor defaults: verify them with the concrete failure interleavings in IDEM-BP-8/15.

## Lookup starting points — not yet version-verified

These links help verify a claim when needed. Their presence does not mark the remaining legacy knowledge text as freshly verified.

| Area | Primary reference / what to check |
| --- | --- |
| API | [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110), [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457): method/status/error semantics |
| DATA / IDEM | [PostgreSQL docs](https://www.postgresql.org/docs/): constraints, isolation, DDL and replication for deployed major |
| CACHE | [Redis docs](https://redis.io/docs/latest/): expiry, eviction, persistence and client behavior |
| CONC / PERF | [Go docs](https://go.dev/doc/), [Node docs](https://nodejs.org/api/): runtime/version, context/driver semantics and measured overhead |
| MSG | [Kafka docs](https://kafka.apache.org/documentation/), [RabbitMQ docs](https://www.rabbitmq.com/docs): broker and client version/configuration |
| SEC | [OWASP API Security](https://owasp.org/API-Security/), [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700): threat and protocol applicability |
| OBS | [OpenTelemetry docs](https://opentelemetry.io/docs/), [Prometheus practices](https://prometheus.io/docs/practices/): signal/exporter/backend compatibility |
| OPS / SCALE / RES | [Kubernetes docs](https://kubernetes.io/docs/): probes, scheduling, disruptions, termination and autoscaling for the deployment |
| ARCH | Evaluate boundaries against domain invariants, change coupling, ownership and requirements; no universal team/service/hop threshold. |

When maintaining a changing claim, record rule IDs, exact source, applicable product/version/configuration, checked date and verified fact. If lookup is unavailable, label the assumption and defer any finding that depends on it. Benchmark numbers require workload/hardware assumptions; unsourced throughput and latency numbers in the area files are examples only.
