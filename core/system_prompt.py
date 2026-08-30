"""System prompt construction and rules loading for Tiny Steward.

Keeps system prompt text and rules composition isolated from runtime loop logic.
"""

from __future__ import annotations

import sys
import yaml
from pathlib import Path

_OS_PATH_RULE = (
    "- Use relative paths (e.g. `skills/`) or valid Windows paths (e.g. `C:\\...`). Do NOT use Unix-style absolute paths (e.g. `/skills`) as they resolve to `C:\\skills` on Windows."
    if sys.platform == "win32"
    else "- Use relative paths (e.g. `skills/`) or valid Unix absolute paths (e.g. `/home/user/...`)."
)

DELEGATE_EXAMPLE_STUB = "Review the Acme NDA text below..."

DEFAULT_RULES_CANDIDATES = (
    Path("RULES.md"),
    Path("sessions") / "RULES.md",
)

RULES_MAX_CHARS = 6000
ATTACH_MAX_CHARS = 48_000

SYSTEM_PROMPT = f"""\
You are Tiny Steward, a smart local pair programmer.
You execute operations using primitive actions and call help() when stuck or needing specialist capabilities.

## Operating Invariants

- You run locally with full OS permissions.
- Always check task.md/plan.md or existing state before making destructive edits.
- Never write credentials, tokens, or raw secrets into logs or messages.
- Be concise and direct in natural language responses.

## Available Actions

- pwsh(command): execute a PowerShell command (Windows)
- bash(command): execute a Bash command (Linux/macOS)
- python(code): execute inline Python script
- read(path, start_line?, end_line?): read a file
- write(path, content): create/overwrite a file
- append(path, content): append to a file
- mkdir(path): create directory
- ls(path): list directory contents
- grep(pattern, path): search for text in files
- http(method, url, body?): make an HTTP request
- mcp(tool, body?): execute a tool on the nina-mcp server
- delegate(agent, task): delegate a full task statement to a specialist micro-agent
- help(query): discover capabilities for a problem or error
- set(key, value): tweak config (temperature, max_tokens, enable_thinking, thinking_budget_tokens)
- checkpoint(note): manually save your state and write a steering note before a complex or risky task

## How to act

Emit native Qwen/Qwythos tool calls (one at a time). Schema is also sent via the
tools payload on the first turn of a session — do not invent alternate XML.

Parameters MUST use <parameter=NAME>…</parameter> (never bare <path> or <content> tags).

Example (list dir):

<tool_call>
<function=ls>
<parameter=path>
skills/_policy
</parameter>
</function>
</tool_call>

Example (write file — path AND content are both parameters):

<tool_call>
<function=write>
<parameter=path>
task.md
</parameter>
<parameter=content>
# Task title
Notes here.
</parameter>
</function>
</tool_call>

Workspace home is the process cwd (typically the Tiny Steward repo root). Prefer relative paths from that home. ls takes a directory path only — do not pass cwd. Use pwsh/bash when you need cwd.
For delegate(agent, task): task must be a complete problem statement (or path to one), never a placeholder.
Long transcripts: the user should /attach <path> instead of pasting; you may also read() the path.

## When to use help()

Call help() when you:
- Encounter an error you're unsure how to fix
- Need a capability outside your primitives
- Want guidance on a domain-specific task (git, docker, python env, etc.)

help() returns relevant skill documents. Read them and continue working.
You can call help() multiple times with narrower queries.

## Rules

- Execute one action at a time. Wait for the result before continuing.
- Explain your reasoning briefly before each action.
{_OS_PATH_RULE}
- When executing multi-step tasks or when asked to continue, ALWAYS follow the Active Session Task Plan or read() the task.md first to adhere strictly to the established objectives.
- When a task is complete, say DONE and summarize what was accomplished.
- If you're stuck after 3 help() calls on the same problem, ask the user.
"""


def load_rules_text(
    path: str | Path | None = None,
    enabled: bool = True,
    max_chars: int = RULES_MAX_CHARS,
) -> str:
    """Load global RULES.md text, or "" if disabled / missing."""
    if not enabled:
        return ""
    candidates: list[Path]
    if path:
        candidates = [Path(path)]
    else:
        candidates = list(DEFAULT_RULES_CANDIDATES)
    for candidate in candidates:
        try:
            p = candidate.expanduser().resolve()
        except OSError:
            continue
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not text:
            return ""
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n\n[… RULES.md truncated …]"
        return text
    return ""


def format_os_invariants(invariants: dict) -> str:
    """Format OS-level invariants for prompt injection."""
    if not invariants:
        return ""
    lines = []
    lines.append("## OS and Shell Invariants (Layer 0)")
    os_name = invariants.get("os", "windows")
    shell_name = invariants.get("shell", "powershell")
    path_style = invariants.get("path_style", "absolute")
    lines.append(f"- Operating System: {os_name}")
    lines.append(f"- Active Shell: {shell_name} (pwsh)")
    lines.append(f"- Path Style: {path_style}")
    mandatories = invariants.get("mandatory_primitives", [])
    if mandatories:
        lines.append("- Mandatory Primitive Constraints:")
        for m in mandatories:
            lines.append(f"  * {m}")
    return "\n".join(lines)


def compose_system_prompt(
    rules_text: str = "",
    invariants: dict | None = None,
    task_plan_text: str = "",
) -> str:
    """Built-in SYSTEM_PROMPT plus invariants prefix, optional global rules, and active task plan."""
    parts = []
    
    # Layer 0 OS Invariants
    inv_text = format_os_invariants(invariants or {})
    if inv_text:
        parts.append(inv_text)
        
    # Persona
    parts.append(SYSTEM_PROMPT.strip())
    
    # Layer 1 RULES.md
    rules = (rules_text or "").strip()
    if rules:
        parts.append(
            "## Global rules (RULES.md)\n\n"
            "Follow these project rules in addition to the above:\n\n"
            f"{rules}"
        )
        
    # Layer 2 Active Task Plan (task.md / plan.md)
    task_plan = (task_plan_text or "").strip()
    if task_plan:
        parts.append(
            "## Active Session Task Plan (task.md)\n\n"
            "The following task plan governs the current session. Adhere to these exact objectives and follow the numbered steps in sequence:\n\n"
            f"{task_plan}"
        )
        
    return "\n\n".join(parts)


def load_global_rules(candidates: tuple[Path, ...] = DEFAULT_RULES_CANDIDATES) -> str:
    """Load global rules text if any candidate exists (soft capped)."""
    return load_rules_text(enabled=True, max_chars=RULES_MAX_CHARS)


def build_system_prompt(config: dict | None = None) -> str:
    """Build system prompt including invariants prefix and optional global rules block."""
    cfg = config or {}
    rules_cfg = (cfg.get("rules") or {}).get("global_file")
    
    if rules_cfg is False:
        rules_text = ""
    elif isinstance(rules_cfg, str) and rules_cfg.strip():
        rules_text = load_rules_text(path=rules_cfg.strip())
    else:
        rules_text = load_rules_text()

    return compose_system_prompt(rules_text=rules_text)
