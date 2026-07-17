"""Fixture-based provider profile evals (no live llama.cpp)."""

from __future__ import annotations

import unittest
from pathlib import Path

from core.providers.registry import list_providers, resolve_provider
from evals.bench_tool_calls import iter_fixtures, score_fixtures

PROVIDERS_ROOT = Path(__file__).resolve().parents[1] / "evals" / "providers"


class TestProviderEvals(unittest.TestCase):
    def test_fixture_dirs_exist_for_registered_providers(self):
        for pid in list_providers():
            self.assertTrue(
                (PROVIDERS_ROOT / pid).is_dir(),
                f"missing evals/providers/{pid}/",
            )

    def test_all_fixtures_match_profile_extract_actions(self):
        cases = iter_fixtures()
        self.assertGreaterEqual(len(cases), 6, "expected at least a few fixtures")
        for case in cases:
            with self.subTest(provider=case.provider_id, name=case.name):
                profile = resolve_provider(case.provider_id, default=case.provider_id)
                got = profile.extract_actions(case.text)
                self.assertEqual(got, case.expected)

    def test_scorecard_all_pass(self):
        report = score_fixtures()
        self.assertEqual(
            report["passed"],
            report["total"],
            msg=report,
        )

    def test_qwythos_does_not_claim_qwen_json(self):
        """Locked dialect: Qwythos profile ignores JSON tool_call bodies."""
        text = (
            '<tool_call>\n'
            '{"name": "read", "arguments": {"path": "config.yaml"}}\n'
            '</tool_call>'
        )
        profile = resolve_provider("qwythos", default="qwythos")
        self.assertEqual(profile.extract_actions(text), [])

    def test_qwen_does_not_claim_qwythos_xml(self):
        """Locked dialect: Qwen profile ignores XML function= bodies."""
        text = (
            '<tool_call>\n'
            '<function=ls>\n'
            '<parameter=path>\n'
            '.\n'
            '</parameter>\n'
            '</function>\n'
            '</tool_call>'
        )
        profile = resolve_provider("qwen3_json", default="qwen3_json")
        self.assertEqual(profile.extract_actions(text), [])


if __name__ == "__main__":
    unittest.main()
