---
type: llm
focus: trace
weight: 1
---

Inspect the trace. The agent ran render_report.py (which validates before rendering) against the report with the target as evidence root, saw it succeed, and the delivered report is the rendered file. FAIL if the tables were typed by hand, if the renderer failed and the run still delivered, or if no run is visible in the trace. The correctness of the rendered tables is not graded here.
