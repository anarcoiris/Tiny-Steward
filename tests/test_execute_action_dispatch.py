"""Tests for _execute_action dispatch of path-based primitives."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.help import HelpEngine
from core.llm import LLMClient
from core.runtime import Runtime
from core.session import Session
from core.skill_loader import Skill, SkillIndex


class MockLLM(LLMClient):
    def __init__(self):
        super().__init__(base_url="http://mock", model="mock")

    def chat(self, messages, *, max_tokens=None, temperature=None, tools=None) -> str:
        return "ok"

    def health(self) -> bool:
        return True


class TestExecuteActionDispatch(unittest.TestCase):
    def setUp(self):
        skill = Skill(name="t", slug="t", path="t.md", skill_type="skill")
        index = SkillIndex([skill], vectors=None)
        self.runtime = Runtime(
            llm=MockLLM(),
            help_engine=HelpEngine(index, None),
            session=Session("test"),
            use_streaming=False,
        )
        self.temp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_ls_uses_attrs_path(self):
        target = self.temp / "subdir"
        target.mkdir()
        (target / "a.txt").write_text("x", encoding="utf-8")
        result = self.runtime._execute_action({
            "name": "ls",
            "body": "",
            "attrs": {"path": str(target)},
        })
        self.assertNotIn("error", result)
        self.assertIn("a.txt", result["content"])

    def test_mkdir_uses_attrs_path(self):
        target = self.temp / "newdir"
        result = self.runtime._execute_action({
            "name": "mkdir",
            "body": "",
            "attrs": {"path": str(target)},
        })
        self.assertNotIn("error", result)
        self.assertTrue(target.is_dir())

    def test_ls_malformed_body_still_fails(self):
        result = self.runtime._execute_action({
            "name": "ls",
            "body": 'path="skills/_policy" cwd="skills">',
            "attrs": {},
        })
        self.assertIn("error", result)
        self.assertTrue(
            result["error"].startswith("Path not found:")
            or result["error"].startswith("Not a directory:")
        )

    def test_ls_missing_path_message(self):
        missing = self.temp / "does_not_exist"
        result = self.runtime._execute_action({
            "name": "ls",
            "body": "",
            "attrs": {"path": str(missing)},
        })
        self.assertIn("error", result)
        self.assertTrue(result["error"].startswith("Path not found:"))

    def test_ls_file_not_directory_message(self):
        f = self.temp / "file.txt"
        f.write_text("hi", encoding="utf-8")
        result = self.runtime._execute_action({
            "name": "ls",
            "body": "",
            "attrs": {"path": str(f)},
        })
        self.assertIn("error", result)
        self.assertTrue(result["error"].startswith("Not a directory:"))

    def test_write_uses_attrs_path(self):
        target = self.temp / "out.txt"
        result = self.runtime._execute_action({
            "name": "write",
            "body": "payload",
            "attrs": {"path": str(target)},
        })
        self.assertNotIn("error", result)
        self.assertEqual(target.read_text(encoding="utf-8"), "payload")

    def test_write_missing_path_errors(self):
        result = self.runtime._execute_action({
            "name": "write",
            "body": "payload",
            "attrs": {},
        })
        self.assertIn("error", result)
        self.assertIn("Missing path", result["error"])

    def test_benign_fs_error_does_not_force_tools_resend(self):
        missing = self.temp / "nope"
        messages: list = []
        response = (
            '<tool_call>\n'
            f'{{"name": "ls", "arguments": {{"path": "{missing.as_posix()}"}}}}\n'
            '</tool_call>'
        )
        # Escape Windows backslashes for JSON in response — use forward path already
        self.runtime._process_response_actions(response, messages, backend="primary")
        self.assertFalse(
            self.runtime.session.metadata.get("force_tools_payload_primary_next", False)
        )


if __name__ == "__main__":
    unittest.main()
