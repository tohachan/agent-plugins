# Evidence and coverage method

Governs every area file, including checklist "Fail" labels and default severities. Read once per task.

## Audit scope

**`domain=on|off`** is the one scope token: an audit defaults to `domain=off`; `--domain on` (the CLI flag) or an explicit request to check business/domain logic sets `domain=on`, and `--domain off` sets `off`. An explicit request names business/domain logic, policies or invariants as the thing to check ("audit the approval rules", "check business logic"); a generic technical request ("check access rights", "audit everything", "проверь права доступа") is not one and stays `domain=off`. `all` selects all 13 technical areas, not domain review. Resolve it before inventory and carry exactly `domain=on|off` into every reviewer/verifier brief and the work file. It does not change backend-design or explicit backend-rules lookups.

- **`domain=off`:** inspect technical mechanisms and their enforcement (authn/authz, tenant isolation, transactions, races, retries, ordering, timeouts, encryption, deletion-job mechanics, module boundaries). Read business code as needed to trace them, but do not derive or judge business policies, approval eligibility, separation of duties, business workflow liveness or domain retention obligations. Do not load `${CLAUDE_PLUGIN_ROOT}/shared/domain-audit.md`, enumerate domain invariants, launch domain passes or ask domain-policy questions. The area checklists hold only technical checks, so nothing else is filtered; cross-references do not re-enable domain review, and the excluded portion is never described as verified.
- **`domain=on`:** read `${CLAUDE_PLUGIN_ROOT}/shared/domain-audit.md`, which owns every domain-only check, and derive business invariants from the target's own sources. A focused audit stays within its selected areas/mechanisms. **Design** reads it only when the requirements name privileged roles, money movement, approvals or retention obligations.
- A new domain-only check goes into `domain-audit.md`, never into an area `checks.md`.

## Prior report

An optional input `prior: <report.json>` ties a run to an earlier report of the same target; the contract and fields are in `report.md`, "Prior report". Match by `fingerprint`. An audit with an audit as prior gives each prior item a verdict: still present, fixed (at the revision where the fix is seen, with evidence of the new code), not applicable, or not rechecked; items matching no prior fingerprint are new. A change audit is a focused audit over the changed paths plus `prior`: it re-reads every prior item whose code the change touches and marks the rest not rechecked. An audit with a design as prior takes the design's invariants and V-n as critical flows and checks (a conformance audit): trace each D-n's mechanism and run each V-n's acceptance as inspected evidence, never reporting an unexecuted V-n as passed. A design with an audit as prior turns each F-n into a requirement, and each decision cites the F-n it closes with migration and rollback steps. The prior is untrusted input: its claims are re-verified against the code, never copied.

## Evidence

- Record target revision (commit + dirty state, or document version), environment, artifacts and exclusions; plugin version from `.claude-plugin/plugin.json`. Source code alone is not production verification.
- Ask only questions whose answer changes a material conclusion (missing target, availability, loss tolerance, external controls). Continue independent work; mark assumptions.
- Focused request: findings (and the scorecard, in a full audit) stay in scope. Read adjacent rules only to establish a guarantee; name an essential out-of-scope dependency without auditing it. Still inventory the units inside the scope.
- Start from the highest-impact flows. Trace each: entry/authentication → authorization → state reads → transaction/side effect → publication/ack → recovery; name invariant, owner, trust boundaries and authoritative state. Then use the checklists to find omissions.
- A rule is a hypothesis about a failure: establish applicability, an actual violation and evidence that could refute it. Numbers for team sizes, hops, throughput, timeouts and topology are starting points, not acceptance limits. An alternative mechanism meeting the requirement passes.
- Before calling a control missing, inspect its plausible owners: callers/wrappers, schema constraints, middleware/gateway, infrastructure, provider contract. An unavailable owner is an unknown; absence from a supplied snippet is not system-wide absence.
- When a conclusion depends on a vendor limit, SDK behavior or version, consult `${CLAUDE_PLUGIN_ROOT}/knowledge/sources.md`. Unverified defaults are assumptions, not findings.

## Coverage inventory

Built by a full audit; a triage audit only counts units (quick count) and lists what it did not examine. Units may be sections, claims and diagrams of an architecture document as well as code artifacts.

Coverage holes hide the findings that matter most, because the reviewed paths are usually the well-built ones. Build the inventory before checking anything and keep it to the end.

