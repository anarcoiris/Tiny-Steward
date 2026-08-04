"""Runtime Reasoning Loop & Cognitive Sprints Mixin.

Provides LLM execution, unified reasoning loop, rethink handling, token tracking,
and multi-turn cognitive sprints for Runtime.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

import core.display as display
from core.primitives import PRIMITIVES_TOOLS
from core.stats import TurnStats

if TYPE_CHECKING:
    from core.llm import LLMClient


class RuntimeLoopMixin:
    """Mixin providing LLM execution, rethink loop, token stats, and cognitive sprints."""

    def _call_llm(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict] | None = None,
        turn: int = 1,
        backend: str = "primary",
        llm: LLMClient | None = None,
        tools_override: list[dict] | None = None,
        force_no_tools: bool = False,
    ) -> tuple[str, dict[str, Any], float]:
        """Execute non-streaming LLM call. Returns (response_text, usage_dict, elapsed_seconds)."""
        kwargs: dict[str, Any] = {}
        target_tools = tools_override if tools_override is not None else tools
        if target_tools is None:
            skill = getattr(self, "skill", None)
            if skill and hasattr(self, "_tools_for_skill"):
                target_tools = self._tools_for_skill(skill)
            else:
                target_tools = PRIMITIVES_TOOLS

        if not force_no_tools and self._should_send_tools(backend) and target_tools:
            kwargs["tools"] = target_tools
            self._mark_tools_sent(backend)

        client = llm or (getattr(self, "atomic_llm", self.llm) if backend in ("secondary", "atomic") else self.llm)

        # Strip vision content if running on secondary/atomic backend
        if backend in ("secondary", "atomic"):
            clean_messages = []
            for msg in messages:
                m = dict(msg)
                c = m.get("content")
                if isinstance(c, list):
                    m["content"] = [
                        p for p in c
                        if not (isinstance(p, dict) and p.get("type") in ("image_ref", "image_url"))
                    ]
                clean_messages.append(m)
            messages = clean_messages

        t0 = time.perf_counter()
        resp = client.chat(messages, **kwargs)
        dt = time.perf_counter() - t0

        usage = getattr(client, "last_usage", {}) or {}
        if usage:
            turn_stats = TurnStats(
                turn=getattr(self.session_stats, "total_turns", 1),
                prompt_tokens_est=usage.get("prompt_tokens", 0),
                completion_tokens_est=usage.get("completion_tokens", 0),
                prompt_tokens_real=usage.get("prompt_tokens"),
                completion_tokens_real=usage.get("completion_tokens"),
                elapsed_s=dt,
            )
            self._emit_stats(turn_stats)

        return resp, usage, dt

    def _stream_response(self, messages: list[dict[str, Any]], tools: list[dict] | None = None) -> str:
        """Stream LLM response with real-time thinking & text display."""
        if not self.use_streaming:
            resp, _, _ = self._call_llm(messages, tools=tools)
            return resp

        backend = "primary"
        kwargs: dict[str, Any] = {}
        if self._should_send_tools(backend) and tools:
            kwargs["tools"] = tools
            self._mark_tools_sent(backend)

        client = getattr(self, "atomic_llm", self.llm) if backend in ("secondary", "atomic") else self.llm

        full_chunks = []
        is_thinking = False
        t0 = time.perf_counter()

        display.print_response_stream_start()
        try:
            for kind, chunk in client.chat_stream_parts(messages, **kwargs):
                if kind == "reasoning":
                    if not is_thinking:
                        display.print_think_start()
                        is_thinking = True
                    display.print_think_chunk(chunk)
                    self._append_think_log(chunk)
                else:
                    if is_thinking:
                        display.print_think_end()
                        is_thinking = False
                    display.print_stream_chunk(chunk)
                full_chunks.append(chunk)

            if is_thinking:
                display.print_think_end()
            display.print_stream_end()

            final_text = "".join(full_chunks)

            dt = time.perf_counter() - t0
            timings = getattr(client, "_last_timings", {}) or {}
            prompt_tok = timings.get("prompt_n", 0) or 0
            compl_tok = timings.get("predicted_n", 0) or 0
            if prompt_tok or compl_tok:
                turn_stats = TurnStats(
                    turn=getattr(self.session_stats, "total_turns", 1),
                    prompt_tokens_est=sum(len(str(m.get("content", ""))) // 4 for m in messages),
                    completion_tokens_est=len(final_text) // 4,
                    prompt_tokens_real=prompt_tok if prompt_tok else None,
                    completion_tokens_real=compl_tok if compl_tok else None,
                    elapsed_s=dt,
                    context_budget_used=sum(len(str(m.get("content", ""))) // 4 for m in messages) / self.context_budget,
                    cache_n=timings.get("cache_n") or None,
                    prompt_n=timings.get("prompt_n") or None,
                )
                display.print_stats(turn_stats)

            return final_text
        except Exception as e:
            if is_thinking:
                display.print_think_end()
            display.print_stream_end()
            display.print_error(f"Streaming error: {e}")
            return f"ERROR: Streaming failed: {e}"

    def _record_assistant_turn(
        self,
        messages: list[dict[str, Any]],
        content: str,
        persist_session: bool = True,
        client: Any = None,
    ) -> None:
        """Append assistant response to context memory and optionally session storage."""
        msg = {"role": "assistant", "content": content}
        messages.append(msg)
        if persist_session and hasattr(self, "session") and self.session:
            self.session.add_message("assistant", content)
            if hasattr(self, "session_manager") and self.session_manager:
                active_client = client or getattr(self, "llm", None)
                reasoning = getattr(active_client, "_last_reasoning", "")
                if not reasoning and "<think>" in content and "</think>" in content:
                    reasoning = content.split("</think>")[0].split("<think>")[-1].strip()
                if reasoning:
                    think_file = self.session_manager.session_dir(self.session.name) / f"{self.session.name}.think.jsonl"
                    try:
                        record = {"timestamp": time.time(), "reasoning": reasoning}
                        with open(think_file, "a", encoding="utf-8") as f:
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    except Exception:
                        pass

    def _append_think_log(self, text: str) -> None:
        """Append text to current session's think log."""
        if hasattr(self, "session_manager") and self.session_manager and hasattr(self, "session") and self.session:
            log_dir = Path(self.session_manager.dir) / ".think_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{self.session.name}.think.log"
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass

    def _emit_stats(self, turn_stats: TurnStats) -> None:
        """Record turn stats to session stats and display if configured."""
        if hasattr(self, "session_stats") and self.session_stats:
            self.session_stats.add_turn(turn_stats)
        if getattr(self, "show_stats", False):
            display.print_stats(turn_stats)

    def _save_checkpoint(self, note: str | None = None) -> None:
        """Save runtime checkpoint."""
        if hasattr(self, "session_manager") and self.session_manager and hasattr(self, "session") and self.session:
            cp_dir = Path(self.session_manager.dir) / "checkpoints"
            cp_dir.mkdir(parents=True, exist_ok=True)
            cp_file = cp_dir / f"{self.session.name}_{int(time.time())}.json"
            data = {
                "session": self.session.name,
                "timestamp": time.time(),
                "note": note or "",
                "messages_count": len(self.session.messages),
            }
            try:
                cp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                display.print_event("checkpoint", f"Saved checkpoint to {cp_file.name}")
            except Exception as e:
                display.print_error(f"Failed to save checkpoint: {e}")

    def _handle_rethink_loop(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict],
        actions: list[dict[str, Any]],
        errors: list[str],
    ) -> tuple[bool, int, list[dict[str, Any]], str]:
        """Attempt a rethink turn after action errors.

        Returns: (rethink_success, errors_in_turn, messages, final_response)
        """
        first_err = errors[0] if isinstance(errors, (list, tuple)) and errors else str(errors)
        display.print_event("rethink", f"Action failed ({first_err}). Invoking rethink loop...")
        
        # Save snapshot of messages before the failed assistant turn + actions
        pre_failed_history = [dict(m) for m in messages]
        
        nudge = (
            f"[SYSTEM NOTE: The action failed with: {first_err}. "
            f"Carefully analyze what went wrong. Do NOT repeat the exact same parameters or approach. "
            f"Think step-by-step about why it failed before trying another action.]"
        )
        temp_messages = list(messages)
        temp_messages.append({"role": "user", "content": nudge})

        display.print_header("RETHINK LOOP")
        rethink_response = self._stream_response(temp_messages, tools=tools)

        # Record assistant turn and track index to accurately slice ALL tool results
        assistant_idx = len(temp_messages)
        self._record_assistant_turn(temp_messages, rethink_response, persist_session=False)

        rethink_had_actions, rethink_errors = self._process_response_actions(
            rethink_response,
            temp_messages,
            persist_session=False,
        )

        if rethink_had_actions and not rethink_errors:
            display.print_event("rethink", "Rethink successful! Action succeeded.")
            # Commit the successful path into main messages and session
            successful_assistant_msg = temp_messages[assistant_idx]
            successful_tool_results = temp_messages[assistant_idx + 1:]
            
            # Re-commit only the successful path
            self._record_assistant_turn(messages, successful_assistant_msg["content"], persist_session=True)
            for msg in successful_tool_results:
                if msg.get("role") == "tool":
                    self._append_tool_result(messages, msg.get("name", "tool"), msg.get("content", ""), persist=True)
            return True, 0, messages, rethink_response
        else:
            display.print_event("rethink", "Rethink failed to resolve action error.")
            # Restore original messages
            messages.clear()
            messages.extend(pre_failed_history)
            return False, len(rethink_errors) if rethink_had_actions else 1, messages, rethink_response

    def _cognitive_sprint(
        self,
        question: str,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
    ) -> str:
        """Execute a 3-phase structured cognitive sprint (Brainstorm -> Rethink -> Synthesis).

        Uses varying temperatures for divergent vs convergent phases. Returns final synthesis.
        """
        display.print_header("COGNITIVE SPRINT — Phase 1: Brainstorming")
        convo = list(messages)
        
        # Phase 1: Brainstorm (High Temp)
        convo.append({
            "role": "user",
            "content": f"{question}\n\n[Phase 1: Brainstorming]\nList 4-6 distinct, creative ideas or technical approaches. One line per idea without full details."
        })
        old_temp = getattr(self.llm, "temperature", 0.15)
        try:
            self.llm.temperature = 0.8
            brainstorm_resp = self._stream_response(convo, tools=None)
            convo.append({"role": "assistant", "content": brainstorm_resp})

            display.print_header("COGNITIVE SPRINT — Phase 2: Critical Rethink & Risk Evaluation")
            # Phase 2: Evaluate / Rethink (Low Temp)
            convo.append({
                "role": "user",
                "content": "[Phase 2: Critical Evaluation]\nFor each brainstormed idea, critically evaluate its validity, potential failure modes, edge cases, and OS/permission risks in 2 sentences."
            })
            self.llm.temperature = 0.2
            eval_resp = self._stream_response(convo, tools=None)
            convo.append({"role": "assistant", "content": eval_resp})

            display.print_header("COGNITIVE SPRINT — Phase 3: Synthesis & Tool Execution Plan")
            # Phase 3: Synthesize (Normal Temp)
            convo.append({
                "role": "user",
                "content": "[Phase 3: Synthesis & Action]\nSynthesize the evaluations into a single, concrete, elegant solution. Emit any primitive tool call needed to proceed."
            })
            self.llm.temperature = 0.3
            final_resp = self._stream_response(convo, tools=tools)
            return final_resp
        finally:
            self.llm.temperature = old_temp

    def _reasoning_loop(
        self,
        messages: list[dict[str, Any]],
        *,
        interactive: bool = False,
        prompt_session: Any = None,
        stop_event: Any = None,
    ) -> str:
        """Unified main reasoning loop for both interactive turns and batch tasks."""
        lock = getattr(self, "execution_lock", None)
        if lock:
            with lock.hold_active():
                return self._run_reasoning_loop_body(
                    messages,
                    interactive=interactive,
                    prompt_session=prompt_session,
                    stop_event=stop_event,
                )
        return self._run_reasoning_loop_body(
            messages,
            interactive=interactive,
            prompt_session=prompt_session,
            stop_event=stop_event,
        )

    def _run_reasoning_loop_body(
        self,
        messages: list[dict[str, Any]],
        *,
        interactive: bool = False,
        prompt_session: Any = None,
        stop_event: Any = None,
    ) -> str:

        skill = getattr(self, "skill", None)
        tools = self._tools_for_skill(skill) if skill else None

        turn = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        t_start = time.time()
        final_response = ""

        while turn < self.max_turns:
            turn += 1
            if interactive:
                display.print_header(f"TURN {turn}")
            else:
                display.print_header(f"TURN {turn}/{self.max_turns}")

            # Check context budget
            current_est = sum(len(str(m.get("content", ""))) // 4 for m in messages)
            if current_est > self.context_budget:
                display.print_event("compaction", f"Context est. {current_est} tokens > budget {self.context_budget}. Compacting...")
                messages = self._compact_messages(messages)

            # Auto-checkpoint every N turns
            if turn > 1 and turn % self.checkpoint_every == 0:
                self._save_checkpoint(f"auto-checkpoint turn {turn}")

            # Drain mailbox
            self._drain_mailbox_into_messages(messages)

            # Interactive mailbox poll check
            if interactive and stop_event and stop_event.is_set():
                break

            # Execute LLM call
            response = self._stream_response(messages, tools=tools)
            final_response = response

            # Accumulate token stats if available
            if hasattr(self.llm, "last_usage") and self.llm.last_usage:
                u = self.llm.last_usage
                total_prompt_tokens += u.get("prompt_tokens", 0)
                total_completion_tokens += u.get("completion_tokens", 0)

            # Record assistant turn
            self._record_assistant_turn(messages, response)

            # Execute actions
            had_actions, errors = self._process_response_actions(response, messages)

            # If actions failed and rethink enabled, attempt rethink
            if errors and getattr(self, "rethink_enabled", True):
                rethink_success, new_errors, messages, rethink_resp = self._handle_rethink_loop(
                    messages, tools or [], had_actions, errors
                )
                if rethink_success:
                    final_response = rethink_resp
                    errors = []

            # Check for DONE signal if no errors
            if not errors and "DONE" in final_response:
                display.print_success("Task complete (DONE signal received).")
                if interactive and hasattr(self, "interaction_log") and self.interaction_log:
                    total_elapsed = time.time() - t_start
                    self.interaction_log.end_interaction(
                        "success", turn, total_prompt_tokens, total_completion_tokens, total_elapsed
                    )
                return final_response

            # If turn had no actions and wasn't interactive completion, break/continue appropriately
            if not had_actions and not interactive:
                break

            if interactive and not had_actions:
                break

        if interactive and hasattr(self, "interaction_log") and self.interaction_log:
            total_elapsed = time.time() - t_start
            outcome = "success" if turn < self.max_turns else "max_turns_exceeded"
            self.interaction_log.end_interaction(
                outcome, turn, total_prompt_tokens, total_completion_tokens, total_elapsed
            )

        return final_response
