"""Tests for client-side backend gate priority."""

from __future__ import annotations

import threading
import time
import unittest

from core.backend_gate import BackendGate, configure_default_gate, reset_default_gate


class TestBackendGate(unittest.TestCase):
    def tearDown(self):
        reset_default_gate()

    def test_interactive_jumps_ahead_of_dream(self):
        gate = BackendGate(orch_slots=1)
        order: list[str] = []
        both_waiting = threading.Barrier(3)  # main + 2 workers

        def dream_job():
            both_waiting.wait(timeout=2.0)
            with gate.hold("orch", priority="dream"):
                order.append("dream")
                time.sleep(0.05)

        def interactive_job():
            both_waiting.wait(timeout=2.0)
            with gate.hold("orch", priority="interactive"):
                order.append("interactive")
                time.sleep(0.05)

        # Occupy the lane so both workers queue
        self.assertTrue(gate.acquire("orch", priority="background"))
        t_dream = threading.Thread(target=dream_job)
        t_inter = threading.Thread(target=interactive_job)
        t_dream.start()
        t_inter.start()
        both_waiting.wait(timeout=2.0)
        time.sleep(0.05)  # let both enter acquire wait queues
        gate.release("orch")
        t_inter.join(timeout=2.0)
        t_dream.join(timeout=2.0)
        self.assertEqual(order[0], "interactive", f"order={order}")
        self.assertEqual(set(order), {"interactive", "dream"})

    def test_configure_default(self):
        g = configure_default_gate(enabled=True, orch_slots=2)
        self.assertEqual(g.lanes["orch"].slots, 2)
        reset_default_gate()


if __name__ == "__main__":
    unittest.main()
