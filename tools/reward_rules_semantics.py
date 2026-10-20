#!/usr/bin/env python3
"""Battle reward-tail byte and win/lose rule types 2/3 — static semantics.

This tool re-derives everything from the ROM; no address in it is trusted
because it was written down by hand.  For each target it

  1. finds the ARM/Thumb literal pools that hold the table pointers,
  2. finds the ``ldr rX, [pc, #imm]`` instructions that consume those pools,
  3. reads the consumer's own instruction stream to recover the record
     stride, the index formula and the dispatch tables,
  4. prints the exact instructions that implement the semantics,
  5. cross-tabulates the ROM data against the recovered semantics,
  6. exits non-zero when a recovered claim does not hold on the data.

Usage:
    python tools/reward_rules_semantics.py rom/base.gba
    python tools/reward_rules_semantics.py rom/base.gba --json build/reward_rules.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import mechanism_map as mm  # noqa: E402
from tools.lib.io import write_json  # noqa: E402

ROM_BASE = 0x08000000

# Table addresses that the audit asks about.  They are the *inputs* of the
# search; every code address used below is discovered at run time.
REWARD_TABLE = 0x59EAE0
RULES_TABLE = 0x594758
MISSION_INDEX = 0x348DAC
CONFIG_MATRIX = 0x5461C4
CONFIG_STRIDE = 0x1AAC
CONFIG_SUB_STRIDE = 0x8E4
ACTOR_SLOT = 0xB8
BATTLE_STAGES = 46
SUBS = 3

# --- reward entry layout (24 bytes) ----------------------------------------
#: The reward record.  ``+0x00``/``+0x02``/``+0x04`` are three u16 head
#: fields, ``+0x06..+0x15`` are eight 2-byte tail slots and ``+0x16..+0x17``
#: are zero in every shipped entry (their meaning stays unknown).
REWARD_STRIDE = 24
REWARD_HEAD_FIELDS = (
    # (offset, size, key, meaning, evidence)
    (0x00, 2, "gold", "金币 u16（直接写进结算结构体）",
     "0x080893FC ldrh r0,[r1] / 0x08089400 strh r0,[r5]"),
    (0x02, 2, "upgrade_points",
     "强化点 u16（与 byte[0x0202680C] 比较通过后才发放）",
     "0x0808940C ldrh r0,[r1,#2] / 0x0808940E strh r0,[r5,#2]"),
    (0x04, 2, "tier",
     "档位/门槛 u16（与 byte[0x0202680C] 比较）",
     "0x08089406 ldrh r2,[r1,#4] / 0x08089408 cmp r0,r2"),
)
#: The eight tail slots start at +0x06; each slot is (category tag, item id).
REWARD_TAIL_OFFSET = 0x06
REWARD_TAIL_SLOTS = 8
#: +0x16 / +0x17 are never read by any consumer and are zero everywhere.
REWARD_TAIL_END = REWARD_TAIL_OFFSET + REWARD_TAIL_SLOTS * 2
REWARD_RESERVED = (0x16, 0x17)

#: The 4-entry pointer table that maps the category tag to the name table.
#: 0x0808A02A loads it and indexes it with the tail byte, so it is the
#: authoritative "tag -> name table" map (independent of the four arms).
REWARD_CATEGORY_TABLE = 0x59F5E0
REWARD_CATEGORY_COUNT = 4
REWARD_CATEGORY_NAMES = ("忍具", "强化素材", "认识卡", "技术")

#: Byte-level guards: the conclusions rest on this exact code.
ROM_LAYOUT_CHECKS = (
    (0x0809731E, "012c", "0x0809731E 奖励类别分派的第一条 cmp r4,#1"),
    (0x0808A02A, "224ab800", "0x0808A02A 载入类别->名字表指针表 0x0859F5E0"),
    (0x08089FA4, "e0ea5908", "0x08089FA4 奖励表字面量 0x0859EAE0"),
)

# Fields of the rules entry that are needed for the cross-tabulation.
RULE_STRIDE = 0xCC
RULE_SUB_STRIDE = 0x44
RULE_GROUPS = 2
RULES_PER_GROUP = 4
RULE_SIZE = 8


# --------------------------------------------------------------------------
# capstone plumbing
# --------------------------------------------------------------------------
def make_disassembler(mode):
    capstone = mm.load_capstone()
    md = capstone.Cs(capstone.CS_ARCH_ARM, mode)
    md.detail = False
    return md


def disassemble(rom: bytes, md, start: int, count: int) -> list:
    off = start - ROM_BASE
    if off < 0 or off >= len(rom):
        return []
    return list(md.disasm(rom[off:off + count * 4 + 8], start))


def literal_target(rom: bytes, insn) -> int | None:
    """Address of the literal pool slot an ``ldr rX, [pc, #imm]`` reads."""
    if insn.mnemonic != "ldr" or "[pc" not in insn.op_str:
        return None
    try:
        imm = int(insn.op_str.split("#")[1].split("]")[0].strip(), 0)
    except (IndexError, ValueError):
        return None
    return ((insn.address + 4) & ~3) + imm


def literal_value(rom: bytes, insn) -> int | None:
    addr = literal_target(rom, insn)
    if addr is None:
        return None
    off = addr - ROM_BASE
    if not (0 <= off <= len(rom) - 4):
        return None
    return struct.unpack_from("<I", rom, off)[0]


def insns_between(rom: bytes, md, start: int, stop: int) -> list:
    """Instructions from ``start`` up to (not including) ``stop``."""
    if stop <= start:
        return []
    return disassemble(rom, md, start, (stop - start) // 2 + 4)


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------
def find_literal_pools(rom: bytes, value: int) -> list[int]:
    """File offsets of every u32 equal to ``value`` (ARM literal pools)."""
    pat = struct.pack("<I", value)
    out = []
    off = 0
    while True:
        i = rom.find(pat, off)
        if i < 0:
            break
        out.append(i)
        off = i + 1
    return out


def find_ldr_users(rom: bytes, md, pool_addr: int) -> list[int]:
    """Thumb instructions that load the u32 stored at ``pool_addr``."""
    md.skipdata = True
    users = []
    for insn in md.disasm(rom, ROM_BASE):
        if insn.mnemonic != "ldr" or "[pc" not in insn.op_str:
            continue
        if literal_target(rom, insn) == pool_addr:
            users.append(insn.address)
    return users


def derive_stride(rom: bytes, md, ldr_addr: int, table_reg: str) -> int | None:
    """Recover the record stride from the consumer's own index arithmetic.

    The reward consumers compute ``index * 3`` then ``<< k``; we look for the
    generic ``lsls rX, rY, #1`` / ``adds rX, rX, rY`` / ``lsls rZ, rX, #k``
    shape and report the resulting multiplier ``3 << k``.
    """
    seq = disassemble(rom, md, ldr_addr - 32, 48)
    for i in range(len(seq) - 2):
        a, b, c = seq[i], seq[i + 1], seq[i + 2]
        if a.mnemonic != "lsls" or b.mnemonic != "adds" or c.mnemonic != "lsls":
            continue
        a_parts = [p.strip() for p in a.op_str.split(",")]
        b_parts = [p.strip() for p in b.op_str.split(",")]
        c_parts = [p.strip() for p in c.op_str.split(",")]
        if len(a_parts) < 3 or len(b_parts) < 3 or len(c_parts) < 3:
            continue
        if a_parts[2] != "#1":
            continue
        if b_parts[0] != b_parts[1]:
            continue
        if b_parts[2] != a_parts[1]:
            continue
        if c_parts[1] != b_parts[0]:
            continue
        try:
            shift = int(c_parts[2].lstrip("#"), 0)
        except ValueError:
            continue
        return 3 << shift
    return None


def nearby_literal_load(rom: bytes, start: int, end: int, value: int) -> bool:
    """Is there a pc-relative LDR literal instruction reading ``value``?

    The scan works on raw halfwords because a linear sweep over the whole
    ROM can drift out of instruction alignment.
    """
    for off in range(max(0, start - ROM_BASE), min(len(rom) - 2, end - ROM_BASE), 2):
        hw = struct.unpack_from("<H", rom, off)[0]
        if not (0x4800 <= hw <= 0x4FFF):
            continue
        imm8 = hw & 0xFF
        addr = ROM_BASE + off
        literal = ((addr + 4) & ~3) + imm8 * 4
        lo = literal - ROM_BASE
        if not (0 <= lo <= len(rom) - 4):
            continue
        if struct.unpack_from("<I", rom, lo)[0] == value:
            return True
    return False


def find_rule_dispatch(rom: bytes, md, rules_value: int) -> dict | None:
    """Locate the win/lose rule dispatch and its jump table.

    Shape searched for (Thumb):
        ldr rX, [rX] ; mov pc, rX        (jump through the table entry)
        adds rX, rX, rY                  (rX = table_base + index*4)
        ldr rY, [pc, #imm]               (rY = table_base)
        lsls rX, rX, #2                  (index * 4)
        cmp  rX, #N ; subs rX, #1        (index = type - 1)
    The site must also sit close to a load of the rules table pointer, which
    keeps unrelated code elsewhere in the ROM from matching.
    """
    # prefilter on the raw halfword of "ldr r0, [r0]" (0x6800)
    needle = struct.pack("<H", 0x6800)
    off = 0
    while True:
        off = rom.find(needle, off)
        if off < 0:
            break
        if off % 2 == 0:
            addr = ROM_BASE + off
            seq = disassemble(rom, md, addr - 16, 14)
            by_addr = {insn.address: insn for insn in seq}
            load = by_addr.get(addr)
            if load is None or load.mnemonic != "ldr" \
                    or load.op_str.strip() != "r0, [r0]":
                off += 2
                continue
            jump = by_addr.get(addr + 2)
            if jump is None or jump.mnemonic not in ("mov", "movs", "bx"):
                off += 2
                continue
            if jump.mnemonic == "bx" and not jump.op_str.endswith(", r0"):
                off += 2
                continue
            if jump.mnemonic != "bx" and not jump.op_str.endswith("pc, r0"):
                off += 2
                continue
            add = by_addr.get(addr - 2)
            ptr = by_addr.get(addr - 4)
            scale = by_addr.get(addr - 6)
            if not (add and ptr and scale):
                off += 2
                continue
            if add.mnemonic != "adds":
                off += 2
                continue
            add_parts = [p.strip() for p in add.op_str.split(",")]
            if len(add_parts) < 3 or add_parts[0] != add_parts[1]:
                off += 2
                continue
            if ptr.mnemonic != "ldr" or "[pc" not in ptr.op_str:
                off += 2
                continue
            if scale.mnemonic != "lsls" or scale.op_str.strip() != "r0, r0, #2":
                off += 2
                continue
            # the index must be built as "type - 1" and range checked
            cmp_ins = None
            subs = None
            for back in range(8, 17, 2):
                probe = by_addr.get(addr - back)
                if probe is None:
                    continue
                if cmp_ins is None and probe.mnemonic == "cmp":
                    cmp_ins = probe
                if subs is None and probe.mnemonic in ("subs", "sub") \
                        and probe.op_str.endswith("#1"):
                    subs = probe
                if cmp_ins is not None and subs is not None:
                    break
            if cmp_ins is None or subs is None:
                off += 2
                continue
            table_base = literal_value(rom, ptr)
            if table_base is None or not (ROM_BASE <= table_base < ROM_BASE + len(rom)):
                off += 2
                continue
            if not nearby_literal_load(rom, addr - 0x300, addr + 0x300, rules_value):
                off += 2
                continue
            entries = []
            ok = True
            for k in range(9):
                eoff = table_base + k * 4 - ROM_BASE
                if not (0 <= eoff <= len(rom) - 4):
                    ok = False
                    break
                target = struct.unpack_from("<I", rom, eoff)[0]
                if not (ROM_BASE <= target < ROM_BASE + len(rom)):
                    ok = False
                    break
                entries.append(target)
            if not ok:
                off += 2
                continue
            return {
                "dispatch_addr": addr + 2,
                "table_addr": table_base,
                "arms": {t + 1: entries[t] for t in range(9)},
                "index_expr": "%s ; %s" % (subs.op_str, cmp_ins.op_str),
            }
        off += 2
    return None


def arm_window(rom: bytes, md, arms: dict, key) -> list:
    """Instructions of one dispatch arm, bounded by the next arm.

    The arms are laid out back to back, so the next arm's address is the
    end of this one; without that bound a short arm would swallow the
    instructions of the arm that follows it.
    """
    if key not in arms:
        return []
    start = arms[key]
    later = [v for k, v in arms.items() if v > start]
    end = min(later) if later else start + 0x100
    seq = disassemble(rom, md, start, max(2, (end - start) // 2))
    return [insn for insn in seq if insn.address < end]


def find_four_way_dispatch(rom: bytes, md, func_addr: int):
    """Find a 4-way dispatch (compare one register against 0/1/2/3) inside a
    function.  Returns ``(head_address, register)`` or ``(None, None)``."""
    seq = disassemble(rom, md, func_addr, 90)
    for i, insn in enumerate(seq):
        if insn.mnemonic != "cmp" or "#1" not in insn.op_str:
            continue
        reg = insn.op_str.split(",")[0].strip()
        values = set()
        for w in seq[i:i + 12]:
            if w.mnemonic == "cmp" and w.op_str.startswith(reg + ","):
                try:
                    values.add(int(w.op_str.split("#")[1].strip(), 0))
                except ValueError:
                    pass
        if {0, 1, 2, 3} <= values:
            return insn.address, reg
    return None, None


def find_reward_dispatcher(rom: bytes, md, users: list[int]):
    """Find the function the reward consumer calls with (tail_byte, id).

    A candidate must be a ``bl`` target inside the consumer and its own body
    must contain a 4-way dispatch.  The call site must also load the two
    arguments with ``ldrb`` out of the reward record.
    """
    md.skipdata = True
    found = []
    for addr in users:
        seq = disassemble(rom, md, addr, 400)
        for i, insn in enumerate(seq):
            if insn.mnemonic not in ("bl", "blx") or not insn.op_str.startswith("#"):
                continue
            try:
                target = int(insn.op_str.split("#")[1], 0)
            except ValueError:
                continue
            head, reg = find_four_way_dispatch(rom, md, target)
            if head is None:
                continue
            # the two arguments must be byte loads right before the call
            arg0 = arg1 = None
            if i >= 2:
                arg0 = seq[i - 2]
                arg1 = seq[i - 1]
            found.append({
                "call_site": insn.address,
                "func": target,
                "head": head,
                "reg": reg,
                "arg0": arg0.op_str if arg0 else None,
                "arg1": arg1.op_str if arg1 else None,
                "ldrb_args": bool(arg0 and arg1
                                  and arg0.mnemonic == "ldrb"
                                  and arg1.mnemonic == "ldrb"),
            })
    # prefer a call site that loads both arguments as bytes
    for entry in found:
        if entry["ldrb_args"]:
            return entry
    return found[0] if found else None


def emulate_dispatch(rom: bytes, md, head: int, reg: str, value: int):
    """Follow the dispatch block with ``reg`` bound to ``value``.

    The block is the run of compare/branch instructions that starts at
    ``head``; a branch that leaves that run lands on the arm body, and that
    address is the answer.
    """
    branch_ops = {"cmp", "beq", "bne", "bgt", "bge", "blt", "ble",
                  "bhi", "bls", "bcc", "bcs", "b"}
    cluster = []
    for insn in disassemble(rom, md, head, 48):
        if insn.mnemonic not in branch_ops:
            break
        cluster.append(insn)
    table = {insn.address: insn for insn in cluster}
    pc = head
    eq = None
    gt = None
    for _ in range(80):
        if pc not in table:
            return pc if pc > head else None
        insn = table[pc]
        op = insn.mnemonic
        args = insn.op_str
        nxt = pc + 2
        if op == "cmp" and args.startswith(reg + ","):
            try:
                imm = int(args.split("#")[1].strip(), 0)
            except (IndexError, ValueError):
                imm = 0
            eq = (value == imm)
            gt = (value > imm)
        elif op == "beq" and eq is not None:
            if eq:
                nxt = int(args.split("#")[1], 0)
        elif op == "bne" and eq is not None:
            if not eq:
                nxt = int(args.split("#")[1], 0)
        elif op == "bgt" and gt is not None:
            if gt:
                nxt = int(args.split("#")[1], 0)
        elif op in ("bge", "ble", "blt", "bhi", "bls", "bcc", "bcs") and eq is not None:
            nxt = int(args.split("#")[1], 0)
        elif op == "b" and args.startswith("#"):
            nxt = int(args.split("#")[1], 0)
        else:
            return None
        pc = nxt
    return None


# --------------------------------------------------------------------------
# table readers
# --------------------------------------------------------------------------
def read_name_table(rom: bytes, base: int, mapping, limit: int = 160) -> list[str]:
    """Decode a ROM pointer table of names (entry 0 included)."""
    out = []
    for i in range(limit):
        off = base + i * 4 - ROM_BASE
        if not (0 <= off <= len(rom) - 4):
            break
        ptr = struct.unpack_from("<I", rom, off)[0] - ROM_BASE
        if not (0 <= ptr < len(rom)):
            break
        text, _ = mm_text(rom, ptr, mapping)
        if not text:
            break
        out.append(text.replace("\n", "").strip())
    return out


def mm_text(rom: bytes, ptr: int, mapping):
    import konoha_font as kf
    return kf.decode_at(rom, ptr, mapping)


def reward_index(rom: bytes, stage: int, sub: int) -> int:
    return rom[MISSION_INDEX + stage] + sub


def reward_entry_count(rom: bytes) -> int:
    """Number of reward records the mission index table can address.

    ``index = MISSION_INDEX[stage] + sub`` with stage 1..46 and sub 0..2.
    The indices are contiguous, so the table holds ``max(index)+1`` records.
    """
    indices = []
    for stage in range(1, BATTLE_STAGES + 1):
        for sub in range(SUBS):
            indices.append(reward_index(rom, stage, sub))
    return max(indices) + 1


def table_capacity(rom: bytes, base: int, limit: int = 512) -> int:
    """Number of consecutive ROM text pointers at the *ROM address* ``base``."""
    count = 0
    start = base - ROM_BASE
    for i in range(limit):
        off = start + i * 4
        if off < 0 or off + 4 > len(rom):
            break
        ptr = struct.unpack_from("<I", rom, off)[0]
        if not (ROM_BASE <= ptr < ROM_BASE + len(rom)):
            break
        count += 1
    return count


def category_name_table(rom: bytes, category: int) -> int | None:
    """The name table the ROM's category->name-table pointer table selects."""
    off = REWARD_CATEGORY_TABLE + category * 4
    if off + 4 > len(rom):
        return None
    value = struct.unpack_from("<I", rom, off)[0]
    if not (ROM_BASE <= value < ROM_BASE + len(rom)):
        return None
    return value


def parse_reward_record(rom: bytes, idx: int, stride: int) -> dict:
    """One 24-byte reward record with every field named."""
    off = REWARD_TABLE + idx * stride
    rec = rom[off:off + stride]
    out = {"index": idx, "offset": off}
    for rel, size, key, meaning, evidence in REWARD_HEAD_FIELDS:
        value = rec[rel] if size == 1 else int.from_bytes(rec[rel:rel + 2], "little")
        out[key] = {"value": value, "meaning": meaning, "evidence": evidence}
    slots = []
    for k in range(REWARD_TAIL_SLOTS):
        base = REWARD_TAIL_OFFSET + k * 2
        if base + 2 > len(rec):
            break
        tag = rec[base]
        item = rec[base + 1]
        slots.append({
            "slot": k,
            "offset": base,
            "category_tag": tag,
            "item_id": item,
            "empty": tag == 0 and item == 0,
        })
    out["slots"] = slots
    out["reserved"] = {f"0x{r:02X}": rec[r] for r in REWARD_RESERVED
                       if r < len(rec)}
    return out


def analyse_reward_domains(rom: bytes, mapping, stride: int,
                            arm_info: dict) -> dict:
    """Per-category value domain of the reward ids vs the name table capacity.

    Every reward record is read, the eight tail slots are grouped by their
    category tag, and each group's id domain is compared against the number
    of entries the matching name table actually holds.
    """
    count = reward_entry_count(rom)
    records = [parse_reward_record(rom, i, stride) for i in range(count)]

    categories: dict[int, dict] = {}
    for rec in records:
        for slot in rec["slots"]:
            if slot["empty"]:
                continue
            tag = slot["category_tag"]
            cell = categories.setdefault(tag, {
                "category": tag,
                "name": (REWARD_CATEGORY_NAMES[tag]
                         if tag < len(REWARD_CATEGORY_NAMES) else "?"),
                "slots": 0,
                "ids": set(),
                "slot_positions": Counter(),
                "records": set(),
            })
            cell["slots"] += 1
            cell["ids"].add(slot["item_id"])
            cell["slot_positions"][slot["slot"]] += 1
            cell["records"].add(rec["index"])

    out = []
    for tag in sorted(categories):
        cell = categories[tag]
        table = category_name_table(rom, tag)
        arm_table = arm_info.get(tag, {}).get("name_table") if isinstance(arm_info, dict) else None
        capacity = table_capacity(rom, table) if table else 0
        ids = sorted(cell["ids"])
        inside = [i for i in ids if i < capacity]
        outside = [i for i in ids if i >= capacity]
        out.append({
            "category": tag,
            "name": cell["name"],
            "slots": cell["slots"],
            "records": len(cell["records"]),
            "distinct_ids": len(ids),
            "id_min": ids[0] if ids else None,
            "id_max": ids[-1] if ids else None,
            "id_domain": ids,
            "name_table": table,
            "name_table_from_arm": arm_table,
            "name_table_agrees_with_arm": (table == arm_table),
            "name_table_capacity": capacity,
            "ids_inside_capacity": len(inside),
            "ids_outside_capacity": outside,
            "slot_position_histogram": dict(sorted(cell["slot_positions"].items())),
        })

    # categories the ROM's dispatch supports but the shipped data never uses
    unused = []
    for tag in range(REWARD_CATEGORY_COUNT):
        if tag in categories:
            continue
        table = category_name_table(rom, tag)
        unused.append({
            "category": tag,
            "name": REWARD_CATEGORY_NAMES[tag],
            "name_table": table,
            "name_table_capacity": table_capacity(rom, table) if table else 0,
            "slots": 0,
        })

    reserved = Counter()
    for rec in records:
        for value in rec["reserved"].values():
            reserved[value] += 1

    return {
        "entry_count": count,
        "table_end": REWARD_TABLE + count * stride,
        "records": records,
        "categories": out,
        "unused_categories": unused,
        "reserved_byte_histogram": {str(k): v for k, v in sorted(reserved.items())},
    }


def reward_entry(rom: bytes, idx: int, stride: int) -> bytes:
    """One reward record.  ``REWARD_TABLE`` is a *file* offset."""
    off = REWARD_TABLE + idx * stride
    return rom[off:off + stride]


def reward_slots(entry: bytes, stride: int) -> list[tuple[int, int]]:
    """(low_byte, high_byte) of every non-empty tail slot."""
    out = []
    for k in range((stride - 6) // 2):
        lo = entry[6 + k * 2]
        hi = entry[7 + k * 2]
        if lo == 0 and hi == 0:
            break
        out.append((lo, hi))
    return out


def rules_entries(rom: bytes) -> list[dict]:
    """Every (stage, sub, group, index, type, a, b, c) rule with content."""
    out = []
    for stage in range(1, BATTLE_STAGES + 1):
        for sub in range(SUBS):
            base = RULES_TABLE + stage * RULE_STRIDE + sub * RULE_SUB_STRIDE
            if base + RULE_SUB_STRIDE > len(rom):
                continue
            for g in range(RULE_GROUPS):
                for i in range(RULES_PER_GROUP):
                    q = base + 4 + g * 32 + i * RULE_SIZE
                    rtype = rom[q]
                    if rtype == 0:
                        continue
                    out.append({
                        "stage": stage, "sub": sub, "group": g, "index": i,
                        "type": rtype, "a": rom[q + 1], "b": rom[q + 2],
                        "c": rom[q + 3],
                        "text_ptr": struct.unpack_from("<I", rom, q + 4)[0],
                        "turn_limit": rom[base],
                    })
    return out


def stage_actors(rom: bytes, stage: int, sub: int) -> list[dict]:
    base = CONFIG_MATRIX + stage * CONFIG_STRIDE + sub * CONFIG_SUB_STRIDE
    out = []
    for i in range(12):
        q = base + 4 + i * ACTOR_SLOT
        cid = rom[q]
        if not cid:
            continue
        out.append({"slot": i, "id": cid, "side": rom[q + 1]})
    return out


# --------------------------------------------------------------------------
# analysis
# --------------------------------------------------------------------------
def analyse_reward(rom: bytes, md, mapping) -> dict:
    value = ROM_BASE + REWARD_TABLE
    pools = find_literal_pools(rom, value)
    users = []
    for pool in pools:
        for addr in find_ldr_users(rom, md, ROM_BASE + pool):
            users.append(addr)
    users.sort()

    strides = []
    for addr in users:
        s = derive_stride(rom, md, addr, "r2")
        if s:
            strides.append({"ldr": addr, "stride": s})
    stride = strides[0]["stride"] if strides else 24
    stride_sources = strides

    # index formula: mission index table is loaded in the same neighbourhood
    mission_users = []
    for pool in find_literal_pools(rom, ROM_BASE + MISSION_INDEX):
        mission_users.extend(find_ldr_users(rom, md, ROM_BASE + pool))

    # the dispatcher of the tail byte: a 4-way dispatch reached from the
    # reward consumer with (tail_byte, id) as arguments
    call = find_reward_dispatcher(rom, md, users)
    dispatcher = call["head"] if call else None
    reg = call["reg"] if call else None
    arms: dict = {}
    if dispatcher is not None:
        for v in (0, 1, 2, 3):
            target = emulate_dispatch(rom, md, dispatcher, reg, v)
            if target is not None:
                arms[v] = target

    arm_info = {}
    for value_id, arm_addr in sorted(arms.items()):
        seq = arm_window(rom, md, arms, value_id)
        rom_literals = []
        for insn in seq:
            val = literal_value(rom, insn)
            if val is not None and ROM_BASE <= val < ROM_BASE + len(rom):
                rom_literals.append({"at": insn.address, "value": val})
        # a name table is a pointer table whose entries are ROM text pointers
        name_table = None
        for lit in rom_literals:
            off = lit["value"] - ROM_BASE
            ok = 0
            for i in range(4):
                if off + i * 4 + 4 > len(rom):
                    break
                p = struct.unpack_from("<I", rom, off + i * 4)[0]
                if ROM_BASE <= p < ROM_BASE + len(rom):
                    ok += 1
            if ok >= 3:
                name_table = lit["value"]
                break
        arm_info[value_id] = {
            "arm_addr": arm_addr,
            "name_table": name_table,
            "rom_literals": rom_literals,
            "instructions": [
                f"0x{insn.address:08X}: {insn.mnemonic:<7} {insn.op_str}"
                for insn in seq[:34]
            ],
        }

    # data cross-tabulation
    rows = []
    for stage in range(1, BATTLE_STAGES + 1):
        for sub in range(SUBS):
            idx = reward_index(rom, stage, sub)
            entry = reward_entry(rom, idx, stride)
            slots = reward_slots(entry, stride)
            rows.append({
                "stage": stage, "sub": sub, "index": idx,
                "gold": entry[0] | entry[1] << 8,
                "bonus": entry[2] | entry[3] << 8,
                "tier": entry[4] | entry[5] << 8,
                "slots": [{"tail_byte": lo, "id": hi} for lo, hi in slots],
            })

    crosstab: dict[int, dict] = {}
    for row in rows:
        for slot in row["slots"]:
            tb = slot["tail_byte"]
            cell = crosstab.setdefault(tb, {
                "count": 0, "ids": set(), "stages": set(),
                "id_in_name_table": 0, "id_out_of_range": [],
            })
            cell["count"] += 1
            cell["ids"].add(slot["id"])
            cell["stages"].add(row["stage"])
    for tb, cell in crosstab.items():
        table = arm_info.get(tb, {}).get("name_table")
        cell["stages"] = sorted(cell["stages"])
        if table:
            names = read_name_table(rom, table, mapping)
            limit = len(names)
            cell["name_table"] = table
            cell["name_table_size"] = limit
            cell["name_table_sample"] = names[:6]
            for i in cell["ids"]:
                if 0 <= i < limit:
                    cell["id_in_name_table"] += 1
                else:
                    cell["id_out_of_range"].append(i)
            cell["ids"] = sorted(cell["ids"])
            cell["id_out_of_range"] = sorted(cell["id_out_of_range"])
        else:
            cell["ids"] = sorted(cell["ids"])

    # slot position of the tail byte per category
    slot_hist: dict[int, dict] = {}
    for row in rows:
        for k, slot in enumerate(row["slots"]):
            cell = slot_hist.setdefault(slot["tail_byte"], {})
            cell[k] = cell.get(k, 0) + 1

    return {
        "table": REWARD_TABLE,
        "literal_pools": [ROM_BASE + p for p in pools],
        "consumer_ldrs": users,
        "stride": stride,
        "stride_sources": stride_sources,
        "mission_index_users": mission_users,
        "dispatcher": dispatcher,
        "arms": arm_info,
        "rows": rows,
        "crosstab": crosstab,
        "slot_position_hist": slot_hist,
        "domains": analyse_reward_domains(rom, mapping, stride, arm_info),
    }


def analyse_rules(rom: bytes, md, mapping) -> dict:
    value = ROM_BASE + RULES_TABLE
    pools = find_literal_pools(rom, value)
    users = []
    for pool in pools:
        users.extend(find_ldr_users(rom, md, ROM_BASE + pool))
    users.sort()

    dispatch = find_rule_dispatch(rom, md, value)
    arms = dispatch["arms"] if dispatch else {}

    rules = rules_entries(rom)
    by_type: dict[int, list] = {}
    for r in rules:
        by_type.setdefault(r["type"], []).append(r)

    # cross-tabulation for types 2 and 3: (a,b) must name an actor of the stage
    detail = {}
    for t in (2, 3):
        rows = []
        for r in by_type.get(t, []):
            actors = stage_actors(rom, r["stage"], r["sub"])
            match = [a for a in actors if a["id"] == r["b"]]
            side_match = [a for a in match if a["side"] == r["a"]]
            ptr = r["text_ptr"] - ROM_BASE
            text = ""
            if 0 <= ptr < len(rom):
                text, _ = mm_text(rom, ptr, mapping)
                text = text.replace("\n", "/").strip()
            rows.append({
                "stage": r["stage"], "sub": r["sub"], "group": r["group"],
                "index": r["index"], "a": r["a"], "b": r["b"], "c": r["c"],
                "turn_limit": r["turn_limit"],
                "b_is_actor": bool(match),
                "a_matches_actor_side": bool(side_match),
                "actors": actors,
                "text": text,
            })
        arm_seq = arm_window(rom, md, arms, t)
        # the dispatch stores the address of the rule record in r5
        rule_reads = []
        state_reads = []
        for insn in arm_seq:
            if insn.mnemonic in ("ldrb", "ldrh", "ldr") and "[r5" in insn.op_str:
                rule_reads.append(f"0x{insn.address:08X}: {insn.mnemonic} {insn.op_str}")
            val = literal_value(rom, insn)
            if val is not None and 0x02000000 <= val < 0x04000000:
                state_reads.append({"at": insn.address, "value": val})
        detail[t] = {
            "rows": rows,
            "total": len(rows),
            "b_is_actor": sum(1 for x in rows if x["b_is_actor"]),
            "a_matches_side": sum(1 for x in rows if x["a_matches_actor_side"]),
            "arm": arms.get(t),
            "rule_field_reads": rule_reads,
            "state_reads": state_reads,
            "arm_instructions": [
                f"0x{insn.address:08X}: {insn.mnemonic:<7} {insn.op_str}"
                for insn in arm_seq
            ],
        }

    # pairing: every type-2 row must have a type-3 twin with the same (a,b)
    t2 = {(r["stage"], r["sub"], r["a"], r["b"]) for r in detail[2]["rows"]}
    t3 = {(r["stage"], r["sub"], r["a"], r["b"]) for r in detail[3]["rows"]}
    pairing = {
        "type2_rows": len(t2),
        "type3_rows": len(t3),
        "type2_with_type3_twin": len(t2 & t3),
        "type2_only": sorted(t2 - t3),
        "type3_only": sorted(t3 - t2),
    }

    return {
        "table": RULES_TABLE,
        "literal_pools": [ROM_BASE + p for p in pools],
        "consumer_ldrs": users,
        "dispatch": dispatch,
        "arms": arms,
        "type_histogram": {t: len(v) for t, v in sorted(by_type.items())},
        "detail": detail,
        "pairing": pairing,
    }


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def validate(reward: dict, rules: dict, rom: bytes | None = None) -> list[str]:
    problems = []

    # 0. the native code the conclusions rest on must be byte-identical
    if rom is not None:
        for addr, expect, what in ROM_LAYOUT_CHECKS:
            got = rom[addr - ROM_BASE:addr - ROM_BASE + len(expect) // 2].hex()
            if got != expect:
                problems.append(
                    f"ROM layout mismatch at 0x{addr:08X}: expected {expect}, "
                    f"got {got} ({what})")

    # 1. the record stride must be 24 for every consumer that computes one
    for src in reward["stride_sources"]:
        if src["stride"] != 24:
            problems.append(
                f"reward consumer at 0x{src['ldr']:08X} implies stride "
                f"{src['stride']}, expected 24")
    if not reward["stride_sources"]:
        problems.append("no reward consumer found for the reward table pointer")
    if reward["stride"] != 24:
        problems.append(f"reward stride {reward['stride']} != 24")

    # 2. the tail byte must be dispatched 0..3 and each arm must own a
    #    distinct name table
    arm_ids = sorted(k for k in reward["arms"] if isinstance(k, int))
    if arm_ids != [0, 1, 2, 3]:
        problems.append(f"tail byte arms recovered {arm_ids}, expected [0,1,2,3]")
    tables = [reward["arms"].get(a, {}).get("name_table") for a in arm_ids]
    if len(set(tables)) != len(tables) or any(t is None for t in tables):
        problems.append(f"tail byte arms do not map to distinct name tables: {tables}")

    # 3. every tail byte value seen in the data must be one of the arms, and
    #    every id must resolve inside its category's name table
    for tb, cell in reward["crosstab"].items():
        if tb not in reward["arms"]:
            problems.append(f"tail byte {tb} has no dispatch arm")
            continue
        if "name_table" in cell:
            if cell["id_in_name_table"] != len(cell["ids"]):
                problems.append(
                    f"category {tb}: {len(cell['ids']) - cell['id_in_name_table']}"
                    f"/{len(cell['ids'])} ids fall outside the category name table")

    # 4. the rule arms for types 2 and 3 must exist and be distinct
    arms = rules["arms"]
    if arms.get(2) is None or arms.get(3) is None:
        problems.append("rule type 2/3 arms were not recovered")
    elif arms[2] == arms[3]:
        problems.append("rule type 2 and 3 share an arm, expected distinct code")

    # 5. rule.b must name an actor and rule.a must be that actor's side
    for t in (2, 3):
        d = rules["detail"][t]
        if d["total"] and d["b_is_actor"] != d["total"]:
            problems.append(
                f"rule type {t}: only {d['b_is_actor']}/{d['total']} rows have "
                f"rule.b among the stage actors")
        if d["total"] and d["a_matches_side"] != d["total"]:
            problems.append(
                f"rule type {t}: only {d['a_matches_side']}/{d['total']} rows have "
                f"rule.a equal to the actor side")

    # 6. every type-2 row must have a type-3 twin with the same (a,b)
    pairing = rules["pairing"]
    if pairing["type2_rows"] and \
            pairing["type2_with_type3_twin"] != pairing["type2_rows"]:
        problems.append(
            f"only {pairing['type2_with_type3_twin']}/{pairing['type2_rows']} "
            f"type-2 rows have a type-3 twin with the same (a,b)")

    # 7. type 3 must read the rule fields (a = side, b = character id) while
    #    type 2 must not - that asymmetry is the core finding
    t3_reads = rules["detail"][3]["rule_field_reads"]
    t2_reads = rules["detail"][2]["rule_field_reads"]
    if len(t3_reads) < 2:
        problems.append(
            f"rule type 3 arm reads the rule record only {len(t3_reads)} time(s); "
            f"expected it to read rule.a and rule.b")
    if t2_reads:
        problems.append(
            f"rule type 2 arm reads the rule record at {t2_reads}; the shipped "
            f"arm was expected to ignore rule.a/rule.b")

    # 8. the ROM's own category -> name table pointer table must agree with
    #    the four dispatch arms, and every category's id domain must fit
    domains = reward.get("domains")
    if not domains:
        problems.append("reward domain analysis did not run")
        return problems

    if domains["entry_count"] != 112:
        problems.append(
            f"reward table holds {domains['entry_count']} records, expected 112")

    for cat in domains["categories"]:
        tag = cat["category"]
        if not cat["name_table"]:
            problems.append(f"category {tag} has no name table in the pointer table")
            continue
        if not cat["name_table_agrees_with_arm"]:
            problems.append(
                f"category {tag}: the pointer table says "
                f"0x{cat['name_table']:08X} but the dispatch arm uses "
                f"{cat['name_table_from_arm']}")
        if cat["ids_outside_capacity"]:
            problems.append(
                f"category {tag} ({cat['name']}): ids "
                f"{cat['ids_outside_capacity']} fall outside the "
                f"{cat['name_table_capacity']}-entry name table")
        if cat["id_min"] is not None and cat["id_max"] is not None:
            if cat["id_max"] >= cat["name_table_capacity"]:
                problems.append(
                    f"category {tag}: id domain {cat['id_min']}..{cat['id_max']} "
                    f"does not fit the {cat['name_table_capacity']}-entry table")

    for cat in domains["unused_categories"]:
        if not cat["name_table"]:
            problems.append(
                f"category {cat['category']} has no name table but the "
                f"dispatcher supports it")

    # 9. the two bytes after the eight tail slots are zero everywhere
    for value, count in domains["reserved_byte_histogram"].items():
        if int(value) != 0:
            problems.append(
                f"reward records have non-zero reserved bytes "
                f"({count} record(s) with 0x{value}); the layout assumption "
                f"that +0x16/+0x17 are unused no longer holds")

    return problems


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def print_reward(report: dict) -> None:
    print("=" * 78)
    print("1. BATTLE REWARD TABLE 0x%06X" % report["table"])
    print("=" * 78)
    print("literal pools holding the table pointer : %s" %
          ", ".join("0x%08X" % p for p in report["literal_pools"]))
    print("consumer ldr instructions                : %s" %
          ", ".join("0x%08X" % a for a in report["consumer_ldrs"]))
    print("record stride recovered from the code    : %d bytes" % report["stride"])
    for src in report["stride_sources"]:
        print("    0x%08X -> index*3 << %d = %d" %
              (src["ldr"], (src["stride"] // 3).bit_length() - 1, src["stride"]))
    print("mission index table consumers            : %s" %
          ", ".join("0x%08X" % a for a in report["mission_index_users"]))
    print()
    print("-- consumer instruction window (index formula + tail byte read) --")
    md = report["_md"]
    rom = report["_rom"]
    for addr in report["consumer_ldrs"]:
        print("   [0x%08X]" % addr)
        for insn in disassemble(rom, md, addr - 12, 14):
            mark = "=>" if insn.address == addr else "  "
            extra = ""
            val = literal_value(rom, insn)
            if val is not None:
                extra = "   ; =0x%08X" % val
            print("   %s 0x%08X: %-8s %-26s%s" %
                  (mark, insn.address, insn.mnemonic, insn.op_str, extra))
        print()
    if report["dispatcher"]:
        print("-- tail byte dispatcher at 0x%08X --" % report["dispatcher"])
        for insn in disassemble(rom, md, report["dispatcher"], 26):
            extra = ""
            val = literal_value(rom, insn)
            if val is not None:
                extra = "   ; =0x%08X" % val
            print("      0x%08X: %-8s %-26s%s" %
                  (insn.address, insn.mnemonic, insn.op_str, extra))
        print()
    for tb in sorted(k for k in report["arms"] if isinstance(k, int)):
        arm = report["arms"][tb]
        print("-- tail byte %d -> arm 0x%08X  name table %s --" %
              (tb, arm["arm_addr"],
               "0x%08X" % arm["name_table"] if arm["name_table"] else "n/a"))
        for line in arm["instructions"][:26]:
            print("      " + line)
        print()
    print("-- cross tabulation: tail byte x category name table --")
    print("%-6s %-8s %-10s %-14s %-24s %s" %
          ("byte", "count", "id-range", "name-table", "sample", "ids-out-of-table"))
    for tb in sorted(report["crosstab"]):
        cell = report["crosstab"][tb]
        ids = cell["ids"]
        rng = "%d..%d" % (min(ids), max(ids)) if ids else "-"
        print("%-6d %-8d %-10s %-14s %-24s %s" %
              (tb, cell["count"], rng,
               ("0x%08X" % cell["name_table"]) if "name_table" in cell else "n/a",
               ",".join(cell.get("name_table_sample", [])[:3]),
               cell.get("id_out_of_range", [])))
    print()
    print("-- slot position histogram (tail byte value -> slot index) --")
    for tb in sorted(report["slot_position_hist"]):
        hist = report["slot_position_hist"][tb]
        print("   tail byte %d: %s" % (tb, dict(sorted(hist.items()))))
    print()

    domains = report.get("domains")
    if domains:
        print("-- reward entry layout (24 bytes) --")
        for rel, size, key, meaning, evidence in REWARD_HEAD_FIELDS:
            print("   +0x%02X %-16s %s" % (rel, key, meaning))
            print("        %s" % evidence)
        print("   +0x%02X..+0x%02X %-16s 每个槽 2 字节: 低字节=类别标签, 高字节=物品 id"
              % (REWARD_TAIL_OFFSET, REWARD_TAIL_END - 1, "tail_slots[8]"))
        print("        证据: 0x08089EA2 ldrb r0,[r0,#7] (高字节=id, 0 表示列表结束)")
        print("              0x08089EC6/0x08089ECA ldrb (低字节) -> cmp #2 (类别判定)")
        print("              0x08089F86 ldrb r0,[r5] -> bl 0x80972f8 dispatch(标签, id)")
        print("   +0x%02X..+0x%02X %-16s 全部 112 条均为 0，语义未解"
              % (REWARD_RESERVED[0], REWARD_RESERVED[1], "reserved"))
        print()
        print("-- per-category value domain vs name table capacity --")
        print("   奖励表 %d 条 (0x%06X..0x%06X), 步长 %d" % (
            domains["entry_count"], report["table"],
            domains["table_end"] - 1, report["stride"]))
        print("%-6s %-10s %-8s %-14s %-12s %-14s %-8s %s" %
              ("类别", "名称", "槽位数", "id 范围", "id 个数", "名字表", "容量", "越界 id"))
        for cat in domains["categories"]:
            rng = ("%d..%d" % (cat["id_min"], cat["id_max"])
                   if cat["id_min"] is not None else "-")
            print("%-6d %-10s %-8d %-14s %-12d 0x%08X %-8d %s" % (
                cat["category"], cat["name"], cat["slots"], rng,
                cat["distinct_ids"], cat["name_table"] or 0,
                cat["name_table_capacity"],
                cat["ids_outside_capacity"] or "无"))
        for cat in domains["unused_categories"]:
            print("%-6d %-10s %-8d %-14s %-12s 0x%08X %-8d %s" % (
                cat["category"], cat["name"], 0, "-", "-",
                cat["name_table"] or 0, cat["name_table_capacity"],
                "本 ROM 数据未使用"))
        print()
        print("   类别->名字表指针表 0x%08X (0x0808A02A 载入, 用尾字节做下标):"
              % (ROM_BASE + REWARD_CATEGORY_TABLE))
        for tag in range(REWARD_CATEGORY_COUNT):
            table = category_name_table(report["_rom"], tag)
            names = read_name_table(report["_rom"], table,
                                    report.get("_mapping"), limit=8) if table else []
            print("      [%d] %-8s -> 0x%08X (%d 条) %s" % (
                tag, REWARD_CATEGORY_NAMES[tag], table or 0,
                table_capacity(report["_rom"], table) if table else 0,
                " / ".join(names[:3])))
        print()


def print_rules(report: dict) -> None:
    print("=" * 78)
    print("2. BATTLE WIN/LOSE CONDITION TABLE 0x%06X" % report["table"])
    print("=" * 78)
    print("literal pools holding the table pointer : %s" %
          ", ".join("0x%08X" % p for p in report["literal_pools"]))
    print("consumer ldr instructions                : %s" %
          ", ".join("0x%08X" % a for a in report["consumer_ldrs"]))
    disp = report["dispatch"]
    if disp:
        print("dispatch site                           : 0x%08X" % disp["dispatch_addr"])
        print("jump table base                         : 0x%08X" % disp["table_addr"])
        print("type -> arm                             : %s" %
              ", ".join("%d->0x%08X" % (t, a) for t, a in sorted(report["arms"].items())))
    print("rule type histogram                     : %s" % report["type_histogram"])
    print()
    for t in (2, 3):
        d = report["detail"][t]
        print("-- rule type %d  (arm 0x%08X) --" %
              (t, d["arm"] if d["arm"] else 0))
        print("   rows=%d  rule.b is a stage actor: %d/%d   rule.a == actor side: %d/%d" %
              (d["total"], d["b_is_actor"], d["total"],
               d["a_matches_side"], d["total"]))
        print("   rule-field reads in the arm : %s" %
              (d["rule_field_reads"] or "none (the arm ignores rule.a/rule.b)"))
        print("   WRAM constants in the arm    : %s" %
              ([hex(s["value"]) for s in d["state_reads"]] or "none"))
        for line in d["arm_instructions"][:48]:
            print("      " + line)
        print()
        print("   %-4s %-4s %-5s %-3s %-3s %-3s %-8s %-22s %s" %
              ("stg", "sub", "group", "a", "b", "c", "turnlim", "actor hit", "text"))
        for row in d["rows"]:
            hits = ",".join("slot%d:side%d" % (a["slot"], a["side"])
                            for a in row["actors"] if a["id"] == row["b"]) or "-"
            print("   %-4d %-4d %-5d %-3d %-3d %-3d %-8d %-22s %s" %
                  (row["stage"], row["sub"], row["group"], row["a"], row["b"],
                   row["c"], row["turn_limit"], hits, row["text"]))
        print()
    pairing = report["pairing"]
    print("-- type 2 / type 3 pairing (same stage/sub and same (a,b)) --")
    print("   type-2 distinct rows            : %d" % pairing["type2_rows"])
    print("   type-3 distinct rows            : %d" % pairing["type3_rows"])
    print("   type-2 rows with a type-3 twin  : %d" % pairing["type2_with_type3_twin"])
    if pairing["type2_only"]:
        print("   type-2 without twin             : %s" % pairing["type2_only"])
    if pairing["type3_only"]:
        print("   type-3 without twin             : %s" % pairing["type3_only"])
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rom", nargs="?", default=None)
    ap.add_argument("--json", default=None, help="write a machine readable report")
    args = ap.parse_args()

    rom_path = pathlib.Path(args.rom) if args.rom else (REPO / "rom" / "base.gba")
    rom = rom_path.read_bytes()
    md = make_disassembler(mm.load_capstone().CS_MODE_THUMB)

    import konoha_font as kf
    mapping, _ = kf.build_mapping(rom)

    reward = analyse_reward(rom, md, mapping)
    rules = analyse_rules(rom, md, mapping)
    reward["_rom"] = rom
    reward["_md"] = md
    reward["_mapping"] = mapping

    problems = validate(reward, rules, rom)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    print_reward(reward)
    print_rules(rules)

    print("=" * 78)
    if problems:
        print("SELF-CHECK FAILED:")
        for p in problems:
            print("   - %s" % p)
    else:
        print("SELF-CHECK PASSED: every recovered claim holds on the ROM data")
    print("=" * 78)

    if args.json:
        clean_reward = {k: v for k, v in reward.items() if not k.startswith("_")}
        clean_rules = {k: v for k, v in rules.items() if not k.startswith("_")}
        payload = {
            "rom": str(rom_path),
            "reward": clean_reward,
            "rules": clean_rules,
            "self_check_problems": problems,
        }
        out = write_json(args.json, payload)
        print("wrote %s" % out)

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
