# backend-architecture

Audit existing backends and design new ones with evidence-calibrated rules, critical-flow verification and one shared scored report format. Version 0.3.0 keeps all existing rule IDs and adds coverage discipline: a mandatory coverage inventory (every entry point, authorization declaration, domain module, store and documented obligation has exactly one owner pass and a terminal status), two-axis coverage (cross-cutting areas × the target's own domain modules), a domain pass whose invariants come from the target's specs rather than from the skill, a coverage gate with independent re-verification before judging, conditional severity, and an explicit index recommendation (for example a graphify code graph) whenever enumeration was incomplete.

## Skills

| Skill | Use it for | Example |
| --- | --- | --- |
| `backend-audit` | Reviewing code, a repo, infra/config, or an architecture doc. One area, several, or all. | `/backend-audit all ./services/orders` · "проверь конкурентность и идемпотентность в этом репо" |
| `backend-design` | Designing a system, service or feature, or applying a pattern to your system. | `/backend-design notification service, 5M users` · "как сделать идемпотентные вебхуки?" |

## Areas (13)

API design · Data storage & transactions · Caching · Queues & messaging · Concurrency · Idempotency & consistency · Resilience · Scalability · Performance · Security · Observability · Architecture styles & boundaries · Delivery & operations.

Each area is one file in `knowledge/` with the same sections: key decisions, best practices (`XX-BP-n`), bad practices (`XX-BAD-n`), anti-patterns (`XX-AP-n`), audit checklist (`XX-CHK-n`), Go/Node.js notes. Reports cite these IDs. Index and aliases: `knowledge/README.md`.

## Output

Both skills follow `shared/output-format.md`:

- header table (mode, target, areas, date, overall score, confidence);
- scorecard: each area assessed, partial, unverified or not applicable, with a numeric score only when defensible; the shared format is the single source for scoring and caps;
- coverage: unit counts by kind (checked / sampled / not covered, with owner passes), domain modules, domain invariants with their sources, gaps and the index recommendation;
- items in one schema — audit findings `F-n`, design residual risks `R-n` — with severity, rule IDs, evidence, impact, fix, effort;
- design decisions `D-n` with options, trade-offs and revisit triggers;
- plan, validation/acceptance criteria, open questions, and a closing JSON summary with revision, scope and coverage for qualified comparisons over time.

Header, scorecard and JSON remain mandatory even for focused questions. Compact reports reduce prose and unrelated checks, not the reporting contract. JSON schema 2.1 keeps every 2.0 field and adds the mandatory `coverage_inventory`, optional conditional severity and prior-report reconciliation; the validator rejects 2.0 reports, which must be regenerated. Consumers must recognize the version and null-score semantics. In particular, do not compare a proposed design score with implemented production readiness or treat an unverified score as zero.

## Layout

```
.claude-plugin/plugin.json
knowledge/            README.md, 13 area files, sources.md, _TEMPLATE.md
shared/               assessment-method.md + output-format.md
scripts/              report/repository validators and contract tests
evals/README.md        comparative behavioral evaluation protocol
skills/backend-audit/SKILL.md   (+ evals/)
skills/backend-design/SKILL.md  (+ evals/)
```

To extend: add a rule to its owning area, cite its applicability and evidence, and reference canonical mechanisms instead of duplicating them. New areas also require index registration and updating the validator's area registry. The source register distinguishes verified facts from references still requiring version checks.

## Tests

Run deterministic checks (Python standard library only):

```sh
python3 -B scripts/validate_repository.py
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B scripts/validate_report.py path/to/report.md --evidence-root path/to/audited/repository
```

`skills/*/evals/` retains the Claude plugin eval layout. Use disposable working directories; scaffold scripts write fixture files. Follow [the evaluation protocol](evals/README.md) for same-model baseline/revised comparisons, false-positive scoring and token measurements. Eval material and validators are not loaded as ordinary knowledge. Structural validation does not establish model quality or runtime correctness.
