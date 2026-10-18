from __future__ import annotations

import copy
import base64
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock
import struct
import zlib

from scripts import _interactive_audit as audit
from scripts import audit_interactive_deck as cli
from scripts import build_interactive_deck as builder
from tests.test_build_interactive_deck import make_fixture


@dataclass(frozen=True)
class _Witness:
    state: tuple[tuple[str, object], ...]
    distance: Decimal = Decimal("0")
    outcome: str = "met"


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        len(payload).to_bytes(4, "big")
        + kind
        + payload
        + (zlib.crc32(kind + payload) & 0xFFFFFFFF).to_bytes(4, "big")
    )


def _rgb_png(*, level: int) -> bytes:
    width, height = 2, 1
    rows = b"\x00\x10\x20\x30\x40\x50\x60"
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(rows, level))
        + _png_chunk(b"IEND", b"")
    )


def _expected(state: dict[str, object], *, output: str = "0", outcome: str | None = None) -> dict:
    return {
        "inputs": {key: str(value) if value is not None else None for key, value in state.items()},
        "outputs": {"result": output},
        "outcome": outcome,
        "viewMode": "live",
    }


def _author_state(name: str, state: dict[str, object], **extra: object) -> dict:
    return {"name": name, "state": state, "expected": _expected(state), **extra}


def _record(scene: dict, states: list[dict], *, accepted: int = 1,
            witnesses: dict | None = None, classifications: dict | None = None,
            boundaries: tuple = (), missing: tuple = ()) -> SimpleNamespace:
    return SimpleNamespace(
        compiled=scene,
        audit=SimpleNamespace(
            accepted_state_count=accepted,
            witnesses=witnesses or {},
            missing_outcomes=missing,
            classifications=classifications or {},
            boundaries=boundaries,
        ),
        fallback_check={"matched": True, "component": scene.get("type")},
        audit_states=tuple(states),
        source_locations={"ignored": "/private/path/that/must/not/ship"},
    )


def _base_scene(slide_id: str, kind: str, initial: dict[str, object]) -> dict:
    return {
        "version": 1,
        "slideId": slide_id,
        "type": kind,
        "locale": "en",
        "initialState": initial,
        "printState": dict(initial),
        "controls": [],
        "quantities": {},
        "outputDefinitions": {},
        "evidence": {"sources": [], "assumptions": [], "leaves": [], "badge": ""},
        "fallback": {"matched": True},
        "targets": {
            "evidence:open": {"kind": "evidence"},
            "evidence:close": {"kind": "evidence"},
            "static:toggle": {"kind": "static"},
        },
        "steps": [],
        "initialEvaluation": {"outputs": {}, "view": None},
    }


