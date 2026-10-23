#!/usr/bin/env python3
"""Read-only probe: space budget + Table B extent."""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

ROM_BASE = 0x08000000
A_ROM, A_STRIDE, A_N = 0x085A57C4, 12, 63
B_ROM, B_STRIDE = 0x085A5AB8, 19


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = (REPO / "rom" / "base.gba").read_bytes()

    total = 0
    longest = []
    for i in range(A_N):
        off = A_ROM - ROM_BASE + i * A_STRIDE
        raw = rom[off:off + A_STRIDE]
        n = 0
        while n < len(raw) and raw[n] != 0:
            n += 1
        total += n + 1
        longest.append((n, i))
    longest.sort(reverse=True)
    print("Table A (0x%08X, %d entries): total string bytes incl. NUL = %d" % (A_ROM, A_N, total))
    print("  longest: " + ", ".join("id %d = %d bytes (%d glyphs)" % (i, n, n // 2)
                                   for n, i in longest[:6]))
    print("  slot capacity: 12 bytes -> max 5 glyphs (10 B) + 1 NUL = 11 B (1 B spare)")
    print("  currently used: max 4 glyphs -> 1 glyph of headroom")

    print("\nTable B (0x%08X, 19-byte records):" % B_ROM)
    n = 0
    maxg = 0
    for i in range(200):
        off = B_ROM - ROM_BASE + i * B_STRIDE
        raw = rom[off:off + B_STRIDE]
        # a record is valid if it is NUL-terminated inside the record
        n2 = 0
        while n2 < len(raw) and raw[n2] != 0:
            n2 += 1
        if n2 >= len(raw):
            print("  record %d: no NUL inside the 19-byte record -> table ends" % i)
            break
        n = i + 1
        maxg = max(maxg, n2 // 2)
    print("  records: %d   max glyphs in a record: %d" % (n, maxg))
    print("  table span: 0x%08X .. 0x%08X (%d bytes)" % (B_ROM, B_ROM + n * B_STRIDE, n * B_STRIDE))
    print("  bytes after Table B (file 0x%06X):" % (B_ROM - ROM_BASE + n * B_STRIDE))
    e = B_ROM - ROM_BASE + n * B_STRIDE
    print("   " + rom[e:e + 48].hex(" "))

    print("\nFree space candidates:")
    print("  ROM tail 0xFF padding: file 0x5DFBEC .. 0x5FFFFF = %d bytes (ROM 0x085DFBEC..0x085FFFFF)"
          % (0x600000 - 0x5DFBEC))
    print("  freed by Table A if replaced: 0x%08X..0x%08X = %d bytes"
          % (A_ROM, A_ROM + A_N * A_STRIDE, A_N * A_STRIDE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())