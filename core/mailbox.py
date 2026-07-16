"""Maildir-style session mailbox — stdlib only, no locks.

Each session has ``sessions/.mailbox/<session>/inbox/``. Messages are
individual JSON files ``{ts}-{uuid}.json``. Write = new file (atomic via
temp + rename). Read = drain directory and delete consumed messages.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
DEFAULT_MAX_BYTES = 256_000


class Mailbox:
    """Per-session inbox under a sessions root directory."""

    def __init__(self, sessions_dir: str | Path, session_id: str):
        self.sessions_dir = Path(sessions_dir).expanduser().resolve()
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        self.session_id = safe
        self.inbox = self.sessions_dir / ".mailbox" / safe / "inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)

    def send(
        self,
        *,
        from_session: str,
        to_session: str | None = None,
        content: str,
        msg_type: str = "supervision_question",
        priority: str = "normal",
        blocking: bool = False,
        in_reply_to: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Path:
        """Write a new message into this mailbox's inbox. Returns the file path."""
        payload: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "from": from_session,
            "to": to_session or self.session_id,
            "priority": priority if priority in PRIORITY_ORDER else "normal",
            "type": msg_type,
            "content": content,
            "blocking": blocking,
            "in_reply_to": in_reply_to,
            "ts": time.time(),
        }
        if extra:
            payload.update(extra)

        ts = int(payload["ts"] * 1000)
        name = f"{ts}-{payload['id']}.json"
        final = self.inbox / name
        tmp = self.inbox / f".{name}.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(final)
        return final

    def drain(
        self,
        *,
        skip_types: frozenset[str] | set[str] | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> list[dict[str, Any]]:
        """Read and delete inbox messages, ordered by blocking → priority → ts.

        Messages whose ``type`` is in ``skip_types`` are left on disk (e.g.
        ``delegate_result`` for the parent wait loop). Corrupt JSON is logged
        and moved aside instead of silent drop.
        """
        skip = set(skip_types or ())
        messages: list[dict[str, Any]] = []
        files = sorted(self.inbox.glob("*.json"))
        for path in files:
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError as e:
                print(f"  [warn] mailbox: cannot read {path.name}: {e}")
                continue

            if len(raw.encode("utf-8")) > max_bytes:
                print(
                    f"  [warn] mailbox: {path.name} exceeds {max_bytes} bytes — quarantined"
                )
                self._quarantine(path, reason="too_large")
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"  [warn] mailbox: corrupt JSON in {path.name}: {e}")
                self._quarantine(path, reason="corrupt_json")
                continue

            if not isinstance(data, dict):
                print(f"  [warn] mailbox: non-object JSON in {path.name} — quarantined")
                self._quarantine(path, reason="not_object")
                continue

            if str(data.get("type", "")) in skip:
                continue

            messages.append(data)
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

        messages.sort(
            key=lambda m: (
                0 if m.get("blocking") else 1,
                PRIORITY_ORDER.get(str(m.get("priority", "normal")), 2),
                float(m.get("ts", 0)),
            )
        )
        return messages

    def _quarantine(self, path: Path, *, reason: str) -> None:
        dest = path.with_suffix(path.suffix + f".{reason}")
        try:
            path.replace(dest)
        except OSError:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def peek(self) -> list[dict[str, Any]]:
        """List messages without deleting them."""
        out: list[dict[str, Any]] = []
        for path in sorted(self.inbox.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    out.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return out


def mailbox_for(sessions_dir: str | Path, session_id: str) -> Mailbox:
    return Mailbox(sessions_dir, session_id)
