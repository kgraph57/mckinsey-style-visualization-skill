"""Cross-engine behavior and security acceptance for Task 4.

The expected values below are hand calculated from the fixture.  No browser
expectation calls the Python compiler/evaluator that the JavaScript runtime is
meant to match.
"""
from __future__ import annotations

from decimal import Decimal
import json
import re

from playwright.sync_api import expect

from base import (
    ENVELOPE_RE,
    InteractiveDeckBrowserTestCase,
    build_fixture,
    build_numeric_edge_fixture,
    decode_envelope_text,
    replace_envelope_text,
)


SCENE = '[data-slide-id="queue-capacity"]'
RANGE = SCENE + ' input[type="range"]'
PRIMARY_VALUE = SCENE + ' [data-live-value="capacity"]'
DECISION_STATUS = SCENE + ' [data-decision-status]'
DECISION_RECOMMENDATION = SCENE + ' [data-decision-recommendation]'
STATUS = SCENE + ' .scene-status'
POINT = SCENE + ' .live-layer #idsvg-2-live-shell-service-capacity'

EXPECTED_STATES = (
    ("0", "18 cases/wk", "Below demand", "Increase automation before the pilot", 130.0, 441.2),
    ("5", "20 cases/wk", "Below demand", "Increase automation before the pilot", 173.125, 428.0),
    ("10", "22 cases/wk", "Below demand", "Increase automation before the pilot", 216.25, 414.8),
    ("15", "24 cases/wk", "Below demand", "Increase automation before the pilot", 259.375, 401.6),
    ("20", "26 cases/wk", "Below demand", "Increase automation before the pilot", 302.5, 388.4),
    ("25", "28 cases/wk", "Below demand", "Increase automation before the pilot", 345.625, 375.2),
    ("30", "30 cases/wk", "Below demand", "Increase automation before the pilot", 388.75, 362.0),
    ("35", "32 cases/wk", "Ready", "Run a limited queue pilot", 431.875, 348.8),
    ("40", "34 cases/wk", "Ready", "Run a limited queue pilot", 475.0, 335.6),
    ("45", "36 cases/wk", "Ready", "Run a limited queue pilot", 518.125, 322.4),
    ("50", "38 cases/wk", "Ready", "Run a limited queue pilot", 561.25, 309.2),
    ("55", "40 cases/wk", "Ready", "Run a limited queue pilot", 604.375, 296.0),
    ("60", "42 cases/wk", "Ready", "Run a limited queue pilot", 647.5, 282.8),
    ("65", "44 cases/wk", "Ready", "Run a limited queue pilot", 690.625, 269.6),
    ("70", "46 cases/wk", "Ready", "Run a limited queue pilot", 733.75, 256.4),
    ("75", "48 cases/wk", "Ready", "Run a limited queue pilot", 776.875, 243.2),
    ("80", "50 cases/wk", "Ready", "Run a limited queue pilot", 820.0, 230.0),
)


