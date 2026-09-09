from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from astra_worker import _last_json_object, _usage_from_events  # noqa: E402


class AstraWorkerTests(unittest.TestCase):
    def test_last_json_object_falls_back_to_event_stream(self) -> None:
        value = _last_json_object('progress\n{"kind":"patch","patch":"diff"}\n')
        self.assertEqual(value, {"kind": "patch", "patch": "diff"})

    def test_usage_uses_the_largest_snapshot_within_one_turn(self) -> None:
        raw = "\n".join(
            [
                json.dumps({"usage": {"input_tokens": 10, "output_tokens": 2}}),
                json.dumps(
                    {
                        "usage": {
                            "input_tokens": 120,
                            "prompt_tokens_details": {"cached_tokens": 80},
                            "output_tokens": 8,
                            "completion_tokens_details": {"reasoning_tokens": 5},
                        }
                    }
                ),
            ]
        )
        usage = _usage_from_events(raw)
        self.assertEqual(usage["input_tokens"], 120)
        self.assertEqual(usage["cached_input_tokens"], 80)
        self.assertEqual(usage["output_tokens"], 8)
        self.assertEqual(usage["reasoning_output_tokens"], 5)


if __name__ == "__main__":
    unittest.main()
