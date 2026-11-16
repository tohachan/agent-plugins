# Changelog

## 0.6.0

**Breaking: report schema 3.0.** Schema 2.1 reports are rejected by `validate_report.py`; regenerate them.

- Design (`mode: design`) has its own contract: requirements arithmetic, an assumptions registry (assumption, threshold at which the choice changes, how to check it), D-n decisions, R-n risks and V-n validation. It carries no scorecard, readiness verdict or coverage inventory, so a design report no longer needs impossible `passed` validation to be valid. The renderer fills the assumptions, decisions, risks and validation blocks.
- `backend-design` reads `shared/domain-audit.md` only when the requirements name privileged roles, money, approvals or retention obligations; the SEC-BP-21, DATA-BP-21 and IDEM-BP-21 paragraph is gone from its decide step.
- `backend-design` is pinned to `opus`/`medium` like `backend-audit`, so model pinning is symmetric across the two report-producing skills.
- Audit reports carry `depth: "full"` (today's contract, unchanged apart from the version).

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
