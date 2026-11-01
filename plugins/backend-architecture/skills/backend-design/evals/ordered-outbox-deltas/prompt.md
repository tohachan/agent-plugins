---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Предложи протокол outbox relay для изменения остатков: Postgres, два relay-воркера с SKIP LOCKED, Kafka key=sku. События — delta, имеют последовательную версию для sku. Восстановление после падения и порядок важны. Укажи, достаточно ли ключа и UPDATE WHERE version < incoming_version, и дай проверку выбранного решения.
