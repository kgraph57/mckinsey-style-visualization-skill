"""Browser acceptance for the public Project Relay reference deck.

The oracles in this file come from the frozen Task 7 brief.  They exercise the
checked-in audience artifact and independently built public fixture sources;
they do not call the Python evaluator or audit planner to calculate expected
values.
"""
from __future__ import annotations

import base64
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from base import (
    BUILD_SCRIPT,
    ENVELOPE_RE,
    ROOT,
    InteractiveDeckBrowserTestCase,
)


REFERENCE_ROOT = ROOT / "examples" / "interactive-deck"
REFERENCE_ARTIFACT = REFERENCE_ROOT / "deck.interactive.html"
REFERENCE_MANIFEST = REFERENCE_ROOT / "deck.json"
FIXTURE_ROOT = ROOT / "examples" / "interactive-fixtures"
AUDIT_SCRIPT = ROOT / "scripts" / "audit_interactive_deck.py"

SLIDES = {
    "relay-cover": 1,
    "relay-pilot-thesis": 2,
    "relay-late-job-evidence": 3,
    "relay-route-priority": 4,
    "relay-adoption-value": 5,
    "relay-readiness-score": 6,
    "relay-twelve-week-plan": 7,
    "relay-decision": 8,
}

INTERACTIVE_SLIDES = (
    "relay-late-job-evidence",
    "relay-route-priority",
    "relay-adoption-value",
    "relay-readiness-score",
)

EXPECTED_DEMO_STEPS = (
    ("relay-late-job-evidence", "relay-open-late-job-evidence"),
    ("relay-route-priority", "relay-apply-technician-constraint"),
    ("relay-adoption-value", "relay-test-adoption-below-gate"),
    ("relay-adoption-value", "relay-test-adoption-above-gate"),
    ("relay-readiness-score", "relay-remove-manager-capacity"),
    ("relay-readiness-score", "relay-restore-manager-capacity"),
)

DEMO_RECORDER = r"""
(() => {
  const records = {steps: [], ends: []};
  Object.defineProperty(window, "__REFERENCE_DEMO__", {
    value: records, configurable: false, enumerable: false, writable: false
  });
  document.addEventListener("deck:demo-step", event => {
    records.steps.push({
      detail: JSON.parse(JSON.stringify(event.detail)),
      snapshot: window.InteractiveDeck.snapshot(),
      at: performance.now()
    });
  });
  document.addEventListener("deck:demo-end", event => {
    records.ends.push({
      detail: JSON.parse(JSON.stringify(event.detail)),
      snapshot: window.InteractiveDeck.snapshot(),
      at: performance.now()
    });
  });
})();
"""

FULLSCREEN_UNAVAILABLE = r"""
Object.defineProperty(document, "fullscreenEnabled", {
  value: false, configurable: true
});
Object.defineProperty(Element.prototype, "requestFullscreen", {
  value: undefined, configurable: true
});
"""


def _decode_envelope(path: Path) -> dict:
    match = ENVELOPE_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError(f"interactive envelope not found in {path.name}")
    token = match.group(2)
    token += "=" * ((4 - len(token) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))


def _build_fixture(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination)
    artifact = destination / "deck.interactive.html"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(BUILD_SCRIPT),
            "--manifest",
            str(destination / "deck.json"),
            "-o",
            str(artifact),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise AssertionError(
            f"{source.name} fixture build failed: {completed.stderr.strip()}"
        )
    return artifact


def _rects_overlap(first: dict, second: dict) -> bool:
    return (
        float(first["left"]) < float(second["right"])
        and float(first["right"]) > float(second["left"])
        and float(first["top"]) < float(second["bottom"])
        and float(first["bottom"]) > float(second["top"])
    )


