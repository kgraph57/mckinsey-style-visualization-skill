"""Presenter-demo and browser-audit acceptance for Task 6.

The fixture is deliberately original and synthetic.  Expected values and the
demo order below are hand-derived; no assertion calls the Python planner or
scene evaluator that it is meant to verify.
"""
from __future__ import annotations

import ast
import base64
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

from playwright.sync_api import expect

from base import (
    BUILD_SCRIPT,
    ENVELOPE_RE,
    ROOT,
    InteractiveDeckBrowserTestCase,
)
from test_interactive_components import build_task5_fixture as build_all_scene_fixture


AUDIT_SCRIPT = ROOT / "scripts" / "audit_interactive_deck.py"
SLIDER_ID = "dispatch-gate"
DETAIL_ID = "dispatch-method"
SLIDER_ORDINAL = 2
DETAIL_ORDINAL = 3


def _css_seconds(value: str) -> list[float]:
    seconds: list[float] = []
    for token in value.split(","):
        token = token.strip()
        if token.endswith("ms"):
            seconds.append(float(token[:-2]) / 1_000)
        elif token.endswith("s"):
            seconds.append(float(token[:-1]))
        else:
            raise AssertionError(f"unexpected CSS time: {token!r}")
    return seconds


def _rect_center(rect: dict) -> tuple[float, float]:
    return (
        (float(rect["left"]) + float(rect["right"])) / 2,
        (float(rect["top"]) + float(rect["bottom"])) / 2,
    )


def _distance(first: dict, second: dict) -> float:
    first_x, first_y = _rect_center(first)
    second_x, second_y = _rect_center(second)
    return math.hypot(second_x - first_x, second_y - first_y)


def _rect_inside(inner: dict, outer: dict, *, tolerance: float = 1) -> bool:
    return (
        float(inner["left"]) >= float(outer["left"]) - tolerance
        and float(inner["top"]) >= float(outer["top"]) - tolerance
        and float(inner["right"]) <= float(outer["right"]) + tolerance
        and float(inner["bottom"]) <= float(outer["bottom"]) + tolerance
    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _static_cover() -> dict:
    return {
        "pattern": "bullet_list",
        "headline": "A two-zone dispatch pilot can test the handoff in ten days",
        "source": "Illustrative dispatch exercise",
        "classification": "Illustrative",
        "page_number": 1,
        "bullets": [
            {"text": "Use one morning route and one evening route", "emphasis": True},
            {"text": "Keep the acceptance gate fixed before the trial"},
        ],
    }


def _slider_spec() -> dict:
    return {
        "pattern": "scatter",
        "headline": "The pilot clears the dispatch gate at 60% automated coverage",
        "source": "Illustrative dispatch exercise",
        "footnotes": ["All values are synthetic and are used only for runtime validation."],
        "classification": "Illustrative",
        "page_number": SLIDER_ORDINAL,
        "x_axis": {
            "label": "Automated coverage",
            "quantity": "coverage_rate",
            "unit": "%",
            "domain": [0, 100],
            "tick_labels": ["0%", "100%"],
        },
        "y_axis": {
            "label": "Dispatch throughput",
            "quantity": "dispatch_throughput",
            "unit": "jobs/h",
            "domain": [0, 50],
            "tick_labels": ["0 jobs/h", "50 jobs/h"],
        },
        "points": [
            {
                "item_id": "dispatch-result",
                "label": "Dispatch throughput",
                "x": 30,
                "y": 20,
                "emphasis": True,
            }
        ],
        "interactive_result": {
            "quantity": "dispatch_throughput",
            "value": 20,
            "decision_status": "Hold",
            "recommendation": "Increase automated coverage before the trial",
            "operator": "gte",
            "threshold": 32,
        },
        "annotation": (
            "Dispatch throughput 20 jobs/h; Hold; threshold ≥ 32 jobs/h; "
            "Increase automated coverage before the trial"
        ),
    }


def _slider_scene() -> dict:
    illustrative = {
        "basis": "illustrative",
        "assumptionRefs": ["synthetic-dispatch"],
    }
    return {
        "version": 1,
        "type": "slider_model",
        "purpose": "Find the automated-coverage level that clears the dispatch gate",
        "decisionJob": "decision",
        "interactionRationale": (
            "Decide whether the dispatch pilot clears the fixed throughput gate as coverage changes"
        ),
        "initialState": {"coverage": 30},
        "printState": {"coverage": 30},
        "quantities": {
            "coverage_rate": {
                "dimension": "ratio",
                "unit": "percentage_point",
                "display": "%",
            },
            "dispatch_throughput": {
                "dimension": "count",
                "unit": "jobs_per_hour",
                "display": "jobs/h",
            },
        },
        "sources": [
            {
                "id": "dispatch-note",
                "label": "Synthetic dispatch method",
                "detail": "This safe link is presence-checked and must never be activated by demo or audit.",
                "url": "https://example.com/dispatch-method",
            }
        ],
        "assumptions": [
            {
                "id": "synthetic-dispatch",
                "label": "All dispatch values are synthetic",
                "value": "Task 6 browser fixture only",
            }
        ],
        "controls": [
            {
                "id": "coverage",
                "kind": "range",
                "label": "Automated coverage",
                "min": 0,
                "max": 100,
                "step": 10,
                "quantity": "coverage_rate",
                "provenance": illustrative,
            }
        ],
        "model": {
            "kind": "linear",
            "intercept": {"value": 8, "quantity": "dispatch_throughput"},
            "terms": {
                "coverage": {
                    "coefficient": 0.4,
                    "inputQuantity": "coverage_rate",
                    "outputQuantity": "dispatch_throughput",
                }
            },
            "output": "throughput",
            "outputQuantity": "dispatch_throughput",
            "label": "Dispatch throughput",
            "format": "number",
            "round": 0,
            "modelProvenance": illustrative,
        },
        "reporting": {"primaryOutput": "throughput", "secondaryOutputs": []},
        "decisionContract": {
            "id": "dispatch-gate",
            "metric": {"ref": "output:throughput"},
            "operator": "gte",
            "threshold": {
                "value": 32,
                "quantity": "dispatch_throughput",
                "provenance": illustrative,
            },
            "whenMet": {
                "status": "Proceed",
                "recommendation": "Run the two-zone dispatch trial",
            },
            "whenNotMet": {
                "status": "Hold",
                "recommendation": "Increase automated coverage before the trial",
            },
        },
        "view": {
            "component": "dot_plot",
            "xLabel": "Automated coverage",
            "xQuantity": "coverage_rate",
            "xDomain": [0, 100],
            "yLabel": "Dispatch throughput",
            "yQuantity": "dispatch_throughput",
            "yDomain": [0, 50],
            "points": [
                {
                    "id": "dispatch-result",
                    "label": "Dispatch throughput",
                    "x": {"ref": "control:coverage"},
                    "y": {"ref": "output:throughput"},
                    "highlight": True,
                }
            ],
        },
        "demo": [
            {"stepKey": "baseline-pause", "action": "wait", "ms": 20},
            {
                "stepKey": "reach-dispatch-gate",
                "action": "set",
                "control": "coverage",
                "value": 60,
            },
            {"stepKey": "open-dispatch-proof", "action": "openEvidence"},
            {"stepKey": "close-dispatch-proof", "action": "closeEvidence"},
            {
                "stepKey": "go-to-method",
                "action": "goto",
                "slideId": DETAIL_ID,
            },
        ],
    }


def _detail_spec() -> dict:
    return {
        "pattern": "bullet_list",
        "headline": "One drill-down keeps the dispatch method bounded",
        "source": "Illustrative dispatch exercise",
        "classification": "Illustrative",
        "page_number": DETAIL_ORDINAL,
        "bullets": [
            {"text": "The static conclusion remains complete", "emphasis": True}
        ],
    }


def _detail_scene() -> dict:
    return {
        "version": 1,
        "type": "drilldown",
        "purpose": "Reveal one bounded dispatch-method explanation",
        "decisionJob": "insight",
        "interactionRationale": (
            "Inspect the dispatch sequence and return to the unchanged parent conclusion"
        ),
        "initialState": {"panel": None},
        "printState": {"panel": None},
        "fallbackSummary": {
            "field": "headline",
            "text": "One drill-down keeps the dispatch method bounded",
        },
        "sources": [
            {
                "id": "handoff-note",
                "label": "Synthetic handoff note",
                "detail": "No source link is needed for this original fixture.",
            }
        ],
        "panels": [
            {
                "id": "sequence",
                "label": "Sequence",
                "heading": "How the dispatch sequence works",
                "body": "A route enters one bounded queue, receives one assignment, and exits after confirmation.",
                "sourceRefs": ["handoff-note"],
            },
            {
                "id": "exception",
                "label": "Exception",
                "heading": "How the exception path stays bounded",
                "body": "One failed confirmation returns to the same queue without creating another workflow.",
                "sourceRefs": ["handoff-note"],
            },
        ],
        "parentSummary": "The parent dispatch conclusion remains visible before and after inspection.",
        "returnLabel": "Return to the dispatch conclusion",
        "demo": [
            {
                "stepKey": "open-sequence",
                "action": "openPanel",
                "panel": "sequence",
            },
            {
                "stepKey": "close-sequence",
                "action": "closePanel",
                "panel": "sequence",
            },
        ],
    }


def write_task6_fixture(root: Path) -> Path:
    fixture = root / "task6-fixture"
    _write_json(fixture / "specs/01-summary.json", _static_cover())
    _write_json(fixture / "specs/02-dispatch.json", _slider_spec())
    _write_json(fixture / "scenes/02-dispatch.json", _slider_scene())
    _write_json(fixture / "specs/03-method.json", _detail_spec())
    _write_json(fixture / "scenes/03-method.json", _detail_scene())
    manifest = fixture / "deck.json"
    _write_json(
        manifest,
        {
            "title": "Dispatch pilot <script>must stay text</script>",
            "lang": "en",
            "slides": [
                {"id": "pilot-summary", "spec": "specs/01-summary.json"},
                {
                    "id": SLIDER_ID,
                    "spec": "specs/02-dispatch.json",
                    "scene": "scenes/02-dispatch.json",
                },
                {
                    "id": DETAIL_ID,
                    "spec": "specs/03-method.json",
                    "scene": "scenes/03-method.json",
                },
            ],
        },
    )
    return manifest


def build_task6_fixture(root: Path) -> tuple[Path, Path]:
    manifest = write_task6_fixture(root)
    artifact = manifest.parent / "task6.interactive.html"
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
    if completed.returncode:
        raise AssertionError("Task 6 fixture build failed: " + completed.stderr.strip())
    return manifest, artifact


def _decode_envelope(path: Path) -> dict:
    match = ENVELOPE_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError("interactive envelope not found")
    token = match.group(2)
    token += "=" * ((4 - len(token) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))


def _load_exported_author_probe_script() -> str:
    module = ast.parse(AUDIT_SCRIPT.read_text(encoding="utf-8"))
    matches: list[str] = []
    for node in module.body:
        value = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "AUTHOR_PROBE_SCRIPT"
            for target in node.targets
        ):
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "AUTHOR_PROBE_SCRIPT"
        ):
            value = node.value
        if value is not None:
            literal = ast.literal_eval(value)
            if isinstance(literal, str):
                matches.append(literal)
    if len(matches) != 1:
        raise AssertionError("audit CLI must export exactly one AUTHOR_PROBE_SCRIPT")
    return matches[0]


