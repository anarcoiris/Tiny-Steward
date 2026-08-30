# Tiny Steward Trust Boundary & Security Model

## Overview
Tiny Steward is an autonomous local pair-programming agent designed to execute operations directly on the developer's workstation. By design, it operates with full local privileges as the logged-in user.

## Execution Model

### 1. Primitive Execution Surface
- **`pwsh(command)` / `bash(command)`**: Executes shell commands directly in PowerShell / Bash subprocesses.
- **`python(code)`**: Executes inline Python scripts via subprocess using `PYTHONUTF8=1`.
- **`read(path)` / `write(path, content)`**: Direct filesystem read and write access.
- **`ls(path)` / `grep(pattern, path)`**: Local directory traversal and pattern matching.

### 2. Trust Assumptions
- **Local Single-User Boundary**: Tiny Steward assumes the local machine is a trusted workstation environment.
- **No Direct Remote Ingestion**: Prompts and inputs originate from the local user or authorized local mailbox files.

### 3. Safeguards & Best Practices
- **Prompt Hygiene**: Strips REPL statistics and raw tool tags from outbound context to avoid model confusion.
- **Context Compaction**: Caps individual tool outputs at 4,000 characters and directory listings at 100 entries to prevent context window exhaustion.
- **Jinja Chat Template Compliance**: System messages after index 0 are normalized to `user` role with `[System Note]` headers to prevent Jinja parser exceptions on llama-server.
- **Atomic File Writing**: Session state metadata updates use atomic temp-file-rename operations to prevent file corruption during concurrent operations.
- **Health Watchdog**: Background watchdog monitors local LLM endpoints (`:11439` and `:11440`) and logs GPU-lost events.
