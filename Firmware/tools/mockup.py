#!/usr/bin/env python3
"""KanaType mockup round-trip tool (desktop Python, stdlib only).

Formats:
  .txt  ASCII grid: '#' = lit pixel, '.' = dark (one row per line) - pixel-exact,
        readable by humans AND by Claude deterministically.
  .pbm  Portable bitmap P1 (plain text) - exportable from GIMP/ImageMagick.
  .png  Output only, nearest-neighbor scaled (default x4) for easy viewing.

Usage:
  python mockup.py demo <out_dir>              # generate the sample menu screen
  python mockup.py convert <in> <out> [scale]  # by extension: txt/pbm -> txt/pbm/png
  python mockup.py new <out.txt> [W H]         # blank 128x64 grid to draw in

A 5x7 pixel font (ASCII subset) is included so mockups can carry legible text.
"""
import sys
import struct
import zlib

WIDTH, HEIGHT = 128, 64

# ---------------------------------------------------------------- 5x7 font --
_F = {
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110",
    "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01110",
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "11111 00100 00100 00100 00100 00100 11111",
    "J": "00111 00010 00010 00010 10010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 11011 10001",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100",
    "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 11111",
    "2": "01110 10001 00001 00110 01000 10000 11111",
    "3": "01110 10001 00001 00110 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "01110 10000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00001 01110",
    ">": "10000 01000 00100 00010 00100 01000 10000",
    "(": "00100 01000 10000 10000 10000 01000 00100",
    ")": "00100 00010 00001 00001 00001 00010 00100",
    "/": "00001 00001 00010 00100 01000 10000 10000",
    "-": "00000 00000 00000 11111 00000 00000 00000",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    ":": "00000 01100 01100 00000 01100 01100 00000",
    "?": "01110 10001 00001 00110 00100 00000 00100",
    " ": "00000 00000 00000 00000 00000 00000 00000",
}
FONT = {ch: rows.split() for ch, rows in _F.items()}

# ---------------------------------------------------------------- grid ops --


def new_grid(w=WIDTH, h=HEIGHT):
    return [["." for _ in range(w)] for _ in range(h)]


def set_px(grid, x, y, on=True):
    if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
        grid[y][x] = "#" if on else "."


def fill_rect(grid, x, y, w, h, on=True):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            set_px(grid, xx, yy, on)


def text(grid, x, y, s, on=True):
    """Render 5x7 text (uppercased; unknown chars become spaces)."""
    cx = x
    for ch in s.upper():
        glyph = FONT.get(ch, FONT[" "])
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    set_px(grid, cx + gx, y + gy, on)
        cx += 6  # 5 px glyph + 1 px spacing
    return cx


# ------------------------------------------------------------------ txt io --


