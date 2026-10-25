#!/usr/bin/env python3
"""Summarise the original's BG2 overlay ground truth.

The Butano line exported, for four moments of the S49 battle, the original
game's second background layer: its full tilemap, its palette and its tile
set.  This reads those exports and prints the shape of the ground truth so a
remake-side agent can implement against it without re-deriving anything.
"""

from __future__ import annotations

import json
import pathlib
import sys

GT = pathlib.Path(
    r"D:\Shell\Github\gba-naruto-butano\artifacts\s49-original-movegrid-tilemap-v1"
)


def main() -> int:
    if not GT.is_dir():
        print(f"ERR missing {GT}")
        return 2

    manifest = json.loads((GT / "manifest.json").read_text(encoding="utf-8"))
    print("=== manifest top-level keys ===")
    for key, value in manifest.items():
        if isinstance(value, (list, dict)):
            print(f"  {key}: {type(value).__name__} len {len(value)}")
        else:
            print(f"  {key}: {str(value)[:110]}")

    for name in ("movegrid-frame-v1", "field-frame-v1", "grid16-frame-v1",
                 "banner-frame-v1"):
        path = GT / f"{name}.bg2-tilemap.json"
        if not path.is_file():
            print(f"\n=== {name}: MISSING ===")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"\n=== {name}.bg2-tilemap.json ===")
        for key, value in data.items():
            if isinstance(value, list):
                print(f"  {key}: list len {len(value)}  sample {value[:3]}")
            elif isinstance(value, dict):
                print(f"  {key}: dict keys {list(value.keys())[:8]}")
            else:
                print(f"  {key}: {str(value)[:120]}")

    pal = GT / "bg2-palette.json"
    if pal.is_file():
        data = json.loads(pal.read_text(encoding="utf-8"))
        print("\n=== bg2-palette.json ===")
        for key, value in data.items():
            if isinstance(value, list):
                print(f"  {key}: list len {len(value)}  sample {value[:6]}")
            elif isinstance(value, dict):
                print(f"  {key}: dict keys {list(value.keys())[:8]}")
            else:
                print(f"  {key}: {str(value)[:120]}")

    tiles = (GT / "bg2-tiles-4bpp.bin").read_bytes()
    print(f"\n=== bg2-tiles-4bpp.bin: {len(tiles)} bytes ===")
    print("  at 4bpp (16 bytes/tile) =>", len(tiles) // 16, "tiles")
    print("  at 8bpp (32 bytes/tile) =>", len(tiles) // 32, "tiles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
