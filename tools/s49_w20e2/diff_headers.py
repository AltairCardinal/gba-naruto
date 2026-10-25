#!/usr/bin/env python3
"""W20-E2: line-level diff of two generated headers (first N differing lines)."""

from __future__ import annotations

import difflib
import pathlib
import sys


def main() -> int:
    old = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").split("\n")
    new = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").split("\n")
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    print(f"old lines={len(old)} new lines={len(new)}")
    diff = list(
        difflib.unified_diff(old, new, "old", "new", n=1, lineterm="")
    )
    print(f"unified diff lines: {len(diff)}")
    for line in diff[:limit]:
        print(line[:400])
    if len(diff) > limit:
        print(f"... and {len(diff) - limit} more diff lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
