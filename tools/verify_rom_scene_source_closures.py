#!/usr/bin/env python3
"""Independently rebuild and verify rom-scene-source-closures-v1."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import rom_scene_source_closures_contract as C  # noqa: E402


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vector_digest(value: Any) -> str:
    compact = json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n"
    return _digest(compact.encode())


def _packed_bytes(rom: bytes, ranges: list[tuple[int, int]]) -> bytes:
    return b"".join(rom[start:end] for start, end in ranges)


def _input_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe input path: {relative}")
    current = base
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = current.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _coverage_segments(root: Path) -> tuple[bytes, list[dict[str, Any]]]:
    directory = (root / C.PRECOVERAGE_ARTIFACT).resolve(strict=True)
    if not directory.is_relative_to(root.resolve(strict=True)) \
            or not directory.is_dir() \
            or {path.name for path in directory.iterdir()} \
            != {C.MANIFEST_NAME, C.PRECOVERAGE_ARCHIVE_NAME}:
        raise ValueError("immutable precoverage artifact changed")
    manifest_raw = _input_file(
        root, C.PRECOVERAGE_ARTIFACT / C.MANIFEST_NAME).read_bytes()
    archive_raw = _input_file(
        root, C.PRECOVERAGE_ARTIFACT / C.PRECOVERAGE_ARCHIVE_NAME).read_bytes()
    if len(manifest_raw) != C.PRECOVERAGE_MANIFEST_SIZE \
            or _digest(manifest_raw) != C.PRECOVERAGE_MANIFEST_SHA256 \
            or len(archive_raw) != C.PRECOVERAGE_ARCHIVE_SIZE \
            or _digest(archive_raw) != C.PRECOVERAGE_ARCHIVE_SHA256:
        raise ValueError("immutable precoverage identity changed")
    manifest = json.loads(manifest_raw)
    record = manifest.get("files", {}).get(C.PRECOVERAGE_ARCHIVE_NAME)
    if manifest.get("schema") != "rom-byte-coverage-prepromotion-baseline-v1" \
            or manifest.get("artifact_status") != "accepted" \
            or not isinstance(record, dict) \
            or record.get("sha256") != C.PRECOVERAGE_ARCHIVE_SHA256 \
            or record.get("uncompressed_sha256") != C.COVERAGE_SHA256:
        raise ValueError("immutable precoverage manifest changed")
    raw = gzip.decompress(archive_raw)
    if len(raw) != C.PRECOVERAGE_RAW_SIZE or _digest(raw) != C.COVERAGE_SHA256:
        raise ValueError("immutable precoverage payload changed")
    data = json.loads(raw)
    selected = {key: data["summary"][key] for key in C.COVERAGE_SUMMARY}
    if selected != C.COVERAGE_SUMMARY:
        raise ValueError("coverage baseline summary changed")
    low, high = C.ENVELOPE
    overlap = [row for row in data["segments"]
               if row["range"][0] < high and low < row["range"][1]]
    if overlap != [{
            "range": [low, high], "primary_class": "unknown",
            "primary_claim_ids": [], "secondary_claim_ids": [],
            "unknown_reason": "no accepted primary classification claim",
    }]:
        raise ValueError("coverage current-unknown gate changed")
    return raw, data["segments"]


def _lookup_owner(segments: list[dict[str, Any]], offset: int) -> dict[str, Any]:
    matches = [row for row in segments
               if row["range"][0] <= offset < row["range"][1]]
    if len(matches) != 1:
        raise ValueError("consumer coverage membership changed")
    return matches[0]


def _code_owner(row: list[Any]) -> bool:
    return bool(row[4]) and row[3] != "unknown" \
        and ("code" in row[3] or "cfg" in row[3])


def _pointer_denominator(rom: bytes) -> list[list[int]]:
    low, high = C.ENVELOPE
    anchors = (
        (C.ACCIDENTAL_POINTER_WORD, "accidental word"),
        (C.GENUINE_POINTER_WORD, "genuine pointer word"),
        (C.SELF_POINTER_WORD, "self pointer"),
    )
    for (offset, target), label in anchors:
        if struct.unpack_from("<I", rom, offset)[0] != C.ROM_BASE + target:
            raise ValueError(f"{label} changed")
    if struct.unpack_from("<H", rom, C.LDR_ANCHOR[0])[0] != C.LDR_ANCHOR[1]:
        raise ValueError("LDR consumer opcode changed")
    found = []
    for offset in range(0, len(rom) - 3, 2):
        target = struct.unpack_from("<I", rom, offset)[0] - C.ROM_BASE
        if low <= target < high:
            found.append([offset, target])
    outside = sum(not (low <= offset < high) for offset, _ in found)
    inside = len(found) - outside
    actual = (len(found), len({target for _, target in found}), outside, inside)
    expected = (C.POINTER_HIT_COUNT, C.POINTER_TARGET_COUNT,
                C.POINTER_EXTERNAL_COUNT, C.POINTER_SELF_COUNT)
    if actual != expected or _vector_digest(found) != C.POINTER_HIT_VECTOR_SHA256:
        raise ValueError("pointer denominator changed")
    if list(C.ACCIDENTAL_POINTER_WORD) not in found:
        raise ValueError("accidental word changed")
    return found


def _literal_consumers(rom: bytes, pointers: list[list[int]]) -> list[list[int]]:
    decoded = []
    for literal, target in pointers:
        for instruction in range(max(0, literal - 1024), literal, 2):
            opcode = struct.unpack_from("<H", rom, instruction)[0]
            if opcode & 0xF800 == 0x4800:
                resolved = ((instruction + 4) & ~3) + (opcode & 0xFF) * 4
                if resolved == literal:
                    decoded.append([instruction, literal, target])
    actual = (len({row[1] for row in decoded}), len(decoded),
              len({row[2] for row in decoded}))
    expected = (C.LITERAL_COUNT, C.CONSUMER_COUNT, C.CONSUMER_ROOT_COUNT)
    if actual != expected or _vector_digest(decoded) != C.CONSUMER_VECTOR_SHA256:
        raise ValueError("LDR consumer opcode/denominator changed")
    if any(row[1] == C.ACCIDENTAL_POINTER_WORD[0] for row in decoded):
        raise ValueError("accidental word became a consumer")
    return decoded


def _consumer_evidence(
        rom: bytes, decoded: list[list[int]],
        segments: list[dict[str, Any]]) -> tuple[dict[str, Any], list[tuple[int, int]]]:
    memberships = []
    grouped: dict[int, list[list[Any]]] = {}
    all_owner_ids: set[str] = set()
    for instruction, literal, target in decoded:
        owner = _lookup_owner(segments, instruction)
        evidence = [instruction, literal, target, owner["primary_class"],
                    owner["primary_claim_ids"]]
        memberships.append(evidence)
        grouped.setdefault(target, []).append(evidence)
        all_owner_ids.update(owner["primary_claim_ids"])
    if _vector_digest(memberships) != C.MEMBERSHIP_VECTOR_SHA256:
        raise ValueError("consumer coverage membership changed")
    classified = sum(row[3] != "unknown" for row in memberships)
    if (classified, len(memberships) - classified) != (
            C.CLASSIFIED_CONSUMER_COUNT, C.CURRENT_UNKNOWN_CONSUMER_COUNT):
        raise ValueError("consumer coverage denominator changed")

    table_bindings = []
    for root in C.OBJ_TABLE_ROOTS:
        evidence = grouped.get(root, [])
        if not evidence or not all(_code_owner(row) for row in evidence):
            raise ValueError("OBJ table consumer owner changed")
        table_bindings.append({"table_root": root,
                               "consumer_count": len(evidence),
                               "consumers": evidence})

    rejected = []
    sources = []
    for target, evidence in sorted(grouped.items()):
        if target in C.OBJ_TABLE_ROOTS:
            continue
        if not any(_code_owner(row) for row in evidence):
            rejected.append(target)
            continue
        try:
            endpoint = rom.index(0, target, C.ENVELOPE[1]) + 1
        except ValueError as error:
            raise ValueError("source endpoint/terminator changed") from error
        sources.append((target, endpoint))
    if tuple(rejected) != C.REJECTED_UNOWNED_SOURCE_ROOTS:
        raise ValueError("unowned source root denominator changed")
    if (len(sources), sum(end - start for start, end in sources),
            _vector_digest([list(row) for row in sources]),
            _digest(_packed_bytes(rom, sources))) != (
            C.SOURCE_CLAIM_COUNT, C.SOURCE_BYTES, C.SOURCE_RANGE_VECTOR_SHA256,
            C.SOURCE_PACKED_SHA256):
        raise ValueError("source endpoint/terminator changed")
    return {
        "literal_count": C.LITERAL_COUNT,
        "consumer_count": C.CONSUMER_COUNT,
        "root_count": C.CONSUMER_ROOT_COUNT,
        "classified_consumer_count": classified,
        "current_unknown_consumer_count": len(memberships) - classified,
        "consumer_vector_sha256": _vector_digest(decoded),
        "membership_vector_sha256": _vector_digest(memberships),
        "coverage_owner_claim_ids": sorted(all_owner_ids),
        "coverage_memberships": memberships,
        "bindings": decoded,
        "obj_table_bindings": table_bindings,
        "rejected_unowned_source_roots": [
            [target, "no_accepted_instruction_consumer"] for target in rejected
        ],
    }, sources


def _coalesce(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[list[int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            raise ValueError("invalid closure range")
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return [tuple(row) for row in result]


def _obj_records(rom: bytes) -> list[dict[str, Any]]:
    output = []
    for packet_index, spec in enumerate(C.OBJ_SPECS):
        definition_start, definition_end = spec["definition_table_range"]
        animation_start, animation_end = spec["animation_table_range"]
        definition_targets = [
            struct.unpack_from("<I", rom, offset)[0] - C.ROM_BASE
            for offset in range(definition_start, definition_end, 4)
        ]
        animation_targets = [
            struct.unpack_from("<I", rom, offset)[0] - C.ROM_BASE
            for offset in range(animation_start, animation_end, 4)
        ]
        if definition_targets != spec["definition_targets"] \
                or animation_targets != spec["animation_targets"]:
            raise ValueError("OBJ closure internal pointer/size changed")

        count_by_target = dict(zip(spec["definition_targets"],
                                   spec["definition_component_counts"], strict=True))
        definitions = []
        definition_ranges = []
        ordered_definitions = sorted(definition_targets)
        for position, target in enumerate(ordered_definitions):
            end = ordered_definitions[position + 1] \
                if position + 1 < len(ordered_definitions) else definition_start
            raw = rom[target:end]
            component_count = count_by_target[target]
            if len(raw) != component_count * 20 + 4 \
                    or raw[-4:] != bytes.fromhex("ffff0000"):
                raise ValueError("OBJ closure internal pointer/size changed")
            components = []
            for component_index in range(component_count):
                start = target + component_index * 20
                record = rom[start:start + 20]
                width, height = struct.unpack_from("<HH", record, 8)
                if width not in (8, 16, 32, 64) or height not in (8, 16, 32, 64) \
                        or record[18:20] != b"\0\0":
                    raise ValueError("OBJ closure component record changed")
                components.append({
                    "index": component_index, "range": [start, start + 20],
                    "width": width, "height": height,
                    "bytes_sha256": _digest(record),
                })
            definitions.append({
                "target": target, "range": [target, end],
                "component_count": component_count, "components": components,
                "terminator_hex": raw[-4:].hex(),
                "bytes_sha256": _digest(raw),
            })
            definition_ranges.append((target, end))

        animations = []
        animation_ranges = []
        ordered_animations = sorted(animation_targets)
        for position, target in enumerate(ordered_animations):
            end = ordered_animations[position + 1] \
                if position + 1 < len(ordered_animations) else animation_start
            raw = rom[target:end]
            if len(raw) != 8 or raw[-4:] != bytes.fromhex("ffff0000"):
                raise ValueError("OBJ closure internal pointer/size changed")
            animations.append({
                "target": target, "range": [target, end],
                "terminator_hex": raw[-4:].hex(),
                "bytes_sha256": _digest(raw),
            })
            animation_ranges.append((target, end))

        all_parts = definition_ranges + [(definition_start, definition_end)] \
            + animation_ranges + [(animation_start, animation_end)]
        closure = tuple(spec["closure_range"])
        if _coalesce(all_parts) != [closure]:
            raise ValueError("OBJ closure partition changed")
        output.append({
            "index": packet_index, "range": list(closure),
            "definition_pointer_table": {
                "range": [definition_start, definition_end],
                "targets": definition_targets,
                "bytes_sha256": _digest(rom[definition_start:definition_end]),
            },
            "definitions": definitions,
            "animation_pointer_table": {
                "range": [animation_start, animation_end],
                "targets": animation_targets,
                "bytes_sha256": _digest(rom[animation_start:animation_end]),
            },
            "animations": animations,
            "bytes_sha256": _digest(rom[slice(*closure)]),
        })
    ranges = [tuple(row["range"]) for row in output]
    actual = (ranges, sum(end - start for start, end in ranges),
              _vector_digest([list(row) for row in ranges]),
              _digest(_packed_bytes(rom, ranges)))
    expected = (list(C.OBJ_RANGES), C.OBJ_BYTES, C.OBJ_RANGE_VECTOR_SHA256,
                C.OBJ_PACKED_SHA256)
    if actual != expected:
        raise ValueError("OBJ closure partition changed")
    return output


def _residual_partition(
        rom: bytes, promoted: list[tuple[int, int]]) -> tuple[list[tuple[int, int]],
                                                               list[tuple[int, int]]]:
    cursor = C.ENVELOPE[0]
    residual = []
    for start, end in promoted:
        if start < cursor:
            raise ValueError("promotion overlap changed")
        if cursor < start:
            residual.append((cursor, start))
        cursor = end
    if cursor < C.ENVELOPE[1]:
        residual.append((cursor, C.ENVELOPE[1]))
    small = [row for row in residual if row[1] - row[0] <= 3]
    large = [row for row in residual if row[1] - row[0] > 3]
    expected = (
        (small, C.ALIGNMENT_GAP_RANGE_COUNT, C.ALIGNMENT_GAP_BYTES,
         C.ALIGNMENT_GAP_RANGE_VECTOR_SHA256, C.ALIGNMENT_GAP_PACKED_SHA256,
         "alignment gap partition changed"),
        (large, C.UNKNOWN_HOLE_RANGE_COUNT, C.UNKNOWN_HOLE_BYTES,
         C.UNKNOWN_HOLE_RANGE_VECTOR_SHA256, C.UNKNOWN_HOLE_PACKED_SHA256,
         "unknown hole partition changed"),
    )
    for ranges, count, size, vector_hash, byte_hash, message in expected:
        actual = (len(ranges), sum(end - start for start, end in ranges),
                  _vector_digest([list(row) for row in ranges]),
                  _digest(_packed_bytes(rom, ranges)))
        if actual != (count, size, vector_hash, byte_hash):
            raise ValueError(message)
    if sum(end - start for start, end in promoted + small + large) \
            != C.ENVELOPE[1] - C.ENVELOPE[0]:
        raise ValueError("envelope partition changed")
    return small, large


def _rebuild_payload(root: Path) -> dict[str, Any]:
    rom = _input_file(root, C.ROM_PATH).read_bytes()
    if len(rom) != C.ROM_SIZE or _digest(rom) != C.ROM_SHA256:
        raise ValueError("base ROM identity changed")
    coverage_raw, segments = _coverage_segments(root)
    hits = _pointer_denominator(rom)
    consumers = _literal_consumers(rom, hits)
    binding, source_ranges = _consumer_evidence(rom, consumers, segments)
    obj = _obj_records(rom)
    obj_ranges = [tuple(row["range"]) for row in obj]
    promoted = sorted(obj_ranges + source_ranges)
    actual_promotion = (
        len(promoted), sum(end - start for start, end in promoted),
        _vector_digest([list(row) for row in promoted]),
        _digest(_packed_bytes(rom, promoted)),
    )
    if actual_promotion != (
            C.PROMOTION_CLAIM_COUNT, C.PROMOTION_BYTES,
            C.PROMOTION_RANGE_VECTOR_SHA256, C.PROMOTION_PACKED_SHA256):
        raise ValueError("promotion denominator changed")
    gaps, holes = _residual_partition(rom, promoted)
    obj_set = set(obj_ranges)
    claims = []
    object_ordinal = source_ordinal = 0
    for start, end in promoted:
        is_object = (start, end) in obj_set
        ordinal = object_ordinal if is_object else source_ordinal
        prefix = "scene-obj-closure" if is_object else "scene-parser-source"
        primary_class = "scene_obj_source_closure" if is_object \
            else "parser_bound_scene_source_record"
        claims.append({
            "id": f"{prefix}-{ordinal:02d}-{start:06x}",
            "kind": primary_class, "primary_class": primary_class,
            "range": [start, end], "bytes_sha256": _digest(rom[start:end]),
            "baseline_unknown_only": True,
        })
        if is_object:
            object_ordinal += 1
        else:
            source_ordinal += 1
    return {
        "schema": C.SCHEMA,
        "rom": {"path": C.ROM_PATH.as_posix(), "size": len(rom),
                "sha256": _digest(rom)},
        "coverage_baseline": {
            "path": C.COVERAGE_PATH.as_posix(),
            "sha256": _digest(coverage_raw), "summary": C.COVERAGE_SUMMARY,
            "envelope_current_unknown": list(C.ENVELOPE),
        },
        "pointer_denominator": {
            "scan_range": [0, len(rom)], "stride": 2,
            "target_envelope": list(C.ENVELOPE),
            "hit_count": len(hits),
            "unique_target_count": len({row[1] for row in hits}),
            "external_count": sum(not (C.ENVELOPE[0] <= row[0] < C.ENVELOPE[1])
                                  for row in hits),
            "self_count": sum(C.ENVELOPE[0] <= row[0] < C.ENVELOPE[1]
                              for row in hits),
            "hit_vector_sha256": _vector_digest(hits), "hits": hits,
            "rejected_accidental_words": [list(C.ACCIDENTAL_POINTER_WORD)],
        },
        "consumer_binding": binding,
        "obj_closures": obj,
        "source_closures": [{
            "range": [start, end], "terminator": rom[end - 1],
            "bytes_sha256": _digest(rom[start:end]),
        } for start, end in source_ranges],
        "promotion": {
            "claim_count": len(claims), "bytes": C.PROMOTION_BYTES,
            "obj_claim_count": len(obj_ranges), "obj_bytes": C.OBJ_BYTES,
            "source_claim_count": len(source_ranges), "source_bytes": C.SOURCE_BYTES,
            "range_vector_sha256": _vector_digest([list(row) for row in promoted]),
            "packed_bytes_sha256": _digest(_packed_bytes(rom, promoted)),
            "claims": claims,
        },
        "excluded_alignment_gaps": {
            "range_count": len(gaps), "bytes": C.ALIGNMENT_GAP_BYTES,
            "range_vector_sha256": _vector_digest([list(row) for row in gaps]),
            "packed_bytes_sha256": _digest(_packed_bytes(rom, gaps)),
            "ranges": [list(row) for row in gaps],
        },
        "preserved_unknown_holes": {
            "range_count": len(holes), "bytes": C.UNKNOWN_HOLE_BYTES,
            "range_vector_sha256": _vector_digest([list(row) for row in holes]),
            "packed_bytes_sha256": _digest(_packed_bytes(rom, holes)),
            "ranges": [list(row) for row in holes],
        },
        "limitations": list(C.LIMITATIONS),
    }


def _expected_manifest(root: Path, payload_raw: bytes) -> dict[str, Any]:
    implementation = {
        name: {"path": path.as_posix(),
               "sha256": _digest(_input_file(root, path).read_bytes())}
        for name, path in C.IMPLEMENTATION_PATHS.items()
    }
    return {
        "schema": C.PROMOTION_SCHEMA, "artifact_schema": C.SCHEMA,
        "artifact_status": "accepted",
        "canonical_destination": C.OFFICIAL_ARTIFACT.as_posix(),
        "artifact_portability": "content_verified_independent_of_copy_path",
        "files": {C.PAYLOAD_NAME: {
            "size": len(payload_raw), "sha256": _digest(payload_raw),
        }},
        "summary": {
            "promotion_bytes": C.PROMOTION_BYTES,
            "promotion_claim_count": C.PROMOTION_CLAIM_COUNT,
            "alignment_gap_bytes": C.ALIGNMENT_GAP_BYTES,
            "unknown_hole_bytes": C.UNKNOWN_HOLE_BYTES,
        },
        "producer": {"command": list(C.OFFICIAL_EXPORT_COMMAND),
                     "command_role": "canonical_reproduction_recipe"},
        "verifier": {"command": list(C.OFFICIAL_VERIFY_COMMAND),
                     "command_role": "canonical_reproduction_recipe",
                     "exit_code": 0},
        "implementation": implementation,
    }


def _artifact_directory(root: Path, artifact: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = (artifact if artifact.is_absolute() else root / artifact).absolute()
    try:
        relative = lexical.relative_to(root)
    except ValueError as error:
        raise ValueError("artifact escapes root") from error
    if ".." in relative.parts:
        raise ValueError("artifact path contains traversal")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact path contains symlink")
    resolved = lexical.resolve(strict=True)
    if resolved != lexical or not resolved.is_dir():
        raise ValueError("unsafe artifact directory")
    return resolved


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors = []
    try:
        root = root.resolve(strict=True)
        directory = _artifact_directory(root, artifact)
        if {entry.name for entry in directory.iterdir()} != {
                C.MANIFEST_NAME, C.PAYLOAD_NAME}:
            raise ValueError("extra or missing artifact file")
        manifest_raw = (directory / C.MANIFEST_NAME).read_bytes()
        payload_raw = (directory / C.PAYLOAD_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        payload = json.loads(payload_raw)
        if manifest_raw != _canonical_json(manifest) \
                or payload_raw != _canonical_json(payload):
            raise ValueError("artifact JSON is not canonical")
        expected_payload = _rebuild_payload(root)
        if payload != expected_payload:
            raise ValueError("payload does not match independent rebuild")
        if manifest != _expected_manifest(root, payload_raw):
            raise ValueError("manifest contract changed")
    except Exception as error:  # fail closed into a machine-readable report
        errors.append(str(error))
    return {
        "schema": C.VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "promotion_bytes": C.PROMOTION_BYTES if not errors else None,
        "promotion_claim_count": C.PROMOTION_CLAIM_COUNT if not errors else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
