# Behavioral evaluation protocol

These cases test detection, restraint, repair correctness, routing and evidence calibration. Do not load eval prompts/graders during ordinary skill use.

## Running the cases

Run each case in a fresh disposable workspace. Scaffold scripts copy fixtures there; do not run them in a production repository. The shared orders-service fixture lives under `skills/backend-audit/evals/_fixtures/`; case directories refer to it rather than maintaining divergent copies.

Use the installed Claude plugin eval runner (see `claude plugin eval --help` for that version). The per-skill `evals/<case>/{case.yaml,prompt.md,graders/}` contract is retained. Capture final report artifacts and the workspace (work files included) as well as traces; a report saved to disk is not absent merely because chat has a short summary.

Graders judge substance: the correct decision, the trade-off, the failure scenario, the acceptance criterion, the evidence. They do not require a particular report layout, scorecard, readiness verdict or JSON block unless the case is explicitly about one. Run `python3 scripts/validate_report.py <report> --evidence-root <root>` separately where a report is produced; LLM graders are supplementary, not arithmetic/schema validators. `<root>` is the directory against which the report's `file:line` paths resolve: the workspace when paths read `orders-service/...`, the audited target directory when they are relative to it. Use the same root for the validator and the renderer.

## Cases

| Skill | Case | What it checks | Domain | Agent tool |
| --- | --- | --- | --- | --- |
| backend-audit | consumer-messaging-only | Focused request, default triage form (schema 3.0, no scores): messaging and idempotency only; no findings from other areas | off | no |
| backend-audit | domain-invariant-coverage | `--full` (schema 3.0, depth full). Coverage discipline in a neutral domain: guard missing in some writers, unreachable purge predicate, stranded workflow state, registry-derived coverage inventory | on | no |
| backend-audit | gateway-owned-auth | Traces a Node.js control through gateway configuration and deployment | off | no |
| backend-audit | healthy-boundaries | Healthy code: no invented High/Critical findings; valid inherited HTTP deadline preserved | off | no |
| backend-audit | incomplete-evidence | Withheld schema: unknowns stay open questions, no fabricated verification | off | no |
| backend-audit | orders-service-full-audit | `--full`. Full audit protocol (work file, ordered persisted passes, risk-tier coverage, ID convergence): coverage gate, domain=off, renderer run, plus the seeded defects | off | no (sequential path) |
| backend-audit | partition-commit-gap | A plausible but unsafe fix is rejected | off | no |
| backend-audit | split-dedup-transaction | Changing the transaction boundary and schema while preserving guarantees | off | no |
| backend-audit | technical-audit-default | `--full`. Domain review excluded by default, including delegated scope; seeded authorization finding kept | off (default) | yes |
| backend-audit | technical-audit-explicit-off | The same boundary in a focused SEC `--full` audit with `--domain off` | off | no |
| backend-audit | triage-routing | "Look at my service" routes to the triage audit, not the full protocol | off | no |
| backend-design | idempotent-payment-webhooks | A pattern question normally routes to backend-rules; here backend-design is invoked explicitly, so this tests the focused design form (decision with a rejected alternative, assumptions, Go sketch, residual risks, verification) | off | no |
| backend-design | notification-service-design | Full design: provider limits, estimates, decisions, risks, verification | off | no |
| backend-design | ordered-outbox-deltas | Ordered deltas through an outbox; crash and concurrent-relay scenarios | off | no |
| backend-design | small-catalog-monolith | Simplest design for a small load; no invented risk from team size | off | no |
| backend-design | unknown-provider-outcome | Unknown provider outcome; crash windows with acceptance conditions | off | no |
| backend-rules | idempotency-lookup | Single-area lookup finds the defect with rule IDs, no report, no other areas loaded | off | no |
| backend-rules | pattern-question-routing | A pattern question routes to backend-rules, bounded to 1-3 areas, with an offer to move to design | off | no |

## Notes on specific cases

- Report schema is 3.0. Without `--full`, a backend-audit request yields a triage (depth `triage`, no scores, no work file); the cases that test the scorecard, coverage inventory or readiness pass `--full` in their prompt, and the scoped or evidence-calibration cases (consumer-messaging-only, gateway-owned-auth, healthy-boundaries, incomplete-evidence, partition-commit-gap, split-dedup-transaction) grade substance in the triage form. `triage-routing` is the triage case.

- `orders-service-full-audit` runs without the Agent tool, so it exercises the sequential full-audit path; add a variant with `Agent` in `allowed_tools` to exercise the reviewer/verifier path, and compare both on recall and tokens.
- `triage-routing` and `pattern-question-routing` test routing and the target forms of the triage audit and the rules lookup; a skill version that still sends such requests to the full audit or to design will fail them.
- Keep additional real-project holdouts separate from tuning cases; expand Node.js and multi-service production coverage before claiming broad stack effectiveness.

## Comparing conditions

For a meaningful comparison use the same model/version, limits, tools, fixture and user prompt with (A) no backend skill, (B) previous plugin and (C) revised plugin. Keep the evaluator rubric identical and blind to condition. Use separate contexts and at least three runs per condition; record input/output/cached tokens, elapsed time and errors, not just a pass/fail average. Confirm traces actually loaded the intended skill. Do not include graders or expected answers in the task context.

Measure per-case supported defect recall, unsupported/false findings, minimal-fix correctness, treatment of unknowns and preserved guarantees. Healthy cases specifically penalize invented High/Critical findings. Aggregate separately by skill, scope and healthy/defective/incomplete context. Report raw counts, run variability and token cost per supported useful finding; a single composite score hides trade-offs. Count incomplete/failed runs rather than silently dropping them.

No baseline or improvement percentages are claimed by this repository. Record actual run results outside the skill-loading path with model/plugin versions and fixture hashes. Local deterministic checks validate the harness and report contract, not model effectiveness.
