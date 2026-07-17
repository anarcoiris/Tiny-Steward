"""Tests for config.yaml vs GET /props reconciliation."""

from __future__ import annotations

import unittest

from core.config_check import PropsSnapshot, verify_backend, verify_config_backends


class TestConfigCheck(unittest.TestCase):
    def test_gate_slots_exceed_total_warns(self):
        props = PropsSnapshot(n_ctx=98304, total_slots=1, reachable=True)
        msgs = verify_backend(
            "atomic",
            base_url="http://127.0.0.1:11439",
            cfg_ctx=98304,
            gate_slots=2,
            props=props,
        )
        kinds = [k for k, _ in msgs]
        self.assertIn("warn", kinds)
        self.assertTrue(any("total_slots" in m for _, m in msgs))

    def test_ctx_exceeds_server_warns(self):
        props = PropsSnapshot(n_ctx=65536, total_slots=1, reachable=True)
        msgs = verify_backend(
            "orchestrator",
            base_url="http://127.0.0.1:11440",
            cfg_ctx=131072,
            gate_slots=1,
            props=props,
        )
        self.assertTrue(any(k == "warn" and "exceeds server" in m for k, m in msgs))

    def test_ctx_headroom_is_info_not_warn(self):
        props = PropsSnapshot(n_ctx=262144, total_slots=1, reachable=True)
        msgs = verify_backend(
            "orchestrator",
            base_url="http://127.0.0.1:11440",
            cfg_ctx=131072,
            gate_slots=1,
            props=props,
        )
        self.assertTrue(any(k == "info" and "headroom OK" in m for k, m in msgs))
        self.assertFalse(any(k == "warn" for k, m in msgs))

    def test_unreachable_skips(self):
        props = PropsSnapshot(n_ctx=None, total_slots=None, reachable=False, error="down")
        msgs = verify_backend(
            "orchestrator",
            base_url="http://127.0.0.1:11440",
            cfg_ctx=131072,
            gate_slots=1,
            props=props,
        )
        self.assertEqual(msgs, [])

    def test_verify_config_backends_uses_fetch(self):
        def fake_fetch(url: str):
            if "11440" in url:
                return PropsSnapshot(n_ctx=262144, total_slots=1, reachable=True)
            return PropsSnapshot(n_ctx=98304, total_slots=1, reachable=True)

        config = {
            "llm": {
                "orchestrator": {"base_url": "http://127.0.0.1:11440", "ctx": 131072},
                "atomic": {"base_url": "http://127.0.0.1:11439", "ctx": 98304},
            },
            "backends": {"gate": {"orch_slots": 1, "atomic_slots": 1}},
        }
        msgs = verify_config_backends(config, fetch=fake_fetch)
        self.assertTrue(any("headroom OK" in m for _, m in msgs))


if __name__ == "__main__":
    unittest.main()
