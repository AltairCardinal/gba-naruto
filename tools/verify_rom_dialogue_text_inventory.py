#!/usr/bin/env python3
"""Verify dialogue inventory claims directly against the fixed base ROM.

The exporter constructs an artifact from ROM bytes.  This verifier deliberately
uses the opposite data flow: it treats every artifact field as an untrusted
claim, derives the corresponding table slot and NUL-terminated range from the
ROM, and checks the claim in place.  It never reconstructs a replacement
payload or manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-dialogue-text-inventory-v1"
VERIFY_SCHEMA = "rom-dialogue-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_START = 0x461CE4
TABLE_END = 0x4634B8
TABLE_SHA256 = "5b36c67620030d5ccc8795a2a260aca604d90fad4a49f7c7cb9d4c7cdc63c73f"
BUNDLE_SHA256 = "7509a63b2f892ea9f2892ed4cc703da72457247df148a1435edbbee8b2d95569"
ROW_COUNT = 305
ROW_SIZE = 20
TARGET_SLOTS = ("primary", "label_0", "label_1", "label_2")
PAYLOAD_NAME = "dialogue-text-inventory.json"
TABLE_NAME = "pointer-table.bin"
BUNDLE_NAME = "direct-nul-targets.bin"
EXPECTED_FILES = {PAYLOAD_NAME, TABLE_NAME, BUNDLE_NAME, "manifest.json"}
EXPECTED_SUMMARY = {
    "table_row_count": 305,
    "table_byte_count": 6_100,
    "sentinel_count": 305,
    "direct_pointer_slot_count": 1_220,
    "direct_target_count": 1_220,
    "unique_target_count": 1_220,
    "duplicate_target_count": 0,
    "overlapping_target_range_count": 0,
    "direct_target_bytes": 18_207,
    "target_payload_bytes": 16_987,
    "newline_target_count": 170,
    "newline_count": 203,
}
SCOPE = {
    "fixed_table_structure_complete": True,
    "direct_target_extraction_complete": True,
    "consumer_and_nul_protocol_bound": True,
    "all_rows_runtime_reachability_complete": False,
    "label_selector_upstream_bounds_complete": False,
    "natural_language_decoding_complete": False,
}
LIMITATIONS = [
    "one confirmed group-selection path uses u8; no path-level evidence proves runtime reachability of every row 0..304",
    "label selector values 0..2 are an upstream invariant not checked in this function",
    "raw game glyph codes are not claimed to be correctly decoded natural-language text",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _addr(value: int) -> str:
    return f"0x{value:08X}"


def _decode_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _check_bl(rom: bytes, offset: int, target: int) -> None:
    first, second = struct.unpack_from("<HH", rom, offset)
    if _decode_bl(ROM_BASE + offset, first, second) != target:
        raise ValueError(f"consumer BL changed at 0x{ROM_BASE + offset:08X}")


def _verify_consumer_contract(rom: bytes, claimed: object) -> None:
    windows = {
        (0x8F9E2, 0x8F9F4): "0320012101f077fd7ee70320002101f072fd",
        (0x917B0, 0x917C6): "4d4a0f92119b1a93504619900c99002901d14a4a0f92",
        (0x91950, 0x9195E): "f95e8800401880000f9908181090",
        (0x919DA, 0x919EC): "109a50680221009100210b9a0023d4f7b6fe",
        (0x66788, 0x6678E): "4946fff76ffd",
        (0x66302, 0x6630A): "b17c05aafff73dfe",
        (0x6671C, 0x66728): "079a1078002800d0abe50798",
        (0x65FB8, 0x65FC2): "1b18201c311cfff77bff",
    }
    for (start, end), expected in windows.items():
        if rom[start:end].hex() != expected:
            raise ValueError(f"consumer window changed at 0x{ROM_BASE + start:08X}")
    if struct.unpack_from("<I", rom, 0x918E8)[0] != ROM_BASE + TABLE_START:
        raise ValueError("table literal changed")
    if struct.unpack_from("<I", rom, 0x918EC)[0] != 0x08459284:
        raise ValueError("alternate table literal changed")
    for callsite, target in (
        (0x8F9E6, 0x080914D8),
        (0x8F9F0, 0x080914D8),
        (0x919E8, 0x08066758),
        (0x6678A, 0x0806626C),
        (0x66306, 0x08065F84),
        (0x65FBE, 0x08065EB8),
    ):
        _check_bl(rom, callsite, target)
    hashes = {
        "parser_sha256": (
            0x6626C,
            0x66736,
            "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be",
        ),
        "glyph_wrapper_sha256": (
            0x65F84,
            0x66034,
            "7e4316e63cbb44d09b26c7cc6592c580b83af0b328098c67669db1b05d1c784c",
        ),
        "glyph_expander_sha256": (
            0x65EB8,
            0x65F82,
            "354ace23de93d27679e6749fd3ea5d2f39608e85a5abd10eb767f47e418abb47",
        ),
        "label_loop_sha256": (
            0x91A20,
            0x91A68,
            "2746339b568a82686da18aaa91e1a2b818555ec44946650d8345e85536cdcafc",
        ),
    }
    expected: dict[str, Any] = {
        "entry_calls": ["0x0808F9E2", "0x0808F9EC"],
        "table_literal_load": "0x080917B0",
        "table_literal": "0x080918E8",
        "table_base": _addr(ROM_BASE + TABLE_START),
        "row_index_formula": "0x08091950",
        "primary_pointer_load": "0x080919DA",
        "text_object_wrapper": "0x08066758",
        "nul_terminated_parser": "0x0806626C",
        "glyph_wrapper": "0x08065F84",
        "glyph_expander": "0x08065EB8",
        "confirmed_address_formula": "table_base + group_index * 20",
        "confirmed_primary_field_offset": 4,
        "nul_termination_check": "0x0806671C..0x08066726",
    }
    for key, (start, end, expected_hash) in hashes.items():
        if _sha(rom[start:end]) != expected_hash:
            raise ValueError(f"consumer {key} changed")
        expected[key] = expected_hash
    if claimed != expected:
        raise ValueError("consumer evidence differs from ROM contract")


def _expected_implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            (root / "tools/export_rom_dialogue_text_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_dialogue_text_inventory.py").read_bytes()
        ),
    }


def _verify_payload_metadata(
    root: Path,
    payload: object,
    payload_raw: bytes,
    table_raw: bytes,
    bundle_raw: bytes,
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("inventory is not an object")
    if payload_raw != (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode():
        raise ValueError("inventory JSON is not canonical")
    if payload.get("schema") != SCHEMA:
        raise ValueError("inventory schema changed")
    if payload.get("implementation") != _expected_implementation(root):
        raise ValueError("inventory implementation binding changed")
    if payload.get("rom") != {
        "path": ROM_PATH.as_posix(),
        "size": 6_291_456,
        "sha256": ROM_SHA256,
    }:
        raise ValueError("inventory ROM identity changed")
    if payload.get("table") != {
        "file_range": [TABLE_START, TABLE_END],
        "gba_range": [_addr(ROM_BASE + TABLE_START), _addr(ROM_BASE + TABLE_END)],
        "row_size": ROW_SIZE,
        "row_count": ROW_COUNT,
        "word_layout": [
            "zero_sentinel",
            "primary_text_pointer",
            "label_0_text_pointer",
            "label_1_text_pointer",
            "label_2_text_pointer",
        ],
        "sha256": TABLE_SHA256,
    }:
        raise ValueError("inventory table metadata changed")
    if payload.get("scope") != SCOPE or payload.get("limitations") != LIMITATIONS:
        raise ValueError("inventory scope or limitations changed")
    if payload.get("files") != {
        TABLE_NAME: {"size": len(table_raw), "sha256": _sha(table_raw)},
        BUNDLE_NAME: {"size": len(bundle_raw), "sha256": _sha(bundle_raw)},
    }:
        raise ValueError("inventory file metadata changed")


def _verify_promotion_manifest(
    root: Path,
    manifest: object,
    payload_raw: bytes,
    table_raw: bytes,
    bundle_raw: bytes,
) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("promotion manifest is not an object")
    implementation = _expected_implementation(root)
    expected_report = {
        "schema": VERIFY_SCHEMA,
        "verified": True,
        **EXPECTED_SUMMARY,
        "errors": [],
    }
    expected = {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {
            PAYLOAD_NAME: _sha(payload_raw),
            BUNDLE_NAME: _sha(bundle_raw),
            TABLE_NAME: _sha(table_raw),
        },
        "scope": SCOPE,
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_dialogue_text_inventory.py",
                "--root",
                ".",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **implementation,
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_dialogue_text_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": implementation["verifier_sha256"],
            "exit_code": 0,
            "report": expected_report,
        },
    }
    if manifest != expected:
        raise ValueError("promotion manifest bindings changed")


def _verify_rows_against_rom(
    payload: dict[str, Any], rom: bytes, table_raw: bytes, bundle_raw: bytes
) -> dict[str, int]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != ROW_COUNT:
        raise ValueError("inventory row denominator changed")
    if len(table_raw) != ROW_COUNT * ROW_SIZE:
        raise ValueError("pointer table size changed")

    pointers: list[int] = []
    ranges: list[tuple[int, int]] = []
    packed_cursor = 0
    target_payload_bytes = 0
    newline_count = 0
    newline_target_count = 0
    target_id = 0
    for row_id, (words, row) in enumerate(
        zip(struct.iter_unpack("<5I", table_raw), rows, strict=True)
    ):
        row_start = TABLE_START + row_id * ROW_SIZE
        if (
            not isinstance(row, dict)
            or row.get("row_id") != row_id
            or row.get("table_range") != [row_start, row_start + ROW_SIZE]
            or row.get("sentinel") != 0
            or words[0] != 0
        ):
            raise ValueError(f"row {row_id} table identity changed")
        targets = row.get("targets")
        if not isinstance(targets, list) or len(targets) != 4:
            raise ValueError(f"row {row_id} target denominator changed")
        for slot_index, (pointer, target) in enumerate(
            zip(words[1:], targets, strict=True)
        ):
            if not isinstance(target, dict):
                raise ValueError(f"row {row_id} target schema changed")
            start = pointer - ROM_BASE
            if not 0x459414 <= start < TABLE_START:
                raise ValueError(f"row {row_id} target pointer escapes text bank")
            try:
                end = rom.index(b"\0", start, TABLE_START) + 1
            except ValueError as error:
                raise ValueError(f"row {row_id} target has no NUL") from error
            raw = rom[start:end]
            payload_bytes = raw[:-1]
            if any(value < 0x20 and value != 0x0A for value in payload_bytes):
                raise ValueError(f"row {row_id} target control byte changed")
            linefeeds = payload_bytes.count(0x0A)
            packed_end = packed_cursor + len(raw)
            table_offset = row_start + (slot_index + 1) * 4
            if (
                target.get("target_id") != target_id
                or target.get("slot") != TARGET_SLOTS[slot_index]
                or target.get("table_offset") != table_offset
                or target.get("pointer") != _addr(pointer)
                or target.get("range") != [start, end]
                or target.get("gba_range")
                != [_addr(ROM_BASE + start), _addr(ROM_BASE + end)]
                or target.get("packed_range") != [packed_cursor, packed_end]
                or target.get("size") != len(raw)
                or target.get("payload_size") != len(payload_bytes)
                or target.get("newline_count") != linefeeds
                or target.get("bytes_sha256") != _sha(raw)
            ):
                raise ValueError(f"row {row_id} target {slot_index} differs from ROM")
            if bundle_raw[packed_cursor:packed_end] != raw:
                raise ValueError(f"row {row_id} packed target differs from ROM")
            pointers.append(pointer)
            ranges.append((start, end))
            packed_cursor = packed_end
            target_payload_bytes += len(payload_bytes)
            newline_count += linefeeds
            newline_target_count += bool(linefeeds)
            target_id += 1

    if packed_cursor != len(bundle_raw):
        raise ValueError("packed target bundle has trailing or missing bytes")
    if pointers != sorted(pointers) or len(pointers) != len(set(pointers)):
        raise ValueError("target pointers are not unique and strictly ordered")
    ordered_ranges = sorted(ranges)
    overlaps = sum(
        start < previous_end
        for (_, previous_end), (start, _) in zip(
            ordered_ranges, ordered_ranges[1:]
        )
    )
    summary = {
        "table_row_count": len(rows),
        "table_byte_count": len(table_raw),
        "sentinel_count": sum(row["sentinel"] == 0 for row in rows),
        "direct_pointer_slot_count": len(pointers),
        "direct_target_count": len(ranges),
        "unique_target_count": len(set(pointers)),
        "duplicate_target_count": len(pointers) - len(set(pointers)),
        "overlapping_target_range_count": overlaps,
        "direct_target_bytes": len(bundle_raw),
        "target_payload_bytes": target_payload_bytes,
        "newline_target_count": newline_target_count,
        "newline_count": newline_count,
    }
    if summary != EXPECTED_SUMMARY or payload.get("summary") != summary:
        raise ValueError(f"dialogue denominator changed: {summary}")
    return summary


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    summary = {key: 0 for key in EXPECTED_SUMMARY}
    try:
        root = root.resolve(strict=True)
        artifact = artifact.resolve(strict=True)
        if not artifact.is_dir() or artifact.is_symlink():
            raise ValueError("artifact is not a safe directory")
        members = list(artifact.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact contains a symbolic link")
        actual_files = {
            member.relative_to(artifact).as_posix()
            for member in members
            if member.is_file()
        }
        if actual_files != EXPECTED_FILES:
            raise ValueError(f"artifact file set mismatch: {sorted(actual_files)}")

        rom = (root / ROM_PATH).read_bytes()
        if _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM SHA-256 changed")
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_raw)
        table_raw = (artifact / TABLE_NAME).read_bytes()
        bundle_raw = (artifact / BUNDLE_NAME).read_bytes()
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )

        if table_raw != rom[TABLE_START:TABLE_END] or _sha(table_raw) != TABLE_SHA256:
            raise ValueError("pointer table export differs from ROM")
        if _sha(bundle_raw) != BUNDLE_SHA256:
            raise ValueError("packed target bundle hash changed")
        _verify_payload_metadata(root, payload, payload_raw, table_raw, bundle_raw)
        _verify_consumer_contract(rom, payload.get("consumer_evidence"))
        summary = _verify_rows_against_rom(payload, rom, table_raw, bundle_raw)
        _verify_promotion_manifest(
            root, manifest, payload_raw, table_raw, bundle_raw
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        **summary,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
