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

import re
import time
from pathlib import Path
from typing import Any

from core.llm import LLMClient, estimate_messages_tokens, estimate_tokens
from core.primitives import PRIMITIVES
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
- read(path): read file contents
- write(path, content): create/overwrite a file
- append(path, content): append to a file
- mkdir(path): create directory
- ls(path): list directory contents
- grep(pattern, path): search for text in files
- http(method, url, body?): make an HTTP request
- mcp(tool, body?): execute a tool on the nina-mcp server
- delegate(agent, task): delegate a task to a specialist micro-agent (e.g. nda_review)
- help(query): discover capabilities for a problem or error

## How to act

Respond with actions using XML tags:

<action name="pwsh">Get-ChildItem -Recurse</action>
<action name="read" path="config.yaml"></action>
<action name="write" path="output.txt">file content here</action>
<action name="http" method="POST" url="http://example.com">{{"key": "value"}}</action>
<action name="mcp" tool="nina_camera_capture">{{"duration": 1, "save": false}}</action>
<action name="delegate" agent="nda_review">Review the Acme NDA text below...</action>
<action name="help">container won't start</action>

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
ACTION_PATTERN = re.compile(
    r'<action\s+name="(\w+)"'    # name attribute
    r'(?:\s+(\w+)="([^"]*)")*'   # optional extra attributes
    r'\s*>(.*?)</action>',
    re.DOTALL,
)

# More flexible: capture all attributes
ATTR_PATTERN = re.compile(r'(\w+)="([^"]*)"')


