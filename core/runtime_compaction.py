"""Runtime Context Compaction & Tool Result Handling Mixin.

Manages history pruning, tool output capping, and tools payload policies.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from core.primitives import PRIMITIVES_TOOLS
from core.prompt_hygiene import scrub_chrome
from core.dreaming import memory_md_path, memory_summary_for_compact

if TYPE_CHECKING:
    from core.stats import SessionStats


class RuntimeCompactionMixin:
    """Mixin providing context compaction, tool output recording, and tools payload policy."""

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

    def _drain_mailbox_into_messages(self, messages: list[dict[str, Any]]) -> int:
        """Drain inbox and inject supervisor messages. Returns count injected."""
        get_box = getattr(self, "_mailbox", None)
        box = get_box() if callable(get_box) else None
        if not box:
            return 0
        drained = box.drain(skip_types={"delegate_result"})
        for msg in drained:
            sender = str(msg.get("from", "unknown"))
            content = str(msg.get("content", ""))
            msg_type = str(msg.get("type", "message"))
            if msg_type == "delegate_result":
                # Parent wait loop consumes these separately; skip injecting as chat.
                continue
            text = f"[Mail from {sender} | {msg_type} | priority={msg.get('priority', 'normal')}]\n{content}"
            name = f"supervisor_{sender}"
            messages.append({"role": "user", "name": name, "content": text})
            self.session.add_message("user", text, name=name)
            from core.display import display
            display.print_event("mail", f"Injected mail from {sender} ({msg_type})")
        return len(drained)

    def _compact_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compact conversation when approaching context budget while preserving chat template invariants."""
        if hasattr(self, "session_stats") and self.session_stats:
            self.session_stats.record_compaction()

        # Force refreshing tool payload on next turn following compaction
        if hasattr(self, "_force_tools_resend") and getattr(self, "session", None):
            try:
                self._force_tools_resend("primary")
                self._force_tools_resend("secondary")
            except Exception:
                pass

        if not messages:
            return []

        system = messages[0]
        body = messages[1:]
        
        # Take the most recent messages (dynamic window: 14 to 24 messages)
        keep_count = min(max(len(body) // 2, 14), 24)
        recent_raw = body[-keep_count:] if len(body) > keep_count else list(body)
        dropped = body[:-keep_count] if len(body) > keep_count else []

        recent = []
        for msg in recent_raw:
            m = dict(msg)
            if m.get("role") == "tool" and isinstance(m.get("content"), str) and len(m["content"]) > 4000:
                m["content"] = m["content"][:4000] + "\n\n[... tool output truncated for context compaction ...]"
            recent.append(m)

        # Ensure we don't start recent with an orphaned 'tool' message
        while recent and recent[0].get("role") == "tool":
            recent.pop(0)

        # Ensure there is at least one 'user' query in the conversation (required by Jinja templates / Qwen / OpenAI)
        has_user = any(m.get("role") == "user" for m in recent)
        if not has_user:
            # Find the most recent user query from dropped
            last_user_msg = None
            for msg in reversed(dropped):
                if msg.get("role") == "user":
                    last_user_msg = dict(msg)
                    break
            
            if last_user_msg:
                recent.insert(0, last_user_msg)
            else:
                # If no user message was ever present, synthesize one from active task or context
                task_desc = "Continue current task"
                if hasattr(self, "_get_active_task_text"):
                    _, tcontent = self._get_active_task_text(max_chars=200)
                    if tcontent:
                        first_line = tcontent.strip().splitlines()[0]
                        task_desc = f"Continue working on: {first_line}"
                recent.insert(0, {"role": "user", "content": task_desc})

        # If recent starts with an assistant message, ensure the user message is placed before it
        if recent and recent[0].get("role") != "user":
            user_idx = next((i for i, m in enumerate(recent) if m.get("role") == "user"), None)
            if user_idx is not None and user_idx > 0:
                user_msg = recent.pop(user_idx)
                recent.insert(0, user_msg)

        if dropped:
            summary_parts = []
            mem_summary = ""
            if getattr(self, "session_manager", None) and getattr(self, "session", None):
                mem_summary = memory_summary_for_compact(
                    memory_md_path(self.session_manager.dir, self.session.name),
                    max_chars=1200,
                )
            if mem_summary:
                summary_parts.append("[Integrated memories]\n" + mem_summary)
            if hasattr(self, "_get_active_task_text"):
                tpath, tcontent = self._get_active_task_text(max_chars=800)
                if tcontent:
                    summary_parts.append(f"[Active Task Plan ({tpath})]\n{tcontent}")
            # Include discovered skills so agent remembers capabilities acquired in this session
            if getattr(self, "session", None) and getattr(self.session, "discovered_skills", None):
                skills = self.session.discovered_skills
                if skills:
                    summary_parts.append(f"[Discovered Skills in Session]: {', '.join(skills)} (call help() to review any skill manual)")
            for msg in dropped[-5:]:
                role = msg.get("role", "user")
                content = scrub_chrome(msg.get("content", "") or "")[:200]
                if not content.strip():
                    continue
                summary_parts.append(f"[{role}] {content}...")

            summary_text = (
                f"\n\n[Context compacted: {len(dropped)} earlier messages summarized. Recent progress:]\n"
                + "\n".join(summary_parts)
            )
            compacted_system = dict(system)
            compacted_system["content"] = str(compacted_system.get("content", "")) + summary_text
            return [compacted_system] + recent

        return [system] + recent
