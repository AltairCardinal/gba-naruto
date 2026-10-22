#!/usr/bin/env python3
"""Independently verify the value-range-selected renderer-text inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "rom-value-range-text-inventory-v1"
VERIFY_SCHEMA = "rom-value-range-text-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

TABLE_START = 0x599F5C
TABLE_COUNT = 38
TABLE_END = TABLE_START + TABLE_COUNT * 4
TABLE_SHA256 = "70e722a0521ed49bf2ac43cbbee960295332d4b857115b595163da29f7731110"
RANGE_MAP_START = 0x542204
RANGE_MAP_END = RANGE_MAP_START + TABLE_COUNT * 4
RANGE_MAP_SHA256 = "d5fc38cb718478c33f58d2175f2b6d35d360e08c83dfcde2a082a3f5852e39c9"
RECORD_START = 0x542E
RECORD_END = 0x578C
RECORD_RANGE_SHA256 = "90be672576fa1ecba130596da7304d92283f5f77e7b89ee8a42ac41e46f42ef0"
CLASSIFIED_RANGE_SHA256 = "b8a6f9ab5543d67b301a0bc41d2fba960f5d2aaecd9dd9c52455d81670510873"
BUNDLE_SHA256 = "88f201f21194087ff7643f1822d0b89c309feff497fbef6155ff5ae6ce6bc3d0"

CONSUMER_RANGE = (0x087484, 0x0874E0)
CONSUMER_SHA256 = "a9ca68ffde22e43f3aecc742d732be737fc49be134cda7222d86dc9f9c79a493"
TABLE_LITERAL = 0x0874B4
INPUT_LITERAL = 0x0874B8
RANGE_MAP_LITERAL = 0x0874BC
BRIDGE_RANGE = (0x066758, 0x066790)
BRIDGE_SHA256 = "75de35c89077d45929f63af9f7b1aeddd6ad8bbcc7f4f1982f7d596b5140dd8c"
PARSER_RANGE = (0x06626C, 0x066736)
PARSER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
SJIS_LOOKUP_RANGE = (0x065E80, 0x065EB6)
SJIS_LOOKUP_SHA256 = "242a528abb2866b87b760cabe7470db82a4f504cd697be6984333d026f2f2c8e"
SJIS_TABLE = 0x53D644
SJIS_RANGE_COUNT = 31
SJIS_ENTRY_SIZE = 8
SJIS_TABLE_END = SJIS_TABLE + SJIS_RANGE_COUNT * SJIS_ENTRY_SIZE
SJIS_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

PAYLOAD_NAME = "value-range-text-inventory.json"
BUNDLE_NAME = "value-range-text-bytes.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
EXPECTED_SUMMARY = {
    "pointer_table_count": 1,
    "pointer_slot_count": 38,
    "pointer_table_bytes": 152,
    "value_range_map_count": 1,
    "value_range_entry_count": 38,
    "value_range_map_bytes": 152,
    "renderer_record_count": 38,
    "renderer_consumed_bytes": 862,
    "classified_range_count": 39,
    "classified_bytes": 1_014,
    "inter_record_gap_bytes": 0,
    "range_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_bytes": 1_014,
}
SCOPE = {
    "fixed_38_slot_denominator_complete": True,
    "all_pointer_slots_parser_bounded": True,
    "value_range_map_structure_complete": True,
    "pointer_table_already_classified_by_candidate_overlay": True,
    "runtime_input_bounds_proven": False,
    "natural_gameplay_all_ranges_proven": False,
    "unicode_decoding_complete": False,
    "editing_safety_proven": False,
}
LIMITATIONS = [
    "The pointer table is evidence only because the candidate overlay already classifies its 152 bytes.",
    "The 38 value ranges cover 0x0000..0x017B, but the runtime source at 0x02003AD0 is not statically bounded to that domain.",
    "All 38 targets are renderer-parser-bounded; natural execution, Unicode decoding, and safe writeback remain unclaimed.",
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
        raise ValueError("bounded verifier slice escapes input")
    return data[start:end]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 2), "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 4), "little")


def _decode_thumb_bl(data: bytes, offset: int) -> int:
    first = _u16(data, offset)
    second = _u16(data, offset + 2)
    if (first & 0xF800) != 0xF000 or (second & 0xF800) != 0xF800:
        raise ValueError("value-range verifier BL encoding changed")
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


def _source_evidence(
    rom: bytes, start: int, end: int, expected: str, label: str
) -> dict[str, Any]:
    if _digest(_bounded(rom, start, end)) != expected:
        raise ValueError(f"value-range {label} source changed")
    return {
        "range": [start, end],
        "gba_range": [_gba(start), _gba(end)],
        "sha256": expected,
    }


def _independent_value_ranges(rom: bytes) -> list[dict[str, Any]]:
    raw = _bounded(rom, RANGE_MAP_START, RANGE_MAP_END)
    if _digest(raw) != RANGE_MAP_SHA256:
        raise ValueError("value-range map source changed")
    result = []
    next_lower = 0
    for slot in range(TABLE_COUNT):
        offset = RANGE_MAP_START + slot * 4
        lower = _u16(rom, offset)
        upper = _u16(rom, offset + 2)
        if lower != next_lower or upper < lower:
            raise ValueError("value-range map is not a contiguous inclusive partition")
        next_lower = upper + 1
        result.append(
            {
                "slot_index": slot,
                "inclusive_range": [lower, upper],
                "range": [offset, offset + 4],
            }
        )
    if next_lower != 0x017C:
        raise ValueError("value-range map terminal domain changed")
    return result


def _independent_consumer_contract(rom: bytes) -> dict[str, Any]:
    consumer = _source_evidence(
        rom, *CONSUMER_RANGE, CONSUMER_SHA256, "selector consumer"
    )
    bridge = _source_evidence(rom, *BRIDGE_RANGE, BRIDGE_SHA256, "renderer bridge")
    parser = _source_evidence(rom, *PARSER_RANGE, PARSER_SHA256, "renderer parser")
    lookup = _source_evidence(
        rom, *SJIS_LOOKUP_RANGE, SJIS_LOOKUP_SHA256, "SJIS lookup"
    )
    sjis_table = _source_evidence(
        rom, SJIS_TABLE, SJIS_TABLE_END, SJIS_TABLE_SHA256, "SJIS range table"
    )
    ranges = _independent_value_ranges(rom)
    if (
        _u32(rom, TABLE_LITERAL) != ROM_BASE + TABLE_START
        or _u32(rom, INPUT_LITERAL) != 0x02003AD0
        or _u32(rom, RANGE_MAP_LITERAL) != ROM_BASE + RANGE_MAP_START
        or _decode_thumb_bl(rom, 0x0874DC) != BRIDGE_RANGE[0]
        or _decode_thumb_bl(rom, 0x06678A) != PARSER_RANGE[0]
    ):
        raise ValueError("value-range selector consumer data flow changed")
    return {
        "value_range_selector": {
            **consumer,
            "pointer_table_literal_offset": TABLE_LITERAL,
            "pointer_table_address": _gba(TABLE_START),
            "runtime_input_literal_offset": INPUT_LITERAL,
            "runtime_input_address": "0x02003AD0",
            "value_range_map_literal_offset": RANGE_MAP_LITERAL,
            "value_range_map_address": _gba(RANGE_MAP_START),
            "entry_count": len(ranges),
            "index_scale": 4,
            "pointer_load_offset": 0x0874C4,
            "bridge_call_offset": 0x0874DC,
            "bridge_call_target": _gba(BRIDGE_RANGE[0]),
        },
        "renderer_bridge": {
            **bridge,
            "pointer_capture_offset": 0x066760,
            "parser_argument_offset": 0x066788,
            "parser_call_offset": 0x06678A,
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
        lower = row[0] | row[1] << 8
        result.append((lower, lower + row[2]))
    return tuple(result)


def _independent_renderer_end(
    data: bytes,
    cursor: int,
    limit: int,
    sjis_ranges: tuple[tuple[int, int], ...],
) -> int:
    if not 0 <= cursor < limit <= len(data):
        raise ValueError("renderer text has an invalid bounded range")
    while cursor < limit:
        value = data[cursor]
        if value == 0:
            return cursor + 1
        if value == 1:
            advance = 2
        elif value == 2:
            advance = 3
        elif 0x80 <= value <= 0x9F:
            advance = 2
        elif value >= 0xA0:
            if cursor + 1 >= limit:
                raise ValueError("renderer text has a truncated high-byte pair")
            pair = value * 0x100 + data[cursor + 1]
            advance = 1
            for lower, upper in sjis_ranges:
                if lower <= pair < upper:
                    advance = 2
                    break
        else:
            advance = 1
        if cursor + advance > limit:
            raise ValueError("renderer text has a truncated control or pair")
        cursor += advance
    raise ValueError("renderer text lacks a bounded terminator")


def _expected(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    semantics = _independent_consumer_contract(rom)
    value_ranges = _independent_value_ranges(rom)
    pointer_bytes = _bounded(rom, TABLE_START, TABLE_END)
    if _digest(pointer_bytes) != TABLE_SHA256:
        raise ValueError("value-range pointer table source changed")
    pointers = [_u32(rom, TABLE_START + slot * 4) for slot in range(TABLE_COUNT)]
    targets = [pointer - ROM_BASE for pointer in pointers]
    if targets != sorted(set(targets)) or any(target < 0 or target >= len(rom) for target in targets):
        raise ValueError("value-range pointer targets are not unique increasing ROM offsets")

    sjis = _independent_sjis_ranges(rom)
    records = []
    for slot, target in enumerate(targets):
        upper_bound = targets[slot + 1] if slot + 1 < len(targets) else 0x5800
        end = _independent_renderer_end(rom, target, upper_bound, sjis)
        required_end = targets[slot + 1] if slot + 1 < len(targets) else RECORD_END
        if end != required_end:
            raise ValueError(f"value-range record parser boundary changed at slot {slot}")
        raw = _bounded(rom, target, end)
        records.append(
            {
                "record_id": f"value-range-text-{slot:02d}",
                "slot_index": slot,
                "selected_value_range": value_ranges[slot]["inclusive_range"],
                "range": [target, end],
                "gba_range": [_gba(target), _gba(end)],
                "size": len(raw),
                "sha256": _digest(raw),
            }
        )
    record_ranges = [record["range"] for record in records]
    if (
        record_ranges[0][0] != RECORD_START
        or record_ranges[-1][1] != RECORD_END
        or _denominator_digest(record_ranges) != RECORD_RANGE_SHA256
        or any(left[1] != right[0] for left, right in zip(record_ranges, record_ranges[1:]))
    ):
        raise ValueError("value-range record range denominator changed")

    specs = [
        (record["record_id"], "renderer_text_record", record["slot_index"], record["range"])
        for record in records
    ] + [("value-range-map", "value_range_map", None, [RANGE_MAP_START, RANGE_MAP_END])]
    classified = []
    packed = 0
    for range_id, kind, slot, bounds in specs:
        raw = _bounded(rom, bounds[0], bounds[1])
        item = {
            "range_id": range_id,
            "kind": kind,
            "range": bounds,
            "size": len(raw),
            "sha256": _digest(raw),
            "packed_range": [packed, packed + len(raw)],
        }
        if slot is not None:
            item["slot_index"] = slot
        classified.append(item)
        packed += len(raw)
    classified_ranges = [item["range"] for item in classified]
    if _denominator_digest(classified_ranges) != CLASSIFIED_RANGE_SHA256:
        raise ValueError("value-range classified denominator changed")
    bundle = b"".join(_bounded(rom, start, end) for start, end in classified_ranges)
    if len(bundle) != 1_014 or _digest(bundle) != BUNDLE_SHA256:
        raise ValueError("value-range packed bundle changed")

    implementations = {
        label: {"path": path, "sha256": _digest(_root_file(root, path).read_bytes())}
        for label, path in {
            "exporter": "tools/export_rom_value_range_text_inventory.py",
            "verifier": "tools/verify_rom_value_range_text_inventory.py",
            "test": "tests/test_export_rom_value_range_text_inventory.py",
        }.items()
    }
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "pointer_table": {
            "semantic_type": "value_range_renderer_text_pointer_table_38",
            "range": [TABLE_START, TABLE_END],
            "gba_range": [_gba(TABLE_START), _gba(TABLE_END)],
            "entry_count": TABLE_COUNT,
            "entry_size": 4,
            "sha256": TABLE_SHA256,
        },
        "value_range_map": {
            "semantic_type": "value_range_text_selector_u16_pairs",
            "range": [RANGE_MAP_START, RANGE_MAP_END],
            "gba_range": [_gba(RANGE_MAP_START), _gba(RANGE_MAP_END)],
            "entry_count": TABLE_COUNT,
            "entry_size": 4,
            "sha256": RANGE_MAP_SHA256,
            "entries": value_ranges,
        },
        "records": records,
        "classified_ranges": classified,
        "record_range_denominator_sha256": RECORD_RANGE_SHA256,
        "classified_range_denominator_sha256": CLASSIFIED_RANGE_SHA256,
        "consumer_evidence": {"decoded_semantics": semantics},
        "summary": dict(EXPECTED_SUMMARY),
        "files": {BUNDLE_NAME: {"size": len(bundle), "sha256": BUNDLE_SHA256}},
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
                "tools/verify_rom_value_range_text_inventory.py",
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
        names = {member.relative_to(artifact).as_posix() for member in members if member.is_file()}
        if names != EXPECTED_FILES or any(member.is_symlink() for member in members):
            raise ValueError("artifact file set differs")
        manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_bytes)
        bundle = (artifact / BUNDLE_NAME).read_bytes()
        expected_payload, expected_bundle = _expected(root, rom)
        expected_files = {PAYLOAD_NAME: _canonical(expected_payload), BUNDLE_NAME: expected_bundle}
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
        report["bundle_sha256"] = _digest(bundle)
        report["record_range_denominator_sha256"] = RECORD_RANGE_SHA256
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
    artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir
    report = verify_artifact(args.root, artifact)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
