# Task: Multi-Provider LLM Fallback System & Extension / Skill / Tool Inspection & Execution

## User Request Goal
Implement a resilient multi-provider LLM fallback engine in Tiny-Steward (supporting local Qwythos/llama.cpp/Ollama and cloud fallbacks like GitHub Models, Groq, OpenRouter, Gemini, OpenAI) and create an Extension/Skill/MCP Tool inspection and execution architecture across CLI REPL and Web IDE.

## Action Plan
- [x] **Phase 1: Research & Architectural Design**
  - [x] Inspect existing `core/llm.py`, `core/providers/`, `core/skill_loader.py`, `core/runtime_meta.py`, `config.yaml`, and `dashboard.html`.
  - [x] Draft `implementation_plan.md` and `plans/llm_fallback_and_extensions_plan.md` for user approval.

- [x] **Phase 2: Multi-Provider LLM Architecture & Resilient Fallback Engine**
  - [x] Refactor `core/llm.py` and `core/providers/` to support a unified `LLMProvider` interface.
  - [x] Implement concrete providers: `LlamaCppProvider`, `OllamaProvider`, `GitHubModelsProvider`, `OpenRouterProvider`, `GroqProvider`, `GeminiProvider`.
  - [x] Implement `ResilientLLMClient` with automatic failover, retry logic, timeout handling, and provider health checks.
  - [x] Update `config.yaml` schema to configure primary and fallback provider chains for `orchestrator` and `atomic` lanes.

- [x] **Phase 3: Extension, Skill & MCP Tool Inspection Architecture**
  - [x] Implement `ExtensionManager` in `core/extensions.py` to inspect, load, and manage Skills, MCP Tools, and custom Python plugin extensions.
  - [x] Enhance `core/skill_loader.py` with extension discovery, health checks, and metadata verification.
  - [x] Expose REPL meta-commands: `/providers` (status & test), `/fallback` (test failover), `/extensions` (list & inspect skills/tools), `/mcp` (manage MCP servers).

- [x] **Phase 4: Web UI Integration & Telemetry**
  - [x] Extend `core/web_server.py` with REST endpoints for `/api/providers/status`, `/api/extensions/list`.
  - [x] Update `dashboard.html` with Provider & Fallback telemetry controls and Extension Inspector pane.

- [x] **Phase 5: Unit Testing & Verification**
  - [x] Add unit tests in `tests/test_llm_providers.py` and `tests/test_extensions.py` validating failover, fallback triggers, and extension discovery.
  - [x] Run full pytest suite ensuring 100% clean passage.