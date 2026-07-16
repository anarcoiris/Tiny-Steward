"""Runtime — the main reasoning loop.

The orchestrator sends the conversation to the LLM, parses action tags
from the response, executes them, and feeds results back into the
conversation. The help() action triggers semantic skill search.

Action format (XML-tagged in LLM response):
  <action name="pwsh">Get-ChildItem</action>
  <action name="help">Permission denied publickey</action>
  <action name="write" path="file.txt">content here</action>
  <action name="http" method="GET">https://example.com</action>
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from core.llm import LLMClient, estimate_messages_tokens, estimate_tokens
from core.primitives import PRIMITIVES, PRIMITIVES_TOOLS, PRIMARY_ARGS
from core.help import HelpEngine
from core.session import Session, SessionManager
from core.stats import SessionStats
from core.guidance import GuidanceEngine
from core.interaction_log import InteractionLog
import core.display as display


import sys

_OS_PATH_RULE = (
    "- Use relative paths (e.g. `skills/`) or valid Windows paths (e.g. `C:\\...`). Do NOT use Unix-style absolute paths (e.g. `/skills`) as they resolve to `C:\\skills` on Windows."
    if sys.platform == "win32"
    else "- Use relative paths (e.g. `skills/`) or valid Unix absolute paths (e.g. `/home/user/...`)."
)

# ------------------------------------------------------------------
# System prompt — intentionally tiny (~600 tokens)
# ------------------------------------------------------------------
SYSTEM_PROMPT = f"""\
You are Tiny Steward, a task executor with a minimal set of primitive actions.

## Available primitives

- pwsh(command): execute a PowerShell command (primary shell)
- bash(command): execute a bash command (via WSL on Windows)
- python(code): execute a Python snippet
- read(path, start_line?, end_line?): read file contents (default capped to 500 lines)
- write(path, content): create/overwrite a file
- append(path, content): append to a file
- mkdir(path): create directory
- ls(path): list directory contents
- grep(pattern, path): search for text in files
- http(method, url, body?): make an HTTP request
- mcp(tool, body?): execute a tool on the nina-mcp server
- delegate(agent, task): delegate a task to a specialist micro-agent (e.g. nda_review)
- help(query): discover capabilities for a problem or error
- set(key, value): tweak config parameters dynamically (e.g. temperature, max_tokens, thinking)
- checkpoint(note): manually save your state and write a steering note before a complex or risky task

## How to act

Respond with actions using XML tags:

<action name="pwsh">Get-ChildItem -Recurse</action>
<action name="read" path="config.yaml" start_line="1" end_line="50"></action>
<action name="write" path="output.txt">file content here</action>
<action name="http" method="POST" url="http://example.com">{{"key": "value"}}</action>
<action name="mcp" tool="nina_camera_capture">{{"duration": 1, "save": false}}</action>
<action name="delegate" agent="nda_review">Review the Acme NDA text below...</action>
<action name="help">container won't start</action>
<action name="checkpoint">I am about to rewrite the index, if I crash I will retry with smaller chunks.</action>

## When to use help()

Call help() when you:
- Encounter an error you're unsure how to fix
- Need a capability outside your primitives
- Want guidance on a domain-specific task (git, docker, python env, etc.)

help() returns relevant skill documents. Read them and continue working.
You can call help() multiple times with narrower queries.

## Rules

- Execute one action at a time. Wait for the result before continuing.
- Explain your reasoning briefly before each action.
{_OS_PATH_RULE}
- When a task is complete, say DONE and summarize what was accomplished.
- If you're stuck after 3 help() calls on the same problem, ask the user.
"""


# ------------------------------------------------------------------
# Action parsing
# ------------------------------------------------------------------


# More flexible: capture all attributes
ATTR_PATTERN = re.compile(r'(\w+)="([^"]*)"')
TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
LEGACY_RESULT_RE = re.compile(r"^\[Result of (?P<name>[^\]]+)\]\n(?P<content>[\s\S]*)$")
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
QWEN_PARAM_RE = re.compile(r"<parameter=([^>]+)>\n?(.*?)\n?</parameter>", re.DOTALL)


def strip_think_from_text(text: str) -> str:
    """Remove <think> blocks (for LLM context only)."""
    return THINK_RE.sub("", text).strip()


def normalize_messages_for_llm(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prepare messages for the backend: legacy result conversion + think pruning."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        m = dict(msg)
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "user" and isinstance(content, str):
            legacy = LEGACY_RESULT_RE.match(content)
            if legacy:
                m = {
                    "role": "tool",
                    "name": legacy.group("name"),
                    "content": legacy.group("content"),
                }
        if m.get("role") == "assistant" and isinstance(m.get("content"), str):
            m["content"] = strip_think_from_text(m["content"])
        out.append(m)
    return out


def _args_to_action(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Map tool arguments dict to legacy action shape {name, body, attrs}."""
    primary = PRIMARY_ARGS.get(name)
    attrs = {k: str(v) if v is not None else "" for k, v in args.items()}
    body = ""
    if primary is None:
        body = ""
    elif primary in attrs:
        body = attrs.pop(primary)
    return {"name": name, "body": body, "attrs": attrs}


