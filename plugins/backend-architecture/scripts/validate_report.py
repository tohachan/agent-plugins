#!/usr/bin/env python3
"""Validate report arithmetic and evidence metadata, not architectural truth."""
import argparse
from collections import Counter
from datetime import date
import math
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SEVERITIES = ('critical', 'high', 'medium', 'low')
AREAS = {'API', 'DATA', 'CACHE', 'MSG', 'CONC', 'IDEM', 'RES', 'SCALE', 'PERF', 'SEC', 'OBS', 'ARCH', 'OPS'}

RANK = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
UNIT_STATUSES = ('checked', 'sampled', 'not_covered')
LEDGER_STATUSES = ('verified', 'violation', 'unverified', 'not_applicable')
PRIOR_VERDICTS = ('reproduced', 'refuted', 'not_applicable', 'unverifiable')
PRIORITIES = ('now', 'next', 'later')
RISK_TIERS = ('read-only', 'writes-state', 'trust-boundary')
SAMPLED_TIER = 'read-only'
EVIDENCE_REF = re.compile(r'([^\s:]+):(\d+)(?:-(\d+))?')  # a file citation: no whitespace in the path ('RFC 9110:15' is a document citation)

def derive(report):
    """Fill the fields the contract computes from the judgments (full audit only): area counts, the overall
    mean/cap/flags/blockers and readiness. The renderer calls it before validating; the validator never does."""
    if not isinstance(report, dict) or report.get('mode') != 'audit' or report.get('depth') != 'full': return
    areas, items, validation = report.get('areas'), report.get('items'), report.get('validation', [])
    if not all(isinstance(v, list) and all(isinstance(x, dict) for x in v) for v in (areas, items, validation)): return
    if not isinstance(report.get('overall', {}), dict): return
    counts = {a.get('id'): Counter() for a in areas if isinstance(a.get('id'), str)}
    for i in items:
        if i.get('area') in counts and i.get('severity') in SEVERITIES: counts[i['area']][i['severity']] += 1
    inputs, provisional = [], False
    for a in areas:
        if a.get('id') not in counts: continue
        a['counts'] = None if a.get('status') == 'not_applicable' else {k: counts[a['id']][k] for k in SEVERITIES}
        provisional |= a.get('status') in ('partial', 'unverified')
        if a.get('status') not in ('unverified', 'not_applicable') and type(a.get('score')) in (int, float) and math.isfinite(a['score']): inputs.append(a['score'])
    o = report.setdefault('overall', {})
    critical = any(i.get('severity') == 'critical' for i in items)
    raw = (sum(Decimal(str(x)) for x in inputs) / len(inputs)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP) if inputs else None
    o['score'] = float(min(raw, Decimal('4.0')) if critical else raw) if raw is not None else None
    o.update(score_inputs=inputs, denominator=len(inputs), capped=critical, provisional=provisional)
    found = [str(i.get('id')) for i in items if i.get('severity') in ('critical', 'high')]
    extra = [b for b in o.get('blockers', []) if b not in found] if isinstance(o.get('blockers'), list) else []
    o['blockers'] = found + extra
    if not inputs: o['confidence'] = None
    ci = report.get('coverage_inventory')
    ci = ci if isinstance(ci, dict) else {}
    uncovered = any(isinstance(u, dict) and type(u.get('not_covered')) is int and u['not_covered'] > 0 for u in ci.get('units') or []) \
        or any(isinstance(m, dict) and m.get('status') == 'not_covered' for m in ci.get('domain_modules') or [])
    if o['blockers'] or any(v.get('status') == 'failed' for v in validation): o['readiness'] = 'blocked'
    elif provisional or o.get('unknowns') or uncovered or not inputs or not all(v.get('status') == 'passed' for v in validation): o['readiness'] = 'undetermined'
    else: o['readiness'] = 'supported_in_scope'

