# Integrate Qwythos Chat Template Features

This plan outlines the changes needed in the Tiny Steward codebase to take full advantage of the Qwythos LLM backend's chat template, such as native tool XML translation, context pruning (stripping `<think>` blocks on old turns), and centralized prompt instructions.

## User Review Required

> [!IMPORTANT]
> The new XML format for `<tool_call>` does not naturally map to a single `body` text block like the old `<action>` tag did. Most tools take multiple named parameters. We will adjust `parse_actions` to automatically map primary arguments (e.g., `command`, `code`, `content`, `query`) to the old `action["body"]` for backward compatibility, while keeping all other arguments in `action["attrs"]`. Does this sound acceptable?

## Open Questions

> [!WARNING]
> Do you want to remove the old `<action name="...">...</action>` parsing completely, or leave it as a fallback in `parse_actions` just in case a different LLM (like atomic backend) still tries to use it? (We will leave it as a fallback for now unless you instruct otherwise).

## Proposed Changes

### `core/primitives.py`

Define standard OpenAI JSON schemas for all available primitives so they can be sent securely via the `tools` payload.

#### [MODIFY] [primitives.py](file:///c:/Users/soyko/Documents/tiny_steward/core/primitives.py)
- Create a `PRIMITIVES_TOOLS: list[dict]` array containing the JSON schema definition for all 15 primitives (e.g., `pwsh`, `python`, `read`, `write`, `help`, `checkpoint`, `delegate`, etc.).

---

### `core/llm.py`

Update the `LLMClient` to accept and send the `tools` array.

#### [MODIFY] [llm.py](file:///c:/Users/soyko/Documents/tiny_steward/core/llm.py)
- Add `tools: list[dict] | None = None` argument to `chat()` and `chat_stream_with_usage()`.
- Pass `tools` down to `_build_body()`.
- In `_build_body()`, inject `body["tools"] = tools` if tools is provided.

---

### `core/runtime.py`

Integrate the `tools` schema with the system prompt, adjust the parser to handle Qwythos `<tool_call>` XML, and emit `role: "tool"` for execution results to trigger the backend's context optimization.

#### [MODIFY] [runtime.py](file:///c:/Users/soyko/Documents/tiny_steward/core/runtime.py)
- **SYSTEM_PROMPT**: Remove the hardcoded list of primitives and the manual explanation of `<action>`. The Qwythos jinja template automatically injects tool lists and syntax instructions based on the `tools` payload. Keep the persona guidelines, rules, and "when to use help()".
- **`parse_actions(text: str)`**: Introduce a RegEx parser for `<tool_call>\s*<function=...>\s*<parameter=...>...\s*</function>\s*</tool_call>` alongside the legacy `<action>` parser.
- **`run_task` & `run_interactive` Loops**:
  - Pass `tools=PRIMITIVES_TOOLS` into `_call_llm(..., tools=PRIMITIVES_TOOLS)`.
  - When recording tool outputs back into `messages`, replace:
    ```python
    {"role": "user", "content": f"[Result of {action['name']}]\n{result_text}"}
    ```
    with standard tool messages:
    ```python
    {"role": "tool", "name": action["name"], "content": result_text}
    ```
    (The template natively groups `role: "tool"` into `<tool_response>` blocks and uses this to accurately prune old `<think>` blocks for multi-step tasks).

## Verification Plan

### Automated Tests
- Run `pytest tests/` to ensure no unit tests are broken by the parser change. (Tests simulating the old `<action>` syntax should still pass via the fallback parser).

### Manual Verification
- Launch `python steward.py` interactively.
- Execute a multi-step query like "List files in core/ and view llm.py".
- Verify that the model uses the new `<tool_call>` XML format natively.
- Verify that intermediate `<think>` blocks are successfully pruned in subsequent prompts (reducing context bloat) without dropping the current task state.
