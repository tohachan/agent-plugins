# backend-architecture

Audit existing backend code and design new backend services against a rule base of best practices, bad practices and anti-patterns in 13 technical areas. An audit is by default a triage of the few highest-impact risks with evidence and an honest list of what was not examined; `--full` adds the coverage inventory and a scored report. A design records assumptions, decisions and a validation plan. Most rule text is not yet version-verified: `knowledge/sources.md` lists only five verified facts plus lookup starting points, so findings are evidence-backed claims about your code, not certified statements about every rule.

## Install

```text
/plugin marketplace add tohachan/agent-plugins
/plugin install backend-architecture@agent-plugins
```

For a local checkout use `/plugin marketplace add <path-to-repo>`, or load the plugin directly with `claude --plugin-dir ./plugins/backend-architecture`. Skills are then available as `/backend-rules`, `/backend-audit` and `/backend-design` (or namespaced `/backend-architecture:backend-audit` if a name clashes).

## Requirements

- Claude Code with plugin and marketplace support.
- Python 3 (standard library only, no minimum version tested) to validate and render reports with `${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py`. Without it the audit still runs, but report validation is skipped and the tables must be written by hand.
- The Agent tool is optional. With it, full audits run parallel `backend-reviewer` and `backend-verifier` agents; without it the same passes run sequentially in one session.
- No network access, third-party packages or subprocesses are needed by the scripts.

## Limits and not for

- Knowledge targets **Go and Node.js** services. Other stacks get the language-neutral rules, but the runtime-specific notes and examples do not apply.
- **Domain (business-logic) review is off by default**: `/backend-audit all` is a technical audit. Turn it on with `--domain on`; see Audit scope.
- Audits are **static analysis** of code, configuration and documents you point at. They do not observe a running system, load, real data or production behavior, and a clean report is not a production sign-off.
- The audit **reports and recommends; it does not edit or fix your code.**
- Product defaults, limits and SDK behavior must be checked against your actual versions (`${CLAUDE_PLUGIN_ROOT}/knowledge/sources.md`).
- Structural validation of the plugin does not establish model quality; no speedup or accuracy improvement is claimed.
- Not a penetration test, exploit validation or load test; security findings are code-level review claims.

## Skills and agents

| Skill | Use it for | Example |
| --- | --- | --- |
| `backend-rules` | A pattern or "how do I do X" question, or a check of code or a plan against one to three areas' rules, without a report. Loads only those areas and offers `backend-design` if the question grows into a whole system. | "как сделать идемпотентные вебхуки?" (how to make webhooks idempotent?) · "сверься с правилами идемпотентности в charge.go" (check idempotency rules in charge.go) · `/backend-rules IDEM-BP-13` |
| `backend-audit` | Reviewing code, a repo, infra/config or an architecture doc. Default: triage of the top risks, no numeric scores. `--full`: coverage inventory, scorecard, readiness. | "посмотри мой сервис" (look at my service) · `/backend-audit all ./services/orders` · `/backend-audit all ./services/orders --full` · "проверь конкурентность и идемпотентность" (audit concurrency and idempotency) |
| `backend-design` | Designing a whole system, service or multi-component feature: capacity arithmetic, assumptions, decisions, rollout, validation plan. Not a single pattern question. | `/backend-design notification service, 5M users` · "спроектируй сервис уведомлений" (design a notification service) |

A triage audit (the default) is one pass by the lead: quick unit count, system map, 3–5 critical flows traced, findings with evidence, a list of what was not examined and, when it would pay off, a note that `--full` is worthwhile. It never widens itself to a full audit. A full audit with no focus areas (`--full`) follows `${CLAUDE_PLUGIN_ROOT}/shared/full-audit.md`: fixed passes (inventory → critical flows → four area-group passes → optional domain passes → coverage gate → report), a work file that holds the inventory and ledger across context compaction, and — when the Agent tool is available — parallel `backend-reviewer` agents per pass plus `backend-verifier` agents that independently try to refute every High/Critical candidate and critical strength. Without subagents the same passes run sequentially, each persisted before the next.

Models: `backend-audit` (the lead that merges passes and judges) runs on `opus` at `medium` effort for its turn; `backend-reviewer` on `sonnet`/`medium`; `backend-verifier` on `opus`/`medium`, since refuting High/Critical claims is the narrowest and most consequential step. `backend-design` is pinned the same way (`opus`/`medium`); `backend-rules` sets no model and inherits the session's. Change the pinned ones in the frontmatter; a `model` passed on an Agent call would override the agents' setting, so the protocol forbids it.

## Terms

- **Coverage inventory**: the list of units (handlers, consumers, jobs, tables, entry points) found in scope and which of them were actually read.
- **Unit**: one item in that inventory.
- **Ledger**: the running record, kept in a work file, of candidate findings and their status across passes and context compaction.
- **Critical flow**: a path whose failure is costly (money, auth, data loss), verified end to end rather than file by file.
- **Critical strength**: a claimed strong point on such a flow; the verifier tries to refute it like a High/Critical finding.
- **Coverage gate**: the pass that checks the inventory before the report; unread units become explicit gaps.
- **Readiness** (full audit only): a verdict on a scope (for example `supported_in_scope`) that cannot be given while units remain uncovered.
- **Code index**: a graph, LSP references, ctags or Sourcegraph used to enumerate callers and writers; graphify is one such code-graph tool. Optional.

