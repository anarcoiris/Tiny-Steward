"""Tiny Steward — Semantic Capability Graph micro-agent runtime.

Entry point. Provides:
  - Interactive REPL (default)
  - Single task execution (--task "...")
  - Index building (--build-index)
  - Session management (--session <name>)

Usage:
  python steward.py                          # interactive REPL, default session
  python steward.py --session deploy-flask   # resume named session
  python steward.py --task "list all .py files in ~/projects"
  python steward.py --build-index            # rebuild skill embeddings
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows to support emojis in console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


import yaml

from core.llm import LLMClient
from core.embedder import Embedder
from core.skill_loader import build_index, SkillIndex
from core.help import HelpEngine
from core.session import SessionManager
from core.runtime import Runtime


def load_config(path: str = "config.yaml") -> dict:
    """Load configuration from YAML."""
    config_path = Path(path)
    if not config_path.exists():
        print(f"  [error] Config not found: {config_path.resolve()}")
        sys.exit(1)
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_health(llm: LLMClient, embedder: Embedder) -> bool:
    """Verify endpoints are reachable."""
    ok = True
    if not llm.health():
        print(f"  [warn] Orchestrator LLM not reachable at {llm.base_url}")
        ok = False
    else:
        print(f"  [ok] Orchestrator LLM: {llm.base_url}")

    if not embedder.health():
        print(f"  [warn] Embedder not reachable at {embedder.base_url}")
        ok = False
    else:
        print(f"  [ok] Embedder: {embedder.base_url}")

    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Tiny Steward — Semantic Capability Graph",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--session", default="default", help="Session name")
    parser.add_argument("--task", help="Run a single task and exit")
    parser.add_argument("--build-index", action="store_true", help="Rebuild skill index")
    parser.add_argument("--list-skills", action="store_true", help="List all indexed skills")
    parser.add_argument("--no-health-check", action="store_true", help="Skip endpoint health checks")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Initialize clients
    orch_cfg = config["llm"]["orchestrator"]
    llm = LLMClient(
        base_url=orch_cfg["base_url"],
        model=orch_cfg["model"],
        max_tokens=orch_cfg.get("max_tokens", 4096),
        temperature=orch_cfg.get("temperature", 0.15),
        top_p=orch_cfg.get("top_p", 0.9),
        repeat_penalty=orch_cfg.get("repeat_penalty", 1.05),
    )

    emb_cfg = config["embeddings"]
    embedder = Embedder(
        base_url=emb_cfg["base_url"],
        model=emb_cfg["model"],
    )

    # Health check
    if not args.no_health_check:
        print()
        if not check_health(llm, embedder):
            print("\n  [warn] Some endpoints are not reachable. Continuing anyway...\n")

    # Skills
    skills_cfg = config["skills"]
    skills_root = Path(skills_cfg["root"])
    index_path = Path(skills_cfg["index"])

    # Build index if requested or if it doesn't exist
    if args.build_index or not index_path.exists() or skills_cfg.get("rebuild_on_start"):
        print("\n  Building skill index...")
        skill_index = build_index(skills_root, embedder)
        skill_index.save(index_path)
        print(f"  Saved index: {index_path.resolve()}\n")

        if args.build_index:
            # Just build and exit
            for s in skill_index.skills:
                t = "🗂️" if s.skill_type == "hub" else "📖"
                print(f"  {t} {s.slug:30s} [{', '.join(s.tags)}]")
            print(f"\n  Total: {skill_index.size} skills")
            return
    else:
        print(f"\n  Loading skill index from {index_path} ...")
        skill_index = SkillIndex.load(index_path, skills_root)
        print(f"  Loaded {skill_index.size} skills")

    # List skills
    if args.list_skills:
        for s in skill_index.skills:
            t = "🗂️" if s.skill_type == "hub" else "📖"
            print(f"  {t} {s.slug:30s} [{', '.join(s.tags)}]  {s.description[:50]}")
        print(f"\n  Total: {skill_index.size} skills")
        return

    # Help engine
    help_cfg = config.get("help", {})
    help_engine = HelpEngine(
        index=skill_index,
        embedder=embedder,
        top_k=help_cfg.get("top_k", 5),
        min_similarity=help_cfg.get("min_similarity", 0.35),
        max_inject_tokens=help_cfg.get("max_inject_tokens", 4000),
    )

    # Session
    session_cfg = config.get("sessions", {})
    session_mgr = SessionManager(session_cfg.get("dir", "./sessions"))
    session = session_mgr.switch(args.session)

    # Runtime
    runtime = Runtime(
        llm=llm,
        help_engine=help_engine,
        session=session,
    )
    # Attach session manager for /sessions command
    runtime.session_manager = session_mgr

    # Execute
    if args.task:
        result = runtime.run_task(args.task)
        # Auto-save
        session_mgr.save()
    else:
        try:
            runtime.run_interactive()
        finally:
            session_mgr.save()
            print(f"  Session '{session.name}' saved.")


if __name__ == "__main__":
    main()
