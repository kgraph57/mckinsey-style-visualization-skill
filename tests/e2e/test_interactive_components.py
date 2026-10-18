"""Task 5 browser contracts for the complete interactive component set.

Expected values are authored literals or hand-calculated fixture results.  The
tests intentionally do not call the Python evaluator to predict browser output.
"""
from __future__ import annotations

import copy
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from base import (
    BUILD_SCRIPT,
    ROOT,
    InteractiveDeckBrowserTestCase,
    _write_exact_json,
    decode_envelope_text,
    replace_envelope_text,
)


PROVENANCE = {"basis": "illustrative", "assumptionRefs": ["synthetic-inputs"]}
LONG_RANK_ALPHA = "ranked-alpha-" + "a" * 48
LONG_RANK_BETA = "ranked-beta-" + "b" * 49
LONG_DOT_ALPHA = "dot-alpha-" + "a" * 50
LONG_DOT_BETA = "dot-beta-" + "b" * 51


def _assumptions() -> list[dict]:
    return [{
        "id": "synthetic-inputs",
        "label": "All values are synthetic",
        "value": "Browser fixture only",
    }]


def _numeric_common(scene_type: str, purpose: str, rationale: str) -> dict:
    return {
        "version": 1,
        "type": scene_type,
        "purpose": purpose,
        "decisionJob": "decision" if scene_type in ("slider_model", "score_model") else "insight",
        "interactionRationale": rationale,
        "quantities": {
            "value": {"dimension": "scalar", "unit": "one", "display": "units"},
        },
        "assumptions": _assumptions(),
    }


def _literal(value: Decimal | int) -> dict:
    return {
        "value": value,
        "quantity": "value",
        "provenance": copy.deepcopy(PROVENANCE),
    }


def _decision(threshold: Decimal | int, *, met: tuple[str, str], unmet: tuple[str, str]) -> dict:
    return {
        "id": "fixture-gate",
        "metric": {"ref": "output:result"},
        "operator": "gte",
        "threshold": {
            "value": threshold,
            "quantity": "value",
            "provenance": copy.deepcopy(PROVENANCE),
        },
        "whenMet": {"status": met[0], "recommendation": met[1]},
        "whenNotMet": {"status": unmet[0], "recommendation": unmet[1]},
    }


def _bar_static(
    *,
    headline: str,
    page: int,
    value: Decimal | int,
    value_text: str,
    domain_max: Decimal | int,
    threshold: Decimal | int,
    status: str,
    recommendation: str,
) -> dict:
    return {
        "pattern": "gap",
        "headline": headline,
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "quantity": "value",
        "unit": "units",
        "value_domain": [0, domain_max],
        "baseline": 0,
        "items": [{
            "item_id": "result",
            "label": "Result",
            "value": value,
            "value_text": value_text,
            "emphasis": True,
            "removed": False,
        }],
        "interactive_result": {
            "quantity": "value",
            "value": value,
            "decision_status": status,
            "recommendation": recommendation,
            "operator": "gte",
            "threshold": threshold,
        },
        "annotation": (
            f"Result {value_text}; {status}; threshold ≥ {threshold} units; {recommendation}"
        ),
    }


def _dot_static(
    *,
    headline: str,
    page: int,
    x: Decimal | int,
    y: Decimal | int,
    x_max: Decimal | int,
    y_max: Decimal | int,
    y_text: str,
    threshold: Decimal | int,
    status: str,
    recommendation: str,
) -> dict:
    def tick(value: Decimal | int) -> str:
        return f"{value} units"

    return {
        "pattern": "scatter",
        "headline": headline,
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "x_axis": {
            "label": "Input",
            "quantity": "value",
            "unit": "units",
            "domain": [0, x_max],
            "tick_labels": [tick(0), tick(x_max)],
        },
        "y_axis": {
            "label": "Result",
            "quantity": "value",
            "unit": "units",
            "domain": [0, y_max],
            "tick_labels": [tick(0), tick(y_max)],
        },
        "points": [{
            "item_id": "result-point",
            "label": "Result",
            "x": x,
            "y": y,
            "emphasis": True,
        }],
        "interactive_result": {
            "quantity": "value",
            "value": y,
            "decision_status": status,
            "recommendation": recommendation,
            "operator": "gte",
            "threshold": threshold,
        },
        "annotation": (
            f"Result {y_text}; {status}; threshold ≥ {threshold} units; {recommendation}"
        ),
    }


def _evidence_only_scene() -> dict:
    return {
        "version": 1,
        "type": "evidence_only",
        "purpose": "Keep the proof adjacent to the operating recommendation",
        "decisionJob": "fact",
        "interactionRationale": "Verify the source and the synthetic assumption without leaving the page",
        "initialState": {"evidence": "closed"},
        "printState": {"evidence": "closed"},
        "fallbackSummary": {
            "field": "headline",
            "text": "The operating recommendation is backed by one bounded source",
        },
        "triggerLabel": "Inspect the operating evidence",
        "sources": [{
            "id": "operating-note",
            "label": "Operating method note",
            "detail": "Synthetic fixture evidence for browser acceptance.",
            "url": "https://example.com/operating-note",
        }, {
            "id": "plain-note",
            "label": "Plain-text rejected link",
            "detail": "Unsafe source values remain readable without navigation.",
            "url": "javascript:alert('blocked')",
        }],
        "assumptions": [{
            "id": "synthetic-inputs",
            "label": "All values are synthetic",
            "value": "Browser fixture only",
        }],
    }


def _evidence_only_spec() -> dict:
    return {
        "pattern": "bullet_list",
        "headline": "The operating recommendation is backed by one bounded source",
        "source": "Illustrative operating exercise",
        "classification": "Illustrative",
        "page_number": 1,
        "bullets": [{"text": "The proof remains available in one action", "emphasis": True}],
    }


def _ranked_state_scene() -> dict:
    scene = _numeric_common(
        "state_toggle",
        "Show how a capacity constraint changes the queue order",
        "Verify which queue moves first and which item leaves the active set",
    )
    scene.update({
        "initialState": {"scenario": "base"},
        "printState": {"scenario": "base"},
        "controls": [{
            "id": "scenario",
            "kind": "segmented",
            "label": "Queue scenario",
            "options": [
                {"value": "base", "label": "Base"},
                {"value": "constrained", "label": "Constrained"},
            ],
        }],
        "states": [
            {
                "id": "base",
                "provenance": copy.deepcopy(PROVENANCE),
                "view": {
                    "component": "ranked_list",
                    "items": [
                        {"id": "north", "label": "North queue", "rank": 1, "emphasis": True},
                        {"id": "central", "label": "Central queue", "rank": 2},
                        {"id": "west", "label": "West queue", "rank": 3},
                    ],
                },
            },
            {
                "id": "constrained",
                "provenance": copy.deepcopy(PROVENANCE),
                "view": {
                    "component": "ranked_list",
                    "items": [
                        {"id": "central", "label": "Central queue", "rank": 1, "emphasis": True},
                        {"id": "north", "label": "North queue", "rank": 2},
                        {"id": "west", "label": "West queue", "rank": 3, "removed": True},
                    ],
                },
            },
        ],
    })
    return scene


def _ranked_state_spec(page: int) -> dict:
    return {
        "pattern": "bullet_list",
        "headline": "The unconstrained queue starts with North",
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "bullets": [
            {"item_id": "north", "text": "North queue", "rank": 1, "removed": False, "emphasis": True},
            {"item_id": "central", "text": "Central queue", "rank": 2, "removed": False, "emphasis": False},
            {"item_id": "west", "text": "West queue", "rank": 3, "removed": False, "emphasis": False},
        ],
    }


def _bar_state_scene() -> dict:
    scene = _numeric_common(
        "state_toggle",
        "Preserve exact authored display precision across named states",
        "Compare the base and pressure capacity without recomputing authored display text",
    )
    scene.update({
        "initialState": {"scenario": "base"},
        "printState": {"scenario": "base"},
        "controls": [{
            "id": "scenario",
            "kind": "select",
            "label": "Capacity scenario",
            "options": [
                {"value": "base", "label": "Base capacity"},
                {"value": "pressure", "label": "Pressure capacity"},
            ],
        }],
        "states": [
            {
                "id": "base",
                "provenance": copy.deepcopy(PROVENANCE),
                "view": {
                    "component": "bar_compare",
                    "quantity": "value",
                    "domain": [0, 10],
                    "baseline": 0,
                    "items": [{
                        "id": "capacity",
                        "label": "Capacity",
                        "value": _literal(Decimal("2")),
                        "emphasis": True,
                    }],
                },
            },
            {
                "id": "pressure",
                "provenance": copy.deepcopy(PROVENANCE),
                "view": {
                    "component": "bar_compare",
                    "quantity": "value",
                    "domain": [0, 10],
                    "baseline": 0,
                    "items": [{
                        "id": "capacity",
                        "label": "Capacity",
                        "value": _literal(Decimal("3.0")),
                        "emphasis": False,
                    }],
                },
            },
        ],
    })
    return scene


def _bar_state_spec(page: int) -> dict:
    return {
        "pattern": "gap",
        "headline": "Base capacity is two units",
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "quantity": "value",
        "unit": "units",
        "value_domain": [0, 10],
        "baseline": 0,
        "items": [{
            "item_id": "capacity",
            "label": "Capacity",
            "value": 2,
            "value_text": "2 units",
            "emphasis": True,
            "removed": False,
        }],
    }


def _slider_common(
    *,
    model: dict,
    initial: Decimal | int,
    maximum: Decimal | int,
    step: Decimal | int,
    threshold: Decimal | int,
    view: dict,
) -> dict:
    scene = _numeric_common(
        "slider_model",
        "Check exact browser parity for a bounded numeric model",
        "Find whether the validated result reaches the declared decision threshold",
    )
    scene.update({
        "initialState": {"input": initial},
        "printState": {"input": initial},
        "controls": [{
            "id": "input",
            "kind": "range",
            "label": "Input",
            "min": 0,
            "max": maximum,
            "step": step,
            "quantity": "value",
            "provenance": copy.deepcopy(PROVENANCE),
        }],
        "model": model,
        "reporting": {"primaryOutput": "result", "secondaryOutputs": []},
        "decisionContract": _decision(
            threshold,
            met=("Proceed", "Run the bounded pilot"),
            unmet=("Hold", "Keep the pilot bounded"),
        ),
        "view": view,
    })
    return scene


def _bar_view(domain_max: Decimal | int = 20) -> dict:
    return {
        "component": "bar_compare",
        "quantity": "value",
        "domain": [0, domain_max],
        "baseline": 0,
        "items": [{
            "id": "result",
            "label": "Result",
            "value": {"ref": "output:result"},
            "emphasis": True,
        }],
    }


def _dot_view(*, x_max: Decimal | int, y_max: Decimal | int) -> dict:
    return {
        "component": "dot_plot",
        "xLabel": "Input",
        "xQuantity": "value",
        "xDomain": [0, x_max],
        "yLabel": "Result",
        "yQuantity": "value",
        "yDomain": [0, y_max],
        "points": [{
            "id": "result-point",
            "label": "Result",
            "x": {"ref": "control:input"},
            "y": {"ref": "output:result"},
            "highlight": True,
        }],
    }


def _linear_scene() -> dict:
    model = {
        "kind": "linear",
        "intercept": {"value": 3, "quantity": "value"},
        "terms": {"input": {
            "coefficient": 5,
            "inputQuantity": "value",
            "outputQuantity": "value",
        }},
        "output": "result",
        "outputQuantity": "value",
        "label": "Result",
        "format": "number",
        "round": 0,
        "modelProvenance": copy.deepcopy(PROVENANCE),
    }
    return _slider_common(
        model=model,
        initial=1,
        maximum=2,
        step=1,
        threshold=8,
        view=_bar_view(),
    )


def _lookup_scene() -> dict:
    model = {
        "kind": "lookup",
        "input": "input",
        "entries": [
            {"input": 0, "output": {"value": 3, "quantity": "value"}},
            {"input": 1, "output": {"value": 8, "quantity": "value"}},
            {"input": 2, "output": {"value": 13, "quantity": "value"}},
        ],
        "output": "result",
        "outputQuantity": "value",
        "label": "Result",
        "format": "number",
        "round": 0,
        "modelProvenance": copy.deepcopy(PROVENANCE),
    }
    return _slider_common(
        model=model,
        initial=0,
        maximum=2,
        step=1,
        threshold=8,
        view=_bar_view(),
    )


