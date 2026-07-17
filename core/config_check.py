"""Reconcile config.yaml client budgets against live llama.cpp GET /props.

Does not mutate config.yaml. Emits warn/info lines via the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class PropsSnapshot:
    n_ctx: int | None
    total_slots: int | None
    reachable: bool
    error: str | None = None


def fetch_props(base_url: str, *, timeout: float = 5.0) -> PropsSnapshot:
    """GET {base_url}/props and extract n_ctx + total_slots."""
    url = base_url.rstrip("/") + "/props"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return PropsSnapshot(n_ctx=None, total_slots=None, reachable=False, error=str(e))

    n_ctx = None
    settings = data.get("default_generation_settings") or {}
    if isinstance(settings, dict) and settings.get("n_ctx") is not None:
        try:
            n_ctx = int(settings["n_ctx"])
        except (TypeError, ValueError):
            n_ctx = None

    total_slots = None
    if data.get("total_slots") is not None:
        try:
            total_slots = int(data["total_slots"])
        except (TypeError, ValueError):
            total_slots = None

    return PropsSnapshot(n_ctx=n_ctx, total_slots=total_slots, reachable=True)


def verify_backend(
    lane: str,
    *,
    base_url: str,
    cfg_ctx: int | None,
    gate_slots: int | None,
    props: PropsSnapshot | None = None,
) -> list[tuple[str, str]]:
    """Compare yaml vs /props. Returns list of (kind, message) where kind is warn|info.

    Rules:
    - gate_slots > total_slots → warn
    - cfg_ctx > server n_ctx → warn
    - cfg_ctx < server n_ctx → info (intentional headroom)
    - unreachable → empty (caller already health-warns)
    """
    snap = props if props is not None else fetch_props(base_url)
    if not snap.reachable:
        return []

    messages: list[tuple[str, str]] = []

    if gate_slots is not None and snap.total_slots is not None:
        if gate_slots > snap.total_slots:
            messages.append((
                "warn",
                (
                    f"{lane}: backends.gate slots={gate_slots} > server total_slots="
                    f"{snap.total_slots} (yaml is reference; raise --parallel or lower gate)"
                ),
            ))

    if cfg_ctx is not None and snap.n_ctx is not None:
        if cfg_ctx > snap.n_ctx:
            messages.append((
                "warn",
                (
                    f"{lane}: config ctx={cfg_ctx} > server n_ctx={snap.n_ctx} "
                    f"(client budget exceeds server — raise -c or lower ctx)"
                ),
            ))
        elif cfg_ctx < snap.n_ctx:
            messages.append((
                "info",
                (
                    f"{lane}: server n_ctx={snap.n_ctx}; client budget ctx={cfg_ctx} "
                    f"— headroom OK"
                ),
            ))

    return messages


def verify_config_backends(
    config: dict[str, Any],
    *,
    fetch=fetch_props,
) -> list[tuple[str, str]]:
    """Run verify_backend for orch and atomic lanes present in config."""
    llm = config.get("llm") or {}
    gate = ((config.get("backends") or {}).get("gate") or {})
    out: list[tuple[str, str]] = []

    for lane, gate_key in (("orchestrator", "orch_slots"), ("atomic", "atomic_slots")):
        cfg = llm.get(lane) or {}
        base_url = cfg.get("base_url")
        if not base_url:
            continue
        props = fetch(base_url)
        out.extend(
            verify_backend(
                lane,
                base_url=base_url,
                cfg_ctx=int(cfg["ctx"]) if cfg.get("ctx") is not None else None,
                gate_slots=int(gate[gate_key]) if gate.get(gate_key) is not None else None,
                props=props,
            )
        )
    return out
