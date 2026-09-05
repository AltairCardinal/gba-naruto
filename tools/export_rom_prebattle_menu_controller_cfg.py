#!/usr/bin/env python3
"""Export the frozen pre-battle menu controller Thumb CFG candidate."""

from __future__ import annotations

import argparse
import ctypes
import errno
import gzip
import hashlib
import heapq
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _root in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from tools import rom_prebattle_menu_controller_cfg_contract as C  # noqa: E402
from tools.export_rom_cfg_inventory import _build_blocks, _decode_one, _key  # noqa: E402

PAYLOAD_NAME = C.PAYLOAD_NAME
MANIFEST_NAME = C.MANIFEST_NAME


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _vsha(value: Any) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n"
    return _sha(raw.encode())


def _packed(rom: bytes, ranges: Any) -> bytes:
    return b"".join(rom[start:end] for start, end in ranges)


def _inside(offset: int, ranges: Any) -> bool:
    return any(start <= offset < end for start, end in ranges)


def _merge_ranges(ranges: Any) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            raise ValueError("invalid promotion component range")
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _safe_file(root: Path, relative: Path) -> Path:
    base = root.resolve(strict=True)
    cursor = base
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"unsafe input path: {relative}")
    result = cursor.resolve(strict=True)
    if not result.is_relative_to(base) or not result.is_file():
        raise ValueError(f"unsafe input path: {relative}")
    return result


