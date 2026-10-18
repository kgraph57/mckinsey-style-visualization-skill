"""Private scene compiler: models. No I/O except explicit loaders/render validation."""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

if __package__:
    from .interactive_contract import (Location, OutputDefinition, RESERVED, TextValue, TypedValue, canonical_decimal, closed, combine_lineage, compile_provenance, fail, identifier, integer, normalized, parse_decimal, plain, require_same_quantity)
    from ._interactive_graph import (_compile_graph, _evaluate_graph)
    from ._interactive_shape import (array, distinct)
else:
    from interactive_contract import (Location, OutputDefinition, RESERVED, TextValue, TypedValue, canonical_decimal, closed, combine_lineage, compile_provenance, fail, identifier, integer, normalized, parse_decimal, plain, require_same_quantity)
    from _interactive_graph import (_compile_graph, _evaluate_graph)
    from _interactive_shape import (array, distinct)


@dataclass(frozen=True)
class ModelProgram:
    kind: str
    scale: int
    instructions: dict
    definitions: dict
    controls: dict
    domains: tuple
    quantities: dict
    evidence: dict
    leaves: tuple
    locations: dict
    location: Location


class _Compiler:
    def __init__(self, scene, quantities, evidence):
        self.scene, self.quantities, self.evidence = scene, quantities, evidence
        self.leaves, self.locations, self.controls, self.definitions = [], {}, {}, {}

    def quantity(self, key, loc):
        if not isinstance(key, str) or key not in self.quantities:
            fail(loc, 'reference', 'declared quantity ID', key)
        return key

    def leaf(self, value, quantity, provenance, loc, inherited=None, label='Value'):
        number = parse_decimal(value, loc.child('value'))
        self.quantity(quantity, loc.child('quantity'))
        lineage = compile_provenance(provenance, self.evidence, loc.child('provenance'), inherited)
        for note in lineage.normalizations:
            if dict(note)['toUnit'] != self.quantities[quantity].unit:
                fail(loc.child('provenance'), 'provenance', 'normalization toUnit equal to storage unit')
        id = f'leaf-{len(self.leaves) + 1:03d}'
        lineage = replace(lineage, leaves=(id,))
        self.leaves.append({'id': id, 'label': label, 'quantity': quantity, 'basis': lineage.badge, 'sourceRefs': list(lineage.source_refs), 'assumptionRefs': list(lineage.assumption_refs)})
        self.locations[id] = loc
        return TypedValue(number, quantity, lineage)

    def numeric_leaf(self, raw, loc, inherited=None, label='Value'):
        closed(raw, ('value', 'quantity'), ('provenance',), loc)
        return self.leaf(raw['value'], raw['quantity'], raw.get('provenance'), loc, inherited, label)

    def coefficient(self, raw, loc, inherited, input_q, output_q):
        closed(raw, ('coefficient', 'inputQuantity', 'outputQuantity'), ('provenance',), loc)
        require_same_quantity(input_q, raw['inputQuantity'], loc.child('inputQuantity'))
        require_same_quantity(output_q, raw['outputQuantity'], loc.child('outputQuantity'))
        value = self.leaf(raw['coefficient'], output_q, raw.get('provenance'), loc, inherited, 'Coefficient')
        return {'value': value, 'inputQuantity': input_q, 'outputQuantity': output_q}

    def definition(self, id, raw, loc, quantity=None):
        if id not in ('score',):
            identifier(id, loc)
            if id in RESERVED:
                fail(loc, 'duplicate_id', 'nonreserved output ID', id)
        q = self.quantity(quantity if quantity is not None else raw.get('quantity'), loc.child('quantity'))
        fmt = raw['format']
        if fmt not in ('number', 'percent', 'currency', 'duration', 'score'):
            fail(loc.child('format'), 'shape', 'number/percent/currency/duration/score')
        dimension = self.quantities[q].dimension
        if fmt != 'number' and dimension != {'percent': 'ratio', 'currency': 'currency', 'duration': 'time', 'score': 'score'}[fmt]:
            fail(loc.child('format'), 'quantity', 'format compatible with quantity')
        label = plain(raw.get('label', id.replace('_', ' ').replace('-', ' ')), loc.child('label'), 40)
        self.definitions[id] = OutputDefinition('numeric', label, q, fmt, integer(raw['round'], 0, 6, loc.child('round')))


