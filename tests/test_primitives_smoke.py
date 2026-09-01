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

    def test_replace_ok(self):
        target = self.temp / "sample.py"
        target.write_text("def foo():\n    print('bad')\n", encoding="utf-8")
        r = primitives.replace(str(target), "print('bad')", "print('good')")
        self.assertNotIn("error", r)
        self.assertIn("Successfully replaced", r["content"])
        self.assertEqual(target.read_text(encoding="utf-8"), "def foo():\n    print('good')\n")

    def test_replace_target_not_found(self):
        target = self.temp / "sample2.py"
        target.write_text("x = 1\n", encoding="utf-8")
        r = primitives.replace(str(target), "nonexistent", "new")
        self.assertIn("error", r)
        self.assertIn("Target string not found", r["error"])

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

    def test_workspace_isolation(self):
        ws = self.temp / "sandbox"
        old_ws = primitives.get_workspace_dir()
        try:
            primitives.set_workspace_dir(ws)
            self.assertEqual(primitives.get_workspace_dir(), ws.resolve())

            # Relative write should go into sandbox
            res = primitives.write("isolated.txt", "content_in_sandbox")
            self.assertNotIn("error", res)
            self.assertTrue((ws / "isolated.txt").exists())

            # Relative read should read from sandbox
            res_read = primitives.read("isolated.txt")
            self.assertIn("content_in_sandbox", res_read.get("content", ""))

            # Relative ls should list sandbox
            res_ls = primitives.ls(".")
            self.assertIn("isolated.txt", res_ls.get("content", ""))
        finally:
            primitives.set_workspace_dir(old_ws)


if __name__ == "__main__":
    unittest.main()
