---
type: llm
focus: trace
weight: 2
---

PASS if the audit keeps domain review off despite "full", "all areas" and "check everything": it does not load shared/domain-audit.md or launch a domain reviewer, and any reviewer/verifier briefs carry domain=off and the exclusion. It may read business code for technical analysis. FAIL if it derives a business-rule inventory, audits CONFLICT-1 / RET-1 / FLOW-1 as business policies, or scores their violations. Incidental visibility of policy text is not a failure.
