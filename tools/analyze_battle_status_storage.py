#!/usr/bin/env python3
"""Bind the original battle unit's active and removed-status record storage."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
STATUS_LOOKUP = 0x0806C160
STATUS_LOOKUP_END = 0x0806C1A2
STATUS_LOOKUP_SHA256 = "bdcd8223eee67a911627f7fed9f241584b46dd3cfb2f1b5c59e6c5163ac6e2dd"
STATUS_REMOVE = 0x0806C1A4
STATUS_REMOVE_END = 0x0806C204
STATUS_REMOVE_SHA256 = "bc4814f073f78ad611386f79910f79c93e34ce0be8a8a4045ad0098165d1cee0"
STATUS_UPSERT = 0x0806C204
STATUS_UPSERT_END = 0x0806C308
STATUS_UPSERT_SHA256 = "fddf887db4c97e2d001e952eee0da2758b09cb2826073d6d8084e5910b33d82a"
UNIT_POOL = 0x020240C0
UNIT_STRIDE = 0x1D4
ACTIVE_BANK_OFFSET = 0xD4
REMOVED_EVENT_BANK_OFFSET = 0x154
RECORDS_PER_BANK = 16
RECORD_STRIDE = 8


def _offset(address: int) -> int:
    return address - ROM_BASE


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, _offset(address))[0]


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _expect_function_hash(
    rom: bytes,
    start: int,
    end: int,
    expected_sha256: str,
    label: str,
) -> None:
    body = rom[_offset(start) : _offset(end)]
    _expect(_sha256(body), expected_sha256, f"{label} SHA-256")


def build_status_storage_manifest(rom_path: Path | str) -> dict[str, Any]:
    rom = Path(rom_path).read_bytes()
    _expect_function_hash(
        rom,
        STATUS_LOOKUP,
        STATUS_LOOKUP_END,
        STATUS_LOOKUP_SHA256,
        "status lookup",
    )
    _expect_function_hash(
        rom,
        STATUS_REMOVE,
        STATUS_REMOVE_END,
        STATUS_REMOVE_SHA256,
        "status removal",
    )
    _expect_function_hash(
        rom,
        STATUS_UPSERT,
        STATUS_UPSERT_END,
        STATUS_UPSERT_SHA256,
        "status upsert",
    )

    # Each routine loads the same unit-pool base independently. This prevents a
    # matching byte pattern elsewhere from being accepted as the status API.
    _expect(_u32(rom, 0x0806C18C), UNIT_POOL, "lookup unit-pool literal")
    _expect(_u32(rom, 0x0806C1C8), UNIT_POOL, "remove unit-pool literal")
    _expect(_u32(rom, 0x0806C268), UNIT_POOL, "upsert unit-pool literal")
    _expect(
        REMOVED_EVENT_BANK_OFFSET + RECORDS_PER_BANK * RECORD_STRIDE,
        UNIT_STRIDE,
        "removed-event bank end",
    )
    _expect(
        ACTIVE_BANK_OFFSET + RECORDS_PER_BANK * RECORD_STRIDE,
        REMOVED_EVENT_BANK_OFFSET,
        "contiguous status banks",
    )

    return {
        "schema_version": 1,
        "identity": "battle_unit_active_and_removed_status_storage",
        "lookup": f"0x{STATUS_LOOKUP:08X}",
        "remove": f"0x{STATUS_REMOVE:08X}",
        "upsert": f"0x{STATUS_UPSERT:08X}",
        "unit_pool": f"0x{UNIT_POOL:08X}",
        "unit_stride": UNIT_STRIDE,
        "active_bank_offset": ACTIVE_BANK_OFFSET,
        "removed_event_bank_offset": REMOVED_EVENT_BANK_OFFSET,
        "records_per_bank": RECORDS_PER_BANK,
        "record_stride": RECORD_STRIDE,
        "record_fields": {
            "0x00": "status_code_with_flags",
            "0x01": "raw_parameter_1",
            "0x02": "duration_ticks",
            "0x03": "raw_parameter_3_low5",
            "0x04": "raw_parameter_4",
            "0x05": "unwritten_by_upsert",
            "0x06": "raw_parameter_6_u16",
        },
        "lookup_code_mask": 0x3F,
        "not_found": 0xFF,
        "lookup_policy": "first_active_slot_matching_low_6_code_bits",
        "remove_modes": {
            "0": "clear_active_record_without_removed_event_copy",
            "nonzero": "copy_full_record_to_first_free_removed_event_slot_if_available_then_clear_active_code",
        },
        "duration_encoding": "(raw_duration_low_7_bits * 2) as u8",
        "ordinary_code_policy": "replace_first_existing_low_6_code_match",
        "code_0x3f_policy": (
            "replace_only_when_existing_duration_is_nonzero_and_less_than_new_duration"
        ),
        "full_bank_result": 0xFF,
        "conclusion": (
            "Every unit owns one 16-record active-status bank followed by one "
            "16-record removed-status event bank. Expiry/removal mode can preserve "
            "the full record for later processing, while direct consumption only "
            "clears the active code."
        ),
        "boundary": (
            "The record storage, lookup mask, removal modes, duration encoding, and "
            "replacement policy are statically closed. Raw parameter meanings and "
            "status-code-specific gameplay effects remain unresolved."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("rom/base.gba"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("notes/battle-status-storage-bindings-20260723.json"),
    )
    args = parser.parse_args()
    result = build_status_storage_manifest(args.rom)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
