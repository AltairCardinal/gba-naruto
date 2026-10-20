#!/usr/bin/env python3
"""Audit the same-address (alias) conflicts between the legacy content banks.

Why this tool exists
--------------------
The legacy bank extraction produced several content banks that claim the
*same* ROM address under different names, and several banks whose claimed
identity the ROM does not support at all.  Completion condition **C1**
("身份唯一") and **C6** ("无待裁决冲突", `notes/completion-audit-20261020.md`
§1.1) are not satisfied by hiding those collisions -- they are satisfied by
*adjudicating* them:

  * `merge`   the two names describe ONE structure; one name is canonical,
              the other becomes a deprecated alias;
  * `split`   the two names describe DIFFERENT structures that happen to
              start nearby; each gets its own base;
  * `repoint` one name is simply wrong and is repointed to the real base;
  * `falsify` the name is a fabrication and is recorded as such instead of
              being given a fake base.

The decisions live in `tools/table_registry.py` (`CONFLICTS`, `ALIASES`,
`FALSIFIED`).  This tool is the mechanical check of those decisions:

  1. re-derive every same-address collision from the 32 `bank.json` files;
  2. re-derive the native consumer of every contested address **from the
     ROM** (whole-ROM literal index, `tools/consumer_locate.py`) and print
     the disassembly that proves what the data is;
  3. check the registry decision against those ROM-derived facts;
  4. check that no content bank disagrees with the registry;
  5. exit non-zero when a collision has no recorded decision, when a
     recorded decision contradicts the ROM, or when a bank and the
     registry disagree.

Usage
-----
    python tools/alias_audit.py rom/base.gba
    python tools/alias_audit.py rom/base.gba --json build/alias_audit.json

Exit codes
----------
    0  every collision is adjudicated and every check passed
    1  at least one unresolved collision, failed check or registry mismatch
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import struct
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _p in (REPO, REPO / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from tools import table_registry as registry  # noqa: E402
from consumer_locate import (  # noqa: E402
    ROM_BASE,
    LiteralIndex,
    disassemble,
    load_capstone,
    locate_consumers,
)

HEX_TOKEN = re.compile(r"0x[0-9A-Fa-f]+")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def hexs(value: int) -> str:
    return f"0x{value:X}"


def thumb_push_is_prologue(half: int) -> bool:
    """`push {regs, lr}` -- the LR bit is bit 8, not bit 7.

    `tools/consumer_locate.py::_is_thumb_prologue` tests bit 7, which is
    part of the register list, so it misses `push {r4, r5, lr}` (0xB530).
    We re-derive the enclosing function ourselves so the quoted
    instruction really belongs to the function we name.
    """
    if (half & 0xFF00) != 0xB500:
        return False
    return bool(half & 0x0100)


def find_function_start(rom: bytes, insn_addr: int, mode: str,
                        lookback: int = 0x2000) -> int | None:
    off = insn_addr - ROM_BASE
    if mode == "arm":
        addr = (off - 4) & ~3
        limit = max(0, off - lookback)
        while addr > limit:
            word = struct.unpack_from("<I", rom, addr)[0]
            if (word & 0xFFFF0000) == 0xE92D0000 and (word & 0x4000):
                return ROM_BASE + addr
            addr -= 4
        return None
    addr = (off - 2) & ~1
    limit = max(0, off - lookback)
    while addr > limit:
        half = struct.unpack_from("<H", rom, addr)[0]
        if thumb_push_is_prologue(half):
            return ROM_BASE + addr
        addr -= 2
    return None


def instruction_at(rom: bytes, addr: int, mode: str) -> str:
    """The single instruction at `addr`, formatted."""
    capstone = load_capstone()
    md = capstone.Cs(capstone.CS_ARCH_ARM,
                     capstone.CS_MODE_ARM if mode == "arm" else capstone.CS_MODE_THUMB)
    blob = rom[addr - ROM_BASE:addr - ROM_BASE + 8]
    for insn in md.disasm(blob, addr):
        return f"{insn.mnemonic} {insn.op_str}".strip()
    return "<undecodable>"


# ---------------------------------------------------------------------------
# collision detection
# ---------------------------------------------------------------------------
def detect_collisions(banks: dict[str, dict]) -> list[dict]:
    """Every address claimed by more than one bank."""
    by_base: dict[int, list[str]] = {}
    for bank, info in banks.items():
        offset = info.get("offset")
        if offset is None:
            continue
        by_base.setdefault(offset, []).append(bank)
    out = []
    for base, names in sorted(by_base.items()):
        if len(names) < 2:
            continue
        out.append({"address": base, "address_hex": hex(base), "banks": sorted(names)})
    return out


def detect_overlaps(banks: dict[str, dict]) -> list[dict]:
    """Windows that overlap without sharing a base address.

    Informational only: an overlap is not a same-address conflict, and the
    legacy set contains many of them.  They are printed so they cannot be
    mistaken for adjudicated facts.
    """
    ranges = []
    for bank, info in banks.items():
        offset = info.get("offset")
        if offset is None:
            continue
        count = info.get("entry_count") or 1
        size = info.get("entry_size") or 4
        ranges.append((bank, offset, offset + max(count, 1) * max(size, 1)))
    out = []
    for i, (bank_a, lo_a, hi_a) in enumerate(ranges):
        for bank_b, lo_b, hi_b in ranges[i + 1:]:
            if lo_a < hi_b and lo_b < hi_a and lo_a != lo_b:
                out.append({
                    "banks": sorted([bank_a, bank_b]),
                    "ranges": {bank_a: [hex(lo_a), hex(hi_a)],
                               bank_b: [hex(lo_b), hex(hi_b)]},
                })
    return out


# ---------------------------------------------------------------------------
# the ROM-derived evidence
# ---------------------------------------------------------------------------
def consumer_report(rom: bytes, index: LiteralIndex, address: int) -> dict:
    """Native readers of `address`, with the instruction that reads it."""
    readers = index.readers_of(ROM_BASE + address)
    rows = []
    for reader_addr, mode in readers:
        fn_start = find_function_start(rom, reader_addr, mode)
        rows.append({
            "reader": f"0x{reader_addr:08X}",
            "mode": mode,
            "function": f"0x{fn_start:08X}" if fn_start else None,
            "instruction": instruction_at(rom, reader_addr, mode),
        })
    return {
        "address": hex(address),
        "arm_address": f"0x{ROM_BASE + address:08X}",
        "reader_count": len(rows),
        "readers": rows,
    }


def run_checks(rom: bytes, index: LiteralIndex, checks: list[dict]) -> list[dict]:
    """Run the mechanical checks a registry decision declares."""
    results = []
    for check in checks:
        address = check["address"]
        readers = {r for r, _ in index.readers_of(ROM_BASE + address)}
        kind = check["kind"]
        if kind == "no_reader":
            ok = len(readers) == 0
            detail = (f"{hexs(address)} 必须没有原生读者，实际 {len(readers)} 个")
        elif kind == "reader":
            at = check.get("at")
            if at is not None:
                ok = at in readers
                detail = (f"0x{at:08X} 必须读 {hexs(address)}；"
                          f"实际该地址的读者 = "
                          + (", ".join(sorted(f"0x{r:08X}" for r in readers)) or "（无）"))
            else:
                ok = len(readers) >= check.get("min", 1)
                detail = (f"{hexs(address)} 至少要有 {check.get('min', 1)} 个原生读者，"
                          f"实际 {len(readers)} 个")
        else:
            ok = False
            detail = f"未知检查类型 {kind}"
        results.append({
            "kind": kind,
            "address": hexs(address),
            "at": f"0x{check['at']:08X}" if check.get("at") is not None else None,
            "why": check.get("why", ""),
            "passed": ok,
            "detail": detail,
        })
    return results


# ---------------------------------------------------------------------------
# the audit
# ---------------------------------------------------------------------------
def audit(rom_path: pathlib.Path) -> dict:
    rom = rom_path.read_bytes()
    index = LiteralIndex(rom)
    banks = registry.load_bank_meta()

    collisions = detect_collisions(banks)
    overlaps = detect_overlaps(banks)

    conflicts: list[dict] = []
    unresolved: list[str] = []
    failed_checks: list[str] = []

    for collision in collisions:
        key = collision["address_hex"].lower()
        decision = registry.CONFLICTS.get(key)
        entry = {
            "address": collision["address_hex"],
            "banks": collision["banks"],
            "verdict": None,
            "base_status": None,
            "canonical_bank": None,
            "canonical_address": None,
            "adjudicated": decision is not None,
            "evidence": "",
            "falsifiable_test": "",
            "dispositions": {},
            "consumers": {},
            "checks": [],
        }
        if decision is None:
            entry["verdict"] = "unresolved"
            unresolved.append(
                f"{collision['address_hex']} <- {', '.join(collision['banks'])}: "
                f"tools/table_registry.py 的 CONFLICTS 里没有这条裁决")
            conflicts.append(entry)
            continue

        entry["verdict"] = decision["verdict"]
        entry["base_status"] = decision.get("base_status")
        entry["canonical_bank"] = decision.get("canonical_bank")
        canonical = decision.get("canonical_address")
        entry["canonical_address"] = hexs(canonical) if canonical is not None else None
        entry["evidence"] = decision.get("evidence", "")
        entry["falsifiable_test"] = decision.get("falsifiable_test", "")
        entry["dispositions"] = decision.get("dispositions", {})

        entry["consumers"][collision["address_hex"]] = consumer_report(
            rom, index, collision["address"])
        if canonical is not None and canonical != collision["address"]:
            entry["consumers"][hexs(canonical)] = consumer_report(rom, index, canonical)
        for extra in decision.get("also_inspect", []):
            entry["consumers"][hexs(extra)] = consumer_report(rom, index, extra)

        checks = run_checks(rom, index, decision.get("checks", []))
        entry["checks"] = checks
        for check in checks:
            if not check["passed"]:
                failed_checks.append(f"{collision['address_hex']}: {check['detail']}")

        # The decision must still describe the collision we observed.
        if sorted(decision.get("banks", [])) != sorted(collision["banks"]) and \
                not set(decision.get("banks", [])) & set(collision["banks"]):
            unresolved.append(
                f"{collision['address_hex']} 的裁决记录了 "
                f"{decision.get('banks')}，但实际同址的是 {collision['banks']}")
        conflicts.append(entry)

    # Decisions that are not (or no longer) same-address collisions are still
    # part of the adjudication (e.g. the falsified Sappy bank); audit them
    # too so they cannot rot.
    for key, decision in sorted(registry.CONFLICTS.items()):
        if any(c["address"].lower() == key for c in conflicts):
            continue
        canonical = decision.get("canonical_address")
        checks = run_checks(rom, index, decision.get("checks", []))
        for check in checks:
            if not check["passed"]:
                failed_checks.append(f"{key}: {check['detail']}")
        consumers = {key: consumer_report(rom, index, int(key, 16))}
        if canonical is not None and canonical != int(key, 16):
            consumers[hexs(canonical)] = consumer_report(rom, index, canonical)
        for extra in decision.get("also_inspect", []):
            consumers[hexs(extra)] = consumer_report(rom, index, extra)
        conflicts.append({
            "address": key,
            "banks": decision.get("banks", []),
            "verdict": decision["verdict"],
            "base_status": decision.get("base_status"),
            "canonical_bank": decision.get("canonical_bank"),
            "canonical_address": hexs(canonical) if canonical is not None else None,
            "adjudicated": True,
            "evidence": decision.get("evidence", ""),
            "falsifiable_test": decision.get("falsifiable_test", ""),
            "dispositions": decision.get("dispositions", {}),
            "consumers": consumers,
            "checks": checks,
            "note": "非同址冲突（身份被证伪 / 基址被修正），一并复核",
        })

    # registry vs banks
    verify = registry.verify_table_bases()
    mismatches = verify["mismatches"]

    return {
        "rom": str(rom_path),
        "banks_checked": len(banks),
        "literal_index": {
            "distinct_values": len(index.readers),
            "reader_instructions": sum(len(v) for v in index.readers.values()),
        },
        "collisions": collisions,
        "overlaps": overlaps,
        "conflicts": conflicts,
        "unresolved": unresolved,
        "failed_checks": failed_checks,
        "registry_mismatches": mismatches,
        "registry_rows_checked": verify["banks_checked"],
        "registry_alias_conflicts": verify["alias_conflicts"],
        "aliases": registry.ALIASES,
        "falsified": registry.FALSIFIED,
    }


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def print_report(report: dict) -> None:
    out = sys.stdout
    out.reconfigure(encoding="utf-8", errors="replace")

    print(f"ROM            : {report['rom']}")
    print(f"content banks  : {report['banks_checked']}")
    print(f"literal index  : {report['literal_index']['distinct_values']} 个常量被 "
          f"{report['literal_index']['reader_instructions']} 条指令引用")
    print()

    print("同址冲突（原始碰撞，裁决记录在 tools/table_registry.py 的 CONFLICTS）")
    print(f"{'地址':<12} {'冲突的 bank':<40} {'裁决':<10} {'基址状态':<18} "
          f"{'裁决后权威基址':<14} 状态")
    print("-" * 112)
    for conflict in report["conflicts"]:
        banks = ", ".join(conflict["banks"])
        canonical = conflict["canonical_address"] or "（无基址）"
        state = "已裁决" if conflict["adjudicated"] else "未裁决"
        if not conflict["checks"] or all(c["passed"] for c in conflict["checks"]):
            state += " / 检查通过"
        else:
            state += " / 检查失败"
        print(f"{conflict['address']:<12} {banks:<40} {conflict['verdict']:<10} "
              f"{str(conflict['base_status']):<18} {canonical:<14} {state}")
    print()

    for conflict in report["conflicts"]:
        print(f"=== {conflict['address']}  [{conflict['verdict']}] "
              f"banks: {', '.join(conflict['banks'])}")
        for bank, disposition in sorted(conflict["dispositions"].items()):
            print(f"    {bank:<18} {disposition}")
        for address, consumers in conflict["consumers"].items():
            if consumers["reader_count"] == 0:
                print(f"    消费者 {address:<12} 无原生读者"
                      f"（这正是该裁决的判据之一）")
                continue
            print(f"    消费者 {address:<12} {consumers['reader_count']} 个原生读者")
            for reader in consumers["readers"][:6]:
                print(f"        {reader['reader']}  fn {reader['function']}  "
                      f"{reader['instruction']}")
        for check in conflict["checks"]:
            mark = "PASS" if check["passed"] else "FAIL"
            print(f"    [{mark}] {check['kind']:<10} {check['address']:<12} "
                  f"{check['detail']}")
            if check["why"]:
                print(f"           理由: {check['why']}")
        if conflict.get("evidence"):
            print(f"    证据: {conflict['evidence']}")
        if conflict.get("falsifiable_test"):
            print(f"    判死检验: {conflict['falsifiable_test']}")
        print()

    if report["overlaps"]:
        print("重叠窗口（信息项：不是同址冲突，未纳入本次裁决）")
        for overlap in report["overlaps"]:
            print(f"    {', '.join(overlap['banks'])}  {overlap['ranges']}")
        print()

    print(f"registry-vs-bank 不一致: {len(report['registry_mismatches'])}")
    for mismatch in report["registry_mismatches"]:
        print(f"    {mismatch}")
    print(f"未裁决冲突: {len(report['unresolved'])}")
    for item in report["unresolved"]:
        print(f"    {item}")
    print(f"失败的判死检验: {len(report['failed_checks'])}")
    for item in report["failed_checks"]:
        print(f"    {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("rom", type=pathlib.Path, help="path to the GBA ROM")
    parser.add_argument("--json", type=pathlib.Path, default=None,
                        help="write the machine-readable report here")
    args = parser.parse_args()

    report = audit(args.rom)
    print_report(report)

    if args.json:
        from tools.lib.io import write_json
        write_json(args.json, report)

    failed = bool(report["unresolved"] or report["failed_checks"]
                  or report["registry_mismatches"])
    print()
    print("RESULT:", "FAIL" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
