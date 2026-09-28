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
import ctypes
import json
import os
import shutil
import socket
import subprocess
import threading
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
from dataclasses import asdict

from core.agora import AgoraForum, AgoraAwakener, AgoraDispatcher, Persona, AgoraMessage

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

FABRICA_LANDING_DIR = WORKSPACE_ROOT / "fabrica" / "web" / "landing"
if FABRICA_LANDING_DIR.exists():
    app.mount("/fabrica-web", StaticFiles(directory=str(FABRICA_LANDING_DIR)), name="fabrica_web")


# Pydantic Schemas
class SwitchSessionRequest(BaseModel):
    name: str

class CreateSessionRequest(BaseModel):
    name: str

class SaveFileRequest(BaseModel):
    path: str
    content: str

class CreateFileRequest(BaseModel):
    path: str
    is_dir: Optional[bool] = False
    initial_content: Optional[str] = ""

class DeleteFileRequest(BaseModel):
    path: str

class UpdateTaskRequest(BaseModel):
    task_id: str
    status: str
    session: Optional[str] = "default"

class CreateTaskRequest(BaseModel):
    title: str
    status: Optional[str] = "todo"
    session: Optional[str] = "default"

class ChatPromptRequest(BaseModel):
    prompt: str
    session: str = "default"

class UpdateOrderStatusRequest(BaseModel):
    status: str
    carrier: Optional[str] = ""
    tracking_code: Optional[str] = ""
    operator_notes: Optional[str] = ""


# Helper Functions
# Windows Memory Info Struct
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


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


_telemetry_cache = None
_telemetry_cache_time = 0.0
_telemetry_lock = threading.Lock()


def get_system_telemetry() -> Dict[str, Any]:
    global _telemetry_cache, _telemetry_cache_time
    now = time.time()
    if _telemetry_cache is not None and (now - _telemetry_cache_time) < 2.0:
        return _telemetry_cache

    with _telemetry_lock:
        if _telemetry_cache is not None and (time.time() - _telemetry_cache_time) < 2.0:
            return _telemetry_cache

        ram_data = {"usedMb": 0, "totalMb": 0, "pct": 0.0}
        try:
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if hasattr(ctypes, "windll") and ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_mb = int(stat.ullTotalPhys / (1024 * 1024))
                avail_mb = int(stat.ullAvailPhys / (1024 * 1024))
                used_mb = total_mb - avail_mb
                pct = round((used_mb / total_mb) * 100, 1) if total_mb > 0 else 0.0
                ram_data = {"usedMb": used_mb, "totalMb": total_mb, "pct": pct}
        except Exception:
            pass

        disk_data = {"usedGb": 0.0, "totalGb": 0.0, "freeGb": 0.0, "pct": 0.0}
        try:
            usage = shutil.disk_usage(WORKSPACE_ROOT)
            total_gb = round(usage.total / (1024**3), 2)
            used_gb = round(usage.used / (1024**3), 2)
            free_gb = round(usage.free / (1024**3), 2)
            pct = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0
            disk_data = {"usedGb": used_gb, "totalGb": total_gb, "freeGb": free_gb, "pct": pct}
        except Exception:
            pass

        def check_port(host: str, port: int, timeout: float = 0.05) -> bool:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(timeout)
                    return s.connect_ex((host, port)) == 0
            except Exception:
                return False

        services = {
            "web_server": {"port": 8000, "alive": True},
            "ollama_guard": {"port": 11800, "alive": check_port("127.0.0.1", 11800)},
            "ollama": {"port": 11434, "alive": check_port("127.0.0.1", 11434)}
        }

        gpus = get_gpu_metrics()

        result = {
            "timestamp": time.time(),
            "ram": ram_data,
            "disk": disk_data,
            "services": services,
            "gpus": gpus,
            "active_session": session_manager.current.name if session_manager.current else "default"
        }
        _telemetry_cache = result
        _telemetry_cache_time = time.time()
        return result


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


_task_lock = threading.RLock()


def _resolve_session_task_file(session_name: Optional[str]) -> Path:
    if session_name and session_name != "default":
        sess_task = SESSIONS_DIR / session_name / "task.md"
        if sess_task.exists():
            return sess_task
    return WORKSPACE_ROOT / "task.md"


