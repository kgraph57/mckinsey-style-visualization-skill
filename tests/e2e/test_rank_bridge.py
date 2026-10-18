"""Paired rankings retain identities while the selected scenario changes."""
from base import InteractiveDeckBrowserTestCase, ROOT
from scripts.build_interactive_deck import build_deck


class RankBridgeTests(InteractiveDeckBrowserTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.artifact = cls.fixture_root / "rank-bridge.interactive.html"
        cls.artifact.write_text(build_deck(ROOT / "examples/interactive-deck/deck.json"), encoding="utf-8")

    def _open(self, width=1280, height=720):
        session = self.open_deck("chromium", "http", artifact=self.artifact,
                                 viewport={"width": width, "height": height}, reduced_motion="reduce")
        session.page.evaluate("location.hash='#slide=4'")
        session.page.wait_for_function("() => !document.querySelector('#idrt-page-4').hidden")
        scene = session.page.locator('#idrt-page-4')
        self.assertEqual(scene.get_attribute('data-visual-layout'), 'rank_bridge')
        return session, scene

    def test_rank_links_update_without_changing_the_baseline(self):
        session, scene = self._open()
        try:
            page = session.page
            bases = page.locator('[id^="idsvg-4-live-shell-LiveBase-"]').evaluate_all("es=>es.map(e=>e.outerHTML)")
            east = page.locator('#idsvg-4-live-shell-LiveMark-east').element_handle()
            for item, metric in (('north', '86'), ('central', '78'), ('east', '73')):
                self.assertEqual(page.locator('#idsvg-4-live-shell-LiveBaseMetric-' + item).text_content(), metric)
            scene.locator('[data-control-value="constrained"]').click()
            self.assertEqual(page.locator('#idsvg-4-live-shell-LiveMetric-east').text_content(), '76')
            self.assertEqual(page.locator('#idsvg-4-live-shell-LiveRank-east').text_content(), '#2')
            self.assertEqual(page.locator('#idsvg-4-live-shell-LiveBridge-east').get_attribute('y1'), '520')
            self.assertEqual(page.locator('#idsvg-4-live-shell-LiveBridge-east').get_attribute('y2'), '410')
            self.assertEqual(page.locator('#idsvg-4-live-shell-LiveBridge-central').get_attribute('y2'), '520')
            self.assertEqual(bases, page.locator('[id^="idsvg-4-live-shell-LiveBase-"]').evaluate_all("es=>es.map(e=>e.outerHTML)"))
            self.assertTrue(page.evaluate("e=>e===document.querySelector('#idsvg-4-live-shell-LiveMark-east')", east))
            self.assertIn('+3', page.locator('#idsvg-4-live-shell-LiveDelta').text_content())
            self.assert_no_automatic_activity(session)
        finally:
            session.close()

    def test_desktop_and_mobile_controls_and_data_are_keyboard_reachable(self):
        for width, height in ((1280, 720), (390, 844)):
            session, scene = self._open(width, height)
            try:
                button = scene.locator('[data-control-value="constrained"]')
                for control in scene.locator('.control-rail button').all():
                    box = control.bounding_box()
                    self.assertIsNotNone(box)
                    self.assertGreaterEqual(box['height'], 44)
                    self.assertGreaterEqual(box['width'], 44)
                button.focus()
                session.page.keyboard.press('Enter')
                self.assertEqual(button.get_attribute('aria-pressed'), 'true')
                self.assertFalse(session.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                self.assertLess(button.bounding_box()['y'] + 44, height)
                summary = scene.locator('.data-details > summary')
                summary.focus()
                session.page.keyboard.press('Enter')
                self.assertTrue(scene.locator('.data-details').evaluate('e=>e.open'))
                self.assertEqual(scene.locator('[data-view-item-id="east"] [data-view-rank]').inner_text(), '2')
                summary.focus()
                session.page.keyboard.press('Enter')
                session.page.wait_for_function("() => !document.querySelector('#idrt-page-4 .data-details').open")
                button.wait_for(state='visible')
                session.page.keyboard.press('Tab')  # Base follows the closed disclosure.
                session.page.keyboard.press('Tab')  # Then the alternate scenario.
                self.assertTrue(button.evaluate('e=>e===document.activeElement'), str({'width': width, 'state': button.evaluate('e=>({activeTag:document.activeElement.tagName,activeId:document.activeElement.id,visibility:getComputedStyle(e).visibility,disabled:e.disabled,open:document.querySelector("#idrt-page-4 .data-details").open})')}))
                if width == 390:
                    name = session.page.locator('#idsvg-4-live-shell-LiveValue-east')
                    self.assertGreaterEqual(name.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)*e.getScreenCTM().a'), 18)
                    rank = session.page.locator('#idsvg-4-live-shell-LiveRank-east')
                    self.assertGreaterEqual(rank.evaluate('e=>parseFloat(getComputedStyle(e).fontSize)*e.getScreenCTM().a'), 18)
                captures = ROOT / 'output/playwright/rank-bridge'
                captures.mkdir(parents=True, exist_ok=True)
                summary.evaluate('e => e.blur()')
                scene.locator('[data-control-value="base"]').click()
                session.page.wait_for_function("() => getComputedStyle(document.querySelector('#idrt-page-4 [data-control-value=base]')).backgroundColor === 'rgb(21, 41, 107)'")
                session.page.screenshot(path=str(captures / f'base-{width}.png'))
                button.click()
                session.page.wait_for_function("() => getComputedStyle(document.querySelector('#idrt-page-4 [data-control-value=constrained]')).backgroundColor === 'rgb(21, 41, 107)'")
                session.page.screenshot(path=str(captures / f'constrained-{width}.png'))
                self.assert_no_automatic_activity(session)
            finally:
                session.close()

    def test_rank_motion_keeps_links_attached_and_stops_at_the_selected_rank(self):
        session = self.open_deck('chromium', 'http', artifact=self.artifact,
                                 viewport={'width': 1280, 'height': 720}, reduced_motion='no-preference')
        try:
            page = session.page
            page.evaluate("location.hash='#slide=4'")
            page.wait_for_function("() => !document.querySelector('#idrt-page-4').hidden")
            scene = page.locator('#idrt-page-4')
            scene.locator('[data-control-value="constrained"]').click()
            page.wait_for_function("() => Number(document.querySelector('#idsvg-4-live-shell-LiveBridge-east').getAttribute('y2')) < 520")
            current = page.locator('#idsvg-4-live-shell-LiveBridge-east').evaluate("e=>({y: Number(e.getAttribute('y2')),label:Number(document.querySelector('#idsvg-4-live-shell-LiveValue-east').getAttribute('y'))})")
            self.assertAlmostEqual(current['y'], current['label'])
            page.wait_for_function("() => document.querySelector('#idsvg-4-live-shell-LiveBridge-east').getAttribute('y2') === '410'")
            scene.locator('[data-control-value="base"]').click()
            scene.locator('[data-control-value="constrained"]').click()
            page.wait_for_function("() => document.querySelector('#idsvg-4-live-shell-LiveBridge-east').getAttribute('y2') === '410'")
            self.assert_no_automatic_activity(session)
        finally:
            session.close()