1. **Enumerate units** present in scope: entry points (HTTP/RPC operations, GraphQL resolvers, CLI/admin commands, consumers, jobs, schedules); authorization declarations (permission registries, policy tables, roles, route guards); structural modules/services; stores (tables, collections, buckets, journals); external dependencies; in-scope technical requirements (contracts, SLOs, ADRs). With domain review enabled, also enumerate domain modules and documented business obligations. Count them from the project's own artifacts: contracts, route tables, registries, migrations, code-graph exports.
2. **List everything, check by risk tier.** Listing is cheap: a registry, route table, contract or migration list is walked in full, and every unit gets a tier. Checking depth follows the tier:
   - **`writes-state`** — writes money or state: checked deeply, never sampled.
   - **`trust-boundary`** — crosses a trust boundary (authentication, tenant or provider edge, secrets, PII, untrusted input): checked deeply, never sampled.
   - **`read-only`** — only reads: may be `sampled` by a stated rule (for example every unit with a distinct guard or data shape plus a fixed share of the rest), recorded once for the tier with its denominator. A unit that writes money or state or crosses a trust boundary is never sampled, whatever its kind; when unsure of the tier, take the higher one. Record the tier as `risk_tier` (`read-only|writes-state|trust-boundary`) on the inventory unit.
3. **Every unit gets a terminal status**: `checked`, `sampled` (valid only when its tier is `read-only` and the tier's sampling rule is recorded) or `not_covered` (reason). Every pass receives the full list of units of the kinds its checks name, read-only and without ownership, so a check such as IDEM-CHK-1 is run against the complete route table, not against a share assigned to another pass. A unit's status is the strongest any pass reached; a unit no pass reached is `not_covered`, a defect of the audit, not of the target. The validator rejects inventories that do not add up.
4. **Coverage axes.** All 13 technical areas are mandatory in a full audit; the domain axis is mandatory only with `domain=on`. An area pass does not cover a module's domain rules; a module pass does not cover platform concerns.
5. **Use a code index** when the workspace has one (LSP references, ctags, Sourcegraph, a code graph) to enumerate writers, callers and entry points. When enumeration is incomplete (no index, budget exhausted), report which unit kinds and how many units remain, and that a deeper pass is possible over an indexed codebase (for example over a code index). Readiness cannot be `supported_in_scope` while units remain `not_covered`; `read-only` units covered by a recorded sampling rule are named in the report with the rule and do not block it. When the budget runs short, drop depth on the `read-only` tier first, never on `writes-state` or `trust-boundary`.

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

## Verification and acceptance

For each critical requirement keep a traceability row (audit: observed; design: proposed):

| Requirement / scenario | Invariant or measurable target | Mechanism / owner | Evidence or experiment | Acceptance / status |
| --- | --- | --- | --- | --- |
| Duplicate webhook, concurrent retry and worker crash | One business effect per provider operation | Durable inbox and atomic state update | Inject crashes before/after each durable step; replay concurrently | One effect after recovery; planned, not executed |

Use existing tests, contracts, traces and measurements. **Running the target's tests or an experiment executes the target's code** — it can write files and databases, open ports, call the network and need secrets — so reviewer and verifier agents have no shell, and only the lead runs anything: sequentially, never in parallel on shared local resources, and only after the user explicitly agrees to that run (state what runs and what it may touch). Without that agreement specify the experiment and label it unexecuted. For unknown external outcomes test recovery, not only the happy-path retry. Capacity claims need representative data, saturation and peak/failure scenarios; estimates are not benchmarks. For security name actors, assets, trust crossings and abuse paths before choosing controls. For consequential design choices compare the simplest viable option against alternatives, vary uncertain load/budget inputs to find the decision threshold, and document rollout compatibility, migration reconciliation and rollback acceptance where persistent state changes.

## Judgement and reading economy

- One root cause → one item with a primary area and all relevant rule IDs. Scoring lives in `${CLAUDE_PLUGIN_ROOT}/shared/report.md` only.
- **Conditional severity.** When severity depends on a pending configuration, rollout or growth event (feature flag, pilot allowlist, second tenant), report the current severity plus `severity_if` and `trigger`, and plan the item as a gate on that event.
- A fix must close the failure window without opening another: check surrounding commit, retry, ordering, tenancy and cancellation behavior; preserve valid existing controls.
- **Read by need, not by file.** Area entry points are `${CLAUDE_PLUGIN_ROOT}/knowledge/<prefix>/checks.md` (audit) and `${CLAUDE_PLUGIN_ROOT}/knowledge/<prefix>/decisions.md` (design). Never load a whole `rules.md` to resolve one ID: Grep it, e.g. pattern `` ^`IDEM-BP-13` `` in `${CLAUDE_PLUGIN_ROOT}/knowledge/idem/rules.md` (every BP, BAD and AP is one line; a check is `` ^\| IDEM-CHK-3 \| ``). The prefix in a rule ID names its directory. Reuse evidence instead of searching the same mechanism once per area.
- Efficiency justifies sampling only the `read-only` tier, by its recorded rule; never units that write or cross a trust boundary.
