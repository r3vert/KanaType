"""Practice config screen: category toggles + mode/font settings + start.

Settings persist across sessions via kanatype.settings (nvm); 'Reset'
restores DEFAULTS. Saved on Start, on Reset, and on backing out after changes.
"""
import time

from kanatype import input as kt_input
from kanatype import layout, settings, ui

DEFAULTS = {"H": True, "K": False, "HC": False, "KC": False,
            "instant": True, "font": layout.PROMPT_FONTS[0]}

FONT_CYCLE = layout.PROMPT_FONTS
FONT_NUM = dict((role, str(i + 1)) for i, role in enumerate(FONT_CYCLE))


def _labels(opts):
    def box(key):
        return "[x]" if opts[key] else "[ ]"

    return [
        "%s Hiragana" % box("H"),
        "%s Katakana" % box("K"),
        "%s Hira combos" % box("HC"),
        "%s Kata combos" % box("KC"),
        "Mode: %s" % ("Instant" if opts["instant"] else "Confirm"),
        "Font: %s" % FONT_NUM[opts["font"]],
        "Start",
        "Reset to defaults",
    ]


def _pick_font(ctx, current):
    """Font submenu: numbered list + the highlighted font's kana rendered at
    its true drill size on the right. Returns a role, or None for Back."""
    import displayio  # noqa: F401  (label needs displayio initialized)
    from adafruit_display_text import label as _label

    menu = ui.Menu("Font", ["Font %s" % FONT_NUM[r] for r in FONT_CYCLE] + ["Back"],
                   status="")
    previews = []
    for role in FONT_CYCLE:
        adv, scale, _y = layout.DRILL_PROMPT_STYLES[role]
        f = ui.try_font(role)
        if f is not None:
            lbl = _label.Label(f, text="あ", color=0xFFFFFF, scale=scale,
                               x=layout.WIDTH - 8 - adv * scale, y=34)
        else:
            lbl = _label.Label(ui.font("menu"), text="n/a", color=0xFFFFFF,
                               x=layout.WIDTH - 8 - 24, y=34)
        lbl.hidden = True
        previews.append(lbl)
        menu.group.append(lbl)

    def show_preview():
        # up to 5 visibility flags flip together -> one frame, no flicker
        with ui.frame():
            for i, lbl in enumerate(previews):
                lbl.hidden = menu.index != i  # Back row: no preview

    with ui.frame():
        menu.index = FONT_CYCLE.index(current)
        menu.move(0)
        show_preview()
    ctx.display.root_group = menu.group

    while True:
        for ev in ctx.input.poll():
            if ev.code in (kt_input.UP, "k"):
                with ui.frame():
                    menu.move(-1)
                    show_preview()
            elif ev.code in (kt_input.DOWN, "j"):
                with ui.frame():
                    menu.move(1)
                    show_preview()
            elif ev.code == kt_input.EXIT:
                return None
            elif ev.code in (kt_input.ENTER, kt_input.SPACE):
                if menu.index < len(FONT_CYCLE):
                    return FONT_CYCLE[menu.index]
                return None  # Back
        time.sleep(0.02)


def run_config(ctx):
    """Returns the opts dict, or None if the user backed out to the menu."""
    opts = settings.load_practice() or dict(DEFAULTS)
    loaded = dict(opts)
    menu = ui.Menu("Practice", _labels(opts), status="Enter: toggle")
    ctx.display.root_group = menu.group

    def refresh():
        menu.set_items(_labels(opts))

    while True:
        for ev in ctx.input.poll():
            if ev.code in (kt_input.UP, "k"):
                menu.move(-1)
            elif ev.code in (kt_input.DOWN, "j"):
                menu.move(1)
            elif ev.code == kt_input.EXIT:
                if opts != loaded:
                    settings.save_practice(opts)
                return None
            elif ev.code in (kt_input.ENTER, kt_input.SPACE):
                i = menu.index
                if i < 4:
                    key = ("H", "K", "HC", "KC")[i]
                    opts[key] = not opts[key]
                    refresh()
                elif i == 4:
                    opts["instant"] = not opts["instant"]
                    refresh()
                elif i == 5:
                    role = _pick_font(ctx, opts["font"])
                    with ui.frame():
                        if role is not None:
                            opts["font"] = role
                        ctx.display.root_group = menu.group  # back from picker
                        refresh()
                elif i == 6:  # Start
                    if any(opts[k] for k in ("H", "K", "HC", "KC")):
                        settings.save_practice(opts)
                        return opts
                    menu.set_status("Pick a category!")
                else:  # Reset to defaults
                    opts.clear()
                    opts.update(DEFAULTS)
                    settings.save_practice(opts)
                    refresh()
                    menu.set_status("Defaults restored")
        time.sleep(0.02)
