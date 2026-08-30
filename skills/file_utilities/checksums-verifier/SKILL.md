---
name: checksums-verifier
description: File integrity verification, multi-algorithm hashing (MD5, SHA1, SHA256, SHA384, SHA512), and directory manifest generation.
domain: developer-tools
subdomain: security
tags:
  - checksum
  - hash
  - sha256
  - md5
  - integrity
  - verification
version: '1.0'
requires:
  - python
provides:
  - calcular_checksum
  - verificar_integridad
  - generar_manifest
---
# Checksums Verifier

## Overview
Calculates cryptographic digests for single files or complete directory trees, generates audit manifests, and detects corrupted or modified files.

## When to Use
- When verifying the integrity of downloaded artifacts or models.
- When creating directory checksum manifests for deployment.
- When checking if files have changed without reading full text contents.

## Usage

### CLI Execution
```bash
python skills/file_utilities/checksums-verifier/scripts/checksums.py archivo.tar.gz --algo sha256
```

### Python API
```python
from skills.file_utilities.checksums_verifier.scripts.checksums import calcular_checksum, generar_manifest

sha = calcular_checksum("documento.pdf", algoritmo="sha256")
manifest = generar_manifest("./release_folder")
```
