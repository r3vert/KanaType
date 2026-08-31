#!/usr/bin/env python3
"""Firmware-faithful screen renderer (desktop Python, stdlib only).

Renders screens EXACTLY as the firmware draws them:
  - geometry from src/kanatype/layout.py (the same file ui.py uses)
  - glyphs from the same BDF files the device loads (src/fonts/)
  - vertical/horizontal placement replicating adafruit_display_text.Label:
        baseline = label.y + ascent // 2
        glyph top = baseline - glyph_height - glyph_dy
        glyph left = label.x + cursor + glyph_dx;  cursor += shift_x
        missing glyphs are skipped with no advance
    (verified against adafruit_display_text label.py source)

Usage:
  python render.py menu [index] [status]      # launcher menu, e.g.: menu 0 USB
  python render.py screen "line 1" "line 2" ...
Options (append anywhere):
  --out PATH   output file (.png/.txt/.pbm), default ../mockups/render.png
  --scale N    png scale, default 4

mockup.py = free-form sketching; render.py = what the panel will actually show.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
sys.path.insert(0, SRC)
sys.path.insert(0, HERE)

import mockup  # grid + txt/pbm/png writers
from kanatype import icons, layout  # the firmware's own geometry + icon art


# ------------------------------------------------------------- BDF parsing --


class Glyph:
    __slots__ = ("shift_x", "w", "h", "dx", "dy", "rows")


class BDFFont:
    def __init__(self, path):
        self.glyphs = {}
        self.ascent = None
        self.descent = None
        fbb = None
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            glyph = None
            code = None
            in_bitmap = False
            for line in f:
                parts = line.split()
                if not parts:
                    continue
                key = parts[0]
                if key == "FONTBOUNDINGBOX":
                    fbb = [int(v) for v in parts[1:5]]
                elif key == "FONT_ASCENT":
                    self.ascent = int(parts[1])
                elif key == "FONT_DESCENT":
                    self.descent = int(parts[1])
                elif key == "STARTCHAR":
                    glyph = Glyph()
                    glyph.rows = []
                    code = None
                    in_bitmap = False
                elif key == "ENCODING" and glyph is not None:
                    code = int(parts[1])
                elif key == "DWIDTH" and glyph is not None:
                    glyph.shift_x = int(parts[1])
                elif key == "BBX" and glyph is not None:
                    glyph.w, glyph.h, glyph.dx, glyph.dy = (int(v) for v in parts[1:5])
                elif key == "BITMAP":
                    in_bitmap = True
                elif key == "ENDCHAR":
                    if code is not None and code >= 0:
                        self.glyphs[code] = glyph
                    glyph = None
                    in_bitmap = False
                elif in_bitmap and glyph is not None:
                    glyph.rows.append(int(parts[0], 16))
        if self.ascent is None:
            self.ascent = (fbb[1] + fbb[3]) if fbb else 0
        if self.descent is None:
            self.descent = (-fbb[3]) if fbb else 0


def draw_label(grid, font, x, y, text, scale=1, ink=True):
    """Replicates adafruit_display_text.Label placement (defaults).
    scale mirrors Label(scale=N): origin stays in parent pixels, content
    geometry (offsets, advances, glyph pixels) multiplies by N."""
    y_offset = font.ascent // 2
    cursor = 0
    for ch in text:
        g = font.glyphs.get(ord(ch))
        if g is None:
            continue  # exactly what the firmware does: skip, no advance
        top = y + (y_offset - g.h - g.dy) * scale
        left = x + (cursor + g.dx) * scale
        pad_bits = ((g.w + 7) // 8) * 8
        for r, rowbits in enumerate(g.rows):
            for c in range(g.w):
                if rowbits & (1 << (pad_bits - 1 - c)):
                    for sy in range(scale):
                        for sx in range(scale):
                            mockup.set_px(grid, left + c * scale + sx,
                                          top + r * scale + sy, ink)
        cursor += g.shift_x


# ------------------------------------------------------- firmware screens --


def font_path(role):
    """Resolve a font ROLE ('menu'/'jp'/'noto'/...) via layout.FONT_PATHS —
    the same table the firmware uses.

    FONT_PATHS names the .pcf the DEVICE loads; this returns the .bdf beside
    it, which is the source both this renderer and tools/bdf2pcf.py read. One
    table still decides which font a role means, so a role change follows into
    the previews automatically."""
    name = os.path.basename(layout.FONT_PATHS[role])
    if name.endswith(".pcf"):
        name = name[:-4] + ".bdf"
    p = os.path.join(SRC, "fonts", name)
    if not os.path.exists(p):
        raise SystemExit(
            "%s not found - drop the BDFs into src/fonts/ (see fonts/README.md)" % p
        )
    return p


def menu_font():
    return BDFFont(font_path("menu"))


def draw_icon(grid, art, x, y):
    """Blit kanatype.icons art — mirrors ui.icon()."""
    for row_i, row in enumerate(art):
        for col_i, ch in enumerate(row):
            if ch == "#":
                mockup.set_px(grid, x + col_i, y + row_i, True)


def draw_status_icon(grid, art):
    w, h = icons.size(art)
    draw_icon(grid, art, layout.STATUS_ICON_RIGHT - w,
              layout.STATUS_ICON_CY - h // 2)


def render_menu(items, index=0, status="", title="Practice"):
    """Mirrors ui.Menu: the practice config and font picker, jp font."""
    f = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    draw_label(g, f, layout.MENU_TITLE_X, layout.MENU_TITLE_Y, title)
    top = max(0, min(index - layout.MENU_MAX_VISIBLE + 1, len(items) - layout.MENU_MAX_VISIBLE))
    if index < top:
        top = index
    for i in range(min(len(items), layout.MENU_MAX_VISIBLE)):
        item = top + i
        y = layout.MENU_ITEM_Y0 + i * layout.MENU_PITCH
        if item == index:
            draw_label(g, f, layout.MENU_ITEM_X, y, layout.MENU_CURSOR)
        draw_label(g, f, layout.MENU_ITEM_X + layout.MENU_TEXT_DX, y, items[item])
    if status:
        draw_label(g, f, layout.STATUS_X, layout.STATUS_Y, status)
    return g


def render_screen(lines):
    f = menu_font()
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    y = layout.SCREEN_Y0
    for line in lines:
        if line:
            draw_label(g, f, layout.SCREEN_X, y, line)
        y += layout.SCREEN_PITCH
    return g


def draw_label_bg(grid, font, x, y, text):
    """label.Label with background_color=black: clear the glyph box, then draw.
    Box approximates adafruit's tight bounding box (ascent+descent tall,
    width from the actual glyph advances)."""
    width = sum(font.glyphs[ord(c)].shift_x for c in text if ord(c) in font.glyphs)
    top = y + font.ascent // 2 - font.ascent - 1
    bottom = y + font.ascent // 2 + font.descent
    for yy in range(max(0, top), min(layout.HEIGHT, bottom + 1)):
        for xx in range(max(0, x - 1), min(layout.WIDTH, x + width)):
            mockup.set_px(grid, xx, yy, False)
    draw_label(grid, font, x, y, text)


def render_loading(text=None):
    """The splash exactly as the device shows it: the bitmap and nothing else.
    Text is baked in by tools/make_splash.py, so nothing is drawn on top."""
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    splash_txt = os.path.join(HERE, "..", "mockups", "loading_splash.txt")
    if not os.path.exists(splash_txt):
        raise SystemExit("run tools/make_splash.py first (%s missing)" % splash_txt)
    for y, row in enumerate(mockup.read_txt(splash_txt)):
        for x, c in enumerate(row):
            if c == "#":
                mockup.set_px(g, x, y)
    return g


def _font_installed(role):
    name = os.path.basename(layout.FONT_PATHS[role])
    return os.path.exists(os.path.join(SRC, "fonts", name))


def render_drill(kana="きゃ", typed="ky", cats="H,HC", correct="12",
                 answered="34", role=None, miss=""):
    """Practice drill screen preview (geometry from layout.DRILL_*).
    Mirrors the firmware's font fallback chain."""
    if role is None:
        role = layout.PROMPT_FONTS[0]
        if not _font_installed(role):
            role = "prompt" if _font_installed("prompt") else "jp"
    adv, scale, kana_y = layout.DRILL_PROMPT_STYLES[role]
    uif = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)

    # left: enabled types, one per line
    for i, cat in enumerate([c for c in cats.split(",") if c]):
        draw_label(g, uif, layout.DRILL_TYPES_X,
                   layout.DRILL_TYPES_Y0 + i * layout.DRILL_TYPES_PITCH, cat)

    # right: score as a fraction (right-aligned in a 3-digit column)
    draw_label(g, uif,
               layout.DRILL_SCORE_RIGHT - len(correct) * layout.JP_CHAR_W,
               layout.DRILL_SCORE_Y, correct)
    draw_label(g, uif,
               layout.DRILL_SCORE_RIGHT - len(answered) * layout.JP_CHAR_W,
               layout.DRILL_TOTAL_Y, answered)
    rx, ry, rw, rh = layout.DRILL_SCORE_RULE
    mockup.fill_rect(g, rx, ry, rw, rh, True)

    # right: typed-answer box (hollow) + slots
    bx, by, bw, bh = layout.DRILL_ANSWER_BOX
    mockup.fill_rect(g, bx, by, bw, 1, True)
    mockup.fill_rect(g, bx, by + bh - 1, bw, 1, True)
    mockup.fill_rect(g, bx, by, 1, bh, True)
    mockup.fill_rect(g, bx + bw - 1, by, 1, bh, True)
    slots = layout.DRILL_ANSWER_SLOTS
    shown = typed[:slots]
    draw_label(g, uif, layout.DRILL_ANSWER_X, layout.DRILL_ANSWER_Y,
               shown + layout.DRILL_ANSWER_BLANK * (slots - len(shown)))

    # centre: the prompt glyph
    pf = BDFFont(font_path(role))
    kx = layout.DRILL_PROMPT_CENTER_X - (adv * scale * len(kana)) // 2
    draw_label(g, pf, kx, kana_y, kana, scale=scale)

    # under it: the correct reading, shown only after a miss
    if miss:
        draw_label(g, uif,
                   layout.DRILL_PROMPT_CENTER_X
                   - len(miss) * layout.JP_CHAR_W // 2,
                   layout.DRILL_MISS_Y, miss)
    return g


