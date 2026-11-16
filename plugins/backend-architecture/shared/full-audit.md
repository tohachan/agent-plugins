# Full audit protocol

Use only for a full audit with no focus areas: `--full` (or an explicit request for a full, complete audit) over a service, repository or architecture document, all 13 technical areas, domain passes only with `domain=on`. It is never entered by default or by inventory size: the default audit is the triage in `backend-audit`, and a large inventory only makes the triage recommend `--full`. Its purpose: no unit is skipped and no conclusion rests on an unrecorded read. The coverage rules themselves are in `method.md`.

## Work file

Before checking anything create `docs/audit/backend-audit-<YYYY-MM-DD>.work.md` (a scratch file when the target is read-only). It records `domain=on|off` and the scope exclusions, and holds the system map, critical flows, the inventory with owners, and the ledger rows each pass appends. It is the only input to the gate and the report, and it survives context compaction: after compaction re-read the work file, not the code. Keep it beside the report as coverage evidence unless the user asks otherwise.

## Phases, in fixed order

0. **Inventory (lead).** System map — entry points, modules/services, stores, brokers, external clients, deployment and trust boundaries — as claims to verify, not findings. Unit inventory per `method.md`, extending the quick count `backend-audit` already took rather than recounting it; for an architecture document the units are its sections, claims and diagrams (document units are valid, with quoted text as evidence); domain sources and their invariants only with `domain=on`; available code index; prior audits of the same target. Give every in-scope unit its risk tier (`writes`, `boundary`, `read-only`; `method.md`, "Coverage inventory") and the tier's sampling rule for `read-only`, and write them to the work file. Units are not assigned to a single owner: each pass is given the full list of units of the kinds its checks name (see the table), read-only, plus the deep-check list of `writes` and `boundary` units that fall under its main risk.
1. **Critical flows (lead).** Trace the 3–5 highest-impact flows end to end. Record each with file:line as claims for the passes to confirm or refute.
2. **Area passes.** Each pass reads `${CLAUDE_PLUGIN_ROOT}/shared/method.md` and only its own `checks.md` files, resolves rule bodies by ID and gives every check of its areas a ledger state.

   | Pass | Areas | Unit kinds its checks name (full list, no ownership) |
   | --- | --- | --- |
   | A · State & writes | DATA, IDEM, CONC, MSG | stores, consumers and jobs, relays/outboxes, transactions |
   | B · Edge & trust | API, SEC | entry points, authorization declarations, secrets and PII |
   | C · Runtime | RES, PERF, CACHE, SCALE | external dependencies, caches, hot paths, capacity |
   | D · Operations & structure | OBS, OPS, ARCH | CI/deploy/config artifacts, migrations in production, module boundaries |

   A unit kind not listed goes to the pass whose areas own its main risk, and its status is recorded from that pass; record the choice in the work file. A pass whose deep-check list exceeds about 40 units is split into several reviewers by unit batch (same areas, same full reference list), so no single context carries hundreds of units.
3. **Domain passes (only with `domain=on`).** One per domain module, or per batch of up to three small modules or one registry slice: `${CLAUDE_PLUGIN_ROOT}/shared/domain-audit.md` plus any area rule that applies. With domain off, skip this phase entirely.
4. **Coverage gate** (below). Nothing is scored before it passes.
5. **Report** per `${CLAUDE_PLUGIN_ROOT}/shared/report.md`, built from the work file; render and validate before delivering.

## Execution with subagents

When the Agent tool is available, run pass 2 and, only with domain on, pass 3 as parallel `backend-architecture:backend-reviewer` agents — one per area pass, one per domain batch — unless the user asked for a single-agent run. Each brief contains: the resolved plugin root path (the value of `${CLAUDE_PLUGIN_ROOT}`, spelled out because a subagent may not have the variable), `domain=on|off`, the pass's areas or domain checks, its full reference list and deep-check batch, tier sampling rules, domain sources only when enabled, the system map and flows labelled as claims to verify, and the work-file excerpt it needs. Briefs stay neutral: never characterise the code's quality ("defensive", "well-tested", "don't invent findings" — restraint is already the method's rule). Do not pass a `model` parameter on these Agent calls: it would override the agents' own model and effort settings. The lead appends each returned ledger to the work file and, while writing, gives every candidate and every strength a stable ID: `C-<pass>-<n>` and `S-<pass>-<n>` (pass letter A–D, or `X1`… for a domain batch; `n` in return order). Reviewers do not assign IDs; the work file does, and every later hand-off cites them.

Then send every High/Critical candidate, and every strength standing for a critical invariant, to `backend-architecture:backend-verifier` agents (each brief carries the resolved plugin root path, as for reviewers), up to five claims per agent. A verifier is always a separate dispatch with its own context, never a reviewer's and never the verifier that already ruled on the same ID. A claim in the brief is exactly: its ID (`C-…` or `S-…`), the **claim** — one line saying what is asserted to fail (candidate) or to hold (strength), as plain assertion — the code locations, and the domain. Not the reviewer's severity, reasoning, fix or confidence: those are the conclusion. The brief also carries `domain=on|off`; with `domain=off`, business policies do not become verifier tasks. Add one line to every verifier brief: "For this flow, name the most likely failure the reviewers missed." That is the recall probe; its answer goes to the work file as a new candidate to check, not as a finding.

Append each verdict to the work file against its ID as it returns; the work file stays the only input to the gate and the report.

## Execution without subagents

Run the same passes sequentially in the table's order. After each pass append its ledger rows and unit statuses to the work file before opening the next pass's checklists; never carry a candidate only in context. Give candidates and strengths the same `C-`/`S-` IDs, and before keeping a High/Critical candidate or a critical strength, re-read its code for the opposite hypothesis — how this could be safe, or how the control could be bypassed — and record the result against the ID, with `unresolved` and refuted strengths handled as in the gate.

Reviewers and verifiers have no shell. Anything that needs the target's code run (tests, an experiment) is collected by the lead as a named proposal; the lead runs it only with the user's explicit agreement, one at a time (`method.md`, "Verification and acceptance"), and records it as executed. Otherwise it stays `unexecuted`.

## Coverage gate

1. **Merge.** Every in-scope unit and enabled domain module has a terminal status, the strongest any pass reached. A unit no pass reached is `not_covered` and reported as a gap, never dropped.
2. **Check the tiers.** `sampled` is accepted only for `read-only` units with the tier's sampling rule recorded; a `sampled` unit that writes money or state or crosses a trust boundary is a defect of the audit and goes back to a pass. Name each sampling rule and denominator in the report. `not_covered` units go to gaps with the index recommendation; readiness then cannot be `supported_in_scope`.
3. **Independent re-verification** done as above, with every verdict recorded against its ID in the work file. `upheld` keeps the item. `refuted` candidates are removed or downgraded with the verifier's evidence. `unresolved` keeps the item at confidence `likely` and adds the open question the verifier named. A refuted strength is not deleted: the bypass the verifier found is a new candidate `C-…`, carrying the verifier's evidence; at High or above it goes to a fresh verifier before it is kept. `out_of_scope` claims are excluded without being described as safe or refuted. A probe answer is checked once like any new candidate and is kept only with evidence.
4. **Reconcile prior reports.** First confirm the same codebase and revision; prior domain-only items in a `domain=off` run are `not_applicable` with the explicit scope exclusion, never refuted. Then classify each prior High/Critical as reproduced, refuted (naming the control), not applicable (feature or codebase absent, with evidence) or unverifiable.
