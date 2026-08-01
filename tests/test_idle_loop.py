"""Unit tests for core/idle_loop.py (SharedExecutionLock and IdleLoop)."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock
from core.idle_loop import SharedExecutionLock, IdleExecutionLock, IdleLoop, IdleState


def test_idle_execution_lock_mutual_exclusion():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock = SharedExecutionLock(sessions_dir=tmpdir, session_name="session-a")
        assert not lock.is_busy

        # Test non-blocking idle acquire
        assert lock.acquire_idle()
        assert lock.is_busy
        assert not lock.is_active_running

        # Releasing idle lock
        lock.release_idle()
        assert not lock.is_busy

        # Active lock context
        with lock.hold_active():
            assert lock.is_busy
            assert lock.is_active_running
            # Non-blocking idle acquire must fail while active lock is held
            assert not lock.acquire_idle()

        assert not lock.is_busy


def test_shared_execution_lock_cross_session_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_a = SharedExecutionLock(sessions_dir=tmpdir, session_name="session-a")
        lock_b = SharedExecutionLock(sessions_dir=tmpdir, session_name="session-b")

        status_init = lock_a.get_shared_status()
        assert status_init["shared_lock_state"] == "FREE"
        assert status_init["registered_processes_count"] >= 1

        # Lock A acquires active turn
        with lock_a.hold_active():
            status_busy = lock_b.get_shared_status()
            assert status_busy["shared_lock_state"] == "LOCKED_ACTIVE_BUSY"
            assert status_busy["lock_holder"]["session"] == "session-a"

            # Lock B tries idle acquire across session -> must be rejected
            assert not lock_b.acquire_idle()

        # After Lock A releases
        status_after = lock_b.get_shared_status()
        assert status_after["shared_lock_state"] == "FREE"
        assert lock_b.acquire_idle()
        lock_b.release_idle()


def test_idle_loop_trigger_now():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_runtime = MagicMock()
        mock_runtime.llm.health.return_value = True
        mock_runtime.atomic_llm.health.return_value = True
        mock_runtime.execution_lock = SharedExecutionLock(sessions_dir=tmpdir, session_name="test-sess")

        idle = IdleLoop(
            runtime=mock_runtime,
            enabled=True,
            tick_interval=1.0,
            health_check_interval=30.0,
            dream_check_interval=60.0,
            alert_check_interval=3.0,
        )

        res = idle.trigger_now()
        assert res.get("ok") is True
        assert "health" in res
        assert res["health"].get("orch_health") is True
        assert res["health"].get("atomic_health") is True


def test_idle_loop_skips_when_active_busy():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_runtime = MagicMock()
        lock = SharedExecutionLock(sessions_dir=tmpdir, session_name="busy-sess")
        mock_runtime.execution_lock = lock

        idle = IdleLoop(runtime=mock_runtime, enabled=True)

        with lock.hold_active():
            # Attempting manual trigger while active turn is running
            res = idle.trigger_now()
            assert res.get("ok") is False
            assert "busy" in res.get("reason", "").lower()


def test_idle_loop_start_stop():
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_runtime = MagicMock()
        mock_runtime.execution_lock = SharedExecutionLock(sessions_dir=tmpdir, session_name="loop-sess")
        mock_runtime.llm.health.return_value = True
        mock_runtime.atomic_llm.health.return_value = True

        idle = IdleLoop(
            runtime=mock_runtime,
            enabled=True,
            tick_interval=0.1,
            health_check_interval=0.2,
            dream_check_interval=0.5,
            alert_check_interval=0.2,
        )

        assert not idle.is_running
        idle.start()
        assert idle.is_running

        time.sleep(0.35)

        idle.stop()
        assert not idle.is_running
        assert idle.state.last_run_ts is not None
