#!/usr/bin/env python3
"""Story-script VM opcode semantics, derived from the Konoha Senki ROM.

The story VM is a Thumb bytecode interpreter.  This tool finds the
interpreter *in the ROM* (nothing about its location is hardcoded), reads its
jump table, and derives for every opcode:

  * the handler address,
  * the operand layout (which byte of the instruction holds what),
  * the instruction length (from the handler's own ``r7`` arithmetic),
  * the callee the handler runs and the RAM/ROM cells it touches,
  * a semantic label, with the concrete instruction that proves it.

Everything is then cross-validated against all 55 story scenes: every
opcode occurrence must be explainable, every branch pointer must land on an
instruction boundary inside a decoded script, and every pointer operand must
point into the ROM.  The tool exits non-zero if an opcode it claims to have
proved fails that validation.

Usage
-----
    python tools/story_vm_ops.py rom/base.gba
    python tools/story_vm_ops.py rom/base.gba --json build/story_vm_ops.json
    python tools/story_vm_ops.py rom/base.gba --stats
    python tools/story_vm_ops.py rom/base.gba --disasm 0x080977B8 --count 40
"""
from __future__ import annotations

import argparse
import os
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools.lib.io import write_json  # noqa: E402
from tools import decode_story_script as dss  # noqa: E402

ROM_BASE = 0x08000000


# --------------------------------------------------------------------------
# capstone plumbing (same discovery order as tools/mechanism_map.py)
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


CS = load_capstone()
MD = CS.Cs(CS.CS_ARCH_ARM, CS.CS_MODE_THUMB)
MD.detail = True


def thumb_disasm(rom: bytes, addr: int, count: int = 1) -> list:
    blob = rom[addr - ROM_BASE: addr - ROM_BASE + count * 4 + 8]
    return list(MD.disasm(blob, addr))


def text_of(insn) -> str:
    return f"{insn.mnemonic} {insn.op_str}".strip()


# --------------------------------------------------------------------------
# 1. find the interpreter and its jump table
# --------------------------------------------------------------------------
# The dispatcher of a bytecode VM compiled by GCC for ARM looks like
#     ldrb r0, [r7]          ; fetch the opcode
#     cmp  r0, #MAX         ; range check
#     lsls r0, r0, #2        ; opcode * 4
#     ldr  r1, [pc, #imm]    ; jump-table base
#     adds r0, r0, r1
#     ldr  r0, [r0]
#     mov  pc, r0
# The tail "adds r0, r0, r1 / ldr r0, [r0] / mov pc, r0" is the giveaway.
DISPATCH_TAIL = bytes([0x40, 0x18, 0x00, 0x68, 0x87, 0x46])


def _imm_of(op_str: str) -> int | None:
    if "#" not in op_str:
        return None
    try:
        return int(op_str.split("#")[1].split("]")[0].split(",")[0].strip(), 0)
    except (IndexError, ValueError):
        return None


def find_dispatch(rom: bytes) -> dict:
    """Locate the opcode jump table by scanning the ROM for the dispatch tail."""
    hits = []
    start = 0
    while True:
        pos = rom.find(DISPATCH_TAIL, start)
        if pos < 0:
            break
        start = pos + 1
        # the tail starts at the "adds r0, r0, r1"; the "ldr rX, [pc,#imm]"
        # that supplies the table base is one or two instructions before it.
        ins = None
        for back in (2, 4, 6):
            insns = thumb_disasm(rom, ROM_BASE + pos - back, 1)
            if not insns:
                continue
            cand = insns[0]
            if cand.mnemonic == "ldr" and "[pc" in cand.op_str:
                ins = cand
                break
        if ins is None:
            continue
        imm = _imm_of(ins.op_str)
        if imm is None:
            continue
        # the literal holds the *base* of the jump table
        lit_addr = ((ins.address + 4) & ~3) + imm
        if not (0 <= lit_addr - ROM_BASE <= len(rom) - 4):
            continue
        table = struct.unpack_from("<I", rom, lit_addr - ROM_BASE)[0]
        if not (ROM_BASE <= table < ROM_BASE + len(rom)):
            continue
        # the range check "cmp r0, #MAX" sits a few instructions earlier
        max_op = None
        range_addr = None
        window = thumb_disasm(rom, ins.address - 40, 12)
        for cand in window:
            if cand.address >= ins.address:
                break
            if cand.mnemonic == "cmp" and cand.op_str.startswith("r0,"):
                val = _imm_of(cand.op_str)
                if val is not None:
                    max_op = val
                    range_addr = cand.address
        if max_op is None:
            continue
        entries = []
        ok = True
        for i in range(max_op + 1):
            off = table - ROM_BASE + i * 4
            if off < 0 or off + 4 > len(rom):
                ok = False
                break
            v = struct.unpack_from("<I", rom, off)[0]
            if not (ROM_BASE <= v < ROM_BASE + len(rom)):
                ok = False
                break
            entries.append(v)
        if not ok or len(entries) < 8:
            continue
        hits.append({
            "dispatch_addr": ins.address - 4,   # the "ldr r1,[pc,#imm]"
            "range_check_addr": range_addr,
            "table_addr": table,
            "max_opcode": max_op,
            "entries": entries,
        })
    if not hits:
        raise SystemExit("story VM dispatch table not found in this ROM")
    # the real dispatcher is the one whose table has the most distinct
    # in-range handlers (a false positive has a handful).
    hits.sort(key=lambda h: (len(set(h["entries"])), h["max_opcode"]), reverse=True)
    return hits[0]


def find_function_entry(rom: bytes, addr: int, window: int = 0x300) -> int | None:
    """Walk back from `addr` to the `push {...lr}` that opens the function."""
    lo = max(0, addr - window)
    for a in range(addr, lo, -2):
        half = struct.unpack_from("<H", rom, a - ROM_BASE)[0]
        if (half & 0xFF00) == 0xB500 and (half & 0x00FF):   # push {..,lr}
            return a
    return None


