"""Deterministic indexed BMP writers shared by Butano asset generators."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Sequence


RgbColor = tuple[int, int, int]


def write_4bpp_bmp(
    path: Path,
    width: int,
    height: int,
    pixels: Sequence[int] | bytes,
    palette: Sequence[RgbColor],
) -> None:
    """Write an uncompressed Windows 3.x 4bpp indexed BMP."""

    if len(pixels) != width * height:
        raise ValueError("pixel count does not match BMP dimensions")
    if any(pixel < 0 or pixel > 15 for pixel in pixels):
        raise ValueError("4bpp pixels must be palette indices 0..15")
    if len(palette) != 16:
        raise ValueError("4bpp BMP palette must contain exactly 16 colors")
    if any(
        channel < 0 or channel > 255
        for color in palette
        for channel in color
    ):
        raise ValueError("BMP palette channels must be in range 0..255")

    packed_width = (width + 1) // 2
    row_size = (packed_width + 3) & ~3
    image_size = row_size * height
    pixel_offset = 14 + 40 + len(palette) * 4
    file_size = pixel_offset + image_size

    output = bytearray()
    output.extend(
        struct.pack(
            "<2sIHHI",
            b"BM",
            file_size,
            0,
            0,
            pixel_offset,
        )
    )
    output.extend(
        struct.pack(
            "<IiiHHIIiiII",
            40,
            width,
            height,
            1,
            4,
            0,
            image_size,
            2835,
            2835,
            len(palette),
            len(palette),
        )
    )
    for red, green, blue in palette:
        output.extend(bytes((blue, green, red, 0)))

    for y in range(height - 1, -1, -1):
        row = bytearray()
        start = y * width
        for x in range(0, width, 2):
            high = pixels[start + x]
            low = pixels[start + x + 1] if x + 1 < width else 0
            row.append((high << 4) | low)
        row.extend(bytes(row_size - len(row)))
        output.extend(row)
    path.write_bytes(output)

