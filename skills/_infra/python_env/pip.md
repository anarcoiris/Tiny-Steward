---
name: pip
type: skill
requires: [pwsh, bash, python]
provides: [package-management, dependency-install]
tags: [python, pip, install, package, dependency, requirements]
related: [venv, pytest]
---

# Pip — Python Package Manager

Install, upgrade, and manage Python packages.

## Common Commands

```bash
# Install a package
pip install <package>

# Install from requirements.txt
pip install -r requirements.txt

# Upgrade
pip install --upgrade <package>

# List installed
pip list

# Show package info
pip show <package>

# Freeze current packages
pip freeze > requirements.txt

# Uninstall
pip uninstall <package>
```

## Errors

### No module named pip

```bash
python -m ensurepip --default-pip
```

### Permission denied

Use `--user` flag or (better) use a virtual environment:

```bash
pip install --user <package>
```

### Could not find a version that satisfies the requirement

- Check package name spelling
- Check Python version compatibility
- Try: `pip install <package> --pre` for pre-release versions

### Conflicting dependencies

```bash
pip install <package> --force-reinstall
# or clean install:
pip install -r requirements.txt --force-reinstall
```

## Tips

- Always prefer `python -m pip install` over bare `pip`
- Use virtual environments to avoid system-wide conflicts
- Pin versions in requirements.txt: `requests==2.31.0`
