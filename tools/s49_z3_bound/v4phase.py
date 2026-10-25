"""Locate the phase the remake is missing -- the 50 "field" overlay cells.

    python tools/s49_z3_bound/v4phase.py \
        --walk build/s49-v4/walk --out build/s49-v4/phase-v4.json

What Z3 decided, and what is still open
---------------------------------------
Z3 proved that the 130 "walk phase" cells split into two kinds:

* ``grid16``'s 80 cells: the **original's** exported frame is a single frame
  transient (a half refreshed buffer).  Nothing to fix.
* ``field``'s 50 cells: the original's frame is a **stable state** that the
  remake never shows -- the remake's 783 frame walk contains **0** frames with
  the original's phase family set ``{band, hatch, line_alt}``
  (yellow cursor + teal move range + orange attack range).

Z3 did **not** decide *which* phase it is, *where* in the battle it belongs,
and -- the decisive question -- whether it is a **product** gap (the remake's
own range rule can never draw the three families together) or a **walk** gap
(the rule can draw it, the walk just never got there).

This tool decides it from the two dense walks:

1. it builds a **timeline** of both sides: for every captured frame the phase
   family set (the same map space decoder Z3 used, so the numbers are
   comparable), the family histogram, the camera, the acting unit pointer and
   the scene class;
2. it finds every **maximal run** of frames that carry the original's phase
   set, on both sides;
3. it looks for the frame of the remake that corresponds to the original's
   run (same acting pointer, same camera, same scene) and reports what the
   remake draws there.

The output is a receipt with no wall clock time, so two runs over the same
recording are byte identical.

Everything is read-only: the dense walks recorded by ``z3record.py`` and the
shared instruments (``tools/s49_pairing``, ``tools/s49_fidelity_report``,
``tools/s49_overlay_align``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "s49_z3_bound"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from s49_fidelity_report.pixels import load_rgb, screen_stats  # noqa: E402
from s49_pairing import anchors as anchors_module  # noqa: E402
from s49_pairing import savestate as savestate_module  # noqa: E402

from s49_z3_bound import z3phase  # noqa: E402

# The original's phase family set at the "field" moment: yellow cursor (band)
# + teal move range (hatch) + orange attack range (line_alt).
FIELD_PHASE = ("band", "hatch", "line_alt")

# The overlay families, with the role the original gives them
# (tools/s49_rule_probe/overlay_ground_truth.py).
FAMILY_ROLE = {
    "blank": "grid-nothing",
    "edge": "grid",
    "hatch": "move",
    "line_alt": "attack_range",
    "band": "cursor",
    "hatch_shift": "move_shift",
    "solid": "blocked",
}

# The frames of one beat: the recording takes the base frame, then for every
# beat ``per_beat`` frames (the inner samples plus the beat end).
PER_BEAT = 23
# The remake's prefix beats (Down, Down, A, A) navigate into the battle; the
# original starts at the battle entry.
REMAKE_PREFIX_BEATS = 4


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def frame_index(name: str) -> int:
    """``step-0123-in.png`` -> 123."""
    stem = pathlib.Path(name).stem
    parts = stem.split("-")
    return int(parts[1])


def beat_of(index: int) -> dict:
    """The beat a recorded frame belongs to.

    ``index`` is the number in the file name.  ``0`` is the base frame, the
    frames of beat ``k`` are the indices ``23(k-1)+1 .. 23k`` and the frame
    with the index ``23k`` is the **beat end** (the one the judgment bench
    calls the beat's canonical frame).
    """
    if index == 0:
        return {"beat": 0, "kind": "base", "semantic_beat": None}
    beat = (index - 1) // PER_BEAT + 1
    kind = "beat" if index % PER_BEAT == 0 else "in"
    return {"beat": beat, "kind": kind, "semantic_beat": beat}


def timeline(side: str, directory: pathlib.Path, terrain, shared,
             cells_by_frame: dict | None = None) -> list[dict]:
    """The per frame timeline of one side of the walk."""
    records = []
    for png in sorted(directory.glob("step-*.png")):
        state_path = png.with_suffix(".ss9")
        if not state_path.exists():
            continue
        state = savestate_module.load(state_path)
        data = savestate_module.regions(state)
        registers = savestate_module.io_registers(data["io"])
        raw = data["ewram"][anchors_module.ACTING_OFFSET[side]]
        acting = raw - anchors_module.ACTING_BASE[side]
        image = load_rgb(png)
        screen = screen_stats(image)
        bright = anchors_module._bright_share(image)
        if side == "original":
            _grid, cells = z3phase.original_map_cells_from_vram(data["vram"])
        else:
            cells = z3phase.remake_cells(data["vram"], terrain, shared)
        index = frame_index(png.name)
        beat = beat_of(index)
        semantic = beat["semantic_beat"]
        if semantic is not None and side == "remake":
            semantic = semantic - REMAKE_PREFIX_BEATS
        if cells_by_frame is not None:
            cells_by_frame[png.name] = cells
        records.append({
            "frame": png.name,
            "index": index,
            "beat": beat["beat"],
            "kind": beat["kind"],
            "semantic_beat": semantic,
            "phase_set": z3phase.phase_set(cells),
            "map_lit_cells": len(cells),
            "families": dict(sorted(Counter(cells.values()).items())),
            "camera_v": registers["bg_vofs"],
            "camera_h": registers["bg_hofs"],
            "acting": acting,
            "scene": anchors_module.scene_of(screen, bright),
        })
    return records


def runs(records: list[dict], wanted) -> list[dict]:
    """Every maximal run of **consecutive** records carrying the phase set."""
    wanted = set(wanted)
    result = []
    current = None
    for record in records:
        if wanted <= set(record["phase_set"]):
            if current is None:
                current = {"first_index": record["index"], "last_index": record["index"],
                           "frames": 0, "beats": [], "acting": [], "camera_v": [],
                           "scenes": [], "first_frame": record["frame"],
                           "last_frame": record["frame"]}
            current["last_index"] = record["index"]
            current["frames"] += 1
            current["last_frame"] = record["frame"]
            current["beats"].append(record["semantic_beat"])
            current["acting"].append(record["acting"])
            current["camera_v"].append(record["camera_v"])
            current["scenes"].append(record["scene"])
        else:
            if current is not None:
                result.append(current)
                current = None
    if current is not None:
        result.append(current)
    for row in result:
        row["beats"] = sorted({value for value in row["beats"] if value is not None})
        row["acting"] = sorted(set(row["acting"]))
        row["camera_v"] = sorted({tuple(value) for value in row["camera_v"]})
        row["camera_v"] = [list(value) for value in row["camera_v"]]
        row["scenes"] = sorted(set(row["scenes"]))
    return result


def phase_inventory(records: list[dict]) -> list[dict]:
    """Every phase family set the side shows, with how long it shows it."""
    counter = Counter(tuple(record["phase_set"]) for record in records)
    rows = []
    for families, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])):
        sample = next(record for record in records
                      if tuple(record["phase_set"]) == families)
        rows.append({
            "phase_set": list(families),
            "frames": count,
            "beats": sorted({record["semantic_beat"] for record in records
                             if tuple(record["phase_set"]) == families
                             and record["semantic_beat"] is not None}),
            "acting": sorted({record["acting"] for record in records
                               if tuple(record["phase_set"]) == families}),
            "scenes": sorted({record["scene"] for record in records
                              if tuple(record["phase_set"]) == families}),
            "sample_frame": sample["frame"],
            "sample_lit_cells": sample["map_lit_cells"],
        })
    return rows


def beat_table(records: list[dict]) -> list[dict]:
    """One row per beat: the state the side is in during that beat."""
    rows = []
    beats = sorted({record["beat"] for record in records})
    for beat in beats:
        inside = [record for record in records if record["beat"] == beat]
        end = next(record for record in inside if record["kind"] == "beat") \
            if any(record["kind"] == "beat" for record in inside) else inside[-1]
        counter = Counter(tuple(record["phase_set"]) for record in inside)
        families = Counter()
        for record in inside:
            families.update(record["families"])
        rows.append({
            "beat": beat,
            "semantic_beat": end["semantic_beat"],
            "frames": len(inside),
            "frame_range": [inside[0]["index"], inside[-1]["index"]],
            "camera_v_at_beat_end": end["camera_v"],
            "camera_h_at_beat_end": end["camera_h"],
            "scenes": sorted({record["scene"] for record in inside}),
            "acting": sorted({record["acting"] for record in inside}),
            "phase_sets": [{"phase_set": list(families_), "frames": count}
                           for families_, count in sorted(counter.items(),
                                                        key=lambda kv: (-kv[1], kv[0]))],
            "lit_cells_at_beat_end": end["map_lit_cells"],
            "families_at_beat_end": end["families"],
            "family_totals": dict(sorted(families.items())),
        })
    return rows


def family_pairs(comparison: dict) -> list[dict]:
    """The per cell family pairs of a comparison, counted."""
    counter = Counter((row["original"], row["remake"]) for row in comparison["differences"])
    return [{"original": pair[0], "remake": pair[1], "cells": count}
            for pair, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]


def same_moment_comparison(original_cells: dict, records: list[dict],
                            cells_by_frame: dict, shared) -> dict:
    """The original's field frame against **every** remake frame.

    The wave 13 package compared the original's field frame against the remake's
    **best** frame in the 35 frame package walk, which turned out to be a
    *move phase* frame (teal only).  This walks the whole dense recording
    instead, so the comparison can be repeated against the remake's **own
    settlement frames** -- the frames that are at the same game moment.
    """
    rows = []
    for record in records:
        cells = cells_by_frame.get(record["frame"], {})
        if not cells:
            continue
        comparison = shared.compare(original_cells, cells)
        rows.append({
            "frame": record["frame"],
            "beat": record["beat"],
            "semantic_beat": record["semantic_beat"],
            "phase_set": record["phase_set"],
            "camera_v": record["camera_v"],
            "residual": comparison["residual"],
            "original_lit": comparison["original_lit"],
            "remake_lit": comparison["remake_lit"],
            "both_lit": comparison["both_lit"],
            "original_only": comparison["original_only"],
            "remake_only": comparison["remake_only"],
            "family_mismatches": comparison["family_mismatches"],
            "pairs": family_pairs(comparison),
        })
    rows.sort(key=lambda row: (row["residual"], row["frame"]))

    by_phase = {}
    for row in rows:
        key = "+".join(row["phase_set"]) if row["phase_set"] else "(none)"
        if key not in by_phase:
            by_phase[key] = {
                "phase_set": row["phase_set"],
                "frames_compared": 0,
                "best": row,
                "best_residual": row["residual"],
            }
        by_phase[key]["frames_compared"] += 1
        if row["residual"] < by_phase[key]["best_residual"]:
            by_phase[key]["best"] = row
            by_phase[key]["best_residual"] = row["residual"]
    return {"compared_frames": len(rows),
            "overall_best": rows[0] if rows else None,
            "best_per_phase_set": by_phase}


def original_field_moment() -> dict:
    """The original's own ``field`` capture: its phase set and its state."""
    shared = z3phase.load_shared()
    row = z3phase.analyse_moment("field-frame-v1", shared)
    exported = row["exported_frame"]
    capture_dir = pathlib.Path(row["capture_dir"])
    index = int(exported["frame"].split("-")[1])
    vram = (capture_dir / f"vram-{index:02d}.bin").read_bytes()
    _grid, cells = z3phase.original_map_cells_from_vram(vram)
    return {
        "capture_dir": row["capture_dir"],
        "input_state": row["input_state"],
        "exported_frame": exported["frame"],
        "exported_phase_set": exported["phase_set"],
        "exported_map_lit_cells": exported["map_lit_cells"],
        "exported_families": exported["map_families"],
        "exported_bg_vofs": exported["bg_vofs"],
        "exported_bg_hofs": exported["bg_hofs"],
        "frames_with_same_grid_digest": row["frames_with_same_grid_digest"],
        "consecutive_frames_captured": row["captured_frames"],
        "exported_cells": {f"{key[0]},{key[1]}": family
                           for key, family in sorted(cells.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--walk", type=pathlib.Path,
                        default=REPO / "build" / "s49-v4" / "walk")
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-v4" / "phase-v4.json")
    parser.add_argument("--walk-id", default=None)
    args = parser.parse_args(argv)

    original_dir = args.walk / "dense-original"
    remake_dir = args.walk / "dense-remake"
    for required in (original_dir, remake_dir):
        if not required.is_dir():
            raise SystemExit(f"ERR missing the dense walk: {required}")

    shared = z3phase.load_shared()
    terrain = shared.remake_terrain()

    original_cells: dict = {}
    original = timeline("original", original_dir, terrain, shared)
    remake_cells_by_frame: dict = {}
    remake = timeline("remake", remake_dir, terrain, shared,
                      cells_by_frame=remake_cells_by_frame)
    if not original or not remake:
        raise SystemExit("ERR the dense walk is empty")

    field_moment = original_field_moment()
    wanted = field_moment["exported_phase_set"]

    # The original's field frame as map space cells, for the cell level
    # comparison against the remake's frames.
    for key, family in field_moment["exported_cells"].items():
        lx, ly = key.split(",")
        original_cells[(int(lx), int(ly))] = family
    comparison = same_moment_comparison(original_cells, remake,
                                        remake_cells_by_frame, shared)

    original_runs = runs(original, wanted)
    remake_runs = runs(remake, wanted)

    # The frames of the original's run, and the state they carry.
    original_run_detail = []
    for row in original_runs:
        inside = [record for record in original
                  if row["first_index"] <= record["index"] <= row["last_index"]]
        camera_values = [list(value) for value in
                         sorted({tuple(record["camera_v"]) for record in inside})]
        original_run_detail.append({
            **row,
            "acting_values": sorted({record["acting"] for record in inside}),
            "camera_v_values": camera_values,
            "semantic_beats": sorted({record["semantic_beat"] for record in inside
                                      if record["semantic_beat"] is not None}),
            "scenes": sorted({record["scene"] for record in inside}),
            "families": dict(sorted(Counter(
                family for record in inside
                for family in record["families"]).items())),
        })

    # What the remake draws at the same acting pointer and camera.
    acting_values = sorted({value for row in original_runs
                            for value in row["acting"]})
    remake_at_acting = []
    for acting in acting_values:
        frames = [record for record in remake if record["acting"] == acting]
        if not frames:
            continue
        counter = Counter(tuple(record["phase_set"]) for record in frames)
        remake_at_acting.append({
            "acting": acting,
            "frames": len(frames),
            "phase_sets": [{"phase_set": list(families), "frames": count}
                           for families, count in sorted(counter.items(),
                                                        key=lambda kv: (-kv[1], kv[0]))],
            "beats": sorted({record["semantic_beat"] for record in frames
                             if record["semantic_beat"] is not None}),
            "scenes": sorted({record["scene"] for record in frames}),
        })

    # The remake's own inventory: which family sets does it ever draw?
    remake_inventory = phase_inventory(remake)
    original_inventory = phase_inventory(original)

    # Can the two families coexist at all on the remake side?
    coexist = {
        "hatch_and_line_alt": sum(1 for record in remake
                                   if "hatch" in record["phase_set"]
                                   and "line_alt" in record["phase_set"]),
        "band_and_line_alt": sum(1 for record in remake
                                  if "band" in record["phase_set"]
                                  and "line_alt" in record["phase_set"]),
        "band_and_hatch": sum(1 for record in remake
                              if "band" in record["phase_set"]
                              and "hatch" in record["phase_set"]),
        "hatch_and_hatch_shift": sum(1 for record in remake
                                     if "hatch" in record["phase_set"]
                                     and "hatch_shift" in record["phase_set"]),
    }
    original_coexist = {
        "hatch_and_line_alt": sum(1 for record in original
                                   if "hatch" in record["phase_set"]
                                   and "line_alt" in record["phase_set"]),
        "band_and_line_alt": sum(1 for record in original
                                  if "band" in record["phase_set"]
                                  and "line_alt" in record["phase_set"]),
        "band_and_hatch": sum(1 for record in original
                              if "band" in record["phase_set"]
                              and "hatch" in record["phase_set"]),
        "hatch_and_hatch_shift": sum(1 for record in original
                                     if "hatch" in record["phase_set"]
                                     and "hatch_shift" in record["phase_set"]),
    }

    document = {
        "schema": "konoha.s49-v4.phase-locate/1",
        "walk": args.walk_id if args.walk_id else str(args.walk),
        "field_moment": field_moment,
        "field_phase_set": wanted,
        "same_moment_comparison": comparison,
        "family_roles": FAMILY_ROLE,
        "original": {
            "frames": len(original),
            "phase_sets_present": len(original_inventory),
            "inventory": original_inventory,
            "runs_with_field_phase": original_runs,
            "run_detail": original_run_detail,
            "coexistence": original_coexist,
            "beats": beat_table(original),
        },
        "remake": {
            "frames": len(remake),
            "phase_sets_present": len(remake_inventory),
            "inventory": remake_inventory,
            "runs_with_field_phase": remake_runs,
            "coexistence": coexist,
            "at_the_originals_acting_pointers": remake_at_acting,
            "beats": beat_table(remake),
        },
    }
    write_text(args.out, json.dumps(document, ensure_ascii=False, indent=1) + "\n")

    print(f"field phase set : {wanted}")
    print(f"original        : {len(original)} frames, "
          f"{len(original_runs)} run(s) with the field phase")
    for row in original_runs:
        print(f"   run frames {row['first_index']}..{row['last_index']} "
              f"({row['frames']} samples), beats {row['beats']}, "
              f"acting {row['acting']}, camera_v {row['camera_v']}")
    print(f"remake          : {len(remake)} frames, "
          f"{len(remake_runs)} run(s) with the field phase")
    print("remake coexistence: " + json.dumps(coexist))
    print("original coexistence: " + json.dumps(original_coexist))
    print("remake inventory:")
    for row in remake_inventory:
        print(f"   {str(row['phase_set']):58s} {row['frames']:4d} frames "
              f"beats={row['beats']} acting={row['acting']} scenes={row['scenes']}")
    print(f"wrote {args.out}")
    print("=== the original's field frame against the remake's frames ===")
    print(f"  compared {comparison['compared_frames']} remake frames")
    for key, row in comparison["best_per_phase_set"].items():
        best = row["best"]
        print(f"  phase [{key}] x{row['frames_compared']}: best residual "
              f"{row['best_residual']} at {best['frame']} "
              f"(semantic beat {best['semantic_beat']})")
        for pair in best["pairs"][:8]:
            print(f"      {pair['original']:>10s} -> {pair['remake']:<10s} "
                  f"{pair['cells']:4d} cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
