"""Screen geometry — the SINGLE source of truth shared by the firmware UI
(kanatype/ui.py) and the desktop renderer (tools/render.py).

PURE PYTHON ONLY: no displayio/board imports — this file must run on both
CircuitPython and desktop CPython. If you move a pixel here, both the panel
and the mockup renders move together; that's the point.

All y values are label CENTER lines (adafruit_display_text convention).
"""

WIDTH = 128
HEIGHT = 64

# Font roles. These are the DEVICE paths, and the device loads PCF: the
# adafruit_bitmap_font BDF loader keeps no glyph index and rescans the whole
# file for any uncached code point, while its PCF loader seeks straight to
# each glyph (PLAN.md has the measurements). The .bdf beside each .pcf is the
# SOURCE and stays in the repo for tools/render.py; `tools/bdf2pcf.py --all`
# regenerates the .pcf files and preflight fails if one is stale.
FONT_PATHS = {
    # Terminus bold 8x14, subset to ASCII (169 KB/1356 glyphs -> 15 KB/95).
    # This is the FIRST font loaded on every boot, so its parse time is the
    # black screen you stare at; the UI never draws anything but ASCII.
    "menu": "/fonts/ter-u14b_ascii.pcf",
    # k8x12 subset to ASCII+kana by tools/subset_font.py (845 KB -> 29 KB;
    # kanji dropped 2026-08 - no on-device use yet). 4px halfwidth, 8px
    # fullwidth, 12px tall.
    "jp": "/fonts/k8x12_kana.pcf",
    # 16px kana subset - big drill prompt (x2 = 32px). Unifont JP, subset to
    # ASCII+kana by tools/subset_font.py (Shinonome's upstream is dead: see
    # fonts/README.md). Advance 16 fullwidth / 8 halfwidth, ascent 14.
    "prompt": "/fonts/unifont_jp16_kana.pcf",
    # Same font dilated 1px right+down (subset_font.py --bold): heavier weight,
    # counters verified still open (mockups/bold_loop_check.png).
    "prompt_bold": "/fonts/unifont_jp16_kana_bold.pcf",
    # Noto Sans JP rasterized natively at 40px by tools/ttf2bdf.py (scale 1 =
    # full 40px of detail, unlike scaling a 16px source up). Advance 40
    # fullwidth / ~20 halfwidth, tight ascent 35 / descent 11. SIL OFL.
    "noto": "/fonts/notosansjp40.pcf",
}

# Prompt-font choices in picker order = Font 1..N. settings.py persists the
# INDEX into this tuple, so changing the order/length needs a settings.MAGIC bump.
PROMPT_FONTS = ("noto", "prompt", "prompt_bold", "jp")
# What the font picker calls them. "Font 1" told the user nothing about what
# they were choosing. Index-aligned with PROMPT_FONTS; preflight checks that.
PROMPT_FONT_NAMES = ("Noto Sans", "Unifont", "Unifont B", "k8x12")
# (ter-u16b.bdf stays in fonts/ as a spare — near-identical look, 3-item menus.)

# List screens (ui.Menu) — the practice config and the font picker; the
# launcher has its own HOME_* layout. jp font throughout, like every other
# screen: at the old 8px/char, "Reset to defaults" was 136px on a 128px panel,
# i.e. literally off the edge, and three more rows were close behind.
# Title inks y1..y11, so items start at 16; pitch 10 fits five rows with the
# last descender ending at 62.
MENU_TITLE_X = 2
MENU_TITLE_Y = 5
MENU_ITEM_X = 2
MENU_ITEM_Y0 = 16
MENU_PITCH = 10
MENU_MAX_VISIBLE = 5
# Cursor is its own 1-char label (moving it = one cheap y update, not four
# full label re-layouts — that was the menu-scroll lag, fixed 2026-08-13).
MENU_CURSOR = ">"
MENU_TEXT_DX = 8   # item text offset, leaves room for the cursor column

