"""W3: diff the shipped dialogue reveal mask table against a fresh measurement.

The shipped table lives in
``butano-sequel/game/include/konoha/battle_presentation_content.h`` and was
written back by ``tools/s49_z3_dialogue/sync_mask_table.py``.  This probe
re-measures the same mask from the original's own captures and reports every
entry that differs, so a stale table can never pass silently again.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

from PIL import Image

ROWS = (103, 127, 152)
WIDTH = 240
ENTRY = re.compile(
    r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\},\s*"
    r"//\s*capture\s+(\d+)\s+row\s+(\d+)")


def load(src: pathlib.Path, index: int, width: int):
    for suffix in ("in", "beat", "base"):
        png = src / f"step-{index:0{width}d}-{suffix}.png"
        if png.exists():
            with Image.open(png) as handle:
                return handle.convert("RGB")
    return None


def runs_of(cells):
    out = []
    for value in sorted(cells):
        if out and out[-1][1] == value - 1:
            out[-1][1] = value
        else:
            out.append([value, value])
    return out


def measure(src, settled_index, width, first, last):
    settled = load(src, settled_index, width).load()
    table = {}
    for index in range(first, last + 1):
        image = load(src, index, width)
        if image is None:
            break
        pixels = image.load()
        for y in ROWS:
            cells = {x for x in range(WIDTH)
                     if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24}
            runs = runs_of(cells)
            first_run = tuple(runs[0]) if runs else (WIDTH, 0)
            second_run = tuple(runs[1]) if len(runs) > 1 else (WIDTH, 0)
            table[(index, y)] = first_run + second_run
    return table


def shipped(header: pathlib.Path):
    text = header.read_text(encoding="utf-8")
    entries = {}
    for match in ENTRY.finditer(text):
        values = tuple(int(match.group(i)) for i in range(1, 5))
        entries[(int(match.group(5)), int(match.group(6)))] = values
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--header", required=True)
    parser.add_argument("--settled", type=int, default=276)
    parser.add_argument("--width", type=int, default=4)
    parser.add_argument("--first", type=int, default=259)
    parser.add_argument("--last", type=int, default=274)
    args = parser.parse_args()

    src = pathlib.Path(args.src)
    fresh = measure(src, args.settled, args.width, args.first, args.last)
    stored = shipped(pathlib.Path(args.header))

    print(f"fresh entries: {len(fresh)}  shipped entries: {len(stored)}")
    bad = 0
    for key in sorted(fresh):
        got = fresh[key]
        want = stored.get(key)
        mark = "ok " if want == got else "DIFF"
        if want != got:
            bad += 1
        print(f"  {mark} capture {key[0]:04d} row {key[1]:3d}: "
              f"fresh={got} shipped={want}")
    print(f"differing entries: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
