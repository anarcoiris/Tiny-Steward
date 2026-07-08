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
from pathlib import Path
from typing import Any

import httpx


def _run_shell(
    command: str,
    shell_exe: str,
    shell_args: list[str],
    timeout: float = 60.0,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Run a shell command and capture output."""
    try:
        result = subprocess.run(
            [shell_exe, *shell_args, command],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
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

def pwsh(command: str, *, cwd: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """Execute a PowerShell command."""
    return _run_shell(
        command,
        shell_exe="pwsh",
        shell_args=["-NoProfile", "-NonInteractive", "-Command"],
        timeout=timeout,
        cwd=cwd,
    )


def bash(command: str, *, cwd: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """Execute a bash command (WSL or native)."""
    # Try WSL first on Windows, native bash on Linux/macOS
    if os.name == "nt":
        return _run_shell(
            command,
            shell_exe="wsl",
            shell_args=["bash", "-c"],
            timeout=timeout,
            cwd=cwd,
        )
    return _run_shell(
        command,
        shell_exe="bash",
        shell_args=["-c"],
        timeout=timeout,
        cwd=cwd,
    )


def python(code: str, *, cwd: str | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """Execute a Python snippet."""
    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
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

def read(path: str) -> dict[str, Any]:
    """Read file contents."""
    try:
        p = Path(path).expanduser().resolve()
        content = p.read_text(encoding="utf-8")
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
        p = Path(path).expanduser().resolve()
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
        p = Path(path).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return {"content": f"Appended {len(content)} bytes to {p}"}
    except Exception as e:
        return {"error": str(e)}


def mkdir(path: str) -> dict[str, Any]:
    """Create a directory (including parents)."""
    try:
        p = Path(path).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return {"content": f"Created directory: {p}"}
    except Exception as e:
        return {"error": str(e)}


def ls(path: str = ".") -> dict[str, Any]:
    """List directory contents."""
    try:
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}

        entries = []
        for item in sorted(p.iterdir()):
            if item.is_dir():
                entries.append(f"  {item.name}/")
            else:
                size = item.stat().st_size
                entries.append(f"  {item.name}  ({size} bytes)")
        return {"content": f"{p}/\n" + "\n".join(entries) if entries else f"{p}/ (empty)"}
    except Exception as e:
        return {"error": str(e)}


def grep(pattern: str, path: str) -> dict[str, Any]:
    """Search for a pattern in files. Uses PowerShell Select-String on Windows."""
    try:
        p = Path(path).expanduser().resolve()
        if p.is_file():
            # Search single file
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
            # Use Select-String for recursive search
            result = pwsh(
                f'Get-ChildItem -Recurse -File "{p}" | Select-String -Pattern "{pattern}" -SimpleMatch | Select-Object -First 50 | Format-Table -AutoSize Path, LineNumber, Line'
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


def mcp(tool: str, body: str = "") -> dict[str, Any]:
    """Execute an MCP tool on nina-mcp.

    Attributes:
      - tool: the name of the tool (e.g. nina_camera_capture)
    Body:
      - JSON string containing the tool parameters
    """
    python_exe = r"C:\Users\soyko\Documents\nina-mcp\.venv\Scripts\python.exe"
    client_py = r"C:\Users\soyko\Documents\nina-mcp\test_client.py"

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


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

PRIMITIVES = {
    "pwsh": pwsh,
    "bash": bash,
    "python": python,
    "read": read,
    "write": write,
    "append": append,
    "mkdir": mkdir,
    "ls": ls,
    "grep": grep,
    "http": http,
    "mcp": mcp,
    # "help" is handled specially by the runtime, not here
}

PRIMITIVE_NAMES = list(PRIMITIVES.keys()) + ["help"]
