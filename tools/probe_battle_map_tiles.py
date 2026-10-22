"""核实二：tilemap / metatile / gfx / palette 各自装的是什么。

事实依据见 notes/evidence/battle-map-render-facts-20261022.md。
结论：tilemap 的每一条 u16 指的是**组合图块表**的下标，
组合图块表每项 8 字节 = 4 个 u16 的图块号（2×2 排布），
图块本身是 4bpp 8×8、每块 32 字节；调色板是 384 字节 = 192 个 BGR555 色值
（= 12 组 × 16 色，色号 = 4bpp 值 + 调色板组 × 16）。

用法：python tools/probe_battle_map_tiles.py
"""
import collections
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.lib.lz77 import decompress  # noqa: E402

ROM = Path("rom/base.gba").read_bytes()
BASE = 0x08000000
MAP_TABLE = 0x053D910


def u32(off):
    return struct.unpack_from("<I", ROM, off)[0]


def u16(off):
    return struct.unpack_from("<H", ROM, off)[0]


def lz(off):
    return decompress(ROM, off) if off else None


for i in (0, 1):
    base = MAP_TABLE + i * 32
    w, h = u16(base) // 4, u16(base + 2) // 2
    gfx = lz(u32(base + 0x04) - BASE)
    pal = lz(u32(base + 0x08) - BASE)
    layer0 = lz(u32(base + 0x0C) - BASE)
    meta = lz(u32(base + 0x14) - BASE)
    terrain = lz(u32(base + 0x18) - BASE)
    cells = w * h
    print("=== 地图 %d : %d×%d = %d 格 ===" % (i, w, h, cells))
    print("  gfx       %6d 字节  = %d 个 8×8 4bpp 图块（32 字节/个）? %s"
          % (len(gfx), len(gfx) // 32, len(gfx) % 32 == 0))
    print("  palette   %6d 字节  = %d 个 BGR555 色值（2 字节/个）? %s"
          % (len(pal), len(pal) // 2, len(pal) % 2 == 0))
    print("  layer0    %6d 字节  = %d 个 u16  (%d 格 × %s)"
          % (len(layer0), len(layer0) // 2, cells, len(layer0) // 2 // cells))
    print("  metatile  %6d 字节  = %d 项（8 字节/项）" % (len(meta), len(meta) // 8))
    print("  terrain   %6d 字节  = %d 个 u16（每格 1 个）" % (len(terrain), len(terrain) // 2))

    entries = struct.unpack_from("<%dH" % (len(layer0) // 2), layer0, 0)
    low = [e & 0x3FF for e in entries]
    meta_count = len(meta) // 8
    gfx_count = len(gfx) // 32
    print("  layer0 低 10 位：最大 %d，落在 metatile 数(%d)内? %s；落在 4bpp 图块数(%d)内? %s"
          % (max(low), meta_count, max(low) < meta_count,
             gfx_count, max(low) < gfx_count))
    print("  低 10 位的不同取值数：%d" % len(set(low)))
    print("  最常见 8 个：%s" % collections.Counter(low).most_common(8))
    upper = [(e >> 10) & 0x3F for e in entries]
    print("  高 6 位取值分布：%s" % collections.Counter(upper).most_common(6))
    print()
