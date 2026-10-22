#!/usr/bin/env python3
"""Independently verify the fixed consumer-bound sprite source packet."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
from typing import Any


def _load_contract():
    path = Path(__file__).with_name("rom_sprite_component_source_contract.py")
    spec = importlib.util.spec_from_file_location("sprite_component_source_contract_for_verify", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load sprite component source contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = _load_contract()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _vector_sha(value: Any) -> str:
    return _sha(json.dumps(value, separators=(",", ":")).encode("ascii"))


def _addr(offset: int) -> str:
    return f"0x{C.ROM_BASE + offset:08X}"


def _safe_file(root: Path, relative: Path | str) -> Path:
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative input: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _take(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"ROM range is outside input: 0x{start:06X}..0x{end:06X}")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<H", rom, offset)[0]


def _u32(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def _rom_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - C.ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer 0x{pointer:08X} is outside ROM")
    return offset


def _literal_load(rom: bytes, expected: dict[str, Any]) -> dict[str, Any]:
    instruction = expected["instruction"]
    raw = _u16(rom, instruction)
    if raw != expected["raw_u16"]:
        raise ValueError("consumer literal-load opcode changed")
    if raw & 0xF800 != 0x4800 or (raw >> 8) & 7 != expected["register"]:
        raise ValueError("consumer literal-load instruction changed")
    literal = ((instruction + 4) & ~3) + (raw & 0xFF) * 4
    if literal != expected["literal"]:
        raise ValueError("consumer literal-load target changed")
    value = _u32(rom, literal)
    if value != expected["value"]:
        raise ValueError("consumer table-pointer literal changed")
    return {
        "instruction": instruction,
        "raw_u16": raw,
        "register": expected["register"],
        "literal": literal,
        "value": value,
    }


def _thumb_bl_target(rom: bytes, source: int) -> tuple[int, tuple[int, int]]:
    first, second = _u16(rom, source), _u16(rom, source + 2)
    if first & 0xF800 != 0xF000 or second & 0xD000 != 0xD000:
        raise ValueError("consumer parser call is not Thumb BL")
    sign = (first >> 10) & 1
    imm10 = first & 0x03FF
    j1 = (second >> 13) & 1
    j2 = (second >> 11) & 1
    i1 = (~(j1 ^ sign)) & 1
    i2 = (~(j2 ^ sign)) & 1
    displacement = (
        (sign << 24)
        | (i1 << 23)
        | (i2 << 22)
        | (imm10 << 12)
        | ((second & 0x07FF) << 1)
    )
    if sign:
        displacement -= 1 << 25
    return source + 4 + displacement, (first, second)


def _decode_consumer(rom: bytes) -> dict[str, Any]:
    definition = _literal_load(rom, C.CONSUMER_LITERAL_LOADS[0])
    animation = _literal_load(rom, C.CONSUMER_LITERAL_LOADS[1])
    call_offset = C.CONSUMER_CALL["instruction"]
    target, raw_call = _thumb_bl_target(rom, call_offset)
    if raw_call != tuple(C.CONSUMER_CALL["raw_u16"]):
        raise ValueError("consumer parser call opcode changed")
    if target != C.CONSUMER_CALL["target"]:
        raise ValueError("consumer parser call target changed")
    setup_start, setup_end = C.CONSUMER_SETUP_RANGE
    setup = _take(rom, setup_start, setup_end)
    if _sha(setup) != C.CONSUMER_SETUP_SHA256:
        raise ValueError("consumer setup window changed")
    path = [list(row) for row in C.CONSUMER_PATH]
    if _vector_sha(path) != C.CONSUMER_PATH_SHA256:
        raise ValueError("consumer path contract changed")
    code_slices: list[list[Any]] = []
    for start, end, name, digest in C.CONSUMER_CODE_SLICES:
        raw = _take(rom, start, end)
        if _sha(raw) != digest:
            raise ValueError(f"consumer {name} code slice changed")
        code_slices.append([start, end, name, digest])
    return {
        "definition_load": definition,
        "animation_load": animation,
        "parser_call": {
            "instruction": call_offset,
            "raw_u16": list(raw_call),
            "target": target,
        },
        "setup_window": [setup_start, setup_end],
        "setup_window_sha256": _sha(setup),
        "consumer_path": path,
        "consumer_path_sha256": _vector_sha(path),
        "code_slices": code_slices,
        "stride_terminator_promotion": "current_unknown_provenance_only",
    }


def _parse_source(rom: bytes) -> dict[str, Any]:
    source_start, source_end = C.SOURCE_RANGE
    source_raw = _take(rom, source_start, source_end)
    if len(source_raw) != C.SOURCE_BYTES:
        raise ValueError("source range size changed")
    if _sha(source_raw) != C.REPORT_HASHES["source_packed_sha256"]:
        raise ValueError("source packed SHA-256 changed")
    semantic_ranges = [list(row) for row in C.SEMANTIC_RANGES]
    if _vector_sha(semantic_ranges) != C.REPORT_HASHES["source_semantic_range_vector_sha256"]:
        raise ValueError("source semantic range denominator changed")

    definition_start, definition_end = C.DEFINITION_TABLE_RANGE
    definition_raw = _take(rom, definition_start, definition_end)
    definition_pointers = [_u32(rom, definition_start + index * 4) for index in range(C.COMPONENT_LIST_COUNT)]
    if tuple(definition_pointers) != C.EXPECTED_DEFINITION_POINTERS:
        raise ValueError("definition pointer denominator changed")
    if _vector_sha(definition_pointers) != C.REPORT_HASHES["component_pointer_vector_sha256"]:
        raise ValueError("definition pointer vector changed")

    component_lists: list[list[Any]] = []
    component_records: list[list[int]] = []
    for list_id, pointer in enumerate(definition_pointers):
        start = _rom_offset(pointer, len(rom))
        expected_start = C.COMPONENT_RANGE[0] + list_id * C.COMPONENT_LIST_SIZE
        expected_end = expected_start + C.COMPONENT_LIST_SIZE
        if start != expected_start:
            raise ValueError("component list pointer target changed")
        raw = _take(rom, start, expected_end)
        if len(raw) != C.COMPONENT_LIST_SIZE:
            raise ValueError("component list size changed")
        if raw[-4:] != C.COMPONENT_TERMINATOR:
            raise ValueError("component terminator changed")
        if _sha(raw) != C.COMPONENT_LIST_SHA256[list_id]:
            raise ValueError(f"component list {list_id} hash changed")
        component_lists.append([list_id, start, expected_end, 8, _sha(raw)])
        for component_id in range(8):
            offset = start + component_id * C.COMPONENT_RECORD_SIZE
            fields = struct.unpack_from(C.COMPONENT_STRUCT, rom, offset)
            component_records.append([list_id, component_id, offset, *fields])
    if len(component_records) != C.COMPONENT_RECORD_COUNT:
        raise ValueError("component record denominator changed")
    if _vector_sha(component_lists) != C.REPORT_HASHES["component_list_vector_sha256"]:
        raise ValueError("component list vector changed")
    if _vector_sha(component_records) != C.REPORT_HASHES["component_vector_sha256"]:
        raise ValueError("component vector changed")
    if _sha(_take(rom, *C.COMPONENT_RANGE)) != C.REPORT_HASHES["component_packed_sha256"]:
        raise ValueError("component source bytes changed")
    if _sha(definition_raw) != C.REPORT_HASHES["definition_table_packed_sha256"]:
        raise ValueError("definition pointer table bytes changed")

    timeline_start, timeline_end = C.TIMELINE_RANGE
    timeline_raw = _take(rom, timeline_start, timeline_end)
    animation_start, animation_end = C.ANIMATION_TABLE_RANGE
    animation_raw = _take(rom, animation_start, animation_end)
    animation_pointers = [_u32(rom, animation_start + index * 4) for index in range(C.TIMELINE_COUNT)]
    if tuple(animation_pointers) != C.EXPECTED_ANIMATION_POINTERS:
        raise ValueError("animation pointer denominator changed")
    if _vector_sha(animation_pointers) != C.REPORT_HASHES["animation_pointer_vector_sha256"]:
        raise ValueError("animation pointer vector changed")
    timelines: list[list[Any]] = []
    keyframes: list[list[int]] = []
    for timeline_id, pointer in enumerate(animation_pointers):
        start = _rom_offset(pointer, len(rom))
        expected_start = timeline_start + timeline_id * C.TIMELINE_SIZE
        expected_end = expected_start + C.TIMELINE_SIZE
        if start != expected_start:
            raise ValueError("timeline pointer target changed")
        raw = _take(rom, start, expected_end)
        if len(raw) != C.TIMELINE_SIZE or raw[-4:] != C.TIMELINE_TERMINATOR:
            raise ValueError("timeline terminator or size changed")
        if _sha(raw) != C.TIMELINE_SHA256[timeline_id]:
            raise ValueError(f"timeline {timeline_id} hash changed")
        duration = 0
        for keyframe_id in range(3):
            offset = start + keyframe_id * C.KEYFRAME_SIZE
            frame_id, hold_frames = struct.unpack_from("<HH", rom, offset)
            if frame_id >= C.COMPONENT_LIST_COUNT or hold_frames <= 0:
                raise ValueError("timeline keyframe domain changed")
            duration += hold_frames
            keyframes.append([timeline_id, keyframe_id, offset, frame_id, hold_frames])
        if duration != 16:
            raise ValueError("timeline duration changed")
        timelines.append([timeline_id, start, expected_end, 3, _sha(raw)])
    if _vector_sha(timelines) != C.REPORT_HASHES["timeline_vector_sha256"]:
        raise ValueError("timeline vector changed")
    if _vector_sha(keyframes) != C.REPORT_HASHES["keyframe_vector_sha256"]:
        raise ValueError("keyframe vector changed")
    if _sha(timeline_raw) != C.REPORT_HASHES["timeline_packed_sha256"]:
        raise ValueError("timeline source bytes changed")
    if _sha(animation_raw) != C.REPORT_HASHES["animation_table_packed_sha256"]:
        raise ValueError("animation pointer table bytes changed")
    return {
        "source": {
            "range": [source_start, source_end],
            "gba_range": [_addr(source_start), _addr(source_end)],
            "bytes": C.SOURCE_BYTES,
            "packed_sha256": _sha(source_raw),
            "semantic_ranges": semantic_ranges,
            "semantic_range_vector_sha256": _vector_sha(semantic_ranges),
        },
        "components": {
            "range": list(C.COMPONENT_RANGE),
            "gba_range": [_addr(C.COMPONENT_RANGE[0]), _addr(C.COMPONENT_RANGE[1])],
            "bytes": C.COMPONENT_BYTES,
            "list_count": C.COMPONENT_LIST_COUNT,
            "record_count": len(component_records),
            "terminator_count": C.COMPONENT_LIST_COUNT,
            "pointer_values": definition_pointers,
            "pointer_vector_sha256": _vector_sha(definition_pointers),
            "lists": component_lists,
            "list_vector_sha256": _vector_sha(component_lists),
            "component_records": component_records,
            "component_vector_sha256": _vector_sha(component_records),
            "packed_sha256": _sha(_take(rom, *C.COMPONENT_RANGE)),
        },
        "definition_table": {
            "range": list(C.DEFINITION_TABLE_RANGE),
            "gba_range": [_addr(C.DEFINITION_TABLE_RANGE[0]), _addr(C.DEFINITION_TABLE_RANGE[1])],
            "bytes": C.DEFINITION_TABLE_BYTES,
            "slot_count": C.COMPONENT_LIST_COUNT,
            "packed_sha256": _sha(definition_raw),
        },
        "timelines": {
            "range": list(C.TIMELINE_RANGE),
            "gba_range": [_addr(C.TIMELINE_RANGE[0]), _addr(C.TIMELINE_RANGE[1])],
            "bytes": C.TIMELINE_BYTES,
            "timeline_count": C.TIMELINE_COUNT,
            "keyframe_count": len(keyframes),
            "terminator_count": C.TIMELINE_COUNT,
            "timelines": timelines,
            "timeline_vector_sha256": _vector_sha(timelines),
            "keyframes": keyframes,
            "keyframe_vector_sha256": _vector_sha(keyframes),
            "packed_sha256": _sha(timeline_raw),
        },
        "animation_table": {
            "range": list(C.ANIMATION_TABLE_RANGE),
            "gba_range": [_addr(C.ANIMATION_TABLE_RANGE[0]), _addr(C.ANIMATION_TABLE_RANGE[1])],
            "bytes": C.ANIMATION_TABLE_BYTES,
            "slot_count": C.TIMELINE_COUNT,
            "pointer_values": animation_pointers,
            "pointer_vector_sha256": _vector_sha(animation_pointers),
            "packed_sha256": _sha(animation_raw),
        },
    }


def _validate_coverage(root: Path, raw: bytes | None = None) -> dict[str, Any]:
    if raw is None:
        raw = _safe_file(root, C.COVERAGE_PATH).read_bytes()
    if _sha(raw) != C.COVERAGE_SHA256:
        raise ValueError("coverage identity changed")
    try:
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("coverage is not valid JSON") from error
    expected_base_rom = {"path": C.ROM_PATH.as_posix(), "size": C.ROM_SIZE, "sha256": C.ROM_SHA256}
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage schema changed")
    if coverage.get("base_rom") != expected_base_rom or coverage.get("domain") != [0, C.ROM_SIZE]:
        raise ValueError("coverage ROM domain changed")
    if coverage.get("policy", {}).get("ranges_are_half_open") is not True:
        raise ValueError("coverage range policy changed")
    summary = coverage.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("coverage summary is missing")
    for key, value in C.BASELINE_COVERAGE_SUMMARY.items():
        if summary.get(key) != value:
            raise ValueError(f"coverage baseline {key} changed")
    if summary.get("accounted_bytes") != C.ROM_SIZE:
        raise ValueError("coverage accounted bytes changed")
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    if not isinstance(segments, list) or not isinstance(claims, list):
        raise ValueError("coverage ledgers are missing")
    if len(segments) != C.BASELINE_COVERAGE_SUMMARY["segment_count"] or len(claims) != C.BASELINE_COVERAGE_SUMMARY["claim_count"]:
        raise ValueError("coverage ledger counts changed")
    cursor = 0
    classified = 0
    unknown = 0
    owner: dict[str, Any] | None = None
    for segment in segments:
        bounds = segment.get("range") if isinstance(segment, dict) else None
        if not isinstance(bounds, list) or len(bounds) != 2 or bounds[0] != cursor or not all(isinstance(value, int) for value in bounds) or bounds[0] >= bounds[1]:
            raise ValueError("coverage segments are not a partition")
        cursor = bounds[1]
        if segment.get("primary_class") == "unknown":
            unknown += bounds[1] - bounds[0]
        else:
            classified += bounds[1] - bounds[0]
        if bounds[0] <= C.SOURCE_RANGE[0] and C.SOURCE_RANGE[1] <= bounds[1]:
            if owner is not None:
                raise ValueError("source has multiple coverage owners")
            owner = segment
    if cursor != C.ROM_SIZE or classified != C.BASELINE_COVERAGE_SUMMARY["classified_bytes"] or unknown != C.BASELINE_COVERAGE_SUMMARY["unknown_bytes"]:
        raise ValueError("coverage byte summary changed")
    if owner is None or owner.get("range") != list(C.BASELINE_SOURCE_OWNER_RANGE) or owner.get("primary_class") != "unknown" or owner.get("primary_claim_ids") != [] or owner.get("secondary_claim_ids") != []:
        raise ValueError("source current-unknown owner changed")
    provenance_start, provenance_end = C.CURRENT_UNKNOWN_PROVENANCE_RANGE
    provenance_owner = next(
        (
            segment
            for segment in segments
            if segment["range"][0] <= provenance_start
            and provenance_end <= segment["range"][1]
        ),
        None,
    )
    if (
        provenance_owner is None
        or provenance_owner.get("primary_class") != "unknown"
        or provenance_owner.get("primary_claim_ids") != []
        or provenance_owner.get("secondary_claim_ids") != []
    ):
        raise ValueError("stride/terminator current-unknown owner changed")
    for claim in claims:
        bounds = claim.get("range") if isinstance(claim, dict) else None
        if not isinstance(bounds, list) or len(bounds) != 2 or not all(isinstance(value, int) for value in bounds) or bounds[0] >= bounds[1]:
            raise ValueError("coverage claim range is malformed")
        if bounds[0] < C.SOURCE_RANGE[1] and C.SOURCE_RANGE[0] < bounds[1]:
            raise ValueError("source overlaps an existing coverage claim")
    return {
        "schema": coverage["schema"],
        "path": C.COVERAGE_PATH.as_posix(),
        "sha256": C.COVERAGE_SHA256,
        "summary": dict(C.BASELINE_COVERAGE_SUMMARY),
        "classified_plus_unknown": classified + unknown,
        "source_owner": {
            "range": list(owner["range"]),
            "primary_class": owner["primary_class"],
            "primary_claim_ids": list(owner["primary_claim_ids"]),
            "secondary_claim_ids": list(owner["secondary_claim_ids"]),
        },
        "unknown_provenance_owner": {
            "range": list(provenance_owner["range"]),
            "primary_class": provenance_owner["primary_class"],
            "primary_claim_ids": list(provenance_owner["primary_claim_ids"]),
            "secondary_claim_ids": list(provenance_owner["secondary_claim_ids"]),
        },
    }


def validate_coverage(root: Path | str, raw: bytes | None = None) -> dict[str, Any]:
    return _validate_coverage(Path(root).resolve(strict=True), raw)


def validate_baseline(root: Path | str, raw: bytes | None = None) -> dict[str, Any]:
    return validate_coverage(root, raw)


def _implementation(root: Path) -> dict[str, Any]:
    paths = (
        C.ROOT_CONTRACT_PATH,
        Path("tools/export_rom_sprite_component_source.py"),
        Path("tools/verify_rom_sprite_component_source.py"),
        Path("tests/test_export_rom_sprite_component_source.py"),
        Path("tests/test_verify_rom_sprite_component_source.py"),
    )
    dependencies: dict[str, str] = {}
    for relative in paths:
        dependencies[relative.as_posix()] = _sha(_safe_file(root, relative).read_bytes())
    return {
        "runtime_dependency_sha256": dependencies,
        "exporter": {"path": "tools/export_rom_sprite_component_source.py", "sha256": dependencies["tools/export_rom_sprite_component_source.py"]},
        "verifier": {"path": "tools/verify_rom_sprite_component_source.py", "sha256": dependencies["tools/verify_rom_sprite_component_source.py"]},
        "contract": {"path": C.ROOT_CONTRACT_PATH.as_posix(), "sha256": dependencies[C.ROOT_CONTRACT_PATH.as_posix()]},
        "tests": {
            "exporter": {"path": "tests/test_export_rom_sprite_component_source.py", "sha256": dependencies["tests/test_export_rom_sprite_component_source.py"]},
            "verifier": {"path": "tests/test_verify_rom_sprite_component_source.py", "sha256": dependencies["tests/test_verify_rom_sprite_component_source.py"]},
        },
    }


def _rebuild(root: Path, rom: bytes | None = None, coverage: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, C.ROM_PATH).read_bytes()
    if len(rom) != C.ROM_SIZE or _sha(rom) != C.ROM_SHA256:
        raise ValueError("base ROM identity changed")
    parsed = _parse_source(rom)
    consumer = _decode_consumer(rom)
    baseline = _validate_coverage(root, coverage)
    classified_ranges: list[dict[str, Any]] = []
    bundle = bytearray()
    for start, end, kind in C.SEMANTIC_RANGES:
        raw = _take(rom, start, end)
        packed_start = len(bundle)
        bundle.extend(raw)
        classified_ranges.append(
            {
                "id": f"{C.SCHEMA}-{kind}",
                "kind": kind,
                "primary_class": C.SCOPE["primary_class"],
                "claim_kind": C.SCOPE["claim_kind"],
                "promotion_batch": C.SCHEMA,
                "baseline_state": "current_unknown",
                "runtime_reachability_claimed": False,
                "range": [start, end],
                "gba_range": [_addr(start), _addr(end)],
                "size": end - start,
                "bytes_hex": raw.hex(),
                "bytes_sha256": _sha(raw),
                "packed_range": [packed_start, len(bundle)],
                "packed_sha256": _sha(raw),
            }
        )
    packed = bytes(bundle)
    if packed != rom[C.SOURCE_RANGE[0] : C.SOURCE_RANGE[1]] or _sha(packed) != C.REPORT_HASHES["source_packed_sha256"]:
        raise ValueError("packed source differs from ROM source range")
    promotion_range_hash = _vector_sha([row["range"] for row in classified_ranges])
    coverage_baseline = {
        **baseline,
        "promoted_from_unknown_bytes": C.PROMOTED_FROM_UNKNOWN_BYTES,
        "promotion_applied_to_live_coverage": False,
        "excluded_adjacent_range": {
            "range": list(C.EXCLUDED_ADJACENT_RANGE),
            "gba_range": [_addr(C.EXCLUDED_ADJACENT_RANGE[0]), _addr(C.EXCLUDED_ADJACENT_RANGE[1])],
            "bytes": C.EXCLUDED_ADJACENT_RANGE[1] - C.EXCLUDED_ADJACENT_RANGE[0],
            "reason": "outside frozen source range",
        },
    }
    summary = {
        "source_bytes": C.SOURCE_BYTES,
        "semantic_range_count": len(classified_ranges),
        "component_list_count": C.COMPONENT_LIST_COUNT,
        "component_record_count": C.COMPONENT_RECORD_COUNT,
        "timeline_count": C.TIMELINE_COUNT,
        "keyframe_count": C.KEYFRAME_COUNT,
        "promoted_from_unknown_bytes": C.PROMOTED_FROM_UNKNOWN_BYTES,
        "classified_bytes": baseline["summary"]["classified_bytes"],
        "unknown_bytes": baseline["summary"]["unknown_bytes"],
        "classified_plus_unknown": baseline["classified_plus_unknown"],
        "promotion_projected_classified_bytes": baseline["summary"]["classified_bytes"] + C.PROMOTED_FROM_UNKNOWN_BYTES,
        "promotion_projected_unknown_bytes": baseline["summary"]["unknown_bytes"] - C.PROMOTED_FROM_UNKNOWN_BYTES,
        "consumer_code_promoted_bytes": 0,
        "excluded_adjacent_bytes": C.EXCLUDED_ADJACENT_RANGE[1] - C.EXCLUDED_ADJACENT_RANGE[0],
    }
    payload = {
        "schema": C.SCHEMA,
        "artifact_status": "accepted",
        "rom": {"path": C.ROM_PATH.as_posix(), "size": len(rom), "sha256": C.ROM_SHA256},
        "coverage_baseline": coverage_baseline,
        "coverage": coverage_baseline,
        "source": parsed["source"],
        "components": parsed["components"],
        "definition_table": parsed["definition_table"],
        "timelines": parsed["timelines"],
        "animation_table": parsed["animation_table"],
        "consumer": consumer,
        "classified_ranges": classified_ranges,
        "classified_range_denominator_sha256": promotion_range_hash,
        "packed_bytes": packed.hex(),
        "packed_bytes_sha256": _sha(packed),
        "files": {C.BUNDLE_NAME: {"size": len(packed), "sha256": _sha(packed)}},
        "summary": summary,
        "scope": C.SCOPE,
        "limitations": C.LIMITATIONS,
        "implementation": _implementation(root),
    }
    return payload, packed


def rebuild_payload(root: Path | str, rom: bytes | None = None, coverage: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    return _rebuild(Path(root), rom, coverage)


def rebuild_from_rom(root: Path | str, rom: bytes) -> tuple[dict[str, Any], bytes]:
    return rebuild_payload(root, rom=rom)


def _artifact_file(artifact: Path, name: str) -> Path:
    path = artifact / name
    if path.is_symlink():
        raise ValueError(f"artifact member must not be a symlink: {name}")
    resolved = path.resolve(strict=True)
    if resolved != artifact and artifact not in resolved.parents:
        raise ValueError(f"artifact member escapes directory: {name}")
    if not resolved.is_file():
        raise ValueError(f"artifact member is not a file: {name}")
    return resolved


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _manifest(payload: dict[str, Any], payload_bytes: bytes, bundle: bytes) -> dict[str, Any]:
    return {
        "schema": f"{C.SCHEMA}-artifact-manifest-v1",
        "artifact_schema": C.SCHEMA,
        "artifact_status": "accepted",
        "files": {C.PAYLOAD_NAME: _sha(payload_bytes), C.BUNDLE_NAME: _sha(bundle)},
        "producer": payload["implementation"],
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "scope": payload["scope"],
        "verification": {
            "schema": C.VERIFY_SCHEMA,
            "command": ["python3", "tools/verify_rom_sprite_component_source.py", "--root", ".", "--artifact-dir", f"artifacts/{C.SCHEMA}"],
            "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
        },
    }


def verify_artifact(root: Path | str, artifact_dir: Path | str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = Path(root).resolve(strict=True)
        requested = _reject_symlink_components(Path(artifact_dir))
        artifact = requested.resolve(strict=True)
        if not artifact.is_dir():
            raise ValueError("artifact path is not a directory")
        members = list(artifact.rglob("*"))
        if any(member.is_symlink() for member in members):
            raise ValueError("artifact tree contains a symlink")
        actual = {member.relative_to(artifact).as_posix() for member in members if member.is_file()}
        if actual != set(C.EXPECTED_FILES):
            raise ValueError("artifact file denominator differs")
        rom = _safe_file(root, C.ROM_PATH).read_bytes()
        expected_payload, expected_bundle = _rebuild(root, rom=rom)
        payload_bytes = _canonical(expected_payload)
        expected_manifest = _manifest(expected_payload, payload_bytes, expected_bundle)
        manifest = json.loads(_artifact_file(artifact, C.MANIFEST_NAME).read_text(encoding="utf-8"))
        if manifest != expected_manifest:
            raise ValueError("artifact manifest differs from independent reconstruction")
        actual_payload_bytes = _artifact_file(artifact, C.PAYLOAD_NAME).read_bytes()
        if actual_payload_bytes != payload_bytes:
            raise ValueError("artifact payload differs from independent reconstruction")
        actual_payload = json.loads(actual_payload_bytes.decode("utf-8"))
        if actual_payload != expected_payload:
            raise ValueError("artifact payload JSON differs from independent reconstruction")
        actual_bundle = _artifact_file(artifact, C.BUNDLE_NAME).read_bytes()
        if actual_bundle != expected_bundle:
            raise ValueError("artifact bundle differs from ROM source range")
        if manifest.get("files") != {C.PAYLOAD_NAME: _sha(payload_bytes), C.BUNDLE_NAME: _sha(expected_bundle)}:
            raise ValueError("artifact file hashes differ")
    except (OSError, ValueError, KeyError, TypeError, struct.error, UnicodeDecodeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    result: dict[str, Any] = {
        "schema": C.VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
    }
    if not errors:
        result.update(expected_payload["summary"])
        result.update(
            {
                "rom_sha256": C.ROM_SHA256,
                "coverage_sha256": C.COVERAGE_SHA256,
                "packed_bytes_sha256": C.REPORT_HASHES["source_packed_sha256"],
                "bundle_sha256": _sha(expected_bundle),
            }
        )
    return result


def verify_rom_sprite_component_source(root: Path | str, artifact_dir: Path | str) -> dict[str, Any]:
    return verify_artifact(root, artifact_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, default=Path(f"artifacts/{C.SCHEMA}"))
    args = parser.parse_args()
    result = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
