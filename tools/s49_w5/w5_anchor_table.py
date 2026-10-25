#!/usr/bin/env python3
"""W5 -- print the judgement bench's content anchors for the critical frames.

The bench (``tools/s49_fidelity_report``) already measured a content anchor for
every captured frame: screen brightness facts, the camera registers
(``bg_hofs``) and the overlay layer's lit-cell family counts.  ``report.json``
stores the original-side anchor of every frame plus the remake-side anchor of
the frame it was paired with, so merging them recovers an anchor for almost
every remake frame without re-probing mGBA.

Usage
-----
    python tools/s49_w5/w5_anchor_table.py \
        --report build/s49-package-u3-final/work/s49-report/report.json \
        --matrix build/s49-wave18/w5/align-matrix.json
"""

from __future__ import annotations

import argparse
import json


def row(name: str, anchor: dict | None) -> str:
    if not anchor:
        return "{:<16} (no anchor)".format(name)
    screen = anchor.get("screen", {})
    # ``report.json`` stores the anchor flattened (dispcnt_hex / bg_hofs sit at
    # the top level); the live ``anchors.py`` nests them under "registers".
    registers = anchor.get("registers", {})
    dispcnt = registers.get("dispcnt_hex") or anchor.get("dispcnt_hex")
    bg_hofs = registers.get("bg_hofs") or anchor.get("bg_hofs")
    overlay = anchor.get("overlay", {})
    families = overlay.get("family_counts", {})
    family_text = "/".join(
        "{}:{}".format(key, value)
        for key, value in sorted(families.items()) if value
    ) or "-"
    return (
        "{:<16} nb={:.3f} ucol={:>3} disp={} hofs={} lit={} fam={}".format(
            name,
            screen.get("non_black_fraction", 0.0),
            screen.get("unique_colours", 0),
            dispcnt,
            bg_hofs,
            overlay.get("lit_cells"),
            family_text,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--matrix", default=None)
    parser.add_argument("--from", dest="lo", type=int, default=0)
    parser.add_argument("--to", dest="hi", type=int, default=999)
    args = parser.parse_args()

    report = json.load(open(args.report, encoding="utf-8"))
    merged = {}
    for frame in report.get("frames", []):
        anchor = (frame.get("anchor") or {}).get("remake")
        if anchor:
            merged.setdefault(frame["best_match"], anchor)

    print("=== ORIGINAL side (report.json frames[].anchor.original) ===")
    for frame in report.get("frames", []):
        name = frame["original"]
        index = 0 if "base" in name else int(name[5:7])
        if args.lo <= index <= args.hi:
            print(row(name, (frame.get("anchor") or {}).get("original")))

    print()
    print("=== REMAKE side (merged anchors) ===")
    names = sorted(merged.keys(), key=lambda n: (0 if "base" in n else int(n[5:7])))
    for name in names:
        index = 0 if "base" in name else int(name[5:7])
        if args.lo <= index <= args.hi:
            print(row(name, merged[name]))

    if args.matrix:
        matrix = json.load(open(args.matrix, encoding="utf-8"))
        missing = [n for n in matrix["remake_frames"] if n not in merged]
        if missing:
            print()
            print("=== remake frames WITHOUT a merged anchor (never paired) ===")
            for name in missing:
                print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