def _piecewise_scene() -> dict:
    model = {
        "kind": "piecewise",
        "input": "input",
        "segments": [
            {
                "kind": "linear",
                "min": 0,
                "max": 2,
                "inputQuantity": "value",
                "slope": {
                    "coefficient": 2,
                    "inputQuantity": "value",
                    "outputQuantity": "value",
                },
                "intercept": {"value": 1, "quantity": "value"},
            },
            {
                "kind": "endpoints",
                "min": 2,
                "max": 4,
                "inputQuantity": "value",
                "start": {"value": 5, "quantity": "value"},
                "end": {"value": 11, "quantity": "value"},
            },
        ],
        "output": "result",
        "outputQuantity": "value",
        "label": "Result",
        "format": "number",
        "round": 0,
        "modelProvenance": copy.deepcopy(PROVENANCE),
    }
    return _slider_common(
        model=model,
        initial=0,
        maximum=4,
        step=1,
        threshold=8,
        view=_dot_view(x_max=4, y_max=12),
    )


def _graph_scene() -> dict:
    model = {
        "kind": "operation_graph",
        "nodes": [
            {"id": "x", "op": "input", "control": "input", "quantity": "value"},
            {
                "id": "half",
                "op": "constant",
                "value": Decimal(".5"),
                "quantity": "value",
                "provenance": copy.deepcopy(PROVENANCE),
            },
            {"id": "product", "op": "multiply", "left": "x", "right": "half", "quantity": "value"},
            {"id": "sum", "op": "add", "left": "product", "right": "product", "quantity": "value"},
        ],
        "outputs": {
            "product": {
                "node": "product",
                "quantity": "value",
                "label": "Rounded product",
                "format": "number",
                "round": 1,
            },
            "result": {
                "node": "sum",
                "quantity": "value",
                "label": "Result",
                "format": "number",
                "round": 1,
            },
        },
    }
    scene = _slider_common(
        model=model,
        initial=Decimal(".5"),
        maximum=1,
        step=Decimal(".5"),
        threshold=Decimal(".6"),
        view=_dot_view(x_max=1, y_max=1),
    )
    scene["reporting"] = {"primaryOutput": "result", "secondaryOutputs": ["product"]}
    return scene


def _score_scene() -> dict:
    scene = _numeric_common(
        "score_model",
        "Combine four bounded readiness inputs into one explicit recommendation",
        "Decide whether the complete readiness scenario reaches the action threshold",
    )
    scene["quantities"]["points"] = {
        "dimension": "score",
        "unit": "point",
        "display": "points",
    }
    controls = [
        {
            "id": "scale",
            "kind": "range",
            "label": "Scale readiness",
            "min": 0,
            "max": 1,
            "step": 1,
            "quantity": "value",
            "provenance": copy.deepcopy(PROVENANCE),
        },
        {
            "id": "channel",
            "kind": "segmented",
            "label": "Channel readiness",
            "options": [
                {"value": "narrow", "label": "Narrow channel"},
                {"value": "wide", "label": "Wide channel"},
            ],
        },
        {
            "id": "sponsor",
            "kind": "toggle",
            "label": "Sponsor readiness",
            "options": [
                {"value": "off", "label": "Sponsor off"},
                {"value": "on", "label": "Sponsor on"},
            ],
        },
        {
            "id": "scope",
            "kind": "select",
            "label": "Scope readiness",
            "options": [
                {"value": "small", "label": "Small scope"},
                {"value": "large", "label": "Large scope"},
            ],
        },
        {
            "id": "reserve",
            "kind": "toggle",
            "label": "Reserve readiness",
            "options": [
                {"value": "off", "label": "Reserve off"},
                {"value": "on", "label": "Reserve on"},
            ],
        },
        {
            "id": "process",
            "kind": "segmented",
            "label": "Process readiness",
            "options": [
                {"value": "basic", "label": "Basic process"},
                {"value": "mature", "label": "Mature process"},
            ],
        },
        {
            "id": "demand",
            "kind": "select",
            "label": "Demand readiness",
            "options": [
                {"value": "low", "label": "Low demand"},
                {"value": "high", "label": "High demand"},
            ],
        },
        {
            "id": "quality",
            "kind": "toggle",
            "label": "Quality readiness",
            "options": [
                {"value": "off", "label": "Quality off"},
                {"value": "on", "label": "Quality on"},
            ],
        },
    ]
    contributions = [
        {
            "control": "scale",
            "values": [{"input": 0, "points": 0}, {"input": 1, "points": 1}],
        },
        {
            "control": "channel",
            "values": [{"input": "narrow", "points": 0}, {"input": "wide", "points": 2}],
        },
        {
            "control": "sponsor",
            "values": [{"input": "off", "points": 0}, {"input": "on", "points": 3}],
        },
        {
            "control": "scope",
            "values": [{"input": "small", "points": 0}, {"input": "large", "points": 4}],
        },
        {
            "control": "reserve",
            "values": [{"input": "off", "points": 0}, {"input": "on", "points": 0}],
        },
        {
            "control": "process",
            "values": [{"input": "basic", "points": 0}, {"input": "mature", "points": 0}],
        },
        {
            "control": "demand",
            "values": [{"input": "low", "points": 0}, {"input": "high", "points": 0}],
        },
        {
            "control": "quality",
            "values": [{"input": "off", "points": 0}, {"input": "on", "points": 0}],
        },
    ]
    scene.update({
        "initialState": {
            "scale": 0,
            "channel": "narrow",
            "sponsor": "off",
            "scope": "small",
            "reserve": "off",
            "process": "basic",
            "demand": "low",
            "quality": "off",
        },
        "printState": {
            "scale": 0,
            "channel": "narrow",
            "sponsor": "off",
            "scope": "small",
            "reserve": "off",
            "process": "basic",
            "demand": "low",
            "quality": "off",
        },
        "controls": controls,
        "model": {
            "kind": "score_sum",
            "quantity": "points",
            "contributions": contributions,
            "bands": [
                {"id": "early", "min": 0, "max": 5, "label": "Early"},
                {"id": "ready", "min": 5, "max": 10, "label": "Ready"},
            ],
            "label": "Readiness score",
            "format": "score",
            "round": 0,
            "modelProvenance": copy.deepcopy(PROVENANCE),
        },
        "reporting": {"primaryOutput": "score", "secondaryOutputs": []},
        "decisionContract": {
            "id": "readiness-gate",
            "metric": {"ref": "output:score"},
            "operator": "gte",
            "threshold": {
                "value": 5,
                "quantity": "points",
                "provenance": copy.deepcopy(PROVENANCE),
            },
            "whenMet": {"status": "Advance", "recommendation": "Run the integrated pilot"},
            "whenNotMet": {"status": "Hold", "recommendation": "Resolve readiness gaps"},
        },
        "view": {"component": "recommendation_panel", "score": {"ref": "output:score"}},
    })
    return scene


def _score_spec(page: int) -> dict:
    return {
        "pattern": "closing",
        "headline": "The baseline readiness score remains below the action threshold",
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "annotation": "",
        "interactive_result": {
            "quantity": "points",
            "value": 0,
            "classification": "Early",
            "decision_status": "Hold",
            "recommendation": "Resolve readiness gaps",
            "operator": "gte",
            "threshold": 5,
        },
        "takeaways": [
            "Readiness score 0 points",
            "Early",
            "Hold; threshold ≥ 5 points",
        ],
        "next_steps": [{"action": "Resolve readiness gaps"}],
    }


def _disclosure_scene(kind: str) -> dict:
    base = {
        "version": 1,
        "type": kind,
        "purpose": "Reveal one bounded explanation while preserving the parent claim",
        "decisionJob": "insight",
        "interactionRationale": "Inspect one explanation and return to the unchanged parent conclusion",
        "initialState": {"panel": None},
        "printState": {"panel": None},
        "fallbackSummary": {
            "field": "headline",
            "text": (
                "One drill-down explains the operating sequence"
                if kind == "drilldown"
                else "One accordion answer remains open at a time"
            ),
        },
        "sources": [{
            "id": "method-note",
            "label": "Method note",
            "detail": "Synthetic fixture detail.",
        }],
    }
    entries = [
        {
            "id": "method",
            "label": "Method",
            "heading": "How the method works",
            "body": "The fixture follows one validated path from input to result.",
            "sourceRefs": ["method-note"],
        },
        {
            "id": "boundary",
            "label": "Boundary",
            "heading": "Where the boundary sits",
            "body": "The fixture uses an explicit threshold and a fixed scale.",
            "sourceRefs": ["method-note"],
        },
    ]
    if kind == "drilldown":
        base.update({
            "panels": entries,
            "parentSummary": "The parent conclusion stays visible before and after inspection.",
            "returnLabel": "Return to the parent conclusion",
        })
    else:
        base.update({"items": entries, "allowNone": True})
    return base


def _disclosure_spec(kind: str, page: int) -> dict:
    headline = (
        "One drill-down explains the operating sequence"
        if kind == "drilldown"
        else "One accordion answer remains open at a time"
    )
    return {
        "pattern": "bullet_list",
        "headline": headline,
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "bullets": [{"text": "The static conclusion remains complete", "emphasis": True}],
    }


def _initially_open_disclosure_scene(kind: str, panel: str) -> dict:
    scene = _disclosure_scene(kind)
    scene["initialState"] = {"panel": panel}
    scene["printState"] = {"panel": panel}
    if kind == "accordion":
        scene["allowNone"] = False
    return scene


def _long_ranked_scene() -> dict:
    scene = _numeric_common(
        "state_toggle",
        "Keep long ranked identifiers bound to the same visual marks",
        "Verify identity while the two ranked items exchange positions",
    )
    scene.update({
        "initialState": {"scenario": "base"},
        "printState": {"scenario": "base"},
        "controls": [{
            "id": "scenario",
            "kind": "segmented",
            "label": "Long ranked scenario",
            "options": [
                {"value": "base", "label": "Original order"},
                {"value": "swapped", "label": "Swap order"},
            ],
        }],
        "states": [
            {
                "id": "base",
                "provenance": copy.deepcopy(PROVENANCE),
                "view": {
                    "component": "ranked_list",
                    "items": [
                        {"id": LONG_RANK_ALPHA, "label": "Long Alpha", "rank": 1, "emphasis": True},
                        {"id": LONG_RANK_BETA, "label": "Long Beta", "rank": 2},
                    ],
                },
            },
            {
                "id": "swapped",
                "provenance": copy.deepcopy(PROVENANCE),
                "view": {
                    "component": "ranked_list",
                    "items": [
                        {"id": LONG_RANK_BETA, "label": "Long Beta", "rank": 1, "emphasis": True},
                        {"id": LONG_RANK_ALPHA, "label": "Long Alpha", "rank": 2},
                    ],
                },
            },
        ],
    })
    return scene


def _long_ranked_spec(page: int) -> dict:
    return {
        "pattern": "bullet_list",
        "headline": "Long identifiers retain their ranked visual identity",
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "bullets": [
            {
                "item_id": LONG_RANK_ALPHA,
                "text": "Long Alpha",
                "rank": 1,
                "removed": False,
                "emphasis": True,
            },
            {
                "item_id": LONG_RANK_BETA,
                "text": "Long Beta",
                "rank": 2,
                "removed": False,
                "emphasis": False,
            },
        ],
    }


def _long_dot_scene() -> dict:
    scene = _numeric_common(
        "state_toggle",
        "Keep long dot identifiers bound through a reordered transition",
        "Verify that each labelled dot travels to its own target coordinates",
    )

    def point(item_id: str, label: str, x: int, y: int, highlight: bool = False) -> dict:
        return {
            "id": item_id,
            "label": label,
            "x": _literal(x),
            "y": _literal(y),
            "highlight": highlight,
        }

    def view(points: list[dict]) -> dict:
        return {
            "component": "dot_plot",
            "xLabel": "Input",
            "xQuantity": "value",
            "xDomain": [0, 10],
            "yLabel": "Result",
            "yQuantity": "value",
            "yDomain": [0, 10],
            "points": points,
        }

    scene.update({
        "initialState": {"scenario": "base"},
        "printState": {"scenario": "base"},
        "controls": [{
            "id": "scenario",
            "kind": "segmented",
            "label": "Long dot scenario",
            "options": [
                {"value": "base", "label": "Original points"},
                {"value": "swapped", "label": "Swap points"},
            ],
        }],
        "states": [
            {
                "id": "base",
                "provenance": copy.deepcopy(PROVENANCE),
                "view": view([
                    point(LONG_DOT_ALPHA, "Dot Alpha", 2, 2, True),
                    point(LONG_DOT_BETA, "Dot Beta", 8, 8),
                ]),
            },
            {
                "id": "swapped",
                "provenance": copy.deepcopy(PROVENANCE),
                "view": view([
                    point(LONG_DOT_BETA, "Dot Beta", 7, 3, True),
                    point(LONG_DOT_ALPHA, "Dot Alpha", 3, 9),
                ]),
            },
        ],
    })
    return scene


