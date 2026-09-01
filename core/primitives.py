"""Primitive actions — the 10 (now 11) built-in capabilities.

These are always available, never need discovery.
Each returns a dict with {stdout, stderr, exit_code} or {content} or {error}.

Primitives:
  pwsh, bash, python, read, write, append, mkdir, ls, grep, http, help
"""

from __future__ import annotations

import os
import subprocess
import json
import time
from pathlib import Path
from typing import Any

import httpx

_WORKSPACE_DIR: Path = Path.cwd()


def get_workspace_dir() -> Path:
    """Return the active working directory for file primitives and commands."""
    return _WORKSPACE_DIR


def set_workspace_dir(path: Path | str) -> Path:
    """Set and ensure the active working directory."""
    global _WORKSPACE_DIR
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    _WORKSPACE_DIR = p
    return _WORKSPACE_DIR


def resolve_path(path: str | Path) -> Path:
    """Resolve a path relative to the active workspace directory unless absolute."""
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()
    return (_WORKSPACE_DIR / p).resolve()


from core.task_runner import get_augmented_env, get_task_runner


def _run_shell(
    command: str,
    shell_exe: str,
    shell_args: list[str],
    timeout: float = 60.0,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Run a shell command and capture output."""
    eff_cwd = str(cwd) if cwd else str(_WORKSPACE_DIR)
    eff_env = get_augmented_env()
    try:
        result = subprocess.run(
            [shell_exe, *shell_args, command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=eff_cwd,
            env=eff_env,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Command timed out", "exit_code": -1}
    except FileNotFoundError:
        return {"stdout": "", "stderr": f"{shell_exe} not found", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}


# ------------------------------------------------------------------
# Shell primitives
# ------------------------------------------------------------------

def pwsh(
    command: str,
    *,
    cwd: str | None = None,
    timeout: float = 120.0,
    is_async: bool = False,
) -> dict[str, Any]:
    """Execute a PowerShell command (synchronously or in background)."""
    eff_cwd = str(cwd) if cwd else str(_WORKSPACE_DIR)
    if is_async:
        runner = get_task_runner(_WORKSPACE_DIR)
        task = runner.spawn(command, shell="pwsh", cwd=eff_cwd)
        return {
            "content": f"Task started in background: {task.task_id} (PID: {task.pid})\nLog: {task.log_path}",
            "task_id": task.task_id,
            "pid": task.pid,
            "log_path": task.log_path,
            "status": task.status,
            "exit_code": 0,
        }

    res = _run_shell(
        command,
        shell_exe="pwsh",
        shell_args=["-NoProfile", "-NonInteractive", "-Command"],
        timeout=timeout,
        cwd=eff_cwd,
    )
    if res.get("exit_code") == -1 and "not found" in res.get("stderr", ""):
        res = _run_shell(
            command,
            shell_exe="powershell",
            shell_args=["-NoProfile", "-NonInteractive", "-Command"],
            timeout=timeout,
            cwd=eff_cwd,
        )
    return res


def bash(
    command: str,
    *,
    cwd: str | None = None,
    timeout: float = 120.0,
    is_async: bool = False,
) -> dict[str, Any]:
    """Execute a bash command (synchronously or in background)."""
    eff_cwd = str(cwd) if cwd else str(_WORKSPACE_DIR)
    if is_async:
        runner = get_task_runner(_WORKSPACE_DIR)
        task = runner.spawn(command, shell="bash", cwd=eff_cwd)
        return {
            "content": f"Task started in background: {task.task_id} (PID: {task.pid})\nLog: {task.log_path}",
            "task_id": task.task_id,
            "pid": task.pid,
            "log_path": task.log_path,
            "status": task.status,
            "exit_code": 0,
        }

    # Try WSL first on Windows, native bash on Linux/macOS
    if os.name == "nt":
        return _run_shell(
            command,
            shell_exe="wsl",
            shell_args=["bash", "-c"],
            timeout=timeout,
            cwd=eff_cwd,
        )
    return _run_shell(
        command,
        shell_exe="bash",
        shell_args=["-c"],
        timeout=timeout,
        cwd=eff_cwd,
    )


def python(code: str, *, cwd: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """Execute a Python snippet."""
    eff_cwd = str(cwd) if cwd else str(_WORKSPACE_DIR)
    try:
        # Inherit the current environment and ensure PYTHONUTF8 is set for
        # the child process so print() doesn't crash on non-ASCII characters.
        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONIOENCODING", "utf-8")
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=eff_cwd,
            env=env,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Python execution timed out", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}


# ------------------------------------------------------------------
# File I/O primitives
# ------------------------------------------------------------------

def read(path: str, start_line: int | None = None, end_line: int | None = None) -> dict[str, Any]:
    """Read file contents, with optional line range and a 500-line safety cap."""
    try:
        p = resolve_path(path)
        lines = p.read_text(encoding="utf-8").splitlines()
        
        start = max(1, start_line) if start_line is not None else 1
        end = min(len(lines), end_line) if end_line is not None else len(lines)
        
        # 500 lines cap
        if (end - start + 1) > 500:
            end = start + 499
            truncated = True
        else:
            truncated = False
            
        selected_lines = lines[start - 1 : end]
        content = "\n".join(selected_lines)
        
        if truncated:
            content += f"\n\n[Warning: File truncated at 500 lines. Use start_line/end_line to read more of '{p.name}']"
            
        return {"content": content}
    except FileNotFoundError:
        return {"error": f"File not found: {path}"}
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as e:
        return {"error": str(e)}


def write(path: str, content: str) -> dict[str, Any]:
    """Write content to a file (creates parent dirs)."""
    try:
        p = resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"content": f"Written {len(content)} bytes to {p}"}
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as e:
        return {"error": str(e)}


def append(path: str, content: str) -> dict[str, Any]:
    """Append content to a file."""
    try:
        p = resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return {"content": f"Appended {len(content)} bytes to {p}"}
    except Exception as e:
        return {"error": str(e)}


def replace(path: str, old_str: str, new_str: str, count: int = 1) -> dict[str, Any]:
    """Replace occurrences of old_str with new_str in a file without overwriting the whole file."""
    try:
        p = resolve_path(path)
        if not p.exists():
            return {"error": f"File not found: {path}"}
        if p.is_dir():
            return {"error": f"Path is a directory, not a file: {path}"}

        content = p.read_text(encoding="utf-8")
        if old_str not in content:
            return {"error": f"Target string not found in {path}. Ensure whitespace, indentation, and characters match exactly."}

        occurrences = content.count(old_str)
        if count and count > 0:
            new_content = content.replace(old_str, new_str, count)
            replaced = min(occurrences, count)
        else:
            new_content = content.replace(old_str, new_str)
            replaced = occurrences

        p.write_text(new_content, encoding="utf-8")
        return {"content": f"Successfully replaced {replaced} occurrence(s) in {p.name}"}
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as e:
        return {"error": str(e)}


def mkdir(path: str) -> dict[str, Any]:
    """Create a directory (including parents)."""
    try:
        p = resolve_path(path)
        p.mkdir(parents=True, exist_ok=True)
        return {"content": f"Created directory: {p}"}
    except Exception as e:
        return {"error": str(e)}


def ls(path: str = ".") -> dict[str, Any]:
    """List directory contents."""
    try:
        p = resolve_path(path)
        if not p.exists():
            return {"error": f"Path not found: {path}"}
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}

        entries = []
        all_items = sorted(p.iterdir())
        capped = False
        if len(all_items) > 100:
            all_items = all_items[:100]
            capped = True
        for item in all_items:
            if item.is_dir():
                entries.append(f"  {item.name}/")
            else:
                size = item.stat().st_size
                entries.append(f"  {item.name}  ({size} bytes)")
        if capped:
            entries.append("\n  [... directory listing capped at 100 entries ...]")
        return {"content": f"{p}/\n" + "\n".join(entries) if entries else f"{p}/ (empty)"}
    except Exception as e:
        return {"error": str(e)}


def grep(pattern: str, path: str = ".") -> dict[str, Any]:
    """Search for a pattern in files. Uses PowerShell Select-String on Windows."""
    try:
        stripped = (path or ".").strip()
        # Reject multi-path strings like "./ ./skills/" — one path per call.
        # Still allow a single existing path that contains spaces (e.g. Program Files).
        if len(stripped.split()) > 1 and not resolve_path(stripped).exists():
            return {
                "error": (
                    "grep accepts a single path per call "
                    f"(got {path!r}). For several roots, issue separate grep calls."
                )
            }
        p = resolve_path(path or ".")
        if p.is_file():
            # Search single file natively — no shell, no encoding issues
            lines = p.read_text(encoding="utf-8").split("\n")
            matches = [
                f"{i+1}: {line}"
                for i, line in enumerate(lines)
                if pattern.lower() in line.lower()
            ]
            if matches:
                return {"content": "\n".join(matches)}
            return {"content": f"No matches for '{pattern}' in {path}"}
        elif p.is_dir():
            # Escape single-quotes inside the pattern to avoid PowerShell injection.
            safe_pattern = pattern.replace("'", "''")
            # Use -Pattern with a single-quoted string so the regex pipe char (|)
            # and other special chars are handled correctly by Select-String.
            result = pwsh(
                f"Get-ChildItem -Recurse -File '{p}' "
                f"| Select-String -Pattern '{safe_pattern}' "
                f"| Select-Object -First 50 "
                f"| Format-Table -AutoSize Path, LineNumber, Line"
            )
            return result
        else:
            return {"error": f"Not a file or directory: {path}"}
    except Exception as e:
        return {"error": str(e)}


def http(method: str, url: str, body: str | None = None) -> dict[str, Any]:
    """Make an HTTP request."""
    try:
        with httpx.Client(timeout=30.0) as client:
            kwargs: dict[str, Any] = {}
            if body:
                try:
                    kwargs["json"] = json.loads(body)
                except json.JSONDecodeError:
                    kwargs["content"] = body

            resp = client.request(method.upper(), url, **kwargs)
            return {
                "status": resp.status_code,
                "content": resp.text[:8000],  # cap response size
            }
    except Exception as e:
        return {"error": str(e)}


# Module-level MCP client paths (overridden via configure_mcp from config.yaml).
_MCP_PYTHON_EXE = r"C:\Users\soyko\Documents\nina-mcp\.venv\Scripts\python.exe"
_MCP_CLIENT_PY = r"C:\Users\soyko\Documents\nina-mcp\test_client.py"


def configure_mcp(*, python_exe: str | None = None, client_py: str | None = None) -> None:
    """Set nina-mcp launcher paths (from config.yaml mcp: block)."""
    global _MCP_PYTHON_EXE, _MCP_CLIENT_PY
    if python_exe:
        _MCP_PYTHON_EXE = python_exe
    if client_py:
        _MCP_CLIENT_PY = client_py


def mcp(tool: str, body: str = "") -> dict[str, Any]:
    """Execute an MCP tool on nina-mcp.

    Attributes:
      - tool: the name of the tool (e.g. nina_camera_capture)
    Body:
      - JSON string containing the tool parameters
    """
    python_exe = _MCP_PYTHON_EXE
    client_py = _MCP_CLIENT_PY

    cmd = [python_exe, client_py, tool]
    if body:
        try:
            params = json.loads(body)
            if isinstance(params, dict):
                for k, v in params.items():
                    cmd.append(f"{k}={json.dumps(v)}")
            else:
                cmd.append(str(params))
        except json.JSONDecodeError:
            cmd.extend(body.split())

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60.0,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}


def reindex(path: str = "skills", embedder: Any = None) -> dict[str, Any]:
    """Rebuild and save the skills index in memory and on disk.

    Args:
        path: Path to the skills directory (defaults to "skills").
        embedder: Optional Embedder instance. If None, initializes Embedder.from_config({}).
    """
    import time
    from core.skill_loader import build_index
    from core.embedder import Embedder

    t0 = time.time()
    try:
        skills_root = resolve_path(path)
        if not skills_root.exists() and (Path(__file__).resolve().parent.parent / path).exists():
            skills_root = Path(__file__).resolve().parent.parent / path

        if embedder is None:
            embedder = Embedder.from_config({})

        idx = build_index(skills_root, embedder)
        idx_path = skills_root / "_index.json"
        idx.save(idx_path)
        elapsed = round(time.time() - t0, 2)
        return {
            "ok": True,
            "skills_indexed": idx.size,
            "index_path": str(idx_path),
            "elapsed_sec": elapsed,
            "content": f"Successfully reindexed {idx.size} skills into {idx_path} in {elapsed}s",
        }
    except Exception as e:
        return {"error": f"Failed to reindex skills: {e}"}


def task_status(task_id: str, tail: int = 30) -> dict[str, Any]:
    """Check status and recent log output of a background task."""
    runner = get_task_runner(_WORKSPACE_DIR)
    task = runner.poll(task_id)
    if not task:
        return {"error": f"Task not found: {task_id}"}
    log_tail = runner.tail_log(task_id, lines=tail)
    return {
        "task_id": task.task_id,
        "status": task.status,
        "exit_code": task.exit_code,
        "runtime_s": round((task.end_time or time.time()) - task.start_time, 2),
        "content": f"Status: {task.status} (exit_code: {task.exit_code})\n\n=== Recent Log Output ===\n{log_tail}",
    }


def task_kill(task_id: str) -> dict[str, Any]:
    """Terminate a running background task."""
    runner = get_task_runner(_WORKSPACE_DIR)
    success = runner.kill(task_id)
    if success:
        return {"content": f"Task {task_id} killed successfully."}
    task = runner.poll(task_id)
    if not task:
        return {"error": f"Task not found: {task_id}"}
    return {"content": f"Task {task_id} is not running (current status: {task.status})."}


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

PRIMITIVES = {
    "pwsh": pwsh,
    "bash": bash,
    "python": python,
    "task_status": task_status,
    "task_kill": task_kill,
    "read": read,
    "write": write,
    "replace": replace,
    "append": append,
    "mkdir": mkdir,
    "ls": ls,
    "grep": grep,
    "http": http,
    "mcp": mcp,
    "reindex": reindex,
    # "help" is handled specially by the runtime, not here
}

PRIMITIVE_NAMES = list(PRIMITIVES.keys()) + ["help"]

# Primary argument per tool — popped into action["body"] by extract_actions()
PRIMARY_ARGS: dict[str, str | None] = {
    "pwsh": "command",
    "bash": "command",
    "python": "code",
    "task_status": "task_id",
    "task_kill": "task_id",
    "read": "path",
    "write": "content",
    "replace": "new_str",
    "append": "content",
    "mkdir": "path",
    "ls": "path",
    "grep": "pattern",
    "http": "body",
    "mcp": "body",
    "reindex": "path",
    "help": "query",
    "delegate": "task",
    "checkpoint": "note",
    "set": None,
}


def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


PRIMITIVES_TOOLS: list[dict] = [
    _fn("pwsh", "Execute a PowerShell command (primary shell on Windows). Set is_async=true for long-running background tasks.", {
        "command": {"type": "string"},
        "cwd": {"type": "string"},
        "is_async": {"type": "boolean", "description": "Run in background asynchronously without blocking"},
    }, ["command"]),
    _fn("bash", "Execute a bash command (Linux/macOS only — on Windows use pwsh). Set is_async=true for background tasks.", {
        "command": {"type": "string"},
        "cwd": {"type": "string"},
        "is_async": {"type": "boolean"},
    }, ["command"]),
    _fn("task_status", "Check status and recent log output of a background task.", {
        "task_id": {"type": "string", "description": "Task ID returned when starting an async task"},
        "tail": {"type": "integer", "description": "Number of log lines to inspect (default: 30)"},
    }, ["task_id"]),
    _fn("task_kill", "Terminate a running background task.", {
        "task_id": {"type": "string", "description": "Task ID to terminate"},
    }, ["task_id"]),
    _fn("python", "Execute a Python snippet.", {"code": {"type": "string"}}, ["code"]),
    _fn("read", "Read file contents (capped to 500 lines).", {
        "path": {"type": "string"},
        "start_line": {"type": "integer"},
        "end_line": {"type": "integer"},
    }, ["path"]),
    _fn("write", "Create or overwrite a file.", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _fn("replace", "Surgical find-and-replace in an existing file (preferred over write for editing/fixing code).", {
        "path": {"type": "string"},
        "old_str": {"type": "string", "description": "Exact text/lines to find"},
        "new_str": {"type": "string", "description": "New replacement text/lines"},
        "count": {"type": "integer", "description": "Number of occurrences to replace (default: 1)"},
    }, ["path", "old_str", "new_str"]),
    _fn("append", "Append to a file.", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _fn("mkdir", "Create a directory.", {"path": {"type": "string"}}, ["path"]),
    _fn("ls", "List directory contents. Directory path only — do not pass cwd.", {"path": {"type": "string"}}),
    _fn("grep", "Search for text in files.", {"pattern": {"type": "string"}, "path": {"type": "string"}}, ["pattern"]),
    _fn("http", "Make an HTTP request.", {
        "method": {"type": "string"},
        "url": {"type": "string"},
        "body": {"type": "string"},
    }, ["method", "url"]),
    _fn("mcp", "Execute a tool on the nina-mcp server.", {"tool": {"type": "string"}, "body": {"type": "string"}}, ["tool"]),
    _fn("reindex", "Rebuild the semantic skill index (RAG) on demand.", {"path": {"type": "string"}}),
    _fn("delegate", "Delegate a task to a specialist micro-agent.", {
        "agent": {"type": "string"},
        "task": {"type": "string"},
    }, ["agent", "task"]),
    _fn("help", "Discover capabilities for a problem or error.", {"query": {"type": "string"}}, ["query"]),
    _fn("set", "Tweak runtime config (temperature, max_tokens, etc.).", {
        "key": {"type": "string"},
        "value": {"type": "string"},
    }, ["key", "value"]),
    _fn("checkpoint", "Save session state with a steering note.", {"note": {"type": "string"}}, ["note"]),
]
