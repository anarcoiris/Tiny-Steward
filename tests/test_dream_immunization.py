"""Unit tests for dream immunization, session health assessment, and quarantine isolation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.dreaming import (
    assess_session_health,
    clean_trace_content,
    compute_traces_sha256,
    run_dream,
)


class TestDreamImmunization(unittest.TestCase):
    def test_clean_trace_content_removes_stacktraces_and_noise(self):
        noisy = (
            "Thinking about doing task...\n"
            "Traceback (most recent call last):\n"
            "  File 'foo.py', line 10, in <module>\n"
            "    raise ValueError('bad')\n"
            "Remediated issue: fixed syntax error.\n"
            "Successfully wrote output to result.txt"
        )
        cleaned = clean_trace_content(noisy)
        self.assertNotIn("Traceback (most recent call last)", cleaned)
        self.assertNotIn("Remediated issue:", cleaned)
        self.assertIn("Successfully wrote output to result.txt", cleaned)

    def test_assess_session_health_healthy(self):
        with tempfile.TemporaryDirectory() as td:
            ipath = Path(td) / "interactions.jsonl"
            ipath.write_text(
                json.dumps({"actions": [{"name": "write", "exit_code": 0, "body_preview": "ok"}]}) + "\n"
                + json.dumps({"actions": [{"name": "pwsh", "exit_code": 0, "body_preview": "pass"}]}) + "\n",
                encoding="utf-8",
            )
            health = assess_session_health(ipath, [{"reasoning": "all good"}])
            self.assertTrue(health["healthy"])
            self.assertEqual(health["error_rate"], 0.0)

    def test_assess_session_health_unhealthy_quarantines(self):
        with tempfile.TemporaryDirectory() as td:
            ipath = Path(td) / "interactions.jsonl"
            # 3 failed actions out of 3 -> error_rate 1.0 > 0.35 threshold
            ipath.write_text(
                json.dumps({"actions": [{"name": "pwsh", "exit_code": 1, "body_preview": "fatal error"}]}) + "\n"
                + json.dumps({"actions": [{"name": "read", "exit_code": 1, "body_preview": "File not found"}]}) + "\n"
                + json.dumps({"actions": [{"name": "write", "exit_code": 1, "body_preview": "Permission denied"}]}) + "\n",
                encoding="utf-8",
            )
            health = assess_session_health(ipath, [{"reasoning": "trying to fix failures"}])
            self.assertFalse(health["healthy"])
            self.assertGreaterEqual(health["error_rate"], 0.35)

    def test_run_dream_quarantines_unhealthy_session(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sess_dir = root / "unhealthy_sess"
            sess_dir.mkdir(parents=True, exist_ok=True)

            think = sess_dir / "unhealthy_sess.think.jsonl"
            think.write_text(
                json.dumps({
                    "ts": "2026-08-30T21:00:00+00:00",
                    "session": "unhealthy_sess",
                    "reasoning": "Repeated crash attempts",
                }) + "\n",
                encoding="utf-8",
            )

            inter = sess_dir / "unhealthy_sess.interactions.jsonl"
            inter.write_text(
                json.dumps({"actions": [{"name": "pwsh", "exit_code": 1, "body_preview": "CUDA out of memory"}]}) + "\n"
                + json.dumps({"actions": [{"name": "pwsh", "exit_code": 1, "body_preview": "CUDA out of memory"}]}) + "\n",
                encoding="utf-8",
            )

            llm = MagicMock()
            llm.gate_priority = "interactive"
            llm.chat.return_value = "{}"

            res = run_dream(
                session_name="unhealthy_sess",
                llm=llm,
                sessions_dir=root,
            )

            self.assertTrue(res.get("ok"))
            self.assertTrue(res.get("quarantined"))
            self.assertIn("quarantined", res.get("reason", "").lower())
            qpath = Path(res["quarantine_path"])
            self.assertTrue(qpath.exists())


if __name__ == "__main__":
    unittest.main()
