---
type: llm
focus: trace
weight: 1
---

Finds that the inbox insert commits outside the business transaction. A crash/failed shipment after inbox insertion makes retry skip the effect permanently. Fix places marker and effect in the same transaction.
