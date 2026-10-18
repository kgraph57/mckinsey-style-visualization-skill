"""Private scene compiler: graph. No I/O except explicit loaders/render validation."""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

if __package__:
    from .interactive_contract import (RESERVED, TypedValue, closed, combine_lineage, fail, identifier, infer_product_quantity, normalized, require_same_quantity)
    from ._interactive_shape import (array)
else:
    from interactive_contract import (RESERVED, TypedValue, closed, combine_lineage, fail, identifier, infer_product_quantity, normalized, require_same_quantity)
    from _interactive_shape import (array)


GRAPH_FIELDS = {'input': ('control',), 'constant': ('value', 'provenance'), 'add': ('left', 'right'), 'subtract': ('left', 'right'), 'multiply': ('left', 'right'), 'divide': ('left', 'right'), 'min': ('inputs',), 'max': ('inputs',), 'abs': ('input',), 'clamp': ('input', 'min', 'max')}


def _outward(value, scale, upper):
    value = Fraction(value) * 10 ** scale
    integer_value = -((-value.numerator) // value.denominator) if upper else value.numerator // value.denominator
    return Decimal(integer_value).scaleb(-scale)


def _compile_graph(c, model, domains, loc):
    closed(model, ('kind', 'nodes', 'outputs'), loc=loc)
    nodes, intervals, depths, dependencies = {}, {}, {}, {}
    for i, raw in enumerate(array(model['nodes'], 1, 32, loc.child('nodes'))):
        here = loc.child('nodes').child(i)
        op = raw.get('op') if isinstance(raw, dict) else None
        if not isinstance(op, str) or op not in GRAPH_FIELDS:
            fail(here.child('op'), 'shape', 'allowlisted graph operator', op)
        closed(raw, ('id', 'op', 'quantity') + GRAPH_FIELDS[op], loc=here)
        id, q = identifier(raw['id'], here.child('id')), c.quantity(raw['quantity'], here.child('quantity'))
        if id in nodes:
            fail(here.child('id'), 'duplicate_id', 'unique node ID', id)
        node, refs = {'id': id, 'op': op, 'quantity': q}, []
        if op == 'input':
            key = identifier(raw['control'], here.child('control'))
            if key not in c.controls:
                fail(here.child('control'), 'reference', 'numeric control')
            require_same_quantity(q, c.controls[key].quantity, here.child('quantity'))
            node['control'] = key
            interval = (domains[key].minimum, domains[key].maximum)
        elif op == 'constant':
            node['constant'] = c.leaf(raw['value'], q, raw['provenance'], here, label='Constant')
            interval = (node['constant'].value,) * 2
        else:
            if op in ('min', 'max'):
                refs = array(raw['inputs'], 2, 32, here.child('inputs'))
                ref_locations = [here.child('inputs').child(index) for index in range(len(refs))]
                for ref, location in zip(refs, ref_locations):
                    identifier(ref, location)
                if len(set(refs)) != len(refs):
                    fail(here.child('inputs'), 'reference', 'ordered unique node IDs')
                node['inputs'] = tuple(refs)
            else:
                refs = [raw[k] for k in GRAPH_FIELDS[op]]
                ref_locations = [here.child(key) for key in GRAPH_FIELDS[op]]
                node.update({k: raw[k] for k in GRAPH_FIELDS[op]})
            for ref, location in zip(refs, ref_locations):
                identifier(ref, location)
                if ref not in nodes:
                    fail(location, 'reference', 'earlier graph node ID', ref)
            if op in ('multiply', 'divide'):
                infer_product_quantity(c.quantities[nodes[refs[0]]['quantity']], c.quantities[nodes[refs[1]]['quantity']], c.quantities[q], op, here)
            else:
                for ref in refs:
                    require_same_quantity(q, nodes[ref]['quantity'], here)
            ranges = [intervals[r] for r in refs]
            if op == 'add':
                interval = (ranges[0][0] + ranges[1][0], ranges[0][1] + ranges[1][1])
            elif op == 'subtract':
                interval = (ranges[0][0] - ranges[1][1], ranges[0][1] - ranges[1][0])
            elif op in ('multiply', 'divide'):
                if op == 'divide' and ranges[1][0] <= 0 <= ranges[1][1]:
                    fail(here.child('right'), 'model_domain', 'denominator interval strictly above or below zero')
                candidates = [Fraction(a) * Fraction(b) if op == 'multiply' else Fraction(a) / Fraction(b) for a in ranges[0] for b in ranges[1]]
                interval = (_outward(min(candidates), c.scene.scale, False), _outward(max(candidates), c.scene.scale, True))
            elif op in ('min', 'max'):
                fn = min if op == 'min' else max
                interval = (fn(r[0] for r in ranges), fn(r[1] for r in ranges))
            elif op == 'abs':
                a, b = ranges[0]
                interval = (Decimal(0) if a <= 0 <= b else min(abs(a), abs(b)), max(abs(a), abs(b)))
            else:
                if any(nodes[r]['op'] != 'constant' for r in refs[1:]) or ranges[1][0] > ranges[2][0]:
                    fail(here, 'model_domain', 'ordered typed constant clamp bounds')
                a, b = ranges[1][0], ranges[2][0]
                interval = (min(b, max(a, ranges[0][0])), min(b, max(a, ranges[0][1])))
        depth = 1 + max((depths[r] for r in refs), default=0)
        if depth > 8:
            fail(here, 'limit', 'graph depth <=8')
        nodes[id], intervals[id], depths[id], dependencies[id] = node, interval, depth, tuple(refs)
    outputs = model['outputs']
    if not isinstance(outputs, dict) or not 1 <= len(outputs) <= 4:
        fail(loc.child('outputs'), 'limit', 'one through four output definitions')
    exposed = {}
    for id, raw in outputs.items():
        here = loc.child('outputs').child(id)
        if id in RESERVED:
            fail(here, 'duplicate_id', 'nonreserved output ID', id)
        closed(raw, ('node', 'quantity', 'format', 'round'), ('label',), here)
        identifier(raw['node'], here.child('node'))
        if raw['node'] not in nodes:
            fail(here.child('node'), 'reference', 'declared node')
        require_same_quantity(raw['quantity'], nodes[raw['node']]['quantity'], here)
        c.definition(id, raw, here)
        exposed[id] = raw['node']
    used = set()
    def visit(id):
        if id not in used:
            used.add(id)
            for dep in dependencies[id]:
                visit(dep)
    for id in exposed.values():
        visit(id)
    if used != set(nodes):
        fail(loc.child('nodes'), 'model_domain', 'every node reaches an exposed output')
    return {'nodes': tuple(nodes.values()), 'outputs': exposed}


def _evaluate_graph(program, controls):
    values = {}
    for node in program.instructions['nodes']:
        op = node['op']
        if op == 'input':
            result = controls[node['control']]
        elif op == 'constant':
            result = node['constant']
        else:
            keys = node['inputs'] if op in ('min', 'max') else tuple(node[k] for k in GRAPH_FIELDS[op])
            operands = [values[key] for key in keys]
            numbers = [v.value for v in operands]
            a = numbers[0]
            if op == 'add': value = a + numbers[1]
            elif op == 'subtract': value = a - numbers[1]
            elif op == 'multiply': value = Fraction(a) * Fraction(numbers[1])
            elif op == 'divide':
                if not numbers[1]:
                    fail(program.location, 'model_domain', 'nonzero normalized denominator')
                value = Fraction(a) / Fraction(numbers[1])
            elif op == 'min': value = min(numbers)
            elif op == 'max': value = max(numbers)
            elif op == 'abs': value = abs(a)
            else: value = min(numbers[2], max(numbers[1], a))
            result = TypedValue(normalized(value, program.scale, program.location), node['quantity'], combine_lineage(*(v.lineage for v in operands), step='node:' + node['id']))
        values[node['id']] = result
    return {id: values[node] for id, node in program.instructions['outputs'].items()}
