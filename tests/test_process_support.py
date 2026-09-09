import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from process_support import run_streaming_process  # noqa: E402


class StreamingProcessTests(unittest.TestCase):
    def _run(self, code: str, *, timeout: int = 5, inactivity_timeout: int = 5):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stdout = root / "stdout.txt"
            stderr = root / "stderr.txt"
            logs: list[str] = []
            result = run_streaming_process(
                cmd=[sys.executable, "-c", code],
                cwd=root,
                stdin_path=None,
                stdout_path=stdout,
                stderr_path=stderr,
                activity_paths=(stdout, stderr),
                activity_label="stdout/stderr",
                heartbeat_formatter=lambda sizes: f"out={sizes[0]} err={sizes[1]}",
                timeout=timeout,
                inactivity_timeout=inactivity_timeout,
                log=logs.append,
            )
            return result, stdout.read_text(encoding="utf-8"), logs

    def test_completed_process_streams_output(self):
        result, stdout, _ = self._run("print('ready')")

        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.timed_out)
        self.assertFalse(result.inactivity_timed_out)
        self.assertIn("ready", stdout)

    def test_inactivity_watchdog_terminates_stalled_process(self):
        result, _, logs = self._run(
            "import time; time.sleep(3)",
            timeout=5,
            inactivity_timeout=1,
        )

        self.assertTrue(result.timed_out)
        self.assertTrue(result.inactivity_timed_out)
        self.assertTrue(any("no stdout/stderr progress" in message for message in logs))


if __name__ == "__main__":
    unittest.main()
