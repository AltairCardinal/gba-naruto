#!/usr/bin/env python3
"""Gate: two consecutive captured frames may only be pixel identical at the
outline wave's flat spots.

The original ROM rewrites the unit's OBJ palette index 15 -- the one pixel
outline -- on **every** frame, so two neighbouring frames differ by the
outline colour.  The wave is quantised to sixteen shades, so the darkest
shade (cycle positions 9 and 10) and the brightest one (positions 25 and 26)
each span two consecutive positions; when the pose does not change there, the
original's own frame repeats.

Measured on the original's 200 frame idle sweep (100 GBA frames, the local
probe writes every GBA frame twice): 4 identical consecutive GBA frames,
**exactly** at the phase pairs 9->10 and 25->26.

So the rule is not "never identical" but:

    two consecutive frames may only be identical when the outline wave's
    colour repeats, i.e. at the wave's flat spots.

How a flat spot is recognised
------------------------------
Two ways, and the tool uses the better one that is available:

* **the outline shade** (default, no extra input needed): the outline is the
  only colour of the shape ``(0, g, g)`` in the unit's pixel region, so the
  shade of a frame says whether it sits on a flat spot (shade 1 or 31).  Two
  conditions have to hold for a repeat to be excused: the capture has to show
  the outline wave **actually animating** (more than one shade), and the
  repeated frame's own shade has to be a flat spot shade.  A capture whose
  outline never changes is not "at a flat spot", it is *frozen*, and every
  repeat it produces is a defect.
* **the pose identification** (``--pose``): the phase map of the dense sweep,
  which names the phase pair the repeat happened at.  This is the
  authoritative one, because it does not have to guess which shade the frame
  was drawn with.

Usage::

    # the walk capture: the samples are 47 GBA frames apart, so they never
    # land on a flat spot and every identical pair is a defect
    python tools/s49_idle_frame_repeat.py \
        --original build/s49-report/capture-original \
        --remake build/s49-report/capture-remake \
        --out build/s49-idle/frame-repeat-check.json

    # the dense original sweep: the flat spots are allowed, and the pose map
    # names them
    python tools/s49_idle_frame_repeat.py --dir build/s49-logic/original-idle-sweep \
        --glob 'frame-*.png' --stride 2 --pose build/s49-idle/original-sweep-pose.json \
        --out build/s49-idle/original-repeat-check.json

    # the dense original sweep without the pose map: the outline shade alone
    # has to decide
    python tools/s49_idle_frame_repeat.py --dir build/s49-logic/original-idle-sweep \
        --glob 'frame-*.png' --stride 2 \
        --out build/s49-idle/original-repeat-shade-check.json
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s49_fidelity_report.pixels import load_rgb  # noqa: E402
from s49_fidelity_report.staticframes import (  # noqa: E402
    STATIC_RULE, check_capture,
)

DEFAULT_ORIGINAL = pathlib.Path(
    r"D:\Github\gba-naruto\build\s49-report\capture-original")
DEFAULT_REMAKE = pathlib.Path(
    r"D:\Github\gba-naruto\build\s49-report\capture-remake")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--original", type=pathlib.Path, default=DEFAULT_ORIGINAL)
    parser.add_argument("--remake", type=pathlib.Path, default=DEFAULT_REMAKE)
    parser.add_argument("--dir", type=pathlib.Path,
                        help="check one directory instead of the two sides")
    parser.add_argument("--glob", default="step-*.png",
                        help="the frame file pattern (default step-*.png)")
    parser.add_argument("--stride", type=int, default=1,
                        help="take every n-th frame (the local probe writes "
                             "every GBA frame twice)")
    parser.add_argument("--pose", type=pathlib.Path,
                        help="a pose identification, to tell a wave flat spot "
                             "from a frozen frame")
    parser.add_argument("--out", type=pathlib.Path)
    args = parser.parse_args()

    poses = None
    if args.pose:
        if not args.pose.is_file():
            print(f"missing the pose identification: {args.pose}",
                  file=sys.stderr)
            return 2
        poses = json.loads(args.pose.read_text(encoding="utf-8"))["sequence"]

    targets = []
    if args.dir:
        targets.append(("directory", args.dir))
    else:
        targets.append(("original", args.original))
        targets.append(("remake", args.remake))

    results = {}
    failed = False
    for role, directory in targets:
        if not directory.is_dir():
            print(f"missing the capture directory: {directory}",
                  file=sys.stderr)
            return 2
        paths = sorted(directory.glob(args.glob))
        images = {path.name: load_rgb(path) for path in paths}
        order = [path.name for path in paths]
        results[role] = check_capture(images, order, stride=args.stride,
                                      poses=poses)
        report = results[role]
        print(f"{role}: {report['frames']} frames, "
              f"{report['consecutive_identical_pairs']} consecutive identical "
              f"pairs, {report['unexpected_pairs']} unexpected")
        print(f"  outline shades seen: {report['distinct_outline_shades']} "
              f"(the wave {'animates' if report['outline_wave_animates'] else 'never changes'})")
        for pair in report["pairs"]:
            flag = "flat spot" if pair["wave_flat_spot"] else "UNEXPECTED"
            print(f"  {pair['previous']} == {pair['current']} "
                  f"({pair['sha256'][:8]}) {flag} -- {pair['reason']}")
        if report["unexpected_pairs"]:
            failed = True

    payload = {
        "rule": STATIC_RULE,
        "criterion": ("the outline shade (default) or the pose identification "
                      "(--pose) decides whether a repeat sits on a wave flat "
                      "spot"),
        "results": results,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    if failed:
        print("FAIL: at least one capture repeats a frame outside the "
              "wave's flat spots", file=sys.stderr)
        return 1
    print("OK: every repeated frame is a wave flat spot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
