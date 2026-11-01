# Evidence and decision method

Read once per task. This method governs all area files, including their checklist “Fail” labels and default severities.

## Scope and evidence

- Record target revision (commit + dirty state, or document version), environment, available artifacts and exclusions. Read the plugin version from `.claude-plugin/plugin.json` for report provenance. Do not imply production verification from source code alone.
- Ask only questions whose answers could change a material conclusion. Continue independent work; mark unresolved assumptions. Missing target, required availability, loss tolerance or external controls may justify a question.
- For a focused request, keep findings and scorecard within scope. Read adjacent rules only to establish guarantees; note an essential out-of-scope dependency without performing an unsolicited full audit. A focused request still inventories the units inside its scope (next section).
- Start with the highest-impact user/business flows, then use the area checklists to find omissions. For each critical flow trace entry/authentication → authorization → state reads → transaction/side effect → publication/ack → recovery. Name the invariant, owner, trust boundaries and authoritative state.
- A rule is a hypothesis about a failure, not proof. Identify applicability, an actual violation and evidence that could refute it. Numbers for team sizes, hop counts, throughput, timeouts and topology are starting points, not universal acceptance limits. An alternative mechanism meeting the requirement passes.
- Before claiming a control is missing, inspect its plausible owners: callers/wrappers, schema constraints, middleware/gateway, infrastructure and provider contract. If an owner is unavailable, record the unknown; absence from a supplied snippet is not system-wide absence.

## Coverage inventory

Coverage holes — a module nobody reviewed, a registry checked by one example — hide the findings that matter most, because the reviewed paths are usually the well-built ones. Before checking anything, build an inventory of coverage units and keep it to the end.

