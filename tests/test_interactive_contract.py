"""Independent hand-calculated oracles for the interactive contract."""
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import interactive_contract as c


class DecimalContractTests(unittest.TestCase):
    def test_dangerous_ids_and_interactive_manifest_ids_are_rejected(self):
        for value in ('__proto__', 'prototype', 'constructor', [], {}, None, True):
            with self.subTest(value=value), self.assertRaises(c.SceneValidationError): c.identifier(value)
        self.assertEqual(c.validate_interactive_slide_ids(['capacity', 'slide-002']), ('capacity', 'slide-002'))
        for ids in (['constructor'], ['UPPER'], ['a', 'a'], [None]):
            with self.assertRaises(c.SceneValidationError): c.validate_interactive_slide_ids(ids)

    def test_decimal_limits_and_canonical_text(self):
        loc = c.Location('scene.json', '/value')
        for raw, expected in [(D('-0.000'), '0'), (D('1.20'), '1.2'), (D('1e-6'), '0.000001')]:
            self.assertEqual(c.canonical_decimal(c.parse_decimal(raw, loc)), expected)
        for raw in [True, '1.2', D('NaN'), D('Infinity'), D('0.0000001'), D('1000000000001')]:
            with self.subTest(raw=raw), self.assertRaises(c.SceneValidationError):
                c.parse_decimal(raw, loc)

    def test_half_away_and_endpoint_grid(self):
        for n, d, want in [(5, 2, 3), (-5, 2, -3), (5, -2, -3), (4, 3, 1)]:
            self.assertEqual(c.round_scaled(n, d), want)
        domain = c.ControlDomain.range('x', D('-1'), D('1'), D('.2'))
        self.assertEqual(c.snap_range(D('-.7'), domain), D('-.6'))
        self.assertEqual(c.snap_range(D('100'), domain), D('1'))
        self.assertEqual(domain.values[-1], D('1'))
        with self.assertRaises(c.SceneValidationError):
            c.ControlDomain.range('x', D('0'), D('1'), D('.3'))


class QuantityEvidenceTests(unittest.TestCase):
    def test_audience_badge_is_compiler_owned_and_conservative(self):
        for bases, expected in [(('measured', 'estimated'), 'estimated'), (('measured', 'assumed'), 'assumed'), (('measured', 'assumed', 'illustrative'), 'illustrative')]:
            lineage = c.combine_lineage(*(c.Lineage(bases=(basis,)) for basis in bases), step='sum')
            self.assertEqual(lineage.as_dict()['badge'], expected)

    def test_combined_lineage_uses_registry_order_not_operand_traversal(self):
        evidence = {'sources': [{'id': 'first'}, {'id': 'second'}], 'assumptions': []}
        second = c.compile_provenance({'basis': 'measured', 'sourceRefs': ['second']}, evidence, c.Location())
        first = c.compile_provenance({'basis': 'measured', 'sourceRefs': ['first']}, evidence, c.Location())
        joined = c.combine_lineage(second, first, step='add')
        self.assertEqual(joined.source_refs, ('first', 'second'))

    def registry(self):
        return c.compile_quantities({
            'usd': {'dimension': 'currency', 'unit': 'USD', 'currency': 'USD', 'display': '$'},
            'eur': {'dimension': 'currency', 'unit': 'EUR', 'currency': 'EUR', 'display': '€'},
            'day': {'dimension': 'time', 'unit': 'day', 'display': 'days'},
            'rate': {'dimension': 'derived', 'unit': 'USD_day', 'currency': 'USD', 'display': '$/day', 'exponents': {'currency': 1, 'time': -1, 'count': 0}, 'unitFactors': {'USD': 1, 'day': -1}},
            'pct': {'dimension': 'ratio', 'unit': 'percent', 'display': '%'},
            'pp': {'dimension': 'ratio', 'unit': 'percentage_point', 'display': 'pp'},
            'score': {'dimension': 'score', 'unit': 'point', 'display': 'points'},
        }, c.Location())

    def test_storage_algebra_rejects_implicit_conversion(self):
        q = self.registry()
        self.assertEqual(c.infer_product_quantity(q['rate'], q['day'], q['usd'], 'multiply').id, 'usd')
        for a, b, result in [('usd', 'eur', 'usd'), ('score', 'day', 'score'), ('pct', 'day', 'pp')]:
            with self.subTest(a=a), self.assertRaises(c.SceneValidationError):
                c.infer_product_quantity(q[a], q[b], q[result], 'multiply')
        with self.assertRaises(c.SceneValidationError):
            c.require_same_quantity(q['pct'], q['pp'])
        with self.assertRaises(c.SceneValidationError):
            c.compile_quantities({'bad': {'dimension': 'currency', 'unit': 'ZZZ', 'currency': 'ZZZ', 'display': '$'}}, c.Location())

    def test_provenance_inheritance_retains_refs_and_conservative_basis(self):
        evidence = {'sources': [{'id': 'source'}], 'assumptions': [{'id': 'scenario'}, {'id': 'extra'}]}
        parent = c.compile_provenance({'basis': 'illustrative', 'assumptionRefs': ['scenario']}, evidence, c.Location())
        child = c.compile_provenance({'basis': 'illustrative', 'assumptionRefs': ['extra']}, evidence, c.Location(), parent)
        self.assertEqual(child.assumption_refs, ('scenario', 'extra'))
        joined = c.combine_lineage(parent, child, parent, step='model:add')
        self.assertEqual(joined.bases, ('illustrative',))
        self.assertEqual(joined.assumption_refs, ('scenario', 'extra'))
        self.assertTrue(joined.derived)
        for raw in [{'basis': 'measured'}, {'basis': 'assumed'}, {'basis': 'derived'}, {'basis': 'measured', 'sourceRefs': ['source']}]:
            with self.subTest(raw=raw), self.assertRaises(c.SceneValidationError):
                c.compile_provenance(raw, evidence, c.Location(), parent)


