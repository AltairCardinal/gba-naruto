#!/usr/bin/env python3
"""Independently verify the fixed 46-slot profile text inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


SCHEMA = "rom-profile-text-inventory-v1"
VERIFY_SCHEMA = "rom-profile-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

TABLE_RANGE = (0x5A143C, 0x5A14F4)
TABLE_COUNT = 46
TABLE_HASH = "e372c37fc5d41e2118ebee5feeb81967dd2f8413cc70d01ff7dc493197771410"
REGION_RANGE = (0x59F988, 0x5A143C)
REGION_HASH = "b3b663177a39e60f691fde0ff9272df69e875a116abc5a08647c4ec5d17c142d"

LIST_BUILDER_RANGE = (0x08A6AC, 0x08A6F8)
LIST_BUILDER_HASH = "b4f85b40bae2f9dd6d47f2f98d47a8955c27b97ecff8ff1c3aacb0a6c98f6f55"
LITERAL_OFFSETS = (0x08A704, 0x08B214)
SELECTOR_RANGE = (0x08B19E, 0x08B1B6)
SELECTOR_HASH = "a85145a1f4f5342a07dda4175aa93de57ea55d5b1bb514c55ea65a1a47acf625"
PROFILE_WRAPPER_RANGE = (0x08D1A4, 0x08D230)
PROFILE_WRAPPER_HASH = "7646f12d2cdcbeb8b86bb39d491906bb112ac92afd0730ae5b56ac96a7f5c552"
PROFILE_CALL = 0x08D214
BRIDGE_RANGE = (0x066758, 0x066790)
BRIDGE_HASH = "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
BRIDGE_CALL = 0x06678A
PARSER_RANGE = (0x06626C, 0x066736)
PARSER_HASH = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"

BANK_PATH = Path("sequel/content/data-table-a/bank.json")
BANK_HASH = "319cfe202e5e630ec69fb2ec0f207a1cd80076efb8ad1a813a20ef0a90e6537d"
RUNTIME_PATH = Path("artifacts/runtime-checkpoints/profile-text-runtime-evidence.json")
RUNTIME_HASH = "552b94be0613af35642524136f631b211c47d71e113c575111154ee2a529b363"

PAYLOAD_NAME = "profile-text-inventory.json"
REGION_NAME = "profile-text-region.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, REGION_NAME}
EXPECTED_SUMMARY = {
    "pointer_table_count": 1,
    "pointer_slot_count": 46,
    "unique_target_count": 46,
    "profile_text_record_count": 46,
    "profile_text_bytes": 6_798,
    "alignment_padding_range_count": 19,
    "alignment_padding_bytes": 38,
    "claimed_region_bytes": 6_836,
    "parse_failure_count": 0,
}
SCOPE = {
    "fixed_pointer_table_denominator_complete": True,
    "profile_reader_consumer_bound": True,
    "profile_text_record_partition_complete": True,
    "alignment_padding_partition_complete": True,
    "natural_gameplay_all_ids_complete": False,
    "unicode_decoding_complete": False,
}
LIMITATIONS = [
    "Only the 46 targets selected by the fixed profile table and the exact zero alignment gaps between them are classified.",
    "The preceding unreferenced bytes before the first target at 0x0059F988 remain outside this denominator.",
    "The natural runtime A/B proves entry 0 selection and same-table replacement causality, not natural execution of all 46 IDs.",
    "Game-encoded profile bytes are not asserted to be Unicode-decoded natural-language text.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _safe_file(root: Path, relative: Path | str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = path.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _artifact_file(artifact: Path, name: str) -> Path:
    path = artifact / name
    if path.is_symlink():
        raise ValueError(f"artifact member must not be a symlink: {name}")
    resolved = path.resolve(strict=True)
    if artifact != resolved and artifact not in resolved.parents:
        raise ValueError(f"artifact member escapes directory: {name}")
    if not resolved.is_file():
        raise ValueError(f"artifact member is not a file: {name}")
    return resolved


def _take(rom: bytes, start: int, size: int) -> bytes:
    if start < 0 or size <= 0 or start + size > len(rom):
        raise ValueError(f"invalid ROM range at {_addr(start)}")
    return rom[start : start + size]


def _word(rom: bytes, offset: int) -> int:
    return struct.unpack("<I", _take(rom, offset, 4))[0]


def _thumb_bl_target(rom: bytes, offset: int) -> int:
    first = int.from_bytes(_take(rom, offset, 2), "little")
    second = int.from_bytes(_take(rom, offset + 2, 2), "little")
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"expected Thumb BL at {_addr(offset)}")
    delta = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return offset + 4 + delta


def _half(rom: bytes, offset: int) -> int:
    return int.from_bytes(_take(rom, offset, 2), "little")


def _assert_instruction_vector(
    rom: bytes, start: int, vector: tuple[int, ...], label: str
) -> None:
    decoded = tuple(_half(rom, start + index * 2) for index in range(len(vector)))
    if decoded != vector:
        raise ValueError(f"profile {label} decoded instruction vector differs")


def _literal_target(offset: int, instruction: int, destination: int) -> int:
    opcode = instruction & 0xF800
    register = (instruction >> 8) & 7
    if opcode != 0x4800 or register != destination:
        raise ValueError("profile literal instruction contract differs")
    return ((offset + 4) & ~3) + (instruction & 0xFF) * 4


def _decode_consumer_contract(rom: bytes) -> dict[str, Any]:
    selector = (
        0x491D,
        0x7830,
        0x0080,
        0x1840,
        0x6800,
        0x2106,
        0x9100,
        0x2100,
        0x1C2A,
        0x230C,
    )
    _assert_instruction_vector(rom, 0x08B19E, selector, "selector")
    shift = selector[2]
    if (
        _literal_target(0x08B19E, selector[0], 1) != 0x08B214
        or _word(rom, 0x08B214) != ROM_BASE + TABLE_RANGE[0]
        or ((shift >> 6) & 0x1F, (shift >> 3) & 7, shift & 7) != (2, 0, 0)
        or _thumb_bl_target(rom, 0x08B1B2) != PROFILE_WRAPPER_RANGE[0]
    ):
        raise ValueError("profile selector decoded data flow differs")

    _assert_instruction_vector(rom, 0x08A6C4, (0x042A,), "list index source")
    builder = (
        0x7820,
        0x0080,
        0x1C21,
        0x3134,
        0x1809,
        0x1390,
        0x19C0,
        0x6800,
        0x6008,
    )
    _assert_instruction_vector(rom, 0x08A6D2, builder, "list builder")
    if (
        _literal_target(0x08A6BA, _half(rom, 0x08A6BA), 7) != 0x08A704
        or _word(rom, 0x08A704) != ROM_BASE + TABLE_RANGE[0]
        or (builder[1] >> 6) & 0x1F != 2
        or (builder[5] >> 6) & 0x1F != 14
    ):
        raise ValueError("profile list-builder decoded data flow differs")

    _assert_instruction_vector(rom, 0x08D1C8, (0x3401,), "line advance")
    _assert_instruction_vector(
        rom,
        0x08D1DC,
        (
            0x7820,
            0x7008,
            0x1C50,
            0x4669,
            0x1809,
            0x3104,
            0x7860,
            0x7008,
            0x1C90,
            0x0400,
            0x0C02,
            0x3402,
            0x7820,
        ),
        "pair-copy grammar",
    )
    _assert_instruction_vector(
        rom,
        0x08D1F6,
        (0x280A, 0xD001, 0x2800, 0xD1EB),
        "record-boundary grammar",
    )
    _assert_instruction_vector(
        rom, 0x08D21C, (0x7820, 0x2800, 0xD1D2), "outer record loop"
    )
    if _thumb_bl_target(rom, PROFILE_CALL) != BRIDGE_RANGE[0]:
        raise ValueError("profile wrapper decoded call differs")

    _assert_instruction_vector(rom, 0x066760, (0x4681,), "bridge source capture")
    _assert_instruction_vector(rom, 0x066788, (0x4649,), "bridge source forwarding")
    if _thumb_bl_target(rom, BRIDGE_CALL) != PARSER_RANGE[0]:
        raise ValueError("profile bridge decoded call differs")

    return {
        "profile_list_builder": {
            "index_load_offset": 0x08A6D2,
            "index_scale": 4,
            "pointer_load_offset": 0x08A6E0,
            "table_literal_offset": 0x08A704,
        },
        "profile_pointer_selector": {
            "id_load_offset": 0x08B1A0,
            "index_scale": 4,
            "pointer_load_offset": 0x08B1A6,
            "table_literal_offset": 0x08B214,
            "wrapper_call_offset": 0x08B1B2,
            "wrapper_call_target": _addr(PROFILE_WRAPPER_RANGE[0]),
        },
        "profile_record_grammar": {
            "pair_width": 2,
            "pair_copy_range": [0x08D1DC, 0x08D1F4],
            "line_break_value": 0x0A,
            "line_break_compare_offset": 0x08D1F6,
            "terminator_value": 0,
            "terminator_compare_offset": 0x08D1FA,
            "line_advance_offset": 0x08D1C8,
        },
        "renderer_path": {
            "wrapper_call_offset": PROFILE_CALL,
            "bridge_source_capture_offset": 0x066760,
            "bridge_source_forward_offset": 0x066788,
            "parser_call_offset": BRIDGE_CALL,
            "parser_call_target": _addr(PARSER_RANGE[0]),
        },
    }


def _bounded_profile_end(rom: bytes, start: int, limit: int) -> tuple[int, int]:
    cursor = start
    line_breaks = 0
    while cursor < limit:
        first = rom[cursor]
        if first == 0:
            return cursor + 1, line_breaks
        if first == 0x0A:
            cursor += 1
            line_breaks += 1
        else:
            if cursor + 2 > limit:
                break
            cursor += 2
    raise ValueError(f"profile record at {_addr(start)} lacks a bounded terminator")


def _slice(rom: bytes, bounds: tuple[int, int], digest: str, label: str) -> dict[str, Any]:
    start, end = bounds
    if _sha(_take(rom, start, end - start)) != digest:
        raise ValueError(f"{label} hash differs")
    return {
        "address": _addr(start),
        "range": [start, end],
        "gba_range": [_addr(start), _addr(end)],
        "sha256": digest,
    }


def _runtime_evidence(root: Path, rom: bytes, pointers: list[int]) -> dict[str, Any]:
    path = _safe_file(root, RUNTIME_PATH)
    if _sha(path.read_bytes()) != RUNTIME_HASH:
        raise ValueError("runtime evidence hash differs")
    evidence = json.loads(path.read_text(encoding="utf-8"))
    control = evidence.get("control", {})
    variant = evidence.get("variant", {})
    if (
        evidence.get("bank") != "data-table-a"
        or evidence.get("table") != _addr(TABLE_RANGE[0])
        or evidence.get("hook") != _addr(0x08B1A4)
        or evidence.get("route") != "title-menu character encyclopedia"
        or control.get("magic") != "PTPR"
        or control.get("hit_count") != 1
        or control.get("character_id") != 0
        or control.get("table_entry") != _addr(TABLE_RANGE[0])
        or control.get("selected_pointer") != f"0x{pointers[0]:08X}"
        or variant.get("magic") != "PTPR"
        or variant.get("hit_count") != 1
        or variant.get("character_id") != 0
        or variant.get("table_entry") != _addr(TABLE_RANGE[0])
        or variant.get("selected_pointer") != f"0x{pointers[7]:08X}"
        or evidence.get("single_factor_patch")
        != {"rom_offset": "0x5A143C", "size": 4, "source_entry": 7}
    ):
        raise ValueError("runtime evidence contract differs")
    for item in (control, variant):
        target = int(item["selected_pointer"], 16) - ROM_BASE
        if _take(rom, target, 16).hex() != item.get("target_first_16_hex"):
            raise ValueError("runtime evidence target sample differs")
    return {"path": RUNTIME_PATH.as_posix(), "sha256": RUNTIME_HASH, **evidence}


def _consumer_contract(root: Path, rom: bytes, pointers: list[int]) -> dict[str, Any]:
    bank_path = _safe_file(root, BANK_PATH)
    if _sha(bank_path.read_bytes()) != BANK_HASH:
        raise ValueError("bank hash differs")
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    if (
        bank.get("table_offset") != TABLE_RANGE[0]
        or bank.get("entry_count") != TABLE_COUNT
        or bank.get("entry_size") != 4
        or bank.get("verification") != "runtime_verified"
        or [entry.get("text_ptr") for entry in bank.get("entries", [])] != pointers
    ):
        raise ValueError("bank denominator differs")
    if any(_word(rom, offset) != ROM_BASE + TABLE_RANGE[0] for offset in LITERAL_OFFSETS):
        raise ValueError("table literal differs")
    list_builder = _slice(rom, LIST_BUILDER_RANGE, LIST_BUILDER_HASH, "list builder")
    selector = _slice(rom, SELECTOR_RANGE, SELECTOR_HASH, "selector")
    wrapper = _slice(rom, PROFILE_WRAPPER_RANGE, PROFILE_WRAPPER_HASH, "profile wrapper")
    if _thumb_bl_target(rom, PROFILE_CALL) != BRIDGE_RANGE[0]:
        raise ValueError("profile wrapper call differs")
    wrapper["call_offset"] = PROFILE_CALL
    wrapper["call_target"] = _addr(BRIDGE_RANGE[0])
    bridge = _slice(rom, BRIDGE_RANGE, BRIDGE_HASH, "renderer bridge")
    if _thumb_bl_target(rom, BRIDGE_CALL) != PARSER_RANGE[0]:
        raise ValueError("renderer bridge call differs")
    bridge["call_offset"] = BRIDGE_CALL
    bridge["call_target"] = _addr(PARSER_RANGE[0])
    return {
        "pointer_table_address": _addr(TABLE_RANGE[0]),
        "table_base_literals": [_addr(offset) for offset in LITERAL_OFFSETS],
        "profile_list_builder": list_builder,
        "profile_pointer_selector": selector,
        "profile_line_wrapper": wrapper,
        "renderer_bridge": bridge,
        "renderer_parser": _slice(rom, PARSER_RANGE, PARSER_HASH, "renderer parser"),
        "decoded_semantics": _decode_consumer_contract(rom),
        "bank": {"path": BANK_PATH.as_posix(), "sha256": BANK_HASH},
        "runtime_ab": _runtime_evidence(root, rom, pointers),
    }


def _expected_payload(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    table = _take(rom, TABLE_RANGE[0], TABLE_RANGE[1] - TABLE_RANGE[0])
    if _sha(table) != TABLE_HASH:
        raise ValueError("pointer table hash differs")
    pointers = list(struct.unpack(f"<{TABLE_COUNT}I", table))
    targets = [pointer - ROM_BASE for pointer in pointers]
    if (
        len(set(targets)) != TABLE_COUNT
        or targets != sorted(targets)
        or targets[0] != REGION_RANGE[0]
        or any(target < REGION_RANGE[0] or target >= REGION_RANGE[1] for target in targets)
    ):
        raise ValueError("pointer target denominator differs")
    records: list[dict[str, Any]] = []
    padding: list[dict[str, Any]] = []
    for index, start in enumerate(targets):
        limit = targets[index + 1] if index + 1 < TABLE_COUNT else REGION_RANGE[1]
        end, line_breaks = _bounded_profile_end(rom, start, limit)
        raw = _take(rom, start, end - start)
        records.append(
            {
                "record_id": f"profile-text-{index:03d}",
                "table_index": index,
                "pointer_slot_offset": TABLE_RANGE[0] + index * 4,
                "pointer_value": f"0x{pointers[index]:08X}",
                "range": [start, end],
                "gba_range": [_addr(start), _addr(end)],
                "region_range": [start - REGION_RANGE[0], end - REGION_RANGE[0]],
                "size": len(raw),
                "bytes_sha256": _sha(raw),
                "line_break_count": line_breaks,
                "terminator": 0,
            }
        )
        if end < limit:
            raw_gap = _take(rom, end, limit - end)
            if any(raw_gap):
                raise ValueError("profile alignment gap is not all zero")
            padding.append(
                {
                    "padding_id": f"profile-alignment-{index:03d}",
                    "after_record_index": index,
                    "range": [end, limit],
                    "gba_range": [_addr(end), _addr(limit)],
                    "region_range": [end - REGION_RANGE[0], limit - REGION_RANGE[0]],
                    "size": len(raw_gap),
                    "bytes_sha256": _sha(raw_gap),
                    "all_zero": True,
                }
            )
    region = _take(rom, REGION_RANGE[0], REGION_RANGE[1] - REGION_RANGE[0])
    if _sha(region) != REGION_HASH:
        raise ValueError("profile region hash differs")
    summary = {
        "pointer_table_count": 1,
        "pointer_slot_count": len(pointers),
        "unique_target_count": len(set(pointers)),
        "profile_text_record_count": len(records),
        "profile_text_bytes": sum(record["size"] for record in records),
        "alignment_padding_range_count": len(padding),
        "alignment_padding_bytes": sum(item["size"] for item in padding),
        "claimed_region_bytes": len(region),
        "parse_failure_count": 0,
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError(f"profile summary differs: {summary}")
    denominator = [
        {"table_index": record["table_index"], "range": record["range"]}
        for record in records
    ] + [
        {"after_record_index": item["after_record_index"], "range": item["range"]}
        for item in padding
    ]
    implementation = {
        "exporter": {
            "path": "tools/export_rom_profile_text_inventory.py",
            "sha256": _sha(
                _safe_file(root, "tools/export_rom_profile_text_inventory.py").read_bytes()
            ),
        },
        "verifier": {
            "path": "tools/verify_rom_profile_text_inventory.py",
            "sha256": _sha(
                _safe_file(root, "tools/verify_rom_profile_text_inventory.py").read_bytes()
            ),
        },
        "test": {
            "path": "tests/test_export_rom_profile_text_inventory.py",
            "sha256": _sha(
                _safe_file(root, "tests/test_export_rom_profile_text_inventory.py").read_bytes()
            ),
        },
    }
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "pointer_table": {
            "range": list(TABLE_RANGE),
            "gba_range": [_addr(TABLE_RANGE[0]), _addr(TABLE_RANGE[1])],
            "entry_count": TABLE_COUNT,
            "entry_size": 4,
            "sha256": TABLE_HASH,
            "pointer_vector_sha256": _sha(table),
        },
        "consumer_evidence": _consumer_contract(root, rom, pointers),
        "profile_region": {
            "range": list(REGION_RANGE),
            "gba_range": [_addr(REGION_RANGE[0]), _addr(REGION_RANGE[1])],
            "size": len(region),
            "sha256": REGION_HASH,
            "file": REGION_NAME,
        },
        "records": records,
        "alignment_padding": padding,
        "range_denominator_sha256": _sha(_canonical(denominator)),
        "summary": summary,
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": implementation,
    }
    return payload, region


def _expected_manifest(payload_bytes: bytes, region: bytes) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "files": {
            PAYLOAD_NAME: _sha(payload_bytes),
            REGION_NAME: _sha(region),
        },
        "verification": {
            "schema": VERIFY_SCHEMA,
            "command": [
                "python3",
                "tools/verify_rom_profile_text_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
        },
    }


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = Path(root).resolve(strict=True)
        artifact_path = Path(artifact_dir)
        if artifact_path.is_symlink():
            raise ValueError("artifact directory must not be a symlink")
        artifact = artifact_path.resolve(strict=True)
        if not artifact.is_dir():
            raise ValueError("artifact path is not a directory")
        actual_members = {
            member.relative_to(artifact).as_posix()
            for member in artifact.rglob("*")
            if member.is_file()
        }
        if actual_members != EXPECTED_FILES:
            raise ValueError("artifact file denominator differs")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity differs")
        expected_payload, expected_region = _expected_payload(root, rom)
        expected_payload_bytes = _canonical(expected_payload)
        manifest = json.loads(
            _artifact_file(artifact, "manifest.json").read_text(encoding="utf-8")
        )
        expected_manifest = _expected_manifest(expected_payload_bytes, expected_region)
        if manifest != expected_manifest:
            raise ValueError("artifact manifest differs from independent reconstruction")
        for name, digest in manifest["files"].items():
            if _sha(_artifact_file(artifact, name).read_bytes()) != digest:
                raise ValueError(f"artifact file hash differs: {name}")
        payload = json.loads(
            _artifact_file(artifact, PAYLOAD_NAME).read_text(encoding="utf-8")
        )
        if payload != expected_payload:
            raise ValueError("artifact payload differs from independent reconstruction")
        if _artifact_file(artifact, REGION_NAME).read_bytes() != expected_region:
            raise ValueError("profile region bundle differs from ROM")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
    }
    if not errors:
        report.update(EXPECTED_SUMMARY)
        report["rom_sha256"] = ROM_SHA256
        report["table_sha256"] = TABLE_HASH
        report["region_sha256"] = REGION_HASH
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
