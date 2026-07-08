---
name: grep
type: skill
requires: []
provides: [text-search]
tags: [grep, search, find, text, pattern]
related: [read, ls, find]
---

# Grep / Text Search

Search for a pattern in a file or directory.

## Usage

```xml
<action name="grep" path="src/">TODO</action>
<action name="grep" path="config.yaml">base_url</action>
```

## Behavior

- **Single file**: reads the file and returns matching lines with line numbers
- **Directory**: uses PowerShell `Select-String` for recursive search (capped at 50 results)
- Case-insensitive by default

## Notes

- For regex patterns, use pwsh: `Select-String -Pattern "regex" -Path *.py`
- For large codebases, prefer `pwsh` with `Get-ChildItem | Select-String` for more control
