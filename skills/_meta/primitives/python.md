---
name: python
type: skill
requires: []
provides: [scripting, data-processing, automation]
tags: [python, scripting, automation]
related: [pip, venv, pytest]
---

# Python

Execute Python code snippets directly.

## Usage

```xml
<tool_call>
<function=python>
<parameter=code>
print("hello_world")
</parameter>
</function>
</tool_call>
```
