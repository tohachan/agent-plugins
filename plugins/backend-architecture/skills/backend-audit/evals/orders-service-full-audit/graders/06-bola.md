---
type: llm
focus: trace
weight: 1
---

The report flags that GetOrder returns any order by id without checking ownership or authentication (BOLA / missing authz), and that admin search has no auth.
