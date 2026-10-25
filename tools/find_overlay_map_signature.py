#!/usr/bin/env python3
"""Find the remake's overlay tilemap by its signature, not by guessing.

The remake's overlay layer is a regular BG whose tilemap entries must have
the shape the style header implies:

* tile index inside the overlay's own tile range (1..77 in
  battle_range_ui_style.h), and
* a char base that matches the overlay's char base, and
* 8bpp (or 4bpp) as the layer's BGCNT says.

This scans every screen-block aligned offset in a full VRAM dump and reports
the regions whose entries look like overlay tiles, together with the BG
registers that were live at the same frame.
"""

from __future__ import annotations

import argparse
import pathlib
import struct
from collections import Counter


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--vram", type=pathlib.Path, required=True)
    ap.add_argument("--io", type=pathlib.Path, default=None)
    ap.add_argument("--tile-max", type=int, default=77)
    args = ap.parse_args()

    raw = args.vram.read_bytes()
    print(f"vram dump: {args.vram} ({len(raw)} bytes)")

    if args.io and args.io.is_file():
        b = args.io.read_bytes()
        disp = b[0] | (b[1] << 8)
        bg2 = b[0x0C] | (b[0x0D] << 8)
        print(f"same-frame registers: DISPCNT=0x{disp:04X} BGCNT2=0x{bg2:04X}")
        prio = bg2 & 3
        charbase = ((bg2 >> 2) & 3) * 0x4000
        screenbase = 0x10000 + ((bg2 >> 8) & 0x1F) * 0x400
        bpp = 4 if (bg2 & 0x8000) else 8
        print(f"  overlay: prio={prio} charbase=0x{charbase:05X} "
              f"screenbase=0x{screenbase:05X} bpp={bpp}")
        expected = screenbase
    else:
        expected = None

    print("\nregions whose entries look like overlay tiles:")
    for base in range(0, len(raw) - 2048, 0x400):
        cells = struct.unpack_from("<1024H", raw, base)
        indices = [c & 0x3FF for c in cells]
        charbases = {((c >> 2) & 3) for c in cells if c}
        palettes = {((c >> 10) & 3) for c in cells if c}
        if not any(cells):
            continue
        in_range = sum(1 for i in indices if 1 <= i <= args.tile_max)
        if in_range < 100:
            continue
        distinct = len(set(cells))
        mark = "  <== expected screenbase" if expected is not None and base == expected else ""
        print(f"  0x{base:05X}  in-range tiles {in_range:>4}/1024  distinct {distinct:>4}  "
              f"charbases {sorted(charbases)}  palettes {sorted(palettes)}{mark}")

    if expected is not None:
        cells = struct.unpack_from("<1024H", raw, expected)
        print(f"\nexpected overlay map at 0x{expected:05X}:")
        kinds = Counter((c & 0x3FF) for c in cells if c)
        print("  tile indices:", dict(kinds.most_common(12)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