class InteractiveReferenceE2ETests(InteractiveDeckBrowserTestCase):
    """Runs the real eight-page reference and three independent fixtures."""

    @classmethod
    def setUpClass(cls) -> None:
        required = [
            REFERENCE_MANIFEST,
            REFERENCE_ARTIFACT,
            *(FIXTURE_ROOT / name / "deck.json" for name in ("drilldown", "accordion", "tooltip")),
        ]
        missing = [path for path in required if not path.is_file()]
        if missing:
            raise AssertionError(
                "Task 7 reference inputs are incomplete: "
                + ", ".join(str(path.relative_to(ROOT)) for path in missing)
            )
        super().setUpClass()

        public_copy = cls.fixture_root / "project-relay" / "deck.interactive.html"
        public_copy.parent.mkdir(parents=True)
        shutil.copyfile(REFERENCE_ARTIFACT, public_copy)
        cls.artifact = public_copy
        cls.envelope = _decode_envelope(public_copy)
        cls.reference_scenes = {
            slide["slideId"]: slide["scene"]
            for slide in cls.envelope["slides"]
            if slide["scene"] is not None
        }
        cls.compiled_scenes = dict(cls.reference_scenes)

        cls.fixture_artifacts = {}
        for name in ("drilldown", "accordion", "tooltip"):
            artifact = _build_fixture(
                FIXTURE_ROOT / name,
                cls.fixture_root / "component-fixtures" / name,
            )
            cls.fixture_artifacts[name] = artifact
            fixture_envelope = _decode_envelope(artifact)
            for slide in fixture_envelope["slides"]:
                if slide["scene"] is not None:
                    cls.compiled_scenes[slide["slideId"]] = slide["scene"]

    def _wait_ready(self, page) -> None:
        page.wait_for_function(
            """() => document.documentElement.dataset.interactiveRuntime === 'ready' &&
              window.InteractiveDeck && typeof window.InteractiveDeck.snapshot === 'function'""",
            timeout=10_000,
        )

    def _activate(self, page, slide_id: str) -> None:
        ordinal = SLIDES[slide_id]
        page.locator(
            f'#idrt-presenter-chrome [data-page-index="{ordinal}"]'
        ).click()
        page.wait_for_function(
            """args => {
              const section = document.querySelector(`[data-slide-id="${args.slideId}"]`);
              return window.InteractiveDeck.snapshot().currentSlide === args.ordinal &&
                section && !section.hidden &&
                (!section.dataset.runtime || section.dataset.runtime === 'ready');
            }""",
            arg={"slideId": slide_id, "ordinal": ordinal},
            timeout=10_000,
        )

    @staticmethod
    def _scene(page, slide_id: str):
        return page.locator(f'[data-slide-id="{slide_id}"]')

    def _set_data_details(self, page, slide_id: str, *, opened: bool) -> None:
        details = self._scene(page, slide_id).locator(".data-details")
        self.assertEqual(details.count(), 1)
        if (details.get_attribute("open") is not None) != opened:
            summary = details.locator("summary")
            summary.focus()
            summary.press("Enter")
        self.assertEqual(details.get_attribute("open") is not None, opened)

    @staticmethod
    def _snapshot(page) -> dict:
        return page.evaluate("() => window.InteractiveDeck.snapshot()")

    def _page_state(self, page, slide_id: str) -> dict:
        return self._snapshot(page)["pages"][SLIDES[slide_id] - 1]

    def _set_range(self, page, slide_id: str, control_id: str, actual: str) -> None:
        control = next(
            item
            for item in self.compiled_scenes[slide_id]["controls"]
            if item["id"] == control_id
        )
        minimum = Decimal(control["min"])
        step = Decimal(control["step"])
        index = (Decimal(actual) - minimum) / step
        self.assertEqual(index, index.to_integral_value())
        locator = self._scene(page, slide_id).locator(
            f'input[data-control-id="{control_id}"]'
        )
        self.assertEqual(locator.count(), 1)
        locator.evaluate(
            """(input, index) => {
              input.value = index;
              input.dispatchEvent(new Event('input', {bubbles: true}));
            }""",
            str(index.to_integral_value()),
        )
        page.wait_for_function(
            """args => document.querySelector(
              `[data-slide-id="${args.slideId}"] input[data-control-id="${args.controlId}"]`
            )?.getAttribute('aria-valuetext') === args.actual""",
            arg={
                "slideId": slide_id,
                "controlId": control_id,
                "actual": actual,
            },
        )

    def _set_categorical(
        self,
        page,
        slide_id: str,
        control_id: str,
        value: str,
    ) -> None:
        scene = self._scene(page, slide_id)
        select = scene.locator(
            f'[data-control-id="{control_id}"] select[data-control-select]'
        )
        if select.count() == 1:
            select.select_option(value)
            page.wait_for_function(
                """args => document.querySelector(
                  `[data-slide-id="${args.slideId}"] ` +
                  `[data-control-id="${args.controlId}"] select`
                )?.value === args.value""",
                arg={
                    "slideId": slide_id,
                    "controlId": control_id,
                    "value": value,
                },
            )
        else:
            button = scene.locator(
                f'[data-control-id="{control_id}"] '
                f'button[data-control-value="{value}"]'
            )
            self.assertEqual(button.count(), 1, (slide_id, control_id, value))
            button.click()
            page.wait_for_function(
                """args => document.querySelector(
                  `[data-slide-id="${args.slideId}"] ` +
                  `[data-control-id="${args.controlId}"] ` +
                  `button[data-control-value="${args.value}"]`
                )?.getAttribute('aria-pressed') === 'true'""",
                arg={
                    "slideId": slide_id,
                    "controlId": control_id,
                    "value": value,
                },
            )

    def _set_score_inputs(self, page, values: dict[str, str]) -> None:
        slide_id = "relay-readiness-score"
        for control_id, value in values.items():
            control = next(
                item
                for item in self.compiled_scenes[slide_id]["controls"]
                if item["id"] == control_id
            )
            if control["kind"] == "range":
                self._set_range(page, slide_id, control_id, value)
            else:
                self._set_categorical(page, slide_id, control_id, value)

    @staticmethod
    def _svg_anchor(locator) -> dict:
        return locator.evaluate(
            """node => ({
              x: node.getAttribute('x'), y: node.getAttribute('y'),
              x1: node.getAttribute('x1'), x2: node.getAttribute('x2'),
              y1: node.getAttribute('y1'), y2: node.getAttribute('y2'),
              width: node.getAttribute('width'), height: node.getAttribute('height'),
              text: node.textContent
            })"""
        )

    def _live_node(self, page, slide_id: str, source_id: str):
        ordinal = SLIDES[slide_id]
        return self._scene(page, slide_id).locator(
            f'.live-layer [id="idsvg-{ordinal}-live-shell-{source_id}"]'
        )

    def _assert_clean(self, session) -> None:
        self.assert_no_automatic_activity(session)

    def test_real_reference_boots_over_file_and_http_in_both_engines(self) -> None:
        """Catches an audience artifact that requires a server or hides a scene."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode, artifact=self.artifact)
                try:
                    page = session.page
                    self._wait_ready(page)
                    self.assertEqual(
                        page.locator("#idrt-deck-pages > .slide").count(), 8
                    )
                    self.assertEqual(
                        page.locator("[data-slide-id][data-runtime='ready']").count(),
                        4,
                    )
                    self.assertEqual(
                        set(self.reference_scenes), set(INTERACTIVE_SLIDES)
                    )
                    self.assertEqual(
                        page.locator(
                            "#idrt-presenter-chrome [data-page-index]"
                        ).count(),
                        8,
                    )
                    api = page.evaluate(
                        """() => ({
                          keys: Reflect.ownKeys(window.InteractiveDeck),
                          frozen: Object.isFrozen(window.InteractiveDeck),
                          snapshotType: typeof window.InteractiveDeck.snapshot
                        })"""
                    )
                    self.assertEqual(
                        api,
                        {"keys": ["snapshot"], "frozen": True, "snapshotType": "function"},
                    )
                    self._assert_clean(session)
                finally:
                    session.close()

    def test_presenter_keyboard_pointer_touch_overview_help_replay_and_fullscreen_fallback(self) -> None:
        """Catches broken presenter paths or shortcuts that bypass focused controls."""
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.artifact,
                    init_script=FULLSCREEN_UNAVAILABLE,
                )
                page = session.page
                try:
                    self._wait_ready(page)

                    page.locator("#idrt-heading-1").focus()
                    page.keyboard.press("ArrowRight")
                    self.assertEqual(self._snapshot(page)["currentSlide"], 2)

                    page.locator(
                        '#idrt-presenter-chrome [data-page-index="3"]'
                    ).click()
                    self.assertEqual(self._snapshot(page)["currentSlide"], 3)

                    frame = page.locator("#idrt-page-3 .frame")
                    box = frame.bounding_box()
                    assert box is not None
                    page.mouse.click(
                        box["x"] + box["width"] * 0.9,
                        box["y"] + box["height"] * 0.5,
                    )
                    page.wait_for_function(
                        "() => window.InteractiveDeck.snapshot().currentSlide === 4"
                    )

                    touch_result = page.locator("#idrt-page-4 .frame").evaluate(
                        """frame => {
                          const box = frame.getBoundingClientRect();
                          // The right rail now sits inside the slide. Start
                          // on the chart, not on a control that guards swipes.
                          const x = box.left + box.width * .45;
                          const y = box.top + box.height * .50;
                          for (const dx of [0, -64]) {
                            const target = document.elementFromPoint(x + dx, y);
                            if (!target || !frame.contains(target) ||
                                target.closest('button,input,select,summary,a[href]')) {
                              throw new Error('Swipe must start and end on the chart');
                            }
                          }
                          const emit = (type, dx) => frame.dispatchEvent(
                            new PointerEvent(type, {
                              bubbles: true, pointerId: 47, isPrimary: true,
                              pointerType: 'touch',
                              clientX: x + dx, clientY: y
                            })
                          );
                          emit('pointerdown', 0);
                          emit('pointerup', -64);
                          return true;
                        }"""
                    )
                    self.assertTrue(touch_result)
                    page.wait_for_function(
                        "() => window.InteractiveDeck.snapshot().currentSlide === 5"
                    )

                    adoption = self._scene(
                        page, "relay-adoption-value"
                    ).locator('input[data-control-id="adoption"]')
                    adoption.evaluate(
                        """input => {
                          const box = input.getBoundingClientRect();
                          for (const [type, dx] of [['pointerdown', 0], ['pointerup', -64]]) {
                            input.dispatchEvent(new PointerEvent(type, {
                              bubbles: true, pointerId: 48, isPrimary: true,
                              pointerType: 'touch', clientX: box.left + box.width / 2 + dx,
                              clientY: box.top + box.height / 2
                            }));
                          }
                        }"""
                    )
                    self.assertEqual(self._snapshot(page)["currentSlide"], 5)
                    adoption.focus()
                    page.keyboard.press("ArrowLeft")
                    self.assertEqual(
                        self._page_state(page, "relay-adoption-value")["inputs"]["adoption"],
                        "50",
                    )
                    page.keyboard.press("Alt+O")
                    self.assertTrue(page.locator("#idrt-presenter-overview").is_hidden())

                    page.locator('[data-presenter-action="replay"]').click()
                    self.assertEqual(
                        self._page_state(page, "relay-adoption-value")["inputs"]["adoption"],
                        "55",
                    )

                    page.locator("#idrt-heading-5").focus()
                    page.keyboard.press("Alt+O")
                    overview = page.locator("#idrt-presenter-overview")
                    self.assertTrue(overview.is_visible())
                    self.assertEqual(
                        overview.locator("button[data-overview-slide]").count(), 8
                    )
                    overview.locator('button[data-overview-slide="6"]').click()
                    self.assertEqual(self._snapshot(page)["currentSlide"], 6)

                    help_button = page.locator('[data-presenter-action="help"]')
                    help_button.focus()
                    help_button.click()
                    help_dialog = page.locator("#idrt-presenter-help")
                    self.assertTrue(help_dialog.is_visible())
                    self.assertIn("Alt+D", help_dialog.inner_text())
                    page.keyboard.press("Escape")
                    self.assertTrue(help_dialog.is_hidden())
                    self.assertTrue(
                        help_button.evaluate("node => node === document.activeElement")
                    )

                    fullscreen = page.locator('[data-presenter-action="fullscreen"]')
                    fullscreen.click()
                    page.wait_for_function(
                        """() => document.documentElement.classList.contains(
                          'idrt-local-fullscreen'
                        ) && document.documentElement.dataset.fullscreenMode === 'local'"""
                    )
                    fullscreen.click()
                    page.wait_for_function(
                        """() => !document.documentElement.classList.contains(
                          'idrt-local-fullscreen'
                        )"""
                    )
                    self._assert_clean(session)
                finally:
                    session.close()

    def test_page_three_evidence_and_page_four_ranking_are_accessible_and_stable(self) -> None:
        """Catches a disclosure focus leak or recreated/floating ranked marks."""
        expected = {
            "base": {"north": (1, "86"), "central": (2, "78"), "east": (3, "73")},
            "constrained": {"north": (1, "82"), "east": (2, "76"), "central": (3, "64")},
        }
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=self.artifact)
                page = session.page
                try:
                    self._wait_ready(page)
                    self._activate(page, "relay-late-job-evidence")
                    opener = page.locator("#idrt-evidence-open-3")
                    opener.focus()
                    opener.press("Enter")
                    dialog = page.locator("#idrt-evidence-dialog-3")
                    self.assertTrue(dialog.is_visible())
                    self.assertEqual(opener.get_attribute("aria-expanded"), "true")
                    self.assertIn("Illustrative", dialog.inner_text())
                    self.assertIn("1,200", dialog.inner_text())

                    close = page.locator("#idrt-evidence-close-3")
                    self.assertTrue(close.evaluate("node => node === document.activeElement"))
                    close.press("Shift+Tab")
                    self.assertTrue(
                        dialog.evaluate("node => node.contains(document.activeElement)")
                    )
                    page.keyboard.press("Tab")
                    self.assertTrue(close.evaluate("node => node === document.activeElement"))

                    assumptions = dialog.locator(
                        '[role="tab"][data-evidence-tab="assumptions"]'
                    )
                    assumptions.click()
                    self.assertEqual(assumptions.get_attribute("aria-selected"), "true")
                    self.assertIn("evidence=assumptions", page.evaluate("() => location.hash"))
                    self.assertIn("61", dialog.inner_text())
                    self.assertIn("24", dialog.inner_text())
                    self.assertIn("15", dialog.inner_text())
                    assumptions.press("ArrowLeft")
                    sources = dialog.locator(
                        '[role="tab"][data-evidence-tab="sources"]'
                    )
                    self.assertEqual(sources.get_attribute("aria-selected"), "true")
                    page.keyboard.press("Escape")
                    self.assertTrue(dialog.is_hidden())
                    self.assertTrue(opener.evaluate("node => node === document.activeElement"))

                    self._activate(page, "relay-route-priority")
                    scene = self._scene(page, "relay-route-priority")
                    marks = {
                        item: self._live_node(page, "relay-route-priority", f"LiveMark-{item}")
                        for item in ("north", "central", "east")
                    }
                    handles = {item: locator.element_handle() for item, locator in marks.items()}
                    self.assertTrue(all(handles.values()))
                    anchors = {
                        name: self._svg_anchor(
                            self._live_node(page, "relay-route-priority", name)
                        )
                        for name in ("LiveDomainStart", "LiveDomainEnd")
                    }

                    def observed_rank() -> dict[str, tuple[int, str]]:
                        self._set_data_details(page, "relay-route-priority", opened=True)
                        rows = scene.locator('[data-view-component="ranked_list"] .view-item')
                        result = {}
                        for row in rows.all():
                            item_id = row.get_attribute("data-view-item-id")
                            assert item_id is not None
                            result[item_id] = (
                                int(row.locator("[data-view-rank]").inner_text()),
                                row.locator("[data-view-metric]").inner_text().split()[0],
                            )
                        self._set_data_details(page, "relay-route-priority", opened=False)
                        return result

                    self.assertEqual(observed_rank(), expected["base"])
                    base_narration = page.locator("#idrt-status-4").inner_text()
                    scene.locator(
                        '[data-control-id="route-scenario"] '
                        'button[data-control-value="constrained"]'
                    ).click()
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="relay-route-priority"] ' +
                          '[data-control-value="constrained"]'
                        )?.getAttribute('aria-pressed') === 'true'"""
                    )
                    self.assertEqual(observed_rank(), expected["constrained"])
                    self.assertNotEqual(page.locator("#idrt-status-4").inner_text(), base_narration)
                    for name, before in anchors.items():
                        self.assertEqual(
                            self._svg_anchor(
                                self._live_node(page, "relay-route-priority", name)
                            ),
                            before,
                        )
                    for item, handle in handles.items():
                        assert handle is not None
                        self.assertTrue(
                            handle.evaluate(
                                "(node, id) => node === document.getElementById(id)",
                                marks[item].get_attribute("id"),
                            )
                        )

                    page.evaluate(
                        "() => { location.hash = '#slide=4&route-scenario=constrained'; }"
                    )
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="relay-route-priority"] ' +
                          '[data-control-value="constrained"]'
                        )?.getAttribute('aria-pressed') === 'true'"""
                    )
                    self.assertEqual(observed_rank(), expected["constrained"])
                    self._assert_clean(session)
                finally:
                    session.close()

    def test_page_five_exact_gate_deep_link_static_and_reset_contract(self) -> None:
        """Catches float drift, wrong threshold polarity, or split live/static truth."""
        cases = (
            ("30", "0.3", "notMet", "Hold"),
            ("50", "1.5", "notMet", "Hold"),
            ("55", "1.8", "met", "Proceed"),
            ("60", "2.1", "met", "Proceed"),
            ("80", "3.3", "met", "Proceed"),
        )
        slide_id = "relay-adoption-value"
        output_id = self.compiled_scenes[slide_id]["reporting"]["primaryOutput"]
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=self.artifact)
                page = session.page
                try:
                    self._wait_ready(page)
                    self._activate(page, slide_id)
                    view = self.compiled_scenes[slide_id]["view"]
                    self.assertEqual(view["xDomain"], ["30", "80"])
                    self.assertEqual(view["yDomain"], ["0", "4"])
                    chart = self._live_node(page, slide_id, "LiveChartBand")
                    fixed_axes = chart.locator("line").evaluate_all(
                        """nodes => nodes.map(node => ({
                          x1: node.getAttribute('x1'), y1: node.getAttribute('y1'),
                          x2: node.getAttribute('x2'), y2: node.getAttribute('y2')
                        }))"""
                    )
                    point = self._live_node(page, slide_id, "annual-value-point")
                    point_handle = point.element_handle()
                    assert point_handle is not None

                    for adoption, value, outcome, status in cases:
                        with self.subTest(engine=engine, adoption=adoption):
                            self._set_range(page, slide_id, "adoption", adoption)
                            state = self._page_state(page, slide_id)
                            self.assertEqual(state["outputs"][output_id], value)
                            self.assertEqual(state["outcome"], outcome)
                            self.assertEqual(
                                self._scene(page, slide_id).locator(
                                    "[data-decision-status]"
                                ).inner_text(),
                                status,
                            )
                            self.assertEqual(
                                chart.locator("line").evaluate_all(
                                    """nodes => nodes.map(node => ({
                                      x1: node.getAttribute('x1'), y1: node.getAttribute('y1'),
                                      x2: node.getAttribute('x2'), y2: node.getAttribute('y2')
                                    }))"""
                                ),
                                fixed_axes,
                            )
                            self.assertTrue(
                                point_handle.evaluate(
                                    "(node, id) => node === document.getElementById(id)",
                                    point.get_attribute("id"),
                                )
                            )

                    page.evaluate(
                        "() => { location.hash = '#slide=5&adoption=58'; }"
                    )
                    page.wait_for_function(
                        """() => window.InteractiveDeck.snapshot().pages[4]
                          .inputs.adoption === '60'"""
                    )
                    self.assertEqual(
                        self._page_state(page, slide_id)["outputs"][output_id], "2.1"
                    )
                    page.evaluate(
                        "() => { location.hash = '#slide=5&adoption=999'; }"
                    )
                    page.wait_for_function(
                        """() => window.InteractiveDeck.snapshot().pages[4]
                          .inputs.adoption === '80'"""
                    )

                    self._set_range(page, slide_id, "adoption", "60")
                    toggle = page.locator("#idrt-static-toggle-5")
                    toggle.click()
                    self.assertEqual(
                        self._page_state(page, slide_id)["viewMode"], "static"
                    )
                    self.assertEqual(
                        self._scene(page, slide_id).locator(
                            f'[data-live-value="{output_id}"]'
                        ).inner_text(),
                        "$1.8m",
                    )
                    self.assertTrue(
                        self._scene(page, slide_id).locator(".fallback-layer").is_visible()
                    )
                    toggle.click()
                    self.assertEqual(
                        self._page_state(page, slide_id)["viewMode"], "live"
                    )
                    self.assertEqual(
                        self._page_state(page, slide_id)["outputs"][output_id], "2.1"
                    )
                    page.locator("#idrt-reset-5").click()
                    reset = self._page_state(page, slide_id)
                    self.assertEqual(reset["inputs"], {"adoption": "55"})
                    self.assertEqual(reset["outputs"][output_id], "1.8")
                    self._assert_clean(session)
                finally:
                    session.close()

    def test_page_six_score_classes_decision_witnesses_and_atomic_restore(self) -> None:
        """Catches a band gap, wrong binary decision, or partial multi-input restore."""
        slide_id = "relay-readiness-score"
        cases = (
            (
                {"frequency": "6", "data-quality": "basic", "manager-capacity": "unavailable", "integration-depth": "none"},
                "16",
                "Defer",
                "notMet",
            ),
            (
                {"frequency": "24", "data-quality": "standard", "manager-capacity": "unavailable", "integration-depth": "core"},
                "54",
                "Prepare",
                "notMet",
            ),
            (
                {"frequency": "30", "data-quality": "standard", "manager-capacity": "unavailable", "integration-depth": "full"},
                "70",
                "Pilot-ready",
                "met",
            ),
            (
                {"frequency": "24", "data-quality": "standard", "manager-capacity": "available", "integration-depth": "core"},
                "72",
                "Pilot-ready",
                "met",
            ),
            (
                {"frequency": "30", "data-quality": "complete", "manager-capacity": "available", "integration-depth": "full"},
                "98",
                "Pilot-ready",
                "met",
            ),
        )
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=self.artifact)
                page = session.page
                try:
                    self._wait_ready(page)
                    self._activate(page, slide_id)
                    scene = self._scene(page, slide_id)
                    for inputs, score, classification, outcome in cases:
                        with self.subTest(engine=engine, score=score):
                            self._set_score_inputs(page, inputs)
                            state = self._page_state(page, slide_id)
                            self.assertEqual(state["outputs"]["score"], score)
                            self.assertEqual(state["outcome"], outcome)
                            self.assertEqual(
                                scene.locator(
                                    '[data-live-value="classification"]'
                                ).inner_text(),
                                classification,
                            )
                            self.assertEqual(
                                scene.locator("[data-decision-status]").count(), 1
                            )

                    fragment = (
                        "#slide=6&frequency=30&data-quality=standard&"
                        "manager-capacity=unavailable&integration-depth=full"
                    )
                    page.evaluate("fragment => { location.hash = fragment; }", fragment)
                    page.wait_for_function(
                        """() => window.InteractiveDeck.snapshot().pages[5]
                          .outputs.score === '70'"""
                    )
                    restored = self._page_state(page, slide_id)
                    self.assertEqual(
                        restored["inputs"],
                        {"frequency": "30"},
                    )
                    self.assertEqual(
                        scene.locator(
                            '[data-control-id="data-quality"] '
                            'button[aria-pressed="true"]'
                        ).get_attribute("data-control-value"),
                        "standard",
                    )
                    self.assertEqual(
                        scene.locator(
                            '[data-control-id="manager-capacity"] '
                            'button[aria-pressed="true"]'
                        ).get_attribute("data-control-value"),
                        "unavailable",
                    )
                    self.assertEqual(
                        scene.locator(
                            '[data-control-id="integration-depth"] select'
                        ).input_value(),
                        "full",
                    )
                    self.assertEqual(restored["outcome"], "met")
                    self.assertEqual(
                        scene.locator(
                            '[data-live-value="classification"]'
                        ).inner_text(),
                        "Pilot-ready",
                    )
                    self._assert_clean(session)
                finally:
                    session.close()

    def test_independent_drilldown_accordion_and_tooltip_fixtures(self) -> None:
        """Accordion Arrow/Escape guard state; Tab is native, Space/Enter toggle."""
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine, fixture="drilldown"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.fixture_artifacts["drilldown"],
                )
                page = session.page
                try:
                    self._wait_ready(page)
                    scene = page.locator('[data-slide-id="fixture-drilldown"]')
                    before_history = page.evaluate("() => history.length")
                    opener = scene.locator(
                        '[data-action="open-panel"][data-panel-target="method"]'
                    )
                    self.assertEqual(opener.get_attribute("data-target-key"), "panel:method")
                    opener.focus()
                    opener.press("Enter")
                    panel = scene.locator('[data-panel-id="method"]')
                    self.assertTrue(panel.is_visible())
                    self.assertIn("panel=method", page.evaluate("() => location.hash"))
                    self.assertEqual(page.evaluate("() => history.length"), before_history)
                    close = panel.locator(
                        '[data-action="close-panel"][data-panel-target="method"]'
                    )
                    self.assertEqual(
                        close.get_attribute("data-target-key"), "panel:method:close"
                    )
                    close.press("Enter")
                    self.assertTrue(panel.is_hidden())
                    self.assertTrue(opener.evaluate("node => node === document.activeElement"))
                    self.assertNotIn("panel=", page.evaluate("() => location.hash"))

                    page.evaluate(
                        "() => { location.hash = '#slide=1&panel=boundary'; }"
                    )
                    scene.locator('[data-panel-id="boundary"]').wait_for(
                        state="visible"
                    )
                    scene.locator("#idrt-static-toggle-1").click()
                    self.assertTrue(scene.locator(".fallback-layer").is_visible())
                    self._assert_clean(session)
                finally:
                    session.close()

            with self.subTest(engine=engine, fixture="accordion"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.fixture_artifacts["accordion"],
                )
                page = session.page
                try:
                    self._wait_ready(page)
                    scene = page.locator('[data-slide-id="fixture-accordion"]')
                    handoff = scene.locator('[data-accordion-id="handoff"]')
                    exception = scene.locator('[data-accordion-id="exception"]')
                    owner = scene.locator('[data-accordion-id="owner"]')
                    handoff.focus()
                    handoff.press("Tab")
                    self.assertTrue(
                        exception.evaluate("node => node === document.activeElement")
                    )
                    exception.press("ArrowRight")
                    self.assertTrue(
                        exception.evaluate("node => node === document.activeElement")
                    )
                    self.assertEqual(
                        self._snapshot(page)["currentSlide"], 1
                    )
                    exception.press("Space")
                    self.assertEqual(exception.get_attribute("aria-expanded"), "true")
                    self.assertEqual(handoff.get_attribute("aria-expanded"), "false")
                    owner.focus()
                    owner.press("Enter")
                    self.assertEqual(owner.get_attribute("aria-expanded"), "true")
                    self.assertEqual(exception.get_attribute("aria-expanded"), "false")
                    self.assertIn("panel=owner", page.evaluate("() => location.hash"))
                    owner.press("Escape")
                    self.assertEqual(owner.get_attribute("aria-expanded"), "true")
                    self.assertTrue(owner.evaluate("node => node === document.activeElement"))
                    owner.press("Space")
                    self.assertEqual(owner.get_attribute("aria-expanded"), "false")
                    self.assertNotIn("panel=", page.evaluate("() => location.hash"))
                    page.evaluate(
                        "() => { location.hash = '#slide=1&panel=handoff'; }"
                    )
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-accordion-id="handoff"]'
                        )?.getAttribute('aria-expanded') === 'true'"""
                    )
                    scene.locator("#idrt-static-toggle-1").click()
                    self.assertTrue(scene.locator(".fallback-layer").is_visible())
                    page.emulate_media(media="print")
                    self.assertTrue(scene.locator(".fallback-layer").is_visible())
                    page.emulate_media(media="screen")
                    self._assert_clean(session)
                finally:
                    session.close()

            with self.subTest(engine=engine, fixture="tooltip"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.fixture_artifacts["tooltip"],
                )
                page = session.page
                try:
                    self._wait_ready(page)
                    scene = page.locator('[data-slide-id="fixture-tooltip"]')
                    self._set_data_details(page, "fixture-tooltip", opened=True)
                    trigger = scene.locator(
                        '[data-tooltip-for="lookup-result"]'
                    ).first
                    tooltip = page.locator(
                        f'#{trigger.get_attribute("aria-controls")}'
                    )
                    before = self._snapshot(page)

                    trigger.hover()
                    trigger.click()
                    self.assertTrue(tooltip.is_visible())
                    self.assertEqual(self._snapshot(page), before)
                    page.locator("body").click(position={"x": 2, "y": 2})
                    self.assertTrue(tooltip.is_hidden())

                    trigger.focus()
                    trigger.press("Enter")
                    self.assertTrue(tooltip.is_visible())
                    page.keyboard.press("Escape")
                    self.assertTrue(tooltip.is_hidden())
                    self.assertTrue(trigger.evaluate("node => node === document.activeElement"))

                    trigger.dispatch_event(
                        "pointerdown", {"pointerType": "touch", "pointerId": 81}
                    )
                    trigger.dispatch_event(
                        "pointerup", {"pointerType": "touch", "pointerId": 81}
                    )
                    trigger.dispatch_event("click", {"detail": 1})
                    self.assertTrue(tooltip.is_visible())
                    page.locator("body").dispatch_event(
                        "pointerdown", {"pointerType": "touch", "pointerId": 82}
                    )
                    self.assertTrue(tooltip.is_hidden())

                    self._set_data_details(page, "fixture-tooltip", opened=False)
                    self._set_range(page, "fixture-tooltip", "complexity", "3")
                    self._set_data_details(page, "fixture-tooltip", opened=True)
                    trigger.focus()
                    trigger.press("Enter")
                    self.assertIn("13", tooltip.inner_text())
                    geometry = page.evaluate(
                        """() => {
                          const rect = node => {
                            const value = node.getBoundingClientRect();
                            return {left: value.left, top: value.top,
                              right: value.right, bottom: value.bottom};
                          };
                          return {
                            tooltip: rect(document.querySelector('[role="tooltip"]:not([hidden])')),
                            details: rect(document.querySelector('.data-details[open]')),
                            assertion: rect(document.querySelector('[data-slide-id="fixture-tooltip"] h1')),
                            primary: rect(document.querySelector('[data-slide-id="fixture-tooltip"] [data-live-value]'))
                          };
                        }"""
                    )
                    self.assertFalse(_rects_overlap(geometry["tooltip"], geometry["assertion"]))
                    self.assertFalse(_rects_overlap(geometry["tooltip"], geometry["primary"]))
                    # The desktop data disclosure replaces the rail visually.
                    # Keep its tooltip inside that surface and do not allow
                    # keyboard focus to disappear into covered controls.
                    for edge in ("left", "top"):
                        self.assertGreaterEqual(geometry["tooltip"][edge], geometry["details"][edge])
                    for edge in ("right", "bottom"):
                        self.assertLessEqual(geometry["tooltip"][edge], geometry["details"][edge])
                    trigger.press("Tab")
                    self.assertFalse(page.evaluate(
                        "() => !!document.activeElement.closest('.control-rail')"
                    ))
                    self._set_data_details(page, "fixture-tooltip", opened=False)
                    control = scene.locator('input[data-control-id="complexity"]')
                    control.focus()
                    self.assertTrue(control.evaluate(
                        """node => {
                          const box = node.getBoundingClientRect();
                          return node === document.activeElement && node === document.elementFromPoint(
                            box.left + box.width / 2, box.top + box.height / 2
                          );
                        }"""
                    ))
                    self._assert_clean(session)
                finally:
                    session.close()

    def test_curated_demo_exact_steps_can_cancel_and_finishes_in_overview(self) -> None:
        """Catches missing demo targets, stale callbacks, or catalogue-like extra steps."""
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine, phase="cancel"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.artifact,
                    reduced_motion="reduce",
                    init_script=DEMO_RECORDER,
                )
                page = session.page
                try:
                    self._wait_ready(page)
                    demo = page.locator('[data-presenter-action="demo"]')
                    demo.click()
                    page.wait_for_function(
                        "() => window.__REFERENCE_DEMO__.steps.length >= 1",
                        timeout=5_000,
                    )
                    # Any real presenter key cancels at capture time.  Escape
                    # remains reachable even while the first evidence step has
                    # made the presenter chrome inert.
                    page.keyboard.press("Escape")
                    page.wait_for_function(
                        """() => window.__REFERENCE_DEMO__.ends.some(
                          item => item.detail.reason === 'cancelled'
                        )""",
                        timeout=5_000,
                    )
                    cancelled = page.evaluate(
                        """() => ({
                          steps: window.__REFERENCE_DEMO__.steps.length,
                          ends: window.__REFERENCE_DEMO__.ends.length
                        })"""
                    )
                    time.sleep(0.5)
                    self.assertEqual(
                        page.evaluate(
                            """() => ({
                              steps: window.__REFERENCE_DEMO__.steps.length,
                              ends: window.__REFERENCE_DEMO__.ends.length
                            })"""
                        ),
                        cancelled,
                    )
                    self.assertEqual(demo.get_attribute("aria-pressed"), "false")
                    self.assertTrue(page.locator("#idrt-demo-cue").is_hidden())
                    self._assert_clean(session)
                finally:
                    session.close()

            with self.subTest(engine=engine, phase="complete"):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.artifact,
                    reduced_motion="reduce",
                    init_script=DEMO_RECORDER,
                )
                page = session.page
                try:
                    self._wait_ready(page)
                    page.locator('[data-presenter-action="demo"]').click()
                    page.wait_for_function(
                        """() => window.__REFERENCE_DEMO__.ends.some(
                          item => item.detail.reason === 'complete'
                        )""",
                        timeout=10_000,
                    )
                    records = page.evaluate("() => window.__REFERENCE_DEMO__")
                    observed = tuple(
                        (item["detail"]["slideId"], item["detail"]["stepKey"])
                        for item in records["steps"]
                    )
                    self.assertEqual(observed, EXPECTED_DEMO_STEPS)
                    self.assertEqual(
                        len({item["detail"]["stepKey"] for item in records["steps"]}),
                        6,
                    )
                    for item in records["steps"]:
                        target_key = item["detail"].get("targetKey")
                        self.assertIsNotNone(target_key)
                        self.assertEqual(
                            page.locator(
                                f'[data-target-slide="{item["detail"]["slideId"]}"]'
                                f'[data-target-key="{target_key}"]'
                            ).count(),
                            1,
                        )
                    self.assertTrue(page.locator("#idrt-presenter-overview").is_visible())
                    self.assertEqual(
                        page.locator('[data-presenter-action="demo"]').get_attribute(
                            "aria-pressed"
                        ),
                        "false",
                    )
                    self.assertTrue(page.locator("#idrt-demo-cue").is_hidden())
                    self._assert_clean(session)
                finally:
                    session.close()

    def test_audit_reconstructs_targets_boundaries_classes_outcomes_and_demo_steps(self) -> None:
        """Catches a reference whose author audit leaves a declared state unproved."""
        destination = self.fixture_root / "project-relay-audit"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                str(AUDIT_SCRIPT),
                "--manifest",
                str(REFERENCE_MANIFEST),
                "--audit-out",
                str(destination),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=240,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        ledger = json.loads(
            (destination / "audit-ledger.json").read_text(encoding="utf-8")
        )
        self.assertEqual(ledger["deck"]["slideCount"], 8)
        self.assertEqual(
            {entry["sceneType"] for entry in ledger["slides"]},
            {"static", "evidence_only", "state_toggle", "slider_model", "score_model"},
        )
        obligations = {
            obligation
            for state in ledger["states"]
            for obligation in state["obligations"]
        }
        self.assertTrue(
            {
                "static",
                "reduced-motion",
                "overview-after-change",
                "evidence:sources",
                "evidence:assumptions",
                "evidence:both",
                "option:route-scenario:constrained",
                "range:adoption:min",
                "range:adoption:max",
                "boundary:output:score:16:exact",
                "boundary:output:score:16:above",
                "boundary:output:score:50:below",
                "boundary:output:score:50:exact",
                "boundary:output:score:50:above",
                "boundary:output:score:70:below",
                "boundary:output:score:70:exact",
                "boundary:output:score:70:above",
                "boundary:output:score:98:below",
                "boundary:output:score:98:exact",
                "classification:Defer",
                "classification:Prepare",
                "classification:Pilot-ready",
                "decision:notMet",
                "decision:met",
                "decision:exact",
            }.issubset(obligations),
            sorted(obligations),
        )
        slide_ledger = {entry["slideId"]: entry for entry in ledger["slides"]}
        adoption = slide_ledger["relay-adoption-value"]
        self.assertEqual(
            adoption["controls"][0]["acceptedValues"],
            [str(value) for value in range(30, 81, 5)],
        )
        self.assertEqual(
            {
                key: witness["state"]["adoption"]
                for key, witness in adoption["decisionWitnesses"].items()
            },
            {"notMet": "50", "met": "55", "exact": "55"},
        )
        readiness = slide_ledger["relay-readiness-score"]
        self.assertEqual(readiness["acceptedStateCount"], 90)
        self.assertEqual(
            set(readiness["classificationWitnesses"]),
            {"Defer", "Prepare", "Pilot-ready"},
        )
        self.assertEqual(
            {
                (entry["slideId"], entry["stepKey"])
                for entry in ledger["stepCoverage"]
            },
            set(EXPECTED_DEMO_STEPS),
        )
        envelope_targets = {
            (slide["slideId"], target_key)
            for slide in self.envelope["slides"]
            if slide["scene"] is not None
            for target_key in slide["scene"]["targets"]
        }
        self.assertEqual(
            {
                (entry["slideId"], entry["targetKey"])
                for entry in ledger["targetCoverage"]
            },
            envelope_targets,
        )
        self.assertTrue(ledger["states"])
        for state in ledger["states"]:
            reconstruction = state["reconstruction"]
            self.assertEqual(reconstruction["networkRequests"], [])
            self.assertEqual(reconstruction["consoleErrors"], [])
            self.assertTrue(reconstruction["runtimeReady"])
            self.assertTrue(reconstruction["staticParity"])
            self.assertEqual(len(reconstruction["pngSha256"]), 64)
        self.assertLess(len(ledger["states"]), 512)

    def test_supported_viewports_zoom_targets_and_portrait_typography_do_not_clip(self) -> None:
        """Catches a responsive layout that makes required content unreachable."""
        viewports = (
            (390, 844),
            (844, 390),
            (1280, 720),
            (1440, 900),
        )
        for engine in ("chromium", "firefox"):
            for width, height in viewports:
                with self.subTest(engine=engine, viewport=(width, height)):
                    session = self.open_deck(
                        engine,
                        "http",
                        artifact=self.artifact,
                        viewport={"width": width, "height": height},
                    )
                    page = session.page
                    try:
                        self._wait_ready(page)
                        self.assertLessEqual(
                            page.evaluate(
                                """() => document.documentElement.scrollWidth -
                                  document.documentElement.clientWidth"""
                            ),
                            1,
                        )
                        for slide_id in INTERACTIVE_SLIDES:
                            self._activate(page, slide_id)
                            scene = self._scene(page, slide_id)
                            self.assertEqual(scene.locator(".control-rail").count(), 1)
                            # The paired comparison places its controls above
                            # and below the figure. Its display:contents rail
                            # deliberately has no box; test the actual scenario
                            # fieldset and every focusable target instead.
                            rank_bridge = scene.get_attribute("data-visual-layout") == "rank_bridge"
                            controls_selector = ".control-rail > .option-control" if rank_bridge else ".control-rail"
                            for selector in (
                                "h1",
                                ".semantic-source",
                                controls_selector,
                            ):
                                required = scene.locator(selector)
                                self.assertEqual(required.count(), 1, (slide_id, selector))
                                required.scroll_into_view_if_needed()
                                box = required.bounding_box()
                                self.assertIsNotNone(box, (slide_id, selector))
                                assert box is not None
                                self.assertGreater(box["width"], 0)
                                self.assertGreater(box["height"], 0)
                                self.assertGreater(box["x"], -1)
                                self.assertLessEqual(box["x"] + box["width"], width + 1)

                            targets = scene.locator(
                                "button:visible, input:visible, select:visible, a[href]:visible"
                            )
                            for index in range(targets.count()):
                                box = targets.nth(index).bounding_box()
                                if box is None:
                                    continue
                                # Firefox can report a 44 CSS-pixel target a few
                                # ten-thousandths below 44 after device scaling.
                                self.assertGreaterEqual(box["width"] + 0.01, 44, (slide_id, index, box))
                                self.assertGreaterEqual(box["height"] + 0.01, 44, (slide_id, index, box))
                                self.assertGreater(box["x"], -1, (slide_id, index, box))
                                self.assertLessEqual(box["x"] + box["width"], width + 1, (slide_id, index, box))

                        if width == 390 and height == 844:
                            self._activate(page, "relay-adoption-value")
                            floors = page.evaluate(
                                """() => {
                                  const scene = document.querySelector(
                                    '[data-slide-id="relay-adoption-value"]'
                                  );
                                  const size = selector => parseFloat(
                                    getComputedStyle(scene.querySelector(selector)).fontSize
                                  );
                                  return {
                                    headline: size('h1'),
                                    primary: size('[data-live-value]'),
                                    source: size('.semantic-source')
                                  };
                                }"""
                            )
                            self.assertGreaterEqual(floors["headline"], 24)
                            self.assertGreaterEqual(floors["primary"], 32)
                            self.assertGreaterEqual(floors["source"], 16)

                        page.evaluate(
                            "() => { document.documentElement.style.zoom = '2'; }"
                        )
                        self._activate(page, "relay-adoption-value")
                        control = self._scene(
                            page, "relay-adoption-value"
                        ).locator('input[data-control-id="adoption"]')
                        page.evaluate(
                            """() => {
                              if (document.activeElement instanceof HTMLElement) {
                                document.activeElement.blur();
                              }
                            }"""
                        )
                        for _ in range(40):
                            page.keyboard.press("Tab")
                            if control.evaluate("node => node === document.activeElement"):
                                break
                        self.assertTrue(
                            control.evaluate("node => node === document.activeElement")
                        )
                        focus = control.evaluate(
                            """node => {
                              const style = getComputedStyle(node);
                              const box = node.getBoundingClientRect();
                              return {
                                visible: node.matches(':focus-visible'),
                                outlineStyle: style.outlineStyle,
                                outlineWidth: parseFloat(style.outlineWidth),
                                width: box.width,
                                height: box.height
                              };
                            }"""
                        )
                        self.assertTrue(focus["visible"])
                        self.assertNotEqual(focus["outlineStyle"], "none")
                        self.assertGreaterEqual(focus["outlineWidth"], 3)
                        self.assertGreaterEqual(focus["width"], 44)
                        self.assertGreaterEqual(focus["height"], 44)
                        self._assert_clean(session)
                    finally:
                        session.close()


if __name__ == "__main__":
    import unittest

    unittest.main()
