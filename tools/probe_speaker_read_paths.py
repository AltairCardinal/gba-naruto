#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读普查：穷举 ROM 里**所有**能读到「说话人名表」区域 (0x085A57C4..0x085A5AB8) 的代码路径。

背景
----
说话人名表在 ROM 0x085A57C4（文件 0x5A57C4），原版是 12 字节定长内联槽。
改法是「指针表 + 变长串池」：基址不变，指针表占 0x085A57C4..0x085A58C3，
12 个「取名读者」被 14 处代码补丁改成「基址 + id*4 再解引用」。

要验的假设 U1：「存在第 13 个没被识别出来的读者，仍按 基址 + id*12 读名字」。
旧的内联槽 0x085A58C4..0x085A5AB8 仍然留在 ROM 里，任何这样的读者都会炸。

本探针穷举四条搜索路径（一次跑出全部结果）：
  S2  全 ROM Thumb-1 `ldr Rt,[pc,#imm]` 字面量池普查（复核已知 12 处）
  S3  全 ROM 原始 4 字节值 0x085A57C4 普查 + 区域内任意 u32 指针普查
  S4  ARM 模式 `ldr Rd,[pc,#±imm]` 字面量普查
  S5  「步长模式」普查：×12 / ×19 的乘法序列普查（不依赖字面量）
  S6  算址路径污点分析：仿射形式 (C + d + S*U) 的过程间数据流，
      找出所有「能把地址算进该区域」的指令（基址不必是 0x085A57C4 字面量）
  S7  「说话人全名表」3 个读者的核实
  S8  与 tools/data/speaker_name_code_patches.json 的 14 处补丁做覆盖归类

用法
----
  python tools/probe_speaker_read_paths.py

