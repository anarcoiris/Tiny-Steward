---
name: ls
type: skill
requires: []
provides: [directory-listing]
tags: [ls, directory, filesystem, list]
related: [read, grep, find]
---

# List Directory

List files and subdirectories in a directory.

## Usage

```xml
<tool_call>
<function=ls>
<parameter=path>
.
</parameter>
</function>
</tool_call>
```

## Notes

- Directory path only — do not pass cwd as an argument name
- Prefer relative paths from the Tiny Steward workspace cwd
- For recursive listing use `pwsh`: `Get-ChildItem -Recurse`
