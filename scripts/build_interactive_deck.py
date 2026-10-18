#!/usr/bin/env python3
"""Build a self-contained interactive companion deck from one manifest."""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext
from fractions import Fraction
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import tempfile

if __package__:
    from .deck_core import normalize_manifest
    from . import render_slide_spec
    from .deck_bundle import (
        BundleIssue, BundleSlide, BundleValidationError, RuntimeAssets,
        bundle_deck, load_runtime_assets, validate_renderer_svg,
    )
    from .interactive_contract import (
        Location, SceneValidationError, canonical_decimal, format_value,
        round_scaled, validate_interactive_slide_ids,
    )
    from .interactive_scene import LocatedDocument, compile_scene, serialize_compiled_scene
else:
    # Isolated direct execution (`python -I /abs/path/to/script.py`) omits the
    # script directory from sys.path.  Register a narrow file-backed package
    # in sys.modules so sibling modules can use their tested relative imports
    # without mutating process-wide import search paths.
    import importlib
    import sys
    import types

    _PACKAGE = "_interactive_deck_scripts"
    package = types.ModuleType(_PACKAGE)
    package.__path__ = [str(Path(__file__).resolve().parent)]
    package.__package__ = _PACKAGE
    sys.modules.setdefault(_PACKAGE, package)
    deck_core = importlib.import_module(_PACKAGE + ".deck_core")
    render_slide_spec = importlib.import_module(_PACKAGE + ".render_slide_spec")
    deck_bundle_module = importlib.import_module(_PACKAGE + ".deck_bundle")
    contract_module = importlib.import_module(_PACKAGE + ".interactive_contract")
    scene_module = importlib.import_module(_PACKAGE + ".interactive_scene")
    normalize_manifest = deck_core.normalize_manifest
    BundleIssue = deck_bundle_module.BundleIssue
    BundleSlide = deck_bundle_module.BundleSlide
    BundleValidationError = deck_bundle_module.BundleValidationError
    RuntimeAssets = deck_bundle_module.RuntimeAssets
    bundle_deck = deck_bundle_module.bundle_deck
    load_runtime_assets = deck_bundle_module.load_runtime_assets
    validate_renderer_svg = deck_bundle_module.validate_renderer_svg
    Location = contract_module.Location
    SceneValidationError = contract_module.SceneValidationError
    canonical_decimal = contract_module.canonical_decimal
    format_value = contract_module.format_value
    round_scaled = contract_module.round_scaled
    validate_interactive_slide_ids = contract_module.validate_interactive_slide_ids
    compile_scene = scene_module.compile_scene
    LocatedDocument = scene_module.LocatedDocument
    serialize_compiled_scene = scene_module.serialize_compiled_scene


MAX_MANIFEST_BYTES = 256 * 1024
MAX_SPEC_BYTES = 1024 * 1024
MAX_SCENE_BYTES = 256 * 1024
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_SLIDES = 64
MAX_DEPTH = 32
MAX_NODES = 250_000
MAX_STRINGS = 100_000
MAX_STRING_BYTES = 8 * 1024 * 1024
MAX_FALLBACK_WORK_PER_SLIDE = 4_096
MAX_FALLBACK_WORK_PER_DECK = 32_768
MAX_ESTIMATED_FALLBACK_ELEMENTS_PER_SLIDE = 8_000
MAX_ESTIMATED_FALLBACK_ELEMENTS_PER_DECK = 40_000
MAX_ACCEPTED_STATES_PER_DECK = 65_536
STATIC_SHELL_ELEMENT_ALLOWANCE = 32
LIVE_SHELL_ELEMENT_ALLOWANCE = 256
MAX_EXACT_DECIMAL_TOKEN = 128
MAX_EXACT_DECIMAL_ADJUSTED_EXPONENT = 308
_RUNTIME_SCENE_TYPES = frozenset((
    "evidence_only", "state_toggle", "slider_model", "score_model",
    "drilldown", "accordion",
))
_RUNTIME_MODEL_KINDS = frozenset((
    "none", "linear", "lookup", "state_map", "piecewise", "score_sum",
    "operation_graph",
))
_RUNTIME_VIEW_COMPONENTS = frozenset((
    "bar_compare", "ranked_list", "dot_plot", "recommendation_panel",
))
_RUNTIME_CONTROL_KINDS = frozenset(("range", "segmented", "toggle", "select"))
_RUNTIME_NUMERIC_MODEL_KINDS = frozenset((
    "linear", "lookup", "piecewise", "operation_graph",
))
_CHROMELESS_PATTERNS = frozenset(("cover", "section_divider", "end_cover"))
_FALLBACK_COMMON_KEYS = frozenset((
    "pattern", "theme", "layout", "palette", "headline", "subline",
    "classification", "exhibit_label", "annotation", "footnotes", "source",
    "page_number", "lang", "label", "notes", "refs",
))
_FALLBACK_PATTERN_KEYS = {
    "cover": frozenset(("title", "subtitle", "presenter", "date", "classification", "presentation")),
    "scatter": frozenset(("x_axis", "y_axis", "points", "x_zero", "y_zero", "model_context")),
    "distribution": frozenset(("bins", "unit", "highlight", "commentary")),
    "small_multiples": frozenset(("charts", "columns", "unit")),
    "waterfall": frozenset(("start", "drivers", "end_label", "unit")),
    "gap": frozenset(("items", "gap_label", "unit", "value_domain", "baseline")),
    "before_after": frozenset(("pairs", "before_label", "after_label", "unit", "value_domain", "baseline")),
    "time_series": frozenset(("x_labels", "series", "unit")),
    "benchmark_table": frozenset(("columns", "rows", "leaders")),
    "summary_strip": frozenset(("blocks", "focus_block", "model_context", "presentation")),
    "process_flow": frozenset(("steps", "highlight")),
    "funnel": frozenset(("stages", "unit")),
    "heatmap": frozenset(("rows", "columns", "values", "unit", "diverging")),
    "gantt": frozenset(("periods", "bars", "gates")),
    "kpi_scorecard": frozenset(("columns", "metrics")),
    "two_by_two": frozenset(("x_axis", "y_axis", "quadrants", "points", "focus_quadrant", "legend_title")),
    "section_divider": frozenset(("section_number", "title", "subtitle", "sections", "classification")),
    "end_cover": frozenset(("title", "subtitle", "contact", "presenter", "date", "classification")),
    "agenda": frozenset(("items", "current")),
    "bullet_list": frozenset(("bullets", "columns", "model_context")),
    "closing": frozenset(("takeaways", "next_steps", "call_to_action", "presentation")),
    "quote": frozenset(("text", "attribution", "context")),
}
_FALLBACK_REQUIRED_KEYS = {
    "cover": frozenset(("pattern", "title")),
    "scatter": frozenset(("pattern", "headline", "x_axis", "y_axis", "points")),
    "distribution": frozenset(("pattern", "headline", "bins")),
    "small_multiples": frozenset(("pattern", "headline", "charts")),
    "waterfall": frozenset(("pattern", "headline", "start", "drivers")),
    "gap": frozenset(("pattern", "headline", "items")),
    "before_after": frozenset(("pattern", "headline", "pairs")),
    "time_series": frozenset(("pattern", "headline", "x_labels", "series")),
    "benchmark_table": frozenset(("pattern", "headline", "columns", "rows")),
    "summary_strip": frozenset(("pattern", "headline", "blocks")),
    "process_flow": frozenset(("pattern", "headline", "steps")),
    "funnel": frozenset(("pattern", "headline", "stages")),
    "heatmap": frozenset(("pattern", "headline", "rows", "columns", "values")),
    "gantt": frozenset(("pattern", "headline", "periods", "bars")),
    "kpi_scorecard": frozenset(("pattern", "headline", "metrics")),
    "two_by_two": frozenset(("pattern", "headline", "x_axis", "y_axis", "points")),
    "section_divider": frozenset(("pattern", "section_number", "title")),
    "end_cover": frozenset(("pattern",)),
    "agenda": frozenset(("pattern", "headline", "items")),
    "bullet_list": frozenset(("pattern", "headline", "bullets")),
    "closing": frozenset(("pattern", "headline", "next_steps")),
    "quote": frozenset(("pattern", "headline", "text")),
}
_FALLBACK_ADAPTER_TOP_KEYS = {
    "scatter": frozenset(("interactive_result", "domain_reason")),
    "gap": frozenset(("quantity", "interactive_result")),
    "before_after": frozenset(("quantity", "interactive_result")),
    "bullet_list": frozenset(("quantity", "unit", "value_domain", "baseline")),
    "summary_strip": frozenset(("interactive_result",)),
    "closing": frozenset(("interactive_result",)),
}
_FALLBACK_COLLECTIONS = {
    "waterfall": {"drivers": (20, frozenset(("label", "value")))},
    "gap": {"items": (64, frozenset(("label", "value", "emphasis", "value_text")))},
    "before_after": {"pairs": (32, frozenset(("label", "before", "after", "unit", "before_text", "after_text", "delta_text")))},
    "time_series": {"series": (12, frozenset(("label", "values")))},
    "benchmark_table": {"rows": (32, frozenset(("label", "values")))},
    "summary_strip": {"blocks": (12, frozenset(("metric", "claim", "proof", "implication")))},
    "process_flow": {"steps": (16, frozenset(("label", "detail", "owner", "duration")))},
    "funnel": {"stages": (32, frozenset(("label", "value")))},
    "gantt": {
        "bars": (64, frozenset(("label", "start", "end", "highlight", "note"))),
        "gates": (32, frozenset(("label", "period"))),
    },
    "kpi_scorecard": {"metrics": (32, frozenset(("label", "value", "target", "trend", "status")))},
    "two_by_two": {"points": (64, frozenset(("label", "x", "y", "emphasis")))},
    "agenda": {"items": (32, frozenset(("title", "detail")))},
    "bullet_list": {"bullets": (64, frozenset(("text", "sub", "emphasis")))},
    "closing": {"next_steps": (32, frozenset(("action", "owner", "timing")))},
    "distribution": {"bins": (64, frozenset(("label", "value")))},
    "small_multiples": {"charts": (32, frozenset(("label", "values", "emphasis")))},
    "scatter": {"points": (64, frozenset(("label", "x", "y", "emphasis")))},
}
_FALLBACK_LIST_LIMITS = {
    "x_labels": 128, "columns": 32, "rows": 64, "values": 64,
    "periods": 128, "quadrants": 4, "sections": 32, "contact": 4,
    "takeaways": 4, "footnotes": 2, "refs": 20,
}
_FALLBACK_OBJECT_KEYS = {
    "start": frozenset(("label", "value")),
    "x_axis": frozenset(("label", "unit", "quantity", "domain", "tick_labels", "low", "high")),
    "y_axis": frozenset(("label", "unit", "quantity", "domain", "tick_labels", "low", "high")),
    "commentary": frozenset(("title", "points")),
    "interactive_result": frozenset((
        "quantity", "value", "classification", "decision_status",
        "recommendation", "operator", "threshold",
    )),
}
_FALLBACK_TEXT_KEYS = frozenset((
    "headline", "subline", "classification", "exhibit_label", "annotation", "source", "lang",
    "title", "subtitle", "presenter", "date", "end_label", "gap_label", "before_label",
    "after_label", "unit", "text", "attribution", "context", "call_to_action", "legend_title",
    "label", "notes",
))
_SEMANTIC_MARKERS = {
    "en": {
        "current": "Current", "emphasized": "Emphasized", "focused": "Focused",
        "highlighted": "Highlighted", "focused_quadrant": "Focused quadrant", "leader": "Leader",
        "target": "Target: ",
    },
    "ja": {
        "current": "現在", "emphasized": "強調", "focused": "注目",
        "highlighted": "ハイライト", "focused_quadrant": "注目象限", "leader": "優位",
        "target": "目標：",
    },
}
MAX_FALLBACK_NUMBER_MAGNITUDE = Decimal("1000000000000")
MAX_FALLBACK_TEXT_SCALARS = 500
_RAW_DECIMAL = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$")
_JSON_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


@dataclass(frozen=True)
class CompiledDeck:
    title: str
    lang: str
    slides: tuple[BundleSlide, ...]
    author_records: tuple[object, ...]


@dataclass
class _JsonBudget:
    nodes: int = 0
    strings: int = 0
    string_bytes: int = 0


@dataclass(frozen=True)
class _RetainedInput:
    path: Path
    data: bytes


class _DuplicateJsonKey(ValueError):
    def __init__(self, key: str):
        self.key = key


class _InvalidJsonNumber(ValueError):
    pass


def _fail(code: str, location: str, message: str) -> None:
    raise BundleValidationError((BundleIssue(code, location, message),))


