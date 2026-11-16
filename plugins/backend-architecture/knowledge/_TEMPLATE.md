# Area template

A new area is a directory `knowledge/<prefix>/` with three files. Each starts with `# <Area> — <kind>` and the same scope line:

> **Scope:** one or two lines — what this area covers. **Hands off to:** neighbouring areas by prefix (e.g. "retry policy → RES, dedup on the consumer → IDEM").

## decisions.md — `## Key decisions`

| Decision | Options | Choose … when | Trade-off | Rules |
| --- | --- | --- | --- | --- |

5–10 rows. Options are concrete ("offset / keyset pagination"); "when" names the deciding requirement (volume, consistency need, team size…). `Rules` lists full rule IDs (`ARCH-BP-1, ARCH-AP-7`) or `—`; no abbreviations, no prose.

## checks.md — `## Audit checklist`

| ID | Check | Evidence / search hints | Default severity |
| --- | --- | --- | --- |

`<PREFIX>-CHK-n`, one table row each, the ID plain (no backticks) so `^\| <PREFIX>-CHK-n \|` finds it. Each check yields verified / violation / unverified / not_applicable per the shared method. Evidence says what to read or grep (Go and Node.js idioms, config, infra manifests) and what result means fail; a grep hit is a lead, not a finding. Cite BP/BAD/AP IDs in full (`SEC-BP-1, SEC-BP-3`, never `SEC-BP-1, BP-3` or `IDEM-BP-12/13`). List any BP/BAD/AP that neither the checklist nor a decisions `Rules` cell cites under `## Also scan for (rules not cited above)`, after a `Bodies: \`knowledge/<prefix>/rules.md\`, looked up by ID.` line, as `- ID — name`, so every rule is reachable.

## rules.md — `## Best practices`, `## Bad practices`, `## Anti-patterns`, `## Go / Node.js notes`

Every rule is exactly one line that starts with the ID in backticks, so `^\`<ID>\`` returns the whole body; no list marker, no continuation lines. IDs are `<PREFIX>-<kind>-n` with `<kind>` one of `BP`, `BAD`, `AP`.

`<PREFIX>-BP-n` — **Rule in one line.** Why (the failure prevented), how (mechanism), applicability, alternative, verification.

`<PREFIX>-BAD-n` — **The mistake.** What goes wrong. → Instead: the fix (BP ID). Local, single-spot mistakes; distinct failure mechanisms only.

`<PREFIX>-AP-n` — **Name.** Symptoms: … Why it hurts: … Way out: … Structural, recurring solutions; distinguish symptoms from proved impact.

- Go / Node.js notes: short bullets where stacks differ. Critical correctness constraints must also be linked from a rule or check so ID lookups cannot skip them.

Numeric values are illustrative unless sourced for a named version (register source, versions and verification date in `sources.md`). Prefer a cross-reference over repeating another area. New areas also need a row in `README.md` and the validator's area registry.