def compile_model(scene, quantities, evidence):
    compiler = _Compiler(scene, quantities, evidence)
    raw, root = scene.data, scene.location
    for i, control in enumerate(raw.get('controls', [])):
        if control['kind'] == 'range':
            compiler.controls[control['id']] = compiler.leaf(raw['initialState'][control['id']], control['quantity'], control['provenance'], root.child('controls').child(i), label=control['label'])
    model, loc = raw.get('model'), root.child('model')
    if model is None:
        if raw['type'] == 'state_toggle':
            model = {'kind': 'state_map', 'input': raw['controls'][0]['id'], 'entries': [{'input': o['value'], 'state': o['value']} for o in raw['controls'][0]['options']]}
        else:
            return ModelProgram('none', scene.scale, {}, {}, compiler.controls, scene.domains, quantities, evidence, tuple(compiler.leaves), compiler.locations, root)
    if not isinstance(model, dict):
        fail(loc, 'type', 'typed model object')
    kind = model.get('kind')
    allowed = {'slider_model': ('linear', 'lookup', 'piecewise', 'operation_graph'), 'score_model': ('score_sum',), 'state_toggle': ('state_map',)}
    if kind not in allowed.get(raw['type'], ()):
        fail(loc.child('kind'), 'shape', 'model allowed for scene type', kind)
    inherited = compile_provenance(model['modelProvenance'], evidence, loc.child('modelProvenance')) if 'modelProvenance' in model else None
    instructions = {}
    domains = {d.id: d for d in scene.domains}
    if kind in ('linear', 'lookup', 'piecewise'):
        fields = {'linear': ('intercept', 'terms'), 'lookup': ('input', 'entries'), 'piecewise': ('input', 'segments')}[kind]
        closed(model, ('kind', 'output', 'outputQuantity', 'format', 'round') + fields, ('label', 'modelProvenance'), loc)
        output, q = model['output'], model['outputQuantity']
        if output in RESERVED:
            fail(loc.child('output'), 'duplicate_id', 'nonreserved output ID', output)
        compiler.definition(output, model, loc, q)
        instructions['output'] = output
        if kind == 'linear':
            intercept = compiler.numeric_leaf(model['intercept'], loc.child('intercept'), inherited, 'Intercept')
            require_same_quantity(intercept.quantity, q, loc.child('intercept'))
            terms = model['terms']
            if not isinstance(terms, dict) or not terms:
                fail(loc.child('terms'), 'shape', 'nonempty named coefficient map')
            compiled_terms = []
            for control, term in terms.items():
                if control not in compiler.controls:
                    fail(loc.child('terms').child(control), 'reference', 'numeric range control')
                compiled_terms.append((control, compiler.coefficient(term, loc.child('terms').child(control), inherited, compiler.controls[control].quantity, q)))
            instructions.update(intercept=intercept, terms=tuple(compiled_terms))
        elif kind == 'lookup':
            control = identifier(model['input'], loc.child('input'))
            if control not in compiler.controls:
                fail(loc.child('input'), 'reference', 'range control')
            entries = array(model['entries'], 1, 10001, loc.child('entries'))
            keys, values = [], []
            for i, entry in enumerate(entries):
                here = loc.child('entries').child(i)
                closed(entry, ('input', 'output'), loc=here)
                keys.append(parse_decimal(entry['input'], here.child('input')))
                leaf = compiler.numeric_leaf(entry['output'], here.child('output'), inherited, 'Lookup result')
                require_same_quantity(leaf.quantity, q, here.child('output'))
                values.append(leaf)
            if tuple(keys) != domains[control].values:
                fail(loc.child('entries'), 'model_domain', 'exactly one ascending entry per accepted input')
            instructions.update(input=control, entries=tuple(zip(keys, values)))
        else:
            instructions = _compile_piecewise(compiler, model, inherited, domains, loc)
    elif kind == 'state_map':
        closed(model, ('kind', 'input', 'entries'), loc=loc)
        control = identifier(model['input'], loc.child('input'))
        if control != scene.domains[0].id:
            fail(loc.child('input'), 'reference', 'scene categorical control')
        entries = array(model['entries'], 2, 4, loc.child('entries'))
        for i, entry in enumerate(entries):
            closed(entry, ('input', 'state'), loc=loc.child('entries').child(i))
            identifier(entry['input'], loc.child('entries').child(i).child('input'))
            identifier(entry['state'], loc.child('entries').child(i).child('state'))
        if tuple(e['input'] for e in entries) != scene.domains[0].values or sorted(e['state'] for e in entries) != sorted(s['id'] for s in raw['states']):
            fail(loc.child('entries'), 'model_domain', 'bijection from options in declaration order to scene states')
        instructions = {'input': control, 'entries': tuple((e['input'], e['state']) for e in entries)}
    elif kind == 'score_sum':
        instructions = _compile_score(compiler, model, inherited, domains, loc)
    elif kind == 'operation_graph':
        instructions = _compile_graph(compiler, model, domains, loc)
    return ModelProgram(kind, scene.scale, instructions, compiler.definitions, compiler.controls, scene.domains, quantities, evidence, tuple(compiler.leaves), compiler.locations, root)


