"""Chromium visual, transition, PDF, and audit acceptance for Project Relay.

Linux reference screenshots are reviewer-owned fixtures.  A normal test run
never rewrites them.  ``UPDATE_INTERACTIVE_BASELINES=1`` is accepted only on
the pinned Linux/Chromium environment; every other platform writes review
candidates below ignored ``test-results/interactive/``.
"""
from __future__ import annotations

import base64
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from playwright.sync_api import Page, sync_playwright

from base import ENVELOPE_RE, ROOT


DECK_ROOT = ROOT / "examples" / "interactive-deck"
MANIFEST = DECK_ROOT / "deck.json"
ARTIFACT = DECK_ROOT / "deck.interactive.html"
CHECKED_PDF = DECK_ROOT / "deck.pdf"
FIXTURE_ROOT = ROOT / "examples" / "interactive-fixtures"
BUILD_SCRIPT = ROOT / "scripts" / "build_interactive_deck.py"
EXPORT_SCRIPT = ROOT / "scripts" / "export_pdf.py"
AUDIT_SCRIPT = ROOT / "scripts" / "audit_interactive_deck.py"
RESULT_ROOT = ROOT / "test-results" / "interactive"
CANDIDATE_ROOT = RESULT_ROOT / "project-relay-visual-candidates"
DIFF_ROOT = RESULT_ROOT / "project-relay-visual-diffs"
AUDIT_ROOT = RESULT_ROOT / "project-relay-audit"
AUDIT_REPEAT_ROOT = RESULT_ROOT / "project-relay-audit-repeat"
BASELINE_ROOT = ROOT / "tests" / "e2e" / "baselines" / "chromium-linux"

VIEW_DESKTOP = {"width": 1280, "height": 720}
VIEW_PORTRAIT = {"width": 390, "height": 844}
PINNED_CHROMIUM_VERSION = "145.0.7632.6"

# Baseline images come from the same pinned Chromium build at DPR 1.  A pixel
# counts as changed only when one RGB channel moves by more than 12.  At most
# 0.50% of pixels may change and the mean absolute channel delta must stay at
# or below 0.35.  This tolerates bounded antialiasing noise without accepting
# layout, copy, colour, or state drift.
PIXEL_CHANNEL_TOLERANCE = 12
PIXEL_CHANGED_RATIO_LIMIT = 0.005
PIXEL_MEAN_DELTA_LIMIT = 0.35

# Chrome screenshots and Poppler rasters use different antialiasers.  This
# second, still deterministic, threshold is deliberately limited to their
# cross-renderer parity check; geometry is also asserted directly in the DOM.
PDF_CHANNEL_TOLERANCE = 36
PDF_CHANGED_RATIO_LIMIT = 0.12
PDF_MEAN_DELTA_LIMIT = 4.0


def _decode_envelope(path: Path) -> dict:
    match = ENVELOPE_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError("interactive envelope not found")
    token = match.group(2)
    token += "=" * ((4 - len(token) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))


def _png_rgb(path: Path) -> tuple[int, int, bytes]:
    """Decode a non-interlaced 8-bit RGB/RGBA PNG with the stdlib only."""
    payload = path.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"not a PNG: {path}")
    cursor = 8
    width = height = bit_depth = colour_type = interlace = None
    compressed = bytearray()
    while cursor < len(payload):
        length = int.from_bytes(payload[cursor : cursor + 4], "big")
        kind = payload[cursor + 4 : cursor + 8]
        data = payload[cursor + 8 : cursor + 8 + length]
        cursor += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, colour_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if compression != 0 or filtering != 0:
                raise AssertionError("unsupported PNG compression/filter method")
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            break
    if not width or not height or bit_depth != 8 or colour_type not in (2, 6) or interlace != 0:
        raise AssertionError(
            f"unsupported PNG shape: {width}x{height}, depth={bit_depth}, "
            f"colour={colour_type}, interlace={interlace}"
        )
    channels = 3 if colour_type == 2 else 4
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    if len(raw) != height * (stride + 1):
        raise AssertionError("truncated PNG scanlines")
    prior = bytearray(stride)
    rgb = bytearray(width * height * 3)
    source = 0
    target = 0

    def paeth(left: int, up: int, upper_left: int) -> int:
        estimate = left + up - upper_left
        left_distance = abs(estimate - left)
        up_distance = abs(estimate - up)
        diagonal_distance = abs(estimate - upper_left)
        if left_distance <= up_distance and left_distance <= diagonal_distance:
            return left
        if up_distance <= diagonal_distance:
            return up
        return upper_left

    for _row_index in range(height):
        filter_kind = raw[source]
        source += 1
        scanline = bytearray(raw[source : source + stride])
        source += stride
        for index in range(stride):
            left = scanline[index - channels] if index >= channels else 0
            up = prior[index]
            upper_left = prior[index - channels] if index >= channels else 0
            if filter_kind == 1:
                scanline[index] = (scanline[index] + left) & 0xFF
            elif filter_kind == 2:
                scanline[index] = (scanline[index] + up) & 0xFF
            elif filter_kind == 3:
                scanline[index] = (scanline[index] + ((left + up) // 2)) & 0xFF
            elif filter_kind == 4:
                scanline[index] = (
                    scanline[index] + paeth(left, up, upper_left)
                ) & 0xFF
            elif filter_kind != 0:
                raise AssertionError(f"unsupported PNG row filter: {filter_kind}")
        for index in range(0, stride, channels):
            red, green, blue = scanline[index : index + 3]
            if channels == 4:
                alpha = scanline[index + 3]
                red = (red * alpha + 255 * (255 - alpha) + 127) // 255
                green = (green * alpha + 255 * (255 - alpha) + 127) // 255
                blue = (blue * alpha + 255 * (255 - alpha) + 127) // 255
            rgb[target : target + 3] = bytes((red, green, blue))
            target += 3
        prior = scanline
    return width, height, bytes(rgb)


def _png_size(path: Path) -> tuple[int, int]:
    """Read PNG dimensions without decoding every audit-atlas pixel."""
    payload = path.read_bytes()
    if len(payload) < 24 or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"not a PNG: {path}")
    if payload[12:16] != b"IHDR":
        raise AssertionError(f"missing PNG header: {path}")
    return struct.unpack(">II", payload[16:24])


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        len(payload).to_bytes(4, "big")
        + kind
        + payload
        + (zlib.crc32(kind + payload) & 0xFFFFFFFF).to_bytes(4, "big")
    )


def _write_rgb_png(path: Path, width: int, height: int, rgb: bytes) -> None:
    if len(rgb) != width * height * 3:
        raise AssertionError("invalid RGB payload length")
    rows = b"".join(
        b"\x00" + rgb[row * width * 3 : (row + 1) * width * 3]
        for row in range(height)
    )
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(rows, 9))
        + _png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _image_delta(
    actual: Path, expected: Path, *, channel_tolerance: int
) -> tuple[float, float, tuple[int, int], bytes]:
    actual_width, actual_height, actual_rgb = _png_rgb(actual)
    expected_width, expected_height, expected_rgb = _png_rgb(expected)
    if (actual_width, actual_height) != (expected_width, expected_height):
        raise AssertionError(
            f"image size mismatch: actual={actual_width}x{actual_height}, "
            f"expected={expected_width}x{expected_height}"
        )
    pixel_count = actual_width * actual_height
    changed = 0
    delta_sum = 0
    diff = bytearray(len(actual_rgb))
    for offset in range(0, len(actual_rgb), 3):
        deltas = tuple(
            abs(actual_rgb[offset + channel] - expected_rgb[offset + channel])
            for channel in range(3)
        )
        delta_sum += sum(deltas)
        is_changed = max(deltas) > channel_tolerance
        if is_changed:
            changed += 1
            diff[offset : offset + 3] = b"\xff\x00\x52"
        else:
            muted = sum(actual_rgb[offset : offset + 3]) // 9 + 160
            diff[offset : offset + 3] = bytes((muted, muted, muted))
    return (
        changed / pixel_count,
        delta_sum / (pixel_count * 3),
        (actual_width, actual_height),
        bytes(diff),
    )


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def _safe_generated_reset(path: Path) -> None:
    resolved = path.resolve()
    result_root = RESULT_ROOT.resolve()
    if result_root not in resolved.parents or resolved == result_root:
        raise AssertionError(f"refusing to reset non-generated path: {path}")
    if path.exists():
        shutil.rmtree(path)


TRANSITION_SCHEDULER = r"""
(() => {
  let now = 0;
  let nextId = 1;
  const rafs = new Map();
  const timers = new Map();
  const scheduler = {
    now() { return now; },
    setTimeout(callback, delay) {
      const id = nextId++;
      timers.set(id, {callback, delay});
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
    requestAnimationFrame(callback) {
      const id = nextId++;
      rafs.set(id, callback);
      return id;
    },
    cancelAnimationFrame(id) { rafs.delete(id); }
  };
  Object.defineProperty(window, "__IDRT_TEST_SCHEDULER__", {
    configurable: true,
    value: scheduler
  });
  Object.defineProperty(window, "__PROJECT_RELAY_VISUAL_CLOCK__", {
    configurable: false,
    value: Object.freeze({
      stepRaf(milliseconds) {
        now += milliseconds;
        const callbacks = Array.from(rafs.values());
        rafs.clear();
        callbacks.forEach(callback => callback(now));
        return {now, pendingRafs: rafs.size, pendingTimers: timers.size};
      },
      pendingRafs() { return rafs.size; }
    })
  });
})();
"""


