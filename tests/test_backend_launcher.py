"""Tests for generic backend launcher (no real processes)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core.backend_launcher import (
    BackendLauncher,
    LaneLaunchConfig,
    normalize_lane,
)
from core.config_check import PropsSnapshot


class TestBackendLauncher(unittest.TestCase):
    def test_normalize_lane(self):
        self.assertEqual(normalize_lane("orch"), "orch")
        self.assertEqual(normalize_lane("orchestrator"), "orch")
        self.assertEqual(normalize_lane("atomic"), "atomic")
        self.assertIsNone(normalize_lane("embed"))

    def test_from_config_parses_launch(self):
        config = {
            "llm": {
                "orchestrator": {
                    "base_url": "http://127.0.0.1:11440",
                    "launch": {
                        "cmd": ["powershell", "-File", "x.ps1"],
                        "cwd": "C:\\tmp",
                        "autostart": False,
                        "parallel": 1,
                    },
                },
                "atomic": {},
            },
            "backends": {"gate": {"orch_slots": 1, "atomic_slots": 1}},
        }
        bl = BackendLauncher.from_config(config)
        self.assertIsNotNone(bl.configs["orch"])
        self.assertEqual(bl.configs["orch"].cmd[0], "powershell")
        self.assertEqual(bl.configs["orch"].parallel, 1)
        self.assertEqual(bl.configs["orch"].base_url, "http://127.0.0.1:11440")
        self.assertIsNone(bl.configs["atomic"])

    def test_build_argv_appends_f3_params(self):
        cfg = LaneLaunchConfig(
            cmd=["powershell", "-File", "start.ps1"],
            parallel=2,
            profile="concurrent2",
            context=98304,
            extra_args=["-Foreground"],
        )
        argv = cfg.build_argv()
        self.assertEqual(
            argv,
            [
                "powershell", "-File", "start.ps1",
                "-Parallel", "2",
                "-Profile", "concurrent2",
                "-Context", "98304",
                "-Foreground",
            ],
        )
        self.assertEqual(cfg.resolved_expect_slots(), 2)

    def test_start_polls_health_and_verifies_props(self):
        cfg = {
            "orch": LaneLaunchConfig(
                cmd=["echo", "hi"],
                cwd=None,
                autostart=False,
                parallel=1,
                expect_total_slots=1,
                base_url="http://127.0.0.1:11440",
            ),
            "atomic": None,
        }
        healthy = MagicMock(return_value=True)
        bl = BackendLauncher(cfg, health={"orch": healthy}, ready_timeout=5, poll_interval=0.01)
        fake_proc = MagicMock()
        fake_proc.pid = 4242
        fake_proc.poll.return_value = None
        snap = PropsSnapshot(n_ctx=262144, total_slots=1, reachable=True)
        with patch("core.backend_launcher.subprocess.Popen", return_value=fake_proc):
            with patch("core.backend_launcher.fetch_props", return_value=snap):
                result = bl.start("orch")
        self.assertTrue(result["ok"])
        self.assertEqual(result["pid"], 4242)
        self.assertTrue(result["props"]["ok"])
        healthy.assert_called()

    def test_start_fails_when_props_slots_mismatch(self):
        cfg = {
            "atomic": LaneLaunchConfig(
                cmd=["echo", "hi"],
                parallel=2,
                expect_total_slots=2,
                base_url="http://127.0.0.1:11439",
            ),
            "orch": None,
        }
        healthy = MagicMock(return_value=True)
        bl = BackendLauncher(cfg, health={"atomic": healthy}, ready_timeout=5, poll_interval=0.01)
        fake_proc = MagicMock()
        fake_proc.pid = 7
        fake_proc.poll.return_value = None
        snap = PropsSnapshot(n_ctx=98304, total_slots=1, reachable=True)
        with patch("core.backend_launcher.subprocess.Popen", return_value=fake_proc):
            with patch("core.backend_launcher.fetch_props", return_value=snap):
                result = bl.start("atomic")
        self.assertFalse(result["ok"])
        self.assertIn("total_slots", result.get("error", ""))

    def test_props_warns_gate_over_slots(self):
        cfg = {
            "orch": LaneLaunchConfig(
                cmd=["x"],
                parallel=1,
                base_url="http://127.0.0.1:11440",
            ),
            "atomic": None,
        }
        bl = BackendLauncher(cfg, gate_slots={"orch": 2})
        snap = PropsSnapshot(n_ctx=100, total_slots=1, reachable=True)
        with patch("core.backend_launcher.fetch_props", return_value=snap):
            result = bl.props("orch")
        self.assertFalse(result["ok"])
        self.assertTrue(any("gate" in m for m in result["messages"]))

    def test_status_unconfigured(self):
        bl = BackendLauncher({"orch": None, "atomic": None})
        st = bl.status("orch")
        self.assertFalse(st["configured"])


if __name__ == "__main__":
    unittest.main()
