#!/usr/bin/env python3
"""Build the reusable settlement plate and measure it.

The `scenario_41_result_*` layers are a capture of the *scenario 41* settlement
screen: they carry that battle's numbers, that battle's character sprite and
that battle's name label.  The remake has to draw its own numbers and its own
sprites, so the capture has to lose that dynamic content before it can be used
as a reusable plate.

This script:

1. composites the three capture layers the way the GBA does (index 0 is
   transparent, the topmost non-transparent pixel wins);
2. erases the dynamic regions (the number block and the character sprite row)
   with the row's own background colour;
3. writes the cleaned plate as one 8bpp layer;
4. measures the cleaned plate against the S49 truth with the same two metrics
   the wave-10 tool uses.

Usage::

    python tools/s49_w3_settlement/w3_build_result_plate.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

from PIL import Image, ImageChops

GRAPHICS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics")
TRUTH = pathlib.Path(
    r"D:\Github\gba-naruto\build\s49-victory-capture\w4\settlement-truth"
    r"\02-settlement-exp-power-turns.png")
OUT = pathlib.Path(r"D:\Github\gba-naruto\build\w3-probe")

#: The capture layers, bottom first.
CAPTURE_LAYERS = (
    "scenario_41_result_bottom.bmp",
    "scenario_41_result_middle.bmp",
    "scenario_41_result_top.bmp",
)

#: The dynamic regions of the capture: the number block and the character
#: sprite row.  The name labels are *not* erased: the capture's one name
#: (the first participant) is the same label the truth shows, so it stays.
DYNAMIC_REGIONS = (
    (80, 44, 230, 102),
    (88, 106, 236, 154),
)


#: The colour that marks a transparent pixel while the layers are composited.
#: It is not a colour the plate uses, so the palette can be rebuilt exactly.
TRANSPARENT_SENTINEL = (255, 0, 255)


def compose(layers: tuple[str, ...]) -> Image.Image:
    width = height = 256
    canvas = [TRANSPARENT_SENTINEL] * (width * height)
    for name in layers:
        with Image.open(GRAPHICS / name) as image:
            paletted = image.convert("P")
            indices = list(paletted.getdata())
            pixels = list(paletted.convert("RGB").getdata())
        for position, index in enumerate(indices):
            if index == 0:
                continue
            canvas[position] = pixels[position]
    composed = Image.new("RGB", (width, height))
    composed.putdata(canvas)
    return composed


def erase_dynamic(composed: Image.Image) -> Image.Image:
    """Replace the dynamic regions with the row's own background colour."""

    image = composed.copy()
    pixels = image.load()
    for left, top, right, bottom in DYNAMIC_REGIONS:
        for row in range(top, min(bottom, image.height)):
            colours = [
                pixels[column, row]
                for column in range(left, min(right, image.width))
            ]
            if not colours:
                continue
            background = max(
                set(colours), key=colours.count)
            for column in range(left, min(right, image.width)):
                pixels[column, row] = background
    return image


def compare(left: Image.Image, right: Image.Image):
    difference = ImageChops.difference(left, right)
    bands = difference.split()
    merged = ImageChops.lighter(
        ImageChops.lighter(bands[0], bands[1]), bands[2])
    box = merged.getbbox()
    if box is None:
        return 0, 0, None
    data = merged.crop(box).tobytes()
    v4_metric = 0
    for index in range(0, len(data) - 2, 3):
        if data[index] or data[index + 1] or data[index + 2]:
            v4_metric += 1
    true_pixels = sum(1 for value in data if value)
    return v4_metric, true_pixels, box


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    capture = compose(CAPTURE_LAYERS)
    cleaned = erase_dynamic(capture)
    with Image.open(TRUTH) as image:
        truth = image.convert("RGB")

    capture_metrics = compare(capture.crop((0, 0, 240, 160)), truth)
    cleaned_metrics = compare(cleaned.crop((0, 0, 240, 160)), truth)

    print("capture layers (scenario 41, with its own numbers and sprite)")
    print(f"  v4={capture_metrics[0]:6d} true={capture_metrics[1]:6d} "
          f"bbox={capture_metrics[2]}")
    print("cleaned plate (the dynamic content erased)")
    print(f"  v4={cleaned_metrics[0]:6d} true={cleaned_metrics[1]:6d} "
          f"bbox={cleaned_metrics[2]}")

    OUT.mkdir(parents=True, exist_ok=True)
    capture.crop((0, 0, 240, 160)).save(OUT / "plate-capture.png")
    cleaned.crop((0, 0, 240, 160)).save(OUT / "plate-cleaned.png")

    if args.write:
        write_plate(cleaned)
        print(f"wrote {GRAPHICS / 'battle_ui_result_plate.bmp'}")
        print("sha256 " + hashlib.sha256(
            (GRAPHICS / "battle_ui_result_plate.bmp").read_bytes()
        ).hexdigest())
    return 0


def write_plate(cleaned: Image.Image) -> None:
    """Write the cleaned plate as an 8bpp layer with an exact palette."""

    pixels = list(cleaned.getdata())
    colours: list[tuple[int, int, int]] = []
    for colour in pixels:
        if colour == TRANSPARENT_SENTINEL:
            continue
        if colour not in colours:
            colours.append(colour)
    palette = [TRANSPARENT_SENTINEL] + colours
    lookup = {colour: index + 1 for index, colour in enumerate(colours)}
    indices = [
        0 if colour == TRANSPARENT_SENTINEL else lookup[colour]
        for colour in pixels
    ]
    plate = Image.new("P", cleaned.size, 0)
    flat: list[int] = []
    for colour in palette:
        flat.extend(colour)
    flat.extend([0] * (768 - len(flat)))
    plate.putpalette(flat)
    plate.putdata(indices)
    plate.save(GRAPHICS / "battle_ui_result_plate.bmp")
    (GRAPHICS / "battle_ui_result_plate.json").write_text(
        '{\n  "type": "regular_bg",\n  "bpp_mode": "bpp_8",\n'
        f'  "colors_count": {len(palette)}\n}}\n',
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())
