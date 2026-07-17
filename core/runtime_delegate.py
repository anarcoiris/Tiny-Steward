"""Delegate spawn / child loop mixin for Runtime."""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from core.mailbox import mailbox_for
from core.delegate_terminal import (
    build_child_argv,
    resolve_terminal_mode,
    spawn_child,
)
import core.display as display


class RuntimeDelegateMixin:
    """Out-of-process and in-process micro-agent delegation."""

    def _build_delegate_system_prompt(self, skill) -> str:
        prompt_parts = []
        if getattr(skill, "system_prompt", None):
            prompt_parts.append(skill.system_prompt)
        else:
            prompt_parts.append(f"You are a specialist agent executing the skill: {skill.name}.")
            if skill.description:
                prompt_parts.append(skill.description)

        prompt_parts.append(
            "Here are your step-by-step instructions, guidelines, and output formatting rules:\n"
            "==================================================\n"
            f"{skill.body}\n"
            "=================================================="
        )
        if skill.requires:
            prompt_parts.append(f"Available tools / primitives: {', '.join(skill.requires)}")
        prompt_parts.append(
            "Adhere strictly to the guidelines and templates. Be extremely concise, professional, and actionable."
        )
        return "\n\n".join(prompt_parts)

    def _delegate_with_terminal(self, skill, problem: str, context_text: str) -> str:
        """Spawn a child terminal when configured; otherwise run in-process."""
        mode = resolve_terminal_mode(self.delegate_terminal)
        if mode == "in_process" or not self.session_manager:
            return self._run_delegate_loop(skill, problem, context_text)

        child_name = f"{self.session.name}__{skill.slug}_{uuid.uuid4().hex[:8]}"
        steward_path = Path(__file__).resolve().parent.parent / "steward.py"
        # Persist problem+context for the child process via a sidecar file.
        problem_blob = {
            "problem": problem,
            "context": context_text,
            "skill": skill.slug,
            "parent": self.session.name,
        }
        problem_dir = self.session_manager.dir / ".mailbox" / child_name
        problem_dir.mkdir(parents=True, exist_ok=True)
        problem_path = problem_dir / "problem.json"
        problem_path.write_text(json.dumps(problem_blob, ensure_ascii=False, indent=2), encoding="utf-8")

        self.session_manager.update_session_metadata(child_name, {
            "parent": self.session.name,
            "status": "running",
            "skill": skill.slug,
            "terminal_kind": mode,
            "problem_path": str(problem_path),
        })
        self.session_manager.register_child(self.session.name, child_name)

        argv = build_child_argv(
            python=sys.executable,
            steward_path=steward_path,
            config=self.config_path,
            session=child_name,
            parent=self.session.name,
            skill=skill.slug,
            problem=str(problem_path),
        )
        spawn_info = spawn_child(mode, argv, cwd=Path.cwd())
        kind = spawn_info.get("kind")
        if kind == "in_process":
            # Do not leave an orphan out-of-process child session on disk.
            self._abandon_orphan_child(child_name)
            return self._run_delegate_loop(skill, problem, context_text)

        proc = spawn_info.get("process")
        if proc is not None:
            # Fail-fast if the child dies immediately (bad argv / missing python).
            time.sleep(0.35)
            rc = proc.poll()
            if rc is not None:
                err = f"[Delegate spawn failed: child process exited immediately (code {rc})]"
                self.session_manager.update_session_metadata(child_name, {
                    "status": "error",
                    "result": err,
                })
                return err

        if self.session_manager:
            self.session_manager.update_session_metadata(child_name, {
                "pane_id": spawn_info.get("pane_id"),
                "pid": spawn_info.get("pid"),
                "terminal_kind": spawn_info.get("kind"),
            })

        display.print_event(
            "delegate",
            f"Spawned child session '{child_name}' via {spawn_info.get('kind')} — waiting for result…",
        )
        return self._wait_for_delegate_result(child_name, timeout_s=3600.0)

    def _abandon_orphan_child(self, child_name: str) -> None:
        """Mark a provisioned child as cancelled when we fall back to in-process."""
        if not self.session_manager:
            return
        self.session_manager.update_session_metadata(child_name, {
            "status": "cancelled",
            "result": "[Abandoned: spawn fell back to in_process]",
        })
        display.print_event(
            "warn",
            f"Child '{child_name}' not spawned out-of-process — running delegate in-process.",
        )

    def _wait_for_delegate_result(self, child_name: str, *, timeout_s: float = 3600.0) -> str:
        """Block until child marks done or mails a delegate_result."""
        assert self.session_manager is not None
        deadline = time.monotonic() + timeout_s
        parent_box = self._mailbox(self.session.name)
        while time.monotonic() < deadline:
            meta = self.session_manager.load_metadata(child_name)
            status = meta.get("status")
            if status in ("done", "error"):
                result = meta.get("result")
                if result:
                    return str(result)
                return f"[Delegate {status} with empty result]"

            if parent_box:
                for path in sorted(parent_box.inbox.glob("*.json")):
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        continue
                    if data.get("type") == "delegate_result" and data.get("from") == child_name:
                        try:
                            path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        return str(data.get("content", ""))

            time.sleep(0.5)

        return f"[Delegate timeout waiting for child session '{child_name}']"

    def run_delegate_child(self, skill, problem: str, context_text: str = "") -> str:
        """Entry point for ``--delegate-mode`` child processes."""
        parent = (self.session.metadata or {}).get("parent")
        if self.session_manager:
            self.session_manager.update_session_metadata(self.session.name, {
                "status": "running",
                "parent": parent,
                "skill": skill.slug,
            })

        try:
            result = self._run_delegate_loop(skill, problem, context_text)
            status = "done"
        except Exception as e:
            result = f"[Delegate child error: {e}]"
            status = "error"

        if self.session_manager:
            self.session_manager.update_session_metadata(self.session.name, {
                "status": status,
                "result": result,
            })
            self.session_manager.save()

        if parent and self.session_manager:
            box = mailbox_for(self.session_manager.dir, parent)
            box.send(
                from_session=self.session.name,
                to_session=parent,
                content=result,
                msg_type="delegate_result",
                priority="high",
            )

        display.print_event("delegate", f"Child session '{self.session.name}' finished ({status}).")
        return result

    def _run_delegate_loop(self, skill, problem: str, context_text: str) -> str:
        """Run atomic (Qwen) micro-agent with tool-call loop."""
        system_prompt = self._build_delegate_system_prompt(skill)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Problem:\n{problem}\n\nContext:\n{context_text}"},
        ]
        skill_tools = self._tools_for_skill(skill)
        final_response = ""

        for _ in range(self.max_delegate_turns):
            self._drain_mailbox_into_messages(messages)
            send_tools = self._should_send_tools("secondary")

            response, _, _ = self._call_llm(
                messages,
                turn=0,
                backend="secondary",
                llm=self.atomic_llm,
                tools_override=skill_tools if send_tools else None,
                force_no_tools=not send_tools,
            )
            if response is None:
                return "[Delegate LLM error]"

            final_response = response
            self._record_assistant_turn(
                messages,
                response,
                client=self.atomic_llm,
                persist_session=self._is_delegate_child,
            )

            if "DONE" in response and not self._extract_actions(response, backend="secondary"):
                break

            had_actions, _ = self._process_response_actions(
                response,
                messages,
                backend="secondary",
                allow_delegate=False,
            )
            if not had_actions:
                break

        return final_response

