"""Runtime Action Execution & Formatting Mixin.

Handles dispatching, executing, formatting, and tracking primitive and delegate actions.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

from core.primitives import PRIMITIVES
from core.system_prompt import DELEGATE_EXAMPLE_STUB
import core.display as display

if TYPE_CHECKING:
    from core.mailbox import Mailbox


class RuntimeExecutionMixin:
    """Mixin providing action dispatch, execution, formatting, and tool result tracking."""

    def _action_failed(self, result: dict[str, Any] | str | None) -> bool:
        if result is None:
            return True
        if isinstance(result, dict):
            if "error" in result:
                return True
            if result.get("exit_code", 0) != 0:
                return True
        return False

    @staticmethod
    def _is_benign_fs_error(result: dict[str, Any] | str | None) -> bool:
        """Path/FS errors that should not trigger tools-payload resend."""
        if not isinstance(result, dict):
            return False
        err = str(result.get("error", ""))
        return (
            err.startswith("Path not found:")
            or err.startswith("Not a directory:")
            or err.startswith("File not found:")
            or err.startswith("Not a file or directory:")
        )

    def _extract_actions(self, text: str, backend: str = "primary") -> list[dict[str, Any]]:
        """Extract tool call actions from response using provider profile."""
        profiles = getattr(self, "profiles", None)
        profile = profiles.get(backend) if isinstance(profiles, dict) else None
        if not profile:
            profile = getattr(self, "provider_profile", None)
        if profile and hasattr(profile, "extract_actions"):
            return profile.extract_actions(text)
        from core.action_parse import extract_actions
        return extract_actions(text)

    def _process_response_actions(
        self,
        response: str,
        messages: list[dict[str, Any]],
        *,
        backend: str = "primary",
        allow_delegate: bool = True,
        log_actions: bool = False,
        persist_session: bool = True,
    ) -> tuple[bool, list[str]]:
        """Execute actions from an LLM response. Returns (had_actions, errors_list)."""
        if "<tool_call>" in response and not self._extract_actions(response, backend=backend):
            self._force_tools_resend(backend)

        actions = self._extract_actions(response, backend=backend)
        if not actions:
            return False, []

        errors: list[str] = []
        for action in actions:
            display.print_action_placeholder(action["name"], action.get("body", ""))
            result = self._execute_action(action, allow_delegate=allow_delegate, messages=messages)
            result_text = self._format_result(action["name"], result)
            is_error = self._action_failed(result)

            if log_actions and getattr(self, "interaction_log", None):
                code = result.get("exit_code", 0) if isinstance(result, dict) else 0
                if is_error and code == 0:
                    code = 1
                self.interaction_log.record_action(action["name"], action.get("body", ""), code)

            display.print_result(action["name"], result_text, is_error=is_error)
            persist = persist_session and (backend != "secondary" or getattr(self, "_is_delegate_child", False))
            self._append_tool_result(messages, action["name"], result_text, persist=persist)

            if is_error:
                err_str = str(result_text) if result_text is not None else "failed"
                err_msg = f"{action['name']}: {err_str[:120]}"
                errors.append(err_msg)
                if not self._is_benign_fs_error(result):
                    self._force_tools_resend(backend)

        return True, errors

    def _execute_action(
        self,
        action: dict[str, Any],
        *,
        allow_delegate: bool = True,
        messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | str:
        """Execute a parsed action dictionary."""
        name = action.get("name", "")
        body = action.get("body", "")
        attrs = action.get("attrs") or {}

        if name == "checkpoint":
            if getattr(self, "session_manager", None):
                if getattr(self, "session", None):
                    self.session.metadata["last_checkpoint_note"] = body
                self._save_checkpoint()
                return {"content": f"Checkpoint saved with note: {body}"}
            else:
                return {"error": "Session manager not available, cannot save checkpoint."}

        if name == "help":
            query = attrs.get("query") or body or ""
            if getattr(self, "help_engine", None):
                result = self.help_engine.search(query)
                if getattr(self, "session", None) and ("📖" in result or "🗂️" in result):
                    for line in result.split("\n"):
                        if line.startswith("## 📖") or line.startswith("## 🗂️"):
                            parts = line.split("(")
                            if len(parts) > 1:
                                skill_name = parts[0].replace("## 📖", "").replace("## 🗂️", "").strip()
                                self.session.record_skill(skill_name.lower().replace(" ", "_"))
                return {"content": result}
            return {"content": f"Help search for '{query}' (no help engine available)"}

        if name == "delegate":
            if not allow_delegate:
                return {"error": "Nested delegate not allowed in micro-agent"}
            agent_slug = attrs.get("agent") or attrs.get("skill") or ""
            problem = (attrs.get("task") or body or "").strip()
            if not agent_slug:
                return {"error": "delegate requires agent=<skill-slug>."}
            if not problem or problem == DELEGATE_EXAMPLE_STUB or problem.startswith(
                DELEGATE_EXAMPLE_STUB.rstrip(".")
            ):
                return {
                    "error": (
                        "delegate task must be a complete problem statement "
                        "(text or path) — not empty or the system-prompt stub."
                    )
                }
            help_eng = getattr(self, "help_engine", None)
            skill = None
            if help_eng and hasattr(help_eng, "index") and help_eng.index:
                idx = help_eng.index
                if hasattr(idx, "get_by_slug"):
                    skill = idx.get_by_slug(agent_slug)
                if not skill and hasattr(idx, "get_by_name"):
                    skill = idx.get_by_name(agent_slug)
            if not skill:
                return {"error": f"Agent or skill '{agent_slug}' not found."}

            if not getattr(self, "atomic_llm", None):
                return {"error": "Delegate action failed: no atomic LLM configured. Please specify an atomic model in config.yaml."}

            context_messages = []
            if messages:
                for msg in messages[-12:]:
                    context_messages.append(f"{msg['role'].upper()}: {msg['content']}")
            elif getattr(self, "session", None) and hasattr(self.session, "messages"):
                for msg in self.session.messages[-12:]:
                    context_messages.append(f"{msg['role'].upper()}: {msg['content']}")
            context_text = "\n".join(context_messages)

            playbook_content = ""
            if hasattr(skill, "path") and "legal/" in skill.path:
                skills_root = Path("skills")
                claude_path = skills_root / "legal" / "CLAUDE.md"
                if claude_path.exists():
                    try:
                        playbook_content = claude_path.read_text(encoding="utf-8")
                    except Exception as e:
                        playbook_content = f"[Warning: Failed to read CLAUDE.md: {e}]"

            if playbook_content:
                context_text = (
                    f"PLAYBOOK CONFIGURATION (CLAUDE.md):\n"
                    f"==================================================\n"
                    f"{playbook_content}\n"
                    f"==================================================\n\n"
                    f"{context_text}"
                )

            res = self._delegate_with_terminal(skill, problem, context_text)
            return {"content": res}

        try:
            primitive = PRIMITIVES.get(name)
            if not primitive:
                return {"error": f"Unknown action: {name}. Use help() to discover capabilities."}

            if name in ("pwsh", "bash"):
                cmd = attrs.get("command") or body
                cwd = attrs.get("cwd")
                is_async_val = attrs.get("is_async")
                is_async = str(is_async_val).lower() in ("true", "1", "yes") if is_async_val is not None else False
                return primitive(cmd, cwd=cwd, is_async=is_async)
            elif name == "task_status":
                tid = attrs.get("task_id") or body
                tail = int(attrs.get("tail", 30))
                return primitive(tid, tail=tail)
            elif name == "task_kill":
                tid = attrs.get("task_id") or body
                return primitive(tid)
            elif name == "python":
                return primitive(attrs.get("code") or body)
            elif name == "read":
                path = attrs.get("path") or body
                start = attrs.get("start_line")
                end = attrs.get("end_line")
                start_line = int(start) if start is not None else None
                end_line = int(end) if end is not None else None
                return primitive(path, start_line, end_line)
            elif name == "write":
                path = attrs.get("path") or ""
                content = body if body else attrs.get("content", "")
                if not path:
                    return {
                        "error": (
                            "Missing path for write. Use "
                            "<parameter=path>…</parameter> and "
                            "<parameter=content>…</parameter> "
                            "(not bare <path> tags)."
                        )
                    }
                res = primitive(path, content)
                if not self._action_failed(res) and getattr(self, "session", None) and hasattr(self.session, "metadata"):
                    p_norm = path.replace("\\", "/")
                    if p_norm.endswith("task.md") or p_norm.endswith("plan.md"):
                        self.session.metadata["task_file"] = path
                return res
            elif name == "replace":
                path = attrs.get("path") or ""
                old_str = attrs.get("old_str") or attrs.get("target") or attrs.get("find") or ""
                new_str = attrs.get("new_str") or attrs.get("replacement") or body
                count_val = attrs.get("count")
                count = int(count_val) if count_val is not None else 1
                if not path:
                    return {"error": "Missing path for replace. Use <parameter=path>…</parameter>."}
                if not old_str:
                    return {"error": "Missing old_str (text to find) for replace. Use <parameter=old_str>…</parameter> and <parameter=new_str>…</parameter>."}
                return primitive(path, old_str, new_str, count=count)
            elif name == "append":
                path = attrs.get("path") or ""
                content = body if body else attrs.get("content", "")
                if not path:
                    return {
                        "error": (
                            "Missing path for append. Use "
                            "<parameter=path>…</parameter> and "
                            "<parameter=content>…</parameter>."
                        )
                    }
                res = primitive(path, content)
                if not self._action_failed(res) and getattr(self, "session", None) and hasattr(self.session, "metadata"):
                    p_norm = path.replace("\\", "/")
                    if p_norm.endswith("task.md") or p_norm.endswith("plan.md"):
                        self.session.metadata["task_file"] = path
                return res
            elif name == "mkdir":
                path = attrs.get("path") or body
                if not path:
                    return {"error": "Missing path for mkdir."}
                return primitive(path)
            elif name == "ls":
                path = attrs.get("path") or body or "."
                return primitive(path)
            elif name == "grep":
                path = attrs.get("path") or "."
                return primitive(body, path)
            elif name == "http":
                method = attrs.get("method", "GET")
                url = attrs.get("url") or body
                http_body = body if attrs.get("url") else None
                return primitive(method, url, http_body)
            elif name == "mcp":
                tool = attrs.get("tool", "")
                return primitive(tool, body)
            elif name == "set":
                key = attrs.get("key")
                val = attrs.get("value")
                if not key or not val:
                    return {"error": "Missing key or value in set action"}
                msg = self._handle_set(f"{key} {val}")
                return {"content": msg}
            else:
                return primitive(body)
        except Exception as e:
            return {"error": f"Action {name} failed: {e}"}

    def _format_result(self, name: str, result: dict[str, Any] | str | None) -> str:
        """Format an action result for injection into conversation."""
        if result is None:
            return "ERROR: Action returned no output."
        if isinstance(result, str):
            return result

        if "error" in result:
            return f"ERROR: {result['error']}"

        parts = []
        if "content" in result:
            parts.append(result["content"])

        for out_key in ("stdout", "stderr"):
            if out_key in result and result[out_key]:
                out_str = result[out_key]
                lines = out_str.splitlines()
                if len(lines) > 50 and getattr(self, "session_manager", None):
                    temp_dir = self.session_manager.dir / ".temp"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    temp_file = temp_dir / f"{out_key}_{name}_{int(time.time())}.txt"
                    temp_file.write_text(out_str, encoding="utf-8")
                    prefix = f"STDERR: " if out_key == "stderr" else ""
                    parts.append(
                        f"{prefix}[{out_key} is {len(lines)} lines long. The first 50 lines are shown below.\n"
                        f"The full output was saved to {temp_file}.\n"
                        f"Use read('{temp_file}', start_line, end_line) to explore pending unexplored sources.]\n\n"
                        + "\n".join(lines[:50])
                    )
                else:
                    prefix = f"STDERR: " if out_key == "stderr" else ""
                    parts.append(f"{prefix}{out_str}")

        if "exit_code" in result and result["exit_code"] != 0:
            parts.append(f"(exit code: {result['exit_code']})")
        if "status" in result:
            parts.append(f"HTTP {result['status']}")

        return "\n".join(parts) if parts else "(no output)"
