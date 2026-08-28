"""Clock — view and set the RTC.

Purpose #1: the RTC-across-deep-sleep experiment (set time -> Sleep -> WAKE
-> reopen Clock and see whether time survived). Purpose #2 later: quick-note
timestamps.

View mode:  live date/time; warns RTC UNSET if the year looks like a cold
            boot default. Enter -> set mode, exit combo -> menu.
Set mode:   LEFT/RIGHT pick field, UP/DOWN change it, Enter commits
            (seconds reset to 0), exit combo cancels.
"""
import time

import displayio
from adafruit_display_text import label

from kanatype import input as kt_input
from kanatype import layout, ui

# (name, char offset in its line, width in chars, min, max)
DATE_FIELDS = (("year", 0, 4, 2020, 2099), ("month", 5, 2, 1, 12), ("day", 8, 2, 1, 31))
TIME_FIELDS = (("hour", 0, 2, 0, 23), ("minute", 3, 2, 0, 59))
FIELDS = DATE_FIELDS + TIME_FIELDS

DATE_X = (layout.WIDTH - 10 * layout.CHAR_W) // 2  # "2026-08-15"
TIME_X = (layout.WIDTH - 8 * layout.CHAR_W) // 2   # "12:34:56"
DATE_Y = 20
TIME_Y = 36


def _days_in(year, month):
    days = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    if month == 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        days = 29
    return days


def _weekday(y, m, d):
    """Zeller -> tm_wday convention (0 = Monday)."""
    if m < 3:
        m += 12
        y -= 1
    k, j = y % 100, y // 100
    h = (d + 13 * (m + 1) // 5 + k + k // 4 + j // 4 + 5 * j) % 7  # 0 = Saturday
    return (h + 5) % 7


def run(ctx):
    try:
        import rtc

        clock = rtc.RTC()
    except Exception:
        from apps import stub

        stub(ctx, "CLOCK", "no RTC here")
        return

    f = ui.font("menu")
    group = displayio.Group()
    group.append(label.Label(f, text="Clock", color=0xFFFFFF,
                             x=layout.MENU_TITLE_X, y=layout.MENU_TITLE_Y))
    date_lbl = label.Label(f, text="", color=0xFFFFFF, x=DATE_X, y=DATE_Y)
    time_lbl = label.Label(f, text="", color=0xFFFFFF, x=TIME_X, y=TIME_Y)
    caret_lbl = label.Label(f, text="", color=0xFFFFFF, x=0, y=0)
    hint_lbl = label.Label(ui.font("jp"), text="", color=0xFFFFFF,
                           x=2, y=layout.SCREEN_HINT_Y)
    for lbl in (date_lbl, time_lbl, caret_lbl, hint_lbl):
        group.append(lbl)
    ctx.display.root_group = group

    editing = False
    field = 0
    buf = {}
    last_second = -1

    def show_view():
        # three labels change together; a torn frame here shows a half-updated
        # timestamp once a second
        with ui.frame():
            now = clock.datetime
            date_lbl.text = "%04d-%02d-%02d" % (now.tm_year, now.tm_mon, now.tm_mday)
            time_lbl.text = "%02d:%02d:%02d" % (now.tm_hour, now.tm_min, now.tm_sec)
            unset = now.tm_year < 2024
            hint_lbl.text = "RTC UNSET!  Enter: set" if unset else "Enter: set"

    def show_edit():
        # value + caret position + caret width all move at once
        with ui.frame():
            date_lbl.text = "%04d-%02d-%02d" % (buf["year"], buf["month"], buf["day"])
            time_lbl.text = "%02d:%02d:00" % (buf["hour"], buf["minute"])
            name, off, width, _lo, _hi = FIELDS[field]
            on_date = field < len(DATE_FIELDS)
            caret_lbl.x = (DATE_X if on_date else TIME_X) + off * layout.CHAR_W
            caret_lbl.y = (DATE_Y if on_date else TIME_Y) + 9
            caret_lbl.text = "-" * width
            hint_lbl.text = "arrows  Enter: ok"

    def bump(delta):
        name, _o, _w, lo, hi = FIELDS[field]
        span = hi - lo + 1
        buf[name] = lo + (buf[name] - lo + delta) % span
        if name in ("year", "month"):
            buf["day"] = min(buf["day"], _days_in(buf["year"], buf["month"]))

    show_view()
    while True:
        for ev in ctx.input.poll():
            code = ev.code
            if not editing:
                if code == kt_input.EXIT:
                    return
                if code == kt_input.ENTER:
                    now = clock.datetime
                    buf = {"year": max(now.tm_year, 2020), "month": now.tm_mon,
                           "day": now.tm_mday, "hour": now.tm_hour,
                           "minute": now.tm_min}
                    field = 0
                    editing = True
                    show_edit()
            else:
                if code == kt_input.EXIT:
                    editing = False
                    with ui.frame():
                        caret_lbl.text = ""
                        show_view()
                elif code == kt_input.LEFT:
                    field = (field - 1) % len(FIELDS)
                    show_edit()
                elif code == kt_input.RIGHT:
                    field = (field + 1) % len(FIELDS)
                    show_edit()
                elif code == kt_input.UP:
                    bump(1)
                    show_edit()
                elif code == kt_input.DOWN:
                    bump(-1)
                    show_edit()
                elif code == kt_input.ENTER:
                    day = min(buf["day"], _days_in(buf["year"], buf["month"]))
                    clock.datetime = time.struct_time((
                        buf["year"], buf["month"], day, buf["hour"], buf["minute"],
                        0, _weekday(buf["year"], buf["month"], day), -1, -1,
                    ))
                    editing = False
                    with ui.frame():
                        caret_lbl.text = ""
                        show_view()
        if not editing:
            now = clock.datetime
            if now.tm_sec != last_second:
                last_second = now.tm_sec
                show_view()
        time.sleep(0.05)
