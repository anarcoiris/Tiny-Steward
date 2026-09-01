"""TaskRunner — Background Asynchronous Process Manager & PATH Augmentation for Tiny Steward.

Provides non-blocking execution of long-running commands (e.g. tshark capture, nmap, dev servers)
with log streaming, periodic polling, kill controls, and Windows tool PATH resolution.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


# Standard Windows installation directories for common CLI tools
KNOWN_WINDOWS_TOOL_PATHS = [
    r"C:\Program Files\Wireshark",
    r"C:\Program Files (x86)\Wireshark",
    r"C:\Program Files\Git\cmd",
    r"C:\Program Files\Git\bin",
    r"C:\Program Files\Nmap",
    r"C:\Program Files (x86)\Nmap",
]


def get_augmented_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return environment dictionary with common Windows tool directories added to PATH."""
    env = dict(base_env or os.environ)
    if sys.platform != "win32":
        return env

    current_path = env.get("PATH", "")
    existing_parts = [p.lower() for p in current_path.split(os.pathsep) if p]

    additional = []
    for tool_dir in KNOWN_WINDOWS_TOOL_PATHS:
        if os.path.isdir(tool_dir) and tool_dir.lower() not in existing_parts:
            additional.append(tool_dir)

    if additional:
        env["PATH"] = os.pathsep.join(additional) + os.pathsep + current_path
    return env


@dataclass
class BackgroundTask:
    task_id: str
    command: str
    shell: str
    cwd: str
    pid: int
    log_path: str
    start_time: float
    end_time: Optional[float] = None
    exit_code: Optional[int] = None
    status: str = "running"  # running, finished, failed, killed

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["runtime_s"] = round(
            (self.end_time or time.time()) - self.start_time, 2
        )
        return d


class TaskRunner:
    """Manages background asynchronous processes."""

    def __init__(self, workspace_root: Path | str):
        self.workspace_root = Path(workspace_root).resolve()
        self.tasks_dir = self.workspace_root / ".tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, BackgroundTask] = {}
        self._processes: Dict[str, subprocess.Popen] = {}
        self._log_handles: Dict[str, Any] = {}

    def spawn(
        self,
        command: str,
        *,
        shell: str = "powershell",
        cwd: Optional[Path | str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> BackgroundTask:
        """Spawn a non-blocking process with stdout/stderr logged to file."""
        task_id = f"task_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        log_file = self.tasks_dir / f"{task_id}.log"

        effective_cwd = str(Path(cwd).resolve() if cwd else self.workspace_root)
        effective_env = get_augmented_env(env)

        if shell == "powershell" or shell == "pwsh":
            # Use pwsh if available, fallback to powershell
            exe = "powershell"
            args = [exe, "-NoProfile", "-NonInteractive", "-Command", command]
        elif shell == "bash":
            args = ["bash", "-c", command]
        elif shell == "python":
            args = [sys.executable, "-c", command]
        else:
            args = [command]

        log_handle = open(log_file, "w", encoding="utf-8", errors="replace")
        log_handle.write(f"=== Task {task_id} ===\n")
        log_handle.write(f"Command: {command}\n")
        log_handle.write(f"Shell: {shell} | CWD: {effective_cwd}\n")
        log_handle.write(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_handle.write("=" * 40 + "\n\n")
        log_handle.flush()

        try:
            proc = subprocess.Popen(
                args,
                cwd=effective_cwd,
                env=effective_env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                shell=False,
            )
        except Exception as e:
            log_handle.write(f"\n[SPAWN ERROR] {e}\n")
            log_handle.close()
            task = BackgroundTask(
                task_id=task_id,
                command=command,
                shell=shell,
                cwd=effective_cwd,
                pid=-1,
                log_path=str(log_file),
                start_time=time.time(),
                end_time=time.time(),
                exit_code=-1,
                status="failed",
            )
            self._tasks[task_id] = task
            return task

        task = BackgroundTask(
            task_id=task_id,
            command=command,
            shell=shell,
            cwd=effective_cwd,
            pid=proc.pid,
            log_path=str(log_file),
            start_time=time.time(),
            status="running",
        )
        self._tasks[task_id] = task
        self._processes[task_id] = proc
        self._log_handles[task_id] = log_handle
        return task

    def poll(self, task_id: str) -> Optional[BackgroundTask]:
        """Poll process status and update task record."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        proc = self._processes.get(task_id)
        if proc and task.status == "running":
            ret = proc.poll()
            if ret is not None:
                task.exit_code = ret
                task.end_time = time.time()
                task.status = "finished" if ret == 0 else "failed"
                handle = self._log_handles.pop(task_id, None)
                if handle:
                    try:
                        handle.close()
                    except Exception:
                        pass

        return task

    def kill(self, task_id: str) -> bool:
        """Kill a running task process."""
        task = self.poll(task_id)
        if not task or task.status != "running":
            return False

        proc = self._processes.get(task_id)
        if proc:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except OSError:
                pass
            task.end_time = time.time()
            task.status = "killed"
            task.exit_code = -9
            handle = self._log_handles.pop(task_id, None)
            if handle:
                try:
                    handle.close()
                except Exception:
                    pass
            return True
        return False

    def tail_log(self, task_id: str, lines: int = 50) -> str:
        """Read recent output from the task's log file."""
        task = self._tasks.get(task_id)
        if not task:
            return f"Task {task_id} not found."

        p = Path(task.log_path)
        if not p.exists():
            return "Log file not found."

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            all_lines = content.splitlines()
            return "\n".join(all_lines[-lines:])
        except Exception as e:
            return f"Error reading log: {e}"

    def list_all(self) -> List[Dict[str, Any]]:
        """List all background tasks with updated status."""
        for tid in list(self._tasks.keys()):
            self.poll(tid)
        return [t.to_dict() for t in self._tasks.values()]


# Global singleton instance
_DEFAULT_RUNNER: Optional[TaskRunner] = None


def get_task_runner(workspace_root: Optional[Path | str] = None) -> TaskRunner:
    global _DEFAULT_RUNNER
    if _DEFAULT_RUNNER is None:
        root = workspace_root or Path.cwd()
        _DEFAULT_RUNNER = TaskRunner(root)
    return _DEFAULT_RUNNER
