import copy
import json
import re
from pathlib import Path
import tempfile
import unittest

from validate_report import load_report, load_examples, ROOT
import render_report

MARKERS = '\n\n'.join(f'<!-- render:{n} -->' for n in ('header', 'scorecard', 'coverage', 'items', 'plan', 'strengths', 'validation'))

def document(report):
    return f'# Backend audit: x\n\n{MARKERS}\n\n## Machine-readable summary\n\n```json\n{json.dumps(report, indent=1)}\n```\n'

class RenderTests(unittest.TestCase):
    def setUp(self):
        self.report = load_report(ROOT / 'shared/report.md')
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'r.md'
    def tearDown(self): self.tmp.cleanup()
    def run_on(self, report, text=None):
        self.path.write_text(text if text is not None else document(report))
        import sys
        argv, sys.argv = sys.argv, ['render_report.py', str(self.path)]
        try: return render_report.main()
        finally: sys.argv = argv

    def test_example_renders_and_is_idempotent(self):
        self.assertEqual(self.run_on(self.report), 0)
        first = self.path.read_text()
        self.assertIn('| RES · Resilience | partial | 7/10 (provisional) |', first)
        self.assertIn('| **Overall** | provisional | 7.0/10 |', first)
        self.assertIn('| entry_points | 3 | 3 | 0 | 0 | lead |', first)
        self.assertIn('_No findings established._', first)
        self.assertIn('_No actions planned._', first)
        self.assertIn('- **Outbound calls inherit the request deadline** — Lookup client only; batch jobs not checked (client.go:24)', first)
        self.assertEqual(self.run_on(self.report, first), 0)
        self.assertEqual(self.path.read_text(), first)
        self.assertEqual(load_report(self.path), self.report)

    def test_render_records_validation_and_script(self):
        self.assertEqual(self.run_on(self.report), 0)
        text = self.path.read_text()
        self.assertIn('**Schema validation:** passed; rendered by `' + str(render_report.SCRIPT) + '` (plugin ', text)

    def test_domain_exclusion_is_visible_in_rendered_report(self):
        self.report['provenance']['exclusions'].append('Domain business logic (domain=off)')
        self.report['coverage_inventory'].update(
            domain_modules=[], domain_modules_reason='Domain business logic excluded (domain=off)')
        self.assertEqual(self.run_on(self.report), 0)
        out = self.path.read_text()
        self.assertIn('**Exclusions:** runtime behavior; Domain business logic (domain=off)', out)
        self.assertIn('**Domain modules:** Domain business logic excluded (domain=off)', out)
        self.assertEqual(load_report(self.path), self.report)

    def test_invalid_report_writes_nothing(self):
        self.report['overall']['confidence'] = 'high'  # provisional overall cannot be high; derivation cannot fix a judgment
        text = document(self.report)
        self.assertEqual(self.run_on(self.report, text), 1)
        self.assertEqual(self.path.read_text(), text)

    def test_missing_marker_writes_nothing(self):
        text = document(self.report).replace('<!-- render:scorecard -->', '')
        self.assertEqual(self.run_on(self.report, text), 1)
        self.assertEqual(self.path.read_text(), text)

    def test_item_and_decision_blocks(self):
        r = copy.deepcopy(self.report)
        r['items'] = [{'id': 'F-1', 'area': 'RES', 'also_areas': ['IDEM'], 'severity': 'medium', 'rules': ['RES-BAD-1'], 'effort': 'S',
                       'title': 'Unbounded call', 'fingerprint': 'orders:lookup:unbounded', 'confidence': 'confirmed',
                       'evidence': ['client.go:24'], 'verification': 'Planned: stalled dependency returns within budget.'}]
        r['areas'][0]['counts']['medium'] = 1
        self.assertEqual(self.run_on(r), 1)  # impact/fix missing
        r['items'][0].update(impact='Lookup hangs.', fix='Inherit the request deadline.', priority='now')
        self.assertEqual(self.run_on(r), 0)
        out = self.path.read_text()
        self.assertIn('### F-1 · Unbounded call — Medium', out)
        self.assertIn('- **Area:** RES; also IDEM · **Rule:** RES-BAD-1 · **Confidence:** confirmed', out)
        d = {'id': 'D-1', 'title': 'Inbox', 'choice': 'DB inbox', 'rules': ['IDEM-BP-7'], 'options': ['DB inbox', 'Redis'],
             'why': 'Atomic with effect', 'tradeoff': 'More rows', 'revisit': '> 5k events/s'}
        self.assertIn('**D-1 · Inbox** — Options: DB inbox; Redis · Chosen: DB inbox', render_report.decisions({'decisions': [d]}))

    def full_item(self, ident, **kw):
        base = {'id': ident, 'area': 'RES', 'severity': 'medium', 'rules': ['RES-BAD-1'], 'effort': 'S', 'priority': 'next', 'title': 'Call ' + ident,
                'fingerprint': 'orders:' + ident, 'confidence': 'confirmed', 'evidence': ['client.go:24'], 'verification': 'Planned: ' + ident,
                'impact': 'Hangs.', 'fix': 'Bound it.'}
        base.update(kw); return base

    def test_plan_is_rendered_from_items_in_priority_order(self):
        r = copy.deepcopy(self.report)
        r['areas'][0]['score'] = 5
        r['items'] = [self.full_item('F-1', priority='later', severity='low'), self.full_item('F-2', priority='now', depends_on=['F-3']),
                      self.full_item('F-3', priority='now', severity='high'), self.full_item('F-4', severity='info', priority=None)]
        del r['items'][3]['priority']
        self.assertEqual(self.run_on(r), 0)
        out = self.path.read_text()
        plan = out.split('<!-- render:plan -->')[1].split('<!-- /render:plan -->')[0]
        rows = [l for l in plan.splitlines() if l.startswith('| ')][2:]
        self.assertEqual([l.split(' | ')[1] for l in rows], ['F-3 · Call F-3 (high)', 'F-2 · Call F-2 (medium)', 'F-1 · Call F-1 (low)'])
        self.assertIn('| Now | F-2 · Call F-2 (medium) | S | F-3 | Planned: F-2 |', plan)
        self.assertIn('- **Effort:** S · **Priority:** Now · **Depends on:** F-3 · **Fingerprint:** orders:F-2', out)
        self.assertNotIn('F-4', plan)

    def test_derived_fields_are_filled_and_written_back(self):
        r = copy.deepcopy(self.report)
        r['areas'][0]['score'] = 3
        r['items'] = [self.full_item('F-1', severity='critical', priority='now')]
        for key in ('score', 'score_inputs', 'denominator', 'capped', 'provisional', 'blockers', 'readiness'): del r['overall'][key]
        del r['areas'][0]['counts'], r['areas'][1]['counts']
        self.assertEqual(self.run_on(r), 0)
        got = load_report(self.path)
        self.assertEqual(got['areas'][0]['counts'], {'critical': 1, 'high': 0, 'medium': 0, 'low': 0})
        self.assertIsNone(got['areas'][1]['counts'])
        self.assertEqual({k: got['overall'][k] for k in ('score', 'score_inputs', 'denominator', 'capped', 'provisional', 'blockers', 'readiness')},
                         {'score': 3.0, 'score_inputs': [3], 'denominator': 1, 'capped': True, 'provisional': True, 'blockers': ['F-1'], 'readiness': 'blocked'})

    def test_derive_never_lets_the_model_raise_readiness(self):
        r = copy.deepcopy(self.report)
        r['overall'].update(readiness='supported_in_scope', blockers=['F-9'])  # an unmet mandatory requirement named by the model
        self.assertEqual(self.run_on(r), 0)
        self.assertEqual(load_report(self.path)['overall']['readiness'], 'blocked')
        r['overall'].update(readiness='supported_in_scope', blockers=[])
        self.assertEqual(self.run_on(r), 0)
        self.assertEqual(load_report(self.path)['overall']['readiness'], 'undetermined')  # partial area, planned validation

    def test_validation_and_strengths_markers_cannot_be_dropped(self):
        for name in ('validation', 'strengths', 'plan'):
            text = document(self.report).replace(f'<!-- render:{name} -->', '')
            self.assertEqual(self.run_on(self.report, text), 1, name)
            self.assertEqual(self.path.read_text(), text)

    def test_documented_required_markers_match_the_renderer(self):
        doc = (ROOT / 'shared/report.md').read_text()
        for label, shape in (('header, scorecard', 'full'), ('header, items, not_examined', 'triage'), ('header, assumptions', 'design')):
            line = [l for l in doc.splitlines() if l.startswith('Required markers: ' + label)]
            self.assertEqual(len(line), 1, label)
            documented = [w.strip() for w in re.match(r'Required markers: ([a-z_, ]+)', line[0])[1].split(',')]
            self.assertEqual(documented, list(render_report.REQUIRED[shape]), shape)

