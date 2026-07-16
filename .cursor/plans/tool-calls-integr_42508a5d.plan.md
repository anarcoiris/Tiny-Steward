---
name: tool-calls-integr
overview: Integrate Qwythos (primary) + Qwen (secondary) tool-call chat templates into Tiny Steward’s runtime by adding OpenAI-style `tools` payload injection, a unified `<tool_call>` parser (Qwen JSON and Qwythos XML), tool-result messaging via `role:"tool"`, and `<think>` pruning only for context (while keeping it visible to the user). Maintain retrocompatibility with existing session history without migrating stored messages, and resend the `tools` payload only after tool failures.
todos:
  - id: schemas-tools
    content: Add `PRIMITIVES_TOOLS` + `PRIMARY_ARGS` to `core/primitives.py` aligned to `Runtime._execute_action()` parameter expectations.
    status: completed
  - id: llm-tools-param
    content: Update `core/llm.py` `chat()` + `chat_stream_with_usage()` to accept optional `tools` and inject `body['tools']`.
    status: completed
  - id: display-think-visible
    content: Modify `core/display.py` to stop stripping `<think>` from `_clean_response()` so user sees reasoning after streaming.
    status: completed
  - id: runtime-normalize-prune
    content: Add `strip_think_from_text()` + `normalize_messages_for_llm()` in `core/runtime.py` to prune `<think>` for LLM context and convert legacy `[Result of ...]` user messages into `role:'tool'` messages.
    status: completed
  - id: runtime-unified-extract
    content: Implement unified `extract_actions()` in `core/runtime.py` supporting Qwen JSON `<tool_call>...` and Qwythos XML `<tool_call>...`, then fallback to legacy `<action>` parsing; map args via `PRIMARY_ARGS` into `{name, body, attrs}`.
    status: completed
  - id: runtime-tool-role-results
    content: Update both runtime loops to append tool execution results as `role:'tool'` messages (not `role:'user'`), while keeping existing `display.print_result()` behavior.
    status: completed
  - id: runtime-tools-policy
    content: Implement session-scoped `tools` payload sending policy in `core/runtime.py` (send once per backend per session; resend only on tool parse/execution failures).
    status: completed
  - id: delegate-atomic-loop
    content: Refactor delegate handling so atomic (Qwen) outputs are parsed for tool calls and executed in a bounded nested loop; stream atomic output to the user while pruning `<think>` only in the prompt sent to atomic.
    status: completed
  - id: tests-tooling
    content: Add unit tests for tool-call parsing (Qwen/Qwythos/legacy), message normalization (legacy result->tool role), and tools payload resend policy using mock LLM clients.
    status: completed
isProject: false
---

## Target behavior
1. When the runtime calls either backend, it can include an OpenAI-style `tools` payload (`body["tools"] = tools`) so the backend templates can emit tool calls.
2. The runtime parses tool calls from assistant output using a unified extractor that supports:
   - Qwen JSON `<tool_call> {"name": ..., "arguments": {...}} </tool_call>`
   - Qwythos XML `<tool_call><function=...><parameter=...>...</parameter>...</function></tool_call>`
   - Legacy fallback `<action name=...>...</action>` (unchanged behavior)
3. Tool execution results are appended to the prompt as `role: "tool"` so the templates can group them as `<tool_response>...</tool_response>`.
4. Retrocompatibility: existing sessions that contain legacy tool results as user messages like `[Result of read]\n...` are not migrated on disk. Instead, we normalize them on-the-fly when building the prompt to send to the LLM.
5. `<think>` is shown to the user (streaming + post-stream render), but pruned from the conversation *that is sent back to the LLM* to control context growth.
6. `tools` payload is sent only once per backend per session by default, and resent only when there is a tool parsing/execution failure for a given step (or the parser detects malformed tool-call blocks).

## Concrete implementation plan (files + key edits)

### 1) Define tool schemas + primary-arg mapping
- **File:** [`core/primitives.py`](core/primitives.py)
- Add:
  - `PRIMITIVES_TOOLS: list[dict]` in OpenAI tools format (each entry: `{ "type": "function", "function": {"name", "description", "parameters"}}`).
  - `PRIMARY_ARGS: dict[str, str | None]` mapping tool name -> primary JSON parameter that becomes `action["body"]`. Use `None` for tools where the existing runtime expects data in `action["attrs"]` (not `body`), e.g. `set`.
- Keep schemas aligned to what `Runtime._execute_action()` actually supports.

### 2) Allow passing `tools` to the backend
- **File:** [`core/llm.py`](core/llm.py)
- Update:
  - `LLMClient.chat(..., tools: list[dict] | None = None)`
  - `LLMClient.chat_stream_with_usage(..., tools: list[dict] | None = None)`
  - Thread `tools` into `_build_body()` and inject `body["tools"] = tools` when provided.
- Keep return type unchanged for now (we will parse `<tool_call>` tags from assistant content rather than relying on native OpenAI `tool_calls`).

### 3) Keep `<think>` visible to users
- **File:** [`core/display.py`](core/display.py)
- Modify `_clean_response(text)` to:
  - Continue stripping `<action ...>...</action>` into dim placeholders.
  - **Stop stripping `<think>...</think>`** so post-stream rendering shows it.

### 4) Prune `<think>` only in the prompt sent back to the LLM
- **File:** [`core/runtime.py`](core/runtime.py)
- Add helper(s):
  - `strip_think_from_text(text: str) -> str` using regex `r"<think>.*?</think>"` with DOTALL.
  - `normalize_messages_for_llm(messages: list[dict[str, Any]]) -> list[dict[str, Any]]` that:
    1. Converts legacy tool-result messages:
       - If `role == "user"` and `content` matches `^\[Result of (?P<name>[^\]]+)\]\n(?P<content>[\s\S]*)$`, convert to `{"role":"tool", "name": name, "content": content}`.
    2. Prunes `<think>` blocks from all assistant messages’ `content` before sending.
    3. Leaves the on-disk session history unchanged (retrocompat without migration).

### 5) Unified action/tool-call extraction
- **File:** [`core/runtime.py`](core/runtime.py)
- Replace the current `parse_actions()` usage in the main loops with a new unified extractor:
  - `extract_actions(response_text: str) -> list[dict[str, Any]]`
  - Precedence:
    1. Parse `<tool_call>` blocks:
       - Try Qwen JSON form by extracting the inner JSON and `json.loads()`.
       - If JSON parsing fails, try Qwythos XML form by regex-matching `<function=...>` and `<parameter=...>` blocks.
       - Convert parsed arguments dict to `action = {"name": ..., "body": ..., "attrs": ...}` using `PRIMARY_ARGS`.
    2. Fallback to the legacy `<action name=...>...</action>` parser (existing behavior).
- Ensure the output action dict shape stays compatible with `Runtime._execute_action()`.

### 6) Send tool results as `role:"tool"`
- **File:** [`core/runtime.py`](core/runtime.py)
- In both `run_task()` and `run_interactive()` loops, after executing an action:
  - Replace appending
    - `{"role":"user", "content": "[Result of ...]..."}`
  - with appending
    - `{"role":"tool", "name": action["name"], "content": result_text}`
- Continue printing via `display.print_result()` for the user.

### 7) Tool payload sending policy (once per session; resend on failures)
- **File:** [`core/runtime.py`](core/runtime.py)
- Add session-scoped state keys in `session.metadata`, for example:
  - `tools_payload_sent_primary: bool`
  - `tools_payload_sent_secondary: bool`
  - `force_tools_payload_primary_next: bool`
  - `force_tools_payload_secondary_next: bool`
- On every backend call:
  - `send_tools = (not tools_payload_sent_<backend>) or force_tools_payload_<backend>_next`
  - If `send_tools`, pass `tools=PRIMITIVES_TOOLS` into the LLM call.
- When to set `force_tools_payload_*_next = True`:
  - When the response contains `<tool_call>` but `extract_actions()` returns empty (tool-call parse failure).
  - When an extracted action fails to execute (`_execute_action()` returns an `{"error":...}`) or returns `exit_code != 0` for shell-like tools.
  - After a successful tool execution step, clear the force flag.

### 8) Atomic delegate benefits using the same mechanism
- **Files:**
  - [`core/micro_agent.py`](core/micro_agent.py)
  - [`core/runtime.py`](core/runtime.py)
- Update delegate execution so atomic (Qwen) tool calls are actually executed:
  - Refactor runtime LLM calling helper to accept an arbitrary LLM client (so we can stream from atomic too).
  - In `Runtime._execute_action()` for `delegate`:
    1. Build the micro-agent conversation `messages` (system + user problem/context) using the skill’s `system_prompt` and `skill.body`.
    2. Run a small loop (bounded by e.g. `max_turns` or a new `max_delegate_turns`):
       - Call atomic with `tools` payload according to the same “once per session + resend on tool failures” rules.
       - Parse atomic output with `extract_actions()`.
       - Execute parsed actions via `_execute_action()`.
       - Append results as `role:"tool"` messages for the next atomic prompt.
       - Stop when atomic output contains `DONE` and no further actions.
    3. Return the atomic final answer as the delegate’s `content`.

### 9) Tests
- Add tests that lock in parsing and message normalization without needing real backends.
- **Files:**
  - `tests/test_tool_call_parsing.py`
  - `tests/test_message_normalization.py`
  - `tests/test_tools_payload_policy.py`
- Coverage targets:
  - Qwen JSON `<tool_call>` -> correct `action.body` + `action.attrs` mapping.
  - Qwythos XML `<tool_call>` -> correct parameter extraction.
  - Legacy `<action>` fallback still works.
  - Legacy session `[Result of ...]\n...` normalization -> `role:"tool"` + `content` mapping.
  - Tool payload policy: tools passed on first call; resent only when tool parse/execution fails.

## Data flow (for clarity)
```mermaid
flowchart LR
  UserPrompt[User input] --> Runtime[Runtime reasoning loop]
  Runtime --> Prep[normalize_messages_for_llm(): prune <think> + convert legacy results]
  Prep --> LLMCall[LLMClient chat(..., tools=...)]

  LLMCall --> ModelOut[assistant content with <tool_call> or <action>]
  ModelOut --> Extract[extract_actions(): Qwen JSON + Qwythos XML + legacy fallback]
  Extract --> Exec[Runtime._execute_action()]
  Exec --> ToolMsg[append role:"tool" messages]
  ToolMsg --> LLMCall

  display sees: full streamed output incl. <think>
  LLM sees: messages with <think> pruned
```

## Non-goals for this plan
- No on-disk migration of existing sessions.
- No reliance on native OpenAI `tool_calls` fields from the API; tool calls are parsed from assistant text content.
