#!/usr/bin/env python3
"""Export the fixed 46-slot character profile text inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import uuid


SCHEMA = "rom-profile-text-inventory-v1"
VERIFY_SCHEMA = "rom-profile-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

TABLE_RANGE = (0x5A143C, 0x5A14F4)
TABLE_ENTRY_COUNT = 46
TABLE_HASH = "e372c37fc5d41e2118ebee5feeb81967dd2f8413cc70d01ff7dc493197771410"
REGION_RANGE = (0x59F988, 0x5A143C)
REGION_HASH = "b3b663177a39e60f691fde0ff9272df69e875a116abc5a08647c4ec5d17c142d"

LIST_BUILDER_RANGE = (0x08A6AC, 0x08A6F8)
LIST_BUILDER_HASH = "b4f85b40bae2f9dd6d47f2f98d47a8955c27b97ecff8ff1c3aacb0a6c98f6f55"
TABLE_LITERAL_OFFSETS = (0x08A704, 0x08B214)
SELECTOR_RANGE = (0x08B19E, 0x08B1B6)
SELECTOR_HASH = "a85145a1f4f5342a07dda4175aa93de57ea55d5b1bb514c55ea65a1a47acf625"
PROFILE_WRAPPER_RANGE = (0x08D1A4, 0x08D230)
PROFILE_WRAPPER_HASH = "7646f12d2cdcbeb8b86bb39d491906bb112ac92afd0730ae5b56ac96a7f5c552"
PROFILE_WRAPPER_CALL = 0x08D214
RENDERER_BRIDGE_RANGE = (0x066758, 0x066790)
RENDERER_BRIDGE_HASH = "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
RENDERER_BRIDGE_CALL = 0x06678A
RENDERER_PARSER_RANGE = (0x06626C, 0x066736)
RENDERER_PARSER_HASH = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"

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


def _take(rom: bytes, start: int, size: int) -> bytes:
    if start < 0 or size <= 0 or start + size > len(rom):
        raise ValueError(f"invalid ROM range at {_addr(start)}")
    return rom[start : start + size]


def _u32(rom: bytes, offset: int) -> int:
    return struct.unpack("<I", _take(rom, offset, 4))[0]


def _thumb_bl_target(rom: bytes, offset: int) -> int:
    high = int.from_bytes(_take(rom, offset, 2), "little")
    low = int.from_bytes(_take(rom, offset + 2, 2), "little")
    if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
        raise ValueError(f"expected Thumb BL at {_addr(offset)}")
    delta = ((high & 0x07FF) << 12) | ((low & 0x07FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return offset + 4 + delta


def _halfword(rom: bytes, offset: int) -> int:
    return int.from_bytes(_take(rom, offset, 2), "little")


def _require_halfwords(
    rom: bytes, offset: int, expected: tuple[int, ...], label: str
) -> None:
    actual = tuple(_halfword(rom, offset + index * 2) for index in range(len(expected)))
    if actual != expected:
        raise ValueError(f"profile {label} instruction semantics changed")


def _thumb_literal_offset(offset: int, instruction: int, register: int) -> int:
    if instruction & 0xF800 != 0x4800 or (instruction >> 8) & 7 != register:
        raise ValueError("profile literal-load instruction semantics changed")
    return ((offset + 4) & ~3) + (instruction & 0xFF) * 4


def _decode_consumer_semantics(rom: bytes) -> dict[str, Any]:
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
    _require_halfwords(rom, 0x08B19E, selector, "selector")
    if (
        _thumb_literal_offset(0x08B19E, selector[0], 1) != 0x08B214
        or _u32(rom, 0x08B214) != ROM_BASE + TABLE_RANGE[0]
        or (selector[2] >> 6) & 0x1F != 2
        or selector[2] & 7 != 0
        or (selector[2] >> 3) & 7 != 0
        or _thumb_bl_target(rom, 0x08B1B2) != PROFILE_WRAPPER_RANGE[0]
    ):
        raise ValueError("profile selector decoded data flow changed")

    _require_halfwords(rom, 0x08A6C4, (0x042A,), "list index source")
    list_builder = (
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
    _require_halfwords(rom, 0x08A6D2, list_builder, "list builder")
    list_literal = _halfword(rom, 0x08A6BA)
    if (
        _thumb_literal_offset(0x08A6BA, list_literal, 7) != 0x08A704
        or _u32(rom, 0x08A704) != ROM_BASE + TABLE_RANGE[0]
        or (list_builder[1] >> 6) & 0x1F != 2
        or (list_builder[5] >> 6) & 0x1F != 14
    ):
        raise ValueError("profile list-builder decoded data flow changed")

    _require_halfwords(rom, 0x08D1C8, (0x3401,), "line advance")
    _require_halfwords(
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
    _require_halfwords(
        rom,
        0x08D1F6,
        (0x280A, 0xD001, 0x2800, 0xD1EB),
        "record-boundary grammar",
    )
    _require_halfwords(
        rom, 0x08D21C, (0x7820, 0x2800, 0xD1D2), "outer record loop"
    )
    if _thumb_bl_target(rom, PROFILE_WRAPPER_CALL) != RENDERER_BRIDGE_RANGE[0]:
        raise ValueError("profile wrapper decoded renderer call changed")

    _require_halfwords(rom, 0x066760, (0x4681,), "bridge source capture")
    _require_halfwords(rom, 0x066788, (0x4649,), "bridge source forwarding")
    if _thumb_bl_target(rom, RENDERER_BRIDGE_CALL) != RENDERER_PARSER_RANGE[0]:
        raise ValueError("profile bridge decoded parser call changed")

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
            "wrapper_call_offset": PROFILE_WRAPPER_CALL,
            "bridge_source_capture_offset": 0x066760,
            "bridge_source_forward_offset": 0x066788,
            "parser_call_offset": RENDERER_BRIDGE_CALL,
            "parser_call_target": _addr(RENDERER_PARSER_RANGE[0]),
        },
    }


def _slice(rom: bytes, bounds: tuple[int, int], expected: str, label: str) -> dict[str, Any]:
    start, end = bounds
    if _sha(_take(rom, start, end - start)) != expected:
        raise ValueError(f"{label} changed")
    return {
        "address": _addr(start),
        "range": [start, end],
        "gba_range": [_addr(start), _addr(end)],
        "sha256": expected,
    }


def _profile_text_end(rom: bytes, start: int, limit: int) -> tuple[int, int]:
    cursor = start
    line_break_count = 0
    while cursor < limit:
        value = rom[cursor]
        if value == 0:
            return cursor + 1, line_break_count
        if value == 0x0A:
            cursor += 1
            line_break_count += 1
        else:
            if cursor + 2 > limit:
                break
            cursor += 2
    raise ValueError(f"profile text at {_addr(start)} lacks a bounded terminator")


def _runtime_contract(root: Path, rom: bytes, pointers: list[int]) -> dict[str, Any]:
    path = _safe_file(root, RUNTIME_PATH)
    if _sha(path.read_bytes()) != RUNTIME_HASH:
        raise ValueError("profile runtime A/B evidence changed")
    evidence = json.loads(path.read_text(encoding="utf-8"))
    if (
        evidence.get("bank") != "data-table-a"
        or evidence.get("table") != _addr(TABLE_RANGE[0])
        or evidence.get("hook") != _addr(0x08B1A4)
        or evidence.get("route") != "title-menu character encyclopedia"
    ):
        raise ValueError("profile runtime A/B identity changed")
    control = evidence.get("control", {})
    variant = evidence.get("variant", {})
    patch = evidence.get("single_factor_patch", {})
    expected_control = _addr(pointers[0] - ROM_BASE)
    expected_variant = _addr(pointers[7] - ROM_BASE)
    if (
        control.get("magic") != "PTPR"
        or control.get("hit_count") != 1
        or control.get("character_id") != 0
        or control.get("table_entry") != _addr(TABLE_RANGE[0])
        or control.get("selected_pointer") != expected_control
        or variant.get("magic") != "PTPR"
        or variant.get("hit_count") != 1
        or variant.get("character_id") != 0
        or variant.get("table_entry") != _addr(TABLE_RANGE[0])
        or variant.get("selected_pointer") != expected_variant
        or patch != {"rom_offset": "0x5A143C", "size": 4, "source_entry": 7}
    ):
        raise ValueError("profile runtime A/B fields changed")
    for record in (control, variant):
        target = int(record["selected_pointer"], 16) - ROM_BASE
        if _take(rom, target, 16).hex() != record.get("target_first_16_hex"):
            raise ValueError("profile runtime A/B target bytes changed")
    return {"path": RUNTIME_PATH.as_posix(), "sha256": RUNTIME_HASH, **evidence}


def _consumer_evidence(root: Path, rom: bytes, pointers: list[int]) -> dict[str, Any]:
    bank_path = _safe_file(root, BANK_PATH)
    if _sha(bank_path.read_bytes()) != BANK_HASH:
        raise ValueError("data-table-a bank changed")
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    if (
        bank.get("table_offset") != TABLE_RANGE[0]
        or bank.get("entry_count") != TABLE_ENTRY_COUNT
        or bank.get("entry_size") != 4
        or bank.get("verification") != "runtime_verified"
        or [entry.get("text_ptr") for entry in bank.get("entries", [])] != pointers
    ):
        raise ValueError("data-table-a bank denominator changed")
    for literal in TABLE_LITERAL_OFFSETS:
        if _u32(rom, literal) != ROM_BASE + TABLE_RANGE[0]:
            raise ValueError("profile table base literal changed")
    list_builder = _slice(rom, LIST_BUILDER_RANGE, LIST_BUILDER_HASH, "profile list builder")
    selector = _slice(rom, SELECTOR_RANGE, SELECTOR_HASH, "profile pointer selector")
    wrapper = _slice(rom, PROFILE_WRAPPER_RANGE, PROFILE_WRAPPER_HASH, "profile line wrapper")
    if _thumb_bl_target(rom, PROFILE_WRAPPER_CALL) != RENDERER_BRIDGE_RANGE[0]:
        raise ValueError("profile line wrapper renderer call changed")
    wrapper["call_offset"] = PROFILE_WRAPPER_CALL
    wrapper["call_target"] = _addr(RENDERER_BRIDGE_RANGE[0])
    bridge = _slice(rom, RENDERER_BRIDGE_RANGE, RENDERER_BRIDGE_HASH, "renderer bridge")
    if _thumb_bl_target(rom, RENDERER_BRIDGE_CALL) != RENDERER_PARSER_RANGE[0]:
        raise ValueError("renderer bridge parser call changed")
    bridge["call_offset"] = RENDERER_BRIDGE_CALL
    bridge["call_target"] = _addr(RENDERER_PARSER_RANGE[0])
    return {
        "pointer_table_address": _addr(TABLE_RANGE[0]),
        "table_base_literals": [_addr(offset) for offset in TABLE_LITERAL_OFFSETS],
        "profile_list_builder": list_builder,
        "profile_pointer_selector": selector,
        "profile_line_wrapper": wrapper,
        "renderer_bridge": bridge,
        "renderer_parser": _slice(
            rom, RENDERER_PARSER_RANGE, RENDERER_PARSER_HASH, "renderer parser"
        ),
        "decoded_semantics": _decode_consumer_semantics(rom),
        "bank": {"path": BANK_PATH.as_posix(), "sha256": BANK_HASH},
        "runtime_ab": _runtime_contract(root, rom, pointers),
    }


def build_payload(root: Path, rom: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    table = _take(rom, TABLE_RANGE[0], TABLE_RANGE[1] - TABLE_RANGE[0])
    if _sha(table) != TABLE_HASH:
        raise ValueError("profile pointer table changed")
    pointers = list(struct.unpack(f"<{TABLE_ENTRY_COUNT}I", table))
    targets = [pointer - ROM_BASE for pointer in pointers]
    if (
        len(set(pointers)) != TABLE_ENTRY_COUNT
        or targets != sorted(targets)
        or targets[0] != REGION_RANGE[0]
        or any(not REGION_RANGE[0] <= target < REGION_RANGE[1] for target in targets)
    ):
        raise ValueError("profile pointer target denominator changed")

    records: list[dict[str, Any]] = []
    padding: list[dict[str, Any]] = []
    for index, (pointer, start) in enumerate(zip(pointers, targets)):
        limit = targets[index + 1] if index + 1 < len(targets) else REGION_RANGE[1]
        end, line_breaks = _profile_text_end(rom, start, limit)
        raw = _take(rom, start, end - start)
        records.append(
            {
                "record_id": f"profile-text-{index:03d}",
                "table_index": index,
                "pointer_slot_offset": TABLE_RANGE[0] + index * 4,
                "pointer_value": f"0x{pointer:08X}",
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
            gap = _take(rom, end, limit - end)
            if gap != bytes(len(gap)):
                raise ValueError(f"nonzero profile alignment gap after record {index}")
            padding.append(
                {
                    "padding_id": f"profile-alignment-{index:03d}",
                    "after_record_index": index,
                    "range": [end, limit],
                    "gba_range": [_addr(end), _addr(limit)],
                    "region_range": [end - REGION_RANGE[0], limit - REGION_RANGE[0]],
                    "size": len(gap),
                    "bytes_sha256": _sha(gap),
                    "all_zero": True,
                }
            )
    region = _take(rom, REGION_RANGE[0], REGION_RANGE[1] - REGION_RANGE[0])
    if _sha(region) != REGION_HASH:
        raise ValueError("profile text region changed")
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
        raise ValueError(f"profile text summary changed: {summary}")
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
            "entry_count": TABLE_ENTRY_COUNT,
            "entry_size": 4,
            "sha256": TABLE_HASH,
            "pointer_vector_sha256": _sha(table),
        },
        "consumer_evidence": _consumer_evidence(root, rom, pointers),
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


def _manifest(files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "files": {name: _sha(content) for name, content in sorted(files.items())},
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


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact output path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    requested = output.expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root:
        raise ValueError("artifact output must not be the repository root")
    if target in root.parents:
        raise ValueError("artifact output must not be an ancestor of the repository root")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("artifact output is not a directory")
    manifest_path = target / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("foreign artifact output directory")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("foreign artifact output directory") from error
    if manifest.get("artifact_schema") != SCHEMA:
        raise ValueError("foreign artifact output directory")
    members = [member for member in target.rglob("*") if member.is_file()]
    if any(member.is_symlink() for member in target.rglob("*")):
        raise ValueError("foreign artifact output directory")
    if {member.relative_to(target).as_posix() for member in members} != EXPECTED_FILES:
        raise ValueError("foreign artifact output directory")
    file_hashes = manifest.get("files")
    if not isinstance(file_hashes, dict):
        raise ValueError("foreign artifact output directory")
    for name, digest in file_hashes.items():
        path = target / name
        if not path.is_file() or _sha(path.read_bytes()) != digest:
            raise ValueError("foreign artifact output directory")
    try:
        from tools.verify_rom_profile_text_inventory import verify_artifact
    except ModuleNotFoundError:
        from verify_rom_profile_text_inventory import verify_artifact

    report = verify_artifact(root, target)
    if report.get("verified") is not True:
        raise ValueError(
            "existing artifact failed independent verification: "
            f"{report.get('errors', [])}"
        )
    return target


def _replace_output(target: Path, files: dict[str, bytes]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent)
    )
    backup: Path | None = None
    try:
        for name, content in files.items():
            (temporary / name).write_bytes(content)
        (temporary / "manifest.json").write_bytes(_canonical(_manifest(files)))
        if target.exists():
            backup = target.with_name(f".{target.name}.old-{uuid.uuid4().hex}")
            os.replace(target, backup)
        os.replace(temporary, target)
        if backup is not None:
            shutil.rmtree(backup)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    target = _validate_output(root, Path(output))
    payload, region = build_payload(root)
    files = {PAYLOAD_NAME: _canonical(payload), REGION_NAME: region}
    _replace_output(target, files)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output_dir)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
