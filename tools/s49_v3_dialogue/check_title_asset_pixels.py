#!/usr/bin/env python3
"""Check the staged 「開始」 items against the recovered art, pixel by pixel.

The staged items are what the runtime will draw.  This tool rebuilds the
expected cell of every piece straight from the recovered art and compares it
with the cell that is in the staged bitmap, so a mistake in the cut (the
bug the original generator had) cannot slip through.

Usage::

    python tools/s49_v3_dialogue/check_title_asset_pixels.py \\
        --staged build/s49-v3/title-assets
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

sys.path.insert(0, str(HERE))

import regenerate_title_assets as regen  # noqa: E402
import verify_title_placement as verify  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", default="build/s49-v3/title-assets")
    parser.add_argument("--header", default=str(regen.HEADER))
    parser.add_argument("--art", default=str(regen.ART_DIR))
    args = parser.parse_args(argv)

    staged_dir = pathlib.Path(args.staged)
    header = verify.read_header(pathlib.Path(args.header))
    art_dir = pathlib.Path(args.art)

    cleaned = {}
    for name, (first, second) in regen.GLYPH_ART.items():
        phases = []
        for file_name in (first, second):
            indices, width, height = regen.load_phase(art_dir / file_name)
            phases.append((indices, width, height))
        cleaned[name] = phases

    report = []
    for piece in header["pieces"]:
        glyph = "kai" if "_kai" in piece["item"] else "shi"
        box = header["glyphs"][0 if glyph == "kai" else 1]
        art_w = box["width"]
        art_h = box["height"]
        image = Image.open(staged_dir / f"{piece['item']}.bmp").convert("P")
        cell_w = piece["cell_width"]
        cell_h = piece["cell_height"]
        row = {"item": piece["item"], "glyph": glyph, "phases": []}
        for phase in (0, 1):
            indices, width, height = cleaned[glyph][phase]
            expected = regen.frame_cell(indices, width, height,
                                        cell_w, cell_h,
                                        piece["art_offset_x"],
                                        piece["art_offset_y"])
            actual = list(image.crop((phase * cell_w, 0,
                                      (phase + 1) * cell_w, cell_h)).getdata())
            differing = sum(1 for left, right in zip(expected, actual)
                            if left != right)
            row["phases"].append({
                "phase": phase,
                "expected_ink": sum(1 for value in expected if value),
                "actual_ink": sum(1 for value in actual if value),
                "differing_pixels": differing,
            })
        report.append(row)

    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = staged_dir / "pixel-check.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
