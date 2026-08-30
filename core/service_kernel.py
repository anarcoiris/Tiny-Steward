"""StewardEngine — Unified Service Kernel and Headless Facade for Tiny Steward.

Provides a clean, decoupled programmatic API for:
- Session lifecycle & Runtime orchestration
- Turn-based stepping (streaming & synchronous)
- Direct primitive & tool action execution
- Memory dreaming, consolidation, and lessons retrieval
- Skill index querying and semantic lookup
- Health diagnostics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generator, Literal
import yaml

from core.embedder import Embedder
from core.help import HelpEngine
from core.llm import LLMClient
from core.primitives import PRIMITIVES, set_workspace_dir
from core.runtime import Runtime
from core.session import Session, SessionManager
from core.skill_loader import SkillIndex
from core.dreaming import (
    lessons_md_path,
    memory_md_path,
    run_dream,
)
from core.action_parse import parse_llm_result


@dataclass
class TurnResult:
    session_name: str
    response_text: str
    actions_executed: list[dict[str, Any]] = field(default_factory=list)
    thinking: str = ""
    done_reason: str = "stop"
    tokens_used: int = 0
    success: bool = True
    errors: list[str] = field(default_factory=list)
    source: str | None = None


@dataclass
class ActionResult:
    name: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    output: Any = None
    success: bool = True


@dataclass
class SkillMatch:
    name: str
    path: str
    score: float = 0.0
    domain: str | None = None
    description: str = ""


@dataclass
class DreamResult:
    ok: bool
    quarantined: bool = False
    watermark: str | None = None
    count: int = 0
    memory_md: str | None = None
    lessons_md: str | None = None
    reason: str | None = None
    manifest: dict[str, Any] = field(default_factory=dict)


class StewardEngine:
    """Headless Kernel facade for Tiny Steward.
    
    Can be consumed by CLI (steward.py), Web API (serve.py/web_server.py),
    FastMCP server (mcp_server/server.py), and external automated pipelines.
    """

    def __init__(
        self,
        config_path: str | Path = "config.yaml",
        workspace: str | Path | None = None,
        config_dict: dict[str, Any] | None = None,
    ):
        self.config_path = Path(config_path)
        if config_dict is not None:
            self.config = config_dict
        else:
            if not self.config_path.exists():
                fallback = Path(__file__).resolve().parent.parent / config_path
                if fallback.exists():
                    self.config_path = fallback
            if self.config_path.exists():
                with self.config_path.open("r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
            else:
                self.config = {}

        # Set workspace
        ws = workspace or self.config.get("workspace", "./workspace")
        self.workspace = set_workspace_dir(ws)

        # Initialize core components
        llm_cfg = self.config.get("llm", {})
        orch_cfg = llm_cfg.get("orchestrator", {})
        atomic_cfg = llm_cfg.get("atomic", {})
        embed_cfg = self.config.get("embeddings", {})
        skills_cfg = self.config.get("skills", {})
        sessions_cfg = self.config.get("sessions", {})
        rules_cfg = self.config.get("rules", {})

        self.llm = LLMClient.from_lane_config(orch_cfg, gate_lane="orch")
        self.atomic_llm = LLMClient.from_lane_config(atomic_cfg, gate_lane="atomic")
        self.embedder = Embedder.from_config(embed_cfg)

        skills_root_path = Path(skills_cfg.get("root", "./skills"))
        if not skills_root_path.exists():
            fallback_skills = Path(__file__).resolve().parent.parent / skills_root_path
            if fallback_skills.exists():
                skills_root_path = fallback_skills

        skills_index_path = Path(skills_cfg.get("index", "./skills/_index.json"))
        if not skills_index_path.is_absolute() and not skills_index_path.exists():
            fallback_idx = Path(__file__).resolve().parent.parent / skills_index_path
            if fallback_idx.exists():
                skills_index_path = fallback_idx

        if skills_index_path.exists():
            try:
                self.skill_index = SkillIndex.load(skills_index_path, skills_root_path)
            except Exception:
                self.skill_index = SkillIndex([])
        else:
            self.skill_index = SkillIndex([])

        self.help_engine = HelpEngine(
            self.skill_index,
            self.embedder,
            top_k=self.config.get("help", {}).get("top_k", 5),
            min_similarity=self.config.get("help", {}).get("min_similarity", 0.35),
            max_inject_tokens=self.config.get("help", {}).get("max_inject_tokens", 4000),
        )


        self.sessions_dir = Path(sessions_cfg.get("dir", "./sessions"))
        self.session_manager = SessionManager(self.sessions_dir)
        self.rules_path = rules_cfg.get("path", "./RULES.md")
        self.rules_enabled = rules_cfg.get("enabled", True)
        self.os_invariants = self.config.get("os_invariants", {})

        # Runtime instances per session
        self._runtimes: dict[str, Runtime] = {}

    @classmethod
    def create(
        cls,
        config_path: str = "config.yaml",
        workspace: str | None = None,
    ) -> "StewardEngine":
        """Factory constructor."""
        return cls(config_path=config_path, workspace=workspace)

    # ------------------------------------------------------------------
    # Session & Runtime Management
    # ------------------------------------------------------------------
    def get_or_create_session(
        self,
        session_name: str,
        *,
        model_override: str | None = None,
        system_override: str | None = None,
    ) -> Session:
        """Retrieve existing session or create a new one."""
        sess = self.session_manager.switch(session_name)
        if model_override:
            sess.metadata["model_override"] = model_override
        if system_override:
            sess.metadata["system_override"] = system_override
        return sess


    def get_runtime(self, session_name: str) -> Runtime:
        """Get or initialize a Runtime instance for the given session."""
        if session_name in self._runtimes:
            return self._runtimes[session_name]

        session = self.get_or_create_session(session_name)
        ui_cfg = self.config.get("ui", {})
        runtime = Runtime(
            llm=self.llm,
            help_engine=self.help_engine,
            session=session,
            max_turns=self.config.get("max_turns", 50),
            context_budget=self.config.get("context_budget", 26000),
            use_streaming=ui_cfg.get("streaming", True),
            use_markdown=ui_cfg.get("markdown", True),
            show_stats=ui_cfg.get("stats", True),
            checkpoint_every=ui_cfg.get("checkpoint_every", 4),
            atomic_llm=self.atomic_llm,
            config_path=str(self.config_path),
            rules_path=self.rules_path,
            rules_enabled=self.rules_enabled,
            invariants=self.os_invariants,
            session_manager=self.session_manager,
            delegate_terminal=ui_cfg.get("delegate_terminal", "auto"),
            idle_config=self.config.get("idle_loop", {}),
        )
        self._runtimes[session_name] = runtime
        return runtime

    # ------------------------------------------------------------------
    # Step / Execution API
    # ------------------------------------------------------------------
    def step(
        self,
        session_name: str,
        user_input: str,
        *,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> TurnResult:
        """Execute a single conversational turn headlessly.

        stream_callback(kind, text) can receive real-time streaming chunks ("reasoning" or "content").
        """
        runtime = self.get_runtime(session_name)
        session = runtime.session

        # Append user message
        session.add_message("user", user_input)

        # Prepare messages
        messages = runtime._fresh_system_messages() + list(session.messages)

        response_chunks: list[str] = []
        reasoning_chunks: list[str] = []


        try:
            if stream_callback:
                for kind, text in runtime.llm.chat_stream_parts(messages):
                    if kind == "reasoning":
                        reasoning_chunks.append(text)
                        stream_callback("reasoning", text)
                    elif kind == "content":
                        response_chunks.append(text)
                        stream_callback("content", text)
                full_content = "".join(response_chunks)
                full_reasoning = "".join(reasoning_chunks)
            else:
                raw_response = runtime.llm.chat(messages)
                full_reasoning = getattr(runtime.llm, "_last_reasoning", "")
                full_content = raw_response

            done_reason = getattr(runtime.llm, "last_done_reason", "stop")

            # Parse actions with thinking rescue fallback
            actions, source = parse_llm_result(full_content, full_reasoning)

            # Record turn in session
            session.add_message("assistant", full_content, reasoning_content=full_reasoning)

            # Execute any parsed actions
            executed_actions: list[dict[str, Any]] = []
            errors: list[str] = []
            for act in actions:
                res = self.execute_action(act["name"], act.get("body", ""), act.get("attrs", {}))
                executed_actions.append({
                    "name": act["name"],
                    "body": act.get("body", ""),
                    "attrs": act.get("attrs", {}),
                    "result": {
                        "stdout": res.stdout,
                        "stderr": res.stderr,
                        "exit_code": res.exit_code,
                    },
                    "success": res.success,
                })
                if not res.success:
                    errors.append(res.stderr or f"Action {act['name']} failed with exit code {res.exit_code}")

            tokens_used = (
                len(full_content.split()) + len(full_reasoning.split())
            )

            return TurnResult(
                session_name=session_name,
                response_text=full_content,
                actions_executed=executed_actions,
                thinking=full_reasoning,
                done_reason=done_reason,
                tokens_used=tokens_used,
                success=(len(errors) == 0),
                errors=errors,
                source=source,
            )

        except Exception as e:
            return TurnResult(
                session_name=session_name,
                response_text="",
                actions_executed=[],
                thinking="",
                done_reason="abort",
                tokens_used=0,
                success=False,
                errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Direct Action Execution
    # ------------------------------------------------------------------
    def execute_action(
        self,
        name: str,
        body: str = "",
        attrs: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Execute a built-in primitive action directly."""
        attrs = attrs or {}
        primitive_fn = PRIMITIVES.get(name)
        if not primitive_fn:
            return ActionResult(
                name=name,
                exit_code=1,
                stderr=f"Unknown primitive action: {name}",
                success=False,
            )

        try:
            # Map parameters
            if name in ("read", "ls", "mkdir"):
                path = attrs.get("path") or body
                res = primitive_fn(path=path)
            elif name in ("write", "append"):
                path = attrs.get("path", "")
                content = body or attrs.get("content", "")
                res = primitive_fn(path=path, content=content)
            elif name in ("pwsh", "bash"):
                command = body or attrs.get("command", "")
                cwd = attrs.get("cwd")
                res = primitive_fn(command=command, cwd=cwd)
            elif name == "python":
                code = body or attrs.get("code", "")
                res = primitive_fn(code=code)
            elif name == "grep":
                pattern = body or attrs.get("pattern", "")
                path = attrs.get("path", ".")
                res = primitive_fn(pattern=pattern, path=path)
            elif name == "mcp":
                tool = attrs.get("tool", "")
                res = primitive_fn(tool=tool, body=body)
            else:
                res = primitive_fn(**attrs)

            if isinstance(res, dict):
                code = res.get("exit_code")
                stdout = str(res.get("stdout") or res.get("content") or "")
                stderr = str(res.get("stderr") or res.get("error") or "")
                success = (code == 0) if code is not None else ("error" not in res)
                return ActionResult(
                    name=name,
                    exit_code=code,
                    stdout=stdout,
                    stderr=stderr,
                    output=res,
                    success=success,
                )
            return ActionResult(name=name, stdout=str(res), success=True)
        except Exception as e:
            return ActionResult(
                name=name,
                exit_code=1,
                stderr=str(e),
                success=False,
            )

    # ------------------------------------------------------------------
    # Dreaming & Memory API
    # ------------------------------------------------------------------
    def dream(
        self,
        session_name: str,
        *,
        force_all: bool = False,
        allow_quarantined: bool = False,
    ) -> DreamResult:
        """Run a dream cycle for the session to consolidate durable memories & lessons."""
        res = run_dream(
            sessions_dir=self.sessions_dir,
            session_name=session_name,
            llm=self.atomic_llm,
            force_all=force_all,
            allow_quarantined=allow_quarantined,
        )
        return DreamResult(
            ok=res.get("ok", False),
            quarantined=res.get("quarantined", False),
            watermark=res.get("watermark"),
            count=res.get("count", 0),
            memory_md=res.get("memory_md"),
            lessons_md=res.get("lessons_md"),
            reason=res.get("reason"),
            manifest=res.get("manifest", {}),
        )

    def read_memory(self, session_name: str) -> str:
        """Read the generated markdown memory for a session."""
        p = memory_md_path(self.sessions_dir, session_name)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def read_lessons(self, session_name: str) -> str:
        """Read the generated lessons learned for a session."""
        p = lessons_md_path(self.sessions_dir, session_name)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    # ------------------------------------------------------------------
    # Skill Lookup API
    # ------------------------------------------------------------------
    def query_skills(
        self,
        query: str,
        domain: str | None = None,
        top_k: int = 5,
    ) -> list[SkillMatch]:
        """Semantically search skills and capabilities."""
        results = self.help_engine.search(query, top_k=top_k)
        matches: list[SkillMatch] = []
        for r in results:
            matches.append(SkillMatch(
                name=r.get("name", ""),
                path=r.get("path", ""),
                score=r.get("score", 0.0),
                domain=r.get("domain"),
                description=r.get("description", ""),
            ))
        return matches

    # ------------------------------------------------------------------
    # Health Diagnostics
    # ------------------------------------------------------------------
    def health_check(self) -> dict[str, Any]:
        """Check reachability and health of all backends."""
        return {
            "orchestrator_llm": {
                "base_url": self.llm.base_url,
                "model": self.llm.model,
                "healthy": self.llm.health(),
            },
            "atomic_llm": {
                "base_url": self.atomic_llm.base_url,
                "model": self.atomic_llm.model,
                "healthy": self.atomic_llm.health(),
            },
            "embedder": {
                "base_url": self.embedder.base_url,
                "model": self.embedder.model,
                "healthy": self.embedder.health(),
            },
            "workspace": str(self.workspace),
            "sessions_count": len(self.session_manager.list_sessions()),
        }
