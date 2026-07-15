#!/usr/bin/env python3
"""Verify the code-referenced character growth table."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any


TABLE_SPECS = {
    "character-stats": {
        "bank": Path("sequel/content/character-stats/bank.json"),
        "offset": 0x545068,
        "entry_count": 63,
        "entry_size": 16,
        "fields": (
            "template_0e_growth",
            "template_08_growth",
            "template_02_growth",
            "template_03_growth",
            "template_04_growth",
            "template_05_growth",
            "template_06_growth",
            "unused_0e",
        ),
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_u16le(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<H", raw, offset)[0]


def validate_bank(
    bank: dict[str, Any], spec: dict[str, Any], rom: bytes | None = None
) -> dict[str, Any]:
    issues: list[str] = []
    table_offset = bank.get("table_offset")
    entry_count = bank.get("entry_count")
    entry_size = bank.get("entry_size")
    entries = bank.get("entries")
    expected_fields = spec["fields"]

    if table_offset != spec["offset"]:
        issues.append(f"table_offset must be 0x{spec['offset']:X}, got {table_offset!r}")
    if entry_count != spec["entry_count"]:
        issues.append(f"entry_count must be {spec['entry_count']}, got {entry_count!r}")
    if entry_size != spec["entry_size"]:
        issues.append(f"entry_size must be {spec['entry_size']}, got {entry_size!r}")
    if not isinstance(entries, list):
        issues.append("entries must be a list")
        entries = []
    elif len(entries) != spec["entry_count"]:
        issues.append(f"entries length must be {spec['entry_count']}, got {len(entries)}")

    fields = bank.get("entry_format", {}).get("fields", [])
    if not isinstance(fields, list):
        issues.append("entry_format.fields must be a list")
        fields = []
    field_names = tuple(field.get("name") for field in fields if isinstance(field, dict))
    if field_names != expected_fields:
        issues.append(f"field order mismatch: {field_names!r}")
    for expected_index, field in enumerate(fields):
        if not isinstance(field, dict):
            continue
        byte_offset = expected_index * 2
        if field.get("offset") != byte_offset or field.get("size") != 2:
            issues.append(
                f"field {field.get('name', expected_index)!r} must be u16 at +0x{byte_offset:X}"
            )

    entry_summaries = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"entry {index} is not an object")
            continue
        expected_raw_offset = spec["offset"] + index * spec["entry_size"]
        if entry.get("_raw_offset") != expected_raw_offset:
            issues.append(
                f"entry {index} _raw_offset must be 0x{expected_raw_offset:X}, got {entry.get('_raw_offset')!r}"
            )

        values = []
        for field_index, field_name in enumerate(expected_fields):
            value = entry.get(field_name)
            if not isinstance(value, int) or not (0 <= value <= 0xFFFF):
                issues.append(f"entry {index}.{field_name} must be a u16, got {value!r}")
                continue
            values.append(value)
            expected_hex = value.to_bytes(2, "little").hex()
            if entry.get(f"{field_name}_hex") != expected_hex:
                issues.append(
                    f"entry {index}.{field_name}_hex must be {expected_hex}, got {entry.get(f'{field_name}_hex')!r}"
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

    return {
        "ok": not issues,
        "issues": issues,
        "entry_count": len(entries),
        "entry_size": entry_size,
        "entries": entry_summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the character growth bank against a base ROM."
    )
    parser.add_argument(
        "--table",
        choices=sorted(TABLE_SPECS),
        action="append",
        help="Table to verify. Defaults to both tables.",
    )
    parser.add_argument("--rom", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Emit full JSON report")
    args = parser.parse_args()

    rom = args.rom.read_bytes() if args.rom else None
    selected = args.table or sorted(TABLE_SPECS)
    report = {"tables": {}}
    ok = True
    for name in selected:
        spec = TABLE_SPECS[name]
        table_report = validate_bank(load_json(spec["bank"]), spec, rom)
        report["tables"][name] = table_report
        ok = ok and table_report["ok"]
    report["ok"] = ok

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"character-stats verification: {'PASS' if ok else 'FAIL'}")
        for name, table_report in report["tables"].items():
            for issue in table_report["issues"]:
                print(f"{name}: {issue}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
