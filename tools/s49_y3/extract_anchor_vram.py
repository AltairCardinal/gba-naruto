#!/usr/bin/env python3
"""Extract the VRAM out of the judgment bench's anchor dumps.

The anchor ``.state.bin`` files are ``io (0x40) || pram (0x400) || vram``.
This writes the VRAM part into ``<out>/<step>.vram-0000.bin`` so that the
overlay comparison can read it.

Usage::

    python tools/s49_y3/extract_anchor_vram.py \
        --anchors build/s49-report/y3/anchors/remake \
        --out build/s49-y3/vram
"""

from __future__ import annotations

import argparse
import pathlib


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--anchors", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    written = 0
    for state in sorted(args.anchors.glob("*.state.bin")):
        blob = state.read_bytes()
        if len(blob) < 0x40 + 0x400:
            continue
        vram = blob[0x40 + 0x400:]
        target = args.out / (state.stem.replace(".state", "") + ".vram-0000.bin")
        target.write_bytes(vram)
        written += 1
    print(f"wrote {written} VRAM dumps to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
