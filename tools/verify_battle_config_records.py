#!/usr/bin/env python3
"""Verify the reverse-engineered battle-config data table."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any


DEFAULT_BANK = Path("sequel/content/battle-config/bank.json")
EXPECTED_TABLE_OFFSET = 0x545458
EXPECTED_ENTRY_COUNT = 32
EXPECTED_ENTRY_SIZE = 16
EXPECTED_FIELD_NAMES = (
    "config_id",
    "param1",
    "param2",
    "value",
    "flag1",
    "flag2",
    "flag3",
    "flag4",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_u16le(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<H", raw, offset)[0]


def validate_bank(bank: dict[str, Any], rom: bytes | None = None) -> dict[str, Any]:
    issues: list[str] = []
    table_offset = bank.get("table_offset")
    entry_count = bank.get("entry_count")
    entry_size = bank.get("entry_size")
    entries = bank.get("entries")

    if table_offset != EXPECTED_TABLE_OFFSET:
        issues.append(f"table_offset must be 0x{EXPECTED_TABLE_OFFSET:X}, got {table_offset!r}")
    if entry_count != EXPECTED_ENTRY_COUNT:
        issues.append(f"entry_count must be {EXPECTED_ENTRY_COUNT}, got {entry_count!r}")
    if entry_size != EXPECTED_ENTRY_SIZE:
        issues.append(f"entry_size must be {EXPECTED_ENTRY_SIZE}, got {entry_size!r}")
    if not isinstance(entries, list):
        issues.append("entries must be a list")
        entries = []
    elif len(entries) != EXPECTED_ENTRY_COUNT:
        issues.append(f"entries length must be {EXPECTED_ENTRY_COUNT}, got {len(entries)}")

    fields = bank.get("entry_format", {}).get("fields", [])
    if not isinstance(fields, list):
        issues.append("entry_format.fields must be a list")
        fields = []
    field_names = tuple(field.get("name") for field in fields if isinstance(field, dict))
    if field_names != EXPECTED_FIELD_NAMES:
        issues.append(f"field order mismatch: {field_names!r}")
    for expected_offset, field in enumerate(fields):
        if not isinstance(field, dict):
            continue
        byte_offset = expected_offset * 2
        if field.get("offset") != byte_offset or field.get("size") != 2:
            issues.append(
                f"field {field.get('name', expected_offset)!r} must be u16 at +0x{byte_offset:X}"
            )

    entry_summaries = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"entry {index} is not an object")
            continue
        raw_offset = entry.get("_raw_offset")
        expected_raw_offset = EXPECTED_TABLE_OFFSET + index * EXPECTED_ENTRY_SIZE
        if raw_offset != expected_raw_offset:
            issues.append(
                f"entry {index} _raw_offset must be 0x{expected_raw_offset:X}, got {raw_offset!r}"
            )

        values = []
        for field_index, field_name in enumerate(EXPECTED_FIELD_NAMES):
            value = entry.get(field_name)
            if not isinstance(value, int) or not (0 <= value <= 0xFFFF):
                issues.append(f"entry {index}.{field_name} must be a u16, got {value!r}")
                continue
            values.append(value)
            hex_value = entry.get(f"{field_name}_hex")
            expected_hex = value.to_bytes(2, "little").hex()
            if hex_value != expected_hex:
                issues.append(
                    f"entry {index}.{field_name}_hex must be {expected_hex}, got {hex_value!r}"
                )
            if rom is not None:
                rom_offset = expected_raw_offset + field_index * 2
                if rom_offset + 2 > len(rom):
                    issues.append(f"entry {index}.{field_name} exceeds ROM at 0x{rom_offset:X}")
                    continue
                rom_value = read_u16le(rom, rom_offset)
                if rom_value != value:
                    issues.append(
                        f"entry {index}.{field_name} mismatch at 0x{rom_offset:X}: "
                        f"bank=0x{value:04X} rom=0x{rom_value:04X}"
                    )

        entry_summaries.append(
            {
                "index": index,
                "rom_offset": f"0x{expected_raw_offset:X}",
                "values": [f"0x{value:04X}" for value in values],
            }
        )

    if entries:
        first = entries[0] if isinstance(entries[0], dict) else {}
        if any(first.get(name) != 0 for name in EXPECTED_FIELD_NAMES):
            issues.append("entry 0 must remain the null battle-config row")

    return {
        "ok": not issues,
        "issues": issues,
        "entry_count": len(entries),
        "entry_size": entry_size,
        "entries": entry_summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify battle-config bank metadata against a base ROM."
    )
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--rom", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Emit full JSON report")
    args = parser.parse_args()

    bank = load_json(args.bank)
    rom = args.rom.read_bytes() if args.rom else None
    report = {"bank": str(args.bank), "bank_validation": validate_bank(bank, rom)}
    report["ok"] = report["bank_validation"]["ok"]

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"battle-config verification: {'PASS' if report['ok'] else 'FAIL'}")
        for issue in report["bank_validation"]["issues"]:
            print(f"bank: {issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
