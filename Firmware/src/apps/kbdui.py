"""Keyboard-app screens: the base readout and the setup overlay.

All four screens live here so every position comes from layout.KBD_* and
tools/render.py can mirror them (CLAUDE.md: geometry only in layout.py).

The overlay runs INSIDE the KMK loop rather than reloading into a separate
app: a KMK module whose process_key returns None breaks the chain before the
key reaches HID (verified in kmk_keyboard.pre_process_key), so while setup is
open every key is ours and the USB connection is never dropped.

Keys are read as APP codes (kanatype.input), translated from the matrix
coordinate by the caller, so this module never sees a scancode.
"""
import displayio
from adafruit_display_text import label

from kanatype import icons, keytable, layout, macros, ui

OFF, MENU, PICK, PROFILES, RENAME = range(5)

# Rows in the setup menu: one per M key, then the profile row.
_MENU_ROWS = macros.COUNT + 1
# Rows in the profile screen: one per profile, then rename.
_PROFILE_ROWS = macros.PROFILES + 1


def _txt(group, font, x, y, text):
    group.append(label.Label(font, text=text, color=0xFFFFFF, x=x, y=y))


def base_group(usb, keys, layer=0):
    """The screen shown while typing: number-row legend + M assignments.

    On layer 2 the number row sends F1..F10, so the legend switches to match:
    showing shifted symbols there would be a lie."""
    group = displayio.Group()
    mf = ui.font("menu")
    jp = ui.font("jp")
    _txt(group, mf, layout.MENU_TITLE_X, layout.KBD_TITLE_Y, "KEYBOARD")
    group.append(ui.status_icon(icons.BOLT if usb else icons.BATTERY))
    group.append(ui.filled_box(*layout.KBD_DIVIDER))
    if layer:
        _txt(group, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[0],
             layout.KBD_NUM_DIGITS)
        _txt(group, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[1],
             layout.KBD_FN_ROW)
    else:
        _txt(group, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[0],
             layout.KBD_NUM_DIGITS)
        _txt(group, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[1],
             layout.KBD_NUM_SYMBOLS)
    _txt(group, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[2],
         layout.KBD_HINT_TAP)
    _txt(group, jp, layout.KBD_COL_L_X, layout.KBD_ROW_Y[3],
         layout.KBD_HINT_HOLD)
    # right column: how wide a label may be before it runs off the panel
    limit = (layout.WIDTH - layout.KBD_COL_R_X) // layout.JP_CHAR_W - 3
    for i in range(macros.COUNT):
        s = macros.slot(layer, i)
        mods, idx = keys[s]
        _txt(group, jp, layout.KBD_COL_R_X, layout.KBD_ROW_Y[i],
             "%s %s" % (macros.slot_name(s), macros.label(mods, idx, limit)))
    return group


