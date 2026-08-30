import time
import os
import sys
from pathlib import Path
import yaml

# Ensure project root is in sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.runtime import Runtime
from core.llm import LLMClient
from core.embedder import Embedder
from core.skill_loader import SkillIndex
from core.help import HelpEngine
from core.session import SessionManager

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

os.makedirs("scratch", exist_ok=True)

llm = LLMClient.from_lane_config(cfg["llm"]["orchestrator"])
embed_cfg = cfg.get("embeddings", {})
embedder = Embedder(base_url=embed_cfg.get("base_url", "http://127.0.0.1:11438"), model=embed_cfg.get("model", "nomic-embed-text"))

skills_cfg = cfg["skills"]
skills_root = Path(skills_cfg["root"])
index_path = Path(skills_cfg["index"])
if index_path.exists():
    skill_index = SkillIndex.load(index_path, skills_root)
else:
    skill_index = SkillIndex(skills=[], vectors=None, root=skills_root)

help_cfg = cfg.get("help", {})
help_engine = HelpEngine(
    index=skill_index,
    embedder=embedder,
    top_k=help_cfg.get("top_k", 5),
    min_similarity=help_cfg.get("min_similarity", 0.35),
    max_inject_tokens=help_cfg.get("max_inject_tokens", 4000),
)

mgr = SessionManager("sessions")
session = mgr.switch("bench_qwen38_test_run")
runtime = Runtime(
    llm=llm,
    help_engine=help_engine,
    session=session,
    session_manager=mgr,
    use_streaming=False
)

prompts = [
    "Usa la acción read para leer el archivo docs/last_review.md",
    "Usa la acción write para crear el archivo scratch/resumen.txt con las dos conclusiones principales.",
    "Usa la acción read para comprobar scratch/resumen.txt y confirmar que está escrito."
]

for i, p in enumerate(prompts):
    print(f"\n=======================================================")
    print(f"🔄 LOOP {i+1}/3: PROMPT -> '{p}'")
    print(f"=======================================================")
    t0 = time.perf_counter()
    resp = runtime.run_task(p)
    dt = time.perf_counter() - t0
    
    print(f"\n[Turn {i+1} Output in {dt:.2f}s]:")
    print(resp)
    
    # Calculate token usage and prompt composition
    total_chars = sum(len(str(m.get("content", ""))) for m in session.messages)
    est_tokens = total_chars // 4
    
    print(f"\n📊 Turn {i+1} Metrics:")
    print(f"  - Session messages count: {len(session.messages)}")
    print(f"  - Context footprint: {total_chars} chars (~{est_tokens} tokens)")
    print(f"  - Latency: {dt:.2f}s")
