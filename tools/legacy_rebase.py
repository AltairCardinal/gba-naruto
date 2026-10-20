#!/usr/bin/env python3
"""Find the live table a legacy content bank is really pointing at.

Why this tool exists
--------------------
Twenty-three legacy content banks under ``sequel/content/*/bank.json`` declare
a ``table_offset`` that the ROM never names -- not as a literal load, not as a
data pointer.  ``tools/completion_audit.py`` calls those "基址无效，需重新定位"
(*rebase*).  A grep cannot settle them, because the interesting question is not
"is this address mentioned?" but "**which live table does this address actually
sit inside?**".

Two different indexes exist, and confusing them is exactly the trap that made
the first pass of this investigation wrong:

  * ``notes/evidence/consumer-evidence.json`` is the **audited subset** -- 54
    tables the completion audit cares about.  It is a *report*, not an index: a
    live table outside the audit surface is simply absent from it, so a
    neighbour query answered from that file returns a silently truncated
    candidate set.
  * ``tools.consumer_locate.LiteralIndex`` is the **whole-ROM literal
    index** -- every address some ``LDR Rn, [pc, #imm]`` actually reads.  18051
    distinct values, 1196 of them pointing into the ROM image.  *This* is the
    index a neighbour query has to use.

So this tool builds the full index from the ROM itself, and uses the evidence
file for two things only: proving the ROM is the one the evidence was
generated from (``rom_sha256``), and labelling the neighbours that happen to
sit inside the audited 54-table subset.  The evidence file is read-only and is
never regenerated.

Strides are derived, not copied
-------------------------------
``tools/consumer_locate.py`` records a stride per reader, but it scans the
*whole function* for a ``mov #imm`` / ``mul`` pair.  When two tables are read
by the same function -- the norm in this ROM -- that pairs the immediate of
one load with the multiply of the other and reports the wrong stride.  The two
examples in ``notes/evidence/legacy-rebase-nearby-20261020.md`` are exactly
that failure: the evidence file says ``0x545068`` has stride 180 (it has
stride **16**; 180 is the stride of the *character template* table read one
instruction earlier by the same function) and ``0x5459C8`` has stride 63 (it
is **12**; 63 = 0x3F is a bit-mask in the same function, not a stride).

This tool therefore re-derives the stride with a small symbolic pass that runs
**from the function start up to and past the reader**, tracking the index
expression ``base + k * idx``.  Because the pass is dataflow-ordered, the
immediate of one load can never be attributed to the multiply of another.

Usage:
    python tools/legacy_rebase.py rom/base.gba --target 0x54507A
    python tools/legacy_rebase.py rom/base.gba --target 0x54507A --window 0x800
    python tools/legacy_rebase.py rom/base.gba --all-legacy
    python tools/legacy_rebase.py rom/base.gba --target 0x546100 --json build/rebase.json

Exit codes:
    0  ok
    2  bad usage, missing ROM, or missing evidence file
    3  the ROM digest does not match the evidence file
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import consumer_locate as cl  # noqa: E402

ROM_BASE = cl.ROM_BASE
ROM_SIZE = 0x600000
ROM_END = ROM_BASE + ROM_SIZE
DEFAULT_ROM = REPO / "rom" / "base.gba"
DEFAULT_EVIDENCE = REPO / "notes" / "evidence" / "consumer-evidence.json"

# The bases that were re-established on 2026-10-21 (see
# notes/evidence/legacy-rebase-nearby-20261020.md).  They are listed here so
# the tool can name them even though they are outside the 54-table audited
# subset of the evidence file.
#   legacy bank -> (true base, entry size, entry count, what it really is)
REBASED_TABLES = {
    0x54229C: ("战斗遭遇记录表", 16, 24,
               "battle-encounters（旧基址 0x542384 是第 14 条 + 8 字节的窗口）"),
    0x545068: ("逐角色属性表", 16, 63,
               "character-stats / character-stats-b（旧基址错位 2 / 8 字节）"),
    0x5459C8: ("角色特性表", 12, 45,
               "levels（旧基址错位 1 条；旧表声明 47 条其实越过表尾）"),
    0x545BE4: ("道具/技能记录表", 16, 94,
               "items / skills（旧基址 0x546100 是第 81 条 + 12 字节的窗口）"),
}

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_DIGEST = 3

# how far past the reader the consumption of the base pointer is looked for
CONSUMPTION_WINDOW = 24
# how many instructions of a function are disassembled at most
FUNCTION_INSTRUCTIONS = 1024


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

    def dominant(self) -> tuple[int | None, int]:
        """Largest effective coefficient and the atom id it belongs to."""
        best_atom, best = None, 0
        for atom, coeff in self.atoms.items():
            eff = coeff * self.scale
            if abs(eff) > abs(best) or best_atom is None:
                best_atom, best = atom, eff
        return best_atom, best

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
    """Rewrite ``value`` so its pending scale becomes ``scale``.

    ``scale`` must divide ``value.scale`` by a power of two, which keeps the
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