def _six_scene_deck(*, hostile_title: str = "Audit fixture") -> SimpleNamespace:
    scenes: list[dict] = []
    records: list[SimpleNamespace] = []

    evidence = _base_scene("evidence", "evidence_only", {"evidence": "closed"})
    evidence["evidence"] = {
        "sources": [{"id": "source-a", "label": "</script><img onerror=1>", "linked": True}],
        "assumptions": [{"id": "assumption-a", "label": "Synthetic", "value": "Only"}],
        "leaves": [],
        "badge": "illustrative",
    }
    evidence["targets"]["source:source-a"] = {"kind": "source", "id": "source-a"}
    scenes.append(evidence)
    records.append(_record(evidence, [
        _author_state("initial", {"evidence": "closed"}),
        _author_state("evidence:sources", {"evidence": "sources"}),
        _author_state("evidence:assumptions", {"evidence": "assumptions"}),
        _author_state("evidence:both", {"evidence": "both"}),
    ], accepted=4))

    toggle = _base_scene("toggle", "state_toggle", {"scenario": "base"})
    toggle["controls"] = [{
        "id": "scenario", "kind": "segmented", "label": "Scenario",
        "options": [{"value": "base", "label": "Base"}, {"value": "stress", "label": "Stress"}],
    }]
    toggle["targets"]["control:scenario"] = {"kind": "control", "id": "scenario"}
    toggle["model"] = {"kind": "state_map"}
    toggle["states"] = [{"id": "base"}, {"id": "stress"}]
    scenes.append(toggle)
    records.append(_record(toggle, [
        _author_state("initial", {"scenario": "base"}),
        _author_state("option:scenario:stress", {"scenario": "stress"}),
    ], accepted=2))

    slider = _base_scene("slider", "slider_model", {"x": "5"})
    slider["controls"] = [{"id": "x", "kind": "range", "label": "Input", "min": "0", "max": "10", "step": "5", "quantity": "value"}]
    slider["targets"]["control:x"] = {"kind": "control", "id": "x"}
    slider["model"] = {
        "kind": "piecewise",
        "input": "x",
        "segments": [
            {"min": {"value": "0"}, "max": {"value": "5"}},
            {"min": {"value": "5"}, "max": {"value": "10"}},
        ],
    }
    slider["decisionContract"] = {"id": "gate"}
    slider["steps"] = [
        {"stepKey": "raise", "action": {"type": "set", "control": "x", "value": "10"}, "targetKey": "control:x"},
        {"stepKey": "pause", "action": {"type": "wait", "ms": 10}},
    ]
    slider_states = [
        _author_state("initial", {"x": "5"}, expected=_expected({"x": "5"}, output="5", outcome="met")),
        _author_state("range:x:min", {"x": "0"}, expected=_expected({"x": "0"}, output="0", outcome="notMet")),
        _author_state("range:x:max", {"x": "10"}, expected=_expected({"x": "10"}, output="10", outcome="met")),
        _author_state("decision:notMet", {"x": "0"}, expected=_expected({"x": "0"}, output="0", outcome="notMet")),
        _author_state("decision:met", {"x": "5"}, expected=_expected({"x": "5"}, output="5", outcome="met")),
        _author_state("decision:exact", {"x": "5"}, expected=_expected({"x": "5"}, output="5", outcome="met")),
        _author_state("boundary:x:0:exact", {"x": "0"}, expected=_expected({"x": "0"}, output="0", outcome="notMet")),
        _author_state("boundary:x:0:above", {"x": "5"}, expected=_expected({"x": "5"}, output="5", outcome="met")),
        _author_state("boundary:x:5:below", {"x": "0"}, expected=_expected({"x": "0"}, output="0", outcome="notMet")),
        _author_state("boundary:x:5:exact", {"x": "5"}, expected=_expected({"x": "5"}, output="5", outcome="met")),
        _author_state("boundary:x:5:above", {"x": "10"}, expected=_expected({"x": "10"}, output="10", outcome="met")),
        _author_state("boundary:x:10:below", {"x": "5"}, expected=_expected({"x": "5"}, output="5", outcome="met")),
        _author_state("boundary:x:10:exact", {"x": "10"}, expected=_expected({"x": "10"}, output="10", outcome="met")),
        _author_state("step:raise", {"x": "10"}, expected=_expected({"x": "10"}, output="10", outcome="met")),
    ]
    scenes.append(slider)
    records.append(_record(
        slider,
        slider_states,
        accepted=3,
        witnesses={
            "notMet": _Witness((("x", Decimal("0")),), Decimal("-5"), "notMet"),
            "met": _Witness((("x", Decimal("5")),), Decimal("0"), "met"),
            "exact": _Witness((("x", Decimal("5")),), Decimal("0"), "met"),
        },
        boundaries=(
            (("x", Decimal("0"), "exact"), (("x", Decimal("0")),)),
            (("x", Decimal("0"), "above"), (("x", Decimal("5")),)),
            (("x", Decimal("5"), "below"), (("x", Decimal("0")),)),
            (("x", Decimal("5"), "exact"), (("x", Decimal("5")),)),
            (("x", Decimal("5"), "above"), (("x", Decimal("10")),)),
            (("x", Decimal("10"), "below"), (("x", Decimal("5")),)),
            (("x", Decimal("10"), "exact"), (("x", Decimal("10")),)),
        ),
    ))

    score = _base_scene("score", "score_model", {"a": "low", "b": "low"})
    score["controls"] = [
        {"id": key, "kind": "toggle", "label": key.upper(), "options": [{"value": "low", "label": "Low"}, {"value": "high", "label": "High"}]}
        for key in ("a", "b")
    ]
    score["targets"].update({f"control:{key}": {"kind": "control", "id": key} for key in ("a", "b")})
    score["model"] = {"kind": "score_sum", "bands": [
        {"id": "early", "min": {"value": "0"}, "max": {"value": "3"}, "label": "Early"},
        {"id": "ready", "min": {"value": "3"}, "max": {"value": "5"}, "label": "Ready"},
    ]}
    score["decisionContract"] = {"id": "score-gate"}
    scenes.append(score)
    records.append(_record(
        score,
        [
            _author_state("initial", {"a": "low", "b": "low"}),
            _author_state("decision:notMet", {"a": "low", "b": "low"}, expected=_expected({"a": "low", "b": "low"}, outcome="notMet")),
            _author_state("decision:met", {"a": "high", "b": "low"}, expected=_expected({"a": "high", "b": "low"}, outcome="met")),
            _author_state("classification:Early", {"a": "low", "b": "low"}),
            _author_state("classification:Ready", {"a": "high", "b": "low"}),
            _author_state("option:a:high", {"a": "high", "b": "low"}),
            _author_state("option:b:high", {"a": "low", "b": "high"}),
        ],
        accepted=4,
        witnesses={
            "notMet": _Witness((("a", "low"), ("b", "low")), Decimal("-3"), "notMet"),
            "met": _Witness((("a", "high"), ("b", "low")), Decimal("0"), "met"),
        },
        classifications={
            "Early": (("a", "low"), ("b", "low")),
            "Ready": (("a", "high"), ("b", "low")),
        },
    ))

    drill = _base_scene("drill", "drilldown", {"panel": None})
    drill["states"] = {"panels": [
        {"id": "method", "label": "Method", "heading": "Method", "body": "Body", "sourceRefs": []},
        {"id": "risk", "label": "Risk", "heading": "Risk", "body": "Body", "sourceRefs": []},
    ], "parentSummary": "Parent", "returnLabel": "Back"}
    for panel_id in ("method", "risk"):
        drill["targets"][f"panel:{panel_id}"] = {"kind": "panel", "id": panel_id}
        drill["targets"][f"panel:{panel_id}:close"] = {"kind": "panelClose", "id": panel_id}
    scenes.append(drill)
    records.append(_record(drill, [
        _author_state("initial", {"panel": None}),
        _author_state("panel:method", {"panel": "method"}),
        _author_state("panel:risk", {"panel": "risk"}),
    ], accepted=3))

    accordion = _base_scene("accordion", "accordion", {"panel": None})
    accordion["states"] = {"panels": [
        {"id": "one", "label": "One", "heading": "One", "body": "Body", "sourceRefs": []},
        {"id": "two", "label": "Two", "heading": "Two", "body": "Body", "sourceRefs": []},
    ], "allowNone": True}
    for panel_id in ("one", "two"):
        accordion["targets"][f"panel:{panel_id}"] = {"kind": "panel", "id": panel_id}
        accordion["targets"][f"panel:{panel_id}:close"] = {"kind": "panelClose", "id": panel_id}
    scenes.append(accordion)
    records.append(_record(accordion, [
        _author_state("initial", {"panel": None}),
        _author_state("panel:one", {"panel": "one"}),
        _author_state("panel:two", {"panel": "two"}),
    ], accepted=3))

    slides = tuple(SimpleNamespace(
        slide_id=scene["slideId"],
        scene=scene,
        headline=f'{scene["slideId"]} headline',
        source="Illustrative",
    ) for scene in scenes)
    return SimpleNamespace(
        title=hostile_title,
        lang="en",
        slides=slides,
        author_records=tuple(records),
    )


