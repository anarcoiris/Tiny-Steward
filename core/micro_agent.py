"""Micro-agent delegation — Phase 2 stub.

When a skill has type: agent, the orchestrator spawns a sub-conversation
on the atomic lane (:11439) instead of just reading the skill markdown.

The micro-agent gets:
- Its own system prompt (from the skill's system_prompt field)
- Only its domain-relevant primitives
- Its own tiny context window
- The problem description from the orchestrator

It returns a structured result to the orchestrator.
"""

from __future__ import annotations

from core.llm import LLMClient
from core.skill_loader import Skill


class MicroAgent:
    """Phase 2: Delegate to a specialist micro-agent on the atomic lane."""

    def __init__(self, atomic_llm: LLMClient):
        self.llm = atomic_llm

    def delegate(self, skill: Skill, problem: str, context: str = "") -> str:
        """Spawn a micro-agent conversation for a specialist skill.

        Args:
            skill: The agent-type skill defining the specialist
            problem: What the orchestrator needs solved
            context: Additional context from the conversation

        Returns:
            The micro-agent's response/solution
        """
        # Extract system prompt from skill metadata
        system_prompt = getattr(skill, "system_prompt", None) or (
            f"You are a {skill.name} specialist. "
            f"Solve the problem using your expertise. "
            f"Available tools: {', '.join(skill.requires)}. "
            f"Be concise and actionable."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Problem:\n{problem}\n\nContext:\n{context}"},
        ]

        return self.llm.chat(messages)
