---
name: backend-design
description: Design backend systems, services and features from requirements, including pattern choices such as idempotent webhooks, outbox, caching or sharding. Use for new backend architecture, system-design practice and Russian requests such as "спроектируй сервис". Produces trade-offs, validation criteria and the shared scorecard and JSON report. For assessing existing implementations, use backend-audit.
---

# Backend design

Paths below are relative to the plugin root, two levels above this skill directory.
Read `knowledge/README.md`, `shared/assessment-method.md` and `shared/output-format.md` once.

## 1. Frame

Extract the following, marking assumptions and proceeding on independent work:
- actors, core flows and invariants;
- latency/availability, consistency and data-loss tolerance;
- average/peak traffic, volume and growth;
- trust boundaries and sensitive data;
- existing stack, team, budget and deadline.

Ask a small batch of decision-changing questions, usually at most three.

Derive the domain invariants from the requirements and from the project's own specs, ADRs and policies; the skill does not prescribe them. For each privileged role, state what it may do to records tied to the actor themself (target = actor). State which irreversible decisions need a second person, which workflow states must always have an actor able to move them on, and which retention, deletion or delivery obligations apply. These go into `coverage_inventory.invariants` with their source.

Show the arithmetic that affects choices (RPS, fan-out, storage, connections, recovery capacity). Use ranges for uncertain inputs and identify where the choice changes; do not present estimated capacity as measured.

## 2. Decide

Consider all indexed areas; read **Key decisions** for relevant ones and full rules only where a choice or failure scenario depends on them. Typically start with ARCH/DATA/API; add IDEM/MSG/CONC for writes and async work, RES for dependencies, SEC for trust crossings, OBS/OPS for production, and CACHE/PERF/SCALE when requirements warrant them. Follow the shared method's mechanism-boundary rules.

Domain authorization rules are declared once at the policy chokepoint and covered by a role × action × target matrix test (SEC-BP-21). Obligations are implemented on every ingestion path (DATA-BP-21). Workflows are explicit state machines with liveness (IDEM-BP-21).

Choose the simplest design meeting the requirements. Each additional component needs a stated benefit and operational cost. Record alternatives, accepted trade-offs and measurable revisit triggers. Make ownership, transaction boundaries, ordering, duplicate handling and unknown external outcomes explicit. Use the project's language for sketches; default to Go only when no stack is given.

## 3. Challenge and validate

Walk applicable scenarios:
- slow/down dependency;
- duplicate or out-of-order event;
- client retry;
- crash between durable steps;
- peak/hot tenant;
- mixed-version deploy;
- leaked credential;
- restore after loss;
- a privileged actor acting on their own record;
- one person completing an approval chain;
- a workflow item stranded by a combination of rules;
- data past its retention entering through an import or sync.

Apply relevant audit checks as hypotheses, not pattern mandates.

Build the shared requirement → invariant/target → mechanism → experiment → acceptance table for critical promises. Include:
- states/transitions and recovery for nontrivial flows;
- threat/abuse scenarios for trust crossings;
- capacity measurements still needed;
- migration, reconciliation and rollback gates.

Fix contradictions and cheap risks, then record residual risks and unresolved evidence. Label every proposed test as planned until actually run.

## 4. Report

Use the shared report contract (schema 2.1) with:
- architecture/flow Mermaid diagrams for a system design;
- D-n decisions and R-n risks;
- a coverage inventory whose invariants come from the requirements;
- strengths, build/rollout plan and validation criteria.

Always retain header, scorecard and closing JSON. A focused pattern question uses the compact form with only relevant areas and one concise validation scenario. Validate with `python3 scripts/validate_report.py <report>` before delivering.

In a repository save to `docs/design/<slug>.md` unless told otherwise; preserve unrelated existing content. Otherwise deliver in the reply. The design score describes the proposal under its assumptions, not production readiness.