def _coverage(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
    summary = {key: data["summary"][key] for key in C.COVERAGE_SUMMARY}
    if summary != C.COVERAGE_SUMMARY:
        raise ValueError("coverage baseline summary changed")
    segments = data["segments"]

    def covering(start: int, end: int) -> list[dict[str, Any]]:
        rows = [row for row in segments
                if row["range"][0] < end and start < row["range"][1]]
        cursor = start
        for row in rows:
            if row["range"][0] > cursor:
                raise ValueError("coverage baseline has a gap")
            cursor = max(cursor, min(end, row["range"][1]))
        if cursor != end:
            raise ValueError("coverage baseline has a gap")
        return rows

    for start, end in (*C.CURRENT_UNKNOWN_CODE_RANGES,
                       *C.CURRENT_UNKNOWN_LITERAL_RANGES, C.TABLE_RANGE):
        if any(row["primary_class"] != "unknown" for row in covering(start, end)):
            raise ValueError("coverage current-unknown gate changed")
    for owner in C.DEPENDENCY_CODE_OWNERS:
        start, end = owner["range"]
        rows = covering(start, end)
        if any(row["primary_class"] != owner["primary_class"]
               or owner["claim_id"] not in row["primary_claim_ids"] for row in rows):
            raise ValueError("coverage dependency owner changed")
    return data, segments


def _direct_target(rom: bytes, offset: int) -> tuple[int, str, int] | None:
    first = struct.unpack_from("<H", rom, offset)[0]
    if first & 0xF800 == 0xF000 and offset + 4 <= len(rom):
        second = struct.unpack_from("<H", rom, offset + 2)[0]
        if second & 0xF800 == 0xF800:
            delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
            if delta & (1 << 22):
                delta -= 1 << 23
            return offset + 4 + delta, "bl", 4
    if first & 0xF800 == 0xE000:
        delta = (first & 0x7FF) << 1
        if delta & 0x800:
            delta -= 0x1000
        return offset + 4 + delta, "b", 2
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition < 14:
        delta = (first & 0xFF) << 1
        if delta & 0x100:
            delta -= 0x200
        return offset + 4 + delta, "bcond", 2
    return None


def _producer(root: Path, rom: bytes, segments: list[dict[str, Any]]) -> dict[str, Any]:
    upstream = (
        (C.UPSTREAM_ARTIFACT / C.MANIFEST_NAME, C.UPSTREAM_MANIFEST_SHA256,
         C.UPSTREAM_MANIFEST_SIZE),
        (C.UPSTREAM_ARTIFACT / C.UPSTREAM_PAYLOAD_NAME, C.UPSTREAM_PAYLOAD_SHA256,
         C.UPSTREAM_PAYLOAD_SIZE),
        (C.UPSTREAM_VERIFIER, C.UPSTREAM_VERIFIER_SHA256, None),
    )
    identities = {}
    evidence_raw: dict[Path, bytes] = {}
    for path, digest, size in upstream:
        try:
            raw = _safe_file(root, path).read_bytes()
        except (FileNotFoundError, ValueError) as error:
            raise ValueError("coverage-bound upstream producer evidence missing") from error
        if _sha(raw) != digest or (size is not None and len(raw) != size):
            raise ValueError("upstream producer owner identity changed")
        evidence_raw[path] = raw
        identities[path.as_posix()] = {"sha256": digest, "size": len(raw)}
    try:
        manifest = json.loads(evidence_raw[C.UPSTREAM_ARTIFACT / C.MANIFEST_NAME])
        payload = json.loads(evidence_raw[C.UPSTREAM_ARTIFACT / C.UPSTREAM_PAYLOAD_NAME])
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError("upstream producer evidence is not valid JSON") from error
    if evidence_raw[C.UPSTREAM_ARTIFACT / C.MANIFEST_NAME] != _canonical(manifest) \
            or evidence_raw[C.UPSTREAM_ARTIFACT / C.UPSTREAM_PAYLOAD_NAME] \
            != _canonical(payload):
        raise ValueError("upstream producer evidence is not canonical JSON")
    if manifest.get("schema") != C.PROMOTION_SCHEMA \
            or manifest.get("artifact_schema") != C.UPSTREAM_SCHEMA \
            or manifest.get("artifact_status") != "accepted" \
            or manifest.get("files") != {C.UPSTREAM_PAYLOAD_NAME: {
                "sha256": C.UPSTREAM_PAYLOAD_SHA256,
                "size": C.UPSTREAM_PAYLOAD_SIZE,
            }}:
        raise ValueError("upstream producer manifest contract changed")
    claims = [
        claim for claim in payload.get("promotion", {}).get("claims", [])
        if claim.get("id") == C.PRODUCER_OWNER_CLAIM_ID
    ]
    if payload.get("schema") != C.UPSTREAM_SCHEMA \
            or payload.get("promotion", {}).get("primary_class") \
            != C.UPSTREAM_PRIMARY_CLASS \
            or payload.get("promotion", {}).get("promotion_bytes") \
            != C.UPSTREAM_PROMOTION_BYTES \
            or claims != [{
                "baseline_unknown_only": True,
                "bytes_sha256": C.UPSTREAM_CODE_CLAIM_BYTES_SHA256,
                "id": C.PRODUCER_OWNER_CLAIM_ID,
                "kind": "reachable_thumb_code",
                "range": list(C.PRODUCER_OWNER_RANGE),
            }]:
        raise ValueError("upstream producer payload claim changed")
    if _sha(rom[C.PRODUCER_OWNER_RANGE[0]:C.PRODUCER_OWNER_RANGE[1]]) \
            != C.PRODUCER_OWNER_BYTES_SHA256:
        raise ValueError("producer owner bytes changed")
    owner_rows = [
        row for row in segments
        if row["range"][0] < C.PRODUCER_OWNER_RANGE[1]
        and C.PRODUCER_OWNER_RANGE[0] < row["range"][1]
    ]
    if owner_rows != [{
        "range": list(C.PRODUCER_OWNER_RANGE),
        "primary_class": C.PRODUCER_OWNER_PRIMARY_CLASS,
        "primary_claim_ids": [C.PRODUCER_OWNER_CLAIM_ID],
        "secondary_claim_ids": [],
    }]:
        raise ValueError("producer owner coverage claim changed")
    if rom[C.PRODUCER[0]:C.PRODUCER[0] + C.PRODUCER[3]].hex() != C.PRODUCER[4] \
            or _sha(rom[C.PRODUCER[0]:C.PRODUCER[0] + C.PRODUCER[3]]) \
            != C.PRODUCER_RAW_SHA256:
        raise ValueError("producer instruction changed")
    matches = []
    for offset in range(0, len(rom) - 1, 2):
        decoded = _direct_target(rom, offset)
        if decoded and decoded[0] == C.ROOT:
            target, kind, size = decoded
            matches.append([offset, target, kind, size, rom[offset:offset + size].hex()])
    if matches != [list(C.PRODUCER)]:
        raise ValueError("producer denominator changed")
    denominator_sha256 = _vsha(C.PRODUCER_SCAN_DENOMINATOR)
    match_vector_sha256 = _vsha(matches)
    if denominator_sha256 != C.PRODUCER_SCAN_DENOMINATOR_SHA256 \
            or match_vector_sha256 != C.PRODUCER_MATCH_VECTOR_SHA256:
        raise ValueError("producer denominator hash changed")
    return {
        "scan": C.PRODUCER_SCAN_DENOMINATOR,
        "denominator_sha256": denominator_sha256,
        "matches": matches,
        "match_vector_sha256": match_vector_sha256,
        "owner_claim_id": C.PRODUCER_OWNER_CLAIM_ID,
        "owner_range": list(C.PRODUCER_OWNER_RANGE),
        "owner_primary_class": C.PRODUCER_OWNER_PRIMARY_CLASS,
        "upstream_identities": identities,
    }


def _verify_upstream_artifact(root: Path) -> None:
    from tools.verify_rom_story_state_callback_cfg import verify_artifact

    report = verify_artifact(
        root, root / C.UPSTREAM_ARTIFACT,
        expected_receipt_path=C.UPSTREAM_ARTIFACT,
    )
    if not report.get("verified") \
            or report.get("promotion_bytes") != C.UPSTREAM_PROMOTION_BYTES:
        raise ValueError("producer upstream independent verification failed")


def _selector(rom: bytes) -> dict[str, Any]:
    if rom[slice(*C.SELECTOR_RANGE)].hex() != C.SELECTOR_RAW_HEX \
            or _sha(rom[slice(*C.SELECTOR_RANGE)]) != C.SELECTOR_SHA256:
        raise ValueError("selector binding changed")
    if rom[C.PC_LITERAL_SITE:C.PC_LITERAL_SITE + 4].hex() != C.PC_LITERAL_RAW_HEX:
        raise ValueError("table PC literal changed")
    raw = rom[slice(*C.TABLE_RANGE)]
    targets = [struct.unpack_from("<I", raw, index)[0] - C.ROM_BASE
               for index in range(0, len(raw), 4)]
    if raw.hex() != C.TABLE_RAW_HEX or _sha(raw) != C.TABLE_SHA256 \
            or targets != list(C.TABLE_TARGETS):
        raise ValueError("table binding changed")
    return {
        "range": list(C.SELECTOR_RANGE), "load_site": C.SELECTOR_LOAD_SITE,
        "bound_site": C.SELECTOR_BOUND_SITE, "max_selector": C.SELECTOR_MAX,
        "branch_site": C.SELECTOR_BRANCH_SITE,
        "fallback_target": C.SELECTOR_FALLBACK_TARGET,
        "index_shift": C.SELECTOR_INDEX_SHIFT,
        "indirect_site": C.INDIRECT_SELECTOR_SITE,
        "pc_literal_site": C.PC_LITERAL_SITE,
        "table_base_value": C.TABLE_BASE_VALUE,
        "table_range": list(C.TABLE_RANGE), "table_targets": targets,
        "table_sha256": _sha(raw),
    }


def _closure(rom: bytes, segments: list[dict[str, Any]]) -> dict[str, Any]:
    if _sha(rom[C.ROOT:C.ROOT + 4]) != C.ROOT_ENTRY_SHA256:
        raise ValueError("root entry changed")
    if _vsha([list(row) for row in C.CURRENT_UNKNOWN_CODE_RANGES]) \
            != C.CURRENT_UNKNOWN_CODE_RANGE_SHA256:
        raise ValueError("code range denominator changed")
    if _vsha([list(row) for row in C.DEPENDENCY_CODE_RANGES]) \
            != C.DEPENDENCY_CODE_RANGE_SHA256:
        raise ValueError("dependency range denominator changed")
    if _vsha([list(row) for row in C.CURRENT_UNKNOWN_LITERAL_RANGES]) \
            != C.LITERAL_RANGE_SHA256:
        raise ValueError("literal range denominator changed")
    if _sha(_packed(rom, C.DEPENDENCY_CODE_RANGES)) != C.DEPENDENCY_CODE_PACKED_SHA256:
        raise ValueError("dependency bridge bytes changed")
    if _sha(_packed(rom, C.CURRENT_UNKNOWN_LITERAL_RANGES)) != C.LITERAL_PACKED_SHA256:
        raise ValueError("literal bytes changed")
    frontier_raw = ("0847", "0847", "0047", "0047", "0047", "0047", "0847")
    if tuple(rom[offset:offset + 2].hex() for offset in C.FRONTIER_OFFSETS) != frontier_raw:
        raise ValueError("frontier instruction changed")
    allowed = C.CURRENT_UNKNOWN_CODE_RANGES + C.DEPENDENCY_CODE_RANGES
    pending = [_key("thumb", root) for root in C.ROOTS]
    heapq.heapify(pending)
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    opaque: list[list[int]] = []
    opaque_evidence: list[list[Any]] = []
    try:
        while pending:
            offset, _, mode = heapq.heappop(pending)
            item = (mode, offset)
            if item in nodes:
                continue
            if mode != "thumb" or not _inside(offset, allowed):
                raise ValueError("worklist escaped")
            decoded = _decode_one(rom, offset, mode)
            if not decoded["accepted"]:
                raise ValueError("decoder rejected")
            nodes[item] = decoded
            successors = list(decoded["successors"])
            if offset == C.INDIRECT_SELECTOR_SITE:
                successors.extend({"kind": "jump_table_target", "mode": "thumb",
                                   "file_offset": target}
                                  for target in C.TABLE_TARGETS)
            for edge in successors:
                target = edge["file_offset"]
                if _inside(target, allowed):
                    heapq.heappush(pending, _key("thumb", target))
                elif edge["kind"] == "call_target":
                    owners = [row for row in segments
                              if row["range"][0] <= target < row["range"][1]]
                    primary_class = owners[0]["primary_class"] if len(owners) == 1 else ""
                    claim_ids = owners[0].get("primary_claim_ids", []) if len(owners) == 1 else []
                    if len(owners) != 1 or primary_class == "unknown" \
                            or not ("code" in primary_class or "cfg" in primary_class) \
                            or not claim_ids:
                        raise ValueError("current-unknown call target was not followed")
                    opaque.append([offset, target])
                    opaque_evidence.append(
                        [offset, target, "call_target", primary_class, claim_ids[0]]
                    )
                else:
                    raise ValueError("non-call edge escaped")
    except Exception as error:
        raise ValueError(f"decode traversal changed: {error}") from error
    frontiers = sorted([offset, row["frontiers"][0]["reason"]]
                       for (_, offset), row in nodes.items()
                       if row["frontiers"] and offset != C.INDIRECT_SELECTOR_SITE)
    if frontiers != [list(row) for row in C.FRONTIERS]:
        raise ValueError("frontier denominator changed")
    if _sha(_packed(rom, C.CURRENT_UNKNOWN_CODE_RANGES)) \
            != C.CURRENT_UNKNOWN_CODE_PACKED_SHA256:
        raise ValueError("decode code bytes changed")
    blocks, _ = _build_blocks(rom, nodes, {("thumb", root) for root in C.ROOTS})
    internal_edges = sum(
        1 for row in nodes.values() for edge in row["successors"]
        if (edge["mode"], edge["file_offset"]) in nodes
    ) + len(C.TABLE_TARGETS)
    block_edges = sum(len(block["successors"]) for block in blocks) + len(C.TABLE_TARGETS)
    unknown_count = sum(_inside(offset, C.CURRENT_UNKNOWN_CODE_RANGES)
                        for _, offset in nodes)
    dependency_count = len(nodes) - unknown_count
    if (len(nodes), sum(row["size"] for row in nodes.values()), len(blocks),
            internal_edges, block_edges, unknown_count, dependency_count,
            len(opaque), len({row[1] for row in opaque})) != (
            C.TRAVERSAL_INSTRUCTION_COUNT, C.TRAVERSAL_INSTRUCTION_BYTES,
            C.TRAVERSAL_BLOCK_COUNT, C.TRAVERSAL_INTERNAL_EDGE_COUNT,
            C.TRAVERSAL_BLOCK_EDGE_COUNT, 699, 87,
            C.OPAQUE_CALL_COUNT, C.OPAQUE_UNIQUE_TARGET_COUNT):
        raise ValueError("decode traversal denominator changed")
    opaque_call_vector_sha256 = _vsha(sorted(opaque_evidence))
    if opaque_call_vector_sha256 != C.OPAQUE_CALL_VECTOR_SHA256:
        raise ValueError("opaque call owner vector changed")
    literals = []
    for (_, offset), row in sorted(nodes.items()):
        if row["size"] == 2:
            halfword = struct.unpack_from("<H", rom, offset)[0]
            if halfword & 0xF800 == 0x4800:
                literals.append([offset, ((offset + 4) & ~3) + (halfword & 0xFF) * 4])
    unknown_literals = [row for row in literals
                        if _inside(row[1], C.CURRENT_UNKNOWN_LITERAL_RANGES)]
    if (len(literals), len({row[1] for row in literals}), len(unknown_literals),
            len({row[1] for row in unknown_literals})) != (87, 85, 84, 83):
        raise ValueError("literal denominator changed")
    return {
        "roots": list(C.ROOTS), "instruction_count": len(nodes),
        "instruction_bytes": sum(row["size"] for row in nodes.values()),
        "basic_block_count": len(blocks), "internal_edge_count": internal_edges,
        "block_edge_count": block_edges,
        "current_unknown_instruction_count": unknown_count,
        "current_unknown_code_bytes": C.CURRENT_UNKNOWN_CODE_BYTES,
        "dependency_instruction_count": dependency_count,
        "dependency_code_bytes": C.DEPENDENCY_CODE_BYTES,
        "dependency_code_ranges": [list(row) for row in C.DEPENDENCY_CODE_RANGES],
        "dependency_code_owners": list(C.DEPENDENCY_CODE_OWNERS),
        "frontiers": frontiers, "frontier_count": len(frontiers),
        "opaque_calls": sorted(opaque), "opaque_call_count": len(opaque),
        "opaque_unique_target_count": len({row[1] for row in opaque}),
        "opaque_call_vector_sha256": opaque_call_vector_sha256,
        "literal_bindings": literals,
    }


def _build_from_rom(root: Path, rom: bytes, *, verify_identity: bool = True) -> dict[str, Any]:
    if verify_identity and (len(rom) != C.ROM_SIZE or _sha(rom) != C.ROM_SHA256):
        raise ValueError("ROM identity changed")
    if len(rom) != C.ROM_SIZE:
        raise ValueError("ROM size changed")
    _, segments = _coverage(root)
    producer = _producer(root, rom, segments)
    selector = _selector(rom)
    closure = _closure(rom, segments)
    component_ranges = [
        *C.CURRENT_UNKNOWN_CODE_RANGES,
        *C.CURRENT_UNKNOWN_LITERAL_RANGES,
        C.TABLE_RANGE,
    ]
    derived_union = _merge_ranges(component_ranges)
    if derived_union != [list(row) for row in C.UNION_RANGES]:
        raise ValueError("promotion union is not derived from components")
    if sum(end - start for start, end in component_ranges) != C.PROMOTION_BYTES:
        raise ValueError("promotion component byte total changed")
    if sum(end - start for start, end in derived_union) != C.PROMOTION_BYTES:
        raise ValueError("promotion union byte total changed")
    promotion_range_sha256 = _vsha(derived_union)
    if promotion_range_sha256 != C.PROMOTION_RANGE_SHA256:
        raise ValueError("promotion range denominator changed")
    if _sha(_packed(rom, derived_union)) != C.PROMOTION_PACKED_SHA256:
        raise ValueError("promotion union bytes changed")
    return {
        "schema": C.SCHEMA,
        "rom": {"path": C.ROM_PATH.as_posix(), "size": len(rom), "sha256": C.ROM_SHA256},
        "coverage_baseline": {"path": C.COVERAGE_PATH.as_posix(),
                              "sha256": C.COVERAGE_SHA256,
                              "summary": C.COVERAGE_SUMMARY},
        "producer_denominator": producer,
        "selector_binding": selector,
        "target_local_denominator": closure,
        "promotion": {
            "code_ranges": [list(row) for row in C.CURRENT_UNKNOWN_CODE_RANGES],
            "code_bytes": C.CURRENT_UNKNOWN_CODE_BYTES,
            "code_range_sha256": C.CURRENT_UNKNOWN_CODE_RANGE_SHA256,
            "code_packed_sha256": C.CURRENT_UNKNOWN_CODE_PACKED_SHA256,
            "literal_ranges": [list(row) for row in C.CURRENT_UNKNOWN_LITERAL_RANGES],
            "literal_bytes": C.CURRENT_UNKNOWN_LITERAL_BYTES,
            "literal_reference_count": C.CURRENT_UNKNOWN_LITERAL_REFERENCE_COUNT,
            "unique_literal_word_count": C.CURRENT_UNKNOWN_LITERAL_WORD_COUNT,
            "literal_range_sha256": C.LITERAL_RANGE_SHA256,
            "literal_packed_sha256": C.LITERAL_PACKED_SHA256,
            "jump_table_range": list(C.TABLE_RANGE),
            "jump_table_bytes": C.JUMP_TABLE_BYTES,
            "jump_table_packed_sha256": C.JUMP_TABLE_PACKED_SHA256,
            "union_ranges": [list(row) for row in C.UNION_RANGES],
            "promotion_bytes": C.PROMOTION_BYTES,
            "promotion_range_sha256": promotion_range_sha256,
            "promotion_packed_sha256": C.PROMOTION_PACKED_SHA256,
        },
        "scope": C.SCOPE, "limitations": list(C.LIMITATIONS),
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


def _authorized_output(root: Path, output: Path) -> tuple[Path, bool]:
    root = root.resolve(strict=True)
    lexical = (output if output.is_absolute() else root / output).absolute()
    try:
        relative = lexical.relative_to(root)
    except ValueError as error:
        raise ValueError("output escapes root") from error
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("output has symlink ancestor")
    resolved = lexical.resolve(strict=False)
    if resolved != lexical:
        raise ValueError("output path contains traversal or alias components")
    official = (root / C.OFFICIAL_ARTIFACT).resolve(strict=False)
    experiment = (root / C.EXPERIMENT_ROOT).resolve(strict=True)
    is_official = resolved == official
    if not is_official and not resolved.is_relative_to(experiment):
        raise ValueError("output must be the official artifact or frozen experiment output")
    return resolved, is_official


def _manifest(root: Path, payload_raw: bytes) -> dict[str, Any]:
    implementation = {
        name: {
            "path": path.as_posix(),
            "sha256": _sha(_safe_file(root, path).read_bytes()),
        }
        for name, path in C.IMPLEMENTATION_PATHS.items()
    }
    official = C.OFFICIAL_ARTIFACT.as_posix()
    return {
        "schema": C.PROMOTION_SCHEMA,
        "artifact_schema": C.SCHEMA,
        "artifact_status": "accepted",
        "canonical_destination": official,
        "artifact_portability": "content_verified_independent_of_copy_path",
        "files": {C.PAYLOAD_NAME: {
            "size": len(payload_raw), "sha256": _sha(payload_raw),
        }},
        "summary": {
            "promotion_bytes": C.PROMOTION_BYTES,
            "instruction_count": C.TRAVERSAL_INSTRUCTION_COUNT,
            "frontier_count": C.TRAVERSAL_FRONTIER_COUNT,
        },
        "producer": {
            "command": ["python3", C.IMPLEMENTATION_PATHS["exporter"].as_posix(),
                        "--root", ".", "--output", official],
            "command_role": "canonical_reproduction_recipe",
        },
        "verifier": {
            "command": ["python3", C.IMPLEMENTATION_PATHS["verifier"].as_posix(),
                        "--root", ".", "--artifact", official],
            "command_role": "canonical_reproduction_recipe",
            "exit_code": 0,
        },
        "implementation": implementation,
    }


def export_artifact(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    output, _ = _authorized_output(root, output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    _verify_upstream_artifact(root)
    raw = _canonical(build_payload(root))
    manifest = _manifest(root, raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".prebattle-cfg-") as tmp:
        stage = Path(tmp)
        (stage / C.PAYLOAD_NAME).write_bytes(raw)
        (stage / C.MANIFEST_NAME).write_bytes(_canonical(manifest))
        from tools.verify_rom_prebattle_menu_controller_cfg import verify_artifact
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
