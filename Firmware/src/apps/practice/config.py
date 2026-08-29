"""Practice config screen: category toggles + mode/font settings + start.

Settings persist across sessions via kanatype.settings (nvm); 'Reset'
restores DEFAULTS. Saved on Start, on Reset, and on backing out after changes.
"""
import time

from kanatype import input as kt_input
from kanatype import layout, settings, ui

DEFAULTS = {"H": True, "K": False, "HC": False, "KC": False,
            "instant": True, "correct": False, "font": layout.PROMPT_FONTS[0]}

# Row order, defined ONCE. run_config dispatches on these names rather than on
# bare indices: adding a row used to mean renumbering an if/elif chain by hand,
# which is a silent off-by-one waiting to happen. preflight checks the two
# lists stay the same length.
ROW_KEYS = ("H", "K", "HC", "KC", "instant", "correct", "font", "start", "reset")

FONT_CYCLE = layout.PROMPT_FONTS
# Show what the font IS, not its position in a tuple: "Font 1" said nothing
# about what you were picking.
FONT_NAME = dict(zip(FONT_CYCLE, layout.PROMPT_FONT_NAMES))


def _labels(opts):
    def box(key):
        return "[x]" if opts[key] else "[ ]"

    return [
        "%s Hiragana" % box("H"),
        "%s Katakana" % box("K"),
        "%s Hira combos" % box("HC"),
        "%s Kata combos" % box("KC"),
        "Mode: %s" % ("Instant" if opts["instant"] else "Confirm"),
        # Bypass: a miss shows the answer and Space/Enter moves on.
        # Correct: you must clear the wrong input and type the right answer,
        # the way the DJT Kana site drills it.
        "Correction Type: %s" % ("Correct" if opts["correct"] else "Bypass"),
        "Font: %s" % FONT_NAME[opts["font"]],
        "Start",
        "Reset to defaults",
    ]


def _pick_font(ctx, current):
    """Font submenu: numbered list + the highlighted font's kana rendered at
    its true drill size on the right. Returns a role, or None for Back."""
    import displayio  # noqa: F401  (label needs displayio initialized)
    from adafruit_display_text import label as _label

    menu = ui.Menu("Font", [FONT_NAME[r] for r in FONT_CYCLE] + ["Back"],
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
    # No standing hint in the status corner -- it is for transient messages
    # ("Pick a category!", "Defaults restored"), not a permanent legend.
    menu = ui.Menu("Practice", _labels(opts))
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
                key = ROW_KEYS[menu.index]
                if key in ("H", "K", "HC", "KC", "instant", "correct"):
                    opts[key] = not opts[key]
                    refresh()
                elif key == "font":
                    role = _pick_font(ctx, opts["font"])
                    with ui.frame():
                        if role is not None:
                            opts["font"] = role
                        ctx.display.root_group = menu.group  # back from picker
                        refresh()
                elif key == "start":
                    if any(opts[k] for k in ("H", "K", "HC", "KC")):
                        settings.save_practice(opts)
                        return opts
                    menu.set_status("Pick a category!")
                else:  # reset
                    opts.clear()
                    opts.update(DEFAULTS)
                    settings.save_practice(opts)
                    refresh()
                    menu.set_status("Defaults restored")
        time.sleep(0.02)
