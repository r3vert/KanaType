"""Practice stats: accuracy per category, per group, and per symbol.

Opened from the drill with the LAYER key (right of the spacebar). NOT the MENU
key the mockup imagined: MENU already maps to app code "exit", which is how the
drill returns to config, and that is confirmed on hardware. LAYER is the only
app code the practice app does not already use.

Three levels, Enter to descend and BACKSPACE to come back:
    overview  -> category (group grid) -> group (symbol grid)
The last one is the point of the feature: a group bar tells you k- is weak, but
only the symbol grid tells you it is か you keep missing.

Counting is per SYMBOL, correct-first-try over answered, matching the fraction
on the drill screen so the two can never disagree. Group and category figures
are summed from the symbols rather than counted separately -- one source of
truth, and no way for the levels to drift apart.

Drawing on a 1-bit panel: a bar is a SOLID fill for the achieved part plus a
50% checkerboard for the rest. The dither reads as grey beside solid white, and
keeping the full-width scale visible is what makes a short bar read as "a small
share" rather than just a small mark. Nothing answered shows "-", not "0%" --
untried and failed are very different when you are picking what to drill.

The three screens do NOT restore the display themselves. Each swaps its own
group in and run() puts the drill back once at the end: restoring in every
`finally` repainted the drill for a frame between screens, which is exactly the
flash this had on first hardware test.
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
    """Fold one answer in, keyed by the SYMBOL itself."""
    entry = stats.get(kana_text)
    if entry is None:
        entry = stats[kana_text] = [0, 0]
    entry[1] += 1
    if correct:
        entry[0] += 1


def totals(stats, category=None, row_id=None):
    """(correct, answered) over everything, one category, or one group."""
    c = a = 0
    for text, (ec, ea) in stats.items():
        if category is not None:
            group = kana.group_of(text)
            if group is None or group[0] != category:
                continue
            if row_id is not None and group[1] != row_id:
                continue
        c += ec
        a += ea
    return c, a


def _frac(correct, answered):
    return (float(correct) / answered) if answered else 0.0


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


def _right(lbl, text):
    lbl.text = text
    lbl.x = layout.STATS_PCT_RIGHT - len(text) * layout.JP_CHAR_W


def _overview(ctx, stats, cats):
    """Category list. Returns a category to descend into, or None to leave."""
    f = ui.font("jp")
    group = displayio.Group()
    canvas = _Canvas(group)
    group.append(label.Label(f, text="Stats", color=WHITE, x=2,
                             y=layout.STATS_TITLE_Y))
    summary = label.Label(f, text="", color=WHITE, x=0, y=layout.STATS_TITLE_Y)
    group.append(summary)
    _right(summary, "%d/%d" % totals(stats))

    cursors, pcts = [], []
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
                           _frac(cc, ca))
                _right(pcts[i],
                       ("%d%%" % int(round(100.0 * cc / ca))) if ca else "-")
                cursors[i].hidden = i != index[0]

    paint()
    ctx.display.root_group = group
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


def _category(ctx, stats, cat):
    """Group grid. Returns a row_id to descend into, or None to go back."""
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
                c, a = totals(stats, cat, row_id)
                canvas.bar(cx, cy + layout.STATS_CELL_BAR_DY,
                           layout.GROUP_CELL_W, layout.STATS_CELL_BAR_H,
                           _frac(c, a))
                canvas.line(cx, cy + layout.STATS_CURSOR_DY,
                            layout.GROUP_CELL_W, i == index[0])
            c, a = totals(stats, cat, ids[index[0]])
            _right(detail, "%s %d/%d"
                   % (kana.group_romaji(ids[index[0]]), c, a))

    paint()
    ctx.display.root_group = group
    while True:
        for ev in ctx.input.poll():
            code = ev.code
            # BACKSPACE goes back, not LEFT: LEFT has to move the cursor or
            # the left half of each row is unreachable.
            if code in (kt_input.EXIT, kt_input.BACKSPACE, kt_input.LAYER):
                return None
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
                index[0] = min(len(ids) - 1, index[0] + layout.GROUP_COLS)
                paint()
            elif code in (kt_input.ENTER, kt_input.SPACE):
                return ids[index[0]]
        time.sleep(0.02)


def _group(ctx, stats, cat, row_id):
    """Symbol grid for one group -- which individual kana you are missing."""
    f = ui.font("jp")
    entries = kana.group_entries(cat, row_id)
    group = displayio.Group()
    canvas = _Canvas(group)
    group.append(label.Label(f, text=kana.group_romaji(row_id), color=WHITE,
                             x=2, y=layout.STATS_TITLE_Y))
    detail = label.Label(f, text="", color=WHITE, x=0, y=layout.STATS_TITLE_Y)
    group.append(detail)
    for i, (text, _romaji) in enumerate(entries):
        cx, cy = layout.symbol_cell(i)
        gw = len(text) * layout.JP_KANA_W
        group.append(label.Label(f, text=text, color=WHITE,
                                 x=cx + (layout.SYMBOL_CELL_W - gw) // 2,
                                 y=cy + layout.GROUP_GLYPH_DY))

    index = [0]

    def paint():
        with ui.frame():
            canvas.clear()
            for i, (text, _romaji) in enumerate(entries):
                cx, cy = layout.symbol_cell(i)
                c, a = stats.get(text, (0, 0))
                canvas.bar(cx, cy + layout.STATS_CELL_BAR_DY,
                           layout.SYMBOL_CELL_W, layout.STATS_CELL_BAR_H,
                           _frac(c, a))
                canvas.line(cx, cy + layout.STATS_CURSOR_DY,
                            layout.SYMBOL_CELL_W, i == index[0])
            text, romaji = entries[index[0]]
            c, a = stats.get(text, (0, 0))
            _right(detail, "%s %d/%d" % (romaji, c, a))

    paint()
    ctx.display.root_group = group
    while True:
        for ev in ctx.input.poll():
            code = ev.code
            if code in (kt_input.EXIT, kt_input.BACKSPACE, kt_input.LAYER):
                return
            if code in (kt_input.LEFT, "h"):
                index[0] = (index[0] - 1) % len(entries)
                paint()
            elif code in (kt_input.RIGHT, "l"):
                index[0] = (index[0] + 1) % len(entries)
                paint()
        time.sleep(0.02)


def run(ctx, stats, cats):
    """Walk the three levels. Restores the caller's screen once, at the end."""
    previous = ctx.display.root_group
    try:
        while True:
            cat = _overview(ctx, stats, cats)
            if cat is None:
                return
            while True:
                row_id = _category(ctx, stats, cat)
                if row_id is None:
                    break
                _group(ctx, stats, cat, row_id)
    finally:
        ctx.display.root_group = previous
