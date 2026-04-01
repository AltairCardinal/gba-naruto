#!/usr/bin/env python3
"""Analyze the tile descriptor table at 0x596D5C.

Dumps the pointer chains for tile entries so we can understand
the graphics data format before writing the PNG extractor.

Usage:
    python tools/analyze_tile_table.py rom.gba
    python tools/analyze_tile_table.py rom.gba --entry 0 --depth 3
    python tools/analyze_tile_table.py rom.gba --list-entries
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROM_BASE = 0x08000000
TILE_TABLE_OFFSET = 0x596D5C
TILE_TABLE_ENTRY_SIZE = 16
TILE_TABLE_COUNT = 312


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def to_file(arm_addr: int) -> int | None:
    if ROM_BASE <= arm_addr < ROM_BASE + 0x800000:
        return arm_addr - ROM_BASE
    return None


def hex_dump(data: bytes, offset: int, length: int = 64, width: int = 16) -> str:
    lines = []
    for row in range(0, length, width):
        chunk = data[offset + row : offset + row + width]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        lines.append(f"  0x{offset+row:06X}: {hex_part:<{width*3}}  {''.join(chr(b) if 0x20<=b<0x7F else '.' for b in chunk)}")
    return "\n".join(lines)


def analyze_entry(data: bytes, row: int, depth: int) -> None:
    base = TILE_TABLE_OFFSET + row * TILE_TABLE_ENTRY_SIZE
    col0 = read_u32(data, base + 0x00)
    col1 = read_u32(data, base + 0x04)
    col2 = read_u32(data, base + 0x08)
    col3 = read_u32(data, base + 0x0C)

    print(f"\n=== Entry {row} at file 0x{base:06X} ===")
    print(f"  col0 (gfx desc): 0x{col0:08X} → file 0x{to_file(col0):06X}" if to_file(col0) is not None else f"  col0 (gfx desc): 0x{col0:08X} [invalid]")
    print(f"  col1 (layout):   0x{col1:08X} → file 0x{to_file(col1):06X}" if to_file(col1) is not None else f"  col1 (layout):   0x{col1:08X} [invalid]")
    print(f"  col2 (attr):     0x{col2:08X} → file 0x{to_file(col2):06X}" if to_file(col2) is not None else f"  col2 (attr):     0x{col2:08X} [invalid]")
    print(f"  col3 (palette):  0x{col3:08X} → file 0x{to_file(col3):06X}" if to_file(col3) is not None else f"  col3 (palette):  0x{col3:08X} [invalid]")

    if depth <= 0:
        return

    # Analyze col0: nested descriptor with sub-pointers
    col0_file = to_file(col0)
    if col0_file is not None:
        print(f"\n  [col0 nested descriptor at 0x{col0_file:06X}]")
        print(hex_dump(data, col0_file, 64))
        # Read up to 8 sub-pointers
        sub_ptrs = []
        for i in range(8):
            ptr = read_u32(data, col0_file + i * 4)
            f = to_file(ptr)
            if f is not None:
                sub_ptrs.append((i, ptr, f))
                print(f"    sub[{i}]: 0x{ptr:08X} → file 0x{f:06X}")
            else:
                print(f"    sub[{i}]: 0x{ptr:08X} [end or data]")
                if ptr == 0:
                    break

        if depth >= 2 and sub_ptrs:
            # Show first sub-pointer content
            i, ptr, f = sub_ptrs[0]
            print(f"\n  [col0 sub[0] data at file 0x{f:06X}]")
            print(hex_dump(data, f, 128))

            # Try to interpret as tile header
            if f + 8 <= len(data):
                v0 = read_u16(data, f)
                v1 = read_u16(data, f + 2)
                v2 = read_u32(data, f + 4)
                v3 = read_u32(data, f + 8) if f + 12 <= len(data) else 0
                print(f"  Interpreted as header: u16[0]=0x{v0:04X}({v0}), u16[1]=0x{v1:04X}({v1}), u32[2]=0x{v2:08X}, u32[3]=0x{v3:08X}")

                # Check if looks like LZ77
                if data[f] == 0x10:
                    decomp_size = int.from_bytes(data[f+1:f+4], "little")
                    print(f"  Looks like LZ77! Decompressed size: {decomp_size} bytes")

    # Analyze col3: palette data (BGR555)
    col3_file = to_file(col3)
    if col3_file is not None:
        print(f"\n  [col3 palette at file 0x{col3_file:06X}]")
        # Check if LZ77 compressed
        if data[col3_file] == 0x10:
            decomp_size = int.from_bytes(data[col3_file+1:col3_file+4], "little")
            print(f"  LZ77 compressed, decompressed size: {decomp_size} bytes")
            print(hex_dump(data, col3_file, 32))
        else:
            # Raw BGR555 palette: 16 colors × 2 bytes = 32 bytes
            print("  Raw BGR555 palette (first 16 colors):")
            for ci in range(16):
                bgr = read_u16(data, col3_file + ci * 2)
                b5 = (bgr >> 10) & 0x1F
                g5 = (bgr >> 5) & 0x1F
                r5 = bgr & 0x1F
                r8 = (r5 << 3) | (r5 >> 2)
                g8 = (g5 << 3) | (g5 >> 2)
                b8 = (b5 << 3) | (b5 >> 2)
                print(f"    color[{ci:2d}]: BGR555=0x{bgr:04X} → RGB({r8:3d},{g8:3d},{b8:3d})")

    if depth >= 2:
        # Also dump col1
        col1_file = to_file(col1)
        if col1_file is not None:
            print(f"\n  [col1 layout at file 0x{col1_file:06X}]")
            print(hex_dump(data, col1_file, 64))


def list_entries(data: bytes, count: int = 32) -> None:
    print(f"{'Row':>4}  {'file_off':>8}  {'col0 (gfx)':>12}  {'col1 (lay)':>12}  {'col2 (att)':>12}  {'col3 (pal)':>12}")
    print("-" * 72)
    for row in range(min(count, TILE_TABLE_COUNT)):
        base = TILE_TABLE_OFFSET + row * TILE_TABLE_ENTRY_SIZE
        col0 = read_u32(data, base + 0x00)
        col1 = read_u32(data, base + 0x04)
        col2 = read_u32(data, base + 0x08)
        col3 = read_u32(data, base + 0x0C)
        if col0 == 0 and col1 == 0:
            print(f"{row:4d}  0x{base:06X}  [zero - end]")
            break
        print(f"{row:4d}  0x{base:06X}  0x{col0:08X}  0x{col1:08X}  0x{col2:08X}  0x{col3:08X}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze tile descriptor table at 0x596D5C")
    parser.add_argument("rom", type=Path, help="GBA ROM file")
    parser.add_argument("--entry", type=int, default=0, help="Entry index to analyze in depth")
    parser.add_argument("--depth", type=int, default=2, help="Pointer chain depth (1-3)")
    parser.add_argument("--list-entries", action="store_true", help="List all table entries")
    parser.add_argument("--list-count", type=int, default=312, help="Max entries to list")
    args = parser.parse_args()

    if not args.rom.exists():
        print(f"Error: ROM not found: {args.rom}", file=sys.stderr)
        return 1

    data = args.rom.read_bytes()
    print(f"ROM size: {len(data):,} bytes (0x{len(data):X})")
    print(f"Tile table: file 0x{TILE_TABLE_OFFSET:06X}, {TILE_TABLE_COUNT} entries × {TILE_TABLE_ENTRY_SIZE} bytes")

    if args.list_entries:
        list_entries(data, args.list_count)
    else:
        analyze_entry(data, args.entry, args.depth)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
