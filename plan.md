# Subjacent Issues Audit & Remediation Plan

## Objective
Conduct a comprehensive static analysis and runtime edge-case audit across `tiny_steward` and `Pulse-main` to discover latent bugs, improper error handling, unhandled edge cases in tool call parsing, delegate IPC, multi-provider failover, and session state persistence.

---

## Target Investigation Areas

### 1. `tiny_steward` Core Runtime & Action Execution
- **Delegate Child Loop (`core/runtime_delegate.py`)**:
  - Check how `_run_delegate_loop` handles action errors and tool call parsing.
  - Verify if `_process_response_actions` return type change `(had_actions, errors: list[str])` affects `runtime_delegate.py` or `runtime_meta.py`.
- **Tool Parsing Robustness (`core/action_parse.py`, `core/providers/`)**:
  - Inspect Qwen JSON parsing when JSON is partially truncated (`parse_qwen_tool_call`).
  - Inspect parameter extraction when parameter names contain hyphen/underscore or odd spacing.
  - Inspect legacy `<action>` fallback behavior when `<tool_call>` tags are mixed or malformed.
- **LLM Streaming & Retry Logic (`core/llm.py`)**:
  - Check stream timeout handling, 503 slot-busy retry loop, and `reasoning_content` merging.
  - Audit fallback provider failover in `LLMClient`.

### 2. `Pulse-main` LLM & Providers Architecture
- **Provider Protocol & Implementations (`knowledge/providers/llm_provider.py`)**:
  - Audit exception handling (are HTTP 429, 503, timeouts properly mapped to `LLMProviderError` / `FallbackException`?).
  - Check header formatting, Bearer token handling, streaming responses vs non-streaming responses.
  - Verify payload building (`tools`, `temperature`, `max_tokens`) across OpenRouter, GitHub Models, Groq, Gemini, Ollama, LlamaCpp.
- **Failover Engine (`knowledge/llm_client.py`)**:
  - Audit failover logic when primary provider fails mid-stream or during non-streaming call.

---

## Execution Steps
1. Perform static analysis across all listed files using `grep_search` and `view_file`.
2. Document all discovered subjacent issues, categorized by severity and component.
3. Propose fixes and unit tests for each issue.
4. Obtain approval and execute fixes.
