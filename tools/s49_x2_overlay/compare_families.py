#!/usr/bin/env python3
"""X2: the per-logical-cell family comparison, with the map-space wrap fixed.

Read-only reuse of the shared instrument
``tools/s49_overlay_align/compare_overlay_families.py`` (U4/W4 own it; this
file must not modify it).

What this tool fixes (and why it matters)
-----------------------------------------

The shared instrument labels the **original**'s logical cells with

    map_lx = (anchor_x + lx * 16) // 16          # 16, 17, ... 31

i.e. it does **not** wrap the original's buffer tail at the map's 480 px
width, while the **remake** side does (``remake_logical_cells`` uses
``% MAP_WIDTH``).  The original's overlay buffer is 256 px wide and is
anchored at map pixel 256, so its tail (buffer px 224..255) holds the map's
first 32 px (the map's column 0) -- that is what the anchor evidence
measured (``tools/s49_y3/anchor_search.py``: 17984 / 17984 px at (256, 0)
**with** wrap).

Because of the missing wrap the two sides are compared on *different* cells
in the tail: the original's last two logical columns are labelled map
columns 30 and 31 (which do not exist in a 30-column map) and the remake's
tail is labelled map columns 0 and 1.  The result is a symmetric
"24 original-only / 24 remake-only" that is a **labelling artefact**, not a
product difference.

This tool wraps the original side the same way as the remake side and then
attributes every remaining difference to one of:

* ``tail``    -- the map's column 0 (the overlay buffer's wrap tail);
* ``phase``   -- the original's frame shows a family the remake never shows
                 in any frame of the walk (attack range / green targets);
* ``state``   -- the same families, different cells: the remake's walk is
                 not in the same game state as the original's frame.

Usage::

    python tools/s49_x2_overlay/compare_families.py \
        --vram-dir build/s49-package/evidence/overlay/vram \
        --out build/s49-x2/compare.json
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
from overlay_ground_truth import LOGICAL_COLS, LOGICAL_ROWS  # noqa: E402

SHORT = {
    "blank": ".", "edge": "E", "hatch": "H", "line_alt": "A",
    "band": "B", "hatch_shift": "h", "solid": "S", "mixed": "?",
}

# The overlay buffer's wrap tail: the map's column 0 (map logical columns 0
# and 1).  See the module docstring and ledger X2-H3.
TAIL_COLUMNS = (0, 1)


def original_map_cells_wrapped(moment_name: str,
                               exclude_tail: bool = False
                               ) -> dict[tuple[int, int], str]:
    """The original's overlay as map space logical cells, **wrapped**.

    Buffer logical column ``lx`` holds the map pixel
    ``(256 + lx * 16) mod 480`` -- the same convention the remake side uses.

    ``exclude_tail`` drops the buffer's wrap tail (the map's column 0).  The
    tail is *not* current map space content: it carries a stale cursor (the
    yellow ``band`` tile of the "grid16" frame), a stale move range (the
    cyan ``hatch`` tiles of rows 14..17) and a half drawn dither on the map's
    wall column -- content that no map space remake can reproduce.  See
    notes/s49-fidelity/X2-overlay-zero.md, ledger X2-H3.
    """
    moment = shared.load_moment(moment_name)
    grid = moment.logical_grid()
    anchor_x, anchor_y = shared.ORIGINAL_MAP_ANCHOR
    cells: dict[tuple[int, int], str] = {}
    for ly in range(LOGICAL_ROWS):
        for lx in range(LOGICAL_COLS):
            family = grid[ly][lx]
            if family == "blank":
                continue
            map_lx = ((anchor_x + lx * 16) % shared.MAP_WIDTH) // 16
            map_ly = ((anchor_y + ly * 16) % shared.MAP_HEIGHT) // 16
            if exclude_tail and map_lx in TAIL_COLUMNS:
                continue
            cells[(map_lx, map_ly)] = family
    return cells


def remake_cells_from(entry_map: list[list[int]],
                      exclude_tail: bool = False
                      ) -> dict[tuple[int, int], str]:
    """The remake's overlay as map space logical cells (tail optionally out)."""
    cells = shared.remake_logical_cells(entry_map, *shared.REMAKE_MAP_ANCHOR)
    if not exclude_tail:
        return cells
    return {key: family for key, family in cells.items()
            if key[0] not in TAIL_COLUMNS}


