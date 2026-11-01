---
type: llm
focus: trace
weight: 1
---

The report identifies ReadMessage auto-commit before durable processing. Its fix commits only after success and never advances a partition past earlier unfinished messages; merely moving CommitMessages into concurrently finishing goroutines is not a correct fix.
