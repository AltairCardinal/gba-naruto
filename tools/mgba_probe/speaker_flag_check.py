#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""说话人名表变长化 14 处补丁的**标志位（condition codes）语义**核对。

回答的问题（台账 N5③）
----------------------
**这 14 处补丁有没有改变标志位语义？**
更精确地说：**补丁前后的标志位，在离开补丁窗口的那一刻是否等价？**

做法
----
1. **静态**（默认）：逐处反汇编 OLD（`before_hex`）与 NEW（`after_hex`），
   列出每一处**写标志的指令**及顺序；对**最后一条写标志的指令**做符号求值
   （id ∈ [0,255]），算出**离开窗口时** N/Z/C/V 的取值；
   再把窗口之后 8 条（另附 16 条）指令里**读标志**的指令逐条列出来。
2. **实测**（`--hw`）：无头 mGBA，用 CLI 的 **`next`（单步一条）** 走剧情路线，
   把单步轨迹记成 `[(PC, CPSR), …]`，在轨迹里找**窗口**的经过：
   **轨迹里 `PC == 窗口后第一条指令` 的那一拍 = 窗口最后一条指令刚执行完**
   ⇒ 那一拍的 CPSR 就是「离开补丁窗口时」的标志位。
   分别跑**原版 ROM** 与**转换版 ROM**，比对同一次窗口经过的 CPSR。

   ⚠️ **N/Z/C/V 在 `CPSR[31:28]`**，**低 5 位是处理器模式**（不是标志位）。
   ⚠️ **不能用断点取窗口处的 CPSR**：mGBA 的断点是「软件断点」，
   命中后**不暂停 CPU**（宿主 `frames` 报 `bp=0`，命中后 CPU 已跑到帧末），
   只有 CLI 的单步 `next` 能取到「某条指令执行后」的现场。

方法纪律（沿用 `speaker_freeze_trace.py` 的口径）
------------------------------------------------
* **判定「能跑 / 卡死」只看画面推进**；本工具**不做**能跑/卡死判定。
* 运行**只挂一个永不命中的死断点** `0x08FFFFFE`
  （宿主需要至少一条断点才会走「调试器路径」）。
* 原版与转换版**走同一条路线**（同一串按键），逐次窗口经过一一对应。
* 批量单步**必须分批写**（≤200 条/批）：一次写几千条会**死锁**
  （子进程 stdout 管道先满 ⇒ 双方互等）。

产物
----
    build/speaker-flag-check.json     机器可读结果
    stdout                            人读表格（可直接粘进报告）

依据：notes/evidence/speaker-name-flag-semantics-20261023.md
      notes/evidence/speaker-name-freeze-trace-20261023.md
      notes/evidence/speaker-names-hypothesis-ledger.md（N5③）
