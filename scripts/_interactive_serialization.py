"""Private scene compiler: serialization. No I/O except explicit loaders/render validation."""
from __future__ import annotations

from decimal import Decimal

if __package__:
    from .interactive_contract import (DecisionSpec, Lineage, Location, OutputDefinition, TextValue, TypedValue, canonical_decimal)
else:
    from interactive_contract import (DecisionSpec, Lineage, Location, OutputDefinition, TextValue, TypedValue, canonical_decimal)


def serialize_compiled_scene(compiled):
    from dataclasses import fields, is_dataclass
    if __package__:
        from .interactive_contract import Quantity
    else:
        from interactive_contract import Quantity
    def convert(value):
        if isinstance(value, Decimal): return canonical_decimal(value)
        if isinstance(value, Lineage): return value.as_dict()
        if isinstance(value, TypedValue): return {'kind': 'numeric', 'value': canonical_decimal(value.value), 'quantity': value.quantity, 'lineage': value.lineage.as_dict()}
        if isinstance(value, TextValue): return {'kind': 'text', 'value': value.value, 'lineage': value.lineage.as_dict()}
        if isinstance(value, OutputDefinition):
            return {k: v for k, v in {'kind': value.kind, 'label': value.label, 'quantity': value.quantity, 'format': value.format, 'round': value.round}.items() if v is not None}
        if isinstance(value, Quantity):
            return {'dimension': value.dimension, 'unit': value.unit, 'exponents': dict(zip(('currency', 'time', 'count'), value.exponents)), 'unitFactors': dict(value.unit_factors), 'display': value.display, **({'currency': value.currency} if value.currency else {})}
        if isinstance(value, DecisionSpec):
            if value.threshold_provenance is None:
                raise TypeError('Decision serialization requires validated threshold provenance')
            threshold = {'value': canonical_decimal(value.threshold.value), 'quantity': value.threshold.quantity, 'provenance': value.threshold_provenance.as_dict()}
            return {'id': value.id, 'metric': {'ref': value.metric}, 'operator': value.operator, 'threshold': threshold, 'whenMet': {'status': value.met_status, 'recommendation': value.met_recommendation}, 'whenNotMet': {'status': value.not_met_status, 'recommendation': value.not_met_recommendation}}
        if isinstance(value, Location):
            raise TypeError('Author locations cannot be serialized into audience data')
        if is_dataclass(value): return {f.name: convert(getattr(value, f.name)) for f in fields(value)}
        if isinstance(value, dict): return {k: convert(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)): return [convert(v) for v in value]
        return value
    return convert(compiled)
