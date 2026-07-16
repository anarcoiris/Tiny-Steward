---
name: bash
type: skill
requires: []
provides: [shell, unix-commands, scripting]
tags: [bash, shell, linux, wsl, unix]
related: [pwsh, python, grep, find, permissions]
---

# Bash

Unix shell. On Windows, runs via WSL when available.

## Usage

```xml
<tool_call>
<function=bash>
<parameter=command>
find . -name "*.py" -type f | head -20
</parameter>
</function>
</tool_call>
```
