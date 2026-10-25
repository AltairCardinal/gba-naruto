#!/usr/bin/env python3
"""X2 diagnostics: where do the per-cell overlay differences come from?

Read-only reuse of the shared instrument
``tools/s49_overlay_align/compare_overlay_families.py`` (U4/W4 own it; this
file must not modify it).

The shared instrument labels the **original**'s logical cells with
``map_lx = (anchor_x + lx * 16) // 16`` -- i.e. it does **not** wrap the
buffer's tail at the map's 480 px width.  The **remake** side does wrap
(``remake_logical_cells`` uses ``% MAP_WIDTH``).  The original's anchor is
map px 256 and its buffer is 256 px wide, so its tail (buffer px 224..255)
holds the map's first 32 px (map logical columns 0 and 1) -- that is exactly
what the anchor evidence measured (``tools/s49_y3/anchor_search.py``:
17984 / 17984 px at (256, 0) **with wrap**).

This script measures both conventions side by side so the difference is
visible instead of argued about.

Usage::

    python tools/s49_x2_overlay/diagnose.py \
        --vram-dir build/s49-package/evidence/overlay/vram
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_overlay_align"))

import compare_overlay_families as shared  # noqa: E402
from overlay_ground_truth import LOGICAL_COLS, LOGICAL_ROWS  # noqa: E402

MAP_WIDTH = shared.MAP_WIDTH
MAP_LOGICAL_COLS = MAP_WIDTH // 16


def original_map_cells_wrapped(moment_name: str) -> dict[tuple[int, int], str]:
    """The original's overlay as map space logical cells, **wrapped**.

    Buffer logical column ``lx`` holds the map pixel
    ``(256 + lx * 16) mod 480`` -- the same convention the remake side uses.
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
            map_lx = ((anchor_x + lx * 16) % MAP_WIDTH) // 16
            map_ly = ((anchor_y + ly * 16) % shared.MAP_HEIGHT) // 16
            cells[(map_lx, map_ly)] = family
    return cells


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram-dir", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    if not dumps:
        print("ERR no VRAM dumps")
        return 2

    terrain = shared.remake_terrain()
    print(f"terrain grid: {len(terrain)} rows x {len(terrain[0])} cols  "
          f"(map {MAP_WIDTH} x {shared.MAP_HEIGHT} px, "
          f"{MAP_LOGICAL_COLS} logical cols)")

    wrapped = {name: original_map_cells_wrapped(name)
               for name in shared.MOMENTS}
    unwrapped = {name: shared.original_map_cells(name)
                 for name in shared.MOMENTS}

    print("\n--- original side: column sets ---")
    for name in shared.MOMENTS:
        for label, table in (("unwrapped", unwrapped), ("wrapped  ", wrapped)):
            cols = sorted({key[0] for key in table[name]})
            rows = sorted({key[1] for key in table[name]})
            span = f"{rows[0]}..{rows[-1]}" if rows else "-"
            print(f"  {name:18s} {label}  lit={len(table[name]):3d}  "
                  f"cols={cols}  rows={span}")

    best: dict[str, dict] = {}
    for path in dumps:
        vram = path.read_bytes()
        base = shared.find_overlay_map(vram, terrain=terrain)
        if base < 0:
            cells: dict[tuple[int, int], str] = {}
        else:
            entry_map = shared.remake_entry_map(vram, base)
            _ax, _ay, cells = shared.best_window(entry_map, terrain)
        for name in shared.MOMENTS:
            for label, table in (("unwrapped", unwrapped), ("wrapped  ", wrapped)):
                result = shared.compare(table[name], cells)
                key = (result["both_lit"] - result["family_mismatches"],
                       -result["residual"])
                slot = best.setdefault((name, label), [None, None])
                if slot[0] is None or key > slot[0]:
                    slot[0] = key
                    slot[1] = {
                        "frame": path.name,
                        "both_lit": result["both_lit"],
                        "original_only": result["original_only"],
                        "remake_only": result["remake_only"],
                        "family_mismatches": result["family_mismatches"],
                        "residual": result["residual"],
                        "exact": result["exact"],
                        "details": result["differences"],
                    }

    print("\n--- per moment ---")
    for name in shared.MOMENTS:
        for label in ("unwrapped", "wrapped  "):
            row = best[(name, label)][1]
            print(f"  {name:18s} {label}  both {row['both_lit']:3d}  "
                  f"orig-only {row['original_only']:3d}  "
                  f"remake-only {row['remake_only']:3d}  "
                  f"mismatch {row['family_mismatches']:3d}  "
                  f"residual {row['residual']:3d}  exact {row['exact']}")

    # The family histogram of the mismatching cells (wrapped convention).
    print("\n--- mismatch composition (wrapped) ---")
    for name in shared.MOMENTS:
        row = best[(name, "wrapped  ")][1]
        pairs = Counter()
        for item in row["details"]:
            pairs[(item["original"], item["remake"])] += 1
        print(f"  {name}: {dict(pairs)}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        import json
        payload = {
            name: {
                label: best[(name, label)][1]
                for label in ("unwrapped", "wrapped  ")
            }
            for name in shared.MOMENTS
        }
        args.out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
