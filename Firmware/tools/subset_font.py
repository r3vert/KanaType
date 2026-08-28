#!/usr/bin/env python3
"""Subset a BDF font to selected codepoints (desktop Python, stdlib only).

Full CJK-capable BDFs are tens of MB — far too big for the device's ~6 MB of
free flash, and pointless when a screen only ever shows kana. Subsetting IS
the compression: keep ~400 glyphs and the file drops to tens of KB, with no
decompressor needed on-device (see PLAN.md, font variety notes).

Usage:
  python subset_font.py IN.bdf OUT.bdf [--ranges SPEC] [--bold] [--quiet]

--bold synthesizes a heavier weight by dilating each glyph one pixel right and
down (inside its existing bounding box). Thin 1px strokes read as spindly once
a small font is scaled up on a 1-bit panel; dilation restores weight while
keeping the higher source detail. Ink already touching the box's right/bottom
edge is clipped, which is why it stays a per-font judgement call — render it
before adopting it.

SPEC is a comma-separated list of presets and/or explicit hex ranges:
  presets: ascii, hiragana, katakana, kana (= hiragana+katakana+marks), latin1
  ranges:  0x3041-0x3096  or a single codepoint  0x30fc
  default: ascii,kana

Output keeps the source header/properties verbatim (CHARS and, if needed,
STARTPROPERTIES/DEFAULT_CHAR are corrected), so it stays a valid BDF for
adafruit_bitmap_font on-device and for tools/render.py on the desktop.
"""
import sys

PRESETS = {
    "ascii": [(0x20, 0x7E)],
    "latin1": [(0x20, 0x7E), (0xA0, 0xFF)],
    "hiragana": [(0x3041, 0x3096)],
    "katakana": [(0x30A1, 0x30FA)],
    # kana: both syllabaries plus the marks/punctuation drills need —
    # combining/standalone dakuten (3099-309C), iteration marks (309D-309F),
    # katakana middle dot + long-vowel mark (30FB-30FF).
    "kana": [(0x3041, 0x309F), (0x30A0, 0x30FF)],
}


def parse_ranges(spec):
    out = []
    for part in spec.split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part in PRESETS:
            out.extend(PRESETS[part])
        elif "-" in part:
            lo, hi = part.split("-", 1)
            out.append((int(lo, 16), int(hi, 16)))
        else:
            cp = int(part, 16)
            out.append((cp, cp))
    if not out:
        raise SystemExit("no codepoints selected")
    return out


def wanted(cp, ranges):
    return any(lo <= cp <= hi for lo, hi in ranges)


def embolden(block):
    """Dilate a glyph block's bitmap 1px right and down, in place."""
    h = None
    bm = None
    for i, line in enumerate(block):
        if line.startswith("BBX"):
            try:
                h = int(line.split()[2])
            except (IndexError, ValueError):
                return
        elif line.startswith("BITMAP"):
            bm = i
            break
    if h is None or bm is None or bm + h >= len(block):
        return
    rows = block[bm + 1:bm + 1 + h]
    digits = len(rows[0].strip()) if rows else 0
    if not digits:
        return
    try:
        vals = [int(r.strip(), 16) for r in rows]
    except ValueError:
        return
    mask = (1 << (digits * 4)) - 1
    out = []
    prev = 0
    for v in vals:
        out.append((v | (v >> 1) | prev | (prev >> 1)) & mask)
        prev = v
    for k, v in enumerate(out):
        block[bm + 1 + k] = ("%0" + str(digits) + "X") % v


def subset(in_path, out_path, ranges, quiet=False, bold=False):
    header = []          # everything before CHARS
    blocks = []          # [(codepoint, [lines])]
    chars_seen = 0

    with open(in_path, "r", encoding="utf-8", errors="replace") as f:
        # --- header ---
        for line in f:
            if line.startswith("CHARS "):
                break
            header.append(line.rstrip("\n"))
        else:
            raise SystemExit("%s: no CHARS line - not a BDF?" % in_path)

        # --- glyph blocks ---
        cur = None
        cp = None
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("STARTCHAR"):
                cur = [line]
                cp = None
            elif line.startswith("ENDCHAR"):
                if cur is not None:
                    cur.append(line)
                    chars_seen += 1
                    if cp is not None and wanted(cp, ranges):
                        blocks.append((cp, cur))
                cur = None
            elif line.startswith("ENDFONT"):
                break
            elif cur is not None:
                cur.append(line)
                if line.startswith("ENCODING"):
                    try:
                        cp = int(line.split()[1])
                    except (IndexError, ValueError):
                        cp = None

    if not blocks:
        raise SystemExit("no glyphs matched the requested ranges")

    kept = set(cp for cp, _b in blocks)

    # DEFAULT_CHAR pointing at a dropped glyph confuses some loaders — drop it
    # and fix the property count.
    default_idx = None
    props_idx = None
    for i, line in enumerate(header):
        if line.startswith("STARTPROPERTIES"):
            props_idx = i
        elif line.startswith("DEFAULT_CHAR"):
            try:
                if int(line.split()[1]) not in kept:
                    default_idx = i
            except (IndexError, ValueError):
                pass
    if default_idx is not None:
        header.pop(default_idx)
        if props_idx is not None and props_idx < default_idx:
            n = int(header[props_idx].split()[1]) - 1
            header[props_idx] = "STARTPROPERTIES %d" % n

    blocks.sort(key=lambda b: b[0])
    if bold:
        for _cp, body in blocks:
            embolden(body)
    with open(out_path, "w", encoding="utf-8", newline="\n") as out:
        for line in header:
            out.write(line + "\n")
        out.write("CHARS %d\n" % len(blocks))
        for _cp, body in blocks:
            for line in body:
                out.write(line + "\n")
        out.write("ENDFONT\n")

    if not quiet:
        import os

        print("%s -> %s" % (in_path, out_path))
        print("  glyphs: %d kept of %d  (%.1f%%)"
              % (len(blocks), chars_seen, 100.0 * len(blocks) / max(chars_seen, 1)))
        print("  size:   %.1f MB -> %d KB"
              % (os.path.getsize(in_path) / 1048576.0,
                 round(os.path.getsize(out_path) / 1024.0)))
    return len(blocks)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    in_path, out_path = argv[0], argv[1]
    spec = "ascii,kana"
    quiet = False
    bold = False
    i = 2
    while i < len(argv):
        if argv[i] == "--ranges":
            spec = argv[i + 1]
            i += 2
        elif argv[i] == "--quiet":
            quiet = True
            i += 1
        elif argv[i] == "--bold":
            bold = True
            i += 1
        else:
            raise SystemExit("unknown option: %s" % argv[i])
    subset(in_path, out_path, parse_ranges(spec), quiet, bold)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
