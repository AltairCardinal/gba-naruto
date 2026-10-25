#!/usr/bin/env python3
"""W24-G3: revert the settlement asset patch.

The wave-24 lane copy keeps `graphics/` and `audio/` as *symlinks* into the
shared tree, so patching the lane's graphics directory patched the shared
tree.  This tool puts the three touched assets back the way they were.

The revert is derived from the same inputs the patch used, so it does not
depend on a backup:

  * the font atlas: every pixel the patch moved from index 2 to index 1
    goes back to index 2 (the light cell lists are in the patch report);
  * the palette: table entry 1 goes back to (231, 247, 214);
  * the plate: every pixel that the patch changed is set back to the colour
    the *remake* frame shows there (the remake frame is the ground truth
    for what the plate has to produce).

Usage:
  python tools/s49_w24g3/revert_settlement_assets.py \
      --target D:/Shell/Github/gba-naruto-butano/butano-sequel/graphics \
      --report build/w24-g3/patch-report.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
REMAKE = REPO / "build/w23-f4/run/shots/page-001-result.png"
TRUTH = REPO / "build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png"

LIGHT = (231, 99, 66)
DARK = (231, 24, 0)
OUTLINE = (231, 173, 140)

CELL_H = 16
PLATE_DX = 16


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, help="graphics directory to revert")
    ap.add_argument("--report", default=str(REPO / "build/w24-g3/patch-report.json"))
    args = ap.parse_args()

    graphics = Path(args.target)
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    truth = Image.open(TRUTH).convert("RGB")
    remake = Image.open(REMAKE).convert("RGB")

    # ---- font atlas -------------------------------------------------
    atlas_path = graphics / "battle_result_font.bmp"
    atlas = Image.open(atlas_path).copy()
    apx = atlas.load()
    cell_of_char = {i["char"]: i["cell"] for i in report["instances"]}
    reverted = 0
    for char, cells in report["per_character_light_cells"].items():
        index = cell_of_char[char]
        for cx, cy in cells:
            assert apx[cx, index * CELL_H + cy] == report["light_slot"]
            apx[cx, index * CELL_H + cy] = 2
            reverted += 1
    atlas.save(atlas_path.with_name("battle_result_font.rev.bmp"), format="BMP")
    data = atlas_path.with_name("battle_result_font.rev.bmp").read_bytes()
    atlas_path.with_name("battle_result_font.rev.bmp").unlink()
    with open(atlas_path, "r+b") as fh:
        fh.write(data)
        fh.truncate()

    # ---- palette ----------------------------------------------------
    palette_path = graphics / "battle_ui_result_total_palette.bmp"
    palette = Image.open(palette_path).copy()
    table = list(palette.getpalette() or [])
    slot = report["light_slot"]
    table[slot * 3:slot * 3 + 3] = list(report["palette_slot"]["old_rgb"])
    palette.putpalette(table)
    palette.save(palette_path.with_name("palette.rev.bmp"), format="BMP")
    data = palette_path.with_name("palette.rev.bmp").read_bytes()
    palette_path.with_name("palette.rev.bmp").unlink()
    with open(palette_path, "r+b") as fh:
        fh.write(data)
        fh.truncate()

    # ---- plate ------------------------------------------------------
    plate_path = graphics / "battle_ui_result_plate.bmp"
    plate = Image.open(plate_path).copy()
    ppx = plate.load()
    plate_pal = plate.getpalette()
    rgb_to_index = {}
    for i in range(len(plate_pal) // 3):
        rgb = tuple(plate_pal[i * 3:i * 3 + 3])
        rgb_to_index.setdefault(rgb, i)

    digit_px = set()
    for y in range(139, 150):
        for x in range(88, 236):
            if truth.getpixel((x, y)) in (LIGHT, DARK, OUTLINE):
                digit_px.add((x, y))

    reverted_plate = 0
    for y in range(160):
        for x in range(240):
            if (x, y) in digit_px:
                continue
            if truth.getpixel((x, y)) == remake.getpixel((x, y)):
                continue
            idx = rgb_to_index.get(remake.getpixel((x, y)))
            if idx is None:
                raise SystemExit(f"remake colour missing from the plate palette at {(x, y)}")
            ppx[x + PLATE_DX, y] = idx
            reverted_plate += 1
    plate.save(plate_path.with_name("plate.rev.bmp"), format="BMP")
    data = plate_path.with_name("plate.rev.bmp").read_bytes()
    plate_path.with_name("plate.rev.bmp").unlink()
    with open(plate_path, "r+b") as fh:
        fh.write(data)
        fh.truncate()

    print("reverted atlas px:", reverted)
    print("reverted palette slot:", slot, "->", report["palette_slot"]["old_rgb"])
    print("reverted plate px:", reverted_plate)


if __name__ == "__main__":
    main()
