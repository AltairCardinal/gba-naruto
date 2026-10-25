#!/usr/bin/env python3
"""W24-G3: analyse the settlement screen's 514 px residual.

Two questions:
  Q1  Are the 合計 row's glyph footprints identical between the original
      truth frame and the remake?  (F4 says the red pixel *count* matches,
      203 = 203, but positions were never checked.)
  Q2  What is the original's top-border decoration made of, and can it be
      baked into the remake's `battle_ui_result_plate` BG asset?

Usage:
  python tools/s49_w24g3/analyse_settlement.py [--out build/w24-g3]
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]

TRUTH = REPO / "build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png"
REMAKE = REPO / "build/w23-f4/run/shots/page-001-result.png"

PLATE = Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\battle_ui_result_plate.bmp")
PALETTE = Path(r"D:\Shell\Github\gba-naruto-butano\butano-sequel\graphics\battle_ui_result_total_palette.bmp")

# The settlement screen's box, in screen coordinates.
BOX_X0, BOX_X1 = 88, 236          # columns, exclusive upper bound
BOX_Y0, BOX_Y1 = 106, 154         # rows, exclusive upper bound

# The 合計 row.
TOTAL_Y0, TOTAL_Y1 = 139, 151

# The BG plate is displayed at create_bg(8, 48): screen (x, y) == plate (x + 16, y).
PLATE_DX = 16


def load(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def diff_pixels(a: Image.Image, b: Image.Image, x0: int, x1: int, y0: int, y1: int):
    out = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            pa = a.getpixel((x, y))
            pb = b.getpixel((x, y))
            if pa != pb:
                out.append((x, y, pa, pb))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "build/w24-g3"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    truth = load(TRUTH)
    remake = load(REMAKE)

    report: dict = {}

    # ---------------------------------------------------------------- Q1
    # Footprint equality of the 合計 row.
    def red_sets(im):
        light, dark, outl = set(), set(), set()
        for y in range(TOTAL_Y0, TOTAL_Y1):
            for x in range(BOX_X0, BOX_X1):
                p = im.getpixel((x, y))
                if p == (231, 99, 66):
                    light.add((x, y))
                elif p == (231, 24, 0):
                    dark.add((x, y))
                elif p == (231, 173, 140):
                    outl.add((x, y))
        return light, dark, outl

    t_light, t_dark, t_outl = red_sets(truth)
    r_light, r_dark, r_outl = red_sets(remake)

    report["total_row"] = {
        "truth_light": len(t_light),
        "truth_dark": len(t_dark),
        "truth_outline": len(t_outl),
        "remake_light": len(r_light),
        "remake_dark": len(r_dark),
        "remake_outline": len(r_outl),
        "truth_red_total": len(t_light) + len(t_dark),
        "remake_red_total": len(r_light) + len(r_dark),
        "footprints_equal": (t_light | t_dark) == (r_light | r_dark),
        "footprint_symmetric_difference": len((t_light | t_dark) ^ (r_light | r_dark)),
        "outline_equal": t_outl == r_outl,
        "outline_symmetric_difference": len(t_outl ^ r_outl),
        "truth_dark_not_in_remake_dark": len(t_dark - r_dark),
        "truth_light_not_in_remake_dark": len(t_light - r_dark),
        "remake_dark_not_in_truth_red": len(r_dark - (t_light | t_dark)),
    }

    # Per-digit breakdown: the 合計 row holds three 3 digit numbers.
    # Digits are 8 px cells; find the columns that carry red pixels.
    red_cols = sorted({x for x, _ in (t_light | t_dark)})
    cells = []
    run = []
    for x in red_cols:
        if run and x == run[-1] + 1:
            run.append(x)
        else:
            if run:
                cells.append(run)
            run = [x]
    if run:
        cells.append(run)
    report["total_row"]["digit_column_groups"] = cells
    for cell in cells:
        cx0, cx1 = cell[0], cell[-1] + 1
        lt = sum(1 for x, y in t_light if cx0 <= x < cx1)
        dk = sum(1 for x, y in t_dark if cx0 <= x < cx1)
        cells_info = {
            "x0": cx0,
            "x1": cx1,
            "truth_light": lt,
            "truth_dark": dk,
        }
        # Per glyph bitmap: 4 wide x 11 tall, offset so the glyph is centred.
        glyph = []
        for y in range(TOTAL_Y0, TOTAL_Y1):
            row = ""
            for x in range(cx0, cx1):
                p = truth.getpixel((x, y))
                row += {
                    (231, 99, 66): "L",
                    (231, 24, 0): "D",
                    (231, 173, 140): "o",
                    (231, 247, 214): ".",
                }.get(p, "?")
            glyph.append(row)
        cells_info["truth_glyph"] = glyph
        report["total_row"].setdefault("digits", []).append(cells_info)

    # ---------------------------------------------------------------- Q2
    # The top border decoration.
    border = []
    for y in range(BOX_Y0, BOX_Y0 + 3):
        for x in range(BOX_X0, BOX_X1):
            pt = truth.getpixel((x, y))
            pr = remake.getpixel((x, y))
            if pt != pr:
                border.append((x, y, pt, pr))
    hist = Counter((pt, pr) for _, _, pt, pr in border)
    report["top_border"] = {
        "diff_px": len(border),
        "color_pairs": [{"truth": list(k[0]), "remake": list(k[1]), "px": v}
                        for k, v in hist.most_common()],
        "rows": sorted({y for _, y, _, _ in border}),
        "cols": sorted({x for x, _, _, _ in border}),
    }

    # The truth's border band as art.
    art = []
    for y in range(BOX_Y0 - 2, BOX_Y0 + 6):
        row = ""
        for x in range(BOX_X0, BOX_X1):
            p = truth.getpixel((x, y))
            row += {
                (107, 156, 90): ".",
                (99, 189, 115): "+",
                (99, 115, 90): "#",
                (231, 247, 214): " ",
            }.get(p, "?")
        art.append({"y": y, "art": row})
    report["top_border"]["truth_art"] = art

    # The plate asset: does it already hold the truth's border colours?
    plate = Image.open(PLATE).convert("RGB")
    plate_colors = Counter(plate.getdata())
    need = {pt for _, _, pt, _ in border}
    report["plate"] = {
        "size": list(plate.size),
        "distinct_colors": len(plate_colors),
        "truth_border_colors_in_plate": {
            str(list(c)): plate_colors.get(c, 0) for c in sorted(need)
        },
        "plate_row106_colors": dict(
            (str(list(c)), n)
            for c, n in Counter(
                plate.getpixel((x, 106 + 0)) for x in range(plate.size[0])
            ).most_common()
        ),
    }

    pal = Image.open(PALETTE).convert("RGB")
    pal_colors = []
    for i in range(16):
        pal_colors.append(list(pal.getpixel((i % 8, i // 8))))
    report["total_palette"] = pal_colors
    report["total_palette_has_light_red"] = [231, 99, 66] in pal_colors

    # Whole-screen diff summary by band.
    bands = {}
    for y in range(160):
        n = sum(
            1
            for x in range(240)
            if truth.getpixel((x, y)) != remake.getpixel((x, y))
        )
        if n:
            bands[y] = n
    report["diff_by_row"] = bands
    report["total_diff_px"] = sum(bands.values())

    with open(out_dir / "settlement-analysis.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    # Human readable summary.
    print("=== Q1 合計 row ===")
    for k, v in report["total_row"].items():
        if k not in ("digits", "digit_column_groups"):
            print(f"  {k}: {v}")
    print("  digit groups:", report["total_row"]["digit_column_groups"])
    print("=== Q2 top border ===")
    print("  diff px:", report["top_border"]["diff_px"])
    for cp in report["top_border"]["color_pairs"]:
        print("   ", cp)
    print("=== plate ===")
    print("  ", report["plate"]["distinct_colors"], "colors;",
          report["plate"]["truth_border_colors_in_plate"])
    print("=== total palette ===")
    print("  ", report["total_palette"])
    print("  has light red:", report["total_palette_has_light_red"])
    print("=== total diff px (whole screen):", report["total_diff_px"])
    print("  rows:", {k: v for k, v in bands.items()})
    print(f"written: {out_dir / 'settlement-analysis.json'}")


if __name__ == "__main__":
    main()
