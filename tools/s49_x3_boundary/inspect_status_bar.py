#!/usr/bin/env python3
"""Inspect the status bar of the recorded X3 walks (read-only helper).

It crops the bottom status bar of every recorded step, stacks the crops
vertically and enlarges them so a human (or a diff) can see which unit the
status bar follows.
"""

from __future__ import annotations

import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

WORK = REPO / "build" / "s49-x3-boundary"
BAR = (0, 144, 240, 160)


def main(argv: list[str]) -> int:
    which = argv[1] if len(argv) > 1 else "remake"
    if which == "remake":
        walk = next(WORK.glob("remake-walk-*"))
        pattern = "step-*.png"
    else:
        walk = next(WORK.glob("original-walk-*"))
        pattern = "step-*.png"
    crops = []
    for path in sorted(walk.glob(pattern)):
        image = Image.open(path).convert("RGB")
        crops.append((path.stem, image.crop(BAR)))
    if not crops:
        print("no frames")
        return 2
    width = max(c.size[0] for _, c in crops)
    height = sum(c.size[1] for _, c in crops)
    sheet = Image.new("RGB", (width, height), (0, 0, 0))
    y = 0
    for _, crop in crops:
        sheet.paste(crop, (0, y))
        y += crop.size[1]
    scale = 3
    sheet = sheet.resize((width * scale, height * scale), Image.NEAREST)
    out = REPO / "build" / "s49-x3-boundary" / ("status-%s.png" % which)
    sheet.save(out)
    print("steps: %s" % ", ".join(name for name, _ in crops))
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
