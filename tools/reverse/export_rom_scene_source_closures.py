#!/usr/bin/env python3
"""Export the frozen scene source closures packet."""

from __future__ import annotations

import argparse
import ctypes
import errno
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import rom_scene_source_closures_contract as C  # noqa: E402


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vsha(value: Any) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n"
    return _sha(raw.encode())


def _packed(rom: bytes, ranges: list[tuple[int, int]]) -> bytes:
    return b"".join(rom[start:end] for start, end in ranges)


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe input path: {relative}")
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _coverage(root: Path) -> tuple[bytes, list[dict[str, Any]]]:
    directory = (root / C.PRECOVERAGE_ARTIFACT).resolve(strict=True)
    if not directory.is_relative_to(root.resolve(strict=True)) \
            or not directory.is_dir() \
            or {path.name for path in directory.iterdir()} \
            != {C.MANIFEST_NAME, C.PRECOVERAGE_ARCHIVE_NAME}:
        raise ValueError("immutable precoverage artifact changed")
    manifest_raw = _safe_file(
        root, C.PRECOVERAGE_ARTIFACT / C.MANIFEST_NAME).read_bytes()
    archive_raw = _safe_file(
        root, C.PRECOVERAGE_ARTIFACT / C.PRECOVERAGE_ARCHIVE_NAME).read_bytes()
    if len(manifest_raw) != C.PRECOVERAGE_MANIFEST_SIZE \
            or _sha(manifest_raw) != C.PRECOVERAGE_MANIFEST_SHA256 \
            or len(archive_raw) != C.PRECOVERAGE_ARCHIVE_SIZE \
            or _sha(archive_raw) != C.PRECOVERAGE_ARCHIVE_SHA256:
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
    if len(raw) != C.PRECOVERAGE_RAW_SIZE or _sha(raw) != C.COVERAGE_SHA256:
        raise ValueError("immutable precoverage payload changed")
    data = json.loads(raw)
    if {key: data["summary"][key] for key in C.COVERAGE_SUMMARY} != C.COVERAGE_SUMMARY:
        raise ValueError("coverage baseline summary changed")
    start, end = C.ENVELOPE
    rows = [row for row in data["segments"]
            if row["range"][0] < end and start < row["range"][1]]
    expected = [{
        "range": [start, end],
        "primary_class": "unknown",
        "primary_claim_ids": [],
        "secondary_claim_ids": [],
        "unknown_reason": "no accepted primary classification claim",
    }]
    if rows != expected:
        raise ValueError("coverage current-unknown gate changed")
    return raw, data["segments"]


def _owner(segments: list[dict[str, Any]], offset: int) -> dict[str, Any]:
    rows = [row for row in segments
            if row["range"][0] <= offset < row["range"][1]]
    if len(rows) != 1:
        raise ValueError("consumer coverage membership changed")
    return rows[0]


def _accepted_instruction_owner(primary_class: str, claim_ids: list[str]) -> bool:
    return bool(claim_ids) and primary_class != "unknown" \
        and ("code" in primary_class or "cfg" in primary_class)


def _scan_pointer_hits(rom: bytes) -> list[list[int]]:
    low, high = C.ENVELOPE
    if struct.unpack_from("<I", rom, C.ACCIDENTAL_POINTER_WORD[0])[0] \
            != C.ROM_BASE + C.ACCIDENTAL_POINTER_WORD[1]:
        raise ValueError("accidental word changed")
    if struct.unpack_from("<I", rom, C.GENUINE_POINTER_WORD[0])[0] \
            != C.ROM_BASE + C.GENUINE_POINTER_WORD[1]:
        raise ValueError("genuine pointer word changed")
    if struct.unpack_from("<I", rom, C.SELF_POINTER_WORD[0])[0] \
            != C.ROM_BASE + C.SELF_POINTER_WORD[1]:
        raise ValueError("self pointer changed")
    if struct.unpack_from("<H", rom, C.LDR_ANCHOR[0])[0] != C.LDR_ANCHOR[1]:
        raise ValueError("LDR consumer opcode changed")
    hits = []
    for offset in range(0, len(rom) - 3, 2):
        target = struct.unpack_from("<I", rom, offset)[0] - C.ROM_BASE
        if low <= target < high:
            hits.append([offset, target])
    external = sum(not (low <= offset < high) for offset, _ in hits)
    self_hits = len(hits) - external
    if (len(hits), len({target for _, target in hits}), external, self_hits) != (
            C.POINTER_HIT_COUNT, C.POINTER_TARGET_COUNT,
            C.POINTER_EXTERNAL_COUNT, C.POINTER_SELF_COUNT):
        raise ValueError("pointer denominator changed")
    if _vsha(hits) != C.POINTER_HIT_VECTOR_SHA256:
        raise ValueError("pointer hit vector changed")
    if list(C.ACCIDENTAL_POINTER_WORD) not in hits:
        raise ValueError("accidental word changed")
    return hits


