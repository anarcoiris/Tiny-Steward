---
name: bash
type: skill
requires: []
provides: [shell, unix-commands, scripting]
tags: [bash, shell, linux, wsl, unix]
related: [pwsh, python, grep, find, permissions]
---

# Bash

Unix shell. On Windows, runs via WSL (Windows Subsystem for Linux).

## When

- Unix-specific commands (sed, awk, xargs, etc.)
- Shell scripting with pipes and redirection
- Working inside WSL environments
- Linux server administration

## Usage

```xml
<action name="bash">find . -name "*.py" -type f | head -20</action>
<action name="bash">cat /etc/os-release</action>
```

## Common Patterns

| Task | Command |
|------|---------|
| Find files | `find . -name "*.md" -type f` |
| Search text | `grep -rn "pattern" .` |
| Process text | `awk '{print $1}' file.txt` |
| Replace text | `sed -i 's/old/new/g' file.txt` |
| Disk usage | `df -h` / `du -sh *` |
| Permissions | `chmod 755 script.sh` |
| Networking | `curl -s http://example.com` |

## Notes

- On Windows, paths translate: `C:\Users\soyko` → `/mnt/c/Users/soyko`
- Use `set -euo pipefail` for robust scripts
- Quote variables: `"$var"` not `$var`
