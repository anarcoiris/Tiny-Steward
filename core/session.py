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

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
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
                sessions.append({
                    "name": data.get("name", path.stem),
                    "messages": len(data.get("messages", [])),
                    "skills": len(data.get("discovered_skills", [])),
                    "updated_at": data.get("updated_at", 0),
                })
            except Exception:
                continue
        return sessions

    def delete(self, name: str) -> bool:
        """Delete a session."""
        path = self._session_path(name)
        if path.exists():
            path.unlink()
            if self.current and self.current.name == name:
                self.current = None
            return True
        return False
