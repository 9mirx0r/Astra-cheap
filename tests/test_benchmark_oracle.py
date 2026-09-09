import tempfile
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from benchmark_oracle import make_acceptance_harness  # noqa: E402
from real_task_catalog import RealTask, get_real_task  # noqa: E402


class BenchmarkOracleTests(unittest.TestCase):
    def test_task_specific_oracle_is_written_without_modifying_the_task(self):
        task = RealTask(
            slug="oracle-test",
            repository="repo",
            issue="issue",
            title="title",
            target_directory="repo",
            statement="statement",
            test_command=("python", "-m", "unittest"),
            evidence_files=(),
            acceptance_code="print('independent')\n",
            required_surfaces=(),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oracle.py"
            make_acceptance_harness(path, task)
            self.assertEqual(path.read_text(encoding="utf-8"), task.acceptance_code)

    def test_legacy_oracle_is_generated_from_the_catalog_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oracle.py"
            make_acceptance_harness(path, get_real_task())
            source = path.read_text(encoding="utf-8")
            self.assertIn("end_strategy=\"review\"", source)
            self.assertIn("final_result", source)


if __name__ == "__main__":
    unittest.main()
