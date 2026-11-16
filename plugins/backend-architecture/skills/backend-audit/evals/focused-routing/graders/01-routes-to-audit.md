---
type: llm
focus: trace
weight: 1
---

Inspect the trace. The backend-audit skill is invoked through the Skill tool (focused triage limited to retries and timeouts). FAIL if the request is answered without a Skill call, or is routed to backend-rules or backend-design.
