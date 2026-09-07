#!/usr/bin/env python3
"""Record provider usage and accepted outcomes without storing prompts or responses."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys


SCHEMA_VERSION = 1
STATUSES = {'completed', 'failed', 'timeout', 'blocked'}
TEXT_FIELDS = {'task_id', 'variant', 'model', 'reasoning_effort', 'status', 'timestamp'}
USAGE_FIELDS = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')
TOP_LEVEL_FIELDS = {
    'schema_version', 'task_id', 'variant', 'model', 'reasoning_effort', 'status',
    'accepted', 'usage', 'retries', 'elapsed_seconds', 'timestamp',
}
CONTROL = re.compile(r'[\x00-\x1f\x7f]')


def _text(value, field):
    if not isinstance(value, str) or not value or len(value) > 200 or CONTROL.search(value):
        raise ValueError(f'{field} must be a non-empty single-line string of at most 200 characters')
    return value


def _nonnegative_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{field} must be a non-negative integer')
    return value


def _nonnegative_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f'{field} must be a non-negative number')
    return float(value)


def validate_event(event):
    if not isinstance(event, dict) or set(event) != TOP_LEVEL_FIELDS:
        raise ValueError('usage event has an unexpected or missing field')
    if event['schema_version'] != SCHEMA_VERSION:
        raise ValueError('unsupported usage event schema version')
    for field in TEXT_FIELDS:
        _text(event[field], field)
    if event['status'] not in STATUSES:
        raise ValueError(f'unsupported status: {event["status"]}')
    if not isinstance(event['accepted'], bool):
        raise ValueError('accepted must be boolean')
    if not isinstance(event['usage'], dict) or set(event['usage']) != set(USAGE_FIELDS):
        raise ValueError('usage must contain exactly the four token counters')
    for field in USAGE_FIELDS:
        _nonnegative_int(event['usage'][field], f'usage.{field}')
    if event['usage']['cached_input_tokens'] > event['usage']['input_tokens']:
        raise ValueError('cached input cannot exceed input tokens')
    _nonnegative_int(event['retries'], 'retries')
    _nonnegative_number(event['elapsed_seconds'], 'elapsed_seconds')
    return event


def make_event(args):
    timestamp = args.timestamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    event = {
        'schema_version': SCHEMA_VERSION,
        'task_id': args.task_id,
        'variant': args.variant,
        'model': args.model,
        'reasoning_effort': args.effort,
        'status': args.status,
        'accepted': args.accepted == 'true',
        'usage': {
            'input_tokens': args.input_tokens,
            'cached_input_tokens': args.cached_input_tokens,
            'output_tokens': args.output_tokens,
            'reasoning_output_tokens': args.reasoning_output_tokens,
        },
        'retries': args.retries,
        'elapsed_seconds': args.elapsed_seconds,
        'timestamp': timestamp,
    }
    return validate_event(event)


def record(ledger, event):
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')
    return {'recorded': 1}


def read_events(ledger):
    path = Path(ledger)
    if not path.exists():
        raise ValueError('ledger does not exist')
    events = []
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            raise ValueError(f'blank ledger line at {line_number}')
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f'invalid JSON at ledger line {line_number}') from error
        try:
            events.append(validate_event(event))
        except ValueError as error:
            raise ValueError(f'invalid event at ledger line {line_number}: {error}') from error
    if not events:
        raise ValueError('ledger is empty')
    return events


def _totals(events):
    return {field: sum(event['usage'][field] for event in events) for field in USAGE_FIELDS}


def _result(events):
    accepted = sum(1 for event in events if event['accepted'])
    totals = _totals(events)
    result = {
        'runs': len(events),
        'accepted_runs': accepted,
        'acceptance_rate': round(accepted / len(events), 6) if events else 0,
        'totals': totals,
        'retries': sum(event['retries'] for event in events),
        'elapsed_seconds': round(sum(event['elapsed_seconds'] for event in events), 6),
    }
    result['cost_per_accepted_outcome'] = (
        {field: round(value / accepted, 6) for field, value in totals.items()}
        if accepted else None
    )
    return result


def summary(ledger):
    events = read_events(ledger)
    by_variant = defaultdict(list)
    for event in events:
        by_variant[event['variant']].append(event)
    result = _result(events)
    result['by_variant'] = {variant: _result(rows) for variant, rows in sorted(by_variant.items())}
    return result


def parser():
    root = argparse.ArgumentParser(description='Record and summarize measured model usage.')
    commands = root.add_subparsers(dest='command', required=True)
    record_parser = commands.add_parser('record')
    record_parser.add_argument('--ledger', required=True)
    record_parser.add_argument('--task-id', required=True)
    record_parser.add_argument('--variant', required=True)
    record_parser.add_argument('--model', required=True)
    record_parser.add_argument('--effort', required=True)
    record_parser.add_argument('--status', choices=sorted(STATUSES), required=True)
    record_parser.add_argument('--accepted', choices=('true', 'false'), required=True)
    for field in USAGE_FIELDS:
        record_parser.add_argument('--' + field.replace('_', '-'), dest=field, type=int, required=True)
    record_parser.add_argument('--retries', type=int, required=True)
    record_parser.add_argument('--elapsed-seconds', type=float, required=True)
    record_parser.add_argument('--timestamp')
    summary_parser = commands.add_parser('summary')
    summary_parser.add_argument('--ledger', required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'record':
            output = record(args.ledger, make_event(args))
        else:
            output = summary(args.ledger)
    except (OSError, ValueError, TypeError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

