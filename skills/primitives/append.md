---
name: append
type: skill
requires: []
provides: [file-append]
tags: [append, file, filesystem, log]
related: [write, read]
---

# Append to File

Append content to an existing file (or create it if it doesn't exist).

## Usage

```xml
<action name="append" path="log.txt">
[2024-01-15] Task completed successfully.
</action>
```

## Notes

- Does not add a newline before content — include it if needed
- Creates parent directories and file if they don't exist
- Useful for logs, accumulating results, building files incrementally
