"""Orchestrator vision / multimodal helpers (F5).

Probe llama.cpp ``/v1/models`` for multimodal capability, build OpenAI-style
``image_url`` data-URI parts from local paths, and keep session history as
lightweight path refs (re-encoded only when calling the LLM).

Atomic lane stays text-only — strip image parts before secondary calls.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

import httpx

# Soft cap on decoded image bytes before base64 (plan: 4–8 MB).
IMAGE_MAX_BYTES = 6 * 1024 * 1024
# How many images to keep as live multimodal parts in one LLM request.
MAX_LIVE_IMAGES = 2

IMAGE_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

VISION_OFF_HINT = (
    "Vision is disabled for this session. Restart the orchestrator with "
    "-WithVision (mmproj loaded), confirm GET /v1/models lists multimodal, "
    "then start a new Steward session. "
    "config: llm.orchestrator.vision=auto|on (currently off or probe failed)."
)


def is_image_path(path: str | Path) -> bool:
    """True when the path suffix is a supported image type."""
    return Path(path).suffix.lower() in IMAGE_MIME


def image_mime_for(path: str | Path) -> str:
    """Return MIME type for an image path (fallback via mimetypes)."""
    suffix = Path(path).suffix.lower()
    if suffix in IMAGE_MIME:
        return IMAGE_MIME[suffix]
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def vision_disabled_message() -> str:
    return VISION_OFF_HINT


def probe_multimodal(base_url: str, *, timeout: float = 5.0) -> bool:
    """Return True if the server advertises multimodal / vision capability.

    Checks GET ``/v1/models`` (OpenAI + llama.cpp ``models`` list with
    ``capabilities``). Falls back to ``/models`` if needed.
    """
    base = base_url.rstrip("/")
    for path in ("/v1/models", "/models"):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(f"{base}{path}")
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            continue
        if _payload_has_multimodal(data):
            return True
    return False


def _payload_has_multimodal(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    for key in ("data", "models"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            caps = item.get("capabilities")
            if isinstance(caps, list) and _caps_include_vision(caps):
                return True
            if item.get("multimodal") is True:
                return True
            meta = item.get("meta")
            if isinstance(meta, dict) and meta.get("multimodal") is True:
                return True
    return False


def _caps_include_vision(caps: list[Any]) -> bool:
    for c in caps:
        if not isinstance(c, str):
            continue
        low = c.lower()
        if low in ("multimodal", "vision") or "multimodal" in low:
            return True
    return False


def resolve_vision_enabled(
    mode: str | bool | None,
    *,
    base_url: str,
    probe: bool | None = None,
) -> tuple[bool, str]:
    """Resolve ``llm.orchestrator.vision`` → (enabled, reason).

    Modes: ``auto`` (probe), ``on`` / True (require), ``off`` / False (refuse).
    """
    if isinstance(mode, bool):
        normalized = "on" if mode else "off"
    else:
        normalized = str(mode or "auto").strip().lower()

    if normalized in ("off", "false", "no", "0"):
        return False, "config vision=off"
    if normalized in ("on", "true", "yes", "1", "require"):
        ok = probe if probe is not None else probe_multimodal(base_url)
        if ok:
            return True, "config vision=on (probe ok)"
        return False, "config vision=on but probe found no multimodal capability"
    # auto (default)
    ok = probe if probe is not None else probe_multimodal(base_url)
    if ok:
        return True, "config vision=auto (probe ok)"
    return False, "config vision=auto (probe: no multimodal)"


def make_image_ref(path: str | Path, *, mime: str | None = None) -> dict[str, Any]:
    """Session-safe image part (path + mime; no base64)."""
    p = Path(path).expanduser()
    return {
        "type": "image_ref",
        "path": str(p),
        "mime": mime or image_mime_for(p),
    }


def encode_image_data_uri(path: str | Path, *, max_bytes: int = IMAGE_MAX_BYTES) -> tuple[str, str | None]:
    """Read image bytes → ``data:<mime>;base64,…``. Returns (uri, error)."""
    p = Path(path).expanduser()
    try:
        if not p.is_file():
            return "", f"Image not found: {p}"
        size = p.stat().st_size
        if size > max_bytes:
            return "", (
                f"Image too large ({size:,} bytes > {max_bytes:,}). "
                f"Resize or compress before /image."
            )
        raw = p.read_bytes()
    except OSError as e:
        return "", f"Cannot read image {p}: {e}"
    mime = image_mime_for(p)
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}", None


def image_url_part(data_uri: str) -> dict[str, Any]:
    """OpenAI-compatible image_url content part."""
    return {"type": "image_url", "image_url": {"url": data_uri}}


def build_user_image_content(
    text: str,
    image_paths: list[str | Path],
    *,
    as_refs: bool = True,
) -> list[dict[str, Any]]:
    """Build multimodal user content: text + image_ref or image_url parts."""
    parts: list[dict[str, Any]] = [{"type": "text", "text": text or "[image]"}]
    for raw in image_paths:
        if as_refs:
            parts.append(make_image_ref(raw))
        else:
            uri, err = encode_image_data_uri(raw)
            if err:
                parts.append({"type": "text", "text": f"[image error: {err}]"})
            else:
                parts.append(image_url_part(uri))
    return parts


def content_text_preview(content: Any) -> str:
    """Flatten content to a short string for logs / paste checks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                bits.append(str(part.get("text") or ""))
            elif ptype == "image_ref":
                bits.append(f"[image:{part.get('path', '?')}]")
            elif ptype == "image_url":
                bits.append("[image]")
        return "\n".join(b for b in bits if b)
    return str(content or "")


