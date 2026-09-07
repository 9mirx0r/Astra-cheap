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

    def test_repeated_expansions_stop_repacking_same_source(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'run.log').write_text('routine\n'*5000)
            initial = self.m.prepare(p,'run.log',full_limit=2000,pack_limit=1500)
            with self.assertRaisesRegex(ValueError, 'targeted native read'):
                self.m.prepare(p,'run.log',previous_sha256=initial['evidence']['sha256'],
                               full_limit=2000,pack_limit=1500,recovery_attempts=2)

    def test_changed_source_does_not_inherit_recovery_count(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'run.log').write_text('routine\n'*5000)
            result = self.m.prepare(p,'run.log',previous_sha256='0'*64,
                                    full_limit=2000,pack_limit=1500,recovery_attempts=2)
            self.assertEqual(result['route'], 'pack')
            self.assertTrue(result['refreshed'])

    def test_recovery_count_requires_valid_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'run.log').write_text('small')
            for count, fingerprint in [(True,'0'*64),(-1,'0'*64),(2,None),(2,'invalid')]:
                with self.subTest(count=count, fingerprint=fingerprint):
                    with self.assertRaises(ValueError):
                        self.m.prepare(p,'run.log',previous_sha256=fingerprint,recovery_attempts=count)
