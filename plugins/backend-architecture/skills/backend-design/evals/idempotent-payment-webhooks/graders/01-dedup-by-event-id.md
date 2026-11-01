---
type: llm
focus: trace
weight: 1
---

Durable ingress dedup uses provider event identity and retains payload/work state before acknowledging. The processing business effect and processed marker are atomic or otherwise demonstrably idempotent. Do not require ingress acceptance and later async processing to share one long transaction. Retention covers the stated three-day retries and documented redrive scope.
