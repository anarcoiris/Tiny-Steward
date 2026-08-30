import yaml
from pathlib import Path
from core.runtime import Runtime
from core.llm import LLMClient
from core.embedder import Embedder
from core.skill_loader import SkillIndex
from core.help import HelpEngine
from core.session import SessionManager

with open("config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

llm = LLMClient.from_lane_config(cfg["llm"]["orchestrator"])
embed_cfg = cfg.get("embeddings", {})
embedder = Embedder(base_url=embed_cfg.get("base_url", "http://127.0.0.1:11438"), model=embed_cfg.get("model", "nomic-embed-text"))

skills_cfg = cfg["skills"]
skills_root = Path(skills_cfg["root"])
index_path = Path(skills_cfg["index"])
skill_index = SkillIndex.load(index_path, skills_root) if index_path.exists() else SkillIndex([], None, skills_root)

help_cfg = cfg.get("help", {})
help_engine = HelpEngine(index=skill_index, embedder=embedder)

mgr = SessionManager("sessions")
session = mgr.switch("test_user_prompt_ejercicios")
runtime = Runtime(llm=llm, help_engine=help_engine, session=session, session_manager=mgr, use_streaming=False)

prompt = (
    "Haz una prueba, proponiendo 10 ejercicios de scripts de python con objetivos a lograr, "
    "créalos en una carpeta ejercicios/ y ejecútalos después de generarlos para auto-evaluarte "
    "y tratar de auto-corregirte mediante prueba y error. Continuaremos hasta completar estas 10 tareas "
    "(las cuales anotaras en \"ejercicios/task.md\")"
)

print("PROMPT RUNNING...")
resp = runtime.run_task(prompt)
print("TASK OUTPUT:")
print(resp)
