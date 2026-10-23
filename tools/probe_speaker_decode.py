#!/usr/bin/env python3
"""Read-only probe: decode the speaker-name tables to text.

- Table A: 12-byte slots @ ROM 0x085A57C4 (file 0x5A57C4), 12 native readers.
- Table B: 19-byte records @ ROM 0x085A5AB8 (file 0x5A5AB8), 3 native readers.
Both hold NUL-terminated strings of the game's 2-byte glyph codes.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import text_codec  # noqa: E402

ROM_BASE = 0x08000000
A_ROM, A_STRIDE = 0x085A57C4, 12
B_ROM, B_STRIDE = 0x085A5AB8, 19


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = (REPO / "rom" / "base.gba").read_bytes()
    mapping, _ = text_codec.load_mapping()

    def dec(raw: bytes) -> str:
        out = []
        i = 0
        while i + 1 < len(raw):
            code = (raw[i] << 8) | raw[i + 1]
            if code == 0:
                break
            out.append(mapping.get(code, "?"))
            i += 2
        return "".join(out)

    def raw_codes(raw: bytes) -> list:
        out = []
        i = 0
        while i + 1 < len(raw):
            code = (raw[i] << 8) | raw[i + 1]
            if code == 0:
                break
            out.append(code)
            i += 2
        return out

    print("=== TABLE A: 12-byte slots @ ROM 0x%08X ===" % A_ROM)
    for i in range(64):
        off = A_ROM - ROM_BASE + i * A_STRIDE
        raw = rom[off:off + A_STRIDE]
        codes = raw_codes(raw)
        print("  id %2d  n=%d  %-28s %s" % (i, len(codes), dec(raw), " ".join("%04X" % c for c in codes)))

    print("\n=== TABLE B: 19-byte records @ ROM 0x%08X ===" % B_ROM)
    for i in range(48):
        off = B_ROM - ROM_BASE + i * B_STRIDE
        raw = rom[off:off + B_STRIDE]
        codes = raw_codes(raw)
        print("  rec %2d n=%d  %-28s %s" % (i, len(codes), dec(raw), " ".join("%04X" % c for c in codes)))

    print("\n=== overlap check ===")
    print("  A base + 63*12 = 0x%08X   B base = 0x%08X" % (A_ROM + 63 * 12, B_ROM))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())