# Transient status, right of the title on the same row (jp font, so a
# 17-character message still fits). Empty unless there is something to say --
# a permanent "Enter: toggle" hint just ate the corner.
STATUS_X = 58
STATUS_Y = MENU_TITLE_Y
# Icons are right-aligned to STATUS_ICON_RIGHT and centred on STATUS_ICON_CY,
# so their own art dimensions decide placement — redraw at any size.
STATUS_ICON_RIGHT = 126
STATUS_ICON_CY = 6

# Plain text screens (ui.screen) — 4 lines of the 14px menu font.
SCREEN_X = 2
SCREEN_Y0 = 7
SCREEN_PITCH = 14
# Bottom hint line (jp font). Line 3 of SCREEN_PITCH collides with a wrapped
# 2-line message above it — found by tools/render.py, so hints live down here.
SCREEN_HINT_Y = HEIGHT - 7

# Practice drill screen (reflowed 2026-08: prompt gets the whole middle band).
#
#   +----------------------------------------+
#   | H                              12  <-- correct
#   | HC          [ BIG KANA ]      ----     |   fraction bar
#   |                                34  <-- answered
#   |                             +------+   |
#   |                             | ky-  | <-- typed answer, 3 slots
#   +-----------------------------+------+---+
#
# Enabled types run VERTICALLY down the left edge (a 16px column instead of a
# full-width title row) and the score stacks as a fraction on the right, which
# frees x 18..98 for the prompt — 40px per kana for a 2-kana combo.
DRILL_TYPES_X = 1
DRILL_TYPES_Y0 = 7
DRILL_TYPES_PITCH = 12

DRILL_PROMPT_CENTER_X = 59   # midpoint of the free band (x 10..109)

# Score is right-aligned to DRILL_SCORE_RIGHT rather than left-aligned in a
# fixed column, so 1- and 3-digit counts line up on their right edge.
DRILL_SCORE_RIGHT = 126
DRILL_SCORE_Y = 7            # correct-first-try count
DRILL_SCORE_RULE = (111, 14, 16, 1)   # x, y, w, h - the fraction bar
DRILL_TOTAL_Y = 22           # total answered

# Typed-answer box. 3 slots is exact: the longest accepted romaji in the whole
# deck is 3 chars (kya/shi/tsu/...), verified against kana.answers().
DRILL_ANSWER_BOX = (110, 33, 17, 19)  # x, y, w, h outline
DRILL_ANSWER_X = 112                  # first slot, centred in the box
DRILL_ANSWER_Y = 43                  # label center inside the box
DRILL_ANSWER_SLOTS = 3
DRILL_ANSWER_BLANK = "-"

# After a miss, the correct reading is shown centred beneath the prompt while
# the wrong input stays in the box, so the two can be compared directly.
# y=57 inks 53..63 in the jp font: below every prompt font (the tallest, jp x4,
# ends at 52) and left of the answer box, which starts at x110.
DRILL_MISS_Y = 57

# MEASURED from k8x12_kana.bdf - the earlier 8/12 guess was wrong and threw
# off every right-alignment on the drill screen.
JP_CHAR_W = 4          # jp-font halfwidth (ASCII) advance
JP_KANA_W = 8          # jp-font fullwidth (kana) advance

# Prompt styles: font role -> (kana advance px, scale, label center y).
# Each y vertically centres that font's glyph box in the band; the rendered
# height is advance*scale square for the kana.
DRILL_PROMPT_STYLES = {
    "noto": (40, 1, 31),
    "prompt": (16, 2, 30),
    "prompt_bold": (16, 2, 30),
    "jp": (8, 4, 32),      # 8px fullwidth kana x4 = 32px
}

