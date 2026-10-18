#!/usr/bin/env python3
"""Drive an interactive deck through its author-only canonical audit plan."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable, Mapping

try:
    from . import build_interactive_deck as builder
    from ._interactive_audit import (
        AuditError,
        attach_reconstruction,
        compile_audit_plan,
        ledger_bytes,
        publish_audit_directory,
        render_contact_sheet,
        render_state_atlas,
        validate_audit_destination,
    )
except ImportError:  # Direct script execution.
    import build_interactive_deck as builder
    from _interactive_audit import (
        AuditError,
        attach_reconstruction,
        compile_audit_plan,
        ledger_bytes,
        publish_audit_directory,
        render_contact_sheet,
        render_state_atlas,
        validate_audit_destination,
    )

VIEWPORT = {"width": 1280, "height": 720}
SEMANTIC_DIGEST_VERSION = "active-slide-semantics-v1"
SEMANTIC_DIGEST_SCRIPT = r"""() => {
  const current = window.InteractiveDeck.snapshot().currentSlide;
  const section = document.querySelector('.deck-slide[data-ordinal="' + current + '"]') ||
    document.querySelector('[data-slide-id]:not([hidden])');
  if (!section) { throw new Error('E_AUDIT_SEMANTIC_ROOT'); }
  const normalize = value => String(value || '').replace(/\s+/g, ' ').trim();
  const attributes = [];
  const nodes = section.querySelectorAll(
    'h1, h2, h3, button, input, select, output, [role], [aria-live], [aria-expanded], [aria-pressed]'
  );
  for (const node of nodes) {
    if (node.hidden) { continue; }
    attributes.push({
      tag: node.tagName.toLowerCase(),
      text: normalize(node.textContent),
      role: node.getAttribute('role') || '',
      expanded: node.getAttribute('aria-expanded') || '',
      pressed: node.getAttribute('aria-pressed') || '',
      value: node instanceof HTMLInputElement || node instanceof HTMLSelectElement ? node.value : ''
    });
  }
  return {
    version: 'active-slide-semantics-v1',
    slideId: section.getAttribute('data-slide-id') || '',
    text: normalize(section.innerText),
    attributes
  };
}"""
AUTHOR_PROBE_SCRIPT = r"""ordinal => {
  const snapshot = window.InteractiveDeck.snapshot();
  const section = document.getElementById('idrt-page-' + ordinal);
  if (!section || section.hidden || snapshot.currentSlide !== ordinal) {
    throw new Error('E_AUDIT_PROBE_ROOT');
  }
  const categoricalInputs = {};
  const controls = section.querySelectorAll('[data-control-id]');
  for (const wrapper of controls) {
    if (wrapper.matches('input[type="range"]')) { continue; }
    const id = wrapper.getAttribute('data-control-id');
    if (!id || Object.prototype.hasOwnProperty.call(categoricalInputs, id)) {
      throw new Error('E_AUDIT_PROBE_CONTROL');
    }
    const select = wrapper.matches('select') ? wrapper : wrapper.querySelector('select');
    if (select) {
      categoricalInputs[id] = select.value;
      continue;
    }
    const pressed = wrapper.querySelectorAll('[data-control-value][aria-pressed="true"]');
    if (pressed.length !== 1) { throw new Error('E_AUDIT_PROBE_CONTROL'); }
    categoricalInputs[id] = pressed[0].getAttribute('data-control-value');
  }
  let panel = null;
  const panelSurface = section.querySelector('.panel-surface');
  if (panelSurface) {
    const expanded = panelSurface.querySelectorAll(
      '[data-panel-target][aria-expanded="true"],[data-accordion-id][aria-expanded="true"]'
    );
    if (expanded.length > 1) { throw new Error('E_AUDIT_PROBE_PANEL'); }
    if (expanded.length === 1) {
      panel = expanded[0].getAttribute('data-panel-target') ||
        expanded[0].getAttribute('data-accordion-id');
    }
  }
  const parameters = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const evidenceMode = parameters.has('evidence') ? parameters.get('evidence') : null;
  if ([null, 'closed', 'sources', 'assumptions', 'both'].indexOf(evidenceMode) < 0) {
    throw new Error('E_AUDIT_PROBE_EVIDENCE');
  }
  const dialog = document.getElementById('idrt-evidence-dialog-' + ordinal);
  let overlay = null;
  if (!dialog || dialog.getAttribute('data-slide-ordinal') !== String(ordinal)) {
    throw new Error('E_AUDIT_PROBE_DIALOG');
  }
  if (!dialog.hidden) {
    const selected = dialog.querySelectorAll('[data-evidence-tab][aria-selected="true"]');
    const visiblePanels = Array.from(dialog.querySelectorAll('[data-evidence-panel]')).filter(node => !node.hidden);
    let tab = selected.length === 1 ? selected[0].getAttribute('data-evidence-tab') :
      visiblePanels.length === 1 ? visiblePanels[0].getAttribute('data-evidence-panel') : null;
    if (!tab && snapshot.overlay && snapshot.overlay.ordinal === ordinal) { tab = snapshot.overlay.tab; }
    if (tab !== 'sources' && tab !== 'assumptions') { throw new Error('E_AUDIT_PROBE_DIALOG'); }
    overlay = {kind: 'evidence', ordinal, tab};
  }
  const overview = document.getElementById('idrt-presenter-overview');
  const runtime = section.getAttribute('data-runtime');
  if (!overview || (runtime !== 'ready' && runtime !== 'failed')) {
    throw new Error('E_AUDIT_PROBE_RUNTIME');
  }
  return {
    categoricalInputs, panel, evidenceMode, overlay,
    overviewOpen: !overview.hidden,
    failed: runtime === 'failed' ? 'unavailable' : null
  };
}"""

def _stable_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonicalize_png(page: object, payload: bytes) -> bytes:
    """Encode equal screenshot pixels to equal bytes in Chromium's C++ path."""
    encoded = base64.b64encode(payload).decode("ascii")
    canonical = page.evaluate(
        """async encoded => {
          const binary = atob(encoded);
          const bytes = new Uint8Array(binary.length);
          for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
          }
          const bitmap = await createImageBitmap(new Blob([bytes], {type: 'image/png'}));
          const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
          const context = canvas.getContext('2d', {alpha: false});
          if (!context) { bitmap.close(); throw new Error('E_AUDIT_CANVAS'); }
          context.fillStyle = '#ffffff';
          context.fillRect(0, 0, bitmap.width, bitmap.height);
          context.drawImage(bitmap, 0, 0);
          bitmap.close();
          const blob = await canvas.convertToBlob({type: 'image/png'});
          const output = new Uint8Array(await blob.arrayBuffer());
          let value = '';
          const chunk = 32768;
          for (let index = 0; index < output.length; index += chunk) {
            value += String.fromCharCode(...output.subarray(index, index + chunk));
          }
          return btoa(value);
        }""",
        encoded,
    )
    if not isinstance(canonical, str):
        raise AuditError("browser_failed")
    try:
        result = base64.b64decode(canonical, validate=True)
    except (ValueError, base64.binascii.Error) as error:
        raise AuditError("browser_failed") from error
    if not result.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AuditError("browser_failed")
    return result

