# Report contract

Closing JSON, schema 3.0, in one of three shapes selected by `mode` and `depth`:

| Report | `mode` / `depth` | Carries | Does not carry |
| --- | --- | --- | --- |
| Triage audit (default) | `audit` / `triage` | system map, critical flows, evidence-backed findings, `not_examined` | scorecard, readiness, coverage inventory (all optional) |
| Full audit (`--full`) | `audit` / `full` | header, scorecard, coverage inventory, evidence-backed items, readiness | |
| Design | `design` | requirements, assumptions registry, D-n decisions, R-n risks, V-n validation | scorecard, readiness, coverage inventory |

Evidence rules: `method.md`. Schema 2.1 reports are rejected; regenerate them.

## Scoring (full audit only)

A full audit scores the observed implementation/configuration or the supplied architecture artifact within its declared scope. A triage audit assigns no numeric score; severities and the `not_examined` list carry its judgment. A design is not scored: it states assumptions, thresholds and validation, and never reports an unexecuted test as passed.

| Status | Score | Meaning |
| --- | --- | --- |
| assessed | 0–10 | Enough evidence for the important properties in scope. |
| partial | 0–10 provisional, ≤ 7 | Some evidenced conclusions; important checks unverified. |
| unverified | `null` ("Not assessed") | No defensible number. |
| not_applicable | `null` ("N/A") | Excluded for an explicit reason. |

Never substitute zero for `null`. Report discovered violations even in an unverified area; no numeric score means no area cap, not no risk.

| Score | Meaning in the assessed scope |
| --- | --- |
| 10 | Critical promises supported, applicable checks verified, no items above Info. |
| 8–9 | Only Low/Info items, no material coverage gap. |
| 6–7 | Medium items; no High/Critical. |
| 4–5 | One High, or compounding Medium items. |
| 2–3 | Several High, or one Critical. |
| 0–1 | Several Critical, or a required control demonstrably absent with severe impact. |

- **Caps** apply in the item's primary area: Critical ≤ 3, High ≤ 5. Another affected area may be lowered with an explanation, without duplicating counts.
- **Overall** = mean of numeric area scores, rounded half-up to one decimal; capped at 4.0 if any Critical exists (also in an unverified area); `null` with no numeric scores. Show inputs and denominator. Provisional if any area is partial/unverified. Do not compare across changes in scope, coverage, mode or rubric without saying so.
- **Confidence.** Area: high = corroborated critical mechanisms/paths; medium = supporting but limited evidence; low = assumptions dominate; partial cannot be high; `null` for unverified/N/A. Overall: `null` without numeric inputs; a provisional overall cannot be high.
- **Readiness** (full audit) leads the summary: `blocked` if High/Critical items or demonstrated unmet mandatory requirements exist; else `undetermined` if material evidence or critical validation is missing or any coverage unit/domain module is `not_covered`; else `supported_in_scope`. It is a scoped assessment, never a launch approval. A high average cannot override blockers. Do not invent residual risks to keep a sound design below 10.

## Domain scope in audit reports

With domain review off (the audit default), add "Domain business logic (domain=off)" to `provenance.exclusions`, state the exclusion in the summary, and set `coverage_inventory.domain_modules` to `[]` with `domain_modules_reason: "Domain business logic excluded (domain=off)"`. Do not enumerate excluded business obligations or label modules checked. Keep technical invariants in `invariants`; if none are established, use `[]` with an honest `invariants_reason`.

Exclusion is a deliberate scope boundary, not missing evidence: do not add excluded domain modules to `units`, `gaps` or `not_covered` counts, or lower readiness solely for the exclusion. Missing technical evidence still affects readiness normally. Scores and `supported_in_scope` cover technical scope only. With domain on, inventory and assess in-scope domain modules normally; name the enabled domain review in the summary. Design reports carry no domain section: domain requirements appear as assumptions and decisions when the requirements name roles, money or approvals.

## Severity

| Severity | Concrete scenario |
| --- | --- |
| Critical | Severe loss/corruption, unauthorized access, wrong financial effect or outage reachable under ordinary operation/exposure. |
| High | Comparable impact under a realistic failure, retry or peak; or a hard block on a mandatory requirement. |
| Medium | Material latency/cost/operability degradation or a substantiated growth risk. |
| Low | Small impact or maintainability issue with a concrete consequence. |
| Info | Observation worth preserving. |

