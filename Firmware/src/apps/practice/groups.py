"""Per-group toggle grid for one practice category.

Reached with RIGHT on a category row in the config screen; Enter on that row
still toggles the whole category, which keeps the common case one keypress.

RIGHT rather than the hold-Enter the mockup imagined: `MatrixInput.poll()`
emits presses only -- releases are consumed and dropped -- so an app driven by
`ctx.input` cannot time a hold at all. (The keyboard app can, because it hooks
KMK's own scanner rather than this driver.) RIGHT is the "descend into"
idiom anyway, and LEFT comes back.

Drawing: enabled cells are INVERTED rather than marked with brackets, which
were unreadable at 16 cells to a screen, so the cursor is an UNDERLINE -- a box
outline is invisible against a filled cell. The fills and the underline live in
ONE displayio.Bitmap behind the labels rather than in per-label
`background_color`, because the background box is only as wide as the glyph
advance and the cell wants to be wider than that.

Combos show their BASE kana (き for ky-): a whole combo is 16px of ink in a
13px cell and spills into its neighbour. All 12 bases are distinct inside a
category, and the highlighted row's romaji prints in the title.
"""
import time

import displayio
from adafruit_display_text import label

from kanatype import input as kt_input
from kanatype import kana, layout, ui

WHITE = 0xFFFFFF
BLACK = 0x000000


