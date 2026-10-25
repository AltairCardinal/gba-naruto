"""What are the 130 "walk phase" overlay cells?  A decidable verdict.

    python tools/s49_z3_bound/z3phase.py \
        --out build/s49-z3-bound/phase.json

The question
------------
The Y2 and Y4 streams classified the remaining 176 overlay mismatches as

    original tail residue  44   /   walk phase  130   /   product gap  2

and justified the 130 with two claims:

* the original's ``field`` picture is a **stable state** that shows the teal
  (``hatch``) and the orange (``line_alt``) together, and **no** frame of the
  remake's 35 frame walk shows that combination;
* the original's ``grid16`` picture is a **single frame transient** (a half
  refreshed buffer).

Those are two different kinds of statement -- "the remake never reaches that
phase" versus "the original only shows that for one frame" -- and they have
different consequences.  This tool decides between them from **evidence that
can be checked**, not from an assertion:

1.  The original game was captured **six consecutive frames** at each of the
    four moments (``artifacts/s49-original-<moment>-frame-v1``: ``frame-00``
    .. ``frame-05`` with their VRAM and IO blocks).  Decoding the BG2 overlay
    of those six frames says directly whether the exported picture is a state
    that **persists** (stable) or one that occurs **once** (transient).

2.  The **same** question is then asked on the remake side: how many frames of
    the remake's recorded game-time line show the original's phase family set?

3.  The 130 cells are read back from the wave 13 package's per cell
    classification and split by the moment they belong to, so the verdict is
    tied to the exact cells the report quotes.

Everything is read-only: the original's own captures, the wave 13 package's
evidence, and the dense walk recorded for this stream.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import struct
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "s49_rule_probe"))

from s49_fidelity_report import overlay as overlay_module  # noqa: E402
from s49_fidelity_report.pixels import load_rgb, screen_stats  # noqa: E402
from s49_pairing import savestate as savestate_module  # noqa: E402

import overlay_ground_truth  # noqa: E402

SHARED = REPO / "tools" / "s49_overlay_align" / "compare_overlay_families.py"

# The families that only exist in one phase of the battle (G-H15):
# teal = the reachable set, orange = the target range, green = the shifted
# reachable set, yellow = the cursor.
PHASE_FAMILIES = ("hatch", "band", "line_alt", "hatch_shift")

# The original's four ground truth moments and the capture directory that
# holds their six consecutive frames.
MOMENT_CAPTURES = {
    "field-frame-v1": "s49-original-field-frame-v1",
    "movegrid-frame-v1": "s49-original-movegrid-frame-v1",
    "grid16-frame-v1": "s49-original-grid16-frame-v1",
    "banner-frame-v1": "s49-original-banner-frame-v1",
}

ARTIFACTS = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts")


def load_shared() -> object:
    """Import the shared overlay instrument read-only."""
    spec = importlib.util.spec_from_file_location(
        "s49_shared_overlay_families", SHARED)
    if spec is None or spec.loader is None:
        raise SystemExit(f"ERR cannot import {SHARED}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def original_tiles(vram: bytes) -> list[int]:
    """The original's BG2 overlay tilemap: 1024 tile indices."""
    entries = struct.unpack_from("<1024H", vram, 0x1000)
    return [entry & 0x3FF for entry in entries]


def original_map_cells_from_vram(vram: bytes) -> tuple[list, dict]:
    """The original's overlay of one frame as (buffer grid, map space cells).

    The buffer grid is the 16 x 16 logical cell grid the ground truth uses;
    the map space cells are the same cells placed in the map (the buffer is
    256 px wide, the map 480 px, the buffer is anchored at map pixel 256) --
    exactly the convention ``compare_overlay_families.original_map_cells``
    uses, so the numbers are comparable with the wave 13 package.
    """
    grid = overlay_module.original_grid(vram)
    cells: dict[tuple[int, int], str] = {}
    for ly in range(16):
        for lx in range(16):
            family = grid[ly][lx]
            if family == "blank":
                continue
            map_lx = ((256 + lx * 16) % 480) // 16
            map_ly = ((0 + ly * 16) % 304) // 16
            cells[(map_lx, map_ly)] = family
    return grid, cells


