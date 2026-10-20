#!/usr/bin/env python3
"""Locate how the game reaches a table that the ROM never *names*.

Why this tool exists
--------------------
The five legacy ``story*`` banks declare bases (``0x53636C`` .. ``0x53C3C0``)
that no instruction loads and no data pointer stores -- ``raw_occurrences``
of those 32-bit values is **zero** for all five.  A structure the ROM never
mentions cannot be reached by *naming* it, so either

  1. the game **computes** the address
     (``target == L + index*stride + imm``), or
  2. the game reaches it through a **data pointer chain** -- a pointer stored
     in some other table, from which the target is reached by a fixed offset
     (``target == P + off``, ``P`` stored in the ROM), or
  3. the "table" is not a table at all and the declared base is simply wrong.

This tool answers (1) and (2) mechanically for any target address.

**The candidate set is the FULL literal index, not the evidence file.**
``notes/evidence/consumer-evidence.json`` only holds the 54 tables the
completion audit cares about, while ``tools.consumer_locate.LiteralIndex``
holds every constant the ROM loads (18051 distinct values / 29920 reader
instructions; 1196 of those values point into the ROM and are therefore
*live*).  Sweeping the truncated 54-table file silently hides every candidate
outside those 54 -- exactly the trap that made the first pass of the
``story*`` investigation reach the wrong answer.  The evidence file is read
**read-only** here, and only for two things:

  * the **ROM SHA-256** (stale evidence must not be trusted), and
  * the already-known consumers of the 54 audited tables, for cross-reference.

Exit codes
----------
``0``  success
``2``  usage error (no target given)
``3``  **ROM digest mismatch** -- the ROM does not match the digest recorded
       in the evidence file; every conclusion would be stale.

Usage
-----
::

    python tools/story_table_locate.py rom/base.gba --target 0x53636C
    python tools/story_table_locate.py rom/base.gba --all-story
    python tools/story_table_locate.py rom/base.gba --target 0x53636C \\
        --neighbors 0x400 --json build/story-table-locate.json

``--target`` accepts an absolute ROM address (``0x08xxxxxx``) or a bare file
offset (``0x53636C``); both notations are printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from consumer_locate import (  # noqa: E402  (path set up above)
    LiteralIndex,
    ROM_BASE,
    disassemble,
    find_function_start,
    load_capstone,
    raw_occurrences,
)

EVIDENCE_PATH = REPO / "notes" / "evidence" / "consumer-evidence.json"

#: Strides the sweep tries.  The arithmetic sweep is the *exhaustive* half of
#: the search ("is there any (L, stride, index, imm) that explains the
#: target?"), so the stride space has to be enumerated rather than guessed.
STRIDE_CATALOG = (1, 2, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 48, 52, 56, 64,
                  80, 96, 128, 0xB4, 0xCC, 0x100, 0x180, 0x200)

#: Index ceiling used only for the "how many hits if the index bound is
#: ignored" statistic -- i.e. "could any literal at all explain this?".
UNBOUNDED_INDEX = 1 << 24

#: End of the ROM's code area.  Determined from the ROM itself: the last
#: real code lives at ~0x0809Dxxx and everything from 0x080A0000 on is
#: 0x0000 padding.  Used only to *label* a neighbouring literal as
#: "code-referenced" or "data-region only" -- the literal index itself
#: scans the whole ROM, so a "reader" inside a data region is a false
#: positive of the linear scan, not an instruction.
CODE_END = 0x080A0000

#: The five legacy ``story*`` banks, with the base each one *declares*.
STORY_BANKS = {
    "story": 0x53636C,
    "story-b": 0x536BC8,
    "story-c": 0x538FF0,
    "story-d": 0x53AB78,
    "story-e": 0x53C3C0,
}


# --------------------------------------------------------------------------
# ROM digest gate
# --------------------------------------------------------------------------
def verify_digest(rom: bytes) -> tuple[str, str | None]:
    """Compare the ROM digest with the one recorded in the evidence file.

    The evidence file is **read-only** here; it is never regenerated.
    """
    actual = hashlib.sha256(rom).hexdigest()
    expected: str | None = None
    if EVIDENCE_PATH.exists():
        try:
            with open(EVIDENCE_PATH, "r", encoding="utf-8") as handle:
                expected = json.load(handle).get("rom_sha256")
        except (OSError, ValueError):
            expected = None
    return actual, expected


# --------------------------------------------------------------------------
# literal index helpers
# --------------------------------------------------------------------------
def live_literals(index: LiteralIndex, rom_len: int) -> dict[int, list[tuple[int, str]]]:
    """Literals that point **into the ROM** -- i.e. real address constants.

    The literal index also holds RAM addresses, hardware register addresses
    and plain constants; only the ROM-range ones can be a table base, so the
    sweep works on this subset (1196 of 18051 for ``rom/base.gba``).
    """
    rom_end = ROM_BASE + rom_len
    return {value: readers for value, readers in index.readers.items()
            if ROM_BASE <= value < rom_end}


def stride_hits(delta: int, max_index: int, imm_span: int,
                strides: tuple[int, ...]) -> list[tuple[int, int, int]]:
    """All ``(stride, index, imm)`` with ``delta == index*stride + imm``.

    ``index`` is capped at ``max_index`` (a table longer than that is not a
    plausible explanation for a single address) and ``imm`` at
    ``+/- imm_span``.
    """
    out: list[tuple[int, int, int]] = []
    if delta <= 0:
        return out
    for stride in strides:
        # delta = index*stride + imm,  |imm| <= imm_span
        index = (delta + stride // 2) // stride
        if index < 1 or index > max_index:
            continue
        imm = delta - index * stride
        if -imm_span <= imm <= imm_span:
            out.append((stride, index, imm))
    return out


class ReaderFacts:
    """What a reader's own code says about the literal it loaded.

    Recognised idioms:
      * ``add rX, rY, rZ, lsl #n``              -> stride ``1 << n``
      * ``movs rT, #imm`` + ``muls rX, rT, rY``   -> stride ``imm``
      * ``lsls rY, rZ, #n`` + ``lsrs rY, rY, #m`` -> ``2**(n-m)``
      * ``adds rX, rY, #imm`` on the loaded register -> offset ``imm``
    """

    def __init__(self, rom: bytes):
        self.rom = rom
        self._cache: dict[tuple[int, str], dict] = {}

    def facts(self, reader_addr: int, mode: str) -> dict:
        key = (reader_addr, mode)
        if key in self._cache:
            return self._cache[key]
        result = {"function": None, "strides": {}, "offsets": {}}
        fn_start = find_function_start(self.rom, reader_addr, mode)
        if fn_start:
            result["function"] = fn_start
            try:
                capstone = load_capstone()
            except SystemExit:
                fn_start = None
            else:
                result.update(self._scan(disassemble(self.rom, fn_start, 96, mode),
                                         capstone, reader_addr))
        self._cache[key] = result
        return result

    def _scan(self, insns, capstone, reader_addr: int) -> dict:
        op_reg = getattr(capstone, "ARM_OP_REG", None) or capstone.CS_OP_REG
        op_imm = getattr(capstone, "ARM_OP_IMM", None) or capstone.CS_OP_IMM
        strides: dict[int, list[str]] = {}
        offsets: dict[int, list[str]] = {}
        immediates: dict[int, int] = {}
        shift_reg: dict[int, int] = {}
        aliases: set[int] = set()
        load_reg = None

        def note(table: dict, key: int, why: str) -> None:
            table.setdefault(key, []).append(why)

        for insn in insns:
            ops = insn.operands
            if not ops or ops[0].type != op_reg:
                continue
            mnemonic = insn.mnemonic
            where = f"0x{insn.address:08X}"

            if insn.address == reader_addr:
                load_reg = ops[0].reg
                aliases.add(load_reg)
                continue

            if mnemonic.startswith("mov") and len(ops) >= 2 and ops[1].type == op_reg:
                if ops[1].reg in aliases:
                    aliases.add(ops[0].reg)
                continue
            if mnemonic.startswith("mov") and len(ops) >= 2 and ops[1].type == op_imm:
                immediates[ops[0].reg] = ops[1].imm
                continue
            if mnemonic == "lsls" and len(ops) >= 3 and ops[2].type == op_imm:
                shift_reg[ops[0].reg] = ops[2].imm
                continue
            if mnemonic == "lsrs" and len(ops) >= 3 and ops[2].type == op_imm \
                    and ops[1].type == op_reg and ops[1].reg in shift_reg:
                shift = shift_reg[ops[1].reg] - ops[2].imm
                if shift >= 0:
                    note(strides, 1 << shift, f"{where}: lsls/lsrs pair")
                continue
            if mnemonic.startswith("add") and len(ops) >= 3:
                if ops[2].type == op_reg:
                    shift = getattr(ops[2], "shift", None)
                    amount = getattr(shift, "value", shift) if shift is not None else None
                    if isinstance(amount, int):
                        note(strides, 1 << amount, f"{where}: {mnemonic} ... lsl #{amount}")
                    elif ops[2].reg in shift_reg:
                        note(strides, 1 << shift_reg[ops[2].reg],
                             f"{where}: {mnemonic} {insn.op_str} (index scaled by "
                             f"lsl #{shift_reg[ops[2].reg]})")
                elif ops[2].type == op_imm:
                    if ops[1].type == op_reg and ops[1].reg in aliases and ops[2].imm:
                        note(offsets, ops[2].imm, f"{where}: {mnemonic} {insn.op_str}")
                    if ops[1].type == op_reg:
                        aliases.add(ops[0].reg)
                continue
            if mnemonic.startswith("mul") and len(ops) >= 3:
                for op in ops[1:]:
                    if op.type == op_reg and op.reg in immediates:
                        note(strides, immediates[op.reg], f"{where}: {mnemonic} {insn.op_str}")
                continue

        return {"strides": strides, "offsets": offsets}


# --------------------------------------------------------------------------
# raw-data neighbourhood scan
# --------------------------------------------------------------------------
def neighbourhood_pointers(rom: bytes, target: int, window: int,
                           live: dict) -> list[dict]:
    """Every u32 **stored in the ROM** that points into ``target +/- window``.

    This is how a data-pointer chain is found: the value the game
    dereferences (``P``) is usually stored in some *other* table, so scanning
    for the storage sites of the neighbourhood addresses reveals the hop that
    a literal-only sweep cannot see.
    """
    lo, hi = target - window, target + window
    wanted = set(range(lo & ~3, hi + 1, 4))
    hits: dict[int, list[int]] = {}
    unpack = struct.unpack_from
    for off in range(0, len(rom) - 3, 4):
        value = unpack("<I", rom, off)[0]
        if value in wanted:
            hits.setdefault(value, []).append(off)
    # nearest live literal below a storage site -> the table it sits in
    # (compared in *file offset* space: live literals are ROM addresses,
    #  storage sites are file offsets)
    bases = sorted(value - ROM_BASE for value in live)
    code_referenced = {value - ROM_BASE for value, readers in live.items()
                       if any(addr < CODE_END for addr, _ in readers)}

    def owning_table(site: int) -> str | None:
        lo_i = 0
        hi_i = len(bases) - 1
        best = None
        while lo_i <= hi_i:
            mid = (lo_i + hi_i) // 2
            if bases[mid] <= site:
                best = bases[mid]
                lo_i = mid + 1
            else:
                hi_i = mid - 1
        if best is None:
            return None
        tag = "code-referenced" if best in code_referenced else "data-region only"
        return f"0x{best + ROM_BASE:08X}+0x{site - best:X} ({tag})"

    out = []
    for value in sorted(hits):
        sites = hits[value]
        out.append({
            "value": f"0x{value:08X}",
            "file_offset": f"0x{value - ROM_BASE:06X}",
            "delta": value - target,
            "stored_at": [f"0x{o:06X}" for o in sites[:8]],
            "stored_at_count": len(sites),
            "owner_tables": sorted({owning_table(o) for o in sites if owning_table(o)}),
        })
    return out


# --------------------------------------------------------------------------
# per-target report
# --------------------------------------------------------------------------
def analyse_target(rom: bytes, index: LiteralIndex, live: dict, target: int,
                   args, facts: ReaderFacts) -> dict:
    report: dict = {
        "target": f"0x{target:08X}",
        "file_offset": f"0x{target - ROM_BASE:06X}",
    }

    # --- (a) literal reachability -------------------------------------
    feasible = 0
    corroborated: list[dict] = []
    for value, readers in live.items():
        delta = target - value
        if delta <= 0:
            continue
        feasible += len(stride_hits(delta, UNBOUNDED_INDEX, args.imm_span,
                                     STRIDE_CATALOG))
        for stride, index_no, imm in stride_hits(delta, args.max_index,
                                                 args.imm_span, STRIDE_CATALOG):
            for reader_addr, mode in readers:
                info = facts.facts(reader_addr, mode)
                why = info["strides"].get(stride)
                if not why:
                    # An offset coincidence alone is not a corroboration:
                    # `adds rX, rY, #4` happens everywhere and would match
                    # almost any target with an aligned offset.
                    continue
                off = info["offsets"].get(imm)
                corroborated.append({
                    "literal": f"0x{value:08X}",
                    "literal_file_offset": f"0x{value - ROM_BASE:06X}",
                    "reader": f"0x{reader_addr:08X}",
                    "reader_mode": mode,
                    "function": f"0x{info['function']:08X}" if info["function"] else None,
                    "stride": stride,
                    "index": index_no,
                    "imm": imm,
                    "delta": delta,
                    "stride_evidence": why or [],
                    "offset_evidence": off or [],
                })
    corroborated.sort(key=lambda h: (abs(h["imm"]), h["delta"]))
    report["literal_reachability"] = {
        "live_literals_scanned": len(live),
        "arithmetically_feasible": feasible,
        "corroborated_hits": len(corroborated),
        "hits": corroborated[:args.max_hits],
    }

    # --- (b) raw data -------------------------------------------------
    report["raw_occurrences"] = [f"0x{o:06X}" for o in raw_occurrences(rom, target)]
    report["neighbourhood"] = neighbourhood_pointers(rom, target, args.neighbors, live)

    return report


def print_report(report: dict) -> None:
    print(f"target {report['target']}  (file {report['file_offset']})")
    reach = report["literal_reachability"]
    print("  (a) literal reachability   target == L + index*stride + imm")
    print(f"      live literals scanned   : {reach['live_literals_scanned']} "
          f"(full index, ROM-range values)")
    print(f"      arithmetically feasible : {reach['arithmetically_feasible']} "
          f"(stride catalog only -- not discriminating on its own)")
    print(f"      corroborated by code    : {reach['corroborated_hits']}")
    for hit in reach["hits"]:
        print(f"        L={hit['literal']}  reader={hit['reader']} "
              f"({hit['reader_mode']})  fn={hit['function']}")
        print(f"          stride={hit['stride']} index={hit['index']} "
              f"imm={hit['imm']:+#x} delta={hit['delta']:+#x}")
        for why in hit["stride_evidence"]:
            print(f"          stride evidence: {why}")
        for why in hit["offset_evidence"]:
            print(f"          offset evidence: {why}")
    if not reach["hits"]:
        print("        (no live literal whose own code corroborates the "
              "stride/offset -> the literal form cannot explain this target)")
    print("  (b) raw data")
    occ = report["raw_occurrences"]
    print(f"      raw occurrences of the target itself: {len(occ)} "
          + " ".join(occ))
    if report["neighbourhood"]:
        print("      neighbourhood addresses that are stored elsewhere in the ROM:")
        for item in report["neighbourhood"]:
            owners = " ".join(item["owner_tables"][:3])
            print(f"        {item['value']} (file {item['file_offset']}, "
                  f"delta {item['delta']:+#x})")
            print(f"          stored at {' '.join(item['stored_at'])}"
                  + (f" (+{item['stored_at_count'] - 8} more)"
                     if item["stored_at_count"] > 8 else "")
                  + (f"   nearest live literal below: {owners}" if owners else ""))
    else:
        print("      (no neighbourhood address is stored anywhere in the ROM)")
    print()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_target(text: str) -> int:
    value = int(text, 0)
    if value >= ROM_BASE:
        return value
    return ROM_BASE + value


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", type=pathlib.Path)
    ap.add_argument("--target", action="append", default=[],
                    help="target address (file offset or 0x08xxxxxx)")
    ap.add_argument("--all-story", action="store_true",
                    help="analyse the five legacy story* banks")
    ap.add_argument("--neighbors", type=lambda x: int(x, 0), default=0x400,
                    help="half-width of the raw-data neighbourhood scan")
    ap.add_argument("--max-index", type=int, default=4096,
                    help="largest table index the reachability sweep accepts")
    ap.add_argument("--imm-span", type=lambda x: int(x, 0), default=0x40,
                    help="largest |imm| the reachability sweep accepts")
    ap.add_argument("--max-hits", type=int, default=24,
                    help="how many corroborated reachability hits to print")
    ap.add_argument("--json", type=pathlib.Path, default=None)
    ap.add_argument("--no-digest-check", action="store_true",
                    help="skip the ROM SHA-256 gate (not recommended)")
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    actual, expected = verify_digest(rom)
    if expected is None:
        print(f"warning: {EVIDENCE_PATH} has no rom_sha256; digest not checked",
              file=sys.stderr)
    elif actual != expected and not args.no_digest_check:
        print(f"ROM digest mismatch:\n  expected {expected}\n  actual   {actual}\n"
              f"{EVIDENCE_PATH} is stale for this ROM -- refusing to continue.",
              file=sys.stderr)
        return 3

    targets: list[tuple[str, int]] = []
    if args.all_story:
        for name, off in STORY_BANKS.items():
            targets.append((name, ROM_BASE + off))
    for text in args.target:
        targets.append((text, parse_target(text)))
    if not targets:
        print("nothing to do: pass --target or --all-story", file=sys.stderr)
        return 2

    index = LiteralIndex(rom)
    live = live_literals(index, len(rom))
    facts = ReaderFacts(rom)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"rom            : {args.rom}")
    print(f"sha256         : {actual}"
          + ("" if expected == actual else f"  (expected {expected})"))
    print(f"literal index  : {len(index.readers)} distinct values, "
          f"{sum(len(v) for v in index.readers.values())} reader instructions")
    print(f"live literals  : {len(live)} (values that point into the ROM)")
    print(f"sweep bounds   : index <= {args.max_index}, |imm| <= {args.imm_span}, "
          f"stride catalog {len(STRIDE_CATALOG)} entries, "
          f"neighbourhood +/- 0x{args.neighbors:X}")
    print()

    results = []
    for name, addr in targets:
        report = analyse_target(rom, index, live, addr, args, facts)
        report["name"] = name
        print_report(report)
        results.append(report)

    if args.json:
        from tools.lib.io import write_text
        payload = {
            "generated_by": "tools/story_table_locate.py",
            "rom": str(args.rom),
            "rom_sha256": actual,
            "indexed_values": len(index.readers),
            "live_literals": len(live),
            "sweep": {
                "max_index": args.max_index,
                "imm_span": args.imm_span,
                "stride_catalog": list(STRIDE_CATALOG),
                "neighbors": args.neighbors,
            },
            "targets": results,
        }
        write_text(args.json, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(f"json written: {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
