#!/usr/bin/env python3
"""Verify save descriptors and an optional raw 64KiB SRAM export."""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any

DEFAULT_BANK = Path("sequel/content/save-state/bank.json")
SRAM_ADVANCE_OVERHEAD = 0x14
RECORD_HEADER_LENGTH = 0x13


def save_checksum(data: bytes) -> int:
    return (~sum(data)) & 0xFF


def record_offsets(lengths: list[int]) -> list[int]:
    offsets, current = [], 0
    for length in lengths:
        offsets.append(current)
        current += length + SRAM_ADVANCE_OVERHEAD
    return offsets


def validate_bank(bank: dict[str, Any], rom: bytes | None = None) -> dict[str, Any]:
    issues: list[str] = []
    entries = bank.get("entries")
    if not isinstance(entries, list) or not entries:
        return {"ok": False, "issues": ["entries must be a non-empty list"], "entry_count": 0}
    table_offset = bank.get("table_offset")
    if bank.get("entry_size") != 8:
        issues.append("entry_size must be 8")
    if bank.get("entry_count") != len(entries):
        issues.append("entry_count does not match entries")
    lengths = []
    for index, entry in enumerate(entries):
        ewram = entry.get("ewram_buffer")
        length = entry.get("payload_length")
        if not isinstance(ewram, int) or not 0x02000000 <= ewram <= 0x0203FFFF:
            issues.append(f"entry {index} invalid EWRAM buffer")
            continue
        if not isinstance(length, int) or length <= 0:
            issues.append(f"entry {index} invalid payload length")
            continue
        lengths.append(length)
        expected_offset = record_offsets(lengths)[-1]
        if entry.get("sram_record_offset") != expected_offset:
            issues.append(f"entry {index} cumulative SRAM offset mismatch")
        if rom is not None and isinstance(table_offset, int):
            raw_offset = table_offset + index * 8
            actual = struct.unpack_from("<II", rom, raw_offset)
            if actual != (ewram, length):
                issues.append(f"entry {index} ROM mismatch at 0x{raw_offset:X}")
    offsets = record_offsets(lengths) if len(lengths) == len(entries) else []
    total_span = (offsets[-1] + lengths[-1] + SRAM_ADVANCE_OVERHEAD) if offsets else 0
    return {
        "ok": not issues,
        "issues": issues,
        "entry_count": len(entries),
        "payload_lengths": lengths,
        "record_offsets": offsets,
        "total_sram_span": total_span,
    }


def validate_sram_dump(bank: dict[str, Any], sram: bytes) -> dict[str, Any]:
    issues: list[str] = []
    records = []
    minimum = max(
        (entry["sram_record_offset"] + entry["payload_length"] + SRAM_ADVANCE_OVERHEAD
         for entry in bank.get("entries", [])), default=0,
    )
    if len(sram) not in (0x8000, 0x10000):
        issues.append(f"SRAM dump must be a 32768- or 65536-byte export, got {len(sram)}")
    if len(sram) < minimum:
        issues.append(f"SRAM dump is shorter than descriptor span {minimum} bytes")
    for entry in bank.get("entries", []):
        offset = entry["sram_record_offset"]
        length = entry["payload_length"]
        if offset + length + SRAM_ADVANCE_OVERHEAD > len(sram):
            issues.append(f"record at 0x{offset:04X} exceeds SRAM dump length")
            continue
        record = sram[offset:offset + length + SRAM_ADVANCE_OVERHEAD]
        header = record[:RECORD_HEADER_LENGTH]
        payload = record[RECORD_HEADER_LENGTH:RECORD_HEADER_LENGTH + length]
        observed = record[RECORD_HEADER_LENGTH + length]
        expected = save_checksum(payload)
        erased = all(byte == 0xFF for byte in record)
        valid = erased or expected == observed
        if not valid:
            issues.append(f"checksum mismatch at SRAM 0x{offset:04X}: expected 0x{expected:02X}, got 0x{observed:02X}")
        records.append({
            "descriptor_index": entry.get("descriptor_index"),
            "sram_offset": f"0x{offset:04X}",
            "payload_length": length,
            "header_hex": header.hex(),
            "erased": erased,
            "checksum": f"0x{observed:02X}",
            "expected_checksum": f"0x{expected:02X}",
            "valid": valid,
        })
    return {"ok": not issues, "issues": issues, "records": records}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--sram-dump", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    bank = json.loads(args.bank.read_text())
    report = {"bank_validation": validate_bank(bank, args.rom.read_bytes() if args.rom else None)}
    if args.sram_dump:
        report["sram_validation"] = validate_sram_dump(bank, args.sram_dump.read_bytes())
    report["ok"] = report["bank_validation"]["ok"] and report.get("sram_validation", {"ok": True})["ok"]
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"save-state verification: {'PASS' if report['ok'] else 'FAIL'}")
        for section in ("bank_validation", "sram_validation"):
            for issue in report.get(section, {}).get("issues", []):
                print(f"{section}: {issue}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