def _decode_consumers(hits: list[list[int]], rom: bytes) -> list[list[int]]:
    consumers = []
    for literal, target in hits:
        for instruction in range(max(0, literal - 1024), literal, 2):
            halfword = struct.unpack_from("<H", rom, instruction)[0]
            if halfword & 0xF800 == 0x4800 \
                    and ((instruction + 4) & ~3) + (halfword & 0xFF) * 4 == literal:
                consumers.append([instruction, literal, target])
    if (len({literal for _, literal, _ in consumers}), len(consumers),
            len({target for _, _, target in consumers})) != (
            C.LITERAL_COUNT, C.CONSUMER_COUNT, C.CONSUMER_ROOT_COUNT):
        raise ValueError("LDR consumer opcode/denominator changed")
    if _vsha(consumers) != C.CONSUMER_VECTOR_SHA256:
        raise ValueError("LDR consumer opcode changed")
    if any(literal == C.ACCIDENTAL_POINTER_WORD[0]
           for _, literal, _ in consumers):
        raise ValueError("accidental word became a consumer")
    return consumers


def _bind_consumers(
        rom: bytes, consumers: list[list[int]],
        segments: list[dict[str, Any]]) -> tuple[dict[str, Any], list[tuple[int, int]]]:
    memberships = []
    by_target: dict[int, list[list[Any]]] = {}
    owner_ids: set[str] = set()
    for instruction, literal, target in consumers:
        row = _owner(segments, instruction)
        membership = [instruction, literal, target, row["primary_class"],
                      row["primary_claim_ids"]]
        memberships.append(membership)
        by_target.setdefault(target, []).append(membership)
        owner_ids.update(row["primary_claim_ids"])
    if _vsha(memberships) != C.MEMBERSHIP_VECTOR_SHA256:
        raise ValueError("consumer coverage membership changed")
    classified = sum(row[3] != "unknown" for row in memberships)
    if (classified, len(memberships) - classified) != (
            C.CLASSIFIED_CONSUMER_COUNT, C.CURRENT_UNKNOWN_CONSUMER_COUNT):
        raise ValueError("consumer coverage denominator changed")

    table_bindings = []
    for target in C.OBJ_TABLE_ROOTS:
        rows = by_target.get(target, [])
        if not rows or not all(_accepted_instruction_owner(row[3], row[4])
                               for row in rows):
            raise ValueError("OBJ table consumer owner changed")
        table_bindings.append({
            "table_root": target,
            "consumer_count": len(rows),
            "consumers": rows,
        })

    rejected = []
    source_ranges = []
    for target, rows in sorted(by_target.items()):
        if target in C.OBJ_TABLE_ROOTS:
            continue
        if not any(_accepted_instruction_owner(row[3], row[4]) for row in rows):
            rejected.append(target)
            continue
        try:
            end = rom.index(0, target, C.ENVELOPE[1]) + 1
        except ValueError as error:
            raise ValueError("source endpoint/terminator changed") from error
        source_ranges.append((target, end))
    if tuple(rejected) != C.REJECTED_UNOWNED_SOURCE_ROOTS:
        raise ValueError("unowned source root denominator changed")
    if len(source_ranges) != C.SOURCE_CLAIM_COUNT \
            or sum(end - start for start, end in source_ranges) != C.SOURCE_BYTES \
            or _vsha([list(row) for row in source_ranges]) != C.SOURCE_RANGE_VECTOR_SHA256 \
            or _sha(_packed(rom, source_ranges)) != C.SOURCE_PACKED_SHA256:
        raise ValueError("source endpoint/terminator changed")
    binding = {
        "literal_count": C.LITERAL_COUNT,
        "consumer_count": C.CONSUMER_COUNT,
        "root_count": C.CONSUMER_ROOT_COUNT,
        "classified_consumer_count": classified,
        "current_unknown_consumer_count": len(memberships) - classified,
        "consumer_vector_sha256": _vsha(consumers),
        "membership_vector_sha256": _vsha(memberships),
        "coverage_owner_claim_ids": sorted(owner_ids),
        "coverage_memberships": memberships,
        "bindings": consumers,
        "obj_table_bindings": table_bindings,
        "rejected_unowned_source_roots": [
            [target, "no_accepted_instruction_consumer"] for target in rejected
        ],
    }
    return binding, source_ranges


