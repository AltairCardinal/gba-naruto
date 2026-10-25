#!/usr/bin/env python3
"""Per-cell diagnostic for the W2 overlay family comparison.

Prints the map-space logical cell table (original family vs remake family)
for one moment and one remake VRAM dump, and classifies the differences.

Usage::

    python tools/s49_w2/cell_diff.py --vram-dir <dir> --moment field-frame-v1
    python tools/s49_w2/cell_diff.py --vram-dir <dir> --moment field-frame-v1 \\
        --frame step-25-A.state.vram-0000.bin
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

from compare_overlay_families import (  # noqa: E402
    find_overlay_map,
    remake_entry_map,
    remake_logical_cells,
    remake_terrain,
    original_map_cells,
    REMAKE_MAP_ANCHOR,
)


def load_remake(vram_path: pathlib.Path, terrain):
    vram = vram_path.read_bytes()
    base = find_overlay_map(vram, terrain=terrain)
    if base < 0:
        return {}
    entry_map = remake_entry_map(vram, base)
    return remake_logical_cells(entry_map, *REMAKE_MAP_ANCHOR)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--moment", default="field-frame-v1")
    ap.add_argument("--frame", default=None,
                    help="the dump to use; default = the best matching one")
    ap.add_argument("--show-blank", action="store_true")
    args = ap.parse_args()

    terrain = remake_terrain()
    original = original_map_cells(args.moment)
    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))

    best = None
    for path in dumps:
        cells = load_remake(path, terrain)
        lit = len(cells)
        overlap = sum(1 for key, fam in cells.items()
                      if original.get(key) == fam)
        if best is None or (overlap, -abs(lit - len(original))) > best[0]:
            best = ((overlap, -abs(lit - len(original))), path, cells)
    if args.frame:
        path = args.vram_dir / args.frame
        cells = load_remake(path, terrain)
        best = (None, path, cells)
    assert best is not None
    print(f"frame {best[1].name}  original lit {len(original)}  "
          f"remake lit {len(best[2])}")

    # the terrain class per battle cell, for the blocked-set check
    blocked = {(bx, by)
               for by, row in enumerate(terrain)
               for bx, value in enumerate(row) if value != 0}

    rows = []
    for key in sorted(set(original) | set(best[2])):
        a = original.get(key, "blank")
        b = best[2].get(key, "blank")
        if a == "blank" and b == "blank":
            continue
        rows.append((key[0], key[1], a, b))

    print(f"{'lx':>3} {'ly':>3}  {'orig':<11} {'remake':<11} note")
    for lx, ly, a, b in rows:
        note = ""
        if a != "blank" and b != "blank":
            note = "MISMATCH" if a != b else ""
        elif a != "blank":
            note = "ORIGINAL-ONLY"
        else:
            note = "REMAKE-ONLY"
        if note == "MISMATCH" or args.show_blank:
            print(f"{lx:>3} {ly:>3}  {a:<11} {b:<11} {note}")
    # summary
    only_o = sum(1 for lx, ly, a, b in rows if a != "blank" and b == "blank")
    only_r = sum(1 for lx, ly, a, b in rows if a == "blank" and b != "blank")
    mism = sum(1 for lx, ly, a, b in rows
               if a != "blank" and b != "blank" and a != b)
    print(f"\nsummary: original-only {only_o}  remake-only {only_r}  "
          f"mismatches {mism}")

    # group the differences by (row, kind) to expose the patterns
    print("\n--- differences grouped ---")
    for label, pred in (
            ("original-only", lambda a, b: a != "blank" and b == "blank"),
            ("remake-only", lambda a, b: a == "blank" and b != "blank"),
            ("mismatch", lambda a, b: a != "blank" and b != "blank" and a != b),
    ):
        buckets: dict = {}
        for lx, ly, a, b in rows:
            if not pred(a, b):
                continue
            key = (ly, a, b)
            buckets.setdefault(key, []).append(lx)
        for (ly, a, b), lxs in sorted(buckets.items()):
            lxs.sort()
            terrain_note = ""
            if "solid" in (a, b):
                terrain_note = ("terrain class "
                                f"{terrain[ly][lx // 2] if ly < len(terrain) and lx // 2 < len(terrain[ly]) else '?'}")
            print(f"{label:<14} ly={ly:<3} {a:<11}->{b:<11} "
                  f"lx={lxs} {terrain_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