def _state_controls(program, state):
    result = {}
    for domain in program.domains:
        if domain.id not in state:
            fail(program.location, 'state', 'complete state')
        value = state[domain.id]
        if domain.minimum is not None:
            value = parse_decimal(value, program.location)
        if value not in domain.values or isinstance(value, bool):
            fail(program.location, 'state', 'accepted value', value)
        if domain.id in program.controls:
            result[domain.id] = replace(program.controls[domain.id], value=value)
    if set(state) != {d.id for d in program.domains}:
        fail(program.location, 'state', 'only declared controls')
    return result


def evaluate_model(program, state):
    p, kind = program.instructions, program.kind
    if kind in ('none', 'state_map'):
        return {}
    controls = _state_controls(program, state)
    if kind == 'linear':
        value = Fraction(p['intercept'].value)
        lines = [p['intercept'].lineage]
        for control, term in p['terms']:
            value += Fraction(controls[control].value) * Fraction(term['value'].value)
            lines += [controls[control].lineage, term['value'].lineage]
        definition = program.definitions[p['output']]
        return {p['output']: TypedValue(normalized(value, program.scale, program.location.child('model')), definition.quantity, combine_lineage(*lines, step='model:linear'))}
    if kind == 'lookup':
        leaf = dict(p['entries'])[controls[p['input']].value]
        return {p['output']: replace(leaf, lineage=combine_lineage(leaf.lineage, controls[p['input']].lineage, step='model:lookup', derived=False))}
    if kind == 'piecewise':
        return _evaluate_piecewise(program, controls)
    if kind == 'score_sum':
        return _evaluate_score(program, state, controls)
    return _evaluate_graph(program, controls)


def _compile_piecewise(c, model, inherited, domains, loc):
    control, q = identifier(model['input'], loc.child('input')), model['outputQuantity']
    if control not in c.controls:
        fail(loc.child('input'), 'reference', 'range control')
    segments = []
    for i, raw in enumerate(array(model['segments'], 1, 10001, loc.child('segments'))):
        here = loc.child('segments').child(i)
        kind = raw.get('kind') if isinstance(raw, dict) else None
        if kind not in ('linear', 'endpoints'):
            fail(here.child('kind'), 'shape', 'linear or endpoints')
        fields = ('slope', 'intercept') if kind == 'linear' else ('start', 'end')
        closed(raw, ('kind', 'min', 'max', 'inputQuantity') + fields, ('provenance',), here)
        require_same_quantity(raw['inputQuantity'], c.controls[control].quantity, here.child('inputQuantity'))
        lineage = compile_provenance(raw.get('provenance'), c.evidence, here.child('provenance'), inherited)
        a = c.leaf(raw['min'], raw['inputQuantity'], None, here.child('min'), lineage, 'Segment start')
        b = c.leaf(raw['max'], raw['inputQuantity'], None, here.child('max'), lineage, 'Segment end')
        if a.value >= b.value or (segments and segments[-1]['max'].value != a.value):
            fail(here, 'model_domain', 'positive, contiguous ordered segment intervals')
        segment = {'kind': kind, 'min': a, 'max': b}
        if kind == 'linear':
            segment['slope'] = c.coefficient(raw['slope'], here.child('slope'), inherited, raw['inputQuantity'], q)
            segment['intercept'] = c.numeric_leaf(raw['intercept'], here.child('intercept'), inherited, 'Intercept')
            require_same_quantity(segment['intercept'].quantity, q, here)
        else:
            for key in ('start', 'end'):
                segment[key] = c.numeric_leaf(raw[key], here.child(key), inherited, 'Endpoint')
                require_same_quantity(segment[key].quantity, q, here.child(key))
        segments.append(segment)
    domain = domains[control]
    if segments[0]['min'].value != domain.minimum or segments[-1]['max'].value != domain.maximum:
        fail(loc.child('segments'), 'model_domain', 'segments covering full control range')
    return {'input': control, 'output': model['output'], 'segments': tuple(segments)}