# --------------------------------------------------------------------------
# per-reader analysis
# --------------------------------------------------------------------------
def _op_types(capstone):
    reg = getattr(capstone, "ARM_OP_REG", None) or capstone.CS_OP_REG
    imm = getattr(capstone, "ARM_OP_IMM", None) or capstone.CS_OP_IMM
    mem = getattr(capstone, "ARM_OP_MEM", None) or capstone.CS_OP_MEM
    return reg, imm, mem


def _shift_amount(op) -> int:
    shift = getattr(op, "shift", None)
    if shift is None:
        return 0
    value = getattr(shift, "value", None)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _literal_target(rom: bytes, insn, mode: str) -> int | None:
    """The pool address a pc-relative literal load reads, if any."""
    offset = insn.address - ROM_BASE
    if offset < 0 or offset + 4 > len(rom):
        return None
    word = int.from_bytes(rom[offset:offset + 4], "little")
    if mode == "arm":
        target = cl.arm_ldr_literal_target(word, insn.address)
    else:
        half = word & 0xFFFF
        target = cl.thumb1_ldr_literal_target(half, insn.address)
        if target is None and insn.address % 4 == 0:
            target = cl.thumb2_ldr_literal_target(word, insn.address)
    if target is None or not (ROM_BASE <= target < ROM_END):
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


def _carries_base(carriers: set, reg) -> bool:
    """True when ``reg`` has held the literal table base at some point.

    The base pointer is routinely copied (``mov r8, r0``) and the two branches
    of a function then write the same register, so a purely linear pass
    cannot always keep the copy alive.  Remembering the carriers keeps the
    classification honest without pretending to be a full CFG analysis.
    """
    return reg is not None and reg in carriers