def doc_for(report, names):
    markers = '\n\n'.join(f'<!-- render:{n} -->' for n in names)
    return f'# x\n\n{markers}\n\n```json\n{json.dumps(report, indent=1)}\n```\n'

class ShapeRenderTests(unittest.TestCase):
    def setUp(self):
        examples = load_examples(ROOT / 'shared/report.md')
        self.triage = [x for x in examples if x.get('depth') == 'triage'][0]
        self.design = [x for x in examples if x.get('mode') == 'design'][0]
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'r.md'
    def tearDown(self): self.tmp.cleanup()
    def run_on(self, text):
        import sys
        self.path.write_text(text)
        argv, sys.argv = sys.argv, ['render_report.py', str(self.path)]
        try: return render_report.main()
        finally: sys.argv = argv

    def test_triage_renders_without_scores(self):
        self.assertEqual(self.run_on(doc_for(self.triage, ('header', 'items', 'not_examined'))), 0)
        out = self.path.read_text()
        self.assertIn('audit (triage)', out)
        self.assertIn('- Runtime recovery behavior', out)
        self.assertNotIn('Overall', out)
        self.assertIn('**Units counted:** 3 entry_points; 1 external_dependencies', out)

    def test_triage_missing_not_examined_marker_writes_nothing(self):
        text = doc_for(self.triage, ('header', 'items'))
        self.assertEqual(self.run_on(text), 1)
        self.assertEqual(self.path.read_text(), text)

    def test_design_renders_assumptions_decisions_risks_without_scorecard(self):
        self.assertEqual(self.run_on(doc_for(self.design, ('header', 'assumptions', 'decisions', 'risks', 'validation'))), 0)
        out = self.path.read_text()
        self.assertIn('| A-1 | Provider retries for up to 3 days', out)
        self.assertIn('**D-1 · Dedup on provider event ID**', out)
        self.assertIn('Assumptions: A-1', out)
        self.assertIn('### R-1 · Inbox grows without a purge — Low', out)
        self.assertNotIn('Readiness', out)
        self.assertNotIn('Scorecard', out)

    def test_design_without_risks_says_so(self):
        self.design['risks'] = []
        self.assertEqual(self.run_on(doc_for(self.design, ('header', 'assumptions', 'decisions', 'risks', 'validation'))), 0)
        self.assertIn('_No residual risks established._', self.path.read_text())

    def test_design_needs_assumptions_marker(self):
        self.assertEqual(self.run_on(doc_for(self.design, ('header', 'decisions', 'risks', 'validation'))), 1)

