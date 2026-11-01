---
type: llm
focus: trace
weight: 1
---

The design separates snapshot replacement from transition/delta processing. It prevents invalid transitions or skipped deltas with predecessor checks/gap recovery or authoritative refetch. Event wall-clock time alone does not prove causal order.
