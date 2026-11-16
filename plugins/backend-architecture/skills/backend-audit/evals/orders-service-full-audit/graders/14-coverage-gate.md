---
type: llm
focus: trace
weight: 1
---

Inspect the work file and the report. Every in-scope unit has a terminal status; units nobody reached appear as gaps, not as silently dropped or claimed as covered. `sampled` appears only on read-only units, with the tier's sampling rule and denominator stated; no unit that writes money or state or crosses a trust boundary is sampled. The coverage gate is recorded as passed before any score is written, and readiness is not claimed as supported_in_scope when gaps remain.
