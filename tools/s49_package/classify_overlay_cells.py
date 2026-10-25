#!/usr/bin/env python3
"""Classify the remaining overlay family mismatches **cell by cell**.

Why this tool exists
--------------------
The shared instrument (``tools/s49_overlay_align/compare_overlay_families.py``)
keeps only the aggregate counters for the best frame of every moment; its
``differences`` list is dropped when the report is written.  The 1:1 report has
to give every remaining mismatch a **property verdict**, and a verdict needs
the per-cell rows.

This tool re-runs the *very same* comparison in-process -- it **imports** the
shared instrument read-only and copies its frame loop and its best-frame
selection rule verbatim -- and keeps the per-cell differences.  The shared
file is never modified.

The three verdicts
------------------
``原版尾部残留`` (stale tail of the original's buffer)
    The cell is the original overlay buffer's **wrap tail**: the buffer is
    256 px wide, the battle-14 map is 480 px wide and the buffer is anchored
    at map pixel 256, so the buffer's logical columns 14 and 15 hold the
    map's **first** 32 px, i.e. the map's column 0.  Measured content there is
    *stale* (a cursor or a reachable set on a column whose terrain is a wall)
    and therefore not part of the current map space -- no faithful remake can
    reproduce it.

``walk 相位`` (walk phase / game state)
    The original's picture of this moment shows a set of **phase families**
    (``hatch`` = the teal reachable set, ``band`` = the yellow cursor,
    ``line_alt`` = the orange target range, ``hatch_shift`` = the green
    variant -- G-H15: 青/橙/绿/黄 are all phase families) and **no** frame of
    the remake's walk shows that same set of phase families.  The remake's
    walk therefore never reaches the phase the original's picture was taken
    in: every mismatching cell of that moment is a walk-phase difference and
    **no overlay rule can close it**.

``产品差`` (product difference)
    Everything else: both sides paint the cell but with a different family, or
    one side paints a family the other side does have (but not at that cell).
    This is the class where a rule or a unit occupancy differs.

Usage::

    python tools/s49_package/classify_overlay_cells.py \
        --vram-dir build/s49-package-y4/evidence/overlay/vram \
        --out build/s49-package-y4/evidence/overlay/cell-classification.json
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
from collections import Counter

# ``os.path.abspath``, not ``Path.resolve()``: the repository is reached through
# a directory junction (D:\Github\gba-naruto -> D:\Shell\gba-naruto) and
# resolving it would report the junction target instead of the path the user
# actually invoked.
HERE = pathlib.Path(os.path.abspath(__file__)).parent
REPO = HERE.parent.parent
SHARED = REPO / "tools" / "s49_overlay_align" / "compare_overlay_families.py"

# The map's columns 0 and 1: where the original's buffer wrap tail lands.
# The buffer is 256 px wide, the battle-14 map is 480 px wide and the buffer is
# anchored at map pixel 256, so the buffer's logical columns 14 and 15 hold
# the map's first 32 px = the map's logical columns 0 and 1.
TAIL_MAP_COLUMNS = (0, 1)
# Families that only exist in one phase of the walk: hatch = the teal
# reachable set, band = the yellow cursor, line_alt = the orange target range,
# hatch_shift = the green variant (G-H15: 青/橙/绿/黄 are all phase families).
PHASE_FAMILIES = ("hatch", "band", "line_alt", "hatch_shift")

CLASS_TAIL = "原版尾部残留"
CLASS_PHASE = "walk 相位"
CLASS_PRODUCT = "产品差"

CLASS_RULES = {
    CLASS_TAIL: (
        "地图逻辑列 0/1 —— 原版覆盖层缓冲的回绕尾部（缓冲 px 224..255 = "
        "地图第 0/1 列）。该处装的是**陈旧内容**（墙列上出现光标格 / 可达集），"
        "不是当前地图空间的内容 ⇒ 任何忠实的重制都复现不了。"),
    CLASS_PHASE: (
        "**相位错位**：原版该时刻的画面同时具备一组相位族"
        "（hatch=青 / band=黄 / line_alt=橙 / hatch_shift=绿），"
        "而重制侧的 35 帧里**没有任何一帧**同时具备这组相位族 "
        "⇒ 重制侧的 walk **从未走到**原版那个相位 "
        "⇒ 差的是走位/相位结构，不是覆盖层规则。"),
    CLASS_PRODUCT: (
        "两侧**同相位**下仍然逐格不同（族名对不同，或某一侧单独点亮）"
        "⇒ 规则或单位占位等**产品差**。"),
}


def load_shared() -> object:
    """Import the shared instrument read-only (its file is never touched)."""
    spec = importlib.util.spec_from_file_location(
        "s49_shared_overlay_families", SHARED)
    if spec is None or spec.loader is None:
        raise SystemExit(f"ERR cannot import {SHARED}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vram-dir", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    if not args.vram_dir.is_dir():
        print(f"ERR no such vram dir: {args.vram_dir}")
        return 2
    dumps = sorted(args.vram_dir.glob("*.vram-*.bin"))
    if not dumps:
        print(f"ERR no VRAM dumps in {args.vram_dir}")
        return 2

    shared = load_shared()
    terrain = shared.remake_terrain()
    originals = {name: shared.original_map_cells(name) for name in shared.MOMENTS}
    original_families = {
        name: Counter(cells.values()) for name, cells in originals.items()}

    # ---- the shared tool's frame loop, copied verbatim ------------------
    best_per_moment: dict[str, tuple[tuple, dict]] = {}
    frame_families: dict[str, set[str]] = {}
    frame_phases: dict[str, set[str]] = {}
    for path in dumps:
        vram = path.read_bytes()
        base = shared.find_overlay_map(vram, terrain=terrain)
        if base < 0:
            cells: dict[tuple[int, int], str] = {}
        else:
            entry_map = shared.remake_entry_map(vram, base)
            _anchor_x, _anchor_y, cells = shared.best_window(entry_map, terrain)
        frame_families[path.name] = set(cells.values())
        frame_phases[path.name] = set(cells.values()) & set(PHASE_FAMILIES)
        for name, original in originals.items():
            result = shared.compare(original, cells)
            key = (result["both_lit"] - result["family_mismatches"],
                   -result["residual"])
            if name not in best_per_moment or key > best_per_moment[name][0]:
                best_per_moment[name] = (key, {
                    "frame": path.name,
                    "overlay_map": base,
                    **{k: v for k, v in result.items() if k != "differences"},
                    "_differences": result["differences"],
                })

    moments = {}
    for name, (_key, row) in best_per_moment.items():
        differences = row.pop("_differences")
        original_families_in_moment = original_families.get(name) or Counter()
        remake_families_in_frame = frame_families.get(row["frame"]) or set()
        # ---- the phase-shift test -------------------------------------
        # The original's picture of this moment shows a set of **phase
        # families** (hatch = the teal reachable set, band = the yellow
        # cursor, line_alt = the orange target range, hatch_shift = the green
        # variant).  If **no** frame of the remake's walk shows that same set
        # of phase families, then the remake's walk never reaches the phase
        # the original's picture was taken in: every mismatching cell is a
        # walk-phase difference and no overlay rule can close it.
        original_phase_set = {
            family for family in PHASE_FAMILIES
            if original_families_in_moment.get(family, 0) > 0}
        phase_matching_frames = [
            frame for frame, families in frame_phases.items()
            if original_phase_set <= families]
        phase_shifted = not phase_matching_frames
        cells_out = []
        classes = Counter()
        pairs = Counter()
        for entry in differences:
            map_lx = entry.get("map_lx")
            original_family = entry.get("original")
            remake_family = entry.get("remake")
            pairs[(original_family, remake_family)] += 1
            if map_lx in TAIL_MAP_COLUMNS:
                verdict = CLASS_TAIL
            elif phase_shifted:
                verdict = CLASS_PHASE
            else:
                verdict = CLASS_PRODUCT
            classes[verdict] += 1
            cells_out.append({
                "map_lx": map_lx,
                "map_ly": entry.get("map_ly"),
                "original": original_family,
                "remake": remake_family,
                "class": verdict,
            })
        cells_out.sort(key=lambda item: (item["map_lx"], item["map_ly"]))
        moments[name] = {
            "frame": row["frame"],
            "overlay_map": row.get("overlay_map"),
            "both_lit": row.get("both_lit"),
            "original_only": row.get("original_only"),
            "remake_only": row.get("remake_only"),
            "family_mismatches": row.get("family_mismatches"),
            "residual": row.get("residual"),
            "exact": row.get("exact"),
            "classes": {key: classes.get(key, 0) for key in
                        (CLASS_TAIL, CLASS_PHASE, CLASS_PRODUCT)},
            "phase_set_original": sorted(original_phase_set),
            "phase_set_best_frame": sorted(
                remake_families_in_frame & set(PHASE_FAMILIES)),
            "phase_shifted": phase_shifted,
            "frames_matching_phase_set": len(phase_matching_frames),
            "pairs": {f"{a}->{b}": count
                      for (a, b), count in sorted(pairs.items())},
            "remake_frame_families": sorted(remake_families_in_frame),
            "original_moment_families": dict(original_families_in_moment),
            "cells": cells_out,
        }

    document = {
        "schema": "konoha.s49-package.overlay-cell-classification.v1",
        "generated_at": datetime.datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "label": args.label,
        "instrument": "tools/s49_package/classify_overlay_cells.py",
        "shared_instrument": "tools/s49_overlay_align/"
                             "compare_overlay_families.py",
        "shared_instrument_sha256": sha256_file(SHARED),
        "vram_dir": str(args.vram_dir),
        "dump_count": len(dumps),
        "map_width_px": shared.MAP_WIDTH,
        "map_height_px": shared.MAP_HEIGHT,
        "tail_map_columns": list(TAIL_MAP_COLUMNS),
        "phase_families": list(PHASE_FAMILIES),
        "class_rules": CLASS_RULES,
        "moments": moments,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(document, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")

    for name, row in moments.items():
        print(f"=== {name} (frame {row['frame']}) ===")
        print(f"  both {row['both_lit']}  original-only {row['original_only']}"
              f"  remake-only {row['remake_only']}"
              f"  family mismatches {row['family_mismatches']}"
              f"  residual {row['residual']}  exact {row['exact']}")
        print("  classes: " + "  ".join(
            f"{key} {value}" for key, value in row["classes"].items()))
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
