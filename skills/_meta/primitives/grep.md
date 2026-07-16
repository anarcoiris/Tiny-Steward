---
name: grep
type: skill
requires: []
provides: [text-search]
tags: [grep, search, find, text, pattern]
related: [read, ls, find]
---

# Grep / Text Search

Search for a pattern in a file or directory.

## Usage

```xml
<tool_call>
<function=grep>
<parameter=pattern>
TODO
</parameter>
<parameter=path>
core/
</parameter>
</function>
</tool_call>
```
