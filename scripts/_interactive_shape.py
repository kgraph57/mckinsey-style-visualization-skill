"""Private scene compiler: shape. No I/O except explicit loaders/render validation."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

if __package__:
    from .interactive_contract import (ControlDomain, Location, closed, fail, identifier, integer, parse_decimal, plain)
else:
    from interactive_contract import (ControlDomain, Location, closed, fail, identifier, integer, parse_decimal, plain)


@dataclass(frozen=True)
class LocatedDocument:
    data: dict
    location: Location


@dataclass(frozen=True)
class ValidatedScene:
    data: dict
    location: Location
    domains: tuple
    scale: int


def array(raw, minimum, maximum, loc):
    if not isinstance(raw, list):
        fail(loc, 'type', 'array', raw)
    if not minimum <= len(raw) <= maximum:
        fail(loc, 'limit', f'{minimum} through {maximum} entries', len(raw))
    return raw


def distinct(entries, key, loc):
    seen = set()
    for i, entry in enumerate(entries):
        value = identifier(entry[key], loc.child(i).child(key))
        if value in seen:
            fail(loc.child(i).child(key), 'duplicate_id', 'unique ID', value)
        seen.add(value)


def _walk(value, loc, depth=0):
    if depth > 32:
        fail(loc, 'limit', 'nesting depth <=32')
    scale = 0
    if isinstance(value, dict):
        for key, item in value.items():
            plain(key, loc, 2048)
            scale = max(scale, _walk(item, loc.child(key), depth + 1))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            scale = max(scale, _walk(item, loc.child(i), depth + 1))
    elif isinstance(value, str):
        # Exact field-specific caps are applied by the closed validators.
        plain(value, loc, 2048, empty=True)
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        number = parse_decimal(value, loc)
        presentation = any('/' + name + '/' in loc.pointer for name in ('domain', 'xDomain', 'yDomain')) or loc.pointer.endswith(('/ms', '/baseline'))
        if not presentation:
            scale = max(0, -number.as_tuple().exponent)
    elif value is not None and not isinstance(value, bool):
        fail(loc, 'type', 'JSON value', value)
    return scale


def load_scene(path):
    path = Path(path)
    loc = Location(str(path))
    if path.stat().st_size > 256 * 1024:
        fail(loc, 'limit', 'scene <=256 KiB')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                fail(loc.child(key), 'duplicate_id', 'unique JSON key', key)
            result[key] = value
        return result
    try:
        data = json.loads(path.read_text(encoding='utf-8'), parse_int=Decimal, parse_float=Decimal,
                          parse_constant=lambda _: fail(loc, 'numeric', 'finite JSON number'), object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        fail(loc, 'shape', 'bounded UTF-8 JSON', type(error).__name__)
    _walk(data, loc)
    return LocatedDocument(data, loc)


COMMON = ('version', 'type', 'purpose', 'decisionJob', 'interactionRationale', 'initialState', 'printState')


TYPE_FIELDS = {
    'slider_model': (('quantities', 'controls', 'model', 'reporting', 'decisionContract', 'view'), ()),
    'score_model': (('quantities', 'controls', 'model', 'reporting', 'decisionContract', 'view'), ()),
    'state_toggle': (('controls', 'states'), ('model', 'quantities')),
    'evidence_only': (('fallbackSummary',), ('triggerLabel',)),
    'drilldown': (('panels', 'parentSummary', 'returnLabel', 'fallbackSummary'), ()),
    'accordion': (('items', 'allowNone', 'fallbackSummary'), ()),
}


def validate_scene_shape(document):
    raw, loc = copy.deepcopy(document.data), document.location
    if not isinstance(raw, dict) or not isinstance(raw.get('type'), str) or raw.get('type') not in TYPE_FIELDS:
        fail(loc.child('type'), 'shape', 'one of six v1 scene types')
    required, optional = TYPE_FIELDS[raw['type']]
    closed(raw, COMMON + required, optional + ('sources', 'assumptions', 'demo'), loc)
    if integer(raw['version'], 1, 1, loc.child('version')) != 1:
        fail(loc.child('version'), 'shape', 'version 1')
    for key in ('purpose', 'interactionRationale'):
        plain(raw[key], loc.child(key))
    if raw['decisionJob'] not in ('fact', 'insight', 'action', 'decision'):
        fail(loc.child('decisionJob'), 'shape', 'fact, insight, action or decision', raw['decisionJob'])
    scale = _walk(raw, loc)
    for key in ('sources', 'assumptions'):
        entries = array(raw.get(key, []), 0, 20, loc.child(key))
        for i, entry in enumerate(entries):
            here = loc.child(key).child(i)
            req, opt = (('id', 'label', 'detail'), ('url',)) if key == 'sources' else (('id', 'label', 'value'), ('unit',))
            closed(entry, req, opt, here)
            for field, value in entry.items():
                plain(value, here.child(field), 2048 if field == 'url' else 2000 if field == 'detail' else 500)
        distinct(entries, 'id', loc.child(key))
    controls = array(raw.get('controls', []), 0, 8, loc.child('controls'))
    domains = []
    for i, control in enumerate(controls):
        here = loc.child('controls').child(i)
        kind = control.get('kind') if isinstance(control, dict) else None
        if kind == 'range':
            closed(control, ('id', 'kind', 'label', 'min', 'max', 'step', 'quantity', 'provenance'), loc=here)
            domains.append(ControlDomain.range(control['id'], control['min'], control['max'], control['step'], here))
        elif kind in ('segmented', 'toggle', 'select'):
            closed(control, ('id', 'kind', 'label', 'options'), loc=here)
            options = array(control['options'], 2, 2 if kind == 'toggle' else 8 if kind == 'select' else 4, here.child('options'))
            for j, option in enumerate(options):
                closed(option, ('value', 'label'), loc=here.child('options').child(j))
                plain(option['label'], here.child('options').child(j).child('label'), 64)
            distinct(options, 'value', here.child('options'))
            domains.append(ControlDomain(control['id'], tuple(o['value'] for o in options)))
        else:
            fail(here.child('kind'), 'shape', 'range, segmented, toggle or select', kind)
        plain(control['label'], here.child('label'), 40)
    distinct(controls, 'id', loc.child('controls'))
    kind = raw['type']
    if kind == 'slider_model' and (len(controls) != 1 or controls[0]['kind'] != 'range'):
        fail(loc.child('controls'), 'shape', 'exactly one range control')
    if kind == 'score_model' and len(controls) < 2:
        fail(loc.child('controls'), 'shape', 'two through eight controls')
    if kind == 'state_toggle' and (len(controls) != 1 or controls[0]['kind'] not in ('segmented', 'select')):
        fail(loc.child('controls'), 'shape', 'one segmented or select control')
    combinations = 1
    for domain in domains:
        combinations *= len(domain.values)
    if combinations > 65536:
        fail(loc.child('controls'), 'limit', '<=65536 accepted combinations', combinations)
    for key in ('initialState', 'printState'):
        state = raw[key]
        if domains:
            closed(state, tuple(d.id for d in domains), loc=loc.child(key))
            for domain in domains:
                value = state[domain.id]
                if domain.minimum is not None:
                    value = parse_decimal(value, loc.child(key).child(domain.id))
                elif not isinstance(value, str):
                    fail(loc.child(key).child(domain.id), 'state', 'option ID', value)
                if value not in domain.values:
                    fail(loc.child(key).child(domain.id), 'state', 'accepted on-grid control value', value)
                state[domain.id] = value
        elif kind == 'evidence_only':
            closed(state, ('evidence',), loc=loc.child(key))
            if state['evidence'] not in ('closed', 'sources', 'assumptions', 'both'):
                fail(loc.child(key), 'state', 'closed/sources/assumptions/both')
            if state['evidence'] in ('sources', 'both') and not raw.get('sources') or state['evidence'] in ('assumptions', 'both') and not raw.get('assumptions'):
                fail(loc.child(key), 'state', 'available evidence mode')
        else:
            closed(state, ('panel',), loc=loc.child(key))
    if raw['initialState'] != raw['printState']:
        fail(loc.child('printState'), 'state', 'exact equality with initialState')
    if kind == 'evidence_only' and not (raw.get('sources') or raw.get('assumptions')):
        fail(loc, 'provenance', 'at least one source or assumption')
    for field in ('triggerLabel', 'parentSummary', 'returnLabel'):
        if field in raw:
            plain(raw[field], loc.child(field), 64 if field != 'parentSummary' else 500)
    if kind in ('drilldown', 'accordion'):
        key = 'panels' if kind == 'drilldown' else 'items'
        entries = array(raw[key], 1 if key == 'panels' else 2, 5 if key == 'panels' else 6, loc.child(key))
        for i, entry in enumerate(entries):
            here = loc.child(key).child(i)
            closed(entry, ('id', 'label', 'heading', 'body'), ('sourceRefs',), here)
            for name in ('label', 'heading', 'body'):
                plain(entry[name], here.child(name), {'label': 64, 'heading': 500, 'body': 2000}[name])
            if 'sourceRefs' in entry:
                refs = array(entry['sourceRefs'], 1, 20, here.child('sourceRefs'))
                if any(r not in [e['id'] for e in raw.get('sources', [])] for r in refs) or len(set(refs)) != len(refs):
                    fail(here.child('sourceRefs'), 'reference', 'unique declared source IDs')
        distinct(entries, 'id', loc.child(key))
        if kind == 'accordion' and type(raw['allowNone']) is not bool:
            fail(loc.child('allowNone'), 'type', 'boolean')
        accepted = [entry['id'] for entry in entries] + ([None] if kind == 'drilldown' or raw['allowNone'] else [])
        for name in ('initialState', 'printState'):
            if raw[name]['panel'] not in accepted:
                fail(loc.child(name).child('panel'), 'state', 'declared panel, null only when permitted')
    if 'fallbackSummary' in raw:
        summary = closed(raw['fallbackSummary'], ('field', 'text'), loc=loc.child('fallbackSummary'))
        if summary['field'] not in ('headline', 'annotation', 'body'):
            fail(loc.child('fallbackSummary').child('field'), 'shape', 'headline, annotation or body')
        plain(summary['text'], loc.child('fallbackSummary').child('text'))
    if kind == 'state_toggle':
        states = array(raw['states'], 2, 4, loc.child('states'))
        for i, state in enumerate(states):
            closed(state, ('id', 'provenance', 'view'), loc=loc.child('states').child(i))
        distinct(states, 'id', loc.child('states'))
    array(raw.get('demo', []), 0, 80, loc.child('demo'))
    return ValidatedScene(raw, loc, tuple(domains), scale)
