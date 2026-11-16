---
type: llm
focus: scope
weight: 1
---

It is a focused change audit, not a new mode: the audit stays within the changed paths (Ship) plus the prior's items, uses no `--since` style flag, and says what it did not re-check. A prior item outside the changed paths would be `not_rechecked` rather than guessed. Lookup and the broker adapter are not audited in depth.
