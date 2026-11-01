---
type: llm
focus: trace
weight: 1
---

Identifies that committing a later finished record advances past earlier unfinished records of the same partition, even with bounded concurrency and per-message dedup.
