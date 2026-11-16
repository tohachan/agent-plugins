import unittest
from validate_repository import decision_errors, rules_layout_errors, checks_layout_errors, abbreviation_errors, orphan_errors, domain_check_errors

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
    def test_spaced_range_and_list_rejected(self):
        for t in ('SEC-BP-1 / 3', 'SEC-BP-1\u20133', 'SEC-BP-1-3', 'SEC-BP-1, 3', 'SEC-BP-1 and 3'): self.assertTrue(abbreviation_errors('s', t), t)
    def test_bare_id_rejected(self): self.assertTrue(abbreviation_errors('s', 'use (BP-8)'))
    def test_full_ids_ok(self): self.assertEqual(abbreviation_errors('s', 'PERF-BP-1, PERF-BP-3 and IDEM-BP-12, IDEM-BP-13; XX-BP-n'), [])
    def test_orphan_rejected(self): self.assertEqual(len(orphan_errors({'A-BP-1': 1, 'A-BP-2': 1, 'A-CHK-1': 1}, {'A-BP-1'})), 1)
    def test_no_orphans_ok(self): self.assertEqual(orphan_errors({'A-BP-1': 1, 'A-CHK-1': 1}, {'A-BP-1'}), [])

class DomainChecksTests(unittest.TestCase):
    ROW = '| SEC-CHK-21 | q | e | High |\n'
    def test_row_registered(self):
        defs = {}
        self.assertEqual(domain_check_errors('d', self.ROW, {'sec'}, defs), [])
        self.assertIn('SEC-CHK-21', defs)
    def test_unknown_area_rejected(self): self.assertTrue(domain_check_errors('d', self.ROW, {'idem'}, {}))
    def test_duplicate_of_area_check_rejected(self): self.assertTrue(domain_check_errors('d', self.ROW, {'sec'}, {'SEC-CHK-21': 1}))
    def test_ticked_id_rejected(self): self.assertTrue(domain_check_errors('d', '| `SEC-CHK-21` | q | e | High |\n', {'sec'}, {}))

if __name__ == '__main__': unittest.main()

class ManifestTests(unittest.TestCase):
    """Claude and Codex cache a plugin by version: manifests that disagree install a stale copy in one runtime."""
    def setUp(self):
        import json, tempfile
        from pathlib import Path
        self.json, self.tmp = json, tempfile.TemporaryDirectory()
        self.market = Path(self.tmp.name); self.plugin = self.market / 'plugins' / 'p'
        (self.plugin / 'skills').mkdir(parents=True)
        self.write(self.plugin / '.claude-plugin/plugin.json', {'name': 'p', 'version': '1.0.0'})
        self.write(self.plugin / '.codex-plugin/plugin.json', {'name': 'p', 'version': '1.0.0', 'skills': './skills/'})
        self.write(self.market / '.claude-plugin/marketplace.json', {'plugins': [{'name': 'p', 'version': '1.0.0', 'source': './plugins/p'}]})
        self.write(self.market / '.agents/plugins/marketplace.json', {'plugins': [{'name': 'p', 'version': '1.0.0', 'source': {'source': 'local', 'path': './plugins/p'}}]})
    def tearDown(self): self.tmp.cleanup()
    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(self.json.dumps(data))
    def errors(self, market=True):
        from validate_repository import manifest_errors
        return manifest_errors(self.plugin, self.market if market else None)
    def test_consistent_ok(self): self.assertEqual(self.errors(), [])
    def test_codex_version_drift_rejected(self):
        self.write(self.plugin / '.codex-plugin/plugin.json', {'name': 'p', 'version': '1.1.0', 'skills': './skills/'})
        self.assertTrue(any('disagree' in e for e in self.errors()))
    def test_marketplace_version_drift_rejected(self):
        self.write(self.market / '.agents/plugins/marketplace.json', {'plugins': [{'name': 'p', 'version': '0.9.0', 'source': {'source': 'local', 'path': './plugins/p'}}]})
        self.assertTrue(any('disagree' in e for e in self.errors()))
    def test_missing_codex_manifest_rejected(self):
        (self.plugin / '.codex-plugin/plugin.json').unlink()
        self.assertTrue(self.errors(market=False))
    def test_missing_codex_marketplace_entry_rejected(self):
        self.write(self.market / '.agents/plugins/marketplace.json', {'plugins': []})
        self.assertTrue(any('found 0' in e for e in self.errors()))
    def test_source_elsewhere_rejected(self):
        self.write(self.market / '.claude-plugin/marketplace.json', {'plugins': [{'name': 'p', 'version': '1.0.0', 'source': './plugins/q'}]})
        self.assertTrue(any('does not point' in e for e in self.errors()))
    def test_codex_skills_path_missing_rejected(self):
        self.write(self.plugin / '.codex-plugin/plugin.json', {'name': 'p', 'version': '1.0.0', 'skills': './nope/'})
        self.assertTrue(any('skills path' in e for e in self.errors()))
    def test_standalone_plugin_skips_marketplaces(self): self.assertEqual(self.errors(market=False), [])
