"""Tests for System Prompt static purity and LCP stability."""

import unittest
from unittest.mock import MagicMock
from core.system_prompt import (
    RULES_MAX_CHARS,
    SYSTEM_PROMPT,
    compose_system_prompt,
    load_rules_text,
)
from core.runtime import Runtime


class TestSystemPromptLCP(unittest.TestCase):
    def test_rules_max_chars_is_3500(self):
        self.assertEqual(RULES_MAX_CHARS, 3500)

    def test_compose_system_prompt_static_purity(self):
        invariants = {
            "os": "windows",
            "shell": "powershell",
            "path_style": "absolute",
            "workspace_dir": "C:/Workspace",
        }
        prompt1 = compose_system_prompt(
            rules_text="Rule 1",
            invariants=invariants,
            workspace_dir="C:/Workspace",
        )
        prompt2 = compose_system_prompt(
            rules_text="Rule 1",
            invariants=invariants,
            workspace_dir="C:/Workspace",
        )
        self.assertEqual(prompt1, prompt2)
        self.assertIn("## OS, Shell & Workspace Invariants (Layer 0)", prompt1)
        self.assertIn("## Global rules (RULES.md)", prompt1)

    def test_fresh_system_messages_does_not_inject_dynamic_task_plan(self):
        llm = MagicMock()
        help_engine = MagicMock()
        session = MagicMock()
        session.name = "test_lcp"
        session.metadata = {}
        session.messages = []

        rt = Runtime(
            llm=llm,
            help_engine=help_engine,
            session=session,
            invariants={"os": "windows", "shell": "powershell"},
        )
        rt._rules_text = "Standard rules"
        rt._get_active_task_text = MagicMock(return_value=("task.md", "Dynamic task content"))

        msgs = rt._fresh_system_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "system")
        # Ensure dynamic task plan is NOT in the frozen system prompt
        self.assertNotIn("Dynamic task content", msgs[0]["content"])
        self.assertNotIn("## Active Session Task Plan", msgs[0]["content"])
        self.assertIn("Standard rules", msgs[0]["content"])


if __name__ == "__main__":
    unittest.main()
