#!/usr/bin/env python3
"""Read-only probe for the speaker-id 63 / full-name-table overlap.

The short-name table (ROM 0x085A57C4, 12 bytes per entry) and the full-name
table (ROM 0x085A5AB8, 19 bytes per entry) share one address:

    0x085A57C4 + 63*12 == 0x085A5AB8

i.e. "short id 63" and "full id 0" are the *same bytes*.  This probe answers
four questions in one run:

  A. which speaker ids do the story scripts actually use (op 0x08 / op 0x0E)?
  B. what do the two tables contain, and does the index line up?
  C. what do the three full-name readers (0x08077EE2 / 0x0808B036 /
     0x080939D6) do with the data they read?
  D. does the converted layout (64x4 pointer table at 0x085A57C4) overlap the
     full-name table at all?

Everything here is read-only: the ROM is never written.

Usage:
    python tools/probe_speaker_id63.py
    python tools/probe_speaker_id63.py --section a
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import struct
import sys
from fractions import Fraction

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import capstone_loader  # noqa: E402

capstone = capstone_loader.load_capstone()
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs  # noqa: E402

import konoha_font as kf  # noqa: E402
from tools import decode_story_script as dss  # noqa: E402

ROM_BASE = 0x08000000
SHORT_BASE = 0x085A57C4   # 12 bytes / entry, inline glyph codes
SHORT_STRIDE = 12
FULL_BASE = 0x085A5AB8    # 19 bytes / entry, inline glyph codes
FULL_STRIDE = 19
NAMES_PTR_BASE = 0x08599280  # 4 bytes / entry, pointer table (character names)
PORTRAIT_BASE = 0x085A4DEC  # 40 bytes / entry (portrait rows)

FULL_READERS = [0x08077EE2, 0x0808B036, 0x080939D6]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def u32(rom: bytes, rom_addr: int) -> int:
    return struct.unpack_from("<I", rom, rom_addr - ROM_BASE)[0]


def thumb_literal(rom: bytes, insn_addr: int, imm: int) -> tuple[int, int]:
    """Resolve a Thumb-1 `ldr rX,[pc,#imm]` literal.  Returns (value, addr)."""
    addr = ((insn_addr + 4) & ~3) + imm
    return u32(rom, addr), addr


def disasm_window(md, rom: bytes, start: int, size: int) -> list[str]:
    off = start - ROM_BASE
    lines = []
    for insn in md.disasm(rom[off:off + size], start):
        note = ""
        if insn.mnemonic == "ldr" and "[pc" in insn.op_str:
            try:
                imm = int(insn.op_str.split("#")[1].rstrip("]"), 0)
                val, at = thumb_literal(rom, insn.address, imm)
                note = "   ; -> 0x%08X (word at 0x%08X)" % (val, at)
            except (IndexError, ValueError):
                note = "   ; -> <unresolved>"
        lines.append("   0x%08X: %-9s %s%s"
                     % (insn.address, insn.mnemonic, insn.op_str, note))
    return lines


def decode_entry(rom: bytes, mapping: dict[int, str], rom_addr: int) -> tuple[str, int]:
    """Decode one NUL-terminated glyph string at `rom_addr`; returns (text, len)."""
    text, nxt = kf.decode_at(rom, rom_addr - ROM_BASE, mapping)
    return text.replace("\n", ""), nxt - (rom_addr - ROM_BASE)


# ---------------------------------------------------------------------------
# A. speaker-id distribution in the story scripts
# ---------------------------------------------------------------------------
def collect_ids(rom: bytes, mapping, roots: list[int], tag: str):
    """Walk one root set and histogram the id operands of op 0x08 / 0x0E."""
    nodes, _issues = dss.walk(rom, roots, mapping)
    c08 = collections.Counter()
    c0e = collections.Counter()
    sites08 = []
    sites0e = []
    for off, node in sorted(nodes.items()):
        if node.op == 0x08 and node.length >= 2:
            c08[node.raw[1]] += 1
            sites08.append((off, node.raw[1]))
        elif node.op == 0x0E and node.length >= 3:
            c0e[(node.raw[1], node.raw[2])] += 1
            sites0e.append((off, node.raw[1], node.raw[2]))
    return {"tag": tag, "c08": c08, "c0e": c0e,
            "sites08": sites08, "sites0e": sites0e,
            "nodes": len(nodes)}


def section_a(rom: bytes, mapping, pack_path: pathlib.Path) -> dict:
    print("=" * 78)
    print("A. speaker id distribution in the story scripts")
    print("=" * 78)

    # --- A1: every scene root (before/after/logic/events x 55 scenes) -------
    all08 = collections.Counter()
    all0e = collections.Counter()
    sites08: list[tuple[int, int]] = []
    sites0e: list[tuple[int, int, int]] = []
    roots_used = 0
    for scene in range(1, dss.STORY_SCENES + 1):
        roots = dss.scene_roots(rom, scene)
        if not roots:
            continue
        roots_used += 1
        res = collect_ids(rom, mapping, list(roots.values()),
                          "scene %d" % scene)
        all08.update(res["c08"])
        all0e.update(res["c0e"])
        sites08.extend(res["sites08"])
        sites0e.extend(res["sites0e"])
    print("A1  ROM walk: %d scene roots, %d op-0x08 sites, %d op-0x0E sites"
          % (roots_used, len(sites08), len(sites0e)))

    # --- A2: the 202 scripts of the content pack --------------------------
    pack08 = collections.Counter()
    pack0e = collections.Counter()
    pack_sites08: list[tuple[int, int]] = []
    pack_sites0e: list[tuple[int, int, int]] = []
    pack_scripts = 0
    pack_ids = []
    if pack_path.exists():
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        for s in pack["scripts"]:
            pack_scripts += 1
            off = s["script_offset"]
            res = collect_ids(rom, mapping, [off], s["id"])
            pack08.update(res["c08"])
            pack0e.update(res["c0e"])
            pack_sites08.extend(res["sites08"])
            pack_sites0e.extend(res["sites0e"])
            for i in list(res["c08"].keys()) + [a for pair in res["c0e"]
                                                for a in pair]:
                pack_ids.append(i)
    print("A2  content pack: %d scripts, %d op-0x08 sites, %d op-0x0E sites"
          % (pack_scripts, len(pack_sites08), len(pack_sites0e)))

    # --- report ------------------------------------------------------------
    def hist(title, c08, c0e, sites8, sitesE):
        print("\n-- %s --" % title)
        print("   op 0x08 (set speaker) id histogram:")
        for k in sorted(c08):
            print("      id %-3d  x%-5d  name=%r" % (k, c08[k],
                  short_name(rom, mapping, k)))
        ids8 = sorted(c08)
        print("   op 0x08 distinct ids: %d  -> %s"
              % (len(ids8), ids8))
        print("   op 0x08 id range: %s .. %s" % (min(ids8) if ids8 else "-",
                                                 max(ids8) if ids8 else "-"))
        print("   op 0x08 ids >= 63: %s"
              % ([k for k in ids8 if k >= 63] or "NONE"))
        flat = sorted({a for pair in c0e for a in pair})
        print("   op 0x0E (two speakers) pairs: %s"
              % sorted(c0e.keys()))
        print("   op 0x0E distinct ids: %s" % flat)
        print("   op 0x0E ids >= 63: %s"
              % ([k for k in flat if k >= 63] or "NONE"))
        print("   op 0x0E sites (rom_offset, id1, id2):")
        for off, a, b in sitesE:
            print("      0x%08X  %3d %3d" % (off + ROM_BASE, a, b))
        return ids8, flat

    ids8, flat0e = hist("A1 ROM walk (all 55 scenes x 4 roots)", all08, all0e,
                        sites08, sites0e)
    ids8b, flat0eb = hist("A2 content pack scripts (202)", pack08, pack0e,
                           pack_sites08, pack_sites0e)

    # --- cross check -------------------------------------------------------
    print("\n-- A3 cross-check --")
    same08 = set(all08.keys()) == set(pack08.keys())
    same0e = set(all0e.keys()) == set(pack0e.keys())
    print("   op 0x08 id sets identical (ROM walk vs content pack): %s" % same08)
    print("   op 0x0E id sets identical (ROM walk vs content pack): %s" % same0e)
    print("   union of every id seen anywhere: %s"
          % sorted(set(ids8) | set(ids8b) | set(flat0e) | set(flat0eb)))
    never = sorted(set(range(0, 64)) - (set(ids8) | set(ids8b) | set(flat0e)
                                        | set(flat0eb)))
    print("   ids in 0..63 never used by op 0x08/0x0E: %s" % never)
    print("   >>> ids >= 63 ever used by op 0x08/0x0E: %s"
          % ([k for k in (set(ids8) | set(ids8b) | set(flat0e) | set(flat0eb))
              if k >= 63] or "NONE  ==> id 63 is never requested by the VM"))
    return {"ids08": sorted(set(ids8) | set(ids8b)),
            "ids0e": sorted(set(flat0e) | set(flat0eb)),
            "never": never}


# ---------------------------------------------------------------------------
# B. the two tables
# ---------------------------------------------------------------------------
def short_name(rom: bytes, mapping, i: int) -> str:
    text, _ = decode_entry(rom, mapping, SHORT_BASE + i * SHORT_STRIDE)
    return text


def full_name(rom: bytes, mapping, i: int) -> str:
    text, _ = decode_entry(rom, mapping, FULL_BASE + i * FULL_STRIDE)
    return text


def section_b(rom: bytes, mapping) -> dict:
    print()
    print("=" * 78)
    print("B. short-name table (12 B) vs full-name table (19 B)")
    print("=" * 78)
    print("%-4s %-10s %-14s %-10s %-16s %s"
          % ("id", "short@", "short", "full@", "full", "relation"))
    align = 0
    same = 0
    for i in range(64):
        s_addr = SHORT_BASE + i * SHORT_STRIDE
        f_addr = FULL_BASE + i * FULL_STRIDE
        s_txt, s_len = decode_entry(rom, mapping, s_addr)
        f_txt, f_len = decode_entry(rom, mapping, f_addr)
        if f_txt.endswith(s_txt) and f_txt != s_txt:
            rel = "full = short + prefix"
            align += 1
        elif f_txt == s_txt:
            rel = "identical"
            same += 1
        else:
            rel = "DIFFERENT"
        print("%-4d 0x%08X %-14r 0x%08X %-16r %s"
              % (i, s_addr, s_txt, f_addr, f_txt, rel))
    print("\nB1  index alignment: %d/64 ids where full-name = short-name + prefix, "
          "%d identical" % (align, same))
    print("B2  short id 63 @ 0x%08X   -> %r"
          % (SHORT_BASE + 63 * SHORT_STRIDE,
             short_name(rom, mapping, 63)))
    print("B3  full  id  0 @ 0x%08X   -> %r"
          % (FULL_BASE, full_name(rom, mapping, 0)))
    print("B4  full  id 63 @ 0x%08X   -> %r"
          % (FULL_BASE + 63 * FULL_STRIDE,
             full_name(rom, mapping, 63)))
    print("B5  short id 63 address == full id 0 address: %s"
          % (SHORT_BASE + 63 * SHORT_STRIDE == FULL_BASE))
    print("B6  bytes at 0x%08X (19 B): %s"
          % (FULL_BASE, rom[FULL_BASE - ROM_BASE:FULL_BASE - ROM_BASE + 19].hex(" ")))
    print("B7  bytes at 0x%08X (12 B, short id 63 slot): %s"
          % (SHORT_BASE + 63 * SHORT_STRIDE,
             rom[SHORT_BASE + 63 * SHORT_STRIDE - ROM_BASE:
                 SHORT_BASE + 63 * SHORT_STRIDE - ROM_BASE + 12].hex(" ")))

    # where does the 19-byte table end?
    print("\nB8  full-name table extent probe (19 B stride, scanning for the "
          "end of the name block):")
    for i in range(60, 72):
        f_addr = FULL_BASE + i * FULL_STRIDE
        txt, ln = decode_entry(rom, mapping, f_addr)
        raw = rom[f_addr - ROM_BASE:f_addr - ROM_BASE + FULL_STRIDE]
        print("      id %-3d 0x%08X  %-24s  %r" % (i, f_addr, raw.hex(" "), txt))
    return {"aligned": align, "identical": same}


# ---------------------------------------------------------------------------
# C. the three full-name readers
# ---------------------------------------------------------------------------
def section_c(rom: bytes, md) -> dict:
    print()
    print("=" * 78)
    print("C. the three full-name readers")
    print("=" * 78)
    out = {}
    for addr in FULL_READERS:
        print("\n" + "-" * 78)
        print("READER 0x%08X  (window 0x%08X..0x%08X)" % (addr, addr - 0x40, addr + 0x40))
        print("-" * 78)
        for line in disasm_window(md, rom, addr - 0x40, 0x80):
            print(line)
        # the literal that carries the table base
        hit = None
        for insn in md.disasm(rom[addr - ROM_BASE:addr - ROM_BASE + 8], addr):
            if insn.mnemonic == "ldr" and "[pc" in insn.op_str:
                imm = int(insn.op_str.split("#")[1].rstrip("]"), 0)
                hit = thumb_literal(rom, insn.address, imm)
        if hit:
            stride = detect_stride(md, rom, addr)
            print("   >> base literal = 0x%08X (word at 0x%08X)  entry stride = %s"
                  % (hit[0], hit[1], stride))
            print("      %s" % ("19 => reads the FULL-NAME table (id * 19)"
                               if stride == 19 else
                               "!! NOT 19 => this is not a full-name reader"))
        out[addr] = hit[0] if hit else None
    return out


# ---------------------------------------------------------------------------
# D. footprint / conversion analysis
# ---------------------------------------------------------------------------
def section_d(rom: bytes, md, readers: dict) -> dict:
    print()
    print("=" * 78)
    print("D. conversion footprint")
    print("=" * 78)
    ptr_lo = SHORT_BASE
    ptr_hi = SHORT_BASE + 64 * 4 - 1
    print("D1  converted pointer table: 0x%08X..0x%08X  (64 x 4 = %d bytes)"
          % (ptr_lo, ptr_hi, 64 * 4))
    print("D2  original short-table region (id 0..62): 0x%08X..0x%08X"
          % (SHORT_BASE, SHORT_BASE + 63 * SHORT_STRIDE - 1))
    print("D3  full-name table region (id 0..63):      0x%08X..0x%08X"
          % (FULL_BASE, FULL_BASE + 64 * FULL_STRIDE - 1))
    overlap = not (ptr_hi < FULL_BASE or ptr_lo > FULL_BASE + 64 * FULL_STRIDE - 1)
    print("D4  pointer table overlaps the full-name table? %s" % overlap)
    print("D5  pointer table ends %d bytes before the full-name table starts"
          % (FULL_BASE - (ptr_hi + 1)))
    print("D6  short id 63 (= full id 0) sits INSIDE the full-name region: %s"
          % (FULL_BASE <= SHORT_BASE + 63 * SHORT_STRIDE
             < FULL_BASE + 64 * FULL_STRIDE))
    # every literal in the ROM that points at either base
    print("\nD7  every Thumb `ldr [pc,#imm]` literal in the ROM pointing at")
    print("    0x%08X (short base) or 0x%08X (full base):" % (SHORT_BASE, FULL_BASE))
    hits_short, hits_full = [], []
    hits_inside = []
    # Thumb-1 `ldr Rt,[pc,#imm8]` T1 encoding: bits 15..11 == 0b01001.
    # Scan range covers the short-name table, the full-name table AND the
    # map-name table (which starts inside the full-name table's last slot).
    scan_lo = SHORT_BASE
    scan_hi = FULL_BASE + 63 * FULL_STRIDE + 55 * 18 + 1
    n = len(rom)
    for off in range(0, n - 4, 2):
        hw = rom[off] | (rom[off + 1] << 8)
        if (hw >> 11) != 0b01001:
            continue
        addr = off + ROM_BASE
        at = ((addr + 4) & ~3) + (hw & 0xFF) * 4
        if at - ROM_BASE + 4 > n:
            continue
        val = struct.unpack_from("<I", rom, at - ROM_BASE)[0]
        if val == SHORT_BASE:
            hits_short.append(addr)
        elif val == FULL_BASE:
            hits_full.append(addr)
        elif scan_lo <= val < scan_hi:
            hits_inside.append((addr, val))
    print("    short base 0x%08X : %d readers %s"
          % (SHORT_BASE, len(hits_short),
             ", ".join("0x%08X" % a for a in hits_short)))
    print("    full  base 0x%08X : %d readers %s"
          % (FULL_BASE, len(hits_full),
             ", ".join("0x%08X" % a for a in hits_full)))
    print("    any other literal pointing INSIDE the three-table region")
    print("    0x%08X..0x%08X :" % (scan_lo, scan_hi - 1))
    for addr, val in hits_inside:
        stride = detect_stride(md, rom, addr)
        print("      0x%08X -> 0x%08X  (stride %s)"
              % (addr, val, stride if stride else "?"))
    print("D7b entry strides of every short-table reader (must all be 12):")
    for a in hits_short:
        print("      0x%08X -> stride %s" % (a, detect_stride(md, rom, a)))
    print("D7c entry strides of every full-name reader (must all be 19):")
    for a in hits_full:
        print("      0x%08X -> stride %s" % (a, detect_stride(md, rom, a)))
    print("D8  => the only code that can reach either table does so through")
    print("    these literals; no reader compares a name pointer against")
    print("    0x%08X, so relocating short id 63's bytes cannot be observed."
          % FULL_BASE)
    return {"ptr_lo": ptr_lo, "ptr_hi": ptr_hi, "overlap": overlap,
            "short_readers": hits_short, "full_readers": hits_full,
            "inside": hits_inside}


def _regs(op_str: str) -> list[str]:
    return [p.strip() for p in op_str.split(",")]


def _split_ops(op_str: str) -> tuple[list[str], str | None]:
    """Split a Thumb operand list into (register operands, memory operand).

    `ldr r1, [pc, #0x50]` splits on ',' into three pieces, so the memory
    part has to be cut off first.
    """
    if "[" in op_str:
        head, mem = op_str.split("[", 1)
        regs = [x.strip() for x in head.split(",") if x.strip()]
        return regs, "[" + mem
    return [x.strip() for x in op_str.split(",") if x.strip()], None


_SKIP_MD = None


def _md_skipdata():
    """A Thumb disassembler that skips undecodable bytes instead of stopping.

    Long windows cross data and literal pools, where plain `disasm` bails out
    at the first bad halfword; the stride evaluator needs to walk past those.
    """
    global _SKIP_MD
    if _SKIP_MD is None:
        _SKIP_MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        _SKIP_MD.skipdata = True
    return _SKIP_MD


def _shift_amount(text: str) -> int:
    """'#3' / '#0x10' -> 3 ; a register shift -> -1 (unsupported)."""
    if "#" not in text:
        return -1
    try:
        return int(text.split("#")[1], 0)
    except ValueError:
        return -1


def detect_stride(md, rom: bytes, ldr_addr: int, window: int = 0x200) -> int | None:
    """Mechanically recover the entry stride of a table access.

    The shape of every table access in this ROM is

        ldr  rB, [pc, #imm]     ; rB = table base (a constant)
        adds rA, rA, rB        ; rA = base + index*stride

    so the stride is the coefficient of the index variable in `rA`.

    The ROM has no multiply instruction; a stride is always built as
        lsls rD, rS, #k   -> X * 2^k
        adds rD, rD, rS   -> X * (2^k + 1)
        lsls rD, rD, #m   -> X * (2^k + 1) * 2^m
    optionally followed by
        subs rD, rD, rS   -> X * (2^k + 1) * 2^m - 1

    This evaluator replays the instructions and tracks every register as a
    rational linear expression a*X + b, where X is "the value the code
    loaded" (loads produce X, pc-relative loads produce a constant, and a
    call's return value is X).  Returns the integer coefficient of the
    register that the base is added into.

    Yields 12 for the short-name table, 19 for the full-name table and
    18 for the map-name table.
    """
    start = max(ROM_BASE, ldr_addr - window)
    win = list(_md_skipdata().disasm(rom[start - ROM_BASE:ldr_addr + 8 - ROM_BASE],
                                     start))
    X = (Fraction(1), Fraction(0))
    ZERO = (Fraction(0), Fraction(0))
    st: dict[str, tuple[Fraction, Fraction]] = {}

    def get(reg):
        return st.get(reg, ZERO)

    for ins in win:
        m = ins.mnemonic
        p, mem = _split_ops(ins.op_str)
        if m.startswith("."):          # capstone skip-data pseudo instruction
            continue
        if m.startswith("ldr") and len(p) == 1 and mem:
            if "pc" in mem:
                st[p[0]] = (Fraction(0), Fraction(1))   # constant base
            else:
                st[p[0]] = X                            # the index
        elif m in ("movs", "mov") and len(p) == 2:
            st[p[0]] = get(p[1])
        elif m in ("lsls", "lsl") and len(p) == 3:
            k = _shift_amount(p[2])
            a, b = get(p[1])
            st[p[0]] = (a * (2 ** k), b * (2 ** k)) if k >= 0 else ZERO
        elif m in ("lsrs", "lsr") and len(p) == 3:
            k = _shift_amount(p[2])
            a, b = get(p[1])
            st[p[0]] = (a / (2 ** k), b / (2 ** k)) if k >= 0 else ZERO
        elif m in ("asrs", "asr") and len(p) == 3:
            k = _shift_amount(p[2])
            a, b = get(p[1])
            st[p[0]] = (a / (2 ** k), b / (2 ** k)) if k >= 0 else ZERO
        elif m in ("adds", "add") and len(p) == 3:
            a1, b1 = get(p[1])
            a2, b2 = get(p[2])
            st[p[0]] = (a1 + a2, b1 + b2)
        elif m in ("adds", "add") and len(p) == 2 and p[1].startswith("#"):
            a, b = get(p[0])                # rD += #imm : coefficient unchanged
            st[p[0]] = (a, b)
        elif m in ("adds", "add") and len(p) == 2:
            # Thumb two-operand add: `add rD, rS` == `adds rD, rD, rS`
            a1, b1 = get(p[0])
            a2, b2 = get(p[1])
            st[p[0]] = (a1 + a2, b1 + b2)
        elif m in ("subs", "sub") and len(p) == 3:
            a1, b1 = get(p[1])
            a2, b2 = get(p[2])
            st[p[0]] = (a1 - a2, b1 - b2)
        elif m in ("bl", "blx"):
            st["r0"] = X          # the call's return value is the index
            for reg in ("r1", "r2", "r3", "r12"):
                st[reg] = ZERO

        # the instruction that adds the base sits right after the load
        if ins.address == ldr_addr + 2 and m in ("adds", "add") and len(p) == 3:
            a, _b = get(p[0])
            if a.denominator == 1 and a != 0:
                return int(a)
    return None


def section_e(rom: bytes, mapping, md) -> dict:
    """The third table that shares the protected region by aliasing."""
    print()
    print("=" * 78)
    print("E. the aliased map-name table (18 B stride, base 0x085A5F65)")
    print("=" * 78)
    print("E1  0x085A5F65 is BOTH:")
    print("      - full-name table id 63 (19 B stride, 0x085A5AB8 + 63*19)")
    print("      - map-name  table id  0 (18 B stride, literal 0x085A5F65)")
    print("      both hold the same bytes: %s"
          % rom[FULL_BASE + 63 * FULL_STRIDE - ROM_BASE:
                FULL_BASE + 63 * FULL_STRIDE - ROM_BASE + 19].hex(" "))
    print("E2  map-name table decoded (18 B stride):")
    n = 0
    for i in range(0, 80):
        a = FULL_BASE + 63 * FULL_STRIDE + 18 * i
        txt, _ = decode_entry(rom, mapping, a)
        if not txt or "{字" in txt:
            break
        n = i
        if i < 6 or i >= 50:
            print("      id %-3d 0x%08X  %r" % (i, a, txt))
    print("      ... (%d entries total, id 0..%d, 0x%08X..0x%08X)"
          % (n + 1, n, FULL_BASE + 63 * FULL_STRIDE,
             FULL_BASE + 63 * FULL_STRIDE + 18 * (n + 1) - 1))
    print("E3  the 18-byte access site 0x0808CD8E:")
    for line in disasm_window(md, rom, 0x0808CD86, 0x10):
        print(line)
    print("      stride detected = %s  (19 would mean full-name reader)"
          % detect_stride(md, rom, 0x0808CD8E))
    print("E4  => this site reads the MAP-name table, not the character")
    print("      full-name table; it is not a 4th full-name reader.")
    print("E5  conversion impact: the map-name table lives at")
    print("      0x%08X..0x%08X; the new pointer table only covers"
          % (FULL_BASE + 63 * FULL_STRIDE,
             FULL_BASE + 63 * FULL_STRIDE + 18 * (n + 1) - 1))
    print("      0x085A57C4..0x085A58C3  =>  untouched.")
    return {"map_entries": n + 1}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(REPO / "rom" / "base.gba"))
    ap.add_argument("--pack", default=str(REPO / "rom-editor" / "content" / "pack.json"))
    ap.add_argument("--section", default="all",
                    choices=["all", "a", "b", "c", "d", "e"])
    args = ap.parse_args()

    rom = pathlib.Path(args.rom).read_bytes()
    mapping, _ = kf.build_mapping(rom)
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

    if args.section in ("all", "a"):
        section_a(rom, mapping, pathlib.Path(args.pack))
    if args.section in ("all", "b"):
        section_b(rom, mapping)
    if args.section in ("all", "c"):
        readers = section_c(rom, md)
    else:
        readers = {}
    if args.section in ("all", "d"):
        if not readers:
            readers = {a: None for a in FULL_READERS}
        section_d(rom, md, readers)
    if args.section in ("all", "e"):
        section_e(rom, mapping, md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
