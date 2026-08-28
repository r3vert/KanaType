#!/usr/bin/env python3
"""Draw the physical keyboard, straight from kanatype/keymap.py.

keymap.py is the single source of truth for both KMK and the app input driver,
but it stores keys in matrix order, which is unreadable as a picture of the
board. This draws the board, so a legend edit can be eyeballed before deploy.

Views (any number, in any order; default `legend`):
  legend   what the key types over USB (KMK name)
  app      logical code the app platform sees ("-" = no app meaning)
  matrix   (scan row, scan col)
  sw       PCB switch reference

Usage:
  python keychart.py [legend|app|matrix|sw|all ...]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from kanatype import keymap  # noqa: E402

# Hardware modifiers are off-matrix, so LAYOUT cannot place them. Their
# physical position is the one thing here that is not derivable from keymap.py
# (it comes from the PCB); what they SEND is derived, so a remap follows.
MOD_PIN_BY_NAME = {"SHIFT1": "A1", "CTRL1": "A2", "CMD": "D4"}
# 0-based physical row -> what sits left of that row's matrix keys. Verified
# against footprint placement in KanaType.kicad_pcb: CTRL1 (152.0, 81.5) is
# leftmost on row 4, CTRL2/CMD (152.5, 87.5) then SHIFT1 (158.5, 87.5) on
# row 5. None is a real empty position: row 4 has a hole where row 5 has
# SHIFT1, so the columns line up as they do on the board.
MODS_BY_ROW = {3: ["CTRL1", None], 4: ["CMD", "SHIFT1"]}


def mod_kmk(name):
    pin = MOD_PIN_BY_NAME[name]
    return keymap.MOD_KMK_NAMES[keymap.MOD_PIN_NAMES.index(pin)]


def cell(view, entry):
    """(top line, bottom line) for one key."""
    if entry is None:                               # empty board position
        return "", ""
    if isinstance(entry, str):                      # a modifier
        return entry, mod_kmk(entry)
    sw, r, c, app, kmk = entry
    rc = "%d,%d" % (r, c)
    if view == "legend":
        # MENU and the macro keys send nothing over USB; "NO" is not a legend
        if (r, c) == keymap.MENU_KEY:
            return "MENU", rc
        if (r, c) == keymap.LAYER_KEY:
            return "LAYER", rc
        macro = keymap.macro_label((r, c))
        if macro:
            return macro, rc
        return kmk, rc
    if view == "app":
        return (app or "-"), rc
    if view == "matrix":
        return rc, sw
    if view == "sw":
        return sw, kmk
    raise SystemExit("unknown view: %s" % view)


def rows(view):
    out = []
    for i, row in enumerate(keymap.LAYOUT):
        out.append([cell(view, m) for m in MODS_BY_ROW.get(i, [])]
                   + [cell(view, e) for e in row])
    return out


def draw(view):
    grid = rows(view)
    w = max(len(s) for row in grid for pair in row for s in pair)
    out = []
    # ASCII box characters on purpose: the Windows console is cp1252 and
    # raises UnicodeEncodeError on box-drawing glyphs.
    for row in grid:
        rule = "+" + "+".join(["-" * (w + 2)] * len(row)) + "+"
        out.append(rule)
        for idx in (0, 1):
            out.append("|"
                       + "|".join(" %-*s " % (w, pair[idx]) for pair in row)
                       + "|")
        out.append(rule)
    return chr(10).join(out)


VIEWS = ("legend", "app", "matrix", "sw")
TITLES = {
    "legend": "USB legend (KMK) / scan row,col",
    "app": "app input code / scan row,col",
    "matrix": "scan row,col / PCB switch",
    "sw": "PCB switch / USB legend",
}


def main(argv):
    wanted = [a for a in argv if not a.startswith("-")] or ["legend"]
    if "all" in wanted:
        wanted = list(VIEWS)
    for view in wanted:
        print("%s  -  %s" % (view.upper(), TITLES[view]))
        print(draw(view))
        print("")
    n = sum(len(r) for r in keymap.LAYOUT)
    print("%d matrix keys + %d hardware modifiers = %d keys"
          % (n, len(keymap.MOD_PIN_NAMES), n + len(keymap.MOD_PIN_NAMES)))
    print("(HANDOFF's \"61 switches\" also counts RESET1 and WAKE1, "
          "which are not keys)")
    print("MENU key at scan %d,%d: sends nothing over USB; hold it in keyboard "
          "mode for the launcher" % keymap.MENU_KEY)
    print("modifiers are off-matrix (ROW9=%s held low): %s"
          % (keymap.ROW9_PIN_NAME,
             ", ".join("%s=%s->%s" % (nm, MOD_PIN_BY_NAME[nm], mod_kmk(nm))
                       for nm in ("CTRL1", "CMD", "SHIFT1"))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
