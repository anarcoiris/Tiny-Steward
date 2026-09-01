"""Unit tests ensuring compacted messages always maintain a valid user query and valid message sequencing for Jinja templates."""

from __future__ import annotations

import unittest
from core.runtime_compaction import RuntimeCompactionMixin
from core.session import Session


class FakeRuntime(RuntimeCompactionMixin):
    def __init__(self):
        self.session = Session("test_sess")
        self.session_stats = None


class TestCompactionUserQuery(unittest.TestCase):

    def test_compact_preserves_user_query_when_recent_are_all_tool_turns(self):
        rt = FakeRuntime()
        messages = [
            {"role": "system", "content": "You are Tiny Steward."},
            {"role": "user", "content": "Original user goal: solve physics problem"},
        ]
        # Simulate 15 tool/assistant iterations in rethink loop
        for i in range(15):
            messages.append({"role": "assistant", "content": f"<tool_call>step {i}</tool_call>"})
            messages.append({"role": "tool", "name": "pwsh", "content": f"output {i}"})

        compacted = rt._compact_messages(messages)

        # Invariants:
        # 1. First message must be system
        self.assertEqual(compacted[0]["role"], "system")
        # 2. Second message MUST be user (to satisfy Jinja template requirement: No user query found)
        self.assertEqual(compacted[1]["role"], "user")
        self.assertIn("solve physics problem", compacted[1]["content"])
        # 3. There must be at least one user message
        self.assertTrue(any(m["role"] == "user" for m in compacted))
        # 4. No orphaned tool message at the start
        self.assertNotEqual(compacted[1]["role"], "tool")

    def test_compact_synthesizes_user_query_if_none_existed(self):
        rt = FakeRuntime()
        messages = [
            {"role": "system", "content": "You are Tiny Steward."},
        ]
        for i in range(12):
            messages.append({"role": "assistant", "content": f"action {i}"})
            messages.append({"role": "tool", "name": "pwsh", "content": f"res {i}"})

        compacted = rt._compact_messages(messages)
        self.assertEqual(compacted[0]["role"], "system")
        self.assertEqual(compacted[1]["role"], "user")
        self.assertTrue(any(m["role"] == "user" for m in compacted))


if __name__ == "__main__":
    unittest.main()
