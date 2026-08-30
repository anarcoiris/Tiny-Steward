---
name: config-loader
description: Multi-format configuration loader (JSON, YAML, INI, TOML) with schema validation, smart merging, and format export.
domain: developer-tools
subdomain: configuration
tags:
  - config
  - yaml
  - json
  - toml
  - ini
  - validation
version: '1.0'
requires:
  - python
provides:
  - ConfigLoader
  - cargar_config
  - fusionar_config
---
# Config Loader

## Overview
Provides unified parsing, validation, merging, and format translation across JSON, YAML, INI, and TOML configuration files.

## When to Use
- When loading settings from multiple configuration sources.
- When merging default configurations with user overrides.
- When validating configuration dicts against strict schemas.

## Usage

### Python API
```python
from skills.file_utilities.config_loader.scripts.config_loader import ConfigLoader

loader = ConfigLoader("config.yaml")
server_port = loader.get("server.port", default=8000)

# Merge overrides
loader.fusionar_con("config.local.json")
loader.guardar("config.merged.yaml")
```
