# Task: Cross-Process & Cross-Session Shared Execution Lock & Idle Loop Status Visibility

## User Request Goal
Automatize a continuous loop in Tiny-Steward that uses idle time to stay alert (monitor mailboxes, background tasks, alerts), dream (memory consolidation), and perform self-health state checks, while ensuring it never overlaps active/running user processes using semaphores/gates, and display its full shared status between processes and sessions.

## Action Plan
- [x] **Phase 1: Research & Architectural Design**
  - [x] Inspect existing `core/backend_gate.py`, `core/dreaming.py`, `core/mailbox.py`, `steward.py`, and `core/runtime.py` / `core/runtime_loop.py`.
  - [x] Design process concurrency guard (`SharedExecutionLock`) + `BackendGate` priority integration to prevent overlap with active reasoning or tool execution.
  - [x] Draft `implementation_plan.md` and obtain user approval.

- [x] **Phase 2: Core Idle Loop Implementation (`core/idle_loop.py`)**
  - [x] Create `core/idle_loop.py` containing `IdleLoop` daemon class.
  - [x] Implement `SharedExecutionLock` ensuring non-overlapping execution across processes and sessions.
  - [x] Implement modular background idle routines:
    - `_do_health_check()`: monitor VRAM, backend LLMs, CPU/GPU, launcher status.
    - `_do_dream_check()`: auto-trigger `run_dream()` when un-dreamed think entries exist and system is idle.
    - `_do_alert_check()`: poll mailbox for inter-agent messages / notifications.
  - [x] Support graceful start/stop/trigger_now.

- [x] **Phase 3: Runtime & CLI Integration**
  - [x] Add `idle_loop` section in `config.yaml`.
  - [x] Integrate `IdleLoop` start/stop in `steward.py` and `Runtime.run_interactive()` / REPL prompt loop.
  - [x] Add `/idle status|start|stop|run` slash command in `core/runtime_meta.py`.

- [x] **Phase 4: Cross-Process & Cross-Session Shared Semaphore Implementation**
  - [x] Update `SharedExecutionLock` in `core/idle_loop.py` to use OS file locking (`sessions/.execution.lock`) + atomic lock registry (`sessions/.lock_registry.json`).
  - [x] Add stale PID detection (`_is_pid_alive`) and cleanup so crashed sessions/processes release locks automatically.
  - [x] Implement `get_shared_status()` returning active lock holder (PID, session), registered processes, and lock states across all sessions.
  - [x] Format and display cross-process & cross-session shared status table in `/idle status`.

- [x] **Phase 5: Unit Testing & Verification**
  - [x] Add cross-process / multi-session unit tests in `tests/test_idle_loop.py`.
  - [x] Run full pytest suite (142/142 passed cleanly).

- [x] **Phase 6: Tiny Steward Web UI & Agent IDE Platform**
  - [x] Deep research & architecture design for Web UI / Agent IDE platform.
  - [x] Implement `core/web_server.py` with REST, SSE/WebSocket endpoints (Chat, Sessions, Files, Tasks, Telemetry, Memory).
  - [x] Upgrade `dashboard.html` to modern 5-module Web IDE SPA (Chat, File Editor, Kanban Board, Memory Graph, Telemetry).
  - [x] Integrate real-time streaming, `<think>` block toggles, and `SharedExecutionLock` concurrency protection.
  - [x] Add unit & end-to-end integration tests for web endpoints (168/168 tests passed cleanly).