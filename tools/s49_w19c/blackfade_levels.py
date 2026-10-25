#!/usr/bin/env python3
"""Print the run length encoding of the black field events of a capture.

Why this exists
---------------
``tools/s49_blackfade/blackfade_report.py`` reports the *segments* (fade-out /
black / fade-in) of a black field event, but not how long every single
brightness step lasted.  The question "which of the twelve fade steps are one
GBA frame too long?" needs that, and the answer decides whether the extra
frames are a *timing constant* problem (``battle_black_field_timing.h``) or a
*rendering* problem (the star mask's level change does not fit into one scene
frame, ``battle_black_field_star_mask.h``).

The run length encoding of the event's frames answers it: a step that is
visible for 4 capture frames instead of 2 is a step whose level change was not
committed within one frame.

Usage::

    python tools/s49_w19c/blackfade_levels.py \
        --frames build/w19-c/blackfade-base/frames \
        --event 6
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--frames", type=pathlib.Path, required=True)
    parser.add_argument("--report", type=pathlib.Path, default=None,
                        help="blackfade.json of the same capture (optional)")
    parser.add_argument("--event", type=int, default=0,
                        help="event index (1 based); 0 = every event")
    args = parser.parse_args()

    files = sorted(args.frames.glob("frame-*.png"))
    if not files:
        print("ERR no frames", file=sys.stderr)
        return 2

    hashes = [sha256_file(path) for path in files]

    events: list[tuple[int, int]] = []
    start = None
    for index, digest in enumerate(hashes):
        black = digest.startswith("47fbde60709a2768")
        if black and start is None:
            start = index
        elif not black and start is not None:
            events.append((start, index - 1))
            start = None
    if start is not None:
        events.append((start, len(hashes) - 1))

    # The black runs alone do not delimit the fade segments, so the events are
    # taken from the report when it is available.
    if args.report and args.report.is_file():
        report = json.loads(args.report.read_text(encoding="utf-8"))
        events = []
        for event in report.get("events", []):
            first = int(event["first_frame"].split("-")[-1].split(".")[0])
            last = int(event["last_frame"].split("-")[-1].split(".")[0])
            events.append((first, last))

    selected = events if args.event == 0 else [events[args.event - 1]]
    for number, (first, last) in enumerate(selected, start=1):
        print(f"event {number}: frames {first + 1}..{last + 1} "
              f"({last - first + 1} frames)")
        index = first
        while index <= last:
            end = index
            while end + 1 <= last and hashes[end + 1] == hashes[index]:
                end += 1
            run = end - index + 1
            marker = "  <== LONG" if run > 2 else ""
            print(f"  frames {index + 1}..{end + 1}: {run} frame(s) "
                  f"sha {hashes[index][:12]}{marker}")
            index = end + 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
