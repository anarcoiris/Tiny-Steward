# Integrate Multi-Backend Chat Template Features

This plan outlines the changes needed in the Tiny Steward codebase to seize the benefits of both the **Qwythos** (Orchestrator) and **Qwen** (Atomic) LLM backends' chat templates. This includes native tool injection, context pruning, JSON-based `<tool_call>` extraction, and building a backend-agnostic runtime flow.

## Proposed Changes

### 1. `core/primitives.py` (Tool Schemas & Metadata)
To allow the backend templates to inject tool instructions automatically, we will define OpenAI-compatible JSON schemas for all primitives.

- Create a `PRIMITIVES_TOOLS: list[dict]` array containing the JSON schemas for the 15 primitives (e.g., `pwsh`, `python`, `read`, `write`, `help`, `checkpoint`, `delegate`).
- Create a `PRIMARY_ARGS: dict[str, str]` mapping to define the "primary argument" for each primitive (e.g., `{"pwsh": "command", "python": "code", "read": "path"}`). This decouples the parser from the underlying primitive definitions.

### 2. `core/llm.py` (LLMClient Adjustments)
Update the `LLMClient` to handle passing the `tools` array and potentially capturing native `tool_calls`.

- Add `tools: list[dict] | None = None` argument to `chat()` and `chat_stream_with_usage()`.
- Pass `tools` down to `_build_body()` and inject `body["tools"] = tools`.
- Adjust `_stream_response` and `chat` to optionally return `tool_calls` from the API response alongside the `content` string, enabling the runtime to detect if the backend bypassed the Jinja template and returned native JSON tool calls.

### 3. `core/runtime.py` (Unified Action Parsing & Runtime Flow)
Refactor the parsing logic and the runtime execution loop to be completely backend-agnostic, supporting a strict precedence chain.

- **System Prompt**: Remove the hardcoded primitives list and `<action>` syntax instructions from `SYSTEM_PROMPT`. The backend templates will handle injecting this based on the `tools` payload. Keep the persona guidelines, rules, and "when to use help()".
- **Tool Extraction (`extract_tool_calls`)**: Replace `parse_actions` with a unified extractor that tries formats in this precedence:
  1. **Native API `tool_calls`**: If the API directly returns OpenAI-style tool calls.
  2. **Qwen JSON XML**: Parse `<tool_call>{"name": "...", "arguments": {...}}</tool_call>` blocks (extracting JSON using `json.loads`).
  3. **Qwythos XML**: Parse `<tool_call>\n<function=...>\n<parameter=...>` blocks.
  4. **Legacy `<action>`**: Parse `<action name="...">...</action>` as a fallback.
- **Backward Compatibility Mapping**: After extracting the tool name and arguments dictionary, use the `PRIMARY_ARGS` mapping to pop the primary argument into `action["body"]` and place the rest into `action["attrs"]`. This ensures the existing `_execute_action` logic remains untouched.
- **Execution Loop (`run_task` & `run_interactive`)**:
  - Pass `tools=PRIMITIVES_TOOLS` to `_call_llm`.
  - Append tool execution results back to the session history as native tool roles instead of user messages:
    ```python
    {"role": "tool", "name": action["name"], "content": result_text}
    ```
    *(Both backend templates use `message.role == "tool"` to trigger `<tool_response>` grouping and accurately calculate reasoning pruning boundaries for multi-step workflows).*

## Verification Plan

### Automated Tests
- Run `pytest tests/` to ensure the new parsing logic doesn't break existing tests, particularly ensuring the legacy `<action>` fallback behaves correctly.

### Manual Verification
- Launch `python steward.py` interactively.
- Execute a multi-step query utilizing both backends (e.g., using a delegate action that routes to the Qwen atomic backend).
- Verify the orchestrator uses its specific template syntax while the atomic backend successfully uses the JSON `<tool_call>` format, and both are correctly extracted by the unified parser.
- Verify that intermediate `<think>` blocks are successfully pruned in subsequent prompts by inspecting the context length and logs.
