"""Real presentation flows, visual boundaries and the complete scripted demo."""
import json
from pathlib import Path
import tempfile
import unittest

from playwright.sync_api import sync_playwright
from scripts.build_motion_deck import build

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'examples/interactive-deck/motion.json'
CAPTURES = ROOT / 'output/playwright/motion-final'


class MotionStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='motion-story-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.html = Path(cls.temp.name) / 'deck.html'
        cls.html.write_text(build(MANIFEST), encoding='utf-8')
        cls.runtime = sync_playwright().start()
        cls.addClassCleanup(cls.runtime.stop)
        cls.browser = cls.runtime.chromium.launch(headless=True)
        cls.addClassCleanup(cls.browser.close)
        CAPTURES.mkdir(parents=True, exist_ok=True)

    def context(self, width=1440, height=900, reduce=True):
        context = self.browser.new_context(viewport={'width':width,'height':height}, has_touch=width<=760, is_mobile=width<=760, reduced_motion='reduce' if reduce else 'no-preference')
        self.addCleanup(context.close)
        page = context.new_page()
        self.errors = []
        page.on('pageerror', lambda error: self.errors.append(str(error)))
        page.goto(self.html.as_uri(), wait_until='load')
        page.wait_for_function('() => Boolean(window.MotionDeck)')
        return page

    def go(self, page, index):
        page.evaluate('(n) => MotionDeck.go(n)', index)
        return page.locator('.motion-page.active')

    def test_every_page_fits_with_readable_exhibits_and_no_panel_overlap(self):
        for width,height in ((1440,900),(1280,720)):
            page = self.context(width,height)
            for index in range(6):
                node = self.go(page,index)
                page.screenshot(path=str(CAPTURES / f'{index+1:02}-{width}.png'))
                self.assertFalse(node.locator('h1').evaluate('e=>e.scrollWidth>e.clientWidth+2'), f'title {index+1}')
                footer = node.locator('footer').bounding_box()
                if index == 0:
                    for card in node.locator('.flow-stop').all():
                        box=card.bounding_box()
                        self.assertLessEqual(box['y']+box['height'], footer['y']-8, 'overview card overlaps source')
                else:
                    comparison=node.locator('.comparison').bounding_box()
                    action=node.locator('.evidence-button').bounding_box()
                    self.assertLessEqual(comparison['y']+comparison['height'],action['y']-4, f'panel overlap page {index+1}')
                    takeaway=node.locator('.takeaway').bounding_box()
                    self.assertLessEqual(takeaway['y']+takeaway['height'],footer['y']-4, f'takeaway page {index+1}')
                    if index == 3:
                        formula=node.locator('.formula').bounding_box()
                        self.assertLessEqual(formula['y']+formula['height'],takeaway['y']-4,'model formula overlaps takeaway')
            self.assertFalse(self.errors)
            page.close()

    def test_overview_direct_chart_evidence_and_native_focus_return(self):
        page=self.context()
        page.locator('[data-go=causes]').click()
        self.assertEqual(page.evaluate('MotionDeck.snapshot().page'),2)
        bar=page.locator('.active [data-item=dispatch]')
        bar.focus();page.keyboard.press('Enter')
        self.assertTrue(page.locator('#evidence-dialog').evaluate('e=>e.open'))
        self.assertIn('配車調整',page.locator('.drawer-selected').inner_text())
        page.get_by_role('tab',name='出所と前提').click()
        self.assertIn('実測値ではありません',page.locator('#drawer-content').inner_text())
        page.keyboard.press('Escape')
        self.assertTrue(bar.evaluate('e=>e===document.activeElement'))
        page.screenshot(path=str(CAPTURES/'evidence-closed.png'))
        self.assertFalse(self.errors)

    def test_model_and_actions_propagate_to_conditional_timeline(self):
        page=self.context()
        node=self.go(page,2)
        node.locator('[data-scenario=base]').click()
        self.assertEqual(node.locator('[data-item=east] [data-rank]').inner_text(),'3')
        node.locator('[data-scenario=constrained]').click()
        self.assertEqual(node.locator('[data-item=east] [data-rank]').inner_text(),'2')
        self.assertEqual(node.locator('[data-item=east] [data-bar-value]').inner_text(),'76')
        node=self.go(page,3)
        node.locator('[data-slider]').evaluate("e=>{e.value=30;e.dispatchEvent(new Event('input',{bubbles:true}));}")
        self.assertEqual(node.locator('[data-hero]').inner_text(),'30')
        self.assertIn('150万ドル不足',node.locator('[data-takeaway]').inner_text())
        node=self.go(page,4)
        node.locator('[data-toggle=manager]').uncheck()
        self.assertEqual(node.locator('[data-hero]').inner_text(),'54')
        self.assertIn('16点不足',node.locator('[data-gap-message]').inner_text())
        page.screenshot(path=str(CAPTURES/'readiness-missing.png'))
        node=self.go(page,5)
        for i in range(3):
            node.locator('[data-next-step]').click()
            if i == 1:
                self.assertIn('保留',node.locator('[data-panel-label]').inner_text())
        self.assertIn('追加できません',node.locator('[data-takeaway]').inner_text())
        self.assertIn('scaleX(0)',node.locator('[data-task="2"]').get_attribute('style'))
        node=self.go(page,3)
        node.locator('[data-slider]').evaluate("e=>{e.value=55;e.dispatchEvent(new Event('input',{bubbles:true}));}")
        node=self.go(page,4);node.locator('[data-toggle=manager]').check()
        node=self.go(page,5)
        self.assertIn('scaleX(1)',node.locator('[data-task="2"]').get_attribute('style'))
        self.assertEqual(node.locator('[data-hero]').inner_text(),'12')
        page.screenshot(path=str(CAPTURES/'plan-complete.png'))
        self.assertFalse(self.errors)

    def test_scripted_cursor_demo_finishes_in_overview_and_can_cancel(self):
        page=self.context(reduce=False)
        page.evaluate('() => { MotionDeck.startDemo({pace:.02}); }')
        page.wait_for_function('() => !MotionDeck.snapshot().demo && MotionDeck.snapshot().overview', timeout=20000)
        self.assertEqual(page.locator('.overview-card').count(),6)
        for preview in page.locator('.preview-box').all():
            frame=preview.bounding_box();heading=preview.locator('h1').bounding_box()
            self.assertGreaterEqual(heading['y'],frame['y'])
            self.assertLess(heading['y']+heading['height'],frame['y']+frame['height'])
        self.assertEqual(page.evaluate('MotionDeck.snapshot().state.value.input'),55)
        self.assertTrue(page.evaluate('MotionDeck.snapshot().state.readiness.manager'))
        page.screenshot(path=str(CAPTURES/'demo-overview.png'))
        page.keyboard.press('Escape')
        page.evaluate('() => { MotionDeck.startDemo({pace:1}); }')
        page.wait_for_function('() => MotionDeck.snapshot().demo')
        page.mouse.click(8,8)
        page.wait_for_function('() => !MotionDeck.snapshot().demo')
        after=page.evaluate('JSON.stringify(MotionDeck.snapshot())')
        page.wait_for_timeout(150)
        self.assertEqual(after,page.evaluate('JSON.stringify(MotionDeck.snapshot())'))
        self.assertFalse(self.errors)

    def test_mobile_reflows_and_static_states_remain_operable(self):
        page=self.context(390,844)
        for index in range(6):
            node=self.go(page,index)
            self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth+1'),f'mobile {index+1}')
            page.screenshot(path=str(CAPTURES/f'{index+1:02}-390.png'),full_page=True)
            if index:
                button=node.locator('.evidence-button');button.scroll_into_view_if_needed();button.click()
                self.assertLessEqual(page.locator('#evidence-dialog').bounding_box()['width'],390)
                page.keyboard.press('Escape')
        page.goto(self.html.as_uri()+'#p3.static')
        self.assertTrue(page.evaluate('MotionDeck.snapshot().static'))
        self.assertEqual(page.evaluate('MotionDeck.snapshot().page'),3)
        self.assertEqual(page.locator('.active [data-hero]').inner_text(),'2')
        self.assertFalse(self.errors)

    def test_demo_can_stop_with_d_while_its_evidence_drawer_is_open(self):
        page=self.context()
        page.evaluate('() => { MotionDeck.startDemo({pace:.2}); }')
        page.wait_for_function('() => MotionDeck.snapshot().demo && MotionDeck.snapshot().evidence',timeout=10000)
        page.keyboard.press('d')
        self.assertFalse(page.evaluate('MotionDeck.snapshot().demo'))


if __name__ == '__main__':
    unittest.main()
