---
type: llm
focus: trace
weight: 1
---

The answer stays focused on the webhook question and does not expand into a full system design. It states the chosen approach, at least one rejected alternative with the reason, the conditions under which the choice should be revisited, and the residual risks that actually follow from the stated constraints (3-day retries, out-of-order events, ~200 rps). No risk is invented to fill a template, and no scorecard, readiness verdict or fixed JSON schema is required for the answer to pass.
