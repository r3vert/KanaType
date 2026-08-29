#!/usr/bin/env python3
"""Pre-deploy checks for KanaType firmware (desktop Python, stdlib only).

Every check here corresponds to a mistake that actually bit this project once:
a font role with no file, a prompt font with no drill style, keymap gaps, a
stale nvm format, icons drawn off the panel edge, and device-side files that
the (deliberately non-destructive) deploy scripts will never clean up.

Usage:  python Firmware/tools/preflight.py
Exit 0 = safe to deploy.
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
FONTS = os.path.join(SRC, "fonts")
sys.path.insert(0, HERE)
sys.path.insert(0, SRC)

FAILS = []
WARNS = []


def ok(msg):
    print("  [ok]   %s" % msg)


def fail(msg):
    FAILS.append(msg)
    print("  [FAIL] %s" % msg)


def warn(msg):
    WARNS.append(msg)
    print("  [warn] %s" % msg)


# ---------------------------------------------------------------- compile --
print("compile")
import compileall  # noqa: E402

if compileall.compile_dir(SRC, quiet=2) and compileall.compile_dir(HERE, quiet=2):
    ok("all .py files compile")
else:
    fail("syntax error in src/ or tools/")

import mockup  # noqa: E402
import render  # noqa: E402

from kanatype import icons, kana, keymap, keytable, layout  # noqa: E402

# ------------------------------------------------------------------ fonts --
print("fonts")
for role, path in sorted(layout.FONT_PATHS.items()):
    f = os.path.join(FONTS, os.path.basename(path))
    if os.path.exists(f):
        ok("role %-12s -> %-26s %4d KB"
           % (role, os.path.basename(path), round(os.path.getsize(f) / 1024.0)))
    else:
        fail("role %s points at missing file %s" % (role, path))

if len(layout.PROMPT_FONT_NAMES) == len(layout.PROMPT_FONTS):
    ok("%d prompt fonts, each with a display name (%s)"
       % (len(layout.PROMPT_FONTS), ", ".join(layout.PROMPT_FONT_NAMES)))
else:
    fail("PROMPT_FONT_NAMES has %d entries, PROMPT_FONTS has %d - the picker "
         "would mislabel a font" % (len(layout.PROMPT_FONT_NAMES),
                                    len(layout.PROMPT_FONTS)))

missing_style = [r for r in layout.PROMPT_FONTS
                 if r not in layout.DRILL_PROMPT_STYLES]
missing_path = [r for r in layout.PROMPT_FONTS if r not in layout.FONT_PATHS]
if missing_style or missing_path:
    fail("prompt fonts missing style %r / path %r" % (missing_style, missing_path))
else:
    ok("%d prompt fonts, each with a path and a drill style"
       % len(layout.PROMPT_FONTS))

deck = kana.build_deck(["H", "K", "HC", "KC"])
chars = set(c for k, _r in deck for c in k)
for role in layout.PROMPT_FONTS:
    p = os.path.join(FONTS, os.path.basename(layout.FONT_PATHS.get(role, "")))
    if not os.path.exists(p):
        continue
    font = render.BDFFont(p)
    absent = sorted(c for c in chars if ord(c) not in font.glyphs)
    if absent:
        fail("font %s cannot render %d deck kana" % (role, len(absent)))
    else:
        ok("font %-12s renders all %d deck kana" % (role, len(chars)))

lit = ("abcdefghijklmnopqrstuvwxyz"
       "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -/:.!,[]")
for role in ("jp", "menu"):
    uif = os.path.join(FONTS, os.path.basename(layout.FONT_PATHS[role]))
    if not os.path.exists(uif):
        continue
    font = render.BDFFont(uif)
    absent = sorted(c for c in lit if ord(c) not in font.glyphs)
    if absent:
        fail("%s font missing UI characters: %s" % (role, "".join(absent)))
    else:
        ok("%-4s font covers the UI character set (%d glyphs)"
           % (role, len(font.glyphs)))

# ------------------------------------------------------- module constants --
# drill.py referenced layout.DRILL_SCORE_X long after the constant was renamed
# to DRILL_SCORE_RIGHT: it compiles fine and only raises AttributeError when
# that screen is actually built, which needs hardware to notice. This resolves
# every `module.NAME` reference in src/ against the real module.
print("constants")
import ast  # noqa: E402

# ast, NOT a text scan: docstrings and comments legitimately mention things
# like `layout.DRILL_*` in prose, and a regex reports every one of those as
# undefined. Only real attribute loads count.
WATCHED = {"layout": layout, "icons": icons, "keymap": keymap, "kana": kana}
_missing = []
_checked = 0
for _root, _dirs, _files in os.walk(SRC):
    _dirs[:] = [d for d in _dirs if d != "__pycache__"]
    for _name in sorted(_files):
        if not _name.endswith(".py"):
            continue
        _path = os.path.join(_root, _name)
        with open(_path, encoding="utf-8") as _fh:
            _tree = ast.parse(_fh.read(), _path)
        for _node in ast.walk(_tree):
            if not isinstance(_node, ast.Attribute):
                continue
            _owner = _node.value
            if not isinstance(_owner, ast.Name) or _owner.id not in WATCHED:
                continue
            _checked += 1
            if not hasattr(WATCHED[_owner.id], _node.attr):
                _missing.append("%s:%d  %s.%s" % (
                    os.path.relpath(_path, SRC).replace(os.sep, "/"),
                    _node.lineno, _owner.id, _node.attr))
if _missing:
    for _m in _missing:
        fail("undefined constant  %s" % _m)
else:
    ok("%d %s.* references all resolve" % (_checked, "/".join(sorted(WATCHED))))

# ----------------------------------------------------------------- keymap --
print("keymap")
names = keymap.kmk_matrix_names()
seen_rc = set((r, c) for row in keymap.LAYOUT for _s, r, c, _a, _k in row)
if len(names) == 56:
    ok("56 matrix positions")
else:
    fail("expected 56 matrix positions, got %d" % len(names))
# "NO" means "sends nothing over USB", which is a gap everywhere EXCEPT:
#   MENU  - the host repeats a held character, so a key meant to be held
#           cannot also type one;
#   M1-M4 - user-assignable, driven from the active profile at runtime;
#   LAYER - a toggle, and a key that also typed would fire on every press.
menu_i = keymap.menu_matrix_index()
layer_i = keymap.layer_matrix_index()
macro_i = keymap.macro_matrix_indices()
allowed_no = set([menu_i, layer_i] + macro_i)
unassigned = [i for i, n in enumerate(names) if n == "NO" and i not in allowed_no]
if unassigned:
    fail("%d matrix positions unassigned: index %s"
         % (len(unassigned), ", ".join(str(i) for i in unassigned)))
elif names[menu_i] != "NO":
    fail("MENU key (index %d) should send nothing, sends %s" % (menu_i, names[menu_i]))
else:
    ok("no unassigned matrix positions (MENU, LAYER + %d macro keys send nothing)"
       % len(macro_i))

# --- second layer ----------------------------------------------------------
if keymap.LAYER_KEY not in seen_rc:
    fail("LAYER_KEY %s is not a position in LAYOUT" % (keymap.LAYER_KEY,))
elif keymap.matrix_app_codes()[keymap.LAYER_KEY] != "layer":
    fail("LAYER key app code is %r, expected 'layer'"
         % keymap.matrix_app_codes()[keymap.LAYER_KEY])
else:
    ok("LAYER key %s, app code 'layer'" % (keymap.LAYER_KEY,))

over = keymap.layer2_overrides()
missing = [n for n in over.values() if n not in keytable.NAMES]
clash = sorted(set(over) & allowed_no)
if len(over) != len(keymap.LAYER2_KMK):
    fail("layer 2 maps %d keys, LAYER2_KMK names %d - a source name is not "
         "in LAYOUT" % (len(over), len(keymap.LAYER2_KMK)))
elif missing:
    fail("layer 2 targets not in the keycode table: %r" % missing)
elif clash:
    fail("layer 2 overrides a reserved key at index %r" % clash)
else:
    ok("layer 2 remaps %d keys (%s)"
       % (len(over), ", ".join(sorted(set(over.values()),
                                      key=lambda n: int(n[1:])))))

# The spacebar must survive the macro-key split: the drill uses Space to step
# past a miss, so at least one key has to still emit it.
spaces = [rc for rc, code in keymap.matrix_app_codes().items() if code == "space"]
if spaces:
    ok("%d key(s) still send space: %s"
       % (len(spaces), ", ".join("%d,%d" % rc for rc in sorted(spaces))))
else:
    fail("no key emits app code 'space' - the drill cannot advance past a miss")

seen = {}
dupes = 0
for row in keymap.LAYOUT:
    for sw, r, c, _app, _kmk in row:
        if (r, c) in seen:
            dupes += 1
            fail("ROW%d/COL%d claimed by both %s and %s" % (r, c, seen[(r, c)], sw))
        seen[(r, c)] = sw
if not dupes and len(seen) == 56:
    ok("every (row, col) pair used exactly once")

app_by_rc = keymap.matrix_app_codes()
if keymap.MENU_KEY not in seen:
    fail("MENU_KEY %s is not a position in LAYOUT" % (keymap.MENU_KEY,))
elif app_by_rc[keymap.MENU_KEY] != "exit":
    fail("MENU key app code is %r, expected 'exit'" % app_by_rc[keymap.MENU_KEY])
else:
    ok("MENU key %s = %s, app code 'exit'"
       % (keymap.MENU_KEY, seen[keymap.MENU_KEY]))

if len(keymap.MOD_PIN_NAMES) == len(keymap.MOD_KMK_NAMES) == 3:
    ok("3 hardware modifiers: %s -> %s"
       % ("/".join(keymap.MOD_PIN_NAMES), "/".join(keymap.MOD_KMK_NAMES)))
else:
    fail("modifier pin/keycode lists disagree")

# ---- romaji correctness ---------------------------------------------------
# kana.ROWS was typed by hand: row GRANULARITY follows DJT Kana, but the romaji
# strings have no external source. The drill now shows the reading after a
# miss, i.e. it TEACHES them, so a typo would teach the wrong thing. Derive
# Hepburn independently from the rules and compare.
print("romaji")
_VOWELS = "aiueo"
_CONS = {"a": "", "k": "k", "s": "s", "t": "t", "n": "n", "h": "h", "m": "m",
         "y": "y", "r": "r", "w": "w", "g": "g", "z": "z", "d": "d",
         "b": "b", "p": "p"}
_IRREGULAR = {"si": "shi", "ti": "chi", "tu": "tsu", "hu": "fu",
              "zi": "ji", "di": "ji", "du": "zu"}
_DIGRAPH = {"ky": "k", "sh": "sh", "ch": "ch", "ny": "n", "hy": "h",
            "my": "m", "ry": "r", "gy": "g", "j": "j", "dj": "j",
            "by": "b", "py": "p"}
_bad = []
_n = 0
for _cat, _row, _entries in kana.ROWS:
    for _i, (_glyph, _romaji) in enumerate(_entries):
        _n += 1
        if _cat in ("H", "K"):
            if _row == "nn":
                _want = "n"
            elif _row == "w":
                _want = ("wa", "wo")[_i]
            elif _row == "y":
                _want = ("ya", "yu", "yo")[_i]
            else:
                _plain = _CONS[_row] + _VOWELS[_i]
                _want = _IRREGULAR.get(_plain, _plain)
        else:
            _base = _DIGRAPH[_row]
            _want = _base + (("a", "u", "o")[_i] if _base in ("sh", "ch", "j")
                             else ("ya", "yu", "yo")[_i])
        if _want != _romaji:
            _bad.append("%s/%s %s: table=%s derived=%s"
                        % (_cat, _row, _glyph, _romaji, _want))
if _bad:
    for _m in _bad:
        fail("romaji mismatch  %s" % _m)
else:
    ok("%d readings match an independent Hepburn derivation" % _n)

# ------------------------------------------------------------------- deck --
print("deck")
counts = {}
for cat, _row, entries in kana.ROWS:
    counts[cat] = counts.get(cat, 0) + len(entries)
if counts == {"H": 71, "HC": 36, "K": 71, "KC": 36}:
    ok("DJT counts match: 71 + 36 per script, 214 total")
else:
    fail("deck counts %r, expected 71/36/71/36" % counts)

longest = max(len(a) for _k, r in deck for a in kana.answers(r))
if longest <= layout.DRILL_ANSWER_SLOTS:
    ok("longest romaji %d char(s) <= %d answer slots"
       % (longest, layout.DRILL_ANSWER_SLOTS))
else:
    fail("longest romaji %d exceeds %d answer slots"
         % (longest, layout.DRILL_ANSWER_SLOTS))

# ------------------------------------------------------------------ icons --
print("icons")
for name in ("BOLT", "BATTERY", "TILDE"):
    art = getattr(icons, name, None)
    if art is None:
        fail("icon %s is missing" % name)
        continue
    w, h = icons.size(art)
    if any(len(r) != w for r in art):
        fail("icon %s has ragged rows" % name)
        continue
    x = layout.STATUS_ICON_RIGHT - w
    y = layout.STATUS_ICON_CY - h // 2
    if 0 <= x and x + w <= layout.WIDTH and 0 <= y and y + h <= layout.HEIGHT:
        ok("icon %-8s %2dx%-2d at (%3d,%2d)" % (name, w, h, x, y))
    else:
        fail("icon %s draws off-panel at (%d,%d)" % (name, x, y))

# --------------------------------------------------------------- settings --
print("settings")
mc = types.ModuleType("microcontroller")
mc.nvm = bytearray(256)   # must exceed settings._BLOB_END or saves no-op
sys.modules["microcontroller"] = mc
from kanatype import clockstore, keytable, macros, settings  # noqa: E402

if settings._BLOB_END <= len(mc.nvm):
    ok("nvm blob is %d bytes" % settings._BLOB_END)
else:
    fail("nvm blob %d bytes exceeds the test buffer" % settings._BLOB_END)

if settings.FONT_ORDER == layout.PROMPT_FONTS:
    ok("settings.FONT_ORDER tracks layout.PROMPT_FONTS")
else:
    fail("settings.FONT_ORDER drifted from layout.PROMPT_FONTS")

bad = []
for role in layout.PROMPT_FONTS:
    for _correct in (False, True):
        o = {"H": True, "K": False, "HC": True, "KC": False, "instant": True,
             "correct": _correct, "font": role}
        settings.save_practice(o)
        if settings.load_practice() != o:
            bad.append((role, _correct))
if bad:
    fail("settings round-trip failed for %r" % bad)
else:
    ok("settings round-trip OK for all fonts (magic %s)"
       % settings.MAGIC.decode())

# ---- macro profiles -------------------------------------------------------
# Every name has to survive getattr(KC, name) on the device.
bad_names = [n for n in keytable.NAMES
             if not n or not n[0].isalpha()
             or not all(c.isalnum() or c == "_" for c in n)]
if bad_names:
    fail("keytable names unusable with getattr: %r" % bad_names[:5])
else:
    ok("%d keycodes, all valid identifiers (hash 0x%04X)"
       % (len(keytable.NAMES), keytable.HASH))

if len(keytable.NAMES) <= macros.UNSET:
    ok("key index fits one byte, UNSET=0x%02X unambiguous" % macros.UNSET)
else:
    fail("keytable has %d entries - index collides with UNSET"
         % len(keytable.NAMES))

profs = macros.blank_profiles()
profs[1]["name"] = "Coding"
profs[1]["keys"][0] = [0x03, macros.index_of("V")]
profs[1]["keys"][3] = [0x00, macros.UNSET]
profs[1]["keys"][macros.slot(1, 0)] = [0x00, macros.index_of("F13")]
profs[1]["keys"][macros.slot(1, 3)] = [0x04, macros.index_of("HOME")]
settings.save_macros(2, profs)
got = settings.load_macros()
if got is None:
    fail("macro round-trip returned nothing")
elif got[0] != 2:
    fail("active profile did not survive: %r" % (got[0],))
elif [p["name"] for p in got[1]] != [p["name"] for p in profs]:
    fail("profile names did not survive: %r" % [p["name"] for p in got[1]])
elif [p["keys"] for p in got[1]] != [p["keys"] for p in profs]:
    fail("assignments did not survive")
else:
    ok("macro round-trip OK (%d profiles x %d slots, both layers)"
       % (macros.PROFILES, macros.SLOTS))

# A regenerated keytable must invalidate saved macros rather than decode them
# to the wrong keys - that is what the stored hash is for.
mc.nvm[settings._OFF_HASH] ^= 0xFF
if settings.load_macros() is None:
    ok("stale keytable hash invalidates saved macros")
else:
    fail("saved macros survived a keytable hash change")
mc.nvm[settings._OFF_HASH] ^= 0xFF

# practice and macros share the blob; neither may clobber the other
saved = {"H": True, "K": True, "HC": False, "KC": False, "instant": False,
         "correct": True, "font": layout.PROMPT_FONTS[0]}
settings.save_practice(saved)
if settings.load_macros() and settings.load_practice() == saved:
    ok("practice and macro regions coexist")
else:
    fail("save_practice clobbered the macro region (or vice versa)")

# ------------------------------------------------------------------- apps --
print("apps")
code_src = open(os.path.join(SRC, "code.py"), encoding="utf-8").read()
entries = [ln for ln in code_src.splitlines()
           if ln.strip().startswith('("') and "apps." in ln]
menu_names = [ln.split('"')[1] for ln in entries]
for ln in entries:
    dotted = ln.split('"')[3]
    rel = dotted.replace(".", os.sep)
    if os.path.exists(os.path.join(SRC, rel + ".py")) or \
            os.path.exists(os.path.join(SRC, rel, "__init__.py")):
        ok("menu entry %-11s -> %s" % (ln.split('"')[1], dotted))
    else:
        fail("menu entry %s has no module" % dotted)

if menu_names == render.APPS:
    ok("render.py APPS matches code.py")
else:
    warn("render.py APPS %r != code.py %r - renders will mislead"
         % (render.APPS, menu_names))

splash = os.path.join(SRC, "assets", "loading.bmp")
if os.path.exists(splash):
    w, h = mockup.read_bmp_size(splash)
    if (w, h) == (layout.WIDTH, layout.HEIGHT):
        ok("splash asset is %dx%d" % (w, h))
    else:
        warn("splash asset is %dx%d, panel is %dx%d"
             % (w, h, layout.WIDTH, layout.HEIGHT))
else:
    warn("no assets/loading.bmp - loading screen falls back to text")

# ---- CircuitPython stubs --------------------------------------------------
# Installed HERE, before anything imports a firmware module, so the checks
# below can exercise real app code on the desktop. kanatype.input imports
# supervisor, ui imports displayio, and so on.
_sup = types.ModuleType("supervisor")


class _Runtime(object):
    usb_connected = True
    serial_connected = False
    serial_bytes_available = 0


_sup.runtime = _Runtime()
_sup.reload = lambda: None
sys.modules["supervisor"] = _sup

_disp = types.ModuleType("displayio")


class _Group(list):
    pass


class _Bitmap(object):
    def __init__(self, w, h, n):
        pass

    def __setitem__(self, key, value):
        pass


class _Palette(list):
    def __init__(self, n):
        list.__init__(self, [0] * n)

    def make_transparent(self, i):
        pass


class _TileGrid(object):
    def __init__(self, *a, **k):
        self.hidden = False


def _no_disk_bitmap(path):
    raise OSError(path)


_disp.Group = _Group
_disp.Bitmap = _Bitmap
_disp.Palette = _Palette
_disp.TileGrid = _TileGrid
_disp.OnDiskBitmap = _no_disk_bitmap
_disp.release_displays = lambda: None
sys.modules["displayio"] = _disp

_term = types.ModuleType("terminalio")
_term.FONT = object()
sys.modules["terminalio"] = _term


class _Label(object):
    def __init__(self, font, text="", color=0, x=0, y=0, scale=1, **kw):
        self.font, self.text, self.x, self.y = font, text, x, y
        self.hidden = False


_adt = types.ModuleType("adafruit_display_text")
_lbl = types.ModuleType("adafruit_display_text.label")
_lbl.Label = _Label
_adt.label = _lbl
sys.modules["adafruit_display_text"] = _adt
sys.modules["adafruit_display_text.label"] = _lbl



# ---- practice config rows -------------------------------------------------
# _labels() and ROW_KEYS are parallel: run_config dispatches by ROW_KEYS[index],
# so a row added to one and not the other silently toggles the wrong setting.
try:
    from apps.practice import config as _cfg  # noqa: E402

    _opts = dict(_cfg.DEFAULTS)
    _rows = _cfg._labels(_opts)
    if len(_rows) != len(_cfg.ROW_KEYS):
        fail("config has %d rows but %d dispatch keys"
             % (len(_rows), len(_cfg.ROW_KEYS)))
    else:
        _wide = [r for r in _rows
                 if layout.MENU_ITEM_X + layout.MENU_TEXT_DX
                 + len(r) * layout.JP_CHAR_W > layout.WIDTH]
        if _wide:
            fail("config rows run off the panel: %r" % _wide)
        else:
            ok("%d config rows, keys aligned, widest %d px"
               % (len(_rows), max(len(r) for r in _rows) * layout.JP_CHAR_W))
    _missing_opt = [k for k in _cfg.ROW_KEYS
                    if k not in ("font", "start", "reset")
                    and k not in _cfg.DEFAULTS]
    if _missing_opt:
        fail("config rows with no default: %r" % _missing_opt)
except ImportError as _exc:
    fail("could not import the practice config: %s" % _exc)

# ---- clock carry-over across deep sleep -----------------------------------
# The RTC does not survive deep sleep (hardware-confirmed 2026-08-28), so the
# time is stamped into nvm. That region sits AFTER the MAGIC-guarded blob and
# is guarded by its own marker, so it must not collide with the macros and a
# zeroed nvm must report nothing rather than a bogus date.
for _i in range(clockstore.OFFSET, clockstore.END):
    mc.nvm[_i] = 0
if clockstore.load() is None:
    ok("blank nvm reports no stored time")
else:
    fail("blank nvm decoded as a stored time: %r" % (clockstore.load(),))

_dt = types.SimpleNamespace(tm_year=2026, tm_mon=8, tm_mday=28, tm_hour=23,
                            tm_min=41, tm_sec=7)
clockstore.save(_dt, approximate=True)
_got = clockstore.load()
if _got is None:
    fail("clock round-trip returned nothing")
elif _got[0][:6] != (2026, 8, 28, 23, 41, 7):
    fail("clock round-trip gave %r" % (_got[0][:6],))
elif not _got[1]:
    fail("approximate flag did not survive")
else:
    ok("clock round-trip OK, flagged approximate")

clockstore.save(_dt, approximate=False)
if clockstore.load()[1]:
    fail("setting the time by hand left it flagged approximate")
else:
    ok("a hand-set time is stored exact")

# clockstore duplicates the offset rather than importing settings (that import
# is the boot cost it exists to avoid), so the two must be asserted equal here.
if clockstore.OFFSET == settings._BLOB_END:
    ok("clockstore.OFFSET %d == settings._BLOB_END" % clockstore.OFFSET)
else:
    fail("clockstore.OFFSET %d != settings._BLOB_END %d - the clock stamp "
         "overlaps the macro profiles" % (clockstore.OFFSET, settings._BLOB_END))

# the two regions must not overlap
if clockstore.OFFSET >= settings._BLOB_END:
    ok("clock region starts at %d, after the macro blob (%d)"
       % (clockstore.OFFSET, settings._BLOB_END))
else:
    fail("clock region overlaps the macro blob")
_before = clockstore.load()
settings.save_macros(1, macros.blank_profiles())
if clockstore.load() != _before:
    fail("save_macros clobbered the stored time")
else:
    ok("macro writes leave the stored time intact")

# ------------------------------------------------------- keyboard overlay --
# The setup overlay is the most intricate logic in the firmware and cannot be
# reached without hardware, so it is driven here against stub displayio /
# adafruit_display_text modules. This has already caught a real bug.
print("kbdui")
_PROFILE_ROWS_MAX = macros.PROFILES + 2
_MENU_ROWS_MAX = macros.COUNT + 3

class _Display(object):
    root_group = None


try:
    from apps import kbdui  # noqa: E402

    saves = [0]
    changes = [0]
    st = {"active": 0, "profiles": macros.blank_profiles(), "layer": 0}
    ui_setup = kbdui.Setup(_Display(), st,
                           lambda: changes.__setitem__(0, changes[0] + 1),
                           lambda: saves.__setitem__(0, saves[0] + 1))

    # base screen builds at all
    kbdui.base_group(True, st["profiles"][0]["keys"])

    ui_setup.open()
    assert ui_setup.mode == kbdui.MENU, "open() did not reach the menu"

    # assign Ctrl+ENTER to M4 by filtering, with a modifier held
    for _ in range(3):
        ui_setup.handle("down")
    assert ui_setup.sel == 3, "cursor did not reach M4"
    ui_setup.handle("enter")
    assert ui_setup.mode == kbdui.PICK, "enter did not open the picker"
    for ch in "ent":
        ui_setup.handle(ch)
    assert ui_setup.hits, "filter 'ent' matched nothing"
    ui_setup.set_mods(0x01)
    ui_setup.handle("enter")
    got = st["profiles"][0]["keys"][3]
    want = [0x01, keytable.find("ent")[0]]
    if got != want:
        fail("picker stored %r, expected %r" % (got, want))
    elif macros.label(got[0], got[1]) != "Ctrl+ENT":
        fail("assignment reads %r" % macros.label(got[0], got[1]))
    else:
        ok("picker: filter + held modifier -> %s"
           % macros.label(got[0], got[1]))

    # clearing an assignment
    ui_setup.handle("backspace")
    if st["profiles"][0]["keys"][3] != [0, macros.UNSET]:
        fail("backspace did not clear the assignment")
    else:
        ok("backspace clears an M key to unassigned")

    # second layer: the same four keys write slots 4..7
    m1_before = list(st["profiles"][0]["keys"][0])
    ui_setup.handle("layer")
    assert st["layer"] == 1, "layer toggle did not flip the state"
    for _ in range(_MENU_ROWS_MAX):
        if ui_setup.sel == 0:
            break
        ui_setup.handle("up")
    ui_setup.handle("enter")
    for ch in "f13":
        ui_setup.handle(ch)
    ui_setup.set_mods(0)
    ui_setup.handle("enter")
    want = [0, keytable.find("f13")[0]]
    if st["profiles"][0]["keys"][macros.slot(1, 0)] != want:
        fail("M5 assignment went to %r, expected slot %d"
             % (st["profiles"][0]["keys"], macros.slot(1, 0)))
    elif st["profiles"][0]["keys"][0] != m1_before:
        fail("assigning M5 modified M1 (%r -> %r)"
             % (m1_before, st["profiles"][0]["keys"][0]))
    else:
        ok("layer 2 writes M5..M8, leaving M1..M4 alone")
    ui_setup.handle("layer")
    assert st["layer"] == 0, "layer toggle did not flip back"

    # profile switch + rename
    for _ in range(_MENU_ROWS_MAX):
        if ui_setup.sel == macros.COUNT:
            break
        ui_setup.handle("down")
    assert ui_setup.sel == macros.COUNT, "cursor did not reach the profile row"
    ui_setup.handle("enter")
    assert ui_setup.mode == kbdui.PROFILES, "did not open the profile list"
    ui_setup.handle("down")
    ui_setup.handle("enter")
    if st["active"] != 1:
        fail("selecting profile 2 left active=%r" % st["active"])
    else:
        ok("profile switch selects profile 2")

    ui_setup.handle("enter")            # profile row again
    # the list opens on the ACTIVE profile, so walk down until Rename rather
    # than assuming a start position
    for _ in range(_PROFILE_ROWS_MAX):
        if ui_setup.sel == macros.PROFILES:
            break
        ui_setup.handle("down")
    assert ui_setup.sel == macros.PROFILES, "cursor did not reach Rename"
    ui_setup.handle("enter")
    assert ui_setup.mode == kbdui.RENAME, "Rename did not open"
    for ch in "coding99":
        ui_setup.handle(ch)
    ui_setup.handle("x")                # one past NAME_LEN, must be ignored
    ui_setup.handle("enter")
    if st["profiles"][1]["name"] != "coding99":
        fail("rename stored %r" % st["profiles"][1]["name"])
    else:
        ok("rename respects the %d-char limit" % macros.NAME_LEN)

    # exit all the way out
    ui_setup.handle("exit")
    ui_setup.handle("exit")
    if ui_setup.mode != kbdui.OFF:
        fail("exit did not close the overlay (mode=%r)" % ui_setup.mode)
    elif not saves[0] or not changes[0]:
        fail("overlay never called back (saves=%d changes=%d)"
             % (saves[0], changes[0]))
    else:
        ok("overlay closes; %d saves, %d keymap re-applies"
           % (saves[0], changes[0]))
except AssertionError as exc:
    fail("kbdui walkthrough: %s" % exc)


# --------------------------------------------------- stale files on device --
print("device")
drive = None
cands = ["/Volumes/CIRCUITPY"] + ["%s:\\" % c for c in "DEFGHIJKLMNOP"]
for cand in cands:
    try:
        if os.path.exists(os.path.join(cand, "boot_out.txt")):
            drive = cand
            break
    except OSError:
        continue
if drive is None:
    warn("CIRCUITPY not mounted - cannot check for stale device files")
else:
    ok("device mounted at %s" % drive)
    dev_fonts = os.path.join(drive, "fonts")
    if os.path.isdir(dev_fonts):
        wanted = set(os.listdir(FONTS))
        stale = [f for f in sorted(os.listdir(dev_fonts))
                 if f not in wanted and not f.startswith(".")]
        if stale:
            kb = sum(os.path.getsize(os.path.join(dev_fonts, f))
                     for f in stale) / 1024.0
            fail("stale fonts on device (deploy never deletes) - delete %s [%d KB]"
                 % (", ".join(stale), round(kb)))
        else:
            ok("no stale font files on device")
    if os.path.isdir(os.path.join(drive, "lib", "kmk")):
        ok("KMK present in lib/")
    else:
        warn("kmk/ not found in lib/ - Keyboard app will show its install hint")

# ---------------------------------------------------------------- verdict --
print("")
if FAILS:
    print("PREFLIGHT FAILED - %d problem(s), %d warning(s)"
          % (len(FAILS), len(WARNS)))
    for m in FAILS:
        print("  - %s" % m)
    sys.exit(1)
print("PREFLIGHT PASSED%s"
      % (" with %d warning(s)" % len(WARNS) if WARNS else ""))
for m in WARNS:
    print("  - %s" % m)
sys.exit(0)