if __name__ == '__main__': unittest.main()


class PriorRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.path = Path(self.tmp.name) / 'r.md'
        self.prior_path = Path(self.tmp.name) / 'prior.json'
    def tearDown(self): self.tmp.cleanup()
    def run_on(self, report, *extra):
        import sys
        self.path.write_text('# x\n\n<!-- render:header -->\n\n<!-- render:items -->\n\n<!-- render:not_examined -->\n\n<!-- render:prior -->\n\n```json\n' + json.dumps(report) + '\n```\n')
        argv, sys.argv = sys.argv, ['render_report.py', str(self.path), *extra]
        try: return render_report.main()
        finally: sys.argv = argv
    def report(self):
        r = copy.deepcopy([x for x in load_examples(ROOT / 'shared/report.md') if x.get('depth') == 'triage'][0])
        item = {'id': 'F-4', 'area': 'IDEM', 'severity': 'low', 'rules': ['RES-BAD-1'], 'effort': 'S', 'priority': 'next', 'title': 'New risk', 'fingerprint': 'orders:ship:new',
                'confidence': 'confirmed', 'evidence': ['service.go:30'], 'verification': 'Planned.', 'impact': 'x', 'fix': 'y'}
        r['items'] = [item]
        r['provenance'].update(revision='9f8e7d6', prior={'source': 'p.json', 'mode': 'audit', 'revision': 'a1b2c3d', 'date': '2026-11-01'})
        r['prior_verdicts'] = [{'item': 'F-1', 'title': 'Inbox outside tx', 'fingerprint': 'orders:ship:inbox', 'verdict': 'fixed', 'fixed_at': '9f8e7d6', 'evidence': ['service.go:30']}]
        return r
    def test_verdict_table_says_fixed_at_the_revision_and_lists_new_items(self):
        self.assertEqual(self.run_on(self.report()), 0)
        out = self.path.read_text()
        self.assertIn('| F-1 | Inbox outside tx | fixed at 9f8e7d6 | service.go:30 |', out)
        self.assertIn('**New in this audit:** F-4', out)
        self.assertIn('revision a1b2c3d', out)
    def test_prior_marker_cannot_be_dropped(self):
        self.path.write_text('# x\n\n<!-- render:header -->\n\n<!-- render:items -->\n\n<!-- render:not_examined -->\n\n```json\n' + json.dumps(self.report()) + '\n```\n')
        import sys
        argv, sys.argv = sys.argv, ['render_report.py', str(self.path)]
        try: self.assertEqual(render_report.main(), 1)
        finally: sys.argv = argv
    def test_prior_file_is_checked_for_coverage(self):
        self.prior_path.write_text(json.dumps({'mode': 'audit', 'date': '2026-11-01', 'provenance': {'revision': 'a1b2c3d'},
                                               'items': [{'id': 'F-1', 'fingerprint': 'orders:ship:inbox'}, {'id': 'F-2', 'fingerprint': 'orders:other'}]}))
        self.assertEqual(self.run_on(self.report(), '--prior', str(self.prior_path)), 1)  # F-2 has no verdict
