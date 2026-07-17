"""Smoke tests for filesystem and shell primitives (no LLM)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from core import primitives


class TestPrimitivesSmoke(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_mkdir_write_read_ls(self):
        sub = self.temp / "nested"
        r = primitives.mkdir(str(sub))
        self.assertNotIn("error", r)

        target = sub / "note.txt"
        r = primitives.write(str(target), "hello_world")
        self.assertNotIn("error", r)

        r = primitives.read(str(target))
        self.assertNotIn("error", r)
        self.assertIn("hello_world", r["content"])

        r = primitives.ls(str(sub))
        self.assertNotIn("error", r)
        self.assertIn("note.txt", r["content"])

    def test_pwsh_ok(self):
        r = primitives.pwsh("Write-Output 'ok'")
        self.assertNotIn("error", r)
        self.assertEqual(r.get("exit_code", 1), 0)
        self.assertIn("ok", r.get("content", "") + r.get("stdout", ""))

    def test_python_unicode_emoji(self):
        r = primitives.python('print("hello_world 🎉 ñ")')
        self.assertNotIn("error", r)
        self.assertEqual(r.get("exit_code", 1), 0)
        out = r.get("content", "") or r.get("stdout", "")
        self.assertIn("hello_world", out)
        self.assertIn("ñ", out)

    def test_grep_rejects_multi_path(self):
        r = primitives.grep("foo", "./ ./skills/ ./core/")
        self.assertIn("error", r)
        self.assertIn("single path", r["error"])

    def test_grep_single_file(self):
        target = self.temp / "a.txt"
        target.write_text("hello findme world", encoding="utf-8")
        r = primitives.grep("findme", str(target))
        self.assertNotIn("error", r)
        self.assertIn("findme", r["content"])


if __name__ == "__main__":
    unittest.main()