def render_groups(cat="H", mask=None, cursor=0, combos_full=False):
    """Per-group toggle grid (geometry from layout.GROUP_*).

    mask: bitmask over kana.groups(cat); None = every group on.
    cursor: index into the cells, or len(cells)+n for the action row.
    combos_full: REJECTED, kept only to reproduce the evidence in
    mockups/practice_groups.png. A whole combo is 16 px of ink in a 13 px
    cell, so it centres to x-2 and spills into the neighbour. Combos show
    their BASE kana instead -- all 12 bases are distinct within a category,
    and the romaji in the title row says which row you are on.
    """
    from kanatype import kana

    jp = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    ids = kana.groups(cat)
    if mask is None:
        mask = kana.full_mask(cat)

    name = {"H": "Hiragana", "K": "Katakana",
            "HC": "Hira combos", "KC": "Kata combos"}[cat]
    on, total = kana.mask_count(cat, mask)
    draw_label(g, jp, 2, layout.GROUP_TITLE_Y, "%s %d/%d" % (name, on, total))

    # the highlighted group's romaji: a kana alone does not tell you which row
    # you are on, and for combos the base kana is genuinely ambiguous
    if cursor < len(ids):
        romaji = kana.group_romaji(ids[cursor])
        draw_label(g, jp, layout.GROUP_ROMAJI_RIGHT
                   - len(romaji) * layout.JP_CHAR_W, layout.GROUP_TITLE_Y,
                   romaji)

    for i, row_id in enumerate(ids):
        cx, cy = layout.group_cell(i)
        label_text = kana.group_label(cat, row_id)
        if not combos_full:
            label_text = label_text[0]
        enabled = bool(mask & (1 << i))
        if enabled:
            mockup.fill_rect(g, cx, cy, layout.GROUP_CELL_W,
                             layout.GROUP_CELL_H, True)
        gw = len(label_text) * layout.JP_KANA_W
        gx = cx + (layout.GROUP_CELL_W - gw) // 2
        # on an enabled (filled) cell the glyph is knocked OUT of the fill
        draw_label(g, jp, gx, cy + layout.GROUP_GLYPH_DY, label_text,
                   ink=not enabled)
        if i == cursor:
            mockup.fill_rect(g, cx, cy + layout.GROUP_CELL_H,
                             layout.GROUP_CELL_W, 1, True)

    for j, text in enumerate(layout.GROUP_ACTIONS):
        x, w = layout.group_action_x(j)
        draw_label(g, jp, x, layout.GROUP_ACTION_Y, text)
        if cursor == len(ids) + j:
            mockup.fill_rect(g, x, layout.GROUP_ACTION_UNDERLINE_Y, w, 1, True)
    return g


