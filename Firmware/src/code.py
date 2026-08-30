"""KanaType launcher (M0).

Context-smart boot: USB host -> 2 s splash defaulting into keyboard mode;
battery -> quick-note default. Any key during the splash opens the full menu.
One app is imported lazily per boot; when it returns we supervisor.reload()
for a clean heap. Serial keys: arrows/jk move, Enter selects.
"""
import time

import displayio
import supervisor

from kanatype import Ctx, hw, layout
from kanatype import input as kt_input
from kanatype import storage, ui

APPS = [
    ("Keyboard", "apps.keyboard"),
    ("Practice", "apps.practice"),
    ("Quick note", "apps.quicknote"),
    ("Vault", "apps.vault"),
    ("Sleep", "apps.sleepmode"),
]
# Clock is NOT in the list: the home screen shows the time, and Enter on the
# clock panel (the focus target one past the last app) opens it. Keeping a
# "Clock" row as well would be two doors into the same room.
CLOCK_APP = "apps.clock"
# Context-smart auto-launch (2 s splash into the default app) is DISABLED for
# debugging: it read as a phantom menu click, especially with the countdown
# status clipped off-screen. Menu is purely interactive; the cursor still
# starts on the context default. Revisit once the UI settles (PLAN.md M1).


# Boot timings go to the serial console. PuTTY can only attach AFTER the device
# is already up, so a single print at boot is never seen -- the line is instead
# REPEATED while the menu sits idle. Set False when you're done measuring.
DEBUG_BOOT_TIMING = True
BOOT_TIMING_REPEAT_S = 3.0


def reboot(display):
    """Blank + release the display, then reload. Displays persist across
    supervisor.reload(), and an unclaimed display shows CircuitPython's
    serial console — releasing it keeps the panel black until the next
    boot's launcher takes over."""
    try:
        display.root_group = displayio.Group()
        time.sleep(0.05)  # let the blank frame reach the panel
    except Exception:
        pass
    displayio.release_displays()
    supervisor.reload()


def import_app(dotted):
    mod = __import__(dotted)
    for part in dotted.split(".")[1:]:
        mod = getattr(mod, part)
    return mod


def boot_line(marks, t_menu, steps=None):
    """One-line boot breakdown. marks = (t0, t_display, t_input).
    steps = [(name, seconds)] detail for what `menu` was spent on."""
    t0, t_disp, t_input = marks
    line = "boot: display %.0fms  input %.0fms  menu %.0fms" % (
        (t_disp - t0) * 1000, (t_input - t_disp) * 1000, (t_menu - t_input) * 1000)
    if steps:
        line += "  [%s]" % " ".join("%s %.0f" % (n, v * 1000) for n, v in steps)
    # nvm SIZE has never been recorded, and it is the ceiling on everything
    # that persists: settings use 122 bytes today and the parked stats screen
    # would want per-group counters on top. Report it once rather than
    # guessing. Costs one import that the settings path makes anyway.
    try:
        import microcontroller

        line += "  nvm %dB" % len(microcontroller.nvm)
    except Exception:
        pass
    return line


def open_clock():
    """(rtc object or None, approximate flag).

    The flag is read ONCE: only the Clock app changes it, and reaching that
    needs leaving the launcher. Reading nvm in the 20 ms poll loop would be
    50 flash reads a second for an answer that cannot change. clockstore
    rather than settings, because settings drags in macros + keytable and
    this is the boot path.
    """
    try:
        import rtc

        from kanatype import clockstore

        return rtc.RTC(), clockstore.approximate()
    except Exception:
        return None, False


