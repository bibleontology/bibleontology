"""The home-screen icon, drawn rather than stored.

2026-08-29: wanted, the ability to associate an icon on an iPhone so the site
feels like an app.

An icon is a binary, and a binary checked into a repository is a thing nobody
can change six months later without the tool that made it. So it is generated:
the source of truth is this file, and the PNGs are output.

## Why it is written by hand

There is no imaging library here and adding one for four small squares would
be a dependency the rest of the project has no use for. A PNG is a zlib stream
of filtered scanlines wrapped in four chunks, which is about thirty lines, and
the drawing is coverage-sampled circles and lines. Nothing here is clever; it
is only unfamiliar.

## The mark

Three points joined by two lines: the smallest thing that is recognisably a
graph rather than a diagram of one. It reads at 60 pixels, which is the only
size that actually matters -- an icon is never seen larger than a fingertip.

It is also, not by accident, the shape of Job 9:9. The verse names Arcturus,
Orion and Pleiades, and it was the verse that exposed how the extractor was
typing stars -- calling them ideas rather than things. Three points of light
in the one book that argues hardest with the dark.

    python -m bibleont.icon
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

from .paths import ROOT

OUT = ROOT / "app2" / "static"

# Warm rather than clinical. This sits between a photo of a grandchild and a
# weather app, not in a toolbar.
INK = (0x14, 0x18, 0x22)          # deep blue-black, the ground
GLOW = (0xF2, 0xC9, 0x7A)         # warm gold, the points
LINE = (0x6E, 0x74, 0x90)         # muted slate, the joins

# In a 0..1 square. Unequal on purpose: three points at even spacing read as a
# decoration, and slightly irregular reads as a constellation.
#
# Centred on the mark's own bounding box including the point radii, not on the
# points' average -- the first version balanced the centres and sat visibly
# high, because the lowest point contributes its whole radius downward and the
# average does not know that.
POINTS = [(0.30, 0.405), (0.62, 0.305), (0.72, 0.695)]
EDGES = [(0, 1), (1, 2)]

R_POINT = 0.075
R_LINE = 0.021
SS = 4                             # samples per pixel per axis


def _dist_to_segment(px: float, py: float, ax: float, ay: float,
                     bx: float, by: float) -> float:
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    t = 0.0 if denom == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    dx, dy = px - (ax + t * vx), py - (ay + t * vy)
    return (dx * dx + dy * dy) ** 0.5


def _shade(x: float, y: float) -> tuple[int, int, int]:
    """Colour at one sample. Points sit above lines; both above the ground."""
    for cx, cy in POINTS:
        if ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 <= R_POINT:
            return GLOW
    for i, j in EDGES:
        ax, ay = POINTS[i]
        bx, by = POINTS[j]
        if _dist_to_segment(x, y, ax, ay, bx, by) <= R_LINE:
            return LINE
    return INK


def render(size: int) -> bytes:
    """Raw RGB rows, supersampled so the curves are not stepped.

    No transparency and no rounded corners: iOS applies its own mask, and a
    square with corners pre-rounded gets rounded twice and looks gnawed.
    """
    rows = []
    inv = 1.0 / (size * SS)
    for py in range(size):
        row = bytearray()
        for px in range(size):
            r = g = b = 0
            for sy in range(SS):
                y = (py * SS + sy + 0.5) * inv
                for sx in range(SS):
                    x = (px * SS + sx + 0.5) * inv
                    c = _shade(x, y)
                    r += c[0]
                    g += c[1]
                    b += c[2]
            n = SS * SS
            row += bytes((r // n, g // n, b // n))
        rows.append(bytes(row))
    return b"".join(rows)


def png(size: int) -> bytes:
    """Minimal PNG: signature, IHDR, IDAT, IEND.

    Each scanline is prefixed with filter type 0 ("none"). Real encoders pick
    a filter per line to compress better; at this size the difference is a few
    hundred bytes and the clarity is worth more.
    """
    raw = render(size)
    stride = size * 3
    lines = b"".join(b"\x00" + raw[i:i + stride]
                     for i in range(0, len(raw), stride))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit truecolour
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(lines, 9))
            + chunk(b"IEND", b""))


# 180 is what iOS asks for by name; 192 and 512 are what a web manifest wants,
# and 512 is what an installer scales down from.
SIZES = (180, 192, 512)


def main(argv: list[str] | None = None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        data = png(size)
        name = "apple-touch-icon.png" if size == 180 else f"icon-{size}.png"
        (OUT / name).write_bytes(data)
        print(f"  {name:24} {size}x{size}  {len(data) / 1024:5.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
