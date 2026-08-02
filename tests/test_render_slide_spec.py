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

    def test_wrap_never_starts_a_line_with_closing_punctuation(self) -> None:
        # 行頭禁則: closing punctuation hangs off the previous line instead
        # of starting its own, at every width where it would otherwise land
        # at a line head.
        text = "多角化より先に、エンタープライズの勢いを守る。"
        for width in range(8, 48, 2):
            lines = renderer.wrap(text, width)
            self.assertEqual("".join(lines), text, f"content lost at width {width}")
            for line in lines[1:]:
                self.assertNotIn(
                    line[0], renderer.KINSOKU_HEAD, f"width {width}: line starts with {line[0]!r}"
                )

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


class StructuralSlidePatternTests(unittest.TestCase):
    """Pillar 1: section_divider, end_cover, agenda, bullet_list, closing, quote."""

    # --- happy paths -----------------------------------------------------

    def test_section_divider_renders_kicker_label_title_and_rail(self) -> None:
        spec = {
            "pattern": "section_divider",
            "section_number": 2,
            "title": "Where to play",
            "subtitle": "Market selection and entry sequence",
            "sections": ["Context", "Where to play", "How to win", "Roadmap"],
            "classification": "Draft — illustrative",
        }

        svg = renderer.render(spec)

        self.assertIn("<svg", svg)
        self.assertIn("SECTION 02", svg)
        self.assertIn("Where to play", svg)
        self.assertIn("Market selection and entry sequence", svg)
        self.assertIn("02 Where to play", svg)
        self.assertIn('opacity="0.55"', svg, "non-current rail items must be dimmed")
        self.assertIn("DRAFT — ILLUSTRATIVE", svg)

    def test_end_cover_renders_with_all_fields(self) -> None:
        spec = {
            "pattern": "end_cover",
            "title": "Thank you",
            "subtitle": "Questions and discussion",
            "contact": ["Strategy Office", "strategy@example.com"],
            "presenter": "Jane Doe",
            "date": "March 2026",
            "classification": "Confidential — illustrative",
        }

        svg = renderer.render(spec)

        self.assertIn("Thank you", svg)
        self.assertIn("Strategy Office", svg)
        self.assertIn("strategy@example.com", svg)
        self.assertIn("Jane Doe · March 2026", svg)
        self.assertIn("CONFIDENTIAL — ILLUSTRATIVE", svg)

    def test_end_cover_bare_spec_still_renders(self) -> None:
        svg = renderer.render({"pattern": "end_cover"})

        self.assertIn("<svg", svg)
        self.assertIn("Thank you", svg, "end_cover must default its title")

    def test_agenda_renders_numbered_rows_and_emphasizes_current(self) -> None:
        spec = {
            "pattern": "agenda",
            "headline": "Three questions decide this investment",
            "items": [
                {"title": "Context", "detail": "What changed since January"},
                {"title": "Options", "detail": "Three entry paths, one recommendation"},
            ],
            "current": 2,
            "page_number": 2,
        }

        svg = renderer.render(spec)

        self.assertIn("Context", svg)
        self.assertIn("Options", svg)
        self.assertIn("What changed since January", svg)
        self.assertIn(renderer.BLUE_TINT, svg, "current row must get a rung-2 tinted fill")

    def test_agenda_over_six_items_splits_into_two_columns(self) -> None:
        spec = {
            "pattern": "agenda",
            "headline": "Eight-item agenda",
            "items": [{"title": f"Item {i}"} for i in range(8)],
        }

        svg = renderer.render(spec)

        for i in range(8):
            self.assertIn(f"Item {i}", svg)

    def test_bullet_list_renders_marker_subs_and_emphasis(self) -> None:
        spec = {
            "pattern": "bullet_list",
            "headline": "Three constraints shape the rollout",
            "bullets": [
                {"text": "Capacity is fixed until Q3", "sub": ["Hiring freeze through June"], "emphasis": True},
                {"text": "Regional pricing has not been finalized"},
            ],
        }

        svg = renderer.render(spec)

        self.assertIn("Capacity is fixed until Q3", svg)
        self.assertIn("– Hiring freeze through June", svg)
        self.assertIn(renderer.BLUE, svg)

    def test_bullet_list_two_columns_splits_bullets(self) -> None:
        spec = {
            "pattern": "bullet_list",
            "headline": "Four items in two columns",
            "bullets": [{"text": f"Bullet {i}"} for i in range(4)],
            "columns": 2,
        }

        svg = renderer.render(spec)

        for i in range(4):
            self.assertIn(f"Bullet {i}", svg)

    def test_closing_with_takeaways_renders_two_columns_and_call_to_action(self) -> None:
        spec = {
            "pattern": "closing",
            "headline": "Decide the pilot now, scale in Q3",
            "takeaways": ["Unit economics clear the bar", "Risk is concentrated in supply"],
            "next_steps": [{"action": "Approve pilot budget", "owner": "CFO", "timing": "This week"}],
            "call_to_action": "Decision requested today: approve the Q2 pilot",
            "page_number": 12,
        }

        svg = renderer.render(spec)

        self.assertIn("KEY TAKEAWAYS", svg)
        self.assertIn("NEXT STEPS", svg)
        self.assertIn("Unit economics clear the bar", svg)
        self.assertIn("Approve pilot budget", svg)
        self.assertIn("CFO · This week", svg)
        # call_to_action rides the existing footer annotation slot, not a new motif.
        self.assertIn("Decision requested today: approve the Q2 pilot", svg)

    def test_closing_without_takeaways_renders_full_width_rows(self) -> None:
        spec = {
            "pattern": "closing",
            "headline": "Next steps",
            "next_steps": [
                {"action": "Do X", "owner": "A", "timing": "Now"},
                {"action": "Do Y"},
            ],
        }

        svg = renderer.render(spec)

        self.assertNotIn("KEY TAKEAWAYS", svg)
        self.assertIn("Do X", svg)
        self.assertIn("A · Now", svg)
        self.assertIn("Do Y", svg)

    def test_quote_renders_mark_text_and_attribution(self) -> None:
        spec = {
            "pattern": "quote",
            "headline": "Customers already describe the switch as done",
            "text": "We moved 80% of volume in six weeks — the old tool is a backup now.",
            "attribution": "COO, mid-market logistics customer",
            "context": "Interview, February 2026",
        }

        svg = renderer.render(spec)

        self.assertIn("“", svg, "quote needs the oversized opening mark")
        self.assertIn("We moved 80% of volume", svg)
        self.assertIn("— COO, mid-market logistics customer", svg)
        self.assertIn("Interview, February 2026", svg)

    # --- validator errors --------------------------------------------------

    def test_section_divider_requires_title(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            renderer.render({"pattern": "section_divider", "section_number": 1})
        self.assertIn("section_divider requires a title", str(ctx.exception))

    def test_section_divider_requires_positive_section_number(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            renderer.render({"pattern": "section_divider", "title": "x", "section_number": 0})
        self.assertIn("section_number", str(ctx.exception))

    def test_agenda_requires_items_with_titles(self) -> None:
        with self.assertRaises(ValueError):
            renderer.render({"pattern": "agenda", "headline": "x", "items": [{}]})

    def test_agenda_over_eight_items_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            renderer.render(
                {"pattern": "agenda", "headline": "x", "items": [{"title": str(i)} for i in range(9)]}
            )
        self.assertIn("at most 8 items", str(ctx.exception))

    def test_bullet_list_requires_bullet_text(self) -> None:
        with self.assertRaises(ValueError):
            renderer.render({"pattern": "bullet_list", "headline": "x", "bullets": [{}]})

    def test_bullet_list_over_six_bullets_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            renderer.render(
                {"pattern": "bullet_list", "headline": "x", "bullets": [{"text": str(i)} for i in range(7)]}
            )
        self.assertIn("at most 6 bullets", str(ctx.exception))

    def test_bullet_list_two_emphasized_bullets_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            renderer.render(
                {
                    "pattern": "bullet_list",
                    "headline": "x",
                    "bullets": [
                        {"text": "a", "emphasis": True},
                        {"text": "b", "emphasis": True},
                    ],
                }
            )
        self.assertIn("at most one emphasized bullet", str(ctx.exception))

    def test_closing_requires_next_steps(self) -> None:
        with self.assertRaises(ValueError):
            renderer.render({"pattern": "closing", "headline": "x"})

    def test_closing_requires_action_per_step(self) -> None:
        with self.assertRaises(ValueError):
            renderer.render({"pattern": "closing", "headline": "x", "next_steps": [{"owner": "A"}]})

    def test_quote_requires_text(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            renderer.render({"pattern": "quote", "headline": "x"})
        self.assertIn("quote requires text", str(ctx.exception))

    # --- Japanese text ------------------------------------------------------

    def test_section_divider_wraps_japanese_title(self) -> None:
        spec = {
            "pattern": "section_divider",
            "section_number": 1,
            "title": "成長は力強く、採用は実証済みで、いまや処理能力が制約条件になっている",
        }

        svg = renderer.render(spec)

        self.assertIn("<svg", svg)

    def test_bullet_list_wraps_japanese_bullets(self) -> None:
        spec = {
            "pattern": "bullet_list",
            "headline": "三つの制約がロールアウトを規定する",
            "bullets": [
                {
                    "text": "処理能力は第3四半期まで固定されている",
                    "sub": ["6月末まで採用凍結"],
                }
            ],
        }

        svg = renderer.render(spec)

        self.assertIn("処理能力", svg)

    # --- chromeless dispatch -------------------------------------------------

    def test_chromeless_patterns_skip_header_and_footer_chrome(self) -> None:
        self.assertEqual(renderer.CHROMELESS, {"cover", "section_divider", "end_cover"})
        for pattern, spec in (
            ("section_divider", {"pattern": "section_divider", "section_number": 1, "title": "Context"}),
            ("end_cover", {"pattern": "end_cover", "title": "Thank you"}),
        ):
            svg = renderer.render(spec)
            # The kicker bar is header()'s signature motif at (ML, 52); chromeless
            # slides use their own kicker at y=200 instead, and never call header/footer.
            self.assertNotIn('y="52.0" width="56.0"', svg, f"{pattern} must not use content-slide header chrome")
            self.assertIn('y="200.0" width="56.0"', svg, f"{pattern} must use the cover-style kicker")
            self.assertNotIn('fill="#FFFFFF" stroke="none"/>\n  <rect x="80.0" y="52.0"', svg)

    def test_chromed_structural_patterns_use_header_and_footer(self) -> None:
        for spec in (
            {"pattern": "agenda", "headline": "Agenda", "items": [{"title": "A"}]},
            {"pattern": "bullet_list", "headline": "Bullets", "bullets": [{"text": "A"}]},
            {"pattern": "closing", "headline": "Closing", "next_steps": [{"action": "A"}]},
            {"pattern": "quote", "headline": "Quote", "text": "A"},
        ):
            svg = renderer.render(spec)
            self.assertIn('y="52.0" width="56.0"', svg, f"{spec['pattern']} must keep the standard kicker/header")

    def test_render_dispatch_chromeless_aria_falls_back_to_title(self) -> None:
        svg = renderer.render({"pattern": "section_divider", "section_number": 1, "title": "Context set-up"})
        self.assertIn('aria-label="Context set-up"', svg)


if __name__ == "__main__":
    unittest.main()
