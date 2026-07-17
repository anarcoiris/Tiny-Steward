"""Outbound message normalization for LLM prompts.

Session storage keeps raw assistant text (including ``<think>``).
Only the view sent to the backend is pruned / scrubbed here.
"""

from __future__ import annotations

import re
from typing import Any

from core.prompt_hygiene import (
    EMPTY_ASSISTANT_PLACEHOLDER,
    scrub_chrome,
)

LEGACY_RESULT_RE = re.compile(r"^\[Result of (?P<name>[^\]]+)\]\n(?P<content>[\s\S]*)$")
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think_from_text(text: str) -> str:
    """Remove <think> blocks (for LLM context only)."""
    return THINK_RE.sub("", text).strip()


def normalize_messages_for_llm(
    messages: list[dict[str, Any]],
    *,
    preserve_thinking: bool = False,
) -> list[dict[str, Any]]:
    """Prepare messages for the backend: legacy result conversion + think pruning.

    When ``preserve_thinking`` is False (default), strip ``<think>`` from assistant
    content and drop ``reasoning_content`` so prior CoT does not inflate the prompt.
    Session storage keeps the raw assistant text; only the outbound LLM view is pruned.
    Also scrubs REPL chrome and replaces empty think-only assistant turns with a
    placeholder so history never contains blank assistant messages.
    """
    out: list[dict[str, Any]] = []
    for msg in messages:
        m = dict(msg)
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "user" and isinstance(content, list):
            # Multimodal: scrub/placeholder only on text parts; keep image_ref / image_url.
            m["content"] = _normalize_content_parts(content)
        elif role == "user" and isinstance(content, str):
            legacy = LEGACY_RESULT_RE.match(content)
            if legacy:
                m = {
                    "role": "tool",
                    "name": legacy.group("name"),
                    "content": legacy.group("content"),
                }
            elif isinstance(m.get("content"), str):
                m["content"] = scrub_chrome(m["content"])
        if m.get("role") == "assistant":
            if not preserve_thinking:
                if isinstance(m.get("content"), str):
                    m["content"] = strip_think_from_text(m["content"])
                m.pop("reasoning_content", None)
            if isinstance(m.get("content"), str):
                m["content"] = scrub_chrome(m["content"])
                if not (m["content"] or "").strip():
                    m["content"] = EMPTY_ASSISTANT_PLACEHOLDER
        elif m.get("role") == "tool" and isinstance(m.get("content"), str):
            m["content"] = scrub_chrome(m["content"])
        out.append(m)
    return out


def _normalize_content_parts(parts: list[Any]) -> list[dict[str, Any]]:
    """Scrub chrome on text parts only; never strip image_ref / image_url."""
    out: list[dict[str, Any]] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype == "text":
            out.append({"type": "text", "text": scrub_chrome(str(part.get("text") or ""))})
        elif ptype in ("image_ref", "image_url"):
            out.append(dict(part))
        else:
            out.append(dict(part))
    return out