Judge by realistic reachability, impact and blast radius, not the rule's default label. A hypothetical failure with no evidenced path is an open question. Conditional severity: current severity counts; `severity_if` (strictly higher) with `trigger` marks the gate.

## Items and decisions

One root cause per item. Preserve F-n/R-n IDs of a prior report for recurring issues; never renumber. `fingerprint` = target + logical component/operation + root cause, independent of line numbers and severity. Each item states realistic impact (scenario, violated requirement/invariant, blast radius), a minimal fix, and verification (executed or planned). Design risks (R-n) cite the proposed element, the failure window and, where one applies, the assumption they rest on (A-n). Decisions record options, the choice, why (requirement), trade-off, an observable revisit threshold and rules; link critical ones to validation rows.

## Writing the report: data once, rendered tables

Write every table and item **only in the closing JSON**; never type them in Markdown. Put render markers where they belong and run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py <report> [--evidence-root <target>]` (the plugin's own script by absolute path, whatever the working directory). It validates the JSON, then replaces each marker with the rendered block; re-running is idempotent and nothing is written while validation fails. On success the header block ends with a `Schema validation: passed; rendered by <script path> (plugin <version>)` line, and the script prints the same path and version: that line is the record that validation ran. Fix the JSON, never the rendered text. Without Python, write those blocks by hand in the same shape and state that validation was not run (no `Schema validation:` line).

**State each proof once** and reference it elsewhere; do not repeat an explanation across Summary, Strengths, Validation and Plan.

### Full audit layout

```markdown
# Backend audit: <target>

<!-- render:header -->

## Summary
Readiness, blockers, critical unknowns, main conclusions, then the score.

## Scorecard
<!-- render:scorecard -->

## Coverage
<!-- render:coverage -->

## Context
Revision/environment, inspected artifacts, exclusions, system map.

## Findings
<!-- render:items -->

## Strengths
Verified controls, each with the boundary tested.

## Plan
| Priority (Now/Next/Later) | Items | Why now / dependencies | Acceptance gate |; migration, mixed-version and rollback gates.

## Validation
<!-- render:validation -->

## Open questions
Material unknowns, consequences, evidence needed.

## Machine-readable summary
(closing JSON block)
```

Required markers: header, scorecard, coverage, items (validation when it has entries). Compact form for narrow requests: keep those markers, fold Context/Strengths/Plan into short paragraphs, 400–800 words excluding JSON for one or two mechanisms; report "Not assessed" rather than manufacture a number.

### Triage audit layout and JSON

```markdown
# Backend audit (triage): <target>

<!-- render:header -->

## System map
Entry points, modules/services, stores, brokers, external clients, trust boundaries: claims verified only where a finding cites them. Include the quick unit counts.

## Critical flows
The 3–5 highest-impact flows traced, each with file:line.

## Findings
<!-- render:items -->

## Not examined
<!-- render:not_examined -->

## Machine-readable summary
(closing JSON block)
```

Required markers: header, items, not_examined. No scorecard, readiness or coverage inventory is needed; if `areas`, `overall` or `coverage_inventory` are present they are validated as in a full audit. Top 3–5 risks, ordered by severity; a healthy system yields few or no findings and says so.

```json
{
  "schema_version": "3.0",
  "mode": "audit",
  "depth": "triage",
  "target": "orders-service",
  "date": "2026-11-01",
  "provenance": {"revision": "unknown", "dirty": null, "environment": "source-only", "plugin_version": "0.6.0", "scope": [], "exclusions": ["Domain business logic (domain=off)", "runtime behavior"]},
  "units_counted": [{"kind": "entry_points", "total": 3}, {"kind": "external_dependencies", "total": 1}],
  "items": [],
  "not_examined": ["Consumers and jobs (not read)", "Runtime recovery behavior"],
  "full_audit_suggested": null
}
```

- `provenance`: as in a full audit but `scope` lists the areas considered (empty means all 13) and `rubric_version` is not needed. `units_counted` (optional): `{kind, total}` from the quick count. `full_audit_suggested`: a nonempty string naming why `--full` would pay off (many units, high-impact unknowns), else `null`.
- `items`: as in a full audit (`F-n`, severity, rules, evidence, impact, fix, verification, fingerprint, effort, confidence); `area` is any of the 13 area IDs. Counts and caps do not apply.
- `not_examined`: nonempty array of what was not looked at and why; it is the honest counterpart of coverage. Never empty.

### Design layout and JSON

```markdown
# Backend design: <target>