def pick_app(ctx, marks=None):
    # Menu appears IMMEDIATELY. USB enumeration takes ~0.3-0.8s on a cold
    # boot, so the status/context resolves in the background instead of
    # blocking on a black screen (soft reloads resolve instantly).
    #
    # Each stage is timed separately: the BDF loader has no glyph index, so
    # where the time goes is not guessable (see ui.preload).
    steps = []
    t = time.monotonic()
    ui.font("menu")                     # open + header parse only
    steps.append(("font", time.monotonic() - t))

    t = time.monotonic()
    # Every glyph the home screen can show, in one file pass, before any Label
    # asks for one and triggers a scan of its own. Digits and separators are
    # for the clock, "~" marks an approximate one.
    ui.preload(layout.TITLE + layout.MENU_CURSOR + "0123456789:-USBAT"
               + "".join(name for name, _ in APPS), "jp")
    ui.preload("0123456789:~-", "menu")
    steps.append(("glyphs", time.monotonic() - t))

    t = time.monotonic()
    menu = ui.Home([name for name, _ in APPS], ctx.usb)
    clock, approx = open_clock()
    now = clock.datetime if clock else None
    menu.set_clock(now, approx)
    steps.append(("labels", time.monotonic() - t))

    def show_power(on_usb):
        menu.set_power(on_usb)

    t = time.monotonic()
    with ui.frame():
        menu.index = 0 if ctx.usb else 2  # cursor starts on the context default
        menu.move(0)  # refresh cursor
        ctx.display.root_group = menu.group
    steps.append(("paint", time.monotonic() - t))

    # The menu is on the panel now, so THIS is the real "ready" moment. Timing
    # it here instead of when pick_app returns keeps `menu` a boot number rather
    # than a measure of how long the user browsed.
    line = boot_line(marks, time.monotonic(), steps) if marks else None
    if line:
        print(line)
    next_print = time.monotonic() + BOOT_TIMING_REPEAT_S

    # USB state is polled for as long as the menu is up, not just once:
    #   shown is None -> still resolving (tilde). We commit the moment USB
    #   appears, or when the grace period expires.
    #   after that -> keep the badge honest if the cable comes or goes, but
    #   never yank the cursor again; that only happens on the first resolve.
    minute = [now.tm_min if now else -1]
    deadline = time.monotonic() + 1.5
    shown = True if ctx.usb else None
    hopped = ctx.usb
    moved = False
    while True:
        if line and DEBUG_BOOT_TIMING and time.monotonic() >= next_print:
            # uptime distinguishes a repeat from a fresh boot
            print("%s  (uptime %.0fs)" % (line, time.monotonic()))
            next_print = time.monotonic() + BOOT_TIMING_REPEAT_S
        live = supervisor.runtime.usb_connected
        if shown is None:
            if live or time.monotonic() >= deadline:
                shown = live
                ctx.usb = live
                with ui.frame():          # icon + cursor hop together
                    show_power(live)
                    if live and not moved and not hopped:
                        menu.index = 0
                        menu.move(0)
                        hopped = True
        elif live != shown:
            shown = live
            ctx.usb = live
            show_power(live)
        for ev in ctx.input.poll():
            if ev.code in (kt_input.UP, "k"):
                menu.move(-1)
                moved = True
            elif ev.code in (kt_input.DOWN, "j"):
                menu.move(1)
                moved = True
            elif ev.code == kt_input.ENTER:
                return CLOCK_APP if menu.clock_selected else APPS[menu.index][1]
        # repaint the clock only when the MINUTE rolls over; once a second
        # would be 60x the redraws for the same picture
        if clock is not None:
            live_now = clock.datetime
            if live_now.tm_min != minute[0]:
                minute[0] = live_now.tm_min
                menu.set_clock(live_now, approx)
        time.sleep(0.02)


def main():
    t0 = time.monotonic()
    display = hw.display()
    # Paint the artwork BEFORE the expensive work (font parse, matrix init).
    # It costs almost nothing and replaces the black screen with something.
    display.root_group = ui.splash_art()
    t_disp = time.monotonic()

    inp = kt_input.get_input()          # matrix + serial drivers
    t_input = time.monotonic()

    # Deep sleep resets the RP2040's RTC, so a woken device comes up with no
    # date. sleepmode.py stamped the time into nvm; put it back before any app
    # can read the clock. No-op when the RTC is already running.
    from kanatype import power

    power.restore_time_after_sleep()

    ctx = Ctx(display, inp, supervisor.runtime.usb_connected, storage.writable())
    # first font load happens in here; pick_app prints the breakdown the moment
    # the menu is painted, and reprints it while DEBUG_BOOT_TIMING is on
    target = pick_app(ctx, (t0, t_disp, t_input))
    ctx.display.root_group = ui.splash_art()
    try:
        import_app(target).run(ctx)
    except Exception as exc:  # app crash -> show it, don't brick the device
        ctx.display.root_group = ui.screen(
            ["APP ERROR", "", str(exc)[:40], "", "Any key: reboot to menu"]
        )
        while not ctx.input.poll():
            time.sleep(0.05)
    reboot(ctx.display)


main()
