"""Runtime — the main reasoning loop orchestrator.

Integrates execution, context compaction, slash commands, micro-agent delegation,
and structured reasoning loops.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from core.llm import LLMClient, estimate_messages_tokens
from core.primitives import PRIMITIVES, PRIMITIVES_TOOLS
from core.help import HelpEngine
from core.session import Session, SessionManager
from core.stats import SessionStats
from core.guidance import GuidanceEngine
from core.interaction_log import InteractionLog
from core.mailbox import Mailbox, mailbox_for
from core.delegate_terminal import (
    build_child_argv,
    resolve_terminal_mode,
    spawn_child,
)
from core.prompt_hygiene import (
    paste_block_message,
    scrub_chrome,
    should_block_paste,
)
from core.dreaming import (
    memory_block_for_prompt,
    memory_md_path,
    memory_summary_for_compact,
    run_dream,
)
from core.action_parse import extract_actions, parse_actions  # noqa: F401
from core.runtime_messages import THINK_RE, normalize_messages_for_llm, strip_think_from_text  # noqa: F401
from core.providers import resolve_provider
from core.providers.base import ProviderProfile

from core.runtime_execution import RuntimeExecutionMixin
from core.runtime_compaction import RuntimeCompactionMixin
from core.runtime_meta import RuntimeMetaMixin
from core.runtime_delegate import RuntimeDelegateMixin
from core.runtime_loop import RuntimeLoopMixin
from core.system_prompt import (  # noqa: F401
    SYSTEM_PROMPT,
    DELEGATE_EXAMPLE_STUB,
    DEFAULT_RULES_CANDIDATES,
    RULES_MAX_CHARS,
    ATTACH_MAX_CHARS,
    _OS_PATH_RULE,
    build_system_prompt,
    load_rules_text,
    format_os_invariants,
    compose_system_prompt,
)
from core.idle_loop import IdleExecutionLock, IdleLoop
import core.display as display



class Runtime(
    RuntimeExecutionMixin,
    RuntimeCompactionMixin,
    RuntimeMetaMixin,
    RuntimeDelegateMixin,
    RuntimeLoopMixin,
):
    """The main reasoning loop orchestrator."""

    def __init__(
        self,
        llm: LLMClient,
        help_engine: HelpEngine,
        session: Session,
        *,
        max_turns: int = 50,
        context_budget: int = 26000,
        use_streaming: bool = True,
        use_markdown: bool = True,
        show_stats: bool = True,
        checkpoint_every: int = 5,
        atomic_llm: LLMClient | None = None,
        shortcuts: dict[str, str] | None = None,
        max_delegate_turns: int = 10,
        delegate_terminal: str = "auto",
        config_path: str = "config.yaml",
        rules_path: str | Path | None = "RULES.md",
        rules_enabled: bool = True,
        invariants: dict | None = None,
        session_manager: SessionManager | None = None,
        provider_profile: ProviderProfile | str | None = None,
        primary_provider: ProviderProfile | str | None = None,
        secondary_provider: ProviderProfile | str | None = None,
        backend_launcher: Any | None = None,
        vision_enabled: bool = True,
        idle_config: dict | None = None,
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
        self.atomic_llm = atomic_llm or llm
        self.shortcuts = shortcuts or {"send": "escape, enter", "newline": "c-j"}
        self.max_delegate_turns = max_delegate_turns
        self.delegate_terminal_setting = str(delegate_terminal or "auto").strip()
        self.config_path = config_path
        self.rules_path = rules_path
        self.rules_enabled = rules_enabled
        self.invariants = invariants or {}
        self.session_manager = session_manager
        self.backend_launcher = backend_launcher

        self.profiles: dict[str, ProviderProfile] = {}
        if primary_provider:
            self.profiles["primary"] = (
                resolve_provider(primary_provider, default="qwythos")
                if isinstance(primary_provider, str)
                else primary_provider
            )
        elif provider_profile:
            self.profiles["primary"] = (
                resolve_provider(provider_profile, default="qwythos")
                if isinstance(provider_profile, str)
                else provider_profile
            )
        else:
            self.profiles["primary"] = resolve_provider("qwythos", default="qwythos")

        if secondary_provider:
            self.profiles["secondary"] = (
                resolve_provider(secondary_provider, default="qwen3_json")
                if isinstance(secondary_provider, str)
                else secondary_provider
            )
        else:
            self.profiles["secondary"] = resolve_provider("qwen3_json", default="qwen3_json")

        self.provider_profile = self.profiles["primary"]

        self.guidance = GuidanceEngine()
        self.session_stats = SessionStats()
        self.interaction_log: InteractionLog | None = None
        self._rules_text = load_rules_text(rules_path, enabled=rules_enabled)
        self.rethink_enabled = True
        self.vision_enabled = vision_enabled
        self._is_delegate_child = False

        self.execution_lock = IdleExecutionLock()
        idle_opts = idle_config or {}
        self.idle_loop = IdleLoop(
            self,
            enabled=bool(idle_opts.get("enabled", True)),
            tick_interval=float(idle_opts.get("tick_interval", 2.0)),
            health_check_interval=float(idle_opts.get("health_check_interval", 30.0)),
            dream_check_interval=float(idle_opts.get("dream_check_interval", 60.0)),
            alert_check_interval=float(idle_opts.get("alert_check_interval", 3.0)),
        )

        self._init_interaction_log()


    def reload_rules(self) -> str:
        """Reload RULES.md from rules_path."""
        self._rules_text = load_rules_text(self.rules_path, enabled=self.rules_enabled)
        return f"Reloaded rules from {self.rules_path} ({len(self._rules_text)} chars)."

    def _get_active_task_text(self, max_chars: int = 2500) -> tuple[str, str]:
        """Find and load the active task.md / plan.md for this session. Returns (path_str, content)."""
        candidates: list[Path] = []
        if getattr(self, "session", None) and hasattr(self.session, "metadata"):
            recorded = self.session.metadata.get("task_file")
            if recorded:
                candidates.append(Path(recorded))
        if getattr(self, "session_manager", None) and getattr(self, "session", None):
            candidates.append(Path(self.session_manager.session_dir(self.session.name)) / "task.md")
            candidates.append(Path(self.session_manager.session_dir(self.session.name)) / "plan.md")
        if getattr(self, "session", None):
            candidates.append(Path(self.session.name) / "task.md")
            candidates.append(Path(self.session.name.replace("python_", "")) / "task.md")
            candidates.append(Path("ejercicios") / "task.md")
        candidates.append(Path("task.md"))

        for p in candidates:
            try:
                resolved = p.expanduser().resolve()
                if resolved.is_file():
                    content = resolved.read_text(encoding="utf-8").strip()
                    if content:
                        if len(content) > max_chars:
                            content = content[:max_chars].rstrip() + "\n\n[... task.md truncated ...]"
                        return str(p).replace("\\", "/"), content
            except OSError:
                continue
        return "", ""

    def _fresh_system_messages(self) -> list[dict[str, Any]]:
        task_path, task_content = self._get_active_task_text()
        task_block = f"Path: `{task_path}`\n\n{task_content}" if task_content else ""
        prompt = compose_system_prompt(self._rules_text, self.invariants, task_plan_text=task_block)
        return [{"role": "system", "content": prompt}]

    def _update_current_state(self, status: str) -> None:
        if not self.session_manager:
            return
        state_file = Path(self.session_manager.dir) / "current.json"
        try:
            state = {
                "status": status,
                "session": self.session.name,
                "updated_at": time.time(),
            }
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def mark_delegate_child(self, parent: str | None = None) -> None:
        """Mark this runtime session as a micro-agent child process."""
        self._is_delegate_child = True
        self.rethink_enabled = False
        self.vision_enabled = False
        self.session.metadata["delegate_child"] = True
        if parent:
            self.session.metadata["parent"] = parent

    mark_as_delegate_child = mark_delegate_child

    def _init_interaction_log(self):
        if not self.interaction_log and self.session_manager:
            self.interaction_log = InteractionLog(self.session_manager.session_dir(self.session.name), self.session.name)

    def _mailbox(self, session_id: str | None = None) -> Mailbox | None:
        if not self.session_manager:
            return None
        return mailbox_for(self.session_manager.dir, session_id or self.session.name)

    def run_task(self, task: str) -> str:
        """Execute a task through the reasoning loop."""
        self._update_current_state("busy")
        try:
            messages = self._fresh_system_messages()
            if self.session.messages:
                messages.extend(self.session.messages[-20:])

            messages.append({"role": "user", "content": task})
            self.session.add_message("user", task)

            return self._reasoning_loop(messages, interactive=False)
        finally:
            self._update_current_state("offline")

    def run_interactive(self):
        """Interactive REPL mode."""
        display.banner(
            session_name=self.session.name,
            skills_count=self.help_engine.index.size,
        )

        messages = self._fresh_system_messages()

        if self.session.messages:
            recent = self.session.messages[-20:]
            messages.extend(recent)
            display.print_event("info", f"Restored {len(recent)} messages from session '{self.session.name}'")
        if self._rules_text:
            display.print_event("info", f"Global RULES.md loaded ({len(self._rules_text)} chars)")

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

        import threading
        
        def poll_mailbox(prompt_sess, st_ev):
            while not st_ev.is_set():
                if self.session_manager:
                    state_path = Path(self.session_manager.dir) / "current.json"
                    try:
                        if state_path.exists():
                            with open(state_path, "r", encoding="utf-8") as f:
                                state = json.load(f)
                            if state.get("status") == "idle":
                                from core.mailbox import mailbox_for
                                box = mailbox_for(self.session_manager.dir, self.session.name)
                                peeked_messages = box.peek()
                                if peeked_messages:
                                    msg = box.drain()[0]
                                    content = msg.get("content", "")
                                    if prompt_sess and prompt_sess.app.is_running:
                                        def inject():
                                            prompt_sess.app.current_buffer.text = content
                                            prompt_sess.app.current_buffer.validate_and_handle()
                                        prompt_sess.app.loop.call_soon_threadsafe(inject)
                                        break
                    except Exception:
                        pass
                time.sleep(1.0)

        if hasattr(self, "idle_loop") and self.idle_loop and not self.idle_loop.is_running:
            self.idle_loop.start()

        stop_event = threading.Event()
        try:
            while True:
                self._update_current_state("idle")
                
                poll_thread = threading.Thread(
                    target=poll_mailbox, 
                    args=(prompt_session, stop_event), 
                    daemon=True
                )
                poll_thread.start()
                
                try:
                    if prompt_session:
                        user_input = prompt_session.prompt(ANSI(display.prompt_text())).strip()
                    else:
                        user_input = input(display.prompt_text()).strip()
                    user_input = user_input.encode('utf-8', 'replace').decode('utf-8')
                except (EOFError, KeyboardInterrupt):
                    display.print_event("info", "Bye.")
                    break
                finally:
                    stop_event.set()
                    stop_event = threading.Event()

                self._update_current_state("busy")
                if not user_input:
                    continue

                if user_input.startswith("/"):
                    handled = self._handle_meta_command(user_input, messages)
                    if handled == "quit":
                        break
                    if handled:
                        continue

                user_content, valid = self._process_user_input(user_input, messages)
                if not valid:
                    continue

                self._reasoning_loop(messages, interactive=True, prompt_session=prompt_session, stop_event=stop_event)
        finally:
            if hasattr(self, "idle_loop") and self.idle_loop:
                self.idle_loop.stop()
            self._update_current_state("offline")


    def _process_user_input(self, user_input: str, messages: list[dict[str, Any]]) -> tuple[Any, bool]:
        """Validate, expand attachments, and format user input for the interactive loop."""
        user_input, attach_notes, image_refs = self._expand_at_attachments(user_input)
        for note in attach_notes:
            display.print_event("info", note)

        if image_refs and not self.vision_enabled:
            from core.vision import vision_disabled_message
            display.print_event("error", vision_disabled_message())
            return None, False

        if should_block_paste(user_input):
            display.print_event("warn", paste_block_message())
            return None, False

        if image_refs:
            from core.vision import build_user_image_content
            user_content: Any = build_user_image_content(
                user_input,
                [r["path"] for r in image_refs],
                as_refs=True,
            )
        else:
            user_content = user_input

        messages.append({"role": "user", "content": user_content})
        self.session.add_message("user", user_content)

        from core.vision import content_text_preview
        self._init_interaction_log()
        if self.interaction_log:
            self.interaction_log.begin_interaction(content_text_preview(user_content))

        return user_content, True