def _bounded_bytes(path: Path, limit: int, code: str) -> bytes:
    try:
        file_status = path.stat()
    except OSError as error:
        _fail("missing_file", str(path), type(error).__name__)
    if not stat.S_ISREG(file_status.st_mode):
        _fail("input_type", str(path), "input must be a regular file")
    if file_status.st_size > limit:
        _fail(code, str(path), f"input exceeds {limit} bytes")
    try:
        with path.open("rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                _fail("input_type", str(path), "input must be a regular file")
            data = handle.read(limit + 1)
    except OSError as error:
        _fail("read_error", str(path), type(error).__name__)
    if len(data) > limit:
        _fail(code, str(path), f"input exceeds {limit} bytes")
    return data


class _RootReader:
    """Open canonical in-root inputs once through no-follow directory handles."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._fd = -1
        if (
            os.name != "posix"
            or not hasattr(os, "O_NOFOLLOW")
            or not hasattr(os, "O_DIRECTORY")
            or os.open not in getattr(os, "supports_dir_fd", set())
        ):
            _fail("input_boundary", str(root), "secure no-follow file loading is unavailable")
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        try:
            current = os.open(os.path.sep, flags)
            for component in self.root.parts[1:]:
                following = os.open(component, flags, dir_fd=current)
                os.close(current)
                current = following
            self._fd = current
        except OSError as error:
            if "current" in locals():
                try:
                    os.close(current)
                except OSError:
                    pass
            _fail("read_error", str(root), type(error).__name__)

    def close(self) -> None:
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self) -> "_RootReader":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def read(self, path: Path, limit: int, code: str) -> bytes:
        try:
            relative = Path(path).relative_to(self.root)
        except ValueError:
            _fail("path_escape", str(path), "resolved path must remain inside the manifest root")
        if not relative.parts:
            _fail("input_type", str(path), "input must be a regular file")
        directory_fd = os.dup(self._fd)
        file_fd = -1
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            for component in relative.parts[:-1]:
                following = os.open(component, directory_flags, dir_fd=directory_fd)
                os.close(directory_fd)
                directory_fd = following
            file_fd = os.open(relative.parts[-1], file_flags, dir_fd=directory_fd)
            before = os.fstat(file_fd)
            if not stat.S_ISREG(before.st_mode):
                _fail("input_type", str(path), "input must be a regular file")
            if before.st_size > limit:
                _fail(code, str(path), f"input exceeds {limit} bytes")
            chunks: list[bytes] = []
            remaining = limit + 1
            while remaining:
                chunk = os.read(file_fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            after = os.fstat(file_fd)
            identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or len(data) != after.st_size:
                _fail("read_error", str(path), "input changed during its bounded read")
        except BundleValidationError:
            raise
        except OSError as error:
            _fail("read_error", str(path), type(error).__name__)
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            os.close(directory_fd)
        if len(data) > limit:
            _fail(code, str(path), f"input exceeds {limit} bytes")
        return data


def _walk_input(value: object, location: str, budget: _JsonBudget | None = None) -> None:
    usage = budget if budget is not None else _JsonBudget()
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if depth > MAX_DEPTH:
            _fail("json_depth", location, f"JSON depth exceeds {MAX_DEPTH}")
        usage.nodes += 1
        if usage.nodes > MAX_NODES:
            _fail("json_nodes", location, f"JSON nodes exceed {MAX_NODES}")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    _fail("json_key", location, "JSON object key must be text")
                usage.nodes += 1
                usage.strings += 1
                try:
                    usage.string_bytes += len(key.encode("utf-8", "strict"))
                except UnicodeError:
                    _fail("json_unicode", location, "invalid Unicode key")
                stack.append((child, depth + 1))
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in reversed(item))
        elif isinstance(item, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in item):
                _fail("json_unicode", location, "lone surrogate is forbidden")
            usage.strings += 1
            usage.string_bytes += len(item.encode("utf-8", "strict"))
        elif item is None or isinstance(item, (bool, int, Decimal)):
            pass
        elif isinstance(item, float):
            if not math.isfinite(item):
                _fail("json_number", location, "JSON numbers must be finite")
        else:
            _fail("json_type", location, f"unsupported JSON value {type(item).__name__}")
        if usage.nodes > MAX_NODES:
            _fail("json_nodes", location, f"JSON nodes exceed {MAX_NODES}")
        if usage.strings > MAX_STRINGS:
            _fail("json_strings", location, f"JSON strings exceed {MAX_STRINGS}")
        if usage.string_bytes > MAX_STRING_BYTES:
            _fail("json_string_bytes", location, "JSON string bytes exceed 8 MiB")


def _exact_decimal(token: str) -> Decimal:
    """Parse one JSON number without permitting exponent-amplification work."""
    if len(token) > MAX_EXACT_DECIMAL_TOKEN:
        raise _InvalidJsonNumber(token)
    try:
        value = Decimal(token)
        adjusted = value.adjusted()
    except (DecimalException, ValueError):
        raise _InvalidJsonNumber(token) from None
    if (
        not value.is_finite()
        or adjusted < -MAX_EXACT_DECIMAL_ADJUSTED_EXPONENT
        or adjusted > MAX_EXACT_DECIMAL_ADJUSTED_EXPONENT
    ):
        raise _InvalidJsonNumber(token)
    return value


def _finite_json_number(token: str) -> None:
    """Reject numeric tokens that the ordinary manifest decoder would widen."""
    if len(token) > MAX_EXACT_DECIMAL_TOKEN:
        raise _InvalidJsonNumber(token)
    try:
        value = float(token)
    except (OverflowError, ValueError):
        raise _InvalidJsonNumber(token) from None
    if not math.isfinite(value):
        raise _InvalidJsonNumber(token)


class _JsonPreflight:
    """Bound JSON structure and decoded strings before materializing a tree."""

    def __init__(
        self,
        text: str,
        location: str,
        budget: _JsonBudget,
        number_hook,
    ):
        self.text = text
        self.location = location
        self.budget = budget
        self.number_hook = number_hook
        self.index = 0

    def run(self) -> None:
        self._space()
        self._value(0)
        self._space()
        if self.index != len(self.text):
            _fail("json_shape", self.location, "invalid bounded JSON")

    def _space(self) -> None:
        while self.index < len(self.text) and self.text[self.index] in " \t\r\n":
            self.index += 1

    def _limits(self) -> None:
        if self.budget.nodes > MAX_NODES:
            _fail("json_nodes", self.location, f"JSON nodes exceed {MAX_NODES}")
        if self.budget.strings > MAX_STRINGS:
            _fail("json_strings", self.location, f"JSON strings exceed {MAX_STRINGS}")
        if self.budget.string_bytes > MAX_STRING_BYTES:
            _fail("json_string_bytes", self.location, "JSON string bytes exceed 8 MiB")

    def _node(self, depth: int) -> None:
        if depth > MAX_DEPTH:
            _fail("json_depth", self.location, f"JSON depth exceeds {MAX_DEPTH}")
        self.budget.nodes += 1
        self._limits()

    def _string(self) -> str:
        if self.index >= len(self.text) or self.text[self.index] != '"':
            _fail("json_shape", self.location, "invalid bounded JSON")
        try:
            value, following = json.decoder.scanstring(self.text, self.index + 1, True)
        except (UnicodeError, ValueError):
            _fail("json_shape", self.location, "invalid bounded JSON")
        self.index = following
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            _fail("json_unicode", self.location, "lone surrogate is forbidden")
        try:
            encoded_size = len(value.encode("utf-8", "strict"))
        except UnicodeError:
            _fail("json_unicode", self.location, "invalid Unicode string")
        self.budget.strings += 1
        self.budget.string_bytes += encoded_size
        self._limits()
        return value

    def _value(self, depth: int) -> None:
        self._space()
        self._node(depth)
        if self.index >= len(self.text):
            _fail("json_shape", self.location, "invalid bounded JSON")
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
        match = _JSON_NUMBER.match(self.text, self.index)
        if match is None:
            _fail("json_shape", self.location, "invalid bounded JSON")
        number = match.group(0)
        self.index = match.end()
        self._delimiter()
        if self.number_hook is not None:
            try:
                self.number_hook(number)
            except _InvalidJsonNumber:
                _fail("json_number", self.location, "JSON number exceeds the exact decimal bound")

    def _delimiter(self) -> None:
        if self.index < len(self.text) and self.text[self.index] not in " \t\r\n,]}":
            _fail("json_shape", self.location, "invalid bounded JSON")

    def _object(self, depth: int) -> None:
        self.index += 1
        self._space()
        seen: set[str] = set()
        if self.index < len(self.text) and self.text[self.index] == "}":
            self.index += 1
            return
        while True:
            self.budget.nodes += 1
            self._limits()
            key = self._string()
            if key in seen:
                _fail("duplicate_json_key", self.location, "duplicate JSON key")
            seen.add(key)
            self._space()
            if self.index >= len(self.text) or self.text[self.index] != ":":
                _fail("json_shape", self.location, "invalid bounded JSON")
            self.index += 1
            self._value(depth + 1)
            self._space()
            if self.index >= len(self.text):
                _fail("json_shape", self.location, "invalid bounded JSON")
            separator = self.text[self.index]
            self.index += 1
            if separator == "}":
                return
            if separator != ",":
                _fail("json_shape", self.location, "invalid bounded JSON")
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
                _fail("json_shape", self.location, "invalid bounded JSON")
            separator = self.text[self.index]
            self.index += 1
            if separator == "]":
                return
            if separator != ",":
                _fail("json_shape", self.location, "invalid bounded JSON")
            self._space()


def _strict_json_bytes(
    data: bytes,
    location: str,
    *,
    exact_numbers: bool,
    budget: _JsonBudget | None = None,
) -> dict:
    try:
        text = data.decode("utf-8", "strict")
    except UnicodeDecodeError:
        _fail("json_utf8", location, "input must be strict UTF-8")
    if text.startswith("\ufeff"):
        _fail("json_utf8", location, "UTF-8 BOM is not accepted")
    usage = budget if budget is not None else _JsonBudget()
    _JsonPreflight(
        text,
        location,
        usage,
        _exact_decimal if exact_numbers else _finite_json_number,
    ).run()

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise _DuplicateJsonKey(key)
            result[key] = value
        return result

    kwargs = {
        "object_pairs_hook": pairs,
        "parse_constant": lambda value: (_ for _ in ()).throw(ValueError(value)),
    }
    if exact_numbers:
        kwargs.update(parse_int=_exact_decimal, parse_float=_exact_decimal)
    try:
        parsed = json.loads(text, **kwargs)
    except _DuplicateJsonKey as error:
        _fail("duplicate_json_key", location, "duplicate JSON key")
    except _InvalidJsonNumber:
        _fail("json_number", location, "JSON number exceeds the exact decimal bound")
    except (json.JSONDecodeError, ValueError, RecursionError):
        _fail("json_shape", location, "invalid bounded JSON")
    if not isinstance(parsed, dict):
        _fail("json_shape", location, "top-level JSON value must be an object")
    return parsed


def _strict_json(
    path: Path,
    *,
    byte_limit: int,
    exact_numbers: bool,
    budget: _JsonBudget | None = None,
) -> dict:
    data = _bounded_bytes(path, byte_limit, "input_limit")
    return _strict_json_bytes(data, str(path), exact_numbers=exact_numbers, budget=budget)


def _confined_file(root: Path, raw: object, location: str) -> Path:
    if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
        _fail("path_escape", location, "path must be a nonempty relative path")
    path = Path(raw)
    windows = PureWindowsPath(raw)
    if path.is_absolute() or windows.is_absolute() or ".." in path.parts or ".." in windows.parts:
        _fail("path_escape", location, "absolute and parent-traversal paths are forbidden")
    try:
        resolved = (root / path).resolve(strict=True)
    except (OSError, RuntimeError):
        _fail("missing_file", location, "path does not resolve to a file")
    if not resolved.is_relative_to(root):
        _fail("path_escape", location, "resolved path must remain inside the manifest root")
    return resolved


def _preflight_paths(
    manifest: dict,
    manifest_path: Path,
    reader: _RootReader,
) -> tuple[list[_RetainedInput], list[_RetainedInput | None]]:
    slides = manifest.get("slides")
    if not isinstance(slides, list) or not 1 <= len(slides) <= MAX_SLIDES:
        _fail("slide_limit", str(manifest_path) + "/slides", f"expected 1 through {MAX_SLIDES} slides")
    root = manifest_path.resolve().parent
    specs: list[_RetainedInput] = []
    scenes: list[_RetainedInput | None] = []
    aggregate = 0
    for index, entry in enumerate(slides):
        location = f"{manifest_path}/slides/{index}"
        if isinstance(entry, str):
            spec_raw, scene_raw = entry, None
        elif isinstance(entry, dict):
            spec_raw, scene_raw = entry.get("spec"), entry.get("scene")
        else:
            _fail("manifest_shape", location, "slide must be a path string or object")
        spec_path = _confined_file(root, spec_raw, location + "/spec")
        spec_data = reader.read(spec_path, MAX_SPEC_BYTES, "input_limit")
        specs.append(_RetainedInput(spec_path, spec_data))
        aggregate += len(spec_data)
        if scene_raw is None:
            scenes.append(None)
        else:
            scene_path = _confined_file(root, scene_raw, location + "/scene")
            scene_data = reader.read(scene_path, MAX_SCENE_BYTES, "input_limit")
            scenes.append(_RetainedInput(scene_path, scene_data))
            aggregate += len(scene_data)
        if aggregate > MAX_INPUT_BYTES:
            _fail("input_limit", str(manifest_path), "aggregate spec and scene input exceeds 32 MiB")
    return specs, scenes


def _renderer_copy(value):
    if isinstance(value, Decimal):
        try:
            if (
                not value.is_finite()
                or value.adjusted() < -MAX_EXACT_DECIMAL_ADJUSTED_EXPONENT
                or value.adjusted() > MAX_EXACT_DECIMAL_ADJUSTED_EXPONENT
            ):
                raise _InvalidJsonNumber
            if value == value.to_integral_value():
                return int(value)
            renderer_value = float(value)
        except (DecimalException, OverflowError, ValueError, _InvalidJsonNumber):
            _fail("json_number", "<spec>", "JSON number exceeds the renderer conversion bound")
        if not math.isfinite(renderer_value):
            _fail("json_number", "<spec>", "JSON number exceeds the renderer conversion bound")
        return renderer_value
    if isinstance(value, dict):
        return {key: _renderer_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_renderer_copy(item) for item in value]
    return value


def _fallback_integer(value: object) -> int | None:
    """Return a bounded renderer index without treating booleans as numbers."""
    if type(value) is int:
        return value
    if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        try:
            return int(value)
        except (OverflowError, ValueError):
            return None
    return None


def _renderer_spec_copy(spec: dict) -> dict:
    """Convert exact numbers while preserving the renderer's integer slots."""
    exact = copy.deepcopy(spec)
    pattern = exact.get("pattern")

    def integer(mapping: dict, key: str) -> None:
        if key in mapping:
            value = _fallback_integer(mapping[key])
            if value is not None:
                mapping[key] = value

    if pattern in ("bullet_list", "kpi_scorecard", "small_multiples"):
        integer(exact, "columns")
    if pattern in ("gap", "distribution", "process_flow"):
        integer(exact, "highlight")
    if pattern == "summary_strip":
        integer(exact, "focus_block")
    if pattern == "benchmark_table":
        for pair in exact.get("leaders", []):
            if isinstance(pair, list):
                for index in range(len(pair)):
                    value = _fallback_integer(pair[index])
                    if value is not None:
                        pair[index] = value
    if pattern == "gantt":
        for bar in exact.get("bars", []):
            if isinstance(bar, dict):
                integer(bar, "start")
                integer(bar, "end")
        for gate in exact.get("gates", []):
            if isinstance(gate, dict):
                integer(gate, "period")
    if pattern == "two_by_two":
        integer(exact, "focus_quadrant")
    if pattern == "section_divider":
        integer(exact, "section_number")
    if pattern == "agenda":
        integer(exact, "current")
    rendered = _renderer_copy(exact)
    assert isinstance(rendered, dict)
    return rendered


def _fallback_shape(condition: bool, location: str) -> None:
    if not condition:
        _fail("fallback_shape", location, "fallback spec violates the closed renderer contract")


def _fallback_work(value: object) -> int:
    """Conservatively bound traversal, wrapping and emitted-node work."""
    work = 0
    stack = [value]
    while stack:
        item = stack.pop()
        work += 1
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str):
            # The legacy wrapper repeatedly measures prefixes. Charge every
            # authored scalar so dense, narrow layouts are rejected before
            # their superlinear wrapping path can run.
            work += len(item)
    return work


def _fallback_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return False
    try:
        if isinstance(value, Decimal):
            return value.is_finite() and abs(value) <= MAX_FALLBACK_NUMBER_MAGNITUDE
        return math.isfinite(value) and abs(value) <= float(MAX_FALLBACK_NUMBER_MAGNITUDE)
    except (OverflowError, TypeError, ValueError):
        return False


