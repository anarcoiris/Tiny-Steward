"""Meta-guidance engine for Tiny Steward.

Provides stateless evaluation of per-turn stats and recent session history
to emit inline hints when thresholds are crossed.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.stats import TurnStats, SessionStats


class GuidanceEngine:
    """Evaluates metrics to produce UI hints."""

    def evaluate(
        self,
        turn_stats: 'TurnStats',
        session_stats: 'SessionStats',
        recent_errors: int,
        help_calls: int,
        turns_this_task: int,
    ) -> list[tuple[str, str]]:
        """Evaluate the current state and return a list of (level, message) hints."""
        hints = []

        # Context pressure
        if turn_stats.context_budget_used > 0.75 and not turn_stats.compaction_triggered:
            hints.append(("warn", f"Context at {int(turn_stats.context_budget_used * 100)}% capacity — consider /compact soon if you change topics"))

        # Slow turn (wall-clock)
        if turn_stats.elapsed_s > 30.0:
            hints.append(("info", f"Turn took {turn_stats.elapsed_s:.1f}s — LLM under load or context is large"))

        # Low generation speed
        if turn_stats.tokens_per_sec > 0 and turn_stats.tokens_per_sec < 10.0:
            hints.append(("warn", f"Generation slowed to {turn_stats.tokens_per_sec:.1f} tok/s — model may be memory-pressured"))

        # High error rate
        if recent_errors >= 2:
            hints.append(("error", "Multiple action errors recently — check endpoint health or consider /help"))

        # Reasoning loop too long
        if turns_this_task > 8:
            hints.append(("warn", "Agent reasoning loop is long — you may need to rephrase the task or /compact context"))

        # Repeated help (crude check based on count for this task)
        if help_calls >= 3:
            hints.append(("info", "Repeated help() calls — you may need to author a new skill for this topic"))

        return hints
