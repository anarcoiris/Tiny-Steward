"""Tests for Sycophancy mitigation and Empirical Precedence in RuntimeLoopMixin."""

import unittest
from unittest.mock import MagicMock
from core.runtime_loop import RuntimeLoopMixin


class DummyRuntime(RuntimeLoopMixin):
    def __init__(self):
        self.session = MagicMock()
        self.session_stats = MagicMock()
        self.use_streaming = False


class TestRuntimeLoopSycophancy(unittest.TestCase):
    def setUp(self):
        self.rt = DummyRuntime()

    def test_has_recent_verification_true_when_tool_output_present(self):
        messages = [
            {"role": "user", "content": "Run tests"},
            {"role": "assistant", "content": "Executing pytest"},
            {"role": "tool", "name": "pwsh", "content": "=== 3 passed in 0.05s ==="},
        ]
        self.assertTrue(self.rt._has_recent_verification(messages))

    def test_has_recent_verification_false_when_no_tool(self):
        messages = [
            {"role": "user", "content": "Fix the bug"},
            {"role": "assistant", "content": "I have fixed it."},
        ]
        self.assertFalse(self.rt._has_recent_verification(messages))

    def test_has_recent_verification_false_on_execution_error_only(self):
        messages = [
            {"role": "user", "content": "Run command"},
            {"role": "tool", "name": "pwsh", "content": "[Execution Error: command not found]"},
        ]
        self.assertFalse(self.rt._has_recent_verification(messages))

    def test_detect_unverified_completion_detects_sycophancy(self):
        # Empty or purely conversational history without verification
        messages = [
            {"role": "user", "content": "Please resolve the issue."},
            {"role": "assistant", "content": "Sure, working on it."},
        ]
        # Response claiming success / DONE without prior tool output
        self.assertTrue(self.rt._detect_unverified_completion("Everything is fixed! DONE", messages))
        self.assertTrue(self.rt._detect_unverified_completion("El problema ha sido solucionado por completo.", messages))
        self.assertTrue(self.rt._detect_unverified_completion("All tests pass now.", messages))

    def test_detect_unverified_completion_false_when_verified(self):
        messages = [
            {"role": "user", "content": "Please resolve the issue."},
            {"role": "tool", "name": "pwsh", "content": "Ran 5 tests: 5 OK"},
        ]
        self.assertFalse(self.rt._detect_unverified_completion("Verified with tests. DONE", messages))


if __name__ == "__main__":
    unittest.main()
