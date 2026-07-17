"""Tests for Qwythos reasoning kwargs, stream reasoning_content, and think merge."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.llm import LLMClient, merge_reasoning_into_content
from core.runtime import Runtime, normalize_messages_for_llm
from core.help import HelpEngine
from core.session import Session, SessionManager
from core.skill_loader import Skill, SkillIndex


class TestMergeReasoning(unittest.TestCase):
    def test_embed_when_missing(self):
        out = merge_reasoning_into_content("Hello", "plan step")
        self.assertIn("<think>", out)
        self.assertIn("plan step", out)
        self.assertIn("Hello", out)

    def test_no_duplicate_when_think_present(self):
        raw = "<think>\nalready\n</think>\n\nHi"
        self.assertEqual(merge_reasoning_into_content(raw, "other"), raw)

    def test_empty_reasoning(self):
        self.assertEqual(merge_reasoning_into_content("Hi", ""), "Hi")


class TestBuildBodyKwargs(unittest.TestCase):
    def test_body_includes_template_kwargs_and_budget(self):
        client = LLMClient(
            base_url="http://mock",
            model="qwythos",
            chat_template_kwargs={"enable_thinking": True, "preserve_thinking": False},
            thinking_budget_tokens=-1,
            cache_prompt=True,
        )
        body = client._build_body(
            [{"role": "user", "content": "hi"}],
            stream=False,
            max_tokens=None,
            temperature=None,
        )
        self.assertEqual(
            body["chat_template_kwargs"],
            {"enable_thinking": True, "preserve_thinking": False},
        )
        self.assertEqual(body["thinking_budget_tokens"], -1)
        self.assertTrue(body["cache_prompt"])

    def test_from_lane_config(self):
        cfg = {
            "base_url": "http://127.0.0.1:11440",
            "model": "qwythos-9b",
            "enable_thinking": True,
            "preserve_thinking": False,
            "thinking_budget_tokens": -1,
            "cache_prompt": True,
            "temperature": 0.6,
            "api": "openai",
            "ctx": 131072,
        }
        client = LLMClient.from_lane_config(cfg)
        self.assertTrue(client.chat_template_kwargs["enable_thinking"])
        self.assertFalse(client.chat_template_kwargs["preserve_thinking"])
        self.assertEqual(client.thinking_budget_tokens, -1)
        self.assertNotIn("api", client.extra_params)
        self.assertNotIn("ctx", client.extra_params)

    def test_from_lane_config_id_slot_and_launch_excluded(self):
        cfg = {
            "base_url": "http://127.0.0.1:11440",
            "model": "qwythos-9b",
            "id_slot": 0,
            "launch": {"cmd": ["echo"], "cwd": ".", "autostart": False},
            "cache_prompt": True,
        }
        client = LLMClient.from_lane_config(cfg)
        self.assertEqual(client.id_slot, 0)
        self.assertNotIn("launch", client.extra_params)
        self.assertNotIn("id_slot", client.extra_params)
        body = client._build_body([{"role": "user", "content": "hi"}], stream=False, max_tokens=1, temperature=0.1)
        self.assertEqual(body["id_slot"], 0)
        self.assertNotIn("launch", body)

    def test_body_omits_id_slot_when_unset(self):
        client = LLMClient(base_url="http://mock", model="x")
        body = client._build_body([{"role": "user", "content": "hi"}], stream=False, max_tokens=1, temperature=0.1)
        self.assertNotIn("id_slot", body)


class TestNormalizePreserve(unittest.TestCase):
    def test_strips_think_and_reasoning_by_default(self):
        messages = [
            {
                "role": "assistant",
                "content": "<think>\nsecret\n</think>\n\nHello",
                "reasoning_content": "secret",
            }
        ]
        out = normalize_messages_for_llm(messages)
        self.assertNotIn("<think>", out[0]["content"])
        self.assertIn("Hello", out[0]["content"])
        self.assertNotIn("reasoning_content", out[0])

    def test_preserve_thinking_keeps_fields(self):
        messages = [
            {
                "role": "assistant",
                "content": "<think>\nsecret\n</think>\n\nHello",
                "reasoning_content": "secret",
            }
        ]
        out = normalize_messages_for_llm(messages, preserve_thinking=True)
        self.assertIn("<think>", out[0]["content"])
        self.assertEqual(out[0]["reasoning_content"], "secret")


class TestStreamReasoningParts(unittest.TestCase):
    def test_chat_stream_parts_yields_reasoning_then_content(self):
        client = LLMClient(base_url="http://mock", model="m")
        lines = [
            'data: {"choices":[{"delta":{"reasoning_content":"step1"}}]}',
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":"!"}}]}',
            "data: [DONE]",
        ]

        class FakeResp:
            def iter_lines(self):
                for line in lines:
                    yield line

        class FakeCM:
            def __enter__(self):
                return FakeResp()

            def __exit__(self, *a):
                return False

        with patch.object(client, "_stream_request", return_value=FakeCM()):
            parts = list(client.chat_stream_parts([{"role": "user", "content": "x"}]))

        self.assertEqual(parts[0], ("reasoning", "step1"))
        self.assertEqual(parts[1], ("content", "Hello"))
        self.assertEqual(parts[2], ("content", "!"))
        self.assertEqual(client._last_reasoning, "step1")

    def test_timings_merged_into_usage(self):
        client = LLMClient(base_url="http://mock", model="m")
        lines = [
            'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            'data: {"choices":[{"delta":{}}],"timings":{"cache_n":1000,"prompt_n":50,"predicted_n":10}}',
            "data: [DONE]",
        ]

        class FakeResp:
            def iter_lines(self):
                for line in lines:
                    yield line

            def close(self):
                pass

        class FakeCM:
            def __enter__(self):
                return FakeResp()

            def __exit__(self, *a):
                return False

        with patch.object(client, "_stream_request", return_value=FakeCM()):
            gen = client.chat_stream_parts([{"role": "user", "content": "x"}])
            parts = []
            usage = None
            try:
                while True:
                    parts.append(next(gen))
            except StopIteration as e:
                usage = e.value

        self.assertEqual(parts, [("content", "Hi")])
        self.assertEqual(usage["cache_n"], 1000)
        self.assertEqual(usage["prompt_n"], 50)
        self.assertEqual(client._last_timings["cache_n"], 1000)


class TestLcpStats(unittest.TestCase):
    def test_lcp_ratio(self):
        from core.stats import TurnStats
        ts = TurnStats(
            turn=1,
            prompt_tokens_est=10,
            completion_tokens_est=5,
            cache_n=900,
            prompt_n=100,
        )
        self.assertAlmostEqual(ts.lcp_ratio, 0.9)


class TestSetThinkingKeys(unittest.TestCase):
    def setUp(self):
        self.llm = LLMClient(
            base_url="http://mock",
            model="m",
            chat_template_kwargs={"enable_thinking": True, "preserve_thinking": False},
            thinking_budget_tokens=-1,
        )
        skill = Skill(name="t", slug="t", path="t.md", skill_type="skill")
        index = SkillIndex([skill], vectors=None)
        self.runtime = Runtime(
            llm=self.llm,
            help_engine=HelpEngine(index, None),
            session=Session("test"),
            use_streaming=False,
        )

    def test_set_enable_thinking(self):
        msg = self.runtime._handle_set("enable_thinking off")
        self.assertIn("False", msg)
        self.assertFalse(self.llm.chat_template_kwargs["enable_thinking"])
        self.assertNotIn("enable_thinking", self.llm.extra_params)

    def test_set_thinking_alias(self):
        self.runtime._handle_set("thinking off")
        self.assertFalse(self.llm.chat_template_kwargs["enable_thinking"])

    def test_set_budget_kv_safe(self):
        msg = self.runtime._handle_set("thinking_budget_tokens 2048")
        self.assertIn("2048", msg)
        self.assertEqual(self.llm.thinking_budget_tokens, 2048)


class TestThinkLogAndSessionRaw(unittest.TestCase):
    def test_record_keeps_raw_and_mirrors_think(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            mgr = SessionManager(td)
            session = mgr.new("thinktest")
            llm = LLMClient(base_url="http://mock", model="m")
            llm._last_reasoning = "internal plan"
            skill = Skill(name="t", slug="t", path="t.md", skill_type="skill")
            rt = Runtime(
                llm=llm,
                help_engine=HelpEngine(SkillIndex([skill], vectors=None), None),
                session=session,
                use_streaming=False,
            )
            rt.session_manager = mgr
            messages: list = []
            raw = "<think>\ninternal plan\n</think>\n\nDONE"
            rt._record_assistant_turn(messages, raw)
            self.assertIn("<think>", session.messages[-1]["content"])
            think_path = Path(td) / "thinktest.think.jsonl"
            self.assertTrue(think_path.exists())
            line = json.loads(think_path.read_text(encoding="utf-8").strip())
            self.assertIn("internal plan", line["reasoning"])
            # LLM view strips think
            out = normalize_messages_for_llm(messages)
            self.assertNotIn("<think>", out[0]["content"])


if __name__ == "__main__":
    unittest.main()