def draw_bar(g, x, y, w, h, frac):
    """1-bit progress bar: solid for the achieved part, 50% checkerboard for
    the rest. The dither reads as grey beside solid white, which is the only
    way to show two levels on this panel -- and it keeps the FULL scale
    visible, so a short bar is obviously 'a small share of something' rather
    than just a small mark."""
    filled = int(round(w * max(0.0, min(1.0, frac))))
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            on = (xx - x) < filled or ((xx + yy) % 2 == 0)
            mockup.set_px(g, xx, yy, on)


def _totals(stats, category=None, row_id=None):
    """Mirrors apps.practice.stats.totals: symbol counts summed upward, so a
    preview can never disagree with the device about a group's accuracy."""
    from kanatype import kana

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


def render_stats_group(stats, cat="H", row_id="k", cursor=0):
    """Per-SYMBOL view: which individual kana in a group you are missing."""
    from kanatype import kana

    jp = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    entries = kana.group_entries(cat, row_id)
    draw_label(g, jp, 2, layout.STATS_TITLE_Y, kana.group_romaji(row_id))
    text, romaji = entries[cursor]
    c, a = stats.get(text, (0, 0))
    detail = "%s %d/%d" % (romaji, c, a)
    draw_label(g, jp, layout.STATS_PCT_RIGHT - len(detail) * layout.JP_CHAR_W,
               layout.STATS_TITLE_Y, detail)
    for i, (text, _r) in enumerate(entries):
        cx, cy = layout.symbol_cell(i)
        gw = len(text) * layout.JP_KANA_W
        draw_label(g, jp, cx + (layout.SYMBOL_CELL_W - gw) // 2,
                   cy + layout.GROUP_GLYPH_DY, text)
        c, a = stats.get(text, (0, 0))
        draw_bar(g, cx, cy + layout.STATS_CELL_BAR_DY, layout.SYMBOL_CELL_W,
                 layout.STATS_CELL_BAR_H, (float(c) / a) if a else 0.0)
        if i == cursor:
            mockup.fill_rect(g, cx, cy + layout.STATS_CURSOR_DY,
                             layout.SYMBOL_CELL_W, 1, True)
    return g


