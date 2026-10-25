"""Pixel maths for the judgment bench.

Everything here is a pure function of two frames, so the bench's numbers can
be re-derived by hand from the captured PNGs.

The pixel semantics are the ones the repository already uses
(``tools/compare_frame_dirs.py`` and ``tools/align_frame_dirs.py``): a pixel
counts as different when any of its three channels differ.
"""

from __future__ import annotations

import hashlib
import statistics

from PIL import Image, ImageChops

from .paths import BLOCK, STRUCT_TOLERANCE


def load_rgb(path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def pixel_digest(image: Image.Image) -> str:
    """The sha256 of the decoded pixels, so PNG metadata cannot fool it."""
    return hashlib.sha256(image.tobytes()).hexdigest()


def diff_mask(left: Image.Image, right: Image.Image, box: tuple[int, int, int, int]):
    """(differing pixel count, per-pixel max-channel-difference image)."""
    delta = ImageChops.difference(left.crop(box), right.crop(box))
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return sum(mask.histogram()[1:]), mask


def block_means(image: Image.Image, box: tuple[int, int, int, int],
                size: int = BLOCK) -> list[list[tuple[int, int, int]]]:
    x0, y0, width, height = box
    rows = []
    for r in range(height // size):
        row = []
        for c in range(width // size):
            cell = image.crop((x0 + c * size, y0 + r * size,
                               x0 + (c + 1) * size, y0 + (r + 1) * size))
            row.append(cell.resize((1, 1), Image.BOX).getpixel((0, 0)))
        rows.append(row)
    return rows


def structure_match(left_blocks, right_blocks, tolerance: int) -> float:
    same = total = 0
    for left_row, right_row in zip(left_blocks, right_blocks):
        for a, b in zip(left_row, right_row):
            total += 1
            if max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])) <= tolerance:
                same += 1
    return same / total


def block_occupancy(mask: Image.Image, size: int = BLOCK) -> float:
    width, height = mask.size
    occupied = blocks = 0
    for r in range(0, height, size):
        for c in range(0, width, size):
            blocks += 1
            if mask.crop((c, r, min(c + size, width), min(r + size, height))).getbbox():
                occupied += 1
    return occupied / blocks


def row_spread(mask: Image.Image) -> float:
    width, height = mask.size
    rows = 0
    for r in range(height):
        if mask.crop((0, r, width, r + 1)).getbbox():
            rows += 1
    return rows / height


def screen_stats(image: Image.Image) -> dict:
    """The machine readable brightness facts of one frame.

    ``non_black_fraction`` is the share of pixels that are not exactly
    ``(0, 0, 0)``; it is what separates a fade frame from a battle frame.
    """
    pixels = list(image.getdata())
    total = len(pixels)
    non_black = sum(1 for pixel in pixels if pixel != (0, 0, 0))
    mean = [round(sum(pixel[channel] for pixel in pixels) / total, 3)
            for channel in range(3)]
    return {
        "non_black_fraction": round(non_black / total, 6),
        "mean_rgb": mean,
        "unique_colours": len(set(pixels)),
    }


def to_five_bit_green(green: int) -> int | None:
    """The ROM's 5 bit green of an 8 bit green, or None when it is not one."""
    for value in range(1, 32, 2):
        if (value << 3) | (value >> 2) == green:
            return value
    return None


def outline_shades(image: Image.Image, region) -> list[int]:
    """The 5 bit shades of the unit's one pixel outline in one frame.

    The outline is the only colour of the shape ``(0, g, g)`` in the unit's
    own pixel region, so the shades can be read straight out of the frame.
    """
    crop = image.crop(region)
    shades = set()
    for pixel in crop.getdata():
        if pixel[0] == 0 and pixel[1] == pixel[2] and pixel[1] > 0:
            five_bit = to_five_bit_green(pixel[1])
            if five_bit is not None:
                shades.add(five_bit)
    return sorted(shades)


def stats(values: list[int]) -> dict:
    if not values:
        return {}
    median = statistics.median(values)
    return {
        "min": min(values),
        "median": int(median) if float(median).is_integer() else median,
        "max": max(values),
        "sum": sum(values),
        "mean": round(sum(values) / len(values), 2),
        "zero_frames": sum(1 for value in values if value == 0),
        "frames": len(values),
    }
