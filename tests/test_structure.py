"""Automated structural regression tests for Runtime mixins & display contracts."""

from __future__ import annotations

import ast
import glob
import unittest
from pathlib import Path

import core.display as display
from core.runtime import Runtime


class TestStructureContracts(unittest.TestCase):
    def test_all_display_calls_exist(self):
        """Ensure all display.* calls across core/ exist in core.display."""
        display_attrs = set(dir(display))
        missing_display_calls = set()

        for file_path in glob.glob("core/*.py"):
            text = Path(file_path).read_text(encoding="utf-8")
            tree = ast.parse(text, filename=file_path)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "display"
                ):
                    if node.attr not in display_attrs:
                        missing_display_calls.add((file_path, node.lineno, node.attr))

        self.assertEqual(
            missing_display_calls,
            set(),
            f"Found missing display.* calls: {missing_display_calls}",
        )

    def test_all_runtime_self_calls_exist(self):
        """Ensure all self.xyz calls & accesses across core/runtime_*.py exist on Runtime."""
        rt = Runtime(llm=None, help_engine=None, session=None)
        rt_attrs = set(dir(rt))

        missing_methods = set()
        missing_attrs = set()

        for file_path in [
            "core/runtime.py",
            "core/runtime_execution.py",
            "core/runtime_compaction.py",
            "core/runtime_meta.py",
            "core/runtime_delegate.py",
            "core/runtime_loop.py",
        ]:
            text = Path(file_path).read_text(encoding="utf-8")
            tree = ast.parse(text, filename=file_path)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "self"
                ):
                    if node.attr not in rt_attrs:
                        missing_attrs.add((file_path, node.lineno, node.attr))
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self"
                ):
                    if node.func.attr not in rt_attrs:
                        missing_methods.add((file_path, node.lineno, node.func.attr))

        self.assertEqual(
            missing_methods,
            set(),
            f"Found missing method calls on self: {missing_methods}",
        )
        self.assertEqual(
            missing_attrs,
            set(),
            f"Found missing attribute accesses on self: {missing_attrs}",
        )


if __name__ == "__main__":
    unittest.main()
