import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "astra_ultra.py"


class CliEntrypointTests(unittest.TestCase):
    def _help(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args, "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_root_help_lists_the_public_tools(self):
        result = self._help()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bounded context and verification", result.stdout)
        self.assertIn("run", result.stdout)
        self.assertIn("mcp", result.stdout)

    def test_run_help_exposes_the_independent_acceptance_command(self):
        result = self._help("run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--acceptance-command-json", result.stdout)
        self.assertIn("--worker", result.stdout)


if __name__ == "__main__":
    unittest.main()
