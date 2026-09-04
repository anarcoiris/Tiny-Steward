"""Deterministic shell command guardrails for Tiny Steward.

Validates shell actions before dispatch, enforcing OS invariants and preventing
unsupported shell invocations (e.g. bash on Windows).
"""

from __future__ import annotations

import re
import sys
from typing import Any

# Prohibited commands / utilities on Windows that must use pwsh primitives or PowerShell cmdlets
_UNIX_ONLY_COMMANDS = {
    "cat": "Get-Content or read()",
    "grep": "Select-String or grep()",
    "ls": "Get-ChildItem or ls()",
    "rm": "Remove-Item",
    "cp": "Copy-Item",
    "mv": "Move-Item",
    "touch": "New-Item or write()",
    "which": "Get-Command",
    "export": "$env:VAR = 'val'",
}

_CD_PATTERN = re.compile(r"^\s*cd\s+", re.IGNORECASE)


def validate_shell_action(
    action_name: str,
    command: str,
    *,
    platform: str = sys.platform,
) -> tuple[bool, str | None]:
    """Validate a shell action (name and command) against OS invariants.

    Returns:
        (is_valid, error_message_or_None)
    """
    cmd = (command or "").strip()

    # Invariant: Never use cd command directly in shell calls (rely on Cwd / relative paths)
    if _CD_PATTERN.search(cmd):
        return False, (
            "Directory change 'cd' is prohibited inside shell actions. "
            "Pass the directory in the 'cwd' parameter or use paths relative to workspace."
        )

    # Invariant: Windows environment restrictions
    if platform == "win32":
        if action_name == "bash":
            return False, (
                "Direct bash execution is disabled on Windows. "
                "Use the 'pwsh' action for PowerShell commands."
            )

        # Check for bash -c invocation in pwsh
        if re.search(r"^\s*bash\s+-c", cmd, re.IGNORECASE) or re.search(r"^\s*wsl\s+", cmd, re.IGNORECASE):
            return False, (
                "WSL / bash wrapper invocations are restricted on Windows. "
                "Use native PowerShell cmdlets or python inline execution."
            )

    # Invariant: Unix environment restrictions
    elif platform != "win32":
        if action_name == "pwsh" and not _is_pwsh_available():
            return False, (
                "PowerShell (pwsh) is not the default shell on Unix. Use 'bash' instead."
            )

    return True, None


def _is_pwsh_available() -> bool:
    import shutil
    return shutil.which("pwsh") is not None