def _write_file(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise AuditError("unsafe_output")
    path.parent.mkdir(parents=False, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())

def _target_locator(page: object, slide_id: str, target_key: str):
    if not isinstance(slide_id, str) or not isinstance(target_key, str):
        raise AuditError("invalid_reconstruction")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in slide_id + target_key.replace(":", "")):
        raise AuditError("invalid_reconstruction")
    return page.locator(
        f'[data-target-slide="{slide_id}"][data-target-key="{target_key}"]'
    )

def _assert_target(page: object, slide_id: str, target_key: str) -> dict:
    locator = _target_locator(page, slide_id, target_key)
    if locator.count() != 1:
        raise AuditError("target_missing")
    box = locator.bounding_box()
    if box is None or box["width"] <= 0 or box["height"] <= 0:
        raise AuditError("target_hitbox")
    return {key: round(float(box[key]), 3) for key in ("x", "y", "width", "height")}

def _click_target(page: object, slide_id: str, target_key: str) -> None:
    if target_key.startswith("source:"):
        raise AuditError("source_activation_forbidden")
    locator = _target_locator(page, slide_id, target_key)
    if locator.count() != 1:
        raise AuditError("target_missing")
    locator.dispatch_event("click")


def _stabilize_capture_ui(page: object) -> None:
    """Remove presenter-idle timing from author screenshots.

    Runtime chrome intentionally fades after 2.5 seconds. Audit reconstruction
    cost varies by machine and state, so capture a single canonical idle state
    instead of racing that timer.
    """
    page.evaluate(
        """() => {
          const chrome = document.getElementById('idrt-presenter-chrome');
          if (!chrome) { throw new Error('E_AUDIT_PRESENTER_CHROME'); }
          const sheet = Array.from(document.styleSheets).find(candidate => {
            try { return candidate.cssRules.length > 0; } catch (_error) { return false; }
          });
          if (!sheet) { throw new Error('E_AUDIT_STYLESHEET'); }
          sheet.insertRule(
            '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}',
            sheet.cssRules.length
          );
          chrome.classList.add('is-idle');
        }"""
    )

