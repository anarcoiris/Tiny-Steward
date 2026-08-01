"""Regression tests for core.stats — TurnStats and SessionStats.

Covers:
- TurnStats field names (guard against accidental kwarg renames)
- tokens_per_sec and lcp_ratio computed properties
- tokens_per_sec must NOT be a constructor kwarg (the original streaming crash)
- SessionStats.add_turn accumulation
- SessionStats.record_turn consistency with add_turn
"""

from __future__ import annotations

import pytest
from core.stats import TurnStats, SessionStats


# ---------------------------------------------------------------------------
# TurnStats
# ---------------------------------------------------------------------------

class TestTurnStatsFields:
    def test_basic_construction(self):
        ts = TurnStats(turn=1, prompt_tokens_est=100, completion_tokens_est=20)
        assert ts.turn == 1
        assert ts.prompt_tokens_est == 100
        assert ts.completion_tokens_est == 20
        assert ts.elapsed_s == 0.0
        assert ts.prompt_tokens_real is None
        assert ts.completion_tokens_real is None

    def test_tokens_per_sec_is_a_property_not_constructor_kwarg(self):
        """Regression: streaming crash was caused by passing tokens_per_sec as kwarg."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(TurnStats)}
        assert "tokens_per_sec" not in field_names, (
            "tokens_per_sec must remain a @property, not a dataclass field"
        )

    def test_tokens_per_sec_kwarg_raises(self):
        """Ensure TypeError is raised when tokens_per_sec is passed as kwarg (regression guard)."""
        with pytest.raises(TypeError, match="tokens_per_sec"):
            TurnStats(
                turn=1,
                prompt_tokens_est=100,
                completion_tokens_est=20,
                tokens_per_sec=5.0,  # must not be accepted
            )

    def test_tokens_per_sec_computed_from_real(self):
        ts = TurnStats(
            turn=1,
            prompt_tokens_est=0,
            completion_tokens_est=0,
            completion_tokens_real=100,
            elapsed_s=5.0,
        )
        assert ts.tokens_per_sec == pytest.approx(20.0)

    def test_tokens_per_sec_falls_back_to_est(self):
        ts = TurnStats(
            turn=1,
            prompt_tokens_est=0,
            completion_tokens_est=50,
            elapsed_s=2.0,
        )
        assert ts.tokens_per_sec == pytest.approx(25.0)

    def test_tokens_per_sec_zero_elapsed(self):
        ts = TurnStats(turn=1, prompt_tokens_est=10, completion_tokens_est=10, elapsed_s=0.0)
        assert ts.tokens_per_sec == 0.0

    def test_lcp_ratio(self):
        ts = TurnStats(
            turn=1, prompt_tokens_est=10, completion_tokens_est=5,
            cache_n=900, prompt_n=100,
        )
        assert ts.lcp_ratio == pytest.approx(0.9)

    def test_lcp_ratio_none_when_missing(self):
        ts = TurnStats(turn=1, prompt_tokens_est=10, completion_tokens_est=5)
        assert ts.lcp_ratio is None

    def test_total_tokens_est(self):
        ts = TurnStats(turn=1, prompt_tokens_est=80, completion_tokens_est=20)
        assert ts.total_tokens_est == 100

    def test_total_tokens_real_none_when_partial(self):
        ts = TurnStats(
            turn=1, prompt_tokens_est=0, completion_tokens_est=0,
            prompt_tokens_real=50,
        )
        assert ts.total_tokens_real is None

    def test_total_tokens_real_computed(self):
        ts = TurnStats(
            turn=1, prompt_tokens_est=0, completion_tokens_est=0,
            prompt_tokens_real=50, completion_tokens_real=10,
        )
        assert ts.total_tokens_real == 60


# ---------------------------------------------------------------------------
# SessionStats.add_turn
# ---------------------------------------------------------------------------

class TestSessionStatsAddTurn:
    def _make_ts(self, **kwargs) -> TurnStats:
        defaults = dict(turn=1, prompt_tokens_est=0, completion_tokens_est=0)
        defaults.update(kwargs)
        return TurnStats(**defaults)

    def test_add_turn_increments_total_turns(self):
        ss = SessionStats()
        ss.add_turn(self._make_ts(turn=1))
        ss.add_turn(self._make_ts(turn=2))
        assert ss.total_turns == 2

    def test_add_turn_uses_real_tokens_when_available(self):
        ss = SessionStats()
        ss.add_turn(self._make_ts(
            prompt_tokens_est=10, completion_tokens_est=5,
            prompt_tokens_real=80, completion_tokens_real=20,
        ))
        assert ss.total_prompt_tokens == 80
        assert ss.total_completion_tokens == 20

    def test_add_turn_falls_back_to_est(self):
        ss = SessionStats()
        ss.add_turn(self._make_ts(prompt_tokens_est=30, completion_tokens_est=10))
        assert ss.total_prompt_tokens == 30
        assert ss.total_completion_tokens == 10

    def test_add_turn_tracks_compaction(self):
        ss = SessionStats()
        ts = self._make_ts(compaction_triggered=True)
        ss.add_turn(ts)
        assert ss.compaction_count == 1

    def test_add_turn_tracks_checkpoint(self):
        ss = SessionStats()
        ts = self._make_ts(checkpoint_saved=True)
        ss.add_turn(ts)
        assert ss.checkpoint_count == 1

    def test_add_turn_total_tokens_property(self):
        ss = SessionStats()
        ss.add_turn(self._make_ts(prompt_tokens_real=40, completion_tokens_real=10))
        assert ss.total_tokens == 50

    def test_add_turn_consistency_with_record_turn(self):
        """Both methods should produce identical session totals for the same input."""
        ss1 = SessionStats()
        ss1.add_turn(TurnStats(
            turn=1,
            prompt_tokens_est=100,
            completion_tokens_est=25,
            prompt_tokens_real=120,
            completion_tokens_real=30,
            elapsed_s=3.0,
            compaction_triggered=True,
        ))

        ss2 = SessionStats()
        ss2.record_turn(
            turn=1,
            prompt_tokens_est=100,
            completion_tokens_est=25,
            elapsed_s=3.0,
            prompt_tokens_real=120,
            completion_tokens_real=30,
            compaction_triggered=True,
        )

        assert ss1.total_prompt_tokens == ss2.total_prompt_tokens
        assert ss1.total_completion_tokens == ss2.total_completion_tokens
        assert ss1.total_turns == ss2.total_turns
        assert ss1.compaction_count == ss2.compaction_count
        assert ss1.checkpoint_count == ss2.checkpoint_count
