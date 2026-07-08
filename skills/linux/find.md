---
name: find
type: skill
requires: [pwsh, bash]
provides: [file-search, directory-search]
tags: [find, search, file, locate, where]
related: [grep, ls, permissions]
---

# Find Files

Search for files and directories by name, type, size, or modification time.

## Linux / WSL

```bash
# By name
find . -name "*.py" -type f

# By name (case-insensitive)
find . -iname "readme*"

# Modified in last 24 hours
find . -mtime -1

# Larger than 10MB
find . -size +10M

# Execute command on results
find . -name "*.log" -exec rm {} +
```

## Windows / PowerShell

```powershell
# By name
Get-ChildItem -Recurse -Filter "*.py"

# By extension
Get-ChildItem -Recurse -Include *.log, *.txt

# Modified in last 24 hours
Get-ChildItem -Recurse | Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-1) }

# Larger than 10MB
Get-ChildItem -Recurse | Where-Object { $_.Length -gt 10MB }

# Just names
Get-ChildItem -Recurse -Filter "*.py" -Name
```

## Tips

- Use `-Depth` in PowerShell to limit recursion
- Combine with `Select-String` for find + grep
- Exclude directories: `-Exclude node_modules` or `find . -not -path "*/node_modules/*"`
