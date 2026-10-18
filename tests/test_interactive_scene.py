"""Compiler fixtures use original, hand-calculated synthetic values."""
import copy
import json
import sys
import tempfile
import os
import subprocess
import unittest
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import interactive_scene as s
import interactive_contract as c

PROV = {'basis': 'illustrative', 'assumptionRefs': ['synthetic']}


def fixture():
    return {
        'version': 1, 'type': 'slider_model', 'purpose': 'Test the capacity threshold',
        'decisionJob': 'decision', 'interactionRationale': 'Find the input required to meet the threshold',
        'initialState': {'x': 1}, 'printState': {'x': 1},
        'quantities': {'value': {'dimension': 'scalar', 'unit': 'one', 'display': 'units'}},
        'assumptions': [{'id': 'synthetic', 'label': 'Synthetic model', 'value': 'Illustrative only'}],
        'controls': [{'id': 'x', 'kind': 'range', 'label': 'Input', 'min': 0, 'max': 2, 'step': 1, 'quantity': 'value', 'provenance': copy.deepcopy(PROV)}],
        'model': {'kind': 'linear', 'intercept': {'value': 3, 'quantity': 'value'}, 'terms': {'x': {'coefficient': 5, 'inputQuantity': 'value', 'outputQuantity': 'value'}}, 'output': 'result', 'outputQuantity': 'value', 'format': 'number', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)},
        'reporting': {'primaryOutput': 'result'},
        'decisionContract': {'id': 'gate', 'metric': {'ref': 'output:result'}, 'operator': 'gte', 'threshold': {'value': 8, 'quantity': 'value', 'provenance': copy.deepcopy(PROV)}, 'whenMet': {'status': 'Proceed', 'recommendation': 'Run'}, 'whenNotMet': {'status': 'Hold', 'recommendation': 'Wait'}},
        'view': {'component': 'bar_compare', 'quantity': 'value', 'domain': [0, 20], 'baseline': 0, 'items': [{'id': 'result', 'label': 'Result', 'value': {'ref': 'output:result'}, 'emphasis': True}]},
    }


def program(raw):
    scene = s.validate_scene_shape(s.LocatedDocument(raw, c.Location('scene.json')))
    return s.compile_model(scene, c.compile_quantities(raw.get('quantities', {})), raw)


def fallback():
    return {'pattern': 'gap', 'headline': 'Capacity meets the gate at one input', 'source': 'Illustrative',
            'quantity': 'value', 'unit': 'units', 'value_domain': [0, 20], 'baseline': 0,
            'items': [{'item_id': 'result', 'label': 'Result', 'value': 8, 'emphasis': True, 'value_text': '8 units'}],
            'interactive_result': {'quantity': 'value', 'value': 8, 'decision_status': 'Proceed', 'recommendation': 'Run', 'operator': 'gte', 'threshold': 8},
            'annotation': 'result 8 units; Proceed; threshold ≥ 8 units; Run'}


def compile_fixture(raw=None, static=None):
    return s.compile_scene(s.LocatedDocument(raw or fixture(), c.Location('scene.json')), fallback_spec=static or fallback(), fallback_path='static.json', slide_id='capacity', slide_ids={'capacity', 'next'}, lang='en')