## Audit scope

```text
/backend-audit all .                  # triage of the top risks; domain review off by default
/backend-audit all . --full           # complete protocol with coverage and scores
/backend-audit all . --domain on      # include business rules and domain invariants
/backend-audit SEC ./api --domain off # explicitly technical, focused audit
```

An explicit natural-language request to check business/domain logic also enables it. `all` or "full audit" alone does not. Domain off skips business-policy discovery and domain reviewer passes; technical authorization enforcement, tenant isolation, transactions, retries and concurrency remain in scope. Reports show the exclusion and assess readiness only within technical scope. Domain instructions in `shared/domain-audit.md` load only when enabled; backend-design considers domain requirements only when the requirements name roles, money or approvals, and backend-rules follows the requested rule.

**Running the target's code.** Auditing someone else's repository and running its tests means executing its code. The agents `backend-reviewer` and `backend-verifier` have no Bash and only read; the lead agent runs tests or experiments one at a time, and only after you explicitly agree. Without agreement they are listed as proposed, not executed.

## Areas (13)

API · DATA · CACHE · MSG · CONC · IDEM · RES · SCALE · PERF · SEC · OBS · ARCH · OPS. Each is `knowledge/<prefix>/` with `decisions.md` (key decisions, for design), `checks.md` (audit checklist, for audit) and `rules.md` (`XX-BP/BAD/AP-n` bodies, looked up by ID). Reports cite the IDs. Index and aliases: `knowledge/README.md`.

Token-budget comparisons and version history are in [CHANGELOG.md](CHANGELOG.md).

## Output

The report-producing skills follow `${CLAUDE_PLUGIN_ROOT}/shared/report.md`. Tables, findings, decisions and validation are written once, in the closing JSON; `${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py` validates it and renders them into the Markdown at `<!-- render:… -->` markers. Three shapes, all with a closing JSON summary (schema 3.0): a **triage audit** (system map, critical flows, F-n findings, not-examined list; no scores, readiness or inventory), a **full audit** (header, scorecard that is numeric only when defensible, coverage with unit counts, domain modules, invariants and gaps, F-n items, plan, validation, open questions) and a **design** (requirements arithmetic, A-n assumptions registry, D-n decisions, R-n risks, V-n validation; no scorecard or readiness). Both skills accept an optional `prior: <report.json>` (an earlier audit or design of the same target), matched by `fingerprint`: an audit says per prior item whether it is new, still present, fixed at a revision or not applicable (a change audit is a focused audit over the changed paths plus `prior`); a design turns an audit's findings into requirements that its decisions close, with migration and rollback; an audit of a design checks its decisions and validation rows. Compact reports reduce prose, not the contract. Never treat an unverified score as zero.

## Layout

```
.claude-plugin/plugin.json
CHANGELOG.md
agents/               backend-reviewer.md, backend-verifier.md (full-audit passes)
knowledge/            README.md, sources.md, _TEMPLATE.md, <prefix>/{decisions,checks,rules}.md × 13
shared/               method.md (evidence & coverage), full-audit.md (pass protocol), domain-audit.md (opt-in domain checks), report.md (contract)
scripts/              report renderer, report/repository validators and tests (Python stdlib only)
evals/README.md       comparative behavioral evaluation protocol
skills/backend-{rules,audit,design}/SKILL.md (+ evals/)
```

To extend: add a rule to its owning area's `rules.md` as one line under its ID, cite it from a check in `checks.md` (or list it under "Also scan for"), and reference canonical mechanisms instead of duplicating them. New areas need a directory per `knowledge/_TEMPLATE.md`, an index row and the validator's area registry.

## Tests

```sh
python3 -B scripts/validate_repository.py
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B scripts/render_report.py path/to/report.md --evidence-root path/to/audited/repository   # validate + render
python3 -B scripts/validate_report.py path/to/report.md --evidence-root path/to/audited/repository   # validate only
```

The scripts use only the Python standard library (no third-party packages, network access or subprocesses); the validator reads files inside `--evidence-root` only, and the renderer writes only the report file it was given, after validation passes. `skills/*/evals/` keeps the Claude plugin eval layout; scaffold scripts copy fixtures into a disposable directory. Follow [the evaluation protocol](evals/README.md) for baseline/revised comparisons and token measurements. Structural validation does not establish model quality.

## Breaking changes

**0.6.0.** Report schema is 3.0 (2.1 reports are rejected and must be regenerated). `/backend-audit` without `--full` is now a triage with no numeric scores; add `--full` for the scorecard and coverage inventory. Design reports no longer carry a scorecard or readiness. `backend-design` is pinned to `opus`.

**0.5.0.**

`/backend-audit all` and "full audit" no longer include domain review. Add `--domain on` (or ask explicitly for business-logic review) to restore the previous scope. Details and earlier versions: [CHANGELOG.md](CHANGELOG.md).
