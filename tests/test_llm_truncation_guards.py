"""Unit tests for LLM truncation guards, normalized done_reason, and CoT tool rescue."""

from __future__ import annotations

import unittest
from core.action_parse import parse_llm_result
from core.llm import normalize_done_reason


class TestLLMTruncationGuards(unittest.TestCase):
    def test_normalize_done_reason(self):
        self.assertEqual(normalize_done_reason("stop"), "stop")
        self.assertEqual(normalize_done_reason("STOP_SEQUENCE"), "stop")
        self.assertEqual(normalize_done_reason("length"), "length")
        self.assertEqual(normalize_done_reason("max_tokens"), "length")
        self.assertEqual(normalize_done_reason("context_length_exceeded"), "length")
        self.assertEqual(normalize_done_reason("tool_calls"), "tool_calls")
        self.assertEqual(normalize_done_reason("content_filter"), "content_filter")
        self.assertEqual(normalize_done_reason("repetition_loop"), "abort")
        self.assertEqual(normalize_done_reason(None), "stop")

    def test_parse_llm_result_from_content(self):
        content = '<tool_call>\n<function=read>\n<parameter=path>\nconfig.yaml\n</parameter>\n</function>\n</tool_call>'
        actions, source = parse_llm_result(content, thinking="I should read config.yaml")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "read")
        self.assertIsNone(source)

    def test_parse_llm_result_rescued_from_thinking(self):
        # Model generated tool_call inside <think> and content was empty/truncated
        content = ""
        thinking = (
            "Let's write a hello.txt file directly:\n"
            "<tool_call>\n"
            "<function=write>\n"
            "<parameter=path>\nhello.txt\n</parameter>\n"
            "<parameter=content>\nHello World\n</parameter>\n"
            "</function>\n"
            "</tool_call>"
        )
        actions, source = parse_llm_result(content, thinking=thinking)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "write")
        self.assertEqual(actions[0]["attrs"]["path"], "hello.txt")
        self.assertEqual(actions[0]["body"], "Hello World")
        self.assertEqual(source, "rescued_from_thinking")

    def test_parse_llm_result_rescued_from_thinking_qwen_json(self):
        content = ""
        thinking = (
            "I need to check the active port. Let me execute netstat.\n"
            "<tool_call>{\"name\": \"pwsh\", \"arguments\": {\"command\": \"netstat -ano\"}}</tool_call>"
        )
        actions, source = parse_llm_result(content, thinking=thinking)
        self.assertEqual(source, "rescued_from_thinking")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "pwsh")
        self.assertEqual(actions[0]["body"], "netstat -ano")

    def test_parse_llm_result_rescued_from_thinking_qwythos_xml(self):
        content = ""
        thinking = (
            "Let me write the patch.\n"
            "<tool_call><function=write><parameter=path>test.txt</parameter><parameter=content>hello world</parameter></function></tool_call>"
        )
        actions, source = parse_llm_result(content, thinking=thinking)
        self.assertEqual(source, "rescued_from_thinking")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "write")
        self.assertEqual(actions[0]["attrs"]["path"], "test.txt")
        self.assertEqual(actions[0]["body"], "hello world")


if __name__ == "__main__":
    unittest.main()