def coverage_inventory(report, require, strings):
    """Check the coverage inventory; return True when anything in scope is not covered."""
    ci = report.get('coverage_inventory')
    if not isinstance(ci, dict):
        require(False, 'coverage_inventory object required in a full audit')
        return True
    def text(v): return isinstance(v, str) and bool(v.strip())
    def count(v): return type(v) is int and v >= 0
    units = ci.get('units')
    require(isinstance(units, list) and bool(units), 'coverage_inventory.units must be a nonempty array')
    units = units if isinstance(units, list) else []
    uncovered, sampled = False, False
    for u in units:
        if not isinstance(u, dict):
            require(False, 'coverage unit must be an object'); continue
        kind = u.get('kind')
        require(text(kind), 'coverage unit kind required')
        nums = [u.get(k) for k in ('total', 'checked', 'sampled', 'not_covered')]
        if not all(count(n) for n in nums):
            require(False, f'coverage unit {kind}: total/checked/sampled/not_covered must be non-negative integers'); continue
        total, checked, samp, nc = nums
        require(checked + samp + nc == total, f'coverage unit {kind}: checked + sampled + not_covered must equal total (no unassigned units)')
        require(text(u.get('owner')), f'coverage unit {kind}: owner pass required')
        require(u.get('risk_tier') is None or u['risk_tier'] in RISK_TIERS, f'coverage unit {kind}: risk_tier must be one of {", ".join(RISK_TIERS)}')
        if samp:
            require(text(u.get('sampling')), f'coverage unit {kind}: sampling rule and denominator required')
            require(u.get('risk_tier') == SAMPLED_TIER, f'coverage unit {kind}: sampled applies only to risk_tier {SAMPLED_TIER}; units that write state or money or cross a trust boundary are checked or not_covered')
        uncovered |= nc > 0
        sampled |= samp > 0
    modules = ci.get('domain_modules')
    require(isinstance(modules, list), 'coverage_inventory.domain_modules array required')
    modules = modules if isinstance(modules, list) else []
    if not modules:
        require(text(ci.get('domain_modules_reason')), 'empty domain_modules needs domain_modules_reason')
    for m in modules:
        if not isinstance(m, dict):
            require(False, 'domain module must be an object'); continue
        require(text(m.get('id')) and text(m.get('owner')), 'domain module id and owner required')
        require(m.get('status') in UNIT_STATUSES, f'domain module {m.get("id")}: status must be checked/sampled/not_covered')
        uncovered |= m.get('status') == 'not_covered'
        sampled |= m.get('status') == 'sampled'
        if m.get('status') == 'sampled': require(m.get('risk_tier') == SAMPLED_TIER, f'domain module {m.get("id")}: sampled applies only to risk_tier {SAMPLED_TIER}')
    invariants = ci.get('invariants')
    require(isinstance(invariants, list), 'coverage_inventory.invariants array required')
    invariants = invariants if isinstance(invariants, list) else []
    if not invariants:
        require(text(ci.get('invariants_reason')), 'empty invariants needs invariants_reason')
    for inv in invariants:
        if not isinstance(inv, dict):
            require(False, 'invariant must be an object'); continue
        for key in ('id', 'statement', 'source'):
            require(text(inv.get(key)), f'invariant {inv.get("id")}: {key} required')
        require(strings(inv.get('entry_points')) and bool(inv.get('entry_points')), f'invariant {inv.get("id")}: entry_points required')
        require(inv.get('status') in LEDGER_STATUSES, f'invariant {inv.get("id")}: invalid status')
    gaps = ci.get('gaps')
    require(strings(gaps), 'coverage_inventory.gaps must be a string array')
    if uncovered or sampled:
        require(strings(gaps) and bool(gaps), 'sampled or uncovered units must be listed in coverage_inventory.gaps')
    require(ci.get('index_recommendation') is None or text(ci['index_recommendation']), 'index_recommendation is optional; when present it must be a nonempty string')
    return uncovered

def known_rules():
    """Rule ids an item, risk or decision may cite (BP/BAD/AP); a check row (CHK) is a question, not a rule."""
    found = set()
    for p in (ROOT / 'knowledge').glob('*/*.md'):
        found.update(re.findall(r'^`([A-Z]+-(?:BP|BAD|AP)-\d+)`', p.read_text(), re.M))
    return found

