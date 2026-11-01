# backend-architecture

Audit existing backends and design new ones with evidence-calibrated rules, critical-flow verification, a mandatory coverage inventory and one shared scored report format.

## Skills and agents

| Skill | Use it for | Example |
| --- | --- | --- |
| `backend-rules` | Checking code or a question against one area's rules, without a report. Loads only that area. | "сверься с правилами идемпотентности в charge.go" · `/backend-rules IDEM-BP-13` |
| `backend-audit` | Reviewing code, a repo, infra/config or an architecture doc: one area, several, or all. | `/backend-audit all ./services/orders` · "проверь конкурентность и идемпотентность" |
| `backend-design` | Designing a system, service or feature, or applying a pattern. | `/backend-design notification service, 5M users` · "как сделать идемпотентные вебхуки?" |

A full audit follows `shared/full-audit.md`: fixed passes (inventory → critical flows → four area-group passes → domain passes → coverage gate → report), a work file that holds the inventory and ledger across context compaction, and — when the Agent tool is available — parallel `backend-reviewer` agents per pass plus `backend-verifier` agents that independently try to refute every High/Critical candidate and critical strength. Without subagents the same passes run sequentially, each persisted before the next.

## Areas (13)

API · DATA · CACHE · MSG · CONC · IDEM · RES · SCALE · PERF · SEC · OBS · ARCH · OPS. Each is `knowledge/<prefix>/` with `decisions.md` (key decisions, for design), `checks.md` (audit checklist, for audit) and `rules.md` (`XX-BP/BAD/AP-n` bodies, looked up by ID). Reports cite the IDs. Index and aliases: `knowledge/README.md`.

## Token budget

Reading is by need, not by file: design reads `decisions.md`, audit reads `checks.md`, and rule bodies are fetched by Grep on their ID. Approximate knowledge + method bytes loaded (≈ 4 bytes per token):

| Task | 0.3.0 | 0.4.0 |
| --- | --- | --- |
| One-area lookup (`backend-rules`, IDEM) | n/a — only a focused audit, ≈ 70 KB | ≈ 27 KB (README + `idem/rules.md`), no report |
| Focused audit, one area (IDEM) | ≈ 70 KB | ≈ 38 KB + looked-up rules |
| Full audit, single agent | ≈ 424 KB | ≈ 143 KB + looked-up rules |
| Full audit, lead with subagents | ≈ 424 KB in one context | ≈ 34 KB lead; each pass ≈ 32–44 KB in its own context |
| System design, ~8 areas | ≈ 39 KB + whole area files (≈ 30 KB each) | ≈ 31 KB + `decisions.md` (≈ 4 KB each) |

Shared method and report contract shrank only modestly (≈ 39 KB → 34 KB with the skill); the savings come from not loading rule bodies wholesale. Rule text itself is unchanged, so eval-tuned behavior is preserved.

## Output

Both report-producing skills follow `shared/report.md`: header, scorecard (assessed / partial / unverified / not applicable, numeric only when defensible), coverage (unit counts, domain modules, invariants with sources, gaps, index recommendation), F-n/R-n items, D-n decisions, plan, validation, open questions and a closing JSON summary (schema 2.1). Compact reports reduce prose, not the contract. Do not compare a design score with implemented readiness or treat an unverified score as zero.

## Layout

```
.claude-plugin/plugin.json
agents/               backend-reviewer.md, backend-verifier.md (full-audit passes)
knowledge/            README.md, sources.md, _TEMPLATE.md, <prefix>/{decisions,checks,rules}.md × 13
shared/               method.md (evidence & coverage), full-audit.md (pass protocol), report.md (contract)
scripts/              report/repository validators and contract tests (Python stdlib only)
evals/README.md       comparative behavioral evaluation protocol
skills/backend-{rules,audit,design}/SKILL.md (+ evals/)
```

To extend: add a rule to its owning area's `rules.md` as one line under its ID, cite it from a check in `checks.md` (or list it under "Also scan for"), and reference canonical mechanisms instead of duplicating them. New areas need a directory per `knowledge/_TEMPLATE.md`, an index row and the validator's area registry.

## Tests

```sh
python3 -B scripts/validate_repository.py
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B scripts/validate_report.py path/to/report.md --evidence-root path/to/audited/repository
```

The scripts use only the Python standard library (no third-party packages, network access or subprocesses); the validator reads files inside `--evidence-root` only. `skills/*/evals/` keeps the Claude plugin eval layout; scaffold scripts copy fixtures into a disposable directory. Follow [the evaluation protocol](evals/README.md) for baseline/revised comparisons and token measurements. Structural validation does not establish model quality.

## Changes in 0.4.0

Rule IDs, rule text, report schema (2.1) and scoring are unchanged. Breaking for anything that references paths: each `knowledge/<area>.md` is split into `knowledge/<prefix>/{decisions,checks,rules}.md`; shared/assessment-method.md → `shared/method.md` (delegation moved to `shared/full-audit.md`); shared/output-format.md → `shared/report.md`. New: `backend-rules` skill, `backend-reviewer` / `backend-verifier` agents, explicit full-audit protocol with a work file.
