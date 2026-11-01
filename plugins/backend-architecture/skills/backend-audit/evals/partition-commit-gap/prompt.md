---
tags: [skill-creator]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash]
---

Проверь только безопасность обработки и commit offsets в consumer.go. У process есть атомарная дедупликация в БД. События из одной partition могут выполняться разное время. Учитывай kafka-go v0.4.51.

Input files: example/
