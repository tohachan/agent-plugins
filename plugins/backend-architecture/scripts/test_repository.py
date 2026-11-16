import unittest
from validate_repository import decision_errors, rules_layout_errors, checks_layout_errors, abbreviation_errors, orphan_errors

HEAD = '| Decision | Options | Choose … when | Trade-off | Rules |\n| --- | --- | --- | --- | --- |\n'
DEFS = {'ARCH-BP-1': 1, 'ARCH-AP-7': 1}

class DecisionRulesColumnTests(unittest.TestCase):
    def check(self, rows, head=HEAD): return decision_errors('x', head + rows, DEFS)
    def test_valid_ids(self): self.assertEqual(self.check('| a | b | c | d | ARCH-BP-1, ARCH-AP-7 |\n'), [])
    def test_explicit_dash(self): self.assertEqual(self.check('| a | b | c | d | — |\n'), [])
    def test_empty_cell_rejected(self): self.assertTrue(self.check('| a | b | c | d |  |\n'))
    def test_unknown_id_rejected(self): self.assertIn('unknown ARCH-BP-9', self.check('| a | b | c | d | ARCH-BP-9 |\n')[0])
    def test_prose_rejected(self): self.assertTrue(self.check('| a | b | c | d | see ARCH-BP-1 |\n'))
    def test_missing_column_rejected(self): self.assertTrue(self.check('| a | b | c | d |\n', '| Decision | Options | Choose … when | Trade-off |\n| --- | --- | --- | --- |\n'))
    def test_short_row_rejected(self): self.assertTrue(self.check('| a | b | c | ARCH-BP-1 |\n'))
    def test_trailing_whitespace_ok(self): self.assertEqual(self.check('| a | b | c | d | ARCH-BP-1 |  \n'), [])
    def test_header_only_rejected(self): self.assertTrue(self.check(''))
    def test_missing_separator_rejected(self): self.assertTrue(self.check('| a | b | c | d | ARCH-BP-1 |\n', HEAD.splitlines()[0] + '\n'))
    def test_dash_mixed_with_id_rejected(self): self.assertTrue(self.check('| a | b | c | d | \u2014, ARCH-BP-1 |\n'))

class IdHygieneTests(unittest.TestCase):
    def test_one_line_rules_ok(self): self.assertEqual(rules_layout_errors('r', '`A-BP-1` — **x.** y\n\n`A-AP-1` — **n.** Symptoms: a. Way out: b.\n'), [])
    def test_marker_rejected(self): self.assertTrue(rules_layout_errors('r', '- `A-BP-1` — **x.** y\n'))
    def test_ap_continuation_rejected(self): self.assertIn('continues', rules_layout_errors('r', '`A-AP-1` — **n.**\n- Symptoms: a\n')[0])
    def test_bp_continuation_rejected(self): self.assertTrue(rules_layout_errors('r', '`A-BP-1` — **x.**\nmore\n'))
    def test_last_line_rule_ok(self): self.assertEqual(rules_layout_errors('r', '`A-BP-1` — **x.**'), [])
    def test_ticked_check_rejected(self): self.assertTrue(checks_layout_errors('c', '| `A-CHK-1` | q | e | high |\n'))
    def test_plain_check_ok(self): self.assertEqual(checks_layout_errors('c', '| A-CHK-1 | q | e | high |\n'), [])
    def test_slash_abbreviation_rejected(self): self.assertTrue(abbreviation_errors('s', 'see IDEM-BP-12/13'))
    def test_comma_abbreviation_rejected(self): self.assertTrue(abbreviation_errors('s', 'PERF-BP-1, BP-3, BAD-2'))
    def test_bare_id_rejected(self): self.assertTrue(abbreviation_errors('s', 'use (BP-8)'))
    def test_full_ids_ok(self): self.assertEqual(abbreviation_errors('s', 'PERF-BP-1, PERF-BP-3 and IDEM-BP-12, IDEM-BP-13; XX-BP-n'), [])
    def test_orphan_rejected(self): self.assertEqual(len(orphan_errors({'A-BP-1': 1, 'A-BP-2': 1, 'A-CHK-1': 1}, {'A-BP-1'})), 1)
    def test_no_orphans_ok(self): self.assertEqual(orphan_errors({'A-BP-1': 1, 'A-CHK-1': 1}, {'A-BP-1'}), [])

if __name__ == '__main__': unittest.main()
