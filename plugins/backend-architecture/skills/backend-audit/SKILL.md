---
name: backend-audit
description: Audit an existing backend service, repository, configuration or architecture document (not a single snippet or pattern question) for evidenced correctness, security, reliability and operability risks. Default is a triage of the 3–5 highest-impact risks with evidence and an honest list of what was not examined, with no numeric scores; `--full` runs the complete protocol with coverage inventory, scorecard and readiness. Use for "посмотри мой сервис", backend reviews, bottlenecks, concurrency, messaging and architecture assessment, "проверь архитектуру". Technical by default; business/domain logic is opt-in. Not for a pattern or "how should I" question (backend-rules) and not for designing new behavior (backend-design).
argument-hint: "[areas | all] [path] [--full] [--domain on|off]"
model: opus
effort: medium
---

# Backend audit

Plugin files live under `${CLAUDE_PLUGIN_ROOT}` (the plugin root, two levels above this skill directory); every `knowledge/`, `shared/` and `scripts/` path below is under it, never in the target repository. Read `${CLAUDE_PLUGIN_ROOT}/knowledge/README.md` and `${CLAUDE_PLUGIN_ROOT}/shared/method.md` once. Read `${CLAUDE_PLUGIN_ROOT}/shared/report.md` only when writing the report.

## 1. Scope and depth

Map the request / `$ARGUMENTS` through the index aliases and symptom table. Resolve domain scope per `${CLAUDE_PLUGIN_ROOT}/shared/method.md`: default `off`; `--domain on` or an explicit request to check business/domain logic enables it, `--domain off` excludes it. `all`, "full audit" and "проверь всё" alone keep it off.

**Depth is chosen before any inventory, from the request alone:**

- **Triage (default)** — any request without `--full`: an unstructured "look at my service", `all`, or explicit areas. Areas named in the request bound the triage; `all` or no areas means all 13 are candidates, but only the ones the critical flows touch are read. Continue with step 2.
- **Full** — `--full`, or an explicit request for a full, complete or exhaustive audit with coverage and scores ("полный аудит", "full audit with a scorecard"). Explicit areas make a focused full audit (follow steps 3–4 of this file, not `${CLAUDE_PLUGIN_ROOT}/shared/full-audit.md`); no areas or `all` makes the unfocused full audit: all 13 technical areas, plus domain passes only when enabled, following `${CLAUDE_PLUGIN_ROOT}/shared/full-audit.md` instead of steps 2–4 here.

Never switch depth by yourself. A large focused audit keeps its areas and its depth; it is not widened to all 13 areas and not promoted to a full audit.

**Quick count first.** Count what exists from the project's own artifacts, cheaply (route tables, registries, consumers and jobs, migrations, external clients; sections for a document): a listing or a grep, not a read of each unit. Record the counts; they size the triage, feed the inventory of a full audit and are not recomputed there. In triage, when the counts are large (roughly more than 30 entry points, or several services), or when the findings leave critical flows unexamined, say in the report that `--full` would pay off and why, without running it.

Record revision, environment, assumptions and unavailable evidence. The target may be code, configuration or an architecture document; for a document the units are its sections, claims and diagrams, and evidence is quoted text.

## 2. Triage

1. **System map** — entry points, modules/services, stores, brokers, external clients, deployment and trust boundaries, from the quick count and a skim: claims to verify, not findings.
2. **Critical flows** — pick the 3–5 whose failure is costliest (money, auth, data loss, ordering) and trace each end to end with file:line.
3. **Mechanism boundaries** — apply the mechanism boundaries of `${CLAUDE_PLUGIN_ROOT}/shared/method.md` to those flows; read the relevant areas' `${CLAUDE_PLUGIN_ROOT}/knowledge/<prefix>/checks.md` (apply the method's domain scope filter), and resolve cited rules by Grep on their ID, never by reading a whole `rules.md`. Check the opposite hypothesis before keeping a High/Critical candidate: the control's other plausible owners (callers, schema, middleware, gateway, provider contract).
4. **Findings** — the top risks, each with realistic impact, file:line evidence, a minimal fix and a verification, severity per `${CLAUDE_PLUGIN_ROOT}/shared/report.md`. A healthy system yields few or no findings; say so instead of padding. No numeric scores, no per-check ledger, no work file, no verifiers.
   With domain review enabled (`--domain on`), also read `${CLAUDE_PLUGIN_ROOT}/shared/domain-audit.md` and apply its checks to the traced flows; domain findings are ordinary findings, and the report omits the domain-off exclusion. Domain modules never examined go to the not-examined list.
