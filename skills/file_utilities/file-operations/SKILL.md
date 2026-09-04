---
name: file-operations
description: Atomic and safe file operations including copy, move, rename, truncate, prepend, append, and rollback backups.
domain: developer-tools
subdomain: file-management
tags:
  - file
  - copy
  - move
  - rename
  - append
  - prepend
  - truncate
  - backup
version: '1.0'
requires:
  - python
provides:
  - copiar_archivo
  - mover_archivo
  - renombrar_archivo
  - truncar_archivo
  - anteponer_lineas
  - anexar_lineas
  - eliminar_archivo_seguro
  - restaurar_backup
---
# File Operations Skill

## Overview
Provides safe, atomic file system manipulation routines with integrity guarantees, automatic parent directory creation, and non-destructive rollbacks.

## When to Use
- When performing atomic file modifications (e.g. prepending headers or licenses without race conditions).
- When moving, copying, or renaming files with deterministic overwrite protections.
- When safely deleting files with an automatic `.bak` recovery point.

## Python API Usage
```python
from file_operations import (
    copiar_archivo,
    mover_archivo,
    renombrar_archivo,
    anteponer_lineas,
    anexar_lineas,
    eliminar_archivo_seguro,
    restaurar_backup,
)

# Atomic prepend
anteponer_lineas("config.txt", ["# Header line\n", "# Generated automatically\n"])

# Safe delete with rollback backup
eliminar_archivo_seguro("documento.txt", con_backup=True)
```
