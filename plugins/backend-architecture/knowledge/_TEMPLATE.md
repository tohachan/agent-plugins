# <Area name>

> **Scope:** one or two lines — what this area covers. **Hands off to:** neighbouring areas by prefix (e.g. "retry policy → RES, dedup on the consumer → IDEM").

## Contents
(list of the sections below; keep it, it helps partial reads)

## Key decisions
A table. One row per decision a design must make in this area.

| Decision | Options | Choose … when | Trade-off |
| --- | --- | --- | --- |

5–10 rows. Options must be concrete (e.g. "offset pagination / keyset pagination"), "when" must name the deciding requirement (volume, consistency need, team size…).

## Best practices
`<PREFIX>-BP-n` — **Rule in one line.** Why (the failure it prevents). How (concrete mechanism), applicability, counterexample/alternative, and verification. Numeric values are illustrative unless sourced for a named version. Prefer a canonical cross-reference over repeating another area. Add only useful items, not a quota.

## Bad practices
`<PREFIX>-BAD-n` — **The mistake.** What goes wrong. → Instead: the fix (point to the BP ID). Local, single-spot mistakes; include only distinct failure mechanisms.

## Anti-patterns
`<PREFIX>-AP-n` — **Name.** Symptoms: how to recognise it in code or diagrams. Why it hurts. Way out: the refactoring path. Structural, recurring solutions; distinguish symptoms from proved impact.

## Audit checklist
| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |
`<PREFIX>-CHK-n`. Each selected check yields verified / violation / unverified / not_applicable per the shared method. Evidence column says what to read or grep for (Go and Node.js idioms, config files, infra manifests) and what result means fail. A grep hit is a lead, not a finding — say what to confirm. Link the BP/BAD/AP IDs the check verifies.

## Go / Node.js notes
Short bullets where stacks differ. Critical correctness constraints must also be linked from the main rule/check, so partial reads cannot skip them. For changing facts register source, applicable versions and verification date in sources.md; use unverified when not checked.
