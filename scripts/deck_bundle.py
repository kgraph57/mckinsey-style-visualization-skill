"""Deterministic, self-contained bundle boundary for interactive decks.

This module accepts only compiler-produced data and renderer-produced SVG that
has crossed :func:`validate_renderer_svg`.  It deliberately does not evaluate
models or load author files.
"""
from __future__ import annotations

import base64
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

if __package__:
    from .interactive_contract import BASE_EXPONENTS, ISO_CURRENCIES, canonical_decimal
    from .interactive_scene import render_narration, safe_source_url
else:
    from interactive_contract import BASE_EXPONENTS, ISO_CURRENCIES, canonical_decimal
    from interactive_scene import render_narration, safe_source_url


SVG_NS = "http://www.w3.org/2000/svg"
MAX_ENVELOPE_BYTES = 16 * 1024 * 1024
MAX_HTML_BYTES = 48 * 1024 * 1024
MAX_RAW_SVG_BYTES = 4 * 1024 * 1024
MAX_SVG_ELEMENTS_BY_ROLE = {"fallback": 8_000, "live-shell": 1_024}
MAX_SVG_DEPTH = 128
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 250_000
MAX_JSON_STRINGS = 100_000
MAX_JSON_STRING_BYTES = 8 * 1024 * 1024
MAX_DOM_ELEMENTS = 50_000
MAX_DOM_ELEMENTS_PER_SLIDE = 10_000
MAX_SLIDES = 64
MAX_VIEW_ITEMS = 768
MAX_TARGETS = 4_096
MAX_STEPS = 5_120
MAX_SCENE_WAIT_MS = 30_000
MAX_DECK_WAIT_MS = 600_000
MAX_ACCEPTED_STATES_PER_DECK = 65_536
DEFAULT_DEMO_PAGE_PAUSE_MS = 800

_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_SVG_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_UNSAFE_IDS = frozenset(("__proto__", "prototype", "constructor"))
_NUMBER_TOKEN = r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
_NUMBER = re.compile(rf"^{_NUMBER_TOKEN}$")
_JSON_NUMBER_LEXEME = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_COLOR = re.compile(r"^(?:#[0-9A-Fa-f]{6}|none)$")
_PATH = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9+., eE-]+$")
_POINTS = re.compile(r"^[0-9+., eE-]+$")
_FONT_FAMILIES = frozenset((
    "Georgia, 'Times New Roman', 'Hiragino Mincho ProN', 'Yu Mincho', serif",
    "'Helvetica Neue', Helvetica, Arial, 'Hiragino Sans', 'Yu Gothic', 'Noto Sans JP', 'Meiryo', sans-serif",
))
_VALIDATED_SVG_SEAL = object()
_UI_TEXT = {
    "en": {
        "sources": "Sources",
        "assumptions": "Assumptions",
        "formula": "Formula",
        "basis": "Basis",
        "input_range": "Input range",
        "print_state": "Print state",
        "lineage": "Lineage",
        "step": "Step",
        "previous": "Previous",
        "next": "Next",
        "slide_links": "Slide links",
        "skip": "Skip to slides",
        "slide_navigation": "Slide navigation",
        "evidence_title": "Evidence",
        "close": "Close",
        "reset": "Reset",
        "static_view": "View static conclusion",
        "live_view": "Return to live view",
        "failure": "Interactive view unavailable. Static baseline restored.",
        "no_decision_change": "No decision change within the tested range",
        "overview": "Overview",
        "replay": "Replay",
        "demo": "Demo",
        "fullscreen": "Full screen",
        "help": "Help",
        "overview_title": "Slide overview",
        "help_title": "Presenter help",
        "presenter_controls": "Presenter controls",
        "presenter_status": "Presenter status",
        "shortcut_overview": "Open slide overview",
        "shortcut_replay": "Reset and replay the current slide",
        "shortcut_demo": "Run the curated deck demo",
        "shortcut_fullscreen": "Toggle full screen",
        "shortcut_help": "Open presenter help",
        "shortcut_close": "Close the top panel",
        "slide": "Slide",
    },
    "ja": {
        "sources": "出典",
        "assumptions": "仮定",
        "formula": "計算式",
        "basis": "根拠区分",
        "input_range": "入力範囲",
        "print_state": "印刷時の値",
        "lineage": "計算経路",
        "step": "刻み幅",
        "previous": "前へ",
        "next": "次へ",
        "slide_links": "スライド内リンク",
        "skip": "スライドへ移動",
        "slide_navigation": "スライドナビゲーション",
        "evidence_title": "根拠",
        "close": "閉じる",
        "reset": "初期値に戻す",
        "static_view": "静的な結論を表示",
        "live_view": "動的表示に戻る",
        "failure": "動的表示を利用できません。初期状態を表示します。",
        "no_decision_change": "検証範囲内では判定は変わりません",
        "overview": "一覧",
        "replay": "リプレイ",
        "demo": "デモ",
        "fullscreen": "全画面",
        "help": "ヘルプ",
        "overview_title": "スライド一覧",
        "help_title": "プレゼンターヘルプ",
        "presenter_controls": "プレゼンター操作",
        "presenter_status": "プレゼンター状態",
        "shortcut_overview": "スライド一覧を開く",
        "shortcut_replay": "現在のスライドを初期化して再表示",
        "shortcut_demo": "デッキのデモを実行",
        "shortcut_fullscreen": "全画面表示を切り替える",
        "shortcut_help": "プレゼンターヘルプを開く",
        "shortcut_close": "一番上のパネルを閉じる",
        "slide": "スライド",
    },
}


@dataclass(frozen=True)
class RuntimeAssets:
    css: bytes
    js: bytes


@dataclass(frozen=True)
class ValidatedSvg:
    serialized: str
    ids: tuple[str, ...]
    element_count: int
    # Attestation fields are init=False so dataclasses.replace() deliberately drops
    # the validator attestation instead of carrying it onto changed bytes.
    _seal: object = field(init=False, default=None, repr=False, compare=False)
    _integrity: bytes = field(init=False, default=b"", repr=False, compare=False)
    _slide_ordinal: int = field(init=False, default=0, repr=False, compare=False)
    _role: str = field(init=False, default="", repr=False, compare=False)


@dataclass(frozen=True)
class BundleSlide:
    slide_id: str
    headline: str
    source: str
    fallback_svg: ValidatedSvg
    static_summary: dict
    scene: dict | None
    live_shell_svg: ValidatedSvg | None
    display: dict | None
    decision_range_message: str | None = None
    # Presentation only: never included in the compiled audience-data envelope.
    visual_layout: str | None = None


@dataclass(frozen=True)
class BundleIssue:
    code: str
    location: str
    message: str


class BundleValidationError(ValueError):
    def __init__(self, issues: tuple[BundleIssue, ...] | list[BundleIssue]):
        self.issues = tuple(issues)
        first = self.issues[0] if self.issues else BundleIssue("bundle", "<bundle>", "invalid bundle")
        super().__init__(f"{first.location} [{first.code}]: {first.message}")


def _raise(code: str, location: str, message: str) -> None:
    raise BundleValidationError((BundleIssue(code, location, message),))


def _is_https_source(value: str) -> bool:
    try:
        return urlsplit(value).scheme.lower() == "https"
    except (TypeError, ValueError):
        return False


def _text(value: object, location: str, maximum: int = 2_000, *, empty: bool = True) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        _raise("text", location, "expected Unicode text")
    if len(value) > maximum or any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        _raise("text", location, f"expected at most {maximum} Unicode scalar values")
    return value


def _identifier(value: object, location: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value) or value in _UNSAFE_IDS:
        _raise("identifier", location, "expected a safe stable interactive ID")
    return value


