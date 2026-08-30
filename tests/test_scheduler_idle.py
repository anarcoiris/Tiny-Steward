"""Unit tests for the autonomous task scheduler and IdleLoop scheduler integration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.scheduler import TaskScheduler, ScheduledJob
from core.idle_loop import IdleLoop, IdleState


class TestSchedulerIdle(unittest.TestCase):
    def test_scheduler_crud_and_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            scheduler = TaskScheduler(sessions_dir=td, session_name="test_session")
            self.assertEqual(len(scheduler.list_jobs()), 0)

            # Add job
            job = scheduler.add_job("reindex skills", interval_sec=60.0, lane="atomic")
            self.assertEqual(job.task, "reindex skills")
            self.assertEqual(job.interval_sec, 60.0)
            self.assertTrue(job.enabled)

            # Check persistence file
            schedules_file = Path(td) / "test_session" / "schedules.json"
            self.assertTrue(schedules_file.exists())

            # Reload into a new scheduler instance
            scheduler2 = TaskScheduler(sessions_dir=td, session_name="test_session")
            jobs2 = scheduler2.list_jobs()
            self.assertEqual(len(jobs2), 1)
            self.assertEqual(jobs2[0].id, job.id)
            self.assertEqual(jobs2[0].task, "reindex skills")

    def test_scheduler_due_jobs_and_execution(self):
        with tempfile.TemporaryDirectory() as td:
            scheduler = TaskScheduler(sessions_dir=td, session_name="test_session")
            job = scheduler.add_job("test task", interval_sec=10.0, max_runs=1)

            # Initially due (last_run_ts == 0.0)
            due = scheduler.get_due_jobs()
            self.assertEqual(len(due), 1)
            self.assertEqual(due[0].id, job.id)

            # Execute via tick
            mock_executor = MagicMock(return_value={"status": "ok"})
            results = scheduler.tick(mock_executor)

            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["ok"])
            mock_executor.assert_called_once()

            # Now not due and disabled (since max_runs=1)
            self.assertEqual(len(scheduler.get_due_jobs()), 0)
            self.assertFalse(job.enabled)
            self.assertEqual(job.runs_count, 1)

    def test_idle_loop_executes_due_schedules(self):
        with tempfile.TemporaryDirectory() as td:
            mock_runtime = MagicMock()
            mock_runtime.session.name = "idle_sess"
            mock_runtime.session.metadata = {}
            mock_runtime.session_manager.dir = td
            mock_runtime.llm = None
            mock_runtime.atomic_llm = None
            mock_runtime.backend_launcher = None
            del mock_runtime._mailbox

            idle = IdleLoop(mock_runtime, enabled=True)
            idle.scheduler.add_job("test_cron_task", interval_sec=5.0, max_runs=1)

            # Trigger idle pass immediately
            res = idle.trigger_now()
            self.assertTrue(res.get("ok"))
            self.assertIn("schedule", res)
            self.assertEqual(res["schedule"]["executed_jobs_count"], 1)


if __name__ == "__main__":
    unittest.main()
