"""Deterministic serialization, rendering, and safe publishing for audit output."""
from __future__ import annotations

import copy
from dataclasses import fields, is_dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
from typing import Callable, Mapping

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_OUTPUTS = frozenset((
    "audit-ledger.json",
    "state-atlas.html",
    "contact-sheet.html",
    "contact-sheet.png",
    "screenshots",
))

class AuditError(ValueError):
    """A stable, non-sensitive audit failure."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"interactive audit failed [{code}]")

def decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise AuditError("invalid_author_record")
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text

def canonical(value: object) -> object:
    if isinstance(value, Decimal):
        return decimal_text(value)
    if is_dataclass(value):
        return {field.name: canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [canonical(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        try:
            return decimal_text(Decimal(str(value)))
        except InvalidOperation as error:
            raise AuditError("invalid_author_record") from error
    raise AuditError("invalid_author_record")

def json_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            canonical(value), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise AuditError("invalid_author_record") from error
    return (text + "\n").encode("utf-8")

def ledger_bytes(ledger: Mapping[str, object]) -> bytes:
    return json_bytes(ledger)

def state_key(ordinal: int, slide_id: str, identity: bytes) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", slide_id.lower()).strip("-")
    digest = hashlib.sha256(identity).hexdigest()[:12]
    return f"s{ordinal:03d}-{(slug or 'slide')[:32]}-{digest}"

def state_identity(slide_id: str, fragment: str, setup: list[dict]) -> bytes:
    return json_bytes({"slideId": slide_id, "fragment": fragment, "setup": setup})

def expected_author_probe(
    ordinal: int,
    scene: Mapping[str, object],
    state: Mapping[str, object],
    setup: list[dict],
) -> dict:
    """Project the closed browser-only state that the public API omits."""
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 1:
        raise AuditError("invalid_author_record")
    categorical: dict[str, str] = {}
    for control in scene.get("controls", []):
        if not isinstance(control, Mapping) or not isinstance(control.get("id"), str):
            raise AuditError("invalid_author_record")
        control_id = control["id"]
        if control.get("kind") != "range":
            value = state.get(control_id)
            if not isinstance(value, str):
                raise AuditError("invalid_author_record")
            categorical[control_id] = value

    scene_type = scene.get("type")
    panel = state.get("panel") if scene_type in ("drilldown", "accordion") else None
    evidence_mode = state.get("evidence") if scene_type == "evidence_only" else None
    evidence = scene.get("evidence", {})
    sources = evidence.get("sources", []) if isinstance(evidence, Mapping) else []
    default_tab = "sources" if sources else "assumptions"
    overlay = None
    if evidence_mode not in (None, "closed"):
        tab = default_tab if evidence_mode == "both" else evidence_mode
        overlay = {"kind": "evidence", "ordinal": ordinal, "tab": tab}
    overview_open = False
    for step in setup:
        action = step.get("action") if isinstance(step, Mapping) else None
        if action == "openEvidence":
            overlay = {"kind": "evidence", "ordinal": ordinal, "tab": default_tab}
            if scene_type == "evidence_only":
                evidence_mode = default_tab
        elif action == "closeEvidence":
            overlay = None
            if scene_type == "evidence_only":
                evidence_mode = "closed"
        elif action == "selectEvidenceTab":
            if overlay is None:
                raise AuditError("unreconstructable_setup")
            overlay = {"kind": "evidence", "ordinal": ordinal, "tab": step.get("tab")}
            if scene_type == "evidence_only":
                evidence_mode = step.get("tab")
        elif action == "openPanel":
            panel = step.get("panel")
        elif action == "closePanel":
            panel = None
        elif action == "openOverview":
            overview_open = True
    return {
        "categoricalInputs": categorical,
        "panel": panel,
        "evidenceMode": evidence_mode,
        "overlay": overlay,
        "overviewOpen": overview_open,
        "failed": None,
    }

def _witness_dict(witness: object) -> dict:
    state = getattr(witness, "state", None)
    if not isinstance(state, (tuple, list)):
        raise AuditError("invalid_author_record")
    return {
        "state": {str(key): canonical(value) for key, value in state},
        "distance": canonical(getattr(witness, "distance", None)),
        "outcome": getattr(witness, "outcome", None),
    }

def _boundary_records(boundaries: tuple) -> list[dict]:
    records: list[dict] = []
    for entry in boundaries:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise AuditError("invalid_author_record")
        boundary, state = entry
        if not isinstance(boundary, (tuple, list)) or len(boundary) != 3:
            raise AuditError("invalid_author_record")
        records.append({
            "control": boundary[0], "value": canonical(boundary[1]),
            "side": boundary[2],
            "state": {str(key): canonical(value) for key, value in state},
        })
    return records

def _decimal_value(value: object) -> Decimal:
    if isinstance(value, Mapping):
        value = value.get("value")
    elif hasattr(value, "value"):
        value = getattr(value, "value")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise AuditError("invalid_author_record")
    if not result.is_finite():
        raise AuditError("invalid_author_record")
    return result

def validate_boundary_coverage(
    scene: Mapping[str, object], boundaries: tuple,
    control_values: Callable[[Mapping[str, object]], tuple[object, ...]],
) -> None:
    model = scene.get("model")
    if not isinstance(model, Mapping) or model.get("kind") != "piecewise":
        return
    control_id = model.get("input")
    segments = model.get("segments")
    controls = scene.get("controls", [])
    control = next((item for item in controls if isinstance(item, Mapping) and item.get("id") == control_id), None)
    if not isinstance(control_id, str) or not isinstance(segments, (tuple, list)) or not segments or control is None:
        raise AuditError("invalid_author_record")
    values = tuple(_decimal_value(value) for value in control_values(control))
    thresholds: list[Decimal] = []
    for index, segment in enumerate(segments):
        if not isinstance(segment, Mapping) or "min" not in segment or (index == len(segments) - 1 and "max" not in segment):
            raise AuditError("invalid_author_record")
        thresholds.append(_decimal_value(segment["min"]))
    thresholds.append(_decimal_value(segments[-1]["max"]))
    actual: dict[Decimal, set[str]] = {}
    for entry in boundaries:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise AuditError("invalid_author_record")
        key = entry[0]
        if not isinstance(key, (tuple, list)) or len(key) != 3:
            raise AuditError("invalid_author_record")
        if key[0] == control_id:
            actual.setdefault(_decimal_value(key[1]), set()).add(key[2])
    for threshold in dict.fromkeys(thresholds):
        required = {
            side for side, present in (
                ("below", any(value < threshold for value in values)),
                ("exact", threshold in values),
                ("above", any(value > threshold for value in values)),
            ) if present
        }
        if not required <= actual.get(threshold, set()):
            raise AuditError("missing_witness")

def validate_descriptor_witnesses(
    descriptor_names: set[str], witnesses: Mapping[str, object],
    classifications: Mapping[str, object], boundaries: tuple,
) -> None:
    expected = {"decision:" + name for name in witnesses}
    expected.update("classification:" + name for name in classifications)
    for entry in boundaries:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2:
            raise AuditError("invalid_author_record")
        key = entry[0]
        if not isinstance(key, (tuple, list)) or len(key) != 3:
            raise AuditError("invalid_author_record")
        expected.add(f"boundary:{key[0]}:{decimal_text(_decimal_value(key[1]))}:{key[2]}")
    declared = {
        name for name in descriptor_names
        if name.startswith(("decision:", "classification:", "boundary:"))
    }
    if declared != expected:
        raise AuditError("missing_witness")

def build_slide_ledger(
    scene: Mapping[str, object], record: object, audit: object, accepted: int, ordinal: int,
    targets: Mapping[str, object], steps: tuple | list,
    control_values: Callable[[Mapping[str, object]], tuple[object, ...]],
) -> dict:
    controls: list[dict] = []
    for control in scene.get("controls", []):
        item = {"id": control["id"], "kind": control["kind"], "acceptedValues": list(control_values(control))}
        for key in ("min", "max", "step", "quantity"):
            if key in control:
                item[key] = canonical(control[key])
        controls.append(item)
    witnesses = getattr(audit, "witnesses", {})
    classifications = getattr(audit, "classifications", {})
    return {
        "slideId": scene["slideId"],
        "ordinal": ordinal,
        "sceneType": scene.get("type"),
        "acceptedStateCount": accepted,
        "controls": controls,
        "quantities": canonical(scene.get("quantities", {})),
        "outputs": canonical(scene.get("outputDefinitions", {})),
        "decisionWitnesses": {name: _witness_dict(witness) for name, witness in witnesses.items()},
        "missingOutcomes": canonical(getattr(audit, "missing_outcomes", ())),
        "classificationWitnesses": {
            name: {str(key): canonical(value) for key, value in state}
            for name, state in classifications.items()
        },
        "boundaryWitnesses": _boundary_records(getattr(audit, "boundaries", ())),
        "lineage": canonical(scene.get("evidence", {}).get("leaves", [])),
        "fallback": canonical(getattr(record, "fallback_check", scene.get("fallback", {}))),
        "targetKeys": list(targets),
        "stepKeys": [step["stepKey"] for step in steps],
    }

def build_ledger(
    *, title: str, lang: str, slide_count: int, accepted_total: int,
    slides: list[dict], states: list[dict], targets: list[dict], steps: list[dict],
) -> dict:
    return {
        "schemaVersion": "interactive-audit-v1",
        "deck": {"title": title, "lang": lang, "slideCount": slide_count},
        "browserContract": {
            "engine": "chromium",
            "viewport": {"width": 1280, "height": 720},
            "screenshot": {"fullPage": False, "format": "png"},
        },
        "proof": {
            "acceptedStateCount": accepted_total,
            "selectedScreenshotCount": len(states),
            "mathematicalEnumeration": "complete",
            "browserWitnessSelection": "canonical",
        },
        "slides": slides,
        "states": states,
        "targetCoverage": targets,
        "stepCoverage": steps,
    }

def _csp() -> str:
    return "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; object-src 'none'"

def _document_start(title: str, lang: object) -> str:
    if lang not in ("en", "ja"):
        raise AuditError("invalid_ledger")
    return (
        f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(_csp(), quote=False)}">'
        f'<title>{html.escape(title)}</title><style>'
        'body{margin:0;background:#f3f5f7;color:#182b49;font-family:Arial,sans-serif}'
        'main{max-width:1440px;margin:auto;padding:32px}h1{font-size:28px;margin:0 0 8px}'
        '.meta{color:#5d6b7c;margin:0 0 24px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}'
        'article{background:#fff;border:1px solid #d8dee6;padding:16px}img{display:block;width:100%;height:auto;background:#fff}'
        'h2{font-size:17px;margin:12px 0 6px}.tags{font-size:13px;color:#44546a;overflow-wrap:anywhere}'
        '</style></head><body><main>'
    )

def _render_cards(ledger: Mapping[str, object], *, detailed: bool) -> str:
    parts = ['<div class="grid">']
    for state in ledger.get("states", []):
        if not isinstance(state, Mapping):
            raise AuditError("invalid_ledger")
        key = html.escape(str(state["stateKey"]))
        image = html.escape(str(state["screenshot"]), quote=True)
        obligations = ", ".join(str(item) for item in state.get("obligations", []))
        parts.append(f'<article id="{key}"><img src="{image}" alt="Audit state {key}">')
        parts.append(f'<h2>{html.escape(str(state["slideId"]))} · {key}</h2>')
        parts.append(f'<p class="tags">{html.escape(obligations)}</p>')
        if detailed:
            parts.append(f'<p class="tags">{html.escape(str(state["fragment"]))}</p>')
        parts.append('</article>')
    parts.append('</div>')
    return ''.join(parts)

def render_state_atlas(ledger: Mapping[str, object]) -> str:
    deck = ledger.get("deck", {})
    title = str(deck.get("title", "Interactive deck"))
    lang = deck.get("lang")
    count = len(ledger.get("states", []))
    return (
        _document_start(title + " — state atlas", lang)
        + f'<h1>{html.escape(title)} — state atlas</h1><p class="meta">{count} canonical browser witnesses</p>'
        + _render_cards(ledger, detailed=True)
        + '</main></body></html>\n'
    )

def render_contact_sheet(ledger: Mapping[str, object]) -> str:
    deck = ledger.get("deck", {})
    title = str(deck.get("title", "Interactive deck"))
    lang = deck.get("lang")
    count = len(ledger.get("states", []))
    return (
        _document_start(title + " — contact sheet", lang)
        + f'<h1>{html.escape(title)} — contact sheet</h1><p class="meta">{count} deterministic screenshots</p>'
        + _render_cards(ledger, detailed=False)
        + '</main></body></html>\n'
    )

def attach_reconstruction(ledger: Mapping[str, object], state_key_value: str, observed: Mapping[str, object]) -> dict:
    required = frozenset((
        "sanitizedSnapshot", "authorProbe", "semanticDigest", "pngSha256", "runtimeReady",
        "networkRequests", "consoleErrors", "targetHitBoxes", "staticParity",
    ))
    if not isinstance(observed, Mapping) or set(observed) != required:
        raise AuditError("invalid_reconstruction")
    if observed.get("runtimeReady") is not True:
        raise AuditError("runtime_not_ready")
    if observed.get("staticParity") is not True:
        raise AuditError("static_parity")
    if observed.get("networkRequests") != []:
        raise AuditError("browser_network")
    if observed.get("consoleErrors") != []:
        raise AuditError("browser_console")
    for field in ("semanticDigest", "pngSha256"):
        if not isinstance(observed.get(field), str) or not _DIGEST.fullmatch(observed[field]):
            raise AuditError("invalid_reconstruction")
    probe = observed.get("authorProbe")
    probe_fields = frozenset((
        "categoricalInputs", "panel", "evidenceMode", "overlay",
        "overviewOpen", "failed",
    ))
    if not isinstance(probe, Mapping) or set(probe) != probe_fields:
        raise AuditError("invalid_reconstruction")
    categorical = probe.get("categoricalInputs")
    if not isinstance(categorical, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in categorical.items()
    ):
        raise AuditError("invalid_reconstruction")
    if probe.get("panel") is not None and not isinstance(probe.get("panel"), str):
        raise AuditError("invalid_reconstruction")
    if probe.get("evidenceMode") not in (None, "closed", "sources", "assumptions", "both"):
        raise AuditError("invalid_reconstruction")
    overlay = probe.get("overlay")
    if overlay is not None and (
        not isinstance(overlay, Mapping)
        or set(overlay) != {"kind", "ordinal", "tab"}
        or overlay.get("kind") != "evidence"
        or isinstance(overlay.get("ordinal"), bool)
        or not isinstance(overlay.get("ordinal"), int)
        or overlay.get("ordinal") < 1
        or overlay.get("tab") not in ("sources", "assumptions")
    ):
        raise AuditError("invalid_reconstruction")
    if not isinstance(probe.get("overviewOpen"), bool) or probe.get("failed") not in (None, "unavailable"):
        raise AuditError("invalid_reconstruction")
    result = copy.deepcopy(canonical(ledger))
    matches = [state for state in result.get("states", []) if state.get("stateKey") == state_key_value]
    if len(matches) != 1 or "reconstruction" in matches[0]:
        raise AuditError("invalid_reconstruction")
    matches[0]["reconstruction"] = copy.deepcopy(canonical(observed))
    return result

def _reject_lexical_escape(path: Path) -> None:
    if ".." in path.parts or path.name in ("", ".", ".."):
        raise AuditError("unsafe_output")

def _reject_symlink_components(path: Path) -> None:
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        if not component.is_symlink():
            continue
        # macOS /var and /tmp are root-owned top-level compatibility links.
        # They are outside the author-controlled destination path.
        root = Path(component.anchor)
        if component.parent == root and component.lstat().st_uid == 0:
            continue
        raise AuditError("unsafe_output")

def _validate_existing_tree(path: Path, *, require_complete: bool = False) -> None:
    if not path.exists():
        return
    if path.is_symlink() or not path.is_dir():
        raise AuditError("unsafe_output")
    names = {entry.name for entry in path.iterdir()}
    if names - _ALLOWED_OUTPUTS or (require_complete and names != _ALLOWED_OUTPUTS):
        raise AuditError("unsafe_output")
    for entry in path.iterdir():
        if entry.is_symlink():
            raise AuditError("unsafe_output")
        if entry.name == "screenshots":
            if not entry.is_dir():
                raise AuditError("unsafe_output")
            for screenshot in entry.iterdir():
                if screenshot.is_symlink() or not screenshot.is_file() or screenshot.suffix != ".png":
                    raise AuditError("unsafe_output")
        elif not entry.is_file():
            raise AuditError("unsafe_output")

def validate_audit_destination(path: Path) -> Path:
    path = Path(path)
    _reject_lexical_escape(path)
    _reject_symlink_components(path)
    parent = path.absolute().parent
    if not parent.exists() or parent.is_symlink() or not parent.is_dir():
        raise AuditError("unsafe_output")
    _validate_existing_tree(path)
    return path.absolute()

def publish_audit_directory(staging: Path, destination: Path) -> None:
    staging = Path(staging).absolute()
    destination = validate_audit_destination(Path(destination))
    _reject_symlink_components(staging)
    if staging.parent != destination.parent or staging == destination:
        raise AuditError("unsafe_output")
    _validate_existing_tree(staging, require_complete=True)
    backup = destination.parent / f".{destination.name}.previous"
    if backup.exists() or backup.is_symlink():
        raise AuditError("unsafe_output")
    moved_old = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            moved_old = True
        os.replace(staging, destination)
    except OSError as error:
        if moved_old and backup.exists() and not destination.exists():
            try:
                os.replace(backup, destination)
            except OSError:
                pass
        raise AuditError("publish_failed") from error
    if moved_old:
        shutil.rmtree(backup)
