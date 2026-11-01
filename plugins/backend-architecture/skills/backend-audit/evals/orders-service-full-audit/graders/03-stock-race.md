---
type: llm
focus: trace
weight: 1
---

The report flags the read-then-write stock update in CreateOrder (SELECT stock then UPDATE stock = value) as a lost-update/overselling race.
