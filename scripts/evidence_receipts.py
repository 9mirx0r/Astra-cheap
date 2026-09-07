"""Content-addressed receipt links. Hash integrity is not runtime authentication.

Source IDs must identify atomic observations in the upstream adapter. This module
does not infer identities from equal token counts or validate capsule freshness.
"""
import hashlib
import json

FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def receipt(source_id, usage, requested_model):
    if not isinstance(source_id, str) or not 0 < len(source_id) <= 200:
        raise ValueError('bounded source event identity required')
    if not isinstance(requested_model, str) or not 0 < len(requested_model) <= 200:
        raise ValueError('bounded requested model required')
    if not isinstance(usage, dict) or set(usage) - set(FIELDS):
        raise ValueError('unsupported usage fields')
    for value in usage.values():
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('usage must be nonnegative integers or unknown')
    for sub, total in [('cached_input_tokens', 'input_tokens'),
                       ('reasoning_output_tokens', 'output_tokens')]:
        if usage.get(sub) is not None and (usage.get(total) is None or usage[sub] > usage[total]):
            raise ValueError('invalid usage subset')
    body = {'source_id': source_id, 'usage': {k: usage.get(k) for k in FIELDS},
            'requested_model': requested_model, 'observed_model': None,
            'provenance': 'caller_supplied_unverified'}
    return dict(body, receipt_id=digest(body))


def link(capsule, receipts):
    return {'capsule_sha256': digest(capsule),
            'receipt_ids': sorted(set(r['receipt_id'] for r in receipts)),
            'proves_claim': False}


def packet(pack, task, acceptance):
    """Build a handoff without invoking a model or removing omitted-range flags."""
    if not isinstance(task, str) or not 0 < len(task.strip()) <= 2000:
        raise ValueError('bounded task required')
    if not isinstance(acceptance, list) or not acceptance or len(acceptance) > 20:
        raise ValueError('explicit acceptance criteria required')
    if any(not isinstance(x, str) or not 0 < len(x.strip()) <= 1000 for x in acceptance):
        raise ValueError('invalid acceptance criterion')
    if not isinstance(pack, dict) or not isinstance(pack.get('source'), str):
        raise ValueError('source reference required')
    if type(pack.get('complete')) is not bool or not isinstance(pack.get('lines'), list):
        raise ValueError('pack completeness and lines required')
    fingerprint = pack.get('sha256')
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
        raise ValueError('source hash required')
    return {'task': task, 'acceptance': list(acceptance),
            'evidence': json.loads(json.dumps(pack, allow_nan=False)),
            'authority': 'untrusted_evidence',
            'expansion': {'source': pack['source'], 'sha256': fingerprint,
                          'instruction': 'Request original line ranges when evidence is insufficient; never infer omitted content.'}}


def aggregate(links, receipts):
    catalog, sources = {}, {}
    for r in receipts:
        body = {k: v for k, v in r.items() if k != 'receipt_id'}
        if digest(body) != r.get('receipt_id'):
            raise ValueError('receipt integrity mismatch')
        expected = receipt(r['source_id'], r['usage'], r['requested_model'])
        if expected != r:
            raise ValueError('unsupported receipt schema')
        prior = sources.setdefault(r['source_id'], r['receipt_id'])
        if prior != r['receipt_id']:
            raise ValueError('conflicting source observation')
        catalog[r['receipt_id']] = r
    ids = set(i for item in links for i in item['receipt_ids'])
    if ids - set(catalog):
        raise ValueError('missing referenced receipt')
    selected = [catalog[i] for i in sorted(ids)]
    known = {k: sum(r['usage'][k] for r in selected if r['usage'][k] is not None) for k in FIELDS}
    totals = {k: known[k] if selected and all(r['usage'][k] is not None for r in selected) else None for k in FIELDS}
    return {'unique_calls': len(selected), 'known_totals': known, 'totals': totals,
            'quota_savings': None, 'usd_cost': None,
            'limitation': 'Declared source identities only; capsule freshness must be checked separately.'}
