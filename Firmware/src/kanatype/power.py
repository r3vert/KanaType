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

    The stamp keeps the accuracy the clock has RIGHT NOW; it is the restore
    that downgrades it to approximate. Stamping approximate=True here was
    wrong for the USB case, where CircuitPython fake-sleeps, the RTC keeps
    ticking, and the time on the other side is still exact.
    """
    try:
        import rtc

        from kanatype import clockstore

        return clockstore.save(rtc.RTC().datetime,
                               approximate=clockstore.approximate())
    except Exception:
        return False


def restore_time_after_sleep():
    """Put a stamped time back after waking. True if the RTC was restored.

    Leaves a RUNNING clock alone: on USB, CircuitPython does a fake deep sleep
    that keeps the RTC ticking, and the stored stamp would be the older value.

    A restore ALWAYS lands us on an approximate clock, so it flags the stamp on
    the way through. The gap is unknowable and its cause does not matter: a
    deep sleep, a RESET and a flat battery all look identical from up here.
    """
    try:
        import rtc

        clock = rtc.RTC()
        if clock.datetime.tm_year >= 2024:
            return False              # the RTC survived; do not clobber it
        from kanatype import clockstore

        saved = clockstore.load()
        if saved is None:
            return False
        clock.datetime = time.struct_time(saved[0])
        clockstore.mark_approximate()
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
