import copy
from pathlib import Path
import tempfile
import unittest

from validate_report import load_report, load_examples, validate, ROOT

class ReportContractTests(unittest.TestCase):
    def setUp(self): self.report = load_report(ROOT/'shared/report.md')
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
        return {'id':'F-1','area':'RES','severity':severity,'rules':['RES-BAD-1'],'effort':'S','priority':'now','title':'Unbounded call','fingerprint':'orders:lookup:unbounded','confidence':'confirmed','evidence':['client.go:24'],'verification':'Planned: stalled dependency returns within the budget.'}
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
        self.assertTrue(any('3.0' in x for x in validate(self.report)))
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
    def test_uncovered_requires_gaps_but_index_is_optional(self):
        u = self.ci()['units'][0]; u.update(checked=2, not_covered=1)
        errors = validate(self.report)
        self.assertTrue(any('coverage_inventory.gaps' in x for x in errors))
        self.assertFalse(any('index_recommendation' in x for x in errors))
        self.ci()['gaps'] = ['one entry point not read']
        self.assertEqual(validate(self.report), [])
        self.ci()['index_recommendation'] = ''
        self.assertTrue(any('index_recommendation' in x for x in validate(self.report)))
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
    def technical_scope(self):
        self.report['provenance']['exclusions'].append('Domain business logic (domain=off)')
        self.ci().update(domain_modules=[], domain_modules_reason='Domain business logic excluded (domain=off)')
        self.report['areas'][0].update(status='assessed', confidence='high',
            coverage={'verified': 2, 'violation': 0, 'unverified': 0, 'not_applicable': 0}, unknowns=[])
        self.report['validation'][0].update(status='passed', evidence=['Recovery test passed'])
        self.report['overall'].update(readiness='supported_in_scope', provisional=False, confidence='high', unknowns=[])
    def test_domain_exclusion_allows_supported_technical_scope(self):
        self.technical_scope()
        self.assertEqual(validate(self.report), [])
    def test_domain_exclusion_does_not_hide_technical_coverage_gaps(self):
        self.technical_scope()
        self.ci()['units'][0].update(checked=2, not_covered=1)
        self.ci().update(gaps=['One entry point not inspected'], index_recommendation='Enumerate routes using an index')
        self.assertTrue(any('not covered' in x for x in validate(self.report)))
    def test_invariant_requires_source(self):
        self.ci()['invariants'][0]['source'] = ''
        self.assertTrue(any('source required' in x for x in validate(self.report)))
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

