---
name: backend-rules
description: Answer a backend pattern or "how should I do X" question, or check code or a plan against the rules of one to three areas (idempotency, retries/timeouts, caching, outbox, locks, transactions, auth, messaging and similar), without a report. Use for questions such as "как сделать идемпотентные вебхуки?", "is this retry loop OK", "сверься с правилами идемпотентности" or a rule ID such as IDEM-BP-13. Loads only the matching area files and offers backend-design when the question grows into a whole system. Not for designing a whole system or service with several components (backend-design) and not for reviewing a service or repository (backend-audit).
argument-hint: "<area | rule ID> [question or path]"
---

# Backend rules lookup

Plugin files live under `${CLAUDE_PLUGIN_ROOT}` (the plugin root, two levels above this skill directory); every `knowledge/` path below is under it, never in the target repository. Do not load `${CLAUDE_PLUGIN_ROOT}/shared/report.md` or `${CLAUDE_PLUGIN_ROOT}/shared/full-audit.md`; this skill produces no scorecard, coverage inventory, JSON or saved report.

1. **Locate.** A rule ID maps to its directory by prefix (`IDEM-BP-13` → `${CLAUDE_PLUGIN_ROOT}/knowledge/idem/`): Grep the ID (`` ^`IDEM-BP-13` ``; a check as `` ^\| IDEM-CHK-3 \| ``; every rule body is one line, so no context flag is needed) and skip to step 3. Otherwise map the request through the aliases in `${CLAUDE_PLUGIN_ROOT}/knowledge/README.md` to 1–3 areas; a question that needs more is not a lookup (see the end).
2. **Read one file per area**, by question type:
   - "how should it be done / is this right" → `rules.md`;
   - "verify this code or config" → `checks.md`, then Grep the cited rule IDs;
   - "which option" → `decisions.md`.
   Follow a cross-reference into another area by Grep on its ID, not by opening that area.
3. **Answer** briefly: for each point the applicable rule IDs, a verdict (holds / violated / unclear) with `file:line` when code was given, and the minimal fix. A rule is a hypothesis: before calling something missing, check whether a caller, schema constraint, middleware, gateway or provider contract already provides it, and say what remained unseen. Vendor limits and SDK defaults: `${CLAUDE_PLUGIN_ROOT}/knowledge/sources.md`.

A pattern question ("how do I make webhooks idempotent?") is answered here: the approach, rule IDs, the main trade-off and what would change the choice; no report. End it with one line offering `backend-design` when the user wants the whole system designed (components, capacity, rollout, validation plan) and do not start that design unprompted. If the question spans more than three areas or asks for an assessment of an existing service, say so and suggest `backend-design` or `backend-audit` rather than expanding here.