def _merge_exact(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            raise ValueError("invalid closure range")
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [tuple(row) for row in merged]


def _parse_obj_closures(rom: bytes) -> list[dict[str, Any]]:
    closures = []
    for index, spec in enumerate(C.OBJ_SPECS):
        def_start, def_end = spec["definition_table_range"]
        anim_start, anim_end = spec["animation_table_range"]
        definition_targets = [struct.unpack_from("<I", rom, offset)[0] - C.ROM_BASE
                              for offset in range(def_start, def_end, 4)]
        animation_targets = [struct.unpack_from("<I", rom, offset)[0] - C.ROM_BASE
                             for offset in range(anim_start, anim_end, 4)]
        if definition_targets != spec["definition_targets"]:
            raise ValueError("OBJ closure internal pointer/size changed")
        if animation_targets != spec["animation_targets"]:
            raise ValueError("OBJ closure internal pointer/size changed")

        expected_counts = dict(zip(spec["definition_targets"],
                                   spec["definition_component_counts"], strict=True))
        physical_definitions = sorted(definition_targets)
        definitions = []
        component_ranges = []
        for position, target in enumerate(physical_definitions):
            end = physical_definitions[position + 1] \
                if position + 1 < len(physical_definitions) else def_start
            raw = rom[target:end]
            count = expected_counts[target]
            if len(raw) != count * 20 + 4 or raw[-4:] != bytes.fromhex("ffff0000"):
                raise ValueError("OBJ closure internal pointer/size changed")
            components = []
            for component_index in range(count):
                start = target + component_index * 20
                record = rom[start:start + 20]
                width, height = struct.unpack_from("<HH", record, 8)
                if width not in (8, 16, 32, 64) or height not in (8, 16, 32, 64) \
                        or record[18:20] != b"\0\0":
                    raise ValueError("OBJ closure component record changed")
                components.append({
                    "index": component_index,
                    "range": [start, start + 20],
                    "width": width,
                    "height": height,
                    "bytes_sha256": _sha(record),
                })
            definitions.append({
                "target": target,
                "range": [target, end],
                "component_count": count,
                "components": components,
                "terminator_hex": raw[-4:].hex(),
                "bytes_sha256": _sha(raw),
            })
            component_ranges.append((target, end))

        physical_animations = sorted(animation_targets)
        animations = []
        animation_ranges = []
        for position, target in enumerate(physical_animations):
            end = physical_animations[position + 1] \
                if position + 1 < len(physical_animations) else anim_start
            raw = rom[target:end]
            if len(raw) != 8 or raw[-4:] != bytes.fromhex("ffff0000"):
                raise ValueError("OBJ closure internal pointer/size changed")
            animations.append({
                "target": target,
                "range": [target, end],
                "terminator_hex": raw[-4:].hex(),
                "bytes_sha256": _sha(raw),
            })
            animation_ranges.append((target, end))

        parts = component_ranges + [(def_start, def_end)] \
            + animation_ranges + [(anim_start, anim_end)]
        closure_range = tuple(spec["closure_range"])
        if _merge_exact(parts) != [closure_range]:
            raise ValueError("OBJ closure partition changed")
        closures.append({
            "index": index,
            "range": list(closure_range),
            "definition_pointer_table": {
                "range": [def_start, def_end],
                "targets": definition_targets,
                "bytes_sha256": _sha(rom[def_start:def_end]),
            },
            "definitions": definitions,
            "animation_pointer_table": {
                "range": [anim_start, anim_end],
                "targets": animation_targets,
                "bytes_sha256": _sha(rom[anim_start:anim_end]),
            },
            "animations": animations,
            "bytes_sha256": _sha(rom[slice(*closure_range)]),
        })
    ranges = [tuple(row["range"]) for row in closures]
    if ranges != list(C.OBJ_RANGES) \
            or sum(end - start for start, end in ranges) != C.OBJ_BYTES \
            or _vsha([list(row) for row in ranges]) != C.OBJ_RANGE_VECTOR_SHA256 \
            or _sha(_packed(rom, ranges)) != C.OBJ_PACKED_SHA256:
        raise ValueError("OBJ closure partition changed")
    return closures


def _partition(
        rom: bytes, claims: list[tuple[int, int]]) -> tuple[list[tuple[int, int]],
                                                            list[tuple[int, int]]]:
    low, high = C.ENVELOPE
    cursor = low
    residual = []
    for start, end in sorted(claims):
        if start < cursor:
            raise ValueError("promotion overlap changed")
        if cursor < start:
            residual.append((cursor, start))
        cursor = end
    if cursor < high:
        residual.append((cursor, high))
    gaps = [row for row in residual if row[1] - row[0] <= 3]
    holes = [row for row in residual if row[1] - row[0] > 3]
    checks = (
        (gaps, C.ALIGNMENT_GAP_RANGE_COUNT, C.ALIGNMENT_GAP_BYTES,
         C.ALIGNMENT_GAP_RANGE_VECTOR_SHA256, C.ALIGNMENT_GAP_PACKED_SHA256,
         "alignment gap partition changed"),
        (holes, C.UNKNOWN_HOLE_RANGE_COUNT, C.UNKNOWN_HOLE_BYTES,
         C.UNKNOWN_HOLE_RANGE_VECTOR_SHA256, C.UNKNOWN_HOLE_PACKED_SHA256,
         "unknown hole partition changed"),
    )
    for ranges, count, size, range_hash, packed_hash, label in checks:
        if len(ranges) != count or sum(end - start for start, end in ranges) != size \
                or _vsha([list(row) for row in ranges]) != range_hash \
                or _sha(_packed(rom, ranges)) != packed_hash:
            raise ValueError(label)
    if sum(end - start for start, end in claims + gaps + holes) != high - low:
        raise ValueError("envelope partition changed")
    return gaps, holes


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool) -> dict[str, Any]:
    if verify_identity and (len(rom) != C.ROM_SIZE or _sha(rom) != C.ROM_SHA256):
        raise ValueError("base ROM identity changed")
    if len(rom) != C.ROM_SIZE:
        raise ValueError("base ROM size changed")
    coverage_raw, segments = _coverage(root)
    hits = _scan_pointer_hits(rom)
    consumers = _decode_consumers(hits, rom)
    consumer_binding, source_ranges = _bind_consumers(rom, consumers, segments)
    obj_closures = _parse_obj_closures(rom)
    obj_ranges = [tuple(row["range"]) for row in obj_closures]
    promotion_ranges = sorted(obj_ranges + source_ranges)
    if len(promotion_ranges) != C.PROMOTION_CLAIM_COUNT \
            or sum(end - start for start, end in promotion_ranges) != C.PROMOTION_BYTES \
            or _vsha([list(row) for row in promotion_ranges]) != C.PROMOTION_RANGE_VECTOR_SHA256 \
            or _sha(_packed(rom, promotion_ranges)) != C.PROMOTION_PACKED_SHA256:
        raise ValueError("promotion denominator changed")
    gaps, holes = _partition(rom, promotion_ranges)
    obj_set = set(obj_ranges)
    claims = []
    obj_index = source_index = 0
    for start, end in promotion_ranges:
        is_obj = (start, end) in obj_set
        ordinal = obj_index if is_obj else source_index
        prefix = "scene-obj-closure" if is_obj else "scene-parser-source"
        claims.append({
            "id": f"{prefix}-{ordinal:02d}-{start:06x}",
            "kind": "scene_obj_source_closure" if is_obj
                    else "parser_bound_scene_source_record",
            "primary_class": "scene_obj_source_closure" if is_obj
                             else "parser_bound_scene_source_record",
            "range": [start, end],
            "bytes_sha256": _sha(rom[start:end]),
            "baseline_unknown_only": True,
        })
        if is_obj:
            obj_index += 1
        else:
            source_index += 1
    return {
        "schema": C.SCHEMA,
        "rom": {"path": C.ROM_PATH.as_posix(), "size": len(rom),
                "sha256": _sha(rom)},
        "coverage_baseline": {
            "path": C.COVERAGE_PATH.as_posix(),
            "sha256": _sha(coverage_raw),
            "summary": C.COVERAGE_SUMMARY,
            "envelope_current_unknown": list(C.ENVELOPE),
        },
        "pointer_denominator": {
            "scan_range": [0, len(rom)], "stride": 2,
            "target_envelope": list(C.ENVELOPE),
            "hit_count": len(hits),
            "unique_target_count": len({target for _, target in hits}),
            "external_count": sum(not (C.ENVELOPE[0] <= offset < C.ENVELOPE[1])
                                  for offset, _ in hits),
            "self_count": sum(C.ENVELOPE[0] <= offset < C.ENVELOPE[1]
                              for offset, _ in hits),
            "hit_vector_sha256": _vsha(hits),
            "hits": hits,
            "rejected_accidental_words": [list(C.ACCIDENTAL_POINTER_WORD)],
        },
        "consumer_binding": consumer_binding,
        "obj_closures": obj_closures,
        "source_closures": [{
            "range": [start, end],
            "terminator": rom[end - 1],
            "bytes_sha256": _sha(rom[start:end]),
        } for start, end in source_ranges],
        "promotion": {
            "claim_count": len(claims), "bytes": C.PROMOTION_BYTES,
            "obj_claim_count": len(obj_ranges), "obj_bytes": C.OBJ_BYTES,
            "source_claim_count": len(source_ranges), "source_bytes": C.SOURCE_BYTES,
            "range_vector_sha256": _vsha([list(row) for row in promotion_ranges]),
            "packed_bytes_sha256": _sha(_packed(rom, promotion_ranges)),
            "claims": claims,
        },
        "excluded_alignment_gaps": {
            "range_count": len(gaps), "bytes": C.ALIGNMENT_GAP_BYTES,
            "range_vector_sha256": _vsha([list(row) for row in gaps]),
            "packed_bytes_sha256": _sha(_packed(rom, gaps)),
            "ranges": [list(row) for row in gaps],
        },
        "preserved_unknown_holes": {
            "range_count": len(holes), "bytes": C.UNKNOWN_HOLE_BYTES,
            "range_vector_sha256": _vsha([list(row) for row in holes]),
            "packed_bytes_sha256": _sha(_packed(rom, holes)),
            "ranges": [list(row) for row in holes],
        },
        "limitations": list(C.LIMITATIONS),
    }


