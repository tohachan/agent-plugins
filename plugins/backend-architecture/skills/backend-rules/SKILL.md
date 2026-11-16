---
name: backend-rules
description: Check code, a plan or a question against one backend area's rules — idempotency, retries/timeouts, caching, outbox, locks, transactions, auth, messaging and similar — without a scored report. Use when the user or an agent only needs to consult or verify against specific rules, e.g. "сверься с правилами идемпотентности", "is this retry loop OK", or a rule ID such as IDEM-BP-13. Loads only the matching area files. For a scored review with coverage use backend-audit; for a full system design use backend-design.
argument-hint: "<area | rule ID> [question or path]"
---

# Backend rules lookup

Plugin files live under `${CLAUDE_PLUGIN_ROOT}` (the plugin root, two levels above this skill directory); every `knowledge/` path below is under it, never in the target repository. Do not load `${CLAUDE_PLUGIN_ROOT}/shared/report.md` or `${CLAUDE_PLUGIN_ROOT}/shared/full-audit.md`; this skill produces no scorecard, coverage inventory, JSON or saved report.

1. **Locate.** A rule ID maps to its directory by prefix (`IDEM-BP-13` → `${CLAUDE_PLUGIN_ROOT}/knowledge/idem/`): Grep the ID (`` ^`IDEM-BP-13` ``, add `-A 3` for an `-AP-` rule) and skip to step 3. Otherwise map the request through the aliases in `${CLAUDE_PLUGIN_ROOT}/knowledge/README.md` to one area, at most three.
2. **Read one file per area**, by question type:
   - "how should it be done / is this right" → `rules.md`;
   - "verify this code or config" → `checks.md`, then Grep the cited rule IDs;
   - "which option" → `decisions.md`.
   Follow a cross-reference into another area by Grep on its ID, not by opening that area.
3. **Answer** briefly: for each point the applicable rule IDs, a verdict (holds / violated / unclear) with `file:line` when code was given, and the minimal fix. A rule is a hypothesis: before calling something missing, check whether a caller, schema constraint, middleware, gateway or provider contract already provides it, and say what remained unseen. Vendor limits and SDK defaults: `${CLAUDE_PLUGIN_ROOT}/knowledge/sources.md`.

If the question turns into a multi-area assessment or needs a score, say so and suggest `backend-audit` (or `backend-design`) rather than expanding here.
