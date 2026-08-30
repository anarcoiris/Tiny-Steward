---
name: git-patch-manager
description: Unified diff generation, patch application, hunk parsing, and version-controlled patch management.
domain: developer-tools
subdomain: version-control
tags:
  - git
  - patch
  - diff
  - apply
  - vcs
version: '1.0'
requires:
  - python
provides:
  - generar_diff_unificado
  - aplicar_patch
  - validar_patch
---
# Git Patch Manager

## Overview
Generates unified git patches, validates applicability against target files, and applies differential changes reliably.

## When to Use
- When generating code patches to share or apply without git CLI.
- When applying differential edits to local source files.
- When exporting reproducible diff artifacts.

## Usage

### CLI Execution
```bash
python skills/file_utilities/git-patch-manager/scripts/git_patch_generator.py original.py modificado.py --output fix.patch
```

### Python API
```python
from skills.file_utilities.git_patch_manager.scripts.git_patch_generator import generar_diff_unificado, aplicar_patch

patch = generar_diff_unificado("v1.py", "v2.py")
aplicar_patch("destino.py", patch)
```
