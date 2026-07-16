"""Tests for unified tool-call / action extraction."""

from __future__ import annotations

import unittest

from core.runtime import extract_actions, parse_actions


class TestToolCallParsing(unittest.TestCase):
    def test_qwen_json_tool_call(self):
        text = (
            'Let me read the file.\n'
            '<tool_call>\n'
            '{"name": "read", "arguments": {"path": "config.yaml", "start_line": 1}}\n'
            '</tool_call>'
        )
        actions = extract_actions(text)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "read")
        self.assertEqual(actions[0]["body"], "config.yaml")
        self.assertEqual(actions[0]["attrs"]["start_line"], "1")

    def test_qwythos_xml_tool_call(self):
        text = (
            '<tool_call>\n'
            '<function=pwsh>\n'
            '<parameter=command>\n'
            'Get-ChildItem\n'
            '</parameter>\n'
            '</function>\n'
            '</tool_call>'
        )
        actions = extract_actions(text)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "pwsh")
        self.assertEqual(actions[0]["body"], "Get-ChildItem")

    def test_legacy_action_fallback(self):
        text = '<action name="ls">.</action>'
        actions = extract_actions(text)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["name"], "ls")
        self.assertEqual(actions[0]["body"], ".")

    def test_set_action_attrs_only(self):
        text = (
            '<tool_call>\n'
            '{"name": "set", "arguments": {"key": "temperature", "value": "0.2"}}\n'
            '</tool_call>'
        )
        actions = extract_actions(text)
        self.assertEqual(actions[0]["name"], "set")
        self.assertEqual(actions[0]["body"], "")
        self.assertEqual(actions[0]["attrs"]["key"], "temperature")
        self.assertEqual(actions[0]["attrs"]["value"], "0.2")

    def test_parse_actions_legacy_only(self):
        text = '<action name="help">docker won\'t start</action>'
        actions = parse_actions(text)
        self.assertEqual(actions[0]["name"], "help")
        self.assertEqual(actions[0]["body"], "docker won't start")


if __name__ == "__main__":
    unittest.main()