class InteractiveDeckE2ETests(InteractiveDeckBrowserTestCase):
    def _wait_for_runtime(self, page) -> None:
        page.wait_for_function(
            """() => window.InteractiveDeck &&
                typeof window.InteractiveDeck.snapshot === 'function'""",
            timeout=8_000,
        )

    def _activate_scene(self, page) -> None:
        self._wait_for_runtime(page)
        control = page.locator('#idrt-presenter-chrome [data-page-index="2"]')
        control.focus()
        control.click()
        page.wait_for_function(
            """() => {
              const section = document.querySelector('[data-slide-id="queue-capacity"]');
              return section && !section.hidden && section.dataset.runtime === 'ready';
            }""",
            timeout=8_000,
        )
        page.locator(RANGE).wait_for(state="visible")

    def _set_range_sync(
        self,
        page,
        value: str,
        *,
        native_index: str | None = None,
    ) -> dict:
        if native_index is None:
            index = Decimal(value) / Decimal("5")
            if index != index.to_integral_value():
                raise AssertionError(f"fixture value is off the native index grid: {value}")
            native_index = format(index, "f")
        return page.locator(RANGE).evaluate(
            """(input, expected) => {
              const section = input.closest('[data-slide-id]');
              const point = section.querySelector('.live-layer #idsvg-2-live-shell-service-capacity');
              const beforeCx = point.getAttribute('cx');
              const beforeCy = point.getAttribute('cy');
              input.value = expected.nativeIndex;
              input.dispatchEvent(new Event('input', {bubbles: true}));
              return {
                value: input.getAttribute('aria-valuetext') || input.value,
                nativeValue: input.value,
                primary: section.querySelector('[data-live-value="capacity"]').textContent,
                status: section.querySelector('[data-decision-status]').textContent,
                recommendation: section.querySelector('[data-decision-recommendation]').textContent,
                narration: section.querySelector('.scene-status').textContent,
                beforeCx,
                beforeCy,
                cx: point.getAttribute('cx'),
                cy: point.getAttribute('cy')
              };
            }""",
            {"semanticValue": value, "nativeIndex": native_index},
        )

    def _snapshot(self, page) -> dict:
        return page.evaluate("() => window.InteractiveDeck.snapshot()")

    def _scene_value(self, page) -> str:
        return page.locator(RANGE).evaluate(
            "input => input.getAttribute('aria-valuetext') || input.value"
        )

    def _aria_snapshot(self, page) -> str:
        return page.locator(SCENE).aria_snapshot()

    def _assert_public_state_has_no_authored_copy(self, value: object) -> None:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "Below demand",
            "Ready",
            "Increase automation before the pilot",
            "Run a limited queue pilot",
            "Baseline:",
            "Automation +",
            "Weekly capacity",
            "Illustrative method note",
            "Original reference-fixture link",
            "https://",
            "cases/wk",
        ):
            self.assertNotIn(forbidden, serialized)

    def _assert_canonical_numeric_string(self, value: object, *, path: str) -> None:
        self.assertIs(type(value), str, f"{path} must be a string")
        assert isinstance(value, str)
        self.assertRegex(
            value,
            r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$",
            f"{path} must be a canonical decimal string",
        )
        self.assertNotEqual(value, "-0", f"{path} must canonicalize negative zero")

    def _assert_public_snapshot_schema(self, value: object) -> None:
        """Reject authored copy and every field outside the public state contract."""
        self.assertIs(type(value), dict)
        assert isinstance(value, dict)
        self.assertEqual(
            set(value),
            {"currentSlide", "pages", "overlay", "reducedMotion"},
        )
        self.assertIs(type(value["currentSlide"]), int)
        self.assertGreater(value["currentSlide"], 0)
        self.assertIs(type(value["reducedMotion"]), bool)

        pages = value["pages"]
        self.assertIs(type(pages), list)
        self.assertTrue(pages)
        self.assertLessEqual(value["currentSlide"], len(pages))
        for index, page in enumerate(pages, start=1):
            self.assertIs(type(page), dict)
            self.assertEqual(
                set(page),
                {"ordinal", "inputs", "outputs", "outcome", "viewMode", "failed"},
            )
            self.assertIs(type(page["ordinal"]), int)
            self.assertEqual(page["ordinal"], index)
            for collection_name in ("inputs", "outputs"):
                collection = page[collection_name]
                self.assertIs(type(collection), dict)
                for item_id, numeric_value in collection.items():
                    self.assertIs(type(item_id), str)
                    self.assertRegex(item_id, r"^[a-z][a-z0-9_-]{0,63}$")
                    self._assert_canonical_numeric_string(
                        numeric_value,
                        path=f"pages[{index - 1}].{collection_name}.{item_id}",
                    )
            self.assertIn(page["outcome"], (None, "met", "notMet"))
            self.assertIn(page["viewMode"], ("live", "static"))
            self.assertIn(page["failed"], (None, "unavailable"))

        overlay = value["overlay"]
        if overlay is not None:
            self.assertIs(type(overlay), dict)
            self.assertEqual(set(overlay), {"kind", "ordinal", "tab"})
            self.assertEqual(overlay["kind"], "evidence")
            self.assertIs(type(overlay["ordinal"]), int)
            self.assertGreater(overlay["ordinal"], 0)
            self.assertLessEqual(overlay["ordinal"], len(pages))
            self.assertIn(overlay["tab"], ("sources", "assumptions"))
        self._assert_public_state_has_no_authored_copy(value)

    def _assert_public_event_schema(self, event: object) -> None:
        self.assertIs(type(event), dict)
        assert isinstance(event, dict)
        self.assertEqual(set(event), {"type", "detail"})
        self.assertIn(event["type"], ("ready", "state"))
        self._assert_public_snapshot_schema(event["detail"])

    def assert_no_automatic_activity(self, session) -> None:
        monitor = session.monitor()
        for event in monitor["deckEvents"]:
            self._assert_public_event_schema(event)
        for audit in monitor["eventAudits"]:
            self.assertEqual(
                audit,
                {
                    "type": audit["type"],
                    "valid": True,
                    "matchesSnapshot": True,
                    "errors": [],
                },
                "every dispatched public event must be an exact, deeply frozen snapshot",
            )
        super().assert_no_automatic_activity(session)

    def _point_label_geometry(self, page) -> dict:
        return page.locator(POINT).evaluate(
            """point => {
              const label = document.getElementById(
                'idsvg-2-live-shell-LivePointLabel-service-capacity'
              );
              if (!label || label.tagName.toLowerCase() !== 'text') throw new Error('missing point label');
              const labelX = Number(label.getAttribute('x'));
              const labelWidth = Number(label.getAttribute('data-label-width'));
              const anchor = label.getAttribute('text-anchor');
              return {
                pointX: Number(point.getAttribute('cx')),
                pointY: Number(point.getAttribute('cy')),
                radius: Number(point.getAttribute('r')),
                labelX,
                labelY: Number(label.getAttribute('y')),
                labelWidth,
                anchor,
                visualLeft: anchor === 'end' ? labelX - labelWidth : labelX,
                visualRight: anchor === 'end' ? labelX : labelX + labelWidth
              };
            }"""
        )

    def _assert_point_label_is_adjacent_and_bounded(self, geometry: dict) -> None:
        self.assertIn(geometry["anchor"], ("start", "end"))
        self.assertGreaterEqual(geometry["visualLeft"], 80.0 - 0.11)
        self.assertLessEqual(geometry["visualRight"], 1200.0 + 0.11)
        self.assertAlmostEqual(
            abs(geometry["labelX"] - geometry["pointX"]),
            geometry["radius"] + 8.0,
            delta=0.11,
        )
        self.assertGreaterEqual(geometry["labelY"], 226.0 - 0.11)
        self.assertLessEqual(geometry["labelY"], 556.0 + 0.11)
        self.assertLessEqual(abs(geometry["labelY"] - geometry["pointY"]), 30.0)

    def _button(self, page, pattern: str):
        return page.get_by_role("button", name=re.compile(pattern, re.I)).first

    def _navigate_to(self, page, ordinal: int) -> None:
        control = page.locator(
            f'#idrt-presenter-chrome [data-page-index="{ordinal}"]'
        )
        control.focus()
        control.click()
        page.wait_for_function(
            """ordinal => {
              const page = document.querySelector(`#idrt-page-${ordinal}`);
              return page && !page.hidden;
            }""",
            arg=ordinal,
        )

    def _click_visible_native_page_link(self, page, ordinal: int) -> None:
        """Use whichever authored anchor remains visible before or after enhancement."""
        candidates = page.locator(
            f'#idrt-presenter-chrome [data-page-index="{ordinal}"], '
            f'.nojs-page-links a[href="#idrt-page-{ordinal}"]'
        ).all()
        for candidate in candidates:
            if candidate.is_visible():
                candidate.focus()
                candidate.click()
                return
        self.fail(f"no visible native page link for slide {ordinal}")

    def _assert_static_fail_closed(self, session, *, forbidden: tuple[str, ...] = ()) -> None:
        page = session.page
        scene = page.locator(SCENE)
        self.assertTrue(scene.locator(".fallback-layer").is_visible())
        live = scene.locator(".live-layer")
        self.assertTrue(live.is_hidden())
        controls = scene.locator("input, button").all()
        for control in controls:
            if control.is_visible() and control.get_attribute("data-global-control") != "true":
                self.assertTrue(control.is_disabled() or control.get_attribute("aria-disabled") == "true")
        monitor = session.monitor()
        errors, csp_events = self.without_firefox_favicon_browser_noise(
            session,
            [entry for entry in session.observations.consoles if entry[0] == "error"],
            monitor["csp"],
            monitor["transports"],
        )
        diagnostics = errors + [
            entry for entry in session.observations.consoles if entry[0] == "warning"
        ]
        combined = "\n".join(text for _kind, text in diagnostics)
        for secret in forbidden + ("https://example.com", "method-note", "Traceback", " at "):
            self.assertNotIn(secret, combined)
        self.assertEqual(session.observations.page_errors, [])
        self.assertEqual(monitor["transports"], [])
        self.assertEqual(csp_events, [])

    def _assert_only_initial_request(self, session) -> None:
        self.assert_only_document_request(session)
        self.assertEqual(session.observations.downloads, [])

    def test_all_17_states_match_the_hand_calculated_oracle_and_commit_semantics_first(self) -> None:
        """Catches Number math, threshold, formatter, or text-after-geometry drift."""
        session = self.open_deck("chromium", "http")
        try:
            self._activate_scene(session.page)
            for value, output, status, recommendation, x, y in EXPECTED_STATES:
                with self.subTest(value=value):
                    immediate = self._set_range_sync(session.page, value)
                    self.assertEqual(immediate["value"], value)
                    self.assertEqual(immediate["primary"], output)
                    self.assertEqual(immediate["status"], status)
                    self.assertEqual(immediate["recommendation"], recommendation)
                    if x != float(immediate["beforeCx"]):
                        self.assertEqual(immediate["cx"], immediate["beforeCx"])
                    session.page.wait_for_function(
                        """expected => {
                          const point = document.querySelector(
                            '[data-slide-id="queue-capacity"] .live-layer #idsvg-2-live-shell-service-capacity'
                          );
                          return point && Math.abs(Number(point.getAttribute('cx')) - expected.x) < 0.11 &&
                            Math.abs(Number(point.getAttribute('cy')) - expected.y) < 0.11;
                        }""",
                        arg={"x": x, "y": y},
                    )
                    snapshot = self._snapshot(session.page)
                    self.assertEqual(snapshot, {
                        "currentSlide": 2,
                        "pages": [
                            {
                                "ordinal": 1,
                                "inputs": {},
                                "outputs": {},
                                "outcome": None,
                                "viewMode": "static",
                                "failed": None,
                            },
                            {
                                "ordinal": 2,
                                "inputs": {"automation": value},
                                "outputs": {"capacity": output.split()[0]},
                                "outcome": "met" if status == "Ready" else "notMet",
                                "viewMode": "live",
                                "failed": None,
                            },
                        ],
                        "overlay": None,
                        "reducedMotion": False,
                    })
                    self._assert_public_snapshot_schema(snapshot)
            events = session.monitor()["deckEvents"]
            self.assertEqual(events[0]["type"], "ready")
            self.assertEqual(events[-1], {"type": "state", "detail": self._snapshot(session.page)})
            for event in events:
                self._assert_public_event_schema(event)
            leaked_ready = json.loads(json.dumps(events[0]))
            leaked_ready["detail"]["headline"] = (
                "A focused queue pilot can test the operating model in one week"
            )
            with self.assertRaises(AssertionError):
                self._assert_public_event_schema(leaked_ready)
            self.assert_no_automatic_activity(session)
        finally:
            session.close()

    def test_boot_navigation_and_idle_runtime_are_clean_in_both_engines_and_url_modes(self) -> None:
        """Catches a loader that needs a server, leaks a request, or strands page navigation."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                try:
                    self._activate_scene(session.page)
                    api_contract = session.page.evaluate(
                        """() => {
                          const api = window.InteractiveDeck;
                          const descriptor = Object.getOwnPropertyDescriptor(
                            window, 'InteractiveDeck'
                          );
                          const state = api.snapshot();
                          return {
                            ownKeys: Reflect.ownKeys(api).map(key =>
                              typeof key === 'symbol'
                                ? `symbol:${String(key.description || '')}`
                                : key
                            ),
                            symbols: Object.getOwnPropertySymbols(api).length,
                            prototypeOk: Object.getPrototypeOf(api) === Object.prototype ||
                              Object.getPrototypeOf(api) === null,
                            frozen: Object.isFrozen(api),
                            snapshotType: typeof api.snapshot,
                            descriptor: {
                              sameValue: descriptor.value === api,
                              writable: descriptor.writable,
                              configurable: descriptor.configurable,
                              enumerable: descriptor.enumerable
                            },
                            stateFrozen: Object.isFrozen(state),
                            pagesFrozen: Object.isFrozen(state.pages),
                            pageRecordsFrozen: state.pages.every(Object.isFrozen),
                            inputsFrozen: state.pages.every(page =>
                              Object.isFrozen(page.inputs)
                            ),
                            outputsFrozen: state.pages.every(page =>
                              Object.isFrozen(page.outputs)
                            ),
                            overlayFrozen: state.overlay === null ||
                              Object.isFrozen(state.overlay)
                          };
                        }"""
                    )
                    self.assertEqual(
                        api_contract,
                        {
                            "ownKeys": ["snapshot"],
                            "symbols": 0,
                            "prototypeOk": True,
                            "frozen": True,
                            "snapshotType": "function",
                            "descriptor": {
                                "sameValue": True,
                                "writable": False,
                                "configurable": False,
                                "enumerable": True,
                            },
                            "stateFrozen": True,
                            "pagesFrozen": True,
                            "pageRecordsFrozen": True,
                            "inputsFrozen": True,
                            "outputsFrozen": True,
                            "overlayFrozen": True,
                        },
                    )
                    self.assertEqual(session.page.locator("section.slide:not([hidden])").count(), 1)
                    self.assertEqual(
                        session.page.locator(SCENE).get_attribute("data-runtime"),
                        "ready",
                    )
                    session.page.locator("#idrt-heading-2").focus()
                    chrome = session.page.locator("#idrt-presenter-chrome")
                    session.page.wait_for_function(
                        """() => document.querySelector('#idrt-presenter-chrome')
                          ?.classList.contains('is-idle')""",
                        polling=50,
                        timeout=5_000,
                    )
                    self.assertTrue("is-idle" in (chrome.get_attribute("class") or "").split())
                    chrome.locator('[data-page-index="2"]').focus()
                    self.assertFalse("is-idle" in (chrome.get_attribute("class") or "").split())
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_compiler_owned_narration_is_immediately_true_at_decision_checkpoints(self) -> None:
        """Catches reconstructed prose, trimmed pp precision, or delayed status truth."""
        expected = {
            "0": "Automation −20.0 pp; Weekly capacity −8 cases/wk",
            "20": "Baseline: Weekly capacity 26 cases/wk; Below demand",
            "35": "Automation +15.0 pp; Weekly capacity +6 cases/wk; Below demand → Ready",
            "80": "Automation +60.0 pp; Weekly capacity +24 cases/wk; Below demand → Ready",
        }
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http")
                try:
                    self._activate_scene(session.page)
                    for value, narration in expected.items():
                        immediate = self._set_range_sync(session.page, value)
                        self.assertEqual(immediate["narration"], narration)
                    self.assertEqual(session.page.locator(SCENE + " .scene-status").count(), 1)
                    final_narration = expected["80"]
                    session.page.wait_for_function(
                        """expected => {
                          const status = document.querySelector(
                            '[data-slide-id="queue-capacity"] .scene-status'
                          );
                          return status?.getAttribute('aria-live') === 'polite' &&
                            status.textContent === expected;
                        }""",
                        arg=final_narration,
                        polling=25,
                        timeout=3_000,
                    )
                    self.assertEqual(session.page.locator(STATUS).inner_text(), final_narration)
                    self.assertEqual(session.page.locator(STATUS).get_attribute("aria-live"), "polite")
                    self._button(session.page, "reset").click()
                    self.assertEqual(
                        session.page.locator(STATUS).inner_text(),
                        "Reset to baseline: Weekly capacity 26 cases/wk; Below demand",
                    )
                finally:
                    session.close()

    def test_presenter_hud_idle_pointer_touch_and_focus_lifecycle(self) -> None:
        """Catches a permanently hidden HUD or an idle timer hiding focused controls."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                page = session.page
                chrome = page.locator("#idrt-presenter-chrome")
                try:
                    self._wait_for_runtime(page)
                    page.locator("#idrt-heading-1").focus()
                    page.wait_for_function(
                        """() => document.querySelector('#idrt-presenter-chrome')
                          .classList.contains('is-idle')""",
                        polling=50,
                        timeout=5_000,
                    )

                    page.mouse.move(12, 12)
                    page.wait_for_function(
                        """() => !document.querySelector('#idrt-presenter-chrome')
                          .classList.contains('is-idle')"""
                    )
                    page.wait_for_function(
                        """() => document.querySelector('#idrt-presenter-chrome')
                          .classList.contains('is-idle')""",
                        polling=50,
                        timeout=5_000,
                    )

                    page.evaluate(
                        "() => document.dispatchEvent(new Event('touchstart', {bubbles: true}))"
                    )
                    page.wait_for_function(
                        """() => !document.querySelector('#idrt-presenter-chrome')
                          .classList.contains('is-idle')"""
                    )
                    page.wait_for_function(
                        """() => document.querySelector('#idrt-presenter-chrome')
                          .classList.contains('is-idle')""",
                        polling=50,
                        timeout=5_000,
                    )

                    focused = chrome.locator('[data-page-index="1"]')
                    focused.focus()
                    self.assertFalse(
                        "is-idle" in (chrome.get_attribute("class") or "").split()
                    )
                    deadline = page.evaluate("() => performance.now() + 2800")
                    page.wait_for_function(
                        "deadline => performance.now() >= deadline",
                        arg=deadline,
                        polling=50,
                        timeout=4_000,
                    )
                    self.assertTrue(focused.evaluate("node => node === document.activeElement"))
                    self.assertFalse(
                        "is-idle" in (chrome.get_attribute("class") or "").split()
                    )
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_bigint_matches_scale_six_ties_single_rounding_safe_integer_and_display_rounding(self) -> None:
        """Catches binary-float math at the fixed-scale parity boundaries."""
        cases = (
            {
                "name": "positive-half-tie",
                "minimum": Decimal("0"), "maximum": Decimal("0.000002"),
                "step": Decimal("0.000001"), "initial": Decimal("0.000001"),
                "intercept": Decimal("0"), "coefficient": Decimal("0.5"),
                "expected": Decimal("0.000001"), "display_precision": 6,
                "expected_text": "0.000001 units", "threshold": Decimal("0.000001"),
                "threshold_text": "0.000001 units",
            },
            {
                "name": "negative-half-tie",
                "minimum": Decimal("0"), "maximum": Decimal("0.000002"),
                "step": Decimal("0.000001"), "initial": Decimal("0.000001"),
                "intercept": Decimal("0"), "coefficient": Decimal("-0.5"),
                "expected": Decimal("-0.000001"), "display_precision": 6,
                "expected_text": "−0.000001 units", "threshold": Decimal("0.000000"),
                "threshold_text": "0.000000 units",
            },
            {
                "name": "single-rounding",
                "minimum": Decimal("0"), "maximum": Decimal("0.000003"),
                "step": Decimal("0.000001"), "initial": Decimal("0.000002"),
                "intercept": Decimal("0"), "coefficient": Decimal("0.333333"),
                "expected": Decimal("0.000001"), "display_precision": 6,
                "expected_text": "0.000001 units", "threshold": Decimal("0.000001"),
                "threshold_text": "0.000001 units",
            },
            {
                "name": "scaled-above-safe-integer",
                "minimum": Decimal("9007199254.740992"),
                "maximum": Decimal("9007199254.740994"),
                "step": Decimal("0.000001"),
                "initial": Decimal("9007199254.740993"),
                "intercept": Decimal("0"), "coefficient": Decimal("1"),
                "expected": Decimal("9007199254.740993"), "display_precision": 6,
                "expected_text": "9,007,199,254.740993 units",
                "threshold": Decimal("9007199254.740993"),
                "threshold_text": "9,007,199,254.740993 units",
            },
            {
                "name": "display-half-away",
                "minimum": Decimal("0"), "maximum": Decimal("2"),
                "step": Decimal("1"), "initial": Decimal("1"),
                "intercept": Decimal("1.000"), "coefficient": Decimal("0.005"),
                "expected": Decimal("1.005"), "display_precision": 2,
                "expected_text": "1.01 units", "threshold": Decimal("1.005"),
                "threshold_text": "1.005 units",
            },
            {
                "name": "independent-view-domain-precision",
                "minimum": Decimal("0"), "maximum": Decimal("2"),
                "step": Decimal("1"), "initial": Decimal("1"),
                "intercept": Decimal("0"), "coefficient": Decimal("1"),
                "expected": Decimal("1"), "display_precision": 0,
                "expected_text": "1 units", "threshold": Decimal("1"),
                "threshold_text": "1 units", "view_y_max": Decimal("2.5"),
            },
        )
        artifacts = []
        for case in cases:
            kwargs = dict(case)
            name = kwargs.pop("name")
            path = build_numeric_edge_fixture(
                self.fixture_root / "numeric" / name,
                output_name=f"{name}.interactive.html",
                **kwargs,
            )
            if name == "independent-view-domain-precision":
                payload, _raw = decode_envelope_text(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["slides"][1]["scene"]["scale"], 0)
                self.assertEqual(
                    payload["slides"][1]["scene"]["view"]["yDomain"],
                    ["0", "2.5"],
                )
            artifacts.append((name, path, case))
        output_axis_path = build_fixture(
            self.fixture_root / "output-axis-x",
            output_axis="x",
            output_name="output-axis-x.interactive.html",
        )

        for engine in ("chromium", "firefox"):
            for name, path, case in artifacts:
                with self.subTest(engine=engine, case=name):
                    session = self.open_deck(engine, "http", artifact=path)
                    try:
                        self._activate_scene(session.page)
                        self.assertEqual(
                            session.page.locator(PRIMARY_VALUE).inner_text(),
                            case["expected_text"],
                        )
                        expected_status = "Ready" if case["expected"] >= case["threshold"] else "Below demand"
                        self.assertEqual(session.page.locator(DECISION_STATUS).inner_text(), expected_status)
                        scene_snapshot = self._snapshot(session.page)["pages"][1]
                        self.assertEqual(scene_snapshot["inputs"]["automation"], str(case["initial"]))
                        self.assertEqual(scene_snapshot["outputs"]["capacity"], str(case["expected"]))
                        self.assertEqual(
                            scene_snapshot["outcome"],
                            "met" if expected_status == "Ready" else "notMet",
                        )
                        if name == "independent-view-domain-precision":
                            point = session.page.locator(
                                SCENE + " .live-layer circle[id]"
                            )
                            self.assertAlmostEqual(
                                float(point.get_attribute("cx")),
                                475.0,
                                delta=0.11,
                            )
                            self.assertAlmostEqual(
                                float(point.get_attribute("cy")),
                                428.0,
                                delta=0.11,
                            )
                        if name == "scaled-above-safe-integer":
                            control = session.page.locator(RANGE)
                            self.assertEqual(
                                control.evaluate(
                                    """input => ({
                                      min: input.min, max: input.max, step: input.step,
                                      value: input.value,
                                      semantic: input.getAttribute('aria-valuetext')
                                    })"""
                                ),
                                {
                                    "min": "0",
                                    "max": "2",
                                    "step": "1",
                                    "value": "1",
                                    "semantic": "9007199254.740993",
                                },
                            )
                            control.focus()
                            session.page.keyboard.press("ArrowRight")
                            self.assertEqual(control.input_value(), "2")
                            self.assertEqual(
                                control.get_attribute("aria-valuetext"),
                                "9007199254.740994",
                            )
                            self.assertEqual(
                                session.page.locator(PRIMARY_VALUE).inner_text(),
                                "9,007,199,254.740994 units",
                            )
                            self.assertEqual(
                                self._snapshot(session.page)["pages"][1]["inputs"],
                                {"automation": "9007199254.740994"},
                            )
                            session.page.keyboard.press("ArrowLeft")
                            self.assertEqual(control.input_value(), "1")
                            box = control.bounding_box()
                            assert box is not None
                            session.page.mouse.click(
                                box["x"] + box["width"] - 1,
                                box["y"] + box["height"] / 2,
                            )
                            session.page.wait_for_function(
                                """() => document.querySelector(
                                  '[data-slide-id="queue-capacity"] input[type="range"]'
                                )?.getAttribute('aria-valuetext') === '9007199254.740994'"""
                            )
                            self.assertEqual(control.input_value(), "2")
                            self.assertEqual(
                                self._snapshot(session.page)["pages"][1]["inputs"],
                                {"automation": "9007199254.740994"},
                            )
                        self.assert_no_automatic_activity(session)
                    finally:
                        session.close()

            with self.subTest(engine=engine, case="output-axis-x-threshold"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=output_axis_path,
                )
                try:
                    self._activate_scene(session.page)
                    threshold = session.page.locator(
                        SCENE + " .live-layer #idsvg-2-live-shell-LiveChartBand line[stroke-dasharray]"
                    )
                    geometry = threshold.evaluate(
                        """line => ({
                          x1: Number(line.getAttribute('x1')),
                          x2: Number(line.getAttribute('x2')),
                          y1: Number(line.getAttribute('y1')),
                          y2: Number(line.getAttribute('y2'))
                        })"""
                    )
                    self.assertAlmostEqual(geometry["x1"], 571.6, delta=0.11)
                    self.assertAlmostEqual(geometry["x2"], 571.6, delta=0.11)
                    self.assertAlmostEqual(geometry["y1"], 230.0, delta=0.11)
                    self.assertAlmostEqual(geometry["y2"], 560.0, delta=0.11)
                    line_box = threshold.bounding_box()
                    assert line_box is not None
                    self.assertLessEqual(line_box["width"], 1.1)
                    self.assertGreater(line_box["height"], 0)
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_javascript_disabled_keeps_both_semantic_fallbacks_and_native_links(self) -> None:
        """Catches CSS or generated markup that makes the no-script artifact unreadable."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode, java_script_enabled=False)
                try:
                    sections = session.page.locator("section.slide")
                    self.assertEqual(sections.count(), 2)
                    self.assertTrue(sections.nth(0).is_visible())
                    self.assertTrue(sections.nth(1).is_visible())
                    self.assertIn("focused queue pilot", sections.nth(0).locator("h1").inner_text())
                    self.assertIn("35% automation", sections.nth(1).locator("h1").inner_text())
                    sections.nth(0).locator('a[href="#idrt-page-2"]').click()
                    self.assertEqual(session.page.evaluate("() => location.hash"), "#idrt-page-2")
                    self._assert_only_initial_request(session)
                    self.assertEqual(session.observations.page_errors, [])
                    self.assert_clean_console_and_csp(session)
                finally:
                    session.close()

    def test_zero_automatic_network_has_one_exact_firefox_browser_chrome_exception(self) -> None:
        """Locks the narrow Firefox favicon-noise exception without hiding page errors."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                try:
                    self._wait_for_runtime(session.page)
                    monitor = session.monitor()
                    errors = [
                        entry
                        for entry in session.observations.consoles
                        if entry[0] == "error"
                    ]
                    is_firefox_http = engine == "firefox" and mode == "http"
                    self.assertEqual(
                        session.page.locator(
                            'head link[href], script[src], img[src], source[src], '
                            'audio[src], video[src], iframe[src], object[data], embed[src]'
                        ).count(),
                        0,
                    )
                    self.assertEqual(monitor["transports"], [])
                    filtered_errors, filtered_csp = self.without_firefox_favicon_browser_noise(
                        session,
                        errors,
                        monitor["csp"],
                        monitor["transports"],
                    )
                    self.assertEqual(
                        (filtered_errors, filtered_csp),
                        ([], []),
                    )
                    if is_firefox_http:
                        # The exact browser-chrome item may be removed beside
                        # a runtime failure, but that other failure must remain.
                        self.assertEqual(
                            self.without_firefox_favicon_browser_noise(
                                session,
                                errors + [("error", "unrelated page failure")],
                                monitor["csp"],
                                monitor["transports"],
                            ),
                            ([("error", "unrelated page failure")], []),
                        )
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_boot_deep_link_restores_one_atomic_scene_and_mode_without_history_growth(self) -> None:
        """Catches restore-after-paint, partial control restore, or pushState growth."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(
                    engine,
                    mode,
                    fragment="#slide=2&automation=35&mode=static",
                )
                page = session.page
                try:
                    self._wait_for_runtime(page)
                    page.wait_for_function(
                        """() => {
                          const scene = document.querySelector('[data-slide-id="queue-capacity"]');
                          const input = scene?.querySelector('input[type=range]');
                          return scene && !scene.hidden &&
                            input?.getAttribute('aria-valuetext') === '20' && input.disabled;
                        }""",
                        timeout=8_000,
                    )
                    snapshot = self._snapshot(page)
                    self.assertEqual(snapshot["currentSlide"], 2)
                    self.assertEqual(snapshot["pages"][1]["inputs"], {"automation": "35"})
                    self.assertEqual(snapshot["pages"][1]["outputs"]["capacity"], "32")
                    self.assertEqual(snapshot["pages"][1]["viewMode"], "static")
                    self.assertEqual(page.locator("#idrt-control-value-2-1").inner_text(), "20%")
                    length = page.evaluate("() => history.length")
                    page.locator("#idrt-static-toggle-2").click()
                    self.assertEqual(self._scene_value(page), "35")
                    self.assertEqual(page.locator("#idrt-control-value-2-1").inner_text(), "35%")
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "32 cases/wk")
                    self.assertEqual(page.evaluate("() => location.hash"), "#slide=2&automation=35")
                    self.assertEqual(page.evaluate("() => history.length"), length)
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_external_hash_restore_emits_one_state_only_after_a_successful_render(self) -> None:
        """Catches pre-render, duplicate, no-op, invalid, or failed restore success events."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                page = session.page
                try:
                    self._activate_scene(page)
                    page.evaluate(
                        """() => {
                          window.__E2E_HASH_COMMITS__ = [];
                          document.addEventListener('deck:state', event => {
                            const scene = document.querySelector(
                              '[data-slide-id="queue-capacity"]'
                            );
                            const input = scene.querySelector('input[type="range"]');
                            window.__E2E_HASH_COMMITS__.push({
                              event: {type: 'state', detail: event.detail},
                              currentSlide: event.detail.currentSlide,
                              semanticValue: input.getAttribute('aria-valuetext'),
                              outputText: scene.querySelector(
                                '[data-live-value="capacity"]'
                              ).textContent,
                              runtime: scene.getAttribute('data-runtime'),
                              visible: !scene.hidden,
                              hash: window.location.hash
                            });
                          });
                          window.__E2E_MONITOR__.deckEvents.length = 0;
                          window.__E2E_MONITOR__.hashes.length = 0;
                        }"""
                    )

                    page.evaluate(
                        "() => { location.hash = '#slide=2&automation=35'; }"
                    )
                    page.wait_for_function(
                        "() => window.__E2E_HASH_COMMITS__.length === 1"
                    )
                    commits = page.evaluate("() => window.__E2E_HASH_COMMITS__")
                    self.assertEqual(len(commits), 1)
                    commit = commits[0]
                    self._assert_public_event_schema(commit["event"])
                    self.assertEqual(commit["currentSlide"], 2)
                    self.assertEqual(
                        commit["event"]["detail"]["pages"][1]["inputs"],
                        {"automation": "35"},
                    )
                    self.assertEqual(commit["semanticValue"], "35")
                    self.assertEqual(commit["outputText"], "32 cases/wk")
                    self.assertEqual(commit["runtime"], "ready")
                    self.assertTrue(commit["visible"])
                    self.assertEqual(commit["hash"], "#slide=2&automation=35")
                    self.assertEqual(
                        [
                            event["type"]
                            for event in session.monitor()["deckEvents"]
                        ],
                        ["state"],
                    )

                    # A valid hash that serializes to the current state is a no-op.
                    page.evaluate(
                        """() => {
                          window.__E2E_HASH_COMMITS__.length = 0;
                          window.__E2E_MONITOR__.deckEvents.length = 0;
                          window.dispatchEvent(new Event('hashchange'));
                        }"""
                    )
                    self.assertEqual(page.evaluate("() => window.__E2E_HASH_COMMITS__"), [])
                    self.assertEqual(session.monitor()["deckEvents"], [])

                    # A successful restore within the current page updates the
                    # state without stealing focus from its visible control.
                    active_control = page.locator(RANGE)
                    active_control.focus()
                    self.assertTrue(
                        active_control.evaluate("node => node === document.activeElement")
                    )
                    page.evaluate(
                        """() => {
                          window.__E2E_HASH_COMMITS__.length = 0;
                          window.__E2E_MONITOR__.deckEvents.length = 0;
                          window.__E2E_MONITOR__.hashes.length = 0;
                          location.hash = '#slide=2&automation=40';
                        }"""
                    )
                    page.wait_for_function(
                        "() => window.__E2E_HASH_COMMITS__.length === 1"
                    )
                    self.assertEqual(self._scene_value(page), "40")
                    self.assertTrue(
                        active_control.evaluate("node => node === document.activeElement")
                    )
                    self.assertEqual(
                        [event["type"] for event in session.monitor()["deckEvents"]],
                        ["state"],
                    )

                    # Invalid fragments may restore the safe baseline, but must
                    # never claim that the external state was accepted.
                    page.evaluate(
                        """() => {
                          window.__E2E_HASH_COMMITS__.length = 0;
                          window.__E2E_MONITOR__.deckEvents.length = 0;
                          window.__E2E_MONITOR__.hashes.length = 0;
                          location.hash = '#slide=2&automation=40&automation=35';
                        }"""
                    )
                    page.wait_for_function(
                        """() => window.__E2E_MONITOR__.hashes.length > 0 &&
                          document.querySelector(
                            '[data-slide-id="queue-capacity"] input[type="range"]'
                          )?.getAttribute('aria-valuetext') === '20'"""
                    )
                    self.assertEqual(page.evaluate("() => window.__E2E_HASH_COMMITS__"), [])
                    self.assertEqual(session.monitor()["deckEvents"], [])

                    # A render exception fails closed and emits no misleading
                    # success event for the requested hash.
                    session.set_fault("geometry")
                    page.evaluate(
                        """() => {
                          window.__E2E_HASH_COMMITS__.length = 0;
                          window.__E2E_MONITOR__.deckEvents.length = 0;
                          location.hash = '#slide=2&automation=40';
                        }"""
                    )
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="queue-capacity"]'
                        )?.getAttribute('data-runtime') === 'failed'"""
                    )
                    self.assertEqual(page.evaluate("() => window.__E2E_HASH_COMMITS__"), [])
                    self.assertEqual(session.monitor()["deckEvents"], [])
                    session.set_fault(None)
                    self._assert_static_fail_closed(session)
                    self._assert_only_initial_request(session)
                finally:
                    session.close()

    def test_malformed_scene_value_restores_the_identified_scene_atomically(self) -> None:
        """Catches a malformed control value discarding its still-valid slide target."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                page = session.page
                try:
                    self._wait_for_runtime(page)
                    page.evaluate(
                        """() => {
                          window.__E2E_MONITOR__.deckEvents.length = 0;
                          window.__E2E_MONITOR__.hashes.length = 0;
                          location.hash = '#slide=2&automation=%';
                        }"""
                    )
                    page.wait_for_function(
                        """() => window.__E2E_MONITOR__.hashes.includes(
                          '#slide=2&automation=%'
                        )"""
                    )
                    snapshot = self._snapshot(page)
                    self.assertEqual(snapshot["currentSlide"], 2)
                    self.assertEqual(
                        snapshot["pages"][1]["inputs"],
                        {"automation": "20"},
                    )
                    self.assertEqual(snapshot["pages"][1]["viewMode"], "live")
                    self.assertTrue(page.locator(SCENE).is_visible())
                    self.assertEqual(self._scene_value(page), "20")
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "26 cases/wk")
                    self.assertEqual(session.monitor()["deckEvents"], [])
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_fragment_matrix_clamps_valid_values_and_rejects_invalid_state_atomically(self) -> None:
        """Covers the complete v1 fragment grammar, boundaries, and atomic fallback."""
        cases = (
            ("#2", 2, "20", True),
            ("#99", 2, "20", True),
            ("#slide=2", 2, "20", True),
            ("#slide=2&automation=32.5", 2, "35", True),
            ("#slide=2&automation=-10", 2, "0", True),
            ("#slide=2&automation=99", 2, "80", True),
            ("#slide=2&automation=35&automation=40", 2, "20", False),
            ("#slide=2&unknown=35", 2, "20", False),
            ("#slide=2&mode=overview", 2, "20", False),
            ("#slide=2&automation=not-a-number", 2, "20", False),
            ("#slide=not-a-slide&automation=35", 1, None, False),
            ("#demo", 1, None, False),
        )
        ten_parameters = "#" + "&".join(
            ["slide=2", "automation=35"] + [f"unknown{index}=x" for index in range(8)]
        )
        eleven_parameters = ten_parameters + "&unknown10=x"
        raw_4096 = "slide=2&unknown=" + "x" * (4096 - len("slide=2&unknown="))
        raw_4097 = raw_4096 + "x"
        boundary_cases = (
            (ten_parameters, 2, "20"),
            (eleven_parameters, 1, None),
            ("#" + raw_4096, 2, "20"),
            ("#" + raw_4097, 1, None),
        )

        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                page = session.page
                try:
                    self._wait_for_runtime(page)

                    def restore(fragment: str) -> None:
                        self._navigate_to(page, 1)
                        page.evaluate(
                            """() => {
                              window.__E2E_MONITOR__.deckEvents.length = 0;
                              window.__E2E_MONITOR__.hashes.length = 0;
                            }"""
                        )
                        page.evaluate(
                            "fragment => { window.location.hash = fragment; }",
                            fragment,
                        )
                        page.wait_for_function(
                            "() => window.__E2E_MONITOR__.hashes.length === 1",
                            timeout=5_000,
                        )

                    for fragment, slide, value, valid in cases:
                        restore(fragment)
                        snapshot = self._snapshot(page)
                        with self.subTest(
                            engine=engine,
                            mode=mode,
                            fragment=fragment,
                        ):
                            self.assertEqual(snapshot["currentSlide"], slide)
                            self.assertEqual(
                                page.locator(f"#idrt-page-{slide}").is_visible(),
                                True,
                            )
                            if value is not None:
                                self.assertEqual(snapshot["pages"][1]["inputs"], {"automation": value})
                                self.assertEqual(self._scene_value(page), value)
                                self.assertEqual(snapshot["pages"][1]["viewMode"], "live")
                            events = session.monitor()["deckEvents"]
                            if valid:
                                self.assertEqual([event["type"] for event in events], ["state"])
                                self._assert_public_event_schema(events[0])
                                self.assertEqual(events[0]["detail"], snapshot)
                            else:
                                self.assertEqual(events, [])

                    for fragment, slide, value in boundary_cases:
                        restore(fragment)
                        snapshot = self._snapshot(page)
                        with self.subTest(
                            engine=engine,
                            mode=mode,
                            boundary=len(fragment) - 1,
                            parameters=fragment.count("&") + 1,
                        ):
                            self.assertEqual(snapshot["currentSlide"], slide)
                            if value is not None:
                                self.assertEqual(snapshot["pages"][1]["inputs"], {"automation": value})
                                self.assertEqual(self._scene_value(page), value)
                            self.assertEqual(session.monitor()["deckEvents"], [])

                    # A legacy page-only fragment is a complete state restore,
                    # not a request to reuse the target page's last visited
                    # controls or view mode. Exercise both accepted legacy
                    # spellings after deliberately dirtying page 2.
                    for fragment in ("#2", "#idrt-page-2"):
                        self._navigate_to(page, 2)
                        self._set_range_sync(page, "40")
                        page.locator("#idrt-static-toggle-2").click()
                        dirty = self._snapshot(page)
                        self.assertEqual(dirty["pages"][1]["inputs"], {"automation": "40"})
                        self.assertEqual(dirty["pages"][1]["viewMode"], "static")

                        self._navigate_to(page, 1)
                        page.evaluate(
                            """() => {
                              window.__E2E_MONITOR__.deckEvents.length = 0;
                              window.__E2E_MONITOR__.hashes.length = 0;
                              window.__E2E_MONITOR__.eventAudits.length = 0;
                            }"""
                        )
                        page.evaluate(
                            "fragment => { window.location.hash = fragment; }",
                            fragment,
                        )
                        page.wait_for_function(
                            """() => window.__E2E_MONITOR__.hashes.length === 1 &&
                              window.__E2E_MONITOR__.deckEvents.length === 1 &&
                              window.InteractiveDeck.snapshot().currentSlide === 2 &&
                              document.querySelector(
                                '[data-slide-id="queue-capacity"] input[type="range"]'
                              )?.getAttribute('aria-valuetext') === '20'""",
                            timeout=5_000,
                        )
                        page.evaluate(
                            """() => new Promise(resolve => requestAnimationFrame(
                              () => requestAnimationFrame(resolve)
                            ))"""
                        )
                        restored = self._snapshot(page)
                        with self.subTest(
                            engine=engine,
                            mode=mode,
                            legacy_revisit=fragment,
                        ):
                            self.assertEqual(restored["currentSlide"], 2)
                            self.assertEqual(
                                restored["pages"][1]["inputs"], {"automation": "20"}
                            )
                            self.assertEqual(restored["pages"][1]["viewMode"], "live")
                            self.assertEqual(self._scene_value(page), "20")
                            self.assertEqual(
                                page.locator(PRIMARY_VALUE).inner_text(), "26 cases/wk"
                            )
                            events = session.monitor()["deckEvents"]
                            self.assertEqual([event["type"] for event in events], ["state"])
                            self._assert_public_event_schema(events[0])
                            self.assertEqual(events[0]["detail"], restored)

                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_controls_fragments_focus_evidence_static_reset_and_revisit_share_one_state(self) -> None:
        """Catches split reducers, partial fragment restores, focus leaks, or reset/revisit loss."""
        japanese_artifact = build_fixture(
            self.fixture_root / "japanese-toggle",
            lang="ja",
            output_name="japanese-toggle.interactive.html",
        )
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                page = session.page
                try:
                    self._activate_scene(page)
                    history_length = page.evaluate("() => history.length")
                    self.assertEqual(
                        page.locator("#idrt-static-toggle-2").inner_text(),
                        "View static conclusion",
                    )

                    page.locator(RANGE).focus()
                    page.keyboard.press("ArrowRight")
                    self.assertEqual(self._scene_value(page), "25")
                    self.assertTrue(page.locator(SCENE).is_visible())
                    self.assertEqual(page.evaluate("() => history.length"), history_length)

                    page.evaluate("() => { location.hash = '#slide=2&automation=32.5'; }")
                    page.wait_for_function(
                        """() => document.querySelector('[data-slide-id="queue-capacity"] input[type="range"]')
                          ?.getAttribute('aria-valuetext') === '35'"""
                    )
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "32 cases/wk")
                    self.assertEqual(page.locator(DECISION_STATUS).inner_text(), "Ready")

                    page.evaluate(
                        "() => { location.hash = '#slide=2&automation=40&automation=35'; }"
                    )
                    page.wait_for_function(
                        """() => document.querySelector('[data-slide-id="queue-capacity"] input[type="range"]')
                          ?.getAttribute('aria-valuetext') === '20'"""
                    )
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "26 cases/wk")

                    self._set_range_sync(page, "40")
                    static_toggle = page.locator('#idrt-static-toggle-2')
                    live_tree = self._aria_snapshot(page)
                    self.assertNotIn("Weekly capacity: 20%, 26 cases/wk", live_tree)
                    self.assertIn("34 cases/wk", live_tree)
                    self.assertIn("Ready", live_tree)
                    self.assertIn(
                        "Automation +20.0 pp; Weekly capacity +8 cases/wk; Below demand → Ready",
                        live_tree,
                    )
                    static_toggle.click()
                    self.assertEqual(static_toggle.inner_text(), "Return to live view")
                    self.assertTrue(static_toggle.evaluate("node => node === document.activeElement"))
                    self.assertEqual(self._scene_value(page), "20")
                    self.assertEqual(
                        page.locator("#idrt-control-value-2-1").inner_text(),
                        "20%",
                    )
                    self.assertTrue(page.locator(SCENE + " .fallback-layer").is_visible())
                    self.assertTrue(page.locator(SCENE + " .live-layer").is_hidden())
                    self.assertTrue(page.locator(RANGE).is_disabled())
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "26 cases/wk")
                    self.assertEqual(page.locator(DECISION_STATUS).inner_text(), "Below demand")
                    self.assertEqual(self._snapshot(page)["pages"][1]["inputs"], {"automation": "40"})
                    static_tree = self._aria_snapshot(page)
                    self.assertIn("Weekly capacity: 20%, 26 cases/wk", static_tree)
                    self.assertNotIn("Automation +20.0 pp", static_tree)
                    self.assertRegex(page.evaluate("() => location.hash"), r"(?:^|&)mode=static(?:&|$)")
                    static_toggle.click()
                    self.assertEqual(static_toggle.inner_text(), "View static conclusion")
                    self.assertTrue(static_toggle.evaluate("node => node === document.activeElement"))
                    self.assertEqual(self._scene_value(page), "40")
                    self.assertEqual(
                        page.locator("#idrt-control-value-2-1").inner_text(),
                        # Control precision follows min/step (0/5), not the
                        # model coefficient's scale. Narration still keeps pp precision.
                        "40%",
                    )
                    self.assertTrue(page.locator(SCENE + " .live-layer").is_visible())
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "34 cases/wk")
                    self.assertEqual(page.locator(DECISION_STATUS).inner_text(), "Ready")

                    evidence = self._button(page, "evidence")
                    self.assertEqual(evidence.get_attribute("aria-expanded"), "false")
                    evidence.focus()
                    evidence.click()
                    dialog = page.get_by_role("dialog")
                    self.assertTrue(dialog.is_visible())
                    self.assertEqual(evidence.get_attribute("aria-expanded"), "true")
                    self.assertEqual(dialog.get_attribute("aria-modal"), "true")
                    labelled_by = dialog.get_attribute("aria-labelledby")
                    self.assertTrue(labelled_by)
                    self.assertEqual(page.locator("#" + labelled_by).count(), 1)
                    self.assertTrue(page.locator("#" + labelled_by).is_visible())
                    self.assertTrue(page.locator("#" + labelled_by).inner_text().strip())
                    self.assertTrue(page.evaluate("() => document.querySelector('#idrt-deck-pages').inert"))
                    focus_order = dialog.evaluate(
                        """dialog => [...dialog.querySelectorAll(
                          'button:not([disabled]),a[href]:not([hidden]),' +
                          '[tabindex]:not([tabindex="-1"]):not([hidden])'
                        )].filter(node => !node.closest('[hidden]')).map((node, index) => {
                          node.setAttribute('data-e2e-focus-order', String(index));
                          return String(index);
                        })"""
                    )
                    self.assertGreaterEqual(len(focus_order), 3)
                    self.assertEqual(
                        page.evaluate(
                            "() => document.activeElement?.getAttribute('data-e2e-focus-order')"
                        ),
                        focus_order[0],
                    )
                    page.keyboard.press("Shift+Tab")
                    self.assertEqual(
                        page.evaluate(
                            "() => document.activeElement?.getAttribute('data-e2e-focus-order')"
                        ),
                        focus_order[-1],
                    )
                    page.keyboard.press("Tab")
                    self.assertEqual(
                        page.evaluate(
                            "() => document.activeElement?.getAttribute('data-e2e-focus-order')"
                        ),
                        focus_order[0],
                    )
                    sources_tab = dialog.locator('[data-evidence-tab="sources"]')
                    assumptions_tab = dialog.locator('[data-evidence-tab="assumptions"]')
                    sources_tab.focus()
                    page.keyboard.press("ArrowLeft")
                    self.assertEqual(assumptions_tab.get_attribute("aria-selected"), "true")
                    page.keyboard.press("End")
                    self.assertEqual(assumptions_tab.get_attribute("aria-selected"), "true")
                    page.keyboard.press("Home")
                    self.assertEqual(sources_tab.get_attribute("aria-selected"), "true")
                    page.keyboard.press("ArrowRight")
                    self.assertEqual(assumptions_tab.get_attribute("aria-selected"), "true")
                    self.assertEqual(assumptions_tab.get_attribute("tabindex"), "0")
                    self.assertTrue(dialog.locator('[data-evidence-panel="sources"]').is_hidden())
                    self.assertTrue(dialog.locator('[data-evidence-panel="assumptions"]').is_visible())
                    page.keyboard.press("Home")
                    self.assertEqual(sources_tab.get_attribute("aria-selected"), "true")
                    source_link = dialog.locator(
                        'a[data-slide-ordinal="2"][data-source-id="method-note"]'
                    )
                    source_link.focus()
                    page.keyboard.press("Escape")
                    self.assertTrue(dialog.is_hidden())
                    self.assertEqual(evidence.get_attribute("aria-expanded"), "false")
                    self.assertTrue(evidence.evaluate("node => node === document.activeElement"))

                    # External source navigation has its own browser focus
                    # lifecycle.  Reopen the dialog so Escape focus return is
                    # tested independently from the intentionally blocked tab.
                    evidence.click()
                    self.assertTrue(dialog.is_visible())
                    self.assertEqual(evidence.get_attribute("aria-expanded"), "true")
                    source = dialog.locator(
                        'a[data-slide-ordinal="2"][data-source-id="method-note"]'
                    )
                    self.assertEqual(source.get_attribute("href"), "https://example.com/method")
                    self.assertEqual(source.get_attribute("target"), "_blank")
                    self.assertEqual(source.get_attribute("rel"), "noopener noreferrer")
                    self.assertEqual(source.get_attribute("referrerpolicy"), "no-referrer")
                    source.focus()
                    with session.context.expect_event(
                        "requestfailed",
                        predicate=lambda request: request.url == "https://example.com/method",
                        timeout=5_000,
                    ):
                        page.keyboard.press("Enter")
                    self.assertIn(
                        "https://example.com/method",
                        session.observations.blocked_requests,
                    )
                    self.assertEqual(
                        set(session.observations.blocked_requests),
                        {"https://example.com/method"},
                    )
                    self.assertEqual(session.monitor()["scriptedClicks"], [])
                    self.assertEqual(session.monitor()["popups"], [])
                    self.assertEqual(session.monitor()["forms"], [])
                    self.assertEqual(session.observations.downloads, [])
                    dialog.locator('[data-action="evidence-close"]').click()
                    self.assertTrue(dialog.is_hidden())
                    self.assertEqual(evidence.get_attribute("aria-expanded"), "false")

                    self._navigate_to(page, 1)
                    self.assertTrue(page.locator('[data-slide-id="slide-001"]').is_visible())
                    self._navigate_to(page, 2)
                    self.assertEqual(self._scene_value(page), "40")
                    self._button(page, "reset").click()
                    self.assertEqual(self._scene_value(page), "20")
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "26 cases/wk")
                    # The two explicit location.hash assignments above add
                    # entries by browser definition. Internal state changes
                    # must not add any more.
                    self.assertEqual(page.evaluate("() => history.length"), history_length + 2)
                    self.assertEqual(session.monitor()["transports"], [])
                    self.assertEqual(session.observations.page_errors, [])
                    self.assert_clean_console_and_csp(session)
                finally:
                    session.close()

        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine, locale="ja"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=japanese_artifact,
                )
                try:
                    self._activate_scene(session.page)
                    toggle = session.page.locator("#idrt-static-toggle-2")
                    self.assertEqual(toggle.inner_text(), "静的な結論を表示")
                    toggle.click()
                    self.assertEqual(toggle.inner_text(), "動的表示に戻る")
                    toggle.click()
                    self.assertEqual(toggle.inner_text(), "静的な結論を表示")
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_navigation_guards_focus_page_strip_background_zones_and_swipe_thresholds(self) -> None:
        """Catches slide shortcuts stealing native control keys or ambiguous gestures."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                page = session.page
                try:
                    self._activate_scene(page)
                    current = page.locator('#idrt-presenter-chrome [aria-current="page"]')
                    self.assertEqual(current.count(), 1)
                    self.assertEqual(current.get_attribute("href"), "#idrt-page-2")

                    guard_cases = page.evaluate(
                        """() => {
                          const add = (id, tagName, configure) => {
                            const node = document.createElement(tagName || 'div');
                            node.id = id;
                            // Programmatic focus remains possible at -1, but
                            // production's explicit tabindex guard is false.
                            node.tabIndex = -1;
                            node.textContent = 'guard';
                            configure(node);
                            return node;
                          };
                          const descriptors = [
                            ['editable-empty', 'div', node =>
                              node.setAttribute('contenteditable', ''), null],
                            ['editable-plaintext', 'div', node =>
                              node.setAttribute('contenteditable', 'plaintext-only'), null],
                            ['tabindex-only', 'div', node => { node.tabIndex = 0; }, null],
                            ['native-button', 'button', () => {}, null],
                            ['native-link', 'a', node => node.setAttribute('href', '#guarded'), null],
                            ['native-textfield', 'input', node => node.setAttribute('type', 'text'), null],
                            ['role-multi-token', 'div', node =>
                              node.setAttribute('role', 'unknown slider'), null],
                            ['nested-grid-row', 'div', node =>
                              node.setAttribute('role', 'row'), 'grid']
                          ];
                          for (const role of [
                            'slider', 'spinbutton', 'textbox', 'combobox', 'listbox',
                            'tree', 'grid', 'menu', 'radiogroup', 'tablist',
                            'progressbar', 'separator', 'application'
                          ]) {
                            descriptors.push(['role-' + role, 'div', node => {
                              node.setAttribute('role', role);
                              if (role === 'slider' || role === 'spinbutton') {
                                node.setAttribute('aria-valuemin', '0');
                                node.setAttribute('aria-valuemax', '10');
                                node.setAttribute('aria-valuenow', '5');
                              }
                            }, null]);
                          }
                          const cases = [];
                          for (const [ordinal, key] of [[1, 'ArrowRight'], [2, 'ArrowLeft']]) {
                            const host = document.createElement('div');
                            host.className = 'e2e-keyboard-guard-host';
                            host.style.cssText =
                              'position:absolute;left:8px;top:8px;width:2px;height:2px;overflow:hidden';
                            for (const [name, tagName, configure, ancestorRole] of descriptors) {
                              const id = `e2e-${name}-page-${ordinal}`;
                              const guarded = add(id, tagName, configure);
                              if (ancestorRole) {
                                const ancestor = document.createElement('div');
                                ancestor.setAttribute('role', ancestorRole);
                                ancestor.append(guarded);
                                host.append(ancestor);
                              } else {
                                host.append(guarded);
                              }
                              cases.push({
                                id, ordinal, key,
                                expectedTabIndex: name === 'tabindex-only' ? 0 : -1
                              });
                            }
                            document.querySelector(`#idrt-page-${ordinal} .frame`).append(host);
                          }
                          return cases;
                        }"""
                    )
                    for guard_case in guard_cases:
                        self._navigate_to(page, guard_case["ordinal"])
                        guarded = page.locator("#" + guard_case["id"])
                        guarded.focus()
                        self.assertEqual(
                            page.evaluate("() => document.activeElement?.id"),
                            guard_case["id"],
                        )
                        self.assertEqual(
                            guarded.evaluate("node => node.tabIndex"),
                            guard_case["expectedTabIndex"],
                        )
                        page.keyboard.press(guard_case["key"])
                        target = page.locator(
                            f'#idrt-page-{guard_case["ordinal"]}'
                        )
                        stayed = target.is_visible()
                        active_id = page.evaluate("() => document.activeElement?.id")
                        if not stayed:
                            self._navigate_to(page, guard_case["ordinal"])
                        with self.subTest(
                            engine=engine,
                            guard=guard_case["id"],
                            key=guard_case["key"],
                        ):
                            self.assertTrue(stayed)
                            self.assertEqual(
                                active_id,
                                guard_case["id"],
                            )
                    page.locator(".e2e-keyboard-guard-host").evaluate_all(
                        "nodes => nodes.forEach(node => node.remove())"
                    )
                    self._navigate_to(page, 2)

                    slider = page.locator(RANGE)
                    slider.focus()
                    page.keyboard.press("ArrowLeft")
                    self.assertEqual(self._scene_value(page), "15")
                    self.assertTrue(page.locator(SCENE).is_visible())

                    page.locator("#idrt-heading-2").focus()
                    page.keyboard.press("ArrowLeft")
                    page.wait_for_function("() => !document.querySelector('#idrt-page-1').hidden")
                    self.assertEqual(page.evaluate("() => document.activeElement?.id"), "idrt-heading-1")
                    page.keyboard.press("ArrowRight")
                    page.wait_for_function("() => !document.querySelector('#idrt-page-2').hidden")
                    self.assertEqual(page.evaluate("() => document.activeElement?.id"), "idrt-heading-2")

                    page.locator('#idrt-presenter-chrome [data-page-index="1"]').click()
                    self.assertTrue(
                        page.locator('#idrt-presenter-chrome [data-page-index="1"]').evaluate(
                            "node => node === document.activeElement"
                        )
                    )
                    first_frame = page.locator("#idrt-page-1 .frame")
                    bounds = first_frame.bounding_box()
                    assert bounds is not None
                    page.mouse.click(bounds["x"] + bounds["width"] * 0.9, bounds["y"] + bounds["height"] * 0.5)
                    page.wait_for_function("() => !document.querySelector('#idrt-page-2').hidden")

                    # A mostly vertical gesture is ambiguous and must not navigate.
                    self.assertEqual(
                        page.locator("#idrt-page-2 .frame").evaluate(
                            """frame => {
                              const box = frame.getBoundingClientRect();
                              const emit = (type, x, y) => frame.dispatchEvent(new PointerEvent(type, {
                                bubbles: true, pointerId: 9, isPrimary: true, pointerType: 'touch',
                                clientX: box.left + x, clientY: box.top + y
                              }));
                              emit('pointerdown', box.width * .8, box.height * .2);
                              emit('pointerup', box.width * .7, box.height * .8);
                              return document.querySelector('#idrt-page-2').hidden;
                            }"""
                        ),
                        False,
                    )

                    page.locator(RANGE).scroll_into_view_if_needed()

                    # Crossing an interactive control invalidates the whole
                    # gesture, even when both endpoints are on the frame.
                    self.assertEqual(
                        page.locator("#idrt-page-2 .frame").evaluate(
                            """frame => {
                              const input = document.querySelector(
                                '[data-slide-id="queue-capacity"] input[type="range"]'
                              );
                              const box = frame.getBoundingClientRect();
                              const inputBox = input.getBoundingClientRect();
                              const emit = (type, x, y) => frame.dispatchEvent(new PointerEvent(type, {
                                bubbles: true, pointerId: 11, isPrimary: true, pointerType: 'touch',
                                clientX: x, clientY: y
                              }));
                              emit('pointerdown', box.left + box.width * .2, box.top + box.height * .5);
                              emit('pointermove', inputBox.left + inputBox.width * .5, inputBox.top + inputBox.height * .5);
                              emit('pointerup', box.left + box.width * .8, box.top + box.height * .5);
                              return document.querySelector('#idrt-page-2').hidden;
                            }"""
                        ),
                        False,
                    )

                    # A release whose hit-tested endpoint is a control is not
                    # a page swipe, even if the event bubbles through frame.
                    self.assertEqual(
                        page.locator("#idrt-page-2 .frame").evaluate(
                            """frame => {
                              const input = document.querySelector(
                                '[data-slide-id="queue-capacity"] input[type="range"]'
                              );
                              const box = frame.getBoundingClientRect();
                              const inputBox = input.getBoundingClientRect();
                              const y = inputBox.top + inputBox.height * .5;
                              const emit = (type, x) => frame.dispatchEvent(new PointerEvent(type, {
                                bubbles: true, pointerId: 12, isPrimary: true, pointerType: 'touch',
                                clientX: x, clientY: y
                              }));
                              emit('pointerdown', box.left + 8);
                              emit('pointerup', inputBox.right - 4);
                              return document.querySelector('#idrt-page-2').hidden;
                            }"""
                        ),
                        False,
                    )

                    # A second contact anywhere in the document cancels the
                    # first contact's candidate, even outside the frame.
                    self.assertEqual(
                        page.locator("#idrt-page-2 .frame").evaluate(
                            """frame => {
                              const box = frame.getBoundingClientRect();
                              const emit = (target, type, id, x, y) => target.dispatchEvent(
                                new PointerEvent(type, {
                                  bubbles: true, pointerId: id, isPrimary: id === 13,
                                  pointerType: 'touch', clientX: box.left + x,
                                  clientY: box.top + y
                                })
                              );
                              emit(frame, 'pointerdown', 13, box.width * .25, box.height * .5);
                              emit(document.body, 'pointerdown', 14, 4, 4);
                              emit(frame, 'pointerup', 13, box.width * .75, box.height * .52);
                              emit(document.body, 'pointerup', 14, 4, 4);
                              return document.querySelector('#idrt-page-2').hidden;
                            }"""
                        ),
                        False,
                    )

                    page.evaluate(
                        "() => { window.__E2E_MONITOR__.deckEvents.length = 0; }"
                    )

                    # One pixel below the threshold is not a swipe.
                    self.assertFalse(
                        page.locator("#idrt-page-2 .frame").evaluate(
                            """frame => {
                              const box = frame.getBoundingClientRect();
                              const x = box.left + 300;
                              const y = box.top + 200;
                              const emit = (type, dx, dy) => frame.dispatchEvent(
                                new PointerEvent(type, {
                                  bubbles: true, pointerId: 20, isPrimary: true,
                                  pointerType: 'touch', clientX: x + dx,
                                  clientY: y + dy
                                })
                              );
                              emit('pointerdown', 0, 0);
                              emit('pointerup', 47, 0);
                              return document.querySelector('#idrt-page-2').hidden;
                            }"""
                        )
                    )
                    self.assertEqual(session.monitor()["deckEvents"], [])

                    # Cancellation clears the candidate even if a later
                    # pointerup would otherwise exceed the threshold.
                    self.assertFalse(
                        page.locator("#idrt-page-2 .frame").evaluate(
                            """frame => {
                              const box = frame.getBoundingClientRect();
                              const x = box.left + 300;
                              const y = box.top + 200;
                              const emit = (type, dx) => frame.dispatchEvent(
                                new PointerEvent(type, {
                                  bubbles: true, pointerId: 21, isPrimary: true,
                                  pointerType: 'touch', clientX: x + dx,
                                  clientY: y
                                })
                              );
                              emit('pointerdown', 0);
                              emit('pointercancel', 0);
                              emit('pointerup', 120);
                              return document.querySelector('#idrt-page-2').hidden;
                            }"""
                        )
                    )
                    self.assertEqual(session.monitor()["deckEvents"], [])

                    # Exactly 48px at the 1.5 horizontal-dominance boundary
                    # qualifies.  The click synthesized after a consumed touch
                    # must not dispatch a second navigation.
                    immediate_click_result = page.locator(
                        "#idrt-page-2 .frame"
                    ).evaluate(
                        """frame => {
                          const box = frame.getBoundingClientRect();
                          const x = box.left + 300;
                          const y = box.top + 200;
                          const emit = (type, dx, dy) => frame.dispatchEvent(
                            new PointerEvent(type, {
                              bubbles: true, pointerId: 22, isPrimary: true,
                              pointerType: 'touch', clientX: x + dx,
                              clientY: y + dy
                            })
                          );
                          emit('pointerdown', 0, 0);
                          emit('pointerup', 48, 32);
                          const activeFrame = document.querySelector(
                            '#idrt-page-1 .frame'
                          );
                          const activeBox = activeFrame.getBoundingClientRect();
                          activeFrame.dispatchEvent(new MouseEvent('click', {
                            bubbles: true, cancelable: true,
                            clientX: activeBox.left + activeBox.width * .9,
                            clientY: activeBox.top + activeBox.height * .5
                          }));
                          return {
                            firstVisible: !document.querySelector('#idrt-page-1').hidden,
                            secondHidden: document.querySelector('#idrt-page-2').hidden
                          };
                        }"""
                    )
                    self.assertEqual(
                        immediate_click_result,
                        {"firstVisible": True, "secondHidden": True},
                    )
                    page.wait_for_function("() => !document.querySelector('#idrt-page-1').hidden")
                    consumed_events = session.monitor()["deckEvents"]
                    self.assertEqual(
                        [event["type"] for event in consumed_events],
                        ["state"],
                    )
                    self._assert_public_event_schema(consumed_events[0])
                    self.assertEqual(consumed_events[0]["detail"]["currentSlide"], 1)

                    # Positive control: once the 500ms suppression window has
                    # elapsed, the same active-frame right-edge click must work.
                    click_deadline = page.evaluate("() => performance.now() + 550")
                    page.wait_for_function(
                        "deadline => performance.now() >= deadline",
                        arg=click_deadline,
                        timeout=2_000,
                    )
                    page.locator("#idrt-page-1 .frame").evaluate(
                        """frame => {
                          const box = frame.getBoundingClientRect();
                          frame.dispatchEvent(new MouseEvent('click', {
                            bubbles: true, cancelable: true,
                            clientX: box.left + box.width * .9,
                            clientY: box.top + box.height * .5
                          }));
                        }"""
                    )
                    page.wait_for_function(
                        "() => !document.querySelector('#idrt-page-2').hidden"
                    )
                    click_events = session.monitor()["deckEvents"]
                    self.assertEqual(
                        [event["detail"]["currentSlide"] for event in click_events],
                        [1, 2],
                    )
                    for event in click_events:
                        self._assert_public_event_schema(event)
                finally:
                    session.close()

    def test_background_keyboard_shortcuts_tab_order_zones_and_overlay_page_change(self) -> None:
        """Covers bounded presenter keys, inert pages, click zones, and current-only reset."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode)
                page = session.page
                try:
                    self._wait_for_runtime(page)

                    def assert_page(ordinal: int) -> None:
                        self.assertEqual(self._snapshot(page)["currentSlide"], ordinal)
                        self.assertTrue(page.locator(f"#idrt-page-{ordinal}").is_visible())
                        current = page.locator(
                            '#idrt-presenter-chrome [aria-current="page"]'
                        )
                        self.assertEqual(current.count(), 1)
                        self.assertEqual(
                            current.get_attribute("data-page-index"),
                            str(ordinal),
                        )

                    page.locator("#idrt-heading-1").focus()
                    for key in ("ArrowLeft", "PageUp", "Home"):
                        page.keyboard.press(key)
                        assert_page(1)
                    page.keyboard.press("ArrowRight")
                    assert_page(2)
                    for key in ("ArrowRight", "PageDown", "End"):
                        page.keyboard.press(key)
                        assert_page(2)
                    page.keyboard.press("PageUp")
                    assert_page(1)
                    page.keyboard.press("Space")
                    assert_page(2)
                    page.keyboard.press("Home")
                    assert_page(1)
                    page.keyboard.press("End")
                    assert_page(2)

                    # The hidden slide is inert and cannot enter sequential Tab order.
                    self._navigate_to(page, 1)
                    self.assertTrue(page.locator("#idrt-page-2").evaluate("node => node.inert"))
                    page.locator("#idrt-heading-1").focus()
                    tab_stops = []
                    for _ in range(12):
                        page.keyboard.press("Tab")
                        tab_stops.append(
                            page.evaluate(
                                "() => document.activeElement?.closest('.slide')?.id || null"
                            )
                        )
                    self.assertNotIn("idrt-page-2", tab_stops)

                    # Left/right 15% are navigation zones; the middle 70% is inert.
                    self._navigate_to(page, 1)
                    frame = page.locator("#idrt-page-1 .frame")
                    bounds = frame.bounding_box()
                    assert bounds is not None
                    page.mouse.click(
                        bounds["x"] + bounds["width"] * 0.50,
                        bounds["y"] + bounds["height"] * 0.50,
                    )
                    assert_page(1)
                    page.mouse.click(
                        bounds["x"] + bounds["width"] * 0.90,
                        bounds["y"] + bounds["height"] * 0.50,
                    )
                    page.wait_for_function("() => !document.querySelector('#idrt-page-2').hidden")
                    assert_page(2)
                    frame = page.locator("#idrt-page-2 .frame")
                    bounds = frame.bounding_box()
                    assert bounds is not None
                    page.mouse.click(
                        bounds["x"] + bounds["width"] * 0.50,
                        bounds["y"] + bounds["height"] * 0.50,
                    )
                    assert_page(2)
                    page.mouse.click(
                        bounds["x"] + bounds["width"] * 0.10,
                        bounds["y"] + bounds["height"] * 0.50,
                    )
                    page.wait_for_function("() => !document.querySelector('#idrt-page-1').hidden")
                    assert_page(1)

                    # Presenter chrome is deliberately inert while the modal is
                    # open. A reachable external page change must still close it
                    # and move focus to the newly active page heading.
                    self._navigate_to(page, 2)
                    opener = page.locator("#idrt-evidence-open-2")
                    opener.focus()
                    opener.click()
                    dialog = page.get_by_role("dialog")
                    self.assertTrue(dialog.is_visible())
                    page.evaluate("() => { window.location.hash = '#slide=1'; }")
                    page.wait_for_function("() => !document.querySelector('#idrt-page-1').hidden")
                    self.assertTrue(dialog.is_hidden())
                    self.assertIsNone(self._snapshot(page)["overlay"])
                    self.assertEqual(opener.get_attribute("aria-expanded"), "false")
                    self.assertEqual(
                        page.evaluate("() => document.activeElement?.id"),
                        "idrt-heading-1",
                    )
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

        multi_scene_artifact = build_fixture(
            self.fixture_root / "keyboard-current-only-reset",
            second_interactive=True,
            output_name="keyboard-current-only-reset.interactive.html",
        )
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine, shortcut="current-only-reset"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=multi_scene_artifact,
                )
                page = session.page
                try:
                    self._wait_for_runtime(page)
                    self._navigate_to(page, 2)
                    page.locator("#idrt-page-2 input[type=range]").evaluate(
                        """input => {
                          input.value = '8';
                          input.dispatchEvent(new Event('input', {bubbles: true}));
                        }"""
                    )
                    self._navigate_to(page, 3)
                    page.locator("#idrt-page-3 input[type=range]").evaluate(
                        """input => {
                          input.value = '7';
                          input.dispatchEvent(new Event('input', {bubbles: true}));
                        }"""
                    )
                    page.locator("#idrt-heading-3").focus()
                    page.keyboard.press("Alt+r")
                    snapshot = self._snapshot(page)
                    self.assertEqual(snapshot["currentSlide"], 3)
                    self.assertEqual(snapshot["pages"][1]["inputs"], {"automation": "40"})
                    self.assertEqual(snapshot["pages"][2]["inputs"], {"automation": "20"})
                    before_reserved = snapshot
                    for key in ("Alt+o", "Alt+d", "Alt+f", "Alt+h"):
                        page.keyboard.press(key)
                        self.assertEqual(self._snapshot(page), before_reserved)
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_animation_cancels_from_current_geometry_and_reduced_motion_has_no_travel(self) -> None:
        """Catches stale RAF completion or semantic interpolation."""
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine, motion="normal"):
                session = self.open_deck(engine, "http")
                page = session.page
                try:
                    self._activate_scene(page)
                    motion_truth = page.locator(RANGE).evaluate(
                        """input => new Promise(resolve => {
                          const section = input.closest('[data-slide-id]');
                          const point = section.querySelector(
                            '.live-layer #idsvg-2-live-shell-service-capacity'
                          );
                          const invariantNodes = [
                            section.querySelector('h1'),
                            section.querySelector('.semantic-source'),
                            ...section.querySelectorAll('.live-layer line'),
                            ...section.querySelectorAll(
                              '.live-layer text:not([id*="LivePointLabel"])'
                            )
                          ];
                          const rect = node => {
                            const box = node.getBoundingClientRect();
                            return [box.x, box.y, box.width, box.height];
                          };
                          window.__E2E_MOTION_INVARIANTS__ = {
                            nodes: invariantNodes,
                            rects: invariantNodes.map(rect)
                          };
                          input.value = '16';
                          input.dispatchEvent(new Event('input', {bubbles: true}));
                          const started = performance.now();
                          const samples = [];
                          const sample = now => {
                            samples.push({
                              elapsed: now - started,
                              cx: Number(point.getAttribute('cx')),
                              primary: section.querySelector(
                                '[data-live-value="capacity"]'
                              ).textContent,
                              value: section.querySelector(
                                '#idrt-control-value-2-1'
                              ).textContent,
                              status: section.querySelector(
                                '[data-decision-status]'
                              ).textContent,
                              narration: section.querySelector('.scene-status').textContent
                            });
                            if (now - started >= 120) resolve(samples);
                            else requestAnimationFrame(sample);
                          };
                          requestAnimationFrame(sample);
                        })"""
                    )
                    midpoint = motion_truth[-1]
                    self.assertGreaterEqual(midpoint["elapsed"], 100)
                    self.assertLess(midpoint["elapsed"], 240)
                    self.assertGreater(midpoint["cx"], 302.5)
                    self.assertLess(midpoint["cx"], 820.0)
                    for sample in motion_truth:
                        self.assertEqual(sample["primary"], "50 cases/wk")
                        self.assertEqual(sample["value"], "80%")
                        self.assertEqual(sample["status"], "Ready")
                        self.assertEqual(
                            sample["narration"],
                            "Automation +60.0 pp; Weekly capacity +24 cases/wk; Below demand → Ready",
                        )
                    page.wait_for_function(
                        """() => Math.abs(Number(document.querySelector(
                          '[data-slide-id="queue-capacity"] .live-layer '
                          + '#idsvg-2-live-shell-service-capacity'
                        ).getAttribute('cx')) - 820) < .11""",
                        timeout=3_000,
                    )
                    quiet_deadline = page.evaluate("() => performance.now() + 80")
                    page.wait_for_function(
                        "deadline => performance.now() >= deadline",
                        arg=quiet_deadline,
                        timeout=1_000,
                    )
                    invariant_result = page.evaluate(
                        """() => {
                          const section = document.querySelector(
                            '[data-slide-id="queue-capacity"]'
                          );
                          const current = [
                            section.querySelector('h1'),
                            section.querySelector('.semantic-source'),
                            ...section.querySelectorAll('.live-layer line'),
                            ...section.querySelectorAll(
                              '.live-layer text:not([id*="LivePointLabel"])'
                            )
                          ];
                          const rect = node => {
                            const box = node.getBoundingClientRect();
                            return [box.x, box.y, box.width, box.height];
                          };
                          const saved = window.__E2E_MOTION_INVARIANTS__;
                          return {
                            sameNodes: current.length === saved.nodes.length &&
                              current.every((node, index) => node === saved.nodes[index]),
                            maxRectDelta: Math.max(0, ...current.flatMap((node, index) =>
                              rect(node).map((value, part) =>
                                Math.abs(value - saved.rects[index][part])
                              )
                            )),
                            cx: Number(section.querySelector(
                              '.live-layer #idsvg-2-live-shell-service-capacity'
                            ).getAttribute('cx')),
                            primary: section.querySelector(
                              '[data-live-value="capacity"]'
                            ).textContent
                          };
                        }"""
                    )
                    self.assertTrue(invariant_result["sameNodes"])
                    self.assertLessEqual(invariant_result["maxRectDelta"], 0.25)
                    self.assertAlmostEqual(invariant_result["cx"], 820.0, delta=0.11)
                    self.assertEqual(invariant_result["primary"], "50 cases/wk")
                    self._button(page, "reset").click()
                    page.wait_for_function(
                        """() => Math.abs(Number(document.querySelector(
                          '[data-slide-id="queue-capacity"] .live-layer '
                          + '#idsvg-2-live-shell-service-capacity'
                        ).getAttribute('cx')) - 302.5) < .11""",
                        timeout=3_000,
                    )
                    handoff = page.locator(RANGE).evaluate(
                        """input => new Promise(resolve => {
                          const section = input.closest('[data-slide-id]');
                          const point = section.querySelector(
                            '.live-layer #idsvg-2-live-shell-service-capacity'
                          );
                          input.value = '16';
                          input.dispatchEvent(new Event('input', {bubbles: true}));
                          requestAnimationFrame(() => requestAnimationFrame(() => {
                            const before = Number(point.getAttribute('cx'));
                            const began = performance.now();
                            input.value = '0';
                            input.dispatchEvent(new Event('input', {bubbles: true}));
                            const immediate = Number(point.getAttribute('cx'));
                            const primary = section.querySelector('[data-live-value="capacity"]').textContent;
                            const status = section.querySelector('[data-decision-status]').textContent;
                            requestAnimationFrame(now => {
                              const fraction = Math.max(0, Math.min(1, (now - began) / 240));
                              const eased = 1 - Math.pow(1 - fraction, 3);
                              resolve({
                                before,
                                immediate,
                                afterFirstFrame: Number(point.getAttribute('cx')),
                                expectedFromRendered: before + (130 - before) * eased,
                                expectedFromStaleTarget: 820 + (130 - 820) * eased,
                                primary,
                                status
                              });
                            });
                          }));
                        })"""
                    )
                    self.assertGreater(handoff["before"], 302.5)
                    self.assertLess(handoff["before"], 820.0)
                    self.assertEqual(handoff["primary"], "18 cases/wk")
                    self.assertEqual(handoff["status"], "Below demand")
                    self.assertAlmostEqual(handoff["immediate"], handoff["before"], delta=0.11)
                    current_error = abs(
                        handoff["afterFirstFrame"] - handoff["expectedFromRendered"]
                    )
                    stale_error = abs(
                        handoff["afterFirstFrame"] - handoff["expectedFromStaleTarget"]
                    )
                    self.assertLess(current_error, stale_error)
                    self.assertLess(handoff["afterFirstFrame"], handoff["before"])
                    self.assertNotAlmostEqual(handoff["afterFirstFrame"], 820.0, delta=0.11)
                    page.emulate_media(reduced_motion="reduce")
                    page.wait_for_function(
                        """() => Math.abs(Number(document.querySelector(
                          '[data-slide-id="queue-capacity"] .live-layer #idsvg-2-live-shell-service-capacity'
                        ).getAttribute('cx')) - 130) < .11"""
                    )
                    self.assertAlmostEqual(float(page.locator(POINT).get_attribute("cx")), 130.0, delta=0.11)
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "18 cases/wk")
                    self.assertTrue(self._snapshot(page)["reducedMotion"])
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

            with self.subTest(engine=engine, motion="reduced"):
                session = self.open_deck(engine, "http", reduced_motion="reduce")
                page = session.page
                try:
                    self._activate_scene(page)
                    geometry_before = self._point_label_geometry(page)
                    self._assert_point_label_is_adjacent_and_bounded(geometry_before)
                    self._set_range_sync(page, "35")
                    geometry_after = self._point_label_geometry(page)
                    self._assert_point_label_is_adjacent_and_bounded(geometry_after)
                    self.assertNotEqual(geometry_after["labelX"], geometry_before["labelX"])
                    self.assertNotEqual(geometry_after["labelY"], geometry_before["labelY"])
                    immediate = self._set_range_sync(page, "80")
                    self.assertEqual(immediate["primary"], "50 cases/wk")
                    self.assertAlmostEqual(float(immediate["cx"]), 820.0, delta=0.11)
                    self.assertAlmostEqual(float(immediate["cy"]), 230.0, delta=0.11)
                    self._assert_point_label_is_adjacent_and_bounded(
                        self._point_label_geometry(page)
                    )
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_portrait_zoom_equivalent_and_print_keep_one_truthful_fallback_per_page(self) -> None:
        """Catches undersized compact UI, horizontal clipping, or current-state printing."""
        for engine in ("chromium", "firefox"):
            for viewport in (
                {"width": 1280, "height": 720},
                {"width": 1280, "height": 900},
                {"width": 390, "height": 844},
                {"width": 844, "height": 390},
                {"width": 1440, "height": 900},
            ):
                with self.subTest(engine=engine, chrome_clearance=viewport):
                    session = self.open_deck(
                        engine,
                        "http",
                        viewport=viewport,
                    )
                    try:
                        page = session.page
                        self._wait_for_runtime(page)
                        initial_geometry = page.evaluate(
                            """() => {
                              const rect = node => {
                                const box = node.getBoundingClientRect();
                                return {
                                  left: box.left, right: box.right,
                                  top: box.top, bottom: box.bottom,
                                  width: box.width, height: box.height
                                };
                              };
                              const intersect = (a, b) => {
                                const left = Math.max(a.left, b.left);
                                const right = Math.min(a.right, b.right);
                                const top = Math.max(a.top, b.top);
                                const bottom = Math.min(a.bottom, b.bottom);
                                return right > left && bottom > top ? {
                                  left, right, top, bottom,
                                  width: right - left, height: bottom - top
                                } : null;
                              };
                              const viewport = {
                                left: 0, top: 0, right: innerWidth, bottom: innerHeight
                              };
                              const chromeNode = document.querySelector('#idrt-presenter-chrome');
                              const chrome = rect(chromeNode);
                              const links = [
                                chromeNode.querySelector('[data-nav-action="previous"]'),
                                ...chromeNode.querySelectorAll('[data-page-index]'),
                                chromeNode.querySelector('[data-nav-action="next"]')
                              ];
                              return {
                                scrollY,
                                deckScrollTop: document.querySelector('#idrt-deck-pages').scrollTop,
                                opacity: getComputedStyle(chromeNode).opacity,
                                chrome,
                                chromeVisible: intersect(chrome, viewport),
                                links: links.map(node => ({
                                  raw: rect(node),
                                  visible: intersect(rect(node), viewport)
                                }))
                              };
                            }"""
                        )
                        self.assertEqual(initial_geometry["scrollY"], 0)
                        self.assertEqual(initial_geometry["deckScrollTop"], 0)
                        self.assertEqual(initial_geometry["opacity"], "1")
                        self.assertIsNotNone(initial_geometry["chromeVisible"])
                        self.assertAlmostEqual(
                            initial_geometry["chrome"]["width"],
                            initial_geometry["chromeVisible"]["width"],
                            delta=0.5,
                        )
                        self.assertAlmostEqual(
                            initial_geometry["chrome"]["height"],
                            initial_geometry["chromeVisible"]["height"],
                            delta=0.5,
                        )
                        for link in initial_geometry["links"]:
                            self.assertIsNotNone(link["visible"], initial_geometry)
                            self.assertAlmostEqual(
                                link["raw"]["width"], link["visible"]["width"], delta=0.5
                            )
                            self.assertAlmostEqual(
                                link["raw"]["height"], link["visible"]["height"], delta=0.5
                            )

                        page.locator(
                            '#idrt-presenter-chrome [data-page-index="2"]'
                        ).dispatch_event("click")
                        page.wait_for_function(
                            "() => !document.querySelector('#idrt-page-2').hidden"
                        )
                        geometry = page.evaluate(
                            """() => {
                              const rect = node => {
                                const box = node.getBoundingClientRect();
                                return {
                                  left: box.left, right: box.right,
                                  top: box.top, bottom: box.bottom,
                                  width: box.width, height: box.height
                                };
                              };
                              const intersect = (a, b) => {
                                const left = Math.max(a.left, b.left);
                                const right = Math.min(a.right, b.right);
                                const top = Math.max(a.top, b.top);
                                const bottom = Math.min(a.bottom, b.bottom);
                                return right > left && bottom > top ? {
                                  left, right, top, bottom,
                                  width: right - left, height: bottom - top
                                } : null;
                              };
                              const viewport = {
                                left: 0, top: 0, right: innerWidth, bottom: innerHeight
                              };
                              const deck = rect(document.querySelector('#idrt-deck-pages'));
                              const deckClip = intersect(deck, viewport);
                              const chrome = intersect(
                                rect(document.querySelector('#idrt-presenter-chrome')),
                                viewport
                              );
                              const scene = document.querySelector('[data-slide-id="queue-capacity"]');
                              const nodes = {
                                headline: scene.querySelector('h1'),
                                status: scene.querySelector('.scene-status'),
                                controls: scene.querySelector('.control-rail'),
                                source: scene.querySelector('.semantic-source')
                              };
                              const visible = node => deckClip ? intersect(rect(node), deckClip) : null;
                              const overlaps = (a, b) => Boolean(a && b &&
                                a.left < b.right && a.right > b.left &&
                                a.top < b.bottom && a.bottom > b.top);
                              return {
                                scrollY,
                                deckScrollTop: document.querySelector('#idrt-deck-pages').scrollTop,
                                chrome,
                                content: Object.fromEntries(Object.entries(nodes).map(
                                  ([key, node]) => [key, visible(node)]
                                )),
                                overlaps: Object.fromEntries(Object.entries(nodes).map(
                                  ([key, node]) => [key, overlaps(chrome, visible(node))]
                                ))
                              };
                            }"""
                        )
                        self.assertEqual(geometry["scrollY"], 0)
                        self.assertEqual(geometry["deckScrollTop"], 0)
                        self.assertIsNotNone(geometry["chrome"])
                        self.assertGreater(geometry["chrome"]["width"], 0)
                        self.assertGreater(geometry["chrome"]["height"], 0)
                        self.assertEqual(
                            geometry["overlaps"],
                            {
                                "headline": False,
                                "status": False,
                                "controls": False,
                                "source": False,
                            },
                            geometry,
                        )
                        self.assert_no_automatic_activity(session)
                    finally:
                        session.close()

        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine, layout="portrait"):
                session = self.open_deck(
                    engine,
                    "http",
                    viewport={"width": 390, "height": 844},
                )
                page = session.page
                try:
                    self._activate_scene(page)
                    metrics = page.evaluate(
                        """() => {
                          const scene = document.querySelector('[data-slide-id="queue-capacity"]');
                          const css = node => getComputedStyle(node);
                          const h1 = scene.querySelector('h1');
                          const value = scene.querySelector('[data-output-id="capacity"] dd');
                          const status = scene.querySelector('.scene-status');
                          const evidence = scene.querySelector('[data-action="evidence"]');
                          const label = scene.querySelector('.range-control label');
                          const source = scene.querySelector('.semantic-source');
                          const controls = [...scene.querySelectorAll('button, input')]
                            .filter(node => node.getClientRects().length)
                            .map(node => ({w: node.getBoundingClientRect().width, h: node.getBoundingClientRect().height}));
                          return {
                            h1: parseFloat(css(h1).fontSize),
                            value: parseFloat(css(value).fontSize),
                            status: parseFloat(css(status).fontSize),
                            evidence: parseFloat(css(evidence).fontSize),
                            label: parseFloat(css(label).fontSize),
                            source: parseFloat(css(source).fontSize),
                            controls,
                            scrollWidth: document.documentElement.scrollWidth,
                            innerWidth,
                            pageRule: [...document.styleSheets].flatMap(sheet => [...sheet.cssRules])
                              .find(rule => rule.cssText.trim().startsWith('@page'))?.cssText || ''
                          };
                        }"""
                    )
                    self.assertGreaterEqual(metrics["h1"], 24)
                    self.assertGreaterEqual(metrics["value"], 32)
                    self.assertGreaterEqual(metrics["status"], 16)
                    self.assertGreaterEqual(metrics["evidence"], 16)
                    self.assertGreaterEqual(metrics["label"], 16)
                    self.assertGreaterEqual(metrics["source"], 16)
                    self.assertTrue(metrics["controls"])
                    for bounds in metrics["controls"]:
                        self.assertGreaterEqual(bounds["w"], 44)
                        self.assertGreaterEqual(bounds["h"], 44)
                    self.assertLessEqual(metrics["scrollWidth"], metrics["innerWidth"])
                    self.assertIn("13.333in 7.5in", metrics["pageRule"])
                    self.assertEqual(page.locator(SCENE + ' input[data-control-id="automation"]').count(), 1)
                    self.assertEqual(page.locator(SCENE + ' [data-action="evidence"]').count(), 1)
                    self.assertTrue(page.evaluate(
                        """() => {
                          const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
                          return ids.length === new Set(ids).size;
                        }"""
                    ))
                    self._set_range_sync(page, "80")
                    self._button(page, "evidence").click()
                    snapshot_before = self._snapshot(page)
                    page.emulate_media(media="print")
                    print_state = page.evaluate(
                        """() => {
                          const hiddenByLayout = node => node.getClientRects().length === 0;
                          return {
                            sections: [...document.querySelectorAll('section.slide')].map(
                              (section, index, all) => ({
                                display: getComputedStyle(section).display,
                                fallback: getComputedStyle(
                                  section.querySelector('.fallback-layer')
                                ).display,
                                live: section.querySelector('.live-layer')
                                  ? getComputedStyle(section.querySelector('.live-layer')).display
                                  : null,
                                semantic: getComputedStyle(
                                  section.querySelector('.semantic-scene')
                                ).display,
                                breakAfter: getComputedStyle(section).breakAfter,
                                legacyBreak: getComputedStyle(section).pageBreakAfter,
                                last: index === all.length - 1
                              })
                            ),
                            fallbackX: document.querySelector(
                              '[data-slide-id="queue-capacity"] .fallback-layer circle'
                            ).getAttribute('cx'),
                            chromeHidden: hiddenByLayout(document.querySelector(
                              '#idrt-presenter-chrome'
                            )),
                            railHidden: hiddenByLayout(document.querySelector(
                              '[data-slide-id="queue-capacity"] .control-rail'
                            )),
                            overlayHidden: hiddenByLayout(document.querySelector(
                              '#idrt-overlay-root'
                            )),
                            noJsNavHidden: [...document.querySelectorAll(
                              '.nojs-page-links'
                            )].every(hiddenByLayout),
                            bodyOverflow: getComputedStyle(document.body).overflow
                          };
                        }"""
                    )
                    self.assertTrue(all(item["display"] == "block" for item in print_state["sections"]))
                    self.assertTrue(all(item["fallback"] == "block" for item in print_state["sections"]))
                    self.assertTrue(all(item["semantic"] == "none" for item in print_state["sections"]))
                    self.assertEqual(print_state["sections"][1]["live"], "none")
                    for section in print_state["sections"][:-1]:
                        self.assertIn(section["breakAfter"], ("page", "always"))
                        self.assertIn(section["legacyBreak"], ("always", "page"))
                    self.assertIn(
                        print_state["sections"][-1]["breakAfter"],
                        ("auto", "page", "always"),
                    )
                    self.assertTrue(print_state["chromeHidden"])
                    self.assertTrue(print_state["railHidden"])
                    self.assertTrue(print_state["overlayHidden"])
                    self.assertTrue(print_state["noJsNavHidden"])
                    self.assertEqual(print_state["bodyOverflow"], "visible")
                    self.assertEqual(print_state["fallbackX"], "302.5")
                    self.assertEqual(self._snapshot(page), snapshot_before)
                    page.emulate_media(media="screen")
                    page.keyboard.press("Escape")
                    page.locator("#idrt-static-toggle-2").click()
                    static_snapshot = self._snapshot(page)
                    page.emulate_media(media="print")
                    self.assertEqual(
                        page.evaluate(
                            """() => ({
                              fallback: getComputedStyle(document.querySelector(
                                '[data-slide-id="queue-capacity"] .fallback-layer'
                              )).display,
                              live: getComputedStyle(document.querySelector(
                                '[data-slide-id="queue-capacity"] .live-layer'
                              )).display,
                              x: document.querySelector(
                                '[data-slide-id="queue-capacity"] .fallback-layer circle'
                              ).getAttribute('cx')
                            })"""
                        ),
                        {"fallback": "block", "live": "none", "x": "302.5"},
                    )
                    self.assertEqual(self._snapshot(page), static_snapshot)
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_zoom_forced_colors_and_reduced_layouts_remain_reachable_and_truthful(self) -> None:
        """Covers 200% reflow, high contrast, reduced motion, and vertical reachability."""
        profiles = (
            (
                "zoom-200-percent",
                {"width": 640, "height": 360},
                2,
                None,
                "no-preference",
                True,
            ),
            (
                "forced-colors",
                {"width": 1280, "height": 720},
                None,
                "active",
                "no-preference",
                False,
            ),
            (
                "reduced-motion-portrait",
                {"width": 390, "height": 844},
                None,
                None,
                "reduce",
                True,
            ),
        )
        for engine in ("chromium", "firefox"):
            for (
                profile,
                viewport,
                device_scale_factor,
                forced_colors,
                reduced_motion,
                compact,
            ) in profiles:
                with self.subTest(engine=engine, profile=profile):
                    session = self.open_deck(
                        engine,
                        "http",
                        viewport=viewport,
                        device_scale_factor=device_scale_factor,
                        forced_colors=forced_colors,
                        reduced_motion=reduced_motion,
                    )
                    page = session.page
                    try:
                        self._activate_scene(page)
                        current = page.locator(
                            '#idrt-presenter-chrome [aria-current="page"]'
                        )
                        current.focus()
                        metrics = page.evaluate(
                            """() => {
                              const deck = document.querySelector('#idrt-deck-pages');
                              const chrome = document.querySelector('#idrt-presenter-chrome');
                              const scene = document.querySelector(
                                '[data-slide-id="queue-capacity"]'
                              );
                              const intersects = (node, boundary) => {
                                const box = node.getBoundingClientRect();
                                const clip = boundary.getBoundingClientRect();
                                return box.right > clip.left && box.left < clip.right &&
                                  box.bottom > clip.top && box.top < clip.bottom;
                              };
                              const required = [
                                scene.querySelector('h1'),
                                scene.querySelector('[data-output-id="capacity"] dd'),
                                scene.querySelector('[data-decision-status]'),
                                scene.querySelector('.scene-status'),
                                scene.querySelector('.control-rail'),
                                scene.querySelector('[data-action="evidence"]'),
                                scene.querySelector('.semantic-source')
                              ];
                              const reachable = required.map(node => {
                                node.scrollIntoView({block: 'nearest', inline: 'nearest'});
                                return intersects(node, deck);
                              });
                              const chromeBox = chrome.getBoundingClientRect();
                              const visibleControls = [...scene.querySelectorAll('button,input')]
                                .filter(node => node.getClientRects().length)
                                .map(node => {
                                  const box = node.getBoundingClientRect();
                                  return {width: box.width, height: box.height};
                                });
                              const css = node => getComputedStyle(node);
                              return {
                                innerWidth,
                                innerHeight,
                                devicePixelRatio,
                                forced: matchMedia('(forced-colors: active)').matches,
                                reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
                                documentOverflow: document.documentElement.scrollWidth - innerWidth,
                                deckOverflow: deck.scrollWidth - deck.clientWidth,
                                deckMaxScroll: deck.scrollHeight - deck.clientHeight,
                                deckScrollTop: deck.scrollTop,
                                deckOverflowY: css(deck).overflowY,
                                reachable,
                                chromeVisible: chromeBox.left >= -0.5 && chromeBox.right <= innerWidth + 0.5 &&
                                  chromeBox.top >= -0.5 && chromeBox.bottom <= innerHeight + 0.5 &&
                                  css(chrome).opacity === '1',
                                currentCount: document.querySelectorAll(
                                  '#idrt-presenter-chrome [aria-current="page"]'
                                ).length,
                                currentOutline: parseFloat(css(document.querySelector(
                                  '#idrt-presenter-chrome [aria-current="page"]'
                                )).outlineWidth) || 0,
                                h1: parseFloat(css(scene.querySelector('h1')).fontSize),
                                value: parseFloat(css(scene.querySelector(
                                  '[data-output-id="capacity"] dd'
                                )).fontSize),
                                evidence: parseFloat(css(scene.querySelector(
                                  '[data-action="evidence"]'
                                )).fontSize),
                                source: parseFloat(css(scene.querySelector(
                                  '.semantic-source'
                                )).fontSize),
                                controls: visibleControls,
                                output: scene.querySelector(
                                  '[data-live-value="capacity"]'
                                ).textContent,
                                decision: scene.querySelector(
                                  '[data-decision-status]'
                                ).textContent,
                                fallbackHidden: scene.querySelector(
                                  '.fallback-layer'
                                ).hidden,
                                liveVisible: !scene.querySelector('.live-layer').hidden
                              };
                            }"""
                        )
                        self.assertEqual(metrics["innerWidth"], viewport["width"])
                        self.assertEqual(metrics["innerHeight"], viewport["height"])
                        if device_scale_factor is not None:
                            self.assertEqual(metrics["devicePixelRatio"], device_scale_factor)
                        self.assertEqual(metrics["forced"], forced_colors == "active")
                        self.assertEqual(metrics["reduced"], reduced_motion == "reduce")
                        self.assertLessEqual(metrics["documentOverflow"], 1)
                        self.assertLessEqual(metrics["deckOverflow"], 1)
                        self.assertTrue(all(metrics["reachable"]), metrics)
                        self.assertGreaterEqual(metrics["deckScrollTop"], 0)
                        self.assertTrue(metrics["chromeVisible"], metrics)
                        self.assertEqual(metrics["currentCount"], 1)
                        self.assertEqual(metrics["output"], "26 cases/wk")
                        self.assertEqual(metrics["decision"], "Below demand")
                        self.assertTrue(metrics["fallbackHidden"])
                        self.assertTrue(metrics["liveVisible"])
                        if compact:
                            self.assertGreater(metrics["deckMaxScroll"], 0, metrics)
                            self.assertIn(
                                metrics["deckOverflowY"], ("auto", "scroll"), metrics
                            )
                            self.assertGreater(metrics["deckScrollTop"], 0, metrics)
                            self.assertGreaterEqual(metrics["h1"], 24)
                            self.assertGreaterEqual(metrics["value"], 32)
                            self.assertGreaterEqual(metrics["evidence"], 16)
                            self.assertGreaterEqual(metrics["source"], 16)
                            for bounds in metrics["controls"]:
                                self.assertGreaterEqual(bounds["width"], 44)
                                self.assertGreaterEqual(bounds["height"], 44)
                        if forced_colors == "active":
                            self.assertGreaterEqual(metrics["currentOutline"], 2)

                        self._button(page, "static").click()
                        self.assertTrue(page.locator(SCENE + " .fallback-layer").is_visible())
                        self.assertTrue(page.locator(SCENE + " .live-layer").is_hidden())
                        self.assertEqual(
                            page.locator(
                                SCENE + " .fallback-layer circle"
                            ).get_attribute("cx"),
                            "302.5",
                        )
                        self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "26 cases/wk")
                        self.assert_no_automatic_activity(session)
                    finally:
                        session.close()

    def test_fragment_numeric_and_total_length_budgets_fail_atomically(self) -> None:
        """Catches BigInt work before caps or partial restore after malformed fragments."""
        runtime_artifact = self.artifact.read_text(encoding="utf-8")
        self.assertNotRegex(
            runtime_artifact,
            r"\b(?:window\.)?location\.(?:replace|assign)\s*\(",
            "history fallback must not invoke document navigation methods",
        )
        self.assertNotRegex(
            runtime_artifact,
            r"\b(?:window\.)?location(?:\.href)?\s*=(?!=)",
            "history fallback must only assign the hash property",
        )
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http")
                page = session.page
                try:
                    self._activate_scene(page)
                    exact_numeric = "9" * 128
                    page.evaluate(
                        "value => { location.hash = '#slide=2&automation=' + value; }",
                        exact_numeric,
                    )
                    page.wait_for_function(
                        """() => document.querySelector('[data-slide-id="queue-capacity"] input')
                          ?.getAttribute('aria-valuetext') === '80'"""
                    )
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "50 cases/wk")

                    page.evaluate(
                        "value => { location.hash = '#slide=2&automation=' + value; }",
                        "9" * 129,
                    )
                    page.wait_for_function(
                        """() => document.querySelector('[data-slide-id="queue-capacity"] input')
                          ?.getAttribute('aria-valuetext') === '20'"""
                    )
                    self.assertEqual(page.locator(PRIMARY_VALUE).inner_text(), "26 cases/wk")

                    hash_events = len(session.monitor()["hashes"])
                    page.evaluate("() => { location.hash = '#' + 'x'.repeat(4097); }")
                    page.wait_for_function(
                        "before => window.__E2E_MONITOR__.hashes.length > before",
                        arg=hash_events,
                    )
                    self.assertEqual(self._scene_value(page), "20")
                    self.assertEqual(page.locator(DECISION_STATUS).inner_text(), "Below demand")
                    self._navigate_to(page, 2)
                    same_document = page.evaluate(
                        "() => location.origin + location.pathname + location.search"
                    )
                    fallback_history_length = page.evaluate("() => history.length")
                    page.evaluate(
                        """() => {
                          window.__E2E_MONITOR__.deckEvents.length = 0;
                          window.__E2E_MONITOR__.hashes.length = 0;
                        }"""
                    )
                    session.set_fault("history")
                    immediate = self._set_range_sync(page, "35")
                    self.assertEqual(immediate["primary"], "32 cases/wk")
                    self.assertEqual(immediate["status"], "Ready")
                    page.wait_for_function(
                        "() => location.hash === '#slide=2&automation=35'",
                        timeout=5_000,
                    )
                    self.assertEqual(
                        page.evaluate(
                            "() => location.origin + location.pathname + location.search"
                        ),
                        same_document,
                    )
                    self.assertEqual(
                        page.evaluate("() => history.length"),
                        fallback_history_length + 1,
                    )
                    page.wait_for_function(
                        """() => window.__E2E_MONITOR__.hashes.includes(
                          '#slide=2&automation=35'
                        )"""
                    )
                    fallback_events = session.monitor()["deckEvents"]
                    self.assertEqual(
                        [event["type"] for event in fallback_events],
                        ["state"],
                        "pendingHash echo must not emit a second state event",
                    )
                    self._assert_public_event_schema(fallback_events[0])
                    self.assertEqual(
                        fallback_events[0]["detail"]["pages"][1]["inputs"],
                        {"automation": "35"},
                    )
                    self.assertTrue(page.locator(SCENE).is_visible())
                    self.assertEqual(page.locator(SCENE).get_attribute("data-runtime"), "ready")
                    self.assertIsNone(self._snapshot(page)["pages"][1]["failed"])
                    session.set_fault(None)
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_corrupt_duplicate_special_and_drifted_envelopes_fail_closed(self) -> None:
        """Catches ordinary JSON.parse, special-key maps, or boot drift acceptance."""
        html_text = self.artifact.read_text(encoding="utf-8")
        payload, raw = decode_envelope_text(html_text)

        version = json.loads(raw)
        version["version"] = 2
        mismatch = json.loads(raw)
        mismatch["slides"][1]["scene"]["initialEvaluation"]["outputs"]["capacity"]["value"] = "27"
        point_mismatch = json.loads(raw)
        point_mismatch["slides"][1]["scene"]["initialEvaluation"]["view"]["points"][0]["x"]["value"] = "25"
        display_value_mismatch = json.loads(raw)
        display_value_mismatch["slides"][1]["display"]["staticSummary"]["values"][0]["text"] = "27 cases/wk"
        display_status_mismatch = json.loads(raw)
        display_status_mismatch["slides"][1]["display"]["staticSummary"]["decision"]["status"] = "Ready"
        display_recommendation_mismatch = json.loads(raw)
        display_recommendation_mismatch["slides"][1]["display"]["staticSummary"]["decision"]["recommendation"] = "Forged recommendation"
        quantity_shape = json.loads(raw)
        quantity_shape["slides"][1]["scene"]["quantities"]["automation_rate"]["unexpected"] = 0
        evidence_shape = json.loads(raw)
        evidence_shape["slides"][1]["scene"]["evidence"]["sources"][0]["unexpected"] = True
        target_shape = json.loads(raw)
        target_shape["slides"][1]["scene"]["targets"]["control:automation"]["unexpected"] = True
        step_shape = json.loads(raw)
        step_shape["slides"][1]["scene"]["steps"][0]["action"]["unexpected"] = True
        narration_shape = json.loads(raw)
        narration_shape["slides"][1]["scene"]["narration"]["program"]["controls"][0]["unexpected"] = True
        broken_reference = json.loads(raw)
        broken_reference["slides"][1]["scene"]["steps"][0]["targetKey"] = "control:missing"
        bad_enum = json.loads(raw)
        bad_enum["slides"][1]["scene"]["steps"][0]["action"]["type"] = "teleport"
        one_over_limit = json.loads(raw)
        one_over_limit["slides"][1]["scene"]["narration"]["maxScalars"] = 161
        intercept_drift = json.loads(raw)
        intercept_drift["slides"][1]["scene"]["model"]["intercept"]["value"] = "16"
        coefficient_drift = json.loads(raw)
        coefficient_drift["slides"][1]["scene"]["model"]["terms"][0][1]["value"]["value"] = "0.5"
        synchronized_formula_drift = json.loads(raw)
        synchronized_formula_scene = synchronized_formula_drift["slides"][1]["scene"]
        synchronized_formula_scene["model"]["intercept"]["value"] = "20"
        synchronized_formula_scene["model"]["terms"][0][1]["value"]["value"] = "0.3"

        narration_initial_forged = json.loads(raw)
        narration = narration_initial_forged["slides"][1]["scene"]["narration"]
        narration["messages"]["initial"] = "Forged synchronized initial narration"
        narration["messagesByLocale"][narration["locale"]]["initial"] = (
            "Forged synchronized initial narration"
        )
        narration_reset_forged = json.loads(raw)
        narration = narration_reset_forged["slides"][1]["scene"]["narration"]
        narration["messages"]["reset"] = "Forged synchronized reset narration"
        narration["messagesByLocale"][narration["locale"]]["reset"] = (
            "Forged synchronized reset narration"
        )
        narration_missing_initial = json.loads(raw)
        narration_missing_initial["slides"][1]["scene"]["narration"]["messages"].pop(
            "initial"
        )
        narration_missing_reset = json.loads(raw)
        narration_missing_reset["slides"][1]["scene"]["narration"]["messages"].pop(
            "reset"
        )
        narration_active_locale_mismatch = json.loads(raw)
        narration = narration_active_locale_mismatch["slides"][1]["scene"]["narration"]
        narration["messagesByLocale"][narration["locale"]]["initial"] = (
            "Active locale no longer matches the fixed registry"
        )
        narration_locale_mismatch = json.loads(raw)
        narration = narration_locale_mismatch["slides"][1]["scene"]["narration"]
        narration["locale"] = "ja" if narration["locale"] == "en" else "en"
        narration_reset_161 = json.loads(raw)
        narration = narration_reset_161["slides"][1]["scene"]["narration"]
        narration["messages"]["reset"] = "R" * 161
        narration["messagesByLocale"][narration["locale"]]["reset"] = "R" * 161
        narration_inactive_161 = json.loads(raw)
        narration = narration_inactive_161["slides"][1]["scene"]["narration"]
        inactive_locale = "ja" if narration["locale"] == "en" else "en"
        narration["messagesByLocale"][inactive_locale]["reset"] = "I" * 161
        narration_inactive_missing = json.loads(raw)
        narration = narration_inactive_missing["slides"][1]["scene"]["narration"]
        inactive_locale = "ja" if narration["locale"] == "en" else "en"
        narration["messagesByLocale"][inactive_locale].pop("reset")

        narration_control_label = json.loads(raw)
        narration_control_label["slides"][1]["scene"]["narration"]["program"][
            "controls"
        ][0]["label"] = "Forged control label"
        narration_output_label = json.loads(raw)
        narration_output_label["slides"][1]["scene"]["narration"]["program"][
            "outputs"
        ][0]["label"] = "Forged output label"
        narration_output_display = json.loads(raw)
        narration_output_display["slides"][1]["scene"]["narration"]["program"][
            "outputs"
        ][0]["display"] = "%"
        narration_output_precision = json.loads(raw)
        narration_output_precision["slides"][1]["scene"]["narration"]["program"][
            "outputs"
        ][0]["precision"] = 6

        analytical_negative_zero = json.loads(raw)
        analytical_negative_zero["slides"][1]["scene"]["view"]["xDomain"][0] = "-0.0"
        analytical_trailing_zero = json.loads(raw)
        analytical_trailing_zero["slides"][1]["scene"]["decisionContract"][
            "threshold"
        ]["value"] = "32.0"
        unsafe_source_linked = json.loads(raw)
        unsafe_scene = unsafe_source_linked["slides"][1]["scene"]
        unsafe_source = unsafe_scene["evidence"]["sources"][0]
        unsafe_source["url"] = "javascript:alert('forged-source')"
        unsafe_source["linked"] = True
        unsafe_scene["targets"]["source:method-note"] = {
            "kind": "source",
            "id": "method-note",
        }
        duplicate = raw.replace(
            '"kind":"interactive-deck"',
            '"kind":"interactive-deck","\\u006b\\u0069\\u006e\\u0064":"interactive-deck"',
            1,
        )
        nested_duplicate = raw.replace(
            '"initialState":{"automation":"20"}',
            '"initialState":{"automation":"20","\\u0061utomation":"20"}',
            1,
        )
        self.assertNotEqual(nested_duplicate, raw)
        corrupt_match = ENVELOPE_RE.search(html_text)
        assert corrupt_match is not None
        corrupt = (
            html_text[:corrupt_match.start(2)]
            + "%%%not-base64url%%%"
            + html_text[corrupt_match.end(2):]
        )
        variants = {
            "corrupt": corrupt,
            "duplicate": replace_envelope_text(html_text, duplicate),
            "nested-duplicate": replace_envelope_text(html_text, nested_duplicate),
            "version": replace_envelope_text(
                html_text,
                json.dumps(version, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            ),
            "mismatch": replace_envelope_text(
                html_text,
                json.dumps(mismatch, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            ),
            "point-value-mismatch": replace_envelope_text(
                html_text,
                json.dumps(
                    point_mismatch,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
            "display-value-mismatch": replace_envelope_text(
                html_text,
                json.dumps(
                    display_value_mismatch,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
            "display-status-mismatch": replace_envelope_text(
                html_text,
                json.dumps(
                    display_status_mismatch,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
            "display-recommendation-mismatch": replace_envelope_text(
                html_text,
                json.dumps(
                    display_recommendation_mismatch,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        }
        for name, value in (
            ("quantity-shape", quantity_shape),
            ("evidence-shape", evidence_shape),
            ("target-shape", target_shape),
            ("step-shape", step_shape),
            ("narration-shape", narration_shape),
            ("broken-reference", broken_reference),
            ("bad-enum", bad_enum),
            ("one-over-limit", one_over_limit),
            ("intercept-18-to-16", intercept_drift),
            ("coefficient-point4-to-point5", coefficient_drift),
            ("coordinated-model-formula-drift", synchronized_formula_drift),
            ("narration-initial-synchronized-forgery", narration_initial_forged),
            ("narration-reset-synchronized-forgery", narration_reset_forged),
            ("narration-missing-initial", narration_missing_initial),
            ("narration-missing-reset", narration_missing_reset),
            ("narration-active-locale-mismatch", narration_active_locale_mismatch),
            ("narration-locale-mismatch", narration_locale_mismatch),
            ("narration-reset-161-scalars", narration_reset_161),
            ("narration-inactive-161-scalars", narration_inactive_161),
            ("narration-inactive-missing-reset", narration_inactive_missing),
            ("narration-control-label-forgery", narration_control_label),
            ("narration-output-label-forgery", narration_output_label),
            ("narration-output-display-forgery", narration_output_display),
            ("narration-output-precision-forgery", narration_output_precision),
            ("analytical-negative-zero", analytical_negative_zero),
            ("analytical-trailing-zero", analytical_trailing_zero),
            ("unsafe-source-forged-linked", unsafe_source_linked),
        ):
            variants[name] = replace_envelope_text(
                html_text,
                json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        for special_id in ("__proto__", "constructor", "prototype"):
            special = json.loads(raw)
            special["slides"][1]["slideId"] = special_id
            special["slides"][1]["scene"]["slideId"] = special_id
            variants["special-" + special_id] = replace_envelope_text(
                html_text,
                json.dumps(special, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            )
        paths = {
            name: self.write_variant(f"invalid-{name}.interactive.html", value)
            for name, value in variants.items()
        }
        for engine in ("chromium", "firefox"):
            for name, path in paths.items():
                with self.subTest(engine=engine, variant=name):
                    session = self.open_deck(engine, "http", artifact=path)
                    try:
                        self.assertEqual(
                            [
                                event
                                for event in session.monitor()["deckEvents"]
                                if event["type"] == "ready"
                            ],
                            [],
                        )
                        self.assertNotEqual(
                            session.page.locator(SCENE).get_attribute("data-runtime"),
                            "ready",
                        )
                        self._click_visible_native_page_link(session.page, 2)
                        self._assert_static_fail_closed(session)
                        self._assert_only_initial_request(session)
                    finally:
                        session.close()

    def test_missing_bigint_or_textdecoder_leaves_readable_static_deck(self) -> None:
        """Catches feature probing after partial enhancement."""
        variants = {
            "BigInt": "delete globalThis.BigInt;",
            "TextDecoder": "delete globalThis.TextDecoder;",
        }
        for engine in ("chromium", "firefox"):
            for primitive, script in variants.items():
                with self.subTest(engine=engine, primitive=primitive):
                    session = self.open_deck(engine, "http", init_script=script)
                    try:
                        self._click_visible_native_page_link(session.page, 2)
                        self._assert_static_fail_closed(session)
                        self._assert_only_initial_request(session)
                    finally:
                        session.close()

        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine, primitive="first-render-geometry"):
                session = self.open_deck(
                    engine,
                    "http",
                    initial_fault="geometry",
                )
                page = session.page
                try:
                    self.assertEqual(
                        page.locator("html").get_attribute("data-interactive-runtime"),
                        "static",
                    )
                    self.assertFalse(
                        page.evaluate("() => typeof window.InteractiveDeck !== 'undefined'")
                    )
                    self.assertEqual(
                        [
                            event
                            for event in session.monitor()["deckEvents"]
                            if event["type"] == "ready"
                        ],
                        [],
                    )
                    self._click_visible_native_page_link(page, 2)
                    page.wait_for_function(
                        "() => location.hash === '#idrt-page-2'"
                    )
                    self.assertTrue(page.locator(SCENE).is_visible())
                    self.assertEqual(page.locator(SCENE).get_attribute("data-runtime"), "static")
                    self.assertTrue(page.locator(SCENE + " .fallback-layer").is_visible())
                    self.assertTrue(page.locator(SCENE + " .live-layer").is_hidden())
                    for control in page.locator(SCENE + " input, " + SCENE + " button").all():
                        if control.is_visible():
                            self.assertTrue(
                                control.is_disabled()
                                or control.get_attribute("aria-disabled") == "true"
                            )
                    self._assert_static_fail_closed(
                        session,
                        forbidden=("E2E_SECRET",),
                    )
                    self._assert_only_initial_request(session)
                finally:
                    session.close()

        for engine in ("chromium", "firefox"):
            for boot_case in ("late-ready-dispatch", "preoccupied-api"):
                with self.subTest(engine=engine, primitive=boot_case):
                    session = self.open_deck(
                        engine,
                        "http",
                        initial_fault="ready" if boot_case == "late-ready-dispatch" else None,
                        preoccupied_api=boot_case == "preoccupied-api",
                    )
                    page = session.page
                    try:
                        self.assertEqual(
                            page.locator("html").get_attribute("data-interactive-runtime"),
                            "static",
                        )
                        self.assertEqual(
                            session.monitor()["deckEvents"],
                            [],
                        )
                        self.assertEqual(
                            session.monitor()["windowHandlers"],
                            {"error": 0, "unhandledrejection": 0},
                        )
                        descriptor = page.evaluate(
                            """() => {
                              const found = Object.getOwnPropertyDescriptor(
                                window, 'InteractiveDeck'
                              );
                              return found ? {
                                value: found.value,
                                writable: found.writable,
                                configurable: found.configurable,
                                enumerable: found.enumerable
                              } : null;
                            }"""
                        )
                        if boot_case == "late-ready-dispatch":
                            self.assertIsNone(descriptor)
                        else:
                            self.assertEqual(
                                descriptor,
                                {
                                    "value": "occupied",
                                    "writable": False,
                                    "configurable": False,
                                    "enumerable": True,
                                },
                            )
                        self.assertTrue(
                            all(
                                section.is_visible()
                                for section in page.locator("section.slide").all()
                            )
                        )
                        self.assertEqual(
                            page.locator(SCENE).get_attribute("data-runtime"),
                            "static",
                        )
                        self.assertTrue(page.locator(SCENE + " .fallback-layer").is_visible())
                        self.assertTrue(page.locator(SCENE + " .live-layer").is_hidden())
                        for control in page.locator(SCENE + " input, " + SCENE + " button").all():
                            if control.is_visible():
                                self.assertTrue(
                                    control.is_disabled()
                                    or control.get_attribute("aria-disabled") == "true"
                                )

                        page.locator("#idrt-heading-2").focus()
                        page.keyboard.press("ArrowLeft")
                        self.assertTrue(
                            all(
                                section.is_visible()
                                for section in page.locator("section.slide").all()
                            )
                        )
                        self._click_visible_native_page_link(page, 2)
                        page.wait_for_function("() => location.hash === '#idrt-page-2'")
                        self.assertTrue(page.locator(SCENE).is_visible())
                        self._assert_static_fail_closed(
                            session,
                            forbidden=("E2E_SECRET",),
                        )
                        self._assert_only_initial_request(session)
                    finally:
                        session.close()

    def test_encoded_envelope_one_over_budget_is_rejected_before_decode(self) -> None:
        """Catches atob/UTF-8 allocation before the 16 MiB decoded cap."""
        html_text = self.artifact.read_text(encoding="utf-8")
        maximum_encoded = (4 * (16 * 1024 * 1024) + 2) // 3
        match = ENVELOPE_RE.search(html_text)
        assert match is not None
        oversized = (
            html_text[:match.start(2)]
            + ("A" * (maximum_encoded + 1))
            + html_text[match.end(2):]
        )
        path = self.write_variant("oversized-envelope.interactive.html", oversized)
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=path)
                try:
                    self._click_visible_native_page_link(session.page, 2)
                    self._assert_static_fail_closed(session)
                    self._assert_only_initial_request(session)
                finally:
                    session.close()

    def test_authored_injection_and_browser_parser_differentials_do_not_execute(self) -> None:
        """Catches executable-context escaping and browser HTML repair surprises."""
        poison = "</script><script>globalThis.pwned=1</script> <>& \u2028\u2029 日本語 🩺"
        poison_root = self.fixture_root / "poison"
        poison_path = build_fixture(poison_root, poison=poison)
        astral_purpose = "🩺" * 300
        astral_path = build_fixture(
            self.fixture_root / "astral-limit",
            scene_purpose=astral_purpose,
        )
        long_point_id = "p" * 64
        long_point_path = build_fixture(
            self.fixture_root / "long-point-id",
            point_id=long_point_id,
            output_name="long-point-id.interactive.html",
        )
        unsafe_source_urls = {
            "javascript-scheme": "javascript:alert(1)",
            "https-credentials": "https://user:pass@example.com",
            "https-encoded-control": "https://example.com/%0A",
            "mailto-query": "mailto:a@example.com?subject=Hi",
        }
        unsafe_source_paths = {
            "unsafe-source-" + name: build_fixture(
                self.fixture_root / ("unsafe-source-" + name),
                source_url=url,
                output_name="unsafe-source.interactive.html",
            )
            for name, url in unsafe_source_urls.items()
        }
        astral_source_url = "https://example.com/" + ("🩺" * 1020)
        self.assertLessEqual(len(astral_source_url), 2048)
        self.assertGreater(len(astral_source_url.encode("utf-16-le")) // 2, 2048)
        astral_source_path = build_fixture(
            self.fixture_root / "astral-source-url",
            source_url=astral_source_url,
            output_name="astral-source-url.interactive.html",
        )
        whatwg_source_urls = {
            "whatwg-dot-host": "https://.",
            "whatwg-rejected-ipvfuture": "https://[v1.foo]",
            "whatwg-valid-ipv4": "https://127.0.0.1/source",
            "whatwg-valid-ipv6": "https://[::1]/source",
        }
        whatwg_expected_linked = {
            "whatwg-dot-host": False,
            "whatwg-rejected-ipvfuture": False,
            "whatwg-valid-ipv4": True,
            "whatwg-valid-ipv6": True,
        }
        whatwg_source_paths = {
            name: build_fixture(
                self.fixture_root / name,
                source_url=url,
                output_name="whatwg-source.interactive.html",
            )
            for name, url in whatwg_source_urls.items()
        }
        scheme_source_urls = {
            "scheme-data": "data:text/plain,deck",
            "scheme-file": "file:///tmp/deck-source",
            "scheme-protocol-relative": "//example.com/source",
            "scheme-malformed-percent": "https://example.com/%",
            "scheme-safe-mailto": "mailto:reader+deck@example.com",
        }
        scheme_expected_linked = {
            "scheme-data": False,
            "scheme-file": False,
            "scheme-protocol-relative": False,
            "scheme-malformed-percent": False,
            "scheme-safe-mailto": True,
        }
        scheme_source_paths = {
            name: build_fixture(
                self.fixture_root / name,
                source_url=url,
                output_name="scheme-source.interactive.html",
            )
            for name, url in scheme_source_urls.items()
        }
        for name, path in unsafe_source_paths.items():
            compiled, _raw = decode_envelope_text(path.read_text(encoding="utf-8"))
            source = compiled["slides"][1]["scene"]["evidence"]["sources"][0]
            self.assertFalse(source["linked"], name)
            self.assertEqual(
                source["url"],
                unsafe_source_urls[name.removeprefix("unsafe-source-")],
            )
        astral_payload, _raw = decode_envelope_text(
            astral_source_path.read_text(encoding="utf-8")
        )
        astral_source = astral_payload["slides"][1]["scene"]["evidence"]["sources"][0]
        self.assertTrue(astral_source["linked"])
        self.assertEqual(astral_source["url"], astral_source_url)
        for name, path in whatwg_source_paths.items():
            compiled, _raw = decode_envelope_text(path.read_text(encoding="utf-8"))
            source = compiled["slides"][1]["scene"]["evidence"]["sources"][0]
            self.assertEqual(source["linked"], whatwg_expected_linked[name], name)
            self.assertEqual(source["url"], whatwg_source_urls[name])
        for name, path in scheme_source_paths.items():
            compiled, _raw = decode_envelope_text(path.read_text(encoding="utf-8"))
            source = compiled["slides"][1]["scene"]["evidence"]["sources"][0]
            self.assertEqual(source["linked"], scheme_expected_linked[name], name)
            self.assertEqual(source["url"], scheme_source_urls[name])

        base_html = self.artifact.read_text(encoding="utf-8")
        parser_probe = """
<div id="parser-differential-probe">
  <SvG xmlns="http://www.w3.org/2000/svg"><a href="https://attacker.invalid/a"><text>inert</text></a></SvG>
  <a id="duplicate-attribute-probe" href="#idrt-page-1" href="https://attacker.invalid/b">duplicate</a>
  <svg xmlns="http://www.w3.org/2000/svg"><g clip-path="url(#idsvg-1-fallback-not-owned)"></g></svg>
  <p data-entity="&amp;#x68;ttps://attacker.invalid/c">&lt;script&gt;globalThis.pwned=2&lt;/script&gt;</p>
</div>
"""
        overlay_marker = '<div id="idrt-overlay-root">'
        self.assertEqual(base_html.count(overlay_marker), 1)
        parser_path = self.write_variant(
            "parser-differential.interactive.html",
            base_html.replace(overlay_marker, parser_probe + overlay_marker, 1),
        )

        for engine in ("chromium", "firefox"):
            variants = (
                ("authored", poison_path),
                ("parser", parser_path),
                ("astral-limit", astral_path),
                ("long-point-id", long_point_path),
                ("astral-source-url", astral_source_path),
            ) + tuple(unsafe_source_paths.items()) + tuple(whatwg_source_paths.items()) + tuple(
                scheme_source_paths.items()
            )
            for name, path in variants:
                with self.subTest(engine=engine, variant=name):
                    session = self.open_deck(engine, "http", artifact=path)
                    try:
                        if name == "authored":
                            self._activate_scene(session.page)
                            self.assertIn(poison, session.page.title())
                            self.assertEqual(session.page.locator("script").count(), 1)
                        elif name == "parser":
                            self._wait_for_runtime(session.page)
                            self.assertEqual(
                                session.page.locator("#duplicate-attribute-probe").get_attribute("href"),
                                "#idrt-page-1",
                            )
                        elif name in (
                            "astral-source-url",
                            "whatwg-valid-ipv4",
                            "whatwg-valid-ipv6",
                            "scheme-safe-mailto",
                        ):
                            self.assertEqual(
                                session.page.locator("html").get_attribute(
                                    "data-interactive-runtime"
                                ),
                                "ready",
                            )
                            self._activate_scene(session.page)
                            self._button(session.page, "evidence").click()
                            source_link = session.page.locator(
                                '#idrt-evidence-dialog-2 '
                                '[data-evidence-panel="sources"] a[href]'
                            )
                            self.assertEqual(source_link.count(), 1)
                            self.assertEqual(
                                source_link.get_attribute("href"),
                                astral_source_url
                                if name == "astral-source-url"
                                else scheme_source_urls[name]
                                if name == "scheme-safe-mailto"
                                else whatwg_source_urls[name],
                            )
                            if name == "scheme-safe-mailto":
                                self.assertIsNone(source_link.get_attribute("target"))
                                self.assertIsNone(source_link.get_attribute("rel"))
                                self.assertIsNone(
                                    source_link.get_attribute("referrerpolicy")
                                )
                            else:
                                self.assertEqual(
                                    source_link.get_attribute("target"), "_blank"
                                )
                            session.page.keyboard.press("Escape")
                        elif name.startswith("unsafe-source-") or name in (
                            "whatwg-dot-host",
                            "whatwg-rejected-ipvfuture",
                        ) or (
                            name.startswith("scheme-")
                            and not scheme_expected_linked[name]
                        ):
                            self.assertEqual(
                                session.page.locator("html").get_attribute(
                                    "data-interactive-runtime"
                                ),
                                "ready",
                            )
                            self._activate_scene(session.page)
                            self._button(session.page, "evidence").click()
                            source_panel = session.page.locator(
                                '#idrt-evidence-dialog-2 [data-evidence-panel="sources"]'
                            )
                            self.assertEqual(source_panel.locator("a[href]").count(), 0)
                            self.assertEqual(
                                source_panel.locator("li > span").inner_text(),
                                "Illustrative method note",
                            )
                            self.assertNotIn(
                                unsafe_source_urls[name.removeprefix("unsafe-source-")]
                                if name.startswith("unsafe-source-")
                                else scheme_source_urls[name]
                                if name.startswith("scheme-")
                                else whatwg_source_urls[name],
                                source_panel.inner_text(),
                            )
                            session.page.keyboard.press("Escape")
                        else:
                            self._activate_scene(session.page)
                            self.assertEqual(
                                session.page.locator(SCENE).get_attribute("data-runtime"),
                                "ready",
                            )
                            self.assertIsNone(self._snapshot(session.page)["pages"][1]["failed"])
                            if name == "long-point-id":
                                svg_ids = session.page.locator(
                                    SCENE + " .live-layer svg [id]"
                                ).evaluate_all("nodes => nodes.map(node => node.id)")
                                self.assertTrue(svg_ids)
                                self.assertEqual(len(svg_ids), len(set(svg_ids)))
                                for svg_id in svg_ids:
                                    self.assertRegex(svg_id, r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
                                self.assertEqual(
                                    session.page.locator(
                                        SCENE + " .live-layer circle[id]"
                                    ).count(),
                                    1,
                                )
                        self.assertIsNone(session.page.evaluate("() => globalThis.pwned"))
                        self.assert_no_automatic_activity(session)
                    finally:
                        session.close()

        # The newly closed scheme corpus must behave identically from file://
        # and loopback HTTP.  The full legacy injection matrix remains on HTTP
        # above to keep the acceptance suite bounded.
        for engine in ("chromium", "firefox"):
            for name, path in scheme_source_paths.items():
                with self.subTest(engine=engine, mode="file", variant=name):
                    session = self.open_deck(engine, "file", artifact=path)
                    try:
                        self.assertEqual(
                            session.page.locator("html").get_attribute(
                                "data-interactive-runtime"
                            ),
                            "ready",
                        )
                        self._activate_scene(session.page)
                        self._button(session.page, "evidence").click()
                        source_panel = session.page.locator(
                            '#idrt-evidence-dialog-2 [data-evidence-panel="sources"]'
                        )
                        source_links = source_panel.locator("a[href]")
                        if scheme_expected_linked[name]:
                            self.assertEqual(source_links.count(), 1)
                            self.assertEqual(
                                source_links.get_attribute("href"),
                                scheme_source_urls[name],
                            )
                            self.assertIsNone(source_links.get_attribute("target"))
                            self.assertIsNone(source_links.get_attribute("rel"))
                            self.assertIsNone(
                                source_links.get_attribute("referrerpolicy")
                            )
                        else:
                            self.assertEqual(source_links.count(), 0)
                            self.assertEqual(
                                source_panel.locator("li > span").inner_text(),
                                "Illustrative method note",
                            )
                            self.assertNotIn(
                                scheme_source_urls[name],
                                source_panel.inner_text(),
                            )
                        session.page.keyboard.press("Escape")
                        self.assertEqual(session.observations.blocked_requests, [])
                        self.assert_no_automatic_activity(session)
                    finally:
                        session.close()

    def test_every_async_fault_phase_fails_only_the_scene_and_sanitizes_diagnostics(self) -> None:
        """Catches mixed truth, stale callbacks, payload logging, or deck-wide failure."""
        multi_scene_artifact = build_fixture(
            self.fixture_root / "two-enhanced-scenes",
            second_interactive=True,
            output_name="two-enhanced-scenes.interactive.html",
        )
        triggers = {
            "evaluation": "range",
            "text": "range",
            "geometry": "range",
            "raf": "range",
            "timer": "timer",
            "hash": "hash",
            "overlay": "overlay",
            "pointer": "pointer",
            "touch": "touch",
            "focus": "focus",
        }
        for engine in ("chromium", "firefox"):
            for phase, trigger in triggers.items():
                with self.subTest(engine=engine, phase=phase):
                    session = self.open_deck(engine, "http")
                    page = session.page
                    try:
                        self._activate_scene(page)
                        if trigger == "focus":
                            page.locator("#idrt-heading-2").focus()
                        session.set_fault(phase)
                        if trigger == "range":
                            self._set_range_sync(page, "35")
                        elif trigger == "timer":
                            self._set_range_sync(page, "35")
                        elif trigger == "hash":
                            page.evaluate("() => { location.hash = '#slide=2&automation=35'; }")
                        elif trigger == "pointer":
                            page.locator("#idrt-page-2 .frame").evaluate(
                                """frame => {
                                  const box = frame.getBoundingClientRect();
                                  frame.dispatchEvent(new PointerEvent('pointerdown', {
                                    bubbles: true,
                                    pointerId: 91,
                                    isPrimary: true,
                                    pointerType: 'touch',
                                    clientX: box.left + box.width * .25,
                                    clientY: box.top + box.height * .5
                                  }));
                                }"""
                            )
                        elif trigger == "touch":
                            page.evaluate(
                                """() => document.dispatchEvent(
                                  new Event('touchstart', {bubbles: true})
                                )"""
                            )
                        elif trigger == "focus":
                            page.locator(
                                '#idrt-presenter-chrome [data-page-index="2"]'
                            ).focus()
                        else:
                            self._button(page, "evidence").click()
                        expect(page.locator(SCENE)).to_have_attribute(
                            "data-runtime",
                            "failed",
                            timeout=5_000,
                        )
                        self._assert_static_fail_closed(
                            session,
                            forbidden=("E2E_SECRET",),
                        )
                        self.assertIn(
                            "Weekly capacity: 20%, 26 cases/wk",
                            self._aria_snapshot(page),
                        )
                        failure_notice = page.locator(STATUS).inner_text()
                        self.assertTrue(failure_notice.strip())
                        if phase != "text":
                            self.assertEqual(
                                failure_notice,
                                "Interactive view unavailable. Static baseline restored.",
                            )
                        if phase == "overlay":
                            self.assertEqual(
                                self._button(page, "evidence").get_attribute("aria-expanded"),
                                "false",
                            )
                            self.assertEqual(
                                page.evaluate("() => document.activeElement?.id"),
                                "idrt-heading-2",
                            )
                            self.assertTrue(page.locator("#idrt-heading-2").is_visible())
                        self._assert_only_initial_request(session)
                        session.set_fault(None)
                        self._navigate_to(page, 1)
                        self.assertTrue(page.locator('[data-slide-id="slide-001"]').is_visible())
                        self._navigate_to(page, 2)
                        self._assert_static_fail_closed(
                            session,
                            forbidden=("E2E_SECRET",),
                        )
                        self.assertEqual(
                            page.locator(STATUS).inner_text(),
                            "Interactive view unavailable. Static baseline restored.",
                        )
                        self.assertEqual(page.locator(SCENE).get_attribute("data-runtime"), "failed")
                        self._navigate_to(page, 1)
                    finally:
                        session.close()

        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine, phase="global-static-all-scenes"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=multi_scene_artifact,
                )
                page = session.page
                try:
                    self._activate_scene(page)
                    page.locator("#idrt-static-toggle-2").click()
                    self.assertEqual(
                        self._snapshot(page)["pages"][1]["viewMode"],
                        "static",
                    )
                    page.evaluate(
                        """() => setTimeout(() => {
                          throw new Error('E2E_SECRET global payload');
                        }, 0)"""
                    )
                    for ordinal, slide_id in (
                        (2, "queue-capacity"),
                        (3, "queue-capacity-copy"),
                    ):
                        scene = page.locator(f'[data-slide-id="{slide_id}"]')
                        expect(scene).to_have_attribute(
                            "data-runtime",
                            "failed",
                            timeout=5_000,
                        )
                        self._navigate_to(page, ordinal)
                        self.assertTrue(scene.locator(".fallback-layer").is_visible())
                        self.assertTrue(scene.locator(".live-layer").is_hidden())
                        for control in scene.locator("input, button").all():
                            if control.is_visible():
                                self.assertTrue(
                                    control.is_disabled()
                                    or control.get_attribute("aria-disabled") == "true"
                                )
                        self.assertIn(
                            "Weekly capacity: 20%, 26 cases/wk",
                            scene.aria_snapshot(),
                        )
                    self._navigate_to(page, 2)
                    self._assert_static_fail_closed(
                        session,
                        forbidden=("E2E_SECRET",),
                    )
                    self._assert_only_initial_request(session)
                finally:
                    session.close()


if __name__ == "__main__":
    import unittest

    unittest.main()