class ContractRuleTests(unittest.TestCase):
    """The rules the prose of shared/report.md states, one test each."""
    def setUp(self): self.report = load_report(ROOT/'shared/report.md')
    def ci(self): return self.report['coverage_inventory']
    def item(self, ident='F-1', **kw):
        base = {'id': ident, 'area': 'RES', 'severity': 'low', 'rules': ['RES-BAD-1'], 'effort': 'S', 'priority': 'next', 'title': 'Unbounded call ' + ident,
                'fingerprint': 'orders:lookup:' + ident, 'confidence': 'confirmed', 'evidence': ['client.go:24'], 'verification': 'Planned.'}
        base.update(kw); return base
    def test_sampled_only_for_read_only_tier(self):
        u = self.ci()['units'][0]; u.update(checked=1, sampled=2, sampling='every 3rd route, 3 of 3', owner='lead')
        self.ci().update(gaps=['entry points sampled'])
        self.assertTrue(any('risk_tier' in x for x in validate(self.report)))
        u['risk_tier'] = 'writes-state'
        self.assertTrue(any('risk_tier' in x for x in validate(self.report)))
        u['risk_tier'] = 'read-only'
        self.assertEqual(validate(self.report), [])
    def test_risk_tier_value_is_checked_even_unsampled(self):
        self.ci()['units'][0]['risk_tier'] = 'bogus'
        self.assertTrue(any('risk_tier must be' in x for x in validate(self.report)))
    def test_sampled_module_needs_read_only_tier(self):
        self.ci()['domain_modules'][0]['status'] = 'sampled'; self.ci()['gaps'] = ['orders/lookup sampled']
        self.assertTrue(any('risk_tier' in x for x in validate(self.report)))
        self.ci()['domain_modules'][0]['risk_tier'] = 'read-only'
        self.assertEqual(validate(self.report), [])
    def test_valid_sampling_does_not_block_supported_but_uncovered_does(self):
        a = self.report['areas'][0]
        a.update(status='assessed', confidence='high', coverage={'verified': 2, 'violation': 0, 'unverified': 0, 'not_applicable': 0}, unknowns=[])
        self.report['validation'][0].update(status='passed', evidence=['Recovery test passed'])
        self.report['overall'].update(readiness='supported_in_scope', provisional=False, confidence='high')
        self.assertEqual(validate(self.report), [])
        self.ci()['units'][0].update(checked=1, sampled=2, sampling='every 3rd route', risk_tier='read-only'); self.ci()['gaps'] = ['sampled']
        self.assertEqual(validate(self.report), [])
        self.ci()['units'][0].update(sampled=0, not_covered=2)
        self.assertTrue(any('not covered' in x for x in validate(self.report)))
    def test_priority_required_except_info_and_depends_on_checked(self):
        item = self.item(); del item['priority']; self.report['items'] = [item]; self.report['areas'][0]['counts']['low'] = 1
        self.assertTrue(any('priority' in x for x in validate(self.report)))
        item['severity'] = 'info'; self.report['areas'][0]['counts']['low'] = 0
        self.assertEqual(validate(self.report), [])
        item['priority'] = 'soon'
        self.assertTrue(any('priority' in x for x in validate(self.report)))
    def test_depends_on_must_name_other_items_without_cycles(self):
        a, b = self.item('F-1', depends_on=['F-9']), self.item('F-2')
        self.report['items'] = [a, b]; self.report['areas'][0]['counts']['low'] = 2
        self.assertTrue(any('depends_on' in x for x in validate(self.report)))
        a['depends_on'] = ['F-1']; self.assertTrue(any('depends_on' in x for x in validate(self.report)))
        a['depends_on'] = ['F-2']; b['depends_on'] = ['F-1']
        self.assertTrue(any('cycle' in x for x in validate(self.report)))
        b.pop('depends_on'); self.assertEqual(validate(self.report), [])
    def test_strengths_need_control_boundary_evidence(self):
        self.report['strengths'] = [{'control': 'Deadline propagation', 'boundary': '', 'evidence': []}]
        errors = validate(self.report)
        self.assertTrue(any('boundary' in x for x in errors) and any('evidence' in x for x in errors))
    def test_models_are_role_model_rows(self):
        self.report['provenance']['models'] = [{'role': 'lead'}]
        self.assertTrue(any('provenance.models' in x for x in validate(self.report)))
        self.report['provenance']['models'] = [{'role': 'lead', 'model': 'opus', 'effort': 'medium'}]
        self.assertEqual(validate(self.report), [])
    def test_noted_unknowns_do_not_move_readiness_but_material_ones_do(self):
        self.report['areas'][0].update(status='assessed', confidence='high', coverage={'verified': 2, 'violation': 0, 'unverified': 0, 'not_applicable': 0}, unknowns=[])
        self.report['validation'][0].update(status='passed', evidence=['Recovery test passed'])
        self.report['overall'].update(readiness='supported_in_scope', provisional=False, confidence='high', unknowns=[], noted_unknowns=['Runtime behavior not observed'])
        self.assertEqual(validate(self.report), [])
        self.report['overall']['unknowns'] = ['Failover untested: a retry storm would go unseen']
        self.assertTrue(any('undetermined' in x for x in validate(self.report)))
    def test_check_ids_are_not_rules(self):
        self.report['items'] = [self.item(rules=['RES-CHK-1'])]; self.report['areas'][0]['counts']['low'] = 1
        self.assertTrue(any('unknown rule' in x for x in validate(self.report)))
    def test_document_citations_are_not_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.report['areas'][0]['evidence'] = ['RFC 9110:15', 'client.go:1']
            (Path(tmp)/'client.go').write_text('x\n' * 30)
            self.assertEqual(validate(self.report, tmp), [])
    def test_coverage_and_area_rules_stated_in_prose(self):
        a = self.report['areas'][0]
        a['coverage'] = {'verified': 1, 'violation': 0, 'unverified': 1}
        self.assertTrue(any('invalid coverage' in x for x in validate(self.report)))
        a['coverage'] = {'verified': 0, 'violation': 0, 'unverified': 0, 'not_applicable': 0}
        self.assertTrue(any('empty coverage' in x for x in validate(self.report)))
    def test_entry_points_required_for_invariants(self):
        self.ci()['invariants'][0]['entry_points'] = []
        self.assertTrue(any('entry_points' in x for x in validate(self.report)))

