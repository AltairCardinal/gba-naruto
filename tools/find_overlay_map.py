#!/usr/bin/env python3
"""Locate the remake's BG2 tilemap inside a full-VRAM dump, by pattern.

The original's BG2 overlay has been exported as a cell-level ground truth.
The remake writes the same layer, but with different tile indices and a
different palette bank, so the two cannot be compared by value.  They *can* be
compared by shape: which cells are populated and which are blank.

This scans every screen-block aligned offset in a full-VRAM dump and ranks the
candidates by how well the populated/blank pattern matches each of the four
ground-truth moments.  The winner is the remake's overlay map.

Usage::

    python tools/find_overlay_map.py --dump build/bg2full/v-0000.bin
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
from collections import Counter

GT = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
)
MOMENTS = ("field-frame-v1", "movegrid-frame-v1", "grid16-frame-v1", "banner-frame-v1")


def load_masks() -> dict[str, list[int]]:
    masks = {}
    for moment in MOMENTS:
        path = GT / f"{moment}.bg2-tilemap.json"
        if not path.is_file():
            continue
        cells = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
        # "populated" = not one of the blank tiles the exporter named
        blank = {int(c["raw_hex"], 16) for c in cells
                 if c.get("family") == "blank"}
        masks[moment] = [0 if int(c["raw_hex"], 16) in blank else 1 for c in cells]
    return masks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dump", type=pathlib.Path, required=True)
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    raw = args.dump.read_bytes()
    masks = load_masks()
    if not masks:
        print(f"ERR no ground truth under {GT}")
        return 2
    print(f"dump: {args.dump} ({len(raw)} bytes)")

    scored = []
    for base in range(0, len(raw) - 2048, 0x400):
        cells = struct.unpack_from("<1024H", raw, base)
        if not any(cells):
            continue
        populated = [0 if c == 0 else 1 for c in cells]
        best = 0
        for moment, mask in masks.items():
            agree = sum(1 for a, b in zip(populated, mask) if a == b)
            best = max(best, agree)
        scored.append((best, base, sum(populated)))
    scored.sort(reverse=True)

    print(f"\n{'base':>10} {'best agreement':>16} {'populated cells':>17}")
    for agree, base, pop in scored[:args.top]:
        print(f"  0x{base:05X} {agree:>13}/1024 {pop:>14}")

    if scored:
        best_agree, best_base, _ = scored[0]
        cells = struct.unpack_from("<1024H", raw, best_base)
        kinds = Counter(cells)
        print(f"\nwinner: 0x{best_base:05X}  ({best_agree}/1024 cells agree with the best moment)")
        print("most common entries:", ", ".join(
            f"{v:#06x}x{c}" for v, c in kinds.most_common(6)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
