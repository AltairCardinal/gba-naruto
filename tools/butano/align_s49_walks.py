#!/usr/bin/env python3
"""Re-derive the step correspondence between two walks after a flow change.

When the remake's flow order changes, the step numbers stop lining up with the
original's, and a comparison that pairs them by index measures the pairing
rather than the product.  This tool builds the full cross product of the two
walks and reports, for every original step, the remake step that matches it
best.

The comparison uses a small grayscale signature of the whole frame, so it is
cheap enough to run over every pair, and it is deliberately not restricted to
any region: the whole frame has to agree for two steps to be the same moment.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SIGNATURE_SIZE = (60, 40)


def signature(path: Path) -> list[int]:
    with Image.open(path) as image:
        small = image.convert("L").resize(SIGNATURE_SIZE, Image.BILINEAR)
    return list(small.get_flattened_data())


def steps(directory: Path) -> list[Path]:
    return sorted(directory.glob("step-*.png"))


def distance(left: list[int], right: list[int]) -> int:
    return sum(abs(a - b) for a, b in zip(left, right))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--remake", type=Path, required=True)
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        help="how many remake candidates to report per original step",
    )
    args = parser.parse_args()

    original = steps(args.original)
    remake = steps(args.remake)
    if not original or not remake:
        print("error: one of the walks is empty", flush=True)
        return 1
    original_signatures = [signature(path) for path in original]
    remake_signatures = [signature(path) for path in remake]

    for index, path in enumerate(original):
        ranked = sorted(
            (
                (distance(original_signatures[index], remake_signatures[other]), other)
                for other in range(len(remake))
            )
        )
        best = ranked[0]
        margin = best[0] - ranked[1][0] if len(ranked) > 1 else best[0]
        candidates = ", ".join(
            f"R{remake[other].name.split('-')[1].split('.')[0]}({value})"
            for value, other in ranked[: args.top]
        )
        print(
            f"O{path.name.split('-')[1].split('.')[0]}: {candidates} "
            f"[margin {margin}]"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
