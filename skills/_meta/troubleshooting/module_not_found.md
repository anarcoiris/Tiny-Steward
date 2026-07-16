---
name: module_not_found
type: skill
requires: [pwsh, bash, python]
provides: [error-recovery]
tags: [python, module, not-found, import, ModuleNotFoundError, no-module-named, pip, install]
related: [venv, pip]
---

# Troubleshooting: ModuleNotFoundError / No module named

Diagnostic tree for Python import failures.

## Decision Tree

```
ModuleNotFoundError: No module named '<package>'
│
├─ Is a virtual environment active?
│   ├─ No → Activate it: .\.venv\Scripts\Activate.ps1
│   └─ Yes → Is the package installed?
│       ├─ No → pip install <package>
│       └─ Yes → Wrong Python?
│           └─ python -c "import sys; print(sys.executable)"
│
├─ Is the package name different from the import name?
│   Common mismatches:
│   ├─ pip install Pillow  → import PIL
│   ├─ pip install opencv-python → import cv2
│   ├─ pip install scikit-learn → import sklearn
│   ├─ pip install python-dateutil → import dateutil
│   └─ pip install PyYAML → import yaml
│
├─ Is it a local package?
│   └─ pip install -e .  (editable install)
│   └─ Or add to PYTHONPATH: $env:PYTHONPATH = "."
│
└─ Multiple Python versions?
    └─ Use: python3 -m pip install <package>
    └─ Or: py -3.12 -m pip install <package>
```

## Quick Fixes

```powershell
# Check which python
python -c "import sys; print(sys.executable)"

# Check if package is installed
pip show <package>

# Install in current environment
python -m pip install <package>

# If in wrong venv, recreate
python -m venv --clear .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
