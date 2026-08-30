"""Unit tests for StewardEngine (core/service_kernel.py)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.service_kernel import (
    ActionResult,
    DreamResult,
    SkillMatch,
    StewardEngine,
    TurnResult,
)


class TestServiceKernel(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.sessions = self.root / "sessions"
        self.sessions.mkdir(parents=True, exist_ok=True)

        self.config = {
            "workspace": str(self.workspace),
            "llm": {
                "orchestrator": {
                    "base_url": "http://127.0.0.1:11434",
                    "model": "qwen3.8-64k",
                },
                "atomic": {
                    "base_url": "http://127.0.0.1:11434",
                    "model": "qwen3.8-64k",
                },
            },
            "embeddings": {
                "base_url": "http://127.0.0.1:11438",
                "model": "nomic-embed-text",
            },
            "skills": {
                "index": str(self.root / "skills_index.json"),
            },
            "sessions": {
                "dir": str(self.sessions),
            },
            "rules": {
                "enabled": False,
            },
        }

        self.engine = StewardEngine(config_dict=self.config, workspace=self.workspace)

    def tearDown(self):
        self.td.cleanup()

    def test_engine_initialization(self):
        self.assertEqual(str(self.engine.workspace), str(self.workspace.resolve()))
        self.assertEqual(self.engine.llm.model, "qwen3.8-64k")
        self.assertEqual(self.engine.atomic_llm.model, "qwen3.8-64k")

    def test_session_lifecycle(self):
        sess = self.engine.get_or_create_session("kernel_test")
        self.assertEqual(sess.name, "kernel_test")

        runtime = self.engine.get_runtime("kernel_test")
        self.assertIsNotNone(runtime)
        self.assertEqual(runtime.session.name, "kernel_test")

        # Caching check
        self.assertIs(runtime, self.engine.get_runtime("kernel_test"))

    def test_execute_action_primitives(self):
        # Write action
        res = self.engine.execute_action("write", body="sample text", attrs={"path": "hello.txt"})
        self.assertTrue(res.success)
        self.assertTrue((self.workspace / "hello.txt").exists())

        # Read action
        res_read = self.engine.execute_action("read", attrs={"path": "hello.txt"})
        self.assertTrue(res_read.success)
        self.assertEqual(res_read.stdout, "sample text")

        # Unknown action
        res_unk = self.engine.execute_action("unknown_tool")
        self.assertFalse(res_unk.success)
        self.assertIn("Unknown primitive", res_unk.stderr)

    def test_step_execution(self):
        mock_response = (
            "I will create the test file.\n"
            "<tool_call>{\"name\": \"write\", \"arguments\": {\"path\": \"step_test.txt\", \"content\": \"kernel content\"}}</tool_call>"
        )

        with patch.object(self.engine.llm, "chat", return_value=mock_response):
            result: TurnResult = self.engine.step("kernel_test", "Create step_test.txt")
            self.assertTrue(result.success)
            self.assertEqual(len(result.actions_executed), 1)
            self.assertEqual(result.actions_executed[0]["name"], "write")
            self.assertTrue((self.workspace / "step_test.txt").exists())
            self.assertEqual((self.workspace / "step_test.txt").read_text(encoding="utf-8"), "kernel content")

    def test_dream_and_memory_retrieval(self):
        sess_name = "dream_test"
        sess_dir = self.sessions / sess_name
        sess_dir.mkdir(parents=True, exist_ok=True)

        think = sess_dir / f"{sess_name}.think.jsonl"
        think.write_text('{"ts": "2026-08-30T12:00:00Z", "reasoning": "Tested kernel"}\n', encoding="utf-8")

        mock_atomic = '{"facts": [{"statement": "Kernel verified", "evidence_refs": ["test"], "confidence": 1.0}], "lessons": [{"mistake": "None", "root_cause": "N/A", "rule_or_fix": "Keep clean", "evidence_refs": []}]}'

        with patch.object(self.engine.atomic_llm, "chat", return_value=mock_atomic):
            dream_res = self.engine.dream(sess_name)
            self.assertTrue(dream_res.ok)
            self.assertFalse(dream_res.quarantined)

            memory = self.engine.read_memory(sess_name)
            self.assertIn("Kernel verified", memory)

            lessons = self.engine.read_lessons(sess_name)
            self.assertIn("Lecciones Aprendidas", lessons)


if __name__ == "__main__":
    unittest.main()
