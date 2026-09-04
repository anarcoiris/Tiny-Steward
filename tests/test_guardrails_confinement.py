"""Unit tests for workspace sandboxing, skill immutability lock, and rethink introspection guardrails."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core import primitives
from core.runtime import Runtime


class TestGuardrailsConfinement(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ws_dir = self.temp_dir / "workspace"
        self.ws_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir = self.ws_dir / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.foreign_dir = self.temp_dir / "foreign_project"
        self.foreign_dir.mkdir(parents=True, exist_ok=True)

        self.old_ws = primitives.get_workspace_dir()
        primitives.set_workspace_dir(self.ws_dir)
        primitives.set_allow_skill_mutation(False)

    def tearDown(self):
        primitives.set_workspace_dir(self.old_ws)
        primitives.set_allow_skill_mutation(False)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_g1_blocks_write_outside_workspace(self):
        foreign_file = self.foreign_dir / "test.txt"
        res = primitives.write(str(foreign_file), "malicious or leaked content")
        self.assertIn("error", res)
        self.assertIn("Workspace Isolation Error", res["error"])
        self.assertFalse(foreign_file.exists())

    def test_g1_blocks_mkdir_outside_workspace(self):
        foreign_subdir = self.foreign_dir / "subfolder"
        res = primitives.mkdir(str(foreign_subdir))
        self.assertIn("error", res)
        self.assertIn("Workspace Isolation Error", res["error"])
        self.assertFalse(foreign_subdir.exists())

    def test_g2_blocks_mutating_skills_by_default(self):
        skill_file = self.skills_dir / "test_skill.py"
        # Initial write should be blocked by skill lock
        res = primitives.write(str(skill_file), "def broken(): pass")
        self.assertIn("error", res)
        self.assertIn("Skill Immutability Lock", res["error"])
        self.assertFalse(skill_file.exists())

    def test_g2_allows_skill_mutation_when_explicitly_unlocked(self):
        primitives.set_allow_skill_mutation(True)
        skill_file = self.skills_dir / "test_skill.py"
        res = primitives.write(str(skill_file), "def working(): pass")
        self.assertNotIn("error", res)
        self.assertTrue(skill_file.exists())

    def test_g4_rethink_nudge_introspects_signature_mismatch(self):
        llm = MagicMock()
        llm.chat = MagicMock(return_value="I will inspect the API")
        mock_session = MagicMock()
        mock_session.name = "test_guard"
        mock_session.metadata = {}
        mock_session.messages = []
        rt = Runtime(llm=llm, help_engine=MagicMock(), session=mock_session, invariants={"os": "windows"})
        rt.use_streaming = False

        messages = [{"role": "system", "content": "system"}]
        # Simulate action error with TypeError unexpected keyword
        rt._handle_rethink_loop(
            messages=messages,
            tools=[],
            actions=[{"name": "python", "code": "foo()"}],
            errors=["TypeError: func() got an unexpected keyword argument 'ncontext'"],
        )

        # Check that the rethink prompt sent to llm.chat contained SIGNATURE MISMATCH guidance
        first_call_messages = llm.chat.call_args_list[0][0][0]
        nudge_content = first_call_messages[-2]["content"]
        self.assertIn("SIGNATURE MISMATCH", nudge_content)
        self.assertIn("Do NOT guess parameter names", nudge_content)


if __name__ == "__main__":
    unittest.main()
