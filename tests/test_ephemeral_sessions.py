"""Unit tests for Ephemeral Sandbox Sessions with clean cache."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.session import SessionManager


class TestEphemeralSessions(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mgr = SessionManager(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_isolate_ephemeral_session(self):
        parent_sess = self.mgr.new("parent_work")
        parent_sess.add_message("user", "Previous contaminated history")
        self.mgr.save()

        # Create ephemeral sandbox session
        eph = self.mgr.new_ephemeral(parent="parent_work", task_label="recon_background")
        self.assertTrue(eph.name.startswith("eph_"))
        self.assertTrue(eph.metadata.get("is_ephemeral"))
        self.assertEqual(eph.metadata.get("parent"), "parent_work")
        # Ensure zero carryover
        self.assertEqual(len(eph.messages), 0)

        # List ephemeral sessions
        eph_list = self.mgr.list_ephemeral()
        self.assertEqual(len(eph_list), 1)
        self.assertEqual(eph_list[0]["name"], eph.name)

        # Cleanup ephemeral session
        cleaned = self.mgr.cleanup_ephemeral(eph.name)
        self.assertTrue(cleaned)
        self.assertEqual(len(self.mgr.list_ephemeral()), 0)


if __name__ == "__main__":
    unittest.main()
