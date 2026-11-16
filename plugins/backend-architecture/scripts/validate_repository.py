#!/usr/bin/env python3
"""Check stable rule definitions, knowledge layout, cross-references, skills/agents, eval layout and report example."""
from pathlib import Path
import re
import sys
from validate_report import load_report, validate, AREAS

ROOT = Path(__file__).resolve().parents[1]
AREA_FILES = ('decisions.md', 'checks.md', 'rules.md')
RULE_DEF = re.compile(r'`([A-Z]+-(?:BP|BAD|AP)-\d+)`')
CHECK_DEF = re.compile(r'\| `?([A-Z]+-CHK-\d+)`? \|')
PATH_REF = re.compile(r'`((?:shared|knowledge|scripts|agents)/[A-Za-z0-9_./-]+\.(?:md|py))`')

RULES_CELL_ID = re.compile(r'[A-Z]+-(?:BP|BAD|AP)-\d+')

def decision_errors(label, text, definitions):
    """The Key decisions table ends in a Rules column: every row lists known rule IDs, or an explicit dash."""
    errors, rows = [], [l.strip() for l in text.splitlines() if l.strip().startswith('|')]
    split = lambda l: [c.strip() for c in l.strip('|').split('|')]
    if len(rows) < 3 or split(rows[0])[-1] != 'Rules' or not set(''.join(split(rows[1]))) <= set('-: '):
        return [f'{label}: decisions table needs a header ending in Rules, a separator and at least one row']
    width = len(split(rows[0]))
    for line in rows[2:]:
        cells = split(line)
        if len(cells) != width: errors.append(f'{label}: row has {len(cells)} cells, expected {width}: {cells[0]}'); continue
        cell = cells[-1]
        if cell == '\u2014': continue
        ids = [x.strip() for x in cell.split(',')]
        if not cell or any(not RULES_CELL_ID.fullmatch(x) for x in ids): errors.append(f'{label}: Rules cell of "{cells[0]}" must list rule IDs or \u2014')
        errors.extend(f'{label}: Rules cell of "{cells[0]}" cites unknown {x}' for x in ids if RULES_CELL_ID.fullmatch(x) and x not in definitions)
    return errors

def frontmatter(path, name, errors):
    body = path.read_text()
    if not body.startswith('---\n') or f'name: {name}\n' not in body.split('\n---\n', 1)[0] or '\ndescription: ' not in body:
        errors.append(f'{path.relative_to(ROOT)}: invalid frontmatter (name/description)')
    return body

def main():
    errors, definitions = [], {}
    dirs = {p.name for p in (ROOT / 'knowledge').iterdir() if p.is_dir()}
    if dirs != {a.lower() for a in AREAS}: errors.append(f'knowledge area dirs {sorted(dirs)} do not match validator registry')
    for d in sorted(dirs):
        for name in AREA_FILES:
            p = ROOT / 'knowledge' / d / name
            if not p.is_file(): errors.append(f'missing {p.relative_to(ROOT)}'); continue
            for n, line in enumerate(p.read_text().splitlines(), 1):
                m = RULE_DEF.match(line) if name == 'rules.md' else CHECK_DEF.match(line) if name == 'checks.md' else None
                if not m: continue
                ident = m[1]
                if ident.split('-')[0].lower() != d: errors.append(f'{ident} defined outside knowledge/{ident.split("-")[0].lower()}/')
                if ident in definitions: errors.append(f'Duplicate rule {ident}')
                definitions[ident] = (p, n)
    for d in sorted(dirs):
        p = ROOT / 'knowledge' / d / 'decisions.md'
        if p.is_file(): errors.extend(decision_errors(str(p.relative_to(ROOT)), p.read_text(), definitions))
    for p in ROOT.rglob('*.md'):
        if p.name == '_TEMPLATE.md': continue
        text = p.read_text()
        for ident in re.findall(r'\b[A-Z]{2,6}-(?:BP|BAD|AP|CHK)-\d+\b', text):
            if ident not in definitions and not ident.startswith('XX-'):
                errors.append(f'{p.relative_to(ROOT)}: unknown {ident}')
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            if target.startswith(('http:', 'https:', '#')): continue
            local = target.split('#')[0]
            if local and not (p.parent / local).exists(): errors.append(f'{p}: missing link {target}')
        if '/evals/' not in str(p):
            for ref in PATH_REF.findall(text):
                if '<' not in ref and not (ROOT / ref).exists(): errors.append(f'{p.relative_to(ROOT)}: missing path {ref}')
    for rel in ('shared/method.md', 'shared/domain-audit.md', 'shared/report.md', 'shared/full-audit.md', 'knowledge/README.md', 'knowledge/sources.md'):
        if not (ROOT / rel).is_file(): errors.append(f'Missing runtime reference {rel}')
    for agent in sorted((ROOT / 'agents').glob('*.md')):
        frontmatter(agent, agent.stem, errors)
    for skill in sorted((ROOT / 'skills').iterdir()):
        if not (skill / 'SKILL.md').exists(): continue
        frontmatter(skill / 'SKILL.md', skill.name, errors)
        evals = skill / 'evals'
        for case in sorted(evals.iterdir()) if evals.is_dir() else []:
            if not (case / 'case.yaml').exists(): continue
            if not (case / 'prompt.md').exists() or not list((case / 'graders').glob('*.md')): errors.append(f'{case}: incomplete eval')
            if 'scaffold_script: place-files.sh' in (case / 'case.yaml').read_text() and not (case / 'place-files.sh').exists(): errors.append(f'{case}: missing scaffold')
    try: errors.extend(validate(load_report(ROOT / 'shared/report.md')))
    except (ValueError, OSError, TypeError) as exc: errors.append(str(exc))
    if errors:
        for e in errors: print('ERROR:', e)
        return 1
    print(f'Repository valid: {len(definitions)} stable rule IDs in {len(dirs)} areas; references, skills, agents, eval layout and report example checked.')
    return 0

if __name__ == '__main__': sys.exit(main())
