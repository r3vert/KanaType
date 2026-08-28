"""Physical keymap — single source of truth for BOTH the KMK keyboard app and
the app-platform MatrixInput driver (PLAN.md parity rule).

Grid derived from the PCB netlist + placement data (5 rows x 12 cols).
Each entry: (sw_ref, matrix_row 1-7, matrix_col 1-8, app_code, kmk_name)
  app_code: logical code for kanatype.input (None = no app meaning yet)
  kmk_name: attribute of kmk.keys.KC for USB keyboard mode

PROVISIONAL Preonic-style QWERTY — edit legends here and both worlds follow.
Hardware modifiers (CTRL1/CTRL2/SHIFT1) are off-matrix: see MOD_* below.
PURE PYTHON: no board imports (desktop renderer reads this file too).
"""

# Feather pin NAMES (resolved via getattr(board, name) on-device).
ROW_PIN_NAMES = ("D13", "D12", "D11", "D10", "D9", "D6", "D5")   # ROW1..ROW7
COL_PIN_NAMES = ("TX", "RX", "MISO", "MOSI", "SCK", "D25", "D24", "A3")  # COL1..COL8
ROW9_PIN_NAME = "A0"    # held LOW so modifiers read as ground-switched keys
# Hardware modifier keys by PCB net: A1=SHIFT1, A2=CTRL1, D4=CTRL2("CMD").
# USB functions remapped per user (2026-08): SHIFT1 key -> Alt,
# CTRL1 key -> Shift, CMD key -> Ctrl. No GUI key on this board.
MOD_PIN_NAMES = ("A1", "A2", "D4")
MOD_KMK_NAMES = ("LALT", "LSFT", "LCTL")

# MENU key (SW3, physically under Tab; was GRV). Holding it in keyboard mode
# returns to the launcher -- it replaced the Ctrl+Alt+Shift chord, which fired
# the instant all three went down and so could not be held deliberately.
# It sends NOTHING over USB ("NO"): the host repeats a held character, so a
# key you are meant to hold cannot also type one. In the apps it reads as
# "exit", the same code as ESC.
MENU_KEY = (1, 3)          # (matrix_row, matrix_col)

# User-assignable macro keys, left to right:
#     M1 = SW13 (2,5)   M2 = SW23 (3,4)   M3 = SW33 (5,1)   M4 = SW43 (5,6)
# Positions verified by matching silkscreen gr_text to footprint placement in
# KanaType.kicad_pcb. BOARD ERRATUM: the silkscreen prints M1/M2/M3 but has no
# legend for M4 (SW43) -- the key is unlabelled on the PCB, so the on-screen
# assignment list is the only place it is identified. Fix in v2.
# SW57 (7,5) is the spacebar and carries the SPACE legend, on its own.
# NOTE: LAYOUT still maps M2/M3/M4 as SPC -- they type a space today. That is
# corrected when the macro system lands.
MACRO_KEYS = ((2, 5), (3, 4), (5, 1), (5, 6))

# LAYER toggle: SW4, the unlabelled key right of the spacebar. Pressed (not
# held) it flips to a second layer where the macro keys become M5..M8 and the
# number row becomes function keys.
LAYER_KEY = (1, 4)

# What the second layer changes. Keyed by KMK NAME rather than by coordinate,
# so re-arranging LAYOUT moves these with it instead of silently pointing at
# whatever key inherited the position. The number row only has ten keys, so
# F11/F12 land on Q and W.
LAYER2_KMK = {
    "N1": "F1", "N2": "F2", "N3": "F3", "N4": "F4", "N5": "F5",
    "N6": "F6", "N7": "F7", "N8": "F8", "N9": "F9", "N0": "F10",
    "Q": "F11", "W": "F12",
}


def menu_matrix_index():
    """MENU_KEY as a KMK KeyMatrix flat index (same order as kmk_matrix_names)."""
    return (MENU_KEY[0] - 1) * 8 + (MENU_KEY[1] - 1)


def macro_matrix_indices():
    """MACRO_KEYS as KMK KeyMatrix flat indices, M1..M4 in order."""
    return [(r - 1) * 8 + (c - 1) for r, c in MACRO_KEYS]


def layer_matrix_index():
    """LAYER_KEY as a KMK KeyMatrix flat index."""
    return (LAYER_KEY[0] - 1) * 8 + (LAYER_KEY[1] - 1)


def layer2_overrides():
    """{flat index: KMK name} for every key the second layer replaces."""
    out = {}
    for row in LAYOUT:
        for _sw, r, c, _app, kmk in row:
            if kmk in LAYER2_KMK:
                out[(r - 1) * 8 + (c - 1)] = LAYER2_KMK[kmk]
    return out


