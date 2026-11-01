# Report contract

Both skills produce header, scorecard, coverage, evidence-backed items and closing JSON (schema 2.1). Audit and design scores mean different things and must not be compared as implementation readiness. Evidence rules: `method.md`.

## Scoring

- **Audit** scores the observed implementation/configuration or the supplied architecture artifact within its declared scope.
- **Design** scores how well the proposed mechanisms and explicit assumptions satisfy the requirements, using flow/state analysis and the validation plan as evidence. Missing implementation or unexecuted tests alone do not make a design area unverified; mark the particular undecided mechanism or unsupported capacity assumption partial/unverified. Never report an unexecuted test as passed.

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
- **Readiness** leads the summary: `blocked` if High/Critical items or demonstrated unmet mandatory requirements exist; else `undetermined` if material evidence or critical validation is missing or any coverage unit/domain module is `not_covered`; else `supported_in_scope`. It is a scoped assessment, never a launch approval (design: support for the proposal only). A high average cannot override blockers. Do not invent residual risks to keep a sound design below 10.

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

One root cause per item, ordered by severity. Preserve F-n/R-n IDs of a prior report for recurring issues; never renumber. `fingerprint` = target + logical component/operation + root cause, independent of line numbers and severity.

```markdown
### F-1 · <title> — <Severity>
- **Area:** <primary; also affected> · **Rule:** <IDs> · **Confidence:** confirmed | likely
- **Evidence:** <file:line/config/doc; observed vs executed; unresolved premise if likely>
- **Impact:** <scenario, violated requirement/invariant, blast radius>
- **Fix:** <minimal effective change>
- **Verification:** <test/inspection and acceptance; executed or planned>
- **Effort:** S | M | L · **Fingerprint:** <stable key>
- **Severity if:** <higher> when <trigger> (conditional only)
```

Design risks (R-n) cite the proposed element and its assumption/failure window. Decisions: **D-n · title** — Options · Chosen · Why (requirement) · Trade-off · Revisit when (observable threshold) · Rules; link critical ones to validation rows.

## Report skeleton

```markdown
# <Backend audit | Backend design>: <target>

| Mode | Target | Areas | Date | Overall | Confidence |
| --- | --- | --- | --- | --- | --- |

## Summary          — readiness, blockers, critical unknowns, main conclusions, then the score
## Scorecard        — | Area | Status | Score | Confidence | Crit | High | Med | Low | Coverage / key point |, plus an Overall row with inputs, denominator and cap
## Coverage         — | Unit kind | Total | Checked | Sampled | Not covered | Owner passes / sampling rule |; domain modules (owner, status); invariants (source, entry points, status); gaps; index recommendation; prior reports reconciled
## Context          — revision/environment, inspected artifacts, exclusions; audit: system map; design: requirements, arithmetic, assumptions, trust boundaries
## Architecture     — design: components, ownership, Mermaid diagrams of nontrivial flows and recovery
## Decisions        — design: D-n blocks
## Findings / Residual risks — F-n / R-n blocks, or "none established"
## Strengths        — verified controls or justified mechanisms, each with the boundary tested
## Plan             — | Priority (Now/Next/Later) | Items | Why now / dependencies | Acceptance gate |; migration, mixed-version and rollback gates
## Validation       — requirement → target → mechanism → experiment → acceptance/status; proposed vs executed kept distinct
## Open questions   — material unknowns, consequences, evidence needed
## Machine-readable summary — closing JSON block
```

**State each proof once** and reference it elsewhere; do not repeat an explanation across Summary, Strengths, Validation and Plan. Summarize the ledger as coverage counts instead of printing it.

**Compact form** (narrow requests): keep header, scorecard, coverage (one row may do), items or none, relevant decisions, material open questions and JSON; fold Context/Strengths/Plan/Validation into short paragraphs or item fields; keep at least one acceptance check for a consequential design. Aim for 400–800 words excluding JSON for one or two mechanisms. Do not expand to unrelated areas; report "Not assessed" rather than manufacture a number.

## Closing JSON (schema 2.1)

```json
{
  "schema_version": "2.1",
  "mode": "audit",
  "target": "orders-service",
  "date": "2026-11-01",
  "provenance": {"revision": "unknown", "dirty": null, "environment": "source-only", "plugin_version": "0.4.0", "rubric_version": "2.0", "scope": ["RES", "CACHE"], "exclusions": ["runtime behavior"]},
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

Field rules (the validator enforces them; it checks contract consistency, not architectural truth):

- **Provenance:** `revision`, `environment`, `plugin_version` nonempty; `rubric_version` "2.0"; `dirty` bool/null; `scope` equals the area IDs; `exclusions` string array.
- **Areas:** `coverage` counts selected ledger entries (not every possible check, not repository-wide completeness); assessed has no unverified entries; partial/unverified have unverified entries and nonempty `unknowns`; N/A has `null` counts, a `reason` and no items. `counts` exclude Info and count each item once in its primary area.
- **Items:** `{id, area, severity, rules, effort, title, fingerprint, confidence, evidence, verification}`; `severity` lowercase `critical|high|medium|low|info`; `confidence` `confirmed|likely`; `effort` `S|M|L`; `rules` and `evidence` nonempty string arrays of known rule IDs and `file:line[-line]` or document citations; `verification` names the check, acceptance and executed/planned status (may reference a V-n). Optional `severity_if` + `trigger`. Audit IDs `F-n`, design `R-n`.
- **Decisions** (design only): `{id: D-n, title, choice, rules}`, optional `requirements` and `validation` (V-n references).
- **Validation:** `{id: V-n, requirement, method, acceptance, status, evidence}`; status `planned|passed|failed|not_run`; passed/failed need result evidence. Design needs at least one entry.
- **overall:** `score`, `score_inputs`, `denominator`, `capped`, `provisional`, `confidence` as in Scoring; `blockers` includes every High/Critical item; `readiness` follows the Readiness rule; `supported_in_scope` requires all validation passed and nothing `not_covered`.
- **coverage_inventory** (required; design needs nonempty `invariants` derived from the requirements):
  - `units`: nonempty in audit; `{kind, total, checked, sampled, not_covered, owner}` with `checked + sampled + not_covered = total`; `sampled > 0` requires `sampling` (rule, denominator, why).
  - `domain_modules`: `{id, owner, status: checked|sampled|not_covered}`; an empty array in audit needs `domain_modules_reason`.
  - `invariants`: `{id, statement, source, entry_points, status}` with ledger statuses; `source` is the spec, ADR, contract or user requirement. Empty in audit needs `invariants_reason`.
  - `gaps`: every sampled or uncovered unit kind and module; then `index_recommendation` is a required string saying what an indexed pass (for example over a graphify graph) would enumerate.
- **prior_reports** (optional): `{source, item, prior_severity, verdict: reproduced|refuted|not_applicable|unverifiable, evidence}`.
- Schema 2.0 reports lack the coverage inventory and are rejected; regenerate rather than compare. Consumers distinguish `null` scores by `status` and never treat them as zero.
