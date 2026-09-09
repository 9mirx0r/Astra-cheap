import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from benchmark_evaluation import diff_stats, run_command, status_files  # noqa: E402


class BenchmarkEvaluationTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_diff_metrics_include_tracked_and_untracked_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init")
            self._git(root, "config", "user.email", "test@example.invalid")
            self._git(root, "config", "user.name", "Test")
            (root / "module.py").write_text("value = 1\n", encoding="utf-8")
            self._git(root, "add", "module.py")
            self._git(root, "commit", "-m", "base")
            base_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            (root / "module.py").write_text("value = 2\nvalue += 1\n", encoding="utf-8")
            (root / "test_new.py").write_text("assert True\n", encoding="utf-8")

            changed = status_files(root, base_sha)
            stats = diff_stats(root, base_sha, changed)

            self.assertEqual(changed, ["module.py", "test_new.py"])
            self.assertEqual(stats["changed_file_count"], 2)
            self.assertEqual(stats["test_files_changed"], ["test_new.py"])
            self.assertEqual(stats["lines_added"], 3)
            self.assertTrue(stats["diff_check_passed"])

    def test_host_command_persists_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stdout = root / "artifacts" / "stdout.txt"
            stderr = root / "artifacts" / "stderr.txt"
            result = run_command(
                [sys.executable, "-c", "print('checked')"],
                root,
                stdout,
                stderr,
                5,
            )

            self.assertEqual(result["returncode"], 0)
            self.assertIn("checked", stdout.read_text(encoding="utf-8"))
            self.assertTrue(stderr.exists())


if __name__ == "__main__":
    unittest.main()