def analyze_reader(rom: bytes, reader_addr: int, mode: str,
                   literal_value: int) -> dict:
    """Derive how ``reader_addr`` uses ``literal_value``.

    Returns the usage class, the deduced stride and the instructions that
    prove it.
    """
    result = {
        "reader": f"0x{reader_addr:08X}",
        "mode": mode,
        "function": None,
        "usage": "unknown",
        "detail": "",
        "stride": None,
        "strides": [],
        "evidence": [],
    }

    capstone = cl.load_capstone()
    OP_REG, OP_IMM, OP_MEM = _op_types(capstone)

    fn_start = cl.find_function_start(rom, reader_addr, mode)
    if fn_start is None:
        return result
    result["function"] = f"0x{fn_start:08X}"

    insns = cl.disassemble(rom, fn_start, FUNCTION_INSTRUCTIONS, mode)

    # A literal pool sits in the middle of a function and decodes as garbage
    # code.  Left in the stream it produces phantom "cmp"/"str" usages, so the
    # pool words are removed before the analysis runs.
    pool_addrs: set[int] = set()
    for insn in insns:
        target = _literal_target(rom, insn, mode)
        if target is not None:
            pool_addrs.add(target)
    insns = [insn for insn in insns if insn.address not in pool_addrs]

    try:
        reader_index = next(i for i, insn in enumerate(insns)
                            if insn.address == reader_addr)
    except StopIteration:
        return result

    state: dict[int, _Val] = {}
    carriers: set[int] = set()
    next_atom = [1]
    base_reg = None
    consumed = False

    def _set(reg, value: _Val) -> None:
        state[reg] = value
        if value.base:
            carriers.add(reg)

    for index, insn in enumerate(insns):
        ops = insn.operands
        mnemonic = insn.mnemonic

        if index == reader_index:
            # the reader itself: the loaded register now holds the base
            if ops and ops[0].type == OP_REG:
                base_reg = ops[0].reg
                _set(base_reg, _Val(const=literal_value, atoms={},
                                    scale=1.0, base=True))
            continue

        # --- a literal load seen *before* the reader: model it as a constant
        if mnemonic.startswith("ldr") and len(ops) >= 2 and ops[1].type == OP_MEM:
            mem = ops[1].mem
            if mem.base and insn.reg_name(mem.base).lower() in ("pc", "r15"):
                value = _literal_value(rom, insn, mode)
                if value is not None and ops[0].type == OP_REG:
                    _set(ops[0].reg, _Val(const=value, atoms={}, scale=1.0))
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
                    if mnemonic == "add" and _shift_amount(ops[2]):
                        right = _scale(right, 2 ** _shift_amount(ops[2]))
                elif ops[2].type == OP_IMM:
                    right = _Val(const=ops[2].imm)
                if left is not None and right is not None and \
                        (left.base or right.base):
                    other = right if left.base else left
                    result["evidence"].append(
                        f"{insn.address:08X}  {mnemonic} {insn.op_str}")
                    if other.atoms:
                        coeffs = other.coefficients()
                        result["usage"] = "indexed" if len(coeffs) == 1 \
                            else "indexed-2d"
                        result["detail"] = "base + " + " + ".join(
                            f"{c:g}*idx" for c in coeffs)
                        result["strides"] = coeffs
                        if coeffs and float(coeffs[0]).is_integer() \
                                and coeffs[0] >= 1:
                            result["stride"] = int(coeffs[0])
                    else:
                        result["usage"] = "deref"
                        result["detail"] = f"base + {other.const}"
                    consumed = True
            if not consumed and mnemonic.startswith("cmp"):
                if any(op.type == OP_REG and _carries_base(carriers, op.reg)
                       for op in ops):
                    result["usage"] = "compare"
                    result["detail"] = insn.op_str
                    result["evidence"].append(
                        f"{insn.address:08X}  {mnemonic} {insn.op_str}")
                    consumed = True
            if not consumed and mnemonic.startswith("str"):
                if any(op.type == OP_MEM and _carries_base(carriers, op.mem.base)
                       for op in ops):
                    result["usage"] = "store"
                    result["detail"] = insn.op_str
                    result["evidence"].append(
                        f"{insn.address:08X}  {mnemonic} {insn.op_str}")
                    consumed = True
            if not consumed and mnemonic.startswith("ldr"):
                for op in ops:
                    if op.type != OP_MEM or not _carries_base(carriers, op.mem.base):
                        continue
                    disp = op.mem.disp
                    result["usage"] = "deref"
                    result["detail"] = f"base + {disp}" if disp else "base"
                    result["evidence"].append(
                        f"{insn.address:08X}  {mnemonic} {insn.op_str}")
                    consumed = True
                    break
            if not consumed and mnemonic in ("blx", "bx"):
                if any(op.type == OP_REG and _carries_base(carriers, op.reg)
                       for op in ops):
                    result["usage"] = "call_target"
                    result["detail"] = insn.op_str
                    consumed = True

        # --- state update
        if mnemonic in ("mov", "movs", "movw") and len(ops) >= 2:
            if ops[1].type == OP_REG:
                _set(dst, state.get(ops[1].reg) or _unknown(next_atom[0]))
                if ops[1].reg not in state:
                    next_atom[0] += 1
            elif ops[1].type == OP_IMM:
                _set(dst, _Val(const=ops[1].imm))
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
            amount = ops[2].imm if ops[2].type == OP_IMM else _shift_amount(ops[2])
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
                if mnemonic == "add" and _shift_amount(ops[2]):
                    right = _scale(right, 2 ** _shift_amount(ops[2]))
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
        if mnemonic.startswith("ldr") and len(ops) >= 2 and ops[1].type == OP_MEM:
            mem = ops[1].mem
            if mem.base and insn.reg_name(mem.base).lower() in ("pc", "r15"):
                value = _literal_value(rom, insn, mode)
                if value is not None:
                    _set(dst, _Val(const=value, atoms={}, scale=1.0))
                    continue
            _set(dst, _unknown(next_atom[0]))
            next_atom[0] += 1
            continue
        if mnemonic.startswith("str"):
            continue
        # anything else clobbers the register as far as we are concerned
        _set(dst, _unknown(next_atom[0]))
        next_atom[0] += 1

    if not result["evidence"]:
        result["evidence"].append(
            f"{reader_addr:08X}  ldr -> 0x{literal_value:08X}")
    return result


