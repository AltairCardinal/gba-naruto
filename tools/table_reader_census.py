"""任意表的「谁读哪一格」普查（2026-10-22）

`tools/item_record_fields.py` 证明忍具记录表那 16 格的方法可以推广到任何表：
把**装载表基址**的字面量指令全找出来，再看这些读者函数里
**带立即数偏移的 load** 落在记录的哪一格。

这个工具把「找读者 + 列候选读点 + 打印上下文」做成一条命令，
让「某张表还有几格没命名」变成可复现的机器事实，而不是靠记忆。

用法::

    python tools/table_reader_census.py --table 0x545BE4 --stride 16 --count 94
    python tools/table_reader_census.py --table 0x545BE4 --stride 16 --count 94 --json build/x.json

输出里：
* `loads` —— 装载表基址的指令地址（= 读者入口）；
* `readers` —— 每个读者附近带立即数偏移的 load（偏移 < stride 即「记录内某格」）；
* `context` —— 读者附近的反汇编，供人工逐条确认。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from capstone_loader import load_capstone  # noqa: E402

CODE_START = 0x08000000
CODE_END = 0x08140000

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def find_loads(rom: bytes, table_rom: int) -> list[int]:
    """全 ROM 扫 Thumb `ldr Rt,[pc,#imm]`，找出装载该表基址的指令。

    16 位 Thumb 的 LDR(literal) 在 r1..r7（字长）时 **imm8 要乘 4**。
    """
    target = (table_rom & 0xFFFFFFFF).to_bytes(4, "little")
    hits = []
    for off in range(CODE_START - 0x08000000, CODE_END - 0x08000000, 2):
        insn = int.from_bytes(rom[off:off + 2], "little")
        if insn & 0xF800 != 0x4800:
            continue
        imm = (insn & 0xFF) * 4
        addr = CODE_START + off
        pool = ((addr + 4) & ~3) + imm
        poff = pool - 0x08000000
        if poff < 0 or poff + 4 > len(rom):
            continue
        if rom[poff:poff + 4] == target:
            hits.append(addr)
    return hits


def disasm(rom: bytes, start: int, size: int):
    cs = load_capstone()
    md = cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_THUMB)
    return list(md.disasm(rom[start - 0x08000000:start - 0x08000000 + size], start))


# 带立即数偏移的 load：ldrb/ldrh/ldr/ldrsb/ldrsh（立即数形式）
OFFSET_FORMS = (
    (0x7800, 0xFC00, 1, False),   # ldrb T1 imm5
    (0x7C00, 0xFC00, 1, True),    # ldrb T2 imm8
    (0x8800, 0xFC00, 2, False),   # ldrh T1 imm5
    (0x8C00, 0xFC00, 2, True),    # ldrh T2 imm8
    (0x6800, 0xFC00, 4, True),    # ldr T1 imm8*4
)


def load_offsets(insn: int):
    """返回 (宽度, 偏移) 或 None。"""
    for base, mask, width, is8 in OFFSET_FORMS:
        if insn & mask == base:
            if is8:
                scale = 2 if width == 2 else (4 if width == 4 else 1)
                return width, ((insn >> 8) & 0xFF) * scale
            return width, ((insn >> 6) & 0x1F) * (2 if width == 2 else 1)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True, help="表基址（文件偏移或 0x08xxxxxx 形式）")
    ap.add_argument("--stride", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--count", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--window", type=lambda s: int(s, 0), default=0x100,
                    help="每个读者打印多少字节")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--no-context", action="store_true")
    args = ap.parse_args()

    rom = (REPO / "rom" / "base.gba").read_bytes()
    table = int(args.table, 0)
    table_rom = table if table >= 0x08000000 else table + 0x08000000

    loads = find_loads(rom, table_rom)
    print(f"表 {table_rom:#010x}（文件偏移 {table_rom - 0x08000000:#x}，"
          f"步长 {args.stride}，{args.count} 条）")
    print(f"装载它的指令：{len(loads)} 处")
    for a in loads:
        print(f"  {a:#010x}")
    print()

    readers = []
    for at in loads:
        # 往前找函数起点（push {..,lr}），往后取一段
        start = at
        for back in range(0x00, 0x300, 2):
            off = (at - back) - 0x08000000
            insn = int.from_bytes(rom[off:off + 2], "little")
            if insn & 0xFF00 == 0xB500:  # push {..,lr}
                start = at - back
                break
        insns = disasm(rom, start, args.window)
        reads = []
        for i in insns:
            if not i.mnemonic.startswith(("ldr", "ldrs")):
                continue
            if "[pc" in i.op_str:
                continue
            m = re.search(r"#(0x[0-9a-fA-F]+|\d+)\]", i.op_str)
            if m:
                off = int(m.group(1), 0)
            elif re.search(r"\[r\d+\]$", i.op_str):
                # 没有立即数 = 偏移 0（`ldrb r0,[r0]`）—— 这类最常见，别漏掉
                off = 0
            else:
                continue
            if off >= args.stride:
                continue
            reads.append({"at": i.address, "offset": off,
                          "text": f"{i.mnemonic} {i.op_str}"})
        readers.append({"load_at": at, "func_start": start, "reads": reads,
                        "context": [f"{i.address:#010x}: {i.bytes.hex():<10} "
                                    f"{i.mnemonic:<7} {i.op_str}" for i in insns]})
        offsets = sorted({r["offset"] for r in reads})
        print(f"  读者 {at:#010x}（函数起点 {start:#010x}）"
              f" → 记录内偏移 {['+0x%02X' % o for o in offsets]}")
        if not args.no_context:
            for i in insns:
                note = ""
                if i.mnemonic.startswith("ldr") and "[pc" in i.op_str:
                    pc = (i.address + 4) & ~3
                    m = re.search(r"#(0x[0-9a-fA-F]+|\d+)\]", i.op_str)
                    if m:
                        # capstone 印的是**字节偏移**（已经乘过 4），不要再乘
                        pool = pc + int(m.group(1), 0)
                        poff = pool - 0x08000000
                        if 0 <= poff <= len(rom) - 4:
                            val = int.from_bytes(rom[poff:poff + 4], "little")
                            note = f"   ; = {val:#010x}"
                print(f"    {i.address:#010x}: {i.bytes.hex():<10} {i.mnemonic:<7} {i.op_str}{note}")
        print()

    if args.json_out:
        pathlib.Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.json_out).write_text(json.dumps({
            "table": table_rom, "stride": args.stride, "count": args.count,
            "loads": loads, "readers": readers,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"写出 {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
