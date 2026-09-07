import importlib.util
from pathlib import Path
import unittest

class PacketBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = Path(__file__).resolve().parents[1] / 'benchmarks' / 'packet_benchmark.py'
        s = importlib.util.spec_from_file_location('packet_benchmark', p)
        cls.m = importlib.util.module_from_spec(s)
        s.loader.exec_module(cls.m)

    def test_no_metadata_is_unknown_not_requested(self):
        r = self.m.telemetry('{"type":"turn.completed","usage":{"input_tokens":42}}\n')
        self.assertEqual(r['usage']['input_tokens'], 42)
        self.assertIsNone(r['observed_model'])
        self.assertIsNone(r['usage']['cached_input_tokens'])

    def test_multiple_completions_are_not_silently_last_only(self):
        raw = '{"type":"turn.completed","usage":{"input_tokens":42}}\n'
        with self.assertRaises(ValueError):
            self.m.telemetry(raw + raw)

    def test_acceptance_requires_exact_cause_and_line(self):
        self.assertTrue(self.m.accept({'cause':'E_SCHEMA','line': 41}, 'E_SCHEMA', 41))
        self.assertFalse(self.m.accept({'cause':'E_SCHEMA','line': 1}, 'E_SCHEMA', 41))

    def test_source_identity_stable_for_same_artifact(self):
        raw = '{"type":"turn.completed","usage":{"input_tokens":42}}\n'
        self.assertEqual(self.m.telemetry(raw)['source_id'], self.m.telemetry(raw)['source_id'])
