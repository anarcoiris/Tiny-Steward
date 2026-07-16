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

## Usage

```xml
<action name="write" path="output/report.md">
# Report

Generated content here.
</action>
```

## Notes

- Overwrites existing files without warning
- Creates parent directories automatically
- UTF-8 encoding
- For appending, use the `append` action instead
