#!/usr/bin/env python3
"""Match the remake's post-battle dialogue BG layers against the original's pages.

The remake ships eleven dialogue page triples
(`scenario_41_postbattle_dialogue_<N>_{bottom,middle,top}`) as 256x256 8bpp
regular_bg maps whose content sits in the *top left* 240x160 window (that is
the window `create_bg(8, 48)` shows - see the codebase's own note in
`battle_runtime_scene.cpp`).

This probe answers: **which original page does each remake layer correspond
to?**  For every layer it computes the pixel difference against every
captured original page, restricted to the layer's own non-black content, so a
layer that carries only the forest is not penalised for the portrait the
original drew on another layer.

Usage:
    python tools/s49_w19b/dialogue_match.py --graphics <dir> \
        --orig-pages <dir> --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image


def load_rgb(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def layer_diff(layer: Image.Image, page: Image.Image):
    """Difference over the layer's own non-black content only."""
    lp, pp = layer.load(), page.load()
    total = 0
    counted = 0
    for y in range(160):
        for x in range(240):
            r, g, b = lp[x, y]
            if r + g + b <= 24:
                continue
            counted += 1
            if lp[x, y] != pp[x, y]:
                total += 1
    return total, counted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphics", required=True)
    parser.add_argument("--orig-pages", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--truth", default="")
    args = parser.parse_args()

    pages = {}
    for name in sorted(os.listdir(args.orig_pages)):
        if name.endswith(".png"):
            pages[name] = load_rgb(os.path.join(args.orig_pages, name))
    if args.truth:
        pages["TRUTH"] = load_rgb(args.truth)

    result = {"pages": sorted(pages), "layers": {}}
    for number in range(1, 12):
        for layer in ("bottom", "middle", "top"):
            name = "scenario_41_postbattle_dialogue_%d_%s" % (number, layer)
            path = os.path.join(args.graphics, name + ".bmp")
            if not os.path.exists(path):
                continue
            asset = load_rgb(path).crop((0, 0, 240, 160))
            scores = {}
            lit = 0
            for page_name, page in pages.items():
                diff, counted = layer_diff(asset, page)
                lit = max(lit, counted)
                scores[page_name] = diff
            best = min(scores.items(), key=lambda kv: kv[1])
            result["layers"][name] = {
                "content_px": lit,
                "best_page": best[0],
                "best_diff": best[1],
                "scores": scores,
            }
            print("%-46s content=%5d best=%-28s diff=%d"
                  % (name, lit, best[0], best[1]))

    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=1)
        handle.write("\n")
    print("wrote " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
