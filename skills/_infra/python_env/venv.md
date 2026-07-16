---
name: venv
type: skill
requires: [pwsh, bash, python]
provides: [virtual-environment, isolated-python]
tags: [python, venv, virtualenv, environment, isolation]
related: [pip, pytest]
---

# Python Virtual Environment

Create and manage isolated Python environments.

## Create

```powershell
python -m venv .venv
```

## Activate

PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

Bash (WSL/Linux):
```bash
source .venv/bin/activate
```

## Deactivate

```bash
deactivate
```

## Errors

### Execution policy prevents activation (Windows)

```
.\.venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled
```

Fix:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Python not found

Ensure Python is installed and on PATH:
```powershell
python --version
# or
py -3 --version
```

## Tips

- Add `.venv/` to `.gitignore`
- Use `python -m venv --clear .venv` to recreate from scratch
- Prefer `python -m pip install` over bare `pip install` inside venvs
