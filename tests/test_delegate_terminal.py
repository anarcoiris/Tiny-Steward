"""Tests for delegate_terminal mode resolution."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

from core.delegate_terminal import resolve_terminal_mode, build_child_argv
from pathlib import Path


class TestDelegateTerminal(unittest.TestCase):
    def test_explicit_in_process(self):
        self.assertEqual(resolve_terminal_mode("in_process"), "in_process")

    def test_auto_windows_without_wt(self):
        with patch("sys.platform", "win32"), patch("core.delegate_terminal.shutil.which", return_value=None):
            self.assertEqual(resolve_terminal_mode("auto"), "console")

    def test_auto_unix_tmux(self):
        with patch("sys.platform", "linux"), patch.dict(os.environ, {"TMUX": "/tmp/tmux-0"}, clear=False):
            self.assertEqual(resolve_terminal_mode("auto"), "tmux")

    def test_build_child_argv(self):
        argv = build_child_argv(
            python="python",
            steward_path=Path("steward.py"),
            config="config.yaml",
            session="child1",
            parent="root",
            skill="nda_review",
            problem="do it",
        )
        self.assertIn("--delegate-mode", argv)
        self.assertIn("--parent", argv)
        self.assertIn("root", argv)
        self.assertIn("--delegate-skill", argv)
        self.assertIn("nda_review", argv)


if __name__ == "__main__":
    unittest.main()
