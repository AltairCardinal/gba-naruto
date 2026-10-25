#!/usr/bin/env python3
"""Map the remake's background layers onto the original's settlement screens.

The original's post-battle dialogue is seven screens.  Each screen is built
from background layers that the remake's ``graphics/`` folder may already
contain (``scenario_41_postbattle_dialogue_N_{bottom,middle,top}``).  This
tool answers three questions with numbers:

1. **Scene layer**: for every original page, which asset's ``_bottom`` layer
   reproduces the top of that page (the forest plus the portrait) exactly, and
   at which visible-window offset?
2. **Box layer**: the same question for the dialogue box (the ``_top`` layer),
   whose line is baked into the image.
3. **Which pages have no asset at all** -- those are asset gaps, not wiring
   defects, and they set the lower bound on what this wave can close.

A perfect (0 px) score means the remake already ships the exact pixels.
"""

from __future__ import annotations

import argparse
import json
import pathlib

from PIL import Image

WIDTH = 240
HEIGHT = 160


def load(path: pathlib.Path) -> list:
    image = Image.open(path).convert("RGB")
    return list(image.get_flattened_data())


def windows(image: Image.Image):
    for y in range(0, image.size[1] - HEIGHT + 1):
        for x in range(0, image.size[0] - WIDTH + 1):
            yield (x, y), list(image.crop((x, y, x + WIDTH, y + HEIGHT))
                               .get_flattened_data())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--page", action="append", default=[],
                        help="original screen PNG (repeat, in page order)")
    parser.add_argument("--role", default="bottom",
                        choices=["bottom", "top", "middle"])
    parser.add_argument("--asset-count", type=int, default=11)
    parser.add_argument("--prefix", default="scenario_41_postbattle_dialogue_")
    parser.add_argument("--region", default="all", choices=["all", "top", "bottom"],
                        help="which part of the screen to compare")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    graphics = pathlib.Path(args.graphics)
    if args.region == "all":
        lo, hi = 0, HEIGHT
    elif args.region == "top":
        lo, hi = 0, 96
    else:
        lo, hi = 96, HEIGHT

    pages = []
    for path in args.page:
        pixels = load(pathlib.Path(path))
        pages.append((pathlib.Path(path).name, pixels[lo * WIDTH:hi * WIDTH]))

    table = []
    print(f"region rows {lo}..{hi - 1}, role={args.role}")
    for number in range(1, args.asset_count + 1):
        path = graphics / f"{args.prefix}{number}_{args.role}.bmp"
        if not path.is_file():
            continue
        image = Image.open(path).convert("RGB")
        best = []
        for (x, y), window in windows(image):
            window = window[lo * WIDTH:hi * WIDTH]
            for name, truth in pages:
                best.append((sum(1 for a, b in zip(truth, window) if a != b),
                             name, x, y))
        best.sort()
        unique = {}
        for score, name, x, y in best:
            unique.setdefault(name, (score, x, y))
        for name in sorted(unique, key=lambda n: unique[n][0]):
            score, x, y = unique[name]
            table.append({"asset": number, "role": args.role, "page": name,
                          "diff_px": score, "x": x, "y": y})
        print(f"asset {number:2d}: " + "  ".join(
            f"{n}:{unique[n][0]:5d}@({unique[n][1]},{unique[n][2]})"
            for n in sorted(unique, key=lambda n: unique[n][0])))

    print("\n=== per page, best asset for this role ===")
    summary = {}
    for name, _ in pages:
        rows = [r for r in table if r["page"] == name]
        if not rows:
            continue
        best = min(rows, key=lambda r: r["diff_px"])
        summary[name] = best
        print(f"{name:28s} best asset {best['asset']:2d}  diff {best['diff_px']:6d}"
              f"  @({best['x']},{best['y']})  "
              f"{'EXACT' if best['diff_px'] == 0 else 'no exact asset'}")
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"table": table, "summary": summary},
                                  ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
