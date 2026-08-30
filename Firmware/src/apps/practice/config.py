"""Practice config screen: category toggles + mode/font settings + start.

Settings persist across sessions via kanatype.settings (nvm); 'Reset'
restores DEFAULTS. Saved on Start, on Reset, and on backing out after changes.
"""
import time

from kanatype import input as kt_input
from kanatype import kana, layout, settings, ui

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


def _labels(opts, masks):
    def box(key):
        return "[x]" if opts[key] else "[ ]"

    def cat(key, name):
        """"[x] Hiragana" while every group is on, "[x] Hiragana 9/16" once it
        is partial. Showing 16/16 on every row all the time would be noise on a
        screen this narrow -- the count is only news when it is not the whole
        set."""
        on, total = kana.mask_count(key, masks.get(key, kana.full_mask(key)))
        suffix = "" if on == total else " %d/%d" % (on, total)
        return "%s %s%s" % (box(key), name, suffix)

    return [
        cat("H", "Hiragana"),
        cat("K", "Katakana"),
        cat("HC", "Hira combos"),
        cat("KC", "Kata combos"),
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
    masks = settings.load_groups()
    loaded_masks = dict(masks)
    # No standing hint in the status corner -- it is for transient messages
    # ("Pick a category!", "Defaults restored"), not a permanent legend.
    menu = ui.Menu("Practice", _labels(opts, masks))
    ctx.display.root_group = menu.group

    def refresh():
        menu.set_items(_labels(opts, masks))

    while True:
        for ev in ctx.input.poll():
            if ev.code in (kt_input.UP, "k"):
                menu.move(-1)
            elif ev.code in (kt_input.DOWN, "j"):
                menu.move(1)
            elif ev.code == kt_input.RIGHT:
                # descend into a category's groups. RIGHT rather than a held
                # Enter: ctx.input reports presses only, so an app cannot time
                # a hold (see apps/practice/groups.py).
                key = ROW_KEYS[menu.index]
                if key in kana.CATEGORIES:
                    from apps.practice import groups as groups_ui

                    masks[key] = groups_ui.run(ctx, key, masks[key])
                    with ui.frame():
                        ctx.display.root_group = menu.group
                        refresh()
            elif ev.code == kt_input.EXIT:
                if opts != loaded:
                    settings.save_practice(opts)
                if masks != loaded_masks:
                    settings.save_groups(masks)
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
                    # An enabled category with every group switched off would
                    # contribute nothing, so check the DECK, not the checkboxes
                    # -- otherwise Start could hand the drill an empty deck.
                    if kana.build_deck([k for k in kana.CATEGORIES if opts[k]],
                                       masks):
                        settings.save_practice(opts)
                        settings.save_groups(masks)
                        opts["masks"] = masks
                        return opts
                    menu.set_status("Pick a category!")
                else:  # reset
                    opts.clear()
                    opts.update(DEFAULTS)
                    masks.clear()
                    masks.update({c: kana.full_mask(c)
                                  for c in kana.CATEGORIES})
                    settings.save_practice(opts)
                    refresh()
                    menu.set_status("Defaults restored")
        time.sleep(0.02)
