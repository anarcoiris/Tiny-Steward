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
<tool_call>
<function=mkdir>
<parameter=path>
output/reports
</parameter>
</function>
</tool_call>
```
