#!/usr/bin/env python3
"""Fill a report's derived fields, validate its closing JSON, then render its tables and item blocks in place.

The report author writes narrative sections plus the closing JSON (judgments only) and leaves markers such as
`<!-- render:scorecard -->`. A full audit's derived fields (area counts, overall score, flags, blockers,
readiness) are computed here and written back into the JSON block. Each marker (or a previously rendered
block) is replaced by `<!-- render:NAME -->` ... `<!-- /render:NAME -->`, so re-running is idempotent.
Nothing is written when validation fails; render a draft that lives in a writable scratch directory.
"""
import copy
import argparse
import json
from pathlib import Path
import re
import sys
from validate_report import load_report, validate, derive, PRIORITIES

NAMES = {'API': 'API design', 'DATA': 'Data storage & transactions', 'CACHE': 'Caching', 'MSG': 'Queues & messaging',
         'CONC': 'Concurrency', 'IDEM': 'Idempotency & consistency', 'RES': 'Resilience', 'SCALE': 'Scalability',
         'PERF': 'Performance', 'SEC': 'Security', 'OBS': 'Observability', 'ARCH': 'Architecture styles & boundaries',
         'OPS': 'Delivery & operations'}
SECTIONS = ('header', 'scorecard', 'coverage', 'items', 'plan', 'strengths', 'decisions', 'validation', 'assumptions', 'risks', 'not_examined', 'prior')
REQUIRED = {'full': ('header', 'scorecard', 'coverage', 'items', 'plan'), 'triage': ('header', 'items', 'not_examined'),
            'design': ('header', 'assumptions', 'decisions', 'risks', 'validation')}

def kind(r): return 'design' if r['mode'] == 'design' else r['depth']

def required(r):
    """Markers a report must carry: its shape's own, plus any section it has data for (so no rows vanish silently)."""
    need = list(REQUIRED[kind(r)])
    for name in ('validation', 'strengths'):
        if r.get(name) and name not in need: need.append(name)
    if r.get('provenance', {}).get('prior'): need.append('prior')
    return need
SCRIPT = Path(__file__).resolve()

def plugin_version():
    try: return json.loads((SCRIPT.parents[1] / '.claude-plugin' / 'plugin.json').read_text())['version']
    except (OSError, ValueError, KeyError): return 'unknown'

MARKER = re.compile(r'<!-- render:(\w+) -->(?:.*?<!-- /render:\1 -->)?', re.S)

def cell(v):
    if v is None or v == '' or v == []: return '—'
    if isinstance(v, list): v = '; '.join(map(str, v))
    return str(v).replace('|', '\\|').replace('\n', ' ')

def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '| ' + ' | '.join('---' for _ in head) + ' |']
    out += ['| ' + ' | '.join(cell(c) for c in r) + ' |' for r in rows]
    return '\n'.join(out)

def score_text(score, status):
    if status == 'unverified' or (status is None and score is None): return 'Not assessed'
    if status == 'not_applicable': return 'N/A'
    s = f'{score:g}/10' if status else f'{score:.1f}/10'
    return s + (' (provisional)' if status in ('partial', True) else '')

def validated(): return f'\n\n**Schema validation:** passed; rendered by `{SCRIPT}` (plugin {plugin_version()}).'

def header(r):
    if r['mode'] == 'design':
        return table(['Mode', 'Target', 'Areas', 'Date', 'Decisions', 'Risks'],
                     [['design', r['target'], ', '.join(r['provenance']['scope']), r['date'], len(r['decisions']), len(r.get('risks', []))]]) + validated()
    if 'overall' not in r or 'areas' not in r:
        result = table(['Mode', 'Target', 'Areas', 'Date', 'Findings'],
                       [[f"audit ({r['depth']})", r['target'], ', '.join(r['provenance'].get('scope') or ['all 13']), r['date'], len(r['items'])]])
        if r['provenance'].get('exclusions'): result += '\n\n**Exclusions:** ' + cell(r['provenance']['exclusions'])
        if r.get('units_counted'): result += '\n\n**Units counted:** ' + '; '.join(f"{u['total']} {u['kind']}" for u in r['units_counted'])
        if r.get('full_audit_suggested'): result += '\n\n**Full audit suggested:** ' + r['full_audit_suggested']
        return result + validated()
    o = r['overall']
    overall = 'Not assessed' if o.get('score') is None else score_text(o['score'], None) + (' (provisional)' if o.get('provisional') else '')
    result = table(['Mode', 'Target', 'Areas', 'Date', 'Overall', 'Readiness', 'Confidence'],
                 [[r['mode'], r['target'], ', '.join(a['id'] for a in r['areas']), r['date'], overall, o.get('readiness'), o.get('confidence') or 'unknown']])
    exclusions = r.get('provenance', {}).get('exclusions', [])
    if exclusions: result += '\n\n**Exclusions:** ' + cell(exclusions)
    return result + f'\n\n**Schema validation:** passed; rendered by `{SCRIPT}` (plugin {plugin_version()}).'

