"""Regression: untrusted tool/event text must not crash Rich markup parsing."""

from __future__ import annotations

import io
import unittest

from rich.console import Console
from rich.errors import MarkupError

import core.display as display


class TestDisplayMarkupEscape(unittest.TestCase):
    def setUp(self):
        if not display._RICH:
            self.skipTest("rich not installed")
        self._buf = io.StringIO()
        self._old = display._console
        display._console = Console(
            file=self._buf,
            force_terminal=True,
            highlight=False,
            soft_wrap=True,
            width=120,
        )

    def tearDown(self):
        if getattr(self, "_old", None) is not None:
            display._console = self._old

    def test_print_result_hostile_markup(self):
        payloads = [
            "closing [/] tag",
            "has [dim] inside",
            "unclosed [unclosed",
            "List[str] and Dict[str, Any]",
        ]
        for text in payloads:
            with self.subTest(text=text):
                try:
                    display.print_result("grep", text, is_error=True)
                except MarkupError as e:
                    self.fail(f"print_result raised MarkupError on {text!r}: {e}")

    def test_print_event_hostile_markup(self):
        payloads = [
            "LLM error: unexpected [/] in body",
            "warn [dim]foo[/dim]",
            "broken [unclosed tag",
        ]
        for text in payloads:
            with self.subTest(text=text):
                try:
                    display.print_event("error", text)
                except MarkupError as e:
                    self.fail(f"print_event raised MarkupError on {text!r}: {e}")

    def test_print_result_python_traceback_still_renders(self):
        text = "Traceback (most recent call last):\n  File \"x.py\", line 1\nValueError: boom [/]"
        try:
            display.print_result("python", text, is_error=True)
        except MarkupError as e:
            self.fail(f"traceback branch raised MarkupError: {e}")


if __name__ == "__main__":
    unittest.main()
