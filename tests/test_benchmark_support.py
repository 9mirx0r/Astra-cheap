import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from benchmark_support import (  # noqa: E402
    build_deterministic_packet,
    build_optimized_prompt,
    calculate_cost,
    create_output_schema,
    parse_codex_telemetry,
    resolve_effort,
)


class BenchmarkSupportTests(unittest.TestCase):
    def test_current_luna_rate_card(self):
        self.assertEqual(calculate_cost("gpt-5.6-luna", 100_000, 0, 10_000), 0.032)

    def test_long_context_multiplier(self):
        self.assertEqual(calculate_cost("gpt-6-astra", 272_001, 0, 1_000), 5.51502)

    def test_auto_effort_is_workload_specific(self):
        self.assertEqual(resolve_effort("raft_split_brain_recovery", "auto"), "max")
        self.assertEqual(resolve_effort("mvcc_aries_dirty_read", "auto"), "high")
        self.assertEqual(resolve_effort("mvcc_aries_dirty_read", "low"), "low")

    def test_parse_telemetry_tracks_cache_writes_turns_and_tools(self):
        raw = "\n".join([
            json.dumps({"type": "item.started", "item": {"type": "command_execution"}}),
            json.dumps({"type": "message", "text": "diagnosis"}),
            json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 120,
                "cached_input_tokens": 80,
                "cache_write_input_tokens": 10,
                "output_tokens": 20,
                "reasoning_output_tokens": 5,
            }, "model": "gpt-5.6-luna", "reasoning_effort": "high"}),
        ])
        usage, text, observed = parse_codex_telemetry(raw)
        self.assertEqual(usage["cache_write_input_tokens"], 10)
        self.assertEqual(observed["turn_count"], 1)
        self.assertEqual(observed["tool_call_count"], 1)
        self.assertEqual(text, "diagnosis")

    def test_packet_is_bounded_and_prompt_has_stop_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "trace.log"
            source.write_text("\n".join(["INFO routine"] * 30 + ["ERROR decisive"] + ["INFO tail"] * 30), encoding="utf-8")
            workload = {
                "id": "packet_test",
                "fixture_path": "trace.log",
                "packet_focus": "ERROR decisive",
            }
            packet = build_deterministic_packet(workload, root, root / "packet.json")
            self.assertLessEqual(len(json.dumps(packet)), 3000)
            prompt = build_optimized_prompt(workload, packet)
            self.assertIn("at most one bounded read", prompt)
            self.assertIn("ERROR decisive", prompt)

    def test_output_schema_is_written_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schema.json"
            create_output_schema(path)
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema["type"], "object")
            self.assertTrue(schema["required"])

    def test_unknown_model_is_not_silently_priced_as_luna(self):
        with self.assertRaisesRegex(ValueError, "no benchmark rate card"):
            calculate_cost("unknown-model", 100, 0, 10)


if __name__ == "__main__":
    unittest.main()