1. **Enumerate units** of every kind present in scope: entry points (HTTP/RPC operations, GraphQL resolvers, CLI and admin commands, consumers, jobs and schedules); authorization declarations (action/permission registries, policy tables, role definitions, route guards); domain modules (packages, services, bounded contexts); persistent stores (tables, collections, buckets, journals); external dependencies; and documented obligations (the project's specs, ADRs, contracts, privacy/retention policies, compliance notes). Use the project's own generated artifacts and indexes (contracts, route tables, registries, migrations, code-graph exports) to count them.
2. **Enumerate, do not sample, whatever is enumerable.** A registry, route table, contract or migration list is finite: walk all of it. "Main write path plus a representative path" is acceptable only for units that cannot be enumerated with the available tools; then state the sampling rule, the denominator and why enumeration was infeasible.
3. **Assign every unit exactly one owner pass** (the lead or a named reviewer) and give it a terminal status: `checked`, `sampled` (with rule and denominator) or `not_covered` (with reason). A unit with no owner is a defect of the audit, not of the target. The report shows the counts; the validator rejects inventories that do not add up.
4. **Cover two axes.** Cross-cutting areas (the 13 knowledge areas) and domain modules are both mandatory for a full audit. An area pass does not cover a module's domain rules, and a module pass does not cover platform concerns. Each domain module receives a domain pass (next section).
5. **Use an index when the inventory is large.** When the workspace has a code index (a call graph or symbol graph such as graphify output, LSP references, ctags, Sourcegraph), use it to enumerate writers, callers and entry points. When enumeration is incomplete because no index is available or the budget is exhausted, say so in the coverage section: which unit kinds and how many units remain, and that a more detailed pass is possible over an indexed codebase (for example a graphify index). Readiness cannot be `supported_in_scope` while units remain uncovered.

## Domain pass

The skill does not define the target's domain. Derive it from the target's own sources — specs, ADRs, contracts, policies, tests, code comments and the authorization registry — and record each invariant with its source, owner and every entry point that can violate it. For each domain module apply at least these generic checks:

- **Privilege matrix (SEC-CHK-21).** For every action that admits an elevated role, decide the case target = actor and targets tied to the actor (records they own or co-own, approvals of their own requests, their own limits, grants or payouts). Prefer a full role × action × target-relation table built from the registry over reading a few handlers.
- **One invariant, every writer (SEC-CHK-22).** When a guard is found in one module, list every other path that reaches the same state — bulk, import, batch, CLI, job, admin tool, database policy — and confirm each enforces it. A guard seen in one place is evidence about that place only.
- **Irreversible decisions (SEC-CHK-23).** Who may prepare, modify, confirm on behalf of others and approve; whether one principal completes the chain; whether the domain's sources require separation. Silent sources produce an owner question, not a finding.
- **Workflow liveness (IDEM-CHK-21).** Every non-terminal state has an actor or job still permitted to move it forward after the preceding steps, and someone is told.
- **Documented obligations (DATA-CHK-21).** Every retention, deletion, consent, audit or delivery obligation has enforcing code covering every ingestion path, with predicates that real data reaches.

Area rules still apply inside a domain pass. Record domain invariants in the report's coverage section with their status.

## Check ledger

Keep a compact ledger for selected checks and critical invariants, with evidence locations. Reuse it across areas; no need to print hundreds of successful rows.

| State | Meaning |
| --- | --- |
| verified | The stated property holds in the assessed scope, with supporting evidence. |
| violation | Evidence supports a concrete failure scenario; record a finding/risk. |
| unverified | Relevant evidence is missing or a hypothesis remains unresolved. |
| not_applicable | A stated reason excludes this check from this target. |

Confidence belongs to a claim: confirmed = supported by the relevant implementation/config/contract or a reproducible result; likely = an evidenced path with an explicit unresolved premise; an unsupported suspicion is an open question. High area confidence requires corroboration of the critical paths and mechanisms, not merely reading files. Preserve distinctions between configured, statically inspected and exercised behavior.

- **Obligations need their source.** `verified` for an obligation-type check (retention, separation of duties, delivery guarantee, audit) cites both the obligation's source and the mechanism that covers it in every path. The existence of a mechanism is not verification of the obligation.
- **Split mixed checks.** When a check mixes code-verifiable and infrastructure parts, record the parts separately. Missing infrastructure evidence never makes the code part unverified.
- **Challenge every strength.** A strength names the boundary it was tested against: the bypass attempted, the other entry points searched, or the rule matrix checked. The existence of a mechanism (a policy layer, row-level security, a guard) is a strength of the mechanism, not proof that its rules are complete; say which rules were checked.

## Mechanism boundaries to check

Read the named canonical rules when these flows exist, even during a partial area read:

- Side effects/retries: IDEM-BAD-3 and IDEM-BP-13 — distinguish known rollback, completed effect and unknown outcome; a timeout is not proof of rollback.
- Outbox/ordered work: IDEM-BP-8, IDEM-BP-15 and MSG-BP-1 — partition keys alone do not order parallel publishers; snapshot replacement differs from ordered deltas; commits cannot skip unfinished earlier records.
- Concurrency: DATA-BP-6 and CONC-BP-12 — transaction isolation and lease fencing protect different boundaries; neither a lock name nor a transaction keyword proves an invariant.
- Authorization and bounds: SEC-BP-1, SEC-BP-3 and RES-BP-1 — follow the complete enforcement path, including schema, gateway and inherited deadlines.
- Domain authorization: SEC-BP-21 and SEC-AP-8 — a central policy layer proves the chokepoint exists, not that each action's role/target decision is right; check the matrix.

## Delegation and review independence

When delegation is authorized, split work so that coverage holes cannot appear and reviewers are not anchored:

- **Split by coverage units, on both axes.** Assign area groups and domain modules (or registry slices) so that every inventory unit has exactly one owner. Hand each reviewer its unit list and require a status per unit back. The lead merges inventories and runs the coverage gate before judging: any unit without a terminal status is reported, never silently dropped.
- **Neutral briefs.** Describe scope, units, sources and the report contract. Do not characterise the code's quality ("defensive", "well-tested", "don't invent findings" — restraint is already this method's rule). Pass the system map as claims to verify, not established facts, and ask for the attempted bypass behind each strength.
- **Independent recheck of strengths and High candidates.** For critical invariants recorded as strengths, and for every High/Critical candidate, have a reviewer other than the one who recorded it attempt to refute it from the code, giving it the code and the claim but not the conclusion.
- **Reconcile prior reports.** When earlier audits or reviews of the same target are available, list each prior High/Critical and classify it — reproduced, refuted (with the control), not applicable (feature or codebase absent, with evidence) or unverifiable. Check that a prior report concerns the same codebase and revision before comparing.

## Verification and design acceptance

For each critical requirement, maintain a small traceability table (audit: observed; design: proposed):

| Requirement / scenario | Invariant or measurable target | Mechanism / owner | Evidence or experiment | Acceptance condition / status |
| --- | --- | --- | --- | --- |
| Duplicate webhook, concurrent retry and worker crash | One business effect per provider operation | Durable inbox and atomic state update | Inject crashes before/after each durable step; replay concurrently | One effect after recovery; planned, not executed |

Use the existing tests, contracts, traces and measurements where available. Run targeted checks when feasible and within the task's authorized environment; otherwise specify the exact experiment and label it unexecuted. For unknown external outcomes test recovery, not just the happy-path retry. For latency/capacity use representative data, saturation and peak/failure scenarios; estimates are not benchmarks. For security identify actors, assets, trust crossings and abuse paths before selecting controls.

For consequential design choices compare the simplest viable option against alternatives using the actual requirements, team, cost and operability. Vary uncertain load/budget assumptions enough to identify the decision threshold. Document rollout compatibility, migration reconciliation and rollback acceptance where persistent state changes.

## Judgement and efficiency

- One root cause → one item with a primary area and all relevant rule IDs. The report format owns scoring; do not copy its rubric here or into area files.
- **Conditional severity.** When the severity depends on a pending configuration, rollout or growth event (a feature flag, a pilot allowlist, a second tenant), report the current severity and add `severity_if` with the `trigger`; plan the item as a gate on that event.
- A fix must close the failure window without opening another. Check surrounding commit, retry, ordering, tenancy and cancellation behavior. Preserve valid existing controls.
- Load the index, this method and the report contract once. Read selected checklists/decision tables, then only rule bodies relevant to the flow. Resolve cross-references by ID; do not load an entire adjacent file for one rule. Reuse evidence instead of searching the same mechanism for every area. Efficiency never justifies sampling an enumerable inventory.
- Consult `knowledge/sources.md` when a conclusion depends on a vendor limit, SDK behavior, version or product recommendation. Unverified defaults are assumptions, not findings.
