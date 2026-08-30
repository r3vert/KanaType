"""Practice stats: accuracy per category, and per group inside one.

Opened from the drill with the LAYER key (right of the spacebar). NOT the MENU
key the mockup imagined: MENU already maps to app code "exit", which is how the
drill returns to config, and that is confirmed on hardware. LAYER is the only
app code the practice app does not already use.

Counting is CORRECT-FIRST-TRY over ANSWERED, matching the score fraction on the
drill screen, so the two can never disagree.

Drawing on a 1-bit panel: a bar is a SOLID fill for the achieved part plus a
50% checkerboard for the rest. The dither reads as grey beside solid white,
and keeping the full-width scale visible is what makes a short bar read as "a
small share" rather than just a small mark. A category with nothing answered
shows "-", not "0%" -- untried and failed are very different things when you
are deciding what to drill next.
"""
import time

import displayio
from adafruit_display_text import label

from kanatype import input as kt_input
from kanatype import kana, layout, ui

WHITE = 0xFFFFFF
NAMES = {"H": "Hiragana", "K": "Katakana",
         "HC": "Hira combos", "KC": "Kata combos"}


def record(stats, kana_text, correct):
    """Fold one answer into the tracker, keyed by the prompt's group."""
    key = kana.group_of(kana_text)
    if key is None:
        return
    entry = stats.get(key)
    if entry is None:
        entry = stats[key] = [0, 0]
    entry[1] += 1
    if correct:
        entry[0] += 1


def totals(stats, category=None):
    """(correct, answered) over everything, or over one category."""
    c = a = 0
    for (cat, _row), (ec, ea) in stats.items():
        if category is None or cat == category:
            c += ec
            a += ea
    return c, a


class _Canvas:
    """Shared bitmap for bars and cursors, behind the labels."""

    def __init__(self, group):
        self.bmp = displayio.Bitmap(layout.WIDTH, layout.HEIGHT, 2)
        pal = displayio.Palette(2)
        pal[0] = 0x000000
        pal[1] = WHITE
        group.append(displayio.TileGrid(self.bmp, pixel_shader=pal))

    def clear(self):
        self.bmp.fill(0)

    def bar(self, x, y, w, h, frac):
        filled = int(round(w * max(0.0, min(1.0, frac))))
        for yy in range(y, min(y + h, layout.HEIGHT)):
            for xx in range(x, min(x + w, layout.WIDTH)):
                self.bmp[xx, yy] = (1 if (xx - x) < filled
                                    or (xx + yy) % 2 == 0 else 0)

    def line(self, x, y, w, on):
        if 0 <= y < layout.HEIGHT:
            for xx in range(x, min(x + w, layout.WIDTH)):
                self.bmp[xx, y] = 1 if on else 0


def _overview(ctx, stats, cats):
    """Category list. Returns a category to drill into, or None to leave."""
    f = ui.font("jp")
    group = displayio.Group()
    canvas = _Canvas(group)
    title = label.Label(f, text="Stats", color=WHITE, x=2,
                        y=layout.STATS_TITLE_Y)
    summary = label.Label(f, text="", color=WHITE, x=0, y=layout.STATS_TITLE_Y)
    group.append(title)
    group.append(summary)

    c, a = totals(stats)
    text = "%d/%d" % (c, a)
    summary.text = text
    summary.x = layout.STATS_PCT_RIGHT - len(text) * layout.JP_CHAR_W

    cursors = []
    pcts = []
    for i, cat in enumerate(cats):
        y = layout.stats_row_y(i)
        cur = label.Label(f, text=">", color=WHITE,
                          x=layout.STATS_NAME_X - 2, y=y)
        cur.hidden = True
        cursors.append(cur)
        group.append(cur)
        group.append(label.Label(f, text=NAMES[cat], color=WHITE,
                                 x=layout.STATS_NAME_X + 4, y=y))
        pct = label.Label(f, text="", color=WHITE, x=0, y=y)
        pcts.append(pct)
        group.append(pct)

    index = [0]

    def paint():
        with ui.frame():
            canvas.clear()
            for i, cat in enumerate(cats):
                y = layout.stats_row_y(i)
                cc, ca = totals(stats, cat)
                canvas.bar(layout.STATS_BAR_X, y - layout.STATS_BAR_H // 2,
                           layout.STATS_BAR_W, layout.STATS_BAR_H,
                           (float(cc) / ca) if ca else 0.0)
                text = ("%d%%" % int(round(100.0 * cc / ca))) if ca else "-"
                pcts[i].text = text
                pcts[i].x = (layout.STATS_PCT_RIGHT
                             - len(text) * layout.JP_CHAR_W)
                cursors[i].hidden = i != index[0]

    paint()
    previous = ctx.display.root_group
    ctx.display.root_group = group
    try:
        while True:
            for ev in ctx.input.poll():
                code = ev.code
                if code in (kt_input.EXIT, kt_input.BACKSPACE, kt_input.LAYER):
                    return None
                if code in (kt_input.UP, "k"):
                    index[0] = (index[0] - 1) % len(cats)
                    paint()
                elif code in (kt_input.DOWN, "j"):
                    index[0] = (index[0] + 1) % len(cats)
                    paint()
                elif code in (kt_input.ENTER, kt_input.SPACE, kt_input.RIGHT):
                    return cats[index[0]]
            time.sleep(0.02)
    finally:
        ctx.display.root_group = previous


