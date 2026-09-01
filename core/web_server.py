"""FastAPI Web Server for Tiny Steward Web IDE & Control Center.

Provides REST and SSE endpoints for:
- Agent streaming chat & reasoning (<think> blocks)
- Session management & switching
- File tree navigation & file reading/writing
- Task & Plan Kanban board synchronization
- Memory daily notes & graph JSON
- GPU telemetry & system status
"""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.session import SessionManager
from core.llm import LLMClient
from core.embedder import Embedder
from core.help import HelpEngine
from core.idle_loop import SharedExecutionLock
import yaml

# Initialize FastAPI app
app = FastAPI(title="Tiny Steward Web IDE & Control Center")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Workspace Root
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_DIR = WORKSPACE_ROOT / "sessions"
session_manager = SessionManager(SESSIONS_DIR)

# Mount web static directory
WEB_DIR = WORKSPACE_ROOT / "web"
if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")


# Pydantic Schemas
class SwitchSessionRequest(BaseModel):
    name: str

class CreateSessionRequest(BaseModel):
    name: str

class SaveFileRequest(BaseModel):
    path: str
    content: str

class UpdateTaskRequest(BaseModel):
    task_id: str
    status: str

class ChatPromptRequest(BaseModel):
    prompt: str
    session: str = "default"


# Helper Functions
def get_gpu_metrics() -> List[Dict[str, Any]]:
    gpus = []
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            for line in res.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 7:
                    used = int(parts[2])
                    total = int(parts[3])
                    pct = round((used / total) * 100, 1) if total > 0 else 0.0
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memoryUsedMb": used,
                        "memoryTotalMb": total,
                        "memoryPct": pct,
                        "gpuUtilPct": int(parts[4]),
                        "tempC": int(parts[5]),
                        "powerW": parts[6]
                    })
    except Exception:
        pass
    return gpus


def build_file_tree(dir_path: Path, relative_to: Path, max_depth: int = 4) -> List[Dict[str, Any]]:
    if max_depth <= 0:
        return []
    items = []
    ignore_names = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", ".temp", ".think_logs"}
    
    try:
        for entry in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if entry.name in ignore_names or entry.name.startswith("."):
                continue
            rel_path = str(entry.relative_to(relative_to)).replace("\\", "/")
            item = {
                "name": entry.name,
                "path": rel_path,
                "is_dir": entry.is_dir()
            }
            if entry.is_dir():
                item["children"] = build_file_tree(entry, relative_to, max_depth - 1)
            items.append(item)
    except Exception:
        pass
    return items


# Routes
@app.get("/")
async def root():
    dashboard_file = WORKSPACE_ROOT / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(dashboard_file)
    return {"message": "Tiny Steward Web Server Online"}

@app.get("/assembled-graph.json")
async def get_graph():
    graph_file = WORKSPACE_ROOT / "assembled-graph.json"
    if graph_file.exists():
        return FileResponse(graph_file)
    return {"nodes": [], "links": []}


@app.get("/api/status")
async def get_status():
    lock = SharedExecutionLock(SESSIONS_DIR)
    st = lock.get_shared_status()
    return {
        "status": "online",
        "timestamp": time.time(),
        "active_session": session_manager.current.name if session_manager.current else "default",
        "lock": st
    }


@app.get("/api/telemetry")
async def get_telemetry():
    gpus = get_gpu_metrics()
    return {
        "timestamp": time.time(),
        "gpus": gpus
    }


@app.get("/api/sessions")
async def list_sessions():
    sessions = []
    if SESSIONS_DIR.exists():
        for item in SESSIONS_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                sessions.append(item.name)
    if not sessions:
        sessions = ["default"]
    return {
        "current": session_manager.current.name if session_manager.current else "default",
        "sessions": sorted(sessions)
    }