def render_stats(stats, cats=("H", "K", "HC", "KC"), cursor=0):
    """Overview: accuracy per category, one bar each.

    stats maps (category, row_id) -> [correct, answered]; a category with no
    answers yet shows a dash rather than 0%, because 0% and 'not attempted'
    mean very different things to someone deciding what to drill.
    """
    jp = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    draw_label(g, jp, 2, layout.STATS_TITLE_Y, "Stats")

    total_c, total_a = _totals(stats)
    summary = "%d/%d" % (total_c, total_a)
    draw_label(g, jp, layout.STATS_PCT_RIGHT - len(summary) * layout.JP_CHAR_W,
               layout.STATS_TITLE_Y, summary)

    names = {"H": "Hiragana", "K": "Katakana",
             "HC": "Hira combos", "KC": "Kata combos"}
    for i, cat in enumerate(cats):
        y = layout.stats_row_y(i)
        draw_label(g, jp, layout.STATS_NAME_X, y, names[cat])
        c, a = _totals(stats, cat)
        top = y - layout.STATS_BAR_H // 2
        if a:
            draw_bar(g, layout.STATS_BAR_X, top, layout.STATS_BAR_W,
                     layout.STATS_BAR_H, float(c) / a)
            pct = "%d%%" % int(round(100.0 * c / a))
        else:
            draw_bar(g, layout.STATS_BAR_X, top, layout.STATS_BAR_W,
                     layout.STATS_BAR_H, 0.0)
            pct = "-"
        draw_label(g, jp, layout.STATS_PCT_RIGHT - len(pct) * layout.JP_CHAR_W,
                   y, pct)
        if i == cursor:
            draw_label(g, jp, layout.STATS_NAME_X - 2, y, ">")
    return g