5. **Not examined** — an honest list of what was not looked at and why (areas, units, runtime behavior, domain scope), plus the `--full` note from the quick count when it applies.

Report using the triage layout of `${CLAUDE_PLUGIN_ROOT}/shared/report.md` and render it as in step 5.

## 3. Trace and check (full, focused)

Build the coverage inventory (method, "Coverage inventory") from the quick count before checking: units from the project's own artifacts, domain sources only when enabled, a code index if present, prior audits of the same target. Document units (sections, claims) are valid units. Trace the critical flows in scope end to end. Read the selected areas' `${CLAUDE_PLUGIN_ROOT}/knowledge/<prefix>/checks.md` and apply the method's domain scope filter before resolving references; resolve each in-scope cited rule by Grep on its ID. Look up a rule to confirm or refute a candidate, not only after deciding to report it. Apply the method's mechanism boundaries and, when domain review is enabled, the relevant checks in `${CLAUDE_PLUGIN_ROOT}/shared/domain-audit.md`. Keep the ledger in the scratch work file; test high-impact hypotheses when feasible and record inspected versus executed.

## 4. Gate (full, focused)

Every in-scope unit has a terminal status. Before keeping a High/Critical candidate or a critical strength, re-read the code for the opposite hypothesis. Reconcile available prior High/Critical items for the same target and revision.

## 5. Judge, report, render

Apply `${CLAUDE_PLUGIN_ROOT}/shared/report.md`: realistic impact, minimal fix and verification per item; conditional severity (`severity_if`, `trigger`) for pending events; strengths instead of invented findings in a healthy area; unsupported hypotheses and owner decisions as open questions. A full audit scores and assesses readiness; a triage does neither.

- **One scratch directory per audit.** Create it once (`mktemp -d`) and keep in it the draft report and, in a full audit, the work file; the target repository gets neither, and the reviewers' "do not edit the target" stays true. The work file moves into the repository (`docs/audit/<name>.work.md`, beside the report) only when the user asks for it.
- **Record the models.** Fill `provenance.models` with one row per role that ran (lead, each reviewer, each verifier): the model and the `effort` requested, as the harness reported them (`unknown` when it did not say). `effort` is a request, not a measurement.
- **Judgments only in the JSON.** Give scores, statuses, coverage, items (with `priority` and optional `depends_on`), strengths, `unknowns` (material: what is unknown and why it matters) and `noted_unknowns`; the renderer computes counts, the overall score, flags, blockers and readiness, so do not type them. Put an unknown in `unknowns` only when it changes a critical promise; runtime behavior a source audit cannot see goes in `noted_unknowns`.
- **Render and validate before delivering:** write the narrative sections, render markers and closing JSON into the scratch draft, then run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_report.py <draft> --evidence-root <target repository root>` (always the plugin's script by this absolute path, whatever the working directory; never a `scripts/` copy in the target). Evidence references are relative to that root. **At most 3 runs:** fix the JSON each time. If the third still fails, deliver the draft marked `validation failed: <the errors>` (no `Schema validation:` line) and say so in the reply, instead of looping.
- **Save** a rendered report in a writable repository to `docs/audit/backend-audit-<slug>-<YYYY-MM-DD>.md` unless the user chooses otherwise; `<slug>` is the target's service or directory name lowercased to `[a-z0-9-]`, at most 40 characters (`orders-service`), the repository name for a whole repository. A file that exists is never overwritten: add `-2`, `-3`, … before `.md`. A read-only repository, or no repository, gets the report in the reply. Prior audits of the same target are the `docs/audit/backend-audit-<slug>-*.md` files (and legacy `backend-audit-<date>.md`); reconcile them as the gate says.
- **Chat summary:** depth, domain review on/off, the top risks, what was not examined and, for triage, whether `--full` is worthwhile; for a full audit also blockers, coverage gaps with the index recommendation, and the score. With domain off, say that business logic was excluded.
