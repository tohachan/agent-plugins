---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Change audit of Ship in example/service.go. The earlier audit of this service is prior/audit-a1b2c3d.json (revision a1b2c3d); the code in example/ is revision 9f8e7d6, the fix commit made after that audit. Use that audit as `prior`: for each of its items say whether it is new, still present, fixed (at which revision) or not applicable. The broker acknowledges only on nil and redelivers otherwise. Report in the shared format.

Input files: example/ prior/
