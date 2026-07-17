"""REPL meta-commands and /set config mixin for Runtime."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.dreaming import (
    memory_md_path,
    run_dream,
)
from core.mailbox import mailbox_for
from core.vision import (
    build_user_image_content,
    is_image_path,
    make_image_ref,
    vision_disabled_message,
)
import core.display as display

# Soft cap mirrored from runtime (avoid circular import at module load).
ATTACH_MAX_CHARS = 48_000


class RuntimeMetaMixin:
    """Slash-commands, attachments, dreaming, and runtime /set."""

    def _attach_image(self, arg: str, messages: list[dict[str, Any]]) -> bool:
        """Inject an image path ref into the conversation. Returns True (always handled)."""
        if not getattr(self, "vision_enabled", False):
            display.print_event("error", vision_disabled_message())
            return True
        cleaned = arg.strip().strip('"').strip("'")
        if cleaned.startswith("@"):
            cleaned = cleaned[1:].strip().strip('"').strip("'")
        p = Path(cleaned).expanduser()
        if not p.is_file():
            display.print_event("error", f"Image not found: {cleaned}")
            return True
        if not is_image_path(p):
            display.print_event(
                "error",
                f"Not a supported image type: {p.suffix or '(no extension)'}. "
                "Use .png .jpg .jpeg .gif .webp .bmp",
            )
            return True
        caption = (
            f"[Attached image: {cleaned}]\n"
            "Describe or answer about this image. Path is available for tools if needed."
        )
        content = build_user_image_content(caption, [p], as_refs=True)
        messages.append({"role": "user", "name": "attachment", "content": content})
        self.session.add_message("user", content, name="attachment")
        display.print_event(
            "ok",
            f"Attached image {cleaned} (path ref; encoded on LLM call). "
            "Prefer a new session after enabling -WithVision.",
        )
        return True

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

        # ── /providers ─────────────────────────────────────────────────
        if command == "/providers":
            from core.providers import list_providers

            for lane, label in (("primary", "orchestrator"), ("secondary", "atomic")):
                p = self.profiles.get(lane)
                if not p:
                    continue
                display.print_event(
                    "info",
                    f"{label}: provider={p.id} dialect={p.notes.tool_call_dialect} "
                    f"jinja={p.notes.jinja_required}",
                )
                if p.notes.ops_notes:
                    display.print_event("info", f"  {p.notes.ops_notes}")
            display.print_event("info", f"registered: {', '.join(list_providers())}")
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
                # Keep orch pin visible on the session tree (F4 metadata only).
                if (
                    not self._is_delegate_child
                    and getattr(self.llm, "id_slot", None) is not None
                ):
                    new_session.metadata["orch_id_slot"] = self.llm.id_slot
                    self.session_manager.save()
                # Reload messages into conversation
                messages.clear()
                messages.extend(self._fresh_system_messages())
                if new_session.messages:
                    messages.extend(new_session.messages[-20:])
                display.print_event("session", f"Switched to session '{arg}'")
            return True

        # ── /rules ─────────────────────────────────────────────────────
        if command == "/rules":
            if arg.lower() in ("reload", "refresh"):
                msg = self.reload_rules()
                display.print_event("warn", "Reloading RULES.md may invalidate the KV prompt prefix")
                display.print_event("ok", msg)
                # Refresh live system message if caller passes messages list
                if messages and messages[0].get("role") == "system":
                    messages[0]["content"] = self._system_prompt
                return True
            if not self.rules_enabled:
                display.print_event("info", "rules disabled in config")
            elif self._rules_text:
                preview = self._rules_text[:500]
                display.print_event("info", f"RULES.md ({len(self._rules_text)} chars):\n{preview}")
            else:
                display.print_event("info", "No RULES.md loaded")
            return True

        # ── /backend start|stop|status <orch|atomic> ───────────────────
        if command == "/backend":
            return self._handle_backend_command(arg)

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

        # ── /dream [session] ───────────────────────────────────────────
        if command == "/dream":
            return self._handle_dream(arg, messages)

        # ── /memory ────────────────────────────────────────────────────
        if command == "/memory":
            if not self.session_manager:
                display.print_event("error", "Session manager not available.")
                return True
            path = memory_md_path(self.session_manager.dir, self.session.name)
            if not path.exists():
                display.print_event(
                    "info",
                    "No memory.md yet — run /dream after some thinking turns.",
                )
                return True
            text = path.read_text(encoding="utf-8")
            preview = text if len(text) <= 2000 else text[:2000] + "\n[…]"
            display.print_event("info", f"{path.name}:\n{preview}")
            # Refresh system message memory block
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = self._fresh_system_messages()[0]["content"]
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

        # ── /image <path> ──────────────────────────────────────────────
        if command == "/image":
            if not arg:
                display.print_event(
                    "info",
                    "Usage: /image <path> — attach an image for vision (alias of image /attach). "
                    "Requires orch -WithVision + multimodal probe.",
                )
                return True
            return self._attach_image(arg, messages)

        # ── /attach <path> ─────────────────────────────────────────────
        if command == "/attach":
            if not arg:
                display.print_event(
                    "info",
                    "Usage: /attach <path> — inject a file by reference (capped). "
                    "Images (.png/.jpg/…) use vision when enabled. "
                    "Also: @path or @\"C:\\...\\file\" in a normal message; /image <path>.",
                )
                return True
            cleaned = arg.strip().strip('"').strip("'")
            if is_image_path(cleaned):
                return self._attach_image(cleaned, messages)
            text, err = self._read_attachment(arg)
            if err:
                display.print_event("error", err)
                return True
            injected = (
                f"[Attached file: {arg} — {len(text)} chars]\n"
                f"Do not ask the user to paste this again; use this content or read() the path.\n"
                f"---\n{text}"
            )
            messages.append({"role": "user", "name": "attachment", "content": injected})
            self.session.add_message("user", injected, name="attachment")
            display.print_event(
                "ok",
                f"Attached {arg} ({len(text)} chars, cap {ATTACH_MAX_CHARS}). Prefer this over pasting transcripts.",
            )
            return True

        # ── /mail <session> <text> ─────────────────────────────────────
        if command == "/mail":
            if not arg or " " not in arg:
                display.print_event("info", "Usage: /mail <session> <message text>")
                return True
            target, text = arg.split(maxsplit=1)
            if not self.session_manager:
                display.print_event("error", "Session manager not available.")
                return True
            box = mailbox_for(self.session_manager.dir, target)
            box.send(
                from_session=self.session.name,
                to_session=target,
                content=text,
                msg_type="supervision_question",
                priority="high",
            )
            display.print_event("mail", f"Queued mail to session '{target}'.")
            return True

        # ── /tree ──────────────────────────────────────────────────────
        if command == "/tree":
            if not self.session_manager:
                display.print_event("error", "Session manager not available.")
                return True
            display.print_session_tree(
                self.session_manager.list_sessions(),
                self.session.name if self.session else "",
            )
            return True

        # ── /set ───────────────────────────────────────────────────────
        if command == "/set":
            if not arg:
                self._print_config_table()
            else:
                self._handle_set(arg)
            return True

        return False

    def _handle_backend_command(self, arg: str) -> bool:
        """/backend start|stop|status|props <orch|atomic>"""
        from core.backend_launcher import normalize_lane

        if not self.backend_launcher:
            display.print_event(
                "error",
                "Backend launcher not configured (missing llm.*.launch in config).",
            )
            return True
        parts = arg.split()
        if len(parts) < 2:
            display.print_event(
                "info",
                "Usage: /backend start|stop|status|props <orch|atomic>",
            )
            return True
        action, lane_raw = parts[0].lower(), parts[1]
        lane = normalize_lane(lane_raw)
        if not lane:
            display.print_event("error", f"Unknown lane '{lane_raw}' (use orch|atomic)")
            return True
        if action == "status":
            st = self.backend_launcher.status(lane)
            display.print_event(
                "info",
                (
                    f"{lane}: configured={st['configured']} pid={st['pid']} "
                    f"process_running={st['process_running']} healthy={st['healthy']} "
                    f"parallel={st.get('parallel')} expect_slots={st.get('expect_total_slots')} "
                    f"props_slots={st.get('props_total_slots')}"
                ),
            )
            return True
        if action == "props":
            result = self.backend_launcher.props(lane)
            if not result.get("reachable") and not result.get("ok"):
                display.print_event("error", result.get("error", "props failed"))
                return True
            kind = "ok" if result.get("ok") else "warn"
            detail = "; ".join(result.get("messages") or [])
            display.print_event(
                kind,
                (
                    f"{lane}: n_ctx={result.get('n_ctx')} total_slots={result.get('total_slots')} "
                    f"expect={result.get('expect_total_slots')} — {detail or 'ok'}"
                ),
            )
            return True
        if action == "start":
            display.print_event("info", f"Starting {lane} backend…")
            result = self.backend_launcher.start(lane)
            if result.get("ok"):
                props = result.get("props") or {}
                display.print_event(
                    "ok",
                    (
                        f"{lane} started pid={result.get('pid')} healthy={result.get('healthy')} "
                        f"slots={props.get('total_slots')}"
                    ),
                )
            else:
                display.print_event("error", result.get("error", "start failed"))
            return True
        if action == "stop":
            result = self.backend_launcher.stop(lane)
            if result.get("ok"):
                if result.get("stopped"):
                    display.print_event("ok", f"{lane} stopped pid={result.get('pid')}")
                else:
                    display.print_event("info", f"{lane}: {result.get('reason')}")
            else:
                display.print_event("error", result.get("error", "stop failed"))
            return True
        display.print_event("info", "Usage: /backend start|stop|status|props <orch|atomic>")
        return True

    def _handle_dream(self, arg: str, messages: list[dict[str, Any]]) -> bool:
        """Run /dream [session] — consolidate think.jsonl into memory artifacts."""
        if not self.session_manager:
            display.print_event("error", "Session manager not available.")
            return True
        target = (arg or "").strip() or self.session.name
        llm = self.atomic_llm or self.llm
        if llm is None:
            display.print_event("error", "No LLM available for dreaming.")
            return True

        watermark = None
        if target == self.session.name:
            watermark = (self.session.metadata or {}).get("dream_watermark")
        else:
            path = self.session_manager._session_path(target)
            if not path.exists():
                display.print_event("error", f"Session '{target}' not found.")
                return True
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                watermark = (data.get("metadata") or {}).get("dream_watermark")
            except (OSError, json.JSONDecodeError) as e:
                display.print_event("error", f"Could not read session '{target}': {e}")
                return True

        display.print_event("info", f"Dreaming session '{target}' (atomic lane, dream priority)…")
        result = run_dream(
            sessions_dir=self.session_manager.dir,
            session_name=target,
            llm=llm,
            watermark=watermark,
            force_all=False,
        )
        if result.get("skipped"):
            display.print_event("info", result.get("reason", "nothing to dream"))
            return True
        if not result.get("ok"):
            display.print_event("error", result.get("error", "dream failed"))
            return True

        new_wm = result.get("watermark")
        if target == self.session.name:
            self.session.metadata["dream_watermark"] = new_wm
            self.session_manager.save()
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = self._fresh_system_messages()[0]["content"]
        else:
            path = self.session_manager._session_path(target)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                meta = data.setdefault("metadata", {})
                meta["dream_watermark"] = new_wm
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except (OSError, json.JSONDecodeError) as e:
                display.print_event("warn", f"Dream wrote memory files but failed to save watermark: {e}")

        counts = result.get("extract_counts") or {}
        display.print_event(
            "ok",
            f"Dreamed {result.get('count', 0)} think entries → {result.get('memory_md')} "
            f"(facts={counts.get('facts', 0)} validated={counts.get('validated', 0)} "
            f"hypotheses={counts.get('hypotheses', 0)})",
        )
        return True

    def _read_attachment(self, raw_path: str) -> tuple[str, str | None]:
        """Read a file for /attach or @path. Returns (text, error_or_None)."""
        cleaned = raw_path.strip().strip('"').strip("'")
        if cleaned.startswith("@"):
            cleaned = cleaned[1:].strip().strip('"').strip("'")
        try:
            p = Path(cleaned).expanduser()
            if not p.is_file():
                return "", f"File not found: {cleaned}"
            data = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return "", f"Cannot read {cleaned}: {e}"
        if len(data) > ATTACH_MAX_CHARS:
            data = (
                data[:ATTACH_MAX_CHARS]
                + f"\n\n[… truncated at {ATTACH_MAX_CHARS} chars; "
                f"use read('{cleaned}', start_line, end_line) for more …]"
            )
        return data, None

    def _expand_at_attachments(self, user_input: str) -> tuple[str, list[str], list[dict[str, Any]]]:
        """Replace @path mentions with capped file bodies; collect image refs.

        Only expands quoted paths, absolute paths, or relative paths under
        ``./``, ``../``, ``sessions/``, ``plans/`` — avoids eating email addresses.

        Returns ``(expanded_text, notes, image_refs)`` where image_refs are
        ``make_image_ref`` dicts (not yet base64-encoded).
        """
        pattern = re.compile(
            r'@(?:"([^"]+)"|\'([^\']+)\'|'
            r'((?:[A-Za-z]:)?[\\/][^\s]+)|'
            r'((?:\.{1,2}[\\/]|sessions[\\/]|plans[\\/]|core[\\/]|skills[\\/])[^\s]+))',
            re.IGNORECASE,
        )
        notes: list[str] = []
        image_refs: list[dict[str, Any]] = []

        def _repl(m: re.Match) -> str:
            path = next(g for g in m.groups() if g)
            cleaned = path.strip().strip('"').strip("'")
            if is_image_path(cleaned):
                p = Path(cleaned).expanduser()
                if not p.is_file():
                    notes.append(f"Image not found: {cleaned}")
                    return m.group(0)
                image_refs.append(make_image_ref(p))
                notes.append(f"Attached image @{cleaned} (vision path ref)")
                return f"\n[Image attached: {cleaned}]\n"
            text, err = self._read_attachment(path)
            if err:
                notes.append(err)
                return m.group(0)
            notes.append(f"Expanded @{path} ({len(text)} chars)")
            return f"\n[Attached via @ ref: {path}]\n---\n{text}\n---\n"

        expanded = pattern.sub(_repl, user_input)
        return expanded, notes, image_refs

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
        "enable_thinking":  "Qwythos chat_template_kwargs.enable_thinking (KV-breaking)",
        "preserve_thinking": "Qwythos chat_template_kwargs.preserve_thinking (KV-breaking)",
        "thinking_budget_tokens": "Sampler think budget (-1 uncapped; KV-safe)",
        "cache_prompt":     "Reuse prompt KV prefix (keep true; KV policy)",
        "vision":           "Orchestrator vision (runtime; set via config.yaml probe)",
        "atomic.model":     "Atomic/subagent model name",
        "atomic.base_url":  "Atomic/subagent base URL",
        "atomic.temperature":   "Atomic LLM temperature",
        "atomic.max_tokens":    "Atomic LLM max_tokens",
        "atomic.enable_thinking": "Atomic chat_template_kwargs.enable_thinking",
        "atomic.thinking_budget_tokens": "Atomic thinking_budget_tokens",
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

        # Alias: /set thinking on → enable_thinking (not flat extra_params)
        if key == "thinking":
            key = "enable_thinking"
            display.print_event(
                "warn",
                "Alias: 'thinking' → 'enable_thinking' (chat_template_kwargs; may invalidate KV prefix)",
            )

        # Boolean keys
        if key in ("streaming", "markdown", "stats", "cache_prompt"):
            new_val = raw_val.lower() in ("on", "1", "true", "yes")
            if key == "streaming":
                self.use_streaming = new_val
            elif key == "markdown":
                self.use_markdown = new_val
            elif key == "stats":
                self.show_stats = new_val
            elif key == "cache_prompt":
                self.llm.cache_prompt = new_val
                if not new_val:
                    display.print_event("warn", "cache_prompt=false forces full prompt recompute")
            msg = f"{key} → {new_val}"
            display.print_event("ok", msg)
            return msg

        # Thinking / chat_template_kwargs (KV-breaking when toggled mid-session)
        if key in ("enable_thinking", "preserve_thinking"):
            low = raw_val.lower()
            if low not in ("on", "1", "true", "yes", "off", "0", "false", "no"):
                msg = (
                    f"Invalid value {raw_val!r} for {key}. "
                    "Use on|true|yes|1 or off|false|no|0 (not 'medium')."
                )
                display.print_event("error", msg)
                return f"ERROR: {msg}"
            new_val = low in ("on", "1", "true", "yes")
            self.llm.set_template_kwarg(key, new_val)
            display.print_event(
                "warn",
                "KV prefix may invalidate — chat_template_kwargs changed mid-session",
            )
            msg = f"{key} → {new_val} (chat_template_kwargs)"
            display.print_event("ok", msg)
            return msg

        if key == "thinking_budget_tokens":
            try:
                new_int = int(raw_val)
            except ValueError:
                msg = f"Expected integer for {key}, got: {raw_val!r}"
                display.print_event("error", msg)
                return f"ERROR: {msg}"
            self.llm.thinking_budget_tokens = new_int
            msg = f"{key} → {new_int} (KV-safe)"
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
            elif sub_key in ("enable_thinking", "preserve_thinking"):
                new_val = raw_val.lower() in ("on", "1", "true", "yes")
                self.atomic_llm.set_template_kwarg(sub_key, new_val)
                display.print_event(
                    "warn",
                    "KV prefix may invalidate — atomic chat_template_kwargs changed",
                )
                msg = f"atomic.{sub_key} → {new_val}"
                display.print_event("ok", msg)
            elif sub_key == "thinking_budget_tokens":
                self.atomic_llm.thinking_budget_tokens = int(raw_val)
                msg = f"atomic.thinking_budget_tokens → {raw_val}"
                display.print_event("ok", msg)
            else:
                self.atomic_llm.extra_params[sub_key] = raw_val
                msg = f"atomic.{sub_key} → {raw_val!r} (saved to extra_params)"
                display.print_event("ok", msg)
            return msg

        # Fallback to LLM extra_params for unknown sampling/ops keys
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
            "enable_thinking":  self.llm.chat_template_kwargs.get("enable_thinking"),
            "preserve_thinking": self.llm.chat_template_kwargs.get("preserve_thinking"),
            "thinking_budget_tokens": self.llm.thinking_budget_tokens,
            "cache_prompt":     self.llm.cache_prompt,
            "vision":           getattr(self, "vision_enabled", False),
        }
        if self.atomic_llm:
            mapping.update({
                "atomic.model":       self.atomic_llm.model,
                "atomic.base_url":    self.atomic_llm.base_url,
                "atomic.temperature": self.atomic_llm.temperature,
                "atomic.max_tokens":  self.atomic_llm.max_tokens,
                "atomic.enable_thinking": self.atomic_llm.chat_template_kwargs.get("enable_thinking"),
                "atomic.thinking_budget_tokens": self.atomic_llm.thinking_budget_tokens,
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
