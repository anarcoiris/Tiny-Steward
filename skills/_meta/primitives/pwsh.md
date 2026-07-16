---
name: pwsh
type: skill
requires: []
provides: [shell, windows-commands, system-admin]
tags: [powershell, shell, windows, system]
related: [bash, python, grep, ls]
---

# PowerShell (pwsh)

Primary shell for Tiny Steward. Executes PowerShell commands natively on Windows.

## Usage

```xml
<tool_call>
<function=pwsh>
<parameter=command>
Get-ChildItem -Recurse -Filter *.py
</parameter>
</function>
</tool_call>
```

## Notes

- Use `-ErrorAction SilentlyContinue` to suppress non-critical errors
- Pipe to `Select-Object -First N` to limit output
- Prefer relative paths from the Tiny Steward workspace cwd
