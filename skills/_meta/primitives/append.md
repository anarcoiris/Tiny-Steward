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
<tool_call>
<function=append>
<parameter=path>
log.txt
</parameter>
<parameter=content>
[timestamp] Task completed.
</parameter>
</function>
</tool_call>
```

## Notes

- Does not add a newline before content — include it if needed
- Creates parent directories and file if they don't exist
- Always use `<parameter=path>` / `<parameter=content>` (never bare `<path>`)