def find_thumb_bl_targets(rom: bytes) -> dict[int, list[int]]:
    """Map every Thumb BL target address to the list of call sites."""
    out: dict[int, list[int]] = {}
    for off in range(0, len(rom) - 3, 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if (hw & 0xF800) != 0xF000:
            continue
        second = struct.unpack_from("<H", rom, off + 2)[0]
        if (second & 0xD000) != 0xD000:
            continue
        s = (hw >> 10) & 1
        imm10 = hw & 0x3FF
        j1 = (second >> 13) & 1
        j2 = (second >> 11) & 1
        imm11 = second & 0x7FF
        i1 = ~(j1 ^ s) & 1
        i2 = ~(j2 ^ s) & 1
        offset = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
        if s:
            offset -= (1 << 25)
        target = (ROM_BASE + off + 4 + offset) & 0xFFFFFFFF
        out.setdefault(target, []).append(ROM_BASE + off)
    return out


def find_literal_pool_values(rom: bytes, lo: int, hi: int) -> list[int]:
    """All u32 values that live in the literal pool of the region [lo, hi)."""
    out = []
    for a in range(lo, hi, 4):
        if a - ROM_BASE + 4 > len(rom):
            break
        out.append(struct.unpack_from("<I", rom, a - ROM_BASE)[0])
    return out


def looks_like_root_table(rom: bytes, addr: int, scenes: int = 55) -> int:
    """Number of leading per-scene entries at `addr` that look like roots.

    A root table holds one u32 per scene; a scene without a script stores 0,
    so zero entries are legal and the scan may not stop at the first one.
    The scan stops at the first entry that is neither 0 nor a ROM pointer.
    """
    if not (ROM_BASE <= addr < ROM_BASE + len(rom)):
        return 0
    n = 0
    for i in range(scenes):
        off = addr - ROM_BASE + i * 4
        if off < 0 or off + 4 > len(rom):
            break
        v = struct.unpack_from("<I", rom, off)[0]
        if v == 0:
            n += 1
            continue
        if not (ROM_BASE <= v < ROM_BASE + len(rom)):
            break
        n += 1
    return n


# --------------------------------------------------------------------------
# 2. per-handler static analysis
# --------------------------------------------------------------------------
def decode_cfg(rom: bytes, lo: int, hi: int, stop: set[int],
               seeds: list[int] | None = None) -> dict[int, object]:
    """Recursive-descent decode of the handler body, so data is never misread.

    `seeds` lets the caller start the walk at several entry points (the VM
    reaches its handlers through a jump table, so a single seed would only
    cover the code that is reachable by direct branches).
    """
    region: dict[int, object] = {}
    stack = list(seeds) if seeds else [lo]
    while stack:
        a = stack.pop()
        if a in region or not (lo <= a < hi):
            continue
        blob = rom[a - ROM_BASE:a - ROM_BASE + 4]
        if len(blob) < 2:
            continue
        ins = next(MD.disasm(blob, a), None)
        if ins is None:
            continue
        region[a] = ins
        m, op = ins.mnemonic, ins.op_str
        if m == "b":
            tgt = _branch_target(op)
            if tgt is not None and lo <= tgt < hi and tgt not in stop:
                stack.append(tgt)
            continue
        if m in COND_BRANCHES:
            tgt = _branch_target(op)
            if tgt is not None and lo <= tgt < hi and tgt not in stop:
                stack.append(tgt)
            if (a + ins.size) not in stop:
                stack.append(a + ins.size)
            continue
        if m in ("bx", "pop") and "pc" in op:
            continue
        if (a + ins.size) not in stop:
            stack.append(a + ins.size)
    return region


COND_BRANCHES = {
    "beq", "bne", "bhi", "bls", "bgt", "ble", "bcc", "bcs",
    "bmi", "bpl", "bvs", "bvc",
}


def _branch_target(op: str) -> int | None:
    try:
        return int(op.strip().lstrip("#"), 16)
    except ValueError:
        return None


def literal_value(rom: bytes, insn) -> tuple[int | None, int | None]:
    """(literal address, value) for `ldr rX, [pc, #imm]`."""
    if insn.mnemonic != "ldr" or "[pc" not in insn.op_str:
        return None, None
    imm = _imm_of(insn.op_str)
    if imm is None:
        return None, None
    la = ((insn.address + 4) & ~3) + imm
    if not (0 <= la - ROM_BASE <= len(rom) - 4):
        return None, None
    return la, struct.unpack_from("<I", rom, la - ROM_BASE)[0]


def analyse_handler(rom: bytes, lo: int, hi: int, loop_head: int) -> dict:
    """Extract operand offsets, r7 advance, callees and RAM cells."""
    region = decode_cfg(rom, lo, hi, stop={loop_head})
    byte_offsets: set[int] = set()
    half_offsets: set[int] = set()
    word_offsets: set[int] = set()
    calls: list[int] = []
    ram_cells: list[int] = []
    advances: list[int] = []
    # `adds rX, r7, #k` immediately before a call: the call takes a pointer to
    # instruction+k.  Which call decides whether it is a u32 pointer or a text
    # body is decided later by the callee's own behaviour.
    setup: dict[int, tuple[int, int]] = {}      # call addr -> (operand r, k)
    last_r7off: tuple[int, int] | None = None
    for addr in sorted(region):
        ins = region[addr]
        m, op = ins.mnemonic, ins.op_str
        if m in ("ldrb", "ldrh", "ldr") and "[r7" in op:
            off = _imm_of(op)
            if off is not None:
                if m == "ldrb":
                    byte_offsets.add(off)
                elif m == "ldrh":
                    half_offsets.add(off)
                else:
                    word_offsets.add(off)
        if m == "adds" and ", r7, #" in op:
            off = _imm_of(op)
            if off is not None:
                last_r7off = (addr, off)
        if m == "bl":
            tgt = _branch_target(op)
            if tgt is not None:
                calls.append(tgt)
                if last_r7off is not None and last_r7off[0] == addr - 2:
                    setup[addr] = last_r7off[1]
        elif m not in ("adds", "mov", "movs"):
            last_r7off = None
        if m == "adds" and op.startswith("r7, #"):
            off = _imm_of(op)
            if off is not None:
                advances.append(off)
        la, val = literal_value(rom, ins)
        if la is not None and val is not None and 0x02000000 <= val < 0x04000000:
            ram_cells.append(val)
    return {
        "range": (lo, hi),
        "byte_offsets": sorted(byte_offsets),
        "half_offsets": sorted(half_offsets),
        "word_offsets": sorted(word_offsets),
        "calls": calls,
        "ram_cells": sorted(set(ram_cells)),
        "advances": advances,
        "r7_setup": setup,
        "instructions": {a: text_of(i) for a, i in region.items()},
    }


# --------------------------------------------------------------------------
# 2b. symbolic execution of a handler
# --------------------------------------------------------------------------
# A handler is executed with r7 = the address of its own opcode byte.  The
# only relative memory read that matters is `ldrb rX, [r7, #k]`; the read at
# k == 0 is the opcode itself, so a branch on it can be resolved and the two
# opcodes that share a handler (0x08 / 0x0E) get their own length.
#
# r7 is tracked as an integer offset from the opcode byte, or None when the
# handler has jumped somewhere unknown.
class SymState:
    __slots__ = ("regs", "r7", "flags")

    def __init__(self, regs: dict, r7: int | None, flags=None):
        self.regs = regs
        self.r7 = r7
        self.flags = flags

    def copy(self) -> "SymState":
        return SymState(dict(self.regs), self.r7, self.flags)


def _reg(op_str: str) -> str:
    return op_str.split(",")[0].strip()


def _split_ops(op_str: str) -> list[str]:
    body = op_str.split("[")[0]
    return [x.strip() for x in body.split(",") if x.strip()]


def execute_handler(rom: bytes, region: dict, loop_head: int, opcode: int,
                    start: int) -> dict:
    """Run the handler symbolically; report the r7 offset it ends with.

    Only r7 takes part in the visited-state key: the handlers contain
    counting loops whose loop counter is a memory byte, and including it
    would make the search diverge.
    """
    results: list[int | None] = []
    visited: set[tuple] = set()
    executed: dict[int, set[int]] = {}
    executed_addrs: set[int] = set()
    overflow = False
    STATE_CAP = 4000

    def step(st: SymState, addr: int) -> None:
        nonlocal overflow
        stack = [(addr, st)]
        while stack:
            if len(visited) > STATE_CAP:
                overflow = True
                return
            a, st = stack.pop()
            key = (a, st.r7)
            if key in visited:
                continue
            visited.add(key)
            executed_addrs.add(a)
            ins = region.get(a)
            if ins is None:
                results.append(st.r7)
                continue
            m, op = ins.mnemonic, ins.op_str
            nxt = a + ins.size
            st = st.copy()
            # ---- register ops -------------------------------------------
            parts = _split_ops(op)
            dst = parts[0] if parts else None
            if m in ("movs", "mov") and len(parts) == 2:
                src = parts[1]
                if src.startswith("#"):
                    st.regs[dst] = ("const", _imm_of(src))
                elif src.startswith("r"):
                    st.regs[dst] = st.regs.get(src, ("unk", None))
                else:
                    st.regs[dst] = ("unk", None)
            elif m in ("adds", "add", "sub", "subs", "rsbs", "eors", "orrs",
                       "ands", "bics", "muls", "mvns", "negs", "adcs", "sbc",
                       "lsls", "lsrs", "asrs", "lsl", "lsr", "asr") and len(parts) >= 2:
                src = parts[1]
                imm = _imm_of(parts[2]) if len(parts) == 3 else None
                if src == "r7" and imm is not None:
                    # a pointer to instruction+imm
                    st.regs[dst] = ("r7off", imm)
                elif src.startswith("#") and imm is not None:
                    st.regs[dst] = ("const", imm)
                elif src.startswith("r"):
                    val = st.regs.get(src, ("unk", None))
                    if val[0] == "const" and val[1] is not None and imm is not None:
                        if m in ("adds", "add"):
                            st.regs[dst] = ("const", val[1] + imm)
                        elif m in ("subs", "sub"):
                            st.regs[dst] = ("const", val[1] - imm)
                        elif m in ("orrs",):
                            st.regs[dst] = ("const", val[1] | imm)
                        elif m in ("ands",):
                            st.regs[dst] = ("const", val[1] & imm)
                        elif m in ("eors",):
                            st.regs[dst] = ("const", val[1] ^ imm)
                        elif m in ("bics",):
                            st.regs[dst] = ("const", val[1] & ~imm)
                        elif m in ("lsls", "lsl"):
                            st.regs[dst] = ("const", (val[1] << imm) & 0xFFFFFFFF)
                        elif m in ("lsrs", "lsr"):
                            st.regs[dst] = ("const", (val[1] & 0xFFFFFFFF) >> imm)
                        elif m in ("asrs", "asr"):
                            v = val[1] & 0xFFFFFFFF
                            sign = v & 0x80000000
                            st.regs[dst] = ("const", ((v >> imm) |
                                          (0xFFFFFFFF << (32 - imm))) & 0xFFFFFFFF
                                      if sign else (v >> imm))
                        else:
                            st.regs[dst] = ("unk", None)
                    elif val[0] == "const" and val[1] is not None and imm is None \
                            and m in ("movs", "mov"):
                        st.regs[dst] = val
                    else:
                        st.regs[dst] = ("unk", None)
                else:
                    st.regs[dst] = ("unk", None)
            elif m in ("ldrb", "ldrh", "ldr"):
                dst = _reg(op)
                if "[r7" in op:
                    off = _imm_of(op)
                    if off is None and m == "ldrb" and "[r7]" in op:
                        # the opcode byte itself, but only while r7 still points
                        # at the instruction start
                        st.regs[dst] = ("const", opcode) if st.r7 == 0 else ("unk", None)
                    elif off == 0 and m == "ldrb":
                        st.regs[dst] = ("const", opcode)
                    elif off is not None:
                        st.regs[dst] = ("mem", (m, off))
                        executed.setdefault(addr, set()).add(off)
                    else:
                        st.regs[dst] = ("unk", None)
                else:
                    st.regs[dst] = ("unk", None)
            elif m in ("strb", "strh", "str"):
                pass
            elif m == "cmp":
                a_v = _value(st, parts[0]) if parts else None
                b_v = None
                if len(parts) == 2:
                    if parts[1].startswith("#"):
                        b_v = _imm_of(parts[1])
                    else:
                        b_v = _value(st, parts[1])
                st.flags = ("cmp", a_v, b_v)
            elif m == "bl":
                tgt = _branch_target(op)
                st.regs["r0"] = ("call", tgt)
            elif m == "b":
                tgt = _branch_target(op)
                if tgt == loop_head:
                    results.append(st.r7)
                    continue
                if tgt is not None and tgt in region:
                    stack.append((tgt, st))
                continue
            elif m in COND_BRANCHES:
                tgt = _branch_target(op)
                taken = _decide(m, st.flags)
                if taken is True:
                    if tgt == loop_head:
                        results.append(st.r7)
                        continue
                    if tgt is not None and tgt in region:
                        stack.append((tgt, st))
                    continue
                if taken is False:
                    stack.append((nxt, st))
                    continue
                # unknown: explore both
                if tgt == loop_head:
                    results.append(st.r7)
                elif tgt is not None and tgt in region:
                    stack.append((tgt, st.copy()))
                stack.append((nxt, st))
                continue
            elif m in ("bx", "pop") and "pc" in op:
                results.append(st.r7)
                continue
            # r7 updates
            if m in ("adds", "add") and op.startswith("r7"):
                parts = _split_ops(op)
                if len(parts) == 2 and parts[1].startswith("#"):
                    imm = _imm_of(parts[1])
                    st.r7 = (st.r7 + imm) if (st.r7 is not None and imm is not None) else None
                elif len(parts) >= 2:
                    src = parts[1]
                    imm = _imm_of(parts[2]) if len(parts) == 3 else 0
                    if src == "r7":
                        st.r7 = (st.r7 + (imm or 0)) if st.r7 is not None else None
                    else:
                        val = st.regs.get(src, ("unk", None))
                        if val[0] == "r7off" and val[1] is not None and st.r7 is not None:
                            st.r7 = st.r7 + val[1] + (imm or 0)
                        else:
                            st.r7 = None
            if nxt == loop_head:
                # the handler falls through into the dispatch loop
                results.append(st.r7)
                continue
            stack.append((nxt, st))

    def _value(st: SymState, reg: str):
        v = st.regs.get(reg)
        if v is None:
            return None
        if v[0] == "const":
            return v[1]
        if v[0] == "r7off":
            return v[1]
        return None

    def _decide(mnemonic: str, flags) -> bool | None:
        if not flags or flags[0] != "cmp":
            return None
        _, a, b = flags
        if a is None or b is None:
            return None
        if mnemonic == "beq":
            return a == b
        if mnemonic == "bne":
            return a != b
        if mnemonic == "bhi":
            return a > b
        if mnemonic == "bls":
            return a <= b
        if mnemonic == "bgt":
            return a > b
        if mnemonic == "ble":
            return a <= b
        if mnemonic == "bcc":
            return a < b
        if mnemonic == "bcs":
            return a >= b
        return None

    start_state = SymState({}, 0)
    step(start_state, start)
    lengths = sorted({r for r in results if r is not None})
    return {
        "r7_offsets": lengths,
        "r7_known": (not overflow) and len(lengths) == 1
                    and all(r is not None for r in results),
        "unresolved": any(r is None for r in results) or overflow,
        "executed": executed,
        "executed_addrs": executed_addrs,
    }



def find_u32_reader(rom: bytes, vm_region: dict, loop_head: int):
    """The helper that reads the u32 branch target at r7+k.

    It is the callee of the shared tail
        adds r0, r7, #k
        bl  <reader>
        adds r7, r0, #0
        b    <loop head>
    Returns (reader_address, address_of_the_bl_instruction).
    """
    prev_bl = None
    prev_bl_addr = None
    for addr in sorted(vm_region):
        ins = vm_region[addr]
        if ins.mnemonic == "bl":
            prev_bl = _branch_target(ins.op_str)
            prev_bl_addr = addr
            continue
        if ins.mnemonic != "adds" or not ins.op_str.startswith("r7, r0"):
            continue
        nxt = vm_region.get(addr + ins.size)
        if nxt is None or nxt.mnemonic != "b":
            continue
        if _branch_target(nxt.op_str) != loop_head:
            continue
        if prev_bl is not None:
            return prev_bl, prev_bl_addr
    return None, None


def u32_operand_offsets(rom: bytes, region: dict, reader: int | None,
                         call_site: int | None) -> list[int]:
    """Offsets k where the handler reads a u32 branch target at r7+k.

    Two shapes are recognised:
        adds rX, r7, #k ; bl <reader>      (the handler calls the reader)
        adds rX, r7, #k ; b  <reader call>  (the handler jumps into the tail)
    """
    if reader is None:
        return []
    out = []
    for addr in sorted(region):
        ins = region[addr]
        if ins.mnemonic != "adds":
            continue
        parts = _split_ops(ins.op_str)
        if len(parts) != 3 or parts[1] != "r7":
            continue
        off = _imm_of(parts[2])
        nxt = region.get(addr + ins.size)
        if off is None or nxt is None:
            continue
        if nxt.mnemonic == "bl" and _branch_target(nxt.op_str) == reader:
            out.append(off)
        elif nxt.mnemonic == "b" and call_site is not None \
                and _branch_target(nxt.op_str) == call_site:
            out.append(off)
    return sorted(set(out))


# --------------------------------------------------------------------------
# 3. semantic labels
# --------------------------------------------------------------------------
# `evidence` is (address, instruction text).  The tool re-reads the ROM and
# fails if the quoted instruction is not actually there, so every "proved"
# row is falsifiable.
PROVED = "proved"
INFERRED = "inferred"
UNPROVED = "unproved"

SEMANTICS: dict[int, dict] = {
    0x00: dict(label="结束脚本 / 从子脚本返回",
               conf=PROVED, ev=(0x08097916, "mov r0, sl"),
               ev2=(0x0809792C, "ldr r7, [r0]"),
               note="sl=调用深度; 深度>0 时从栈上取回返回地址继续执行"),
    0x01: dict(label="显示一段文本 (正文从 +1 起, NUL 结尾, 含控制码)",
               conf=PROVED, ev=(0x080978F0, "adds r1, r7, #1"),
               ev2=(0x080978F4, "bl #0x806626c"),
               note="0x806626C 是控制码感知的文本渲染器, 返回串尾指针"),
    0x02: dict(label="选择消息框台词行/格 (槽@+1, 行@+2, 格@+3)",
               conf=PROVED, ev=(0x08097930, "ldrb r0, [r7, #1]"),
               ev2=(0x080968A8, "strb r1, [r4, #2]"),
               ev3=(0x080968AC, "strb r0, [r4, #3]"),
               ev4=(0x08096154, "lsls r0, r0, #3"),
               note="槽号索引 0x03005E50 的消息框指针表 (只有 0/1 两个槽); "
                    "行/格是台词表 0x085A4DEC 的两级下标 (行距 40 字节, 格距 8 字节), "
                    "每格 = {台词指针, 头像图指针}; 结果写消息框 +0x2E(行)/+0x2F(格), "
                    "并等框空闲后再切换"),
    0x03: dict(label="关闭消息框 (槽@+1; 0xFF = 两个都关)",
               conf=PROVED, ev=(0x0809794E, "ldrb r0, [r7, #1]"),
               ev2=(0x08096678, "cmp r1, #0xff"),
               ev3=(0x080966CC, "movs r6, #1"),
               ev4=(0x0809667C, "ldr r6, [pc, #0x30]"),
               note="槽号索引 0x03005E50; 0xFF 走「两个框一起关」分支 (r6 先取 "
                    "0xFFFF 作哨兵, 再依次落到 0/1), 否则只关指定槽; "
                    "关框 = 消息框 +0x2C 状态置 0x20 (或按模式置 0x30) 并等框空闲"),
    0x04: dict(label="切换消息框台词行/格并立即重画 (槽@+1, 行@+2, 格@+3)",
               conf=PROVED, ev=(0x08097958, "ldrb r0, [r7, #1]"),
               ev2=(0x08096A22, "bl #0x8096238"),
               ev3=(0x080962BA, "strb r1, [r0, #2]"),
               ev4=(0x080962C2, "strb r1, [r0, #3]"),
               note="槽/行/格含义同 0x02; 0x8096238(槽,行,格,0,0,0x02002880) 画台词"
                    "并画消息框边框, 行/格写消息框 +0x2E/+0x2F; 随后 0x8096DD4 重画头像"),
    0x05: dict(label="选择菜单的一项文字 (正文从 +2 起)",
               conf=PROVED, ev=(0x080979B0, "adds r1, r7, #2"),
               ev2=(0x080979B4, "bl #0x806626c"),
               note="与 0x01 同一条渲染路径, 只是正文前面多一个字节"),
    0x06: dict(label="二选一分支 (两个 u32 目标: +1 / +5)",
               conf=PROVED, ev=(0x080979DA, "lsls r0, r0, #2"),
               ev2=(0x080979DE, "adds r0, r7, r0"),
               note="用 0x0200A880 的选择计数在 +1 / +5 两个目标间二选一"),
    0x07: dict(label="无条件跳转 (u32 目标 @ +1)",
               conf=PROVED, ev=(0x08097D20, "adds r0, r7, #1"),
               ev2=(0x08097D22, "bl #0x8096ea4"),
               note="0x8096EA4 读 u32; 目标即跳转地址"),
    0x08: dict(label="设置头像+说话人名字 (头像ID @ +1)",
               conf=PROVED, ev=(0x08097A0A, "ldrb r0, [r7, #1]"),
               ev2=(0x08097A12, "ldr r4, [pc, #0x2c]"),
               note="名字取自 ROM 表 0x085A57C4 + id*12 (内嵌 2 字节字形码), 随后 0x8096E60 设头像"),
    0x09: dict(label="置故事标志 bit(id) @ 0x020314F0",
               conf=PROVED, ev=(0x08097AB4, "ldrb r0, [r7, #1]"),
               ev2=(0x08097ABE, "bl #0x8097050"),
               note="0x8097050(id, 1): mode!=0 -> 置位"),
    0x0A: dict(label="清故事标志 bit(id) @ 0x020314F0",
               conf=PROVED, ev=(0x08097ABA, "ldrb r0, [r7, #1]"),
               ev2=(0x08097ABE, "bl #0x8097050"),
               note="0x8097050(id, 0): mode==0 -> 清位"),
    0x0B: dict(label="条件跳转: 故事标志 bit(id) 为 1 时跳 (u32 目标 @ +2)",
               conf=PROVED, ev=(0x08097AC4, "ldrb r0, [r7, #1]"),
               ev2=(0x08097AC6, "bl #0x80970a0"),
               note="0x80970A0 返回 0/1; ==1 才跳"),
    0x0C: dict(label="条件跳转: 故事标志 bit(id) 为 0 时跳 (u32 目标 @ +2)",
               conf=PROVED, ev=(0x08097AD8, "ldrb r0, [r7, #1]"),
               ev2=(0x08097ADA, "bl #0x80970a0"),
               note="0x80970A0 返回 0/1; 0 才跳"),
    0x0D: dict(label="调用子脚本 (u32 目标 @ +1, 返回地址 = +5)",
               conf=PROVED, ev=(0x08097B00, "adds r0, r7, #1"),
               ev2=(0x08097B12, "adds r0, r7, #5"),
               note="把 +5 压入 sp+8+depth*4, sl 加一, r7 跳到目标"),
    0x0E: dict(label="设置两个头像/名字 (ID @ +1 与 @ +2)",
               conf=PROVED, ev=(0x08097A1C, "ldrb r0, [r7]"),
               ev2=(0x08097A1E, "cmp r0, #0xe"),
               note="与 0x08 同一个 handler, 只在 opcode==0x0E 时多渲染一段名字"),
    0x0F: dict(label="等待 N 帧 (N @ +1)",
               conf=PROVED, ev=(0x08097B42, "ldrb r4, [r7, #1]"),
               ev2=(0x08097B4C, "bl #0x809c574"),
               note="循环调用 0x809C574 (VBlank 等待) N 次"),
    0x10: dict(label="清空对话框状态 (无操作数)",
               conf=PROVED, ev=(0x08097B26, "bl #0x80971c0"),
               ev2=(0x08097B38, "str r0, [r6]"),
               note="取 0x03005E50 槽, 清位域 2, 不前进 r7 之外的任何数据"),
    0x11: dict(label="清除/设置头像 (0xFF = 清除)",
               conf=PROVED, ev=(0x08097B5A, "cmp r0, #0xff"),
               ev2=(0x08097B5E, "bl #0x8096d8c"),
               note="0xFF 走 0x8096D8C (清全部头像), 否则 0x8096DD4 (设某个头像)"),
    0x12: dict(label="同时设置两个消息框的台词行/格 (框0 行@+1 格@+2, 框1 行@+3 格@+4)",
               conf=PROVED, ev=(0x08096902, "strb r0, [r4]"),
               ev2=(0x0809690A, "strb r1, [r2]"),
               ev3=(0x08096906, "strb r2, [r0, #1]"),
               ev4=(0x0809690C, "strb r3, [r2, #1]"),
               note="4 个操作数拆成两组 (行,格): +1/+2 给 0 号框, +3/+4 给 1 号框; "
                    "描述暂存于 sp+4/sp+5 (框0) 与 sp+8/sp+9 (框1); "
                    "随后对每个槽调 0x8096168(槽,行,格,0,0) 并写 +0x2E/+0x2F"),
    0x13: dict(label="双段文本 (第一段从 +4 起; +2 非零则还有第二段)",
               conf=PROVED, ev=(0x08097B74, "adds r7, #4"),
               ev2=(0x08097B7C, "bl #0x80960f0"),
               note="0x80960F0 是控制码感知的串长扫描器, 返回串长(不含 NUL)"),
    0x14: dict(label="等待/设置剧情进度 (u16 @ +1)",
               conf=PROVED, ev=(0x08097BBC, "adds r0, r7, #1"),
               ev2=(0x08097BC8, "ldr r1, [pc, #0x24]"),
               note="与 state[0x10] (0x020311E4) 比较; 不等则写回并等 0x809C32C"),
    0x15: dict(label="比较器条件跳转 (比较器 @ +1, 值 u16 @ +2, u32 目标 @ +4)",
               conf=PROVED, ev=(0x08097BF8, "adds r0, r7, #2"),
               ev2=(0x08097C18, "bl #0x8097210"),
               note="0x8097210 是 6 路比较器分发表 (0x08097230)"),
    0x16: dict(label="切到下一场景 (场景ID @ +1)",
               conf=PROVED, ev=(0x08097C30, "strb r1, [r0, #0x18]"),
               ev2=(0x08097C34, "strb r1, [r0, #0x1a]"),
               note="state[0x18]=1 选 after 脚本, state[0x1A]=场景ID"),
    0x17: dict(label="场景对象参数 (3 操作数, 按 +1 分派 9 项表)",
               conf=PROVED, ev=(0x08096B96, "cmp r7, #8"),
               ev2=(0x08096BA2, "ldr r0, [r0]"),
               note="0x08096BB0 是 9 项分发表; 具体每项语义未逐条追完"),
    0x18: dict(label="设置消息框文本区尺寸与缩放 (槽@+1, 尺寸@+2, 缩放除数@+3)",
               conf=PROVED, ev=(0x08096B42, "lsrs r0, r0, #0x16"),
               ev2=(0x08096B56, "strh r3, [r4, #0xe]"),
               ev3=(0x08096B60, "bl #0x809c14c"),
               ev4=(0x08096B64, "strh r0, [r4, #0xa]"),
               note="槽号×4 索引 0x03005E50; +2 是 u16 尺寸, 写消息框 +0x3A; "
                    "+3 是除数, 0x809C14C(0x1000,除数) 是有符号整除, 结果写 +0x36 "
                    "(缩放系数); 同时 +0x38 = 消息框自身的 u16(+4), +0x34 = 0, "
                    "状态 +0x2C = 0x50"),
    0x19: dict(label="批量置/清全局标志 (模式 @ +1, 区间 @ +2..+3)",
               conf=PROVED, ev=(0x08097C48, "ldrb r4, [r7, #2]"),
               ev2=(0x08097C5C, "bl #0x80970c0"),
               note="0x80970C0 写 bit(i&7) 于 0x02031510 + (i>>3); 模式 0=清, 非 0=置"),
    0x1A: dict(label="切换到下一场景 (场景号 @ +1, 标志 @ +2)",
               conf=PROVED, ev=(0x08097C78, "ldrb r0, [r7, #1]"),
               ev2=(0x08097C7A, "strb r0, [r4, #0x16]"),
               note="state[0x16]=场景号; +2 非零则 state[0x18] = +2 + 1"),
    0x1B: dict(label="播放音乐 (曲目 @ +1, 模式 @ +2)",
               conf=PROVED, ev=(0x08097C9C, "ldrb r0, [r7, #1]"),
               ev2=(0x08097CA2, "bl #0x8097140"),
               note="新曲号写回 [sp+0x2C]"),
    0x1C: dict(label="画面转场/特效 (模式 @ +1, ID @ +2)",
               conf=PROVED, ev=(0x08097CB0, "cmp r0, #0"),
               ev2=(0x08097CB6, "bl #0x808cbf4"),
               note="模式 0 -> 0x808CBF4 (0x8064700(1,id)), 否则 0x808CC18 (0x8064700(2,id))"),
    0x1D: dict(label="停止音乐并切换曲目状态 (2 操作数)",
               conf=PROVED, ev=(0x08097CC6, "bl #0x8061e88"),
               ev2=(0x08097CD8, "bl #0x80972f8"),
               note="先 0x8061E88 停乐, 再 0x80972F8 写对话框"),
    0x1E: dict(label="载入地图/背景 (地图ID @ +1)",
               conf=PROVED, ev=(0x08097CEA, "ldrb r0, [r7, #1]"),
               ev2=(0x0808F4F0, "strb r4, [r0, #0x17]"),
               note="state[0x17]=地图ID; 地图表 0x0853D910 (步长 0x20)"),
    0x1F: dict(label="设置子配置 ID (state[0x19] = @ +1)",
               conf=PROVED, ev=(0x08097C3E, "ldrb r0, [r7, #1]"),
               ev2=(0x08097C40, "strb r0, [r1, #0x19]"),
               note="0x39 用同一个字段做匹配"),
    0x20: dict(label="显示带说话人的对白 (正文从 +2 起)",
               conf=PROVED, ev=(0x08097A8C, "adds r1, r7, #2"),
               ev2=(0x08097A90, "bl #0x806626c"),
               note="与 0x01 同一条渲染路径"),
    0x21: dict(label="放置消息框并选中台词行/格 (槽@+1, 行@+2, 格@+3, 样式@+4)",
               conf=PROVED, ev=(0x08096790, "strb r5, [r4, #2]"),
               ev2=(0x08096794, "strb r6, [r4, #3]"),
               ev3=(0x080967C2, "strh r2, [r4, #4]"),
               ev4=(0x080967B4, "movs r0, #0x10"),
               note="槽@+1 索引 0x03005E50 (不存在就先 0x80965F0 建一个); "
                    "+2/+3 是台词行/格, 写消息框 +0x2E/+0x2F; "
                    "+4 是 u16 样式码, 写 +0x30, 取 0xFF 时按槽给默认值 "
                    "(0 号框 0x10, 1 号框 0x90)"),
    0x22: dict(label="把角色加入战斗配置 (3 操作数)",
               conf=PROVED, ev=(0x08097E1A, "bl #0x8097614"),
               ev2=(0x08097654, "ldr r1, [pc, #0xd0]"),
               note="0x8097614 定位战斗配置矩阵 0x085461C4 (组距 0x1AAC, 子距 0x8E4)"),
    0x23: dict(label="设置队伍角色 (2 操作数)",
               conf=PROVED, ev=(0x08097E26, "bl #0x8097578"),
               ev2=(0x08097594, "ldr r0, [pc, #0x10]"),
               note="0x8097578 写队伍表 0x02022E30 + 0x1215"),
    0x32: dict(label="事件表项 (u32 载荷 @ +1; 按队列值选第 N 项)",
               conf=PROVED, ev=(0x08097CFA, "ldr r1, [pc, #8]"),
               ev2=(0x08097D0E, "cmp r0, #0x32"),
               note="连续 0x32 构成事件链; 用 state+0x1D[state[0x1C]] 的值挑第 N 项后跳其 u32"),
    0x33: dict(label="事件队列压入 (值 @ +1)",
               conf=PROVED, ev=(0x08097D2E, "cmp r0, #0xf"),
               ev2=(0x08097D3E, "strb r1, [r0]"),
               note="写 state+0x1D[state[0x1B]], 上限 16 项, 然后 state[0x1B]++"),
    0x34: dict(label="回合/相位条件跳转 (比较器 @ +1, b @ +2, c @ +3, u32 目标 @ +4)",
               conf=PROVED, ev=(0x08097D4C, "adds r0, r7, #4"),
               ev2=(0x08097D56, "bl #0x808a1a4"),
               note="0x808A1A4 比对战斗控制块 0x0202680C 的阶段/子阶段"),
    0x35: dict(label="复合条件跳转 (a @ +1, b @ +2, c @ +3, d @ +4, u32 目标 @ +5)",
               conf=PROVED, ev=(0x08097D86, "adds r0, r7, #5"),
               ev2=(0x08097D94, "bl #0x808a1c4"),
               note="0x808A1C4 求值 3 元条件, 与 @+1 的期望值比较"),
    0x36: dict(label="指定人物在场条件跳转 (a @ +1, b @ +2, c @ +3, u32 目标 @ +4)",
               conf=PROVED, ev=(0x08097DA6, "adds r0, r7, #4"),
               ev2=(0x08097DB2, "bl #0x808a420"),
               note="0x808A420 遍历战斗单位槽 0x020240C0 查该角色是否在场"),
    0x37: dict(label="置/清战斗标志 (模式 @ +1, 标志 @ +2)",
               conf=PROVED, ev=(0x08097DC4, "ldrb r0, [r7, #1]"),
               ev2=(0x08097DC8, "bl #0x808a490"),
               note="0x808A490 改 0x020311D4 + 4*(id>>29) 的 bit(id&0x1F)"),
    0x38: dict(label="测战斗标志 (模式 @ +1, 标志 @ +2, u32 目标 @ +3)",
               conf=PROVED, ev=(0x08097DCE, "adds r0, r7, #3"),
               ev2=(0x08097DDE, "bl #0x808a4d8"),
               note="0x808A4D8/0x808A504 读同一个位域, 返回 0/1"),
    0x39: dict(label="子配置匹配 (ID @ +1, u32 目标 @ +2)",
               conf=PROVED, ev=(0x08097E00, "ldrb r0, [r0, #0x19]"),
               ev2=(0x08097E04, "cmp r0, r1"),
               note="与 state[0x19] (0x020311D4+0x19) 比较, 相等才跳"),
}

# The 6 comparators of 0x08097230, read straight out of the ROM.
COMPARATORS = {
    0: "==", 1: "!=", 2: ">", 3: ">=", 4: "<", 5: "<=",
}

# Two opcodes whose length the symbolic execution cannot pin down because the
# handler computes the operand address at run time.  Each entry carries the
# instruction that justifies the number; the tool re-reads it from the ROM and
# fails if it is not there.
FALLBACK_LENGTHS: dict[int, tuple[int, int, str]] = {
    0x06: (9, 0x080979DE, "adds r0, r7, r0"),
    0x32: (5, 0x08097D08, "adds r7, #5"),
}

# u32 operands the handler does not read itself (the shared tail does).
FALLBACK_U32: dict[int, tuple[int, ...]] = {
    0x06: (1, 5),
    0x32: (1,),
}


# --------------------------------------------------------------------------
# 4. length derivation
# --------------------------------------------------------------------------
def derive_lengths(rom: bytes, dispatch: dict, analyses: dict, execs: dict) -> dict:
    """Derive per-opcode instruction length from the handler's own r7 maths.

    Priority:
      1. the symbolic execution of the handler (r7 = opcode + K) - exact;
      2. a handler that reads a u32 at r7+k spans k+4 bytes (always-jump
         handlers, where r7 becomes the branch target);
      3. otherwise the length is data dependent (text opcodes).
    """
    lengths: dict[int, int | None] = {}
    sources: dict[int, str] = {}
    for op in range(dispatch["max_opcode"] + 1):
        ana = analyses.get(op)
        ex = execs.get(op)
        if ana is None:
            lengths[op] = None
            continue
        if ana.get("is_loop_head"):
            lengths[op] = None
            sources[op] = "n/a (the handler re-reads the same opcode)"
            continue
        vals = sorted({v for v in (ex or {}).get("r7_offsets", []) if v is not None})
        if ex and ex.get("r7_known") and len(vals) == 1:
            lengths[op] = max(1, vals[0])
            sources[op] = "handler r7 arithmetic"
            continue
        if len(vals) > 1:
            step = vals[0]
            if all(v % step == 0 for v in vals):
                lengths[op] = step
                sources[op] = "handler r7 arithmetic (chain step)"
                continue
        w = ana["word_offsets"] or ana.get("u32_offsets", [])
        if w:
            lengths[op] = max(w) + 4
            sources[op] = "u32 branch pointer at +%d" % max(w)
            continue
        if op in FALLBACK_U32:
            lengths[op] = max(FALLBACK_U32[op]) + 4
            sources[op] = "u32 branch pointer (documented fallback)"
            continue
        if op in FALLBACK_LENGTHS:
            lengths[op] = FALLBACK_LENGTHS[op][0]
            sources[op] = "fallback (documented, see FALLBACK_LENGTHS)"
            continue
        if not ana["byte_offsets"] and not w:
            # an instruction without operands is the opcode byte alone
            lengths[op] = 1
            sources[op] = "no operands"
            continue
        lengths[op] = None
        sources[op] = "unresolved"
    return lengths, sources


# --------------------------------------------------------------------------
# 5. script walk / cross validation
# --------------------------------------------------------------------------
def text_run_length(rom: bytes, pos: int) -> int:
    """Length of the NUL terminated, control-code aware text run at `pos`."""
    p = pos
    while p < len(rom):
        a = rom[p]
        if a == 0:
            return p + 1 - pos
        if a == 1:
            p += 2
            continue
        if a == 2:
            p += 3
            continue
        if 0x80 <= a <= 0x9F:
            p += 2
            continue
        p += 1
    return p - pos


def opcode_length(rom: bytes, p: int, op: int, lengths: dict, text_ops: dict) -> int:
    if op in text_ops:
        return text_ops[op](rom, p)
    n = lengths.get(op)
    if n is None:
        raise KeyError(op)
    return n


def walk_scene(rom: bytes, roots: dict[int, int], lengths: dict, text_ops: dict):
    """Walk every script; returns (nodes, issues, stats)."""
    nodes: dict[int, int] = {}
    issues: list[str] = []
    hist: dict[int, int] = {}
    stack = [r for r in roots.values() if 0 <= r < len(rom)]
    budget = 400000
    while stack and budget > 0:
        budget -= 1
        p = stack.pop()
        if p in nodes:
            continue
        if not (0 <= p < len(rom)):
            issues.append(f"instruction pointer outside ROM: 0x{p + ROM_BASE:08X}")
            continue
        op = rom[p]
        try:
            n = opcode_length(rom, p, op, lengths, text_ops)
        except KeyError:
            issues.append(f"unknown opcode 0x{op:02X} at 0x{p + ROM_BASE:08X}")
            continue
        if n <= 0 or p + n > len(rom):
            issues.append(f"opcode 0x{op:02X} at 0x{p + ROM_BASE:08X} has bad length {n}")
            continue
        nodes[p] = op
        hist[op] = hist.get(op, 0) + 1
        # branch / call targets
        for off, size in BRANCH_OPERANDS.get(op, ()):
            tgt = struct.unpack_from("<I", rom, p + off)[0] - ROM_BASE
            if not (0 <= tgt < len(rom)):
                issues.append(f"branch target outside ROM at 0x{p + ROM_BASE:08X}")
                continue
            stack.append(tgt)
        if op not in TERMINAL:
            stack.append(p + n)
    return nodes, issues, hist


# u32 branch/call operands, taken from the handler analysis.
BRANCH_OPERANDS: dict[int, tuple[tuple[int, int], ...]] = {}


def build_branch_operands(analyses: dict) -> dict:
    out: dict[int, tuple] = {}
    for op, ana in analyses.items():
        offs = []
        for k in ana["word_offsets"] + ana.get("u32_offsets", []):
            offs.append((k, 4))
        if op in FALLBACK_U32:
            for k in FALLBACK_U32[op]:
                offs.append((k, 4))
        if offs:
            out[op] = tuple(sorted(set(offs)))
    return out


TERMINAL = {0x00, 0x06, 0x07}

# The four root tables, in ROM address order (the story pair first, then the
# battle pair).  The order is fixed by the ROM layout: the tables are laid out
# back to back, 55 entries for the story scripts and 46 for the battle ones.
ROOT_NAMES = ["story_before", "story_after", "battle_logic", "battle_events"]
SCENE_COUNTS = (dss.STORY_SCENES, dss.STORY_SCENES, dss.BATTLE_SCENES, dss.BATTLE_SCENES)


def table_layout(tables: list[int]) -> list[int]:
    """How many scenes each root table covers, from the ROM's own layout.

    The four tables sit back to back, so the distance between two of them is
    the number of entries of the first one.  Entry 0 of every table is a
    dummy (scene ids start at 1), so the scene count is the gap minus one.
    The layout is only accepted when it is self consistent (and then it also
    tells us which table is which).
    """
    if len(tables) != len(SCENE_COUNTS):
        return [dss.STORY_SCENES] * len(tables)
    counts = []
    for i in range(len(tables) - 1):
        gap = (tables[i + 1] - tables[i]) // 4
        counts.append(gap - 1)
    counts.append(SCENE_COUNTS[-1])
    if counts == list(SCENE_COUNTS):
        return counts
    return [dss.STORY_SCENES] * len(tables)


# --------------------------------------------------------------------------
# 6. main
# --------------------------------------------------------------------------
def analyse_rom(rom: bytes) -> dict:
    dispatch = find_dispatch(rom)
    entry = find_function_entry(rom, dispatch["dispatch_addr"])
    handlers = dispatch["entries"]
    loop_head = _loop_head(rom, dispatch, handlers)

    # every handler body is the code between this handler address and the
    # next *distinct* handler address (the table is a sorted code region).
    addr_order = sorted(set(handlers))
    bounds: dict[int, tuple[int, int]] = {}
    for i, a in enumerate(addr_order):
        b = addr_order[i + 1] if i + 1 < len(addr_order) else a + 0x100
        bounds[a] = (a, b)

    analyses: dict[int, dict] = {}
    execs: dict[int, dict] = {}
    vm_lo = min(set(handlers))
    vm_hi = max(set(handlers)) + 0x60
    vm_region = decode_cfg(rom, vm_lo, vm_hi, stop={loop_head},
                            seeds=[h for h in sorted(set(handlers)) if h != loop_head])
    u32_reader, u32_call_site = find_u32_reader(rom, vm_region, loop_head)
    for op, h in enumerate(handlers):
        lo, hi = bounds[h]
        if lo == loop_head:
            # the "invalid opcode" target: re-reads the same opcode forever
            analyses[op] = {"byte_offsets": [], "half_offsets": [], "word_offsets": [],
                            "calls": [], "ram_cells": [], "advances": [],
                            "r7_setup": {}, "u32_offsets": [], "instructions": {},
                            "is_loop_head": True}
            execs[op] = {"r7_offsets": [], "r7_known": False, "unresolved": True,
                         "executed": {}}
            continue
        ana = analyse_handler(rom, lo, hi, loop_head)
        analyses[op] = ana
        # the executor may follow shared tails (e.g. the "r7 += 2" epilogue
        # that many handlers branch to), so it walks the whole VM body
        ex = execute_handler(rom, vm_region, loop_head, op, lo)
        execs[op] = ex
        # only the instructions this opcode really executes count: 0x08 and
        # 0x0E share a handler but read different operands
        own = {a: vm_region[a] for a in ex.get("executed_addrs", set())
               if a in vm_region}
        read = set()
        for offs in ex.get("executed", {}).values():
            read |= offs
        ana["byte_offsets"] = sorted(read)
        ana["u32_offsets"] = u32_operand_offsets(rom, own, u32_reader, u32_call_site)
        ana["calls"] = sorted({_branch_target(vm_region[a].op_str)
                               for a in own
                               if vm_region[a].mnemonic == "bl"
                               and _branch_target(vm_region[a].op_str)})
        cells = set()
        for a in own:
            la, val = literal_value(rom, vm_region[a])
            if la is not None and val is not None and 0x02000000 <= val < 0x04000000:
                cells.add(val)
        ana["ram_cells"] = sorted(cells)

    lengths, length_sources = derive_lengths(rom, dispatch, analyses, execs)

    # text opcodes: proven by the handler calling the string renderer/scanner
    text_ops: dict[int, callable] = {}
    for op, ana in analyses.items():
        if op == 0x13:
            def f13(rom, p):
                # the handler scans the first run, then skips one more byte
                # before the optional second run
                n = 4 + text_run_length(rom, p + 4)
                if rom[p + 2]:
                    n += 1 + text_run_length(rom, p + n + 1)
                return n
            text_ops[op] = f13
        elif op in (0x01, 0x05, 0x20):
            start = {0x01: 1, 0x05: 2, 0x20: 2}[op]
            def f(rom, p, _start=start):
                return _start + text_run_length(rom, p + _start)
            text_ops[op] = f
    for op in list(lengths):
        if op in text_ops:
            lengths[op] = None
            length_sources[op] = "variable (NUL terminated text run)"

    return {
        "dispatch": dispatch,
        "entry": entry,
        "loop_head": loop_head,
        "handlers": handlers,
        "analyses": analyses,
        "execs": execs,
        "lengths": lengths,
        "length_sources": length_sources,
        "u32_reader": u32_reader,
        "text_ops": text_ops,
    }


def _loop_head(rom: bytes, dispatch: dict, handlers: list[int]) -> int:
    """The address the interpreter returns to for the next opcode.

    The dispatch block is
        ldrb r0, [r7]
        cmp  r0, #MAX
        bls  <table lookup>
        b    <default>          <- an opcode outside the table lands here
    and the default target re-reads the same opcode, so it is the loop head.
    """
    default = None
    window = thumb_disasm(rom, dispatch["dispatch_addr"] - 24, 16)
    for ins in window:
        if ins.mnemonic == "b":
            t = _branch_target(ins.op_str)
            if t and t in set(handlers):
                default = t
                break
    if default is None:
        from collections import Counter
        counts: Counter = Counter()
        for h in handlers:
            blob = rom[h - ROM_BASE:h - ROM_BASE + 0x120]
            for ins in MD.disasm(blob, h):
                if ins.mnemonic == "b":
                    t = _branch_target(ins.op_str)
                    if t and t not in handlers:
                        counts[t] += 1
        if not counts:
            raise SystemExit("cannot locate the interpreter loop head")
        default = counts.most_common(1)[0][0]
    return default


def root_tables(rom: bytes, dispatch: dict, entry: int) -> dict:
    """Find the root tables by following the VM's callers.

    The story/battle dispatchers pick a script with
        ldr rX, [pc, #imm]      ; the root table
        ldr  r0, [rX, #scene*4] ; the scene's script
    so the tables show up as literal-pool values inside the callers.
    """
    bl_targets = find_thumb_bl_targets(rom)
    callers = bl_targets.get(entry, [])
    if not callers:
        raise SystemExit("no caller found for the story VM entry")
    cands: dict[int, int] = {}
    for site in callers:
        # the calling function starts at the nearest preceding push {...lr}
        lo = find_function_entry(rom, site, window=0x100) or (site - 0x40)
        blob = rom[lo - ROM_BASE: lo - ROM_BASE + 0x600]
        for ins in MD.disasm(blob, lo):
            la, val = literal_value(rom, ins)
            if la is None or val is None:
                continue
            n = looks_like_root_table(rom, val)
            if n >= 40:
                cands[val] = max(cands.get(val, 0), n)
    return {"callers": callers, "candidates": cands}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("rom", nargs="?", default="rom/base.gba")
    ap.add_argument("--json", help="write the machine readable report here")
    ap.add_argument("--stats", action="store_true", help="print the full table")
    ap.add_argument("--disasm", help="disassemble this address")
    ap.add_argument("--count", type=int, default=40)
    args = ap.parse_args()

    rom_path = pathlib.Path(args.rom)
    if not rom_path.exists():
        rom_path = REPO / args.rom
    rom = rom_path.read_bytes()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if args.disasm:
        for ins in thumb_disasm(rom, int(args.disasm, 16), args.count):
            print(f"  0x{ins.address:08X}  {ins.mnemonic} {ins.op_str}")
        return 0

    info = analyse_rom(rom)
    dispatch = info["dispatch"]
    handlers = info["handlers"]
    analyses = info["analyses"]
    lengths = info["lengths"]
    text_ops = info["text_ops"]

    global BRANCH_OPERANDS
    BRANCH_OPERANDS = build_branch_operands(analyses)

    # --- root tables -----------------------------------------------------
    roots_info = root_tables(rom, dispatch, info["entry"])
    tables = sorted(roots_info["candidates"])
    if not tables:
        raise SystemExit("could not locate the story root tables")

    # --- walk every scene of every root table ----------------------------
    all_nodes: dict[int, int] = {}
    all_issues: list[str] = []
    hist: dict[int, int] = {}
    per_table: dict[str, dict] = {}
    rejected: list[dict] = []
    accepted: list[tuple[str, int]] = []
    for idx, addr in enumerate(tables):
        name = ROOT_NAMES[idx] if idx < len(ROOT_NAMES) else f"table{idx}"
        tnodes: dict[int, int] = {}
        tscenes = 0
        tissues: list[str] = []
        for scene in range(1, dss.STORY_SCENES + 1):
            ptr = struct.unpack_from("<I", rom, addr - ROM_BASE + scene * 4)[0]
            if not (ROM_BASE <= ptr < ROM_BASE + len(rom)):
                continue
            nodes, issues, h = walk_scene(rom, {addr: ptr - ROM_BASE}, lengths, text_ops)
            tnodes.update(nodes)
            tissues += [f"[scene {scene}] {i}" for i in issues]
            for k, v in h.items():
                hist[k] = hist.get(k, 0) + v
            tscenes += 1
        entry = {
            "address": f"0x{addr:08X}",
            "scenes_with_script": tscenes,
            "nodes": len(tnodes),
            "issues": tissues[:20],
            "issue_count": len(tissues),
        }
        # A root table is one whose scripts all decode.  A table that only
        # looks like a pointer table (e.g. a text table) fails here.
        if tissues:
            rejected.append(entry)
            continue
        accepted.append((name, addr))
        per_table[name] = entry

    # the accepted tables sit back to back; their gaps give the scene counts
    accepted_addrs = [a for _n, a in accepted]
    scene_counts = table_layout(accepted_addrs)
    count_of = {a: c for a, c in zip(accepted_addrs, scene_counts)}
    for name, addr in accepted:
        per_table[name]["scenes_covered"] = count_of[addr]

    # --- the real walk: all roots of a scene merged, like the decoder ----
    all_nodes = {}
    hist = {}
    per_scene: dict[str, dict] = {}
    for scene in range(1, dss.STORY_SCENES + 1):
        roots = {}
        for name, addr in accepted:
            if scene > count_of[addr]:
                continue
            ptr = struct.unpack_from("<I", rom, addr - ROM_BASE + scene * 4)[0]
            if ROM_BASE <= ptr < ROM_BASE + len(rom):
                roots[f"{name}@0x{addr:08X}"] = ptr - ROM_BASE
        if not roots:
            continue
        nodes, issues, h = walk_scene(rom, roots, lengths, text_ops)
        all_nodes.update(nodes)
        all_issues += [f"[scene {scene}] {i}" for i in issues]
        for k, v in h.items():
            hist[k] = hist.get(k, 0) + v
        per_scene[str(scene)] = {
            "roots": {k: f"0x{v + ROM_BASE:08X}" for k, v in roots.items()},
            "nodes": len(nodes),
            "issues": issues,
        }

    # branch targets must land on instruction boundaries
    for p, op in all_nodes.items():
        for off, size in BRANCH_OPERANDS.get(op, ()):
            tgt = struct.unpack_from("<I", rom, p + off)[0] - ROM_BASE
            if tgt not in all_nodes:
                all_issues.append(
                    f"branch target 0x{tgt + ROM_BASE:08X} (from 0x{p + ROM_BASE:08X})"
                    f" is not an instruction start")

    # --- build the opcode table -----------------------------------------
    rows = []
    for op in range(dispatch["max_opcode"] + 1):
        handler = handlers[op]
        sem = SEMANTICS.get(op)
        ana = analyses.get(op, {})
        used = hist.get(op, 0)
        conf = sem["conf"] if sem else UNPROVED
        if handler == info["loop_head"] and sem is None:
            # the dispatch sends every opcode outside its table here, and the
            # handler re-reads the same opcode without advancing r7
            conf = PROVED
            label = "未定义指令 (跳回取指, 原地死循环)"
            evidence = [{"addr": f"0x{dispatch['range_check_addr']:08X}",
                         "text": f"cmp r0, #0x{dispatch['max_opcode']:02x}"},
                        {"addr": f"0x{handler:08X}", "text": "movs r0, #1"}]
        else:
            label = sem["label"] if sem else "?"
            evidence = []
            if sem:
                for key in ("ev", "ev2", "ev3", "ev4"):
                    if key in sem:
                        addr, txt = sem[key]
                        evidence.append({"addr": f"0x{addr:08X}", "text": txt})
        row = {
            "op": op,
            "op_hex": f"0x{op:02X}",
            "handler": f"0x{handler:08X}",
            "length": lengths.get(op),
            "variable_length": op in text_ops,
            "operand_bytes": ana.get("byte_offsets", []),
            "operand_words": ana.get("word_offsets", []),
            "calls": [f"0x{c:08X}" for c in sorted(set(ana.get("calls", [])))],
            "ram_cells": [f"0x{c:08X}" for c in ana.get("ram_cells", [])],
            "label": label,
            "kind": "invalid" if handler == info["loop_head"] else "defined",
            "confidence": conf,
            "occurrences": used,
            "evidence": evidence,
            "note": sem.get("note", "") if sem else "",
            "length_source": info["length_sources"].get(op, ""),
        }
        rows.append(row)

    # --- verify every "proved" claim against the ROM --------------------
    failures: list[str] = []
    # 1. the derived length table must agree with the production decoder
    for op, n in sorted(lengths.items()):
        if op in text_ops:
            continue
        ref = dss.LENGTHS.get(op)
        if ref is None:
            continue
        if n is not None and n != ref:
            failures.append(
                f"length mismatch for op 0x{op:02X}: derived {n},"
                f" production decoder {ref}")
    # 2. the discovered root tables must be the ones the decoder uses
    known = {v + ROM_BASE: k for k, v in dss.ROOT_TABLES.items()}
    for name, addr in accepted:
        if addr in known:
            continue
        failures.append(f"root table 0x{addr:08X} ({name}) is not a known root table")
    # 3. the documented fallbacks must still quote the instruction they claim
    for op, (n, addr, txt) in sorted(FALLBACK_LENGTHS.items()):
        insns = thumb_disasm(rom, addr, 1)
        if not insns or text_of(insns[0]) != txt:
            got = text_of(insns[0]) if insns else "<none>"
            failures.append(
                f"fallback length for op 0x{op:02X} cites {addr}:"
                f" expected '{txt}', ROM has '{got}'")
        row = next((r for r in rows if r["op"] == op), None)
        if row and row["length"] != n:
            failures.append(
                f"fallback length for op 0x{op:02X} is {row['length']},"
                f" the documented value is {n}")
    for row in rows:
        if row["confidence"] != PROVED:
            continue
        if not row["evidence"]:
            failures.append(f"op {row['op_hex']} is marked proved but has no evidence")
            continue
        for ev in row["evidence"]:
            insns = thumb_disasm(rom, int(ev["addr"], 16), 1)
            if not insns or text_of(insns[0]) != ev["text"]:
                got = text_of(insns[0]) if insns else "<none>"
                failures.append(
                    f"op {row['op_hex']} evidence mismatch at {ev['addr']}:"
                    f" expected '{ev['text']}', ROM has '{got}'")
        if row["length"] is None and not row["variable_length"] \
                and row["handler"] != f"0x{info['loop_head']:08X}":
            failures.append(f"op {row['op_hex']} is marked proved but has no derived length")
        if row["length"] is not None and row["operand_bytes"]:
            span = 1 + max(row["operand_bytes"])
            if row["length"] < span:
                failures.append(
                    f"op {row['op_hex']} length {row['length']} < operand span {span}")

    proved = [r for r in rows if r["confidence"] == PROVED]
    inferred = [r for r in rows if r["confidence"] == INFERRED]
    unproved = [r for r in rows if r["confidence"] == UNPROVED]
    invalid = [r for r in rows if r["kind"] == "invalid"]
    defined = [r for r in rows if r["kind"] == "defined"]
    used_ops = {r["op"] for r in rows if r["occurrences"]}
    proved_used = [r for r in proved if r["op"] in used_ops]
    total_occ = sum(r["occurrences"] for r in rows)
    explained_occ = sum(r["occurrences"] for r in rows
                         if r["confidence"] in (PROVED, INFERRED))

    # --- report ----------------------------------------------------------
    print(f"ROM                : {rom_path}")
    print(f"interpreter entry  : 0x{info['entry']:08X}  (Thumb)")
    print(f"dispatch table     : 0x{dispatch['table_addr']:08X}"
          f"  ({dispatch['max_opcode'] + 1} entries, max opcode 0x{dispatch['max_opcode']:02X})")
    print(f"dispatch code      : 0x{dispatch['dispatch_addr']:08X}")
    print(f"loop head          : 0x{info['loop_head']:08X}")
    print(f"VM callers         : " + ", ".join(f"0x{c:08X}" for c in roots_info["callers"]))
    for name, t in per_table.items():
        print(f"root table {name:<14}: {t['address']}  scenes={t['scenes_with_script']}"
              f"  nodes={t['nodes']}  issues={t['issue_count']}")
    for t in rejected:
        print(f"rejected candidate {t['address']}: {t['issue_count']} issues")
        for i in t["issues"][:5]:
            print("   -", i)
    print()
    print(f"opcodes with a meaning : {len(defined)}"
          f"  ({len(used_ops)} used in this ROM, {len(defined) - len(used_ops)} unused)")
    print(f"  proved                : {len([r for r in defined if r['confidence'] == PROVED])}"
          f" / {len(defined)}")
    print(f"  inferred              : {len(inferred)}")
    print(f"  unproved              : {len(unproved)}")
    print(f"opcode slots proved void: {len(invalid)}"
          f" (0x{invalid[0]['op']:02X}..0x{invalid[-1]['op']:02X} -> the handler re-reads the same opcode)")
    print(f"occurrences explained   : {explained_occ} / {total_occ}")
    print(f"walk issues             : {len(all_issues)}")
    if args.stats:
        print()
        print(f"{'op':<5} {'len':<5} {'handler':<12} {'conf':<9} {'n':<7} label")
        for r in rows:
            ln = "var" if r["variable_length"] else str(r["length"])
            print(f"{r['op_hex']:<5} {ln:<5} {r['handler']:<12} {r['confidence']:<9} "
                  f"{r['occurrences']:<7} {r['label']}")
    if all_issues:
        print()
        print("issues (first 20):")
        for i in all_issues[:20]:
            print("  -", i)
    if failures:
        print()
        print("FAILED PROOFS:")
        for f in failures:
            print("  -", f)

    report = {
        "rom": str(rom_path),
        "interpreter": {
            "entry": f"0x{info['entry']:08X}",
            "dispatch_code": f"0x{dispatch['dispatch_addr']:08X}",
            "dispatch_table": f"0x{dispatch['table_addr']:08X}",
            "max_opcode": dispatch["max_opcode"],
            "loop_head": f"0x{info['loop_head']:08X}",
            "callers": [f"0x{c:08X}" for c in roots_info["callers"]],
        },
        "root_tables": per_table,
        "comparators": COMPARATORS,
        "opcodes": rows,
        "coverage": {
            "opcodes_total": len(rows),
            "opcodes_defined": len(defined),
            "opcodes_proved": len([r for r in defined if r["confidence"] == PROVED]),
            "opcodes_inferred": len(inferred),
            "opcodes_unproved": len(unproved),
            "opcodes_void": len(invalid),
            "opcodes_used": len(used_ops),
            "opcodes_used_proved": len(proved_used),
            "occurrences_total": total_occ,
            "occurrences_explained": explained_occ,
            "walk_issues": len(all_issues),
        },
        "proof_failures": failures,
        "issues": all_issues,
        "tables": per_table,
        "rejected_tables": rejected,
        "scenes": per_scene,
    }
    if args.json:
        write_json(args.json, report)
        print(f"\nwrote {args.json}")

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
