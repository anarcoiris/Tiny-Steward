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
        """Compact conversation when approaching context budget."""
        if hasattr(self, "session_stats") and self.session_stats:
            self.session_stats.record_compaction()

        if not messages:
            return []

        system = messages[0]
        body = messages[1:]
        recent_raw = body[-10:] if len(body) > 10 else body

        recent = []
        for msg in recent_raw:
            m = dict(msg)
            if m.get("role") == "tool" and isinstance(m.get("content"), str) and len(m["content"]) > 4000:
                m["content"] = m["content"][:4000] + "\n\n[... tool output truncated for context compaction ...]"
            recent.append(m)

        dropped = body[:-10] if len(body) > 10 else []
        if dropped:
            summary_parts = []
            mem_summary = ""
            if getattr(self, "session_manager", None):
                mem_summary = memory_summary_for_compact(
                    memory_md_path(self.session_manager.dir, self.session.name),
                    max_chars=1200,
                )
            if mem_summary:
                summary_parts.append("[Integrated memories]\n" + mem_summary)
            for msg in dropped[-5:]:
                role = msg["role"]
                content = scrub_chrome(msg.get("content", "") or "")[:200]
                if not content.strip():
                    continue
                summary_parts.append(f"[{role}] {content}...")

            summary = {
                "role": "system",
                "content": f"[Context compacted. {len(dropped)} earlier messages summarized. Recent context:]\n"
                + "\n".join(summary_parts),
            }
            return [system, summary] + recent

        return [system] + recent