def phase_set(cells: dict) -> list[str]:
    """The phase families present in a cell map."""
    return sorted({family for family in cells.values()
                   if family in PHASE_FAMILIES})


def row_profile(grid: list) -> list[int]:
    """The number of lit logical cells per buffer row."""
    return [sum(1 for family in row if family != "blank") for row in grid]


def digest_grid(grid: list) -> str:
    payload = "\n".join("".join(row) for row in grid).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def analyse_moment(name: str, shared) -> dict:
    """The six consecutive frames of one original moment."""
    capture_dir = ARTIFACTS / MOMENT_CAPTURES[name]
    manifest = json.loads((capture_dir / "manifest.json").read_text("utf-8"))
    moment = overlay_ground_truth.load_moment(name)
    exported_tiles = [cell["tile"] for cell in moment.cells]

    frames = []
    exported_index = None
    for index in range(int(manifest["captured_frames"])):
        vram = (capture_dir / f"vram-{index:02d}.bin").read_bytes()
        io_bytes = (capture_dir / f"io-{index:02d}.bin").read_bytes()
        tiles = original_tiles(vram)
        grid, cells = original_map_cells_from_vram(vram)
        registers = savestate_module.io_registers(io_bytes)
        counts = Counter(cells.values())
        screen = screen_stats(load_rgb(capture_dir / f"frame-{index:02d}.png"))
        row = {
            "frame": f"frame-{index:02d}",
            "is_exported_frame": tiles == exported_tiles,
            "map_lit_cells": len(cells),
            "map_families": dict(sorted(counts.items())),
            "phase_set": phase_set(cells),
            "buffer_row_lit": row_profile(grid),
            "grid_digest": digest_grid(grid),
            "non_black_fraction": round(screen["non_black_fraction"], 4),
            "mean_rgb": screen.get("mean_rgb"),
            "distinct_colours": screen.get("unique_colours"),
            "dispcnt": registers["dispcnt"],
            "dispcnt_hex": f"0x{registers['dispcnt']:04X}",
            "bg_vofs": registers["bg_vofs"],
            "bg_hofs": registers["bg_hofs"],
            "bg_cnt": registers["bg_cnt"],
        }
        if row["is_exported_frame"]:
            exported_index = index
        frames.append(row)

    exported = frames[exported_index] if exported_index is not None else None
    same_phase = [row["frame"] for row in frames
                  if exported and row["phase_set"] == exported["phase_set"]]
    same_digest = [row["frame"] for row in frames
                   if exported and row["grid_digest"] == exported["grid_digest"]]
    same_lit = [row["frame"] for row in frames
                if exported and row["map_lit_cells"] == exported["map_lit_cells"]]
    return {
        "moment": name,
        "capture_dir": str(capture_dir),
        "capture_sha256_manifest": sha256_file(capture_dir / "manifest.json"),
        "input_state": manifest.get("input_state"),
        "settle_frames": manifest.get("settle_frames"),
        "captured_frames": len(frames),
        "exported_frame_index": exported_index,
        "exported_frame": exported,
        "frames_with_same_phase_set": len(same_phase),
        "frames_with_same_phase_set_names": same_phase,
        "frames_with_same_grid_digest": len(same_digest),
        "frames_with_same_grid_digest_names": same_digest,
        "frames_with_same_lit_count": len(same_lit),
        "frames": frames,
    }


def remake_cells(vram: bytes, terrain, shared) -> dict:
    """The remake's overlay of one frame as map space cells."""
    base = shared.find_overlay_map(vram, terrain=terrain)
    if base < 0:
        return {}
    entry_map = shared.remake_entry_map(vram, base)
    _anchor_x, _anchor_y, cells = shared.best_window(entry_map, terrain)
    return cells


