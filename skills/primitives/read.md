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
<action name="read" path="config.yaml"></action>
<action name="read" path="C:\Users\soyko\Documents\notes.md"></action>
```

## Notes

- Returns full file contents as UTF-8 text
- Use for config files, source code, documentation
- For binary files, use pwsh: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("file.bin"))`
