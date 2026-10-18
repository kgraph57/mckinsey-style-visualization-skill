"""Private scene compiler: views. No I/O except explicit loaders/render validation."""
from __future__ import annotations

import copy

if __package__:
    from .interactive_contract import (DecisionSpec, EvidenceProvenance, Location, OutputDefinition, TypedValue, closed, fail, identifier, integer, parse_decimal, plain, require_same_quantity)
    from ._interactive_shape import (array, distinct)
else:
    from interactive_contract import (DecisionSpec, EvidenceProvenance, Location, OutputDefinition, TypedValue, closed, fail, identifier, integer, parse_decimal, plain, require_same_quantity)
    from _interactive_shape import (array, distinct)


def _reference(raw, definitions, controls, loc):
    closed(raw, ('ref',), loc=loc)
    ref = raw['ref']
    if not isinstance(ref, str) or ref.count(':') != 1:
        fail(loc.child('ref'), 'reference', 'control:<id> or output:<id>', ref)
    prefix, id = ref.split(':')
    if prefix == 'control' and id in controls:
        return controls[id].quantity
    if prefix == 'output' and id in definitions and definitions[id].kind == 'numeric':
        return definitions[id].quantity
    fail(loc.child('ref'), 'reference', 'declared numeric control/output', ref)


def _slot(c, raw, quantity, loc):
    if isinstance(raw, dict) and 'ref' in raw:
        q = _reference(raw, c.definitions, c.controls, loc)
        value = {'ref': raw['ref']}
    else:
        closed(raw, ('value', 'quantity', 'provenance'), loc=loc)
        value = c.numeric_leaf(raw, loc)
        q = value.quantity
    if quantity is not None:
        require_same_quantity(q, quantity, loc)
    return value


def _domain(raw, loc, zero=False):
    values = tuple(parse_decimal(v, loc.child(i)) for i, v in enumerate(array(raw, 2, 2, loc)))
    if values[0] >= values[1] or (zero and values[0] != 0):
        fail(loc, 'view_domain', 'ordered fixed domain' + (' starting at zero' if zero else ''))
    return values


def _compile_view(c, raw, loc):
    if not isinstance(raw, dict):
        fail(loc, 'type', 'typed view object')
    component = raw.get('component')
    allowed = {'state_toggle': ('ranked_list', 'bar_compare', 'dot_plot'), 'slider_model': ('bar_compare', 'dot_plot'), 'score_model': ('recommendation_panel',)}
    if component not in allowed.get(c.scene.data['type'], ()):
        fail(loc.child('component'), 'shape', 'component allowed for this scene type', component)
    if component == 'recommendation_panel':
        closed(raw, ('component', 'score'), ('annotation',), loc)
        result = {'component': component, 'score': _slot(c, raw['score'], c.definitions['score'].quantity, loc.child('score')), 'annotation': plain(raw.get('annotation', ''), loc.child('annotation'), empty=True)}
        if not isinstance(result['score'], dict) or result['score']['ref'] != 'output:score':
            fail(loc.child('score'), 'reference', 'score_sum output:score')
        return result
    if component == 'bar_compare':
        closed(raw, ('component', 'quantity', 'domain', 'baseline', 'items'), loc=loc)
    elif component == 'ranked_list':
        closed(raw, ('component', 'items'), ('quantity', 'domain', 'baseline'), loc)
    else:
        closed(raw, ('component', 'xLabel', 'xQuantity', 'xDomain', 'yLabel', 'yQuantity', 'yDomain', 'points'), ('domainReason',), loc)
    result = {'component': component}
    if component == 'dot_plot':
        for axis in ('x', 'y'):
            result[axis + 'Label'] = plain(raw[axis + 'Label'], loc.child(axis + 'Label'))
            result[axis + 'Quantity'] = c.quantity(raw[axis + 'Quantity'], loc.child(axis + 'Quantity'))
            result[axis + 'Domain'] = _domain(raw[axis + 'Domain'], loc.child(axis + 'Domain'))
        if result['xDomain'][0] != 0 or result['yDomain'][0] != 0:
            if 'domainReason' not in raw:
                fail(loc.child('domainReason'), 'view_domain', 'reason for nonzero dot domain')
        if 'domainReason' in raw:
            result['domainReason'] = plain(raw['domainReason'], loc.child('domainReason'))
    else:
        numeric = component == 'bar_compare' or any(isinstance(item, dict) and 'metric' in item for item in raw['items'])
        if numeric:
            for name in ('quantity', 'domain', 'baseline'):
                if name not in raw:
                    fail(loc.child(name), 'shape', 'metric view requires quantity/domain/baseline')
            result['quantity'] = c.quantity(raw['quantity'], loc.child('quantity'))
            result['domain'] = _domain(raw['domain'], loc.child('domain'), True)
            result['baseline'] = parse_decimal(raw['baseline'], loc.child('baseline'))
            if result['baseline'] != 0:
                fail(loc.child('baseline'), 'view_domain', 'zero baseline')
        elif any(key in raw for key in ('quantity', 'domain', 'baseline')):
            fail(loc, 'shape', 'metric metadata only with numeric metrics')
    key = 'points' if component == 'dot_plot' else 'items'
    entries = array(raw[key], 1, 12, loc.child(key))
    items, emphasis = [], 0
    for i, item in enumerate(entries):
        here = loc.child(key).child(i)
        required = {'bar_compare': ('id', 'label', 'value'), 'ranked_list': ('id', 'label', 'rank'), 'dot_plot': ('id', 'label', 'x', 'y')}[component]
        optional = ('highlight', 'removed') if component == 'dot_plot' else ('emphasis', 'removed', 'metric') if component == 'ranked_list' else ('emphasis', 'removed')
        closed(item, required, optional, here)
        flag = 'highlight' if component == 'dot_plot' else 'emphasis'
        row = {'id': item['id'], 'label': plain(item['label'], here.child('label')), flag: item.get(flag, False), 'removed': item.get('removed', False)}
        for boolean in (flag, 'removed'):
            if type(row[boolean]) is not bool:
                fail(here.child(boolean), 'type', 'boolean')
        emphasis += row[flag]
        if component == 'ranked_list':
            row['rank'] = integer(item['rank'], 1, len(entries), here.child('rank'))
        for slot in {'bar_compare': ('value',), 'ranked_list': ('metric',), 'dot_plot': ('x', 'y')}[component]:
            if slot in item:
                quantity = result[slot + 'Quantity'] if component == 'dot_plot' else result.get('quantity')
                row[slot] = _slot(c, item[slot], quantity, here.child(slot))
        items.append(row)
    distinct(entries, 'id', loc.child(key))
    if emphasis > 1:
        fail(loc.child(key), 'shape', 'at most one emphasized item')
    if component == 'ranked_list':
        if len({item['rank'] for item in items}) != len(items):
            fail(loc.child(key), 'shape', 'unique ranks 1 through N')
        items.sort(key=lambda x: x['rank'])
    result[key] = tuple(items)
    return result


