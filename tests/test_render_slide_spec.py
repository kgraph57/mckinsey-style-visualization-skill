from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_renderer():
    module_path = ROOT / "scripts" / "render_slide_spec.py"
    spec = importlib.util.spec_from_file_location("render_slide_spec", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


renderer = load_renderer()


class RenderSlideSpecTests(unittest.TestCase):
    def test_unsupported_pattern_raises_value_error_with_supported_patterns(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            renderer.render({"pattern": "radial_tree", "headline": "Growth map"})

        message = str(ctx.exception)
        self.assertIn("unsupported pattern 'radial_tree'", message)
        self.assertIn("waterfall", message)
        self.assertIn("two_by_two", message)

    def test_time_series_requires_matching_labels_and_values(self) -> None:
        spec = {
            "pattern": "time_series",
            "headline": "Adoption keeps rising",
            "x_labels": ["Q1", "Q2"],
            "series": [{"label": "Adoption", "values": [18, 42, 64]}],
        }

        with self.assertRaises(ValueError) as ctx:
            renderer.render(spec)

        self.assertIn("x_labels must contain 3 labels", str(ctx.exception))

    def test_benchmark_table_requires_each_row_to_match_columns(self) -> None:
        spec = {
            "pattern": "benchmark_table",
            "headline": "Vendor B leads on enterprise readiness",
            "columns": ["Security", "Scale", "Support"],
            "rows": [{"label": "Vendor A", "values": ["High", "Medium"]}],
        }

        with self.assertRaises(ValueError) as ctx:
            renderer.render(spec)

        self.assertIn("rows[0].values must contain 3 values", str(ctx.exception))

    def test_heatmap_requires_each_value_row_to_match_columns(self) -> None:
        spec = {
            "pattern": "heatmap",
            "headline": "Enterprise demand concentrates in two segments",
            "rows": ["SMB", "Enterprise"],
            "columns": ["Awareness", "Trial", "Paid"],
            "values": [[10, 20, 30], [40, 50]],
        }

        with self.assertRaises(ValueError) as ctx:
            renderer.render(spec)

        self.assertIn("values[1] must contain 3 cells", str(ctx.exception))

    def test_funnel_with_zero_previous_stage_renders_undefined_conversion(self) -> None:
        spec = {
            "pattern": "funnel",
            "headline": "Activation begins after seeded imports",
            "unit": "",
            "stages": [
                {"label": "Inbound signups", "value": 0},
                {"label": "Seeded activations", "value": 5},
            ],
        }

        svg = renderer.render(spec)

        self.assertIn("Seeded activations", svg)
        self.assertIn("n/a", svg)

    def test_svg_escapes_text_fields(self) -> None:
        spec = {
            "pattern": "summary_strip",
            "headline": 'A&B <C> "D"',
            "source": 'Source: "ops" & <finance>',
            "blocks": [
                {
                    "claim": "Pipeline & capacity",
                    "proof": "Demand < capacity",
                    "implication": "Approve \"phase 2\"",
                }
            ],
        }

        svg = renderer.render(spec)

        self.assertIn("A&amp;B &lt;C&gt; &quot;D&quot;", svg)
        self.assertIn("Source: &quot;ops&quot; &amp; &lt;finance&gt;", svg)


if __name__ == "__main__":
    unittest.main()
