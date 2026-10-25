"""Scratch: which VRAM blocks change across the dialogue box reveal."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from s49_pairing import savestate as savestate_module


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    first = int(sys.argv[2])
    last = int(sys.argv[3])
    settled_index = int(sys.argv[4]) if len(sys.argv) > 4 else last
    settled_png = src / f"step-{settled_index:04d}-in.png"
    if not settled_png.exists():
        settled_png = src / f"step-{settled_index:04d}-beat.png"
    settled = savestate_module.regions(
        savestate_module.load(src / settled_png.with_suffix(".ss9").name))
    settled_vram = settled["vram"]
    for index in range(first, last + 1):
        ss9 = src / f"step-{index:04d}-in.ss9"
        if not ss9.exists():
            ss9 = src / f"step-{index:04d}-beat.ss9"
        if not ss9.exists():
            continue
        state = savestate_module.regions(savestate_module.load(ss9))
        vram = state["vram"]
        blocks = []
        for block in range(len(vram) // 0x200):
            base = block * 0x200
            if vram[base:base + 0x200] != settled_vram[base:base + 0x200]:
                changed = sum(1 for offset in range(0x200)
                              if vram[base + offset] != settled_vram[base + offset])
                blocks.append((base, changed))
        # Report the contiguous 2K tile map regions that changed.
        regions = []
        for base, changed in blocks:
            if regions and regions[-1][1] == base:
                regions[-1][2] += changed
            else:
                regions.append([base, base, changed])
        text = " ".join(f"0x{lo:05X}-0x{hi + 0x1FF:05X}({n})" for lo, hi, n in regions)
        print(f"{index:04d} changed2k={len(blocks):3d} {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
