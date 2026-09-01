"""Session persistence — save/load/switch named sessions.

Each session stores the conversation history and discovered skill chain.
Sessions are saved as JSON files in the sessions/ directory.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
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

    def add_message(
        self,
        role: str,
        content: str | list[Any],
        *,
        name: str | None = None,
        reasoning_content: str | None = None,
    ):
        """Append a message. ``content`` may be a string or multimodal parts list."""
        msg: dict[str, Any] = {"role": role, "content": content}
        if name is not None:
            msg["name"] = name
        if reasoning_content:
            msg["reasoning_content"] = reasoning_content
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

    def session_dir(self, name: str) -> Path:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        p = self.dir / safe_name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _session_path(self, name: str) -> Path:
        return self.session_dir(name) / f"{name}.json"

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def new(self, name: str) -> Session:
        """Create a new session."""
        from core.primitives import get_workspace_dir
        session = Session(
            name=name,
            metadata={
                "workspace": str(get_workspace_dir()),
                "turn_count": 0,
                "last_active": time.time(),
            },
        )
        self.current = session
        self.save()
        return session

    def new_ephemeral(self, parent: str = "default", task_label: str = "") -> Session:
        """Create an isolated, ephemeral sandbox session with zero context carryover."""
        from core.primitives import get_workspace_dir
        e_id = f"eph_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        eph_dir = self.dir / ".ephemeral" / e_id
        eph_dir.mkdir(parents=True, exist_ok=True)
        
        session = Session(
            name=e_id,
            metadata={
                "workspace": str(get_workspace_dir()),
                "is_ephemeral": True,
                "parent": parent,
                "task_label": task_label,
                "turn_count": 0,
                "last_active": time.time(),
                "created_at": time.time(),
            },
        )
        # Write initial session file inside .ephemeral directory
        eph_path = eph_dir / f"{e_id}.json"
        self._atomic_json_write(eph_path, asdict(session))
        return session

    def cleanup_ephemeral(self, name: str) -> bool:
        """Remove an ephemeral session directory from disk."""
        eph_dir = self.dir / ".ephemeral" / name
        if eph_dir.exists():
            import shutil
            shutil.rmtree(eph_dir, ignore_errors=True)
            return True
        return False

    def list_ephemeral(self) -> list[dict[str, Any]]:
        """List active ephemeral sessions."""
        eph_root = self.dir / ".ephemeral"
        if not eph_root.exists():
            return []
        items = []
        for p in eph_root.glob("*/*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                items.append({
                    "name": data.get("name", p.stem),
                    "parent": data.get("metadata", {}).get("parent", ""),
                    "task_label": data.get("metadata", {}).get("task_label", ""),
                    "turn_count": len(data.get("messages", [])),
                    "created_at": data.get("created_at", p.stat().st_ctime),
                    "last_active": data.get("metadata", {}).get("last_active", p.stat().st_mtime),
                })
            except Exception:
                continue
        return items

    def _atomic_json_write(self, path: Path, data: dict) -> None:
        """Write JSON atomically via temp-file-rename (NTFS same-volume safe)."""
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), suffix=".tmp", prefix=".session_"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            Path(tmp_path).replace(path)  # atomic on NTFS
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def save(self):
        """Save the current session to disk."""
        if not self.current:
            return
        from core.primitives import get_workspace_dir
        if "workspace" not in self.current.metadata:
            self.current.metadata["workspace"] = str(get_workspace_dir())
        self.current.metadata["turn_count"] = len(self.current.messages)
        self.current.metadata["last_active"] = time.time()
        path = self._session_path(self.current.name)
        data = asdict(self.current)
        self._atomic_json_write(path, data)

    def load(self, name: str) -> Session:
        """Load a session by name."""
        path = self._session_path(name)
        if not path.exists():
            # Fallback to old flat location if it exists
            flat_path = self.dir / f"{name}.json"
            if flat_path.exists():
                # Move to the new nested directory structure
                path.parent.mkdir(parents=True, exist_ok=True)
                flat_path.rename(path)
                # Clean up other flat companion files if any
                for suffix in (".think.jsonl", ".interactions.jsonl", ".memory.jsonl", ".memory.md"):
                    old_file = self.dir / f"{name}{suffix}"
                    if old_file.exists():
                        old_file.rename(path.parent / f"{name}{suffix}")
            else:
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
        paths = []
        # Find new folder-scoped session files
        for path in sorted(self.dir.glob("*/*.json")):
            if path.parent.name == path.stem:
                paths.append(path)
        # Find legacy flat files
        for path in sorted(self.dir.glob("*.json")):
            paths.append(path)
            
        seen_names = set()
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                name = data.get("name", path.stem)
                if name in seen_names:
                    continue
                seen_names.add(name)
                meta = data.get("metadata") or {}
                sessions.append({
                    "name": name,
                    "messages": len(data.get("messages", [])),
                    "skills": len(data.get("discovered_skills", [])),
                    "updated_at": data.get("updated_at", 0),
                    "workspace": meta.get("workspace", ""),
                    "turn_count": meta.get("turn_count", len(data.get("messages", []))),
                    "parent": meta.get("parent"),
                    "status": meta.get("status"),
                    "children": list(meta.get("children") or []),
                    "orch_id_slot": meta.get("orch_id_slot"),
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
            self._atomic_json_write(path, asdict(session))
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        meta = data.setdefault("metadata", {})
        meta.update(updates)
        data["updated_at"] = time.time()
        self._atomic_json_write(path, data)
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