def _fallback_text(value: object, *, nonempty: bool = True) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= MAX_FALLBACK_TEXT_SCALARS
        and (bool(value.strip()) if nonempty else True)
    )


def _estimate_fallback_elements(spec: dict) -> int:
    """Conservatively estimate renderer elements before string/XML work."""
    pattern = spec.get("pattern")
    count = STATIC_SHELL_ELEMENT_ALLOWANCE
    sizes = {
        "waterfall": len(spec.get("drivers", [])),
        "gap": len(spec.get("items", [])),
        "before_after": len(spec.get("pairs", [])),
        "time_series": len(spec.get("series", [{}])[0].get("values", [])) if spec.get("series") else 0,
        "summary_strip": len(spec.get("blocks", [])),
        "process_flow": len(spec.get("steps", [])),
        "funnel": len(spec.get("stages", [])),
        "kpi_scorecard": len(spec.get("metrics", [])),
        "two_by_two": len(spec.get("points", [])),
        "scatter": len(spec.get("points", [])),
        "distribution": len(spec.get("bins", [])),
        "small_multiples": len(spec.get("charts", [])),
        "agenda": len(spec.get("items", [])),
        "bullet_list": len(spec.get("bullets", [])),
    }
    n = sizes.get(pattern, 0)
    if pattern == "waterfall":
        count += 8 * n + 18
    elif pattern == "gap":
        count += 7 * n + 2
    elif pattern == "before_after":
        count += 12 * n + 7
    elif pattern == "time_series":
        count += 5 * n + 6
    elif pattern == "benchmark_table":
        columns = len(spec.get("columns", []))
        rows = len(spec.get("rows", []))
        count += 4 * columns + 1 + rows * (6 + 5 * columns)
    elif pattern == "summary_strip":
        count += 26 * n
    elif pattern == "process_flow":
        count += (19 if spec.get("theme") == "executive" else 14) * n
    elif pattern == "funnel":
        count += 9 * n
    elif pattern == "heatmap":
        columns = len(spec.get("columns", []))
        rows = len(spec.get("rows", []))
        count += 3 * columns + rows * (4 + 3 * columns)
    elif pattern == "gantt":
        count += 3 * len(spec.get("periods", [])) + 8 * len(spec.get("bars", [])) + 3 * len(spec.get("gates", [])) + 2
    elif pattern == "kpi_scorecard":
        count += 9 * n
    elif pattern == "two_by_two":
        count += (26 + 9 * n) if spec.get("theme") == "executive" else (23 + 3 * n)
    elif pattern == "scatter":
        count += 14 + 3 * n
    elif pattern == "distribution":
        count += 7 * n + 28
    elif pattern == "small_multiples":
        count += 9 * n
    elif pattern == "cover":
        count += 16
    elif pattern == "section_divider":
        count += 14 + len(spec.get("sections", []))
    elif pattern == "end_cover":
        count += 24
    elif pattern == "agenda":
        count += 8 * n + 1
    elif pattern == "bullet_list":
        count += 12 * n + 6 * sum(len(item.get("sub", [])) for item in spec.get("bullets", []) if isinstance(item, dict))
    elif pattern == "closing":
        count += 4 + 10 * len(spec.get("takeaways", [])) + 7 * len(spec.get("next_steps", []))
    elif pattern == "quote":
        count += 14
    if "model_context" in spec:
        count += 64
    # Wrapped text can emit more nodes than the cardinality formula. The
    # traversal estimate charges by 32-character chunks, then this multiplier
    # safely covers wrapped text plus title attributes without parsing SVG.
    return max(count, STATIC_SHELL_ELEMENT_ALLOWANCE + 4 * _fallback_work(spec))


