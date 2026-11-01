# Domain review

Read only for audits with `domain=on`, or for backend design. Apply checks only within the selected areas and mechanisms in a focused audit; a full audit covers every in-scope domain module.

The skill does not define the target's domain. Derive it from the target's own sources — specs, ADRs, contracts, policies, tests, code comments, the authorization registry — and record each invariant with its source, owner and every entry point that can violate it. For each domain module apply at least:

- **Privilege matrix (SEC-CHK-21).** For every action admitting an elevated role, decide target = actor and targets tied to the actor (records they own or co-own, approvals of their own requests, their own limits, grants or payouts). Prefer a full role × action × target-relation table built from the registry over reading a few handlers.
- **One invariant, every writer (SEC-CHK-22).** A guard found in one module is evidence about that place only. List every other path reaching the same state — bulk, import, batch, CLI, job, admin tool, database policy — and confirm each enforces it.
- **Irreversible decisions (SEC-CHK-23).** Who may prepare, modify, confirm on behalf of others and approve; whether one principal completes the chain; whether the sources require separation. Silent sources produce an owner question, not a finding.
- **Workflow liveness (IDEM-CHK-21).** Every non-terminal state has an actor or job still permitted to move it forward after the preceding steps, and someone is told.
- **Documented obligations (DATA-CHK-21).** Every retention, deletion, consent, audit or delivery obligation has enforcing code on every ingestion path, with predicates that real data reaches.

Area rules still apply inside a domain pass. Record domain invariants with their status in the report's coverage section.

Domain authorization: SEC-BP-21, SEC-AP-8 — a central policy layer proves the chokepoint exists, not that each role/target decision is right; check the matrix.