def content_has_images(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") in ("image_ref", "image_url"):
            return True
    return False


def messages_have_images(messages: list[dict[str, Any]]) -> bool:
    return any(content_has_images(m.get("content")) for m in messages)


def strip_images_for_text_lane(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Replace image parts with short text placeholders (atomic / text-only)."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        m = dict(msg)
        content = m.get("content")
        if not isinstance(content, list):
            out.append(m)
            continue
        texts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                texts.append(str(part.get("text") or ""))
            elif ptype == "image_ref":
                texts.append(f"[image omitted for text-only lane: {part.get('path', '?')}]")
            elif ptype == "image_url":
                texts.append("[image omitted for text-only lane]")
        m["content"] = "\n".join(t for t in texts if t).strip() or "[image omitted]"
        out.append(m)
    return out


def materialize_image_refs(
    messages: list[dict[str, Any]],
    *,
    max_images: int = MAX_LIVE_IMAGES,
    max_bytes: int = IMAGE_MAX_BYTES,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert ``image_ref`` → ``image_url`` data URIs; cap to last *max_images*.

    Older images become text placeholders. Returns (messages, errors).
    """
    # Collect (msg_idx, part_idx) for image_ref / image_url in order.
    locations: list[tuple[int, int]] = []
    for mi, msg in enumerate(messages):
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for pi, part in enumerate(content):
            if isinstance(part, dict) and part.get("type") in ("image_ref", "image_url"):
                locations.append((mi, pi))

    keep = set(locations[-max_images:]) if max_images > 0 else set()
    errors: list[str] = []
    out: list[dict[str, Any]] = []

    for mi, msg in enumerate(messages):
        m = dict(msg)
        content = m.get("content")
        if not isinstance(content, list):
            out.append(m)
            continue
        new_parts: list[dict[str, Any]] = []
        for pi, part in enumerate(content):
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype not in ("image_ref", "image_url"):
                if ptype == "text":
                    new_parts.append({"type": "text", "text": str(part.get("text") or "")})
                else:
                    new_parts.append(dict(part))
                continue
            if (mi, pi) not in keep:
                label = part.get("path") or "prior image"
                new_parts.append({
                    "type": "text",
                    "text": f"[image omitted from context (cap {max_images}): {label}]",
                })
                continue
            if ptype == "image_url":
                # Already materialized (rare in session store).
                new_parts.append(dict(part))
                continue
            path = part.get("path") or ""
            uri, err = encode_image_data_uri(path, max_bytes=max_bytes)
            if err:
                errors.append(err)
                new_parts.append({"type": "text", "text": f"[image error: {err}]"})
            else:
                new_parts.append(image_url_part(uri))
        # Collapse to plain string if only one text part and no images.
        if len(new_parts) == 1 and new_parts[0].get("type") == "text":
            m["content"] = new_parts[0].get("text") or ""
        else:
            m["content"] = new_parts
        out.append(m)
    return out, errors
