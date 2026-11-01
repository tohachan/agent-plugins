---
name: backend-design
description: Design backend systems, services and features from requirements, including pattern choices such as idempotent webhooks, outbox, caching or sharding. Use for new backend architecture, system-design practice and Russian requests such as "спроектируй сервис". Produces trade-offs, validation criteria and the shared scorecard and JSON report. For a quick answer from one area's rules without a report, use backend-rules; for assessing existing implementations, use backend-audit.
argument-hint: "[system or feature, constraints]"
---

# Backend design

Paths are relative to the plugin root, two levels above this skill directory. Read `knowledge/README.md` and `shared/method.md` once; `shared/report.md` when writing the report.

## 1. Frame

Extract, marking assumptions and continuing independent work: actors, core flows and invariants; latency/availability, consistency and data-loss tolerance; average/peak traffic, volume and growth; trust boundaries and sensitive data; existing stack, team, budget, deadline. Ask a small batch of decision-changing questions, usually at most three.

Derive domain invariants from the requirements and the project's own specs, ADRs and policies. For each privileged role state what it may do to records tied to the actor (target = actor); which irreversible decisions need a second person; which workflow states must always have an actor able to move them on; which retention, deletion or delivery obligations apply. Record them in `coverage_inventory.invariants` with their source.

Show the arithmetic that affects choices (RPS, fan-out, storage, connections, recovery capacity), with ranges for uncertain inputs and the point where the choice changes. Estimated capacity is not measured capacity.

## 2. Decide

Consider every indexed area; read `knowledge/<prefix>/decisions.md` for the relevant ones. Typically start with ARCH/DATA/API; add IDEM/MSG/CONC for writes and async work, RES for dependencies, SEC for trust crossings, OBS/OPS for production, CACHE/PERF/SCALE when requirements warrant. Look up rule bodies by Grep on their ID only where a choice or failure scenario depends on them; apply the method's mechanism boundaries.

Domain authorization is declared once at the policy chokepoint and covered by a role × action × target matrix test (SEC-BP-21); obligations hold on every ingestion path (DATA-BP-21); workflows are explicit state machines with liveness (IDEM-BP-21).

Choose the simplest design meeting the requirements; every extra component states its benefit and operational cost. Record alternatives, accepted trade-offs and measurable revisit triggers. Make ownership, transaction boundaries, ordering, duplicate handling and unknown external outcomes explicit. Sketch in the project's language; Go when none is given.

## 3. Challenge and validate

Walk the applicable scenarios: slow/down dependency; duplicate or out-of-order event; client retry; crash between durable steps; peak/hot tenant; mixed-version deploy; leaked credential; restore after loss; a privileged actor acting on their own record; one person completing an approval chain; a workflow item stranded by a combination of rules; data past retention arriving through an import or sync. Apply relevant checks from `checks.md` as hypotheses, not pattern mandates.

Build the method's traceability table for critical promises, with states/transitions and recovery for nontrivial flows, abuse scenarios for trust crossings, capacity measurements still needed, and migration/reconciliation/rollback gates. Fix contradictions and cheap risks; record residual risks and unresolved evidence. Every proposed test is planned until run.

## 4. Report

`shared/report.md` (schema 2.1) with Mermaid architecture/flow diagrams for a system design, D-n decisions, R-n risks, a coverage inventory whose invariants come from the requirements, strengths, build/rollout plan and validation. A focused pattern question uses the compact form: relevant areas only and one concise validation scenario.

Write the narrative sections, render markers and closing JSON, then run `python3 scripts/render_report.py <report>`; it validates and fills tables, risks, decisions and validation. A failing report is not finished. In a repository save to `docs/design/<slug>.md` unless told otherwise, preserving unrelated content; otherwise deliver in the reply. The design score describes the proposal under its assumptions, not production readiness.
