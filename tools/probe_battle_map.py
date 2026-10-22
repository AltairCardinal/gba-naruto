"""核实：单张战斗地图的尺寸、tilemap/terrain 的字节数、坐标单位。

这是「战斗地图可视化」的事实依据（notes/evidence/battle-map-render-facts-20261022.md）。
用仓库自己的 LZ77 解码器（tools/lib/lz77.py）解 ROM 里的压缩块，逐条量。

用法：python tools/probe_battle_map.py
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.lib.lz77 import decompress  # noqa: E402

ROM = Path("rom/base.gba").read_bytes()
BASE = 0x08000000
MAP_TABLE = 0x053D910
ENTRY = 32


def u32(off):
    return struct.unpack_from("<I", ROM, off)[0]


def u16(off):
    return struct.unpack_from("<H", ROM, off)[0]


def lz(off):
    """Decompress the LZ77 block at file offset `off` (0 = none)."""
    if not off:
        return None
    return decompress(ROM, off)


print("=== 地图表前 6 条 ===")
print("  条  原始宽 原始高  图块宽×高  terrain字节  metatile字节  layer0字节  layer1")
for i in range(6):
    base = MAP_TABLE + i * ENTRY
    raw_w = u16(base + 0x00)
    raw_h = u16(base + 0x02)
    w, h = raw_w // 4, raw_h // 2
    terrain = lz(u32(base + 0x18) - BASE)
    meta = lz(u32(base + 0x14) - BASE)
    layer0 = lz(u32(base + 0x0C) - BASE)
    layer1_off = u32(base + 0x10)
    layer1 = lz(layer1_off - BASE) if layer1_off else None
    print("  %2d  %5d %5d  %3d×%-3d  %10s  %10s  %10s  %s" % (
        i, raw_w, raw_h, w, h,
        len(terrain) if terrain else "-",
        len(meta) if meta else "-",
        len(layer0) if layer0 else "-",
        len(layer1) if layer1 else "-",
    ))
    if terrain:
        print("       terrain == w*h*2 ? %s（%d vs %d）"
              % (len(terrain) == w * h * 2, len(terrain), w * h * 2))
    if layer0:
        print("       layer0 == w*h*2 ? %s（%d vs %d）  // 每格 u16"
              % (len(layer0) == w * h * 2, len(layer0), w * h * 2))
    if meta:
        print("       metatile 是 8 字节的倍数 ? %s（%d 项）" % (len(meta) % 8 == 0, len(meta) // 8))

print()
print("=== 坐标单位：物件 / 角色出生点的 x/y 取值范围 ===")
ACTORS = 0x05461C4
GROUP_STRIDE = 0x1AAC
SUB_STRIDE = 0x8E4
SLOT_STRIDE = 0xB8
OBJ_OFFSET = 0x8A4
OBJ_STRIDE = 4

xs, ys = [], []
for s in range(47):
    for v in range(3):
        for k in range(12):
            off = ACTORS + s * GROUP_STRIDE + v * SUB_STRIDE + 4 + k * SLOT_STRIDE
            xs.append(ROM[off + 2])
            ys.append(ROM[off + 3])
print("  角色出生点 x: %d..%d   y: %d..%d" % (min(xs), max(xs), min(ys), max(ys)))

oxs, oys = [], []
for s in range(47):
    for v in range(3):
        base = ACTORS + s * GROUP_STRIDE + v * SUB_STRIDE + OBJ_OFFSET
        for o in range(16):
            off = base + o * OBJ_STRIDE
            oxs.append(ROM[off + 2])
            oys.append(ROM[off + 3])
print("  战场物件   x: %d..%d   y: %d..%d" % (min(oxs), max(oxs), min(oys), max(oys)))

print()
print("=== 地图 0 的尺寸 vs 坐标范围 ===")
base = MAP_TABLE
w, h = u16(base) // 4, u16(base + 2) // 2
print("  地图 0 = %d×%d 图块；角色 x 范围 %d..%d" % (w, h, min(xs), max(xs)))
print("  ⇒ 坐标单位看起来是「图块格」（与地图宽高同量级），不是像素")
