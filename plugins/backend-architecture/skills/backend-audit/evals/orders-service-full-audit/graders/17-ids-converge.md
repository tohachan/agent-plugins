---
type: llm
focus: trace
weight: 1
---

Inspect the work file and the report. Candidates and strengths carry IDs `C-<pass>-<n>` and `S-<pass>-<n>` assigned when they were written to the work file. Every verdict (upheld, refuted, unresolved, out_of_scope), or the lead's recorded opposite-hypothesis re-read on the sequential path, is appended to the work file against the same ID. Every ID the report relies on (finding, strength, removed or downgraded item) appears in the work file with its verdict, and no verdict names an ID the work file lacks. An `unresolved` verdict leaves the item at confidence `likely` with an open question; a refuted strength becomes a new candidate with the verifier's evidence rather than vanishing. FAIL if IDs differ between work file and report, a verdict is missing from the work file, or a refuted strength was silently dropped.
