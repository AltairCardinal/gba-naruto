#!/usr/bin/env python3
"""Consecutive-frame difference inside one walk: which beats are settled and
which are moving (camera pan / typewriter / fade)?"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FIELD = (0, 0, 240, 128)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--box", default="0,0,240,128")
    args = parser.parse_args()
    box = tuple(int(v) for v in args.box.split(","))
    directory = pathlib.Path(args.dir)
    names = sorted(n for n in os.listdir(directory)
                   if n.startswith("step-") and n.endswith(".png"))
    images = {n: load_rgb(directory / n) for n in names}
    print(f"{'frame':<18}{'vs previous':>12}")
    for index, name in enumerate(names):
        if index == 0:
            print(f"{name:<18}{'-':>12}")
            continue
        count, _ = diff_mask(images[names[index - 1]], images[name], box)
        print(f"{name:<18}{count:>12}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
