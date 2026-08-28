"""M-key assignments: what M1..M4 send, and the profiles that hold them.

An assignment is (modifier bits, index into keytable.NAMES). That is two
bytes, which is what makes four profiles fit in nvm, and it is all KMK needs:
modifier keys are CALLABLE, so KC.LCTL(KC.C) *is* Ctrl+C. No macro module is
involved -- kmk.modules.macros exists for multi-step sequences and is a
separate, later thing (PLAN.md).

PURE PYTHON: no board/displayio imports, so the desktop renderer and preflight
can both use it.
"""
from kanatype import keymap, keytable

# bit, KMK modifier name, label. Order decides how a combo reads: Ctrl+Shift+V.
# These are what the key SENDS, not what the board's keycaps say -- the
# physical CMD key sends LCTL, CTRL1 sends LSFT, SHIFT1 sends LALT.
MOD_BITS = (
    (0x01, "LCTL", "Ctrl"),
    (0x02, "LSFT", "Shift"),
    (0x04, "LALT", "Alt"),
    (0x08, "LGUI", "Gui"),
)

COUNT = len(keymap.MACRO_KEYS)      # physical macro keys
LAYERS = 2                          # base -> M1..M4, layer 2 -> M5..M8
SLOTS = COUNT * LAYERS              # assignments stored per profile
PROFILES = 4
NAME_LEN = 8                        # bytes per profile name in nvm

# "no key assigned". A real sentinel, not index 0 -- index 0 is the letter A,
# and an unassigned slot that quietly types "a" is worse than one that is
# visibly empty. Stored as-is in nvm; to_kc turns it into KC.NO.
UNSET = 0xFF


def index_of(name, fallback=0):
    try:
        return keytable.NAMES.index(name)
    except ValueError:
        return fallback


# Factory assignments. M1 defaults to MINUS deliberately: the number row has
# no MINS/EQL, so before the macro system M1 was the only hyphen on the whole
# board and clearing it would leave no way to type one.
DEFAULTS = (
    (0x00, index_of("MINUS")),
    (0x01, index_of("C")),
    (0x01, index_of("V")),
    (0x03, index_of("V")),
)


def slot(layer, i):
    """Assignment index for macro key i on the given layer. M1..M4 are
    slots 0..3, M5..M8 are slots 4..7."""
    return layer * COUNT + i


def slot_name(index):
    return "M%d" % (index + 1)


def valid(mods, idx):
    if not 0 <= mods <= 0x0F:
        return False
    return idx == UNSET or 0 <= idx < len(keytable.NAMES)


def label(mods, idx, limit=0):
    """'Ctrl+Shift+V'. Truncated with a trailing ~ if limit is given."""
    if idx == UNSET:
        return "-"
    if not valid(mods, idx):
        return "?"
    parts = [text for bit, _name, text in MOD_BITS if mods & bit]
    parts.append(keytable.SHORT[idx])
    out = "+".join(parts)
    if limit and len(out) > limit:
        out = out[:limit - 1] + "~"
    return out


def to_kc(KC, mods, idx):
    """Build the KMK key. KC is passed in so this module imports nothing
    board-specific and stays testable on the desktop."""
    if idx == UNSET or not valid(mods, idx):
        return KC.NO
    key = getattr(KC, keytable.NAMES[idx])
    for bit, name, _text in MOD_BITS:
        if mods & bit:
            key = getattr(KC, name)(key)
    return key


def mods_from_kmk(names):
    """Modifier bits for a set of KMK modifier names currently held -- used to
    bake the held modifiers into an assignment at confirm time."""
    bits = 0
    for bit, name, _text in MOD_BITS:
        if name in names:
            bits |= bit
    return bits


def default_profile():
    """M1..M4 from DEFAULTS; M5..M8 start unassigned."""
    keys = [list(a) for a in DEFAULTS]
    keys += [[0, UNSET] for _ in range(SLOTS - len(keys))]
    return keys


def blank_profiles():
    """Factory state: profile 1 carries the defaults, the rest are empty."""
    out = []
    for i in range(PROFILES):
        if i == 0:
            out.append({"name": "Default", "keys": default_profile()})
        else:
            out.append({"name": "",
                        "keys": [[0, UNSET] for _ in range(SLOTS)]})
    return out
