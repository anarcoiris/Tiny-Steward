"""Chronos MCP Server - God-Agent for GPU monitoring, task scheduling, and background repository hygiene.

Runs in the background to dispatch maintenance tasks when the GPU and Steward REPL are idle.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
import yaml
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Chronos",
    instructions="God-Agent for GPU monitoring, task scheduling, and background repository hygiene."
)


def get_repo_paths():
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "config.yaml"
    sessions_dir = repo_root / "sessions"
    
    llamacpp_state = None
    try:
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                cwd = cfg.get("llm", {}).get("orchestrator", {}).get("launch", {}).get("cwd")
                if cwd:
                    llamacpp_state = Path(cwd) / "qwythos.state.json"
    except Exception:
        pass
        
    if not llamacpp_state:
        llamacpp_state = Path(r"C:\Users\soyko\Documents\Ollama\docker\llamacpp\qwythos.state.json")
        
    return repo_root, sessions_dir, llamacpp_state


def check_gpu_idle() -> bool:
    """Query nvidia-smi to ensure no active GPU is running high compute load."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5.0
        )
        if res.returncode == 0:
            utils = [int(line.strip()) for line in res.stdout.splitlines() if line.strip().isdigit()]
            if utils:
                # If any GPU load is > 50%, count as busy
                if any(u > 50 for u in utils):
                    return False
                return True
    except Exception:
        pass
    return True


def chronos_worker():
    """Background polling loop that runs 24/7."""
    repo_root, sessions_dir, state_path = get_repo_paths()
    queue_path = sessions_dir / "chronos_queue.json"
    current_path = sessions_dir / "current.json"
    
    while True:
        try:
            if current_path.exists():
                with open(current_path, "r", encoding="utf-8") as f:
                    curr = json.load(f)
                
                if curr.get("status") == "idle":
                    session_name = curr.get("session")
                    
                    if check_gpu_idle():
                        jobs = []
                        if queue_path.exists():
                            with open(queue_path, "r", encoding="utf-8") as f:
                                jobs = json.load(f)
                                
                        if jobs:
                            job = jobs[0]
                            task_content = job.get("task")
                            priority = job.get("priority", "normal")
                            
                            inbox_dir = sessions_dir / ".mailbox" / session_name / "inbox"
                            inbox_dir.mkdir(parents=True, exist_ok=True)
                            
                            msg_id = str(uuid.uuid4())
                            payload = {
                                "id": msg_id,
                                "from": "chronos",
                                "to": session_name,
                                "priority": priority,
                                "type": "heartbeat_job",
                                "content": task_content,
                                "blocking": False,
                                "ts": time.time()
                            }
                            
                            tmp_name = f".{int(time.time()*1000)}-{msg_id}.json.tmp"
                            final_name = tmp_name[1:-4]
                            
                            tmp_file = inbox_dir / tmp_name
                            final_file = inbox_dir / final_name
                            
                            with open(tmp_file, "w", encoding="utf-8") as out_f:
                                json.dump(payload, out_f, indent=2)
                            tmp_file.replace(final_file)
                            
                            jobs = jobs[1:]
                            with open(queue_path, "w", encoding="utf-8") as out_f:
                                json.dump(jobs, out_f, indent=2)
                                
        except Exception:
            pass
            
        time.sleep(5.0)


@mcp.tool()
def get_gpu_telemetry() -> str:
    """Retrieve detailed GPU telemetry and load sizing."""
    repo_root, sessions_dir, state_path = get_repo_paths()
    info = []
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5.0
        )
        if res.returncode == 0:
            info.append("=== NVIDIA-SMI Telemetry ===")
            info.append(res.stdout.strip())
    except Exception as e:
        info.append(f"Failed to query nvidia-smi: {e}")
        
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            info.append("\n=== Qwythos Stack State ===")
            info.append(json.dumps(state, indent=2))
        except Exception as e:
            info.append(f"Failed to read state.json: {e}")
            
    return "\n".join(info)


@mcp.tool()
def get_steward_status() -> str:
    """Check the active Steward session and its execution status (idle, busy, offline)."""
    repo_root, sessions_dir, state_path = get_repo_paths()
    current_path = sessions_dir / "current.json"
    if current_path.exists():
        try:
            with open(current_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            return f"Session: {state.get('session')}\nStatus: {state.get('status')}\nLast updated: {time.ctime(state.get('ts'))}"
        except Exception as e:
            return f"Error reading current.json: {e}"
    return "Steward is offline (no active session state found)."


@mcp.tool()
def queue_background_job(task: str, priority: str = "normal") -> str:
    """Queue a new background task to be executed automatically when the GPU is idle."""
    repo_root, sessions_dir, state_path = get_repo_paths()
    queue_path = sessions_dir / "chronos_queue.json"
    
    jobs = []
    if queue_path.exists():
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                jobs = json.load(f)
        except Exception:
            pass
            
    jobs.append({
        "id": str(uuid.uuid4()),
        "task": task,
        "priority": priority,
        "queued_at": time.time()
    })
    
    try:
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
        return f"Successfully queued job: '{task}'"
    except Exception as e:
        return f"Failed to save job to queue: {e}"


@mcp.tool()
def list_queued_jobs() -> str:
    """List all pending background jobs in the Chronos queue."""
    repo_root, sessions_dir, state_path = get_repo_paths()
    queue_path = sessions_dir / "chronos_queue.json"
    if queue_path.exists():
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                jobs = json.load(f)
            if not jobs:
                return "Chronos queue is empty."
            res = []
            for i, job in enumerate(jobs):
                res.append(f"[{i+1}] {job.get('task')} (Priority: {job.get('priority')}, Queued: {time.ctime(job.get('queued_at'))})")
            return "\n".join(res)
        except Exception as e:
            return f"Error reading queue: {e}"
    return "Chronos queue is empty (no queue file found)."


def main():
    t = threading.Thread(target=chronos_worker, daemon=True)
    t.start()
    mcp.run()


if __name__ == "__main__":
    main()
