"""Unit tests for TaskRunner and asynchronous primitive executions."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from core.primitives import get_workspace_dir, pwsh, set_workspace_dir, task_kill, task_status
from core.task_runner import TaskRunner, get_augmented_env


class TestTaskRunner(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.old_ws = get_workspace_dir()
        set_workspace_dir(self.root)
        self.runner = TaskRunner(self.root)

    def tearDown(self):
        set_workspace_dir(self.old_ws)
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_augmented_env_has_tools(self):
        env = get_augmented_env()
        path = env.get("PATH", "")
        self.assertTrue(len(path) > 0)

    def test_spawn_and_poll_task(self):
        # Spawn quick python script via TaskRunner
        task = self.runner.spawn('import time; time.sleep(0.5); print("async_done")', shell="python")
        self.assertEqual(task.status, "running")
        self.assertTrue(task.pid > 0)
        self.assertTrue(Path(task.log_path).exists())

        # Wait for task to finish
        time.sleep(1.0)
        polled = self.runner.poll(task.task_id)
        self.assertEqual(polled.status, "finished")
        self.assertEqual(polled.exit_code, 0)

        log = self.runner.tail_log(task.task_id)
        self.assertIn("async_done", log)

    def test_kill_task(self):
        # Spawn long task
        task = self.runner.spawn('import time; time.sleep(30)', shell="python")
        self.assertEqual(task.status, "running")

        killed = self.runner.kill(task.task_id)
        self.assertTrue(killed)
        self.assertEqual(task.status, "killed")

    def test_pwsh_async_primitive(self):
        res = pwsh("Write-Output 'hello_async'", is_async=True)
        self.assertIn("task_id", res)
        self.assertIn("Task started in background", res["content"])

        tid = res["task_id"]
        time.sleep(1.0)

        st = task_status(tid)
        self.assertEqual(st.get("status"), "finished")
        self.assertIn("hello_async", st.get("content", ""))


if __name__ == "__main__":
    unittest.main()
