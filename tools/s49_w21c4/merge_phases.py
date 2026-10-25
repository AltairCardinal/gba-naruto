#!/usr/bin/env python3
"""Merge wave 21 / C2's phase table into wave 21 / C4's presentation timing JSON.

C2 measured the per-beat phase of both walks (original and remake) and found
the phase-chain break: the original's ``step-20`` is still ``turn_banner``
("please wait" box) where the chain predicts ``unit_selection``.
``notes/s49-fidelity/W21-C4-original-presentation.md`` needs that phase
annotation next to every measured frame and beat, so this script merges it
into the same machine readable document.

Usage
-----
    python tools/s49_w21c4/merge_phases.py \
        --c4 build/w21-c4/original-presentation-timing.json \
        --c2 build/w21-c2/press-phase-table.json
"""

from __future__ import annotations

import argparse
import json
import pathlib


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--c4", type=pathlib.Path,
                        default=pathlib.Path(
                            r"D:\Github\gba-naruto\build\w21-c4\original-presentation-timing.json"))
    parser.add_argument("--c2", type=pathlib.Path,
                        default=pathlib.Path(
                            r"D:\Github\gba-naruto\build\w21-c2\press-phase-table.json"))
    args = parser.parse_args()

    doc = json.loads(args.c4.read_text(encoding="utf-8"))
    c2 = json.loads(args.c2.read_text(encoding="utf-8"))

    orig_phase = {f"step-{row['step']:02d}-A.png": row for row in c2["original"]}
    remake_phase = {f"step-{row['step']:02d}-A.png": row for row in c2["remake"]}
    orig_phase["step-00-base.png"] = orig_phase.get("step-00-A.png", {})

    for side, table in (("original_beats", orig_phase), ("remake_beats", remake_phase)):
        for name, row in doc[side].items():
            info = table.get(name, {})
            for key in ("phase", "scene_frame", "round", "cursor", "selected_unit",
                        "selected_command", "press_index", "match_remake_step",
                        "match_field_px", "chain_remake_step", "chain_remake_phase"):
                if key in info:
                    row[key] = info[key]

    matrix = {}
    for name, row in doc["original_beats"].items():
        matrix[name] = {
            "phase": row.get("phase"),
            "move_grid_on_screen": row["move_grid"],
            "red_arrow": row["red_arrow"],
            "select_hud": row["select_hud"],
            "red_arrow_px": row["red_arrow_px"],
            "red_arrow_clusters": row["red_arrow_clusters"],
            "hud_bright_px": row["hud_bright_px"],
        }
    doc["original_transition_matrix"] = matrix
    doc["notes"] = {
        "anchor": "C2's walk offset (+4) holds only up to original step 18; from "
                  "original step 19 on the original runs a round-1 banner -> 'please "
                  "wait' -> camera pan transition that the remake does not implement, "
                  "so the offset drifts to +1 by original step 23.",
        "beat_to_dense_frame": "each dense window is one A press; window "
                               "'step-X-to-Y' contains beat X+1 at f043 and beat X+2 "
                               "at f090.",
        "png_vs_savestate": "the settled PNG and the .ss9 of the same step are NOT "
                             "the same moment: decoding the original's BG2 overlay "
                             "tilemap of step-22-A.ss9 and projecting it with that "
                             "savestate's BG2 scroll (hofs=184, vofs=40) lands on "
                             "plain grass pixels in step-22-A.png.  The screen level "
                             "numbers are therefore the authoritative ones; the VRAM "
                             "census only records the game's overlay *intent* at the "
                             "savestate moment.",
    }
    doc["vram_census"] = "build/w21-c4/overlay-vram-census.json"

    with open(args.c4, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=1)
    print(f"merged -> {args.c4}")
    for name, row in matrix.items():
        print(f"  {name:22s} phase={str(row['phase']):18s} grid={row['move_grid_on_screen']} "
              f"arrow={row['red_arrow']} hud={row['select_hud']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
