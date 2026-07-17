"""Unit tests for Session and SessionManager.

Tests that session loading forces the session name to match the requested session name
(aligning filename and internal session name) and saves to the correct path.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.session import Session, SessionManager


class TestSessionManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.session_mgr = SessionManager(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_new_session(self):
        """Test that new() creates a session with the correct name and saves it."""
        session = self.session_mgr.new("test_session")
        self.assertEqual(session.name, "test_session")
        self.assertEqual(self.session_mgr.current, session)

        expected_path = self.temp_dir / "test_session.json"
        self.assertTrue(expected_path.exists())

        # Load raw file and check name
        data = json.loads(expected_path.read_text(encoding="utf-8"))
        self.assertEqual(data["name"], "test_session")

    def test_load_session_forces_name_alignment(self):
        """Test that load() forces the session name to align with the loaded name."""
        # Create a file on disk manually where the internal name differs from the filename
        mismatched_path = self.temp_dir / "mismatched.json"
        mismatched_data = {
            "name": "internal_old_name",
            "messages": [{"role": "user", "content": "hello"}],
            "discovered_skills": [],
            "metadata": {}
        }
        mismatched_path.write_text(json.dumps(mismatched_data), encoding="utf-8")

        # Load "mismatched" via SessionManager
        session = self.session_mgr.load("mismatched")
        # The internal name should be forced to "mismatched"
        self.assertEqual(session.name, "mismatched")
        self.assertEqual(self.session_mgr.current.name, "mismatched")

        # Now save it and verify it writes back to mismatched.json, not internal_old_name.json
        self.session_mgr.save()
        
        self.assertTrue((self.temp_dir / "mismatched.json").exists())
        self.assertFalse((self.temp_dir / "internal_old_name.json").exists())

        # Check that saved file contains the correct aligned name
        saved_data = json.loads(mismatched_path.read_text(encoding="utf-8"))
        self.assertEqual(saved_data["name"], "mismatched")

    def test_list_sessions_includes_orch_id_slot(self):
        session = self.session_mgr.new("pinned")
        session.metadata["orch_id_slot"] = 0
        session.metadata["parent"] = None
        self.session_mgr.save()
        listed = self.session_mgr.list_sessions()
        by_name = {s["name"]: s for s in listed}
        self.assertIn("pinned", by_name)
        self.assertEqual(by_name["pinned"]["orch_id_slot"], 0)

    def test_list_tree_roots_with_children(self):
        parent = self.session_mgr.new("parent")
        parent.metadata["orch_id_slot"] = 0
        self.session_mgr.save()
        child = self.session_mgr.new("child")
        child.metadata["parent"] = "parent"
        self.session_mgr.save()
        self.session_mgr.register_child("parent", "child")
        roots = self.session_mgr.list_tree()
        root_names = {r["name"] for r in roots}
        self.assertIn("parent", root_names)
        self.assertNotIn("child", root_names)
        parent_row = next(r for r in self.session_mgr.list_sessions() if r["name"] == "parent")
        self.assertIn("child", parent_row["children"])
        self.assertEqual(parent_row["orch_id_slot"], 0)


if __name__ == "__main__":
    unittest.main()
