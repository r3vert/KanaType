"""Tiny 1-bit icons, shared by the firmware UI and tools/render.py.

PURE PYTHON (no displayio import) so the desktop renderer blits the very same
pixels the panel shows — same rule as layout.py.

'#' = lit pixel, anything else = off. Edit the art here and both worlds follow.
Sizes are read from the art itself, so redrawing at a different size is safe.
"""

# Lightning bolt: USB / external power. Upper wedge descends left, a bar jogs
# right, then the lower wedge descends left again to a point.
BOLT = (
    "...###",
    "..###.",
    ".###..",
    "######",
    "..###.",
    ".###..",
    "###...",
    "##....",
)

# Tilde: power source not determined yet (USB enumeration still pending).
TILDE = (
    ".###......",
    "#####...##",
    "#...######",
    ".....###..",
)

# Battery: outline + terminal nub on the right + a charge block.
# There is no fuel gauge on this board (VBAT isn't wired to a free ADC), so the
# block is decorative — the icon means "running on battery", not a level.
BATTERY = (
    "##########..",
    "#........#..",
    "#.######.###",
    "#.######.###",
    "#.######.###",
    "#........#..",
    "##########..",
)


def size(art):
    """(width, height) of an icon."""
    return (max(len(row) for row in art), len(art))