def _validate_fallback_spec(spec: object, location: str, *, scene_adapter: bool = False) -> int:
    """Validate one legacy-renderer input before any renderer/XML work."""
    _fallback_shape(isinstance(spec, dict), location)
    assert isinstance(spec, dict)
    pattern = spec.get("pattern")
    _fallback_shape(isinstance(pattern, str) and pattern in _FALLBACK_PATTERN_KEYS, location + "/pattern")
    assert isinstance(pattern, str)
    allowed = _FALLBACK_PATTERN_KEYS[pattern]
    if pattern not in _CHROMELESS_PATTERNS:
        allowed = allowed | _FALLBACK_COMMON_KEYS
    else:
        allowed = allowed | frozenset((
            "pattern", "theme", "palette", "lang", "label", "notes", "refs",
        ))
    if scene_adapter:
        allowed = allowed | _FALLBACK_ADAPTER_TOP_KEYS.get(pattern, frozenset())
    _fallback_shape(set(spec) <= allowed, location)
    _fallback_shape(_FALLBACK_REQUIRED_KEYS[pattern] <= set(spec), location)
    for key in ("headline", "title"):
        if key in _FALLBACK_REQUIRED_KEYS[pattern]:
            _fallback_shape(isinstance(spec[key], str) and bool(spec[key].strip()), location + "/" + key)
    if "exhibit_label" in spec:
        _fallback_shape(spec.get("layout") == "analytical", location + "/exhibit_label")
    if "lang" in spec:
        _fallback_shape(spec["lang"] in ("en", "ja"), location + "/lang")
    if "presentation" in spec:
        _fallback_shape(spec["presentation"] == "editorial", location + "/presentation")
    if "model_context" in spec:
        context = spec["model_context"]
        here = location + "/model_context"
        _fallback_shape(isinstance(context, dict), here)
        if pattern == "scatter":
            _fallback_shape(set(context) == {"kind", "intercept", "coefficient"} and context.get("kind") == "linear_model", here)
            _fallback_shape(_fallback_number(context["intercept"]) and _fallback_number(context["coefficient"]), here)
        elif pattern == "bullet_list":
            _fallback_shape(set(context) == {"kind", "label", "values"} and context.get("kind") == "scenario_compare" and _fallback_text(context["label"]), here)
            values = context["values"]
            _fallback_shape(isinstance(values, list) and 1 <= len(values) <= 12, here + "/values")
            for index, item in enumerate(values):
                _fallback_shape(isinstance(item, dict) and set(item) == {"item_id", "value", "rank"} and _fallback_text(item["item_id"]) and _fallback_number(item["value"]), f"{here}/values/{index}")
                rank = _fallback_integer(item["rank"])
                _fallback_shape(rank is not None and 1 <= rank <= len(values), f"{here}/values/{index}/rank")
        else:
            _fallback_shape(set(context) == {"kind", "components", "comparison"} and context.get("kind") == "score_breakdown", here)
            components = context["components"]
            _fallback_shape(isinstance(components, list) and 2 <= len(components) <= 8, here + "/components")
            for index, component in enumerate(components):
                _fallback_shape(isinstance(component, dict) and set(component) == {"label", "value"} and _fallback_text(component["label"]) and _fallback_number(component["value"]), f"{here}/components/{index}")
            comparison = context["comparison"]
            _fallback_shape(isinstance(comparison, dict) and set(comparison) == {"label", "remove_index"} and _fallback_text(comparison["label"]), here + "/comparison")
            remove_index = _fallback_integer(comparison["remove_index"])
            _fallback_shape(remove_index is not None and 0 <= remove_index < len(components), here + "/comparison/remove_index")

    for key in _FALLBACK_TEXT_KEYS.intersection(spec):
        _fallback_shape(_fallback_text(spec[key], nonempty=False), location + "/" + key)
    if "page_number" in spec:
        page_number = spec["page_number"]
        _fallback_shape(
            _fallback_text(page_number, nonempty=False)
            if isinstance(page_number, str)
            else _fallback_number(page_number),
            location + "/page_number",
        )
    if "footnotes" in spec:
        _fallback_shape(
            isinstance(spec["footnotes"], list)
            and all(_fallback_text(value, nonempty=False) for value in spec["footnotes"]),
            location + "/footnotes",
        )
        if len(spec["footnotes"]) > _FALLBACK_LIST_LIMITS["footnotes"]:
            _fail("fallback_limit", location + "/footnotes", "fallback collection exceeds its renderer limit")
    if "refs" in spec:
        refs = spec["refs"]
        _fallback_shape(isinstance(refs, list), location + "/refs")
        for index, reference in enumerate(refs):
            _fallback_shape(
                isinstance(reference, dict)
                and set(reference) == {"label", "url"}
                and _fallback_text(reference["label"])
                and _fallback_text(reference["url"]),
                f"{location}/refs/{index}",
            )
    for key, limit in _FALLBACK_LIST_LIMITS.items():
        if key == "footnotes" or key not in spec:
            continue
        if key == "columns" and pattern in ("bullet_list", "kpi_scorecard", "small_multiples"):
            maximum = 2 if pattern == "bullet_list" else 4
            columns = _fallback_integer(spec[key])
            _fallback_shape(columns is not None and 1 <= columns <= maximum, location + "/" + key)
            continue
        _fallback_shape(isinstance(spec[key], list), location + "/" + key)
        if len(spec[key]) > limit:
            _fail("fallback_limit", location + "/" + key, "fallback collection exceeds its renderer limit")
    for key, object_keys in _FALLBACK_OBJECT_KEYS.items():
        if key not in spec:
            continue
        value = spec[key]
        if key in ("x_axis", "y_axis"):
            if pattern == "two_by_two":
                object_keys = frozenset(("label", "low", "high"))
            elif pattern == "scatter":
                object_keys = frozenset(("label", "unit", "domain", "tick_labels"))
                if scene_adapter:
                    object_keys |= frozenset(("quantity",))
        _fallback_shape(isinstance(value, dict) and set(value) <= object_keys, location + "/" + key)
        if key in ("x_axis", "y_axis"):
            _fallback_shape(isinstance(value.get("label"), str) and bool(value["label"].strip()), location + "/" + key + "/label")
    for key, (limit, item_keys) in _FALLBACK_COLLECTIONS.get(pattern, {}).items():
        if key == "gates" and key not in spec:
            continue
        value = spec.get(key)
        _fallback_shape(isinstance(value, list), location + "/" + key)
        assert isinstance(value, list)
        if key != "gates":
            _fallback_shape(bool(value), location + "/" + key)
        if pattern == "time_series" and key == "series" and len(value) != 1:
            _fail("fallback_limit", location + "/series", "time-series fallback supports exactly one rendered series")
        if pattern == "process_flow" and spec.get("theme") == "executive":
            limit = 5
        if pattern == "two_by_two" and spec.get("theme") == "executive":
            limit = 6
        if pattern == "agenda":
            limit = 8
        if pattern == "bullet_list":
            limit = 12 if spec.get("columns", 1) == 2 else 6
        if pattern == "closing" and key == "next_steps":
            limit = 5
        if len(value) > limit:
            _fail("fallback_limit", location + "/" + key, "fallback collection exceeds its renderer limit")
        for index, item in enumerate(value):
            if pattern == "process_flow" and spec.get("theme") != "executive":
                item_keys = frozenset(("label", "detail"))
            if scene_adapter and pattern == "scatter":
                item_keys = item_keys | frozenset(("item_id", "removed"))
            if scene_adapter and pattern in ("gap", "before_after"):
                item_keys = item_keys | frozenset(("item_id", "removed"))
            if scene_adapter and pattern == "bullet_list":
                item_keys = item_keys | frozenset(("item_id", "rank", "metric", "removed"))
            _fallback_shape(
                isinstance(item, dict) and set(item) <= item_keys,
                f"{location}/{key}/{index}",
            )
            if isinstance(item, dict):
                required_item_keys = {
                    "waterfall": ("label", "value"), "gap": ("label", "value"),
                    "before_after": ("label", "before", "after"), "time_series": ("values",),
                    "benchmark_table": ("label", "values"),
                    "summary_strip": ("claim", "proof", "implication"),
                    "process_flow": ("label",), "funnel": ("label", "value"),
                    "gantt": (
                        ("label", "period")
                        if key == "gates"
                        else ("label", "start", "end")
                    ),
                    "kpi_scorecard": ("label", "value"),
                    "two_by_two": ("label", "x", "y"), "agenda": ("title",),
                    "bullet_list": ("text",), "closing": ("action",),
                    "distribution": ("label", "value"),
                    "small_multiples": ("label", "values"),
                    "scatter": ("x", "y"),
                }.get(pattern, ())
                _fallback_shape(set(required_item_keys) <= set(item), f"{location}/{key}/{index}")

    def text(value: object, suffix: str, *, nonempty: bool = True) -> None:
        _fallback_shape(_fallback_text(value, nonempty=nonempty), location + suffix)

    def number(value: object, suffix: str) -> None:
        _fallback_shape(_fallback_number(value), location + suffix)

    def scalar(value: object, suffix: str) -> None:
        _fallback_shape(
            _fallback_text(value, nonempty=False)
            if isinstance(value, str)
            else _fallback_number(value),
            location + suffix,
        )

    def optional_text(mapping: dict, key: str, suffix: str) -> None:
        if key in mapping:
            text(mapping[key], suffix, nonempty=False)

    if pattern == "waterfall":
        start = spec["start"]
        _fallback_shape(isinstance(start, dict) and set(start) == {"label", "value"}, location + "/start")
        text(start["label"], "/start/label")
        number(start["value"], "/start/value")
        for index, driver in enumerate(spec["drivers"]):
            text(driver["label"], f"/drivers/{index}/label")
            number(driver["value"], f"/drivers/{index}/value")
    elif pattern in ("gap", "funnel", "distribution"):
        collection = {"gap": "items", "funnel": "stages", "distribution": "bins"}[pattern]
        for index, item in enumerate(spec[collection]):
            text(item["label"], f"/{collection}/{index}/label")
            number(item["value"], f"/{collection}/{index}/value")
            if pattern in ("funnel", "distribution") or (
                pattern == "gap" and "value_domain" not in spec
            ):
                _fallback_shape(item["value"] >= 0, f"{location}/{collection}/{index}/value")
            if "emphasis" in item:
                _fallback_shape(type(item["emphasis"]) is bool, f"{location}/{collection}/{index}/emphasis")
        if "highlight" in spec:
            highlight = _fallback_integer(spec["highlight"])
            _fallback_shape(highlight is not None and -1 <= highlight < len(spec[collection]), location + "/highlight")
        if pattern == "distribution" and "commentary" in spec:
            commentary = spec["commentary"]
            text(commentary.get("title"), "/commentary/title")
            points = commentary.get("points")
            _fallback_shape(
                isinstance(points, list)
                and 1 <= len(points) <= 3
                and all(_fallback_text(value) for value in points),
                location + "/commentary/points",
            )
            if len(spec[collection]) > 6:
                _fail("fallback_limit", location + "/bins", "commentary fallback supports at most six bins")
    elif pattern == "before_after":
        for index, pair in enumerate(spec["pairs"]):
            text(pair["label"], f"/pairs/{index}/label")
            number(pair["before"], f"/pairs/{index}/before")
            number(pair["after"], f"/pairs/{index}/after")
            if "value_domain" not in spec:
                _fallback_shape(
                    pair["before"] >= 0 and pair["after"] >= 0,
                    f"{location}/pairs/{index}",
                )
            for key in ("unit", "before_text", "after_text", "delta_text"):
                optional_text(pair, key, f"/pairs/{index}/{key}")
    elif pattern == "time_series":
        _fallback_shape(all(_fallback_text(value) for value in spec["x_labels"]), location + "/x_labels")
        series = spec["series"][0]
        optional_text(series, "label", "/series/0/label")
        _fallback_shape(isinstance(series["values"], list), location + "/series/0/values")
        _fallback_shape(
            len(series["values"]) == len(spec["x_labels"])
            and all(_fallback_number(value) and value >= 0 for value in series["values"]),
            location + "/series/0/values",
        )
    elif pattern == "benchmark_table":
        _fallback_shape(all(_fallback_text(value) for value in spec["columns"]), location + "/columns")
        for index, row in enumerate(spec["rows"]):
            text(row["label"], f"/rows/{index}/label")
            _fallback_shape(
                isinstance(row["values"], list)
                and len(row["values"]) == len(spec["columns"]),
                f"{location}/rows/{index}/values",
            )
            for column_index, value in enumerate(row["values"]):
                scalar(value, f"/rows/{index}/values/{column_index}")
        leaders = spec.get("leaders", [])
        _fallback_shape(isinstance(leaders, list), location + "/leaders")
        for index, pair in enumerate(leaders):
            _fallback_shape(
                isinstance(pair, list)
                and len(pair) == 2
                and all(_fallback_integer(value) is not None for value in pair),
                f"{location}/leaders/{index}",
            )
            row_index, column_index = (_fallback_integer(value) for value in pair)
            assert row_index is not None and column_index is not None
            _fallback_shape(
                0 <= row_index < len(spec["rows"])
                and 0 <= column_index < len(spec["columns"]),
                f"{location}/leaders/{index}",
            )
    elif pattern == "summary_strip":
        for index, block in enumerate(spec["blocks"]):
            for key in ("claim", "proof", "implication"):
                text(block[key], f"/blocks/{index}/{key}")
            optional_text(block, "metric", f"/blocks/{index}/metric")
        if "focus_block" in spec:
            focus = _fallback_integer(spec["focus_block"])
            _fallback_shape(focus is not None and 0 <= focus < len(spec["blocks"]), location + "/focus_block")
    elif pattern == "process_flow":
        for index, step in enumerate(spec["steps"]):
            text(step["label"], f"/steps/{index}/label")
            for key in ("detail", "owner", "duration"):
                optional_text(step, key, f"/steps/{index}/{key}")
        if "highlight" in spec:
            highlight = _fallback_integer(spec["highlight"])
            _fallback_shape(highlight is not None and 0 <= highlight < len(spec["steps"]), location + "/highlight")
    elif pattern == "heatmap":
        _fallback_shape(all(_fallback_text(value) for value in spec["rows"]), location + "/rows")
        _fallback_shape(all(_fallback_text(value) for value in spec["columns"]), location + "/columns")
        _fallback_shape(len(spec["values"]) == len(spec["rows"]), location + "/values")
        for index, row in enumerate(spec["values"]):
            _fallback_shape(isinstance(row, list), f"{location}/values/{index}")
            _fallback_shape(
                len(row) == len(spec["columns"]) and all(_fallback_number(value) for value in row),
                f"{location}/values/{index}",
            )
        if "diverging" in spec:
            _fallback_shape(type(spec["diverging"]) is bool, location + "/diverging")
    elif pattern == "gantt":
        _fallback_shape(all(_fallback_text(value) for value in spec["periods"]), location + "/periods")
        for index, bar in enumerate(spec["bars"]):
            text(bar["label"], f"/bars/{index}/label")
            start = _fallback_integer(bar["start"])
            end = _fallback_integer(bar["end"])
            _fallback_shape(
                start is not None
                and end is not None
                and 0 <= start <= end < len(spec["periods"]),
                f"{location}/bars/{index}",
            )
            if "highlight" in bar:
                _fallback_shape(type(bar["highlight"]) is bool, f"{location}/bars/{index}/highlight")
            optional_text(bar, "note", f"/bars/{index}/note")
        for index, gate in enumerate(spec.get("gates", [])):
            text(gate["label"], f"/gates/{index}/label")
            period = _fallback_integer(gate["period"])
            _fallback_shape(period is not None and 0 <= period < len(spec["periods"]), f"{location}/gates/{index}/period")
    elif pattern == "kpi_scorecard":
        columns = _fallback_integer(spec.get("columns", 3))
        assert columns is not None
        if len(spec["metrics"]) > 2 * columns:
            _fail("fallback_limit", location + "/metrics", "scorecard fallback supports at most two rendered rows")
        for index, metric in enumerate(spec["metrics"]):
            text(metric["label"], f"/metrics/{index}/label")
            scalar(metric["value"], f"/metrics/{index}/value")
            for key in ("target", "trend", "status"):
                optional_text(metric, key, f"/metrics/{index}/{key}")
    elif pattern in ("two_by_two", "scatter"):
        for axis_name in ("x_axis", "y_axis"):
            axis = spec[axis_name]
            text(axis["label"], f"/{axis_name}/label")
            for key in ("unit", "low", "high", "quantity"):
                optional_text(axis, key, f"/{axis_name}/{key}")
            if "domain" in axis:
                domain = axis["domain"]
                _fallback_shape(
                    isinstance(domain, list)
                    and len(domain) == 2
                    and all(_fallback_number(value) for value in domain)
                    and domain[0] < domain[1],
                    f"{location}/{axis_name}/domain",
                )
            if "tick_labels" in axis:
                _fallback_shape(
                    isinstance(axis["tick_labels"], list)
                    and len(axis["tick_labels"]) == 2
                    and all(_fallback_text(value) for value in axis["tick_labels"]),
                    f"{location}/{axis_name}/tick_labels",
                )
        for index, point in enumerate(spec["points"]):
            number(point["x"], f"/points/{index}/x")
            number(point["y"], f"/points/{index}/y")
            if pattern == "two_by_two":
                _fallback_shape(
                    0 <= point["x"] <= 100 and 0 <= point["y"] <= 100,
                    f"{location}/points/{index}",
                )
            optional_text(point, "label", f"/points/{index}/label")
            if "emphasis" in point:
                _fallback_shape(type(point["emphasis"]) is bool, f"{location}/points/{index}/emphasis")
            if scene_adapter:
                optional_text(point, "item_id", f"/points/{index}/item_id")
                if "removed" in point:
                    _fallback_shape(type(point["removed"]) is bool, f"{location}/points/{index}/removed")
        if pattern == "two_by_two":
            _fallback_shape(all(_fallback_text(value) for value in spec.get("quadrants", [])), location + "/quadrants")
            if "focus_quadrant" in spec:
                focus = _fallback_integer(spec["focus_quadrant"])
                _fallback_shape(focus is not None and 0 <= focus <= 3, location + "/focus_quadrant")
        else:
            for key in ("x_zero", "y_zero"):
                if key in spec:
                    _fallback_shape(type(spec[key]) is bool, location + "/" + key)
    elif pattern == "small_multiples":
        columns = _fallback_integer(spec.get("columns", 3))
        assert columns is not None
        if len(spec["charts"]) > 4 * columns:
            _fail("fallback_limit", location + "/charts", "small-multiple fallback supports at most four rendered rows")
        for index, chart in enumerate(spec["charts"]):
            text(chart["label"], f"/charts/{index}/label")
            _fallback_shape(
                isinstance(chart["values"], list)
                and bool(chart["values"])
                and all(_fallback_number(value) for value in chart["values"]),
                f"{location}/charts/{index}/values",
            )
            if "emphasis" in chart:
                _fallback_shape(type(chart["emphasis"]) is bool, f"{location}/charts/{index}/emphasis")
    elif pattern == "section_divider":
        section_number = _fallback_integer(spec["section_number"])
        _fallback_shape(section_number is not None and section_number >= 1, location + "/section_number")
    elif pattern == "agenda":
        for index, item in enumerate(spec["items"]):
            text(item["title"], f"/items/{index}/title")
            optional_text(item, "detail", f"/items/{index}/detail")
        if "current" in spec:
            current = _fallback_integer(spec["current"])
            _fallback_shape(current is not None and 1 <= current <= len(spec["items"]), location + "/current")
    elif pattern == "bullet_list":
        for index, bullet in enumerate(spec["bullets"]):
            text(bullet["text"], f"/bullets/{index}/text")
            if "emphasis" in bullet:
                _fallback_shape(type(bullet["emphasis"]) is bool, f"{location}/bullets/{index}/emphasis")
            if "metric" in bullet:
                number(bullet["metric"], f"/bullets/{index}/metric")
    elif pattern == "closing":
        _fallback_shape(
            not (spec.get("annotation") and spec.get("call_to_action")),
            location + "/call_to_action",
        )
        for index, step in enumerate(spec["next_steps"]):
            text(step["action"], f"/next_steps/{index}/action")
            for key in ("owner", "timing"):
                optional_text(step, key, f"/next_steps/{index}/{key}")
    elif pattern == "quote":
        text(spec["text"], "/text")
    if pattern == "bullet_list":
        ranked_scale_keys = frozenset(("quantity", "unit", "value_domain", "baseline"))
        present_ranked_scale_keys = ranked_scale_keys.intersection(spec)
        if present_ranked_scale_keys:
            _fallback_shape(
                scene_adapter and present_ranked_scale_keys == ranked_scale_keys,
                location + "/value_domain",
            )
            _fallback_shape(_fallback_text(spec["quantity"]), location + "/quantity")
            _fallback_shape(_fallback_text(spec["unit"]), location + "/unit")
            domain = spec["value_domain"]
            _fallback_shape(
                isinstance(domain, list)
                and len(domain) == 2
                and all(_fallback_number(value) for value in domain)
                and domain[0] < domain[1],
                location + "/value_domain",
            )
            _fallback_shape(
                _fallback_number(spec["baseline"])
                and domain[0] <= spec["baseline"] <= domain[1],
                location + "/baseline",
            )
        emphasized = 0
        for index, bullet in enumerate(spec["bullets"]):
            sub = bullet.get("sub", [])
            _fallback_shape(
                isinstance(sub, list)
                and all(_fallback_text(value, nonempty=False) for value in sub),
                f"{location}/bullets/{index}/sub",
            )
            if len(sub) > 3:
                _fail("fallback_limit", f"{location}/bullets/{index}/sub", "fallback collection exceeds its renderer limit")
            emphasized += bullet.get("emphasis") is True
        _fallback_shape(emphasized <= 1, location + "/bullets")
    if pattern == "end_cover" and "contact" in spec:
        _fallback_shape(
            all(_fallback_text(value, nonempty=False) for value in spec["contact"]),
            location + "/contact",
        )
    if pattern == "closing" and "takeaways" in spec:
        _fallback_shape(
            all(_fallback_text(value, nonempty=False) for value in spec["takeaways"]),
            location + "/takeaways",
        )
    if pattern == "section_divider" and "sections" in spec:
        _fallback_shape(
            all(_fallback_text(value, nonempty=False) for value in spec["sections"]),
            location + "/sections",
        )
        section_number = _fallback_integer(spec["section_number"])
        assert section_number is not None
        _fallback_shape(section_number <= len(spec["sections"]), location + "/section_number")
        items = [f"{index + 1:02d} {name}" for index, name in enumerate(spec["sections"])]
        total_units = sum(render_slide_spec._text_width(item) for item in items) + 4 * max(len(items) - 1, 0)
        available_units = (render_slide_spec.W - render_slide_spec.ML - render_slide_spec.MR) / (render_slide_spec.T_LABEL * 0.62)
        _fallback_shape(total_units <= available_units, location + "/sections")
    if pattern == "time_series":
        series_values = spec["series"][0]["values"]
        _fallback_shape(isinstance(series_values, list) and bool(series_values), location + "/series/0/values")
        if len(series_values) > 128:
            _fail("fallback_limit", location + "/series/0/values", "fallback collection exceeds its renderer limit")
    if pattern in ("gap", "before_after"):
        _fallback_shape(("value_domain" in spec) == ("baseline" in spec), location + "/value_domain")
    if pattern == "benchmark_table" and "leaders" in spec:
        _fallback_shape(isinstance(spec["leaders"], list), location + "/leaders")
        for index, pair in enumerate(spec["leaders"]):
            _fallback_shape(
                isinstance(pair, list)
                and len(pair) == 2
                and all(_fallback_integer(value) is not None for value in pair),
                f"{location}/leaders/{index}",
            )
    if pattern == "heatmap" and isinstance(spec.get("values"), list):
        cell_count = 0
        for index, row in enumerate(spec["values"]):
            _fallback_shape(isinstance(row, list), f"{location}/values/{index}")
            cell_count += len(row)
        if cell_count > 512:
            _fail("fallback_limit", location + "/values", "fallback heatmap exceeds its cell limit")
    for key in ("values", "sub", "points"):
        # Bound nested arrays which otherwise multiply wrapping or node work.
        stack = [spec]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                nested = item.get(key)
                if isinstance(nested, list) and len(nested) > 128:
                    _fail("fallback_limit", location + "/" + key, "fallback nested collection exceeds its limit")
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)

    work = _fallback_work(spec)
    if work > MAX_FALLBACK_WORK_PER_SLIDE:
        _fail("fallback_limit", location, "fallback render work exceeds the per-slide limit")
    try:
        render_slide_spec.validate_spec(_renderer_spec_copy(spec))
    except BundleValidationError:
        raise
    except Exception:
        _fail("fallback_shape", location, "fallback spec violates the closed renderer contract")
    return work