def render_stats_category(stats, cat="H", cursor=0):
    """Per-category: the group grid with an accuracy bar under each kana."""
    from kanatype import kana

    jp = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    ids = kana.groups(cat)
    name = {"H": "Hiragana", "K": "Katakana",
            "HC": "Hira combos", "KC": "Kata combos"}[cat]
    draw_label(g, jp, 2, layout.STATS_TITLE_Y, name)
    if cursor < len(ids):
        c, a = _totals(stats, cat, ids[cursor])
        detail = "%s %d/%d" % (kana.group_romaji(ids[cursor]), c, a)
        draw_label(g, jp,
                   layout.GROUP_ROMAJI_RIGHT - len(detail) * layout.JP_CHAR_W,
                   layout.STATS_TITLE_Y, detail)

    for i, row_id in enumerate(ids):
        cx, cy = layout.stats_cell(i)
        text = kana.group_label(cat, row_id)[0]
        gx = cx + (layout.GROUP_CELL_W - layout.JP_KANA_W) // 2
        draw_label(g, jp, gx, cy + layout.GROUP_GLYPH_DY, text)
        c, a = _totals(stats, cat, row_id)
        draw_bar(g, cx, cy + layout.STATS_CELL_BAR_DY, layout.GROUP_CELL_W,
                 layout.STATS_CELL_BAR_H, (float(c) / a) if a else 0.0)
        if i == cursor:
            mockup.fill_rect(g, cx, cy + layout.STATS_CURSOR_DY,
                             layout.GROUP_CELL_W, 1, True)
    return g


def render_kbd_base(macros=("Ctrl+C", "Ctrl+V", "Ctrl+Shift+V", "Enter"),
                    usb=True, layer=0):
    """Keyboard app base screen: number-row legend + live M assignments.
    layer=1 shows the F-key legend and the M5..M8 set."""
    mf = menu_font()
    jp = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    draw_label(g, mf, layout.MENU_TITLE_X, layout.KBD_TITLE_Y, "KEYBOARD")
    draw_status_icon(g, icons.BOLT if usb else icons.BATTERY)
    mockup.fill_rect(g, *(layout.KBD_DIVIDER + (True,)))
    draw_label(g, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[0], layout.KBD_NUM_DIGITS)
    draw_label(g, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[1],
               layout.KBD_FN_ROW if layer else layout.KBD_NUM_SYMBOLS)
    draw_label(g, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[2],
               layout.KBD_HINT_TAP)
    draw_label(g, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[3],
               layout.KBD_HINT_HOLD)
    for i, name in enumerate(macros):
        draw_label(g, jp, layout.KBD_COL_R_X, layout.KBD_ROW_Y[i],
                   "M%d %s" % (i + 1 + layer * len(macros), name))
    return g


