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

# ---------------------------------------------------------------------------
# Load .env before anything else so PYTHONUTF8 / PYTHONIOENCODING are set
# for every subprocess we spawn (python, pwsh, bash, mcp …).
# Falls back gracefully when python-dotenv is not installed.
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(_env_path, override=False)  # don't clobber shell-level exports
except ImportError:
    pass  # python-dotenv optional; env vars can also be set in the shell

# Belt-and-suspenders: reconfigure stdout/stderr to UTF-8 for the current
# process (covers rich / print output even without PYTHONUTF8).
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
import core.display as display


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
        display.print_health("Orchestrator LLM", llm.base_url, ok=False)
        ok = False
    else:
        display.print_health("Orchestrator LLM", llm.base_url, ok=True)

    if not embedder.health():
        display.print_health("Embedder", embedder.base_url, ok=False)
        ok = False
    else:
        display.print_health("Embedder", embedder.base_url, ok=True)

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
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output")
    parser.add_argument("--no-color", action="store_true", help="Disable color output")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # UI config
    ui_cfg = config.get("ui", {})
    use_streaming = ui_cfg.get("streaming", True) and not args.no_stream
    use_markdown  = ui_cfg.get("markdown", True)
    show_stats    = ui_cfg.get("stats", True)
    checkpoint_every = ui_cfg.get("checkpoint_every", 5)

    # Initialize orchestrator LLM
    orch_cfg = config["llm"]["orchestrator"]
    llm = LLMClient(
        base_url=orch_cfg["base_url"],
        model=orch_cfg["model"],
        max_tokens=orch_cfg.get("max_tokens", 4096),
        temperature=orch_cfg.get("temperature", 0.15),
        top_p=orch_cfg.get("top_p", 0.9),
        repeat_penalty=orch_cfg.get("repeat_penalty", 1.05),
    )

    # Initialize atomic/subagent LLM (optional)
    atomic_llm: LLMClient | None = None
    if "atomic" in config.get("llm", {}):
        at_cfg = config["llm"]["atomic"]
        atomic_llm = LLMClient(
            base_url=at_cfg["base_url"],
            model=at_cfg["model"],
            max_tokens=at_cfg.get("max_tokens", 2048),
            temperature=at_cfg.get("temperature", 0.1),
            top_p=at_cfg.get("top_p", 0.9),
            repeat_penalty=at_cfg.get("repeat_penalty", 1.05),
        )

    # Initialize embedder
    emb_cfg = config["embeddings"]
    embedder = Embedder(
        base_url=emb_cfg["base_url"],
        model=emb_cfg["model"],
    )

    # Health check
    if not args.no_health_check:
        print()
        if not check_health(llm, embedder):
            display.print_event("warn", "Some endpoints are not reachable. Continuing anyway…")
        print()

    # Skills
    skills_cfg = config["skills"]
    skills_root = Path(skills_cfg["root"])
    index_path = Path(skills_cfg["index"])

    # Build index if requested or if it doesn't exist
    if args.build_index or not index_path.exists() or skills_cfg.get("rebuild_on_start"):
        display.print_event("info", "Building skill index…")
        skill_index = build_index(skills_root, embedder)
        skill_index.save(index_path)
        display.print_event("ok", f"Saved index: {index_path.resolve()}")

        if args.build_index:
            display.print_skills_table(skill_index.skills)
            print(f"\n  Total: {skill_index.size} skills")
            return
    else:
        display.print_event("info", f"Loading skill index from {index_path} …")
        skill_index = SkillIndex.load(index_path, skills_root)
        display.print_event("ok", f"Loaded {skill_index.size} skills")

    # List skills
    if args.list_skills:
        display.print_skills_table(skill_index.skills)
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
    context_budget = int(orch_cfg.get("ctx", 32768) * 0.8)
    runtime = Runtime(
        llm=llm,
        help_engine=help_engine,
        session=session,
        use_streaming=use_streaming,
        use_markdown=use_markdown,
        show_stats=show_stats,
        checkpoint_every=checkpoint_every,
        context_budget=context_budget,
        atomic_llm=atomic_llm,
    )
    runtime.session_manager = session_mgr

    # Execute
    if args.task:
        runtime.run_task(args.task)
        session_mgr.save()
    else:
        try:
            runtime.run_interactive()
        finally:
            session_mgr.save()
            display.print_event("session", f"Session '{session.name}' saved.")


if __name__ == "__main__":
    main()
