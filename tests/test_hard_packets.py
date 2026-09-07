import importlib.util
from pathlib import Path
import tempfile
import unittest

class HardPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = Path(__file__).resolve().parents[1] / 'benchmarks' / 'hard_packets.py'
        s = importlib.util.spec_from_file_location('hard_packets', p)
        cls.m = importlib.util.module_from_spec(s)
        s.loader.exec_module(cls.m)

    def test_omission_requires_exact_expansion(self):
        self.assertFalse(self.m.accepted({'action':'answer','cause':'E_OLD','line':2}, 'E_NEW'))
        self.assertTrue(self.m.accepted({'action':'answer','cause':'E_NEW','line':401}, 'E_NEW'))

    def test_stale_is_blocked_before_expansion(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack, _ = self.m.fixture(root, 'stale')
            with self.assertRaisesRegex(ValueError, 'source changed'):
                self.m.e.expand(root, 'pack.json', 390, 20, 6000)
            self.assertFalse(self.m.fresh(root, pack))

    def test_adversarial_pack_really_omits_answer(self):
        with tempfile.TemporaryDirectory() as d:
            pack, _ = self.m.fixture(Path(d), 'contradiction')
            self.assertNotIn(401, [x['line'] for x in pack['lines']])
            self.assertFalse(pack['complete'])

    def test_range_rejects_bool_and_out_of_bounds(self):
        self.assertFalse(self.m.valid_range(True, 20))
        self.assertFalse(self.m.valid_range(501, 20))
        self.assertTrue(self.m.valid_range(390, 20))
