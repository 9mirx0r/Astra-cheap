from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from astra_patch import verify_command as legacy_verify_command  # noqa: E402
from astra_verification import VerificationResult, verify_command  # noqa: E402


class VerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_successful_command_returns_bounded_result(self) -> None:
        result = verify_command(self.root, (sys.executable, "-c", "print('verified')"), 5)

        self.assertIsInstance(result, VerificationResult)
        self.assertTrue(result.passed)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "verified")
        self.assertFalse(result.timed_out)

    def test_empty_command_is_explicit_failure(self) -> None:
        result = verify_command(self.root, (), 5)

        self.assertFalse(result.passed)
        self.assertIsNone(result.returncode)
        self.assertEqual(result.stderr, "verification command was not provided")

    def test_patch_module_keeps_legacy_verification_surface(self) -> None:
        self.assertIs(legacy_verify_command, verify_command)


if __name__ == "__main__":
    unittest.main()