# --------------------------------------------------------------------------
# neighbour search
# --------------------------------------------------------------------------
def live_literals(index: cl.LiteralIndex) -> list[int]:
    """Every value the ROM's code loads that points into the ROM image."""
    return sorted(v for v in index.readers
                  if ROM_BASE <= v < ROM_END)


def neighbours(index: cl.LiteralIndex, target: int, window: int) -> list[int]:
    lo, hi = target - window, target + window
    hits = [v for v in live_literals(index) if lo <= v <= hi]
    hits.sort(key=lambda v: (abs(v - target), v))
    return hits


def audit_names(evidence: dict) -> dict[str, str]:
    """Map ``0x08xxxxxx`` -> the audited table name, for the 54-table subset."""
    names: dict[str, str] = {}
    for key, table in (evidence.get("tables") or {}).items():
        names[key] = table.get("name") or key
    return names


def _parse_target(text: str) -> int:
    """Interpret a target as a ROM address or a ROM file offset."""
    value = int(text, 0)
    if value >= ROM_BASE:
        return value
    if value >= 0x02000000:          # EWRAM / IWRAM address
        return value
    return ROM_BASE + value


def _file_offset(address: int) -> str:
    if ROM_BASE <= address < ROM_END:
        return f"0x{address - ROM_BASE:06X}"
    return "n/a"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", nargs="?", type=pathlib.Path, default=DEFAULT_ROM,
                    help="ROM image (default: rom/base.gba)")
    ap.add_argument("--target", action="append", default=[],
                    help="base to triage (file offset or 0x08xxxxxx address); "
                         "may be repeated")
    ap.add_argument("--all-legacy", action="store_true",
                    help="triage every legacy bank base known to the audit")
    ap.add_argument("--window", type=lambda t: int(t, 0), default=0x400,
                    help="search radius in bytes (default 0x400)")
    ap.add_argument("--evidence", type=pathlib.Path, default=DEFAULT_EVIDENCE,
                    help="consumer evidence file (read-only, never rewritten)")
    ap.add_argument("--limit", type=int, default=12,
                    help="maximum neighbours printed per target")
    ap.add_argument("--json", type=pathlib.Path, default=None,
                    help="also write the report as JSON")
    args = ap.parse_args()

    if not args.rom.exists():
        print(f"error: ROM not found: {args.rom}", file=sys.stderr)
        return EXIT_USAGE
    if not args.evidence.exists():
        print(f"error: consumer evidence file not found: {args.evidence}\n"
              "       it is the digest anchor for this tool; it is read-only "
              "and must not be regenerated here.", file=sys.stderr)
        return EXIT_USAGE

    rom = args.rom.read_bytes()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))

    digest = hashlib.sha256(rom).hexdigest()
    expected = evidence.get("rom_sha256")
    if expected and digest != expected:
        print(f"error: ROM digest mismatch\n"
              f"       rom      : {digest}\n"
              f"       evidence : {expected}\n"
              "       the evidence file was generated against a different ROM; "
              "re-run tools/consumer_locate.py --evidence before trusting it.",
              file=sys.stderr)
        return EXIT_DIGEST

    index = cl.LiteralIndex(rom)
    names = audit_names(evidence)
    live = live_literals(index)

    targets: list[tuple[str, int]] = []
    for text in args.target:
        targets.append((text, _parse_target(text)))
    if args.all_legacy:
        for name, offset in sorted(cl.AUDIT_TABLES.items()):
            if name.startswith("legacy_"):
                targets.append((name, ROM_BASE + offset))
    if not targets:
        print("nothing to do: pass --target or --all-legacy", file=sys.stderr)
        return EXIT_USAGE

    report = {
        "rom": str(args.rom),
        "rom_sha256": digest,
        "window": args.window,
        "indexed_values": len(index.readers),
        "live_rom_literals": len(live),
        "evidence": str(args.evidence),
        "targets": [],
    }

    for label, target in targets:
        hits = neighbours(index, target, args.window)
        entry = {
            "name": label,
            "target": f"0x{target:08X}",
            "file_offset": _file_offset(target),
            "declared_base_readers": len(index.readers_of(target)),
            "neighbours": [],
        }
        for value in hits[: args.limit]:
            readers = sorted({addr for addr, _ in index.readers_of(value)})
            record = {
                "value": f"0x{value:08X}",
                "file_offset": _file_offset(value),
                "delta": value - target,
                "readers": len(readers),
                "readers_list": [f"0x{a:08X}" for a in readers],
                "audit_name": names.get(f"0x{value:08X}"),
            }
            if readers:
                reader_addr, mode = index.readers_of(value)[0]
                analysis = analyze_reader(rom, reader_addr, mode, value)
                record.update({
                    "reader": analysis["reader"],
                    "reader_mode": analysis["mode"],
                    "function": analysis["function"],
                    "usage": analysis["usage"],
                    "usage_detail": analysis["detail"],
                    "stride": analysis["stride"],
                    "strides": analysis["strides"],
                    "evidence": analysis["evidence"],
                })
            entry["neighbours"].append(record)
        report["targets"].append(entry)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8", newline="\n")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"ROM        : {args.rom}  sha256 {digest[:16]}...")
    print(f"index      : {len(index.readers)} literal values, "
          f"{len(live)} of them point into the ROM image")
    print(f"evidence   : {args.evidence} (read-only; 54-table audited subset)")
    print()

    for entry in report["targets"]:
        print(f"target {entry['target']}  (file {entry['file_offset']})  "
              f"name {entry['name']}")
        readers = entry["declared_base_readers"]
        if readers:
            print(f"  the declared base IS live: {readers} reader(s)")
        else:
            print("  the declared base is NOT live: the ROM never names it")
        print(f"  {'delta':>8}  {'literal':10} {'file off':>9} {'rd':>3}  "
              f"{'reader':10} {'function':10} {'usage':8} {'stride':>6}  name")
        for record in entry["neighbours"]:
            stride = record.get("stride")
            coeffs = record.get("strides") or []
            if len(coeffs) > 1:
                stride = "+".join(str(int(c)) for c in coeffs)
            print(f"  {record['delta']:+#8x}  {record['value']:10} "
                  f"{record['file_offset']:>9} {record['readers']:>3}  "
                  f"{record.get('reader') or '-':10} "
                  f"{record.get('function') or '-':10} "
                  f"{record.get('usage') or '-':8} "
                  f"{(str(stride) if stride else '-'):>6}  "
                  f"{record.get('audit_name') or '(outside the audited subset)'}")
            for line in record.get("evidence") or []:
                print(f"        {line}")
        print()

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
