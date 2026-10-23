#!/usr/bin/env python3
"""修正「说话人名表读者」补丁里的**解引用指令编码**（第十八轮）。

问题
----
补丁清单把解引用写成 Thumb-1 的**寄存器偏移**形式 `ldr rD, [rD, rD]`。
但 Thumb-1 的寄存器偏移寻址是

    LDR Rd, [Rn, Rm, LSL #shift]      —— 地址 = Rn + (Rm << shift)

所以 `ldr r1, [r1, r1]` 算的是 **r1 + r1 = 2×r1**，**不是** `*(r1)`。
清单里把它当成「capstone 渲染成 `[r0,r0]`，语义上是 `ldr r0,[r0]`」—— 那个理解是错的。

正确的写法是**立即数偏移**形式（Rn 可以等于 Rt，没有那种约束）：

    LDR Rd, [Rn, #imm]                 —— 编码 0x6800 | (Rn<<3) | Rt

`imm = 0` ⇒ `ldr rD, [rD, #0]` ⇒ 读的就是 `*(rD)` ✓。

用法
----
    python tools/fix_speaker_deref.py            # 修正清单（就地改）
    python tools/fix_speaker_deref.py --check    # 只检查，不改

依据：notes/evidence/speaker-name-code-patches-20261023.md
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO / "tools" / "data" / "speaker_name_code_patches.json"
sys.path.insert(0, str(REPO / "tools"))

from capstone_loader import load_capstone  # noqa: E402

capstone = load_capstone()

# LDR (immediate) T1：0110 0 imm5 Rn Rt
LDR_IMM = 0x6800


def ldr_imm(rt: int, rn: int) -> int:
    """`ldr r{rt}, [r{rn}, #0]` 的半字编码。"""
    return LDR_IMM | (rn << 3) | rt


def encode_ldr_imm(text: str) -> int:
    """把「ldr rD, [rD, #0]」变成半字编码。"""
    match = re.fullmatch(r"ldr r(\d+), \[r(\d+), #0\]", text.strip())
    if not match:
        raise ValueError(f"看不懂的指令：{text!r}")
    rt, rn = int(match.group(1)), int(match.group(2))
    if rt != rn:
        raise ValueError(f"这条补丁要求基址寄存器 == 目标寄存器：{text!r}")
    return ldr_imm(rt, rn)


def main() -> int:
    check_only = "--check" in sys.argv
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    changed = 0
    problems = []

    for patch in data.get("patches", []):
        after = bytes.fromhex(patch["after_hex"])
        new_disasm = list(patch.get("new_disasm") or [])
        # 找到那条「解引用」指令（它在倒数第二位，后面跟着 nop）。
        index = None
        for i, line in enumerate(new_disasm):
            if re.match(r"ldr r\d+, \[r\d+, ?r\d+\]", line.strip()):
                index = i
                break
        if index is None:
            problems.append(f"补丁 {patch.get('site')}：清单里找不到解引用指令")
            continue
        text = new_disasm[index]
        match = re.match(r"ldr r(\d+), \[r(\d+), ?r(\d+)\]", text.strip())
        rt = int(match.group(1))
        half = int.from_bytes(after[index * 2:index * 2 + 2], "little")
        # 寄存器偏移形式 ⇒ 地址 = 基址 + 偏移（= 2×rD）⇒ 错的。
        if (half & 0xF800) == 0x5800:
            want = encode_ldr_imm(f"ldr r{rt}, [r{rt}, #0]")
            after = after[:index * 2] + want.to_bytes(2, "little") + after[index * 2 + 2:]
            new_disasm[index] = f"ldr r{rt}, [r{rt}, #0]"
            patch["after_hex"] = after.hex()
            patch["new_disasm"] = new_disasm
            patch["note"] = (patch.get("note") or "") + (
                " 【第十八轮更正】解引用原本写成 Thumb-1 的寄存器偏移形式 "
                f"`ldr r{rt}, [r{rt}, {rt}]`，那算的是 {rt} + {rt} = 2×r{rt}，"
                f"**不是** *(r{rt})*；已改成立即数偏移形式 `ldr r{rt}, [r{rt}, #0]`。"
            )
            changed += 1
        elif (half & 0xF800) != 0x6000:
            problems.append(f"补丁 {patch.get('site')}：解引用既不是寄存器偏移也不是立即数偏移")

    # 逐条用 capstone 复核语义。
    for patch in data.get("patches", []):
        after = bytes.fromhex(patch["after_hex"])
        for i in range(0, len(after) - 1, 2):
            half = int.from_bytes(after[i:i + 2], "little")
            for ins in md.disasm(after[i:i + 2], 0x08000000 + patch["rom_offset"] if isinstance(
                    patch["rom_offset"], int) else 0):
                text = f"{ins.mnemonic} {ins.op_str}".replace(",", ",")
                if ins.mnemonic == "ldr" and "[" in ins.op_str:
                    # 基址与偏移都用同一个寄存器 ⇒ 地址翻倍 ⇒ 不对。
                    m = re.match(r"r(\d+)\s*,\s*\[r(\d+)(?:,\s*r(\d+))?\]", ins.op_str)
                    if m and m.group(2) and m.group(3) and m.group(2) == m.group(3):
                        problems.append(
                            f"补丁 {patch.get('site')}：仍有寄存器偏移解引用 {ins.op_str}")

    if problems:
        for p in problems:
            print("ERR " + p)
        return 1
    if changed and not check_only:
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
    print(f"修正了 {changed} 处解引用编码；清单{'已写回' if changed and not check_only else '无需改动'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
