# Evidence and coverage method

Governs every area file, including checklist "Fail" labels and default severities. Read once per task.

## Evidence

- Record target revision (commit + dirty state, or document version), environment, artifacts and exclusions; plugin version from `.claude-plugin/plugin.json`. Source code alone is not production verification.
- Ask only questions whose answer changes a material conclusion (missing target, availability, loss tolerance, external controls). Continue independent work; mark assumptions.
- Focused request: findings and scorecard stay in scope. Read adjacent rules only to establish a guarantee; name an essential out-of-scope dependency without auditing it. Still inventory the units inside the scope.
- Start from the highest-impact flows. Trace each: entry/authentication → authorization → state reads → transaction/side effect → publication/ack → recovery; name invariant, owner, trust boundaries and authoritative state. Then use the checklists to find omissions.
- A rule is a hypothesis about a failure: establish applicability, an actual violation and evidence that could refute it. Numbers for team sizes, hops, throughput, timeouts and topology are starting points, not acceptance limits. An alternative mechanism meeting the requirement passes.
- Before calling a control missing, inspect its plausible owners: callers/wrappers, schema constraints, middleware/gateway, infrastructure, provider contract. An unavailable owner is an unknown; absence from a supplied snippet is not system-wide absence.
- When a conclusion depends on a vendor limit, SDK behavior or version, consult `knowledge/sources.md`. Unverified defaults are assumptions, not findings.

## Coverage inventory

Coverage holes hide the findings that matter most, because the reviewed paths are usually the well-built ones. Build the inventory before checking anything and keep it to the end.

1. **Enumerate units** present in scope: entry points (HTTP/RPC operations, GraphQL resolvers, CLI/admin commands, consumers, jobs, schedules); authorization declarations (permission registries, policy tables, roles, route guards); domain modules (packages, services, bounded contexts); stores (tables, collections, buckets, journals); external dependencies; documented obligations (specs, ADRs, contracts, privacy/retention policies, compliance notes). Count them from the project's own artifacts: contracts, route tables, registries, migrations, code-graph exports.
2. **Enumerate, do not sample, whatever is enumerable.** A registry, route table, contract or migration list is finite: walk all of it. Sample only units that cannot be enumerated with the available tools, stating rule, denominator and why.
3. **Exactly one owner pass per unit** (lead or a named reviewer) and a terminal status: `checked`, `sampled` (rule + denominator) or `not_covered` (reason). An unowned unit is a defect of the audit, not of the target; the validator rejects inventories that do not add up.
4. **Two axes.** The 13 areas and the domain modules are both mandatory in a full audit. An area pass does not cover a module's domain rules; a module pass does not cover platform concerns.
5. **Use a code index** when the workspace has one (graphify graph, LSP references, ctags, Sourcegraph) to enumerate writers, callers and entry points. When enumeration is incomplete (no index, budget exhausted), report which unit kinds and how many units remain, and that a deeper pass is possible over an indexed codebase (for example a graphify index). Readiness cannot be `supported_in_scope` while units remain uncovered.

## Domain pass

The skill does not define the target's domain. Derive it from the target's own sources — specs, ADRs, contracts, policies, tests, code comments, the authorization registry — and record each invariant with its source, owner and every entry point that can violate it. For each domain module apply at least:

- **Privilege matrix (SEC-CHK-21).** For every action admitting an elevated role, decide target = actor and targets tied to the actor (records they own or co-own, approvals of their own requests, their own limits, grants or payouts). Prefer a full role × action × target-relation table built from the registry over reading a few handlers.
- **One invariant, every writer (SEC-CHK-22).** A guard found in one module is evidence about that place only. List every other path reaching the same state — bulk, import, batch, CLI, job, admin tool, database policy — and confirm each enforces it.
- **Irreversible decisions (SEC-CHK-23).** Who may prepare, modify, confirm on behalf of others and approve; whether one principal completes the chain; whether the sources require separation. Silent sources produce an owner question, not a finding.
- **Workflow liveness (IDEM-CHK-21).** Every non-terminal state has an actor or job still permitted to move it forward after the preceding steps, and someone is told.
- **Documented obligations (DATA-CHK-21).** Every retention, deletion, consent, audit or delivery obligation has enforcing code on every ingestion path, with predicates that real data reaches.

Area rules still apply inside a domain pass. Record domain invariants with their status in the report's coverage section.

