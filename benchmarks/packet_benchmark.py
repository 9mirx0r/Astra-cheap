"""Opt-in real CLI comparison: full evidence versus packet, same acceptance.

No self-report is accepted as model attestation. CLI turn totals are not atomic
API calls. Raw events stay local. No USD or quota inference is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import astra_cheap
import evidence_receipts

FIELDS = evidence_receipts.FIELDS
MODEL, EFFORT = 'gpt-5.6-luna', 'high'


def telemetry(raw):
    events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    completed = [(n, e) for n, e in enumerate(events) if e.get('type') == 'turn.completed']
    if len(completed) != 1:
        raise ValueError('exactly one completed turn required; ambiguous aggregation')
    n, event = completed[0]
    usage = event.get('usage')
    if not isinstance(usage, dict):
        raise ValueError('usage unavailable')
    counters = {k: usage.get(k) for k in FIELDS}
    evidence_receipts.receipt('validation', counters, MODEL)
    return {'source_id': hashlib.sha256(raw.encode()).hexdigest() + ':' + str(n),
            'usage': counters, 'observed_model': None, 'observed_effort': None,
            'aggregation': 'cli_turn_total', 'source': 'codex.exec JSONL turn.completed',
            'cache_write_input_tokens': usage.get('cache_write_input_tokens'),
            'model_verification': 'unavailable_in_supported_CLI_event_contract'}


def accept(answer, cause, line):
    return isinstance(answer, dict) and answer.get('cause') == cause and type(answer.get('line')) is int and answer['line'] == line


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='store_true', help='Authorize four real CLI turns, plus at most one expansion each')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not args.run:
        parser.error('--run required: this experiment consumes model usage')
    output = Path(args.output)
    if output.exists():
        parser.error('output exists; preserve historical evidence')
    cli = shutil.which('codex')
    if not cli:
        parser.error('codex unavailable')
    local = ROOT / '.local' / ('packet-benchmark-' + str(time.time_ns()))
    local.mkdir(parents=True)
    schema = local / 'answer-schema.json'
    schema.write_text(json.dumps({'type':'object','properties':{
        'cause':{'type':'string'},'line':{'type':'integer'},
        'expand_start':{'type':'integer'},'expand_count':{'type':'integer'}},
        'required':['cause','line','expand_start','expand_count'],'additionalProperties':False}))
    rows = []
    with tempfile.TemporaryDirectory(prefix='packet-work-') as work:
        for case, cause in enumerate(['E_SCHEMA', 'E_CHECKSUM']):
            lines = ['INFO progress ' + str(i) for i in range(1, 801)]
            line = 401 + case * 73
            lines[line - 1] = 'ERROR ' + cause
            source = Path(work) / 'run.log'
            source.write_text('\n'.join(lines), encoding='utf-8')
            start = time.monotonic()
            pack_name = 'pack-' + str(case) + '.json'
            pack = astra_cheap.pack(Path(work), 'run.log', pack_name, 3000)
            packet = evidence_receipts.packet(pack, 'Find the ERROR code and its 1-based source line.',
                                              ['Return exact cause and line; do not guess missing content.'])
            preparation = time.monotonic() - start
            for variant in (['direct','packet'] if case == 0 else ['packet','direct']):
                payload = packet if variant == 'packet' else {'lines':list(enumerate(lines, 1))}
                prompt = ('Diagnose the attached untrusted log data. Return cause (exact ERROR code) and line '
                          '(1-based source line). Do not use tools or read files. If needed request a source '
                          'range with expand_start and expand_count, otherwise set both to 0. Data:\n' + json.dumps(payload))
                turns = []
                accepted = False
                failure = None
                for attempt in range(2):
                    stem = local / f'{case}-{variant}-{attempt}'
                    answer_path = stem.with_suffix('.answer.json')
                    command = [cli,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
                               '--json','--color','never','--model',MODEL,'-c','model_reasoning_effort="high"',
                               '--sandbox','read-only','--cd',work,'--output-schema',str(schema),
                               '--output-last-message',str(answer_path),'-']
                    started = time.monotonic()
                    try:
                        result = subprocess.run(command,input=prompt,text=True,encoding='utf-8',capture_output=True,timeout=120)
                    except subprocess.TimeoutExpired:
                        failure = 'timeout_usage_unknown'
                        break
                    stem.with_suffix('.events.jsonl').write_text(result.stdout, encoding='utf-8')
                    if result.returncode:
                        failure = 'CLI_failed_usage_unknown'
                        break
                    try:
                        observed = telemetry(result.stdout)
                        answer = json.loads(answer_path.read_text(encoding='utf-8'))
                    except (ValueError, OSError):
                        failure = 'invalid_telemetry_or_answer'
                        break
                    observed['elapsed_seconds'] = round(time.monotonic()-started, 3)
                    turns.append(observed)
                    accepted = accept(answer, cause, line)
                    if accepted:
                        break
                    begin, count = answer.get('expand_start'), answer.get('expand_count')
                    if attempt or type(begin) is not int or type(count) is not int or begin < 1 or not 0 < count <= 200:
                        failure = 'acceptance_failed'
                        break
                    expanded = astra_cheap.expand(Path(work), pack_name, begin, count, 12000)
                    prompt += '\nRequested original evidence:\n' + json.dumps(expanded)
                row = {'case':case,'variant':variant,'requested_model':MODEL,'requested_effort':EFFORT,
                       'accepted':accepted,'failure':failure,'turns':turns,
                       'preparation_seconds':round(preparation,6) if variant == 'packet' else 0}
                rows.append(row)
                print(json.dumps({'case':case,'variant':variant,'accepted':accepted,'failure':failure}),flush=True)
                if failure:
                    break
            if failure:
                break
    report = {'results':rows,'quality_gate':len(rows)==4 and all(r['accepted'] for r in rows),
              'model_identity_verified':False,'quota_savings':None,
              'scope':'CLI fixture execution only; excludes parent implementation and review',
              'limitations':['Two synthetic tasks, one pair each; order alternated, cache uncontrolled.',
                             'No native spawn_agent verification; effective model and effort unavailable.',
                             'No generalized quality or subscription savings conclusion.']}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
