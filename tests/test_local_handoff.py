import importlib.util
from pathlib import Path
import tempfile
import unittest

class LocalHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        s = importlib.util.spec_from_file_location('local_handoff', Path(__file__).resolve().parents[1]/'scripts/local_handoff.py')
        cls.m = importlib.util.module_from_spec(s)
        s.loader.exec_module(cls.m)

    def test_small_uses_current_full_source(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'run.log').write_text('new evidence')
            r = self.m.prepare(p,'run.log',previous_sha256='0'*64)
            self.assertEqual(r['route'],'full')
            self.assertTrue(r['refreshed'])
            self.assertTrue(r['evidence']['complete'])
            self.assertEqual(r['evidence']['lines'], [[1,'new evidence']])

    def test_large_uses_bounded_pack(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'run.log').write_text('routine\n'*5000+'ERROR failure\n')
            r = self.m.prepare(p,'run.log',full_limit=2000,pack_limit=1500)
            self.assertEqual(r['route'],'pack')
            self.assertFalse(r['evidence']['complete'])
            self.assertLessEqual(len(self.m.e.encoded(r['evidence'])),1500)

    def test_sensitive_path_remains_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                self.m.prepare(Path(d),'.env')

    def test_full_route_redacts_values(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'run.log').write_text('api_key=synthetic-test-value')
            r = self.m.prepare(p,'run.log')
            self.assertNotIn('synthetic-test-value',str(r))

    def test_invalid_budget_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                self.m.prepare(Path(d),'run.log',full_limit=-1)
