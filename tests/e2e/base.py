"""Deterministic Playwright harness for the interactive deck.

This module intentionally has no import path from the stdlib-only core test
suite.  It is loaded only by ``unittest discover -s tests/e2e`` after the
separately pinned Playwright dependency and browser binaries are installed.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from typing import Iterator
import unittest
from urllib.parse import urlsplit

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts" / "build_interactive_deck.py"
ENVELOPE_RE = re.compile(
    r'(<div id="idrt-deck-data" hidden data-encoding="base64url-json-v1">)'
    r'([A-Za-z0-9_-]+)(</div>)'
)

PROVENANCE = {"basis": "illustrative", "assumptionRefs": ["synthetic-inputs"]}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_exact_json(path: Path, value: object) -> None:
    """Write Decimal instances as JSON numbers without a float round trip."""
    replacements: dict[str, str] = {}

    def replace(node: object) -> object:
        if isinstance(node, Decimal):
            marker = f"__E2E_DECIMAL_{len(replacements)}__"
            replacements[marker] = str(node)
            return marker
        if isinstance(node, dict):
            return {key: replace(item) for key, item in node.items()}
        if isinstance(node, list):
            return [replace(item) for item in node]
        return node

    text = json.dumps(replace(value), ensure_ascii=False, indent=2)
    for marker, token in replacements.items():
        text = text.replace(json.dumps(marker), token)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def _static_spec(*, poison: str = "") -> dict:
    suffix = (" " + poison) if poison else ""
    return {
        "pattern": "bullet_list",
        "headline": "A focused queue pilot can test the operating model in one week" + suffix,
        "source": "Illustrative service design exercise",
        "classification": "Illustrative",
        "page_number": 1,
        "bullets": [
            {"text": "Start with one bounded queue", "emphasis": True},
            {"text": "Measure capacity before expanding scope"},
        ],
    }


def _slider_scene(*, poison: str = "") -> dict:
    suffix = (" " + poison) if poison else ""
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
            "label": "Illustrative method note" + suffix,
            "detail": "Original reference-fixture link used only to verify safe explicit navigation." + suffix,
            "url": "https://example.com/method",
        }],
        "assumptions": [{
            "id": "synthetic-inputs",
            "label": "All values are synthetic" + suffix,
            "value": "Reference-deck validation only" + suffix,
        }],
        "controls": [{
            "id": "automation",
            "kind": "range",
            "label": "Automation",
            "min": 0,
            "max": 80,
            "step": 5,
            "quantity": "automation_rate",
            "provenance": copy.deepcopy(PROVENANCE),
        }],
        "model": {
            "kind": "linear",
            "intercept": {"value": 18, "quantity": "weekly_capacity"},
            "terms": {"automation": {
                "coefficient": 0.4,
                "inputQuantity": "automation_rate",
                "outputQuantity": "weekly_capacity",
            }},
            "output": "capacity",
            "outputQuantity": "weekly_capacity",
            "label": "Weekly capacity",
            "format": "number",
            "round": 0,
            "modelProvenance": copy.deepcopy(PROVENANCE),
        },
        "reporting": {"primaryOutput": "capacity", "secondaryOutputs": []},
        "decisionContract": {
            "id": "demand-gate",
            "metric": {"ref": "output:capacity"},
            "operator": "gte",
            "threshold": {
                "value": 32,
                "quantity": "weekly_capacity",
                "provenance": copy.deepcopy(PROVENANCE),
            },
            "whenMet": {"status": "Ready", "recommendation": "Run a limited queue pilot"},
            "whenNotMet": {
                "status": "Below demand",
                "recommendation": "Increase automation before the pilot",
            },
        },
        "view": {
            "component": "dot_plot",
            "xLabel": "Automation",
            "xQuantity": "automation_rate",
            "xDomain": [0, 80],
            "yLabel": "Weekly capacity",
            "yQuantity": "weekly_capacity",
            "yDomain": [0, 50],
            "points": [{
                "id": "service-capacity",
                "label": "Weekly capacity",
                "x": {"ref": "control:automation"},
                "y": {"ref": "output:capacity"},
                "highlight": True,
            }],
        },
        "demo": [
            {"stepKey": "reach-threshold", "action": "set", "control": "automation", "value": 35},
            {"stepKey": "show-evidence", "action": "openEvidence"},
        ],
    }


def _slider_spec() -> dict:
    return {
        "pattern": "scatter",
        "headline": "The queue pilot meets demand at 35% automation or more",
        "source": "Illustrative service design exercise",
        "footnotes": ["All values are synthetic and intended only for runtime validation."],
        "classification": "Illustrative",
        "page_number": 2,
        "x_axis": {
            "label": "Automation",
            "quantity": "automation_rate",
            "unit": "%",
            "domain": [0, 80],
            "tick_labels": ["0%", "80%"],
        },
        "y_axis": {
            "label": "Weekly capacity",
            "quantity": "weekly_capacity",
            "unit": "cases/wk",
            "domain": [0, 50],
            "tick_labels": ["0 cases/wk", "50 cases/wk"],
        },
        "points": [{
            "item_id": "service-capacity",
            "label": "Weekly capacity",
            "x": 20,
            "y": 26,
            "emphasis": True,
        }],
        "interactive_result": {
            "quantity": "weekly_capacity",
            "value": 26,
            "decision_status": "Below demand",
            "recommendation": "Increase automation before the pilot",
            "operator": "gte",
            "threshold": 32,
        },
        "annotation": (
            "Weekly capacity 26 cases/wk; Below demand; threshold ≥ 32 cases/wk; "
            "Increase automation before the pilot"
        ),
    }


def write_mixed_fixture(
    root: Path,
    *,
    poison: str = "",
    lang: str = "en",
    second_interactive: bool = False,
) -> Path:
    """Write the original two-page queue fixture and return its manifest."""
    _write_json(root / "specs/01-summary.json", _static_spec(poison=poison))
    slider_spec = _slider_spec()
    if lang == "ja":
        slider_spec["annotation"] = (
            "Weekly capacity 26 cases/wk; Below demand; しきい値 ≥ 32 cases/wk; "
            "Increase automation before the pilot"
        )
    _write_json(root / "specs/02-capacity.json", slider_spec)
    _write_json(root / "scenes/02-capacity.json", _slider_scene(poison=poison))
    slides: list[object] = [
        "specs/01-summary.json",
        {
            "id": "queue-capacity",
            "spec": "specs/02-capacity.json",
            "scene": "scenes/02-capacity.json",
        },
    ]
    if second_interactive:
        second_spec = copy.deepcopy(slider_spec)
        second_spec["page_number"] = 3
        _write_json(root / "specs/03-capacity.json", second_spec)
        _write_json(root / "scenes/03-capacity.json", _slider_scene(poison=poison))
        slides.append({
            "id": "queue-capacity-copy",
            "spec": "specs/03-capacity.json",
            "scene": "scenes/03-capacity.json",
        })
    manifest = {
        "title": "Service queue pilot" + ((" " + poison) if poison else ""),
        "lang": lang,
        "slides": slides,
    }
    _write_json(root / "deck.json", manifest)
    return root / "deck.json"


def build_fixture(
    root: Path,
    *,
    poison: str = "",
    lang: str = "en",
    second_interactive: bool = False,
    scene_purpose: str | None = None,
    point_id: str | None = None,
    source_url: str | None = None,
    output_axis: str = "y",
    output_name: str = "deck.interactive.html",
) -> Path:
    manifest = write_mixed_fixture(
        root,
        poison=poison,
        lang=lang,
        second_interactive=second_interactive,
    )
    if (
        scene_purpose is not None
        or point_id is not None
        or source_url is not None
        or output_axis != "y"
    ):
        spec_path = root / "specs/02-capacity.json"
        scene_path = root / "scenes/02-capacity.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        scene = json.loads(scene_path.read_text(encoding="utf-8"))
        if scene_purpose is not None:
            scene["purpose"] = scene_purpose
        if point_id is not None:
            spec["points"][0]["item_id"] = point_id
            scene["view"]["points"][0]["id"] = point_id
        if source_url is not None:
            scene["sources"][0]["url"] = source_url
        if output_axis == "x":
            spec["x_axis"], spec["y_axis"] = spec["y_axis"], spec["x_axis"]
            spec["points"][0]["x"], spec["points"][0]["y"] = (
                spec["points"][0]["y"],
                spec["points"][0]["x"],
            )
            view = scene["view"]
            for first, second in (
                ("xLabel", "yLabel"),
                ("xQuantity", "yQuantity"),
                ("xDomain", "yDomain"),
            ):
                view[first], view[second] = view[second], view[first]
            view["points"][0]["x"], view["points"][0]["y"] = (
                view["points"][0]["y"],
                view["points"][0]["x"],
            )
        elif output_axis != "y":
            raise ValueError(f"unknown output axis: {output_axis}")
        _write_json(spec_path, spec)
        _write_json(scene_path, scene)
    output = root / output_name
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
    if completed.returncode:
        raise AssertionError(
            "fixture build failed: "
            + completed.stderr.replace(str(root), "<fixture>").strip()
        )
    return output


def build_numeric_edge_fixture(
    root: Path,
    *,
    minimum: Decimal,
    maximum: Decimal,
    step: Decimal,
    initial: Decimal,
    intercept: Decimal,
    coefficient: Decimal,
    expected: Decimal,
    display_precision: int,
    expected_text: str,
    threshold: Decimal,
    threshold_text: str,
    output_name: str,
    view_y_max: Decimal | None = None,
) -> Path:
    """Build one exact-decimal browser oracle without using binary floats."""
    _write_json(root / "specs/01-summary.json", _static_spec())
    met = expected >= threshold
    status = "Ready" if met else "Below demand"
    recommendation = "Proceed" if met else "Hold"
    def axis_tick(value: Decimal, unit: str) -> str:
        precision = max(0, -value.as_tuple().exponent)
        number = format(abs(value), f",.{precision}f")
        return ("−" if value < 0 else "") + number + " " + unit

    x_low = axis_tick(minimum, "x")
    x_high = axis_tick(maximum, "x")
    scale = max(
        max(0, -value.as_tuple().exponent)
        for value in (minimum, maximum, step, initial, intercept, coefficient, expected, threshold)
    )
    quantum = Decimal(1).scaleb(-scale)
    normalize = lambda value: value.quantize(quantum, rounding=ROUND_HALF_UP)
    y_bounds = sorted((
        expected,
        threshold,
        intercept,
        normalize(intercept + coefficient * minimum),
        normalize(intercept + coefficient * maximum),
        Decimal("0"),
    ))
    y_min = y_bounds[0]
    y_max = y_bounds[-1]
    if y_min == y_max:
        y_max += Decimal("1")
    if view_y_max is not None:
        if view_y_max <= y_min:
            raise ValueError("view_y_max must be greater than the lower y domain")
        y_max = view_y_max
    y_low_text = axis_tick(y_min, "units")
    y_high_text = axis_tick(y_max, "units")
    domain_reason = (
        "The synthetic edge case requires a nonzero plotting origin."
        if minimum != 0 or y_min != 0
        else None
    )
    spec = {
        "pattern": "scatter",
        "headline": "Exact decimal runtime parity",
        "source": "Illustrative runtime oracle",
        "classification": "Illustrative",
        "page_number": 2,
        "x_axis": {
            "label": "Input",
            "quantity": "automation_rate",
            "unit": "x",
            "domain": [minimum, maximum],
            "tick_labels": [x_low, x_high],
        },
        "y_axis": {
            "label": "Result",
            "quantity": "weekly_capacity",
            "unit": "units",
            "domain": [y_min, y_max],
            "tick_labels": [y_low_text, y_high_text],
        },
        "points": [{
            "item_id": "edge-result",
            "label": "Edge result",
            "x": initial,
            "y": expected,
            "emphasis": True,
        }],
        "interactive_result": {
            "quantity": "weekly_capacity",
            "value": expected,
            "decision_status": status,
            "recommendation": recommendation,
            "operator": "gte",
            "threshold": threshold,
        },
        "annotation": (
            f"Edge result {expected_text}; {status}; threshold ≥ {threshold_text}; {recommendation}"
        ),
    }
    if domain_reason is not None:
        spec["domain_reason"] = domain_reason
    scene = {
        "version": 1,
        "type": "slider_model",
        "purpose": "Verify exact fixed-scale arithmetic",
        "decisionJob": "decision",
        "interactionRationale": "Expose parity at an exact numeric boundary",
        "initialState": {"automation": initial},
        "printState": {"automation": initial},
        "quantities": {
            "automation_rate": {"dimension": "ratio", "unit": "percentage_point", "display": "x"},
            "weekly_capacity": {"dimension": "count", "unit": "cases_per_week", "display": "units"},
        },
        "sources": [],
        "assumptions": [{
            "id": "synthetic-inputs",
            "label": "All values are synthetic",
            "value": "Exact runtime oracle only",
        }],
        "controls": [{
            "id": "automation",
            "kind": "range",
            "label": "Input",
            "min": minimum,
            "max": maximum,
            "step": step,
            "quantity": "automation_rate",
            "provenance": copy.deepcopy(PROVENANCE),
        }],
        "model": {
            "kind": "linear",
            "intercept": {"value": intercept, "quantity": "weekly_capacity"},
            "terms": {"automation": {
                "coefficient": coefficient,
                "inputQuantity": "automation_rate",
                "outputQuantity": "weekly_capacity",
            }},
            "output": "capacity",
            "outputQuantity": "weekly_capacity",
            "label": "Edge result",
            "format": "number",
            "round": display_precision,
            "modelProvenance": copy.deepcopy(PROVENANCE),
        },
        "reporting": {"primaryOutput": "capacity", "secondaryOutputs": []},
        "decisionContract": {
            "id": "edge-gate",
            "metric": {"ref": "output:capacity"},
            "operator": "gte",
            "threshold": {
                "value": threshold,
                "quantity": "weekly_capacity",
                "provenance": copy.deepcopy(PROVENANCE),
            },
            "whenMet": {"status": "Ready", "recommendation": "Proceed"},
            "whenNotMet": {"status": "Below demand", "recommendation": "Hold"},
        },
        "view": {
            "component": "dot_plot",
            "xLabel": "Input",
            "xQuantity": "automation_rate",
            "xDomain": [minimum, maximum],
            "yLabel": "Result",
            "yQuantity": "weekly_capacity",
            "yDomain": [y_min, y_max],
            "points": [{
                "id": "edge-result",
                "label": "Edge result",
                "x": {"ref": "control:automation"},
                "y": {"ref": "output:capacity"},
                "highlight": True,
            }],
        },
    }
    if domain_reason is not None:
        scene["view"]["domainReason"] = domain_reason
    _write_exact_json(root / "specs/02-edge.json", spec)
    _write_exact_json(root / "scenes/02-edge.json", scene)
    _write_json(root / "deck.json", {
        "title": "Exact decimal runtime parity",
        "lang": "en",
        "slides": [
            "specs/01-summary.json",
            {"id": "queue-capacity", "spec": "specs/02-edge.json", "scene": "scenes/02-edge.json"},
        ],
    })
    output = root / output_name
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(BUILD_SCRIPT), "--manifest", str(root / "deck.json"), "-o", str(output)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise AssertionError("numeric fixture build failed: " + completed.stderr.strip())
    return output


def decode_envelope_text(html_text: str) -> tuple[dict, str]:
    match = ENVELOPE_RE.search(html_text)
    if not match:
        raise AssertionError("deck envelope not found")
    encoded = match.group(2)
    padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
    raw = base64.urlsafe_b64decode(padded).decode("utf-8")
    return json.loads(raw), raw


def encode_unchecked_json_text(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def replace_envelope_text(html_text: str, raw: str) -> str:
    encoded = encode_unchecked_json_text(raw)
    match = ENVELOPE_RE.search(html_text)
    if not match:
        raise AssertionError("deck envelope not found")
    return html_text[:match.start(2)] + encoded + html_text[match.end(2):]


class _QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, request_log: list[str], **kwargs):
        self._request_log = request_log
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback name
        self._request_log.append(self.path)
        super().do_GET()

    def log_message(self, _format: str, *args: object) -> None:
        return


class LoopbackServer:
    def __init__(self, root: Path):
        self.requests: list[str] = []
        handler = partial(_QuietHandler, directory=str(root), request_log=self.requests)
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._started = False

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()
        self._started = True

    def close(self) -> None:
        if self._started:
            self._server.shutdown()
        self._server.server_close()
        if self._started:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise AssertionError("loopback server did not stop")
            self._started = False


MONITOR_INIT_SCRIPT = r"""
(() => {
  const records = {
    transports: [],
    popups: [],
    forms: [],
    scriptedClicks: [],
    csp: [],
    hashes: [],
    deckEvents: [],
    eventAudits: [],
    windowHandlers: {error: 0, unhandledrejection: 0},
    faults: { phase: null }
  };
  Object.defineProperty(window, "__E2E_MONITOR__", {value: records, configurable: false});
  const note = (kind, detail) => records.transports.push({kind, detail: String(detail || "").slice(0, 160)});

  if (typeof window.fetch === "function") {
    const original = window.fetch;
    window.fetch = function(input, init) { note("fetch", input && input.url ? input.url : input); return original.call(this, input, init); };
  }
  if (typeof window.XMLHttpRequest === "function") {
    const open = window.XMLHttpRequest.prototype.open;
    window.XMLHttpRequest.prototype.open = function(method, url) { note("xhr", url); return open.apply(this, arguments); };
  }
  for (const name of ["WebSocket", "EventSource", "Worker", "SharedWorker", "WebTransport", "RTCPeerConnection", "BroadcastChannel", "MessageChannel"]) {
    const Original = window[name];
    if (typeof Original === "function") {
      window[name] = function() { note(name, arguments[0]); return Reflect.construct(Original, Array.from(arguments), new.target || Original); };
      window[name].prototype = Original.prototype;
    }
  }
  if (navigator.sendBeacon) {
    const beacon = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = function(url, data) { note("sendBeacon", url); return beacon(url, data); };
  }
  const postMessage = window.postMessage;
  window.postMessage = function(message, targetOrigin) {
    note("postMessage", targetOrigin);
    return postMessage.apply(this, arguments);
  };
  if (navigator.serviceWorker && navigator.serviceWorker.register) {
    const register = navigator.serviceWorker.register.bind(navigator.serviceWorker);
    navigator.serviceWorker.register = function(url) {
      note("serviceWorker", url);
      return register.apply(this, arguments);
    };
  }
  const open = window.open;
  window.open = function(url) { records.popups.push(String(url || "")); return open.apply(this, arguments); };
  const submit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function() { records.forms.push("submit"); return submit.apply(this, arguments); };
  if (HTMLFormElement.prototype.requestSubmit) {
    const requestSubmit = HTMLFormElement.prototype.requestSubmit;
    HTMLFormElement.prototype.requestSubmit = function() { records.forms.push("requestSubmit"); return requestSubmit.apply(this, arguments); };
  }
  const click = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function() { records.scriptedClicks.push(this.href); return click.apply(this, arguments); };
  const replaceState = History.prototype.replaceState;
  History.prototype.replaceState = function() {
    if (records.faults.phase === "history") {
      throw new DOMException("E2E_SECRET history payload", "SecurityError");
    }
    return replaceState.apply(this, arguments);
  };

  const rawBigInt = window.BigInt;
  if (typeof rawBigInt === "function") {
    const monitoredBigInt = function(value) {
      if (records.faults.phase === "evaluation") throw new Error("E2E_SECRET evaluation payload");
      return rawBigInt(value);
    };
    Object.setPrototypeOf(monitoredBigInt, rawBigInt);
    monitoredBigInt.prototype = rawBigInt.prototype;
    window.BigInt = monitoredBigInt;
  }
  const text = Object.getOwnPropertyDescriptor(Node.prototype, "textContent");
  if (text && text.set) {
    Object.defineProperty(Node.prototype, "textContent", {
      configurable: text.configurable,
      enumerable: text.enumerable,
      get: text.get,
      set(value) {
        if (records.faults.phase === "text" && this instanceof Element &&
            this.closest && this.closest('[data-slide-id="queue-capacity"]') &&
            this.matches('dd, .scene-status, .decision-result strong, .decision-result p')) {
          throw new Error("E2E_SECRET text payload");
        }
        return text.set.call(this, value);
      }
    });
  }
  const setAttribute = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function(name, value) {
    if (records.faults.phase === "geometry" && (name === "cx" || name === "cy") &&
        this.closest && this.closest(".live-layer")) {
      throw new Error("E2E_SECRET geometry payload");
    }
    return setAttribute.call(this, name, value);
  };
  const elementFromPoint = Document.prototype.elementFromPoint;
  Document.prototype.elementFromPoint = function() {
    if (records.faults.phase === "pointer") {
      throw new Error("E2E_SECRET pointer payload");
    }
    return elementFromPoint.apply(this, arguments);
  };
  const tokenRemove = DOMTokenList.prototype.remove;
  DOMTokenList.prototype.remove = function() {
    if ((records.faults.phase === "touch" || records.faults.phase === "focus") &&
        Array.from(arguments).includes("is-idle")) {
      throw new Error("E2E_SECRET wake payload");
    }
    return tokenRemove.apply(this, arguments);
  };
  const hidden = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "hidden");
  if (hidden && hidden.set) {
    Object.defineProperty(HTMLElement.prototype, "hidden", {
      configurable: hidden.configurable,
      enumerable: hidden.enumerable,
      get: hidden.get,
      set(value) {
        if (records.faults.phase === "overlay" && value === false &&
            this.matches && this.matches(".evidence-dialog")) {
          throw new Error("E2E_SECRET overlay payload");
        }
        return hidden.set.call(this, value);
      }
    });
  }
  const raf = window.requestAnimationFrame;
  window.requestAnimationFrame = function(callback) {
    return raf.call(this, function(time) {
      if (records.faults.phase === "raf") throw new Error("E2E_SECRET raf payload");
      return callback(time);
    });
  };
  const timer = window.setTimeout;
  window.setTimeout = function(callback, delay) {
    return timer.call(this, function() {
      if (records.faults.phase === "timer") throw new Error("E2E_SECRET timer payload");
      return typeof callback === "function" ? callback.apply(this, arguments) : undefined;
    }, delay);
  };
  const add = window.addEventListener;
  window.addEventListener = function(type, listener, options) {
    if (Object.prototype.hasOwnProperty.call(records.windowHandlers, type)) {
      records.windowHandlers[type] += 1;
    }
    if (type === "hashchange" && typeof listener === "function") {
      return add.call(this, type, function(event) {
        if (records.faults.phase === "hash") throw new Error("E2E_SECRET hash payload");
        return listener.call(this, event);
      }, options);
    }
    return add.call(this, type, listener, options);
  };
  const remove = window.removeEventListener;
  window.removeEventListener = function(type, listener, options) {
    if (Object.prototype.hasOwnProperty.call(records.windowHandlers, type)) {
      records.windowHandlers[type] = Math.max(0, records.windowHandlers[type] - 1);
    }
    return remove.call(this, type, listener, options);
  };
  const dispatchEvent = EventTarget.prototype.dispatchEvent;
  EventTarget.prototype.dispatchEvent = function(event) {
    if (records.faults.phase === "ready" && event && event.type === "deck:ready") {
      throw new Error("E2E_SECRET ready payload");
    }
    return dispatchEvent.apply(this, arguments);
  };
  document.addEventListener("securitypolicyviolation", event => {
    records.csp.push({directive: event.effectiveDirective, blocked: String(event.blockedURI || "").slice(0, 160)});
  });
  window.addEventListener("hashchange", () => records.hashes.push(window.location.hash), true);
  const auditSnapshot = (detail, eventType) => {
    const errors = [];
    const ownKeys = value => Reflect.ownKeys(value).map(key =>
      typeof key === "symbol" ? `symbol:${String(key.description || "")}` : key
    );
    const exact = (value, expected, path, prototype) => {
      if (!value || typeof value !== "object") {
        errors.push(`${path}:object`);
        return false;
      }
      if (!Object.isFrozen(value)) errors.push(`${path}:not-frozen`);
      if (Object.getPrototypeOf(value) !== prototype) errors.push(`${path}:prototype`);
      const actual = ownKeys(value);
      if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        errors.push(`${path}:keys:${JSON.stringify(actual)}`);
      }
      return true;
    };
    if (exact(
      detail,
      ["currentSlide", "pages", "overlay", "reducedMotion"],
      "snapshot",
      Object.prototype
    )) {
      const pages = detail.pages;
      if (!Number.isInteger(detail.currentSlide) || detail.currentSlide < 1) {
        errors.push("snapshot.currentSlide");
      }
      if (typeof detail.reducedMotion !== "boolean") {
        errors.push("snapshot.reducedMotion");
      }
      const pageKeys = Array.isArray(pages)
        ? pages.map((_, index) => String(index)).concat("length")
        : [];
      if (exact(pages, pageKeys, "snapshot.pages", Array.prototype)) {
        pages.forEach((page, pageIndex) => {
          if (!exact(
            page,
            ["ordinal", "inputs", "outputs", "outcome", "viewMode", "failed"],
            `snapshot.pages[${pageIndex}]`,
            Object.prototype
          )) return;
          if (page.ordinal !== pageIndex + 1) {
            errors.push(`snapshot.pages[${pageIndex}].ordinal`);
          }
          for (const field of ["inputs", "outputs"]) {
            const collection = page[field];
            const path = `snapshot.pages[${pageIndex}].${field}`;
            if (collection && typeof collection === "object") {
              exact(collection, Object.keys(collection), path, Object.prototype);
              for (const [key, value] of Object.entries(collection)) {
                if (!/^[a-z][a-z0-9_-]{0,63}$/.test(key)) errors.push(`${path}:id`);
                if (typeof value !== "string" ||
                    !/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$/.test(value) ||
                    value === "-0") {
                  errors.push(`${path}.${key}:numeric`);
                }
              }
            } else {
              errors.push(`${path}:object`);
            }
          }
          if (![null, "met", "notMet"].includes(page.outcome)) errors.push(`snapshot.pages[${pageIndex}].outcome`);
          if (!["live", "static"].includes(page.viewMode)) errors.push(`snapshot.pages[${pageIndex}].viewMode`);
          if (![null, "unavailable"].includes(page.failed)) errors.push(`snapshot.pages[${pageIndex}].failed`);
        });
      }
      if (detail.overlay !== null) {
        exact(
          detail.overlay,
          ["kind", "ordinal", "tab"],
          "snapshot.overlay",
          Object.prototype
        );
        if (detail.overlay.kind !== "evidence" ||
            !Number.isInteger(detail.overlay.ordinal) ||
            detail.overlay.ordinal < 1 ||
            detail.overlay.ordinal > pages.length ||
            !["sources", "assumptions"].includes(detail.overlay.tab)) {
          errors.push("snapshot.overlay:value");
        }
      }
      if (Array.isArray(pages) && detail.currentSlide > pages.length) {
        errors.push("snapshot.currentSlide:range");
      }
    }
    let matchesSnapshot = false;
    try {
      matchesSnapshot = Boolean(
        window.InteractiveDeck &&
        typeof window.InteractiveDeck.snapshot === "function" &&
        JSON.stringify(detail) === JSON.stringify(window.InteractiveDeck.snapshot())
      );
    } catch (failure) {
      errors.push("snapshot:comparison-threw");
    }
    if (!matchesSnapshot) errors.push("snapshot:mismatch");
    return {type: eventType, valid: errors.length === 0, matchesSnapshot, errors};
  };
  const recordDeckEvent = (type, event) => {
    records.eventAudits.push(auditSnapshot(event.detail, type));
    records.deckEvents.push({type, detail: event.detail});
  };
  document.addEventListener("deck:ready", event => recordDeckEvent("ready", event));
  document.addEventListener("deck:state", event => recordDeckEvent("state", event));
})();
"""


@dataclass
class Observations:
    requests: list[str] = field(default_factory=list)
    blocked_requests: list[str] = field(default_factory=list)
    consoles: list[tuple[str, str]] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    popups: list[str] = field(default_factory=list)
    downloads: list[str] = field(default_factory=list)
    navigations: list[str] = field(default_factory=list)


@dataclass
class BrowserSession:
    engine: str
    mode: str
    context: BrowserContext
    page: Page
    url: str
    observations: Observations
    server_requests: list[str]
    server_request_start: int
    java_script_enabled: bool

    def monitor(self) -> dict:
        return self.page.evaluate("() => window.__E2E_MONITOR__")

    def set_fault(self, phase: str | None) -> None:
        self.page.evaluate("phase => { window.__E2E_MONITOR__.faults.phase = phase; }", phase)

    def close(self) -> None:
        invalid_audits: list[dict[str, object]] = []
        if self.java_script_enabled and not self.page.is_closed():
            invalid_audits = self.page.evaluate(
                """() => (window.__E2E_MONITOR__?.eventAudits || []).filter(
                  audit => audit.valid !== true || audit.matchesSnapshot !== true ||
                    !Array.isArray(audit.errors) || audit.errors.length !== 0
                )"""
            )
        self.context.close()
        if invalid_audits:
            raise AssertionError(
                "public deck event detail failed the in-page exact/deep-freeze audit: "
                + json.dumps(invalid_audits, ensure_ascii=False, sort_keys=True)
            )

    def loopback_requests(self) -> list[str]:
        return list(self.server_requests[self.server_request_start:])


class InteractiveDeckBrowserTestCase(unittest.TestCase):
    """Owns two browsers, one temporary fixture and one local server."""

    playwright: Playwright
    browsers: dict[str, Browser]
    temp: tempfile.TemporaryDirectory[str]
    fixture_root: Path
    artifact: Path
    server: LoopbackServer

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.temp = tempfile.TemporaryDirectory(prefix="interactive-deck-e2e-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.fixture_root = Path(cls.temp.name)
        cls.artifact = build_fixture(cls.fixture_root)
        cls.server = LoopbackServer(cls.fixture_root)
        cls.addClassCleanup(cls.server.close)
        cls.server.start()
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browsers = {}
        cls.browsers["chromium"] = cls.playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.browsers["chromium"].close)
        cls.browsers["firefox"] = cls.playwright.firefox.launch(headless=True)
        cls.addClassCleanup(cls.browsers["firefox"].close)

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()

    def iter_matrix(self) -> Iterator[tuple[str, str]]:
        for engine in ("chromium", "firefox"):
            for mode in ("file", "http"):
                yield engine, mode

    def write_variant(self, name: str, html_text: str) -> Path:
        path = self.fixture_root / name
        path.write_text(html_text, encoding="utf-8")
        return path

    def open_deck(
        self,
        engine: str,
        mode: str,
        *,
        artifact: Path | None = None,
        java_script_enabled: bool = True,
        reduced_motion: str = "no-preference",
        viewport: dict[str, int] | None = None,
        device_scale_factor: float | None = None,
        forced_colors: str | None = None,
        init_script: str | None = None,
        initial_fault: str | None = None,
        preoccupied_api: bool = False,
        fragment: str = "",
    ) -> BrowserSession:
        artifact = artifact or self.artifact
        if mode == "file":
            url = artifact.resolve().as_uri()
        elif mode == "http":
            relative = artifact.resolve().relative_to(self.fixture_root.resolve())
            url = self.server.base_url + "/" + "/".join(relative.parts)
        else:
            raise ValueError(f"unknown mode: {mode}")
        document_url = url
        navigation_url = url + fragment

        context_options = {
            "java_script_enabled": java_script_enabled,
            "reduced_motion": reduced_motion,
            "viewport": viewport or {"width": 1280, "height": 900},
            "accept_downloads": False,
        }
        if device_scale_factor is not None:
            context_options["device_scale_factor"] = device_scale_factor
        if forced_colors is not None:
            context_options["forced_colors"] = forced_colors
        context = self.browsers[engine].new_context(
            **context_options,
        )
        if java_script_enabled:
            monitor_script = MONITOR_INIT_SCRIPT
            if initial_fault is not None:
                monitor_script += (
                    "\nwindow.__E2E_MONITOR__.faults.phase = "
                    + json.dumps(initial_fault)
                    + ";"
                )
            if preoccupied_api:
                monitor_script += (
                    "\nObject.defineProperty(window, 'InteractiveDeck', {"
                    "value: 'occupied', writable: false, configurable: false, "
                    "enumerable: true});"
                )
            context.add_init_script(monitor_script)
            if init_script:
                context.add_init_script(init_script)

        observations = Observations()
        server_request_start = len(self.server.requests)

        def route_request(route: Route) -> None:
            request_url = route.request.url
            if request_url == document_url or request_url.startswith(self.server.base_url + "/"):
                route.continue_()
            else:
                observations.blocked_requests.append(request_url)
                route.abort("blockedbyclient")

        context.route("**/*", route_request)
        page = context.new_page()
        page.on("request", lambda request: observations.requests.append(request.url))
        page.on("console", lambda message: observations.consoles.append((message.type, message.text)))
        page.on("pageerror", lambda error: observations.page_errors.append(str(error)))
        page.on("popup", lambda popup: observations.popups.append(popup.url))
        page.on("download", lambda download: observations.downloads.append(download.suggested_filename))
        page.on("framenavigated", lambda frame: observations.navigations.append(frame.url) if frame == page.main_frame else None)
        try:
            page.goto(navigation_url, wait_until="load")
        except BaseException:
            context.close()
            raise
        return BrowserSession(
            engine,
            mode,
            context,
            page,
            document_url,
            observations,
            self.server.requests,
            server_request_start,
            java_script_enabled,
        )

    def without_firefox_favicon_browser_noise(
        self,
        session: BrowserSession,
        console_errors: list[tuple[str, str]],
        csp_events: list[dict[str, str]],
        transports: list[dict[str, str]],
    ) -> tuple[list[tuple[str, str]], list[dict[str, str]]]:
        """Remove Firefox chrome's exact blocked favicon probe, and nothing else.

        Firefox 146 asks its privileged ``FaviconLoader.sys.mjs`` to probe the
        origin even when the artifact has no icon markup.  ``img-src 'none'``
        blocks the probe before the server sees a request.  The exception is
        valid only while every independent no-I/O signal below agrees.
        """
        if session.engine != "firefox" or session.mode != "http":
            return console_errors, csp_events
        parsed = urlsplit(session.url)
        favicon_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
        expected_console = (
            "[JavaScript Error: \"Content-Security-Policy: The page’s settings "
            "blocked the loading of a resource (img-src) at "
            f"{favicon_url} because it violates the following directive: "
            "“img-src 'none'”\" {file: \"resource:///modules/FaviconLoader.sys.mjs\" line: 164}]"
        )
        expected_csp = {"directive": "img-src", "blocked": favicon_url}
        favicon_entry = ("error", expected_console)
        if console_errors.count(favicon_entry) != 1:
            return console_errors, csp_events
        if session.java_script_enabled:
            if csp_events != [expected_csp]:
                return console_errors, csp_events
        elif csp_events:
            return console_errors, csp_events
        if transports:
            return console_errors, csp_events
        if any(request.split("?", 1)[0] == "/favicon.ico" for request in session.loopback_requests()):
            return console_errors, csp_events
        automatic_resource_selector = (
            'head link[href], script[src], img[src], source[src], audio[src], '
            'video[src], iframe[src], object[data], embed[src]'
        )
        if session.page.locator(automatic_resource_selector).count() != 0:
            return console_errors, csp_events
        return [entry for entry in console_errors if entry != favicon_entry], []

    def assert_clean_console_and_csp(self, session: BrowserSession) -> None:
        console_errors = [
            entry for entry in session.observations.consoles if entry[0] == "error"
        ]
        monitor = session.monitor() if session.java_script_enabled else {"transports": [], "csp": []}
        csp_events = monitor["csp"]
        console_errors, csp_events = self.without_firefox_favicon_browser_noise(
            session,
            console_errors,
            csp_events,
            monitor["transports"],
        )
        self.assertEqual(console_errors, [])
        self.assertEqual(csp_events, [])

    def assert_only_document_request(self, session: BrowserSession) -> None:
        requests = [url for url in session.observations.requests if url != session.url]
        self.assertEqual(requests, [], f"unexpected requests in {session.engine}/{session.mode}")
        expected_server_requests = []
        if session.mode == "http":
            parsed = urlsplit(session.url)
            expected_server_requests = [parsed.path + (("?" + parsed.query) if parsed.query else "")]
        self.assertEqual(session.loopback_requests(), expected_server_requests)
        self.assertEqual(session.observations.blocked_requests, [])

    def assert_no_automatic_activity(self, session: BrowserSession) -> None:
        self.assert_only_document_request(session)
        self.assertEqual(session.observations.popups, [])
        self.assertEqual(session.observations.downloads, [])
        self.assertEqual(session.observations.page_errors, [])
        for navigation in session.observations.navigations:
            self.assertEqual(navigation.split("#", 1)[0], session.url)
        monitor = session.monitor()
        self.assertEqual(monitor["transports"], [])
        self.assertEqual(monitor["popups"], [])
        self.assertEqual(monitor["forms"], [])
        self.assertEqual(monitor["scriptedClicks"], [])
        self.assert_clean_console_and_csp(session)
