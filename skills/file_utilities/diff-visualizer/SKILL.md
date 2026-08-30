---
name: diff-visualizer
description: Unified diff generator, side-by-side comparison, directory diffs, and change statistical summaries.
domain: developer-tools
subdomain: version-control
tags:
  - diff
  - patch
  - file-comparison
  - changes
  - git
version: '1.0'
requires:
  - python
provides:
  - dif_unificado
  - dif_lado_a_lado
  - resumen_dif
  - comparar_directorios
---
# Diff Visualizer

## Overview
Generates unified diffs, side-by-side terminal comparisons, directory tree diffs, and statistical change summaries (lines added, deleted, modified) between files or directories.

## When to Use
- When reviewing code changes before committing.
- When verifying the output of automated file edits.
- When comparing two directory snapshots.

## Usage

### CLI Execution
```bash
python skills/file_utilities/diff-visualizer/scripts/diff_visualizer.py file_v1.txt file_v2.txt --side-by-side
```

### Python API
```python
from skills.file_utilities.diff_visualizer.scripts.diff_visualizer import dif_unificado, resumen_dif

diff_text = dif_unificado("antes.py", "despues.py")
stats = resumen_dif("antes.py", "despues.py")
print(f"Agregadas: {stats['agregadas']}, Eliminadas: {stats['eliminadas']}")
```