def _parse_qwen_tool_call(inner: str) -> dict[str, Any] | None:
    inner = inner.strip()
    try:
        data = json.loads(inner)
        name = data.get("name")
        args = data.get("arguments", {})
        if isinstance(args, str):
            args = json.loads(args)
        if name and isinstance(args, dict):
            return _args_to_action(name, args)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _parse_qwythos_tool_call(inner: str) -> dict[str, Any] | None:
    fn_match = re.search(r"<function=([^>]+)>", inner)
    if not fn_match:
        return None
    name = fn_match.group(1).strip()
    args: dict[str, Any] = {}
    for param_match in QWEN_PARAM_RE.finditer(inner):
        args[param_match.group(1).strip()] = param_match.group(2).strip()
    return _args_to_action(name, args)


def parse_actions(text: str) -> list[dict[str, Any]]:
    """Parse legacy <action> tags from LLM response text."""
    actions: list[dict[str, Any]] = []

    for match in re.finditer(r'<action\s+(.*?)>(.*?)</action>', text, re.DOTALL):
        attrs_str = match.group(1)
        body = match.group(2).strip()

        attrs = dict(ATTR_PATTERN.findall(attrs_str))
        name = attrs.pop("name", None)
        if not name:
            continue

        actions.append({
            "name": name,
            "body": body,
            "attrs": attrs,
        })

    return actions


def extract_actions(text: str) -> list[dict[str, Any]]:
    """Unified extractor: Qwen JSON / Qwythos XML <tool_call>, then legacy <action>."""
    if "<tool_call>" in text:
        actions: list[dict[str, Any]] = []
        for match in TOOL_CALL_RE.finditer(text):
            inner = match.group(1)
            action = _parse_qwen_tool_call(inner) or _parse_qwythos_tool_call(inner)
            if action:
                actions.append(action)
        if actions:
            return actions
    return parse_actions(text)


