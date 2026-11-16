#!/usr/bin/env python3
"""Check stable rule definitions, knowledge layout, cross-references, skills/agents, eval layout, report example and plugin manifests."""
from pathlib import Path
import json
import re
import sys
from validate_report import load_report, validate, AREAS

ROOT = Path(__file__).resolve().parents[1]
AREA_FILES = ('decisions.md', 'checks.md', 'rules.md')
RULE_DEF = re.compile(r'`([A-Z]+-(?:BP|BAD|AP)-\d+)`')
CHECK_DEF = re.compile(r'\| ([A-Z]+-CHK-\d+) \|')
RULE_MARKED = re.compile(r'^\s*[-*>]\s*`[A-Z]+-(?:BP|BAD|AP)-\d+`')
CHECK_TICKED = re.compile(r'^\|\s*`[A-Z]+-CHK-\d+`')
ABBREVIATED = re.compile(r'\b[A-Z]+-(?:BP|BAD|AP|CHK)-\d+(?:\s*/\s*\d+|[\u2013-]\d+| and \d+|, \d+\b|, (?:BP|BAD|AP|CHK)-\d+)|(?<![A-Z]-)\b(?:BP|BAD|AP|CHK)-\d+\b')
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

def rules_layout_errors(label, text):
    """Every BP/BAD/AP rule is one line that starts with its backticked ID: Grep `^`ID`` returns the whole body."""
    errors, lines = [], text.splitlines()
    for n, line in enumerate(lines, 1):
        if RULE_MARKED.match(line): errors.append(f'{label}:{n}: rule has a list marker; the line must start with the backticked ID')
        if RULE_DEF.match(line) and n < len(lines) and lines[n].strip(): errors.append(f'{label}:{n}: rule body continues on the next line; keep BP, BAD and AP to one line')
    return errors

def checks_layout_errors(label, text):
    return [f'{label}:{n}: check ID in backticks; write it plain so `^| ID |` finds it' for n, l in enumerate(text.splitlines(), 1) if CHECK_TICKED.match(l)]

def abbreviation_errors(label, text):
    """IDs are written in full everywhere: no `PREFIX-BP-1, BP-3`, `PREFIX-BP-12/13` or bare `BP-3`."""
    return [f'{label}: abbreviated ID {m.group(0)!r}; write each ID in full' for m in ABBREVIATED.finditer(text)]

def orphan_errors(definitions, cited):
    return [f'{i} is not cited by any check, "Also scan for" entry or decisions Rules cell' for i in sorted(definitions)
            if RULE_DEF.fullmatch(f'`{i}`') and i not in cited]

def domain_check_errors(label, text, dirs, definitions):
    """Domain-only checks live in shared/domain-audit.md: a stable ID of an existing area prefix, defined once, one table row each."""
    errors = checks_layout_errors(label, text)
    for n, line in enumerate(text.splitlines(), 1):
        m = CHECK_DEF.match(line)
        if not m: continue
        ident = m[1]
        if ident.split('-')[0].lower() not in dirs: errors.append(f'{label}:{n}: {ident} has no area directory')
        if ident in definitions: errors.append(f'Duplicate rule {ident}')
        definitions[ident] = (label, n)
    return errors