def _long_dot_spec(page: int) -> dict:
    return {
        "pattern": "scatter",
        "headline": "Long identifiers retain their dot visual identity",
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "x_axis": {
            "label": "Input",
            "quantity": "value",
            "unit": "units",
            "domain": [0, 10],
            "tick_labels": ["0 units", "10 units"],
        },
        "y_axis": {
            "label": "Result",
            "quantity": "value",
            "unit": "units",
            "domain": [0, 10],
            "tick_labels": ["0 units", "10 units"],
        },
        "points": [
            {
                "item_id": LONG_DOT_ALPHA,
                "label": "Dot Alpha",
                "x": 2,
                "y": 2,
                "emphasis": True,
                "removed": False,
            },
            {
                "item_id": LONG_DOT_BETA,
                "label": "Dot Beta",
                "x": 8,
                "y": 8,
                "emphasis": False,
                "removed": False,
            },
        ],
    }


def _twelve_item_bar_scene() -> dict:
    scene = _numeric_common(
        "state_toggle",
        "Compare twelve bounded bars without overlap or clipping",
        "Inspect the complete operating portfolio on one fixed scale",
    )

    def items(reverse: bool = False) -> list[dict]:
        values = list(range(1, 13))
        if reverse:
            values.reverse()
        return [
            {
                "id": f"bar-{index:02d}",
                "label": f"Bar {index:02d}",
                "value": _literal(value),
                "emphasis": index == 1,
            }
            for index, value in enumerate(values, start=1)
        ]

    def view(rows: list[dict]) -> dict:
        return {
            "component": "bar_compare",
            "quantity": "value",
            "domain": [0, 12],
            "baseline": 0,
            "items": rows,
        }

    scene.update({
        "initialState": {"scenario": "base"},
        "printState": {"scenario": "base"},
        "controls": [{
            "id": "scenario",
            "kind": "select",
            "label": "Twelve bar scenario",
            "options": [
                {"value": "base", "label": "Ascending bars"},
                {"value": "reverse", "label": "Descending bars"},
            ],
        }],
        "states": [
            {"id": "base", "provenance": copy.deepcopy(PROVENANCE), "view": view(items())},
            {"id": "reverse", "provenance": copy.deepcopy(PROVENANCE), "view": view(items(True))},
        ],
    })
    return scene


def _twelve_item_bar_spec(page: int) -> dict:
    return {
        "pattern": "gap",
        "headline": "Twelve bars remain readable on the fixed domain",
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "quantity": "value",
        "unit": "units",
        "value_domain": [0, 12],
        "baseline": 0,
        "items": [
            {
                "item_id": f"bar-{index:02d}",
                "label": f"Bar {index:02d}",
                "value": index,
                "value_text": f"{index} units",
                "emphasis": index == 1,
                "removed": False,
            }
            for index in range(1, 13)
        ],
    }


def _twelve_item_ranked_scene() -> dict:
    scene = _numeric_common(
        "state_toggle",
        "Show twelve ranked items without overlap or clipping",
        "Inspect every ranked operating item in one bounded chart band",
    )

    def items(reverse: bool = False) -> list[dict]:
        ranks = list(range(1, 13))
        if reverse:
            ranks.reverse()
        return [
            {
                "id": f"rank-{index:02d}",
                "label": f"Rank {index:02d}",
                "rank": rank,
                "emphasis": index == (12 if reverse else 1),
            }
            for index, rank in enumerate(ranks, start=1)
        ]

    def view(rows: list[dict]) -> dict:
        return {"component": "ranked_list", "items": rows}

    scene.update({
        "initialState": {"scenario": "base"},
        "printState": {"scenario": "base"},
        "controls": [{
            "id": "scenario",
            "kind": "segmented",
            "label": "Twelve rank scenario",
            "options": [
                {"value": "base", "label": "Ascending ranks"},
                {"value": "reverse", "label": "Reverse ranks"},
            ],
        }],
        "states": [
            {"id": "base", "provenance": copy.deepcopy(PROVENANCE), "view": view(items())},
            {"id": "reverse", "provenance": copy.deepcopy(PROVENANCE), "view": view(items(True))},
        ],
    })
    return scene


def _twelve_item_ranked_spec(page: int) -> dict:
    return {
        "pattern": "bullet_list",
        "headline": "Twelve ranked items remain readable in the chart band",
        "source": "Illustrative browser oracle",
        "classification": "Illustrative",
        "page_number": page,
        "columns": 2,
        "bullets": [
            {
                "item_id": f"rank-{index:02d}",
                "text": f"Rank {index:02d}",
                "rank": index,
                "removed": False,
                "emphasis": index == 1,
            }
            for index in range(1, 13)
        ],
    }


def build_reviewed_valid_fixture(root: Path) -> tuple[subprocess.CompletedProcess[str], Path]:
    rows = [
        (
            "accordion-required",
            _disclosure_spec("accordion", 1),
            _initially_open_disclosure_scene("accordion", "method"),
        ),
        (
            "drilldown-open",
            _disclosure_spec("drilldown", 2),
            _initially_open_disclosure_scene("drilldown", "method"),
        ),
        ("ranked-long-ids", _long_ranked_spec(3), _long_ranked_scene()),
        ("dot-long-ids", _long_dot_spec(4), _long_dot_scene()),
        ("bar-twelve", _twelve_item_bar_spec(5), _twelve_item_bar_scene()),
        ("ranked-twelve", _twelve_item_ranked_spec(6), _twelve_item_ranked_scene()),
    ]
    slides = []
    for ordinal, (slide_id, spec, scene) in enumerate(rows, start=1):
        spec_path = root / f"specs/{ordinal:02d}-{slide_id}.json"
        scene_path = root / f"scenes/{ordinal:02d}-{slide_id}.json"
        _write_exact_json(spec_path, spec)
        _write_exact_json(scene_path, scene)
        slides.append({
            "id": slide_id,
            "spec": str(spec_path.relative_to(root)),
            "scene": str(scene_path.relative_to(root)),
        })
    manifest = root / "deck.json"
    _write_exact_json(manifest, {
        "title": "Task 5 reviewed valid cases",
        "lang": "en",
        "slides": slides,
    })
    artifact = root / "task5-reviewed-valid.interactive.html"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(BUILD_SCRIPT),
            "--manifest",
            str(manifest),
            "-o",
            str(artifact),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed, artifact


def write_task5_fixture(root: Path) -> Path:
    """Write an original full-matrix fixture and return its manifest."""
    rows = [
        ("evidence-only", _evidence_only_spec(), _evidence_only_scene()),
        ("ranked-state", _ranked_state_spec(2), _ranked_state_scene()),
        ("bar-state", _bar_state_spec(3), _bar_state_scene()),
        (
            "linear-model",
            _bar_static(
                headline="The linear baseline reaches the gate",
                page=4,
                value=8,
                value_text="8 units",
                domain_max=20,
                threshold=8,
                status="Proceed",
                recommendation="Run the bounded pilot",
            ),
            _linear_scene(),
        ),
        (
            "lookup-model",
            _bar_static(
                headline="The lookup baseline starts below the gate",
                page=5,
                value=3,
                value_text="3 units",
                domain_max=20,
                threshold=8,
                status="Hold",
                recommendation="Keep the pilot bounded",
            ),
            _lookup_scene(),
        ),
        (
            "piecewise-model",
            _dot_static(
                headline="The piecewise baseline starts below the gate",
                page=6,
                x=0,
                y=1,
                x_max=4,
                y_max=12,
                y_text="1 units",
                threshold=8,
                status="Hold",
                recommendation="Keep the pilot bounded",
            ),
            _piecewise_scene(),
        ),
        (
            "graph-model",
            _dot_static(
                headline="The graph baseline reaches the exact decimal gate",
                page=7,
                x=Decimal(".5"),
                y=Decimal(".6"),
                x_max=1,
                y_max=1,
                y_text="0.6 units",
                threshold=Decimal(".6"),
                status="Proceed",
                recommendation="Run the bounded pilot",
            ),
            _graph_scene(),
        ),
        ("score-model", _score_spec(8), _score_scene()),
        ("drilldown", _disclosure_spec("drilldown", 9), _disclosure_scene("drilldown")),
        ("accordion", _disclosure_spec("accordion", 10), _disclosure_scene("accordion")),
    ]
    slides = []
    for ordinal, (slide_id, spec, scene) in enumerate(rows, start=1):
        spec_path = root / f"specs/{ordinal:02d}-{slide_id}.json"
        scene_path = root / f"scenes/{ordinal:02d}-{slide_id}.json"
        _write_exact_json(spec_path, spec)
        _write_exact_json(scene_path, scene)
        slides.append({
            "id": slide_id,
            "spec": str(spec_path.relative_to(root)),
            "scene": str(scene_path.relative_to(root)),
        })
    manifest = {
        "title": "Task 5 component contract",
        "lang": "en",
        "slides": slides,
    }
    _write_exact_json(root / "deck.json", manifest)
    return root / "deck.json"


def build_task5_fixture(root: Path) -> tuple[subprocess.CompletedProcess[str], Path]:
    manifest = write_task5_fixture(root)
    artifact = root / "task5.interactive.html"
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(BUILD_SCRIPT),
            "--manifest",
            str(manifest),
            "-o",
            str(artifact),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed, artifact


class Task5BuildContractTests(unittest.TestCase):
    def test_complete_compiler_matrix_reaches_the_runtime_bundle_as_closed_data(self) -> None:
        """Catches a bundle allowlist narrower than the compiler's v1 matrix."""
        with tempfile.TemporaryDirectory(prefix="task5-matrix-red-") as directory:
            completed, artifact = build_task5_fixture(Path(directory))

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(artifact.is_file())
            envelope, _raw = decode_envelope_text(artifact.read_text(encoding="utf-8"))
            by_id = {row["slideId"]: row for row in envelope["slides"]}
            self.assertEqual(
                {row["scene"]["type"] for row in envelope["slides"]},
                {
                    "evidence_only",
                    "state_toggle",
                    "slider_model",
                    "score_model",
                    "drilldown",
                    "accordion",
                },
            )
            self.assertEqual(
                {
                    row["scene"]["model"]["kind"]
                    for row in envelope["slides"]
                    if row["scene"].get("model") is not None
                },
                {"state_map", "linear", "lookup", "piecewise", "operation_graph", "score_sum"},
            )
            self.assertEqual(
                {
                    row["scene"]["initialEvaluation"]["view"]["component"]
                    for row in envelope["slides"]
                    if row["scene"]["initialEvaluation"]["view"] is not None
                },
                {"bar_compare", "ranked_list", "dot_plot", "recommendation_panel"},
            )
            evidence = by_id["evidence-only"]
            self.assertEqual(evidence["scene"]["evidence"]["badge"], "")
            self.assertIsNone(evidence["scene"]["initialEvaluation"]["view"])
            self.assertIsNone(evidence["display"]["axisTickLabels"])
            self.assertIsNone(by_id["bar-state"]["display"]["axisTickLabels"])
            self.assertEqual(
                by_id["piecewise-model"]["display"]["axisTickLabels"],
                {"x": ["0 units", "4 units"], "y": ["0 units", "12 units"]},
            )
            bar_states = by_id["bar-state"]["scene"]["states"]
            self.assertEqual(bar_states[0]["view"]["items"][0]["valueText"], "2 units")
            self.assertEqual(bar_states[1]["view"]["items"][0]["valueText"], "3.0 units")
            self.assertEqual(
                by_id["bar-state"]["scene"]["initialEvaluation"]["view"],
                bar_states[0]["view"],
            )

    def test_unsupported_scene_view_pair_never_replaces_the_last_complete_artifact(self) -> None:
        """Catches a silent static downgrade or non-atomic invalid-pair rebuild."""
        with tempfile.TemporaryDirectory(prefix="task5-invalid-pair-") as directory:
            root = Path(directory)
            manifest = write_task5_fixture(root)
            output = root / "task5.interactive.html"
            sentinel = b"last complete interactive artifact"
            output.write_bytes(sentinel)
            scene_path = root / "scenes/04-linear-model.json"
            scene = json.loads(scene_path.read_text(encoding="utf-8"), parse_float=Decimal)
            scene["view"] = {
                "component": "ranked_list",
                "items": [{"id": "result", "label": "Result", "rank": 1}],
            }
            _write_exact_json(scene_path, scene)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    str(BUILD_SCRIPT),
                    "--manifest",
                    str(manifest),
                    "-o",
                    str(output),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(output.read_bytes(), sentinel)
            self.assertNotIn("Traceback", completed.stderr)