class TriageContractTests(unittest.TestCase):
    def setUp(self):
        self.report = [x for x in load_examples(ROOT/'shared/report.md') if x.get('depth') == 'triage'][0]
    def test_documented_example(self): self.assertEqual(validate(self.report), [])
    def test_no_scores_or_inventory_needed(self):
        for key in ('areas', 'overall', 'coverage_inventory'): self.assertNotIn(key, self.report)
    def test_not_examined_required(self):
        self.report['not_examined'] = []
        self.assertTrue(any('not_examined' in x for x in validate(self.report)))
    def test_depth_required(self):
        del self.report['depth']
        self.assertTrue(any('depth' in x for x in validate(self.report)))
    def test_finding_needs_evidence_and_known_area(self):
        self.report['items'] = [{'id': 'F-1', 'area': 'RES', 'severity': 'high', 'rules': ['RES-BAD-1'], 'effort': 'S', 'priority': 'now', 'title': 'Unbounded call',
                                 'fingerprint': 'orders:lookup:unbounded', 'confidence': 'confirmed', 'evidence': [], 'verification': 'Planned.'}]
        self.assertTrue(any('evidence' in x for x in validate(self.report)))
        self.report['items'][0].update(evidence=['client.go:24'], area='NOPE')
        self.assertTrue(any('out of scope' in x for x in validate(self.report)))
        self.report['items'][0]['area'] = 'RES'
        self.assertEqual(validate(self.report), [])
    def test_optional_scores_are_still_checked_when_present(self):
        self.report['overall'] = {'score': 9}
        self.assertTrue(validate(self.report))
    def test_suggestion_is_null_or_text(self):
        self.report['full_audit_suggested'] = ''
        self.assertTrue(any('full_audit_suggested' in x for x in validate(self.report)))

class DesignContractTests(unittest.TestCase):
    def setUp(self):
        self.report = [x for x in load_examples(ROOT/'shared/report.md') if x.get('mode') == 'design'][0]
    def test_documented_example_needs_no_scorecard_or_readiness(self):
        self.assertEqual(validate(self.report), [])
        for key in ('areas', 'overall', 'coverage_inventory'): self.assertNotIn(key, self.report)
    def test_scorecard_fields_rejected(self):
        self.report['overall'] = {'readiness': 'supported_in_scope'}
        self.assertTrue(any('no overall' in x for x in validate(self.report)))
    def test_assumptions_required(self):
        self.report['assumptions'] = []
        self.assertTrue(any('assumptions' in x for x in validate(self.report)))
    def test_assumption_needs_threshold(self):
        self.report['assumptions'][0]['threshold'] = ''
        self.assertTrue(any('threshold' in x for x in validate(self.report)))
    def test_decision_references_checked(self):
        self.report['decisions'][0]['assumptions'] = ['A-9']
        self.report['decisions'][0]['validation'] = ['V-9']
        errors = validate(self.report)
        self.assertTrue(any('invalid assumptions' in x for x in errors) and any('invalid validation' in x for x in errors))
    def test_unknown_rule_rejected(self):
        self.report['decisions'][0]['rules'] = ['IDEM-BP-9999']
        self.assertTrue(any('unknown rule' in x for x in validate(self.report)))
    def test_validation_required_and_planned_is_not_passed(self):
        self.report['validation'][0]['status'] = 'passed'
        self.assertTrue(any('result evidence' in x for x in validate(self.report)))
        self.report['validation'] = []
        self.assertTrue(any('validation' in x for x in validate(self.report)))
    def test_risk_needs_scenario_and_known_assumption(self):
        self.report['risks'][0]['scenario'] = ''
        self.report['risks'][0]['assumptions'] = ['A-7']
        errors = validate(self.report)
        self.assertTrue(any('scenario' in x for x in errors) and any('invalid assumptions' in x for x in errors))
    def test_risks_may_be_empty(self):
        self.report['risks'] = []
        self.assertEqual(validate(self.report), [])
    def test_audit_schema_is_not_accepted_for_design(self):
        self.report['schema_version'] = '2.1'
        self.assertTrue(any('3.0' in x for x in validate(self.report)))

if __name__ == '__main__': unittest.main()
