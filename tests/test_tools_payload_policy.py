"""Tests for session-scoped tools payload sending policy."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from core.llm import LLMClient
from core.help import HelpEngine
from core.runtime import Runtime
from core.session import Session
from core.skill_loader import Skill, SkillIndex


class MockLLM(LLMClient):
  def __init__(self):
    super().__init__(base_url="http://mock", model="mock")
    self.calls: list[dict] = []

  def chat(self, messages, *, max_tokens=None, temperature=None, tools=None) -> str:
    self.calls.append({"tools": tools, "messages": messages})
    return "done"

  def health(self) -> bool:
    return True


class TestToolsPayloadPolicy(unittest.TestCase):
  def setUp(self):
    self.llm = MockLLM()
    skill = Skill(name="t", slug="t", path="t.md", skill_type="skill")
    index = SkillIndex([skill], vectors=None)
    self.help_engine = HelpEngine(index, None)
    self.session = Session("test")
    self.runtime = Runtime(
      llm=self.llm,
      help_engine=self.help_engine,
      session=self.session,
      use_streaming=False,
    )

  def test_tools_sent_on_first_call_only(self):
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    self.runtime._call_llm(messages, turn=1, backend="primary")
    self.runtime._call_llm(messages, turn=2, backend="primary")

    self.assertIsNotNone(self.llm.calls[0]["tools"])
    self.assertIsNone(self.llm.calls[1]["tools"])

  def test_tools_resent_after_force_flag(self):
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    self.runtime._call_llm(messages, turn=1, backend="primary")
    self.assertIsNotNone(self.llm.calls[0]["tools"])
    self.runtime._call_llm(messages, turn=2, backend="primary")
    self.assertIsNone(self.llm.calls[1]["tools"])
    self.runtime._force_tools_resend("primary")
    self.runtime._call_llm(messages, turn=3, backend="primary")
    self.assertIsNotNone(self.llm.calls[2]["tools"])

  def test_tool_parse_failure_sets_force_flag(self):
    response = '<tool_call>\n{broken json\n</tool_call>'
    messages = []
    with patch.object(self.runtime, "_execute_action") as mock_exec:
      mock_exec.return_value = {"content": "ok"}
      self.runtime._process_response_actions(response, messages, backend="primary")
    self.assertTrue(self.runtime.session.metadata.get("force_tools_payload_primary_next"))


if __name__ == "__main__":
  unittest.main()
