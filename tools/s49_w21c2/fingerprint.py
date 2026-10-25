#!/usr/bin/env python3
"""W21-C2: cross-side screen fingerprinting.

The original game publishes no telemetry at all, so the only thing both
sides can be compared on is **what is on the screen**.  This tool computes,
for every frame of both walks, a small set of region fingerprints and the
per-region change against the previous frame.  Two frames that share a
fingerprint are in the same UI mode.

Usage::

    python tools/s49_w21c2/fingerprint.py --original <dir> --remake <dir> \\
        --out build/w21-c2/fingerprints.json
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

from PIL import Image

STEP_RE = re.compile(r"^step-(\d+)-([A-Za-z]+)$")

# The battle HUD ("回合 N / 谁的回合") sits in the top band of the field.
REGIONS = {
    "hud_top": (0, 0, 240, 16),
    "hud_upper": (0, 16, 240, 32),
    "field": (0, 32, 240, 128),
    "field_low": (0, 128, 240, 160),
    "left": (0, 0, 60, 160),
    "right": (180, 0, 240, 160),
    "centre": (60, 0, 180, 160),
}


def frames(directory: pathlib.Path) -> list[tuple[int, str, pathlib.Path]]:
    out = []
    for png in sorted(directory.glob("step-*.png")):
        match = STEP_RE.match(png.stem)
        if match:
            out.append((int(match.group(1)), match.group(2), png))
    out.sort()
    return out


def crop_hash(image: Image.Image, box: tuple[int, int, int, int]) -> str:
    data = image.crop(box).tobytes()
    return hashlib.sha256(data).hexdigest()[:16]


def changed_pixels(a: Image.Image, b: Image.Image,
                   box: tuple[int, int, int, int]) -> int:
    region = a.crop(box).convert("RGB")
    other = b.crop(box).convert("RGB")
    left = region.tobytes()
    right = other.tobytes()
    count = 0
    for index in range(0, len(left), 3):
        if (abs(left[index] - right[index])
                + abs(left[index + 1] - right[index + 1])
                + abs(left[index + 2] - right[index + 2])) > 24:
            count += 1
    return count


def analyse(directory: pathlib.Path) -> list[dict]:
    rows = []
    previous = None
    for index, key, png in frames(directory):
        image = Image.open(png).convert("RGB")
        row = {
            "step": index,
            "key": key,
            "size": list(image.size),
            "whole_sha": hashlib.sha256(png.read_bytes()).hexdigest()[:16],
            "region_sha": {name: crop_hash(image, box)
                           for name, box in REGIONS.items()},
        }
        if previous is not None:
            row["changed_vs_prev"] = {
                name: changed_pixels(previous, image, box)
                for name, box in REGIONS.items()
            }
        rows.append(row)
        previous = image
    return rows


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=pathlib.Path, required=True)
    parser.add_argument("--remake", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()
    document = {
        "schema": "konoha.s49-screen-fingerprint.v1",
        "regions": {name: list(box) for name, box in REGIONS.items()},
        "original": analyse(args.original),
        "remake": analyse(args.remake),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=2)
                        + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