class LoadingShapeTests(unittest.TestCase):
    def test_all_reference_container_failures_are_located(self):
        lookup = {'kind': 'lookup', 'input': 'x', 'entries': [{'input': i, 'output': {'value': i, 'quantity': 'value'}} for i in range(3)], 'output': 'result', 'outputQuantity': 'value', 'format': 'number', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)}
        piecewise = {'kind': 'piecewise', 'input': 'x', 'segments': [{'kind': 'endpoints', 'min': 0, 'max': 2, 'inputQuantity': 'value', 'start': {'value': 0, 'quantity': 'value'}, 'end': {'value': 2, 'quantity': 'value'}}], 'output': 'result', 'outputQuantity': 'value', 'format': 'number', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)}
        graph = {'kind': 'operation_graph', 'nodes': [{'id': 'input', 'op': 'input', 'control': 'x', 'quantity': 'value'}], 'outputs': {'result': {'node': 'input', 'quantity': 'value', 'format': 'number', 'round': 0}}}
        graph_add = copy.deepcopy(graph)
        graph_add['nodes'].append({'id': 'sum', 'op': 'add', 'left': 'input', 'right': 'input', 'quantity': 'value'})
        graph_add['outputs']['result']['node'] = 'sum'
        graph_min = copy.deepcopy(graph_add)
        graph_min['nodes'][1] = {'id': 'min', 'op': 'min', 'inputs': ['input', 'missing'], 'quantity': 'value'}
        cases = [(lookup, ('input',)), (piecewise, ('input',)), (graph, ('nodes', 0, 'control')), (graph, ('outputs', 'result', 'node')), (graph_add, ('nodes', 1, 'left')), (graph_min, ('nodes', 1, 'inputs', 1))]
        for model, path in cases:
            for invalid in ([], {}, None, True, 'missing'):
                raw = fixture(); raw['model'] = copy.deepcopy(model); cursor = raw['model']
                for key in path[:-1]: cursor = cursor[key]
                cursor[path[-1]] = invalid
                with self.subTest(path=path, invalid=invalid), self.assertRaises(c.SceneValidationError) as caught:
                    program(raw)
                self.assertEqual(caught.exception.location.file, 'scene.json')
                self.assertEqual(caught.exception.location.pointer, '/model/' + '/'.join(map(str, path)))

    def test_malformed_container_types_produce_located_contract_errors(self):
        for path in [('type',), ('quantities', 'value', 'dimension'), ('decisionContract', 'metric', 'ref'), ('model', 'output'), ('model', 'outputQuantity')]:
            for invalid in ([], {}, None, True):
                raw = fixture(); cursor = raw
                for key in path[:-1]: cursor = cursor[key]
                cursor[path[-1]] = invalid
                with self.subTest(path=path, invalid=invalid), self.assertRaises(c.SceneValidationError): compile_fixture(raw)
        raw = fixture(); raw['demo'] = [{'stepKey': 'go', 'action': 'goto', 'slideId': []}]
        with self.assertRaises(c.SceneValidationError): compile_fixture(raw)

    def test_caps_and_nested_unknown_fields_fail_before_evaluation(self):
        mutations = [
            lambda r: r.update(version=True),
            lambda r: r.update(purpose='x' * 501),
            lambda r: r['controls'][0].update(label='x' * 41),
            lambda r: r['controls'][0].update(max=10001),
            lambda r: r.update(assumptions=r['assumptions'] * 21),
            lambda r: r.update(demo=[{'stepKey': 'x', 'action': 'wait', 'ms': 1}] * 81),
            lambda r: r['model']['intercept'].update(provenance={'basis': 'illustrative', 'assumptionRefs': ['synthetic'], 'derived': True}),
            lambda r: r['decisionContract'].update(operator='eq'),
            lambda r: r['view']['items'][0].update(emphasis=1),
            lambda r: r['view']['items'][0].update(value={'value': 8, 'quantity': 'missing', 'provenance': copy.deepcopy(PROV)}),
            lambda r: r['model']['terms']['x'].update(inputQuantity='missing'),
            lambda r: r['reporting'].update(primaryOutput='recommendation'),
        ]
        for mutate in mutations:
            raw = fixture(); mutate(raw)
            with self.subTest(raw=raw), self.assertRaises(c.SceneValidationError): compile_fixture(raw)

    def test_documented_schema_matches_structural_fixtures(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('Optional schema cross-check dependency; production compiler uses only stdlib')
        schema = json.loads((Path(__file__).resolve().parents[1] / 'schemas/interactive-scene-v1.schema.json').read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        self.assertFalse(list(validator.iter_errors(fixture())))
        for mutate in [lambda x: x.update(extra=True), lambda x: x['controls'][0].update(extra=1), lambda x: x['model']['intercept'].update(value='3'), lambda x: x['view']['items'][0].update(value={'ref': 'output:result', 'value': 3})]:
            raw = fixture(); mutate(raw)
            self.assertTrue(list(validator.iter_errors(raw)))
            with self.assertRaises(c.SceneValidationError): compile_fixture(raw)

    def test_schema_and_compiler_reserve_javascript_object_keys(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('Optional schema cross-check dependency')
        schema = json.loads((Path(__file__).resolve().parents[1] / 'schemas/interactive-scene-v1.schema.json').read_text())
        validator = Draft202012Validator(schema)
        for invalid in ('__proto__', 'prototype', 'constructor'):
            for path in [('controls', 0, 'id'), ('assumptions', 0, 'id'), ('decisionContract', 'id'), ('view', 'items', 0, 'id'), ('model', 'output')]:
                raw = fixture(); cursor = raw
                for key in path[:-1]: cursor = cursor[key]
                cursor[path[-1]] = invalid
                with self.subTest(path=path, invalid=invalid):
                    self.assertTrue(list(validator.iter_errors(raw)))
                    with self.assertRaises(c.SceneValidationError): compile_fixture(raw)

    def test_storage_unit_schema_matches_compiler_in_every_quantity_alternative(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('Optional schema cross-check dependency')
        schema = json.loads((Path(__file__).resolve().parents[1] / 'schemas/interactive-scene-v1.schema.json').read_text())
        validator = Draft202012Validator(schema)
        cases = [(unit, False) for unit in ('__proto__', 'prototype', 'constructor', 'spaces bad', '0item', '_item', 'item-name', 'item.name', 'item/name', '', 'A' * 65, 'Unit\n', '単位')]
        cases += [(unit, True) for unit in ('item', 'Item_2', 'A', 'A' * 64, 'Constructor')]
        for unit, accepted in cases:
            for dimension in ('scalar', 'currency', 'derived'):
                raw = fixture()
                quantity = {'dimension': dimension, 'unit': unit, 'display': 'test'}
                if dimension == 'currency': quantity['currency'] = 'USD'
                if dimension == 'derived': quantity.update(exponents={'currency': 0, 'time': 0, 'count': 0}, unitFactors={})
                raw['quantities']['test'] = quantity
                with self.subTest(unit=unit, dimension=dimension):
                    if accepted: c.compile_quantities(raw['quantities'])
                    else:
                        with self.assertRaises(c.SceneValidationError): c.compile_quantities(raw['quantities'])
                    self.assertEqual(not list(validator.iter_errors(raw)), accepted)
            raw = fixture()
            raw['quantities']['base'] = {'dimension': 'count', 'unit': unit if accepted else 'item', 'display': 'items'}
            raw['quantities']['test'] = {'dimension': 'derived', 'unit': 'derivedUnit', 'display': 'items', 'exponents': {'currency': 0, 'time': 0, 'count': 1}, 'unitFactors': {unit: 1}}
            with self.subTest(unit=unit, dimension='factor-key'):
                if accepted: c.compile_quantities(raw['quantities'])
                else:
                    with self.assertRaises(c.SceneValidationError): c.compile_quantities(raw['quantities'])
                self.assertEqual(not list(validator.iter_errors(raw)), accepted)

    def test_loader_exact_numbers_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scene.json'
            path.write_text('{"x":1.20}', encoding='utf-8')
            self.assertEqual(s.load_scene(path).data['x'].as_tuple().exponent, -2)
            for text in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":"\\ud800"}', '[' * 80 + '0' + ']' * 80]:
                path.write_text(text, encoding='utf-8')
                with self.subTest(text=text[:20]), self.assertRaises(c.SceneValidationError):
                    s.load_scene(path)

    def test_closed_shape_and_strict_initial_state(self):
        self.assertEqual(s.validate_scene_shape(s.LocatedDocument(fixture(), c.Location())).data['type'], 'slider_model')
        for mutate in [lambda x: x.update(extra=True), lambda x: x['controls'][0].update(extra=True), lambda x: x['initialState'].update(x=3), lambda x: x['printState'].update(x=0), lambda x: x['controls'][0].update(step=D('.3'))]:
            raw = fixture(); mutate(raw)
            with self.assertRaises(c.SceneValidationError):
                s.validate_scene_shape(s.LocatedDocument(raw, c.Location('bad.json')))


class CompilationTests(unittest.TestCase):
    def test_evidence_badge_joins_all_leaf_and_state_bases_conservatively(self):
        for basis, expected in [('measured', 'estimated'), ('assumed', 'assumed'), ('illustrative', 'illustrative')]:
            raw = fixture()
            raw['sources'] = [{'id': 'reference', 'label': 'Synthetic source', 'detail': 'Test only'}]
            raw['controls'][0]['provenance'] = {'basis': 'measured', 'sourceRefs': ['reference']}
            raw['model']['modelProvenance'] = {'basis': 'estimated', 'assumptionRefs': ['synthetic']}
            raw['decisionContract']['threshold']['provenance'] = {'basis': basis, 'sourceRefs': ['reference']} if basis == 'measured' else {'basis': basis, 'assumptionRefs': ['synthetic']}
            self.assertEqual(s.serialize_compiled_scene(compile_fixture(raw).compiled)['evidence']['badge'], expected)

    def test_closed_narration_program_reproduces_exact_direct_reset_and_restore(self):
        compiled = s.serialize_compiled_scene(compile_fixture().compiled)
        narration = compiled['narration']
        self.assertEqual(set(narration['program']), {'kind', 'controls', 'outputs', 'transitions'})
        self.assertEqual(narration['program']['kind'], 'numeric_delta_v1')
        for locale in ('en', 'ja'):
            plan = {**narration, 'locale': locale}
            for value, result, status, expected in [(2, 13, 'Proceed', 'Input +1 units; result +5 units'), (0, 3, 'Hold', 'Input −1 units; result −5 units; Proceed → Hold')]:
                evaluation = {'outputs': {'result': {'value': str(result)}, 'decisionStatus': {'value': status}}}
                self.assertEqual(s.render_narration(plan, {'x': str(value)}, evaluation, control='x'), expected)
                self.assertEqual(s.render_narration(plan, {'x': D(value)}, evaluation, event='restore'), expected)
            reset = 'Reset to baseline: result 8 units; Proceed' if locale == 'en' else '初期値に戻しました: result 8 units; Proceed'
            self.assertEqual(s.render_narration(plan, {}, {}, event='reset'), reset)
        self.assertLess(len(json.dumps(narration)), 6000)

    def test_direct_narration_requires_trigger_even_at_baseline(self):
        compiled = s.serialize_compiled_scene(compile_fixture().compiled)
        for locale, initial in [('en', 'Baseline: result 8 units; Proceed'), ('ja', '初期値: result 8 units; Proceed')]:
            plan = {**compiled['narration'], 'locale': locale}
            for state in ({'x': '1'}, {'x': '2'}):
                for control in (None, 'missing'):
                    with self.subTest(locale=locale, state=state, control=control):
                        with self.assertRaisesRegex(ValueError, 'requires a known control'):
                            s.render_narration(plan, state, compiled['initialEvaluation'], control=control)
            self.assertEqual(s.render_narration(plan, {'x': '1'}, compiled['initialEvaluation'], control='x'), initial)

    def test_narration_multicontrol_restore_retains_classification_and_threshold(self):
        raw = fixture()
        raw.update(type='score_model', controls=[{'id': name, 'kind': 'toggle', 'label': name, 'options': [{'value': 'low', 'label': 'Low'}, {'value': 'high', 'label': 'High'}]} for name in ('a', 'b')], initialState={'a': 'low', 'b': 'low'}, printState={'a': 'low', 'b': 'low'})
        raw['quantities']['points'] = {'dimension': 'score', 'unit': 'point', 'display': 'points'}
        raw['model'] = {'kind': 'score_sum', 'quantity': 'points', 'contributions': [{'control': name, 'values': [{'input': 'low', 'points': 0}, {'input': 'high', 'points': points}]} for name, points in [('a', 3), ('b', 2)]], 'bands': [{'id': 'early', 'min': 0, 'max': 3, 'label': 'Early'}, {'id': 'ready', 'min': 3, 'max': 5, 'label': 'Ready'}], 'format': 'score', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)}
        raw['reporting'] = {'primaryOutput': 'score'}
        raw['decisionContract']['metric']['ref'] = 'output:score'
        raw['decisionContract']['threshold'].update(value=3, quantity='points')
        raw['view'] = {'component': 'recommendation_panel', 'score': {'ref': 'output:score'}}
        static = {'pattern': 'closing', 'headline': 'Baseline', 'interactive_result': {'quantity': 'points', 'value': 0, 'classification': 'Early', 'decision_status': 'Hold', 'recommendation': 'Wait', 'operator': 'gte', 'threshold': 3}, 'takeaways': ['score 0 points', 'Early', 'Hold; threshold ≥ 3 points'], 'next_steps': [{'action': 'Wait'}]}
        static['annotation'] = ''
        narration = s.serialize_compiled_scene(compile_fixture(raw, static).compiled)['narration']
        evaluation = {'outputs': {'score': {'value': '5'}, 'classification': {'value': 'Ready'}, 'decisionStatus': {'value': 'Proceed'}}}
        for locale, prefix in [('en', 'Scenario restored: 2 inputs changed'), ('ja', 'シナリオを復元：入力2件を変更')]:
            plan = {**narration, 'locale': locale}
            self.assertEqual(s.render_narration(plan, {'a': 'high', 'b': 'high'}, evaluation, event='restore'), prefix + '; score +5 points; Early → Ready; Hold → Proceed')
            self.assertEqual(s.render_narration(plan, {'a': 'high', 'b': 'high'}, evaluation, control='a'), 'a: High; score +5 points; Early → Ready; Hold → Proceed')
            from unittest.mock import patch
            with patch.dict(c.NARRATION_TEXT[locale], {'restore': 'Uncompiled text'}):
                self.assertEqual(s.render_narration(plan, {'a': 'high', 'b': 'high'}, evaluation, event='restore'), prefix + '; score +5 points; Early → Ready; Hold → Proceed')

    def test_state_narration_counts_semantic_changes_not_distinct_provenance(self):
        raw = {k: v for k, v in fixture().items() if k in s.COMMON or k in ('quantities', 'assumptions')}
        raw.update(type='state_toggle', initialState={'scenario': 'base'}, printState={'scenario': 'base'}, controls=[{'id': 'scenario', 'kind': 'segmented', 'label': 'Scenario', 'options': [{'value': 'base', 'label': 'Base'}, {'value': 'other', 'label': 'Other'}]}])
        view = {'component': 'ranked_list', 'items': [{'id': 'a', 'label': 'A', 'rank': 1}, {'id': 'b', 'label': 'B', 'rank': 2}]}
        raw['states'] = [{'id': name, 'provenance': copy.deepcopy(PROV), 'view': copy.deepcopy(view)} for name in ('base', 'other')]
        raw['states'][0]['provenance']['basis'] = 'assumed'
        raw['states'][1]['view']['items'][0].update(rank=2, emphasis=True)
        raw['states'][1]['view']['items'][1].update(rank=1, removed=True)
        static = {'pattern': 'bullet_list', 'headline': 'Order', 'bullets': [{'item_id': name, 'text': name.upper(), 'rank': rank, 'removed': False, 'emphasis': False} for name, rank in [('a', 1), ('b', 2)]]}
        compiled = s.serialize_compiled_scene(compile_fixture(raw, static).compiled)
        self.assertEqual(compiled['evidence']['badge'], 'illustrative')
        self.assertEqual(set(compiled['narration']['program']), {'kind', 'controls', 'baselineView'})
        evaluation = {'view': compiled['states'][1]['view']}
        for locale, expected in [('en', 'Scenario: Other; 2 moved, 1 changed, 1 removed'), ('ja', 'Scenario：Other；移動2件、変更1件、除外1件')]:
            plan = {**compiled['narration'], 'locale': locale}
            self.assertEqual(s.render_narration(plan, {'scenario': 'other'}, evaluation), expected)
            self.assertEqual(s.render_narration(plan, {'scenario': 'other'}, evaluation, event='restore'), expected)
        # Different leaf/step ancestry does not count as a changed metric.
        plan = copy.deepcopy(compiled['narration'])
        plan['program']['baselineView'][0]['metric'] = '2'
        baseline = copy.deepcopy(compiled['initialEvaluation'])
        baseline['view']['items'][0]['metric'] = {'value': '2', 'lineage': {'leaves': ['other-leaf']}}
        self.assertEqual(s.render_narration(plan, {'scenario': 'other'}, baseline), 'Scenario: Other; 0 moved, 0 changed, 0 removed')

    def test_state_toggle_serializes_resolved_text_for_every_state_and_reuses_selected_view(self):
        raw = {k: v for k, v in fixture().items() if k in s.COMMON or k in ('quantities', 'assumptions')}
        raw.update(
            type='state_toggle',
            initialState={'scenario': 'base'},
            printState={'scenario': 'base'},
            controls=[{
                'id': 'scenario',
                'kind': 'segmented',
                'label': 'Scenario',
                'options': [
                    {'value': 'base', 'label': 'Base'},
                    {'value': 'other', 'label': 'Other'},
                ],
            }],
        )
        raw['states'] = [
            {
                'id': 'base',
                'provenance': copy.deepcopy(PROV),
                'view': {
                    'component': 'bar_compare',
                    'quantity': 'value',
                    'domain': [0, 10],
                    'baseline': 0,
                    'items': [{
                        'id': 'capacity',
                        'label': 'Capacity',
                        'value': {'value': D('2'), 'quantity': 'value', 'provenance': copy.deepcopy(PROV)},
                    }],
                },
            },
            {
                'id': 'other',
                'provenance': copy.deepcopy(PROV),
                'view': {
                    'component': 'bar_compare',
                    'quantity': 'value',
                    'domain': [0, 10],
                    'baseline': 0,
                    'items': [{
                        'id': 'capacity',
                        'label': 'Capacity',
                        'value': {'value': D('3.0'), 'quantity': 'value', 'provenance': copy.deepcopy(PROV)},
                    }],
                },
            },
        ]
        static = {
            'pattern': 'gap',
            'headline': 'Capacity',
            'quantity': 'value',
            'unit': 'units',
            'value_domain': [0, 10],
            'baseline': 0,
            'items': [{
                'item_id': 'capacity',
                'label': 'Capacity',
                'value': 2,
                'value_text': '2 units',
                'emphasis': False,
                'removed': False,
            }],
        }

        compiled = s.serialize_compiled_scene(compile_fixture(raw, static).compiled)

        self.assertEqual(compiled['states'][0]['view']['items'][0]['valueText'], '2 units')
        self.assertEqual(compiled['states'][1]['view']['items'][0]['valueText'], '3.0 units')
        self.assertEqual(compiled['initialEvaluation']['view'], compiled['states'][0]['view'])

    def test_state_narration_reports_both_removal_directions_and_real_no_change(self):
        cases = [
            (False, True, 'Scenario: Other; 0 moved, 0 changed, 1 removed', 'Scenario：Other；移動0件、変更0件、除外1件'),
            (True, False, 'Scenario: Other; 0 moved, 1 changed, 0 removed', 'Scenario：Other；移動0件、変更1件、除外0件'),
            (False, False, 'Scenario: Other; 0 moved, 0 changed, 0 removed', 'Scenario：Other；移動0件、変更0件、除外0件'),
            (True, True, 'Scenario: Other; 0 moved, 0 changed, 0 removed', 'Scenario：Other；移動0件、変更0件、除外0件'),
        ]
        for before, after, en, ja in cases:
            raw = {k: v for k, v in fixture().items() if k in s.COMMON or k == 'assumptions'}
            raw.update(type='state_toggle', initialState={'scenario': 'base'}, printState={'scenario': 'base'}, controls=[{'id': 'scenario', 'kind': 'segmented', 'label': 'Scenario', 'options': [{'value': 'base', 'label': 'Base'}, {'value': 'other', 'label': 'Other'}]}])
            raw['states'] = [{'id': name, 'provenance': copy.deepcopy(PROV), 'view': {'component': 'ranked_list', 'items': [{'id': 'a', 'label': 'A', 'rank': 1, 'removed': removed}]}} for name, removed in [('base', before), ('other', after)]]
            bullet = {'item_id': 'a', 'text': 'A', 'rank': 1, 'removed': before, 'emphasis': False}
            if before: bullet['sub'] = ['Removed']
            result = compile_fixture(raw, {'pattern': 'bullet_list', 'headline': 'State', 'bullets': [bullet]})
            self.assertEqual(result.audit.accepted_state_count, 2)
            for compiled in (result.compiled, s.serialize_compiled_scene(result.compiled)):
                for locale, expected in [('en', en), ('ja', ja)]:
                    plan = {**compiled['narration'], 'locale': locale}
                    for event in ('direct', 'restore'):
                        with self.subTest(before=before, after=after, locale=locale, event=event):
                            self.assertEqual(s.render_narration(plan, {'scenario': 'other'}, {'view': compiled['states'][1]['view']}, event=event), expected)

    def test_narration_drops_optional_outputs_in_priority_order_and_stays_bounded(self):
        plan = s.serialize_compiled_scene(compile_fixture().compiled)['narration']
        atom = plan['program']['outputs'][0]
        plan['program']['outputs'] += [{**atom, 'id': 'first', 'label': 'F' * 40}, {**atom, 'id': 'last', 'label': 'L' * 40}]
        plan['program']['controls'][0]['label'] = 'I' * 40
        evaluation = {'outputs': {name: {'value': '3'} for name in ('result', 'first', 'last')}}
        evaluation['outputs']['decisionStatus'] = {'value': 'Hold'}
        text = s.render_narration(plan, {'x': '0'}, evaluation, control='x')
        self.assertIn('F' * 40, text)
        self.assertNotIn('L' * 40, text)
        self.assertTrue(text.endswith('Proceed → Hold'))
        self.assertLessEqual(len(text), 160)
        plan['program']['controls'][0]['label'] = 'I' * 161
        with self.assertRaises(c.SceneValidationError) as caught:
            s.render_narration(plan, {'x': '0'}, evaluation, control='x')
        self.assertEqual(caught.exception.code, 'narration_length')
        raw, static = fixture(), fallback()
        raw['controls'][0]['max'] = 1000
        raw['view']['domain'] = static['value_domain'] = [0, 6000]
        larger = s.serialize_compiled_scene(compile_fixture(raw, static).compiled)['narration']
        smaller = s.serialize_compiled_scene(compile_fixture().compiled)['narration']
        self.assertEqual(larger['program'], smaller['program'])
        self.assertLess(abs(len(json.dumps(larger)) - len(json.dumps(smaller))), 10)

    def test_compiler_facade_is_small_and_private_modules_are_acyclic(self):
        import ast
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        self.assertLessEqual(len((scripts / 'interactive_scene.py').read_text().splitlines()), 500)
        modules = {path.stem: path for path in scripts.glob('_interactive_*.py')}
        self.assertGreaterEqual(len(modules), 5)
        edges = {}
        for name, path in modules.items():
            self.assertLessEqual(len(path.read_text().splitlines()), 500, name)
            edges[name] = {node.module for node in ast.walk(ast.parse(path.read_text())) if isinstance(node, ast.ImportFrom) and node.module in modules}
        def visit(name, stack):
            self.assertNotIn(name, stack, 'private module import cycle')
            for dependency in edges[name]: visit(dependency, stack + (name,))
        for name in modules: visit(name, ())

    def test_package_and_sibling_facades_work_from_unrelated_cwd(self):
        root = Path(__file__).resolve().parents[1]
        payload = json.dumps({'scene': fixture(), 'fallback': fallback()})
        for package, cwd in [(True, root), (True, tempfile.gettempdir()), (False, tempfile.gettempdir())]:
            prefix = 'scripts.' if package else ''
            code = f'''import json, sys
from {prefix}interactive_scene import LocatedDocument, compile_scene, serialize_compiled_scene, load_scene, validate_scene_shape, compile_model, evaluate_model, resolve_view, compile_registries, project_fallback, validate_fallback
from {prefix}interactive_contract import Location
p=json.load(sys.stdin)
r=compile_scene(LocatedDocument(p['scene'], Location('scene.json')), fallback_spec=p['fallback'], fallback_path='static.json', slide_id='capacity', slide_ids={{'capacity'}}, lang='en')
assert serialize_compiled_scene(r.compiled)['initialEvaluation']['outputs']['result']['value']=='8'
'''
            result = subprocess.run([sys.executable, '-B', '-c', code], input=payload, text=True, capture_output=True, cwd=cwd, env={**os.environ, 'PYTHONPATH': str(root if package else root / 'scripts')})
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_actual_renderer_chrome_is_retained(self):
        static = fallback(); static.update(footnotes=['A qualified note'], page_number=7, classification='Internal')
        invariants = compile_fixture(static=static).compiled['invariants']
        self.assertEqual({k: invariants[k] for k in ('footnotes', 'page_number', 'classification')}, {'footnotes': ['A qualified note'], 'page_number': 7, 'classification': 'Internal'})

    def test_safe_source_policy_is_shared_with_target_registration(self):
        valid = ['https://example.com/source', 'mailto:reader+deck@example.com']
        invalid = ['mailto:a@example.com?subject=Hi', 'mailto:a@example.com#body', 'mailto:a@example.com,b@example.com', 'mailto:a@example.com;b@example.com', 'mailto:a@example.com%0d%0aBcc:b@example.com', 'mailto:a%20b@example.com', 'mailto:@example.com', 'mailto:a@', 'https://user:pass@example.com', 'https://example.com/%00', 'https://example.com/%7f', 'https://example.com/\\x', 'https://example.com/ white', 'https://example.com/%0A', 'https://@example.com', 'https://example.com/?', 'https://example.com/#', 'mailto:a@example.com?', 'mailto:a@example.com#']
        for url in valid: self.assertTrue(s.safe_source_url(url), url)
        for url in invalid: self.assertFalse(s.safe_source_url(url), url)
        for url in valid + invalid:
            raw = fixture(); raw['sources'] = [{'id': 'reference', 'label': 'Test link', 'detail': 'Synthetic source', 'url': url}]
            compiled = compile_fixture(raw).compiled
            self.assertEqual(compiled['evidence']['sources'][0]['linked'], url in valid)
            self.assertEqual('source:reference' in compiled['targets'], url in valid)

    def test_decision_wire_has_exact_approved_shape_and_validated_provenance(self):
        raw = fixture()
        raw['decisionContract']['threshold']['provenance']['normalization'] = {'note': 'Normalized upstream', 'fromUnit': 'other', 'toUnit': 'one'}
        decision = s.serialize_compiled_scene(compile_fixture(raw).compiled)['decisionContract']
        self.assertEqual(set(decision), {'id', 'metric', 'operator', 'threshold', 'whenMet', 'whenNotMet'})
        self.assertEqual(decision['threshold'], {'value': '8', 'quantity': 'value', 'provenance': {'basis': 'illustrative', 'assumptionRefs': ['synthetic'], 'normalization': {'note': 'Normalized upstream', 'fromUnit': 'other', 'toUnit': 'one'}}})

    def test_disclosure_panel_and_accordion_compile_all_restorable_states(self):
        for kind in ('drilldown', 'accordion'):
            raw = {k: v for k, v in fixture().items() if k in s.COMMON}
            panels = [{'id': name, 'label': name.title(), 'heading': name.title(), 'body': name + ' body'} for name in ('one', 'two')]
            raw.update(type=kind, initialState={'panel': None}, printState={'panel': None}, fallbackSummary={'field': 'headline', 'text': 'Proof'})
            if kind == 'drilldown': raw.update(panels=panels, parentSummary='Parent', returnLabel='Back')
            else: raw.update(items=panels, allowNone=True)
            raw['demo'] = [{'stepKey': 'open', 'action': 'openPanel', 'panel': 'one'}, {'stepKey': 'close', 'action': 'closePanel', 'panel': 'one'}]
            result = compile_fixture(raw, {'pattern': 'bullet_list', 'headline': 'Proof', 'bullets': [{'text': 'Summary'}]})
            self.assertEqual(result.audit.accepted_state_count, 3)
            self.assertIn({'name': 'panel:two', 'state': {'panel': 'two'}}, result.audit_states)
            self.assertEqual(
                [panel['sourceRefs'] for panel in result.compiled['states']['panels']],
                [[], []],
            )

    def test_static_boolean_metadata_is_not_numeric_coercion(self):
        static = fallback(); static['items'][0]['emphasis'] = 1
        with self.assertRaises(c.SceneValidationError): compile_fixture(static=static)

    def test_presentation_domains_do_not_change_model_rounding_scale(self):
        raw = fixture()
        raw['controls'][0].update(min=0, max=1, step=D('.1'))
        raw['model']['intercept']['value'] = 0
        raw['model']['terms']['x']['coefficient'] = D('.5')
        raw['view']['domain'] = [0, D('20.123456')]
        p = program(raw)
        self.assertEqual(p.scale, 1)
        self.assertEqual(s.evaluate_model(p, {'x': D('.5')})['result'].value, D('.3'))

    def test_fallback_may_not_truncate_verified_item_labels(self):
        raw = fixture(); raw['view']['items'][0]['label'] = 'Long label ' * 30
        static = fallback(); static['items'][0]['label'] = raw['view']['items'][0]['label']
        with self.assertRaises(c.SceneValidationError) as caught: compile_fixture(raw, static)
        self.assertEqual(caught.exception.location.file, 'static.json')

    def test_author_atlas_retains_witnesses_and_source_paths_are_not_audience_copy(self):
        raw = fixture()
        raw['demo'] = [
            {'stepKey': 'show', 'action': 'openEvidence'},
            {'stepKey': 'hide', 'action': 'closeEvidence'},
        ]
        result = compile_fixture(raw)
        names = {entry['name'] for entry in result.audit_states}
        self.assertTrue({'initial', 'print', 'range:x:min', 'range:x:max', 'decision:met', 'decision:notMet', 'decision:exact'} <= names)
        maximum = result.audit_evaluations['range:x:max']
        self.assertEqual(maximum['inputs'], {'x': '2'})
        self.assertEqual(maximum['outputs'], {'result': '13'})
        self.assertEqual(maximum['outcome'], 'met')
        self.assertEqual(maximum['viewMode'], 'live')
        close_evidence = next(entry for entry in result.audit_states if entry['name'] == 'step:hide')
        self.assertEqual(close_evidence['setup'], [
            {'action': 'openEvidence'},
            {'action': 'closeEvidence'},
        ])
        audience = json.dumps(s.serialize_compiled_scene(result.compiled))
        self.assertNotIn('scene.json', audience)
        self.assertNotIn('/model/', audience)
        self.assertTrue(result.compiled['evidence']['formulas'])

    def test_demo_reachability_rejects_inert_evidence_and_post_goto_actions(self):
        valid_sequences = [
            [
                {'stepKey': 'show', 'action': 'openEvidence'},
                {'stepKey': 'hide', 'action': 'closeEvidence'},
                {'stepKey': 'change', 'action': 'set', 'control': 'x', 'value': 2},
            ],
            [
                {'stepKey': 'show', 'action': 'openEvidence'},
                {'stepKey': 'pause', 'action': 'wait', 'ms': 1},
                {'stepKey': 'hide', 'action': 'closeEvidence'},
            ],
            [{'stepKey': 'next', 'action': 'goto', 'slideId': 'next'}],
        ]
        for demo in valid_sequences:
            raw = fixture()
            raw['demo'] = demo
            with self.subTest(valid=demo):
                compile_fixture(raw)

        invalid_sequences = [
            [
                {'stepKey': 'next', 'action': 'goto', 'slideId': 'next'},
                {'stepKey': 'change', 'action': 'set', 'control': 'x', 'value': 2},
            ],
            [
                {'stepKey': 'show', 'action': 'openEvidence'},
                {'stepKey': 'change', 'action': 'set', 'control': 'x', 'value': 2},
            ],
            [
                {'stepKey': 'show', 'action': 'openEvidence'},
                {'stepKey': 'show-again', 'action': 'openEvidence'},
            ],
            [{'stepKey': 'hide', 'action': 'closeEvidence'}],
            [
                {'stepKey': 'show', 'action': 'openEvidence'},
                {'stepKey': 'next', 'action': 'goto', 'slideId': 'next'},
            ],
        ]
        for demo in invalid_sequences:
            raw = fixture()
            raw['demo'] = demo
            with self.subTest(invalid=demo):
                with self.assertRaises(c.SceneValidationError) as caught:
                    compile_fixture(raw)
                self.assertEqual(caught.exception.code, 'demo_target')

    def test_evidence_only_demo_reachability_starts_from_the_declared_initial_overlay(self):
        def evidence_scene(demo):
            raw = {key: value for key, value in fixture().items() if key in s.COMMON or key == 'assumptions'}
            raw.update(
                type='evidence_only',
                initialState={'evidence': 'sources'},
                printState={'evidence': 'sources'},
                fallbackSummary={'field': 'headline', 'text': 'Proof'},
                sources=[{'id': 'safe', 'label': 'Safe', 'detail': 'Source', 'url': 'https://example.com/data'}],
                demo=demo,
            )
            return raw

        static = {'pattern': 'bullet_list', 'headline': 'Proof', 'bullets': [{'text': 'Evidence is available'}]}
        compiled = compile_fixture(
            evidence_scene([{'stepKey': 'hide-initial', 'action': 'closeEvidence'}]),
            static,
        )
        self.assertEqual(compiled.compiled['steps'][0]['targetKey'], 'evidence:close')

        with self.assertRaises(c.SceneValidationError) as caught:
            compile_fixture(
                evidence_scene([{'stepKey': 'double-open', 'action': 'openEvidence'}]),
                static,
            )
        self.assertEqual(caught.exception.code, 'demo_target')

    def test_panel_demo_reachability_tracks_the_current_visible_close_target(self):
        def panel_scene(kind, *, initial, allow_none, demo):
            raw = {key: value for key, value in fixture().items() if key in s.COMMON}
            panels = [
                {'id': name, 'label': name.title(), 'heading': name.title(), 'body': name + ' body'}
                for name in ('one', 'two')
            ]
            raw.update(
                type=kind,
                initialState={'panel': initial},
                printState={'panel': initial},
                fallbackSummary={'field': 'headline', 'text': 'Proof'},
                demo=demo,
            )
            if kind == 'accordion':
                raw.update(items=panels, allowNone=allow_none)
            else:
                raw.update(panels=panels, parentSummary='Parent', returnLabel='Back')
            return raw

        static = {'pattern': 'bullet_list', 'headline': 'Proof', 'bullets': [{'text': 'Summary'}]}
        valid = panel_scene(
            'drilldown',
            initial='one',
            allow_none=True,
            demo=[
                {'stepKey': 'close-one', 'action': 'closePanel', 'panel': 'one'},
                {'stepKey': 'open-two', 'action': 'openPanel', 'panel': 'two'},
                {'stepKey': 'close-two', 'action': 'closePanel', 'panel': 'two'},
            ],
        )
        compile_fixture(valid, static)
        visible_drilldown_switch = panel_scene(
            'drilldown',
            initial=None,
            allow_none=True,
            demo=[
                {'stepKey': 'open-one', 'action': 'openPanel', 'panel': 'one'},
                {'stepKey': 'open-two', 'action': 'openPanel', 'panel': 'two'},
                {'stepKey': 'close-two', 'action': 'closePanel', 'panel': 'two'},
            ],
        )
        compile_fixture(visible_drilldown_switch, static)

        invalid_cases = [
            panel_scene(
                'drilldown',
                initial='one',
                allow_none=True,
                demo=[{'stepKey': 'close-hidden', 'action': 'closePanel', 'panel': 'two'}],
            ),
            panel_scene(
                'drilldown',
                initial='one',
                allow_none=True,
                demo=[
                    {'stepKey': 'show', 'action': 'openEvidence'},
                    {'stepKey': 'close-inert-panel', 'action': 'closePanel', 'panel': 'one'},
                ],
            ),
            panel_scene(
                'accordion',
                initial='one',
                allow_none=False,
                demo=[{'stepKey': 'close-required', 'action': 'closePanel', 'panel': 'one'}],
            ),
        ]
        for raw in invalid_cases:
            with self.subTest(kind=raw['type'], demo=raw['demo']):
                with self.assertRaises(c.SceneValidationError) as caught:
                    compile_fixture(raw, static)
                self.assertEqual(caught.exception.code, 'demo_target')

    def test_numeric_serialization_reserved_outputs_and_precise_display_rounding(self):
        compiled = s.serialize_compiled_scene(compile_fixture().compiled)
        self.assertEqual(compiled['controls'][0]['min'], '0')
        self.assertEqual(compiled['controls'][0]['step'], '1')
        raw = fixture(); raw['model']['output'] = 'score'
        with self.assertRaises(c.SceneValidationError): program(raw)
        raw = fixture()
        raw['model']['intercept']['value'] = D('3.125')
        raw['model']['round'] = 2
        static = fallback()
        static['items'][0].update(value=D('8.125'), value_text='8.13 units')
        static['interactive_result']['value'] = D('8.125')
        static['annotation'] = 'result 8.13 units; Proceed; threshold ≥ 8 units; Run'
        self.assertTrue(compile_fixture(raw, static).fallback_check['matched'])

    def test_first_invalid_state_is_canonical_even_if_initial_is_invalid(self):
        raw = fixture(); raw['view']['domain'] = [0, 1]
        with self.assertRaises(c.SceneValidationError) as caught: compile_fixture(raw)
        self.assertEqual(caught.exception.state, {'x': D(0)})
        self.assertEqual(caught.exception.location.file, 'scene.json')

    def test_all_state_view_adapters_and_invariant_labels(self):
        raw = {k: v for k, v in fixture().items() if k in s.COMMON or k in ('quantities', 'assumptions')}
        raw.update(type='state_toggle', initialState={'scenario': 'base'}, printState={'scenario': 'base'}, controls=[{'id': 'scenario', 'kind': 'segmented', 'label': 'Scenario', 'options': [{'value': 'base', 'label': 'Base'}, {'value': 'other', 'label': 'Other'}]}])
        literal = lambda value: {'value': value, 'quantity': 'value', 'provenance': copy.deepcopy(PROV)}
        cases = [
            ({'component': 'ranked_list', 'items': [{'id': 'a', 'label': 'A', 'rank': 1}, {'id': 'b', 'label': 'B', 'rank': 2, 'removed': True}]},
             {'pattern': 'bullet_list', 'headline': 'Order', 'bullets': [{'item_id': 'a', 'text': 'A', 'rank': 1, 'removed': False, 'emphasis': False}, {'item_id': 'b', 'text': 'B', 'rank': 2, 'removed': True, 'emphasis': False, 'sub': ['Removed']}]}),
            ({'component': 'bar_compare', 'quantity': 'value', 'domain': [0, 10], 'baseline': 0, 'items': [{'id': 'a', 'label': 'Capacity · Before', 'value': literal(2)}, {'id': 'b', 'label': 'Capacity · After', 'value': literal(5), 'emphasis': True}]},
             {'pattern': 'before_after', 'headline': 'Change', 'quantity': 'value', 'unit': 'units', 'value_domain': [0, 10], 'baseline': 0, 'before_label': 'Before', 'after_label': 'After', 'pairs': [{'label': 'Capacity', 'before': 2, 'after': 5, 'before_item_id': 'a', 'after_item_id': 'b', 'before_text': '2 units', 'after_text': '5 units', 'delta_text': '+3 units'}]}),
            ({'component': 'dot_plot', 'xLabel': 'X', 'xQuantity': 'value', 'xDomain': [0, 10], 'yLabel': 'Y', 'yQuantity': 'value', 'yDomain': [0, 10], 'points': [{'id': 'a', 'label': 'A', 'x': literal(2), 'y': literal(5), 'highlight': True}]},
             {'pattern': 'scatter', 'headline': 'Position', 'x_axis': {'label': 'X', 'quantity': 'value', 'unit': 'units', 'domain': [0, 10], 'tick_labels': ['0 units', '10 units']}, 'y_axis': {'label': 'Y', 'quantity': 'value', 'unit': 'units', 'domain': [0, 10], 'tick_labels': ['0 units', '10 units']}, 'points': [{'item_id': 'a', 'label': 'A', 'x': 2, 'y': 5, 'emphasis': True}]}),
        ]
        for view, static in cases:
            raw['states'] = [{'id': name, 'provenance': copy.deepcopy(PROV), 'view': copy.deepcopy(view)} for name in ('base', 'other')]
            with self.subTest(component=view['component']):
                self.assertTrue(compile_fixture(raw, static).fallback_check['matched'])
                key = 'points' if view['component'] == 'dot_plot' else 'items'
                raw['states'][1]['view'][key][0]['label'] = 'Changed identity'
                with self.assertRaises(c.SceneValidationError):
                    compile_fixture(raw, static)

    def test_recommendation_panel_both_static_patterns_require_visible_decision(self):
        raw = fixture()
        raw.update(type='score_model', controls=[{'id': name, 'kind': 'toggle', 'label': name, 'options': [{'value': 'low', 'label': 'Low'}, {'value': 'high', 'label': 'High'}]} for name in ('a', 'b')], initialState={'a': 'high', 'b': 'low'}, printState={'a': 'high', 'b': 'low'})
        raw['quantities']['points'] = {'dimension': 'score', 'unit': 'point', 'display': 'points'}
        raw['model'] = {'kind': 'score_sum', 'quantity': 'points', 'contributions': [{'control': name, 'values': [{'input': 'low', 'points': 0}, {'input': 'high', 'points': points}]} for name, points in [('a', 3), ('b', 2)]], 'bands': [{'id': 'early', 'min': 0, 'max': 3, 'label': 'Early'}, {'id': 'ready', 'min': 3, 'max': 5, 'label': 'Ready'}], 'format': 'score', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)}
        raw['reporting'] = {'primaryOutput': 'score'}
        raw['decisionContract']['metric']['ref'] = 'output:score'
        raw['decisionContract']['threshold'].update(value=3, quantity='points')
        raw['view'] = {'component': 'recommendation_panel', 'score': {'ref': 'output:score'}}
        metadata = {'quantity': 'points', 'value': 3, 'classification': 'Ready', 'decision_status': 'Proceed', 'recommendation': 'Run', 'operator': 'gte', 'threshold': 3}
        for static in [
            {'pattern': 'summary_strip', 'headline': 'Ready at three', 'annotation': '', 'interactive_result': metadata, 'blocks': [{'metric': '3 points', 'claim': 'Ready', 'proof': 'Proceed; threshold ≥ 3 points', 'implication': 'Run'}]},
            {'pattern': 'closing', 'headline': 'Ready at three', 'annotation': '', 'interactive_result': metadata, 'takeaways': ['score 3 points', 'Ready', 'Proceed; threshold ≥ 3 points'], 'next_steps': [{'action': 'Run'}]},
        ]:
            with self.subTest(pattern=static['pattern']):
                self.assertTrue(compile_fixture(raw, static).fallback_check['matched'])
                bad = copy.deepcopy(static)
                if 'blocks' in bad: bad['blocks'][0]['proof'] = 'Other decision'
                else: bad['takeaways'][2] = 'Other decision'
                with self.assertRaises(c.SceneValidationError): compile_fixture(raw, bad)

    def test_deterministic_complete_compilation_and_audience_boundary(self):
        raw = fixture()
        raw['demo'] = [{'stepKey': 'raise', 'action': 'set', 'control': 'x', 'value': 2}, {'stepKey': 'lower', 'action': 'set', 'control': 'x', 'value': 0}, {'stepKey': 'next', 'action': 'goto', 'slideId': 'next'}]
        result = compile_fixture(raw)
        compiled = s.serialize_compiled_scene(result.compiled)
        self.assertEqual(compiled['initialEvaluation']['outputs']['result']['value'], '8')
        self.assertEqual(compiled['initialEvaluation']['decision']['outcome'], 'met')
        self.assertEqual(result.audit.accepted_state_count, 3)
        self.assertEqual(compiled['steps'][0]['targetKey'], 'control:x')
        self.assertEqual(compiled['steps'][1]['targetKey'], 'control:x')
        self.assertNotIn('targetKey', compiled['steps'][2])
        self.assertNotIn('locations', compiled)
        self.assertEqual(json.dumps(compiled, sort_keys=True), json.dumps(s.serialize_compiled_scene(compile_fixture(raw).compiled), sort_keys=True))
        step_state = result.audit_evaluations['step:raise']
        self.assertEqual(step_state['inputs'], {'x': '2'})
        self.assertEqual(step_state['outputs'], {'result': '13'})

    def test_closed_slots_wrong_quantity_and_first_canonical_counterexample(self):
        for value in [8, {'ref': 'output:result', 'value': 8}, {'ref': 'output:recommendation'}, {'ref': 'output:missing'}, {'value': 8, 'quantity': 'value'}]:
            raw = fixture(); raw['view']['items'][0]['value'] = value
            with self.subTest(value=value), self.assertRaises(c.SceneValidationError):
                compile_fixture(raw)
        raw = fixture(); raw['view']['domain'] = [0, 10]
        with self.assertRaises(c.SceneValidationError) as caught:
            compile_fixture(raw)
        self.assertEqual(caught.exception.code, 'view_domain')
        self.assertEqual(caught.exception.state, {'x': D(2)})

    def test_static_visible_text_not_only_metadata_and_demo_validation(self):
        bad = fallback(); bad['items'][0]['value_text'] = '8.1 units'
        with self.assertRaises(c.SceneValidationError) as caught:
            compile_fixture(static=bad)
        self.assertEqual(caught.exception.code, 'fallback_mismatch')
        self.assertIn('/items/0/value_text', caught.exception.location.pointer)
        for demo in [[{'stepKey': 'set', 'action': 'set', 'control': 'x', 'value': '1'}], [{'stepKey': 'wait', 'action': 'wait', 'ms': 5001}], [{'stepKey': 'bad', 'action': 'goto', 'slideId': 'missing'}], [{'stepKey': 'same', 'action': 'openEvidence'}, {'stepKey': 'same', 'action': 'closeEvidence'}]]:
            raw = fixture(); raw['demo'] = demo
            with self.subTest(demo=demo), self.assertRaises(c.SceneValidationError):
                compile_fixture(raw)

    def test_disclosure_summaries_safe_links_and_panel_replay(self):
        raw = {k: v for k, v in fixture().items() if k in s.COMMON or k == 'assumptions'}
        raw.update(type='evidence_only', initialState={'evidence': 'closed'}, printState={'evidence': 'closed'}, fallbackSummary={'field': 'headline', 'text': 'Proof'}, sources=[{'id': 'safe', 'label': 'Safe', 'detail': 'Source', 'url': 'https://example.com/data'}, {'id': 'unsafe', 'label': 'Unsafe', 'detail': 'Source', 'url': 'javascript:alert(1)'}])
        static = {'pattern': 'bullet_list', 'headline': 'Proof', 'bullets': [{'text': 'Evidence is available'}]}
        compiled = compile_fixture(raw, static).compiled
        self.assertIn('source:safe', compiled['targets'])
        self.assertNotIn('source:unsafe', compiled['targets'])
        raw.update(type='drilldown', initialState={'panel': None}, printState={'panel': None}, panels=[{'id': 'detail', 'label': 'Detail', 'heading': 'Detail heading', 'body': 'Detail body'}], parentSummary='Summary', returnLabel='Back', demo=[{'stepKey': 'bad-close', 'action': 'closePanel', 'panel': 'detail'}])
        with self.assertRaises(c.SceneValidationError):
            compile_fixture(raw, static)



class SimpleModelTests(unittest.TestCase):
    def test_graph_rounds_each_product_and_rejects_forward_or_orphan_nodes(self):
        raw = fixture()
        raw['controls'][0].update(min=0, max=1, step=D('.5'))
        raw['model'] = {'kind': 'operation_graph', 'nodes': [
            {'id': 'x', 'op': 'input', 'control': 'x', 'quantity': 'value'},
            {'id': 'half', 'op': 'constant', 'value': D('.5'), 'quantity': 'value', 'provenance': copy.deepcopy(PROV)},
            {'id': 'product', 'op': 'multiply', 'left': 'x', 'right': 'half', 'quantity': 'value'},
            {'id': 'sum', 'op': 'add', 'left': 'product', 'right': 'product', 'quantity': 'value'},
        ], 'outputs': {'result': {'node': 'sum', 'quantity': 'value', 'format': 'number', 'round': 1}}}
        self.assertEqual(s.evaluate_model(program(raw), {'x': D('.5')})['result'].value, D('.6'))
        self.assertIn('half = 0.5 units', s._formula_text(program(raw), raw['controls']))
        forward = copy.deepcopy(raw); forward['model']['nodes'][2]['right'] = 'sum'
        with self.assertRaises(c.SceneValidationError): program(forward)
        orphan = copy.deepcopy(raw); orphan['model']['outputs']['result']['node'] = 'product'
        with self.assertRaises(c.SceneValidationError): program(orphan)
        large = copy.deepcopy(raw); large['model']['nodes'] *= 9
        with self.assertRaises(c.SceneValidationError): program(large)

    def test_graph_min_max_abs_clamp_and_divide_hand_calculated(self):
        raw = fixture(); raw['controls'][0].update(min=-2, max=2)
        raw['model'] = {'kind': 'operation_graph', 'nodes': [
            {'id': 'x', 'op': 'input', 'control': 'x', 'quantity': 'value'},
            {'id': 'one', 'op': 'constant', 'value': 1, 'quantity': 'value', 'provenance': copy.deepcopy(PROV)},
            {'id': 'two', 'op': 'constant', 'value': 2, 'quantity': 'value', 'provenance': copy.deepcopy(PROV)},
            {'id': 'absolute', 'op': 'abs', 'input': 'x', 'quantity': 'value'},
            {'id': 'small', 'op': 'min', 'inputs': ['absolute', 'one'], 'quantity': 'value'},
            {'id': 'large', 'op': 'max', 'inputs': ['x', 'two'], 'quantity': 'value'},
            {'id': 'clamped', 'op': 'clamp', 'input': 'x', 'min': 'one', 'max': 'two', 'quantity': 'value'},
            {'id': 'quotient', 'op': 'divide', 'left': 'absolute', 'right': 'two', 'quantity': 'value'},
        ], 'outputs': {name: {'node': node, 'quantity': 'value', 'format': 'number', 'round': 0} for name, node in [('minimum', 'small'), ('maximum', 'large'), ('bounded', 'clamped'), ('ratio', 'quotient')]}}
        out = s.evaluate_model(program(raw), {'x': D(-2)})
        self.assertEqual([out[name].value for name in ('minimum', 'maximum', 'bounded', 'ratio')], [D(1), D(2), D(1), D(1)])

    def test_endpoint_interpolation_does_not_round_slope_first(self):
        raw = fixture(); raw['controls'][0]['max'] = 3
        raw['model'] = {'kind': 'piecewise', 'input': 'x', 'segments': [{'kind': 'endpoints', 'min': 0, 'max': 3, 'inputQuantity': 'value', 'start': {'value': 0, 'quantity': 'value'}, 'end': {'value': 1, 'quantity': 'value'}}], 'output': 'result', 'outputQuantity': 'value', 'format': 'number', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)}
        p = program(raw)
        self.assertEqual([s.evaluate_model(p, {'x': D(i)})['result'].value for i in range(4)], [D(0), D(0), D(1), D(1)])

    def test_piecewise_right_boundary_and_exact_endpoint_interpolation(self):
        raw = fixture()
        raw['controls'][0]['max'] = 4
        raw['model'] = {'kind': 'piecewise', 'input': 'x', 'segments': [
            {'kind': 'linear', 'min': 0, 'max': 2, 'inputQuantity': 'value', 'slope': {'coefficient': 2, 'inputQuantity': 'value', 'outputQuantity': 'value'}, 'intercept': {'value': 1, 'quantity': 'value'}},
            {'kind': 'endpoints', 'min': 2, 'max': 4, 'inputQuantity': 'value', 'start': {'value': 5, 'quantity': 'value'}, 'end': {'value': 11, 'quantity': 'value'}},
        ], 'output': 'result', 'outputQuantity': 'value', 'format': 'number', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)}
        p = program(raw)
        self.assertEqual([s.evaluate_model(p, {'x': D(i)})['result'].value for i in range(5)], list(map(D, [1, 3, 5, 8, 11])))
        raw['model']['segments'][1]['start']['value'] = 6
        self.assertEqual(s.evaluate_model(program(raw), {'x': D(2)})['result'].value, D(6))
        raw['model']['segments'][1]['min'] = 3
        with self.assertRaises(c.SceneValidationError):
            program(raw)

    def test_score_totals_classification_and_boundary_lineage(self):
        raw = fixture()
        raw['type'] = 'score_model'
        raw['controls'] = [{'id': name, 'kind': 'select', 'label': name, 'options': [{'value': 'low', 'label': 'Low'}, {'value': 'high', 'label': 'High'}]} for name in ('a', 'b')]
        raw['initialState'] = raw['printState'] = {'a': 'low', 'b': 'low'}
        raw['quantities']['points'] = {'dimension': 'score', 'unit': 'point', 'display': 'points'}
        raw['model'] = {'kind': 'score_sum', 'quantity': 'points', 'contributions': [{'control': name, 'values': [{'input': 'low', 'points': 0}, {'input': 'high', 'points': points}]} for name, points in [('a', 3), ('b', 2)]], 'bands': [{'id': 'early', 'min': 0, 'max': 3, 'label': 'Early'}, {'id': 'ready', 'min': 3, 'max': 5, 'label': 'Ready'}], 'format': 'score', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)}
        p = program(raw)
        outputs = [s.evaluate_model(p, state) for state in c.iter_reachable_states(p.domains)]
        self.assertEqual([o['score'].value for o in outputs], list(map(D, [0, 2, 3, 5])))
        self.assertEqual([o['classification'].value for o in outputs], ['Early', 'Early', 'Ready', 'Ready'])
        self.assertGreater(len(outputs[2]['classification'].lineage.leaves), len(outputs[2]['score'].lineage.leaves))
        raw['model']['bands'][1]['min'] = 4
        with self.assertRaises(c.SceneValidationError):
            program(raw)

    def test_graph_node_rounding_lineage_and_conservative_zero_interval(self):
        raw = fixture()
        raw['controls'][0]['step'] = D('.1')
        raw['model'] = {'kind': 'operation_graph', 'nodes': [
            {'id': 'x', 'op': 'input', 'control': 'x', 'quantity': 'value'},
            {'id': 'two', 'op': 'constant', 'value': 2, 'quantity': 'value', 'provenance': copy.deepcopy(PROV)},
            {'id': 'doubled', 'op': 'multiply', 'left': 'x', 'right': 'two', 'quantity': 'value'},
            {'id': 'difference', 'op': 'subtract', 'left': 'doubled', 'right': 'x', 'quantity': 'value'},
        ], 'outputs': {'total': {'node': 'doubled', 'quantity': 'value', 'format': 'number', 'round': 1}, 'increment': {'node': 'difference', 'quantity': 'value', 'format': 'number', 'round': 1}}}
        p = program(raw)
        out = s.evaluate_model(p, {'x': D('1.5')})
        self.assertEqual(out['total'].value, D(3))
        self.assertEqual(out['increment'].value, D('1.5'))
        self.assertEqual(len(out['increment'].lineage.leaves), 2)
        raw['model']['nodes'][2]['op'] = 'divide'
        raw['model']['nodes'][2]['right'] = 'x'
        with self.assertRaisesRegex(c.SceneValidationError, 'strictly above or below zero'):
            program(raw)

    def test_linear_lookup_and_piecewise_hand_calculated_outputs(self):
        raw = fixture()
        p = program(raw)
        self.assertEqual([s.evaluate_model(p, {'x': D(i)})['result'].value for i in range(3)], [D(3), D(8), D(13)])
        raw['model'] = {'kind': 'lookup', 'input': 'x', 'entries': [{'input': i, 'output': {'value': value, 'quantity': 'value'}} for i, value in enumerate([3, 8, 13])], 'output': 'result', 'outputQuantity': 'value', 'format': 'number', 'round': 0, 'modelProvenance': copy.deepcopy(PROV)}
        self.assertEqual(s.evaluate_model(program(raw), {'x': D(1)})['result'].value, D(8))
        raw['model']['entries'].pop()
        with self.assertRaises(c.SceneValidationError):
            program(raw)

    def test_linear_rounds_once_and_includes_all_input_lineage(self):
        raw = fixture()
        raw['controls'][0].update(min=0, max=1, step=D('.5'))
        raw['initialState'] = raw['printState'] = {'x': D('.5')}
        raw['model']['intercept']['value'] = D('.25')
        raw['model']['terms']['x']['coefficient'] = D('.5')
        output = s.evaluate_model(program(raw), {'x': D('.5')})['result']
        self.assertEqual(output.value, D('.5'))
        self.assertEqual(len(output.lineage.leaves), 3)
        self.assertEqual(output.lineage.leaves, ('leaf-001', 'leaf-002', 'leaf-003'))
        self.assertTrue(output.lineage.derived)


if __name__ == '__main__':
    unittest.main()