def _flatten_static_content(spec: dict, *, lang: str = "en") -> list[str]:
    pattern = spec.get("pattern")
    paragraphs: list[str] = []
    markers = _SEMANTIC_MARKERS[lang]

    def add(value: object) -> None:
        if isinstance(value, str) and value:
            paragraphs.append(value)

    def scalar(value: object) -> str:
        return str(value) if isinstance(value, (str, int, float, Decimal)) and not isinstance(value, bool) else ""

    if pattern not in _CHROMELESS_PATTERNS:
        add(spec.get("exhibit_label"))
        add(spec.get("subline"))
    if pattern == "bullet_list":
        for bullet in spec.get("bullets", []):
            add(bullet.get("text"))
            if bullet.get("emphasis") is True:
                add(f"{markers['emphasized']}: {scalar(bullet.get('text'))}")
            for value in bullet.get("sub", []):
                add(value)
    elif pattern == "agenda":
        current = _fallback_integer(spec.get("current"))
        for index, item in enumerate(spec.get("items", []), start=1):
            text = scalar(item.get("title"))
            if item.get("detail"):
                text += ": " + scalar(item["detail"])
            add(text)
            if current == index:
                add(f"{markers['current']}: {scalar(item.get('title'))}")
    elif pattern == "summary_strip":
        focus = _fallback_integer(spec.get("focus_block"))
        for index, block in enumerate(spec.get("blocks", [])):
            for key in ("metric", "claim", "proof", "implication"):
                add(block.get(key))
            if focus == index:
                add(f"{markers['focused']}: {scalar(block.get('claim'))}")
    elif pattern == "closing":
        for value in spec.get("takeaways", []):
            add(value)
        for step in spec.get("next_steps", []):
            text = scalar(step.get("action"))
            metadata = [scalar(step.get(key)) for key in ("owner", "timing")]
            metadata = [value for value in metadata if value]
            add(text + (": " + " · ".join(metadata) if metadata else ""))
        add(spec.get("call_to_action"))
    elif pattern == "quote":
        for key in ("text", "attribution", "context"):
            add(spec.get(key))
    elif pattern in ("cover", "section_divider", "end_cover"):
        visible_keys = {
            "cover": ("subtitle", "presenter", "date", "classification"),
            "section_divider": ("subtitle", "classification"),
            "end_cover": ("subtitle", "presenter", "date", "classification"),
        }[pattern]
        for key in visible_keys:
            add(spec.get(key))
        if pattern == "section_divider":
            section_number = _fallback_integer(spec.get("section_number"))
            if section_number is not None:
                add(f"SECTION {section_number:02d}")
        if pattern == "section_divider":
            for value in spec.get("sections", []):
                add(value)
        if pattern == "end_cover":
            for item in spec.get("contact", []):
                if isinstance(item, str):
                    add(item)
    elif pattern == "waterfall":
        unit = scalar(spec.get("unit"))
        entries = [spec.get("start", {}), *spec.get("drivers", [])]
        end_value = None
        for item in entries:
            if isinstance(item, dict):
                label, value = scalar(item.get("label")), scalar(item.get("value"))
                add(f"{label}: {value}{' ' + unit if unit else ''}" if label and value else "")
        if isinstance(spec.get("start"), dict) and _fallback_number(spec["start"].get("value")):
            drivers = spec.get("drivers", [])
            if all(isinstance(item, dict) and _fallback_number(item.get("value")) for item in drivers):
                end_value = spec["start"]["value"] + sum(item["value"] for item in drivers)
        if end_value is not None:
            end_label = scalar(spec.get("end_label")) or "End"
            add(f"{end_label}: {scalar(end_value)}{' ' + unit if unit else ''}")
    elif pattern == "before_after":
        for item in spec.get("pairs", []):
            label = scalar(item.get("label"))
            before, after = scalar(item.get("before")), scalar(item.get("after"))
            unit = scalar(item.get("unit")) or scalar(spec.get("unit"))
            before_text = scalar(item.get("before_text")) or (before + unit if before else "")
            after_text = scalar(item.get("after_text")) or (after + unit if after else "")
            add(f"{label}: {before_text} → {after_text}" if label and before_text and after_text else "")
            if _fallback_number(item.get("before")) and _fallback_number(item.get("after")):
                value_unit = scalar(item.get("unit")) or scalar(spec.get("unit"))
                delta = item["after"] - item["before"]
                sign = "+" if delta >= 0 else "−"
                add(scalar(item.get("delta_text")) or f"{sign}{render_slide_spec.fmt(abs(delta), value_unit)}")
        if spec.get("pairs"):
            add(spec.get("before_label") or "Before")
            add(spec.get("after_label") or "After")
    elif pattern == "time_series":
        unit = scalar(spec.get("unit"))
        for item in spec.get("series", []):
            label = scalar(item.get("label"))
            values = ", ".join(filter(None, (scalar(value) for value in item.get("values", []))))
            displayed_values = ", ".join(
                render_slide_spec.fmt(value, unit)
                for value in item.get("values", [])
                if _fallback_number(value)
            )
            add(f"{label}: {values}{unit}" if label and values else displayed_values)
        for label in spec.get("x_labels", []):
            add(label)
    elif pattern in ("gap", "distribution", "funnel"):
        key = {"gap": "items", "distribution": "bins", "funnel": "stages"}[pattern]
        unit = scalar(spec.get("unit"))
        values = spec.get(key, [])
        highlight = _fallback_integer(spec.get("highlight"))
        for index, item in enumerate(values):
            label, value = scalar(item.get("label")), scalar(item.get("value"))
            value_text = scalar(item.get("value_text")) if pattern == "gap" else ""
            add(f"{label}: {value_text or value + unit}" if label and (value_text or value) else "")
            if item.get("emphasis") is True:
                add(f"{markers['emphasized']}: {label}")
            if highlight == index:
                add(f"{markers['highlighted']}: {label}")
            if pattern == "funnel" and index > 0:
                previous = values[index - 1].get("value")
                current = item.get("value")
                if _fallback_number(previous) and _fallback_number(current):
                    conversion = "n/a" if previous == 0 else f"{current / previous * 100:.0f}%"
                    add(f"↓ {conversion}")
        if pattern == "gap":
            add(spec.get("gap_label"))
        elif pattern == "distribution" and isinstance(spec.get("commentary"), dict):
            add(spec["commentary"].get("title"))
            for point in spec["commentary"].get("points", []):
                add(point)
    elif pattern == "benchmark_table":
        for column in spec.get("columns", []):
            add(column)
        for row in spec.get("rows", []):
            label = scalar(row.get("label"))
            values = " | ".join(filter(None, (scalar(value) for value in row.get("values", []))))
            add(f"{label}: {values}" if label and values else "")
        columns = spec.get("columns", [])
        rows = spec.get("rows", [])
        for pair in spec.get("leaders", []):
            if isinstance(pair, list) and len(pair) == 2:
                row_index, column_index = (_fallback_integer(value) for value in pair)
                if (
                    row_index is not None and column_index is not None
                    and 0 <= row_index < len(rows) and 0 <= column_index < len(columns)
                ):
                    add(f"{markers['leader']}: {scalar(rows[row_index].get('label'))} — {scalar(columns[column_index])}")
    elif pattern == "kpi_scorecard":
        for metric in spec.get("metrics", []):
            values = [scalar(metric.get("value"))]
            target = scalar(metric.get("target"))
            if target:
                values.append(markers["target"] + target)
            values.extend(filter(None, (scalar(metric.get("trend")), scalar(metric.get("status")))))
            label = scalar(metric.get("label"))
            add(f"{label}: {'; '.join(values)}" if label and values[0] else "")
    elif pattern in ("scatter", "two_by_two"):
        if pattern == "two_by_two" and spec.get("theme") == "executive":
            add(spec.get("legend_title") or "Options")
        for axis_name in ("x_axis", "y_axis"):
            axis = spec.get(axis_name, {})
            if isinstance(axis, dict):
                add(axis.get("label"))
                tick_labels = axis.get("tick_labels", [])
                for tick in tick_labels:
                    add(tick)
                if pattern == "scatter" and not tick_labels:
                    coordinate = axis_name[0]
                    values = [point.get(coordinate) for point in spec.get("points", [])]
                    values = [value for value in values if _fallback_number(value)]
                    if values:
                        endpoints = axis.get("domain")
                        if not isinstance(endpoints, list) or len(endpoints) != 2:
                            endpoints = [
                                min(values + ([0] if spec.get(coordinate + "_zero") else [])),
                                max(values),
                            ]
                        for endpoint in endpoints:
                            add(render_slide_spec.fmt(endpoint, scalar(axis.get("unit"))))
                for key in ("low", "high"):
                    add(axis.get(key))
        for quadrant in spec.get("quadrants", []):
            add(quadrant)
        for point in spec.get("points", []):
            label, x, y = scalar(point.get("label")), scalar(point.get("x")), scalar(point.get("y"))
            if label and "item_id" in point and point.get("removed") is True:
                label += " · " + ("除外" if lang == "ja" else "Removed")
            if label and x and y:
                add(f"{label}: {x}, {y}")
            elif pattern == "scatter" and x and y:
                x_axis, y_axis = spec.get("x_axis", {}), spec.get("y_axis", {})
                add(
                    f"{scalar(x_axis.get('label'))}: {render_slide_spec.fmt(point['x'], scalar(x_axis.get('unit')))}; "
                    f"{scalar(y_axis.get('label'))}: {render_slide_spec.fmt(point['y'], scalar(y_axis.get('unit')))}"
                )
            if point.get("emphasis") is True:
                add(f"{markers['emphasized']}: {label}")
        if pattern == "two_by_two" and spec.get("theme") == "executive":
            focus = _fallback_integer(spec.get("focus_quadrant"))
            quadrants = spec.get("quadrants", [])
            if focus is not None and 0 <= focus < len(quadrants):
                add(f"{markers['focused_quadrant']}: {scalar(quadrants[focus])}")
    elif pattern == "process_flow":
        highlight = _fallback_integer(spec.get("highlight"))
        for index, step in enumerate(spec.get("steps", [])):
            label = scalar(step.get("label"))
            keys = ("detail", "owner", "duration") if spec.get("theme") == "executive" else ("detail",)
            details = [scalar(step.get(key)) for key in keys]
            details = [value for value in details if value]
            add(label + (": " + " · ".join(details) if details else ""))
            if highlight == index:
                add(f"{markers['highlighted']}: {label}")
    elif pattern == "heatmap":
        unit = scalar(spec.get("unit"))
        columns = [scalar(value) for value in spec.get("columns", [])]
        for label, values in zip(spec.get("rows", []), spec.get("values", [])):
            cells = [
                f"{column} {render_slide_spec.fmt(value, unit)}"
                for column, value in zip(columns, values)
                if column and _fallback_number(value)
            ]
            add(f"{scalar(label)}: {'; '.join(cells)}" if scalar(label) and cells else "")
    elif pattern == "gantt":
        periods = spec.get("periods", [])
        for period in periods:
            add(period)
        for bar in spec.get("bars", []):
            start, end = int(bar.get("start", -1)), int(bar.get("end", -1))
            if 0 <= start < len(periods) and 0 <= end < len(periods):
                add(f"{scalar(bar.get('label'))}: {scalar(periods[start])}–{scalar(periods[end])}")
                add(bar.get("note"))
                if bar.get("highlight") is True:
                    add(f"{markers['highlighted']}: {scalar(bar.get('label'))}")
        for gate in spec.get("gates", []):
            period = int(gate.get("period", -1))
            if 0 <= period < len(periods):
                add(f"{scalar(gate.get('label'))}: {scalar(periods[period])}")
    elif pattern == "small_multiples":
        unit = scalar(spec.get("unit"))
        for chart in spec.get("charts", []):
            label = scalar(chart.get("label"))
            values = ", ".join(filter(None, (scalar(value) for value in chart.get("values", []))))
            add(f"{label}: {values}{unit}" if label and values else "")
            if chart.get("emphasis") is True:
                add(f"{markers['emphasized']}: {label}")
    context = spec.get("model_context")
    if isinstance(context, dict):
        if context.get("kind") == "linear_model":
            add(f"Model: {scalar(context.get('intercept'))} + {scalar(context.get('coefficient'))} × input")
        elif context.get("kind") == "score_breakdown":
            for component in context["components"]:
                add(f"{component['label']}: {scalar(component['value'])}")
            comparison = context["comparison"]
            total = sum(Decimal(str(component["value"])) for component in context["components"])
            removed = Decimal(str(context["components"][int(comparison["remove_index"])]["value"]))
            add(f"{comparison['label']}: {canonical_decimal(total - removed)}")
        elif context.get("kind") == "scenario_compare":
            add(context["label"])
            for item in context["values"]:
                add(f"{item['item_id']}: {scalar(item['value'])}; rank {scalar(item['rank'])}")
    if pattern not in _CHROMELESS_PATTERNS:
        add(spec.get("annotation"))
        for footnote in spec.get("footnotes", []):
            add(footnote)
        if spec.get("classification"):
            add(spec["classification"])
        if spec.get("page_number") not in (None, ""):
            add(str(spec["page_number"]))
    return [text for text in paragraphs if text]


def _static_summary(spec: dict, fallback_label: str, *, lang: str | None = None) -> dict:
    pattern = spec.get("pattern")
    headline_key = "title" if pattern in _CHROMELESS_PATTERNS else "headline"
    default_headline = "Thank you" if pattern == "end_cover" else fallback_label
    headline = spec.get(headline_key) or default_headline
    if not isinstance(headline, str):
        headline = fallback_label
    source = (
        spec.get("source")
        if pattern not in _CHROMELESS_PATTERNS and isinstance(spec.get("source"), str)
        else ""
    )
    return {
        "headline": headline,
        "source": source,
        "paragraphs": _flatten_static_content(
            spec,
            lang=lang if lang in _SEMANTIC_MARKERS else (
                spec.get("lang") if spec.get("lang") in _SEMANTIC_MARKERS else "en"
            ),
        ),
        "values": [],
        "decision": None,
    }


def _validate_summary_preflight(summary: dict, location: str) -> None:
    for key in ("headline", "source"):
        value = summary.get(key)
        if not isinstance(value, str) or len(value) > 500:
            _fail("summary_shape", location + "/" + key, "semantic summary text exceeds its bound")
    paragraphs = summary.get("paragraphs")
    if not isinstance(paragraphs, list) or any(
        not isinstance(value, str) or len(value) > 2_000 for value in paragraphs
    ):
        _fail("summary_shape", location + "/paragraphs", "semantic summary paragraph exceeds its bound")