class Setup:
    """The overlay state machine. handle() consumes app codes and returns
    False once it has closed, so the caller knows to stop swallowing keys."""

    def __init__(self, display, state, on_change, on_save):
        self.display = display
        self.state = state            # {"active": int, "profiles": [...]}
        self.on_change = on_change    # re-apply assignments to the KMK keymap
        self.on_save = on_save        # persist to nvm
        self.mode = OFF
        self.sel = 0
        self.pick_for = 0
        self.filter = ""
        self.hits = []
        self.pick_sel = 0
        self.name_buf = ""
        self.mods = 0

    # ---------------------------------------------------------------- state

    @property
    def active(self):
        return self.state["profiles"][self.state["active"]]

    @property
    def keys(self):
        return self.active["keys"]

    @property
    def layer(self):
        """Which macro set is live AND being edited -- one concept, so the
        toggle key means the same thing whether or not setup is open."""
        return self.state.get("layer", 0)

    def slot(self, i):
        return macros.slot(self.layer, i)

    def profile_name(self, i):
        name = self.state["profiles"][i]["name"]
        return name if name else "Profile %d" % (i + 1)

    def open(self):
        self.mode = MENU
        self.sel = 0
        self.render()

    def close(self):
        self.mode = OFF
        self.on_change()          # caller repaints the base screen

    def set_mods(self, bits):
        """Live modifier state, so the picker can show what would be baked in."""
        if bits != self.mods:
            self.mods = bits
            if self.mode == PICK:
                self.render()

    # ---------------------------------------------------------------- input

    def handle(self, code):
        if self.mode == MENU:
            self._menu(code)
        elif self.mode == PICK:
            self._pick(code)
        elif self.mode == PROFILES:
            self._profiles(code)
        elif self.mode == RENAME:
            self._rename(code)
        return self.mode != OFF

    def _menu(self, code):
        if code == "exit":
            self.close()
            return
        if code == "up":
            self.sel = (self.sel - 1) % _MENU_ROWS
        elif code == "down":
            self.sel = (self.sel + 1) % _MENU_ROWS
        elif code == "layer":
            self.state["layer"] = 1 - self.layer
            self.on_change()          # the live keymap follows the toggle
        elif code == "backspace" and self.sel < macros.COUNT:
            self.keys[self.slot(self.sel)] = [0, macros.UNSET]
            self.on_save()
            self.on_change()
        elif code == "enter":
            if self.sel < macros.COUNT:
                self.pick_for = self.sel
                self.filter = ""
                self.hits = keytable.find("")
                self.pick_sel = 0
                self.mode = PICK
            else:
                self.sel = self.state["active"]
                self.mode = PROFILES
        else:
            return
        self.render()

    def _pick(self, code):
        if code == "exit":
            self.mode = MENU
            self.sel = self.pick_for
        elif code == "enter":
            if self.hits:
                self.keys[self.slot(self.pick_for)] = [self.mods,
                                                       self.hits[self.pick_sel]]
                self.on_save()
                self.on_change()
            self.mode = MENU
            self.sel = self.pick_for
        elif code == "up":
            self.pick_sel = (self.pick_sel - 1) % max(1, len(self.hits))
        elif code == "down":
            self.pick_sel = (self.pick_sel + 1) % max(1, len(self.hits))
        elif code == "backspace":
            self.filter = self.filter[:-1]
            self.hits = keytable.find(self.filter)
            self.pick_sel = 0
        elif len(code) == 1 and (code.isalpha() or code.isdigit()):
            self.filter += code
            self.hits = keytable.find(self.filter)
            self.pick_sel = 0
        else:
            return
        self.render()

    def _profiles(self, code):
        if code == "exit":
            self.mode = MENU
            self.sel = macros.COUNT
        elif code == "up":
            self.sel = (self.sel - 1) % _PROFILE_ROWS
        elif code == "down":
            self.sel = (self.sel + 1) % _PROFILE_ROWS
        elif code == "enter":
            if self.sel < macros.PROFILES:
                self.state["active"] = self.sel
                self.on_save()
                self.on_change()
                self.mode = MENU
                self.sel = macros.COUNT
            else:
                self.name_buf = self.active["name"]
                self.mode = RENAME
        else:
            return
        self.render()

    def _rename(self, code):
        if code == "exit":
            self.mode = PROFILES
        elif code == "enter":
            self.active["name"] = self.name_buf.strip()
            self.on_save()
            self.mode = PROFILES
        elif code == "backspace":
            self.name_buf = self.name_buf[:-1]
        elif code == "space" and len(self.name_buf) < macros.NAME_LEN:
            self.name_buf += " "
        elif (len(code) == 1 and (code.isalpha() or code.isdigit())
              and len(self.name_buf) < macros.NAME_LEN):
            self.name_buf += code
        else:
            return
        self.render()

    # -------------------------------------------------------------- drawing

    def render(self):
        builder = {MENU: self._draw_menu, PICK: self._draw_pick,
                   PROFILES: self._draw_profiles, RENAME: self._draw_rename}
        build = builder.get(self.mode)
        if build is None:
            return
        with ui.frame():
            self.display.root_group = build()

    def _list(self, title, rows, sel, y0, pitch):
        """Title plus a cursor list of (left, right) pairs."""
        group = displayio.Group()
        _txt(group, ui.font("menu"), layout.KBD_MENU_X,
             layout.KBD_MENU_TITLE_Y, title)
        jp = ui.font("jp")
        for i, (left, right) in enumerate(rows):
            y = y0 + i * pitch
            if i == sel:
                _txt(group, jp, layout.KBD_MENU_X, y, layout.MENU_CURSOR)
            _txt(group, jp, layout.KBD_MENU_X + layout.KBD_MENU_TEXT_DX, y, left)
            if right:
                _txt(group, jp, layout.KBD_MENU_VALUE_X, y, right)
        return group

    def _draw_menu(self):
        limit = (layout.WIDTH - layout.KBD_MENU_VALUE_X) // layout.JP_CHAR_W
        rows = []
        for i in range(macros.COUNT):
            s = self.slot(i)
            rows.append((macros.slot_name(s),
                         macros.label(self.keys[s][0], self.keys[s][1], limit)))
        rows.append(("Profile", self.profile_name(self.state["active"])[:limit]))
        title = "SETUP %s-%s" % (macros.slot_name(self.slot(0)),
                                 macros.slot_name(self.slot(macros.COUNT - 1)))
        return self._list(title, rows, self.sel,
                          layout.KBD_MENU_Y0, layout.KBD_MENU_PITCH)

    def _draw_profiles(self):
        rows = []
        for i in range(macros.PROFILES):
            mark = "*" if i == self.state["active"] else " "
            rows.append((mark + self.profile_name(i), ""))
        rows.append((" Rename", ""))   # align with the marked names
        return self._list("PROFILES", rows, self.sel,
                          layout.KBD_MENU_Y0, layout.KBD_MENU_PITCH)

    def _draw_pick(self):
        group = displayio.Group()
        _txt(group, ui.font("menu"), layout.KBD_MENU_X,
             layout.KBD_PICK_TITLE_Y,
             "SET " + macros.slot_name(self.slot(self.pick_for)))
        jp = ui.font("jp")
        # the modifiers currently HELD are what gets baked in on Enter
        held = "+".join(t for b, _n, t in macros.MOD_BITS if self.mods & b)
        caption = "find: %s_" % self.filter
        if held:
            caption += "  +" + held
        else:
            caption += "  %d hit%s" % (len(self.hits),
                                       "" if len(self.hits) == 1 else "s")
        _txt(group, jp, layout.KBD_PICK_FILTER_X, layout.KBD_PICK_FILTER_Y,
             caption)
        top = max(0, min(self.pick_sel - layout.KBD_PICK_MAX_VISIBLE + 1,
                         len(self.hits) - layout.KBD_PICK_MAX_VISIBLE))
        for row in range(min(len(self.hits), layout.KBD_PICK_MAX_VISIBLE)):
            i = top + row
            y = layout.KBD_PICK_Y0 + row * layout.KBD_PICK_PITCH
            if i == self.pick_sel:
                _txt(group, jp, layout.KBD_PICK_X, y, layout.MENU_CURSOR)
            _txt(group, jp, layout.KBD_PICK_X + layout.KBD_PICK_TEXT_DX, y,
                 keytable.SHORT[self.hits[i]])
        if not self.hits:
            _txt(group, jp, layout.KBD_PICK_X, layout.KBD_PICK_Y0, "no match")
        return group

    def _draw_rename(self):
        group = displayio.Group()
        _txt(group, ui.font("menu"), layout.KBD_MENU_X,
             layout.KBD_PICK_TITLE_Y, "NAME")
        jp = ui.font("jp")
        _txt(group, jp, layout.KBD_PICK_FILTER_X, layout.KBD_PICK_FILTER_Y,
             self.name_buf + "_")
        _txt(group, jp, layout.KBD_PICK_X, layout.KBD_PICK_Y0,
             "%d/%d chars" % (len(self.name_buf), macros.NAME_LEN))
        _txt(group, jp, layout.KBD_PICK_X,
             layout.KBD_PICK_Y0 + layout.KBD_PICK_PITCH, "Enter: save")
        return group
