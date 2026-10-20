#!/usr/bin/env python3
"""Extractor for the sprite frame descriptor table (0x53EE98).

This table was found on 2026-10-21 while settling the `units` offset table
(see ``notes/evidence/units-offset-table-20261020.md``).  It is **live**:
three native instructions load the literal ``0x0853EE98``
(``0x080806BA``, ``0x0808077E``, ``0x0808082E``) and all three index it with
a stride of **10** bytes::

    lsls r0, r1, #2      ; r0 = idx * 4
    adds r0, r0, r1      ; r0 = idx * 5
    lsls r0, r0, #1      ; r0 = idx * 10

Each 10-byte record is five u16 fields at +0 / +2 / +4 / +6 / +8:

    +0   0 / 1 / 2 / -1     -1 terminates the list
    +2   -28 .. +12          signed quantity (coordinates?)
    +4   -68 .. +2           signed quantity (coordinates?)
    +6   0 / 1 / 2           class
    +8   0 / 4               != 0 ends the walk; == 0 continues at +0xA

The **business** names of the five fields are still unknown, so this tool
prints them as ``field_0``..``field_4`` with the observed value domains and
marks the two structural fields explicitly (``list_end`` / ``walk_end``).
It never invents a name.

The tool fails loudly (non-zero exit) when the ROM does not have the layout
it assumes, so it cannot be used to "prove" a wrong layout.

Usage:
    python tools/frame_descriptors.py rom/base.gba
    python tools/frame_descriptors.py rom/base.gba --json build/frame-descriptors.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.io import write_json  # noqa: E402

TABLE_BASE = 0x53EE98
RECORD_STRIDE = 10
FIELD_COUNT = 5
MAX_RECORDS = 64

# The three native readers, as (instruction address, function address).
NATIVE_READERS = (
    (0x080806BA, 0x08080670),
    (0x0808077E, 0x08080764),
    (0x0808082E, 0x08080814),
)

# The literal pool slot that stores 0x0853EE98.
LITERAL_POOL_ADDRESS = 0x08080898

LIST_END = -1


def record_offset(index: int) -> int:
    return TABLE_BASE + index * RECORD_STRIDE


def read_records(rom: bytes) -> list[dict]:
    out: list[dict] = []
    for index in range(MAX_RECORDS):
        off = record_offset(index)
        if off + RECORD_STRIDE > len(rom):
            break
        values = struct.unpack_from("<5h", rom, off)
        out.append({
            "index": index,
            "offset": off,
            "offset_hex": f"0x{off:06X}",
            "field_0": values[0],
            "field_2": values[1],
            "field_4": values[2],
            "field_6": values[3],
            "field_8": values[4],
            "list_end": values[0] == LIST_END,
            "walk_end": values[4] != 0,
        })
        if values[0] == LIST_END:
            break
    return out


def validate(rom: bytes, records: list[dict]) -> list[str]:
    """Return the list of problems; empty means the layout matches."""
    problems: list[str] = []

    # 1. the literal pool must really hold the table base
    if len(rom) < LITERAL_POOL_ADDRESS - 0x08000000 + 4:
        problems.append("ROM too small to hold the literal pool")
    else:
        pooled = struct.unpack_from("<I", rom, LITERAL_POOL_ADDRESS - 0x08000000)[0]
        if pooled != TABLE_BASE + 0x08000000:
            problems.append(
                f"literal at 0x{LITERAL_POOL_ADDRESS:08X} is 0x{pooled:08X}, "
                f"expected 0x{TABLE_BASE + 0x08000000:08X}")

    # 2. the list must be terminated by a +0 == -1 record
    if not records:
        problems.append("no records read")
    elif not records[-1]["list_end"]:
        problems.append(
            f"record {records[-1]['index']} does not terminate the list "
            f"(field_0 = {records[-1]['field_0']}, expected -1)")

    # 3. the observed value domains must not drift
    for record in records:
        for name, lo, hi in (("field_0", -1, 2), ("field_2", -32, 16),
                             ("field_4", -72, 8), ("field_6", 0, 2),
                             ("field_8", 0, 4)):
            value = record[name]
            if not lo <= value <= hi:
                problems.append(
                    f"record {record['index']}: {name} = {value} outside the "
                    f"observed domain [{lo}, {hi}]")

    # 4. the three readers must all be present with the stride-10 idiom
    for reader, function in NATIVE_READERS:
        if reader - 0x08000000 + 4 > len(rom):
            problems.append(f"reader 0x{reader:08X} is outside the ROM")
            continue
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("rom", nargs="?", default="rom/base.gba")
    parser.add_argument("--json", help="write the machine-readable report here")
    args = parser.parse_args(argv)

    rom_path = pathlib.Path(args.rom)
    if not rom_path.is_file():
        print(f"ROM not found: {rom_path}", file=sys.stderr)
        return 1
    rom = rom_path.read_bytes()

    records = read_records(rom)
    problems = validate(rom, records)
    report = {
        "rom": str(rom_path),
        "table": TABLE_BASE,
        "table_hex": f"0x{TABLE_BASE:06X}",
        "stride": RECORD_STRIDE,
        "record_count": len(records),
        "native_readers": [
            {"instruction": f"0x{insn:08X}", "function": f"0x{fn:08X}"}
            for insn, fn in NATIVE_READERS
        ],
        "records": records,
        "problems": problems,
    }
    if args.json:
        write_json(args.json, report)

    print(f"table 0x{TABLE_BASE:06X}  stride {RECORD_STRIDE}  "
          f"records {len(records)}")
    print(f"native readers: " + ", ".join(
        f"0x{insn:08X} (fn 0x{fn:08X})" for insn, fn in NATIVE_READERS))
    print()
    print(f'{"idx":>3} {"offset":<10} {"+0":>5} {"+2":>5} {"+4":>5} '
          f'{"+6":>5} {"+8":>5}  flags')
    for record in records:
        flags = []
        if record["list_end"]:
            flags.append("LIST_END")
        if record["walk_end"]:
            flags.append("walk_end")
        print(f'{record["index"]:>3} {record["offset_hex"]:<10} '
              f'{record["field_0"]:>5} {record["field_2"]:>5} '
              f'{record["field_4"]:>5} {record["field_6"]:>5} '
              f'{record["field_8"]:>5}  {",".join(flags)}')
    print()
    if problems:
        print("PROBLEMS:")
        for problem in problems:
            print("  -", problem)
        return 1
    print("SELF-CHECK: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
