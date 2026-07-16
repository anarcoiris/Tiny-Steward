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

    def test_blocking_before_priority(self):
        self.box.send(from_session="a", content="urgent", priority="urgent", blocking=False)
        self.box.send(from_session="b", content="block", priority="low", blocking=True)
        msgs = self.box.drain()
        self.assertEqual(msgs[0]["content"], "block")
        self.assertEqual(msgs[1]["content"], "urgent")

    def test_skip_delegate_result(self):
        self.box.send(
            from_session="child",
            content="done",
            msg_type="delegate_result",
            priority="high",
        )
        self.box.send(from_session="user", content="hi", msg_type="supervision_question")
        msgs = self.box.drain(skip_types={"delegate_result"})
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["content"], "hi")
        left = self.box.peek()
        self.assertEqual(len(left), 1)
        self.assertEqual(left[0]["type"], "delegate_result")

    def test_corrupt_json_quarantined(self):
        bad = self.box.inbox / "1-bad.json"
        bad.write_text("{not json", encoding="utf-8")
        msgs = self.box.drain()
        self.assertEqual(msgs, [])
        self.assertFalse(bad.exists())
        quarantined = list(self.box.inbox.glob("*.corrupt_json"))
        self.assertEqual(len(quarantined), 1)


if __name__ == "__main__":
    unittest.main()