def scorecard(r):
    rows, totals = [], dict(critical=0, high=0, medium=0, low=0)
    for a in r['areas']:
        c, cov = a.get('counts') or {}, a.get('coverage', {})
        for k in totals: totals[k] += c.get(k, 0)
        covtxt = ' · '.join(f'{n} {k.replace("_", " ")}' for k, n in cov.items() if n)
        note = a.get('note') or a.get('reason') or ''
        rows.append([f"{a['id']} · {NAMES.get(a['id'], a['id'])}", a['status'], score_text(a.get('score'), a['status']), a.get('confidence'),
                     *(c.get(k, '—') if c else '—' for k in totals), '; '.join(x for x in (covtxt, note) if x)])
    o = r['overall']
    basis = f"mean of {o.get('score_inputs')} / {o.get('denominator')}" + ('; capped at 4.0 by a Critical item' if o.get('capped') else '')
    rows.append(['**Overall**', 'provisional' if o.get('provisional') else 'assessed', 'Not assessed' if o.get('score') is None else f"{o['score']:.1f}/10",
                 o.get('confidence'), *totals.values(), basis])
    return table(['Area', 'Status', 'Score', 'Confidence', 'Crit', 'High', 'Med', 'Low', 'Coverage / key point'], rows)

def coverage(r):
    ci = r['coverage_inventory']
    parts = [table(['Unit kind', 'Total', 'Checked', 'Sampled', 'Not covered', 'Sampling rule / note'],
                   [[u['kind'], u['total'], u['checked'], u['sampled'], u['not_covered'], '; '.join(x for x in (u.get('owner'), u.get('sampling')) if x)] for u in ci['units']])]
    mods = ci.get('domain_modules') or []
    parts.append('**Domain modules:** ' + ('; '.join(f"{m['id']} ({', '.join(x for x in (m['status'], m.get('owner')) if x)})" for m in mods) if mods else cell(ci.get('domain_modules_reason'))))
    inv = ci.get('invariants') or []
    if inv: parts.append(table(['Invariant', 'Statement', 'Source', 'Entry points', 'Status'], [[i['id'], i['statement'], i['source'], i['entry_points'], i['status']] for i in inv]))
    else: parts.append('**Invariants:** ' + cell(ci.get('invariants_reason')))
    parts.append('**Gaps:** ' + ('; '.join(ci['gaps']) if ci.get('gaps') else 'none'))
    if ci.get('index_recommendation'): parts.append('**Index recommendation:** ' + ci['index_recommendation'])
    return '\n\n'.join(parts)

def items(r):
    if not r['items']: return '_No findings established._'
    out = []
    for i in sorted(r['items'], key=lambda i: ('critical', 'high', 'medium', 'low', 'info').index(i['severity'])):
        also = f"; also {', '.join(i['also_areas'])}" if i.get('also_areas') else ''
        sched = f" · **Priority:** {i['priority'].title()}" + (f" · **Depends on:** {', '.join(i['depends_on'])}" if i.get('depends_on') else '') if i.get('priority') else ''
        block = [f"### {i['id']} · {i['title']} — {i['severity'].title()}",
                 f"- **Area:** {i['area']}{also} · **Rule:** {', '.join(i['rules'])} · **Confidence:** {i['confidence']}",
                 f"- **Evidence:** {'; '.join(i['evidence'])}",
                 f"- **Impact:** {i['impact']}", f"- **Fix:** {i['fix']}",
                 f"- **Verification:** {i['verification']}",
                 f"- **Effort:** {i['effort']}{sched} · **Fingerprint:** {i['fingerprint']}"]
        if i.get('severity_if'): block.append(f"- **Severity if:** {i['severity_if'].title()} when {i['trigger']}")
        out.append('\n'.join(block))
    return '\n\n'.join(out)

def plan(r):
    rank = ('critical', 'high', 'medium', 'low', 'info')
    rows = [[p.title(), f"{i['id']} · {i['title']} ({i['severity']})", i['effort'], i.get('depends_on'), i['verification']]
            for p in PRIORITIES for i in sorted(r['items'], key=lambda i: rank.index(i['severity'])) if i.get('priority') == p]
    if not rows: return '_No actions planned._'
    return table(['Priority', 'Item', 'Effort', 'Depends on', 'Acceptance gate'], rows)

def strengths(r):
    return '\n'.join(f"- **{x['control']}** — {x['boundary']} ({'; '.join(x['evidence'])})" for x in r['strengths'])

def decisions(r):
    if not r['decisions']: return '_No decisions recorded._'
    out = []
    for d in r['decisions']:
        fields = [('Options', d.get('options')), ('Chosen', d['choice']), ('Why', d.get('why')), ('Trade-off', d.get('tradeoff')),
                  ('Revisit when', d.get('revisit')), ('Rules', d['rules']), ('Assumptions', d.get('assumptions')), ('Validation', d.get('validation')),
                  ('Closes', d.get('closes')), ('Migration', d.get('migration')), ('Rollback', d.get('rollback'))]
        out.append(f"**{d['id']} · {d['title']}** — " + ' · '.join(f'{k}: {cell(v)}' for k, v in fields if v))
    return '\n\n'.join(out)

