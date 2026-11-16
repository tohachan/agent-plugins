---
type: llm
focus: trace
weight: 1
---

The report gives the prior item F-1 (inbox marker committed outside the effect's transaction, fingerprint example:Ship:inbox-insert-outside-effect-transaction) the verdict `fixed` with `fixed_at` 9f8e7d6, shown as "fixed at 9f8e7d6", and evidence of the new code: service.go:29, where the marker is now inserted with tx.ExecContext inside the transaction that also writes the shipment. FAIL if F-1 is reported as still present or as a new finding, if the verdict rests only on the prior report's text or on the commit message rather than on a reading of service.go, or if fixed_at is missing.