ZERO_DELAY_SCHEDULER = r"""
(() => {
  let nextId = 1;
  let now = 0;
  const cancelled = new Set();
  const records = {
    delays: [], order: [], steps: [], ends: [], syntheticActions: [],
    placements: [], ready: false, schedulerConsumed: false
  };
  Object.defineProperty(window, "__TASK6_TEST__", {
    value: records, configurable: false, writable: false
  });
  const enqueue = (id, callback, frame) => queueMicrotask(() => {
    if (!cancelled.has(id)) callback(frame ? (now += 16) : undefined);
  });
  Object.defineProperty(window, "__IDRT_TEST_SCHEDULER__", {
    configurable: true,
    value: Object.freeze({
      now() { return now; },
      setTimeout(callback, delay) {
        const id = nextId++;
        records.delays.push(delay);
        enqueue(id, callback, false);
        return id;
      },
      clearTimeout(id) { cancelled.add(id); },
      requestAnimationFrame(callback) {
        const id = nextId++;
        enqueue(id, callback, true);
        return id;
      },
      cancelAnimationFrame(id) { cancelled.add(id); }
    })
  });
  const observedTargetRects = new Map();
  const nativeBoundingRect = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function() {
    const value = nativeBoundingRect.call(this);
    if (this.hasAttribute && this.hasAttribute("data-target-slide") &&
        this.hasAttribute("data-target-key") && value.width > 0 && value.height > 0) {
      const key = `${this.getAttribute("data-target-slide")}\u0000${this.getAttribute("data-target-key")}`;
      observedTargetRects.set(key, {
        left: value.left, top: value.top, right: value.right, bottom: value.bottom,
        width: value.width, height: value.height
      });
    }
    return value;
  };
  const rect = node => {
    if (!node || node.hidden) return null;
    const box = node.getBoundingClientRect();
    return {left: box.left, top: box.top, right: box.right, bottom: box.bottom,
            width: box.width, height: box.height};
  };
  const overlaps = (a, b) => Boolean(a && b &&
    a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top);
  let placementCursor = 0;
  const hiddenDescriptor = Object.getOwnPropertyDescriptor(
    HTMLElement.prototype, "hidden"
  );
  if (hiddenDescriptor && hiddenDescriptor.configurable &&
      hiddenDescriptor.get && hiddenDescriptor.set) {
    Object.defineProperty(HTMLElement.prototype, "hidden", {
      configurable: hiddenDescriptor.configurable,
      enumerable: hiddenDescriptor.enumerable,
      get: hiddenDescriptor.get,
      set(value) {
        hiddenDescriptor.set.call(this, value);
        if (this.id !== "idrt-demo-cue" || value !== false) return;
        const slideId = this.getAttribute("data-slide-id");
        const targetKey = this.getAttribute("data-target-key");
        if (!slideId || !targetKey) return;
        const target = document.querySelector(
          `[data-target-slide="${slideId}"][data-target-key="${targetKey}"]`
        );
        const cueRect = rect(this);
        const targetRect = rect(target);
        const protectedRects = Array.from(document.querySelectorAll(
          `[data-slide-id="${slideId}"] h1, ` +
          `[data-slide-id="${slideId}"] [data-live-value], ` +
          `[data-slide-id="${slideId}"] [role="tooltip"]:not([hidden]), ` +
          `.evidence-dialog:not([hidden]) p`
        )).map(rect).filter(Boolean);
        records.placements.push({
          slideId, targetKey, cueRect, targetRect,
          targetUsable: Boolean(target && targetRect && targetRect.width > 0 &&
            targetRect.height > 0 && !target.closest("[inert]")),
          cueInsideTarget: Boolean(cueRect && targetRect &&
            cueRect.left >= targetRect.left - 1 && cueRect.top >= targetRect.top - 1 &&
            cueRect.right <= targetRect.right + 1 && cueRect.bottom <= targetRect.bottom + 1),
          protectedOverlap: cueRect
            ? protectedRects.some(item => overlaps(cueRect, item)) : false
        });
      }
    });
  }
  document.addEventListener("deck:ready", () => {
    records.ready = true;
    records.order.push("ready");
    records.schedulerConsumed = !("__IDRT_TEST_SCHEDULER__" in window);
  });
  document.addEventListener("deck:demo-step", event => {
    const detail = event.detail;
    const cue = document.getElementById("idrt-demo-cue");
    const ring = cue && cue.querySelector(".demo-cue-ring");
    const cueStyle = cue ? getComputedStyle(cue) : null;
    const ringStyle = ring ? getComputedStyle(ring) : null;
    const pulseStyle = ring ? getComputedStyle(ring, "::after") : null;
    const target = detail.targetKey
      ? document.querySelector(`[data-target-slide="${detail.slideId}"][data-target-key="${detail.targetKey}"]`)
      : null;
    const cueRect = rect(cue);
    const ringRect = rect(ring);
    const currentTargetRect = rect(target);
    const targetLookupKey = detail.targetKey
      ? `${detail.slideId}\u0000${detail.targetKey}` : null;
    const targetRect = currentTargetRect && currentTargetRect.width > 0 &&
      currentTargetRect.height > 0 ? currentTargetRect :
      (targetLookupKey ? observedTargetRects.get(targetLookupKey) || null : null);
    const targetPostActionUsable = Boolean(target && currentTargetRect &&
      currentTargetRect.width > 0 && currentTargetRect.height > 0 &&
      !target.closest("[inert]"));
    const cueEndpointRect = cue && cue.style.left && cue.style.top &&
      cue.style.width && cue.style.height ? (() => {
        const left = Number.parseFloat(cue.style.left);
        const top = Number.parseFloat(cue.style.top);
        const width = Number.parseFloat(cue.style.width);
        const height = Number.parseFloat(cue.style.height);
        return {left, top, right: left + width, bottom: top + height, width, height};
      })() : null;
    const protectedRects = Array.from(document.querySelectorAll(
      `[data-slide-id="${detail.slideId}"] h1, ` +
      `[data-slide-id="${detail.slideId}"] [data-live-value], ` +
      `[data-slide-id="${detail.slideId}"] [role="tooltip"]:not([hidden]), ` +
      `.evidence-dialog:not([hidden]) p`
    )).map(rect).filter(Boolean);
    records.order.push(`step:${detail.stepKey}`);
    const placements = records.placements.slice(placementCursor);
    placementCursor = records.placements.length;
    records.steps.push({
      detail: JSON.parse(JSON.stringify(detail)),
      snapshot: window.InteractiveDeck.snapshot(),
      cueHidden: !cue || cue.hidden,
      cueRect, ringRect, cueEndpointRect, targetRect, targetPostActionUsable,
      placements,
      cueInsideTarget: !detail.targetKey || Boolean(cueRect && targetRect &&
        cueRect.left >= targetRect.left - 1 && cueRect.top >= targetRect.top - 1 &&
        cueRect.right <= targetRect.right + 1 && cueRect.bottom <= targetRect.bottom + 1),
      protectedOverlap: cueRect ? protectedRects.some(item => overlaps(cueRect, item)) : false,
      ariaHidden: cue && cue.getAttribute("aria-hidden"),
      inert: Boolean(cue && cue.inert),
      pointerEvents: cueStyle ? cueStyle.pointerEvents : null,
      animationName: cueStyle ? cueStyle.animationName : null,
      transitionProperty: cueStyle ? cueStyle.transitionProperty : null,
      transitionDuration: cueStyle ? cueStyle.transitionDuration : null,
      ringAnimationName: ringStyle ? ringStyle.animationName : null,
      ringAnimationDuration: ringStyle ? ringStyle.animationDuration : null,
      ringTransitionProperty: ringStyle ? ringStyle.transitionProperty : null,
      ringTransitionDuration: ringStyle ? ringStyle.transitionDuration : null,
      pulseAnimationName: pulseStyle ? pulseStyle.animationName : null,
      pulseAnimationDuration: pulseStyle ? pulseStyle.animationDuration : null
    });
  });
  document.addEventListener("deck:demo-end", event => {
    records.order.push(`end:${event.detail.reason}`);
    records.ends.push(JSON.parse(JSON.stringify(event.detail)));
  });
  const nativeClick = HTMLElement.prototype.click;
  HTMLElement.prototype.click = function() {
    if (this.hasAttribute && this.hasAttribute("data-target-key")) {
      records.syntheticActions.push({kind: "click", key: this.getAttribute("data-target-key")});
    }
    return nativeClick.apply(this, arguments);
  };
  const nativeDispatch = EventTarget.prototype.dispatchEvent;
  EventTarget.prototype.dispatchEvent = function(event) {
    if (event instanceof MouseEvent && event.isTrusted === false &&
        this instanceof Element && this.hasAttribute("data-target-key")) {
      records.syntheticActions.push({kind: event.type, key: this.getAttribute("data-target-key")});
    }
    return nativeDispatch.apply(this, arguments);
  };
})();
"""


