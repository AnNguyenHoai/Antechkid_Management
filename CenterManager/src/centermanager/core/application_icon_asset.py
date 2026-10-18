# -*- coding: utf-8 -*-
"""Canonical AnTechKids application icon artwork.

This module deliberately has no Qt/Pillow dependency so the same pixels can be
used by both the runtime Qt icon and the Windows executable ICO generator.
"""
from __future__ import annotations


APPLICATION_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

_BLUE = (21, 101, 192, 255)
_ORANGE = (245, 124, 0, 255)
_WHITE = (255, 255, 255, 255)

_GLYPHS = {
    "A": (
        "01110",
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
        "10001",
    ),
    "K": (
        "10001",
        "10010",
        "10100",
        "11000",
        "10100",
        "10010",
        "10001",
    ),
}


def render_application_icon_rgba(size: int) -> bytes:
    """Render the canonical square icon as top-down RGBA bytes."""
    size = max(16, int(size))
    pixels = [[_BLUE for _ in range(size)] for _ in range(size)]

    accent_height = max(4, round(size * 0.24))
    for y in range(size - accent_height, size):
        for x in range(size):
            pixels[y][x] = _ORANGE

    # Keep the block glyph proportional at every Windows shell icon size.
    scale = max(1, size // 20)
    glyph_width = 5 * scale
    gap = max(1, scale)
    total_width = glyph_width * 2 + gap
    start_x = max(0, (size - total_width) // 2)
    available_height = max(7, size - accent_height)
    glyph_height = 7 * scale
    start_y = max(0, (available_height - glyph_height) // 2)

    for index, letter in enumerate(("A", "K")):
        origin_x = start_x + index * (glyph_width + gap)
        for gy, row in enumerate(_GLYPHS[letter]):
            for gx, bit in enumerate(row):
                if bit != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        x = origin_x + gx * scale + dx
                        y = start_y + gy * scale + dy
                        if 0 <= x < size and 0 <= y < size - accent_height:
                            pixels[y][x] = _WHITE

    raw = bytearray()
    for row in pixels:
        for rgba in row:
            raw.extend(rgba)
    return bytes(raw)


__all__ = ["APPLICATION_ICON_SIZES", "render_application_icon_rgba"]
