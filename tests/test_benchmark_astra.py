import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_astra import _runtime_focus_terms  # noqa: E402
from real_task_catalog import RealTask  # noqa: E402


class AstraAdapterTests(unittest.TestCase):
    def test_focus_terms_are_bounded_and_skip_generic_noise(self):
        task = RealTask(
            slug="focus-test",
            repository="repo",
            issue="issue",
            title="title",
            target_directory="repo",
            statement="statement",
            test_command=("python", "-m", "unittest"),
            evidence_files=(("module.py", ("class Example", "def run", "verification_timeout")),),
            acceptance_code="",
            required_surfaces=(),
        )

        terms = _runtime_focus_terms(task)

        self.assertLessEqual(len(terms), 32)
        self.assertIn("class Example", terms)
        self.assertIn("verification_timeout", terms)
        self.assertNotIn("class", terms)
        self.assertNotIn("def", terms)
        self.assertEqual(len(terms), len(set(terms)))


if __name__ == "__main__":
    unittest.main()
