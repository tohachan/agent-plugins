---
type: llm
focus: trace
weight: 1
---

The report flags that the DB write and the Kafka publish are a dual write without an outbox (event can be lost or published for a failed flow).
