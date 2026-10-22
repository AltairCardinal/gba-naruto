#!/usr/bin/env python3
"""Export the fixed 45-slot training text command-script inventory."""

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


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _range_hash(ranges: list[list[int]]) -> str:
    return _sha(json.dumps(ranges, separators=(",", ":")).encode("ascii"))


def _addr(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _take(data: bytes, start: int, size: int) -> bytes:
    if start < 0 or size < 0 or start + size > len(data):
        raise ValueError("bounded ROM slice escapes input")
    return data[start : start + size]


def _half(data: bytes, offset: int) -> int:
    return int.from_bytes(_take(data, offset, 2), "little")


def _word(data: bytes, offset: int) -> int:
    return int.from_bytes(_take(data, offset, 4), "little")


def _thumb_bl_target(data: bytes, offset: int) -> int:
    first = _half(data, offset)
    second = _half(data, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("training consumer BL encoding changed")
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return offset + 4 + delta


def _literal_offset(offset: int, instruction: int, register: int) -> int:
    if instruction & 0xF800 != 0x4800 or (instruction >> 8) & 7 != register:
        raise ValueError("training consumer literal-load encoding changed")
    return ((offset + 4) & ~3) + (instruction & 0xFF) * 4


def _safe_file(root: Path, relative: Path | str) -> Path:
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = path.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    return resolved


def _slice_evidence(
    rom: bytes, bounds: tuple[int, int], digest: str, label: str
) -> dict[str, Any]:
    start, end = bounds
    if _sha(_take(rom, start, end - start)) != digest:
        raise ValueError(f"training {label} evidence changed")
    return {
        "range": [start, end],
        "gba_range": [_addr(start), _addr(end)],
        "sha256": digest,
    }


def _assert_halfwords(rom: bytes, offset: int, expected: tuple[int, ...], label: str) -> None:
    actual = tuple(_half(rom, offset + index * 2) for index in range(len(expected)))
    if actual != expected:
        raise ValueError(f"training interpreter semantics changed: {label}")


def _decode_training_contract(rom: bytes) -> dict[str, Any]:
    consumer = _slice_evidence(rom, CONSUMER_RANGE, CONSUMER_SHA256, "consumer")
    interpreter = _slice_evidence(
        rom, INTERPRETER_RANGE, INTERPRETER_SHA256, "interpreter"
    )
    parser = _slice_evidence(rom, PARSER_RANGE, PARSER_SHA256, "renderer parser")
    sjis_lookup = _slice_evidence(
        rom, SJIS_LOOKUP_RANGE, SJIS_LOOKUP_SHA256, "SJIS lookup"
    )
    sjis_table = _slice_evidence(
        rom, (SJIS_TABLE, SJIS_TABLE_END), SJIS_TABLE_SHA256, "SJIS table"
    )

    consumer_vector = (0x490B, 0x79A0, 0x0080, 0x1840, 0x6800, 0xF7D3, 0xFF38)
    _assert_halfwords(rom, CONSUMER_RANGE[0], consumer_vector, "consumer")
    literal = _literal_offset(CONSUMER_RANGE[0], consumer_vector[0], 1)
    if (
        literal != CONSUMER_LITERAL
        or _word(rom, literal) != ROM_BASE + TABLE_START
        or _thumb_bl_target(rom, 0x0932E4) != INTERPRETER_RANGE[0]
    ):
        raise ValueError("training consumer data flow changed")

    actual_dispatch = tuple(
        _word(rom, DISPATCH_TABLE + index * 4) - ROM_BASE
        for index in range(len(DISPATCH_TARGETS))
    )
    if actual_dispatch != DISPATCH_TARGETS:
        raise ValueError("training interpreter dispatch table changed")
    _assert_halfwords(rom, 0x0671D4, (0x3507, 0xF001, 0xF8BC), "opcode 1 advance")
    _assert_halfwords(rom, 0x0671F2, (0x9A05, 0x3202, 0x9205), "opcode 3 advance")
    _assert_halfwords(rom, 0x067206, (0x9B05, 0x3301, 0x9305), "opcode 4 advance")
    _assert_halfwords(rom, 0x067224, (0x1C26, 0x3602), "opcode 5 text start")
    _assert_halfwords(rom, 0x06740C, (0x6838, 0x2520, 0x4028, 0x3601), "opcode 5 text end")
    _assert_halfwords(rom, 0x06748C, (0x9605, 0xF000, 0xFF61), "opcode 5 advance")
    _assert_halfwords(rom, 0x068200, (0x9E05, 0x3601), "opcode 12 advance")
    _assert_halfwords(rom, 0x068224, (0x9605, 0xE095), "opcode 12 dispatch")
    _assert_halfwords(rom, 0x068352, (0x9505, 0x2600, 0x2E00, 0xD101), "dispatch helper")
    if (
        _thumb_bl_target(rom, 0x0671D6) != 0x068352
        or _thumb_bl_target(rom, 0x06723C) != PARSER_RANGE[0]
        or _thumb_bl_target(rom, 0x06748E) != 0x068354
        or _thumb_bl_target(rom, 0x06835A) != 0x067166
    ):
        raise ValueError("training interpreter call semantics changed")

    return {
        "training_consumer": {
            **consumer,
            "table_literal_offset": CONSUMER_LITERAL,
            "table_address": _addr(TABLE_START),
            "index_source": "training_row_plus_6_u8",
            "index_scale": 4,
            "pointer_load_offset": 0x0932E2,
            "call_offset": 0x0932E4,
            "call_target": _addr(INTERPRETER_RANGE[0]),
        },
        "training_interpreter": {
            **interpreter,
            "dispatch_table": _addr(DISPATCH_TABLE),
            "dispatch_entry_count": len(DISPATCH_TARGETS),
            "dispatch_targets": [_addr(offset) for offset in DISPATCH_TARGETS],
            "used_opcode_contract": {
                "0": "terminate",
                "1": "fixed_7",
                "3": "fixed_2",
                "4": "fixed_1",
                "5": "renderer_text_from_plus_2",
                "12": "fixed_1",
            },
            "renderer_call_offset": 0x06723C,
            "renderer_call_target": _addr(PARSER_RANGE[0]),
        },
        "renderer_parser": parser,
        "sjis_lookup": sjis_lookup,
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


def _parse_training_record(
    data: bytes,
    start: int,
    limit: int,
    sjis_ranges: tuple[tuple[int, int], ...],
) -> dict[str, Any]:
    if start < 0 or start >= limit or limit > len(data):
        raise ValueError("training record has an invalid bounded range")
    cursor = start
    commands = []
    embedded = []
    fixed_width = {1: 7, 3: 2, 4: 1, 12: 1}
    while cursor < limit:
        command_start = cursor
        opcode = data[cursor]
        if opcode == 0:
            cursor += 1
        elif opcode in fixed_width:
            cursor += fixed_width[opcode]
            if cursor > limit:
                raise ValueError("training record has a truncated fixed command")
        elif opcode == 5:
            if cursor + 2 > limit:
                raise ValueError("training record has a truncated renderer command")
            text_start = cursor + 2
            cursor = _renderer_end(data, text_start, limit, sjis_ranges)
            embedded.append([text_start, cursor])
        else:
            raise ValueError(f"training record uses unsupported opcode {opcode}")
        commands.append({"opcode": opcode, "range": [command_start, cursor]})
        if opcode == 0:
            return {
                "end": cursor,
                "commands": commands,
                "opcode_sequence": [item["opcode"] for item in commands],
                "embedded_renderer_ranges": embedded,
            }
    raise ValueError("training record lacks a bounded terminator")


def _derive(root: Path) -> tuple[dict[str, Any], bytes]:
    rom_path = _safe_file(root, ROM_PATH)
    rom = rom_path.read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    semantics = _decode_training_contract(rom)
    sjis = _sjis_ranges(rom)
    table_raw = _take(rom, TABLE_START, TABLE_END - TABLE_START)
    if _sha(table_raw) != TABLE_SHA256:
        raise ValueError("training pointer table differs")
    pointers = [_word(rom, TABLE_START + index * 4) for index in range(TABLE_COUNT)]
    null_slots = [index for index, pointer in enumerate(pointers) if pointer == 0]
    if null_slots != [0]:
        raise ValueError("training null-slot denominator differs")
    targets = [pointer - ROM_BASE for pointer in pointers[1:]]
    if any(not 0 <= target < len(rom) for target in targets):
        raise ValueError("training pointer escapes ROM")
    if targets != sorted(set(targets)):
        raise ValueError("training targets are not unique and strictly increasing")

    records = []
    command_ranges = []
    command_sequence = []
    opcode_counts: dict[str, int] = {}
    embedded_count = 0
    embedded_bytes = 0
    for position, target in enumerate(targets):
        slot = position + 1
        limit = targets[position + 1] if position + 1 < len(targets) else LAST_RECORD_LIMIT
        parsed = _parse_training_record(rom, target, limit, sjis)
        end = parsed["end"]
        expected_end = targets[position + 1] if position + 1 < len(targets) else LAST_RECORD_END
        if end != expected_end:
            raise ValueError(f"training record boundary differs at slot {slot}")
        if parsed["opcode_sequence"] != [1, 5, 4, 12, 3, 0]:
            raise ValueError(f"training opcode sequence differs at slot {slot}")
        for command in parsed["commands"]:
            command_ranges.append(command["range"])
            command_sequence.append([slot, command["opcode"]])
            key = str(command["opcode"])
            opcode_counts[key] = opcode_counts.get(key, 0) + 1
        for bounds in parsed["embedded_renderer_ranges"]:
            embedded_count += 1
            embedded_bytes += bounds[1] - bounds[0]
        raw = rom[target:end]
        records.append(
            {
                "record_id": f"training-text-script-{slot:02d}",
                "slot_index": slot,
                "range": [target, end],
                "gba_range": [_addr(target), _addr(end)],
                "size": len(raw),
                "sha256": _sha(raw),
                "opcode_sequence": parsed["opcode_sequence"],
                "commands": parsed["commands"],
                "embedded_renderer_ranges": parsed["embedded_renderer_ranges"],
            }
        )

    record_ranges = [record["range"] for record in records]
    if _range_hash(record_ranges) != RECORD_RANGE_SHA256:
        raise ValueError("training record denominator differs")
    if _range_hash(command_ranges) != COMMAND_RANGE_SHA256:
        raise ValueError("training command denominator differs")
    if _sha(json.dumps(command_sequence, separators=(",", ":")).encode("ascii")) != COMMAND_SEQUENCE_SHA256:
        raise ValueError("training command sequence differs")
    if any(left[1] != right[0] for left, right in zip(record_ranges, record_ranges[1:])):
        raise ValueError("training records are not contiguous")

    bundle = b"".join(rom[start:end] for start, end in record_ranges)
    if _sha(bundle) != BUNDLE_SHA256:
        raise ValueError("training packed bytes differ")
    packed_start = 0
    classified = []
    for record in records:
        packed_end = packed_start + record["size"]
        record["packed_range"] = [packed_start, packed_end]
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
        packed_start = packed_end

    summary = {
        "pointer_table_count": 1,
        "pointer_slot_count": TABLE_COUNT,
        "pointer_table_bytes": TABLE_END - TABLE_START,
        "null_slot_count": len(null_slots),
        "non_null_slot_count": len(targets),
        "unique_target_count": len(targets),
        "command_record_count": len(records),
        "command_count": len(command_ranges),
        "embedded_renderer_text_count": embedded_count,
        "embedded_renderer_text_bytes": embedded_bytes,
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

    implementation = {
        label: {"path": path, "sha256": _sha(_safe_file(root, path).read_bytes())}
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
            "gba_range": [_addr(TABLE_START), _addr(TABLE_END)],
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
                "tools/verify_rom_training_text_script_inventory.py",
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
    actual = {member.relative_to(target).as_posix() for member in members if member.is_file()}
    if (
        manifest.get("artifact_schema") != SCHEMA
        or actual != EXPECTED_FILES
        or any(member.is_symlink() for member in members)
    ):
        raise ValueError("foreign artifact output directory")
    try:
        from tools.verify_rom_training_text_script_inventory import verify_artifact
    except ModuleNotFoundError:
        from verify_rom_training_text_script_inventory import verify_artifact
    report = verify_artifact(root, target)
    if report.get("verified") is not True:
        raise ValueError(f"existing artifact failed independent verification: {report.get('errors', [])}")
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
