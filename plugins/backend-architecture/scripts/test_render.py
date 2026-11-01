import copy
import json
from pathlib import Path
import tempfile
import unittest

from validate_report import load_report, ROOT
import render_report

MARKERS = '\n\n'.join(f'<!-- render:{n} -->' for n in ('header', 'scorecard', 'coverage', 'items', 'validation'))

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
        self.assertEqual(self.run_on(self.report, first), 0)
        self.assertEqual(self.path.read_text(), first)
        self.assertEqual(load_report(self.path), self.report)

    def test_invalid_report_writes_nothing(self):
        self.report['overall']['score'] = 9
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
        r['items'][0].update(impact='Lookup hangs.', fix='Inherit the request deadline.')
        self.assertEqual(self.run_on(r), 0)
        out = self.path.read_text()
        self.assertIn('### F-1 · Unbounded call — Medium', out)
        self.assertIn('- **Area:** RES; also IDEM · **Rule:** RES-BAD-1 · **Confidence:** confirmed', out)
        d = {'id': 'D-1', 'title': 'Inbox', 'choice': 'DB inbox', 'rules': ['IDEM-BP-7'], 'options': ['DB inbox', 'Redis'],
             'why': 'Atomic with effect', 'tradeoff': 'More rows', 'revisit': '> 5k events/s'}
        self.assertIn('**D-1 · Inbox** — Options: DB inbox; Redis · Chosen: DB inbox', render_report.decisions({'decisions': [d]}))

if __name__ == '__main__': unittest.main()
