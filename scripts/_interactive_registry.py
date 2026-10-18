"""Private scene compiler: registry. No I/O except explicit loaders/render validation."""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit
from urllib.parse import unquote
import re

if __package__:
    from .interactive_contract import (closed, fail, identifier, integer, parse_decimal)
else:
    from interactive_contract import (closed, fail, identifier, integer, parse_decimal)


def _safe_https_hostname(parsed):
    hostname = parsed.hostname
    if not hostname or not hostname.isascii():
        return False
    if parsed.netloc.startswith('['):
        if '%' in hostname:
            return False
        try:
            ipaddress.IPv6Address(hostname)
        except ValueError:
            return False
        return True
    if ':' in hostname:
        return False
    if re.fullmatch(r'[0-9.]+', hostname):
        try:
            return str(ipaddress.IPv4Address(hostname)) == hostname
        except ValueError:
            return False
    dns_hostname = hostname[:-1] if hostname.endswith('.') else hostname
    labels = dns_hostname.split('.')
    return bool(
        dns_hostname
        and len(hostname) <= 253
        and re.search(r'[A-Za-z]', labels[-1])
        and all(
            re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
            for label in labels
        )
    )


def safe_source_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        if re.search(r'%(?![0-9a-fA-F]{2})', value):
            return False
        decoded = unquote(value, errors='strict')
        if any(ord(ch) < 33 or ord(ch) == 127 or ch.isspace() or ch == '\\' for ch in value + decoded):
            return False
        parsed = urlsplit(value)
        if '?' in value or '#' in value or parsed.username is not None or parsed.password is not None:
            return False
        if parsed.scheme == 'https':
            parsed.port  # validate a supplied port, including range and syntax
            return _safe_https_hostname(parsed)
        if parsed.scheme != 'mailto' or parsed.netloc or '%' in parsed.path:
            return False
        # Deliberately bounded bare addr-spec: no display name, quoted local
        # part, headers, multiple recipients, or percent-encoded structure.
        local, separator, domain = parsed.path.partition('@')
        return bool(separator and len(local) <= 64 and len(domain) <= 253
                    and re.fullmatch(r"[A-Za-z0-9!#$&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$&'*+/=?^_`{|}~-]+)*", local)
                    and re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+', domain))
    except (ValueError, UnicodeError):
        return False


def compile_registries(scene, slide_ids):
    raw, loc = scene.data, scene.location
    targets = {'evidence:open': {'kind': 'evidence'}, 'evidence:close': {'kind': 'evidence'}, 'static:toggle': {'kind': 'static'}}
    controls = {c['id']: c for c in raw.get('controls', [])}
    domains = {d.id: d for d in scene.domains}
    for id in controls:
        targets['control:' + id] = {'kind': 'control', 'id': id}
    panels = raw.get('panels', raw.get('items', []))
    for panel in panels:
        targets['panel:' + panel['id']] = {'kind': 'panel', 'id': panel['id']}
        targets['panel:' + panel['id'] + ':close'] = {'kind': 'panelClose', 'id': panel['id']}
    for source in raw.get('sources', []):
        if safe_source_url(source.get('url')):
            targets['source:' + source['id']] = {'kind': 'source', 'id': source['id']}
    steps, seen, waits = [], set(), 0
    open_panel = raw['initialState'].get('panel')
    evidence_open = raw['initialState'].get('evidence', 'closed') != 'closed'
    terminal_goto = False
    shapes = {'set': ('control', 'value'), 'select': ('control', 'value'), 'openEvidence': (), 'closeEvidence': (), 'openPanel': ('panel',), 'closePanel': ('panel',), 'goto': ('slideId',), 'wait': ('ms',)}
    for i, raw_step in enumerate(raw.get('demo', [])):
        here = loc.child('demo').child(i)
        action = raw_step.get('action') if isinstance(raw_step, dict) else None
        if not isinstance(action, str) or action not in shapes:
            fail(here.child('action'), 'demo_target', 'allowlisted demo action')
        closed(raw_step, ('stepKey', 'action') + shapes[action], loc=here)
        if terminal_goto:
            fail(here.child('action'), 'demo_target', 'goto as the terminal demo action')
        if evidence_open and action not in ('closeEvidence', 'wait'):
            fail(here.child('action'), 'demo_target', 'close evidence before another owner action')
        if action == 'closeEvidence' and not evidence_open:
            fail(here.child('action'), 'demo_target', 'visible evidence close target')
        step_key = identifier(raw_step['stepKey'], here.child('stepKey'))
        if step_key in seen:
            fail(here.child('stepKey'), 'duplicate_id', 'unique stepKey')
        seen.add(step_key)
        reducer, target = {'type': action}, None
        if action in ('set', 'select'):
            id = identifier(raw_step['control'], here.child('control'))
            if id not in controls or (controls[id]['kind'] == 'range') != (action == 'set'):
                fail(here.child('control'), 'demo_target', 'control of matching kind')
            value = parse_decimal(raw_step['value'], here.child('value')) if action == 'set' else identifier(raw_step['value'], here.child('value'))
            if value not in domains[id].values:
                fail(here.child('value'), 'demo_target', 'accepted control value')
            reducer.update(control=id, value=value)
            target = 'control:' + id
        elif action in ('openPanel', 'closePanel'):
            id = raw_step['panel']
            if id not in [p['id'] for p in panels] or (action == 'closePanel' and open_panel != id):
                fail(here.child('panel'), 'demo_target', 'declared panel, currently open when closing')
            if action == 'closePanel' and raw['type'] == 'accordion' and not raw['allowNone']:
                fail(here, 'demo_target', 'accordion allowNone to close last panel')
            target = 'panel:' + id + (':close' if action == 'closePanel' else '')
            open_panel = id if action == 'openPanel' else None
            reducer['panel'] = id
        elif action == 'goto':
            identifier(raw_step['slideId'], here.child('slideId'))
            if raw_step['slideId'] not in slide_ids:
                fail(here.child('slideId'), 'demo_target', 'manifest slide ID')
            reducer['slideId'] = raw_step['slideId']
            terminal_goto = True
        elif action == 'wait':
            reducer['ms'] = integer(raw_step['ms'], 0, 5000, here.child('ms'))
            waits += reducer['ms']
            if waits > 30000:
                fail(here.child('ms'), 'limit', '<=30000 ms waits per scene')
        else:
            target = 'evidence:open' if action == 'openEvidence' else 'evidence:close'
            evidence_open = action == 'openEvidence'
        step = {'stepKey': step_key, 'action': reducer}
        if target:
            if target not in targets:
                fail(here, 'demo_target', 'registered derived target')
            step['targetKey'] = target
        steps.append(step)
    return targets, tuple(steps)
