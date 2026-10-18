"""Private scene compiler: fallback. No I/O except explicit loaders/render validation."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from dataclasses import replace
from decimal import Decimal

if __package__:
    from .interactive_contract import (Location, TypedValue, canonical_decimal, closed, fail, format_value, parse_decimal)
else:
    from interactive_contract import (Location, TypedValue, canonical_decimal, closed, fail, format_value, parse_decimal)


@dataclass(frozen=True)
class FallbackProjection:
    spec: dict
    scene_type: str
    component: str | None
    locale: str
    location: Location = Location('<fallback>')


def project_fallback(spec, scene_type, component, locale):
    if __package__:
        from . import render_slide_spec
    else:
        import render_slide_spec
    def renderer_copy(value):
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else float(value)
        if isinstance(value, dict): return {key: renderer_copy(item) for key, item in value.items()}
        if isinstance(value, list): return [renderer_copy(item) for item in value]
        return value
    # The legacy geometry API is float-based. Retain the untouched Decimal
    # source for all semantic equality checks; only its defensive validation
    # copy enters the static renderer.
    defensive = renderer_copy(spec)
    try:
        render_slide_spec.validate_spec(defensive)
        rendered = render_slide_spec.render(defensive)
    except (ValueError, KeyError, TypeError) as error:
        fail(Location('<fallback>'), 'fallback_mismatch', 'valid static content spec', type(error).__name__)
    # A value present only in metadata or a title tooltip is not a visible
    # print equivalent. Rendering truncation must be resolved by the author.
    import xml.etree.ElementTree as ET
    for text in ET.fromstring(rendered).iter('{http://www.w3.org/2000/svg}text'):
        visible = (text.text or '') + ''.join(child.tail or '' for child in text)
        if visible.endswith(render_slide_spec.ELLIPSIS):
            fail(Location('<fallback>'), 'fallback_mismatch', 'visible static text without truncation')
    if spec['pattern'] in ('cover', 'section_divider', 'end_cover') or spec.get('layout', 'standard') != 'standard':
        fail(Location('<fallback>'), 'fallback_mismatch', 'standard content slide')
    matrix = {'ranked_list': ('bullet_list',), 'bar_compare': ('gap', 'before_after'), 'dot_plot': ('scatter',), 'recommendation_panel': ('summary_strip', 'closing')}
    if component is not None and spec['pattern'] not in matrix.get(component, ()):
        fail(Location('<fallback>', '/pattern'), 'fallback_mismatch', 'registered typed adapter', spec['pattern'])
    return FallbackProjection(copy.deepcopy(spec), scene_type, component, locale)


def _number_text(value, definitions, quantities, locale):
    precision = max(0, -value.value.as_tuple().exponent)
    return format_value(value.value, quantities[value.quantity], precision, locale)


def _decision_display(evaluation, invariants, locale):
    definition = invariants['definitions'][invariants['reporting']['primaryOutput']]
    value = evaluation['outputs'][invariants['reporting']['primaryOutput']]
    score = format_value(value.value, invariants['quantities'][value.quantity], definition.round, locale)
    decision, spec = evaluation['decision'], invariants['decision']
    threshold = _number_text(spec.threshold, {}, invariants['quantities'], locale)
    operator = {'lt': '<', 'lte': '≤', 'gt': '>', 'gte': '≥'}[spec.operator]
    sentence = f'{decision.status}; ' + ('しきい値' if locale == 'ja' else 'threshold') + f' {operator} {threshold}'
    summary = f'{definition.label} {score}; {sentence}; {decision.recommendation}'
    return score, sentence, summary


def validate_fallback(print_evaluation, projection, invariants):
    spec, view, loc = projection.spec, print_evaluation.get('view'), projection.location
    def equal(actual, expected, path):
        if isinstance(expected, Decimal):
            actual = parse_decimal(actual, Location(loc.file, path))
        if type(expected) is bool and type(actual) is not bool:
            fail(Location(loc.file, path), 'fallback_mismatch', 'explicit boolean flag', actual)
        if type(expected) is int and isinstance(actual, bool):
            fail(Location(loc.file, path), 'fallback_mismatch', 'integer, not boolean', actual)
        if actual != expected:
            fail(Location(loc.file, path), 'fallback_mismatch', 'exact print-state value ' + (canonical_decimal(expected) if isinstance(expected, Decimal) else repr(expected)[:100]), actual)
    def number(actual, expected, path):
        equal(actual, expected.value if isinstance(expected, TypedValue) else expected, path)
    def field(container, key, expected, path):
        if key not in container:
            fail(Location(loc.file, path + '/' + key), 'fallback_mismatch', 'explicit field matching print state')
        equal(container[key], expected, path + '/' + key)
    _validate_model_context(spec, invariants, equal, number, field, loc)
    if view is None:
        summary = invariants['fallbackSummary']
        key = summary['field']
        if key == 'body':
            if spec['pattern'] != 'quote':
                fail(loc, 'fallback_mismatch', 'registered single body field: quote.text')
            key = 'text'
        field(spec, key, summary['text'], '')
        return {'matched': True, 'pattern': spec['pattern']}
    component = view['component']
    quantities, definitions = invariants['quantities'], invariants['definitions']
    def display(slot):
        return _number_text(slot, definitions, quantities, projection.locale)
    if component in ('bar_compare', 'ranked_list') and 'quantity' in view:
        field(spec, 'quantity', view['quantity'], '')
        field(spec, 'unit', quantities[view['quantity']].display, '')
        field(spec, 'baseline', view['baseline'], '')
        domain = spec.get('value_domain')
        if not isinstance(domain, list) or len(domain) != 2:
            fail(loc.child('value_domain'), 'fallback_mismatch', 'explicit two-endpoint domain')
        for i, expected in enumerate(view['domain']):
            number(domain[i], expected, '/value_domain/' + str(i))
    if component == 'bar_compare':
        if spec['pattern'] == 'gap':
            rows = spec['items']
            equal(len(rows), len(view['items']), '/items')
            for i, (row, item) in enumerate(zip(rows, view['items'])):
                path = '/items/' + str(i)
                for key, expected in [('item_id', item['id']), ('label', item['label']), ('emphasis', item['emphasis'])]:
                    field(row, key, expected, path)
                number(row.get('value'), item['value'], path + '/value')
                field(row, 'value_text', item.get('valueText', display(item['value'])), path)
                equal(row.get('removed', False), item['removed'], path + '/removed')
        else:
            _validate_before_after(spec, view, field, equal, number, display)
    elif component == 'ranked_list':
        rows = spec['bullets']
        equal(len(rows), len(view['items']), '/bullets')
        for i, (row, item) in enumerate(zip(rows, view['items'])):
            path = '/bullets/' + str(i)
            for key, expected in [('item_id', item['id']), ('text', item['label']), ('rank', item['rank']), ('removed', item['removed']), ('emphasis', item['emphasis'])]:
                field(row, key, expected, path)
            sub = []
            if 'metric' in item:
                number(row.get('metric'), item['metric'], path + '/metric')
                sub.append(item.get('metricText', display(item['metric'])))
            elif 'metric' in row:
                fail(Location(loc.file, path + '/metric'), 'fallback_mismatch', 'no extra metric')
            if item['removed']:
                sub.append('除外' if projection.locale == 'ja' else 'Removed')
            equal(row.get('sub', []), sub, path + '/sub')
    elif component == 'dot_plot':
        _validate_scatter(spec, view, quantities, projection.locale, field, equal, number, loc)
    else:
        _validate_recommendation(spec, view, print_evaluation, invariants, projection.locale, field, equal)
    if 'decision' in print_evaluation:
        result = spec.get('interactive_result')
        has_class = 'classification' in print_evaluation['outputs']
        closed(result, ('quantity', 'value', 'decision_status', 'recommendation', 'operator', 'threshold') + (('classification',) if has_class else ()), loc=loc.child('interactive_result'))
        output = print_evaluation['outputs'][invariants['reporting']['primaryOutput']]
        for key, expected in [('quantity', output.quantity), ('value', output.value), ('decision_status', print_evaluation['decision'].status), ('recommendation', print_evaluation['decision'].recommendation), ('operator', invariants['decision'].operator), ('threshold', invariants['decision'].threshold.value)]:
            field(result, key, expected, '/interactive_result')
        if has_class:
            field(result, 'classification', print_evaluation['outputs']['classification'].value, '/interactive_result')
        if projection.scene_type == 'slider_model':
            field(spec, 'annotation', _decision_display(print_evaluation, invariants, projection.locale)[2], '')
    return {'matched': True, 'pattern': spec['pattern']}


def _validate_model_context(spec, invariants, equal, number, field, loc):
    """Additional visual proof is executable-model evidence, not decoration.

    Renderer validation covers shape and geometry. This pass binds any line,
    contribution or second scenario to the scene that the reader can operate.
    The internal program/rawScene inputs are never serialized for the audience.
    """
    context = spec.get('model_context')
    if context is None:
        return
    program, raw = invariants['program'], invariants['rawScene']
    path = '/model_context'
    p = program.instructions
    controls = {control['id']: control for control in raw.get('controls', [])}
    kind = context['kind']
    if kind == 'linear_model':
        equal(program.kind, 'linear', path + '/kind')
        equal(len(p['terms']), 1, path + '/coefficient')
        control_id, coefficient = p['terms'][0]
        number(context['intercept'], p['intercept'], path + '/intercept')
        number(context['coefficient'], coefficient['value'], path + '/coefficient')
        view = raw.get('view', {})
        equal(view.get('component'), 'dot_plot', path + '/kind')
        equal(len(view.get('points', [])), 1, path + '/kind')
        equal(view['points'][0]['x'], {'ref': 'control:' + control_id}, path + '/kind')
        equal(view['points'][0]['y'], {'ref': 'output:' + p['output']}, path + '/kind')
        equal(raw['reporting']['primaryOutput'], p['output'], path + '/kind')
    elif kind == 'score_breakdown':
        equal(program.kind, 'score_sum', path + '/kind')
        components = context['components']
        equal(len(components), len(p['contributions']), path + '/components')
        for index, (component, (control_id, values)) in enumerate(zip(components, p['contributions'])):
            base = path + '/components/' + str(index)
            field(component, 'label', controls[control_id]['label'], base)
            number(component['value'], dict(values)[raw['printState'][control_id]], base + '/value')
        if 'comparison' in context:
            index = int(context['comparison']['remove_index'])
            _, values = p['contributions'][index]
            if not any(value.value == 0 for _, value in values):
                fail(loc.child('model_context').child('comparison').child('remove_index'),
                     'fallback_mismatch', 'removal with a reachable zero-point option')
    elif kind == 'scenario_compare':
        equal(program.kind, 'state_map', path + '/kind')
        matching = [option for option in controls[p['input']]['options']
                    if option['label'] == context['label']]
        equal(len(matching), 1, path + '/label')
        state_id = dict(p['entries'])[matching[0]['value']]
        state = next(state for state in invariants['resolvedStates'] if state['id'] == state_id)
        equal(state['view']['component'], 'ranked_list', path + '/kind')
        expected = {item['id']: item for item in state['view']['items']}
        equal({item['item_id'] for item in context['values']}, set(expected), path + '/values')
        equal(len(context['values']), len(expected), path + '/values')
        for index, item in enumerate(context['values']):
            base = path + '/values/' + str(index)
            match = expected[item['item_id']]
            number(item['value'], match['metric'], base + '/value')
            field(item, 'rank', match['rank'], base)
    else:
        fail(loc.child('model_context').child('kind'), 'fallback_mismatch', 'registered evidence context', kind)


def _validate_before_after(spec, view, field, equal, number, display):
    equal(len(spec['pairs']), 1, '/pairs')
    equal(len(view['items']), 2, '/pairs')
    pair = spec['pairs'][0]
    for index, prefix in enumerate(('before', 'after')):
        item = view['items'][index]
        field(pair, prefix + '_item_id', item['id'], '/pairs/0')
        equal(pair['label'] + ' · ' + spec.get(prefix + '_label', prefix.title()), item['label'], '/pairs/0/label')
        equal(item['emphasis'], prefix == 'after', '/pairs/0/' + prefix + '_item_id')
        equal(item['removed'], False, '/pairs/0/' + prefix + '_item_id')
        number(pair[prefix], item['value'], '/pairs/0/' + prefix)
        field(pair, prefix + '_text', item.get('valueText', display(item['value'])), '/pairs/0')
    delta = view['items'][1]['value'].value - view['items'][0]['value'].value
    text = display(replace(view['items'][0]['value'], value=abs(delta)))
    field(pair, 'delta_text', ('+' if delta >= 0 else '−') + text, '/pairs/0')
    if 'unit' in pair:
        equal(pair['unit'], spec['unit'], '/pairs/0/unit')


def _validate_scatter(spec, view, quantities, locale, field, equal, number, loc):
    for extra in ('thresholds', 'trendline', 'trendlines', 'overlays', 'legend'):
        if extra in spec:
            fail(loc.child(extra), 'fallback_mismatch', 'no unrepresented scatter overlays')
    for axis in ('x', 'y'):
        raw = spec[axis + '_axis']
        path = '/' + axis + '_axis'
        q = quantities[view[axis + 'Quantity']]
        for key, expected in [('label', view[axis + 'Label']), ('quantity', q.id), ('unit', q.display)]:
            field(raw, key, expected, path)
        if 'domain' not in raw or len(raw['domain']) != 2:
            fail(Location(loc.file, path + '/domain'), 'fallback_mismatch', 'explicit two-endpoint domain')
        labels = []
        for i, expected in enumerate(view[axis + 'Domain']):
            number(raw['domain'][i], expected, path + '/domain/' + str(i))
            labels.append(format_value(expected, q, max(0, -expected.as_tuple().exponent), locale))
        field(raw, 'tick_labels', labels, path)
    equal(spec.get('domain_reason'), view.get('domainReason'), '/domain_reason')
    equal(len(spec['points']), len(view['points']), '/points')
    for i, (raw, item) in enumerate(zip(spec['points'], view['points'])):
        path = '/points/' + str(i)
        for key, expected in [('item_id', item['id']), ('label', item['label']), ('emphasis', item['highlight'])]:
            field(raw, key, expected, path)
        for axis in ('x', 'y'):
            number(raw[axis], item[axis], path + '/' + axis)
        equal(raw.get('removed', False), item['removed'], path + '/removed')


def _validate_recommendation(spec, view, evaluation, invariants, locale, field, equal):
    score, sentence, _ = _decision_display(evaluation, invariants, locale)
    classification = evaluation['outputs']['classification'].value
    recommendation = evaluation['decision'].recommendation
    field(spec, 'annotation', view['annotation'], '')
    if spec['pattern'] == 'summary_strip':
        equal(len(spec['blocks']), 1, '/blocks')
        for key, expected in [('metric', score), ('claim', classification), ('proof', sentence), ('implication', recommendation)]:
            field(spec['blocks'][0], key, expected, '/blocks/0')
    else:
        label = invariants['definitions'][invariants['reporting']['primaryOutput']].label
        field(spec, 'takeaways', [label + ' ' + score, classification, sentence], '')
        field(spec, 'next_steps', [{'action': recommendation}], '')
        if 'call_to_action' in spec:
            equal(spec['call_to_action'], view['annotation'], '/call_to_action')
