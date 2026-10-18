"""English copy, monetary units and the same conditional decision flow."""
from pathlib import Path
import tempfile
import unittest

from playwright.sync_api import sync_playwright
from scripts.build_motion_deck import build
from tests.e2e import test_motion_story as story

ROOT=Path(__file__).resolve().parents[2]
CAPTURES=ROOT/'output/playwright/motion-english'


class EnglishMotionTests(unittest.TestCase):
    context=story.MotionStoryTests.context
    go=story.MotionStoryTests.go

    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='motion-english-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.html=Path(cls.temp.name)/'english.html'
        cls.html.write_text(build(ROOT/'examples/interactive-deck/motion.en.json'))
        cls.runtime=sync_playwright().start()
        cls.addClassCleanup(cls.runtime.stop)
        cls.browser=cls.runtime.chromium.launch(headless=True)
        cls.addClassCleanup(cls.browser.close)
        CAPTURES.mkdir(parents=True,exist_ok=True)

    def test_all_pages_desktop_and_phone(self):
        for width,height in ((1440,900),(1280,720),(390,844)):
            page=self.context(width,height)
            for i in range(6):
                node=self.go(page,i)
                self.assertNotRegex(node.inner_text(),r'[\u3040-\u30ff\u3400-\u9fff]')
                self.assertFalse(node.locator('h1').evaluate('e=>e.scrollWidth>e.clientWidth+2'))
                if width==390:
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth+1'))
                elif i:
                    comparison=node.locator('.comparison').bounding_box()
                    action=node.locator('.evidence-button').bounding_box()
                    self.assertLessEqual(comparison['y']+comparison['height'],action['y']-4,f'panel {i+1}')
                    takeaway=node.locator('.takeaway').bounding_box()
                    footer=node.locator('footer').bounding_box()
                    self.assertLessEqual(takeaway['y']+takeaway['height'],footer['y']-4,f'footer {i+1}')
                page.screenshot(path=str(CAPTURES/f'{i+1:02}-{width}.png'),full_page=width==390)
            self.assertFalse(self.errors)
            page.close()

    def test_money_evidence_help_and_conditional_expansion(self):
        page=self.context()
        node=self.go(page,3)
        self.assertEqual(node.locator('[data-hero]').inner_text(),'1.8')
        self.assertIn('Gate 1.8',node.locator('svg').text_content())
        for adoption,amount in ((30,'0.3'),(55,'1.8'),(80,'3.3')):
            node.locator('[data-slider]').evaluate('(e,n)=>{e.value=n;e.dispatchEvent(new Event("input",{bubbles:true}));}',adoption)
            self.assertEqual(node.locator('[data-hero]').inner_text(),amount)
        node.locator('[data-slider]').evaluate('e=>{e.value=30;e.dispatchEvent(new Event("input",{bubbles:true}));}')
        self.assertIn('$1.5m/year below',node.locator('[data-takeaway]').inner_text())
        node.locator('[data-evidence]').first.click()
        self.assertIn('$0.3m/year',page.locator('#drawer-content').inner_text())
        page.get_by_role('tab',name='Sources & assumptions').click()
        self.assertIn('not evidence of a causal effect',page.locator('#drawer-content').inner_text())
        page.screenshot(path=str(CAPTURES/'sources.png'))
        page.keyboard.press('Escape')
        node=self.go(page,4);node.locator('[data-toggle=manager]').uncheck()
        self.assertIn('16 points below',node.locator('[data-gap-message]').inner_text())
        node=self.go(page,5)
        node.locator('[data-next-step]').click();node.locator('[data-next-step]').click()
        self.assertEqual(node.locator('[data-panel-label]').inner_text(),'Hold East expansion')
        self.assertIn('scaleX(0)',node.locator('[data-task="2"]').get_attribute('style'))
        page.locator('[data-help]').click()
        self.assertIn('Start or stop the guided demo',page.locator('#drawer-content').inner_text())
        self.assertNotRegex(page.locator('#evidence-dialog').inner_text(),r'[\u3040-\u30ff\u3400-\u9fff]')
        self.assertFalse(self.errors)

    def test_english_guided_demo_and_static_companion(self):
        page=self.context(reduce=False)
        page.evaluate('() => { MotionDeck.startDemo({pace:.02}); }')
        page.wait_for_function('() => !MotionDeck.snapshot().demo && MotionDeck.snapshot().overview',timeout=20000)
        self.assertEqual(page.locator('.overview-card').count(),6)
        self.assertIn('Guided demo',page.locator('[data-demo-start]').inner_text())
        self.assertNotRegex(page.locator('#overview-dialog').inner_text(),r'[\u3040-\u30ff\u3400-\u9fff]')
        page.screenshot(path=str(CAPTURES/'demo-overview.png'))
        static=Path(self.temp.name)/'static.html'
        static.write_text(build(ROOT/'examples/interactive-deck/motion.en.json',True))
        page.goto(static.as_uri())
        self.assertEqual(page.locator('.motion-page:visible').count(),6)
        self.assertEqual(page.locator('[data-page=value] [data-hero]').inner_text(),'1.8')
        self.assertFalse(self.errors)

    def test_decision_headlines_baseline_and_reset_follow_the_active_state(self):
        page=self.context()
        node=self.go(page,3)
        node.locator('[data-slider]').fill('30')
        self.assertIn('falls short',node.locator('h1').inner_text())
        self.assertEqual(node.locator('[data-decision-status]').inner_text(),'VALUE GATE NOT MET')
        self.assertTrue(node.locator('[data-baseline-point]').is_visible())
        self.assertIn('$1.8m',node.locator('[data-baseline-label]').text_content())
        node.locator('[data-model-reset]').click()
        self.assertIn('55% adoption meets',node.locator('h1').inner_text())
        self.assertEqual(node.locator('[data-hero]').inner_text(),'1.8')
        self.assertFalse(node.locator('[data-baseline-point]').is_visible())
        node=self.go(page,4);node.locator('[data-toggle=manager]').uncheck()
        self.assertIn('54',node.locator('h1').inner_text())
        self.assertIn('16-point gap',node.locator('h1').inner_text())
        node=self.go(page,5)
        self.assertIn('Hold East',node.locator('h1').inner_text())
        self.assertEqual(node.locator('[data-decision-status]').inner_text(),'2 OF 3 CONDITIONS MET')
        node=self.go(page,2);node.locator('[data-scenario=base]').click()
        self.assertIn('Central ranks second',node.locator('h1').inner_text())
        node=self.go(page,5)
        self.assertEqual(node.locator('[data-decision-status]').inner_text(),'1 OF 3 CONDITIONS MET')
        self.assertFalse(self.errors)
