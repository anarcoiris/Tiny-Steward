"""Tests for task.md preservation and cap in context compaction."""

import unittest
from unittest.mock import MagicMock
from core.runtime import Runtime


class TestCompactionTaskPreservation(unittest.TestCase):
    def test_compact_messages_preserves_large_task_plan(self):
        llm = MagicMock()
        help_engine = MagicMock()
        session = MagicMock()
        session.name = "test_compact_task"
        session.metadata = {}
        session.messages = []

        rt = Runtime(
            llm=llm,
            help_engine=help_engine,
            session=session,
            invariants={"os": "windows"},
        )
        rt._rules_text = "Global rules"

        large_task = "# Big Task\n" + ("- [ ] Step item with detailed info\n" * 40)
        self.assertTrue(len(large_task) > 1000)
        self.assertTrue(len(large_task) <= 2500)

        rt._get_active_task_text = MagicMock(return_value=("sessions/test/task.md", large_task))

        # Build message history that exceeds compaction window
        messages = [{"role": "system", "content": "System prompt"}]
        for i in range(30):
            messages.append({"role": "user", "content": f"Turn query {i}"})
            messages.append({"role": "assistant", "content": f"Turn response {i}"})

        compacted = rt._compact_messages(messages)
        self.assertTrue(len(compacted) < len(messages))
        system_msg = compacted[0]
        self.assertEqual(system_msg["role"], "system")
        self.assertIn("[Active Task Plan (sessions/test/task.md)]", system_msg["content"])
        self.assertIn("Step item with detailed info", system_msg["content"])


if __name__ == "__main__":
    unittest.main()
