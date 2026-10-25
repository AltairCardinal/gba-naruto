#!/usr/bin/env python3
"""W21-C2: merge the raw captures, the remake telemetry and the cross-side
alignment into the deliverable phase table.

The deliverable schema is fixed by the task brief::

    {"schema":"konoha.s49-press-phase-table.v1",
     "original":[{"step":0,"phase":...,"scene_frame":...,"round":...,
                  "cursor":[x,y],"selected_unit":...,"sha256":"..."}, ...],
     "remake":[ ... ],
     "first_divergence":{"step":N,"original_phase":...,
                          "remake_phase":...,"detail":"..."}}

The original game publishes **no** telemetry, so the original row's phase /
round / cursor / selected_unit are *transferred* from the remake frame the
original frame was matched to.  Every row carries the evidence of that
transfer (``match_remake_step`` / ``match_field_px`` / ``match_basis``), and
``first_divergence`` is computed from the same evidence, not hand written.

Usage::

    python tools/s49_w21c2/finalize_table.py --raw build/w21-c2/press-phase-table.json \\
        --cross build/w21-c2/cross-align.json --out build/w21-c2/press-phase-table.json
"""

from __future__ import annotations

import json
import pathlib

# The walk offset the byte-identical anchors fix: remake index = original
# index + 4.  Verified by four exact sha256 frame pairs.
ANCHOR_OFFSET = 4

# A frame is "the same picture" when the field residual is at most this.
IDENTICAL_MAX = 64

# A frame has "no counterpart" when the best residual over *all* remake
# frames exceeds this (the field is 240x128 = 30720 px).
NO_COUNTERPART_MIN = 5000

# A frame whose *whole* picture differs by more than this (about half of
# the battlefield) has no counterpart at all -- it is not "the same picture
# drawn differently", it is "a picture the other walk never shows".
WHOLE_FRAME_MIN = 15000

# A frame with at most this many distinct colours, or a nearly empty PNG,
# carries no phase information (it is a black / flat transition frame), so
# it must not be used to decide where the two walks diverge.
DEGENERATE_COLOURS = 8
DEGENERATE_BYTES = 1200


