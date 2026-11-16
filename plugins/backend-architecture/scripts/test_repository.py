import unittest
from validate_repository import decision_errors

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

if __name__ == '__main__': unittest.main()
