#!/usr/bin/env python3
"""Check the 「開始」 title's placement against the original's own frames.

The runtime draws the title with five Butano sprite items, and a Butano
sprite is placed relative to the centre of the screen: create_sprite(x, y)
puts the centre of the sprite's cell at (120 + x, 80 + y).  The recovered art
is measured in screen absolute coordinates, so the two systems have to be
told apart.

This tool composes the title out of the staged sprite items, the way the
runtime draws them, and compares the result with the original's own frames:

  * the ink box of the composed title against the ink box the original's
    title frame carries,
  * the residual of the remake's own battlefield with the composed title
    pasted on it against the original's title frame,
  * the same residual with the placement the runtime used before the fix
    (the cell's screen absolute centre), to show what the bug cost.

Usage::

    python tools/s49_v3_dialogue/verify_title_placement.py \\
        --staged build/s49-v3/title-assets \\
        --original build/s49-pairing/walk5/dense-original \\
        --remake build/s49-pairing/walk5/dense-remake
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from PIL import Image, ImageChops

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\battle_opening_title.h")

GLYPH_RE = re.compile(
    r"battle_opening_title_glyph\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)")
PIECE_DEF_RE = re.compile(
    r"static constexpr battle_opening_title_piece (\w+) =\s*\{\s*"
    r'"([^"]+)",\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\}')
PIECES_RE = re.compile(
    r"std::array<battle_opening_title_piece,\s*(\d+)>\s*pieces\s*=\s*\{\{(.*?)\}\};",
    re.S)


def read_header(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    glyphs = [
        {"x": int(m[0]), "y": int(m[1]),
         "width": int(m[2]), "height": int(m[3])}
        for m in GLYPH_RE.findall(text)
    ]
    definitions = {
        name: {"item": item, "cell_width": int(width),
               "cell_height": int(height),
               "art_offset_x": int(offset_x),
               "art_offset_y": int(offset_y)}
        for name, item, width, height, offset_x, offset_y
        in PIECE_DEF_RE.findall(text)
    }
    match = PIECES_RE.search(text)
    order = re.findall(r"(\w+)", match.group(2))
    pieces = [definitions[name] for name in order]
    return {"glyphs": glyphs, "pieces": pieces}


def compose(staged_dir: pathlib.Path, header: dict, phase: int,
            screen_centre=(120, 80), absolute=False) -> Image.Image:
    """The title as the runtime draws it, on an empty 240x160 canvas.

    With ``absolute`` the pieces are placed the way the runtime placed them
    before the fix: the cell's screen absolute centre was handed to
    create_sprite(), and Butano shifts that by the screen's centre, so the
    whole title lands a screen centre further right and down.
    """
    canvas = Image.new("RGBA", (240, 160), (0, 0, 0, 0))
    for index, piece in enumerate(header["pieces"]):
        image = Image.open(staged_dir / f"{piece['item']}.bmp").convert("P")
        palette = image.getpalette()
        cell_w = piece["cell_width"]
        cell_h = piece["cell_height"]
        # The bitmap holds the two phases side by side.
        left = phase * cell_w
        cell = image.crop((left, 0, left + cell_w, cell_h))
        glyph = header["glyphs"][0 if "_kai" in piece["item"] else 1]
        screen_x = glyph["x"] + piece["art_offset_x"]
        screen_y = glyph["y"] + piece["art_offset_y"]
        if absolute:
            # Butano puts the cell's centre at (120 + x, 80 + y), and the
            # runtime handed it the cell's screen absolute centre.
            screen_x += screen_centre[0]
            screen_y += screen_centre[1]
        rgba = Image.new("RGBA", (cell_w, cell_h))
        rgba.putdata([
            (palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2], 255)
            if index != 0 else (0, 0, 0, 0)
            for index in list(cell.getdata())
        ])
        canvas.alpha_composite(rgba, (screen_x, screen_y))
    return canvas


def ink_box(image: Image.Image) -> dict:
    alpha = image.getchannel("A")
    box = alpha.getbbox()
    if not box:
        return {"left": None, "top": None, "right": None, "bottom": None,
                "ink": 0}
    return {"left": box[0], "top": box[1], "right": box[2], "bottom": box[3],
            "ink": sum(1 for value in alpha.getdata() if value)}


def difference_mask(left: Image.Image, right: Image.Image):
    delta = ImageChops.difference(left.crop((0, 0, 240, 128)),
                                  right.crop((0, 0, 240, 128)))
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return mask.point(lambda value: 255 if value else 0)


def residual(left: Image.Image, right: Image.Image) -> int:
    return sum(difference_mask(left, right).histogram()[1:])


def project(remake: Image.Image, art: Image.Image,
            before: Image.Image) -> Image.Image:
    """The remake's battlefield with the title on it."""
    projected = remake.copy()
    projected.paste(art, (0, 0), art)
    text_mask = difference_mask(before, remake).crop((0, 0, 70, 40))
    projected.paste(before.crop((0, 0, 70, 40)), (0, 0), text_mask)
    return projected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", default="build/s49-v3/title-assets")
    parser.add_argument("--original",
                        default="build/s49-pairing/walk5/dense-original")
    parser.add_argument("--remake",
                        default="build/s49-pairing/walk5/dense-remake")
    parser.add_argument("--header", default=str(HEADER))
    args = parser.parse_args(argv)

    staged_dir = pathlib.Path(args.staged)
    original_dir = pathlib.Path(args.original)
    remake_dir = pathlib.Path(args.remake)
    header = read_header(pathlib.Path(args.header))

    original = Image.open(original_dir / "step-0207-beat.png").convert("RGB")
    original_next = Image.open(original_dir / "step-0230-beat.png").convert("RGB")
    before = Image.open(original_dir / "step-0184-beat.png").convert("RGB")
    remake = Image.open(remake_dir / "step-0292-in.png").convert("RGB")

    report = {"placements": [], "phases": []}
    for index, piece in enumerate(header["pieces"]):
        glyph = header["glyphs"][0 if "_kai" in piece["item"] else 1]
        cell_w = piece["cell_width"]
        cell_h = piece["cell_height"]
        screen_x = glyph["x"] + piece["art_offset_x"]
        screen_y = glyph["y"] + piece["art_offset_y"]
        butano_x = screen_x + cell_w // 2 - 120
        butano_y = screen_y + cell_h // 2 - 80
        report["placements"].append({
            "item": piece["item"],
            "cell": [cell_w, cell_h],
            "cell_screen_origin": [screen_x, screen_y],
            "butano_position": [butano_x, butano_y],
            "butano_position_absolute_bug": [
                screen_x + cell_w // 2, screen_y + cell_h // 2],
        })

    for phase, reference in ((0, original), (1, original_next)):
        art = compose(staged_dir, header, phase)
        art_absolute = compose(staged_dir, header, phase, absolute=True)
        projected = project(remake.copy(), art, before)
        projected_absolute = project(remake.copy(), art_absolute, before)
        report["phases"].append({
            "phase": phase,
            "composed_ink_box": ink_box(art),
            "composed_ink_box_absolute": ink_box(art_absolute),
            "residual_fixed": residual(reference, projected),
            "residual_absolute": residual(reference, projected_absolute),
            "residual_without_title": residual(reference, remake),
        })

    out = staged_dir / "placement.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
