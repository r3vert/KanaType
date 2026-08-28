"""Filesystem helpers: write-session detection and crash-safe appends."""
import os


def writable():
    """True when boot.py granted this session a writable filesystem."""
    try:
        import storage as _storage

        return not _storage.getmount("/").readonly
    except Exception:
        return False


def append(path, text):
    """Append + flush + sync — data must be on flash before any sleep/blank.
    Caller is responsible for checking writable() first."""
    with open(path, "ab") as f:
        f.write(text.encode("utf-8"))
        f.flush()
    os.sync()
