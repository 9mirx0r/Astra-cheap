"""Tests for the local usage ledger; no provider calls are made."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'usage_ledger.py'
sys.path.insert(0, str(SCRIPT.parent))
import usage_ledger


class UsageLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = self.root / 'usage.jsonl'

    def run_cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), *args],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, expected,
                         f'stdout={result.stdout}\nstderr={result.stderr}')
        return json.loads(result.stdout) if result.stdout.strip() else None

    def record(self, variant, accepted, input_tokens, output_tokens):
        return self.run_cli(
            'record', '--ledger', str(self.ledger), '--task-id', 'task-001',
            '--variant', variant, '--model', 'gpt-test', '--effort', 'low',
            '--status', 'completed', '--accepted', str(accepted).lower(),
            '--input-tokens', str(input_tokens), '--cached-input-tokens', '10',
            '--output-tokens', str(output_tokens), '--reasoning-output-tokens', '2',
            '--retries', '1', '--elapsed-seconds', '1.25',
            '--timestamp', '2026-09-06T12:00:00Z')

    def test_record_writes_bounded_structured_event(self):
        result = self.record('baseline', True, 100, 20)
        row = json.loads(self.ledger.read_text(encoding='utf-8'))
        self.assertEqual(result['recorded'], 1)
        self.assertEqual(row['usage']['input_tokens'], 100)
        self.assertTrue(row['accepted'])
        self.assertNotIn('prompt', row)
        self.assertNotIn('response', row)

    def test_record_rejects_negative_usage(self):
        self.run_cli(
            'record', '--ledger', str(self.ledger), '--task-id', 'task-001',
            '--variant', 'baseline', '--model', 'gpt-test', '--effort', 'low',
            '--status', 'completed', '--accepted', 'false', '--input-tokens', '-1',
            '--cached-input-tokens', '0', '--output-tokens', '0',
            '--reasoning-output-tokens', '0', '--retries', '0', '--elapsed-seconds', '0',
            '--timestamp', '2026-09-06T12:00:00Z', expected=2)
        self.assertFalse(self.ledger.exists())

    def test_direct_record_validates_before_creating_ledger(self):
        ledger = self.root / 'new' / 'usage.jsonl'
        event = {
            'schema_version': 1,
            'task_id': 'task-001',
            'variant': 'baseline',
            'model': 'gpt-test',
            'reasoning_effort': 'low',
            'status': 'completed',
            'accepted': False,
            'usage': {
                'input_tokens': -1,
                'cached_input_tokens': 0,
                'output_tokens': 0,
                'reasoning_output_tokens': 0,
            },
            'retries': 0,
            'elapsed_seconds': 0.0,
            'timestamp': '2026-09-06T12:00:00Z',
        }
        with self.assertRaises(ValueError):
            usage_ledger.record(ledger, event)
        self.assertFalse(ledger.exists())
        self.assertFalse(ledger.parent.exists())

    def test_record_rejects_nonfinite_duration(self):
        self.run_cli(
            'record', '--ledger', str(self.ledger), '--task-id', 'task-001',
            '--variant', 'baseline', '--model', 'gpt-test', '--effort', 'low',
            '--status', 'completed', '--accepted', 'false', '--input-tokens', '1',
            '--cached-input-tokens', '0', '--output-tokens', '1',
            '--reasoning-output-tokens', '0', '--retries', '0', '--elapsed-seconds', 'nan',
            '--timestamp', '2026-09-06T12:00:00Z', expected=2)
        self.assertFalse(self.ledger.exists())

    def test_record_rejects_reasoning_tokens_above_output(self):
        self.run_cli(
            'record', '--ledger', str(self.ledger), '--task-id', 'task-001',
            '--variant', 'baseline', '--model', 'gpt-test', '--effort', 'low',
            '--status', 'completed', '--accepted', 'false', '--input-tokens', '1',
            '--cached-input-tokens', '0', '--output-tokens', '1',
            '--reasoning-output-tokens', '2', '--retries', '0', '--elapsed-seconds', '0',
            '--timestamp', '2026-09-06T12:00:00Z', expected=2)
        self.assertFalse(self.ledger.exists())

    def test_record_rejects_accepted_non_completed_status(self):
        self.run_cli(
            'record', '--ledger', str(self.ledger), '--task-id', 'task-001',
            '--variant', 'baseline', '--model', 'gpt-test', '--effort', 'low',
            '--status', 'failed', '--accepted', 'true', '--input-tokens', '1',
            '--cached-input-tokens', '0', '--output-tokens', '1',
            '--reasoning-output-tokens', '0', '--retries', '0', '--elapsed-seconds', '0',
            '--timestamp', '2026-09-06T12:00:00Z', expected=2)
        self.assertFalse(self.ledger.exists())

    def test_summary_reports_cost_per_accepted_outcome(self):
        self.record('baseline', True, 100, 20)
        self.record('astra-cheap', False, 50, 10)
        result = self.run_cli('summary', '--ledger', str(self.ledger))
        self.assertEqual(result['runs'], 2)
        self.assertEqual(result['accepted_runs'], 1)
        self.assertEqual(result['acceptance_rate'], 0.5)
        self.assertEqual(result['totals']['input_tokens'], 150)
        self.assertEqual(result['totals']['output_tokens'], 30)
        self.assertEqual(result['cost_per_accepted_outcome']['input_tokens'], 150)
        self.assertEqual(result['by_variant']['baseline']['accepted_runs'], 1)
        self.assertEqual(result['by_variant']['astra-cheap']['accepted_runs'], 0)

    def test_summary_rejects_malformed_ledger_line(self):
        self.ledger.write_text('{"not": "a usage event"}\n', encoding='utf-8')
        self.run_cli('summary', '--ledger', str(self.ledger), expected=2)


if __name__ == '__main__':
    unittest.main()
