# Full audit protocol

Use for an unfocused service/repository audit (all 13 technical areas; domain passes only with `domain=on`), or for any audit whose inventory is too large for one pass to hold (roughly more than 30 entry points or 5 domain modules when domain review is enabled). Its purpose: no unit is skipped and no conclusion rests on an unrecorded read. The coverage rules themselves are in `method.md`.

## Work file

Before checking anything create `docs/audit/backend-audit-<YYYY-MM-DD>.work.md` (a scratch file when the target is read-only). It records `domain=off|on` and the scope exclusions, and holds the system map, critical flows, the inventory with owners, and the ledger rows each pass appends. It is the only input to the gate and the report, and it survives context compaction: after compaction re-read the work file, not the code. Keep it beside the report as coverage evidence unless the user asks otherwise.

## Phases, in fixed order

0. **Inventory (lead).** System map — entry points, modules/services, stores, brokers, external clients, deployment and trust boundaries — as claims to verify, not findings. Unit inventory per `method.md`; domain sources and their invariants only with `domain=on`; available code index; prior audits of the same target. Assign every in-scope unit and, when enabled, domain module to exactly one pass below and write the assignment to the work file.
1. **Critical flows (lead).** Trace the 3–5 highest-impact flows end to end. Record each with file:line as claims for the passes to confirm or refute.
2. **Area passes.** Each pass reads `method.md` and only its own `checks.md` files, applies the domain scope filter before following rule references, resolves remaining rule bodies by ID and gives every check of its areas a ledger state (`not_applicable` with a reason for excluded domain checks).

   | Pass | Areas | Default unit kinds owned |
   | --- | --- | --- |
   | A · State & writes | DATA, IDEM, CONC, MSG | stores, consumers and jobs, relays/outboxes, transactions |
   | B · Edge & trust | API, SEC | entry points, authorization declarations, secrets and PII |
   | C · Runtime | RES, PERF, CACHE, SCALE | external dependencies, caches, hot paths, capacity |
   | D · Operations & structure | OBS, OPS, ARCH | CI/deploy/config artifacts, migrations in production, module boundaries |

   A unit kind not listed goes to the pass whose areas own its main risk; record that choice in the work file.
3. **Domain passes (only with `domain=on`).** One per domain module, or per batch of up to three small modules or one registry slice: `shared/domain-audit.md` plus any area rule that applies. With domain off, skip this phase entirely.
4. **Coverage gate** (below). Nothing is scored before it passes.
5. **Report** per `report.md`, built from the work file; render and validate before delivering.

## Execution with subagents

When the Agent tool is available, run pass 2 and, only with domain on, pass 3 as parallel `backend-architecture:backend-reviewer` agents — one per area pass, one per domain batch — unless the user asked for a single-agent run. Each brief contains: the plugin root path, the resolved domain mode and exclusions, the pass's areas or domain checks, its unit list, domain sources only when enabled, the system map and flows labelled as claims to verify, and the work-file excerpt it needs. Briefs stay neutral: never characterise the code's quality ("defensive", "well-tested", "don't invent findings" — restraint is already the method's rule). Do not pass a `model` parameter on these Agent calls: it would override the agents' own model and effort settings. The lead appends each returned ledger to the work file.

Then send every High/Critical candidate, and every strength standing for a critical invariant, to `backend-architecture:backend-verifier` agents: up to five claims per agent, never to the reviewer that recorded them, giving code locations, the claim and the resolved domain mode/exclusions, not the conclusion. Excluded business policies do not become verifier tasks.

## Execution without subagents

Run the same passes sequentially in the table's order. After each pass append its ledger rows and unit statuses to the work file before opening the next pass's checklists; never carry a candidate only in context. Before keeping a High/Critical candidate or a critical strength, re-read its code for the opposite hypothesis — how this could be safe, or how the control could be bypassed — and record the result.

## Coverage gate

1. **Merge.** Every in-scope unit and enabled domain module has an owner and a terminal status. A unit nobody took is reported as a gap, never dropped.
2. **Name what was not enumerated.** Sampled or uncovered units go to gaps with the index recommendation; readiness then cannot be `supported_in_scope`.
3. **Independent re-verification** done as above; refuted items are removed or downgraded with the verifier's evidence; `out_of_scope` claims are excluded without being described as safe or refuted.
4. **Reconcile prior reports.** First confirm the same codebase and revision; prior domain-only items in a domain-off run are `not_applicable` with the explicit scope exclusion, never refuted. Then classify each prior High/Critical as reproduced, refuted (naming the control), not applicable (feature or codebase absent, with evidence) or unverifiable.