# ------------------------------------------------------------ home screen --
# Apps down the left in the jp font, clock and power state on the right, split
# by a rule. The clock is a FOCUS TARGET one past the last app -- Enter on it
# opens the Clock app, which is why Clock is not in the app list itself.
HOME_ITEM_X = 2
HOME_TEXT_DX = 8
HOME_ITEM_Y0 = 8
HOME_PITCH = 11
HOME_DIVIDER = (54, 2, 1, 60)      # x, y, w, h
HOME_RIGHT_X = 58
HOME_RIGHT_W = WIDTH - HOME_RIGHT_X - 2
HOME_TITLE_Y = 7
HOME_TIME_Y = 22
HOME_DATE_Y = 35
HOME_CURSOR_DX = 2                 # clock's focus cursor, right of the rule
# "~" marks a clock restored after deep sleep. Drawn as its OWN label in the
# left margin, never prefixed to the string, so the time does not shift when
# the flag appears. +4 puts its ink on the digits' centre line: measured, the
# menu font's tilde inks at y-5..-3 while a digit inks at y-4..+5.
HOME_APPROX_DX = -10
HOME_APPROX_DY = 4
# Power state: outline + terminal nub, then the state spelled out beside it.
# Deliberately NOT a fill gauge -- VBAT is unconnected on this board and every
# analog pin is taken, so charge level is unmeasurable and a bar would lie.
HOME_BATT = (72, 48, 20, 9)        # x, y, w, h outline
HOME_BATT_NUB = (2, 3)             # w, h, centred on the right edge
HOME_BATT_LABEL_DX = 5

# ---------------------------------------------------------- keyboard app --
# Base screen. Two columns split by a rule: the LEFT carries the things the
# board's silkscreen does not print (the number row's shifted symbols), the
# RIGHT carries the live M-key assignments. jp font (4px halfwidth) is what
# makes two columns fit at all - 32 characters per line instead of 16.
KBD_TITLE_Y = 6
KBD_COL_L_X = 2
KBD_COL_R_X = 52
KBD_ROW_Y = (22, 33, 44, 55)         # four rows, shared by both columns
KBD_DIVIDER = (46, 16, 1, 45)        # x, y, w, h - vertical rule
# The number row is silkscreened 1..0 with no shifted legend, so it is the
# one part of the board you cannot read off the keycaps.
KBD_NUM_DIGITS = "1234567890"
KBD_NUM_SYMBOLS = "!@#$%^&*()"
# Layer 2 replaces the number row with F1..F10. Those names cannot be printed
# under their digits -- "F10" is 3 characters where the digit is 1 -- so the
# second row states the mapping instead of aligning to it.
KBD_FN_ROW = "-> F1-F10"
# 11 chars max: the left column is only KBD_COL_R_X-KBD_COL_L_X wide and the
# jp font advances 4px, so anything longer runs under the M assignments.
# Both MENU gestures, on the two spare left-column rows: a hold that is not
# advertised is not findable. MENU is the only key with tap/hold behaviour, so
# the subject is unambiguous even without room to name it.
KBD_HINT_TAP = "tap: setup"
KBD_HINT_HOLD = "hold: exit"

# Setup menu (tap MENU). jp font list so five rows fit without scrolling.
KBD_MENU_TITLE_Y = 6
KBD_MENU_X = 2
KBD_MENU_TEXT_DX = 8
KBD_MENU_VALUE_X = 46
KBD_MENU_Y0 = 18
KBD_MENU_PITCH = 10
KBD_MENU_MAX_VISIBLE = 5

# Key picker. Type-to-filter rather than scrolling categories: the device IS
# a keyboard, so the fastest search is the one already under your fingers.
KBD_PICK_TITLE_Y = 6
KBD_PICK_FILTER_X = 2
KBD_PICK_FILTER_Y = 20
KBD_PICK_Y0 = 32
KBD_PICK_PITCH = 10
KBD_PICK_X = 2
KBD_PICK_TEXT_DX = 8
KBD_PICK_MAX_VISIBLE = 3

# App title — shown on the menu and the loading splash, same position.
TITLE = "KanaType"

# Loading screen. The title and loading text are BAKED INTO
# /assets/loading.bmp by tools/make_splash.py (source art:
# mockups/loading_art.txt) so the splash needs no font and can paint before
# the font parse. These constants are what that tool bakes with — change them
# and re-run make_splash.py.
LOADING_TEXT_X = MENU_TITLE_X
LOADING_TEXT_Y = 20
CHAR_W = 8  # menu-font advance, used for text-width math
