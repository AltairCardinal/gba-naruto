#!/usr/bin/env python3
"""Search every recorded frame of a walk for the bee sprite.

The S49 scenario data the remake ships does contain five 蜜蜂, so the question
is whether they ever reach the screen.  This scans a whole walk rather than a
single frame, which is the difference between "the bees are off camera" and
"the bees are not in the battle at all".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.butano.count_s49_bees import (  # noqa: E402
    BEE_BOXES,
    ORIGINAL_FRAME,
    _match_score,
    _samples,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--walk", type=Path, required=True)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="fraction of the bee's pixels that must match",
    )
    args = parser.parse_args()

    original = Image.open(ORIGINAL_FRAME).convert("RGB")
    needles = [original.crop(box) for box in BEE_BOXES]
    totals = [_samples(needle) for needle in needles]
    print(
        "scanning "
        f"{args.walk} against {len(needles)} bee sprites "
        f"({totals} distinctive pixels each)"
    )
    for path in sorted(args.walk.glob("step-*.png")):
        image = Image.open(path).convert("RGB")
        scores = [_match_score(image, needle) for needle in needles]
        hits = [
            index
            for index, (score, total) in enumerate(zip(scores, totals))
            if total and score >= total * args.threshold
        ]
        if hits:
            print(f"  {path.name}: bee(s) {hits} scores {scores}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