class Task5InteractiveComponentsE2ETests(InteractiveDeckBrowserTestCase):
    SLIDES = {
        "evidence-only": 1,
        "ranked-state": 2,
        "bar-state": 3,
        "linear-model": 4,
        "lookup-model": 5,
        "piecewise-model": 6,
        "graph-model": 7,
        "score-model": 8,
        "drilldown": 9,
        "accordion": 10,
    }

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        completed, artifact = build_task5_fixture(cls.fixture_root / "task5-matrix")
        if completed.returncode:
            raise AssertionError("Task 5 fixture build failed: " + completed.stderr.strip())
        cls.artifact = artifact

    def _wait_for_runtime(self, page) -> None:
        page.wait_for_function(
            """() => window.InteractiveDeck &&
                typeof window.InteractiveDeck.snapshot === 'function'""",
            timeout=10_000,
        )

    def _scene(self, page, slide_id: str):
        return page.locator(f'[data-slide-id="{slide_id}"]')

    def _set_data_details(self, page, slide_id: str, *, opened: bool) -> None:
        details = self._scene(page, slide_id).locator(".data-details")
        self.assertEqual(details.count(), 1)
        if (details.get_attribute("open") is not None) != opened:
            summary = details.locator("summary")
            summary.focus()
            summary.press("Enter")
        self.assertEqual(details.get_attribute("open") is not None, opened)

    def _activate(self, page, slide_id: str) -> None:
        ordinal = self.SLIDES[slide_id]
        page.locator(
            f'#idrt-presenter-chrome [data-page-index="{ordinal}"]'
        ).click()
        page.wait_for_function(
            """slideId => {
              const scene = document.querySelector(`[data-slide-id="${slideId}"]`);
              return scene && !scene.hidden && scene.dataset.runtime === "ready";
            }""",
            arg=slide_id,
            timeout=10_000,
        )

    def _range(self, page, slide_id: str, control_id: str = "input"):
        return self._scene(page, slide_id).locator(
            f'input[data-control-id="{control_id}"], '
            f'[data-control-id="{control_id}"] input[type="range"]'
        ).first

    def _select(self, page, slide_id: str, control_id: str):
        return self._scene(page, slide_id).locator(
            f'select[data-control-id="{control_id}"], '
            f'[data-control-id="{control_id}"] select'
        ).first

    def _set_range_index(self, page, slide_id: str, native_index: str, control_id: str = "input") -> None:
        self._range(page, slide_id, control_id).evaluate(
            """(input, value) => {
              input.value = value;
              input.dispatchEvent(new Event("input", {bubbles: true}));
            }""",
            native_index,
        )

    def _live_value(self, page, slide_id: str, output_id: str) -> str:
        return self._scene(page, slide_id).locator(
            f'[data-live-value="{output_id}"]'
        ).inner_text()

    def _live_svg_node(self, page, slide_id: str, source_id: str):
        ordinal = self.SLIDES[slide_id]
        return self._scene(page, slide_id).locator(
            f'.live-layer [id="idsvg-{ordinal}-live-shell-{source_id}"]'
        )

    @staticmethod
    def _fixed_svg_anchor(anchor) -> dict:
        return anchor.evaluate(
            """node => ({
              x: node.getAttribute("x"),
              y: node.getAttribute("y"),
              x1: node.getAttribute("x1"),
              x2: node.getAttribute("x2"),
              y1: node.getAttribute("y1"),
              y2: node.getAttribute("y2"),
              width: node.getAttribute("width"),
              height: node.getAttribute("height"),
              text: node.textContent
            })"""
        )

    def _state_event_count(self, session) -> int:
        return sum(
            event.get("type") == "state"
            for event in session.monitor()["deckEvents"]
        )

    def _assert_one_state_event(self, session, before: int) -> None:
        self.assertEqual(self._state_event_count(session), before + 1)

    def _assert_ready_matrix(self, page) -> None:
        self._wait_for_runtime(page)
        for slide_id in self.SLIDES:
            scene = self._scene(page, slide_id)
            self.assertEqual(scene.get_attribute("data-runtime"), "ready", slide_id)
        for component in ("ranked_list", "bar_compare", "dot_plot", "recommendation_panel"):
            self.assertGreater(
                page.locator(f'[data-view-component="{component}"]').count(),
                0,
                component,
            )

    def test_boots_the_complete_matrix_without_network_in_both_engines_and_url_modes(self) -> None:
        """Catches browser-only validator drift or an automatic request in any mode."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode, artifact=self.artifact)
                try:
                    self._assert_ready_matrix(session.page)
                    self.assertEqual(
                        session.page.locator("#idrt-deck-pages > .slide").count(),
                        10,
                    )
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_all_models_and_control_kinds_share_one_atomic_state_event_and_url_contract(self) -> None:
        """Catches a second calculator, reducer, or fragment path for Task 5 controls."""
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=self.artifact)
                page = session.page
                try:
                    self._wait_for_runtime(page)

                    # state_map + segmented: stable node identity and labelled ghost removal.
                    self._activate(page, "ranked-state")
                    page.evaluate(
                        """() => {
                          window.__task5StableNode = document.querySelector(
                            '[data-slide-id="ranked-state"] [data-view-item-id="north"]'
                          );
                        }"""
                    )
                    before = self._state_event_count(session)
                    self._scene(page, "ranked-state").get_by_role(
                        "button", name="Constrained", exact=True
                    ).click()
                    page.wait_for_function(
                        """() => location.hash.includes("scenario=constrained")"""
                    )
                    self._assert_one_state_event(session, before)
                    self.assertTrue(page.evaluate(
                        """() => window.__task5StableNode === document.querySelector(
                          '[data-slide-id="ranked-state"] [data-view-item-id="north"]'
                        )"""
                    ))
                    west = self._scene(page, "ranked-state").locator(
                        '[data-view-item-id="west"]'
                    )
                    self._set_data_details(page, "ranked-state", opened=True)
                    self.assertIn("West queue", west.inner_text())
                    self.assertEqual(west.get_attribute("data-removed"), "true")
                    self.assertIn("removed", self._scene(page, "ranked-state").locator(".scene-status").inner_text())
                    self._set_data_details(page, "ranked-state", opened=False)

                    # state_map + select: compiler-owned 3.0 display text survives unchanged.
                    self._activate(page, "bar-state")
                    before = self._state_event_count(session)
                    self._select(page, "bar-state", "scenario").select_option("pressure")
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="bar-state"] [data-view-item-id="capacity"]'
                        )?.textContent.includes("3.0 units")"""
                    )
                    self._assert_one_state_event(session, before)
                    self._set_data_details(page, "bar-state", opened=True)
                    self.assertIn(
                        "3.0 units",
                        self._scene(page, "bar-state").locator(
                            '[data-view-item-id="capacity"]'
                        ).inner_text(),
                    )
                    self._set_data_details(page, "bar-state", opened=False)

                    numeric_oracles = (
                        ("linear-model", "2", "13 units"),
                        ("lookup-model", "2", "13 units"),
                    )
                    for slide_id, native_index, expected in numeric_oracles:
                        self._activate(page, slide_id)
                        before = self._state_event_count(session)
                        self._set_range_index(page, slide_id, native_index)
                        page.wait_for_function(
                            """args => document.querySelector(
                              `[data-slide-id="${args.slide}"] [data-live-value="result"]`
                            )?.textContent === args.expected""",
                            arg={"slide": slide_id, "expected": expected},
                        )
                        self._assert_one_state_event(session, before)

                    self._activate(page, "piecewise-model")
                    self.assertEqual(
                        self._live_value(page, "piecewise-model", "result"),
                        "1 units",
                    )
                    for native_index, expected in enumerate(
                        ("3 units", "5 units", "8 units", "11 units"),
                        start=1,
                    ):
                        before = self._state_event_count(session)
                        self._set_range_index(page, "piecewise-model", str(native_index))
                        page.wait_for_function(
                            """expected => document.querySelector(
                              '[data-slide-id="piecewise-model"] [data-live-value="result"]'
                            )?.textContent === expected""",
                            arg=expected,
                        )
                        self._assert_one_state_event(session, before)

                    self._activate(page, "graph-model")
                    self.assertEqual(self._live_value(page, "graph-model", "product"), "0.3 units")
                    self.assertEqual(self._live_value(page, "graph-model", "result"), "0.6 units")
                    before = self._state_event_count(session)
                    self._set_range_index(page, "graph-model", "2")
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="graph-model"] [data-live-value="result"]'
                        )?.textContent === '1.0 units'"""
                    )
                    self._assert_one_state_event(session, before)

                    # score_sum consumes range, segmented, toggle and select through the same path.
                    self._activate(page, "score-model")
                    before = self._state_event_count(session)
                    self._set_range_index(page, "score-model", "1", "scale")
                    self._assert_one_state_event(session, before)
                    for label in ("Wide channel", "Sponsor on"):
                        before = self._state_event_count(session)
                        self._scene(page, "score-model").get_by_role(
                            "button", name=label, exact=True
                        ).click()
                        self._assert_one_state_event(session, before)
                    before = self._state_event_count(session)
                    self._select(page, "score-model", "scope").select_option("large")
                    self._assert_one_state_event(session, before)
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="score-model"] [data-live-value="score"]'
                        )?.textContent === '10 points'"""
                    )
                    score_scene = self._scene(page, "score-model")
                    self.assertEqual(score_scene.locator('[data-live-value="classification"]').inner_text(), "Ready")
                    self.assertEqual(score_scene.locator("[data-decision-status]").inner_text(), "Advance")
                    self.assertEqual(
                        score_scene.locator("[data-decision-recommendation]").inner_text(),
                        "Run the integrated pilot",
                    )
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_ten_parameter_score_restore_is_one_atomic_evaluation(self) -> None:
        """Catches partial multi-control restore or an off-by-one fragment budget."""
        fragment = (
            "#slide=8&scale=1&channel=wide&sponsor=on&scope=large&reserve=on&"
            "process=mature&demand=high&quality=on&mode=live"
        )
        self.assertEqual(len(fragment[1:].split("&")), 10)
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=self.artifact)
                page = session.page
                try:
                    self._wait_for_runtime(page)
                    before = self._state_event_count(session)
                    page.evaluate("hash => { location.hash = hash; }", fragment)
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="score-model"] [data-live-value="score"]'
                        )?.textContent === '10 points'"""
                    )
                    self._assert_one_state_event(session, before)
                    self.assertEqual(page.evaluate("() => location.hash"), fragment)
                    snapshot = page.evaluate("() => window.InteractiveDeck.snapshot()")
                    self.assertEqual(snapshot["currentSlide"], 8)
                    self.assertEqual(snapshot["pages"][7]["outputs"]["score"], "10")
                    self.assertEqual(snapshot["pages"][7]["outcome"], "met")
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_evidence_drilldown_and_accordion_are_keyboard_focus_and_fragment_complete(self) -> None:
        """Catches disclosure state that bypasses the overlay/panel URL contract."""
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=self.artifact)
                page = session.page
                try:
                    self._wait_for_runtime(page)

                    self._activate(page, "evidence-only")
                    evidence_trigger = self._scene(page, "evidence-only").get_by_role(
                        "button", name="Inspect the operating evidence", exact=True
                    )
                    evidence_trigger.focus()
                    evidence_trigger.press("Enter")
                    dialog = page.get_by_role("dialog", name="Evidence")
                    self.assertTrue(dialog.is_visible())
                    self.assertEqual(evidence_trigger.get_attribute("aria-expanded"), "true")
                    self.assertIn("Operating method note", dialog.inner_text())
                    source_link = dialog.get_by_role("link", name="Operating method note", exact=True)
                    self.assertEqual(
                        source_link.get_attribute("href"),
                        "https://example.com/operating-note",
                    )
                    self.assertEqual(source_link.get_attribute("target"), "_blank")
                    self.assertEqual(source_link.get_attribute("rel"), "noopener noreferrer")
                    self.assertIn("Plain-text rejected link", dialog.inner_text())
                    self.assertEqual(
                        dialog.get_by_role("link", name="Plain-text rejected link", exact=True).count(),
                        0,
                    )
                    assumptions = dialog.get_by_role("tab", name="Assumptions", exact=True)
                    assumptions.click()
                    self.assertIn("All values are synthetic", dialog.inner_text())
                    page.keyboard.press("Escape")
                    self.assertTrue(dialog.is_hidden())
                    self.assertTrue(evidence_trigger.evaluate("node => node === document.activeElement"))

                    self._activate(page, "drilldown")
                    drill_scene = self._scene(page, "drilldown")
                    opener = drill_scene.get_by_role("button", name="Method", exact=True)
                    self.assertEqual(opener.get_attribute("data-action"), "open-panel")
                    opener.focus()
                    before = self._state_event_count(session)
                    opener.press("Enter")
                    page.wait_for_function(
                        """() => location.hash.includes("panel=method")"""
                    )
                    self._assert_one_state_event(session, before)
                    panel = drill_scene.locator('[data-panel-id="method"]')
                    self.assertTrue(panel.is_visible())
                    self.assertIn("validated path from input to result", panel.inner_text())
                    return_button = drill_scene.get_by_role(
                        "button", name="Return to the parent conclusion", exact=True
                    )
                    self.assertEqual(return_button.get_attribute("data-action"), "close-panel")
                    return_button.click()
                    self.assertTrue(panel.is_hidden())
                    self.assertNotIn("panel=", page.evaluate("() => location.hash"))
                    self.assertTrue(opener.evaluate("node => node === document.activeElement"))
                    before = self._state_event_count(session)
                    page.evaluate(
                        "() => { location.hash = '#slide=9&panel=boundary'; }"
                    )
                    boundary_panel = drill_scene.locator('[data-panel-id="boundary"]')
                    boundary_panel.wait_for(state="visible")
                    self._assert_one_state_event(session, before)
                    self.assertIn("explicit threshold", boundary_panel.inner_text())
                    drill_scene.get_by_role(
                        "button", name="Return to the parent conclusion", exact=True
                    ).click()

                    self._activate(page, "accordion")
                    accordion_scene = self._scene(page, "accordion")
                    method_button = accordion_scene.get_by_role("button", name="Method", exact=True)
                    boundary_button = accordion_scene.get_by_role("button", name="Boundary", exact=True)
                    self.assertEqual(method_button.get_attribute("data-accordion-id"), "method")
                    self.assertEqual(boundary_button.get_attribute("data-accordion-id"), "boundary")
                    method_button.press("Space")
                    self.assertEqual(method_button.get_attribute("aria-expanded"), "true")
                    self.assertEqual(boundary_button.get_attribute("aria-expanded"), "false")
                    boundary_button.focus()
                    boundary_button.press("Enter")
                    self.assertEqual(method_button.get_attribute("aria-expanded"), "false")
                    self.assertEqual(boundary_button.get_attribute("aria-expanded"), "true")
                    self.assertIn("panel=boundary", page.evaluate("() => location.hash"))
                    boundary_button.press("Space")
                    self.assertEqual(boundary_button.get_attribute("aria-expanded"), "false")
                    self.assertNotIn("panel=", page.evaluate("() => location.hash"))
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_derived_tooltips_use_only_resolved_facts_and_support_focus_tap_escape(self) -> None:
        """Catches authored tooltip prose, inaccessible proxies, or stale resolved text."""
        session = self.open_deck("chromium", "http", artifact=self.artifact)
        page = session.page
        try:
            self._wait_for_runtime(page)
            cases = (
                ("ranked-state", "north", ("North queue", "1")),
                ("bar-state", "capacity", ("Capacity", "2 units")),
                ("piecewise-model", "result-point", ("Result", "Input", "0 units", "1 units")),
                ("score-model", "early", ("Early", "0", "5")),
            )
            forbidden = (
                "Keep the proof adjacent",
                "Compare the base and pressure",
                "Synthetic fixture evidence",
                "Find whether the validated result",
            )
            for index, (slide_id, item_id, expected) in enumerate(cases):
                with self.subTest(slide_id=slide_id):
                    self._activate(page, slide_id)
                    self._set_data_details(page, slide_id, opened=True)
                    trigger = self._scene(page, slide_id).locator(
                        f'[data-tooltip-for="{item_id}"]'
                    ).first
                    self.assertTrue(trigger.is_visible())
                    trigger.focus()
                    trigger.press("Enter")
                    tooltip_id = trigger.get_attribute("aria-controls")
                    self.assertTrue(tooltip_id)
                    tooltip = page.locator(f"#{tooltip_id}")
                    self.assertTrue(tooltip.is_visible())
                    text = tooltip.inner_text()
                    for token in expected:
                        self.assertIn(token, text)
                    for prose in forbidden:
                        self.assertNotIn(prose, text)
                    page.keyboard.press("Escape")
                    self.assertTrue(tooltip.is_hidden())
                    self.assertTrue(trigger.evaluate("node => node === document.activeElement"))

                    # A touch-origin pointer sequence must reach the same proxy/action path.
                    trigger.dispatch_event("pointerdown", {"pointerType": "touch", "pointerId": 71 + index})
                    trigger.dispatch_event("pointerup", {"pointerType": "touch", "pointerId": 71 + index})
                    trigger.dispatch_event("click", {"detail": 1})
                    self.assertTrue(tooltip.is_visible())
                    page.locator("body").dispatch_event("pointerdown", {"pointerType": "touch", "pointerId": 91 + index})
                    self.assertTrue(tooltip.is_hidden())
                    self._set_data_details(page, slide_id, opened=False)

            self._activate(page, "ranked-state")
            self._set_data_details(page, "ranked-state", opened=True)
            navigation_trigger = self._scene(page, "ranked-state").locator(
                '[data-tooltip-for="north"]'
            ).first
            navigation_trigger.focus()
            navigation_trigger.press("Enter")
            navigation_tooltip = page.locator(
                f'#{navigation_trigger.get_attribute("aria-controls")}'
            )
            self.assertTrue(navigation_tooltip.is_visible())
            self._activate(page, "bar-state")
            self.assertTrue(navigation_tooltip.is_hidden())
            self.assertFalse(navigation_trigger.evaluate(
                "node => node === document.activeElement"
            ))

            self._activate(page, "ranked-state")
            self._set_data_details(page, "ranked-state", opened=True)
            navigation_trigger.focus()
            navigation_trigger.press("Enter")
            self.assertTrue(navigation_tooltip.is_visible())
            destination = page.locator(
                '#idrt-presenter-chrome [data-page-index="3"]'
            )
            destination.focus()
            page.evaluate(
                "() => { location.hash = '#slide=3&scenario=base'; }"
            )
            page.wait_for_function(
                """() => {
                  const scene = document.querySelector('[data-slide-id="bar-state"]');
                  return scene && !scene.hidden && scene.dataset.runtime === 'ready';
                }"""
            )
            self.assertTrue(navigation_tooltip.is_hidden())
            self.assertFalse(navigation_trigger.evaluate(
                "node => node === document.activeElement"
            ))
            self.assert_no_automatic_activity(session)
        finally:
            session.close()

    def test_live_svg_chart_band_updates_without_replacing_marks_or_domain_anchors(self) -> None:
        """Catches a semantic-only update hidden behind an unchanged static SVG."""
        for engine, mode in self.iter_matrix():
            session = self.open_deck(engine, mode, artifact=self.artifact)
            page = session.page
            try:
                self._wait_for_runtime(page)

                with self.subTest(engine=engine, mode=mode, component="ranked_list"):
                    self._activate(page, "ranked-state")
                    scene = self._scene(page, "ranked-state")
                    chart = self._live_svg_node(page, "ranked-state", "LiveChartBand")
                    domain_start = self._live_svg_node(page, "ranked-state", "LiveDomainStart")
                    domain_end = self._live_svg_node(page, "ranked-state", "LiveDomainEnd")
                    north = self._live_svg_node(page, "ranked-state", "LiveMark-north")
                    central = self._live_svg_node(page, "ranked-state", "LiveMark-central")
                    west = self._live_svg_node(page, "ranked-state", "LiveMark-west")
                    north_value = self._live_svg_node(page, "ranked-state", "LiveValue-north")
                    central_value = self._live_svg_node(page, "ranked-state", "LiveValue-central")
                    west_value = self._live_svg_node(page, "ranked-state", "LiveValue-west")
                    for name, locator in (
                        ("chart", chart),
                        ("domain-start", domain_start),
                        ("domain-end", domain_end),
                        ("north", north),
                        ("central", central),
                        ("west", west),
                        ("north-value", north_value),
                        ("central-value", central_value),
                        ("west-value", west_value),
                    ):
                        self.assertEqual(locator.count(), 1, name)
                    chart_handle = chart.element_handle()
                    north_handle = north.element_handle()
                    central_handle = central.element_handle()
                    west_handle = west.element_handle()
                    assert chart_handle and north_handle and central_handle and west_handle
                    start_before = self._fixed_svg_anchor(domain_start)
                    end_before = self._fixed_svg_anchor(domain_end)
                    north_y_before = float(north.locator("rect").get_attribute("y"))
                    central_y_before = float(central.locator("rect").get_attribute("y"))
                    west_opacity_before = float(west.get_attribute("opacity") or "1")
                    self.assertEqual(north_value.get_attribute("font-weight"), "600")
                    self.assertEqual(central_value.get_attribute("font-weight"), "normal")

                    scene.get_by_role("button", name="Constrained", exact=True).click()
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="ranked-state"] [data-view-item-id="west"]'
                        )?.dataset.removed === 'true'"""
                    )
                    north_y_after = float(north.locator("rect").get_attribute("y"))
                    central_y_after = float(central.locator("rect").get_attribute("y"))
                    west_opacity_after = float(west.get_attribute("opacity") or "1")
                    self.assertNotEqual(north_y_after, north_y_before)
                    self.assertNotEqual(central_y_after, central_y_before)
                    self.assertLess(west_opacity_after, west_opacity_before)
                    self.assertGreater(west_opacity_after, 0)
                    self.assertEqual(north_value.get_attribute("font-weight"), "normal")
                    self.assertEqual(central_value.get_attribute("font-weight"), "600")
                    self.assertIn("removed", (west_value.text_content() or "").lower())
                    self.assertEqual(self._fixed_svg_anchor(domain_start), start_before)
                    self.assertEqual(self._fixed_svg_anchor(domain_end), end_before)
                    for handle, locator in (
                        (chart_handle, chart),
                        (north_handle, north),
                        (central_handle, central),
                        (west_handle, west),
                    ):
                        self.assertTrue(handle.evaluate(
                            "(node, id) => node === document.getElementById(id)",
                            locator.get_attribute("id"),
                        ))

                    scene.get_by_role("button", name="Base", exact=True).click()
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="ranked-state"] [data-view-item-id="west"]'
                        )?.dataset.removed === 'false'"""
                    )
                    self.assertEqual(
                        float(north.locator("rect").get_attribute("y")),
                        north_y_before,
                    )
                    self.assertEqual(
                        float(central.locator("rect").get_attribute("y")),
                        central_y_before,
                    )
                    self.assertEqual(
                        float(west.get_attribute("opacity") or "1"),
                        west_opacity_before,
                    )
                    self.assertNotIn(
                        "removed", (west_value.text_content() or "").lower()
                    )
                    self.assertEqual(north_value.get_attribute("font-weight"), "600")
                    self.assertEqual(central_value.get_attribute("font-weight"), "normal")
                    scene.get_by_role(
                        "button", name="Constrained", exact=True
                    ).click()
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="ranked-state"] [data-view-item-id="west"]'
                        )?.dataset.removed === 'true'"""
                    )

                    toggle = scene.get_by_role(
                        "button", name="View static conclusion", exact=True
                    )
                    toggle.click()
                    self.assertTrue(scene.locator(".live-layer").is_hidden())
                    self.assertTrue(scene.locator(".fallback-layer").is_visible())
                    fallback_text = scene.locator(".fallback-layer").inner_text()
                    self.assertIn("North queue", fallback_text)
                    self.assertNotIn("removed", fallback_text.lower())
                    scene.get_by_role(
                        "button", name="Return to live view", exact=True
                    ).click()
                    self.assertTrue(chart_handle.evaluate("node => node.isConnected"))
                    self.assertEqual(
                        float(north.locator("rect").get_attribute("y")),
                        north_y_after,
                    )

                with self.subTest(engine=engine, mode=mode, component="bar_compare"):
                    self._activate(page, "bar-state")
                    scene = self._scene(page, "bar-state")
                    chart = self._live_svg_node(page, "bar-state", "LiveChartBand")
                    domain_start = self._live_svg_node(page, "bar-state", "LiveDomainStart")
                    domain_end = self._live_svg_node(page, "bar-state", "LiveDomainEnd")
                    mark = self._live_svg_node(page, "bar-state", "LiveMark-capacity")
                    label = self._live_svg_node(page, "bar-state", "LiveLabel-capacity")
                    value = self._live_svg_node(page, "bar-state", "LiveValue-capacity")
                    for node_name, locator in (
                        ("chart", chart),
                        ("domain-start", domain_start),
                        ("domain-end", domain_end),
                        ("mark", mark),
                        ("label", label),
                        ("value", value),
                    ):
                        self.assertEqual(locator.count(), 1, node_name)
                    chart_handle = chart.element_handle()
                    mark_handle = mark.element_handle()
                    label_handle = label.element_handle()
                    assert chart_handle and mark_handle and label_handle
                    start_before = self._fixed_svg_anchor(domain_start)
                    end_before = self._fixed_svg_anchor(domain_end)
                    width_before = float(mark.get_attribute("width"))
                    self.assertEqual(label.get_attribute("font-weight"), "600")
                    self.assertEqual((value.text_content() or "").strip(), "2 units")

                    self._select(page, "bar-state", "scenario").select_option("pressure")
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="bar-state"] [data-view-item-id="capacity"]'
                        )?.textContent.includes('3.0 units')"""
                    )
                    width_after = float(mark.get_attribute("width"))
                    self.assertGreater(width_after, width_before)
                    self.assertEqual(label.get_attribute("font-weight"), "normal")
                    self.assertEqual((value.text_content() or "").strip(), "3.0 units")
                    self.assertEqual(self._fixed_svg_anchor(domain_start), start_before)
                    self.assertEqual(self._fixed_svg_anchor(domain_end), end_before)
                    self.assertTrue(chart_handle.evaluate(
                        "(node, id) => node === document.getElementById(id)",
                        chart.get_attribute("id"),
                    ))
                    self.assertTrue(mark_handle.evaluate(
                        "(node, id) => node === document.getElementById(id)",
                        mark.get_attribute("id"),
                    ))
                    self.assertTrue(label_handle.evaluate(
                        "(node, id) => node === document.getElementById(id)",
                        label.get_attribute("id"),
                    ))

                    scene.get_by_role(
                        "button", name="View static conclusion", exact=True
                    ).click()
                    self.assertTrue(scene.locator(".live-layer").is_hidden())
                    self.assertTrue(scene.locator(".fallback-layer").is_visible())
                    self.assertIn("2 units", scene.locator(".fallback-layer").inner_text())
                    scene.get_by_role(
                        "button", name="Return to live view", exact=True
                    ).click()
                    self.assertTrue(mark_handle.evaluate("node => node.isConnected"))
                    self.assertEqual(float(mark.get_attribute("width")), width_after)

                with self.subTest(
                    engine=engine,
                    mode=mode,
                    component="recommendation_panel",
                ):
                    self._activate(page, "score-model")
                    scene = self._scene(page, "score-model")
                    chart = self._live_svg_node(page, "score-model", "LiveChartBand")
                    domain_start = self._live_svg_node(page, "score-model", "LiveDomainStart")
                    domain_end = self._live_svg_node(page, "score-model", "LiveDomainEnd")
                    cursor = self._live_svg_node(page, "score-model", "LiveScoreCursor")
                    early = self._live_svg_node(page, "score-model", "LiveBand-early")
                    ready = self._live_svg_node(page, "score-model", "LiveBand-ready")
                    score_value = self._live_svg_node(page, "score-model", "LiveScoreValue")
                    classification = self._live_svg_node(
                        page, "score-model", "LiveClassification"
                    )
                    for name, locator in (
                        ("chart", chart),
                        ("domain-start", domain_start),
                        ("domain-end", domain_end),
                        ("cursor", cursor),
                        ("early-band", early),
                        ("ready-band", ready),
                        ("score-value", score_value),
                        ("classification", classification),
                    ):
                        self.assertEqual(locator.count(), 1, name)
                    chart_handle = chart.element_handle()
                    cursor_handle = cursor.element_handle()
                    early_handle = early.element_handle()
                    ready_handle = ready.element_handle()
                    assert chart_handle and cursor_handle and early_handle and ready_handle
                    start_before = self._fixed_svg_anchor(domain_start)
                    end_before = self._fixed_svg_anchor(domain_end)
                    cursor_before = float(cursor.get_attribute("x1"))
                    early_opacity_before = float(early.get_attribute("opacity") or "1")
                    ready_opacity_before = float(ready.get_attribute("opacity") or "1")
                    self.assertEqual((score_value.text_content() or "").strip(), "0 points")
                    self.assertEqual((classification.text_content() or "").strip(), "Early")

                    self._set_range_index(page, "score-model", "1", "scale")
                    self._select(page, "score-model", "scope").select_option("large")
                    page.wait_for_function(
                        """() => document.querySelector(
                          '[data-slide-id="score-model"] [data-live-value="score"]'
                        )?.textContent === '5 points'"""
                    )
                    cursor_after = float(cursor.get_attribute("x1"))
                    early_opacity_after = float(early.get_attribute("opacity") or "1")
                    ready_opacity_after = float(ready.get_attribute("opacity") or "1")
                    self.assertGreater(cursor_after, cursor_before)
                    self.assertLess(early_opacity_after, early_opacity_before)
                    self.assertGreater(ready_opacity_after, ready_opacity_before)
                    self.assertEqual((score_value.text_content() or "").strip(), "5 points")
                    self.assertEqual((classification.text_content() or "").strip(), "Ready")
                    self.assertEqual(self._fixed_svg_anchor(domain_start), start_before)
                    self.assertEqual(self._fixed_svg_anchor(domain_end), end_before)
                    for handle, locator in (
                        (chart_handle, chart),
                        (cursor_handle, cursor),
                        (early_handle, early),
                        (ready_handle, ready),
                    ):
                        self.assertTrue(handle.evaluate(
                            "(node, id) => node === document.getElementById(id)",
                            locator.get_attribute("id"),
                        ))

                    scene.get_by_role(
                        "button", name="View static conclusion", exact=True
                    ).click()
                    self.assertTrue(scene.locator(".live-layer").is_hidden())
                    self.assertTrue(scene.locator(".fallback-layer").is_visible())
                    fallback_text = scene.locator(".fallback-layer").inner_text()
                    self.assertIn("0 points", fallback_text)
                    self.assertIn("Early", fallback_text)
                    scene.get_by_role(
                        "button", name="Return to live view", exact=True
                    ).click()
                    self.assertTrue(cursor_handle.evaluate("node => node.isConnected"))
                    self.assertEqual(float(cursor.get_attribute("x1")), cursor_after)

                self.assert_no_automatic_activity(session)
            finally:
                session.close()

    def test_live_static_print_reduced_motion_and_failure_keep_one_truthful_semantic_state(self) -> None:
        """Catches mixed fallback/live truth or a Task 5-only failure branch."""
        session = self.open_deck("chromium", "http", artifact=self.artifact)
        page = session.page
        try:
            self._wait_for_runtime(page)
            representatives = (
                ("ranked-state", "ranked_list"),
                ("bar-state", "bar_compare"),
                ("piecewise-model", "dot_plot"),
                ("score-model", "recommendation_panel"),
            )
            for slide_id, component in representatives:
                with self.subTest(slide_id=slide_id):
                    self._activate(page, slide_id)
                    scene = self._scene(page, slide_id)
                    self.assertTrue(scene.locator(f'[data-view-component="{component}"]').is_hidden())
                    self._set_data_details(page, slide_id, opened=True)
                    self.assertTrue(scene.locator(f'[data-view-component="{component}"]').is_visible())
                    self._set_data_details(page, slide_id, opened=False)
                    toggle = scene.get_by_role("button", name="View static conclusion", exact=True)
                    toggle_id = toggle.get_attribute("id")
                    toggle.click()
                    self.assertTrue(scene.locator(".fallback-layer").is_visible())
                    self.assertTrue(scene.locator(".live-layer").is_hidden())
                    live_toggle = scene.get_by_role(
                        "button", name="Return to live view", exact=True
                    )
                    self.assertEqual(live_toggle.inner_text(), "Return to live view")
                    for control in scene.locator("input, select, button").all():
                        if (
                            control.is_visible()
                            and control.get_attribute("id") != toggle_id
                        ):
                            self.assertTrue(
                                control.is_disabled()
                                or control.get_attribute("aria-disabled") == "true"
                                or control.get_attribute("data-global-control") == "true"
                            )
                    live_toggle.click()
                    self.assertTrue(scene.locator(".live-layer").is_visible())
                    self.assertTrue(scene.locator(".fallback-layer").is_hidden())

            page.emulate_media(media="print")
            for slide_id, _component in representatives:
                scene = self._scene(page, slide_id)
                self.assertTrue(scene.locator(".fallback-layer").is_visible())
                self.assertTrue(scene.locator(".live-layer").is_hidden())
            page.emulate_media(media="screen")

            # The same fail-all reducer transition is atomic for a Task 5 model.
            self._activate(page, "lookup-model")
            self._set_range_index(page, "lookup-model", "1")
            page.wait_for_function(
                """() => document.querySelector(
                  '[data-slide-id="lookup-model"] [data-live-value="result"]'
                )?.textContent === '8 units'"""
            )
            before_snapshot = page.evaluate("() => window.InteractiveDeck.snapshot()")
            before_hash = page.evaluate("() => location.hash")
            self.assert_no_automatic_activity(session)
            session.set_fault("evaluation")
            self._set_range_index(page, "lookup-model", "2")
            lookup_scene = self._scene(page, "lookup-model")
            page.wait_for_function(
                """() => document.querySelector(
                  '[data-slide-id="lookup-model"]'
                )?.dataset.runtime === 'failed'"""
            )
            session.set_fault(None)
            after_snapshot = page.evaluate("() => window.InteractiveDeck.snapshot()")
            before_page = before_snapshot["pages"][4]
            after_page = after_snapshot["pages"][4]
            self.assertEqual(after_page["inputs"], before_page["inputs"])
            self.assertEqual(after_page["outputs"], before_page["outputs"])
            self.assertEqual(after_page["outcome"], before_page["outcome"])
            self.assertEqual(after_page["failed"], "unavailable")
            self.assertEqual(after_page["viewMode"], "static")
            self.assertEqual(page.evaluate("() => location.hash"), before_hash)
            self.assertTrue(lookup_scene.locator(".fallback-layer").is_visible())
            self.assertTrue(lookup_scene.locator(".live-layer").is_hidden())
            page.evaluate(
                """() => setTimeout(() => {
                  throw new Error("TASK5_GLOBAL_FAIL_ALL");
                }, 0)"""
            )
            for slide_id, _component in representatives:
                scene = self._scene(page, slide_id)
                page.wait_for_function(
                    """id => document.querySelector(
                      `[data-slide-id="${id}"]`
                    )?.dataset.runtime === 'failed'""",
                    arg=slide_id,
                )
                self.assertFalse(
                    scene.locator(".fallback-layer").evaluate("node => node.hidden")
                )
                self.assertTrue(
                    scene.locator(".live-layer").evaluate("node => node.hidden")
                )
            self.assert_only_document_request(session)
            self.assertEqual(session.observations.page_errors, [])
            self.assertEqual(session.monitor()["transports"], [])
        finally:
            session.close()

        reduced = self.open_deck(
            "firefox",
            "http",
            artifact=self.artifact,
            reduced_motion="reduce",
        )
        try:
            self._wait_for_runtime(reduced.page)
            self._activate(reduced.page, "ranked-state")
            self._scene(reduced.page, "ranked-state").get_by_role(
                "button", name="Constrained", exact=True
            ).click()
            self.assertEqual(
                self._scene(reduced.page, "ranked-state").locator(
                    '[data-view-item-id="west"]'
                ).get_attribute("data-removed"),
                "true",
            )
            self._activate(reduced.page, "bar-state")
            self._select(reduced.page, "bar-state", "scenario").select_option("pressure")
            self._set_data_details(reduced.page, "bar-state", opened=True)
            self.assertIn(
                "3.0 units",
                self._scene(reduced.page, "bar-state").locator(
                    '[data-view-item-id="capacity"]'
                ).inner_text(),
            )
            self._set_data_details(reduced.page, "bar-state", opened=False)
            self._activate(reduced.page, "piecewise-model")
            self._set_range_index(reduced.page, "piecewise-model", "4")
            self.assertEqual(
                self._live_value(reduced.page, "piecewise-model", "result"),
                "11 units",
            )
            before_snapshot = reduced.page.evaluate(
                "() => window.InteractiveDeck.snapshot()"
            )
            before_page = before_snapshot["pages"][self.SLIDES["piecewise-model"] - 1]
            before_hash = reduced.page.evaluate("() => location.hash")
            reduced.page.evaluate(
                "() => { window.__E2E_MONITOR__.deckEvents.length = 0; }"
            )
            reduced.set_fault("geometry")
            self._set_range_index(reduced.page, "piecewise-model", "3")
            reduced.page.wait_for_function(
                """() => document.querySelector(
                  '[data-slide-id="piecewise-model"]'
                )?.dataset.runtime === 'failed'"""
            )
            reduced.set_fault(None)
            after_snapshot = reduced.page.evaluate(
                "() => window.InteractiveDeck.snapshot()"
            )
            after_page = after_snapshot["pages"][self.SLIDES["piecewise-model"] - 1]
            url_input = reduced.page.evaluate(
                """() => new URLSearchParams(
                  location.hash.slice(1)
                ).get('input')"""
            )
            self.assertEqual(after_page["inputs"], before_page["inputs"])
            self.assertEqual(after_page["outputs"], before_page["outputs"])
            self.assertEqual(after_page["outcome"], before_page["outcome"])
            self.assertEqual(after_page["inputs"]["input"], url_input)
            self.assertEqual(reduced.page.evaluate("() => location.hash"), before_hash)
            self.assertEqual(reduced.monitor()["deckEvents"], [])
            expected_fault_error = (
                "error",
                "[interactive-deck] page-6 E_INPUT: Interactive scene unavailable.",
            )
            console_errors = [
                entry for entry in reduced.observations.consoles
                if entry[0] == "error"
            ]
            console_errors, _csp_events = self.without_firefox_favicon_browser_noise(
                reduced,
                console_errors,
                reduced.monitor()["csp"],
                reduced.monitor()["transports"],
            )
            self.assertEqual(console_errors, [expected_fault_error])
            self.assertNotIn(
                "E2E_SECRET",
                " ".join(message for _level, message in reduced.observations.consoles),
            )
            reduced.observations.consoles.remove(expected_fault_error)
            self.assertTrue(
                self._scene(reduced.page, "piecewise-model").locator(
                    ".fallback-layer"
                ).is_visible()
            )
            self._activate(reduced.page, "score-model")
            self._set_range_index(reduced.page, "score-model", "1", "scale")
            self._select(reduced.page, "score-model", "scope").select_option("large")
            self.assertEqual(
                self._live_value(reduced.page, "score-model", "score"),
                "5 points",
            )
            self.assertTrue(reduced.page.evaluate(
                "() => matchMedia('(prefers-reduced-motion: reduce)').matches"
            ))
            self.assert_no_automatic_activity(reduced)
        finally:
            reduced.close()

    def test_runtime_uses_prebuilt_semantics_without_createelement_or_innerhtml(self) -> None:
        """Catches a new dynamic HTML injection path in Task 5 components."""
        sink_monitor = r"""
        (() => {
          const calls = [];
          Object.defineProperty(window, "__TASK5_DOM_SINKS__", {
            value: calls, writable: false, configurable: false
          });
          const createElement = Document.prototype.createElement;
          Document.prototype.createElement = function(...args) {
            calls.push({kind: "createElement", tag: String(args[0] || "")});
            return createElement.apply(this, args);
          };
          const descriptor = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
          if (descriptor && descriptor.get && descriptor.set) {
            Object.defineProperty(Element.prototype, "innerHTML", {
              configurable: descriptor.configurable,
              enumerable: descriptor.enumerable,
              get: descriptor.get,
              set(value) {
                calls.push({kind: "innerHTML", size: String(value).length});
                return descriptor.set.call(this, value);
              }
            });
          }
        })();
        """
        session = self.open_deck(
            "chromium",
            "http",
            artifact=self.artifact,
            init_script=sink_monitor,
        )
        try:
            self._wait_for_runtime(session.page)
            self._activate(session.page, "ranked-state")
            self._scene(session.page, "ranked-state").get_by_role(
                "button", name="Constrained", exact=True
            ).click()
            self._activate(session.page, "accordion")
            self._scene(session.page, "accordion").get_by_role(
                "button", name="Method", exact=True
            ).click()
            self.assertEqual(
                session.page.evaluate("() => window.__TASK5_DOM_SINKS__"),
                [],
            )
            self.assert_no_automatic_activity(session)
        finally:
            session.close()


class Task5ReviewedValidCasesE2ETests(InteractiveDeckBrowserTestCase):
    SLIDES = {
        "accordion-required": 1,
        "drilldown-open": 2,
        "ranked-long-ids": 3,
        "dot-long-ids": 4,
        "bar-twelve": 5,
        "ranked-twelve": 6,
    }

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        completed, artifact = build_reviewed_valid_fixture(
            cls.fixture_root / "task5-reviewed-valid"
        )
        if completed.returncode:
            raise AssertionError(
                "Task 5 reviewed-valid fixture build failed: "
                + completed.stderr.strip()
            )
        cls.artifact = artifact

    def _wait_for_runtime(self, page) -> None:
        page.wait_for_function(
            """() => window.InteractiveDeck &&
                typeof window.InteractiveDeck.snapshot === 'function'""",
            timeout=10_000,
        )

    def _scene(self, page, slide_id: str):
        return page.locator(f'[data-slide-id="{slide_id}"]')

    def _activate(self, page, slide_id: str) -> None:
        ordinal = self.SLIDES[slide_id]
        page.locator(
            f'#idrt-presenter-chrome [data-page-index="{ordinal}"]'
        ).click()
        page.wait_for_function(
            """slideId => {
              const scene = document.querySelector(`[data-slide-id="${slideId}"]`);
              return scene && !scene.hidden && scene.dataset.runtime === "ready";
            }""",
            arg=slide_id,
            timeout=10_000,
        )

    def _assert_live(self, page, slide_id: str) -> None:
        scene = self._scene(page, slide_id)
        self.assertEqual(scene.get_attribute("data-runtime"), "ready")
        page_state = page.evaluate("() => window.InteractiveDeck.snapshot()")[
            "pages"
        ][self.SLIDES[slide_id] - 1]
        self.assertEqual(page_state["viewMode"], "live")
        self.assertIsNone(page_state["failed"])

    def _live_svg_node(self, page, slide_id: str, source_id: str):
        ordinal = self.SLIDES[slide_id]
        return self._scene(page, slide_id).locator(
            f'.live-layer [id="idsvg-{ordinal}-live-shell-{source_id}"]'
        )

    def test_tampered_ranked_ranks_are_rejected_before_runtime_boot(self) -> None:
        """Catches browser validation accepting duplicate or impossible ranks."""
        html_text = self.artifact.read_text(encoding="utf-8")
        payload, _raw = decode_envelope_text(html_text)
        variants = {}
        for name, forged_rank in (("duplicate", 1), ("out-of-range", 3)):
            tampered = copy.deepcopy(payload)
            ranked_items = tampered["slides"][2]["scene"]["states"][0][
                "view"
            ]["items"]
            ranked_items[1]["rank"] = forged_rank
            encoded = replace_envelope_text(
                html_text,
                json.dumps(
                    tampered,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
            variants[name] = self.write_variant(
                f"task5-invalid-rank-{name}.interactive.html",
                encoded,
            )

        for engine, mode in self.iter_matrix():
            for name, artifact in variants.items():
                with self.subTest(engine=engine, mode=mode, variant=name):
                    session = self.open_deck(engine, mode, artifact=artifact)
                    page = session.page
                    try:
                        self.assertEqual(
                            page.locator("html").get_attribute(
                                "data-interactive-runtime"
                            ),
                            "static",
                        )
                        self.assertFalse(page.evaluate(
                            "() => typeof window.InteractiveDeck !== 'undefined'"
                        ))
                        self.assertEqual(
                            [
                                event for event in session.monitor()["deckEvents"]
                                if event["type"] == "ready"
                            ],
                            [],
                        )
                        ranked = self._scene(page, "ranked-long-ids")
                        self.assertNotEqual(
                            ranked.get_attribute("data-runtime"), "ready"
                        )
                        self.assertTrue(
                            ranked.locator(".fallback-layer").is_visible()
                        )
                        self.assertTrue(ranked.locator(".live-layer").is_hidden())
                        for control in ranked.locator(
                            "input, select, button"
                        ).all():
                            if control.is_visible():
                                self.assertTrue(
                                    control.is_disabled()
                                    or control.get_attribute("aria-disabled") == "true"
                                )
                        self.assert_only_document_request(session)
                        self.assertEqual(session.observations.page_errors, [])
                        self.assertEqual(session.monitor()["transports"], [])
                    finally:
                        session.close()

    def test_required_accordion_and_open_drilldown_preserve_declared_panel_state(self) -> None:
        """Catches a runtime that silently adds null to a required panel domain."""
        for engine, mode in self.iter_matrix():
            with self.subTest(engine=engine, mode=mode):
                session = self.open_deck(engine, mode, artifact=self.artifact)
                page = session.page
                try:
                    self._wait_for_runtime(page)

                    self._activate(page, "accordion-required")
                    accordion = self._scene(page, "accordion-required")
                    method = accordion.get_by_role("button", name="Method", exact=True)
                    boundary = accordion.get_by_role("button", name="Boundary", exact=True)
                    method_panel = accordion.locator(
                        f'#{method.get_attribute("aria-controls")}'
                    )
                    boundary_panel = accordion.locator(
                        f'#{boundary.get_attribute("aria-controls")}'
                    )
                    self.assertEqual(method.get_attribute("aria-expanded"), "true")
                    self.assertEqual(boundary.get_attribute("aria-expanded"), "false")
                    self.assertTrue(method_panel.is_visible())
                    self.assertTrue(boundary_panel.is_hidden())

                    method.click()
                    self.assertEqual(method.get_attribute("aria-expanded"), "true")
                    self.assertTrue(method_panel.is_visible())
                    self.assertNotIn("panel=null", page.evaluate("() => location.hash"))
                    self._assert_live(page, "accordion-required")

                    page.evaluate(
                        "() => { location.hash = '#slide=1&panel=boundary'; }"
                    )
                    boundary_panel.wait_for(state="visible")
                    self.assertEqual(method.get_attribute("aria-expanded"), "false")
                    self.assertEqual(boundary.get_attribute("aria-expanded"), "true")
                    self.assertIn("panel=boundary", page.evaluate("() => location.hash"))
                    self._assert_live(page, "accordion-required")

                    boundary.click()
                    self.assertEqual(boundary.get_attribute("aria-expanded"), "true")
                    self.assertTrue(boundary_panel.is_visible())
                    self.assertIn("panel=boundary", page.evaluate("() => location.hash"))

                    page.evaluate(
                        "() => { location.hash = '#slide=1&panel=method'; }"
                    )
                    method_panel.wait_for(state="visible")
                    self.assertEqual(method.get_attribute("aria-expanded"), "true")
                    self._assert_live(page, "accordion-required")

                    self._activate(page, "drilldown-open")
                    drilldown = self._scene(page, "drilldown-open")
                    opener = drilldown.get_by_role("button", name="Method", exact=True)
                    open_panel = drilldown.locator('[data-panel-id="method"]')
                    self.assertEqual(opener.get_attribute("aria-expanded"), "true")
                    self.assertTrue(open_panel.is_visible())
                    self._assert_live(page, "drilldown-open")

                    page.evaluate(
                        "() => { location.hash = '#slide=2&panel=boundary'; }"
                    )
                    boundary_drilldown = drilldown.locator(
                        '[data-panel-id="boundary"]'
                    )
                    boundary_drilldown.wait_for(state="visible")
                    self.assertIn("explicit threshold", boundary_drilldown.inner_text())
                    self._assert_live(page, "drilldown-open")
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_long_ranked_and_dot_ids_keep_the_same_nodes_through_reorder(self) -> None:
        """Catches position-keyed fallback IDs and index-keyed dot animation."""
        dot_write_monitor = r"""
        (() => {
          const writes = [];
          Object.defineProperty(window, "__TASK5_DOT_WRITES__", {
            value: writes, writable: false, configurable: false
          });
          const original = Element.prototype.setAttribute;
          Element.prototype.setAttribute = function(name, value) {
            const id = typeof this.id === "string" ? this.id : "";
            if ((name === "cx" || name === "cy") &&
                (id.includes("dot-alpha-") || id.includes("dot-beta-"))) {
              writes.push({id, name, value: Number(value)});
            }
            return original.call(this, name, value);
          };
        })();
        """
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.artifact,
                    init_script=dot_write_monitor,
                )
                page = session.page
                try:
                    self._wait_for_runtime(page)
                    self._activate(page, "ranked-long-ids")
                    ranked = self._scene(page, "ranked-long-ids")
                    ranked_chart = self._live_svg_node(
                        page, "ranked-long-ids", "LiveChartBand"
                    )
                    alpha_label = ranked_chart.locator("text").filter(
                        has_text="Long Alpha"
                    )
                    beta_label = ranked_chart.locator("text").filter(
                        has_text="Long Beta"
                    )
                    self.assertEqual(alpha_label.count(), 1)
                    self.assertEqual(beta_label.count(), 1)
                    alpha_mark = alpha_label.locator("xpath=..")
                    beta_mark = beta_label.locator("xpath=..")
                    alpha_label_handle = alpha_label.element_handle()
                    beta_label_handle = beta_label.element_handle()
                    alpha_mark_handle = alpha_mark.element_handle()
                    beta_mark_handle = beta_mark.element_handle()
                    assert alpha_label_handle and beta_label_handle
                    assert alpha_mark_handle and beta_mark_handle
                    alpha_y_before = float(
                        alpha_mark.locator("rect").get_attribute("y")
                    )
                    beta_y_before = float(beta_mark.locator("rect").get_attribute("y"))
                    ranked.get_by_role(
                        "button", name="Swap order", exact=True
                    ).click()
                    page.wait_for_function(
                        """() => location.hash.includes('scenario=swapped')"""
                    )
                    alpha_y_after = float(
                        alpha_mark.locator("rect").get_attribute("y")
                    )
                    beta_y_after = float(beta_mark.locator("rect").get_attribute("y"))
                    self.assertGreater(alpha_y_after, alpha_y_before)
                    self.assertLess(beta_y_after, beta_y_before)
                    self.assertIn("Long Alpha", alpha_label.text_content() or "")
                    self.assertIn("Long Beta", beta_label.text_content() or "")
                    for handle, locator in (
                        (alpha_label_handle, alpha_label),
                        (beta_label_handle, beta_label),
                        (alpha_mark_handle, alpha_mark),
                        (beta_mark_handle, beta_mark),
                    ):
                        self.assertTrue(handle.evaluate(
                            "(node, id) => node === document.getElementById(id)",
                            locator.get_attribute("id"),
                        ))
                    self._assert_live(page, "ranked-long-ids")

                    self._activate(page, "dot-long-ids")
                    alpha_dot = self._live_svg_node(
                        page, "dot-long-ids", LONG_DOT_ALPHA
                    )
                    beta_dot = self._live_svg_node(page, "dot-long-ids", LONG_DOT_BETA)
                    dot_chart = self._live_svg_node(
                        page, "dot-long-ids", "LiveChartBand"
                    )
                    alpha_dot_label = dot_chart.locator("text").filter(
                        has_text="Dot Alpha"
                    )
                    beta_dot_label = dot_chart.locator("text").filter(
                        has_text="Dot Beta"
                    )
                    self.assertEqual(alpha_dot_label.count(), 1)
                    self.assertEqual(beta_dot_label.count(), 1)
                    alpha_dot_handle = alpha_dot.element_handle()
                    beta_dot_handle = beta_dot.element_handle()
                    alpha_dot_label_handle = alpha_dot_label.element_handle()
                    beta_dot_label_handle = beta_dot_label.element_handle()
                    assert alpha_dot_handle and beta_dot_handle
                    assert alpha_dot_label_handle and beta_dot_label_handle
                    alpha_before = (
                        float(alpha_dot.get_attribute("cx")),
                        float(alpha_dot.get_attribute("cy")),
                    )
                    beta_before = (
                        float(beta_dot.get_attribute("cx")),
                        float(beta_dot.get_attribute("cy")),
                    )
                    alpha_fill_before = alpha_dot.get_attribute("fill")
                    beta_fill_before = beta_dot.get_attribute("fill")
                    self.assertEqual(alpha_dot.get_attribute("r"), "9")
                    self.assertEqual(beta_dot.get_attribute("r"), "7")
                    self.assertNotEqual(alpha_fill_before, beta_fill_before)
                    self.assertEqual(alpha_dot_label.get_attribute("font-weight"), "600")
                    self.assertEqual(beta_dot_label.get_attribute("font-weight"), "normal")
                    page.evaluate("() => window.__TASK5_DOT_WRITES__.splice(0)")
                    self._scene(page, "dot-long-ids").get_by_role(
                        "button", name="Swap points", exact=True
                    ).dispatch_event("click")
                    page.wait_for_function(
                        """([alphaId, betaId, alphaX, alphaY, betaX, betaY]) => {
                          const prefix = 'idsvg-4-live-shell-';
                          const alpha = document.getElementById(prefix + alphaId);
                          const beta = document.getElementById(prefix + betaId);
                          return alpha && beta &&
                            alpha.getAttribute('cx') !== alphaX &&
                            alpha.getAttribute('cy') !== alphaY &&
                            beta.getAttribute('cx') !== betaX &&
                            beta.getAttribute('cy') !== betaY;
                        }""",
                        arg=[
                            LONG_DOT_ALPHA,
                            LONG_DOT_BETA,
                            f"{alpha_before[0]:.1f}",
                            f"{alpha_before[1]:.1f}",
                            f"{beta_before[0]:.1f}",
                            f"{beta_before[1]:.1f}",
                        ],
                    )
                    page.wait_for_timeout(300)
                    alpha_after = (
                        float(alpha_dot.get_attribute("cx")),
                        float(alpha_dot.get_attribute("cy")),
                    )
                    beta_after = (
                        float(beta_dot.get_attribute("cx")),
                        float(beta_dot.get_attribute("cy")),
                    )
                    self.assertGreater(alpha_after[0], alpha_before[0])
                    self.assertLess(alpha_after[1], alpha_before[1])
                    self.assertLess(beta_after[0], beta_before[0])
                    self.assertGreater(beta_after[1], beta_before[1])
                    self.assertEqual(alpha_dot.get_attribute("r"), "7")
                    self.assertEqual(beta_dot.get_attribute("r"), "9")
                    self.assertEqual(alpha_dot.get_attribute("fill"), beta_fill_before)
                    self.assertEqual(beta_dot.get_attribute("fill"), alpha_fill_before)
                    self.assertEqual(alpha_dot_label.get_attribute("font-weight"), "normal")
                    self.assertEqual(beta_dot_label.get_attribute("font-weight"), "600")
                    self.assertTrue(alpha_dot_handle.evaluate(
                        "(node, id) => node === document.getElementById(id)",
                        alpha_dot.get_attribute("id"),
                    ))
                    self.assertTrue(beta_dot_handle.evaluate(
                        "(node, id) => node === document.getElementById(id)",
                        beta_dot.get_attribute("id"),
                    ))
                    self.assertTrue(alpha_dot_label_handle.evaluate(
                        "(node, id) => node === document.getElementById(id)",
                        alpha_dot_label.get_attribute("id"),
                    ))
                    self.assertTrue(beta_dot_label_handle.evaluate(
                        "(node, id) => node === document.getElementById(id)",
                        beta_dot_label.get_attribute("id"),
                    ))
                    writes = page.evaluate("() => window.__TASK5_DOT_WRITES__.slice()")
                    for item_id, before, after in (
                        (LONG_DOT_ALPHA, alpha_before, alpha_after),
                        (LONG_DOT_BETA, beta_before, beta_after),
                    ):
                        x_values = [
                            row["value"] for row in writes
                            if row["id"].endswith(item_id) and row["name"] == "cx"
                        ]
                        y_values = [
                            row["value"] for row in writes
                            if row["id"].endswith(item_id) and row["name"] == "cy"
                        ]
                        self.assertGreater(len(x_values), 1)
                        self.assertGreater(len(y_values), 1)
                        self.assertTrue(all(
                            min(before[0], after[0]) <= value <= max(before[0], after[0])
                            for value in x_values
                        ))
                        self.assertTrue(all(
                            min(before[1], after[1]) <= value <= max(before[1], after[1])
                            for value in y_values
                        ))
                    self._assert_live(page, "dot-long-ids")
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_twelve_item_bar_and_ranked_marks_fit_without_overlap_or_clipping(self) -> None:
        """Catches a fixed row gap that clips or overlaps compiler-valid views."""
        def assert_chart_fits(page, slide_id: str, *, reversed_state: bool) -> None:
            chart = self._live_svg_node(page, slide_id, "LiveChartBand")
            clip = chart.evaluate(
                r"""node => {
                  const reference = /^url\(#([^\)]+)\)$/.exec(node.getAttribute('clip-path'));
                  const rect = reference && document.getElementById(reference[1])?.querySelector('rect');
                  if (!rect) return null;
                  const x = Number(rect.getAttribute('x'));
                  const y = Number(rect.getAttribute('y'));
                  return {x, y, right: x + Number(rect.getAttribute('width')),
                    bottom: y + Number(rect.getAttribute('height'))};
                }"""
            )
            self.assertIsNotNone(clip)
            assert clip is not None
            self.assertGreater(clip["right"], clip["x"])
            self.assertGreater(clip["bottom"], clip["y"])
            ordinal = self.SLIDES[slide_id]
            marks = chart.locator(f'[id^="idsvg-{ordinal}-live-shell-LiveMark-"]')
            values = chart.locator(f'[id^="idsvg-{ordinal}-live-shell-LiveValue-"]')
            labels = chart.locator(f'[id^="idsvg-{ordinal}-live-shell-LiveLabel-"]')
            self.assertEqual(marks.count(), 12)
            self.assertEqual(values.count(), 12)
            self.assertEqual(labels.count(), 12 if slide_id == "bar-twelve" else 0)
            domain_start = self._live_svg_node(page, slide_id, "LiveDomainStart")
            domain_end = self._live_svg_node(page, slide_id, "LiveDomainEnd")
            domain_width = float(domain_end.get_attribute("x")) - float(domain_start.get_attribute("x"))
            self.assertGreater(domain_width, 0)
            intervals = []
            for index in range(12):
                mark = marks.nth(index)
                rect = mark if slide_id == "bar-twelve" else mark.locator("rect")
                x = float(rect.get_attribute("x"))
                y = float(rect.get_attribute("y"))
                width = float(rect.get_attribute("width"))
                height = float(rect.get_attribute("height"))
                if slide_id == "bar-twelve":
                    self.assertGreater(width, 0)
                else:
                    # This fixture has ranks but no numeric metric: do not
                    # invent magnitude by drawing a full-width metric bar.
                    self.assertEqual(width, 0)
                self.assertGreaterEqual(x, clip["x"])
                self.assertLessEqual(x + width, clip["right"])
                self.assertGreaterEqual(y, clip["y"])
                self.assertLessEqual(y + height, clip["bottom"])
                if slide_id == "bar-twelve":
                    intervals.append((y, y + height, index))
                    expected_value = 12 - index if reversed_state else index + 1
                    self.assertAlmostEqual(width / domain_width, expected_value / 12, delta=0.001)
                value = values.nth(index)
                value_y = float(value.get_attribute("y"))
                font_size = float(value.get_attribute("font-size"))
                self.assertGreaterEqual(value_y, clip["y"] + font_size)
                self.assertLessEqual(value_y, clip["bottom"])
                self.assertGreaterEqual(font_size, 12)
                self.assertTrue((value.text_content() or "").strip())
                if slide_id == "ranked-twelve":
                    label_bounds = value.evaluate("node => { const box = node.getBBox(); return {y: box.y, height: box.height}; }")
                    self.assertGreater(label_bounds["height"], 0)
                    intervals.append((label_bounds["y"], label_bounds["y"] + label_bounds["height"], index))
            for text_node in (*values.all(), *labels.all()):
                bounds = text_node.evaluate(
                    """node => {
                      const box = node.getBBox();
                      return {x: box.x, y: box.y, width: box.width, height: box.height};
                    }"""
                )
                self.assertGreaterEqual(bounds["x"], clip["x"])
                self.assertLessEqual(bounds["x"] + bounds["width"], clip["right"])
                self.assertGreaterEqual(bounds["y"], clip["y"])
                self.assertLessEqual(bounds["y"] + bounds["height"], clip["bottom"])
            intervals.sort()
            for previous, following in zip(intervals, intervals[1:]):
                self.assertLessEqual(previous[1], following[0])
            if slide_id == "ranked-twelve":
                expected_order = list(range(11, -1, -1)) if reversed_state else list(range(12))
                self.assertEqual([interval[2] for interval in intervals], expected_order)
            self._assert_live(page, slide_id)

        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=self.artifact)
                page = session.page
                try:
                    self._wait_for_runtime(page)
                    for slide_id in ("bar-twelve", "ranked-twelve"):
                        with self.subTest(engine=engine, slide_id=slide_id):
                            self._activate(page, slide_id)
                            assert_chart_fits(page, slide_id, reversed_state=False)
                            scene = self._scene(page, slide_id)
                            if slide_id == "bar-twelve":
                                scene.locator("select[data-control-select]").select_option("reverse")
                            else:
                                scene.get_by_role("button", name="Reverse ranks", exact=True).click()
                            assert_chart_fits(page, slide_id, reversed_state=True)

                    page.set_viewport_size({"width": 390, "height": 844})
                    self._activate(page, "ranked-twelve")
                    self.assertLessEqual(page.evaluate(
                        "() => document.documentElement.scrollWidth"
                    ), page.evaluate("() => document.documentElement.clientWidth") + 1)
                    svg_box = self._scene(page, "ranked-twelve").locator(
                        ".live-layer svg"
                    ).bounding_box()
                    self.assertIsNotNone(svg_box)
                    assert svg_box is not None
                    self.assertGreaterEqual(svg_box["x"], -1)
                    self.assertLessEqual(svg_box["x"] + svg_box["width"], 391)
                    control = self._scene(page, "ranked-twelve").get_by_role(
                        "button", name="Reverse ranks", exact=True
                    )
                    control.scroll_into_view_if_needed()
                    control_box = control.bounding_box()
                    self.assertIsNotNone(control_box)
                    assert control_box is not None
                    self.assertGreaterEqual(control_box["x"], 0)
                    self.assertLessEqual(control_box["x"] + control_box["width"], 390)
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()


if __name__ == "__main__":
    unittest.main()
