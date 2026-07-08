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

## When

- Running Windows-native commands and cmdlets
- System administration tasks
- File management beyond simple read/write
- Process management
- Registry operations

## Usage

```xml
<action name="pwsh">Get-ChildItem -Recurse -Filter *.py</action>
<action name="pwsh">Get-Process | Where-Object { $_.CPU -gt 100 }</action>
```

## Common Patterns

| Task | Command |
|------|---------|
| List files | `Get-ChildItem -Path . -Recurse` |
| Find text | `Select-String -Path *.log -Pattern "error"` |
| Environment vars | `$env:PATH` |
| Install module | `Install-Module -Name <name> -Scope CurrentUser` |
| Service status | `Get-Service -Name <name>` |
| Network test | `Test-NetConnection -ComputerName <host> -Port <port>` |

## Notes

- Use `-ErrorAction SilentlyContinue` to suppress non-critical errors
- Pipe to `Select-Object -First N` to limit output
- Use `ConvertTo-Json` for structured output