def frame_families(cells: dict[tuple[int, int], str]) -> Counter:
    return Counter(cells.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--exclude-tail", action="store_true",
                    help="drop the overlay buffer's wrap tail (the map's "
                         "column 0) from both sides; the tail is not current "
                         "map space content (ledger X2-H3)")
    args = ap.parse_args()

    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    if not dumps:
        print("ERR no VRAM dumps")
        return 2

    terrain = shared.remake_terrain()
    originals = {name: original_map_cells_wrapped(name, args.exclude_tail)
                 for name in shared.MOMENTS}
    unwrapped = {name: shared.original_map_cells(name)
                 for name in shared.MOMENTS}

    report: dict = {"vram_dir": str(args.vram_dir),
                    "exclude_tail": args.exclude_tail,
                    "moments": {}, "frames": {}}

    # ---- per frame -------------------------------------------------------
    remake_cells: dict[str, dict[tuple[int, int], str]] = {}
    for path in dumps:
        vram = path.read_bytes()
        base = shared.find_overlay_map(vram, terrain=terrain)
        if base < 0:
            cells: dict[tuple[int, int], str] = {}
        else:
            entry_map = shared.remake_entry_map(vram, base)
            _ax, _ay, cells = shared.best_window(entry_map, terrain)
            cells = remake_cells_from(entry_map, args.exclude_tail)
        remake_cells[path.name] = cells
        report["frames"][path.name] = {
            "overlay_map": base,
            "families": dict(frame_families(cells)),
        }

    # ---- per moment ------------------------------------------------------
    for name in shared.MOMENTS:
        ranking = []
        for path in dumps:
            cells = remake_cells[path.name]
            result = shared.compare(originals[name], cells)
            key = (result["both_lit"] - result["family_mismatches"],
                   -result["residual"])
            ranking.append((key, path.name, result))
        ranking.sort(key=lambda item: item[0], reverse=True)

        best = ranking[0]
        row = {
            "frame": best[1],
            "original_lit": best[2]["original_lit"],
            "remake_lit": best[2]["remake_lit"],
            "both_lit": best[2]["both_lit"],
            "original_only": best[2]["original_only"],
            "remake_only": best[2]["remake_only"],
            "family_mismatches": best[2]["family_mismatches"],
            "residual": best[2]["residual"],
            "exact": best[2]["exact"],
            "original_families": dict(frame_families(originals[name])),
            "remake_families": dict(frame_families(remake_cells[best[1]])),
            "top_frames": [
                {"frame": path_name,
                 "both_lit": result["both_lit"],
                 "original_only": result["original_only"],
                 "remake_only": result["remake_only"],
                 "family_mismatches": result["family_mismatches"],
                 "residual": result["residual"]}
                for _key, path_name, result in ranking[:args.top]
            ],
        }
        # the shared instrument's own numbers, for the record
        shared_best = None
        for path in dumps:
            cells = remake_cells[path.name]
            result = shared.compare(unwrapped[name], cells)
            key = (result["both_lit"] - result["family_mismatches"],
                   -result["residual"])
            if shared_best is None or key > shared_best[0]:
                shared_best = (key, path.name, result)
        row["shared_instrument"] = {
            "frame": shared_best[1],
            "both_lit": shared_best[2]["both_lit"],
            "original_only": shared_best[2]["original_only"],
            "remake_only": shared_best[2]["remake_only"],
            "family_mismatches": shared_best[2]["family_mismatches"],
        }
        report["moments"][name] = row

    # ---- print -----------------------------------------------------------
    print("=== per logical cell, map space, both sides wrapped at 480 px")
    for name in shared.MOMENTS:
        row = report["moments"][name]
        shared_row = row["shared_instrument"]
        print(f"\n=== {name}")
        print(f"  shared instrument (original side NOT wrapped): "
              f"both {shared_row['both_lit']}  orig-only "
              f"{shared_row['original_only']}  remake-only "
              f"{shared_row['remake_only']}  mismatch "
              f"{shared_row['family_mismatches']}")
        print(f"  wrapped (this tool): frame {row['frame']}  "
              f"lit {row['original_lit']}/{row['remake_lit']}  "
              f"both {row['both_lit']}  orig-only {row['original_only']}  "
              f"remake-only {row['remake_only']}  mismatch "
              f"{row['family_mismatches']}  residual {row['residual']}")
        print(f"  original families {row['original_families']}")
        print(f"  remake   families {row['remake_families']}")
        for entry in row["top_frames"]:
            print(f"    {entry['frame']:<34s} both {entry['both_lit']:3d}  "
                  f"orig-only {entry['original_only']:3d}  remake-only "
                  f"{entry['remake_only']:3d}  mismatch "
                  f"{entry['family_mismatches']:3d}")

    # ---- attribution -----------------------------------------------------
    print("\n=== attribution of the remaining differences")
    for name in shared.MOMENTS:
        row = report["moments"][name]
        cells = remake_cells[row["frame"]]
        original = originals[name]
        pairs: Counter = Counter()
        tail = 0
        for key in sorted(set(original) | set(cells)):
            a = original.get(key, "blank")
            b = cells.get(key, "blank")
            if a == b:
                continue
            pairs[(a, b)] += 1
            if key[0] in (0, 1):
                tail += 1
        row["difference_pairs"] = {f"{a}->{b}": count
                                   for (a, b), count in pairs.items()}
        row["tail_differences"] = tail
        row["state_differences"] = row["family_mismatches"] - tail
        print(f"  {name:18s} tail {tail:3d}  other {row['state_differences']:3d}"
              f"   {row['difference_pairs']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
