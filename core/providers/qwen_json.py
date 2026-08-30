"""Qwen JSON (atomic) provider profile."""

from __future__ import annotations

from typing import Any, Literal

from core.action_parse import extract_actions
from core.providers.base import BaseProviderProfile, ProviderNotes


class QwenJsonProfile(BaseProviderProfile):
    id = "qwen3_json"
    lane: Literal["orch", "atomic"] = "atomic"
    notes = ProviderNotes(
        template_name="qwen-json-tools",
        tool_call_dialect="qwen_json",
        jinja_required=True,
        ops_notes=(
            "Atomic lane (default :11439). Requires llama.cpp --jinja. "
            "JSON <tool_call>{\"name\", \"arguments\"}</tool_call> dialect. "
            "role:tool messages group into <tool_response>. Prefer thinking off "
            "for TTFT (enable_thinking=false, thinking_budget_tokens=0)."
        ),
    )

    def extract_actions(self, text: str) -> list[dict[str, Any]]:
        return extract_actions(text, dialect="qwen_json")

    def default_template_kwargs(self) -> dict[str, Any]:
        return {"enable_thinking": False, "preserve_thinking": False}
