# Area template

A new area is a directory `knowledge/<prefix>/` with three files. Each starts with `# <Area> — <kind>` and the same scope line:

> **Scope:** one or two lines — what this area covers. **Hands off to:** neighbouring areas by prefix (e.g. "retry policy → RES, dedup on the consumer → IDEM").

## decisions.md — `## Key decisions`

| Decision | Options | Choose … when | Trade-off |
| --- | --- | --- | --- |

5–10 rows. Options are concrete ("offset / keyset pagination"); "when" names the deciding requirement (volume, consistency need, team size…).

## checks.md — `## Audit checklist`

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |

`<PREFIX>-CHK-n`, one table row each. Each check yields verified / violation / unverified / not_applicable per the shared method. Evidence says what to read or grep (Go and Node.js idioms, config, infra manifests) and what result means fail; a grep hit is a lead, not a finding. Cite the BP/BAD/AP IDs the check verifies. List any BAD/AP the checklist does not cite under `## Also scan for (rules not cited above)` as `- ID — name`, so every rule is reachable from `checks.md`.

## rules.md — `## Best practices`, `## Bad practices`, `## Anti-patterns`, `## Go / Node.js notes`

- `<PREFIX>-BP-n` — **Rule in one line.** Why (the failure prevented), how (mechanism), applicability, alternative, verification. One paragraph on one line, so Grep by ID returns it whole.
- `<PREFIX>-BAD-n` — **The mistake.** What goes wrong. → Instead: the fix (BP ID). Local, single-spot mistakes; distinct failure mechanisms only.
- `<PREFIX>-AP-n` — **Name.** Symptoms, why it hurts, way out — at most a few lines directly under the ID line. Structural, recurring solutions; distinguish symptoms from proved impact.
- Go / Node.js notes: short bullets where stacks differ. Critical correctness constraints must also be linked from a rule or check so ID lookups cannot skip them.

Numeric values are illustrative unless sourced for a named version (register source, versions and verification date in `sources.md`). Prefer a cross-reference over repeating another area. New areas also need a row in `README.md` and the validator's area registry.