def assumptions(r):
    return table(['ID', 'Assumption', 'Choice changes when', 'How to check'], [[a['id'], a['statement'], a['threshold'], a['check']] for a in r['assumptions']])

def risks(r):
    if not r.get('risks'): return '_No residual risks established._'
    out = []
    for x in sorted(r['risks'], key=lambda x: ('critical', 'high', 'medium', 'low', 'info').index(x['severity'])):
        assumes = f" · **Assumes:** {', '.join(x['assumptions'])}" if x.get('assumptions') else ''
        out.append(f"### {x['id']} · {x['title']} — {x['severity'].title()}\n"
                   f"- **Element:** {x['element']} · **Rule:** {', '.join(x['rules'])}{assumes}\n"
                   f"- **Scenario:** {x['scenario']}\n- **Fix:** {x['fix']}")
    return '\n\n'.join(out)

def verdict_text(x):
    return f"fixed at {x['fixed_at']}" if x['verdict'] == 'fixed' else x['verdict'].replace('_', ' ')

def prior(r):
    pin = r['provenance']['prior']
    out = [f"**Prior {pin['mode']}:** {pin['source']} · revision {pin['revision']} · {pin['date']}"]
    if r['mode'] == 'audit' and pin['mode'] == 'audit':
        known = {x['fingerprint'] for x in r['prior_verdicts']}
        out.append(table(['Prior item', 'Title', 'Verdict', 'Evidence / note'],
                         [[x['item'], x['title'], verdict_text(x), [*x.get('evidence', []), *([x['note']] if x.get('note') else [])]] for x in r['prior_verdicts']]))
        new = [i['id'] for i in r['items'] if i['fingerprint'] not in known]
        out.append('**New in this audit:** ' + (', '.join(new) if new else 'none'))
    elif r['mode'] == 'audit':
        out.append(table(['Prior ref', 'Status', 'Evidence / note'], [[x['ref'], x['status'], [*x.get('evidence', []), *([x['note']] if x.get('note') else [])]] for x in r['prior_checks']]))
    else:
        closed = {f: d['id'] for d in r['decisions'] for f in d.get('closes', [])}
        out.append(table(['From finding', 'Requirement', 'Closed by'], [[x['from'], x['requirement'], closed.get(x['from'], 'open')] for x in r['requirements']]))
    return '\n\n'.join(out)

def not_examined(r):
    return '\n'.join('- ' + x for x in r['not_examined'])

def validation(r):
    if not r['validation']: return '_No validation scenarios._'
    return table(['ID', 'Requirement / scenario', 'Method / experiment', 'Acceptance', 'Status', 'Evidence'],
                 [[v['id'], v['requirement'], v['method'], v['acceptance'], v['status'], v.get('evidence')] for v in r['validation']])

def render_errors(r):
    errors = []
    for i in r.get('items', []):
        for k in ('impact', 'fix'):
            if not (isinstance(i.get(k), str) and i[k].strip()): errors.append(f"{i.get('id')}: {k} required for rendering")
    for d in r.get('decisions', []):
        for k in ('options', 'why', 'tradeoff', 'revisit'):
            if not d.get(k): errors.append(f"{d.get('id')}: {k} required for rendering")
    return errors

def render(text, report):
    found = set()
    def sub(m):
        name = m[1]
        if name not in SECTIONS: return m[0]
        found.add(name)
        return f'<!-- render:{name} -->\n{globals()[name](report)}\n<!-- /render:{name} -->'
    out = MARKER.sub(sub, text)
    missing = [n for n in required(report) if n not in found]
    return out, [f'missing marker <!-- render:{n} -->' for n in missing]

def write_back(text, report):
    """Replace the last fenced JSON block with the report as derived."""
    blocks = list(re.finditer(r'```json\s*\n(.*?)\n```', text, re.S))
    b = blocks[-1]
    return text[:b.start(1)] + json.dumps(report, indent=1, ensure_ascii=False) + text[b.end(1):]

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('report', type=Path)
    ap.add_argument('--evidence-root', type=Path)
    ap.add_argument('--prior', type=Path, help='the prior report, to check that the verdicts/requirements/checks cover it')
    args = ap.parse_args()
    try:
        report = load_report(args.report)
        before = copy.deepcopy(report)
        derive(report)
        errors = validate(report, args.evidence_root, load_report(args.prior) if args.prior else None)
        if not errors: errors = render_errors(report)
        if not errors:
            text, errors = render(args.report.read_text(), report)
        if not errors and report != before: text = write_back(text, report)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors = [str(exc)]
    if errors:
        for e in errors: print('ERROR:', e)
        print('Nothing written.')
        return 1
    args.report.write_text(text)
    print(f'render_report.py {SCRIPT} (plugin {plugin_version()})')
    print(f'Rendered and valid: {args.report} (claims still require substantive review).')
    return 0

if __name__ == '__main__': sys.exit(main())
