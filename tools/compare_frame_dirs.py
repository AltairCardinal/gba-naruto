#!/usr/bin/env python3
"""Compare two directories of frame captures pixel by pixel.

Used to answer two different questions:

* **Is a capture reproducible?**  Record the same walk twice (or on another
  machine) and check that every frame matches the recorded one.  Byte equality
  is reported separately from pixel equality, because the PNG *encoder* may
  differ between emulator builds while the rendered image is identical.

* **What is still different?**  For the remake-versus-original comparison this
  gives the per-frame pixel difference, which is the number the fidelity work
  is judged on.  A per-frame list (not just the minimum) is what catches
  "one frame got better, another got worse".

Usage::

    python tools/compare_frame_dirs.py A B
    python tools/compare_frame_dirs.py A B --field-area 0 0 240 128
    python tools/compare_frame_dirs.py A B --json build/compare.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("ERR Pillow is required (pip install pillow)", file=sys.stderr)
    raise SystemExit(2)


def compare_pair(left: pathlib.Path, right: pathlib.Path,
                 area: tuple[int, int, int, int] | None) -> dict:
    left_bytes = left.read_bytes()
    right_bytes = right.read_bytes()
    a = Image.open(left).convert("RGB")
    b = Image.open(right).convert("RGB")
    result = {
        "frame": left.name,
        "byte_equal": left_bytes == right_bytes,
        "left_size": list(a.size),
        "right_size": list(b.size),
    }
    if a.size != b.size:
        result["pixel_diff"] = None
        result["note"] = "frame sizes differ"
        return result
    if area:
        x, y, w, h = area
        a = a.crop((x, y, x + w, y + h))
        b = b.crop((x, y, x + w, y + h))
    pa, pb = a.tobytes(), b.tobytes()
    diff = 0
    for i in range(0, len(pa), 3):
        if pa[i:i + 3] != pb[i:i + 3]:
            diff += 1
    result["pixel_diff"] = diff
    result["total_pixels"] = (a.size[0] * a.size[1])
    result["percent"] = round(100.0 * diff / max(1, a.size[0] * a.size[1]), 4)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("left", type=pathlib.Path)
    ap.add_argument("right", type=pathlib.Path)
    ap.add_argument("--field-area", nargs=4, type=int, default=None,
                    metavar=("X", "Y", "W", "H"),
                    help="compare only this rectangle (e.g. 0 0 240 128 to skip the HUD)")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    args = ap.parse_args()

    if not args.left.is_dir() or not args.right.is_dir():
        print("ERR both sides must be directories", file=sys.stderr)
        return 2
    area = tuple(args.field_area) if args.field_area else None

    rows = []
    for left in sorted(args.left.glob("*.png")):
        right = args.right / left.name
        if not right.is_file():
            rows.append({"frame": left.name, "missing_on_right": True})
            continue
        rows.append(compare_pair(left, right, area))

    matched = sum(1 for r in rows if r.get("pixel_diff") == 0)
    byte_equal = sum(1 for r in rows if r.get("byte_equal"))
    diffs = [r["pixel_diff"] for r in rows if isinstance(r.get("pixel_diff"), int)]

    print(f"frames compared : {len(rows)}")
    print(f"pixel-identical : {matched}")
    print(f"byte-identical  : {byte_equal}")
    if diffs:
        print(f"pixel diff      : min {min(diffs)}  max {max(diffs)}  sum {sum(diffs)}")
    print()
    for row in rows:
        if row.get("missing_on_right"):
            print(f"  {row['frame']:<28} MISSING on the right")
            continue
        if row.get("pixel_diff") is None:
            print(f"  {row['frame']:<28} {row.get('note', 'not comparable')}")
            continue
        flag = "OK " if row["pixel_diff"] == 0 else "DIFF"
        print(f"  {row['frame']:<28} {flag} {row['pixel_diff']:>6} px "
              f"({row['percent']}%)  byte-equal={row['byte_equal']}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"rows": rows, "pixel_identical": matched,
                        "byte_identical": byte_equal}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print("\nwrote", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
