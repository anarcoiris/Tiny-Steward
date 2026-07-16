"""Spawn a child steward process for out-of-process delegation.

Resolves ``ui.delegate_terminal``:
  auto | in_process | windows_terminal | tmux | console
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def resolve_terminal_mode(configured: str = "auto") -> str:
    """Pick an effective spawn backend."""
    mode = (configured or "auto").lower().strip()
    if mode != "auto":
        return mode

    if sys.platform == "win32":
        if shutil.which("wt") or shutil.which("wt.exe"):
            return "windows_terminal"
        return "console"

    if os.environ.get("TMUX"):
        return "tmux"

    return "in_process"


def build_child_argv(
    *,
    python: str,
    steward_path: Path,
    config: str,
    session: str,
    parent: str,
    skill: str,
    problem: str,
    no_health_check: bool = True,
) -> list[str]:
    argv = [
        python,
        str(steward_path),
        "--config", config,
        "--session", session,
        "--parent", parent,
        "--delegate-mode",
        "--delegate-skill", skill,
        "--problem", problem,
    ]
    if no_health_check:
        argv.append("--no-health-check")
    return argv


def spawn_child(
    mode: str,
    argv: list[str],
    *,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    """Launch a child steward. Returns metadata about how it was spawned.

    For ``in_process``, returns ``{"kind": "in_process"}`` without spawning —
    the caller should run the delegate loop locally.
    """
    cwd = str(cwd or Path.cwd())
    kind = resolve_terminal_mode(mode) if mode == "auto" else mode

    if kind == "in_process":
        return {"kind": "in_process", "pid": None, "pane_id": None}

    if kind == "windows_terminal":
        wt = shutil.which("wt") or shutil.which("wt.exe")
        if not wt:
            return spawn_child("console", argv, cwd=cwd)
        # Split pane ~25% of current window height (horizontal split below).
        cmd = [wt, "split-pane", "-V", "-s", "0.25", "--"] + argv
        proc = subprocess.Popen(cmd, cwd=cwd)
        return {"kind": "windows_terminal", "pid": proc.pid, "pane_id": None, "process": proc}

    if kind == "console":
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            creationflags=creationflags,
        )
        return {"kind": "console", "pid": proc.pid, "pane_id": None, "process": proc}

    if kind == "tmux":
        if not os.environ.get("TMUX") or not shutil.which("tmux"):
            return {"kind": "in_process", "pid": None, "pane_id": None}
        # Launch in a split pane; capture pane id.
        inner = " ".join(_shell_quote(a) for a in argv)
        proc = subprocess.run(
            ["tmux", "split-window", "-p", "25", "-P", "-F", "#{pane_id}", inner],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        pane_id = (proc.stdout or "").strip() or None
        return {"kind": "tmux", "pid": None, "pane_id": pane_id, "process": None}

    return {"kind": "in_process", "pid": None, "pane_id": None}


def _shell_quote(s: str) -> str:
    if not s:
        return "''"
    if all(c.isalnum() or c in "-_./:\\" for c in s):
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"