def _walk_json(value: object) -> None:
    nodes = strings = string_bytes = 0
    stack: list[tuple[object, int]] = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            _raise("json_depth", "<envelope>", f"JSON depth exceeds {MAX_JSON_DEPTH}")
        nodes += 1
        if nodes > MAX_JSON_NODES:
            _raise("json_nodes", "<envelope>", f"JSON nodes exceed {MAX_JSON_NODES}")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    _raise("json_key", "<envelope>", "JSON object keys must be strings")
                if any(0xD800 <= ord(char) <= 0xDFFF for char in key):
                    _raise("json_unicode", "<envelope>", "lone surrogate is not valid in a JSON object key")
                if key in _UNSAFE_IDS:
                    _raise("identifier", "<envelope>", "unsafe registry key is forbidden")
                strings += 1
                string_bytes += len(key.encode("utf-8", "strict"))
                nodes += 1  # property names count toward the budget
                stack.append((child, depth + 1))
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in reversed(item))
        elif isinstance(item, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                _raise("json_unicode", "<envelope>", "lone surrogate is not valid audience data")
            strings += 1
            string_bytes += len(item.encode("utf-8", "strict"))
        elif item is None or isinstance(item, (bool, int)):
            pass
        elif isinstance(item, float):
            _raise("json_number", "<envelope>", "analytical numbers must already be canonical strings")
        else:
            _raise("json_type", "<envelope>", f"unsupported JSON value {type(item).__name__}")
        if strings > MAX_JSON_STRINGS:
            _raise("json_strings", "<envelope>", f"JSON strings exceed {MAX_JSON_STRINGS}")
        if string_bytes > MAX_JSON_STRING_BYTES:
            _raise("json_string_bytes", "<envelope>", "JSON string bytes exceed 8 MiB")


class _EnvelopeJsonPreflight:
    """Validate JSON grammar and budgets before allocating the decoded tree."""

    def __init__(self, text: str):
        self.text = text
        self.index = 0
        self.nodes = 0
        self.strings = 0
        self.string_bytes = 0

    def run(self) -> None:
        self._space()
        self._value(0)
        self._space()
        if self.index != len(self.text):
            _raise("envelope_json", "<envelope>", "invalid bounded JSON")

    def _space(self) -> None:
        while self.index < len(self.text) and self.text[self.index] in " \t\r\n":
            self.index += 1

    def _limits(self) -> None:
        if self.nodes > MAX_JSON_NODES:
            _raise("json_nodes", "<envelope>", f"JSON nodes exceed {MAX_JSON_NODES}")
        if self.strings > MAX_JSON_STRINGS:
            _raise("json_strings", "<envelope>", f"JSON strings exceed {MAX_JSON_STRINGS}")
        if self.string_bytes > MAX_JSON_STRING_BYTES:
            _raise("json_string_bytes", "<envelope>", "JSON string bytes exceed 8 MiB")

    def _node(self, depth: int) -> None:
        if depth > MAX_JSON_DEPTH:
            _raise("json_depth", "<envelope>", f"JSON depth exceeds {MAX_JSON_DEPTH}")
        self.nodes += 1
        self._limits()

    def _string(self) -> str:
        if self.index >= len(self.text) or self.text[self.index] != '"':
            _raise("envelope_json", "<envelope>", "invalid bounded JSON")
        try:
            value, following = json.decoder.scanstring(self.text, self.index + 1, True)
        except (UnicodeError, ValueError):
            _raise("envelope_json", "<envelope>", "invalid bounded JSON")
        self.index = following
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            _raise("json_unicode", "<envelope>", "lone surrogate is not valid audience data")
        try:
            encoded_size = len(value.encode("utf-8", "strict"))
        except UnicodeError:
            _raise("json_unicode", "<envelope>", "invalid Unicode string")
        self.strings += 1
        self.string_bytes += encoded_size
        self._limits()
        return value

    def _value(self, depth: int) -> None:
        self._space()
        self._node(depth)
        if self.index >= len(self.text):
            _raise("envelope_json", "<envelope>", "invalid bounded JSON")
        token = self.text[self.index]
        if token == "{":
            self._object(depth)
            return
        if token == "[":
            self._array(depth)
            return
        if token == '"':
            self._string()
            return
        for literal in ("true", "false", "null"):
            if self.text.startswith(literal, self.index):
                self.index += len(literal)
                self._delimiter()
                return
        match = _JSON_NUMBER_LEXEME.match(self.text, self.index)
        if match is None:
            _raise("envelope_json", "<envelope>", "invalid bounded JSON")
        self.index = match.end()
        self._delimiter()

    def _delimiter(self) -> None:
        if self.index < len(self.text) and self.text[self.index] not in " \t\r\n,]}":
            _raise("envelope_json", "<envelope>", "invalid bounded JSON")

    def _object(self, depth: int) -> None:
        self.index += 1
        self._space()
        seen: set[str] = set()
        if self.index < len(self.text) and self.text[self.index] == "}":
            self.index += 1
            return
        while True:
            self.nodes += 1
            self._limits()
            key = self._string()
            if key in seen:
                _raise("duplicate_json_key", "<envelope>", "duplicate JSON key")
            seen.add(key)
            self._space()
            if self.index >= len(self.text) or self.text[self.index] != ":":
                _raise("envelope_json", "<envelope>", "invalid bounded JSON")
            self.index += 1
            self._value(depth + 1)
            self._space()
            if self.index >= len(self.text):
                _raise("envelope_json", "<envelope>", "invalid bounded JSON")
            separator = self.text[self.index]
            self.index += 1
            if separator == "}":
                return
            if separator != ",":
                _raise("envelope_json", "<envelope>", "invalid bounded JSON")
            self._space()

    def _array(self, depth: int) -> None:
        self.index += 1
        self._space()
        if self.index < len(self.text) and self.text[self.index] == "]":
            self.index += 1
            return
        while True:
            self._value(depth + 1)
            self._space()
            if self.index >= len(self.text):
                _raise("envelope_json", "<envelope>", "invalid bounded JSON")
            separator = self.text[self.index]
            self.index += 1
            if separator == "]":
                return
            if separator != ",":
                _raise("envelope_json", "<envelope>", "invalid bounded JSON")
            self._space()


_SCENE_KEYS = frozenset((
    "version", "slideId", "type", "locale", "scale", "purpose", "decisionJob",
    "interactionRationale", "initialState", "printState", "controls", "quantities",
    "outputDefinitions", "evidence", "invariants", "fallback", "targets", "steps",
    "narration", "initialEvaluation", "model", "reporting", "decisionContract", "view",
    "states",
))


def _validate_summary(value: object, location: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"headline", "source", "paragraphs", "values", "decision"}:
        _raise("summary_shape", location, "expected closed static summary")
    _text(value["headline"], location + "/headline", 500)
    _text(value["source"], location + "/source", 500)
    if not isinstance(value["paragraphs"], list):
        _raise("summary_shape", location + "/paragraphs", "expected text array")
    for index, paragraph in enumerate(value["paragraphs"]):
        _text(paragraph, f"{location}/paragraphs/{index}", 2_000)
    if not isinstance(value["values"], list):
        _raise("summary_shape", location + "/values", "expected value array")
    seen: set[str] = set()
    for index, item in enumerate(value["values"]):
        if not isinstance(item, dict) or set(item) != {"id", "label", "text"}:
            _raise("summary_shape", f"{location}/values/{index}", "expected id, label and text")
        identifier = _identifier(item["id"], f"{location}/values/{index}/id")
        if identifier in seen:
            _raise("duplicate_id", f"{location}/values/{index}/id", "duplicate summary value ID")
        seen.add(identifier)
        _text(item["label"], f"{location}/values/{index}/label", 500)
        _text(item["text"], f"{location}/values/{index}/text", 500)
    decision = value["decision"]
    if decision is not None:
        if not isinstance(decision, dict) or set(decision) != {"status", "recommendation"}:
            _raise("summary_shape", location + "/decision", "expected status and recommendation")
        _text(decision["status"], location + "/decision/status", 500)
        _text(decision["recommendation"], location + "/decision/recommendation", 500)
    return value


def _validate_display(value: object, location: str) -> dict | None:
    if value is None:
        return None
    keys = {"staticSummary", "baselineAnnotation", "thresholdText", "axisTickLabels"}
    if not isinstance(value, dict) or set(value) != keys:
        _raise("display_shape", location, "expected closed display bridge")
    _validate_summary(value["staticSummary"], location + "/staticSummary")
    _text(value["baselineAnnotation"], location + "/baselineAnnotation", 2_000)
    if value["thresholdText"] is not None:
        _text(value["thresholdText"], location + "/thresholdText", 500)
    ticks = value["axisTickLabels"]
    if ticks is not None:
        if not isinstance(ticks, dict) or set(ticks) != {"x", "y"}:
            _raise("display_shape", location + "/axisTickLabels", "expected x and y tick pairs")
        for axis in ("x", "y"):
            if not isinstance(ticks[axis], list) or len(ticks[axis]) != 2:
                _raise("display_shape", location + f"/axisTickLabels/{axis}", "expected two tick labels")
            for index, label in enumerate(ticks[axis]):
                _text(label, location + f"/axisTickLabels/{axis}/{index}", 500)
    return value


def _format_scene_value(scene: dict, value_text: str, quantity_id: str, precision: int) -> str:
    value = Decimal(value_text)
    with localcontext() as context:
        context.prec = 40
        rounded = value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    number = format(abs(rounded), f",.{precision}f")
    sign = "−" if rounded < 0 else ""
    display = scene["quantities"][quantity_id]["display"]
    if display.startswith(("$", "€", "£", "¥", "￥")):
        number = display[0] + number + display[1:]
    else:
        number += ("" if display == "%" else " ") + display
    return sign + number


def _scene_numeric_text(scene: dict, output_id: str) -> str:
    definition = scene["outputDefinitions"][output_id]
    typed = scene["initialEvaluation"]["outputs"][output_id]
    return _format_scene_value(
        scene,
        typed["value"],
        definition["quantity"],
        definition["round"],
    )


def _display_candidates(
    scene: dict,
    value_text: str,
    quantity_id: str,
    maximum_precision: int,
) -> tuple[str, ...]:
    minimum_precision = max(0, -Decimal(value_text).as_tuple().exponent)
    return tuple(
        _format_scene_value(scene, value_text, quantity_id, precision)
        for precision in range(minimum_precision, maximum_precision + 1)
    )


def _validate_task4_scene_summary(
    scene: dict,
    summary: dict,
    display: dict,
    location: str,
) -> None:
    reporting = scene["reporting"]
    output_ids = [reporting["primaryOutput"], *reporting["secondaryOutputs"]]
    expected_values = [
        {
            "id": output_id,
            "label": scene["outputDefinitions"][output_id]["label"],
            "text": _scene_numeric_text(scene, output_id),
        }
        for output_id in output_ids
    ]
    decision = scene["initialEvaluation"].get("decision")
    expected_decision = None if decision is None else {
        "status": decision["status"],
        "recommendation": decision["recommendation"],
    }
    invariants = scene["invariants"]
    expected_paragraphs: list[str] = []
    if invariants.get("subline"):
        expected_paragraphs.append(invariants["subline"])
    view = scene["view"]
    ticks = display["axisTickLabels"]
    display_matches_scene = ticks is not None
    if ticks is not None:
        for axis in ("x", "y"):
            quantity_id = view[axis + "Quantity"]
            for index, endpoint in enumerate(view[axis + "Domain"]):
                display_matches_scene = display_matches_scene and ticks[axis][index] in _display_candidates(
                    scene,
                    endpoint,
                    quantity_id,
                    6,
                )

    decision_contract = scene.get("decisionContract")
    if decision_contract is None:
        display_matches_scene = (
            display_matches_scene
            and display["thresholdText"] is None
            and display["baselineAnnotation"] == ""
        )
    else:
        threshold = decision_contract["threshold"]
        threshold_text = display["thresholdText"]
        display_matches_scene = (
            display_matches_scene
            and isinstance(threshold_text, str)
            and threshold_text in _display_candidates(
                scene,
                threshold["value"],
                threshold["quantity"],
                scene["scale"],
            )
        )
        if isinstance(threshold_text, str) and decision is not None:
            operator = {"lt": "<", "lte": "≤", "gt": ">", "gte": "≥"}[
                decision_contract["operator"]
            ]
            threshold_label = "しきい値" if scene["locale"] == "ja" else "threshold"
            primary_output = reporting["primaryOutput"]
            expected_annotation = (
                scene["outputDefinitions"][primary_output]["label"]
                + " "
                + _scene_numeric_text(scene, primary_output)
                + "; "
                + decision["status"]
                + "; "
                + threshold_label
                + " "
                + operator
                + " "
                + threshold_text
                + "; "
                + decision["recommendation"]
            )
            display_matches_scene = (
                display_matches_scene
                and display["baselineAnnotation"] == expected_annotation
            )
    for axis in ("x", "y"):
        expected_paragraphs.append(view[axis + "Label"])
        if ticks is not None:
            expected_paragraphs.extend(ticks[axis])
    removed_marker = "除外" if scene["locale"] == "ja" else "Removed"
    emphasized_marker = "強調" if scene["locale"] == "ja" else "Emphasized"
    for point in scene["initialEvaluation"]["view"]["points"]:
        label = point["label"]
        if point["removed"]:
            label += " · " + removed_marker
        expected_paragraphs.append(
            f'{label}: {point["xText"]}, {point["yText"]}'
        )
        if point["highlight"]:
            expected_paragraphs.append(f"{emphasized_marker}: {label}")
    expected_paragraphs.extend(invariants.get("footnotes", []))
    for key in ("classification", "page_number"):
        if invariants.get(key):
            expected_paragraphs.append(invariants[key])
    if (
        not display_matches_scene
        or summary["headline"] != invariants.get("headline", "")
        or summary["source"] != invariants.get("source", "")
        or summary["paragraphs"] != expected_paragraphs
        or summary["values"] != expected_values
        or summary["decision"] != expected_decision
    ):
        _raise(
            "summary_mismatch",
            location,
            "semantic chrome, visible facts and evaluation must match the validated compiled scene",
        )


def _validate_scene_summary(
    scene: dict,
    summary: dict,
    display: dict,
    location: str,
) -> None:
    scene_type = scene.get("type")
    fallback = scene.get("fallback")
    display_contract_matches = (
        isinstance(fallback, dict)
        and summary["paragraphs"] == fallback.get("paragraphs")
        and display["baselineAnnotation"] == fallback.get("baselineAnnotation")
        and display["thresholdText"] == fallback.get("thresholdText")
        and display["axisTickLabels"] == fallback.get("axisTickLabels")
    )
    if scene_type in ("evidence_only", "drilldown", "accordion"):
        invariants = scene["invariants"]
        if (
            not display_contract_matches
            or summary["headline"] != invariants.get("headline", "")
            or summary["source"] != invariants.get("source", "")
            or summary["values"] != []
            or summary["decision"] is not None
            or display["thresholdText"] is not None
            or display["axisTickLabels"] is not None
        ):
            _raise(
                "summary_mismatch",
                location,
                "disclosure semantics must match invariant chrome and remain non-numeric",
            )
        return
    if (
        scene_type == "slider_model"
        and scene.get("model", {}).get("kind") == "linear"
        and scene.get("view", {}).get("component") == "dot_plot"
    ):
        _validate_task4_scene_summary(scene, summary, display, location)
        return
    invariants = scene["invariants"]
    expected_values: list[dict] = []
    expected_decision = None
    initial = scene["initialEvaluation"]
    if scene_type in ("slider_model", "score_model"):
        output_ids = [
            scene["reporting"]["primaryOutput"],
            *scene["reporting"]["secondaryOutputs"],
        ]
        if scene_type == "score_model":
            output_ids.append("classification")
        for output_id in output_ids:
            definition = scene["outputDefinitions"][output_id]
            typed = initial["outputs"][output_id]
            expected_values.append({
                "id": output_id,
                "label": definition["label"],
                "text": (
                    _scene_numeric_text(scene, output_id)
                    if definition["kind"] == "numeric"
                    else typed["value"]
                ),
            })
        decision = initial.get("decision")
        expected_decision = {
            "status": decision["status"],
            "recommendation": decision["recommendation"],
        }
    component = (
        initial["view"].get("component")
        if isinstance(initial.get("view"), dict)
        else None
    )
    if (
        not display_contract_matches
        or summary["headline"] != invariants.get("headline", "")
        or summary["source"] != invariants.get("source", "")
        or summary["values"] != expected_values
        or summary["decision"] != expected_decision
        or ((component == "dot_plot") != (display["axisTickLabels"] is not None))
        or ((scene_type in ("slider_model", "score_model")) != (display["thresholdText"] is not None))
    ):
        _raise(
            "summary_mismatch",
            location,
            "semantic chrome, live values and evaluation must match the compiled scene",
        )


def _closed_object(
    value: object,
    required: set[str] | frozenset[str],
    optional: set[str] | frozenset[str],
    location: str,
) -> dict:
    if not isinstance(value, dict):
        _raise("scene_shape", location, "expected object")
    allowed = set(required) | set(optional)
    if set(value) - allowed or set(required) - set(value):
        _raise("scene_shape", location, "unexpected or missing compiled scene keys")
    return value


def _array(value: object, location: str, *, maximum: int = 10_000) -> list:
    if not isinstance(value, list) or len(value) > maximum:
        _raise("scene_shape", location, f"expected array of at most {maximum} items")
    return value


def _integer(value: object, location: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _raise("scene_shape", location, f"expected integer from {minimum} through {maximum}")
    return value


def _boolean(value: object, location: str) -> bool:
    if not isinstance(value, bool):
        _raise("scene_shape", location, "expected boolean")
    return value


_CANONICAL_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")
_REGISTRY_IDS = frozenset(("score", "classification", "decisionStatus", "recommendation"))
_BASIS_ORDER = ("illustrative", "assumed", "estimated", "measured")
_NARRATION_TEMPLATES = {
    "en": {
        "baseline": "Baseline", "reset": "Reset to baseline",
        "restore": "Scenario restored: {count} inputs changed", "closed": "Evidence closed",
        "sources": "Sources open", "assumptions": "Assumptions open",
        "both": "Sources and assumptions open", "openPanel": "{label} open",
        "closePanel": "{label} closed",
        "state": "{label}: {option}; {moved} moved, {changed} changed, {removed} removed",
    },
    "ja": {
        "baseline": "初期値", "reset": "初期値に戻しました",
        "restore": "シナリオを復元：入力{count}件を変更", "closed": "根拠を閉じました",
        "sources": "出典を表示", "assumptions": "仮定を表示",
        "both": "出典と仮定を表示", "openPanel": "{label}を開きました",
        "closePanel": "{label}を閉じました",
        "state": "{label}：{option}；移動{moved}件、変更{changed}件、除外{removed}件",
    },
}


def _decimal_text(value: object, location: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 128
        or not _CANONICAL_DECIMAL.fullmatch(value)
        or value == "-0"
        or canonical_decimal(Decimal(value)) != value
    ):
        _raise("scene_shape", location, "expected canonical decimal text")
    return value


def _registry_id(value: object, location: str) -> str:
    if isinstance(value, str) and value in _REGISTRY_IDS:
        return value
    return _identifier(value, location)


def _text_array(value: object, location: str, *, maximum: int = 100) -> list[str]:
    result = _array(value, location, maximum=maximum)
    for index, item in enumerate(result):
        _text(item, f"{location}/{index}", 2_000)
    return result


def _validate_provenance(value: object, location: str) -> None:
    item = _closed_object(
        value,
        {"basis"},
        {"sourceRefs", "assumptionRefs", "normalization"},
        location,
    )
    if item["basis"] not in ("illustrative", "assumed", "estimated", "measured"):
        _raise("scene_shape", location + "/basis", "unexpected evidence basis")
    for key in ("sourceRefs", "assumptionRefs"):
        if key in item:
            _text_array(item[key], location + "/" + key, maximum=20)
    if "normalization" in item:
        note = _closed_object(
            item["normalization"],
            {"note", "fromUnit", "toUnit"},
            set(),
            location + "/normalization",
        )
        for key in note:
            _text(note[key], location + "/normalization/" + key, 500, empty=False)


def _validate_lineage(value: object, location: str) -> None:
    item = _closed_object(
        value,
        {"derived", "badge", "bases", "sourceRefs", "assumptionRefs", "normalizations", "leaves", "steps"},
        set(),
        location,
    )
    _boolean(item["derived"], location + "/derived")
    _text(item["badge"], location + "/badge", 50)
    bases = _text_array(item["bases"], location + "/bases", maximum=4)
    if any(basis not in ("illustrative", "assumed", "estimated", "measured") for basis in bases):
        _raise("scene_shape", location + "/bases", "unexpected lineage basis")
    for key, maximum in (("sourceRefs", 20), ("assumptionRefs", 20), ("leaves", 64), ("steps", 128)):
        _text_array(item[key], location + "/" + key, maximum=maximum)
    for index, note in enumerate(_array(item["normalizations"], location + "/normalizations", maximum=20)):
        record = _closed_object(
            note,
            {"note", "fromUnit", "toUnit"},
            set(),
            f"{location}/normalizations/{index}",
        )
        for key in record:
            _text(record[key], f"{location}/normalizations/{index}/{key}", 500, empty=False)


def _validate_typed_value(value: object, location: str, *, allow_reference: bool = False) -> None:
    if allow_reference and isinstance(value, dict) and set(value) == {"ref"}:
        reference = _text(value["ref"], location + "/ref", 140, empty=False)
        match = re.fullmatch(r"(control|output):([a-z][a-z0-9_-]{0,63}|decisionStatus|recommendation|classification|score)", reference)
        if not match or match.group(2) in _UNSAFE_IDS:
            _raise("scene_shape", location + "/ref", "expected compiled control or output reference")
        return
    if not isinstance(value, dict):
        _raise("scene_shape", location, "expected typed value")
    kind = value.get("kind")
    if kind == "numeric":
        item = _closed_object(value, {"kind", "value", "quantity", "lineage"}, set(), location)
        _decimal_text(item["value"], location + "/value")
        _identifier(item["quantity"], location + "/quantity")
    elif kind == "text":
        item = _closed_object(value, {"kind", "value", "lineage"}, set(), location)
        _text(item["value"], location + "/value", 2_000, empty=False)
    else:
        _raise("scene_shape", location + "/kind", "expected numeric or text typed value")
    _validate_lineage(item["lineage"], location + "/lineage")


def _validate_dot_view(value: object, location: str, *, resolved: bool) -> tuple[str, ...]:
    item = _closed_object(
        value,
        {"component", "xDomain", "xLabel", "xQuantity", "yDomain", "yLabel", "yQuantity", "points"},
        {"domainReason"},
        location,
    )
    if item["component"] != "dot_plot":
        _raise("scene_shape", location + "/component", "Task 4 requires dot_plot")
    for axis in ("x", "y"):
        domain = _array(item[axis + "Domain"], location + "/" + axis + "Domain", maximum=2)
        if len(domain) != 2:
            _raise("scene_shape", location + "/" + axis + "Domain", "expected two domain endpoints")
        for index, endpoint in enumerate(domain):
            _decimal_text(endpoint, f"{location}/{axis}Domain/{index}")
        _text(item[axis + "Label"], location + "/" + axis + "Label", 500, empty=False)
        _identifier(item[axis + "Quantity"], location + "/" + axis + "Quantity")
    if "domainReason" in item:
        _text(item["domainReason"], location + "/domainReason", 500, empty=False)
    points = _array(item["points"], location + "/points", maximum=12)
    point_ids: list[str] = []
    for index, point in enumerate(points):
        here = f"{location}/points/{index}"
        required = {"id", "label", "x", "y", "highlight", "removed"}
        optional = {"xText", "yText"} if resolved else set()
        record = _closed_object(point, required | optional if resolved else required, set(), here)
        point_id = _identifier(record["id"], here + "/id")
        if point_id in point_ids:
            _raise("duplicate_id", here + "/id", "duplicate dot-plot point ID")
        point_ids.append(point_id)
        _text(record["label"], here + "/label", 500, empty=False)
        _boolean(record["highlight"], here + "/highlight")
        _boolean(record["removed"], here + "/removed")
        for axis in ("x", "y"):
            _validate_typed_value(record[axis], here + "/" + axis, allow_reference=not resolved)
            if resolved:
                _text(record[axis + "Text"], here + "/" + axis + "Text", 500)
    return tuple(point_ids)


def _validate_quantities(value: object, location: str) -> None:
    if not isinstance(value, dict):
        _raise("scene_shape", location, "expected quantity registry")
    for quantity_id, quantity in value.items():
        _identifier(quantity_id, location + "/" + str(quantity_id))
        here = location + "/" + quantity_id
        item = _closed_object(
            quantity,
            {"dimension", "unit", "exponents", "unitFactors", "display"},
            {"currency"},
            here,
        )
        for key in ("dimension", "unit", "display"):
            _text(item[key], here + "/" + key, 64 if key != "display" else 12, empty=False)
        if (
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", item["unit"])
            or item["unit"] in _UNSAFE_IDS
        ):
            _raise("identifier", here + "/unit", "invalid storage unit ID")
        exponents = _closed_object(
            item["exponents"], {"currency", "time", "count"}, set(), here + "/exponents"
        )
        for key, exponent in exponents.items():
            _integer(exponent, here + "/exponents/" + key, -2, 2)
        if not isinstance(item["unitFactors"], dict):
            _raise("scene_shape", here + "/unitFactors", "expected unit-factor registry")
        for unit, exponent in item["unitFactors"].items():
            if not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", unit) or unit in _UNSAFE_IDS:
                _raise("identifier", here + "/unitFactors", "invalid storage unit ID")
            _integer(exponent, here + "/unitFactors/" + unit, -2, 2)
        if "currency" in item:
            _text(item["currency"], here + "/currency", 3, empty=False)


def _validate_output_definitions(value: object, location: str) -> None:
    if not isinstance(value, dict):
        _raise("scene_shape", location, "expected output registry")
    for output_id, definition in value.items():
        _registry_id(output_id, location + "/" + str(output_id))
        here = location + "/" + output_id
        if not isinstance(definition, dict):
            _raise("scene_shape", here, "expected output definition")
        if definition.get("kind") == "numeric":
            item = _closed_object(
                definition,
                {"kind", "label", "quantity", "format", "round"},
                set(),
                here,
            )
            _identifier(item["quantity"], here + "/quantity")
            if item["format"] not in ("number", "percent", "currency", "duration", "score"):
                _raise("scene_shape", here + "/format", "unexpected numeric display format")
            _integer(item["round"], here + "/round", 0, 6)
        elif definition.get("kind") == "text":
            item = _closed_object(definition, {"kind", "label"}, set(), here)
        else:
            _raise("scene_shape", here + "/kind", "expected numeric or text output")
        _text(
            item["label"], here + "/label",
            40 if definition.get("kind") == "numeric" else 500,
            empty=False,
        )


def _validate_evidence(value: object, location: str) -> None:
    item = _closed_object(
        value,
        {"sources", "assumptions", "leaves", "badge", "formulas", "triggerLabel"},
        set(),
        location,
    )
    source_ids: set[str] = set()
    for index, source in enumerate(_array(item["sources"], location + "/sources", maximum=20)):
        here = f"{location}/sources/{index}"
        record = _closed_object(source, {"id", "label", "detail", "linked"}, {"url"}, here)
        source_id = _identifier(record["id"], here + "/id")
        if source_id in source_ids:
            _raise("duplicate_id", here + "/id", "duplicate evidence source ID")
        source_ids.add(source_id)
        _text(record["label"], here + "/label", 500, empty=False)
        _text(record["detail"], here + "/detail", 2_000, empty=False)
        linked = _boolean(record["linked"], here + "/linked")
        if "url" in record:
            _text(record["url"], here + "/url", 2_048, empty=False)
        if linked and ("url" not in record or not safe_source_url(record["url"])):
            _raise("scene_shape", here + "/url", "linked source requires one safe exact URL")
    assumption_ids: set[str] = set()
    for index, assumption in enumerate(_array(item["assumptions"], location + "/assumptions", maximum=20)):
        here = f"{location}/assumptions/{index}"
        record = _closed_object(assumption, {"id", "label", "value"}, {"unit"}, here)
        assumption_id = _identifier(record["id"], here + "/id")
        if assumption_id in assumption_ids:
            _raise("duplicate_id", here + "/id", "duplicate evidence assumption ID")
        assumption_ids.add(assumption_id)
        for key in ("label", "value", "unit"):
            if key in record:
                _text(record[key], here + "/" + key, 500, empty=False)
    leaf_ids: set[str] = set()
    for index, leaf in enumerate(_array(item["leaves"], location + "/leaves", maximum=64)):
        here = f"{location}/leaves/{index}"
        record = _closed_object(
            leaf,
            {"id", "label", "quantity", "basis", "sourceRefs", "assumptionRefs"},
            set(),
            here,
        )
        leaf_id = _identifier(record["id"], here + "/id")
        if leaf_id in leaf_ids:
            _raise("duplicate_id", here + "/id", "duplicate evidence leaf ID")
        leaf_ids.add(leaf_id)
        _identifier(record["quantity"], here + "/quantity")
        _text(record["label"], here + "/label", 500, empty=False)
        if record["basis"] not in ("illustrative", "assumed", "estimated", "measured"):
            _raise("scene_shape", here + "/basis", "unexpected evidence basis")
        _text_array(record["sourceRefs"], here + "/sourceRefs", maximum=20)
        _text_array(record["assumptionRefs"], here + "/assumptionRefs", maximum=20)
    _text(item["badge"], location + "/badge", 50)
    _text_array(item["formulas"], location + "/formulas", maximum=64)
    _text(item["triggerLabel"], location + "/triggerLabel", 500, empty=False)


def _validate_narration(value: object, location: str, lang: str) -> None:
    item = _closed_object(
        value,
        {"locale", "templates", "templatesByLocale", "messages", "messagesByLocale", "program", "validatedVariants", "comparison", "maxScalars"},
        set(),
        location,
    )
    if item["locale"] != lang or item["comparison"] != "initialState":
        _raise("scene_shape", location, "narration identity mismatch")
    _integer(item["validatedVariants"], location + "/validatedVariants", 0, MAX_JSON_NODES)
    max_scalars = _integer(item["maxScalars"], location + "/maxScalars", 1, 2_000)
    if max_scalars != 160:
        _raise("scene_shape", location + "/maxScalars", "unexpected narration scalar cap")
    template_keys = {
        "baseline", "reset", "restore", "state", "sources", "assumptions",
        "both", "closed", "openPanel", "closePanel",
    }
    message_keys = {
        "evidence:closed", "evidence:sources", "evidence:assumptions",
        "evidence:both", "panels:closed", "initial", "reset",
    }

    def text_registry(registry: object, here: str, *, exact_keys: set[str] | None = None) -> None:
        if not isinstance(registry, dict) or (exact_keys is not None and set(registry) != exact_keys):
            _raise("scene_shape", here, "unexpected narration text registry")
        for key, text_value in registry.items():
            if not isinstance(key, str) or key in _UNSAFE_IDS or len(key) > 140:
                _raise("identifier", here, "unsafe narration registry key")
            _text(text_value, here + "/" + key, 500)
            if len(text_value) > max_scalars:
                _raise("scene_shape", here + "/" + key, "narration exceeds scalar cap")

    text_registry(item["templates"], location + "/templates", exact_keys=template_keys)
    text_registry(item["messages"], location + "/messages", exact_keys=message_keys)
    localized_templates = _closed_object(
        item["templatesByLocale"], {"en", "ja"}, set(), location + "/templatesByLocale"
    )
    localized_messages = _closed_object(
        item["messagesByLocale"], {"en", "ja"}, set(), location + "/messagesByLocale"
    )
    for locale in ("en", "ja"):
        text_registry(localized_templates[locale], location + "/templatesByLocale/" + locale, exact_keys=template_keys)
        text_registry(localized_messages[locale], location + "/messagesByLocale/" + locale, exact_keys=message_keys)
    program = _closed_object(
        item["program"], {"kind", "controls", "outputs", "transitions"}, set(), location + "/program"
    )
    if program["kind"] != "numeric_delta_v1":
        _raise("scene_shape", location + "/program/kind", "Task 4 requires numeric narration")
    narration_control_ids: set[str] = set()
    for index, atom in enumerate(_array(program["controls"], location + "/program/controls", maximum=8)):
        here = f"{location}/program/controls/{index}"
        record = _closed_object(
            atom,
            {"baseline", "display", "id", "kind", "label", "precision", "unit"},
            set(),
            here,
        )
        if record["kind"] != "range":
            _raise("scene_shape", here + "/kind", "Task 4 requires range narration control")
        _decimal_text(record["baseline"], here + "/baseline")
        narration_control_id = _identifier(record["id"], here + "/id")
        if narration_control_id in narration_control_ids:
            _raise("duplicate_id", here + "/id", "duplicate narration control ID")
        narration_control_ids.add(narration_control_id)
        for key in ("display", "label", "unit"):
            _text(record[key], here + "/" + key, 500)
        _integer(record["precision"], here + "/precision", 0, 6)
    narration_output_ids: set[str] = set()
    for index, atom in enumerate(_array(program["outputs"], location + "/program/outputs", maximum=3)):
        here = f"{location}/program/outputs/{index}"
        record = _closed_object(
            atom,
            {"baseline", "display", "id", "label", "precision", "unit"},
            set(),
            here,
        )
        _decimal_text(record["baseline"], here + "/baseline")
        narration_output_id = _registry_id(record["id"], here + "/id")
        if narration_output_id in narration_output_ids:
            _raise("duplicate_id", here + "/id", "duplicate narration output ID")
        narration_output_ids.add(narration_output_id)
        for key in ("display", "label", "unit"):
            _text(record[key], here + "/" + key, 500)
        _integer(record["precision"], here + "/precision", 0, 6)
    narration_transition_ids: set[str] = set()
    for index, atom in enumerate(_array(program["transitions"], location + "/program/transitions", maximum=2)):
        here = f"{location}/program/transitions/{index}"
        record = _closed_object(atom, {"baseline", "id"}, set(), here)
        _text(record["baseline"], here + "/baseline", 500)
        narration_transition_id = _registry_id(record["id"], here + "/id")
        if narration_transition_id in narration_transition_ids:
            _raise("duplicate_id", here + "/id", "duplicate narration transition ID")
        narration_transition_ids.add(narration_transition_id)


def _scene_reference(condition: bool, location: str) -> None:
    if not condition:
        _raise("scene_reference", location, "compiled scene reference is not registered")


def _scene_relation(condition: bool, location: str) -> None:
    if not condition:
        _raise("scene_relation", location, "compiled scene registries do not agree")


def _validate_scene_relations(scene: dict, location: str) -> None:
    """Rebind the exact Task 4 slider graph before browser-facing trust."""
    controls = scene["controls"]
    _scene_relation(len(controls) == 1, location + "/controls")
    control = controls[0]
    control_id = control["id"]
    control_by_id = {control_id: control}
    quantities = scene["quantities"]
    quantity_ids = set(quantities)
    _scene_reference(control["quantity"] in quantity_ids, location + "/controls/0/quantity")

    units: dict[str, tuple[tuple, dict]] = {}
    for quantity_id, quantity in quantities.items():
        here = location + "/quantities/" + quantity_id
        dimension = quantity["dimension"]
        _scene_relation(
            dimension in BASE_EXPONENTS or dimension == "derived",
            here + "/dimension",
        )
        exponent_tuple = tuple(
            quantity["exponents"][key] for key in ("currency", "time", "count")
        )
        factor_tuple = tuple(sorted(quantity["unitFactors"].items()))
        currency = quantity.get("currency")
        if dimension == "derived":
            _scene_relation(
                all(exponent != 0 for _, exponent in factor_tuple),
                here + "/unitFactors",
            )
        else:
            expected_factors = (
                ()
                if (dimension, quantity["unit"]) in (("scalar", "one"), ("ratio", "fraction"))
                else ((quantity["unit"], 1),)
            )
            _scene_relation(
                exponent_tuple == tuple(BASE_EXPONENTS[dimension])
                and factor_tuple == expected_factors,
                here,
            )
        _scene_relation(
            (
                isinstance(currency, str)
                and currency in ISO_CURRENCIES
                if exponent_tuple[0]
                else currency is None
            ),
            here + "/currency",
        )
        signature = (dimension, exponent_tuple, factor_tuple, currency)
        prior = units.get(quantity["unit"])
        _scene_relation(prior is None or prior[0] == signature, here + "/unit")
        units[quantity["unit"]] = (signature, quantity)
    for quantity_id, quantity in quantities.items():
        if quantity["dimension"] != "derived":
            continue
        here = location + "/quantities/" + quantity_id
        reproduced = [0, 0, 0]
        currencies: set[str] = set()
        for unit, factor_exponent in quantity["unitFactors"].items():
            base = units.get(unit, (None, None))[1]
            _scene_relation(
                base is not None
                and base["dimension"] not in ("derived", "score")
                and bool(base["unitFactors"]),
                here + "/unitFactors/" + unit,
            )
            for index, key in enumerate(("currency", "time", "count")):
                reproduced[index] += base["exponents"][key] * factor_exponent
            if base.get("currency"):
                currencies.add(base["currency"])
        declared = tuple(quantity["exponents"][key] for key in ("currency", "time", "count"))
        _scene_relation(
            tuple(reproduced) == declared
            and len(currencies) <= 1
            and (not quantity.get("currency") or currencies == {quantity["currency"]}),
            here,
        )

    scale = scene["scale"]

    def bounded_decimal(text: str, here: str) -> Decimal:
        value = Decimal(text)
        fractional = max(0, -value.as_tuple().exponent)
        _scene_relation(
            abs(value) <= Decimal("1000000000000") and fractional <= 6,
            here,
        )
        return value

    def decimal(text: str, here: str) -> Decimal:
        value = bounded_decimal(text, here)
        fractional = max(0, -value.as_tuple().exponent)
        _scene_relation(fractional <= scale, here)
        return value

    minimum = decimal(control["min"], location + "/controls/0/min")
    maximum = decimal(control["max"], location + "/controls/0/max")
    step = decimal(control["step"], location + "/controls/0/step")
    _scene_relation(minimum < maximum and step > 0, location + "/controls/0")
    positions = (maximum - minimum) / step
    _scene_relation(
        positions == positions.to_integral_value() and positions <= 10_000,
        location + "/controls/0/step",
    )

    def on_grid(text: str, here: str) -> Decimal:
        value = decimal(text, here)
        _scene_relation(minimum <= value <= maximum, here)
        offset = (value - minimum) / step
        _scene_relation(offset == offset.to_integral_value(), here)
        return value

    _scene_relation(scene["initialState"] == scene["printState"], location + "/printState")
    initial_control = on_grid(
        scene["initialState"][control_id], location + "/initialState/" + control_id
    )

    definitions = scene["outputDefinitions"]
    numeric_definitions = {
        output_id: definition
        for output_id, definition in definitions.items()
        if definition["kind"] == "numeric"
    }
    for output_id, definition in numeric_definitions.items():
        _scene_reference(
            definition["quantity"] in quantity_ids,
            location + "/outputDefinitions/" + output_id + "/quantity",
        )
        expected_dimension = {
            "percent": "ratio",
            "currency": "currency",
            "duration": "time",
            "score": "score",
        }.get(definition["format"])
        _scene_relation(
            expected_dimension is None
            or quantities[definition["quantity"]]["dimension"] == expected_dimension,
            location + "/outputDefinitions/" + output_id + "/format",
        )

    model = scene["model"]
    model_output = model["output"]
    _scene_reference(model_output in definitions, location + "/model/output")
    _scene_relation(
        model_output in numeric_definitions and model_output not in _REGISTRY_IDS,
        location + "/model/output",
    )
    output_quantity = numeric_definitions[model_output]["quantity"]
    intercept = model["intercept"]
    _scene_reference(intercept["quantity"] in quantity_ids, location + "/model/intercept/quantity")
    _scene_relation(
        intercept["kind"] == "numeric" and intercept["quantity"] == output_quantity,
        location + "/model/intercept",
    )
    model_value = decimal(intercept["value"], location + "/model/intercept/value")
    term_ids = [term[0] for term in model["terms"]]
    for index, term_id in enumerate(term_ids):
        _scene_reference(term_id in control_by_id, f"{location}/model/terms/{index}/0")
    _scene_relation(term_ids == [control_id], location + "/model/terms")
    term = model["terms"][0][1]
    _scene_reference(term["inputQuantity"] in quantity_ids, location + "/model/terms/0/1/inputQuantity")
    _scene_reference(term["outputQuantity"] in quantity_ids, location + "/model/terms/0/1/outputQuantity")
    _scene_reference(term["value"]["quantity"] in quantity_ids, location + "/model/terms/0/1/value/quantity")
    _scene_relation(
        term["inputQuantity"] == control["quantity"]
        and term["outputQuantity"] == output_quantity
        and term["value"]["kind"] == "numeric"
        and term["value"]["quantity"] == output_quantity,
        location + "/model/terms/0/1",
    )
    coefficient = decimal(term["value"]["value"], location + "/model/terms/0/1/value/value")

    def rounded_model(control_value: Decimal) -> Decimal:
        precision = scale
        with localcontext() as context:
            context.prec = 40
            return (model_value + coefficient * control_value).quantize(
                Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP
            )

    expected_model_value = rounded_model(initial_control)
    _scene_relation(set(numeric_definitions) == {model_output}, location + "/outputDefinitions")

    reporting = scene["reporting"]
    reporting_ids = [reporting["primaryOutput"], *reporting["secondaryOutputs"]]
    _scene_relation(len(reporting_ids) == len(set(reporting_ids)), location + "/reporting")
    for index, output_id in enumerate(reporting_ids):
        _scene_reference(output_id in definitions, f"{location}/reporting/{index}")
        _scene_relation(output_id in numeric_definitions, f"{location}/reporting/{index}")
    _scene_relation(
        reporting["primaryOutput"] == model_output
        and reporting["secondaryOutputs"] == []
        and reporting_ids == [model_output],
        location + "/reporting",
    )

    evidence = scene["evidence"]
    source_order = [source["id"] for source in evidence["sources"]]
    assumption_order = [assumption["id"] for assumption in evidence["assumptions"]]
    source_ids = set(source_order)
    assumption_ids = set(assumption_order)
    for index, source in enumerate(evidence["sources"]):
        _scene_relation(
            source["linked"] is bool(safe_source_url(source.get("url"))),
            f"{location}/evidence/sources/{index}/linked",
        )
    _scene_relation(
        evidence["triggerLabel"]
        == ("根拠を表示" if scene["locale"] == "ja" else "Open evidence"),
        location + "/evidence/triggerLabel",
    )
    _scene_relation(
        [leaf["id"] for leaf in evidence["leaves"]]
        == [f"leaf-{index:03d}" for index in range(1, len(evidence["leaves"]) + 1)],
        location + "/evidence/leaves",
    )
    leaf_by_id = {leaf["id"]: leaf for leaf in evidence["leaves"]}
    leaf_ids = set(leaf_by_id)
    owned_leaf_ids: set[str] = set()
    next_leaf_index = 1
    for index, leaf in enumerate(evidence["leaves"]):
        here = f"{location}/evidence/leaves/{index}"
        _scene_reference(leaf["quantity"] in quantity_ids, here + "/quantity")
        _scene_reference(set(leaf["sourceRefs"]) <= source_ids, here + "/sourceRefs")
        _scene_reference(set(leaf["assumptionRefs"]) <= assumption_ids, here + "/assumptionRefs")
    expected_evidence_badge = next(
        (basis for basis in _BASIS_ORDER if any(leaf["basis"] == basis for leaf in evidence["leaves"])),
        "",
    )
    _scene_relation(evidence["badge"] == expected_evidence_badge, location + "/evidence/badge")

    def unique(values: list) -> list:
        result: list = []
        for value in values:
            if value not in result:
                result.append(value)
        return result

    def lineage(value: dict, here: str) -> None:
        _scene_reference(set(value["sourceRefs"]) <= source_ids, here + "/sourceRefs")
        _scene_reference(set(value["assumptionRefs"]) <= assumption_ids, here + "/assumptionRefs")
        _scene_reference(set(value["leaves"]) <= leaf_ids, here + "/leaves")
        expected_bases = [basis for basis in _BASIS_ORDER if basis in set(value["bases"])]
        expected_badge = expected_bases[0] if expected_bases else ""
        _scene_relation(value["bases"] == expected_bases, here + "/bases")
        _scene_relation(value["badge"] == expected_badge, here + "/badge")
        _scene_relation(
            value["sourceRefs"] == [identifier for identifier in source_order if identifier in set(value["sourceRefs"])],
            here + "/sourceRefs",
        )
        _scene_relation(
            value["assumptionRefs"] == [identifier for identifier in assumption_order if identifier in set(value["assumptionRefs"])],
            here + "/assumptionRefs",
        )
        expected_leaves = unique(value["leaves"])
        if expected_leaves and all(re.fullmatch(r"leaf-[0-9]+", leaf) for leaf in expected_leaves):
            expected_leaves.sort(key=lambda leaf: int(leaf.split("-")[1]))
        _scene_relation(value["leaves"] == expected_leaves, here + "/leaves")
        _scene_relation(value["steps"] == unique(value["steps"]), here + "/steps")
        _scene_relation(
            value["normalizations"] == unique(value["normalizations"]),
            here + "/normalizations",
        )

    def bases_have_required_support(
        bases: list[str], source_refs: list[str], assumption_refs: list[str]
    ) -> bool:
        return all(
            (basis != "measured" or bool(source_refs))
            and (basis != "estimated" or bool(source_refs or assumption_refs))
            and (basis not in ("assumed", "illustrative") or bool(assumption_refs))
            for basis in bases
        )

    def leaf_lineage(
        value: dict,
        quantity: str,
        label: str,
        here: str,
        *,
        max_bases: int,
        max_normalizations: int,
    ) -> dict:
        nonlocal next_leaf_index
        lineage(value, here)
        _scene_relation(len(value["leaves"]) == 1, here + "/leaves")
        leaf_id = value["leaves"][0]
        _scene_relation(
            leaf_id == f"leaf-{next_leaf_index:03d}"
            and leaf_id not in owned_leaf_ids,
            here + "/leaves",
        )
        owned_leaf_ids.add(leaf_id)
        next_leaf_index += 1
        leaf = leaf_by_id[leaf_id]
        _scene_relation(
            leaf["label"] == label
            and leaf["quantity"] == quantity
            and leaf["basis"] == value["badge"]
            and leaf["sourceRefs"] == value["sourceRefs"]
            and leaf["assumptionRefs"] == value["assumptionRefs"]
            and 1 <= len(value["bases"]) <= max_bases
            and len(value["normalizations"]) <= max_normalizations
            and bases_have_required_support(
                value["bases"], value["sourceRefs"], value["assumptionRefs"]
            )
            and all(
                note["toUnit"] == quantities[quantity]["unit"]
                for note in value["normalizations"]
            )
            and value["steps"] == []
            and value["derived"] is bool(value["normalizations"]),
            here,
        )
        return value

    def combine_lineages(*values: dict, step_name: str) -> dict:
        bases = [basis for basis in _BASIS_ORDER if any(basis in value["bases"] for value in values)]
        source_refs = [
            identifier for identifier in source_order
            if any(identifier in value["sourceRefs"] for value in values)
        ]
        assumption_refs = [
            identifier for identifier in assumption_order
            if any(identifier in value["assumptionRefs"] for value in values)
        ]
        normalizations = unique([
            note for value in values for note in value["normalizations"]
        ])
        leaves = unique([leaf for value in values for leaf in value["leaves"]])
        if leaves and all(re.fullmatch(r"leaf-[0-9]+", leaf) for leaf in leaves):
            leaves.sort(key=lambda leaf: int(leaf.split("-")[1]))
        steps = unique([step for value in values for step in value["steps"]] + [step_name])
        return {
            "derived": True,
            "badge": bases[0] if bases else "",
            "bases": bases,
            "sourceRefs": source_refs,
            "assumptionRefs": assumption_refs,
            "normalizations": normalizations,
            "leaves": leaves,
            "steps": steps,
        }

    control_lineage = leaf_lineage(
        control["lineage"], control["quantity"], control["label"],
        location + "/controls/0/lineage",
        max_bases=1,
        max_normalizations=1,
    )
    intercept_lineage = leaf_lineage(
        intercept["lineage"], intercept["quantity"], "Intercept",
        location + "/model/intercept/lineage",
        max_bases=2,
        max_normalizations=2,
    )
    coefficient_lineage = leaf_lineage(
        term["value"]["lineage"], term["value"]["quantity"], "Coefficient",
        location + "/model/terms/0/1/value/lineage",
        max_bases=2,
        max_normalizations=2,
    )
    inherited_model_provenance = any(
        len(lineage_value[field]) > 1
        for lineage_value in (intercept_lineage, coefficient_lineage)
        for field in ("bases", "normalizations")
    )
    if inherited_model_provenance:
        inherited_basis = next(
            basis for basis in reversed(_BASIS_ORDER)
            if basis in set(intercept_lineage["bases"]) | set(coefficient_lineage["bases"])
        )
        shared_sources = list(
            set(intercept_lineage["sourceRefs"]) & set(coefficient_lineage["sourceRefs"])
        )
        shared_assumptions = list(
            set(intercept_lineage["assumptionRefs"])
            & set(coefficient_lineage["assumptionRefs"])
        )
        _scene_relation(
            inherited_basis in intercept_lineage["bases"]
            and inherited_basis in coefficient_lineage["bases"]
            and bases_have_required_support(
                [inherited_basis],
                shared_sources,
                shared_assumptions,
            ),
            location + "/model/modelProvenance",
        )
        if (
            len(intercept_lineage["normalizations"]) > 1
            or len(coefficient_lineage["normalizations"]) > 1
        ):
            _scene_relation(
                bool(intercept_lineage["normalizations"])
                and bool(coefficient_lineage["normalizations"])
                and intercept_lineage["normalizations"][0]
                == coefficient_lineage["normalizations"][0],
                location + "/model/modelProvenance/normalization",
            )
    expected_model_lineage = combine_lineages(
        intercept_lineage, control_lineage, coefficient_lineage, step_name="model:linear"
    )
    expected_formula = (
        numeric_definitions[model_output]["label"]
        + " = "
        + intercept["value"]
        + " + "
        + term["value"]["value"]
        + " × "
        + control["label"]
    )
    _scene_relation(
        evidence["formulas"] == [expected_formula],
        location + "/evidence/formulas",
    )

    initial = scene["initialEvaluation"]
    initial_outputs = initial["outputs"]
    for output_id, definition in definitions.items():
        output = initial_outputs[output_id]
        _scene_relation(output["kind"] == definition["kind"], location + "/initialEvaluation/outputs/" + output_id)
        if definition["kind"] == "numeric":
            _scene_reference(
                output["quantity"] in quantity_ids,
                location + "/initialEvaluation/outputs/" + output_id + "/quantity",
            )
            _scene_relation(
                output["quantity"] == definition["quantity"],
                location + "/initialEvaluation/outputs/" + output_id + "/quantity",
            )
            decimal(output["value"], location + "/initialEvaluation/outputs/" + output_id + "/value")
        lineage(output["lineage"], location + "/initialEvaluation/outputs/" + output_id + "/lineage")
    evaluated_model = initial_outputs[model_output]
    _scene_relation(
        Decimal(evaluated_model["value"]) == expected_model_value
        and evaluated_model["lineage"] == expected_model_lineage,
        location + "/initialEvaluation/outputs/" + model_output + "/value",
    )

    decision = scene.get("decisionContract")
    decision_result = initial.get("decision")
    _scene_relation(
        decision is not None and decision_result is not None,
        location + "/initialEvaluation/decision",
    )
    expected_output_ids = {model_output}
    if decision is not None:
        expected_output_ids.update(("decisionStatus", "recommendation"))
    _scene_relation(set(definitions) == expected_output_ids, location + "/outputDefinitions")
    if decision is not None:
        metric_ref = decision["metric"]["ref"]
        metric_kind, metric_id = metric_ref.split(":", 1)
        _scene_reference(metric_kind == "output" and metric_id in definitions, location + "/decisionContract/metric/ref")
        _scene_relation(metric_id == model_output and metric_id in numeric_definitions, location + "/decisionContract/metric/ref")
        threshold = decision["threshold"]
        _scene_reference(threshold["quantity"] in quantity_ids, location + "/decisionContract/threshold/quantity")
        _scene_relation(threshold["quantity"] == output_quantity, location + "/decisionContract/threshold/quantity")
        provenance = threshold["provenance"]
        _scene_reference(set(provenance.get("sourceRefs", [])) <= source_ids, location + "/decisionContract/threshold/provenance/sourceRefs")
        _scene_reference(set(provenance.get("assumptionRefs", [])) <= assumption_ids, location + "/decisionContract/threshold/provenance/assumptionRefs")
        provenance_source_refs = list(provenance.get("sourceRefs", []))
        provenance_assumption_refs = list(provenance.get("assumptionRefs", []))
        _scene_relation(
            ("sourceRefs" not in provenance or bool(provenance_source_refs))
            and ("assumptionRefs" not in provenance or bool(provenance_assumption_refs))
            and provenance_source_refs
            == [identifier for identifier in source_order if identifier in set(provenance_source_refs)]
            and provenance_assumption_refs
            == [identifier for identifier in assumption_order if identifier in set(provenance_assumption_refs)]
            and bases_have_required_support(
                [provenance["basis"]],
                provenance_source_refs,
                provenance_assumption_refs,
            )
            and (
                "normalization" not in provenance
                or provenance["normalization"]["toUnit"]
                == quantities[threshold["quantity"]]["unit"]
            ),
            location + "/decisionContract/threshold/provenance",
        )
        threshold_value = decimal(threshold["value"], location + "/decisionContract/threshold/value")
        threshold_matches = [
            leaf for leaf in evidence["leaves"]
            if leaf["id"] == f"leaf-{next_leaf_index:03d}"
            and leaf["id"] not in owned_leaf_ids
            and leaf["label"] == "Decision threshold"
            and leaf["quantity"] == threshold["quantity"]
            and leaf["basis"] == provenance["basis"]
            and leaf["sourceRefs"] == provenance.get("sourceRefs", [])
            and leaf["assumptionRefs"] == provenance.get("assumptionRefs", [])
        ]
        _scene_relation(len(threshold_matches) == 1, location + "/decisionContract/threshold/provenance")
        threshold_leaf_id = threshold_matches[0]["id"]
        _scene_relation(
            threshold_leaf_id not in owned_leaf_ids,
            location + "/decisionContract/threshold/provenance",
        )
        owned_leaf_ids.add(threshold_leaf_id)
        next_leaf_index += 1
        normalizations = [provenance["normalization"]] if "normalization" in provenance else []
        threshold_lineage = {
            "derived": bool(normalizations),
            "badge": provenance["basis"],
            "bases": [provenance["basis"]],
            "sourceRefs": list(provenance.get("sourceRefs", [])),
            "assumptionRefs": list(provenance.get("assumptionRefs", [])),
            "normalizations": normalizations,
            "leaves": [threshold_matches[0]["id"]],
            "steps": [],
        }
        expected_decision_lineage = combine_lineages(
            expected_model_lineage,
            threshold_lineage,
            step_name="decision:" + decision["id"],
        )
        operator = decision["operator"]
        comparisons = {
            "gte": expected_model_value >= threshold_value,
            "gt": expected_model_value > threshold_value,
            "lte": expected_model_value <= threshold_value,
            "lt": expected_model_value < threshold_value,
        }
        met = comparisons[operator]
        selected = decision["whenMet"] if met else decision["whenNotMet"]
        assert decision_result is not None
        _scene_reference(decision_result["quantity"] in quantity_ids, location + "/initialEvaluation/decision/quantity")
        _scene_relation(
            decision_result["quantity"] == output_quantity
            and Decimal(decision_result["distance"]) == expected_model_value - threshold_value
            and decision_result["outcome"] == ("met" if met else "notMet")
            and decision_result["status"] == selected["status"]
            and decision_result["recommendation"] == selected["recommendation"]
            and decision_result["lineage"] == expected_decision_lineage,
            location + "/initialEvaluation/decision",
        )
        lineage(decision_result["lineage"], location + "/initialEvaluation/decision/lineage")
        _scene_relation(
            definitions.get("decisionStatus", {}).get("kind") == "text"
            and definitions["decisionStatus"].get("label") == "Decision status"
            and definitions.get("recommendation", {}).get("kind") == "text"
            and definitions["recommendation"].get("label") == "Recommendation"
            and initial_outputs["decisionStatus"]["value"] == selected["status"]
            and initial_outputs["recommendation"]["value"] == selected["recommendation"]
            and initial_outputs["decisionStatus"]["lineage"] == expected_decision_lineage
            and initial_outputs["recommendation"]["lineage"] == expected_decision_lineage,
            location + "/initialEvaluation/outputs",
        )

    def format_numeric(value_text: str, quantity_id: str, precision: int) -> str:
        value = Decimal(value_text)
        with localcontext() as context:
            context.prec = 40
            rounded = value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
        number = format(abs(rounded), f",.{precision}f")
        sign = "−" if rounded < 0 else ""
        display = scene["quantities"][quantity_id]["display"]
        if display.startswith(("$", "€", "£", "¥", "￥")):
            number = display[0] + number + display[1:]
        else:
            number += ("" if display == "%" else " ") + display
        return sign + number

    view = scene["view"]
    evaluated_view = initial["view"]
    view_domains: dict[str, tuple[Decimal, Decimal]] = {}
    for axis in ("x", "y"):
        quantity = view[axis + "Quantity"]
        _scene_reference(quantity in quantity_ids, location + "/view/" + axis + "Quantity")
        domain = tuple(
            bounded_decimal(value, f"{location}/view/{axis}Domain/{index}")
            for index, value in enumerate(view[axis + "Domain"])
        )
        fallback_domain = tuple(float(value) for value in domain)
        _scene_relation(
            domain[0] < domain[1]
            and all(math.isfinite(value) for value in fallback_domain)
            and fallback_domain[0] < fallback_domain[1],
            location + "/view/" + axis + "Domain",
        )
        view_domains[axis] = domain
        for key in ("Domain", "Label", "Quantity"):
            _scene_relation(
                evaluated_view[axis + key] == view[axis + key],
                location + "/initialEvaluation/view/" + axis + key,
            )
    _scene_relation(
        evaluated_view.get("domainReason") == view.get("domainReason")
        and (
            all(view_domains[axis][0] == 0 for axis in ("x", "y"))
            or bool(view.get("domainReason"))
        ),
        location + "/initialEvaluation/view/domainReason",
    )
    _scene_relation(evaluated_view["component"] == view["component"], location + "/initialEvaluation/view/component")
    _scene_relation(bool(view["points"]), location + "/view/points")
    _scene_relation(
        sum(1 for point in view["points"] if point["highlight"]) <= 1,
        location + "/view/points",
    )
    view_output_refs: set[str] = set()
    for index, (point, evaluated_point) in enumerate(zip(view["points"], evaluated_view["points"])):
        here = f"{location}/view/points/{index}"
        _scene_relation(
            all(point[key] == evaluated_point[key] for key in ("id", "label", "highlight", "removed")),
            here,
        )
        for axis in ("x", "y"):
            unresolved = point[axis]
            resolved = evaluated_point[axis]
            axis_quantity = view[axis + "Quantity"]
            if set(unresolved) == {"ref"}:
                ref_kind, ref_id = unresolved["ref"].split(":", 1)
                if ref_kind == "control":
                    _scene_reference(ref_id in control_by_id, here + "/" + axis + "/ref")
                    expected = {
                        "kind": "numeric",
                        "value": scene["initialState"][ref_id],
                        "quantity": control_by_id[ref_id]["quantity"],
                    }
                    expected_lineage = control_by_id[ref_id]["lineage"]
                    minimum_precision = max(0, -Decimal(expected["value"]).as_tuple().exponent)
                    display_precisions = range(minimum_precision, scale + 1)
                    _scene_relation(
                        view_domains[axis][0] <= minimum <= maximum <= view_domains[axis][1],
                        here + "/" + axis,
                    )
                else:
                    _scene_reference(ref_id in definitions, here + "/" + axis + "/ref")
                    _scene_relation(ref_id in numeric_definitions, here + "/" + axis + "/ref")
                    view_output_refs.add(ref_id)
                    expected_output = initial_outputs[ref_id]
                    expected = {
                        "kind": "numeric",
                        "value": expected_output["value"],
                        "quantity": expected_output["quantity"],
                    }
                    expected_lineage = expected_output["lineage"]
                    display_precisions = (numeric_definitions[ref_id]["round"],)
                    endpoint_values = (rounded_model(minimum), rounded_model(maximum))
                    _scene_relation(
                        all(view_domains[axis][0] <= value <= view_domains[axis][1] for value in endpoint_values),
                        here + "/" + axis,
                    )
            else:
                _scene_relation(unresolved["kind"] == "numeric", here + "/" + axis)
                expected = {
                    "kind": "numeric",
                    "value": unresolved["value"],
                    "quantity": unresolved["quantity"],
                }
                expected_lineage = leaf_lineage(
                    unresolved["lineage"], expected["quantity"], "Value",
                    here + "/" + axis + "/lineage",
                    max_bases=1,
                    max_normalizations=1,
                )
                minimum_precision = max(0, -Decimal(expected["value"]).as_tuple().exponent)
                display_precisions = range(minimum_precision, scale + 1)
            _scene_reference(expected["quantity"] in quantity_ids, here + "/" + axis + "/quantity")
            _scene_relation(expected["quantity"] == axis_quantity, here + "/" + axis + "/quantity")
            _scene_relation(
                resolved["kind"] == expected["kind"]
                and resolved["value"] == expected["value"]
                and resolved["quantity"] == expected["quantity"]
                and resolved["lineage"] == expected_lineage
                and any(
                    evaluated_point[axis + "Text"]
                    == format_numeric(expected["value"], expected["quantity"], precision)
                    for precision in display_precisions
                ),
                f"{location}/initialEvaluation/view/points/{index}/{axis}",
            )
            resolved_value = decimal(
                resolved["value"], f"{location}/initialEvaluation/view/points/{index}/{axis}/value"
            )
            domain = view_domains[axis]
            _scene_relation(domain[0] <= resolved_value <= domain[1], here + "/" + axis)
            lineage(resolved["lineage"], f"{location}/initialEvaluation/view/points/{index}/{axis}/lineage")
    _scene_relation(view_output_refs == set(reporting_ids), location + "/view/points")
    _scene_relation(leaf_ids == owned_leaf_ids, location + "/evidence/leaves")

    narration = scene["narration"]
    _scene_relation(
        narration["templates"] == narration["templatesByLocale"][scene["locale"]]
        and narration["messages"] == narration["messagesByLocale"][scene["locale"]],
        location + "/narration",
    )
    _scene_relation(
        narration["templatesByLocale"] == _NARRATION_TEMPLATES,
        location + "/narration/templatesByLocale",
    )
    program = narration["program"]
    program_controls = program["controls"]
    for index, program_item in enumerate(program_controls):
        _scene_reference(
            program_item["id"] in control_by_id,
            f"{location}/narration/program/controls/{index}/id",
        )
    _scene_relation([item["id"] for item in program_controls] == [control_id], location + "/narration/program/controls")
    program_control = program_controls[0]
    control_quantity = scene["quantities"][control["quantity"]]
    _scene_relation(
        program_control["kind"] == control["kind"]
        and program_control["label"] == control["label"]
        and program_control["baseline"] == scene["initialState"][control_id]
        and program_control["unit"] == control_quantity["unit"]
        and program_control["display"] == control_quantity["display"]
        and program_control["precision"] == scale,
        location + "/narration/program/controls/0",
    )
    program_outputs = program["outputs"]
    for index, program_item in enumerate(program_outputs):
        _scene_reference(
            program_item["id"] in numeric_definitions,
            f"{location}/narration/program/outputs/{index}/id",
        )
    _scene_relation([item["id"] for item in program_outputs] == reporting_ids, location + "/narration/program/outputs")
    for index, output in enumerate(program_outputs):
        output_id = output["id"]
        _scene_reference(output_id in numeric_definitions, f"{location}/narration/program/outputs/{index}/id")
        definition = numeric_definitions[output_id]
        quantity = scene["quantities"][definition["quantity"]]
        _scene_relation(
            output["label"] == definition["label"]
            and output["baseline"] == initial_outputs[output_id]["value"]
            and output["unit"] == quantity["unit"]
            and output["display"] == quantity["display"]
            and output["precision"] == definition["round"],
            f"{location}/narration/program/outputs/{index}",
        )
    transition_ids = [item["id"] for item in program["transitions"]]
    expected_transitions = [
        output_id for output_id in definitions
        if output_id in ("classification", "decisionStatus") and definitions[output_id]["kind"] == "text"
    ]
    for index, transition_id in enumerate(transition_ids):
        _scene_reference(transition_id in definitions, f"{location}/narration/program/transitions/{index}/id")
    _scene_relation(transition_ids == expected_transitions, location + "/narration/program/transitions")
    for index, transition in enumerate(program["transitions"]):
        _scene_relation(
            transition["baseline"] == initial_outputs[transition["id"]]["value"],
            f"{location}/narration/program/transitions/{index}/baseline",
        )
    expected_messages_by_locale: dict[str, dict[str, str]] = {}
    primary_atom = program_outputs[0]
    primary_definition = numeric_definitions[primary_atom["id"]]
    primary_text = primary_atom["label"] + " " + format_numeric(
        initial_outputs[primary_atom["id"]]["value"],
        primary_definition["quantity"],
        primary_definition["round"],
    )
    transition_text = [transition["baseline"] for transition in program["transitions"]]
    for locale, templates in _NARRATION_TEMPLATES.items():
        initial_text = "; ".join([templates["baseline"] + ": " + primary_text, *transition_text])
        reset_text = "; ".join([templates["reset"] + ": " + primary_text, *transition_text])
        _scene_relation(
            len(initial_text) <= narration["maxScalars"]
            and len(reset_text) <= narration["maxScalars"],
            location + "/narration/messagesByLocale/" + locale,
        )
        expected_messages_by_locale[locale] = {
            "evidence:closed": templates["closed"],
            "evidence:sources": templates["sources"],
            "evidence:assumptions": templates["assumptions"],
            "evidence:both": templates["both"],
            "panels:closed": "説明を閉じました" if locale == "ja" else "Panels closed",
            "initial": initial_text,
            "reset": reset_text,
        }
    _scene_relation(
        narration["messagesByLocale"] == expected_messages_by_locale
        and narration["messages"] == expected_messages_by_locale[scene["locale"]],
        location + "/narration/messagesByLocale",
    )
    validated_variants = 0
    for position in range(int(positions) + 1):
        control_value = minimum + step * position
        model_at_state = rounded_model(control_value)
        outputs_at_state: dict[str, dict[str, object]] = {
            model_output: {"value": model_at_state},
        }
        if decision is not None:
            state_comparisons = {
                "gte": model_at_state >= threshold_value,
                "gt": model_at_state > threshold_value,
                "lte": model_at_state <= threshold_value,
                "lt": model_at_state < threshold_value,
            }
            state_selected = (
                decision["whenMet"]
                if state_comparisons[decision["operator"]]
                else decision["whenNotMet"]
            )
            outputs_at_state["decisionStatus"] = {"value": state_selected["status"]}
            outputs_at_state["recommendation"] = {
                "value": state_selected["recommendation"]
            }
        state = {control_id: control_value}
        evaluation = {"outputs": outputs_at_state}
        for locale in _NARRATION_TEMPLATES:
            plan = dict(narration)
            plan["locale"] = locale
            for event, triggering_control in (
                ("restore", None),
                ("direct", control_id),
            ):
                try:
                    render_narration(
                        plan,
                        state,
                        evaluation,
                        event=event,
                        control=triggering_control,
                    )
                except Exception:
                    _scene_relation(False, location + "/narration/program")
                validated_variants += 1
    expected_variants = (int(positions) + 1) * len(_NARRATION_TEMPLATES) * (1 + len(program_controls))
    _scene_relation(
        validated_variants == expected_variants
        and narration["validatedVariants"] == expected_variants,
        location + "/narration/validatedVariants",
    )

    for index, step_record in enumerate(scene["steps"]):
        action = step_record["action"]
        if action["type"] == "set":
            _scene_reference(action["control"] in control_by_id, f"{location}/steps/{index}/action/control")
            on_grid(action["value"], f"{location}/steps/{index}/action/value")


_NO_DEMO_PANEL = object()


def _validate_demo_reachability(
    steps: list,
    location: str,
    *,
    initial_panel: object = _NO_DEMO_PANEL,
    panel_can_close: bool = True,
    initial_evidence_open: bool = False,
) -> None:
    """Reject demo actions whose prebuilt owner target is not currently reachable."""
    evidence_open = initial_evidence_open
    current_panel = initial_panel
    terminal_goto = False
    for index, step in enumerate(steps):
        here = f"{location}/{index}/action/type"
        action = step["action"]
        action_type = action["type"]
        if terminal_goto:
            _raise("scene_relation", here, "goto must be the terminal demo action")
        if evidence_open:
            if action_type == "wait":
                continue
            if action_type == "closeEvidence":
                evidence_open = False
                continue
            _raise("scene_relation", here, "evidence must close before another owner action")
        if action_type == "openEvidence":
            evidence_open = True
        elif action_type == "closeEvidence":
            _raise("scene_relation", here, "evidence close target is not visible")
        elif action_type == "openPanel":
            if current_panel is _NO_DEMO_PANEL:
                _raise("scene_relation", here, "panel action is not available in this scene")
            current_panel = action["panel"]
        elif action_type == "closePanel":
            if current_panel is _NO_DEMO_PANEL or current_panel != action["panel"]:
                _raise("scene_relation", here, "panel close target is not visible")
            if not panel_can_close:
                _raise("scene_relation", here, "the required accordion panel cannot close")
            current_panel = None
        elif action_type == "goto":
            terminal_goto = True


def _validate_task4_scene(
    scene: dict,
    slide_id: str,
    lang: str,
    location: str,
) -> tuple[int, int, int, int, tuple[str, ...], tuple[str, ...]]:
    required = _SCENE_KEYS - {"model", "reporting", "decisionContract", "view", "states"}
    item = _closed_object(scene, required, _SCENE_KEYS - required, location)
    if _integer(item["version"], location + "/version", 1, 1) != 1:
        _raise("scene_shape", location + "/version", "expected scene version 1")
    if item["slideId"] != slide_id or item["locale"] != lang:
        _raise("scene_shape", location, "compiled scene identity does not match its slide")
    if item["type"] != "slider_model":
        _raise("scene_shape", location + "/type", "Task 4 requires slider_model")
    _integer(item["scale"], location + "/scale", 0, 6)
    for key in ("purpose", "interactionRationale"):
        _text(item[key], location + "/" + key, 500, empty=False)
    if item["decisionJob"] not in ("fact", "insight", "action", "decision"):
        _raise("scene_shape", location + "/decisionJob", "unexpected decision job")

    controls = _array(item["controls"], location + "/controls", maximum=8)
    control_ids: set[str] = set()
    for index, control in enumerate(controls):
        here = f"{location}/controls/{index}"
        record = _closed_object(
            control,
            {"id", "kind", "label", "min", "max", "step", "quantity", "lineage"},
            set(),
            here,
        )
        identifier = _identifier(record["id"], here + "/id")
        if identifier in control_ids or record["kind"] != "range":
            _raise("scene_shape", here, "expected unique range control")
        control_ids.add(identifier)
        _text(record["label"], here + "/label", 40, empty=False)
        for key in ("min", "max", "step"):
            _decimal_text(record[key], here + "/" + key)
        _identifier(record["quantity"], here + "/quantity")
        _validate_lineage(record["lineage"], here + "/lineage")
    for state_key in ("initialState", "printState"):
        state = item[state_key]
        if not isinstance(state, dict) or set(state) != control_ids:
            _raise("scene_shape", location + "/" + state_key, "state keys must match declared controls")
        for control_id, state_value in state.items():
            _decimal_text(state_value, location + "/" + state_key + "/" + control_id)

    _validate_quantities(item["quantities"], location + "/quantities")
    _validate_output_definitions(item["outputDefinitions"], location + "/outputDefinitions")
    output_ids = set(item["outputDefinitions"])
    _validate_evidence(item["evidence"], location + "/evidence")
    invariants = item["invariants"]
    invariant_keys = {
        "headline", "subline", "source", "footnotes", "eyebrow", "section",
        "page_number", "classification", "lang", "theme", "palette",
    }
    if not isinstance(invariants, dict) or set(invariants) - invariant_keys:
        _raise("scene_shape", location + "/invariants", "unexpected invariant chrome")
    for key, invariant in invariants.items():
        if key == "footnotes":
            footnotes = _array(
                invariant,
                location + "/invariants/footnotes",
                maximum=2,
            )
            for index, footnote in enumerate(footnotes):
                _text(
                    footnote,
                    f"{location}/invariants/footnotes/{index}",
                    500,
                )
        else:
            _text(invariant, location + "/invariants/" + key, 500)
    if invariants.get("theme", "classic") not in ("classic", "executive"):
        _raise("scene_shape", location + "/invariants/theme", "unexpected fallback theme")
    if invariants.get("palette", "navy") not in ("navy", "red", "green", "mono"):
        _raise("scene_shape", location + "/invariants/palette", "unexpected fallback palette")
    fallback = _closed_object(item["fallback"], {"matched", "pattern"}, set(), location + "/fallback")
    if fallback["matched"] is not True or fallback["pattern"] != "scatter":
        _raise("scene_shape", location + "/fallback", "Task 4 requires matched scatter fallback")

    model = _closed_object(item.get("model"), {"kind", "output", "intercept", "terms"}, set(), location + "/model")
    if model["kind"] != "linear":
        _raise("scene_shape", location + "/model/kind", "Task 4 requires linear model")
    _registry_id(model["output"], location + "/model/output")
    _validate_typed_value(model["intercept"], location + "/model/intercept")
    term_controls: set[str] = set()
    for index, term in enumerate(_array(model["terms"], location + "/model/terms", maximum=8)):
        here = f"{location}/model/terms/{index}"
        if not isinstance(term, list) or len(term) != 2:
            _raise("scene_shape", here, "linear term must be a two-item pair")
        term_control = _identifier(term[0], here + "/0")
        if term_control in term_controls:
            _raise("duplicate_id", here + "/0", "duplicate linear-model control term")
        term_controls.add(term_control)
        record = _closed_object(term[1], {"value", "inputQuantity", "outputQuantity"}, set(), here + "/1")
        _validate_typed_value(record["value"], here + "/1/value")
        _identifier(record["inputQuantity"], here + "/1/inputQuantity")
        _identifier(record["outputQuantity"], here + "/1/outputQuantity")

    reporting = _closed_object(
        item.get("reporting"), {"primaryOutput", "secondaryOutputs"}, set(), location + "/reporting"
    )
    _registry_id(reporting["primaryOutput"], location + "/reporting/primaryOutput")
    for index, output_id in enumerate(_array(reporting["secondaryOutputs"], location + "/reporting/secondaryOutputs", maximum=2)):
        _registry_id(output_id, f"{location}/reporting/secondaryOutputs/{index}")

    decision = None
    if "decisionContract" in item:
        decision = _closed_object(
            item["decisionContract"],
            {"id", "metric", "operator", "threshold", "whenMet", "whenNotMet"},
            set(),
            location + "/decisionContract",
        )
        _identifier(decision["id"], location + "/decisionContract/id")
        metric = _closed_object(decision["metric"], {"ref"}, set(), location + "/decisionContract/metric")
        _validate_typed_value(metric, location + "/decisionContract/metric", allow_reference=True)
        if decision["operator"] not in ("gte", "gt", "lte", "lt"):
            _raise("scene_shape", location + "/decisionContract/operator", "unexpected decision operator")
        threshold = _closed_object(
            decision["threshold"], {"value", "quantity", "provenance"}, set(), location + "/decisionContract/threshold"
        )
        _decimal_text(threshold["value"], location + "/decisionContract/threshold/value")
        _identifier(threshold["quantity"], location + "/decisionContract/threshold/quantity")
        _validate_provenance(threshold["provenance"], location + "/decisionContract/threshold/provenance")
        for outcome in ("whenMet", "whenNotMet"):
            record = _closed_object(decision[outcome], {"status", "recommendation"}, set(), location + "/decisionContract/" + outcome)
            _text(record["status"], location + "/decisionContract/" + outcome + "/status", 32, empty=False)
            _text(record["recommendation"], location + "/decisionContract/" + outcome + "/recommendation", 500, empty=False)

    point_ids = _validate_dot_view(item.get("view"), location + "/view", resolved=False)
    view_items = len(point_ids)
    if "states" in item:
        _raise("scene_shape", location + "/states", "slider_model must not contain state views")
    initial_evaluation = _closed_object(
        item["initialEvaluation"], {"outputs", "view"}, {"decision"}, location + "/initialEvaluation"
    )
    outputs = initial_evaluation["outputs"]
    if not isinstance(outputs, dict) or set(outputs) != output_ids:
        _raise("scene_shape", location + "/initialEvaluation/outputs", "evaluated outputs must match output definitions")
    for output_id, output in outputs.items():
        _registry_id(output_id, location + "/initialEvaluation/outputs/" + str(output_id))
        _validate_typed_value(output, location + "/initialEvaluation/outputs/" + output_id)
    evaluated_point_ids = _validate_dot_view(
        initial_evaluation["view"], location + "/initialEvaluation/view", resolved=True
    )
    if evaluated_point_ids != point_ids:
        _raise("scene_shape", location + "/initialEvaluation/view", "evaluated point IDs must match the compiled view")
    view_items += len(evaluated_point_ids)
    if "decision" in initial_evaluation:
        result = _closed_object(
            initial_evaluation["decision"],
            {"outcome", "distance", "quantity", "status", "recommendation", "lineage"},
            set(),
            location + "/initialEvaluation/decision",
        )
        if result["outcome"] not in ("met", "notMet"):
            _raise("scene_shape", location + "/initialEvaluation/decision/outcome", "unexpected decision outcome")
        _decimal_text(result["distance"], location + "/initialEvaluation/decision/distance")
        _identifier(result["quantity"], location + "/initialEvaluation/decision/quantity")
        _text(result["status"], location + "/initialEvaluation/decision/status", 500, empty=False)
        _text(result["recommendation"], location + "/initialEvaluation/decision/recommendation", 500, empty=False)
        _validate_lineage(result["lineage"], location + "/initialEvaluation/decision/lineage")

    _validate_narration(item["narration"], location + "/narration", lang)
    targets = item["targets"]
    if not isinstance(targets, dict):
        _raise("scene_shape", location + "/targets", "expected target registry")
    expected_targets = {
        "evidence:open": {"kind": "evidence"},
        "evidence:close": {"kind": "evidence"},
        "static:toggle": {"kind": "static"},
    }
    expected_targets.update({
        "control:" + control_id: {"kind": "control", "id": control_id}
        for control_id in control_ids
    })
    for source in item["evidence"]["sources"]:
        if source["linked"]:
            expected_targets["source:" + source["id"]] = {"kind": "source", "id": source["id"]}
    if targets != expected_targets:
        _raise("scene_shape", location + "/targets", "target registry does not match compiled scene registries")
    for target_key, target in targets.items():
        _text(target_key, location + "/targets", 140, empty=False)
        record = _closed_object(target, {"kind"}, {"id"}, location + "/targets/" + target_key)
        if record["kind"] not in ("control", "source", "evidence", "static"):
            _raise("scene_shape", location + "/targets/" + target_key + "/kind", "unsupported target kind")
        if "id" in record:
            _identifier(record["id"], location + "/targets/" + target_key + "/id")

    step_keys: list[str] = []
    goto_ids: list[str] = []
    wait_ms = 0
    steps = _array(item["steps"], location + "/steps", maximum=80)
    for index, step in enumerate(steps):
        here = f"{location}/steps/{index}"
        record = _closed_object(step, {"stepKey", "action"}, {"targetKey"}, here)
        step_key = _identifier(record["stepKey"], here + "/stepKey")
        if step_key in step_keys:
            _raise("duplicate_id", here + "/stepKey", "duplicate compiled step key")
        step_keys.append(step_key)
        action = record["action"]
        if not isinstance(action, dict) or not isinstance(action.get("type"), str):
            _raise("scene_shape", here + "/action", "expected compiled demo action")
        action_type = action["type"]
        action_shapes = {
            "set": ({"type", "control", "value"}, set()),
            "openEvidence": ({"type"}, set()),
            "closeEvidence": ({"type"}, set()),
            "goto": ({"type", "slideId"}, set()),
            "wait": ({"type", "ms"}, set()),
        }
        if action_type not in action_shapes:
            _raise("scene_shape", here + "/action/type", "unsupported Task 4 demo action")
        action_record = _closed_object(action, *action_shapes[action_type], here + "/action")
        if action_type == "set":
            control_id = _identifier(action_record["control"], here + "/action/control")
            if control_id not in control_ids:
                _raise("scene_shape", here + "/action/control", "demo control is not registered")
            _decimal_text(action_record["value"], here + "/action/value")
            expected_target = "control:" + control_id
        elif action_type in ("openEvidence", "closeEvidence"):
            expected_target = "evidence:open" if action_type == "openEvidence" else "evidence:close"
        elif action_type == "goto":
            goto_ids.append(_identifier(action_record["slideId"], here + "/action/slideId"))
            expected_target = None
        elif action_type == "wait":
            wait_ms += _integer(action_record["ms"], here + "/action/ms", 0, 5_000)
            expected_target = None
        if expected_target is None:
            if "targetKey" in record:
                _raise("scene_shape", here + "/targetKey", "goto and wait actions cannot declare a cue target")
        elif record.get("targetKey") != expected_target or expected_target not in targets:
            _raise("scene_shape", here + "/targetKey", "demo target does not match its compiled action")
    if wait_ms > MAX_SCENE_WAIT_MS:
        _raise("aggregate_limit", location + "/steps", "declared waits exceed 30 seconds for one scene")
    _validate_demo_reachability(steps, location + "/steps")
    _validate_scene_relations(item, location)
    return view_items, len(targets), len(steps), wait_ms, tuple(step_keys), tuple(goto_ids)


def _compiled_task4_scene_state_count(scene: object, location: str) -> int:
    if not isinstance(scene, dict):
        _raise("scene_shape", location, "compiled scene must be an object")
    controls = scene.get("controls")
    if not isinstance(controls, list) or len(controls) != 1:
        return 0
    if not isinstance(controls[0], dict):
        _raise("scene_shape", location + "/controls/0", "compiled control must be an object")
    control = controls[0]
    if control.get("kind") != "range":
        _raise("scene_shape", location + "/controls/0/kind", "Task 4 requires a range control")
    values = [
        Decimal(_decimal_text(control.get(key), location + "/controls/0/" + key))
        for key in ("min", "max", "step")
    ]
    minimum, maximum, step = values
    positions = (maximum - minimum) / step if step > 0 else Decimal("-1")
    if (
        not minimum < maximum
        or step <= 0
        or positions != positions.to_integral_value()
        or not 0 < positions <= 10_000
    ):
        _raise("scene_relation", location + "/controls/0", "compiled range grid is invalid")
    accepted_states = int(positions) + 1
    narration = scene.get("narration")
    if not isinstance(narration, dict):
        _raise("scene_shape", location + "/narration", "compiled narration must be an object")
    validated_variants = narration.get("validatedVariants")
    if type(validated_variants) is not int or validated_variants != accepted_states * 4:
        _raise(
            "scene_relation",
            location + "/narration/validatedVariants",
            "compiled narration work does not match accepted states",
        )
    return accepted_states


def _validate_invariant_chrome(value: object, location: str) -> None:
    allowed = {
        "headline", "subline", "source", "footnotes", "eyebrow", "section",
        "page_number", "classification", "lang", "theme", "palette",
    }
    if not isinstance(value, dict) or set(value) - allowed:
        _raise("scene_shape", location, "unexpected invariant chrome")
    for key, item in value.items():
        if key == "footnotes":
            for index, note in enumerate(_array(item, location + "/footnotes", maximum=2)):
                _text(note, f"{location}/footnotes/{index}", 500)
        elif key == "page_number":
            if isinstance(item, bool) or not isinstance(item, (int, str)):
                _raise("scene_shape", location + "/page_number", "expected bounded page number")
            _text(str(item), location + "/page_number", 500)
        else:
            _text(item, location + "/" + key, 500)
    if value.get("theme", "classic") not in ("classic", "executive"):
        _raise("scene_shape", location + "/theme", "unexpected fallback theme")
    if value.get("palette", "navy") not in ("navy", "red", "green", "mono"):
        _raise("scene_shape", location + "/palette", "unexpected fallback palette")


def _validate_disclosure_narration(value: object, location: str, lang: str, *, panels: tuple[str, ...] = ()) -> None:
    item = _closed_object(
        value,
        {"locale", "templates", "templatesByLocale", "messages", "messagesByLocale", "program", "validatedVariants", "comparison", "maxScalars"},
        set(),
        location,
    )
    if item["locale"] != lang or item["comparison"] != "initialState":
        _raise("scene_shape", location, "narration identity mismatch")
    if _integer(item["maxScalars"], location + "/maxScalars", 1, 2_000) != 160:
        _raise("scene_shape", location + "/maxScalars", "unexpected narration scalar cap")
    _integer(item["validatedVariants"], location + "/validatedVariants", 0, MAX_JSON_NODES)
    template_keys = set(_NARRATION_TEMPLATES["en"])
    templates_by_locale = _closed_object(item["templatesByLocale"], {"en", "ja"}, set(), location + "/templatesByLocale")
    messages_by_locale = _closed_object(item["messagesByLocale"], {"en", "ja"}, set(), location + "/messagesByLocale")
    message_keys = {
        "evidence:closed", "evidence:sources", "evidence:assumptions",
        "evidence:both", "panels:closed", "initial", "reset",
    }
    message_keys.update(action + ":" + panel for panel in panels for action in ("openPanel", "closePanel"))
    for locale in ("en", "ja"):
        templates = _closed_object(templates_by_locale[locale], template_keys, set(), location + "/templatesByLocale/" + locale)
        if templates != _NARRATION_TEMPLATES[locale]:
            _raise("scene_relation", location + "/templatesByLocale/" + locale, "narration templates must be compiler-owned")
        messages = _closed_object(messages_by_locale[locale], message_keys, set(), location + "/messagesByLocale/" + locale)
        for key, text_value in messages.items():
            _text(text_value, location + "/messagesByLocale/" + locale + "/" + key, 160)
    if item["templates"] != templates_by_locale[lang] or item["messages"] != messages_by_locale[lang]:
        _raise("scene_relation", location, "localized narration aliases must match the selected locale")
    program = _closed_object(item["program"], {"kind", "stateKey"}, set(), location + "/program")
    if program["kind"] != "disclosure_v1" or program["stateKey"] not in ("evidence", "panel"):
        _raise("scene_shape", location + "/program", "expected the closed disclosure narration program")


def _validate_task5_fallback(value: object, location: str) -> dict:
    fallback = _closed_object(
        value,
        {
            "matched", "pattern", "paragraphs", "baselineAnnotation",
            "thresholdText", "axisTickLabels",
        },
        set(),
        location,
    )
    if fallback["matched"] is not True:
        _raise("scene_relation", location, "fallback must be compiler matched")
    _text(fallback["pattern"], location + "/pattern", 64, empty=False)
    paragraphs = _array(fallback["paragraphs"], location + "/paragraphs", maximum=1_000)
    for index, paragraph in enumerate(paragraphs):
        _text(paragraph, f"{location}/paragraphs/{index}", 2_000)
    _text(fallback["baselineAnnotation"], location + "/baselineAnnotation", 2_000)
    if fallback["thresholdText"] is not None:
        _text(fallback["thresholdText"], location + "/thresholdText", 500)
    ticks = fallback["axisTickLabels"]
    if ticks is not None:
        row = _closed_object(ticks, {"x", "y"}, set(), location + "/axisTickLabels")
        for axis in ("x", "y"):
            labels = _array(row[axis], location + "/axisTickLabels/" + axis, maximum=2)
            if len(labels) != 2:
                _raise(
                    "scene_shape",
                    location + "/axisTickLabels/" + axis,
                    "expected two tick labels",
                )
            for index, label in enumerate(labels):
                _text(label, f"{location}/axisTickLabels/{axis}/{index}", 500)
    return fallback


def _validate_disclosure_scene(
    scene: dict,
    slide_id: str,
    lang: str,
    location: str,
) -> tuple[int, int, int, int, tuple[str, ...], tuple[str, ...]]:
    required = _SCENE_KEYS - {"model", "reporting", "decisionContract", "view", "states"}
    item = _closed_object(scene, required, set(), location)
    if _integer(item["version"], location + "/version", 1, 1) != 1:
        _raise("scene_shape", location + "/version", "expected scene version 1")
    if item["slideId"] != slide_id or item["locale"] != lang or item["type"] != "evidence_only":
        _raise("scene_shape", location, "compiled disclosure identity does not match its slide")
    _integer(item["scale"], location + "/scale", 0, 6)
    for key in ("purpose", "interactionRationale"):
        _text(item[key], location + "/" + key, 500, empty=False)
    if item["decisionJob"] not in ("fact", "insight", "action", "decision"):
        _raise("scene_shape", location + "/decisionJob", "unexpected decision job")
    if item["controls"] != [] or item["quantities"] != {} or item["outputDefinitions"] != {}:
        _raise("scene_shape", location, "evidence-only scenes cannot carry controls, quantities or outputs")
    available = {"closed"}
    evidence = item["evidence"]
    _validate_evidence(evidence, location + "/evidence")
    if evidence["sources"]:
        available.add("sources")
    if evidence["assumptions"]:
        available.add("assumptions")
    if evidence["sources"] and evidence["assumptions"]:
        available.add("both")
    for state_key in ("initialState", "printState"):
        state = _closed_object(item[state_key], {"evidence"}, set(), location + "/" + state_key)
        if state["evidence"] not in available:
            _raise("scene_shape", location + "/" + state_key + "/evidence", "unavailable evidence mode")
    if item["initialState"] != item["printState"]:
        _raise("scene_relation", location + "/printState", "print state must equal initial state")
    initial = _closed_object(item["initialEvaluation"], {"outputs", "view"}, set(), location + "/initialEvaluation")
    if initial["outputs"] != {} or initial["view"] is not None:
        _raise("scene_shape", location + "/initialEvaluation", "evidence-only evaluation must be empty")
    _validate_invariant_chrome(item["invariants"], location + "/invariants")
    _validate_task5_fallback(item["fallback"], location + "/fallback")
    _validate_disclosure_narration(item["narration"], location + "/narration", lang)

    expected_targets = {
        "evidence:open": {"kind": "evidence"},
        "evidence:close": {"kind": "evidence"},
        "static:toggle": {"kind": "static"},
    }
    for source in evidence["sources"]:
        if source["linked"]:
            expected_targets["source:" + source["id"]] = {"kind": "source", "id": source["id"]}
    if item["targets"] != expected_targets:
        _raise("scene_relation", location + "/targets", "target registry does not match the disclosure scene")

    step_keys: list[str] = []
    goto_ids: list[str] = []
    wait_ms = 0
    steps = _array(item["steps"], location + "/steps", maximum=80)
    for index, step in enumerate(steps):
        here = f"{location}/steps/{index}"
        record = _closed_object(step, {"stepKey", "action"}, {"targetKey"}, here)
        step_key = _identifier(record["stepKey"], here + "/stepKey")
        if step_key in step_keys:
            _raise("duplicate_id", here + "/stepKey", "duplicate compiled step key")
        step_keys.append(step_key)
        action = record["action"]
        if not isinstance(action, dict) or not isinstance(action.get("type"), str):
            _raise("scene_shape", here + "/action", "expected compiled demo action")
        action_type = action["type"]
        if action_type in ("openEvidence", "closeEvidence"):
            _closed_object(action, {"type"}, set(), here + "/action")
            expected_target = "evidence:open" if action_type == "openEvidence" else "evidence:close"
            if record.get("targetKey") != expected_target:
                _raise("scene_relation", here + "/targetKey", "evidence cue target mismatch")
        elif action_type == "goto":
            target = _closed_object(action, {"type", "slideId"}, set(), here + "/action")
            goto_ids.append(_identifier(target["slideId"], here + "/action/slideId"))
            if "targetKey" in record:
                _raise("scene_shape", here + "/targetKey", "goto cannot declare a cue target")
        elif action_type == "wait":
            wait = _closed_object(action, {"type", "ms"}, set(), here + "/action")
            wait_ms += _integer(wait["ms"], here + "/action/ms", 0, 5_000)
            if "targetKey" in record:
                _raise("scene_shape", here + "/targetKey", "wait cannot declare a cue target")
        else:
            _raise("scene_shape", here + "/action/type", "unsupported evidence-only demo action")
    if wait_ms > MAX_SCENE_WAIT_MS:
        _raise("aggregate_limit", location + "/steps", "declared waits exceed 30 seconds for one scene")
    _validate_demo_reachability(
        steps,
        location + "/steps",
        initial_evidence_open=item["initialState"]["evidence"] != "closed",
    )
    return 0, len(item["targets"]), len(item["steps"]), wait_ms, tuple(step_keys), tuple(goto_ids)


def _validate_task5_control(value: object, location: str) -> tuple[str, int, tuple[str, ...]]:
    if not isinstance(value, dict):
        _raise("scene_shape", location, "expected compiled control")
    kind = value.get("kind")
    if kind == "range":
        item = _closed_object(
            value,
            {"id", "kind", "label", "min", "max", "step", "quantity", "lineage"},
            set(),
            location,
        )
        control_id = _identifier(item["id"], location + "/id")
        _text(item["label"], location + "/label", 40, empty=False)
        minimum, maximum, step = (
            Decimal(_decimal_text(item[key], location + "/" + key))
            for key in ("min", "max", "step")
        )
        positions = (maximum - minimum) / step if step > 0 else Decimal("-1")
        if (
            not minimum < maximum
            or positions != positions.to_integral_value()
            or not 0 < positions <= 10_000
        ):
            _raise("scene_relation", location, "compiled range grid is invalid")
        _identifier(item["quantity"], location + "/quantity")
        _validate_lineage(item["lineage"], location + "/lineage")
        return control_id, int(positions) + 1, tuple(
            canonical_decimal(minimum + step * index)
            for index in range(int(positions) + 1)
        )
    if kind not in ("segmented", "toggle", "select"):
        _raise("scene_shape", location + "/kind", "unsupported compiled control kind")
    item = _closed_object(value, {"id", "kind", "label", "options"}, set(), location)
    control_id = _identifier(item["id"], location + "/id")
    _text(item["label"], location + "/label", 40, empty=False)
    options = _array(
        item["options"],
        location + "/options",
        maximum=2 if kind == "toggle" else 8 if kind == "select" else 4,
    )
    if len(options) < 2 or (kind == "toggle" and len(options) != 2):
        _raise("scene_shape", location + "/options", "compiled option count is invalid")
    option_ids: list[str] = []
    for index, option in enumerate(options):
        here = f"{location}/options/{index}"
        record = _closed_object(option, {"value", "label"}, set(), here)
        option_id = _identifier(record["value"], here + "/value")
        if option_id in option_ids:
            _raise("duplicate_id", here + "/value", "duplicate compiled option")
        option_ids.append(option_id)
        _text(record["label"], here + "/label", 40, empty=False)
    return control_id, len(options), tuple(option_ids)


def _validate_task5_view(value: object, location: str, *, resolved: bool) -> tuple[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        _raise("scene_shape", location, "expected compiled view")
    component = value.get("component")
    if component == "dot_plot":
        return component, _validate_dot_view(value, location, resolved=resolved)
    if component == "recommendation_panel":
        item = _closed_object(value, {"component", "score", "annotation"}, set(), location)
        _validate_typed_value(item["score"], location + "/score", allow_reference=not resolved)
        _text(item["annotation"], location + "/annotation", 500)
        return component, ("score",)
    if component not in ("bar_compare", "ranked_list"):
        _raise("scene_shape", location + "/component", "unsupported compiled view component")
    required = {"component", "items"}
    optional: set[str] = set()
    if component == "bar_compare" or any(
        isinstance(row, dict) and "metric" in row
        for row in value.get("items", []) if isinstance(value.get("items"), list)
    ):
        required |= {"quantity", "domain", "baseline"}
    else:
        optional |= {"quantity", "domain", "baseline"}
    item = _closed_object(value, required, optional, location)
    if "quantity" in item:
        _identifier(item["quantity"], location + "/quantity")
        domain = _array(item["domain"], location + "/domain", maximum=2)
        if len(domain) != 2:
            _raise("scene_shape", location + "/domain", "expected fixed two-value domain")
        lo, hi = (Decimal(_decimal_text(raw, location + "/domain")) for raw in domain)
        if lo != 0 or lo >= hi or Decimal(_decimal_text(item["baseline"], location + "/baseline")) != 0:
            _raise("scene_relation", location, "bar/ranked numeric domain must start at zero")
    rows = _array(item["items"], location + "/items", maximum=12)
    if not rows:
        _raise("scene_shape", location + "/items", "view requires at least one item")
    identifiers: list[str] = []
    ranks: list[int] = []
    for index, row in enumerate(rows):
        here = f"{location}/items/{index}"
        if component == "bar_compare":
            keys = {"id", "label", "emphasis", "removed", "value"}
            if resolved:
                keys.add("valueText")
            record = _closed_object(row, keys, set(), here)
            _validate_typed_value(record["value"], here + "/value", allow_reference=not resolved)
            if resolved:
                _text(record["valueText"], here + "/valueText", 500)
        else:
            keys = {"id", "label", "emphasis", "removed", "rank"}
            optional_keys = {"metric", "metricText"} if resolved else {"metric"}
            record = _closed_object(row, keys, optional_keys, here)
            rank = _integer(record["rank"], here + "/rank", 1, len(rows))
            ranks.append(rank)
            if "metric" in record:
                _validate_typed_value(record["metric"], here + "/metric", allow_reference=not resolved)
                if resolved:
                    _text(record.get("metricText", ""), here + "/metricText", 500)
            elif "metricText" in record:
                _raise("scene_shape", here + "/metricText", "metric text requires a metric")
        row_id = _identifier(record["id"], here + "/id")
        if row_id in identifiers:
            _raise("duplicate_id", here + "/id", "duplicate compiled view item")
        identifiers.append(row_id)
        _text(record["label"], here + "/label", 500, empty=False)
        _boolean(record["emphasis"], here + "/emphasis")
        _boolean(record["removed"], here + "/removed")
    if component == "ranked_list" and len(set(ranks)) != len(ranks):
        _raise("scene_relation", location + "/items", "compiled ranks must be unique")
    return component, tuple(identifiers)


def _validate_task5_narration(value: object, location: str, lang: str) -> None:
    item = _closed_object(
        value,
        {"locale", "templates", "templatesByLocale", "messages", "messagesByLocale", "program", "validatedVariants", "comparison", "maxScalars"},
        set(),
        location,
    )
    if item["locale"] != lang or item["comparison"] != "initialState":
        _raise("scene_shape", location, "narration identity mismatch")
    if _integer(item["maxScalars"], location + "/maxScalars", 1, 2_000) != 160:
        _raise("scene_shape", location + "/maxScalars", "unexpected narration scalar cap")
    _integer(item["validatedVariants"], location + "/validatedVariants", 0, MAX_JSON_NODES)
    template_keys = set(_NARRATION_TEMPLATES["en"])
    localized_templates = _closed_object(item["templatesByLocale"], {"en", "ja"}, set(), location + "/templatesByLocale")
    localized_messages = _closed_object(item["messagesByLocale"], {"en", "ja"}, set(), location + "/messagesByLocale")
    for locale in ("en", "ja"):
        templates = _closed_object(localized_templates[locale], template_keys, set(), location + "/templatesByLocale/" + locale)
        if templates != _NARRATION_TEMPLATES[locale]:
            _raise("scene_relation", location + "/templatesByLocale/" + locale, "narration templates must be compiler-owned")
        if not isinstance(localized_messages[locale], dict):
            _raise("scene_shape", location + "/messagesByLocale/" + locale, "expected narration messages")
        for key, message in localized_messages[locale].items():
            _text(key, location + "/messagesByLocale/" + locale, 140, empty=False)
            _text(message, location + "/messagesByLocale/" + locale + "/" + key, 160)
    if item["templates"] != localized_templates[lang] or item["messages"] != localized_messages[lang]:
        _raise("scene_relation", location, "localized narration aliases must match the selected locale")
    program = item["program"]
    if not isinstance(program, dict):
        _raise("scene_shape", location + "/program", "expected compiled narration program")
    kind = program.get("kind")
    if kind == "numeric_delta_v1":
        record = _closed_object(program, {"kind", "controls", "outputs", "transitions"}, set(), location + "/program")
        for index, atom in enumerate(_array(record["controls"], location + "/program/controls", maximum=8)):
            here = f"{location}/program/controls/{index}"
            if atom.get("kind") == "range":
                row = _closed_object(atom, {"id", "kind", "label", "baseline", "unit", "display", "precision"}, set(), here)
                _decimal_text(row["baseline"], here + "/baseline")
                for key in ("unit", "display"):
                    _text(row[key], here + "/" + key, 500)
                _integer(row["precision"], here + "/precision", 0, 6)
            else:
                row = _closed_object(atom, {"id", "kind", "label", "baseline", "options"}, set(), here)
                if row["kind"] not in ("segmented", "toggle", "select"):
                    _raise("scene_shape", here + "/kind", "unsupported narration control kind")
                _identifier(row["baseline"], here + "/baseline")
                for option_index, option in enumerate(_array(row["options"], here + "/options", maximum=8)):
                    option_row = _closed_object(option, {"value", "label"}, set(), f"{here}/options/{option_index}")
                    _identifier(option_row["value"], f"{here}/options/{option_index}/value")
                    _text(option_row["label"], f"{here}/options/{option_index}/label", 40, empty=False)
            _identifier(row["id"], here + "/id")
            _text(row["label"], here + "/label", 40, empty=False)
        for index, atom in enumerate(_array(record["outputs"], location + "/program/outputs", maximum=4)):
            here = f"{location}/program/outputs/{index}"
            row = _closed_object(atom, {"id", "label", "baseline", "unit", "display", "precision"}, set(), here)
            _registry_id(row["id"], here + "/id")
            _decimal_text(row["baseline"], here + "/baseline")
            _integer(row["precision"], here + "/precision", 0, 6)
            for key in ("label", "unit", "display"):
                _text(row[key], here + "/" + key, 500)
        for index, atom in enumerate(_array(record["transitions"], location + "/program/transitions", maximum=2)):
            row = _closed_object(atom, {"id", "baseline"}, set(), f"{location}/program/transitions/{index}")
            _registry_id(row["id"], f"{location}/program/transitions/{index}/id")
            _text(row["baseline"], f"{location}/program/transitions/{index}/baseline", 500)
    elif kind == "state_delta_v1":
        record = _closed_object(program, {"kind", "controls", "baselineView"}, set(), location + "/program")
        for index, atom in enumerate(_array(record["controls"], location + "/program/controls", maximum=1)):
            here = f"{location}/program/controls/{index}"
            row = _closed_object(atom, {"id", "kind", "label", "baseline", "options"}, set(), here)
            _identifier(row["id"], here + "/id")
            if row["kind"] not in ("segmented", "select"):
                _raise("scene_shape", here + "/kind", "unsupported state narration control")
            _identifier(row["baseline"], here + "/baseline")
            _array(row["options"], here + "/options", maximum=8)
        for index, row in enumerate(_array(record["baselineView"], location + "/program/baselineView", maximum=12)):
            here = f"{location}/program/baselineView/{index}"
            if not isinstance(row, dict):
                _raise("scene_shape", here, "unexpected baseline view item")
            keys = set(row)
            if keys == {"id", "highlight", "removed", "x", "y"}:
                _identifier(row["id"], here + "/id")
                _boolean(row["highlight"], here + "/highlight")
                _boolean(row["removed"], here + "/removed")
                _decimal_text(row["x"], here + "/x")
                _decimal_text(row["y"], here + "/y")
            elif keys == {"id", "emphasis", "removed", "value"}:
                _identifier(row["id"], here + "/id")
                _boolean(row["emphasis"], here + "/emphasis")
                _boolean(row["removed"], here + "/removed")
                _decimal_text(row["value"], here + "/value")
            elif keys in (
                {"id", "rank", "emphasis", "removed"},
                {"id", "rank", "emphasis", "removed", "metric"},
            ):
                _identifier(row["id"], here + "/id")
                _integer(row["rank"], here + "/rank", 1, 12)
                _boolean(row["emphasis"], here + "/emphasis")
                _boolean(row["removed"], here + "/removed")
                if "metric" in row:
                    _decimal_text(row["metric"], here + "/metric")
            else:
                _raise("scene_shape", here, "unexpected baseline view item")
    else:
        _raise("scene_shape", location + "/program/kind", "unsupported narration program")


def _validate_task5_model(value: object, location: str) -> str:
    if not isinstance(value, dict):
        _raise("scene_shape", location, "expected compiled model")
    kind = value.get("kind")
    if kind == "linear":
        item = _closed_object(value, {"kind", "output", "intercept", "terms"}, set(), location)
        _registry_id(item["output"], location + "/output")
        _validate_typed_value(item["intercept"], location + "/intercept")
        for index, term in enumerate(_array(item["terms"], location + "/terms", maximum=8)):
            here = f"{location}/terms/{index}"
            if not isinstance(term, list) or len(term) != 2:
                _raise("scene_shape", here, "linear term must be a pair")
            _identifier(term[0], here + "/0")
            record = _closed_object(term[1], {"value", "inputQuantity", "outputQuantity"}, set(), here + "/1")
            _validate_typed_value(record["value"], here + "/1/value")
            _identifier(record["inputQuantity"], here + "/1/inputQuantity")
            _identifier(record["outputQuantity"], here + "/1/outputQuantity")
    elif kind == "lookup":
        item = _closed_object(value, {"kind", "output", "input", "entries"}, set(), location)
        _registry_id(item["output"], location + "/output")
        _identifier(item["input"], location + "/input")
        for index, entry in enumerate(_array(item["entries"], location + "/entries", maximum=10_001)):
            here = f"{location}/entries/{index}"
            if not isinstance(entry, list) or len(entry) != 2:
                _raise("scene_shape", here, "lookup entry must be a pair")
            _decimal_text(entry[0], here + "/0")
            _validate_typed_value(entry[1], here + "/1")
    elif kind == "state_map":
        item = _closed_object(value, {"kind", "input", "entries"}, set(), location)
        _identifier(item["input"], location + "/input")
        for index, entry in enumerate(_array(item["entries"], location + "/entries", maximum=8)):
            here = f"{location}/entries/{index}"
            if not isinstance(entry, list) or len(entry) != 2:
                _raise("scene_shape", here, "state-map entry must be a pair")
            _identifier(entry[0], here + "/0")
            _identifier(entry[1], here + "/1")
    elif kind == "piecewise":
        item = _closed_object(value, {"kind", "input", "output", "segments"}, set(), location)
        _identifier(item["input"], location + "/input")
        _registry_id(item["output"], location + "/output")
        segments = _array(item["segments"], location + "/segments", maximum=16)
        if not segments:
            _raise("scene_shape", location + "/segments", "piecewise model requires segments")
        for index, segment in enumerate(segments):
            here = f"{location}/segments/{index}"
            if not isinstance(segment, dict):
                _raise("scene_shape", here, "expected compiled segment")
            segment_kind = segment.get("kind")
            if segment_kind == "linear":
                row = _closed_object(segment, {"kind", "min", "max", "slope", "intercept"}, set(), here)
                slope = _closed_object(row["slope"], {"value", "inputQuantity", "outputQuantity"}, set(), here + "/slope")
                _validate_typed_value(slope["value"], here + "/slope/value")
                _identifier(slope["inputQuantity"], here + "/slope/inputQuantity")
                _identifier(slope["outputQuantity"], here + "/slope/outputQuantity")
                _validate_typed_value(row["intercept"], here + "/intercept")
            elif segment_kind == "endpoints":
                row = _closed_object(segment, {"kind", "min", "max", "start", "end"}, set(), here)
                _validate_typed_value(row["start"], here + "/start")
                _validate_typed_value(row["end"], here + "/end")
            else:
                _raise("scene_shape", here + "/kind", "unsupported piecewise segment")
            _validate_typed_value(row["min"], here + "/min")
            _validate_typed_value(row["max"], here + "/max")
    elif kind == "score_sum":
        item = _closed_object(value, {"kind", "quantity", "contributions", "bands"}, set(), location)
        _identifier(item["quantity"], location + "/quantity")
        contributions = _array(item["contributions"], location + "/contributions", maximum=8)
        for index, contribution in enumerate(contributions):
            here = f"{location}/contributions/{index}"
            if not isinstance(contribution, list) or len(contribution) != 2:
                _raise("scene_shape", here, "score contribution must be a pair")
            _identifier(contribution[0], here + "/0")
            for option_index, option in enumerate(_array(contribution[1], here + "/1", maximum=10_001)):
                option_here = f"{here}/1/{option_index}"
                if not isinstance(option, list) or len(option) != 2:
                    _raise("scene_shape", option_here, "score option must be a pair")
                if not isinstance(option[0], str) or len(option[0]) > 128:
                    _raise("scene_shape", option_here + "/0", "invalid score selector")
                _validate_typed_value(option[1], option_here + "/1")
        bands = _array(item["bands"], location + "/bands", maximum=8)
        if not bands:
            _raise("scene_shape", location + "/bands", "score model requires bands")
        for index, band in enumerate(bands):
            here = f"{location}/bands/{index}"
            row = _closed_object(band, {"id", "label", "min", "max"}, set(), here)
            _identifier(row["id"], here + "/id")
            _text(row["label"], here + "/label", 40, empty=False)
            _validate_typed_value(row["min"], here + "/min")
            _validate_typed_value(row["max"], here + "/max")
    elif kind == "operation_graph":
        item = _closed_object(value, {"kind", "nodes", "outputs"}, set(), location)
        graph_shapes = {
            "input": {"id", "op", "quantity", "control"},
            "constant": {"id", "op", "quantity", "constant"},
            "add": {"id", "op", "quantity", "left", "right"},
            "subtract": {"id", "op", "quantity", "left", "right"},
            "multiply": {"id", "op", "quantity", "left", "right"},
            "divide": {"id", "op", "quantity", "left", "right"},
            "min": {"id", "op", "quantity", "inputs"},
            "max": {"id", "op", "quantity", "inputs"},
            "abs": {"id", "op", "quantity", "input"},
            "clamp": {"id", "op", "quantity", "input", "min", "max"},
        }
        node_ids: list[str] = []
        for index, node in enumerate(_array(item["nodes"], location + "/nodes", maximum=32)):
            here = f"{location}/nodes/{index}"
            if not isinstance(node, dict) or node.get("op") not in graph_shapes:
                _raise("scene_shape", here + "/op", "unsupported operation graph node")
            row = _closed_object(node, graph_shapes[node["op"]], set(), here)
            node_id = _identifier(row["id"], here + "/id")
            if node_id in node_ids:
                _raise("duplicate_id", here + "/id", "duplicate graph node")
            node_ids.append(node_id)
            _identifier(row["quantity"], here + "/quantity")
            if row["op"] == "constant":
                _validate_typed_value(row["constant"], here + "/constant")
            elif row["op"] == "input":
                _identifier(row["control"], here + "/control")
            else:
                references = row["inputs"] if row["op"] in ("min", "max") else [row[key] for key in graph_shapes[row["op"]] - {"id", "op", "quantity"}]
                if not isinstance(references, list):
                    references = list(references)
                for reference in references:
                    if _identifier(reference, here + "/reference") not in node_ids[:-1]:
                        _raise("scene_reference", here, "graph operands must reference earlier nodes")
        outputs = item["outputs"]
        if not isinstance(outputs, dict) or not 1 <= len(outputs) <= 4:
            _raise("scene_shape", location + "/outputs", "invalid graph output registry")
        for output_id, node_id in outputs.items():
            _registry_id(output_id, location + "/outputs/" + str(output_id))
            if _identifier(node_id, location + "/outputs/" + str(output_id)) not in node_ids:
                _raise("scene_reference", location + "/outputs/" + str(output_id), "graph output node is missing")
    else:
        _raise("scene_shape", location + "/kind", "unsupported compiled model kind")
    return str(kind)


def _validate_task5_decision(value: object, location: str) -> None:
    item = _closed_object(
        value,
        {"id", "metric", "operator", "threshold", "whenMet", "whenNotMet"},
        set(),
        location,
    )
    _identifier(item["id"], location + "/id")
    _validate_typed_value(item["metric"], location + "/metric", allow_reference=True)
    if item["operator"] not in ("gte", "gt", "lte", "lt"):
        _raise("scene_shape", location + "/operator", "unsupported decision operator")
    threshold = _closed_object(item["threshold"], {"value", "quantity", "provenance"}, set(), location + "/threshold")
    _decimal_text(threshold["value"], location + "/threshold/value")
    _identifier(threshold["quantity"], location + "/threshold/quantity")
    _validate_provenance(threshold["provenance"], location + "/threshold/provenance")
    for key in ("whenMet", "whenNotMet"):
        record = _closed_object(item[key], {"status", "recommendation"}, set(), location + "/" + key)
        _text(record["status"], location + "/" + key + "/status", 32, empty=False)
        _text(record["recommendation"], location + "/" + key + "/recommendation", 500, empty=False)


def _validate_task5_steps(
    value: object,
    location: str,
    targets: dict,
    *,
    initial_panel: object = _NO_DEMO_PANEL,
    panel_can_close: bool = True,
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    step_keys: list[str] = []
    goto_ids: list[str] = []
    wait_ms = 0
    shapes = {
        "set": {"type", "control", "value"},
        "select": {"type", "control", "value"},
        "openEvidence": {"type"}, "closeEvidence": {"type"},
        "openPanel": {"type", "panel"}, "closePanel": {"type", "panel"},
        "goto": {"type", "slideId"}, "wait": {"type", "ms"},
    }
    steps = _array(value, location, maximum=80)
    for index, step in enumerate(steps):
        here = f"{location}/{index}"
        record = _closed_object(step, {"stepKey", "action"}, {"targetKey"}, here)
        step_key = _identifier(record["stepKey"], here + "/stepKey")
        if step_key in step_keys:
            _raise("duplicate_id", here + "/stepKey", "duplicate compiled step key")
        step_keys.append(step_key)
        action = record["action"]
        if not isinstance(action, dict) or action.get("type") not in shapes:
            _raise("scene_shape", here + "/action", "unsupported compiled action")
        action_type = action["type"]
        row = _closed_object(action, shapes[action_type], set(), here + "/action")
        expected_target = None
        if action_type in ("set", "select"):
            control_id = _identifier(row["control"], here + "/action/control")
            if action_type == "set":
                _decimal_text(row["value"], here + "/action/value")
            else:
                _identifier(row["value"], here + "/action/value")
            expected_target = "control:" + control_id
        elif action_type in ("openEvidence", "closeEvidence"):
            expected_target = "evidence:open" if action_type == "openEvidence" else "evidence:close"
        elif action_type in ("openPanel", "closePanel"):
            panel_id = _identifier(row["panel"], here + "/action/panel")
            expected_target = "panel:" + panel_id + (":close" if action_type == "closePanel" else "")
        elif action_type == "goto":
            goto_ids.append(_identifier(row["slideId"], here + "/action/slideId"))
        else:
            wait_ms += _integer(row["ms"], here + "/action/ms", 0, 5_000)
        if expected_target is None:
            if "targetKey" in record:
                _raise("scene_shape", here + "/targetKey", "goto/wait cannot have a target")
        elif record.get("targetKey") != expected_target or expected_target not in targets:
            _raise("scene_relation", here + "/targetKey", "compiled action target mismatch")
    if wait_ms > MAX_SCENE_WAIT_MS:
        _raise("aggregate_limit", location, "declared waits exceed 30 seconds for one scene")
    _validate_demo_reachability(
        steps,
        location,
        initial_panel=initial_panel,
        panel_can_close=panel_can_close,
    )
    return wait_ms, tuple(step_keys), tuple(goto_ids)


def _validate_task5_interactive_scene(
    scene: dict,
    slide_id: str,
    lang: str,
    location: str,
) -> tuple[int, int, int, int, tuple[str, ...], tuple[str, ...]]:
    scene_type = scene.get("type") if isinstance(scene, dict) else None
    if scene_type not in ("state_toggle", "slider_model", "score_model"):
        _raise("scene_shape", location + "/type", "unsupported interactive scene type")
    required = _SCENE_KEYS - {"states", "model", "reporting", "decisionContract", "view"}
    if scene_type == "state_toggle":
        required |= {"states", "model"}
        optional: set[str] = set()
    else:
        required |= {"model", "reporting", "decisionContract", "view"}
        optional = set()
    item = _closed_object(scene, required, optional, location)
    if _integer(item["version"], location + "/version", 1, 1) != 1:
        _raise("scene_shape", location + "/version", "expected scene version 1")
    if item["slideId"] != slide_id or item["locale"] != lang:
        _raise("scene_shape", location, "compiled scene identity does not match its slide")
    _integer(item["scale"], location + "/scale", 0, 6)
    for key in ("purpose", "interactionRationale"):
        _text(item[key], location + "/" + key, 500, empty=False)
    if item["decisionJob"] not in ("fact", "insight", "action", "decision"):
        _raise("scene_shape", location + "/decisionJob", "unexpected decision job")

    controls = _array(item["controls"], location + "/controls", maximum=8)
    control_ids: list[str] = []
    domains: dict[str, tuple[str, ...]] = {}
    accepted_states = 1
    for index, control in enumerate(controls):
        control_id, count, values = _validate_task5_control(control, f"{location}/controls/{index}")
        if control_id in control_ids:
            _raise("duplicate_id", f"{location}/controls/{index}/id", "duplicate compiled control")
        control_ids.append(control_id)
        domains[control_id] = values
        accepted_states *= count
    if accepted_states > MAX_ACCEPTED_STATES_PER_DECK:
        _raise("aggregate_limit", location + "/controls", "scene accepted states exceed deck budget")
    if scene_type == "state_toggle" and (
        len(controls) != 1 or controls[0].get("kind") not in ("segmented", "select")
    ):
        _raise("scene_shape", location + "/controls", "state toggle requires one segmented or select control")
    if scene_type == "slider_model" and (
        len(controls) != 1 or controls[0].get("kind") != "range"
    ):
        _raise("scene_shape", location + "/controls", "slider model requires one range control")
    if scene_type == "score_model" and not 2 <= len(controls) <= 8:
        _raise("scene_shape", location + "/controls", "score model requires two through eight controls")
    for state_key in ("initialState", "printState"):
        state = item[state_key]
        if not isinstance(state, dict) or set(state) != set(control_ids):
            _raise("scene_shape", location + "/" + state_key, "state keys must match declared controls")
        for control_id in control_ids:
            raw = state[control_id]
            if not isinstance(raw, str) or raw not in domains[control_id]:
                _raise("scene_relation", location + "/" + state_key + "/" + control_id, "state value is outside its control domain")
    if item["initialState"] != item["printState"]:
        _raise("scene_relation", location + "/printState", "print state must equal initial state")

    _validate_quantities(item["quantities"], location + "/quantities")
    _validate_output_definitions(item["outputDefinitions"], location + "/outputDefinitions")
    _validate_evidence(item["evidence"], location + "/evidence")
    _validate_invariant_chrome(item["invariants"], location + "/invariants")
    _validate_task5_fallback(item["fallback"], location + "/fallback")
    model_kind = _validate_task5_model(item["model"], location + "/model")
    _validate_task5_narration(item["narration"], location + "/narration", lang)

    initial = _closed_object(
        item["initialEvaluation"],
        {"outputs", "view"},
        set() if scene_type == "state_toggle" else {"decision"},
        location + "/initialEvaluation",
    )
    outputs = initial["outputs"]
    if not isinstance(outputs, dict) or set(outputs) != set(item["outputDefinitions"]):
        _raise("scene_shape", location + "/initialEvaluation/outputs", "evaluated outputs must match definitions")
    for output_id, output in outputs.items():
        _registry_id(output_id, location + "/initialEvaluation/outputs/" + output_id)
        _validate_typed_value(output, location + "/initialEvaluation/outputs/" + output_id)

    view_items = 0
    if scene_type == "state_toggle":
        if model_kind != "state_map" or outputs:
            _raise("scene_relation", location, "state toggle requires state_map and no output registry")
        state_rows = _array(item["states"], location + "/states", maximum=8)
        if not state_rows:
            _raise("scene_shape", location + "/states", "state toggle requires compiled states")
        state_ids: list[str] = []
        initial_component = None
        initial_ids: tuple[str, ...] = ()
        for index, state_row in enumerate(state_rows):
            here = f"{location}/states/{index}"
            row = _closed_object(state_row, {"id", "lineage", "view"}, set(), here)
            state_id = _identifier(row["id"], here + "/id")
            if state_id in state_ids:
                _raise("duplicate_id", here + "/id", "duplicate compiled state")
            state_ids.append(state_id)
            _validate_lineage(row["lineage"], here + "/lineage")
            component, identifiers = _validate_task5_view(row["view"], here + "/view", resolved=True)
            if component not in ("bar_compare", "ranked_list", "dot_plot"):
                _raise("scene_shape", here + "/view/component", "unsupported state-toggle view")
            view_items += len(identifiers)
            if row["id"] == item["initialState"][control_ids[0]]:
                initial_component, initial_ids = component, identifiers
                if initial["view"] != row["view"]:
                    _raise("scene_relation", location + "/initialEvaluation/view", "selected state view must be reused exactly")
        component, identifiers = _validate_task5_view(initial["view"], location + "/initialEvaluation/view", resolved=True)
        if (component, identifiers) != (initial_component, initial_ids):
            _raise("scene_relation", location + "/initialEvaluation/view", "initial state view does not match selected state")
        view_items += len(identifiers)
    else:
        expected_models = {
            "slider_model": {"linear", "lookup", "piecewise", "operation_graph"},
            "score_model": {"score_sum"},
        }[scene_type]
        if model_kind not in expected_models:
            _raise("scene_shape", location + "/model/kind", "model kind is not allowed for this scene")
        component, authored_ids = _validate_task5_view(item["view"], location + "/view", resolved=False)
        resolved_component, resolved_ids = _validate_task5_view(initial["view"], location + "/initialEvaluation/view", resolved=True)
        if component != resolved_component or authored_ids != resolved_ids:
            _raise("scene_relation", location + "/initialEvaluation/view", "resolved view does not match authored view")
        if scene_type == "slider_model" and component not in ("bar_compare", "dot_plot"):
            _raise("scene_shape", location + "/view/component", "slider view must be bar or dot")
        if scene_type == "score_model" and component != "recommendation_panel":
            _raise("scene_shape", location + "/view/component", "score view must be recommendation panel")
        view_items += len(authored_ids) + len(resolved_ids)
        reporting = _closed_object(item["reporting"], {"primaryOutput", "secondaryOutputs"}, set(), location + "/reporting")
        reporting_ids = [_registry_id(reporting["primaryOutput"], location + "/reporting/primaryOutput")]
        for index, output_id in enumerate(_array(reporting["secondaryOutputs"], location + "/reporting/secondaryOutputs", maximum=3)):
            reporting_ids.append(_registry_id(output_id, f"{location}/reporting/secondaryOutputs/{index}"))
        if len(reporting_ids) != len(set(reporting_ids)) or not set(reporting_ids) <= set(outputs):
            _raise("scene_reference", location + "/reporting", "reporting outputs are not registered")
        _validate_task5_decision(item["decisionContract"], location + "/decisionContract")
        decision = _closed_object(
            initial.get("decision"),
            {"outcome", "distance", "quantity", "status", "recommendation", "lineage"},
            set(),
            location + "/initialEvaluation/decision",
        )
        if decision["outcome"] not in ("met", "notMet"):
            _raise("scene_shape", location + "/initialEvaluation/decision/outcome", "unexpected decision outcome")
        _decimal_text(decision["distance"], location + "/initialEvaluation/decision/distance")
        _identifier(decision["quantity"], location + "/initialEvaluation/decision/quantity")
        _text(decision["status"], location + "/initialEvaluation/decision/status", 32, empty=False)
        _text(decision["recommendation"], location + "/initialEvaluation/decision/recommendation", 500, empty=False)
        _validate_lineage(decision["lineage"], location + "/initialEvaluation/decision/lineage")

    expected_targets = {
        "evidence:open": {"kind": "evidence"},
        "evidence:close": {"kind": "evidence"},
        "static:toggle": {"kind": "static"},
    }
    expected_targets.update({
        "control:" + control_id: {"kind": "control", "id": control_id}
        for control_id in control_ids
    })
    for source in item["evidence"]["sources"]:
        if source["linked"]:
            expected_targets["source:" + source["id"]] = {"kind": "source", "id": source["id"]}
    if item["targets"] != expected_targets:
        _raise("scene_relation", location + "/targets", "target registry does not match compiled scene")
    wait_ms, step_keys, goto_ids = _validate_task5_steps(
        item["steps"], location + "/steps", item["targets"]
    )
    program = item["narration"]["program"]
    if program.get("kind") in ("numeric_delta_v1", "state_delta_v1"):
        expected_variants = accepted_states * 2 * (1 + len(program.get("controls", [])))
        if item["narration"]["validatedVariants"] != expected_variants:
            _raise("scene_relation", location + "/narration/validatedVariants", "narration validation work does not match accepted states")
    return view_items, len(item["targets"]), len(item["steps"]), wait_ms, step_keys, goto_ids


def _validate_panel_scene(
    scene: dict,
    slide_id: str,
    lang: str,
    location: str,
) -> tuple[int, int, int, int, tuple[str, ...], tuple[str, ...]]:
    required = (_SCENE_KEYS - {"model", "reporting", "decisionContract", "view"}) | {"states"}
    item = _closed_object(scene, required, set(), location)
    if item["type"] not in ("drilldown", "accordion") or item["slideId"] != slide_id or item["locale"] != lang:
        _raise("scene_shape", location, "compiled panel scene identity mismatch")
    _integer(item["version"], location + "/version", 1, 1)
    _integer(item["scale"], location + "/scale", 0, 6)
    for key in ("purpose", "interactionRationale"):
        _text(item[key], location + "/" + key, 500, empty=False)
    if item["controls"] != [] or item["quantities"] != {} or item["outputDefinitions"] != {}:
        _raise("scene_shape", location, "panel scenes cannot carry controls, quantities or outputs")
    _validate_evidence(item["evidence"], location + "/evidence")
    _validate_invariant_chrome(item["invariants"], location + "/invariants")
    _validate_task5_fallback(item["fallback"], location + "/fallback")
    initial = _closed_object(item["initialEvaluation"], {"outputs", "view"}, set(), location + "/initialEvaluation")
    if initial != {"outputs": {}, "view": None}:
        _raise("scene_shape", location + "/initialEvaluation", "panel evaluation must be empty")
    state_required = {"panels", "parentSummary", "returnLabel"} if item["type"] == "drilldown" else {"panels", "allowNone"}
    states = _closed_object(item["states"], state_required, set(), location + "/states")
    panels = _array(states["panels"], location + "/states/panels", maximum=6)
    if not panels:
        _raise("scene_shape", location + "/states/panels", "panel scene requires panels")
    panel_ids: list[str] = []
    for index, panel in enumerate(panels):
        here = f"{location}/states/panels/{index}"
        row = _closed_object(panel, {"id", "label", "heading", "body", "sourceRefs"}, set(), here)
        panel_id = _identifier(row["id"], here + "/id")
        if panel_id in panel_ids:
            _raise("duplicate_id", here + "/id", "duplicate compiled panel")
        panel_ids.append(panel_id)
        _text(row["label"], here + "/label", 64, empty=False)
        _text(row["heading"], here + "/heading", 500, empty=False)
        _text(row["body"], here + "/body", 2_000, empty=False)
        _text_array(row["sourceRefs"], here + "/sourceRefs", maximum=20)
    if item["type"] == "drilldown":
        _text(states["parentSummary"], location + "/states/parentSummary", 2_000, empty=False)
        _text(states["returnLabel"], location + "/states/returnLabel", 500, empty=False)
    else:
        _boolean(states["allowNone"], location + "/states/allowNone")
    for state_key in ("initialState", "printState"):
        state = _closed_object(item[state_key], {"panel"}, set(), location + "/" + state_key)
        if state["panel"] is None and item["type"] == "accordion" and not states["allowNone"]:
            _raise("scene_relation", location + "/" + state_key + "/panel", "null panel is not allowed by this accordion")
        if state["panel"] is not None and state["panel"] not in panel_ids:
            _raise("scene_reference", location + "/" + state_key + "/panel", "unknown compiled panel")
    if item["initialState"] != item["printState"]:
        _raise("scene_relation", location + "/printState", "print state must equal initial state")
    _validate_disclosure_narration(item["narration"], location + "/narration", lang, panels=tuple(panel_ids))
    expected_targets = {
        "evidence:open": {"kind": "evidence"},
        "evidence:close": {"kind": "evidence"},
        "static:toggle": {"kind": "static"},
    }
    for panel_id in panel_ids:
        expected_targets["panel:" + panel_id] = {"kind": "panel", "id": panel_id}
        expected_targets["panel:" + panel_id + ":close"] = {"kind": "panelClose", "id": panel_id}
    for source in item["evidence"]["sources"]:
        if source["linked"]:
            expected_targets["source:" + source["id"]] = {"kind": "source", "id": source["id"]}
    if item["targets"] != expected_targets:
        _raise("scene_relation", location + "/targets", "target registry does not match panel scene")
    wait_ms, step_keys, goto_ids = _validate_task5_steps(
        item["steps"],
        location + "/steps",
        item["targets"],
        initial_panel=item["initialState"]["panel"],
        panel_can_close=item["type"] != "accordion" or states["allowNone"],
    )
    return 0, len(item["targets"]), len(item["steps"]), wait_ms, step_keys, goto_ids


def _validate_scene(
    scene: dict,
    slide_id: str,
    lang: str,
    location: str,
) -> tuple[int, int, int, int, tuple[str, ...], tuple[str, ...]]:
    if isinstance(scene, dict) and scene.get("type") == "evidence_only":
        return _validate_disclosure_scene(scene, slide_id, lang, location)
    if isinstance(scene, dict) and scene.get("type") in ("drilldown", "accordion"):
        return _validate_panel_scene(scene, slide_id, lang, location)
    if (
        isinstance(scene, dict)
        and scene.get("type") == "slider_model"
        and isinstance(scene.get("model"), dict)
        and scene["model"].get("kind") == "linear"
        and isinstance(scene.get("view"), dict)
        and scene["view"].get("component") == "dot_plot"
    ):
        return _validate_task4_scene(scene, slide_id, lang, location)
    return _validate_task5_interactive_scene(scene, slide_id, lang, location)


def _compiled_scene_state_count(scene: object, location: str) -> int:
    if not isinstance(scene, dict):
        _raise("scene_shape", location, "compiled scene must be an object")
    scene_type = scene.get("type")
    if scene_type == "evidence_only":
        evidence = scene.get("evidence")
        if not isinstance(evidence, dict):
            _raise("scene_shape", location + "/evidence", "expected compiled evidence")
        count = 1 + int(bool(evidence.get("sources"))) + int(bool(evidence.get("assumptions")))
        if evidence.get("sources") and evidence.get("assumptions"):
            count += 1
        return count
    if scene_type in ("drilldown", "accordion"):
        states = scene.get("states")
        if not isinstance(states, dict) or not isinstance(states.get("panels"), list):
            _raise("scene_shape", location + "/states", "expected compiled panel states")
        panel_count = len(states["panels"])
        if scene_type == "drilldown":
            return panel_count + 1
        allow_none = states.get("allowNone")
        if type(allow_none) is not bool:
            _raise("scene_shape", location + "/states/allowNone", "expected accordion allowNone flag")
        return panel_count + int(allow_none)
    if (
        scene_type == "slider_model"
        and isinstance(scene.get("model"), dict)
        and scene["model"].get("kind") == "linear"
        and isinstance(scene.get("view"), dict)
        and scene["view"].get("component") == "dot_plot"
    ):
        return _compiled_task4_scene_state_count(scene, location)
    controls = scene.get("controls")
    if not isinstance(controls, list) or not controls:
        _raise("scene_shape", location + "/controls", "interactive scene requires controls")
    accepted_states = 1
    for index, control in enumerate(controls):
        _control_id, count, _values = _validate_task5_control(
            control, f"{location}/controls/{index}"
        )
        accepted_states *= count
        if accepted_states > MAX_ACCEPTED_STATES_PER_DECK:
            _raise("aggregate_limit", location + "/controls", "scene accepted states exceed deck budget")
    narration = scene.get("narration")
    if not isinstance(narration, dict):
        _raise("scene_shape", location + "/narration", "compiled narration must be an object")
    program = narration.get("program")
    if not isinstance(program, dict) or not isinstance(program.get("controls"), list):
        _raise("scene_shape", location + "/narration/program", "compiled narration program is invalid")
    expected_variants = accepted_states * 2 * (1 + len(program["controls"]))
    if narration.get("validatedVariants") != expected_variants:
        _raise(
            "scene_relation",
            location + "/narration/validatedVariants",
            "compiled narration work does not match accepted states",
        )
    return accepted_states


def _validate_envelope(payload: object) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"version", "kind", "lang", "locale", "slides"}:
        _raise("envelope_shape", "<envelope>", "expected version, kind, lang, locale and slides")
    # Validate the JSON value domain before any shape-specific access.  This
    # keeps Python-only values (tuples, floats, custom mappings) from reaching
    # the browser-facing contract even when a later field check would happen
    # to accept them.
    _walk_json(payload)
    if _integer(payload["version"], "<envelope>/version", 1, 1) != 1 or payload["kind"] != "interactive-deck":
        _raise("envelope_version", "<envelope>", "expected interactive-deck version 1")
    locales = {"en": "en-US", "ja": "ja-JP"}
    lang = payload["lang"]
    if not isinstance(lang, str) or lang not in locales or payload["locale"] != locales[lang]:
        _raise("envelope_locale", "<envelope>", "language and BCP47 locale do not agree")
    slides = payload["slides"]
    if not isinstance(slides, list) or not 1 <= len(slides) <= MAX_SLIDES:
        _raise("slide_limit", "<envelope>/slides", f"expected 1 through {MAX_SLIDES} slides")
    accepted_states = 0
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict) or set(slide) != {"slideId", "scene", "display"}:
            continue
        if slide["scene"] is None:
            continue
        accepted_states += _compiled_scene_state_count(
            slide["scene"],
            f"<envelope>/slides/{index}/scene",
        )
        if accepted_states > MAX_ACCEPTED_STATES_PER_DECK:
            _raise("aggregate_limit", "<envelope>/slides", "accepted states exceed the deck budget")
    seen: set[str] = set()
    goto_references: list[tuple[str, str]] = []
    view_items = targets = steps = wait_ms = 0
    for index, slide in enumerate(slides):
        location = f"<envelope>/slides/{index}"
        if not isinstance(slide, dict) or set(slide) != {"slideId", "scene", "display"}:
            _raise("envelope_shape", location, "expected slideId, scene and display")
        slide_id = _identifier(slide["slideId"], location + "/slideId")
        if slide_id in seen:
            _raise("duplicate_id", location + "/slideId", "duplicate slide ID")
        seen.add(slide_id)
        scene = slide["scene"]
        display = _validate_display(slide["display"], location + "/display")
        if scene is None:
            if display is not None:
                _raise(
                    "display_shape",
                    location + "/display",
                    "static envelope slides must not carry a live display bridge",
                )
            continue
        if display is None:
            _raise("display_shape", location + "/display", "scene slides require the closed display bridge")
        scene_view_items, scene_targets, scene_steps, scene_wait_ms, _step_keys, goto_ids = _validate_scene(
            scene, slide_id, payload["lang"], location + "/scene"
        )
        view_items += scene_view_items
        targets += scene_targets
        steps += scene_steps
        wait_ms += scene_wait_ms
        _validate_scene_summary(
            scene,
            display["staticSummary"],
            display,
            location + "/display/staticSummary",
        )
        goto_references.extend((location + "/scene/steps", goto_id) for goto_id in goto_ids)
    for location, goto_id in goto_references:
        if goto_id not in seen:
            _raise("scene_shape", location, "goto slide ID is not present in this deck")
    if view_items > MAX_VIEW_ITEMS:
        _raise("aggregate_limit", "<envelope>/slides", f"view items exceed {MAX_VIEW_ITEMS}")
    if targets > MAX_TARGETS:
        _raise("aggregate_limit", "<envelope>/slides", f"targets exceed {MAX_TARGETS}")
    if steps > MAX_STEPS:
        _raise("aggregate_limit", "<envelope>/slides", f"steps exceed {MAX_STEPS}")
    wait_ms += DEFAULT_DEMO_PAGE_PAUSE_MS * len(slides)
    if wait_ms > MAX_DECK_WAIT_MS:
        _raise("aggregate_limit", "<envelope>/slides", "demo waits exceed the 10 minute deck budget")
    return payload


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8", "strict")


def _encode_validated_envelope(payload: dict) -> tuple[bytes, str]:
    raw = _canonical_json(payload)
    if len(raw) > MAX_ENVELOPE_BYTES:
        _raise("envelope_limit", "<envelope>", "decoded envelope exceeds 16 MiB")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return raw, encoded


def encode_envelope(payload: dict) -> str:
    _validate_envelope(payload)
    return _encode_validated_envelope(payload)[1]


class _DuplicateJsonKey(ValueError):
    def __init__(self, key: str):
        self.key = key


def decode_envelope(encoded: str) -> dict:
    if not isinstance(encoded, str) or not encoded:
        _raise("envelope_encoding", "<envelope>", "expected unpadded base64url alphabet")
    if len(encoded) % 4 == 1 or len(encoded) > math.ceil(4 * MAX_ENVELOPE_BYTES / 3):
        _raise("envelope_encoding", "<envelope>", "impossible or oversized base64url length")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        _raise("envelope_encoding", "<envelope>", "expected unpadded base64url alphabet")
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, base64.binascii.Error):
        _raise("envelope_encoding", "<envelope>", "invalid base64url payload")
    if len(raw) > MAX_ENVELOPE_BYTES:
        _raise("envelope_limit", "<envelope>", "decoded envelope exceeds 16 MiB")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeDecodeError:
        _raise("envelope_utf8", "<envelope>", "payload must be strict UTF-8")
    _EnvelopeJsonPreflight(text).run()

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise _DuplicateJsonKey(key)
            result[key] = value
        return result

    try:
        payload = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except _DuplicateJsonKey as error:
        _raise("duplicate_json_key", "<envelope>", "duplicate JSON key")
    except (json.JSONDecodeError, ValueError, RecursionError):
        _raise("envelope_json", "<envelope>", "invalid bounded JSON")
    _validate_envelope(payload)
    canonical_raw, canonical_encoded = _encode_validated_envelope(payload)
    if canonical_raw != raw or canonical_encoded != encoded:
        _raise("envelope_encoding", "<envelope>", "payload is not in canonical encoding")
    return payload


_STATIC_TAGS = frozenset(("svg", "rect", "text", "title", "line", "polyline", "circle", "path"))
_LIVE_TAGS = _STATIC_TAGS | frozenset(("g", "defs", "clipPath"))
_ATTRS = {
    "svg": frozenset(("viewBox", "width", "height", "role", "aria-label", "aria-hidden", "focusable", "id")),
    "rect": frozenset(("x", "y", "width", "height", "fill", "stroke", "stroke-width", "opacity", "id", "clip-path")),
    "text": frozenset(("x", "y", "fill", "font-family", "font-size", "font-weight", "text-anchor", "opacity", "id", "clip-path", "data-label-width")),
    "title": frozenset(),
    "line": frozenset(("x1", "x2", "y1", "y2", "stroke", "stroke-width", "stroke-dasharray", "opacity", "id", "clip-path")),
    "polyline": frozenset(("points", "fill", "stroke", "stroke-width", "opacity", "id", "clip-path")),
    "circle": frozenset(("cx", "cy", "r", "fill", "stroke", "stroke-width", "opacity", "id", "clip-path")),
    "path": frozenset(("d", "fill", "stroke", "stroke-width", "opacity", "id", "clip-path")),
    "g": frozenset(("id", "clip-path", "opacity")),
    "defs": frozenset(("id",)),
    "clipPath": frozenset(("id",)),
}
_NUMERIC_ATTRS = frozenset(("x", "y", "width", "height", "x1", "x2", "y1", "y2", "cx", "cy", "r", "stroke-width", "font-size", "opacity", "data-label-width"))


def _local_tag(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        namespace, _, name = tag[1:].partition("}")
        return namespace, name
    return None, tag


def _bounded_svg_number(value: str, location: str) -> float:
    if not _NUMBER.fullmatch(value):
        _raise("svg_attribute", location, "expected a finite renderer decimal")
    try:
        number = float(value)
    except ValueError:
        number = math.inf
    if not math.isfinite(number) or abs(number) > 1_000_000:
        _raise("svg_attribute", location, "renderer decimal is outside the numeric bound")
    return number


def _svg_integrity(
    serialized: str,
    ids: tuple[str, ...],
    element_count: int,
    slide_ordinal: int,
    role: str,
) -> bytes:
    digest = hashlib.sha256()
    digest.update(serialized.encode("utf-8", "strict"))
    digest.update(b"\0")
    for identifier in ids:
        digest.update(identifier.encode("ascii", "strict"))
        digest.update(b"\0")
    digest.update(str(element_count).encode("ascii"))
    digest.update(b"\0")
    digest.update(str(slide_ordinal).encode("ascii"))
    digest.update(b"\0")
    digest.update(role.encode("ascii"))
    return digest.digest()


def _validated_svg_intact(
    value: object,
    *,
    slide_ordinal: int | None = None,
    role: str | None = None,
) -> bool:
    if (
        not isinstance(value, ValidatedSvg)
        or value._seal is not _VALIDATED_SVG_SEAL
        or not isinstance(value.serialized, str)
        or not isinstance(value.ids, tuple)
        or not all(isinstance(identifier, str) for identifier in value.ids)
        or isinstance(value.element_count, bool)
        or not isinstance(value.element_count, int)
        or value.element_count < 1
        or isinstance(value._slide_ordinal, bool)
        or not isinstance(value._slide_ordinal, int)
        or value._slide_ordinal < 1
        or value._role not in ("fallback", "live-shell")
        or (slide_ordinal is not None and value._slide_ordinal != slide_ordinal)
        or (role is not None and value._role != role)
    ):
        return False
    try:
        return value._integrity == _svg_integrity(
            value.serialized,
            value.ids,
            value.element_count,
            value._slide_ordinal,
            value._role,
        )
    except (UnicodeError, ValueError):
        return False


def _bounded_svg_number_list(
    value: str,
    location: str,
    *,
    even: bool = False,
    nonnegative: bool = False,
) -> None:
    parts = [part for part in re.split(r"[\s,]+", value.strip()) if part]
    if not parts or (even and len(parts) % 2):
        _raise("svg_attribute", location, "invalid renderer numeric list")
    for part in parts:
        number = _bounded_svg_number(part, location)
        if nonnegative and number < 0:
            _raise("svg_attribute", location, "renderer numeric list must be nonnegative")


def _validate_svg_attribute(tag: str, name: str, value: str, location: str) -> None:
    if name.startswith("on") or name == "style" or name not in _ATTRS[tag]:
        _raise("svg_attribute", location, f"attribute {name!r} is not allowed on {tag}")
    if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
        _raise("svg_attribute", location, "control character in SVG attribute")
    if name in _NUMERIC_ATTRS:
        number = _bounded_svg_number(value, location)
        if name in ("width", "height", "r", "stroke-width", "font-size") and number < 0:
            _raise("svg_attribute", location, "renderer size must be nonnegative")
        if name == "opacity" and not 0 <= number <= 1:
            _raise("svg_attribute", location, "renderer opacity must be between zero and one")
    elif name in ("fill", "stroke") and not _COLOR.fullmatch(value):
        _raise("svg_attribute", location, f"{name} must be a renderer color")
    elif name == "viewBox":
        parts = value.split()
        if len(parts) != 4:
            _raise("svg_attribute", location, "viewBox must contain four finite decimals")
        for part in parts:
            _bounded_svg_number(part, location)
    elif name == "font-family" and value not in _FONT_FAMILIES:
        _raise("svg_attribute", location, "font-family must be a renderer font stack")
    elif name == "font-weight" and value not in ("normal", "600", "bold"):
        _raise("svg_attribute", location, "font-weight must be a renderer weight")
    elif name == "text-anchor" and value not in ("start", "middle", "end"):
        _raise("svg_attribute", location, "text-anchor must be start, middle or end")
    elif name == "points":
        if len(value) > 8_192 or not _POINTS.fullmatch(value):
            _raise("svg_attribute", location, "invalid polyline points")
        _bounded_svg_number_list(value, location, even=True)
    elif name == "d":
        if len(value) > 8_192 or not _PATH.fullmatch(value):
            _raise("svg_attribute", location, "invalid path data")
        numbers = re.findall(_NUMBER_TOKEN, value)
        residual = re.sub(_NUMBER_TOKEN, "", value)
        if not numbers or re.sub(r"[MmLlHhVvCcSsQqTtAaZz,\s]", "", residual):
            _raise("svg_attribute", location, "invalid path data")
        for number in numbers:
            _bounded_svg_number(number, location)
    elif name == "stroke-dasharray":
        if len(value) > 1_024 or not re.fullmatch(r"[0-9+., eE-]+", value):
            _raise("svg_attribute", location, "invalid dash array")
        _bounded_svg_number_list(value, location, nonnegative=True)
    elif name == "id" and not _SVG_ID.fullmatch(value):
        _raise("svg_id", location, "invalid renderer SVG ID")
    elif name == "clip-path" and not re.fullmatch(r"url\(#[A-Za-z][A-Za-z0-9_-]{0,63}\)", value):
        _raise("svg_reference", location, "clip-path must be a same-tree fragment")


def validate_renderer_svg(raw: str, *, slide_ordinal: int, role: str) -> ValidatedSvg:
    if (
        role not in ("fallback", "live-shell")
        or isinstance(slide_ordinal, bool)
        or not isinstance(slide_ordinal, int)
        or slide_ordinal < 1
    ):
        _raise("svg_role", "<svg>", "invalid renderer SVG role or ordinal")
    if not isinstance(raw, str) or not raw.strip():
        _raise("svg_xml", "<svg>", "expected renderer SVG text")
    try:
        raw_size = len(raw.encode("utf-8", "strict"))
    except UnicodeError:
        _raise("svg_xml", "<svg>", "expected strict UTF-8 renderer SVG text")
    if raw_size > MAX_RAW_SVG_BYTES:
        _raise("svg_limit", "<svg>", "renderer SVG exceeds the raw byte limit")
    lowered = raw.lower()
    if any(token in lowered for token in ("<!doctype", "<?", "<!entity", "<![cdata[", "<!--")):
        _raise("svg_xml", "<svg>", "declarations, processing instructions and comments are forbidden")
    # Reject every prefixed namespace declaration before ElementTree can drop
    # an unused declaration during serialization.  The prefix may be any XML
    # name, including non-ASCII names, so do not constrain this check to an
    # ASCII approximation of the grammar.
    if re.search(r"(?i)\sxmlns\s*:", raw):
        _raise("svg_namespace", "<svg>", "non-SVG namespace declarations are forbidden")
    # With declarations/comments/CDATA forbidden, every literal '<' starts
    # an element or closes one.  Bound start tags before ElementTree can
    # materialize an attacker-sized tree or any list/parent-map derivative.
    start_tag_upper_bound = raw.count("<") - raw.count("</")
    if start_tag_upper_bound > MAX_SVG_ELEMENTS_BY_ROLE[role]:
        _raise("svg_limit", "<svg>", "renderer SVG exceeds the role element limit")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        _raise("svg_xml", "<svg>", "expected one well-formed XML SVG tree")
    namespace, root_name = _local_tag(root.tag)
    if namespace != SVG_NS or root_name != "svg":
        _raise("svg_xml", "<svg>", "root must be an SVG-namespace svg element")
    if (
        root.attrib.get("viewBox") != "0 0 1280 720"
        or root.attrib.get("width") != "1280"
        or root.attrib.get("height") != "720"
    ):
        _raise("svg_attribute", "<svg>", "renderer root geometry must be exactly 1280 by 720")
    depth_stack = [(root, 1)]
    while depth_stack:
        element, depth = depth_stack.pop()
        if depth > MAX_SVG_DEPTH:
            _raise("svg_limit", "<svg>", "renderer SVG exceeds the nesting-depth limit")
        depth_stack.extend((child, depth + 1) for child in element)
    allowed_tags = _STATIC_TAGS if role == "fallback" else _LIVE_TAGS
    original_ids: dict[str, str] = {}
    elements = list(root.iter())
    if len(elements) > MAX_SVG_ELEMENTS_BY_ROLE[role]:
        _raise("svg_limit", "<svg>", "renderer SVG exceeds the role element limit")
    if not any(
        _local_tag(element.tag)[1] in ("rect", "text", "line", "polyline", "circle", "path")
        for element in elements[1:]
    ):
        _raise("svg_tag", "<svg>", "renderer SVG must contain visible geometry or text")
    parents = {child: parent for parent in elements for child in parent}
    for index, element in enumerate(elements):
        namespace, tag = _local_tag(element.tag)
        if namespace != SVG_NS or tag not in allowed_tags:
            _raise("svg_tag", f"<svg>/{index}", f"element {tag!r} is not allowed for {role}")
        if index and tag == "svg":
            _raise("svg_tag", f"<svg>/{index}", "nested SVG roots are forbidden")
        if tag == "title" and any(True for _ in element):
            _raise("svg_tag", f"<svg>/{index}", "title cannot contain elements")
        if tag not in ("text", "title") and (element.text or "").strip():
            _raise("svg_text", f"<svg>/{index}", f"text is not allowed in {tag}")
        if (element.tail or "").strip():
            parent = parents.get(element)
            parent_tag = _local_tag(parent.tag)[1] if parent is not None else None
            # The classic renderer emits <text><title>full label</title>visible
            # label</text> for accessible truncation.  That title tail is the
            # only legitimate mixed-content form in the renderer subset.
            if tag != "title" or parent_tag != "text":
                _raise("svg_text", f"<svg>/{index}", "tail text is not allowed in renderer SVG")
        for raw_name, value in element.attrib.items():
            attr_namespace, name = _local_tag(raw_name)
            if attr_namespace is not None:
                _raise("svg_namespace", f"<svg>/{index}", "namespaced SVG attributes are forbidden")
            _validate_svg_attribute(tag, name, value, f"<svg>/{index}/@{name}")
        if "id" in element.attrib:
            original = element.attrib["id"]
            if original in original_ids:
                _raise("duplicate_id", f"<svg>/{index}/@id", "duplicate SVG ID")
            original_ids[original] = f"idsvg-{slide_ordinal}-{role}-{original}"
    for index, element in enumerate(elements):
        if "id" in element.attrib:
            element.set("id", original_ids[element.attrib["id"]])
        if "clip-path" in element.attrib:
            original = element.attrib["clip-path"][5:-1]
            if original not in original_ids:
                _raise("svg_reference", f"<svg>/{index}/@clip-path", "unresolved same-tree SVG fragment")
            element.set("clip-path", f"url(#{original_ids[original]})")
    root.attrib.pop("role", None)
    root.attrib.pop("aria-label", None)
    root.set("aria-hidden", "true")
    root.set("focusable", "false")
    ET.register_namespace("", SVG_NS)
    serialized = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    ids = tuple(element.attrib["id"] for element in elements if "id" in element.attrib)
    validated = ValidatedSvg(
        serialized=serialized,
        ids=ids,
        element_count=len(elements),
    )
    object.__setattr__(validated, "_seal", _VALIDATED_SVG_SEAL)
    object.__setattr__(validated, "_slide_ordinal", slide_ordinal)
    object.__setattr__(validated, "_role", role)
    object.__setattr__(
        validated,
        "_integrity",
        _svg_integrity(serialized, ids, len(elements), slide_ordinal, role),
    )
    return validated


def _validate_asset_bytes(data: object, name: str, closing: bytes) -> str:
    if not isinstance(data, bytes) or data.startswith(b"\xef\xbb\xbf") or b"\r" in data:
        _raise("runtime_asset", name, "runtime asset must be UTF-8 bytes without BOM and with LF endings")
    try:
        text = data.decode("utf-8", "strict")
    except UnicodeDecodeError:
        _raise("runtime_asset", name, "runtime asset must be strict UTF-8")
    if closing.lower() in data.lower():
        _raise("runtime_asset", name, "runtime asset contains its raw-text closing tag")
    return text


def _strip_js_literals(source: str) -> str:
    output: list[str] = []
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        char = source[index]
        next_char = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char in ("'", '"'):
                state, quote = "string", char
                output.append(" ")
            elif char == "`":
                _raise("runtime_syntax", "interactive.js", "template literals are outside the fixed runtime subset")
            elif char == "/" and next_char == "/":
                state = "line-comment"
                output.extend((" ", " "))
                index += 1
            elif char == "/" and next_char == "*":
                state = "block-comment"
                output.extend((" ", " "))
                index += 1
            else:
                output.append(char)
        elif state == "string":
            output.append(" ")
            if char == "\\":
                if index + 1 < len(source):
                    output.append(" ")
                    index += 1
            elif char == quote:
                state = "code"
        elif state == "line-comment":
            output.append("\n" if char == "\n" else " ")
            if char == "\n":
                state = "code"
        else:
            output.append(" ")
            if char == "*" and next_char == "/":
                output.append(" ")
                index += 1
                state = "code"
        index += 1
    if state in ("string", "block-comment"):
        _raise("runtime_syntax", "interactive.js", "unterminated JavaScript token")
    return "".join(output)


def _asset_issues(assets: RuntimeAssets) -> tuple[BundleIssue, ...]:
    try:
        css = _validate_asset_bytes(assets.css, "interactive.css", b"</style")
        js = _validate_asset_bytes(assets.js, "interactive.js", b"</script")
    except BundleValidationError as error:
        return error.issues
    issues: list[BundleIssue] = []
    normalized_css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if "\\" in normalized_css or re.search(r"(?i)@import|url\s*\(|image-set\s*\(|@font-face", normalized_css):
        issues.append(BundleIssue("forbidden_css_capability", "interactive.css", "external CSS resource syntax is forbidden"))
    try:
        executable = _strip_js_literals(js)
    except BundleValidationError as error:
        issues.extend(error.issues)
        executable = ""
    forbidden = re.compile(
        r"\b(?:eval|Function|fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|Worker|SharedWorker|WebTransport|RTCPeerConnection|importScripts|postMessage|BroadcastChannel|MessageChannel|import)\b"
    )
    if forbidden.search(executable) or re.search(r"\bserviceWorker\b", executable):
        issues.append(BundleIssue("forbidden_runtime_capability", "interactive.js", "network, code-loading or cross-context capability is forbidden"))
    # The runtime needs arrays and bounded registry indexing.  Computed access
    # on capability-bearing globals remains outside the fixed subset.  Reject
    # Unicode-escaped executable tokens as well, so a dangerous member cannot
    # be hidden from the lexical checks with ``globalThis\u005b...``.
    if (
        re.search(r"\\u[0-9A-Fa-f]{4}|\\x[0-9A-Fa-f]{2}", executable)
        or re.search(
            r"\b(?:globalThis|window|document|location|history|navigator)\s*\[",
            executable,
        )
    ):
        issues.append(BundleIssue("forbidden_runtime_capability", "interactive.js", "computed access to browser capabilities is forbidden"))
    if re.search(r"\bcreateElement(?:NS)?\s*\(", executable):
        issues.append(BundleIssue("forbidden_runtime_capability", "interactive.js", "dynamic element construction is outside the Slice 0-4 runtime subset"))
    same_document_hash = re.compile(
        r"\bwindow\s*\.\s*location\s*\.\s*hash\s*=\s*target\b"
    )
    hash_updates = same_document_hash.findall(executable)
    trusted_same_document_hash = (
        len(hash_updates) == 1
        and re.search(
            r"\bvar\s+target\s*=\s*URL_STATE\s*\.\s*serialize\s*\(\s*state\s*,\s*deck\s*\)",
            executable,
        )
        and re.search(
            r"\bhistory\s*\.\s*replaceState\s*\(\s*null\s*,\s*[^,]+,\s*window\s*\.\s*location\s*\.\s*pathname\s*\+\s*window\s*\.\s*location\s*\.\s*search\s*\+\s*target\s*\)",
            executable,
        )
        and re.search(r"\bpendingHash\s*=\s*target\b", executable)
        and re.search(
            r"\bpendingHash\s*===\s*currentHash\b[\s\S]*?\bpendingHash\s*=\s*null\b[\s\S]*?\breturn\b",
            executable,
        )
    )
    navigation_executable = same_document_hash.sub(
        "", executable, count=1 if trusted_same_document_hash else 0,
    )
    if re.search(
        r"\bwindow\s*\.\s*open\b|\blocation\s*\.\s*(?:assign|replace)\b|"
        r"\b(?:window\s*\.\s*)?location(?:\s*\.\s*(?:href|hash))?\s*=(?!=)|\.\s*(?:submit|click)\s*\(|"
        r"\bhistory\s*\.\s*pushState\b",
        navigation_executable,
    ):
        issues.append(BundleIssue("forbidden_runtime_capability", "interactive.js", "programmatic external navigation is forbidden"))
    if re.search(r"\b(?:innerHTML|outerHTML|insertAdjacentHTML|document\.write|DOMParser|cssText|localStorage|sessionStorage)\b", executable):
        issues.append(BundleIssue("forbidden_runtime_sink", "interactive.js", "unsafe DOM or persistence sink is forbidden"))
    return tuple(issues)


def load_runtime_assets() -> RuntimeAssets:
    root = Path(__file__).resolve().parent / "runtime"
    assets = RuntimeAssets(css=(root / "interactive.css").read_bytes(), js=(root / "interactive.js").read_bytes())
    issues = _asset_issues(assets)
    if issues:
        raise BundleValidationError(issues)
    return assets


def content_security_policy(assets: RuntimeAssets) -> str:
    issues = _asset_issues(assets)
    if issues:
        raise BundleValidationError(issues)
    script_digest = base64.b64encode(hashlib.sha256(assets.js).digest()).decode("ascii")
    style_digest = base64.b64encode(hashlib.sha256(assets.css).digest()).decode("ascii")
    return (
        "default-src 'none'; "
        f"script-src 'sha256-{script_digest}'; script-src-attr 'none'; "
        f"style-src 'sha256-{style_digest}'; style-src-elem 'sha256-{style_digest}'; style-src-attr 'unsafe-inline'; "
        "connect-src 'none'; img-src 'none'; font-src 'none'; media-src 'none'; "
        "object-src 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'; form-action 'none'"
    )


class _ArtifactBudgetExceeded(ValueError):
    pass


class _ArtifactParser(HTMLParser):
    def __init__(self, assets: RuntimeAssets, allowed_sources: Mapping[tuple[int, str], str], local_ids: set[str] | None):
        super().__init__(convert_charrefs=True)
        self.assets = assets
        self.allowed_sources = allowed_sources
        self.expected_local_ids = local_ids
        self.issues: list[BundleIssue] = []
        self.stack: list[tuple[str, bool, bool, bool, bool, bool, bool, bool]] = []
        self.ids: set[str] = set()
        self.local_hrefs: list[str] = []
        self.script_parts: list[str] = []
        self.style_parts: list[str] = []
        self.envelope_parts: list[str] = []
        self.script_count = self.style_count = self.envelope_count = self.csp_count = 0
        self.referrer_count = 0
        self.element_count = 0
        self.slide_counts: list[int] = []
        self.slide_records: list[tuple[str, str]] = []
        self.current_slide = -1
        self.in_evidence = 0
        self.current_evidence_ordinal = -1
        self.in_semantic_scene = 0
        self.head_direct_children = 0
        self.head_charset_ok = False
        self.document_html_count = 0
        self.document_head_count = 0
        self.document_body_count = 0
        self.doctype_count = 0
        self.top_level_content = False
        self.root_started = False
        self.root_closed = False
        self.root_direct_children: list[str] = []
        self.in_envelope = 0
        self.svg_depth = 0
        self.seen_sources: set[tuple[int, str]] = set()
        self.target_nodes: list[tuple[str, str]] = []

    def issue(self, code: str, location: str, message: str) -> None:
        self.issues.append(BundleIssue(code, location, message))

    def handle_decl(self, decl: str) -> None:
        exact_doctype = decl.strip().lower() == "doctype html"
        if exact_doctype:
            self.doctype_count += 1
        if (
            not exact_doctype
            or self.doctype_count != 1
            or self.top_level_content
            or self.root_started
            or self.root_closed
        ):
            self.issue("html_root", "<!DOCTYPE>", "document must begin with one exact HTML doctype")

    def handle_comment(self, data: str) -> None:
        self.issue("html_root", "<!-- -->", "generated document must not contain HTML comments")

    def handle_pi(self, data: str) -> None:
        self.issue("html_root", "<? ?>", "generated document must not contain processing instructions")

    def unknown_decl(self, data: str) -> None:
        self.issue("html_root", "<![ ]>", "generated document contains an unknown declaration")

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        pairs = [(name.lower(), value if value is not None else "") for name, value in attrs]
        if len({name for name, _ in pairs}) != len(pairs):
            self.issue("duplicate_attribute", tag, "duplicate HTML attribute")
        attributes = dict(pairs)
        parent_frame = self.stack[-1] if self.stack else None
        parent = parent_frame[0] if parent_frame else None
        top_level = parent_frame is None
        root_html = tag == "html" and top_level and not self.root_started
        if top_level:
            if not root_html or self.root_closed:
                self.issue("html_root", tag, "the only top-level element must be the single html root")
            self.top_level_content = True
        if root_html:
            self.root_started = True
        if tag == "html" and not self.stack:
            self.document_html_count += 1
        if parent_frame and parent_frame[5]:
            self.root_direct_children.append(tag)
        document_head = tag == "head" and bool(parent_frame and parent_frame[5])
        if document_head:
            self.document_head_count += 1
            if self.document_head_count > 1:
                self.issue("csp_mismatch", "head", "document must contain exactly one direct head")
                document_head = False
        parent_is_document_head = bool(parent_frame and parent_frame[6])
        document_body = tag == "body" and bool(parent_frame and parent_frame[5])
        if document_body:
            self.document_body_count += 1
            if self.document_body_count > 1:
                self.issue("envelope_node", "body", "document must contain exactly one direct body")
                document_body = False
        parent_is_document_body = bool(parent_frame and parent_frame[7])
        head_child_index = None
        if parent_is_document_head:
            self.head_direct_children += 1
            head_child_index = self.head_direct_children
            if head_child_index == 1:
                self.head_charset_ok = tag == "meta" and attributes == {"charset": "utf-8"}
        envelope_owner = (
            tag == "div"
            and parent_is_document_body
            and attributes == {
                "id": "idrt-deck-data",
                "hidden": "",
                "data-encoding": "base64url-json-v1",
            }
        )
        if self.in_envelope:
            self.issue("envelope_node", "#idrt-deck-data", "inert envelope cannot contain elements")
        classes = set(attributes.get("class", "").split())
        requested_evidence = "evidence-container" in classes
        semantic_scene = (
            tag == "div"
            and classes == {"semantic-scene"}
            and attributes == {"class": "semantic-scene"}
        )
        evidence_ordinal = -1
        if requested_evidence:
            try:
                evidence_ordinal = int(attributes.get("data-slide-ordinal", ""))
            except ValueError:
                evidence_ordinal = -1
        evidence = (
            requested_evidence
            and tag == "div"
            and classes == {"evidence-dialog", "evidence-container"}
            and evidence_ordinal > 0
            and attributes == {
                "id": f"idrt-evidence-dialog-{evidence_ordinal}",
                "class": "evidence-dialog evidence-container",
                "role": "dialog",
                "aria-modal": "true",
                "aria-labelledby": f"idrt-evidence-title-{evidence_ordinal}",
                "data-slide-ordinal": str(evidence_ordinal),
                "hidden": "",
            }
            and self.in_evidence == 0
        )
        if requested_evidence and not evidence:
            self.issue("source_link", tag, "evidence source owner is not the generated modal container")
        requested_slide_start = tag == "section" and "slide" in classes
        if requested_slide_start and self.current_slide >= 0:
            self.issue("slide_structure", "section.slide", "slide sections cannot be nested")
        slide_start = requested_slide_start and self.current_slide < 0
        if tag == "a" and self.svg_depth:
            self.issue("svg_anchor", "svg/a", "anchors are forbidden inside SVG")
        if tag not in {"meta", "link", "img", "br", "hr", "input", "source", "area", "base", "col", "embed", "param", "track", "wbr"}:
            self.stack.append((
                tag,
                evidence,
                slide_start,
                semantic_scene,
                envelope_owner,
                root_html,
                document_head,
                document_body,
            ))
            if evidence:
                self.in_evidence += 1
                self.current_evidence_ordinal = evidence_ordinal
            if semantic_scene:
                self.in_semantic_scene += 1
            if envelope_owner:
                self.in_envelope += 1
            if tag == "svg":
                self.svg_depth += 1
        self.element_count += 1
        if slide_start:
            self.current_slide = len(self.slide_counts)
            self.slide_counts.append(0)
            self.slide_records.append((
                attributes.get("id", ""),
                attributes.get("data-slide-id", ""),
            ))
        if self.current_slide >= 0:
            self.slide_counts[self.current_slide] += 1
        if self.element_count > MAX_DOM_ELEMENTS:
            self.issue("dom_limit", "<html>", "generated DOM exceeds global element limit")
            raise _ArtifactBudgetExceeded
        if self.current_slide >= 0 and self.slide_counts[self.current_slide] > MAX_DOM_ELEMENTS_PER_SLIDE:
            self.issue("dom_limit", f"slide:{self.current_slide + 1}", "generated slide exceeds element limit")
            raise _ArtifactBudgetExceeded
        identifier = attributes.get("id")
        if identifier:
            if identifier in self.ids:
                self.issue("duplicate_id", identifier, "duplicate document ID")
            self.ids.add(identifier)
        has_target_slide = "data-target-slide" in attributes
        has_target_key = "data-target-key" in attributes
        if has_target_slide or has_target_key:
            if (
                not has_target_slide
                or not has_target_key
                or tag not in {"input", "select", "fieldset", "button", "a", "span"}
                or not attributes.get("data-target-slide")
                or not attributes.get("data-target-key")
                or len(attributes["data-target-slide"]) > 64
                or len(attributes["data-target-key"]) > 140
            ):
                self.issue(
                    "target_registry",
                    tag,
                    "demo targets require one exact prebuilt registry node",
                )
            else:
                self.target_nodes.append((
                    attributes["data-target-slide"],
                    attributes["data-target-key"],
                ))
        forbidden_tags = {
            "iframe", "frame", "object", "embed", "form", "base",
            "foreignobject", "image", "use", "video", "audio", "source",
            "template", "noscript", "noembed", "noframes", "xmp",
            "plaintext", "textarea",
        }
        if tag in forbidden_tags:
            self.issue("forbidden_element", tag, "active or resource-bearing element is forbidden")
        for name, value in pairs:
            if name.startswith("on"):
                self.issue("event_handler", tag, "inline event handler is forbidden")
            if name in {"href", "xlink:href"} and not (tag == "a" and name == "href"):
                self.issue(
                    "resource_attribute",
                    f"{tag}/@{name}",
                    "only exact authorized anchor href values are allowed",
                )
            if name in {"src", "srcset", "poster", "background", "ping", "srcdoc", "action", "formaction", "attributionsrc"}:
                self.issue("image" if tag == "img" else "resource_attribute", f"{tag}/@{name}", "resource attribute is forbidden")
            if name == "download":
                self.issue("download", tag, "download navigation is forbidden")
            if name == "style":
                self.issue("inline_style", tag, "generated HTML cannot contain authored style text")
        if tag == "script":
            self.script_count += 1
            if pairs:
                self.issue("script_src" if "src" in attributes else "unexpected_script", "script", "runtime script must have no attributes")
        if tag == "style":
            self.style_count += 1
            if pairs:
                self.issue("unexpected_style", "style", "runtime style must have no attributes")
        if tag == "meta":
            http_equiv = attributes.get("http-equiv", "").strip().lower()
            if http_equiv == "refresh":
                self.issue("meta_refresh", "meta", "meta refresh is forbidden")
            if http_equiv == "content-security-policy":
                if not (
                    parent_is_document_head
                    and head_child_index == 2
                    and self.head_charset_ok
                    and set(attributes) == {"http-equiv", "content"}
                ):
                    self.issue("csp_mismatch", "meta", "CSP meta is not the fixed second head child")
                else:
                    self.csp_count += 1
                    try:
                        expected = content_security_policy(self.assets)
                    except BundleValidationError as error:
                        self.issues.extend(error.issues)
                    else:
                        if attributes.get("content") != expected:
                            self.issue("csp_mismatch", "meta", "CSP does not match fixed assets")
            if attributes.get("name", "").strip().lower() == "referrer":
                if parent_is_document_head and attributes == {
                    "name": "referrer",
                    "content": "no-referrer",
                }:
                    self.referrer_count += 1
                else:
                    self.issue(
                        "referrer_mismatch",
                        "meta",
                        "referrer policy must be the exact direct-head element",
                    )
        if tag == "link":
            self.issue("resource_hint", "link", "link/resource hints are forbidden")
        if tag == "a" and "href" in attributes:
            href = attributes["href"]
            if href.startswith("#"):
                self.local_hrefs.append(href[1:])
                exact_skip = attributes == {
                    "id": "idrt-skip",
                    "class": "skip-link",
                    "href": "#idrt-deck-pages",
                }
                page_index = attributes.get("data-page-index")
                exact_page_link = (
                    set(attributes) == {"href", "data-page-index"}
                    and page_index is not None
                    and page_index.isascii()
                    and page_index.isdigit()
                    and href == "#idrt-page-" + page_index
                )
                exact_nav_action = (
                    set(attributes) == {"href", "data-nav-action"}
                    and attributes.get("data-nav-action") in {"previous", "next"}
                )
                if (
                    set(attributes) != {"href"}
                    and not exact_skip
                    and not exact_page_link
                    and not exact_nav_action
                ):
                    self.issue("local_link", "a", "local anchors cannot open or impersonate source navigation")
            else:
                try:
                    ordinal = int(attributes.get("data-slide-ordinal", ""))
                except ValueError:
                    ordinal = -1
                source_id = attributes.get("data-source-id", "")
                expected = self.allowed_sources.get((ordinal, source_id))
                expected_attributes = {"data-slide-ordinal", "data-source-id", "href"}
                if has_target_slide or has_target_key:
                    expected_attributes.update({"data-target-slide", "data-target-key"})
                if _is_https_source(href):
                    expected_attributes.update({"target", "rel", "referrerpolicy"})
                if (
                    not self.in_evidence
                    or self.current_evidence_ordinal != ordinal
                    or expected != href
                    or not safe_source_url(href)
                    or set(attributes) != expected_attributes
                ):
                    self.issue("source_link", "a", "anchor is not an exact authorized evidence source")
                else:
                    key = (ordinal, source_id)
                    if key in self.seen_sources:
                        self.issue("source_link", "a", "authorized evidence source appears more than once")
                    self.seen_sources.add(key)
                if _is_https_source(href):
                    if attributes.get("target") != "_blank" or set(attributes.get("rel", "").split()) != {"noopener", "noreferrer"} or attributes.get("referrerpolicy") != "no-referrer":
                        self.issue("source_link", "a", "HTTPS source policy attributes are incomplete")
                elif any(name in attributes for name in ("target", "rel", "referrerpolicy")):
                    self.issue("source_link", "a", "mailto source must not open a new tab")
        if tag == "div" and attributes.get("id") == "idrt-deck-data":
            self.envelope_count += 1
            if not envelope_owner:
                self.issue("envelope_node", "#idrt-deck-data", "invalid inert envelope node")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.stack:
            opened, evidence, slide_start, semantic_scene, envelope_owner, root_html, _, _ = self.stack.pop()
            if evidence:
                self.in_evidence -= 1
                self.current_evidence_ordinal = -1
            if semantic_scene:
                self.in_semantic_scene -= 1
            if envelope_owner:
                self.in_envelope -= 1
            if opened == "svg":
                self.svg_depth -= 1
            if slide_start:
                self.current_slide = -1
            if opened != tag:
                self.issue("html_nesting", tag, "mismatched generated HTML nesting")
            if root_html:
                self.root_closed = True
        else:
            self.issue("html_nesting", tag, "unexpected generated HTML closing tag")

    def handle_data(self, data):
        if not self.stack:
            if data.strip():
                self.top_level_content = True
                self.issue("html_root", "<document>", "only whitespace is allowed outside the html root")
            return
        tag = self.stack[-1][0]
        if data.strip() and (self.stack[-1][5] or self.stack[-1][6]):
            self.issue(
                "html_root",
                tag,
                "only whitespace is allowed directly in the html root or document head",
            )
        if tag == "script":
            self.script_parts.append(data)
        elif tag == "style":
            self.style_parts.append(data)
        elif self.stack[-1][4]:
            encoded = data.strip()
            if not encoded or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
                self.issue("envelope_node", "#idrt-deck-data", "invalid inert envelope text")
            else:
                self.envelope_parts.append(encoded)


def inspect_self_contained(
    html_text: str,
    *,
    assets: RuntimeAssets,
    allowed_sources: Mapping[tuple[int, str], str] | None = None,
    local_ids: set[str] | None = None,
) -> tuple[BundleIssue, ...]:
    if not isinstance(html_text, str):
        return (BundleIssue("html_type", "<html>", "artifact must be Unicode text"),)
    try:
        html_size = len(html_text.encode("utf-8", "strict"))
    except UnicodeError:
        return (BundleIssue("html_utf8", "<html>", "artifact must be strict UTF-8 text"),)
    if html_size > MAX_HTML_BYTES:
        return (BundleIssue("html_limit", "<html>", "final HTML exceeds 48 MiB"),)
    issues = list(_asset_issues(assets))
    parser = _ArtifactParser(assets, allowed_sources or {}, local_ids)
    try:
        parser.feed(html_text)
        parser.close()
        if parser.stack:
            parser.issue("html_nesting", parser.stack[-1][0], "unclosed generated HTML element")
    except _ArtifactBudgetExceeded:
        return tuple(issues + parser.issues)
    except (ValueError, RecursionError):
        parser.issue("html_parse", "<html>", "generated HTML could not be verified")
    issues.extend(parser.issues)
    if (
        parser.doctype_count != 1
        or not parser.root_started
        or not parser.root_closed
        or parser.root_direct_children != ["head", "body"]
    ):
        issues.append(BundleIssue(
            "html_root",
            "<html>",
            "expected one doctype and one html root with direct head then body",
        ))
    if parser.script_count != 1:
        issues.append(BundleIssue("script_count", "<html>", "expected exactly one fixed runtime script"))
    elif "".join(parser.script_parts).encode("utf-8") != assets.js:
        issues.append(BundleIssue("tampered_script", "script", "runtime script bytes differ from fixed asset"))
    if parser.style_count != 1:
        issues.append(BundleIssue("style_count", "<html>", "expected exactly one fixed runtime style"))
    elif "".join(parser.style_parts).encode("utf-8") != assets.css:
        issues.append(BundleIssue("tampered_style", "style", "runtime style bytes differ from fixed asset"))
    if parser.csp_count != 1:
        issues.append(BundleIssue("csp_mismatch", "<head>", "expected exactly one fixed CSP meta element"))
    if parser.referrer_count != 1:
        issues.append(BundleIssue(
            "referrer_mismatch",
            "<head>",
            "expected exactly one exact direct-head referrer policy",
        ))
    if parser.document_html_count != 1 or parser.document_head_count != 1:
        issues.append(BundleIssue("csp_mismatch", "<head>", "CSP must belong to the single document head"))
    if parser.document_body_count != 1:
        issues.append(BundleIssue("envelope_node", "<body>", "envelope must belong to the single document body"))
    decoded_payload = None
    if parser.envelope_count != 1 or len(parser.envelope_parts) != 1:
        issues.append(BundleIssue("envelope_node", "<html>", "expected exactly one inert encoded envelope"))
    else:
        try:
            decoded_payload = decode_envelope(parser.envelope_parts[0])
        except BundleValidationError as error:
            issues.extend(error.issues)
    if decoded_payload is not None:
        expected_slides = [
            (f"idrt-page-{index}", slide["slideId"])
            for index, slide in enumerate(decoded_payload["slides"], start=1)
        ]
        if parser.slide_records != expected_slides:
            issues.append(BundleIssue(
                "slide_structure",
                "<main>",
                "generated slide sections do not match the ordered envelope registry",
            ))
        expected_targets: set[tuple[str, str]] = set()
        for slide in decoded_payload["slides"]:
            scene = slide.get("scene")
            if isinstance(scene, dict):
                expected_targets.update(
                    (slide["slideId"], target_key)
                    for target_key in scene.get("targets", {})
                )
        target_counts: dict[tuple[str, str], int] = {}
        for target in parser.target_nodes:
            target_counts[target] = target_counts.get(target, 0) + 1
        if (
            set(target_counts) != expected_targets
            or any(count != 1 for count in target_counts.values())
        ):
            issues.append(BundleIssue(
                "target_registry",
                "<html>",
                "prebuilt demo targets must match the compiled target registry exactly once",
            ))
    for target in parser.local_hrefs:
        if target not in parser.ids:
            issues.append(BundleIssue("local_link", target, "local anchor target does not exist"))
    missing_sources = set(parser.allowed_sources).difference(parser.seen_sources)
    if missing_sources:
        issues.append(BundleIssue("source_link", "<html>", "authorized evidence source anchor is missing"))
    if local_ids is not None and parser.ids != local_ids:
        issues.append(BundleIssue("id_registry", "<html>", "document IDs differ from generated registry"))
    return tuple(issues)


def assert_self_contained(
    html_text: str,
    *,
    assets: RuntimeAssets,
    allowed_sources: Mapping[tuple[int, str], str] | None = None,
    local_ids: set[str] | None = None,
) -> None:
    issues = inspect_self_contained(html_text, assets=assets, allowed_sources=allowed_sources, local_ids=local_ids)
    if issues:
        raise BundleValidationError(issues)


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _summary_html(
    summary: dict,
    *,
    ordinal: int,
    interactive: bool,
    decision_range_message: str | None = None,
) -> str:
    parts = [
        f'<h1 id="idrt-heading-{ordinal}" tabindex="-1">{_escape(summary["headline"])}</h1>'
    ]
    parts.append('<div class="scene-summary">')
    for paragraph in summary["paragraphs"]:
        parts.append(f'<p data-summary-paragraph>{_escape(paragraph)}</p>')
    if summary["values"]:
        parts.append('<dl class="static-values">')
        for value in summary["values"]:
            parts.append(
                f'<div><dt>{_escape(value["label"])}</dt>'
                f'<dd>{_escape(value["text"])}</dd></div>'
            )
        parts.append("</dl>")
    if summary["decision"] is not None:
        parts.append(
            '<div class="static-decision-result"><strong>'
            + _escape(summary["decision"]["status"])
            + '</strong><p>'
            + _escape(summary["decision"]["recommendation"])
            + "</p></div>"
        )
    parts.append("</div>")
    if interactive:
        parts.append('<div class="live-summary" hidden aria-hidden="true">')
        if summary["values"]:
            parts.append('<dl class="semantic-values">')
            for value in summary["values"]:
                parts.append(
                    f'<div data-output-id="{_escape(value["id"])}"><dt>{_escape(value["label"])}</dt>'
                    f'<dd data-live-value="{_escape(value["id"])}">{_escape(value["text"])}</dd></div>'
                )
            parts.append("</dl>")
        if summary["decision"] is not None:
            parts.append(
                '<div class="decision-result"><strong data-decision-status>'
                + _escape(summary["decision"]["status"])
                + '</strong><p data-decision-recommendation>'
                + _escape(summary["decision"]["recommendation"])
                + "</p></div>"
            )
        parts.append("</div>")
    if decision_range_message is not None:
        parts.append(
            '<p class="decision-range-note" data-decision-range="constant">'
            + _escape(decision_range_message)
            + "</p>"
        )
    if interactive:
        parts.append(
            f'<p id="idrt-status-{ordinal}" class="scene-status" '
            'aria-live="polite" aria-atomic="true"></p>'
        )
    return "".join(parts)


def _format_control_value(scene: dict, control: dict, raw_value: object | None = None) -> str:
    program = scene["narration"]["program"]
    atom = next(item for item in program["controls"] if item["id"] == control["id"])
    value = Decimal(
        scene["initialState"][control["id"]]
        if raw_value is None else str(raw_value)
    )
    precision = max(0, -Decimal(control["min"]).as_tuple().exponent, -Decimal(control["step"]).as_tuple().exponent)
    with localcontext() as context:
        context.prec = 40
        rounded = value.quantize(
            Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP
        )
    number = format(abs(rounded), f',.{precision}f')
    sign = "−" if rounded < 0 else ""
    display = atom["display"]
    if display.startswith(("$", "€", "£", "¥", "￥")):
        number = display[0] + number + display[1:]
    else:
        number += ("" if display == "%" else " ") + display
    return sign + number


def _format_control_state_value(scene: dict, control: dict, raw_value: object | None = None) -> str:
    value = scene["initialState"][control["id"]] if raw_value is None else str(raw_value)
    if control["kind"] == "range":
        return _format_control_value(scene, control, value)
    for option in control["options"]:
        if option["value"] == value:
            return option["label"]
    return value


def _tooltip_html(ordinal: int, item_id: str, label: str, text_value: str) -> str:
    tooltip_id = f"idrt-tooltip-{ordinal}-{item_id}"
    return (
        f'<button type="button" class="tooltip-proxy" data-tooltip-for="{_escape(item_id)}" '
        f'aria-controls="{tooltip_id}" aria-expanded="false">{_escape(label)}</button>'
        f'<div id="{tooltip_id}" class="derived-tooltip" role="tooltip" hidden>{_escape(text_value)}</div>'
    )


def _target_attributes(scene: dict, target_key: str) -> str:
    """Return the exact prebuilt DOM registry attributes for one target."""
    targets = scene.get("targets", {})
    if target_key not in targets:
        return ""
    return (
        f' data-target-slide="{_escape(scene["slideId"])}"'
        f' data-target-key="{_escape(target_key)}"'
    )


def _semantic_view_html(scene: dict, ordinal: int) -> str:
    view = scene.get("initialEvaluation", {}).get("view")
    if not isinstance(view, dict):
        return ""
    component = view["component"]
    parts = [
        f'<div class="semantic-view" data-view-component="{_escape(component)}" hidden>'
    ]
    removed_label = "除外" if scene["locale"] == "ja" else "removed"
    if component in ("bar_compare", "ranked_list"):
        for row in view["items"]:
            item_id = row["id"]
            parts.append(
                f'<div class="view-item" data-view-item-id="{_escape(item_id)}" '
                f'data-removed="{str(row["removed"]).lower()}" '
                f'data-emphasis="{str(row["emphasis"]).lower()}">'
                f'<span data-view-label hidden>{_escape(row["label"])}</span>'
            )
            if component == "bar_compare":
                parts.append(f'<span data-view-value>{_escape(row["valueText"])}</span>')
                tooltip = f'{row["label"]}; {row["valueText"]}'
            else:
                parts.append(f'<span data-view-rank>{row["rank"]}</span>')
                metric = row.get("metricText", "")
                if metric:
                    parts.append(f'<span data-view-metric>{_escape(metric)}</span>')
                tooltip = f'{row["rank"]}; {row["label"]}' + (f'; {metric}' if metric else "")
            parts.append(
                f'<span data-view-removal{"" if row["removed"] else " hidden"}>'
                f'{_escape(removed_label)}</span>'
            )
            if row["removed"]:
                tooltip += "; " + removed_label
            parts.append(_tooltip_html(ordinal, item_id, row["label"], tooltip))
            parts.append("</div>")
    elif component == "dot_plot":
        for point in view["points"]:
            item_id = point["id"]
            tooltip = (
                f'{point["label"]}; {view["xLabel"]}: {point["xText"]}; '
                f'{view["yLabel"]}: {point["yText"]}'
            )
            if point["removed"]:
                tooltip += "; " + removed_label
            parts.extend((
                f'<div class="view-item" data-view-item-id="{_escape(item_id)}" '
                f'data-removed="{str(point["removed"]).lower()}" '
                f'data-emphasis="{str(point["highlight"]).lower()}">',
                f'<span data-view-label hidden>{_escape(point["label"])}</span>',
                f'<span data-view-x>{_escape(view["xLabel"])}: {_escape(point["xText"])}</span>',
                f'<span data-view-y>{_escape(view["yLabel"])}: {_escape(point["yText"])}</span>',
                f'<span data-view-removal{"" if point["removed"] else " hidden"}>{_escape(removed_label)}</span>',
                _tooltip_html(ordinal, item_id, point["label"], tooltip),
                "</div>",
            ))
    else:
        score = view["score"]
        score_definition = scene["outputDefinitions"]["score"]
        score_text = _format_scene_value(
            scene,
            score["value"],
            score_definition["quantity"],
            score_definition["round"],
        )
        parts.append(f'<p class="recommendation-score" data-view-score>{_escape(score_text)}</p>')
        parts.append('<div class="score-bands">')
        for band in scene["model"]["bands"]:
            item_id = band["id"]
            minimum = band["min"]["value"]
            maximum = band["max"]["value"]
            tooltip = f'{band["label"]}; {minimum}; {maximum}'
            parts.extend((
                f'<div class="score-band" data-view-item-id="{_escape(item_id)}" data-removed="false">',
                f'<span data-view-label hidden>{_escape(band["label"])}</span>',
                f'<span data-band-min>{_escape(minimum)}</span>',
                f'<span data-band-max>{_escape(maximum)}</span>',
                _tooltip_html(ordinal, item_id, band["label"], tooltip),
                "</div>",
            ))
        parts.append("</div>")
    parts.append("</div>")
    return "".join(parts)


def _panel_surface_html(scene: dict, ordinal: int, labels: Mapping[str, str]) -> str:
    if scene["type"] not in ("drilldown", "accordion"):
        return ""
    states = scene["states"]
    parts = ['<div class="panel-surface" hidden>']
    if scene["type"] == "drilldown":
        parts.append(f'<p class="panel-parent-summary">{_escape(states["parentSummary"])}</p>')
        parts.append('<div class="panel-openers">')
        for panel in states["panels"]:
            open_target = _target_attributes(scene, f'panel:{panel["id"]}')
            parts.append(
                f'<button type="button" data-action="open-panel" '
                f'data-panel-target="{_escape(panel["id"])}" aria-expanded="false" '
                f'aria-controls="idrt-panel-{ordinal}-{_escape(panel["id"])}"{open_target}>'
                f'{_escape(panel["label"])}</button>'
            )
        parts.append("</div>")
        for panel in states["panels"]:
            close_target = _target_attributes(scene, f'panel:{panel["id"]}:close')
            parts.append(
                f'<section id="idrt-panel-{ordinal}-{_escape(panel["id"])}" '
                f'data-panel-id="{_escape(panel["id"])}" hidden>'
                f'<h2>{_escape(panel["heading"])}</h2><p>{_escape(panel["body"])}</p>'
                f'<button type="button" data-action="close-panel" data-panel-target="{_escape(panel["id"])}"{close_target}>'
                f'{_escape(states["returnLabel"])}</button></section>'
            )
    else:
        for panel in states["panels"]:
            panel_id = panel["id"]
            open_target = _target_attributes(scene, f"panel:{panel_id}")
            close_target = _target_attributes(scene, f"panel:{panel_id}:close")
            parts.append(
                f'<section class="accordion-item" data-panel-id="{_escape(panel_id)}">'
                f'<h2><button type="button" data-accordion-id="{_escape(panel_id)}" '
                f'aria-expanded="false" aria-controls="idrt-panel-{ordinal}-{_escape(panel_id)}">'
                f'{_escape(panel["label"])}</button></h2>'
                f'<div id="idrt-panel-{ordinal}-{_escape(panel_id)}" class="accordion-panel" '
                f'data-accordion-panel="{_escape(panel_id)}" hidden>'
                f'<h3>{_escape(panel["heading"])}</h3><p>{_escape(panel["body"])}</p>'
                f'<button type="button" data-action="close-panel" data-panel-target="{_escape(panel_id)}"{close_target}>'
                f'{_escape(labels["close"])}</button></div></section>'
            )
            # Insert the registry attributes on the one focusable opener rather
            # than duplicating them on its containing section.
            parts[-1] = parts[-1].replace(
                f'aria-controls="idrt-panel-{ordinal}-{_escape(panel_id)}">',
                f'aria-controls="idrt-panel-{ordinal}-{_escape(panel_id)}"{open_target}>',
                1,
            )
    parts.append("</div>")
    return "".join(parts)


def _controls_html(scene: dict, ordinal: int, labels: Mapping[str, str]) -> str:
    view = _semantic_view_html(scene, ordinal)
    data_label = "数値を確認" if scene["locale"] == "ja" else "View data"
    details = f'<details class="data-details"><summary>{data_label}</summary>{view}</details>' if view else ""
    parts = [details, _panel_surface_html(scene, ordinal, labels), '<div class="control-rail" hidden>']
    for position, control in enumerate(scene["controls"], start=1):
        control_id = f"idrt-control-{ordinal}-{position}"
        output_id = f"idrt-control-value-{ordinal}-{position}"
        if control["kind"] == "range":
            minimum = Decimal(control["min"])
            maximum = Decimal(control["max"])
            step = Decimal(control["step"])
            value = Decimal(scene["initialState"][control["id"]])
            positions = int((maximum - minimum) / step)
            selected = int((value - minimum) / step)
            value_text = _format_control_value(scene, control)
            parts.extend((
                '<div class="range-control">',
                f'<label for="{control_id}">{_escape(control["label"])} '
                f'<output id="{output_id}" for="{control_id}">{_escape(value_text)}</output></label>',
                f'<input id="{control_id}" type="range" min="0" '
                f'max="{positions}" step="1" value="{selected}" '
                f'data-control-id="{_escape(control["id"])}" '
                f'data-target-slide="{_escape(scene["slideId"])}" '
                f'data-target-key="control:{_escape(control["id"])}" '
                f'aria-valuetext="{_escape(scene["initialState"][control["id"]])}" '
                f'aria-describedby="idrt-status-{ordinal}">',
                '</div>',
            ))
        elif control["kind"] == "select":
            parts.append(f'<div class="option-control" data-control-id="{_escape(control["id"])}">')
            parts.append(f'<label for="{control_id}">{_escape(control["label"])}</label>')
            parts.append(
                f'<select id="{control_id}" data-control-select '
                f'aria-describedby="idrt-status-{ordinal}"'
                f'{_target_attributes(scene, f"control:{control["id"]}")}>'
            )
            for option in control["options"]:
                selected = " selected" if option["value"] == scene["initialState"][control["id"]] else ""
                parts.append(f'<option value="{_escape(option["value"])}"{selected}>{_escape(option["label"])}</option>')
            parts.append('</select><output id="' + output_id + '" hidden>' + _escape(_format_control_state_value(scene, control)) + '</output></div>')
        else:
            parts.append(
                f'<fieldset id="{control_id}" class="option-control" '
                f'data-control-id="{_escape(control["id"])}"'
                f'{_target_attributes(scene, f"control:{control["id"]}")}>'
                f'<legend>{_escape(control["label"])}</legend>'
            )
            for option in control["options"]:
                selected = option["value"] == scene["initialState"][control["id"]]
                parts.append(
                    f'<button type="button" data-control-value="{_escape(option["value"])}" '
                    f'aria-pressed="{str(selected).lower()}">{_escape(option["label"])}</button>'
                )
            parts.append('</fieldset><output id="' + output_id + '" hidden>' + _escape(_format_control_state_value(scene, control)) + '</output>')
    parts.extend((
        f'<button id="idrt-reset-{ordinal}" type="button" data-action="reset">{_escape(labels["reset"])}</button>',
        f'<button id="idrt-evidence-open-{ordinal}" type="button" data-action="evidence" '
        f'aria-haspopup="dialog" aria-controls="idrt-evidence-dialog-{ordinal}" '
        f'aria-expanded="false"{_target_attributes(scene, "evidence:open")}>{_escape(scene["evidence"]["triggerLabel"])}</button>',
        f'<button id="idrt-static-toggle-{ordinal}" type="button" data-action="static" '
        f'aria-pressed="false"{_target_attributes(scene, "static:toggle")}>{_escape(labels["static_view"])}</button>',
        '</div>',
    ))
    return "".join(parts)


def _evidence_dialog_html(
    scene: dict,
    ordinal: int,
    allowed_sources: dict[tuple[int, str], str],
    labels: Mapping[str, str],
) -> str:
    evidence = scene.get("evidence", {})
    sources = evidence.get("sources", []) if isinstance(evidence, dict) else []
    assumptions = evidence.get("assumptions", []) if isinstance(evidence, dict) else []
    formulas = evidence.get("formulas", []) if isinstance(evidence, dict) else []
    title_id = f"idrt-evidence-title-{ordinal}"
    sources_tab = f"idrt-evidence-tab-sources-{ordinal}"
    assumptions_tab = f"idrt-evidence-tab-assumptions-{ordinal}"
    sources_panel = f"idrt-evidence-panel-sources-{ordinal}"
    assumptions_panel = f"idrt-evidence-panel-assumptions-{ordinal}"
    parts = [
        f'<div id="idrt-evidence-dialog-{ordinal}" class="evidence-dialog evidence-container" '
        f'role="dialog" aria-modal="true" aria-labelledby="{title_id}" hidden '
        f'data-slide-ordinal="{ordinal}"><div class="evidence-card">'
        f'<div class="evidence-header"><h2 id="{title_id}">{_escape(labels["evidence_title"])}</h2>'
        f'<button id="idrt-evidence-close-{ordinal}" type="button" data-action="evidence-close"'
        f'{_target_attributes(scene, "evidence:close")}>'
        f'{_escape(labels["close"])}</button></div>'
    ]
    badge = evidence.get("badge") if isinstance(evidence, dict) else None
    if isinstance(badge, str) and badge:
        parts.append(
            f'<p class="evidence-badge"><strong>{_escape(labels["basis"])}:</strong> '
            f'{_escape(badge)}</p>'
        )
    controls = scene.get("controls", [])
    if controls:
        parts.append(f'<section class="evidence-inputs"><h3>{_escape(labels["input_range"])}</h3>')
        for control in controls:
            if control["kind"] == "range":
                range_text = (
                    f'{control["label"]}: '
                    f'{_format_control_value(scene, control, control["min"])} – '
                    f'{_format_control_value(scene, control, control["max"])}; '
                    f'{labels["step"]} {_format_control_value(scene, control, control["step"])}'
                )
            else:
                range_text = control["label"] + ": " + ", ".join(
                    option["label"] for option in control["options"]
                )
            parts.append(f'<p>{_escape(range_text)}</p>')
        parts.append('</section>')
        parts.append(f'<section class="evidence-print-state"><h3>{_escape(labels["print_state"])}</h3>')
        for control in controls:
            print_text = (
                f'{control["label"]}: '
                f'{_format_control_state_value(scene, control, scene["printState"][control["id"]])}'
            )
            parts.append(f'<p>{_escape(print_text)}</p>')
        parts.append('</section>')
    leaf_labels = {
        leaf.get("id"): str(leaf.get("label", ""))
        for leaf in evidence.get("leaves", [])
        if isinstance(leaf, dict) and isinstance(leaf.get("id"), str)
    }
    output_definitions = scene.get("outputDefinitions", {})
    initial_outputs = scene.get("initialEvaluation", {}).get("outputs", {})
    reporting = scene.get("reporting", {})
    output_ids = [
        reporting.get("primaryOutput"),
        *reporting.get("secondaryOutputs", []),
    ]
    lineage_rows: list[tuple[str, str]] = []
    for output_id in output_ids:
        definition = output_definitions.get(output_id, {})
        output = initial_outputs.get(output_id, {})
        lineage = output.get("lineage", {})
        path = [
            leaf_labels[leaf_id]
            for leaf_id in lineage.get("leaves", [])
            if leaf_id in leaf_labels
        ] + [str(step) for step in lineage.get("steps", [])]
        if definition.get("label") and path:
            lineage_rows.append((str(definition["label"]), " → ".join(path)))
    if lineage_rows:
        parts.append(f'<section class="evidence-lineage"><h3>{_escape(labels["lineage"])}</h3>')
        for label, path in lineage_rows:
            parts.append(f'<p><strong>{_escape(label)}:</strong> {_escape(path)}</p>')
        parts.append('</section>')
    if sources and assumptions:
        parts.append(
            f'<div class="evidence-tabs" role="tablist" aria-label="{_escape(labels["evidence_title"])}">'
            f'<button id="{sources_tab}" type="button" role="tab" data-evidence-tab="sources" '
            f'aria-selected="true" aria-controls="{sources_panel}" tabindex="0">{_escape(labels["sources"])}</button>'
            f'<button id="{assumptions_tab}" type="button" role="tab" data-evidence-tab="assumptions" '
            f'aria-selected="false" aria-controls="{assumptions_panel}" tabindex="-1">{_escape(labels["assumptions"])}</button>'
            '</div>'
        )
    if sources:
        panel_attributes = (
            f'id="{sources_panel}" data-evidence-panel="sources"'
            + (f' role="tabpanel" aria-labelledby="{sources_tab}"' if assumptions else "")
        )
        parts.append(f'<section {panel_attributes}><h3>{_escape(labels["sources"])}</h3><ul>')
        for source in sources:
            source_id = source.get("id", "")
            label = _escape(str(source.get("label", "")))
            detail = _escape(str(source.get("detail", "")))
            url = source.get("url")
            linked = source.get("linked") is True and safe_source_url(url)
            target_attributes = _target_attributes(scene, f"source:{source_id}")
            if linked:
                allowed_sources[(ordinal, source_id)] = url
                common = (
                    f'data-slide-ordinal="{ordinal}" data-source-id="{_escape(source_id)}" '
                    f'href="{_escape(url)}"'
                )
                if _is_https_source(url):
                    common += ' target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer"'
                common += target_attributes
                parts.append(f"<li><a {common}>{label}</a><p>{detail}</p></li>")
            else:
                parts.append(f"<li><span{target_attributes}>{label}</span><p>{detail}</p></li>")
        parts.append("</ul></section>")
    if assumptions:
        panel_attributes = (
            f'id="{assumptions_panel}" data-evidence-panel="assumptions"'
            + (f' role="tabpanel" aria-labelledby="{assumptions_tab}" hidden' if sources else "")
        )
        parts.append(f'<section {panel_attributes}><h3>{_escape(labels["assumptions"])}</h3><ul>')
        for assumption in assumptions:
            text = f'{assumption.get("label", "")}: {assumption.get("value", "")}'
            if assumption.get("unit"):
                text += " " + str(assumption["unit"])
            parts.append(f"<li>{_escape(text)}</li>")
        parts.append("</ul></section>")
    if formulas:
        parts.append(f'<section class="evidence-formula"><h3>{_escape(labels["formula"])}</h3>')
        for formula in formulas:
            parts.append(f"<p>{_escape(str(formula))}</p>")
        parts.append("</section>")
    parts.append("</div></div>")
    return "".join(parts)


def _estimated_slide_elements(slide: BundleSlide) -> int:
    """Return a conservative pre-assembly count for all emitted variants."""
    summary = slide.static_summary
    count = 3 + slide.fallback_svg.element_count  # section, frame, fallback wrapper
    if slide.live_shell_svg is not None:
        count += 1 + slide.live_shell_svg.element_count
    count += 3 + len(summary["paragraphs"])  # semantic wrapper, h1 and static-summary wrapper
    if summary["values"]:
        count += 1 + 3 * len(summary["values"])
    if summary["decision"] is not None:
        count += 3
    if slide.decision_range_message is not None:
        count += 1
    count += 1  # semantic source
    if slide.scene is not None:
        count += 1  # live-summary wrapper
        if summary["values"]:
            count += 1 + 3 * len(summary["values"])
        if summary["decision"] is not None:
            count += 3
        count += 1  # status
        count += 6 + 4 * len(slide.scene.get("controls", []))  # rail, controls, actions and data disclosure
        evidence = slide.scene.get("evidence", {})
        if isinstance(evidence, dict):
            sources = evidence.get("sources", [])
            assumptions = evidence.get("assumptions", [])
            formulas = evidence.get("formulas", [])
            if any(isinstance(items, list) and items for items in (sources, assumptions, formulas)):
                count += 5  # dialog, card, header, title and close
                if sources and assumptions:
                    count += 3  # tablist and two tabs
                if isinstance(sources, list) and sources:
                    count += 3 + 3 * len(sources)  # panel, heading, list and rows
                if isinstance(assumptions, list) and assumptions:
                    count += 3 + len(assumptions)
                if isinstance(formulas, list) and formulas:
                    count += 2 + len(formulas)
                controls = slide.scene.get("controls", [])
                reporting = slide.scene.get("reporting", {})
                output_count = int(bool(reporting.get("primaryOutput"))) + len(reporting.get("secondaryOutputs", []))
                count += 2  # compiler-owned basis paragraph and strong label
                if controls:
                    count += 4 + 2 * len(controls)  # input/print sections, headings and rows
                if output_count:
                    count += 2 + 2 * output_count  # lineage section/heading and strong-labelled rows
    return count + 3  # no-JS nav and its two anchors


def _overview_svg(svg: ValidatedSvg, ordinal: int) -> tuple[str, tuple[str, ...]]:
    """Clone one sealed fallback SVG with a deterministic overview namespace."""
    if not _validated_svg_intact(svg, slide_ordinal=ordinal, role="fallback"):
        _raise("svg_boundary", f"slide:{ordinal}/overview", "overview requires a validated fallback")
    mapping = {
        identifier: f"idrtov-{ordinal}-{index}"
        for index, identifier in enumerate(svg.ids, start=1)
    }
    # The validated serialization is already inert and accessibility-hidden.
    # Rewrite only exact validator-owned ID/reference tokens so text-node
    # whitespace remains byte-for-byte identical to the slide fallback.
    serialized = _document_fallback_svg(svg, ordinal)
    for identifier, replacement in mapping.items():
        serialized = serialized.replace(
            f'id="{identifier}"', f'id="{replacement}"'
        ).replace(
            f'url(#{identifier})', f'url(#{replacement})'
        )
    return serialized, tuple(mapping.values())


def _document_fallback_svg(svg: ValidatedSvg, ordinal: int) -> str:
    """Return the inert visual fallback without renderer-only tooltip text.

    The classic renderer nests ``title`` inside ``text`` when a visible label
    is truncated.  The complete accessible equivalent lives in the semantic
    HTML, while the SVG root is deliberately aria-hidden.  Removing those
    non-rendering descendants keeps the main and overview copies textually
    identical whether the main fallback is currently hidden behind live mode
    or rendered as a thumbnail.
    """
    if not _validated_svg_intact(svg, slide_ordinal=ordinal, role="fallback"):
        _raise("svg_boundary", f"slide:{ordinal}/fallback", "fallback requires a validated SVG")
    return re.sub(r"<title>[^<]*</title>", "", svg.serialized)


def _presenter_overlays_html(
    slides: tuple[BundleSlide, ...],
    labels: Mapping[str, str],
) -> tuple[str, tuple[str, ...]]:
    overview_parts = [
        '<section id="idrt-presenter-overview" class="presenter-dialog overview-dialog" '
        'role="dialog" aria-modal="true" aria-labelledby="idrt-overview-title" hidden>',
        '<div class="presenter-card overview-card">',
        '<header class="presenter-dialog-header">',
        f'<h2 id="idrt-overview-title">{_escape(labels["overview_title"])}</h2>',
        f'<button type="button" data-presenter-close="overview">{_escape(labels["close"])}</button>',
        '</header><div class="overview-grid">',
    ]
    overview_ids: list[str] = []
    for ordinal, slide in enumerate(slides, start=1):
        thumbnail, svg_ids = _overview_svg(slide.fallback_svg, ordinal)
        overview_ids.extend(svg_ids)
        overview_parts.extend((
            f'<button type="button" data-overview-slide="{ordinal}" '
            f'aria-label="{_escape(labels["slide"])} {ordinal}: {_escape(slide.headline)}">',
            f'<span class="overview-number">{ordinal}</span>',
            f'<div class="overview-fallback">{thumbnail}</div>',
            f'<span class="overview-headline">{_escape(slide.headline)}</span>',
            '</button>',
        ))
    overview_parts.append('</div></div></section>')
    shortcuts = (
        ("Alt+O", labels["shortcut_overview"]),
        ("Alt+R", labels["shortcut_replay"]),
        ("Alt+D", labels["shortcut_demo"]),
        ("Alt+F", labels["shortcut_fullscreen"]),
        ("Alt+H", labels["shortcut_help"]),
        ("Escape", labels["shortcut_close"]),
    )
    help_parts = [
        '<section id="idrt-presenter-help" class="presenter-dialog help-dialog" '
        'role="dialog" aria-modal="true" aria-labelledby="idrt-help-title" hidden>',
        '<div class="presenter-card help-card">',
        '<header class="presenter-dialog-header">',
        f'<h2 id="idrt-help-title">{_escape(labels["help_title"])}</h2>',
        f'<button type="button" data-presenter-close="help">{_escape(labels["close"])}</button>',
        '</header><dl class="shortcut-list">',
    ]
    for shortcut, description in shortcuts:
        help_parts.append(
            f'<div><dt><kbd>{_escape(shortcut)}</kbd></dt><dd>{_escape(description)}</dd></div>'
        )
    help_parts.append('</dl></div></section>')
    cue = (
        '<div id="idrt-demo-cue" class="demo-cue" aria-hidden="true" inert hidden>'
        '<span class="demo-cue-ring"></span></div>'
    )
    return "".join((*overview_parts, *help_parts, cue)), tuple(overview_ids)


def bundle_deck(*, title: str, lang: str, slides: tuple[BundleSlide, ...], assets: RuntimeAssets) -> str:
    _text(title, "<title>", 500)
    if lang not in ("en", "ja"):
        _raise("language", "<deck>", "interactive deck language must be en or ja")
    asset_issues = _asset_issues(assets)
    if asset_issues:
        raise BundleValidationError(asset_issues)
    if not isinstance(slides, tuple) or not 1 <= len(slides) <= MAX_SLIDES:
        _raise("slide_limit", "<deck>", f"expected 1 through {MAX_SLIDES} slides")
    identifiers: set[str] = set()
    svg_ids: set[str] = set()
    records: list[dict] = []
    labels = _UI_TEXT[lang]
    # Fixed document/chrome plus presenter controls and the two closed overlays.
    # Overview thumbnails add one full fallback clone and four wrapper nodes each.
    estimated_dom = 61 + len(slides)
    for ordinal, slide in enumerate(slides, start=1):
        if not isinstance(slide, BundleSlide):
            _raise("slide_shape", f"slide:{ordinal}", "expected BundleSlide")
        slide_id = _identifier(slide.slide_id, f"slide:{ordinal}/slideId")
        if slide_id in identifiers:
            _raise("duplicate_id", f"slide:{ordinal}/slideId", "duplicate slide ID")
        identifiers.add(slide_id)
        _text(slide.headline, f"slide:{ordinal}/headline", 500)
        _text(slide.source, f"slide:{ordinal}/source", 500)
        _validate_summary(slide.static_summary, f"slide:{ordinal}/staticSummary")
        if slide.decision_range_message is not None:
            if (
                slide.scene is None
                or slide.decision_range_message != labels["no_decision_change"]
            ):
                _raise(
                    "display_shape",
                    f"slide:{ordinal}/decisionRangeMessage",
                    "decision-range message must be the compiler-owned localized text",
                )
        if (
            slide.static_summary["headline"] != slide.headline
            or slide.static_summary["source"] != slide.source
        ):
            _raise("summary_mismatch", f"slide:{ordinal}/staticSummary", "semantic summary must match slide chrome")
        if not _validated_svg_intact(
            slide.fallback_svg, slide_ordinal=ordinal, role="fallback"
        ):
            _raise("svg_boundary", f"slide:{ordinal}/fallback", "fallback must be a ValidatedSvg")
        if (slide.scene is None) != (slide.live_shell_svg is None):
            _raise("live_pair", f"slide:{ordinal}", "compiled scene and validated live shell must appear together")
        validated_display = _validate_display(slide.display, f"slide:{ordinal}/display")
        if validated_display is not None and validated_display["staticSummary"] != slide.static_summary:
            _raise("display_mismatch", f"slide:{ordinal}/display", "display and semantic summaries must be identical")
        if slide.scene is not None:
            if not isinstance(slide.scene, dict):
                _raise("scene_shape", f"slide:{ordinal}/scene", "compiled scene must be an object")
            if slide.scene.get("slideId") != slide_id:
                _raise("scene_shape", f"slide:{ordinal}/scene", "compiled scene slideId mismatch")
            if validated_display is None:
                _raise("display_shape", f"slide:{ordinal}/display", "scene slides require the closed display bridge")
            requires_ticks = (
                isinstance(slide.scene.get("initialEvaluation"), dict)
                and isinstance(slide.scene["initialEvaluation"].get("view"), dict)
                and slide.scene["initialEvaluation"]["view"].get("component") == "dot_plot"
            )
            if requires_ticks != (validated_display["axisTickLabels"] is not None):
                _raise("display_shape", f"slide:{ordinal}/display", "axis tick labels must match dot-plot presence")
            if ("decisionContract" in slide.scene) != (validated_display["thresholdText"] is not None):
                _raise("display_shape", f"slide:{ordinal}/display", "threshold text must match decision-contract presence")
        for svg, expected_role in (
            (slide.fallback_svg, "fallback"),
            (slide.live_shell_svg, "live-shell"),
        ):
            if svg is None:
                continue
            if not _validated_svg_intact(
                svg, slide_ordinal=ordinal, role=expected_role
            ):
                _raise("svg_boundary", f"slide:{ordinal}/svg", "SVG must come from validate_renderer_svg")
            overlap = svg_ids.intersection(svg.ids)
            if overlap:
                _raise("duplicate_id", f"slide:{ordinal}/svg", "duplicate global SVG ID")
            svg_ids.update(svg.ids)
        slide_elements = _estimated_slide_elements(slide)
        if slide_elements > MAX_DOM_ELEMENTS_PER_SLIDE:
            _raise("dom_limit", f"slide:{ordinal}", "generated slide exceeds preflight element limit")
        estimated_dom += slide_elements + 4 + slide.fallback_svg.element_count
        if estimated_dom > MAX_DOM_ELEMENTS:
            _raise("dom_limit", "<html>", "generated DOM exceeds preflight element limit")
        records.append({"slideId": slide_id, "scene": slide.scene, "display": slide.display})
    payload = {"version": 1, "kind": "interactive-deck", "lang": lang, "locale": {"en": "en-US", "ja": "ja-JP"}[lang], "slides": records}
    encoded = encode_envelope(payload)
    for ordinal, slide in enumerate(slides, start=1):
        if slide.scene is not None:
            _validate_scene_summary(
                slide.scene,
                slide.static_summary,
                slide.display,
                f"slide:{ordinal}/staticSummary",
            )
    css = assets.css.decode("utf-8")
    js = assets.js.decode("utf-8")
    csp = content_security_policy(assets)
    allowed_sources: dict[tuple[int, str], str] = {}
    presenter_overlays, overview_svg_ids = _presenter_overlays_html(slides, labels)
    overlap = svg_ids.intersection(overview_svg_ids)
    if overlap:
        _raise("duplicate_id", "<overview>", "overview SVG IDs collide with the slide registry")
    local_ids = {
        "idrt-skip",
        "idrt-deck-pages",
        "idrt-presenter-chrome",
        "idrt-presenter-status",
        "idrt-overlay-root",
        "idrt-presenter-overview",
        "idrt-overview-title",
        "idrt-presenter-help",
        "idrt-help-title",
        "idrt-demo-cue",
        "idrt-deck-data",
    } | svg_ids | set(overview_svg_ids)
    sections: list[str] = []
    dialogs: list[str] = []
    for ordinal, slide in enumerate(slides, start=1):
        page_id = f"idrt-page-{ordinal}"
        local_ids.update((page_id, f"idrt-heading-{ordinal}"))
        previous = f"idrt-page-{max(1, ordinal - 1)}"
        following = f"idrt-page-{min(len(slides), ordinal + 1)}"
        live = "" if slide.live_shell_svg is None else f'<div class="live-layer" hidden>{slide.live_shell_svg.serialized}</div>'
        interactive = slide.scene is not None
        controls = ""
        if interactive:
            controls = _controls_html(slide.scene, ordinal, labels)
            local_ids.update((
                f"idrt-status-{ordinal}",
                f"idrt-reset-{ordinal}",
                f"idrt-evidence-open-{ordinal}",
                f"idrt-static-toggle-{ordinal}",
                f"idrt-evidence-dialog-{ordinal}",
                f"idrt-evidence-title-{ordinal}",
                f"idrt-evidence-close-{ordinal}",
            ))
            for position, _control in enumerate(slide.scene["controls"], start=1):
                local_ids.update((
                    f"idrt-control-{ordinal}-{position}",
                    f"idrt-control-value-{ordinal}-{position}",
                ))
            resolved_view = slide.scene.get("initialEvaluation", {}).get("view")
            if isinstance(resolved_view, dict):
                if resolved_view.get("component") == "dot_plot":
                    tooltip_ids = [point["id"] for point in resolved_view["points"]]
                elif resolved_view.get("component") in ("bar_compare", "ranked_list"):
                    tooltip_ids = [item["id"] for item in resolved_view["items"]]
                elif resolved_view.get("component") == "recommendation_panel":
                    tooltip_ids = [band["id"] for band in slide.scene["model"]["bands"]]
                else:
                    tooltip_ids = []
                local_ids.update(f"idrt-tooltip-{ordinal}-{item_id}" for item_id in tooltip_ids)
            if slide.scene.get("type") in ("drilldown", "accordion"):
                local_ids.update(
                    f'idrt-panel-{ordinal}-{panel["id"]}'
                    for panel in slide.scene["states"]["panels"]
                )
            evidence = slide.scene.get("evidence", {})
            if evidence.get("sources"):
                local_ids.add(f"idrt-evidence-panel-sources-{ordinal}")
            if evidence.get("assumptions"):
                local_ids.add(f"idrt-evidence-panel-assumptions-{ordinal}")
            if evidence.get("sources") and evidence.get("assumptions"):
                local_ids.update((
                    f"idrt-evidence-tab-sources-{ordinal}",
                    f"idrt-evidence-tab-assumptions-{ordinal}",
                ))
            dialogs.append(_evidence_dialog_html(
                slide.scene, ordinal, allowed_sources, labels
            ))
        section_runtime = (' data-runtime="pending" data-scene-type="' + _escape(slide.scene["type"]) + '"') if interactive else ""
        if slide.visual_layout is not None:
            if slide.visual_layout != "rank_bridge" or not interactive or slide.scene.get("initialEvaluation", {}).get("view", {}).get("component") != "ranked_list":
                _raise("visual_layout", f"slide:{ordinal}", "unsupported presentation modifier")
            section_runtime += ' data-visual-layout="rank_bridge"'
        sections.append(
            f'<section id="{page_id}" class="slide" data-slide-id="{_escape(slide.slide_id)}"{section_runtime}>'
            '<div class="frame">'
            f'<div class="fallback-layer">{_document_fallback_svg(slide.fallback_svg, ordinal)}</div>{live}</div>'
            f'<div class="semantic-scene">{_summary_html(slide.static_summary, ordinal=ordinal, interactive=interactive, decision_range_message=slide.decision_range_message)}'
            f'{controls}<p class="semantic-source">{_escape(slide.source)}</p></div>'
            f'<nav class="nojs-page-links" aria-label="{_escape(labels["slide_links"])}">'
            f'<a href="#{previous}">{_escape(labels["previous"])}</a>'
            f'<a href="#{following}">{_escape(labels["next"])}</a></nav></section>'
        )
    page_links = "".join(
        f'<a href="#idrt-page-{index}" data-page-index="{index}">{index}</a>'
        for index in range(1, len(slides) + 1)
    )
    presenter_links = (
        f'<a href="#idrt-page-1" data-nav-action="previous">{_escape(labels["previous"])}</a>'
        + page_links
        + f'<a href="#idrt-page-{len(slides)}" data-nav-action="next">{_escape(labels["next"])}</a>'
    )
    presenter_controls = "".join(
        f'<button type="button" data-presenter-action="{action}"'
        + (' aria-pressed="false"' if action in ("demo", "fullscreen") else "")
        + f'>{_escape(labels[action])}</button>'
        for action in ("overview", "replay", "demo", "fullscreen", "help")
    )
    document = (
        '<!DOCTYPE html>\n'
        f'<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{_escape(csp)}">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="referrer" content="no-referrer">\n'
        f'<title>{_escape(title)}</title>\n<style>{css}</style>\n</head>\n<body>\n'
        f'<a id="idrt-skip" class="skip-link" href="#idrt-deck-pages">{_escape(labels["skip"])}</a>\n'
        '<main id="idrt-deck-pages">\n' + "\n".join(sections) + '\n</main>\n'
        f'<nav id="idrt-presenter-chrome" class="presenter-chrome" aria-label="{_escape(labels["slide_navigation"])}">{presenter_links}{presenter_controls}</nav>\n'
        f'<p id="idrt-presenter-status" class="visually-hidden" aria-live="polite" aria-atomic="true" aria-label="{_escape(labels["presenter_status"])}"></p>\n'
        '<div id="idrt-overlay-root">' + "".join(dialogs) + presenter_overlays + '</div>\n'
        f'<div id="idrt-deck-data" hidden data-encoding="base64url-json-v1">{encoded}</div>\n'
        f'<script>{js}</script>\n</body>\n</html>\n'
    )
    if len(document.encode("utf-8")) > MAX_HTML_BYTES:
        _raise("html_limit", "<html>", "final HTML exceeds 48 MiB")
    assert_self_contained(document, assets=assets, allowed_sources=allowed_sources, local_ids=local_ids)
    return document
