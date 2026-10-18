"""Visible explanatory geometry must agree with the executable scene model."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from interactive_scene import LocatedDocument, compile_scene
from interactive_contract import Location, SceneValidationError

EXAMPLE = ROOT / 'examples' / 'interactive-deck'


def fixture(name):
    return tuple(json.loads((EXAMPLE / folder / (name + '.json')).read_text())
                 for folder in ('scenes', 'specs'))


def compile_pair(raw, spec):
    return compile_scene(LocatedDocument(raw, Location('scene.json')),
                         fallback_spec=spec, fallback_path='spec.json',
                         slide_id='relay', slide_ids={'relay'}, lang='en')


class EvidenceContextTests(unittest.TestCase):
    def test_contexts_match_the_executable_scene(self):
        for name in ('04-route-priority', '05-adoption-value', '06-readiness-score'):
            with self.subTest(name=name):
                self.assertTrue(compile_pair(*fixture(name)).fallback_check['matched'])

    def test_an_unrelated_linear_slope_cannot_illustrate_the_model(self):
        raw, spec = fixture('05-adoption-value')
        spec['model_context']['coefficient'] = 0.04
        with self.assertRaisesRegex(SceneValidationError, 'fallback_mismatch'):
            compile_pair(raw, spec)

    def test_a_different_intercept_cannot_illustrate_the_model(self):
        raw, spec = fixture('05-adoption-value')
        spec['model_context']['intercept'] = -1
        with self.assertRaisesRegex(SceneValidationError, 'fallback_mismatch'):
            compile_pair(raw, spec)

    def test_a_false_line_through_the_correct_print_point_is_rejected(self):
        raw, spec = fixture('05-adoption-value')
        # Both lines pass through (55, 1.8); matching only that point is not
        # evidence that the rest of the relationship is truthful.
        spec['model_context'].update(intercept=-0.4, coefficient=0.04)
        with self.assertRaisesRegex(SceneValidationError, 'fallback_mismatch'):
            compile_pair(raw, spec)

    def test_score_contribution_values_and_labels_are_not_free_form(self):
        raw, original = fixture('06-readiness-score')
        for field, value in (('value', 23), ('label', 'Unrelated evidence')):
            spec = copy.deepcopy(original)
            spec['model_context']['components'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(SceneValidationError, 'fallback_mismatch'):
                compile_pair(raw, spec)

    def test_score_removal_must_be_an_available_control_alternative(self):
        raw, spec = fixture('06-readiness-score')
        # Dispatch frequency cannot reach zero within the authored controls.
        spec['model_context']['comparison']['remove_index'] = 0
        with self.assertRaisesRegex(SceneValidationError, 'fallback_mismatch'):
            compile_pair(raw, spec)

    def test_scenario_comparison_must_match_an_authored_state(self):
        raw, original = fixture('04-route-priority')
        for field, value in (('value', 83), ('rank', 2), ('item_id', 'invented')):
            spec = copy.deepcopy(original)
            spec['model_context']['values'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(SceneValidationError, 'fallback_mismatch'):
                compile_pair(raw, spec)
        spec = copy.deepcopy(original)
        spec['model_context']['label'] = 'Invented scenario'
        with self.assertRaisesRegex(SceneValidationError, 'fallback_mismatch'):
            compile_pair(raw, spec)
