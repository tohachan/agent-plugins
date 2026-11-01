---
type: llm
focus: trace
weight: 1
---

The report establishes that duplicate shipment inserts are possible from consumer.go AND the authoritative schema.sql (no unique order_id). It does not infer the absence of constraints from the INSERT alone. The fix provides durable uniqueness or an atomic inbox/effect transaction.
