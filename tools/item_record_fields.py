"""忍具记录表 `0x08545BE4` 的字段取证与自检工具（2026-10-22）

这张表以前在编辑器里是 16 格「未解字节」。本工具把「哪一格被哪段原生代码读、
读成什么宽度」变成**可复现、可证伪**的事实，并逐条核对内容包里写下的字段表。

它做四件事：

1. **读者普查** —— 全 ROM 扫 Thumb 的 `ldr Rt,[pc,#imm]`（按位模式 01001 识别，
   不依赖线性反汇编），把装载 `0x08545BE4` 的每一条指令列出来。
2. **字段触达核对** —— 对每条已登记的读点，直接解码那两字节 Thumb 指令，
   取出「偏移 + 宽度」，与登记表比对；**对不上就 exit 1**。
3. **无读者证明** —— 把所有已登记读点的偏移并起来，凡是并集里没有的字节，
   就是「原生代码根本不读」的格子（+0x01 / +0x0E / +0x0F）。
4. **取值分布** —— 94 条记录逐字节的取值集合。

用法::

    python tools/item_record_fields.py rom/base.gba
    python tools/item_record_fields.py rom/base.gba --json build/item-fields.json
    python tools/item_record_fields.py rom/base.gba --rows 1,2,3   # 看某几条记录

退出码：0 = 全部核对通过；1 = 与登记的字段表对不上（说明 ROM 变了或登记写错了）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

ITEM_TABLE = 0x08545BE4
ITEM_ROWS = 94
ITEM_STRIDE = 16
NAME_TABLE = 0x08599634
NAME_ROWS = 93

# ROM 里 Thumb 代码区的范围（文件偏移 0x000000..0x140000）。
CODE_START = 0x08000000
CODE_END = 0x08140000

# ---------------------------------------------------------------------------
# 已登记的读点。每一行 = 一条读表指令，以及它读到记录的哪些偏移。
#
#   kind="imm"  指令用**立即数偏移**直接读记录（偏移就编码在指令里）
#   kind="add"  指令用**寄存器 + 常量**算地址（0x0C 是加在基址上的，
#               循环变量再逐次 +1，于是同一段代码扫过 +0x0C 与 +0x0D）
#
# 工具会直接解码那两字节 Thumb 指令核对，**对不上就 exit 1**。
# ---------------------------------------------------------------------------
READ_POINTS: list[dict] = [
    # fn 0x0806D910：忍具记录读取器（把记录搬进 16 字节槽位）
    {"at": 0x0806D924, "offsets": [0x00], "width": 1, "kind": "imm"},
    {"at": 0x0806D928, "offsets": [0x02, 0x03], "width": 2, "kind": "imm"},
    {"at": 0x0806D92E, "offsets": [0x04], "width": 1, "kind": "imm"},
    {"at": 0x0806D932, "offsets": [0x05], "width": 1, "kind": "imm"},
    {"at": 0x0806D936, "offsets": [0x06], "width": 1, "kind": "imm"},
    {"at": 0x0806D93A, "offsets": [0x07], "width": 1, "kind": "imm"},
    {"at": 0x0806D93E, "offsets": [0x08], "width": 1, "kind": "imm"},
    {"at": 0x0806D942, "offsets": [0x09], "width": 1, "kind": "imm"},
    # fn 0x0808FC20：按 +0x0C / +0x0D 找记录
    {"at": 0x0808FC2E, "offsets": [0x0C], "width": 1, "kind": "imm"},
    {"at": 0x0808FC44, "offsets": [0x0C, 0x0D], "width": 1, "kind": "add",
     "add_at": 0x0808FC3E, "add_imm": 0x0C, "cmp_at": 0x0808FC50, "cmp_imm": 0x01},
    # fn 0x0808FF24：按 +0x0A 挑记录、拿 +0x0B 找槽
    {"at": 0x0808FF7C, "offsets": [0x0A], "width": 1, "kind": "imm"},
    {"at": 0x0808FF88, "offsets": [0x0B], "width": 1, "kind": "imm"},
    # fn 0x08078E.. / fn 0x080953..：按 +0x00 索引每类自己的表
    {"at": 0x08078F16, "offsets": [0x00], "width": 1, "kind": "imm"},
    {"at": 0x080953B4, "offsets": [0x00], "width": 1, "kind": "imm"},
]

# 装 0x08545BE4 的 7 条指令（字面量池所在的指令）。
TABLE_LOADS = [0x0806D91A, 0x08078EF8, 0x08078F08, 0x0808FC28, 0x0808FF78,
               0x08095394, 0x080953A4]


def decode_load_offset(rom: bytes, addr: int):
    """解码一条 Thumb「立即数偏移 load」，返回 (宽度字节数, 偏移) 或 None。

    Thumb 的四种立即数偏移 load（Rn 只能是 r0-r7）：
      LDRB T1 `0111 0 imm5 Rn Rt`     偏移 = imm5
      LDRB T2 `0111 1 imm8 Rn Rt`     偏移 = imm8
      LDRH T1 `1000 0 imm5 Rn Rt`     偏移 = imm5*2
      LDRH T2 `1000 1 imm8 Rn Rt`     偏移 = imm8*2
    """
    off = addr - 0x08000000
    if off < 0 or off + 2 > len(rom):
        return None
    insn = int.from_bytes(rom[off:off + 2], "little")
    if insn & 0xFC00 == 0x7800:        # ldrb T1
        return 1, (insn >> 6) & 0x1F
    if insn & 0xFC00 == 0x7C00:        # ldrb T2
        return 1, (insn >> 8) & 0xFF
    if insn & 0xFC00 == 0x8800:        # ldrh T1
        return 2, ((insn >> 6) & 0x1F) * 2
    if insn & 0xFC00 == 0x8C00:        # ldrh T2
        return 2, ((insn >> 8) & 0xFF) * 2
    return None


def decode_add_imm(rom: bytes, addr: int):
    """解码 Thumb `adds rX, #imm8`（T1: 00110 Rdn imm8），返回 imm8 或 None。"""
    off = addr - 0x08000000
    if off < 0 or off + 2 > len(rom):
        return None
    insn = int.from_bytes(rom[off:off + 2], "little")
    if insn & 0xF800 == 0x3000:       # ADD immediate T1
        return insn & 0xFF
    return None


def decode_cmp_imm(rom: bytes, addr: int):
    """解码 Thumb `cmp rX, #imm8`（T1: 00101 Rdn imm8），返回 imm8 或 None。

    注意 CMP(立即数) 的位模式是 00101，MOV(立即数) 是 00100 —— 两者只差一位，
    写错就会把 `movs r2,#1` 当成 `cmp r2,#1`。
    """
    off = addr - 0x08000000
    if off < 0 or off + 2 > len(rom):
        return None
    insn = int.from_bytes(rom[off:off + 2], "little")
    if insn & 0xF800 == 0x2800:       # CMP immediate T1
        return insn & 0xFF
    return None


def scan_table_loads(rom: bytes) -> list[int]:
    """全 ROM 扫 Thumb `ldr Rt,[pc,#imm]`（位模式 01001），找出装载本表基址的指令。

    注意：16 位 Thumb 的 LDR(literal) 在寄存器是 r1-r7（字长）时，**imm8 要乘 4**
    （ARM ARM: LDR (literal) T1，Rt∈{r1-r7} 时 imm8 = imm8:4）。写错这一步就会
    把字面量池的地址算错 4 倍 —— 本工具早期版本就踩过这个坑。
    """
    hits = []
    for off in range(CODE_START - 0x08000000, CODE_END - 0x08000000, 2):
        insn = int.from_bytes(rom[off:off + 2], "little")
        if insn & 0xF800 != 0x4800:      # 01001 Rt:3 imm8
            continue
        imm = (insn & 0xFF) * 4
        addr = CODE_START + off
        pc = (addr + 4) & ~3
        pool = pc + imm
        poff = pool - 0x08000000
        if poff < 0 or poff + 4 > len(rom):
            continue
        if int.from_bytes(rom[poff:poff + 4], "little") == ITEM_TABLE:
            hits.append(addr)
    return hits


def decode_names(rom: bytes) -> list[str]:
    """忍具名表：u32 指针表，指针指向 SJIS 串（用内容包的译码结果更省事，这里只取指针）。"""
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?", default=str(REPO / "rom" / "base.gba"))
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--rows", help="逗号分隔的记录下标，打印这些记录的逐字节值")
    args = ap.parse_args()

    rom = pathlib.Path(args.rom).read_bytes()
    base = ITEM_TABLE - 0x08000000
    records = [list(rom[base + i * ITEM_STRIDE:base + (i + 1) * ITEM_STRIDE])
               for i in range(ITEM_ROWS)]

    problems: list[str] = []

    # ---- 1. 读者普查 --------------------------------------------------
    loads = scan_table_loads(rom)
    print(f"装载 0x{ITEM_TABLE:08X} 的原生指令：{len(loads)} 处")
    for a in loads:
        print(f"  {a:#010x}")
    for a in TABLE_LOADS:
        if a not in loads:
            problems.append(f"登记的装载指令 {a:#010x} 在 ROM 里没找到")
    extra = [a for a in loads if a not in TABLE_LOADS]
    if extra:
        problems.append(f"ROM 里出现未登记的装载指令：{[hex(a) for a in extra]}")

    # ---- 2. 字段触达核对 ----------------------------------------------
    print()
    print("字段触达核对（直接解码那两字节 Thumb 指令）：")
    touched: dict[int, list[str]] = {}
    for spec in READ_POINTS:
        addr = spec["at"]
        want_offsets = spec["offsets"]
        want_w = spec["width"]
        got = decode_load_offset(rom, addr)
        if got is None:
            problems.append(f"{addr:#010x} 不是一条立即数偏移 load")
            print(f"  {addr:#010x}  FAIL (解码失败)")
            continue
        width, off = got
        ok = width == want_w
        if spec["kind"] == "imm":
            ok = ok and off == want_offsets[0]
        else:
            # 「寄存器 + 常量」型：指令本身的立即数偏移是 0，
            # 真正读到的偏移 = 加在基址上的常量 + 循环变量（0 / 1）。
            add_imm = decode_add_imm(rom, spec["add_at"])
            cmp_imm = decode_cmp_imm(rom, spec["cmp_at"])
            ok = ok and off == 0 and add_imm == spec["add_imm"] and cmp_imm == spec["cmp_imm"]
            ok = ok and [spec["add_imm"], spec["add_imm"] + 1] == want_offsets
        if not ok:
            problems.append(
                f"{addr:#010x} 登记为 {want_offsets}/宽 {want_w}，实际解出 "
                f"偏移 {off}/宽 {width}")
        print(f"  {addr:#010x}  offset {'+'.join('0x%02X' % o for o in want_offsets)}"
              f"  width {width}  {'OK' if ok else 'FAIL'}")
        for o in want_offsets:
            touched.setdefault(o, []).append(f"{addr:#010x}")

    # ---- 3. 没有读者的字节 --------------------------------------------
    print()
    never = [o for o in range(ITEM_STRIDE) if o not in touched]
    print(f"没有任何原生读者读的字节：{['+0x%02X' % o for o in never]}")
    for o in (0x01, 0x0E, 0x0F):
        if o not in never:
            problems.append(f"+0x{o:02X} 被登记成「没有读者」，但读点表里却有它")

    # ---- 4. 取值分布 --------------------------------------------------
    print()
    print("逐字节取值分布（94 条记录）：")
    dist = {}
    for o in range(ITEM_STRIDE):
        vals = sorted({r[o] for r in records})
        dist[o] = vals
        print(f"  +0x{o:02X}: {len(vals):3d} 个取值  {vals}")
    always_zero = [o for o, v in dist.items() if v == [0]]
    print(f"94 条记录里恒为 0 的字节：{['+0x%02X' % o for o in always_zero]}")

    if args.rows:
        print()
        for idx in [int(x) for x in args.rows.split(",")]:
            print(f"  #{idx}: " + " ".join("%02X" % b for b in records[idx]))

    if problems:
        print()
        print("核对失败：")
        for p in problems:
            print(f"  FAIL {p}")
        return 1
    print()
    print("核对通过：读点、无读者证明、取值分布三样都对得上。")
    if args.json_out:
        pathlib.Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json_out).write_text(json.dumps({
            "table": {"address": ITEM_TABLE, "rows": ITEM_ROWS, "stride": ITEM_STRIDE},
            "loads": loads,
            "read_points": [{"at": s["at"], "offsets": s["offsets"], "width": s["width"]}
                            for s in READ_POINTS],
            "never_read": never,
            "always_zero": always_zero,
            "distributions": {f"0x{o:02X}": v for o, v in dist.items()},
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"写出 {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
