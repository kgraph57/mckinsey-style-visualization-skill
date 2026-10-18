from __future__ import annotations

import copy
from contextlib import redirect_stderr
from dataclasses import replace
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from scripts import build_html_deck as classic
from scripts import build_interactive_deck as builder
from scripts import deck_bundle


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = {"basis": "illustrative", "assumptionRefs": ["synthetic-inputs"]}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def static_spec() -> dict:
    return {
        "pattern": "bullet_list",
        "headline": "A focused queue pilot can test the operating model in one week",
        "source": "Illustrative service design exercise",
        "classification": "Illustrative",
        "page_number": 1,
        "bullets": [
            {"text": "Start with one bounded queue", "emphasis": True},
            {"text": "Measure capacity before expanding scope"},
        ],
    }


def slider_scene(*, threshold: float = 32) -> dict:
    return {
        "version": 1,
        "type": "slider_model",
        "purpose": "Find the automation level at which weekly queue capacity meets demand",
        "decisionJob": "decision",
        "interactionRationale": "Decide whether the queue pilot clears the capacity threshold as automation changes",
        "initialState": {"automation": 20},
        "printState": {"automation": 20},
        "quantities": {
            "automation_rate": {"dimension": "ratio", "unit": "percentage_point", "display": "%"},
            "weekly_capacity": {"dimension": "count", "unit": "cases_per_week", "display": "cases/wk"},
        },
        "sources": [{
            "id": "method-note",
            "label": "Illustrative method note",
            "detail": "Original reference-fixture link used only to verify safe explicit navigation.",
            "url": "https://example.com/method",
        }],
        "assumptions": [{
            "id": "synthetic-inputs",
            "label": "All values are synthetic",
            "value": "Reference-deck validation only",
        }],
        "controls": [{
            "id": "automation", "kind": "range", "label": "Automation",
            "min": 0, "max": 80, "step": 5,
            "quantity": "automation_rate", "provenance": copy.deepcopy(PROVENANCE),
        }],
        "model": {
            "kind": "linear",
            "intercept": {"value": 18, "quantity": "weekly_capacity"},
            "terms": {"automation": {
                "coefficient": 0.4,
                "inputQuantity": "automation_rate",
                "outputQuantity": "weekly_capacity",
            }},
            "output": "capacity", "outputQuantity": "weekly_capacity",
            "label": "Weekly capacity", "format": "number", "round": 0,
            "modelProvenance": copy.deepcopy(PROVENANCE),
        },
        "reporting": {"primaryOutput": "capacity", "secondaryOutputs": []},
        "decisionContract": {
            "id": "demand-gate", "metric": {"ref": "output:capacity"}, "operator": "gte",
            "threshold": {
                "value": threshold, "quantity": "weekly_capacity",
                "provenance": copy.deepcopy(PROVENANCE),
            },
            "whenMet": {"status": "Ready", "recommendation": "Run a limited queue pilot"},
            "whenNotMet": {"status": "Below demand", "recommendation": "Increase automation before the pilot"},
        },
        "view": {
            "component": "dot_plot",
            "xLabel": "Automation", "xQuantity": "automation_rate", "xDomain": [0, 80],
            "yLabel": "Weekly capacity", "yQuantity": "weekly_capacity", "yDomain": [0, 50],
            "points": [{
                "id": "service-capacity", "label": "Weekly capacity",
                "x": {"ref": "control:automation"}, "y": {"ref": "output:capacity"},
                "highlight": True,
            }],
        },
        "demo": [
            {"stepKey": "reach-threshold", "action": "set", "control": "automation", "value": 35},
            {"stepKey": "show-evidence", "action": "openEvidence"},
        ],
    }


def slider_spec(*, threshold_text: str = "32 cases/wk", threshold_value: float = 32) -> dict:
    return {
        "pattern": "scatter",
        "headline": "The queue pilot meets demand at 35% automation or more",
        "source": "Illustrative service design exercise",
        "footnotes": ["All values are synthetic and intended only for runtime validation."],
        "classification": "Illustrative",
        "page_number": 2,
        "x_axis": {
            "label": "Automation", "quantity": "automation_rate", "unit": "%",
            "domain": [0, 80], "tick_labels": ["0%", "80%"],
        },
        "y_axis": {
            "label": "Weekly capacity", "quantity": "weekly_capacity", "unit": "cases/wk",
            "domain": [0, 50], "tick_labels": ["0 cases/wk", "50 cases/wk"],
        },
        "points": [{
            "item_id": "service-capacity", "label": "Weekly capacity",
            "x": 20, "y": 26, "emphasis": True,
        }],
        "interactive_result": {
            "quantity": "weekly_capacity", "value": 26,
            "decision_status": "Below demand",
            "recommendation": "Increase automation before the pilot",
            "operator": "gte", "threshold": threshold_value,
        },
        "annotation": (
            "Weekly capacity 26 cases/wk; Below demand; threshold ≥ "
            + threshold_text + "; Increase automation before the pilot"
        ),
    }


def make_fixture(root: Path, *, lang: str | None = "en", threshold: float = 32) -> Path:
    _write_json(root / "specs/01-summary.json", static_spec())
    threshold_text = ("32.0" if isinstance(threshold, float) and str(threshold).endswith(".0") else str(threshold)) + " cases/wk"
    spec = slider_spec(threshold_text=threshold_text, threshold_value=threshold)
    if lang == "ja":
        spec["annotation"] = spec["annotation"].replace("threshold", "しきい値")
    _write_json(root / "specs/02-capacity.json", spec)
    _write_json(root / "scenes/02-capacity.json", slider_scene(threshold=threshold))
    manifest = {
        "title": "Service queue pilot",
        "slides": [
            "specs/01-summary.json",
            {"id": "queue-capacity", "spec": "specs/02-capacity.json", "scene": "scenes/02-capacity.json"},
        ],
    }
    if lang is not None:
        manifest["lang"] = lang
    _write_json(root / "deck.json", manifest)
    return root / "deck.json"


def envelope_from(html_text: str) -> dict:
    match = re.search(r'<div id="idrt-deck-data" hidden data-encoding="base64url-json-v1">([A-Za-z0-9_-]+)</div>', html_text)
    if not match:
        raise AssertionError("deck envelope not found")
    return deck_bundle.decode_envelope(match.group(1))


class StaticSemanticExtractorTests(unittest.TestCase):
    def test_static_semantics_ignore_cross_pattern_fields_and_match_visible_chrome(self) -> None:
        cases = (
            (
                {
                    "pattern": "cover",
                    "title": "Visible cover title",
                    "subtitle": "Visible cover subtitle",
                    "headline": "INVISIBLE HEADLINE",
                    "subline": "INVISIBLE SUBLINE",
                    "annotation": "INVISIBLE ANNOTATION",
                    "source": "INVISIBLE SOURCE",
                    "context": "INVISIBLE CONTEXT",
                    "sections": ["INVISIBLE SECTION"],
                    "contact": ["INVISIBLE CONTACT"],
                },
                "Visible cover title",
                "",
                ("Visible cover subtitle",),
                (
                    "INVISIBLE HEADLINE", "INVISIBLE SUBLINE", "INVISIBLE ANNOTATION",
                    "INVISIBLE SOURCE", "INVISIBLE CONTEXT", "INVISIBLE SECTION",
                    "INVISIBLE CONTACT",
                ),
            ),
            (
                {
                    "pattern": "bullet_list",
                    "headline": "Visible content headline",
                    "subline": "Visible content subline",
                    "annotation": "Visible content annotation",
                    "source": "Visible content source",
                    "bullets": [{"text": "Visible bullet"}],
                    "title": "INVISIBLE TITLE",
                    "subtitle": "INVISIBLE SUBTITLE",
                    "presenter": "INVISIBLE PRESENTER",
                },
                "Visible content headline",
                "Visible content source",
                ("Visible content subline", "Visible bullet", "Visible content annotation"),
                ("INVISIBLE TITLE", "INVISIBLE SUBTITLE", "INVISIBLE PRESENTER"),
            ),
        )
        for spec, headline, source, paragraphs, invisible in cases:
            with self.subTest(pattern=spec["pattern"]):
                svg = builder.render_slide_spec.render(spec)
                summary = builder._static_summary(spec, "Fallback")
                self.assertEqual(summary["headline"], headline)
                self.assertEqual(summary["source"], source)
                self.assertEqual(tuple(summary["paragraphs"]), paragraphs)
                self.assertIn(headline, svg)
                for paragraph in paragraphs:
                    self.assertIn(paragraph, svg)
                for poison in invisible:
                    self.assertNotIn(poison, svg)
                    self.assertNotIn(poison, json.dumps(summary))

    def test_current_visual_patterns_expose_their_primary_details_in_reading_order(self) -> None:
        expected = {
            "arr-waterfall.json": "New enterprise: 3.0 $M",
            "adoption-before-after.json": "AI workflow adoption: 18% → 64%",
            "adoption-trend.json": "Adoption rate: 18, 31, 49, 64%",
            "capacity-gap.json": "Signed commitments: 45",
            "vendor-benchmark.json": "Vendor A: 3.1 | 2.8 | 3.6 | 4.5",
            "eng-incident-flow.json": "Alert fired: Monitoring; minute 0",
            "sales-pipeline-funnel.json": "Leads: 480",
            "marketing-channel-heatmap.json": "Paid search: SMB 140; Mid-market 52; Enterprise 8",
            "pmo-rollout-gantt.json": "Vendor selection: Jan–Feb",
            "hr-talent-scorecard.json": "OFFERS ACCEPTED: 38; Target: 40; +5 vs LQ; good",
            "pricing-retention-scatter.json": "Guided onboarding: 18, 92",
            "product-priority-two-by-two.json": "SSO integration: 20, 82",
            "deal-size-distribution.json": "<$25k: 48",
            "segment-adoption-multiples.json": "Financial services: 22, 35, 51, 68%",
        }
        spec_root = ROOT / "examples/render-specs"
        for filename, detail in expected.items():
            with self.subTest(filename=filename):
                spec = json.loads((spec_root / filename).read_text(encoding="utf-8"))
                paragraphs = builder._static_summary(spec, "Fallback")["paragraphs"]
                self.assertIn(detail, paragraphs)

    def test_static_semantics_follow_variant_visibility_without_truncating_content(self) -> None:
        bare_end = {"pattern": "end_cover"}
        end_svg = builder.render_slide_spec.render(bare_end)
        end_summary = builder._static_summary(bare_end, "Fallback")
        self.assertEqual(end_summary["headline"], "Thank you")
        self.assertIn(end_summary["headline"], end_svg)

        classic_process = {
            "pattern": "process_flow",
            "headline": "Visible process",
            "steps": [{"label": "Visible step", "detail": "Visible detail", "owner": "INVISIBLE OWNER", "duration": "INVISIBLE DURATION"}],
        }
        process_svg = builder.render_slide_spec.render(classic_process)
        process_summary = builder._static_summary(classic_process, "Fallback")
        self.assertEqual(process_summary["paragraphs"], ["Visible step: Visible detail"])
        self.assertNotIn("INVISIBLE OWNER", process_svg)
        self.assertNotIn("INVISIBLE OWNER", json.dumps(process_summary))
        self.assertNotIn("INVISIBLE DURATION", json.dumps(process_summary))

        long_bullets = {
            "pattern": "bullet_list",
            "headline": "All semantic facts remain available",
            "bullets": [{"text": f"Fact {index}"} for index in range(41)],
        }
        self.assertEqual(len(builder._static_summary(long_bullets, "Fallback")["paragraphs"]), 41)

        analytical = {
            "pattern": "distribution",
            "layout": "analytical",
            "headline": "Distribution",
            "exhibit_label": "EXHIBIT 4",
            "bins": [{"label": "A", "value": 2}],
            "commentary": {"title": "Visible conclusion", "points": ["Visible evidence"]},
            "footnotes": ["Visible note"],
        }
        semantic = builder._static_summary(analytical, "Fallback")["paragraphs"]
        for visible in ("EXHIBIT 4", "Visible conclusion", "Visible evidence", "Visible note"):
            self.assertIn(visible, semantic)
            self.assertIn(visible, builder.render_slide_spec.render(analytical))

    def test_static_semantics_include_renderer_derived_text_and_non_color_state(self) -> None:
        visible_cases = (
            ({
                "pattern": "before_after", "headline": "Change",
                "pairs": [{"label": "Adoption", "before": 10, "after": 20, "delta_text": "VISIBLE DELTA"}],
            }, "VISIBLE DELTA"),
            ({
                "pattern": "gap", "headline": "Gap",
                "items": [{"label": "Capacity", "value": 10, "value_text": "VISIBLE VALUE"}],
            }, "VISIBLE VALUE"),
            ({
                "pattern": "funnel", "headline": "Funnel",
                "stages": [{"label": "Start", "value": 100}, {"label": "Next", "value": 25}],
            }, "↓ 25%"),
            ({
                "pattern": "two_by_two", "theme": "executive", "headline": "Matrix",
                "legend_title": "VISIBLE LEGEND", "x_axis": {"label": "x"}, "y_axis": {"label": "y"},
                "points": [{"label": "Option", "x": 50, "y": 50}],
            }, "VISIBLE LEGEND"),
            ({
                "pattern": "heatmap", "headline": "Heat", "unit": "pts",
                "rows": ["Row"], "columns": ["Column"], "values": [[7]],
            }, "7pts"),
            ({
                "pattern": "gantt", "headline": "Plan", "periods": ["USED", "UNUSED PERIOD"],
                "bars": [{"label": "Build", "start": 0, "end": 0}],
            }, "UNUSED PERIOD"),
        )
        for spec, visible in visible_cases:
            with self.subTest(pattern=spec["pattern"], visible=visible):
                svg = builder.render_slide_spec.render(spec)
                summary = builder._static_summary(spec, "Fallback")
                self.assertIn(visible, svg)
                self.assertIn(visible, "\n".join(summary["paragraphs"]))

        state_cases = (
            ({"pattern": "agenda", "headline": "Agenda", "current": 1, "items": [{"title": "Now"}]}, "Current: Now"),
            ({"pattern": "bullet_list", "headline": "Bullets", "bullets": [{"text": "Priority", "emphasis": True}]}, "Emphasized: Priority"),
            ({"pattern": "summary_strip", "headline": "Summary", "focus_block": 0, "blocks": [{"claim": "Focus", "proof": "Proof", "implication": "Act"}]}, "Focused: Focus"),
            ({"pattern": "process_flow", "headline": "Flow", "highlight": 0, "steps": [{"label": "Active"}]}, "Highlighted: Active"),
            ({"pattern": "distribution", "headline": "Distribution", "highlight": 0, "bins": [{"label": "Peak", "value": 1}]}, "Highlighted: Peak"),
            ({"pattern": "small_multiples", "headline": "Charts", "charts": [{"label": "Priority chart", "values": [1], "emphasis": True}]}, "Emphasized: Priority chart"),
            ({"pattern": "two_by_two", "theme": "executive", "headline": "Matrix", "focus_quadrant": 0, "quadrants": ["Focus quadrant"], "x_axis": {"label": "x"}, "y_axis": {"label": "y"}, "points": [{"label": "Priority point", "x": 50, "y": 50, "emphasis": True}]}, "Focused quadrant: Focus quadrant"),
        )
        for spec, marker in state_cases:
            with self.subTest(pattern=spec["pattern"], marker=marker):
                self.assertIn(marker, builder._static_summary(spec, "Fallback", lang="en")["paragraphs"])
        self.assertIn(
            "現在: 今",
            builder._static_summary(
                {"pattern": "agenda", "headline": "予定", "current": 1, "items": [{"title": "今"}]},
                "Fallback", lang="ja",
            )["paragraphs"],
        )

        japanese_kpi = {
            "pattern": "kpi_scorecard", "headline": "指標", "lang": "ja",
            "metrics": [{"label": "成長率", "value": "+10%", "target": "+12%"}],
        }
        japanese_kpi_svg = builder.render_slide_spec.render(japanese_kpi)
        japanese_kpi_paragraphs = builder._static_summary(
            japanese_kpi, "Fallback", lang="ja",
        )["paragraphs"]
        self.assertIn("目標：+12%", japanese_kpi_svg)
        self.assertIn("成長率: +10%; 目標：+12%", japanese_kpi_paragraphs)
        self.assertNotIn("target +12%", "\n".join(japanese_kpi_paragraphs))

    def test_static_semantics_match_valid_optional_renderer_variants(self) -> None:
        before_after = {
            "pattern": "before_after", "headline": "Change", "unit": "%",
            "pairs": [{"label": "Adoption", "before": 1, "after": 2}],
        }
        self.assertIn(
            "Adoption: 1% → 2%",
            builder._static_summary(before_after, "Fallback")["paragraphs"],
        )

        unlabeled_series = {
            "pattern": "time_series", "headline": "Trend", "unit": "%",
            "x_labels": ["Q1", "Q2"], "series": [{"values": [1, 2]}],
        }
        self.assertIn(
            "1%, 2%",
            builder._static_summary(unlabeled_series, "Fallback")["paragraphs"],
        )

        highlighted_gantt = {
            "pattern": "gantt", "headline": "Plan", "periods": ["Q1"],
            "bars": [{"label": "Build", "start": 0, "end": 0, "highlight": True}],
        }
        self.assertIn(
            "Highlighted: Build",
            builder._static_summary(highlighted_gantt, "Fallback")["paragraphs"],
        )

        classic_matrix = {
            "pattern": "two_by_two", "headline": "Matrix", "focus_quadrant": 0,
            "quadrants": ["Classic quadrant"], "x_axis": {"label": "x"},
            "y_axis": {"label": "y"}, "points": [{"label": "Point", "x": 50, "y": 50}],
        }
        self.assertNotIn(
            "Focused quadrant: Classic quadrant",
            builder._static_summary(classic_matrix, "Fallback")["paragraphs"],
        )

        unlabeled_scatter = {
            "pattern": "scatter", "headline": "Scatter",
            "x_axis": {"label": "Automation", "unit": "%", "domain": [0, 100]},
            "y_axis": {"label": "Capacity", "unit": "cases", "domain": [0, 50]},
            "points": [{"x": 10, "y": 20}],
        }
        svg = builder.render_slide_spec.render(unlabeled_scatter)
        paragraphs = builder._static_summary(unlabeled_scatter, "Fallback")["paragraphs"]
        for visible in ("0%", "100%", "0cases", "50cases"):
            self.assertIn(visible, svg)
            self.assertIn(visible, paragraphs)
        self.assertIn("Automation: 10%; Capacity: 20cases", paragraphs)

    def test_scatter_semantics_expose_removed_state_without_color(self) -> None:
        for lang, marker in (("en", "Removed"), ("ja", "除外")):
            spec = {
                "pattern": "scatter", "headline": "Scatter", "lang": lang,
                "x_axis": {"label": "Automation", "unit": "%", "domain": [0, 100]},
                "y_axis": {"label": "Capacity", "unit": "cases", "domain": [0, 50]},
                "points": [{"item_id": "point-1", "label": "Pilot", "x": 10, "y": 20, "removed": True}],
            }
            with self.subTest(lang=lang):
                svg = builder.render_slide_spec.render(spec)
                paragraphs = builder._static_summary(spec, "Fallback", lang=lang)["paragraphs"]
                self.assertIn(f"Pilot · {marker}", svg)
                self.assertTrue(any(f"Pilot · {marker}" in paragraph for paragraph in paragraphs))