def render_kbd_menu(items, values, index=0, title="KEYBOARD SETUP"):
    """Setup menu: name on the left, current assignment on the right."""
    mf = menu_font()
    jp = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    draw_label(g, mf, layout.KBD_MENU_X, layout.KBD_MENU_TITLE_Y, title)
    top = max(0, min(index - layout.KBD_MENU_MAX_VISIBLE + 1,
                     len(items) - layout.KBD_MENU_MAX_VISIBLE))
    for i in range(min(len(items), layout.KBD_MENU_MAX_VISIBLE)):
        item = top + i
        y = layout.KBD_MENU_Y0 + i * layout.KBD_MENU_PITCH
        if item == index:
            draw_label(g, jp, layout.KBD_MENU_X, y, layout.MENU_CURSOR)
        draw_label(g, jp, layout.KBD_MENU_X + layout.KBD_MENU_TEXT_DX, y, items[item])
        if values[item]:
            draw_label(g, jp, layout.KBD_MENU_VALUE_X, y, values[item])
    return g


def render_key_picker(target="M1", typed="ent", matches=("ENTER", "KP_ENTER"),
                      index=0, total=None):
    """Type-to-filter key picker."""
    mf = menu_font()
    jp = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)
    draw_label(g, mf, layout.KBD_MENU_X, layout.KBD_PICK_TITLE_Y, "SET " + target)
    caption = "find: %s_" % typed
    if total is not None:
        caption += "   %d hit%s" % (total, "" if total == 1 else "s")
    draw_label(g, jp, layout.KBD_PICK_FILTER_X, layout.KBD_PICK_FILTER_Y, caption)
    for i in range(min(len(matches), layout.KBD_PICK_MAX_VISIBLE)):
        y = layout.KBD_PICK_Y0 + i * layout.KBD_PICK_PITCH
        if i == index:
            draw_label(g, jp, layout.KBD_PICK_X, y, layout.MENU_CURSOR)
        draw_label(g, jp, layout.KBD_PICK_X + layout.KBD_PICK_TEXT_DX, y, matches[i])
    return g


def render_kbd_profiles(names=("Default", "coding99", "", ""), active=1, index=1):
    """Profile list: * marks the active one, Rename is the last row."""
    rows = []
    for i, name in enumerate(names):
        mark = "*" if i == active else " "
        rows.append(mark + (name or "Profile %d" % (i + 1)))
    rows.append(" Rename")
    return render_kbd_menu(rows, [""] * len(rows), index, title="PROFILES")


# The launcher's app entries — keep in sync with code.py APPS. Clock is
# absent on purpose: the home screen shows the time and Enter on the clock
# panel opens it.
APPS = ["Keyboard", "Practice", "Quick note", "Vault", "Sleep"]


