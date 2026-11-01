---
name: backend-audit
description: Audit existing backend code, configuration or architecture for evidenced correctness, security, reliability and operability risks. Use for backend reviews, bottlenecks, concurrency, messaging and architecture assessment, including Russian requests such as "проверь архитектуру". Covers focused or full audits with the shared scorecard, coverage inventory and JSON report. For designing new behavior, use backend-design.
---

# Backend audit

Paths below are relative to the plugin root, two levels above this skill directory.
Read `knowledge/README.md`, `shared/assessment-method.md` and `shared/output-format.md` once.

## 1. Scope, inventory and domain sources

Map the request / `$ARGUMENTS` through the index aliases and symptom table. An explicit area limits the audit; an unfocused service/repository audit selects all 13 areas **and** the domain pass. Record the target revision, environment, assumptions and unavailable evidence.

Build one system map — entry points, modules/services, stores, brokers, external clients, deployment and trust boundaries — and treat it as claims to verify, not as findings.

Build the coverage inventory (method, "Coverage inventory") before checking anything:

- Enumerate the units in scope: entry points, authorization declarations, domain modules, stores, external dependencies and documented obligations. Count them from the project's own artifacts (contract, route table, action/permission registry, migrations).
- Locate the project's domain sources — specs, ADRs, contracts, policies, tests — and derive domain modules and invariants from them. The skill does not supply domain rules.
- Look for an existing code index (for example a graphify graph, LSP, ctags) and use it to enumerate writers and callers.
- Look for prior audits or reviews of the same target; plan to reconcile their High/Critical items.
- Plan coverage on both axes, areas × domain modules, so that every unit has exactly one owner pass. Walk enumerable registries completely; sample only what cannot be enumerated, with a stated rule and denominator.

Ask only for missing information that changes a material conclusion.

## 2. Trace and check

Trace critical flows end to end before scoring individual areas.

- **Area passes.** Read the selected knowledge files' **Audit checklist** and **Anti-patterns** sections, the method's mandatory boundary rules and relevant version notes. Open full rules to confirm or refute a candidate, not only after deciding to report it.
- **Domain passes.** For every domain module apply the method's domain checks: the privilege matrix including target = actor (SEC-CHK-21), one invariant enforced by every writer (SEC-CHK-22), separation of duties where the domain requires it (SEC-CHK-23), workflow liveness (IDEM-CHK-21) and documented obligations against code (DATA-CHK-21).
- **Ledger.** Maintain the shared check ledger. Distinguish a missing implementation from missing evidence and check alternative enforcement layers. An obligation is verified only against its cited source. Mixed code/infra checks are recorded in parts. Every strength names the boundary it was tested against. Test high-impact hypotheses when feasible and record inspected versus executed.

**Delegation** (only when authorized) follows the method's "Delegation and review independence":

- Split work by coverage units on both axes, not by areas alone.
- Give each reviewer its unit list, the domain sources, the system map as claims to verify, the report contract and a demand for a status per unit plus the bypass attempted behind each strength.
- Never characterise the code's quality in a brief.

## 3. Coverage gate (before judging)

Do not score until this gate passes:

1. **Merge inventories.** Every unit and domain module has an owner and a terminal status (`checked`, `sampled` with its rule, or `not_covered` with its reason). A unit nobody took is listed as a gap, never dropped.
2. **Name what was not enumerated.** When something is sampled or not covered, write the gaps and the index recommendation: what a deeper pass over an indexed codebase (for example a graphify graph) would enumerate. Readiness cannot be `supported_in_scope` while gaps remain.
3. **Re-verify independently.** Have every High/Critical candidate, and every strength that stands for a critical invariant, re-verified by someone other than the reviewer who recorded it. Give them the code and the claim, not the conclusion. Without delegation, the lead re-reads the code for the opposite hypothesis before keeping the item.
4. **Reconcile prior reports.** Classify each available prior High/Critical as reproduced, refuted, not applicable or unverifiable, with evidence. First confirm it concerns the same codebase and revision.

## 4. Judge and report

Apply the shared severity, coverage and scoring rules. Explain realistic impact, a minimal fix and how to verify it.

- Use conditional severity (`severity_if`, `trigger`) when a pending event raises the impact, and plan it as a gate.
- A healthy area needs strengths, not invented findings.
- Open questions carry unsupported hypotheses and owner decisions where the domain sources are silent.

Always use the shared report shape — header, scorecard, coverage, findings and closing JSON (schema 2.1); use its compact form for narrow requests.

- **Validate before delivering.** Run `python3 scripts/validate_report.py <report> --evidence-root <target>`. A report that fails validation is not finished.
- **Saving.** In a writable repository save to `docs/audit/backend-audit-<YYYY-MM-DD>.md` unless the user chooses otherwise; avoid overwriting a different audit from the same day. If saving is unavailable, return the complete report in the reply.
- **Chat summary.** Summarize blockers, coverage gaps (with the index recommendation) and the score.