def analyse_remake(dump_paths: list[pathlib.Path], terrain, shared) -> dict:
    """The phase family set of every frame of the remake's game-time line."""
    per_frame = []
    for path in dump_paths:
        cells = remake_cells(path.read_bytes(), terrain, shared)
        per_frame.append({
            "frame": path.name,
            "map_lit_cells": len(cells),
            "phase_set": phase_set(cells),
            "families": dict(sorted(Counter(cells.values()).items())),
        })
    return {"frames": per_frame, "count": len(per_frame)}


def analyse_original_dense(directory: pathlib.Path) -> dict:
    """The phase family set of every frame of the original's dense walk.

    The original's overlay lives on BG2 at a fixed VRAM offset, so the frame's
    overlay is read straight out of the savestate next to it -- no probe, no
    reinterpretation.
    """
    per_frame = []
    for png in sorted(directory.glob("step-*.png")):
        state_path = png.with_suffix(".ss9")
        if not state_path.exists():
            continue
        state = savestate_module.load(state_path)
        data = savestate_module.regions(state)
        _grid, cells = original_map_cells_from_vram(data["vram"])
        per_frame.append({
            "frame": png.name,
            "map_lit_cells": len(cells),
            "phase_set": phase_set(cells),
        })
    return {"frames": per_frame, "count": len(per_frame)}


