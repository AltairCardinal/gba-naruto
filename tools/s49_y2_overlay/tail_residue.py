#!/usr/bin/env python3
"""Y2: is the original's overlay buffer tail current map space content?

The original's BG2 overlay is a 256x256 px buffer anchored in **map space** at
map pixel ``(256, 0)`` (``tools/s49_y3/anchor_search.py``: the original's
``solid`` pixels are exactly the map cells whose terrain class is not "plain",
17984 / 17984 px).  The map is 480 px wide, so the buffer covers

    map px 256..479  -> battle columns 8..14   ("the main region")
    map px   0..31   -> battle column  0       ("the wrap tail")

and nothing else (battle columns 1..7 are not in the buffer at all).

The question this tool answers is **decidable**, not rhetorical: the original's
own overlay obeys three invariants that current map space content must obey,
because they are stated in terms of the map's own terrain:

    I1  ``solid`` (the grey dither = "blocked") is painted **exactly** where
        the cell's terrain class is not "plain";
    I2  a walkable cell that is not highlighted shows the lattice (``edge``);
    I3  a **highlight** family (``hatch`` = move range, ``band`` = cursor,
        ``line_alt`` = attack range, ``hatch_shift`` = legal target) is never
        painted on a cell whose terrain class is not "plain" -- a cursor or a
        reachable cell cannot stand on a wall.

The terrain used is the **original's own** collision grid
(``tools/s49_orig_map/battle-14-map-truth.json``, copied out of the reverse
line's ``map-canvases-v1`` manifest), so the test does not depend on the
remake's map at all.  The remake's terrain is printed next to it for
information only.

The tool reports the three invariants **separately for the main region and for
the wrap tail**.  If the main region satisfies them and the tail does not,
the tail cannot be current map space content: no faithful remake can paint it.

Usage::

    python tools/s49_y2_overlay/tail_residue.py
    python tools/s49_y2_overlay/tail_residue.py --out build/s49-y2/tail.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

from overlay_ground_truth import MOMENTS, load_moment  # noqa: E402

ORIG_MAP_TRUTH = REPO / "tools" / "s49_orig_map" / "battle-14-map-truth.json"

# The overlay buffer's geometry (see the module docstring).
ANCHOR_X = 256
MAP_W = 480
MAP_H = 304
CELL_W = 32          # one battle cell is 32x16 px
CELL_H = 16
ENTRY = 8            # the tilemap's 8x8 entries
COLS = 32            # entries per row
ROWS = 32
FIRST_MAP_ROW = 1    # the original paints map rows 1..12 of the buffer
LAST_MAP_ROW = 12

HIGHLIGHT_FAMILIES = ("hatch", "band", "line_alt", "hatch_shift")


def original_collision_grid() -> list[list[int]]:
    """The original's battle-14 terrain classes (15 wide x 19 tall)."""
    data = json.loads(ORIG_MAP_TRUTH.read_text(encoding="utf-8"))
    width, height = data["geometry"]["coarse_grid"]
    grid = data["collision_grid"]
    return [[grid[by * width + bx] for bx in range(width)]
            for by in range(height)]


def remake_terrain() -> list[list[int]]:
    """The remake's battle-14 terrain classes (15 wide x 19 tall)."""
    sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))
    import compare_overlay_families as shared  # noqa: E402
    return shared.remake_terrain()


def entry_map_px(ex: int, ey: int) -> tuple[int, int]:
    """The map pixel an 8x8 tilemap entry holds (480 px wrap, anchor 256)."""
    return ((ex * ENTRY + ANCHOR_X) % MAP_W, ey * ENTRY)


