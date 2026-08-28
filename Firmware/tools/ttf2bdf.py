#!/usr/bin/env python3
"""Rasterize a TrueType/OpenType font into a 1-bit BDF at any pixel size.

Classic Japanese bitmap fonts stop at 24px (jiskan24, shinonome) because
beyond that the world moved to outlines — so a "native 48px bitmap font"
doesn't exist to download. It has to be generated, which is what this does:
FreeType renders each glyph in MONOCHROME mode (hinted, no antialiasing to
threshold away), and the result is emitted as a proper BDF.

Rasterizing at the final size and using scale=1 keeps full detail; scaling a
16px source x3 only ever shows 16px of detail in 48px of space.

Requires Pillow.

Usage:
  python ttf2bdf.py FONT.ttf OUT.bdf --size 48 [--ranges SPEC] [--index N]

--ranges takes the same presets/hex ranges as subset_font.py (default
ascii,kana), so only the glyphs you need are rasterized — no subsetting pass
needed afterwards.
--index picks a face inside a .ttc collection (Windows CJK fonts are .ttc).

NOTE ON LICENSING: system fonts (Meiryo, MS Gothic, Yu Gothic...) are fine to
generate for your own device but are NOT redistributable — don't commit their
output. Use a free font (Noto Sans JP, M PLUS, IPAex) for anything shared.
"""
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else ".")
from subset_font import parse_ranges  # shared preset/range parsing


def render_glyph(font, ch, cell_h, ascent, pad=8):
    """Monochrome-render one char; return (advance, bitmap rows as bool grid,
    ink bbox x0,y0,x1,y1 in image coords with baseline at y=ascent)."""
    try:
        advance = int(round(font.getlength(ch)))
    except AttributeError:  # very old Pillow
        advance = font.getsize(ch)[0]
    img = Image.new("1", (advance + 2 * pad, cell_h + 2 * pad), 0)
    d = ImageDraw.Draw(img)
    # mode "1" image => FreeType monochrome rendering (no antialiasing)
    d.text((pad, pad), ch, font=font, fill=1)
    px = img.load()
    xs, ys = [], []
    for y in range(img.height):
        for x in range(img.width):
            if px[x, y]:
                xs.append(x)
                ys.append(y)
    if not xs:
        return advance, None, None
    return advance, px, (min(xs), min(ys), max(xs), max(ys))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    in_path, out_path = argv[0], argv[1]
    size = 48
    spec = "ascii,kana"
    index = 0
    i = 2
    while i < len(argv):
        if argv[i] == "--size":
            size = int(argv[i + 1]); i += 2
        elif argv[i] == "--ranges":
            spec = argv[i + 1]; i += 2
        elif argv[i] == "--index":
            index = int(argv[i + 1]); i += 2
        else:
            raise SystemExit("unknown option: %s" % argv[i])

    ranges = parse_ranges(spec)
    font = ImageFont.truetype(in_path, size=size, index=index)
    ascent, descent = font.getmetrics()
    cell_h = ascent + descent
    PAD = 8

    glyphs = []  # (cp, advance, bbx, rows)
    for lo, hi in ranges:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            advance, px, ink = render_glyph(font, ch, cell_h, ascent, PAD)
            if px is None:  # blank (space): 1x1 empty cell keeps parsers happy
                glyphs.append((cp, advance, (1, 1, 0, 0), ["00"]))
                continue
            x0, y0, x1, y1 = ink
            w, h = x1 - x0 + 1, y1 - y0 + 1
            digits = ((w + 7) // 8) * 2
            rows = []
            for y in range(y0, y1 + 1):
                v = 0
                for k in range(w):
                    if px[x0 + k, y]:
                        v |= 1 << (digits * 4 - 1 - k)
                rows.append(("%0" + str(digits) + "X") % v)
            # BDF: dx from origin, dy from baseline to bbox bottom (up = +)
            dx = x0 - PAD
            dy = (ascent + PAD) - (y1 + 1)
            glyphs.append((cp, advance, (w, h, dx, dy), rows))

    # TTF ascent/descent include LINE SPACING — at 48px Meiryo reports a 73px
    # cell, taller than the whole panel, which would wreck label placement.
    # Declare metrics from the actual ink instead, so the BDF cell hugs the
    # glyphs and layout constants stay predictable.
    ink_ascent = max((dy + h) for _cp, _a, (w, h, dx, dy), _r in glyphs)
    ink_descent = max((-dy) for _cp, _a, (w, h, dx, dy), _r in glyphs)
    ink_descent = max(ink_descent, 0)
    ascent, descent = ink_ascent, ink_descent
    cell_h = ascent + descent
    maxw = max(g[1] for g in glyphs)
    name = in_path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    with open(out_path, "w", encoding="utf-8", newline="\n") as o:
        o.write("STARTFONT 2.1\n")
        o.write("FONT -ttf2bdf-%s-Medium-R-Normal--%d-%d-75-75-c-%d-iso10646-1\n"
                % (name, cell_h, size * 10, maxw * 10))
        o.write("SIZE %d 75 75\n" % size)
        o.write("FONTBOUNDINGBOX %d %d 0 %d\n" % (maxw, cell_h, -descent))
        o.write("STARTPROPERTIES 4\n")
        o.write('FAMILY_NAME "%s"\n' % name)
        o.write("FONT_ASCENT %d\n" % ascent)
        o.write("FONT_DESCENT %d\n" % descent)
        o.write('SOURCE "rasterized from %s at %dpx by tools/ttf2bdf.py"\n'
                % (name, size))
        o.write("ENDPROPERTIES\n")
        o.write("CHARS %d\n" % len(glyphs))
        for cp, advance, (w, h, dx, dy), rows in glyphs:
            o.write("STARTCHAR U+%04X\n" % cp)
            o.write("ENCODING %d\n" % cp)
            o.write("SWIDTH %d 0\n" % int(round(advance * 1000.0 / size)))
            o.write("DWIDTH %d 0\n" % advance)
            o.write("BBX %d %d %d %d\n" % (w, h, dx, dy))
            o.write("BITMAP\n")
            for r in rows:
                o.write(r + "\n")
            o.write("ENDCHAR\n")
        o.write("ENDFONT\n")

    import os

    print("%s (%dpx, face %d) -> %s" % (name, size, index, out_path))
    print("  glyphs: %d   cell: %dx%d (tight ascent %d, descent %d)"
          % (len(glyphs), maxw, cell_h, ascent, descent))
    kana = [g for g in glyphs if 0x3041 <= g[0] <= 0x30FF]
    if kana:
        print("  kana ink: max %dw x %dh   advance %d"
              % (max(g[2][0] for g in kana), max(g[2][1] for g in kana),
                 max(g[1] for g in kana)))
    print("  size:   %d KB" % round(os.path.getsize(out_path) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