def _apply_setup(page: object, state: Mapping[str, object]) -> dict[str, dict]:
    hit_boxes: dict[str, dict] = {}
    slide_id = str(state["slideId"])
    for step in state["setup"]:
        action = step["action"]
        if action == "emulateReducedMotion":
            # This action is applied before navigation by the caller.
            continue
        if action == "openOverview":
            page.locator("html").dispatch_event(
                "keydown", {"key": "o", "code": "KeyO", "altKey": True}
            )
        elif action == "openEvidence":
            _click_target(page, slide_id, "evidence:open")
        elif action == "closeEvidence":
            _click_target(page, slide_id, "evidence:close")
        elif action == "selectEvidenceTab":
            tab = step["tab"]
            ordinal = state["ordinal"]
            locator = page.locator(
                f'#idrt-evidence-dialog-{ordinal}[data-slide-ordinal="{ordinal}"]:not([hidden]) '
                f'[data-evidence-tab="{tab}"]'
            )
            if locator.count() != 1 or not locator.is_visible():
                raise AuditError("target_missing")
            locator.dispatch_event("click")
            if not locator.is_visible() or locator.get_attribute("aria-selected") != "true":
                raise AuditError("target_missing")
        elif action == "openPanel":
            _click_target(page, slide_id, "panel:" + step["panel"])
        elif action == "closePanel":
            _click_target(page, slide_id, "panel:" + step["panel"] + ":close")
        elif action == "assertTarget":
            target_key = step["targetKey"]
            hit_boxes[target_key] = _assert_target(page, slide_id, target_key)
        else:
            raise AuditError("unreconstructable_setup")
    return hit_boxes

def _assert_expected(
    snapshot: Mapping[str, object],
    state: Mapping[str, object],
    *,
    author_probe: Mapping[str, object] | None = None,
) -> None:
    ordinal = state["ordinal"]
    if snapshot.get("currentSlide") != ordinal:
        raise AuditError("reconstruction_mismatch")
    reduced = any(step["action"] == "emulateReducedMotion" for step in state["setup"])
    if snapshot.get("reducedMotion") is not reduced:
        raise AuditError("reconstruction_mismatch")
    pages = snapshot.get("pages")
    if not isinstance(pages, list) or not 1 <= ordinal <= len(pages):
        raise AuditError("reconstruction_mismatch")
    page = pages[ordinal - 1]
    if not isinstance(page, Mapping):
        raise AuditError("reconstruction_mismatch")
    expected = state["expected"]
    expected_probe = expected.get("authorProbe")
    if expected_probe is not None and author_probe != expected_probe:
        raise AuditError("reconstruction_mismatch")
    if page.get("outcome") != expected.get("outcome"):
        raise AuditError("reconstruction_mismatch")
    if page.get("viewMode") != expected.get("viewMode"):
        raise AuditError("reconstruction_mismatch")
    outputs = page.get("outputs")
    if not isinstance(outputs, Mapping) or dict(outputs) != expected.get("outputs"):
        raise AuditError("reconstruction_mismatch")
    inputs = page.get("inputs")
    if not isinstance(inputs, Mapping):
        raise AuditError("reconstruction_mismatch")
    observed_inputs = dict(inputs)
    if author_probe is not None:
        categorical = author_probe.get("categoricalInputs")
        if not isinstance(categorical, Mapping):
            raise AuditError("reconstruction_mismatch")
        observed_inputs.update(categorical)
        if "panel" in expected.get("inputs", {}):
            observed_inputs["panel"] = author_probe.get("panel")
        if "evidence" in expected.get("inputs", {}):
            observed_inputs["evidence"] = author_probe.get("evidenceMode")
        if snapshot.get("overlay") != author_probe.get("overlay"):
            raise AuditError("reconstruction_mismatch")
        if page.get("failed") != author_probe.get("failed"):
            raise AuditError("reconstruction_mismatch")
    if observed_inputs != expected.get("inputs"):
        raise AuditError("reconstruction_mismatch")

