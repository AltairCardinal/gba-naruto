"""Scratch: the dialogue signature sequence with a window end."""
from __future__ import annotations

import json
import pathlib
import sys


def main() -> int:
    path = pathlib.Path(sys.argv[1])
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
    data = json.loads(path.read_text(encoding="utf-8"))
    frames = data["frames"]
    sequence = []
    for name in sorted(frames):
        index = int(name.split("-")[1])
        if index > last:
            break
        frame = frames[name]
        if frame["scene"] != "dialogue":
            if sequence:
                break
            continue
        sequence.append((index, frame["bright_share"]))
    distinct = []
    for index, value in sequence:
        if not distinct or distinct[-1][1] != value:
            distinct.append((index, value))
    print(f"frames={len(sequence)} distinct={len(distinct)} "
          f"first={sequence[0][0] if sequence else '-'} "
          f"last={sequence[-1][0] if sequence else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
