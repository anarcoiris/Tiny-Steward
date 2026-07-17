"""Tests for /attach and @path transcript injection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.help import HelpEngine
from core.llm import LLMClient
from core.runtime import Runtime, ATTACH_MAX_CHARS
from core.session import Session
from core.skill_loader import Skill, SkillIndex


class TestAttach(unittest.TestCase):
    def setUp(self):
        skill = Skill(name="t", slug="t", path="t.md", skill_type="skill")
        self.rt = Runtime(
            llm=LLMClient(base_url="http://mock", model="m"),
            help_engine=HelpEngine(SkillIndex([skill], vectors=None), None),
            session=Session("attach-test"),
            use_streaming=False,
            rules_enabled=False,
        )
        self.temp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_read_attachment_cap(self):
        f = self.temp / "big.txt"
        f.write_text("x" * (ATTACH_MAX_CHARS + 100), encoding="utf-8")
        text, err = self.rt._read_attachment(str(f))
        self.assertIsNone(err)
        self.assertIn("truncated", text)
        self.assertLessEqual(len(text), ATTACH_MAX_CHARS + 200)

    def test_expand_quoted_at_path(self):
        f = self.temp / "note.md"
        f.write_text("hello attach", encoding="utf-8")
        out, notes, refs = self.rt._expand_at_attachments(f'Review @"{f}" please')
        self.assertIn("hello attach", out)
        self.assertEqual(refs, [])
        self.assertTrue(any("Expanded" in n for n in notes))

    def test_email_not_expanded(self):
        out, notes, refs = self.rt._expand_at_attachments("mail user@example.com thanks")
        self.assertEqual(out, "mail user@example.com thanks")
        self.assertEqual(notes, [])
        self.assertEqual(refs, [])


if __name__ == "__main__":
    unittest.main()
