#!/usr/bin/env python3
"""Print the black field truth table of a scan / trace receipt.

Usage::

    python tools/s49_blackfade/show_blackfade.py \
        build/s49-blackfade/original-entry-v2/blackfade.json \
        build/s49-blackfade/remake-entry/blackfade.json
"""

from __future__ import annotations

import json
import pathlib
import sys


def main(argv: list[str]) -> int:
    for item in argv:
        path = pathlib.Path(item)
        document = json.loads(path.read_text(encoding="utf-8"))
        print(f"== {path.parent.name}: {document['frame_count']} frames, "
              f"{document['event_count']} black field event(s)")
        for event in document["events"]:
            print(f"  event {event['event']}: {event['first_frame']} .. "
                  f"{event['last_frame']}  total {event['total_frames']} frame(s) "
                  f"({event['distinct_frames']} distinct)")
            print(f"     fade-out {event['fade_out_range']} "
                  f"({event['fade_out_frames']}f)")
            print(f"     black    {event['black_hold_range']} "
                  f"({event['black_hold_frames']}f) sha256 "
                  f"{event['first_black_sha256']}")
            print(f"     fade-in  {event['fade_in_range']} "
                  f"({event['fade_in_frames']}f)")
            print(f"     prev {event['previous_frame']} "
                  f"sha256 {event['previous_frame_sha256']} "
                  f"mean {event['previous_frame_mean']}")
            print(f"     next {event['next_frame']} "
                  f"sha256 {event['next_frame_sha256']} "
                  f"mean {event['next_frame_mean']}")
            print(f"     mean range {event['mean_min']} .. {event['mean_max']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
