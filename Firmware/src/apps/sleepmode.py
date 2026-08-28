"""Manual sleep — the software 'off switch' (battery is not removable).

Screen off, then the deepest sleep available (~1.5-2.5 mA on battery).
ONLY the WAKE button wakes it: WAKE drives COL8/A3 to 3.3 V through R11
against the board's 8.2 k pull-down — no other key can, so pocket presses
are harmless. Waking restarts code.py -> launcher menu.

While USB-connected, CircuitPython keeps the connection instead of truly
deep-sleeping (its documented behavior); the screen still turns off and
WAKE still wakes — battery savings just don't apply until unplugged.

THE RTC DOES NOT SURVIVE A REAL DEEP SLEEP. Deep sleep cuts power to nearly
all of the RP2040 and there is no battery-backed RTC domain, so the clock
comes back unset (confirmed on hardware 2026-08-28). The wall clock is
stamped into nvm here and restored by code.py on the way up, flagged
approximate because the time spent asleep is unknowable.
"""
import time


def run(ctx):
    import board
    import supervisor

    from kanatype import power, ui

    ctx.display.root_group = ui.screen(["SLEEP", "", "WAKE button", "wakes me up"])
    # Stamp the clock BEFORE the message delay, so the stored time is as close
    # to the moment of sleeping as we can make it.
    power.save_time_for_sleep()
    time.sleep(1.5)  # let the message be seen
    power.screen_off(ctx.display)   # no underclock: we are about to power down

    # Free the matrix pins: the wake alarm needs A3 (COL8) for itself.
    if hasattr(ctx.input, "deinit"):
        ctx.input.deinit()

    try:
        import alarm

        wake = alarm.pin.PinAlarm(pin=board.A3, value=True, pull=False)
        alarm.exit_and_deep_sleep_until_alarms(wake)
        # never returns — wake restarts boot.py/code.py from the top
    except Exception:
        # alarm unavailable/refused: low-power poll of COL8 directly. This path
        # never loses power, so it underclocks instead and the RTC keeps time.
        import digitalio

        power.nap(ctx.display)

        col8 = digitalio.DigitalInOut(board.A3)
        col8.switch_to_input()  # external 8.2k pull-down holds it low
        while not col8.value:
            time.sleep(0.1)
        supervisor.reload()
