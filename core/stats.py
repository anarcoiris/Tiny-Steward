"""Stats tracking for Tiny Steward.

Accumulates per-turn and session-level token, compaction, and checkpoint
counters. Purely a data module — display is handled by core.display.

Usage
-----
    stats = SessionStats()
    turn_stats = stats.record_turn(
        turn=1,
        prompt_tokens_est=1200,
        completion_tokens_est=350,
        elapsed_s=2.3,
    )
    display.print_stats(turn_stats)
    display.print_session_stats(stats)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# TurnStats — one row per LLM call
# ---------------------------------------------------------------------------
@dataclass
class TurnStats:
    """Statistics for a single reasoning turn."""

    turn: int
    """Turn index within the current user task (1-based)."""

    prompt_tokens_est: int
    """Locally estimated prompt tokens (char-count heuristic)."""

    completion_tokens_est: int
    """Locally estimated completion tokens."""

    prompt_tokens_real: Optional[int] = None
    """Actual prompt tokens reported by the API (if available)."""

    completion_tokens_real: Optional[int] = None
    """Actual completion tokens reported by the API (if available)."""

    compaction_triggered: bool = False
    """True if context was compacted before this turn."""

    checkpoint_saved: bool = False
    """True if a checkpoint was saved after this turn."""

    elapsed_s: float = 0.0
    """Wall-clock seconds for this LLM call."""

    context_budget_used: float = 0.0
    """Fraction of context budget used (0.0 to 1.0+)."""

    @property
    def total_tokens_est(self) -> int:
        return self.prompt_tokens_est + self.completion_tokens_est

    @property
    def total_tokens_real(self) -> Optional[int]:
        if self.prompt_tokens_real is not None and self.completion_tokens_real is not None:
            return self.prompt_tokens_real + self.completion_tokens_real
        return None

    @property
    def tokens_per_sec(self) -> float:
        toks = self.completion_tokens_real if self.completion_tokens_real is not None else self.completion_tokens_est
        return toks / self.elapsed_s if self.elapsed_s > 0 else 0.0



# ---------------------------------------------------------------------------
# SessionStats — running totals for the whole session
# ---------------------------------------------------------------------------
@dataclass
class SessionStats:
    """Running totals accumulated across all turns in the session."""

    total_turns: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    compaction_count: int = 0
    checkpoint_count: int = 0
    _start_time: float = field(default_factory=time.time, repr=False, compare=False)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def record_turn(
        self,
        turn: int,
        prompt_tokens_est: int,
        completion_tokens_est: int,
        elapsed_s: float,
        *,
        prompt_tokens_real: Optional[int] = None,
        completion_tokens_real: Optional[int] = None,
        compaction_triggered: bool = False,
        checkpoint_saved: bool = False,
        context_budget_used: float = 0.0,
    ) -> TurnStats:
        """Record a completed turn and return its TurnStats."""
        # Prefer real counts for session totals when available
        self.total_prompt_tokens += (
            prompt_tokens_real if prompt_tokens_real is not None else prompt_tokens_est
        )
        self.total_completion_tokens += (
            completion_tokens_real
            if completion_tokens_real is not None
            else completion_tokens_est
        )
        self.total_turns += 1

        if compaction_triggered:
            self.compaction_count += 1
        if checkpoint_saved:
            self.checkpoint_count += 1

        return TurnStats(
            turn=turn,
            prompt_tokens_est=prompt_tokens_est,
            completion_tokens_est=completion_tokens_est,
            prompt_tokens_real=prompt_tokens_real,
            completion_tokens_real=completion_tokens_real,
            compaction_triggered=compaction_triggered,
            checkpoint_saved=checkpoint_saved,
            elapsed_s=elapsed_s,
            context_budget_used=context_budget_used,
        )

    def record_compaction(self):
        """Explicitly record a compaction event (e.g. pre-flight)."""
        self.compaction_count += 1

    def record_checkpoint(self):
        """Explicitly record a checkpoint save."""
        self.checkpoint_count += 1

    @property
    def session_elapsed_s(self) -> float:
        return time.time() - self._start_time

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens
