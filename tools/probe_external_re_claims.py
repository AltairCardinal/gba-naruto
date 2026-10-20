#!/usr/bin/env python3
"""Verify externally-derived RE claims against this repo's own ROM.

Context: the "木叶工房" story-editor package (v0.4.4, no-ROM) documents ROM
addresses discovered by a third party. Those addresses were checked against
the ROM that lives in this repo and were found to hold. This probe re-checks
them from scratch so the conclusions in
notes/external-konoha-workshop-gap-20261020.md stay reproducible.

Usage:
    python tools/probe_external_re_claims.py [rom_path]
"""
from __future__ import annotations

import hashlib
import pathlib
import struct
import sys
from collections import Counter

BASE = 0x08000000
DEFAULT_ROM = pathlib.Path(
    r"D:\Github\gba-naruto\火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba"
)

# Externally sourced addresses (file offsets) under evaluation.
MAP_TABLE = 0x53D910
RULES = 0x594758
BEFORE = 0x60C74
AFTER = 0x60D54
LOGIC = 0x60E34
EVENTS = 0x60EF0
MISSION_INDEX = 0x348DAC
MISSION_TABLES = (0x59AA5C, 0x59D214, 0x59E920)
REWARDS = 0x59EAE0
SPRITE_ACTION = 0x596CCC
PORTRAIT_PTR = 0x5A4DEC
PORTRAIT_PIECE = 0x4643C0
ITEM_NAMES = 0x599634
UPGRADE_NAMES = 0x5A7E8C
NAMES = 0x599280
SKILL_TABLE = 0x545458
ACTORS = 0x5461C4
FONT_SEGMENTS = 0x53D644


class Rom:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.data = path.read_bytes()

    def u8(self, p: int) -> int:
        return self.data[p]

    def u16(self, p: int) -> int:
        return struct.unpack_from("<H", self.data, p)[0]

    def u32(self, p: int) -> int:
        return struct.unpack_from("<I", self.data, p)[0]

    def head(self, p: int, n: int = 16) -> str:
        return " ".join(f"{b:02X}" for b in self.data[p : p + n])

    def lz77(self, file_off: int) -> bytes | None:
        """Decode a GBA LZ77 block; returns None when the block is not LZ77."""
        d = self.data
        if file_off < 0 or file_off + 4 > len(d) or d[file_off] != 0x10:
            return None
        n = d[file_off + 1] | d[file_off + 2] << 8 | d[file_off + 3] << 16
        out = bytearray()
        q, k = file_off + 4, 0
        while k < n and q < len(d):
            flags = d[q]
            q += 1
            for bit in range(7, -1, -1):
                if k >= n:
                    break
                if flags >> bit & 1:
                    if q + 2 > len(d):
                        break
                    a, b = d[q], d[q + 1]
                    q += 2
                    dist = ((a & 15) << 8 | b) + 1
                    count = (a >> 4) + 3
                    for _ in range(count):
                        if k >= n:
                            break
                        out.append(out[k - dist])
                        k += 1
                else:
                    if q >= len(d):
                        break
                    out.append(d[q])
                    q += 1
                    k += 1
        return bytes(out)

    def text_at(self, file_off: int, limit: int = 40) -> bytes:
        out = bytearray()
        for i in range(limit):
            if file_off + i >= len(self.data):
                break
            b = self.data[file_off + i]
            out.append(b)
            if b == 0:
                break
        return bytes(out)


def check_map_table(rom: Rom) -> None:
    """Map entry layout claimed externally:
    +0 w(u16) +2 h(u16) | +4 gfx +8 palette +12 layer0 +16 layer1
    +20 metatiles +24 terrain +28 background id.  w/4 x h/2 = tile grid.
    """
    print("=== A. map table 0x53D910 — field order proven by decompressed sizes ===")
    for i in (0, 1, 3):
        p = MAP_TABLE + i * 32
        w, h = rom.u16(p), rom.u16(p + 2)
        tw, th = w // 4, h // 2
        print(f"\n-- entry {i}: raw w={w} h={h} -> grid {tw}x{th} tiles (+28={rom.u8(p + 28)})")
        for label, off in (
            ("+4", p + 4),
            ("+8", p + 8),
            ("+12", p + 12),
            ("+16", p + 16),
            ("+20", p + 20),
            ("+24", p + 24),
        ):
            ptr = rom.u32(off)
            blob = rom.lz77(ptr - BASE)
            if blob is None:
                print(f"   {label:4s} ptr={ptr:08X} (absent)")
                continue
            note = []
            if len(blob) == tw * th * 2:
                note.append("== terrain/tilemap cell count")
            if len(blob) % 8 == 0 and len(blob) // 8 >= 32:
                note.append(f"metatile-sized ({len(blob) // 8})")
            print(f"   {label:4s} ptr={ptr:08X} lz77={len(blob)} {' '.join(note)}")
    print()


def check_sprite_action(rom: Rom) -> None:
    """0x596ccc + id*144 + action*16 -> (frames, animations, gfx, palette).
    NOTE: this repo used to call 0x596D5C a "tile descriptor table"; it is in
    fact the id=1 row of the sprite action table.
    """
    print("=== B. sprite action table 0x596ccc (id*144 + action*16) ===")
    p = SPRITE_ACTION + 1 * 144
    frames, anim, gfx, pal = (rom.u32(p + k * 4) for k in range(4))
    print(f"  id=1 action=0: frames={frames:08X} anim={anim:08X} gfx={gfx:08X} pal={pal:08X}")
    print(f"  palette 32 bytes = {rom.head(pal - BASE, 32)}")
    print(f"  palette as BGR555 = {[hex(rom.u16(pal - BASE + 2 * i)) for i in range(16)]}")
    print()


def check_portraits(rom: Rom) -> None:
    print("=== C. portrait pointer table 0x5a4dec (id*40 + expr*8) ===")
    for cid in (1, 2, 47):
        for expr in (0, 1):
            q = PORTRAIT_PTR + cid * 40 + expr * 8
            g_ptr, p_ptr = rom.u32(q), rom.u32(q + 4)
            blob = rom.lz77(g_ptr - BASE)
            print(
                f"  id={cid:2d} expr={expr}: gfx={g_ptr:08X} "
                f"(lz77 {None if blob is None else len(blob)}) pal={p_ptr:08X}"
            )
    print()


def check_portrait_pieces(rom: Rom) -> None:
    print("=== D. portrait piece table 0x4643c0 (20 bytes/piece) ===")
    for j in range(6):
        q = PORTRAIT_PIECE + j * 20
        tile = rom.u32(q)
        x, y = rom.u16(q + 4), rom.u16(q + 6)
        w, h = rom.u16(q + 8), rom.u16(q + 10)
        print(
            f"  piece{j}: tile={tile} x={x} y={y} w={w} h={h} "
            f"(fits 80x80: {x + w <= 80 and y + h <= 80})"
        )
    print()


def check_scripts(rom: Rom) -> None:
    print("=== E. story script roots (before/after/logic/events) ===")
    for name, tbl in (("before", BEFORE), ("after", AFTER), ("logic", LOGIC), ("events", EVENTS)):
        for scene in (1, 2, 20):
            ptr = rom.u32(tbl + scene * 4)
            if ptr == 0:
                continue
            print(f"  {name:6s} scene{scene:3d} -> {ptr:08X}: {rom.head(ptr - BASE, 24)}")
        print()


def check_opcodes(rom: Rom) -> None:
    print("=== F. opcode census across native stage 1..5 before+after scripts ===")
    interesting = {0, 1, 2, 3, 6, 7, 9, 10, 13, 19, 20, 21, 25, 26, 27, 30, 31, 32, 33, 34, 50, 52, 54, 55, 56, 57}
    census: Counter[int] = Counter()
    for scene in range(1, 6):
        for tbl in (BEFORE, AFTER):
            ptr = rom.u32(tbl + scene * 4)
            if not ptr:
                continue
            base = ptr - BASE
            for k in range(0, 200):
                op = rom.u8(base + k)
                if op in interesting:
                    census[op] += 1
    for op, n in sorted(census.items()):
        print(f"  op 0x{op:02X} ({op:3d}): {n}")
    print()


def check_mission_texts(rom: Rom) -> None:
    print("=== G. mission index 0x348dac + three mission text tables ===")
    print(f"  index bytes: {list(rom.data[MISSION_INDEX:MISSION_INDEX + 48])}")
    for stage in (1, 2):
        base_idx = rom.u8(MISSION_INDEX + stage)
        print(f"  stage {stage}: missionIndex={base_idx}")
        for sub in range(3):
            idx = base_idx + sub
            for tbl, label in zip(MISSION_TABLES, ("title", "desc", "hint")):
                ptr = rom.u32(tbl + idx * 4)
                print(
                    f"    sub{sub} {label:5s} idx={idx:3d} ptr={ptr:08X} "
                    f"bytes={rom.text_at(ptr - BASE, 32).hex(' ')}"
                )
    print()


def check_misc_tables(rom: Rom) -> None:
    print("=== H. remaining externally-claimed tables (raw heads) ===")
    for name, off, n in (
        ("rules 0x594758", RULES, 16),
        ("rewards 0x59eae0", REWARDS, 16),
        ("skillTbl 0x545458", SKILL_TABLE, 16),
        ("actors 0x5461c4", ACTORS, 16),
        ("itemNames 0x599634", ITEM_NAMES, 16),
        ("upgradeNames 0x5a7e8c", UPGRADE_NAMES, 16),
        ("names 0x599280", NAMES, 16),
    ):
        print(f"  {name:22s} {rom.head(off, n)}")
    print("  name table samples:")
    for i in range(1, 6):
        off = rom.u32(NAMES + i * 4) - BASE
        print(f"    id {i}: {rom.text_at(off, 24).hex(' ')}")
    print("  item-name table samples (CONTRADICTS our 'audio index' note):")
    for i in range(1, 4):
        off = rom.u32(ITEM_NAMES + i * 4) - BASE
        print(f"    id {i}: {rom.text_at(off, 24).hex(' ')}")
    print()


def check_font_segments(rom: Rom) -> None:
    print("=== I. font segment table 0x53d644 (8 bytes: start u16, count u8, offset u32) ===")
    for i in range(8):
        p = FONT_SEGMENTS + i * 8
        start = rom.u16(p)
        count = rom.u8(p + 2)
        off = rom.u32(p + 4)
        print(f"  seg{i}: start=0x{start:04X} count={count} offset=0x{off:08X} (file 0x{off - BASE:X})")
    print()


def main() -> None:
    rom_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ROM
    rom = Rom(rom_path)
    print(f"ROM   : {rom_path}")
    print(f"size  : {len(rom.data)} bytes (0x{len(rom.data):X})")
    print(f"sha256: {hashlib.sha256(rom.data).hexdigest()}")
    print(f"sha1  : {hashlib.sha1(rom.data).hexdigest()}")
    print()

    check_map_table(rom)
    check_sprite_action(rom)
    check_portraits(rom)
    check_portrait_pieces(rom)
    check_scripts(rom)
    check_opcodes(rom)
    check_mission_texts(rom)
    check_misc_tables(rom)
    check_font_segments(rom)


if __name__ == "__main__":
    main()
