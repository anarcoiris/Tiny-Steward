"""Tests for dream error resilience, timestamp duality, and LLM error enrichment."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import httpx
import pytest

from core.dreaming import (
    _extract_ts,
    entries_after_watermark,
    run_dream,
)
from core.llm import LLMClient


def test_extract_ts_supports_both_ts_and_timestamp():
    entry_iso = {"ts": "2026-09-04T12:00:00+00:00", "reasoning": "iso ts"}
    assert _extract_ts(entry_iso) == "2026-09-04T12:00:00+00:00"

    entry_epoch = {"timestamp": 1788538202.942, "reasoning": "epoch timestamp"}
    extracted = _extract_ts(entry_epoch)
    assert "2026-" in extracted or "1788538202" in extracted

    entry_none = {"reasoning": "no time"}
    assert _extract_ts(entry_none) == ""


def test_entries_after_watermark_with_mixed_timestamps():
    entries = [
        {"timestamp": 1000.0, "reasoning": "first"},
        {"timestamp": 2000.0, "reasoning": "second"},
        {"ts": "2026-09-04T20:00:00+00:00", "reasoning": "third"},
    ]
    # Filter with no watermark returns all
    assert len(entries_after_watermark(entries, None)) == 3

    # Filter after watermark
    wm = _extract_ts(entries[0])
    filtered = entries_after_watermark(entries, wm)
    assert len(filtered) == 2
    assert filtered[0]["reasoning"] == "second"
    assert filtered[1]["reasoning"] == "third"


def test_run_dream_handles_llm_exception_gracefully(tmp_path: Path):
    session_name = "test_resilient_session"
    sdir = tmp_path / "sessions"
    sdir.mkdir()
    sess_folder = sdir / session_name
    sess_folder.mkdir()

    # Create think log
    think_file = sess_folder / f"{session_name}.think.jsonl"
    think_file.write_text(
        json.dumps({"timestamp": 1788538202.0, "reasoning": "exploring things"}) + "\n",
        encoding="utf-8",
    )

    # Mock LLM that raises an HTTP 500 error
    mock_llm = MagicMock()
    mock_llm.gate_priority = "interactive"
    mock_llm.chat.side_effect = RuntimeError("500 Server Error: slot allocation failed")

    result = run_dream(
        sessions_dir=sdir,
        session_name=session_name,
        llm=mock_llm,
        force_all=True,
    )

    assert result["ok"] is False
    assert "LLM error during dream" in result["error"]
    assert "500 Server Error" in result["error"]
    # Verify priority restored
    assert mock_llm.gate_priority == "interactive"


def test_llm_post_enriches_http_status_error():
    client = LLMClient(base_url="http://127.0.0.1:9999", model="test-model")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.is_error = True
    mock_resp.text = '{"error": {"message": "context window exceeded: limit is 32768"}}'
    mock_resp.request = MagicMock()

    with patch.object(client._client, "post", return_value=mock_resp):
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client._post("/v1/chat/completions", {"prompt": "test"})

        err_msg = str(exc_info.value)
        assert "HTTP 500" in err_msg
        assert "context window exceeded" in err_msg


def test_atomic_lane_fallback_inheritance():
    from core.providers.llm_provider import BaseLLMProvider

    mock_fallback = MagicMock(spec=BaseLLMProvider)
    mock_fallback.name = "mock_cloud_fallback"

    at_cfg = {
        "base_url": "http://127.0.0.1:11800",
        "model": "qwen3.8-128k",
        "enable_thinking": False,
        "preserve_thinking": False,
        "expect_total_slots": 1,
    }

    # When fallback_providers passed from orchestrator
    client = LLMClient.from_lane_config(
        at_cfg,
        gate_lane="atomic",
        fallback_providers=[mock_fallback],
    )

    assert len(client.fallback_providers) == 1
    assert client.fallback_providers[0].name == "mock_cloud_fallback"

    # Verify reserved keys are not leaked into extra_params
    assert "enable_thinking" not in client.extra_params
    assert "preserve_thinking" not in client.extra_params
    assert "expect_total_slots" not in client.extra_params
