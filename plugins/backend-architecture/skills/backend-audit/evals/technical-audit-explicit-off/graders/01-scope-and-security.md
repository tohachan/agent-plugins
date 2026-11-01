---
type: llm
focus: trace
weight: 2
---

PASS if the audit remains focused on SEC, does not load shared/domain-audit.md, excludes business self-approval/separation-of-duties policies, and still finds the technical authorization bypass in DeleteTalk (delete.go ignores Caller and deletes arbitrary IDs without any other enforcement). The saved report must state domain exclusion, use empty domain_modules with a reason and avoid declaring domain policies verified or penalizing their deliberate exclusion. FAIL if explicit --domain off is ignored, technical authorization is skipped, or the scope expands to all areas/domain policies.
