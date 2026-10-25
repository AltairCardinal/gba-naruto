#!/usr/bin/env python3
"""W5 -- check the watch frames against the bench captures over the FULL frame.

``w5_watch_compare.py`` prices the field area (240x128) because that is what
the judgement bench prices.  This script repeats the comparison over the full
240x160 screen so that a claim like "byte identical" can be made honestly
about the whole picture, not just about the part the bench looks at.

Usage
-----
    python tools/s49_w5/w5_fullframe_check.py \
        --original-capture build/s49-package-u3-final/work/s49-report/capture-original \
        --remake-capture build/s49-package-u3-final/work/s49-report/capture-remake \
        --pairs "orig:step-10-A.png:build/s49-wave18/w5/watch-original/f0030.png" \
                "remake:step-13-A.png:build/s49-wave18/w5/pressa300/watch-remake/f0010.png"
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FULL_BOX = (0, 0, 240, 160)
FIELD_AREA = (0, 0, 240, 128)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-capture", required=True)
    parser.add_argument("--remake-capture", required=True)
    parser.add_argument("--pairs", nargs="+", required=True)
    args = parser.parse_args()

    for spec in args.pairs:
        label, left, right = spec.split(":")
        base = pathlib.Path(args.original_capture if label == "orig"
                            else args.remake_capture)
        left_image = load_rgb(base / left)
        right_image = load_rgb(right_path := pathlib.Path(right))
        field, _ = diff_mask(left_image, right_image, FIELD_AREA)
        full, _ = diff_mask(left_image, right_image, FULL_BOX)
        print("{:<7} {:<18} vs {:<52}  field={:<6} full={:<6}".format(
            label, left, str(right_path), field, full))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