def build_payload(root: Path, rom: bytes | None = None,
                  *, verify_identity: bool = True) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, C.ROM_PATH).read_bytes()
    return _build_from_rom(root, rom, verify_identity=verify_identity)


def _publish_exclusive(source: Path, destination: Path) -> None:
    source, destination = source.absolute(), destination.absolute()
    if source.parent != destination.parent:
        raise ValueError("exclusive publication requires a shared parent")
    parent_fd = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if sys.platform == "darwin":
            rename, flag = libc.renameatx_np, 0x00000004
        elif hasattr(libc, "renameat2"):
            rename, flag = libc.renameat2, 0x00000001
        else:
            raise OSError(errno.ENOTSUP, "atomic no-replace rename unavailable")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(parent_fd, os.fsencode(source.name), parent_fd,
                  os.fsencode(destination.name), flag):
            code = ctypes.get_errno()
            if code == errno.EEXIST:
                raise FileExistsError(destination)
            raise OSError(code, os.strerror(code), destination)
    finally:
        os.close(parent_fd)


def _authorized(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    lexical = (output if output.is_absolute() else root / output).absolute()
    try:
        relative = lexical.relative_to(root)
    except ValueError as error:
        raise ValueError("unauthorized output or symlink") from error
    if ".." in relative.parts:
        raise ValueError("unauthorized output or symlink")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("unauthorized output or symlink")
    resolved = lexical.resolve(strict=False)
    if resolved != lexical:
        raise ValueError("unauthorized output or symlink")
    official = (root / C.OFFICIAL_ARTIFACT).resolve(strict=False)
    experiment = (root / C.EXPERIMENT_ROOT).resolve(strict=True)
    if resolved != official and not resolved.is_relative_to(experiment):
        raise ValueError("unauthorized output or symlink")
    return resolved


def _manifest(root: Path, payload_raw: bytes) -> dict[str, Any]:
    implementation = {
        name: {"path": path.as_posix(),
               "sha256": _sha(_safe_file(root, path).read_bytes())}
        for name, path in C.IMPLEMENTATION_PATHS.items()
    }
    return {
        "schema": C.PROMOTION_SCHEMA,
        "artifact_schema": C.SCHEMA,
        "artifact_status": "accepted",
        "canonical_destination": C.OFFICIAL_ARTIFACT.as_posix(),
        "artifact_portability": "content_verified_independent_of_copy_path",
        "files": {C.PAYLOAD_NAME: {
            "size": len(payload_raw), "sha256": _sha(payload_raw),
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


def export_artifact(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    output = _authorized(root, output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    payload_raw = _canonical(build_payload(root))
    manifest = _manifest(root, payload_raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,
                                     prefix=".scene-source-closures-") as raw:
        stage = Path(raw)
        (stage / C.PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / C.MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_scene_source_closures import verify_artifact
        report = verify_artifact(root, stage)
        if not report["verified"]:
            raise ValueError(report["errors"])
        _publish_exclusive(stage, output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export_artifact(args.root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
