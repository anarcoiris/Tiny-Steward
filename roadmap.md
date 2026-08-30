# Referenced Roadmap for Today — Tiny Steward & Qwythos Stack
**Date**: 2026-08-02  
**Referenced Source Files**: [task.md](file:///c:/Users/soyko/Documents/tiny_steward/task.md), [tiny_plan.md](file:///c:/Users/soyko/Documents/tiny_steward/tiny_plan.md), [qwythos-daemon.ps1](file:///c:/Users/soyko/Documents/Ollama/docker/llamacpp/qwythos-daemon.ps1)

---

## 🎯 Executive Summary & Status Overview
- **Completed Infrastructure**:
  - `SharedExecutionLock` cross-process/session gate ([task.md:L26-30](file:///c:/Users/soyko/Documents/tiny_steward/task.md#L26-L30)).
  - Idle Loop daemon (`core/idle_loop.py`) with memory dreaming & background health checks ([task.md:L12-20](file:///c:/Users/soyko/Documents/tiny_steward/task.md#L12-L20)).
  - Tiny Steward Web UI & 5-Module Agent IDE Platform ([task.md:L36-41](file:///c:/Users/soyko/Documents/tiny_steward/task.md#L36-L41)).
  - Qwythos Web Dashboard (`:11445`) with Launch Control, Live Logs, and SSE Token Echo ([qwythos-daemon.ps1](file:///c:/Users/soyko/Documents/Ollama/docker/llamacpp/qwythos-daemon.ps1)).

---

## 📋 Prioritized Action Roadmap for Today

### 🟢 Block 1: Error Handling & Fallback Hardening (High Priority)
1. **Atomic Model Fallback Logic** ([tiny_plan.md:L9-10](file:///c:/Users/soyko/Documents/tiny_steward/tiny_plan.md#L9-L10))
   - Implement automatic fallback from Atomic (`:11439`) to Orchestrator (`:11440`) when Atomic times out or throws streaming/connection errors.
2. **Structured Exception Hierarchy** ([tiny_plan.md:L6-8](file:///c:/Users/soyko/Documents/tiny_steward/tiny_plan.md#L6-L8))
   - Replace bare warning prints with `LLMTimeoutError`, `EmbeddingError`, and automatic exponential backoff retry policy for flaky local LLM calls.

---

### 🟡 Block 2: Config Validation & Centralized Logging (Mid Priority)
3. **Config Schema Validation** ([tiny_plan.md:L3-5](file:///c:/Users/soyko/Documents/tiny_steward/tiny_plan.md#L3-L5))
   - Validate `config.yaml` against a schema definition during startup in `steward.py` to catch missing or malformed keys early.
4. **Structured Logging Migration** ([tiny_plan.md:L15-17](file:///c:/Users/soyko/Documents/tiny_steward/tiny_plan.md#L15-L17))
   - Replace remaining `print()` statements in `steward.py` and `core/` with Python's standard `logging` library, supporting file & console loggers.

---

### 🔵 Block 3: CLI Usability & Graceful Shutdown (Polish & Reliability)
5. **CLI Flags & Resumption** ([tiny_plan.md:L24-26](file:///c:/Users/soyko/Documents/tiny_steward/tiny_plan.md#L24-L26))
   - Add `--verbose`, `--dry-run`, and `--checkpoint <id>` CLI arguments to `steward.py` for state resumption.
6. **Graceful Shutdown & Request Cleanup** ([tiny_plan.md:L30-31](file:///c:/Users/soyko/Documents/tiny_steward/tiny_plan.md#L30-L31))
   - Implement signal handlers (`SIGINT`/`SIGTERM`) to cancel pending HTTP/LLM streaming requests cleanly on exit.

---

## 📊 Roadmap Timeline Matrix

| Time Window | Focus Area | Target Components | Expected Deliverable |
| :--- | :--- | :--- | :--- |
| **Morning / Now** | Atomic Fallback & Error Resilience | `core/llm_client.py`, `steward.py` | Automatic fallback when subagent is offline/busy |
| **Midday** | Config Validation & Logging | `steward.py`, `config.yaml` | Schema checks & standard `logging` integration |
| **Afternoon** | CLI Flags & Graceful Shutdown | `steward.py`, `core/runtime.py` | Clean `--checkpoint` CLI resumption & SIGINT handling |
