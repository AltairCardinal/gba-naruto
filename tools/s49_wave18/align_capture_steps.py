#!/usr/bin/env python3
"""Align the two judgement-bench capture walks and price the misalignment.

Why this tool exists
--------------------
The judgement bench (tools/s49_fidelity_report) compares the original's
capture walk with the remake's capture walk by *pixel similarity*: for every
original frame it picks the best looking remake frame.  On wave 17 that left
four frames classified as ``moment_mismatch`` which together carried 82,571 px
of the 109,569 px reading -- 75 % of the whole residual.

But the two walks are not the same walk:

  original: starts from the save state ``scenario-49-battle-14-entry.ss9``
            (already inside battle 14) and presses A 24 times
  remake:   starts from **boot**, presses Down, Down, then A 32 times

so the remake's walk is *offset* by the two navigation presses plus whatever
extra confirmations the remake's flow demands.  This tool measures that
offset directly (exact sha256 matches) and then prices every candidate
alignment, so that "the instrument paired the wrong frame" can be separated
from "the product draws the wrong pixels".

Usage
-----
    python tools/s49_wave18/align_capture_steps.py \
        --original build/.../s49-report/capture-original \
        --remake   build/.../s49-report/capture-remake

Exit code 0 always (this is an analysis tool); the verdict is printed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s49_fidelity_report.pixels import diff_mask, load_rgb  # noqa: E402

FIELD_AREA = (0, 0, 240, 128)
FULL_BOX = (0, 0, 240, 160)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_side(directory: str) -> list[tuple[str, str]]:
    names = sorted(
        n for n in os.listdir(directory) if n.startswith("step-") and n.endswith(".png")
    )
    out = []
    for name in names:
        out.append((name, sha256_file(os.path.join(directory, name))))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--remake", required=True)
    parser.add_argument("--out", default=None, help="write a JSON report here")
    args = parser.parse_args()

    original = load_side(args.original)
    remake = load_side(args.remake)
    print(f"original frames: {len(original)}   remake frames: {len(remake)}")

    # --- 1. exact sha256 matches give the true walk offset ----------------
    remake_by_sha: dict[str, list[str]] = {}
    for name, digest in remake:
        remake_by_sha.setdefault(digest, []).append(name)
    remake_index = {name: i for i, (name, _) in enumerate(remake)}

    print("\n=== exact sha256 matches (original -> remake) ===")
    exact: dict[int, int] = {}
    for oi, (oname, odigest) in enumerate(original):
        hits = remake_by_sha.get(odigest, [])
        if hits:
            for h in hits:
                print(f"  {oname:<16} -> {h:<16} (offset {remake_index[h] - oi:+d})")
            exact[oi] = remake_index[hits[0]]

    offsets = [remake_index[h] - oi for oi, (oname, odigest) in enumerate(original)
               for h in remake_by_sha.get(odigest, [])]
    if offsets:
        print(f"\n  offsets observed: {sorted(set(offsets))}  (mode = "
              f"{max(set(offsets), key=offsets.count)})")

    # --- 2. price every constant offset ----------------------------------
    o_images = {name: load_rgb(os.path.join(args.original, name)) for name, _ in original}
    r_images = {name: load_rgb(os.path.join(args.remake, name)) for name, _ in remake}

    print("\n=== residual per constant offset (field area 240x128) ===")
    results = []
    for offset in range(0, 9):
        total = 0
        matched = 0
        rows = []
        for oi, (oname, _) in enumerate(original):
            ri = oi + offset
            if ri >= len(remake):
                rows.append((oname, None, None))
                continue
            rname = remake[ri][0]
            count, _ = diff_mask(o_images[oname], r_images[rname], FIELD_AREA)
            total += count
            matched += 1
            rows.append((oname, rname, count))
        results.append((offset, total, matched))
        print(f"  offset {offset:+d}: total field residual = {total:>7} "
              f"({matched} original frames aligned)")

    best_offset, best_total, _ = min(results, key=lambda r: r[1])
    print(f"\n  best constant offset: {best_offset:+d} with {best_total} px")

    # --- 3. per frame table at the best offset ---------------------------
    print(f"\n=== per frame at offset {best_offset:+d} ===")
    print(f"{'original':<16}{'remake':<16}{'field px':>9}{'full px':>9}")
    rows = []
    for oi, (oname, _) in enumerate(original):
        ri = oi + best_offset
        if ri >= len(remake):
            print(f"{oname:<16}{'(none)':<16}{'-':>9}{'-':>9}")
            continue
        rname = remake[ri][0]
        field, _ = diff_mask(o_images[oname], r_images[rname], FIELD_AREA)
        full, _ = diff_mask(o_images[oname], r_images[rname], FULL_BOX)
        rows.append((oname, rname, field, full))
        print(f"{oname:<16}{rname:<16}{field:>9}{full:>9}")
    print(f"\n  total field residual at offset {best_offset:+d}: {sum(r[2] for r in rows)}")

    # --- 4. per frame offset profile: where does the walk diverge? -------
    print("\n=== offset profile: residual per original frame at offsets +1..+6 ===")
    profile = []
    header = "".join(f"{('+' + str(o)):>9}" for o in range(1, 7))
    print(f"{'original':<16}{header}   best")
    for oi, (oname, _) in enumerate(original):
        cells = []
        best_o = None
        best_v = None
        for offset in range(1, 7):
            ri = oi + offset
            if ri >= len(remake):
                cells.append(None)
                continue
            count, _ = diff_mask(o_images[oname], r_images[remake[ri][0]], FIELD_AREA)
            cells.append(count)
            if best_v is None or count < best_v:
                best_o = offset
                best_v = count
        profile.append({"original": oname, "cells": cells, "best_offset": best_o,
                        "best_px": best_v})
        line = "".join(f"{('-' if c is None else c):>9}" for c in cells)
        print(f"{oname:<16}{line}   +{best_o} ({best_v})")

    # --- 5. what the bench's own pairing charged -------------------------
    print("\n=== what the bench charged for the same frames (from report.json) ===")
    print("  see notes/s49-fidelity/W18-PARENT-residual-structure.md section 1.1")

    if args.out:
        import json
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "original_dir": args.original,
                    "remake_dir": args.remake,
                    "exact_matches": [
                        {"original": original[oi][0], "remake": remake[ri][0],
                         "offset": ri - oi}
                        for oi, ri in sorted(exact.items())
                    ],
                    "offset_totals": [
                        {"offset": o, "total_field_px": t, "frames": m}
                        for o, t, m in results
                    ],
                    "best_offset": best_offset,
                    "best_total": best_total,
                    "per_frame": [
                        {"original": o, "remake": r, "field_px": f, "full_px": fu}
                        for o, r, f, fu in rows
                    ],
                    "offset_profile": profile,
                },
                handle, ensure_ascii=False, indent=1,
            )
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