def _scene_display(result, serialized: dict, spec: dict, lang: str) -> dict:
    if result.fallback_check.get("matched") is not True:
        _fail("fallback_mismatch", "<scene>", "display bridge requires an exact matched fallback")
    compiled = result.compiled
    reporting = compiled.get("reporting")
    values: list[dict] = []
    if reporting:
        output_ids = [reporting["primaryOutput"], *reporting.get("secondaryOutputs", [])]
        if serialized.get("type") == "score_model":
            output_ids.append("classification")
        for output_id in output_ids:
            definition = compiled["outputDefinitions"][output_id]
            typed = compiled["initialEvaluation"]["outputs"][output_id]
            quantity = (
                compiled["quantities"][typed.quantity]
                if definition.kind == "numeric"
                else None
            )
            values.append({
                "id": output_id,
                "label": definition.label,
                "text": (
                    format_value(typed.value, quantity, definition.round, lang)
                    if quantity is not None
                    else str(typed.value)
                ),
            })
    initial_decision = serialized["initialEvaluation"].get("decision")
    decision = None if initial_decision is None else {
        "status": initial_decision["status"],
        "recommendation": initial_decision["recommendation"],
    }
    annotation = spec.get("annotation", "")
    if not isinstance(annotation, str):
        _fail("display_shape", "<fallback>/annotation", "baseline annotation must be text")
    threshold_text = None
    if compiled.get("decisionContract") is not None:
        threshold = compiled["decisionContract"].threshold
        precision = max(0, -threshold.value.as_tuple().exponent)
        threshold_text = format_value(threshold.value, compiled["quantities"][threshold.quantity], precision, lang)
    tick_labels = None
    if spec.get("pattern") == "scatter":
        x = spec.get("x_axis", {}).get("tick_labels")
        y = spec.get("y_axis", {}).get("tick_labels")
        if not isinstance(x, list) or not isinstance(y, list) or len(x) != 2 or len(y) != 2 or not all(isinstance(value, str) for value in x + y):
            _fail("display_shape", "<fallback>/axis", "scatter display bridge requires exact two-label tick arrays")
        tick_labels = {"x": list(x), "y": list(y)}
    semantic_spec = copy.deepcopy(spec)
    semantic_spec.pop("annotation", None)
    if serialized.get("type") == "slider_model" and serialized.get("model", {}).get("kind") == "linear":
        # The live linear relationship is already exposed by the compiled
        # formula in Evidence. Its closed legacy semantic bridge is unchanged.
        semantic_spec.pop("model_context", None)
    resolved_view = serialized["initialEvaluation"]["view"]
    if resolved_view is not None:
        if resolved_view.get("component") == "dot_plot":
            semantic_points = semantic_spec.get("points")
            resolved_points = resolved_view["points"]
            if not isinstance(semantic_points, list) or len(semantic_points) != len(resolved_points):
                _fail("display_shape", "<fallback>/points", "semantic points must match the compiled view")
            for semantic_point, resolved_point in zip(semantic_points, resolved_points):
                semantic_point["label"] = resolved_point["label"]
                semantic_point["x"] = resolved_point["xText"]
                semantic_point["y"] = resolved_point["yText"]
                semantic_point["removed"] = resolved_point["removed"]
                semantic_point["emphasis"] = resolved_point["highlight"]
    fallback_summary = _static_summary(semantic_spec, "Fallback", lang=lang)
    summary = {
        "headline": fallback_summary["headline"],
        "source": fallback_summary["source"],
        # Values and decision nodes are the single semantic source; repeating
        # their combined baseline annotation would duplicate the same result
        # for assistive technology.
        "paragraphs": fallback_summary["paragraphs"],
        "values": values,
        "decision": decision,
    }
    return {
        "staticSummary": summary,
        "baselineAnnotation": annotation,
        "thresholdText": threshold_text,
        "axisTickLabels": tick_labels,
    }


def _scatter_position(value: Decimal, domain: tuple[Decimal, Decimal], start: Decimal, extent: Decimal) -> Decimal:
    return start + extent * (value - domain[0]) / (domain[1] - domain[0])


def _live_svg_id(prefix: str, item_id: str, index: int) -> str:
    candidate = f"{prefix}-{item_id}"
    if len(candidate) <= 64:
        return candidate
    digest = 2_166_136_261
    for character in item_id:
        digest ^= ord(character)
        digest = (digest * 16_777_619) & 0xFFFF_FFFF
    return f"{prefix}Key-{digest:08x}"


def _svg_with_id(markup: str, element: str, identifier: str) -> str:
    return markup.replace(f"<{element} ", f'<{element} id="{identifier}" ', 1)


def _live_shell_document(spec: dict, geometry: str) -> str:
    shell_spec = copy.deepcopy(spec)
    shell_spec.pop("annotation", None)
    shell_spec.pop("interactive_result", None)
    parts = render_slide_spec.header(shell_spec)
    parts.extend(render_slide_spec.footer(shell_spec))
    body = render_slide_spec.apply_palette("\n  ".join(parts), shell_spec)
    geometry = render_slide_spec.apply_palette(geometry, shell_spec)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">\n'
        '  <rect width="1280" height="720" fill="#FFFFFF"/>\n'
        f'  {geometry}\n  {body}\n</svg>\n'
    )


def _domain_label(value: str, display: str) -> str:
    if display.startswith(("$", "€", "£", "¥", "￥")):
        return display[0] + value + display[1:]
    return value + ("" if display == "%" else " ") + display


def _serialized_output_text(serialized: dict, output_id: str) -> str:
    definition = serialized["outputDefinitions"][output_id]
    value = Decimal(serialized["initialEvaluation"]["outputs"][output_id]["value"])
    precision = definition["round"]
    with localcontext() as context:
        context.prec = 40
        rounded = value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    number = format(abs(rounded), f",.{precision}f")
    sign = "−" if rounded < 0 else ""
    display = serialized["quantities"][definition["quantity"]]["display"]
    if display.startswith(("$", "€", "£", "¥", "￥")):
        return sign + display[0] + number + display[1:]
    return sign + number + ("" if display == "%" else " ") + display


def _bar_live_shell(spec: dict, serialized: dict, view: dict) -> str:
    domain = tuple(Decimal(value) for value in view["domain"])
    quantity = serialized["quantities"][view["quantity"]]
    chart_x, chart_y, chart_w = Decimal(100), Decimal(232), Decimal(620)
    item_count = max(1, len(view["items"]))
    row_gap = min(Decimal(76), Decimal(300) / item_count)
    compact = item_count > 6
    label_offset = Decimal(12 if compact else 18)
    bar_offset = Decimal(16 if compact else 24)
    bar_height = Decimal(7 if compact else 24)
    marks: list[str] = []
    for index, item in enumerate(view["items"], start=1):
        value = Decimal(item["value"]["value"])
        width = max(Decimal(0), min(chart_w, _scatter_position(value, domain, Decimal(0), chart_w)))
        y = chart_y + (index - 1) * row_gap
        opacity = "0.35" if item["removed"] else "1"
        mark_id = _live_svg_id("LiveMark", item["id"], index)
        label_id = _live_svg_id("LiveLabel", item["id"], index)
        value_id = _live_svg_id("LiveValue", item["id"], index)
        marks.append(
            f'<rect id="{mark_id}" x="{float(chart_x):.1f}" y="{float(y + bar_offset):.1f}" '
            f'width="{float(width):.1f}" height="{float(bar_height):.1f}" fill="{render_slide_spec.BLUE}" opacity="{opacity}"/>'
        )
        marks.append(_svg_with_id(render_slide_spec.text_el(
            float(chart_x), float(y + label_offset), item["label"],
            size=render_slide_spec.T_TICK if compact else render_slide_spec.T_LABEL, fill=render_slide_spec.BLACK,
            weight="600" if item["emphasis"] else "normal",
        ), "text", label_id))
        marks.append(_svg_with_id(render_slide_spec.text_el(
            float(min(chart_x + width + 12, Decimal(800))), float(y + bar_offset + bar_height),
            item["valueText"], size=render_slide_spec.T_TICK,
            fill=render_slide_spec.BLUE, weight="600",
        ), "text", value_id))
    start = _domain_label(view["domain"][0], quantity["display"])
    end = _domain_label(view["domain"][1], quantity["display"])
    anchors = (
        _svg_with_id(render_slide_spec.text_el(float(chart_x), 548, start, size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED), "text", "LiveDomainStart")
        + _svg_with_id(render_slide_spec.text_el(float(chart_x + chart_w), 548, end, size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED, anchor="end"), "text", "LiveDomainEnd")
    )
    geometry = (
        '<defs><clipPath id="LiveChartClip"><rect x="80" y="208" width="750" height="352" fill="#FFFFFF"/></clipPath></defs>'
        '<g id="LiveChartBand" clip-path="url(#LiveChartClip)">'
        '<rect x="80" y="208" width="750" height="352" fill="#FFFFFF"/>'
        + render_slide_spec.line_el(float(chart_x), 528, float(chart_x + chart_w), 528, render_slide_spec.GREY_DARK)
        + anchors + "".join(marks) + "</g>"
    )
    return _live_shell_document(spec, geometry)


def _rank_bridge_layout(spec: dict, view: dict) -> bool:
    return (spec.get("model_context", {}).get("kind") == "scenario_compare"
            and view.get("component") == "ranked_list"
            and 2 <= len(view["items"]) <= 3)


def _rank_bridge_live_shell(spec: dict, serialized: dict, view: dict) -> str:
    """A fixed baseline and keyed selected ranking; vertical distance is ordinal."""
    comparison = {row["item_id"]: row for row in spec["model_context"]["values"]}
    improved = [row for row in view["items"] if comparison[row["id"]]["rank"] < row["rank"]]
    focus = max(improved, key=lambda row: row["rank"] - comparison[row["id"]]["rank"])["id"] if improved else None
    control = serialized["controls"][0]
    selected_label = next(option["label"] for option in control["options"] if option["value"] == serialized["initialState"][control["id"]])
    gap = min(110, 330 / max(1, len(view["items"]) - 1))
    parts = [
        '<g id="LiveChartBand">',
        _svg_with_id(render_slide_spec.text_el(100, 204, selected_label, size=24, weight="600", fill=render_slide_spec.GREY_DARK), "text", "LiveDomainStart"),
        _svg_with_id(render_slide_spec.text_el(900, 204, selected_label, size=24, weight="600", fill=render_slide_spec.GREY_DARK), "text", "LiveCurrentHeading"),
        _svg_with_id(render_slide_spec.text_el(100, 238, "Rank · score " + "–".join(view["domain"]), size=20, fill=render_slide_spec.GREY_MED), "text", "LiveDomainEnd"),
    ]
    for index, row in enumerate(view["items"], start=1):
        y = 300 + (row["rank"] - 1) * gap
        color = render_slide_spec.BLUE if row["id"] == focus else "#77818F"
        parts.append(f'<line id="{_live_svg_id("LiveBridge", row["id"], index)}" x1="420" y1="{y:g}" x2="860" y2="{y:g}" stroke="{color}" stroke-width="{5 if row["id"] == focus else 2}" opacity="{1 if row["id"] == focus else 0.55}"/>')
    for index, row in enumerate(view["items"], start=1):
        y = 300 + (row["rank"] - 1) * gap
        color = render_slide_spec.BLUE if row["id"] == focus else "#626D7C"
        label = re.sub(r" route$", "", row["label"])
        for baseline, x in ((True, 100), (False, 900)):
            prefix = "LiveBase" if baseline else "Live"
            group = _live_svg_id("LiveBase" if baseline else "LiveMark", row["id"], index)
            parts.append(f'<g id="{group}">')
            for name, px, py, text, size, anchor in (
                ("Rank", x, 0, "#" + str(row["rank"]), 22, "start"),
                ("Value", x + 48, 0, label, 30, "start"),
                ("Metric", x + 292, 3, row["metric"]["value"], 40, "end"),
                ("Unit", x + 292, 31, "", 20, "end"),
            ):
                parts.append(_svg_with_id(render_slide_spec.text_el(px, y + py, text, size=size, fill=color, weight="600" if name != "Unit" else "normal", anchor=anchor), "text", _live_svg_id(prefix + name, row["id"], index)))
            parts.append('</g>')
    focus_row = next((row for row in view["items"] if row["id"] == focus), view["items"][0])
    delta = re.sub(r" route$", "", focus_row["label"]) + " starts at #" + str(focus_row["rank"])
    parts.append(_svg_with_id(render_slide_spec.text_el(100, 625, delta, size=28, fill=render_slide_spec.BLUE, weight="600"), "text", "LiveDelta"))
    parts.append('</g>')
    return _live_shell_document(spec, "".join(parts))


def _ranked_live_shell(spec: dict, serialized: dict, view: dict) -> str:
    if _rank_bridge_layout(spec, view):
        return _rank_bridge_live_shell(spec, serialized, view)
    row_start = Decimal(246)
    item_count = max(1, len(view["items"]))
    row_gap = min(Decimal(104), Decimal(320) / item_count)
    compact = item_count > 6
    row_height = Decimal(9) if compact else Decimal(22)
    text_offset = Decimal(14) if compact else Decimal(26)
    domain = tuple(Decimal(value) for value in view.get("domain", ("0", "1")))
    metric_view = "domain" in view
    marks: list[str] = []
    removed_label = "除外" if serialized["locale"] == "ja" else "removed"
    for index, item in enumerate(view["items"], start=1):
        y = row_start + (item["rank"] - 1) * row_gap
        opacity = "0.35" if item["removed"] else "1"
        mark_id = _live_svg_id("LiveMark", item["id"], index)
        value_id = _live_svg_id("LiveValue", item["id"], index)
        value_text = f'{item["rank"]} · {item["label"]}'
        if item["removed"]:
            value_text += " · " + removed_label
        label_markup = _svg_with_id(render_slide_spec.text_el(
            100, float(y + text_offset), value_text,
            size=render_slide_spec.T_TICK if compact else render_slide_spec.T_BODY, fill=render_slide_spec.BLACK,
            weight="600" if item["emphasis"] else "normal",
        ), "text", value_id)
        width = Decimal(0)
        if metric_view and item.get("metric"):
            width = max(Decimal(0), min(Decimal(690), _scatter_position(Decimal(item["metric"]["value"]), domain, Decimal(0), Decimal(690))))
        marks.append(
            f'<g id="{mark_id}" opacity="{opacity}">'
            f'<rect x="100" y="{float(y + text_offset + 13):.1f}" width="{float(width):.1f}" height="{float(row_height):.1f}" fill="{render_slide_spec.BLUE}"/>'
            + label_markup
            + _svg_with_id(render_slide_spec.text_el(800, float(y + text_offset), item.get("metricText", ""), size=render_slide_spec.T_BODY, fill=render_slide_spec.BLUE, weight="600", anchor="end"), "text", _live_svg_id("LiveMetric", item["id"], index))
            + "</g>"
        )
    geometry = (
        '<defs><clipPath id="LiveChartClip"><rect x="80" y="208" width="750" height="392" fill="#FFFFFF"/></clipPath></defs>'
        '<g id="LiveChartBand" clip-path="url(#LiveChartClip)">'
        '<rect x="80" y="208" width="750" height="392" fill="#FFFFFF"/>'
        + _svg_with_id(render_slide_spec.text_el(100, 230, view.get("domain", ["1"])[0], size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED), "text", "LiveDomainStart")
        + _svg_with_id(render_slide_spec.text_el(800, 230, view.get("domain", ["", str(len(view["items"]))])[1], size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED, anchor="end"), "text", "LiveDomainEnd")
        + "".join(marks) + "</g>"
    )
    return _live_shell_document(spec, geometry)


