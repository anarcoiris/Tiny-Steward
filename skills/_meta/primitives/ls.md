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
<action name="ls">.</action>
<action name="ls">C:\Users\soyko\Documents</action>
```

## Notes

- Shows file sizes in bytes
- Directories are marked with trailing `/`
- For recursive listing, use `pwsh`: `Get-ChildItem -Recurse`
- For tree view, use `pwsh`: `tree /F`
