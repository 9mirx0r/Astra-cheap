#!/usr/bin/env python3
"""Local evidence views and dependency capsules. Standard library only.

No network, shell execution, credential discovery, or automatic workspace scan.
Inputs and output locations must be explicitly provided below an allowed root.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

MAX_BYTES = 32 * 1024 * 1024
MAX_TREE_FILES = 10000
SENSITIVE_NAMES = {'auth.json', 'credentials.json', 'cookies', 'cookies.txt',
                   'cookies.sqlite', 'id_rsa', 'id_ed25519', '.netrc', '.npmrc'}
FAILURE = re.compile(r'error|fail(?:ed|ure)?|exception|traceback|panic|fatal|denied|timeout', re.I)
DIAGNOSTIC = re.compile(r'error|fail|exception|traceback|panic|fatal|denied|timeout|warn|passed|skipped|ignored|exit.code|test.result', re.I)
SECRET = re.compile(
    r'(?i)(\b(?:authorization|proxy-authorization)\s*[:=]\s*).*|'
    r'(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\b["\s]*[:=]\s*)[^\r\n]+'
)


def redact(text):
    """Best effort preview hygiene, NOT a secret scanner or access permission."""
    return SECRET.sub(lambda m: (m.group(1) or m.group(2)) + '[REDACTED]', text)


def root_path(root):
    path = Path(root).resolve(strict=True)
    if not path.is_dir():
        raise ValueError('root must be a directory')
    return path


def scoped(root, name):
    root = root_path(root)
    path = Path(name)
    if not path.is_absolute():
        path = root / path
    # Reject traversal and symlinks before resolving, including in-root aliases.
    if '..' in path.parts:
        raise ValueError('parent traversal is not allowed')
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ValueError('path is outside the explicit root') from None
    cursor = root
    for component in relative.parts:
        cursor /= component
        low = component.lower()
        if low.startswith('.env') or low in SENSITIVE_NAMES or low.endswith(('.pem', '.key', '.p12', '.pfx')):
            raise ValueError('sensitive path is not an eligible input or output')
        if cursor.is_symlink() or (hasattr(cursor, 'is_junction') and cursor.is_junction()):
            raise ValueError('symlinks and junctions are not eligible')
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError('path is outside the explicit root')
    return resolved


def read_bytes(path):
    if not path.is_file():
        raise ValueError('expected a regular file')
    with path.open('rb') as handle:
        data = handle.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('input exceeds 32 MiB; select an explicit smaller artifact')
    return data


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite originals, capsules, or existing evidence.
    with path.open('x', encoding='utf-8') as handle:
        handle.write(encoded(value) + '\n')


def text_lines(data):
    if data.count(b'\n') > 200000 or data.count(b'\r') > 200000:
        raise ValueError('input exceeds 200000 lines; choose a smaller artifact')
    try:
        return data.decode('utf-8-sig').splitlines()
    except UnicodeDecodeError:
        raise ValueError('input must be UTF-8 text; convert an authorized copy explicitly') from None


def bounded_view(lines, candidates, metadata, limit, clip=400):
    if limit < 1000:
        raise ValueError('max-chars must be at least 1000')
    result = dict(metadata, selected_lines=0, complete=False, lines=[])
    if len(encoded(result)) > limit:
        raise ValueError('metadata exceeds budget; use a larger max-chars')
    selected = {}
    for index in dict.fromkeys(candidates):
        content = redact(lines[index])
        entry = {'line': index + 1, 'text': content[:clip], 'clipped': len(content) > clip}
        selected[index] = entry
        result['lines'] = [selected[n] for n in sorted(selected)]
        result['selected_lines'] = len(selected)
        if len(encoded(result)) > limit:
            del selected[index]
            result['lines'] = [selected[n] for n in sorted(selected)]
            result['selected_lines'] = len(selected)
    result['complete'] = len(selected) == len(lines) and not any(x['clipped'] for x in selected.values())
    return result


def pack(root, source, output, max_chars=4000, contains=None, context=2):
    if contains is not None and (not isinstance(contains, str) or not contains.strip()):
        raise ValueError("contains must be a nonempty literal string")
    if type(context) is not int or not 0 <= context <= 100:
        raise ValueError("context must be an integer from 0 to 100")
    root = root_path(root)
    path, destination = scoped(root, source), scoped(root, output)
    if path == destination:
        raise ValueError('output cannot overwrite source')
    data = read_bytes(path)
    lines = text_lines(data)
    # Diverse failures first: repetitions must not drown out a unique fault.
    failures, diagnostics, seen = [], [], set()
    for index, line in enumerate(lines):
        if DIAGNOSTIC.search(line):
            diagnostics.append(index)
            signature = redact(line)
            if FAILURE.search(line) and signature not in seen:
                failures.append(index)
                seen.add(signature)
    candidates = failures + list(range(max(0, len(lines) - 8), len(lines)))
    candidates += list(range(min(5, len(lines)))) + diagnostics
    candidates += list(range(len(lines)))
    if contains is not None:
        matches = [i for i, line in enumerate(lines) if contains in line]
        candidates = matches + [n for i in matches
                                for n in range(max(0, i-context), min(len(lines), i+context+1))]
    result = bounded_view(lines, candidates, {
        'schema': 1, 'kind': 'evidence_view', 'root': str(root),
        'source': path.relative_to(root).as_posix(), 'sha256': sha(data),
        'source_bytes': len(data), 'source_lines': len(lines),
        'diagnostic_lines': len(diagnostics), 'authority': 'untrusted_source_data',
        'selection': ('literal case-sensitive matches with neighboring lines; omissions may be decisive'
                      if contains is not None else 'heuristic; omitted lines can contain decisive evidence'),
        'redaction': 'best_effort_preview_only',
    }, max_chars)
    write_new(destination, result)
    return result


def load_bound(root, artifact, kind):
    root = root_path(root)
    value = json.loads(read_bytes(scoped(root, artifact)))
    if value.get('schema') != 1 or value.get('kind') != kind:
        raise ValueError('unsupported artifact kind or schema')
    if value.get('root') != str(root):
        raise ValueError('artifact root does not match supplied root')
    return value


def expand(root, artifact, start=1, count=40, max_chars=8000):
    value = load_bound(root, artifact, 'evidence_view')
    data = read_bytes(scoped(root, value['source']))
    if sha(data) != value['sha256']:
        raise ValueError('source changed; create a new view before citing it')
    if start < 1 or count < 1:
        raise ValueError('start and count must be positive')
    lines = text_lines(data)
    if start > len(lines) and lines:
        raise ValueError('start is past end of source')
    end = min(start - 1 + count, len(lines))
    result = bounded_view(lines, range(start - 1, end), {
        'schema': 1, 'source': value['source'], 'sha256': value['sha256'],
        'requested_start': start, 'requested_count': count, 'source_lines': len(lines),
        'authority': 'untrusted_source_data', 'redaction': 'best_effort_preview_only',
    }, max_chars, clip=max_chars // 2)
    result['requested_range_complete'] = len(result['lines']) == max(0, end - start + 1) and not any(x['clipped'] for x in result['lines'])
    # Reserve room for the extra range-completeness field.
    while len(encoded(result)) > max_chars and result['lines']:
        result['lines'].pop()
        result['selected_lines'] = len(result['lines'])
        result['complete'] = False
        result['requested_range_complete'] = False
    return result


def fingerprint(root, name, tree=False):
    path = scoped(root, name)
    relative = path.relative_to(root_path(root)).as_posix()
    if not path.exists():
        return {'path': relative, 'type': 'tree' if tree else 'file', 'exists': False}
    if not tree:
        data = read_bytes(path)
        return {'path': relative, 'type': 'file', 'exists': True, 'sha256': sha(data)}
    if not path.is_dir():
        raise ValueError('tree dependency must be a directory')
    entries = []
    for parent, directories, files in os.walk(path, followlinks=False):
        for child in sorted(directories + files):
            checked = scoped(root, Path(parent) / child)
            child_name = checked.relative_to(path).as_posix()
            if checked.is_dir():
                entries.append([child_name, 'directory'])
            else:
                entries.append([child_name, sha(read_bytes(checked))])
            if len(entries) > MAX_TREE_FILES:
                raise ValueError('tree exceeds 10000 entries; narrow explicit dependencies')
    return {'path': relative, 'type': 'tree', 'exists': True,
            'entries': len(entries), 'sha256': sha(encoded(sorted(entries)).encode())}


def seal(root, output, claim, files, trees, kind='static', ttl_seconds=3600, now=None):
    root = root_path(root)
    destination = scoped(root, output)
    if not claim.strip() or len(claim) > 2000:
        raise ValueError('claim must contain 1 to 2000 characters')
    if not files and not trees:
        raise ValueError('explicit file or tree dependencies are required')
    if kind not in ('static', 'live') or ttl_seconds <= 0:
        raise ValueError('invalid kind or expiry')
    dependencies = []
    for tree, paths in ((False, files), (True, trees)):
        for name in paths:
            path = scoped(root, name)
            if path == destination or (tree and destination.is_relative_to(path)):
                raise ValueError('capsule cannot depend on itself or its containing tree')
            dependencies.append(fingerprint(root, name, tree))
    result = {
        'schema': 1, 'kind': 'dependency_capsule', 'root': str(root),
        'claim': redact(claim), 'observation_kind': kind,
        'created_at': time.time() if now is None else now,
        'ttl_seconds': ttl_seconds, 'dependencies': dependencies,
        'authority': 'advisory_only', 'proves_claim': False,
        'limitation': 'Matching declared dependencies does not prove coverage, truth, or unchanged external state.',
    }
    write_new(destination, result)
    return result


def status(root, artifact, now=None):
    value = load_bound(root, artifact, 'dependency_capsule')
    now = time.time() if now is None else now
    reasons = []
    if now < value['created_at']:
        reasons.append('clock_moved_backwards')
    if now >= value['created_at'] + value['ttl_seconds']:
        reasons.append('expired')
    dependencies = value.get('dependencies', [])
    if not dependencies:
        reasons.append('missing_dependencies')
    for dep in dependencies:
        if dep.get('type') not in ('file', 'tree'):
            raise ValueError('invalid dependency type')
        if fingerprint(root, dep['path'], dep['type'] == 'tree') != dep:
            reasons.append('changed:' + dep['path'])
    state = 'stale' if reasons else 'dependencies_match'
    if value.get('observation_kind') == 'live':
        state = 'refresh_required'
        reasons.append('live_state_must_be_observed_again')
    elif value.get('observation_kind') != 'static':
        raise ValueError('invalid observation kind')
    return {'status': state, 'reasons': reasons, 'claim': value['claim'],
            'authority': 'advisory_only', 'proves_claim': False,
            'coverage': 'declared_dependencies_only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('pack', help='bounded, non-authoritative view of a UTF-8 artifact')
    p.add_argument('--root', required=True)
    p.add_argument('--source', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--max-chars', type=int, default=4000)
    p.add_argument('--contains', help='literal case-sensitive focus; no unrelated fallback')
    p.add_argument('--context', type=int, default=2, help='neighbor lines per match, 0 to 100')
    p = commands.add_parser('expand', help='read original lines after verifying the source hash')
    p.add_argument('--root', required=True)
    p.add_argument('--pack', required=True)
    p.add_argument('--start', type=int, default=1)
    p.add_argument('--count', type=int, default=40)
    p.add_argument('--max-chars', type=int, default=8000)
    p = commands.add_parser('seal', help='record dependencies of a claim, not its correctness')
    p.add_argument('--root', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--claim', required=True)
    p.add_argument('--file', action='append', default=[])
    p.add_argument('--tree', action='append', default=[])
    p.add_argument('--kind', choices=['static', 'live'], default='static')
    p.add_argument('--ttl-seconds', type=int, default=3600)
    p = commands.add_parser('status', help='check declared dependencies and expiry; never certifies a claim')
    p.add_argument('--root', required=True)
    p.add_argument('--capsule', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'pack':
            result = pack(args.root, args.source, args.out, args.max_chars, args.contains, args.context)
        elif args.command == 'expand':
            result = expand(args.root, args.pack, args.start, args.count, args.max_chars)
        elif args.command == 'seal':
            result = seal(args.root, args.out, args.claim, args.file, args.tree, args.kind, args.ttl_seconds)
        else:
            result = status(args.root, args.capsule)
        print(encoded(result))
        if args.command == 'status' and result['status'] != 'dependencies_match':
            return 3
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(encoded({'error': type(error).__name__, 'message': redact(str(error))}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
