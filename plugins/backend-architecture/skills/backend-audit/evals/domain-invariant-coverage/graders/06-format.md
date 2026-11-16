---
type: llm
focus: output
weight: 1
---

The closing JSON uses schema_version 3.0 and `depth: "full"` and passes `python3 scripts/validate_report.py <report> --evidence-root <target repository root>` (evidence references are relative to that root); counts, overall score, blockers and readiness are written by the renderer, not typed by the model; readiness is `blocked` because of the High conflict and retention findings.
