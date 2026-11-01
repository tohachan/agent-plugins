---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Проверь только эффективный timeout в Lookup и идемпотентность Ship. Схема приложена и является полной для этих таблиц. Client создаётся через New, Lookup — единственное место HTTP-вызова. Адаптер очереди подтверждает сообщение только после nil из Ship. В этой задаче достаточно статического разбора; продовые метрики не предоставлены.

Input files: example/
