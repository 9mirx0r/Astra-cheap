import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'evidence_receipts.py'


class EvidenceReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('receipts', PATH)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def test_shared_receipt_counts_once(self):
        receipt = self.m.receipt('source:1', {'input_tokens': 20}, 'requested-model')
        a = self.m.link({'claim': 'a'}, [receipt])
        b = self.m.link({'claim': 'b'}, [receipt])
        result = self.m.aggregate([a, b], [receipt])
        self.assertEqual(result['unique_calls'], 1)
        self.assertEqual(result['known_totals']['input_tokens'], 20)
        self.assertIsNone(result['totals']['output_tokens'])
        self.assertIsNone(receipt['observed_model'])

    def test_missing_receipt_blocks(self):
        r = self.m.receipt('source:1', {}, 'requested-model')
        with self.assertRaises(ValueError):
            self.m.aggregate([self.m.link({}, [r])], [])

    def test_tampered_receipt_blocks(self):
        r = self.m.receipt('source:1', {'input_tokens': 20}, 'm')
        link = self.m.link({}, [r])
        r['usage']['input_tokens'] = 99
        with self.assertRaises(ValueError):
            self.m.aggregate([link], [r])

    def test_conflicting_source_identity_blocks(self):
        a = self.m.receipt('source:1', {'input_tokens': 20}, 'm')
        b = self.m.receipt('source:1', {'input_tokens': 30}, 'm')
        with self.assertRaises(ValueError):
            self.m.aggregate([self.m.link({}, [a, b])], [a, b])

    def test_extra_usage_fields_rejected(self):
        with self.assertRaises(ValueError):
            self.m.receipt('source:1', {'prompt': 'do not persist'}, 'm')

    def test_packet_preserves_expansion_and_acceptance(self):
        pack = {'sha256': 'a' * 64, 'source': 'run.log', 'complete': False, 'lines': []}
        packet = self.m.packet(pack, 'Find the failure', ['Cite the source line'])
        self.assertEqual(packet['acceptance'], ['Cite the source line'])
        self.assertEqual(packet['expansion']['source'], 'run.log')
        self.assertFalse(packet['evidence']['complete'])
        self.assertEqual(packet['authority'], 'untrusted_evidence')

    def test_packet_without_acceptance_rejected(self):
        with self.assertRaises(ValueError):
            self.m.packet({}, 'Find the failure', [])
