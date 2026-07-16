---
name: read
type: skill
requires: []
provides: [file-contents]
tags: [read, file, filesystem]
related: [write, append, ls, grep]
---

# Read File

Read the contents of a text file.

## Usage

```xml
<tool_call>
<function=read>
<parameter=path>
config.yaml
</parameter>
</function>
</tool_call>
```

Optional line range:

```xml
<tool_call>
<function=read>
<parameter=path>
core/runtime.py
</parameter>
<parameter=start_line>
1
</parameter>
<parameter=end_line>
50
</parameter>
</function>
</tool_call>
```

## Notes

- Returns UTF-8 text (capped ~500 lines by default)
- Prefer relative paths from the Tiny Steward workspace cwd
- For binary files, use pwsh base64 helpers
