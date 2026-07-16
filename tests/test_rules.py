"""Tests for global RULES.md loading and system prompt composition."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.help import HelpEngine
from core.llm import LLMClient
from core.runtime import (
    Runtime,
    SYSTEM_PROMPT,
    compose_system_prompt,
    load_rules_text,
)
from core.session import Session
from core.skill_loader import Skill, SkillIndex


class TestRulesLoading(unittest.TestCase):
    def test_load_missing_returns_empty(self):
        self.assertEqual(load_rules_text(Path("definitely-missing-rules-xyz.md")), "")

    def test_load_and_compose(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "RULES.md"
            path.write_text("# Rules\n\nAlways write tests.\n", encoding="utf-8")
            text = load_rules_text(path)
            self.assertIn("Always write tests", text)
            composed = compose_system_prompt(text)
            self.assertTrue(composed.startswith(SYSTEM_PROMPT.rstrip()[:40]) or SYSTEM_PROMPT[:40] in composed)
            self.assertIn("Global rules", composed)
            self.assertIn("Always write tests", composed)

    def test_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "RULES.md"
            path.write_text("secret rule", encoding="utf-8")
            self.assertEqual(load_rules_text(path, enabled=False), "")

    def test_runtime_injects_rules(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "RULES.md"
            path.write_text("Use task.md for multi-turn work.", encoding="utf-8")
            llm = LLMClient(base_url="http://mock", model="m")
            skill = Skill(name="t", slug="t", path="t.md", skill_type="skill")
            rt = Runtime(
                llm=llm,
                help_engine=HelpEngine(SkillIndex([skill], vectors=None), None),
                session=Session("rules-test"),
                use_streaming=False,
                rules_path=path,
                rules_enabled=True,
            )
            msgs = rt._fresh_system_messages()
            self.assertEqual(msgs[0]["role"], "system")
            self.assertIn("Use task.md", msgs[0]["content"])

    def test_truncate_long_rules(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "RULES.md"
            path.write_text("x" * 10_000, encoding="utf-8")
            text = load_rules_text(path, max_chars=100)
            self.assertLessEqual(len(text), 150)
            self.assertIn("truncated", text)


if __name__ == "__main__":
    unittest.main()
