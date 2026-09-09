import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from benchmark_lattice import _last_json_object  # noqa: E402


class LatticeAdapterTests(unittest.TestCase):
    def test_last_json_object_ignores_logs_and_malformed_lines(self):
        expected = {"status": "passed", "telemetry": {"outputTokens": 4}}
        raw = "\n".join(
            [
                "human-readable log",
                "{not json}",
                json.dumps({"status": "intermediate"}),
                json.dumps(expected),
            ]
        )

        self.assertEqual(_last_json_object(raw), expected)

    def test_last_json_object_returns_none_without_an_object(self):
        self.assertIsNone(_last_json_object("log\n[1, 2]\nnull\n"))


if __name__ == "__main__":
    unittest.main()
