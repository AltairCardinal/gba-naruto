"""Scratch: the dialogue signature sequence of both sides.

The signature is the ``bright_share`` the pairing anchors use: the share of
"bright paper" pixels in the dialogue band.  This prints the distinct
signature values in order for the dialogue window of both sides.
"""
from __future__ import annotations

import json
import pathlib
import sys


def main() -> int:
    root = pathlib.Path(sys.argv[1])
    for side in ("original", "remake"):
        path = root / f"anchors-{side}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        frames = data["frames"]
        print(f"--- {side}: {len(frames)} frames ---")
        sequence = []
        for name in sorted(frames):
            frame = frames[name]
            if frame["scene"] != "dialogue":
                if sequence:
                    break
                continue
            sequence.append((name, frame["bright_share"]))
        distinct = []
        for name, value in sequence:
            if not distinct or distinct[-1][1] != value:
                distinct.append((name, value))
        print(f"dialogue frames={len(sequence)} distinct={len(distinct)}")
        for name, value in distinct:
            print(f"  {name} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