def _category(ctx, stats, cat):
    """The group grid for one category, with an accuracy bar under each kana."""
    f = ui.font("jp")
    ids = kana.groups(cat)
    group = displayio.Group()
    canvas = _Canvas(group)
    group.append(label.Label(f, text=NAMES[cat], color=WHITE, x=2,
                             y=layout.STATS_TITLE_Y))
    detail = label.Label(f, text="", color=WHITE, x=0, y=layout.STATS_TITLE_Y)
    group.append(detail)
    for i, row_id in enumerate(ids):
        cx, cy = layout.stats_cell(i)
        gx = cx + (layout.GROUP_CELL_W - layout.JP_KANA_W) // 2
        group.append(label.Label(f, text=kana.group_label(cat, row_id)[0],
                                 color=WHITE, x=gx,
                                 y=cy + layout.GROUP_GLYPH_DY))

    index = [0]

    def paint():
        with ui.frame():
            canvas.clear()
            for i, row_id in enumerate(ids):
                cx, cy = layout.stats_cell(i)
                c, a = stats.get((cat, row_id), (0, 0))
                canvas.bar(cx, cy + layout.STATS_CELL_BAR_DY,
                           layout.GROUP_CELL_W, layout.STATS_CELL_BAR_H,
                           (float(c) / a) if a else 0.0)
                canvas.line(cx, cy + layout.STATS_CURSOR_DY,
                            layout.GROUP_CELL_W, i == index[0])
            c, a = stats.get((cat, ids[index[0]]), (0, 0))
            text = "%s %d/%d" % (kana.group_romaji(ids[index[0]]), c, a)
            detail.text = text
            detail.x = (layout.GROUP_ROMAJI_RIGHT
                        - len(text) * layout.JP_CHAR_W)

    paint()
    previous = ctx.display.root_group
    ctx.display.root_group = group
    try:
        while True:
            for ev in ctx.input.poll():
                code = ev.code
                # BACKSPACE goes back, not LEFT: LEFT has to move the cursor
                # or the left half of each row is unreachable.
                if code in (kt_input.EXIT, kt_input.BACKSPACE, kt_input.LAYER):
                    return
                if code in (kt_input.LEFT, "h"):
                    index[0] = (index[0] - 1) % len(ids)
                    paint()
                elif code in (kt_input.RIGHT, "l"):
                    index[0] = (index[0] + 1) % len(ids)
                    paint()
                elif code in (kt_input.UP, "k"):
                    index[0] = max(0, index[0] - layout.GROUP_COLS)
                    paint()
                elif code in (kt_input.DOWN, "j"):
                    index[0] = min(len(ids) - 1,
                                   index[0] + layout.GROUP_COLS)
                    paint()
            time.sleep(0.02)
    finally:
        ctx.display.root_group = previous


def run(ctx, stats, cats):
    """Overview, with Enter to drill into a category. Returns when left."""
    while True:
        cat = _overview(ctx, stats, cats)
        if cat is None:
            return
        _category(ctx, stats, cat)
