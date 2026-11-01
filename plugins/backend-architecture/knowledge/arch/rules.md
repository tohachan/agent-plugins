# Architecture styles & boundaries — rules

> **Scope:** the macro shape of a system (monolith, modular monolith, microservices, serverless, event-driven), how it is cut (bounded contexts, business capabilities, data ownership), how parts talk (sync vs async, gateway/BFF), the internal structure of one service (layered, hexagonal, clean), coupling, Conway's law, migration (strangler fig) and decision records. **Hands off to:** endpoint and contract design → API; broker semantics, delivery guarantees, event schemas → MSG; sagas, outbox, cross-service consistency → IDEM; timeouts, retries, circuit breakers on inter-service calls → RES; partitioning and horizontal scaling → SCALE; per-service DB schema and migrations → DATA; service-to-service auth → SEC; pipelines and deploy independence mechanics → OPS.

## Best practices

`ARCH-BP-1` — **Start with a modular monolith; extract services only for a concrete, named force.** Premature distribution spends the complexity budget before the domain is understood. How: one deployable with enforced module boundaries; extract a module when one of these is true and written in an ADR: independent scaling profile (e.g. 50× CPU of the rest), different availability/compliance tier, team release contention, or a tech requirement the main stack can't meet.

`ARCH-BP-2` — **Draw boundaries around bounded contexts / business capabilities, not entities or layers.** Entity-shaped services make every use case a multi-service transaction. How: event storming or capability mapping; a context owns a cohesive set of use cases, rules and data (e.g. Checkout, Pricing, Fulfilment); the same real-world thing ("Product") may be modelled differently in each context.

`ARCH-BP-3` — **Keep a ubiquitous language per context and a context map across them.** Shared names with different meanings ("account", "order status") cause silent integration bugs. How: glossary per context in the repo; context map naming each relationship (customer/supplier, conformist, ACL, open-host, published language, partnership) and the upstream/downstream direction.

`ARCH-BP-4` — **Exactly one owner writes each piece of data; others read via API or events.** Shared write access makes schema changes a cross-team negotiation and invariants unenforceable. How: per-service schema and DB credentials (no grants on other schemas); other contexts get data via queries to the owner, subscribed events into local read models, or CDC from the owner's outbox (→ IDEM, MSG).

`ARCH-BP-5` — **Choose transaction boundaries from invariants and ownership.** Aggregates help model consistency, but multiple aggregates in one database may legitimately share an atomic transaction. Do not replace a simple local transaction with eventual consistency to satisfy a modeling rule. When independent stores/owners require distribution, explicitly accept loss of isolation and design recovery (IDEM-BP-10/11). Revisit oversized transactions based on contention and change coupling.

`ARCH-BP-6` — **Choose sync versus async from latency, availability and consistency needs.** Keep required immediate answers synchronous when their measured budgets fit. Propagate facts asynchronously when decoupling is valuable and lag/recovery are acceptable; use IDEM-BP-8 for durable publication. Hop count is a lead, not a defect or universal cutoff.

`ARCH-BP-7` — **See RES-BP-1, RES-BP-12 (canonical mechanism).** For each remote dependency state which user operation fails or degrades and why that meets its requirement.

`ARCH-BP-8` — **Make module and service APIs explicit, small and versioned.** Implicit coupling via internals spreads changes everywhere. How: in a monolith, one public package/entrypoint per module (`internal/` in Go, `exports` in package.json or an index barrel per module in Node) and lint rules forbidding deep imports; between services, contracts in OpenAPI/protobuf/AsyncAPI with compatibility checks (→ API).

`ARCH-BP-9` — **Separate business rules from transport where reuse and testing warrant it.** Keep one owner for invariants across handlers/consumers. Ports/adapters can isolate external dependencies in rich domains; a transaction script is valid for small CRUD flows. Do not require interfaces, DTO layers or an ORM-independent domain model without a concrete benefit (ARCH-BP-10).

`ARCH-BP-10` — **Add abstraction only where variation or testability is real.** Ports for every table and DTO-to-entity-to-model mapping in a CRUD service triple the code with no benefit. How: one interface per external dependency the domain uses, not per class; interfaces defined by the consumer; skip the domain layer entirely for pure CRUD contexts (transaction script is a legitimate choice).

`ARCH-BP-11` — **Use an API gateway for edge concerns only; use a BFF owned by the client team for client-specific composition.** Gateways that accumulate business rules become a shared bottleneck. How: gateway = TLS, authn/token validation, rate limiting, routing, request size limits; BFF = aggregation and shaping for one client; no domain rules in either.

