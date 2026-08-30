#!/usr/bin/env python3
"""Convert a BDF font to PCF, so the device stops scanning font files.

WHY THIS EXISTS: `adafruit_bitmap_font`'s BDF loader keeps no glyph index.
`load_glyphs()` does `file.seek(0)` and reads the whole .bdf line by line for
any code point it has not already cached, which cost this project 4.6 s of boot
and ~3.1 s per first-seen kana in the drill (see PLAN.md). The PCF loader in
the same library reads a small encoding table at init and then SEEKS straight
to each glyph, so nothing is ever scanned and RAM stays proportional to the
glyphs actually on screen.

No pure-Python BDF->PCF converter exists to install: the X.org `bdftopcf` is a
C program that is awkward on Windows, and the Adafruit one that would be the
obvious choice is not real. Hence this.

WHAT IT TARGETS: not the whole PCF spec, but exactly what
`adafruit_bitmap_font/pcf.py` reads, which is stricter than the spec in one
place -- it rejects any bitmap table whose format is not 0xE (4-byte row
padding, most-significant byte and bit first). Tables the reader never touches
are omitted: PROPERTIES, SWIDTHS, GLYPH_NAMES, INK_METRICS. PROPERTIES in
particular is skipped deliberately -- the library's own `_read_properties()`
subscripts a namedtuple and would raise if anything ever called it.

Every table's format word is stored little-endian; everything else inside a
table is big-endian, which is what the reader demands.

Usage:
  python bdf2pcf.py IN.bdf [OUT.pcf]      # convert one font
  python bdf2pcf.py --all                 # convert every .bdf in src/fonts/
  python bdf2pcf.py --verify OUT.pcf IN.bdf
Conversion always self-verifies; --verify re-checks an existing pair.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
FONTS = os.path.join(SRC, "fonts")
sys.path.insert(0, HERE)
sys.path.insert(0, SRC)

from render import BDFFont  # noqa: E402  the project's one BDF parser

PCF_METRICS = 1 << 2
PCF_BITMAPS = 1 << 3
PCF_BDF_ENCODINGS = 1 << 5
PCF_BDF_ACCELERATORS = 1 << 8

PCF_BYTE_MASK = 1 << 2          # set = most significant byte first
PCF_BIT_MASK = 1 << 3           # set = most significant bit first
PCF_COMPRESSED_METRICS = 0x100

BIG = PCF_BYTE_MASK | PCF_BIT_MASK              # 0xC, the common flags
FMT_METRICS = BIG | PCF_COMPRESSED_METRICS      # 5 bytes per glyph, biased
FMT_BITMAPS = BIG | 2                           # 0xE: rows padded to 4 bytes
FMT_ENCODINGS = BIG
FMT_ACCEL = BIG                                 # no separate ink bounds

NO_GLYPH = 0xFFFF


def align4(n):
    return (n + 3) & ~3


class Metric:
    """PCF per-glyph metrics, derived from the BDF's BBX and DWIDTH.

    The mapping has to be exact or every glyph shifts: the reader builds
    Glyph(width=rsb-lsb, height=ascent+descent, dx=lsb, dy=-descent,
    shift_x=character_width), and the BDF loader builds the same fields from
    BBX w/h/xoff/yoff and DWIDTH.
    """

    def __init__(self, g):
        self.lsb = g.dx
        self.rsb = g.dx + g.w
        self.width = g.shift_x
        self.ascent = g.h + g.dy
        self.descent = -g.dy

    def values(self):
        return (self.lsb, self.rsb, self.width, self.ascent, self.descent)

    def packed(self):
        """5 bytes, each biased by 0x80 -- the compressed-metrics encoding."""
        out = bytearray()
        for v in self.values():
            if not -128 <= v <= 127:
                raise ValueError("metric %d out of range for compressed "
                                 "metrics" % v)
            out.append(v + 0x80)
        return bytes(out)


def glyph_rows(g):
    """Glyph bitmap as PCF rows: 4-byte padded, MSB first, leftmost pixel in
    the top bit of byte 0. `rows` came out of the BDF as one int per row with
    ((w+7)//8)*8 significant bits, so this is a re-pad, not a re-pack."""
    stride = ((g.w + 31) // 32) * 4
    src_bits = ((g.w + 7) // 8) * 8
    out = bytearray()
    for r in range(g.h):
        bits = g.rows[r] if r < len(g.rows) else 0
        row = bytearray(stride)
        for c in range(g.w):
            if bits & (1 << (src_bits - 1 - c)):
                row[c // 8] |= 128 >> (c % 8)
        out += row
    return bytes(out)


def build(bdf):
    """Assemble the whole PCF file as bytes."""
    codes = sorted(bdf.glyphs)
    if not codes:
        raise SystemExit("no glyphs in that BDF")
    glyphs = [bdf.glyphs[c] for c in codes]
    metrics = [Metric(g) for g in glyphs]

    # ---- encoding table: a dense grid over the byte1/byte2 ranges ----------
    min_b1, max_b1 = min(c >> 8 for c in codes), max(c >> 8 for c in codes)
    min_b2, max_b2 = min(c & 0xFF for c in codes), max(c & 0xFF for c in codes)
    cols = max_b2 - min_b2 + 1
    grid = [NO_GLYPH] * ((max_b1 - min_b1 + 1) * cols)
    for idx, code in enumerate(codes):
        b1, b2 = code >> 8, code & 0xFF
        if min_b2 <= b2 <= max_b2:
            grid[(b1 - min_b1) * cols + (b2 - min_b2)] = idx
    unreachable = [c for c in codes if not min_b2 <= (c & 0xFF) <= max_b2]
    if unreachable:                     # cannot happen with a dense grid, but
        raise SystemExit("unreachable code points: %r" % unreachable[:8])

    enc = bytearray(struct.pack("<I", FMT_ENCODINGS))
    # default_char is -1 ("none"): the reader unpacks these as SIGNED shorts,
    # so 0xFFFF has to be written as -1 rather than as NO_GLYPH.
    enc += struct.pack(">hhhhh", min_b2, max_b2, min_b1, max_b1, -1)
    for v in grid:
        enc += struct.pack(">H", v)

    # ---- metrics table ----------------------------------------------------
    met = bytearray(struct.pack("<I", FMT_METRICS))
    met += struct.pack(">H", len(glyphs))
    for m in metrics:
        met += m.packed()

    # ---- bitmap table -----------------------------------------------------
    blobs = [glyph_rows(g) for g in glyphs]
    offsets, pos = [], 0
    for b in blobs:
        offsets.append(pos)
        pos += len(b)
    # sizes[i] is what the data WOULD occupy at padding 1<<i; the reader uses
    # sizes[format & 3] == sizes[2], which is the padding actually written.
    sizes = []
    for shift in range(4):
        pad = 1 << shift
        total = 0
        for g in glyphs:
            stride = ((g.w + pad * 8 - 1) // (pad * 8)) * pad
            total += stride * g.h
        sizes.append(total)
    sizes[2] = pos                      # the authoritative one

    bmp = bytearray(struct.pack("<I", FMT_BITMAPS))
    bmp += struct.pack(">I", len(glyphs))
    for off in offsets:
        bmp += struct.pack(">I", off)
    for sz in sizes:
        bmp += struct.pack(">I", sz)
    for b in blobs:
        bmp += b

    # ---- accelerator table ------------------------------------------------
    def bounds(pick):
        return [pick(m.lsb for m in metrics), pick(m.rsb for m in metrics),
                pick(m.width for m in metrics), pick(m.ascent for m in metrics),
                pick(m.descent for m in metrics)]

    lo, hi = bounds(min), bounds(max)
    widths = {m.width for m in metrics}
    acc = bytearray(struct.pack("<I", FMT_ACCEL))
    acc += struct.pack(
        ">BBBBBBBBIII",
        0,                          # no_overlap
        1 if len(widths) == 1 else 0,   # constant_metrics
        0,                          # terminal_font
        1 if len(widths) == 1 else 0,   # constant_width
        0,                          # ink_inside
        0,                          # ink_metrics: our metrics ARE ink bounds
        0,                          # draw_direction: left to right
        0,                          # padding
        bdf.ascent, bdf.descent,
        0,                          # max_overlap
    )
    acc += struct.pack(">5hH", lo[0], lo[1], lo[2], lo[3], lo[4], 0)
    acc += struct.pack(">5hH", hi[0], hi[1], hi[2], hi[3], hi[4], 0)

    # ---- header + table of contents ---------------------------------------
    tables = [(PCF_METRICS, FMT_METRICS, met),
              (PCF_BITMAPS, FMT_BITMAPS, bmp),
              (PCF_BDF_ENCODINGS, FMT_ENCODINGS, enc),
              (PCF_BDF_ACCELERATORS, FMT_ACCEL, acc)]
    head = bytearray(b"\x01fcp")
    head += struct.pack("<I", len(tables))
    offset = align4(len(head) + 16 * len(tables))
    toc, body = bytearray(), bytearray()
    for type_, fmt, data in tables:
        toc += struct.pack("<IIII", type_, fmt, len(data), offset + len(body))
        body += data
        body += b"\x00" * (align4(len(body)) - len(body))
    out = head + toc
    out += b"\x00" * (offset - len(out))
    return bytes(out + body), len(glyphs)


# --------------------------------------------------------------- verify --
class PCFFont:
    """Independent reader that replicates adafruit_bitmap_font/pcf.py exactly,
    including its pure-Python bitmap path. Reading our own output back with
    OUR writer's assumptions would prove nothing, so this follows the library
    line by line instead."""

    def __init__(self, path):
        self.f = open(path, "rb")
        self.f.seek(0)
        _magic, count = self._r("<4sI")
        self.tables = {}
        for _ in range(count):
            t, fmt, size, off = self._r("<IIII")
            self.tables[t] = (fmt, size, off)
        fmt = self.tables[PCF_BITMAPS][0]
        if fmt != 0xE:
            raise ValueError("reader rejects bitmap format 0x%X" % fmt)
        self._accel()
        self._encoding()
        self._bitmap_table()

    def _r(self, fmt):
        n = struct.calcsize(fmt)
        return struct.unpack(fmt, self.f.read(n))

    def _seek(self, table):
        self.f.seek(table[2])
        (fmt,) = self._r("<I")
        if fmt & PCF_BYTE_MASK == 0:
            raise ValueError("reader requires big endian")
        return fmt

    def _metrics(self, compressed):
        if compressed:
            v = [b - 0x80 for b in self._r("5B")]
        else:
            v = list(self._r(">5hH"))[:5]
        return v          # lsb, rsb, width, ascent, descent

    def _accel(self):
        t = self.tables.get(PCF_BDF_ACCELERATORS) or self.tables[2]
        fmt = self._seek(t)
        vals = self._r(">BBBBBBBBIII")
        self.ascent, self.descent = vals[8], vals[9]
        self.minbounds = self._metrics(False)
        self.maxbounds = self._metrics(False)
        if fmt & 0x100:
            self.minbounds = self._metrics(False)
            self.maxbounds = self._metrics(False)

    def _encoding(self):
        self._seek(self.tables[PCF_BDF_ENCODINGS])
        (self.min_b2, self.max_b2, self.min_b1,
         self.max_b1, self.default) = self._r(">hhhhh")

    def _bitmap_table(self):
        fmt = self._seek(self.tables[PCF_BITMAPS])
        (self.glyph_count,) = self._r(">I")
        self.f.seek(self.tables[PCF_BITMAPS][2] + 8 + 4 * self.glyph_count)
        self.bitmap_size = self._r(">4I")[fmt & 3]

    def index_of(self, code):
        b1, b2 = (code >> 8) & 0xFF, code & 0xFF
        if not self.min_b1 <= b1 <= self.max_b1:
            return None
        if not self.min_b2 <= b2 <= self.max_b2:
            return None
        i = (b1 - self.min_b1) * (self.max_b2 - self.min_b2 + 1) + b2 - self.min_b2
        self.f.seek(self.tables[PCF_BDF_ENCODINGS][2] + 14 + 2 * i)
        (idx,) = self._r(">H")
        return None if idx == NO_GLYPH else idx

    def glyph(self, code):
        """(width, height, dx, dy, shift_x, [row bitmasks]) or None."""
        idx = self.index_of(code)
        if idx is None:
            return None
        mfmt = self.tables[PCF_METRICS][0]
        compressed = mfmt & PCF_COMPRESSED_METRICS
        self.f.seek(self.tables[PCF_METRICS][2] + (6 if compressed else 8)
                    + (5 if compressed else 12) * idx)
        lsb, rsb, width, ascent, descent = self._metrics(compressed)
        self.f.seek(self.tables[PCF_BITMAPS][2] + 8 + 4 * idx)
        (boff,) = self._r(">I")
        first = self.tables[PCF_BITMAPS][2] + 4 * (6 + self.glyph_count)
        w, h = rsb - lsb, ascent + descent
        self.f.seek(first + boff)
        rows = []
        stride = 4 * ((w + 31) // 32)
        for _ in range(h):
            buf = self.f.read(stride)
            bits = 0
            for k in range(w):
                if buf[k // 8] & (128 >> (k % 8)):
                    bits |= 1 << (w - 1 - k)
                                    # normalised: bit (w-1) is the leftmost
            rows.append(bits)
        return (w, h, lsb, -descent, width, rows)


def verify(pcf_path, bdf_path):
    """Compare every glyph, metric and the font-wide ascent/descent."""
    bdf = BDFFont(bdf_path)
    pcf = PCFFont(pcf_path)
    problems = []
    if (pcf.ascent, pcf.descent) != (bdf.ascent, bdf.descent):
        problems.append("font ascent/descent %s != BDF %s"
                        % ((pcf.ascent, pcf.descent), (bdf.ascent, bdf.descent)))
    for code in sorted(bdf.glyphs):
        g = bdf.glyphs[code]
        got = pcf.glyph(code)
        if got is None:
            problems.append("U+%04X missing from the PCF" % code)
            continue
        w, h, dx, dy, shift, rows = got
        if (w, h, dx, dy, shift) != (g.w, g.h, g.dx, g.dy, g.shift_x):
            problems.append("U+%04X metrics %s != BDF %s"
                            % (code, (w, h, dx, dy, shift),
                               (g.w, g.h, g.dx, g.dy, g.shift_x)))
            continue
        src_bits = ((g.w + 7) // 8) * 8
        for r in range(g.h):
            want = 0
            bits = g.rows[r] if r < len(g.rows) else 0
            for c in range(g.w):
                if bits & (1 << (src_bits - 1 - c)):
                    want |= 1 << (g.w - 1 - c)
            if rows[r] != want:
                problems.append("U+%04X row %d differs" % (code, r))
                break
        if len(problems) > 20:
            problems.append("... stopping after 20")
            break
    return problems


def convert(bdf_path, out_path=None):
    if out_path is None:
        out_path = os.path.splitext(bdf_path)[0] + ".pcf"
    bdf = BDFFont(bdf_path)
    data, n = build(bdf)
    with open(out_path, "wb") as f:
        f.write(data)
    problems = verify(out_path, bdf_path)
    src_kb = os.path.getsize(bdf_path) / 1024.0
    out_kb = len(data) / 1024.0
    print("%-28s %5d glyphs  %6.1f KB bdf -> %6.1f KB pcf  (%+.0f%%)"
          % (os.path.basename(out_path), n, src_kb, out_kb,
             100.0 * (out_kb - src_kb) / src_kb))
    for p in problems:
        print("   [FAIL] %s" % p)
    if not problems:
        print("   [ok]   every glyph round-trips")
    return not problems


def main(argv):
    if "--verify" in argv:
        rest = [a for a in argv if a != "--verify"]
        problems = verify(rest[0], rest[1])
        for p in problems:
            print("  [FAIL] %s" % p)
        print("verify: %s" % ("PASSED" if not problems else "FAILED"))
        return 1 if problems else 0
    if "--all" in argv:
        # Only the fonts a ROLE points at. ter-u14b/ter-u16b are subset sources
        # that nothing loads, and converting them would ship 400 KB of PCF to
        # the device for nothing.
        from kanatype import layout
        ok = True
        for name in sorted({os.path.basename(v)
                            for v in layout.FONT_PATHS.values()}):
            bdf = os.path.join(FONTS, os.path.splitext(name)[0] + ".bdf")
            if not os.path.exists(bdf):
                print("[FAIL] %s has no .bdf source" % name)
                ok = False
                continue
            ok &= convert(bdf)
        return 0 if ok else 1
    if not argv:
        raise SystemExit(__doc__)
    return 0 if convert(argv[0], argv[1] if len(argv) > 1 else None) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
