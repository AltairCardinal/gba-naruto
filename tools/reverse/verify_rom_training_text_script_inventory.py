#!/usr/bin/env python3
"""Independently verify the fixed training text command-script inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "rom-training-text-script-inventory-v1"
VERIFY_SCHEMA = "rom-training-text-script-inventory-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

TABLE_START = 0x59A104
TABLE_COUNT = 45
TABLE_END = TABLE_START + TABLE_COUNT * 4
TABLE_SHA256 = "98b063cc49b8ab7b036b612bd81fb3f564187b54fd963e36c9cdc78909d9876b"
LAST_RECORD_END = 0x007F1D
LAST_RECORD_LIMIT = 0x008000
RECORD_RANGE_SHA256 = "d4658b515cf3f02813546f9ae909a0a00a646a70096470f1475695f9b46ede94"
COMMAND_RANGE_SHA256 = "6c055dc42bb2012bfb1879a07ffcdc765cfe67b129ca8f68f48677b10ab9a4db"
COMMAND_SEQUENCE_SHA256 = "0cc54154efdcb99d953d5ba0b60609241c5539b976a165656253b43a39b23a13"
BUNDLE_SHA256 = "fa9991353e99ecd63d8e0617fb078198b62527d548c8c5eb5fbac173d0302da0"

CONSUMER_RANGE = (0x0932DA, 0x0932E8)
CONSUMER_SHA256 = "0d8de4e88cd69edbbd61df9efefe1d4fcc9898f5693eff5fd5e5304f87385b07"
CONSUMER_LITERAL = 0x093308
INTERPRETER_RANGE = (0x067158, 0x06836E)
INTERPRETER_SHA256 = "211812743de17ef5158ef63bd52deb3271c962b9119bf74f1bbd458b6bec96dd"
DISPATCH_TABLE = 0x067180
DISPATCH_TARGETS = (
    0x06835E,
    0x0671B8,
    0x0671DA,
    0x0671EA,
    0x0671FC,
    0x067210,
    0x067210,
    0x0675E4,
    0x068090,
    0x0674C0,
    0x067570,
    0x0681B0,
    0x068200,
    0x06822C,
)
PARSER_RANGE = (0x06626C, 0x066736)
PARSER_SHA256 = "b7bdea4f0af2836fcc4b3c18a6b54ad019a5e06da62bf110b88779a445e4c9be"
SJIS_LOOKUP_RANGE = (0x065E80, 0x065EB6)
SJIS_LOOKUP_SHA256 = "242a528abb2866b87b760cabe7470db82a4f504cd697be6984333d026f2f2c8e"
SJIS_TABLE = 0x53D644
SJIS_RANGE_COUNT = 31
SJIS_ENTRY_SIZE = 8
SJIS_TABLE_END = SJIS_TABLE + SJIS_RANGE_COUNT * SJIS_ENTRY_SIZE
SJIS_TABLE_SHA256 = "10bff7abebc963193e5490fd876a3f11f294ca89f2918856746ce76f5990e1b1"

PAYLOAD_NAME = "training-text-script-inventory.json"
BUNDLE_NAME = "training-text-script-bytes.bin"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME, BUNDLE_NAME}
EXPECTED_SUMMARY = {
    "pointer_table_count": 1,
    "pointer_slot_count": 45,
    "pointer_table_bytes": 180,
    "null_slot_count": 1,
    "non_null_slot_count": 44,
    "unique_target_count": 44,
    "command_record_count": 44,
    "command_count": 264,
    "embedded_renderer_text_count": 44,
    "embedded_renderer_text_bytes": 1_889,
    "record_bytes": 2_505,
    "classified_range_count": 44,
    "classified_bytes": 2_505,
    "inter_record_gap_bytes": 0,
    "range_overlap_bytes": 0,
    "parse_failure_count": 0,
    "packed_bytes": 2_505,
}
SCOPE = {
    "fixed_45_slot_denominator_complete": True,
    "all_45_slots_classified": True,
    "all_non_null_records_parsed": True,
    "interpreter_used_opcode_contract_bound": True,
    "nested_renderer_consumed_bytes_complete": True,
    "pointer_table_already_classified_by_candidate_overlay": True,
    "natural_gameplay_all_ids_proven": False,
    "unicode_decoding_complete": False,
    "editing_safety_proven": False,
}
LIMITATIONS = [
    "The existing candidate overlay already classifies the 180-byte pointer table; this artifact promotes only the 44 interpreter-consumed records.",
    "The fixed denominator has one null slot (ID 0) and 44 non-null slots (IDs 1..44); it does not claim natural execution of every ID.",
    "Only opcodes 0, 1, 3, 4, 5, and 12 occur in these records and are in this artifact's parser denominator.",
    "Embedded strings are bounded by the actual renderer grammar; Unicode decoding and safe writeback remain unclaimed.",
]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


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


def _decode_bl(data: bytes, offset: int) -> int:
    high = _u16(data, offset)
    low = _u16(data, offset + 2)
    if high >> 11 != 0x1E or low >> 11 != 0x1F:
        raise ValueError("training consumer BL encoding changed")
    displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if displacement >= 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def _decode_literal(data: bytes, offset: int, register: int) -> int:
    instruction = _u16(data, offset)
    if instruction >> 11 != 9 or ((instruction >> 8) & 7) != register:
        raise ValueError("training consumer literal-load encoding changed")
    return ((offset + 4) & ~3) + (instruction & 0xFF) * 4


def _root_file(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = candidate.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    return resolved


def _evidence(
    rom: bytes, start: int, end: int, expected_digest: str, label: str
) -> dict[str, Any]:
    if _digest(_bounded(rom, start, end)) != expected_digest:
        raise ValueError(f"training {label} evidence changed")
    return {
        "range": [start, end],
        "gba_range": [_gba(start), _gba(end)],
        "sha256": expected_digest,
    }


def _require_words(rom: bytes, start: int, words: tuple[int, ...], label: str) -> None:
    found = tuple(_u16(rom, start + index * 2) for index in range(len(words)))
    if found != words:
        raise ValueError(f"training interpreter semantics changed: {label}")


def _independent_consumer_contract(rom: bytes) -> dict[str, Any]:
    consumer = _evidence(rom, *CONSUMER_RANGE, CONSUMER_SHA256, "consumer")
    interpreter = _evidence(
        rom, *INTERPRETER_RANGE, INTERPRETER_SHA256, "interpreter"
    )
    parser = _evidence(rom, *PARSER_RANGE, PARSER_SHA256, "renderer parser")
    lookup = _evidence(rom, *SJIS_LOOKUP_RANGE, SJIS_LOOKUP_SHA256, "SJIS lookup")
    range_table = _evidence(
        rom, SJIS_TABLE, SJIS_TABLE_END, SJIS_TABLE_SHA256, "SJIS table"
    )

    _require_words(
        rom,
        CONSUMER_RANGE[0],
        (0x490B, 0x79A0, 0x0080, 0x1840, 0x6800, 0xF7D3, 0xFF38),
        "consumer",
    )
    if (
        _decode_literal(rom, CONSUMER_RANGE[0], 1) != CONSUMER_LITERAL
        or _u32(rom, CONSUMER_LITERAL) != ROM_BASE + TABLE_START
        or _decode_bl(rom, 0x0932E4) != INTERPRETER_RANGE[0]
    ):
        raise ValueError("training consumer data flow changed")

    rebuilt_dispatch = tuple(
        _u32(rom, DISPATCH_TABLE + 4 * index) - ROM_BASE
        for index in range(len(DISPATCH_TARGETS))
    )
    if rebuilt_dispatch != DISPATCH_TARGETS:
        raise ValueError("training interpreter dispatch table changed")
    semantic_windows = (
        (0x0671D4, (0x3507, 0xF001, 0xF8BC), "opcode 1 advance"),
        (0x0671F2, (0x9A05, 0x3202, 0x9205), "opcode 3 advance"),
        (0x067206, (0x9B05, 0x3301, 0x9305), "opcode 4 advance"),
        (0x067224, (0x1C26, 0x3602), "opcode 5 text start"),
        (0x06740C, (0x6838, 0x2520, 0x4028, 0x3601), "opcode 5 text end"),
        (0x06748C, (0x9605, 0xF000, 0xFF61), "opcode 5 advance"),
        (0x068200, (0x9E05, 0x3601), "opcode 12 advance"),
        (0x068224, (0x9605, 0xE095), "opcode 12 dispatch"),
        (0x068352, (0x9505, 0x2600, 0x2E00, 0xD101), "dispatch helper"),
    )
    for start, words, label in semantic_windows:
        _require_words(rom, start, words, label)
    if (
        _decode_bl(rom, 0x0671D6) != 0x068352
        or _decode_bl(rom, 0x06723C) != PARSER_RANGE[0]
        or _decode_bl(rom, 0x06748E) != 0x068354
        or _decode_bl(rom, 0x06835A) != 0x067166
    ):
        raise ValueError("training interpreter call semantics changed")

    return {
        "training_consumer": {
            **consumer,
            "table_literal_offset": CONSUMER_LITERAL,
            "table_address": _gba(TABLE_START),
            "index_source": "training_row_plus_6_u8",
            "index_scale": 4,
            "pointer_load_offset": 0x0932E2,
            "call_offset": 0x0932E4,
            "call_target": _gba(INTERPRETER_RANGE[0]),
        },
        "training_interpreter": {
            **interpreter,
            "dispatch_table": _gba(DISPATCH_TABLE),
            "dispatch_entry_count": len(DISPATCH_TARGETS),
            "dispatch_targets": [_gba(offset) for offset in DISPATCH_TARGETS],
            "used_opcode_contract": {
                "0": "terminate",
                "1": "fixed_7",
                "3": "fixed_2",
                "4": "fixed_1",
                "5": "renderer_text_from_plus_2",
                "12": "fixed_1",
            },
            "renderer_call_offset": 0x06723C,
            "renderer_call_target": _gba(PARSER_RANGE[0]),
        },
        "renderer_parser": parser,
        "sjis_lookup": lookup,
        "sjis_range_table": {
            **range_table,
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
    ranges = []
    for row_index in range(SJIS_RANGE_COUNT):
        row = _bounded(
            rom,
            SJIS_TABLE + row_index * SJIS_ENTRY_SIZE,
            SJIS_TABLE + row_index * SJIS_ENTRY_SIZE + 3,
        )
        start = row[0] | row[1] << 8
        ranges.append((start, start + row[2]))
    return tuple(ranges)


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


def _independent_parse_record(
    data: bytes,
    start: int,
    limit: int,
    sjis_ranges: tuple[tuple[int, int], ...],
) -> dict[str, Any]:
    if not 0 <= start < limit <= len(data):
        raise ValueError("training record has an invalid bounded range")
    cursor = start
    commands: list[dict[str, Any]] = []
    embedded: list[list[int]] = []
    advances = {1: 7, 3: 2, 4: 1, 12: 1}
    while cursor < limit:
        begin = cursor
        opcode = data[begin]
        if opcode in advances:
            cursor = begin + advances[opcode]
            if cursor > limit:
                raise ValueError("training record has a truncated fixed command")
        elif opcode == 5:
            text = begin + 2
            if text > limit:
                raise ValueError("training record has a truncated renderer command")
            cursor = _independent_renderer_end(data, text, limit, sjis_ranges)
            embedded.append([text, cursor])
        elif opcode == 0:
            cursor = begin + 1
        else:
            raise ValueError(f"training record uses unsupported opcode {opcode}")
        commands.append({"opcode": opcode, "range": [begin, cursor]})
        if opcode == 0:
            return {
                "end": cursor,
                "commands": commands,
                "opcode_sequence": [command["opcode"] for command in commands],
                "embedded_renderer_ranges": embedded,
            }
    raise ValueError("training record lacks a bounded terminator")


def _expected(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    semantics = _independent_consumer_contract(rom)
    sjis = _independent_sjis_ranges(rom)
    table = _bounded(rom, TABLE_START, TABLE_END)
    if _digest(table) != TABLE_SHA256:
        raise ValueError("training pointer table differs")
    raw_pointers = [_u32(rom, TABLE_START + 4 * index) for index in range(TABLE_COUNT)]
    null_slots = [index for index, pointer in enumerate(raw_pointers) if pointer == 0]
    if null_slots != [0]:
        raise ValueError("training null-slot denominator differs")
    targets = [pointer - ROM_BASE for pointer in raw_pointers[1:]]
    if targets != sorted(set(targets)) or any(target < 0 or target >= len(rom) for target in targets):
        raise ValueError("training targets are not unique in-ROM offsets")

    records = []
    all_command_ranges = []
    sequence_pairs = []
    opcode_counts: dict[str, int] = {}
    renderer_count = 0
    renderer_bytes = 0
    for zero_index, target in enumerate(targets):
        slot = zero_index + 1
        limit = targets[zero_index + 1] if zero_index + 1 < len(targets) else LAST_RECORD_LIMIT
        parsed = _independent_parse_record(rom, target, limit, sjis)
        expected_end = targets[zero_index + 1] if zero_index + 1 < len(targets) else LAST_RECORD_END
        if parsed["end"] != expected_end:
            raise ValueError(f"training record boundary differs at slot {slot}")
        if parsed["opcode_sequence"] != [1, 5, 4, 12, 3, 0]:
            raise ValueError(f"training opcode sequence differs at slot {slot}")
        for command in parsed["commands"]:
            all_command_ranges.append(command["range"])
            sequence_pairs.append([slot, command["opcode"]])
            key = str(command["opcode"])
            opcode_counts[key] = opcode_counts.get(key, 0) + 1
        for bounds in parsed["embedded_renderer_ranges"]:
            renderer_count += 1
            renderer_bytes += bounds[1] - bounds[0]
        raw = _bounded(rom, target, parsed["end"])
        records.append(
            {
                "record_id": f"training-text-script-{slot:02d}",
                "slot_index": slot,
                "range": [target, parsed["end"]],
                "gba_range": [_gba(target), _gba(parsed["end"])],
                "size": len(raw),
                "sha256": _digest(raw),
                "opcode_sequence": parsed["opcode_sequence"],
                "commands": parsed["commands"],
                "embedded_renderer_ranges": parsed["embedded_renderer_ranges"],
            }
        )

    record_ranges = [record["range"] for record in records]
    if _denominator_digest(record_ranges) != RECORD_RANGE_SHA256:
        raise ValueError("training record denominator differs")
    if _denominator_digest(all_command_ranges) != COMMAND_RANGE_SHA256:
        raise ValueError("training command denominator differs")
    sequence_digest = _digest(
        json.dumps(sequence_pairs, separators=(",", ":")).encode("ascii")
    )
    if sequence_digest != COMMAND_SEQUENCE_SHA256:
        raise ValueError("training command sequence differs")
    if any(left[1] != right[0] for left, right in zip(record_ranges, record_ranges[1:])):
        raise ValueError("training records are not contiguous")
    bundle = b"".join(_bounded(rom, start, end) for start, end in record_ranges)
    if _digest(bundle) != BUNDLE_SHA256:
        raise ValueError("training packed bytes differ")

    classified = []
    packed_cursor = 0
    for record in records:
        next_cursor = packed_cursor + record["size"]
        record["packed_range"] = [packed_cursor, next_cursor]
        classified.append(
            {
                "range_id": record["record_id"],
                "kind": "training_text_command_script",
                "slot_index": record["slot_index"],
                "range": record["range"],
                "size": record["size"],
                "sha256": record["sha256"],
                "packed_range": record["packed_range"],
            }
        )
        packed_cursor = next_cursor

    summary = {
        "pointer_table_count": 1,
        "pointer_slot_count": TABLE_COUNT,
        "pointer_table_bytes": TABLE_END - TABLE_START,
        "null_slot_count": len(null_slots),
        "non_null_slot_count": len(targets),
        "unique_target_count": len(targets),
        "command_record_count": len(records),
        "command_count": len(all_command_ranges),
        "embedded_renderer_text_count": renderer_count,
        "embedded_renderer_text_bytes": renderer_bytes,
        "record_bytes": len(bundle),
        "classified_range_count": len(classified),
        "classified_bytes": len(bundle),
        "inter_record_gap_bytes": 0,
        "range_overlap_bytes": 0,
        "parse_failure_count": 0,
        "packed_bytes": len(bundle),
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError(f"training summary differs: {summary}")
    implementations = {
        label: {"path": path, "sha256": _digest(_root_file(root, path).read_bytes())}
        for label, path in {
            "exporter": "tools/export_rom_training_text_script_inventory.py",
            "verifier": "tools/verify_rom_training_text_script_inventory.py",
            "test": "tests/test_export_rom_training_text_script_inventory.py",
        }.items()
    }
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "pointer_table": {
            "semantic_type": "training_text_command_script_pointer_table",
            "range": [TABLE_START, TABLE_END],
            "gba_range": [_gba(TABLE_START), _gba(TABLE_END)],
            "entry_count": TABLE_COUNT,
            "entry_size": 4,
            "null_slot_indices": null_slots,
            "non_null_slot_indices": list(range(1, TABLE_COUNT)),
            "sha256": TABLE_SHA256,
        },
        "records": records,
        "classified_ranges": classified,
        "record_range_denominator_sha256": RECORD_RANGE_SHA256,
        "command_range_denominator_sha256": COMMAND_RANGE_SHA256,
        "command_sequence_sha256": COMMAND_SEQUENCE_SHA256,
        "command_opcode_counts": dict(sorted(opcode_counts.items(), key=lambda item: int(item[0]))),
        "consumer_evidence": {"decoded_semantics": semantics},
        "summary": summary,
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
                "tools/verify_rom_training_text_script_inventory.py",
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
    report: dict[str, Any] = {
        "schema": VERIFY_SCHEMA,
        "verified": False,
        "errors": [],
    }
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
        report["command_range_denominator_sha256"] = COMMAND_RANGE_SHA256
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
