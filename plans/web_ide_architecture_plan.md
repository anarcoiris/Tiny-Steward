# Design Document: Tiny Steward Web UI & Agent IDE Platform (Detailed Reflection)

## Architecture Summary
- **Backend**: FastAPI + Uvicorn (`core/web_server.py`) serving REST endpoints, SSE streaming for LLM tokens/reasoning/tools, static files, and process lock integration.
- **Frontend**: Zero-build Vanilla ES Modules (`web/js/*.js`, `web/css/*.css`, `dashboard.html`).
- **Default View**: Agent Chat & REPL Playground.

## Directory Structure
```
tiny_steward/
├── dashboard.html             # Shell & Layout SPA entry point
├── serve.py                   # FastAPI / Uvicorn server launcher
├── core/
│   └── web_server.py          # FastAPI REST & SSE streaming API
└── web/
    ├── css/
    │   ├── main.css           # Global resets, HSL design system & Glassmorphic variables
    │   └── components.css     # Component styling (chat, editor, kanban, telemetry)
    └── js/
        ├── app.js             # Main router, AppState & tab events
        ├── api.js             # Centralized fetch & SSE API client
        └── components/
            ├── chat.js        # Token streaming, <think> details, tool badges
            ├── editor.js      # File tree & lightweight code editor
            ├── kanban.js      # Task & Plan Kanban board (task.md & plan.md)
            ├── graph.js       # D3 / Force Graph memory visualizer
            └── telemetry.js   # GPU metrics (nvidia-smi) & backend health
```

## Technical Implementation Highlights

### 1. State Management (`app.js`)
Centralized `AppState` object:
```javascript
export const AppState = {
  activeTab: 'chat',
  session: 'default',
  connected: false,
  tasks: [],
  gpus: [],
  lockStatus: null
};
```
Inter-component communication via native `CustomEvent` dispatching on `window`.

### 2. Real-Time Token & Reasoning Streaming (`chat.js`)
- Consumes SSE (`ReadableStream`) from `POST /api/chat/stream`.
- Reasoning content parsed dynamically into `<details open><summary>🧠 Reasoning Chain</summary><div class="think-content">...</div></details>`.
- Token text appended atomically to preserve smooth layout rendering.

### 3. File Editor & Task Synchronization (`editor.js` & `kanban.js`)
- Workspace tree fetched via `GET /api/files/tree` (respecting ignore patterns).
- Diffs rendered side-by-side.
- Kanban board updates sync bidirectionally with `task.md` and `plan.md`.