<!-- render:header -->

## Requirements and arithmetic
Actors, flows, invariants, NFRs; RPS, storage, connections with ranges.

## Assumptions
<!-- render:assumptions -->

## Architecture
Components, ownership, Mermaid diagram of the main flow and recovery.

## Decisions
<!-- render:decisions -->

## Failure scenarios
Crash between durable steps, duplicate or out-of-order input, slow dependency, restore: what happens and why it is acceptable.

## Residual risks
<!-- render:risks -->

## Rollout
Migration, mixed-version and rollback gates.

## Validation
<!-- render:validation -->

## Machine-readable summary
(closing JSON block)
```

Required markers: header, assumptions, decisions, risks, validation. Focused pattern design: relevant sections only, one concise validation scenario. No scorecard, readiness or coverage inventory; domain requirements enter as assumptions and decisions.

```json
{
  "schema_version": "3.0",
  "mode": "design",
  "target": "payment webhooks",
  "date": "2026-11-01",
  "provenance": {"plugin_version": "0.6.0", "scope": ["IDEM", "MSG"]},
  "assumptions": [
    {"id": "A-1", "statement": "Provider retries for up to 3 days, about 200 rps at peak", "threshold": "Sustained above 2000 rps or retries beyond 7 days", "check": "Provider documentation; peak from access logs"}
  ],
  "decisions": [
    {"id": "D-1", "title": "Dedup on provider event ID", "choice": "Unique inbox row per event ID, ack after commit", "options": "in-memory cache; unique inbox row", "why": "Retries span days, so dedup must survive restarts", "tradeoff": "One insert per event", "revisit": "Inbox above 50M rows or a provider without stable event IDs", "rules": ["IDEM-BP-13"], "assumptions": ["A-1"], "validation": ["V-1"]}
  ],
  "risks": [
    {"id": "R-1", "title": "Inbox grows without a purge", "severity": "low", "rules": ["IDEM-BP-13"], "element": "inbox table", "scenario": "Retention job missing: table grows until vacuum cost affects the ack path", "fix": "Purge rows older than 4 days in batches", "assumptions": ["A-1"]}
  ],
  "validation": [
    {"id": "V-1", "requirement": "Duplicate delivery produces one effect", "method": "Replay each event twice, concurrently, with a crash after commit", "acceptance": "One effect per event ID after recovery", "status": "planned", "evidence": []}
  ]
}
```

- `provenance`: `plugin_version` nonempty, `scope` area IDs considered.
- `assumptions` (nonempty): `{id: A-n, statement, threshold, check}` — the claim, the value at which the choice changes, how to verify it.
- `decisions` (nonempty): `{id: D-n, title, choice, options, why, tradeoff, revisit, rules}`, optional `assumptions` (A-n) and `validation` (V-n) references. `rules` are known rule IDs.
- `risks` (may be empty): `{id: R-n, title, severity, rules, element, scenario, fix}`, optional `assumptions`; no file evidence is required for a proposal.
- `validation` (nonempty): `{id: V-n, requirement, method, acceptance, status, evidence}`; `planned` until run; `passed`/`failed` need result evidence.

## Full audit JSON (schema 3.0)

This focused example includes domain review (`--domain on`); for the default technical audit use the exclusion and empty domain-module inventory described above.

```json
{
  "schema_version": "3.0",
  "mode": "audit",
  "depth": "full",
  "target": "orders-service",
  "date": "2026-11-01",
  "provenance": {"revision": "unknown", "dirty": null, "environment": "source-only", "plugin_version": "0.6.0", "rubric_version": "2.0", "scope": ["RES", "CACHE"], "exclusions": ["runtime behavior"]},
  "overall": {"score": 7.0, "confidence": "medium", "capped": false, "provisional": true, "readiness": "undetermined", "blockers": [], "unknowns": ["Runtime recovery not exercised"], "score_inputs": [7], "denominator": 1},
  "areas": [
    {"id": "RES", "status": "partial", "score": 7, "confidence": "medium", "counts": {"critical": 0, "high": 0, "medium": 0, "low": 0}, "coverage": {"verified": 1, "violation": 0, "unverified": 1, "not_applicable": 0}, "evidence": ["client.go:24"], "unknowns": ["Runtime recovery not exercised"]},
    {"id": "CACHE", "status": "not_applicable", "score": null, "confidence": null, "counts": null, "coverage": {"verified": 0, "violation": 0, "unverified": 0, "not_applicable": 1}, "reason": "No cache and no requirement for one"}
  ],
  "coverage_inventory": {
    "units": [
      {"kind": "entry_points", "total": 3, "checked": 3, "sampled": 0, "not_covered": 0, "owner": "lead"},
      {"kind": "external_dependencies", "total": 1, "checked": 1, "sampled": 0, "not_covered": 0, "owner": "lead"}
    ],
    "domain_modules": [{"id": "orders/lookup", "owner": "lead", "status": "checked"}],
    "invariants": [{"id": "INV-1", "statement": "A lookup returns within the caller's deadline", "source": "docs/slo.md", "entry_points": ["GET /orders/{id}"], "status": "verified"}],
    "gaps": [],
    "index_recommendation": null
  },
  "items": [],
  "decisions": [],
  "validation": [{"id": "V-1", "requirement": "Recover within the agreed outage budget", "method": "Dependency fault injection", "acceptance": "Recovery meets the agreed budget", "status": "planned", "evidence": []}]
}
```

Field rules (the validator enforces them; it checks contract consistency, not architectural truth). The rest of this section is the **full audit** contract; triage and design follow their own sections.

- **Top level:** `schema_version` "3.0"; `mode` `audit|design`; audit also `depth` `full|triage`; `target`; `date`.
- **Provenance:** `revision`, `environment`, `plugin_version` nonempty; `rubric_version` "2.0"; `dirty` bool/null; `scope` equals the area IDs; `exclusions` string array.
- **Areas:** `coverage` counts selected ledger entries (not every possible check, not repository-wide completeness); assessed has no unverified entries; partial/unverified have unverified entries and nonempty `unknowns`; N/A has `null` counts, a `reason` and no items. `counts` exclude Info and count each item once in its primary area.
- **Rendering fields:** items add `impact` and `fix` (nonempty strings) and optional `also_areas` (area IDs); areas add optional `note` (the scorecard's key point); decisions add `options`, `why`, `tradeoff`, `revisit`. The renderer requires them; the validator ignores them.
- **Items:** `{id, area, severity, rules, effort, title, fingerprint, confidence, evidence, verification}`; `severity` lowercase `critical|high|medium|low|info`; `confidence` `confirmed|likely`; `effort` `S|M|L`; `rules` and `evidence` nonempty string arrays of known rule IDs and `file:line[-line]` or document citations; `verification` names the check, acceptance and executed/planned status (may reference a V-n). Optional `severity_if` + `trigger`. IDs `F-n`.
- **Validation:** `{id: V-n, requirement, method, acceptance, status, evidence}`; status `planned|passed|failed|not_run`; passed/failed need result evidence.
- **overall:** `score`, `score_inputs`, `denominator`, `capped`, `provisional`, `confidence` as in Scoring; `blockers` includes every High/Critical item; `readiness` follows the Readiness rule; `supported_in_scope` requires all validation passed and nothing `not_covered`.
- **coverage_inventory** (required in a full audit):
  - `units`: nonempty; `kind` is free text and may name documents (`document_sections`, `claims`) for an architecture-document audit; `{kind, total, checked, sampled, not_covered, owner}` with `checked + sampled + not_covered = total`; `sampled > 0` requires `sampling` (rule, denominator, why).
  - `domain_modules`: `{id, owner, status: checked|sampled|not_covered}`; an empty array needs `domain_modules_reason`.
  - `invariants`: `{id, statement, source, entry_points, status}` with ledger statuses; `source` is the spec, ADR, contract or user requirement. Empty needs `invariants_reason`.
  - `gaps`: every sampled or uncovered unit kind and module; then `index_recommendation` is a required string saying what an indexed pass (for example over a graphify graph) would enumerate.
- **prior_reports** (optional): `{source, item, prior_severity, verdict: reproduced|refuted|not_applicable|unverifiable, evidence}`.
- Schema 2.0 and 2.1 reports are rejected; regenerate rather than compare. Consumers distinguish `null` scores by `status` and never treat them as zero.
