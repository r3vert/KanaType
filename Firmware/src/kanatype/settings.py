"""Persistent settings in microcontroller.nvm.

nvm is a reserved flash region OUTSIDE the FAT filesystem, so it is writable
even while the USB host owns the CIRCUITPY drive (files are not, until the
M2 write-session work). Survives reboots, deep sleep, and power loss.

Layout (version-tagged; bump MAGIC when it changes):
  [0:4]  b"KT06" magic
  [4]    practice flags: bit0 H, bit1 K, bit2 HC, bit3 KC, bit4 instant,
         bit5 correction mode
  [5]    practice font index into FONT_ORDER
  [6:8]  keytable.HASH, big-endian -- see load_macros
  [8]    active macro profile index
  [9:105]  4 profiles x (8-byte name + 8 x (mod bits, key index))
  [105:113] clock stamp across deep sleep -- owned by kanatype/clockstore.py,
            under its OWN marker byte (not MAGIC), so adding it reset nothing
Future consumers (quick-note wake routing etc.) append bytes and bump MAGIC.

The regions are written independently: save_practice touches only [0:6],
save_macros only [0:4] and [6:105], clockstore only [105:113] — so none of
them clobbers another.

Every function degrades to no-op/None on builds without nvm.
"""
from kanatype import keytable, layout, macros

# Bump on every PROMPT_FONTS change: a stored index would otherwise decode to
# the wrong font. KT02 = bold added, KT03 = Noto added, KT04 = "small" dropped,
# KT05 = macro profiles added, KT06 = second macro layer (M5-M8).
MAGIC = b"KT06"
FONT_ORDER = layout.PROMPT_FONTS  # index stored in nvm byte 5

_CAT_BITS = (("H", 1), ("K", 2), ("HC", 4), ("KC", 8))
_INSTANT_BIT = 16
# bit 5 = correction mode. Appended to the EXISTING flags byte, so no MAGIC
# bump: a device saved under KT06 reads this as 0 = Bypass, which is exactly
# the behaviour it had before the option existed.
_CORRECT_BIT = 32

_OFF_HASH = 6
_OFF_ACTIVE = 8
_OFF_PROFILES = 9
_PROFILE_SIZE = macros.NAME_LEN + macros.SLOTS * 2
_BLOB_END = _OFF_PROFILES + macros.PROFILES * _PROFILE_SIZE


def _nvm():
    try:
        import microcontroller

        return microcontroller.nvm
    except Exception:
        return None


def load_practice():
    """Saved practice config dict, or None if absent/invalid."""
    nvm = _nvm()
    if nvm is None or bytes(nvm[0:4]) != MAGIC:
        return None
    flags = nvm[4]
    font_i = nvm[5]
    if font_i >= len(FONT_ORDER):
        return None
    opts = {name: bool(flags & bit) for name, bit in _CAT_BITS}
    if not any(opts[name] for name, _bit in _CAT_BITS):
        # A drill with no categories cannot build a deck. This happens on a
        # fresh nvm whose magic was written by save_macros before practice ran
        # once; treat it as "unset" so the caller falls back to its defaults.
        return None
    opts["instant"] = bool(flags & _INSTANT_BIT)
    opts["correct"] = bool(flags & _CORRECT_BIT)
    opts["font"] = FONT_ORDER[font_i]
    return opts


def save_practice(opts):
    nvm = _nvm()
    if nvm is None:
        return
    flags = 0
    for name, bit in _CAT_BITS:
        if opts.get(name):
            flags |= bit
    if opts.get("instant"):
        flags |= _INSTANT_BIT
    if opts.get("correct"):
        flags |= _CORRECT_BIT
    blob = MAGIC + bytes((flags, FONT_ORDER.index(opts.get("font", "prompt"))))
    if bytes(nvm[0:len(blob)]) != blob:  # skip the flash write when unchanged
        nvm[0:len(blob)] = blob


def _name_to_bytes(name):
    out = bytearray(macros.NAME_LEN)
    for i, ch in enumerate(name[:macros.NAME_LEN]):
        c = ord(ch)
        out[i] = c if 32 <= c < 127 else 32
    return bytes(out)


def _name_from_bytes(raw):
    chars = []
    for b in raw:
        if b == 0:
            break
        chars.append(chr(b) if 32 <= b < 127 else " ")
    return "".join(chars).rstrip()


def load_macros():
    """(active index, profiles) or None if absent/invalid.

    Returns None when keytable.HASH disagrees with the stored one: saved
    assignments are INDICES into keytable.NAMES, so a regenerated table would
    otherwise silently decode every macro to the wrong key.
    """
    nvm = _nvm()
    if nvm is None or len(nvm) < _BLOB_END or bytes(nvm[0:4]) != MAGIC:
        return None
    stored_hash = (nvm[_OFF_HASH] << 8) | nvm[_OFF_HASH + 1]
    if stored_hash != keytable.HASH:
        return None
    profiles = []
    for p in range(macros.PROFILES):
        base = _OFF_PROFILES + p * _PROFILE_SIZE
        name = _name_from_bytes(bytes(nvm[base:base + macros.NAME_LEN]))
        keys = []
        for k in range(macros.SLOTS):
            off = base + macros.NAME_LEN + k * 2
            mods, idx = nvm[off], nvm[off + 1]
            if not macros.valid(mods, idx):
                mods, idx = 0, macros.UNSET   # clamp, don't discard the rest
            keys.append([mods, idx])
        profiles.append({"name": name, "keys": keys})
    active = nvm[_OFF_ACTIVE]
    if active >= macros.PROFILES:
        active = 0
    return active, profiles


def save_macros(active, profiles):
    nvm = _nvm()
    if nvm is None or len(nvm) < _BLOB_END:
        return
    blob = bytearray()
    blob.append((keytable.HASH >> 8) & 0xFF)
    blob.append(keytable.HASH & 0xFF)
    blob.append(active & 0xFF)
    for p in range(macros.PROFILES):
        prof = profiles[p]
        blob += _name_to_bytes(prof["name"])
        for k in range(macros.SLOTS):
            mods, idx = prof["keys"][k]
            blob.append(mods & 0xFF)
            blob.append(idx & 0xFF)
    if bytes(nvm[0:4]) != MAGIC:
        nvm[0:4] = MAGIC
    if bytes(nvm[_OFF_HASH:_BLOB_END]) != bytes(blob):  # skip a flash write
        nvm[_OFF_HASH:_BLOB_END] = bytes(blob)


# The clock carried across deep sleep lives in kanatype/clockstore.py, not
# here: it is read on every boot and this module imports macros + keytable,
# which is ~770 lines of source that the boot path should not pay for.
# clockstore.OFFSET must equal _BLOB_END below; preflight asserts it.


def reset():
    """Invalidate saved settings -> defaults on next load."""
    nvm = _nvm()
    if nvm is not None and bytes(nvm[0:4]) == MAGIC:
        nvm[0:4] = b"\x00\x00\x00\x00"
