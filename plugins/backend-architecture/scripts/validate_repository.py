#!/usr/bin/env python3
"""Check stable rule definitions, cross-references, eval layout and report example."""
from pathlib import Path
import re
import sys
from validate_report import load_report, validate

ROOT = Path(__file__).resolve().parents[1]

def main():
    errors, definitions = [], {}
    for p in (ROOT / 'knowledge').glob('*.md'):
        if p.name == '_TEMPLATE.md': continue
        for n, line in enumerate(p.read_text().splitlines(), 1):
            m = re.match(r'`([A-Z]+-(?:BP|BAD|AP)-\d+)`', line) or re.match(r'\| `?([A-Z]+-CHK-\d+)`? \|', line)
            if m:
                if m[1] in definitions: errors.append(f'Duplicate rule {m[1]}')
                definitions[m[1]] = (p, n)
    for p in ROOT.rglob('*.md'):
        if p.name == '_TEMPLATE.md': continue
        for ident in re.findall(r'\b[A-Z]{2,6}-(?:BP|BAD|AP|CHK)-\d+\b', p.read_text()):
            if ident not in definitions and not ident.startswith('XX-'):
                errors.append(f'{p.relative_to(ROOT)}: unknown {ident}')
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', p.read_text()):
            if target.startswith(('http:', 'https:', '#')): continue
            local = target.split('#')[0]
            if local and not (p.parent / local).exists(): errors.append(f'{p}: missing link {target}')
    for rel in ('shared/assessment-method.md', 'shared/output-format.md', 'knowledge/README.md', 'knowledge/sources.md'):
        if not (ROOT / rel).is_file(): errors.append(f'Missing runtime reference {rel}')
    for skill in (ROOT / 'skills').iterdir():
        if not (skill/'SKILL.md').exists(): continue
        body=(skill/'SKILL.md').read_text()
        if not body.startswith('---\n') or f'name: {skill.name}\n' not in body: errors.append(f'{skill}: invalid skill frontmatter')
        for case in (skill/'evals').iterdir():
            if not (case/'case.yaml').exists(): continue
            if not (case/'prompt.md').exists() or not list((case/'graders').glob('*.md')): errors.append(f'{case}: incomplete eval')
            if 'scaffold_script: place-files.sh' in (case/'case.yaml').read_text() and not (case/'place-files.sh').exists(): errors.append(f'{case}: missing scaffold')
    try: errors.extend(validate(load_report(ROOT/'shared/output-format.md')))
    except (ValueError, OSError, TypeError) as exc: errors.append(str(exc))
    if errors:
        for e in errors: print('ERROR:', e)
        return 1
    print(f'Repository valid: {len(definitions)} stable rule IDs; references, eval layout and report example checked.')
    return 0

if __name__ == '__main__': sys.exit(main())