@app.post("/api/sessions/switch")
async def switch_sess(req: SwitchSessionRequest):
    try:
        session_manager.switch(req.name)
        return {"status": "ok", "current": req.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sessions/create")
async def create_sess(req: CreateSessionRequest):
    try:
        session_manager.new(req.name)
        return {"status": "ok", "current": req.name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/files/tree")
async def get_tree():
    tree = build_file_tree(WORKSPACE_ROOT, WORKSPACE_ROOT)
    return tree


@app.get("/api/files/content")
async def get_file_content(path: str = Query(...)):
    safe_path = (WORKSPACE_ROOT / path).resolve()
    if not str(safe_path).startswith(str(WORKSPACE_ROOT)):
        raise HTTPException(status_code=403, detail="Path outside workspace boundary")
    if not safe_path.exists() or safe_path.is_dir():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = safe_path.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/files/save")
async def save_file_content(req: SaveFileRequest):
    safe_path = (WORKSPACE_ROOT / req.path).resolve()
    if not str(safe_path).startswith(str(WORKSPACE_ROOT)):
        raise HTTPException(status_code=403, detail="Path outside workspace boundary")
    try:
        safe_path.write_text(req.content, encoding="utf-8")
        return {"status": "ok", "path": req.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks")
async def get_tasks():
    columns = {"backlog": [], "todo": [], "in_progress": [], "review": [], "done": []}
    task_file = WORKSPACE_ROOT / "task.md"
    if task_file.exists():
        lines = task_file.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if line_str.startswith("- [x]"):
                columns["done"].append({"id": f"task_{idx}", "title": line_str[5:].strip(), "source": "task.md", "status": "done"})
            elif line_str.startswith("- [ ]"):
                columns["todo"].append({"id": f"task_{idx}", "title": line_str[5:].strip(), "source": "task.md", "status": "todo"})
    return columns


@app.post("/api/tasks/update")
async def update_task(req: UpdateTaskRequest):
    return {"status": "ok", "task_id": req.task_id, "new_status": req.status}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatPromptRequest):
    async def sse_generator():
        # Yield initial thinking chunk
        yield f"data: {json.dumps({'type': 'think', 'content': 'Analyzing user prompt and checking session state...\\n'})}\n\n"
        await asyncio.sleep(0.2)
        
        yield f"data: {json.dumps({'type': 'token', 'content': f'Received request in session [{req.session}]: {req.prompt}\\n\\nTiny Steward Web IDE agent is processing.'})}\n\n"
        await asyncio.sleep(0.1)
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/providers/status")
async def get_providers_status():
    cfg_file = WORKSPACE_ROOT / "config.yaml"
    cfg = {}
    if cfg_file.exists():
        try:
            cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    orch_cfg = cfg.get("llm", {}).get("orchestrator", {})
    client = LLMClient.from_lane_config(orch_cfg)
    statuses = client.get_provider_statuses()
    client.close()
    return {"status": "ok", "providers": statuses}


@app.get("/api/extensions/list")
async def get_extensions_list():
    from core.extensions import ExtensionManager
    cfg_file = WORKSPACE_ROOT / "config.yaml"
    cfg = {}
    if cfg_file.exists():
        try:
            cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
        except Exception:
            pass
    mgr = ExtensionManager(workspace_root=WORKSPACE_ROOT, config=cfg)
    return {"status": "ok", "extensions": mgr.get_all_extensions()}


# ─── Dashboard & Monitoring Endpoints ─────────────────────────

@app.get("/api/v1/sessions/tree")
async def get_sessions_tree():
    """Return tree of active, child, and ephemeral sessions."""
    all_sessions = session_manager.list_sessions()
    ephemeral = session_manager.list_ephemeral()
    return {
        "current": session_manager.current.name if session_manager.current else "default",
        "persistent_sessions": all_sessions,
        "ephemeral_sessions": ephemeral,
        "total_sessions": len(all_sessions) + len(ephemeral),
    }


@app.get("/api/v1/mailbox/queue")
async def get_mailbox_queue():
    """Inspect all active session mailboxes and message priority counts."""
    mb_root = SESSIONS_DIR / ".mailbox"
    boxes = {}
    priority_counts = {"urgent": 0, "high": 0, "normal": 0, "low": 0}
    total_messages = 0

    if mb_root.exists():
        for sdir in mb_root.iterdir():
            if not sdir.is_dir():
                continue
            inbox = sdir / "inbox"
            if not inbox.exists():
                continue
            messages = []
            for p in sorted(inbox.glob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    prio = data.get("priority", "normal")
                    if prio in priority_counts:
                        priority_counts[prio] += 1
                    total_messages += 1
                    messages.append({
                        "id": data.get("id", p.stem),
                        "from": data.get("from", "unknown"),
                        "to": data.get("to", sdir.name),
                        "type": data.get("type", "message"),
                        "priority": prio,
                        "blocking": bool(data.get("blocking", False)),
                        "content_preview": str(data.get("content", ""))[:120],
                        "ts": data.get("ts", p.stat().st_mtime),
                    })
                except Exception:
                    continue
            if messages:
                boxes[sdir.name] = messages

    return {
        "total_messages": total_messages,
        "priority_breakdown": priority_counts,
        "mailboxes": boxes,
    }


@app.get("/api/v1/tasks/background")
async def get_background_tasks():
    """Return all background tasks tracked by TaskRunner."""
    from core.task_runner import get_task_runner
    runner = get_task_runner(WORKSPACE_ROOT)
    tasks = runner.list_all()
    return {
        "total_tasks": len(tasks),
        "running": sum(1 for t in tasks if t.get("status") == "running"),
        "tasks": tasks,
    }


class KillTaskRequest(BaseModel):
    task_id: str


@app.post("/api/v1/tasks/kill")
async def kill_background_task(req: KillTaskRequest):
    """Terminate a background task by ID."""
    from core.task_runner import get_task_runner
    runner = get_task_runner(WORKSPACE_ROOT)
    success = runner.kill(req.task_id)
    return {"status": "ok" if success else "failed", "task_id": req.task_id, "killed": success}


@app.get("/api/v1/tasks/tail")
async def tail_task_log(task_id: str = Query(...), lines: int = Query(50)):
    """Tail log output of a specific background task."""
    from core.task_runner import get_task_runner
    runner = get_task_runner(WORKSPACE_ROOT)
    tail = runner.tail_log(task_id, lines=lines)
    return {"task_id": task_id, "lines": lines, "output": tail}

