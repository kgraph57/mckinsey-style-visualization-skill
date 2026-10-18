from __future__ import annotations

import base64
import copy
from dataclasses import replace
import hashlib
import html.parser
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

from scripts import render_slide_spec

from scripts import deck_bundle as bundle


SAFE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720" role="img" aria-label="Safe">
  <rect width="1280" height="720" fill="#FFFFFF"/>
  <text x="80.0" y="96.0" font-family="Georgia, 'Times New Roman', 'Hiragino Mincho ProN', 'Yu Mincho', serif" font-size="40" fill="#000000" font-weight="bold" text-anchor="start">A safe claim</text>
</svg>
"""

LIVE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <defs><clipPath id="chart-clip"><rect x="80" y="208" width="1120" height="352" fill="#FFFFFF"/></clipPath></defs>
  <g id="geometry" clip-path="url(#chart-clip)"><circle id="point" cx="385" cy="377" r="9" fill="#15296B"/></g>
</svg>
"""


class _Capture(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.scripts: list[str] = []
        self.styles: list[str] = []
        self.deck_data: list[str] = []
        self.titles: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag.lower())

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag.lower():
            self.stack.pop()

    def handle_data(self, data):
        if not self.stack:
            return
        if self.stack[-1] == "script":
            self.scripts.append(data)
        elif self.stack[-1] == "style":
            self.styles.append(data)
        elif self.stack[-1] == "title":
            self.titles.append(data)
        elif self.stack[-1] == "div" and data.strip() and all(ch.isalnum() or ch in "-_" for ch in data.strip()):
            self.deck_data.append(data.strip())


