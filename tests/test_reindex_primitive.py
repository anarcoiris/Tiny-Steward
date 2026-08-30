"""Unit tests for the reindex primitive and hot RAG rebuilding."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.primitives import reindex


class TestReindexPrimitive(unittest.TestCase):
    def test_reindex_custom_skills_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)

            # Create a sample skill
            sample_skill_dir = skills_dir / "sample_domain" / "sample-tool"
            sample_skill_dir.mkdir(parents=True, exist_ok=True)

            skill_md = sample_skill_dir / "SKILL.md"
            skill_md.write_text(
                "---\n"
                "name: sample-tool\n"
                "description: A test sample tool for reindex verification.\n"
                "domain: testing\n"
                "tags:\n"
                "  - test\n"
                "  - sample\n"
                "---\n"
                "# Sample Tool\n\n"
                "This is a test tool.\n",
                encoding="utf-8",
            )

            mock_embedder = MagicMock()
            import numpy as np
            mock_embedder.embed_batch.return_value = np.zeros((1, 384), dtype=np.float32)

            res = reindex(path=str(skills_dir), embedder=mock_embedder)
            self.assertTrue(res.get("ok"))
            self.assertEqual(res.get("skills_indexed"), 1)
            self.assertIn("_index.json", res.get("index_path", ""))

            # Check that _index.json and _index.npy exist
            idx_json = skills_dir / "_index.json"
            idx_npy = skills_dir / "_index.npy"
            self.assertTrue(idx_json.exists())
            self.assertTrue(idx_npy.exists())

            # Check content of _index.json
            data = json.loads(idx_json.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["name"], "sample-tool")
            self.assertEqual(data[0]["slug"], "sample-tool")


if __name__ == "__main__":
    unittest.main()
