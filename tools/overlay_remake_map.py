#!/usr/bin/env python3
"""What does the remake's overlay actually paint, cell by cell?

Reads a per-frame dump of the remake's BG2 tilemap and reports, per tile
index: how many cells carry it, and which of the remake's own tile kinds
that index belongs to (the kind boundaries come from
butano-sequel/game/include/konoha/battle_range_ui_style.h).

This is the "what is the remake doing" half of the overlay diff; the
"what should it do" half is the original's exported ground truth.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import struct
from collections import Counter

STYLE = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\battle_range_ui_style.h"
)


def remake_kinds() -> dict[int, str]:
    """Tile index -> kind, read out of the remake's own style header."""
    text = STYLE.read_text(encoding="utf-8", errors="replace")
    kinds = ["grid", "move", "attack_range", "cursor", "target", "blocked"]
    firsts = {}
    for kind in kinds:
        match = re.search(
            r"case\s+battle_range_ui_tile_kind::" + kind + r":\s*\n\s*first_tile = (\d+);",
            text)
        if match:
            firsts[kind] = int(match.group(1))
    # Each kind owns 8 tiles (4 x 2 per cell), except the first kind which
    # starts at tile 1.
    ordered = sorted(firsts.items(), key=lambda kv: kv[1])
    out: dict[int, str] = {}
    for index, (kind, first) in enumerate(ordered):
        last = ordered[index + 1][1] if index + 1 < len(ordered) else first + 8
        for tile in range(first, last):
            out[tile] = kind
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dump", type=pathlib.Path, required=True)
    args = ap.parse_args()

    kinds = remake_kinds()
    print("remake tile index -> kind (from battle_range_ui_style.h):")
    by_kind: dict[str, list[int]] = {}
    for tile, kind in kinds.items():
        by_kind.setdefault(kind, []).append(tile)
    for kind in sorted(by_kind, key=lambda k: min(by_kind[k])):
        print(f"  {kind:<12} tiles {sorted(by_kind[kind])}")

    raw = args.dump.read_bytes()
    cells = struct.unpack_from("<1024H", raw, 0)
    counts = Counter(cells)
    print(f"\n{args.dump.name}: {sum(1 for c in cells if c)} populated of 1024")
    print(f"{'tile':>6} {'count':>7}  kind")
    for tile, count in counts.most_common():
        if not tile:
            continue
        print(f"  0x{tile:04X} {count:>6}  {kinds.get(tile, '(not in style header)')}")

    # A rough map: how many cells of each kind, and the bounding shape.
    grid = ["" for _ in range(1024)]
    for index, cell in enumerate(cells):
        grid[index] = kinds.get(cell, "?") if cell else "."
    print("\nkind map (32x32 cells, one char each):")
    for row in range(32):
        print("  " + "".join(grid[row * 32:(row + 1) * 32]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
