#!/usr/bin/env python3
"""Validate a report's closing JSON, then render its tables and item blocks into the Markdown in place.

The report author writes narrative sections plus the closing JSON and leaves markers such as
`<!-- render:scorecard -->`. Each marker (or a previously rendered block) is replaced by
`<!-- render:NAME -->` ... `<!-- /render:NAME -->`, so re-running is idempotent. Nothing is written
when validation fails.
"""
import argparse
from pathlib import Path
import re
import sys
from validate_report import load_report, validate

NAMES = {'API': 'API design', 'DATA': 'Data storage & transactions', 'CACHE': 'Caching', 'MSG': 'Queues & messaging',
         'CONC': 'Concurrency', 'IDEM': 'Idempotency & consistency', 'RES': 'Resilience', 'SCALE': 'Scalability',
         'PERF': 'Performance', 'SEC': 'Security', 'OBS': 'Observability', 'ARCH': 'Architecture styles & boundaries',
         'OPS': 'Delivery & operations'}
SECTIONS = ('header', 'scorecard', 'coverage', 'items', 'decisions', 'validation')
REQUIRED = {'audit': ('header', 'scorecard', 'coverage', 'items'), 'design': ('header', 'scorecard', 'coverage', 'items', 'decisions', 'validation')}
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

def header(r):
    o = r['overall']
    overall = 'Not assessed' if o.get('score') is None else score_text(o['score'], None) + (' (provisional)' if o.get('provisional') else '')
    result = table(['Mode', 'Target', 'Areas', 'Date', 'Overall', 'Readiness', 'Confidence'],
                 [[r['mode'], r['target'], ', '.join(a['id'] for a in r['areas']), r['date'], overall, o.get('readiness'), o.get('confidence') or 'unknown']])
    exclusions = r.get('provenance', {}).get('exclusions', [])
    if exclusions: result += '\n\n**Exclusions:** ' + cell(exclusions)
    return result

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
    parts = [table(['Unit kind', 'Total', 'Checked', 'Sampled', 'Not covered', 'Owner / sampling rule'],
                   [[u['kind'], u['total'], u['checked'], u['sampled'], u['not_covered'], '; '.join(x for x in (u.get('owner'), u.get('sampling')) if x)] for u in ci['units']])]
    mods = ci.get('domain_modules') or []
    parts.append('**Domain modules:** ' + ('; '.join(f"{m['id']} ({m['status']}, {m['owner']})" for m in mods) if mods else cell(ci.get('domain_modules_reason'))))
    inv = ci.get('invariants') or []
    if inv: parts.append(table(['Invariant', 'Statement', 'Source', 'Entry points', 'Status'], [[i['id'], i['statement'], i['source'], i['entry_points'], i['status']] for i in inv]))
    else: parts.append('**Invariants:** ' + cell(ci.get('invariants_reason')))
    parts.append('**Gaps:** ' + ('; '.join(ci['gaps']) if ci.get('gaps') else 'none'))
    if ci.get('index_recommendation'): parts.append('**Index recommendation:** ' + ci['index_recommendation'])
    if r.get('prior_reports'):
        parts.append(table(['Prior source', 'Item', 'Prior severity', 'Verdict', 'Evidence'],
                           [[p['source'], p['item'], p.get('prior_severity'), p['verdict'], p['evidence']] for p in r['prior_reports']]))
    return '\n\n'.join(parts)

def items(r):
    if not r['items']: return '_No ' + ('findings' if r['mode'] == 'audit' else 'residual risks') + ' established._'
    out = []
    for i in sorted(r['items'], key=lambda i: ('critical', 'high', 'medium', 'low', 'info').index(i['severity'])):
        also = f"; also {', '.join(i['also_areas'])}" if i.get('also_areas') else ''
        block = [f"### {i['id']} · {i['title']} — {i['severity'].title()}",
                 f"- **Area:** {i['area']}{also} · **Rule:** {', '.join(i['rules'])} · **Confidence:** {i['confidence']}",
                 f"- **Evidence:** {'; '.join(i['evidence'])}",
                 f"- **Impact:** {i['impact']}", f"- **Fix:** {i['fix']}",
                 f"- **Verification:** {i['verification']}",
                 f"- **Effort:** {i['effort']} · **Fingerprint:** {i['fingerprint']}"]
        if i.get('severity_if'): block.append(f"- **Severity if:** {i['severity_if'].title()} when {i['trigger']}")
        out.append('\n'.join(block))
    return '\n\n'.join(out)

def decisions(r):
    if not r['decisions']: return '_No decisions recorded._'
    out = []
    for d in r['decisions']:
        fields = [('Options', d.get('options')), ('Chosen', d['choice']), ('Why', d.get('why')), ('Trade-off', d.get('tradeoff')),
                  ('Revisit when', d.get('revisit')), ('Rules', d['rules']), ('Validation', d.get('validation'))]
        out.append(f"**{d['id']} · {d['title']}** — " + ' · '.join(f'{k}: {cell(v)}' for k, v in fields if v))
    return '\n\n'.join(out)

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
    missing = [n for n in REQUIRED[report['mode']] if n not in found]
    return out, [f'missing marker <!-- render:{n} -->' for n in missing]

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('report', type=Path)
    ap.add_argument('--evidence-root', type=Path)
    args = ap.parse_args()
    try:
        report = load_report(args.report)
        errors = validate(report, args.evidence_root)
        if not errors: errors = render_errors(report)
        if not errors:
            text, errors = render(args.report.read_text(), report)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors = [str(exc)]
    if errors:
        for e in errors: print('ERROR:', e)
        print('Nothing written.')
        return 1
    args.report.write_text(text)
    print(f'Rendered and valid: {args.report} (claims still require substantive review).')
    return 0

if __name__ == '__main__': sys.exit(main())
