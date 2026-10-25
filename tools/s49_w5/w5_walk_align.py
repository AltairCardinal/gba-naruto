#!/usr/bin/env python3
"""W5 -- price the ORIGINAL-vs-REMAKE A-key walk divergence frame by frame.

Why this tool exists
--------------------
``tools/s49_wave18/align_capture_steps.py`` measures the step offset inside a
+/-6 window and reports "best offset" per original frame.  That is enough to
say *that* the offset drops from +4 to +3 between original step 9 and step 10,
but it cannot say *what* the extra A press was, because a +/-6 window cannot
answer the only question that matters here:

    "does the remake contain ANY frame that matches original step-10?"

So this tool builds the **complete** residual matrix (every original frame
against every remake frame, field area and full frame), and merges the content
anchors the judgement bench already measured (``report.json``) into a
per-remake-frame table so that both sides can be described in the same
vocabulary: ``non_black_fraction`` / ``unique_colours`` / ``bg_hofs`` /
``overlay.lit_cells``.

Usage
-----
    python tools/s49_w5/w5_walk_align.py \
        --original build/s49-package-u3-final/work/s49-report/capture-original \
        --remake   build/s49-package-u3-final/work/s49-report/capture-remake \
        --report   build/s49-package-u3-final/work/s49-report/report.json \
        --out      build/s49-wave18/w5/align-matrix.json

Exit code 0 always (analysis tool).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FIELD_AREA = (0, 0, 240, 128)
FULL_BOX = (0, 0, 240, 160)


def frame_names(directory: str) -> list[str]:
    return sorted(
        n for n in os.listdir(directory)
        if n.startswith("step-") and n.endswith(".png")
    )


def short(name: str) -> str:
    """'step-09-A.png' -> '09A'  (compact column headers)."""
    stem = name[len("step-"):-len(".png")]
    return stem.replace("-", "")


def merge_anchors(report: dict) -> dict:
    """Collect the per-remake-frame anchors the bench already measured.

    ``report.json`` stores, for every original frame, the anchor of the frame it
    paired with on the remake side (``frames[].anchor.remake``).  The pairing
    covers a wide spread of remake frames, so merging them by remake frame name
    recovers an anchor for almost every remake frame without re-probing mGBA.
    """
    merged: dict[str, dict] = {}
    for row in report.get("frames", []):
        anchor = (row.get("anchor") or {}).get("remake")
        if not anchor:
            continue
        merged.setdefault(row["best_match"], anchor)
    return merged


def anchor_row(name: str, anchor: dict | None) -> str:
    if not anchor:
        return f"{name:<12} (no anchor)"
    screen = anchor.get("screen", {})
    registers = anchor.get("registers", {})
    overlay = anchor.get("overlay", {})
    families = overlay.get("family_counts", {})
    family_text = "/".join(
        f"{key}:{value}" for key, value in sorted(families.items()) if value
    ) or "-"
    return (
        f"{name:<12} "
        f"nb={screen.get('non_black_fraction', 0):.3f} "
        f"rgb={screen.get('mean_rgb', [0, 0, 0])} "
        f"ucol={screen.get('unique_colours', 0):>3} "
        f"disp={registers.get('dispcnt_hex', '?')} "
        f"hofs={registers.get('bg_hofs')} "
        f"lit={overlay.get('lit_cells', '?')} "
        f"fam={family_text}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--report", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    original = frame_names(args.original)
    remake = frame_names(args.remake)
    print(f"original frames: {len(original)}   remake frames: {len(remake)}")

    o_images = {n: load_rgb(os.path.join(args.original, n)) for n in original}
    r_images = {n: load_rgb(os.path.join(args.remake, n)) for n in remake}

    # --- 1. complete residual matrix (field area) ------------------------
    print("\n=== complete residual matrix, field area 240x128 ===")
    print("rows = original, cols = remake; cell = differing pixels")
    matrix = []
    for oname in original:
        row = []
        for rname in remake:
            count, _ = diff_mask(o_images[oname], r_images[rname], FIELD_AREA)
            row.append(count)
        matrix.append(row)

    header = "orig    " + "".join(f"{short(r):>7}" for r in remake)
    print(header)
    for oname, row in zip(original, matrix):
        print(f"{short(oname):<8}" + "".join(f"{value:>7}" for value in row))

    # --- 2. global best remake frame per original frame -----------------
    print("\n=== global best remake frame per original frame (field area) ===")
    print(f"{'original':<16}{'best remake':<16}{'px':>8}   runner-up")
    best_table = []
    for oi, (oname, row) in enumerate(zip(original, matrix)):
        order = sorted(range(len(row)), key=lambda i: row[i])
        best_i = order[0]
        second = order[1]
        best_table.append({
            "original": oname,
            "best_remake": remake[best_i],
            "best_offset": best_i - oi,
            "best_px": row[best_i],
            "runner_up": remake[second],
            "runner_up_px": row[second],
        })
        print(f"{oname:<16}{remake[best_i]:<16}{row[best_i]:>8}   "
              f"{remake[second]} ({row[second]})")

    # --- 3. the windowed offset profile, for comparison -----------------
    print("\n=== best offset inside the +/-6 window (parent instrument's view) ===")
    windowed = []
    for oi, (oname, row) in enumerate(zip(original, matrix)):
        window = [(row[oi + off], off) for off in range(1, 7) if oi + off < len(row)]
        if not window:
            continue
        value, offset = min(window)
        windowed.append({"original": oname, "offset": offset, "px": value})
        print(f"{oname:<16} +{offset} ({value})")

    # --- 4. anchors ------------------------------------------------------
    anchors = {}
    if args.report and os.path.exists(args.report):
        report = json.load(open(args.report, encoding="utf-8"))
        anchors = merge_anchors(report)
        print(f"\n=== merged anchors (remake side), {len(anchors)} frames ===")
        for rname in remake:
            print(anchor_row(rname, anchors.get(rname)))
        print("\n=== original side anchors, from report.json frames[] ===")
        for row in report.get("frames", []):
            left = (row.get("anchor") or {}).get("original")
            print(anchor_row(row["original"], left))

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "original_dir": args.original,
                    "remake_dir": args.remake,
                    "original_frames": original,
                    "remake_frames": remake,
                    "residual_matrix_field": matrix,
                    "global_best": best_table,
                    "windowed_best": windowed,
                    "remake_anchors": anchors,
                },
                handle, ensure_ascii=False, indent=1,
            )
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