def resolve_view(view, state, outputs, quantities, *, location=Location(), check_bounds=True):
    """Resolve a compiled view using typed control values and typed outputs."""
    def resolve(slot):
        if isinstance(slot, TypedValue):
            return slot
        prefix, id = slot['ref'].split(':')
        result = (state if prefix == 'control' else outputs)[id]
        if not isinstance(result, TypedValue):
            fail(Location(), 'reference', 'numeric slot result')
        return result
    result = copy.deepcopy(view)
    if view['component'] == 'recommendation_panel':
        result['score'] = resolve(view['score'])
        return result
    key = 'points' if view['component'] == 'dot_plot' else 'items'
    items = []
    for i, item in enumerate(view[key]):
        row = dict(item)
        for slot in ('x', 'y', 'value', 'metric'):
            if slot in item:
                value = resolve(item[slot])
                domain = view[slot + 'Domain'] if slot in ('x', 'y') else view['domain']
                if check_bounds and not domain[0] <= value.value <= domain[1]:
                    fail(location.child('view').child(key).child(i).child(slot), 'view_domain', 'value within fixed domain', value.value)
                row[slot] = value
        items.append(row)
    result[key] = tuple(items)
    return result


def _compile_decision(c, raw, loc):
    closed(raw, ('id', 'metric', 'operator', 'threshold', 'whenMet', 'whenNotMet'), loc=loc)
    id = identifier(raw['id'], loc.child('id'))
    quantity = _reference(raw['metric'], c.definitions, c.controls, loc.child('metric'))
    if raw['operator'] not in ('lt', 'lte', 'gt', 'gte'):
        fail(loc.child('operator'), 'shape', 'lt/lte/gt/gte')
    closed(raw['threshold'], ('value', 'quantity', 'provenance'), loc=loc.child('threshold'))
    threshold = c.numeric_leaf(raw['threshold'], loc.child('threshold'), label='Decision threshold')
    require_same_quantity(quantity, threshold.quantity, loc.child('threshold'))
    for field in ('whenMet', 'whenNotMet'):
        closed(raw[field], ('status', 'recommendation'), loc=loc.child(field))
        plain(raw[field]['status'], loc.child(field).child('status'), 32)
        plain(raw[field]['recommendation'], loc.child(field).child('recommendation'))
    c.definitions['decisionStatus'] = OutputDefinition('text', 'Decision status')
    c.definitions['recommendation'] = OutputDefinition('text', 'Recommendation')
    provenance = EvidenceProvenance(raw['threshold']['provenance']['basis'], threshold.lineage.source_refs, threshold.lineage.assumption_refs, threshold.lineage.normalizations[0] if threshold.lineage.normalizations else ())
    return DecisionSpec(id, raw['metric']['ref'], raw['operator'], threshold, raw['whenMet']['status'], raw['whenMet']['recommendation'], raw['whenNotMet']['status'], raw['whenNotMet']['recommendation'], provenance)


def _invariant_view(view):
    if view['component'] == 'recommendation_panel':
        return {'component': view['component'], 'annotation': view['annotation']}
    key = 'points' if view['component'] == 'dot_plot' else 'items'
    return {**{k: v for k, v in view.items() if k != key}, 'labels': {row['id']: row['label'] for row in view[key]}, 'slots': {row['id']: tuple(k for k in ('value', 'metric', 'x', 'y') if k in row) for row in view[key]}}
