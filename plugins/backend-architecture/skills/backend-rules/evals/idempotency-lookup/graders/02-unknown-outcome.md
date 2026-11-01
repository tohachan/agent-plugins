---
type: llm
focus: trace
weight: 1
---

Treats a timeout as an unknown outcome rather than a failed charge: recommends persisting intent/pending state and querying or safely retrying under the provider's idempotency contract, instead of only adding more retries.
