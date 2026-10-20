#!/usr/bin/env python3
"""Locate the native game code that consumes a ROM table.

Why this tool exists
--------------------
The completion audit (`tools/completion_audit.py`) accepts a "native code
addressing" proof (C2 type 4) as one of the four admissible format proofs,
but until now every such proof had been produced by hand: somebody read a
disassembly, noticed the address, and typed it into a note.  That is not
reproducible and it is not checkable -- the audit could only grep the note
for the literal string.

This tool makes that proof *mechanical*:

  1. build a **whole-ROM literal index**: every address that some
     `LDR Rn, [pc, #imm]` (ARM), `LDR Rt, [pc, #imm]` (Thumb-1) or
     `LDR.W Rt, [pc, #imm]` (Thumb-2) actually reads, together with the
     32-bit value stored there;
  2. for a table base, list every reader of that value -- that is the
     game's own proof that the address is a live table;
  3. walk back to the enclosing function prologue and disassemble it;
  4. classify how the loaded pointer is used (plain dereference, indexed
     table access with a deduced stride, function-pointer dispatch, ...);
  5. optionally, list the *neighbouring* indexed addresses so a wrong
     base can be corrected to the real one.

A structure whose consumer is found this way can then be attached to the
audit with the new `codecite` probe, which re-checks the JSON instead of
grepping prose.

The tool re-derives everything from the ROM; it never trusts a hand-written
address.

Usage:
    python tools/consumer_locate.py rom/base.gba --target 0x53D910
    python tools/consumer_locate.py rom/base.gba --registry --only-legacy
    python tools/consumer_locate.py rom/base.gba --target 0x53636C --neighbors 0x200
    python tools/consumer_locate.py rom/base.gba --registry --json build/consumers.json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import struct
import sys
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

ROM_BASE = 0x08000000

# ARM LDR (literal): cond 01 0 U 1 0 0 1 1111 Rd imm12
ARM_LDR_LITERAL_MASK = 0x0EFF0800
ARM_LDR_LITERAL_VALUE = 0x049F0800
# Thumb-1 LDR (literal): 01001 Rt imm8
THUMB1_LDR_LITERAL_MASK = 0xF800
THUMB1_LDR_LITERAL_VALUE = 0x4800
# Thumb-2 LDR (literal) T2: 11111000 U 1011111 Rt imm12
THUMB2_LDR_LITERAL_MASK = 0xFF7F0000
THUMB2_LDR_LITERAL_VALUE = 0xF85F0000

# ARM prologue: STMFD sp!, {..., lr} = 0xE92D4xxx
ARM_PUSH_MASK = 0xFFFF0000
ARM_PUSH_VALUE = 0xE92D0000
# Thumb-1 PUSH {..., lr} = 0xB5xx
THUMB_PUSH_MASK = 0xFF00
THUMB_PUSH_VALUE = 0xB500


# --------------------------------------------------------------------------
# capstone plumbing (mirrors tools/mechanism_map.py so no env var is needed)
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


# --------------------------------------------------------------------------
# literal decoding
# --------------------------------------------------------------------------
def arm_ldr_literal_target(word: int, insn_addr: int) -> int | None:
    """Target address of an ARM `LDR Rn, [pc, #imm]` at `insn_addr`, if any."""
    if (word & ARM_LDR_LITERAL_MASK) != ARM_LDR_LITERAL_VALUE:
        return None
    imm = word & 0xFFF
    up = (word >> 24) & 1
    offset = imm * 4
    return insn_addr + 8 + offset if up else insn_addr + 8 - offset


def thumb1_ldr_literal_target(half: int, insn_addr: int) -> int | None:
    """Target address of a Thumb-1 `LDR Rt, [pc, #imm]` at `insn_addr`."""
    if (half & THUMB1_LDR_LITERAL_MASK) != THUMB1_LDR_LITERAL_VALUE:
        return None
    base = (insn_addr + 4) & ~3
    return base + (half & 0xFF) * 4


def thumb2_ldr_literal_target(word: int, insn_addr: int) -> int | None:
    """Target address of a Thumb-2 `LDR.W Rn, [pc, #imm]` at `insn_addr`."""
    if (word & THUMB2_LDR_LITERAL_MASK) != THUMB2_LDR_LITERAL_VALUE:
        return None
    imm = word & 0xFFF
    up = (word >> 23) & 1
    base = (insn_addr + 4) & ~3
    offset = imm * 4
    return base + offset if up else base - offset


def _is_arm_prologue(word: int) -> bool:
    return (word & ARM_PUSH_MASK) == ARM_PUSH_VALUE and bool(word & 0x4000)


def _is_thumb_prologue(half: int) -> bool:
    return (half & THUMB_PUSH_MASK) == THUMB_PUSH_VALUE and bool(half & 0x80)


# --------------------------------------------------------------------------
# the whole-ROM literal index
# --------------------------------------------------------------------------
class LiteralIndex:
    """value -> list of (reader_addr, mode) plus pool_addr -> value."""

    def __init__(self, rom: bytes):
        self.rom = rom
        self.rom_end = ROM_BASE + len(rom)
        # value -> [(reader_addr, mode)]
        self.readers: dict[int, list[tuple[int, str]]] = defaultdict(list)
        # pool address -> value
        self.pool_value: dict[int, int] = {}
        self._build()

    def _build(self) -> None:
        rom = self.rom
        n = len(rom)
        unpack32 = struct.unpack_from
        unpack16 = struct.unpack_from

        # --- ARM pass (4-byte aligned) ---
        for addr in range(0, n - 3, 4):
            word = unpack32("<I", rom, addr)[0]
            if (word & ARM_LDR_LITERAL_MASK) != ARM_LDR_LITERAL_VALUE:
                continue
            target = arm_ldr_literal_target(word, ROM_BASE + addr)
            if target is None or not (ROM_BASE <= target < self.rom_end):
                continue
            toff = target - ROM_BASE
            value = unpack32("<I", rom, toff)[0]
            self.pool_value[target] = value
            self.readers[value].append((ROM_BASE + addr, "arm"))

        # --- Thumb pass (2-byte aligned) ---
        for addr in range(0, n - 3, 2):
            half = unpack16("<H", rom, addr)[0]
            if (half & THUMB1_LDR_LITERAL_MASK) == THUMB1_LDR_LITERAL_VALUE:
                target = thumb1_ldr_literal_target(half, ROM_BASE + addr)
                if target is not None and ROM_BASE <= target < self.rom_end:
                    toff = target - ROM_BASE
                    value = unpack32("<I", rom, toff)[0]
                    self.pool_value[target] = value
                    self.readers[value].append((ROM_BASE + addr, "thumb"))
                continue
            if addr % 4:
                continue
            word = unpack32("<I", rom, addr)[0]
            if (word & THUMB2_LDR_LITERAL_MASK) != THUMB2_LDR_LITERAL_VALUE:
                continue
            target = thumb2_ldr_literal_target(word, ROM_BASE + addr)
            if target is None or not (ROM_BASE <= target < self.rom_end):
                continue
            toff = target - ROM_BASE
            value = unpack32("<I", rom, toff)[0]
            self.pool_value[target] = value
            self.readers[value].append((ROM_BASE + addr, "thumb"))

    def readers_of(self, value: int) -> list[tuple[int, str]]:
        return self.readers.get(value, [])

    def neighbors(self, arm_address: int, window: int) -> list[tuple[int, int]]:
        """Indexed values within `window` bytes of `arm_address`.

        Returns [(value, reader_count)] sorted by distance to the base.
        """
        lo = arm_address - window
        hi = arm_address + window
        hits = [(v, len(rs)) for v, rs in self.readers.items() if lo <= v <= hi]
        hits.sort(key=lambda item: abs(item[0] - arm_address))
        return hits

    def suggest(self, arm_address: int, window: int = 0x2000,
                limit: int = 12) -> list[dict]:
        """Where might the real table be, if `arm_address` is not a base?

        A legacy bank whose declared base is referenced nowhere in the ROM
        still sits *somewhere* in the data area.  This lists the indexed
        addresses around it, strongest reader first, so the search for the
        real base starts from evidence instead of a guess.
        """
        lo = arm_address - window
        hi = arm_address + window
        cands = [(v, len(rs)) for v, rs in self.readers.items() if lo <= v <= hi]
        cands.sort(key=lambda item: (-item[1], abs(item[0] - arm_address)))
        out = []
        for value, count in cands[:limit]:
            readers = sorted({addr for addr, _ in self.readers[value]})
            out.append({
                "value": f"0x{value:08X}",
                "file_offset": f"0x{value - ROM_BASE:06X}",
                "delta": value - arm_address,
                "readers": count,
                "first_reader": f"0x{readers[0]:08X}" if readers else None,
            })
        return out


def find_function_start(rom: bytes, insn_addr: int, mode: str,
                        lookback: int = 0x2000) -> int | None:
    """Walk back to the closest function prologue before `insn_addr`."""
    off = insn_addr - ROM_BASE
    if mode == "arm":
        addr = (off - 4) & ~3
        limit = max(0, off - lookback)
        while addr > limit:
            word = struct.unpack_from("<I", rom, addr)[0]
            if _is_arm_prologue(word):
                return ROM_BASE + addr
            addr -= 4
    else:
        addr = (off - 2) & ~1
        limit = max(0, off - lookback)
        while addr > limit:
            half = struct.unpack_from("<H", rom, addr)[0]
            if _is_thumb_prologue(half):
                return ROM_BASE + addr
            addr -= 2
    return None


# --------------------------------------------------------------------------
# disassembly + usage classification
# --------------------------------------------------------------------------
def disassemble(rom: bytes, start: int, count: int, mode: str):
    capstone = load_capstone()
    md = capstone.Cs(capstone.CS_ARCH_ARM,
                     capstone.CS_MODE_ARM if mode == "arm" else capstone.CS_MODE_THUMB)
    md.detail = True
    off = start - ROM_BASE
    step = 4 if mode == "arm" else 2
    blob = rom[off:off + count * step + 16]
    return list(md.disasm(blob, start))


def _op_types(capstone) -> tuple[int, int, int]:
    """(REG, IMM, MEM) operand type constants, across capstone bindings."""
    reg = getattr(capstone, "ARM_OP_REG", None) or capstone.CS_OP_REG
    imm = getattr(capstone, "ARM_OP_IMM", None) or capstone.CS_OP_IMM
    mem = getattr(capstone, "ARM_OP_MEM", None) or capstone.CS_OP_MEM
    return reg, imm, mem


# --------------------------------------------------------------------------
# literal-pool aware decoding
# --------------------------------------------------------------------------
def _literal_target(rom: bytes, insn, mode: str) -> int | None:
    """The pool address a pc-relative literal load reads, if any."""
    offset = insn.address - ROM_BASE
    if offset < 0 or offset + 4 > len(rom):
        return None
    word = int.from_bytes(rom[offset:offset + 4], "little")
    if mode == "arm":
        target = arm_ldr_literal_target(word, insn.address)
    else:
        target = thumb1_ldr_literal_target(word & 0xFFFF, insn.address)
        if target is None and insn.address % 4 == 0:
            target = thumb2_ldr_literal_target(word, insn.address)
    if target is None or not (ROM_BASE <= target < ROM_BASE + len(rom)):
        return None
    return target


def _literal_value(rom: bytes, insn, mode: str) -> int | None:
    """The 32-bit value a pc-relative literal load reads, if any."""
    target = _literal_target(rom, insn, mode)
    if target is None:
        return None
    offset = target - ROM_BASE
    if offset + 4 > len(rom):
        return None
    return int.from_bytes(rom[offset:offset + 4], "little")


def _decode_stream(rom, md, start, mode, pool, limit):
    """One linear decoding pass; `pool` grows with the words it reads."""
    step = 4 if mode == "arm" else 2
    insns: list = []
    addr = start
    guard = 0
    while len(insns) < limit and guard < 4 * limit + 64:
        guard += 1
        offset = addr - ROM_BASE
        if offset < 0 or offset + 4 > len(rom):
            break
        if addr in pool:
            addr += 4            # a pool word is four bytes of data, not code
            continue
        decoded = list(md.disasm(rom[offset:offset + 256], addr))
        if not decoded:
            addr += step          # undecodable halfword: resync
            continue
        for insn in decoded:
            if insn.address in pool:
                addr = insn.address + 4
                break             # re-decode from just after the pool word
            insns.append(insn)
            target = _literal_target(rom, insn, mode)
            if target is not None:
                pool.add(target)
            addr = insn.address + insn.size
            if len(insns) >= limit:
                break
    return insns


def decode_function(rom: bytes, fn_start: int, mode: str,
                    limit: int = 512) -> list:
    """Disassemble a function with its literal pool filtered out.

    A literal pool sits *inside* a function and decodes as garbage code.
    Left in the stream it produces phantom usages and it even stops the
    scan (pool bytes are not always valid Thumb), which is how the readers
    that sit after a pool used to go unanalysed.  The pool words are found
    from the pc-relative loads that read them and skipped, so the
    instruction stream stays code from the prologue to the end.
    """
    capstone = load_capstone()
    md = capstone.Cs(capstone.CS_ARCH_ARM,
                     capstone.CS_MODE_ARM if mode == "arm"
                     else capstone.CS_MODE_THUMB)
    md.detail = True
    pool: set[int] = set()
    insns: list = []
    for _ in range(3):
        known = len(pool)
        insns = _decode_stream(rom, md, fn_start, mode, pool, limit)
        if len(pool) == known:
            break
    return insns


# --------------------------------------------------------------------------
# symbolic register values
# --------------------------------------------------------------------------
class _Val:
    """A register value: ``const + sum(atoms[a] * scale)``.

    ``atoms`` maps an opaque "index variable" id to its coefficient and
    ``scale`` is the pending power-of-two scale applied to the whole value.
    Keeping the scale separate from the coefficients is what lets
    ``lsls #0x18`` / ``lsrs #0x14`` be recognised as "multiply the index by
    16" instead of destroying the index.

    ``base`` marks a value that still carries the literal table base, so the
    consumption detector can tell "base + k*idx" from an unrelated add.
    """

    __slots__ = ("const", "atoms", "scale", "base")

    def __init__(self, const=0, atoms=None, scale=1.0, base=False):
        self.const = const
        self.atoms = dict(atoms) if atoms else {}
        self.scale = scale
        self.base = base

    @property
    def is_const(self) -> bool:
        return not self.atoms

    def coefficients(self) -> list[float]:
        """Every distinct effective index coefficient, largest first.

        A table can be indexed in two dimensions at once -- ``battle_actors``
        at ``0x5461C4`` is read as ``base + row*2276 + column*6828`` -- and a
        single "stride" would hide half the picture.
        """
        seen: list[float] = []
        for coeff in self.atoms.values():
            eff = coeff * self.scale
            if not eff:
                continue
            if not any(abs(eff - other) < 1e-9 for other in seen):
                seen.append(eff)
        seen.sort(key=abs, reverse=True)
        return seen


def _unknown(atom: int) -> _Val:
    """A value the analyser cannot follow (a memory load, a masked value...)."""
    return _Val(const=0, atoms={atom: 1}, scale=1.0)


def _scale(value: _Val, factor: float) -> _Val:
    return _Val(const=value.const, atoms=value.atoms,
                scale=value.scale * factor, base=value.base)


def _rescale(value: _Val, scale: float) -> _Val:
    """Rewrite `value` so its pending scale becomes `scale`.

    `scale` must divide `value.scale` by a power of two, which keeps the
    rewrite exact for the coefficient bookkeeping.
    """
    factor = value.scale / scale
    if factor == 1.0:
        return _Val(const=value.const, atoms=value.atoms, scale=scale,
                    base=value.base)
    if factor >= 1.0 and float(factor).is_integer() \
            and int(factor) & (int(factor) - 1) == 0:
        atoms = {a: c * int(factor) for a, c in value.atoms.items()}
        return _Val(const=value.const * int(factor), atoms=atoms, scale=scale,
                    base=value.base)
    # cannot rescale exactly -- keep the value but drop the unknown scale
    return _Val(const=value.const, atoms=value.atoms, scale=scale,
                base=value.base)


def _add(left: _Val, right: _Val) -> _Val:
    scale = min(left.scale, right.scale)
    left = _rescale(left, scale)
    right = _rescale(right, scale)
    atoms = dict(left.atoms)
    for atom, coeff in right.atoms.items():
        atoms[atom] = atoms.get(atom, 0) + coeff
    return _Val(const=left.const + right.const, atoms=atoms, scale=scale,
                base=left.base or right.base)


def _sub(left: _Val, right: _Val) -> _Val:
    scale = min(left.scale, right.scale)
    left = _rescale(left, scale)
    right = _rescale(right, scale)
    atoms = dict(left.atoms)
    for atom, coeff in right.atoms.items():
        atoms[atom] = atoms.get(atom, 0) - coeff
    return _Val(const=left.const - right.const, atoms=atoms, scale=scale,
                base=left.base)


def _mul(left: _Val, right: _Val) -> _Val:
    if left.is_const:
        factor = left.const
        atoms = {a: c * factor for a, c in right.atoms.items()}
        return _Val(const=right.const * factor, atoms=atoms, scale=right.scale,
                    base=right.base)
    if right.is_const:
        factor = right.const
        atoms = {a: c * factor for a, c in left.atoms.items()}
        return _Val(const=left.const * factor, atoms=atoms, scale=left.scale,
                    base=left.base)
    # two indexed operands: the product is not affine, give up on the scale
    return _Val(const=0, atoms={}, scale=1.0, base=left.base or right.base)


def _shift_amount(op) -> int:
    """Extract the `lsl #n` amount from a capstone register operand."""
    shift = getattr(op, "shift", None)
    if shift is None:
        return 0
    value = getattr(shift, "value", None)
    if value is None and isinstance(shift, int):
        value = shift
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _mnemonic(insn) -> str:
    """The mnemonic without the Thumb-2 width suffix (`add.w` -> `add`)."""
    return insn.mnemonic.split(".")[0]


# --------------------------------------------------------------------------
# per-reader analysis
# --------------------------------------------------------------------------
def analyze_reader(rom: bytes, insns, reader_addr: int, literal_value: int,
                   mode: str) -> dict:
    """Derive how `reader_addr` uses `literal_value`.

    The pass is a small symbolic dataflow over the function, **scoped to the
    reader**: the base pointer is seeded at the reader instruction and every
    later instruction is interpreted as ``const + sum(atoms * scale)``.

    That scoping is what makes the stride trustworthy:

    * an immediate only becomes a stride when it is combined with the
      register that holds the base (or a copy of it), so the immediate of
      *another* load in the same function can no longer be paired with this
      load's multiply;
    * a bit mask (``ands r0, r3, #0x3f``) destroys the value it masks, so it
      can never be mistaken for a stride.

    Returns the usage class, the deduced stride(s) and the instructions that
    prove them.
    """
    capstone = load_capstone()
    OP_REG, OP_IMM, OP_MEM = _op_types(capstone)

    result = {"usage": "unknown", "detail": "", "stride": None,
              "strides": [], "evidence": []}

    try:
        reader_index = next(i for i, insn in enumerate(insns)
                            if insn.address == reader_addr)
    except StopIteration:
        return result

    state: dict[int, _Val] = {}
    carriers: set[int] = set()
    origins: dict[int, int] = {}
    slot_candidates: dict[tuple[int, int], None] = {}
    next_atom = [1]
    base_reg = None
    consumed = False

    def _set(reg, value: _Val) -> None:
        state[reg] = value
        if value.base:
            carriers.add(reg)

    def _carries_base(reg) -> bool:
        """True when `reg` holds -- or has held -- the literal table base."""
        value = state.get(reg)
        if value is not None and value.base:
            return True
        return reg in carriers

    for index, insn in enumerate(insns):
        ops = insn.operands
        mnemonic = _mnemonic(insn)

        if index == reader_index:
            # the reader itself: the loaded register now holds the base
            if ops and ops[0].type == OP_REG:
                base_reg = ops[0].reg
                _set(base_reg, _Val(const=literal_value, atoms={},
                                    scale=1.0, base=True))
            result["evidence"].append(
                f"{insn.address:08X}  {insn.mnemonic} {insn.op_str}"
                f"  ; base = 0x{literal_value:08X}")
            continue

        # --- a literal load seen *before* the reader: model it as a constant
        if mnemonic == "ldr" and len(ops) >= 2 and ops[1].type == OP_MEM:
            mem = ops[1].mem
            if mem.base and insn.reg_name(mem.base).lower() in ("pc", "r15"):
                value = _literal_value(rom, insn, mode)
                if value is not None and ops[0].type == OP_REG:
                    _set(ops[0].reg, _Val(const=value, atoms={}, scale=1.0))
                    origins[ops[0].reg] = insn.address
                    continue

        if not ops or ops[0].type != OP_REG:
            continue
        dst = ops[0].reg

        # --- consumption of the base pointer
        if index > reader_index and not consumed and base_reg is not None:
            if mnemonic.startswith("add") and len(ops) >= 3:
                left = state.get(ops[1].reg) if ops[1].type == OP_REG else None
                right = None
                if ops[2].type == OP_REG:
                    right = state.get(ops[2].reg)
                    shift = _shift_amount(ops[2])
                    if right is not None and shift:
                        right = _scale(right, 2 ** shift)
                elif ops[2].type == OP_IMM:
                    right = _Val(const=ops[2].imm)
                if left is not None and right is not None \
                        and (left.base or right.base):
                    other = right if left.base else left
                    result["evidence"].append(
                        f"{insn.address:08X}  {insn.mnemonic} {insn.op_str}")
                    if other.atoms:
                        coeffs = other.coefficients()
                        result["usage"] = ("indexed" if len(coeffs) == 1
                                           else "indexed-2d")
                        result["detail"] = "base + " + " + ".join(
                            f"{c:g}*idx" for c in coeffs)
                        result["strides"] = coeffs
                        if coeffs and float(coeffs[0]).is_integer() \
                                and coeffs[0] >= 1:
                            result["stride"] = int(coeffs[0])
                    else:
                        result["usage"] = "offset"
                        result["detail"] = f"base + {other.const:g}"
                    consumed = True
            if not consumed and mnemonic == "cmp":
                if any(op.type == OP_REG and _carries_base(op.reg)
                       for op in ops):
                    result["usage"] = "compare"
                    result["detail"] = insn.op_str
                    result["evidence"].append(
                        f"{insn.address:08X}  {insn.mnemonic} {insn.op_str}")
                    consumed = True
            if not consumed and mnemonic == "str":
                if any(op.type == OP_MEM and _carries_base(op.mem.base)
                       for op in ops):
                    result["usage"] = "store"
                    result["detail"] = insn.op_str
                    result["evidence"].append(
                        f"{insn.address:08X}  {insn.mnemonic} {insn.op_str}")
                    consumed = True
            if not consumed and mnemonic == "ldr":
                for op in ops:
                    if op.type != OP_MEM or not _carries_base(op.mem.base):
                        continue
                    disp = op.mem.disp
                    result["usage"] = "deref"
                    result["detail"] = f"base + {disp}" if disp else "base"
                    result["evidence"].append(
                        f"{insn.address:08X}  {insn.mnemonic} {insn.op_str}")
                    consumed = True
                    break
            if not consumed and mnemonic in ("blx", "bx"):
                if any(op.type == OP_REG and _carries_base(op.reg)
                       for op in ops):
                    result["usage"] = "call_target"
                    result["detail"] = insn.op_str
                    result["evidence"].append(
                        f"{insn.address:08X}  {insn.mnemonic} {insn.op_str}")
                    consumed = True

        # --- state update
        if mnemonic in ("mov", "movs", "movw") and len(ops) >= 2:
            if ops[1].type == OP_REG:
                src = state.get(ops[1].reg)
                if src is None:
                    src = _unknown(next_atom[0])
                    next_atom[0] += 1
                # a copy of the base pointer stays the base pointer
                if dst in carriers and src.is_const and src.const > 0:
                    slot_candidates[(origins.get(ops[1].reg) or insn.address,
                                     src.const)] = None
                _set(dst, src)
                origins[dst] = origins.get(ops[1].reg)
            elif ops[1].type == OP_IMM:
                if dst in carriers and ops[1].imm > 0:
                    slot_candidates[(insn.address, ops[1].imm)] = None
                _set(dst, _Val(const=ops[1].imm))
                origins.pop(dst, None)
            continue
        if mnemonic in ("movt", "movw2") and len(ops) >= 3:
            _set(dst, _unknown(next_atom[0]))
            next_atom[0] += 1
            continue
        if mnemonic in ("lsls", "lsl", "lsrs", "lsr") and len(ops) >= 3 \
                and ops[1].type == OP_REG:
            src = state.get(ops[1].reg)
            if src is None:
                src = _unknown(next_atom[0])
                next_atom[0] += 1
            amount = ops[2].imm if ops[2].type == OP_IMM \
                else _shift_amount(ops[2])
            factor = 2 ** amount if mnemonic.startswith("lsl") else 2 ** -amount
            _set(dst, _scale(src, factor))
            continue
        if mnemonic in ("add", "adds") and len(ops) >= 3:
            left = state.get(ops[1].reg) if ops[1].type == OP_REG else None
            if left is None:
                left = _unknown(next_atom[0])
                next_atom[0] += 1
            if ops[2].type == OP_REG:
                right = state.get(ops[2].reg)
                if right is None:
                    right = _unknown(next_atom[0])
                    next_atom[0] += 1
                shift = _shift_amount(ops[2])
                if shift:
                    right = _scale(right, 2 ** shift)
            else:
                right = _Val(const=ops[2].imm)
            _set(dst, _add(left, right))
            continue
        if mnemonic in ("sub", "subs") and len(ops) >= 3:
            left = state.get(ops[1].reg) if ops[1].type == OP_REG else None
            if left is None:
                left = _unknown(next_atom[0])
                next_atom[0] += 1
            if ops[2].type == OP_REG:
                right = state.get(ops[2].reg)
                if right is None:
                    right = _unknown(next_atom[0])
                    next_atom[0] += 1
            else:
                right = _Val(const=ops[2].imm)
            _set(dst, _sub(left, right))
            continue
        if mnemonic in ("mul", "muls", "mla") and len(ops) >= 3:
            left = state.get(ops[1].reg) if ops[1].type == OP_REG else None
            if left is None:
                left = _unknown(next_atom[0])
                next_atom[0] += 1
            right = state.get(ops[2].reg) if ops[2].type == OP_REG else None
            if right is None:
                right = _unknown(next_atom[0])
                next_atom[0] += 1
            _set(dst, _mul(left, right))
            continue
        if mnemonic == "ldr" and len(ops) >= 2 and ops[1].type == OP_MEM:
            mem = ops[1].mem
            if mem.base and insn.reg_name(mem.base).lower() in ("pc", "r15"):
                value = _literal_value(rom, insn, mode)
                if value is not None:
                    _set(dst, _Val(const=value, atoms={}, scale=1.0))
                    origins[dst] = insn.address
                    continue
            _set(dst, _unknown(next_atom[0]))
            next_atom[0] += 1
            continue
        if mnemonic == "str":
            continue
        # anything else clobbers the register as far as we are concerned
        _set(dst, _unknown(next_atom[0]))
        next_atom[0] += 1

    # --- the derived slots of the same table are constants that are
    #     installed into the register that carries the base pointer
    #     (``mov sb, r2``).  Attributing them is the cross-check that the
    #     deduced stride is the *right* one: a wrong stride would leave the
    #     sibling slots unattributed.
    stride = result["stride"]
    if stride:
        for (address, value) in slot_candidates:
            delta = value - literal_value
            if delta <= 0 or delta % stride:
                continue
            result["evidence"].append(
                f"{address:08X}  slot 0x{value:08X} = base + "
                f"{delta // stride}*{stride}")

    return result



# --------------------------------------------------------------------------
# the main scan
# --------------------------------------------------------------------------
def locate_consumers(rom: bytes, index: LiteralIndex, arm_address: int,
                     radius: int = 0, max_consumers: int = 24) -> dict:
    """Full consumer analysis for one ARM address."""
    result = {
        "arm_address": f"0x{arm_address:08X}",
        "file_offset": (f"0x{arm_address - ROM_BASE:06X}"
                        if arm_address >= ROM_BASE else "n/a (not in ROM)"),
        "radius": radius,
        "consumers": [],
        "unreferenced": True,
    }
    capstone = load_capstone()
    seen: set[tuple[int, int]] = set()

    for k in range(0, radius + 1):
        value = arm_address + 4 * k
        for reader_addr, mode in index.readers_of(value):
            key = (reader_addr, value)
            if key in seen:
                continue
            seen.add(key)
            fn_start = find_function_start(rom, reader_addr, mode)
            entry = {
                "literal_value": f"0x{value:08X}",
                "offset_from_base": value - arm_address,
                "reader_addr": f"0x{reader_addr:08X}",
                "reader_mode": mode,
                "reader_kind": "literal-pool",
                "function_start": f"0x{fn_start:08X}" if fn_start else None,
            }
            if fn_start:
                # The literal pool is filtered out of the stream, so a reader
                # that sits after a pool is analysed like any other one.
                insns = decode_function(rom, fn_start, mode)
                use = analyze_reader(rom, insns, reader_addr, value, mode)
                if use["evidence"]:
                    entry["usage"] = use["usage"]
                    entry["usage_detail"] = use["detail"]
                    entry["usage_evidence"] = use["evidence"]
                    entry["strides"] = use["strides"]
                    if use["stride"]:
                        entry["stride"] = use["stride"]
                entry["disasm"] = [
                    f"{i.address:08X}  {i.mnemonic} {i.op_str}".rstrip()
                    for i in insns[:48]
                ]
            result["consumers"].append(entry)
            if len(result["consumers"]) >= max_consumers:
                result["unreferenced"] = False
                return result

    result["unreferenced"] = not result["consumers"]
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _parse_target(text: str) -> int:
    """Interpret a target as ROM address, RAM address or ROM file offset.

    * ``0x08xxxxxx`` -> absolute ROM address
    * ``0x02xxxxxx`` -> EWRAM/IWRAM address (used as-is)
    * anything else  -> ROM file offset
    """
    value = int(text, 0)
    if value >= ROM_BASE or value >= 0x02000000:
        return value
    return ROM_BASE + value


def _registry_targets() -> list[tuple[str, int, bool]]:
    from table_registry import TABLES  # local import: keeps the CLI light
    rows = []
    for name, (addr, verified, _note) in sorted(TABLES.items()):
        rows.append((name, ROM_BASE + addr, verified))
    return rows


# Every structure the completion audit tracks, with the ROM file offset of
# its base.  Kept here so the evidence file covers the whole audit surface,
# not only what `tools/table_registry.py` currently lists.
AUDIT_TABLES: dict[str, int] = {
    # --- battle ---
    "battle_actors": 0x5461C4,
    "battle_rules": 0x594758,
    "reward_table": 0x59EAE0,
    "map_table": 0x53D910,
    "character_template": 0x54241C,
    "skill_table": 0x545458,
    "per_character_skills": 0x545068,
    "character_perks": 0x5459C8,
    # --- story / text ---
    "story_before_root": 0x060C74,
    "story_after_root": 0x060D54,
    "story_logic_root": 0x060E34,
    "story_events_root": 0x060EF0,
    "font_segments": 0x53D644,
    "character_names": 0x599280,
    "ninjutsu_names": 0x599634,
    "material_names": 0x5A7E8C,
    "background_table": 0x59903C,
    "mission_index": 0x348DAC,
    "mission_title_table": 0x59AA5C,
    "mission_description_table": 0x59D214,
    "mission_hint_table": 0x59E920,
    # --- assets ---
    "portrait_table": 0x5A4DEC,
    "portrait_pieces": 0x4643C0,
    "sprite_action_table": 0x596CCC,
    "sound_id_table": 0x465B70,
    "pickup_dispatch": 0x0815E4,
    "mechanism_effects": 0x08136C,
    # --- legacy banks (see notes/legacy-table-base-correction-20261020.md) ---
    "legacy_audio_or_palettes": 0x53F138,
    "legacy_battle_encounters": 0x542384,
    "legacy_battle_handlers": 0x53E6D8,
    "legacy_character_stats": 0x54507A,
    "legacy_character_stats_b": 0x545200,
    "legacy_cutscene_scripts": 0x53DF70,
    "legacy_data_table_a": 0x5A14A4,
    "legacy_data_table_b": 0x5A2120,
    "legacy_fonts": 0x53E5B4,
    "legacy_function_pointers": 0x53D5F4,
    "legacy_items_or_skills": 0x546100,
    "legacy_levels": 0x5459D4,
    "legacy_map_events": 0x53EB08,
    "legacy_map_sprites": 0x53F1DC,
    "map_object_table": 0x53F140,
    "legacy_menu_ui": 0x5A5774,
    "legacy_resource_pointers": 0x596F0C,
    "legacy_sappy_engine": 0x079668,
    "legacy_save_state": 0x53D848,
    "legacy_sprite_animations": 0x53F200,
    "legacy_story": 0x53636C,
    "legacy_story_b": 0x536BC8,
    "legacy_story_c": 0x538FF0,
    "legacy_story_d": 0x53AB78,
    "legacy_story_e": 0x53C3C0,
    "legacy_tile_assets": 0x5A3218,
    "legacy_units": 0x53F298,
}


def raw_occurrences(rom: bytes, arm_address: int) -> list[int]:
    """Every file offset where the 32-bit value `arm_address` appears.

    A live table base is normally referenced at least once -- by a literal
    load, or by a pointer stored in a data table.  Zero occurrences means
    the address is not an address the ROM ever names, whatever the bytes
    there happen to look like.
    """
    needle = struct.pack("<I", arm_address)
    out: list[int] = []
    pos = rom.find(needle)
    while pos != -1:
        out.append(pos)
        pos = rom.find(needle, pos + 1)
    return out


def build_evidence(rom: bytes, index: LiteralIndex, targets: list[tuple[str, int]],
                   radius: int = 0) -> dict:
    """Compact, machine-checkable consumer evidence for the completion audit.

    Unlike the verbose JSON dump this keeps only what a reviewer needs to
    re-check a claim: who reads the address, in which function, and the
    instructions that prove it.  The ROM digest is included so stale
    evidence cannot silently outlive a ROM change.
    """
    import hashlib

    tables: dict[str, dict] = {}
    for name, addr in targets:
        res = locate_consumers(rom, index, addr, radius=radius)
        # Keyed by the ARM address, not by the registry name: a table may be
        # renamed or re-registered without invalidating the evidence.
        tables[res["arm_address"]] = {
            "name": name,
            "file_offset": res["file_offset"],
            "raw_occurrences": [f"0x{o:06X}" for o in raw_occurrences(rom, addr)],
            "consumers": [
                {
                    "reader": c["reader_addr"],
                    "mode": c["reader_mode"],
                    "function": c["function_start"],
                    "usage": c.get("usage"),
                    "usage_detail": c.get("usage_detail"),
                    "stride": c.get("stride"),
                    "evidence": c.get("usage_evidence") or [],
                    "disasm": (c.get("disasm") or [])[:24],
                }
                for c in res["consumers"]
            ],
            # The nearest *other* addresses the game does index: this is how a
            # wrong base gets corrected to the real one.
            "neighbors": [
                {"value": f"0x{v:08X}", "delta": v - addr, "readers": n}
                for v, n in index.neighbors(addr, 0x1000)[:16]
            ],
        }
    return {
        "generated_by": "tools/consumer_locate.py",
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "rom_size": len(rom),
        "indexed_values": len(index.readers),
        "tables": tables,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--target", action="append", default=[],
                    help="table base (file offset or 0x08xxxxxx ARM address)")
    ap.add_argument("--radius", type=int, default=0,
                    help="also look for base+4*k literals (k = 1..radius)")
    ap.add_argument("--neighbors", type=int, default=0,
                    help="list indexed values within N bytes of the target")
    ap.add_argument("--suggest", type=int, default=0,
                    help="for a target with no native reader, list the "
                         "strongest candidate bases within N bytes")
    ap.add_argument("--registry", action="store_true",
                    help="scan every table in tools/table_registry.py")
    ap.add_argument("--all", action="store_true",
                    help="scan the registry plus the built-in AUDIT_TABLES list")
    ap.add_argument("--only-legacy", action="store_true",
                    help="with --registry/--all: only the unverified legacy entries")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--evidence", type=pathlib.Path, default=None,
                    help="write the compact consumer-evidence file used by "
                         "tools/completion_audit.py")
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    index = LiteralIndex(rom)

    targets: list[tuple[str, int]] = []
    if args.registry or args.all:
        for name, addr, verified in _registry_targets():
            if args.only_legacy and verified:
                continue
            targets.append((name, addr))
    if args.all:
        for name, off in sorted(AUDIT_TABLES.items()):
            targets.append((name, ROM_BASE + off))
    for text in args.target:
        targets.append((text, _parse_target(text)))

    if not targets:
        print("nothing to do: pass --target or --registry", file=sys.stderr)
        return 2

    report = {"rom": str(args.rom), "indexed_values": len(index.readers),
              "targets": []}
    for name, addr in targets:
        res = locate_consumers(rom, index, addr, radius=args.radius)
        res["name"] = name
        if args.neighbors:
            res["neighbors"] = [
                {"value": f"0x{v:08X}", "delta": v - addr, "readers": n}
                for v, n in index.neighbors(addr, args.neighbors)
            ]
        if args.suggest:
            res["suggested_bases"] = index.suggest(addr, window=args.suggest)
        report["targets"].append(res)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")

    if args.evidence:
        # The evidence file is the *audited subset*: the structures the
        # completion audit tracks (its `codecite` / `notatable` probes are
        # derived from this file).  The registry grows over time, so folding
        # it in here would silently change what the file covers; `--all`
        # therefore keeps the evidence file pinned to AUDIT_TABLES.
        evidence_targets = targets
        if args.all:
            evidence_targets = [(name, ROM_BASE + off)
                                for name, off in sorted(AUDIT_TABLES.items())]
        evidence = build_evidence(rom, index, evidence_targets,
                                  radius=args.radius)
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        proven = sum(1 for t in evidence["tables"].values() if t["consumers"])
        print(f"evidence written: {args.evidence} "
              f"({proven}/{len(evidence['tables'])} tables with a native reader)")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"literal index: {len(index.readers)} distinct values referenced "
          f"by {sum(len(v) for v in index.readers.values())} instructions")
    print()
    total = len(report["targets"])
    found = 0
    for res in report["targets"]:
        n = len(res["consumers"])
        print(f"{res['name']:38s} {res['arm_address']}  consumers={n}")
        if n == 0:
            print("    (no native reader -- this address is NOT referenced "
                  "by any literal load in the ROM)")
            for nb in (res.get("suggested_bases") or [])[:8]:
                print(f"      candidate base {nb['value']} "
                      f"(file {nb['file_offset']}, delta {nb['delta']:+#x}, "
                      f"{nb['readers']} readers, first reader "
                      f"{nb['first_reader']})")
            for nb in (res.get("neighbors") or [])[:12]:
                print(f"      neighbor {nb['value']} delta={nb['delta']:+#x} "
                      f"readers={nb['readers']}")
            continue
        found += 1
        for c in res["consumers"][:6]:
            stride = c.get("stride")
            print(f"    reader {c['reader_addr']} ({c['reader_mode']}) "
                  f"fn {c['function_start']} "
                  f"usage={c.get('usage', '?')} {c.get('usage_detail', '')}"
                  + (f" stride={stride}" if stride else ""))
            for line in (c.get("usage_evidence") or [])[:3]:
                print(f"        {line}")
    print()
    print(f"targets with a proven native consumer: {found} / {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
