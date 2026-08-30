"""Task Scheduler — autonomous background timer, delayed executions, and recurring cron jobs.

Persists scheduled jobs under ``sessions/<session>/schedules.json`` and executes due jobs
during idle intervals without interfering with active user turns.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """A persistent scheduled task definition."""

    id: str
    task: str
    interval_sec: float
    lane: str = "atomic"                  # "atomic" | "orch"
    enabled: bool = True
    last_run_ts: float = 0.0
    runs_count: int = 0
    max_runs: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_result: dict[str, Any] | None = None


class TaskScheduler:
    """Manages creation, persistence, and execution of autonomous scheduled tasks."""

    def __init__(self, sessions_dir: str | Path | None = None, session_name: str = "default"):
        self.sessions_dir = Path(sessions_dir or "./sessions").expanduser().resolve()
        self.session_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_name)
        self.jobs_file = self.sessions_dir / self.session_name / "schedules.json"
        self._jobs: dict[str, ScheduledJob] = {}
        self._load()

    def _load(self) -> None:
        if not self.jobs_file.exists():
            return
        try:
            raw = json.loads(self.jobs_file.read_text(encoding="utf-8"))
            for item in raw.get("jobs", []):
                job = ScheduledJob(**item)
                self._jobs[job.id] = job
        except Exception as e:
            logger.debug("Could not load schedules from %s: %s", self.jobs_file, e)

    def _save(self) -> None:
        try:
            self.jobs_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "session": self.session_name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "jobs": [asdict(j) for j in self._jobs.values()],
            }
            tmp = self.jobs_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.jobs_file)
        except Exception as e:
            logger.debug("Failed to save schedules to %s: %s", self.jobs_file, e)

    def add_job(
        self,
        task: str,
        interval_sec: float,
        *,
        lane: str = "atomic",
        max_runs: int | None = None,
        job_id: str | None = None,
    ) -> ScheduledJob:
        """Register a new scheduled task."""
        jid = job_id or f"job-{uuid.uuid4().hex[:8]}"
        job = ScheduledJob(
            id=jid,
            task=task.strip(),
            interval_sec=max(1.0, float(interval_sec)),
            lane=lane,
            max_runs=max_runs,
        )
        self._jobs[jid] = job
        self._save()
        return job

    def remove_job(self, job_id: str) -> bool:
        """Cancel and remove a scheduled job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save()
            return True
        return False

    def list_jobs(self) -> list[ScheduledJob]:
        """Return all registered scheduled jobs."""
        return list(self._jobs.values())

    def get_due_jobs(self, now: float | None = None) -> list[ScheduledJob]:
        """Return jobs that are due for execution."""
        cur = now if now is not None else time.time()
        due: list[ScheduledJob] = []
        for job in self._jobs.values():
            if not job.enabled:
                continue
            if job.max_runs is not None and job.runs_count >= job.max_runs:
                continue
            elapsed = cur - job.last_run_ts
            if job.last_run_ts == 0.0 or elapsed >= job.interval_sec:
                due.append(job)
        return due

    def mark_executed(self, job_id: str, result: dict[str, Any] | None = None) -> None:
        """Record execution timestamp and increment counter."""
        job = self._jobs.get(job_id)
        if not job:
            return
        job.last_run_ts = time.time()
        job.runs_count += 1
        job.last_result = result
        if job.max_runs is not None and job.runs_count >= job.max_runs:
            job.enabled = False
        self._save()

    def tick(self, executor: Callable[[ScheduledJob], dict[str, Any]]) -> list[dict[str, Any]]:
        """Check and execute all due jobs synchronously."""
        due_jobs = self.get_due_jobs()
        results: list[dict[str, Any]] = []
        for job in due_jobs:
            try:
                res = executor(job)
                self.mark_executed(job.id, result=res)
                results.append({"job_id": job.id, "ok": True, "result": res})
            except Exception as e:
                err_res = {"error": str(e)}
                self.mark_executed(job.id, result=err_res)
                results.append({"job_id": job.id, "ok": False, "error": str(e)})
        return results
