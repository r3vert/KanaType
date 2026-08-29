"""The wall clock carried across deep sleep, in nvm.

Split out of settings.py on purpose. The RP2040's RTC does not survive deep
sleep, so this is read on EVERY boot (code.py) and by the launcher's home
screen -- and settings.py imports macros + keytable, ~770 lines of source that
would then be parsed on the boot path for nothing. This module needs only
microcontroller.

The region sits immediately after settings' MAGIC-guarded blob and is guarded
by its own marker byte, so adding it never forced an nvm reset. OFFSET is
duplicated rather than imported (importing settings is the very cost this
avoids); preflight asserts it still equals settings._BLOB_END.

Layout, 8 bytes: mark, flags, year-2000, month, day, hour, minute, second.
"""
OFFSET = 105
MARK = 0xC1
SIZE = 8
END = OFFSET + SIZE
APPROX = 0x01      # flags bit 0: restored after a sleep, so it is a guess


def _nvm():
    try:
        import microcontroller

        return microcontroller.nvm
    except Exception:
        return None


def save(dt, approximate=True):
    """Stamp a time.struct_time into nvm. True if it was written."""
    nvm = _nvm()
    if nvm is None or len(nvm) < END:
        return False
    blob = bytes((
        MARK,
        APPROX if approximate else 0,
        max(0, min(255, dt.tm_year - 2000)),
        dt.tm_mon, dt.tm_mday, dt.tm_hour, dt.tm_min, dt.tm_sec,
    ))
    if bytes(nvm[OFFSET:END]) != blob:      # skip the flash write when unchanged
        nvm[OFFSET:END] = blob
    return True


def load():
    """(9-tuple accepted by rtc.RTC.datetime, approximate) or None."""
    nvm = _nvm()
    if nvm is None or len(nvm) < END or nvm[OFFSET] != MARK:
        return None
    flags = nvm[OFFSET + 1]
    year = 2000 + nvm[OFFSET + 2]
    mon, day = nvm[OFFSET + 3], nvm[OFFSET + 4]
    hour, minute, sec = nvm[OFFSET + 5], nvm[OFFSET + 6], nvm[OFFSET + 7]
    if not (1 <= mon <= 12 and 1 <= day <= 31 and hour < 24
            and minute < 60 and sec < 60):
        return None
    # tm_wday / tm_yday / tm_isdst are ignored by rtc.RTC on assignment
    return (year, mon, day, hour, minute, sec, 0, -1, -1), bool(flags & APPROX)


def approximate():
    """True when the stored time came back from a sleep and is a guess."""
    got = load()
    return bool(got and got[1])
