"""Persistent settings in microcontroller.nvm.

nvm is a reserved flash region OUTSIDE the FAT filesystem, so it is writable
even while the USB host owns the CIRCUITPY drive (files are not, until the
M2 write-session work). Survives reboots, deep sleep, and power loss.

Layout (version-tagged; bump MAGIC when it changes):
  [0:4]  b"KT06" magic
  [4]    practice flags: bit0 H, bit1 K, bit2 HC, bit3 KC, bit4 instant
  [5]    practice font index into FONT_ORDER
  [6:8]  keytable.HASH, big-endian -- see load_macros
  [8]    active macro profile index
  [9:105]  4 profiles x (8-byte name + 8 x (mod bits, key index))
  [105:113] clock stamp carried across deep sleep, under its OWN marker byte
            (not MAGIC) so adding it did not reset the regions above
Future consumers (quick-note wake routing etc.) append bytes and bump MAGIC.

The regions are written independently: save_practice touches only [0:6],
save_macros only [0:4] and [6:105], save_clock only [105:113] — so none of
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


# ---- clock carry-over across deep sleep -----------------------------------
# The RP2040 has no battery-backed RTC domain and CircuitPython's deep sleep
# "shuts down power to nearly all of the microcontroller" -- confirmed on
# hardware 2026-08-28: set the clock, sleep, wake, RTC is unset. sleepmode.py
# stamps the wall clock here on the way down and code.py puts it back on the
# way up.
#
# This region sits AFTER _BLOB_END and is guarded by its own marker byte
# rather than the file MAGIC, deliberately: bumping MAGIC would reset the
# macro profiles and practice settings a third time in one day. On a device
# that has never stored a time these bytes read as zero, the marker fails,
# and load_clock() reports nothing.
_OFF_CLOCK = _BLOB_END
_CLOCK_MARK = 0xC1
_CLOCK_SIZE = 8          # mark, flags, year-2000, month, day, hour, min, sec
_CLOCK_END = _OFF_CLOCK + _CLOCK_SIZE
_CLOCK_APPROX = 0x01     # flags bit 0: restored, so the seconds are a guess


def save_clock(dt, approximate=True):
    """Stamp a time.struct_time into nvm. Returns True if it was written."""
    nvm = _nvm()
    if nvm is None or len(nvm) < _CLOCK_END:
        return False
    blob = bytes((
        _CLOCK_MARK,
        _CLOCK_APPROX if approximate else 0,
        max(0, min(255, dt.tm_year - 2000)),
        dt.tm_mon, dt.tm_mday, dt.tm_hour, dt.tm_min, dt.tm_sec,
    ))
    if bytes(nvm[_OFF_CLOCK:_CLOCK_END]) != blob:
        nvm[_OFF_CLOCK:_CLOCK_END] = blob
    return True


def load_clock():
    """(struct_time-compatible 9-tuple, approximate) or None."""
    nvm = _nvm()
    if nvm is None or len(nvm) < _CLOCK_END or nvm[_OFF_CLOCK] != _CLOCK_MARK:
        return None
    flags = nvm[_OFF_CLOCK + 1]
    year = 2000 + nvm[_OFF_CLOCK + 2]
    mon, day = nvm[_OFF_CLOCK + 3], nvm[_OFF_CLOCK + 4]
    hour, minute, sec = (nvm[_OFF_CLOCK + 5], nvm[_OFF_CLOCK + 6],
                         nvm[_OFF_CLOCK + 7])
    if not (1 <= mon <= 12 and 1 <= day <= 31 and hour < 24
            and minute < 60 and sec < 60):
        return None
    # tm_wday/tm_yday/tm_isdst are ignored by rtc.RTC on assignment
    return (year, mon, day, hour, minute, sec, 0, -1, -1), bool(flags & _CLOCK_APPROX)


def reset():
    """Invalidate saved settings -> defaults on next load."""
    nvm = _nvm()
    if nvm is not None and bytes(nvm[0:4]) == MAGIC:
        nvm[0:4] = b"\x00\x00\x00\x00"
