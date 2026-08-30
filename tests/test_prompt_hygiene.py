"""Tests for prompt hygiene (REPL chrome detection / scrub / empty assistant)."""

from __future__ import annotations

import unittest

from core.prompt_hygiene import (
    EMPTY_ASSISTANT_PLACEHOLDER,
    is_chrome_only,
    looks_like_repl_chrome,
    scrub_chrome,
    should_block_paste,
    think_content_preview,
)
from core.runtime import normalize_messages_for_llm


CHROME_SAMPLE = """
──────── Tiny Steward — Semantic Capability Graph ────────
  Session: inspect-and-supervise   │   Skills: 2784
  you › /set enable_thinking true
  ⚠  KV prefix may invalidate — chat_template_kwargs changed mid-session
  steward │
<think>
planning
</think>
  turn 1  │  ~622 prompt  │  ~99 completion  │  3 tok/s  │  ░░░░░░░░░░ 0%  │  26.6s  │  LCP 0+1862 (0%)
  ⚡  Generation slowed to 3.7 tok/s — model may be memory-pressured
PS C:\\Users\\soyko\\Documents\\tiny_steward>
"""


class TestPromptHygiene(unittest.TestCase):
    def test_detects_repl_chrome(self):
        self.assertTrue(looks_like_repl_chrome(CHROME_SAMPLE))
        self.assertTrue(should_block_paste(CHROME_SAMPLE))

    def test_short_clean_message_ok(self):
        msg = "Please ls plans/ and read fuera-de-alcance.md"
        self.assertFalse(should_block_paste(msg))
        self.assertFalse(looks_like_repl_chrome(msg))

    def test_scrub_removes_stats_lines(self):
        cleaned = scrub_chrome(CHROME_SAMPLE)
        self.assertNotIn("LCP 0+1862", cleaned)
        self.assertNotIn("tok/s", cleaned)

    def test_chrome_only_preview_blank(self):
        preview = (
            "turn 5  │  ~622 prompt  │  ~100 completion  │  3 tok/s  │  ░░░░░░░░░░ 0%  │  "
            "148.6s  │  LCP 0+1862 (0%)\n  ⚡  Generation slowed to 3.7 tok/s"
        )
        self.assertTrue(is_chrome_only(preview) or looks_like_repl_chrome(preview))
        self.assertEqual(think_content_preview(preview), "")

    def test_empty_assistant_placeholder(self):
        messages = [
            {
                "role": "assistant",
                "content": "<think>\nonly reasoning\n</think>",
                "reasoning_content": "only reasoning",
            },
        ]
        out = normalize_messages_for_llm(messages, preserve_thinking=False)
        self.assertEqual(out[0]["content"], EMPTY_ASSISTANT_PLACEHOLDER)

    def test_normalize_scrubs_user_chrome(self):
        messages = [{"role": "user", "content": CHROME_SAMPLE}]
        out = normalize_messages_for_llm(messages)
        self.assertNotIn("LCP 0+1862", out[0]["content"])


if __name__ == "__main__":
    unittest.main()