class _ElementCounter(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1

    def handle_startendtag(self, tag, attrs):
        self.count += 1


def assets() -> bundle.RuntimeAssets:
    return bundle.RuntimeAssets(
        css=b":root { color-scheme: light; }\n.slide { display: block; }\n",
        js=b'(function () { "use strict"; document.documentElement.setAttribute("data-interactive-runtime", "static-bootstrap"); }());\n',
    )


def summary(headline: str = "A safe claim") -> dict:
    return {
        "headline": headline,
        "source": "Illustrative source",
        "paragraphs": ["Static conclusion"],
        "values": [],
        "decision": None,
    }


def static_slide(headline: str = "A safe claim") -> bundle.BundleSlide:
    return bundle.BundleSlide(
        slide_id="slide-001",
        headline=headline,
        source="Illustrative source",
        fallback_svg=bundle.validate_renderer_svg(SAFE_SVG, slide_ordinal=1, role="fallback"),
        static_summary=summary(headline),
        scene=None,
        live_shell_svg=None,
        display=None,
    )


def compiled_slider_payload() -> dict:
    """Return the exact public Task 3 fixture consumed by the bundle boundary."""
    from scripts import build_interactive_deck
    from tests.test_build_interactive_deck import make_fixture

    with tempfile.TemporaryDirectory() as directory:
        compiled = build_interactive_deck.compile_manifest(make_fixture(Path(directory)))
        slide = compiled.slides[1]
        return {
            "version": 1,
            "kind": "interactive-deck",
            "lang": "en",
            "locale": "en-US",
            "slides": [{
                "slideId": slide.slide_id,
                "scene": json.loads(json.dumps(slide.scene)),
                "display": json.loads(json.dumps(slide.display)),
            }],
        }


class EnvelopeTests(unittest.TestCase):
    def test_disclosure_evidence_accepts_compiler_owned_empty_badge(self) -> None:
        evidence = {
            "sources": [{
                "id": "method",
                "label": "Method note",
                "detail": "Compiled evidence-only source",
                "linked": False,
            }],
            "assumptions": [],
            "leaves": [],
            "badge": "",
            "formulas": [],
            "triggerLabel": "Open evidence",
        }

        bundle._validate_evidence(evidence, "scene/evidence")

    def test_panel_validator_matches_compiler_required_and_open_initial_states(self) -> None:
        from scripts import interactive_scene
        from tests.test_interactive_scene import compile_fixture, fixture

        panels = [
            {"id": "one", "label": "L" * 64, "heading": "One", "body": "One body"},
            {"id": "two", "label": "Two", "heading": "Two", "body": "Two body"},
        ]

        def compiled(kind: str) -> dict:
            raw = {key: value for key, value in fixture().items() if key in interactive_scene.COMMON}
            raw.update(
                type=kind,
                initialState={"panel": "one"},
                printState={"panel": "one"},
                fallbackSummary={"field": "headline", "text": "Proof"},
            )
            if kind == "accordion":
                raw.update(items=copy.deepcopy(panels), allowNone=False)
            else:
                raw.update(
                    panels=copy.deepcopy(panels),
                    parentSummary="Parent",
                    returnLabel="Back",
                )
            result = compile_fixture(
                raw,
                {"pattern": "bullet_list", "headline": "Proof", "bullets": [{"text": "Summary"}]},
            )
            scene = interactive_scene.serialize_compiled_scene(result.compiled)
            scene["fallback"].update(
                paragraphs=["Summary"],
                baselineAnnotation="",
                thresholdText=None,
                axisTickLabels=None,
            )
            return scene

        for kind in ("drilldown", "accordion"):
            scene = compiled(kind)
            with self.subTest(kind=kind, valid=True):
                bundle._validate_panel_scene(scene, "capacity", "en", "scene")
            if kind == "accordion":
                forged = copy.deepcopy(scene)
                forged["initialState"]["panel"] = None
                forged["printState"]["panel"] = None
                with self.subTest(kind=kind, valid=False), self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle._validate_panel_scene(forged, "capacity", "en", "scene")
                self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_compiled_panel_demo_reachability_tracks_the_visible_close_target(self) -> None:
        from scripts import interactive_scene
        from tests.test_interactive_scene import compile_fixture, fixture

        def compiled(kind: str, *, initial: str | None, allow_none: bool) -> dict:
            panels = [
                {"id": name, "label": name.title(), "heading": name.title(), "body": name + " body"}
                for name in ("one", "two")
            ]
            raw = {key: value for key, value in fixture().items() if key in interactive_scene.COMMON}
            raw.update(
                type=kind,
                initialState={"panel": initial},
                printState={"panel": initial},
                fallbackSummary={"field": "headline", "text": "Proof"},
            )
            if kind == "accordion":
                raw.update(items=panels, allowNone=allow_none)
            else:
                raw.update(panels=panels, parentSummary="Parent", returnLabel="Back")
            result = compile_fixture(
                raw,
                {"pattern": "bullet_list", "headline": "Proof", "bullets": [{"text": "Summary"}]},
            )
            scene = interactive_scene.serialize_compiled_scene(result.compiled)
            scene["fallback"].update(
                paragraphs=["Summary"],
                baselineAnnotation="",
                thresholdText=None,
                axisTickLabels=None,
            )
            return scene

        valid = compiled("drilldown", initial="one", allow_none=True)
        valid["steps"] = [
            {"stepKey": "close-one", "action": {"type": "closePanel", "panel": "one"}, "targetKey": "panel:one:close"},
            {"stepKey": "open-two", "action": {"type": "openPanel", "panel": "two"}, "targetKey": "panel:two"},
            {"stepKey": "close-two", "action": {"type": "closePanel", "panel": "two"}, "targetKey": "panel:two:close"},
        ]
        bundle._validate_panel_scene(valid, "capacity", "en", "scene")
        visible_drilldown_switch = compiled("drilldown", initial=None, allow_none=True)
        visible_drilldown_switch["steps"] = [
            {"stepKey": "open-one", "action": {"type": "openPanel", "panel": "one"}, "targetKey": "panel:one"},
            {"stepKey": "open-two", "action": {"type": "openPanel", "panel": "two"}, "targetKey": "panel:two"},
            {"stepKey": "close-two", "action": {"type": "closePanel", "panel": "two"}, "targetKey": "panel:two:close"},
        ]
        bundle._validate_panel_scene(visible_drilldown_switch, "capacity", "en", "scene")

        hidden_close = compiled("drilldown", initial="one", allow_none=True)
        hidden_close["steps"] = [
            {"stepKey": "close-hidden", "action": {"type": "closePanel", "panel": "two"}, "targetKey": "panel:two:close"},
        ]
        inert_close = compiled("drilldown", initial="one", allow_none=True)
        inert_close["steps"] = [
            {"stepKey": "show", "action": {"type": "openEvidence"}, "targetKey": "evidence:open"},
            {"stepKey": "close-inert", "action": {"type": "closePanel", "panel": "one"}, "targetKey": "panel:one:close"},
        ]
        required_close = compiled("accordion", initial="one", allow_none=False)
        required_close["steps"] = [
            {"stepKey": "close-required", "action": {"type": "closePanel", "panel": "one"}, "targetKey": "panel:one:close"},
        ]
        for scene in (hidden_close, inert_close, required_close):
            with self.subTest(type=scene["type"], steps=scene["steps"]):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle._validate_panel_scene(scene, "capacity", "en", "scene")
                self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_compiled_demo_reachability_rejects_inert_evidence_and_post_goto_actions(self) -> None:
        valid_sequences = [
            [
                {"stepKey": "show", "action": {"type": "openEvidence"}, "targetKey": "evidence:open"},
                {"stepKey": "hide", "action": {"type": "closeEvidence"}, "targetKey": "evidence:close"},
                {"stepKey": "change", "action": {"type": "set", "control": "automation", "value": "35"}, "targetKey": "control:automation"},
            ],
            [{"stepKey": "next", "action": {"type": "goto", "slideId": "queue-capacity"}}],
        ]
        for steps in valid_sequences:
            payload = compiled_slider_payload()
            payload["slides"][0]["scene"]["steps"] = steps
            with self.subTest(valid=steps):
                bundle.encode_envelope(payload)

        invalid_sequences = [
            [
                {"stepKey": "next", "action": {"type": "goto", "slideId": "queue-capacity"}},
                {"stepKey": "change", "action": {"type": "set", "control": "automation", "value": "35"}, "targetKey": "control:automation"},
            ],
            [
                {"stepKey": "show", "action": {"type": "openEvidence"}, "targetKey": "evidence:open"},
                {"stepKey": "change", "action": {"type": "set", "control": "automation", "value": "35"}, "targetKey": "control:automation"},
            ],
            [
                {"stepKey": "show", "action": {"type": "openEvidence"}, "targetKey": "evidence:open"},
                {"stepKey": "show-again", "action": {"type": "openEvidence"}, "targetKey": "evidence:open"},
            ],
            [{"stepKey": "hide", "action": {"type": "closeEvidence"}, "targetKey": "evidence:close"}],
        ]
        for steps in invalid_sequences:
            payload = compiled_slider_payload()
            payload["slides"][0]["scene"]["steps"] = steps
            with self.subTest(invalid=steps):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_compiled_evidence_demo_reachability_starts_from_the_declared_initial_overlay(self) -> None:
        from scripts import interactive_scene
        from tests.test_interactive_scene import compile_fixture, fixture

        raw = {key: value for key, value in fixture().items() if key in interactive_scene.COMMON or key == "assumptions"}
        raw.update(
            type="evidence_only",
            initialState={"evidence": "sources"},
            printState={"evidence": "sources"},
            fallbackSummary={"field": "headline", "text": "Proof"},
            sources=[{"id": "safe", "label": "Safe", "detail": "Source", "url": "https://example.com/data"}],
        )
        result = compile_fixture(
            raw,
            {"pattern": "bullet_list", "headline": "Proof", "bullets": [{"text": "Evidence is available"}]},
        )
        scene = interactive_scene.serialize_compiled_scene(result.compiled)
        scene["fallback"].update(
            paragraphs=["Evidence is available"],
            baselineAnnotation="",
            thresholdText=None,
            axisTickLabels=None,
        )

        close_initial = copy.deepcopy(scene)
        close_initial["steps"] = [
            {"stepKey": "hide-initial", "action": {"type": "closeEvidence"}, "targetKey": "evidence:close"},
        ]
        bundle._validate_disclosure_scene(close_initial, "capacity", "en", "scene")

        double_open = copy.deepcopy(scene)
        double_open["steps"] = [
            {"stepKey": "double-open", "action": {"type": "openEvidence"}, "targetKey": "evidence:open"},
        ]
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle._validate_disclosure_scene(double_open, "capacity", "en", "scene")
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_compiled_state_cost_counts_disclosures_and_all_control_domains(self) -> None:
        lineage = {
            "derived": False,
            "badge": "illustrative",
            "bases": ["illustrative"],
            "sourceRefs": [],
            "assumptionRefs": ["synthetic"],
            "normalizations": [],
            "leaves": ["control:scale"],
            "steps": [],
        }
        controls = [
            {
                "id": "scale", "kind": "range", "label": "Scale",
                "min": "0", "max": "2", "step": "1", "quantity": "value",
                "lineage": lineage,
            },
            {
                "id": "channel", "kind": "segmented", "label": "Channel",
                "options": [{"value": "narrow", "label": "Narrow"}, {"value": "wide", "label": "Wide"}],
            },
            {
                "id": "sponsor", "kind": "toggle", "label": "Sponsor",
                "options": [{"value": "off", "label": "Off"}, {"value": "on", "label": "On"}],
            },
            {
                "id": "scope", "kind": "select", "label": "Scope",
                "options": [
                    {"value": "small", "label": "Small"},
                    {"value": "medium", "label": "Medium"},
                    {"value": "large", "label": "Large"},
                ],
            },
        ]
        accepted_states = 36
        numeric = {
            "type": "score_model",
            "controls": controls,
            "narration": {
                "program": {"controls": [{"id": control["id"]} for control in controls]},
                "validatedVariants": accepted_states * 2 * (1 + len(controls)),
            },
        }
        cases = {
            "all_control_kinds": (numeric, accepted_states),
            "evidence_sources": ({"type": "evidence_only", "evidence": {"sources": [{}], "assumptions": []}}, 2),
            "evidence_assumptions": ({"type": "evidence_only", "evidence": {"sources": [], "assumptions": [{}]}}, 2),
            "evidence_both": ({"type": "evidence_only", "evidence": {"sources": [{}], "assumptions": [{}]}}, 4),
            "drilldown": ({"type": "drilldown", "states": {"panels": [{}, {}]}}, 3),
            "accordion_none": ({"type": "accordion", "states": {"panels": [{}, {}], "allowNone": True}}, 3),
            "accordion_required": ({"type": "accordion", "states": {"panels": [{}, {}], "allowNone": False}}, 2),
        }
        for label, (scene, expected) in cases.items():
            with self.subTest(label=label):
                self.assertEqual(bundle._compiled_scene_state_count(scene, "scene"), expected)

        forged = copy.deepcopy(numeric)
        forged["narration"]["validatedVariants"] -= 1
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle._compiled_scene_state_count(forged, "scene")
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_state_delta_narration_accepts_the_closed_dot_baseline_shape(self) -> None:
        from scripts.interactive_contract import NARRATION_TEXT

        program = {
            "kind": "state_delta_v1",
            "controls": [{
                "id": "scenario",
                "kind": "segmented",
                "label": "Scenario",
                "baseline": "base",
                "options": [
                    {"value": "base", "label": "Base"},
                    {"value": "shift", "label": "Shift"},
                ],
            }],
            "baselineView": [{
                "id": "point",
                "highlight": True,
                "removed": False,
                "x": "1",
                "y": "2",
            }],
        }
        narration = {
            "locale": "en",
            "templates": copy.deepcopy(NARRATION_TEXT["en"]),
            "templatesByLocale": copy.deepcopy(NARRATION_TEXT),
            "messages": {},
            "messagesByLocale": {"en": {}, "ja": {}},
            "program": program,
            "validatedVariants": 2,
            "comparison": "initialState",
            "maxScalars": 160,
        }
        bundle._validate_task5_narration(narration, "scene/narration", "en")

        forged = copy.deepcopy(narration)
        forged["program"]["baselineView"][0]["rank"] = 1
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle._validate_task5_narration(forged, "scene/narration", "en")
        self.assertEqual(caught.exception.issues[0].code, "scene_shape")

        source = bundle.load_runtime_assets().js.decode("utf-8")
        validator = source[
            source.index("    function validateTask5Narration(") : source.index(
                "    function validateTask5TargetsAndSteps("
            )
        ]
        self.assertIn('["id", "highlight", "removed", "x", "y"]', validator)

    def test_task5_static_summary_inverse_covers_every_scene_model_and_view(self) -> None:
        invariants = {"headline": "Executive claim", "source": "Illustrative source"}
        empty_summary = {
            "headline": "Executive claim", "source": "Illustrative source",
            "paragraphs": [], "values": [], "decision": None,
        }
        base_display = {
            "staticSummary": empty_summary,
            "baselineAnnotation": "",
            "thresholdText": None,
            "axisTickLabels": None,
        }

        def state_scene(component: str) -> dict:
            return {
                "type": "state_toggle", "invariants": invariants,
                "fallback": {"paragraphs": [], "baselineAnnotation": ""},
                "initialEvaluation": {"outputs": {}, "view": {"component": component}},
            }

        def numeric_scene(scene_type: str, model: str, component: str) -> tuple[dict, dict, dict]:
            scene = {
                "type": scene_type,
                "model": {"kind": model},
                "invariants": invariants,
                "fallback": {"paragraphs": [], "baselineAnnotation": ""},
                "quantities": {"value": {"display": "units"}},
                "reporting": {"primaryOutput": "result", "secondaryOutputs": []},
                "outputDefinitions": {
                    "result": {"kind": "numeric", "label": "Result", "quantity": "value", "round": 0},
                },
                "initialEvaluation": {
                    "outputs": {"result": {"value": "8"}},
                    "view": {"component": component},
                    "decision": {"status": "Proceed", "recommendation": "Run"},
                },
            }
            summary = copy.deepcopy(empty_summary)
            summary["values"] = [{"id": "result", "label": "Result", "text": "8 units"}]
            summary["decision"] = {"status": "Proceed", "recommendation": "Run"}
            display = copy.deepcopy(base_display)
            display["staticSummary"] = summary
            display["thresholdText"] = "8 units"
            if component == "dot_plot":
                display["axisTickLabels"] = {"x": ["0", "1"], "y": ["0", "8"]}
            return scene, summary, display

        score, score_summary, score_display = numeric_scene(
            "score_model", "score_sum", "recommendation_panel"
        )
        score["quantities"]["points"] = {"display": "points"}
        score["outputDefinitions"]["result"] = {
            "kind": "numeric", "label": "Score", "quantity": "points", "round": 0,
        }
        score["outputDefinitions"]["classification"] = {"kind": "text", "label": "Classification"}
        score["initialEvaluation"]["outputs"] = {
            "result": {"value": "5"}, "classification": {"value": "Ready"},
        }
        score_summary["values"] = [
            {"id": "result", "label": "Score", "text": "5 points"},
            {"id": "classification", "label": "Classification", "text": "Ready"},
        ]
        score_display["staticSummary"] = score_summary

        cases: dict[str, tuple[dict, dict, dict]] = {}
        for scene_type in ("evidence_only", "drilldown", "accordion"):
            scene = {
                "type": scene_type,
                "invariants": invariants,
                "fallback": {"paragraphs": [], "baselineAnnotation": ""},
            }
            cases[scene_type] = (scene, copy.deepcopy(empty_summary), copy.deepcopy(base_display))
        for component in ("bar_compare", "ranked_list", "dot_plot"):
            summary = copy.deepcopy(empty_summary)
            display = copy.deepcopy(base_display)
            display["staticSummary"] = summary
            if component == "dot_plot":
                display["axisTickLabels"] = {"x": ["0", "1"], "y": ["0", "1"]}
            cases["state_map_" + component] = (state_scene(component), summary, display)
        for model, component in (
            ("linear", "bar_compare"),
            ("lookup", "bar_compare"),
            ("piecewise", "dot_plot"),
            ("operation_graph", "dot_plot"),
        ):
            cases[model + "_" + component] = numeric_scene("slider_model", model, component)
        cases["score_sum_recommendation_panel"] = (score, score_summary, score_display)

        for label, (scene, summary, display) in cases.items():
            scene["fallback"].update({
                "thresholdText": copy.deepcopy(display["thresholdText"]),
                "axisTickLabels": copy.deepcopy(display["axisTickLabels"]),
            })
            with self.subTest(label=label, valid=True):
                bundle._validate_scene_summary(scene, summary, display, "scene/display/staticSummary")
            forged_display = copy.deepcopy(display)
            component = scene.get("initialEvaluation", {}).get("view", {}).get("component")
            if component == "dot_plot":
                forged_display["axisTickLabels"] = None
            elif scene["type"] in ("slider_model", "score_model"):
                forged_display["thresholdText"] = None
            else:
                forged_display["thresholdText"] = "forged"
            with self.subTest(label=label, valid=False), self.assertRaises(bundle.BundleValidationError) as caught:
                bundle._validate_scene_summary(scene, summary, forged_display, "scene/display/staticSummary")
            self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

            forged_summary = copy.deepcopy(summary)
            forged_summary["paragraphs"] = ["FORGED STATIC CLAIM"]
            with self.subTest(label=label, forged="paragraphs"), self.assertRaises(bundle.BundleValidationError) as caught:
                bundle._validate_scene_summary(scene, forged_summary, display, "scene/display/staticSummary")
            self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

            forged_display = copy.deepcopy(display)
            forged_display["baselineAnnotation"] = "FORGED BASELINE"
            with self.subTest(label=label, forged="annotation"), self.assertRaises(bundle.BundleValidationError) as caught:
                bundle._validate_scene_summary(scene, summary, forged_display, "scene/display/staticSummary")
            self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

            if display["thresholdText"] is not None:
                forged_display = copy.deepcopy(display)
                forged_display["thresholdText"] = "FORGED THRESHOLD"
                with self.subTest(label=label, forged="threshold_content"), self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle._validate_scene_summary(scene, summary, forged_display, "scene/display/staticSummary")
                self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

            if display["axisTickLabels"] is not None:
                forged_display = copy.deepcopy(display)
                forged_display["axisTickLabels"]["y"][1] = "FORGED TICK"
                with self.subTest(label=label, forged="tick_content"), self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle._validate_scene_summary(scene, summary, forged_display, "scene/display/staticSummary")
                self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

    def test_analytical_decimal_text_is_canonical(self) -> None:
        for value in ("0", "32", "-0.1", "0.000001", "1000000000000"):
            with self.subTest(value=value, accepted=True):
                self.assertEqual(bundle._decimal_text(value, "scene/value"), value)

        for value in ("-0", "-0.0", "-0.000000", "32.0", "1.230", "01", "+1"):
            with self.subTest(value=value, accepted=False):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle._decimal_text(value, "scene/value")
                self.assertEqual(caught.exception.issues[0].code, "scene_shape")

    def test_canonical_envelope_round_trips_hostile_unicode_as_inert_data(self) -> None:
        hostile = '</script><script>globalThis.pwned=1</script> " <>& \u2028\u2029 日本語 🧪'
        payload = compiled_slider_payload()
        payload["slides"][0]["scene"]["invariants"]["headline"] = hostile
        payload["slides"][0]["display"]["staticSummary"]["headline"] = hostile
        encoded = bundle.encode_envelope(payload)
        self.assertRegex(encoded, r"^[A-Za-z0-9_-]+$")
        self.assertNotIn("=", encoded)
        self.assertEqual(bundle.decode_envelope(encoded), payload)
        self.assertEqual(bundle.encode_envelope(payload), encoded)

    def test_decoder_rejects_noncanonical_duplicate_or_invalid_data(self) -> None:
        valid = bundle.encode_envelope({
            "version": 1, "kind": "interactive-deck", "lang": "en", "locale": "en-US",
            "slides": [{"slideId": "slide-001", "scene": None, "display": None}],
        })
        for encoded in (valid + "=", valid + "!", "A", "____"):
            with self.subTest(encoded=encoded), self.assertRaises(bundle.BundleValidationError):
                bundle.decode_envelope(encoded)
        duplicate = b'{"kind":"interactive-deck","kind":"other","lang":"en","locale":"en-US","slides":[],"version":1}'
        encoded = base64.urlsafe_b64encode(duplicate).decode("ascii").rstrip("=")
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.decode_envelope(encoded)
        self.assertEqual(caught.exception.issues[0].code, "duplicate_json_key")

        long_key = "x" * 5_000
        duplicate = ('{"' + long_key + '":1,"' + long_key + '":2}').encode("utf-8")
        encoded = base64.urlsafe_b64encode(duplicate).decode("ascii").rstrip("=")
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.decode_envelope(encoded)
        self.assertEqual(caught.exception.issues[0].code, "duplicate_json_key")
        self.assertLess(len(str(caught.exception)), 512)

    def test_decoder_validates_once_without_public_reencoding(self) -> None:
        payload = {
            "version": 1,
            "kind": "interactive-deck",
            "lang": "en",
            "locale": "en-US",
            "slides": [{"slideId": "slide-001", "scene": None, "display": None}],
        }
        encoded = bundle.encode_envelope(payload)
        with (
            mock.patch.object(
                bundle,
                "_validate_envelope",
                wraps=bundle._validate_envelope,
            ) as validate,
            mock.patch.object(
                bundle,
                "encode_envelope",
                side_effect=AssertionError("public re-encode reached"),
            ),
        ):
            self.assertEqual(bundle.decode_envelope(encoded), payload)
        self.assertEqual(validate.call_count, 1)

        noncanonical_raw = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
        noncanonical = base64.urlsafe_b64encode(noncanonical_raw).decode("ascii").rstrip("=")
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.decode_envelope(noncanonical)
        self.assertEqual(caught.exception.issues[0].code, "envelope_encoding")

    def test_envelope_budget_rejects_before_full_tree_materialization(self) -> None:
        raw = b'{"junk":[0,0,0,0,0,0]}'
        encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        with (
            mock.patch.object(bundle, "MAX_JSON_NODES", 5),
            mock.patch.object(bundle.json, "loads", side_effect=AssertionError("full decode reached")),
        ):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.decode_envelope(encoded)
        self.assertEqual(caught.exception.issues[0].code, "json_nodes")

    def test_envelope_and_json_budgets_are_inclusive_with_predecode_rejection(self) -> None:
        payload = {
            "version": 1,
            "kind": "interactive-deck",
            "lang": "en",
            "locale": "en-US",
            "slides": [{"slideId": "slide-001", "scene": None, "display": None}],
        }
        raw = bundle._canonical_json(payload)
        with mock.patch.object(bundle, "MAX_ENVELOPE_BYTES", len(raw)):
            encoded = bundle.encode_envelope(payload)
            self.assertEqual(bundle.decode_envelope(encoded), payload)
        with mock.patch.object(bundle, "MAX_ENVELOPE_BYTES", len(raw) - 1):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "envelope_limit")

        decoded_limit = 6
        too_long = "A" * (math.ceil(4 * decoded_limit / 3) + 1)
        with (
            mock.patch.object(bundle, "MAX_ENVELOPE_BYTES", decoded_limit),
            mock.patch.object(
                bundle.base64,
                "urlsafe_b64decode",
                side_effect=AssertionError("decoder reached"),
            ),
        ):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.decode_envelope(too_long)
        self.assertEqual(caught.exception.issues[0].code, "envelope_encoding")
        with (
            mock.patch.object(bundle, "MAX_ENVELOPE_BYTES", decoded_limit),
            mock.patch.object(bundle.re, "fullmatch", side_effect=AssertionError("alphabet scan reached")),
        ):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.decode_envelope(too_long)
        self.assertEqual(caught.exception.issues[0].code, "envelope_encoding")

        scalar = '{"a":"é"}'
        for constant, exact, code in (
            ("MAX_JSON_NODES", 3, "json_nodes"),
            ("MAX_JSON_STRINGS", 2, "json_strings"),
            ("MAX_JSON_STRING_BYTES", 3, "json_string_bytes"),
        ):
            with self.subTest(constant=constant, boundary="exact"):
                with mock.patch.object(bundle, constant, exact):
                    bundle._EnvelopeJsonPreflight(scalar).run()
            with self.subTest(constant=constant, boundary="one-over"):
                with mock.patch.object(bundle, constant, exact - 1):
                    with self.assertRaises(bundle.BundleValidationError) as caught:
                        bundle._EnvelopeJsonPreflight(scalar).run()
                self.assertEqual(caught.exception.issues[0].code, code)

        nested = '{"a":{"b":0}}'
        with mock.patch.object(bundle, "MAX_JSON_DEPTH", 2):
            bundle._EnvelopeJsonPreflight(nested).run()
        with mock.patch.object(bundle, "MAX_JSON_DEPTH", 1):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle._EnvelopeJsonPreflight(nested).run()
        self.assertEqual(caught.exception.issues[0].code, "json_depth")

    def test_aggregate_scene_budgets_are_enforced_by_the_envelope_boundary(self) -> None:
        payload = compiled_slider_payload()
        scene = payload["slides"][0]["scene"]
        for constant, limit in (("MAX_VIEW_ITEMS", 0), ("MAX_TARGETS", 1), ("MAX_STEPS", 0)):
            with self.subTest(constant=constant), mock.patch.object(bundle, constant, limit):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, "aggregate_limit")

        non_json = json.loads(json.dumps(payload))
        non_json["slides"][0]["scene"]["purpose"] = ("tuple", "is", "not", "json")
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(non_json)
        self.assertEqual(caught.exception.issues[0].code, "json_type")

        noncanonical_number = json.loads(json.dumps(payload))
        noncanonical_number["slides"][0]["scene"]["scale"] = 1.0
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(noncanonical_number)
        self.assertEqual(caught.exception.issues[0].code, "json_number")

        unsafe_registry = json.loads(json.dumps(payload))
        unsafe_registry["slides"][0]["scene"]["targets"]["constructor"] = {"kind": "static"}
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(unsafe_registry)
        self.assertEqual(caught.exception.issues[0].code, "identifier")

        surrogate_key = json.loads(json.dumps(payload))
        surrogate_key["slides"][0]["scene"]["targets"]["\ud800"] = {"kind": "static"}
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(surrogate_key)
        self.assertEqual(caught.exception.issues[0].code, "json_unicode")

        for mutation in (
            lambda candidate: candidate.update({"lang": []}),
            lambda candidate: candidate["slides"][0]["scene"]["model"].update({"output": []}),
        ):
            malformed_type = json.loads(json.dumps(payload))
            mutation(malformed_type)
            with self.subTest(mutation=mutation), self.assertRaises(bundle.BundleValidationError):
                bundle.encode_envelope(malformed_type)

        nested_unknown = json.loads(json.dumps(payload))
        nested_unknown["slides"][0]["scene"]["view"]["points"][0]["unexpected"] = True
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(nested_unknown)
        self.assertEqual(caught.exception.issues[0].code, "scene_shape")

        duplicate_point = json.loads(json.dumps(payload))
        duplicate_point["slides"][0]["scene"]["view"]["points"].append(
            json.loads(json.dumps(scene["view"]["points"][0]))
        )
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(duplicate_point)
        self.assertEqual(caught.exception.issues[0].code, "duplicate_id")

        duplicate_paths = (
            ("evidence", "sources"),
            ("evidence", "assumptions"),
            ("evidence", "leaves"),
            ("narration", "program", "controls"),
            ("narration", "program", "outputs"),
            ("narration", "program", "transitions"),
            ("model", "terms"),
        )
        for path in duplicate_paths:
            duplicate_registry = json.loads(json.dumps(payload))
            values = duplicate_registry["slides"][0]["scene"]
            for key in path:
                values = values[key]
            values.append(json.loads(json.dumps(values[0])))
            with self.subTest(path=path):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(duplicate_registry)
                self.assertEqual(caught.exception.issues[0].code, "duplicate_id")

        divergent_evaluation = json.loads(json.dumps(payload))
        divergent_evaluation["slides"][0]["scene"]["initialEvaluation"]["view"]["points"][0]["id"] = "other-point"
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(divergent_evaluation)
        self.assertEqual(caught.exception.issues[0].code, "scene_shape")

        missing_output = json.loads(json.dumps(payload))
        missing_output["slides"][0]["scene"]["initialEvaluation"]["outputs"].pop("capacity")
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(missing_output)
        self.assertEqual(caught.exception.issues[0].code, "scene_shape")

        duplicated_view = json.loads(json.dumps(payload))
        with mock.patch.object(bundle, "MAX_VIEW_ITEMS", 1):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(duplicated_view)
        self.assertEqual(caught.exception.issues[0].code, "aggregate_limit")

        wait_scene = json.loads(json.dumps(payload))
        wait_scene["slides"][0]["scene"]["steps"] = [{
            "stepKey": "pause",
            "action": {"type": "wait", "ms": 1},
        }]
        with mock.patch.object(bundle, "MAX_DECK_WAIT_MS", 0):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(wait_scene)
        self.assertEqual(caught.exception.issues[0].code, "aggregate_limit")

        scene_wait_over = json.loads(json.dumps(payload))
        scene_wait_over["slides"][0]["scene"]["steps"] = [
            {"stepKey": f"pause-{index}", "action": {"type": "wait", "ms": 5_000}}
            for index in range(7)
        ]
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(scene_wait_over)
        self.assertEqual(caught.exception.issues[0].code, "aggregate_limit")

        goto = json.loads(json.dumps(payload))
        goto["slides"][0]["scene"]["steps"] = [{
            "stepKey": "return-to-capacity",
            "action": {"type": "goto", "slideId": "queue-capacity"},
        }]
        self.assertEqual(bundle.decode_envelope(bundle.encode_envelope(goto)), goto)
        goto["slides"][0]["scene"]["steps"][0]["action"]["slideId"] = "missing-slide"
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(goto)
        self.assertEqual(caught.exception.issues[0].code, "scene_shape")

        missing_target = json.loads(json.dumps(payload))
        missing_target["slides"][0]["scene"]["steps"][0].pop("targetKey")
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(missing_target)
        self.assertEqual(caught.exception.issues[0].code, "scene_shape")

        invented_target = json.loads(json.dumps(payload))
        invented_target["slides"][0]["scene"]["steps"] = [{
            "stepKey": "pause-with-cue",
            "action": {"type": "wait", "ms": 1},
            "targetKey": "evidence:open",
        }]
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(invented_target)
        self.assertEqual(caught.exception.issues[0].code, "scene_shape")

        repeated_step = json.loads(json.dumps(payload))
        second = json.loads(json.dumps(repeated_step["slides"][0]))
        second["slideId"] = "queue-capacity-copy"
        second["scene"]["slideId"] = "queue-capacity-copy"
        repeated_step["slides"].append(second)
        self.assertEqual(
            bundle.decode_envelope(bundle.encode_envelope(repeated_step)),
            repeated_step,
        )

        duplicate_step = json.loads(json.dumps(payload))
        duplicate_step["slides"][0]["scene"]["steps"].append(
            json.loads(json.dumps(duplicate_step["slides"][0]["scene"]["steps"][0]))
        )
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(duplicate_step)
        self.assertEqual(caught.exception.issues[0].code, "duplicate_id")

    def test_deck_accepted_state_budget_is_exact_at_the_envelope_boundary(self) -> None:
        payload = compiled_slider_payload()
        second = copy.deepcopy(payload["slides"][0])
        second["slideId"] = "queue-capacity-copy"
        second["scene"]["slideId"] = "queue-capacity-copy"
        payload["slides"].append(second)

        with mock.patch.object(bundle, "MAX_ACCEPTED_STATES_PER_DECK", 34):
            bundle.encode_envelope(payload)
        with mock.patch.object(bundle, "MAX_ACCEPTED_STATES_PER_DECK", 33):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "aggregate_limit")

    def test_slider_validates_model_and_view_domains_at_every_accepted_state(self) -> None:
        payload = compiled_slider_payload()
        scene = payload["slides"][0]["scene"]

        # The baseline remains exactly 26 at input 20, so an initial-state-only
        # check cannot distinguish this forged model from the compiled model.
        # At input 80 the forged model yields 56, beyond the declared y-domain
        # maximum of 50, and must therefore fail the complete state-space gate.
        scene["model"]["intercept"]["value"] = "16"
        scene["model"]["terms"][0][1]["value"]["value"] = "0.5"
        scene["evidence"]["formulas"] = [
            "Weekly capacity = 16 + 0.5 × Automation",
        ]

        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_slider_formula_is_bound_to_the_exact_linear_model(self) -> None:
        payload = compiled_slider_payload()
        scene = payload["slides"][0]["scene"]

        # This coordinated mutation preserves the compiled initial result
        # (20 + 0.3 * 20 == 18 + 0.4 * 20) and remains inside the view domain.
        # The unchanged evidence formula must still make the envelope invalid.
        scene["model"]["intercept"]["value"] = "20"
        scene["model"]["terms"][0][1]["value"]["value"] = "0.3"

        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_slider_scene_rejects_dangling_and_cross_registry_relations(self) -> None:
        def second_control(scene):
            control = json.loads(json.dumps(scene["controls"][0]))
            control["id"] = "automation-copy"
            scene["controls"].append(control)
            scene["initialState"]["automation-copy"] = "20"
            scene["printState"]["automation-copy"] = "20"
            scene["targets"]["control:automation-copy"] = {
                "kind": "control", "id": "automation-copy",
            }

        def add_uncomputed_numeric_output(scene):
            scene["outputDefinitions"]["capacity2"] = copy.deepcopy(
                scene["outputDefinitions"]["capacity"]
            )
            extra_output = copy.deepcopy(scene["initialEvaluation"]["outputs"]["capacity"])
            extra_output["value"] = "27"
            scene["initialEvaluation"]["outputs"]["capacity2"] = extra_output
            scene["reporting"]["secondaryOutputs"] = ["capacity2"]
            authored = copy.deepcopy(scene["view"]["points"][0])
            authored.update(id="forged-capacity", label="Forged capacity", highlight=False)
            authored["y"] = {"ref": "output:capacity2"}
            scene["view"]["points"].append(authored)
            resolved = copy.deepcopy(scene["initialEvaluation"]["view"]["points"][0])
            resolved.update(id="forged-capacity", label="Forged capacity", highlight=False)
            resolved["y"].update(value="27")
            resolved["yText"] = "27 cases/wk"
            scene["initialEvaluation"]["view"]["points"].append(resolved)
            narration = copy.deepcopy(scene["narration"]["program"]["outputs"][0])
            narration.update(id="capacity2", baseline="27")
            scene["narration"]["program"]["outputs"].append(narration)

        def move_linear_domain_outside_view(scene):
            scene["model"]["terms"][0][1]["value"]["value"] = "1"
            outputs = scene["initialEvaluation"]["outputs"]
            outputs["capacity"]["value"] = "38"
            outputs["decisionStatus"]["value"] = "Ready"
            outputs["recommendation"]["value"] = "Run a limited queue pilot"
            point = scene["initialEvaluation"]["view"]["points"][0]
            point["y"]["value"] = "38"
            point["yText"] = "38 cases/wk"
            decision = scene["initialEvaluation"]["decision"]
            decision.update(
                outcome="met", distance="6", status="Ready",
                recommendation="Run a limited queue pilot",
            )
            scene["narration"]["program"]["outputs"][0]["baseline"] = "38"
            scene["narration"]["program"]["transitions"][0]["baseline"] = "Ready"

        def forge_resolved_lineage(scene):
            scene["initialEvaluation"]["view"]["points"][0]["x"]["lineage"] = copy.deepcopy(
                scene["model"]["intercept"]["lineage"]
            )

        def add_uncomputed_text_output(scene):
            scene["outputDefinitions"]["forged"] = {"kind": "text", "label": "Forged"}
            forged = copy.deepcopy(scene["initialEvaluation"]["outputs"]["recommendation"])
            forged["value"] = "arbitrary"
            scene["initialEvaluation"]["outputs"]["forged"] = forged

        def forge_narration_message(scene):
            scene["narration"]["messages"]["initial"] = "forged"
            scene["narration"]["messagesByLocale"][scene["locale"]]["initial"] = "forged"

        def remove_narration_message(scene):
            scene["narration"]["messages"].pop("initial")
            scene["narration"]["messagesByLocale"][scene["locale"]].pop("initial")

        def forge_inactive_narration_message(scene):
            inactive = "ja" if scene["locale"] == "en" else "en"
            scene["narration"]["messagesByLocale"][inactive]["reset"] = "X" * 161

        def remove_inactive_narration_message(scene):
            inactive = "ja" if scene["locale"] == "en" else "en"
            scene["narration"]["messagesByLocale"][inactive].pop("reset")

        def forge_narration_template(scene):
            scene["narration"]["templates"]["restore"] = "{bogus}"
            scene["narration"]["templatesByLocale"][scene["locale"]]["restore"] = "{bogus}"

        def forge_model_lineage(scene):
            forged = copy.deepcopy(scene["controls"][0]["lineage"])
            scene["initialEvaluation"]["outputs"]["capacity"]["lineage"] = forged
            scene["initialEvaluation"]["view"]["points"][0]["y"]["lineage"] = copy.deepcopy(forged)

        def forge_decision_lineage(scene):
            forged = copy.deepcopy(scene["controls"][0]["lineage"])
            scene["initialEvaluation"]["decision"]["lineage"] = copy.deepcopy(forged)
            scene["initialEvaluation"]["outputs"]["decisionStatus"]["lineage"] = copy.deepcopy(forged)
            scene["initialEvaluation"]["outputs"]["recommendation"]["lineage"] = copy.deepcopy(forged)

        def forge_long_narration(scene):
            label = "L" * 200
            scene["controls"][0]["label"] = label
            scene["evidence"]["leaves"][0]["label"] = label
            scene["narration"]["program"]["controls"][0]["label"] = label

        def add_unused_evidence_leaf(scene):
            leaf = copy.deepcopy(scene["evidence"]["leaves"][0])
            leaf.update(id="leaf-999", label="Unused")
            scene["evidence"]["leaves"].append(leaf)

        def renumber_evidence_leaves(scene):
            leaves = scene["evidence"]["leaves"]
            replacements = {
                leaf["id"]: f"leaf-{index + 101:03d}"
                for index, leaf in enumerate(leaves)
            }
            for leaf in leaves:
                leaf["id"] = replacements[leaf["id"]]

            def replace_lineage_ids(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key == "leaves" and isinstance(child, list) and all(
                            isinstance(item, str) for item in child
                        ):
                            value[key] = [replacements.get(item, item) for item in child]
                        else:
                            replace_lineage_ids(child)
                elif isinstance(value, list):
                    for child in value:
                        replace_lineage_ids(child)

            replace_lineage_ids(scene)

        def clear_assumption_support(scene):
            scene["evidence"]["assumptions"] = []

            def clear_refs(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key == "assumptionRefs" and isinstance(child, list):
                            value[key] = []
                        else:
                            clear_refs(child)
                elif isinstance(value, list):
                    for child in value:
                        clear_refs(child)

            clear_refs(scene)

        def suppress_safe_source(scene):
            scene["evidence"]["sources"][0]["linked"] = False
            scene["targets"].pop("source:method-note")

        def add_invalid_storage_unit(scene):
            scene["quantities"]["forged_quantity"] = {
                "dimension": "derived",
                "unit": "bad unit",
                "exponents": {"currency": 0, "time": 0, "count": 1},
                "unitFactors": {"cases_per_week": 1},
                "display": "x",
            }

        def duplicate_threshold_refs(scene):
            refs = ["synthetic-inputs", "synthetic-inputs"]
            scene["decisionContract"]["threshold"]["provenance"]["assumptionRefs"] = refs
            threshold_leaf = next(
                leaf for leaf in scene["evidence"]["leaves"]
                if leaf["label"] == "Decision threshold"
            )
            threshold_leaf["assumptionRefs"] = refs

        mutations = (
            ("exactly_one_range", second_control, "scene_relation"),
            ("control_quantity", lambda scene: scene["controls"][0].update(quantity="ghost"), "scene_reference"),
            ("model_term_control", lambda scene: scene["model"]["terms"][0].__setitem__(0, "ghost"), "scene_reference"),
            ("model_output", lambda scene: scene["model"].update(output="ghost"), "scene_reference"),
            ("model_intercept_quantity", lambda scene: scene["model"]["intercept"].update(quantity="ghost"), "scene_reference"),
            ("model_input_quantity", lambda scene: scene["model"]["terms"][0][1].update(inputQuantity="ghost"), "scene_reference"),
            ("model_output_quantity", lambda scene: scene["model"]["terms"][0][1].update(outputQuantity="ghost"), "scene_reference"),
            ("coefficient_quantity", lambda scene: scene["model"]["terms"][0][1]["value"].update(quantity="ghost"), "scene_reference"),
            ("reporting_output", lambda scene: scene["reporting"].update(primaryOutput="ghost"), "scene_reference"),
            ("reporting_text_output", lambda scene: scene["reporting"].update(primaryOutput="recommendation"), "scene_relation"),
            ("uncomputed_numeric_output", add_uncomputed_numeric_output, "scene_relation"),
            ("uncomputed_text_output", add_uncomputed_text_output, "scene_relation"),
            ("linear_domain_endpoint", move_linear_domain_outside_view, "scene_relation"),
            ("view_axis_quantity", lambda scene: scene["view"].update(yQuantity="ghost"), "scene_reference"),
            ("view_output_ref", lambda scene: scene["view"]["points"][0].update(y={"ref": "output:recommendation"}), "scene_relation"),
            ("resolved_text", lambda scene: scene["initialEvaluation"]["view"]["points"][0].update(xText="FORGED"), "scene_relation"),
            ("resolved_lineage", forge_resolved_lineage, "scene_relation"),
            ("evidence_quantity", lambda scene: scene["evidence"]["leaves"][0].update(quantity="ghost"), "scene_reference"),
            ("decision_metric", lambda scene: scene["decisionContract"].update(metric={"ref": "output:recommendation"}), "scene_relation"),
            ("missing_initial_decision", lambda scene: scene["initialEvaluation"].pop("decision"), "scene_relation"),
            ("evaluated_output_quantity", lambda scene: scene["initialEvaluation"]["outputs"]["capacity"].update(quantity="automation_rate"), "scene_relation"),
            ("evaluated_output_value", lambda scene: scene["initialEvaluation"]["outputs"]["capacity"].update(value="27"), "scene_relation"),
            ("evaluated_view_value", lambda scene: scene["initialEvaluation"]["view"]["points"][0]["y"].update(value="27"), "scene_relation"),
            ("decision_status", lambda scene: scene["initialEvaluation"]["decision"].update(status="forged"), "scene_relation"),
            ("decision_status_label", lambda scene: scene["outputDefinitions"]["decisionStatus"].update(label="FORGED"), "scene_relation"),
            ("recommendation_label", lambda scene: scene["outputDefinitions"]["recommendation"].update(label="FORGED"), "scene_relation"),
            ("evidence_badge", lambda scene: scene["evidence"].update(badge="measured"), "scene_relation"),
            ("evidence_formula", lambda scene: scene["evidence"].update(formulas=["FORGED"]), "scene_relation"),
            ("unused_evidence_leaf", add_unused_evidence_leaf, "scene_relation"),
            ("compiler_owned_leaf_ids", renumber_evidence_leaves, "scene_relation"),
            ("missing_basis_support", clear_assumption_support, "scene_relation"),
            ("suppressed_safe_source", suppress_safe_source, "scene_relation"),
            ("evidence_trigger_label", lambda scene: scene["evidence"].update(triggerLabel="FORGED"), "scene_relation"),
            ("invalid_storage_unit", add_invalid_storage_unit, "identifier"),
            ("duplicate_threshold_refs", duplicate_threshold_refs, "scene_relation"),
            ("quantity_dimension", lambda scene: scene["quantities"]["weekly_capacity"].update(dimension="banana"), "scene_relation"),
            ("quantity_exponents", lambda scene: scene["quantities"]["weekly_capacity"]["exponents"].update(count=0), "scene_relation"),
            ("quantity_unit_factors", lambda scene: scene["quantities"]["weekly_capacity"]["unitFactors"].update(cases_per_week=0), "scene_relation"),
            ("quantity_currency", lambda scene: scene["quantities"]["weekly_capacity"].update(currency="USD"), "scene_relation"),
            ("output_format_quantity", lambda scene: scene["outputDefinitions"]["capacity"].update(format="currency"), "scene_relation"),
            ("model_lineage", forge_model_lineage, "scene_relation"),
            ("decision_lineage", forge_decision_lineage, "scene_relation"),
            ("narration_variants", lambda scene: scene["narration"].update(validatedVariants=0), "scene_relation"),
            ("narration_length", forge_long_narration, "text"),
            ("narration_message_value", forge_narration_message, "scene_relation"),
            ("narration_message_missing", remove_narration_message, "scene_shape"),
            ("narration_inactive_length", forge_inactive_narration_message, "scene_shape"),
            ("narration_inactive_missing", remove_inactive_narration_message, "scene_shape"),
            ("narration_template", forge_narration_template, "scene_relation"),
            ("demo_value_grid", lambda scene: scene["steps"][0]["action"].update(value="34"), "scene_relation"),
            ("narration_control", lambda scene: scene["narration"]["program"]["controls"][0].update(id="ghost"), "scene_reference"),
            ("narration_output", lambda scene: scene["narration"]["program"]["outputs"][0].update(id="ghost"), "scene_reference"),
            ("narration_transition", lambda scene: scene["narration"]["program"]["transitions"][0].update(id="ghost"), "scene_reference"),
        )
        for name, mutate, expected in mutations:
            payload = compiled_slider_payload()
            mutate(payload["slides"][0]["scene"])
            with self.subTest(name=name):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, expected)

    def test_slider_requires_decision_contract_and_matching_initial_decision(self) -> None:
        without_decision = compiled_slider_payload()
        scene = without_decision["slides"][0]["scene"]
        scene.pop("decisionContract")
        scene["initialEvaluation"].pop("decision")
        scene["evidence"]["leaves"] = [
            leaf for leaf in scene["evidence"]["leaves"]
            if leaf["label"] != "Decision threshold"
        ]
        for output_id in ("decisionStatus", "recommendation"):
            scene["outputDefinitions"].pop(output_id)
            scene["initialEvaluation"]["outputs"].pop(output_id)
        scene["narration"]["program"]["transitions"] = []
        for locale_messages in scene["narration"]["messagesByLocale"].values():
            locale_messages["initial"] = locale_messages["initial"].removesuffix("; Below demand")
            locale_messages["reset"] = locale_messages["reset"].removesuffix("; Below demand")
        scene["narration"]["messages"] = copy.deepcopy(
            scene["narration"]["messagesByLocale"][scene["locale"]]
        )
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(without_decision)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

        result_without_contract = compiled_slider_payload()
        result_without_contract["slides"][0]["scene"].pop("decisionContract")
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(result_without_contract)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_compiler_field_caps_remain_binding_at_the_envelope_boundary(self) -> None:
        mutations = (
            ("control_label", lambda scene: scene["controls"][0].update(label="C" * 41)),
            ("numeric_output_label", lambda scene: scene["outputDefinitions"]["capacity"].update(label="O" * 41)),
            ("met_status", lambda scene: scene["decisionContract"]["whenMet"].update(status="M" * 33)),
            ("not_met_status", lambda scene: scene["decisionContract"]["whenNotMet"].update(status="N" * 33)),
        )
        for name, mutate in mutations:
            payload = compiled_slider_payload()
            mutate(payload["slides"][0]["scene"])
            with self.subTest(name=name):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, "text")

    def test_fallback_invariant_caps_remain_binding_at_the_envelope_boundary(self) -> None:
        mutations = (
            ("headline", lambda scene: scene["invariants"].update(headline="H" * 501), "text"),
            ("source", lambda scene: scene["invariants"].update(source="S" * 501), "text"),
            ("classification", lambda scene: scene["invariants"].update(classification="C" * 501), "text"),
            ("footnote_text", lambda scene: scene["invariants"].update(footnotes=["F" * 501]), "text"),
            ("footnote_count", lambda scene: scene["invariants"].update(footnotes=["a", "b", "c"]), "scene_shape"),
        )
        for name, mutate, expected_code in mutations:
            payload = compiled_slider_payload()
            mutate(payload["slides"][0]["scene"])
            with self.subTest(name=name):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, expected_code)

    def test_fallback_theme_and_palette_remain_closed_at_the_envelope_boundary(self) -> None:
        mutations = (
            ("theme", "untrusted-theme"),
            ("palette", "untrusted-palette"),
        )
        for key, value in mutations:
            payload = compiled_slider_payload()
            payload["slides"][0]["scene"]["invariants"][key] = value
            with self.subTest(key=key):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, "scene_shape")

    def test_required_compiler_text_fields_reject_empty_or_whitespace(self) -> None:
        mutations = (
            ("source_label", lambda scene: scene["evidence"]["sources"][0].update(label="")),
            ("source_detail", lambda scene: scene["evidence"]["sources"][0].update(detail="   ")),
            ("assumption_label", lambda scene: scene["evidence"]["assumptions"][0].update(label="\t")),
            ("assumption_value", lambda scene: scene["evidence"]["assumptions"][0].update(value="")),
            ("axis_label", lambda scene: scene["view"].update(xLabel="   ")),
            ("point_label", lambda scene: scene["view"]["points"][0].update(label="")),
            ("control_label", lambda scene: scene["controls"][0].update(label="\n")),
            ("output_label", lambda scene: scene["outputDefinitions"]["capacity"].update(label="")),
            ("decision_status", lambda scene: scene["decisionContract"]["whenMet"].update(status=" ")),
            ("recommendation", lambda scene: scene["decisionContract"]["whenNotMet"].update(recommendation="")),
        )
        for name, mutate in mutations:
            payload = compiled_slider_payload()
            mutate(payload["slides"][0]["scene"])
            with self.subTest(name=name):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, "text")

    def test_linear_model_output_cannot_reuse_a_reserved_output_id(self) -> None:
        for replacement in ("score", "classification"):
            payload = compiled_slider_payload()
            scene = payload["slides"][0]["scene"]
            old = "capacity"
            scene["outputDefinitions"][replacement] = scene["outputDefinitions"].pop(old)
            scene["initialEvaluation"]["outputs"][replacement] = (
                scene["initialEvaluation"]["outputs"].pop(old)
            )
            scene["model"]["output"] = replacement
            scene["reporting"]["primaryOutput"] = replacement
            scene["decisionContract"]["metric"]["ref"] = "output:" + replacement
            for point in scene["view"]["points"]:
                if point["y"] == {"ref": "output:" + old}:
                    point["y"] = {"ref": "output:" + replacement}
            scene["narration"]["program"]["outputs"][0]["id"] = replacement
            payload["slides"][0]["display"]["staticSummary"]["values"][0]["id"] = replacement
            with self.subTest(replacement=replacement):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_envelope_rebinds_every_display_bridge_field_to_the_scene(self) -> None:
        mutations = (
            ("annotation", lambda display: display.update(baselineAnnotation="FORGED")),
            ("threshold", lambda display: display.update(thresholdText="999 cases/wk")),
            ("tick", lambda display: display["axisTickLabels"]["y"].__setitem__(1, "999 cases/wk")),
            ("value", lambda display: display["staticSummary"]["values"][0].update(text="999 cases/wk")),
            ("decision", lambda display: display["staticSummary"]["decision"].update(status="FORGED")),
            ("headline", lambda display: display["staticSummary"].update(headline="FORGED")),
            ("source", lambda display: display["staticSummary"].update(source="FORGED")),
        )
        for name, mutate in mutations:
            payload = compiled_slider_payload()
            mutate(payload["slides"][0]["display"])
            raw = bundle._canonical_json(payload)
            forged_encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
            with self.subTest(name=name, boundary="encode"):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.encode_envelope(payload)
                self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")
            with self.subTest(name=name, boundary="decode"):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.decode_envelope(forged_encoded)
                self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

        orphan_display = compiled_slider_payload()
        orphan_display["slides"][0]["scene"] = None
        raw = bundle._canonical_json(orphan_display)
        forged_encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        for boundary, operation in (
            ("encode", lambda: bundle.encode_envelope(orphan_display)),
            ("decode", lambda: bundle.decode_envelope(forged_encoded)),
        ):
            with self.subTest(name="orphan_display", boundary=boundary):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    operation()
                self.assertEqual(caught.exception.issues[0].code, "display_shape")

    def test_leaf_roots_have_compiler_exact_provenance_cardinality_and_ownership(self) -> None:
        multi_basis = compiled_slider_payload()
        scene = multi_basis["slides"][0]["scene"]
        control_leaf = scene["controls"][0]["lineage"]["leaves"][0]

        def add_basis(value):
            if isinstance(value, dict):
                if value.get("leaves") and control_leaf in value["leaves"]:
                    value["bases"] = ["illustrative", "assumed"]
                for child in value.values():
                    add_basis(child)
            elif isinstance(value, list):
                for child in value:
                    add_basis(child)

        add_basis(scene)
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(multi_basis)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import PROVENANCE, make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            scene_path = root / "scenes/02-capacity.json"
            authored = json.loads(scene_path.read_text(encoding="utf-8"))
            for index, x_value in enumerate((60, 70), start=1):
                authored["view"]["points"].append({
                    "id": f"literal-{index}",
                    "label": f"Literal {index}",
                    "x": {
                        "value": x_value,
                        "quantity": "automation_rate",
                        "provenance": copy.deepcopy(PROVENANCE),
                    },
                    "y": {"ref": "output:capacity"},
                })
            scene_path.write_text(json.dumps(authored, ensure_ascii=False), encoding="utf-8")
            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            for index, x_value in enumerate((60, 70), start=1):
                spec["points"].append({
                    "item_id": f"literal-{index}", "label": f"Literal {index}",
                    "x": x_value, "y": 26, "emphasis": False,
                })
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            compiled = build_interactive_deck.compile_manifest(manifest)

        compiled_scene = copy.deepcopy(compiled.slides[1].scene)
        first = compiled_scene["view"]["points"][-2]["x"]["lineage"]
        second = compiled_scene["view"]["points"][-1]["x"]["lineage"]
        first_leaf, second_leaf = first["leaves"][0], second["leaves"][0]
        compiled_scene["view"]["points"][-1]["x"]["lineage"] = copy.deepcopy(first)
        compiled_scene["initialEvaluation"]["view"]["points"][-1]["x"]["lineage"] = copy.deepcopy(first)
        compiled_scene["evidence"]["leaves"] = [
            leaf for leaf in compiled_scene["evidence"]["leaves"]
            if leaf["id"] != second_leaf
        ]
        self.assertNotEqual(first_leaf, second_leaf)
        payload = {
            "version": 1, "kind": "interactive-deck", "lang": "en", "locale": "en-US",
            "slides": [{
                "slideId": compiled.slides[1].slide_id,
                "scene": compiled_scene,
                "display": copy.deepcopy(compiled.slides[1].display),
            }],
        }
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_compiler_leaf_ids_follow_semantic_allocation_order(self) -> None:
        payload = compiled_slider_payload()
        scene = payload["slides"][0]["scene"]
        leaves = scene["evidence"]["leaves"]
        intercept_leaf = copy.deepcopy(leaves[1])
        coefficient_leaf = copy.deepcopy(leaves[2])
        leaves[1] = {"id": intercept_leaf["id"], **{
            key: value for key, value in coefficient_leaf.items() if key != "id"
        }}
        leaves[2] = {"id": coefficient_leaf["id"], **{
            key: value for key, value in intercept_leaf.items() if key != "id"
        }}
        scene["model"]["intercept"]["lineage"]["leaves"] = [coefficient_leaf["id"]]
        scene["model"]["terms"][0][1]["value"]["lineage"]["leaves"] = [intercept_leaf["id"]]
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_linear_leaf_lineages_require_a_feasible_shared_model_provenance(self) -> None:
        payload = compiled_slider_payload()
        scene = payload["slides"][0]["scene"]
        intercept = scene["model"]["intercept"]["lineage"]
        coefficient = scene["model"]["terms"][0][1]["value"]["lineage"]
        intercept_leaf = intercept["leaves"][0]
        coefficient_leaf = coefficient["leaves"][0]

        def forge_root(lineage, *, bases, badge):
            lineage.update(
                bases=bases,
                badge=badge,
                sourceRefs=["method-note"],
                assumptionRefs=["synthetic-inputs"],
            )
            leaf = next(
                item for item in scene["evidence"]["leaves"]
                if item["id"] == lineage["leaves"][0]
            )
            leaf.update(
                basis=badge,
                sourceRefs=["method-note"],
                assumptionRefs=["synthetic-inputs"],
            )

        forge_root(
            intercept,
            bases=["illustrative", "measured"],
            badge="illustrative",
        )
        forge_root(
            coefficient,
            bases=["assumed", "estimated"],
            badge="assumed",
        )

        def propagate(value):
            if isinstance(value, dict):
                leaves = value.get("leaves")
                if (
                    isinstance(leaves, list)
                    and intercept_leaf in leaves
                    and coefficient_leaf in leaves
                ):
                    value.update(
                        bases=["illustrative", "assumed", "estimated", "measured"],
                        badge="illustrative",
                        sourceRefs=["method-note"],
                        assumptionRefs=["synthetic-inputs"],
                    )
                for child in value.values():
                    propagate(child)
            elif isinstance(value, list):
                for child in value:
                    propagate(child)

        propagate(scene)
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

        normalization_only = compiled_slider_payload()
        scene = normalization_only["slides"][0]["scene"]
        intercept = scene["model"]["intercept"]["lineage"]
        coefficient = scene["model"]["terms"][0][1]["value"]["lineage"]
        intercept_leaf = intercept["leaves"][0]
        coefficient_leaf = coefficient["leaves"][0]
        normalization_notes = [
            {
                "note": name,
                "fromUnit": "cases_per_week",
                "toUnit": "cases_per_week",
            }
            for name in ("A", "B")
        ]
        intercept.update(
            derived=True,
            normalizations=copy.deepcopy(normalization_notes),
        )
        coefficient.update(bases=["assumed"], badge="assumed")
        coefficient_record = next(
            item for item in scene["evidence"]["leaves"]
            if item["id"] == coefficient_leaf
        )
        coefficient_record["basis"] = "assumed"

        def propagate_normalization_only(value):
            if isinstance(value, dict):
                leaves = value.get("leaves")
                if (
                    isinstance(leaves, list)
                    and intercept_leaf in leaves
                    and coefficient_leaf in leaves
                ):
                    value.update(
                        derived=True,
                        bases=["illustrative", "assumed"],
                        badge="illustrative",
                        normalizations=copy.deepcopy(normalization_notes),
                    )
                for child in value.values():
                    propagate_normalization_only(child)
            elif isinstance(value, list):
                for child in value:
                    propagate_normalization_only(child)

        propagate_normalization_only(scene)
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(normalization_only)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_linear_leaf_normalizations_share_feasible_model_provenance(self) -> None:
        payload = compiled_slider_payload()
        scene = payload["slides"][0]["scene"]
        intercept = scene["model"]["intercept"]["lineage"]
        coefficient = scene["model"]["terms"][0][1]["value"]["lineage"]
        intercept_leaf = intercept["leaves"][0]
        coefficient_leaf = coefficient["leaves"][0]

        def note(name: str) -> dict:
            return {
                "note": name,
                "fromUnit": "cases_per_week",
                "toUnit": "cases_per_week",
            }

        intercept_notes = [note("A"), note("B")]
        coefficient_notes = [note("C"), note("D")]
        intercept.update(
            derived=True,
            bases=["illustrative", "measured"],
            badge="illustrative",
            sourceRefs=["method-note"],
            assumptionRefs=["synthetic-inputs"],
            normalizations=copy.deepcopy(intercept_notes),
        )
        coefficient.update(
            derived=True,
            bases=["assumed", "measured"],
            badge="assumed",
            sourceRefs=["method-note"],
            assumptionRefs=["synthetic-inputs"],
            normalizations=copy.deepcopy(coefficient_notes),
        )
        for lineage in (intercept, coefficient):
            leaf = next(
                item for item in scene["evidence"]["leaves"]
                if item["id"] == lineage["leaves"][0]
            )
            leaf.update(
                basis=lineage["badge"],
                sourceRefs=["method-note"],
                assumptionRefs=["synthetic-inputs"],
            )

        combined_notes = intercept_notes + coefficient_notes

        def propagate(value):
            if isinstance(value, dict):
                leaves = value.get("leaves")
                if (
                    isinstance(leaves, list)
                    and intercept_leaf in leaves
                    and coefficient_leaf in leaves
                ):
                    value.update(
                        derived=True,
                        bases=["illustrative", "assumed", "measured"],
                        badge="illustrative",
                        sourceRefs=["method-note"],
                        assumptionRefs=["synthetic-inputs"],
                        normalizations=copy.deepcopy(combined_notes),
                    )
                for child in value.values():
                    propagate(child)
            elif isinstance(value, list):
                for child in value:
                    propagate(child)

        propagate(scene)
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_provenance_normalization_text_is_required(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            scene_path = root / "scenes/02-capacity.json"
            authored = json.loads(scene_path.read_text(encoding="utf-8"))
            authored["controls"][0]["provenance"]["normalization"] = {
                "note": "Converted for display",
                "fromUnit": "ratio",
                "toUnit": "percentage_point",
            }
            scene_path.write_text(json.dumps(authored, ensure_ascii=False), encoding="utf-8")
            compiled = build_interactive_deck.compile_manifest(manifest)

        payload = {
            "version": 1, "kind": "interactive-deck", "lang": "en", "locale": "en-US",
            "slides": [{
                "slideId": compiled.slides[1].slide_id,
                "scene": copy.deepcopy(compiled.slides[1].scene),
                "display": copy.deepcopy(compiled.slides[1].display),
            }],
        }

        def erase_notes(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "note" and child == "Converted for display":
                        value[key] = ""
                    else:
                        erase_notes(child)
            elif isinstance(value, list):
                for child in value:
                    erase_notes(child)

        erase_notes(payload["slides"][0]["scene"])
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "text")

    def test_threshold_leaf_selection_allows_a_legitimate_label_collision(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            scene_path = root / "scenes/02-capacity.json"
            authored = json.loads(scene_path.read_text(encoding="utf-8"))
            authored["controls"][0].update(
                label="Decision threshold",
                quantity="weekly_capacity",
            )
            authored["model"]["terms"]["automation"]["inputQuantity"] = "weekly_capacity"
            authored["view"].update(
                xLabel="Decision threshold",
                xQuantity="weekly_capacity",
            )
            scene_path.write_text(json.dumps(authored, ensure_ascii=False), encoding="utf-8")

            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["x_axis"].update(
                label="Decision threshold",
                quantity="weekly_capacity",
                unit="cases/wk",
                tick_labels=["0 cases/wk", "80 cases/wk"],
            )
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            compiled = build_interactive_deck.compile_manifest(manifest)

        payload = {
            "version": 1, "kind": "interactive-deck", "lang": "en", "locale": "en-US",
            "slides": [{
                "slideId": compiled.slides[1].slide_id,
                "scene": copy.deepcopy(compiled.slides[1].scene),
                "display": copy.deepcopy(compiled.slides[1].display),
            }],
        }
        self.assertEqual(
            bundle.decode_envelope(bundle.encode_envelope(payload)),
            payload,
        )

    def test_view_display_text_accepts_authored_precision_without_trusting_forged_text(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import PROVENANCE, make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)

            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["initialState"]["automation"] = 20.0
            scene["printState"]["automation"] = 20.0
            scene["view"]["points"].append({
                "id": "authored-reference",
                "label": "Authored reference",
                "x": {
                    "value": 60.5,
                    "quantity": "automation_rate",
                    "provenance": copy.deepcopy(PROVENANCE),
                },
                "y": {
                    "value": 42.0,
                    "quantity": "weekly_capacity",
                    "provenance": copy.deepcopy(PROVENANCE),
                },
            })
            scene_path.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")

            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["points"][0]["x"] = 20.0
            spec["points"].append({
                "item_id": "authored-reference",
                "label": "Authored reference",
                "x": 60.5,
                "y": 42.0,
                "emphasis": False,
            })
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

            compiled = build_interactive_deck.compile_manifest(manifest)
            compiled_slide = compiled.slides[1]
            payload = {
                "version": 1,
                "kind": "interactive-deck",
                "lang": "en",
                "locale": "en-US",
                "slides": [{
                    "slideId": compiled_slide.slide_id,
                    "scene": copy.deepcopy(compiled_slide.scene),
                    "display": copy.deepcopy(compiled_slide.display),
                }],
            }
            points = payload["slides"][0]["scene"]["initialEvaluation"]["view"]["points"]
            self.assertEqual(points[0]["xText"], "20.0%")
            self.assertEqual((points[1]["xText"], points[1]["yText"]), ("60.5%", "42.0 cases/wk"))
            self.assertEqual(bundle.decode_envelope(bundle.encode_envelope(payload)), payload)

            forged = copy.deepcopy(payload)
            forged_points = forged["slides"][0]["scene"]["initialEvaluation"]["view"]["points"]
            forged_points[0]["xText"] = "20.00%"
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(forged)
            self.assertEqual(caught.exception.issues[0].code, "scene_relation")

            rounded_literal = copy.deepcopy(payload)
            rounded_literal["slides"][0]["scene"]["initialEvaluation"]["view"]["points"][1]["xText"] = "61%"
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(rounded_literal)
            self.assertEqual(caught.exception.issues[0].code, "scene_relation")

            def literal_parts(candidate):
                candidate_scene = candidate["slides"][0]["scene"]
                authored = candidate_scene["view"]["points"][1]["x"]["lineage"]
                resolved = candidate_scene["initialEvaluation"]["view"]["points"][1]["x"]["lineage"]
                leaf_id = authored["leaves"][0]
                leaf = next(
                    item for item in candidate_scene["evidence"]["leaves"]
                    if item["id"] == leaf_id
                )
                return authored, resolved, leaf

            literal_mutations = (
                ("leaf_label", lambda authored, resolved, leaf: leaf.update(label="FORGED")),
                ("lineage_steps", lambda authored, resolved, leaf: (
                    authored.update(steps=["forged"]), resolved.update(steps=["forged"])
                )),
                ("derived_without_normalization", lambda authored, resolved, leaf: (
                    authored.update(derived=True), resolved.update(derived=True)
                )),
            )
            for name, mutate in literal_mutations:
                forged_literal = copy.deepcopy(payload)
                mutate(*literal_parts(forged_literal))
                with self.subTest(name=name):
                    with self.assertRaises(bundle.BundleValidationError) as caught:
                        bundle.encode_envelope(forged_literal)
                    self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_view_domain_precision_is_bounded_but_independent_of_model_scale(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)

            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["view"]["yDomain"] = [0, 50.25]
            scene_path.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")

            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["y_axis"]["domain"] = [0, 50.25]
            spec["y_axis"]["tick_labels"] = ["0 cases/wk", "50.25 cases/wk"]
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

            compiled = build_interactive_deck.compile_manifest(manifest)
            compiled_slide = compiled.slides[1]
            payload = {
                "version": 1,
                "kind": "interactive-deck",
                "lang": "en",
                "locale": "en-US",
                "slides": [{
                    "slideId": compiled_slide.slide_id,
                    "scene": copy.deepcopy(compiled_slide.scene),
                    "display": copy.deepcopy(compiled_slide.display),
                }],
            }
            self.assertEqual(payload["slides"][0]["scene"]["scale"], 1)
            self.assertEqual(payload["slides"][0]["scene"]["view"]["yDomain"], ["0", "50.25"])
            self.assertEqual(bundle.decode_envelope(bundle.encode_envelope(payload)), payload)

            overprecise = copy.deepcopy(payload)
            overprecise_scene = overprecise["slides"][0]["scene"]
            overprecise_scene["view"]["yDomain"] = ["0", "50.0000001"]
            overprecise_scene["initialEvaluation"]["view"]["yDomain"] = ["0", "50.0000001"]
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(overprecise)
            self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_dot_domains_remain_distinct_in_fallback_number_space(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import PROVENANCE, make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["view"].update(
                xDomain=[999999999999, 1000000000000],
                domainReason="High-magnitude synthetic axis",
            )
            scene["view"]["points"][0]["x"] = {
                "value": 999999999999,
                "quantity": "automation_rate",
                "provenance": copy.deepcopy(PROVENANCE),
            }
            scene_path.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")

            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["x_axis"].update(
                domain=[999999999999, 1000000000000],
                tick_labels=["999,999,999,999%", "1,000,000,000,000%"],
            )
            spec["points"][0]["x"] = 999999999999
            spec["domain_reason"] = "High-magnitude synthetic axis"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            compiled_slide = build_interactive_deck.compile_manifest(manifest).slides[1]

        payload = {
            "version": 1,
            "kind": "interactive-deck",
            "lang": "en",
            "locale": "en-US",
            "slides": [{
                "slideId": compiled_slide.slide_id,
                "scene": copy.deepcopy(compiled_slide.scene),
                "display": copy.deepcopy(compiled_slide.display),
            }],
        }
        collapsed_upper = "999999999999.000001"
        scene = payload["slides"][0]["scene"]
        scene["view"]["xDomain"][1] = collapsed_upper
        scene["initialEvaluation"]["view"]["xDomain"][1] = collapsed_upper
        display = payload["slides"][0]["display"]
        display["axisTickLabels"]["x"][1] = "999,999,999,999.000001%"
        display["staticSummary"]["paragraphs"] = [
            paragraph.replace(
                "1,000,000,000,000%",
                "999,999,999,999.000001%",
            )
            for paragraph in display["staticSummary"]["paragraphs"]
        ]
        self.assertEqual(float(scene["view"]["xDomain"][0]), float(collapsed_upper))
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.encode_envelope(payload)
        self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_signed_dot_plot_domain_reason_crosses_the_task3_bundle_boundary(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)

            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["controls"][0].update(min=-20, max=20, step=5)
            scene["view"]["xDomain"] = [-20, 20]
            scene["view"]["yDomain"] = [-10, 30]
            scene["view"]["domainReason"] = "Signed operational range"
            scene["demo"][0]["value"] = 15
            scene_path.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")

            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["x_axis"]["domain"] = [-20, 20]
            spec["x_axis"]["tick_labels"] = ["−20%", "20%"]
            spec["y_axis"]["domain"] = [-10, 30]
            spec["y_axis"]["tick_labels"] = ["−10 cases/wk", "30 cases/wk"]
            spec["domain_reason"] = "Signed operational range"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

            compiled = build_interactive_deck.compile_manifest(manifest)
            compiled_slide = compiled.slides[1]
            self.assertIn(
                "Threshold 32 cases/wk · above range",
                compiled_slide.live_shell_svg.serialized,
            )
            payload = {
                "version": 1,
                "kind": "interactive-deck",
                "lang": "en",
                "locale": "en-US",
                "slides": [{
                    "slideId": compiled_slide.slide_id,
                    "scene": copy.deepcopy(compiled_slide.scene),
                    "display": copy.deepcopy(compiled_slide.display),
                }],
            }
            self.assertEqual(payload["slides"][0]["scene"]["view"]["domainReason"], "Signed operational range")
            self.assertEqual(bundle.decode_envelope(bundle.encode_envelope(payload)), payload)

    def test_model_inverse_uses_scene_scale_before_output_display_rounding(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)

            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["model"]["terms"]["automation"]["coefficient"] = 0.33
            scene_path.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")

            spec_path = root / "specs/02-capacity.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["points"][0]["y"] = 24.6
            spec["interactive_result"]["value"] = 24.6
            spec["annotation"] = (
                "Weekly capacity 25 cases/wk; Below demand; threshold ≥ "
                "32 cases/wk; Increase automation before the pilot"
            )
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

            compiled = build_interactive_deck.compile_manifest(manifest)
            compiled_slide = compiled.slides[1]
            payload = {
                "version": 1,
                "kind": "interactive-deck",
                "lang": "en",
                "locale": "en-US",
                "slides": [{
                    "slideId": compiled_slide.slide_id,
                    "scene": copy.deepcopy(compiled_slide.scene),
                    "display": copy.deepcopy(compiled_slide.display),
                }],
            }
            compiled_scene = payload["slides"][0]["scene"]
            self.assertEqual(compiled_scene["scale"], 2)
            self.assertEqual(compiled_scene["initialEvaluation"]["outputs"]["capacity"]["value"], "24.6")
            self.assertEqual(compiled_scene["initialEvaluation"]["view"]["points"][0]["yText"], "25 cases/wk")
            self.assertEqual(bundle.decode_envelope(bundle.encode_envelope(payload)), payload)

            display_rounded = copy.deepcopy(payload)
            display_rounded["slides"][0]["scene"]["initialEvaluation"]["outputs"]["capacity"]["value"] = "25"
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(display_rounded)
            self.assertEqual(caught.exception.issues[0].code, "scene_relation")

    def test_leaf_normalizations_must_end_in_the_typed_quantity_storage_unit(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = make_fixture(root)
            scene_path = root / "scenes/02-capacity.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"))
            scene["controls"][0]["provenance"]["normalization"] = {
                "note": "Converted to storage percentage points",
                "fromUnit": "percent",
                "toUnit": "percentage_point",
            }
            scene["decisionContract"]["threshold"]["provenance"]["normalization"] = {
                "note": "Converted to weekly capacity",
                "fromUnit": "daily_cases",
                "toUnit": "cases_per_week",
            }
            scene_path.write_text(json.dumps(scene, ensure_ascii=False), encoding="utf-8")

            compiled = build_interactive_deck.compile_manifest(manifest)
            compiled_slide = compiled.slides[1]
            payload = {
                "version": 1,
                "kind": "interactive-deck",
                "lang": "en",
                "locale": "en-US",
                "slides": [{
                    "slideId": compiled_slide.slide_id,
                    "scene": copy.deepcopy(compiled_slide.scene),
                    "display": copy.deepcopy(compiled_slide.display),
                }],
            }
            self.assertEqual(bundle.decode_envelope(bundle.encode_envelope(payload)), payload)

            wrong_unit = copy.deepcopy(payload)

            def replace_to_unit(value):
                if isinstance(value, dict):
                    for key, child in value.items():
                        if key == "toUnit":
                            value[key] = "WRONG"
                        else:
                            replace_to_unit(child)
                elif isinstance(value, list):
                    for child in value:
                        replace_to_unit(child)

            replace_to_unit(wrong_unit["slides"][0]["scene"])
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.encode_envelope(wrong_unit)
            self.assertEqual(caught.exception.issues[0].code, "scene_relation")


class SvgBoundaryTests(unittest.TestCase):
    def test_raw_svg_byte_limit_is_inclusive_and_precedes_xml_parsing(self) -> None:
        exact = len(SAFE_SVG.encode("utf-8"))
        with mock.patch.object(bundle, "MAX_RAW_SVG_BYTES", exact):
            bundle.validate_renderer_svg(SAFE_SVG, slide_ordinal=1, role="fallback")
        with (
            mock.patch.object(bundle, "MAX_RAW_SVG_BYTES", exact - 1),
            mock.patch.object(bundle.ET, "fromstring", side_effect=AssertionError("XML parser reached")) as parser,
            self.assertRaises(bundle.BundleValidationError) as caught,
        ):
            bundle.validate_renderer_svg(SAFE_SVG, slide_ordinal=1, role="fallback")
        self.assertEqual(caught.exception.issues[0].code, "svg_limit")
        parser.assert_not_called()

    def test_svg_element_limit_is_role_specific_and_precedes_tree_materialization(self) -> None:
        for role, limit in bundle.MAX_SVG_ELEMENTS_BY_ROLE.items():
            root = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">'
            exact = root + '<rect/>' * (limit - 1) + '</svg>'
            self.assertEqual(
                bundle.validate_renderer_svg(exact, slide_ordinal=1, role=role).element_count,
                limit,
            )
            one_over = root + '<rect/>' * limit + '</svg>'
            with (
                mock.patch.object(bundle.ET, "fromstring", side_effect=AssertionError("tree parser reached")) as parser,
                self.assertRaises(bundle.BundleValidationError) as caught,
            ):
                bundle.validate_renderer_svg(one_over, slide_ordinal=1, role=role)
            self.assertEqual(caught.exception.issues[0].code, "svg_limit")
            parser.assert_not_called()

    def test_svg_depth_is_bounded_before_serialization_recursion(self) -> None:
        root = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">'
        exact = root + "<g>" * 100 + '<rect width="1" height="1" fill="#FFFFFF"/>' + "</g>" * 100 + "</svg>"
        self.assertGreater(bundle.validate_renderer_svg(exact, slide_ordinal=1, role="live-shell").element_count, 100)
        too_deep = root + "<g>" * 1_000 + '<rect width="1" height="1" fill="#FFFFFF"/>' + "</g>" * 1_000 + "</svg>"
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.validate_renderer_svg(too_deep, slide_ordinal=1, role="live-shell")
        self.assertEqual(caught.exception.issues[0].code, "svg_limit")

    def test_svg_is_validated_rewritten_and_made_inert(self) -> None:
        validated = bundle.validate_renderer_svg(LIVE_SVG, slide_ordinal=2, role="live-shell")
        self.assertIn('id="idsvg-2-live-shell-chart-clip"', validated.serialized)
        self.assertIn('clip-path="url(#idsvg-2-live-shell-chart-clip)"', validated.serialized)
        self.assertIn('aria-hidden="true"', validated.serialized)
        self.assertIn('focusable="false"', validated.serialized)
        self.assertNotIn('role="img"', validated.serialized)
        self.assertEqual(validated.ids, (
            "idsvg-2-live-shell-chart-clip",
            "idsvg-2-live-shell-geometry",
            "idsvg-2-live-shell-point",
        ))

        boundary = bundle.validate_renderer_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">'
            '<rect x="-1" y="-1" width="0" height="0" stroke-width="0" opacity="0" fill="#FFFFFF"/>'
            '<circle cx="0" cy="0" r="0" opacity="1" fill="#000000"/>'
            '<text x="0" y="0" font-size="0" opacity="1" fill="#000000">x</text>'
            '</svg>',
            slide_ordinal=3,
            role="fallback",
        )
        self.assertEqual(boundary.element_count, 4)

    def test_svg_rejects_active_malformed_or_cross_tree_content(self) -> None:
        attacks = {
            "doctype": '<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>',
            "processing_instruction": '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>',
            "script": '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            "foreign_object": '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
            "event": '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
            "style": '<svg xmlns="http://www.w3.org/2000/svg"><rect style="background:url(https://x)"/></svg>',
            "external_reference": '<svg xmlns="http://www.w3.org/2000/svg"><g clip-path="url(https://x/#a)"/></svg>',
            "unresolved_reference": '<svg xmlns="http://www.w3.org/2000/svg"><g clip-path="url(#missing)"/></svg>',
            "duplicate_attribute": '<svg xmlns="http://www.w3.org/2000/svg" width="1" width="2"/>',
            "unexpected_namespace": '<svg xmlns="http://www.w3.org/2000/svg" xmlns:x="urn:x"><x:script/></svg>',
            "unused_namespace": '<svg xmlns="http://www.w3.org/2000/svg" xmlns:x="urn:x" viewBox="0 0 1280 720" width="1280" height="720"/>',
            "unicode_namespace_prefix": '<svg xmlns="http://www.w3.org/2000/svg" xmlns:π="urn:x" viewBox="0 0 1280 720" width="1280" height="720"/>',
            "root_text": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">TRAIL<rect width="1" height="1" fill="#FFFFFF"/></svg>',
            "element_tail": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><rect width="1" height="1" fill="#FFFFFF"/>TRAIL</svg>',
            "unicode_numeric": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><rect x="１" y="0" width="1" height="1" fill="#FFFFFF"/></svg>',
            "nonfinite_viewbox": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1e999 720" width="1280" height="720"/>',
            "nonfinite_path": '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0 L1e999 2" fill="none"/></svg>',
            "entity": '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>',
            "mixed_case_tag": '<svg xmlns="http://www.w3.org/2000/svg"><Script/></svg>',
            "missing_root_geometry": '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1" fill="#FFFFFF"/></svg>',
            "wrong_root_geometry": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="1 2 3 4" width="1" height="1"><rect width="1" height="1" fill="#FFFFFF"/></svg>',
            "empty_root": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"/>',
            "negative_width": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><rect width="-1" height="1" fill="#FFFFFF"/></svg>',
            "negative_height": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><rect width="1" height="-1" fill="#FFFFFF"/></svg>',
            "negative_radius": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><circle cx="1" cy="1" r="-1" fill="#FFFFFF"/></svg>',
            "negative_stroke_width": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><line x1="0" y1="0" x2="1" y2="1" stroke="#000000" stroke-width="-1"/></svg>',
            "negative_dasharray": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><line x1="0" y1="0" x2="1" y2="1" stroke="#000000" stroke-dasharray="1,-2"/></svg>',
            "negative_font_size": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><text x="0" y="0" font-size="-1" fill="#000000">x</text></svg>',
            "opacity_over_one": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"><rect width="1" height="1" opacity="2" fill="#FFFFFF"/></svg>',
        }
        for name, raw in attacks.items():
            with self.subTest(name=name), self.assertRaises(bundle.BundleValidationError):
                bundle.validate_renderer_svg(raw, slide_ordinal=1, role="live-shell")

    def test_static_renderer_role_does_not_accept_live_shell_elements(self) -> None:
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.validate_renderer_svg(LIVE_SVG, slide_ordinal=1, role="fallback")
        self.assertEqual(caught.exception.issues[0].code, "svg_tag")
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.validate_renderer_svg(SAFE_SVG, slide_ordinal=True, role="fallback")
        self.assertEqual(caught.exception.issues[0].code, "svg_role")

    def test_every_current_renderer_example_crosses_the_strict_svg_boundary(self) -> None:
        root = Path(__file__).resolve().parents[1]
        ordinal = 1
        for path in sorted((root / "examples").glob("**/*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or "pattern" not in raw:
                continue
            with self.subTest(path=path):
                validated = bundle.validate_renderer_svg(
                    render_slide_spec.render(raw), slide_ordinal=ordinal, role="fallback"
                )
                self.assertGreater(validated.element_count, 1)
            ordinal += 1


class BundleAndScannerTests(unittest.TestCase):
    def test_demo_cue_has_bounded_normal_motion_and_a_static_reduced_mode(self) -> None:
        assets = bundle.load_runtime_assets()
        css = assets.css.decode("utf-8")
        javascript = assets.js.decode("utf-8")

        cue_rule = css[css.index(".demo-cue {") : css.index(".demo-cue-ring {", css.index(".demo-cue {"))]
        for property_name in ("left", "top", "width", "height"):
            self.assertIn(property_name + " 180ms cubic-bezier(0.22, 1, 0.36, 1)", cue_rule)
        ring_rule = css[css.index(".demo-cue-ring {") : css.index("@keyframes idrt-cue-pulse")]
        self.assertIn("animation: idrt-cue-pulse", ring_rule)
        self.assertIn(".demo-cue.is-positioning { transition: none; }", css)
        self.assertIn(".demo-cue.is-static { transition: none; }", css)
        self.assertIn(".demo-cue.is-static .demo-cue-ring { animation: none; }", css)

        placement = javascript[
            javascript.index("      function positionDemoCue(") : javascript.index(
                "      function demoEvent(", javascript.index("      function positionDemoCue(")
            )
        ]
        self.assertIn("var cueTravelLimit = 12;", placement)
        self.assertIn("var cueSizeTravel = 2;", placement)
        self.assertIn('demoCue.classList.add("is-positioning")', placement)
        self.assertIn("demoCue.getBoundingClientRect()", placement)
        self.assertIn('demoCue.classList.remove("is-positioning")', placement)

    def test_panel_action_controls_keep_a_44_pixel_target_floor(self) -> None:
        css = bundle.load_runtime_assets().css.decode("utf-8")
        start = css.index(".panel-openers button,")
        end = css.index(".panel-openers button[aria-expanded", start)
        rule = css[start:end]
        self.assertIn("min-width: 44px;", rule)
        self.assertIn("min-height: 44px;", rule)

    def test_bundle_rejects_a_forged_validated_svg_value(self) -> None:
        forged = bundle.ValidatedSvg(
            '<svg xmlns="http://www.w3.org/2000/svg"><script>globalThis.pwned=1</script></svg>',
            (),
            2,
        )
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.bundle_deck(
                title="Safe",
                lang="en",
                slides=(replace(static_slide(), fallback_svg=forged),),
                assets=assets(),
            )
        self.assertEqual(caught.exception.issues[0].code, "svg_boundary")

    def test_bundle_rejects_validated_svg_from_the_wrong_role_or_slide(self) -> None:
        wrong_role = bundle.validate_renderer_svg(
            LIVE_SVG, slide_ordinal=1, role="live-shell",
        )
        wrong_ordinal = bundle.validate_renderer_svg(
            SAFE_SVG, slide_ordinal=99, role="fallback",
        )
        for validated in (wrong_role, wrong_ordinal):
            with self.subTest(validated=validated):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.bundle_deck(
                        title="Safe",
                        lang="en",
                        slides=(replace(static_slide(), fallback_svg=validated),),
                        assets=assets(),
                    )
                self.assertEqual(caught.exception.issues[0].code, "svg_boundary")

        replaced = replace(
            static_slide().fallback_svg,
            serialized=(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                '<filter><feImage href="https://evil.example/pixel.png"/></filter></svg>'
            ),
            ids=(),
            element_count=3,
        )
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.bundle_deck(
                title="Safe",
                lang="en",
                slides=(replace(static_slide(), fallback_svg=replaced),),
                assets=assets(),
            )
        self.assertEqual(caught.exception.issues[0].code, "svg_boundary")

    def test_bundle_rejects_divergent_semantic_and_display_truth(self) -> None:
        slide = static_slide()
        divergent = replace(
            slide,
            display={
                "staticSummary": summary("Different claim"),
                "baselineAnnotation": "",
                "thresholdText": None,
                "axisTickLabels": None,
            },
        )
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.bundle_deck(title="Safe", lang="en", slides=(divergent,), assets=assets())
        self.assertEqual(caught.exception.issues[0].code, "display_mismatch")

    def test_bundle_rebinds_matching_semantic_and_display_truth_to_scene(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            compiled = build_interactive_deck.compile_manifest(make_fixture(Path(directory)))
        interactive = compiled.slides[1]
        forged_summary = copy.deepcopy(interactive.static_summary)
        forged_summary["values"][0]["text"] = "999 cases/wk"
        forged_summary["decision"] = None
        forged_display = copy.deepcopy(interactive.display)
        forged_display["staticSummary"] = copy.deepcopy(forged_summary)
        forged = replace(
            interactive,
            static_summary=forged_summary,
            display=forged_display,
        )
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.bundle_deck(
                title=compiled.title,
                lang=compiled.lang,
                slides=(compiled.slides[0], forged),
                assets=bundle.load_runtime_assets(),
            )
        self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

        for mutation in ("chrome", "paragraphs", "highlight", "ticks", "threshold"):
            forged_summary = copy.deepcopy(interactive.static_summary)
            if mutation == "chrome":
                forged_summary.update(headline="FORGED HEADLINE", source="FORGED SOURCE")
            elif mutation == "paragraphs":
                forged_summary["paragraphs"] = ["FORGED PARAGRAPH"]
            elif mutation in ("highlight", "ticks"):
                if mutation == "highlight":
                    forged_summary["paragraphs"].remove("Emphasized: Weekly capacity")
                else:
                    forged_summary["paragraphs"] = [
                        paragraph for paragraph in forged_summary["paragraphs"]
                        if paragraph not in ("0%", "80%", "0 cases/wk", "50 cases/wk")
                    ]
            forged_display = copy.deepcopy(interactive.display)
            forged_display["staticSummary"] = copy.deepcopy(forged_summary)
            if mutation == "ticks":
                forged_display["axisTickLabels"] = None
            if mutation == "threshold":
                forged_display["thresholdText"] = None
            forged = replace(
                interactive,
                headline=forged_summary["headline"],
                source=forged_summary["source"],
                static_summary=forged_summary,
                display=forged_display,
            )
            with self.subTest(mutation=mutation):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.bundle_deck(
                        title=compiled.title,
                        lang=compiled.lang,
                        slides=(compiled.slides[0], forged),
                        assets=bundle.load_runtime_assets(),
                    )
                self.assertEqual(
                    caught.exception.issues[0].code,
                    "display_shape" if mutation in ("ticks", "threshold") else "summary_mismatch",
                )

    def test_bundle_rejects_forged_display_bridge_text_even_when_semantics_match_it(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            compiled = build_interactive_deck.compile_manifest(make_fixture(Path(directory)))
        interactive = compiled.slides[1]

        def forged_slide(kind: str) -> bundle.BundleSlide:
            forged_display = copy.deepcopy(interactive.display)
            forged_summary = copy.deepcopy(interactive.static_summary)
            if kind == "annotation":
                forged_display["baselineAnnotation"] = "FORGED BASELINE"
            elif kind == "threshold":
                forged_display["thresholdText"] = "999 cases/wk"
            else:
                old_tick = forged_display["axisTickLabels"]["y"][1]
                new_tick = "999 cases/wk"
                forged_display["axisTickLabels"]["y"][1] = new_tick
                forged_summary["paragraphs"] = [
                    new_tick if paragraph == old_tick else paragraph
                    for paragraph in forged_summary["paragraphs"]
                ]
                forged_display["staticSummary"] = copy.deepcopy(forged_summary)
            return replace(
                interactive,
                static_summary=forged_summary,
                display=forged_display,
            )

        for kind in ("annotation", "threshold", "tick_and_summary"):
            with self.subTest(kind=kind):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.bundle_deck(
                        title=compiled.title,
                        lang=compiled.lang,
                        slides=(compiled.slides[0], forged_slide(kind)),
                        assets=bundle.load_runtime_assets(),
                    )
                self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

    def test_bundle_rejects_additive_semantic_only_paragraphs(self) -> None:
        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            compiled = build_interactive_deck.compile_manifest(make_fixture(Path(directory)))
        interactive = compiled.slides[1]
        original = interactive.static_summary["paragraphs"]
        variants = {
            "prepend": ["FORGED SEMANTIC-ONLY CLAIM", *original],
            "interleave": [original[0], "FORGED SEMANTIC-ONLY CLAIM", *original[1:]],
            "append": [*original, "FORGED SEMANTIC-ONLY CLAIM"],
        }
        for name, paragraphs in variants.items():
            forged_summary = copy.deepcopy(interactive.static_summary)
            forged_summary["paragraphs"] = paragraphs
            forged_display = copy.deepcopy(interactive.display)
            forged_display["staticSummary"] = copy.deepcopy(forged_summary)
            forged = replace(
                interactive,
                static_summary=forged_summary,
                display=forged_display,
            )
            with self.subTest(name=name):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.bundle_deck(
                        title=compiled.title,
                        lang=compiled.lang,
                        slides=(compiled.slides[0], forged),
                        assets=bundle.load_runtime_assets(),
                    )
                self.assertEqual(caught.exception.issues[0].code, "summary_mismatch")

    def test_bundle_reports_malformed_scene_values_as_stable_validation_errors(self) -> None:
        live_svg = bundle.validate_renderer_svg(LIVE_SVG, slide_ordinal=1, role="live-shell")
        for malformed in ([], "scene", 1):
            with self.subTest(malformed=malformed):
                with self.assertRaises(bundle.BundleValidationError) as caught:
                    bundle.bundle_deck(
                        title="Safe",
                        lang="en",
                        slides=(replace(static_slide(), scene=malformed, live_shell_svg=live_svg),),
                        assets=assets(),
                    )
                self.assertEqual(caught.exception.issues[0].code, "scene_shape")

    def test_dom_budget_is_preflighted_from_validated_svg_metadata(self) -> None:
        slide = static_slide()
        authentic_count = bundle._estimated_slide_elements(slide)
        with (
            mock.patch.object(bundle, "MAX_DOM_ELEMENTS_PER_SLIDE", authentic_count - 1),
            self.assertRaises(bundle.BundleValidationError) as caught,
        ):
            bundle.bundle_deck(title="Safe", lang="en", slides=(slide,), assets=assets())
        self.assertEqual(caught.exception.issues[0].code, "dom_limit")

    def test_dom_budget_counts_fixed_chrome_before_artifact_scanning(self) -> None:
        slide = static_slide()
        baseline = bundle.bundle_deck(title="Safe", lang="en", slides=(slide,), assets=assets())
        counter = _ElementCounter()
        counter.feed(baseline)
        counter.close()

        with mock.patch.object(bundle, "MAX_DOM_ELEMENTS", counter.count):
            self.assertEqual(
                bundle.bundle_deck(title="Safe", lang="en", slides=(slide,), assets=assets()),
                baseline,
            )

        with (
            mock.patch.object(bundle, "MAX_DOM_ELEMENTS", counter.count - 1),
            mock.patch.object(bundle, "assert_self_contained") as scanner,
            self.assertRaises(bundle.BundleValidationError) as caught,
        ):
            bundle.bundle_deck(title="Safe", lang="en", slides=(slide,), assets=assets())
        self.assertEqual(caught.exception.issues[0].code, "dom_limit")
        scanner.assert_not_called()

    def test_per_slide_dom_budget_excludes_fixed_document_chrome(self) -> None:
        slide = static_slide()
        html = bundle.bundle_deck(title="Safe", lang="en", slides=(slide,), assets=assets())
        with mock.patch.object(
            bundle,
            "MAX_DOM_ELEMENTS_PER_SLIDE",
            bundle._estimated_slide_elements(slide),
        ):
            codes = {issue.code for issue in bundle.inspect_self_contained(html, assets=assets())}
        self.assertNotIn("dom_limit", codes)

    def test_bundle_is_deterministic_escaped_hashed_and_self_contained(self) -> None:
        hostile = '</title><script>globalThis.pwned=1</script> & 日本語 \u2028'
        runtime = assets()
        html = bundle.bundle_deck(title=hostile, lang="en", slides=(static_slide(hostile),), assets=runtime)
        self.assertEqual(html, bundle.bundle_deck(title=hostile, lang="en", slides=(static_slide(hostile),), assets=runtime))
        self.assertEqual(bundle.inspect_self_contained(html, assets=runtime), ())
        capture = _Capture()
        capture.feed(html)
        self.assertEqual(capture.scripts, [runtime.js.decode("utf-8")])
        self.assertEqual(capture.styles, [runtime.css.decode("utf-8")])
        self.assertEqual(capture.titles, [hostile])
        self.assertNotIn("globalThis.pwned=1</script>", html)
        expected_script = base64.b64encode(hashlib.sha256(runtime.js).digest()).decode("ascii")
        expected_style = base64.b64encode(hashlib.sha256(runtime.css).digest()).decode("ascii")
        self.assertIn("script-src &#x27;sha256-" + expected_script + "&#x27;", html)
        self.assertIn("style-src &#x27;sha256-" + expected_style + "&#x27;", html)
        self.assertIn('<meta name="referrer" content="no-referrer">', html)

    def test_final_html_byte_limit_is_inclusive(self) -> None:
        runtime = assets()
        slide = static_slide()
        baseline = bundle.bundle_deck(title="Safe", lang="en", slides=(slide,), assets=runtime)
        exact = len(baseline.encode("utf-8"))
        with mock.patch.object(bundle, "MAX_HTML_BYTES", exact):
            self.assertEqual(
                bundle.bundle_deck(title="Safe", lang="en", slides=(slide,), assets=runtime),
                baseline,
            )
        with mock.patch.object(bundle, "MAX_HTML_BYTES", exact - 1):
            with self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.bundle_deck(title="Safe", lang="en", slides=(slide,), assets=runtime)
        self.assertEqual(caught.exception.issues[0].code, "html_limit")

    def test_scanner_reports_tampering_resources_and_forbidden_runtime_capabilities(self) -> None:
        runtime = assets()
        html = bundle.bundle_deck(title="Safe", lang="en", slides=(static_slide(),), assets=runtime)
        mutations = {
            "script_src": html.replace("<script>", '<script src="https://evil.example/x.js">', 1),
            "event_handler": html.replace("<main ", '<main onclick="alert(1)" ', 1),
            "image": html.replace("</main>", '<img src="https://evil.example/x.png"></main>', 1),
            "resource_attribute": html.replace(
                "</main>", '<map><area href="https://evil.example/navigate"></map></main>', 1,
            ),
            "slide_structure": html.replace('class="slide"', 'class="not-slide"', 1),
            "meta_refresh": html.replace("</head>", '<meta http-equiv="refresh" content="0;url=https://evil.example"></head>', 1),
            "tampered_script": html.replace("static-bootstrap", "static-tampered", 1),
            "html_nesting": html.removesuffix("</body>\n</html>\n"),
        }
        for expected_code, bad_html in mutations.items():
            with self.subTest(expected_code=expected_code):
                codes = {issue.code for issue in bundle.inspect_self_contained(bad_html, assets=runtime)}
                self.assertIn(expected_code, codes)

        spaced_refresh = html.replace(
            "</head>",
            '<meta http-equiv=" refresh " content="0;url=https://evil.example"></head>',
            1,
        )
        self.assertIn(
            "meta_refresh",
            {issue.code for issue in bundle.inspect_self_contained(spaced_refresh, assets=runtime)},
        )

        csp_meta = re.search(
            r'<meta http-equiv="Content-Security-Policy"[^>]+>\n',
            html,
        ).group(0)
        relocated_csp = html.replace(csp_meta, "", 1).replace(
            "</body>", csp_meta + "</body>", 1,
        )
        self.assertIn(
            "csp_mismatch",
            {issue.code for issue in bundle.inspect_self_contained(relocated_csp, assets=runtime)},
        )

        templated_csp = html.replace(csp_meta, "", 1).replace(
            "</head>", "</head><template><head>" + csp_meta + "</head></template>", 1,
        )
        self.assertIn(
            "csp_mismatch",
            {issue.code for issue in bundle.inspect_self_contained(templated_csp, assets=runtime)},
        )

        popup_local = html.replace(
            'href="#idrt-page-1"',
            'href="#idrt-page-1" target="_blank"',
            1,
        )
        self.assertIn(
            "local_link",
            {issue.code for issue in bundle.inspect_self_contained(popup_local, assets=runtime)},
        )

        attribution_local = html.replace(
            'href="#idrt-page-1"',
            'href="#idrt-page-1" attributionsrc="https://evil.example/register"',
            1,
        )
        self.assertIn(
            "resource_attribute",
            {issue.code for issue in bundle.inspect_self_contained(attribution_local, assets=runtime)},
        )

        envelope_node = re.search(
            r'(<div id="idrt-deck-data" hidden data-encoding="base64url-json-v1">)([A-Za-z0-9_-]+)(</div>)',
            html,
        )
        moved_envelope = html.replace(
            envelope_node.group(0),
            envelope_node.group(1) + envelope_node.group(3) + "<div>" + envelope_node.group(2) + "</div>",
            1,
        )
        self.assertIn(
            "envelope_node",
            {issue.code for issue in bundle.inspect_self_contained(moved_envelope, assets=runtime)},
        )

        noscript_envelope = html.replace(
            envelope_node.group(0),
            "<noscript>" + envelope_node.group(0) + "</noscript>",
            1,
        )
        self.assertIn(
            "envelope_node",
            {issue.code for issue in bundle.inspect_self_contained(noscript_envelope, assets=runtime)},
        )

        svg_anchor = html.replace(
            "</main>", '<svg><a href="#idrt-page-1">not a source</a></svg></main>', 1,
        )
        self.assertIn(
            "svg_anchor",
            {issue.code for issue in bundle.inspect_self_contained(svg_anchor, assets=runtime)},
        )

        from scripts import build_interactive_deck
        from tests.test_build_interactive_deck import make_fixture

        with tempfile.TemporaryDirectory() as directory:
            scene_html = build_interactive_deck.build_deck(make_fixture(Path(directory)))
        source_anchor = re.search(
            r'<a data-slide-ordinal="2" data-source-id="method-note"[^>]*>[^<]*</a>',
            scene_html,
        ).group(0)
        moved_source = scene_html.replace(source_anchor, "<span>Illustrative method note</span>", 1)
        first_nav = '<nav class="nojs-page-links" aria-label="Slide links">'
        moved_source = moved_source.replace(
            first_nav,
            '<section class="slide"><details class="evidence-container"><summary>Evidence</summary>'
            + source_anchor
            + "</details></section>"
            + first_nav,
            1,
        )
        moved_codes = {
            issue.code
            for issue in bundle.inspect_self_contained(
                moved_source,
                assets=bundle.load_runtime_assets(),
                allowed_sources={(2, "method-note"): "https://example.com/method"},
            )
        }
        self.assertIn("source_link", moved_codes)

        for token in (
            "fetch('/x')", "new XMLHttpRequest()", "new WebSocket('wss://x')", "eval('1')",
            "new Function('')", "postMessage('x','*')", "window.location = '#x'",
            "location.href = 'https://evil.example'", "window.location.href = '#x'",
            "window.location.hash = '#slide=1'",
            "document.createElement('form').submit()", "document.createElement('a').click()",
            "document.createElement('script')", "new BroadcastChannel('x')",
            "globalThis['fetch']('https://evil.example')", "window['open']('https://evil.example')",
            "document['write']('x')", "document['createElement']('script')",
            "location['href']='https://evil.example'", "globalThis\\u005b'fetch'\\u005d('/x')",
            "window.location.replace('https://evil.example')",
        ):
            hostile_assets = bundle.RuntimeAssets(css=runtime.css, js=("(function(){" + token + "}());\n").encode())
            with self.subTest(token=token), self.assertRaises(bundle.BundleValidationError) as caught:
                bundle.bundle_deck(title="Safe", lang="en", slides=(static_slide(),), assets=hostile_assets)
            self.assertIn("forbidden_runtime_capability", {issue.code for issue in caught.exception.issues})

        generated_replace = bundle.RuntimeAssets(
            css=runtime.css,
            js=(
                b'(function(){var state={},deck={};'
                b'var target=URL_STATE.serialize(state,deck);'
                b'history.replaceState(null,"",window.location.pathname+'
                b'window.location.search+target);window.location.replace(target);}());\n'
            ),
        )
        with self.assertRaises(bundle.BundleValidationError) as caught:
            bundle.bundle_deck(
                title="Safe",
                lang="en",
                slides=(static_slide(),),
                assets=generated_replace,
            )
        self.assertIn(
            "forbidden_runtime_capability",
            {issue.code for issue in caught.exception.issues},
        )

        malformed_href = html.replace('href="#idrt-page-1"', 'href="https://["', 1)
        issues = bundle.inspect_self_contained(malformed_href, assets=runtime)
        self.assertIn("source_link", {issue.code for issue in issues})

    def test_runtime_boot_and_navigation_guards_are_transactional_and_ancestry_aware(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")

        ancestry_start = source.index("function interactiveTarget(target)")
        ancestry_end = source.index("function interactiveEvent(event)", ancestry_start)
        ancestry_guard = source[ancestry_start:ancestry_end]
        self.assertIn("while (node && node.nodeType === 1)", ancestry_guard)
        self.assertIn('node.getAttribute("role")', ancestry_guard)
        self.assertIn("node = node.parentElement", ancestry_guard)
        self.assertNotIn('target.closest("[role]")', ancestry_guard)

        preflight = source.index('Object.getOwnPropertyDescriptor(window, "InteractiveDeck")')
        create = source.index("CONTROLLER.create(deck, scheduler)")
        temporary_api = source.index("configurable: true", create)
        ready = source.index("controller.ready()", temporary_api)
        locked_api = source.index("configurable: false", ready)
        rollback = source.index("delete window.InteractiveDeck", locked_api)
        self.assertLess(preflight, create)
        self.assertLess(create, temporary_api)
        self.assertLess(temporary_api, ready)
        self.assertLess(ready, locked_api)
        self.assertLess(locked_api, rollback)

    def test_runtime_reducer_keeps_a_closed_presenter_overlay_stack(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        reducer = source[
            source.index("  var STATE = (function () {") : source.index(
                "  var URL_STATE = (function () {"
            )
        ]
        javascript = r"""
function invariant(condition, code) { if (!condition) { throw new Error(code); } }
function plain(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
var MODEL = { evaluate: function () { throw new Error("unexpected evaluation"); } };
var DECIMAL = {};
""" + reducer + r"""
var deck = {slides: [{id: "one", ordinal: 1, runtime: null}, {id: "two", ordinal: 2, runtime: null}]};
var state = Object.freeze({currentIndex: 0, pages: new Map([["one", null], ["two", null]]), overlays: Object.freeze([]), reducedMotion: false});
state = STATE.reduce(state, {type: "OPEN_PRESENTER_OVERLAY", kind: "overview"}, deck);
state = STATE.reduce(state, {type: "OPEN_PRESENTER_OVERLAY", kind: "help"}, deck);
var stacked = state.overlays.map(function (item) { return item.kind; });
state = STATE.reduce(state, {type: "CLOSE_TOP_OVERLAY"}, deck);
var revealed = state.overlays.map(function (item) { return item.kind; });
state = STATE.reduce(state, {type: "NAVIGATE", index: 1}, deck);
console.log(JSON.stringify([stacked, revealed, state.overlays.length, state.currentIndex]));
"""
        result = subprocess.run(
            ["node", "-e", javascript],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            [["overview", "help"], ["overview"], 0, 1],
        )

    def test_runtime_reset_restores_a_declared_initial_evidence_overlay(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        reducer = source[
            source.index("  var STATE = (function () {") : source.index(
                "  var URL_STATE = (function () {"
            )
        ]
        javascript = r"""
function invariant(condition, code) { if (!condition) { throw new Error(code); } }
function plain(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
var MODEL = { evaluate: function (_runtime, inputs) { return Object.freeze({mode: inputs.get("evidence")}); } };
""" + reducer + r"""
var slide = {
  id: "proof", ordinal: 1,
  runtime: {scene: {type: "evidence_only", initialState: {evidence: "sources"}, evidence: {sources: [{}], assumptions: []}}}
};
var deck = {slides: [slide]};
var page = Object.freeze({
  inputs: new Map([["evidence", "closed"]]), evaluation: Object.freeze({mode: "closed"}),
  viewMode: "live", failed: null
});
var state = Object.freeze({currentIndex: 0, pages: new Map([["proof", page]]), overlays: Object.freeze([]), reducedMotion: false});
state = STATE.reduce(state, {type: "RESET_PAGE"}, deck);
var afterReset = [state.pages.get("proof").inputs.get("evidence"), state.overlays.map(function (item) { return [item.kind, item.ordinal, item.tab]; })];
state = STATE.reduce(state, {type: "CLOSE_TOP_OVERLAY"}, deck);
var afterClose = [state.pages.get("proof").inputs.get("evidence"), state.overlays.length];
state = STATE.reduce(state, {type: "RESET_PAGE"}, deck);
var afterReplay = [state.pages.get("proof").inputs.get("evidence"), state.overlays.map(function (item) { return [item.kind, item.ordinal, item.tab]; })];
console.log(JSON.stringify([afterReset, afterClose, afterReplay]));
"""
        result = subprocess.run(
            ["node", "-e", javascript],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                ["sources", [["evidence", 1, "sources"]]],
                ["closed", 0],
                ["sources", [["evidence", 1, "sources"]]],
            ],
        )

    def test_runtime_scheduler_injection_is_consumed_before_controller_boot(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        start = source.index("  function resolveScheduler()")
        end = source.index("  var scheduler = Object.freeze", start)
        resolver = source[start:end]
        javascript = r"""
function invariant(condition, code) { if (!condition) { throw new Error(code); } }
function plain(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
var calls = [];
var injected = {
  now: function () { return 7; },
  setTimeout: function (callback, delay) { calls.push(["set", delay]); callback(); return 11; },
  clearTimeout: function (handle) { calls.push(["clear", handle]); },
  requestAnimationFrame: function (callback) { calls.push(["raf"]); callback(7); return 12; },
  cancelAnimationFrame: function (handle) { calls.push(["cancel", handle]); }
};
var window = {
  __IDRT_TEST_SCHEDULER__: injected,
  setTimeout: function () {}, clearTimeout: function () {},
  requestAnimationFrame: function () {}, cancelAnimationFrame: function () {}
};
var performance = {now: function () { return 0; }};
""" + resolver + r"""
var scheduler = resolveScheduler();
scheduler.setTimeout(function () { calls.push(["ran"]); }, 5);
console.log(JSON.stringify([scheduler.now(), calls, Object.prototype.hasOwnProperty.call(window, "__IDRT_TEST_SCHEDULER__")]));
"""
        result = subprocess.run(
            ["node", "-e", javascript],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout), [7, [["set", 5], ["ran"]], False])

    def test_runtime_scheduler_injection_requires_an_exact_consumable_own_record(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        start = source.index("  function resolveScheduler()")
        end = source.index("  var scheduler = Object.freeze", start)
        resolver = source[start:end]
        javascript = r"""
function invariant(condition, code) { if (!condition) { throw new Error(code); } }
function plain(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function methods() {
  return {
    now: function () { return 7; },
    setTimeout: function () { return 1; },
    clearTimeout: function () {},
    requestAnimationFrame: function () { return 2; },
    cancelAnimationFrame: function () {}
  };
}
function nativeWindow() {
  return {
    setTimeout: function () {}, clearTimeout: function () {},
    requestAnimationFrame: function () {}, cancelAnimationFrame: function () {}
  };
}
var performance = {now: function () { return 0; }};
var window;
""" + resolver + r"""
function run(factory) {
  window = factory();
  try {
    resolveScheduler();
    return ["accepted", Object.prototype.hasOwnProperty.call(window, "__IDRT_TEST_SCHEDULER__"), "__IDRT_TEST_SCHEDULER__" in window];
  } catch (failure) {
    return [failure.message, Object.prototype.hasOwnProperty.call(window, "__IDRT_TEST_SCHEDULER__"), "__IDRT_TEST_SCHEDULER__" in window];
  }
}
var results = [];
results.push(run(function () {
  var value = nativeWindow();
  Object.defineProperty(value, "__IDRT_TEST_SCHEDULER__", {value: methods(), configurable: true});
  return value;
}));
results.push(run(function () {
  var value = nativeWindow();
  Object.defineProperty(value, "__IDRT_TEST_SCHEDULER__", {value: methods(), configurable: false});
  return value;
}));
results.push(run(function () {
  var prototype = {};
  Object.defineProperty(prototype, "__IDRT_TEST_SCHEDULER__", {value: methods(), configurable: true});
  return Object.assign(Object.create(prototype), nativeWindow());
}));
results.push(run(function () {
  var inheritedMethod = Object.create({now: function () { return 7; }});
  Object.assign(inheritedMethod, methods());
  delete inheritedMethod.now;
  inheritedMethod.extra = function () {};
  var value = nativeWindow();
  Object.defineProperty(value, "__IDRT_TEST_SCHEDULER__", {value: inheritedMethod, configurable: true});
  return value;
}));
results.push(run(function () {
  var inheritedExtra = Object.create({extra: true});
  Object.assign(inheritedExtra, methods());
  var value = nativeWindow();
  Object.defineProperty(value, "__IDRT_TEST_SCHEDULER__", {value: inheritedExtra, configurable: true});
  return value;
}));
results.push(run(function () {
  var withSymbol = methods();
  withSymbol[Symbol("extra")] = true;
  var value = nativeWindow();
  Object.defineProperty(value, "__IDRT_TEST_SCHEDULER__", {value: withSymbol, configurable: true});
  return value;
}));
console.log(JSON.stringify(results));
"""
        result = subprocess.run(
            ["node", "-e", javascript],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                ["accepted", False, False],
                ["E_TEST_SCHEDULER", True, True],
                ["E_TEST_SCHEDULER", False, True],
                ["E_TEST_SCHEDULER", False, False],
                ["E_TEST_SCHEDULER", False, False],
                ["E_TEST_SCHEDULER", False, False],
            ],
        )

    def test_runtime_focus_trap_selects_only_the_top_noninert_overlay(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        navigation = source[
            source.index("  var NAVIGATION = (function () {") : source.index(
                "  var CONTROLLER = (function () {"
            )
        ]
        self.assertIn(
            '.presenter-dialog:not([hidden]):not([inert]),.evidence-dialog:not([hidden]):not([inert])',
            navigation,
        )

    def test_demo_cancellation_invalidates_only_demo_touched_scene_rafs(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        controller = source[
            source.index("  var CONTROLLER = (function () {") : source.index(
                "  function resolveScheduler()"
            )
        ]
        cancel_demo = controller[
            controller.index("      function cancelDemo(") : controller.index(
                "      function slideIndexById("
            )
        ]
        self.assertIn("demoTouchedOrdinals.forEach", cancel_demo)
        self.assertIn("cancelOrdinal(ordinal)", cancel_demo)
        self.assertIn("demoTouchedOrdinals.clear()", cancel_demo)
        self.assertNotIn("slideIndex < deck.slides.length", cancel_demo)

    def test_demo_completion_cancels_touched_scene_async_work_before_overview(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        controller = source[
            source.index("  var CONTROLLER = (function () {") : source.index(
                "  function resolveScheduler()"
            )
        ]
        advance = controller[
            controller.index("        function advance()") : controller.index(
                "      function focusNeedsRepair("
            )
        ]
        completion = advance[
            advance.index("          if (cursor >= sequence.length)") : advance.index(
                "          var item = sequence[cursor]"
            )
        ]
        for cleanup in (
            "demoTouchedOrdinals.forEach",
            "cancelOrdinal(ordinal)",
            "settleDemoGeometry(ordinal)",
            "demoTouchedOrdinals.clear()",
        ):
            self.assertIn(cleanup, completion)
        self.assertLess(
            completion.index("cancelOrdinal(ordinal)"),
            completion.index("demoTouchedOrdinals.clear()"),
        )
        self.assertLess(
            completion.index("demoTouchedOrdinals.clear()"),
            completion.index('openPresenterOverlay("overview", demoControl)'),
        )

    def test_scheduled_demo_failure_cleans_owned_work_before_failing_the_scene(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        controller = source[
            source.index("  var CONTROLLER = (function () {") : source.index(
                "  function resolveScheduler()"
            )
        ]
        self.assertIn("function guardDemoAdvance(", controller)
        fail_guard = controller[
            controller.index("      function guardDemoAdvance(") : controller.index(
                "      function scheduleDemo(", controller.index("      function guardDemoAdvance(")
            )
        ]
        for cleanup in (
            "demoGeneration += 1",
            "demoActive = false",
            'demoControl.setAttribute("aria-pressed", "false")',
            "clearDemoTimers()",
            "demoTouchedOrdinals.forEach",
            "cancelOrdinal(ordinal)",
            "renderedGeometry.delete(ordinal)",
            "demoTouchedOrdinals.clear()",
            "hideDemoCue()",
        ):
            self.assertIn(cleanup, fail_guard)
        self.assertLess(fail_guard.index("hideDemoCue()"), fail_guard.index("failScene("))

        scheduler = controller[
            controller.index("      function scheduleDemo(") : controller.index(
                "      function settleDemoGeometry("
            )
        ]
        self.assertIn("guardDemoAdvance(", scheduler)

        advance = controller[
            controller.index("        function advance()") : controller.index(
                "      function focusNeedsRepair("
            )
        ]
        self.assertLess(advance.index("applyDemoAction(item.slide, action)"), advance.index('demoEvent("deck:demo-step", detail)'))
        post_action_recheck = advance.index(
            "positionDemoCue(item.slide, step.targetKey, true)",
            advance.index("applyDemoAction(item.slide, action)"),
        )
        self.assertLess(post_action_recheck, advance.index('demoEvent("deck:demo-step", detail)'))

    def test_runtime_state_commits_only_after_synchronous_render_succeeds(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        controller = source[
            source.index("  var CONTROLLER = (function () {") : source.index(
                "  var scheduler = Object.freeze"
            )
        ]
        dispatch = controller[
            controller.index("      function dispatch(") : controller.index(
                "      function navigate("
            )
        ]
        self.assertIn("var candidate = STATE.reduce(state, action, deck);", dispatch)
        self.assertIn("state = candidate;", dispatch)
        self.assertIn("state = previous;", dispatch)
        self.assertLess(dispatch.index("render(previous"), dispatch.index("writeUrl()"))
        self.assertLess(dispatch.index("writeUrl()"), dispatch.index('emit("deck:state")'))

        restore = controller[
            controller.index("      function restore(hash, write)") : controller.index(
                "      function closeTooltip("
            )
        ]
        self.assertIn("var candidate = state;", restore)
        self.assertIn("candidate = STATE.reduce(candidate", restore)
        self.assertIn("state = previous;", restore)
        self.assertLess(restore.index("render(null"), restore.index("writeUrl()"))
        self.assertLess(restore.index("render(null"), restore.index('emit("deck:state")'))

    def test_runtime_source_link_policy_matches_the_compiler_policy(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        self.assertIn("function safeSourceUrl(value)", source)
        self.assertIn("scalarLength(value, \"E_SOURCE_URL\") > 2048", source)
        self.assertNotIn("value.length > 2048", source)
        self.assertIn(
            "source.linked === safeSourceUrl(own(source, \"url\") ? source.url : null)",
            source,
        )
        self.assertNotIn("source.linked === own(source, \"url\")", source)

        scalar_helper = source[
            source.index("  function scalarLength(value, code)") : source.index(
                "  function text(value, code, maximum)"
            )
        ]
        url_helpers = source[
            source.index("    function unsafeUrlCharacters(value)") : source.index(
                "    function unitId(value, code)"
            )
        ]
        urls = [
            "https://.",
            "https://[v1.foo]",
            "https://example.com/source",
            "https://example.com/" + ("🩺" * 1020),
            "https://192.0.2.1/source",
            "https://[2001:db8::1]/source",
        ]
        expected = [False, False, True, True, True, True]
        self.assertEqual([bool(bundle.safe_source_url(url)) for url in urls], expected)
        javascript = (
            'function invariant(condition, code) { if (!condition) { throw new Error(code); } }\n'
            + scalar_helper
            + url_helpers
            + "console.log(JSON.stringify(JSON.parse(process.argv[1]).map(safeSourceUrl)));\n"
        )
        result = subprocess.run(
            ["node", "-e", javascript, json.dumps(urls, ensure_ascii=False)],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout), expected)

    def test_external_hash_restore_emits_one_success_event_only_for_a_valid_change(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        restore = source[
            source.index("      function restore(hash, write)") : source.index(
                "      function bind()"
            )
        ]
        self.assertIn("var before = URL_STATE.serialize(state, deck);", restore)
        self.assertIn(
            'if (!write && parsed.valid && URL_STATE.serialize(state, deck) !== before) {\n          emit("deck:state");\n        }',
            restore,
        )
        self.assertLess(restore.index("render(null"), restore.index('emit("deck:state")'))

        hash_handler = source[
            source.index('        window.addEventListener("hashchange"') : source.index(
                "      try {", source.index('        window.addEventListener("hashchange"')
            )
        ]
        self.assertLess(hash_handler.index("pendingHash === currentHash"), hash_handler.index("restore(currentHash, false)"))
        self.assertLess(hash_handler.index("return;"), hash_handler.index("restore(currentHash, false)"))

    def test_malformed_non_slide_fragment_resets_the_raw_target_scene(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        url_state = source[
            source.index("  var URL_STATE = (function () {") : source.index(
                "  var VIEW = (function () {"
            )
        ]
        javascript = """
function invariant(condition, code) { if (!condition) { throw new Error(code); } }
var DECIMAL = {
  canonical: function (value) { return String(value); },
  parse: function (value) { return value; },
  snap: function (value) { if (!/^[0-9]+$/.test(value)) { throw new Error("E_DECIMAL"); } return value; }
};
""" + url_state + """
var deck = { slides: [
  { id: "static", runtime: null },
  { id: "scene", runtime: { control: { id: "automation" }, scene: { initialState: { automation: "20" }, scale: 0 } } }
] };
var hashes = JSON.parse(process.argv[1]);
var results = hashes.map(function (hash) {
  var parsed = URL_STATE.parse(hash, deck);
  return {
    index: parsed.index,
    valid: parsed.valid,
    mode: parsed.mode,
    value: parsed.values ? parsed.values.get("automation") : null
  };
});
console.log(JSON.stringify(results));
"""
        hashes = [
            "#slide=2&automation=%",
            "#slide=%&automation=35",
            "#slide=2&slide=1&automation=35",
            "#slide=2&automation=35",
            "#" + "&".join(["slide=2"] + [f"x{index}=1" for index in range(10)]),
            "#slide=2&x=" + ("a" * 4090),
            "#2",
            "#idrt-page-2",
            "#1",
        ]
        result = subprocess.run(
            ["node", "-e", javascript, json.dumps(hashes)],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            [
                {"index": 1, "valid": False, "mode": "live", "value": "20"},
                {"index": 0, "valid": False, "mode": "live", "value": None},
                {"index": 1, "valid": False, "mode": "live", "value": "20"},
                {"index": 1, "valid": True, "mode": "live", "value": "35"},
                {"index": 0, "valid": False, "mode": "live", "value": None},
                {"index": 0, "valid": False, "mode": "live", "value": None},
                {"index": 1, "valid": True, "mode": "live", "value": "20"},
                {"index": 1, "valid": True, "mode": "live", "value": "20"},
                {"index": 0, "valid": True, "mode": "live", "value": None},
            ],
        )

    def test_runtime_panel_validator_matches_compiler_optional_and_required_states(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        validator = source[
            source.index("    function validateTask5Scene(") : source.index(
                "    function validateStateSpace("
            )
        ]
        javascript = """
function invariant(condition, code) { if (!condition) { throw new Error(code); } }
function exactKeys(value) { return value; }
function integer(value) { return value; }
function nonEmptyText(value) { return value; }
function validateEvidence() { return {}; }
function validateTask5Fallback() {}
function plain(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function validateTask5TargetsAndSteps() { return {targets: new Map(), gotoIds: Object.freeze([]), waitMs: 0}; }
function validateTask5Narration() {}
function boundedArray(value) { return value; }
function safeId(value) { return value; }
function textArray(value) { return value; }
function booleanValue(value, code) { invariant(typeof value === "boolean", code); return value; }
function deepFreeze(value) { return value; }
""" + validator + """
function scene(type, allowNone, panel) {
  var states = {panels: [
    {id: "one", label: "L".repeat(64), heading: "One heading", body: "One body", sourceRefs: []},
    {id: "two", label: "Two", heading: "Two heading", body: "Two body", sourceRefs: []}
  ]};
  if (type === "accordion") { states.allowNone = allowNone; }
  else { states.parentSummary = "Parent"; states.returnLabel = "Back"; }
  return {
    version: 1, slideId: "slide", type: type, locale: "en", scale: 0,
    purpose: "Inspect one panel", decisionJob: "insight", interactionRationale: "Inspect detail",
    initialState: {panel: panel}, printState: {panel: panel}, controls: [], quantities: {},
    outputDefinitions: {}, evidence: {}, invariants: {}, fallback: {matched: true, pattern: "bullet_list"},
    targets: {}, steps: [], narration: {}, initialEvaluation: {outputs: {}, view: null}, states: states
  };
}
var results = [];
results.push(validateTask5Scene(scene("drilldown", true, "one"), "slide", "en", 1).acceptedStates);
results.push(validateTask5Scene(scene("accordion", false, "one"), "slide", "en", 1).acceptedStates);
try {
  validateTask5Scene(scene("accordion", false, null), "slide", "en", 1);
  results.push("accepted-invalid");
} catch (failure) { results.push(failure.message); }
console.log(JSON.stringify(results));
"""
        result = subprocess.run(
            ["node", "-e", javascript],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(result.stdout), [3, 2, "E_INITIAL_STATE"])

    def test_runtime_ranked_view_bounds_and_uniqueness_match_bundle(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        validator = source[
            source.index("    function validateTask5View(") : source.index(
                "    function validateTask5Model("
            )
        ]
        javascript = r"""
function invariant(condition, code) { if (!condition) { throw new Error(code); } }
function plain(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }
function own(value, key) { return Object.prototype.hasOwnProperty.call(value, key); }
function exactKeys(value, required, optional, code) {
  invariant(plain(value), code);
  var allowed = required.concat(optional);
  for (var index = 0; index < required.length; index += 1) { invariant(own(value, required[index]), code); }
  Object.keys(value).forEach(function (key) { invariant(allowed.indexOf(key) >= 0, code); });
  return value;
}
function boundedArray(value, maximum, code, minimum) {
  invariant(Array.isArray(value) && value.length <= maximum && value.length >= (minimum || 0), code);
  return value;
}
function safeId(value, code) { invariant(typeof value === "string" && value.length > 0, code); return value; }
function nonEmptyText(value, code) { invariant(typeof value === "string" && value.length > 0, code); return value; }
function booleanValue(value, code) { invariant(typeof value === "boolean", code); return value; }
function integer(value, minimum, maximum, code) { invariant(Number.isInteger(value) && value >= minimum && value <= maximum, code); return value; }
function decimalAny(value, code) { invariant(typeof value === "string", code); return value; }
function validateTypedValue() {}
function text() {}
""" + validator + r"""
function ranked(ranks) {
  return {component: "ranked_list", items: ranks.map(function (rank, index) {
    return {id: "item-" + index, label: "Item " + index, rank: rank, emphasis: false, removed: false};
  })};
}
var results = [];
[[1, 2], [1, 1], [1, 3]].forEach(function (ranks) {
  try { validateTask5View(ranked(ranks), 0, true, "E_VIEW_SHAPE"); results.push("accepted"); }
  catch (failure) { results.push(failure.message); }
});
console.log(JSON.stringify(results));
"""
        result = subprocess.run(
            ["node", "-e", javascript],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(result.stdout),
            ["accepted", "E_VIEW_SHAPE", "E_VIEW_SHAPE"],
        )

    def test_runtime_dot_animation_reuses_prior_geometry_by_item_id(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        controller = source[
            source.index("  var CONTROLLER = (function () {") : source.index(
                "  var scheduler = Object.freeze"
            )
        ]
        self.assertIn("function pointWithId(points, id)", controller)
        self.assertIn("id: points[index].id", controller)
        self.assertIn("pointWithId(rendered, points[index].id)", controller)
        self.assertIn("pointWithId(previous.evaluation.points, points[index].id)", controller)
        self.assertNotIn("previous.evaluation.points[index]", controller)

    def test_runtime_repaints_visual_emphasis_and_resets_tooltips_on_page_change(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        paint = source[
            source.index("    function paintSvgView(") : source.index(
                "    function paintView("
            )
        ]
        self.assertIn('liveSvgId("LiveLabel", barItem.id, barIndex)', paint)
        self.assertIn('barItem.emphasis ? "600" : "normal"', paint)
        self.assertIn('barMark.setAttribute("y",', paint)
        self.assertIn('barName.setAttribute("y",', paint)
        self.assertIn('barLabel.setAttribute("y",', paint)
        self.assertIn('rankItem.emphasis ? "600" : "normal"', paint)
        self.assertIn('point.highlight ? "9" : "7"', paint)
        self.assertIn("livePrimaryColor(slide.runtime.scene)", paint)
        self.assertIn('point.highlight ? "600" : "normal"', paint)

        view = source[
            source.index("    function paintView(") : source.index(
                "    function paintPanels("
            )
        ]
        self.assertIn('node.setAttribute("data-emphasis"', view)
        self.assertIn('removal.hidden = !item.removed', view)
        self.assertIn('removal.textContent = slide.runtime.scene.locale', view)
        self.assertIn('dom.semanticView.appendChild(node)', view)

        controller = source[
            source.index("  var CONTROLLER = (function () {") : source.index(
                "  var scheduler = Object.freeze"
            )
        ]
        navigate = controller[
            controller.index("      function navigate(") : controller.index(
                "      function closeOverlay("
            )
        ]
        restore = controller[
            controller.index("      function restore(") : controller.index(
                "      function closeTooltip("
            )
        ]
        self.assertIn("closeTooltip(false);", navigate)
        self.assertIn("closeTooltip(false);", restore)

    def test_runtime_reuses_compiler_display_text_for_literal_view_slots(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        evaluator = source[
            source.index("  var MODEL = (function () {") : source.index(
                "  var STATE = (function () {"
            )
        ]
        self.assertIn("function initialResolvedViewRow(scene, component, id)", evaluator)
        self.assertIn("var initialRow = initialResolvedViewRow(scene, authored.component, source.id);", evaluator)
        self.assertIn("row[slotName + \"Text\"] = initialRow[slotName + \"Text\"];", evaluator)

    def test_semantic_view_prebuilds_reversible_removal_marker(self) -> None:
        scene = {
            "locale": "en",
            "initialEvaluation": {
                "view": {
                    "component": "ranked_list",
                    "items": [{
                        "id": "north",
                        "label": "North",
                        "rank": 1,
                        "metricText": "",
                        "emphasis": True,
                        "removed": False,
                    }],
                }
            },
        }
        markup = bundle._semantic_view_html(scene, 2)
        self.assertIn('data-emphasis="true"', markup)
        self.assertIn('<span data-view-removal hidden>removed</span>', markup)

    def test_external_hash_navigation_repairs_focus_only_when_it_becomes_unsafe(self) -> None:
        source = bundle.load_runtime_assets().js.decode("utf-8")
        controller = source[
            source.index("  var CONTROLLER = (function () {") : source.index(
                "  var scheduler = Object.freeze"
            )
        ]
        self.assertIn("function focusNeedsRepair()", controller)
        self.assertIn("var previousIndex = state.currentIndex;", controller)
        self.assertIn(
            "if (!write && (parsed.index !== previousIndex || focusNeedsRepair())) {",
            controller,
        )
        self.assertIn("domById.get(slide.id).heading.focus();", controller)

        restore = controller[
            controller.index("      function restore(hash, write)") : controller.index(
                "      function bind()"
            )
        ]
        self.assertLess(restore.index("render(null"), restore.index("focusNeedsRepair()"))
        self.assertLess(restore.index("heading.focus()"), restore.index('emit("deck:state")'))

    def test_runtime_verifier_allows_bounded_registry_syntax_but_rejects_computed_capabilities(self) -> None:
        safe_runtime = bundle.RuntimeAssets(
            css=assets().css,
            js=(
                b'(function(){"use strict";var rows=[1,2];var registry=new Map();'
                b'for(var index=0;index<rows.length;index+=1){registry.set(String(index),rows[index]);}'
                b'document.documentElement.setAttribute("data-size",String(registry.size));}());\n'
            ),
        )
        html_text = bundle.bundle_deck(
            title="Safe", lang="en", slides=(static_slide(),), assets=safe_runtime,
        )
        self.assertEqual(bundle.inspect_self_contained(html_text, assets=safe_runtime), ())

        for hostile in (
            b'(function(){globalThis["fetch"]("/x");}());\n',
            b'(function(){window["open"]("https://evil.example");}());\n',
            b'(function(){document["write"]("x");}());\n',
            b'(function(){location["href"]="https://evil.example";}());\n',
            b'(function(){globalThis\\u005b"fetch"\\u005d("/x");}());\n',
        ):
            with self.subTest(hostile=hostile), self.assertRaises(bundle.BundleValidationError):
                bundle.bundle_deck(
                    title="Safe",
                    lang="en",
                    slides=(static_slide(),),
                    assets=bundle.RuntimeAssets(css=assets().css, js=hostile),
                )

    def test_scanner_requires_one_exact_direct_head_referrer_policy(self) -> None:
        runtime = assets()
        html = bundle.bundle_deck(title="Safe", lang="en", slides=(static_slide(),), assets=runtime)
        meta = '<meta name="referrer" content="no-referrer">\n'
        mutations = (
            html.replace(meta, "", 1),
            html.replace(meta, meta + meta, 1),
            html.replace(meta, "", 1).replace("</body>", meta + "</body>", 1),
            html.replace(meta, '<meta name="referrer" content="unsafe-url">\n', 1),
            html.replace(meta, '<meta name="referrer" content="no-referrer" data-extra="x">\n', 1),
            html.replace(meta, '<meta name="viewport" content="no-referrer">\n', 1),
        )
        for index, mutated in enumerate(mutations):
            with self.subTest(index=index):
                codes = {issue.code for issue in bundle.inspect_self_contained(mutated, assets=runtime)}
                self.assertIn("referrer_mismatch", codes)

    def test_scanner_requires_the_exact_browser_document_root_and_head_order(self) -> None:
        runtime = assets()
        html_text = bundle.bundle_deck(
            title="Safe",
            lang="en",
            slides=(static_slide(),),
            assets=runtime,
        )
        top_level_prefixes = (
            "<div></div>",
            "<p>x</p>",
            "<body></body>",
            "<head></head>",
            "X",
            "&lt;x&gt;",
        )
        mutations = [prefix + html_text for prefix in top_level_prefixes]
        root_prefixes = ("<div></div>", "<p>x</p>", "X", '<meta charset="utf-8">')
        mutations.extend(
            html_text.replace('<html lang="en">\n', '<html lang="en">\n' + prefix, 1)
            for prefix in root_prefixes
        )
        mutations.extend((
            html_text.replace("<head>", "<head>X", 1),
            html_text.replace("<head>", "<head>&lt;x&gt;", 1),
            html_text + "<div></div>",
            html_text.replace("<!DOCTYPE html>", "", 1),
            "<!DOCTYPE html>" + html_text,
        ))
        for index, tampered in enumerate(mutations):
            with self.subTest(index=index):
                codes = {
                    issue.code
                    for issue in bundle.inspect_self_contained(tampered, assets=runtime)
                }
                self.assertIn("html_root", codes)

    def test_scanner_short_circuits_html_and_dom_budgets(self) -> None:
        runtime = assets()
        html = bundle.bundle_deck(title="Safe", lang="en", slides=(static_slide(),), assets=runtime)
        with mock.patch.object(bundle, "MAX_HTML_BYTES", len(html.encode("utf-8")) - 1):
            issues = bundle.inspect_self_contained(html, assets=runtime)
        self.assertEqual([(issue.code, issue.location) for issue in issues], [("html_limit", "<html>")])

        many_elements = "<div>" * 100 + "</div>" * 100
        with mock.patch.object(bundle, "MAX_DOM_ELEMENTS", 1):
            issues = bundle.inspect_self_contained(many_elements, assets=runtime)
        self.assertEqual(sum(issue.code == "dom_limit" for issue in issues), 1)

    def test_runtime_assets_reject_closing_tags_bom_and_crlf(self) -> None:
        bad_assets = (
            bundle.RuntimeAssets(css=b"x{}\r\n", js=b"(function(){}());\n"),
            bundle.RuntimeAssets(css=b"x{}\n", js=b"\xef\xbb\xbf(function(){}());\n"),
            bundle.RuntimeAssets(css=b"</style>\n", js=b"(function(){}());\n"),
            bundle.RuntimeAssets(css=b"x{}\n", js=b"</script>\n"),
        )
        for runtime in bad_assets:
            with self.subTest(runtime=runtime), self.assertRaises(bundle.BundleValidationError):
                bundle.bundle_deck(title="Safe", lang="en", slides=(static_slide(),), assets=runtime)


if __name__ == "__main__":
    unittest.main()
