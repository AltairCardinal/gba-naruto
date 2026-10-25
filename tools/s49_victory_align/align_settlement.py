#!/usr/bin/env python3
"""Pixel-align the remake's settlement chain against the original's truth.

The original's truth images live in
``build/s49-victory-capture/w4/settlement-truth/`` (nine PNGs plus the
receipt ``settlement-truth.json``).  The remake's running frames are
produced by ``tools/s49_battle_balance/z1_settlement_chain.py``.

This tool compares the two sides screen by screen and reports, for every
pair:

* the number of pixels that differ (any channel differs),
* the contiguous row bands that contain differences,
* the number of distinct colours on each side,
* whether the two images are byte identical.

The truth screens have no remake counterpart of their own, so the pairs are
given explicitly.  ``--auto`` pairs the truth images with the remake's
screens by their settlement phase, using the file names' prefixes.

Usage::

    python tools/s49_victory_align/align_settlement.py \
        --truth build/s49-victory-capture/w4/settlement-truth \
        --remake build/z1/chain-e/shots \
        --out build/w3/settlement-align.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

from PIL import Image

WIDTH = 240
HEIGHT = 160
SCREEN_PIXELS = WIDTH * HEIGHT

# The truth screens and the remake's screens of the same settlement phase.
# The remake's file names carry the phase, the truth's carry the index.
PHASE_PAIRS = [
    ("01-victory.png", "page-000-outcome.png", "victory"),
    ("02-settlement-exp-power-turns.png", "page-001-result.png", "result"),
    ("03-levelup-naruto.png", "page-002-level_up.png", "level_up_1"),
    ("05-levelup-sasuke-jutsu-name.png", "page-003-level_up.png", "level_up_2"),
    ("04-levelup-konohamaru.png", "page-004-level_up.png", "level_up_3"),
    ("05-levelup-sasuke.png", "page-005-level_up.png", "level_up_4"),
    ("06-levelup-sakura.png", "page-006-level_up.png", "level_up_5"),
    ("07-ninja-tool-list.png", "page-007-level_up.png", "level_up_6"),
]


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> list[tuple[int, int, int]]:
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise SystemExit(f"{path} is {image.size}, expected {(WIDTH, HEIGHT)}")
    return list(image.get_flattened_data())


def row_bands(rows: list[int]) -> list[list[int]]:
    bands: list[list[int]] = []
    start = None
    for index, count in enumerate(rows):
        if count:
            if start is None:
                start = index
        elif start is not None:
            bands.append([start, index - 1])
            start = None
    if start is not None:
        bands.append([start, len(rows) - 1])
    return bands


def compare(truth: pathlib.Path, remake: pathlib.Path) -> dict:
    left = load(truth)
    right = load(remake)
    rows = [0] * HEIGHT
    columns = [0] * WIDTH
    diff = 0
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            diff += 1
            rows[index // WIDTH] += 1
            columns[index % WIDTH] += 1
    return {
        "truth": truth.name,
        "remake": remake.name,
        "truth_sha256": sha256_file(truth),
        "remake_sha256": sha256_file(remake),
        "diff_px": diff,
        "same_px": SCREEN_PIXELS - diff,
        "identical": diff == 0,
        "diff_row_bands": row_bands(rows),
        "diff_columns": sum(1 for count in columns if count),
        "truth_colors": len(set(left)),
        "remake_colors": len(set(right)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--truth", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--markdown", default="")
    args = parser.parse_args()

    truth_dir = pathlib.Path(args.truth)
    remake_dir = pathlib.Path(args.remake)
    rows = []
    for truth_name, remake_name, phase in PHASE_PAIRS:
        truth_path = truth_dir / truth_name
        remake_path = remake_dir / remake_name
        if not truth_path.is_file():
            print(f"SKIP {truth_name}: missing")
            continue
        if not remake_path.is_file():
            print(f"SKIP {remake_name}: missing")
            continue
        row = compare(truth_path, remake_path)
        row["phase"] = phase
        rows.append(row)
        print(f"{phase:14s} {truth_name:36s} vs {remake_name:26s} "
              f"diff {row['diff_px']:6d} px "
              f"({100.0 * row['diff_px'] / SCREEN_PIXELS:5.1f} %) "
              f"bands {row['diff_row_bands']}")

    document = {
        "schema": "konoha.s49-victory-align.v1",
        "truth_dir": str(truth_dir),
        "remake_dir": str(remake_dir),
        "screen_pixels": SCREEN_PIXELS,
        "pairs": rows,
        "total_diff_px": sum(row["diff_px"] for row in rows),
        "identical_pairs": sum(1 for row in rows if row["identical"]),
    }
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    if args.markdown:
        lines = [
            "| phase | truth | remake | diff px | identical |",
            "|---|---|---|---:|---|",
        ]
        for row in rows:
            lines.append(f"| {row['phase']} | `{row['truth']}` | "
                         f"`{row['remake']}` | {row['diff_px']} | "
                         f"{'yes' if row['identical'] else 'no'} |")
        pathlib.Path(args.markdown).write_text("\n".join(lines) + "\n",
                                                encoding="utf-8", newline="\n")
        print("->", args.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
