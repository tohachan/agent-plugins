---
type: llm
focus: trace
weight: 1
---

Inspect the trace and the workspace. Before the first area check, a work file docs/audit/backend-audit-<date>.work.md (or a scratch equivalent) is created. It records domain=off and the scope exclusions, the system map, the 3-5 critical flows with file:line, and the unit inventory with an owning pass for every unit. PASS only if the file exists and these parts are present; FAIL if it is created after findings were already written, or only at the end.
