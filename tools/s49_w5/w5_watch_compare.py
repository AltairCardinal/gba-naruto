#!/usr/bin/env python3
"""W5 -- price the title-card watch frames against the original's two poses.

The original's 开战 title card shows **two** poses: original step 9 (pose 1)
and original step 10 (pose 2).  The watch runs the card with no input at all
and screenshots it every N frames.  This script prices every watch frame
against pose 1 and pose 2 so the question "does this side ever render the
other side's pose?" is answered by a number.

Usage
-----
    python tools/s49_w5/w5_watch_compare.py \
        --original-capture build/s49-package-u3-final/work/s49-report/capture-original \
        --remake-capture   build/s49-package-u3-final/work/s49-report/capture-remake \
        --watch build/s49-wave18/w5/watch-original build/s49-wave18/w5/watch-remake
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FIELD_AREA = (0, 0, 240, 128)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-capture", required=True)
    parser.add_argument("--remake-capture", required=True)
    parser.add_argument("--watch", nargs="+", required=True)
    parser.add_argument("--poses", default="step-09-A.png,step-10-A.png")
    parser.add_argument("--reference", default=None,
                        help="capture dir for the pose pictures "
                             "(default: original capture)")
    args = parser.parse_args()

    original = pathlib.Path(args.original_capture)
    remake = pathlib.Path(args.remake_capture)
    reference = pathlib.Path(args.reference) if args.reference else original
    pose_names = [n for n in args.poses.split(",") if n]
    poses = {name: load_rgb(reference / name) for name in pose_names}

    for watch_dir in args.watch:
        watch = pathlib.Path(watch_dir)
        shots = sorted(watch.glob("f*.png"))
        if not shots:
            print(f"{watch}: no screenshots")
            continue
        print()
        print("=" * 78)
        print(watch)
        print("=" * 78)
        header = "  ".join(f"{name:>22}" for name in pose_names)
        print(f"{'frame':<12}{header}   winner")
        for shot in shots:
            image = load_rgb(shot)
            cells = []
            for name in pose_names:
                count, _ = diff_mask(poses[name], image, FIELD_AREA)
                cells.append(count)
            winner = pose_names[cells.index(min(cells))]
            print("  {:<12}".format(shot.name)
                  + "  ".join(f"{value:>22}" for value in cells)
                  + f"   {winner}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
