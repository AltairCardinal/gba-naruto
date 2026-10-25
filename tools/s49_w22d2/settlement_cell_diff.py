#!/usr/bin/env python3
"""Decompose the settlement screen difference into rows / columns / cells.

Wave 22 / D2.  The remake's settlement screen (結算屏) differs from the
original's truth by 985 px (real chain) / 684 px (poked chain).  This tool
answers the question that matters for "same premise => 0 px":

* **which rows** carry the difference,
* **which columns** carry it,
* **how many pixels are outside the number area** (the answer must be 0),
* and, as a positive control, **the 經驗值 row -- whose value (125/125/125)
  is the same on both sides -- is byte identical**, so a number cell that
  holds the same value renders identically.

Usage::

    python tools/s49_w22d2/settlement_cell_diff.py \
        --truth build/s49-victory-capture/w4/settlement-truth/02-settlement-exp-power-turns.png \
        --remake build/w20-e1/chain-fix2/shots/page-001-result.png \
        --out build/w22-d2/settlement-cell-diff-real.json
"""

from __future__ import annotations

import argparse
import json
import pathlib

from PIL import Image

WIDTH = 240
HEIGHT = 160


def load(path: pathlib.Path) -> list[tuple[int, int, int]]:
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise SystemExit(f"{path} is {image.size}, expected {(WIDTH, HEIGHT)}")
    return list(image.get_flattened_data())


def bands(flags: list[bool]) -> list[list[int]]:
    out: list[list[int]] = []
    start = None
    for index, flag in enumerate(flags):
        if flag:
            if start is None:
                start = index
        elif start is not None:
            out.append([start, index - 1])
            start = None
    if start is not None:
        out.append([start, len(flags) - 1])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    truth = load(pathlib.Path(args.truth))
    remake = load(pathlib.Path(args.remake))

    rows = [0] * HEIGHT
    cols = [0] * WIDTH
    total = 0
    for index, (a, b) in enumerate(zip(truth, remake)):
        if a != b:
            total += 1
            rows[index // WIDTH] += 1
            cols[index % WIDTH] += 1

    row_bands = bands([count > 0 for count in rows])
    col_bands = bands([count > 0 for count in cols])
    band_rows = {y for start, end in row_bands for y in range(start, end + 1)}

    # column profile restricted to the differing row band
    in_band = [0] * WIDTH
    for y in sorted(band_rows):
        for x in range(WIDTH):
            if truth[y * WIDTH + x] != remake[y * WIDTH + x]:
                in_band[x] += 1

    document = {
        "label": args.label,
        "truth": args.truth,
        "remake": args.remake,
        "total_diff_px": total,
        "diff_row_bands": row_bands,
        "diff_col_bands": col_bands,
        "diff_rows": {str(y): count for y, count in enumerate(rows) if count},
        "diff_px_outside_row_band": sum(count for y, count in enumerate(rows)
                                         if y not in band_rows),
        "diff_px_outside_col_bands": sum(cols[x] for x in range(WIDTH)
                                         if not any(start <= x <= end
                                                    for start, end in col_bands)),
        "column_profile_in_diff_band": {str(x): in_band[x]
                                        for x in range(WIDTH) if in_band[x]},
        "zero_diff_columns_in_number_area": [x for x in range(WIDTH)
                                             if x >= 88 and in_band[x] == 0],
    }
    text = json.dumps(document, ensure_ascii=False, indent=1) + "\n"
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
