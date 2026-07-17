from __future__ import annotations

import importlib.util
import json
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

    def test_deck_contains_one_section_per_slide(self) -> None:
        html = self.build_demo()
        self.assertEqual(html.count('<section class="slide"'), 6)
        self.assertEqual(html.count('class="dot"'), 6)

    def test_deck_is_self_contained(self) -> None:
        html = self.build_demo()
        for marker in ("http://", "https://", "src=", "@import"):
            self.assertNotIn(marker, html.replace("http://www.w3.org/2000/svg", ""))

    def test_deck_has_animation_and_print_support(self) -> None:
        html = self.build_demo()
        self.assertIn("animation-delay", html)
        self.assertIn("prefers-reduced-motion", html)
        self.assertIn("@media print", html)
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
