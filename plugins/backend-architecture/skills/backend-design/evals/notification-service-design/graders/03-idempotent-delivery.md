---
type: llm
focus: trace
weight: 1
---

The design persists operation identity/intent and distinguishes confirmed, known-not-applied and unknown provider outcomes. It uses provider idempotency/status lookup where supported and states the duplicate-versus-loss trade-off where unavailable. Dedup before sending alone must NOT be credited as guaranteeing no duplicate external sends. Check the crash after provider acceptance but before local result persistence.