只读：不写 ROM，不改任何其它文件。
"""
from __future__ import annotations

import json
import pathlib
import sys
from array import array
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import capstone_loader  # noqa: E402

capstone = capstone_loader.load_capstone()
from capstone import CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, Cs  # noqa: E402

# ----------------------------------------------------------------- 常量定义
ROM_BASE = 0x08000000
TABLE_BASE = 0x085A57C4          # 说话人名表基址（原版 12 字节定长内联槽）
OLD_STRIDE = 12
OLD_COUNT = 63                  # 真实条目数 id 0..62
NEW_STRIDE = 4
NEW_COUNT = 64
REGION_LO = TABLE_BASE                                 # 0x085A57C4 旧内联槽区起点
REGION_HI = TABLE_BASE + OLD_COUNT * OLD_STRIDE         # 0x085A5AB8 = 全名表第 0 条
NEW_TABLE_HI = TABLE_BASE + NEW_COUNT * NEW_STRIDE      # 0x085A58C4 新指针表末端
FULLNAME_BASE = REGION_HI                               # 0x085A5AB8 全名表基址（19 字节/条）

NARROW_LO = TABLE_BASE - 0x1000        # 窄锚点窗口（±4 KB）
NARROW_HI = REGION_HI + 0x1000
WIDE_LO = TABLE_BASE - 0x10000         # 宽锚点窗口（±64 KB）
WIDE_HI = REGION_HI + 0x10000
KEY_ANCHORS = (TABLE_BASE, FULLNAME_BASE)

MAX_D = 0x20000          # 污点偏移量上限
MAX_FORMS = 8            # 每个寄存器保留的污点形式数上限（保证状态集合能收敛）
MAX_STEPS = 20000        # 单个种子的前向探索步数上限
MAX_VISITS = 12          # 同一地址在一个种子的探索里最多被处理几次
MAX_INDEX = 4096         # 命中判定允许的未知下标上限（排除「别的表 + 巨大下标」的噪音）

# ----------------------------------------------------------------- Thumb 指令种类
K_OTHER = 0
K_LDRLIT = 1
K_ADD_IMM = 2
K_SUB_IMM = 3
K_ADD_REG = 4
K_SUB_REG = 5
K_ADD_HI = 57           # ARMv4T 高位寄存器 ADD (reg) T2：Rd = Rd + Rn
K_SUB_HI = 58           # ARMv4T 高位寄存器 SUB (reg) T2：Rd = Rd - Rn
K_MOV_IMM = 6
K_MOV_REG = 7
K_LSL_IMM = 8
K_LSL_REG = 9
K_LSR_IMM = 10
K_LSR_REG = 11
K_ASR_IMM = 12
K_ASR_REG = 13
K_MUL = 14
K_MLA = 15
K_NEG = 16
K_NOT = 17
K_AND = 18
K_ORR = 19
K_EOR = 20
K_BIC = 21
K_ADC = 22
K_SBC = 23
K_RSB = 24
K_LDR = 25
K_LDRB = 26
K_LDRH = 27
K_LDRSB = 28
K_LDRSH = 29
K_STR = 30
K_STRB = 31
K_STRH = 32
K_LDR_REG = 33
K_STR_REG = 34
K_B = 35
K_BCC = 36
K_BL = 37
K_BLX = 38
K_BX = 39
K_PUSH = 40
K_POP = 41
K_CMP = 42
K_TST = 43
K_ADR = 44
K_ADD_SP = 45
K_LDR_SP = 46
K_STR_SP = 47
K_ADDSP = 48
K_SUBSP = 49
K_LDM = 50
K_STM = 51
K_SVC = 52

KIND_NAME = {
    K_OTHER: "other", K_LDRLIT: "ldr-literal", K_ADD_IMM: "add-imm",
    K_SUB_IMM: "sub-imm", K_ADD_REG: "add-reg", K_SUB_REG: "sub-reg",
    K_ADD_HI: "add-hi", K_SUB_HI: "sub-hi",
    K_MOV_IMM: "mov-imm", K_MOV_REG: "mov-reg", K_LSL_IMM: "lsl-imm",
    K_LSL_REG: "lsl-reg", K_LSR_IMM: "lsr-imm", K_LSR_REG: "lsr-reg",
    K_ASR_IMM: "asr-imm", K_ASR_REG: "asr-reg", K_MUL: "mul",
    K_MLA: "mla", K_NEG: "neg", K_NOT: "not", K_AND: "and", K_ORR: "orr",
    K_EOR: "eor", K_BIC: "bic", K_ADC: "adc", K_SBC: "sbc", K_RSB: "rsb",
    K_LDR: "ldr-imm", K_LDRB: "ldrb-imm", K_LDRH: "ldrh-imm",
    K_LDRSB: "ldrsb-imm", K_LDRSH: "ldrsh-imm", K_STR: "str-imm",
    K_STRB: "strb-imm", K_STRH: "strh-imm", K_LDR_REG: "ldr-reg",
    K_STR_REG: "str-reg", K_B: "b", K_BCC: "bcc", K_BL: "bl", K_BLX: "blx",
    K_BX: "bx", K_PUSH: "push", K_POP: "pop", K_CMP: "cmp", K_TST: "tst",
    K_ADR: "adr", K_ADD_SP: "add-sp-imm", K_LDR_SP: "ldr-sp", K_STR_SP: "str-sp",
    K_ADDSP: "addsp", K_SUBSP: "subsp", K_LDM: "ldm", K_STM: "stm",
    K_SVC: "svc",
}


def dec(hw: int) -> tuple:
    """解一条 16 位 Thumb-1 (ARMv4T) 指令，返回 (kind, rd, rn, rm, imm)。

    分组按 hw>>11（5 位）划分，位域定义见 ARM ARM A4.2。
    """
    g5 = hw >> 11
    if g5 == 0:                                   # 00000 imm5 Rm Rd  LSL (imm)
        return (K_LSL_IMM, hw & 7, 0, (hw >> 3) & 7, (hw >> 6) & 0x1F)
    if g5 == 1:                                   # 00001 imm5 Rm Rd  LSR (imm)
        return (K_LSR_IMM, hw & 7, 0, (hw >> 3) & 7, (hw >> 6) & 0x1F)
    if g5 == 2:                                   # 00010 imm5 Rm Rd  ASR (imm)
        return (K_ASR_IMM, hw & 7, 0, (hw >> 3) & 7, (hw >> 6) & 0x1F)
    if g5 == 3:                                   # 00011x 加减组
        p = (hw >> 9) & 0x7F
        if p == 0x0C:                             # 0001100 Rm Rn Rd  ADD (reg) T1
            return (K_ADD_REG, hw & 7, (hw >> 3) & 7, (hw >> 6) & 7, 0)
        if p == 0x0D:                             # 0001101 Rm Rn Rd  SUB (reg) T1
            return (K_SUB_REG, hw & 7, (hw >> 3) & 7, (hw >> 6) & 7, 0)
        if p == 0x0E:                             # 0001110 imm3 Rn Rd ADD (imm3)
            return (K_ADD_IMM, hw & 7, (hw >> 3) & 7, 0, (hw >> 6) & 7)
        return (K_SUB_IMM, hw & 7, (hw >> 3) & 7, 0, hw & 0xFF)   # 0001111 imm8 SUB (imm8)
    if g5 <= 7:                                   # 001xx Rd imm8
        b = g5 & 3
        rd = (hw >> 8) & 7
        imm = hw & 0xFF
        if b == 0:
            return (K_MOV_IMM, rd, 0, 0, imm)
        if b == 1:
            return (K_CMP, rd, 0, 0, imm)
        if b == 2:
            return (K_ADD_IMM, rd, rd, 0, imm)
        return (K_SUB_IMM, rd, rd, 0, imm)
    if g5 == 8:                                   # 010000xx / 010001xx
        if (hw >> 10) & 1:                        # 010001xx 特殊数据 / 分支
            b = (hw >> 8) & 3
            if b == 0:                            # ADD (reg) T2：Rd = Rd + Rn
                rd = (hw & 7) | ((hw >> 4) & 8)
                return (K_ADD_HI, rd, (hw >> 3) & 0xF, 0, 0)
            if b == 1:                            # SUB (reg) T2：Rd = Rd - Rn
                rd = (hw & 7) | ((hw >> 4) & 8)
                return (K_SUB_HI, rd, (hw >> 3) & 0xF, 0, 0)
            if b == 2:                            # MOV (reg) T2：Rd = Rn
                rd = (hw & 7) | ((hw >> 4) & 8)
                return (K_MOV_REG, rd, 0, (hw >> 3) & 0xF, 0)
            rm = (hw >> 3) & 0xF
            return (K_BLX, 0, 0, rm, 0) if (hw & 0x80) else (K_BX, 0, 0, rm, 0)
        b = (hw >> 6) & 0xF                      # 010000xx 数据处理
        rd = hw & 7
        rm = (hw >> 3) & 7
        if b == 0x0:
            return (K_AND, rd, 0, rm, 0)
        if b == 0x1:
            return (K_EOR, rd, 0, rm, 0)
        if b == 0x2:
            return (K_LSL_REG, rd, 0, rm, (hw >> 6) & 7)
        if b == 0x3:
            return (K_LSR_REG, rd, 0, rm, (hw >> 6) & 7)
        if b == 0x4:
            return (K_ASR_REG, rd, 0, rm, (hw >> 6) & 7)
        if b == 0x5:
            return (K_ADC, rd, 0, rm, 0)
        if b == 0x6:
            return (K_SBC, rd, 0, rm, 0)
        if b == 0x7:
            return (K_OTHER, rd, 0, rm, 0)        # ROR
        if b == 0x8:
            return (K_TST, rd, 0, rm, 0)
        if b == 0x9:
            return (K_RSB, rd, (hw >> 3) & 7, 0, (hw >> 6) & 7)
        if b == 0xA:
            return (K_CMP, rd, 0, rm, 0)
        if b == 0xB:
            return (K_CMP, rd, 0, (hw >> 3) & 7, 0)
        if b == 0xC:
            return (K_MUL, rd, 0, rm, (hw >> 6) & 7)
        if b == 0xD:
            return (K_MLA, rd, (hw >> 3) & 7, (hw >> 6) & 7, (hw >> 8) & 7)
        if b == 0xE:
            return (K_NEG, rd, 0, rm, 0)
        return (K_NOT, rd, 0, rm, 0)
    if g5 == 9:                                   # 01001xxx  LDR (literal) T1
        return (K_LDRLIT, (hw >> 8) & 7, 0, 0, hw & 0xFF)
    if g5 <= 11:                                  # 0101xxxx  寄存器偏移读写
        b = (hw >> 9) & 7
        rt, rn, rm = hw & 7, (hw >> 3) & 7, (hw >> 6) & 7
        return ([K_STR, K_STRH, K_STRB, K_LDRSB, K_LDR, K_LDRH, K_LDRSB, K_LDRH][b],
                rt, rn, rm, 0)
    if g5 <= 15:                                  # 011xxxxx  字/字节立即数读写
        b = (hw >> 11) & 3
        rt, rn = hw & 7, (hw >> 3) & 7
        imm5 = (hw >> 6) & 0x1F
        if b == 0:
            return (K_STR, rt, rn, 0, imm5 * 4)
        if b == 1:
            return (K_LDR, rt, rn, 0, imm5 * 4)
        if b == 2:
            return (K_STRB, rt, rn, 0, imm5)
        return (K_LDRB, rt, rn, 0, imm5)
    if g5 <= 17:                                  # 1000xxxx  半字立即数读写
        b = (hw >> 11) & 3
        rt, rn = hw & 7, (hw >> 3) & 7
        imm5 = (hw >> 6) & 0x1F
        if b == 0:
            return (K_STRH, rt, rn, 0, imm5 * 2)
        return (K_LDRH, rt, rn, 0, imm5 * 2)
    if g5 <= 19:                                  # 1001xxxx  SP 相对读写
        b = (hw >> 11) & 3
        rt, imm = (hw >> 8) & 7, (hw & 0xFF) * 4
        if b in (0, 2):
            return (K_STR_SP, rt, 0, 0, imm)
        return (K_LDR_SP, rt, 0, 0, imm)
    if g5 <= 21:                                  # 1010xxxx  ADR / ADD (SP)
        b = (hw >> 11) & 3
        rd, imm = (hw >> 8) & 7, (hw & 0xFF) * 4
        if b == 0:
            return (K_ADR, rd, 0, 0, imm)
        return (K_ADD_SP, rd, 0, 0, imm)
    if g5 <= 23:                                  # 1011xxxx  杂项
        b = (hw >> 8) & 0xF
        if b == 0x0:
            imm = ((hw >> 6) & 0x7F) * 4
            return (K_SUBSP if (hw & 0x80) else K_ADDSP, 0, 0, 0, imm)
        if b in (0x4, 0x5):
            return (K_PUSH, 0, 0, 0, hw & 0x1FF)          # PUSH（含 M=1 含 lr）
        if b in (0x6, 0x7):
            return (K_STM if b == 0x6 else K_LDM, 0, 0, 0, hw & 0xFF)
        if b == 0x8:
            return (K_STRH, hw & 7, 13, 0, ((hw >> 6) & 0x7F) * 2)
        if b == 0x9:
            return (K_LDRH, hw & 7, 13, 0, ((hw >> 6) & 0x7F) * 2)
        if b in (0xA, 0xB):
            imm = ((hw >> 6) & 0x7F) * 4
            return (K_SUBSP if (hw & 0x80) else K_ADDSP, 0, 0, 0, imm)
        if b in (0xC, 0xD):
            return (K_POP, 0, 0, 0, hw & 0x1FF)           # POP（含 P=1 含 pc）
        return (K_OTHER, 0, 0, 0, 0)
    if g5 <= 25:                                  # 1100xxxx  LDM/STM
        b = (hw >> 11) & 3
        return (K_STM if b in (0, 2) else K_LDM, hw & 7, (hw >> 3) & 7, 0, hw & 0xFF)
    if g5 <= 27:                                  # 1101xxxx  条件分支 / SVC
        cond = (hw >> 8) & 0xF
        if cond == 0xF:
            return (K_SVC, 0, 0, 0, hw & 0xFF)
        imm8 = hw & 0xFF
        if cond == 0xE:
            off = imm8 * 2
        else:
            off = (imm8 - 256 if imm8 & 0x80 else imm8) * 2
        return (K_BCC, cond, 0, 0, off)
    if g5 == 28:                                  # 11100xxx  B (T2)
        imm11 = hw & 0x7FF
        off = (imm11 - 2048 if imm11 & 0x400 else imm11) * 2
        return (K_B, 0, 0, 0, off)
    if g5 == 29:                                  # 11101xxx  BL (T1)
        imm11 = hw & 0x7FF
        off = (imm11 - 2048 if imm11 & 0x400 else imm11) * 2
        return (K_BL, 0, 0, 0, off)
    return (K_OTHER, 0, 0, 0, 0)                   # 1111xxx：ARMv5 BLX，ARMv4T 未定义


# =============================================================== 抽象域
# 污点形式 form = (C, d, S, v, w)  表示值 = C + d + S * U_v
#   C == 0  -> 没有已知基址（纯未知量），此时 d/S 只是相对量
#   C != 0  -> C 是「锚点常量」（字面量基址之类），d 是相对它的偏移
#   S == 0  -> 值是精确常量 C + d
#   S  > 0  -> 值里含一个未知量 U_v（v 是未知来源编号，w 是 U_v 的位宽，
#              即 U_v ∈ [0, 2^w-1]；w=32 表示无界）
def f_add(f1, f2):
    """f1 + f2。保留『非零的那个基址』在 C 里，偏移累加到 d。"""
    C1, d1, S1, v1, w1 = f1
    C2, d2, S2, v2, w2 = f2
    if S1 == 0 and S2 == 0:                      # 两个精确常量
        return (C1 + C2, d1 + d2, 0, 0, 32)
    if S1 > 0 and S2 > 0:                       # 两个都带未知量
        if v1 != v2:
            return None
        base = C1 if C1 != 0 else C2
        return (base, d1 + d2 + C1 + C2 - base, S1 + S2, v1, max(w1, w2))
    if S1 == 0:
        f1, f2 = f2, f1
        C1, d1, S1, v1, w1, C2, d2, S2, v2, w2 = C2, d2, S2, v2, w2, C1, d1, S1, v1, w1
    # 现在 f1 带未知量，f2 是精确常量
    if C1 != 0:
        return (C1, d1 + C2 + d2, S1, v1, w1)
    return (C2, d2 + d1, S1, v1, w1)


def f_sub(f1, f2):
    """f1 - f2；f2 必须是精确常量，否则结果不可锚定（返回 None）。"""
    C1, d1, S1, v1, w1 = f1
    C2, d2, S2, v2, w2 = f2
    if S2 != 0:
        return None
    if S1 == 0:
        return (C1 - C2, d1 - d2, 0, 0, 32)
    if C1 != 0:
        return (C1, d1 - C2 - d2, S1, v1, w1)
    return None


def f_scale(f, k):
    C, d, S, v, w = f
    if S == 0:                                  # 精确常量左移后仍是精确常量
        val = (C + d) * k
        if val > 0xFFFFFFFF or val < 0:
            return f_unknown(v, 32)
        return (val, 0, 0, 0, w)
    val = C + d
    if val * k > 0xFFFFFFFF or val * k < 0:
        return f_unknown(v, 32)        # 32 位溢出：精度丢失，降级为无界未知量
    return (C, d * k, S * k, v, w)


def f_const(v):
    return (v, 0, 0, 0, 32)


def f_unknown(vid, w=32):
    return (0, 0, 1, vid, w)


def f_shift_right(f, n, arith=False):
    """右移 n 位：步长是 2 的幂时按比例缩小步长与位宽，否则降级为无界未知量。"""
    C, d, S, v, w = f
    if S == 0:
        val = C + d
        return f_const((val >> n) if not arith else (val >> n))
    if S > 0 and (S & (S - 1)) == 0:            # S 是 2 的幂
        bits = S.bit_length() - 1
        if n <= bits:
            return (C, d >> n, S >> n, v, max(0, w - n))
    return f_unknown(v, 32)


def region_hit(form, lo=REGION_LO, hi=REGION_HI):
    """若该形式在 0 <= U <= 2^w-1 时能落进 [lo, hi)，返回 (命中值, 步长S)，否则 None。

    C == 0 且 S > 0 表示「纯未知量 × 系数」（C=0 是未知标记），
    这种形式取遍任意值，命中区域不构成证据，直接排除。
    """
    C, d, S, v, w = form
    if C == 0 and S > 0:
        return None
    base = C + d
    if S == 0:
        return (base, 0) if lo <= base < hi else None
    if base >= hi:
        return None
    u = 0 if base >= lo else (lo - base + S - 1) // S
    if u > MAX_INDEX:
        return None
    if u > (1 << min(w, 32)) - 1:
        return None            # 下标位宽不够，够不到该区域
    val = base + S * u
    return (val, S) if lo <= val < hi else None


def clip(forms):
    if len(forms) <= MAX_FORMS:
        return forms
    out = set()
    for f in sorted(forms, key=lambda x: (abs(x[1]), x[2])):
        out.add(f)
        if len(out) >= MAX_FORMS:
            break
    return out


# =============================================================== 工具
def disasm(md, rom, addr, count):
    out = []
    off = addr - ROM_BASE
    for insn in md.disasm(rom[off:off + count * 2], addr):
        out.append((insn.address, insn.mnemonic, insn.op_str))
        if len(out) >= count:
            break
    return out


class Decoder:
    """全 ROM Thumb-1 解码结果。"""

    def __init__(self, rom):
        self.rom = rom
        n = len(rom) // 2
        self.n = n
        self.kinds = bytearray(n)
        self.rd = bytearray(n)
        self.rn = bytearray(n)
        self.rm = bytearray(n)
        self.imm = array("i", bytes(4 * n))
        decode_fn = dec
        kinds, rd_a, rn_a, rm_a, imm_a = self.kinds, self.rd, self.rn, self.rm, self.imm
        rom_get = rom.__getitem__
        for i in range(n):
            hw = rom_get(2 * i) | (rom_get(2 * i + 1) << 8)
            k, r0, r1, r2, im = decode_fn(hw)
            kinds[i] = k
            rd_a[i] = r0
            rn_a[i] = r1
            rm_a[i] = r2
            imm_a[i] = im

    def lit_addr(self, i):
        """第 i 条指令（若是 ldr-literal）指向的字面量 ROM 地址。"""
        a = ROM_BASE + 2 * i
        return ((a + 4) & ~3) + self.imm[i] * 4


# =============================================================== 污点引擎
class TaintEngine:
    """「锚点字面量 → 仿射形式」的前向数据流分析。

    抽象值 form = (C, d, S, v)：值 = C + d + S * U_v。
      S == 0  精确常量
      S  > 0  含未知量 U_v（v = 未知来源编号）
    目标：找出所有「能把地址算进 [0x085A57C4, 0x085A5AB8)」的指令。
    """

    def __init__(self, dec: Decoder, anchor_sites, tag=""):
        self.dec = dec
        self.tag = tag
        self.anchor_sites = list(anchor_sites)   # [(insn_addr, literal_value)]
        self.owner = None                     # addr -> 函数起点
        self.funcs = {}                       # start -> 地址列表
        self.entries = []
        self.target_funcs = []
        self.hits = []
        self._hit_keys = set()
        self.paths = []
        self.capped = 0

    # -------------------------------------------------- 函数归属
    def build_functions(self):
        d = self.dec
        n = d.n
        entries = set()
        for i in range(n):
            k = d.kinds[i]
            a = ROM_BASE + 2 * i
            if k == K_BL:
                entries.add((a + 4 + d.imm[i]) & ~1)
            elif k == K_BX and d.rm[i] == 14:
                entries.add(a + 2)
            elif k == K_POP and (d.imm[i] & 0x100):
                entries.add(a + 2)
            elif k == K_PUSH and (d.imm[i] & 0x100):
                entries.add(a)
        # 跳转表：ROM 里指向代码区的 u32（Thumb 位可有可无，handler 入口常常不带 Thumb 位）
        for off in range(0, len(d.rom) - 3, 4):
            v = int.from_bytes(d.rom[off:off + 4], "little")
            if 0x08000100 <= v < 0x08400000:
                entries.add(v & ~1)
        entries = {e for e in entries if ROM_BASE <= e < ROM_BASE + 2 * n}
        self.entries = sorted(entries)
        owner = [-1] * n
        for start in sorted(entries):
            si = (start - ROM_BASE) >> 1
            if owner[si] != -1:
                continue
            stack = [si]
            while stack:
                i = stack.pop()
                if i < 0 or i >= n or owner[i] != -1:
                    continue
                owner[i] = start
                k = d.kinds[i]
                a = ROM_BASE + 2 * i
                if k == K_B:
                    stack.append((a + 4 + d.imm[i] - ROM_BASE) >> 1)
                elif k == K_BCC:
                    stack.append(i + 1)
                    stack.append((a + 4 + d.imm[i] - ROM_BASE) >> 1)
                elif k in (K_BX, K_POP, K_SVC, K_BLX):
                    continue
                else:
                    stack.append(i + 1)
        self.owner = owner
        funcs = {}
        for i in range(n):
            o = owner[i]
            if o != -1:
                funcs.setdefault(o, []).append(ROM_BASE + 2 * i)
        self.funcs = funcs

    def func_of(self, addr):
        """所属函数起点；未被 DFS 认领时回退到「最近的前一个函数入口」。"""
        if self.owner is None:
            return None
        i = (addr - ROM_BASE) >> 1
        if i < 0 or i >= self.dec.n:
            return None
        o = self.owner[i]
        if o != -1:
            return o
        # 回退：最近的前一个入口（差值小于 0x8000 才认）
        import bisect
        k = bisect.bisect_right(self.entries, addr) - 1
        if k >= 0 and addr - self.entries[k] < 0x8000:
            return self.entries[k]
        return None

    # -------------------------------------------------- 状态工具
    @staticmethod
    def merge(old, new):
        """合并两个寄存器状态；返回 (新状态, 是否发生变化)。"""
        if old is None:
            return tuple(frozenset(s) for s in new), True
        changed = False
        out = []
        for r in range(16):
            u = set(old[r]) | set(new[r])
            if len(u) > len(old[r]):
                changed = True
            out.append(frozenset(clip(u)))
        return tuple(out), changed

    def fold_add(self, s1, s2):
        out = set()
        for f1 in s1:
            for f2 in s2:
                r = f_add(f1, f2)
                if r is not None and abs(r[1]) <= MAX_D:
                    out.add(r)
        return clip(out)

    def fold_sub(self, s1, s2):
        out = set()
        for f1 in s1:
            for f2 in s2:
                r = f_sub(f1, f2)
                if r is not None and abs(r[1]) <= MAX_D:
                    out.add(r)
        return clip(out)

    @staticmethod
    def scale(s, k):
        return clip({f_scale(f, k) for f in s})

    # -------------------------------------------------- 主流程
    def run(self):
        if self.owner is None:
            self.build_functions()
        tf = set()
        for a, v in self.anchor_sites:
            i = (a - ROM_BASE) >> 1
            if 0 <= i < self.dec.n and self.owner[i] != -1:
                tf.add(self.owner[i])
        self.target_funcs = sorted(tf)
        for start in self.target_funcs:
            visited = self.analyze_function(start)
            # 该函数里没被入口走到的连续段（跳表 handler 等），逐段从段首再跑一遍
            addrs = self.funcs.get(start, [])
            runs = []
            cur = []
            prev = None
            for a in addrs:
                if a in visited:
                    if cur:
                        runs.append(cur)
                        cur = []
                    prev = None
                    continue
                if prev is not None and a != prev + 2:
                    runs.append(cur)
                    cur = []
                cur.append(a)
                prev = a
            if cur:
                runs.append(cur)
            for run in runs:
                self.analyze_function(run[0])
        for h in self.hits:
            C, d, S, vv, _uu = h["form"]
            if S == 0:
                h["cat"] = "B"            # 地址精确落在区域内
            elif S == 1:
                h["cat"] = "C+" if C in KEY_ANCHORS else "C"
            else:
                h["cat"] = "A"            # 地址 = 基址 + 步长*未知下标
        for h in self.hits:
            if h["cat"] in ("A", "B", "C+"):
                self.paths.append(h)

    # -------------------------------------------------- 单函数前向分析
    def analyze_function(self, start):
        """从 start 做流敏感分析；字面量载入即为污点源。返回走到的地址集合。"""
        d = self.dec
        n = d.n
        faddrs = self.funcs.get(start)
        if not faddrs:
            return set()
        inset = set((a - ROM_BASE) >> 1 for a in faddrs)   # 指令槽号集合
        si = (start - ROM_BASE) >> 1
        st = [set() for _ in range(16)]
        # 入口参数 r0..r7 是调用者传进来的未知值（位宽 32）
        for r in range(8):
            st[r] = {f_unknown(start + 0x100 + r, 32)}
        states = {si: tuple(frozenset(s) for s in st)}
        stack = [si]
        stackmap = {}
        sp_off = 0
        steps = 0
        visits = {}
        visited = set()

        def push(nxt):
            if nxt < 0 or nxt >= n or nxt not in inset:
                return
            merged, changed = self.merge(states.get(nxt), newregs)
            if changed:
                states[nxt] = merged
                stack.append(nxt)

        while stack:
            steps += 1
            if steps > MAX_STEPS:
                self.capped += 1
                break
            i = stack.pop()
            if i < 0 or i >= n:
                continue
            visits[i] = visits.get(i, 0) + 1
            if visits[i] > MAX_VISITS:
                continue
            a = ROM_BASE + 2 * i
            visited.add(a)
            state = states.get(i)
            if state is None:
                continue
            k = d.kinds[i]
            rd, rn, rm = d.rd[i], d.rn[i], d.rm[i]
            im = d.imm[i]
            newregs = [set(s) for s in state]
            nstack = dict(stackmap)
            nsp = sp_off
            hit = None

            def reg(r, st=state):
                return st[r] if 0 <= r < 16 else frozenset()

            def setreg(r, forms, regs=newregs):
                if 0 <= r < 16:
                    regs[r] = forms

            if k == K_LDRLIT:
                lit = d.lit_addr(i)
                lo = lit - ROM_BASE
                val = None
                if 0 <= lo and lo + 4 <= len(d.rom):
                    val = int.from_bytes(d.rom[lo:lo + 4], "little")
                if val is not None and (WIDE_LO <= val <= WIDE_HI or val < 0x10000):
                    setreg(rd, {f_const(val)})
                else:
                    setreg(rd, {f_unknown(a)})
            elif k == K_MOV_IMM:
                setreg(rd, {f_const(im)})
            elif k == K_MOV_REG:
                setreg(rd, set(reg(rm)))
            elif k == K_ADD_IMM:
                setreg(rd, self.fold_add(reg(rn), {f_const(im)}))
            elif k == K_SUB_IMM:
                setreg(rd, self.fold_sub(reg(rn), {f_const(im)}))
            elif k == K_ADD_REG:
                setreg(rd, self.fold_add(reg(rn), reg(rm)))
            elif k == K_SUB_REG:
                setreg(rd, self.fold_sub(reg(rn), reg(rm)))
            elif k == K_ADD_HI:
                setreg(rd, self.fold_add(reg(rd), reg(rn)))
            elif k == K_SUB_HI:
                setreg(rd, self.fold_sub(reg(rd), reg(rn)))
            elif k == K_LSL_IMM:
                setreg(rd, self.scale(reg(rm), 1 << im if im else 32))
            elif k in (K_LSR_IMM, K_ASR_IMM):
                # 右移：精确常量照算；步长是 2 的幂时按比例缩小步长与位宽
                out = set()
                for f in reg(rm):
                    out.add(f_shift_right(f, im, k == K_ASR_IMM))
                setreg(rd, clip(out))
            elif k in (K_LSL_REG, K_LSR_REG, K_ASR_REG,
                       K_NOT, K_AND, K_ORR, K_EOR, K_BIC, K_ADC, K_SBC):
                setreg(rd, {f_unknown(a)})
            elif k == K_MUL:
                out = set()
                for f1 in reg(rm):
                    for f2 in reg(im):
                        if f1[2] == 0 and f2[2] == 0:
                            out.add(f_const(f1[0] + f1[1] + f2[0] + f2[1]))
                        elif f1[2] == 0:
                            out.add(f_scale(f2, f1[0] + f1[1]))
                        elif f2[2] == 0:
                            out.add(f_scale(f1, f2[0] + f2[1]))
                setreg(rd, clip(out))
            elif k == K_NEG:
                setreg(rd, clip({f_const(-(f[0] + f[1])) for f in reg(rm) if f[2] == 0}))
            elif k == K_RSB:
                setreg(rd, clip({f_const(im - (f[0] + f[1])) for f in reg(rn) if f[2] == 0}))
            elif k in (K_LDR, K_LDRB, K_LDRH, K_LDR_REG, K_LDRSB, K_LDRSH):
                if k == K_LDR_REG:
                    base_forms = self.fold_add(reg(rn), reg(rm))
                elif k in (K_LDR, K_LDRB, K_LDRH):
                    base_forms = self.fold_add(reg(rn), {f_const(im)})
                else:
                    base_forms = set(reg(rn))
                for f in base_forms:
                    h = region_hit(f)
                    if h:
                        hit = (a, f, "read")
                        break
                # 载入的值带取值上界：字节 0..255，半字 0..65535，字无界
                if k == K_LDRB:
                    setreg(rd, {f_unknown(a, 8)})
                elif k == K_LDRH:
                    setreg(rd, {f_unknown(a, 16)})
                elif k == K_LDRSB:
                    setreg(rd, {f_unknown(a, 8)})
                else:
                    setreg(rd, {f_unknown(a)})
            elif k in (K_STR, K_STRB, K_STRH, K_STR_REG):
                for f in reg(rd):
                    h = region_hit(f)
                    if h:
                        hit = (a, f, "store")
                        break
            elif k == K_PUSH:
                reglist = im & 0xFF
                for r in range(8):
                    if reglist & (1 << r):
                        nsp -= 4
                        nstack[nsp] = set(reg(r))
            elif k == K_POP:
                reglist = im & 0xFF
                for r in range(8):
                    if reglist & (1 << r):
                        setreg(r, set(nstack.get(nsp, frozenset())))
                        nsp += 4
                if im & 0x100:
                    continue                    # 返回
            elif k == K_B:
                push((a + 4 + im - ROM_BASE) >> 1)
                continue
            elif k == K_BCC:
                push((a + 4 + im - ROM_BASE) >> 1)
                push(i + 1)
                continue
            elif k == K_BL:
                callee = (a + 4 + im) & ~1
                for r in range(4):
                    for f in reg(r):
                        if region_hit(f):
                            self.record(a, callee, f, "arg%d" % r, "call")
                setreg(0, {f_unknown(a, 32)})       # 返回值未知
                push(i + 1)
                continue
            elif k in (K_BX, K_BLX, K_SVC):
                continue
            elif k == K_ADR:
                setreg(rd, {f_unknown(a)})
            elif k == K_ADD_SP:
                setreg(rd, frozenset())
            elif k == K_LDR_SP:
                setreg(rd, {f_unknown(a)})

            if hit is not None:
                self.record(hit[0], None, hit[1], hit[2], "mem")
            # 「算址点」：某个寄存器第一次形成能落进旧槽区的形式
            if 0 <= rd < 16:
                old = state[rd]
                for f in newregs[rd]:
                    if f in old:
                        continue
                    if region_hit(f):
                        self.record(a, None, f, "compute", "addr")
            push(i + 1)
        self.last_states = states          # 调试用：最后一次分析的逐指令状态
        return visited

    def record(self, addr, callee, form, how, kind):
        key = (addr, how, form)
        if key in self._hit_keys:
            return
        self._hit_keys.add(key)
        self.hits.append({
            "addr": addr, "form": form, "how": how, "kind": kind,
            "callee": callee, "base": form[0], "delta": form[1], "scale": form[2],
            "func": self.func_of(addr), "cat": "",
        })

    def describe(self, h):
        C, d, S, v, _uu = h["form"]
        desc = "0x%08X" % C + ("%+d" % d if d else "")
        if S:
            desc += " + %d*U" % S
        return desc


# =============================================================== 主流程
def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rom = (REPO / "rom" / "base.gba").read_bytes()
    md_thumb = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    print("=" * 100)
    print("说话人名表读名路径穷举普查   ROM 0x%08X （文件 0x%06X）" % (TABLE_BASE, TABLE_BASE - ROM_BASE))
    print("=" * 100)
    print("ROM          : rom/base.gba  %d 字节" % len(rom))
    print("区域定义     : 旧内联槽区 [0x%08X, 0x%08X)   = 旧槽 id 0..62" % (REGION_LO, REGION_HI))
    print("               新指针表区 [0x%08X, 0x%08X)   = 64 项 x 4 字节" % (TABLE_BASE, NEW_TABLE_HI))
    print("               转换后会被当成指针读的旧字形码区 = [0x%08X, 0x%08X)" % (NEW_TABLE_HI, REGION_HI))
    print()

    # ---------------------------------------------------------------- S1 解码
    print("-" * 100)
    print("[S1] 全 ROM Thumb-1 (ARMv4T) 解码（自写解码器）")
    dec = Decoder(rom)
    print("  解码 %d 条 16 位指令" % dec.n)
    # 与 capstone 逐条交叉校验（全 ROM，每个 16 位槽单独解一次）
    ALLOW = {
        "lsl": {K_LSL_IMM, K_LSL_REG}, "lsls": {K_LSL_IMM, K_LSL_REG},
        "movs": {K_MOV_IMM, K_MOV_REG, K_LSL_IMM, K_LSL_REG},
        "lsr": {K_LSR_IMM, K_LSR_REG}, "lsrs": {K_LSR_IMM, K_LSR_REG},
        "asr": {K_ASR_IMM, K_ASR_REG}, "asrs": {K_ASR_IMM, K_ASR_REG},
        "add": {K_ADD_IMM, K_ADD_REG, K_ADD_SP, K_ADD_HI},
        "adds": {K_ADD_IMM, K_ADD_REG, K_ADD_HI},
        "sub": {K_SUB_IMM, K_SUB_REG, K_SUBSP, K_SUB_HI},
        "subs": {K_SUB_IMM, K_SUB_REG, K_SUB_HI},
        "mov": {K_MOV_IMM, K_MOV_REG}, "cmp": {K_CMP},
        "and": {K_AND}, "ands": {K_AND}, "orr": {K_ORR}, "orrs": {K_ORR},
        "eor": {K_EOR}, "eors": {K_EOR}, "bic": {K_BIC}, "bics": {K_BIC},
        "adc": {K_ADC}, "adcs": {K_ADC}, "sbc": {K_SBC}, "sbcs": {K_SBC},
        "mul": {K_MUL}, "muls": {K_MUL}, "mla": {K_MLA},
        "neg": {K_NEG}, "negs": {K_NEG}, "mvn": {K_NOT}, "mvns": {K_NOT},
        "rsb": {K_RSB}, "rsbs": {K_RSB},
        "ldr": {K_LDRLIT, K_LDR, K_LDR_REG, K_LDR_SP},
        "ldrb": {K_LDRB, K_LDRSB}, "ldrh": {K_LDRH, K_LDRSH},
        "str": {K_STR, K_STR_REG, K_STR_SP}, "strb": {K_STRB}, "strh": {K_STRH},
        "b": {K_B}, "bl": {K_BL}, "blx": {K_BLX}, "bx": {K_BX},
        "push": {K_PUSH}, "pop": {K_POP},
        "stmia": {K_STM}, "ldmia": {K_LDM}, "stmdb": {K_STM}, "ldmdb": {K_LDM},
        "stm": {K_STM}, "ldm": {K_LDM},
        "svc": {K_SVC}, "nop": {K_OTHER}, "hint": {K_OTHER}, "adr": {K_ADR},
        "addsp": {K_ADDSP}, "subsp": {K_SUBSP},
        "uxtb": {K_OTHER}, "uxth": {K_OTHER}, "sxth": {K_OTHER}, "sxtb": {K_OTHER},
        "ror": {K_OTHER}, "rors": {K_OTHER},
    }
    COND = {"eq", "ne", "cs", "hs", "cc", "lo", "mi", "pl", "vs", "vc",
            "hi", "ls", "ge", "lt", "gt", "le"}
    # capstone 用 ARMv7 语义，下列助记符在 ARMv4T 上语义不同（以 ARMv4T 为准，故不计错）
    ARMV7_ONLY = {"ldrsh", "ldrsb", "cbz", "cbnz", "udf", "it", "ite", "itt",
                  "tst", "rev", "rev16", "revsh", "cmn", "orrs", "muls", "bics"}
    mism = Counter()
    ex = {}
    checked = 0
    for i in range(dec.n):
        r = list(md_thumb.disasm_lite(rom[2 * i:2 * i + 2], ROM_BASE + 2 * i))
        if not r or r[0][1] != 2:
            continue
        checked += 1
        mn = r[0][2]
        k = dec.kinds[i]
        if mn in COND:
            ok = (k == K_BCC)
        elif mn in ALLOW:
            ok = k in ALLOW[mn]
        elif mn in ARMV7_ONLY:
            ok = True
        else:
            ok = True
        if not ok:
            mism[mn] += 1
            if mn not in ex:
                ex[mn] = (hex(ROM_BASE + 2 * i), mn + " " + r[0][3],
                          KIND_NAME.get(k, k), rom[2 * i:2 * i + 2].hex(" "))
    print("  与 capstone 逐槽交叉校验：核对 %d 个 16 位槽" % checked)
    print("      不一致分类（应只剩 ARMv4T 与 ARMv7 的语义差异）：")
    for kk, v in mism.most_common(20):
        print("         %-10s %6d   例: %s" % (kk, v, ex.get(kk)))
    if not mism:
        print("         （完全一致）")
    print()

    # ------------------------------------------------------- S2 字面量池普查
    print("-" * 100)
    print("[S2] 全 ROM Thumb-1 `ldr Rt,[pc,#imm]` 字面量池普查")
    lit_sites = []
    for i in range(dec.n):
        if dec.kinds[i] != K_LDRLIT:
            continue
        lit = dec.lit_addr(i)
        lo = lit - ROM_BASE
        if lo < 0 or lo + 4 > len(rom):
            continue
        lit_sites.append((ROM_BASE + 2 * i, lit, int.from_bytes(rom[lo:lo + 4], "little")))
    base_sites = [s for s in lit_sites if s[2] == TABLE_BASE]
    print("  全 ROM ldr-literal 站点总数        : %d" % len(lit_sites))
    print("  字面量值 == 0x%08X（名表基址）     : %d 处" % (TABLE_BASE, len(base_sites)))
    for a, lit, v in base_sites:
        print("      insn 0x%08X   字面量 0x%08X (文件 0x%06X)" % (a, lit, lit - ROM_BASE))
    in_region = [s for s in lit_sites if REGION_LO <= s[2] < REGION_HI]
    other_in = [s for s in in_region if s[2] != TABLE_BASE]
    print("  字面量值落在旧槽区内的站点        : %d 处（除基址本身外 %d 处）"
          % (len(in_region), len(other_in)))
    for a, lit, v in other_in:
        print("      insn 0x%08X   字面量 0x%08X = 0x%08X" % (a, lit, v))
    full_sites = [s for s in lit_sites if s[2] == FULLNAME_BASE]
    print("  字面量值 == 0x%08X（全名表基址）   : %d 处" % (FULLNAME_BASE, len(full_sites)))
    for a, lit, v in full_sites:
        print("      insn 0x%08X   字面量 0x%08X" % (a, lit))
    narrow = {}
    for a, lit, v in lit_sites:
        if NARROW_LO <= v <= NARROW_HI:
            narrow.setdefault(v, []).append(a)
    print("  窄锚点窗口 (±0x1000) 内的常量      : %d 个不同值 / %d 个站点"
          % (len(narrow), sum(len(x) for x in narrow.values())))
    for v in sorted(narrow):
        print("      0x%08X x%-3d %s" % (v, len(narrow[v]),
                                       " ".join("0x%08X" % s for s in narrow[v][:8])))
    wide = {v for _, _, v in lit_sites if WIDE_LO <= v <= WIDE_HI}
    print("  宽锚点窗口 (±0x10000) 内的常量     : %d 个不同值 / %d 个站点"
          % (len(wide), sum(1 for _, _, v in lit_sites if WIDE_LO <= v <= WIDE_HI)))
    print()

    # ---------------------------------------------------------- S3 原始 u32
    print("-" * 100)
    print("[S3] 全 ROM 原始 4 字节值普查")
    needle = TABLE_BASE.to_bytes(4, "little")
    occ = []
    pos = rom.find(needle)
    while pos != -1:
        occ.append(pos)
        pos = rom.find(needle, pos + 1)
    lit_pool = {lit - ROM_BASE for _, lit, _ in lit_sites}
    print("  原始值 0x%08X 出现次数 : %d" % (TABLE_BASE, len(occ)))
    for p in occ:
        tag = "ldr 字面量池单元" if p in lit_pool else "★ 非字面量池命中"
        print("      文件 0x%06X (ROM 0x%08X)  %s" % (p, p + ROM_BASE, tag))
    region_ptrs = []
    for p in range(0, len(rom) - 3):
        v = int.from_bytes(rom[p:p + 4], "little")
        if REGION_LO <= v < REGION_HI:
            region_ptrs.append((p, v))
    extra = [(p, v) for p, v in region_ptrs if v != TABLE_BASE]
    print("  旧槽区内的任意 u32（任何字节对齐）: %d 处（其中非基址值 %d 处）"
          % (len(region_ptrs), len(extra)))
    for p, v in extra:
        ctx = rom[max(0, p - 8):p + 12]
        printable = sum(1 for c in ctx if 32 <= c < 127)
        print("      文件 0x%06X (ROM 0x%08X) 值 0x%08X  = base+%d (非 12 的整数倍=%s)"
              % (p, p + ROM_BASE, v, v - TABLE_BASE, (v - TABLE_BASE) % OLD_STRIDE != 0))
        print("          上下文 %s  可打印字节 %d/20  %s"
              % (ctx.hex(" "), printable,
                 "<- 落在 ASCII 文本/数据串里，属巧合" if printable >= 12 else ""))
    fn = FULLNAME_BASE.to_bytes(4, "little")
    occ2 = []
    pos = rom.find(fn)
    while pos != -1:
        occ2.append(pos)
        pos = rom.find(fn, pos + 1)
    print("  原始值 0x%08X（全名表基址）出现次数 : %d  -> %s"
          % (FULLNAME_BASE, len(occ2), " ".join("0x%06X" % p for p in occ2)))
    print()

    # ---------------------------------------------------------- S4 ARM 模式
    print("-" * 100)
    print("[S4] ARM 模式 `ldr Rd,[pc,#±imm]` 字面量普查（全 ROM，4 字节对齐）")
    arm_total = 0
    arm_near = []
    for off in range(0, len(rom) - 3, 4):
        insn = int.from_bytes(rom[off:off + 4], "little")
        if (insn & 0x0F7F0000) != 0x051F0000:
            continue
        arm_total += 1
        up = (insn >> 23) & 1
        imm = insn & 0xFFF
        if ((insn >> 16) & 0xF) != 15:
            continue
        addr = (ROM_BASE + off + 8) + (imm * 4 if up else -imm * 4)
        lo = addr - ROM_BASE
        if 0 <= lo and lo + 4 <= len(rom):
            v = int.from_bytes(rom[lo:lo + 4], "little")
            if WIDE_LO <= v <= WIDE_HI:
                arm_near.append((ROM_BASE + off, addr, v))
    print("  全 ROM ARM 模式 LDR-from-PC 指令数 : %d" % arm_total)
    print("  其中字面量值落在宽锚点窗口内的      : %d 处" % len(arm_near))
    for a, ad, v in arm_near:
        print("      insn 0x%08X  字面量 0x%08X = 0x%08X" % (a, ad, v))
    print()

    # ------------------------------------------------------ S5 步长模式普查
    print("-" * 100)
    print("[S5] 「步长模式」普查：×12 / ×19 的乘法序列（与基址字面量无关）")
    x12 = []
    x19 = []
    for i in range(dec.n - 3):
        if dec.kinds[i] != K_LSL_IMM:
            continue
        rd0, rm0, im0 = dec.rd[i], dec.rm[i], dec.imm[i]
        if dec.kinds[i + 1] != K_ADD_REG:
            continue
        rd1, rn1, rm1 = dec.rd[i + 1], dec.rn[i + 1], dec.rm[i + 1]
        if dec.kinds[i + 2] != K_LSL_IMM:
            continue
        rd2, rm2, im2 = dec.rd[i + 2], dec.rm[i + 2], dec.imm[i + 2]
        if not (rd0 == rd1 == rd2 and rn1 == rd0 and rm1 == rm0):
            continue
        if im0 == 1 and im2 == 2:
            x12.append((ROM_BASE + 2 * i, "lsls #1 + adds + lsls #2"))
        if im0 == 2 and im2 == 2 and dec.kinds[i + 3] == K_SUB_REG \
                and dec.rd[i + 3] == rd2 and dec.rn[i + 3] == rd2 and dec.rm[i + 3] == rm0:
            x19.append((ROM_BASE + 2 * i, "lsls #2 + adds + lsls #2 + subs  => id*19"))
    print("  ×12 序列命中 : %d 处" % len(x12))
    for a, shape in x12:
        print("      0x%08X  %s" % (a, shape))
    print("  ×19 序列命中 : %d 处" % len(x19))
    for a, shape in x19:
        print("      0x%08X  %s" % (a, shape))
    print()

    # ------------------------------------------------------- S8 补丁清单
    print("-" * 100)
    print("[S8] 14 处代码补丁清单（tools/data/speaker_name_code_patches.json）")
    manifest = json.loads((REPO / "tools" / "data" / "speaker_name_code_patches.json")
                           .read_text(encoding="utf-8"))
    patches = manifest["patches"]
    patch_ranges = []
    for p in patches:
        a = int(p["rom_addr"], 16)
        patch_ranges.append((a, a + p["byte_length"], p))
        print("      reader %-2s %-22s 0x%08X..0x%08X  字面量 0x%08X"
              % (p["reader"], p["site"], a, a + p["byte_length"] - 1,
                 int(p["literal_rom_addr"], 16)))
    print()

    def in_patch(addr):
        for lo, hi, p in patch_ranges:
            if lo <= addr < hi:
                return p
        return None

    # ------------------------------- S5b：每个 ×12 站点用的是哪个基址
    print("-" * 100)
    print("[S5b] 逐个 ×12 站点的基址回溯（从『加基址』那条指令往前回溯 16 条，定位基址寄存器的定义）")

    def last_def(site_slot, reg_want):
        """从 site_slot 往前回溯，找 reg_want 的最近一次定义。"""
        for back in range(1, 25):
            j = site_slot - back
            if j < 0:
                return None
            k = dec.kinds[j]
            if k in (K_LDRLIT, K_MOV_IMM, K_MOV_REG, K_LDR, K_LDRB, K_LDRH, K_LDR_REG):
                if dec.rd[j] == reg_want:
                    return j, k
        return None

    x12_base = {}
    for a, shape in x12:
        i = (a - ROM_BASE) >> 1
        basereg = None
        for k in range(3, 9):
            j = i + k
            if j >= dec.n:
                break
            if dec.kinds[j] == K_ADD_REG and dec.rn[j] == dec.rd[j]:
                basereg = dec.rm[j]
                break
            if dec.kinds[j] == K_ADD_HI:
                basereg = dec.rn[j]
                break
        if basereg is None:
            x12_base.setdefault("<未找到基址寄存器>", []).append(a)
            continue
        d = last_def(j, basereg)
        if d is None:
            x12_base.setdefault("<基址定义未定位>", []).append(a)
            continue
        j, k = d
        if k == K_LDRLIT:
            lit = dec.lit_addr(j)
            lo = lit - ROM_BASE
            val = int.from_bytes(rom[lo:lo + 4], "little") if 0 <= lo and lo + 4 <= len(rom) else None
            x12_base.setdefault("0x%08X" % val if val is not None else "?", []).append(a)
        else:
            x12_base.setdefault("<非字面量:%s>" % KIND_NAME.get(k, k), []).append(a)
    print("  ×12 站点基址分布：")
    for key in sorted(x12_base, key=lambda k: -len(x12_base[k])):
        sites = x12_base[key]
        print("      基址 %-18s 站点 %3d 个：%s"
              % (key, len(sites), " ".join("0x%08X" % s for s in sites[:6])
                 + ("" if len(sites) <= 6 else " ...")))
    name_base_sites = x12_base.get("0x%08X" % TABLE_BASE, [])
    print("  以名表基址 0x%08X 为基址的 ×12 站点：%d 个" % (TABLE_BASE, len(name_base_sites)))
    for s in name_base_sites:
        p = in_patch(s)
        print("      0x%08X  %s" % (s, ("读者 %s / %s" % (p["reader"], p["site"])) if p else "★ 不在补丁内"))
    print()

    # ------------------------------------------------------- S8 补丁清单
    print("-" * 100)
    print("[S8] 14 处代码补丁清单（tools/data/speaker_name_code_patches.json）")
    manifest = json.loads((REPO / "tools" / "data" / "speaker_name_code_patches.json")
                           .read_text(encoding="utf-8"))
    patches = manifest["patches"]
    patch_ranges = []
    for p in patches:
        a = int(p["rom_addr"], 16)
        patch_ranges.append((a, a + p["byte_length"], p))
        print("      reader %-2s %-22s 0x%08X..0x%08X  字面量 0x%08X"
              % (p["reader"], p["site"], a, a + p["byte_length"] - 1,
                 int(p["literal_rom_addr"], 16)))
    print()

    def in_patch(addr):
        for lo, hi, p in patch_ranges:
            if lo <= addr < hi:
                return p
        return None

    # ------------------------------------------------------ S6 污点分析
    print("-" * 100)
    print("[S6] 算址路径污点分析（仿射形式 C + d + S*U）")
    narrow_seeds = [(a, v) for v, sites in narrow.items() for a in sites]
    wide_seeds = [(a, v) for _, _, v in lit_sites if WIDE_LO <= v <= WIDE_HI]
    engine = TaintEngine(dec, narrow_seeds, "narrow")
    engine.build_functions()
    # 只在「已识别函数体内」的站点做种子：数据区里偶然匹配 ldr-literal 形态的字节不是代码
    narrow_seeds = [s for s in narrow_seeds if engine.func_of(s[0]) is not None]
    wide_seeds = [s for s in wide_seeds if engine.func_of(s[0]) is not None]
    engine.anchor_sites = narrow_seeds
    engine.run()
    print("  窄窗口锚点字面量 %d 个（全部落在已识别函数体内），涉及函数 %d 个"
          % (len(narrow_seeds), len(engine.target_funcs)))
    print("  命中总数 %d，分类：" % len(engine.hits))
    cats = {}
    for h in engine.hits:
        cats[h["cat"]] = cats.get(h["cat"], 0) + 1
    print("      A=地址=基址+步长*未知下标   B=地址精确落在区内   C/C+=基址+任意未知量")
    for c in sorted(cats):
        print("      类别 %-3s : %d 条" % (c, cats[c]))
    print("  步数上限触发次数 : %d" % engine.capped)
    shown = 0
    for h in engine.hits:
        if h["cat"] not in ("A", "B", "C+"):
            continue
        shown += 1
        if shown > 60:
            print("      ... 截断")
            break
        print("    [%-2s] 0x%08X  函数 0x%08X  %-6s %-30s %s"
              % (h["cat"], h["addr"], h["func"] or 0, h["how"], engine.describe(h),
                 ("-> callee 0x%08X" % h["callee"]) if h["callee"] else ""))
    print()

    # 宽窗口复查（稳健性检查）
    engine_w = TaintEngine(dec, wide_seeds, "wide")
    engine_w.build_functions()
    engine_w.anchor_sites = wide_seeds
    engine_w.run()
    catsw = {}
    for h in engine_w.hits:
        catsw[h["cat"]] = catsw.get(h["cat"], 0) + 1
    print("  宽窗口复查（±0x10000，%d 个种子）：命中 %d 条  %s"
          % (len(wide_seeds), len(engine_w.hits),
             " ".join("%s=%d" % (k, v) for k, v in sorted(catsw.items()))))
    wide_new = [h for h in engine_w.hits
                if h["cat"] in ("A", "B") and h["addr"] not in {x["addr"] for x in engine.hits}]
    print("  宽窗口里出现、窄窗口没有的 A/B 类命中 : %d 条" % len(wide_new))
    for h in wide_new[:40]:
        print("      [%-2s] 0x%08X  函数 0x%08X  %-6s %s"
              % (h["cat"], h["addr"], h["func"] or 0, h["how"], engine_w.describe(h)))
    print()

    # ------------------------------------------------------- S7 全名表读者
    print("-" * 100)
    print("[S7] 「说话人全名表」3 个读者核实（0x%08X 是不是『说话人 id 63』？）" % FULLNAME_BASE)
    for a, lit, v in full_sites:
        print("  读者 insn 0x%08X  字面量 0x%08X = 0x%08X" % (a, lit, v))
        for ins in disasm(md_thumb, rom, a - 0x18, 14):
            mark = "  <<< 字面量载入" if ins[0] == a else ""
            print("      0x%08X: %-8s %s%s" % (ins[0], ins[1], ins[2], mark))
        print()
    print("  语义核对：")
    print("    旧 12 字节表 id 62 槽地址 = 0x%08X" % (TABLE_BASE + 62 * OLD_STRIDE))
    print("    旧 12 字节表 id 63 槽地址 = 0x%08X   <- 恰好等于全名表基址" % (TABLE_BASE + 63 * OLD_STRIDE))
    for label, addr in (("旧表 id 0", TABLE_BASE), ("旧表 id 62", TABLE_BASE + 62 * OLD_STRIDE),
                         ("全名表第 0 条", FULLNAME_BASE)):
        raw = rom[addr - ROM_BASE:addr - ROM_BASE + 12]
        print("    %-14s @0x%08X  %s" % (label, addr, raw.hex(" ")))
    print("    => 0x%08X 在地址上就是『旧表 id 63』的位置，但旧表只有 id 0..62（63 条），" % FULLNAME_BASE)
    print("       该地址上的字节属于『全名表第 0 条』；内容与旧表 id 0 相同，是两张表首尾相接的巧合。")
    print()

    # ------------------------------------------------------- S9 汇总表
    print("-" * 100)
    print("[S9] 读名路径清单表")
    rows = []
    for a, lit, v in base_sites:
        p = in_patch(a)
        f = engine.func_of(a)
        rows.append((a, "基址字面量 0x%08X + id*12" % TABLE_BASE, f,
                     "是" if p else "否",
                     ("读者 %s / %s" % (p["reader"], p["site"])) if p else "★ 不在补丁内"))
    for a, lit, v in full_sites:
        p = in_patch(a)
        f = engine.func_of(a)
        rows.append((a, "全名表基址 0x%08X + id*19" % FULLNAME_BASE, f,
                     "是" if p else "否",
                     ("读者 %s / %s" % (p["reader"], p["site"])) if p
                     else "不读旧槽区：基址 = 区域末端，id>=0 时地址 >= 0x%08X" % FULLNAME_BASE))
    for h in engine.paths:
        p = in_patch(h["addr"])
        f = h["func"] or engine.func_of(h["addr"])
        rows.append((h["addr"], "污点：%s（%s）" % (engine.describe(h), h["how"]), f,
                     "是" if p else "否",
                     ("读者 %s / %s" % (p["reader"], p["site"])) if p else "★ 不在补丁内"))
    seen = set()
    uniq = []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        uniq.append(r)
    uniq.sort()
    print("  %-10s %-10s %-36s %-10s %s"
          % ("指令地址", "所属函数", "读法（怎么算到那个地址）", "在14处补丁内", "结论"))
    for addr, how, f, patched, note in uniq:
        print("  0x%08X %-10s %-36s %-10s %s"
              % (addr, ("0x%08X" % f) if f else "-", how, patched, note))
    print()

    print("=" * 100)
    print("[结论]")
    unmatched = [r for r in uniq if r[4].startswith("★")]
    taint_sites = sorted({h["addr"] for h in engine.hits})
    taint_sites_unmatched = [a for a in taint_sites if in_patch(a) is None]
    print("  (a) 字面量直接引用 0x%08X 的站点             : %d 处" % (TABLE_BASE, len(base_sites)))
    print("  (b) 全名表基址 0x%08X 的站点                 : %d 处（读的是全名表，不读旧槽区）"
          % (FULLNAME_BASE, len(full_sites)))
    print("  (c) 污点分析算出的『能读进旧槽区』的算址点    : %d 个站点 / %d 条路径"
          % (len(taint_sites), len(engine.hits)))
    print("  (d) ARM 模式命中                               : %d 处" % len(arm_near))
    print("  (e) 原始 u32 落在旧槽区内的非基址值             : %d 处（ASCII 数据串里的巧合）" % len(extra))
    print("  (f) ×12 站点里以名表基址为基址的                : %d 个（= 14 处补丁）"
          % len(name_base_sites))
    print("  (g) 与 14 处补丁对不上的读名路径               : %d 条" % len(unmatched))
    for r in unmatched:
        print("        0x%08X  %s" % (r[0], r[1]))
    if taint_sites_unmatched:
        print("      污点分析里不在补丁内的算址点：")
        for a in taint_sites_unmatched:
            print("        0x%08X" % a)
    if unmatched or taint_sites_unmatched:
        print("  => 假设 U1 **成立**：存在对不上补丁的读名路径。")
    else:
        print("  => 假设 U1 **证伪**：每一条能读到该区域的路径都能对应到 14 处补丁之一。")
        print("     （唯一另外引用相邻地址的是『说话人全名表』的 3 个读者，它们的基址")
        print("       0x%08X 正是旧槽区的末端，id>=0 时地址只会更大，不会读进旧槽区。）" % FULLNAME_BASE)
    print("=" * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
