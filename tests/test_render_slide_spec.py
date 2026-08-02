from __future__ import annotations

import importlib.util
import re
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
    bounds: list[tuple[float, float]] = []
    for match in re.finditer(r'<rect x="[^"]+" y="([\d.\-]+)" width="[^"]+" height="([\d.\-]+)"', svg):
        bounds.append((float(match.group(1)), float(match.group(1)) + float(match.group(2))))
    return bounds


def _rects_with_stroke(svg: str, stroke_value: str) -> list[str]:
    """`<rect ...>` tags (only rects, not hairline `<line>` elements) whose
    stroke attribute equals `stroke_value`. Used to assert flat-fill-only
    ink discipline without tripping on legitimate GREY_BORDER hairlines
    (table rules, gantt grid lines, agenda rows) drawn with `<line>`."""
    return re.findall(rf'<rect[^>]*stroke="{re.escape(stroke_value)}"[^>]*/>', svg)


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

    def test_section_divider_renders_label_title_and_rail(self) -> None:
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
            # Chromeless slides never call header/footer, and no slide carries
            # the former decorative kicker bar (removed 2026-08-03 — data-ink
            # rule with no exceptions).
            self.assertNotIn('width="56.0" height="5.0"', svg, f"{pattern} must not draw a kicker bar")

    def test_no_pattern_draws_a_decorative_kicker_bar(self) -> None:
        for spec in (
            {"pattern": "agenda", "headline": "Agenda", "items": [{"title": "A"}]},
            {"pattern": "bullet_list", "headline": "Bullets", "bullets": [{"text": "A"}]},
            {"pattern": "closing", "headline": "Closing", "next_steps": [{"action": "A"}]},
            {"pattern": "quote", "headline": "Quote", "text": "A"},
            {"pattern": "cover", "title": "Cover"},
        ):
            svg = renderer.render(spec)
            self.assertNotIn(
                'width="56.0" height="5.0"', svg, f"{spec['pattern']} must not draw a kicker bar"
            )

    def test_render_dispatch_chromeless_aria_falls_back_to_title(self) -> None:
        svg = renderer.render({"pattern": "section_divider", "section_number": 1, "title": "Context set-up"})
        self.assertIn('aria-label="Context set-up"', svg)