def macro_label(rc):
    """'M1'..'M4' for a macro key's (row, col), else None."""
    try:
        return "M%d" % (MACRO_KEYS.index(tuple(rc)) + 1)
    except ValueError:
        return None

# 56 matrix keys, physical rows top-to-bottom, left-to-right.
LAYOUT = [
    [  # row 1 (top)
        ("SW1", 1, 1, "exit", "ESC"), ("SW9", 2, 1, "1", "N1"),
        ("SW19", 3, 2, "2", "N2"), ("SW29", 3, 7, "3", "N3"),
        ("SW39", 5, 4, "4", "N4"), ("SW49", 7, 1, "5", "N5"),
        ("SW5", 1, 5, "6", "N6"), ("SW15", 2, 7, "7", "N7"),
        ("SW25", 3, 5, "8", "N8"), ("SW35", 5, 2, "9", "N9"),
        ("SW45", 5, 7, "0", "N0"), ("SW61", 7, 7, "backspace", "BSPC"),
    ],
    [  # row 2
        ("SW2", 1, 2, None, "TAB"), ("SW10", 2, 2, "q", "Q"),
        ("SW20", 4, 2, "w", "W"), ("SW30", 4, 7, "e", "E"),
        ("SW40", 6, 4, "r", "R"), ("SW51", 7, 2, "t", "T"),
        ("SW6", 1, 6, "y", "Y"), ("SW16", 2, 8, "u", "U"),
        ("SW26", 4, 5, "i", "I"), ("SW36", 6, 2, "o", "O"),
        ("SW46", 6, 7, "p", "P"), ("SW63", 7, 8, "backspace", "DEL"),
    ],
    [  # row 3 (home)
        ("SW3", 1, 3, "exit", "NO"), ("SW11", 2, 3, "a", "A"),
        ("SW21", 3, 3, "s", "S"), ("SW31", 3, 8, "d", "D"),
        ("SW41", 5, 5, "f", "F"), ("SW53", 7, 3, "g", "G"),
        ("SW7", 1, 7, "h", "H"), ("SW17", 3, 1, "j", "J"),
        ("SW27", 3, 6, "k", "K"), ("SW37", 5, 3, "l", "L"),
        ("SW47", 5, 8, None, "SCLN"), ("SW59", 7, 6, "enter", "ENT"),
    ],
    [  # row 4 (CTRL1 hardware modifier sits physically leftmost)
        ("SW12", 2, 4, "z", "Z"), ("SW22", 4, 3, "x", "X"),
        ("SW32", 4, 8, "c", "C"), ("SW42", 6, 5, "v", "V"),
        ("SW55", 7, 4, "b", "B"), ("SW8", 1, 8, "n", "N"),
        ("SW18", 4, 1, "m", "M"), ("SW28", 4, 6, None, "COMM"),
        ("SW38", 6, 3, None, "DOT"), ("SW48", 6, 8, "hint", "SLSH"),
    ],
    [  # row 5 (bottom; CTRL2=CMD and SHIFT1 sit physically leftmost)
        # M1 still types "-": it is the ONLY minus on the board (the number
        # row has no MINS/EQL), so nulling it would leave no hyphen at all.
        ("SW13", 2, 5, None, "MINS"),
        # M2/M3/M4 were SPC, which contradicted the silkscreen -- they typed a
        # space. Unassigned until the macro system lands; SW57 is the spacebar.
        ("SW23", 3, 4, None, "NO"),
        ("SW33", 5, 1, None, "NO"), ("SW43", 5, 6, None, "NO"),
        ("SW57", 7, 5, "space", "SPC"),
        # LAYER toggle (right of space, unlabelled on the silkscreen). Was
        # RBRC -- the board's only "]", now gone. Sends nothing: it is a
        # toggle, and a key that also typed would fire on every press.
        ("SW4", 1, 4, "layer", "NO"),
        ("SW14", 2, 6, "up", "UP"), ("SW24", 4, 4, "down", "DOWN"),
        ("SW34", 6, 1, "left", "LEFT"), ("SW44", 6, 6, "right", "RGHT"),
    ],
]


def matrix_app_codes():
    """{(matrix_row, matrix_col): app_code} for the input driver."""
    return {(r, c): app for row in LAYOUT for _sw, r, c, app, _k in row}


def kmk_matrix_names():
    """56-entry list of KC names in KeyMatrix coord order (row-major
    ROW1..ROW7 x COL1..COL8) for the KMK keymap."""
    names = ["NO"] * 56
    for row in LAYOUT:
        for _sw, r, c, _app, kmk in row:
            names[(r - 1) * 8 + (c - 1)] = kmk
    return names