def longest_run(frames: list[dict], wanted: list[str]) -> int:
    """The longest run of **consecutive** frames showing the phase set."""
    best = 0
    current = 0
    for frame in frames:
        if set(wanted) <= set(frame["phase_set"]):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=pathlib.Path,
                        default=REPO / "build" / "s49-z3-bound" / "phase.json")
    parser.add_argument("--package", type=pathlib.Path,
                        default=REPO / "build" / "s49-package-y4-final",
                        help="the wave 13 package directory")
    parser.add_argument("--dense-remake", type=pathlib.Path,
                        default=REPO / "build" / "s49-z3-bound" / "walk"
                               / "dense-remake")
    parser.add_argument("--dense-original", type=pathlib.Path,
                        default=REPO / "build" / "s49-z3-bound" / "walk"
                               / "dense-original")
    parser.add_argument("--skip-dense", action="store_true")
    args = parser.parse_args(argv)

    shared = load_shared()
    terrain = shared.remake_terrain()

    moments = {name: analyse_moment(name, shared) for name in MOMENT_CAPTURES}

    # ---- the remake side ------------------------------------------------
    vram_dir = args.package / "evidence" / "overlay" / "vram"
    dumps = sorted(vram_dir.glob("*.vram-*.bin"))
    if not dumps:
        raise SystemExit(f"ERR no VRAM dumps in {vram_dir}")
    package_side = analyse_remake(dumps, terrain, shared)

    dense_side = {"count": 0, "frames": []}
    original_dense = {"count": 0, "frames": []}
    if not args.skip_dense:
        dense_paths = sorted(args.dense_remake.glob("step-*.png"))
        dense_frames = []
        for png in dense_paths:
            state_path = png.with_suffix(".ss9")
            if not state_path.exists():
                continue
            state = savestate_module.load(state_path)
            data = savestate_module.regions(state)
            cells = remake_cells(data["vram"], terrain, shared)
            dense_frames.append({
                "frame": png.name,
                "map_lit_cells": len(cells),
                "phase_set": phase_set(cells),
            })
        dense_side = {"count": len(dense_frames), "frames": dense_frames}
        original_dense = analyse_original_dense(args.dense_original)

    # ---- the 130 cells --------------------------------------------------
    classification_path = (args.package / "evidence" / "overlay"
                           / "cell-classification.json")
    classification = json.loads(classification_path.read_text("utf-8"))
    phase_cells = {"原版尾部残留": 0, "walk 相位": 0, "产品差": 0}
    phase_by_moment = {}
    for name, row in classification["moments"].items():
        counts = Counter(cell["class"] for cell in row["cells"])
        for key in phase_cells:
            phase_cells[key] += counts.get(key, 0)
        phase_by_moment[name] = {
            "frame": row["frame"],
            "classes": dict(counts),
            "phase_set_original": row["phase_set_original"],
            "phase_set_best_frame": row["phase_set_best_frame"],
            "phase_shifted": row["phase_shifted"],
            "frames_matching_phase_set": row["frames_matching_phase_set"],
            "original_moment_families": row["original_moment_families"],
        }

    # ---- the verdict ----------------------------------------------------
    verdicts = {}
    for name, row in moments.items():
        exported = row["exported_frame"]
        stable = row["frames_with_same_grid_digest"] >= 3
        verdicts[name] = {
            "exported_frame": exported["frame"] if exported else None,
            "exported_phase_set": exported["phase_set"] if exported else [],
            "exported_map_lit_cells": exported["map_lit_cells"] if exported else 0,
            "consecutive_frames_captured": row["captured_frames"],
            "frames_with_same_phase_set": row["frames_with_same_phase_set"],
            "frames_with_same_grid_digest": row["frames_with_same_grid_digest"],
            "verdict": "stable state" if stable else "single frame transient",
        }

    def count_phase_set(side: dict, wanted: list[str]) -> int:
        if not wanted:
            return 0
        return sum(1 for frame in side["frames"]
                   if set(wanted) <= set(frame["phase_set"]))

    reach = {}
    for name, row in moments.items():
        exported = row["exported_frame"]
        wanted = exported["phase_set"] if exported else []
        reach[name] = {
            "phase_set": wanted,
            "package_walk_frames": package_side["count"],
            "package_walk_frames_with_phase_set":
                count_phase_set(package_side, wanted),
            "dense_walk_frames": dense_side["count"],
            "dense_walk_frames_with_phase_set": count_phase_set(dense_side, wanted),
            "original_dense_walk_frames": original_dense["count"],
            "original_dense_walk_frames_with_phase_set":
                count_phase_set(original_dense, wanted),
            "original_dense_walk_longest_consecutive_run":
                longest_run(original_dense["frames"], wanted),
            "remake_dense_walk_longest_consecutive_run":
                longest_run(dense_side["frames"], wanted),
        }

    document = {
        "schema": "konoha.s49-z3.phase-attribution/1",
        "phase_families": list(PHASE_FAMILIES),
        "original_moments": moments,
        "remake_package_walk": package_side,
        "remake_dense_walk": dense_side,
        "original_dense_walk": original_dense,
        "cell_classification": {
            "path": str(classification_path),
            "sha256": sha256_file(classification_path),
            "totals": phase_cells,
            "by_moment": phase_by_moment,
        },
        "verdicts": verdicts,
        "phase_reachability": reach,
    }
    write_text(args.out, json.dumps(document, ensure_ascii=False, indent=1) + "\n")

    print("=== the original's four moments (six consecutive frames each) ===")
    for name, row in verdicts.items():
        print(f"  {name:22s} exported={row['exported_frame']} "
              f"phase={row['exported_phase_set']} "
              f"lit={row['exported_map_lit_cells']:3d} "
              f"same_phase_set={row['frames_with_same_phase_set']}/{row['consecutive_frames_captured']} "
              f"same_grid={row['frames_with_same_grid_digest']}/{row['consecutive_frames_captured']} "
              f"=> {row['verdict']}")
    print("=== the remake's game-time line ===")
    for name, row in reach.items():
        print(f"  {name:22s} phase={row['phase_set']} "
              f"package walk {row['package_walk_frames_with_phase_set']}/{row['package_walk_frames']} "
              f"remake dense {row['dense_walk_frames_with_phase_set']}/{row['dense_walk_frames']} "
              f"original dense {row['original_dense_walk_frames_with_phase_set']}/{row['original_dense_walk_frames']} "
              f"(longest run original {row['original_dense_walk_longest_consecutive_run']}, "
              f"remake {row['remake_dense_walk_longest_consecutive_run']})")
    print(f"=== the 176 cells === {phase_cells}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
