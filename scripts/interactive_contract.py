"""Exact, standard-library-only analytical contracts. No rendering or I/O."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fractions import Fraction
from itertools import product
from collections.abc import Mapping
import re

LIMIT = Decimal('1e12')
ID = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
RESERVED = ('score', 'classification', 'decisionStatus', 'recommendation')
UNSAFE_IDS = frozenset(('__proto__', 'prototype', 'constructor'))


@dataclass(frozen=True)
class Location:
    file: str = '<scene>'
    pointer: str = ''

    def child(self, key):
        return Location(self.file, self.pointer + '/' + str(key).replace('~', '~0').replace('/', '~1'))


class SceneValidationError(ValueError):
    def __init__(self, location, code, expected, actual=None, *, related_locations=(), state=None):
        self.location, self.code, self.expected = location, code, expected
        # Do not echo evidence, URLs, or an entire object into diagnostics.
        self.actual_summary = type(actual).__name__ if isinstance(actual, (dict, list)) else repr(actual)[:120]
        if isinstance(actual, str) and '://' in actual:
            self.actual_summary = '<URL omitted>'
        self.related_locations, self.state = tuple(related_locations), state
        super().__init__(f'{location.file}:{location.pointer} [{code}]: expected {expected}; found {self.actual_summary}')


def fail(loc, code, expected, actual=None):
    raise SceneValidationError(loc, code, expected, actual)


def closed(value, required, optional=(), loc=Location()):
    if not isinstance(value, dict):
        fail(loc, 'type', 'object', value)
    for key in value:
        if key not in set(required) | set(optional):
            fail(loc.child(key), 'unknown_key', 'one of ' + ', '.join(sorted(set(required) | set(optional))), key)
    for key in required:
        if key not in value:
            fail(loc.child(key), 'shape', 'required field')
    return value


def plain(value, loc=Location(), maximum=500, *, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        fail(loc, 'type', 'nonempty Unicode scalar text', value)
    if len(value) > maximum:
        fail(loc, 'limit', f'at most {maximum} Unicode scalars', value)
    return value


def identifier(value, loc=Location()):
    if not isinstance(value, str) or not ID.fullmatch(value) or value in UNSAFE_IDS:
        fail(loc, 'shape', 'lowercase ID matching ' + ID.pattern, value)
    return value


def validate_interactive_slide_ids(values, location=Location('<manifest>', '/slides')):
    """Interactive-only ID boundary; classic manifest normalization is unchanged."""
    if not isinstance(values, (list, tuple, set, frozenset)):
        fail(location, 'type', 'collection of interactive slide IDs', values)
    if isinstance(values, (set, frozenset)):
        values = sorted(values, key=repr)
    result, seen = [], set()
    for index, value in enumerate(values):
        id = identifier(value, location.child(index))
        if id in seen:
            fail(location.child(index), 'duplicate_id', 'unique interactive slide ID', id)
        seen.add(id)
        result.append(id)
    return tuple(result)


def integer(value, lo, hi, loc=Location()):
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)) or (isinstance(value, Decimal) and not value.is_finite()):
        fail(loc, 'type', 'integer', value)
    if not lo <= value <= hi:
        fail(loc, 'limit', f'integer {lo} through {hi}', value)
    if value != int(value):
        fail(loc, 'type', 'integer', value)
    return int(value)


def parse_decimal(value, location=Location()):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        fail(location, 'numeric', 'finite JSON number, not string or boolean', value)
    result = Decimal(str(value)) if not isinstance(value, Decimal) else value
    if not result.is_finite() or abs(result) > LIMIT or result.as_tuple().exponent < -6:
        fail(location, 'numeric', 'finite number with <=6 fractional digits and absolute value <=1e12', value)
    return result


def canonical_decimal(value):
    if not value:
        return '0'
    text = format(value, 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def round_scaled(numerator, denominator):
    if not denominator:
        fail(Location(), 'model_domain', 'nonzero denominator', denominator)
    sign = -1 if (numerator < 0) != (denominator < 0) else 1
    quotient, remainder = divmod(abs(numerator), abs(denominator))
    return sign * (quotient + (2 * remainder >= abs(denominator)))


def normalized(value, scale, loc=Location()):
    fraction = Fraction(value) * 10 ** scale
    result = Decimal(round_scaled(fraction.numerator, fraction.denominator)).scaleb(-scale)
    return parse_decimal(result, loc)


@dataclass(frozen=True)
class ControlDomain:
    id: str
    values: tuple
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    step: Decimal | None = None

    @classmethod
    def range(cls, id, minimum, maximum, step, loc=Location()):
        a, b, s = (parse_decimal(x, loc) for x in (minimum, maximum, step))
        if a >= b or s <= 0 or (b - a) % s:
            fail(loc, 'state', 'min < max, step >0, and exactly reachable maximum')
        count = int((b - a) / s) + 1
        if count > 10001:
            fail(loc, 'limit', 'at most 10001 range positions', count)
        return cls(id, tuple(a + i * s for i in range(count)), a, b, s)


def snap_range(raw, domain):
    value = parse_decimal(raw)
    steps = Fraction(value - domain.minimum) / Fraction(domain.step)
    snapped = domain.minimum + round_scaled(steps.numerator, steps.denominator) * domain.step
    return min(domain.maximum, max(domain.minimum, snapped))


def iter_reachable_states(domains):
    for values in product(*(domain.values for domain in domains)):
        yield dict(zip((domain.id for domain in domains), values))


# ISO 4217 alphabetic codes, bundled so compilation does not depend on a service.
ISO_CURRENCIES = frozenset('AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA XBB XBC XBD XCD XCG XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG'.split())
BASE_EXPONENTS = {'currency': (1, 0, 0), 'time': (0, 1, 0), 'count': (0, 0, 1), 'scalar': (0, 0, 0), 'ratio': (0, 0, 0), 'score': (0, 0, 0)}


@dataclass(frozen=True)
class Quantity:
    id: str
    dimension: str
    unit: str
    exponents: tuple[int, int, int]
    unit_factors: tuple[tuple[str, int], ...]
    currency: str | None
    display: str


def compile_quantities(raw, location=Location()):
    if not isinstance(raw, dict):
        fail(location, 'type', 'quantity registry object', raw)
    registry, units = {}, {}
    for key, value in raw.items():
        loc = location.child(key)
        identifier(key, loc)
        closed(value, ('dimension', 'unit', 'display'), ('currency', 'exponents', 'unitFactors'), loc)
        dimension = value['dimension']
        if not isinstance(dimension, str) or (dimension not in BASE_EXPONENTS and dimension != 'derived'):
            fail(loc.child('dimension'), 'quantity', 'base dimension or derived', dimension)
        unit = value['unit']
        if not isinstance(unit, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', unit) or unit in UNSAFE_IDS:
            fail(loc.child('unit'), 'quantity', 'stable storage unit ID', unit)
        display = plain(value['display'], loc.child('display'), 12)
        if dimension == 'derived':
            closed(value.get('exponents'), ('currency', 'time', 'count'), loc=loc.child('exponents'))
            exp = tuple(integer(value['exponents'][d], -2, 2, loc.child('exponents').child(d)) for d in ('currency', 'time', 'count'))
            factors = value.get('unitFactors')
            if not isinstance(factors, dict):
                fail(loc.child('unitFactors'), 'quantity', 'base-unit factor object', factors)
            factors = tuple(sorted((u, integer(e, -2, 2, loc.child('unitFactors').child(u))) for u, e in factors.items()))
            if any(not e for _, e in factors):
                fail(loc.child('unitFactors'), 'quantity', 'nonzero unit exponents')
        else:
            if 'exponents' in value or 'unitFactors' in value:
                fail(loc, 'quantity', 'base quantity without derived fields')
            exp = BASE_EXPONENTS[dimension]
            factors = () if (dimension, unit) in (('scalar', 'one'), ('ratio', 'fraction')) else ((unit, 1),)
        currency = value.get('currency')
        if exp[0]:
            if not isinstance(currency, str) or currency not in ISO_CURRENCIES:
                fail(loc.child('currency'), 'quantity', 'bundled ISO 4217 code', currency)
        elif currency is not None:
            fail(loc.child('currency'), 'quantity', 'no currency on zero currency exponent', currency)
        q = Quantity(key, dimension, unit, exp, factors, currency, display)
        signature = (dimension, exp, factors, currency)
        if unit in units and units[unit][0] != signature:
            fail(loc.child('unit'), 'quantity', 'one meaning per storage unit', unit)
        units[unit] = (signature, q)
        registry[key] = q
    for q in registry.values():
        if q.dimension != 'derived':
            continue
        exponents, currencies = [0, 0, 0], set()
        for unit, exponent in q.unit_factors:
            base = units.get(unit, (None, None))[1]
            if base is None or base.dimension in ('derived', 'score'):
                fail(location.child(q.id).child('unitFactors'), 'quantity', 'declared composable base units', unit)
            if not base.unit_factors:
                fail(location.child(q.id).child('unitFactors'), 'quantity', 'identity factors omitted', unit)
            exponents = [a + b * exponent for a, b in zip(exponents, base.exponents)]
            if base.currency:
                currencies.add(base.currency)
        if tuple(exponents) != q.exponents or len(currencies) > 1 or (q.currency and currencies != {q.currency}):
            fail(location.child(q.id), 'quantity', 'factors reproducing declared dimensions and currency')
    return registry


def require_same_quantity(left, right, location=Location()):
    a, b = getattr(left, 'id', left), getattr(right, 'id', right)
    if a != b:
        fail(location, 'quantity', f'exact quantity {a}', b)


def infer_product_quantity(left, right, result, operation, location=Location()):
    if 'score' in (left.dimension, right.dimension, result.dimension):
        fail(location, 'quantity', 'no score multiplication or division')
    if left.currency and right.currency and left.currency != right.currency:
        fail(location, 'quantity', 'no mixed currencies even before cancellation')
    sign = 1 if operation == 'multiply' else -1
    exp = tuple(a + sign * b for a, b in zip(left.exponents, right.exponents))
    factors = dict(left.unit_factors)
    for key, exponent in right.unit_factors:
        factors[key] = factors.get(key, 0) + sign * exponent
    factors = tuple(sorted((key, value) for key, value in factors.items() if value))
    currency = (left.currency or right.currency) if exp[0] else None
    if (exp, factors, currency) != (result.exponents, result.unit_factors, result.currency):
        fail(location, 'quantity', 'exact dimension, storage-factor and currency algebra')
    return result


BASIS_ORDER = ('illustrative', 'assumed', 'estimated', 'measured')


@dataclass(frozen=True)
class Lineage:
    derived: bool = False
    bases: tuple = ()
    source_refs: tuple = ()
    assumption_refs: tuple = ()
    normalizations: tuple = ()
    leaves: tuple = ()
    steps: tuple = ()
    source_order: tuple = field(default=(), repr=False, compare=False)
    assumption_order: tuple = field(default=(), repr=False, compare=False)

    @property
    def badge(self):
        return next((b for b in BASIS_ORDER if b in self.bases), '')

    def as_dict(self):
        return {'derived': self.derived, 'badge': self.badge, 'bases': list(self.bases), 'sourceRefs': list(self.source_refs), 'assumptionRefs': list(self.assumption_refs), 'normalizations': [dict(n) for n in self.normalizations], 'leaves': list(self.leaves), 'steps': list(self.steps)}


def unique(values):
    return tuple(dict.fromkeys(values))


def combine_lineage(*lineages, step=None, derived=True):
    def union(attr):
        return unique(value for line in lineages for value in getattr(line, attr))
    source_order, assumption_order = union('source_order'), union('assumption_order')
    def ordered(refs, order):
        return tuple(ref for ref in order if ref in refs) + tuple(ref for ref in refs if ref not in order)
    leaves = union('leaves')
    if all(re.fullmatch(r'leaf-[0-9]+', leaf) for leaf in leaves):
        leaves = tuple(sorted(leaves, key=lambda leaf: int(leaf.split('-')[1])))
    return Lineage(derived or any(l.derived for l in lineages), tuple(b for b in BASIS_ORDER if b in union('bases')), ordered(union('source_refs'), source_order), ordered(union('assumption_refs'), assumption_order), union('normalizations'), leaves, unique((*union('steps'), *((step,) if step else ()))), source_order, assumption_order)


def compile_provenance(raw, evidence, location=Location(), inherited=None):
    if raw is None:
        if inherited is None:
            fail(location, 'provenance', 'explicit provenance or simple modelProvenance')
        return inherited
    closed(raw, ('basis',), ('sourceRefs', 'assumptionRefs', 'normalization'), location)
    basis = raw['basis']
    if basis not in BASIS_ORDER:
        fail(location.child('basis'), 'provenance', 'measured, estimated, assumed or illustrative', basis)
    refs = []
    for field, registry in [('sourceRefs', 'sources'), ('assumptionRefs', 'assumptions')]:
        values = raw.get(field, [])
        declared = [entry['id'] for entry in evidence.get(registry, [])]
        if not isinstance(values, list) or (field in raw and not values) or any(not isinstance(v, str) for v in values) or len(set(values)) != len(values) or any(v not in declared for v in values):
            fail(location.child(field), 'reference', 'nonempty unique declared evidence IDs', values)
        refs.append(tuple(v for v in declared if v in values))
    if inherited and any(BASIS_ORDER.index(basis) > BASIS_ORDER.index(b) for b in inherited.bases):
        fail(location.child('basis'), 'provenance', 'no upgrade of inherited evidence basis', basis)
    normalized_notes = ()
    if 'normalization' in raw:
        note = closed(raw['normalization'], ('note', 'fromUnit', 'toUnit'), loc=location.child('normalization'))
        normalized_notes = (tuple((k, plain(note[k], location.child('normalization').child(k))) for k in ('note', 'fromUnit', 'toUnit')),)
    line = Lineage(bool(normalized_notes), (basis,), refs[0], refs[1], normalized_notes)
    if inherited:
        line = combine_lineage(inherited, line, derived=False)
    if (basis == 'measured' and not line.source_refs) or (basis == 'estimated' and not (line.source_refs or line.assumption_refs)) or (basis in ('assumed', 'illustrative') and not line.assumption_refs):
        fail(location, 'provenance', 'source for measured; source/assumption for estimated; assumption for assumed/illustrative')
    # Canonical reference order is declaration order, even after inheritance.
    return Lineage(line.derived, line.bases, tuple(e['id'] for e in evidence.get('sources', []) if e['id'] in line.source_refs), tuple(e['id'] for e in evidence.get('assumptions', []) if e['id'] in line.assumption_refs), line.normalizations, line.leaves, line.steps, tuple(e['id'] for e in evidence.get('sources', [])), tuple(e['id'] for e in evidence.get('assumptions', [])))


@dataclass(frozen=True)
class TypedValue:
    value: Decimal
    quantity: str
    lineage: Lineage


@dataclass(frozen=True)
class TextValue:
    value: str
    lineage: Lineage


@dataclass(frozen=True)
class OutputDefinition:
    kind: str
    label: str
    quantity: str | None = None
    format: str | None = None
    round: int | None = None


@dataclass(frozen=True)
class EvidenceProvenance:
    """Validated authored provenance, distinct from calculated lineage."""
    basis: str
    source_refs: tuple = ()
    assumption_refs: tuple = ()
    normalization: tuple = ()

    def as_dict(self):
        result = {'basis': self.basis}
        if self.source_refs: result['sourceRefs'] = list(self.source_refs)
        if self.assumption_refs: result['assumptionRefs'] = list(self.assumption_refs)
        if self.normalization: result['normalization'] = dict(self.normalization)
        return result


@dataclass(frozen=True)
class DecisionSpec:
    id: str
    metric: str
    operator: str
    threshold: TypedValue
    met_status: str
    met_recommendation: str
    not_met_status: str
    not_met_recommendation: str
    threshold_provenance: EvidenceProvenance | None = None


@dataclass(frozen=True)
class DecisionResult:
    outcome: str
    distance: Decimal
    quantity: str
    status: str
    recommendation: str
    lineage: Lineage


def evaluate_decision(spec, outputs, controls):
    prefix, key = spec.metric.split(':')
    metric = (outputs if prefix == 'output' else controls)[key]
    require_same_quantity(metric.quantity, spec.threshold.quantity)
    distance = metric.value - spec.threshold.value
    met = {'lt': distance < 0, 'lte': distance <= 0, 'gt': distance > 0, 'gte': distance >= 0}[spec.operator]
    return DecisionResult('met' if met else 'notMet', distance, metric.quantity, spec.met_status if met else spec.not_met_status, spec.met_recommendation if met else spec.not_met_recommendation, combine_lineage(metric.lineage, spec.threshold.lineage, step='decision:' + spec.id))


@dataclass(frozen=True)
class Witness:
    state: tuple
    distance: Decimal
    outcome: str


@dataclass(frozen=True)
class ContractAudit:
    accepted_state_count: int
    witnesses: dict
    missing_outcomes: tuple
    classifications: dict = field(default_factory=dict)
    boundaries: tuple = ()


def audit_contract(domains, evaluator, decision=None, boundary_requests=()):
    witnesses, classes, boundaries, count = {}, {}, {}, 0
    for state in iter_reachable_states(domains):
        count += 1
        if count > 65536:
            fail(Location(), 'limit', 'at most 65536 reachable states')
        try:
            evaluation = evaluator(state)
            outputs = evaluation.get('outputs', evaluation)
            if decision:
                result = evaluate_decision(decision, outputs, evaluation.get('controls', {}))
                witness = Witness(tuple(state.items()), result.distance, result.outcome)
                previous = witnesses.get(result.outcome)
                if previous is None or abs(result.distance) < abs(previous.distance):
                    witnesses[result.outcome] = witness
                if result.distance == 0:
                    witnesses.setdefault('exact', witness)
            if 'classification' in outputs:
                classes.setdefault(outputs['classification'].value, tuple(state.items()))
            for control, value in boundary_requests:
                current = outputs[control.split(':', 1)[1]].value if control.startswith('output:') else state[control]
                side = 'exact' if current == value else ('below' if current < value else 'above')
                key = (control, value, side)
                distance = abs(current - value)
                if key not in boundaries or distance < boundaries[key][0]:
                    boundaries[key] = (distance, tuple(state.items()))
        except SceneValidationError as error:
            if error.state is None:
                error.state = dict(state)
            raise
    missing = tuple({'outcome': key, 'reason': 'unreachable_within_declared_domain'} for key in ('met', 'notMet') if decision and key not in witnesses)
    return ContractAudit(count, witnesses, missing, classes, tuple((key, state) for key, (_, state) in boundaries.items()))


def format_value(value, quantity, precision, locale='en', *, delta=False):
    """Bundled en-US/ja-JP formatting. Stored percentages are never rescaled."""
    if locale not in ('en', 'ja'):
        fail(Location(), 'shape', 'en or ja locale', locale)
    with localcontext() as context:
        context.prec = 40
        rounded = value.quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP)
    number = format(abs(rounded), f',.{precision}f')
    sign = '−' if rounded < 0 else '+' if delta and rounded > 0 else ''
    unit = 'pp' if delta and quantity.unit in ('percent', 'percentage_point') else quantity.display
    if unit.startswith(('$', '€', '£', '¥', '￥')):
        # Explicit display labels such as $m retain prefix/suffix semantics.
        number = unit[0] + number + unit[1:]
    else:
        number += ('' if unit == '%' else ' ') + unit
    return sign + number


def fit_narration(mandatory, optional=(), location=Location()):
    mandatory = list(mandatory)
    optional = list(optional)
    while True:
        sentence = '; '.join(part for part in mandatory + optional if part)
        if len(sentence) <= 160:
            return sentence
        if not optional:
            fail(location, 'narration_length', 'mandatory narration <=160 Unicode scalars', len(sentence))
        optional.pop()


NARRATION_TEXT = {
    'en': {'baseline': 'Baseline', 'reset': 'Reset to baseline', 'restore': 'Scenario restored: {count} inputs changed', 'closed': 'Evidence closed', 'sources': 'Sources open', 'assumptions': 'Assumptions open', 'both': 'Sources and assumptions open', 'openPanel': '{label} open', 'closePanel': '{label} closed', 'state': '{label}: {option}; {moved} moved, {changed} changed, {removed} removed'},
    'ja': {'baseline': '初期値', 'reset': '初期値に戻しました', 'restore': 'シナリオを復元：入力{count}件を変更', 'closed': '根拠を閉じました', 'sources': '出典を表示', 'assumptions': '仮定を表示', 'both': '出典と仮定を表示', 'openPanel': '{label}を開きました', 'closePanel': '{label}を閉じました', 'state': '{label}：{option}；移動{moved}件、変更{changed}件、除外{removed}件'},
}


def compile_narration(scene_kind, evaluations, definitions, locale):
    """Validate a stream of semantic variants; retain templates, not state atlases.

    Each evaluation is a tuple (semantic_key, mandatory_parts, optional_parts).
    Callers may feed both locales through the same exhaustive evaluation pass.
    """
    if locale not in NARRATION_TEXT:
        fail(Location(), 'shape', 'en or ja locale', locale)
    count = 0
    for key, mandatory, optional in evaluations:
        fit_narration(mandatory, optional)
        count += 1
    return {'locale': locale, 'templates': dict(NARRATION_TEXT[locale]), 'validatedVariants': count}
