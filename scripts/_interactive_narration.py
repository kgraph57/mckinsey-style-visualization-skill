"""Closed, bounded narration programs and their pure Python runtime oracle."""
from __future__ import annotations

from decimal import Decimal, localcontext
from types import SimpleNamespace

if __package__:
    from .interactive_contract import Location, NARRATION_TEXT, fail, fit_narration, format_value
else:
    from interactive_contract import Location, NARRATION_TEXT, fail, fit_narration, format_value


def _value(value):
    """Accept either compiler typed values or their canonical wire form."""
    return value['value'] if isinstance(value, dict) else value.value


def _format(value, atom, locale, delta=False):
    return format_value(value, SimpleNamespace(unit=atom['unit'], display=atom['display']),
                        atom['precision'], locale, delta=delta)


def _different(control, value):
    if control['kind'] == 'range':
        return Decimal(value) != Decimal(control['baseline'])
    return value != control['baseline']


def _control_text(control, state, locale):
    value = state[control['id']]
    if control['kind'] == 'range':
        with localcontext() as context:
            context.prec = 40
            difference = Decimal(value) - Decimal(control['baseline'])
        return control['label'] + ' ' + _format(difference, control, locale, delta=True)
    option = next(o['label'] for o in control['options'] if o['value'] == value)
    return control['label'] + ': ' + option


def _semantic_view(view):
    """Retain only compared truth, never provenance or derived display text."""
    key = 'points' if view['component'] == 'dot_plot' else 'items'
    items = []
    for item in view[key]:
        result = {k: item[k] for k in ('id', 'rank', 'emphasis', 'highlight', 'removed') if k in item}
        for slot in ('value', 'metric', 'x', 'y'):
            if slot in item:
                result[slot] = Decimal(_value(item[slot]))
        items.append(result)
    return items


def render_narration(narration, state, evaluation, *, event='direct', control=None,
                     location=Location()):
    """Render a compiler-owned program, without I/O, mutation or evaluation.

    Accepts in-memory or serialized evaluations. Events are initial/reset,
    direct (triggering control ID required for numeric programs), restore,
    and compiled evidence:/openPanel:/closePanel: message keys. Baselines,
    output priority, precision, transition order and labels are fixed atoms.
    All deltas compare to initialState; optional outputs drop last-first.
    The compiler invokes this exact function for both locales at every state.
    """
    locale = narration['locale']
    templates = narration['templatesByLocale'][locale]
    messages = narration['messagesByLocale'][locale]
    if event in messages:
        return messages[event]
    if event not in ('direct', 'restore'):
        raise ValueError('Unknown narration event')
    program = narration['program']
    if program['kind'] == 'disclosure_v1':
        key = program['stateKey']
        message = 'evidence:' + state[key] if key == 'evidence' else 'openPanel:' + str(state[key])
        return messages[message] if message in messages else messages['panels:closed']
    controls = program['controls']
    if program['kind'] == 'state_delta_v1':
        descriptor = controls[0]
        option = next(o['label'] for o in descriptor['options'] if o['value'] == state[descriptor['id']])
        before = {item['id']: item for item in program['baselineView']}
        moved = changed = removed = 0
        for item in _semantic_view(evaluation['view']):
            old = before[item['id']]
            moved += item.get('rank') != old.get('rank') or any(
                item.get(axis) != (Decimal(old[axis]) if axis in old else None) for axis in ('x', 'y'))
            # state_delta_v1 counts restoration as a changed item; a new
            # removal retains its separate count. Count each changed item once.
            changed += (old['removed'] and not item['removed']) or any(item.get(slot) != (
                Decimal(old[slot]) if slot in old and slot in ('value', 'metric') else old.get(slot))
                for slot in ('value', 'metric', 'emphasis', 'highlight'))
            removed += item['removed'] and not old['removed']
        return fit_narration([templates['state'].format(label=descriptor['label'], option=option,
                             moved=moved, changed=changed, removed=removed)], location=location)
    if program['kind'] != 'numeric_delta_v1':
        raise ValueError('Unknown narration program')
    if event == 'direct':
        descriptor = next((atom for atom in controls if atom['id'] == control), None)
        if descriptor is None:
            raise ValueError('Direct numeric narration requires a known control')
    changed = [atom for atom in controls if _different(atom, state[atom['id']])]
    if not changed:
        return messages['initial']
    if event == 'restore':
        prefix = templates['restore'].format(count=len(changed)) if len(changed) > 1 else _control_text(changed[0], state, locale)
    else:
        prefix = _control_text(descriptor, state, locale)
    deltas = []
    for atom in program['outputs']:
        with localcontext() as context:
            context.prec = 40
            difference = Decimal(_value(evaluation['outputs'][atom['id']])) - Decimal(atom['baseline'])
        deltas.append(atom['label'] + ' ' + _format(difference, atom, locale, delta=True) if difference else '')
    transitions = []
    for atom in program['transitions']:
        after = _value(evaluation['outputs'][atom['id']])
        if atom['baseline'] != after:
            transitions.append(atom['baseline'] + ' → ' + after)
    optional = deltas[1:]
    while True:
        text = '; '.join(part for part in [prefix, deltas[0]] + optional + transitions if part)
        if len(text) <= 160:
            return text
        if not optional:
            fail(location, 'narration_length', 'mandatory narration <=160 Unicode scalars', len(text))
        optional.pop()


