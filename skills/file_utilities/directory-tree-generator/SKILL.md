---
name: directory-tree-generator
description: Generate visual directory trees with statistics, size calculation, depth limiting, and file pattern filters.
domain: developer-tools
subdomain: filesystem
tags:
  - tree
  - directory
  - filesystem
  - visualization
  - stats
version: '1.0'
requires:
  - python
provides:
  - arbol_directorio
  - formatear_tamano
---
# Directory Tree Generator

## Overview
Generates hierarchical, visual directory trees (ASCII / Unicode) for any workspace or project folder with size metrics, file counts, and depth control.

## When to Use
- When exploring project architectures or directory structures.
- When generating filesystem maps for documentation or task reviews.
- When inspecting folder sizes and file distributions recursively.

## Usage

### CLI Execution
```bash
python skills/file_utilities/directory-tree-generator/scripts/file_tree_generator.py . --max-depth 3
```

### Python API
```python
from skills.file_utilities.directory_tree_generator.scripts.file_tree_generator import arbol_directorio

tree_view = arbol_directorio(".", max_profundidad=2, mostrar_tamano=True)
print(tree_view)
```
