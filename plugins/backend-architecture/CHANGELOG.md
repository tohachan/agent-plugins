# Changelog

## 0.6.0

**Breaking: report schema 3.0.** Schema 2.1 reports are rejected by `validate_report.py`; regenerate them.

- Design (`mode: design`) has its own contract: requirements arithmetic, an assumptions registry (assumption, threshold at which the choice changes, how to check it), D-n decisions, R-n risks and V-n validation. It carries no scorecard, readiness verdict or coverage inventory, so a design report no longer needs impossible `passed` validation to be valid. The renderer fills the assumptions, decisions, risks and validation blocks.
- `backend-design` reads `shared/domain-audit.md` only when the requirements name privileged roles, money, approvals or retention obligations; the SEC-BP-21, DATA-BP-21 and IDEM-BP-21 paragraph is gone from its decide step.
- `backend-design` is pinned to `opus`/`medium` like `backend-audit`, so model pinning is symmetric across the two report-producing skills.
- **`backend-audit` is a triage by default**: quick unit count, system map, 3–5 critical flows, findings with evidence and a list of what was not examined, with no numeric scores, ledger, work file or verifiers. `--full` (or an explicit request for a full audit) runs today's protocol with coverage inventory, scorecard and readiness. `all` no longer implies the full protocol, and a large focused audit keeps its areas and depth; the triage says when `--full` would pay off but never switches itself. Depth is chosen from the request, before the inventory, and the quick count is reused by the full protocol instead of being rebuilt.
- Audit reports carry `depth: "triage" | "full"`. A triage report needs only findings and a nonempty `not_examined` list; `areas`, `overall` and `coverage_inventory` are optional (validated as before when present). New triage fields: `not_examined`, `units_counted`, `full_audit_suggested`; new render markers `assumptions`, `risks`, `not_examined`. A full audit keeps its contract apart from `schema_version` 3.0 and `depth: "full"`. Document units (sections, claims, diagrams) are explicitly valid in a full audit of an architecture document.
- Routing: a pattern question over 1–3 areas ("how do I make webhooks idempotent?") goes to `backend-rules`, which offers `backend-design` when it grows into a whole system. The `backend-rules` and `backend-design` descriptions no longer overlap, and `backend-rules` says "1–3 areas" consistently.
- **Plan and Strengths are data (AGP-14).** Items carry `priority` (`now|next|later`, required except on Info) and optional `depends_on` (F-ids, no cycles); new optional `strengths` (`{control, boundary, evidence}`). New markers `plan` (required in a full audit) and `strengths` render them, so the report has no hand-typed table; a `validation` or `strengths` marker missing while the JSON has entries is an error instead of silently dropping rows.
- **The renderer owns the derived fields (AGP-19).** `render_report.py` fills area `counts`, `overall.score`, `score_inputs`, `denominator`, `capped`, `provisional`, `blockers` and `readiness` from the judgments and writes them back into the JSON; the validator still rejects any mismatch. Readiness can no longer be set above what the data supports. `report.md` now states every rule the validator enforces (coverage keys, score caps, nonempty area evidence, `entry_points`, duplicate fingerprints, `capped`); item, risk and decision `rules` accept rule IDs only, not CHK check IDs; a reference with whitespace in its path (`RFC 9110:15`) is a document citation, not a file; evidence is relative to the target repository root. One rule for `sampled`: a unit or module is sampled only with `risk_tier: "read-only"` and a recorded sampling rule, never when it writes state or money or crosses a trust boundary; valid sampling does not block `supported_in_scope`, `not_covered` does. Render runs are bounded (3), then the draft is delivered as `validation failed: <errors>`; drafts live in a scratch directory because the renderer rewrites its input in place.
- **Audit details (AGP-21).** `overall.unknowns` holds material unknowns only (what and why it matters); `noted_unknowns` records the rest and never moves readiness. `provenance.models` records the model and requested effort of each role. `index_recommendation` is optional and generic. The audit work file and draft stay in a scratch directory; saved reports are `docs/audit/backend-audit-<slug>-<date>.md` with `-2`, `-3` for repeats, `<slug>` defined in the skill. The README token table is not updated here: it counted a single agent, not the lead plus four reviewers and verifiers (about 200 KB or more against 143 KB), and plugin measurements stay in `evals/`.

## 0.5.0

**Breaking: behavior change.** `/backend-audit all` and "full audit" no longer run domain (business-logic) review. Before 0.5.0 a full audit covered business rules and domain invariants; now it is a technical audit. To get the old scope pass `--domain on` or ask explicitly to check business/domain logic. Anything that relied on the old default (scripts, prompts, saved commands, CI) must add the flag.

- Domain-only instructions moved to `shared/domain-audit.md`; they load only when domain review is enabled.
- The mode applies to focused and full audits, reviewers, verifiers and mixed checklists. Technical authorization enforcement, tenant isolation, transactions, retries and concurrency stay in scope when domain review is off.
- Reports render the scope exclusion; excluded domain modules use existing schema 2.1 fields and are not a coverage failure.
- `backend-design` and `backend-rules` keep their scope.
- Evals cover default-off, explicit-off and explicit-on behavior. No measured speedup is claimed.

## 0.4.0

Rule IDs, rule text, report schema (2.1) and scoring are unchanged.

**Breaking for anything that references paths:**

- each `knowledge/<area>.md` is split into `knowledge/<prefix>/{decisions,checks,rules}.md`;
- the shared assessment-method file is now `shared/method.md` (delegation moved to `shared/full-audit.md`);
- the shared output-format file is now `shared/report.md`.

New: `render_report.py` (JSON to Markdown tables and item blocks; items gain `impact`/`fix`, decisions gain `options`/`why`/`tradeoff`/`revisit`), model/effort settings, the `backend-rules` skill, the `backend-reviewer` and `backend-verifier` agents, and an explicit full-audit protocol with a work file.

Token budget, 0.3.0 versus 0.4.0 (before domain review became opt-in). Approximate knowledge and method bytes loaded, at about 4 bytes per token:

| Task | 0.3.0 | 0.4.0 |
| --- | --- | --- |
| One-area lookup (`backend-rules`, IDEM) | n/a; only a focused audit, ≈ 70 KB | ≈ 27 KB (README + `idem/rules.md`), no report |
| Focused audit, one area (IDEM) | ≈ 70 KB | ≈ 38 KB + looked-up rules |
| Full audit, single agent | ≈ 424 KB | ≈ 143 KB + looked-up rules |
| Full audit, lead with subagents | ≈ 424 KB in one context | ≈ 34 KB lead; each pass ≈ 32–44 KB in its own context |
| System design, ~8 areas | ≈ 39 KB + whole area files (≈ 30 KB each) | ≈ 31 KB + `decisions.md` (≈ 4 KB each) |

Shared method and report contract shrank only modestly (≈ 39 KB to 34 KB with the skill); the savings come from not loading rule bodies wholesale. Rule text itself is unchanged. Runtime and token savings from 0.5.0 need comparative eval runs.