def read_txt(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line and set(line) <= {"#", "."}:
                rows.append(list(line))
    if not rows:
        raise SystemExit("no grid rows ('#'/'.') found in %s" % path)
    w = max(len(r) for r in rows)
    return [r + ["."] * (w - len(r)) for r in rows]


def write_txt(grid, path):
    with open(path, "w") as f:
        f.write("\n".join("".join(row) for row in grid) + "\n")


# ------------------------------------------------------------------ pbm io --


def read_pbm(path):
    with open(path) as f:
        tokens = []
        for line in f:
            line = line.split("#", 1)[0]
            tokens += line.split()
    if tokens[0] != "P1":
        raise SystemExit("only plain-text PBM (P1) supported; GIMP: export as .pbm ASCII")
    w, h = int(tokens[1]), int(tokens[2])
    bits = "".join(tokens[3:])
    grid = new_grid(w, h)
    for i, b in enumerate(bits[: w * h]):
        grid[i // w][i % w] = "#" if b == "1" else "."  # PBM: 1 = black ink = lit OLED px
    return grid


def write_pbm(grid, path):
    h, w = len(grid), len(grid[0])
    with open(path, "w") as f:
        f.write("P1\n# KanaType mockup %dx%d\n%d %d\n" % (w, h, w, h))
        for row in grid:
            f.write(" ".join("1" if c == "#" else "0" for c in row) + "\n")


# ------------------------------------------------------------------ bmp io --


def write_bmp(grid, path):
    """1-bit indexed BMP — the format displayio.OnDiskBitmap loads on-device."""
    h, w = len(grid), len(grid[0])
    row_bytes = ((w + 31) // 32) * 4  # rows padded to 4 bytes
    pixel_bytes = row_bytes * h
    offset = 14 + 40 + 8  # file header + DIB + 2-color palette
    with open(path, "wb") as f:
        f.write(b"BM" + struct.pack("<IHHI", offset + pixel_bytes, 0, 0, offset))
        f.write(struct.pack("<IiiHHIIiiII", 40, w, h, 1, 1, 0, pixel_bytes, 2835, 2835, 2, 0))
        f.write(bytes([0, 0, 0, 0, 255, 255, 255, 0]))  # palette: 0=black, 1=white
        for row in reversed(grid):  # BMP rows are bottom-up
            out = bytearray(row_bytes)
            for x, c in enumerate(row):
                if c == "#":
                    out[x // 8] |= 0x80 >> (x % 8)
            f.write(out)


def read_bmp_size(path):
    with open(path, "rb") as f:
        f.seek(18)
        w, h = struct.unpack("<ii", f.read(8))
    return w, abs(h)


# ------------------------------------------------------------------ png io --


def write_png(grid, path, scale=4):
    """Minimal grayscale PNG writer (stdlib only), nearest-neighbor scaled."""
    h, w = len(grid), len(grid[0])
    raw = b""
    for row in grid:
        line = b"\x00" + bytes(
            255 if c == "#" else 0 for c in row for _ in range(scale)
        )
        raw += line * scale

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# -------------------------------------------------------------------- demo --


def demo_menu():
    """The launcher menu screen, as the firmware should render it."""
    g = new_grid()
    fill_rect(g, 0, 0, WIDTH, 9)                     # title bar
    text(g, 2, 1, "KANATYPE", on=False)              # carved into the bar
    text(g, 98, 1, "USB", on=False)
    text(g, 2, 13, "> KEYBOARD")
    text(g, 2, 24, "  PRACTICE")
    text(g, 2, 35, "  QUICK NOTE")
    text(g, 2, 46, "  VAULT")
    fill_rect(g, 0, 55, WIDTH, 1)                    # footer separator
    text(g, 2, 57, "AUTO: KEYBOARD 2")
    return g


# --------------------------------------------------------------------- cli --


def _load(path):
    if path.endswith(".txt"):
        return read_txt(path)
    if path.endswith(".pbm"):
        return read_pbm(path)
    raise SystemExit("can read .txt or .pbm (for .png: view it, or re-export as .pbm)")


def _save(grid, path, scale=4):
    if path.endswith(".txt"):
        write_txt(grid, path)
    elif path.endswith(".pbm"):
        write_pbm(grid, path)
    elif path.endswith(".png"):
        write_png(grid, path, scale)
    elif path.endswith(".bmp"):
        write_bmp(grid, path)
    else:
        raise SystemExit("can write .txt, .pbm, .png or .bmp")


def main(argv):
    if len(argv) >= 2 and argv[0] == "demo":
        import os

        out = argv[1]
        os.makedirs(out, exist_ok=True)
        g = demo_menu()
        write_txt(g, os.path.join(out, "menu.txt"))
        write_pbm(g, os.path.join(out, "menu.pbm"))
        write_png(g, os.path.join(out, "menu_x4.png"), 4)
        print("wrote menu.txt / menu.pbm / menu_x4.png to", out)
    elif len(argv) >= 3 and argv[0] == "convert":
        scale = int(argv[3]) if len(argv) > 3 else 4
        _save(_load(argv[1]), argv[2], scale)
        print("converted", argv[1], "->", argv[2])
    elif len(argv) >= 2 and argv[0] == "new":
        w = int(argv[2]) if len(argv) > 2 else WIDTH
        h = int(argv[3]) if len(argv) > 3 else HEIGHT
        write_txt(new_grid(w, h), argv[1])
        print("blank %dx%d grid -> %s" % (w, h, argv[1]))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
