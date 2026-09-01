"""Unit tests for workspace isolation, ubiquitous resolution, and session metadata."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.primitives import set_workspace_dir, get_workspace_dir, resolve_path
from core.session import Session, SessionManager
from core.system_prompt import compose_system_prompt, format_os_invariants
from core.runtime import Runtime


class TestWorkspaceIsolation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ws_dir = self.temp_dir / "workspace_test"
        self.ws_dir.mkdir(parents=True, exist_ok=True)
        set_workspace_dir(self.ws_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_primitives_workspace_dir(self):
        self.assertEqual(get_workspace_dir(), self.ws_dir.resolve())
        p = resolve_path("sub/file.txt")
        self.assertEqual(p, (self.ws_dir / "sub/file.txt").resolve())

    def test_session_metadata_workspace_persistence(self):
        sess_dir = self.temp_dir / "sessions"
        mgr = SessionManager(sess_dir)
        sess = mgr.new("ws_session")
        self.assertEqual(sess.metadata.get("workspace"), str(self.ws_dir.resolve()))
        self.assertEqual(sess.metadata.get("turn_count"), 0)

        sess.add_message("user", "test input")
        sess.add_message("assistant", "test output")
        mgr.save()

        # Reload session and check metadata
        loaded = mgr.load("ws_session")
        self.assertEqual(loaded.metadata.get("workspace"), str(self.ws_dir.resolve()))
        self.assertEqual(loaded.metadata.get("turn_count"), 2)

    def test_system_prompt_workspace_injection(self):
        prompt = compose_system_prompt(
            rules_text="rule 1",
            invariants={"os": "windows", "shell": "powershell"},
            workspace_dir=str(self.ws_dir.resolve()),
        )
        self.assertIn("Active Workspace Directory", prompt)
        self.assertIn(str(self.ws_dir.resolve()), prompt)

    def test_active_task_text_isolation(self):
        sess_dir = self.temp_dir / "sessions"
        mgr = SessionManager(sess_dir)
        sess = mgr.new("custom_project")

        # Fake runtime minimal mock
        class FakeRuntime:
            session = sess
            session_manager = mgr
            _get_active_task_text = Runtime._get_active_task_text

        rt = FakeRuntime()
        # When no task.md exists, should return empty, not fall back to ejercicios/task.md
        path_str, content = rt._get_active_task_text()
        self.assertEqual(path_str, "")
        self.assertEqual(content, "")

        # When task.md is created in the workspace
        task_file = self.ws_dir / "task.md"
        task_file.write_text("# My Isolated Task", encoding="utf-8")

        path_str, content = rt._get_active_task_text()
        self.assertIn("task.md", path_str)
        self.assertEqual(content, "# My Isolated Task")


if __name__ == "__main__":
    unittest.main()
