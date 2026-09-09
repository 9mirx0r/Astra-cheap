from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from astra_context import ContextKernel  # noqa: E402
from astra_contracts import ContextRequest, TaskSpec  # noqa: E402
from astra_index import RepositoryIndex  # noqa: E402
from astra_runtime import AstraRuntime  # noqa: E402
from astra_worker import ScriptedWorker  # noqa: E402


PATCH_NEW = """diff --git a/value.txt b/value.txt
--- a/value.txt
+++ b/value.txt
@@ -1 +1 @@
-old
+new
"""

PATCH_BAD = """diff --git a/value.txt b/value.txt
--- a/value.txt
+++ b/value.txt
@@ -1 +1 @@
-old
+wrong
"""

PATCH_HEADERLESS = """--- a/value.txt
+++ b/value.txt
@@ -1 +1 @@
-old
+new
"""

PATCH_BARE_HUNK = """--- a/value.txt
+++ b/value.txt
@@
-old
+new
"""

PATCH_MIXED = """--- a/value.txt
+++ b/value.txt
@@ -1 +1 @@
-old
+new
*** Add File: added.txt
+created by worker
"""

PATCH_UPDATE_WRAPPER = """*** Begin Patch
*** Update File: value.txt
@@
-old
+new
*** End Patch
"""

PATCH_RECOUNT = """diff --git a/value.txt b/value.txt
--- a/value.txt
+++ b/value.txt
@@ -99,99 +99,99 @@
-old
+new
"""


class AstraRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "value.txt").write_text("old\n", encoding="utf-8")
        (self.root / "module.py").write_text(
            "def read_value():\n    return open('value.txt', encoding='utf-8').read().strip()\n",
            encoding="utf-8",
        )
        (self.root / "details.txt").write_text("old detail\nsecond line\n", encoding="utf-8")
        self._git("init")
        self._git("config", "user.email", "astra@example.test")
        self._git("config", "user.name", "Astra Test")
        self._git("add", "value.txt", "module.py", "details.txt")
        self._git("commit", "-m", "initial")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _git(self, *args: str) -> None:
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def _task(self, **overrides: object) -> TaskSpec:
        values: dict[str, object] = {
            "task_id": "runtime-test",
            "objective": "Change value.txt to the expected value.",
            "root": self.root,
            "test_command": (
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('value.txt').read_text(encoding='utf-8') == 'new\\n'",
            ),
            "focus_paths": ("value.txt",),
            "focus_terms": ("value",),
            "allowed_paths": (),
            "context_budget_tokens": 1200,
            "page_budget_tokens": 400,
            "max_page_faults": 2,
            "max_turns": 3,
            "max_recoveries": 1,
            "verification_timeout_seconds": 30,
        }
        values.update(overrides)
        return TaskSpec(**values)  # type: ignore[arg-type]

    def test_context_kernel_is_bounded_and_confined(self) -> None:
        task = self._task()
        index = RepositoryIndex.build(self.root, task.allowed_paths)
        kernel = ContextKernel(task, index)
        bundle = kernel.initial()
        self.assertTrue(bundle.pages)
        self.assertLessEqual(bundle.estimated_tokens, task.context_budget_tokens)
        with self.assertRaises(ValueError):
            kernel.resolve(ContextRequest(paths=("../outside.txt",)), bundle)

    def test_runtime_requests_context_applies_patch_and_verifies(self) -> None:
        task = self._task()
        worker = ScriptedWorker(
            [
                {
                    "kind": "context_request",
                    "paths": ["details.txt"],
                    "terms": ["detail"],
                    "max_lines": 4,
                    "reason": "need the current value",
                },
                {"kind": "patch", "patch": PATCH_NEW, "message": "updated the value"},
            ]
        )
        result = AstraRuntime(task).run(worker)
        self.assertTrue(result.accepted)
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.changed_paths, ("value.txt",))
        self.assertEqual(result.telemetry["page_faults"], 1)
        self.assertEqual(result.telemetry["turns"], 2)
        self.assertEqual((self.root / "value.txt").read_text(encoding="utf-8"), "new\n")
        self.assertIn("context_fault", result.state_history)
        self.assertIn("verified", result.state_history)

    def test_failed_verification_rolls_back_and_is_not_accepted(self) -> None:
        task = self._task(max_recoveries=0)
        result = AstraRuntime(task).run(ScriptedWorker([{"kind": "patch", "patch": PATCH_BAD}]))
        self.assertFalse(result.accepted)
        self.assertEqual(result.status, "verification_failed")
        self.assertEqual((self.root / "value.txt").read_text(encoding="utf-8"), "old\n")

    def test_recovery_can_request_one_missing_page_before_retrying(self) -> None:
        task = self._task(
            context_budget_tokens=800,
            page_budget_tokens=300,
            max_turns=4,
            max_recoveries=1,
        )
        worker = ScriptedWorker(
            [
                {"kind": "patch", "patch": PATCH_BAD},
                {
                    "kind": "context_request",
                    "paths": ["details.txt"],
                    "terms": ["detail"],
                    "max_lines": 4,
                    "reason": "need the missing detail before retrying",
                },
                {"kind": "patch", "patch": PATCH_NEW},
            ]
        )
        result = AstraRuntime(task).run(worker)
        self.assertTrue(result.accepted)
        self.assertEqual(result.telemetry["recovery_attempts"], 1)
        self.assertEqual(result.telemetry["page_faults"], 1)
        self.assertNotIn("SYNTHESIS GATE", worker.prompts[1])

    def test_acceptance_oracle_runs_after_primary_tests_and_rolls_back(self) -> None:
        task = self._task(
            acceptance_command=(
                sys.executable,
                "-c",
                "raise SystemExit(7)",
            ),
            max_recoveries=0,
        )
        result = AstraRuntime(task).run(ScriptedWorker([{"kind": "patch", "patch": PATCH_NEW}]))
        self.assertFalse(result.accepted)
        self.assertEqual(result.status, "verification_failed")
        self.assertEqual(result.verification["returncode"], 0)
        self.assertEqual(result.verification["acceptance"]["returncode"], 7)
        self.assertFalse(result.verification["acceptance"]["passed"])
        self.assertEqual((self.root / "value.txt").read_text(encoding="utf-8"), "old\n")

    def test_runtime_accepts_headerless_unified_diff(self) -> None:
        result = AstraRuntime(self._task()).run(
            ScriptedWorker([{"kind": "patch", "patch": PATCH_HEADERLESS}])
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.status, "verified")
        self.assertEqual((self.root / "value.txt").read_text(encoding="utf-8"), "new\n")

    def test_runtime_expands_bare_hunk_ranges(self) -> None:
        result = AstraRuntime(self._task()).run(
            ScriptedWorker([{"kind": "patch", "patch": PATCH_BARE_HUNK}])
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.status, "verified")

    def test_runtime_normalizes_mixed_add_file_patch(self) -> None:
        result = AstraRuntime(self._task()).run(
            ScriptedWorker([{"kind": "patch", "patch": PATCH_MIXED}])
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.changed_paths, ("added.txt", "value.txt"))
        self.assertEqual((self.root / "added.txt").read_text(encoding="utf-8"), "created by worker\n")

    def test_runtime_normalizes_update_file_wrapper(self) -> None:
        result = AstraRuntime(self._task()).run(
            ScriptedWorker([{"kind": "patch", "patch": PATCH_UPDATE_WRAPPER}])
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.status, "verified")
        self.assertEqual(result.changed_paths, ("value.txt",))
        self.assertEqual((self.root / "value.txt").read_text(encoding="utf-8"), "new\n")

    def test_runtime_recounts_inaccurate_hunk_headers(self) -> None:
        result = AstraRuntime(self._task()).run(
            ScriptedWorker([{"kind": "patch", "patch": PATCH_RECOUNT}])
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.status, "verified")
        self.assertEqual((self.root / "value.txt").read_text(encoding="utf-8"), "new\n")

    def test_allowlist_rejects_unrelated_patch_before_writing(self) -> None:
        task = self._task(max_recoveries=0, allowed_paths=("value.txt",))
        patch = PATCH_NEW.replace("value.txt", "module.py").replace("-old", "-def read_value():").replace("+new", "+def read_value():")
        result = AstraRuntime(task).run(ScriptedWorker([{"kind": "patch", "patch": patch}]))
        self.assertFalse(result.accepted)
        self.assertEqual(result.status, "patch_failed")
        self.assertEqual((self.root / "module.py").read_text(encoding="utf-8"), "def read_value():\n    return open('value.txt', encoding='utf-8').read().strip()\n")


if __name__ == "__main__":
    unittest.main()
