"""Task Contract specification for atomic subagent execution workers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskContract:
    """Task Contract specification for atomic subagent execution workers."""

    problem_statement: str
    target_artifacts: list[str] = field(default_factory=list)
    acceptance_criteria: str = ""
    context_attachments: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, data: Any) -> TaskContract:
        if isinstance(data, TaskContract):
            return data
        if isinstance(data, dict):
            return cls(
                problem_statement=str(data.get("problem_statement") or data.get("problem") or ""),
                target_artifacts=list(data.get("target_artifacts") or data.get("artifacts") or []),
                acceptance_criteria=str(data.get("acceptance_criteria") or data.get("criteria") or ""),
                context_attachments=list(data.get("context_attachments") or data.get("attachments") or []),
            )
        if isinstance(data, str):
            text = data.strip()
            if text.startswith("{") and text.endswith("}"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict) and ("problem_statement" in parsed or "problem" in parsed):
                        return cls.parse(parsed)
                except Exception:
                    pass
            return cls(problem_statement=text)
        return cls(problem_statement=str(data))

    def format_prompt(self, context_text: str = "", max_chars: int = 48_000) -> str:
        parts = ["## Task Contract (Execution Worker)"]
        parts.append(f"- **Problem Statement:** {self.problem_statement}")
        if self.target_artifacts:
            parts.append(f"- **Target Artifacts:** {', '.join(self.target_artifacts)}")
        if self.acceptance_criteria:
            parts.append(f"- **Acceptance Criteria:** {self.acceptance_criteria}")
        if self.context_attachments:
            parts.append(f"- **Context Attachments:** {', '.join(self.context_attachments)}")
        if context_text and context_text.strip():
            c_text = context_text.strip()
            if len(c_text) > max_chars:
                c_text = c_text[:max_chars].rstrip() + "\n\n[... Context truncated to fit subagent budget ...]"
            parts.append(f"\n### Supplementary Context\n{c_text}")
        parts.append(
            "\n### Directives for Execution Worker\n"
            "1. Execute actions surgically without questioning or second-guessing the task statement.\n"
            "2. Confirm the Acceptance Criteria before completing.\n"
            "3. Conclude your report with DONE once verified."
        )
        return "\n".join(parts)
