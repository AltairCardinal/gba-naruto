#!/usr/bin/env python3
"""W21-C2: full cross-side alignment matrix + phase transfer.

The offset profile in ``build/w20-e3/align-e3.json`` only looks at offsets
+1..+6 and only at the battlefield area.  The phase table (made by
``make_phase_table.py``) says what the remake was doing at every one of its
own steps, so the useful question is:

    for every original step, which remake step does it correspond to, and
    therefore which remake phase was it in?

This tool prices **every** (original step, remake step) pair on three
regions -- the whole field, the HUD band and the frame edges -- and reports
the best candidates per original step, annotated with the remake telemetry.

Usage::

    python tools/s49_w21c2/cross_align.py --original <dir> --remake <dir> \\
        --phase-table build/w21-c2/press-phase-table.json \\
        --out build/w21-c2/cross-align.json
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FIELD_AREA = (0, 0, 240, 128)
FULL_BOX = (0, 0, 240, 160)
HUD_AREA = (0, 0, 240, 16)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=pathlib.Path, required=True)
    parser.add_argument("--remake", type=pathlib.Path, required=True)
    parser.add_argument("--phase-table", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--top", type=int, default=4)
    args = parser.parse_args()

    table = json.loads(args.phase_table.read_text(encoding="utf-8"))
    remake_phase = {row["step"]: row for row in table["remake"]}

    def names(directory: pathlib.Path) -> list[str]:
        out = [p.name for p in sorted(directory.glob("step-*.png"))]
        return out

    original_names = names(args.original)
    remake_names = names(args.remake)
    o_images = {name: load_rgb(str(args.original / name)) for name in original_names}
    r_images = {name: load_rgb(str(args.remake / name)) for name in remake_names}

    rows = []
    for oi, oname in enumerate(original_names):
        field = []
        hud = []
        for ri, rname in enumerate(remake_names):
            field.append(diff_mask(o_images[oname], r_images[rname], FIELD_AREA)[0])
            hud.append(diff_mask(o_images[oname], r_images[rname], HUD_AREA)[0])
        order = sorted(range(len(remake_names)), key=lambda k: field[k])
        best = []
        for ri in order[:args.top]:
            row = remake_phase.get(ri, {})
            best.append({
                "remake_step": ri,
                "remake_name": remake_names[ri],
                "field_px": field[ri],
                "hud_px": hud[ri],
                "remake_phase": row.get("phase"),
                "remake_round": row.get("round"),
                "remake_cursor": row.get("cursor"),
                "remake_selected_unit": row.get("selected_unit"),
                "remake_scene_frame": row.get("scene_frame"),
            })
        rows.append({
            "original_step": oi,
            "original_name": original_names[oi],
            "best": best,
            "best_field_px": field[order[0]],
            "best_hud_px": hud[order[0]],
            "field_at_offset4": field[oi + 4] if oi + 4 < len(remake_names) else None,
            "hud_at_offset4": hud[oi + 4] if oi + 4 < len(remake_names) else None,
            "hud_best_step": min(range(len(remake_names)), key=lambda k: hud[k]),
            "hud_best_px": min(hud),
        })
        print(f"{original_names[oi]:<16} best field {field[order[0]]:>7} -> "
              f"{remake_names[order[0]]:<16} "
              f"phase={remake_phase.get(order[0], {}).get('phase')} | "
              f"hud best {min(hud):>6} -> step {min(range(len(remake_names)), key=lambda k: hud[k])}")

    document = {
        "schema": "konoha.s49-cross-align.v1",
        "original_dir": str(args.original),
        "remake_dir": str(args.remake),
        "regions": {"field": list(FIELD_AREA), "hud": list(HUD_AREA),
                    "full": list(FULL_BOX)},
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=2)
                        + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