class _NarrationValidator:
    """Stream every state/event through the public oracle; retain O(schema) atoms."""
    def __init__(self, scene, initial, definitions, quantities, reporting):
        self.scene = scene
        self.templates = {lang: dict(templates) for lang, templates in NARRATION_TEXT.items()}
        self.messages = {lang: {} for lang in ('en', 'ja')}
        self.count = 0
        raw = scene.data
        controls = []
        for control in raw.get('controls', []):
            atom = {k: control[k] for k in ('id', 'kind', 'label')}
            atom['baseline'] = raw['initialState'][control['id']]
            if control['kind'] == 'range':
                quantity = quantities[control['quantity']]
                atom.update(unit=quantity.unit, display=quantity.display, precision=scene.scale)
            else:
                atom['options'] = [{k: option[k] for k in ('value', 'label')} for option in control['options']]
            controls.append(atom)
        if reporting:
            outputs = []
            for id in [reporting['primaryOutput']] + reporting['secondaryOutputs']:
                definition = definitions[id]
                quantity = quantities[definition.quantity]
                outputs.append({'id': id, 'label': definition.label, 'baseline': initial['outputs'][id].value,
                                'unit': quantity.unit, 'display': quantity.display, 'precision': definition.round})
            transitions = [{'id': id, 'baseline': initial['outputs'][id].value}
                           for id in ('classification', 'decisionStatus') if id in initial['outputs']]
            self.program = {'kind': 'numeric_delta_v1', 'controls': controls, 'outputs': outputs, 'transitions': transitions}
        elif raw['type'] == 'state_toggle':
            self.program = {'kind': 'state_delta_v1', 'controls': controls, 'baselineView': _semantic_view(initial['view'])}
        else:
            self.program = {'kind': 'disclosure_v1', 'stateKey': 'evidence' if raw['type'] == 'evidence_only' else 'panel'}
        for lang, templates in NARRATION_TEXT.items():
            messages = self.messages[lang]
            for key in ('closed', 'sources', 'assumptions', 'both'):
                messages['evidence:' + key] = fit_narration([templates[key]], location=scene.location)
            messages['panels:closed'] = '説明を閉じました' if lang == 'ja' else 'Panels closed'
            for panel in raw.get('panels', raw.get('items', [])):
                for action in ('openPanel', 'closePanel'):
                    messages[action + ':' + panel['id']] = fit_narration(
                        [templates[action].format(label=panel['label'])], location=scene.location)
            if reporting:
                atom = self.program['outputs'][0]
                baseline = atom['label'] + ' ' + _format(atom['baseline'], atom, lang)
                for key in ('baseline', 'reset'):
                    parts = [templates[key] + ': ' + baseline] + [atom['baseline'] for atom in self.program['transitions']]
                    messages['initial' if key == 'baseline' else key] = fit_narration(parts, location=scene.location)
            else:
                message = render_narration(self.result(lang), raw['initialState'], initial, event='restore', location=scene.location)
                messages['initial'] = message
                messages['reset'] = fit_narration([templates['reset'], message], location=scene.location)

    def visit(self, state, evaluation):
        for lang in NARRATION_TEXT:
            plan = self.result(lang)
            events = [('restore', None)]
            if self.program['kind'] == 'numeric_delta_v1':
                events += [('direct', control['id']) for control in self.program['controls']]
            elif self.program['kind'] == 'state_delta_v1':
                events += [('direct', None)]
            for event, control in events:
                render_narration(plan, state, evaluation, event=event, control=control, location=self.scene.location)
                self.count += 1

    def result(self, lang):
        return {'locale': lang, 'templates': self.templates[lang], 'templatesByLocale': self.templates, 'messages': self.messages[lang],
                'messagesByLocale': self.messages, 'program': self.program,
                'validatedVariants': self.count, 'comparison': 'initialState', 'maxScalars': 160}
