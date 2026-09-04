"""Tests for deterministic shell guardrails and OS invariants."""

import unittest
from core.shell_guard import validate_shell_action


class TestShellGuard(unittest.TestCase):
    def test_windows_allows_pwsh(self):
        valid, err = validate_shell_action("pwsh", "Get-ChildItem", platform="win32")
        self.assertTrue(valid)
        self.assertIsNone(err)

    def test_windows_blocks_bash_action(self):
        valid, err = validate_shell_action("bash", "ls -la", platform="win32")
        self.assertFalse(valid)
        self.assertIn("Direct bash execution is disabled on Windows", err)

    def test_windows_blocks_wsl_and_bash_subshell(self):
        valid, err = validate_shell_action("pwsh", "bash -c 'echo hello'", platform="win32")
        self.assertFalse(valid)
        self.assertIn("WSL / bash wrapper invocations are restricted", err)

        valid_wsl, err_wsl = validate_shell_action("pwsh", "wsl ls", platform="win32")
        self.assertFalse(valid_wsl)
        self.assertIn("WSL / bash wrapper invocations are restricted", err_wsl)

    def test_cd_command_is_prohibited_on_all_platforms(self):
        valid_win, err_win = validate_shell_action("pwsh", "cd /tmp", platform="win32")
        self.assertFalse(valid_win)
        self.assertIn("Directory change 'cd' is prohibited", err_win)

        valid_unix, err_unix = validate_shell_action("bash", "cd /home", platform="linux")
        self.assertFalse(valid_unix)
        self.assertIn("Directory change 'cd' is prohibited", err_unix)


if __name__ == "__main__":
    unittest.main()
