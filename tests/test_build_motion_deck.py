import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_motion_deck import build, validate

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'examples/interactive-deck/motion.json'


class MotionBuilderTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads(MANIFEST.read_text(encoding='utf-8'))

    def test_empty_input_domain_is_rejected_before_rendering(self):
        p=self.data['pages'][3]
        p['input']['min']=p['input']['max']=p['input']['initial']
        with self.assertRaises(ValueError):validate(self.data)

    def test_missing_conditional_page_is_rejected_before_runtime(self):
        self.data['pages'][5]['conditions'][0]['page']='missing'
        with self.assertRaises(ValueError):validate(self.data)

    def test_text_cannot_escape_the_embedded_json_or_heading(self):
        self.data['pages'][0]['title']='</script><script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'motion.json'
            path.write_text(json.dumps(self.data),encoding='utf-8')
            result=build(path)
        self.assertNotIn('<script>alert(1)</script>',result)
        self.assertIn('\\u003c/script\\u003e',result)
        self.assertIn('&lt;/script&gt;',result)

    def test_served_artifacts_match_the_current_builder(self):
        for static,name in ((False,'deck.motion.html'),(True,'deck.motion.static.html')):
            self.assertEqual(build(MANIFEST,static),(MANIFEST.parent/name).read_text(encoding='utf-8'))

    def test_english_artifacts_are_current_and_fully_localized(self):
        manifest=MANIFEST.with_name('motion.en.json')
        for static,name in ((False,'deck.motion.en.html'),(True,'deck.motion.en.static.html')):
            result=build(manifest,static)
            self.assertEqual(result,(MANIFEST.parent/name).read_text(encoding='utf-8'))
            self.assertNotRegex(result,r'[\u3040-\u30ff\u3400-\u9fff]')
            self.assertIn('Gate 1.8</text>',result)
            self.assertIn('const money = n => (n / 100).toFixed(1)',result)

    def test_translation_keeps_exact_models_and_decision_conditions(self):
        english=json.loads(MANIFEST.with_name('motion.en.json').read_text())
        for ja,en in zip(self.data['pages'],english['pages']):
            self.assertEqual(ja['id'],en['id'])
            for field in ('model','domain','threshold','initial'):
                self.assertEqual(ja.get(field),en.get(field))
            if ja['kind']=='sequence':
                for a,b in zip(ja['conditions'],en['conditions']):
                    self.assertEqual({k:v for k,v in a.items() if k!='label'}, {k:v for k,v in b.items() if k!='label'})
