#!/usr/bin/env python3
"""Does the remake's own graphics folder reproduce the original's screens?

Two questions, one script:

``dialogue``
    The original's post-battle dialogue is seven screens, each built from three
    background layers (``_bottom`` = scene + portrait, ``_middle`` = empty,
    ``_top`` = dialogue box with the line baked in).  The remake ships eleven
    such layer triples.  This mode composites every triple and scores it
    against every original page, so "are the assets right?" becomes a number.

``taskmenu``
    The original's task menu is the world map plus two panels.  This mode
    decomposes a target frame into (map layer, ui layer, unknown region) by
    asking, per pixel, which layer the truth agrees with.

The transparent colour of a layer is the one the original leaves blank; it is
``--transparent`` (white by default) because that is how the extracted layers
store "nothing here".
"""

from __future__ import annotations

import argparse
import json
import pathlib

from PIL import Image

WIDTH = 240
HEIGHT = 160
SCREEN_PIXELS = WIDTH * HEIGHT


def layer(path: pathlib.Path) -> list:
    image = Image.open(path).convert("RGB")
    return list(image.crop((0, 0, WIDTH, HEIGHT)).get_flattened_data())


def screen(path: pathlib.Path) -> list:
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise SystemExit(f"{path} is {image.size}")
    return list(image.get_flattened_data())


def diff(a: list, b: list) -> int:
    return sum(1 for x, y in zip(a, b) if x != y)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--mode", choices=["dialogue", "taskmenu"], required=True)
    parser.add_argument("--pages", action="append", default=[],
                        help="original dialogue page PNG (dialogue mode)")
    parser.add_argument("--target", default="", help="task menu frame")
    parser.add_argument("--map-layer", default="")
    parser.add_argument("--ui-layer", default="")
    parser.add_argument("--asset-count", type=int, default=11)
    parser.add_argument("--transparent", type=int, nargs=3, default=[255, 255, 255])
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    graphics = pathlib.Path(args.graphics)
    transparent = tuple(args.transparent)

    if args.mode == "dialogue":
        truths = [(pathlib.Path(p), screen(pathlib.Path(p)))
                  for p in args.pages]
        table = []
        for number in range(1, args.asset_count + 1):
            names = {
                role: graphics / f"scenario_41_postbattle_dialogue_{number}_{role}.bmp"
                for role in ("bottom", "middle", "top")
            }
            if not names["bottom"].is_file():
                continue
            bottom = layer(names["bottom"])
            top = layer(names["top"])
            composed = list(bottom)
            for index, pixel in enumerate(top):
                if pixel != transparent:
                    composed[index] = pixel
            scores = [{"page": path.name, "diff_px": diff(truth, composed)}
                      for path, truth in truths]
            best = min(scores, key=lambda item: item["diff_px"])
            table.append({"asset": number, "best": best, "scores": scores})
            print(f"asset {number:2d}  best {best['diff_px']:6d} px  "
                  f"({best['page']})   " +
                  " ".join(f"{s['diff_px']:6d}" for s in scores))
        if args.out:
            out = pathlib.Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8", newline="\n")
            print("->", out)
        return 0

    truth = screen(pathlib.Path(args.target))
    map_layer = layer(graphics / (args.map_layer + ".bmp"))
    ui_layer = layer(graphics / (args.ui_layer + ".bmp"))
    both = only_map = only_ui = neither = 0
    unknown = []
    for index, (t, m, u) in enumerate(zip(truth, map_layer, ui_layer)):
        if t == m and t == u:
            both += 1
        elif t == m:
            only_map += 1
        elif t == u:
            only_ui += 1
        else:
            neither += 1
            unknown.append(index)
    bbox = None
    if unknown:
        xs = [i % WIDTH for i in unknown]
        ys = [i // WIDTH for i in unknown]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
    result = {
        "target": str(args.target),
        "map_layer": args.map_layer,
        "ui_layer": args.ui_layer,
        "truth_equals_both": both,
        "truth_equals_map_only": only_map,
        "truth_equals_ui_only": only_ui,
        "truth_equals_neither": neither,
        "unknown_bbox": bbox,
        "diff_map_only": diff(truth, map_layer),
    }
    print(json.dumps(result, indent=1))
    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
