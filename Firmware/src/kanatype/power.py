"""Power helpers: nap mode primitives (quick-note M2) and an idle timer.

Every call is defensive — on the dev rig or under future CircuitPython
versions a missing capability should degrade, never crash.
"""
import time

import microcontroller

FULL_HZ = 125_000_000
NAP_HZ = 48_000_000


def screen_off(display):
    """Panel off (~10 uA), clocks untouched.

    Split out of nap() for the deep-sleep path: underclocking milliseconds
    before the chip powers down buys nothing, and it put a clock-tree change
    right next to the RTC-across-sleep question. Keep the two separate so the
    sleep path has one fewer variable in it.
    """
    try:
        display.sleep()
    except Exception:
        pass


def nap(display):
    """Screen off (~10 uA panel) + underclock. keypad scanning keeps running."""
    screen_off(display)
    try:
        microcontroller.cpu.frequency = NAP_HZ
    except Exception:
        pass


def save_time_for_sleep():
    """Stamp the RTC into nvm before a deep sleep. True if stored.

    Deep sleep resets the RP2040's RTC (no battery-backed domain; CircuitPython
    cuts power to nearly all of the chip), so this is the only way the time
    survives. Verified on hardware 2026-08-28.
    """
    try:
        import rtc

        from kanatype import settings

        return settings.save_clock(rtc.RTC().datetime, approximate=True)
    except Exception:
        return False


def restore_time_after_sleep():
    """Put a stamped time back after waking. True if the RTC was restored.

    Leaves a RUNNING clock alone: on USB, CircuitPython does a fake deep sleep
    that keeps the RTC ticking, and the stored stamp would be the older value.
    """
    try:
        import rtc

        from kanatype import settings

        clock = rtc.RTC()
        if clock.datetime.tm_year >= 2024:
            return False              # the RTC survived; do not clobber it
        saved = settings.load_clock()
        if saved is None:
            return False
        clock.datetime = time.struct_time(saved[0])
        return True
    except Exception:
        return False


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
