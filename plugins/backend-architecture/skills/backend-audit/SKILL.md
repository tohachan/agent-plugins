---
name: backend-audit
description: Audit existing backend code, configuration or architecture for evidenced correctness, security, reliability and operability risks. Use for backend reviews, bottlenecks, concurrency, messaging and architecture assessment, including Russian requests such as "проверь архитектуру". Covers focused or full audits with the shared scorecard, coverage inventory and JSON report. For a quick check against one area's rules without a report, use backend-rules; for designing new behavior, use backend-design.
argument-hint: "[areas | all] [path]"
---

# Backend audit

Paths are relative to the plugin root, two levels above this skill directory. Read `knowledge/README.md` and `shared/method.md` once. Read `shared/report.md` only when writing the report.

## 1. Scope

Map the request / `$ARGUMENTS` through the index aliases and symptom table.

- **Focused audit** — explicit areas or one mechanism: only those areas. Continue below.
- **Full audit** — an unfocused service/repository audit, `all`, or an inventory too large for one pass: all 13 areas plus the domain pass. Follow `shared/full-audit.md` (fixed passes, work file, subagents when available, coverage gate) instead of steps 2–3 here.

Record revision, environment, assumptions and unavailable evidence. Build the system map — entry points, modules/services, stores, brokers, external clients, deployment and trust boundaries — as claims to verify, not findings. Build the coverage inventory (method, "Coverage inventory") before checking anything: count units from the project's own artifacts, locate domain sources, use a code index if present, look for prior audits of the same target. Ask only for missing information that changes a material conclusion.

## 2. Trace and check (focused)

Trace the critical flows in scope end to end. Read the selected areas' `knowledge/<prefix>/checks.md`; resolve each cited rule by Grep on its ID, never by reading a whole `rules.md`. Look up a rule to confirm or refute a candidate, not only after deciding to report it. Apply the method's mechanism boundaries and, where domain modules are in scope, its domain checks. Keep the ledger; test high-impact hypotheses when feasible and record inspected versus executed.

## 3. Gate (focused)

Every in-scope unit has a terminal status. Before keeping a High/Critical candidate or a critical strength, re-read the code for the opposite hypothesis. Reconcile available prior High/Critical items for the same target and revision.

## 4. Judge and report

Apply `shared/report.md`: realistic impact, minimal fix and verification per item; conditional severity (`severity_if`, `trigger`) for pending events; strengths instead of invented findings in a healthy area; unsupported hypotheses and owner decisions as open questions. Use the compact form for narrow requests.

- **Validate before delivering:** `python3 scripts/validate_report.py <report> --evidence-root <target>`. A failing report is not finished.
- **Save** in a writable repository to `docs/audit/backend-audit-<YYYY-MM-DD>.md` unless the user chooses otherwise, without overwriting a different audit of the same day; otherwise return the full report in the reply.
- **Chat summary:** blockers, coverage gaps with the index recommendation, and the score.
