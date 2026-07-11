#!/usr/bin/env python3
"""Verify the reverse-engineered save-state table and optional SRAM records."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any


DEFAULT_BANK = Path("sequel/content/save-state/bank.json")
SRAM_OFFSET_DELTA = 0x14


def save_checksum(data: bytes) -> int:
    """Return the one-byte NOT(sum) checksum used by save records."""
    return (~sum(data)) & 0xFF


def real_sram_offset(sram_offset_field: int) -> int:
    return sram_offset_field + SRAM_OFFSET_DELTA


def read_u32le(raw: bytes, offset: int) -> int:
    return struct.unpack_from("<I", raw, offset)[0]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def hex_int(value: str) -> int:
    return int(value, 16)


def validate_bank(bank: dict[str, Any], rom: bytes | None = None) -> dict[str, Any]:
    issues: list[str] = []
    entries = bank.get("entries")
    unique_fields = bank.get("unique_save_fields")
    entry_size = bank.get("entry_size")
    table_offset = bank.get("table_offset")
    data_format = bank.get("data_format", {})
    data_bytes = data_format.get("data_bytes")
    checksum_bytes = data_format.get("checksum_bytes")
    data_size = bank.get("data_size_per_entry")

    if not isinstance(entries, list) or not entries:
        issues.append("entries must be a non-empty list")
        entries = []
    if not isinstance(unique_fields, list) or not unique_fields:
        issues.append("unique_save_fields must be a non-empty list")
        unique_fields = []
    if not isinstance(entry_size, int) or entry_size != 8:
        issues.append(f"entry_size must be 8, got {entry_size!r}")
    if not isinstance(table_offset, int) or table_offset < 0:
        issues.append(f"table_offset must be a non-negative integer, got {table_offset!r}")
    if data_bytes != 19 or checksum_bytes != 1 or data_size != 20:
        issues.append(
            "save record format must be 19 data bytes plus 1 checksum byte"
        )

    declared_count = bank.get("entry_count")
    if isinstance(declared_count, int) and declared_count != len(entries):
        issues.append(f"entry_count={declared_count} but entries has {len(entries)}")

    expected_unique_count = bank.get("unique_field_count")
    observed_pairs: set[tuple[int, int]] = set()
    entry_summaries = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            issues.append(f"entry {index} is not an object")
            continue
        ewram = entry.get("ewram_buffer")
        sram_field = entry.get("sram_offset_field")
        raw_offset = entry.get("_raw_offset", table_offset + index * entry_size)
        if not isinstance(ewram, int) or not (0x02000000 <= ewram <= 0x0203FFFF):
            issues.append(f"entry {index} has invalid EWRAM address {ewram!r}")
            continue
        if not isinstance(sram_field, int):
            issues.append(f"entry {index} has invalid SRAM offset field {sram_field!r}")
            continue
        real_offset = real_sram_offset(sram_field)
        if not (0 <= real_offset <= 0x10000 - 20):
            issues.append(f"entry {index} real SRAM offset 0x{real_offset:X} is out of range")
        observed_pairs.add((ewram, real_offset))
        entry_summaries.append(
            {
                "index": index,
                "rom_offset": f"0x{raw_offset:X}" if isinstance(raw_offset, int) else None,
                "ewram_buffer": f"0x{ewram:08X}",
                "sram_offset": f"0x{real_offset:04X}",
            }
        )

        if rom is not None and isinstance(table_offset, int) and isinstance(entry_size, int):
            expected_offset = table_offset + index * entry_size
            if expected_offset + 8 > len(rom):
                issues.append(f"entry {index} exceeds ROM length at 0x{expected_offset:X}")
                continue
            rom_ewram = read_u32le(rom, expected_offset)
            rom_sram_field = read_u32le(rom, expected_offset + 4)
            if rom_ewram != ewram or rom_sram_field != sram_field:
                issues.append(
                    "entry "
                    f"{index} ROM mismatch at 0x{expected_offset:X}: "
                    f"bank=(0x{ewram:08X},0x{sram_field:08X}) "
                    f"rom=(0x{rom_ewram:08X},0x{rom_sram_field:08X})"
                )

    field_pairs: set[tuple[int, int]] = set()
    for index, field in enumerate(unique_fields):
        if not isinstance(field, dict):
            issues.append(f"unique_save_fields[{index}] is not an object")
            continue
        try:
            sram_offset = hex_int(field["sram_offset"])
            ewram = hex_int(field["ewram_buffer"])
        except (KeyError, TypeError, ValueError) as exc:
            issues.append(f"unique_save_fields[{index}] has invalid hex fields: {exc}")
            continue
        field_pairs.add((ewram, sram_offset))

    if isinstance(expected_unique_count, int) and expected_unique_count != len(field_pairs):
        issues.append(
            f"unique_field_count={expected_unique_count} but unique_save_fields has {len(field_pairs)}"
        )
    if observed_pairs != field_pairs:
        missing = sorted(field_pairs - observed_pairs)
        extra = sorted(observed_pairs - field_pairs)
        if missing:
            issues.append(
                "unique_save_fields missing from entries: "
                + ", ".join(f"0x{ewram:08X}/0x{sram:04X}" for ewram, sram in missing)
            )
        if extra:
            issues.append(
                "entries contain undocumented unique fields: "
                + ", ".join(f"0x{ewram:08X}/0x{sram:04X}" for ewram, sram in extra)
            )

    return {
        "ok": not issues,
        "issues": issues,
        "entry_count": len(entries),
        "unique_entry_count": len(observed_pairs),
        "entries": entry_summaries,
    }


def validate_sram_dump(bank: dict[str, Any], sram: bytes) -> dict[str, Any]:
    issues: list[str] = []
    records = []
    if len(sram) != 0x10000:
        issues.append(f"SRAM dump must be 65536 bytes, got {len(sram)}")

    for field in bank.get("unique_save_fields", []):
        if not isinstance(field, dict):
            continue
        try:
            offset = hex_int(field["sram_offset"])
            ewram = hex_int(field["ewram_buffer"])
        except (KeyError, TypeError, ValueError):
            continue
        if offset + 20 > len(sram):
            issues.append(f"record at 0x{offset:04X} exceeds SRAM dump length")
            continue
        record = sram[offset:offset + 20]
        expected = save_checksum(record[:19])
        observed = record[19]
        valid = expected == observed
        if not valid:
            issues.append(
                f"checksum mismatch at SRAM 0x{offset:04X}: expected 0x{expected:02X}, got 0x{observed:02X}"
            )
        records.append(
            {
                "sram_offset": f"0x{offset:04X}",
                "ewram_buffer": f"0x{ewram:08X}",
                "checksum": f"0x{observed:02X}",
                "expected_checksum": f"0x{expected:02X}",
                "valid": valid,
            }
        )

    return {"ok": not issues, "issues": issues, "records": records}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify save-state bank metadata against ROM and optional SRAM dump."
    )
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--rom", type=Path, default=None)
    parser.add_argument("--sram-dump", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Emit full JSON report")
    args = parser.parse_args()

    bank = load_json(args.bank)
    rom = args.rom.read_bytes() if args.rom else None
    report = {"bank": str(args.bank), "bank_validation": validate_bank(bank, rom)}
    if args.sram_dump:
        report["sram_validation"] = validate_sram_dump(bank, args.sram_dump.read_bytes())

    ok = report["bank_validation"]["ok"] and report.get("sram_validation", {"ok": True})["ok"]
    report["ok"] = ok

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"save-state verification: {'PASS' if ok else 'FAIL'}")
        for issue in report["bank_validation"]["issues"]:
            print(f"bank: {issue}")
        if "sram_validation" in report:
            for issue in report["sram_validation"]["issues"]:
                print(f"sram: {issue}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
