"""Runtime — the main reasoning loop.

The orchestrator sends the conversation to the LLM, parses action tags
from the response, executes them, and feeds results back into the
conversation. The help() action triggers semantic skill search.

Action format (XML-tagged in LLM response):
  <action name="pwsh">Get-ChildItem</action>
  <action name="help">Permission denied publickey</action>
  <action name="write" path="file.txt">content here</action>
  <action name="http" method="GET">https://example.com</action>
"""

from __future__ import annotations

import re
import json
from typing import Any

from core.llm import LLMClient, estimate_messages_tokens
from core.primitives import PRIMITIVES
from core.help import HelpEngine
from core.session import Session


# ------------------------------------------------------------------
# System prompt — intentionally tiny (~600 tokens)
# ------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are Tiny Steward, a task executor with a minimal set of primitive actions.

## Available primitives

- pwsh(command): execute a PowerShell command (primary shell)
- bash(command): execute a bash command (via WSL on Windows)
- python(code): execute a Python snippet
- read(path): read file contents
- write(path, content): create/overwrite a file
- append(path, content): append to a file
- mkdir(path): create directory
- ls(path): list directory contents
- grep(pattern, path): search for text in files
- http(method, url, body?): make an HTTP request
- mcp(tool, body?): execute a tool on the nina-mcp server
- help(query): discover capabilities for a problem or error

## How to act

Respond with actions using XML tags:

<action name="pwsh">Get-ChildItem -Recurse</action>
<action name="read" path="config.yaml"></action>
<action name="write" path="output.txt">file content here</action>
<action name="http" method="POST" url="http://example.com">{"key": "value"}</action>
<action name="mcp" tool="nina_camera_capture">{"duration": 1, "save": false}</action>
<action name="help">container won't start</action>

## When to use help()

Call help() when you:
- Encounter an error you're unsure how to fix
- Need a capability outside your primitives
- Want guidance on a domain-specific task (git, docker, python env, etc.)

help() returns relevant skill documents. Read them and continue working.
You can call help() multiple times with narrower queries.

## Rules