def _static_parity(page: object, state: Mapping[str, object]) -> bool:
    expected_static = state["expected"].get("viewMode") == "static"
    return bool(page.evaluate(
        """expectedStatic => {
          const ordinal = window.InteractiveDeck.snapshot().currentSlide;
          const section = document.querySelector('.deck-slide[data-ordinal="' + ordinal + '"]') ||
            document.querySelector('[data-slide-id]:not([hidden])');
          if (!section) { return false; }
          const fallback = section.querySelector('.fallback-layer');
          if (!fallback) { return false; }
          const visible = !fallback.hidden && getComputedStyle(fallback).display !== 'none' &&
            getComputedStyle(fallback).visibility !== 'hidden';
          return expectedStatic ? visible : !visible;
        }""",
        expected_static,
    ))

def run_browser_audit(
    deck_path: Path,
    ledger: dict,
    staging: Path,
    chromium_executable: Path | None = None,
) -> dict:
    """Reconstruct and capture every planned state in one Chromium context."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise AuditError("browser_unavailable") from error

    if chromium_executable is not None:
        chromium_executable = Path(chromium_executable)
        if not chromium_executable.is_file() or chromium_executable.is_symlink():
            raise AuditError("browser_unavailable")
    screenshot_dir = staging / "screenshots"
    screenshot_dir.mkdir()
    finalized = copy.deepcopy(ledger)
    browser = None
    try:
        with sync_playwright() as playwright:
            launch = {"headless": True}
            if chromium_executable is not None:
                launch["executable_path"] = str(chromium_executable)
            try:
                browser = playwright.chromium.launch(**launch)
            except PlaywrightError as error:
                raise AuditError("browser_unavailable") from error
            context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
            page = context.new_page()
            state_network: list[str] = []
            state_console: list[str] = []
            page_errors: list[str] = []

            def record_request(request: object) -> None:
                url = request.url
                if url.startswith(("http://", "https://")):
                    state_network.append("automatic-network")

            def record_console(message: object) -> None:
                if message.type == "error":
                    state_console.append("console-error")

            page.on("request", record_request)
            page.on("console", record_console)
            page.on("pageerror", lambda _error: page_errors.append("page-error"))
            base_url = deck_path.resolve(strict=True).as_uri()
            for planned in ledger["states"]:
                state_network.clear()
                state_console.clear()
                page_errors.clear()
                reduced = any(step["action"] == "emulateReducedMotion" for step in planned["setup"])
                page.emulate_media(reduced_motion="reduce" if reduced else "no-preference")
                page.goto("about:blank", wait_until="load")
                page.goto(base_url + planned["fragment"], wait_until="load")
                page.wait_for_function(
                    """ordinal => {
                      if (!window.InteractiveDeck || typeof window.InteractiveDeck.snapshot !== 'function') { return false; }
                      const snapshot = window.InteractiveDeck.snapshot();
                      if (snapshot.currentSlide !== ordinal) { return false; }
                      const section = document.querySelector('.deck-slide[data-ordinal="' + ordinal + '"]') ||
                        document.querySelector('[data-slide-id]:not([hidden])');
                      return !!section && (!section.dataset.runtime || section.dataset.runtime === 'ready');
                    }""",
                    arg=planned["ordinal"],
                )
                hit_boxes = _apply_setup(page, planned)
                page.wait_for_timeout(450)
                _stabilize_capture_ui(page)
                snapshot = page.evaluate("() => window.InteractiveDeck.snapshot()")
                author_probe = page.evaluate(AUTHOR_PROBE_SCRIPT, planned["ordinal"])
                _assert_expected(snapshot, planned, author_probe=author_probe)
                semantic = page.evaluate(SEMANTIC_DIGEST_SCRIPT)
                semantic_digest = hashlib.sha256(_stable_json(semantic)).hexdigest()
                png = _canonicalize_png(page, page.screenshot(full_page=False))
                png_path = staging / planned["screenshot"]
                _write_file(png_path, png)
                observed = {
                    "sanitizedSnapshot": snapshot,
                    "authorProbe": author_probe,
                    "semanticDigest": semantic_digest,
                    "pngSha256": hashlib.sha256(png).hexdigest(),
                    "runtimeReady": not page_errors,
                    "networkRequests": list(state_network),
                    "consoleErrors": list(state_console) + list(page_errors),
                    "targetHitBoxes": hit_boxes,
                    "staticParity": _static_parity(page, planned),
                }
                finalized = attach_reconstruction(finalized, planned["stateKey"], observed)

            contact_path = staging / "contact-sheet.html"
            page.emulate_media(reduced_motion="reduce")
            page.goto(contact_path.resolve(strict=True).as_uri(), wait_until="load")
            page.wait_for_load_state("load")
            contact_png = _canonicalize_png(page, page.screenshot(full_page=True))
            _write_file(staging / "contact-sheet.png", contact_png)
            context.close()
            browser.close()
            browser = None
    except AuditError:
        raise
    except Exception as error:
        raise AuditError("browser_failed") from error
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
    return finalized

def _validate_final_staging(staging: Path, ledger: Mapping[str, object]) -> None:
    expected = {
        "audit-ledger.json", "state-atlas.html", "contact-sheet.html",
        "contact-sheet.png", "screenshots",
    }
    if {entry.name for entry in staging.iterdir()} != expected:
        raise AuditError("partial_output")
    states = ledger.get("states")
    if not isinstance(states, list) or any("reconstruction" not in state for state in states):
        raise AuditError("partial_output")
    screenshots = staging / "screenshots"
    expected_pngs = {Path(state["screenshot"]).name for state in states}
    if {path.name for path in screenshots.iterdir()} != expected_pngs:
        raise AuditError("partial_output")

def run_audit(
    manifest: Path,
    audit_out: Path,
    *,
    chromium_executable: Path | None = None,
    browser_runner: Callable[[Path, dict, Path, Path | None], dict] | None = None,
) -> Path:
    destination = validate_audit_destination(Path(audit_out))
    manifest = Path(manifest)
    try:
        compiled = builder.compile_manifest(manifest)
        plan = compile_audit_plan(compiled)
        deck_html = builder.bundle_deck(
            title=compiled.title,
            lang=compiled.lang,
            slides=compiled.slides,
            assets=builder.load_runtime_assets(),
        )
    except AuditError:
        raise
    except Exception as error:
        raise AuditError("compile_failed") from error

    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    runner = browser_runner or run_browser_audit
    try:
        _write_file(staging / "state-atlas.html", render_state_atlas(plan.ledger).encode("utf-8"))
        _write_file(staging / "contact-sheet.html", render_contact_sheet(plan.ledger).encode("utf-8"))
        with tempfile.TemporaryDirectory(prefix="interactive-audit-deck-") as temporary:
            deck_path = Path(temporary) / "deck.interactive.html"
            _write_file(deck_path, deck_html.encode("utf-8"))
            finalized = runner(deck_path, plan.ledger, staging, chromium_executable)
        # Re-render from the finalized ledger.  The visible cards are identical,
        # but this keeps the artifact derivation explicit and deterministic.
        (staging / "state-atlas.html").write_text(render_state_atlas(finalized), encoding="utf-8", newline="\n")
        (staging / "contact-sheet.html").write_text(render_contact_sheet(finalized), encoding="utf-8", newline="\n")
        _write_file(staging / "audit-ledger.json", ledger_bytes(finalized))
        _validate_final_staging(staging, finalized)
        publish_audit_directory(staging, destination)
        return destination
    except AuditError:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    except Exception as error:
        if staging.exists():
            shutil.rmtree(staging)
        raise AuditError("audit_failed") from error

class _CliUsageError(Exception):
    pass

class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise _CliUsageError

def main(argv: list[str] | None = None) -> int:
    parser = _SafeArgumentParser(description="Audit a compiled interactive deck in Chromium.")
    parser.add_argument("--manifest", required=True, help="Deck manifest JSON")
    parser.add_argument("--audit-out", required=True, help="Explicit audit output directory")
    parser.add_argument("--chromium-executable", help="Optional explicit Chromium executable")
    try:
        args = parser.parse_args(argv)
    except _CliUsageError:
        import sys
        print("ERROR: interactive audit failed [cli_usage]", file=sys.stderr)
        return 2
    try:
        run_audit(
            Path(args.manifest),
            Path(args.audit_out),
            chromium_executable=Path(args.chromium_executable) if args.chromium_executable else None,
        )
    except AuditError as error:
        import sys
        print(f"ERROR: interactive audit failed [{error.code}]", file=sys.stderr)
        return 1
    except Exception:
        import sys
        print("ERROR: interactive audit failed [internal_error]", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
