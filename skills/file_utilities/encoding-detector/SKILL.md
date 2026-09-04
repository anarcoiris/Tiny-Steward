---
name: encoding-detector
description: Deterministic character encoding detection (BOMs, UTF-8, UTF-16, ASCII, Windows-1252) and safe file transcoding.
domain: developer-tools
subdomain: file-management
tags:
  - encoding
  - utf8
  - utf16
  - bom
  - charset
  - transcode
version: '1.0'
requires:
  - python
provides:
  - detectar_codificacion
  - convertir_codificacion
  - es_archivo_binario
---
# Encoding Detector Skill

## Overview
Detects character encodings without third-party dependencies using deterministic BOM inspection and byte heuristics. Converts files between encodings safely.

## When to Use
- When encountering mojibake or character corruption errors (`UnicodeDecodeError`).
- When inspecting files with BOM headers (UTF-8-SIG, UTF-16 LE/BE).
- When normalizing legacy Windows-1252 or Latin-1 files to standard UTF-8.

## Python API Usage
```python
from encoding_detector import detectar_codificacion, convertir_codificacion

info = detectar_codificacion("archivo_antiguo.txt")
print(info["encoding"], info["has_bom"])

convertir_codificacion(
    "archivo_antiguo.txt",
    "archivo_utf8.txt",
    codificacion_destino="utf-8"
)
```