- Execute one action at a time. Wait for the result before continuing.
- Explain your reasoning briefly before each action.
- When a task is complete, say DONE and summarize what was accomplished.
- If you're stuck after 3 help() calls on the same problem, ask the user.
"""


# ------------------------------------------------------------------
# Action parsing
# ------------------------------------------------------------------
ACTION_PATTERN = re.compile(
    r'<action\s+name="(\w+)"'    # name attribute
    r'(?:\s+(\w+)="([^"]*)")*'   # optional extra attributes
    r'\s*>(.*?)</action>',
    re.DOTALL,
)

# More flexible: capture all attributes
ATTR_PATTERN = re.compile(r'(\w+)="([^"]*)"')


def parse_actions(text: str) -> list[dict[str, Any]]:
    """Parse <action> tags from LLM response text."""
    actions: list[dict[str, Any]] = []

    for match in re.finditer(r'<action\s+(.*?)>(.*?)</action>', text, re.DOTALL):
        attrs_str = match.group(1)
        body = match.group(2).strip()

        attrs = dict(ATTR_PATTERN.findall(attrs_str))
        name = attrs.pop("name", None)
        if not name:
            continue

        actions.append({
            "name": name,
            "body": body,
            "attrs": attrs,
        })

    return actions


# ------------------------------------------------------------------
# Runtime
# ------------------------------------------------------------------
class Runtime:
    """The main reasoning loop."""

    def __init__(
        self,
        llm: LLMClient,
        help_engine: HelpEngine,
        session: Session,
        *,
        max_turns: int = 50,
        context_budget: int = 28000,  # tokens, leave room below 32k
    ):
        self.llm = llm
        self.help_engine = help_engine
        self.session = session
        self.max_turns = max_turns
        self.context_budget = context_budget

    def run_task(self, task: str) -> str:
        """Execute a task through the reasoning loop."""
        # Initialize conversation
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # If session has history, restore it (but summarize if too long)
        if self.session.messages:
            history = self.session.messages[-20:]  # keep recent context
            messages.extend(history)

        # Pre-flight: compact before the first LLM call if already over budget
        if estimate_messages_tokens(messages) > self.context_budget:
            messages = self._compact_messages(messages)

        # Add the new task
        messages.append({"role": "user", "content": task})
        self.session.add_message("user", task)

        # Reasoning loop
        for turn in range(self.max_turns):
            # Check context budget
            token_est = estimate_messages_tokens(messages)
            if token_est > self.context_budget:
                messages = self._compact_messages(messages)

            # Call LLM
            try:
                response = self.llm.chat(messages)
            except Exception as e:
                error_msg = f"LLM error: {e}"
                print(f"\n  [error] {error_msg}")
                return error_msg

            messages.append({"role": "assistant", "content": response})
            self.session.add_message("assistant", response)

            # Print the response
            self._print_response(response)

            # Check for DONE
            if "DONE" in response and not parse_actions(response):
                return response

            # Parse and execute actions
            actions = parse_actions(response)
            if not actions:
                # No actions and no DONE — might be a question or reasoning
                # Let the user see it and decide
                return response

            for action in actions:
                result = self._execute_action(action)
                result_text = self._format_result(action["name"], result)

                # Add result to conversation
                messages.append({"role": "user", "content": f"[Result of {action['name']}]\n{result_text}"})
                self.session.add_message("user", f"[Result of {action['name']}]\n{result_text}")

                # Print result
                self._print_result(action["name"], result_text)

        return "[Max turns reached]"

    def run_interactive(self):
        """Interactive REPL mode."""
        print("\n  Tiny Steward — Semantic Capability Graph")
        print("  ─────────────────────────────────────────")
        print(f"  Session: {self.session.name}")
        print(f"  Skills indexed: {self.help_engine.index.size}")
        print("  Commands: /session <name>, /sessions, /quit, /help <query>")
        print()

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Restore session history
        if self.session.messages:
            recent = self.session.messages[-20:]
            messages.extend(recent)
            print(f"  (Restored {len(recent)} messages from session)")
            print()

        # Pre-flight: compact before the first user turn if already over budget
        if estimate_messages_tokens(messages) > self.context_budget:
            messages = self._compact_messages(messages)
            print("  (Session history compacted to fit context budget)")
            print()

        while True:
            try:
                user_input = input("  you › ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Bye.")
                break

            if not user_input:
                continue

            # Meta commands
            if user_input.startswith("/"):
                if self._handle_meta_command(user_input):
                    continue
                if user_input.lower() in ("/quit", "/exit", "/q"):
                    break

            # Add user message
            messages.append({"role": "user", "content": user_input})
            self.session.add_message("user", user_input)

            # Reasoning loop for this turn
            for turn in range(self.max_turns):
                # Budget check
                token_est = estimate_messages_tokens(messages)
                if token_est > self.context_budget:
                    messages = self._compact_messages(messages)

                # Call LLM
                try:
                    response = self.llm.chat(messages)
                except Exception as e:
                    print(f"\n  [error] LLM error: {e}")
                    break

                messages.append({"role": "assistant", "content": response})
                self.session.add_message("assistant", response)
                self._print_response(response)

                # Parse actions
                actions = parse_actions(response)
                if not actions:
                    break  # No actions — turn complete, wait for user

                # Execute actions
                for action in actions:
                    result = self._execute_action(action)
                    result_text = self._format_result(action["name"], result)
                    messages.append({"role": "user", "content": f"[Result of {action['name']}]\n{result_text}"})
                    self.session.add_message("user", f"[Result of {action['name']}]\n{result_text}")
                    self._print_result(action["name"], result_text)

                # If response contains DONE, break
                if "DONE" in response:
                    break

            print()

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------
    def _execute_action(self, action: dict[str, Any]) -> dict[str, Any] | str:
        """Execute a single parsed action."""
        name = action["name"]
        body = action["body"]
        attrs = action.get("attrs", {})

        # Special case: help
        if name == "help":
            result = self.help_engine.search(body)
            # Record discovered skills
            if "📖" in result or "🗂️" in result:
                # Extract skill slugs from result (rough heuristic)
                for line in result.split("\n"):
                    if line.startswith("## 📖") or line.startswith("## 🗂️"):
                        parts = line.split("(")
                        if len(parts) > 1:
                            skill_name = parts[0].replace("## 📖", "").replace("## 🗂️", "").strip()
                            self.session.record_skill(skill_name.lower().replace(" ", "_"))
            return {"content": result}

        # Lookup primitive
        primitive = PRIMITIVES.get(name)
        if not primitive:
            return {"error": f"Unknown action: {name}. Use help() to discover capabilities."}

        # Dispatch based on action type
        try:
            if name in ("pwsh", "bash"):
                return primitive(body, cwd=attrs.get("cwd"))
            elif name == "python":
                return primitive(body)
            elif name == "read":
                path = attrs.get("path") or body
                return primitive(path)
            elif name == "write":
                path = attrs.get("path", "")
                return primitive(path, body)
            elif name == "append":
                path = attrs.get("path", "")
                return primitive(path, body)
            elif name == "mkdir":
                return primitive(body)
            elif name == "ls":
                return primitive(body or ".")
            elif name == "grep":
                path = attrs.get("path", ".")
                return primitive(body, path)
            elif name == "http":
                method = attrs.get("method", "GET")
                url = attrs.get("url") or body
                http_body = body if attrs.get("url") else None
                return primitive(method, url, http_body)
            elif name == "mcp":
                tool = attrs.get("tool", "")
                return primitive(tool, body)
            else:
                return primitive(body)
        except Exception as e:
            return {"error": f"Action {name} failed: {e}"}

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------
    def _format_result(self, name: str, result: dict[str, Any] | str) -> str:
        """Format an action result for injection into conversation."""
        if isinstance(result, str):
            return result

        if "error" in result:
            return f"ERROR: {result['error']}"

        parts = []
        if "content" in result:
            parts.append(result["content"])
        if "stdout" in result and result["stdout"]:
            parts.append(result["stdout"])
        if "stderr" in result and result["stderr"]:
            parts.append(f"STDERR: {result['stderr']}")
        if "exit_code" in result and result["exit_code"] != 0:
            parts.append(f"(exit code: {result['exit_code']})")
        if "status" in result:
            parts.append(f"HTTP {result['status']}")
            if "content" in result:
                parts.append(result["content"])

        return "\n".join(parts) if parts else "(no output)"

    def _print_response(self, text: str):
        """Print LLM response with formatting."""
        # Strip action tags for display, show reasoning
        clean = re.sub(r'<action\s+.*?>.*?</action>', '[action]', text, flags=re.DOTALL)
        for line in clean.strip().split("\n"):
            print(f"  steward │ {line}")

    def _print_result(self, name: str, text: str):
        """Print action result."""
        lines = text.split("\n")
        max_lines = 30
        if len(lines) > max_lines:
            shown = lines[:max_lines]
            print(f"  ── {name} ──")
            for line in shown:
                print(f"  │ {line}")
            print(f"  │ ... ({len(lines) - max_lines} more lines)")
            print(f"  └──────────")
        else:
            print(f"  ── {name} ──")
            for line in lines:
                print(f"  │ {line}")
            print(f"  └──────────")

    # ------------------------------------------------------------------
    # Context compaction
    # ------------------------------------------------------------------
    def _compact_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Compact conversation when approaching context budget.

        Strategy: keep system prompt + last N messages, summarize the rest.
        """
        system = messages[0]  # always keep system prompt
        recent = messages[-10:]  # keep last 10 messages

        # Build a summary of what was dropped
        dropped = messages[1:-10]
        if dropped:
            summary_parts = []
            for msg in dropped[-5:]:  # summarize only last 5 of dropped
                role = msg["role"]
                content = msg["content"][:200]
                summary_parts.append(f"[{role}] {content}...")

            summary = {
                "role": "system",
                "content": f"[Context compacted. {len(dropped)} earlier messages summarized. Recent context:]\n"
                + "\n".join(summary_parts),
            }
            return [system, summary] + recent

        return [system] + recent

    # ------------------------------------------------------------------
    # Meta commands
    # ------------------------------------------------------------------
    def _handle_meta_command(self, cmd: str) -> bool:
        """Handle /commands. Returns True if handled."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        if command == "/help" and len(parts) > 1:
            # Direct help query without going through LLM
            result = self.help_engine.search(parts[1])
            print(f"\n{result}\n")
            return True

        if command == "/sessions":
            sessions = self.session_manager.list_sessions() if hasattr(self, 'session_manager') else []
            if sessions:
                print("\n  Sessions:")
                for s in sessions:
                    marker = " ◀" if self.session and s["name"] == self.session.name else ""
                    print(f"    {s['name']} ({s['messages']} msgs, {s['skills']} skills){marker}")
            else:
                print("  No saved sessions.")
            print()
            return True

        if command == "/skills":
            print(f"\n  Indexed skills: {self.help_engine.index.size}")
            for skill in self.help_engine.index.skills:
                t = "🗂️" if skill.skill_type == "hub" else "📖"
                print(f"    {t} {skill.slug} — {skill.description[:60] if skill.description else skill.name}")
            print()
            return True

        return False