class ManifestBoundaryTests(unittest.TestCase):
    def test_fallback_preflight_accepts_every_current_renderer_example(self) -> None:
        paths = [
            *sorted((ROOT / "examples").glob("**/*.json")),
            *sorted((ROOT / "templates").glob("**/specs/*.json")),
        ]
        for path in paths:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or "pattern" not in raw:
                continue
            with self.subTest(path=path):
                scene_adapter = (
                    (ROOT / "examples" / "interactive-deck") in path.parents
                    or (ROOT / "examples" / "interactive-fixtures") in path.parents
                )
                self.assertGreater(
                    builder._validate_fallback_spec(
                        raw, "slide:1/spec", scene_adapter=scene_adapter
                    ),
                    0,
                )

    def test_fallback_preflight_rejects_expensive_shapes_before_renderer_or_xml(self) -> None:
        oversized = (
            (
                {
                    "pattern": "process_flow",
                    "headline": "Too many steps",
                    "steps": [{"label": f"Step {index}"} for index in range(45)],
                },
                "fallback_limit",
            ),
            (
                {
                    "pattern": "gap",
                    "headline": "Too many items",
                    "items": [{"label": f"Item {index}", "value": index} for index in range(3_500)],
                },
                "fallback_limit",
            ),
            (
                {
                    "pattern": "process_flow",
                    "headline": "Pathological wrapping",
                    "steps": [
                        {"label": "A" * builder.MAX_FALLBACK_TEXT_SCALARS,
                         "detail": "B" * builder.MAX_FALLBACK_TEXT_SCALARS}
                        for _ in range(16)
                    ],
                },
                "fallback_limit",
            ),
        )
        for spec, code in oversized:
            with self.subTest(pattern=spec["pattern"]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_json(root / "slide.json", spec)
                _write_json(root / "deck.json", {"slides": ["slide.json"]})
                output = root / "deck.interactive.html"
                output.write_bytes(b"sentinel")
                with (
                    mock.patch.object(builder.render_slide_spec, "render") as render,
                    mock.patch.object(builder, "validate_renderer_svg") as xml_validator,
                    self.assertRaises(deck_bundle.BundleValidationError) as caught,
                ):
                    builder.compile_manifest(root / "deck.json")
                self.assertEqual(caught.exception.issues[0].code, code)
                render.assert_not_called()
                xml_validator.assert_not_called()
                self.assertEqual(output.read_bytes(), b"sentinel")

    def test_deck_accepted_state_budget_is_exact_and_precedes_scene_compilation(self) -> None:
        class CompileReached(Exception):
            pass

        def write_state_deck(root: Path, counts: list[int]) -> Path:
            make_fixture(root)
            slides = []
            for index, count in enumerate(counts, start=1):
                scene = slider_scene()
                scene["controls"][0].update(min=0, max=count - 1, step=1)
                scene["initialState"]["automation"] = 0
                scene["printState"]["automation"] = 0
                scene["model"]["terms"]["automation"]["coefficient"] = 0.0032
                scene["view"]["xDomain"] = [0, count - 1]
                scene["demo"][0]["value"] = 4_375
                scene_path = root / f"scenes/state-{index}.json"
                _write_json(scene_path, scene)

                spec = slider_spec()
                spec["x_axis"].update(
                    domain=[0, count - 1],
                    tick_labels=["0%", f"{count - 1:,}%"],
                )
                spec["points"][0].update(x=0, y=18)
                spec["interactive_result"]["value"] = 18
                spec["annotation"] = (
                    "Weekly capacity 18 cases/wk; Below demand; threshold ≥ "
                    "32 cases/wk; Increase automation before the pilot"
                )
                spec_path = root / f"specs/state-{index}.json"
                _write_json(spec_path, spec)
                slides.append({
                    "id": f"state-{index}",
                    "spec": f"specs/state-{index}.json",
                    "scene": f"scenes/state-{index}.json",
                })
            manifest = root / "deck.json"
            _write_json(manifest, {"title": "State budget", "lang": "en", "slides": slides})
            return manifest

        exact_counts = [10_001] * 6 + [5_530]
        self.assertEqual(sum(exact_counts), 65_536)
        with tempfile.TemporaryDirectory() as directory:
            manifest = write_state_deck(Path(directory), exact_counts)
            with mock.patch.object(builder, "compile_scene", side_effect=CompileReached):
                with self.assertRaises(CompileReached):
                    builder.compile_manifest(manifest)

        for name, counts in (
            ("one_over", [10_001] * 6 + [5_531]),
            ("seven_maximal_scenes", [10_001] * 7),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                manifest = write_state_deck(Path(directory), counts)
                with mock.patch.object(
                    builder,
                    "compile_scene",
                    side_effect=AssertionError("scene compilation reached"),
                ):
                    with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                        builder.compile_manifest(manifest)
                self.assertEqual(caught.exception.issues[0].code, "aggregate_limit")

    def test_fallback_preflight_is_closed_and_normalizes_renderer_failures(self) -> None:
        invalid_specs = (
            ({"pattern": "bullet_list", "headline": "Bad", "bullets": [], "classification": 7}, "fallback_shape"),
            ({"pattern": "bullet_list", "headline": "Bad", "bullets": [{"text": "x", "foreign": True}]}, "fallback_shape"),
            ({"pattern": "time_series", "headline": "Bad", "x_labels": ["Q1"], "series": [{"values": 1}]}, "fallback_shape"),
            ({"pattern": "heatmap", "headline": "Bad", "rows": ["r"], "columns": ["c"], "values": [1]}, "fallback_shape"),
            ({"pattern": "benchmark_table", "headline": "Bad", "columns": ["c"], "rows": [{"label": "r", "values": [1]}], "leaders": [[]]}, "fallback_shape"),
            ({"pattern": "benchmark_table", "headline": "Bad", "columns": ["c"], "rows": [{"label": "r", "values": [1]}], "leaders": None}, "fallback_shape"),
            ({"pattern": "benchmark_table", "headline": "Bad", "columns": ["c"], "rows": [{"label": "r", "values": [1]}], "leaders": True}, "fallback_shape"),
        )
        for spec, code in invalid_specs:
            with self.subTest(spec=spec):
                with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                    builder._validate_fallback_spec(spec, "slide:1/spec")
                self.assertEqual(caught.exception.issues[0].code, code)

        valid = static_spec()
        for error in (AttributeError("secret"), IndexError("secret"), ZeroDivisionError("secret")):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_json(root / "slide.json", valid)
                _write_json(root / "deck.json", {"slides": ["slide.json"]})
                with mock.patch.object(builder.render_slide_spec, "render", side_effect=error):
                    with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                        builder.compile_manifest(root / "deck.json")
                issue = caught.exception.issues[0]
                self.assertEqual(issue.code, "fallback_render")
                self.assertNotIn("secret", str(caught.exception))
                self.assertNotIn(directory, str(caught.exception))

    def test_ranked_list_scene_adapter_accepts_only_closed_item_metadata(self) -> None:
        ranked = {
            "pattern": "bullet_list",
            "headline": "North leads the initial queue",
            "quantity": "priority_score",
            "unit": "priority points",
            "value_domain": [0, 100],
            "baseline": 0,
            "bullets": [{
                "item_id": "north",
                "text": "North queue",
                "rank": 1,
                "metric": 86,
                "removed": False,
                "emphasis": True,
                "sub": ["86 priority points"],
            }],
        }

        self.assertGreater(
            builder._validate_fallback_spec(ranked, "slide:1/spec", scene_adapter=True),
            0,
        )
        with self.assertRaises(deck_bundle.BundleValidationError):
            builder._validate_fallback_spec(ranked, "slide:1/spec")

        poisoned = copy.deepcopy(ranked)
        poisoned["bullets"][0]["tooltip"] = "authored runtime prose"
        with self.assertRaises(deck_bundle.BundleValidationError) as caught:
            builder._validate_fallback_spec(poisoned, "slide:1/spec", scene_adapter=True)
        self.assertEqual(caught.exception.issues[0].code, "fallback_shape")

        for invalid_metric in (True, "86", float("inf")):
            with self.subTest(invalid_metric=invalid_metric):
                invalid = copy.deepcopy(ranked)
                invalid["bullets"][0]["metric"] = invalid_metric
                with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                    builder._validate_fallback_spec(
                        invalid, "slide:1/spec", scene_adapter=True
                    )
                self.assertEqual(caught.exception.issues[0].code, "fallback_shape")

        malformed_domain = copy.deepcopy(ranked)
        malformed_domain["value_domain"] = [100, 0]
        with self.assertRaises(deck_bundle.BundleValidationError) as caught:
            builder._validate_fallback_spec(
                malformed_domain, "slide:1/spec", scene_adapter=True
            )
        self.assertEqual(caught.exception.issues[0].code, "fallback_shape")

    def test_bar_scene_adapter_accepts_declared_quantity_metadata(self) -> None:
        bar = {
            "pattern": "gap",
            "headline": "Capacity starts at two units",
            "quantity": "value",
            "unit": "units",
            "value_domain": [0, 10],
            "baseline": 0,
            "items": [{
                "item_id": "capacity",
                "label": "Capacity",
                "value": 2,
                "value_text": "2 units",
                "removed": False,
                "emphasis": True,
            }],
        }

        self.assertGreater(
            builder._validate_fallback_spec(bar, "slide:1/spec", scene_adapter=True),
            0,
        )
        with self.assertRaises(deck_bundle.BundleValidationError):
            builder._validate_fallback_spec(bar, "slide:1/spec")

    def test_recommendation_scene_adapter_accepts_closed_result_metadata(self) -> None:
        result = {
            "quantity": "points",
            "value": 0,
            "classification": "Early",
            "decision_status": "Hold",
            "recommendation": "Resolve readiness gaps",
            "operator": "gte",
            "threshold": 5,
        }
        recommendations = ({
            "pattern": "closing",
            "headline": "Readiness remains below the action threshold",
            "interactive_result": copy.deepcopy(result),
            "takeaways": ["Readiness score 0 points", "Early"],
            "next_steps": [{"action": "Resolve readiness gaps"}],
        }, {
            "pattern": "summary_strip",
            "headline": "Readiness remains below the action threshold",
            "interactive_result": copy.deepcopy(result),
            "blocks": [{
                "metric": "0 points",
                "claim": "Early",
                "proof": "Hold; threshold at least 5 points",
                "implication": "Resolve readiness gaps",
            }],
        })

        for recommendation in recommendations:
            with self.subTest(pattern=recommendation["pattern"]):
                self.assertGreater(
                    builder._validate_fallback_spec(
                        recommendation, "slide:1/spec", scene_adapter=True
                    ),
                    0,
                )
                with self.assertRaises(deck_bundle.BundleValidationError):
                    builder._validate_fallback_spec(recommendation, "slide:1/spec")

    def test_fallback_preflight_enforces_pattern_relations_and_visible_cardinality(self) -> None:
        invalid = (
            ({"pattern": "waterfall", "headline": "x", "start": {"label": "Start"}, "drivers": [{"label": "d", "value": 1}]}, "fallback_shape"),
            ({"pattern": "gantt", "headline": "x", "periods": ["Q1"], "bars": [{"label": "b", "start": 0, "end": 1}]}, "fallback_shape"),
            ({"pattern": "benchmark_table", "headline": "x", "columns": ["c"], "rows": [{"label": "r", "values": [1]}], "leaders": [[2, 0]]}, "fallback_shape"),
            ({"pattern": "small_multiples", "headline": "x", "charts": [{"label": "c", "values": ["not numeric"]}]}, "fallback_shape"),
            ({"pattern": "two_by_two", "headline": "x", "x_axis": {"label": "x"}, "y_axis": {"label": "y"}, "points": [{"label": "p", "x": "bad", "y": 1}]}, "fallback_shape"),
            ({"pattern": "time_series", "headline": "x", "x_labels": ["Q1"], "series": [{"label": "a", "values": [1]}, {"label": "b", "values": [1]}]}, "fallback_limit"),
            ({"pattern": "bullet_list", "headline": "x", "bullets": [{"text": "b"}], "footnotes": ["1", "2", "3"]}, "fallback_limit"),
            ({"pattern": "end_cover", "contact": ["1", "2", "3", "4", "5"]}, "fallback_limit"),
            ({"pattern": "closing", "headline": "x", "next_steps": [{"action": "a"}], "takeaways": ["1", "2", "3", "4", "5"]}, "fallback_limit"),
            ({"pattern": "closing", "headline": "x", "next_steps": [{"action": str(i)} for i in range(6)]}, "fallback_limit"),
            ({"pattern": "closing", "headline": "x", "annotation": "Visible", "call_to_action": "Shadowed", "next_steps": [{"action": "a"}]}, "fallback_shape"),
        )
        for spec, code in invalid:
            with self.subTest(pattern=spec["pattern"], code=code):
                with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                    builder._validate_fallback_spec(spec, "slide:1/spec")
                self.assertEqual(caught.exception.issues[0].code, code)

        ranked_twelve = {
            "pattern": "bullet_list",
            "headline": "Twelve ranked items",
            "columns": 2,
            "bullets": [{"text": str(index)} for index in range(12)],
        }
        self.assertGreater(
            builder._validate_fallback_spec(ranked_twelve, "slide:1/spec"),
            0,
        )
        ranked_thirteen = copy.deepcopy(ranked_twelve)
        ranked_thirteen["bullets"].append({"text": "12"})
        with self.assertRaises(deck_bundle.BundleValidationError) as caught:
            builder._validate_fallback_spec(ranked_thirteen, "slide:1/spec")
        self.assertEqual(caught.exception.issues[0].code, "fallback_limit")

        bounded_matrix = {
            "pattern": "two_by_two",
            "headline": "Bounded matrix",
            "x_axis": {"label": "x"},
            "y_axis": {"label": "y"},
            "points": [
                {"label": "lower", "x": 0, "y": 0},
                {"label": "upper", "x": 100, "y": 100},
            ],
        }
        self.assertGreater(builder._validate_fallback_spec(bounded_matrix, "slide:1/spec"), 0)
        for axis, value in (("x", -1), ("x", 101), ("y", -1), ("y", 101)):
            outside = copy.deepcopy(bounded_matrix)
            outside["points"][0][axis] = value
            with self.subTest(classic_axis=axis, value=value):
                with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                    builder._validate_fallback_spec(outside, "slide:1/spec")
                self.assertEqual(caught.exception.issues[0].code, "fallback_shape")

        visible_rail = {
            "pattern": "section_divider", "section_number": 2, "title": "Phase",
            "sections": ["Discover", "Deliver"],
        }
        self.assertGreater(builder._validate_fallback_spec(visible_rail, "slide:1/spec"), 0)
        for mutate in (
            lambda spec: spec.update(section_number=3),
            lambda spec: spec.update(sections=["A" * 120, "B" * 120]),
        ):
            hidden_rail = copy.deepcopy(visible_rail)
            mutate(hidden_rail)
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder._validate_fallback_spec(hidden_rail, "slide:1/spec")
            self.assertEqual(caught.exception.issues[0].code, "fallback_shape")

    def test_fallback_grid_geometry_accepts_exact_rows_and_rejects_one_over_before_render(self) -> None:
        cases = (
            ("kpi_scorecard", "metrics", 2),
            ("small_multiples", "charts", 4),
        )
        for pattern, collection, max_rows in cases:
            for columns in (1, 4):
                def item(index: int) -> dict:
                    if pattern == "kpi_scorecard":
                        return {"label": f"Metric {index}", "value": str(index), "target": "target", "trend": "up", "status": "ok"}
                    return {"label": f"Chart {index}", "values": [0, 1]}

                exact = {
                    "pattern": pattern, "headline": "Exact grid", "columns": columns,
                    collection: [item(index) for index in range(max_rows * columns)],
                }
                self.assertGreater(builder._validate_fallback_spec(exact, "slide:1/spec"), 0)
                one_over = copy.deepcopy(exact)
                one_over[collection].append(item(max_rows * columns))
                with self.subTest(pattern=pattern, columns=columns), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    _write_json(root / "slide.json", one_over)
                    _write_json(root / "deck.json", {"slides": ["slide.json"]})
                    with (
                        mock.patch.object(builder.render_slide_spec, "render") as render,
                        mock.patch.object(builder, "validate_renderer_svg") as xml_validator,
                        self.assertRaises(deck_bundle.BundleValidationError) as caught,
                    ):
                        builder.compile_manifest(root / "deck.json")
                    self.assertEqual(caught.exception.issues[0].code, "fallback_limit")
                    render.assert_not_called()
                    xml_validator.assert_not_called()

    def test_exact_json_integral_renderer_fields_compile_without_widening_fractional_values(self) -> None:
        specs = (
            {
                "pattern": "gantt", "headline": "Timeline", "periods": ["Q1"],
                "bars": [{"label": "Build", "start": 0, "end": 0}],
                "gates": [{"label": "Go", "period": 0}],
            },
            {
                "pattern": "agenda", "headline": "Agenda", "current": 1,
                "items": [{"title": "One"}],
            },
            {
                "pattern": "section_divider", "section_number": 1, "title": "Phase",
                "sections": ["Phase"],
            },
            {
                "pattern": "kpi_scorecard", "headline": "Scorecard", "columns": 1,
                "metrics": [{"label": "One", "value": "1"}],
            },
        )
        for index, spec in enumerate(specs):
            with self.subTest(pattern=spec["pattern"]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_json(root / "slide.json", spec)
                _write_json(root / "deck.json", {"slides": ["slide.json"]})
                self.assertEqual(len(builder.compile_manifest(root / "deck.json").slides), 1)

        fractional = copy.deepcopy(specs[0])
        fractional["bars"][0]["start"] = 0.5
        with self.assertRaises(deck_bundle.BundleValidationError) as caught:
            builder._validate_fallback_spec(fractional, "slide:1/spec")
        self.assertEqual(caught.exception.issues[0].code, "fallback_shape")

    def test_extreme_fallback_numbers_reject_before_renderer_or_xml(self) -> None:
        huge = 1e308
        specs = (
            {"pattern": "gap", "headline": "Gap", "items": [{"label": "x", "value": huge}]},
            {"pattern": "funnel", "headline": "Funnel", "stages": [{"label": "x", "value": huge}]},
            {"pattern": "scatter", "headline": "Scatter", "x_axis": {"label": "x"}, "y_axis": {"label": "y"}, "points": [{"label": "x", "x": huge, "y": 1}]},
            {"pattern": "before_after", "headline": "Change", "pairs": [{"label": "x", "before": huge, "after": 1}]},
            {"pattern": "time_series", "headline": "Trend", "x_labels": ["Q1"], "series": [{"values": [huge]}]},
        )
        for spec in specs:
            with self.subTest(pattern=spec["pattern"]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_json(root / "slide.json", spec)
                _write_json(root / "deck.json", {"slides": ["slide.json"]})
                with (
                    mock.patch.object(builder.render_slide_spec, "render") as render,
                    mock.patch.object(builder, "validate_renderer_svg") as xml_validator,
                    self.assertRaises(deck_bundle.BundleValidationError) as caught,
                ):
                    builder.compile_manifest(root / "deck.json")
                self.assertEqual(caught.exception.issues[0].code, "fallback_shape")
                render.assert_not_called()
                xml_validator.assert_not_called()

    def test_zero_baseline_patterns_reject_negative_values_before_renderer_or_xml(self) -> None:
        accepted_zero = (
            {"pattern": "gap", "headline": "Gap", "items": [{"label": "x", "value": 0}]},
            {"pattern": "before_after", "headline": "Change", "pairs": [{"label": "x", "before": 0, "after": 0}]},
            {"pattern": "distribution", "headline": "Distribution", "bins": [{"label": "x", "value": 0}]},
            {"pattern": "funnel", "headline": "Funnel", "stages": [{"label": "x", "value": 0}]},
            {"pattern": "time_series", "headline": "Trend", "x_labels": ["Q1"], "series": [{"values": [0]}]},
            {"pattern": "gap", "headline": "Signed gap", "value_domain": [-2, 2], "baseline": 0, "items": [{"label": "x", "value": -1}]},
            {"pattern": "before_after", "headline": "Signed change", "value_domain": [-2, 2], "baseline": 0, "pairs": [{"label": "x", "before": -1, "after": 1}]},
        )
        for spec in accepted_zero:
            with self.subTest(accepted=spec["pattern"]):
                self.assertGreater(builder._validate_fallback_spec(spec, "slide:1/spec"), 0)

        rejected_negative = (
            {"pattern": "gap", "headline": "Gap", "items": [{"label": "x", "value": -1}]},
            {"pattern": "before_after", "headline": "Change", "pairs": [{"label": "x", "before": 2, "after": -1}]},
            {"pattern": "distribution", "headline": "Distribution", "bins": [{"label": "x", "value": -1}]},
            {"pattern": "funnel", "headline": "Funnel", "stages": [{"label": "x", "value": -1}]},
            {"pattern": "time_series", "headline": "Trend", "x_labels": ["Q1"], "series": [{"values": [-1]}]},
        )
        for spec in rejected_negative:
            with self.subTest(rejected=spec["pattern"]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_json(root / "slide.json", spec)
                _write_json(root / "deck.json", {"slides": ["slide.json"]})
                with (
                    mock.patch.object(builder.render_slide_spec, "render") as render,
                    mock.patch.object(builder, "validate_renderer_svg") as xml_validator,
                    self.assertRaises(deck_bundle.BundleValidationError) as caught,
                ):
                    builder.compile_manifest(root / "deck.json")
                self.assertEqual(caught.exception.issues[0].code, "fallback_shape")
                render.assert_not_called()
                xml_validator.assert_not_called()

    def test_semantic_and_title_bounds_reject_before_renderer_or_xml(self) -> None:
        exact_text = {
            "pattern": "bullet_list", "headline": "ok",
            "bullets": [{"text": "B" * builder.MAX_FALLBACK_TEXT_SCALARS}],
        }
        self.assertGreater(builder._validate_fallback_spec(exact_text, "slide:1/spec"), 0)
        cases = (
            ({"pattern": "bullet_list", "headline": "H" * 501, "bullets": [{"text": "ok"}]}, None),
            ({"pattern": "bullet_list", "headline": "ok", "bullets": [{"text": "B" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1)}]}, None),
            ({"pattern": "bullet_list", "headline": "ok", "annotation": "A" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1), "bullets": [{"text": "ok"}]}, None),
            ({"pattern": "bullet_list", "headline": "ok", "footnotes": ["F" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1)], "bullets": [{"text": "ok"}]}, None),
            ({"pattern": "bullet_list", "headline": "ok", "page_number": "P" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1), "bullets": [{"text": "ok"}]}, None),
            ({"pattern": "bullet_list", "headline": "ok", "bullets": [{"text": "ok", "sub": ["S" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1)]}]}, None),
            ({"pattern": "end_cover", "contact": ["C" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1)]}, None),
            ({"pattern": "closing", "headline": "ok", "takeaways": ["T" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1)], "next_steps": [{"action": "ok"}]}, None),
            ({"pattern": "section_divider", "section_number": 1, "title": "ok", "sections": ["S" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1)]}, None),
            ({"pattern": "benchmark_table", "headline": "ok", "columns": ["c"], "rows": [{"label": "r", "values": ["V" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1)]}]}, None),
            ({"pattern": "kpi_scorecard", "headline": "ok", "metrics": [{"label": "m", "value": "V" * (builder.MAX_FALLBACK_TEXT_SCALARS + 1)}]}, None),
            ({"pattern": "process_flow", "headline": "ok", "steps": [{"label": "L" * 1_500, "detail": "D" * 1_500}]}, None),
            ({"pattern": "bullet_list", "headline": "ok", "bullets": [{"text": "ok"}]}, "T" * 501),
        )
        for spec, title in cases:
            with self.subTest(title=title is not None, pattern=spec["pattern"]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_json(root / "slide.json", spec)
                manifest = {"slides": ["slide.json"]}
                if title is not None:
                    manifest["title"] = title
                _write_json(root / "deck.json", manifest)
                with (
                    mock.patch.object(builder.render_slide_spec, "render") as render,
                    mock.patch.object(builder, "validate_renderer_svg") as xml_validator,
                    self.assertRaises(deck_bundle.BundleValidationError) as caught,
                ):
                    builder.compile_manifest(root / "deck.json")
                self.assertIn(caught.exception.issues[0].code, {"fallback_shape", "summary_shape", "title"})
                render.assert_not_called()
                xml_validator.assert_not_called()

    def test_conservative_element_budget_counts_fallback_and_live_shell_before_render(self) -> None:
        static = static_spec()
        estimate = builder._estimate_fallback_elements(static)
        self.assertGreater(estimate, 0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_json(root / "slide.json", static)
            _write_json(root / "deck.json", {"slides": ["slide.json", "slide.json"]})
            with (
                mock.patch.object(builder, "MAX_ESTIMATED_FALLBACK_ELEMENTS_PER_DECK", estimate * 2 - 1),
                mock.patch.object(builder.render_slide_spec, "render") as render,
                mock.patch.object(builder, "validate_renderer_svg") as xml_validator,
                self.assertRaises(deck_bundle.BundleValidationError) as caught,
            ):
                builder.compile_manifest(root / "deck.json")
            self.assertEqual(caught.exception.issues[0].code, "fallback_limit")
            render.assert_not_called()
            xml_validator.assert_not_called()

        with tempfile.TemporaryDirectory() as directory:
            manifest = make_fixture(Path(directory))
            scene_estimate = builder._estimate_fallback_elements(slider_spec())
            with (
                mock.patch.object(builder, "MAX_ESTIMATED_FALLBACK_ELEMENTS_PER_SLIDE", scene_estimate + builder.LIVE_SHELL_ELEMENT_ALLOWANCE - 1),
                mock.patch.object(builder.render_slide_spec, "render") as render,
                mock.patch.object(builder, "validate_renderer_svg") as xml_validator,
                self.assertRaises(deck_bundle.BundleValidationError) as caught,
            ):
                builder.compile_manifest(manifest)
            self.assertEqual(caught.exception.issues[0].code, "fallback_limit")
            render.assert_not_called()
            xml_validator.assert_not_called()

    def test_raw_fragment_normalizer_clamps_then_snaps_exact_half_away(self) -> None:
        normalize = builder.normalize_raw_range
        kwargs = {"minimum": Decimal("0"), "maximum": Decimal("80"), "step": Decimal("5")}
        expected = {
            "32.4999999": "30",
            "32.5": "35",
            "-999999999999999999999999999999999": "0",
            "+000099.0000000": "80",
        }
        for raw, accepted in expected.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize(raw, **kwargs), accepted)
        signed = {"minimum": Decimal("-0.000002"), "maximum": Decimal("0.000002"), "step": Decimal("0.000001")}
        self.assertEqual(normalize("-0.0000015", **signed), "-0.000001")
        self.assertEqual(normalize("0.0000005", **signed), "0.000001")
        for invalid in (
            "1e2", "NaN", "Infinity", "", "1_0", "１.５", "١.٥", "१.५", "1" * 129,
        ):
            with self.subTest(invalid=invalid), self.assertRaises(deck_bundle.BundleValidationError) as caught:
                normalize(invalid, **kwargs)
            self.assertEqual(caught.exception.issues[0].code, "fragment_number")

    def test_runtime_support_matrix_covers_every_task5_discriminant(self) -> None:
        def disclosure(scene_type: str) -> dict:
            return {
                "type": scene_type,
                "controls": [],
                "model": None,
                "view": None,
                "initialEvaluation": {"view": None},
            }

        def state(component: str, control_kind: str) -> dict:
            return {
                "type": "state_toggle",
                "controls": [{"kind": control_kind}],
                "model": {"kind": "state_map"},
                "view": None,
                "initialEvaluation": {"view": {"component": component}},
            }

        def slider(model: str, component: str) -> dict:
            return {
                "type": "slider_model",
                "controls": [{"kind": "range"}],
                "model": {"kind": model},
                "view": {"component": component},
                "initialEvaluation": {"view": {"component": component}},
            }

        score = {
            "type": "score_model",
            "controls": [
                {"kind": "range"},
                {"kind": "segmented"},
                {"kind": "toggle"},
                {"kind": "select"},
            ],
            "model": {"kind": "score_sum"},
            "view": {"component": "recommendation_panel"},
            "initialEvaluation": {"view": {"component": "recommendation_panel"}},
        }
        supported = {
            "evidence_only": disclosure("evidence_only"),
            "drilldown": disclosure("drilldown"),
            "accordion": disclosure("accordion"),
            "state_segmented_ranked": state("ranked_list", "segmented"),
            "state_select_bar": state("bar_compare", "select"),
            "state_segmented_dot": state("dot_plot", "segmented"),
            "linear_bar": slider("linear", "bar_compare"),
            "lookup_bar": slider("lookup", "bar_compare"),
            "piecewise_dot": slider("piecewise", "dot_plot"),
            "operation_graph_dot": slider("operation_graph", "dot_plot"),
            "score_all_controls": score,
        }
        for label, scene in supported.items():
            with self.subTest(label=label):
                self.assertTrue(builder._runtime_supports_scene(scene))

    def test_runtime_support_matrix_rejects_unsupported_pairs_closed(self) -> None:
        base_slider = {
            "type": "slider_model",
            "controls": [{"kind": "range"}],
            "model": {"kind": "linear"},
            "view": {"component": "bar_compare"},
            "initialEvaluation": {"view": {"component": "bar_compare"}},
        }
        cases = {
            "unknown_scene": {**base_slider, "type": "carousel"},
            "unknown_model": {**base_slider, "model": {"kind": "polynomial"}},
            "slider_ranked": {**base_slider, "view": {"component": "ranked_list"}, "initialEvaluation": {"view": {"component": "ranked_list"}}},
            "slider_select": {**base_slider, "controls": [{"kind": "select"}]},
            "view_mismatch": {**base_slider, "initialEvaluation": {"view": {"component": "dot_plot"}}},
            "state_recommendation": {
                "type": "state_toggle", "controls": [{"kind": "segmented"}],
                "model": {"kind": "state_map"}, "view": None,
                "initialEvaluation": {"view": {"component": "recommendation_panel"}},
            },
            "state_toggle_control": {
                "type": "state_toggle", "controls": [{"kind": "toggle"}],
                "model": {"kind": "state_map"}, "view": None,
                "initialEvaluation": {"view": {"component": "bar_compare"}},
            },
            "score_bar": {
                "type": "score_model", "controls": [{"kind": "toggle"}, {"kind": "select"}],
                "model": {"kind": "score_sum"}, "view": {"component": "bar_compare"},
                "initialEvaluation": {"view": {"component": "bar_compare"}},
            },
            "score_one_control": {
                "type": "score_model", "controls": [{"kind": "toggle"}],
                "model": {"kind": "score_sum"}, "view": {"component": "recommendation_panel"},
                "initialEvaluation": {"view": {"component": "recommendation_panel"}},
            },
            "disclosure_with_control": {
                "type": "drilldown", "controls": [{"kind": "select"}],
                "model": None, "view": None, "initialEvaluation": {"view": None},
            },
        }
        for label, scene in cases.items():
            with self.subTest(label=label):
                self.assertFalse(builder._runtime_supports_scene(scene))

    def test_raw_state_cost_counts_disclosures_and_all_control_domains(self) -> None:
        cases = {
            "evidence_sources": ({"type": "evidence_only", "sources": [{}], "assumptions": []}, 2),
            "evidence_assumptions": ({"type": "evidence_only", "sources": [], "assumptions": [{}]}, 2),
            "evidence_both": ({"type": "evidence_only", "sources": [{}], "assumptions": [{}]}, 4),
            "drilldown": ({"type": "drilldown", "panels": [{}, {}]}, 3),
            "accordion_none": ({"type": "accordion", "items": [{}, {}], "allowNone": True}, 3),
            "accordion_required": ({"type": "accordion", "items": [{}, {}], "allowNone": False}, 2),
            "range": ({"type": "slider_model", "controls": [{"kind": "range", "min": Decimal("0"), "max": Decimal("2"), "step": Decimal("1")}]}, 3),
            "all_control_kinds": ({
                "type": "score_model",
                "controls": [
                    {"kind": "range", "min": Decimal("0"), "max": Decimal("2"), "step": Decimal("1")},
                    {"kind": "segmented", "options": [{}, {}]},
                    {"kind": "toggle", "options": [{}, {}]},
                    {"kind": "select", "options": [{}, {}, {}]},
                ],
            }, 36),
        }
        for label, (scene, expected) in cases.items():
            with self.subTest(label=label):
                self.assertEqual(builder._retained_scene_state_count(scene, "scene"), expected)

        for scene in (
            {"type": "accordion", "items": [{}], "allowNone": None},
            {"type": "drilldown", "panels": "not-an-array"},
        ):
            with self.subTest(rejected=scene["type"]), self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder._retained_scene_state_count(scene, "scene")
            self.assertEqual(caught.exception.issues[0].code, "scene_shape")

    def test_mixed_manifest_compiles_exact_task3_wire_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_fixture(Path(directory))
            compiled = builder.compile_manifest(manifest)
            self.assertEqual(compiled.title, "Service queue pilot")
            self.assertEqual(compiled.lang, "en")
            self.assertEqual([slide.slide_id for slide in compiled.slides], ["slide-001", "queue-capacity"])
            self.assertIsNone(compiled.slides[0].scene)
            scene = compiled.slides[1].scene
            self.assertEqual(scene["locale"], "en")
            self.assertEqual(scene["controls"][0]["min"], "0")
            self.assertEqual(scene["controls"][0]["max"], "80")
            self.assertEqual(scene["model"]["kind"], "linear")
            self.assertEqual(scene["model"]["terms"][0][0], "automation")
            self.assertEqual(scene["model"]["terms"][0][1]["value"]["value"], "0.4")
            self.assertEqual(scene["initialEvaluation"]["outputs"]["capacity"]["value"], "26")
            self.assertEqual(scene["initialEvaluation"]["decision"]["outcome"], "notMet")
            self.assertEqual(scene["initialEvaluation"]["view"]["points"][0]["xText"], "20%")
            self.assertEqual(scene["steps"][0]["targetKey"], "control:automation")
            self.assertEqual(scene["evidence"]["badge"], "illustrative")
            self.assertNotIn("audit", scene)
            self.assertNotIn(str(Path(directory)), json.dumps(scene))
            self.assertEqual(compiled.author_records[0].audit.accepted_state_count, 17)

            # This is the complete public Task 3 handshake, not a projection
            # through private compiler helpers. Any serialized-key drift must
            # be reviewed deliberately before the browser consumer changes.
            wire = json.dumps(scene, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.assertEqual(len(wire), 9_490)
            self.assertEqual(
                hashlib.sha256(wire).hexdigest(),
                "2221b23a911c127f8aef1aa738223531c573ce31941df7edae8c0ca0ffb09066",
            )

            intercept = Decimal(scene["model"]["intercept"]["value"])
            coefficient = Decimal(scene["model"]["terms"][0][1]["value"]["value"])
            checkpoints = {0: 18, 20: 26, 30: 30, 35: 32, 40: 34, 80: 50}
            self.assertEqual(
                {value: intercept + coefficient * value for value in checkpoints},
                {value: Decimal(expected) for value, expected in checkpoints.items()},
            )
            threshold = Decimal(scene["decisionContract"]["threshold"]["value"])
            self.assertFalse(intercept + coefficient * 30 >= threshold)
            self.assertTrue(intercept + coefficient * 35 >= threshold)
            x0, y0, width, height = map(Decimal, (130, 208, 1020, 352))
            position = lambda x, y: (
                x0 + width * Decimal(x) / Decimal(80),
                y0 + height - height * Decimal(y) / Decimal(50),
            )
            self.assertEqual(position(20, 26), (Decimal("385"), Decimal("376.96")))
            self.assertEqual(position(35, 32), (Decimal("576.25"), Decimal("334.72")))
            self.assertEqual(position(80, 50), (Decimal("1150"), Decimal("208")))

    def test_scene_requires_language_and_explicit_unsupported_language_always_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = make_fixture(root, lang=None)
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(missing)
            self.assertEqual(caught.exception.issues[0].code, "language")
            manifest = json.loads(missing.read_text(encoding="utf-8"))
            manifest["lang"] = "fr"
            _write_json(missing, manifest)
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(missing)
            self.assertEqual(caught.exception.issues[0].code, "language")

            # A legacy all-static manifest keeps the interactive builder's safe en default.
            manifest["slides"] = ["specs/01-summary.json"]
            manifest.pop("lang")
            _write_json(missing, manifest)
            self.assertEqual(builder.compile_manifest(missing).lang, "en")
            manifest["lang"] = "fr"
            _write_json(missing, manifest)
            with self.assertRaises(deck_bundle.BundleValidationError):
                builder.compile_manifest(missing)

            ja_root = root / "ja"
            japanese = make_fixture(ja_root, lang="ja")
            payload = envelope_from(builder.build_deck(japanese))
            self.assertEqual((payload["lang"], payload["locale"]), ("ja", "ja-JP"))

    def test_strict_manifest_rejects_duplicate_depth_slide_limit_and_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = make_fixture(root)
            manifest_path.write_text('{"title":"A","title":"B","lang":"en","slides":[]}', encoding="utf-8")
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(manifest_path)
            self.assertEqual(caught.exception.issues[0].code, "duplicate_json_key")

            manifest = {"title": "x", "slides": ["specs/01-summary.json"] * 65}
            _write_json(manifest_path, manifest)
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(manifest_path)
            self.assertEqual(caught.exception.issues[0].code, "slide_limit")

            for raw in ("../outside.json", "/tmp/outside.json", "nested/../outside.json", "bad\u0000.json"):
                with self.subTest(raw=raw):
                    manifest = {"title": "x", "slides": [raw]}
                    _write_json(manifest_path, manifest)
                    with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                        builder.compile_manifest(manifest_path)
                    self.assertEqual(caught.exception.issues[0].code, "path_escape")

            for raw in (r"C:\\private\\slide.json", r"folder\\..\\slide.json", "missing.json", "specs"):
                with self.subTest(raw=raw):
                    _write_json(manifest_path, {"title": "x", "slides": [raw]})
                    with self.assertRaises(builder.BundleValidationError):
                        builder.compile_manifest(manifest_path)

            nested: dict = {}
            cursor = nested
            for _ in range(builder.MAX_DEPTH + 2):
                cursor["next"] = {}
                cursor = cursor["next"]
            _write_json(manifest_path, {
                "title": "x", "metadata": nested, "slides": ["specs/01-summary.json"],
            })
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(manifest_path)
            self.assertEqual(caught.exception.issues[0].code, "json_depth")

    def test_strict_input_byte_limits_are_inclusive_and_specs_reject_duplicate_or_nonfinite_json(self) -> None:
        with self.assertRaises(deck_bundle.BundleValidationError) as caught:
            builder.compile_manifest(Path(os.devnull))
        self.assertEqual(caught.exception.issues[0].code, "input_type")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = make_fixture(root)
            manifest_size = manifest_path.stat().st_size
            with mock.patch.object(builder, "MAX_MANIFEST_BYTES", manifest_size):
                self.assertEqual(len(builder.compile_manifest(manifest_path).slides), 2)
            with mock.patch.object(builder, "MAX_MANIFEST_BYTES", manifest_size - 1):
                with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                    builder.compile_manifest(manifest_path)
                self.assertEqual(caught.exception.issues[0].code, "input_limit")

            spec_path = root / "specs/01-summary.json"
            spec_path.write_text('{"pattern":"cover","pattern":"cover"}', encoding="utf-8")
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(manifest_path)
            self.assertEqual(caught.exception.issues[0].code, "duplicate_json_key")
            spec_path.write_text('{"pattern":"cover","title":NaN}', encoding="utf-8")
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(manifest_path)
            self.assertEqual(caught.exception.issues[0].code, "json_shape")

    def test_spec_scene_and_aggregate_byte_limits_are_inclusive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            spec_sizes = [path.stat().st_size for path in sorted((root / "specs").glob("*.json"))]
            scene_size = (root / "scenes/02-capacity.json").stat().st_size
            aggregate = sum(spec_sizes) + scene_size
            boundaries = (
                ("MAX_SPEC_BYTES", max(spec_sizes)),
                ("MAX_SCENE_BYTES", scene_size),
                ("MAX_INPUT_BYTES", aggregate),
            )
            for constant, exact in boundaries:
                with self.subTest(constant=constant, boundary="exact"):
                    with mock.patch.object(builder, constant, exact):
                        self.assertEqual(len(builder.compile_manifest(manifest).slides), 2)
                with self.subTest(constant=constant, boundary="one-over"):
                    with mock.patch.object(builder, constant, exact - 1):
                        with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                            builder.compile_manifest(manifest)
                    self.assertEqual(caught.exception.issues[0].code, "input_limit")

    def test_json_shape_budgets_are_inclusive_with_stable_one_over_codes(self) -> None:
        scalar = '{"a":"é"}'.encode("utf-8")
        cases = (
            ("MAX_NODES", 3, "json_nodes"),
            ("MAX_STRINGS", 2, "json_strings"),
            ("MAX_STRING_BYTES", 3, "json_string_bytes"),
        )
        for constant, exact, code in cases:
            with self.subTest(constant=constant, boundary="exact"):
                with mock.patch.object(builder, constant, exact):
                    self.assertEqual(
                        builder._strict_json_bytes(scalar, "spec.json", exact_numbers=True),
                        {"a": "é"},
                    )
            with self.subTest(constant=constant, boundary="one-over"):
                with mock.patch.object(builder, constant, exact - 1):
                    with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                        builder._strict_json_bytes(scalar, "spec.json", exact_numbers=True)
                self.assertEqual(caught.exception.issues[0].code, code)

        nested = b'{"a":{"b":0}}'
        with mock.patch.object(builder, "MAX_DEPTH", 2):
            self.assertEqual(builder._strict_json_bytes(nested, "spec.json", exact_numbers=True)["a"]["b"], 0)
        with mock.patch.object(builder, "MAX_DEPTH", 1):
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder._strict_json_bytes(nested, "spec.json", exact_numbers=True)
        self.assertEqual(caught.exception.issues[0].code, "json_depth")

    def test_symlinked_parent_cannot_escape_the_manifest_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            manifest_path = make_fixture(root)
            outside = Path(outside_directory)
            _write_json(outside / "private.json", static_spec())
            (root / "outside-parent").symlink_to(outside, target_is_directory=True)
            _write_json(manifest_path, {"title": "x", "slides": ["outside-parent/private.json"]})
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(manifest_path)
            self.assertEqual(caught.exception.issues[0].code, "path_escape")

    def test_unknown_manifest_metadata_keeps_current_json_number_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = make_fixture(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["metadata"] = {"ratio": 0.5, "count": 3}
            _write_json(manifest_path, manifest)
            self.assertEqual(len(builder.compile_manifest(manifest_path).slides), 2)

            text = manifest_path.read_text(encoding="utf-8").replace(
                '"metadata": {',
                '"overflow": 1e9999999,\n  "metadata": {',
                1,
            )
            manifest_path.write_text(text, encoding="utf-8")
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(manifest_path)
            self.assertEqual(caught.exception.issues[0].code, "json_number")

    def test_exact_spec_numbers_reject_unbounded_decimal_exponents_before_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.json"
            path.write_text('{"metadata":1e999999999}', encoding="utf-8")
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder._strict_json(path, byte_limit=builder.MAX_SPEC_BYTES, exact_numbers=True)
            self.assertEqual(caught.exception.issues[0].code, "json_number")

            path.write_text('{"metadata":1e999999999999999999999999}', encoding="utf-8")
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder._strict_json(path, byte_limit=builder.MAX_SPEC_BYTES, exact_numbers=True)
            self.assertEqual(caught.exception.issues[0].code, "json_number")

            path.write_text('{"metadata":1e2}', encoding="utf-8")
            parsed = builder._strict_json(path, byte_limit=builder.MAX_SPEC_BYTES, exact_numbers=True)
            self.assertEqual(builder._renderer_copy(parsed)["metadata"], 100)

    def test_json_node_budget_is_deck_wide_across_manifest_and_specs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec = {"pattern": "cover", "title": "Safe", "metadata": [0] * 20}
            _write_json(root / "one.json", spec)
            _write_json(root / "two.json", spec)
            manifest = root / "deck.json"
            _write_json(manifest, {"title": "Safe", "slides": ["one.json", "two.json"]})
            with mock.patch.object(builder, "MAX_NODES", 40):
                with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                    builder.compile_manifest(manifest)
            self.assertEqual(caught.exception.issues[0].code, "json_nodes")

    def test_json_budget_rejects_before_full_tree_materialization(self) -> None:
        payload = b'{"metadata":[0,0,0,0,0,0]}'
        with (
            mock.patch.object(builder, "MAX_NODES", 5),
            mock.patch.object(builder.json, "loads", side_effect=AssertionError("full decode reached")),
        ):
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder._strict_json_bytes(
                    payload,
                    "spec.json",
                    exact_numbers=True,
                    budget=builder._JsonBudget(),
                )
        self.assertEqual(caught.exception.issues[0].code, "json_nodes")

    def test_preflight_retains_bounded_inputs_across_path_swap(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            manifest = make_fixture(root)
            outside = Path(outside_directory) / "outside.json"
            outside_spec = static_spec()
            outside_spec["headline"] = "OUTSIDE SECRET MUST NOT BE READ"
            _write_json(outside, outside_spec)
            original_normalize = builder.normalize_manifest

            def swap_after_preflight(raw_manifest, manifest_path, *, interactive=False):
                spec_path = root / "specs/01-summary.json"
                spec_path.unlink()
                spec_path.symlink_to(outside)
                (root / "scenes/02-capacity.json").write_bytes(
                    b" " * (builder.MAX_SCENE_BYTES + 1)
                )
                return original_normalize(raw_manifest, manifest_path, interactive=interactive)

            with mock.patch.object(builder, "normalize_manifest", side_effect=swap_after_preflight):
                compiled = builder.compile_manifest(manifest)
            self.assertEqual(compiled.slides[0].headline, static_spec()["headline"])
            self.assertNotIn("OUTSIDE SECRET", compiled.slides[0].fallback_svg.serialized)
            self.assertIsNotNone(compiled.slides[1].scene)

    def test_interactive_build_confines_symlink_leaf_but_allows_in_root_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory:
            root = Path(directory)
            manifest_path = make_fixture(root)
            outside = Path(outside_directory) / "private.json"
            _write_json(outside, static_spec())
            (root / "escape.json").symlink_to(outside)
            manifest = {"title": "x", "slides": ["escape.json"]}
            _write_json(manifest_path, manifest)
            with self.assertRaises(deck_bundle.BundleValidationError) as caught:
                builder.compile_manifest(manifest_path)
            self.assertEqual(caught.exception.issues[0].code, "path_escape")

            (root / "inside-link.json").symlink_to(root / "specs/01-summary.json")
            manifest["slides"] = ["inside-link.json"]
            _write_json(manifest_path, manifest)
            self.assertEqual(len(builder.compile_manifest(manifest_path).slides), 1)

    def test_evidence_runtime_pair_builds_and_fallback_mismatch_fails_before_bundling(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = make_fixture(root)
            scene = slider_scene()
            scene["type"] = "evidence_only"
            for key in ("quantities", "controls", "model", "reporting", "decisionContract", "view"):
                scene.pop(key)
            scene["initialState"] = {"evidence": "closed"}
            scene["printState"] = {"evidence": "closed"}
            scene["fallbackSummary"] = {"field": "headline", "text": slider_spec()["headline"]}
            scene.pop("demo")
            _write_json(root / "scenes/02-capacity.json", scene)
            compiled = builder.compile_manifest(manifest_path)
            self.assertEqual(compiled.slides[1].scene["type"], "evidence_only")
            self.assertIsNone(compiled.slides[1].scene["initialEvaluation"]["view"])

            _write_json(root / "scenes/02-capacity.json", slider_scene())
            spec = slider_spec()
            spec["points"][0]["y"] = 27
            _write_json(root / "specs/02-capacity.json", spec)
            with self.assertRaises(Exception) as caught:
                builder.compile_manifest(manifest_path)
            self.assertIn("fallback_mismatch", str(caught.exception))

    def test_task4_accepts_compiler_valid_literal_dot_slots_for_the_browser_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = make_fixture(root)
            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["view"]["points"].append({
                "id": "literal-reference",
                "label": "Literal reference",
                "x": {
                    "value": 60,
                    "quantity": "automation_rate",
                    "provenance": copy.deepcopy(PROVENANCE),
                },
                "y": {
                    "value": 42,
                    "quantity": "weekly_capacity",
                    "provenance": copy.deepcopy(PROVENANCE),
                },
            })
            _write_json(scene_path, scene)
            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["points"].append({
                "item_id": "literal-reference", "label": "Literal reference",
                "x": 60, "y": 42, "emphasis": False,
            })
            _write_json(spec_path, spec)
            html_text = builder.build_deck(manifest_path)
            payload = envelope_from(html_text)
            literal = payload["slides"][1]["scene"]["view"]["points"][1]
            self.assertEqual((literal["x"]["value"], literal["y"]["value"]), ("60", "42"))
            self.assertIn('id="idsvg-2-live-shell-literal-reference"', html_text)
            self.assertIn('id="idsvg-2-live-shell-LivePointLabel-literal-reference"', html_text)


class AssemblyAndCliTests(unittest.TestCase):
    def test_rank_bridge_is_a_bounded_presentation_only_modifier(self) -> None:
        compiled = builder.compile_manifest(ROOT / "examples/interactive-deck/deck.json")
        slide = compiled.slides[3]
        self.assertEqual(slide.visual_layout, "rank_bridge")
        self.assertIn("LiveBaseMetric-east", slide.live_shell_svg.serialized)
        self.assertIn("LiveBridge-east", slide.live_shell_svg.serialized)
        self.assertNotIn("visual_layout", slide.scene)
        assets = deck_bundle.load_runtime_assets()
        bridge_html = deck_bundle.bundle_deck(title=compiled.title, lang=compiled.lang,
                                             slides=compiled.slides, assets=assets)
        plain_html = deck_bundle.bundle_deck(title=compiled.title, lang=compiled.lang,
                                            slides=tuple(replace(item, visual_layout=None) for item in compiled.slides), assets=assets)
        envelope = r'<div id="idrt-deck-data" hidden data-encoding="base64url-json-v1">([^<]+)</div>'
        self.assertEqual(re.search(envelope, bridge_html).group(1), re.search(envelope, plain_html).group(1))
        self.assertRegex(bridge_html, r'<section[^>]+data-visual-layout="rank_bridge"')
        self.assertNotRegex(plain_html, r'<section[^>]+data-visual-layout="rank_bridge"')

    def test_rank_bridge_does_not_override_dense_or_unvalidated_rank_views(self) -> None:
        context = {"model_context": {"kind": "scenario_compare"}}
        for count in (1, 4, 12):
            self.assertFalse(builder._rank_bridge_layout(context, {"component": "ranked_list", "items": [{}] * count}))
        self.assertTrue(builder._rank_bridge_layout(context, {"component": "ranked_list", "items": [{}, {}, {}]}))
        self.assertFalse(builder._rank_bridge_layout({}, {"component": "ranked_list", "items": [{}, {}, {}]}))

    def test_print_css_does_not_force_a_blank_page_after_the_last_slide(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            html_text = builder.build_deck(make_fixture(Path(directory)))

        self.assertIn(
            "#idrt-deck-pages > .slide:last-child { break-after: auto; page-break-after: auto; }",
            html_text,
        )
        self.assertNotIn(
            ".slide:last-of-type { break-after: auto; page-break-after: auto; }",
            html_text,
        )
        self.assertIn(
            "#idrt-presenter-status,\n  .skip-link { display: none !important; }",
            html_text,
        )

    def test_cli_usage_errors_are_one_fixed_path_safe_diagnostic(self) -> None:
        cases = (
            ["--manifest", "/private/secret-manifest.json", "-o", "/tmp/deck.interactive.html", "--unknown", "/private/secret-value"],
            ["--manifest", "/private/secret-manifest.json", "-o", "/tmp/deck.interactive.html", "/private/secret-trailing"],
            ["--manifest", "/private/secret-manifest.json"],
        )
        for argv in cases:
            stderr = io.StringIO()
            with self.subTest(argv=argv), redirect_stderr(stderr):
                status = builder.main(argv)
            self.assertEqual(status, 2)
            self.assertEqual(
                stderr.getvalue(),
                "ERROR: interactive deck build failed [cli_usage]\n",
            )
            self.assertNotIn("usage:", stderr.getvalue())
            self.assertNotIn("private", stderr.getvalue())
            self.assertNotIn("secret", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_cli_catches_ordinary_failures_with_one_payload_free_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            output = root / "deck.interactive.html"
            output.write_bytes(b"sentinel")
            cases = (
                (AttributeError("secret attribute"), "internal_error"),
                (IndexError("secret index"), "internal_error"),
                (ZeroDivisionError("secret arithmetic"), "internal_error"),
            )
            for error, code in cases:
                with self.subTest(error=type(error).__name__):
                    stderr = io.StringIO()
                    with mock.patch.object(builder, "build_deck", side_effect=error), redirect_stderr(stderr):
                        status = builder.main([
                            "--manifest", str(manifest), "-o", str(output),
                        ])
                    self.assertEqual(status, 1)
                    self.assertEqual(stderr.getvalue(), f"ERROR: interactive deck build failed [{code}]\n")
                    self.assertNotIn(directory, stderr.getvalue())
                    self.assertNotIn("secret", stderr.getvalue())
                    self.assertNotIn("Traceback", stderr.getvalue())
                    self.assertEqual(output.read_bytes(), b"sentinel")

    def test_cli_hides_invalid_paths_and_values_from_validation_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "hostile\n\x1b[31m-path"
            root.mkdir()
            _write_json(root / "slide.json", {
                "pattern": "bullet_list",
                "headline": "Invalid",
                "classification": 7,
                "bullets": [{"text": "x"}],
            })
            _write_json(root / "deck.json", {"slides": ["slide.json"]})
            output = root / "deck.interactive.html"
            output.write_bytes(b"sentinel")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                status = builder.main([
                    "--manifest", str(root / "deck.json"), "-o", str(output),
                ])
            self.assertEqual(status, 1)
            self.assertEqual(stderr.getvalue(), "ERROR: interactive deck build failed [fallback_shape]\n")
            self.assertNotIn(directory, stderr.getvalue())
            self.assertNotIn("\x1b", stderr.getvalue())
            self.assertEqual(output.read_bytes(), b"sentinel")

    def test_japanese_artifact_localizes_every_fixed_accessible_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            html_text = builder.build_deck(make_fixture(Path(directory), lang="ja"))
        payload = envelope_from(html_text)
        self.assertEqual((payload["lang"], payload["locale"]), ("ja", "ja-JP"))
        expected = (
            '<html lang="ja">',
            '>根拠を表示</button>',
            '<h3>出典</h3>',
            '<h3>仮定</h3>',
            '<h3>計算式</h3>',
            'aria-label="スライド内リンク"',
            '>前へ</a>',
            '>次へ</a>',
            '>スライドへ移動</a>',
            'aria-label="スライドナビゲーション"',
        )
        for label in expected:
            with self.subTest(label=label):
                self.assertIn(label, html_text)
        for english in (
            '>Open evidence</button>', '<h3>Sources</h3>', '<h3>Assumptions</h3>',
            '<h3>Formula</h3>', 'aria-label="Slide links"', '>Previous</a>', '>Next</a>',
            '>Skip to slides</a>', 'aria-label="Slide navigation"',
        ):
            self.assertNotIn(english, html_text)

    def test_live_shell_internal_ids_cannot_collide_with_authored_point_ids(self) -> None:
        for point_id in ("chart-clip", "chart_band"):
            with self.subTest(point_id=point_id), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest = make_fixture(root)
                scene_path = root / "scenes/02-capacity.json"
                scene = json.loads(scene_path.read_text(encoding="utf-8"))
                scene["view"]["points"][0]["id"] = point_id
                _write_json(scene_path, scene)
                spec_path = root / "specs/02-capacity.json"
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                spec["points"][0]["item_id"] = point_id
                _write_json(spec_path, spec)

                html_text = builder.build_deck(manifest)
                live = re.search(r'<div class="live-layer" hidden>(.*?)</div>', html_text, re.S).group(1)
                ids = re.findall(r'\bid="([^"]+)"', live)
                self.assertEqual(len(ids), len(set(ids)))
                self.assertIn(f'id="idsvg-2-live-shell-{point_id}"', live)
                self.assertIn('id="idsvg-2-live-shell-LiveChartClip"', live)
                self.assertIn('id="idsvg-2-live-shell-LiveChartBand"', live)
                self.assertIn('clip-path="url(#idsvg-2-live-shell-LiveChartClip)"', live)

    def test_task5_live_shells_prebuild_stable_keyed_chart_geometry(self) -> None:
        spec = static_spec()
        bar = builder._bar_live_shell(
            spec,
            {"quantities": {"capacity": {"display": "units"}}},
            {
                "component": "bar_compare",
                "quantity": "capacity",
                "domain": ["0", "4"],
                "items": [{
                    "id": "capacity", "label": "Capacity", "removed": False,
                    "value": {"value": "2"}, "valueText": "2 units",
                    "emphasis": False,
                }],
            },
        )
        ranked = builder._ranked_live_shell(
            spec,
            {"locale": "en-US"},
            {
                "component": "ranked_list",
                "domain": ["0", "10"],
                "items": [{
                    "id": "north", "label": "North", "rank": 1,
                    "removed": False, "emphasis": True, "metricText": "8 units", "metric": {"value": "8"},
                }],
            },
        )
        recommendation = builder._recommendation_live_shell(
            spec,
            {
                "controls": [{"id": "capacity", "label": "Capacity"}, {"id": "data", "label": "Data"}],
                "initialState": {"capacity": "high", "data": "ready"},
                "decisionContract": {"threshold": {"value": "20"}},
                "model": {"contributions": [["capacity", [["high", {"value": "10"}]]], ["data", [["ready", {"value": "5"}]]]], "bands": [
                    {"id": "early", "label": "Early", "min": {"value": "10"}, "max": {"value": "20"}},
                    {"id": "ready", "label": "Ready", "min": {"value": "20"}, "max": {"value": "30"}},
                ]},
                "initialEvaluation": {
                    "outputs": {"score": {"value": "15"}, "classification": {"value": "Early"}}
                },
                "outputDefinitions": {"score": {"quantity": "points", "round": 0}},
                "quantities": {"points": {"display": "points"}},
            },
            {"component": "recommendation_panel", "score": {"value": "15"}},
        )

        for shell in (bar, ranked, recommendation):
            self.assertIn('id="LiveChartBand"', shell)
            self.assertIn('id="LiveDomainStart"', shell)
            self.assertIn('id="LiveDomainEnd"', shell)
        self.assertIn('id="LiveMark-capacity"', bar)
        self.assertIn('id="LiveLabel-capacity"', bar)
        self.assertIn('id="LiveValue-capacity"', bar)
        self.assertIn('id="LiveMark-north"', ranked)
        self.assertIn('id="LiveValue-north"', ranked)
        ranked_root = ET.fromstring(ranked)
        ranked_bar = ranked_root.find(".//{http://www.w3.org/2000/svg}g[@id='LiveMark-north']/{http://www.w3.org/2000/svg}rect")
        self.assertEqual(ranked_bar.attrib["width"], "552.0")  # 8 / 10 of the fixed 690-unit scale
        self.assertIn('id="LiveScoreCursor"', recommendation)
        self.assertIn('id="LiveScoreValue"', recommendation)
        self.assertIn('id="LiveClassification"', recommendation)

        root = ET.fromstring(recommendation)
        namespace = {"svg": "http://www.w3.org/2000/svg"}
        for band_id in ("LiveBand-early", "LiveBand-ready"):
            band = root.find(f".//svg:rect[@id='{band_id}']", namespace)
            self.assertIsNotNone(band)
            self.assertEqual(band.attrib["width"], "350.0")

        long_id = "item" + ("x" * 60)
        self.assertEqual(
            builder._live_svg_id("LiveMark", long_id, 1),
            builder._live_svg_id("LiveMark", long_id, 12),
        )

        dense_bar = builder._bar_live_shell(
            spec,
            {"quantities": {"capacity": {"display": "units"}}},
            {
                "component": "bar_compare", "quantity": "capacity", "domain": ["0", "12"],
                "items": [
                    {
                        "id": f"bar-{index}", "label": f"Bar {index}", "removed": False,
                        "value": {"value": str(index)}, "valueText": f"{index} units",
                        "emphasis": index == 1,
                    }
                    for index in range(1, 13)
                ],
            },
        )
        dense_ranked = builder._ranked_live_shell(
            spec,
            {"locale": "en-US"},
            {
                "component": "ranked_list",
                "items": [
                    {
                        "id": f"rank-{index}", "label": f"Rank {index}", "rank": index,
                        "removed": False, "emphasis": index == 1, "metricText": "",
                    }
                    for index in range(1, 13)
                ],
            },
        )
        for component, shell in (("bar", dense_bar), ("ranked", dense_ranked)):
            dense_root = ET.fromstring(shell)
            if component == "bar":
                mark_rects = [
                    node for node in dense_root.findall(".//svg:rect", namespace)
                    if node.attrib.get("id", "").startswith("LiveMark-")
                ]
            else:
                mark_rects = [
                    group.find("svg:rect", namespace)
                    for group in dense_root.findall(".//svg:g", namespace)
                    if group.attrib.get("id", "").startswith("LiveMark-")
                ]
            bounds = sorted((float(node.attrib["y"]), float(node.attrib["height"])) for node in mark_rects)
            self.assertEqual(len(bounds), 12)
            clip_bottom = 600 if component == "ranked" else 560
            self.assertTrue(all(y >= 208 and y + height <= clip_bottom for y, height in bounds))
            self.assertTrue(all(y + height <= next_y for (y, height), (next_y, _) in zip(bounds, bounds[1:])))

    def test_task5_envelope_binds_the_full_static_display_inverse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            scene = slider_scene()
            scene["type"] = "evidence_only"
            for key in ("quantities", "controls", "model", "reporting", "decisionContract", "view"):
                scene.pop(key)
            scene["initialState"] = {"evidence": "closed"}
            scene["printState"] = {"evidence": "closed"}
            scene["fallbackSummary"] = {
                "field": "headline",
                "text": slider_spec()["headline"],
            }
            scene.pop("demo")
            _write_json(root / "scenes/02-capacity.json", scene)
            compiled = builder.compile_manifest(manifest)

        slide = compiled.slides[1]
        self.assertEqual(
            slide.scene["fallback"]["paragraphs"],
            slide.display["staticSummary"]["paragraphs"],
        )
        self.assertEqual(
            slide.scene["fallback"]["baselineAnnotation"],
            slide.display["baselineAnnotation"],
        )
        self.assertEqual(
            slide.scene["fallback"]["thresholdText"],
            slide.display["thresholdText"],
        )
        self.assertEqual(
            slide.scene["fallback"]["axisTickLabels"],
            slide.display["axisTickLabels"],
        )

    def test_live_shell_marks_the_decision_threshold_with_compiler_owned_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_fixture(Path(directory), threshold=32.0)
            html_text = builder.build_deck(manifest)
            live = re.search(r'<div class="live-layer" hidden>(.*?)</div>', html_text, re.S).group(1)
            self.assertIn('y1="348.8"', live)
            self.assertIn('y2="348.8"', live)
            self.assertIn('stroke-dasharray="6 6"', live)
            self.assertIn('>Threshold 32.0 cases/wk</text>', live)
            svg = ET.fromstring(live)
            relationship = svg.find(".//{http://www.w3.org/2000/svg}line[@id='idsvg-2-live-shell-LiveRelationship']")
            self.assertEqual([relationship.get(key) for key in ("x1", "y1", "x2", "y2")], ["130.0", "441.2", "820.0", "230.0"])
            self.assertEqual(relationship.get("clip-path"), "url(#idsvg-2-live-shell-LiveRelationshipClip)")

    def test_live_shell_discloses_when_no_decision_change_is_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root, threshold=40)
            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["model"]["terms"]["automation"]["coefficient"] = 0.2
            _write_json(scene_path, scene)
            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["points"][0]["y"] = 22
            spec["interactive_result"]["value"] = 22
            spec["annotation"] = spec["annotation"].replace(
                "Weekly capacity 26 cases/wk", "Weekly capacity 22 cases/wk"
            )
            _write_json(spec_path, spec)

            html_text = builder.build_deck(manifest)
            live = re.search(r'<div class="live-layer" hidden>(.*?)</div>', html_text, re.S).group(1)
            self.assertIn("No decision change within the tested range", live)
            self.assertIn(
                '<p class="decision-range-note" data-decision-range="constant">'
                'No decision change within the tested range</p>',
                html_text,
            )

    def test_live_shell_renders_every_compiled_dot_plot_point(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["view"]["points"].append({
                "id": "reference-capacity",
                "label": "Reference capacity",
                "x": {"ref": "control:automation"},
                "y": {"ref": "output:capacity"},
            })
            _write_json(scene_path, scene)
            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["points"].append({
                "item_id": "reference-capacity",
                "label": "Reference capacity",
                "x": 20,
                "y": 26,
                "emphasis": False,
            })
            _write_json(spec_path, spec)

            html_text = builder.build_deck(manifest)
            live = re.search(r'<div class="live-layer" hidden>(.*?)</div>', html_text, re.S).group(1)
            self.assertIn('id="idsvg-2-live-shell-service-capacity"', live)
            self.assertIn('id="idsvg-2-live-shell-reference-capacity"', live)
            self.assertIn("Reference capacity", live)
            payload = envelope_from(html_text)
            paragraphs = payload["slides"][1]["display"]["staticSummary"]["paragraphs"]
            self.assertIn("Reference capacity: 20%, 26 cases/wk", paragraphs)

            # Exercise label layout at all plot boundaries without weakening
            # Task 3's truthful authored fallback contract for the real build.
            compiled = builder.compile_manifest(manifest)
            serialized = copy.deepcopy(compiled.slides[1].scene)
            base_point = serialized["initialEvaluation"]["view"]["points"][0]
            edge_points = (
                ("edge-low", "Lower edge capacity " * 12, "0", "0"),
                ("edge-high", "Upper edge capacity " * 12, "80", "50"),
            )
            for point_id, label, x_value, y_value in edge_points:
                point = copy.deepcopy(base_point)
                point["id"] = point_id
                point["label"] = label
                point["highlight"] = False
                point["x"]["value"] = x_value
                point["y"]["value"] = y_value
                point["xText"] = x_value + "%"
                point["yText"] = y_value + " cases/wk"
                serialized["initialEvaluation"]["view"]["points"].append(point)
            raw = builder._live_shell(builder._renderer_copy(spec), serialized, compiled.slides[1].display)
            validated = deck_bundle.validate_renderer_svg(raw, slide_ordinal=2, role="live-shell")
            svg = ET.fromstring(validated.serialized)
            nodes = {node.get("id"): node for node in svg.iter() if node.get("id")}
            self.assertEqual(
                (nodes["idsvg-2-live-shell-edge-low"].get("cx"), nodes["idsvg-2-live-shell-edge-low"].get("cy")),
                ("130.0", "560.0"),
            )
            self.assertEqual(
                (nodes["idsvg-2-live-shell-edge-high"].get("cx"), nodes["idsvg-2-live-shell-edge-high"].get("cy")),
                ("820.0", "230.0"),
            )
            edge_labels = {}
            for text_node in svg.findall(".//{http://www.w3.org/2000/svg}text"):
                title_node = text_node.find("{http://www.w3.org/2000/svg}title")
                if title_node is not None and title_node.text in {point[1] for point in edge_points}:
                    edge_labels[title_node.text] = text_node
            self.assertEqual(set(edge_labels), {point[1] for point in edge_points})
            for label, text_node in edge_labels.items():
                baseline = float(text_node.get("y"))
                self.assertGreaterEqual(baseline - builder.render_slide_spec.T_LABEL, 230)
                self.assertLessEqual(baseline + 4, 560)
                visible = text_node.find("{http://www.w3.org/2000/svg}title").tail
                width = builder.render_slide_spec._text_width(visible) * builder.render_slide_spec.T_LABEL * 0.62
                x_value = float(text_node.get("x"))
                if text_node.get("text-anchor") == "start":
                    self.assertGreaterEqual(x_value, 80)
                    self.assertLessEqual(x_value + width, 830)
                else:
                    self.assertLessEqual(x_value, 830)
                    self.assertGreaterEqual(x_value - width, 80)

    def test_live_shell_maps_maximum_length_point_id_to_bounded_label_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            point_id = "p" * 64
            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["view"]["points"][0]["id"] = point_id
            _write_json(scene_path, scene)
            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["points"][0]["item_id"] = point_id
            _write_json(spec_path, spec)

            html_text = builder.build_deck(manifest)

        self.assertIn(f'id="idsvg-2-live-shell-{point_id}"', html_text)
        label_id = builder._live_svg_id("LivePointLabel", point_id, 1)
        self.assertIn(f'id="idsvg-2-live-shell-{label_id}"', html_text)
        self.assertNotIn("LivePointLabel-" + point_id, html_text)

    def test_two_page_build_has_truthful_layers_display_bridge_and_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_fixture(Path(directory))
            html_text = builder.build_deck(manifest)
            self.assertEqual(html_text.count('<section id="idrt-page-'), 2)
            self.assertEqual(html_text.count('class="fallback-layer"'), 2)
            self.assertEqual(html_text.count('class="live-layer" hidden'), 1)
            # The two overview thumbnails reuse inert static SVG clones, and
            # the prebuilt demo cue is also hidden from assistive technology.
            self.assertEqual(html_text.count('aria-hidden="true"'), 7)
            self.assertEqual(html_text.count('focusable="false"'), 5)
            self.assertIn('cx="385.0" cy="377.0"', html_text)
            self.assertIn("Illustrative service design exercise", html_text)
            self.assertIn("All values are synthetic and intended only for runtime validation.", html_text)
            self.assertIn("ILLUSTRATIVE", html_text)

            # Baseline decision annotation belongs to the complete fallback;
            # the semantic tree exposes the recommendation once as a decision.
            self.assertEqual(
                html_text.count('<p data-decision-recommendation>Increase automation before the pilot</p>'),
                1,
            )
            live = re.search(r'<div class="live-layer" hidden>(.*?)</div>', html_text, re.S).group(1)
            self.assertNotIn("Increase automation before the pilot", live)
            self.assertIn("Weekly capacity", live)
            self.assertIn("0 cases/wk", live)
            self.assertIn("50 cases/wk", live)
            self.assertLess(live.index('id="idsvg-2-live-shell-LiveChartBand"'), live.index("Automation</text>"))

            payload = envelope_from(html_text)
            self.assertEqual(payload["locale"], "en-US")
            display = payload["slides"][1]["display"]
            self.assertEqual(display["thresholdText"], "32 cases/wk")
            self.assertEqual(display["axisTickLabels"], {"x": ["0%", "80%"], "y": ["0 cases/wk", "50 cases/wk"]})
            self.assertEqual(display["staticSummary"]["values"], [{
                "id": "capacity", "label": "Weekly capacity", "text": "26 cases/wk",
            }])
            self.assertEqual(display["staticSummary"]["decision"], {
                "status": "Below demand", "recommendation": "Increase automation before the pilot",
            })

            runtime = deck_bundle.load_runtime_assets()
            allowed = {(2, "method-note"): "https://example.com/method"}
            self.assertEqual(deck_bundle.inspect_self_contained(html_text, assets=runtime, allowed_sources=allowed), ())
            tampered = html_text.replace('data-source-id="method-note"', 'data-source-id="other"', 1)
            self.assertIn("source_link", {issue.code for issue in deck_bundle.inspect_self_contained(tampered, assets=runtime, allowed_sources=allowed)})
            source_anchor = re.search(
                r'<a data-slide-ordinal="2" data-source-id="method-note"[^>]*>[^<]*</a>',
                html_text,
            ).group(0)
            for tampered in (
                html_text.replace(source_anchor, source_anchor + source_anchor, 1),
                html_text.replace(source_anchor, "", 1),
            ):
                with self.subTest(source_registry=True):
                    self.assertIn(
                        "source_link",
                        {issue.code for issue in deck_bundle.inspect_self_contained(
                            tampered, assets=runtime, allowed_sources=allowed,
                        )},
                    )

            fake_div = html_text.replace(
                '<div id="idrt-evidence-dialog-2" class="evidence-dialog evidence-container"',
                '<div id="idrt-evidence-dialog-2" class="evidence-container"',
                1,
            )
            self.assertIn(
                "source_link",
                {issue.code for issue in deck_bundle.inspect_self_contained(
                    fake_div, assets=runtime, allowed_sources=allowed,
                )},
            )

            moved_source = html_text.replace(source_anchor, "", 1).replace(
                "</nav></section>\n</main>",
                f'</nav><details class="evidence-container">{source_anchor}</details></section>\n</main>',
                1,
            )
            self.assertIn(
                "source_link",
                {issue.code for issue in deck_bundle.inspect_self_contained(
                    moved_source, assets=runtime, allowed_sources=allowed,
                )},
            )

    def test_scene_emits_fixed_runtime_controls_status_and_modal_dom(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            html_text = builder.build_deck(make_fixture(Path(directory)))

        # Enhancement is progressive: every runtime target exists before the
        # fixed script executes.  The runtime may only bind/update these nodes.
        expected = (
            'data-runtime="pending"',
            'id="idrt-status-2" class="scene-status" aria-live="polite" aria-atomic="true"',
            'class="control-rail" hidden',
            'id="idrt-control-2-1" type="range"',
            'data-control-id="automation"',
            'data-target-key="control:automation"',
            'id="idrt-reset-2" type="button" data-action="reset"',
            'id="idrt-evidence-open-2" type="button" data-action="evidence"',
            'aria-haspopup="dialog" aria-controls="idrt-evidence-dialog-2" aria-expanded="false"',
            'id="idrt-static-toggle-2" type="button" data-action="static" aria-pressed="false"',
            'id="idrt-evidence-dialog-2" class="evidence-dialog evidence-container" role="dialog"',
            'aria-modal="true" aria-labelledby="idrt-evidence-title-2" hidden',
            'id="idrt-evidence-close-2" type="button" data-action="evidence-close"',
            'data-evidence-tab="sources"',
            'data-evidence-tab="assumptions"',
            'data-evidence-panel="sources"',
            'data-evidence-panel="assumptions"',
            '<strong>Basis:</strong> illustrative',
            '<h3>Input range</h3>',
            'Automation: 0% – 80%; Step 5%',
            '<h3>Print state</h3>',
            'Automation: 20%',
            '<h3>Lineage</h3>',
            '<strong>Weekly capacity:</strong>',
            'data-nav-action="previous"',
            'data-page-index="1"',
            'data-page-index="2"',
            'data-nav-action="next"',
        )
        for token in expected:
            with self.subTest(token=token):
                self.assertIn(token, html_text)
        self.assertEqual(html_text.count('data-control-id="automation"'), 1)
        self.assertLess(
            html_text.index('id="idrt-evidence-dialog-2"'),
            html_text.index('id="idrt-deck-data"'),
        )

    def test_presenter_surfaces_and_labels_are_prebuilt_in_both_languages(self) -> None:
        expected = {
            "en": {
                "controls": ("Overview", "Replay", "Demo", "Full screen", "Help"),
                "titles": ("Slide overview", "Presenter help"),
                "close": "Close",
            },
            "ja": {
                "controls": ("一覧", "リプレイ", "デモ", "全画面", "ヘルプ"),
                "titles": ("スライド一覧", "プレゼンターヘルプ"),
                "close": "閉じる",
            },
        }
        for lang, labels in expected.items():
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as directory:
                html_text = builder.build_deck(make_fixture(Path(directory), lang=lang))
                for action, label in zip(
                    ("overview", "replay", "demo", "fullscreen", "help"),
                    labels["controls"],
                ):
                    self.assertIn(
                        f'data-presenter-action="{action}"',
                        html_text,
                    )
                    self.assertRegex(
                        html_text,
                        rf'data-presenter-action="{action}"[^>]*>{re.escape(label)}</button>',
                    )
                self.assertIn(
                    'id="idrt-presenter-overview" class="presenter-dialog overview-dialog" '
                    'role="dialog" aria-modal="true"',
                    html_text,
                )
                self.assertIn(
                    'id="idrt-presenter-help" class="presenter-dialog help-dialog" '
                    'role="dialog" aria-modal="true"',
                    html_text,
                )
                self.assertIn(
                    'id="idrt-demo-cue" class="demo-cue" aria-hidden="true" inert hidden',
                    html_text,
                )
                for title in labels["titles"]:
                    self.assertIn(f">{title}</h2>", html_text)
                for kind in ("overview", "help"):
                    self.assertRegex(
                        html_text,
                        rf'data-presenter-close="{kind}"[^>]*>{re.escape(labels["close"])}</button>',
                    )
                self.assertEqual(html_text.count('data-overview-slide="1"'), 1)
                self.assertEqual(html_text.count('data-overview-slide="2"'), 1)
                self.assertEqual(html_text.count('class="overview-fallback"'), 2)

    def test_every_compiled_target_maps_to_exactly_one_prebuilt_dom_node(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            html_text = builder.build_deck(make_fixture(Path(directory)))
        payload = envelope_from(html_text)
        scene = payload["slides"][1]["scene"]
        slide_id = payload["slides"][1]["slideId"]
        expected = {(slide_id, key) for key in scene["targets"]}
        actual = re.findall(
            r'<(?:input|select|fieldset|button|a|span)\b[^>]*'
            r'data-target-slide="([^"]+)"[^>]*data-target-key="([^"]+)"[^>]*>',
            html_text,
        )
        self.assertEqual(set(actual), expected)
        self.assertEqual(len(actual), len(expected))
        for pair in expected:
            with self.subTest(pair=pair):
                self.assertEqual(actual.count(pair), 1)

    def test_overview_uses_static_fallbacks_without_duplicate_svg_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            html_text = builder.build_deck(make_fixture(Path(directory)))
        document_ids = re.findall(r'\bid="([^"]+)"', html_text)
        self.assertEqual(len(document_ids), len(set(document_ids)))
        overview = re.search(
            r'<section id="idrt-presenter-overview".*?</section>',
            html_text,
            re.S,
        )
        self.assertIsNotNone(overview)
        self.assertEqual(overview.group(0).count("<svg"), 2)
        self.assertEqual(overview.group(0).count('aria-hidden="true"'), 2)

    def test_range_dom_uses_bounded_integer_indices_and_exact_accessible_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            html_text = builder.build_deck(make_fixture(Path(directory)))

        control = re.search(
            r'<input id="idrt-control-2-1" type="range"[^>]+>',
            html_text,
        ).group(0)
        self.assertIn('min="0"', control)
        self.assertIn('max="16"', control)
        self.assertIn('step="1"', control)
        self.assertIn('value="4"', control)
        self.assertIn('aria-valuetext="20"', control)
        self.assertNotIn('value="20"', control)

    def test_live_scene_pre_renders_one_atomic_baseline_summary_and_action_labels(self) -> None:
        expected_labels = {
            "en": ("View static conclusion", "Return to live view"),
            "ja": ("静的な結論を表示", "動的表示に戻る"),
        }
        for lang, (static_label, live_label) in expected_labels.items():
            with self.subTest(lang=lang), tempfile.TemporaryDirectory() as directory:
                html_text = builder.build_deck(make_fixture(Path(directory), lang=lang))
                scene = re.search(
                    r'<section id="idrt-page-2".*?</section>',
                    html_text,
                    re.S,
                ).group(0)
                self.assertEqual(scene.count('class="scene-summary"'), 1)
                self.assertIn('class="scene-summary"', scene)
                self.assertIn(f'>{static_label}</button>', scene)
                self.assertNotIn(f'>{live_label}</button>', scene)

    def test_display_bridge_preserves_authored_threshold_precision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_fixture(Path(directory), threshold=32.0)
            payload = envelope_from(builder.build_deck(manifest))
            self.assertEqual(payload["slides"][1]["scene"]["decisionContract"]["threshold"]["value"], "32")
            self.assertEqual(payload["slides"][1]["display"]["thresholdText"], "32.0 cases/wk")
            self.assertIn("threshold ≥ 32.0 cases/wk", payload["slides"][1]["display"]["baselineAnnotation"])

    def test_scene_semantics_use_compiled_point_display_text_with_trailing_zero_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["points"][0].update(x=20.0, y=26.0)
            _write_json(spec_path, spec)

            payload = envelope_from(builder.build_deck(manifest))
            paragraphs = payload["slides"][1]["display"]["staticSummary"]["paragraphs"]
            self.assertIn("Weekly capacity: 20%, 26 cases/wk", paragraphs)

    def test_source_scheme_classification_is_case_insensitive_but_policy_is_shared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["sources"][0]["url"] = "HTTPS://example.com/method"
            _write_json(scene_path, scene)
            html_text = builder.build_deck(manifest)
            self.assertIn(
                'href="HTTPS://example.com/method" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"',
                html_text,
            )
            self.assertEqual(deck_bundle.inspect_self_contained(
                html_text,
                assets=deck_bundle.load_runtime_assets(),
                allowed_sources={(2, "method-note"): "HTTPS://example.com/method"},
            ), ())

    def test_build_is_deterministic_and_contains_no_author_paths_or_raw_scene_script(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = make_fixture(Path(directory))
            first = builder.build_deck(manifest)
            second = builder.build_deck(manifest)
            self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))
            self.assertNotIn(directory, first)
            self.assertNotIn('type="application/json"', first)
            self.assertNotIn('"interactionRationale"', first)

    def test_cli_build_is_byte_identical_across_cwd_locale_timezone_and_hash_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as first_cwd, tempfile.TemporaryDirectory() as second_cwd:
            root = Path(directory)
            manifest = make_fixture(root)
            outputs = (root / "one.interactive.html", root / "two.interactive.html")
            environments = (
                {"LC_ALL": "C", "TZ": "UTC", "PYTHONHASHSEED": "1"},
                {"LC_ALL": "ja_JP.UTF-8", "TZ": "Asia/Tokyo", "PYTHONHASHSEED": "777"},
            )
            for output, cwd, changes in zip(outputs, (first_cwd, second_cwd), environments):
                environment = os.environ.copy()
                environment.update(changes)
                result = subprocess.run(
                    [sys.executable, "-I", "-B", str(ROOT / "scripts/build_interactive_deck.py"), "--manifest", str(manifest), "-o", str(output)],
                    cwd=cwd, env=environment, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())

    def test_cli_is_atomic_companion_only_and_runs_from_unrelated_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as cwd:
            root = Path(directory)
            manifest = make_fixture(root)
            output = root / "deck.interactive.html"
            classic_path = root / "deck.html"
            classic_path.write_bytes(b"classic sentinel")
            result = subprocess.run(
                [sys.executable, "-I", "-B", str(ROOT / "scripts/build_interactive_deck.py"), "--manifest", str(manifest), "-o", str(output)],
                cwd=cwd, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))
            self.assertEqual(classic_path.read_bytes(), b"classic sentinel")

            # A failed rebuild preserves the last complete companion artifact.
            sentinel = b"interactive sentinel"
            output.write_bytes(sentinel)
            broken = json.loads(manifest.read_text(encoding="utf-8"))
            broken["slides"][1]["scene"] = "../outside.json"
            _write_json(manifest, broken)
            result = subprocess.run(
                [sys.executable, "-I", "-B", str(ROOT / "scripts/build_interactive_deck.py"), "--manifest", str(manifest), "-o", str(output)],
                cwd=cwd, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(output.read_bytes(), sentinel)

    def test_cli_refuses_a_classic_or_non_companion_output_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            for name in ("deck.html", "preview.html"):
                with self.subTest(name=name):
                    output = root / name
                    output.write_bytes(b"classic sentinel")
                    with redirect_stderr(io.StringIO()):
                        status = builder.main(["--manifest", str(manifest), "-o", str(output)])
                    self.assertEqual(status, 1)
                    self.assertEqual(output.read_bytes(), b"classic sentinel")

    def test_classic_builder_bytes_are_unchanged_and_ignore_scene(self) -> None:
        manifest = json.loads((ROOT / "examples/demo-deck.json").read_text(encoding="utf-8"))
        spec_paths = [ROOT / "examples" / value for value in manifest["slides"]]
        self.assertEqual(
            classic.build_deck(spec_paths, manifest["title"]).encode("utf-8"),
            (ROOT / "examples/demo-deck.html").read_bytes(),
        )

    def test_same_mixed_manifest_builds_classic_then_companion_without_cross_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            classic_output = root / "deck.html"
            companion_output = root / "deck.interactive.html"
            classic_result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "scripts/build_html_deck.py"), "--manifest", str(manifest), "-o", str(classic_output)],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(classic_result.returncode, 0, classic_result.stderr)
            classic_bytes = classic_output.read_bytes()
            interactive_result = subprocess.run(
                [sys.executable, "-I", "-B", str(ROOT / "scripts/build_interactive_deck.py"), "--manifest", str(manifest), "-o", str(companion_output)],
                cwd=root, capture_output=True, text=True,
            )
            self.assertEqual(interactive_result.returncode, 0, interactive_result.stderr)
            self.assertEqual(classic_output.read_bytes(), classic_bytes)
            self.assertNotEqual(companion_output.read_bytes(), classic_bytes)
            self.assertNotIn(b"interactionRationale", classic_bytes)


if __name__ == "__main__":
    unittest.main()
