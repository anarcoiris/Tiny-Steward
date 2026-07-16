"""Session persistence — save/load/switch named sessions.

Each session stores the conversation history and discovered skill chain.
Sessions are saved as JSON files in the sessions/ directory.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class Session:
    """A persisted conversation session."""

    name: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: list[dict[str, str]] = field(default_factory=list)
    discovered_skills: list[str] = field(default_factory=list)  # slugs used during session
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, *, name: str | None = None):
        msg: dict[str, Any] = {"role": role, "content": content}
        if name is not None:
            msg["name"] = name
        self.messages.append(msg)
        self.updated_at = time.time()

    def record_skill(self, slug: str):
        if slug not in self.discovered_skills:
            self.discovered_skills.append(slug)
            self.updated_at = time.time()


class SessionManager:
    """Manages named sessions on disk."""

    def __init__(self, sessions_dir: str | Path):
        self.dir = Path(sessions_dir).expanduser().resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.current: Session | None = None
        self._cleanup_temp_dir()

    def _cleanup_temp_dir(self):
        temp_dir = self.dir / ".temp"
        if not temp_dir.exists():
            return
        now = time.time()
        for f in temp_dir.glob("*.txt"):
            try:
                # remove files older than 6 hours
                if now - f.stat().st_mtime > 6 * 3600:
                    f.unlink()
            except Exception:
                pass

    def _session_path(self, name: str) -> Path:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return self.dir / f"{safe_name}.json"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def new(self, name: str) -> Session:
        """Create a new session."""
        session = Session(name=name)
        self.current = session
        self.save()
        return session

    def save(self):
        """Save the current session to disk."""
        if not self.current:
            return
        path = self._session_path(self.current.name)
        data = asdict(self.current)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load(self, name: str) -> Session:
        """Load a session by name."""
        path = self._session_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Session '{name}' not found at {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        # Force the session name to be the loaded session name to keep filename and internal name aligned
        data["name"] = name
        
        from dataclasses import fields
        valid_keys = {f.name for f in fields(Session)}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        session = Session(**filtered_data)
        self.current = session
        return session

    def switch(self, name: str) -> Session:
        """Save current session and switch to another (load or create)."""
        self.save()
        try:
            return self.load(name)
        except FileNotFoundError:
            return self.new(name)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all saved sessions with summary info."""
        sessions = []
        for path in sorted(self.dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                meta = data.get("metadata") or {}
                sessions.append({
                    "name": data.get("name", path.stem),
                    "messages": len(data.get("messages", [])),
                    "skills": len(data.get("discovered_skills", [])),
                    "updated_at": data.get("updated_at", 0),
                    "parent": meta.get("parent"),
                    "status": meta.get("status"),
                    "children": list(meta.get("children") or []),
                })
            except Exception:
                continue
        return sessions

    def list_tree(self) -> list[dict[str, Any]]:
        """Return sessions shaped for a parent→children tree display."""
        sessions = self.list_sessions()
        by_name = {s["name"]: s for s in sessions}
        roots = []
        for s in sessions:
            parent = s.get("parent")
            if not parent or parent not in by_name:
                roots.append(s)
        return roots

    def register_child(self, parent_name: str, child_name: str) -> None:
        """Append child_name to parent's metadata.children (loads/saves parent)."""
        path = self._session_path(parent_name)
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data.setdefault("metadata", {})
        children = list(meta.get("children") or [])
        if child_name not in children:
            children.append(child_name)
            meta["children"] = children
            data["updated_at"] = time.time()
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if self.current and self.current.name == parent_name:
            self.current.metadata["children"] = children

    def load_metadata(self, name: str) -> dict[str, Any]:
        path = self._session_path(name)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return dict(data.get("metadata") or {})
        except Exception:
            return {}

    def update_session_metadata(self, name: str, updates: dict[str, Any]) -> None:
        path = self._session_path(name)
        if not path.exists():
            # Create a minimal session shell so child can mark status before first save.
            session = Session(name=name, metadata=dict(updates))
            path.write_text(json.dumps(asdict(session), indent=2, ensure_ascii=False), encoding="utf-8")
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data.setdefault("metadata", {})
        meta.update(updates)
        data["updated_at"] = time.time()
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if self.current and self.current.name == name:
            self.current.metadata.update(updates)

    def delete(self, name: str) -> bool:
        """Delete a session."""
        path = self._session_path(name)
        if path.exists():
            path.unlink()
            if self.current and self.current.name == name:
                self.current = None
            return True
        return False