def render_home(index=0, usb=True, tm="23:41", date="2026-08-28",
                approx=False):
    """Launcher home screen — mirrors ui.Home.
    index == len(APPS) focuses the clock panel."""
    mf = menu_font()
    jp = BDFFont(font_path("jp"))
    g = mockup.new_grid(layout.WIDTH, layout.HEIGHT)

    for i, name in enumerate(APPS):
        draw_label(g, jp, layout.HOME_ITEM_X + layout.HOME_TEXT_DX,
                   layout.HOME_ITEM_Y0 + i * layout.HOME_PITCH, name)
    if index == len(APPS):
        draw_label(g, jp, layout.HOME_DIVIDER[0] + layout.HOME_CURSOR_DX,
                   layout.HOME_TIME_Y, layout.MENU_CURSOR)
    else:
        draw_label(g, jp, layout.HOME_ITEM_X,
                   layout.HOME_ITEM_Y0 + index * layout.HOME_PITCH,
                   layout.MENU_CURSOR)
    mockup.fill_rect(g, *(layout.HOME_DIVIDER + (True,)))

    def centre(text, cw):
        return layout.HOME_RIGHT_X + (layout.HOME_RIGHT_W - len(text) * cw) // 2

    draw_label(g, jp, centre(layout.TITLE, layout.JP_CHAR_W),
               layout.HOME_TITLE_Y, layout.TITLE)
    tx = centre(tm, layout.CHAR_W)
    draw_label(g, mf, tx, layout.HOME_TIME_Y, tm)
    if approx:
        draw_label(g, mf, tx + layout.HOME_APPROX_DX,
                   layout.HOME_TIME_Y + layout.HOME_APPROX_DY, "~")
    draw_label(g, jp, centre(date, layout.JP_CHAR_W), layout.HOME_DATE_Y, date)

    bx, by, bw, bh = layout.HOME_BATT
    nw, nh = layout.HOME_BATT_NUB
    mockup.fill_rect(g, bx, by, bw, 1, True)
    mockup.fill_rect(g, bx, by + bh - 1, bw, 1, True)
    mockup.fill_rect(g, bx, by, 1, bh, True)
    mockup.fill_rect(g, bx + bw - 1, by, 1, bh, True)
    mockup.fill_rect(g, bx + bw, by + bh // 2 - nh // 2, nw, nh, True)
    if usb:
        draw_icon(g, icons.BOLT, bx + bw // 2 - 3, by + 1)
    draw_label(g, jp, bx + bw + nw + layout.HOME_BATT_LABEL_DX, by + bh // 2,
               "USB" if usb else "BATT")
    return g


# --------------------------------------------------------------------- cli --


def main(argv):
    out = os.path.join(HERE, "..", "mockups", "render.png")
    scale = 4
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == "--out":
            out = argv[i + 1]
            i += 2
        elif argv[i] == "--scale":
            scale = int(argv[i + 1])
            i += 2
        else:
            args.append(argv[i])
            i += 1
    if not args:
        print(__doc__)
        return 1
    if args[0] == "config":
        names = dict(zip(layout.PROMPT_FONTS, layout.PROMPT_FONT_NAMES))
        grid = render_menu(
            ["[x] Hiragana", "[ ] Katakana", "[x] Hira combos",
             "[ ] Kata combos", "Mode: Instant",
             "Correction Type: Correct",
             "Font: %s" % names[layout.PROMPT_FONTS[0]],
             "Start", "Reset to defaults"],
            int(args[1]) if len(args) > 1 else 0,
            args[2] if len(args) > 2 else "", "Practice")
    elif args[0] == "home":
        grid = render_home(int(args[1]) if len(args) > 1 else 0,
                           usb=(len(args) < 3 or args[2] != "batt"),
                           approx=(len(args) > 3 and args[3] == "approx"))
    elif args[0] == "menu":
        index = int(args[1]) if len(args) > 1 else 0
        status = args[2] if len(args) > 2 else "USB"
        grid = render_menu(APPS, index, status)
    elif args[0] == "screen":
        grid = render_screen(args[1:])
    elif args[0] == "loading":
        grid = render_loading(args[1] if len(args) > 1 else "Loading...")
    elif args[0] == "drill":
        grid = render_drill(*args[1:8]) if len(args) > 1 else render_drill()
    elif args[0] == "kbd":
        grid = render_kbd_base(
            args[2:6] or ("Ctrl+C", "Ctrl+V", "Ctrl+Shift+V", "Enter"),
            layer=int(args[1]) if len(args) > 1 else 0)
    elif args[0] == "kbd2":
        grid = render_kbd_base(("F13", "Home", "-", "-"), layer=1)
    elif args[0] == "kbdmenu":
        grid = render_kbd_menu(["M1", "M2", "M3", "M4", "Profile"],
                               ["Ctrl+C", "Ctrl+V", "Ctrl+Shift+V", "Enter",
                                "Coding"],
                               int(args[1]) if len(args) > 1 else 0)
    elif args[0] == "kbdprofiles":
        grid = render_kbd_profiles(index=int(args[1]) if len(args) > 1 else 1)
    elif args[0] == "kbdpick":
        grid = render_key_picker(args[1] if len(args) > 1 else "M1",
                                 args[2] if len(args) > 2 else "ent",
                                 args[3:] or ("ENTER", "KP_ENTER", "ENTER_PAD"),
                                 0, len(args[3:]) or 3)
    else:
        print(__doc__)
        return 1
    mockup._save(grid, out, scale)
    print("rendered ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
