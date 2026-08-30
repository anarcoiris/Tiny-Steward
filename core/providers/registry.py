"""Resolve provider profiles by id."""

from __future__ import annotations

from core.providers.base import ProviderProfile
from core.providers.qwen_json import QwenJsonProfile
from core.providers.qwythos import QwythosProfile

_QWYTHOS = QwythosProfile()
_QWEN = QwenJsonProfile()

PROVIDER_REGISTRY: dict[str, ProviderProfile] = {
    "qwythos": _QWYTHOS,
    "qwen3_json": _QWEN,
    # Aliases
    "qwen": _QWEN,
    "qwen3": _QWEN,
}


def list_providers() -> list[str]:
    """Canonical provider ids (no aliases)."""
    return ["qwythos", "qwen3_json"]


def resolve_provider(provider_id: str | None, *, default: str) -> ProviderProfile:
    """Look up a profile; raise ValueError with registered ids on unknown."""
    key = (provider_id or default).strip().lower()
    profile = PROVIDER_REGISTRY.get(key)
    if profile is None:
        known = ", ".join(list_providers())
        raise ValueError(f"Unknown provider {provider_id!r}. Registered: {known}")
    return profile
