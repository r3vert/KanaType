"""Power helpers: nap mode primitives (quick-note M2) and an idle timer.

Every call is defensive — on the dev rig or under future CircuitPython
versions a missing capability should degrade, never crash.
"""
import time

import microcontroller

FULL_HZ = 125_000_000
NAP_HZ = 48_000_000


def nap(display):
    """Screen off (~10 uA panel) + underclock. keypad scanning keeps running."""
    try:
        display.sleep()
    except Exception:
        pass
    try:
        microcontroller.cpu.frequency = NAP_HZ
    except Exception:
        pass


def wake(display):
    try:
        microcontroller.cpu.frequency = FULL_HZ
    except Exception:
        pass
    try:
        display.wake()
    except Exception:
        pass


class IdleTimer:
    def __init__(self, seconds):
        self.seconds = seconds
        self.reset()

    def reset(self):
        self._t0 = time.monotonic()

    def expired(self):
        return time.monotonic() - self._t0 >= self.seconds