def _recommendation_live_shell(spec: dict, serialized: dict, view: dict) -> str:
    bands = serialized["model"]["bands"]
    domain_min = Decimal(bands[0]["min"]["value"])
    domain_max = Decimal(bands[-1]["max"]["value"])
    chart_x, chart_w = Decimal(100), Decimal(700)
    classification = serialized["initialEvaluation"]["outputs"]["classification"]["value"]
    band_markup: list[str] = []
    for index, band in enumerate(bands, start=1):
        minimum = Decimal(band["min"]["value"])
        maximum = Decimal(band["max"]["value"])
        x = _scatter_position(minimum, (domain_min, domain_max), chart_x, chart_w)
        width = (
            _scatter_position(maximum, (domain_min, domain_max), chart_x, chart_w)
            - x
        )
        opacity = "0.9" if band["label"] == classification else "0.35"
        band_id = _live_svg_id("LiveBand", band["id"], index)
        band_markup.append(
            f'<rect id="{band_id}" x="{float(x):.1f}" y="520" width="{float(width):.1f}" '
            f'height="28" fill="{render_slide_spec.BLUE}" opacity="{opacity}"/>'
        )
        band_markup.append(render_slide_spec.text_el(
            float(x + width / 2), 582, band["label"],
            size=render_slide_spec.T_LABEL, fill=render_slide_spec.GREY_DARK,
            weight="600", anchor="middle",
        ))
    score = Decimal(view["score"]["value"])
    score_text = _serialized_output_text(serialized, "score")
    cursor_x = _scatter_position(score, (domain_min, domain_max), chart_x, chart_w)
    contribution_markup = []
    controls = {control["id"]: control for control in serialized["controls"]}
    contributions = serialized["model"]["contributions"]
    maximum = max(Decimal(typed["value"]) for _, entries in contributions for _, typed in entries)
    row_gap = min(Decimal(50), Decimal(200) / len(contributions))
    for index, (control_id, entries) in enumerate(contributions, start=1):
        selected = serialized["initialState"][control_id]
        value = next(Decimal(typed["value"]) for key, typed in entries if key == selected)
        y = Decimal(300) + (index - 1) * row_gap
        width = Decimal(360) * value / maximum if maximum else Decimal(0)
        contribution_markup.extend((
            render_slide_spec.text_el(100, float(y), controls[control_id]["label"], size=render_slide_spec.T_LABEL, fill=render_slide_spec.GREY_DARK),
            f'<rect id="{_live_svg_id("LiveContribution", control_id, index)}" x="380" y="{y - 17}" width="{width:.1f}" height="20" fill="{render_slide_spec.BLUE}"/>',
            _svg_with_id(render_slide_spec.text_el(800, float(y), canonical_decimal(value), size=render_slide_spec.T_LABEL, fill=render_slide_spec.BLUE, weight="600", anchor="end"), "text", _live_svg_id("LiveContributionValue", control_id, index)),
        ))
    threshold = Decimal(serialized["decisionContract"]["threshold"]["value"])
    threshold_x = _scatter_position(threshold, (domain_min, domain_max), chart_x, chart_w)
    geometry = (
        '<defs><clipPath id="LiveChartClip"><rect x="80" y="208" width="750" height="412" fill="#FFFFFF"/></clipPath></defs>'
        '<g id="LiveChartBand" clip-path="url(#LiveChartClip)">'
        '<rect x="80" y="208" width="750" height="412" fill="#FFFFFF"/>'
        + "".join(contribution_markup)
        + "".join(band_markup)
        + f'<line x1="{threshold_x:.1f}" x2="{threshold_x:.1f}" y1="498" y2="554" stroke="{render_slide_spec.GREY_DARK}" stroke-dasharray="4 4"/>'
        + render_slide_spec.text_el(float(threshold_x), 488, "Gate " + canonical_decimal(threshold), size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_DARK, anchor="middle")
        + f'<line id="LiveScoreCursor" x1="{float(cursor_x):.1f}" x2="{float(cursor_x):.1f}" y1="510" y2="560" stroke="{render_slide_spec.BLUE2}" stroke-width="5"/>'
        + _svg_with_id(render_slide_spec.text_el(100, 244, score_text, size=40, fill=render_slide_spec.BLUE, weight="bold"), "text", "LiveScoreValue")
        + _svg_with_id(render_slide_spec.text_el(800, 244, classification, size=render_slide_spec.T_BODY, fill=render_slide_spec.BLACK, weight="600", anchor="end"), "text", "LiveClassification")
        + _svg_with_id(render_slide_spec.text_el(float(chart_x), 610, canonical_decimal(domain_min), size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED), "text", "LiveDomainStart")
        + _svg_with_id(render_slide_spec.text_el(float(chart_x + chart_w), 610, canonical_decimal(domain_max), size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED, anchor="end"), "text", "LiveDomainEnd")
        + "</g>"
    )
    return _live_shell_document(spec, geometry)


def _live_shell(
    spec: dict,
    serialized: dict,
    display: dict,
    *,
    decision_range_message: str | None = None,
) -> str:
    resolved_view = serialized.get("initialEvaluation", {}).get("view")
    if not isinstance(resolved_view, dict):
        return render_slide_spec.render(copy.deepcopy(spec))
    component = resolved_view.get("component")
    if component == "bar_compare":
        return _bar_live_shell(spec, serialized, resolved_view)
    if component == "ranked_list":
        return _ranked_live_shell(spec, serialized, resolved_view)
    if component == "recommendation_panel":
        return _recommendation_live_shell(spec, serialized, resolved_view)
    if component != "dot_plot" or spec.get("pattern") != "scatter" or serialized.get("type") not in ("slider_model", "state_toggle"):
        _fail("runtime_unsupported", "<scene>/view", "unsupported live view shell")
    shell_spec = copy.deepcopy(spec)
    shell_spec.pop("annotation", None)
    shell_spec.pop("interactive_result", None)
    parts = render_slide_spec.header(shell_spec)
    x_axis, y_axis = shell_spec["x_axis"], shell_spec["y_axis"]
    x_labels, y_labels = display["axisTickLabels"]["x"], display["axisTickLabels"]["y"]
    plot_x, plot_y, plot_w, plot_h = Decimal(130), Decimal(230), Decimal(690), Decimal(330)
    parts.extend((
        render_slide_spec.line_el(float(plot_x), float(plot_y + plot_h), float(plot_x + plot_w), float(plot_y + plot_h), render_slide_spec.GREY_DARK),
        render_slide_spec.line_el(float(plot_x), float(plot_y), float(plot_x), float(plot_y + plot_h), render_slide_spec.GREY_DARK),
        render_slide_spec.text_el(float(plot_x + plot_w / 2), float(plot_y + plot_h + 44), x_axis["label"], size=render_slide_spec.T_LABEL, fill=render_slide_spec.GREY_DARK, weight="600", anchor="middle"),
        render_slide_spec.text_el(render_slide_spec.ML, float(plot_y - 9), y_axis["label"], size=render_slide_spec.T_LABEL, fill=render_slide_spec.GREY_DARK, weight="600"),
        render_slide_spec.text_el(float(plot_x), float(plot_y + plot_h + 23), x_labels[0], size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED),
        render_slide_spec.text_el(float(plot_x + plot_w), float(plot_y + plot_h + 23), x_labels[1], size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED, anchor="end"),
        render_slide_spec.text_el(float(plot_x - 10), float(plot_y + 10), y_labels[1], size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED, anchor="end"),
        render_slide_spec.text_el(float(plot_x - 10), float(plot_y + plot_h), y_labels[0], size=render_slide_spec.T_TICK, fill=render_slide_spec.GREY_MED, anchor="end"),
    ))
    view = serialized["initialEvaluation"]["view"]
    authored_view = serialized.get("view", resolved_view)
    x_domain = tuple(Decimal(value) for value in authored_view["xDomain"])
    y_domain = tuple(Decimal(value) for value in authored_view["yDomain"])
    threshold_markup = ""
    relationship_markup = ""
    if serialized.get("type") == "slider_model":
        threshold = Decimal(serialized["decisionContract"]["threshold"]["value"])
        model_output = serialized["reporting"]["primaryOutput"]
        output_axes = {
            axis
            for point in serialized["view"]["points"]
            for axis in ("x", "y")
            if point[axis].get("ref") == f"output:{model_output}"
        }
        if len(output_axes) != 1:
            _fail(
                "runtime_unsupported",
                "<scene>/view/points",
                "dot-plot live shell requires the primary output on exactly one axis",
            )
        output_axis = next(iter(output_axes))
        model = serialized.get("model", {})
        if model.get("kind") == "linear":
            control = serialized["controls"][0]
            input_axis = "y" if output_axis == "x" else "x"
            if any(point[input_axis].get("ref") == "control:" + control["id"] and point[output_axis].get("ref") == "output:" + model_output for point in serialized["view"]["points"]):
                endpoints = []
                for raw_input in (control["min"], control["max"]):
                    value = Decimal(model["intercept"]["value"])
                    for control_id, term in model["terms"]:
                        selected = raw_input if control_id == control["id"] else serialized["initialState"][control_id]
                        value += Decimal(selected) * Decimal(term["value"]["value"])
                    x_value, y_value = (value, Decimal(raw_input)) if output_axis == "x" else (Decimal(raw_input), value)
                    endpoints.append((_scatter_position(x_value, x_domain, plot_x, plot_w), plot_y + plot_h - _scatter_position(y_value, y_domain, Decimal(0), plot_h)))
                relationship_markup = (
                    f'<defs><clipPath id="LiveRelationshipClip"><rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}"/></clipPath></defs>'
                    f'<line id="LiveRelationship" x1="{endpoints[0][0]:.1f}" y1="{endpoints[0][1]:.1f}" x2="{endpoints[1][0]:.1f}" y2="{endpoints[1][1]:.1f}" stroke="{render_slide_spec.BLUE}" stroke-width="3" opacity="0.65" clip-path="url(#LiveRelationshipClip)"/>'
                )
        threshold_domain = x_domain if output_axis == "x" else y_domain
        threshold_position = min(threshold_domain[1], max(threshold_domain[0], threshold))
        threshold_label = (
            ("しきい値 " if serialized["locale"] == "ja" else "Threshold ")
            + display["thresholdText"]
        )
        if threshold < threshold_domain[0]:
            threshold_label += " · " + ("範囲未満" if serialized["locale"] == "ja" else "below range")
        elif threshold > threshold_domain[1]:
            threshold_label += " · " + ("範囲超過" if serialized["locale"] == "ja" else "above range")
        if output_axis == "x":
            threshold_x = _scatter_position(threshold_position, x_domain, plot_x, plot_w)
            label_on_right = threshold_x <= plot_x + plot_w / 2
            threshold_markup = render_slide_spec.line_el(
                float(threshold_x), float(plot_y), float(threshold_x),
                float(plot_y + plot_h), render_slide_spec.BLUE2, "6 6",
            ) + render_slide_spec.text_el(
                float(threshold_x + (Decimal(8) if label_on_right else Decimal(-8))),
                float(plot_y + Decimal(render_slide_spec.T_TICK + 6)),
                threshold_label,
                size=render_slide_spec.T_TICK, fill=render_slide_spec.BLUE2,
                weight="600", anchor="start" if label_on_right else "end",
            )
        else:
            threshold_y = plot_y + plot_h - _scatter_position(
                threshold_position, y_domain, Decimal(0), plot_h
            )
            threshold_label_y = threshold_y - Decimal(8)
            if threshold_label_y < plot_y + Decimal(render_slide_spec.T_TICK):
                threshold_label_y = threshold_y + Decimal(render_slide_spec.T_TICK + 6)
            threshold_markup = render_slide_spec.line_el(
                float(plot_x), float(threshold_y), float(plot_x + plot_w),
                float(threshold_y), render_slide_spec.BLUE2, "6 6",
            ) + render_slide_spec.text_el(
                float(plot_x + plot_w - 8), float(threshold_label_y), threshold_label,
                size=render_slide_spec.T_TICK, fill=render_slide_spec.BLUE2,
                weight="600", anchor="end",
            )
    if decision_range_message:
        threshold_markup += render_slide_spec.text_el(
            float(plot_x + 8), float(plot_y + 22), decision_range_message,
            size=render_slide_spec.T_TICK, fill=render_slide_spec.BLUE,
            weight="600", anchor="start",
        )
    point_markup: list[str] = []
    for point_index, point in enumerate(view["points"], start=1):
        x_value = Decimal(point["x"]["value"])
        y_value = Decimal(point["y"]["value"])
        cx = _scatter_position(x_value, x_domain, plot_x, plot_w)
        cy = plot_y + plot_h - _scatter_position(y_value, y_domain, Decimal(0), plot_h)
        emphasis = point["highlight"]
        radius = 9 if emphasis else 7
        point_markup.append(
            f'<circle id="{point["id"]}" cx="{float(cx):.1f}" cy="{float(cy):.1f}" '
            f'r="{radius}" fill="{render_slide_spec.BLUE if emphasis else render_slide_spec.GREY_MED}"/>'
        )
        label = (point["xText"] + " · " + point["yText"]) if serialized.get("type") == "slider_model" and len(view["points"]) == 1 else point["label"]
        if point["removed"]:
            label += " · " + ("除外" if serialized["locale"] == "ja" else "Removed")
        if label:
            label_id = _live_svg_id("LivePointLabel", point["id"], point_index)
            raw_width = render_slide_spec._text_width(label) * render_slide_spec.T_LABEL * 0.62
            clip_left = float(render_slide_spec.ML)
            clip_right = 830.0
            right_x = float(cx) + radius + 8
            left_x = float(cx) - radius - 8
            right_available = clip_right - right_x
            left_available = left_x - clip_left
            if raw_width <= right_available or (
                raw_width > left_available and right_available >= left_available
            ):
                label_x, anchor = right_x, "start"
                available = right_available
            else:
                label_x, anchor = left_x, "end"
                available = left_available
            width_units = max(int(max(available, 0) / (render_slide_spec.T_LABEL * 0.62)), 1)
            clamped = render_slide_spec.wrap(label, width_units, max_lines=1)[0]
            baseline = float(cy) + 7
            clip_top = float(plot_y)
            clip_bottom = float(plot_y + plot_h)
            if baseline + 4 > clip_bottom:
                baseline = float(cy) - radius - 8
            elif baseline - render_slide_spec.T_LABEL < clip_top:
                baseline = float(cy) + radius + render_slide_spec.T_LABEL
            baseline = min(
                clip_bottom - 4,
                max(clip_top + render_slide_spec.T_LABEL, baseline),
            )
            visible_width = (
                render_slide_spec._text_width(clamped)
                * render_slide_spec.T_LABEL
                * 0.62
            )
            point_markup.append(render_slide_spec.text_el(
                label_x,
                baseline,
                clamped,
                size=render_slide_spec.T_LABEL,
                fill=render_slide_spec.BLACK if emphasis else render_slide_spec.GREY_DARK,
                weight="600" if emphasis else "normal",
                anchor=anchor,
                title=label,
            ).replace(
                "<text ",
                f'<text id="{label_id}" '
                f'data-label-width="{visible_width:.1f}" ',
                1,
            ))
    geometry = (
        '<defs><clipPath id="LiveChartClip"><rect x="80" y="208" width="750" height="352" fill="#FFFFFF"/></clipPath></defs>'
        '<g id="LiveChartBand" clip-path="url(#LiveChartClip)">'
        '<rect x="80" y="208" width="750" height="352" fill="#FFFFFF"/>'
        + relationship_markup + threshold_markup
        + "".join(point_markup)
        + '</g>'
    )
    parts.extend(render_slide_spec.footer(shell_spec))
    body = render_slide_spec.apply_palette("\n  ".join(parts), shell_spec)
    geometry = render_slide_spec.apply_palette(geometry, shell_spec)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">\n'
        '  <rect width="1280" height="720" fill="#FFFFFF"/>\n'
        f'  {geometry}\n  {body}\n</svg>\n'
    )


