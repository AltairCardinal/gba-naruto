#!/usr/bin/env python3
"""Y2: per-cell classification of the remaining overlay family mismatches.

After the two wave-13 / Y2 fixes the two sides agree on **which** cells are
lit (``both 192 / original-only 0 / remake-only 0`` for ``field`` and
``movegrid``).  What is left are cells both sides paint with a **different
family**.  This tool lists every one of them and gives each one a *nature*,
decided by a test that can be checked, not by an opinion:

``tail-residue``
    The cell lies in the overlay buffer's wrap tail -- the map's column 0.
    In battle-14 that column is a **solid wall column** (terrain class 15 in
    all twelve drawn rows, in the original's *own* collision grid), yet the
    original's overlay paints its **yellow cursor**, its **cyan move range**
    and the **walkable lattice** there.  The original's own invariant
    ("a blocked cell is painted ``solid``; a highlight family is never
    painted on a blocked cell") holds on 520 of 521 painted entries of the
    buffer's main region and is violated on 44 to 59 entries of the tail.
    => the tail is **not** current map space content and **no faithful
    remake can reproduce it**.  See ``tail_residue.py``.

``walk-phase``
    The original's moment is **not reachable** in the remake's walk.  The
    test is the moment's own family set: the original's ``field`` moment
    shows ``hatch`` (cyan) and ``line_alt`` (orange) **at the same time**,
    and no frame of the remake's walk shows those two families together
    (the walk's frames are either cyan-only or green+orange).  A moment the
    walk never reaches cannot be compared cell by cell.

``unit-occupied``
    The remake paints ``solid`` on a cell whose terrain class is **plain**.
    The remake's overlay paints ``solid`` on the terrain's blocked cells
    *and* on the cells a unit stands on, so this is a **unit placement**
    difference -- a game state, not a painting rule.

``product-diff``
    Everything else: a real painting-rule difference.  This is the only
    class that is a candidate for a product fix, and it must be zero.

Usage::

    python tools/s49_y2_overlay/classify_mismatches.py \
        --vram-dir build/s49-package-y4/evidence/overlay/vram \
        --out build/s49-y2/classification.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

import compare_overlay_families as shared  # noqa: E402

# The overlay buffer's wrap tail: the map's column 0, i.e. the map's logical
# columns 0 and 1 (a battle cell is 32 px wide = two 16 px logical cells).
TAIL_COLUMNS = (0, 1)

NATURE_LABELS = {
    "tail-residue": "not reproducible (the original's wrap-tail residue)",
    "walk-phase": "walk phase / game state",
    "unit-occupied": "game state (a unit stands on the cell)",
    "product-diff": "product difference",
}


def family_set(cells: dict, tail: bool) -> set[str]:
    return {family for key, family in cells.items()
            if (key[0] in TAIL_COLUMNS) == tail}


def classify(original: dict, remake: dict, all_frames: dict,
             terrain: list[list[int]]) -> tuple[list, Counter]:
    """Every mismatch, with its nature."""
    # The original's family set outside the tail, and whether **any** frame of
    # the walk can show all of it at once (the moment reachability test).
    want = family_set(original, tail=False)
    reachable = any(want <= family_set(cells, tail=False)
                    for cells in all_frames.values())
    rows = []
    counts: Counter = Counter()
    for key in sorted(set(original) | set(remake)):
        a = original.get(key, "blank")
        b = remake.get(key, "blank")
        if a == b:
            continue
        if key[0] in TAIL_COLUMNS:
            nature = "tail-residue"
        elif not reachable:
            nature = "walk-phase"
        elif a == "blank" or b == "blank":
            nature = "walk-phase"
        elif b == "solid":
            # The remake paints "blocked" here; the terrain says plain.
            bx, by = key[0] // 2, key[1]
            plain = (by < len(terrain) and bx < len(terrain[by])
                     and terrain[by][bx] == 0)
            nature = "unit-occupied" if plain else "product-diff"
        elif any(cells.get(key) == a for cells in all_frames.values()):
            nature = "walk-phase"
        else:
            nature = "product-diff"
        counts[nature] += 1
        rows.append({"map_lx": key[0], "map_ly": key[1],
                     "original": a, "remake": b, "nature": nature})
    return rows, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--moments", nargs="*", default=list(shared.MOMENTS))
    args = ap.parse_args()

    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    if not dumps:
        print("ERR no VRAM dumps")
        return 2

    terrain = shared.remake_terrain()
    originals = {name: shared.original_map_cells(name) for name in args.moments}

    all_frames: dict[str, dict] = {}
    for path in dumps:
        vram = path.read_bytes()
        base = shared.find_overlay_map(vram, terrain=terrain)
        if base < 0:
            all_frames[path.name] = {}
            continue
        entry_map = shared.remake_entry_map(vram, base)
        _ax, _ay, cells = shared.best_window(entry_map, terrain)
        all_frames[path.name] = cells

    report = {"vram_dir": str(args.vram_dir), "moments": {}}
    for name in args.moments:
        original = originals[name]
        ranking = []
        for path_name, cells in all_frames.items():
            result = shared.compare(original, cells)
            key = (result["both_lit"] - result["family_mismatches"],
                   -result["residual"])
            ranking.append((key, path_name, result))
        ranking.sort(key=lambda item: item[0], reverse=True)
        best = ranking[0]
        rows, counts = classify(original, all_frames[best[1]], all_frames, terrain)
        want = family_set(original, tail=False)
        report["moments"][name] = {
            "frame": best[1],
            "both_lit": best[2]["both_lit"],
            "original_only": best[2]["original_only"],
            "remake_only": best[2]["remake_only"],
            "family_mismatches": best[2]["family_mismatches"],
            "original_family_set": sorted(want),
            "moment_reachable": any(
                want <= family_set(cells, tail=False)
                for cells in all_frames.values()),
            "nature_counts": dict(counts),
            "cells": rows,
        }

    print("=== per-cell family mismatches, classified")
    for name in args.moments:
        row = report["moments"][name]
        print(f"\n=== {name}   frame {row['frame']}")
        print(f"  both {row['both_lit']}  original-only {row['original_only']}  "
              f"remake-only {row['remake_only']}  family mismatches "
              f"{row['family_mismatches']}")
        print(f"  the original's family set (outside the tail): "
              f"{row['original_family_set']}   moment reachable in the walk: "
              f"{row['moment_reachable']}")
        for nature, count in sorted(row["nature_counts"].items()):
            print(f"  {nature:14s} {count:4d}   {NATURE_LABELS.get(nature, '')}")
        pairs: Counter = Counter()
        for cell in row["cells"]:
            pairs[(cell["original"], cell["remake"], cell["nature"])] += 1
        for (a, b, nature), count in sorted(pairs.items()):
            print(f"      {a:11s} -> {b:11s}  x{count:<3d}  {nature}")
        print("      cells:")
        for cell in row["cells"]:
            print(f"        map_lx={cell['map_lx']:<3d} map_ly={cell['map_ly']:<3d} "
                  f"{cell['original']:11s} -> {cell['remake']:11s} "
                  f"{cell['nature']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8", newline="\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
