"""Interaction logging and review system.

Logs user-agent exchanges to a JSONL file per session for later review
and self-improvement. Rotates files if they get too large.
Generates an HTML report for easy viewing.
"""

from __future__ import annotations
import json
import time
import datetime
from pathlib import Path
from typing import Any, Optional


class InteractionLog:
    def __init__(self, sessions_dir: str | Path, session_name: str, max_lines: int = 1000):
        self.dir = Path(sessions_dir).expanduser().resolve()
        self.session_name = session_name
        self.max_lines = max_lines
        self.log_path = self.dir / f"{session_name}.interactions.jsonl"
        self._rotate_if_needed()
        
        self.current_interaction: dict[str, Any] | None = None

    def _rotate_if_needed(self):
        """Rotate the log file to old_YYYYMMDD_HHMMSS.jsonl if it exceeds max_lines."""
        if not self.log_path.exists():
            return
            
        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                lines = sum(1 for _ in f)
                
            if lines >= self.max_lines:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_path = self.dir / f"old_{self.session_name}_{ts}.jsonl"
                self.log_path.rename(archive_path)
        except Exception:
            pass

    def begin_interaction(self, user_input: str):
        self.current_interaction = {
            "id": str(time.time()),
            "ts": datetime.datetime.now().isoformat() + "Z",
            "session": self.session_name,
            "user_input": user_input,
            "turns": 0,
            "actions": [],
            "outcome": "unknown",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "elapsed_s": 0.0,
            "skills_used": [],
            "errors": [],
            "reviewed": False,
            "rating": None,
            "notes": ""
        }

    def record_action(self, name: str, body: str, exit_code: int):
        if not self.current_interaction:
            return
        
        preview = body.replace("\n", " ").strip()
        if len(preview) > 80:
            preview = preview[:77] + "..."
            
        self.current_interaction["actions"].append({
            "name": name,
            "body_preview": preview,
            "exit_code": exit_code
        })
        
        if exit_code != 0:
            self.current_interaction["errors"].append(f"{name} exited with {exit_code}")

    def end_interaction(self, outcome: str, turns: int, prompt_tokens: int, completion_tokens: int, elapsed_s: float):
        if not self.current_interaction:
            return
            
        self.current_interaction["outcome"] = outcome
        self.current_interaction["turns"] = turns
        self.current_interaction["prompt_tokens"] = prompt_tokens
        self.current_interaction["completion_tokens"] = completion_tokens
        self.current_interaction["elapsed_s"] = elapsed_s
        
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(self.current_interaction) + "\n")
        except Exception:
            pass
            
        self.current_interaction = None

    def list_unreviewed(self) -> list[dict[str, Any]]:
        """Return a list of unreviewed interaction records."""
        if not self.log_path.exists():
            return []
            
        unreviewed = []
        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        if not record.get("reviewed"):
                            unreviewed.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return unreviewed

    def mark_reviewed(self, interaction: dict[str, Any], rating: Optional[str], notes: str):
        """Mark an interaction as reviewed and rewrite the log file."""
        if not self.log_path.exists():
            return
            
        target_id = interaction.get("id")
        if not target_id:
            return
            
        records = []
        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                        
            # Update the specific record
            for r in records:
                if r.get("id") == target_id:
                    r["reviewed"] = True
                    r["rating"] = rating
                    r["notes"] = notes
                    break
                    
            # Rewrite file
            with self.log_path.open("w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
        except Exception:
            pass

    def generate_html_report(self) -> str:
        """Generate an HTML report of interactions and return its path."""
        records = []
        if self.log_path.exists():
            try:
                with self.log_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            records.append(json.loads(line))
            except Exception:
                pass
                
        html_path = self.dir / f"{self.session_name}_review.html"
        
        # Simple HTML generation
        html = [
            "<html><head><title>Interaction Review Report</title>",
            "<style>body { font-family: sans-serif; background: #1e1e1e; color: #d4d4d4; padding: 20px; }",
            ".record { background: #252526; padding: 15px; margin-bottom: 20px; border-radius: 5px; border-left: 5px solid #007acc; }",
            ".error { border-left-color: #f48771; }",
            ".reviewed { opacity: 0.7; }",
            "code { background: #1e1e1e; padding: 2px 5px; border-radius: 3px; color: #ce9178; }",
            "</style></head><body>",
            f"<h1>Interaction Review: {self.session_name}</h1>"
        ]
        
        for r in reversed(records):  # Show newest first
            ts = r.get("ts", "")[:19].replace("T", " ")
            status_class = "error" if r.get("outcome") != "success" else ""
            reviewed_class = "reviewed" if r.get("reviewed") else ""
            
            html.append(f"<div class='record {status_class} {reviewed_class}'>")
            html.append(f"<h3>[{ts}] {r.get('user_input', '')}</h3>")
            html.append(f"<p><strong>Outcome:</strong> {r.get('outcome')} | <strong>Turns:</strong> {r.get('turns')} | <strong>Elapsed:</strong> {r.get('elapsed_s', 0):.1f}s</p>")
            
            if r.get("reviewed"):
                html.append(f"<p><strong>Rating:</strong> {r.get('rating')} | <strong>Notes:</strong> {r.get('notes')}</p>")
                
            if r.get("actions"):
                html.append("<h4>Actions:</h4><ul>")
                for a in r.get("actions", []):
                    mark = "❌" if a.get("exit_code") != 0 else "✅"
                    html.append(f"<li>{mark} {a.get('name')}: <code>{a.get('body_preview')}</code></li>")
                html.append("</ul>")
                
            html.append("</div>")
            
        html.append("</body></html>")
        
        try:
            html_path.write_text("\n".join(html), encoding="utf-8")
        except Exception:
            return ""
            
        return str(html_path)