HOLDING_SCHEDULER = r"""
(() => {
  let nextId = 1;
  let now = 0;
  const pending = new Map();
  const records = {steps: [], ends: [], delays: [], cancelled: [], order: []};
  const scheduler = Object.freeze({
    now() { return now; },
    setTimeout(callback, delay) {
      const id = nextId++;
      records.delays.push(delay);
      pending.set(id, {kind: "timeout", callback: () => callback()});
      return id;
    },
    clearTimeout(id) {
      records.cancelled.push({kind: "timeout", id});
      pending.delete(id);
    },
    requestAnimationFrame(callback) {
      const id = nextId++;
      pending.set(id, {kind: "raf", callback: () => callback(now += 16)});
      return id;
    },
    cancelAnimationFrame(id) {
      records.cancelled.push({kind: "raf", id});
      pending.delete(id);
    }
  });
  Object.defineProperty(window, "__IDRT_TEST_SCHEDULER__", {
    configurable: true, value: scheduler
  });
  Object.defineProperty(window, "__TASK6_TEST__", {
    configurable: false,
    value: Object.assign(records, {
      flushAll() {
        let guard = 0;
        while (pending.size && guard < 500) {
          const batch = Array.from(pending.values());
          pending.clear();
          batch.forEach(entry => entry.callback());
          guard += 1;
        }
        return {guard, pending: pending.size};
      },
      advanceUntilSteps(count) {
        let guard = 0;
        while (records.steps.length < count && pending.size && guard < 500) {
          const [id, entry] = pending.entries().next().value;
          pending.delete(id);
          entry.callback();
          guard += 1;
        }
        return {guard, steps: records.steps.length};
      },
      pendingCount() { return pending.size; },
      pendingRafs() {
        return Array.from(pending).filter(([, entry]) => entry.kind === "raf")
          .map(([id]) => id);
      },
      pendingTimers() {
        return Array.from(pending).filter(([, entry]) => entry.kind === "timeout")
          .map(([id]) => id);
      },
      flushRafs() {
        let guard = 0;
        while (guard < 500) {
          const next = Array.from(pending).find(([, entry]) => entry.kind === "raf");
          if (!next) break;
          const [id, entry] = next;
          pending.delete(id);
          entry.callback();
          guard += 1;
        }
        return {guard, pendingRafs: this.pendingRafs()};
      },
      releaseOneAsync() {
        if (!pending.size) return null;
        const [id, entry] = pending.entries().next().value;
        pending.delete(id);
        window.setTimeout(() => entry.callback(), 0);
        return {id, kind: entry.kind};
      }
    })
  });
  document.addEventListener("deck:demo-step", event => {
    records.order.push(`step:${event.detail.stepKey}`);
    records.steps.push(JSON.parse(JSON.stringify(event.detail)));
  });
  document.addEventListener("deck:demo-end", event => {
    records.order.push(`end:${event.detail.reason}`);
    records.ends.push(JSON.parse(JSON.stringify(event.detail)));
  });
})();
"""


