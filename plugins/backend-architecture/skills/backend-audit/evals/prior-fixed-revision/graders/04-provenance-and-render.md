---
type: llm
focus: format
weight: 1
---

The closing JSON pins the prior in provenance.prior with the prior report's own values (source prior/audit-a1b2c3d.json, mode audit, revision a1b2c3d, date 2026-11-01) while provenance.revision is 9f8e7d6, and carries prior_verdicts with exactly one entry per prior item (F-1 fixed, F-2 still_present), each with the prior fingerprint copied exactly. The report was rendered with `render_report.py <draft> --evidence-root <target repository root> --prior prior/audit-a1b2c3d.json` and passed, the prior marker is rendered, and the rendered verdict table says "fixed at 9f8e7d6". FAIL if the prior's revision is missing from provenance or the validator was not run with --prior.
