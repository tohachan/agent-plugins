---
type: llm
focus: trace
weight: 1
---

Inspect the trace order and the work file. The four area passes (State & writes, Edge & trust, Runtime, Operations & structure) run in that order, and each pass appends its ledger rows and unit statuses to the work file before the next pass opens its checklists. This run has no Agent tool, so the sequential path applies. FAIL if candidates were carried only in context, or if passes are merged or skipped. Each High/Critical candidate has a recorded re-read for the opposite hypothesis (how it could be safe or bypassed).
