"""Public scene compiler facade and orchestration."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from dataclasses import replace

if __package__:
    from .interactive_contract import (BASIS_ORDER, ControlDomain, Location, SceneValidationError, TextValue, audit_contract, canonical_decimal, closed, compile_provenance, compile_quantities, evaluate_decision, fail, format_value, identifier, parse_decimal, validate_interactive_slide_ids)
    from ._interactive_models import (ModelProgram, _Compiler, _formula_text, _state_controls, compile_model, evaluate_model)
    from ._interactive_narration import (_NarrationValidator, render_narration)
    from ._interactive_views import (_compile_decision, _compile_view, _invariant_view, resolve_view)
    from ._interactive_shape import (COMMON, LocatedDocument, ValidatedScene, array, load_scene, validate_scene_shape)
    from ._interactive_registry import (compile_registries, safe_source_url)
    from ._interactive_fallback import (project_fallback, validate_fallback)
    from ._interactive_serialization import (serialize_compiled_scene)
else:
    from interactive_contract import (BASIS_ORDER, ControlDomain, Location, SceneValidationError, TextValue, audit_contract, canonical_decimal, closed, compile_provenance, compile_quantities, evaluate_decision, fail, format_value, identifier, parse_decimal, validate_interactive_slide_ids)
    from _interactive_models import (ModelProgram, _Compiler, _formula_text, _state_controls, compile_model, evaluate_model)
    from _interactive_narration import (_NarrationValidator, render_narration)
    from _interactive_views import (_compile_decision, _compile_view, _invariant_view, resolve_view)
    from _interactive_shape import (COMMON, LocatedDocument, ValidatedScene, array, load_scene, validate_scene_shape)
    from _interactive_registry import (compile_registries, safe_source_url)
    from _interactive_fallback import (project_fallback, validate_fallback)
    from _interactive_serialization import (serialize_compiled_scene)


@dataclass(frozen=True)
class CompileResult:
    compiled: dict
    audit: object
    source_locations: dict
    fallback_check: dict
    audit_states: tuple
    audit_evaluations: dict


def compile_scene(document, *, fallback_spec, fallback_path, slide_id, slide_ids, lang):
    identifier(slide_id, document.location.child('slideId'))
    validate_interactive_slide_ids(slide_ids)
    if lang not in ('en', 'ja'):
        fail(document.location, 'shape', 'en or ja locale', lang)
    scene = validate_scene_shape(document)
    raw, loc = scene.data, scene.location
    quantities = compile_quantities(raw.get('quantities', {}), loc.child('quantities'))
    program = compile_model(scene, quantities, raw)
    c = _Compiler(scene, quantities, raw)
    c.controls, c.definitions = dict(program.controls), dict(program.definitions)
    c.leaves, c.locations = list(program.leaves), dict(program.locations)
    decision = _compile_decision(c, raw['decisionContract'], loc.child('decisionContract')) if 'decisionContract' in raw else None
    reporting = raw.get('reporting')
    if reporting:
        closed(reporting, ('primaryOutput',), ('secondaryOutputs',), loc.child('reporting'))
        secondary = array(reporting.get('secondaryOutputs', []), 0, 2, loc.child('reporting').child('secondaryOutputs'))
        outputs = [reporting['primaryOutput']] + secondary
        if any(not isinstance(id, str) or id not in c.definitions or c.definitions[id].kind != 'numeric' for id in outputs) or len(set(outputs)) != len(outputs):
            fail(loc.child('reporting'), 'reference', 'unique numeric primary and secondary outputs')
        reporting = {'primaryOutput': reporting['primaryOutput'], 'secondaryOutputs': list(secondary)}
    views, states = {}, []
    if 'view' in raw:
        views['default'] = _compile_view(c, raw['view'], loc.child('view'))
    for i, state in enumerate(raw.get('states', [])):
        here = loc.child('states').child(i)
        lineage = compile_provenance(state['provenance'], raw, here.child('provenance'))
        view = _compile_view(c, state['view'], here.child('view'))
        if views and _invariant_view(view) != _invariant_view(next(iter(views.values()))):
            fail(here.child('view'), 'view_domain', 'same component, labels, IDs, axes, quantities and domains across states')
        views[state['id']] = view
        states.append({'id': state['id'], 'lineage': lineage, 'view': view})
    def evaluate(state, check_bounds=True):
        outputs = evaluate_model(program, state)
        controls = _state_controls(program, state) if scene.domains else {}
        result = {'outputs': outputs, 'controls': controls}
        if decision:
            d = evaluate_decision(decision, outputs, controls)
            result['decision'] = d
            outputs['decisionStatus'], outputs['recommendation'] = TextValue(d.status, d.lineage), TextValue(d.recommendation, d.lineage)
        if views:
            key = dict(program.instructions['entries'])[state[program.instructions['input']]] if program.kind == 'state_map' else 'default'
            result['view'] = resolve_view(views[key], controls, outputs, quantities, location=loc, check_bounds=check_bounds)
            collection = 'points' if result['view']['component'] == 'dot_plot' else 'items'
            for authored, resolved in zip(views[key].get(collection, ()), result['view'].get(collection, ())):
                for name in ('value', 'metric', 'x', 'y'):
                    if name in resolved:
                        slot, value = authored[name], resolved[name]
                        precision = max(0, -value.value.as_tuple().exponent)
                        if isinstance(slot, dict) and slot['ref'].startswith('output:'):
                            precision = c.definitions[slot['ref'].split(':')[1]].round
                        resolved[name + 'Text'] = format_value(value.value, quantities[value.quantity], precision, lang)
        else:
            result['view'] = None
        return result
    try:
        initial = evaluate(raw['initialState'], check_bounds=False)
    except SceneValidationError:
        # Replay in canonical order to report the first counterexample, even
        # when the authored initial state is not the first accepted state.
        audit_contract(scene.domains, evaluate, decision)
        raise
    if states:
        input_id = program.instructions['input']
        state_for_view = {state_id: input_value for input_value, state_id in program.instructions['entries']}
        for state_record in states:
            state_record['view'] = evaluate(
                {input_id: state_for_view[state_record['id']]},
                check_bounds=False,
            )['view']
        selected_state_id = dict(program.instructions['entries'])[raw['initialState'][input_id]]
        initial['view'] = next(
            state_record['view'] for state_record in states
            if state_record['id'] == selected_state_id
        )
    narration = _NarrationValidator(scene, initial, c.definitions, quantities, reporting)
    def visitor(state):
        evaluation = evaluate(state)
        narration.visit(state, evaluation)
        return evaluation
    boundaries = tuple((program.instructions['input'], segment['min'].value) for segment in program.instructions.get('segments', ()))
    if program.kind == 'piecewise':
        boundaries += ((program.instructions['input'], program.instructions['segments'][-1]['max'].value),)
    elif program.kind == 'score_sum':
        boundaries = tuple(('output:score', band['min'].value) for band in program.instructions['bands']) + (('output:score', program.instructions['bands'][-1]['max'].value),)
    disclosure_states = []
    if scene.domains:
        audit = audit_contract(scene.domains, visitor, decision, boundaries)
    else:
        if raw['type'] == 'evidence_only':
            modes = ['closed'] + (['sources'] if raw.get('sources') else []) + (['assumptions'] if raw.get('assumptions') else []) + (['both'] if raw.get('sources') and raw.get('assumptions') else [])
            domain = ControlDomain('evidence', tuple(modes))
        else:
            modes = [panel['id'] for panel in raw.get('panels', raw.get('items', []))]
            if raw['type'] == 'drilldown' or raw.get('allowNone'):
                modes = [None] + modes
            domain = ControlDomain('panel', tuple(modes))
        audit = audit_contract((domain,), lambda _: initial)
        disclosure_states = [{'name': domain.id + ':' + (str(value) if value is not None else 'closed'), 'state': {domain.id: value}} for value in modes]
    targets, steps = compile_registries(scene, slide_ids)
    component = initial['view']['component'] if initial['view'] else None
    invariants = {'quantities': quantities, 'definitions': c.definitions, 'reporting': reporting, 'decision': decision, 'fallbackSummary': raw.get('fallbackSummary'),
                  'program': program, 'rawScene': raw, 'resolvedStates': states}
    try:
        projection = replace(project_fallback(fallback_spec, raw['type'], component, lang), location=Location(str(fallback_path)))
        fallback_check = validate_fallback(initial, projection, invariants)
    except SceneValidationError as error:
        raise SceneValidationError(Location(str(fallback_path), error.location.pointer), error.code, error.expected, error.actual_summary, related_locations=(loc.child('printState'),)) from error
    chrome = {k: copy.deepcopy(fallback_spec[k]) for k in ('headline', 'subline', 'source', 'footnotes', 'eyebrow', 'section', 'page_number', 'classification', 'lang', 'theme', 'palette') if k in fallback_spec}
    evidence = {'sources': copy.deepcopy(raw.get('sources', [])), 'assumptions': copy.deepcopy(raw.get('assumptions', [])), 'leaves': tuple(c.leaves)}
    bases = {leaf['basis'] for leaf in c.leaves} | {basis for state in states for basis in state['lineage'].bases}
    evidence['badge'] = next((basis for basis in BASIS_ORDER if basis in bases), '')
    evidence['formulas'] = _formula_text(program, raw.get('controls', []))
    evidence['triggerLabel'] = raw.get('triggerLabel', '根拠を表示' if lang == 'ja' else 'Open evidence')
    for source in evidence['sources']:
        source['linked'] = safe_source_url(source.get('url'))
    compiled = {'version': 1, 'slideId': slide_id, 'type': raw['type'], 'locale': lang, 'scale': scene.scale, 'purpose': raw['purpose'], 'decisionJob': raw['decisionJob'], 'interactionRationale': raw['interactionRationale'], 'initialState': raw['initialState'], 'printState': raw['printState'], 'controls': copy.deepcopy(raw.get('controls', [])), 'quantities': quantities, 'outputDefinitions': c.definitions, 'evidence': evidence, 'invariants': chrome, 'fallback': fallback_check, 'targets': targets, 'steps': steps, 'narration': narration.result(lang), 'initialEvaluation': {k: v for k, v in initial.items() if k != 'controls'}}
    for control in compiled['controls']:
        if control['kind'] == 'range':
            for key in ('min', 'max', 'step'):
                control[key] = parse_decimal(control[key], loc)
            control.pop('provenance')
            control['lineage'] = program.controls[control['id']].lineage
    if program.kind != 'none':
        compiled['model'] = {'kind': program.kind, **program.instructions}
    if reporting: compiled['reporting'] = reporting
    if decision: compiled['decisionContract'] = decision
    if 'default' in views: compiled['view'] = views['default']
    if states: compiled['states'] = tuple(states)
    if raw['type'] in ('drilldown', 'accordion'):
        # Type-specific semantic panels live in the states member of the closed audience envelope.
        panels = copy.deepcopy(raw.get('panels', raw.get('items')))
        for panel in panels:
            panel.setdefault('sourceRefs', [])
        compiled['states'] = {'panels': panels, **{k: raw[k] for k in ('allowNone', 'parentSummary', 'returnLabel') if k in raw}}
    descriptors = [{'name': 'initial', 'state': raw['initialState']}, {'name': 'print', 'state': raw['printState']}] + disclosure_states
    for domain in scene.domains:
        if domain.minimum is not None:
            for key, value in [('min', domain.minimum), ('max', domain.maximum)]:
                descriptors.append({'name': 'range:' + domain.id + ':' + key, 'state': {**raw['initialState'], domain.id: value}})
        else:
            for value in domain.values:
                descriptors.append({'name': 'option:' + domain.id + ':' + value, 'state': {**raw['initialState'], domain.id: value}})
    for name, witness in audit.witnesses.items():
        descriptors.append({'name': 'decision:' + name, 'state': dict(witness.state)})
    for name, state in audit.classifications.items():
        descriptors.append({'name': 'classification:' + name, 'state': dict(state)})
    for (control, value, side), state in audit.boundaries:
        descriptors.append({'name': 'boundary:' + control + ':' + canonical_decimal(value) + ':' + side, 'state': dict(state)})
    demo_state = copy.deepcopy(raw['initialState'])
    for step in steps:
        action = step['action']
        action_type = action['type']
        descriptor = {'name': 'step:' + step['stepKey']}
        if action_type in ('set', 'select'):
            demo_state[action['control']] = action['value']
            descriptor['state'] = copy.deepcopy(demo_state)
        elif action_type == 'openPanel':
            demo_state['panel'] = action['panel']
            descriptor['state'] = copy.deepcopy(demo_state)
        elif action_type == 'closePanel':
            descriptor['setup'] = [
                {'action': 'openPanel', 'panel': action['panel']},
                {'action': 'closePanel', 'panel': action['panel']},
            ]
            demo_state['panel'] = None
            descriptor['state'] = copy.deepcopy(demo_state)
        elif action_type == 'openEvidence':
            descriptor['state'] = copy.deepcopy(demo_state)
            descriptor['setup'] = [{'action': 'openEvidence'}]
        elif action_type == 'closeEvidence':
            descriptor['state'] = copy.deepcopy(demo_state)
            descriptor['setup'] = [{'action': 'openEvidence'}, {'action': 'closeEvidence'}]
        descriptors.append(descriptor)
    for key in targets:
        descriptors.append({'name': 'target:' + key, 'targetKey': key})
    for mode in ('static', 'reduced-motion', 'overview-after-change'):
        descriptors.append({'name': mode, 'state': raw['printState']})
    def expected_for_state(state):
        evaluated = serialize_compiled_scene(evaluate(state))
        inputs = {}
        for key, value in state.items():
            if value is None:
                inputs[key] = None
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                inputs[key] = canonical_decimal(parse_decimal(value, loc))
            elif hasattr(value, 'as_tuple'):
                inputs[key] = canonical_decimal(value)
            else:
                inputs[key] = str(value)
        outputs = {}
        for output_id, definition in c.definitions.items():
            output = evaluated.get('outputs', {}).get(output_id)
            if definition.kind == 'numeric' and isinstance(output, dict) and 'value' in output:
                outputs[output_id] = output['value']
        decision_result = evaluated.get('decision')
        return {
            'inputs': inputs,
            'outputs': outputs,
            'outcome': decision_result.get('outcome') if isinstance(decision_result, dict) else None,
            'viewMode': 'live',
        }
    audit_evaluations = {
        descriptor['name']: expected_for_state(descriptor['state'])
        for descriptor in descriptors if 'state' in descriptor
    }
    return CompileResult(compiled, audit, c.locations, fallback_check, tuple(descriptors), audit_evaluations)
