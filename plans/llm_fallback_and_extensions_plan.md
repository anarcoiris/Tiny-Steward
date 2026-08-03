# Architecture Plan: Multi-Provider LLM Fallback Engine & Extension System in Tiny-Steward

## Context & Objectives
The user requested a hybrid fallback LLM engine capable of dynamically failing over between local hardware (Qwythos/llama.cpp/Ollama) and cloud APIs (such as GitHub Models, OpenRouter, Groq, Gemini, OpenAI), as well as a robust inspection and execution mechanism for extensions, skills, and MCP tools within `tiny_steward`.

## Architectural Design

### 1. Multi-Provider LLM & Dynamic Fallback Engine (`core/providers/`, `core/llm.py`)
- **Unified Provider Protocol (`LLMProvider`)**:
  - `chat(messages, max_tokens, temperature, tools) -> str`
  - `chat_stream(messages, max_tokens, temperature, tools) -> Generator[StreamPart]`
  - `check_health() -> bool`
- **Concrete Provider Implementations**:
  - `LlamaCppProvider`: Local llamacpp server (`http://127.0.0.1:11440`).
  - `OllamaProvider`: Local Ollama API (`http://127.0.0.1:11434`).
  - `GitHubModelsProvider`: GitHub Models Gateway (`https://models.github.ai/inference`, using `GITHUB_TOKEN`).
  - `OpenRouterProvider`: OpenRouter Gateway (`https://openrouter.ai/api/v1`, using `OPENROUTER_API_KEY`).
  - `GroqProvider`: Groq Cloud API (`https://api.groq.com/openai/v1`, using `GROQ_API_KEY`).
  - `GeminiProvider`: Google Gemini OpenAI-compatible API (`https://generativelanguage.googleapis.com/v1beta/openai/`, using `GEMINI_API_KEY`).
- **Fallback Controller (`ResilientLLMClient`)**:
  - Primary provider attempt -> On failure (timeout, 503, connection error, rate limit) -> auto failover to secondary provider in fallback list.
  - Active provider status notification: Emits REPL and Web UI events during automatic fallback.

### 2. Extension & Skill & MCP Tool Inspection System (`core/extensions.py`, `core/skill_loader.py`)
- **Unified Extension Registry**:
  - **Skills**: Discoverable markdown skill packages in `skills/`.
  - **MCP Tools**: Integration with Model Context Protocol servers (`nina-mcp`, `chronos_mcp`).
  - **Custom Plugins**: Python plugin modules that extend `tiny_steward` capabilities.
- **Inspection & Management**:
  - `/extensions`: List all registered skills, MCP tools, and plugins.
  - `/providers`: Display current LLM provider status, latencies, and fallback priority chain.
  - `/mcp`: Query active MCP tools, parameters, and server health.

### 3. Verification Plan
- Unit tests covering provider initialization, mock fallback failover on 503/timeout, extension discovery, and MCP tool registry.
- Integration test running `pytest tests/`.
