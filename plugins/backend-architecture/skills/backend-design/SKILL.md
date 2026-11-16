---
name: backend-design
description: Design a backend system, service or multi-component feature from requirements — new architecture, capacity and trade-offs across several areas, system-design practice, Russian requests such as "спроектируй сервис". Produces requirements arithmetic, an assumptions registry, decisions with trade-offs and a validation plan; no scorecard or readiness verdict. Not for a single pattern question over 1–3 areas ("как сделать идемпотентные вебхуки?", outbox vs CDC, caching choice) — that is backend-rules, which offers to continue here — and not for assessing an existing implementation (backend-audit).
argument-hint: "[system or feature, constraints] [--prior <report.json>]"
model: opus
effort: medium
---

# Backend design

Plugin files live under `${CLAUDE_PLUGIN_ROOT}` (the plugin root, two levels above this skill directory); every `knowledge/`, `shared/` and `scripts/` path below is under it, never in the target repository. Read `${CLAUDE_PLUGIN_ROOT}/knowledge/README.md` and `${CLAUDE_PLUGIN_ROOT}/shared/method.md` once; the design section of `${CLAUDE_PLUGIN_ROOT}/shared/report.md` when writing the report.

## 1. Frame

A request that is only a pattern question over 1–3 areas belongs to `backend-rules`; stay here when the user wants a design (several components, capacity, rollout, validation plan) or explicitly asks for a design document.

Extract, marking assumptions and continuing independent work: actors, core flows and invariants; latency/availability, consistency and data-loss tolerance; average/peak traffic, volume and growth; trust boundaries and sensitive data; existing stack, team, budget, deadline. Ask a small batch of decision-changing questions, usually at most three.

Show the arithmetic that affects choices (RPS, fan-out, storage, connections, recovery capacity), with ranges for uncertain inputs and the point where the choice changes. Estimated capacity is not measured capacity.

Every input the design leans on that the requirements do not state goes into the **assumptions registry**: the assumption, the threshold at which the choice changes, and how to check it.

**Prior (optional): `prior: <report.json>` / `--prior`.** An audit of the system being redesigned (`${CLAUDE_PLUGIN_ROOT}/shared/method.md`, "Prior report"). Its non-Info F-n become requirements, keeping their `fingerprint`; each D-n names the F-n it closes (`closes`) and carries `migration` and `rollback` steps; a requirement no decision closes is stated as open. A prior that is itself a design is not accepted. Read the audit's findings as claims, not as the whole requirement set.

Read `${CLAUDE_PLUGIN_ROOT}/shared/domain-audit.md` **only** when the requirements name privileged roles, money movement, approvals or retention/deletion obligations; derive the domain invariants it asks about from those requirements and the project's own specs, ADRs and policies, and record them as assumptions and decisions. Without such requirements do not invent roles, separation of duties or retention rules.

## 2. Decide

Consider every indexed area; read `${CLAUDE_PLUGIN_ROOT}/knowledge/<prefix>/decisions.md` for the relevant ones. Typically start with ARCH/DATA/API; add IDEM/MSG/CONC for writes and async work, RES for dependencies, SEC for trust crossings, OBS/OPS for production, CACHE/PERF/SCALE when requirements warrant. Look up rule bodies by Grep on their ID only where a choice or failure scenario depends on them; apply the method's mechanism boundaries.

Choose the simplest design meeting the requirements; every extra component states its benefit and operational cost. Record alternatives, accepted trade-offs and measurable revisit triggers. Make ownership, transaction boundaries, ordering, duplicate handling and unknown external outcomes explicit. Sketch in the project's language; Go when none is given.

## 3. Challenge and validate

Walk the scenarios that apply to the design: slow/down dependency; duplicate or out-of-order event; client retry; crash between durable steps; peak/hot tenant; mixed-version deploy; leaked credential; restore after loss. Add the role, approval and retention scenarios only when the requirements brought them in. Apply relevant checks from `checks.md` as hypotheses, not pattern mandates. This is your own review of your own proposal: say what it cannot prove, and name what an independent reader or a run would have to confirm.

Build the method's traceability table for critical promises, with states/transitions and recovery for nontrivial flows, abuse scenarios for trust crossings, capacity measurements still needed, and migration/reconciliation/rollback gates. Fix contradictions and cheap risks; record residual risks, and never invent one to fill a template. Mark each proposed test `planned` until you have run it.

## 4. Report

Follow the design layout in `${CLAUDE_PLUGIN_ROOT}/shared/report.md` (schema 3.0): requirements and arithmetic, the assumptions registry, a Mermaid architecture/flow diagram, D-n decisions with rule IDs, alternatives and revisit conditions, failure scenarios, R-n residual risks, rollout and V-n validation. The closing JSON is a small hand-off of assumptions, decisions, risks and validation; there is no scorecard, readiness verdict or coverage inventory. A focused pattern design uses the relevant sections only and one concise validation scenario.

Write the narrative sections, render markers and closing JSON, then run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py <draft>` (with a prior: set `provenance.prior`, write `requirements` and add `--prior <the audit>` and the `prior` marker) on a draft kept in a scratch directory (`mktemp -d`; always the plugin's script by this absolute path, whatever the working directory); it validates and fills the assumptions, decisions, risks and validation blocks. Record the model and effort of each role that ran in `provenance.models`. At most 3 runs: if the third still fails, deliver the draft marked `validation failed: <the errors>` and say so. In a repository save to `docs/design/<slug>.md` unless told otherwise (`<slug>` is the system's name lowercased to `[a-z0-9-]`, at most 40 characters; an existing file is never overwritten: add `-2`, `-3`, …), preserving unrelated content; otherwise deliver in the reply.
