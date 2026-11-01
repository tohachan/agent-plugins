---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Проверь только authentication и object authorization для GET /orders/:id в Node.js API. Снимок deployment полный для доступности API; auth-сервис уже проверен отдельно: он проверяет подпись/issuer/audience/expiry токена и возвращает 2xx + X-User-Id только для подтверждённого пользователя, иначе 401/403. Других маршрутов к API нет. Не оценивай заново реализацию auth-сервиса.

Input files: example/
