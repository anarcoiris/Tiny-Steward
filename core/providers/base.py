"""Provider profile protocol and shared base."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from core.runtime_messages import normalize_messages_for_llm


@dataclass(frozen=True)
class ProviderNotes:
    """Human/ops metadata for a chat-template dialect."""

    template_name: str
    tool_call_dialect: str  # qwythos_xml | qwen_json | ...
    jinja_required: bool
    think_tags: tuple[str, str] = ("<think>", "</think>")
    kv_breaking_keys: frozenset[str] = field(
        default_factory=lambda: frozenset({"enable_thinking", "preserve_thinking", "add_vision_id"})
    )
    ops_notes: str = ""


@runtime_checkable
class ProviderProfile(Protocol):
    """Chat-template dialect used by one LLM lane."""

    id: str
    lane: Literal["orch", "atomic"]
    notes: ProviderNotes

    def extract_actions(self, text: str) -> list[dict[str, Any]]: ...

    def normalize_outbound(
        self,
        messages: list[dict[str, Any]],
        *,
        preserve_thinking: bool = False,
    ) -> list[dict[str, Any]]: ...

    def default_template_kwargs(self) -> dict[str, Any]: ...

    def tools_for_request(self, tools: list[dict] | None) -> list[dict] | None: ...


class BaseProviderProfile:
    """Default implementations shared by concrete profiles."""

    id: str
    lane: Literal["orch", "atomic"]
    notes: ProviderNotes

    def normalize_outbound(
        self,
        messages: list[dict[str, Any]],
        *,
        preserve_thinking: bool = False,
    ) -> list[dict[str, Any]]:
        return normalize_messages_for_llm(messages, preserve_thinking=preserve_thinking)

    def default_template_kwargs(self) -> dict[str, Any]:
        return {}

    def tools_for_request(self, tools: list[dict] | None) -> list[dict] | None:
        return tools
