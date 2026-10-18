"""The presenter can see the graphic and operate its model in one viewport."""
from pathlib import Path

from base import InteractiveDeckBrowserTestCase, ROOT
from scripts.build_interactive_deck import build_deck


class PresentationSurfaceTests(InteractiveDeckBrowserTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.surface = cls.fixture_root / "presentation-surface.interactive.html"
        cls.surface.write_text(build_deck(ROOT / "examples/interactive-deck/deck.json"), encoding="utf-8")

    def _page(self, page, ordinal):
        page.evaluate("n => { location.hash = '#slide=' + n; }", ordinal)
        page.wait_for_function("n => {const s=document.querySelector('#idrt-page-'+n);return s&&!s.hidden&&s.dataset.runtime==='ready';}", arg=ordinal)
        return page.locator(f"#idrt-page-{ordinal}")

    def test_desktop_graph_and_all_model_controls_fit_without_rail_scroll(self):
        for width, height in ((1280, 720), (1440, 900)):
            session = self.open_deck("chromium", "http", artifact=self.surface, viewport={"width": width, "height": height})
            try:
                for ordinal in (3, 4, 5, 6):
                    with self.subTest(width=width, ordinal=ordinal):
                        scene = self._page(session.page, ordinal)
                        result = scene.evaluate("""s => {const rail=s.querySelector('.semantic-scene');return {
                          stage:s.getBoundingClientRect().bottom,
                          scroll:rail.scrollHeight-rail.clientHeight,
                          controls:[...s.querySelectorAll('.control-rail input,.control-rail select,.control-rail button')].filter(e=>e.getBoundingClientRect().width>0).map(e=>e.getBoundingClientRect().bottom),
                          dataOpen:s.querySelector('.data-details')?.open||false,
                          dataHeight:s.querySelector('.data-details > summary')?.getBoundingClientRect().height||44,
                          h1:s.querySelector('h1').getBoundingClientRect().width
                        };}""")
                        self.assertLessEqual(result["stage"], height)
                        self.assertLessEqual(result["scroll"], 1)
                        self.assertTrue(all(bottom <= height for bottom in result["controls"]))
                        self.assertFalse(result["dataOpen"])
                        self.assertGreaterEqual(result["dataHeight"], 44)
                        self.assertEqual(result["h1"], 1)
                self.assert_no_automatic_activity(session)
            finally:
                session.close()

    def test_rank_comparison_score_contributions_and_gate_update_from_real_state(self):
        session = self.open_deck("chromium", "http", artifact=self.surface, reduced_motion="reduce", viewport={"width": 1280, "height": 720})
        page = session.page
        try:
            scene = self._page(page, 4)
            self.assertEqual(scene.get_attribute("data-visual-layout"), "rank_bridge")
            expected_base = {"north": (1, "86"), "central": (2, "78"), "east": (3, "73")}
            expected_current = {"north": (1, "82"), "central": (3, "64"), "east": (2, "76")}

            def bridge(item):
                return page.locator(f'#idsvg-4-live-shell-LiveBridge-{item}')

            def label(prefix, item):
                return page.locator(f'#idsvg-4-live-shell-{prefix}-{item}').text_content().strip()

            base_y = {}
            for item, (rank, metric) in expected_base.items():
                line = bridge(item)
                base_y[item] = float(line.get_attribute("y1"))
                self.assertEqual(float(line.get_attribute("y2")), base_y[item])
                self.assertLess(float(line.get_attribute("x1")), float(line.get_attribute("x2")))
                self.assertEqual(label("LiveBaseMetric", item).split()[0], metric)
                self.assertEqual(label("LiveMetric", item).split()[0], metric)
                self.assertEqual(label("LiveBaseRank", item), f"#{rank}")
                self.assertEqual(label("LiveRank", item), f"#{rank}")
            self.assertLess(base_y["north"], base_y["central"])
            self.assertLess(base_y["central"], base_y["east"])
            self.assertAlmostEqual(base_y["central"] - base_y["north"], base_y["east"] - base_y["central"], delta=.1)

            scene.locator('[data-control-value="constrained"]').click()
            ranked_y = dict(zip((1, 2, 3), sorted(base_y.values())))
            for item, (rank, metric) in expected_current.items():
                line = bridge(item)
                self.assertEqual(float(line.get_attribute("y1")), base_y[item])
                self.assertEqual(float(line.get_attribute("y2")), ranked_y[rank])
                self.assertEqual(label("LiveBaseMetric", item).split()[0], expected_base[item][1])
                self.assertEqual(label("LiveBaseRank", item), f"#{expected_base[item][0]}")
                self.assertEqual(label("LiveMetric", item).split()[0], metric)
                self.assertEqual(label("LiveRank", item), f"#{rank}")
            self.assertLess(float(bridge("east").get_attribute("y2")), base_y["east"])
            self.assertGreater(float(bridge("central").get_attribute("y2")), base_y["central"])
            self._page(page, 5)
            relation = page.locator('#idsvg-5-live-shell-LiveRelationship').evaluate("e=>e.outerHTML")
            slider = page.locator('#idrt-page-5 input[type=range]')
            slider.press("ArrowLeft")  # 50% adoption gives $1.5m, below the $1.8m gate.
            self.assertEqual(page.locator('#idrt-page-5 [data-decision-status]').inner_text(), "Hold")
            self.assertEqual(page.locator('#idsvg-5-live-shell-LiveRelationship').evaluate("e=>e.outerHTML"), relation)
            self._page(page, 6)
            page.locator('#idrt-page-6 [data-control-value="unavailable"]').click()
            self.assertEqual(page.locator('#idsvg-6-live-shell-LiveScoreValue').text_content(), "54 points")
            self.assertEqual(page.locator('#idsvg-6-live-shell-LiveContribution-manager-capacity').get_attribute("width"), "0.0")
            self.assertEqual(page.locator('#idrt-page-6 [data-decision-status]').inner_text(), "Hold")
            self.assert_no_automatic_activity(session)
        finally:
            session.close()

    def test_phone_has_one_title_and_an_immediately_reachable_primary_control(self):
        session = self.open_deck("chromium", "http", artifact=self.surface, viewport={"width": 390, "height": 844})
        try:
            for ordinal in (5, 6):
                scene = self._page(session.page, ordinal)
                self.assertEqual(scene.locator('.live-layer svg').get_attribute("viewBox"), "60 190 790 440")
                control = scene.locator('.control-rail input[type=range]')
                self.assertLess(control.bounding_box()["y"] + 44, 844)
                self.assertTrue(scene.locator('h1').is_visible())
                primary = scene.locator('.semantic-values dd')
                if primary.count() and primary.first.is_visible():
                    self.assertGreaterEqual(primary.first.evaluate("e => parseFloat(getComputedStyle(e).fontSize)"), 32)
                self.assertFalse(session.page.evaluate("document.documentElement.scrollWidth > innerWidth"))
                control.focus()
                old = control.input_value()
                session.page.keyboard.press("ArrowRight")
                self.assertNotEqual(control.input_value(), old)
            self.assert_no_automatic_activity(session)
        finally:
            session.close()

    def test_evidence_static_toggle_remains_visible_and_reversible(self):
        session = self.open_deck("chromium", "http", artifact=self.surface, viewport={"width": 1280, "height": 720})
        try:
            scene = self._page(session.page, 3)
            toggle = scene.locator('[data-action="static"]')
            self.assertTrue(toggle.is_visible())
            self.assertGreaterEqual(toggle.bounding_box()["height"], 44)
            toggle.click()
            self.assertEqual(scene.get_attribute("data-view-mode"), "static")
            self.assertTrue(toggle.is_visible())
            toggle.click()
            self.assertEqual(scene.get_attribute("data-view-mode"), "live")
        finally:
            session.close()

    def test_desktop_data_disclosure_hides_covered_controls_and_restores_them(self):
        session = self.open_deck("chromium", "http", artifact=self.surface, viewport={"width": 1280, "height": 720})
        try:
            scene = self._page(session.page, 5)
            summary = scene.locator('.data-details > summary')
            slider = scene.locator('.control-rail input[type="range"]')
            summary.focus()
            session.page.keyboard.press("Enter")
            self.assertTrue(scene.locator('.data-details').evaluate("e => e.open"))
            self.assertFalse(slider.is_visible())
            for _ in range(20):
                session.page.keyboard.press("Tab")
                self.assertFalse(session.page.evaluate("Boolean(document.activeElement.closest('.control-rail'))"))
            summary.focus()
            session.page.keyboard.press("Enter")
            self.assertTrue(slider.is_visible())
            slider.focus()
            self.assertTrue(slider.evaluate("e => e === document.activeElement"))
        finally:
            session.close()
