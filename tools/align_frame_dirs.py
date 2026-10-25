#!/usr/bin/env python3
"""Cross-align two frame captures: for every frame on the left, find the frame
on the right that matches it best.

Index-aligned comparison is not enough.  A capture is a walk through a game,
and two runs of the same walk can be offset by a frame or two (a fade that
started one frame earlier, a different settle count).  Comparing by index then
reports a huge difference for frames that are actually the same moment.

This prints the full distance matrix so the offset is visible instead of
guessed, which is what the fidelity work needs before it can judge a frame.
"""

from __future__ import annotations

import argparse
import pathlib

from PIL import Image


def pixels(path: pathlib.Path) -> bytes:
    return Image.open(path).convert("RGB").tobytes()


def distance(a: bytes, b: bytes) -> int:
    return sum(1 for i in range(0, len(a), 3) if a[i:i + 3] != b[i:i + 3])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("left", type=pathlib.Path)
    ap.add_argument("right", type=pathlib.Path)
    args = ap.parse_args()

    left = {p.name: pixels(p) for p in sorted(args.left.glob("step-*.png"))}
    right = {p.name: pixels(p) for p in sorted(args.right.glob("step-*.png"))}
    if not left or not right:
        print("ERR no frames found")
        return 2

    header = "".join(f"{n[5:-4]:>9}" for n in right)
    print(f"{'mine':<18}{header}")
    best = {}
    for lname, la in left.items():
        row = {rname: distance(la, ra) for rname, ra in right.items()}
        winner = min(row, key=row.get)
        best[lname] = (winner, row[winner])
        cells = "".join(f"{row[n]:>9}" for n in right)
        print(f"{lname:<18}{cells}")
    print()
    print("best match per left frame:")
    for lname, (winner, value) in best.items():
        print(f"  {lname:<18} -> {winner:<18} {value} px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
