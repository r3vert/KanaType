"""Shared UI: font loading (with graceful ASCII fallback), screens, menu widget.

All geometry comes from kanatype/layout.py — shared with tools/render.py so
desktop renders match the panel pixel-for-pixel. Never hardcode positions here.
"""
import displayio
import terminalio

from adafruit_display_text import label

from kanatype import layout

# Font roles live in layout.py (shared with the desktop renderer).
FONT_PATHS = layout.FONT_PATHS
_fonts = {}


def font(name="menu"):
    """Load a font once; fall back to terminalio.FONT (ASCII-only) if the
    BDF isn't installed yet — see fonts/README.md."""
    if name not in _fonts:
        f = terminalio.FONT
        path = FONT_PATHS.get(name)
        if path:
            try:
                from adafruit_bitmap_font import bitmap_font

                f = bitmap_font.load_font(path)
            except (OSError, ImportError):
                pass
        _fonts[name] = f
    return _fonts[name]


def try_font(name):
    """Like font(), but returns None instead of the ASCII fallback — lets
    callers detect a missing JP font and pick their own fallback."""
    f = font(name)
    return None if f is terminalio.FONT else f


def preload(chars, name="menu"):
    """Load a font's glyphs for `chars` in one batch, before any Label exists.

    WHY IT WAS URGENT: adafruit_bitmap_font's BDF loader keeps no glyph index,
    so every load_glyphs() call hitting an uncached code point re-scanned the
    whole .bdf from byte 0. Both the Label constructor and every `.text =`
    assignment call it, so building a 6-item menu cost ~6 full scans — the
    4.6 s black screen. This collapsed that to one pass.

    WHY IT IS STILL HERE: the fonts are PCF now (2026-08-30) and nothing
    scans, so this is no longer load-bearing for speed. It still batches —
    one gc.collect for the whole set, sequential seeks, and no allocation on
    the interactive path — which is worth keeping for a FIXED, small set of
    glyphs the screen is certain to show. Do NOT use it for a large or
    open-ended set: it makes every one of those glyphs resident, and the
    library's glyph cache never evicts. That is exactly why the practice
    drill stopped preloading its prompt font.
    """
    f = font(name)
    loader = getattr(f, "load_glyphs", None)
    if loader is not None:          # terminalio.FONT fallback has none
        loader(set(ord(c) for c in chars))
    return f


def screen(lines, font_name="menu"):
    """Simple stack of text lines -> displayio Group (assign to root_group)."""
    group = displayio.Group()
    f = font(font_name)
    y = layout.SCREEN_Y0
    for line in lines:
        if line:
            group.append(label.Label(f, text=line, color=0xFFFFFF, x=layout.SCREEN_X, y=y))
        y += layout.SCREEN_PITCH
    return group


class Frame:
    """Suspend the display's auto-refresh while a screen is updated, then push
    exactly one frame.

    displayio refreshes on a timer, so it can catch a label mid-layout and show
    a partially built line — a 2-kana prompt appearing one glyph at a time.
    That window is widest the first time a glyph is used, because the font
    loader has to seek it out of the BDF (a 40px glyph is ~9x the bytes of a
    16px one).

    Reentrant: only the outermost block refreshes, so composite updates
    (score + prompt + answer box) still land as a single frame.
    """

    def __init__(self, display):
        self._display = display
        self._depth = 0

    def __enter__(self):
        if self._depth == 0:
            try:
                self._display.auto_refresh = False
            except Exception:
                pass
        self._depth += 1
        return self

    def __exit__(self, *args):
        self._depth -= 1
        if self._depth == 0:
            try:
                self._display.refresh()
            except Exception:
                pass
            try:
                self._display.auto_refresh = True
            except Exception:
                pass
        return False


