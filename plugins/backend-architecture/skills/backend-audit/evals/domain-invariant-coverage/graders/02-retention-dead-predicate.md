---
type: llm
focus: trace
weight: 2
---

The report finds that RET-1 is not enforced: PurgePhones only matches `phone = ''`, which no code path writes (deleted values are NULL, imported values are real numbers), so it never deletes anything, and ImportSpeakers loads phone numbers of speakers whose last event ended more than 6 months ago. It cites docs/policy.md as the obligation's source and does not mark retention as verified merely because a purge job exists.
