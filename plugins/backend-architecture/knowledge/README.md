# Knowledge base index

One file per area. Each file has the same sections, in this order:

1. **Scope** — what the area covers and where it hands off to neighbours.
2. **Key decisions** — the questions a design must answer, the options, and when each option wins.
3. **Best practices** (`<PREFIX>-BP-n`) — what to do, why, and how.
4. **Bad practices** (`<PREFIX>-BAD-n`) — a single local mistake (a missing timeout, an unbounded query). Each has a fix.
5. **Anti-patterns** (`<PREFIX>-AP-n`) — a recurring structural solution that looks reasonable but backfires (dual writes, distributed monolith). Each has symptoms, why it hurts, and a way out.
6. **Audit checklist** (`<PREFIX>-CHK-n`) — checks with the evidence that confirms or refutes them, search hints, and the default severity.
7. **Go / Node.js notes** — only what differs between the stacks.

Findings, decisions and risks cite these IDs, so a report can be traced back to a rule. Stable IDs may be short references to a canonical rule in another area; resolve those IDs instead of loading or duplicating entire files.

`../shared/assessment-method.md` governs applicability, evidence and critical mechanism boundaries for all areas. Checklist fail labels are hypotheses until those conditions are established. `sources.md` distinguishes verified vendor facts from lookup starting points; do not treat unsourced defaults or numerical heuristics as acceptance limits.

## Areas

| Area | File | Prefix | Pull it in when the system has… |
| --- | --- | --- | --- |
| API design | `api-design.md` | API | HTTP/gRPC/GraphQL endpoints, public or internal contracts |
| Data storage & transactions | `data-storage.md` | DATA | a database, schema, migrations, transactions |
| Caching | `caching.md` | CACHE | Redis/Memcached/in-process caches, CDN, read-heavy paths |
| Queues & messaging | `messaging.md` | MSG | brokers (Kafka, RabbitMQ, SQS, NATS), background jobs, events |
| Concurrency | `concurrency.md` | CONC | goroutines/workers/event loop, shared state, locks, parallel requests touching the same rows |
| Idempotency & consistency | `idempotency-consistency.md` | IDEM | retries, payments/orders/inventory, multi-step or cross-service writes |
| Resilience | `resilience.md` | RES | calls to other services or third parties, any network dependency |
| Scalability | `scalability.md` | SCALE | growth targets, multiple instances, partitioning, hot spots |
| Performance | `performance.md` | PERF | latency/throughput goals, slow endpoints, cost concerns |
| Security | `security.md` | SEC | users, auth, secrets, personal data, anything internet-facing |
| Observability | `observability.md` | OBS | anything that runs in production |
| Architecture styles & boundaries | `architecture-styles.md` | ARCH | more than one module/service, or a choice between monolith and services |
| Delivery & operations | `delivery-operations.md` | OPS | CI/CD, deploys, config, migrations in production, on-call |

### Domain coverage (derived per target, not an area file)

The 13 areas are cross-cutting. Every audit or design also covers the target's own domain: its modules, the invariants and obligations its specs, ADRs, contracts, tests and policies state, and the privileges its authorization registry declares. The skill does not prescribe domain content; it prescribes how to derive and cover it (`../shared/assessment-method.md`, "Coverage inventory" and "Domain pass"). Domain findings take the closest area as their primary area and use the generic domain checks SEC-CHK-21, SEC-CHK-22, SEC-CHK-23, DATA-CHK-21 and IDEM-CHK-21 together with any area rule that applies.

### Aliases for scoping requests

`api`, `rest`, `grpc` → API · `db`, `database`, `sql`, `transactions`, `migrations` → DATA · `cache`, `redis` → CACHE · `queues`, `kafka`, `events`, `jobs`, `очереди` → MSG · `concurrency`, `races`, `locks`, `конкурентность` → CONC · `idempotency`, `consistency`, `saga`, `outbox`, `идемпотентность` → IDEM · `resilience`, `retries`, `timeouts`, `отказоустойчивость` → RES · `scaling`, `sharding`, `масштабирование` → SCALE · `performance`, `optimization`, `latency`, `оптимизация` → PERF · `security`, `auth`, `безопасность` → SEC · `observability`, `logging`, `metrics`, `tracing` → OBS · `architecture`, `microservices`, `monolith`, `ddd` → ARCH · `deploy`, `ci/cd`, `ops`, `config` → OPS · `domain`, `business logic`, `permissions matrix`, `бизнес-логика`, `права` → domain pass plus SEC/IDEM/DATA · `all`, `everything`, `всё` → every area plus the domain pass.

### Symptom → areas

| Symptom | Start with |
| --- | --- |
| "it's slow" | PERF, DATA, CACHE |
| duplicates, double charges | IDEM, MSG, CONC |
| cascading outages, timeouts | RES, SCALE, OBS |
| lost or out-of-order events | MSG, IDEM |
| "can't deploy without breaking things" | OPS, ARCH, API |
| data leaks, abuse | SEC, API |
| a privileged user changed their own outcome; a rule holds in one screen but not another | domain pass, SEC-CHK-21, SEC-CHK-22 |
| items stuck waiting, a period cannot close | domain pass, IDEM-CHK-21 |
| data kept longer than policy allows | DATA-CHK-21, SEC-CHK-20 |
