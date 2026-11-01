---
type: llm
focus: trace
weight: 1
---

Does not report a missing effective timeout merely because http.Client.Timeout is zero; traces the 2-second context into NewRequestWithContext and Do.