def load_examples(path):
    """All fenced JSON blocks of a Markdown file (the documented examples), in order."""
    return [json.loads(b) for b in re.findall(r'```json\s*\n(.*?)\n```', Path(path).read_text(), re.S)]

def load_report(path):
    text = Path(path).read_text()
    if Path(path).suffix == '.json':
        return json.loads(text)
    blocks = re.findall(r'```json\s*\n(.*?)\n```', text, re.S)
    if not blocks:
        raise ValueError('No closing JSON report block')
    return json.loads(blocks[-1])

def check_models(prov, require):
    models = prov.get('models')
    if models is not None:
        require(isinstance(models, list) and all(isinstance(m, dict) and all(isinstance(m.get(k), str) and bool(m[k].strip()) for k in ('role', 'model')) and isinstance(m.get('effort', ''), str) for m in models),
                'provenance.models must be an array of {role, model, optional effort}')

def validate_design(report, require, strings, rules):
    """Design reports (schema 3.0): assumptions registry, decisions, risks, validation; no scores or readiness."""
    def text(v): return isinstance(v, str) and bool(v.strip())
    prov = report.get('provenance')
    if not isinstance(prov, dict):
        require(False, 'provenance object required'); prov = {}
    require(text(prov.get('plugin_version')), 'provenance.plugin_version required')
    require(strings(prov.get('scope')) and bool(prov['scope']) and set(prov['scope']) <= AREAS, 'provenance.scope must be a nonempty array of known area ids')
    check_models(prov, require)
    for banned in ('areas', 'overall', 'coverage_inventory', 'items'):
        require(banned not in report, f'design reports carry no {banned}; use assumptions, decisions, risks and validation')
    def rows(key, prefix, required):
        value = report.get(key)
        if not (isinstance(value, list) and all(isinstance(x, dict) for x in value)):
            require(False, f'{key} must be an array of objects'); return []
        if required: require(bool(value), f'design requires at least one entry in {key}')
        ids = [str(x.get('id')) for x in value]
        require(all(re.fullmatch(prefix + r'-\d+', i) for i in ids), f'{key}: ids must look like {prefix}-n')
        require(len(set(ids)) == len(ids), f'{key}: duplicate ids')
        return value
    assumptions = rows('assumptions', 'A', True)
    decisions = rows('decisions', 'D', True)
    risks = rows('risks', 'R', False)
    validation = rows('validation', 'V', True)
    a_ids = {str(a.get('id')) for a in assumptions}
    v_ids = {str(v.get('id')) for v in validation}
    for a in assumptions:
        for key in ('statement', 'threshold', 'check'):
            require(text(a.get(key)), f'{a.get("id")}: {key} required')
    for d in decisions:
        label = str(d.get('id'))
        for key in ('title', 'choice', 'why', 'tradeoff', 'revisit'):
            require(text(d.get(key)), f'{label}: {key} required')
        require(text(d.get('options')) or (strings(d.get('options')) and bool(d['options'])), f'{label}: options required')
        refs = d.get('rules')
        require(strings(refs) and bool(refs), f'{label}: rules required')
        if strings(refs): require(set(refs) <= rules, f'{label}: unknown rule ids {set(refs) - rules}')
        for key, known in (('assumptions', a_ids), ('validation', v_ids)):
            if key in d: require(strings(d[key]) and set(d[key]) <= known, f'{label}: invalid {key} references')
    for r in risks:
        label = str(r.get('id'))
        require(r.get('severity') in (*SEVERITIES, 'info'), f'{label}: invalid severity')
        for key in ('title', 'element', 'scenario', 'fix'):
            require(text(r.get(key)), f'{label}: {key} required')
        refs = r.get('rules')
        require(strings(refs) and bool(refs), f'{label}: rules required')
        if strings(refs): require(set(refs) <= rules, f'{label}: unknown rule ids {set(refs) - rules}')
        if 'assumptions' in r: require(strings(r['assumptions']) and set(r['assumptions']) <= a_ids, f'{label}: invalid assumptions references')
    for v in validation:
        label = str(v.get('id'))
        require(v.get('status') in ('planned', 'passed', 'failed', 'not_run'), f'{label}: invalid validation status')
        for key in ('requirement', 'method', 'acceptance'):
            require(text(v.get(key)), f'{label}: {key} required')
        require(strings(v.get('evidence')), f'{label}: evidence must be a string array')
        if v.get('status') in ('passed', 'failed'): require(bool(v.get('evidence')), f'{label}: passed/failed needs result evidence')

