---
name: mkdir
type: skill
requires: []
provides: [directory-creation]
tags: [mkdir, directory, filesystem]
related: [write, ls]
---

# Create Directory

Create a directory, including any necessary parent directories.

## Usage

```xml
<action name="mkdir">output/reports/2024</action>
```

## Notes

- Creates parent directories automatically (like `mkdir -p`)
- No error if directory already exists
- Paths can be relative or absolute