class Grid:
    def __init__(self, category, mask):
        self.category = category
        self.ids = kana.groups(category)
        self.mask = mask
        self.cursor = 0
        self.group = displayio.Group()

        # One bitmap for every fill and the cursor underline. Toggling repaints
        # a single cell rather than rebuilding display objects.
        self.bmp = displayio.Bitmap(layout.WIDTH, layout.HEIGHT, 2)
        pal = displayio.Palette(2)
        pal[0] = BLACK
        pal[1] = WHITE
        self.group.append(displayio.TileGrid(self.bmp, pixel_shader=pal))

        f = ui.font("jp")
        self._title = label.Label(f, text="", color=WHITE, x=2,
                                  y=layout.GROUP_TITLE_Y)
        self._romaji = label.Label(f, text="", color=WHITE, x=0,
                                   y=layout.GROUP_TITLE_Y)
        self.group.append(self._title)
        self.group.append(self._romaji)

        self._cells = []
        for i, row_id in enumerate(self.ids):
            cx, cy = layout.group_cell(i)
            text = kana.group_label(category, row_id)[0]
            gx = cx + (layout.GROUP_CELL_W - layout.JP_KANA_W) // 2
            lbl = label.Label(f, text=text, color=WHITE, x=gx,
                              y=cy + layout.GROUP_GLYPH_DY)
            self._cells.append(lbl)
            self.group.append(lbl)

        for j, name in enumerate(layout.GROUP_ACTIONS):
            x, _w = layout.group_action_x(j)
            self.group.append(label.Label(f, text=name, color=WHITE, x=x,
                                          y=layout.GROUP_ACTION_Y))

        with ui.frame():
            self._paint_all()

    # ---- painting ---------------------------------------------------------
    def _fill(self, x, y, w, h, on):
        value = 1 if on else 0
        for yy in range(y, min(y + h, layout.HEIGHT)):
            for xx in range(x, min(x + w, layout.WIDTH)):
                self.bmp[xx, yy] = value

    def _paint_cell(self, i):
        """One cell: its fill, its glyph colour, and its slice of the cursor."""
        cx, cy = layout.group_cell(i)
        on = bool(self.mask & (1 << i))
        self._fill(cx, cy, layout.GROUP_CELL_W, layout.GROUP_CELL_H, on)
        # knocked out of the fill when enabled, drawn normally when not
        self._cells[i].color = BLACK if on else WHITE
        self._fill(cx, cy + layout.GROUP_CELL_H, layout.GROUP_CELL_W, 1,
                   self.cursor == i)

    def _paint_action(self, j):
        x, w = layout.group_action_x(j)
        self._fill(x, layout.GROUP_ACTION_UNDERLINE_Y, w, 1,
                   self.cursor == len(self.ids) + j)

    def _paint_title(self):
        on, total = kana.mask_count(self.category, self.mask)
        name = {"H": "Hiragana", "K": "Katakana",
                "HC": "Hira combos", "KC": "Kata combos"}[self.category]
        self._title.text = "%s %d/%d" % (name, on, total)
        # A kana alone does not say which row it stands for, and for a combo
        # the base kana is genuinely ambiguous -- so name the highlighted row.
        if self.cursor < len(self.ids):
            text = kana.group_romaji(self.ids[self.cursor])
            self._romaji.text = text
            self._romaji.x = (layout.GROUP_ROMAJI_RIGHT
                              - len(text) * layout.JP_CHAR_W)
        else:
            self._romaji.text = ""

    def _paint_all(self):
        self._paint_title()
        for i in range(len(self.ids)):
            self._paint_cell(i)
        for j in range(len(layout.GROUP_ACTIONS)):
            self._paint_action(j)

    # ---- interaction ------------------------------------------------------
    def _paint_focus(self, old):
        """Repaint only what the cursor left and what it landed on."""
        with ui.frame():
            for idx in (old, self.cursor):
                if idx < len(self.ids):
                    self._paint_cell(idx)
                else:
                    self._paint_action(idx - len(self.ids))
            self._paint_title()

    def move(self, delta):
        total = len(self.ids) + len(layout.GROUP_ACTIONS)
        old = self.cursor
        self.cursor = (self.cursor + delta) % total
        self._paint_focus(old)

    def move_row(self, delta):
        """UP/DOWN by a grid row, with the action strip as the row past the
        end. Clamped rather than wrapped: wrapping vertically through a
        two-row grid lands somewhere unpredictable."""
        total = len(self.ids) + len(layout.GROUP_ACTIONS)
        old = self.cursor
        if self.cursor >= len(self.ids):        # on the action strip
            target = self.cursor if delta > 0 else self.cursor - len(self.ids)
            if delta < 0:                       # back into the last grid row
                last_row = (len(self.ids) - 1) // layout.GROUP_COLS
                col = min(target, layout.GROUP_COLS - 1)
                target = min(last_row * layout.GROUP_COLS + col,
                             len(self.ids) - 1)
            self.cursor = target
        else:
            target = self.cursor + delta * layout.GROUP_COLS
            if target < 0:
                target = self.cursor
            elif target >= len(self.ids):
                # past the bottom row -> the action whose column it sits over
                col = self.cursor % layout.GROUP_COLS
                target = len(self.ids) + min(col, len(layout.GROUP_ACTIONS) - 1)
            self.cursor = min(target, total - 1)
        self._paint_focus(old)

    def activate(self):
        """Enter/Space. Returns 'back' when the Back action was chosen."""
        if self.cursor < len(self.ids):
            self.mask ^= 1 << self.cursor
            with ui.frame():
                self._paint_cell(self.cursor)
                self._paint_title()
            return None
        action = layout.GROUP_ACTIONS[self.cursor - len(self.ids)]
        if action == "Back":
            return "back"
        self.mask = kana.full_mask(self.category) if action == "All on" else 0
        with ui.frame():
            self._paint_all()
        return None


def run(ctx, category, mask):
    """Returns the mask the user left the grid with.

    An all-off mask is allowed here and handled at Start: forcing at least one
    group on would fight someone who is clearing a category to rebuild it.
    """
    grid = Grid(category, mask)
    previous = ctx.display.root_group
    ctx.display.root_group = grid.group
    try:
        while True:
            for ev in ctx.input.poll():
                code = ev.code
                # BACKSPACE, not LEFT, is "go back": LEFT has to stay free to
                # move the cursor, or half the grid is unreachable.
                if code in (kt_input.EXIT, kt_input.BACKSPACE):
                    return grid.mask
                if code in (kt_input.UP, "k"):
                    grid.move_row(-1)
                elif code in (kt_input.DOWN, "j"):
                    grid.move_row(1)
                elif code in (kt_input.LEFT, "h"):
                    grid.move(-1)
                elif code in (kt_input.RIGHT, "l"):
                    grid.move(1)
                elif code in (kt_input.ENTER, kt_input.SPACE):
                    if grid.activate() == "back":
                        return grid.mask
            time.sleep(0.02)
    finally:
        ctx.display.root_group = previous
