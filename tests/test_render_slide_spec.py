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


def _element_bounds(svg: str) -> list[tuple[float, float]]:
    """Collect (y, height-extent) pairs for rects and text elements."""
    import re

    bounds: list[tuple[float, float]] = []
    for match in re.finditer(r'<rect x="[^"]+" y="([\d.\-]+)" width="[^"]+" height="([\d.\-]+)"', svg):
        bounds.append((float(match.group(1)), float(match.group(1)) + float(match.group(2))))
    return bounds


class GraphicalIntegrityTests(unittest.TestCase):
    def test_waterfall_with_negative_cumulative_stays_inside_canvas(self) -> None:
        spec = {
            "pattern": "waterfall",
            "headline": "Churn event drives ARR negative before recovery",
            "unit": "$M",
            "start": {"label": "Starting ARR", "value": 5},
            "drivers": [
                {"label": "New logos", "value": 2},
                {"label": "Massive churn event", "value": -14},
                {"label": "Downsell", "value": -3},
                {"label": "Expansion", "value": 6},
            ],
            "end_label": "Ending ARR",
        }

        svg = renderer.render(spec)

        for top, bottom in _element_bounds(svg):
            self.assertGreaterEqual(top, 0, "bar starts above the canvas")
            self.assertLessEqual(bottom, renderer.H, "bar extends past the canvas")

    def test_negative_currency_formats_sign_before_symbol(self) -> None:
        self.assertEqual(renderer.fmt(-4, "$M"), "-$4M")
        self.assertEqual(renderer.fmt(-4.5, "€"), "-€4.5")
        self.assertEqual(renderer.fmt(-12, "%"), "-12%")

    def test_cjk_text_wraps_instead_of_overflowing(self) -> None:
        headline = "成長は力強く、採用は実証済みで、いまや処理能力が制約条件になっている"
        lines = renderer.wrap(headline, 64)
        self.assertGreater(len(lines), 1, "CJK headline must wrap")
        for line in lines:
            self.assertLessEqual(renderer._text_width(line), 64)

    def test_wrap_clamps_with_visible_ellipsis(self) -> None:
        lines = renderer.wrap("Enterprise strategic accounts renewal team (APAC)", 20, max_lines=2)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith(renderer.ELLIPSIS), "truncation must be visible")

    def test_wrap_hard_breaks_unbreakable_tokens(self) -> None:
        lines = renderer.wrap("SOC2/ISO27001/HIPAA/FedRAMP-High", 12)
        for line in lines:
            self.assertLessEqual(renderer._text_width(line), 12)

    def test_primary_accent_separates_from_dark_grey_in_greyscale(self) -> None:
        blue_lum = renderer._rel_luminance(renderer.BLUE)
        grey_lum = renderer._rel_luminance(renderer.GREY_DARK)
        ratio = max(blue_lum, grey_lum) / max(min(blue_lum, grey_lum), 1e-9)
        self.assertGreaterEqual(ratio, 1.5, "rung-1 fill must survive greyscale print")

    def test_heatmap_cell_text_meets_wcag_aa(self) -> None:
        for t in [i / 20 for i in range(21)]:
            fill = renderer._lerp_color(renderer.BLUE_TINT, renderer.BLUE, t)
            text = renderer._cell_text_color(fill)
            self.assertGreaterEqual(
                renderer.contrast_ratio(text, fill), 4.5, f"cell tone t={t} fails AA"
            )

    def test_heatmap_with_signed_data_uses_diverging_scale(self) -> None:
        spec = {
            "pattern": "heatmap",
            "headline": "Channel efficiency diverges by region",
            "rows": ["APAC", "EMEA"],
            "columns": ["Q1", "Q2"],
            "values": [[-40, 10], [25, -5]],
        }

        svg = renderer.render(spec)

        self.assertIn(renderer.RED[1:3], svg.upper(), "negative cells must use the red ramp")

    def test_before_after_uses_direct_labels_not_legend_swatches(self) -> None:
        spec = {
            "pattern": "before_after",
            "headline": "Adoption doubles after onboarding revamp",
            "pairs": [{"label": "Adoption", "before": 20, "after": 40}],
        }

        svg = renderer.render(spec)

        self.assertIn(">Before<", svg)
        self.assertIn(">After<", svg)

    def test_footer_furniture_renders_page_number_and_classification(self) -> None:
        spec = {
            "pattern": "distribution",
            "headline": "Deal sizes cluster below $50k",
            "bins": [{"label": "<$50k", "value": 34}, {"label": "$50-100k", "value": 12}],
            "page_number": 7,
            "classification": "For internal discussion only",
            "footnotes": ["Excludes renewals booked before Q2."],
        }

        svg = renderer.render(spec)

        self.assertIn(">7<", svg)
        self.assertIn("FOR INTERNAL DISCUSSION ONLY", svg)
        self.assertIn("¹ Excludes renewals", svg)

    def test_new_patterns_render(self) -> None:
        specs = [
            {
                "pattern": "scatter",
                "headline": "Price does not explain retention",
                "x_axis": {"label": "Price"},
                "y_axis": {"label": "Retention"},
                "points": [{"x": 10, "y": 80, "label": "A", "emphasis": True}, {"x": 30, "y": 60, "label": "B"}],
            },
            {
                "pattern": "small_multiples",
                "headline": "Adoption rises in every segment",
                "charts": [
                    {"label": "SMB", "values": [10, 20, 30]},
                    {"label": "Mid-market", "values": [15, 18, 26], "emphasis": True},
                ],
            },
            {"pattern": "cover", "title": "FY26 Growth Review", "subtitle": "Board meeting", "date": "July 2026"},
        ]
        for spec in specs:
            svg = renderer.render(spec)
            self.assertIn("<svg", svg)


if __name__ == "__main__":
    unittest.main()