def _resolve_session_plan_file(session_name: Optional[str]) -> Path:
    if session_name and session_name != "default":
        sess_plan = SESSIONS_DIR / session_name / "plan.md"
        if sess_plan.exists():
            return sess_plan
    return WORKSPACE_ROOT / "plan.md"


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
    return await asyncio.to_thread(get_system_telemetry)


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
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(req.content, encoding="utf-8")
        return {"status": "ok", "path": req.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/files/create")
async def create_file_or_dir(req: CreateFileRequest):
    safe_path = (WORKSPACE_ROOT / req.path).resolve()
    if not str(safe_path).startswith(str(WORKSPACE_ROOT)):
        raise HTTPException(status_code=403, detail="Path outside workspace boundary")
    try:
        if req.is_dir:
            safe_path.mkdir(parents=True, exist_ok=True)
        else:
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            if not safe_path.exists():
                safe_path.write_text(req.initial_content or "", encoding="utf-8")
        return {"status": "ok", "path": req.path, "is_dir": bool(req.is_dir)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/files/delete")
async def delete_file_or_dir(req: DeleteFileRequest):
    safe_path = (WORKSPACE_ROOT / req.path).resolve()
    if not str(safe_path).startswith(str(WORKSPACE_ROOT)) or safe_path == WORKSPACE_ROOT:
        raise HTTPException(status_code=403, detail="Cannot delete workspace root or external files")
    
    # Critical protected folders
    rel_str = str(safe_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    if rel_str in [".git", "core", "sessions", "node_modules", "web"]:
        raise HTTPException(status_code=403, detail=f"Cannot delete protected core path: {rel_str}")
        
    if not safe_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
        
    try:
        if safe_path.is_dir():
            shutil.rmtree(safe_path)
        else:
            safe_path.unlink()
        return {"status": "ok", "path": req.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tasks")
async def get_tasks(session: Optional[str] = Query("default")):
    columns = {"backlog": [], "todo": [], "in_progress": [], "review": [], "done": []}
    task_file = _resolve_session_task_file(session)
    source_rel = str(task_file.relative_to(WORKSPACE_ROOT)).replace("\\", "/")

    if task_file.exists():
        lines = task_file.read_text(encoding="utf-8").splitlines()
        current_section = ""
        for idx, line in enumerate(lines):
            line_str = line.strip()
            if line_str.startswith("#"):
                current_section = line_str.lower()
                continue
            if line_str.startswith("- [x]"):
                title = line_str[5:].replace("#in-progress", "").replace("#in_progress", "").replace("#review", "").replace("#backlog", "").strip()
                columns["done"].append({"id": f"task_{idx}", "title": title, "source": source_rel, "status": "done", "line_idx": idx})
            elif line_str.startswith("- [ ]"):
                raw_title = line_str[5:].strip()
                if "#in-progress" in raw_title or "#in_progress" in raw_title or "en progreso" in current_section or "in progress" in current_section:
                    clean_title = raw_title.replace("#in-progress", "").replace("#in_progress", "").strip()
                    columns["in_progress"].append({"id": f"task_{idx}", "title": clean_title, "source": source_rel, "status": "in_progress", "line_idx": idx})
                elif "#review" in raw_title or "revisión" in current_section or "review" in current_section:
                    clean_title = raw_title.replace("#review", "").strip()
                    columns["review"].append({"id": f"task_{idx}", "title": clean_title, "source": source_rel, "status": "review", "line_idx": idx})
                elif "#backlog" in raw_title or "backlog" in current_section:
                    clean_title = raw_title.replace("#backlog", "").strip()
                    columns["backlog"].append({"id": f"task_{idx}", "title": clean_title, "source": source_rel, "status": "backlog", "line_idx": idx})
                else:
                    columns["todo"].append({"id": f"task_{idx}", "title": raw_title, "source": source_rel, "status": "todo", "line_idx": idx})

    # Also extract backlog proposals from plan.md if backlog has few items
    plan_file = _resolve_session_plan_file(session)
    if plan_file.exists() and len(columns["backlog"]) < 3:
        plan_rel = str(plan_file.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        p_lines = plan_file.read_text(encoding="utf-8").splitlines()
        for p_idx, p_line in enumerate(p_lines):
            p_str = p_line.strip()
            if p_str.startswith("### Fase ") or (p_str.startswith("- [ ]") and len(columns["backlog"]) < 6):
                clean_p = p_str.lstrip("#- [ ]").strip()
                if len(clean_p) > 5 and not any(t["title"] == clean_p for t in columns["backlog"]):
                    columns["backlog"].append({"id": f"plan_{p_idx}", "title": clean_p, "source": plan_rel, "status": "backlog", "line_idx": p_idx})

    return {
        "session": session,
        "source_file": source_rel,
        "columns": columns,
        "backlog": columns["backlog"],
        "todo": columns["todo"],
        "in_progress": columns["in_progress"],
        "review": columns["review"],
        "done": columns["done"]
    }


@app.post("/api/tasks/update")
async def update_task(req: UpdateTaskRequest):
    with _task_lock:
        task_file = _resolve_session_task_file(req.session)
        if not task_file.exists():
            task_file.write_text("# Tasks\n\n## To Do\n", encoding="utf-8")
            
        lines = task_file.read_text(encoding="utf-8").splitlines()
        updated = False
        
        # Parse task_id index if present
        target_idx = None
        if req.task_id.startswith("task_"):
            try:
                target_idx = int(req.task_id.split("_")[1])
            except Exception:
                target_idx = None

        new_status = req.status.lower()

        for idx, line in enumerate(lines):
            if target_idx is not None and idx == target_idx:
                raw = line.strip()
                title = raw[5:].replace("#in-progress", "").replace("#in_progress", "").replace("#review", "").replace("#backlog", "").strip()
                indent = line[:len(line) - len(line.lstrip())]
                
                if new_status == "done":
                    lines[idx] = f"{indent}- [x] {title}"
                elif new_status == "in_progress":
                    lines[idx] = f"{indent}- [ ] {title} #in-progress"
                elif new_status == "review":
                    lines[idx] = f"{indent}- [ ] {title} #review"
                elif new_status == "backlog":
                    lines[idx] = f"{indent}- [ ] {title} #backlog"
                else: # todo
                    lines[idx] = f"{indent}- [ ] {title}"
                updated = True
                break

        if not updated and target_idx is None:
            # Append as new line if not found
            if new_status == "done":
                lines.append(f"- [x] {req.task_id}")
            elif new_status == "in_progress":
                lines.append(f"- [ ] {req.task_id} #in-progress")
            elif new_status == "review":
                lines.append(f"- [ ] {req.task_id} #review")
            elif new_status == "backlog":
                lines.append(f"- [ ] {req.task_id} #backlog")
            else:
                lines.append(f"- [ ] {req.task_id}")
            updated = True

        task_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"status": "ok", "task_id": req.task_id, "new_status": req.status, "session": req.session}


@app.post("/api/tasks/create")
async def create_task(req: CreateTaskRequest):
    with _task_lock:
        task_file = _resolve_session_task_file(req.session)
        if not task_file.exists():
            task_file.parent.mkdir(parents=True, exist_ok=True)
            task_file.write_text("# Tasks\n\n", encoding="utf-8")
            
        content = task_file.read_text(encoding="utf-8")
        st = (req.status or "todo").lower()
        
        tag = ""
        if st == "in_progress":
            tag = " #in-progress"
        elif st == "review":
            tag = " #review"
        elif st == "backlog":
            tag = " #backlog"
            
        check = "[x]" if st == "done" else "[ ]"
        new_line = f"- {check} {req.title.strip()}{tag}\n"
        task_file.write_text(content.rstrip() + "\n" + new_line, encoding="utf-8")
        return {"status": "ok", "title": req.title, "status": st, "session": req.session}


@app.get("/api/chat/history")
async def get_chat_history(session: Optional[str] = Query("default")):
    try:
        sess = session_manager.switch(session or "default")
        return {
            "session": sess.name,
            "created_at": sess.created_at,
            "updated_at": sess.updated_at,
            "messages": sess.messages
        }
    except Exception as e:
        return {"session": session, "messages": [], "error": str(e)}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatPromptRequest):
    sess = session_manager.switch(req.session or "default")
    sess.add_message("user", req.prompt)

    async def sse_generator():
        # Step 1: Thinking and context exploration
        yield f"data: {json.dumps({'type': 'think', 'content': f'🔍 [Session: {sess.name}] Evaluando directiva y estado del workspace...\n'})}\n\n"
        await asyncio.sleep(0.08)

        # Check if orchestrator / local LLM is responsive
        cfg_file = WORKSPACE_ROOT / "config.yaml"
        cfg = {}
        if cfg_file.exists():
            try:
                cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
            except Exception:
                pass
        orch_cfg = cfg.get("llm", {}).get("orchestrator", {})

        llm_client = None
        is_llm_online = False
        try:
            llm_client = LLMClient.from_lane_config(orch_cfg)
            statuses = llm_client.get_provider_statuses()
            is_llm_online = any(s.get("available") for s in statuses)
        except Exception:
            is_llm_online = False

        full_token_acc = []
        full_think_acc = [f"🔍 [Session: {sess.name}] Evaluando directiva y estado del workspace...\n"]

        if is_llm_online and llm_client:
            yield f"data: {json.dumps({'type': 'think', 'content': '⚡ Conectado con motor LLM local. Generando inferencia streaming...\n'})}\n\n"
            full_think_acc.append("⚡ Conectado con motor LLM local. Generando inferencia streaming...\n")
            try:
                # Format messages for LLM
                msgs = [{"role": m["role"], "content": str(m.get("content", ""))} for m in sess.messages]
                # If stream method is available
                resp_text = llm_client.chat(msgs)
                # Parse think blocks if returned
                if "<think>" in resp_text and "</think>" in resp_text:
                    parts = resp_text.split("</think>")
                    think_part = parts[0].replace("<think>", "").strip()
                    main_part = parts[1].strip()
                    yield f"data: {json.dumps({'type': 'think', 'content': think_part + '\\n'})}\n\n"
                    full_think_acc.append(think_part)
                    tokens = [main_part[i:i+12] for i in range(0, len(main_part), 12)]
                    for tok in tokens:
                        yield f"data: {json.dumps({'type': 'token', 'content': tok})}\n\n"
                        full_token_acc.append(tok)
                        await asyncio.sleep(0.015)
                else:
                    tokens = [resp_text[i:i+12] for i in range(0, len(resp_text), 12)]
                    for tok in tokens:
                        yield f"data: {json.dumps({'type': 'token', 'content': tok})}\n\n"
                        full_token_acc.append(tok)
                        await asyncio.sleep(0.015)
            except Exception as e:
                yield f"data: {json.dumps({'type': 'think', 'content': f'⚠️ Aviso de fallback cognitivo: {str(e)}\\n'})}\n\n"
                is_llm_online = False
            finally:
                if llm_client:
                    llm_client.close()

        if not is_llm_online or not full_token_acc:
            # Tiny-Steward Cognitive Resident Engine
            yield f"data: {json.dumps({'type': 'think', 'content': '🧠 Activando Motor Cognitivo Residente de Tiny-Steward (Inspección viva de artefactos)...\n'})}\n\n"
            full_think_acc.append("🧠 Activando Motor Cognitivo Residente de Tiny-Steward (Inspección viva de artefactos)...\n")
            await asyncio.sleep(0.06)

            # Analyze workspace context
            task_f = _resolve_session_task_file(sess.name)
            open_tasks = 0
            if task_f.exists():
                open_tasks = sum(1 for line in task_f.read_text(encoding="utf-8").splitlines() if line.strip().startswith("- [ ]"))

            orders_dir = WORKSPACE_ROOT / "fabrica" / "orders"
            total_orders = len(list(orders_dir.glob("*.json"))) if orders_dir.exists() else 0

            response_markdown = (
                f"**🐱 Tiny-Steward [Sesión: `{sess.name}`]**\n\n"
                f"He procesado tu solicitud: *\"{req.prompt}\"*\n\n"
                f"### 📊 Estado y Contexto Operativo:\n"
                f"- **Sesión Activa:** `{sess.name}` (Historial persistido en disco)\n"
                f"- **Tareas Pendientes:** `{open_tasks}` registradas en `{task_f.name}`\n"
                f"- **Comandas 3D Fábrica:** `{total_orders}` pedidos bajo demanda en catálogo\n"
                f"- **Servicios del Host:** Web IDE (Port 8000: En línea)\n\n"
                f"Todos los módulos de la Factoría y el Control Center están plenamente interconectados. "
                f"Puedes gestionar tareas en el Kanban, inspeccionar nodos de memoria, despachar pedidos 3D o solicitar ejecución de scripts en cualquier momento."
            )

            chunk_size = 14
            for i in range(0, len(response_markdown), chunk_size):
                chunk = response_markdown[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                full_token_acc.append(chunk)
                await asyncio.sleep(0.012)

        # Save assistant message in session
        final_answer = "".join(full_token_acc)
        final_reasoning = "".join(full_think_acc)
        sess.add_message("assistant", final_answer, reasoning_content=final_reasoning)
        session_manager.save()

        yield "data: [DONE]\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/graph/inspect")
async def inspect_graph_node(id: str = Query(...)):
    """Devuelve metadatos, contenido y enlaces de un nodo del grafo de memoria/conocimiento."""
    node_data = {
        "id": id,
        "name": id.split("/")[-1] if "/" in id else id,
        "type": "document",
        "content": "",
        "outgoing_links": [],
        "incoming_links": [],
        "metadata": {}
    }

    clean_path = id.replace("article:", "").replace("skill:", "").replace("topic:", "").replace("persona:", "")
    target_file = (WORKSPACE_ROOT / clean_path).resolve()
    
    if str(target_file).startswith(str(WORKSPACE_ROOT)) and target_file.exists() and target_file.is_file():
        try:
            content = target_file.read_text(encoding="utf-8")
            node_data["content"] = content
            node_data["metadata"]["size_bytes"] = len(content)
            node_data["metadata"]["modified_at"] = target_file.stat().st_mtime
            
            # Extract wikilinks [[...]]
            import re
            links = re.findall(r'\[\[(.*?)\]\]', content)
            node_data["outgoing_links"] = list(set(links))
        except Exception as e:
            node_data["content"] = f"Error reading file: {e}"
    elif id.startswith("persona:"):
        p_file = WORKSPACE_ROOT / "agora" / "personas" / f"{clean_path}.json"
        if p_file.exists():
            node_data["type"] = "persona"
            node_data["content"] = p_file.read_text(encoding="utf-8")
            node_data["metadata"] = json.loads(node_data["content"])
    else:
        node_data["content"] = f"Nodo `{id}` indexado en el grafo de conocimiento de Tiny-Steward."

    return node_data


@app.post("/api/graph/rebuild")
async def rebuild_graph():
    """Reconstruye el archivo assembled-graph.json a partir de todos los artefactos."""
    nodes = []
    links = []
    seen_ids = set()

    # 1. Memory files
    mem_dir = WORKSPACE_ROOT / "memory"
    if mem_dir.exists():
        for p in mem_dir.glob("*.md"):
            nid = f"article:memory/{p.name}"
            if nid not in seen_ids:
                seen_ids.add(nid)
                nodes.append({"id": nid, "name": p.stem, "val": 15, "group": "memory"})

    # 2. Agora topics
    topics_dir = WORKSPACE_ROOT / "agora" / "topics"
    if topics_dir.exists():
        for t in topics_dir.glob("*.json"):
            nid = f"topic:{t.stem}"
            if nid not in seen_ids:
                seen_ids.add(nid)
                nodes.append({"id": nid, "name": f"#{t.stem}", "val": 20, "group": "agora"})
                # Link to root
                links.append({"source": nid, "target": "topic:general" if "general" in seen_ids else nid})

    # 3. Personas
    personas_dir = WORKSPACE_ROOT / "agora" / "personas"
    if personas_dir.exists():
        for p in personas_dir.glob("*.json"):
            nid = f"persona:{p.stem}"
            if nid not in seen_ids:
                seen_ids.add(nid)
                nodes.append({"id": nid, "name": f"@{p.stem}", "val": 25, "group": "persona"})

    # 4. Products
    products_dir = WORKSPACE_ROOT / "fabrica" / "products"
    if products_dir.exists():
        for p in products_dir.glob("0*"):
            nid = f"product:{p.name}"
            if nid not in seen_ids:
                seen_ids.add(nid)
                nodes.append({"id": nid, "name": p.name, "val": 18, "group": "fabrica"})

    graph_data = {"nodes": nodes, "links": links}
    graph_out = WORKSPACE_ROOT / "assembled-graph.json"
    graph_out.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "total_nodes": len(nodes), "total_links": len(links)}


class MailboxSendRequest(BaseModel):
    from_session: str
    to_session: str
    content: str
    priority: Optional[str] = "normal"
    type: Optional[str] = "message"
    blocking: Optional[bool] = False


@app.post("/api/v1/mailbox/send")
async def send_mailbox_message(req: MailboxSendRequest):
    """Envía un mensaje a la cola mailbox de una sesión."""
    inbox_dir = SESSIONS_DIR / ".mailbox" / req.to_session / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    msg_id = f"msg_{int(time.time()*1000)}"
    msg_path = inbox_dir / f"{msg_id}.json"
    msg_data = {
        "id": msg_id,
        "from": req.from_session,
        "to": req.to_session,
        "content": req.content,
        "priority": req.priority,
        "type": req.type,
        "blocking": req.blocking,
        "ts": time.time()
    }
    msg_path.write_text(json.dumps(msg_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "message_id": msg_id}


@app.get("/api/factory/orders/list")
async def list_factory_orders():
    """Lista todas las comandas de compra registradas con estadísticas calculadas."""
    orders_dir = WORKSPACE_ROOT / "fabrica" / "orders"
    orders = []
    stats = {
        "total": 0,
        "pending": 0,
        "in_print": 0,
        "printed": 0,
        "shipped": 0,
        "delivered": 0,
        "cancelled": 0,
        "total_revenue_eur": 0.0
    }

    if orders_dir.exists():
        for p in sorted(orders_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                st = data.get("status", "pending")
                stats["total"] += 1
                if st in stats:
                    stats[st] += 1
                price = float(data.get("product", {}).get("total", data.get("product", {}).get("price", 0)))
                stats["total_revenue_eur"] = round(stats["total_revenue_eur"] + price, 2)
                orders.append(data)
            except Exception:
                continue

    return {"stats": stats, "orders": orders}


@app.patch("/api/factory/orders/{order_id}/status")
async def update_factory_order_status(order_id: str, req: UpdateOrderStatusRequest):
    """Actualiza el estado de fabricación, tracking de envío y notas de un pedido."""
    orders_dir = WORKSPACE_ROOT / "fabrica" / "orders"
    order_path = orders_dir / f"{order_id}.json"
    if not order_path.exists():
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        data = json.loads(order_path.read_text(encoding="utf-8"))
        old_status = data.get("status", "pending")
        data["status"] = req.status
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if req.carrier:
            data["carrier"] = req.carrier
        if req.tracking_code:
            data["tracking_code"] = req.tracking_code
        if req.operator_notes:
            data["operator_notes"] = req.operator_notes

        order_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Notify in Agora
        item_title = data.get("product", {}).get("title", "Pieza 3D")
        customer_name = data.get("customer", {}).get("name", "Cliente")
        agora_forum.post_message(
            "autofinanciacion_y_hardware",
            {"id": "signal_raven", "name": "Signal-Raven", "emoji": "🦅📦"},
            f"🔄 **Actualización de Pedido [{order_id}]**\n\n"
            f"- **Artículo:** {item_title}\n"
            f"- **Cliente:** {customer_name}\n"
            f"- **Estado:** `{old_status}` ➔ **`{req.status.upper()}`**\n"
            f"- **Transportista / Tracking:** {req.carrier or 'N/A'} `{req.tracking_code or ''}`\n"
            f"- **Notas Operador:** {req.operator_notes or 'Sin observaciones adicionales.'}"
        )

        return {"status": "ok", "order_id": order_id, "new_status": req.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# ─── 🏛️ Ágora (Social Hub & Multi-Agent Forum) Endpoints ────────

agora_forum = AgoraForum(WORKSPACE_ROOT / "agora")


class CreateThreadRequest(BaseModel):
    slug: str
    title: Optional[str] = None
    initial_message: Optional[str] = None
    author_id: Optional[str] = "tiny_steward"


class PostAgoraMessageRequest(BaseModel):
    author_id: str
    content: str
    in_reply_to: Optional[str] = None
    proposal: Optional[Dict[str, Any]] = None


class ProposePersonaRequest(BaseModel):
    proposer_id: str
    persona: Dict[str, Any]
    justification: str = ""


class ApprovePersonaRequest(BaseModel):
    persona: Dict[str, Any]
    approver_id: str = "tiny_steward"


class EvaluateWorkerRequest(BaseModel):
    worker_id: str
    evaluator_id: Optional[str] = "tiny_steward"
    score: Optional[int] = 90
    rating: Optional[str] = "A"
    feedback: Optional[str] = ""
    current_focus: Optional[str] = ""


class ProposeMissionRequest(BaseModel):
    thread_slug: str
    proposer_id: str
    mission: Dict[str, Any]


class SteerMissionRequest(BaseModel):
    thread_slug: str
    mission_id: str
    steerer_id: Optional[str] = "tiny_steward"
    feedback: str
    required_changes: Optional[List[str]] = None


class ApproveMissionRequest(BaseModel):
    thread_slug: str
    mission_id: str
    approver_id: Optional[str] = "tiny_steward"
    comments: Optional[str] = ""


class AwakenAgoraRequest(BaseModel):
    persona_id: Optional[str] = None
    custom_instructions: Optional[str] = ""


@app.get("/api/agora/threads")
async def get_agora_threads():
    """List all discussion threads in the Agora."""
    threads = agora_forum.list_threads()
    return {"threads": [asdict(t) for t in threads]}


@app.get("/api/agora/threads/{slug}")
async def get_agora_thread(slug: str, limit: int = Query(50)):
    """Retrieve messages for a specific thread."""
    messages = agora_forum.get_messages(slug, limit=limit)
    return {"slug": slug, "messages": [asdict(m) for m in messages]}


@app.post("/api/agora/threads")
async def create_agora_thread(req: CreateThreadRequest):
    """Create a new topic / thread in the Agora."""
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in req.slug.lower().strip())
    if not slug:
        raise HTTPException(status_code=400, detail="Invalid thread slug")

    # If initial message provided, post it
    if req.initial_message:
        author = agora_forum.get_persona(req.author_id or "tiny_steward")
        author_info = author or {"id": req.author_id, "name": (req.author_id or "Agent").title(), "emoji": "💬"}
        agora_forum.post_message(slug, author_info, req.initial_message)
    else:
        # Create empty thread file if not exists
        tfile = agora_forum.get_thread_file(slug)
        if not tfile.exists():
            tfile.touch()
            agora_forum.render_markdown(slug)

    return {"status": "ok", "slug": slug}


@app.post("/api/agora/threads/{slug}/messages")
async def post_agora_message(slug: str, req: PostAgoraMessageRequest):
    """Post a message (from human or agent) to an Agora thread."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    author = agora_forum.get_persona(req.author_id)
    if author:
        author_info = author
    elif req.author_id in ("human", "user", "admin"):
        author_info = {"id": "human", "name": "Operador Humano", "emoji": "👤"}
    else:
        author_info = {"id": req.author_id, "name": req.author_id.title(), "emoji": "💬"}

    msg = agora_forum.post_message(
        thread_slug=slug,
        author=author_info,
        content=req.content,
        in_reply_to=req.in_reply_to,
        proposal=req.proposal,
    )
    return {"status": "ok", "message": asdict(msg)}


@app.get("/api/agora/personas")
async def get_agora_personas():
    """List all registered personas in the Agora with assigned skill domains."""
    personas = agora_forum.list_personas()
    return {"personas": [asdict(p) for p in personas]}


@app.get("/api/agora/personas/{persona_id}")
async def get_agora_persona(persona_id: str):
    """Retrieve a single persona by ID."""
    persona = agora_forum.get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
    return {"persona": asdict(persona)}


class ReflectMementoRequest(BaseModel):
    context: Optional[str] = ""
    trigger: Optional[str] = "manual_operator_request"


class AddTattooRequest(BaseModel):
    tattoo: str


@app.get("/api/agora/personas/{persona_id}/memento")
async def get_persona_memento(persona_id: str):
    """Retrieve an agent's Memento epistemic slate (tattoos, opinions, polaroids)."""
    from core.memento import memento_manager
    memento = memento_manager.load_memento(persona_id)
    return {
        "memento": memento.to_dict(),
        "awakening_preview": memento.to_awakening_block(),
    }


@app.post("/api/agora/personas/{persona_id}/memento/reflect")
async def reflect_persona_memento(persona_id: str, req: ReflectMementoRequest):
    """Trigger an introspective Memento reflection cycle for an agent."""
    from core.memento import memento_manager
    llm = getattr(agora_dispatcher, "llm_client", None) if agora_dispatcher else None
    memento = memento_manager.reflect(
        persona_id=persona_id,
        context_text=req.context or f"Reflexión solicitada por @human para @{persona_id}",
        trigger=req.trigger or "manual_operator_request",
        llm_client=llm,
    )
    return {"status": "ok", "memento": memento.to_dict()}


@app.post("/api/agora/personas/{persona_id}/memento/tattoos")
async def add_persona_tattoo(persona_id: str, req: AddTattooRequest):
    """Permanently ink a new invariant tattoo into an agent's Memento slate."""
    from core.memento import memento_manager
    memento = memento_manager.load_memento(persona_id)
    memento.add_tattoo(req.tattoo)
    memento_manager.save_memento(memento)
    return {"status": "ok", "memento": memento.to_dict()}


@app.delete("/api/agora/personas/{persona_id}/memento/tattoos/{index}")
async def delete_persona_tattoo(persona_id: str, index: int):
    """Remove a tattoo from an agent's Memento slate."""
    from core.memento import memento_manager
    memento = memento_manager.load_memento(persona_id)
    success = memento.remove_tattoo(index)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid tattoo index")
    memento_manager.save_memento(memento)
    return {"status": "ok", "memento": memento.to_dict()}


class AddGoalRequest(BaseModel):
    goal: str


@app.get("/api/agora/personas/{persona_id}/workbench")
async def get_persona_workbench(persona_id: str):
    """Retrieve an agent's individual autonomous workbench status, personal goals, and task history."""
    from core.memento import memento_manager
    memento = memento_manager.load_memento(persona_id)
    return {
        "persona_id": persona_id,
        "personal_goals": memento.personal_goals,
        "workbench_task": memento.workbench_task,
        "workbench_history": memento.workbench_history,
        "last_reflection_iso": memento.last_reflection_iso,
    }


@app.post("/api/agora/personas/{persona_id}/workbench/step")
async def execute_persona_workbench_step(persona_id: str):
    """Trigger an autonomous technical step in the agent's individual domain workbench."""
    from core.workbench import agent_workbench
    result = agent_workbench.execute_autonomous_step(persona_id)
    return {
        "status": "ok",
        "result": result.to_dict(),
    }


@app.post("/api/agora/personas/{persona_id}/goals")
async def add_persona_goal(persona_id: str, req: AddGoalRequest):
    """Add a new personal goal/objective to an agent's Memento."""
    from core.memento import memento_manager
    memento = memento_manager.load_memento(persona_id)
    memento.add_personal_goal(req.goal)
    memento_manager.save_memento(memento)
    return {"status": "ok", "personal_goals": memento.personal_goals}


@app.delete("/api/agora/personas/{persona_id}/goals/{index}")
async def delete_persona_goal(persona_id: str, index: int):
    """Remove a personal goal from an agent's Memento."""
    from core.memento import memento_manager
    memento = memento_manager.load_memento(persona_id)
    success = memento.remove_personal_goal(index)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid goal index")
    memento_manager.save_memento(memento)
    return {"status": "ok", "personal_goals": memento.personal_goals}




@app.post("/api/agora/personas/propose")
async def propose_agora_persona(req: ProposePersonaRequest):
    """Propose the recruitment of a new persona."""
    proposal = agora_forum.propose_persona(
        proposer_id=req.proposer_id,
        persona_data=req.persona,
        justification=req.justification,
    )
    return {"status": "ok", "proposal": proposal}


@app.post("/api/agora/personas/approve")
async def approve_agora_persona(req: ApprovePersonaRequest):
    """Master approves and provisions a new persona."""
    persona = agora_forum.approve_persona(
        persona_data=req.persona,
        approver_id=req.approver_id,
    )
    return {"status": "ok", "persona": asdict(persona)}


@app.get("/api/agora/workers/evaluations")
async def get_agora_worker_evaluations():
    """Retrieve scorecard of worker evaluations, KPIs, and Master steering notes."""
    evals = agora_forum.get_worker_evaluations()
    return {"evaluations": evals}


@app.post("/api/agora/workers/evaluate")
async def evaluate_agora_worker(req: EvaluateWorkerRequest):
    """Master or supervisor evaluates a worker's performance and sets current focus."""
    record = agora_forum.evaluate_worker(
        worker_id=req.worker_id,
        evaluator_id=req.evaluator_id or "tiny_steward",
        score=req.score or 90,
        rating=req.rating or "A",
        feedback=req.feedback or "",
        current_focus=req.current_focus or "",
    )
    return {"status": "ok", "evaluation": record}


@app.post("/api/agora/missions/propose")
async def propose_agora_mission(req: ProposeMissionRequest):
    """Worker proposes a commercial mission or task initiative."""
    proposal = agora_forum.propose_mission(
        thread_slug=req.thread_slug,
        proposer_id=req.proposer_id,
        mission_data=req.mission,
    )
    return {"status": "ok", "proposal": proposal}


@app.post("/api/agora/missions/steer")
async def steer_agora_mission(req: SteerMissionRequest):
    """Master steers an initiative and requests specific course corrections."""
    steering = agora_forum.steer_mission(
        thread_slug=req.thread_slug,
        mission_id=req.mission_id,
        steerer_id=req.steerer_id or "tiny_steward",
        feedback=req.feedback,
        required_changes=req.required_changes,
    )
    return {"status": "ok", "steering": steering}


@app.post("/api/agora/missions/approve")
async def approve_agora_mission(req: ApproveMissionRequest):
    """Master formally approves a mission and issues the work order."""
    approval = agora_forum.approve_mission(
        thread_slug=req.thread_slug,
        mission_id=req.mission_id,
        approver_id=req.approver_id or "tiny_steward",
        comments=req.comments or "",
    )
    return {"status": "ok", "approval": approval}


# ─── 🚀 Ágora Background Dispatcher (24/7 Auto-Socialize & Scouting) ───

def _get_agora_llm_client():
    cfg_file = WORKSPACE_ROOT / "config.yaml"
    if cfg_file.exists():
        try:
            cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
            lane_cfg = cfg.get("llm", {}).get("atomic") or cfg.get("llm", {}).get("orchestrator")
            if lane_cfg:
                return LLMClient.from_lane_config(lane_cfg)
        except Exception:
            pass
    return None

agora_awakener = AgoraAwakener(agora_forum, llm_client=_get_agora_llm_client())
agora_dispatcher = AgoraDispatcher(
    forum=agora_forum,
    awakener=agora_awakener,
    interval_s=20.0,
    active_threads=[
        "autofinanciacion_y_hardware",
        "scouting_de_oportunidades",
        "autoorganizacion_y_roles",
    ],
)


@app.post("/api/agora/threads/{slug}/awaken")
async def awaken_persona_in_thread(slug: str, req: AwakenAgoraRequest):
    """Awaken a persona (or next in rotation) to reflect and contribute to a thread."""
    if req.persona_id:
        persona = agora_forum.get_persona(req.persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona '{req.persona_id}' not found")
    else:
        personas = agora_forum.list_personas()
        if not personas:
            raise HTTPException(status_code=400, detail="No personas available to awaken")
        persona = personas[0]

    msg = agora_awakener.awaken_persona(
        persona=persona,
        thread_slug=slug,
        custom_instructions=req.custom_instructions or "",
    )
    return {"status": "ok", "awakened_persona": persona.id, "message": asdict(msg)}


@app.get("/api/agora/events")
async def get_agora_events(request: Request):
    """Server-Sent Events (SSE) stream for real-time Agora updates."""
    queue: asyncio.Queue = asyncio.Queue()

    def listener(event_data: dict[str, Any]):
        try:
            queue.put_nowait(event_data)
        except Exception:
            pass

    agora_forum.add_listener(listener)

    async def event_generator():
        try:
            # Send connection greeting
            yield f"data: {json.dumps({'type': 'connected', 'ts': time.time()})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive ping to prevent proxy/browser timeout
                    yield ": keepalive\n\n"
        finally:
            if listener in agora_forum._listeners:
                agora_forum._listeners.remove(listener)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class StartDispatcherRequest(BaseModel):
    interval_s: Optional[float] = 20.0
    threads: Optional[List[str]] = None


@app.get("/api/agora/dispatcher/status")
async def get_agora_dispatcher_status():
    """Retrieve current background dispatcher status."""
    return agora_dispatcher.get_status()


@app.post("/api/agora/dispatcher/start")
async def start_agora_dispatcher(req: StartDispatcherRequest):
    """Start 24/7 background time-slicing debate & scouting dispatcher."""
    if req.threads:
        agora_dispatcher.active_threads = req.threads
    success = agora_dispatcher.start(interval_s=req.interval_s)
    return {"status": "ok" if success else "already_running", "dispatcher": agora_dispatcher.get_status()}


@app.post("/api/agora/dispatcher/stop")
async def stop_agora_dispatcher():
    """Stop 24/7 background dispatcher."""
    success = agora_dispatcher.stop()
    return {"status": "ok" if success else "already_stopped", "dispatcher": agora_dispatcher.get_status()}


# -----------------------------------------------------------------------------
# Micro-Landing & Factory Commercial Endpoints
# -----------------------------------------------------------------------------
@app.get("/landing")
async def get_landing_page():
    """Sirve la Micro-Landing comercial de la factoría."""
    landing_index = WORKSPACE_ROOT / "fabrica" / "web" / "landing" / "index.html"
    if landing_index.exists():
        return FileResponse(str(landing_index))
    raise HTTPException(status_code=404, detail="Landing page not found")


@app.get("/api/factory/products")
async def get_factory_products():
    """Devuelve el catálogo de productos con verificación empírica de mallas 3D."""
    products_dir = WORKSPACE_ROOT / "fabrica" / "products"
    cert_file = products_dir / "verification_certificate.json"
    cert_data = json.loads(cert_file.read_text(encoding="utf-8")) if cert_file.exists() else {}

    products = []
    for sub in sorted(products_dir.glob("0*")):
        meta_file = sub / "metadata.json"
        if meta_file.exists():
            try:
                products.append(json.loads(meta_file.read_text(encoding="utf-8")))
            except Exception:
                pass
    return {"products": products, "verification_certificate": cert_data}


class FactoryOrderRequest(BaseModel):
    order_id: str
    product: Dict[str, Any]
    customer: Dict[str, Any]
    created_at: str
    status: str
    payment_wallets: Dict[str, str]


@app.post("/api/factory/orders")
async def place_factory_order(order: FactoryOrderRequest):
    """Registra una orden de compra bajo demanda para que @human la imprima y envíe."""
    orders_dir = WORKSPACE_ROOT / "fabrica" / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    order_path = orders_dir / f"{order.order_id}.json"
    order_dict = order.dict()
    order_path.write_text(json.dumps(order_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    # Notificar en el Ágora
    title = order.product.get("title", "Pieza 3D")
    price = order.product.get("total", order.product.get("price", 0))
    buyer = order.customer.get("name", "Cliente")
    agora_forum.post_message(
        "autofinanciacion_y_hardware",
        {"id": "signal_raven", "name": "Signal-Raven", "emoji": "🦅🌐"},
        f"🛍️ **¡Nueva Venta en la Micro-Landing!**\n\n"
        f"- **Pedido:** `{order.order_id}`\n"
        f"- **Artículo:** **{title}** (€{price})\n"
        f"- **Destinatario:** {buyer} ({order.customer.get('city', 'España')})\n"
        f"- **Estado:** Preparando archivo STL para impresión 3D.\n\n"
        f"Comanda registrada en `fabrica/orders/{order.order_id}.json`. Delegado aviso al Operador Humano (@human) para la impresión física y envío postal."
    )
    return {"status": "ok", "order_id": order.order_id}