class AuditPlannerTests(unittest.TestCase):
    def test_real_compiler_author_records_feed_plan_without_entering_audience_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = make_fixture(Path(temporary))
            compiled = builder.compile_manifest(manifest)
            plan = audit.compile_audit_plan(compiled)
            maximum = next(
                state for state in plan.ledger["states"]
                if state["slideId"] == "queue-capacity" and "range:automation:max" in state["obligations"]
            )
            self.assertEqual(maximum["expected"]["inputs"], {"automation": "80"})
            self.assertEqual(maximum["expected"]["outputs"], {"capacity": "50"})
            for obligation in ("static", "reduced-motion", "overview-after-change"):
                matches = [state for state in plan.ledger["states"] if obligation in state["obligations"]]
                self.assertEqual(len(matches), 1, obligation)
            audience = builder.bundle_deck(
                title=compiled.title,
                lang=compiled.lang,
                slides=compiled.slides,
                assets=builder.load_runtime_assets(),
            )
            self.assertNotIn("acceptedStateCount", audience)
            self.assertNotIn("range:automation:max", audience)

    def test_all_six_scene_types_have_canonical_deduplicated_obligations(self) -> None:
        plan = audit.compile_audit_plan(_six_scene_deck())
        self.assertLess(len(plan.ledger["states"]), audit.MAX_AUDIT_SCREENSHOTS)
        self.assertEqual(plan.ledger["proof"]["acceptedStateCount"], 19)
        self.assertEqual(
            {slide["sceneType"] for slide in plan.ledger["slides"]},
            {"evidence_only", "state_toggle", "slider_model", "score_model", "drilldown", "accordion"},
        )
        obligations = {
            obligation
            for state in plan.ledger["states"]
            for obligation in state["obligations"]
        }
        self.assertTrue({
            "initial", "print", "static", "reduced-motion", "overview-after-change",
            "evidence:sources", "evidence:assumptions", "evidence:both",
            "option:scenario:stress", "range:x:min", "range:x:max",
            "boundary:x:5:below", "boundary:x:5:exact", "boundary:x:5:above",
            "classification:Early", "classification:Ready",
            "decision:notMet", "decision:met", "decision:exact",
            "panel:method", "panel:risk", "panel:one", "panel:two",
            "step:raise",
        } <= obligations)
        initial = next(
            state for state in plan.ledger["states"]
            if state["slideId"] == "slider" and "initial" in state["obligations"]
        )
        self.assertIn("print", initial["obligations"])
        special = {
            "static": lambda state: state["fragment"].endswith("mode=static"),
            "reduced-motion": lambda state: state["setup"] == [{"action": "emulateReducedMotion"}],
            "overview-after-change": lambda state: state["setup"][-1:] == [{"action": "openOverview"}],
        }
        for obligation, predicate in special.items():
            matches = [state for state in plan.ledger["states"] if obligation in state["obligations"]]
            self.assertEqual(len(matches), 6, obligation)
            self.assertTrue(all(predicate(state) for state in matches), obligation)
        evidence_overview = next(
            state for state in plan.ledger["states"]
            if state["slideId"] == "evidence" and "overview-after-change" in state["obligations"]
        )
        self.assertEqual(evidence_overview["fragment"], "#slide=1&evidence=sources")
        self.assertEqual(evidence_overview["setup"], [{"action": "openOverview"}])
        keys = [state["stateKey"] for state in plan.ledger["states"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys, sorted(keys, key=lambda key: plan.state_order[key]))

    def test_evidence_both_is_restored_by_url_without_being_overwritten(self) -> None:
        plan = audit.compile_audit_plan(_six_scene_deck())
        both = next(
            state for state in plan.ledger["states"]
            if state["slideId"] == "evidence" and "evidence:both" in state["obligations"]
        )
        self.assertEqual(both["fragment"], "#slide=1&evidence=both")
        self.assertEqual(both["setup"], [])
        self.assertEqual(
            both["expected"]["authorProbe"],
            {
                "categoricalInputs": {},
                "panel": None,
                "evidenceMode": "both",
                "overlay": {"kind": "evidence", "ordinal": 1, "tab": "sources"},
                "overviewOpen": False,
                "failed": None,
            },
        )

        coverage_by_target = {
            row["targetKey"]: row for row in plan.ledger["targetCoverage"]
            if row["slideId"] == "evidence"
        }
        states_by_key = {state["stateKey"]: state for state in plan.ledger["states"]}
        for target_key in ("evidence:close", "source:source-a"):
            target_state = states_by_key[coverage_by_target[target_key]["stateKey"]]
            self.assertEqual(target_state["fragment"], "#slide=1&evidence=sources")
            self.assertEqual(
                target_state["setup"],
                [{"action": "assertTarget", "targetKey": target_key}],
            )

    def test_step_and_target_coverage_are_separate_and_sources_are_presence_only(self) -> None:
        plan = audit.compile_audit_plan(_six_scene_deck())
        step_keys = {entry["stepKey"] for entry in plan.ledger["stepCoverage"]}
        target_keys = {entry["targetKey"] for entry in plan.ledger["targetCoverage"]}
        self.assertEqual(step_keys, {"raise", "pause"})
        self.assertIn("control:x", target_keys)
        self.assertNotIn("raise", target_keys)
        self.assertNotIn("control:x", step_keys)
        source = next(entry for entry in plan.ledger["targetCoverage"] if entry["targetKey"] == "source:source-a")
        self.assertEqual(source["coverageMode"], "presence")
        for state in plan.ledger["states"]:
            self.assertNotIn("activateSource", {step["action"] for step in state["setup"]})

    def test_full_mathematical_proof_is_separate_from_selected_screenshots(self) -> None:
        deck = _six_scene_deck()
        deck.author_records[3].audit.accepted_state_count = 65_000
        plan = audit.compile_audit_plan(deck)
        self.assertEqual(plan.ledger["proof"]["acceptedStateCount"], 65_015)
        self.assertLess(len(plan.ledger["states"]), 512)

    def test_missing_classification_witness_and_uncovered_control_target_fail(self) -> None:
        deck = _six_scene_deck()
        del deck.author_records[2].audit.witnesses["exact"]
        with self.assertRaises(audit.AuditError) as caught:
            audit.compile_audit_plan(deck)
        self.assertEqual(caught.exception.code, "missing_witness")

        deck = _six_scene_deck()
        deck.author_records[3].audit.classifications.pop("Ready")
        with self.assertRaises(audit.AuditError) as caught:
            audit.compile_audit_plan(deck)
        self.assertEqual(caught.exception.code, "missing_witness")

        deck = _six_scene_deck()
        del deck.author_records[2].compiled["targets"]["control:x"]
        with self.assertRaises(audit.AuditError) as caught:
            audit.compile_audit_plan(deck)
        self.assertEqual(caught.exception.code, "uncovered_target")

    def test_missing_reachable_piecewise_boundary_and_unmatched_fallback_fail(self) -> None:
        deck = _six_scene_deck()
        deck.author_records[2].audit.boundaries = tuple(
            entry for entry in deck.author_records[2].audit.boundaries
            if entry[0] != ("x", Decimal("5"), "exact")
        )
        with self.assertRaises(audit.AuditError) as caught:
            audit.compile_audit_plan(deck)
        self.assertEqual(caught.exception.code, "missing_witness")

        deck = _six_scene_deck()
        deck.author_records[2].fallback_check["matched"] = False
        with self.assertRaises(audit.AuditError) as caught:
            audit.compile_audit_plan(deck)
        self.assertEqual(caught.exception.code, "static_parity")

    def test_duplicate_state_keys_and_unreconstructable_setup_fail(self) -> None:
        with mock.patch.object(audit, "_state_key", return_value="duplicate"):
            with self.assertRaises(audit.AuditError) as caught:
                audit.compile_audit_plan(_six_scene_deck())
        self.assertEqual(caught.exception.code, "duplicate_state_key")

        deck = _six_scene_deck()
        deck.author_records[0].audit_states += ({
            "name": "bad-setup", "state": {"evidence": "closed"},
            "expected": _expected({"evidence": "closed"}),
            "setup": [{"action": "runCode", "value": "alert(1)"}],
        },)
        with self.assertRaises(audit.AuditError) as caught:
            audit.compile_audit_plan(deck)
        self.assertEqual(caught.exception.code, "unreconstructable_setup")

    def test_budget_fails_before_browser_work(self) -> None:
        with self.assertRaises(audit.AuditError) as caught:
            audit.preflight_screenshot_budget(513)
        self.assertEqual(caught.exception.code, "audit_limit")


class DeterministicArtifactTests(unittest.TestCase):
    def test_png_canonicalizer_removes_encoder_compression_variance(self) -> None:
        fast = _rgb_png(level=1)
        compact = _rgb_png(level=9)
        self.assertNotEqual(fast, compact)
        page = mock.Mock()
        page.evaluate.return_value = base64.b64encode(compact).decode("ascii")
        self.assertEqual(cli._canonicalize_png(page, fast), compact)
        encoded_argument = page.evaluate.call_args.args[1]
        self.assertEqual(base64.b64decode(encoded_argument), fast)

    def test_ledger_atlas_and_contact_sheet_are_byte_deterministic_and_script_free(self) -> None:
        plan_a = audit.compile_audit_plan(_six_scene_deck(hostile_title='</script><script>alert(1)</script>'))
        plan_b = audit.compile_audit_plan(_six_scene_deck(hostile_title='</script><script>alert(1)</script>'))
        self.assertEqual(audit.ledger_bytes(plan_a.ledger), audit.ledger_bytes(plan_b.ledger))
        atlas_a = audit.render_state_atlas(plan_a.ledger)
        atlas_b = audit.render_state_atlas(plan_b.ledger)
        contact = audit.render_contact_sheet(plan_a.ledger)
        self.assertEqual(atlas_a, atlas_b)
        for document in (atlas_a, contact):
            lowered = document.lower()
            self.assertNotIn("<script", lowered)
            self.assertNotIn("onerror=", lowered)
            self.assertIn("content-security-policy", lowered)
            self.assertIn("img-src 'self' data:", document)
            self.assertIn("&lt;/script&gt;", document)
        ledger_text = audit.ledger_bytes(plan_a.ledger).decode("utf-8")
        for forbidden in ("/private/path", "timestamp", "nonce", "traceback"):
            self.assertNotIn(forbidden, ledger_text.lower())

    def test_atlas_and_contact_sheet_use_only_the_allowlisted_deck_language(self) -> None:
        deck = _six_scene_deck()
        deck.lang = "ja"
        plan = audit.compile_audit_plan(deck)
        self.assertIn('<html lang="ja">', audit.render_state_atlas(plan.ledger))
        self.assertIn('<html lang="ja">', audit.render_contact_sheet(plan.ledger))

        invalid = json.loads(audit.ledger_bytes(plan.ledger))
        invalid["deck"]["lang"] = 'ja" onload="alert(1)'
        with self.assertRaises(audit.AuditError) as caught:
            audit.render_state_atlas(invalid)
        self.assertEqual(caught.exception.code, "invalid_ledger")

    def test_observed_reconstruction_contract_is_serialized_without_host_paths(self) -> None:
        plan = audit.compile_audit_plan(_six_scene_deck())
        state = plan.ledger["states"][0]
        observed = {
            "sanitizedSnapshot": {"currentSlide": state["ordinal"], "pages": []},
            "authorProbe": {
                "categoricalInputs": {},
                "panel": None,
                "evidenceMode": "closed",
                "overlay": None,
                "overviewOpen": False,
                "failed": None,
            },
            "semanticDigest": "a" * 64,
            "pngSha256": "b" * 64,
            "runtimeReady": True,
            "networkRequests": [],
            "consoleErrors": [],
            "targetHitBoxes": {},
            "staticParity": True,
        }
        finalized = audit.attach_reconstruction(plan.ledger, state["stateKey"], observed)
        record = next(item for item in finalized["states"] if item["stateKey"] == state["stateKey"])
        self.assertEqual(record["reconstruction"], observed)
        self.assertNotIn(str(Path.cwd()), audit.ledger_bytes(finalized).decode("utf-8"))


class SafeOutputTests(unittest.TestCase):
    def test_unknown_destination_files_symlinks_and_parent_escape_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "audit"
            destination.mkdir()
            (destination / "unknown.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(audit.AuditError) as caught:
                audit.validate_audit_destination(destination)
            self.assertEqual(caught.exception.code, "unsafe_output")
            self.assertEqual((destination / "unknown.txt").read_text(encoding="utf-8"), "keep")

            symlink = root / "linked-audit"
            symlink.symlink_to(destination, target_is_directory=True)
            with self.assertRaises(audit.AuditError) as caught:
                audit.validate_audit_destination(symlink)
            self.assertEqual(caught.exception.code, "unsafe_output")

            real_parent = root / "real-parent"
            (real_parent / "nested").mkdir(parents=True)
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            with self.assertRaises(audit.AuditError) as caught:
                audit.validate_audit_destination(linked_parent / "nested" / "audit")
            self.assertEqual(caught.exception.code, "unsafe_output")

            with self.assertRaises(audit.AuditError) as caught:
                audit.validate_audit_destination(root / "child" / ".." / "escaped")
            self.assertEqual(caught.exception.code, "unsafe_output")

    def test_known_output_can_be_replaced_atomically_from_sibling_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "audit"
            destination.mkdir()
            (destination / "audit-ledger.json").write_text("old", encoding="utf-8")
            (destination / "screenshots").mkdir()
            (destination / "screenshots" / "old.png").write_bytes(b"old")
            staging = root / ".audit.stage-test"
            staging.mkdir()
            (staging / "audit-ledger.json").write_text("new", encoding="utf-8")
            (staging / "state-atlas.html").write_text("atlas", encoding="utf-8")
            (staging / "contact-sheet.html").write_text("sheet", encoding="utf-8")
            (staging / "contact-sheet.png").write_bytes(b"png")
            (staging / "screenshots").mkdir()
            (staging / "screenshots" / "state.png").write_bytes(b"state")
            audit.publish_audit_directory(staging, destination)
            self.assertEqual((destination / "audit-ledger.json").read_text(encoding="utf-8"), "new")
            self.assertFalse(staging.exists())
            self.assertFalse((destination / "screenshots" / "old.png").exists())


class AuditCliTests(unittest.TestCase):
    def test_capture_stabilizer_forces_presenter_chrome_idle(self) -> None:
        page = mock.Mock()
        cli._stabilize_capture_ui(page)
        page.evaluate.assert_called_once()
        script = page.evaluate.call_args.args[0]
        self.assertIn("idrt-presenter-chrome", script)
        self.assertIn("classList.add('is-idle')", script)

    @staticmethod
    def _successful_browser(deck_path: Path, ledger: dict, staging: Path,
                            chromium_executable: Path | None = None) -> dict:
        assert deck_path.name.endswith(".interactive.html")
        assert chromium_executable is None or isinstance(chromium_executable, Path)
        screenshots = staging / "screenshots"
        screenshots.mkdir()
        finalized = ledger
        for state in ledger["states"]:
            png = b"\x89PNG\r\n\x1a\n" + state["stateKey"].encode("ascii")
            (staging / state["screenshot"]).write_bytes(png)
            observed = {
                "sanitizedSnapshot": {"currentSlide": state["ordinal"], "pages": []},
                "authorProbe": state["expected"]["authorProbe"],
                "semanticDigest": "a" * 64,
                "pngSha256": __import__("hashlib").sha256(png).hexdigest(),
                "runtimeReady": True,
                "networkRequests": [],
                "consoleErrors": [],
                "targetHitBoxes": {},
                "staticParity": True,
            }
            finalized = audit.attach_reconstruction(finalized, state["stateKey"], observed)
        (staging / "contact-sheet.png").write_bytes(b"\x89PNG\r\n\x1a\ncontact")
        return finalized

    def test_run_audit_compiles_once_publishes_exact_outputs_and_keeps_deck_temporary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "deck.json"
            manifest.write_text("{}", encoding="utf-8")
            destination = root / "audit"
            compiled = _six_scene_deck()
            with mock.patch.object(cli.builder, "compile_manifest", return_value=compiled) as compile_manifest, \
                 mock.patch.object(cli.builder, "bundle_deck", return_value="<html>deck</html>"):
                result = cli.run_audit(
                    manifest,
                    destination,
                    browser_runner=self._successful_browser,
                )
            self.assertEqual(result, destination.absolute())
            compile_manifest.assert_called_once_with(manifest)
            self.assertEqual(
                {entry.name for entry in destination.iterdir()},
                {"audit-ledger.json", "state-atlas.html", "contact-sheet.html", "contact-sheet.png", "screenshots"},
            )
            self.assertFalse(any(entry.name.endswith(".interactive.html") for entry in destination.iterdir()))
            ledger = json.loads((destination / "audit-ledger.json").read_text(encoding="utf-8"))
            self.assertTrue(all("reconstruction" in state for state in ledger["states"]))

    def test_browser_failure_leaves_no_final_or_partial_directory(self) -> None:
        def fail_browser(*_args: object, **_kwargs: object) -> dict:
            raise audit.AuditError("browser_unavailable")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "deck.json"
            manifest.write_text("{}", encoding="utf-8")
            destination = root / "audit"
            with mock.patch.object(cli.builder, "compile_manifest", return_value=_six_scene_deck()), \
                 mock.patch.object(cli.builder, "bundle_deck", return_value="<html>deck</html>"), \
                 self.assertRaises(audit.AuditError) as caught:
                cli.run_audit(manifest, destination, browser_runner=fail_browser)
            self.assertEqual(caught.exception.code, "browser_unavailable")
            self.assertFalse(destination.exists())
            self.assertFalse(any(entry.name.startswith(".audit.stage-") for entry in root.iterdir()))

    def test_closed_setup_dispatches_targets_without_activating_sources(self) -> None:
        page = mock.Mock()
        locator = page.locator.return_value
        locator.count.return_value = 1
        cli._click_target(page, "slide-one", "evidence:open")
        locator.dispatch_event.assert_called_once_with("click")
        locator.click.assert_not_called()

        with self.assertRaises(audit.AuditError) as caught:
            cli._click_target(page, "slide-one", "source:reference-one")
        self.assertEqual(caught.exception.code, "source_activation_forbidden")

    def test_evidence_tab_selection_is_scoped_visible_and_confirmed(self) -> None:
        page = mock.Mock()
        locator = mock.Mock()
        page.locator.return_value = locator
        locator.count.return_value = 1
        locator.is_visible.return_value = True
        locator.get_attribute.return_value = "true"
        cli._apply_setup(
            page,
            {
                "slideId": "slide-one",
                "ordinal": 3,
                "setup": [{"action": "selectEvidenceTab", "tab": "assumptions"}],
            },
        )
        page.locator.assert_called_once_with(
            '#idrt-evidence-dialog-3[data-slide-ordinal="3"]:not([hidden]) '
            '[data-evidence-tab="assumptions"]'
        )
        locator.dispatch_event.assert_called_once_with("click")

        locator.is_visible.return_value = False
        with self.assertRaises(audit.AuditError) as caught:
            cli._apply_setup(
                page,
                {
                    "slideId": "slide-one",
                    "ordinal": 3,
                    "setup": [{"action": "selectEvidenceTab", "tab": "sources"}],
                },
            )
        self.assertEqual(caught.exception.code, "target_missing")

    def test_overview_setup_dispatches_the_shortcut_from_a_non_widget_root(self) -> None:
        page = mock.Mock()
        root = page.locator.return_value
        cli._apply_setup(
            page,
            {
                "slideId": "evidence",
                "ordinal": 1,
                "setup": [{"action": "openOverview"}],
            },
        )
        page.locator.assert_called_once_with("html")
        root.dispatch_event.assert_called_once_with(
            "keydown",
            {"key": "o", "code": "KeyO", "altKey": True},
        )
        page.keyboard.press.assert_not_called()

    def test_author_probe_closes_the_public_snapshot_input_gap_symmetrically(self) -> None:
        state = {
            "ordinal": 1,
            "setup": [],
            "expected": {
                "inputs": {"scenario": "stress"},
                "outputs": {},
                "outcome": None,
                "viewMode": "live",
                "authorProbe": {
                    "categoricalInputs": {"scenario": "stress"},
                    "panel": None,
                    "evidenceMode": None,
                    "overlay": None,
                    "overviewOpen": False,
                    "failed": None,
                },
            },
        }
        snapshot = {
            "currentSlide": 1,
            "pages": [{
                "inputs": {}, "outputs": {}, "outcome": None,
                "viewMode": "live", "failed": None,
            }],
            "overlay": None,
            "reducedMotion": False,
        }
        with self.assertRaises(audit.AuditError) as caught:
            cli._assert_expected(snapshot, state)
        self.assertEqual(caught.exception.code, "reconstruction_mismatch")

        cli._assert_expected(snapshot, state, author_probe=state["expected"]["authorProbe"])
        wrong = copy.deepcopy(state["expected"]["authorProbe"])
        wrong["overviewOpen"] = True
        with self.assertRaises(audit.AuditError) as caught:
            cli._assert_expected(snapshot, state, author_probe=wrong)
        self.assertEqual(caught.exception.code, "reconstruction_mismatch")

    def test_reduced_motion_witness_must_match_the_public_snapshot(self) -> None:
        state = {
            "ordinal": 1,
            "setup": [{"action": "emulateReducedMotion"}],
            "expected": {"inputs": {}, "outputs": {}, "outcome": None, "viewMode": "live"},
        }
        snapshot = {
            "currentSlide": 1,
            "pages": [{"inputs": {}, "outputs": {}, "outcome": None, "viewMode": "live"}],
            "reducedMotion": False,
        }
        with self.assertRaises(audit.AuditError) as caught:
            cli._assert_expected(snapshot, state)
        self.assertEqual(caught.exception.code, "reconstruction_mismatch")
        snapshot["reducedMotion"] = True
        cli._assert_expected(snapshot, state)

    def test_main_has_stable_exit_codes_and_never_prints_raw_browser_errors(self) -> None:
        stderr = __import__("io").StringIO()
        with __import__("contextlib").redirect_stderr(stderr):
            self.assertEqual(cli.main([]), 2)
        self.assertEqual(stderr.getvalue(), "ERROR: interactive audit failed [cli_usage]\n")

        stderr = __import__("io").StringIO()
        with mock.patch.object(cli, "run_audit", side_effect=audit.AuditError("browser_failed")), \
             __import__("contextlib").redirect_stderr(stderr):
            self.assertEqual(cli.main(["--manifest", "deck.json", "--audit-out", "audit"]), 1)
        self.assertEqual(stderr.getvalue(), "ERROR: interactive audit failed [browser_failed]\n")


if __name__ == "__main__":
    unittest.main()
