#!/usr/bin/env python3
"""Battle map-object ("mechanism") semantics for the Konoha Senki ROM.

Everything in this tool is measured on the ROM passed on the command line
(default ``rom/base.gba``).  The third-party "13 mechanisms" taxonomy is only
*reported* next to the native facts, so the two layers are never confused.

Native structure (all three tables are found by disassembly, not assumed)
-------------------------------------------------------------------------
1. ``0x085815E4`` - **pickup dispatch table**, 7 ROM pointers.
   Indexed by ``(u16 at runtime-slot+4) - 1``; the slot word is a copy of the
   config record's type byte, so the index is the *record type* 1..7.
2. ``0x0806E868`` - **per-type setup dispatch**, 7 ROM pointers.
   Indexed by ``(config record byte 0) - 1`` = record type 1..7.  Each branch
   decides whether the object is created at all (types 3/4 are conditional)
   and which *runtime type* (3..6) it gets.
3. ``0x0808136C`` - **per-target effect table**, 13 ROM pointers.
   Indexed by ``target - 1`` = 1..13.  Only config types 5/6/7 use it, and
   only for targets != 9 (target 9 is intercepted earlier by the counter
   branch).  This is the native home of the third-party "13 mechanisms".

Data
----
* ``0x085461C4 + stage*0x1AAC + sub*0x8E4`` - battle configuration matrix;
  its trailing 16 x 4-byte map-object records (``+0x8A4``) are
  ``type, target, x, y``.
* ``0x08599634`` (ninjutsu names, 93), ``0x085A7E8C`` (upgrade material
  names, 16), ``0x08599280`` (character names, 62) - cross-statistics of
  which ids the maps actually use, and which table slots stay unused.

Runtime layout (verified by disassembly, see notes/mechanisms-20261020.md)
-------------------------------------------------------------------------
* runtime object array ``WRAM 0x02026604``: 32 slots x 16 bytes
  (+0 runtime type, +1 x, +2 y, +4 config type, +6 target, +0x0C extra);
* map tile table ``WRAM 0x02021E2C`` (u16 per tile) carries the slot index
  in bits 6..10; map width in tiles is ``WRAM 0x0201BE2A``;
* builder ``0x08081024`` creates a slot, ``0x08081544`` picks it up.

Usage
-----
    python tools/mechanism_map.py rom/base.gba --stats
    python tools/mechanism_map.py rom/base.gba --json build/mechanism_map.json
    python tools/mechanism_map.py rom/base.gba --stage 1 --sub 0
    python tools/mechanism_map.py rom/base.gba --disasm 0x0808173C --count 60
    python tools/mechanism_map.py rom/base.gba --callers 0x08081024
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.lib.io import write_text  # noqa: E402
from tools import text_codec  # noqa: E402

ROM_BASE = 0x08000000

# --- native tables --------------------------------------------------------
DISPATCH_TABLE = 0x815E4          # pickup dispatch pointers (index = type-1)
DISPATCH_SCAN = 16
SETUP_TABLE = 0x0806E868          # per-type setup pointers (index = type-1)
EFFECT_TABLE = 0x0808136C         # per-target effect pointers (index = target-1)
EFFECT_COUNT = 13
BUILDER = 0x08081024              # creates a runtime object slot
PICKUP_DISPATCHER = 0x08081544    # finds the slot, jumps through DISPATCH_TABLE
EFFECT_DISPATCHER = 0x080812DC    # 13-way effect dispatcher

OBJECT_ARRAY_WRAM = 0x02026604    # 32 slots x 16 bytes
TILE_TABLE_WRAM = 0x02021E2C      # u16 per tile, slot index in bits 6..10
MAP_WIDTH_WRAM = 0x0201BE2A       # map width in tiles
UNIT_BASE_WRAM = 0x020240C0       # battle unit slots, stride 468
UNIT_STRIDE = 468
BATTLE_CTRL_WRAM = 0x02026804     # +1 stage, +2 sub, +3 result
BATTLE_STATE_WRAM = 0x02022E30    # party / training table, stride 0xBC

CONFIG_BASE = 0x5461C4
GROUP_STRIDE = 0x1AAC
SUB_STRIDE = 0x8E4
OBJECT_OFFSET = 0x8A4
OBJECT_COUNT = 16
# The battle matrix has 48 configuration groups, but only 46 of them are
# battles (stage 0 is not a battle; group 47 holds unrelated data - its
# +0x8A4 block contains bytes that are not object records at all).
BATTLE_STAGE_FIRST = 1
BATTLE_STAGE_LAST = 46
SUB_COUNT = 3

# The per-type setup code lives in one contiguous block; the CFG walk below
# must not leave it.
SETUP_REGION = (0x0806E884, 0x0806E958)
# The 13 mechanism effects and their shared tail.
EFFECT_REGION = (0x080813A0, 0x080814D4)
EFFECT_CALL = 0x0808A638
# The shared "no effect" endpoint every mechanism effect falls through to
# (close the message window, play the stage BGM, wait for a key press).
# The effect table uses it for targets whose effect body is empty.
EFFECT_NOOP = 0x080814CC
# The pickup handler for record types 5/6/7 intercepts target 9 *before* it
# ever reaches EFFECT_DISPATCHER, so effect-table slot 9 is dead code.
EFFECT_INTERCEPT_TARGET = 9
EFFECT_INTERCEPT_ADDR = 0x08081986   # cmp r0, #9
EFFECT_CALL_SITE = 0x08081AE0        # bl EFFECT_DISPATCHER inside the handler

# Story/logic VM opcodes (see notes/story-script-vm.md).
STORY_OPS = {
    0x00: "结束", 0x01: "文本", 0x02: "头像/对话框", 0x03: "旁白",
    0x07: "跳转", 0x12: "场景对象操作", 0x13: "调用子脚本",
    0x1E: "进入战斗", 0x20: "对白", 0x33: "分支结束",
    0x34: "回合/相位条件", 0x35: "复合条件", 0x36: "指定人物在场",
    0x37: "置/清标志位", 0x38: "测标志位", 0x39: "配置(sub)匹配",
}


def decode_script_header(rom: bytes, addr: int) -> dict:
    """Decode the first story-VM instruction of the script at `addr`."""
    off = addr - ROM_BASE
    if not (0 <= off < len(rom) - 8):
        return {}
    op = rom[off]
    info = {
        "addr": addr,
        "op": op,
        "op_name": STORY_OPS.get(op, f"未知 0x{op:02X}"),
        "bytes": rom[off:off + 8].hex(" "),
    }
    if op == 0x36:      # presence: [a, side, character_id, d, pointer]
        info["character_id"] = rom[off + 3]
        info["pointer"] = struct.unpack_from("<I", rom, off + 4)[0]
    return info


NAME_TABLES = {
    "ninjutsu": (0x599634, 93),   # 忍具名
    "material": (0x5A7E8C, 16),   # 强化素材名
    "character": (0x599280, 62),  # 人物名 / 认识卡
}

# Labels for addresses that show up in the literal pools.
KNOWN = {
    0x085461C4: "战斗配置矩阵基址",
    0x02026804: "战斗控制块",
    0x02026805: "battle_stage",
    0x02026806: "battle_sub",
    0x02026807: "battle_result",
    0x020240C0: "战斗单位槽基址(stride 468)",
    0x02022E30: "战斗状态/队伍表(stride 0xBC)",
    0x02026604: "运行时物件数组(32x16)",
    0x02021E2C: "地图格表(u16/格, bit6..10=槽位)",
    0x08599634: "忍具名表(93)",
    0x085A7E8C: "强化素材名表(16)",
    0x08599280: "人物名表(62)",
    0x085A7060: "人物相关文本表",
    0x08001631: "剧情脚本入口",
    0x0800164F: "剧情脚本入口",
    0x08001671: "剧情脚本入口",
    0x080016A1: "剧情脚本入口",
    0x08001725: "剧情脚本入口",
}

# The 8 record types the game itself distinguishes (type byte of a record).
OBJECT_TYPES = {
    0: "空位（不放置）",
    1: "忍具",
    2: "强化素材",
    3: "专属修行卷轴",
    4: "认识卡（人物图鉴）",
    5: "机关宝箱",
    6: "特殊机关（卷轴外观）",
    7: "剧情物件",
}

# Types 3 / 4 only materialise when their precondition holds, so the item
# number the game reports is not the record index.
CONDITIONAL_TYPES = {3, 4}

# Third-party naming overlay (NOT the native dispatch table).
THIRD_PARTY_MECHANISM_NAMES = {
    1: "开门机关", 2: "空箱 / 开门分支", 3: "停止傀儡的机关",
    4: "开门机关（另一组）", 5: "空箱 / 开门分支（另一组）",
    6: "停止傀儡的机关（另一组）", 7: "密书", 8: "空箱 / 密书分支",
    9: "甘薯（收集计数）", 10: "发现奖励（强化剂剧情）", 11: "空事件",
    12: "宝箱教学", 13: "认识卡教学",
}

# Native pickup handler behaviour (index = record type - 1).
HANDLER_ROLES = {
    0: "忍具：读名表 0x599634 显示名称，弹窗并计入持有上限",
    1: "强化素材：读名表 0x5A7E8C 显示名称，弹窗并计入持有上限",
    2: "专属修行卷轴：在队伍表 0x02022E30(0xBC 步长) 找同号人物并解锁修行",
    3: "认识卡：读人物名表 0x599280 显示人物名",
    4: "机关/剧情物件：target==9 走计数分支，其余走 13 效果表",
    5: "机关/剧情物件：同 4（兜底）",
    6: "机关/剧情物件：同 4（兜底）",
}

# What each *effect-table* target actually selects, derived from the native
# code (see notes/evidence/mechanism-sprite-background-20261020.md).
#
#   * the effect dispatcher 0x080812DC has exactly one caller (0x08081AE0),
#     inside the shared pickup handler 0x08081984;
#   * that handler compares the target against 9 at 0x08081986 and branches
#     to the counter branch 0x0808198C, so target 9 never reaches the table.
#
# => effect-table slot 9 (index 8) is unreachable, and slot 11 (index 10)
#    points at the shared "no effect" endpoint.
EFFECT_TARGET_FACTS = {
    9: {
        "reachable": False,
        "note": "被拾取处理程序在 0x08081986 拦截（cmp r0,#9 → 计数分支 "
                "0x0808198C），永远进不了 13 项效果表；表内第 9 项指向通用"
                "空操作端点 0x080814CC，是死代码。原生语义＝收集计数机关。",
    },
    11: {
        "reachable": True,
        "note": "表内第 11 项直接指向通用空操作端点 0x080814CC（不跑任何"
                "原版关卡脚本）；原版 46 个战场里 target 11 一次都没被使用。",
    },
}

# Record type -> runtime object type -> which level script it drives.
# The *script* is selected by the target byte alone (all three types share
# the pickup handler 0x08081984 and the effect table 0x0808136C); the record
# type only selects the runtime object type, i.e. the on-map sprite and the
# pickup sound (0x080814FC maps runtime type 3/4/5/6 to sfx 0x6B/0x6A/-/0x75).
TYPE_SCRIPT_ROUTE = {
    5: {"setup": 0x0806E8E4, "runtime_types": [3], "sound": 0x6B,
        "note": "机关宝箱：target 1..8/12/13 → 开门/空箱/密书/教学类关卡脚本"},
    6: {"setup": 0x0806E8F8, "runtime_types": [4], "sound": 0x6A,
        "note": "特殊机关（卷轴外观）：与 type 5 共用同一张效果表；"
                "原版 46 个战场里 0 次出现"},
    7: {"setup": 0x0806E90C, "runtime_types": [5, 6], "sound": None,
        "note": "剧情物件：target 9 → 计数机关（运行时类型 6），"
                "target 10 → 对话脚本 0x08006B24（运行时类型 5）"},
}


# --------------------------------------------------------------------------
# capstone plumbing
# --------------------------------------------------------------------------
def _candidate_capstone_dirs() -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    env = os.environ.get("LIBCAPSTONE_PATH")
    if env:
        out.append(pathlib.Path(env))
    deps = REPO / "build" / "python-deps"
    if deps.exists():
        for dll in deps.rglob("capstone.dll"):
            out.append(dll.parent)
        for dll in deps.rglob("libcapstone.dll"):
            out.append(dll.parent)
    return out


def load_capstone():
    """Import capstone, auto-pointing LIBCAPSTONE_PATH at a local DLL."""
    vendor = REPO / "tools" / "_vendor"
    if str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    try:
        import capstone  # noqa: F401
        return capstone
    except Exception:
        pass
    for cand in _candidate_capstone_dirs():
        if cand and cand.exists():
            os.environ["LIBCAPSTONE_PATH"] = str(cand)
            try:
                import capstone  # noqa: F401
                return capstone
            except Exception:
                continue
    raise SystemExit(
        "capstone is unavailable: set LIBCAPSTONE_PATH to the folder that "
        "holds capstone.dll (see notes/windows-migration-20261020.md 2.2)"
    )


def disasm(rom: bytes, addr: int, count: int = 40) -> list:
    capstone = load_capstone()
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    blob = rom[addr - ROM_BASE: addr - ROM_BASE + count * 4 + 16]
    return list(md.disasm(blob, addr))


def disassembler():
    """A capstone instance with detail enabled (needed for regs_access)."""
    capstone = load_capstone()
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True
    return md


COND_BRANCHES = {
    "beq", "bne", "bhi", "bls", "bgt", "ble", "bcc", "bcs",
    "bmi", "bpl", "bvs", "bvc",
}


def branch_target(op: str) -> int | None:
    try:
        return int(op.strip().lstrip("#"), 16)
    except ValueError:
        return None


def literal_addr(insn) -> int | None:
    if insn.mnemonic != "ldr" or "[pc" not in insn.op_str:
        return None
    try:
        imm = int(insn.op_str.split("#")[1].split("]")[0].strip(), 0)
    except (IndexError, ValueError):
        return None
    return ((insn.address + 4) & ~3) + imm


def literal_value(rom: bytes, insn) -> int | None:
    la = literal_addr(insn)
    if la is None:
        return None
    off = la - ROM_BASE
    if not (0 <= off <= len(rom) - 4):
        return None
    return struct.unpack_from("<I", rom, off)[0]


def classify_literal(value: int) -> str:
    if value == 0:
        return "NULL"
    if ROM_BASE <= value < ROM_BASE + 0x02000000:
        return "ROM"
    if 0x02000000 <= value < 0x03000000:
        return "WRAM"
    if 0x03000000 <= value < 0x04000000:
        return "IWRAM"
    if value < 0x10000:
        return "const"
    return "?"


def rom_byte(rom: bytes, addr: int) -> int | None:
    off = addr - ROM_BASE
    if 0 <= off < len(rom):
        return rom[off]
    return None


def analyze_block(rom: bytes, addr: int, count: int) -> dict:
    """Disassemble a block and pull out the machine-checkable facts."""
    insns = disasm(rom, addr, count)
    calls, lits, mems, cmps = [], [], [], []
    for insn in insns:
        m, op = insn.mnemonic, insn.op_str
        if m == "bl":
            calls.append(int(op.strip().lstrip("#"), 16))
        elif m == "ldr":
            la = literal_addr(insn)
            if la is not None:
                val = literal_value(rom, insn)
                lits.append({
                    "at": insn.address, "lit_addr": la, "value": val,
                    "kind": classify_literal(val) if val is not None else "?",
                    "reg": op.split(",")[0].strip(),
                    "label": KNOWN.get(val, ""),
                })
        if m in ("ldrb", "ldrh", "ldr", "strb", "strh", "str") and "[" in op:
            mems.append({"at": insn.address, "op": f"{m} {op}"})
        if m == "cmp":
            cmps.append({"at": insn.address, "op": op})
    return {
        "address": addr,
        "calls": calls,
        "literals": lits,
        "memory": mems,
        "compares": cmps,
        "instructions": [
            {"addr": insn.address, "text": f"{insn.mnemonic} {insn.op_str}".strip()}
            for insn in insns
        ],
    }


# --------------------------------------------------------------------------
# data extraction
# --------------------------------------------------------------------------
def read_pointer_table(rom: bytes, base: int, count: int) -> list[int]:
    return [struct.unpack_from("<I", rom, base - ROM_BASE + 4 * i)[0]
            for i in range(count)]


def read_dispatch(rom: bytes) -> tuple[list[dict], int]:
    out = []
    for i in range(DISPATCH_SCAN):
        value = struct.unpack_from("<I", rom, DISPATCH_TABLE + i * 4)[0]
        out.append({
            "index": i,
            "addr": DISPATCH_TABLE + i * 4,
            "value": value,
            "is_rom_pointer": ROM_BASE <= value < ROM_BASE + 0x02000000,
        })
    native = 0
    for d in out:
        if not d["is_rom_pointer"]:
            break
        native += 1
    return out, native


def _decode_region(md, rom: bytes, lo: int, hi: int) -> dict:
    region: dict[int, object] = {}
    addr = lo
    while addr < hi:
        chunk = rom[addr - ROM_BASE: addr - ROM_BASE + 4]
        if len(chunk) < 2:
            break
        insn = next(md.disasm(chunk, addr), None)
        if insn is None:
            addr += 2
            continue
        region[addr] = insn
        addr += insn.size
    return region


def cfg_walk(md, rom: bytes, entry: int, lo: int, hi: int,
             stop_calls: set[int]) -> list[dict]:
    """Control-flow walk that tracks r0/r1 back to their origin.

    The setup branches and the mechanism-effect branches are interleaved in
    one code block, so a linear scan would bleed into the neighbours.  This
    walks the actual basic blocks instead and, for every call to one of
    `stop_calls`, reports what r0 and r1 were:

    ``const``  - a literal immediate moved into the register
    ``literal``- a 32-bit word loaded from the ROM literal pool
    ``deref``  - a byte loaded from (literal base + offset), i.e. the
                 address a runtime field is read from
    """
    region = _decode_region(md, rom, lo, hi)
    # state: reg -> (kind, value, extra)
    hits: list[dict] = []
    visited: set[tuple] = set()

    def copy_state(state):
        return {k: v for k, v in state.items()}

    stack: list[tuple[int, dict]] = [(entry, {})]
    while stack:
        addr, state = stack.pop()
        key = (addr, tuple(sorted((r, v) for r, v in state.items())))
        if key in visited:
            continue
        visited.add(key)
        insn = region.get(addr)
        if insn is None:
            continue
        m, op = insn.mnemonic, insn.op_str
        new_state = copy_state(state)
        try:
            _, written = insn.regs_access()
            written_names = {insn.reg_name(r) for r in written}
        except Exception:
            written_names = set()
        # the base register of a load may be the destination register itself,
        # so read it before the written registers are invalidated
        base_state = None
        if m in ("ldrb", "ldrh") and "[" in op:
            inner = op.split("[")[1].split("]")[0]
            base_reg = inner.split(",")[0].strip()
            base_state = state.get(base_reg)
        for reg in written_names:
            if reg in ("pc", "cpsr", "lr", "sp"):
                continue
            new_state.pop(reg, None)
        if m == "movs" and "," in op:
            dst, _, imm = op.partition(",")
            dst = dst.strip()
            imm = imm.strip()
            if dst.startswith("r") and imm.startswith("#"):
                try:
                    new_state[dst] = ("const", int(imm[1:], 0), None)
                except ValueError:
                    pass
        elif m == "ldr" and "[pc" in op:
            dst = op.split(",")[0].strip()
            la = literal_addr(insn)
            val = literal_value(rom, insn) if la is not None else None
            if val is not None:
                new_state[dst] = ("literal", val, la)
        elif m in ("ldrb", "ldrh") and "[" in op:
            dst = op.split(",")[0].strip()
            inner = op.split("[")[1].split("]")[0]
            try:
                off = int(inner.split(",")[1].strip().lstrip("#"), 0)
            except (IndexError, ValueError):
                off = 0
            if base_state and base_state[0] == "literal":
                new_state[dst] = ("deref", base_state[1], off)
        if m == "bl":
            tgt = branch_target(op)
            if tgt in stop_calls:
                hits.append({"at": addr, "state": dict(new_state)})
                continue
            stack.append((addr + insn.size, new_state))
            continue
        if m == "b":
            tgt = branch_target(op)
            if tgt is not None and lo <= tgt < hi:
                stack.append((tgt, new_state))
            continue
        if m in COND_BRANCHES:
            tgt = branch_target(op)
            if tgt is not None and lo <= tgt < hi:
                stack.append((tgt, new_state))
            stack.append((addr + insn.size, new_state))
            continue
        if m == "bx":
            continue
        stack.append((addr + insn.size, new_state))
    return hits


def cfg_runtime_types(md, rom: bytes, entry: int) -> list[dict]:
    """Runtime types the setup branch assigns (r0 before the builder call)."""
    hits = cfg_walk(md, rom, entry, SETUP_REGION[0], SETUP_REGION[1], {BUILDER})
    out = []
    for h in hits:
        r0 = h["state"].get("r0")
        if r0 and r0[0] == "const":
            out.append({"at": h["at"], "runtime_type": r0[1]})
    return out


def describe_state(state: dict, reg: str) -> str:
    v = state.get(reg)
    if not v:
        return "?"
    kind, value, extra = v
    if kind == "const":
        return f"const {value}"
    if kind == "literal":
        label = KNOWN.get(value, "")
        return f"ROM {value:#010x}" + (f" ({label})" if label else "")
    if kind == "deref":
        label = KNOWN.get(value + extra, KNOWN.get(value, ""))
        return (f"byte[{value + extra:#010x}]"
                + (f" ({label})" if label else ""))
    return "?"


def derive_setup(rom: bytes) -> list[dict]:
    """Per record type: the setup branch and the runtime type(s) it assigns."""
    md = disassembler()
    table = read_pointer_table(rom, SETUP_TABLE, 7)
    out = []
    for i, addr in enumerate(table):
        hits = cfg_runtime_types(md, rom, addr)
        runtime_types = sorted({h["runtime_type"] for h in hits})
        out.append({
            "type": i + 1,
            "type_name": OBJECT_TYPES.get(i + 1, "?"),
            "setup_handler": addr,
            "runtime_types": runtime_types,
            "runtime_type_evidence": hits,
            "conditional": (i + 1) in CONDITIONAL_TYPES,
        })
    return out


def derive_effects(rom: bytes) -> list[dict]:
    """The 13-entry effect table with each entry's disassembly facts.

    Every effect ends in ``bl 0x0808A638(r0, r1, config[0])`` - i.e. it runs
    an original level script.  r0 is a runtime field of the battle control
    block and r1 is a ROM script-data pointer; both are read back from the
    code path that reaches the call.
    """
    md = disassembler()
    table = read_pointer_table(rom, EFFECT_TABLE, EFFECT_COUNT)
    out = []
    for i, addr in enumerate(table):
        block = analyze_block(rom, addr, 16)
        hits = cfg_walk(md, rom, addr, EFFECT_REGION[0], EFFECT_REGION[1],
                        {EFFECT_CALL})
        calls = []
        for h in hits:
            r1 = h["state"].get("r1")
            script = None
            if r1 and r1[0] == "literal":
                script = decode_script_header(rom, r1[1])
            calls.append({
                "at": h["at"],
                "r0": describe_state(h["state"], "r0"),
                "r1": describe_state(h["state"], "r1"),
                "script": script,
            })
        out.append({
            "target": i + 1,
            "third_party_name": THIRD_PARTY_MECHANISM_NAMES.get(i + 1, ""),
            "handler": addr,
            "script_calls": calls,
            "is_noop": addr == EFFECT_NOOP,
            "reachable": i + 1 not in (EFFECT_INTERCEPT_TARGET,),
            "fact": EFFECT_TARGET_FACTS.get(i + 1, {}).get("note", ""),
            "calls": block["calls"],
            "literals": block["literals"],
            "instructions": block["instructions"],
        })
    return out


def read_objects(rom: bytes, stage: int, sub: int) -> list[dict]:
    base = CONFIG_BASE + stage * GROUP_STRIDE + sub * SUB_STRIDE
    recs = []
    for i in range(OBJECT_COUNT):
        p = base + OBJECT_OFFSET + i * 4
        otype, target, x, y = rom[p], rom[p + 1], rom[p + 2], rom[p + 3]
        recs.append({
            "index": i, "addr": p, "type": otype, "target": target,
            "x": x, "y": y, "occupied": otype != 0,
            "type_name": OBJECT_TYPES.get(otype, f"未知类型 {otype}"),
            "conditional": otype in CONDITIONAL_TYPES,
        })
    return recs


def scan_objects(rom: bytes) -> dict:
    type_count: dict[int, int] = {}
    type_targets: dict[int, dict[int, int]] = {}
    per_stage: list[dict] = []
    occupied_total = 0
    slots_used: dict[int, int] = {}
    for stage in range(BATTLE_STAGE_FIRST, BATTLE_STAGE_LAST + 1):
        for sub in range(SUB_COUNT):
            recs = read_objects(rom, stage, sub)
            occ = [r for r in recs if r["occupied"]]
            occupied_total += len(occ)
            for r in occ:
                t = r["type"]
                type_count[t] = type_count.get(t, 0) + 1
                type_targets.setdefault(t, {})
                type_targets[t][r["target"]] = type_targets[t].get(r["target"], 0) + 1
                slots_used[r["index"]] = slots_used.get(r["index"], 0) + 1
            if occ:
                per_stage.append({
                    "stage": stage, "sub": sub, "occupied": len(occ),
                    "records": [
                        {"index": r["index"], "type": r["type"],
                         "type_name": r["type_name"], "target": r["target"],
                         "x": r["x"], "y": r["y"]}
                        for r in occ
                    ],
                })
    return {
        "type_count": type_count,
        "type_targets": type_targets,
        "stages_with_objects": per_stage,
        "occupied_total": occupied_total,
        "stage_subs_with_objects": len(per_stage),
        "stage_subs_total": (BATTLE_STAGE_LAST - BATTLE_STAGE_FIRST + 1) * SUB_COUNT,
        "slot_usage": slots_used,
    }


def read_name_table(rom: bytes, base: int, count: int, mapping) -> list[str]:
    names = []
    for i in range(1, count + 1):
        ptr = struct.unpack_from("<I", rom, base + i * 4)[0] - ROM_BASE
        if not (0 <= ptr < len(rom)):
            names.append("")
            continue
        try:
            text, _ = text_codec.decode_tokens(rom, ptr, mapping)
        except Exception:
            text = ""
        names.append(text.replace("\n", "").strip())
    return names


def cross_name_tables(rom: bytes, scan: dict, mapping) -> dict:
    """Which table slots the maps actually use, and which stay unused."""
    used_by_type = {
        1: scan["type_targets"].get(1, {}),
        2: scan["type_targets"].get(2, {}),
        3: scan["type_targets"].get(3, {}),
        4: scan["type_targets"].get(4, {}),
    }
    out = {}
    for key, (base, count) in NAME_TABLES.items():
        if key == "ninjutsu":
            used = {int(t) for t in used_by_type.get(1, {})}
        elif key == "material":
            used = {int(t) for t in used_by_type.get(2, {})}
        else:
            used = {int(t) for t in used_by_type.get(4, {})}
            used |= {int(t) for t in used_by_type.get(3, {})}
        names = read_name_table(rom, base, count, mapping)
        out[key] = {
            "addr": base, "count": count,
            "names": names,
            "used_ids": sorted(used),
            "unused_ids": [i for i in range(1, count + 1) if i not in used],
            "used_count": len(used),
            "unused_count": count - len(used),
        }
    return out


def find_thumb_callers(rom: bytes, target: int) -> list[int]:
    """Find Thumb ``bl`` instructions that target `target`."""
    hits = []
    for off in range(0, len(rom) - 3, 2):
        h1, h2 = struct.unpack_from("<HH", rom, off)
        if (h1 & 0xF800) != 0xF000 or (h2 & 0xD000) != 0xD000:
            continue
        s = (h1 >> 10) & 1
        imm10 = h1 & 0x3FF
        j1 = (h2 >> 13) & 1
        j2 = (h2 >> 11) & 1
        imm11 = h2 & 0x7FF
        i1 = 1 - (j1 ^ s)
        i2 = 1 - (j2 ^ s)
        value = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if value & (1 << 24):
            value -= (1 << 25)
        addr = off + ROM_BASE
        if (addr + 4 + value) & ~1 == (target & ~1):
            hits.append(addr)
    return hits


def verify_effect_dispatch(rom: bytes) -> list[dict]:
    """Mechanically re-check the effect-table claims of notes/mechanisms-*.md.

    Every check is a ROM observation, so a wrong note fails here.
    """
    table = read_pointer_table(rom, EFFECT_TABLE, EFFECT_COUNT)
    callers = find_thumb_callers(rom, EFFECT_DISPATCHER)
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    add("effect table has 13 entries",
        len(table) == EFFECT_COUNT,
        f"{len(table)} pointers at {EFFECT_TABLE:#010x}")
    add("target 9 and 11 both point at the shared no-op endpoint",
        table[EFFECT_INTERCEPT_TARGET - 1] == EFFECT_NOOP
        and table[11 - 1] == EFFECT_NOOP,
        f"target 9 -> {table[EFFECT_INTERCEPT_TARGET - 1]:#010x}, "
        f"target 11 -> {table[11 - 1]:#010x}, endpoint {EFFECT_NOOP:#010x}")
    add("effect dispatcher has exactly one caller",
        callers == [EFFECT_CALL_SITE],
        f"callers: {[hex(c) for c in callers]}")
    # the interception: `cmp r0, #9` / `beq` right before the dispatcher call
    handler = disasm(rom, EFFECT_INTERCEPT_ADDR - 8, 6)
    texts = [f"{i.mnemonic} {i.op_str}".strip() for i in handler]
    add("pickup handler intercepts target 9 before the effect table",
        any(t.startswith("cmp") and "#9" in t for t in texts),
        " | ".join(texts))
    # the two-branch structure of the handler
    site = disasm(rom, EFFECT_CALL_SITE - 2, 2)
    add("the single call site is inside the shared type 5/6/7 handler",
        any(i.mnemonic == "bl"
            and int(i.op_str.strip().lstrip("#"), 16) == EFFECT_DISPATCHER
            for i in site),
        " | ".join(f"{i.mnemonic} {i.op_str}".strip() for i in site))
    return checks


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def print_stats(report: dict) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = print
    p(f"ROM      : {report['rom']}")
    p(f"SHA-256  : {report['sha256']}")
    p()

    disp = report["dispatch"]
    p(f"pickup dispatch table @ {DISPATCH_TABLE:#010x}: {disp['native_count']} handlers")
    for e in disp["entries"][:disp["native_count"]]:
        p(f"  [{e['index']}] -> {e['value']:#010x}   (record type {e['index'] + 1})")
    p()

    p("--- record type -> setup -> runtime type -> pickup handler ---")
    for row in report["setup"]:
        ev = ", ".join(f"{h['runtime_type']}@{h['at']:#010x}"
                       for h in row["runtime_type_evidence"]) or "-"
        p(f"  type {row['type']} {row['type_name']:<14} setup={row['setup_handler']:#010x} "
          f"runtime_type={row['runtime_types']} ({ev})"
          f"{'  [conditional]' if row['conditional'] else ''}")
    p()

    p("--- pickup handler disassembly summary ---")
    for h in report["handlers"]:
        p("")
        p(f"[{h['index']}] {h['address']:#010x}  record type {h['index'] + 1}  {h['role']}")
        for ins in h["instructions"][:report["insn_limit"]]:
            p(f"  {ins['addr']:#010x}: {ins['text']}")
        p("  calls  : " + (", ".join(f"{c:#010x}" for c in h["calls"]) or "-"))
        p("  literals:")
        for lit in h["literals"]:
            extra = f"  {lit['label']}" if lit["label"] else ""
            p(f"    {lit['at']:#010x} {lit['reg']} <- [{lit['lit_addr']:#010x}] "
              f"= {lit['value']:#010x} ({lit['kind']}){extra}")
        p("  memory : " + (", ".join(f"{m['at']:#010x}:{m['op']}" for m in h["memory"]) or "-"))
    p()

    p(f"--- effect table @ {EFFECT_TABLE:#010x} (index = target-1) ---")
    for e in report["effects"]:
        p(f"  target {e['target']:>2}  {e['handler']:#010x}  {e['third_party_name']}"
          f"{'  [no-op]' if e['is_noop'] else ''}")
        for c in e["script_calls"]:
            sc = c.get("script") or {}
            extra = ""
            if sc:
                extra = (f"  script@{sc['addr']:#010x} op=0x{sc['op']:02X}"
                         f"({sc['op_name']})")
                if "character_id" in sc:
                    extra += f" 角色ID={sc['character_id']} -> {sc['pointer']:#010x}"
            p(f"              -> {EFFECT_CALL:#010x}(r0={c['r0']}, r1={c['r1']}){extra}")
    p()

    p("--- effect target facts (derived from the native code) ---")
    for target, fact in sorted(report["effect_target_facts"].items()):
        p(f"  target {target}: reachable={fact['reachable']}")
        p(f"      {fact['note']}")
    p()

    p("--- record type -> level script route ---")
    for rtype, route in sorted(report["type_script_route"].items()):
        p(f"  type {rtype}: setup={route['setup']:#010x} "
          f"runtime_type={route['runtime_types']} sound={route['sound']}")
        p(f"      {route['note']}")
    p()

    p("--- map object type distribution (all stages x subs) ---")
    scan = report["objects"]
    p(f"records with type != 0: {scan['occupied_total']} "
      f"over {scan['stage_subs_with_objects']}/{scan['stage_subs_total']} stage/sub")
    for t in sorted(scan["type_count"]):
        p(f"  type {t} {OBJECT_TYPES.get(t, '?'):<14} count={scan['type_count'][t]:<4} "
          f"targets={dict(sorted(scan['type_targets'][t].items()))}")
    p("  record slot usage: " + str(dict(sorted(scan["slot_usage"].items()))))
    p()

    p("--- name table cross statistics ---")
    for key, info in report["name_tables"].items():
        p(f"  {key:<11} {info['addr']:#010x} count={info['count']:<3} "
          f"used={info['used_count']:<3} unused={info['unused_count']:<3} "
          f"unused_ids={info['unused_ids']}")
    p()

    p("--- stage/sub carrying objects ---")
    for row in scan["stages_with_objects"]:
        desc = " | ".join(
            f"#{r['index']} t{r['type']} tgt{r['target']} ({r['x']},{r['y']})"
            for r in row["records"])
        p(f"  stage {row['stage']:>2} sub {row['sub']}: {row['occupied']:>2}  {desc}")


def build_report(rom_path: pathlib.Path, insn_limit: int) -> dict:
    rom = rom_path.read_bytes()
    mapping, _ = text_codec.load_mapping(rom_path)
    dispatch_entries, native_count = read_dispatch(rom)
    handlers = []
    for e in dispatch_entries[:native_count]:
        block = analyze_block(rom, e["value"], max(insn_limit, 24))
        handlers.append({
            "index": e["index"],
            "address": e["value"],
            "role": HANDLER_ROLES.get(e["index"], ""),
            "calls": block["calls"],
            "literals": block["literals"],
            "memory": block["memory"],
            "compares": block["compares"],
            "instructions": block["instructions"],
        })
    scan = scan_objects(rom)
    names = cross_name_tables(rom, scan, mapping)
    return {
        "rom": str(rom_path),
        "sha256": hashlib.sha256(rom).hexdigest(),
        "insn_limit": insn_limit,
        "dispatch": {
            "addr": DISPATCH_TABLE,
            "native_count": native_count,
            "entries": dispatch_entries,
            "index_rule": "(u16 runtime-slot+4) - 1 ; slot+4 = record type byte",
        },
        "setup": derive_setup(rom),
        "setup_table": {"addr": SETUP_TABLE, "entries": read_pointer_table(rom, SETUP_TABLE, 7)},
        "effects": derive_effects(rom),
        "effect_table": {"addr": EFFECT_TABLE, "count": EFFECT_COUNT,
                         "index_rule": "target - 1 (1..13)"},
        "effect_target_facts": EFFECT_TARGET_FACTS,
        "effect_noop_endpoint": EFFECT_NOOP,
        "type_script_route": TYPE_SCRIPT_ROUTE,
        "handlers": handlers,
        "objects": scan,
        "name_tables": names,
        "object_types": OBJECT_TYPES,
        "conditional_types": sorted(CONDITIONAL_TYPES),
        "third_party_mechanism_names": THIRD_PARTY_MECHANISM_NAMES,
        "runtime": {
            "object_array_wram": OBJECT_ARRAY_WRAM,
            "object_slot_bytes": 16,
            "object_slot_count": 32,
            "tile_table_wram": TILE_TABLE_WRAM,
            "map_width_wram": MAP_WIDTH_WRAM,
            "unit_base_wram": UNIT_BASE_WRAM,
            "unit_stride": UNIT_STRIDE,
            "battle_state_wram": BATTLE_STATE_WRAM,
            "builder": BUILDER,
            "pickup_dispatcher": PICKUP_DISPATCHER,
            "effect_dispatcher": EFFECT_DISPATCHER,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", nargs="?", default=None)
    ap.add_argument("--stats", action="store_true", help="human readable report")
    ap.add_argument("--json", default=None, help="write structured JSON here")
    ap.add_argument("--stage", type=int, default=None)
    ap.add_argument("--sub", type=int, default=0)
    ap.add_argument("--disasm", default=None, help="disassemble this address")
    ap.add_argument("--count", type=int, default=48, help="instructions per block")
    ap.add_argument("--callers", default=None, help="find thumb bl callers of this address")
    ap.add_argument("--verify", action="store_true",
                    help="mechanically re-check the effect-table claims")
    args = ap.parse_args()

    rom_path = text_codec.resolve_rom(args.rom)
    rom = rom_path.read_bytes()

    if args.verify:
        checks = verify_effect_dispatch(rom)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        for c in checks:
            print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['check']}: {c['detail']}")
        return 0 if all(c["ok"] for c in checks) else 1

    if args.disasm:
        for insn in disasm(rom, int(args.disasm, 0), args.count):
            print(f"{insn.address:#010x}: {insn.mnemonic:<8} {insn.op_str}".rstrip())
        return 0

    if args.callers:
        for c in find_thumb_callers(rom, int(args.callers, 0)):
            print(f"{c:#010x}")
        return 0

    report = build_report(rom_path, args.count)

    if args.stage is not None:
        recs = read_objects(rom, args.stage, args.sub)
        names = report["name_tables"]
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(f"stage {args.stage} sub {args.sub}: "
              f"{sum(1 for r in recs if r['occupied'])}/16 records occupied")
        for r in recs:
            if not r["occupied"]:
                continue
            extra = ""
            if r["type"] == 1 and 1 <= r["target"] <= 93:
                extra = names["ninjutsu"]["names"][r["target"] - 1]
            elif r["type"] == 2 and 1 <= r["target"] <= 16:
                extra = names["material"]["names"][r["target"] - 1]
            elif r["type"] in (3, 4) and 1 <= r["target"] <= 62:
                extra = names["character"]["names"][r["target"] - 1]
            elif r["type"] in (5, 6, 7):
                extra = THIRD_PARTY_MECHANISM_NAMES.get(r["target"], f"机关 {r['target']}")
            flag = " (conditional)" if r["conditional"] else ""
            print(f"  [{r['index']:2d}] type={r['type']} {r['type_name']:<14} "
                  f"target={r['target']:<3} ({r['x']},{r['y']}) {extra}{flag}")
        return 0

    if args.json:
        write_text(args.json, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"wrote {args.json}")

    if args.stats or not args.json:
        print_stats(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