def validate_triage_extras(report, require, strings):
    ne = report.get('not_examined')
    require(strings(ne) and bool(ne), 'triage requires a nonempty not_examined list')
    counted = report.get('units_counted', [])
    ok = isinstance(counted, list) and all(isinstance(u, dict) and isinstance(u.get('kind'), str) and u['kind'].strip() and type(u.get('total')) is int and u['total'] >= 0 for u in counted)
    require(ok, 'units_counted must be an array of {kind, total}')
    fa = report.get('full_audit_suggested')
    require(fa is None or (isinstance(fa, str) and bool(fa.strip())), 'full_audit_suggested must be null or a nonempty string')

def validate(report, evidence_root=None):
    errors = []
    def require(condition, message):
        if not condition: errors.append(message)
    def strings(value):
        return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)
    def evidence(value, label):
        require(strings(value) and bool(value), f'{label}: nonempty evidence array required')
        if not strings(value) or evidence_root is None: return
        for ref in value:
            match = EVIDENCE_REF.fullmatch(ref)
            if not match: continue  # Config/document citations need human verification.
            p = (Path(evidence_root) / match[1]).resolve()
            try:
                p.relative_to(Path(evidence_root).resolve())
                lines = len(p.read_text().splitlines())
                start, end = int(match[2]), int(match[3] or match[2])
                require(1 <= start <= end <= lines, f'{label}: line outside {ref}')
            except (ValueError, OSError, UnicodeError):
                errors.append(f'{label}: inaccessible evidence {ref}')
    if not isinstance(report, dict): return ['Report must be an object']
    require(report.get('schema_version') == '3.0', 'schema_version must be 3.0; older reports must be regenerated')
    mode = report.get('mode')
    require(mode in ('audit', 'design'), 'mode must be audit/design')
    require(isinstance(report.get('target'), str) and bool(report['target'].strip()), 'target required')
    try: date.fromisoformat(report.get('date', ''))
    except (TypeError, ValueError): errors.append('date must be ISO YYYY-MM-DD')
    if mode == 'design':
        validate_design(report, require, strings, known_rules())
        return errors
    depth = report.get('depth')
    require(depth in ('full', 'triage'), 'audit depth must be full or triage')
    triage = depth == 'triage'
    if triage: validate_triage_extras(report, require, strings)
    areas, items, decisions, validation = [report.get(k, []) if triage else report.get(k) for k in ('areas', 'items', 'decisions', 'validation')]
    if not all(isinstance(v, list) and all(isinstance(x, dict) for x in v) for v in (areas, items, decisions, validation)):
        return errors + ['areas/items/decisions/validation must be arrays of objects']
    if not triage: require(bool(areas), 'At least one in-scope area required')
    area_ids = [a.get('id') for a in areas]
    if not all(isinstance(x, str) for x in area_ids): return errors + ['Area ids must be strings']
    require(len(set(area_ids)) == len(area_ids), 'Duplicate area ids')
    require(set(area_ids) <= AREAS, 'Unknown area ids')
    provenance = report.get('provenance', {})
    if not isinstance(provenance, dict): return errors + ['provenance must be an object']
    for key in ('revision', 'environment', 'plugin_version') + (() if triage else ('rubric_version',)):
        require(isinstance(provenance.get(key), str) and bool(provenance[key]), f'provenance.{key} required')
    if not triage: require(provenance.get('rubric_version') == '2.0', 'rubric_version must be 2.0')
    require('dirty' in provenance and (provenance['dirty'] is None or isinstance(provenance['dirty'], bool)), 'dirty must be bool/null')
    if triage: require(strings(provenance.get('scope')) and set(provenance['scope']) <= AREAS, 'provenance.scope must list known area ids (empty means all)')
    else: require(strings(provenance.get('scope')) and sorted(provenance['scope']) == sorted(area_ids), 'provenance.scope must match areas')
    require(strings(provenance.get('exclusions')), 'provenance.exclusions must be a string array')
    check_models(provenance, require)
    rules = known_rules()
    counts = {a: Counter() for a in area_ids}
    fingerprints, item_ids = [], []
    for item in items:
        label = str(item.get('id', '?'))
        require(bool(re.fullmatch(r'F-\d+', label)), f'{label}: invalid item id')
        item_ids.append(label)
        area = item.get('area')
        if not isinstance(area, str) or (area not in AREAS if triage else area not in counts): errors.append(f'{label}: primary area out of scope')
        severity = item.get('severity')
        require(severity in (*SEVERITIES, 'info'), f'{label}: invalid severity')
        if isinstance(area, str) and area in counts and severity in SEVERITIES: counts[area][severity] += 1
        require(item.get('effort') in ('S', 'M', 'L'), f'{label}: invalid effort')
        require(item.get('confidence') in ('confirmed', 'likely'), f'{label}: invalid confidence')
        if severity != 'info' or 'priority' in item: require(item.get('priority') in PRIORITIES, f'{label}: priority must be now/next/later')
        if 'depends_on' in item: require(strings(item['depends_on']), f'{label}: depends_on must be an array of item ids')
        for key in ('title', 'fingerprint', 'verification'):
            require(isinstance(item.get(key), str) and bool(item[key].strip()), f'{label}: {key} required')
        fingerprints.append(str(item.get('fingerprint')))
        refs = item.get('rules')
        require(strings(refs) and bool(refs), f'{label}: rules required')
        if strings(refs): require(set(refs) <= rules, f'{label}: unknown rule ids {set(refs) - rules}')
        evidence(item.get('evidence'), label)
        if 'severity_if' in item or 'trigger' in item:
            cond = item.get('severity_if')
            require(cond in SEVERITIES and severity in RANK and RANK[cond] > RANK[severity], f'{label}: severity_if must be a severity higher than severity')
            require(isinstance(item.get('trigger'), str) and bool(item['trigger'].strip()), f'{label}: trigger required with severity_if')
    require(len(set(item_ids)) == len(item_ids), 'Duplicate item ids')
    depends = {str(i.get('id')): i['depends_on'] for i in items if strings(i.get('depends_on'))}
    for ident, deps in depends.items():
        require(ident not in deps and set(deps) <= set(item_ids), f'{ident}: depends_on must name other items of this report')
    def cyclic(node, path):
        return node in path or any(cyclic(d, path | {node}) for d in depends.get(node, ()) if d in depends)
    require(not any(cyclic(i, frozenset()) for i in depends), 'depends_on forms a cycle')
    strengths = report.get('strengths')
    if strengths is not None:
        require(isinstance(strengths, list) and all(isinstance(x, dict) for x in strengths), 'strengths must be an array of objects')
        for x in strengths if isinstance(strengths, list) else []:
            if not isinstance(x, dict): continue
            for key in ('control', 'boundary'): require(isinstance(x.get(key), str) and bool(x[key].strip()), f'strengths.{key} required (the control and the boundary tested)')
            evidence(x.get('evidence'), f'strength {x.get("control")}')
    require(len(set(fingerprints)) == len(fingerprints), 'Duplicate root-cause fingerprints')
    inputs = []
    provisional = False
    for area in areas:
        ident, status, score = area.get('id'), area.get('status'), area.get('score')
        if ident not in counts: continue
        require(status in ('assessed', 'partial', 'unverified', 'not_applicable'), f'{ident}: invalid status')
        provisional |= status in ('partial', 'unverified')
        cov = area.get('coverage', {})
        valid_cov = isinstance(cov, dict) and set(cov) == {'verified', 'violation', 'unverified', 'not_applicable'} and all(type(n) is int and n >= 0 for n in cov.values())
        require(valid_cov, f'{ident}: invalid coverage')
        if valid_cov:
            require(sum(cov.values()) > 0, f'{ident}: empty coverage')
            if status == 'assessed': require(cov['unverified'] == 0, f'{ident}: assessed with unknown checks')
            if status in ('partial', 'unverified'): require(cov['unverified'] > 0, f'{ident}: missing unverified checks')
            if status == 'partial': require(cov['verified'] + cov['violation'] > 0, f'{ident}: partial without assessed checks')
            if status == 'assessed': require(cov['verified'] + cov['violation'] > 0, f'{ident}: assessed without applicable checks')
            if status == 'not_applicable': require(cov['verified'] + cov['violation'] + cov['unverified'] == 0, f'{ident}: N/A contains applicable checks')
        if status == 'not_applicable':
            require(area.get('counts') is None and not any(i.get('area') == ident for i in items), f'{ident}: N/A must have no items and null counts')
            require(bool(area.get('reason')), f'{ident}: N/A reason required')
        else:
            expected = {k: counts[ident][k] for k in SEVERITIES}
            require(isinstance(area.get('counts'), dict) and area['counts'] == expected and all(type(v) is int for v in area['counts'].values()), f'{ident}: counts do not match items')
        if status in ('unverified', 'not_applicable'):
            require(score is None and area.get('confidence') is None, f'{ident}: score/confidence must be null')
        else:
            numeric = type(score) in (int, float) and 0 <= score <= 10
            require(numeric, f'{ident}: score must be 0..10')
            require(area.get('confidence') in ('high', 'medium', 'low'), f'{ident}: invalid confidence')
            evidence(area.get('evidence'), ident)
            if numeric:
                inputs.append(score)
                if status == 'partial': require(score <= 7 and area.get('confidence') != 'high', f'{ident}: partial cap/confidence violated')
                if counts[ident]['critical']: require(score <= 3, f'{ident}: Critical cap violated')
                elif counts[ident]['high']: require(score <= 5, f'{ident}: High cap violated')
                elif counts[ident]['medium']: require(score <= 7, f'{ident}: Medium rubric violated')
                elif counts[ident]['low']: require(score <= 9, f'{ident}: Low rubric violated')
        if status in ('partial', 'unverified'):
            require(strings(area.get('unknowns')) and bool(area['unknowns']), f'{ident}: unknowns required')
    v_ids = [v.get('id') for v in validation]
    require(all(isinstance(i, str) and re.fullmatch(r'V-\d+', i) for i in v_ids), 'Invalid validation ids')
    require(len(set(map(str, v_ids))) == len(v_ids), 'Duplicate validation ids')
    for v in validation:
        require(v.get('status') in ('planned', 'passed', 'failed', 'not_run'), 'Invalid validation status')
        for key in ('requirement', 'method', 'acceptance'):
            require(isinstance(v.get(key), str) and bool(v[key].strip()), f'validation.{key} required')
        if v.get('status') in ('passed', 'failed'): evidence(v.get('evidence'), str(v.get('id')))
        else: require(strings(v.get('evidence')), 'Validation evidence must be a string array')
    d_ids = []
    for decision in decisions:
        ident = str(decision.get('id'))
        d_ids.append(ident)
        require(bool(re.fullmatch(r'D-\d+', ident)), 'Invalid decision id')
        for key in ('title', 'choice'): require(isinstance(decision.get(key), str) and bool(decision[key]), f'{ident}: {key} required')
        require(strings(decision.get('rules')) and bool(decision['rules']), f'{ident}: rules required')
        if strings(decision.get('rules')): require(set(decision['rules']) <= rules, f'{ident}: unknown rules')
        if 'validation' in decision:
            require(strings(decision['validation']) and set(decision['validation']) <= set(map(str, v_ids)), f'{ident}: invalid validation references')
    require(len(set(d_ids)) == len(d_ids), 'Duplicate decision ids')
    require(not decisions, 'Audit decisions must be empty')
    uncovered = coverage_inventory(report, require, strings) if not triage or 'coverage_inventory' in report else False
    priors = report.get('prior_reports')
    if priors is not None:
        require(isinstance(priors, list) and all(isinstance(x, dict) for x in priors), 'prior_reports must be an array of objects')
        for x in priors if isinstance(priors, list) else []:
            if not isinstance(x, dict): continue
            for key in ('source', 'item'):
                require(isinstance(x.get(key), str) and bool(x[key].strip()), f'prior_reports.{key} required')
            require(x.get('verdict') in PRIOR_VERDICTS, 'prior_reports.verdict must be reproduced/refuted/not_applicable/unverifiable')
            require(strings(x.get('evidence')) and bool(x.get('evidence')), 'prior_reports.evidence must be a nonempty string array')
    overall = report.get('overall', {})
    if not isinstance(overall, dict): return errors + ['overall must be an object']
    if triage and 'overall' not in report: return errors
    critical = any(i.get('severity') == 'critical' for i in items)
    blockers = [i['id'] for i in items if i.get('severity') in ('critical', 'high')]
    raw = (sum(Decimal(str(x)) for x in inputs) / len(inputs)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP) if inputs else None
    expected_score = float(min(raw, Decimal('4.0')) if critical else raw) if raw is not None else None
    require(overall.get('score') is None or type(overall['score']) in (int, float), 'Overall score must be numeric/null, not boolean')
    require(overall.get('score') == expected_score, 'Overall mean/cap mismatch')
    require(overall.get('capped') is critical, 'capped must reflect existence of Critical items')
    require(overall.get('provisional') is provisional, 'provisional must reflect coverage')
    require(overall.get('score_inputs') == inputs and type(overall.get('denominator')) is int and overall['denominator'] == len(inputs), 'Overall formula inputs/denominator mismatch')
    require(strings(overall.get('blockers')), 'blockers must be a string array')
    require(strings(overall.get('unknowns')), 'unknowns must be a string array of material unknowns, each with its reason')
    require(strings(overall.get('noted_unknowns', [])), 'noted_unknowns must be a string array')
    if strings(overall.get('blockers')):
        require(set(blockers) <= set(overall['blockers']), 'High/Critical missing from blockers')
        require(len(set(overall['blockers'])) == len(overall['blockers']), 'Duplicate blockers')
    readiness = overall.get('readiness')
    require(readiness in ('blocked', 'undetermined', 'supported_in_scope'), 'Invalid readiness')
    if blockers or overall.get('blockers') or any(v.get('status') == 'failed' for v in validation): require(readiness == 'blocked', 'Blockers/failed acceptance require blocked readiness')
    elif provisional or overall.get('unknowns'): require(readiness == 'undetermined', 'Unknowns require undetermined readiness')
    if readiness == 'supported_in_scope':
        require(bool(inputs) and all(v.get('status') == 'passed' for v in validation), 'Supported status requires completed declared validation')
        require(not uncovered, 'Supported status is impossible while coverage units or domain modules are not covered')
    require(overall.get('confidence') in ('high', 'medium', 'low', None), 'Invalid overall confidence')
    if inputs: require(overall.get('confidence') is not None, 'Numeric overall requires confidence')
    if provisional: require(overall.get('confidence') != 'high', 'Provisional overall cannot have high confidence')
    if not inputs: require(overall.get('confidence') is None, 'No scores requires null overall confidence')
    return errors

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--evidence-root', type=Path)
    args = parser.parse_args()
    try: errors = validate(load_report(args.report), args.evidence_root)
    except (OSError, ValueError, TypeError, KeyError) as exc: errors = [str(exc)]
    if errors:
        for error in errors: print('ERROR:', error)
        return 1
    print('Report contract valid (claims still require substantive review).')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
