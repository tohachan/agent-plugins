---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

как сделать идемпотентную обработку вебхуков от платёжного провайдера? у нас Go + Postgres, пики ~200 rps, провайдер ретраит до 3 суток и может слать события не по порядку
