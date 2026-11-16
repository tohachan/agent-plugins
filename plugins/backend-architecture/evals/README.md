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
| backend-audit | focused-routing | A request to check one area of concrete code ("only retries and timeouts in the payment client") routes to backend-audit as a focused triage, not to backend-rules or an inline answer | off | no |
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

The first measured run is below (one run per case per arm; no improvement percentage is claimed from n=1). Record actual run results outside the skill-loading path with model/plugin versions and fixture hashes. Local deterministic checks validate the harness and report contract, not model effectiveness.

## Measured results: A (no plugin) vs C (plugin), 2026-11-16

Method. Plugin under test: commit `64bcc08` (agp-integration). Model `claude-sonnet-5-5` for both arms (C's reviewer/verifier subagents keep their pinned models; Opus appears in C-agent). One run per case per arm, `claude -p --output-format json`, tools Read/Glob/Grep/Skill/Write/Edit/Bash (+Agent in the "with Agent" variant), fixture hash (orders-service) `a187e6f290d4`. Arm A runs with a clean config dir, no plugin dir, a locked `plugins/` directory (the account auto-syncs the plugin into any config dir, which leaked it into arm A in the first rounds; those rounds are discarded and not counted) and deny rules on arm A: no Read/Glob/Grep under `/home/agent/.claude`, `/Users/tohachen`, `/home/agent/.local`, and no Bash command mentioning `projects/agent-plugins`, `.claude/plugins`, `.claude/skills`, `/Users/tohachen`, `/.local/state`. Each output was graded by a fresh subagent per output (Sonnet), blind to arm, against the case's graders from the output text and fixture only. Raw runs: outside the repository (`eval-runs/`).

Counts. Recall = graders met / graders of the case (full audit: the 8 seeded-defect graders 01-08; the 9 protocol graders 09-17 are not scored from text, see below). False = claims the grader found wrong or unsupported. Useful = distinct correct findings or decisions. Tokens = input + output + cache creation + cache read, subagents included (`modelUsage`); "fresh" omits cache reads (fresh is skewed by cache warm-up between parallel runs, use total for comparison).

| Path | Case | Recall A | Recall C | False A / C | Useful A / C | Tokens A | Tokens C | Tokens per useful A / C |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | idempotency-lookup | 1/3 | 3/3 | 0 / 0 | 3 / 6 | 53.8k | 89.3k | 17.9k / 14.9k |
| focused audit | consumer-messaging-only | 3/5 | 3/5 | 0 / 0 | 6 / 7 | 53.9k | 58.3k | 9.0k / 8.3k |
| focused audit | gateway-owned-auth | 2/3 | 2/3 | 0 / 1 | 7 / 6 | 55.2k | 59.2k | 7.9k / 9.9k |
| focused audit | healthy-boundaries | 3/3 | 3/3 | 0 / 0 | 6 / 8 | 55.7k | 59.7k | 9.3k / 7.5k |
| design | unknown-provider-outcome | 2/3 | 3/3 | 0 / 1 | 10 / 10 | 22.1k | 45.7k | 2.2k / 4.6k |
| design | ordered-outbox-deltas | 3/3 | 3/3 | 2 / 2 | 9 / 9 | 23.6k | 130.1k | 2.6k / 14.5k |
| full audit, no Agent | orders-service-full-audit | 7/8 | 7/8 | 1 / 0 | 24 / 14 | 63.2k | 791.0k | 2.6k / 56.5k |
| full audit, with Agent | orders-service-full-audit | 7/8 | 7/8 | 0 / 1 | 24 / 13 | 68.3k | 2,639.3k | 2.8k / 203.0k |

Fresh tokens (without cache reads) for the full audit: A 17.8k / 16.6k; C 96.6k (no Agent) / 346.7k (with Agent, 7 subagents).

Reading.
- The plugin loaded its skill in 5 of 8 C runs. In all three focused-audit cases (consumer-messaging-only, gateway-owned-auth, healthy-boundaries) the C transcript shows no Skill call, so C answered without the plugin's knowledge; recall is equal there (tokens, false and useful counts differ by run-to-run noise). With n=1 this is a signal of a routing miss, not a rate.
- Rules and design: C scored higher on two single cells (idempotency-lookup 3/3 vs 1/3: A gave no rule IDs and did not treat a timeout as unknown; unknown-provider-outcome 3/3 vs 2/3: A gave no test plan). Elsewhere both arms are equal.
- Full audit: both arms find the same 7 of 8 seeded defects (both miss the partition-prefix commit fix, 07). C costs 12.5x (no Agent) and 38.6x (with Agent) the tokens of A. Graders saw only the final text, so the protocol graders 09-17 were not scored for either arm. By trace, C wrote a work file, ran passes (sequentially, or via 4 reviewers and 3 verifiers with Agent), rendered and validated the report; the A transcripts show none of this and the answers are hand-written tables.
- n=1 per cell: differences of one grader item or one false finding are noise. No ambiguous result was rerun.
