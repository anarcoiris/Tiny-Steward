"""Qwythos (orchestrator) provider profile — XML tool_call dialect."""

from __future__ import annotations

from typing import Any, Literal

from core.action_parse import extract_actions
from core.providers.base import BaseProviderProfile, ProviderNotes


class QwythosProfile(BaseProviderProfile):
    id = "qwythos"
    lane: Literal["orch", "atomic"] = "orch"
    notes = ProviderNotes(
        template_name="qwythos-xml-tools",
        tool_call_dialect="qwythos_xml",
        jinja_required=True,
        ops_notes=(
            "Orchestrator lane (default :11440). XML <tool_call><function=…>"
            "<parameter=…> dialect. enable_thinking / preserve_thinking are "
            "KV-breaking (chat_template_kwargs). Prefer tools payload once per session."
        ),
    )

    def extract_actions(self, text: str) -> list[dict[str, Any]]:
        return extract_actions(text, dialect="qwythos_xml")

    def default_template_kwargs(self) -> dict[str, Any]:
        return {"enable_thinking": True, "preserve_thinking": False}
