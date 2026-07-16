"""OpenClaw _meta packs stay on disk but are excluded from the skill index."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.skill_loader import OPENCLAW_META_EXCLUDE, discover_skills


class TestOpenClawQuarantine(unittest.TestCase):
    def test_exclude_constant_covers_known_packs(self):
        for name in (
            "delegation-gate",
            "delegate-router",
            "pulse-routing",
            "nomic-local",
            "paid-bash-security-v1-1",
        ):
            self.assertIn(name, OPENCLAW_META_EXCLUDE)

    def test_discover_skips_openclaw_keeps_primitives(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "_meta" / "delegation-gate").mkdir(parents=True)
            (root / "_meta" / "delegation-gate" / "SKILL.md").write_text(
                "---\nname: bad\n---\n# Bad\n", encoding="utf-8"
            )
            (root / "_meta" / "primitives").mkdir(parents=True)
            (root / "_meta" / "primitives" / "ls.md").write_text(
                "---\nname: ls_meta\n---\n# LS\n", encoding="utf-8"
            )
            skills = discover_skills(root)
            slugs = {s.slug for s in skills}
            self.assertNotIn("SKILL", slugs)
            self.assertNotIn("bad", {s.name for s in skills})
            # path-based: excluded pack not present
            self.assertFalse(any("delegation-gate" in s.path for s in skills))
            self.assertTrue(any("primitives" in s.path for s in skills))


if __name__ == "__main__":
    unittest.main()
