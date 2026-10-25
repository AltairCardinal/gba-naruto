"""Rewrite the mask table inside the remake's content header.

The table is the measured mask of the original's dialogue box reveal; it is
generated from the original's captured frames so the header never carries a
hand typed number.

    python tools/s49_z3_dialogue/sync_mask_table.py \
        build/s49-pairing/walk5/dense-original 0276
"""
from __future__ import annotations

import pathlib
import re
import sys

from PIL import Image

HEADER = pathlib.Path(
    "D:/Shell/Github/gba-naruto-butano/butano-sequel/game/include/konoha/"
    "battle_presentation_content.h")
ROWS = (103, 127, 152)
WIDTH = 240
BEGIN = "    {   4, 239,   0,   0 },  // capture 259 row 103"
END = "    {   0,   0,   0,   0 },  // capture 274 row 152"


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


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    settled_index = int(sys.argv[2])
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    first = int(sys.argv[4]) if len(sys.argv) > 4 else 259
    last = int(sys.argv[5]) if len(sys.argv) > 5 else 274
    settled = load(src, settled_index, width).load()
    lines = []
    for index in range(first, last + 1):
        image = load(src, index, width)
        if image is None:
            break
        pixels = image.load()
        for y in ROWS:
            cells = {x for x in range(WIDTH)
                     if max(pixels[x, y]) < 24 and max(settled[x, y]) >= 24}
            runs = runs_of(cells)
            first_run = runs[0] if runs else (240, 0)
            second_run = runs[1] if len(runs) > 1 else (240, 0)
            lines.append(f"    {{ {first_run[0]:3d}, {first_run[1]:3d}, "
                         f"{second_run[0]:3d}, {second_run[1]:3d} }},"
                         f"  // capture {index} row {y}")
    text = HEADER.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(BEGIN) + ".*?" + re.escape(END),
                          re.DOTALL)
    if not pattern.search(text):
        print("ERR the table markers were not found")
        return 1
    text = pattern.sub("\n".join(lines), text, count=1)
    HEADER.write_text(text, encoding="utf-8", newline="\n")
    print(f"rewrote {len(lines)} table rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
