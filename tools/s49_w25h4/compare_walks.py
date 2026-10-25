#!/usr/bin/env python3
"""Compare two captured walks frame by frame (sha256 of every PNG).

Used for the 8bpp no-op proof: the lane's baseline ROM (the shared tree's
overlay code) and the lane's H4 ROM must produce byte-identical frames.

Usage:
    python tools/s49_w25h4/compare_walks.py <dir-a> <dir-b>
"""
from __future__ import annotations

import hashlib
import pathlib
import sys


def frames(directory: pathlib.Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(directory.glob("step-*.png")):
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    a = frames(pathlib.Path(sys.argv[1]))
    b = frames(pathlib.Path(sys.argv[2]))
    names = sorted(set(a) | set(b))
    same = 0
    different: list[str] = []
    missing: list[str] = []
    for name in names:
        if name not in a or name not in b:
            missing.append(name)
            continue
        if a[name] == b[name]:
            same += 1
        else:
            different.append(name)
    print(f"frames A: {len(a)}  frames B: {len(b)}")
    print(f"identical: {same}/{len(names)}")
    if different:
        print("different:")
        for name in different:
            print(f"  {name}  A={a[name][:16]}  B={b[name][:16]}")
    if missing:
        print("missing on one side:")
        for name in missing:
            print(f"  {name}")
    return 0 if (not different and not missing) else 1


if __name__ == "__main__":
    raise SystemExit(main())