class DecisionTests(unittest.TestCase):
    def test_formatting_is_exact_and_narration_never_truncates_mandatory_text(self):
        q = c.Quantity('rate', 'ratio', 'percent', (0, 0, 0), (('percent', 1),), None, '%')
        self.assertEqual(c.format_value(D('12.345'), q, 2), '12.35%')
        self.assertEqual(c.format_value(D('-12.345'), q, 2), '−12.35%')
        self.assertEqual(c.format_value(D('2'), q, 0, delta=True), '+2 pp')
        self.assertEqual(c.fit_narration(['a' * 160], ['optional']), 'a' * 160)
        with self.assertRaises(c.SceneValidationError) as caught:
            c.fit_narration(['a' * 161], [])
        self.assertEqual(caught.exception.code, 'narration_length')

    def test_audit_nearest_witness_and_missing_outcome(self):
        lineage = c.Lineage(bases=('illustrative',), assumption_refs=('synthetic',))
        decision = c.DecisionSpec('gate', 'output:result', 'gte', c.TypedValue(D('3'), 'value', lineage), 'Go', 'Run', 'Hold', 'Wait')
        domains = (c.ControlDomain('a', ('low', 'high')), c.ControlDomain('b', ('low', 'high')))
        def evaluator(state):
            return {'result': c.TypedValue(D((3 if state['a'] == 'high' else 0) + (2 if state['b'] == 'high' else 0)), 'value', lineage)}
        audit = c.audit_contract(domains, evaluator, decision, ())
        self.assertEqual(audit.accepted_state_count, 4)
        self.assertEqual(dict(audit.witnesses['notMet'].state), {'a': 'low', 'b': 'high'})
        self.assertEqual(dict(audit.witnesses['met'].state), {'a': 'high', 'b': 'low'})
        self.assertEqual(audit.witnesses['exact'].distance, D('0'))
        far = c.DecisionSpec('gate', 'output:result', 'gt', c.TypedValue(D('9'), 'value', lineage), 'Go', 'Run', 'Hold', 'Wait')
        self.assertEqual(c.audit_contract(domains, evaluator, far, ()).missing_outcomes, ({'outcome': 'met', 'reason': 'unreachable_within_declared_domain'},))

    def test_threshold_uses_exact_value_and_all_four_operators(self):
        line = c.Lineage()
        for op, expected in [('gt', False), ('gte', True), ('lt', False), ('lte', True)]:
            spec = c.DecisionSpec('gate', 'output:x', op, c.TypedValue(D('2'), 'q', line), 'Yes', 'Do', 'No', 'Wait')
            self.assertEqual(c.evaluate_decision(spec, {'x': c.TypedValue(D('2'), 'q', line)}, {}).outcome, 'met' if expected else 'notMet')


if __name__ == '__main__':
    unittest.main()
