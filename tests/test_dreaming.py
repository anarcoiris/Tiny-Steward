"""Tests for dreaming extract parse, watermark, and memory templates."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.dreaming import (
    entries_after_watermark,
    filter_dream_entries,
    parse_extract_json,
    render_memory_md,
    run_dream,
)


class TestDreaming(unittest.TestCase):
    def test_parse_extract_json_plain(self):
        raw = json.dumps({
            "facts": [{"statement": "ls plans/ worked", "evidence_refs": ["t1"], "confidence": 0.9}],
            "validated": [],
            "falsified": [],
            "hypotheses": [{"statement": "LCP needs cooling", "evidence_refs": [], "confidence": 0.2}],
            "ideas": [],
            "open_questions": [],
        })
        data = parse_extract_json(raw)
        self.assertEqual(len(data["facts"]), 1)
        self.assertEqual(data["facts"][0]["statement"], "ls plans/ worked")

    def test_parse_extract_json_fenced(self):
        raw = '```json\n{"facts":[],"validated":[],"falsified":[],"hypotheses":[],"ideas":[],"open_questions":[]}\n```'
        data = parse_extract_json(raw)
        self.assertEqual(data["facts"], [])

    def test_watermark_slice(self):
        entries = [
            {"ts": "2026-07-16T20:00:00+00:00", "reasoning": "a"},
            {"ts": "2026-07-16T21:00:00+00:00", "reasoning": "b"},
            {"ts": "2026-07-16T22:00:00+00:00", "reasoning": "c"},
        ]
        after = entries_after_watermark(entries, "2026-07-16T21:00:00+00:00")
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0]["reasoning"], "c")

    def test_filter_skips_chrome_only(self):
        entries = [
            {
                "ts": "1",
                "reasoning": "",
                "content_preview": "turn 1  │  ~622 prompt  │  3 tok/s  │  LCP 0+1862 (0%)",
            },
            {"ts": "2", "reasoning": "real thought", "content_preview": ""},
        ]
        kept = filter_dream_entries(entries)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["reasoning"], "real thought")

    def test_render_memory_md(self):
        extract = {
            "facts": [{"statement": "P0 done", "evidence_refs": ["t"], "confidence": 1.0}],
            "validated": [],
            "falsified": [],
            "hypotheses": [],
            "ideas": [],
            "open_questions": [],
        }
        md = render_memory_md("demo", extract, watermark="ts1")
        self.assertIn("# Memory — demo", md)
        self.assertIn("P0 done", md)
        self.assertIn("Facts", md)

    def test_run_dream_with_mock_llm(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            think = root / "demo.think.jsonl"
            think.write_text(
                json.dumps({
                    "ts": "2026-07-16T22:00:00+00:00",
                    "session": "demo",
                    "reasoning": "Listed plans/ and confirmed F3 is deferred.",
                    "content_preview": "DONE",
                }, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            llm = MagicMock()
            llm.gate_priority = "interactive"
            llm.chat.return_value = json.dumps({
                "facts": [{
                    "statement": "F3 is deferred",
                    "evidence_refs": ["2026-07-16T22:00:00+00:00"],
                    "confidence": 0.8,
                }],
                "validated": [],
                "falsified": [],
                "hypotheses": [],
                "ideas": [],
                "open_questions": [],
            })
            result = run_dream(
                sessions_dir=root,
                session_name="demo",
                llm=llm,
                watermark=None,
            )
            self.assertTrue(result["ok"])
            self.assertFalse(result["skipped"])
            self.assertTrue(Path(result["memory_md"]).exists())
            self.assertEqual(llm.gate_priority, "interactive")
            # Second dream with watermark should skip
            result2 = run_dream(
                sessions_dir=root,
                session_name="demo",
                llm=llm,
                watermark=result["watermark"],
            )
            self.assertTrue(result2["skipped"])


if __name__ == "__main__":
    unittest.main()
