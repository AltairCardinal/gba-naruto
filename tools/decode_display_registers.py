#!/usr/bin/env python3
"""Decode the GBA display registers out of a dumped I/O block.

Usage::

    python tools/decode_display_registers.py build/bg2fd/io-0000.bin
"""

from __future__ import annotations

import pathlib
import sys

NAMES = {
    0x00: "DISPCNT", 0x04: "DISPSTAT", 0x06: "VCOUNT",
    0x08: "BGCNT0", 0x0A: "BGCNT1", 0x0C: "BGCNT2", 0x0E: "BGCNT3",
    0x26: "BG2HOFS", 0x28: "BG2VOFS", 0x32: "BG3HOFS", 0x34: "BG3VOFS",
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    data = pathlib.Path(sys.argv[1]).read_bytes()
    print(f"{sys.argv[1]}: {len(data)} bytes")
    for off, name in NAMES.items():
        if off + 1 >= len(data):
            continue
        value = data[off] | (data[off + 1] << 8)
        extra = ""
        if name.startswith("BGCNT"):
            prio = value & 3
            charbase = ((value >> 2) & 3) * 0x4000
            screenbase = ((value >> 8) & 0x1F) * 0x400
            bpp = 4 if (value & 0x8000) else 8
            size = (value >> 14) & 3
            extra = (f"  prio={prio} charbase=0x{charbase:05X}"
                     f" screenbase=0x{screenbase:05X} bpp={bpp} size={size}")
        if name == "DISPCNT":
            bgs = [n for n, bit in (("BG0", 8), ("BG1", 9), ("BG2", 10), ("BG3", 11))
                   if value & (1 << bit)]
            extra = f"  enabled: {','.join(bgs) or 'none'}"
        print(f"  {name:<9} 0x{value:04X}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