class _NoFrame:
    """Fallback when no display exists (headless tests): does nothing."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


_shared_frame = None


def frame():
    """The shared atomic-frame context manager for the active display.

    One instance per display so nesting collapses across widgets: a Menu
    update inside an app's own frame still pushes a single refresh.
    """
    global _shared_frame
    if _shared_frame is None:
        try:
            from kanatype import hw

            _shared_frame = Frame(hw.display())
        except Exception:
            _shared_frame = _NoFrame()
    return _shared_frame


def icon(art, x, y):
    """1-bit icon (kanatype.icons art) as a TileGrid, background transparent."""
    from kanatype import icons

    w, h = icons.size(art)
    bmp = displayio.Bitmap(w, h, 2)
    pal = displayio.Palette(2)
    pal[0] = 0x000000
    pal[1] = 0xFFFFFF
    pal.make_transparent(0)
    for row_i, row in enumerate(art):
        for col_i, ch in enumerate(row):
            if ch == "#":
                bmp[col_i, row_i] = 1
    return displayio.TileGrid(bmp, pixel_shader=pal, x=x, y=y)


def status_icon(art):
    """Icon placed in the title row's status corner, right-aligned."""
    from kanatype import icons

    w, h = icons.size(art)
    return icon(art, layout.STATUS_ICON_RIGHT - w,
                layout.STATUS_ICON_CY - h // 2)


def outline_box(x, y, w, h):
    """Hollow 1px rectangle as a TileGrid. Drawn from a Bitmap rather than
    adafruit_display_shapes so the device needs no extra library."""
    bmp = displayio.Bitmap(w, h, 2)
    pal = displayio.Palette(2)
    pal[0] = 0x000000
    pal[1] = 0xFFFFFF
    pal.make_transparent(0)
    for i in range(w):
        bmp[i, 0] = 1
        bmp[i, h - 1] = 1
    for j in range(h):
        bmp[0, j] = 1
        bmp[w - 1, j] = 1
    return displayio.TileGrid(bmp, pixel_shader=pal, x=x, y=y)


def filled_box(x, y, w, h):
    """Solid rectangle (used for the score's fraction bar)."""
    bmp = displayio.Bitmap(w, h, 2)
    pal = displayio.Palette(2)
    pal[0] = 0x000000
    pal[1] = 0xFFFFFF
    pal.make_transparent(0)
    for j in range(h):
        for i in range(w):
            bmp[i, j] = 1
    return displayio.TileGrid(bmp, pixel_shader=pal, x=x, y=y)


def splash_art():
    """The boot splash: one bitmap, no labels, so it needs NO font.

    Title and "Loading..." are baked into /assets/loading.bmp by
    tools/make_splash.py. OnDiskBitmap streams from flash without parsing,
    so this is the cheapest thing we can put on screen — which is why the
    text has to be part of the image: drawing it with labels would mean
    waiting for the very font parse this splash exists to cover.
    """
    group = displayio.Group()
    try:
        bmp = displayio.OnDiskBitmap("/assets/loading.bmp")
        group.append(displayio.TileGrid(bmp, pixel_shader=bmp.pixel_shader, x=0, y=0))
    except (OSError, ValueError):
        pass
    return group


def centre_x(text, char_w):
    """x that centres `text` in the home screen's right panel."""
    return layout.HOME_RIGHT_X + (layout.HOME_RIGHT_W - len(text) * char_w) // 2


class Home:
    """Launcher home screen: app list, clock, power state.

    The clock is selectable — index == len(items) focuses it, and the caller
    opens the Clock app on Enter. Labels are built once and only their text or
    position changes, the same reason ui.Menu keeps its cursor separate: a full
    re-layout every second was what made the old menu feel slow.
    """

    def __init__(self, items, usb=False):
        self.items = items
        self.index = 0
        self.group = displayio.Group()
        jp = font("jp")
        mf = font("menu")

        for i, name in enumerate(items):
            self.group.append(label.Label(
                jp, text=name, color=0xFFFFFF,
                x=layout.HOME_ITEM_X + layout.HOME_TEXT_DX,
                y=layout.HOME_ITEM_Y0 + i * layout.HOME_PITCH))
        self._cursor = label.Label(jp, text=layout.MENU_CURSOR, color=0xFFFFFF,
                                   x=layout.HOME_ITEM_X, y=layout.HOME_ITEM_Y0)
        self.group.append(self._cursor)
        self.group.append(filled_box(*layout.HOME_DIVIDER))

        self.group.append(label.Label(
            jp, text=layout.TITLE, color=0xFFFFFF,
            x=centre_x(layout.TITLE, layout.JP_CHAR_W), y=layout.HOME_TITLE_Y))
        self._time = label.Label(mf, text="", color=0xFFFFFF, x=0,
                                 y=layout.HOME_TIME_Y)
        self._date = label.Label(jp, text="", color=0xFFFFFF, x=0,
                                 y=layout.HOME_DATE_Y)
        self._approx = label.Label(mf, text="~", color=0xFFFFFF, x=0,
                                   y=layout.HOME_TIME_Y + layout.HOME_APPROX_DY)
        self._approx.hidden = True
        for lbl in (self._time, self._date, self._approx):
            self.group.append(lbl)

        x, y, w, h = layout.HOME_BATT
        nw, nh = layout.HOME_BATT_NUB
        self.group.append(outline_box(x, y, w, h))
        self.group.append(filled_box(x + w, y + h // 2 - nh // 2, nw, nh))
        from kanatype import icons

        self._bolt = icon(icons.BOLT, x + w // 2 - 3, y + 1)
        self.group.append(self._bolt)
        self._power = label.Label(jp, text="", color=0xFFFFFF,
                                  x=x + w + nw + layout.HOME_BATT_LABEL_DX,
                                  y=y + h // 2)
        self.group.append(self._power)

        self.set_power(usb)
        self.move(0)

    # ------------------------------------------------------------- updates

    def move(self, delta):
        with frame():
            self.index = (self.index + delta) % (len(self.items) + 1)
            if self.clock_selected:
                self._cursor.x = layout.HOME_DIVIDER[0] + layout.HOME_CURSOR_DX
                self._cursor.y = layout.HOME_TIME_Y
            else:
                self._cursor.x = layout.HOME_ITEM_X
                self._cursor.y = (layout.HOME_ITEM_Y0
                                  + self.index * layout.HOME_PITCH)

    @property
    def clock_selected(self):
        return self.index == len(self.items)

    def set_power(self, usb):
        with frame():
            self._bolt.hidden = not usb
            self._power.text = "USB" if usb else "BATT"

    def set_clock(self, now, approximate=False):
        """now is a struct_time, or None when there is no RTC at all."""
        with frame():
            if now is None:
                self._time.text = "--:--"
                self._date.text = ""
            else:
                self._time.text = "%02d:%02d" % (now.tm_hour, now.tm_min)
                self._date.text = "%04d-%02d-%02d" % (now.tm_year, now.tm_mon,
                                                      now.tm_mday)
            self._time.x = centre_x(self._time.text, layout.CHAR_W)
            self._date.x = centre_x(self._date.text, layout.JP_CHAR_W)
            self._approx.x = self._time.x + layout.HOME_APPROX_DX
            self._approx.hidden = not approximate


class Menu:
    """Vertical menu. The cursor is its own tiny label — moving the selection
    updates one y coordinate instead of re-laying-out every visible line,
    which is what made scrolling feel slow."""

    def __init__(self, title, items, status=""):
        self.items = items
        self.index = 0
        self.group = displayio.Group()
        f = font("jp")          # same small font as the launcher and keyboard
        self.group.append(
            label.Label(f, text=title, color=0xFFFFFF, x=layout.MENU_TITLE_X, y=layout.MENU_TITLE_Y)
        )
        self._labels = []
        for i in range(layout.MENU_MAX_VISIBLE):
            lbl = label.Label(
                f, text="", color=0xFFFFFF,
                x=layout.MENU_ITEM_X + layout.MENU_TEXT_DX,
                y=layout.MENU_ITEM_Y0 + i * layout.MENU_PITCH,
            )
            self._labels.append(lbl)
            self.group.append(lbl)
        self._cursor = label.Label(
            f, text=layout.MENU_CURSOR, color=0xFFFFFF,
            x=layout.MENU_ITEM_X, y=layout.MENU_ITEM_Y0,
        )
        self.group.append(self._cursor)
        self._status = label.Label(
            f, text=status, color=0xFFFFFF, x=layout.STATUS_X, y=layout.STATUS_Y
        )
        self.group.append(self._status)
        self._top = 0  # first visible item
        self._rewrite()

    def _rewrite(self):
        """Full re-render: only when the scroll window or the items change.
        Wrapped in a frame so a scrolled window never shows half-updated rows."""
        with frame():
            for i, lbl in enumerate(self._labels):
                item = self._top + i
                lbl.text = self.items[item] if item < len(self.items) else ""
            self._place_cursor()

    def _place_cursor(self):
        with frame():
            self._cursor.y = (layout.MENU_ITEM_Y0
                              + (self.index - self._top) * layout.MENU_PITCH)

    def move(self, delta):
        with frame():
            self._move(delta)

    def _move(self, delta):
        self.index = (self.index + delta) % len(self.items)
        top = self._top
        if self.index < top:
            top = self.index
        elif self.index >= top + layout.MENU_MAX_VISIBLE:
            top = self.index - layout.MENU_MAX_VISIBLE + 1
        if top != self._top:
            self._top = top
            self._rewrite()   # window scrolled: lines must change
        else:
            self._place_cursor()  # cheap path: one y update

    def set_items(self, items):
        with frame():
            self.items = items
            self._rewrite()

    def set_status(self, text):
        with frame():
            self._status.text = text
