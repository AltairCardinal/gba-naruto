#!/usr/bin/env python3
"""Export the fixed 79-slot battle-message text and zero-padding inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
import uuid


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


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _range_hash(ranges: list[list[int]]) -> str:
    return _sha(json.dumps(ranges, separators=(",", ":")).encode("ascii"))


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _take(data: bytes, start: int, size: int) -> bytes:
    end = start + size
    if start < 0 or end < start or end > len(data):
        raise ValueError("bounded exporter slice escapes input")
    return data[start:end]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_take(data, offset, 2), "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_take(data, offset, 4), "little")


def _decode_bl(data: bytes, offset: int) -> int:
    high = _u16(data, offset)
    low = _u16(data, offset + 2)
    if high >> 11 != 0x1E or low >> 11 != 0x1F:
        raise ValueError("battle-message BL encoding changed")
    displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if displacement >= 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def _safe_file(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = candidate.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    return resolved


def _evidence(
    rom: bytes, start: int, end: int, digest: str, label: str
) -> dict[str, Any]:
    if _sha(_take(rom, start, end - start)) != digest:
        raise ValueError(f"battle-message {label} evidence changed")
    return {
        "range": [start, end],
        "gba_range": [_addr(start), _addr(end)],
        "sha256": digest,
    }


def _decode_consumer_contract(rom: bytes) -> dict[str, Any]:
    table_word = (ROM_BASE + TABLE_START).to_bytes(4, "little")
    literal_offsets = [
        offset
        for offset in range(0, len(rom) - 3)
        if rom[offset : offset + 4] == table_word
    ]
    expected_literals = [item["literal"] for item in CONSUMERS]
    if literal_offsets != expected_literals:
        raise ValueError("battle-message pointer-table literal denominator changed")

    consumers = []
    for index, item in enumerate(CONSUMERS):
        evidence = _evidence(
            rom, *item["range"], item["sha256"], f"consumer {index}"
        )
        if (
            _u32(rom, item["literal"]) != ROM_BASE + TABLE_START
            or _decode_bl(rom, item["call"]) != WRAPPER_RANGE[0]
        ):
            raise ValueError("battle-message consumer data flow changed")
        consumers.append(
            {
                **evidence,
                "message_id_width": 1,
                "pointer_index_scale": 4,
                "pointer_table_literal": _addr(item["literal"]),
                "pointer_table_address": _addr(TABLE_START),
                "wrapper_call_offset": _addr(item["call"]),
                "wrapper_call_target": _addr(WRAPPER_RANGE[0]),
            }
        )

    wrapper = _evidence(rom, *WRAPPER_RANGE, WRAPPER_SHA256, "message wrapper")
    bridge = _evidence(rom, *BRIDGE_RANGE, BRIDGE_SHA256, "renderer bridge")
    parser = _evidence(rom, *PARSER_RANGE, PARSER_SHA256, "renderer parser")
    lookup = _evidence(rom, *SJIS_LOOKUP_RANGE, SJIS_LOOKUP_SHA256, "SJIS lookup")
    sjis_table = _evidence(
        rom, SJIS_TABLE, SJIS_TABLE_END, SJIS_TABLE_SHA256, "SJIS range table"
    )
    if (
        _decode_bl(rom, WRAPPER_BRIDGE_CALL) != BRIDGE_RANGE[0]
        or _decode_bl(rom, BRIDGE_PARSER_CALL) != PARSER_RANGE[0]
    ):
        raise ValueError("battle-message wrapper/parser chain changed")
    return {
        "table_consumers": consumers,
        "message_wrapper": {
            **wrapper,
            "text_pointer_capture_register": "r7",
            "bridge_argument_restore_offset": _addr(0x098308),
            "bridge_call_offset": _addr(WRAPPER_BRIDGE_CALL),
            "bridge_call_target": _addr(BRIDGE_RANGE[0]),
        },
        "renderer_bridge": {
            **bridge,
            "pointer_capture_offset": _addr(0x066760),
            "parser_argument_offset": _addr(0x066788),
            "parser_call_offset": _addr(BRIDGE_PARSER_CALL),
            "parser_call_target": _addr(PARSER_RANGE[0]),
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


def _sjis_ranges(rom: bytes) -> tuple[tuple[int, int], ...]:
    result = []
    for index in range(SJIS_RANGE_COUNT):
        row = _take(rom, SJIS_TABLE + index * SJIS_ENTRY_SIZE, 3)
        lower = int.from_bytes(row[:2], "little")
        result.append((lower, lower + row[2]))
    return tuple(result)


def _renderer_end(
    data: bytes,
    start: int,
    limit: int,
    sjis_ranges: tuple[tuple[int, int], ...],
) -> int:
    if start < 0 or start >= limit or limit > len(data):
        raise ValueError("renderer text has an invalid bounded range")
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


def _verify_zero_padding(data: bytes, start: int, end: int) -> None:
    raw = _take(data, start, end - start)
    if not raw or any(raw):
        raise ValueError("battle-message inter-record zero padding changed")


def _source_bank(root: Path, rom: bytes, pointers: list[int]) -> dict[str, Any]:
    bank_path = _safe_file(root, SOURCE_BANK_PATH)
    raw = bank_path.read_bytes()
    if _sha(raw) != SOURCE_BANK_SHA256:
        raise ValueError("battle-message source bank changed")
    bank = json.loads(raw)
    entries = bank.get("entries")
    if (
        bank.get("table_offset") != TABLE_START
        or bank.get("entry_count") != TABLE_COUNT
        or bank.get("entry_size") != 4
        or bank.get("verification") != "runtime_verified"
        or bank.get("runtime_evidence") != RUNTIME_EVIDENCE_PATH.as_posix()
        or not isinstance(entries, list)
        or len(entries) != TABLE_COUNT
    ):
        raise ValueError("battle-message source bank denominator changed")
    for index, (entry, pointer) in enumerate(zip(entries, pointers)):
        if (
            entry.get("_index") != index
            or entry.get("_raw_offset") != TABLE_START + index * 4
            or entry.get("text_ptr") != pointer
        ):
            raise ValueError("battle-message source bank entries changed")
    evidence = _safe_file(root, RUNTIME_EVIDENCE_PATH).read_bytes()
    if _sha(evidence) != RUNTIME_EVIDENCE_SHA256:
        raise ValueError("battle-message runtime evidence changed")
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


def _derive(root: Path) -> tuple[dict[str, Any], bytes]:
    rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    semantics = _decode_consumer_contract(rom)
    table_raw = _take(rom, TABLE_START, TABLE_END - TABLE_START)
    if _sha(table_raw) != TABLE_SHA256:
        raise ValueError("battle-message pointer table changed")
    pointers = [_u32(rom, TABLE_START + slot * 4) for slot in range(TABLE_COUNT)]
    targets = [pointer - ROM_BASE for pointer in pointers]
    if (
        targets != sorted(set(targets))
        or targets[0] != REGION_START
        or any(not REGION_START <= target < REGION_END for target in targets)
    ):
        raise ValueError("battle-message text target denominator changed")
    bank = _source_bank(root, rom, pointers)

    sjis = _sjis_ranges(rom)
    records = []
    padding = []
    for slot, target in enumerate(targets):
        limit = targets[slot + 1] if slot + 1 < len(targets) else REGION_END
        end = _renderer_end(rom, target, limit, sjis)
        _verify_zero_padding(rom, end, limit)
        record_raw = _take(rom, target, end - target)
        padding_raw = _take(rom, end, limit - end)
        records.append(
            {
                "record_id": f"battle-message-text-{slot:02d}",
                "slot_index": slot,
                "range": [target, end],
                "gba_range": [_addr(target), _addr(end)],
                "size": len(record_raw),
                "sha256": _sha(record_raw),
            }
        )
        padding.append(
            {
                "padding_id": f"battle-message-padding-{slot:02d}",
                "after_slot_index": slot,
                "range": [end, limit],
                "gba_range": [_addr(end), _addr(limit)],
                "size": len(padding_raw),
                "sha256": _sha(padding_raw),
                "all_zero": True,
                "safe_allocatable_space_claimed": False,
            }
        )

    record_ranges = [record["range"] for record in records]
    padding_ranges = [item["range"] for item in padding]
    record_bytes = b"".join(_take(rom, start, end - start) for start, end in record_ranges)
    padding_bytes = b"".join(_take(rom, start, end - start) for start, end in padding_ranges)
    if (
        _range_hash(record_ranges) != RECORD_RANGE_SHA256
        or _sha(record_bytes) != RECORD_CONTENT_SHA256
        or _range_hash(padding_ranges) != PADDING_RANGE_SHA256
        or _sha(padding_bytes) != PADDING_CONTENT_SHA256
    ):
        raise ValueError("battle-message record or padding denominator changed")

    classified_specs = []
    for record, gap in zip(records, padding):
        classified_specs.extend(
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
    classified_ranges = []
    packed_cursor = 0
    for range_id, kind, slot, bounds in classified_specs:
        start, end = bounds
        raw = _take(rom, start, end - start)
        item = {
            "range_id": range_id,
            "kind": kind,
            "slot_index": slot,
            "range": bounds,
            "size": len(raw),
            "sha256": _sha(raw),
            "packed_range": [packed_cursor, packed_cursor + len(raw)],
        }
        classified_ranges.append(item)
        packed_cursor += len(raw)
    denominator = [item["range"] for item in classified_ranges]
    if (
        _range_hash(denominator) != CLASSIFIED_RANGE_SHA256
        or denominator[0][0] != REGION_START
        or denominator[-1][1] != REGION_END
        or any(left[1] != right[0] for left, right in zip(denominator, denominator[1:]))
    ):
        raise ValueError("battle-message classified range denominator changed")
    bundle = b"".join(_take(rom, start, end - start) for start, end in denominator)
    if len(bundle) != 2_740 or _sha(bundle) != REGION_SHA256:
        raise ValueError("battle-message packed bytes changed")

    implementation = {
        label: {"path": path, "sha256": _sha(_safe_file(root, path).read_bytes())}
        for label, path in {
            "exporter": "tools/export_rom_battle_message_text_inventory.py",
            "verifier": "tools/verify_rom_battle_message_text_inventory.py",
            "test": "tests/test_export_rom_battle_message_text_inventory.py",
        }.items()
    }
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "source_bank": bank,
        "pointer_table": {
            "semantic_type": "battle_message_renderer_text_pointer_table_79",
            "range": [TABLE_START, TABLE_END],
            "gba_range": [_addr(TABLE_START), _addr(TABLE_END)],
            "entry_count": TABLE_COUNT,
            "entry_size": 4,
            "sha256": TABLE_SHA256,
            "classified_here": False,
        },
        "records": records,
        "zero_padding": padding,
        "classified_ranges": classified_ranges,
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
        "implementation": implementation,
    }
    return payload, bundle


def _manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "files": {name: _sha(content) for name, content in sorted(files.items())},
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
        raise ValueError("foreign artifact output is not a directory")
    manifest_path = target / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("foreign artifact output directory")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("foreign artifact output directory") from error
    members = list(target.rglob("*"))
    actual = {
        member.relative_to(target).as_posix() for member in members if member.is_file()
    }
    if (
        manifest.get("artifact_schema") != SCHEMA
        or actual != EXPECTED_FILES
        or any(member.is_symlink() for member in members)
    ):
        raise ValueError("foreign artifact output directory")
    try:
        from tools.verify_rom_battle_message_text_inventory import verify_artifact
    except ModuleNotFoundError:
        from verify_rom_battle_message_text_inventory import verify_artifact
    report = verify_artifact(root, target)
    if report.get("verified") is not True:
        raise ValueError(
            f"existing artifact failed independent verification: {report.get('errors', [])}"
        )
    return target


def _replace_output(target: Path, files: dict[str, bytes]) -> None:
    _reject_symlink_components(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(target.parent)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    backup: Path | None = None
    try:
        for name, content in files.items():
            (temporary / name).write_bytes(content)
        _reject_symlink_components(target)
        if target.exists():
            backup = target.with_name(f".{target.name}.old-{uuid.uuid4().hex}")
            os.replace(target, backup)
        _reject_symlink_components(target.parent)
        os.replace(temporary, target)
        if backup is not None:
            shutil.rmtree(backup)
    except BaseException:
        if backup is not None and backup.exists():
            if target.exists():
                shutil.rmtree(target)
            os.replace(backup, target)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    target = _validate_output(root, Path(output))
    payload, bundle = _derive(root)
    files = {PAYLOAD_NAME: _canonical(payload), BUNDLE_NAME: bundle}
    files["manifest.json"] = _canonical(_manifest(payload, files))
    _replace_output(target, files)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    output = args.output_dir if args.output_dir.is_absolute() else args.root / args.output_dir
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