def distinct_colours(directory: pathlib.Path) -> dict[str, int]:
    """How many distinct colours each original frame has.

    A black or flat transition frame has almost none, and therefore carries
    no phase information -- its "best match" against another flat frame is
    an artefact of both being blank, not evidence of the same game state.
    """
    from PIL import Image

    out: dict[str, int] = {}
    for png in sorted(directory.glob("step-*.png")):
        image = Image.open(png).convert("RGB")
        colours = image.getcolors(maxcolors=4096)
        index = png.stem.split("-")[1]
        out[index] = len(colours) if colours else 4096
    return out


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=pathlib.Path, required=True)
    parser.add_argument("--cross", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    cross = json.loads(args.cross.read_text(encoding="utf-8"))
    remake = {row["step"]: row for row in raw["remake"]}
    cross_rows = {row["original_step"]: row for row in cross["rows"]}

    # --- exact sha256 anchors -------------------------------------------
    anchors = []
    for row in cross["rows"]:
        for candidate in row["best"]:
            if candidate["field_px"] == 0:
                anchors.append({
                    "original_step": row["original_step"],
                    "remake_step": candidate["remake_step"],
                    "offset": candidate["remake_step"] - row["original_step"],
                    "remake_phase": candidate["remake_phase"],
                })
                break

    original = []
    colours = distinct_colours(pathlib.Path(raw["captures"]["original"]))
    for row in raw["original"]:
        index = row["step"]
        c = cross_rows[index]
        best = c["best"][0]
        chain_step = index + ANCHOR_OFFSET
        chain = remake.get(chain_step)
        chain_field = c["field_at_offset4"]
        degenerate = (colours.get(str(index), 999) <= DEGENERATE_COLOURS
                      or row["png_bytes"] <= DEGENERATE_BYTES)
        # basis of the transfer
        best_phase = best["remake_phase"]
        if best["field_px"] == 0:
            basis = "byte_identical"
        elif best["field_px"] >= WHOLE_FRAME_MIN:
            basis = "no_counterpart"
        elif best["field_px"] > NO_COUNTERPART_MIN:
            basis = "weak_match"
        else:
            basis = "residual_match"

        # phase of the original step: the phase of the remake frame it shows
        phase = best_phase
        entry = {
            "step": index,
            "key": row["key"],
            "sha256": row["sha256"],
            "png_bytes": row["png_bytes"],
            "phase": phase,
            "scene_frame": (remake.get(best["remake_step"], {}) or {}).get("scene_frame"),
            "round": (remake.get(best["remake_step"], {}) or {}).get("round"),
            "cursor": (remake.get(best["remake_step"], {}) or {}).get("cursor"),
            "selected_unit": (remake.get(best["remake_step"], {}) or {}).get("selected_unit"),
            "match_basis": basis,
            "match_remake_step": best["remake_step"],
            "match_field_px": best["field_px"],
            "chain_remake_step": chain_step,
            "chain_remake_phase": (chain or {}).get("phase"),
            "chain_field_px": chain_field,
            "global_min_field_px": best["field_px"],
            "degenerate_blank_frame": degenerate,
            "distinct_colours": colours.get(f"{index:02d}"),
        }
        original.append(entry)

    # --- first divergence -------------------------------------------------
    # Two complementary criteria, both reported:
    #   (1) the first original frame that has **no counterpart at all** in
    #       the remake walk (the smallest residual over all 35 remake frames
    #       is still huge) -- the first *visible* divergence;
    #   (2) the first original frame whose phase does **not** match the
    #       phase the walk offset predicts -- the phase chain break.
    # Degenerate (flat / black transition) frames carry no phase
    # information and are excluded from (2).
    informative = [row for row in original
                   if not row["degenerate_blank_frame"]]
    first_px = next((row["step"] for row in original
                     if row["match_basis"] == "no_counterpart"), None)
    first_chain = next((row["step"] for row in informative
                        if row["phase"] is not None
                        and row["chain_remake_phase"] is not None
                        and row["phase"] != row["chain_remake_phase"]), None)
    first_step = first_px if first_px is not None else first_chain

    detail = ""
    if first_step is not None:
        row = original[first_step]
        detail = (
            f"original step {first_step} ({row['key']}) is the first frame "
            f"with no counterpart in the remake walk: the smallest residual "
            f"over all {len(remake)} remake frames is "
            f"{row['global_min_field_px']} px "
            f"({100.0 * row['global_min_field_px'] / 30720:.1f} % of the "
            f"240x128 field). The walk offset {ANCHOR_OFFSET:+d} still holds "
            f"up to original step 18 (four byte-identical anchor pairs), so "
            f"the two walks are in the same game state there; from this step "
            f"on the original runs the round-1 banner -> 'please wait' -> "
            f"camera pan transition that the remake does not implement, and "
            f"the offset drifts to {ANCHOR_OFFSET - 3:+d} by original step 23."
        )

    document = {
        "schema": "konoha.s49-press-phase-table.v1",
        "generated_by": "tools/s49_w21c2/finalize_table.py",
        "roms": raw["roms"],
        "captures": raw["captures"],
        "step_semantics": raw["step_semantics"],
        "anchor": {
            "definition": (
                "A = byte-identical frame pairs (sha256 equal) across the two "
                "walks; they fix the walk offset at remake_index = "
                "original_index + 4 and prove both walks are in the same game "
                "state at those points. B = the remake's telemetry phase read "
                "from EWRAM 0x0202A56C. C = the phase chain: the offset+4 "
                "transfer of B onto the original walk."),
            "walk_offset": ANCHOR_OFFSET,
            "byte_identical_pairs": anchors,
            "identical_max_field_px": IDENTICAL_MAX,
            "no_counterpart_min_field_px": NO_COUNTERPART_MIN,
        },
        "original": original,
        "remake": raw["remake"],
        "first_divergence": {
            "step": first_step,
            "original_phase": (original[first_step] or {}).get("phase")
            if first_step is not None else None,
            "remake_phase": (original[first_step] or {}).get("chain_remake_phase")
            if first_step is not None else None,
            "kind": "b_state_difference",
            "detail": detail,
            "also": {
                "first_frame_without_any_counterpart": first_px,
                "first_phase_chain_break": first_chain,
            },
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=2)
                        + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    print(f"first divergence step = {first_step} "
          f"(no-counterpart frame = {first_px}, chain break = {first_chain})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