def manifest_errors(plugin_root, marketplace_root=None):
    """The Claude and Codex manifests agree on name and version, and so does each marketplace's entry.

    Both runtimes cache an installed plugin by version, so a version that differs between them
    installs a stale copy in one runtime. A marketplace root is checked only when it exists (the
    plugin may be used outside this repository)."""
    errors = []
    def load(path):
        try: return json.loads(path.read_text())
        except (OSError, ValueError) as exc: errors.append(f'{path}: {exc}'); return None
    manifests = {rel: load(plugin_root / rel) for rel in ('.claude-plugin/plugin.json', '.codex-plugin/plugin.json')}
    found = {rel: (d.get('name'), d.get('version')) for rel, d in manifests.items() if d}
    codex = manifests['.codex-plugin/plugin.json']
    if codex and not (plugin_root / codex.get('skills', '')).is_dir(): errors.append(f'.codex-plugin/plugin.json: skills path {codex.get("skills")!r} is not a directory')
    name = found.get('.claude-plugin/plugin.json', (plugin_root.name, None))[0]
    if marketplace_root is not None:
        for rel, source_path in (('.claude-plugin/marketplace.json', lambda e: e.get('source')),
                                 ('.agents/plugins/marketplace.json', lambda e: (e.get('source') or {}).get('path'))):
            path = marketplace_root / rel
            if not path.is_file(): errors.append(f'missing marketplace manifest {rel}'); continue
            data = load(path)
            entries = [e for e in (data or {}).get('plugins', []) if e.get('name') == name]
            if len(entries) != 1: errors.append(f'{rel}: expected one entry for {name}, found {len(entries)}'); continue
            found[rel] = (entries[0].get('name'), entries[0].get('version'))
            src = source_path(entries[0])
            if not src or (marketplace_root / src).resolve() != plugin_root.resolve(): errors.append(f'{rel}: source {src!r} does not point at {plugin_root.name}')
    if len(set(found.values())) > 1:
        errors.append('manifests disagree on name/version: ' + ', '.join(f'{k}={v[0]}@{v[1]}' for k, v in sorted(found.items())))
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
    cited = set()
    for d in sorted(dirs):
        p = ROOT / 'knowledge' / d / 'decisions.md'
        if p.is_file():
            errors.extend(decision_errors(str(p.relative_to(ROOT)), p.read_text(), definitions))
            cited.update(RULES_CELL_ID.findall(''.join(l.split('|')[-2] for l in p.read_text().splitlines() if l.startswith('|') and l.count('|') > 2)))
        for name, check in (('rules.md', rules_layout_errors), ('checks.md', checks_layout_errors)):
            q = ROOT / 'knowledge' / d / name
            if q.is_file(): errors.extend(check(str(q.relative_to(ROOT)), q.read_text()))
        q = ROOT / 'knowledge' / d / 'checks.md'
        if q.is_file(): cited.update(RULES_CELL_ID.findall(q.read_text()))
    domain = ROOT / 'shared' / 'domain-audit.md'
    if domain.is_file():
        errors.extend(domain_check_errors('shared/domain-audit.md', domain.read_text(), dirs, definitions))
        cited.update(RULES_CELL_ID.findall(domain.read_text()))
    errors.extend(orphan_errors(definitions, cited))
    for p in ROOT.rglob('*.md'):
        if p.name == '_TEMPLATE.md': continue
        text = p.read_text()
        errors.extend(abbreviation_errors(str(p.relative_to(ROOT)), text))
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
        front = frontmatter(agent, agent.stem, errors).split('\n---\n', 1)[0]
        if re.search(r'^tools:.*\bBash\b', front, re.M): errors.append(f'{agent.relative_to(ROOT)}: audit agents read only; running the target\'s code is the lead\'s, with the user\'s consent')
    for skill in sorted((ROOT / 'skills').iterdir()):
        if not (skill / 'SKILL.md').exists(): continue
        frontmatter(skill / 'SKILL.md', skill.name, errors)
        evals = skill / 'evals'
        for case in sorted(evals.iterdir()) if evals.is_dir() else []:
            if not (case / 'case.yaml').exists(): continue
            if not (case / 'prompt.md').exists() or not list((case / 'graders').glob('*.md')): errors.append(f'{case}: incomplete eval')
            if 'scaffold_script: place-files.sh' in (case / 'case.yaml').read_text() and not (case / 'place-files.sh').exists(): errors.append(f'{case}: missing scaffold')
    market = ROOT.parents[1]
    errors.extend(manifest_errors(ROOT, market if (market / '.claude-plugin/marketplace.json').is_file() else None))
    try: errors.extend(validate(load_report(ROOT / 'shared/report.md')))
    except (ValueError, OSError, TypeError) as exc: errors.append(str(exc))
    if errors:
        for e in errors: print('ERROR:', e)
        return 1
    print(f'Repository valid: {len(definitions)} stable rule IDs in {len(dirs)} areas; references, skills, agents, eval layout, report example and manifests checked.')
    return 0

if __name__ == '__main__': sys.exit(main())
