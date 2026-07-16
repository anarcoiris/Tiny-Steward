"""Tests for maildir-style session mailbox."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.mailbox import Mailbox


class TestMailbox(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.box = Mailbox(self.temp, "root")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_send_and_drain(self):
        self.box.send(from_session="root", content="hello", priority="high")
        self.box.send(from_session="child", content="later", priority="low")
        msgs = self.box.drain()
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["priority"], "high")
        self.assertEqual(msgs[0]["content"], "hello")
        self.assertEqual(len(self.box.peek()), 0)

    def test_priority_order(self):
        self.box.send(from_session="a", content="n", priority="normal")
        self.box.send(from_session="b", content="u", priority="urgent")
        msgs = self.box.drain()
        self.assertEqual(msgs[0]["content"], "u")
        self.assertEqual(msgs[1]["content"], "n")


if __name__ == "__main__":
    unittest.main()
