#!/usr/bin/env python3
"""Deduplicate a palettised BMP's palette, losslessly.

Butano's `bpp_4_auto` quantiser refuses an input whose palette contains two
entries with the same RGB colour:

    ValueError: There's two used identical colors in: 1 and 33

That is a property of the *source asset*, not of the 4bpp conversion: the
image renders identically either way.  This tool rewrites the BMP with a
palette in which every used colour appears exactly once (index 0 stays the
transparent slot), so the 4bpp conversion can run.

The rewrite is verified pixel-by-pixel in RGB space: the output must be
identical to the input.

Usage:
    python dedupe_bmp_palette.py --bmp <in.bmp> --out <out.bmp> [--report <json>]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from PIL import Image


def dedupe(src: pathlib.Path, dst: pathlib.Path) -> dict[str, object]:
    image = Image.open(src)
    if image.mode != "P":
        raise SystemExit(f"not a palettised BMP: {src}")
    palette = image.getpalette()
    pixels = list(image.getdata())
    width, height = image.size

    used = sorted(set(pixels))
    # index 0 keeps its slot (GBA treats index 0 as transparent in 4bpp)
    kept: list[int] = [0] if 0 in used else []
    kept += [i for i in used if i != 0]

    remap: dict[int, int] = {}
    new_palette: list[tuple[int, int, int]] = []
    seen: dict[tuple[int, int, int], int] = {}
    for index in kept:
        color = tuple(palette[index * 3 : index * 3 + 3])
        if color in seen:
            remap[index] = seen[color]
            continue
        new_index = len(new_palette)
        seen[color] = new_index
        remap[index] = new_index
        new_palette.append(color)

    out_pixels = [remap[p] for p in pixels]
    out = Image.new("P", (width, height))
    flat: list[int] = []
    for color in new_palette:
        flat.extend(color)
    flat.extend([0] * (768 - len(flat)))
    out.putpalette(flat)
    out.putdata(out_pixels)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)

    # verify in RGB space
    a = list(Image.open(src).convert("RGB").getdata())
    b = list(Image.open(dst).convert("RGB").getdata())
    changed = sum(1 for x, y in zip(a, b) if x != y)
    return {
        "source": str(src),
        "output": str(dst),
        "palette_entries_before": len(palette) // 3,
        "palette_entries_after": len(new_palette),
        "colors_removed": len(palette) // 3 - len(new_palette),
        "distinct_indices_before": len(used),
        "pixels_total": len(a),
        "pixels_changed_rgb": changed,
        "lossless": changed == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bmp", nargs="+", required=True)
    parser.add_argument("--out-dir", default=r"D:\Github\gba-naruto\build\w22-d6\bpp4-auto")
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    result = {}
    for raw in args.bmp:
        src = pathlib.Path(raw)
        dst = out_dir / (src.stem + ".dedup.bmp")
        result[src.name] = dedupe(src, dst)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        report = pathlib.Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
