import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "scripts"))

from real_task_catalog import RealTask  # noqa: E402
from real_task_evidence import build_evidence_packet  # noqa: E402


class RealTaskEvidenceTests(unittest.TestCase):
    def test_packet_is_bounded_hashed_and_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "module.py"
            source.write_text(
                "class Example:\n    def run(self):\n        return 1\n",
                encoding="utf-8",
            )
            task = RealTask(
                slug="evidence-test",
                repository="https://example.invalid/repo.git",
                issue="https://example.invalid/issues/1",
                title="test",
                target_directory="repo",
                statement="test evidence",
                test_command=("python", "-m", "unittest"),
                evidence_files=(("module.py", ("class Example",)),),
                acceptance_code="",
                required_surfaces=(),
            )
            packet_path = root / "artifacts" / "packet.json"

            packet = build_evidence_packet(root, packet_path, task, "abc123")

            self.assertEqual(packet["base_sha"], "abc123")
            self.assertEqual(packet["bounded_characters"], len(json.dumps(packet["files"][0], ensure_ascii=False)))
            self.assertEqual(packet_path.exists(), True)
            item = packet["files"][0]
            self.assertEqual(item["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(item["windows"][0]["focus"], "class Example")
            self.assertEqual(json.loads(packet_path.read_text(encoding="utf-8")), packet)


if __name__ == "__main__":
    unittest.main()
