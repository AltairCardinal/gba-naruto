#!/usr/bin/env python3
"""Locate the display registers inside mGBA's dumped I/O block.

mGBA's Lua "io" memory domain is not the GBA's flat I/O map, so the offsets
have to be found rather than assumed.  This prints every 16-bit word of a
dumped block and flags the ones that match the values the remake is known to
run with (DISPCNT 0xFC40, BGCNT2 0x138A, BGCNT3 0xCC83), plus the values the
original is known to run with (DISPCNT 0x1D40 / 0x1940, BGCNT2 0x0202).

Usage::

    python tools/find_io_registers.py build/vram-dump/frame-0000.io
"""

from __future__ import annotations

import pathlib
import struct
import sys

KNOWN = {
    0xFC40: "remake DISPCNT (BG2+BG3+OBJ)",
    0x138A: "remake BGCNT2 (overlay, prio 2, 8bpp)",
    0xCC83: "remake BGCNT3 (map, prio 3, 8bpp)",
    0x1D40: "original DISPCNT (BG2 enabled)",
    0x1940: "original DISPCNT (BG2 disabled)",
    0x0202: "original BGCNT2 (4bpp)",
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = pathlib.Path(sys.argv[1])
    data = path.read_bytes()
    print(f"{path}: {len(data)} bytes")
    print("offset  value     note")
    for offset in range(0, len(data) - 1, 2):
        value = struct.unpack_from("<H", data, offset)[0]
        note = KNOWN.get(value, "")
        if note or offset < 0x30:
            print(f"  0x{offset:02X}  0x{value:04X}   {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
