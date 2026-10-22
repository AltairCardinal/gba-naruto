#!/usr/bin/env python3
"""Measure the remake's move-range frame against the original's, pixel by pixel.

The S49 fidelity work pins one comparison: the remake's move-range frame
against the original's ``walk-original-a24/step-19-A.png``, over the
battlefield area (0, 0, 240, 128) -- the bottom 32 rows are the HUD, not the
map.  The number is the count of pixels that differ.

Two things make this worth a script rather than a one-off:

* the number has to be **reproducible** from the recordings, and
* a change to the overlay can easily make one frame better and another
  worse, so the report gives the **per frame** differences and not only the
  minimum.  The minimum is the headline number (the original's frame is
  matched at the step where the remake reaches the same game moment); the
  per frame list is the guard against "improve one frame, break the rest".

Usage::

    /usr/local/bin/python3 tools/butano/measure_s49_movegrid_baseline.py \\
        --walk artifacts/s49-remake-walk-20261021-v1

    /usr/local/bin/python3 tools/butano/measure_s49_movegrid_baseline.py \\
        --walk <dir> --json <out.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

#: The original's move-range frame.  It is the reference for every walk.
ORIGINAL_FRAME = (
    ROOT / "artifacts/s49-fidelity-20261019-v1/walk-original-a24/step-19-A.png"
)
#: The battlefield area.  The bottom 32 rows are the HUD, not the map.
FIELD_AREA = (0, 0, 240, 128)


class BaselineError(RuntimeError):
    """Raised when the evidence is missing or malformed."""


def _load(path: Path):
    from PIL import Image

    if not path.is_file():
        raise BaselineError(f"missing frame: {path}")
    image = Image.open(path).convert("RGB")
    if image.size != (240, 160):
        raise BaselineError(f"{path} is {image.size}, not a 240x160 GBA frame")
    return image.load()


def measure(walk: Path) -> dict[str, Any]:
    original = _load(ORIGINAL_FRAME)
    x0, y0, x1, y1 = FIELD_AREA
    frames: list[dict[str, Any]] = []
    for path in sorted(walk.glob("step-*.png")):
        remake = _load(path)
        differing = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                if original[x, y] != remake[x, y]:
                    differing += 1
        frames.append({"frame": path.name, "differing_pixels": differing})
    if not frames:
        raise BaselineError(f"no frames in {walk}")
    best = min(frames, key=lambda item: item["differing_pixels"])
    return {
        "schema": "konoha.s49-movegrid-baseline.v1",
        "walk": str(walk.relative_to(ROOT)),
        "original_frame": str(ORIGINAL_FRAME.relative_to(ROOT)),
        "field_area": list(FIELD_AREA),
        "baseline_pixels": best["differing_pixels"],
        "baseline_frame": best["frame"],
        "frames": frames,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--walk", required=True, help="the remake walk directory")
    parser.add_argument("--json", help="write the report to this path")
    args = parser.parse_args(argv)
    walk = Path(args.walk)
    if not walk.is_absolute():
        walk = ROOT / walk
    try:
        report = measure(walk)
    except BaselineError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        f"baseline={report['baseline_pixels']} "
        f"frame={report['baseline_frame']} walk={report['walk']}"
    )
    for frame in report["frames"]:
        print(f"  {frame['frame']}: {frame['differing_pixels']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
