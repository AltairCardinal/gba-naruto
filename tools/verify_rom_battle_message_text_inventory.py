#!/usr/bin/env python3
"""Independently verify the fixed battle-message text and padding inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "rom-battle-message-text-inventory-v1"
VERIFY_SCHEMA = "rom-battle-message-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

TABLE_START = 0x5A2034
TABLE_COUNT = 79
TABLE_END = TABLE_START + TABLE_COUNT * 4
TABLE_SHA256 = "c6dc43fda3044405fec144561fb76b3e684aa974a0c5633ec990ba5532b47ce3"
REGION_START = 0x5A1580
REGION_END = TABLE_START
REGION_SHA256 = "e0be9ff986140ae489c88769e483d98eab06febcf9f26ebf5fc6395fb428e0b9"
RECORD_RANGE_SHA256 = "d397dcf693ddcfedccaeb56efba1eeb2e646adfdfcea116254b41ad6898110cf"
RECORD_CONTENT_SHA256 = "24f1684e150bed11571cfa2f35fbb77d4e44c952d58fbcd5ec15d3e70f8eb8af"
PADDING_RANGE_SHA256 = "2170a4fffa02b01884c4633470fae48d24594e0083dfeebfb7b1dc52d41bd6e5"
PADDING_CONTENT_SHA256 = "738f09bb312878c2a990ac9af0ef31be3d3935a34233802f11b8bf10d1a47479"
CLASSIFIED_RANGE_SHA256 = "e175a9a9cd36fb1d8dba72a36318a27d2c40d0e622bbb498cb09917cf52f10bc"

SOURCE_BANK_PATH = Path("sequel/content/data-table-b/bank.json")
SOURCE_BANK_SHA256 = "5b8bf5e464c52dac97cd5522c079dea6e31527beb51ed4c0f8b07f934e2a7059"
RUNTIME_EVIDENCE_PATH = Path(
    "artifacts/data-table-b-message0-pointer-pixel-ab-v1/evidence.json"
)
RUNTIME_EVIDENCE_SHA256 = "b0d25756ca36b49a61ee5297aa0e238196ff6c9d49c610a29cd022e03c8594ff"

CONSUMERS = (
    {
        "range": (0x0985D8, 0x0985EA),
        "sha256": "50b0d700a1ec1776de8e5ef43d24a7eedee8948ed99019c92c1ac4e1c4b48411",
        "literal": 0x098624,
        "call": 0x0985E6,
    },
    {
        "range": (0x099D24, 0x099D38),
        "sha256": "2f996260fc7403bcc8a6558fc65ea0662cd3c29f263ba2d28488f43cab3baf48",
        "literal": 0x099D58,
        "call": 0x099D34,
    },
)
WRAPPER_RANGE = (0x098290, 0x098314)
WRAPPER_SHA256 = "fb8c3be986e3ac7e35cb11b2c7b4411d54e421a1427c03b6892b5f6f8ba86bf7"
WRAPPER_BRIDGE_CALL = 0x098310
BRIDGE_RANGE = (0x066758, 0x066790)
BRIDGE_SHA256 = "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
BRIDGE_PARSER_CALL = 0x06678A
PARSER_RANGE = (0x06626C, 0x066736)
PARSER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
SJIS_LOOKUP_RANGE = (0x065E80, 0x065EB6)
SJIS_LOOKUP_SHA256 = "242a528abb2866b87b760cabe7470db82a4f504cd697be6984333d026f2f2c8e"
SJIS_TABLE = 0x53D644
SJIS_RANGE_COUNT = 31
SJIS_ENTRY_SIZE = 8
SJIS_TABLE_END = SJIS_TABLE + SJIS_RANGE_COUNT * SJIS_ENTRY_SIZE
SJIS_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

PAYLOAD_NAME = "battle-message-text-inventory.json"
BUNDLE_NAME = "battle-message-text-bytes.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
EXPECTED_SUMMARY = {
    "pointer_table_count": 1,
    "pointer_slot_count": 79,
    "pointer_table_bytes": 316,
    "renderer_record_count": 79,
    "renderer_consumed_bytes": 1_411,
    "zero_padding_range_count": 79,
    "zero_padding_bytes": 1_329,
    "classified_range_count": 158,
    "classified_bytes": 2_740,
    "range_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_bytes": 2_740,
}
SCOPE = {
    "fixed_79_slot_denominator_complete": True,
    "all_pointer_slots_parser_bounded": True,
    "all_inter_record_bytes_accounted": True,
    "pointer_table_already_classified_by_bank": True,
    "runtime_index_bounds_proven": False,
    "natural_gameplay_all_ids_proven": False,
    "natural_gameplay_id_zero_proven": True,
    "unicode_decoding_complete": False,
    "editing_safety_proven": False,
    "zero_padding_safe_allocatable": False,
}
LIMITATIONS = [
    "The 316-byte pointer table is denominator evidence only because data-table-b already owns it as fixed_table.",
    "Natural action-7 evidence binds message ID 0 only; runtime bounds and natural execution of every ID remain unproven.",
    "The 1,329 zero bytes are structural inter-record padding, not text and not proven safe allocatable space.",
    "Unicode decoding, editing safety, physical-GBA behavior, and the preceding 0x5A14F4..0x5A1580 bytes remain unclaimed.",
]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _denominator_digest(ranges: list[list[int]]) -> str:
    return _digest(json.dumps(ranges, separators=(",", ":")).encode("ascii"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _bounded(data: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(data):
        raise ValueError("independent bounded slice escapes input")
    return data[start:end]


def _word16(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 2), "little")


def _word32(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 4), "little")


def _thumb_bl_target(data: bytes, offset: int) -> int:
    first = _word16(data, offset)
    second = _word16(data, offset + 2)
    if (first & 0xF800) != 0xF000 or (second & 0xF800) != 0xF800:
        raise ValueError("battle-message independent BL encoding changed")
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & 0x400000:
        delta -= 0x800000
    return offset + 4 + delta


def _root_file(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = candidate.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    return resolved


def _fixed_slice(
    rom: bytes, bounds: tuple[int, int], digest: str, label: str
) -> dict[str, Any]:
    start, end = bounds
    if _digest(_bounded(rom, start, end)) != digest:
        raise ValueError(f"battle-message independent {label} evidence changed")
    return {
        "range": [start, end],
        "gba_range": [_gba(start), _gba(end)],
        "sha256": digest,
    }


def _independent_consumer_contract(rom: bytes) -> dict[str, Any]:
    needle = (ROM_BASE + TABLE_START).to_bytes(4, "little")
    offsets = [
        offset
        for offset in range(0, len(rom) - 3)
        if _bounded(rom, offset, offset + 4) == needle
    ]
    if offsets != [item["literal"] for item in CONSUMERS]:
        raise ValueError("battle-message independent literal denominator changed")

    decoded_consumers = []
    for index, descriptor in enumerate(CONSUMERS):
        source = _fixed_slice(
            rom,
            descriptor["range"],
            descriptor["sha256"],
            f"consumer {index}",
        )
        if (
            _word32(rom, descriptor["literal"]) != ROM_BASE + TABLE_START
            or _thumb_bl_target(rom, descriptor["call"]) != WRAPPER_RANGE[0]
        ):
            raise ValueError("battle-message independent consumer data flow changed")
        decoded_consumers.append(
            {
                **source,
                "message_id_width": 1,
                "pointer_index_scale": 4,
                "pointer_table_literal": _gba(descriptor["literal"]),
                "pointer_table_address": _gba(TABLE_START),
                "wrapper_call_offset": _gba(descriptor["call"]),
                "wrapper_call_target": _gba(WRAPPER_RANGE[0]),
            }
        )

    wrapper = _fixed_slice(rom, WRAPPER_RANGE, WRAPPER_SHA256, "message wrapper")
    bridge = _fixed_slice(rom, BRIDGE_RANGE, BRIDGE_SHA256, "renderer bridge")
    parser = _fixed_slice(rom, PARSER_RANGE, PARSER_SHA256, "renderer parser")
    lookup = _fixed_slice(rom, SJIS_LOOKUP_RANGE, SJIS_LOOKUP_SHA256, "SJIS lookup")
    sjis_table = _fixed_slice(
        rom,
        (SJIS_TABLE, SJIS_TABLE_END),
        SJIS_TABLE_SHA256,
        "SJIS range table",
    )
    if (
        _thumb_bl_target(rom, WRAPPER_BRIDGE_CALL) != BRIDGE_RANGE[0]
        or _thumb_bl_target(rom, BRIDGE_PARSER_CALL) != PARSER_RANGE[0]
    ):
        raise ValueError("battle-message independent wrapper/parser chain changed")
    return {
        "table_consumers": decoded_consumers,
        "message_wrapper": {
            **wrapper,
            "text_pointer_capture_register": "r7",
            "bridge_argument_restore_offset": _gba(0x098308),
            "bridge_call_offset": _gba(WRAPPER_BRIDGE_CALL),
            "bridge_call_target": _gba(BRIDGE_RANGE[0]),
        },
        "renderer_bridge": {
            **bridge,
            "pointer_capture_offset": _gba(0x066760),
            "parser_argument_offset": _gba(0x066788),
            "parser_call_offset": _gba(BRIDGE_PARSER_CALL),
            "parser_call_target": _gba(PARSER_RANGE[0]),
        },
        "renderer_parser": parser,
        "sjis_lookup": lookup,
        "sjis_range_table": {
            **sjis_table,
            "entry_count": SJIS_RANGE_COUNT,
            "entry_size": SJIS_ENTRY_SIZE,
        },
        "renderer_grammar": {
            "terminator": 0,
            "control_01_width": 2,
            "control_02_width": 3,
            "high_80_9f_width": 2,
            "valid_sjis_pair_width": 2,
            "otherwise_width": 1,
            "sjis_range_count": SJIS_RANGE_COUNT,
            "sjis_entry_size": SJIS_ENTRY_SIZE,
        },
    }


def _independent_sjis_ranges(rom: bytes) -> tuple[tuple[int, int], ...]:
    result = []
    for index in range(SJIS_RANGE_COUNT):
        row = _bounded(
            rom,
            SJIS_TABLE + index * SJIS_ENTRY_SIZE,
            SJIS_TABLE + index * SJIS_ENTRY_SIZE + 3,
        )
        lower = int.from_bytes(row[:2], "little")
        result.append((lower, lower + row[2]))
    return tuple(result)


def _independent_renderer_end(
    data: bytes,
    start: int,
    limit: int,
    sjis_ranges: tuple[tuple[int, int], ...],
) -> int:
    if start < 0 or start >= limit or limit > len(data):
        raise ValueError("renderer text has an invalid independent bounded range")
    cursor = start
    while cursor < limit:
        first = data[cursor]
        if first == 0:
            return cursor + 1
        if first == 1:
            width = 2
        elif first == 2:
            width = 3
        elif 0x80 <= first <= 0x9F:
            width = 2
        elif first >= 0xA0:
            if cursor + 1 >= limit:
                raise ValueError("renderer text has a truncated high-byte pair")
            code = first << 8 | data[cursor + 1]
            width = 2 if any(lower <= code < upper for lower, upper in sjis_ranges) else 1
        else:
            width = 1
        if cursor + width > limit:
            raise ValueError("renderer text has a truncated control or pair")
        cursor += width
    raise ValueError("renderer text lacks a bounded terminator")


def _independent_verify_zero_padding(data: bytes, start: int, end: int) -> None:
    gap = _bounded(data, start, end)
    if not gap or gap != bytes(len(gap)):
        raise ValueError("battle-message independent zero padding changed")


def _independent_source_bank(
    root: Path, pointers: list[int]
) -> dict[str, Any]:
    bank_raw = _root_file(root, SOURCE_BANK_PATH).read_bytes()
    if _digest(bank_raw) != SOURCE_BANK_SHA256:
        raise ValueError("battle-message independent source bank changed")
    bank = json.loads(bank_raw)
    entries = bank.get("entries")
    expected_fields = (
        bank.get("table_offset") == TABLE_START,
        bank.get("entry_count") == TABLE_COUNT,
        bank.get("entry_size") == 4,
        bank.get("verification") == "runtime_verified",
        bank.get("runtime_evidence") == RUNTIME_EVIDENCE_PATH.as_posix(),
        isinstance(entries, list) and len(entries) == TABLE_COUNT,
    )
    if not all(expected_fields):
        raise ValueError("battle-message independent source bank denominator changed")
    assert isinstance(entries, list)
    for index in range(TABLE_COUNT):
        entry = entries[index]
        if (
            entry.get("_index") != index
            or entry.get("_raw_offset") != TABLE_START + index * 4
            or entry.get("text_ptr") != pointers[index]
        ):
            raise ValueError("battle-message independent source bank entry changed")
    runtime_raw = _root_file(root, RUNTIME_EVIDENCE_PATH).read_bytes()
    if _digest(runtime_raw) != RUNTIME_EVIDENCE_SHA256:
        raise ValueError("battle-message independent runtime evidence changed")
    return {
        "path": SOURCE_BANK_PATH.as_posix(),
        "sha256": SOURCE_BANK_SHA256,
        "table_offset": TABLE_START,
        "entry_count": TABLE_COUNT,
        "entry_size": 4,
        "verification": "runtime_verified",
        "runtime_evidence": {
            "path": RUNTIME_EVIDENCE_PATH.as_posix(),
            "sha256": RUNTIME_EVIDENCE_SHA256,
            "naturally_verified_message_ids": [0],
        },
    }


def _expected(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    semantics = _independent_consumer_contract(rom)
    table = _bounded(rom, TABLE_START, TABLE_END)
    if _digest(table) != TABLE_SHA256:
        raise ValueError("battle-message independent pointer table changed")
    pointers = [_word32(rom, TABLE_START + slot * 4) for slot in range(TABLE_COUNT)]
    targets = [pointer - ROM_BASE for pointer in pointers]
    if (
        targets != sorted(set(targets))
        or targets[0] != REGION_START
        or any(target < REGION_START or target >= REGION_END for target in targets)
    ):
        raise ValueError("battle-message independent target denominator changed")
    source_bank = _independent_source_bank(root, pointers)

    sjis = _independent_sjis_ranges(rom)
    records = []
    padding = []
    for slot, target in enumerate(targets):
        limit = targets[slot + 1] if slot + 1 < TABLE_COUNT else REGION_END
        end = _independent_renderer_end(rom, target, limit, sjis)
        _independent_verify_zero_padding(rom, end, limit)
        record_raw = _bounded(rom, target, end)
        padding_raw = _bounded(rom, end, limit)
        records.append(
            {
                "record_id": f"battle-message-text-{slot:02d}",
                "slot_index": slot,
                "range": [target, end],
                "gba_range": [_gba(target), _gba(end)],
                "size": len(record_raw),
                "sha256": _digest(record_raw),
            }
        )
        padding.append(
            {
                "padding_id": f"battle-message-padding-{slot:02d}",
                "after_slot_index": slot,
                "range": [end, limit],
                "gba_range": [_gba(end), _gba(limit)],
                "size": len(padding_raw),
                "sha256": _digest(padding_raw),
                "all_zero": True,
                "safe_allocatable_space_claimed": False,
            }
        )

    record_ranges = [record["range"] for record in records]
    padding_ranges = [gap["range"] for gap in padding]
    record_content = b"".join(_bounded(rom, start, end) for start, end in record_ranges)
    padding_content = b"".join(_bounded(rom, start, end) for start, end in padding_ranges)
    if (
        _denominator_digest(record_ranges) != RECORD_RANGE_SHA256
        or _digest(record_content) != RECORD_CONTENT_SHA256
        or _denominator_digest(padding_ranges) != PADDING_RANGE_SHA256
        or _digest(padding_content) != PADDING_CONTENT_SHA256
    ):
        raise ValueError("battle-message independent record or padding denominator changed")

    specs = []
    for record, gap in zip(records, padding):
        specs.extend(
            [
                (
                    record["record_id"],
                    "renderer_text_record",
                    record["slot_index"],
                    record["range"],
                ),
                (
                    gap["padding_id"],
                    "inter_record_zero_padding",
                    gap["after_slot_index"],
                    gap["range"],
                ),
            ]
        )
    classified = []
    packed = 0
    for range_id, kind, slot, bounds in specs:
        raw = _bounded(rom, bounds[0], bounds[1])
        classified.append(
            {
                "range_id": range_id,
                "kind": kind,
                "slot_index": slot,
                "range": bounds,
                "size": len(raw),
                "sha256": _digest(raw),
                "packed_range": [packed, packed + len(raw)],
            }
        )
        packed += len(raw)
    denominator = [item["range"] for item in classified]
    if (
        _denominator_digest(denominator) != CLASSIFIED_RANGE_SHA256
        or denominator[0][0] != REGION_START
        or denominator[-1][1] != REGION_END
        or any(left[1] != right[0] for left, right in zip(denominator, denominator[1:]))
    ):
        raise ValueError("battle-message independent classified denominator changed")
    bundle = b"".join(_bounded(rom, start, end) for start, end in denominator)
    if len(bundle) != 2_740 or _digest(bundle) != REGION_SHA256:
        raise ValueError("battle-message independent packed bytes changed")

    implementations = {
        label: {"path": path, "sha256": _digest(_root_file(root, path).read_bytes())}
        for label, path in {
            "exporter": "tools/export_rom_battle_message_text_inventory.py",
            "verifier": "tools/verify_rom_battle_message_text_inventory.py",
            "test": "tests/test_export_rom_battle_message_text_inventory.py",
        }.items()
    }
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "source_bank": source_bank,
        "pointer_table": {
            "semantic_type": "battle_message_renderer_text_pointer_table_79",
            "range": [TABLE_START, TABLE_END],
            "gba_range": [_gba(TABLE_START), _gba(TABLE_END)],
            "entry_count": TABLE_COUNT,
            "entry_size": 4,
            "sha256": TABLE_SHA256,
            "classified_here": False,
        },
        "records": records,
        "zero_padding": padding,
        "classified_ranges": classified,
        "record_range_denominator_sha256": RECORD_RANGE_SHA256,
        "record_content_sha256": RECORD_CONTENT_SHA256,
        "zero_padding_range_denominator_sha256": PADDING_RANGE_SHA256,
        "zero_padding_content_sha256": PADDING_CONTENT_SHA256,
        "classified_range_denominator_sha256": CLASSIFIED_RANGE_SHA256,
        "consumer_evidence": {"decoded_semantics": semantics},
        "summary": dict(EXPECTED_SUMMARY),
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": REGION_SHA256}},
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "implementation": implementations,
    }
    return payload, bundle


def _expected_manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "files": {name: _digest(content) for name, content in sorted(files.items())},
        "producer": payload["implementation"],
        "scope": SCOPE,
        "verification": {
            "schema": VERIFY_SCHEMA,
            "command": [
                "python3",
                "tools/verify_rom_battle_message_text_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
        },
    }


def _artifact_directory(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact path uses a symlink")
        if not cursor.exists():
            break
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("artifact path is not a directory")
    return resolved


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    report: dict[str, Any] = {"schema": VERIFY_SCHEMA, "verified": False, "errors": []}
    try:
        root = Path(root).resolve(strict=True)
        rom = _root_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256:
            raise ValueError("base ROM identity mismatch")
        artifact = _artifact_directory(Path(artifact_dir))
        members = list(artifact.rglob("*"))
        names = {
            member.relative_to(artifact).as_posix()
            for member in members
            if member.is_file()
        }
        if names != EXPECTED_FILES or any(member.is_symlink() for member in members):
            raise ValueError("artifact file set differs")
        manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_bytes)
        bundle = (artifact / BUNDLE_NAME).read_bytes()
        expected_payload, expected_bundle = _expected(root, rom)
        expected_files = {
            PAYLOAD_NAME: _canonical(expected_payload),
            BUNDLE_NAME: expected_bundle,
        }
        expected_manifest = _expected_manifest(expected_payload, expected_files)
        if payload != expected_payload:
            raise ValueError("artifact payload differs from independent reconstruction")
        if bundle != expected_bundle:
            raise ValueError("artifact bundle differs from independent reconstruction")
        if manifest != expected_manifest:
            raise ValueError("artifact manifest differs from independent reconstruction")
        if payload_bytes != expected_files[PAYLOAD_NAME]:
            raise ValueError("artifact payload is not canonical JSON")
        report.update(expected_payload["summary"])
        report["summary"] = expected_payload["summary"]
        report["artifact_schema"] = expected_payload["schema"]
        report["bundle_sha256"] = _digest(bundle)
        report["record_range_denominator_sha256"] = RECORD_RANGE_SHA256
        report["zero_padding_range_denominator_sha256"] = PADDING_RANGE_SHA256
        report["classified_range_denominator_sha256"] = CLASSIFIED_RANGE_SHA256
        report["verified"] = True
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        report["errors"].append(str(error))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    artifact = (
        args.artifact_dir
        if args.artifact_dir.is_absolute()
        else args.root / args.artifact_dir
    )
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
