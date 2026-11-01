---
type: llm
focus: correctness
weight: 2
---

Identifies that a new idempotency key is generated per retry attempt, so a timed-out charge that actually succeeded is charged again; the fix derives the key from a persisted operation identity (e.g. the invoice) and reuses it across attempts and recovery. Cites IDEM-BP-12 and/or IDEM-BP-13 (IDEM-BAD-3 also acceptable).