"""
from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from capstone_loader import load_capstone  # noqa: E402
from tools.mgba_probe.speaker_freeze_trace import (  # noqa: E402
    BOOT_FRAMES,
    DEAD_BP,
    FRAMES_PER_PRESS,
    GAP_FRAMES,
    KEY_BITS,
    Probe,
    arm,
    disarm,
    send,
    status_full,
)

ROM_BASE = 0x08000000
MANIFEST = REPO / "tools" / "data" / "speaker_name_code_patches.json"
BASE_ROM = REPO / "rom" / "base.gba"
CONV_ROM = REPO / "build" / "speaker-test.gba"
EXE = REPO / "build" / "mgba-probe" / "mgba-probe.exe"
OUT_JSON = REPO / "build" / "speaker-flag-check.json"

#: 说话人简称表基址（指针表 / 原版内联槽表的起点）
BASE_TABLE = 0x085A57C4

#: id 是从 `ldrb` 取出的一个字节 ⇒ 0..255
ID_MIN, ID_MAX = 0, 255

# ---------------------------------------------------------------- 标志位知识

#: **写标志**的 Thumb 指令（ARMv4T）。
#: 值 = 写了哪几个标志（N/Z/C/V）。未列出的标志**保持原值**。
FLAG_WRITERS: dict[str, str] = {
    "adds": "NZCV",     # ADD(S) T1/T2
    "adcs": "NZCV",
    "subs": "NZCV",
    "sbcs": "NZCV",
    "negs": "NZCV",
    "rsbs": "NZCV",
    "cmp": "NZCV",      # 只比较，不写结果寄存器
    "cmn": "NZCV",
    "tst": "NZC",
    "teq": "NZC",
    "ands": "NZC",
    "orrs": "NZC",
    "eors": "NZC",
    "bics": "NZC",
    "mvns": "NZC",
    "movs": "NZ",       # Thumb MOVS T1/T2：C 不变
    "muls": "NZ",       # ARMv4 MULS：N/Z 写，C/V 不变
    "lsls": "NZC",      # 移位：C 写，V 不变
    "lsrs": "NZC",
    "asrs": "NZC",
}

#: **读标志**的 Thumb 指令（条件执行 / 依赖进位）
COND_BRANCHES = {
    "beq": "Z", "bne": "Z", "bcs": "C", "bcc": "C",
    "bmi": "N", "bpl": "N", "bhi": "CV", "bls": "CV",
    "bge": "NV", "blt": "NV", "bgt": "NZV", "ble": "NZV",
}
FLAG_READERS = dict(COND_BRANCHES)
FLAG_READERS.update({"adc": "C", "adcs": "C", "sbc": "C", "sbcs": "C"})

#: 绝对无条件跳转（不读标志）
UNCOND = {"b", "bl", "blx", "bx", "pop", "push", "ldr", "str", "mov"}


def flags_of(cpsr: int | None) -> dict[str, int]:
    """CPSR → N/Z/C/V。

    ⚠️ ARM 的 N/Z/C/V 在 **CPSR[31:28]**，**低 5 位是处理器模式**（mode）。
    （CPSR[31:28]：N=bit31、Z=bit30、C=bit29、V=bit28）
    """
    if cpsr is None:
        return {}
    nib = (cpsr >> 28) & 0xF
    return {"N": (nib >> 3) & 1, "Z": (nib >> 2) & 1,
            "C": (nib >> 1) & 1, "V": nib & 1}


def flags_text(f: dict[str, int]) -> str:
    if not f:
        return "—"
    return "N=%d Z=%d C=%d V=%d" % (f["N"], f["Z"], f["C"], f["V"])


# ---------------------------------------------------------------- 反汇编

def disasm_thumb(code: bytes, addr: int):
    """反汇编一串 16 位 Thumb 指令。"""
    cs = load_capstone()
    md = cs.Cs(cs.CS_ARCH_ARM, cs.CS_MODE_THUMB)
    md.detail = False
    return list(md.disasm(code, addr))


def insn_text(insn) -> str:
    return f"{insn.mnemonic} {insn.op_str}".strip()


def read_rom(path: pathlib.Path) -> bytes:
    return path.read_bytes()


def rom_u32(rom: bytes, addr: int) -> int:
    off = addr - ROM_BASE
    return int.from_bytes(rom[off:off + 4], "little")


# ---------------------------------------------------------------- 符号求值

#: 一个寄存器值的符号形式：**id * k + c**（k、c 为整数）。
#: id 是「说话人 id」（一个字节，来自 `ldrb`）。
UNKNOWN = None


def val_id() -> tuple[int, int]:
    return (1, 0)


def val_const(c: int) -> tuple[int, int]:
    return (0, c)


def val_add(a, b):
    if a is None or b is None:
        return None
    return (a[0] + b[0], a[1] + b[1])


def val_lsl(a, n):
    if a is None:
        return None
    return (a[0] << n, a[1] << n)


def eval_flags_add(k: int, c: int) -> dict[str, int]:
    """`adds` 的结果 = id*k + c ⇒ N/Z/C/V（对 id ∈ [0,255] 取并集）。

    * N = 结果 bit31
    * Z = 结果是否为 0
    * C = 无符号进位（真值 > 0xFFFFFFFF）
    * V = 有符号溢出（真值超出 [-2^31, 2^31-1]）

    返回的是**并集**：只要有一个 id 让某标志为 1，就记 1。
    """
    out = {"N": 0, "Z": 0, "C": 0, "V": 0}
    for i in range(ID_MIN, ID_MAX + 1):
        true_val = i * k + c
        v = true_val & 0xFFFFFFFF
        out["N"] |= (v >> 31) & 1
        if v == 0:
            out["Z"] = 1
        if true_val > 0xFFFFFFFF or true_val < 0:
            out["C"] = 1
        if true_val < -(1 << 31) or true_val > (1 << 31) - 1:
            out["V"] = 1
    return out


# ---------------------------------------------------------------- 窗口分析

def parse_reg(text: str) -> int | None:
    text = text.strip().lower()
    if text.startswith("r"):
        tail = text[1:]
        if tail.isdigit():
            return int(tail)
    return None


def split_ops(op_str: str) -> list[str]:
    """按逗号切操作数，**但不能切开方括号里的逗号**。

    `ldr r1, [pc, #0x50]` ⇒ ['r1', '[pc, #0x50]']（不是 3 段）。
    """
    out: list[str] = []
    depth = 0
    cur = ""
    for ch in op_str:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def imm_of(text: str) -> int | None:
    text = text.strip().lstrip("#")
    try:
        return int(text, 0)
    except ValueError:
        return None


def analyze_window(insns, rom: bytes, id_reg: int | None,
                   seeds: dict[int, tuple[int, int]] | None = None):
    """对一条窗口序列做符号求值。

    `seeds` = 窗口开始前就已知取值的寄存器（例如 variant D 的基址寄存器）。

    返回：(每一行指令的信息, 结束时的寄存器表)
    每一行里带 `result_val` = 该指令执行**之后**它写的结果寄存器的值。
    """
    regs: dict[int, tuple[int, int] | None] = {}
    # id 寄存器一开始装的就是「说话人 id」（一个字节）
    if id_reg is not None:
        regs[id_reg] = val_id()
    for reg, v in (seeds or {}).items():
        regs[reg] = v
    rows = []
    for insn in insns:
        ops = split_ops(insn.op_str)
        mnemonic = insn.mnemonic
        wrote = FLAG_WRITERS.get(mnemonic, "")
        row = {"text": insn_text(insn), "addr": insn.address,
               "writes": wrote, "mnemonic": mnemonic, "result_val": None}
        new_vals: list[tuple[int | None, tuple[int, int] | None]] = []
        if mnemonic in ("lsls", "lsrs", "asrs") and len(ops) == 3:
            n = imm_of(ops[2])
            src = parse_reg(ops[1])
            dst = parse_reg(ops[0])
            val = val_lsl(regs.get(src), n) if n is not None else None
            row["result_val"] = val
            new_vals.append((dst, val))
        elif mnemonic == "adds" and len(ops) == 3:
            dst = parse_reg(ops[0])
            a = parse_reg(ops[1])
            b = parse_reg(ops[2])
            val = val_add(regs.get(a), regs.get(b))
            row["result_val"] = val
            new_vals.append((dst, val))
        elif mnemonic == "adds" and len(ops) == 2:
            dst = parse_reg(ops[0])
            imm = imm_of(ops[1])
            val = val_add(regs.get(dst), val_const(imm)) if imm is not None else None
            row["result_val"] = val
            new_vals.append((dst, val))
        elif mnemonic == "ldr" and len(ops) == 2 and "[pc" in ops[1].lower():
            dst = parse_reg(ops[0])
            lit = literal_of(insn, rom)
            val = val_const(lit[1]) if lit else None
            row["literal_addr"] = lit[0] if lit else None
            row["literal"] = lit[1] if lit else None
            new_vals.append((dst, val))
        elif mnemonic == "mov" and len(ops) == 2:
            new_vals.append((parse_reg(ops[0]), regs.get(parse_reg(ops[1]))))
        for dst, v in new_vals:
            if dst is not None:
                regs[dst] = v
        rows.append(row)
    return rows, regs


def literal_of(insn, rom: bytes) -> tuple[int, int] | None:
    """`ldr rX, [pc, #imm]` → (字面量地址, 字面量值)。"""
    ops = split_ops(insn.op_str)
    if len(ops) != 2 or "[pc" not in ops[1].lower():
        return None
    pc_base = insn.address + 4
    imm_txt = ops[1].split("#")[-1].rstrip("]").strip()
    try:
        imm = int(imm_txt, 0)
    except ValueError:
        return None
    lit_addr = (pc_base + imm) & ~3
    return lit_addr, rom_u32(rom, lit_addr)


def find_base_reg(insns, id_reg: int) -> int | None:
    """OLD 序列里「最后一条 `adds rX, rX, rY`」中的 rY = 基址寄存器。"""
    for insn in reversed(insns):
        ops = split_ops(insn.op_str)
        if insn.mnemonic == "adds" and len(ops) == 3:
            dst, a, b = parse_reg(ops[0]), parse_reg(ops[1]), parse_reg(ops[2])
            if dst == a and b != id_reg:
                return b
    return None


def find_base_load(rom: bytes, base_reg: int, window_start: int,
                   limit: int = 0x400) -> dict | None:
    """在窗口**之前**找「把基址装进 base_reg」的那条 `ldr rX, [pc, #imm]」。

    variant D（基址已在寄存器里）没有这条 `ldr`，基址是**同一函数里更早**装进去的。
    这里往回扫，找到**字面量 == BASE_TABLE** 的那条，返回它的地址与字面量。
    """
    for off in range(2, limit + 1, 2):
        addr = window_start - off
        if addr < ROM_BASE:
            break
        insns = disasm_thumb(rom[addr - ROM_BASE:addr - ROM_BASE + 2], addr)
        if not insns:
            continue
        insn = insns[0]
        ops = split_ops(insn.op_str)
        if insn.mnemonic != "ldr" or len(ops) != 2:
            continue
        if parse_reg(ops[0]) != base_reg:
            continue
        lit = literal_of(insn, rom)
        if lit and lit[1] == BASE_TABLE:
            return {"addr": addr, "text": insn_text(insn),
                    "literal_addr": lit[0], "literal": lit[1]}
    return None


def static_site(patch: dict, rom: bytes, rom_conv: bytes,
                all_windows: list[dict] | None = None) -> dict:
    """一处补丁的静态分析。"""
    addr = int(str(patch["rom_addr"]), 0)
    before = bytes.fromhex(str(patch["before_hex"]))
    after = bytes.fromhex(str(patch["after_hex"]))
    old_insns = disasm_thumb(before, addr)
    new_insns = disasm_thumb(after, addr)

    # id 寄存器 = OLD 第一条 `lsls` 的源寄存器
    id_reg = None
    if old_insns:
        ops = split_ops(old_insns[0].op_str)
        if old_insns[0].mnemonic.startswith("lsl") and len(ops) == 3:
            id_reg = parse_reg(ops[1])

    old_rows, old_regs = analyze_window(old_insns, rom, id_reg)
    new_rows, new_regs = analyze_window(new_insns, rom, id_reg)

    # ---- 基址寄存器：窗口里自己装，还是更早装好的（variant D）
    base_reg = find_base_reg(old_insns, id_reg)
    seeds: dict[int, tuple[int, int]] = {}
    base_load = None
    loaded_in_window = any(r.get("literal") == BASE_TABLE for r in old_rows)
    if base_reg is not None and not loaded_in_window:
        base_load = find_base_load(rom, base_reg, addr)
        if base_load:
            seeds[base_reg] = val_const(BASE_TABLE)
            old_rows, old_regs = analyze_window(old_insns, rom, id_reg, seeds)
            new_rows, new_regs = analyze_window(new_insns, rom, id_reg, seeds)

    # ---- OLD / NEW 各自「最后一条写标志的指令」+ 离开窗口时的标志位
    def last_flag_writer(rows, regs):
        for row in reversed(rows):
            if row["writes"]:
                return row
        return None

    def flags_at_exit(insns, rows, regs):
        """对最后一条写标志的指令求值，返回 (行号, 标志, 说明)。"""
        idx = None
        for i, row in enumerate(rows):
            if row["writes"]:
                idx = i
        if idx is None:
            return None, None, "窗口内没有写标志的指令"
        row = rows[idx]
        insn = insns[idx]
        if insn.mnemonic == "adds":
            val = row.get("result_val")
            if val is None:
                return row, None, "操作数无法求值"
            k, c = val
            f = eval_flags_add(k, c)
            return row, f, f"结果 = id*{k} + 0x{c:X}（id ∈ 0..255）"
        return row, None, f"未覆盖的写法：{row['text']}"

    old_row, old_flags, old_why = flags_at_exit(old_insns, old_rows, old_regs)
    new_row, new_flags, new_why = flags_at_exit(new_insns, new_rows, new_regs)

    equivalent = None
    if old_flags is not None and new_flags is not None:
        equivalent = old_flags == new_flags

    # ---- 基址字面量核对
    literals = []
    for insn in old_insns + new_insns:
        lit = literal_of(insn, rom)
        if lit:
            literals.append({"addr": insn.address, "literal_addr": lit[0],
                             "value": lit[1], "value_hex": f"0x{lit[1]:08X}"})

    # ---- 窗口之后 16 条指令里的标志读取者
    window_end = addr + len(after)
    after_bytes = rom[window_end - ROM_BASE: window_end - ROM_BASE + 32]
    after_insns = disasm_thumb(after_bytes, window_end)

    def collect_readers(limit: int) -> list[dict]:
        out = []
        for i, insn in enumerate(after_insns[:limit]):
            dep = FLAG_READERS.get(insn.mnemonic)
            if not dep:
                continue
            # 这条读标志的指令**依赖的标志**在窗口之后、到达它之前，
            # 有没有已经被别的写标志指令覆盖掉？
            overwritten = {}
            for j in range(i):
                w = FLAG_WRITERS.get(after_insns[j].mnemonic, "")
                for f in dep:
                    if f in w:
                        overwritten[f] = after_insns[j]
            still_from_patch = [f for f in dep if f not in overwritten]
            out.append({
                "idx": i, "addr": insn.address, "text": insn_text(insn),
                "depends": dep,
                "depends_on_patch": still_from_patch,
                "overwritten_by": {f: insn_text(v) for f, v in overwritten.items()},
            })
        return out

    readers8 = collect_readers(8)
    readers16 = collect_readers(16)

    # ---- 窗口内部有没有条件分支（有的话两版必须一致）
    cond_in_old = [insn_text(i) for i in old_insns if i.mnemonic in COND_BRANCHES]
    cond_in_new = [insn_text(i) for i in new_insns if i.mnemonic in COND_BRANCHES]

    # ---- 窗口之后的代码在两版 ROM 里必须逐字节相同（等长补丁的必然结果）
    tail8 = rom[window_end - ROM_BASE: window_end - ROM_BASE + 16]
    tail8_conv = rom_conv[window_end - ROM_BASE: window_end - ROM_BASE + 16]
    tail_same = tail8 == tail8_conv
    # 32 字节尾巴里如果还有别的补丁窗口，字节当然不同 —— 逐段列出差异
    diffs = []
    tail32 = rom[window_end - ROM_BASE: window_end - ROM_BASE + 32]
    tail32_conv = rom_conv[window_end - ROM_BASE: window_end - ROM_BASE + 32]
    for i in range(0, 32, 2):
        if tail32[i:i + 2] != tail32_conv[i:i + 2]:
            diffs.append(window_end + i)
    diff_in_other_patch = all(
        any(w["rom_addr"] <= a < w["rom_addr"] + w["byte_length"]
            for w in (all_windows or []))
        for a in diffs
    )

    # ---- 窗口之后的第一条指令是否立刻覆盖标志位？
    #      （若是 ⇒ 补丁留下的标志位在**任何读者到达之前**就被冲掉了 ⇒ 不可观测）
    first_after = None
    if after_insns:
        insn = after_insns[0]
        first_after = {"addr": insn.address, "text": insn_text(insn),
                       "writes": FLAG_WRITERS.get(insn.mnemonic, "")}
    overwrite_idx = None
    for i, insn in enumerate(after_insns[:8]):
        if FLAG_WRITERS.get(insn.mnemonic, ""):
            overwrite_idx = i
            break

    return {
        "site": patch["site"],
        "reader": patch["reader"],
        "variant": patch["variant"],
        "rom_addr": f"0x{addr:08X}",
        "window_end": f"0x{window_end:08X}",
        "byte_length": patch["byte_length"],
        "id_reg": id_reg,
        "base_reg": base_reg,
        "base_loaded_in_window": loaded_in_window,
        "base_load": base_load,
        "old_rows": old_rows,
        "new_rows": new_rows,
        "old_flag_writers": [r for r in old_rows if r["writes"]],
        "new_flag_writers": [r for r in new_rows if r["writes"]],
        "old_last_writer": old_row,
        "new_last_writer": new_row,
        "old_flags_at_exit": old_flags,
        "new_flags_at_exit": new_flags,
        "old_flags_text": flags_text(old_flags) if old_flags else "—",
        "new_flags_text": flags_text(new_flags) if new_flags else "—",
        "old_why": old_why,
        "new_why": new_why,
        "equivalent": equivalent,
        "literals": literals,
        "readers_after8": readers8,
        "readers_after16": readers16,
        "cond_in_old": cond_in_old,
        "cond_in_new": cond_in_new,
        "tail_identical": tail_same,
        "first_after_window": first_after,
        "first_flag_overwriter_idx": overwrite_idx,
        "tail32_diff_addrs": [f"0x{a:08X}" for a in diffs],
        "tail32_diffs_are_other_patches": diff_in_other_patch,
        "after_insns": [{"addr": i.address, "text": insn_text(i),
                         "reads": FLAG_READERS.get(i.mnemonic)}
                        for i in after_insns[:16]],
    }


# ---------------------------------------------------------------- 真机实测

HIT_RE = None
R15_RE = re.compile(r"r15:\s*([0-9A-Fa-f]{8})")
CPSR_RE = re.compile(r"cpsr:\s*([0-9A-Fa-f]{8})")
_SEQ = itertools.count(1)


def walk(probe: Probe, steps: int, chunk: int = 200,
         keep: list[tuple[str, int, int]] | None = None) -> dict:
    """单步 `steps` 条指令。

    `keep` = [(名字, 起址, 止址), ...]：只保留 PC 落在这些区间里的采样点，
    返回 {名字: [(pc, cpsr), ...]}（按执行顺序）。
    **必须**过滤：一次按键要走千万条指令，全存会吃掉几个 GB 内存。

    mGBA 的 CLI `next` = 执行**一条**指令后停下，并打印寄存器（含 cpsr）。
    实测：它会**走进被调用函数的函数体**（不是「跨过调用」）⇒
    可以一路单步走进剧情 VM 的 op 0x08 handler，在窗口边界读到 CPSR。

    ⚠️ **必须分批写**：一次写几千条 `next` 会**死锁** ——
    子进程每条要打印 14 行（约 500 字节），stdout 管道（64 KB）先满，
    子进程卡在写 stdout；此时本进程又卡在写 stdin（4 KB 管道缓冲）⇒ 双方互等。
    所以：**写一批（<= `chunk` 条）→ 把这一批的输出读干净 → 再写下一批**。
    """
    out: dict[str, list[tuple[int, int]]] = {name: [] for name, _, _ in (keep or [])}
    done = 0
    while done < steps:
        n = min(chunk, steps - done)
        token = f"__walk_{next(_SEQ):08d}"
        probe.proc.stdin.write(("next\n" * n) + f"echo {token}\n")
        probe.proc.stdin.flush()
        cur_pc: int | None = None
        while True:
            line = probe.proc.stdout.readline()
            if not line:
                raise EOFError("probe exited")
            if line[0] == "\n" or line[0] == "\r":
                continue
            # 每条 `next` 打印 14 行；只有两行有用（r15 与 cpsr）。
            # 先用子串过滤再上正则 —— 否则几千万行的正则会把 CPU 打满。
            if "r15:" in line:
                m = R15_RE.search(line)
                if m:
                    cur_pc = int(m.group(1), 16)
            elif "cpsr:" in line:
                m = CPSR_RE.search(line)
                if m and cur_pc is not None:
                    cpsr = int(m.group(1), 16)
                    for name, ws, we in (keep or []):
                        if ws <= cur_pc <= we:
                            out[name].append((cur_pc, cpsr))
            else:
                if line.rstrip("\r\n") == token:
                    break
        done += n
    return out


def window_runs(entries: list[tuple[int, int]]):
    """把「窗口内的采样点」切成一次次的经过。

    窗口内 PC 单调递增 ⇒ 遇到 PC 变小就是**另一次**经过。
    """
    runs = []
    cur: list[tuple[int, int]] = []
    for e in entries:
        if cur and e[0] <= cur[-1][0]:
            runs.append(cur)
            cur = []
        cur.append(e)
    if cur:
        runs.append(cur)
    return runs


def hw_measure_all(rom_path: pathlib.Path, sites: list[dict], presses: int,
                   max_walk: int = 12000000, chunk: int = 200,
                   max_hits: int = 3, progress: bool = True) -> dict:
    """走一遍剧情路线，**同时**记录 14 处窗口的经过。

    一条单步轨迹就能覆盖所有站点（轨迹里每个元素 = 执行完某条指令后的 PC），
    所以不必每个站点单独跑一遍。

    返回：{rom, found: {site: [...]}, notes: [...]}
    """
    ranges = [(s["site"], int(s["rom_addr"], 0), int(s["window_end"], 0)) for s in sites]
    found: dict[str, list[dict]] = {name: [] for name, _, _ in ranges}
    notes: list[str] = []
    probe = Probe(EXE, rom_path)
    try:
        send(probe, f"frames {BOOT_FRAMES} 0x000")
        arm(probe, DEAD_BP)
        # 按住 START，把剧情推进到「按 A 之前」
        send(probe, "key 0x008")
        walk(probe, min(max_walk, 1000000), chunk, ranges)
        send(probe, "key 0x000")

        for press in range(presses):
            send(probe, "key 0x001")
            samples: dict[str, list[tuple[int, int]]] = {n: [] for n, _, _ in ranges}
            walked = 0
            while walked < max_walk:
                got = walk(probe, chunk, chunk, ranges)
                walked += chunk
                for name in samples:
                    samples[name].extend(got.get(name, []))
                if any(samples.values()):
                    # 再走一小段，把同一段里的其它窗口也覆盖到
                    got = walk(probe, 2000, chunk, ranges)
                    walked += 2000
                    for name in samples:
                        samples[name].extend(got.get(name, []))
                    break
            send(probe, "key 0x000")
            for name, _, _ in ranges:
                for run in window_runs(samples[name]):
                    steps = [{"pc": f"0x{pc:08X}", "cpsr": f"0x{cpsr:08X}",
                              "flags": flags_text(flags_of(cpsr))}
                             for pc, cpsr in run]
                    after = run[-1]
                    found[name].append({
                        "press": press,
                        "steps_in_window": steps,
                        "at_window_end": {
                            "pc": f"0x{after[0]:08X}",
                            "cpsr": f"0x{after[1]:08X}",
                            "flags": flags_text(flags_of(after[1])),
                        },
                        "walked": walked,
                    })
            if press == 0 and not any(found.values()):
                notes.append(f"第 0 次按键：{walked} 步内 14 处窗口一处都没走到")
            if progress:
                got = {k: len(v) for k, v in found.items() if v}
                print(f"    [{rom_path.name}] press {press}: {walked} 步, "
                      f"命中 {got}", flush=True)
            # 已经有足够的样本就不必再按了（省时间）
            if max_hits and any(len(v) >= max_hits for v in found.values()):
                break
    finally:
        probe.close()
    return {"rom": str(rom_path.relative_to(REPO)), "found": found, "notes": notes}


def hw_measure_by_frame(rom_path: pathlib.Path, sites: list[dict],
                        max_frames: int = 600, save_path: pathlib.Path | None = None,
                        progress: bool = True, max_samples: int = 3) -> dict:
    """**逐帧**找窗口：找到窗口所在的那一帧，再把那一帧**单步**重放一遍取样。

    为什么不用「一直单步」（`hw_measure_all` 那种）：
    一帧 ≈ 28 万条指令，而 CLI 的 `next` 每条要打印 14 行 ⇒
    一帧的输出就有 400 万行 ⇒ 全程单步太慢。
    所以改成：
      1. **用断点找到窗口在哪一帧**（断点只用来「发现」，不取现场）；
         每一帧之前存一次 savestate（`save`）。
      2. 命中那一帧后 `load` 回那一帧之前，**只单步这一帧**（28 万步 ≈ 十几秒），
         在轨迹里读窗口边界的 CPSR。
    """
    ranges = [(s["site"], int(s["rom_addr"], 0), int(s["window_end"], 0)) for s in sites]
    found: dict[str, list[dict]] = {name: [] for name, _, _ in ranges}
    notes: list[str] = []
    save_path = save_path or (REPO / "build" / "speaker-flag-savestate.bin")
    probe = Probe(EXE, rom_path)
    try:
        send(probe, f"frames {BOOT_FRAMES} 0x000")
        arm(probe, DEAD_BP)
        # 「发现用」的断点：挂在**窗口之后第 2 条**指令上
        # （窗口本身的指令一条都不动 ⇒ 不扰动被测代码；
        #   断点命中时调试器会恢复原指令并重执行 ⇒ 净效果不变）
        det_addr = int(sites[0]["window_end"], 0) + 2
        arm(probe, det_addr)
        # START：剧情开始（与 `speaker_acceptance.py` 的路线一致：按住 30 帧 + 松 6 帧）
        send(probe, "key 0x008")
        send(probe, "run 30")
        send(probe, "key 0x000")
        send(probe, "run 6")
        # A：推进剧情。**必须**重复「按下-松开」才能一次次产生按键沿 ——
        # 一直按住只算一次沿，故事只推进一屏（实测：按住 A 连跑 400 帧，
        # vm_0x08 的窗口一次都没执行到）。
        hit_frame = None
        cur_key = 0x000
        hit_states: list[tuple[int, pathlib.Path]] = []
        for frame in range(max_frames):
            phase = frame % 36
            want = 0x001 if phase < 30 else 0x000
            if want != cur_key:
                send(probe, f"key {want:03X}")
                cur_key = want
            send(probe, f"save {save_path}")
            out = send(probe, "run 1")
            if any("Hit breakpoint" in line for line in out):
                hit_frame = frame
                keep = save_path.with_name(save_path.stem + f".hit{frame}.bin")
                keep.write_bytes(save_path.read_bytes())
                hit_states.append((frame, keep))
                if len(hit_states) >= max_samples:
                    break
            if progress and frame % 50 == 0:
                print(f"    [{rom_path.name}] 找窗口：已跑 {frame} 帧", flush=True)
        send(probe, "key 0x000")
        if not hit_states:
            notes.append(f"跑了 {max_frames} 帧都没命中窗口（断点 @ 0x{det_addr:08X}）")
            return {"rom": str(rom_path.relative_to(REPO)), "found": found,
                    "notes": notes, "hit_frame": None}
        # 回到每个命中帧之前，单步重放那一帧
        for frame, state_file in hit_states:
            send(probe, f"load {state_file}")
            # ⚠️ **load 之后必须重新设置按键**：`setKeys` 的按键状态**不在 savestate 里**
            # （实测：load 之后不重设，重放的那一帧就收不到按键沿 ⇒ 剧情不推进 ⇒
            #   窗口不会执行 ⇒ 采不到样  ）。
            phase = frame % 36
            send(probe, f"key {0x001 if phase < 30 else 0x000:03X}")
            samples = walk(probe, 400000, 200, ranges)
            for name, _, _ in ranges:
                for run in window_runs(samples.get(name, [])):
                    steps = [{"pc": f"0x{pc:08X}", "cpsr": f"0x{cpsr:08X}",
                              "flags": flags_text(flags_of(cpsr))}
                             for pc, cpsr in run]
                    after = run[-1]
                    found[name].append({
                        "press": frame,
                        "steps_in_window": steps,
                        "at_window_end": {
                            "pc": f"0x{after[0]:08X}",
                            "cpsr": f"0x{after[1]:08X}",
                            "flags": flags_text(flags_of(after[1])),
                        },
                        "walked": 400000,
                    })
            state_file.unlink(missing_ok=True)
            if progress:
                print(f"    [{rom_path.name}] 第 {frame} 帧：取到 "
                      f"{sum(len(v) for v in found.values())} 次采样", flush=True)
    finally:
        probe.close()
    return {"rom": str(rom_path.relative_to(REPO)), "found": found, "notes": notes,
            "hit_frame": hit_frame}


def hw_compare(sites: list[dict], presses: int, only: str | None,
               max_hits: int = 3, max_walk: int = 12000000,
               method: str = "frame") -> list[dict]:
    """原版 vs 转换版：逐站点、逐次比对窗口边界的 CPSR。

    `method`：
      * `frame` —— 逐帧找窗口所在帧 → 单步重放那一帧（快，默认）
      * `walk`  —— 一路单步（慢，但能一次采到多个样本）
    """
    picked = [s for s in sites if not only or s["site"] == only]
    if method == "walk":
        base = hw_measure_all(BASE_ROM, picked, presses, max_walk=max_walk,
                              max_hits=max_hits)
        conv = hw_measure_all(CONV_ROM, picked, presses, max_walk=max_walk,
                              max_hits=max_hits)
    else:
        base = hw_measure_by_frame(BASE_ROM, picked)
        conv = hw_measure_by_frame(CONV_ROM, picked)
    rows = []
    for site in picked:
        name = site["site"]
        b = base["found"].get(name, [])
        c = conv["found"].get(name, [])
        n = min(len(b), len(c))
        diffs = []
        for i in range(n):
            b_all = [s["flags"] for s in b[i]["steps_in_window"]]
            c_all = [s["flags"] for s in c[i]["steps_in_window"]]
            if b_all != c_all:
                diffs.append({"hit": i, "base": b_all, "conv": c_all})
        rows.append({
            "site": name,
            "rom_addr": site["rom_addr"],
            "window_end": site["window_end"],
            "base_hits": len(b),
            "conv_hits": len(c),
            "hit_count_equal": len(b) == len(c),
            "window_flags_diffs": diffs,
            "base_flags_at_exit": [h["at_window_end"]["flags"] for h in b],
            "conv_flags_at_exit": [h["at_window_end"]["flags"] for h in c],
            "base_cpsr_at_exit": [h["at_window_end"]["cpsr"] for h in b],
            "conv_cpsr_at_exit": [h["at_window_end"]["cpsr"] for h in c],
            "base_window_steps": [[s["flags"] for s in h["steps_in_window"]] for h in b],
            "conv_window_steps": [[s["flags"] for s in h["steps_in_window"]] for h in c],
            "notes": base["notes"] + conv["notes"],
        })
    return rows


# ---------------------------------------------------------------- 主流程

def print_static_table(sites: list[dict]) -> None:
    print("| # | site | reader | OLD 里写标志的指令（顺序） | NEW 里写标志的指令（顺序） "
          "| 离开窗口时标志位等价？ | 窗口之后 8 条里读标志的（哪一个） | 实测 |")
    print("|---|---|---|---|---|---|---|---|")
    for i, s in enumerate(sites, 1):
        old_w = " → ".join(f"`{r['text']}`" for r in s["old_flag_writers"]) or "（无）"
        new_w = " → ".join(f"`{r['text']}`" for r in s["new_flag_writers"]) or "（无）"
        if s["equivalent"] is True:
            eq = f"**是**（都是 {s['old_flags_text']}）"
        elif s["equivalent"] is False:
            eq = f"**否**（OLD {s['old_flags_text']} vs NEW {s['new_flags_text']}）"
        else:
            eq = "**未能求值**"
        if s["readers_after8"]:
            rd = "；".join(
                f"`{r['text']}`（依赖 {r['depends']}；"
                + ("**依赖补丁留下的标志位**" if r["depends_on_patch"]
                   else "到达前已被覆盖 ⇒ 不依赖补丁的标志位")
                + "）" for r in s["readers_after8"])
        else:
            rd = "**无**"
        print(f"| {i} | `{s['site']}` | {s['reader']} | {old_w} | {new_w} | {eq} | {rd} | 见实测表 |")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hw", action="store_true",
                    help="做真机 CPSR 比对（无头 mGBA）")
    ap.add_argument("--presses", type=int, default=14,
                    help="按 A 的次数（与 speaker_acceptance.py 的路线一致）")
    ap.add_argument("--only", default=None,
                    help="只实测某一处（site 名）")
    ap.add_argument("--max-hits", type=int, default=3,
                    help="每处站点采够多少个样本就停（默认 3）")
    ap.add_argument("--walk-budget", type=int, default=12000000,
                    help="每次按键最多单步多少条指令（默认 1200 万 ≈ 42 帧）")
    ap.add_argument("--method", choices=["frame", "walk"], default="frame",
                    help="实测手法：frame=逐帧找窗口再单步重放那一帧（快）；"
                         "walk=一路单步（慢，样本多）")
    ap.add_argument("--json", type=pathlib.Path, default=OUT_JSON)
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rom = read_rom(BASE_ROM)
    conv = read_rom(CONV_ROM)

    all_windows = [{"rom_addr": int(str(p["rom_addr"]), 0),
                    "byte_length": p["byte_length"],
                    "site": p["site"]} for p in manifest["patches"]]

    sites = [static_site(p, rom, conv, all_windows) for p in manifest["patches"]]

    print("=" * 100)
    print("静态判定：14 处补丁的标志位语义")
    print("=" * 100)
    for s in sites:
        print(f"\n■ {s['site']}（reader {s['reader']}, variant {s['variant']}, "
              f"窗口 {s['rom_addr']}..{s['window_end']}, {s['byte_length']} 字节）")
        print("  OLD:")
        for r in s["old_rows"]:
            mark = f"  ← 写标志 {r['writes']}" if r["writes"] else ""
            print(f"    0x{r['addr']:08X}  {r['text']}{mark}")
        print("  NEW:")
        for r in s["new_rows"]:
            mark = f"  ← 写标志 {r['writes']}" if r["writes"] else ""
            print(f"    0x{r['addr']:08X}  {r['text']}{mark}")
        print(f"  离开窗口时的标志位：OLD {s['old_flags_text']}（{s['old_why']}）")
        print(f"                      NEW {s['new_flags_text']}（{s['new_why']}）")
        print(f"  ⇒ 等价：{'是' if s['equivalent'] else ('否' if s['equivalent'] is False else '未求值')}")
        print(f"  窗口之后的指令（两版 ROM 逐字节相同：{s['tail_identical']}）：")
        for row in s["after_insns"][:8]:
            mark = f"  ← 读标志 {row['reads']}" if row["reads"] else ""
            print(f"    0x{row['addr']:08X}  {row['text']}{mark}")
        if s["readers_after16"]:
            extra = [r for r in s["readers_after16"] if r["idx"] >= 8]
            if extra:
                print(f"  窗口之后 8..16 条里还有读标志的："
                      + "；".join(f"`{r['text']}`（{r['depends']}）" for r in extra))
        for r in s["readers_after16"]:
            if r["depends_on_patch"]:
                print(f"  ⚠ 读标志者 `{r['text']}`（{r['depends']}）**依赖补丁留下的标志位**")
            else:
                print(f"  ✓ 读标志者 `{r['text']}`（{r['depends']}）不依赖补丁留下的标志位"
                      f"（到达它之前已被覆盖：{r['overwritten_by']}）")
        if s["tail32_diff_addrs"]:
            print(f"  窗口后 32 字节里与转换版不同的位置：{'、'.join(s['tail32_diff_addrs'])}"
                  f"（全部落在别的补丁窗口内：{s['tail32_diffs_are_other_patches']}）")
        for lit in s["literals"]:
            print(f"  字面量：0x{lit['literal_addr']:08X} = {lit['value_hex']}")

    print("\n" + "=" * 100)
    print("主表")
    print("=" * 100)
    print_static_table(sites)

    hw_rows = []
    if args.hw:
        print("\n" + "=" * 100)
        print("真机实测：CPSR 比对（原版 vs 转换版）")
        print("=" * 100)
        if not EXE.exists():
            print(f"ERR {EXE} 不存在；先跑 python tools/mgba_probe/build.py")
        else:
            hw_rows = hw_compare(sites, args.presses, args.only, args.max_hits,
                                 args.walk_budget, args.method)
            print("| site | 原版命中数 | 转换版命中数 | 命中数相同 | "
                  "窗口内逐条 CPSR 全同？ | 原版离开窗口时的标志 | 转换版离开窗口时的标志 |")
            print("|---|---|---|---|---|---|---|")
            for r in hw_rows:
                ok = ("**是**" if not r["window_flags_diffs"] and r["hit_count_equal"]
                      else "**否**")
                print(f"| `{r['site']}` | {r['base_hits']} | {r['conv_hits']} | "
                      f"{'是' if r['hit_count_equal'] else '否'} | {ok} | "
                      f"{', '.join(r['base_flags_at_exit']) or '—'} | "
                      f"{', '.join(r['conv_flags_at_exit']) or '—'} |")
            for r in hw_rows:
                if r["notes"]:
                    print(f"  · {r['site']}：{'；'.join(r['notes'])}")
                for d in r["window_flags_diffs"]:
                    print(f"  · {r['site']} 第 {d['hit']} 次窗口内标志位不同："
                          f"原版 {d['base']} vs 转换版 {d['conv']}")

    out = {
        "base_rom": str(BASE_ROM.relative_to(REPO)),
        "conv_rom": str(CONV_ROM.relative_to(REPO)),
        "static": sites,
        "hw": hw_rows,
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    print(f"\n已写出 {args.json.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
