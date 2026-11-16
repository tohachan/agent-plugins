---
type: llm
focus: trace
weight: 1
---

Inspect the trace and the workspace. Before the first area check, a work file `work.md` is created in the audit's scratch directory (not in the target repository unless the user asked). It records domain=off and the scope exclusions, the system map, the 3-5 critical flows with file:line, and the unit inventory with a risk tier (writes-state / trust-boundary / read-only) for every unit, a recorded sampling rule for the read-only tier if it is sampled, and the full unit list available to each pass. PASS only if the file exists and these parts are present; FAIL if it is created after findings were already written, or only at the end.
