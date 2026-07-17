"""Client-side backend gate — serialize orch / atomic / embed lanes.

Complements llama.cpp ``--parallel 1`` + HTTP 503 retries. Interactive
acquires jump ahead of dream work so consolidation never starves the REPL.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator, Literal

Lane = Literal["orch", "atomic", "embed"]
Priority = Literal["interactive", "dream", "background"]

_PRIORITY_RANK = {"interactive": 0, "dream": 1, "background": 2}


@dataclass
class _Waiter:
    priority: Priority
    event: threading.Event = field(default_factory=threading.Event)
    cancelled: bool = False


class LaneGate:
    """FIFO-within-priority semaphore for one backend lane."""

    def __init__(self, name: Lane, slots: int = 1):
        self.name = name
        self.slots = max(1, int(slots))
        self._lock = threading.Lock()
        self._in_use = 0
        self._waiters: list[_Waiter] = []

    def acquire(self, priority: Priority = "interactive", timeout: float | None = None) -> bool:
        deadline = None if timeout is None else time.monotonic() + timeout
        waiter = _Waiter(priority=priority)
        with self._lock:
            if self._in_use < self.slots and not self._has_higher_or_equal_waiter(priority):
                self._in_use += 1
                return True
            self._waiters.append(waiter)
            self._waiters.sort(key=lambda w: _PRIORITY_RANK.get(w.priority, 9))

        while True:
            remaining = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    with self._lock:
                        if waiter in self._waiters:
                            self._waiters.remove(waiter)
                        waiter.cancelled = True
                    return False
            if waiter.event.wait(timeout=remaining if remaining is not None else 0.5):
                with self._lock:
                    if waiter.cancelled:
                        return False
                    # Slot was reserved for us by release()
                    return True
            # Spurious / timeout slice — re-check if we can take a free slot
            with self._lock:
                if waiter.cancelled:
                    return False
                if self._in_use < self.slots and self._waiters and self._waiters[0] is waiter:
                    self._waiters.pop(0)
                    self._in_use += 1
                    return True

    def release(self) -> None:
        with self._lock:
            self._in_use = max(0, self._in_use - 1)
            while self._waiters and self._in_use < self.slots:
                nxt = self._waiters.pop(0)
                if nxt.cancelled:
                    continue
                self._in_use += 1
                nxt.event.set()
                break

    def _has_higher_or_equal_waiter(self, priority: Priority) -> bool:
        rank = _PRIORITY_RANK.get(priority, 9)
        return any(_PRIORITY_RANK.get(w.priority, 9) <= rank for w in self._waiters)

    @contextmanager
    def hold(self, priority: Priority = "interactive", timeout: float | None = None) -> Generator[None, None, None]:
        ok = self.acquire(priority=priority, timeout=timeout)
        if not ok:
            raise TimeoutError(f"backend gate '{self.name}' timed out (priority={priority})")
        try:
            yield
        finally:
            self.release()


class BackendGate:
    """Named gates for orch / atomic / embed."""

    def __init__(
        self,
        *,
        orch_slots: int = 1,
        atomic_slots: int = 1,
        embed_slots: int = 1,
        enabled: bool = True,
    ):
        self.enabled = enabled
        self.lanes: dict[Lane, LaneGate] = {
            "orch": LaneGate("orch", orch_slots),
            "atomic": LaneGate("atomic", atomic_slots),
            "embed": LaneGate("embed", embed_slots),
        }

    def acquire(self, lane: Lane, priority: Priority = "interactive", timeout: float | None = None) -> bool:
        if not self.enabled:
            return True
        return self.lanes[lane].acquire(priority=priority, timeout=timeout)

    def release(self, lane: Lane) -> None:
        if not self.enabled:
            return
        self.lanes[lane].release()

    @contextmanager
    def hold(
        self,
        lane: Lane,
        priority: Priority = "interactive",
        timeout: float | None = None,
    ) -> Generator[None, None, None]:
        if not self.enabled:
            yield
            return
        with self.lanes[lane].hold(priority=priority, timeout=timeout):
            yield


# Process-wide default (configured from steward.py / config.yaml)
_default_gate: BackendGate | None = None


def configure_default_gate(
    *,
    enabled: bool = True,
    orch_slots: int = 1,
    atomic_slots: int = 1,
    embed_slots: int = 1,
) -> BackendGate:
    global _default_gate
    _default_gate = BackendGate(
        enabled=enabled,
        orch_slots=orch_slots,
        atomic_slots=atomic_slots,
        embed_slots=embed_slots,
    )
    return _default_gate


def get_gate() -> BackendGate:
    global _default_gate
    if _default_gate is None:
        _default_gate = BackendGate()
    return _default_gate


def reset_default_gate() -> None:
    """Test helper — clear the process-wide gate."""
    global _default_gate
    _default_gate = None