class ProjectRelayVisualPdfTests(unittest.TestCase):
    """Uses the checked-in Project Relay artifact; no example-specific hooks."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        required = [MANIFEST, ARTIFACT, CHECKED_PDF]
        required.extend(FIXTURE_ROOT / name / "deck.json" for name in ("drilldown", "accordion", "tooltip"))
        missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
        if missing:
            raise AssertionError("Project Relay artifacts are incomplete: " + ", ".join(missing))

        RESULT_ROOT.mkdir(parents=True, exist_ok=True)
        CANDIDATE_ROOT.mkdir(parents=True, exist_ok=True)
        DIFF_ROOT.mkdir(parents=True, exist_ok=True)
        for root in (CANDIDATE_ROOT, DIFF_ROOT):
            for png in root.glob("*.png"):
                png.unlink()

        cls.temp = tempfile.TemporaryDirectory(prefix="project-relay-visual-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.temp_root = Path(cls.temp.name)
        cls.fixture_artifacts: dict[str, Path] = {}
        for name in ("drilldown", "accordion", "tooltip"):
            output = cls.temp_root / f"{name}.interactive.html"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(BUILD_SCRIPT),
                    "--manifest",
                    str(FIXTURE_ROOT / name / "deck.json"),
                    "-o",
                    str(output),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode:
                raise AssertionError(f"{name} fixture build failed: {completed.stderr.strip()}")
            cls.fixture_artifacts[name] = output

        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.browser.close)
        cls.chromium_version = cls.browser.version
        cls.chromium_executable = cls.playwright.chromium.executable_path
        cls.envelope = _decode_envelope(ARTIFACT)
        cls._candidates: dict[str, Path] | None = None

    def _open(
        self,
        *,
        artifact: Path = ARTIFACT,
        viewport: dict[str, int] = VIEW_DESKTOP,
        reduced_motion: str = "no-preference",
        init_script: str | None = None,
    ) -> tuple[object, Page]:
        context = self.browser.new_context(
            viewport=viewport,
            device_scale_factor=1,
            reduced_motion=reduced_motion,
        )
        if init_script is not None:
            context.add_init_script(init_script)
        page = context.new_page()
        try:
            page.goto(artifact.resolve().as_uri(), wait_until="load")
            page.wait_for_selector('html[data-interactive-runtime="ready"]')
        except BaseException:
            context.close()
            raise
        return context, page

    def _activate(self, page: Page, ordinal: int, parameters: str = "") -> None:
        fragment = f"#slide={ordinal}" + (("&" + parameters) if parameters else "")
        page.evaluate("fragment => { location.hash = fragment; }", fragment)
        page.wait_for_function(
            "ordinal => window.InteractiveDeck.snapshot().currentSlide === ordinal",
            arg=ordinal,
        )

    def _set_control(self, page: Page, slide_id: str, control_id: str, value: str) -> None:
        section = page.locator(f'[data-slide-id="{slide_id}"]')
        wrapper = section.locator(f'[data-control-id="{control_id}"]')
        select = wrapper.locator("select")
        range_input = section.locator(
            f'input[type="range"][data-control-id="{control_id}"]'
        )
        option = wrapper.locator(f'[data-control-value="{value}"]')
        if select.count():
            select.select_option(value)
            page.wait_for_function(
                """args => document.querySelector(
                  `[data-slide-id="${args.slideId}"] [data-control-id="${args.controlId}"] select`
                )?.value === args.value""",
                arg={"slideId": slide_id, "controlId": control_id, "value": value},
            )
        elif range_input.count():
            compiled = next(
                slide["scene"]
                for slide in self.envelope["slides"]
                if slide["slideId"] == slide_id
            )
            control = next(
                item for item in compiled["controls"] if item["id"] == control_id
            )
            index = (Decimal(value) - Decimal(control["min"])) / Decimal(control["step"])
            self.assertEqual(index, index.to_integral_value())
            range_input.evaluate(
                "(node, next) => { node.value = next; node.dispatchEvent(new Event('input', {bubbles: true})); }",
                str(index.to_integral_value()),
            )
            ordinal = next(
                index
                for index, slide in enumerate(self.envelope["slides"], start=1)
                if slide["slideId"] == slide_id
            )
            page.wait_for_function(
                """args => window.InteractiveDeck.snapshot().pages[args.ordinal - 1]
                  .inputs[args.controlId] === args.value""",
                arg={"ordinal": ordinal, "controlId": control_id, "value": value},
            )
        elif option.count():
            option.click()
            page.wait_for_function(
                """args => document.querySelector(
                  `[data-slide-id="${args.slideId}"] [data-control-id="${args.controlId}"] ` +
                  `[data-control-value="${args.value}"]`
                )?.getAttribute('aria-pressed') === 'true'""",
                arg={"slideId": slide_id, "controlId": control_id, "value": value},
            )
        else:
            self.fail(f"control value is not reachable: {slide_id}/{control_id}={value}")

    def _capture(
        self,
        name: str,
        *,
        ordinal: int = 1,
        viewport: dict[str, int] = VIEW_DESKTOP,
        reduced_motion: str = "no-preference",
        parameters: str = "",
        mutate=None,
        artifact: Path = ARTIFACT,
    ) -> Path:
        context, page = self._open(
            artifact=artifact,
            viewport=viewport,
            reduced_motion=reduced_motion,
        )
        try:
            self._activate(page, ordinal, parameters)
            if mutate is not None:
                mutate(page)
            page.wait_for_timeout(320)
            output = CANDIDATE_ROOT / f"{name}.png"
            page.screenshot(path=str(output), animations="disabled", caret="hide")
            width, height, rgb = _png_rgb(output)
            self.assertEqual((width, height), (viewport["width"], viewport["height"]))
            self.assertGreater(
                sum(1 for offset in range(0, len(rgb), 3) if rgb[offset : offset + 3] != b"\xff\xff\xff"),
                width * height // 100,
                f"blank-looking candidate: {name}",
            )
            return output
        finally:
            context.close()

    def _ensure_candidates(self) -> dict[str, Path]:
        if self.__class__._candidates is not None:
            return self.__class__._candidates

        def open_evidence(page: Page) -> None:
            page.locator('[data-slide-id="relay-late-job-evidence"] [data-action="evidence"]').click()
            page.locator(".evidence-dialog:not([hidden])").wait_for(state="visible")

        def choose_constrained(page: Page) -> None:
            self._set_control(page, "relay-route-priority", "route-scenario", "constrained")

        def set_adoption_60(page: Page) -> None:
            self._set_control(page, "relay-adoption-value", "adoption", "60")

        def wait_for_idle_chrome(page: Page) -> None:
            # This portrait reference is the idle reading state. A slow capture
            # used to hide the HUD while a fast CI capture retained it.
            page.wait_for_function(
                "() => getComputedStyle(document.querySelector('#idrt-presenter-chrome')).opacity === '0'",
                timeout=8_000,
            )

        def show_static(page: Page) -> None:
            page.locator('[data-slide-id="relay-adoption-value"] [data-action="static"]').click()

        def remove_manager(page: Page) -> None:
            self._set_control(
                page,
                "relay-readiness-score",
                "manager-capacity",
                "unavailable",
            )

        def open_overview(page: Page) -> None:
            page.keyboard.press("Alt+O")
            page.locator("#idrt-presenter-overview").wait_for(state="visible")

        def open_first_panel(page: Page) -> None:
            page.locator('[data-action="open-panel"]').first.click()
            page.locator('[data-panel-id]:not([hidden])').wait_for(state="visible")

        def open_first_accordion(page: Page) -> None:
            opener = page.locator("[data-accordion-id]").first
            opener.click()
            opener.wait_for(state="visible")
            page.wait_for_function(
                "node => node.getAttribute('aria-expanded') === 'true'",
                arg=opener.element_handle(),
            )

        def open_tooltip(page: Page) -> None:
            summary = page.locator('.data-details > summary').first
            if summary.count():
                summary.focus()
                summary.press('Enter')
            page.locator("[data-tooltip-for]").first.click()
            page.locator('[role="tooltip"]:not([hidden])').wait_for(state="visible")

        candidates = {
            "01-cover-initial-1280x720": self._capture("01-cover-initial-1280x720"),
            "03-evidence-open-1280x720": self._capture(
                "03-evidence-open-1280x720", ordinal=3, mutate=open_evidence
            ),
            "04-constrained-1280x720": self._capture(
                "04-constrained-1280x720", ordinal=4, mutate=choose_constrained
            ),
            "05-adoption-60-1280x720": self._capture(
                "05-adoption-60-1280x720", ordinal=5, mutate=set_adoption_60
            ),
            "05-static-1280x720": self._capture(
                "05-static-1280x720", ordinal=5, mutate=show_static
            ),
            "05-reduced-60-1280x720": self._capture(
                "05-reduced-60-1280x720",
                ordinal=5,
                reduced_motion="reduce",
                mutate=set_adoption_60,
            ),
            "06-no-manager-1280x720": self._capture(
                "06-no-manager-1280x720", ordinal=6, mutate=remove_manager
            ),
            "overview-1280x720": self._capture(
                "overview-1280x720", ordinal=5, mutate=open_overview
            ),
            "05-adoption-55-390x844": self._capture(
                "05-adoption-55-390x844", ordinal=5, viewport=VIEW_PORTRAIT,
                mutate=wait_for_idle_chrome,
            ),
            "06-no-manager-390x844": self._capture(
                "06-no-manager-390x844",
                ordinal=6,
                viewport=VIEW_PORTRAIT,
                mutate=remove_manager,
            ),
            "fixture-drilldown-open-1280x720": self._capture(
                "fixture-drilldown-open-1280x720",
                artifact=self.fixture_artifacts["drilldown"],
                mutate=open_first_panel,
            ),
            "fixture-accordion-open-1280x720": self._capture(
                "fixture-accordion-open-1280x720",
                artifact=self.fixture_artifacts["accordion"],
                mutate=open_first_accordion,
            ),
            "fixture-tooltip-open-1280x720": self._capture(
                "fixture-tooltip-open-1280x720",
                artifact=self.fixture_artifacts["tooltip"],
                mutate=open_tooltip,
            ),
        }
        self.__class__._candidates = candidates
        return candidates

    def test_curated_visual_states_emit_review_candidates_without_cross_platform_mutation(self) -> None:
        before = _file_hashes(BASELINE_ROOT) if BASELINE_ROOT.is_dir() else {}
        candidates = self._ensure_candidates()
        self.assertEqual(len(candidates), 13)
        self.assertEqual(set(CANDIDATE_ROOT.glob("*.png")), set(candidates.values()))
        if platform.system() != "Linux":
            after = _file_hashes(BASELINE_ROOT) if BASELINE_ROOT.is_dir() else {}
            self.assertEqual(after, before, "non-Linux run must not rewrite Linux baselines")

    @unittest.skipUnless(platform.system() == "Linux", "Linux/Chromium baseline gate; macOS emits candidates only")
    def test_reviewed_linux_visual_baselines(self) -> None:
        candidates = self._ensure_candidates()
        update = os.environ.get("UPDATE_INTERACTIVE_BASELINES") == "1"
        if update:
            self.assertEqual(
                self.chromium_version,
                PINNED_CHROMIUM_VERSION,
                "baseline update requires the pinned Chromium build",
            )
            BASELINE_ROOT.mkdir(parents=True, exist_ok=True)
        for name, candidate in candidates.items():
            with self.subTest(state=name):
                baseline = BASELINE_ROOT / f"{name}.png"
                if update:
                    shutil.copyfile(candidate, baseline)
                self.assertTrue(
                    baseline.is_file(),
                    f"reviewed baseline missing: {baseline.relative_to(ROOT)}",
                )
                ratio, mean, size, diff = _image_delta(
                    candidate,
                    baseline,
                    channel_tolerance=PIXEL_CHANNEL_TOLERANCE,
                )
                if ratio > PIXEL_CHANGED_RATIO_LIMIT or mean > PIXEL_MEAN_DELTA_LIMIT:
                    _write_rgb_png(DIFF_ROOT / f"{name}.png", *size, diff)
                self.assertLessEqual(ratio, PIXEL_CHANGED_RATIO_LIMIT)
                self.assertLessEqual(mean, PIXEL_MEAN_DELTA_LIMIT)

    def test_fixed_geometry_stable_ids_and_in_flight_transition_truth(self) -> None:
        context, page = self._open(init_script=TRANSITION_SCHEDULER)
        try:
            # Page 4 reorders the same nodes; neither SVG nor semantic items are recreated.
            self._activate(page, 4)
            semantic_handles = {
                item_id: page.locator(
                    f'[data-slide-id="relay-route-priority"] [data-view-item-id="{item_id}"]'
                ).element_handle()
                for item_id in ("north", "central", "east")
            }
            svg_handles = {
                item_id: page.locator(
                    f'#idsvg-4-live-shell-LiveMark-{item_id}'
                ).element_handle()
                for item_id in ("north", "central", "east")
            }
            self._set_control(page, "relay-route-priority", "route-scenario", "constrained")
            order = page.locator(
                '[data-slide-id="relay-route-priority"] [data-view-component="ranked_list"] > [data-view-item-id]'
            ).evaluate_all("nodes => nodes.map(node => node.dataset.viewItemId)")
            self.assertEqual(order, ["north", "east", "central"])
            for item_id in ("north", "central", "east"):
                self.assertTrue(
                    semantic_handles[item_id].evaluate(
                        "(node, selector) => node === document.querySelector(selector)",
                        f'[data-slide-id="relay-route-priority"] [data-view-item-id="{item_id}"]',
                    )
                )
                self.assertTrue(
                    svg_handles[item_id].evaluate(
                        "(node, id) => node === document.getElementById(id)",
                        f"idsvg-4-live-shell-LiveMark-{item_id}",
                    )
                )

            # The live exhibit leaves room for controls; print uses the whole
            # slide. Both must encode the same fixed data domain and relation,
            # not happen to share screen pixels. Overview remains a static clone.
            self._activate(page, 5)
            geometry = page.evaluate(
                """() => {
                  const section = document.querySelector('[data-slide-id="relay-adoption-value"]');
                  const point = section.querySelector('#idsvg-5-live-shell-annual-value-point');
                  const fallbackPoint = section.querySelector('.fallback-layer circle');
                  const overviewPoint = document.querySelector('[data-overview-slide="5"] .overview-fallback circle');
                  const axis = root => [...root.querySelectorAll('line')].map(line => ({
                    x1: Number(line.getAttribute('x1')), y1: Number(line.getAttribute('y1')),
                    x2: Number(line.getAttribute('x2')), y2: Number(line.getAttribute('y2'))
                  })).filter(item => Number.isFinite(item.x1));
                  const plot = (root, point) => {
                    const horizontals = axis(root).filter(line => line.y1 === line.y2 && line.x2 - line.x1 > 500);
                    const verticals = axis(root).filter(line => line.x1 === line.x2 && line.y2 - line.y1 > 250);
                    const left = Math.min(...horizontals.map(line => line.x1));
                    const right = Math.max(...horizontals.map(line => line.x2));
                    const top = Math.min(...horizontals.map(line => line.y1), ...verticals.map(line => line.y1));
                    const bottom = Math.max(...horizontals.map(line => line.y1), ...verticals.map(line => line.y2));
                    const normal = (x,y) => [(x-left)/(right-left), (bottom-y)/(bottom-top)];
                    // Overview copies intentionally strip IDs. The model is
                    // still the unique non-axis/non-guide diagonal line.
                    const relationship = root.querySelector('line[id$="model-relationship"], line[id$="LiveRelationship"]') ||
                      [...root.querySelectorAll('line')].find(line => line.getAttribute('x1') !== line.getAttribute('x2') && line.getAttribute('y1') !== line.getAttribute('y2'));
                    return {
                      point: normal(Number(point.getAttribute('cx')), Number(point.getAttribute('cy'))),
                      relationship: [normal(Number(relationship.getAttribute('x1')), Number(relationship.getAttribute('y1'))),
                                     normal(Number(relationship.getAttribute('x2')), Number(relationship.getAttribute('y2')))]
                    };
                  };
                  return {
                    livePoint: [Number(point.getAttribute('cx')), Number(point.getAttribute('cy'))],
                    fallbackPoint: [Number(fallbackPoint.getAttribute('cx')), Number(fallbackPoint.getAttribute('cy'))],
                    overviewPoint: [Number(overviewPoint.getAttribute('cx')), Number(overviewPoint.getAttribute('cy'))],
                    liveAxes: axis(section.querySelector('.live-layer')),
                    fallbackAxes: axis(section.querySelector('.fallback-layer')),
                    overviewAxes: axis(document.querySelector('[data-overview-slide="5"] .overview-fallback')),
                    livePlot: plot(section.querySelector('.live-layer'), point),
                    fallbackPlot: plot(section.querySelector('.fallback-layer'), fallbackPoint),
                    overviewPlot: plot(document.querySelector('[data-overview-slide="5"] .overview-fallback'), overviewPoint),
                    liveSvgAriaHidden: section.querySelector('.live-layer svg').getAttribute('aria-hidden')
                  };
                }"""
            )
            self.assertEqual(geometry["fallbackPoint"], geometry["overviewPoint"])
            self.assertEqual(geometry['fallbackAxes'], geometry['overviewAxes'])
            for surface in ('livePlot', 'fallbackPlot', 'overviewPlot'):
                for actual, expected in zip(geometry[surface]['point'], (0.5, 0.45)):
                    self.assertAlmostEqual(actual, expected, places=3)
                for endpoint, expected in zip(geometry[surface]['relationship'], ((0, 0.075), (1, 0.825))):
                    for actual, target in zip(endpoint, expected):
                        self.assertAlmostEqual(actual, target, places=3)
            self.assertEqual(geometry["liveSvgAriaHidden"], "true")

            point = page.locator("#idsvg-5-live-shell-annual-value-point")
            point_handle = point.element_handle()
            before_point = (
                float(point.get_attribute("cx")),
                float(point.get_attribute("cy")),
            )
            stable_before = page.evaluate(
                """() => {
                  const section = document.querySelector('[data-slide-id="relay-adoption-value"]');
                  const box = node => {
                    const rect = node.getBoundingClientRect();
                    return [rect.x, rect.y, rect.width, rect.height];
                  };
                  const pointLabel = '#idsvg-5-live-shell-LivePointLabel-annual-value-point';
                  const nodes = [section.querySelector('h1'), section.querySelector('.semantic-source')]
                    .concat([...section.querySelectorAll('.live-layer svg text')]
                      .filter(node => !node.matches(pointLabel)));
                  return nodes.map(node => ({text: node.textContent, rect: box(node)}));
                }"""
            )
            fallback_before = page.locator(
                '[data-slide-id="relay-adoption-value"] .fallback-layer'
            ).inner_html()
            self._set_control(page, "relay-adoption-value", "adoption", "60")

            immediate_point = (
                float(point.get_attribute("cx")),
                float(point.get_attribute("cy")),
            )
            self.assertEqual(immediate_point, before_point)
            snapshot = page.evaluate("() => window.InteractiveDeck.snapshot()")
            page_state = snapshot["pages"][4]
            self.assertEqual(page_state["inputs"]["adoption"], "60")
            self.assertEqual(page_state["outputs"]["annual-value"], "2.1")
            self.assertEqual(page_state["outcome"], "met")
            semantic = page.locator('[data-slide-id="relay-adoption-value"] .semantic-scene')
            self.assertIn("60%", semantic.inner_text())
            self.assertIn("$2.1m", semantic.inner_text())
            self.assertEqual(
                semantic.locator("[data-decision-status]").inner_text().strip(),
                "Proceed",
            )
            # The live summary carries the absolute target immediately while
            # the polite status intentionally narrates the delta from the
            # prior state.
            status = semantic.locator(".scene-status").inner_text()
            self.assertIn("Adoption +5.00 pp", status)
            self.assertIn("Annual value +$0.3m", status)

            page.evaluate("() => window.__PROJECT_RELAY_VISUAL_CLOCK__.stepRaf(120)")
            midpoint = (
                float(point.get_attribute("cx")),
                float(point.get_attribute("cy")),
            )
            page.evaluate("() => window.__PROJECT_RELAY_VISUAL_CLOCK__.stepRaf(180)")
            endpoint = (
                float(point.get_attribute("cx")),
                float(point.get_attribute("cy")),
            )
            for start, middle, end in zip(before_point, midpoint, endpoint):
                self.assertNotEqual(start, end)
                self.assertGreater(middle, min(start, end))
                self.assertLess(middle, max(start, end))
            self.assertGreaterEqual(endpoint[0], 130)
            self.assertLessEqual(endpoint[0], 820)
            self.assertGreaterEqual(endpoint[1], 230)
            self.assertLessEqual(endpoint[1], 560)
            self.assertTrue(
                point_handle.evaluate(
                    "node => node === document.getElementById('idsvg-5-live-shell-annual-value-point')"
                )
            )
            self.assertEqual(
                page.locator('[data-slide-id="relay-adoption-value"] .fallback-layer').inner_html(),
                fallback_before,
            )
            stable_after = page.evaluate(
                """() => {
                  const section = document.querySelector('[data-slide-id="relay-adoption-value"]');
                  const box = node => {
                    const rect = node.getBoundingClientRect();
                    return [rect.x, rect.y, rect.width, rect.height];
                  };
                  const pointLabel = '#idsvg-5-live-shell-LivePointLabel-annual-value-point';
                  const nodes = [section.querySelector('h1'), section.querySelector('.semantic-source')]
                    .concat([...section.querySelectorAll('.live-layer svg text')]
                      .filter(node => !node.matches(pointLabel)));
                  return nodes.map(node => ({text: node.textContent, rect: box(node)}));
                }"""
            )
            self.assertEqual(stable_after, stable_before)
        finally:
            context.close()

    def _export_fresh_pdf(self) -> Path:
        output = self.temp_root / "project-relay.pdf"
        completed = subprocess.run(
            [
                sys.executable,
                str(EXPORT_SCRIPT),
                str(ARTIFACT),
                "-o",
                str(output),
                "--browser",
                self.chromium_executable,
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(output.read_bytes().startswith(b"%PDF-"))
        return output

    def _pdf_info(self, pdf: Path, page_number: int | None = None) -> str:
        command = ["pdfinfo"]
        if page_number is not None:
            command.extend(["-f", str(page_number), "-l", str(page_number), "-box"])
        command.append(str(pdf))
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    def _raster_pdf_page(self, pdf: Path, page_number: int, name: str) -> Path:
        prefix = self.temp_root / name
        completed = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-singlefile",
                "-r",
                "96",
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                str(pdf),
                str(prefix),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = prefix.with_suffix(".png")
        self.assertTrue(output.is_file())
        return output

    def _print_frame(self, ordinal: int, name: str) -> Path:
        context, page = self._open(viewport=VIEW_DESKTOP)
        try:
            page.emulate_media(media="print")
            frame = page.locator(
                f'[data-slide-id="{self.envelope["slides"][ordinal - 1]["slideId"]}"] .frame'
            )
            output = self.temp_root / f"{name}.png"
            frame.screenshot(path=str(output), animations="disabled", caret="hide")
            self.assertEqual(_png_rgb(output)[:2], (1280, 720))
            return output
        finally:
            context.close()

    def test_pdf_is_eight_page_16_by_9_nonblank_and_matches_print_rasters(self) -> None:
        fresh_pdf = self._export_fresh_pdf()
        general = self._pdf_info(fresh_pdf)
        self.assertRegex(general, r"(?m)^Pages:\s+8$")
        for page_number in range(1, 9):
            with self.subTest(page=page_number):
                page_info = self._pdf_info(fresh_pdf, page_number)
                match = re.search(
                    r"(?m)^Page\s+(?:size|\d+ size):\s+([0-9.]+) x ([0-9.]+) pts",
                    page_info,
                )
                if match is None:
                    match = re.search(r"(?m)^Page size:\s+([0-9.]+) x ([0-9.]+) pts", page_info)
                self.assertIsNotNone(match, page_info)
                width, height = (float(value) for value in match.groups())
                self.assertAlmostEqual(width / height, 16 / 9, delta=0.002)
                raster = self._raster_pdf_page(fresh_pdf, page_number, f"pdf-page-{page_number}")
                raster_width, raster_height, pixels = _png_rgb(raster)
                self.assertEqual((raster_width, raster_height), (1280, 720))
                nonwhite = sum(
                    1
                    for offset in range(0, len(pixels), 3)
                    if pixels[offset : offset + 3] != b"\xff\xff\xff"
                )
                self.assertGreater(nonwhite, raster_width * raster_height // 200)

        # Checked-in output must have the same structural contract as a fresh
        # export, but byte identity is intentionally not required.
        self.assertRegex(self._pdf_info(CHECKED_PDF), r"(?m)^Pages:\s+8$")
        for ordinal in (4, 5, 6):
            with self.subTest(raster_parity_page=ordinal):
                pdf_raster = self._raster_pdf_page(fresh_pdf, ordinal, f"pdf-parity-{ordinal}")
                print_frame = self._print_frame(ordinal, f"print-frame-{ordinal}")
                ratio, mean, size, diff = _image_delta(
                    pdf_raster,
                    print_frame,
                    channel_tolerance=PDF_CHANNEL_TOLERANCE,
                )
                if ratio > PDF_CHANGED_RATIO_LIMIT or mean > PDF_MEAN_DELTA_LIMIT:
                    _write_rgb_png(DIFF_ROOT / f"pdf-page-{ordinal}.png", *size, diff)
                self.assertLessEqual(ratio, PDF_CHANGED_RATIO_LIMIT)
                self.assertLessEqual(mean, PDF_MEAN_DELTA_LIMIT)

    def _run_audit(self, output: Path, executable: str | None = None) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--manifest",
            str(MANIFEST),
            "--audit-out",
            str(output),
        ]
        if executable is not None:
            command.extend(["--chromium-executable", executable])
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = "0"
        return subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
            env=environment,
        )

    def test_project_relay_audit_is_reproducible_complete_and_private(self) -> None:
        _safe_generated_reset(AUDIT_ROOT)
        _safe_generated_reset(AUDIT_REPEAT_ROOT)
        first = self._run_audit(AUDIT_ROOT, self.chromium_executable)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self._run_audit(AUDIT_REPEAT_ROOT, self.chromium_executable)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(_file_hashes(AUDIT_ROOT), _file_hashes(AUDIT_REPEAT_ROOT))
        self.assertEqual(
            {path.name for path in AUDIT_ROOT.iterdir()},
            {
                "audit-ledger.json",
                "state-atlas.html",
                "contact-sheet.html",
                "contact-sheet.png",
                "screenshots",
            },
        )
        self.assertEqual(list(AUDIT_ROOT.rglob("*.interactive.html")), [])

        ledger = json.loads((AUDIT_ROOT / "audit-ledger.json").read_text(encoding="utf-8"))
        self.assertEqual(ledger["deck"]["slideCount"], 8)
        scene_slides = [slide for slide in ledger["slides"] if slide["sceneType"] != "static"]
        self.assertEqual(
            [slide["sceneType"] for slide in scene_slides],
            ["evidence_only", "state_toggle", "slider_model", "score_model"],
        )
        obligations: dict[str, set[str]] = {}
        for state in ledger["states"]:
            obligations.setdefault(state["slideId"], set()).update(state["obligations"])
            screenshot = AUDIT_ROOT / state["screenshot"]
            self.assertTrue(screenshot.is_file())
            self.assertEqual(_png_size(screenshot), (1280, 720))
            self.assertEqual(
                hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                state["reconstruction"]["pngSha256"],
            )
            self.assertEqual(state["reconstruction"]["networkRequests"], [])
            self.assertEqual(state["reconstruction"]["consoleErrors"], [])
            self.assertTrue(state["reconstruction"]["staticParity"])
        common = {"initial", "print", "static", "reduced-motion", "overview-after-change"}
        for slide in scene_slides:
            self.assertTrue(common <= obligations[slide["slideId"]])
        self.assertTrue(
            {"evidence:sources", "evidence:assumptions", "evidence:both"}
            <= obligations["relay-late-job-evidence"]
        )
        # `boundary:*` is reserved for declared model segment/band boundaries.
        # The page-5 linear decision threshold is instead reconstructed through
        # below/exact/above decision witnesses, plus both authored range ends.
        self.assertTrue(
            {
                "range:adoption:min",
                "range:adoption:max",
                "decision:notMet",
                "decision:exact",
                "decision:met",
            }
            <= obligations["relay-adoption-value"]
        )
        self.assertTrue(
            {
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
            }
            <= obligations["relay-readiness-score"]
        )
        self.assertTrue(
            {"classification:Defer", "classification:Prepare", "classification:Pilot-ready"}
            <= obligations["relay-readiness-score"]
        )
        self.assertTrue(
            {"decision:met", "decision:notMet"}
            <= obligations["relay-adoption-value"]
        )
        self.assertTrue(
            {"decision:met", "decision:notMet"}
            <= obligations["relay-readiness-score"]
        )

        expected_targets = {
            (slide["slideId"], target)
            for slide in self.envelope["slides"]
            if slide["scene"] is not None
            for target in slide["scene"]["targets"]
        }
        self.assertEqual(
            {(row["slideId"], row["targetKey"]) for row in ledger["targetCoverage"]},
            expected_targets,
        )
        expected_steps = {
            (slide["slideId"], step["stepKey"])
            for slide in self.envelope["slides"]
            if slide["scene"] is not None
            for step in slide["scene"]["steps"]
        }
        self.assertEqual(len(expected_steps), 6)
        self.assertEqual(
            {(row["slideId"], row["stepKey"]) for row in ledger["stepCoverage"]},
            expected_steps,
        )

        for path in AUDIT_ROOT.rglob("*"):
            if path.suffix not in (".json", ".html"):
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(str(ROOT), text)
            self.assertNotIn("/Users/", text)
            self.assertNotRegex(text.lower(), r'"(?:timestamp|nonce)"\s*:')
            self.assertNotRegex(text, r"\b20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}")

    def test_audit_browser_failure_is_atomic(self) -> None:
        failed = RESULT_ROOT / "project-relay-audit-failed"
        _safe_generated_reset(failed)
        completed = self._run_audit(failed, "/bin/false")
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(failed.exists())
        self.assertEqual(list(RESULT_ROOT.glob(".project-relay-audit-failed.stage-*")), [])
        self.assertEqual(
            completed.stderr.strip(),
            "ERROR: interactive audit failed [browser_unavailable]",
        )


if __name__ == "__main__":
    unittest.main()
