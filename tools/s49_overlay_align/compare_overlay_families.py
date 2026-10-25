#!/usr/bin/env python3
"""Per-logical-cell family comparison: original BG2 overlay vs the remake.

Both sides are reduced to a **map space** grid of 16x16 px logical cells and
the *family* of every cell is compared.

* The **original** side comes from the exported ground truth
  (``tools/s49_rule_probe/overlay_ground_truth.py``): a 256x256 px BG2 layer.
  Its buffer is anchored in map space: buffer pixel (x, y) is map pixel
  ``(x + 256, y)`` -- verified against the battle-14 terrain (the original's
  ``solid`` pixels are *exactly* the map cells whose terrain class is not
  "plain", 17984 / 17984 px) and against the acting unit's map position.
* The **remake** side comes from a VRAM dump of the built ROM: the overlay's
  own BG map is located by signature and turned into families with the same
  vocabulary.

Three bugs in the previous version of this tool are fixed here:

1. ``find_overlay_map`` scanned *every* 0x400 aligned window of VRAM, which
   includes the BG **tile graphics** (VRAM 0x00000-0x0FFFF).  It happily
   returned a window of tile graphics and decoded it as a tilemap.  The overlay
   map is now located by requiring every non-zero entry to be a valid overlay
   tile index.
2. The two sides used to be compared at an arbitrary grid offset, which
   cannot express a map space anchor (the map is not 256 px periodic).  The
   comparison is now done in map space.
3. **Wave 10 / U4 (2026-10-24): the anchor is now a *measured constant*, not a
   searched window.**  The previous version labelled the remake's buffer with a
   *camera derived* window (``window_x = 240 + camera.x()``) and then searched
   that window in ``[0, 256)``.  The original's anchor is map pixel
   ``(256, 0)`` -- which that search range cannot even express (the map is
   480 px wide, so 256 is not 0).  Measured: the original's ``solid`` pixels
   are *exactly* the map cells whose terrain class is not "plain",
   17984 / 17984 px, at anchor ``(256, 0)``; the runner up ``(264, 0)`` only
   reaches 17216.  So the buffer pixel ``p`` now holds the map pixel
   ``((p + 256) mod 480, p)`` on **both** sides and the window search is gone:
   the instrument now asks the question the product has to answer -- "does the
   remake's overlay buffer carry the original's content at the original's
   anchor?" -- instead of "is there *some* window that flatters the remake?".

   Evidence that this does not hide a window difference: wave 9's V2 stream
   measured the explicit-anchor comparison and the free-window search on the
   same VRAM dump and got **the same numbers** (field 81/111/36/26, movegrid
   81/111/36/10), i.e. the residual lives in the *content*, not in the window.
   See ``notes/s49-fidelity/V2-camera-anchor.md`` and
   ``tools/s49_v2_anchor/compare_at_anchor.py``.

4. **Wave 13 / Y2 (2026-10-24): the original's side now wraps at the map's
   480 px width.**  The remake's side has always wrapped
   (``remake_logical_cells``: ``% MAP_WIDTH``) but the original's side did
   not, so the two sides were compared on **different cells** in the
   overlay buffer's wrap tail (the map's column 0).  The symptom was a
   symmetric "24 original-only / 24 remake-only" on every moment, which is a
   labelling artefact, not a product difference: after the wrap the tail
   compares like every other cell and ``field`` / ``movegrid`` read
   ``both 192 / original-only 0 / remake-only 0``.
   See ``notes/s49-fidelity/Y2-overlay-final.md``.

Usage::

    python tools/s49_overlay_align/compare_overlay_families.py \
        --vram <remake vram dump> --out build/s49-overlay/compare.json

    python tools/s49_overlay_align/compare_overlay_families.py \
        --vram-dir <dir with *.vram-*.bin> --out build/s49-overlay/compare.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from overlay_ground_truth import (  # noqa: E402
    LOGICAL_COLS,
    LOGICAL_ROWS,
    MOMENTS,
    load_moment,
)

# The remake's overlay tile index layout (battle_range_ui_style.h):
#   grid 1..8, move 9..16, attack_range 17..24, cursor 53..60,
#   target 61..68, blocked 69..76.
REMAKE_TILE_RANGES = (
    (1, 8, "edge"),
    (9, 16, "hatch"),
    (17, 24, "line_alt"),
    (53, 60, "band"),
    (61, 68, "hatch_shift"),
    (69, 76, "solid"),
)

FAMILY_ORDER = (
    "blank", "edge", "hatch", "line_alt", "band", "hatch_shift", "solid",
)

# The original's BG2 buffer is anchored in map space.  See the module
# docstring; the anchor is checked against the terrain by
# ``tools/s49_y3/anchor_search.py`` (17984 / 17984 px at (256, 0)).
ORIGINAL_MAP_ANCHOR = (256, 0)

# The remake's buffer is read with the **same** convention: the buffer pixel
# ``p`` holds the map pixel ``((p + 256) mod 480, p)``.  This is the same
# arithmetic as ``battle_map_overlay_map_x`` / ``battle_map_overlay_map_y`` in
# the remake (``battle_map_visual_projection.h``), so the instrument measures
# the product the way the product is specified.
REMAKE_MAP_ANCHOR = ORIGINAL_MAP_ANCHOR

# The remake's battle-14 terrain (generated_battle_map_content.h).  Only the
# blocked/terrain class matters here.
REMAKE_MAP_HEADER = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\butano-sequel\game\include\konoha"
    r"\generated_battle_map_content.h")
REMAKE_BATTLE_ID = 14
# The map the battle grid lives on: 15 battle columns x 32 px, 19 battle rows
# x 16 px.
MAP_WIDTH = 15 * 32
MAP_HEIGHT = 19 * 16

# Filled in by ``best_window``: how many of the buffer's ``solid`` cells sit
# on blocked terrain at the fixed anchor.  A sanity check on the anchor, and
# a number the report can cite.
BEST_WINDOW_DIAGNOSTIC: dict = {}


def remake_family(tile: int) -> tuple[str, int, int]:
    """(family, tile_x, tile_y) of a remake overlay tile index.

    The remake's style header lays each 32x16 px battle cell out as 4x2
    8x8 entries, so the tile index itself carries the position of the entry
    inside its cell: ``tile = first + tile_y * 4 + tile_x``.
    """
    for first, _last, family in REMAKE_TILE_RANGES:
        if first <= tile < first + 8:
            offset = tile - first
            return family, offset % 4, offset // 4
    return "blank", 0, 0


def ceil_div(value: int, divisor: int) -> int:
    quotient = value // divisor
    remainder = value % divisor
    return quotient + 1 if remainder > 0 else quotient


def find_overlay_map(vram: bytes, tile_max: int = 77,
                     terrain: list[list[int]] | None = None) -> int:
    """The VRAM offset of the remake's overlay BG map (by signature).

    A candidate is a 0x800 aligned window (one GBA screen block) whose every
    non-zero entry is a valid overlay tile index.  The action menu re-uses
    the same map with the tiles 25..52, which are not overlay tiles, so an
    action-menu frame correctly has no overlay map.

    The previous version of this function scanned *every* 0x400 aligned
    window of VRAM, which includes the BG **tile graphics** (VRAM
    0x00000-0x0FFFF); it happily returned a window of tile graphics and
    decoded it as a tilemap, so every number it produced was measured on
    garbage.

    Wave 10 / U4: the "every entry is a valid overlay tile" signature is
    **not** strong enough on its own.  A window of tile graphics whose bytes
    happen to fall inside the overlay's tile indices decodes into a
    plausible-looking tilemap (measured: VRAM window 0x00800, 1024 non-zero
    entries, all of them "valid"), and that window then wins the search
    because it has more entries than the real overlay map (768).  The
    discriminator that separates them is the original's own rule: **the
    overlay draws a cell as ``solid`` exactly where the map's terrain class
    is not "plain"** (17984 / 17984 px measured).  So when the terrain is
    given, a candidate must show at least one ``solid`` cell that lands on
    blocked terrain; the tile-graphics window has none.

    Without a terrain the function keeps its previous behaviour, so the
    callers that only have VRAM (the judgment bench's own overlay reader) are
    unaffected.
    """
    candidates = []
    for base in range(0, len(vram) - 2048 + 1, 0x800):
        entries = struct.unpack_from("<1024H", vram, base)
        non_zero = [entry & 0x3FF for entry in entries if (entry & 0x3FF)]
        if not non_zero:
            continue
        if any(remake_family(tile)[0] == "blank" or tile > tile_max
               for tile in non_zero):
            continue
        candidates.append((len(non_zero), base))
    if not candidates:
        return -1
    if terrain is None:
        return max(candidates)[1]
    blocked = {(bx, by)
               for by, row in enumerate(terrain)
               for bx, value in enumerate(row) if value != 0}
    scored = []
    for non_zero_count, base in candidates:
        cells = remake_logical_cells(remake_entry_map(vram, base))
        on_blocked, off_blocked = _solid_terrain_counts(cells, blocked)
        scored.append((on_blocked, -off_blocked, non_zero_count, base))
    best = max(scored)
    return best[3] if best[0] > 0 else -1


def _solid_terrain_counts(cells: dict[tuple[int, int], str],
                          blocked: set) -> tuple[int, int]:
    """(solid cells on blocked terrain, solid cells off it)."""
    on_blocked = 0
    off_blocked = 0
    for (lx, ly), family in cells.items():
        if family != "solid":
            continue
        if (lx // 2, ly) in blocked:
            on_blocked += 1
        else:
            off_blocked += 1
    return on_blocked, off_blocked


def remake_terrain() -> list[list[int]]:
    """The remake's battle-14 terrain classes (15 wide x 19 tall)."""
    text = REMAKE_MAP_HEADER.read_text(encoding="utf-8")
    body = re.search(r"battle_map_cells = \{\{(.*?)\n\}\};", text, re.S).group(1)
    values = [int(item, 16) for item in re.findall(
        r"battle_map_cell\{\s*(0x[0-9a-fA-F]+)\s*\}", body)]
    definitions = re.search(
        r"battle_map_definitions = \{\{(.*?)\n\}\};", text, re.S).group(1)
    rows = re.findall(
        r"battle_map_definition\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)"
        r"\s*,\s*(\d+)\s*\}", definitions)
    for battle_id, width, height, offset, count in rows:
        if int(battle_id) != REMAKE_BATTLE_ID:
            continue
        width = int(width)
        height = int(height)
        offset = int(offset)
        return [[values[offset + by * width + bx] & 15 for bx in range(width)]
                for by in range(height)]
    raise RuntimeError("battle 14 not found in the remake's map content")


def remake_entry_map(vram: bytes, base: int) -> list[list[int]]:
    """The overlay map's 32x32 entry grid (tile indices)."""
    entries = struct.unpack_from("<1024H", vram, base)
    return [[entries[row * 32 + column] & 0x3FF for column in range(32)]
            for row in range(32)]


def remake_logical_cells(entry_map: list[list[int]],
                         window_x: int | None = None,
                         window_y: int | None = None) -> dict[tuple[int, int], str]:
    """The remake's overlay as map space logical cells.

    The buffer pixel ``p`` holds the map pixel
    ``((p + anchor_x) mod 480, (p + anchor_y) mod 304)`` -- the original's
    anchoring convention (anchor ``(256, 0)``, measured 17984 / 17984 px
    against the battle-14 terrain).

    ``window_x`` / ``window_y`` keep their names and their position in the
    signature (other streams' tools call this function with them), but they
    now mean the **anchor** instead of a camera derived window origin.
    ``None`` means "the original's anchor".
    """
    anchor_x = REMAKE_MAP_ANCHOR[0] if window_x is None else window_x
    anchor_y = REMAKE_MAP_ANCHOR[1] if window_y is None else window_y
    cells: dict[tuple[int, int], str] = {}
    for row in range(32):
        map_px_y = (row * 8 + anchor_y) % MAP_HEIGHT
        for column in range(32):
            tile = entry_map[row][column]
            if tile == 0:
                continue
            family, _tile_x, _tile_y = remake_family(tile)
            if family == "blank":
                continue
            map_px_x = (column * 8 + anchor_x) % MAP_WIDTH
            key = (map_px_x // 16, map_px_y // 16)
            if cells.get(key, family) != family:
                cells[key] = "mixed"
            else:
                cells[key] = family
    return cells


def best_window(entry_map: list[list[int]],
                terrain: list[list[int]]) -> tuple[int, int, dict]:
    """The remake's map space anchor and the cells it produces.

    The anchor is **not searched any more**: it is a measured constant
    (map pixel ``(256, 0)``, see the module docstring).  The previous
    version searched a camera derived window in ``[0, 256)``, a range that
    cannot even express the original's anchor, and it reported the best of
    the search -- which flatters the remake.  The free search is still
    available as a read-only diagnostic in
    ``tools/s49_v2_anchor/scan_window.py``.

    The terrain is still used for one thing: to report how many of the
    ``solid`` cells the buffer carries actually sit on blocked terrain
    (the original draws ``solid`` exactly where the terrain class is not
    "plain"), which is a cheap sanity check on the anchor.
    """
    anchor_x, anchor_y = REMAKE_MAP_ANCHOR
    cells = remake_logical_cells(entry_map, anchor_x, anchor_y)
    blocked = {(bx, by)
               for by, row in enumerate(terrain)
               for bx, value in enumerate(row) if value != 0}
    contained, wrong = _solid_terrain_counts(cells, blocked)
    BEST_WINDOW_DIAGNOSTIC.clear()
    BEST_WINDOW_DIAGNOSTIC.update({"solid_on_blocked": contained,
                                   "solid_off_blocked": wrong})
    return anchor_x, anchor_y, cells


def original_map_cells(moment_name: str) -> dict[tuple[int, int], str]:
    """The original's overlay as map space logical cells.

    The buffer's logical cell ``lx`` holds the map pixel
    ``(anchor_x + lx * 16) mod MAP_WIDTH`` -- the **same** convention the
    remake side uses (``remake_logical_cells``), and the wrap is not a
    detail:

    * the original's overlay buffer is 256 px wide, the battle-14 map is
      480 px wide, and the buffer is anchored at map pixel 256;
    * so the buffer's tail (buffer px 224..255, its logical columns 14 and
      15) holds the map's **first** 32 px -- the map's column 0.  That is
      what the anchor measurement says (``tools/s49_y3/anchor_search.py``:
      17984 / 17984 px at ``(256, 0)``, **with** wrap);
    * without the wrap those two logical columns were labelled map columns
      30 and 31, which do not exist in a 30 logical column map, while the
      remake's tail was labelled map columns 0 and 1.  The two sides were
      therefore compared on **different cells** in the tail, which produced
      a symmetric "24 original-only / 24 remake-only" that was a labelling
      artefact and not a product difference.

    ``map_ly`` wraps over ``MAP_HEIGHT`` as well; with ``anchor_y == 0`` the
    vertical wrap is the identity (the buffer's 16 logical rows are 0..240,
    the map is 304 px tall), but the formula is written symmetrically so it
    stays correct if the anchor ever moves.
    """
    moment = load_moment(moment_name)
    grid = moment.logical_grid()
    anchor_x, anchor_y = ORIGINAL_MAP_ANCHOR
    cells: dict[tuple[int, int], str] = {}
    for ly in range(LOGICAL_ROWS):
        for lx in range(LOGICAL_COLS):
            family = grid[ly][lx]
            if family == "blank":
                continue
            map_lx = ((anchor_x + lx * 16) % MAP_WIDTH) // 16
            map_ly = ((anchor_y + ly * 16) % MAP_HEIGHT) // 16
            cells[(map_lx, map_ly)] = family
    return cells


def compare(left: dict[tuple[int, int], str],
            right: dict[tuple[int, int], str]) -> dict:
    original_only = 0
    remake_only = 0
    mismatch = 0
    both_lit = 0
    details = []
    for key in sorted(set(left) | set(right)):
        a = left.get(key, "blank")
        b = right.get(key, "blank")
        a_lit = a != "blank"
        b_lit = b != "blank"
        if a_lit and b_lit:
            both_lit += 1
            if a != b:
                mismatch += 1
                details.append({"map_lx": key[0], "map_ly": key[1],
                                "original": a, "remake": b})
        elif a_lit:
            original_only += 1
            details.append({"map_lx": key[0], "map_ly": key[1],
                            "original": a, "remake": "blank"})
        elif b_lit:
            remake_only += 1
            details.append({"map_lx": key[0], "map_ly": key[1],
                            "original": "blank", "remake": b})
    return {
        "original_lit": len(left),
        "remake_lit": len(right),
        "both_lit": both_lit,
        "original_only": original_only,
        "remake_only": remake_only,
        "family_mismatches": mismatch,
        "residual": original_only + remake_only + mismatch,
        "exact": original_only == 0 and remake_only == 0 and mismatch == 0,
        "differences": details,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vram", type=pathlib.Path, default=None)
    ap.add_argument("--vram-dir", type=pathlib.Path, default=None)
    ap.add_argument("--io", type=pathlib.Path, default=None)
    ap.add_argument("--moments", nargs="*", default=list(MOMENTS))
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    if not args.vram and not args.vram_dir:
        print("ERR --vram or --vram-dir is required")
        return 2

    dumps = []
    if args.vram:
        dumps = [args.vram]
    if args.vram_dir:
        dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    if not dumps:
        print("ERR no VRAM dumps")
        return 2

    terrain = remake_terrain()
    originals = {name: original_map_cells(name) for name in args.moments}

    report = {"moments": {}, "frames": {},
              "anchor": {"map_px_x": REMAKE_MAP_ANCHOR[0],
                         "map_px_y": REMAKE_MAP_ANCHOR[1],
                         "map_width": MAP_WIDTH,
                         "map_height": MAP_HEIGHT,
                         "convention": "buffer px p holds map px "
                                       "((p + 256) mod 480, p)"}}
    best_per_moment: dict[str, tuple[int, dict]] = {}
    for path in dumps:
        vram = path.read_bytes()
        base = find_overlay_map(vram, terrain=terrain)
        if base < 0:
            # No overlay map in VRAM: the overlay is not displayed at all
            # (the action menu re-uses the map, or the overlay is off).
            # That is an *empty* overlay, not a missing measurement.
            entry_map = [[0] * 32 for _ in range(32)]
            anchor_x = REMAKE_MAP_ANCHOR[0]
            anchor_y = REMAKE_MAP_ANCHOR[1]
            cells: dict[tuple[int, int], str] = {}
        else:
            entry_map = remake_entry_map(vram, base)
            anchor_x, anchor_y, cells = best_window(entry_map, terrain)
        report["frames"][path.name] = {
            "overlay_map": base,
            "anchor_x": anchor_x,
            "anchor_y": anchor_y,
            # deprecated aliases: the anchor used to be a searched "window"
            "window_x": anchor_x,
            "window_y": anchor_y,
            "anchor_diagnostic": dict(BEST_WINDOW_DIAGNOSTIC),
        }
        for name, original in originals.items():
            result = compare(original, cells)
            key = (result["both_lit"] - result["family_mismatches"],
                   -result["residual"])
            if name not in best_per_moment or key > best_per_moment[name][0]:
                best_per_moment[name] = (key, {
                    "frame": path.name,
                    "overlay_map": base,
                    "anchor_x": anchor_x,
                    "anchor_y": anchor_y,
                    "window_x": anchor_x,
                    "window_y": anchor_y,
                    **{k: v for k, v in result.items() if k != "differences"},
                })

    for name in args.moments:
        if name not in best_per_moment:
            print(f"=== {name}: no remake frame with an overlay map")
            continue
        row = best_per_moment[name][1]
        report["moments"][name] = row
        print(f"=== {name} ===")
        print(f"  frame {row['frame']}  overlay map 0x{row['overlay_map']:05X}  "
              f"anchor ({row['anchor_x']}, {row['anchor_y']})")
        print(f"  original lit {row['original_lit']}  remake lit {row['remake_lit']}  "
              f"both {row['both_lit']}")
        print(f"  original-only {row['original_only']}  remake-only {row['remake_only']}  "
              f"family mismatches {row['family_mismatches']}  "
              f"residual {row['residual']}  exact {row['exact']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
