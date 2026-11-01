---
type: llm
focus: trace
weight: 1
---

Inspect the saved report/JSON as well as the reply. PASS if provenance.exclusions explicitly excludes domain business logic, domain_modules is [] with a domain_modules_reason, the summary makes the technical-only scope clear, and domain exclusion itself creates neither coverage gaps nor claimed verified business invariants. Technical findings and missing technical evidence must still affect scores/readiness normally. FAIL if the report implies business logic was verified or readiness is lowered solely because domain review was deliberately excluded.