`ARCH-BP-12` — **Protect your model with an anti-corruption layer at legacy and third-party boundaries.** Foreign models leak their quirks into your domain and lock you to their changes. How: a translating adapter (`stripeadapter`, `legacyerp`) that maps their types to yours; nothing outside it imports the vendor SDK types.

`ARCH-BP-13` — **Align team ownership with boundaries (Conway's law, used on purpose).** Systems mirror the communication structure of the org; a service owned by three teams turns into three fiefdoms. How: one team owns one or more contexts end-to-end (code, data, on-call); CODEOWNERS reflects it; if the desired architecture conflicts with team layout, change the team layout (inverse Conway manoeuvre).

`ARCH-BP-14` — **Keep services independently deployable and testable.** If two services must ship together, they are one service with a network in the middle. How: backward-compatible contract changes, consumer-driven contract tests (Pact, buf breaking), no shared release train; a service's test suite runs without spinning up its peers (stubs/contracts).

`ARCH-BP-15` — **Migrate with the strangler fig, one capability at a time.** Big-bang rewrites stall for years and lose behaviour nobody documented. How: put a routing facade (gateway/proxy) in front of the legacy system; move one capability, route its traffic to the new service, keep data in sync via CDC/events during transition, delete the legacy path; measure progress as % of routes/traffic moved.

`ARCH-BP-16` — **Record significant decisions as ADRs next to the code.** Without context, future teams undo good decisions or keep bad ones out of fear. How: `docs/adr/NNNN-title.md` with context, decision, alternatives, consequences, status; supersede, don't rewrite; link ADRs from design docs and PRs.

`ARCH-BP-17` — **Size services by cohesion and team cognitive load, not lines of code.** Too-small services push complexity into the network; too-large ones block teams. How: a service should be ownable by one team (≈ 5–9 people) and usually covers one bounded context; merging two services that always change together is as valid as splitting.

`ARCH-BP-18` — **Choose serverless for event-driven, bursty, short work and keep functions coarse.** One function per endpoint explodes deployment units and cold starts. How: a function per bounded context or per trigger type; keep handlers < 15 min (Lambda limit), stateless, with connection pooling via proxies (RDS Proxy) and provisioned concurrency for latency-critical paths.

`ARCH-BP-19` — **In event-driven designs, distinguish commands from events and own their schemas.** Mixing them hides who is responsible for the outcome. How: commands are addressed to one owner and may be rejected ("ReserveStock"); events are facts in past tense published by the owner ("StockReserved"); the publisher owns and versions the event schema in a registry (→ MSG).

`ARCH-BP-20` — **Pick the runtime per service by workload, not fashion, and cap the number of stacks.** Each extra language multiplies tooling, libraries and on-call knowledge. How: Go for CPU-bound, high-concurrency, latency-sensitive or infra-like services; Node.js/TypeScript for I/O-bound APIs, BFFs and teams sharing code with the frontend; at most 2–3 sanctioned stacks with golden-path templates.

## Bad practices

`ARCH-BAD-1` — **Reading or writing another service's tables directly.** Silent coupling: the owner's schema change breaks you in production. → Instead: API, events or CDC from the owner (ARCH-BP-4).

`ARCH-BAD-2` — **Cross-module imports of internals in a monolith.** Module boundaries erode until the monolith is a big ball of mud. → Instead: public module API + import lint rules (ARCH-BP-8).

`ARCH-BAD-3` — **Sharing a "common" library that contains domain models.** Every service redeploys when the shared `Order` struct changes; contexts lose their own models. → Instead: share only technical libs (logging, auth middleware); each context owns its types, contracts are generated from schemas (ARCH-BP-2, ARCH-BP-8).

`ARCH-BAD-4` — **A synchronous chain that violates its end-to-end budget.** Trace latency, failure propagation and correlation across dependencies. More than three hops prompts inspection, not automatic High. Fix the demonstrated bottleneck/coupling; async introduces its own consistency and recovery cost. See ARCH-BP-6.

`ARCH-BAD-5` — **Domain logic in HTTP handlers or ORM models.** Rules duplicated across REST, gRPC and consumers; untestable without a DB. → Instead: use-case functions behind handlers (ARCH-BP-9).

`ARCH-BAD-6` — **Interface for every struct/class "for testability".** Indirection without variation; navigation and refactoring get harder, mocks test mocks. → Instead: interfaces only at real boundaries, defined by the consumer (ARCH-BP-10).

`ARCH-BAD-7` — **Vendor SDK types (Stripe, AWS, legacy ERP DTOs) in domain code.** Swapping or upgrading the vendor touches the whole codebase. → Instead: anti-corruption adapter (ARCH-BP-12).

`ARCH-BAD-8` — **Business rules in the API gateway or BFF.** A second place to change rules, owned by another team, untested with the domain. → Instead: edge concerns only (ARCH-BP-11).

`ARCH-BAD-9` — **See IDEM-AP-2 (canonical mechanism).** Evaluate coordinator/participant failure and actual support before choosing cross-service transactions.

`ARCH-BAD-10` — **Events that are thin CRUD notifications (`OrderUpdated` with no meaning).** Consumers can't tell what happened and must call back, recreating sync coupling. → Instead: intent-revealing domain events with the state consumers need (ARCH-BP-19).

`ARCH-BAD-11` — **Splitting a service without splitting its data.** Two services, one schema: all the cost of distribution, none of the independence. → Instead: move ownership of tables with the code, migrate data before or during extraction (ARCH-BP-4, ARCH-BP-15).

`ARCH-BAD-12` — **See OPS-BP-8 (canonical mechanism).** Demonstrate compatibility across versions; investigate coordinated deploys as evidence of coupling.

`ARCH-BAD-13` — **Decisions only in chat threads or heads.** Rationale lost; teams re-litigate or cargo-cult. → Instead: ADRs (ARCH-BP-16).

`ARCH-BAD-14` — **Service per team member or per sprint.** Ownership spread thin, services orphaned when people move. → Instead: size by context and team (ARCH-BP-13, ARCH-BP-17).

`ARCH-BAD-15` — **Using the same message bus topic as a shared request/response RPC channel for everything.** Hides synchronous coupling behind async plumbing, adds latency and correlation bugs. → Instead: sync calls where an answer is needed, events for facts (ARCH-BP-6, ARCH-BP-19).

`ARCH-BAD-16` — **Services coordinating through shared Redis keys, shared tables or a shared file bucket.** An undocumented contract nobody versions; one side changes a key format and the other silently misbehaves. → Instead: each store has one owner; communicate via API or events (ARCH-BP-4, ARCH-BP-19).

## Anti-patterns

`ARCH-AP-1` — **Distributed monolith.** Symptoms: services must be deployed together or in order; one service's outage takes down most features; shared domain library versions pinned across repos; end-to-end test environment is the only way to test anything. Why it hurts: costs of microservices (network, ops, distributed debugging) with none of the autonomy. Way out: map change-coupling (which repos change in the same PRs/weeks), merge services that always change together, then re-split along contexts with owned data and async integration; or consolidate into a modular monolith.

`ARCH-AP-2` — **Shared database integration.** Symptoms: several services hold credentials to the same schema; triggers or views serve as "APIs"; schema changes need a multi-team meeting; no one knows who writes a column. Why it hurts: invisible coupling, unenforceable invariants, impossible independent scaling, migrations block everyone. Way out: assign an owner per table, revoke foreign write grants first, then reads; replace with API/events/CDC; split schemas, later instances.

`ARCH-AP-3` — **Entity services / anemic CRUD services.** Symptoms: `user-service`, `order-service`, `product-service` exposing `GET/PUT /{entity}`; orchestration of every use case in a gateway or "process" service; business rules scattered across callers. Why it hurts: every feature touches many services; no place enforces invariants; chatty traffic. Way out: regroup by capability (Checkout owns order placement rules, pricing snapshot, reservation); entity data becomes internal state of the owning context.

`ARCH-AP-4` — **Nanoservices.** Symptoms: more services than engineers; services with one endpoint or one function; most code is plumbing (clients, DTOs, configs); deploy pipelines outnumber features. Why it hurts: network overhead and ops cost dominate; reasoning about flows requires tracing across a dozen hops. Way out: merge by cohesion (shared data, changed together) into context-sized services or modules of a monolith.

`ARCH-AP-5` — **Chatty services.** Symptoms: N+1 over HTTP (loop calling `GET /items/{id}`), a page render making 20+ downstream calls, high p99 driven by fan-out. Why it hurts: latency and load multiply; any slow dependency becomes user-visible. Way out: batch endpoints, local read models from events, rethink the boundary if two services need each other's data on every request.

`ARCH-AP-6` — **A module whose coupling blocks required change or isolation.** Symptoms: measured release contention, frequent unrelated change failures, unclear ownership or an excessive blast radius. Table count and centrality alone do not make a small monolith defective. Establish the actual constraint, improve internal boundaries first, and extract only when justified by ARCH-BP-1.

`ARCH-AP-7` — **Premature microservices.** Symptoms: < 10 engineers running 10+ services; boundaries changed several times in the first year; no tracing, per-service on-call, or contract tests. Why it hurts: speed collapses on infrastructure work and cross-service refactors while the domain is still moving. Way out: consolidate into a modular monolith with the same module boundaries; extract again only per ARCH-BP-1 criteria.

`ARCH-AP-8` — **Over-layered "clean" architecture.** Symptoms: controller → service → use case → domain service → repository interface → repository impl → DAO for a CRUD endpoint; 4 near-identical DTOs per entity; mapping code exceeds logic. Why it hurts: slower changes, more bugs in mapping, no testability gain. Way out: collapse layers where nothing varies; keep ports only at true I/O boundaries (ARCH-BP-10).

`ARCH-AP-9` — **Event spaghetti (choreography without a map).** Symptoms: a business process emerges from 10+ services reacting to each other's events; nobody can say which events complete an order; cyclical event chains. Why it hurts: invisible workflows, hard-to-debug stalls, accidental loops. Way out: document flows (event catalogue, AsyncAPI); use an explicit orchestrator (workflow engine such as Temporal, or a process manager service) for long multi-step processes (→ IDEM sagas).

## Go / Node.js notes

- **Module enforcement:** Go's `internal/` directories give compiler-enforced boundaries for free — a modular monolith can use `internal/<context>/` with a small exported API per context, plus `depguard`/`go-arch-lint` for rules between siblings. Node has no built-in equivalent: rely on package.json `exports` in a workspace monorepo (pnpm/npm workspaces, Nx, Turborepo) and lint rules (`eslint-plugin-boundaries`, `dependency-cruiser`); otherwise relative deep imports erode boundaries quickly.
- **Interfaces:** Go interfaces are implicit and idiomatically declared by the consumer, which makes ports cheap and small ("accept interfaces, return structs"); don't pre-declare a provider-side interface for each struct. In TypeScript, interfaces vanish at runtime, so DI containers (NestJS, InversifyJS) rely on tokens/decorators; plain constructor injection in a composition root is usually enough and keeps hexagonal structure without framework magic.
- **Frameworks shape architecture:** NestJS imposes modules/controllers/providers — good for consistency, but its module system is not a boundary enforcer (any module can import another's provider if exported). Go has no dominant framework; structure comes from package layout, so audit directory conventions (`cmd/`, `internal/<context>/{app,domain,adapters}`) rather than framework usage.
- **Choosing the runtime per service:** Go wins for CPU-heavy work, high fan-out concurrency, low memory per instance (~10–30 MB baseline), single static binaries and fast cold starts for serverless; Node wins for I/O-bound JSON APIs, BFFs/GraphQL gateways, SSR alongside frontend teams and code sharing with TypeScript clients. CPU-bound code in Node blocks the event loop for every request on that process (worker threads or a Go service instead).
- **Serverless:** Measure cold starts using the chosen runtime, architecture, bundle, initialization and concurrency settings. For DB access budget connections across concurrent invocations; use a proxy/data API when the measured connection budget requires it, not merely because the runtime is serverless.
- **Monorepo builds:** in Go, a single module with many `cmd/` binaries builds fast and keeps shared types in sync — which also makes accidental shared domain types easy; in Node workspaces, check that each service's dependency graph only includes allowed packages (Nx project graph, `turbo` filters).
- **ORM pulls boundaries together:** a single Prisma schema/client or TypeORM `DataSource` shared by all Node modules makes cross-module joins and writes one line away; give each module its own schema (Postgres schema per module) and repository layer, and lint against importing another module's models. In Go, `sqlc` per module with its own queries directory gives the same separation.
- **Inter-service RPC:** Go has first-class gRPC (`grpc-go`) and Connect (`connectrpc.com/connect`) with generated clients/servers from `.proto`; Node uses `@grpc/grpc-js` or Connect-ES, workable but less common — TS shops often choose OpenAPI-generated clients or tRPC (only for TS-to-TS, which couples both sides to one language).
- **Workflows:** Temporal SDKs exist for both; TS workflow code runs in a deterministic sandbox (no direct I/O, `Date`/`Math.random` replaced), Go workflows rely on discipline and the `workflowcheck` linter — either way, orchestration code must be deterministic, so audit for I/O inside workflow functions.
- **Strangler facades:** Go is a common choice for the routing proxy itself (`httputil.ReverseProxy`, Envoy/Caddy plugins) because of low overhead; in Node, `http-proxy-middleware`/Fastify `@fastify/http-proxy` work but put the event loop on the critical path of all legacy traffic — prefer a dedicated gateway for high RPS.