## Check ledger

Keep a compact ledger of selected checks and critical invariants with evidence locations; reuse it across areas. Do not print hundreds of passing rows.

| State | Meaning |
| --- | --- |
| verified | The property holds in the assessed scope, with supporting evidence. |
| violation | Evidence supports a concrete failure scenario; record a finding/risk. |
| unverified | Evidence is missing or a hypothesis is unresolved. |
| not_applicable | A stated reason excludes the check. |

Claim confidence: confirmed = supported by implementation/config/contract or a reproducible result; likely = evidenced path with an explicit unresolved premise; an unsupported suspicion is an open question. High area confidence requires corroborated critical paths and mechanisms, not the number of files read. Keep configured, statically inspected and exercised behavior distinct.

- **Obligations need their source.** A `verified` obligation check (retention, separation of duties, delivery guarantee, audit) cites the obligation's source and the mechanism covering it on every path. A mechanism's existence does not verify the obligation.
- **Split mixed checks.** Record code-verifiable and infrastructure parts separately; missing infrastructure evidence never makes the code part unverified.
- **Challenge every strength.** A strength names the boundary it was tested against: the bypass attempted, other entry points searched, or the rule matrix checked. A policy layer, row-level security or a guard is a strength of the mechanism, not proof its rules are complete; say which rules were checked.
- **Missing implementation ≠ missing evidence.** Check alternative enforcement layers before recording either.

## Mechanism boundaries

When these flows exist, look up the named rules even during a partial read:

- Side effects/retries: IDEM-BAD-3, IDEM-BP-13 — known rollback, completed effect and unknown outcome differ; a timeout is not proof of rollback.
- Outbox/ordered work: IDEM-BP-8, IDEM-BP-15, MSG-BP-1 — partition keys alone do not order parallel publishers; snapshot replacement differs from ordered deltas; commits cannot skip unfinished earlier records.
- Concurrency: DATA-BP-6, CONC-BP-12 — isolation and lease fencing protect different boundaries; neither a lock name nor a transaction keyword proves an invariant.
- Authorization and bounds: SEC-BP-1, SEC-BP-3, RES-BP-1 — follow the complete enforcement path, including schema, gateway and inherited deadlines.
- Domain authorization: SEC-BP-21, SEC-AP-8 — a central policy layer proves the chokepoint exists, not that each role/target decision is right; check the matrix.

## Verification and acceptance

For each critical requirement keep a traceability row (audit: observed; design: proposed):

| Requirement / scenario | Invariant or measurable target | Mechanism / owner | Evidence or experiment | Acceptance / status |
| --- | --- | --- | --- | --- |
| Duplicate webhook, concurrent retry and worker crash | One business effect per provider operation | Durable inbox and atomic state update | Inject crashes before/after each durable step; replay concurrently | One effect after recovery; planned, not executed |

Use existing tests, contracts, traces and measurements. Run targeted checks when feasible and authorized; otherwise specify the experiment and label it unexecuted. For unknown external outcomes test recovery, not only the happy-path retry. Capacity claims need representative data, saturation and peak/failure scenarios; estimates are not benchmarks. For security name actors, assets, trust crossings and abuse paths before choosing controls. For consequential design choices compare the simplest viable option against alternatives, vary uncertain load/budget inputs to find the decision threshold, and document rollout compatibility, migration reconciliation and rollback acceptance where persistent state changes.

## Judgement and reading economy

- One root cause → one item with a primary area and all relevant rule IDs. Scoring lives in `shared/report.md` only.
- **Conditional severity.** When severity depends on a pending configuration, rollout or growth event (feature flag, pilot allowlist, second tenant), report the current severity plus `severity_if` and `trigger`, and plan the item as a gate on that event.
- A fix must close the failure window without opening another: check surrounding commit, retry, ordering, tenancy and cancellation behavior; preserve valid existing controls.
- **Read by need, not by file.** Area entry points are `knowledge/<prefix>/checks.md` (audit) and `knowledge/<prefix>/decisions.md` (design). Never load a whole `rules.md` to resolve one ID: Grep it, e.g. pattern `` ^`IDEM-BP-13` `` in `knowledge/idem/rules.md` (add `-A 3` for anti-patterns, whose symptoms span lines). The prefix in a rule ID names its directory. Reuse evidence instead of searching the same mechanism once per area.
- Efficiency never justifies sampling an enumerable inventory.
