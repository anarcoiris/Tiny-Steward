"""Idle Loop Engine — continuous background alertness, self-health checks, and memory dreaming.

Uses SharedExecutionLock (cross-process file lock + lock registry) to ensure background idle work
never overlaps or interferes with active user reasoning or running processes across ANY session/PID.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.backend_gate import get_gate
from core.dreaming import run_dream, think_path
from core.scheduler import TaskScheduler, ScheduledJob

logger = logging.getLogger(__name__)


def _is_pid_alive(pid: int) -> bool:
    """Cross-platform check if a process ID is currently running on the host."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h_proc:
                ctypes.windll.kernel32.CloseHandle(h_proc)
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class SharedExecutionLock:
    """Cross-process and cross-session shared execution lock (semaphore).

    Combines thread locks with OS file locking (`sessions/.execution.lock`) and a
    shared process registry (`sessions/.lock_registry.json`).

    If ANY process or session on the host is executing an active task (`ACTIVE_BUSY`),
    the background idle loops across ALL running sessions/processes automatically detect
    the shared lock and yield without overlapping.
    """

    def __init__(self, sessions_dir: str | Path | None = None, session_name: str = "default"):
        self.sessions_dir = Path(sessions_dir or "./sessions").expanduser().resolve()
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.session_name = session_name
        self.pid = os.getpid()

        self._thread_lock = threading.Lock()
        self._active_running = False
        self._idle_running = False

        self.lock_file_path = self.sessions_dir / ".execution.lock"
        self.registry_file_path = self.sessions_dir / ".lock_registry.json"
        self._file_handle: Any = None

        self._register_process("IDLE_WAITING")

    def set_session_name(self, name: str) -> None:
        self.session_name = name
        self._register_process("IDLE_WAITING")

    def _register_process(self, status: str, mode: str | None = None) -> None:
        """Update shared process registry file atomically."""
        try:
            data = self._read_registry()
            procs = data.get("registered_processes", {})

            # Clean stale PIDs
            clean_procs = {}
            for p_str, p_info in procs.items():
                p_id = int(p_str)
                if _is_pid_alive(p_id):
                    clean_procs[p_str] = p_info

            clean_procs[str(self.pid)] = {
                "pid": self.pid,
                "session": self.session_name,
                "status": status,
                "mode": mode,
                "updated_at": time.time(),
                "updated_ts": datetime.now(timezone.utc).isoformat(),
            }

            data["registered_processes"] = clean_procs
            data["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._write_registry(data)
        except Exception as e:
            logger.debug("Failed to update process registry: %s", e)

    def _read_registry(self) -> dict[str, Any]:
        if not self.registry_file_path.exists():
            return {"lock_holder": None, "registered_processes": {}}
        try:
            return json.loads(self.registry_file_path.read_text(encoding="utf-8"))
        except Exception:
            return {"lock_holder": None, "registered_processes": {}}

    def _write_registry(self, data: dict[str, Any]) -> None:
        try:
            tmp_path = self.registry_file_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp_path.replace(self.registry_file_path)
        except Exception:
            pass

    def _try_os_lock(self) -> bool:
        """Attempt non-blocking acquire of OS file lock."""
        try:
            if self._file_handle is None:
                self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
                self._file_handle = open(self.lock_file_path, "a+b")

            fd = self._file_handle.fileno()
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError, ImportError):
            return False

    def _release_os_lock(self) -> None:
        """Release OS file lock."""
        if self._file_handle is not None:
            try:
                fd = self._file_handle.fileno()
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

    @property
    def is_busy(self) -> bool:
        with self._thread_lock:
            if self._active_running or self._idle_running:
                return True
        st = self.get_shared_status()
        return st.get("shared_lock_state") != "FREE"

    @property
    def is_active_running(self) -> bool:
        with self._thread_lock:
            return self._active_running

    def acquire_active(self) -> None:
        """Acquired by main execution turns (interactive / single task).

        Blocks until any local or remote background idle task finishes.
        """
        while True:
            with self._thread_lock:
                if not self._idle_running:
                    if self._try_os_lock():
                        self._active_running = True
                        data = self._read_registry()
                        data["lock_holder"] = {
                            "pid": self.pid,
                            "session": self.session_name,
                            "mode": "ACTIVE_BUSY",
                            "acquired_at": datetime.now(timezone.utc).isoformat(),
                        }
                        self._write_registry(data)
                        self._register_process("ACTIVE_BUSY", mode="ACTIVE_BUSY")
                        return
            time.sleep(0.05)

    def release_active(self) -> None:
        """Released when main execution turn ends."""
        with self._thread_lock:
            self._active_running = False
            self._release_os_lock()
            data = self._read_registry()
            if (data.get("lock_holder") or {}).get("pid") == self.pid:
                data["lock_holder"] = None
                self._write_registry(data)
            self._register_process("IDLE_WAITING")

    class _ActiveContext:
        def __init__(self, parent: SharedExecutionLock):
            self.parent = parent

        def __enter__(self):
            self.parent.acquire_active()
            return self.parent

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.parent.release_active()

    def hold_active(self) -> _ActiveContext:
        """Context manager for main active execution blocks."""
        return self._ActiveContext(self)

    def acquire_idle(self) -> bool:
        """Attempt non-blocking acquire for background idle tasks.

        Returns True if acquired across ALL processes and sessions, False if busy.
        """
        with self._thread_lock:
            if self._active_running or self._idle_running:
                return False

            # Check shared registry for active turns in other processes
            data = self._read_registry()
            holder = data.get("lock_holder")
            if holder and holder.get("pid"):
                h_pid = int(holder["pid"])
                if _is_pid_alive(h_pid):
                    # Busy active turn in another process
                    return False
                else:
                    # Clean dead holder
                    data["lock_holder"] = None
                    self._write_registry(data)

            if not self._try_os_lock():
                return False

            self._idle_running = True
            data["lock_holder"] = {
                "pid": self.pid,
                "session": self.session_name,
                "mode": "IDLE_RUNNING",
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write_registry(data)
            self._register_process("IDLE_RUNNING", mode="IDLE_RUNNING")
            return True

    def release_idle(self) -> None:
        """Release idle lock after background task finishes."""
        with self._thread_lock:
            self._idle_running = False
            self._release_os_lock()
            data = self._read_registry()
            if (data.get("lock_holder") or {}).get("pid") == self.pid:
                data["lock_holder"] = None
                self._write_registry(data)
            self._register_process("IDLE_WAITING")

    def get_shared_status(self) -> dict[str, Any]:
        """Return structured status of the shared execution lock across processes and sessions."""
        data = self._read_registry()
        holder = data.get("lock_holder")
        procs = data.get("registered_processes", {})

        # Verify holder liveness
        if holder and holder.get("pid"):
            h_pid = int(holder["pid"])
            if not _is_pid_alive(h_pid):
                holder = None

        clean_procs: list[dict[str, Any]] = []
        for p_str, p_info in list(procs.items()):
            p_id = int(p_str)
            if _is_pid_alive(p_id):
                info = dict(p_info)
                info["is_current_process"] = (p_id == self.pid)
                clean_procs.append(info)

        lock_state = "FREE"
        if holder:
            lock_state = f"LOCKED_{holder.get('mode', 'BUSY')}"

        return {
            "shared_lock_state": lock_state,
            "lock_holder": holder,
            "current_pid": self.pid,
            "current_session": self.session_name,
            "registered_processes_count": len(clean_procs),
            "registered_processes": clean_procs,
            "lock_file": str(self.lock_file_path),
            "registry_file": str(self.registry_file_path),
        }


# Alias for backwards compatibility
IdleExecutionLock = SharedExecutionLock


@dataclass
class IdleState:
    enabled: bool = True
    tick_interval: float = 2.0
    health_check_interval: float = 30.0
    dream_check_interval: float = 60.0
    alert_check_interval: float = 3.0
    schedule_check_interval: float = 10.0
    last_health_check: float = 0.0
    last_dream_check: float = 0.0
    last_alert_check: float = 0.0
    last_schedule_check: float = 0.0
    health_status: dict[str, Any] = field(default_factory=dict)
    dream_runs_count: int = 0
    alerts_processed_count: int = 0
    scheduled_jobs_run_count: int = 0
    last_run_ts: str | None = None
    last_error: str | None = None


class IdleLoop:
    """Background daemon thread performing continuous health checks, dreaming, alertness, and scheduled jobs."""

    def __init__(
        self,
        runtime: Any,
        *,
        enabled: bool = True,
        tick_interval: float = 2.0,
        health_check_interval: float = 30.0,
        dream_check_interval: float = 60.0,
        alert_check_interval: float = 3.0,
        schedule_check_interval: float = 10.0,
    ):
        self.runtime = runtime
        sessions_dir = getattr(runtime.session_manager, "dir", "./sessions") if hasattr(runtime, "session_manager") else "./sessions"
        session_name = getattr(runtime.session, "name", "default") if hasattr(runtime, "session") else "default"

        self.lock = getattr(runtime, "execution_lock", None) or SharedExecutionLock(sessions_dir, session_name)
        self.scheduler = TaskScheduler(sessions_dir, session_name)
        self.state = IdleState(
            enabled=enabled,
            tick_interval=max(0.05, float(tick_interval)),
            health_check_interval=max(0.1, float(health_check_interval)),
            dream_check_interval=max(0.1, float(dream_check_interval)),
            alert_check_interval=max(0.1, float(alert_check_interval)),
            schedule_check_interval=max(0.1, float(schedule_check_interval)),
        )
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the background idle daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="IdleLoopDaemon", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        """Stop the background idle daemon thread cleanly."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def trigger_now(self) -> dict[str, Any]:
        """Manually trigger an immediate idle pass (health, dreaming, alertness, scheduled jobs)."""
        if not self.lock.acquire_idle():
            return {"ok": False, "reason": "Execution lock busy (active turn running on host)"}
        try:
            res_health = self._do_health_check()
            res_alert = self._do_alert_check()
            res_dream = self._do_dream_check()
            res_schedule = self._do_schedule_check()
            self.state.last_run_ts = datetime.now(timezone.utc).isoformat()
            return {
                "ok": True,
                "health": res_health,
                "alerts": res_alert,
                "dream": res_dream,
                "schedule": res_schedule,
            }
        finally:
            self.lock.release_idle()

    def _run_loop(self) -> None:
        """Daemon loop body."""
        while not self._stop_event.is_set():
            time.sleep(self.state.tick_interval)
            if self._stop_event.is_set() or not self.state.enabled:
                continue

            now = time.time()
            due_health = (now - self.state.last_health_check) >= self.state.health_check_interval
            due_alert = (now - self.state.last_alert_check) >= self.state.alert_check_interval
            due_dream = (now - self.state.last_dream_check) >= self.state.dream_check_interval
            due_schedule = (now - self.state.last_schedule_check) >= self.state.schedule_check_interval

            if not (due_health or due_alert or due_dream or due_schedule):
                continue

            # Try acquiring non-overlapping shared lock across processes
            if not self.lock.acquire_idle():
                continue

            try:
                if due_alert:
                    self._do_alert_check()
                    self.state.last_alert_check = time.time()

                if due_health:
                    self._do_health_check()
                    self.state.last_health_check = time.time()

                if due_dream:
                    self._do_dream_check()
                    self.state.last_dream_check = time.time()

                if due_schedule:
                    self._do_schedule_check()
                    self.state.last_schedule_check = time.time()

                self.state.last_run_ts = datetime.now(timezone.utc).isoformat()
                self.state.last_error = None
            except Exception as e:
                self.state.last_error = str(e)
                logger.debug("IdleLoop exception: %s", e)
            finally:
                self.lock.release_idle()

    def _do_health_check(self) -> dict[str, Any]:
        """Perform backend & system health checks."""
        res: dict[str, Any] = {"ts": datetime.now(timezone.utc).isoformat()}

        if hasattr(self.runtime, "llm") and self.runtime.llm:
            res["orch_health"] = self.runtime.llm.health()
        if hasattr(self.runtime, "atomic_llm") and self.runtime.atomic_llm:
            res["atomic_health"] = self.runtime.atomic_llm.health()

        if hasattr(self.runtime, "backend_launcher") and self.runtime.backend_launcher:
            launcher = self.runtime.backend_launcher
            res["launcher_status"] = launcher.get_status()

        self.state.health_status = res
        return res

    def _do_alert_check(self) -> dict[str, Any]:
        """Check mailbox and inter-agent messages for unhandled alerts."""
        processed = 0
        mailbox = None
        if hasattr(self.runtime, "_mailbox"):
            try:
                mailbox = self.runtime._mailbox()
            except Exception:
                pass

        if mailbox:
            msgs = mailbox.peek()
            if msgs:
                processed = len(msgs)
                self.state.alerts_processed_count += processed

        return {"alerts_found": processed}

    def _do_dream_check(self) -> dict[str, Any]:
        """Consolidate think entries into memory if un-dreamed records exist."""
        if not hasattr(self.runtime, "session_manager") or not self.runtime.session_manager:
            return {"skipped": True, "reason": "no session manager"}
        if not hasattr(self.runtime, "session") or not self.runtime.session:
            return {"skipped": True, "reason": "no active session"}

        session_name = self.runtime.session.name
        sessions_dir = Path(self.runtime.session_manager.dir)
        tpath = think_path(sessions_dir, session_name)
        if not tpath.exists():
            return {"skipped": True, "reason": "no think log file"}

        watermark = (self.runtime.session.metadata or {}).get("dream_watermark")
        llm = getattr(self.runtime, "atomic_llm", None) or getattr(self.runtime, "llm", None)
        if not llm:
            return {"skipped": True, "reason": "no LLM client available for dream"}

        res = run_dream(
            sessions_dir=sessions_dir,
            session_name=session_name,
            llm=llm,
            watermark=watermark,
            force_all=False,
        )

        if res.get("ok") and not res.get("skipped"):
            new_wm = res.get("watermark")
            if new_wm:
                self.runtime.session.metadata["dream_watermark"] = new_wm
                self.runtime.session_manager.save()
            self.state.dream_runs_count += 1

        return res

    def _do_schedule_check(self) -> dict[str, Any]:
        """Execute any due scheduled jobs autonomously."""
        results = self.scheduler.tick(self._execute_scheduled_job)
        if results:
            self.state.scheduled_jobs_run_count += len(results)
        return {"executed_jobs_count": len(results), "results": results}

    def _execute_scheduled_job(self, job: ScheduledJob) -> dict[str, Any]:
        """Execute a single scheduled job."""
        task_str = (job.task or "").strip()
        logger.info("Executing scheduled job %s: %s", job.id, task_str)

        # Built-in tasks
        if task_str.startswith("reindex"):
            from core import primitives
            return primitives.reindex()

        # Custom agent task execution if runtime supports it
        if hasattr(self.runtime, "execute_autonomous_task"):
            return self.runtime.execute_autonomous_task(task_str, lane=job.lane)

        return {"status": "dispatched", "task": task_str, "ts": datetime.now(timezone.utc).isoformat()}
