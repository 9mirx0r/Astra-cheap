import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

from real_task_catalog import (  # noqa: E402
    PYDANTIC_REVIEW_SLUG,
    available_tasks,
    get_real_task,
)


class RealTaskCatalogTests(unittest.TestCase):
    def test_default_task_is_allowlisted_and_has_a_contract(self):
        task = get_real_task()

        self.assertEqual(task.slug, PYDANTIC_REVIEW_SLUG)
        self.assertTrue(task.repository.startswith("https://github.com/"))
        self.assertTrue(task.statement)
        self.assertTrue(task.test_command)
        self.assertTrue(task.evidence_files)
        self.assertTrue(task.required_surfaces)

    def test_unknown_task_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown real-task benchmark"):
            get_real_task("not-allowlisted")

    def test_available_tasks_have_unique_slugs(self):
        tasks = available_tasks()

        self.assertEqual(set(tasks), {task.slug for task in tasks.values()})
        self.assertGreaterEqual(len(tasks), 3)


if __name__ == "__main__":
    unittest.main()
