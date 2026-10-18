"""Pure author-only planning for the interactive-deck audit."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping
from urllib.parse import quote, urlencode

try:
    from . import _interactive_audit_output as _output
except ImportError:  # Direct script execution.
    import _interactive_audit_output as _output

AuditError = _output.AuditError
attach_reconstruction = _output.attach_reconstruction
ledger_bytes = _output.ledger_bytes
publish_audit_directory = _output.publish_audit_directory
render_contact_sheet = _output.render_contact_sheet
render_state_atlas = _output.render_state_atlas
validate_audit_destination = _output.validate_audit_destination
_build_ledger = _output.build_ledger
_build_slide_ledger = _output.build_slide_ledger
_canonical = _output.canonical
_decimal_text = _output.decimal_text
_expected_author_probe = _output.expected_author_probe
_state_identity = _output.state_identity
_stable_state_key = _output.state_key
MAX_AUDIT_SCREENSHOTS = 512
_SETUP_FIELDS = {
    "emulateReducedMotion": frozenset(("action",)),
    "openOverview": frozenset(("action",)),
    "openEvidence": frozenset(("action",)),
    "closeEvidence": frozenset(("action",)),
    "selectEvidenceTab": frozenset(("action", "tab")),
    "openPanel": frozenset(("action", "panel")),
    "closePanel": frozenset(("action", "panel")),
    "assertTarget": frozenset(("action", "targetKey")),
}
@dataclass(frozen=True)
class AuditPlan:
    ledger: dict
    state_order: dict[str, int]
def preflight_screenshot_budget(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= MAX_AUDIT_SCREENSHOTS:
        raise AuditError("audit_limit")
def _state_key(ordinal: int, slide_id: str, identity: bytes) -> str:
    return _stable_state_key(ordinal, slide_id, identity)
def _control_values(control: Mapping[str, object]) -> tuple[object, ...]:
    kind = control.get("kind")
    if kind == "range":
        try:
            minimum = Decimal(str(control["min"]))
            maximum = Decimal(str(control["max"]))
            step = Decimal(str(control["step"]))
        except (KeyError, InvalidOperation, ValueError):
            raise AuditError("invalid_author_record")
        if not minimum < maximum or step <= 0:
            raise AuditError("invalid_author_record")
        count = (maximum - minimum) / step
        if count != count.to_integral_value() or count > 10_000:
            raise AuditError("invalid_author_record")
        return tuple(_decimal_text(minimum + step * index) for index in range(int(count) + 1))
    options = control.get("options")
    if kind not in ("segmented", "toggle", "select") or not isinstance(options, list):
        raise AuditError("invalid_author_record")
    values = tuple(option.get("value") for option in options if isinstance(option, Mapping))
    if len(values) != len(options) or any(not isinstance(value, str) for value in values):
        raise AuditError("invalid_author_record")
    return values
def _normalize_state(scene: Mapping[str, object], raw_state: object) -> dict[str, object]:
    if not isinstance(raw_state, Mapping):
        raise AuditError("unreconstructable_state")
    state = {str(key): _canonical(value) for key, value in raw_state.items()}
    controls = scene.get("controls", [])
    if not isinstance(controls, list):
        raise AuditError("invalid_author_record")
    allowed = {str(control.get("id")) for control in controls if isinstance(control, Mapping)}
    scene_type = scene.get("type")
    if scene_type == "evidence_only":
        allowed.add("evidence")
    if scene_type in ("drilldown", "accordion"):
        allowed.add("panel")
    if set(state) - allowed:
        raise AuditError("unreconstructable_state")
    for control in controls:
        if not isinstance(control, Mapping) or not isinstance(control.get("id"), str):
            raise AuditError("invalid_author_record")
        control_id = control["id"]
        if control_id not in state or state[control_id] not in _control_values(control):
            raise AuditError("unreconstructable_state")
    if scene_type == "evidence_only" and state.get("evidence") not in ("closed", "sources", "assumptions", "both"):
        raise AuditError("unreconstructable_state")
    if scene_type in ("drilldown", "accordion"):
        states = scene.get("states")
        panels = states.get("panels", []) if isinstance(states, Mapping) else []
        panel_ids = {panel.get("id") for panel in panels if isinstance(panel, Mapping)}
        if state.get("panel") is not None and state.get("panel") not in panel_ids:
            raise AuditError("unreconstructable_state")
    return state
def _fragment(ordinal: int, scene: Mapping[str, object], state: Mapping[str, object], *, mode: str) -> str:
    fields: list[tuple[str, str]] = [("slide", str(ordinal))]
    for control in scene.get("controls", []):
        control_id = control["id"]
        value = state[control_id]
        fields.append((control_id, str(value)))
    if scene.get("type") == "evidence_only":
        fields.append(("evidence", str(state["evidence"])))
    if scene.get("type") in ("drilldown", "accordion") and state.get("panel") is not None:
        fields.append(("panel", str(state["panel"])))
    if mode == "static":
        fields.append(("mode", "static"))
    return "#" + urlencode(fields, quote_via=quote, safe="-_.~")
def _normalize_expected(scene: Mapping[str, object], state: Mapping[str, object], descriptor: Mapping[str, object] | None) -> dict:
    if descriptor is not None and isinstance(descriptor.get("expected"), Mapping):
        expected = copy.deepcopy(_canonical(descriptor["expected"]))
    else:
        evaluation = descriptor.get("evaluation") if descriptor is not None else None
        if not isinstance(evaluation, Mapping):
            evaluation = scene.get("initialEvaluation")
        if not isinstance(evaluation, Mapping):
            raise AuditError("missing_expected_evaluation")
        outputs: dict[str, object] = {}
        definitions = scene.get("outputDefinitions", {})
        raw_outputs = evaluation.get("outputs", {})
        if not isinstance(definitions, Mapping) or not isinstance(raw_outputs, Mapping):
            raise AuditError("missing_expected_evaluation")
        for output_id, definition in definitions.items():
            if not isinstance(definition, Mapping) or definition.get("kind") != "numeric":
                continue
            output = raw_outputs.get(output_id)
            if isinstance(output, Mapping) and "value" in output:
                outputs[output_id] = _canonical(output["value"])
        decision = evaluation.get("decision")
        expected = {
            "inputs": {key: (None if value is None else str(value)) for key, value in state.items()},
            "outputs": outputs,
            "outcome": decision.get("outcome") if isinstance(decision, Mapping) else None,
            "viewMode": "live",
        }
    required = frozenset(("inputs", "outputs", "outcome", "viewMode"))
    if not isinstance(expected, Mapping) or not required <= set(expected):
        raise AuditError("missing_expected_evaluation")
    return dict(expected)

def _validate_setup(scene: Mapping[str, object], setup: object) -> list[dict]:
    if not isinstance(setup, list):
        raise AuditError("unreconstructable_setup")
    targets = scene.get("targets", {})
    panels = scene.get("states", {}).get("panels", []) if isinstance(scene.get("states"), Mapping) else []
    panel_ids = {panel.get("id") for panel in panels if isinstance(panel, Mapping)}
    normalized: list[dict] = []
    for step in setup:
        if not isinstance(step, Mapping) or not isinstance(step.get("action"), str):
            raise AuditError("unreconstructable_setup")
        action = step["action"]
        if action not in _SETUP_FIELDS or set(step) != _SETUP_FIELDS[action]:
            raise AuditError("unreconstructable_setup")
        clean = dict(_canonical(step))
        if action == "selectEvidenceTab" and clean.get("tab") not in ("sources", "assumptions"):
            raise AuditError("unreconstructable_setup")
        if action in ("openPanel", "closePanel") and clean.get("panel") not in panel_ids:
            raise AuditError("unreconstructable_setup")
        if action == "assertTarget":
            target = clean.get("targetKey")
            if not isinstance(target, str) or not isinstance(targets, Mapping) or target not in targets:
                raise AuditError("unreconstructable_setup")
        normalized.append(clean)
    return normalized

def _descriptor_setup(name: str, state: Mapping[str, object]) -> list[dict]:
    if "evidence" in state and name.startswith("evidence:"):
        return []
    if name == "evidence:sources":
        return [{"action": "openEvidence"}, {"action": "selectEvidenceTab", "tab": "sources"}]
    if name == "evidence:assumptions":
        return [{"action": "openEvidence"}, {"action": "selectEvidenceTab", "tab": "assumptions"}]
    if name == "evidence:both":
        return [{"action": "openEvidence"}]
    return []

def _audit_descriptors(record: object) -> list[dict]:
    descriptors = getattr(record, "audit_states", None)
    if not isinstance(descriptors, (tuple, list)):
        raise AuditError("invalid_author_record")
    evaluations = getattr(record, "audit_evaluations", {})
    if not isinstance(evaluations, Mapping):
        raise AuditError("invalid_author_record")
    result: list[dict] = []
    for descriptor in descriptors:
        if not isinstance(descriptor, Mapping) or not isinstance(descriptor.get("name"), str):
            raise AuditError("invalid_author_record")
        copied = dict(descriptor)
        if copied["name"] in evaluations:
            copied["expected"] = copy.deepcopy(evaluations[copied["name"]])
        result.append(copied)
    return result

def _band_labels(scene: Mapping[str, object]) -> tuple[str, ...]:
    model = scene.get("model")
    if not isinstance(model, Mapping) or model.get("kind") != "score_sum":
        return ()
    bands = model.get("bands", [])
    labels: list[str] = []
    for band in bands:
        if not isinstance(band, Mapping) or not isinstance(band.get("label"), str):
            raise AuditError("invalid_author_record")
        labels.append(band["label"])
    return tuple(labels)

def _required_targets(scene: Mapping[str, object]) -> set[str]:
    required = {"evidence:open", "evidence:close", "static:toggle"}
    for control in scene.get("controls", []):
        if not isinstance(control, Mapping) or not isinstance(control.get("id"), str):
            raise AuditError("invalid_author_record")
        required.add("control:" + control["id"])
    states = scene.get("states")
    if scene.get("type") in ("drilldown", "accordion"):
        panels = states.get("panels", []) if isinstance(states, Mapping) else []
        for panel in panels:
            if not isinstance(panel, Mapping) or not isinstance(panel.get("id"), str):
                raise AuditError("invalid_author_record")
            required.add("panel:" + panel["id"])
            required.add("panel:" + panel["id"] + ":close")
    evidence = scene.get("evidence")
    sources = evidence.get("sources", []) if isinstance(evidence, Mapping) else []
    for source in sources:
        if isinstance(source, Mapping) and source.get("linked") is True and isinstance(source.get("id"), str):
            required.add("source:" + source["id"])
    return required

def _target_state(scene: Mapping[str, object], target_key: str) -> tuple[dict, list[dict], str]:
    state = dict(_canonical(scene.get("initialState", {})))
    setup: list[dict] = []
    mode = "presence" if target_key.startswith("source:") else "hitbox"
    evidence_only = scene.get("type") == "evidence_only"
    evidence = scene.get("evidence", {})
    default_tab = "sources" if isinstance(evidence, Mapping) and evidence.get("sources") else "assumptions"
    if evidence_only and (target_key == "evidence:close" or target_key.startswith("source:")):
        state["evidence"] = default_tab
    elif target_key == "evidence:close":
        setup.append({"action": "openEvidence"})
    elif target_key.startswith("source:"):
        setup.extend(({"action": "openEvidence"}, {"action": "selectEvidenceTab", "tab": "sources"}))
    elif target_key.startswith("panel:") and target_key.endswith(":close"):
        panel_id = target_key.split(":", 2)[1]
        state["panel"] = panel_id
    setup.append({"action": "assertTarget", "targetKey": target_key})
    return state, setup, mode

def _record_state(
    *,
    states: list[dict],
    by_identity: dict[bytes, dict],
    key_identities: dict[str, bytes],
    ordinal: int,
    scene: Mapping[str, object],
    descriptor: Mapping[str, object] | None,
    obligation: str,
    state: Mapping[str, object],
    mode: str = "live",
    setup: list[dict] | None = None,
) -> str:
    normalized_state = _normalize_state(scene, state)
    normalized_setup = _validate_setup(scene, list(setup or []))
    fragment = _fragment(ordinal, scene, normalized_state, mode=mode)
    identity = _state_identity(scene["slideId"], fragment, normalized_setup)
    existing = by_identity.get(identity)
    if existing is not None:
        if obligation not in existing["obligations"]:
            existing["obligations"].append(obligation)
        return existing["stateKey"]
    state_key = _state_key(ordinal, scene["slideId"], identity)
    prior_identity = key_identities.get(state_key)
    if prior_identity is not None and prior_identity != identity:
        raise AuditError("duplicate_state_key")
    expected = _normalize_expected(scene, normalized_state, descriptor)
    expected["viewMode"] = "static" if mode == "static" else expected.get("viewMode", "live")
    expected["authorProbe"] = _expected_author_probe(ordinal, scene, normalized_state, normalized_setup)
    if "panel" in expected["inputs"]:
        expected["inputs"]["panel"] = expected["authorProbe"]["panel"]
    if "evidence" in expected["inputs"]:
        expected["inputs"]["evidence"] = expected["authorProbe"]["evidenceMode"]
    record = {
        "stateKey": state_key,
        "slideId": scene["slideId"],
        "ordinal": ordinal,
        "fragment": fragment,
        "setup": normalized_setup,
        "obligations": [obligation],
        "expected": expected,
        "screenshot": f"screenshots/{state_key}.png",
    }
    states.append(record)
    by_identity[identity] = record
    key_identities[state_key] = identity
    return state_key

def compile_audit_plan(compiled_deck: object) -> AuditPlan:
    """Select canonical audit witnesses from one already-compiled deck."""
    title = getattr(compiled_deck, "title", None)
    lang = getattr(compiled_deck, "lang", None)
    slides = getattr(compiled_deck, "slides", None)
    author_records = getattr(compiled_deck, "author_records", None)
    if not isinstance(title, str) or lang not in ("en", "ja") or not isinstance(slides, tuple) or not isinstance(author_records, tuple):
        raise AuditError("invalid_author_record")
    record_by_slide: dict[str, object] = {}
    for record in author_records:
        scene = getattr(record, "compiled", None)
        slide_id = scene.get("slideId") if isinstance(scene, Mapping) else None
        if not isinstance(slide_id, str) or slide_id in record_by_slide:
            raise AuditError("invalid_author_record")
        record_by_slide[slide_id] = record
    states: list[dict] = []
    by_identity: dict[bytes, dict] = {}
    key_identities: dict[str, bytes] = {}
    slides_ledger: list[dict] = []
    target_coverage: list[dict] = []
    step_coverage: list[dict] = []
    accepted_total = 0
    for ordinal, slide in enumerate(slides, start=1):
        scene = getattr(slide, "scene", None)
        slide_id = getattr(slide, "slide_id", None)
        if not isinstance(slide_id, str):
            raise AuditError("invalid_author_record")
        if scene is None:
            slides_ledger.append({"slideId": slide_id, "ordinal": ordinal, "sceneType": "static"})
            continue
        if not isinstance(scene, Mapping) or scene.get("slideId") != slide_id:
            raise AuditError("invalid_author_record")
        record = record_by_slide.get(slide_id)
        if record is None:
            raise AuditError("invalid_author_record")
        audit = getattr(record, "audit", None)
        accepted = getattr(audit, "accepted_state_count", None)
        if isinstance(accepted, bool) or not isinstance(accepted, int) or accepted < 1:
            raise AuditError("invalid_author_record")
        accepted_total += accepted
        descriptors = _audit_descriptors(record)
        descriptor_by_name = {descriptor["name"]: descriptor for descriptor in descriptors}
        if len(descriptor_by_name) != len(descriptors):
            raise AuditError("duplicate_obligation")
        witnesses = getattr(audit, "witnesses", None)
        missing_outcomes = getattr(audit, "missing_outcomes", None)
        classifications = getattr(audit, "classifications", None)
        boundaries = getattr(audit, "boundaries", None)
        if not isinstance(witnesses, dict) or not isinstance(missing_outcomes, tuple) or not isinstance(classifications, dict) or not isinstance(boundaries, tuple):
            raise AuditError("invalid_author_record")
        _output.validate_boundary_coverage(scene, boundaries, _control_values)
        _output.validate_descriptor_witnesses(set(descriptor_by_name), witnesses, classifications, boundaries)
        fallback_check = getattr(record, "fallback_check", None)
        if not isinstance(fallback_check, Mapping) or fallback_check.get("matched") is not True:
            raise AuditError("static_parity")
        if "decisionContract" in scene:
            missing_names = {entry.get("outcome") for entry in missing_outcomes if isinstance(entry, Mapping)}
            for outcome in ("met", "notMet"):
                if outcome not in witnesses and outcome not in missing_names:
                    raise AuditError("missing_witness")
        for label in _band_labels(scene):
            if label not in classifications:
                raise AuditError("missing_witness")
        targets = scene.get("targets")
        if not isinstance(targets, Mapping):
            raise AuditError("invalid_author_record")
        required_targets = _required_targets(scene)
        if not required_targets <= set(targets):
            raise AuditError("uncovered_target")
        for target_key, target in targets.items():
            if not isinstance(target_key, str) or not isinstance(target, Mapping) or target.get("kind") not in ("evidence", "static", "control", "panel", "panelClose", "source"):
                raise AuditError("uncovered_target")

        initial = _normalize_state(scene, scene.get("initialState"))
        print_state = _normalize_state(scene, scene.get("printState"))
        for descriptor in descriptors:
            name = descriptor["name"]
            if "state" not in descriptor or name in ("static", "reduced-motion", "overview-after-change"):
                continue
            state = _normalize_state(scene, descriptor["state"])
            setup = _descriptor_setup(name, state)
            if "setup" in descriptor:
                if not isinstance(descriptor["setup"], list):
                    raise AuditError("unreconstructable_setup")
                setup.extend(descriptor["setup"])
            _record_state(
                states=states, by_identity=by_identity, key_identities=key_identities,
                ordinal=ordinal, scene=scene, descriptor=descriptor,
                obligation=name, state=state, setup=setup,
            )
        initial_descriptor = descriptor_by_name.get("initial")
        print_descriptor = descriptor_by_name.get("print") or initial_descriptor
        _record_state(
            states=states, by_identity=by_identity, key_identities=key_identities,
            ordinal=ordinal, scene=scene, descriptor=initial_descriptor,
            obligation="initial", state=initial,
        )
        _record_state(
            states=states, by_identity=by_identity, key_identities=key_identities,
            ordinal=ordinal, scene=scene, descriptor=print_descriptor,
            obligation="print", state=print_state,
        )
        _record_state(
            states=states, by_identity=by_identity, key_identities=key_identities,
            ordinal=ordinal, scene=scene, descriptor=print_descriptor,
            obligation="static", state=print_state, mode="static",
        )
        _record_state(
            states=states, by_identity=by_identity, key_identities=key_identities,
            ordinal=ordinal, scene=scene, descriptor=initial_descriptor,
            obligation="reduced-motion", state=initial,
            setup=[{"action": "emulateReducedMotion"}],
        )
        changed_descriptor = next(
            (descriptor for descriptor in descriptors if descriptor.get("state") is not None and _normalize_state(scene, descriptor["state"]) != initial),
            initial_descriptor,
        )
        changed_state = _normalize_state(scene, changed_descriptor["state"]) if changed_descriptor and "state" in changed_descriptor else initial
        changed_setup = _descriptor_setup(changed_descriptor["name"], changed_state) if changed_descriptor else []
        authored_setup = changed_descriptor.get("setup", []) if changed_descriptor else []
        if not isinstance(authored_setup, list):
            raise AuditError("unreconstructable_setup")
        changed_setup.extend(authored_setup)
        changed_setup.append({"action": "openOverview"})
        _record_state(
            states=states, by_identity=by_identity, key_identities=key_identities,
            ordinal=ordinal, scene=scene, descriptor=changed_descriptor,
            obligation="overview-after-change", state=changed_state,
            setup=changed_setup,
        )

        for target_key in targets:
            target_state, target_setup, coverage_mode = _target_state(scene, target_key)
            descriptor = next(
                (candidate for candidate in descriptors if candidate.get("state") is not None and _normalize_state(scene, candidate["state"]) == _normalize_state(scene, target_state)),
                initial_descriptor,
            )
            state_key = _record_state(
                states=states, by_identity=by_identity, key_identities=key_identities,
                ordinal=ordinal, scene=scene, descriptor=descriptor,
                obligation="target:" + target_key, state=target_state, setup=target_setup,
            )
            target_coverage.append({
                "slideId": slide_id,
                "ordinal": ordinal,
                "targetKey": target_key,
                "coverageMode": coverage_mode,
                "stateKey": state_key,
            })

        steps = scene.get("steps")
        if not isinstance(steps, (list, tuple)):
            raise AuditError("invalid_author_record")
        seen_steps: set[str] = set()
        for step in steps:
            if not isinstance(step, Mapping) or not isinstance(step.get("stepKey"), str) or not isinstance(step.get("action"), Mapping):
                raise AuditError("invalid_author_record")
            step_key = step["stepKey"]
            if step_key in seen_steps:
                raise AuditError("duplicate_step_key")
            seen_steps.add(step_key)
            action_type = step["action"].get("type")
            target_key = step.get("targetKey")
            if action_type in ("goto", "wait"):
                if target_key is not None:
                    raise AuditError("unreconstructable_setup")
            elif not isinstance(target_key, str) or target_key not in targets:
                raise AuditError("uncovered_target")
            state_key = None
            descriptor = descriptor_by_name.get("step:" + step_key)
            if descriptor is not None and "state" in descriptor:
                state_key = _record_state(
                    states=states, by_identity=by_identity, key_identities=key_identities,
                    ordinal=ordinal, scene=scene, descriptor=descriptor,
                    obligation="step:" + step_key, state=descriptor["state"],
                    setup=list(descriptor.get("setup", [])),
                )
            coverage = {
                "slideId": slide_id,
                "ordinal": ordinal,
                "stepKey": step_key,
                "action": action_type,
            }
            if target_key is not None:
                coverage["targetKey"] = target_key
            if state_key is not None:
                coverage["stateKey"] = state_key
            step_coverage.append(coverage)

        slides_ledger.append(_build_slide_ledger(
            scene, record, audit, accepted, ordinal, targets, steps, _control_values,
        ))

    if set(record_by_slide) != {getattr(slide, "slide_id", None) for slide in slides if getattr(slide, "scene", None) is not None}:
        raise AuditError("invalid_author_record")
    preflight_screenshot_budget(len(states))
    ledger = _build_ledger(
        title=title, lang=lang, slide_count=len(slides), accepted_total=accepted_total,
        slides=slides_ledger, states=states, targets=target_coverage, steps=step_coverage,
    )
    return AuditPlan(ledger=ledger, state_order={state["stateKey"]: index for index, state in enumerate(states)})