# ------------------------------------------------------------------
# Runtime
# ------------------------------------------------------------------
class Runtime:
    """The main reasoning loop."""

    def __init__(
        self,
        llm: LLMClient,
        help_engine: HelpEngine,
        session: Session,
        *,
        max_turns: int = 50,
        context_budget: int = 26000,        # tokens, leave room below 32k
        use_streaming: bool = True,
        use_markdown: bool = True,
        show_stats: bool = True,
        checkpoint_every: int = 5,          # auto-checkpoint every N turns
        atomic_llm: LLMClient | None = None,
        shortcuts: dict[str, str] | None = None,
        max_delegate_turns: int = 10,
    ):
        self.llm = llm
        self.help_engine = help_engine
        self.session = session
        self.max_turns = max_turns
        self.context_budget = context_budget
        self.use_streaming = use_streaming
        self.use_markdown = use_markdown
        self.show_stats = show_stats
        self.checkpoint_every = checkpoint_every
        self.atomic_llm = atomic_llm
        self.max_delegate_turns = max_delegate_turns
        self.shortcuts = shortcuts or {
            "send": "escape, enter",
            "newline": "c-j"
        }

        # Session stats accumulator
        self.session_stats = SessionStats()
        # Reference to the session manager (attached externally)
        self.session_manager: SessionManager | None = None
        
        self.guidance_engine = GuidanceEngine()
        # Ensure session manager's directory is available for InteractionLog
        log_dir = session.name  # fallback placeholder
        self.interaction_log = None  # Will be initialized once we know log_dir

    def _init_interaction_log(self):
        if not self.interaction_log and self.session_manager:
            self.interaction_log = InteractionLog(self.session_manager.dir, self.session.name)

    # ------------------------------------------------------------------
    # Tools payload policy (once per session per backend; resend on failure)
    # ------------------------------------------------------------------
    def _tools_sent_key(self, backend: str) -> str:
        return f"tools_payload_sent_{'primary' if backend == 'primary' else 'secondary'}"

    def _tools_force_key(self, backend: str) -> str:
        return f"force_tools_payload_{'primary' if backend == 'primary' else 'secondary'}_next"

    def _should_send_tools(self, backend: str) -> bool:
        if self.session.metadata.get(self._tools_force_key(backend)):
            return True
        return not self.session.metadata.get(self._tools_sent_key(backend))

    def _mark_tools_sent(self, backend: str) -> None:
        self.session.metadata[self._tools_sent_key(backend)] = True
        self.session.metadata[self._tools_force_key(backend)] = False

    def _force_tools_resend(self, backend: str) -> None:
        self.session.metadata[self._tools_force_key(backend)] = True

    def _tools_for_skill(self, skill) -> list[dict]:
        if not skill.requires:
            return PRIMITIVES_TOOLS
        allowed = set(skill.requires) | {"help"}
        return [t for t in PRIMITIVES_TOOLS if t["function"]["name"] in allowed]

    def _append_tool_result(
        self,
        messages: list[dict[str, Any]],
        action_name: str,
        result_text: str,
        *,
        persist: bool = True,
    ) -> None:
        tool_msg = {"role": "tool", "name": action_name, "content": result_text}
        messages.append(tool_msg)
        if persist:
            self.session.add_message("tool", result_text, name=action_name)

    def _action_failed(self, result: dict[str, Any] | str) -> bool:
        if isinstance(result, dict):
            if "error" in result:
                return True
            if result.get("exit_code", 0) != 0:
                return True
        return False

    def _process_response_actions(
        self,
        response: str,
        messages: list[dict[str, Any]],
        *,
        backend: str = "primary",
        allow_delegate: bool = True,
        log_actions: bool = False,
    ) -> tuple[bool, int]:
        """Execute actions from an LLM response. Returns (had_actions, error_count)."""
        if "<tool_call>" in response and not extract_actions(response):
            self._force_tools_resend(backend)

        actions = extract_actions(response)
        if not actions:
            return False, 0

        errors = 0
        for action in actions:
            display.print_action_placeholder(action["name"], action.get("body", ""))
            result = self._execute_action(action, allow_delegate=allow_delegate)
            result_text = self._format_result(action["name"], result)
            is_error = self._action_failed(result)

            if log_actions and self.interaction_log:
                code = result.get("exit_code", 0) if isinstance(result, dict) else 0
                if is_error and code == 0:
                    code = 1
                self.interaction_log.record_action(action["name"], action.get("body", ""), code)

            display.print_result(action["name"], result_text, is_error=is_error)
            self._append_tool_result(messages, action["name"], result_text)

            if is_error:
                errors += 1
                self._force_tools_resend(backend)

        return True, errors

    # ------------------------------------------------------------------
    # Public: run a single task
    # ------------------------------------------------------------------
    def run_task(self, task: str) -> str:
        """Execute a task through the reasoning loop."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if self.session.messages:
            history = self.session.messages[-20:]
            messages.extend(history)

        if estimate_messages_tokens(messages) > self.context_budget:
            messages = self._compact_messages(messages)

        messages.append({"role": "user", "content": task})
        self.session.add_message("user", task)

        for turn in range(1, self.max_turns + 1):
            compaction_triggered = False
            token_est = estimate_messages_tokens(messages)
            if token_est > self.context_budget:
                messages = self._compact_messages(messages)
                compaction_triggered = True

            response, usage, elapsed = self._call_llm(messages, turn=turn)
            if response is None:
                return "[LLM error]"

            messages.append({"role": "assistant", "content": response})
            self.session.add_message("assistant", response)

            self._emit_stats(
                turn=turn,
                messages_before=messages[:-1],
                response=response,
                elapsed=elapsed,
                usage=usage,
                compaction_triggered=compaction_triggered,
            )

            if "DONE" in response and not extract_actions(response):
                return response

            had_actions, _ = self._process_response_actions(response, messages, backend="primary")
            if not had_actions:
                return response

        return "[Max turns reached]"

    # ------------------------------------------------------------------
    # Public: interactive REPL
    # ------------------------------------------------------------------
    def run_interactive(self):
        """Interactive REPL mode."""
        display.banner(
            session_name=self.session.name,
            skills_count=self.help_engine.index.size,
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if self.session.messages:
            recent = self.session.messages[-20:]
            messages.extend(recent)
            display.print_event("info", f"Restored {len(recent)} messages from session '{self.session.name}'")

        if estimate_messages_tokens(messages) > self.context_budget:
            messages = self._compact_messages(messages)
            display.print_event("compact", "Session history compacted to fit context budget")

        try:
            from prompt_toolkit import PromptSession
            from prompt_toolkit.formatted_text import ANSI
            from prompt_toolkit.key_binding import KeyBindings
            
            bindings = KeyBindings()
            hint_active = False
            
            def get_bottom_toolbar():
                if hint_active:
                    send_key = self.shortcuts.get('send', 'escape, enter')
                    nl_key = self.shortcuts.get('newline', 'c-j')
                    return f" [Hint] Press '{send_key}' to send, '{nl_key}' for a new line."
                return ""
                
            send_keys = [k.strip() for k in self.shortcuts.get('send', 'escape, enter').split(',')]
            @bindings.add(*send_keys)
            def _(event):
                nonlocal hint_active
                hint_active = False
                event.current_buffer.validate_and_handle()

            nl_keys = [k.strip() for k in self.shortcuts.get('newline', 'c-j').split(',')]
            @bindings.add(*nl_keys)
            def _(event):
                nonlocal hint_active
                hint_active = False
                event.current_buffer.insert_text('\n')

            @bindings.add('enter')
            def _(event):
                nonlocal hint_active
                hint_active = True
                event.app.invalidate()
                
            prompt_session = PromptSession(key_bindings=bindings, multiline=True, bottom_toolbar=get_bottom_toolbar)
        except ImportError:
            prompt_session = None

        while True:
            try:
                if prompt_session:
                    user_input = prompt_session.prompt(ANSI(display.prompt_text())).strip()
                else:
                    user_input = input(display.prompt_text()).strip()
                user_input = user_input.encode('utf-8', 'replace').decode('utf-8')
            except (EOFError, KeyboardInterrupt):
                display.print_event("info", "Bye.")
                break

            if not user_input:
                continue

            # Meta commands
            if user_input.startswith("/"):
                handled = self._handle_meta_command(user_input, messages)
                if handled == "quit":
                    break
                if handled:
                    continue

            # Add user message
            messages.append({"role": "user", "content": user_input})
            self.session.add_message("user", user_input)
            
            self._init_interaction_log()
            if self.interaction_log:
                self.interaction_log.begin_interaction(user_input)

            # Reasoning loop for this turn
            global_turn = self.session_stats.total_turns
            outcome = "unknown"
            errors_in_turn = 0
            help_calls = 0
            task_start_time = time.monotonic()
            
            for turn in range(1, self.max_turns + 1):
                compaction_triggered = False
                token_est = estimate_messages_tokens(messages)
                if token_est > self.context_budget:
                    messages = self._compact_messages(messages)
                    compaction_triggered = True
                    display.print_event(
                        "compact",
                        f"Context compacted — budget {self.context_budget:,} tokens"
                    )

                response, usage, elapsed = self._call_llm(messages, turn=turn)
                if response is None:
                    break

                messages.append({"role": "assistant", "content": response})
                self.session.add_message("assistant", response)

                # Stats + optional auto-checkpoint
                budget_used = token_est / self.context_budget
                turn_stats, checkpoint_saved = self._emit_stats(
                    turn=global_turn + turn,
                    messages_before=messages[:-1],
                    response=response,
                    elapsed=elapsed,
                    usage=usage,
                    compaction_triggered=compaction_triggered,
                    context_budget_used=budget_used,
                )
                
                # Meta Guidance
                hints = self.guidance_engine.evaluate(
                    turn_stats=turn_stats,
                    session_stats=self.session_stats,
                    recent_errors=errors_in_turn,
                    help_calls=help_calls,
                    turns_this_task=turn,
                )
                display.print_guidance(hints)

                actions = extract_actions(response)
                if not actions:
                    outcome = "success"
                    break

                for action in actions:
                    if action["name"] == "help":
                        help_calls += 1

                _, errors_in_turn = self._process_response_actions(
                    response,
                    messages,
                    backend="primary",
                    log_actions=True,
                )

                if "DONE" in response:
                    outcome = "success"
                    break
            else:
                outcome = "max_turns_reached"

            if self.interaction_log:
                total_elapsed = time.monotonic() - task_start_time
                self.interaction_log.end_interaction(outcome, turn, 0, 0, total_elapsed)  # We could track total tokens here if needed
                
            display.print_separator()

    # ------------------------------------------------------------------
    # LLM call — streaming or blocking
    # ------------------------------------------------------------------
    def _call_llm(
        self,
        messages: list[dict[str, Any]],
        *,
        turn: int,
        backend: str = "primary",
        llm: LLMClient | None = None,
        tools_override: list[dict] | None = None,
        force_no_tools: bool = False,
    ) -> tuple[str | None, dict | None, float]:
        """Call the LLM. Returns (response_text, usage_dict_or_None, elapsed_s)."""
        client = llm or (self.atomic_llm if backend == "secondary" else self.llm)
        if client is None:
            display.print_event("error", "LLM client not configured")
            return None, None, 0.0

        tools: list[dict] | None = None
        if not force_no_tools:
            if tools_override is not None:
                tools = tools_override
            elif self._should_send_tools(backend):
                tools = PRIMITIVES_TOOLS

        llm_messages = normalize_messages_for_llm(messages)
        t0 = time.monotonic()
        usage: dict | None = None

        try:
            if self.use_streaming:
                response = self._stream_response(llm_messages, client=client, tools=tools)
                usage = getattr(self, "_last_usage", None)
            else:
                response = client.chat(llm_messages, tools=tools)
        except Exception as e:
            display.print_event("error", f"LLM error: {e}")
            return None, None, time.monotonic() - t0

        if tools is not None:
            self._mark_tools_sent(backend)

        elapsed = time.monotonic() - t0
        return response, usage, elapsed

    def _stream_response(
        self,
        messages: list[dict[str, Any]],
        *,
        client: LLMClient | None = None,
        tools: list[dict] | None = None,
    ) -> str:
        """Stream the LLM response token-by-token, render it, and return full text."""
        llm = client or self.llm
        display.print_response_stream_start()
        chunks: list[str] = []
        usage: dict | None = None

        gen = llm.chat_stream_with_usage(messages, tools=tools)
        try:
            while True:
                chunk = next(gen)
                display.print_stream_chunk(chunk)
                chunks.append(chunk)
        except StopIteration as e:
            usage = e.value

        display.print_stream_end()
        full_response = "".join(chunks)

        # If markdown mode, re-render the cleaned text nicely after streaming
        if self.use_markdown:
            from core.display import _clean_response, _RICH, _console
            from rich.markdown import Markdown  # type: ignore
            clean = _clean_response(full_response)
            if clean and _RICH and _console:
                _console.print(Markdown(clean, code_theme="monokai"))

        self._last_usage = usage  # stash for _emit_stats
        return full_response

    # ------------------------------------------------------------------
    # Stats emission + auto-checkpoint
    # ------------------------------------------------------------------
    def _emit_stats(
        self,
        turn: int,
        messages_before: list[dict[str, str]],
        response: str,
        elapsed: float,
        usage: dict | None,
        compaction_triggered: bool,
        context_budget_used: float = 0.0,
    ) -> tuple['TurnStats', bool]:
        """Record stats, emit the stats line, and handle auto-checkpoint.
        Returns (TurnStats, checkpoint_saved)."""
        prompt_est = estimate_messages_tokens(messages_before)
        completion_est = estimate_tokens(response)

        real_prompt = usage.get("prompt_tokens") if usage else None
        real_completion = usage.get("completion_tokens") if usage else None

        # Auto-checkpoint check
        checkpoint_saved = False
        if (
            self.checkpoint_every > 0
            and self.session_stats.total_turns > 0
            and self.session_stats.total_turns % self.checkpoint_every == 0
        ):
            self._save_checkpoint()
            checkpoint_saved = True

        turn_stats = self.session_stats.record_turn(
            turn=turn,
            prompt_tokens_est=prompt_est,
            completion_tokens_est=completion_est,
            elapsed_s=elapsed,
            prompt_tokens_real=real_prompt,
            completion_tokens_real=real_completion,
            compaction_triggered=compaction_triggered,
            checkpoint_saved=checkpoint_saved,
            context_budget_used=context_budget_used,
        )

        if self.show_stats:
            display.print_stats(turn_stats)

        if checkpoint_saved:
            display.print_event("checkpoint", f"Auto-checkpoint saved (every {self.checkpoint_every} turns)")

        return turn_stats, checkpoint_saved

    def _save_checkpoint(self):
        """Save the current session to disk as a checkpoint."""
        if self.session_manager:
            self.session_manager.save()

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------
    def _execute_action(self, action: dict[str, Any], *, allow_delegate: bool = True) -> dict[str, Any] | str:
        """Execute a single parsed action."""
        name = action["name"]
        body = action["body"]
        attrs = action.get("attrs", {})

        if name == "help":
            result = self.help_engine.search(body)
            if "📖" in result or "🗂️" in result:
                for line in result.split("\n"):
                    if line.startswith("## 📖") or line.startswith("## 🗂️"):
                        parts = line.split("(")
                        if len(parts) > 1:
                            skill_name = parts[0].replace("## 📖", "").replace("## 🗂️", "").strip()
                            self.session.record_skill(skill_name.lower().replace(" ", "_"))
            return {"content": result}

        if name == "checkpoint":
            if self.session_manager:
                self.session.metadata["last_checkpoint_note"] = body
                self._save_checkpoint()
                return {"content": f"Checkpoint saved with note: {body}"}
            else:
                return {"error": "Session manager not available, cannot save checkpoint."}

        if name == "delegate":
            if not allow_delegate:
                return {"error": "Nested delegate not allowed in micro-agent"}
            agent_slug = attrs.get("agent") or attrs.get("skill") or body
            problem = body
            skill = self.help_engine.index.get_by_slug(agent_slug)
            if not skill:
                skill = self.help_engine.index.get_by_name(agent_slug)
            if not skill:
                return {"error": f"Agent or skill '{agent_slug}' not found."}

            if not self.atomic_llm:
                return {"error": "Delegate action failed: no atomic LLM configured. Please specify an atomic model in config.yaml."}

            context_messages = []
            for msg in self.session.messages[-12:]:
                context_messages.append(f"{msg['role'].upper()}: {msg['content']}")
            context_text = "\n".join(context_messages)

            playbook_content = ""
            if "legal/" in skill.path:
                skills_root = Path("skills")
                claude_path = skills_root / "legal" / "CLAUDE.md"
                if claude_path.exists():
                    try:
                        playbook_content = claude_path.read_text(encoding="utf-8")
                    except Exception as e:
                        playbook_content = f"[Warning: Failed to read CLAUDE.md: {e}]"

            if playbook_content:
                context_text = (
                    f"PLAYBOOK CONFIGURATION (CLAUDE.md):\n"
                    f"==================================================\n"
                    f"{playbook_content}\n"
                    f"==================================================\n\n"
                    f"{context_text}"
                )

            result = self._run_delegate_loop(skill, problem, context_text)
            return {"content": result}

        primitive = PRIMITIVES.get(name)
        if not primitive:
            return {"error": f"Unknown action: {name}. Use help() to discover capabilities."}

        try:
            if name in ("pwsh", "bash"):
                return primitive(body, cwd=attrs.get("cwd"))
            elif name == "python":
                return primitive(body)
            elif name == "read":
                path = attrs.get("path") or body
                start_line = int(attrs["start_line"]) if "start_line" in attrs else None
                end_line = int(attrs["end_line"]) if "end_line" in attrs else None
                return primitive(path, start_line, end_line)
            elif name == "write":
                path = attrs.get("path", "")
                return primitive(path, body)
            elif name == "append":
                path = attrs.get("path", "")
                return primitive(path, body)
            elif name == "mkdir":
                return primitive(body)
            elif name == "ls":
                return primitive(body or ".")
            elif name == "grep":
                path = attrs.get("path", ".")
                return primitive(body, path)
            elif name == "http":
                method = attrs.get("method", "GET")
                url = attrs.get("url") or body
                http_body = body if attrs.get("url") else None
                return primitive(method, url, http_body)
            elif name == "mcp":
                tool = attrs.get("tool", "")
                return primitive(tool, body)
            elif name == "set":
                key = attrs.get("key")
                val = attrs.get("value")
                if not key or not val:
                    return {"error": "Missing key or value in set action"}
                msg = self._handle_set(f"{key} {val}")
                return {"content": msg}
            else:
                return primitive(body)
        except Exception as e:
            return {"error": f"Action {name} failed: {e}"}

    def _build_delegate_system_prompt(self, skill) -> str:
        prompt_parts = []
        if getattr(skill, "system_prompt", None):
            prompt_parts.append(skill.system_prompt)
        else:
            prompt_parts.append(f"You are a specialist agent executing the skill: {skill.name}.")
            if skill.description:
                prompt_parts.append(skill.description)

        prompt_parts.append(
            "Here are your step-by-step instructions, guidelines, and output formatting rules:\n"
            "==================================================\n"
            f"{skill.body}\n"
            "=================================================="
        )
        if skill.requires:
            prompt_parts.append(f"Available tools / primitives: {', '.join(skill.requires)}")
        prompt_parts.append(
            "Adhere strictly to the guidelines and templates. Be extremely concise, professional, and actionable."
        )
        return "\n\n".join(prompt_parts)

    def _run_delegate_loop(self, skill, problem: str, context_text: str) -> str:
        """Run atomic (Qwen) micro-agent with tool-call loop."""
        system_prompt = self._build_delegate_system_prompt(skill)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Problem:\n{problem}\n\nContext:\n{context_text}"},
        ]
        skill_tools = self._tools_for_skill(skill)
        final_response = ""

        for _ in range(self.max_delegate_turns):
            send_tools = self._should_send_tools("secondary")

            response, _, _ = self._call_llm(
                messages,
                turn=0,
                backend="secondary",
                llm=self.atomic_llm,
                tools_override=skill_tools if send_tools else None,
                force_no_tools=not send_tools,
            )
            if response is None:
                return "[Delegate LLM error]"

            final_response = response
            messages.append({"role": "assistant", "content": response})

            if "DONE" in response and not extract_actions(response):
                break

            had_actions, _ = self._process_response_actions(
                response,
                messages,
                backend="secondary",
                allow_delegate=False,
            )
            if not had_actions:
                break

        return final_response

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    def _format_result(self, name: str, result: dict[str, Any] | str) -> str:
        """Format an action result for injection into conversation."""
        if isinstance(result, str):
            return result

        if "error" in result:
            return f"ERROR: {result['error']}"

        parts = []
        if "content" in result:
            parts.append(result["content"])

        for out_key in ("stdout", "stderr"):
            if out_key in result and result[out_key]:
                out_str = result[out_key]
                lines = out_str.splitlines()
                if len(lines) > 50 and self.session_manager:
                    import time
                    temp_dir = self.session_manager.dir / ".temp"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    temp_file = temp_dir / f"{out_key}_{name}_{int(time.time())}.txt"
                    temp_file.write_text(out_str, encoding="utf-8")
                    prefix = f"STDERR: " if out_key == "stderr" else ""
                    parts.append(
                        f"{prefix}[{out_key} is {len(lines)} lines long. The first 50 lines are shown below.\n"
                        f"The full output was saved to {temp_file}.\n"
                        f"Use read('{temp_file}', start_line, end_line) to explore pending unexplored sources.]\n\n"
                        + "\n".join(lines[:50])
                    )
                else:
                    prefix = f"STDERR: " if out_key == "stderr" else ""
                    parts.append(f"{prefix}{out_str}")

        if "exit_code" in result and result["exit_code"] != 0:
            parts.append(f"(exit code: {result['exit_code']})")
        if "status" in result:
            parts.append(f"HTTP {result['status']}")
            if "content" in result:
                parts.append(result["content"])

        return "\n".join(parts) if parts else "(no output)"

    # ------------------------------------------------------------------
    # Context compaction
    # ------------------------------------------------------------------
    def _compact_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Compact conversation when approaching context budget."""
        self.session_stats.record_compaction()
        system = messages[0]
        recent = messages[-10:]

        dropped = messages[1:-10]
        if dropped:
            summary_parts = []
            for msg in dropped[-5:]:
                role = msg["role"]
                content = msg["content"][:200]
                summary_parts.append(f"[{role}] {content}...")

            summary = {
                "role": "system",
                "content": f"[Context compacted. {len(dropped)} earlier messages summarized. Recent context:]\n"
                + "\n".join(summary_parts),
            }
            return [system, summary] + recent

        return [system] + recent

    # ------------------------------------------------------------------
    # Meta commands
    # ------------------------------------------------------------------
    def _handle_meta_command(self, cmd: str, messages: list[dict[str, str]]) -> bool | str:
        """Handle /commands. Returns True if handled, 'quit' to exit, False if unknown."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        # ── /quit /exit /q ─────────────────────────────────────────────
        if command in ("/quit", "/exit", "/q"):
            return "quit"

        # ── /help <query> ──────────────────────────────────────────────
        if command == "/help" and arg:
            result = self.help_engine.search(arg)
            display.print_result("help", result)
            return True

        # ── /sessions ──────────────────────────────────────────────────
        if command == "/sessions":
            sessions = self.session_manager.list_sessions() if self.session_manager else []
            display.print_session_table(sessions, self.session.name if self.session else "")
            return True

        # ── /session <name> ────────────────────────────────────────────
        if command == "/session" and arg:
            if self.session_manager:
                self.session_manager.save()
                new_session = self.session_manager.switch(arg)
                self.session = new_session
                # Reload messages into conversation
                messages.clear()
                messages.append({"role": "system", "content": SYSTEM_PROMPT})
                if new_session.messages:
                    messages.extend(new_session.messages[-20:])
                display.print_event("session", f"Switched to session '{arg}'")
            return True

        # ── /skills ────────────────────────────────────────────────────
        if command == "/skills":
            display.print_skills_table(self.help_engine.index.skills)
            return True

        # ── /review ────────────────────────────────────────────────────
        if command == "/review":
            self._init_interaction_log()
            if self.interaction_log:
                display.run_review_session(self.interaction_log)
            else:
                display.print_event("error", "Interaction log not available (session manager missing).")
            return True

        # ── /stats ─────────────────────────────────────────────────────
        if command == "/stats":
            display.print_session_stats(self.session_stats)
            return True

        # ── /checkpoint ────────────────────────────────────────────────
        if command == "/checkpoint":
            self._save_checkpoint()
            self.session_stats.record_checkpoint()
            display.print_event("checkpoint", "Manual checkpoint saved.")
            return True

        # ── /compact ───────────────────────────────────────────────────
        if command == "/compact":
            before = len(messages)
            messages[:] = self._compact_messages(messages)
            after = len(messages)
            display.print_event("compact", f"Manually compacted: {before} → {after} messages")
            return True

        # ── /stream on|off ─────────────────────────────────────────────
        if command == "/stream":
            if arg.lower() in ("on", "1", "true", "yes"):
                self.use_streaming = True
                display.print_event("ok", "Streaming enabled.")
            elif arg.lower() in ("off", "0", "false", "no"):
                self.use_streaming = False
                display.print_event("ok", "Streaming disabled.")
            else:
                state = "on" if self.use_streaming else "off"
                display.print_event("info", f"Streaming is currently {state}. Use /stream on|off")
            return True

        # ── /clear ─────────────────────────────────────────────────────
        if command == "/clear":
            display.clear_screen()
            display.banner(self.session.name, self.help_engine.index.size)
            return True

        # ── /config ────────────────────────────────────────────────────
        if command == "/config":
            if arg.lower() == "save":
                self._save_config_overrides()
            else:
                self._print_config_table()
            return True

        # ── /set ───────────────────────────────────────────────────────
        if command == "/set":
            if not arg:
                self._print_config_table()
            else:
                self._handle_set(arg)
            return True

        return False

    # ------------------------------------------------------------------
    # /set handler
    # ------------------------------------------------------------------
    _SET_DOCS: dict[str, str] = {
        "temperature":      "LLM sampling temperature (0.0–2.0)",
        "max_tokens":       "Max tokens to generate per call",
        "top_p":            "Nucleus sampling p (0.0–1.0)",
        "repeat_penalty":   "Repetition penalty (≥1.0)",
        "context_budget":   "Context window compaction threshold (tokens)",
        "max_turns":        "Max reasoning turns per user task",
        "checkpoint_every": "Auto-checkpoint every N turns (0=off)",
        "streaming":        "Stream tokens to terminal (on/off)",
        "markdown":         "Render Markdown in responses (on/off)",
        "stats":            "Show per-turn token stats (on/off)",
        "model":            "Orchestrator model name (hot-swap, no restart)",
        "base_url":         "Orchestrator base URL (hot-swap)",
        "atomic.model":     "Atomic/subagent model name",
        "atomic.base_url":  "Atomic/subagent base URL",
        "atomic.temperature":   "Atomic LLM temperature",
        "atomic.max_tokens":    "Atomic LLM max_tokens",
    }

    def _handle_set(self, arg: str):
        """Parse `/set key value` and apply the override."""
        parts = arg.split(maxsplit=1)
        if len(parts) < 2:
            key = parts[0].lower()
            doc = self._SET_DOCS.get(key, "Unknown key")
            val = self._get_config_value(key)
            msg = f"{key} = {val!r}   [{doc}]"
            display.print_event("info", msg)
            return msg

        key, raw_val = parts[0].lower(), parts[1].strip()

        # Boolean keys
        if key in ("streaming", "markdown", "stats"):
            new_val = raw_val.lower() in ("on", "1", "true", "yes")
            if key == "streaming":
                self.use_streaming = new_val
            elif key == "markdown":
                self.use_markdown = new_val
            elif key == "stats":
                self.show_stats = new_val
            msg = f"{key} → {new_val}"
            display.print_event("ok", msg)
            return msg

        # Integer keys
        if key in ("max_tokens", "context_budget", "max_turns", "checkpoint_every"):
            try:
                new_int = int(raw_val)
            except ValueError:
                msg = f"Expected integer for {key}, got: {raw_val!r}"
                display.print_event("error", msg)
                return f"ERROR: {msg}"
            if key == "max_tokens":
                self.llm.max_tokens = new_int
            elif key == "context_budget":
                self.context_budget = new_int
            elif key == "max_turns":
                self.max_turns = new_int
            elif key == "checkpoint_every":
                self.checkpoint_every = new_int
            msg = f"{key} → {new_int}"
            display.print_event("ok", msg)
            return msg

        # Float keys
        if key in ("temperature", "top_p", "repeat_penalty"):
            try:
                new_float = float(raw_val)
            except ValueError:
                msg = f"Expected float for {key}, got: {raw_val!r}"
                display.print_event("error", msg)
                return f"ERROR: {msg}"
            setattr(self.llm, key, new_float)
            msg = f"{key} → {new_float}"
            display.print_event("ok", msg)
            return msg

        # String keys
        if key == "model":
            self.llm.model = raw_val
            msg = f"model → {raw_val!r}"
            display.print_event("ok", msg)
            return msg

        if key == "base_url":
            import httpx
            self.llm.base_url = raw_val.rstrip("/")
            self.llm._client = httpx.Client(
                base_url=self.llm.base_url,
                timeout=httpx.Timeout(300.0, connect=15.0),
            )
            msg = f"base_url → {raw_val!r}  (new HTTP client created)"
            display.print_event("ok", msg)
            return msg

        # Atomic/subagent keys
        if key.startswith("atomic.") and self.atomic_llm:
            sub_key = key[len("atomic."):]
            if sub_key == "model":
                self.atomic_llm.model = raw_val
                msg = f"atomic.model → {raw_val!r}"
                display.print_event("ok", msg)
            elif sub_key == "base_url":
                import httpx
                self.atomic_llm.base_url = raw_val.rstrip("/")
                self.atomic_llm._client = httpx.Client(
                    base_url=self.atomic_llm.base_url,
                    timeout=httpx.Timeout(300.0, connect=15.0),
                )
                msg = f"atomic.base_url → {raw_val!r}"
                display.print_event("ok", msg)
            elif sub_key == "temperature":
                self.atomic_llm.temperature = float(raw_val)
                msg = f"atomic.temperature → {raw_val}"
                display.print_event("ok", msg)
            elif sub_key == "max_tokens":
                self.atomic_llm.max_tokens = int(raw_val)
                msg = f"atomic.max_tokens → {raw_val}"
                display.print_event("ok", msg)
            else:
                self.atomic_llm.extra_params[sub_key] = raw_val
                msg = f"atomic.{sub_key} → {raw_val!r} (saved to extra_params)"
                display.print_event("ok", msg)
            return msg

        # Fallback to LLM extra_params for unknown keys (like 'thinking')
        # Try to parse as int/float/bool if possible
        val_parsed: Any = raw_val
        if raw_val.lower() in ("true", "on", "yes"):
            val_parsed = True
        elif raw_val.lower() in ("false", "off", "no"):
            val_parsed = False
        else:
            try:
                val_parsed = int(raw_val)
            except ValueError:
                try:
                    val_parsed = float(raw_val)
                except ValueError:
                    pass
                    
        self.llm.extra_params[key] = val_parsed
        msg = f"{key} → {val_parsed!r} (saved to extra_params)"
        display.print_event("ok", msg)
        return msg

    # ------------------------------------------------------------------
    # /config helpers
    # ------------------------------------------------------------------
    def _get_config_value(self, key: str) -> Any:
        """Return the current runtime value for a config key."""
        mapping = {
            "temperature":      self.llm.temperature,
            "max_tokens":       self.llm.max_tokens,
            "top_p":            self.llm.top_p,
            "repeat_penalty":   self.llm.repeat_penalty,
            "context_budget":   self.context_budget,
            "max_turns":        self.max_turns,
            "checkpoint_every": self.checkpoint_every,
            "streaming":        self.use_streaming,
            "markdown":         self.use_markdown,
            "stats":            self.show_stats,
            "model":            self.llm.model,
            "base_url":         self.llm.base_url,
        }
        if self.atomic_llm:
            mapping.update({
                "atomic.model":       self.atomic_llm.model,
                "atomic.base_url":    self.atomic_llm.base_url,
                "atomic.temperature": self.atomic_llm.temperature,
                "atomic.max_tokens":  self.atomic_llm.max_tokens,
            })
        return mapping.get(key, "?")

    def _print_config_table(self):
        """Print a full runtime configuration table."""
        rows: list[tuple[str, str, str]] = []
        for key, doc in self._SET_DOCS.items():
            val = self._get_config_value(key)
            rows.append((key, str(val), doc))
        display.print_config_table(rows)

    def _save_config_overrides(self):
        """Stub: write runtime overrides back to config.yaml."""
        display.print_event("warn", "/config save not yet implemented — overrides are runtime-only.")