def _evaluate_piecewise(program, controls):
    p = program.instructions
    control = controls[p['input']]
    for i, segment in enumerate(p['segments']):
        if segment['min'].value <= control.value and (control.value < segment['max'].value or i == len(p['segments']) - 1):
            lines = [control.lineage, segment['min'].lineage, segment['max'].lineage]
            if segment['kind'] == 'linear':
                slope, intercept = segment['slope']['value'], segment['intercept']
                value = Fraction(intercept.value) + Fraction(slope.value) * Fraction(control.value)
                lines += [slope.lineage, intercept.lineage]
            else:
                start, end = segment['start'], segment['end']
                value = Fraction(start.value) + Fraction(end.value - start.value) * Fraction(control.value - segment['min'].value) / Fraction(segment['max'].value - segment['min'].value)
                lines += [start.lineage, end.lineage]
            return {p['output']: TypedValue(normalized(value, program.scale, program.location), program.definitions[p['output']].quantity, combine_lineage(*lines, step=f'model:piecewise:{i}'))}
    fail(program.location, 'model_domain', 'accepted segment')


def _compile_score(c, model, inherited, domains, loc):
    closed(model, ('kind', 'quantity', 'contributions', 'bands', 'format', 'round'), ('modelProvenance', 'label'), loc)
    q = c.quantity(model['quantity'], loc.child('quantity'))
    if c.quantities[q].dimension != 'score' or model['format'] != 'score' or model['round'] != 0:
        fail(loc, 'quantity', 'score quantity, score format and round 0')
    c.definition('score', model, loc, q)
    c.definitions['classification'] = OutputDefinition('text', 'Classification')
    contributions = array(model['contributions'], len(domains), len(domains), loc.child('contributions'))
    compiled, minimum, maximum = [], Decimal(0), Decimal(0)
    for i, (raw, domain) in enumerate(zip(contributions, domains.values())):
        here = loc.child('contributions').child(i)
        closed(raw, ('control', 'values'), loc=here)
        if raw['control'] != domain.id:
            fail(here.child('control'), 'model_domain', 'one contribution per control in declaration order')
        values = array(raw['values'], len(domain.values), len(domain.values), here.child('values'))
        rows = []
        for j, (row, accepted) in enumerate(zip(values, domain.values)):
            rowloc = here.child('values').child(j)
            closed(row, ('input', 'points'), ('provenance',), rowloc)
            selector = parse_decimal(row['input'], rowloc.child('input')) if domain.minimum is not None else identifier(row['input'], rowloc.child('input'))
            if selector != accepted:
                fail(rowloc.child('input'), 'model_domain', 'exact accepted values in control order', selector)
            points = integer(row['points'], -10**12, 10**12, rowloc.child('points'))
            rows.append((selector, c.leaf(points, q, row.get('provenance'), rowloc, inherited, 'Points')))
        compiled.append((domain.id, tuple(rows)))
        minimum += min(v.value for _, v in rows)
        maximum += max(v.value for _, v in rows)
    bands = []
    raw_bands = array(model['bands'], 1, 10001, loc.child('bands'))
    for i, band in enumerate(raw_bands):
        here = loc.child('bands').child(i)
        closed(band, ('id', 'min', 'max', 'label'), ('provenance',), here)
        a, b = (integer(band[key], -10**12, 10**12, here.child(key)) for key in ('min', 'max'))
        if a > b or (a == b and not (len(raw_bands) == 1 and minimum == maximum)) or (bands and bands[-1]['max'].value != a):
            fail(here, 'model_domain', 'contiguous ordered score bands')
        bands.append({'id': band['id'], 'label': plain(band['label'], here.child('label'), 32), 'min': c.leaf(a, q, band.get('provenance'), here.child('min'), inherited, 'Band start'), 'max': c.leaf(b, q, band.get('provenance'), here.child('max'), inherited, 'Band end')})
    distinct(raw_bands, 'id', loc.child('bands'))
    if bands[0]['min'].value != minimum or bands[-1]['max'].value != maximum:
        fail(loc.child('bands'), 'model_domain', 'bands covering full minimum/maximum total interval')
    return {'quantity': q, 'contributions': tuple(compiled), 'bands': tuple(bands)}