def battle_cell(map_px: tuple[int, int]) -> tuple[int, int]:
    return (map_px[0] // CELL_W, map_px[1] // CELL_H)


def region_of(map_px: tuple[int, int]) -> str:
    """``"main"`` for battle columns 8..14, ``"tail"`` for battle column 0."""
    bx, _by = battle_cell(map_px)
    return "tail" if bx == 0 else "main"


def analyse(moment_name: str, terrain: list[list[int]]) -> dict:
    """The three invariants, per region, over the original's own overlay."""
    moment = load_moment(moment_name)
    counters = {region: Counter() for region in ("main", "tail")}
    violations = {region: [] for region in ("main", "tail")}
    cursor_cells = []

    for ey in range(ROWS):
        map_y = ey * ENTRY
        by = map_y // CELL_H
        if not (FIRST_MAP_ROW <= by <= LAST_MAP_ROW):
            continue
        for ex in range(COLS):
            cell = moment.cells[ey * COLS + ex]
            family = cell["family"]
            if family == "blank":
                continue
            map_px = entry_map_px(ex, ey)
            bx, row = battle_cell(map_px)
            region = region_of(map_px)
            blocked = terrain[row][bx] != 0 if row < len(terrain) else False
            counters[region][family] += 1
            counters[region]["entries"] += 1
            counters[region]["blocked_entries" if blocked
                             else "walkable_entries"] += 1

            bad = None
            if family == "solid" and not blocked:
                bad = "I1-solid-on-walkable"
            elif family in ("edge", "blank") and blocked:
                bad = "I1-blocked-not-solid"
            elif family in HIGHLIGHT_FAMILIES and blocked:
                bad = "I3-highlight-on-blocked"
            if bad:
                counters[region][bad] += 1
                violations[region].append({
                    "buffer_entry": [ex, ey],
                    "map_px": list(map_px),
                    "battle_cell": [bx, row],
                    "terrain_class": terrain[row][bx] if row < len(terrain) else None,
                    "family": family,
                    "violation": bad,
                })
            if family == "band":
                cursor_cells.append({
                    "buffer_entry": [ex, ey],
                    "battle_cell": [bx, row],
                    "terrain_class": terrain[row][bx] if row < len(terrain) else None,
                    "blocked": blocked,
                })

    return {
        "moment": moment_name,
        "regions": {region: dict(counters[region]) for region in counters},
        "violations": violations,
        "cursor_cells": cursor_cells,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    terrain = original_collision_grid()
    remake = remake_terrain()

    print("=== the original's own battle-14 collision grid (rows 1..12)")
    for by in range(FIRST_MAP_ROW, LAST_MAP_ROW + 1):
        print(f"  row {by:2d}  " + " ".join(f"{terrain[by][bx]:2d}" for bx in range(15))
              + "   | remake: "
              + " ".join(f"{remake[by][bx]:2d}" for bx in range(15)))
    print("  (0 = plain / walkable, 15 = wall, 7 = rock, 1 = river, 3 = patch)")

    report = {"original_terrain": terrain, "remake_terrain": remake, "moments": {}}
    for name in MOMENTS:
        result = analyse(name, terrain)
        report["moments"][name] = result
        print(f"\n=== {name}")
        for region in ("main", "tail"):
            row = result["regions"][region]
            total = row.get("entries", 0)
            bad = (row.get("I1-solid-on-walkable", 0)
                   + row.get("I1-blocked-not-solid", 0)
                   + row.get("I3-highlight-on-blocked", 0))
            verdict = "holds" if bad == 0 else f"VIOLATED ({bad} entries)"
            print(f"  {region:5s}: {total:5d} painted entries   {verdict}")
            families = {k: v for k, v in sorted(row.items())
                        if k not in ("entries", "blocked_entries", "walkable_entries")
                        and not k.startswith("I1-") and not k.startswith("I3-")}
            print(f"          families {families}")
            if bad:
                print(f"          violations "
                      f"solid-on-walkable={row.get('I1-solid-on-walkable', 0)} "
                      f"blocked-not-solid={row.get('I1-blocked-not-solid', 0)} "
                      f"highlight-on-blocked={row.get('I3-highlight-on-blocked', 0)}")
        for cursor in result["cursor_cells"]:
            print(f"  yellow (cursor) cell: buffer entry {cursor['buffer_entry']} "
                  f"-> battle cell {cursor['battle_cell']} "
                  f"terrain class {cursor['terrain_class']} "
                  f"blocked={cursor['blocked']}")

    # ---- the verdict ------------------------------------------------------
    print("\n=== verdict")
    for name in MOMENTS:
        result = report["moments"][name]
        main_bad = sum(v for k, v in result["regions"]["main"].items()
                       if k.startswith(("I1-", "I3-")))
        tail_bad = sum(v for k, v in result["regions"]["tail"].items()
                       if k.startswith(("I1-", "I3-")))
        verdict = ("the tail obeys the invariants too -> it IS current map "
                   "space content" if tail_bad == 0 else
                   "the tail VIOLATES the invariants -> it is NOT current map "
                   "space content")
        print(f"  {name:20s} main violations {main_bad:3d}   "
              f"tail violations {tail_bad:3d}   -> {verdict}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8", newline="\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
