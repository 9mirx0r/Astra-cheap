"""Two authorized real Codex CLI runs. Does not read credentials or install tools.

Runs one baseline and one skill variant; reports actual CLI usage, not quota savings.
Raw events remain local under .local/ and are excluded from publication.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    cli = shutil.which('codex')
    if not cli:
        raise SystemExit('Codex CLI is unavailable; no model benchmark ran.')
    output = Path(args.output)
    if output.exists():
        raise SystemExit('Output already exists; preserve prior measurements.')
    local = ROOT / '.local' / ('benchmark-' + str(time.time_ns()))
    local.mkdir(parents=True)
    lines = ['Export job started; schema expected: invoice-v4']
    lines += [f'INFO stage=extract row={i:05d} scanned=ok' for i in range(4200)]
    lines += ['ERROR E_SCHEMA_MISMATCH record=INV-042 expected=invoice-v4 received=invoice-v3']
    error_line = len(lines)
    lines += [f'INFO stage=cleanup item={i:05d} cleanup=ok' for i in range(800)]
    lines += ['INFO wrapper process completed successfully; export artifact was not written']
    fixture = '\n'.join(lines) + '\n'
    schema = {'type': 'object', 'properties': {
        'root_cause': {'type': 'string'}, 'error_line': {'type': 'integer'},
        'wrapper_success_proves_export': {'type': 'boolean'},
        'next_check': {'type': 'string'}},
        'required': ['root_cause', 'error_line', 'wrapper_success_proves_export', 'next_check'],
        'additionalProperties': False}
    schema_path = local / 'answer-schema.json'
    schema_path.write_text(json.dumps(schema), encoding='utf-8')
    task = ('Diagnose the failed invoice export using logs/job.log in the current directory. '
            'Identify the actual cause with its exact 1-based log line, determine whether the final '
            'wrapper success proves export success, and give the next verification. '
            'Do not change source inputs or call a provider/network service. '
            'You may create local analysis artifacts. Return the required JSON. '
            'Use whatever reading strategy you consider appropriate.')
    results = []
    for variant in ('baseline', 'astra-cheap'):
        work = local / variant
        (work / 'logs').mkdir(parents=True)
        (work / 'logs' / 'job.log').write_text(fixture, encoding='utf-8')
        prompt = task
        if variant == 'astra-cheap':
            prompt = f'Use $astra-cheap. Read its instructions at {ROOT / "SKILL.md"}.\n' + task
        answer = work / 'answer.json'
        command = [cli, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                   '--json', '--color', 'never', '-m', args.model,
                   '-c', 'model_reasoning_effort="low"', '-s', 'workspace-write',
                   '-C', str(work), '--output-schema', str(schema_path),
                   '-o', str(answer), '-']
        print(f'Starting {variant}: model={args.model}, effort=low', flush=True)
        start = time.monotonic()
        try:
            run = subprocess.run(command, input=prompt, text=True, encoding='utf-8',
                                 capture_output=True, timeout=240)
        except subprocess.TimeoutExpired:
            results.append({'variant': variant, 'status': 'timeout', 'accepted': False})
            break
        (work / 'events.jsonl').write_text(run.stdout, encoding='utf-8')
        (work / 'stderr.txt').write_text(run.stderr, encoding='utf-8')
        events = []
        for line in run.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        usage = [e.get('usage') for e in events if e.get('type') == 'turn.completed' and e.get('usage')]
        responses = json.loads(answer.read_text(encoding='utf-8')) if answer.exists() and answer.stat().st_size else {}
        accepted = (run.returncode == 0 and responses.get('error_line') == error_line
                    and responses.get('wrapper_success_proves_export') is False
                    and 'schema' in responses.get('root_cause', '').lower()
                    and bool(responses.get('next_check', '').strip()))
        observed = {'variant': variant, 'returncode': run.returncode,
                    'elapsed_seconds': round(time.monotonic() - start, 2),
                    'usage': usage[-1] if usage else None, 'accepted': accepted,
                    'answer': responses, 'status': 'completed' if run.returncode == 0 else 'failed'}
        results.append(observed)
        print(json.dumps({k: v for k, v in observed.items() if k != 'answer'}), flush=True)
        if run.returncode != 0 or not usage:
            # Do not spend another run when the model/account or measurement is unavailable.
            errors = [e.get('message', '') for e in events if e.get('type') == 'error']
            print(json.dumps({'blocking_error': errors[-1:] or ['CLI failed or usage absent; inspect local evidence']}), flush=True)
            break
    report = {'model': args.model, 'effort': 'low', 'task': 'invoice_log_diagnosis',
              'trials_per_variant': 1, 'order': 'baseline_then_skill',
              'fixture_sha256': hashlib.sha256(fixture.encode()).hexdigest(),
              'expected_error_line': error_line, 'source_characters': len(fixture),
              'results': results, 'quota_savings': None,
              'limitations': ['One pair, not a general benchmark.',
                              'Same CLI, model, effort, fixture and acceptance schema.',
                              'Global discovery and host instructions may still exist in both arms.',
                              'Second-run cache/order effects are not controlled.',
                              'Token totals do not map directly to a Plus allowance percentage.',
                              'Mechanical acceptance is narrow; next-check semantics require human review.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
