import copy
from pathlib import Path
import tempfile
import unittest

from validate_report import load_report, validate, ROOT

class ReportContractTests(unittest.TestCase):
    def setUp(self): self.report = load_report(ROOT/'shared/output-format.md')
    def test_documented_example(self): self.assertEqual(validate(self.report), [])
    def test_false_overall_is_rejected(self):
        self.report['overall']['score'] = 9
        self.assertTrue(validate(self.report))
    def test_formula_denominator_is_checked(self):
        self.report['overall']['denominator'] = 13
        self.assertTrue(validate(self.report))
    def test_partial_cannot_claim_high_confidence_or_score(self):
        self.report['areas'][0].update(score=9, confidence='high')
        self.assertTrue(any('partial cap' in x for x in validate(self.report)))
    def test_unverified_is_not_zero(self):
        a=self.report['areas'][0]; a.update(status='unverified',score=0,confidence=None)
        self.assertTrue(any('score/confidence' in x for x in validate(self.report)))
    def test_no_scores_has_no_mean(self):
        a=self.report['areas'][0]; a.update(status='unverified',score=None,confidence=None)
        o=self.report['overall']; o.update(score=None,confidence=None,score_inputs=[],denominator=0)
        self.assertEqual(validate(self.report), [])
    def test_assessed_requires_applicable_evidence(self):
        self.report['areas'][0].update(status='assessed',coverage={'verified':0,'violation':0,'unverified':0,'not_applicable':1})
        self.assertTrue(any('without applicable' in x for x in validate(self.report)))
    def item(self, severity='high'):
        return {'id':'F-1','area':'RES','severity':severity,'rules':['RES-BAD-1'],'effort':'S','title':'Unbounded call','fingerprint':'orders:lookup:unbounded','confidence':'confirmed','evidence':['client.go:24'],'verification':'Planned: stalled dependency returns within the budget.'}
    def test_high_cannot_hide_in_mean(self):
        self.report['items']=[self.item()]
        self.report['areas'][0]['counts']['high']=1
        errors=validate(self.report)
        self.assertTrue(any('High cap' in x for x in errors))
        self.assertTrue(any('missing from blockers' in x for x in errors))
    def test_critical_in_unverified_area_still_caps_overall(self):
        a=self.report['areas'][1]
        a.update(status='unverified', counts={'critical':1,'high':0,'medium':0,'low':0}, coverage={'verified':0,'violation':1,'unverified':1,'not_applicable':0},unknowns=['Cache configuration missing'])
        item=self.item('critical'); item['area']='CACHE'; self.report['items']=[item]
        self.report['overall'].update(score=4.0,capped=True,readiness='blocked',blockers=['F-1'])
        self.assertEqual(validate(self.report), [])
    def test_unknown_rule_rejected(self):
        self.report['items']=[self.item()]; self.report['items'][0]['rules']=['RES-BP-999']
        self.assertTrue(any('unknown rule' in x for x in validate(self.report)))
    def test_duplicate_root_cause_rejected(self):
        self.report['items']=[self.item(), self.item()]
        self.report['items'][1]['id']='F-2'
        self.assertTrue(any('root-cause' in x for x in validate(self.report)))
    def test_evidence_line_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'client.go').write_text('one line\n')
            self.assertTrue(any('line outside' in x for x in validate(self.report,tmp)))
    def test_evidence_path_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.report['areas'][0]['evidence']=['../secret:1']
            self.assertTrue(any('inaccessible' in x for x in validate(self.report,tmp)))
    def test_evidence_range_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'client.go').write_text('one\ntwo\n')
            self.report['areas'][0]['evidence']=['client.go:1-99']
            self.assertTrue(any('line outside' in x for x in validate(self.report,tmp)))
    def test_invalid_counts_type_rejected(self):
        self.report['areas'][0]['counts']=[1]
        self.assertTrue(validate(self.report))
    def test_old_schema_requires_migration(self):
        del self.report['schema_version']
        self.assertTrue(any('schema_version' in x for x in validate(self.report)))
    def test_missing_evidence_rejected(self):
        self.report['areas'][0]['evidence']=[]
        self.assertTrue(any('nonempty evidence' in x for x in validate(self.report)))
    def test_passed_test_requires_result(self):
        self.report['validation'][0]['status']='passed'
        self.assertTrue(any('nonempty evidence' in x for x in validate(self.report)))
    def test_supported_readiness_cannot_claim_planned_tests(self):
        self.report['overall']['readiness']='supported_in_scope'
        self.assertTrue(any('completed declared validation' in x for x in validate(self.report)))
    def test_boolean_score_rejected(self):
        self.report['areas'][0]['score']=True
        self.assertTrue(any('score must' in x for x in validate(self.report)))
    # ---- schema 2.1: coverage inventory and conditional severity
    def ci(self): return self.report['coverage_inventory']
    def test_legacy_schema_rejected(self):
        self.report['schema_version'] = '2.0'
        self.assertTrue(any('2.1' in x for x in validate(self.report)))
    def test_missing_coverage_inventory_rejected(self):
        del self.report['coverage_inventory']
        self.assertTrue(any('coverage_inventory' in x for x in validate(self.report)))
    def test_unassigned_units_rejected(self):
        self.ci()['units'][0]['total'] = 5
        self.assertTrue(any('no unassigned units' in x for x in validate(self.report)))
    def test_unit_without_owner_rejected(self):
        self.ci()['units'][0]['owner'] = ''
        self.assertTrue(any('owner pass' in x for x in validate(self.report)))
    def test_sampling_needs_rule(self):
        u = self.ci()['units'][0]; u.update(checked=1, sampled=2)
        self.ci()['gaps'] = ['entry points sampled']; self.ci()['index_recommendation'] = 'Enumerate routes over a code index'
        self.assertTrue(any('sampling rule' in x for x in validate(self.report)))
    def test_uncovered_requires_gaps_and_index(self):
        u = self.ci()['units'][0]; u.update(checked=2, not_covered=1)
        errors = validate(self.report)
        self.assertTrue(any('coverage_inventory.gaps' in x for x in errors))
        self.assertTrue(any('index_recommendation' in x for x in errors))
    def test_uncovered_module_forbids_supported(self):
        self.ci()['domain_modules'][0]['status'] = 'not_covered'
        self.ci()['gaps'] = ['orders/lookup not reviewed']; self.ci()['index_recommendation'] = 'Graph-indexed pass over the module'
        self.report['overall']['readiness'] = 'supported_in_scope'
        self.assertTrue(any('not covered' in x for x in validate(self.report)))
    def test_module_requires_owner(self):
        self.ci()['domain_modules'][0]['owner'] = ''
        self.assertTrue(any('domain module id and owner' in x for x in validate(self.report)))
    def test_empty_modules_need_reason(self):
        self.ci()['domain_modules'] = []
        self.assertTrue(any('domain_modules_reason' in x for x in validate(self.report)))
        self.ci()['domain_modules_reason'] = 'Single-mechanism focused audit'
        self.assertEqual(validate(self.report), [])
    def test_invariant_requires_source(self):
        self.ci()['invariants'][0]['source'] = ''
        self.assertTrue(any('source required' in x for x in validate(self.report)))
    def test_design_requires_invariants(self):
        self.report['mode'] = 'design'; self.ci()['invariants'] = []
        self.assertTrue(any('derived from the requirements' in x for x in validate(self.report)))
    def test_severity_if_must_be_higher(self):
        item = self.item('medium'); item['area'] = 'RES'; item.update(severity_if='low', trigger='pilot lifted')
        self.report['items'] = [item]; self.report['areas'][0]['counts']['medium'] = 1
        self.assertTrue(any('severity_if' in x for x in validate(self.report)))
        item['severity_if'] = 'high'; item['trigger'] = ''
        self.assertTrue(any('trigger required' in x for x in validate(self.report)))
        item['trigger'] = 'pilot allowlist lifted'
        self.assertEqual(validate(self.report), [])
    def test_prior_report_verdict_checked(self):
        self.report['prior_reports'] = [{'source': 'audit 2026-10-12', 'item': 'C1', 'prior_severity': 'critical', 'verdict': 'maybe', 'evidence': ['db.go:10']}]
        self.assertTrue(any('verdict' in x for x in validate(self.report)))
        self.report['prior_reports'][0]['verdict'] = 'refuted'
        self.assertEqual(validate(self.report), [])
    def test_bad_input_does_not_pass(self):
        for value in [[],{}, {'areas':[None]}]:
            self.assertTrue(validate(value))

if __name__ == '__main__': unittest.main()
