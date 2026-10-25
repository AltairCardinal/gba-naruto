#!/usr/bin/env python3
"""Extract the original's 「開始」 title screen and project its residual.

What this tool answers
----------------------
The original's battle-14 entry performance shows a 「開始」 calligraphy title
on top of the battlefield right before the first black field.  The remake has
no such screen (X2-6: none of the remake's 783 walk frames show it), which
costs 5869 + 4699 = 10568 residual pixels (judgment bench steps 09 and 10).

This tool

  1. recovers the title art from the original's own frames (the title is
     drawn with OBJ sprites, so the pixels that differ between the frame
     before the title and the title frame *are* the title),
  2. writes the recovered art as RGBA PNGs, and
  3. projects the residual the remake would reach if it drew that art at
     that place on its own battlefield.

Step 3 is the decision instrument: it separates the pixels the missing
title costs from the pixels the remake's battlefield already differs by.

Usage::

    python tools/s49_opening_title/project_title_residual.py \
        --original-dir build/s49-pairing/walk5/dense-original \
        --remake-dir build/s49-pairing/walk5/dense-remake \
        --out build/s49-opening-title
"""

from __future__ import annotations

import argparse
import json
import pathlib

from PIL import Image, ImageChops

FIELD = (0, 0, 240, 128)

# The original's walk frames: the beat before the title, the title itself
# and the next beat (the title animates).
ORIGINAL_BEATS = {
    "before": "step-0184-beat.png",
    "title": "step-0207-beat.png",
    "title_next": "step-0230-beat.png",
}

# The remake's frame at the same phase: the deployment screen.
REMAKE_FRAME = "step-0292-in.png"


def difference_mask(left: Image.Image, right: Image.Image) -> Image.Image:
    delta = ImageChops.difference(left.crop(FIELD), right.crop(FIELD))
    red, green, blue = delta.split()
    mask = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return mask.point(lambda value: 255 if value else 0)


def components(mask: Image.Image) -> list[tuple[int, int, int, int, int]]:
    """8-connected components of a mask, biggest first."""
    pixels = mask.load()
    width, height = mask.size
    seen = [[False] * width for _ in range(height)]
    found: list[tuple[int, int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == 0 or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            points = []
            while stack:
                cx, cy = stack.pop()
                points.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if (0 <= nx < width and 0 <= ny < height
                                and pixels[nx, ny] and not seen[ny][nx]):
                            seen[ny][nx] = True
                            stack.append((nx, ny))
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            found.append((len(points), min(xs), min(ys), max(xs) + 1,
                          max(ys) + 1))
    found.sort(reverse=True)
    return found


def extract_art(before: Image.Image, title: Image.Image, box: tuple[int, int, int, int],
                 source: Image.Image) -> Image.Image:
    """The opaque title pixels of one component, as RGBA."""
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    art = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mask = difference_mask(before, title).crop((x0, y0, x1, y1))
    mask_pixels = mask.load()
    art_pixels = art.load()
    source_pixels = source.crop((x0, y0, x1, y1)).load()
    for y in range(height):
        for x in range(width):
            if mask_pixels[x, y]:
                red, green, blue = source_pixels[x, y]
                art_pixels[x, y] = (red, green, blue, 255)
    return art


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--original-dir", required=True)
    parser.add_argument("--remake-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    original_dir = pathlib.Path(args.original_dir)
    remake_dir = pathlib.Path(args.remake_dir)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    before = Image.open(original_dir / ORIGINAL_BEATS["before"]).convert("RGB")
    title = Image.open(original_dir / ORIGINAL_BEATS["title"]).convert("RGB")
    title_next = Image.open(original_dir / ORIGINAL_BEATS["title_next"]).convert("RGB")
    remake = Image.open(remake_dir / REMAKE_FRAME).convert("RGB")

    mask = difference_mask(before, title)
    found = components(mask)

    # The title is the two biggest components: 「開」 and 「始」.  The
    # smaller ones are the bird's animation frame and the scene's own
    # reticle, which the remake already draws.
    glyphs = found[:2]
    # The bird's animation frame is the component above the title; the
    # reticle brackets are below it.
    art_boxes = []
    for area, x0, y0, x1, y1 in glyphs:
        art_boxes.append((x0, y0, x1, y1))

    arts = []
    for index, box in enumerate(art_boxes):
        art = extract_art(before, title, box, title)
        art.save(out / f"glyph-{index}.png")
        # The title animates: the second beat paints the same glyphs with a
        # different frame.  The second phase is the glyph as the second
        # title frame paints it, that is the pixels that differ from the
        # frame before the title.
        art_next = extract_art(before, title_next, box, title_next)
        art_next.save(out / f"glyph-{index}-phase1.png")
        arts.append((box, art, art_next))

    # ---- the projection ----------------------------------------------------
    # The remake's screen: its own battlefield, the title art on top of it
    # and the remake's own text erased (the original has no text there).
    def project(phase: int) -> Image.Image:
        projected = remake.copy()
        for box, art, art_next in arts:
            projected.paste(art_next if phase else art, (box[0], box[1]),
                            art_next if phase else art)
        # The remake's deployment text ("... DEPLOY" / "START") has no
        # counterpart in the original: erase it with the original's picture.
        text_mask = difference_mask(before, remake)
        text_region = (0, 0, 70, 40)
        erase = text_mask.crop(text_region)
        projected.paste(before.crop(text_region), (0, 0), erase)
        return projected

    def residual(left: Image.Image, right: Image.Image) -> int:
        return sum(difference_mask(left, right).histogram()[1:])

    report = {
        "schema": "konoha.s49-opening-title-projection.v1",
        "original": {
            "before": ORIGINAL_BEATS["before"],
            "title": ORIGINAL_BEATS["title"],
            "title_next": ORIGINAL_BEATS["title_next"],
        },
        "remake": REMAKE_FRAME,
        "glyph_boxes": [list(box) for box in art_boxes],
        "residual": {
            "original_title_vs_remake_screen": residual(title, remake),
            "original_before_vs_remake_screen": residual(before, remake),
            "projected_phase0": residual(title, project(0)),
            "projected_phase1": residual(title_next, project(1)),
            "original_title_vs_original_title_next":
                    residual(title, title_next),
        },
    }
    (out / "projection.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")

    print(json.dumps(report["residual"], indent=2))
    print("->", out / "projection.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
