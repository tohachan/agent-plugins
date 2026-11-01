# Shared report contract

Both skills retain header, scorecard, evidence-backed items and closing JSON. Audit and design share structure, but their scores have different meanings and must not be compared as implementation readiness. Evidence rules live in `assessment-method.md`.

## Coverage and scoring

**Mode-specific evidence:** in audit mode, score the observed implementation/configuration or the supplied architecture artifact within its declared scope. In design mode, score how well the proposed mechanisms and explicit assumptions satisfy requirements, using flow/state analysis and the validation plan as design evidence. Missing implementation or unexecuted runtime tests alone do not make every design area unverified. Mark the particular undecided mechanism or unsupported capacity assumption partial/unverified; keep implementation readiness and planned experiments separate from the proposal score. Never report an unexecuted test as passed.

Each in-scope area has a status:

| Status | Score display | Meaning |
| --- | --- | --- |
| assessed | 0–10 | Enough evidence for the important properties in the declared scope. |
| partial | 0–10, provisional | Some evidenced conclusions; important checks remain unverified. |
| unverified | Not assessed | Insufficient evidence to assign a defensible number. |
| not_applicable | N/A | Excluded for an explicit reason. |

Use `null` scores for the last two states; never substitute zero. Partial scores describe inspected behavior and cannot exceed 7; if the missing evidence prevents any useful rating, use unverified. Report discovered violations even in an otherwise unverified area. No numeric score means no area cap calculation, not no risk.

| Score | Meaning within the assessed scope |
| --- | --- |
| 10 | Critical promises supported, applicable checks verified, no items above Info. |
| 8–9 | Solid: only Low/Info items and no material coverage gap. |
| 6–7 | Medium items; no High/Critical. |
| 4–5 | One High, or compounding Medium items. |
| 2–3 | Several High, or one Critical. |
| 0–1 | Several Critical, or a required control demonstrably absent with severe impact. |

Caps: Critical ≤ 3; High ≤ 5, applied only in the item's primary area. Another affected area may be lowered with an explanation, without duplicating counts. **Overall** remains the mean of numeric area scores, rounded half-up to one decimal, capped at 4.0 if any Critical item exists (including in an unverified area). With no numeric scores it is `null`. Show the numeric inputs and denominator. Overall is provisional if any area is partial/unverified. Do not compare scores across changes in scope, coverage, mode or rubric without calling out those changes.

Area confidence: high = corroborated critical mechanisms/paths; medium = supporting but limited evidence; low = assumptions dominate. Partial confidence cannot be high; null confidence for unverified/N/A. Confidence measures support for conclusions, not the number of files read.

Overall confidence is null without numeric inputs, otherwise high/medium/low; a provisional overall cannot have high confidence.

Lead the summary with **Readiness**: `blocked` if High/Critical items or demonstrated unmet mandatory requirements exist; otherwise `undetermined` if material evidence or critical validation is missing, or if any coverage unit or domain module in scope is `not_covered`; otherwise `supported_in_scope`. This is a scoped assessment, never a launch approval. In design mode this means support for the proposal only. A high average cannot override blockers or missing validation. Do not invent residual risks to keep a sound design below 10.

## Severity

| Severity | Concrete scenario |
| --- | --- |
| Critical | Severe loss/corruption, unauthorized access, wrong financial effect or outage reachable under ordinary operation/exposure. |
| High | Comparable material impact under a realistic failure, retry or peak; or a hard block on a mandatory requirement. |
| Medium | Material latency/cost/operability degradation or a substantiated growth risk. |
| Low | Small impact or maintainability issue with a concrete consequence. |
| Info | Observation worth preserving. |

Use realistic reachability, impact and blast radius, not a rule's default label. A hypothetical attack/failure with no evidenced path belongs in open questions.

When the severity depends on a pending event — a configuration switch, a rollout step, a pilot allowlist lifted, a second tenant — report the current severity, add `severity_if` (a higher severity) and `trigger` (the event), and plan the item as a gate on that event. Counts and caps use the current severity.

## Items and decisions

One root cause per item, ordered by severity. Preserve F-n/R-n IDs from a prior report when the same issue recurs; assign new IDs without renumbering existing ones. Add a stable `fingerprint` derived from target + logical component/operation + root cause, independent of line numbers and severity.

```markdown
### F-1 · <title> — <Severity>
- **Area:** <primary; also affected areas> · **Rule:** <IDs> · **Confidence:** confirmed | likely
- **Evidence:** <file:line/config/doc section; observed vs executed; unresolved premise if likely>
- **Impact:** <scenario, violated requirement/invariant and blast radius>
- **Fix:** <minimal effective change>
- **Verification:** <test/inspection and acceptance condition; executed or planned>
- **Effort:** S | M | L · **Fingerprint:** <stable key>
- **Severity if:** <higher severity> when <trigger> (only for conditional severity)
```

Unsupported suspicions go to Open questions, not items. Design risks cite the proposed element and assumption/failure window. Every item has one primary area for counts, and may cite multiple rules.

Decisions retain: **D-n · title** — Options · Chosen · Why (requirement) · Trade-off · Revisit when (observable threshold) · Rules. Link critical decisions to the validation table. JSON keeps existing decision fields and adds `requirements` and `validation` references when relevant.

## Report skeleton

