"""Tiny Steward — Semantic Capability Graph micro-agent runtime.

Entry point. Provides:
  - Interactive REPL (default)
  - Single task execution (--task "...")
  - Index building (--build-index)
  - Session management (--session <name>)
  - Out-of-process delegate child (--delegate-mode)

See also:
  - RULES.md — global rules injected into the system prompt
  - plans/archivos-retirados.md — deleted/absorbed modules (e.g. micro_agent.py)
  - plans/fuera-de-alcance.md — next-cycle backlog (F3+)

Usage:
  python steward.py                          # interactive REPL, default session
  python steward.py --session deploy-flask   # resume named session
  python steward.py --task "list all .py files in ~/projects"
  python steward.py --build-index            # rebuild skill embeddings
"""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--delegate-mode", action="store_true", help="Run as out-of-process delegate child")
    parser.add_argument("--parent", help="Parent session name (delegate child)")
    parser.add_argument("--delegate-skill", help="Skill slug for delegate child")
    parser.add_argument("--problem", help="Problem text or path to problem.json (delegate child)")
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # UI config
    ui_cfg = config.get("ui", {})
    use_streaming = ui_cfg.get("streaming", True) and not args.no_stream
    use_markdown  = ui_cfg.get("markdown", True)
    show_stats    = ui_cfg.get("stats", True)
    checkpoint_every = ui_cfg.get("checkpoint_every", 5)
    delegate_terminal = ui_cfg.get("delegate_terminal", "auto")

    # Initialize orchestrator LLM (Qwythos: thinking on by default)
    orch_cfg = config["llm"]["orchestrator"]
    llm = LLMClient.from_lane_config(orch_cfg, gate_lane="orch")

    # Initialize atomic/subagent LLM (optional; thinking off by default)
    atomic_llm: LLMClient | None = None
    if "atomic" in config.get("llm", {}):
        at_cfg = config["llm"]["atomic"]
        atomic_llm = LLMClient.from_lane_config(at_cfg, gate_lane="atomic")

    from core.backend_launcher import BackendLauncher
    backend_launcher = BackendLauncher.from_config(
        config,
        orch_health=llm.health,
        atomic_health=(atomic_llm.health if atomic_llm else None),
    )

    if not args.delegate_mode:
        backend_launcher.start_vram_monitor(threshold_mb=1750.0, check_interval=30.0)
        for lane in ("orch", "atomic"):
            cfg = backend_launcher.configs.get(lane)
            if cfg and cfg.autostart:
                hf = backend_launcher.health.get(lane)
                if hf and hf():
                    display.print_event("info", f"{lane} backend is already healthy, skipping autostart.")
                else:
                    display.print_event("info", f"Autostarting {lane} backend…")
                    res = backend_launcher.start(lane)
                    if res.get("ok"):
                        display.print_event("ok", f"{lane} backend ready (pid={res.get('pid')})")
                    else:
                        display.print_event("error", f"Failed to autostart {lane}: {res.get('error')}")

    # Backend gate (client-side serialization; complements --parallel 1)
    from core.backend_gate import configure_default_gate

    gate_cfg = (config.get("backends") or {}).get("gate") or {}
    configure_default_gate(
        enabled=bool(gate_cfg.get("enabled", True)),
        orch_slots=int(gate_cfg.get("orch_slots", 1)),
        atomic_slots=int(gate_cfg.get("atomic_slots", 1)),
        embed_slots=int(gate_cfg.get("embed_slots", 1)),
    )

    # MCP launcher paths from config (fallback to primitives defaults)
    mcp_cfg = config.get("mcp") or {}
    if mcp_cfg:
        from core.primitives import configure_mcp
        configure_mcp(
            python_exe=mcp_cfg.get("python_exe"),
            client_py=mcp_cfg.get("client_py"),
        )

    # Initialize embedder
    emb_cfg = config["embeddings"]
    embedder = Embedder(
        base_url=emb_cfg["base_url"],
        model=emb_cfg["model"],
    )

    # Health check + /props reconciliation (yaml is reference; never rewritten)
    vision_enabled = False
    vision_reason = "skipped (--no-health-check or delegate)"
    if not args.no_health_check:
        print()
        if not check_health(llm, embedder):
            display.print_event("warn", "Some endpoints are not reachable. Continuing anyway…")
        from core.config_check import verify_config_backends
        for kind, msg in verify_config_backends(config):
            display.print_event(kind, msg)
        # F5: multimodal probe (orch only; atomic stays text-only)
        from core.vision import resolve_vision_enabled
        vision_mode = orch_cfg.get("vision", "auto")
        vision_enabled, vision_reason = resolve_vision_enabled(
            vision_mode, base_url=llm.base_url,
        )
        kind = "ok" if vision_enabled else "info"
        display.print_event(kind, f"Vision: {'enabled' if vision_enabled else 'disabled'} — {vision_reason}")
        if orch_cfg.get("vision") in ("on", True, "true", "yes", "1") and not vision_enabled:
            display.print_event(
                "warn",
                "vision=on but orch has no multimodal capability — restart with -WithVision / --mmproj",
            )
        print()
    elif not args.delegate_mode:
        # Still resolve off/on without probe when health checks skipped
        from core.vision import resolve_vision_enabled
        mode = str(orch_cfg.get("vision", "auto")).lower()
        if mode in ("off", "false", "no", "0"):
            vision_enabled, vision_reason = False, "config vision=off (--no-health-check)"
        elif mode in ("on", "true", "yes", "1", "require"):
            # Without probe, trust on but warn
            vision_enabled, vision_reason = True, "config vision=on (unprobed; --no-health-check)"
            display.print_event("warn", vision_reason)
        else:
            vision_enabled, vision_reason = False, "vision=auto skipped (--no-health-check)"

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

    if args.parent:
        session.metadata["parent"] = args.parent
        session_mgr.save()

    # Runtime
    context_budget = int(orch_cfg.get("ctx", 32768) * 0.8)
    shortcuts = ui_cfg.get("shortcuts", {
        "send": "escape, enter",
        "newline": "c-j"
    })
    rules_cfg = config.get("rules") or {}
    # Delegate children always use the atomic lane as their primary LLM client.
    runtime_llm = atomic_llm if (args.delegate_mode and atomic_llm) else llm

    orch_provider = str(orch_cfg.get("provider") or "qwythos")
    atomic_provider = str(
        (config.get("llm") or {}).get("atomic", {}).get("provider") or "qwen3_json"
    )
    # Delegate children run on the atomic lane as their primary client.
    if args.delegate_mode:
        primary_provider, secondary_provider = atomic_provider, atomic_provider
    else:
        primary_provider, secondary_provider = orch_provider, atomic_provider

    runtime = Runtime(
        llm=runtime_llm,
        help_engine=help_engine,
        session=session,
        use_streaming=use_streaming,
        use_markdown=use_markdown,
        show_stats=show_stats,
        checkpoint_every=checkpoint_every,
        context_budget=context_budget,
        atomic_llm=atomic_llm,
        shortcuts=shortcuts,
        delegate_terminal=delegate_terminal,
        config_path=args.config,
        rules_path=rules_cfg.get("path", "RULES.md"),
        rules_enabled=bool(rules_cfg.get("enabled", True)),
        backend_launcher=backend_launcher,
        primary_provider=primary_provider,
        secondary_provider=secondary_provider,
        vision_enabled=False if args.delegate_mode else vision_enabled,
    )
    runtime.session_manager = session_mgr

    # F4 metadata: record orch slot pin on the session tree (not a KV dump).
    if not args.delegate_mode and llm.id_slot is not None:
        session.metadata["orch_id_slot"] = llm.id_slot
        session_mgr.save()

    # Execute
    if args.delegate_mode:
        if not args.delegate_skill:
            display.print_event("error", "--delegate-mode requires --delegate-skill")
            sys.exit(2)
        if not atomic_llm:
            display.print_event("error", "No atomic LLM configured for delegate child.")
            sys.exit(2)
        skill = help_engine.index.get_by_slug(args.delegate_skill) or help_engine.index.get_by_name(args.delegate_skill)
        if not skill:
            display.print_event("error", f"Skill '{args.delegate_skill}' not found.")
            sys.exit(2)

        problem = args.problem or ""
        context_text = ""
        if problem and Path(problem).is_file():
            blob = json.loads(Path(problem).read_text(encoding="utf-8"))
            problem = str(blob.get("problem", ""))
            context_text = str(blob.get("context", ""))

        try:
            runtime.mark_delegate_child(parent=args.parent)
            runtime.run_delegate_child(skill, problem, context_text)
        finally:
            session_mgr.save()
        return

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
