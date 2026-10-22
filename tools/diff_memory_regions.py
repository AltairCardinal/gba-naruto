#!/usr/bin/env python3
"""Find dense change regions between binary dumps of equal size."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--window", type=int, default=0x100)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    a = Path(args.before).read_bytes()
    b = Path(args.after).read_bytes()
    if len(a) != len(b):
        raise SystemExit("size mismatch")

    rows = []
    for off in range(0, len(a), args.window):
        aa = a[off : off + args.window]
        bb = b[off : off + args.window]
        diff = sum(x != y for x, y in zip(aa, bb))
        if diff:
            rows.append((diff, off))

    rows.sort(reverse=True)
    print(f"# Diff Summary: {args.before} -> {args.after}")
    print(f"- size: 0x{len(a):X}")
    print(f"- window: 0x{args.window:X}")
    print(f"- nonzero windows: {len(rows)}")
    print("")
    for diff, off in rows[: args.top]:
        print(f"- 0x{off:06X}: {diff} changed bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
