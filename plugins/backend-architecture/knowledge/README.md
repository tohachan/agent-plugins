# Knowledge index

Each area is a directory named by its lowercase rule prefix (`IDEM-BP-13` → `knowledge/idem/`) with three files. Read only the file the task needs:

| File | Contents | Read it for |
| --- | --- | --- |
| `decisions.md` | Scope, hand-offs, **Key decisions** table | designing, choosing between options |
| `checks.md` | Scope, **Audit checklist** (`XX-CHK-n`) with evidence/search hints and default severity; index of rules the checklist does not cite | auditing, verifying code against the area |
| `rules.md` | **Best practices** (`XX-BP-n`), **Bad practices** (`XX-BAD-n`, local mistakes), **Anti-patterns** (`XX-AP-n`, structural), Go/Node.js notes | rule bodies — Grep one ID (`` ^`XX-BP-n` ``, `-A 3` for anti-patterns); read whole only for a single-area lookup |

Rule IDs are stable; findings, decisions and risks cite them. `../shared/method.md` governs applicability and evidence: a checklist "Fail" is a hypothesis until those conditions hold. `sources.md` separates verified vendor facts from lookup starting points.

| Prefix / dir | Area | Pull it in when the system has… |
| --- | --- | --- |
| API · `api/` | API design | HTTP/gRPC/GraphQL endpoints, public or internal contracts |
| DATA · `data/` | Data storage & transactions | a database, schema, migrations, transactions |
| CACHE · `cache/` | Caching | Redis/Memcached/in-process caches, CDN, read-heavy paths |
| MSG · `msg/` | Queues & messaging | brokers (Kafka, RabbitMQ, SQS, NATS), background jobs, events |
| CONC · `conc/` | Concurrency | goroutines/workers/event loop, shared state, locks, parallel writes to the same rows |
| IDEM · `idem/` | Idempotency & consistency | retries, payments/orders/inventory, multi-step or cross-service writes |
| RES · `res/` | Resilience | calls to other services or third parties |
| SCALE · `scale/` | Scalability | growth targets, multiple instances, partitioning, hot spots |
| PERF · `perf/` | Performance | latency/throughput goals, slow endpoints, cost concerns |
| SEC · `sec/` | Security | users, auth, secrets, personal data, anything internet-facing |
| OBS · `obs/` | Observability | anything that runs in production |
| ARCH · `arch/` | Architecture styles & boundaries | several modules/services, monolith vs services |
| OPS · `ops/` | Delivery & operations | CI/CD, deploys, config, production migrations, on-call |

**Domain coverage** is derived per target, not stored here: modules, invariants and obligations come from the target's specs, ADRs, contracts, tests, policies and authorization registry (`../shared/method.md`, "Domain pass"). Domain findings take the closest area as primary and use SEC-CHK-21, SEC-CHK-22, SEC-CHK-23, DATA-CHK-21 and IDEM-CHK-21 plus any applicable area rule.

## Aliases

`api`, `rest`, `grpc` → API · `db`, `database`, `sql`, `transactions`, `migrations` → DATA · `cache`, `redis` → CACHE · `queues`, `kafka`, `events`, `jobs`, `очереди` → MSG · `concurrency`, `races`, `locks`, `конкурентность` → CONC · `idempotency`, `consistency`, `saga`, `outbox`, `идемпотентность` → IDEM · `resilience`, `retries`, `timeouts`, `отказоустойчивость` → RES · `scaling`, `sharding`, `масштабирование` → SCALE · `performance`, `optimization`, `latency`, `оптимизация` → PERF · `security`, `auth`, `безопасность` → SEC · `observability`, `logging`, `metrics`, `tracing` → OBS · `architecture`, `microservices`, `monolith`, `ddd` → ARCH · `deploy`, `ci/cd`, `ops`, `config` → OPS · `domain`, `business logic`, `permissions matrix`, `бизнес-логика`, `права` → domain pass + SEC/IDEM/DATA · `all`, `everything`, `всё` → every area + domain pass.

## Symptom → areas

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
