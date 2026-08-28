#!/usr/bin/env python3
"""Compose the boot splash: artwork + BAKED-IN text -> 1-bit BMP.

The launcher paints this bitmap before any font is loaded (OnDiskBitmap streams
from flash with no parsing), so the text has to be part of the image rather
than drawn with labels — otherwise the splash would appear wordless until the
font parse finished, which is exactly the delay it exists to cover.

Inputs / outputs
  mockups/loading_art.txt     art only, no text  (archival source - edit this)
  mockups/loading_splash.txt  art + text         (generated, for render.py)
  src/assets/loading.bmp      art + text         (generated, what ships)

Text, position and font all come from kanatype/layout.py so the baked result
matches what label.Label would have drawn.

Usage:  python Firmware/tools/make_splash.py [--text "Loading..."]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
MOCKUPS = os.path.abspath(os.path.join(HERE, "..", "mockups"))
sys.path.insert(0, HERE)
sys.path.insert(0, SRC)

import mockup
import render
from kanatype import layout

ART = os.path.join(MOCKUPS, "loading_art.txt")
OUT_TXT = os.path.join(MOCKUPS, "loading_splash.txt")
OUT_BMP = os.path.join(SRC, "assets", "loading.bmp")


def main(argv):
    text = "Loading..."
    if len(argv) >= 2 and argv[0] == "--text":
        text = argv[1]

    if not os.path.exists(ART):
        raise SystemExit("missing %s (the art-only source)" % ART)
    grid = mockup.read_txt(ART)
    if len(grid) != layout.HEIGHT or len(grid[0]) != layout.WIDTH:
        raise SystemExit("art is %dx%d, panel is %dx%d"
                         % (len(grid[0]), len(grid), layout.WIDTH, layout.HEIGHT))

    # same font, positions and black knockout boxes ui.loading() used
    f = render.BDFFont(render.font_path("jp"))
    render.draw_label_bg(grid, f, layout.MENU_TITLE_X, layout.MENU_TITLE_Y,
                         layout.TITLE)
    render.draw_label_bg(grid, f, layout.LOADING_TEXT_X, layout.LOADING_TEXT_Y,
                         text)

    mockup.write_txt(grid, OUT_TXT)
    mockup.write_bmp(grid, OUT_BMP)
    lit = sum(row.count("#") for row in grid)
    print("baked %r + %r into the splash" % (layout.TITLE, text))
    print("  %s" % OUT_TXT)
    print("  %s  (%d lit px, %d bytes)"
          % (OUT_BMP, lit, os.path.getsize(OUT_BMP)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
