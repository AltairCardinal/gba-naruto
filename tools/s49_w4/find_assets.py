#!/usr/bin/env python3
"""Search the remake's own ``graphics/`` folder for the layers that reproduce
the original's settlement screens.

The wave-18 / W4 lane has two full-screen residuals (post-battle dialogue and
task menu).  Before blaming the product for "missing art", the cheap
question is: *does the remake already ship the layers that would make the
original's screen exactly?*  If yes the residual is a wiring defect; if no it
is an asset gap and the fix has to invent art.

The tool therefore does an exhaustive search:

* every ``*.bmp`` under ``graphics/`` that Butano treats as a regular
  background is a candidate layer,
* every candidate is tried at every visible-window offset ``(0..16, 0..16)``
  inside its 256x256 tilemap,
* every candidate is scored against every target screen,
* the best matches are printed, per target, with the residual in pixels.

Usage::

    python tools/s49_w4/find_assets.py --graphics <graphics dir> \
        --target <png> [--target <png> ...] [--top 8] [--out report.json]
"""

from __future__ import annotations

import argparse
import json
import pathlib

from PIL import Image

WIDTH = 240
HEIGHT = 160
SCREEN_PIXELS = WIDTH * HEIGHT


def load_rgb(path: pathlib.Path) -> list:
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise SystemExit(f"{path} is {image.size}, expected {(WIDTH, HEIGHT)}")
    return list(image.get_flattened_data())


def candidates(graphics: pathlib.Path):
    for path in sorted(graphics.glob("*.bmp")):
        try:
            image = Image.open(path)
        except OSError:
            continue
        if image.size[0] < WIDTH or image.size[1] < HEIGHT:
            continue
        yield path, image.convert("RGB")


def windows(image: Image.Image):
    """Every 240x160 window of a layer, with its offset."""
    max_x = image.size[0] - WIDTH
    max_y = image.size[1] - HEIGHT
    for y in range(0, max_y + 1):
        for x in range(0, max_x + 1):
            yield (x, y), list(image.crop((x, y, x + WIDTH, y + HEIGHT))
                               .get_flattened_data())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    graphics = pathlib.Path(args.graphics)
    targets = [(pathlib.Path(t), load_rgb(pathlib.Path(t)))
               for t in args.target]

    best = [[] for _ in targets]
    for path, image in candidates(graphics):
        for (x, y), window in windows(image):
            for (target_path, target), record in zip(targets, best):
                diff = sum(1 for a, b in zip(target, window) if a != b)
                record.append((diff, path.stem, x, y))

    document = []
    for (target_path, _), record in zip(targets, best):
        record.sort(key=lambda item: item[0])
        print(f"=== {target_path.name}")
        for diff, name, x, y in record[:args.top]:
            print(f"    {diff:6d} px   {name} @ ({x},{y})")
        document.append({
            "target": str(target_path),
            "best": [{"diff_px": diff, "asset": name, "x": x, "y": y}
                     for diff, name, x, y in record[:args.top]],
        })

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
