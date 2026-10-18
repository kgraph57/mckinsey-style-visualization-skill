from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str):
    module_path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = load_module("build_html_deck")


class BuildHtmlDeckTests(unittest.TestCase):
    def build_demo(self) -> str:
        manifest = json.loads((ROOT / "examples" / "demo-deck.json").read_text(encoding="utf-8"))
        spec_paths = [ROOT / "examples" / p for p in manifest["slides"]]
        return builder.build_deck(spec_paths, manifest["title"])

    def test_demo_deck_is_byte_identical_to_committed_classic_artifact(self) -> None:
        self.assertEqual(self.build_demo().encode("utf-8"), (ROOT / "examples/demo-deck.html").read_bytes())

    def test_absolute_importlib_builder_loads_from_unrelated_cwd_without_path_changes(self) -> None:
        program = """
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("portable_deck", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.build_deck([], "Portable"))
"""
        for relative in ("scripts/build_html_deck.py", "docs/site/artifacts/py/build_html_deck.py"):
            with self.subTest(builder=relative), tempfile.TemporaryDirectory() as td:
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", program, str(ROOT / relative)],
                    cwd=td, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("<title>Portable</title>", result.stdout)

    def test_cli_mixed_manifest_preserves_classic_output_and_ignores_missing_scene(self) -> None:
        manifest = json.loads((ROOT / "examples/demo-deck.json").read_text(encoding="utf-8"))
        manifest["slides"] = [
            str(ROOT / "examples" / entry) if i % 2 == 0 else {
                "spec": str(ROOT / "examples" / entry),
                "scene": "../missing-scenes/never-read.json",
                "id": f"page-{i}",
            }
            for i, entry in enumerate(manifest["slides"])
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "deck.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_html_deck.py"), "--manifest", str(root / "deck.json"), "-o", str(root / "deck.html")],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "deck.html").read_bytes(), (ROOT / "examples/demo-deck.html").read_bytes())

    def test_deck_contains_one_section_per_slide(self) -> None:
        html = self.build_demo()
        manifest = json.loads((ROOT / "examples" / "demo-deck.json").read_text(encoding="utf-8"))
        slide_count = len(manifest["slides"])
        self.assertEqual(html.count('<section class="slide"'), slide_count)
        self.assertEqual(html.count('class="dot"'), slide_count)

    def test_deck_is_self_contained(self) -> None:
        html = self.build_demo()
        for marker in ("http://", "https://", "src=", "@import"):
            self.assertNotIn(marker, html.replace("http://www.w3.org/2000/svg", ""))

    def test_deck_has_animation_and_print_support(self) -> None:
        html = self.build_demo()
        self.assertIn("animation-delay", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn("@media print", html)
        # Print fragmentation: the deck must leave flex layout so each slide
        # can take its own 16:9 page (flex items ignore forced page breaks).
        self.assertIn("@page { size: 13.333in 7.5in; margin: 0; }", html)
        self.assertIn(".deck { display: block; height: auto; }", html)
        # Presentation chrome: the HUD auto-hides on idle and on keyboard
        # navigation so it never lingers over a projected slide.
        self.assertIn("body.hud-hidden .hud { opacity: 0; pointer-events: none; }", html)
        self.assertIn("hudTimer = setTimeout(hideHud, 2500)", html)
        self.assertIn("body.embed .hud", html)
        self.assertIn("embed=1", html)
        self.assertIn("page-break-after: always", html)

    def test_animate_svg_tags_elements_but_not_background(self) -> None:
        renderer = load_module("render_slide_spec")
        svg = renderer.render(
            {
                "pattern": "gap",
                "headline": "Capacity trails demand",
                "items": [
                    {"label": "Demand", "value": 100, "emphasis": True},
                    {"label": "Capacity", "value": 60},
                ],
            }
        )
        animated = builder.animate_svg(svg)
        self.assertIn('class="el"', animated)
        # The white background rect is the first element and must stay static
        # so slides never flash dark while revealing.
        first_element_line = next(
            line for line in animated.splitlines() if line.lstrip().startswith("<rect")
        )
        self.assertNotIn('class="el"', first_element_line)

    def test_delays_are_capped(self) -> None:
        html = self.build_demo()
        import re

        delays = [int(m) for m in re.findall(r"animation-delay:(\d+)ms", html)]
        self.assertTrue(delays, "expected staggered delays in the deck")
        self.assertLessEqual(max(delays), builder.STAGGER_MAX_MS)


if __name__ == "__main__":
    unittest.main()