def parse_actions(text: str) -> list[dict[str, Any]]:
    """Parse <action> tags from LLM response text."""
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
        context_budget: int = 68000,        # tokens, leave room below 32k
        use_streaming: bool = True,
        use_markdown: bool = True,
        show_stats: bool = True,
        checkpoint_every: int = 5,          # auto-checkpoint every N turns
        atomic_llm: LLMClient | None = None,
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

            if "DONE" in response and not parse_actions(response):
                return response

            actions = parse_actions(response)
            if not actions:
                return response

            for action in actions:
                result = self._execute_action(action)
                result_text = self._format_result(action["name"], result)
                is_error = "error" in (result if isinstance(result, dict) else {})
                display.print_result(action["name"], result_text, is_error=is_error)
                messages.append({"role": "user", "content": f"[Result of {action['name']}]\n{result_text}"})
                self.session.add_message("user", f"[Result of {action['name']}]\n{result_text}")

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

        while True:
            try:
                user_input = input(display.prompt_text()).strip()
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

                actions = parse_actions(response)
                if not actions:
                    outcome = "success"
                    break

                for action in actions:
                    if action["name"] == "help":
                        help_calls += 1
                        
                    display.print_action_placeholder(action["name"], action.get("body", ""))
                    result = self._execute_action(action)
                    result_text = self._format_result(action["name"], result)
                    is_error = isinstance(result, dict) and "error" in result
                    if is_error or (isinstance(result, dict) and result.get("exit_code", 0) != 0):
                        errors_in_turn += 1
                        
                    if self.interaction_log:
                        code = result.get("exit_code", 0) if isinstance(result, dict) else 0
                        if is_error and code == 0: code = 1
                        self.interaction_log.record_action(action["name"], action["body"], code)
                        
                    display.print_result(action["name"], result_text, is_error=is_error)
                    messages.append({"role": "user", "content": f"[Result of {action['name']}]\n{result_text}"})
                    self.session.add_message("user", f"[Result of {action['name']}]\n{result_text}")

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
        messages: list[dict[str, str]],
        *,
        turn: int,
    ) -> tuple[str | None, dict | None, float]:
        """Call the LLM. Returns (response_text, usage_dict_or_None, elapsed_s)."""
        t0 = time.monotonic()
        usage: dict | None = None

        try:
            if self.use_streaming:
                response = self._stream_response(messages)
            else:
                response = self.llm.chat(messages)
        except Exception as e:
            display.print_event("error", f"LLM error: {e}")
            return None, None, time.monotonic() - t0

        elapsed = time.monotonic() - t0
        return response, usage, elapsed

    def _stream_response(self, messages: list[dict[str, str]]) -> str:
        """Stream the LLM response token-by-token, render it, and return full text."""
        display.print_response_stream_start()
        chunks: list[str] = []
        usage: dict | None = None

        gen = self.llm.chat_stream_with_usage(messages)
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
    def _execute_action(self, action: dict[str, Any]) -> dict[str, Any] | str:
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

        if name == "delegate":
            agent_slug = attrs.get("agent") or attrs.get("skill") or body
            problem = body
            skill = self.help_engine.index.get_by_slug(agent_slug)
            if not skill:
                skill = self.help_engine.index.get_by_name(agent_slug)
            if not skill:
                return {"error": f"Agent or skill '{agent_slug}' not found."}

            if not self.atomic_llm:
                return {"error": "Delegate action failed: no atomic LLM configured. Please specify an atomic model in config.yaml."}

            # Retrieve context (last 12 messages from session)
            context_messages = []
            for msg in self.session.messages[-12:]:
                context_messages.append(f"{msg['role'].upper()}: {msg['content']}")
            context_text = "\n".join(context_messages)

            # Auto-load CLAUDE.md if the agent is in the legal domain
            playbook_content = ""
            if "legal/" in skill.path:
                # Find CLAUDE.md in the same directory as the skill path
                skill_dir = (Path(self.help_engine.index.skills[0].path).parent if self.help_engine.index.skills else Path("skills"))
                # But since skill.path is relative to skills root, let's locate it relative to skills root:
                skills_root = Path("skills")
                claude_path = skills_root / "legal" / "CLAUDE.md"
                if claude_path.exists():
                    try:
                        playbook_content = claude_path.read_text(encoding="utf-8")
                    except Exception as e:
                        playbook_content = f"[Warning: Failed to read CLAUDE.md: {e}]"

            if playbook_content:
                context_text = f"PLAYBOOK CONFIGURATION (CLAUDE.md):\n==================================================\n{playbook_content}\n==================================================\n\n{context_text}"

            from core.micro_agent import MicroAgent
            micro_agent = MicroAgent(self.atomic_llm)
            result = micro_agent.delegate(skill, problem, context_text)
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
                return primitive(path)
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
            else:
                return primitive(body)
        except Exception as e:
            return {"error": f"Action {name} failed: {e}"}

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
        if "stdout" in result and result["stdout"]:
            parts.append(result["stdout"])
        if "stderr" in result and result["stderr"]:
            parts.append(f"STDERR: {result['stderr']}")
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
            # Print docs for just this key
            key = parts[0].lower()
            doc = self._SET_DOCS.get(key, "Unknown key")
            val = self._get_config_value(key)
            display.print_event("info", f"{key} = {val!r}   [{doc}]")
            return

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
            display.print_event("ok", f"{key} → {new_val}")
            return

        # Integer keys
        if key in ("max_tokens", "context_budget", "max_turns", "checkpoint_every"):
            try:
                new_int = int(raw_val)
            except ValueError:
                display.print_event("error", f"Expected integer for {key}, got: {raw_val!r}")
                return
            if key == "max_tokens":
                self.llm.max_tokens = new_int
            elif key == "context_budget":
                self.context_budget = new_int
            elif key == "max_turns":
                self.max_turns = new_int
            elif key == "checkpoint_every":
                self.checkpoint_every = new_int
            display.print_event("ok", f"{key} → {new_int}")
            return

        # Float keys
        if key in ("temperature", "top_p", "repeat_penalty"):
            try:
                new_float = float(raw_val)
            except ValueError:
                display.print_event("error", f"Expected float for {key}, got: {raw_val!r}")
                return
            setattr(self.llm, key, new_float)
            display.print_event("ok", f"{key} → {new_float}")
            return

        # String keys
        if key == "model":
            self.llm.model = raw_val
            display.print_event("ok", f"model → {raw_val!r}")
            return

        if key == "base_url":
            import httpx
            self.llm.base_url = raw_val.rstrip("/")
            self.llm._client = httpx.Client(
                base_url=self.llm.base_url,
                timeout=httpx.Timeout(300.0, connect=15.0),
            )
            display.print_event("ok", f"base_url → {raw_val!r}  (new HTTP client created)")
            return

        # Atomic/subagent keys
        if key.startswith("atomic.") and self.atomic_llm:
            sub_key = key[len("atomic."):]
            if sub_key == "model":
                self.atomic_llm.model = raw_val
                display.print_event("ok", f"atomic.model → {raw_val!r}")
            elif sub_key == "base_url":
                import httpx
                self.atomic_llm.base_url = raw_val.rstrip("/")
                self.atomic_llm._client = httpx.Client(
                    base_url=self.atomic_llm.base_url,
                    timeout=httpx.Timeout(300.0, connect=15.0),
                )
                display.print_event("ok", f"atomic.base_url → {raw_val!r}")
            elif sub_key == "temperature":
                self.atomic_llm.temperature = float(raw_val)
                display.print_event("ok", f"atomic.temperature → {raw_val}")
            elif sub_key == "max_tokens":
                self.atomic_llm.max_tokens = int(raw_val)
                display.print_event("ok", f"atomic.max_tokens → {raw_val}")
            else:
                display.print_event("warn", f"Unknown atomic key: {key}")
            return

        display.print_event("warn", f"Unknown config key: {key!r}. Run /set for a full list.")

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
