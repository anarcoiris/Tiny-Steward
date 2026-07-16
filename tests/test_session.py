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


if __name__ == "__main__":
    unittest.main()
