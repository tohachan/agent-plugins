---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Спроектируй отправку SMS через провайдера: Go + Postgres, 50 сообщений/с. Провайдер НЕ поддерживает idempotency key, поиск по нашему reference и webhooks статуса. После timeout неизвестно, отправлена ли SMS. Нужно выбрать политику восстановления и объяснить гарантии. Пользовательские дубликаты нежелательны, потеря OTP допустима с явным повторным запросом пользователя.