class InkDisciplineRegressionTests(unittest.TestCase):
    """Locks in the de-slop pass (2026-08-02 panel review, two rounds): flat
    fill only on KPI cards / grey context bars, no divider rule between
    summary_strip columns, and band-filling geometry that replaces fixed
    decoration and fixed-cap whitespace. Round 2 replaced two round-1 fixes
    that were themselves regressions: `closing` and `bullet_list` no longer
    center the *whole* item stack as one block (that detached item 1 from
    its label whenever a short list left slack in the band) — they divide
    the band into one row per item instead, like `render_gap`, and center
    each item's own text block within its own row. `summary_strip` never
    had this problem (no external label to detach from) so it still centers
    its one-column stack as a single unit, replacing a fixed `CHART_TOP+50`
    anchor. See references/style-system.md Ink Discipline and Chart Rules
    for the corresponding documentation."""

    def test_kpi_scorecard_cards_have_no_border_or_status_accent_bar(self) -> None:
        spec = {
            "pattern": "kpi_scorecard",
            "headline": "Six metrics status check",
            "metrics": [
                {"label": "A", "value": "1", "status": "good"},
                {"label": "B", "value": "2", "status": "watch"},
                {"label": "C", "value": "3", "status": "risk"},
            ],
        }
        svg = renderer.render(spec)
        self.assertEqual(_rects_with_stroke(svg, renderer.GREY_BORDER), [], "KPI cards must be flat fill, no border")
        # The old status accent bar was a fixed 5px-wide rect the full card height.
        self.assertNotIn('width="5.0"', svg, "status must no longer render as an accent bar")

    def test_summary_strip_has_no_column_divider_line(self) -> None:
        spec = {
            "pattern": "summary_strip",
            "headline": "Three takeaways",
            "blocks": [
                {"claim": "A", "proof": "B", "implication": "C"},
                {"claim": "D", "proof": "E", "implication": "F"},
                {"claim": "G", "proof": "H", "implication": "I"},
            ],
        }
        svg = renderer.render(spec)
        self.assertNotIn("<line", svg, "summary_strip columns must separate by whitespace, not a rule")

    def test_summary_strip_claim_anchors_directly_under_the_subhead(self) -> None:
        spec = {
            "pattern": "summary_strip",
            "headline": "Three takeaways",
            "blocks": [
                {"claim": "A", "proof": "B", "implication": "C"},
                {"claim": "D", "proof": "E", "implication": "F"},
            ],
        }
        svg = renderer.render(spec)
        # 2026-08-02 panel round 3: whole-block centering (the fix locked in
        # here until this round) solved the 44%-dead-space complaint but
        # opened a new offense — a 135-205px gap between the subhead and the
        # claim line that no other text pattern on the deck has (measured on
        # executive-summary.svg / jp-board-summary.svg: strip_top=325.5,
        # 205.5px below the subhead at y=138). The subhead directly above
        # this band functions as the same kind of content-introducing label
        # "KEY TAKEAWAYS" is for `closing`, so it gets the same fixed
        # band_start anchor bullet_list and closing use.
        strip_top = renderer.CHART_TOP + 20
        expected_claim_y = strip_top + 18
        self.assertIn(f'y="{expected_claim_y:.1f}"', svg)
        # Must not regress to the whole-block-centered position this test
        # locked in previously (2-block short list, single-line claim/proof/
        # implication: total_height=79, centered to strip_top=344.5,
        # claim_y=362.5).
        old_centered_claim_y = 362.5
        self.assertNotIn(f'y="{old_centered_claim_y:.1f}"', svg)

    def test_summary_strip_claim_anchor_is_independent_of_block_count(self) -> None:
        # Regardless of how many blocks or how tall the tallest one is, every
        # column's claim line starts at the same fixed offset from CHART_TOP
        # — the point of dropping whole-block centering.
        short_spec = {
            "pattern": "summary_strip",
            "headline": "One block",
            "blocks": [{"claim": "A", "proof": "B", "implication": "C"}],
        }
        long_spec = {
            "pattern": "summary_strip",
            "headline": "Three tall blocks",
            "blocks": [
                {
                    "claim": "A much longer claim line that will wrap across more than one row of text",
                    "proof": "A much longer proof line that will also wrap across more than one row of text",
                    "implication": "A much longer implication line that will wrap across more than one row too",
                }
                for _ in range(3)
            ],
        }
        expected_claim_y = renderer.CHART_TOP + 20 + 18
        for spec in (short_spec, long_spec):
            svg = renderer.render(spec)
            self.assertIn(f'y="{expected_claim_y:.1f}"', svg)

    def test_gap_before_after_distribution_gantt_process_flow_bars_are_flat_fill(self) -> None:
        specs = [
            {
                "pattern": "gap",
                "headline": "Gap to target",
                "items": [{"label": "A", "value": 10}, {"label": "B", "value": 20, "emphasis": True}],
            },
            {
                "pattern": "before_after",
                "headline": "Before after",
                "pairs": [{"label": "A", "before": 10, "after": 20}],
            },
            {
                "pattern": "distribution",
                "headline": "Distribution",
                "bins": [{"label": "A", "value": 10}, {"label": "B", "value": 20}],
                "highlight": 1,
            },
            {
                "pattern": "gantt",
                "headline": "Gantt",
                "periods": ["Q1", "Q2"],
                "bars": [
                    {"label": "A", "start": 0, "end": 1, "highlight": True},
                    {"label": "B", "start": 0, "end": 1},
                ],
            },
            {
                "pattern": "process_flow",
                "headline": "Flow",
                "steps": [{"label": "A", "detail": "x"}, {"label": "B", "detail": "y"}],
                "highlight": 0,
            },
        ]
        for spec in specs:
            svg = renderer.render(spec)
            self.assertEqual(
                _rects_with_stroke(svg, renderer.GREY_BORDER),
                [],
                f"{spec['pattern']} bars/boxes must be flat fill only (grey fill must not pair with a border)",
            )

    def test_gap_row_height_fills_the_band_without_a_fixed_cap(self) -> None:
        items = [{"label": "A", "value": 10}, {"label": "B", "value": 20}, {"label": "C", "value": 30}]
        svg = renderer.render({"pattern": "gap", "headline": "x", "items": items})
        expected_row_h = (renderer.CHART_BOTTOM - renderer.CHART_TOP - 30) / len(items)
        expected_bar_h = expected_row_h * 0.52
        # The old 86px row cap held bar_h to ~44.7px regardless of item count;
        # three items must now use the full uncapped share of the band (~55.8px).
        self.assertGreater(expected_bar_h, 50.0)
        self.assertIn(f'height="{expected_bar_h:.1f}"', svg)

    def test_process_flow_box_height_reduced_and_recentered(self) -> None:
        svg = renderer.render(
            {"pattern": "process_flow", "headline": "x", "steps": [{"label": "A"}, {"label": "B"}]}
        )
        expected_box_h = 104.0
        expected_y = (renderer.CHART_TOP + renderer.CHART_BOTTOM) / 2 - expected_box_h / 2
        self.assertIn(f'height="{expected_box_h:.1f}"', svg)
        self.assertIn(f'y="{expected_y:.1f}"', svg)

    def test_center_block_start_splits_slack_evenly_around_a_short_list(self) -> None:
        # heights sum to 30, +2 gaps of 5 = 40 natural height inside a 100px
        # band: 60px of slack, split evenly above/below the block -> +30.
        start_y = renderer._center_block_start(0.0, 100.0, [10.0, 10.0, 10.0], gap=5.0)
        self.assertEqual(start_y, 30.0)

    def test_center_block_start_falls_back_to_band_start_when_the_band_is_tight(self) -> None:
        # natural height (10*3 + 5*2 = 40) exceeds the 30px band: no slack to
        # distribute, so the block starts at the band's top edge unmoved.
        start_y = renderer._center_block_start(0.0, 30.0, [10.0, 10.0, 10.0], gap=5.0)
        self.assertEqual(start_y, 0.0)

    def test_closing_takeaways_items_anchor_to_row_top_for_a_three_item_list(self) -> None:
        spec = {
            "pattern": "closing",
            "headline": "Three and three",
            "takeaways": ["Unit economics clear the bar", "Risk is concentrated in supply", "Capacity binds"],
            "next_steps": [
                {"action": "Approve pilot budget", "owner": "CFO", "timing": "This week"},
                {"action": "Confirm capacity", "owner": "Ops", "timing": "Two weeks"},
                {"action": "Review results", "owner": "Strategy", "timing": "Q3"},
            ],
        }
        svg = renderer.render(spec)
        # 2026-08-02 panel round 2 divided the band into one row per item
        # (render_gap's technique) instead of whole-block centering, but
        # still centered each item *within* its own row — round 3 found that
        # this degenerates back to whole-block centering whenever a row is
        # much taller than its content (see the 1-item regression test
        # below). Items now anchor to each row's top edge instead.
        band_start = float(renderer.CHART_TOP) + 34
        row_h = (renderer.CHART_BOTTOM - band_start) / 3
        expected_ys = [band_start + i * row_h for i in range(3)]
        for y in expected_ys:
            self.assertIn(f'y="{y:.1f}"', svg)
        # Rows are evenly spaced across the whole band (no single dead gap
        # collecting either right after the label or right before the footer).
        self.assertAlmostEqual(expected_ys[1] - expected_ys[0], expected_ys[2] - expected_ys[1])
        # Item 1 sits exactly at the label's row boundary — no offset at all.
        self.assertEqual(expected_ys[0], band_start)
        self.assertNotIn('y="350.0"', svg, "must not regress to the whole-block-center bug's item-1 position")

    def test_closing_single_takeaway_and_single_next_step_stay_under_their_labels(self) -> None:
        # 2026-08-02 panel round 3 regression: with one item, row_h spans the
        # entire band, so centering *within* the row (the round-2 fix) put
        # the item 182px below its label — the same detachment round 2 had
        # already diagnosed and fixed for 3-item lists, just recurring at
        # n=1. takeaways(1-4) and next_steps(1-5) are both in the documented
        # input range (style-system.md), not edge cases.
        spec = {
            "pattern": "closing",
            "headline": "One thing matters",
            "takeaways": ["Unit economics clear the bar"],
            "next_steps": [{"action": "Approve pilot budget", "owner": "CFO", "timing": "This week"}],
        }
        svg = renderer.render(spec)
        band_start = float(renderer.CHART_TOP) + 34
        self.assertIn(f'y="{band_start:.1f}"', svg)
        # The old within-row centering bug put the sole takeaway at y=390.0
        # for this exact spec (148px below band_start=242.0, 182px below the
        # "KEY TAKEAWAYS" label itself at CHART_TOP=208) and the sole next
        # step at y=380.5, before the round-3 fix anchored both to their
        # row's top edge instead (band_start, same for both columns).
        self.assertNotIn('y="390.0"', svg)
        self.assertNotIn('y="380.5"', svg)

    def test_bullet_list_items_fill_the_band_by_row_instead_of_block_centering(self) -> None:
        spec = {
            "pattern": "bullet_list",
            "headline": "Three constraints",
            "bullets": [
                {"text": "Capacity is fixed until Q3", "sub": ["Hiring freeze through June"]},
                {"text": "Vendor A integration is not yet certified"},
                {"text": "Regional pricing has not been finalized"},
            ],
        }
        svg = renderer.render(spec)
        self.assertIn("Regional pricing has not been finalized", svg)
        # render_gap's "divide the band into one row per item" technique
        # replaces the whole-block center this test locked in until round 2
        # (that bug pinned item 1 far from band_start whenever the 3-item
        # stack left slack in the band). Round 3 dropped the extra
        # center-within-row step on top of that (see the 1-bullet regression
        # test below) — each marker now sits at its row's top edge.
        band_start = float(renderer.CHART_TOP) + 20
        row_h = (renderer.CHART_BOTTOM - band_start) / 3
        row_tops = [band_start + i * row_h for i in range(3)]
        expected_marker_ys = [row_tops[i] - 10 for i in range(3)]
        for marker_y in expected_marker_ys:
            self.assertIn(f'y="{marker_y:.1f}"', svg)
        # Each item gets an equal share of the band (row boundaries are
        # evenly spaced).
        self.assertAlmostEqual(row_tops[1] - row_tops[0], row_tops[2] - row_tops[1])
        old_whole_block_item3_marker_y = 430.0
        self.assertNotIn(f'y="{old_whole_block_item3_marker_y:.1f}"', svg)
        old_within_row_item1_marker_y = row_tops[0] + max(row_h - 48.0, 0.0) / 2 - 10
        self.assertNotIn(f'y="{old_within_row_item1_marker_y:.1f}"', svg)

    def test_bullet_list_single_bullet_stays_under_the_band_start(self) -> None:
        # 2026-08-02 panel round 3 regression: with one bullet, row_h spans
        # the entire band, so centering *within* the row (the round-2 fix)
        # left the text floating in the column's dead center — 154px below
        # band_start, marker at 144px below. bullets(1-6) is a documented
        # input range (style-system.md), not an edge case.
        spec = {
            "pattern": "bullet_list",
            "headline": "One constraint dominates",
            "bullets": [{"text": "Capacity is fixed until Q3"}],
        }
        svg = renderer.render(spec)
        band_start = float(renderer.CHART_TOP) + 20
        marker_y = band_start - 10
        self.assertIn(f'y="{marker_y:.1f}"', svg)
        # The old within-row centering bug put the marker at y=372.0 for
        # this exact spec (144px below band_start=228.0) before the round-3
        # fix anchored it to the row's top edge instead.
        self.assertNotIn('y="372.0"', svg)


if __name__ == "__main__":
    unittest.main()