def _evaluate_score(program, state, controls):
    p = program.instructions
    values, lines = [], []
    for control, rows in p['contributions']:
        leaf = dict(rows)[state[control]]
        values.append(leaf.value)
        lines.append(leaf.lineage)
        if control in controls:
            lines.append(controls[control].lineage)
    total = parse_decimal(sum(values), program.location.child('model'))
    score = TypedValue(total, p['quantity'], combine_lineage(*lines, step='model:score_sum'))
    for i, band in enumerate(p['bands']):
        if band['min'].value <= total and (total < band['max'].value or i == len(p['bands']) - 1):
            return {'score': score, 'classification': TextValue(band['label'], combine_lineage(score.lineage, band['min'].lineage, band['max'].lineage, step='classification:' + band['id']))}
    fail(program.location, 'model_domain', 'score covered by classification band')


def _formula_text(program, controls):
    p, kind = program.instructions, program.kind
    labels = {c['id']: c['label'] for c in controls}
    if kind == 'linear':
        terms = [canonical_decimal(p['intercept'].value)]
        terms += [canonical_decimal(coefficient['value'].value) + ' × ' + labels[control] for control, coefficient in p['terms']]
        return [program.definitions[p['output']].label + ' = ' + ' + '.join(terms)]
    if kind == 'lookup':
        return [labels[p['input']] + ' ' + canonical_decimal(key) + ' → ' + canonical_decimal(value.value) for key, value in p['entries']]
    if kind == 'state_map':
        return [key + ' → ' + value for key, value in p['entries']]
    if kind == 'piecewise':
        formulas = []
        for segment in p['segments']:
            interval = canonical_decimal(segment['min'].value) + ' … ' + canonical_decimal(segment['max'].value)
            if segment['kind'] == 'linear':
                expression = canonical_decimal(segment['intercept'].value) + ' + ' + canonical_decimal(segment['slope']['value'].value) + ' × ' + labels[p['input']]
            else:
                expression = canonical_decimal(segment['start'].value) + ' → ' + canonical_decimal(segment['end'].value)
            formulas.append(interval + ': ' + expression)
        return formulas
    if kind == 'score_sum':
        return ['Score = ' + ' + '.join(labels[id] for id, _ in p['contributions'])]
    if kind == 'operation_graph':
        formulas = []
        for node in p['nodes']:
            op = node['op']
            if op == 'input':
                expression = labels[node['control']]
            elif op == 'constant':
                expression = canonical_decimal(node['constant'].value) + ' ' + program.quantities[node['quantity']].display
            elif op in ('add', 'subtract', 'multiply', 'divide'):
                expression = node['left'] + ' ' + {'add': '+', 'subtract': '−', 'multiply': '×', 'divide': '÷'}[op] + ' ' + node['right']
            elif op in ('min', 'max'):
                expression = op + '(' + ', '.join(node['inputs']) + ')'
            elif op == 'abs':
                expression = '|' + node['input'] + '|'
            else:
                expression = 'clamp(' + ', '.join(node[key] for key in ('input', 'min', 'max')) + ')'
            formulas.append(node['id'] + ' = ' + expression)
        return formulas
    return []
