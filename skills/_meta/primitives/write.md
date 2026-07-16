---
name: write
type: skill
requires: []
provides: [file-creation]
tags: [write, file, filesystem, create]
related: [read, append, mkdir]
---

# Write File

Create or overwrite a file with content. Parent directories are created automatically.

## Usage (native Qwythos / Qwen tool_call)

```xml
<tool_call>
<function=write>
<parameter=path>
output/report.md
</parameter>
<parameter=content>
# Report

Generated content here.
</parameter>
</function>
</tool_call>
```

Do **not** use bare `<path>` tags — always `<parameter=path>…</parameter>`.

## Notes

- Overwrites existing files without warning
- Creates parent directories automatically
- UTF-8 encoding
- Prefer relative paths from the Tiny Steward workspace cwd
- For appending, use the `append` action instead