```markdown
# <Backend audit | Backend design>: <target>

| Mode | Target | Areas | Date | Overall | Confidence |
| --- | --- | --- | --- | --- | --- |
| audit/design | target | scope | YYYY-MM-DD | x.x/10 (provisional if needed), or Not assessed | high/medium/low or unknown |

## Summary
Readiness, blockers, critical unknowns and main conclusions; then the supporting score.

## Scorecard
| Area | Status | Score | Confidence | Crit | High | Med | Low | Coverage / key point |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ... | assessed/partial/unverified/not_applicable | ... | ... | ... | ... | ... | ... | verified/violation/unverified/N/A counts; references |
| Overall | provisional or assessed | ... | ... | ... | ... | ... | ... | explicit inputs and denominator; cap if any |

## Coverage
| Unit kind | Total | Checked | Sampled | Not covered | Owner passes / sampling rule |
| --- | --- | --- | --- | --- | --- |
| entry points / authorization declarations / domain modules / stores / obligations … | n | n | n | n | who covered them; sampling rule and denominator |

Domain modules with owner and status; domain invariants with source (spec/ADR/contract), entry points and status; gaps; and, when anything is sampled or not covered, the index recommendation (for example: a more detailed pass is possible over an indexed codebase such as a graphify graph). Prior reports reconciled, when any were available.

## Context
Revision/environment, inspected artifacts/flows and exclusions. Audit: system map and invariants. Design: requirements, arithmetic, assumptions and trust boundaries.

## Architecture (design)
Components/ownership and Mermaid diagrams of nontrivial flows and recovery.

## Decisions (design)
D-n blocks.

## Findings (audit) / Residual risks (design)
F-n / R-n blocks, or explicitly none established.

## Strengths
Verified controls (audit) or justified mechanisms (design), with rule/evidence references and the boundary each was tested against (bypass attempted, other writers searched, rule matrix checked).

## Plan
| Priority | Items / decisions | Why now / dependencies | Acceptance gate |
| --- | --- | --- | --- |
| Now / Next / Later | ... | ... | ... |
Include migration, mixed-version compatibility and rollback gates where applicable.

## Validation
Requirement/scenario → invariant/target → mechanism/owner → evidence/experiment → acceptance/status. Keep proposed and executed checks distinct.

## Open questions
Material unknowns, their consequences and evidence needed to settle them.

## Machine-readable summary
Closing JSON block.
```

## Machine-readable summary

Schema 2.1 preserves every 2.0 field and adds the mandatory `coverage_inventory` (plus optional `severity_if`/`trigger` on items and `prior_reports`). Consumers must distinguish null scores using `status`; never treat them as zero. The High cap is 5. Reports in schema 2.0 have no coverage inventory and are rejected by the validator; regenerate rather than compare them with 2.1 reports.

```json
{
  "schema_version": "2.1",
  "mode": "audit",
  "target": "orders-service",
  "date": "2026-11-01",
  "provenance": {"revision": "unknown", "dirty": null, "environment": "source-only", "plugin_version": "0.3.0", "rubric_version": "2.0", "scope": ["RES", "CACHE"], "exclusions": ["runtime behavior"]},
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

Items retain `{id, area, severity, rules, effort, title}` and add `{fingerprint, confidence, evidence, verification}`; evidence is a nonempty string array. Counts exclude Info and count each item once in its primary area, including for unverified areas. N/A has null counts and no items. Coverage counts the selected ledger entries, not every possible check; it does not imply repository-wide completeness. Decisions retain `{id, title, choice, rules}`. Validation status is `planned`, `passed`, `failed` or `not_run`; passed/failed requires result evidence.

JSON item types: `severity` is lowercase `critical|high|medium|low|info`; `confidence` is `confirmed|likely`; `effort` is uppercase `S|M|L`; `rules` and `evidence` are nonempty string arrays. `id`, `area`, `title`, `fingerprint` and `verification` are nonempty strings. In `verification`, describe the check, acceptance condition and executed/planned status; detailed results can reference a V-n entry. Display labels in Markdown may use title case.

`coverage_inventory` (audit: required; design: required with nonempty `invariants` derived from the requirements):

- `units`: nonempty array of `{kind, total, checked, sampled, not_covered, owner}` with `checked + sampled + not_covered = total`; a unit kind with `sampled > 0` carries `sampling` (rule, denominator and why enumeration was infeasible).
- `domain_modules`: array of `{id, owner, status}` with status `checked|sampled|not_covered` and a nonempty owner; an empty array needs `domain_modules_reason` (for example a single-mechanism focused audit).
- `invariants`: array of `{id, statement, source, entry_points, status}` with the ledger statuses; `source` names where the invariant comes from (the project's spec, ADR, contract or the user's requirement). An empty array in audit mode needs `invariants_reason`.
- `gaps`: strings naming every uncovered or sampled unit kind and module; `index_recommendation`: required string whenever anything is sampled or not covered — say what an indexed pass (for example over a graphify code graph) would enumerate.
- Any `not_covered` unit or module forbids `supported_in_scope` readiness.

Items may add `severity_if` (strictly higher than `severity`) with a nonempty `trigger`. `prior_reports`, when present, is an array of `{source, item, prior_severity, verdict, evidence}` with verdict `reproduced|refuted|not_applicable|unverifiable`.

Validate an exported JSON or Markdown report with `python3 scripts/validate_report.py <report>`. Validation checks contract consistency, not truth of architectural claims.

## Compact reports

Keep header, scorecard, coverage (it may be a single table row for a narrow scope), items (or none), relevant decisions, material open questions and final JSON in every mode. Combine Context/Strengths/Plan/Validation into concise paragraphs or item fields when narrow; include at least one acceptance check for a consequential design. Do not expand to unrelated areas to fill the format. Report “Not assessed” rather than manufacture a numeric score.

For one or two mechanisms, aim for 400–800 words of prose/tables excluding JSON unless the risk requires more. State each proof once and reference it from other sections; summarize the check ledger in coverage counts rather than printing it in full. Keep Context to the facts needed to assess the conclusion. Retain all mandatory reporting fields without repeating the same explanation in Summary, Strengths, Validation and Plan.
