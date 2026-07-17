"""Tests for LLM message normalization (legacy results + think pruning)."""

from __future__ import annotations

import unittest

from core.runtime import normalize_messages_for_llm, strip_think_from_text


class TestMessageNormalization(unittest.TestCase):
    def test_legacy_result_to_tool_role(self):
        messages = [
            {"role": "user", "content": "[Result of read]\nfile contents here"},
        ]
        out = normalize_messages_for_llm(messages)
        self.assertEqual(out[0]["role"], "tool")
        self.assertEqual(out[0]["name"], "read")
        self.assertEqual(out[0]["content"], "file contents here")

    def test_strip_think_from_assistant(self):
        messages = [
            {
                "role": "assistant",
                "content": "<think>\nreasoning\n</think>\n\nHello",
            },
        ]
        out = normalize_messages_for_llm(messages)
        self.assertNotIn("<think>", out[0]["content"])
        self.assertIn("Hello", out[0]["content"])

    def test_drops_reasoning_content_field(self):
        messages = [
            {
                "role": "assistant",
                "content": "Hello",
                "reasoning_content": "hidden",
            },
        ]
        out = normalize_messages_for_llm(messages)
        self.assertNotIn("reasoning_content", out[0])
        kept = normalize_messages_for_llm(messages, preserve_thinking=True)
        self.assertEqual(kept[0]["reasoning_content"], "hidden")

    def test_strip_think_from_text_helper(self):
        text = "<think>secret</think>\nvisible"
        self.assertEqual(strip_think_from_text(text), "visible")

    def test_regular_user_message_unchanged(self):
        messages = [{"role": "user", "content": "list files in core/"}]
        out = normalize_messages_for_llm(messages)
        self.assertEqual(out[0]["role"], "user")
        self.assertEqual(out[0]["content"], "list files in core/")

    def test_think_only_becomes_placeholder(self):
        from core.prompt_hygiene import EMPTY_ASSISTANT_PLACEHOLDER

        messages = [
            {"role": "assistant", "content": "<think>\nx\n</think>"},
        ]
        out = normalize_messages_for_llm(messages)
        self.assertEqual(out[0]["content"], EMPTY_ASSISTANT_PLACEHOLDER)


if __name__ == "__main__":
    unittest.main()
