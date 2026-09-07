#!/usr/bin/env python3
"""Exercise the real local CLI on synthetic artifacts; no model or quota claims."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HELPER = Path(__file__).with_name('astra_cheap.py')


def call(root, *arguments, expected=0):
    result = subprocess.run([sys.executable, '-B', str(HELPER), *arguments,
                             '--root', str(root)], capture_output=True, text=True,
                            encoding='utf-8', timeout=30)
    if result.returncode != expected:
        raise AssertionError(f'CLI exit={result.returncode}, expected={expected}: {result.stderr}')
    return json.loads(result.stdout), result.returncode


def main():
    with tempfile.TemporaryDirectory(prefix='astra-cheap-benchmark-') as directory:
        root = Path(directory)
        source = 'Setup complete\n' + 'Routine progress: item visited\n' * 8000
        source += 'ERROR checksum mismatch at record 8001\nexit code: 1\n'
        (root / 'run.log').write_text(source, encoding='utf-8')
        view, pack_exit = call(root, 'pack', '--source', 'run.log', '--out', 'view.json',
                               '--max-chars', '3000')
        assert 'checksum mismatch' in json.dumps(view)
        assert not view['complete']
        expanded, expand_exit = call(root, 'expand', '--pack', 'view.json',
                                     '--start', '4000', '--count', '2')
        assert expanded['requested_range_complete']
        assert expanded['lines'][0]['text'] == 'Routine progress: item visited'
        assert (root / 'run.log').read_text(encoding='utf-8') == source
        _, seal_exit = call(root, 'seal', '--out', 'capsule.json', '--file', 'run.log',
                            '--claim', 'Synthetic local fixture observed; no model tested')
        before, match_exit = call(root, 'status', '--capsule', 'capsule.json')
        assert before['status'] == 'dependencies_match' and not before['proves_claim']
        (root / 'run.log').write_text(source + 'Later change\n', encoding='utf-8')
        after, stale_exit = call(root, 'status', '--capsule', 'capsule.json', expected=3)
        assert after['status'] == 'stale'
        _, live_seal_exit = call(root, 'seal', '--out', 'live.json', '--file', 'run.log',
                                 '--kind', 'live', '--claim', 'Live state cannot be reused')
        live, live_exit = call(root, 'status', '--capsule', 'live.json', expected=3)
        assert live['status'] == 'refresh_required'
        result = {
            'fixture': 'synthetic_repetitive_log', 'source_characters': len(source),
            'view_characters': len(json.dumps(view, ensure_ascii=False)),
            'expansion_characters': len(json.dumps(expanded, ensure_ascii=False)),
            'checks': {'failure_visible': True, 'original_unchanged_before_explicit_edit': True,
                       'omitted_lines_recoverable': True, 'dependency_change_invalidates': True,
                       'live_requires_refresh': True},
            'cli_exit_codes': [pack_exit, expand_exit, seal_exit, match_exit,
                               stale_exit, live_seal_exit, live_exit],
            'model_calls': 0, 'quota_savings': None, 'model_quality_equivalence': None,
            'limitation': 'Character volumes on one synthetic fixture; not a token or Plus savings benchmark.',
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
