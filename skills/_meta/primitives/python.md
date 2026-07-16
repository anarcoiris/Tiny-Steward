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

## When

- Data processing and transformation
- JSON/YAML manipulation
- Quick calculations
- File format conversion
- API interactions

## Usage

```xml
<action name="python">
import json
data = {"key": "value", "count": 42}
print(json.dumps(data, indent=2))
</action>
```

## Notes

- Code runs as `python -c "..."` in a subprocess
- Import any installed package
- Use print() to return output
- For complex scripts, write to a file first, then run with pwsh/bash