def normalize_raw_range(raw: str, *, minimum: Decimal, maximum: Decimal, step: Decimal) -> str:
    """Normalize one untrusted fragment decimal without widening author limits."""
    if not isinstance(raw, str) or len(raw) > 128 or not _RAW_DECIMAL.fullmatch(raw):
        _fail("fragment_number", "<fragment>", "expected ordinary signed decimal text up to 128 characters")
    value = Fraction(raw)
    lo, hi, increment = Fraction(minimum), Fraction(maximum), Fraction(step)
    if not lo < hi or increment <= 0 or (hi - lo) % increment:
        _fail("fragment_number", "<fragment>", "invalid declared range grid")
    if value <= lo:
        accepted = lo
    elif value >= hi:
        accepted = hi
    else:
        steps = (value - lo) / increment
        accepted = lo + round_scaled(steps.numerator, steps.denominator) * increment
        accepted = min(hi, max(lo, accepted))
    decimal = Decimal(accepted.numerator) / Decimal(accepted.denominator)
    return canonical_decimal(decimal)


def _retained_scene_state_count(scene: dict, location: str) -> int:
    if not isinstance(scene, dict):
        _fail("scene_shape", location, "scene must be an object")
    scene_type = scene.get("type")
    if scene_type == "evidence_only":
        has_sources = bool(scene.get("sources"))
        has_assumptions = bool(scene.get("assumptions"))
        return 1 + int(has_sources) + int(has_assumptions) + int(
            has_sources and has_assumptions
        )
    if scene_type in ("drilldown", "accordion"):
        collection = "panels" if scene_type == "drilldown" else "items"
        panels = scene.get(collection)
        if not isinstance(panels, list):
            _fail(
                "scene_shape",
                location + "/" + collection,
                "disclosure states must be a bounded array",
            )
        if scene_type == "drilldown":
            return len(panels) + 1
        allow_none = scene.get("allowNone")
        if type(allow_none) is not bool:
            _fail(
                "scene_shape",
                location + "/allowNone",
                "accordion state cost requires an explicit allowNone flag",
            )
        return len(panels) + int(allow_none)
    controls = scene.get("controls", [])
    if not isinstance(controls, list) or len(controls) > 8:
        _fail("scene_shape", location + "/controls", "scene controls must be a bounded array")
    combinations = 1
    for index, control in enumerate(controls):
        here = f"{location}/controls/{index}"
        if not isinstance(control, dict):
            _fail("scene_shape", here, "scene control must be an object")
        kind = control.get("kind")
        if kind == "range":
            values = []
            for key in ("min", "max", "step"):
                value = control.get(key)
                if not isinstance(value, Decimal) or not value.is_finite():
                    _fail("scene_shape", here + "/" + key, "range grid must use finite exact numbers")
                fractional = max(0, -value.as_tuple().exponent)
                if abs(value) > Decimal("1000000000000") or fractional > 6:
                    _fail("scene_shape", here + "/" + key, "range grid exceeds the numeric contract")
                values.append(value)
            minimum, maximum, step = values
            if not minimum < maximum or step <= 0:
                _fail("scene_shape", here, "range grid must be positive and ordered")
            positions = (maximum - minimum) / step
            if positions != positions.to_integral_value() or positions > 10_000:
                _fail("scene_shape", here + "/step", "range grid exceeds 10,001 accepted states")
            combinations *= int(positions) + 1
        elif kind in ("segmented", "toggle", "select"):
            options = control.get("options")
            maximum = 2 if kind == "toggle" else 8 if kind == "select" else 4
            if not isinstance(options, list) or not 2 <= len(options) <= maximum:
                _fail("scene_shape", here + "/options", "control options exceed the accepted-state contract")
            combinations *= len(options)
        else:
            _fail("scene_shape", here + "/kind", "unsupported control kind")
        if combinations > MAX_ACCEPTED_STATES_PER_DECK:
            _fail("aggregate_limit", "<deck>", "accepted states exceed the deck budget")
    return combinations


def _runtime_supports_scene(scene: object) -> bool:
    """Return whether one compiler-owned scene has a Task 5 runtime shape."""
    if not isinstance(scene, dict) or scene.get("type") not in _RUNTIME_SCENE_TYPES:
        return False
    controls = scene.get("controls")
    if not isinstance(controls, list) or not all(
        isinstance(control, dict)
        and control.get("kind") in _RUNTIME_CONTROL_KINDS
        for control in controls
    ):
        return False
    scene_type = scene["type"]
    model = scene.get("model")
    authored_view = scene.get("view")
    evaluated_view = scene.get("initialEvaluation", {}).get("view")
    evaluated_component = (
        evaluated_view.get("component") if isinstance(evaluated_view, dict) else None
    )
    if scene_type in ("evidence_only", "drilldown", "accordion"):
        return model is None and authored_view is None and evaluated_view is None and not controls
    if scene_type == "state_toggle":
        return (
            isinstance(model, dict)
            and model.get("kind") == "state_map"
            and authored_view is None
            and evaluated_component in ("bar_compare", "ranked_list", "dot_plot")
            and len(controls) == 1
            and controls[0].get("kind") in ("segmented", "select")
        )
    if not isinstance(model, dict) or not isinstance(authored_view, dict):
        return False
    component = authored_view.get("component")
    if component != evaluated_component:
        return False
    if scene_type == "slider_model":
        return (
            model.get("kind") in _RUNTIME_NUMERIC_MODEL_KINDS
            and component in ("bar_compare", "dot_plot")
            and len(controls) == 1
            and controls[0].get("kind") == "range"
        )
    return (
        scene_type == "score_model"
        and model.get("kind") == "score_sum"
        and component == "recommendation_panel"
        and 2 <= len(controls) <= 8
    )


def compile_manifest(manifest_path: Path, *, title: str | None = None) -> CompiledDeck:
    try:
        manifest_path = Path(manifest_path).resolve(strict=True)
    except (OSError, RuntimeError):
        _fail("missing_file", str(manifest_path), "manifest does not resolve to a file")
    budget = _JsonBudget()
    with _RootReader(manifest_path.parent) as reader:
        manifest_data = reader.read(manifest_path, MAX_MANIFEST_BYTES, "input_limit")
        manifest = _strict_json_bytes(
            manifest_data,
            str(manifest_path),
            exact_numbers=False,
            budget=budget,
        )
        spec_inputs, scene_inputs = _preflight_paths(manifest, manifest_path, reader)
    exact_specs = [
        _strict_json_bytes(item.data, str(item.path), exact_numbers=True, budget=budget)
        for item in spec_inputs
    ]
    exact_scenes = [
        None
        if item is None
        else _strict_json_bytes(item.data, str(item.path), exact_numbers=True, budget=budget)
        for item in scene_inputs
    ]
    accepted_states = 0
    for ordinal, scene in enumerate(exact_scenes, start=1):
        if scene is None:
            continue
        accepted_states += _retained_scene_state_count(scene, f"slide:{ordinal}/scene")
        if accepted_states > MAX_ACCEPTED_STATES_PER_DECK:
            _fail("aggregate_limit", "<deck>", "accepted states exceed the deck budget")
    has_scene = any(item is not None for item in scene_inputs)
    lang = manifest.get("lang")
    if lang is None:
        if has_scene:
            _fail("language", str(manifest_path) + "/lang", "scene-bearing manifests require en or ja")
        lang = "en"
    if lang not in ("en", "ja"):
        _fail("language", str(manifest_path) + "/lang", "interactive language must be en or ja")
    deck_title = title if title is not None else manifest.get("title", "Slide Deck")
    if not isinstance(deck_title, str) or len(deck_title) > 500:
        _fail("title", str(manifest_path) + "/title", "deck title must be text within 500 characters")
    fallback_work = 0
    estimated_elements = 0
    for ordinal, (spec, scene) in enumerate(zip(exact_specs, exact_scenes), start=1):
        fallback_work += _validate_fallback_spec(
            spec, f"slide:{ordinal}/spec", scene_adapter=scene is not None
        )
        _validate_summary_preflight(
            _static_summary(spec, f"Slide {ordinal}", lang=lang),
            f"slide:{ordinal}/staticSummary",
        )
        slide_elements = _estimate_fallback_elements(spec)
        if scene is not None:
            fallback_work += 128  # fixed live-shell and semantic companion allowance
            slide_elements += LIVE_SHELL_ELEMENT_ALLOWANCE
        if slide_elements > MAX_ESTIMATED_FALLBACK_ELEMENTS_PER_SLIDE:
            _fail("fallback_limit", f"slide:{ordinal}/spec", "fallback element estimate exceeds the per-slide limit")
        estimated_elements += slide_elements
        if fallback_work > MAX_FALLBACK_WORK_PER_DECK:
            _fail("fallback_limit", "<deck>", "fallback render work exceeds the deck limit")
        if estimated_elements > MAX_ESTIMATED_FALLBACK_ELEMENTS_PER_DECK:
            _fail("fallback_limit", "<deck>", "fallback element estimate exceeds the deck limit")
    # The shared normalizer is intentionally called exactly once. Interactive
    # confinement above is stricter; classic consumers retain their contract.
    normalized = normalize_manifest(manifest, manifest_path, interactive=True)
    if len(normalized) != len(spec_inputs):
        _fail("manifest_shape", str(manifest_path), "manifest normalization changed slide count")
    slide_ids = validate_interactive_slide_ids([entry.slide_id for entry in normalized], Location(str(manifest_path), "/slides"))
    bundle_slides: list[BundleSlide] = []
    author_records: list[object] = []
    for ordinal, (entry, spec_input, scene_input, exact_spec, exact_scene) in enumerate(
        zip(normalized, spec_inputs, scene_inputs, exact_specs, exact_scenes),
        start=1,
    ):
        renderer_spec = _renderer_spec_copy(exact_spec)
        try:
            fallback_raw = render_slide_spec.render(copy.deepcopy(renderer_spec))
        except Exception:
            _fail("fallback_render", f"slide:{ordinal}/spec", "validated fallback renderer failed")
        fallback_svg = validate_renderer_svg(fallback_raw, slide_ordinal=ordinal, role="fallback")
        summary = _static_summary(exact_spec, f"Slide {ordinal}", lang=lang)
        headline = summary["headline"]
        source = summary["source"]
        if scene_input is None:
            bundle_slides.append(BundleSlide(
                slide_id=entry.slide_id, headline=headline, source=source,
                fallback_svg=fallback_svg, static_summary=summary,
                scene=None, live_shell_svg=None, display=None,
            ))
            continue
        result = compile_scene(
            LocatedDocument(exact_scene, Location(str(scene_input.path))),
            fallback_spec=exact_spec,
            fallback_path=spec_input.path,
            slide_id=entry.slide_id,
            slide_ids=slide_ids,
            lang=lang,
        )
        serialized = serialize_compiled_scene(result.compiled)
        if not _runtime_supports_scene(serialized):
            _fail("runtime_unsupported", str(scene_input.path), "scene/model/view combination is not supported by the runtime")
        display = _scene_display(result, serialized, exact_spec, lang)
        legacy_task4 = (
            serialized["type"] == "slider_model"
            and serialized.get("model", {}).get("kind") == "linear"
            and serialized.get("view", {}).get("component") == "dot_plot"
        )
        if not legacy_task4:
            serialized["fallback"]["paragraphs"] = copy.deepcopy(
                display["staticSummary"]["paragraphs"]
            )
            serialized["fallback"]["baselineAnnotation"] = display["baselineAnnotation"]
            serialized["fallback"]["thresholdText"] = display["thresholdText"]
            serialized["fallback"]["axisTickLabels"] = copy.deepcopy(
                display["axisTickLabels"]
            )
        decision_range_message = None
        if result.audit.missing_outcomes:
            decision_range_message = (
                "検証範囲内では判定は変わりません"
                if lang == "ja"
                else "No decision change within the tested range"
            )
        live_raw = _live_shell(
            renderer_spec,
            serialized,
            display,
            decision_range_message=decision_range_message,
        )
        live_svg = validate_renderer_svg(live_raw, slide_ordinal=ordinal, role="live-shell")
        bundle_slides.append(BundleSlide(
            slide_id=entry.slide_id, headline=headline, source=source,
            fallback_svg=fallback_svg, static_summary=display["staticSummary"],
            scene=serialized, live_shell_svg=live_svg, display=display,
            decision_range_message=decision_range_message,
            visual_layout="rank_bridge" if _rank_bridge_layout(renderer_spec, serialized.get("initialEvaluation", {}).get("view", {})) else None,
        ))
        author_records.append(result)
    return CompiledDeck(deck_title, lang, tuple(bundle_slides), tuple(author_records))


def build_deck(manifest_path: Path, *, title: str | None = None) -> str:
    compiled = compile_manifest(manifest_path, title=title)
    return bundle_deck(
        title=compiled.title,
        lang=compiled.lang,
        slides=compiled.slides,
        assets=load_runtime_assets(),
    )


def _atomic_write(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


class _CliUsageError(Exception):
    pass


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _CliUsageError


def main(argv: list[str] | None = None) -> int:
    parser = _SafeArgumentParser(description="Build a self-contained interactive companion deck.")
    parser.add_argument("--manifest", required=True, help="Deck manifest JSON")
    parser.add_argument("-o", "--output", required=True, help="Interactive HTML output")
    parser.add_argument("--title", help="Artifact-only browser title override")
    try:
        args = parser.parse_args(argv)
    except _CliUsageError:
        import sys
        print("ERROR: interactive deck build failed [cli_usage]", file=sys.stderr)
        return 2
    try:
        output = Path(args.output)
        if not output.name.endswith(".interactive.html"):
            _fail(
                "output_name",
                str(output),
                "interactive companion output must end with .interactive.html",
            )
        html_text = build_deck(Path(args.manifest), title=args.title)
        _atomic_write(output, html_text)
    except Exception as error:
        import sys
        if isinstance(error, BundleValidationError) and error.issues:
            code = error.issues[0].code
        elif isinstance(error, SceneValidationError):
            code = "scene_validation"
        elif isinstance(error, (OSError, ValueError)):
            code = "build_error"
        else:
            code = "internal_error"
        print(f"ERROR: interactive deck build failed [{code}]", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
