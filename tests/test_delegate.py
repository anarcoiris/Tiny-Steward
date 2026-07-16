"""Unit tests for micro-agent delegation and custom system prompt loading.

Tests that skill parser extracts system_prompt and that the runtime delegates correctly.
"""

from __future__ import annotations

import unittest
from pathlib import Path
import tempfile
import shutil

from core.skill_loader import Skill, load_skill, discover_skills, SkillIndex
from core.llm import LLMClient
from core.runtime import Runtime, DELEGATE_EXAMPLE_STUB
from core.help import HelpEngine
from core.session import Session


class MockLLM(LLMClient):
    """Mock LLM client that logs chat calls and returns canned responses."""

    def __init__(self):
        super().__init__(base_url="http://mock", model="mock")
        self.last_messages = []

    def chat(self, messages: list[dict[str, str]], *, max_tokens=None, temperature=None, tools=None) -> str:
        self.last_messages = messages
        return "Mock sub-agent response"

    def health(self) -> bool:
        return True


class TestDelegation(unittest.TestCase):
    """Test suite for specialized agent skills and delegation routing."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.legal_dir = self.temp_dir / "legal"
        self.legal_dir.mkdir(parents=True, exist_ok=True)

        # Create a mock agent skill
        self.skill_file = self.legal_dir / "nda-review.md"
        self.skill_file.write_text(
            "---\n"
            "name: nda_review\n"
            "type: agent\n"
            "system_prompt: \"Custom NDA System Prompt\"\n"
            "---\n"
            "# NDA Review guidelines\n"
            "Instructions go here.\n",
            encoding="utf-8",
        )

        # Create a CLAUDE.md file
        self.claude_file = self.legal_dir / "CLAUDE.md"
        self.claude_file.write_text("Playbook: standard Delaware law.", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_load_system_prompt(self):
        """Test that system_prompt is correctly parsed from frontmatter."""
        skill = load_skill(self.skill_file, self.temp_dir)
        self.assertEqual(skill.skill_type, "agent")
        self.assertEqual(skill.system_prompt, "Custom NDA System Prompt")
        self.assertIn("Instructions go here.", skill.body)

    def test_discover_skips_claude(self):
        """Test that discover_skills discovers the skill but skips CLAUDE.md."""
        skills = discover_skills(self.temp_dir)
        slugs = {s.slug for s in skills}
        self.assertIn("nda-review", slugs)
        self.assertNotIn("CLAUDE", slugs)

    def test_runtime_delegate_prompt_assembly(self):
        """Runtime._build_delegate_system_prompt replaces retired MicroAgent."""
        llm = MockLLM()
        skill = load_skill(self.skill_file, self.temp_dir)
        runtime = Runtime(
            llm=llm,
            help_engine=HelpEngine(SkillIndex([skill], vectors=None), None),
            session=Session("test"),
            atomic_llm=llm,
            use_streaming=False,
        )
        prompt = runtime._build_delegate_system_prompt(skill)
        self.assertIn("Custom NDA System Prompt", prompt)
        self.assertIn("Instructions go here.", prompt)

    def test_runtime_delegate_action(self):
        """Test that Runtime delegates when running delegate action."""
        llm = MockLLM()
        skill = load_skill(self.skill_file, self.temp_dir)
        index = SkillIndex([skill], vectors=None)
        help_engine = HelpEngine(index, None)
        session = Session("test_session")

        runtime = Runtime(
            llm=llm,
            help_engine=help_engine,
            session=session,
            atomic_llm=llm,
            use_streaming=False,
            delegate_terminal="in_process",
        )

        action = {
            "name": "delegate",
            "body": "Analyze Acme NDA for non-compete clauses",
            "attrs": {"agent": "nda_review"},
        }

        skill.path = "legal/nda-review.md"

        import unittest.mock
        with unittest.mock.patch("core.runtime.Path") as mock_path:
            mock_path.return_value = self.claude_file
            mock_path.exists.return_value = True
            result = runtime._execute_action(action)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("content"), "Mock sub-agent response")

    def test_delegate_rejects_prompt_stub(self):
        llm = MockLLM()
        skill = load_skill(self.skill_file, self.temp_dir)
        runtime = Runtime(
            llm=llm,
            help_engine=HelpEngine(SkillIndex([skill], vectors=None), None),
            session=Session("test"),
            atomic_llm=llm,
            use_streaming=False,
        )
        result = runtime._execute_action({
            "name": "delegate",
            "body": DELEGATE_EXAMPLE_STUB,
            "attrs": {"agent": "nda_review"},
        })
        self.assertIn("error", result)
        self.assertIn("complete problem statement", result["error"])


if __name__ == "__main__":
    unittest.main()