DOM_SINK_MONITOR = r"""
(() => {
  const calls = [];
  Object.defineProperty(window, "__TASK6_DOM_SINKS__", {value: calls});
  const createElement = Document.prototype.createElement;
  Document.prototype.createElement = function(...args) {
    calls.push({kind: "createElement", tag: String(args[0] || "")});
    return createElement.apply(this, args);
  };
  const createElementNS = Document.prototype.createElementNS;
  Document.prototype.createElementNS = function(...args) {
    calls.push({kind: "createElementNS", tag: String(args[1] || "")});
    return createElementNS.apply(this, args);
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


class InteractivePresenterDemoAuditE2ETests(InteractiveDeckBrowserTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.manifest, cls.artifact = build_task6_fixture(cls.fixture_root)
        cls.envelope = _decode_envelope(cls.artifact)
        audit_root = cls.fixture_root / "task6-audit-matrix"
        completed, cls.audit_artifact = build_all_scene_fixture(audit_root)
        if completed.returncode:
            raise AssertionError(
                "Task 6 all-scene audit fixture build failed: "
                + completed.stderr.strip()
            )
        cls.audit_manifest = audit_root / "deck.json"
        cls.audit_envelope = _decode_envelope(cls.audit_artifact)
        audit_manifest = json.loads(cls.audit_manifest.read_text(encoding="utf-8"))
        audit_manifest["title"] = "Task 6 matrix <script>must stay text</script>"
        _write_json(cls.audit_manifest, audit_manifest)

    def _wait_ready(self, page) -> None:
        page.wait_for_function(
            """() => document.documentElement.dataset.interactiveRuntime === 'ready' &&
              window.InteractiveDeck && typeof window.InteractiveDeck.snapshot === 'function'""",
            timeout=8_000,
        )

    def _activate(self, page, ordinal: int) -> None:
        page.locator(
            f'#idrt-presenter-chrome [data-page-index="{ordinal}"]'
        ).click()
        page.wait_for_function(
            """ordinal => {
              const slide = document.getElementById(`idrt-page-${ordinal}`);
              return slide && !slide.hidden && slide.dataset.runtime === "ready";
            }""",
            arg=ordinal,
            timeout=8_000,
        )

    def _set_coverage_index(self, page, native_index: str) -> None:
        page.locator(
            f'[data-slide-id="{SLIDER_ID}"] input[data-control-id="coverage"]'
        ).evaluate(
            """(input, value) => {
              input.value = value;
              input.dispatchEvent(new Event("input", {bubbles: true}));
            }""",
            native_index,
        )

    def _press_presenter_shortcut(self, page, key: str) -> None:
        page.locator(
            f'[data-slide-id="{SLIDER_ID}"] h1'
        ).focus()
        page.keyboard.press(key)

    def _api_contract(self, page) -> dict:
        return page.evaluate(
            """() => {
              const api = window.InteractiveDeck;
              const descriptor = Object.getOwnPropertyDescriptor(window, "InteractiveDeck");
              return {
                keys: Reflect.ownKeys(api),
                frozen: Object.isFrozen(api),
                descriptor: {
                  writable: descriptor.writable,
                  configurable: descriptor.configurable,
                  enumerable: descriptor.enumerable
                },
                hasSchedulerLeak: "__IDRT_TEST_SCHEDULER__" in window
              };
            }"""
        )

    def _apply_closed_audit_setup(self, page, state: dict) -> None:
        slide_id = state["slideId"]

        def target(target_key: str):
            locator = page.locator(
                f'[data-target-slide="{slide_id}"][data-target-key="{target_key}"]'
            )
            self.assertEqual(locator.count(), 1, (slide_id, target_key))
            return locator

        for setup in state["setup"]:
            action = setup["action"]
            if action == "emulateReducedMotion":
                continue
            if action == "openOverview":
                page.locator("html").dispatch_event(
                    "keydown",
                    {"key": "o", "code": "KeyO", "altKey": True},
                )
            elif action == "openEvidence":
                target("evidence:open").dispatch_event("click")
            elif action == "closeEvidence":
                target("evidence:close").dispatch_event("click")
            elif action == "selectEvidenceTab":
                ordinal = state["ordinal"]
                tab = page.locator(
                    f'#idrt-evidence-dialog-{ordinal}:not([hidden]) '
                    f'[data-evidence-tab="{setup["tab"]}"]'
                )
                self.assertEqual(tab.count(), 1)
                tab.dispatch_event("click")
            elif action == "openPanel":
                target("panel:" + setup["panel"]).dispatch_event("click")
            elif action == "closePanel":
                target("panel:" + setup["panel"] + ":close").dispatch_event(
                    "click"
                )
            elif action == "assertTarget":
                box = target(setup["targetKey"]).bounding_box()
                self.assertIsNotNone(box)
                self.assertGreater(box["width"], 0)
                self.assertGreater(box["height"], 0)
            else:
                self.fail(f"unclosed audit setup action: {action}")

    def _assert_author_probe_replay(self, ledger: dict) -> None:
        probe_script = _load_exported_author_probe_script()
        relative = self.audit_artifact.resolve().relative_to(
            self.fixture_root.resolve()
        )
        base_url = self.server.base_url + "/" + "/".join(relative.parts)
        context = self.browsers["chromium"].new_context(
            viewport={"width": 1280, "height": 720}
        )
        unexpected_requests: list[str] = []
        page_errors: list[str] = []
        console_errors: list[str] = []

        def route_request(route) -> None:
            if route.request.url.split("#", 1)[0] == base_url:
                route.continue_()
            else:
                unexpected_requests.append(route.request.url)
                route.abort("blockedbyclient")

        context.route("**/*", route_request)
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        try:
            for state in ledger["states"]:
                reduced = any(
                    setup["action"] == "emulateReducedMotion"
                    for setup in state["setup"]
                )
                page.emulate_media(
                    reduced_motion="reduce" if reduced else "no-preference"
                )
                page.goto("about:blank", wait_until="load")
                page.goto(base_url + state["fragment"], wait_until="load")
                page.wait_for_function(
                    """ordinal => {
                      if (!window.InteractiveDeck) return false;
                      const snapshot = window.InteractiveDeck.snapshot();
                      const section = document.getElementById(`idrt-page-${ordinal}`);
                      return snapshot.currentSlide === ordinal && section && !section.hidden &&
                        (!section.dataset.runtime || section.dataset.runtime === "ready");
                    }""",
                    arg=state["ordinal"],
                    timeout=8_000,
                )
                self._apply_closed_audit_setup(page, state)
                observed = page.evaluate(probe_script, state["ordinal"])
                self.assertEqual(observed, state["expected"]["authorProbe"])
                self.assertEqual(observed, state["reconstruction"]["authorProbe"])
        finally:
            context.close()
        self.assertEqual(unexpected_requests, [])
        self.assertEqual(page_errors, [])
        self.assertEqual(console_errors, [])

    def test_presenter_shortcuts_overlay_stack_focus_guards_and_hash_clear(self) -> None:
        """Catches shortcuts bypassing focus guards or a one-record overlay model."""
        expected_labels = {
            "overview": "Overview",
            "replay": "Replay",
            "demo": "Demo",
            "fullscreen": "Full screen",
            "help": "Help",
        }
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(engine, "http", artifact=self.artifact)
                page = session.page
                try:
                    self._wait_ready(page)
                    self._activate(page, SLIDER_ORDINAL)
                    for action, label in expected_labels.items():
                        button = page.locator(
                            f'[data-presenter-action="{action}"]'
                        )
                        self.assertEqual(button.count(), 1)
                        self.assertEqual(button.inner_text().strip(), label)

                    # A focused control suppresses presenter shortcuts.
                    self._set_coverage_index(page, "9")
                    range_control = page.locator(
                        f'[data-slide-id="{SLIDER_ID}"] input[data-control-id="coverage"]'
                    )
                    range_control.focus()
                    page.keyboard.press("Alt+O")
                    self.assertTrue(page.locator("#idrt-presenter-overview").is_hidden())
                    page.keyboard.press("Alt+R")
                    self.assertEqual(range_control.get_attribute("aria-valuetext"), "90")

                    # Background Alt+R replays only the current page.
                    page.locator(f'[data-slide-id="{SLIDER_ID}"] h1').focus()
                    page.keyboard.press("Alt+R")
                    expect(range_control).to_have_attribute("aria-valuetext", "30")

                    # Evidence can sit below Help; Escape closes only the top layer.
                    evidence = page.locator(f"#idrt-evidence-open-{SLIDER_ORDINAL}")
                    evidence.focus()
                    evidence.click()
                    evidence_dialog = page.locator(
                        f"#idrt-evidence-dialog-{SLIDER_ORDINAL}"
                    )
                    self.assertTrue(evidence_dialog.is_visible())
                    page.evaluate("() => document.activeElement && document.activeElement.blur()")
                    page.keyboard.press("Alt+H")
                    help_dialog = page.locator("#idrt-presenter-help")
                    self.assertTrue(help_dialog.is_visible())
                    self.assertTrue(evidence_dialog.is_visible())
                    self.assertEqual(
                        page.evaluate("() => window.InteractiveDeck.snapshot().overlay"),
                        {"kind": "evidence", "ordinal": 2, "tab": "sources"},
                    )
                    help_text = help_dialog.inner_text()
                    for shortcut in ("Alt+O", "Alt+R", "Alt+D", "Alt+F", "Alt+H", "Escape"):
                        self.assertIn(shortcut, help_text)
                    self.assertEqual(
                        help_dialog.locator('[data-presenter-close="help"]').inner_text().strip(),
                        "Close",
                    )
                    page.keyboard.press("Escape")
                    self.assertTrue(help_dialog.is_hidden())
                    self.assertTrue(evidence_dialog.is_visible())
                    page.keyboard.press("Escape")
                    self.assertTrue(evidence_dialog.is_hidden())
                    self.assertTrue(
                        evidence.evaluate("node => node === document.activeElement")
                    )

                    # Help opened by its visible control returns focus to that control.
                    help_button = page.locator('[data-presenter-action="help"]')
                    help_button.focus()
                    help_button.click()
                    self.assertTrue(help_dialog.is_visible())
                    page.keyboard.press("Escape")
                    self.assertTrue(
                        help_button.evaluate("node => node === document.activeElement")
                    )

                    # Page/hash restoration closes the entire stack, not one record.
                    evidence.click()
                    page.evaluate("() => document.activeElement && document.activeElement.blur()")
                    page.keyboard.press("Alt+H")
                    self.assertTrue(help_dialog.is_visible())
                    page.evaluate("() => { location.hash = '#slide=1'; }")
                    page.wait_for_function(
                        "() => !document.getElementById('idrt-page-1').hidden",
                        timeout=8_000,
                    )
                    self.assertTrue(help_dialog.is_hidden())
                    self.assertTrue(evidence_dialog.is_hidden())
                    self.assertIsNone(
                        page.evaluate("() => window.InteractiveDeck.snapshot().overlay")
                    )
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_prebuilt_targets_static_overview_public_api_and_dom_sinks(self) -> None:
        """Catches unresolved target keys, live thumbnails, duplicate IDs, or DOM injection."""
        session = self.open_deck(
            "chromium",
            "http",
            artifact=self.artifact,
            init_script=DOM_SINK_MONITOR,
        )
        page = session.page
        try:
            self._wait_ready(page)
            for selector in (
                "#idrt-presenter-overview",
                "#idrt-presenter-help",
                "#idrt-demo-cue",
                "#idrt-presenter-status[aria-live=\"polite\"]",
            ):
                self.assertEqual(page.locator(selector).count(), 1, selector)
            self.assertEqual(
                page.locator("#idrt-demo-cue").get_attribute("aria-hidden"),
                "true",
            )
            self.assertTrue(page.locator("#idrt-demo-cue").evaluate("node => node.inert"))

            expected_pairs: list[tuple[str, str]] = []
            for slide in self.envelope["slides"]:
                scene = slide["scene"]
                if scene is None:
                    continue
                expected_pairs.extend(
                    (slide["slideId"], target_key)
                    for target_key in scene["targets"]
                )
            for slide_id, target_key in expected_pairs:
                locator = page.locator(
                    f'[data-target-slide="{slide_id}"][data-target-key="{target_key}"]'
                )
                self.assertEqual(
                    locator.count(),
                    1,
                    f"{slide_id}/{target_key} must resolve to one prebuilt node",
                )

            self._activate(page, SLIDER_ORDINAL)
            self._set_coverage_index(page, "9")
            self._press_presenter_shortcut(page, "Alt+O")
            overview = page.locator("#idrt-presenter-overview")
            self.assertTrue(overview.is_visible())
            thumbnails = overview.locator("button[data-overview-slide]")
            self.assertEqual(thumbnails.count(), 3)
            for ordinal in range(1, 4):
                thumbnail = overview.locator(
                    f'button[data-overview-slide="{ordinal}"]'
                )
                fallback = thumbnail.locator(".overview-fallback")
                self.assertTrue(fallback.is_visible())
                self.assertEqual(thumbnail.locator(".live-layer").count(), 0)
                self.assertEqual(
                    fallback.locator(
                        "input, select, button, [data-runtime], [data-target-key]"
                    ).count(),
                    0,
                )
                overview_svg = fallback.locator("svg")
                page_svg = page.locator(
                    f"#idrt-page-{ordinal} .fallback-layer svg"
                )
                self.assertEqual(overview_svg.count(), 1)
                self.assertEqual(page_svg.count(), 1)
                self.assertEqual(
                    " ".join((overview_svg.text_content() or "").split()),
                    " ".join((page_svg.text_content() or "").split()),
                )

            duplicate_ids = page.evaluate(
                """() => {
                  const counts = new Map();
                  document.querySelectorAll("[id]").forEach(node => {
                    counts.set(node.id, (counts.get(node.id) || 0) + 1);
                  });
                  return Array.from(counts).filter(([, count]) => count !== 1);
                }"""
            )
            self.assertEqual(duplicate_ids, [])
            overview_opener = page.locator('[data-presenter-action="overview"]')
            page.keyboard.press("Escape")
            self.assertTrue(overview.is_hidden())
            self.assertTrue(
                overview_opener.evaluate("node => node === document.activeElement")
            )
            overview_opener.click()
            self.assertTrue(overview.is_visible())
            overview.locator('button[data-overview-slide="3"]').click()
            page.wait_for_function(
                "() => !document.getElementById('idrt-page-3').hidden",
                timeout=8_000,
            )
            self.assertTrue(overview.is_hidden())

            api = self._api_contract(page)
            self.assertEqual(api, {
                "keys": ["snapshot"],
                "frozen": True,
                "descriptor": {
                    "writable": False,
                    "configurable": False,
                    "enumerable": True,
                },
                "hasSchedulerLeak": False,
            })
            self.assertEqual(page.evaluate("() => window.__TASK6_DOM_SINKS__"), [])
            self.assert_no_automatic_activity(session)
        finally:
            session.close()

    def test_fullscreen_denial_and_unavailability_use_local_fallback(self) -> None:
        """Catches fullscreen rejection escaping into scene failure or a dead control."""
        variants = {
            "denied": r"""
              Object.defineProperty(document, "fullscreenEnabled", {value: true, configurable: true});
              Object.defineProperty(Element.prototype, "requestFullscreen", {
                configurable: true,
                value() { return Promise.reject(new DOMException("denied", "NotAllowedError")); }
              });
            """,
            "unavailable": r"""
              Object.defineProperty(document, "fullscreenEnabled", {value: false, configurable: true});
              Object.defineProperty(Element.prototype, "requestFullscreen", {
                configurable: true, value: undefined
              });
            """,
        }
        for engine in ("chromium", "firefox"):
            for name, init_script in variants.items():
                with self.subTest(engine=engine, variant=name):
                    session = self.open_deck(
                        engine,
                        "http",
                        artifact=self.artifact,
                        init_script=init_script,
                    )
                    page = session.page
                    try:
                        self._wait_ready(page)
                        self._activate(page, SLIDER_ORDINAL)
                        self._press_presenter_shortcut(page, "Alt+F")
                        page.wait_for_function(
                            """() => document.documentElement.classList.contains('idrt-local-fullscreen') &&
                              document.documentElement.dataset.fullscreenMode === 'local'""",
                            timeout=8_000,
                        )
                        self.assertEqual(
                            page.locator(
                                f'[data-slide-id="{SLIDER_ID}"]'
                            ).get_attribute("data-runtime"),
                            "ready",
                        )
                        self.assertIsNone(
                            page.evaluate(
                                """() => window.InteractiveDeck.snapshot().pages
                                  .find(page => page.ordinal === 2).failed"""
                            )
                        )
                        self._press_presenter_shortcut(page, "Alt+F")
                        page.wait_for_function(
                            """() => !document.documentElement.classList.contains("idrt-local-fullscreen") &&
                              !document.documentElement.hasAttribute("data-fullscreen-mode")""",
                            timeout=8_000,
                        )
                        self.assert_no_automatic_activity(session)
                    finally:
                        session.close()

    def _assert_completed_demo(self, page, *, reduced_motion: bool) -> None:
        page.wait_for_function(
            """() => window.__TASK6_TEST__.ends.some(item => item.reason === 'complete')""",
            timeout=8_000,
        )
        records = page.evaluate("() => window.__TASK6_TEST__")
        expected_steps = [
            (SLIDER_ID, "baseline-pause", None),
            (SLIDER_ID, "reach-dispatch-gate", "control:coverage"),
            (SLIDER_ID, "open-dispatch-proof", "evidence:open"),
            (SLIDER_ID, "close-dispatch-proof", "evidence:close"),
            (SLIDER_ID, "go-to-method", None),
            (DETAIL_ID, "open-sequence", "panel:sequence"),
            (DETAIL_ID, "close-sequence", "panel:sequence:close"),
        ]
        actual_steps = [
            (
                item["detail"]["slideId"],
                item["detail"]["stepKey"],
                item["detail"].get("targetKey"),
            )
            for item in records["steps"]
        ]
        self.assertEqual(actual_steps, expected_steps)
        for item in records["steps"]:
            detail = item["detail"]
            expected_keys = {"slideId", "stepKey", "ordinal", "reason"}
            if detail.get("targetKey") is not None:
                expected_keys.add("targetKey")
            self.assertEqual(set(detail), expected_keys)
            self.assertEqual(detail["reason"], "step")
            self.assertIs(type(detail["ordinal"]), int)
            for key in ("slideId", "stepKey"):
                self.assertRegex(detail[key], r"^[a-z][a-z0-9_-]{0,63}$")
        self.assertEqual(len(records["ends"]), 1)
        demo_end = records["ends"][0]
        self.assertEqual(set(demo_end), {"reason", "slideId", "ordinal"})
        self.assertEqual(
            demo_end,
            {"reason": "complete", "slideId": DETAIL_ID, "ordinal": DETAIL_ORDINAL},
        )
        self.assertRegex(demo_end["slideId"], r"^[a-z][a-z0-9_-]{0,63}$")
        self.assertIs(type(demo_end["ordinal"]), int)
        self.assertEqual(records["syntheticActions"], [])
        self.assertTrue(records["schedulerConsumed"])
        if reduced_motion:
            self.assertNotIn(800, records["delays"])
            self.assertTrue(any(0 < delay < 800 for delay in records["delays"]))
        else:
            self.assertGreaterEqual(records["delays"].count(800), 3)

        wait_step = records["steps"][0]
        self.assertTrue(wait_step["cueHidden"])
        self.assertEqual(wait_step["snapshot"]["pages"][1]["inputs"]["coverage"], "30")
        goto_step = next(
            item for item in records["steps"]
            if item["detail"]["stepKey"] == "go-to-method"
        )
        self.assertTrue(goto_step["cueHidden"])
        for item in records["steps"]:
            if item["detail"].get("targetKey") is None:
                self.assertIsNone(item["cueRect"])
                self.assertEqual(item["placements"], [])
                continue
            self.assertGreaterEqual(len(item["placements"]), 1, item["detail"])
            pre_action = item["placements"][0]
            self.assertEqual(pre_action["slideId"], item["detail"]["slideId"])
            self.assertEqual(
                pre_action["targetKey"], item["detail"]["targetKey"]
            )
            self.assertTrue(pre_action["targetUsable"], pre_action)
            self.assertTrue(pre_action["cueInsideTarget"], pre_action)
            self.assertFalse(pre_action["protectedOverlap"], pre_action)
            if item["cueHidden"]:
                self.assertFalse(item["targetPostActionUsable"], item)
                self.assertIsNone(item["cueRect"])
                self.assertFalse(item["protectedOverlap"], item)
                continue
            self.assertTrue(item["targetPostActionUsable"], item)
            self.assertFalse(item["cueHidden"], item["detail"])
            self.assertTrue(item["cueInsideTarget"], item)
            self.assertFalse(item["protectedOverlap"], item)
            self.assertEqual(item["ariaHidden"], "true")
            self.assertTrue(item["inert"])
            self.assertEqual(item["pointerEvents"], "none")
            if reduced_motion:
                self.assertEqual(item["transitionProperty"], "none")
                self.assertTrue(
                    all(
                        duration == 0
                        for duration in _css_seconds(item["transitionDuration"])
                    )
                )
                self.assertEqual(item["ringAnimationName"], "none")
                self.assertTrue(
                    all(
                        duration == 0
                        for duration in _css_seconds(
                            item["ringAnimationDuration"]
                        )
                    )
                )
                self.assertLessEqual(
                    _distance(item["cueRect"], item["cueEndpointRect"]),
                    1,
                )
            else:
                self.assertEqual(
                    item["ringAnimationName"], "idrt-cue-pulse"
                )

        overview = page.locator("#idrt-presenter-overview")
        self.assertTrue(overview.is_visible())
        self.assertEqual(
            page.locator('[data-presenter-action="demo"]').get_attribute(
                "aria-pressed"
            ),
            "false",
        )
        self.assertTrue(page.locator("#idrt-demo-cue").is_hidden())
        self.assertEqual(
            overview.locator("button[data-overview-slide] .overview-fallback").count(),
            3,
        )
        self.assertEqual(
            page.evaluate("() => window.InteractiveDeck.snapshot().pages[1].inputs.coverage"),
            "60",
        )
        self.assertEqual(self._api_contract(page)["keys"], ["snapshot"])

    def _assert_normal_cue_travels_between_separated_targets(self) -> None:
        session = self.open_deck(
            "chromium",
            "http",
            artifact=self.artifact,
            init_script=HOLDING_SCHEDULER,
        )
        page = session.page

        def cue_sample() -> dict:
            return page.evaluate(
                """() => {
                  const cue = document.getElementById("idrt-demo-cue");
                  const ring = cue.querySelector(".demo-cue-ring");
                  const box = node => {
                    const value = node.getBoundingClientRect();
                    return {left: value.left, top: value.top, right: value.right,
                            bottom: value.bottom, width: value.width, height: value.height};
                  };
                  const number = value => Number.parseFloat(value);
                  const endpoint = {
                    left: number(cue.style.left), top: number(cue.style.top),
                    width: number(cue.style.width), height: number(cue.style.height)
                  };
                  endpoint.right = endpoint.left + endpoint.width;
                  endpoint.bottom = endpoint.top + endpoint.height;
                  const cueStyle = getComputedStyle(cue);
                  const ringStyle = getComputedStyle(ring);
                  const slideId = cue.getAttribute("data-slide-id");
                  const targetKey = cue.getAttribute("data-target-key");
                  const target = document.querySelector(
                    `[data-target-slide="${slideId}"][data-target-key="${targetKey}"]`
                  );
                  const cueRect = box(cue);
                  const overlaps = (first, second) => first.left < second.right &&
                    first.right > second.left && first.top < second.bottom &&
                    first.bottom > second.top;
                  const protectedRects = Array.from(document.querySelectorAll(
                    `[data-slide-id="${slideId}"] h1, ` +
                    `[data-slide-id="${slideId}"] [data-live-value], ` +
                    `[data-slide-id="${slideId}"] [role="tooltip"]:not([hidden]), ` +
                    `.evidence-dialog:not([hidden]) p`
                  )).filter(node => !node.hidden && !node.closest("[hidden]"))
                    .map(box);
                  return {
                    hidden: cue.hidden,
                    slideId, targetKey,
                    rect: cueRect, endpoint, targetRect: box(target),
                    protectedOverlap: protectedRects.some(
                      protectedRect => overlaps(cueRect, protectedRect)
                    ),
                    transitionProperty: cueStyle.transitionProperty,
                    transitionDuration: cueStyle.transitionDuration,
                    transitionTimingFunction: cueStyle.transitionTimingFunction,
                    ringAnimationName: ringStyle.animationName,
                    ringAnimationDuration: ringStyle.animationDuration
                  };
                }"""
            )

        try:
            self._wait_ready(page)
            self._activate(page, SLIDER_ORDINAL)
            self._press_presenter_shortcut(page, "Alt+D")
            first_advance = page.evaluate(
                "() => window.__TASK6_TEST__.advanceUntilSteps(2)"
            )
            self.assertEqual(first_advance["steps"], 2)
            page.evaluate("() => window.__TASK6_TEST__.flushRafs()")
            first_initial = cue_sample()
            self.assertFalse(first_initial["hidden"])
            self.assertEqual(first_initial["slideId"], SLIDER_ID)
            self.assertEqual(first_initial["targetKey"], "control:coverage")
            transition_properties = {
                item.strip() for item in first_initial["transitionProperty"].split(",")
            }
            self.assertTrue(
                {"left", "top", "width", "height"} <= transition_properties
            )
            transition_seconds = _css_seconds(first_initial["transitionDuration"])
            self.assertTrue(
                all(abs(value - 0.18) <= 0.001 for value in transition_seconds)
            )
            travel_seconds = max(transition_seconds)
            timing_functions = re.findall(
                r"cubic-bezier\([^)]*\)",
                first_initial["transitionTimingFunction"],
            )
            self.assertEqual(len(timing_functions), 4)
            self.assertEqual(
                set(timing_functions), {"cubic-bezier(0.22, 1, 0.36, 1)"}
            )
            self.assertEqual(
                first_initial["ringAnimationName"], "idrt-cue-pulse"
            )
            pulse_seconds = max(
                _css_seconds(first_initial["ringAnimationDuration"])
            )
            self.assertAlmostEqual(pulse_seconds, 0.9, places=3)

            page.wait_for_timeout(round(travel_seconds * 1_000) + 80)
            first_settled = cue_sample()
            self.assertLessEqual(
                _distance(first_settled["rect"], first_settled["endpoint"]),
                2,
            )
            self.assertTrue(
                _rect_inside(first_settled["rect"], first_settled["targetRect"])
            )
            self.assertFalse(first_settled["protectedOverlap"])
            second_advance = page.evaluate(
                "() => window.__TASK6_TEST__.advanceUntilSteps(6)"
            )
            self.assertEqual(second_advance["steps"], 6)
            second_start = cue_sample()
            self.assertEqual(second_start["slideId"], DETAIL_ID)
            self.assertEqual(second_start["targetKey"], "panel:sequence")
            endpoint_travel = _distance(
                first_settled["endpoint"], second_start["endpoint"]
            )
            self.assertGreater(endpoint_travel, math.hypot(12, 12) * 4)
            self.assertLess(endpoint_travel, 1_280)
            self.assertTrue(
                _rect_inside(second_start["rect"], second_start["targetRect"])
            )
            self.assertFalse(second_start["protectedOverlap"])
            bounded_start = _distance(
                second_start["rect"], second_start["endpoint"]
            )
            self.assertGreater(bounded_start, 0.5)
            self.assertLessEqual(bounded_start, math.hypot(12, 12) + 1)
            size_delta = abs(
                float(second_start["rect"]["width"])
                - float(second_start["endpoint"]["width"])
            )
            self.assertGreater(size_delta, 0.2)
            self.assertLessEqual(size_delta, 2.1)

            page.wait_for_timeout(max(20, round(travel_seconds * 500)))
            second_midpoint = cue_sample()
            page.wait_for_timeout(round(travel_seconds * 500) + 100)
            second_settled = cue_sample()
            start_remaining = _distance(
                second_start["rect"], second_start["endpoint"]
            )
            midpoint_remaining = _distance(
                second_midpoint["rect"], second_start["endpoint"]
            )
            end_remaining = _distance(
                second_settled["rect"], second_start["endpoint"]
            )
            self.assertGreater(start_remaining, midpoint_remaining)
            self.assertGreater(midpoint_remaining, end_remaining)
            self.assertLessEqual(end_remaining, 2)
            self.assertTrue(
                _rect_inside(
                    second_midpoint["rect"], second_midpoint["targetRect"]
                )
            )
            self.assertFalse(second_midpoint["protectedOverlap"])
            self.assertTrue(
                _rect_inside(
                    second_settled["rect"], second_settled["targetRect"]
                )
            )
            self.assertFalse(second_settled["protectedOverlap"])
            self.assertGreater(
                _distance(second_start["rect"], second_midpoint["rect"]),
                5,
            )

            page.mouse.wheel(0, 100)
            page.wait_for_function(
                """() => window.__TASK6_TEST__.ends.some(
                  item => item.reason === "cancelled"
                )""",
                timeout=8_000,
            )
            step_count = page.evaluate(
                "() => window.__TASK6_TEST__.steps.length"
            )
            flushed = page.evaluate("() => window.__TASK6_TEST__.flushAll()")
            self.assertEqual(flushed["pending"], 0)
            self.assertEqual(
                page.evaluate("() => window.__TASK6_TEST__.steps.length"),
                step_count,
            )
            self.assert_no_automatic_activity(session)
        finally:
            session.close()

    def _assert_demo_fails_closed_when_required_mark_disappears(self) -> None:
        session = self.open_deck(
            "chromium",
            "http",
            artifact=self.artifact,
            init_script=HOLDING_SCHEDULER,
        )
        page = session.page
        try:
            self._wait_ready(page)
            self._activate(page, SLIDER_ORDINAL)
            self._press_presenter_shortcut(page, "Alt+D")
            advanced = page.evaluate(
                "() => window.__TASK6_TEST__.advanceUntilSteps(1)"
            )
            self.assertEqual(advanced["steps"], 1)
            self.assertEqual(
                page.evaluate(
                    "() => window.__TASK6_TEST__.steps.map(step => step.stepKey)"
                ),
                ["baseline-pause"],
            )
            settled = page.evaluate("() => window.__TASK6_TEST__.flushRafs()")
            self.assertEqual(settled["pendingRafs"], [])
            self.assertTrue(
                page.evaluate("() => window.__TASK6_TEST__.pendingTimers()")
            )

            required_mark = page.locator(
                f"#idsvg-{SLIDER_ORDINAL}-live-shell-dispatch-result"
            )
            self.assertEqual(required_mark.count(), 1)
            required_mark.evaluate("node => node.remove()")
            released = page.evaluate(
                "() => window.__TASK6_TEST__.releaseOneAsync()"
            )
            self.assertEqual(released["kind"], "timeout")
            page.wait_for_function(
                f"() => document.getElementById('idrt-page-{SLIDER_ORDINAL}')"
                ".dataset.runtime === 'failed'",
                timeout=8_000,
            )

            self.assertEqual(
                page.evaluate(
                    "() => window.__TASK6_TEST__.steps.map(step => step.stepKey)"
                ),
                ["baseline-pause"],
                "a failed action must not emit deck:demo-step coverage",
            )
            demo_button = page.locator('[data-presenter-action="demo"]')
            self.assertEqual(demo_button.get_attribute("aria-pressed"), "false")
            cue = page.locator("#idrt-demo-cue")
            self.assertTrue(cue.is_hidden())
            self.assertIsNone(cue.get_attribute("data-slide-id"))
            self.assertIsNone(cue.get_attribute("data-target-key"))
            self.assertEqual(
                page.evaluate("() => window.__TASK6_TEST__.pendingCount()"), 0
            )
            self.assertEqual(
                page.evaluate("() => window.__TASK6_TEST__.pendingTimers()"), []
            )
            self.assertEqual(
                page.evaluate("() => window.__TASK6_TEST__.pendingRafs()"), []
            )
            before = page.evaluate(
                """() => ({
                  steps: window.__TASK6_TEST__.steps.length,
                  snapshot: window.InteractiveDeck.snapshot()
                })"""
            )
            page.wait_for_timeout(100)
            flushed = page.evaluate("() => window.__TASK6_TEST__.flushAll()")
            after = page.evaluate(
                """() => ({
                  steps: window.__TASK6_TEST__.steps.length,
                  snapshot: window.InteractiveDeck.snapshot()
                })"""
            )
            self.assertEqual(flushed["pending"], 0)
            self.assertEqual(after, before)
            self.assertEqual(
                after["snapshot"]["pages"][SLIDER_ORDINAL - 1]["failed"],
                "unavailable",
            )
            self.assertEqual(
                after["snapshot"]["pages"][SLIDER_ORDINAL - 1]["inputs"][
                    "coverage"
                ],
                "30",
            )
        finally:
            session.close()

    def test_zero_delay_alt_d_demo_uses_reducer_targets_and_ends_in_overview(self) -> None:
        """Catches a second demo transition path, cue clicks, or nondeterministic order."""
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.artifact,
                    init_script=ZERO_DELAY_SCHEDULER,
                )
                page = session.page
                try:
                    self._wait_ready(page)
                    self._activate(page, SLIDER_ORDINAL)
                    self._set_coverage_index(page, "6")
                    manual_target_page = page.evaluate(
                        """() => window.InteractiveDeck.snapshot().pages.find(
                          page => page.ordinal === 2
                        )"""
                    )
                    self._set_coverage_index(page, "9")
                    self._press_presenter_shortcut(page, "Alt+D")
                    self._assert_completed_demo(page, reduced_motion=False)
                    self.assertEqual(
                        page.evaluate(
                            """() => window.InteractiveDeck.snapshot().pages.find(
                              page => page.ordinal === 2
                            )"""
                        ),
                        manual_target_page,
                        "demo set actions must produce the same reducer snapshot as user input",
                    )
                    self.assertEqual(
                        page.evaluate("() => window.__TASK6_TEST__.order[0]"),
                        "ready",
                    )
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()
        self._assert_normal_cue_travels_between_separated_targets()
        self._assert_demo_fails_closed_when_required_mark_disappears()

    def test_hash_demo_starts_after_ready_and_reduced_motion_uses_static_ring(self) -> None:
        """Catches #demo racing boot or reduced motion skipping semantic actions."""
        for engine in ("chromium", "firefox"):
            with self.subTest(engine=engine):
                session = self.open_deck(
                    engine,
                    "http",
                    artifact=self.artifact,
                    init_script=ZERO_DELAY_SCHEDULER,
                    reduced_motion="reduce",
                    fragment="#demo",
                )
                page = session.page
                try:
                    self._wait_ready(page)
                    self._assert_completed_demo(page, reduced_motion=True)
                    order = page.evaluate("() => window.__TASK6_TEST__.order")
                    self.assertEqual(order[0], "ready")
                    self.assertEqual(order[-1], "end:complete")
                    self.assert_no_automatic_activity(session)
                finally:
                    session.close()

    def test_pointer_key_wheel_and_hash_cancel_demo_and_invalidate_callbacks(self) -> None:
        """Catches stale scheduled actions executing after any supported user cancellation."""
        actions = {
            "pointer": lambda page: page.mouse.click(10, 10),
            "key": lambda page: page.keyboard.press("ArrowRight"),
            "wheel": lambda page: page.mouse.wheel(0, 100),
            "hash": lambda page: page.evaluate("() => { location.hash = '#slide=3'; }"),
        }
        for engine in ("chromium", "firefox"):
            for action_name, action in actions.items():
                with self.subTest(engine=engine, action=action_name):
                    session = self.open_deck(
                        engine,
                        "http",
                        artifact=self.artifact,
                        init_script=HOLDING_SCHEDULER,
                    )
                    page = session.page
                    try:
                        self._wait_ready(page)
                        self._activate(page, SLIDER_ORDINAL)
                        demo_button = page.locator('[data-presenter-action="demo"]')
                        page.locator(f'[data-slide-id="{SLIDER_ID}"] h1').focus()
                        page.keyboard.press("Alt+D")
                        page.wait_for_function(
                            "() => window.__TASK6_TEST__.pendingCount() > 0",
                            timeout=8_000,
                        )
                        self.assertEqual(
                            page.evaluate("() => window.__TASK6_TEST__.ends"),
                            [],
                            "the starting key must not cancel its own demo",
                        )
                        target_step_count = 3 if action_name == "pointer" else 2
                        advanced = page.evaluate(
                            "count => window.__TASK6_TEST__.advanceUntilSteps(count)",
                            target_step_count,
                        )
                        self.assertEqual(advanced["steps"], target_step_count)
                        if action_name == "pointer":
                            self.assertTrue(
                                page.locator(
                                    f"#idrt-evidence-dialog-{SLIDER_ORDINAL}"
                                ).is_visible()
                            )
                        pending_rafs = page.evaluate(
                            "() => window.__TASK6_TEST__.pendingRafs()"
                        )
                        if action_name != "pointer":
                            self.assertTrue(
                                pending_rafs,
                                "the fixture must hold an active geometry RAF before cancellation",
                            )
                        action(page)
                        page.wait_for_function(
                            """() => window.__TASK6_TEST__.ends.some(
                              item => item.reason === "cancelled"
                            )""",
                            timeout=8_000,
                        )
                        cancelled_end = page.evaluate(
                            "() => window.__TASK6_TEST__.ends.at(-1)"
                        )
                        self.assertEqual(
                            set(cancelled_end),
                            {"reason", "slideId", "ordinal"},
                        )
                        self.assertEqual(cancelled_end["reason"], "cancelled")
                        cancelled_rafs = page.evaluate(
                            """() => window.__TASK6_TEST__.cancelled
                              .filter(item => item.kind === "raf").map(item => item.id)"""
                        )
                        self.assertTrue(set(pending_rafs) <= set(cancelled_rafs))
                        self.assertEqual(
                            page.evaluate("() => window.__TASK6_TEST__.pendingRafs()"),
                            [],
                        )
                        before = page.evaluate(
                            """() => ({
                              steps: window.__TASK6_TEST__.steps.length,
                              snapshot: window.InteractiveDeck.snapshot()
                            })"""
                        )
                        flushed = page.evaluate("() => window.__TASK6_TEST__.flushAll()")
                        after = page.evaluate(
                            """() => ({
                              steps: window.__TASK6_TEST__.steps.length,
                              snapshot: window.InteractiveDeck.snapshot()
                            })"""
                        )
                        self.assertEqual(flushed["pending"], 0)
                        self.assertEqual(after, before)
                        if action_name == "pointer":
                            self.assertTrue(
                                page.locator(
                                    f"#idrt-evidence-dialog-{SLIDER_ORDINAL}"
                                ).is_hidden()
                            )
                        if action_name == "hash":
                            self.assertEqual(
                                page.evaluate("() => location.hash"), "#slide=3"
                            )
                            self.assertEqual(
                                after["snapshot"]["currentSlide"], DETAIL_ORDINAL
                            )
                        self.assertTrue(page.locator("#idrt-demo-cue").is_hidden())
                        self.assertTrue(
                            demo_button.evaluate("node => node === document.activeElement")
                        )
                        cancellation_status = page.locator("#idrt-presenter-status")
                        expect(cancellation_status).to_contain_text("Demo cancelled")
                        self.assertRegex(
                            cancellation_status.inner_text(),
                            r"Slide [123]: ",
                        )
                        self.assertGreater(
                            page.evaluate("() => window.__TASK6_TEST__.cancelled.length"),
                            0,
                        )
                        self.assert_no_automatic_activity(session)
                    finally:
                        session.close()

    def _run_audit(
        self,
        output: Path,
        *,
        executable: str | None = None,
        manifest: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--manifest",
            str(manifest or self.audit_manifest),
            "--audit-out",
            str(output),
        ]
        if executable is not None:
            command.extend(["--chromium-executable", executable])
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = "0"
        return subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
            env=environment,
        )

    def test_audit_cli_reconstructs_canonical_states_with_closed_outputs(self) -> None:
        """Catches a ledger that cannot reconstruct screenshots or silently uses network."""
        output = self.fixture_root / "task6-audit"
        completed = self._run_audit(output)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        expected_top_level = {
            "audit-ledger.json",
            "state-atlas.html",
            "contact-sheet.html",
            "contact-sheet.png",
            "screenshots",
        }
        self.assertEqual({path.name for path in output.iterdir()}, expected_top_level)
        self.assertEqual(list(output.rglob("*.interactive.html")), [])

        ledger_bytes = (output / "audit-ledger.json").read_bytes()
        ledger = json.loads(ledger_bytes)
        self.assertEqual(
            set(ledger),
            {
                "schemaVersion",
                "deck",
                "browserContract",
                "proof",
                "states",
                "targetCoverage",
                "stepCoverage",
                "slides",
            },
        )
        self.assertEqual(ledger["schemaVersion"], "interactive-audit-v1")
        self.assertEqual(
            ledger["deck"],
            {
                "title": "Task 6 matrix <script>must stay text</script>",
                "lang": "en",
                "slideCount": len(self.audit_envelope["slides"]),
            },
        )
        self.assertEqual(
            ledger["browserContract"],
            {
                "engine": "chromium",
                "viewport": {"width": 1280, "height": 720},
                "screenshot": {"fullPage": False, "format": "png"},
            },
        )
        self.assertEqual(
            ledger["proof"],
            {
                "acceptedStateCount": sum(
                    slide.get("acceptedStateCount", 0)
                    for slide in ledger["slides"]
                ),
                "selectedScreenshotCount": len(ledger["states"]),
                "mathematicalEnumeration": "complete",
                "browserWitnessSelection": "canonical",
            },
        )
        self.assertEqual(
            {slide["sceneType"] for slide in ledger["slides"]},
            {
                "evidence_only",
                "state_toggle",
                "slider_model",
                "score_model",
                "drilldown",
                "accordion",
            },
        )
        self.assertEqual(len(ledger["states"]), 125)

        obligations_by_slide: dict[str, set[str]] = {}
        for state in ledger["states"]:
            obligations_by_slide.setdefault(state["slideId"], set()).update(
                state["obligations"]
            )
        for slide in ledger["slides"]:
            common = obligations_by_slide[slide["slideId"]]
            self.assertTrue(
                {"initial", "print", "static", "reduced-motion", "overview-after-change"}
                <= common
            )
        self.assertTrue(
            {"evidence:sources", "evidence:assumptions", "evidence:both"}
            <= obligations_by_slide["evidence-only"]
        )
        piecewise_obligations = obligations_by_slide["piecewise-model"]
        for side in ("below", "exact", "above"):
            self.assertTrue(
                any(
                    obligation.startswith("boundary:")
                    and obligation.endswith(":" + side)
                    for obligation in piecewise_obligations
                ),
                side,
            )
        self.assertTrue(
            {"classification:Early", "classification:Ready"}
            <= obligations_by_slide["score-model"]
        )

        state_keys = [state["stateKey"] for state in ledger["states"]]
        self.assertEqual(len(state_keys), len(set(state_keys)))
        states_by_key = {state["stateKey"]: state for state in ledger["states"]}
        screenshot_names = sorted(
            str(path.relative_to(output))
            for path in (output / "screenshots").iterdir()
        )
        self.assertEqual(
            screenshot_names,
            sorted(state["screenshot"] for state in ledger["states"]),
        )
        expected_targets = {
            (slide["slideId"], key)
            for slide in self.audit_envelope["slides"]
            if slide["scene"] is not None
            for key in slide["scene"]["targets"]
        }
        public_range_inputs = {
            slide["slideId"]: {
                control["id"]
                for control in slide["scene"]["controls"]
                if control["kind"] == "range"
            }
            for slide in self.audit_envelope["slides"]
            if slide["scene"] is not None
        }
        for state in ledger["states"]:
            self.assertTrue(state["obligations"])
            self.assertEqual(
                set(state),
                {
                    "stateKey",
                    "slideId",
                    "ordinal",
                    "fragment",
                    "setup",
                    "obligations",
                    "expected",
                    "screenshot",
                    "reconstruction",
                },
            )
            self.assertEqual(
                set(state["expected"]),
                {"inputs", "outputs", "outcome", "viewMode", "authorProbe"},
            )
            author_probe = state["expected"]["authorProbe"]
            self.assertEqual(
                set(author_probe),
                {
                    "categoricalInputs",
                    "panel",
                    "evidenceMode",
                    "overlay",
                    "overviewOpen",
                    "failed",
                },
            )
            expected_categorical_inputs = {
                control_id: state["expected"]["inputs"][control_id]
                for control_id in state["expected"]["inputs"]
                if control_id not in public_range_inputs[state["slideId"]]
                and control_id not in {"panel", "evidence"}
            }
            self.assertEqual(
                author_probe["categoricalInputs"],
                expected_categorical_inputs,
            )
            self.assertEqual(
                author_probe["panel"],
                state["expected"]["inputs"].get("panel"),
            )
            if "evidence" in state["expected"]["inputs"]:
                self.assertEqual(
                    author_probe["evidenceMode"],
                    state["expected"]["inputs"]["evidence"],
                )
            if author_probe["overlay"] is not None:
                self.assertEqual(
                    set(author_probe["overlay"]),
                    {"kind", "ordinal", "tab"},
                )
                self.assertEqual(author_probe["overlay"]["kind"], "evidence")
                self.assertEqual(
                    author_probe["overlay"]["ordinal"], state["ordinal"]
                )
                self.assertIn(
                    author_probe["overlay"]["tab"], {"sources", "assumptions"}
                )
            self.assertRegex(
                state["fragment"],
                rf"^#slide={state['ordinal']}(?:&|$)",
            )
            setup_fields = {
                "emulateReducedMotion": {"action"},
                "openOverview": {"action"},
                "openEvidence": {"action"},
                "closeEvidence": {"action"},
                "selectEvidenceTab": {"action", "tab"},
                "openPanel": {"action", "panel"},
                "closePanel": {"action", "panel"},
                "assertTarget": {"action", "targetKey"},
            }
            for setup in state["setup"]:
                self.assertIn(setup["action"], setup_fields)
                self.assertEqual(set(setup), setup_fields[setup["action"]])
                if setup.get("targetKey", "").startswith("source:"):
                    self.assertEqual(setup["action"], "assertTarget")
            screenshot = output / state["screenshot"]
            self.assertTrue(screenshot.is_file())
            screenshot_bytes = screenshot.read_bytes()
            self.assertTrue(screenshot_bytes.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertEqual(
                (
                    int.from_bytes(screenshot_bytes[16:20], "big"),
                    int.from_bytes(screenshot_bytes[20:24], "big"),
                ),
                (1280, 720),
            )
            reconstruction = state["reconstruction"]
            self.assertEqual(
                set(reconstruction),
                {
                    "sanitizedSnapshot",
                    "semanticDigest",
                    "pngSha256",
                    "runtimeReady",
                    "networkRequests",
                    "consoleErrors",
                    "targetHitBoxes",
                    "staticParity",
                    "authorProbe",
                },
            )
            self.assertEqual(
                hashlib.sha256(screenshot_bytes).hexdigest(),
                reconstruction["pngSha256"],
            )
            self.assertTrue(reconstruction["runtimeReady"])
            self.assertEqual(reconstruction["networkRequests"], [])
            self.assertEqual(reconstruction["consoleErrors"], [])
            self.assertTrue(reconstruction["staticParity"])
            self.assertRegex(reconstruction["semanticDigest"], r"^[0-9a-f]{64}$")
            self.assertIs(type(reconstruction["targetHitBoxes"]), dict)
            for target_key, hit_box in reconstruction["targetHitBoxes"].items():
                self.assertIn((state["slideId"], target_key), expected_targets)
                self.assertEqual(set(hit_box), {"x", "y", "width", "height"})
                self.assertTrue(
                    all(isinstance(value, str) for value in hit_box.values())
                )
                self.assertGreater(Decimal(hit_box["width"]), 0)
                self.assertGreater(Decimal(hit_box["height"]), 0)
            snapshot = reconstruction["sanitizedSnapshot"]
            self.assertEqual(snapshot["currentSlide"], state["ordinal"])
            current_page = snapshot["pages"][state["ordinal"] - 1]
            for field in ("outputs", "outcome", "viewMode"):
                self.assertEqual(current_page[field], state["expected"][field])
            expected_public_inputs = {
                control_id: state["expected"]["inputs"][control_id]
                for control_id in public_range_inputs[state["slideId"]]
            }
            self.assertEqual(current_page["inputs"], expected_public_inputs)

        evidence_both = next(
            state
            for state in ledger["states"]
            if state["slideId"] == "evidence-only"
            and "evidence:both" in state["obligations"]
        )
        self.assertIn("evidence=both", evidence_both["fragment"])
        self.assertNotIn(
            "openEvidence",
            {setup["action"] for setup in evidence_both["setup"]},
        )
        self.assertEqual(
            evidence_both["expected"]["authorProbe"]["evidenceMode"],
            "both",
        )
        self.assertEqual(
            evidence_both["reconstruction"]["authorProbe"],
            evidence_both["expected"]["authorProbe"],
        )

        self._assert_author_probe_replay(ledger)

        self.assertEqual(
            {
                (row["slideId"], row["targetKey"])
                for row in ledger["targetCoverage"]
            },
            expected_targets,
        )
        for row in ledger["targetCoverage"]:
            self.assertEqual(
                set(row),
                {"slideId", "ordinal", "targetKey", "coverageMode", "stateKey"},
            )
            self.assertIn(row["coverageMode"], {"hitbox", "presence"})
            self.assertIn(row["stateKey"], state_keys)
            self.assertEqual(
                row["coverageMode"],
                "presence" if row["targetKey"].startswith("source:") else "hitbox",
            )
            self.assertIn(
                row["targetKey"],
                states_by_key[row["stateKey"]]["reconstruction"]["targetHitBoxes"],
            )
        expected_steps = {
            (slide["slideId"], step["stepKey"]): (
                step["action"]["type"],
                step.get("targetKey"),
            )
            for slide in self.audit_envelope["slides"]
            if slide["scene"] is not None
            for step in slide["scene"]["steps"]
        }
        self.assertEqual(
            {
                (row["slideId"], row["stepKey"])
                for row in ledger["stepCoverage"]
            },
            set(expected_steps),
        )
        for row in ledger["stepCoverage"]:
            self.assertEqual(
                set(row),
                {"slideId", "ordinal", "stepKey", "action"}
                | ({"targetKey"} if "targetKey" in row else set())
                | ({"stateKey"} if "stateKey" in row else set()),
            )
            if "targetKey" in row:
                self.assertIn((row["slideId"], row["targetKey"]), expected_targets)
            if "stateKey" in row:
                self.assertIn(row["stateKey"], state_keys)
            expected_action, expected_target = expected_steps[
                (row["slideId"], row["stepKey"])
            ]
            self.assertEqual(row["action"], expected_action)
            self.assertEqual(row.get("targetKey"), expected_target)

        for name in ("state-atlas.html", "contact-sheet.html"):
            text = (output / name).read_text(encoding="utf-8")
            self.assertNotRegex(text.lower(), r"<\s*script\b")
            self.assertRegex(
                text,
                r"Content-Security-Policy[^>]+default-src (?:&(?:#39|#x27|apos);|')none",
            )
            self.assertIn("&lt;script&gt;must stay text&lt;/script&gt;", text)
            self.assertNotIn("<script>must stay text</script>", text)
            self.assertNotRegex(text, r"https?://")
        contact_png = (output / "contact-sheet.png").read_bytes()
        self.assertTrue(contact_png.startswith(b"\x89PNG\r\n\x1a\n"))

        repeat_output = self.fixture_root / "task6-audit-repeat"
        repeated = self._run_audit(repeat_output)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        first_files = {
            str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in output.rglob("*")
            if path.is_file()
        }
        repeated_files = {
            str(path.relative_to(repeat_output)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in repeat_output.rglob("*")
            if path.is_file()
        }
        self.assertEqual(len(first_files), 129)
        self.assertEqual(set(repeated_files), set(first_files))
        differing_files = {
            name: (first_files[name], repeated_files[name])
            for name in first_files
            if first_files[name] != repeated_files[name]
        }
        self.assertEqual(differing_files, {})
        repeated_ledger = json.loads(
            (repeat_output / "audit-ledger.json").read_bytes()
        )
        self.assertEqual(
            [
                {key: value for key, value in state.items() if key != "reconstruction"}
                for state in repeated_ledger["states"]
            ],
            [
                {key: value for key, value in state.items() if key != "reconstruction"}
                for state in ledger["states"]
            ],
        )
        self.assertEqual(
            repeated_ledger["targetCoverage"], ledger["targetCoverage"]
        )
        self.assertEqual(
            repeated_ledger["stepCoverage"], ledger["stepCoverage"]
        )
        for state in repeated_ledger["states"]:
            screenshot = repeat_output / state["screenshot"]
            self.assertEqual(
                hashlib.sha256(screenshot.read_bytes()).hexdigest(),
                state["reconstruction"]["pngSha256"],
            )

    def test_audit_browser_launch_failure_leaves_no_partial_output(self) -> None:
        """Catches staging publication before Chromium has completed every state."""
        output = self.fixture_root / "task6-audit-failed"
        completed = self._run_audit(
            output,
            executable="/bin/false",
            manifest=self.manifest,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertFalse(output.exists())
        self.assertEqual(
            list(output.parent.glob(".task6-audit-failed.stage-*")),
            [],
        )
        self.assertEqual(completed.stdout, "")
        self.assertEqual(
            completed.stderr.strip(),
            "ERROR: interactive audit failed [browser_unavailable]",
        )


if __name__ == "__main__":
    unittest.main()
