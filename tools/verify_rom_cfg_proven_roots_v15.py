#!/usr/bin/env python3
"""Independently verify the frozen raw-ROM CFG proven-roots v15 packet."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"


def _require_isolated_cli_runtime() -> None:
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("CFG v15 CLI requires Python -I -S isolation")
    if any(name == "capstone" or name.startswith("capstone.") for name in sys.modules):
        raise RuntimeError("CFG v15 CLI rejects preloaded Capstone modules")
    if any(os.environ.get(name) for name in ("PYTHONPATH", "PYTHONHOME", "LIBCAPSTONE_PATH")):
        raise RuntimeError("CFG v15 CLI rejects runtime path overrides")


_require_isolated_cli_runtime()
for _root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from tools import verify_rom_cfg_proven_roots_v13 as _base  # noqa: E402
from tools.rom_cfg_proven_roots_v15_contract import (  # noqa: E402
    EXCLUDED_SOURCE_SPEC,
    EXPERIMENT_OUTPUT_ROOT,
    MANIFEST_NAME,
    NONCLAIMS,
    OFFICIAL_ARTIFACT,
    ORACLE_IDENTITIES,
    PAYLOAD_NAME,
    PROMOTION_CODE_PACKED_SHA256,
    PROMOTION_LITERAL_PACKED_SHA256,
    PROMOTION_PACKED_SHA256,
    PROMOTION_SCHEMA,
    PROMOTION_SEMANTIC_RANGES,
    PROMOTION_SEMANTIC_RANGE_SHA256,
    PROMOTION_UNION_RANGES,
    PROMOTION_UNION_RANGE_SHA256,
    ROM_BASE,
    ROM_PATH,
    ROM_SHA256,
    ROM_SIZE,
    REJECTED_TARGET_SPEC,
    SCHEMA,
    SCOPE,
    TARGET_SPECS,
    UPSTREAM,
    VERIFY_SCHEMA,
    RUNTIME_DEPENDENCY_PATHS as CONTRACT_RUNTIME_DEPENDENCY_PATHS,
)


_canonical_sha = _base._canonical_sha
_packed = _base._packed
_producer_target = _base._producer_target
_sha = _base._sha


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _safe_file(root: Path, relative: str | Path) -> Path:
    root = Path(root).resolve(strict=True)
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValueError("v15 path is not repository-relative")
    candidate = root / relative_path
    if candidate.is_symlink():
        raise ValueError("v15 dependency uses a symlink")
    current = root
    for component in relative_path.parts[:-1]:
        current = current / component
        if current.is_symlink():
            raise ValueError("v15 dependency path uses a symlink")
    return candidate.resolve(strict=True)


def _runtime_dependency_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            {
                Path("tools/rom_cfg_proven_roots_v15_contract.py"),
                Path("tools/export_rom_cfg_proven_roots_v13.py"),
                Path("tools/verify_rom_cfg_proven_roots_v13.py"),
                *CONTRACT_RUNTIME_DEPENDENCY_PATHS,
            },
            key=lambda path: path.as_posix(),
        )
    )


RUNTIME_DEPENDENCY_PATHS = _runtime_dependency_paths()


EXPECTED_REPORT = {
    "schema": VERIFY_SCHEMA,
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "rom_sha256": ROM_SHA256,
    "target_root_count": 4,
    "target_roots": [0x09A3E0, 0x0611F4, 0x0618FC, 0x08B6F0],
    "accepted_roots": [0x0611F4, 0x0618FC, 0x08B6F0, 0x09A3E0],
    "rejected_roots": [0x09C0F4],
    "producer_count": 5,
    "target_decoded_instruction_count": 197,
    "target_decoded_basic_block_count": 31,
    "target_reachable_instruction_bytes": 398,
    "target_frontier_count": 3,
    "target_frontiers": [
        [0x061274, "indirect_pc_target"],
        [0x061934, "indirect_pc_target"],
        [0x08B798, "indirect_pc_target"],
    ],
    "target_instruction_internal_edge_count": 208,
    "target_block_internal_edge_count": 42,
    "target_external_call_edge_count": 2,
    "target_literal_reference_count": 17,
    "target_unique_literal_word_count": 13,
    "target_literal_bytes": 52,
        "promotion_range_count": 10,
    "semantic_promotion_range_count": 10,
    "promotion_union_range_count": 7,
    "promotion_bytes": 450,
    "promotion_code_bytes": 398,
    "promotion_literal_bytes": 52,
    "hole_bytes": 386,
    "semantic_range_vector_sha256": PROMOTION_SEMANTIC_RANGE_SHA256,
    "union_range_vector_sha256": PROMOTION_UNION_RANGE_SHA256,
    "promotion_packed_sha256": PROMOTION_PACKED_SHA256,
    "nonclaims": {name: False for name in NONCLAIMS},
}


def _require_rom(rom: bytes) -> None:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")


def _canonical_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    if _canonical_json(value) != raw:
        raise ValueError(f"{label} is not canonical JSON")
    return value


def _assert_oracle_identity(root: Path) -> None:
    for identity in ORACLE_IDENTITIES.values():
        path = _safe_file(root, identity["path"])
        if _sha(path.read_bytes()) != identity["sha256"]:
            raise ValueError("v13 decoder oracle identity changed")


def _load_upstream_payloads(root: Path) -> dict[int, dict[str, Any]]:
    payloads: dict[int, dict[str, Any]] = {}
    for label, identity in UPSTREAM.items():
        version = int(label.removeprefix("v"))
        manifest_path = _safe_file(root, identity["manifest_path"])
        payload_path = _safe_file(root, identity["payload_path"])
        manifest_raw = manifest_path.read_bytes()
        payload_raw = payload_path.read_bytes()
        if _sha(manifest_raw) != identity["manifest_sha256"]:
            raise ValueError(f"accepted upstream {label} identity changed")
        if _sha(payload_raw) != identity["payload_sha256"]:
            raise ValueError(f"accepted upstream {label} identity changed")
        manifest = _canonical_object(manifest_raw, f"upstream {label} manifest")
        payload = _canonical_object(payload_raw, f"upstream {label} payload")
        expected_schema = f"rom-cfg-proven-roots-v{version}"
        if payload.get("schema") != expected_schema or manifest.get("artifact_schema") != expected_schema:
            raise ValueError(f"accepted upstream {label} contract changed")
        if version != 8 and manifest.get("artifact_status") != "accepted":
            raise ValueError(f"accepted upstream {label} status changed")
        file_record = manifest.get("files", {}).get(Path(identity["payload_path"]).name, {})
        if file_record.get("sha256") != identity["payload_sha256"]:
            raise ValueError(f"accepted upstream {label} payload receipt changed")
        payloads[version] = payload
    return payloads


def _producer_denominator(rom: bytes, target_root: int) -> dict[str, Any]:
    _require_rom(rom)
    matches = [spec for spec in (*TARGET_SPECS, REJECTED_TARGET_SPEC) if spec["root"] == target_root]
    if len(matches) != 1:
        raise ValueError("target root is outside the frozen v15 denominator")
    spec = matches[0]
    thumb_bl: list[int] = []
    thumb_b: list[int] = []
    thumb_bcond: list[int] = []
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset : offset + 2], "little")
        second = int.from_bytes(rom[offset + 2 : offset + 4], "little")
        if _producer_target(offset, first, second) == target_root:
            thumb_bl.append(offset)
        elif first & 0xF800 == 0xE000:
            displacement = (first & 0x7FF) << 1
            if displacement & 0x800:
                displacement -= 0x1000
            if offset + 4 + displacement == target_root:
                thumb_b.append(offset)
        elif first & 0xF000 == 0xD000 and ((first >> 8) & 0xF) <= 0xD:
            displacement = (first & 0xFF) << 1
            if displacement & 0x100:
                displacement -= 0x200
            if offset + 4 + displacement == target_root:
                thumb_bcond.append(offset)
    arm_b_bl: list[int] = []
    aligned_arm_pointers: list[int] = []
    for offset in range(0, len(rom) - 3, 4):
        word = int.from_bytes(rom[offset : offset + 4], "little")
        if word == ROM_BASE + target_root:
            aligned_arm_pointers.append(offset)
        if word >> 28 != 0xF and (word >> 25) & 0x7 == 0b101:
            displacement = (word & 0xFFFFFF) << 2
            if displacement & 0x02000000:
                displacement -= 0x04000000
            if offset + 8 + displacement == target_root:
                arm_b_bl.append(offset)
    pointer = (ROM_BASE + target_root) | 1
    thumb_pointers = [
        offset
        for offset in range(0, len(rom) - 3, 2)
        if int.from_bytes(rom[offset : offset + 4], "little") == pointer
    ]
    vector = [[offset, target_root, "thumb_bl"] for offset in thumb_bl]
    actual = {
        "aligned_arm_pointers": aligned_arm_pointers,
        "arm_b_bl": arm_b_bl,
        "thumb_b": thumb_b,
        "thumb_bcond": thumb_bcond,
        "thumb_bl": thumb_bl,
        "thumb_pointers": thumb_pointers,
        "vector": vector,
        "vector_sha256": _canonical_sha(vector),
    }
    if actual != spec["producer_denominator"]:
        raise ValueError("target-limited producer denominator changed")
    for producer in spec.get("producers", ()):
        raw = rom[producer["file_offset"] : producer["file_offset"] + 4]
        if raw.hex() != producer["raw_hex"] or _sha(raw) != producer["bytes_sha256"]:
            raise ValueError("producer bytes changed")
    if target_root == REJECTED_TARGET_SPEC["root"]:
        expected = REJECTED_TARGET_SPEC["unbound_raw_matches"][0x0610C6]
        raw = rom[expected["file_offset"] : expected["file_offset"] + 4]
        if raw.hex() != expected["raw_hex"] or _sha(raw) != expected["bytes_sha256"]:
            raise ValueError("unbound rejected producer bytes changed")
    return copy.deepcopy(actual)


def _target_spec(index: int) -> dict[str, Any]:
    try:
        return TARGET_SPECS[index]
    except IndexError as error:
        raise ValueError("target index is outside the frozen v15 denominator") from error


def _merged_ranges(ranges: list[list[int] | tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            raise ValueError("empty or reversed ROM range")
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _intersections(left: list[list[int]], right: list[list[int]]) -> list[list[int]]:
    return _merged_ranges(
        [
            [max(a, c), min(b, d)]
            for a, b in left
            for c, d in right
            if max(a, c) < min(b, d)
        ]
    )


def _subtract_ranges(ranges: list[list[int]], blockers: list[list[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in ranges:
        pieces = [[start, end]]
        for block_start, block_end in blockers:
            next_pieces: list[list[int]] = []
            for piece_start, piece_end in pieces:
                if block_end <= piece_start or piece_end <= block_start:
                    next_pieces.append([piece_start, piece_end])
                else:
                    if piece_start < block_start:
                        next_pieces.append([piece_start, block_start])
                    if block_end < piece_end:
                        next_pieces.append([block_end, piece_end])
            pieces = next_pieces
        result.extend(pieces)
    return _merged_ranges(result) if result else []


def _literal_projection(
    rom: bytes,
    nodes: dict[tuple[str, int], dict[str, Any]],
    spec: dict[str, Any],
) -> dict[str, Any]:
    bindings: list[list[Any]] = []
    for node in _base._nodes(nodes):
        offset = node["file_offset"]
        if node["mnemonic"] != "ldr" or "[pc," not in node["op_str"]:
            continue
        raw = rom[offset : offset + 2]
        halfword = int.from_bytes(raw, "little")
        if halfword & 0xF800 != 0x4800:
            continue
        literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
        literal_raw = rom[literal : literal + 4]
        bindings.append([offset, literal, int.from_bytes(literal_raw, "little"), raw.hex(), literal_raw.hex()])
    unique_words = sorted({row[1] for row in bindings})
    envelope_start, envelope_end = spec["envelope"]
    internal_words = [offset for offset in unique_words if envelope_start <= offset and offset + 4 <= envelope_end]
    external_words = [offset for offset in unique_words if offset not in internal_words]
    internal_ranges = _merged_ranges([[offset, offset + 4] for offset in internal_words])
    external_ranges = _merged_ranges([[offset, offset + 4] for offset in external_words])
    if external_ranges != spec["known_external_literal_ranges"]:
        raise ValueError("known external literal projection changed")
    overlap_ranges = _intersections(internal_ranges, spec["code_ranges"])
    literal_only_ranges = _subtract_ranges(internal_ranges, spec["code_ranges"])
    binding_vector = [[row[0], row[1]] for row in bindings]
    projection = {
        "bindings": bindings,
        "binding_vector": binding_vector,
        "literal_reference_count": len(bindings),
        "unique_literal_word_count": len(unique_words),
        "all_ranges": _merged_ranges([[offset, offset + 4] for offset in unique_words]),
        "internal_ranges": internal_ranges,
        "known_external_ranges": external_ranges,
        "literal_only_ranges": literal_only_ranges,
        "literal_code_overlap_ranges": overlap_ranges,
        "internal_bytes": sum(end - start for start, end in internal_ranges),
        "known_external_bytes": sum(end - start for start, end in external_ranges),
        "literal_only_bytes": sum(end - start for start, end in literal_only_ranges),
        "overlap_bytes": sum(end - start for start, end in overlap_ranges),
        "internal_range_vector_sha256": _canonical_sha(internal_ranges),
        "known_external_range_vector_sha256": _canonical_sha(external_ranges),
        "binding_vector_sha256": _canonical_sha(binding_vector),
        "packed_internal_sha256": _packed(rom, internal_ranges),
        "packed_known_external_sha256": _packed(rom, external_ranges),
    }
    if (
        projection["internal_ranges"] != spec["literal_ranges"]
        or projection["literal_only_ranges"] != _subtract_ranges(spec["literal_ranges"], spec["code_ranges"])
        or projection["literal_code_overlap_ranges"] != spec.get("literal_code_overlap_ranges", [])
        or projection["literal_reference_count"] != spec["literal_reference_count"]
        or projection["unique_literal_word_count"] != spec["unique_literal_word_count"]
        or projection["binding_vector_sha256"] != spec["literal_binding_vector_sha256"]
        or projection["internal_range_vector_sha256"] != spec["literal_range_vector_sha256"]
        or projection["packed_internal_sha256"] != _packed(rom, spec["literal_ranges"])
    ):
        raise ValueError("target literal projection changed")
    return projection


def _holes(envelope: list[int], occupied: list[list[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    cursor = envelope[0]
    for start, end in sorted(occupied):
        if cursor < start:
            result.append([cursor, start])
        cursor = max(cursor, end)
    if cursor < envelope[1]:
        result.append([cursor, envelope[1]])
    return result


def _target_worklist(rom: bytes, target_index: int) -> dict[str, Any]:
    _require_rom(rom)
    spec = _target_spec(target_index)
    start, end = spec["envelope"]
    if _sha(rom[start:end]) != spec["envelope_sha256"]:
        raise ValueError("target envelope changed")
    nodes, blocks, external, boundary = _base._bounded_worklist(rom, spec["root"], (start, end), None)
    if len(nodes) != spec["decoded_instruction_count"] or len(blocks) != spec["decoded_basic_block_count"]:
        raise ValueError("target CFG denominator changed")
    code_ranges = _base._merged_ranges(nodes)
    block_ranges = [block["range"] for block in blocks]
    instruction_internal = [
        [node["file_offset"], edge["file_offset"], edge["kind"]]
        for node in _base._nodes(nodes)
        for edge in node["successors"]
        if (edge["mode"], edge["file_offset"]) in nodes
    ]
    instruction_internal.sort(key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1]))
    block_internal = [
        [block["terminator"]["file_offset"], edge["file_offset"], edge["kind"]]
        for block in blocks
        for edge in block["successors"]
    ]
    block_internal.sort(key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1]))
    external_vector = [
        [row["source_file_offset"], row["target_file_offset"], row["edge_kind"]]
        for row in sorted(external, key=lambda row: row["source_file_offset"])
    ]
    frontiers = _base._frontier_vector(nodes)
    semantic = _base._semantic(nodes)
    literals = _literal_projection(rom, nodes, spec)
    expected_external = [
        [row["source_file_offset"], row["target_file_offset"], row["edge_kind"]]
        for row in spec["external_edges"]
    ]
    checks = {
        "code ranges": code_ranges == spec["code_ranges"],
        "block ranges": block_ranges == spec["block_ranges"],
        "frontiers": frontiers == spec["frontiers"],
        "external edges": external_vector == expected_external,
        "boundary edges": boundary == spec["boundary_edges"],
        "code hash": _canonical_sha(code_ranges) == spec["code_range_vector_sha256"],
        "block hash": _canonical_sha(block_ranges) == spec["block_range_vector_sha256"],
        "semantic hash": _canonical_sha(semantic) == spec["semantic_instruction_vector_sha256"],
        "instruction edge count": len(instruction_internal) == spec["instruction_internal_edge_count"],
        "instruction edge hash": _canonical_sha(instruction_internal) == spec["instruction_internal_edge_vector_sha256"],
        "block edge count": len(block_internal) == spec["block_internal_edge_count"],
        "block edge hash": _canonical_sha(block_internal) == spec["block_internal_edge_vector_sha256"],
        "external hash": _canonical_sha(external_vector) == spec["external_edge_vector_sha256"],
        "frontier hash": _canonical_sha(frontiers) == spec["frontier_vector_sha256"],
        "code bytes": _packed(rom, code_ranges) == spec["packed_code_sha256"],
        "promotion bytes": _packed(rom, spec["promotion_ranges"]) == spec["packed_promotion_sha256"],
        "promotion ranges": _canonical_sha(spec["promotion_ranges"]) == spec["promotion_range_vector_sha256"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("target CFG vector changed: " + ", ".join(failed))
    if literals["literal_code_overlap_ranges"] or literals["known_external_ranges"] != spec["known_external_literal_ranges"]:
        raise ValueError("accepted literal projection is not disjoint")
    occupied = _merged_ranges(code_ranges + literals["literal_only_ranges"])
    holes = _holes(spec["envelope"], occupied)
    if holes != spec["holes"]:
        raise ValueError("preserved unknown holes changed")
    return {
        "name": spec["name"],
        "root": spec["root"],
        "root_gba_address": f"0x{ROM_BASE + spec['root']:08X}",
        "root_raw_hex": spec["root_raw_hex"],
        "root_sha256": spec["root_sha256"],
        "envelope": copy.deepcopy(spec["envelope"]),
        "envelope_bytes": spec["envelope_bytes"],
        "envelope_sha256": spec["envelope_sha256"],
        "producer_denominator": _producer_denominator(rom, spec["root"]),
        "producer_membership": [],
        "unbound_raw_thumb_bl_matches": [],
        "unbound_raw_matches": [],
        "accepted": True,
        "reasons": [],
        "decoded_instruction_count": len(nodes),
        "decoded_basic_block_count": len(blocks),
        "reachable_instruction_bytes": sum(node["size"] for node in nodes.values()),
        "code_ranges": code_ranges,
        "code_range_vector_sha256": spec["code_range_vector_sha256"],
        "block_ranges": block_ranges,
        "block_range_vector_sha256": spec["block_range_vector_sha256"],
        "semantic_instruction_vector_sha256": spec["semantic_instruction_vector_sha256"],
        "instruction_internal_edge_count": len(instruction_internal),
        "instruction_internal_edge_vector_sha256": spec["instruction_internal_edge_vector_sha256"],
        "block_internal_edge_count": len(block_internal),
        "block_internal_edge_vector_sha256": spec["block_internal_edge_vector_sha256"],
        "external_edges": external,
        "external_edge_vector": external_vector,
        "external_edge_vector_sha256": spec["external_edge_vector_sha256"],
        "boundary_edges": boundary,
        "frontiers": frontiers,
        "frontier_vector_sha256": spec["frontier_vector_sha256"],
        "literal_projection": literals,
        "literal_only_bytes": literals["literal_only_bytes"],
        "literal_code_overlap_ranges": literals["literal_code_overlap_ranges"],
        "known_external_literal_ranges": literals["known_external_ranges"],
        "promotion_ranges": copy.deepcopy(spec["promotion_ranges"]),
        "promotion_range_vector_sha256": spec["promotion_range_vector_sha256"],
        "promotion_bytes": spec["promotion_bytes"],
        "packed_code_sha256": spec["packed_code_sha256"],
        "packed_literals_sha256": _packed(rom, literals["literal_only_ranges"]),
        "packed_promotion_sha256": spec["packed_promotion_sha256"],
        "holes": holes,
        "coverage_projection": {
            "overlaps": [[start, end, "unknown"] for start, end in spec["promotion_ranges"]],
            "known_bytes": 0,
            "unknown_bytes": spec["promotion_bytes"],
        },
    }


def _producer_membership(root: Path, rom: bytes, target_index: int, payloads: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    spec = _target_spec(target_index)
    result: list[dict[str, Any]] = []
    for frozen in spec.get("producers", ()):
        version = frozen["upstream_version"]
        payload = payloads[version]
        offset = frozen["file_offset"]
        raw = rom[offset : offset + 4]
        if raw.hex() != frozen["raw_hex"] or _sha(raw) != frozen["bytes_sha256"]:
            raise ValueError("source producer bytes changed")
        if version == 12:
            nodes = [node for node in payload.get("source", {}).get("nodes", []) if node.get("file_offset") == offset]
            if len(nodes) != 1:
                raise ValueError("accepted upstream source node denominator changed")
            node = nodes[0]
            call_targets = [
                {"file_offset": edge.get("file_offset"), "kind": edge.get("kind"), "mode": edge.get("mode")}
                for edge in node.get("successors", []) if edge.get("kind") == "call_target"
            ]
            if (
                node.get("accepted") is not True
                or node.get("mode") != "thumb"
                or node.get("mnemonic") != "bl"
                or node.get("flow_kind") != "call"
                or node.get("bytes_sha256") != frozen["bytes_sha256"]
                or call_targets != [{"file_offset": spec["root"], "kind": "call_target", "mode": "thumb"}]
            ):
                raise ValueError("accepted upstream producer membership changed")
            result.append({**copy.deepcopy(frozen), "artifact_node": copy.deepcopy(node)})
        elif version == 8:
            accepted = payload.get("source", {}).get("worklist", {}).get("accepted_instruction_offsets", [])
            if accepted.count(offset) != 1 or frozen["source_pointer"] != f"/source/worklist/accepted_instruction_offsets/{accepted.index(offset)}":
                raise ValueError("accepted V8 source worklist membership changed")
            result.append(copy.deepcopy(frozen))
        else:
            raise ValueError("unsupported source artifact version")
    return result


def _excluded_source_candidate(rom: bytes, payloads: dict[int, dict[str, Any]]) -> dict[str, Any]:
    frozen = EXCLUDED_SOURCE_SPEC
    raw = rom[frozen["file_offset"] : frozen["file_offset"] + 4]
    accepted = payloads[8].get("source", {}).get("worklist", {}).get("accepted_instruction_offsets", [])
    if raw.hex() != frozen["raw_hex"] or _sha(raw) != frozen["bytes_sha256"]:
        raise ValueError("excluded source candidate bytes changed")
    first = int.from_bytes(raw[:2], "little")
    second = int.from_bytes(raw[2:], "little")
    if _producer_target(frozen["file_offset"], first, second) != frozen["decoded_target"]:
        raise ValueError("excluded source candidate target changed")
    if frozen["file_offset"] in accepted:
        raise ValueError("excluded source candidate became accepted")
    return copy.deepcopy(frozen)


def _target_worklist_rejected(rom: bytes, payloads: dict[int, dict[str, Any]]) -> dict[str, Any]:
    spec = REJECTED_TARGET_SPEC
    _require_rom(rom)
    start, end = spec["envelope"]
    if _sha(rom[start:end]) != spec["envelope_sha256"]:
        raise ValueError("rejected target envelope changed")
    nodes, blocks, external, boundary = _base._bounded_worklist(rom, spec["root"], (start, end), None)
    if len(nodes) != spec["decoded_instruction_count"] or len(blocks) != spec["decoded_basic_block_count"]:
        raise ValueError("rejected target CFG denominator changed")
    code_ranges = _base._merged_ranges(nodes)
    block_ranges = [block["range"] for block in blocks]
    instruction_internal = [
        [node["file_offset"], edge["file_offset"], edge["kind"]]
        for node in _base._nodes(nodes)
        for edge in node["successors"] if (edge["mode"], edge["file_offset"]) in nodes
    ]
    instruction_internal.sort(key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1]))
    block_internal = [
        [block["terminator"]["file_offset"], edge["file_offset"], edge["kind"]]
        for block in blocks for edge in block["successors"]
    ]
    block_internal.sort(key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1]))
    external_vector = [
        [row["source_file_offset"], row["target_file_offset"], row["edge_kind"]]
        for row in sorted(external, key=lambda row: row["source_file_offset"])
    ]
    frontiers = _base._frontier_vector(nodes)
    semantic = _base._semantic(nodes)
    bindings: list[list[Any]] = []
    for node in _base._nodes(nodes):
        offset = node["file_offset"]
        if node["mnemonic"] == "ldr" and "[pc," in node["op_str"]:
            raw = rom[offset : offset + 2]
            halfword = int.from_bytes(raw, "little")
            if halfword & 0xF800 == 0x4800:
                literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
                literal_raw = rom[literal : literal + 4]
                bindings.append([offset, literal, int.from_bytes(literal_raw, "little"), raw.hex(), literal_raw.hex()])
    binding_vector = [[row[0], row[1]] for row in bindings]
    internal_ranges = [[0x09C108, 0x09C110]]
    literals = {
        "bindings": bindings,
        "binding_vector": binding_vector,
        "literal_reference_count": len(bindings),
        "unique_literal_word_count": len({row[1] for row in bindings}),
        "all_ranges": internal_ranges,
        "internal_ranges": internal_ranges,
        "known_external_ranges": [],
        "literal_only_ranges": [],
        "literal_code_overlap_ranges": internal_ranges,
        "internal_bytes": 8,
        "known_external_bytes": 0,
        "literal_only_bytes": 0,
        "overlap_bytes": 8,
        "internal_range_vector_sha256": _canonical_sha(internal_ranges),
        "known_external_range_vector_sha256": _canonical_sha([]),
        "binding_vector_sha256": _canonical_sha(binding_vector),
        "packed_internal_sha256": _packed(rom, internal_ranges),
        "packed_known_external_sha256": _packed(rom, []),
    }
    expected_external = []
    checks = {
        "code ranges": code_ranges == spec["code_ranges"],
        "blocks": block_ranges == spec["block_ranges"],
        "semantic": _canonical_sha(semantic) == spec["semantic_instruction_vector_sha256"],
        "instruction edges": len(instruction_internal) == spec["instruction_internal_edge_count"] and _canonical_sha(instruction_internal) == spec["instruction_internal_edge_vector_sha256"],
        "block edges": len(block_internal) == spec["block_internal_edge_count"] and _canonical_sha(block_internal) == spec["block_internal_edge_vector_sha256"],
        "external": external_vector == expected_external and _canonical_sha(external_vector) == spec["external_edge_vector_sha256"],
        "boundary": boundary == spec["boundary_edges"],
        "frontiers": frontiers == spec["frontiers"] and _canonical_sha(frontiers) == spec["frontier_vector_sha256"],
        "literal binding": binding_vector == spec["literal_binding_vector"] and _canonical_sha(binding_vector) == spec["literal_binding_vector_sha256"],
        "code hash": _canonical_sha(code_ranges) == spec["code_range_vector_sha256"] and _packed(rom, code_ranges) == spec["packed_code_sha256"],
        "promotion hash": _canonical_sha(spec["promotion_ranges"]) == spec["promotion_range_vector_sha256"] and _packed(rom, spec["promotion_ranges"]) == spec["packed_promotion_sha256"],
    }
    failed = [key for key, ok in checks.items() if not ok]
    if failed:
        raise ValueError("rejected target vector changed: " + ", ".join(failed))
    if len(bindings) != 2 or len({row[1] for row in bindings}) != 2:
        raise ValueError("rejected literal denominator changed")
    producer_denominator = _producer_denominator(rom, spec["root"])
    frozen_unbound = spec["unbound_raw_matches"][0x0610C6]
    raw = rom[0x0610C6 : 0x0610CA]
    if raw.hex() != frozen_unbound["raw_hex"] or _sha(raw) != frozen_unbound["bytes_sha256"]:
        raise ValueError("rejected unbound raw match changed")
    frozen = spec["producers"][0]
    nodes12 = [node for node in payloads[12].get("source", {}).get("nodes", []) if node.get("file_offset") == frozen["file_offset"]]
    if len(nodes12) != 1:
        raise ValueError("rejected source membership changed")
    node = nodes12[0]
    call_targets = [edge for edge in node.get("successors", []) if edge.get("kind") == "call_target"]
    if node.get("accepted") is not True or node.get("mnemonic") != "bl" or call_targets != [{"file_offset": spec["root"], "kind": "call_target", "mode": "thumb"}]:
        raise ValueError("rejected source membership changed")
    rejected_membership = [{**copy.deepcopy(frozen), "artifact_node": copy.deepcopy(node)}]
    return {
        "name": spec["name"],
        "root": spec["root"],
        "root_gba_address": f"0x{ROM_BASE + spec['root']:08X}",
        "root_raw_hex": spec["root_raw_hex"],
        "root_sha256": spec["root_sha256"],
        "envelope": copy.deepcopy(spec["envelope"]),
        "envelope_bytes": spec["envelope_bytes"],
        "envelope_sha256": spec["envelope_sha256"],
        "producer_denominator": producer_denominator,
        "producer_membership": rejected_membership,
        "unbound_raw_thumb_bl_matches": copy.deepcopy(spec["unbound_raw_thumb_bl_matches"]),
        "unbound_raw_matches": [copy.deepcopy(frozen_unbound)],
        "accepted": False,
        "reasons": copy.deepcopy(spec["reasons"]),
        "decoded_instruction_count": len(nodes),
        "decoded_basic_block_count": len(blocks),
        "reachable_instruction_bytes": sum(node["size"] for node in nodes.values()),
        "code_ranges": code_ranges,
        "code_range_vector_sha256": spec["code_range_vector_sha256"],
        "block_ranges": block_ranges,
        "block_range_vector_sha256": spec["block_range_vector_sha256"],
        "semantic_instruction_vector_sha256": spec["semantic_instruction_vector_sha256"],
        "instruction_internal_edge_count": len(instruction_internal),
        "instruction_internal_edge_vector_sha256": spec["instruction_internal_edge_vector_sha256"],
        "block_internal_edge_count": len(block_internal),
        "block_internal_edge_vector_sha256": spec["block_internal_edge_vector_sha256"],
        "external_edges": external,
        "external_edge_vector": external_vector,
        "external_edge_vector_sha256": spec["external_edge_vector_sha256"],
        "boundary_edges": boundary,
        "frontiers": frontiers,
        "frontier_vector_sha256": spec["frontier_vector_sha256"],
        "literal_projection": literals,
        "literal_only_bytes": 0,
        "literal_code_overlap_ranges": internal_ranges,
        "known_external_literal_ranges": [],
        "promotion_ranges": copy.deepcopy(spec["promotion_ranges"]),
        "promotion_range_vector_sha256": spec["promotion_range_vector_sha256"],
        "promotion_bytes": spec["promotion_bytes"],
        "packed_code_sha256": spec["packed_code_sha256"],
        "packed_literals_sha256": spec["packed_literals_sha256"],
        "packed_promotion_sha256": spec["packed_promotion_sha256"],
        "holes": [],
        "coverage_projection": {"overlaps": [[spec["root"], spec["envelope"][1], "unknown"]], "known_bytes": 0, "unknown_bytes": spec["promotion_bytes"]},
    }


PROMOTION_CODE_RANGES = [
    [0x0611F4, 0x06123A], [0x061250, 0x061276], [0x0618FC, 0x061920],
    [0x061924, 0x061936], [0x08B6F0, 0x08B79A], [0x09A3E0, 0x09A422],
]
PROMOTION_LITERAL_RANGES = [
    [0x06123C, 0x061250], [0x061278, 0x06128C], [0x061920, 0x061924], [0x09A424, 0x09A42C],
]


def _promotion(rom: bytes, targets: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> dict[str, Any]:
    ranges = copy.deepcopy(PROMOTION_UNION_RANGES)
    if any(_intersections(ranges, target.get("promotion_ranges", [])) for target in rejected):
        raise ValueError("rejected target intersects promotion union")
    if any(target.get("accepted") is not False for target in rejected):
        raise ValueError("rejected target entered promotion scope")
    if _canonical_sha(PROMOTION_SEMANTIC_RANGES) != PROMOTION_SEMANTIC_RANGE_SHA256 or _canonical_sha(ranges) != PROMOTION_UNION_RANGE_SHA256:
        raise ValueError("promotion range vector changed")
    if _packed(rom, ranges) != PROMOTION_PACKED_SHA256:
        raise ValueError("packed promotion bytes changed")
    code_bytes = sum(target["reachable_instruction_bytes"] for target in targets)
    literal_only_bytes = sum(target["literal_only_bytes"] for target in targets)
    holes = [hole for target in targets for hole in target["holes"]]
    promotion_bytes = sum(end - start for start, end in ranges)
    if code_bytes != 398 or literal_only_bytes != 52 or promotion_bytes != 450 or sum(end - start for start, end in holes) != 386:
        raise ValueError("combined promotion denominator changed")
    if _packed(rom, PROMOTION_CODE_RANGES) != PROMOTION_CODE_PACKED_SHA256 or _packed(rom, PROMOTION_LITERAL_RANGES) != PROMOTION_LITERAL_PACKED_SHA256:
        raise ValueError("packed promotion partition changed")
    return {
        "batch": "cfg-proven-roots-v15",
        "ranges": copy.deepcopy(ranges),
        "union_ranges": copy.deepcopy(ranges),
        "semantic_ranges": copy.deepcopy(PROMOTION_SEMANTIC_RANGES),
        "promotion_range_count": len(PROMOTION_SEMANTIC_RANGES),
        "semantic_range_count": len(PROMOTION_SEMANTIC_RANGES),
        "promotion_union_range_count": len(ranges),
        "accepted_root_count": len(targets),
        "rejected_root_count": len(rejected),
        "accepted_roots": [target["root"] for target in targets],
        "rejected_roots": [target["root"] for target in rejected],
        "code_bytes": code_bytes,
        "literal_only_bytes": literal_only_bytes,
        "promotion_bytes": promotion_bytes,
        "promotion_code_bytes": code_bytes,
        "promotion_literal_bytes": literal_only_bytes,
        "preserved_unknown_hole_bytes": sum(end - start for start, end in holes),
        "hole_bytes": sum(end - start for start, end in holes),
        "semantic_range_vector_sha256": PROMOTION_SEMANTIC_RANGE_SHA256,
        "union_range_vector_sha256": PROMOTION_UNION_RANGE_SHA256,
        "range_vector_sha256": PROMOTION_UNION_RANGE_SHA256,
        "packed_sha256": PROMOTION_PACKED_SHA256,
        "packed_code_sha256": PROMOTION_CODE_PACKED_SHA256,
        "packed_literal_sha256": PROMOTION_LITERAL_PACKED_SHA256,
        "coverage_projection": {"overlaps": [[start, end, "unknown"] for start, end in ranges], "known_bytes": 0, "unknown_bytes": promotion_bytes},
        "summary": {
            "decoded_instruction_count": sum(target["decoded_instruction_count"] for target in targets),
            "decoded_basic_block_count": sum(target["decoded_basic_block_count"] for target in targets),
            "reachable_instruction_bytes": code_bytes,
            "literal_only_bytes": literal_only_bytes,
            "frontier_count": sum(len(target["frontiers"]) for target in targets),
            "external_call_edge_count": sum(len(target["external_edges"]) for target in targets),
        },
    }


def _runtime_dependencies(root: Path) -> dict[str, str]:
    return {path.as_posix(): _sha(_safe_file(root, path).read_bytes()) for path in RUNTIME_DEPENDENCY_PATHS}


def _implementation(root: Path) -> dict[str, Any]:
    paths = {
        "exporter": Path("tools/export_rom_cfg_proven_roots_v15.py"),
        "verifier": Path("tools/verify_rom_cfg_proven_roots_v15.py"),
        "bundle_verifier": Path("tools/verify_rom_cfg_proven_roots_v15_bundle.py"),
        "test_exporter": Path("tests/test_export_rom_cfg_proven_roots_v15.py"),
        "test_verifier": Path("tests/test_verify_rom_cfg_proven_roots_v15.py"),
        "test_bundle_verifier": Path("tests/test_verify_rom_cfg_proven_roots_v15_bundle.py"),
    }
    return {
        "binding": "passed-root-runtime-dependency-and-test-hash-bound",
        "paths": {key: path.as_posix() for key, path in paths.items()},
        "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()),
        "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()),
        "bundle_verifier_sha256": _sha(_safe_file(root, paths["bundle_verifier"]).read_bytes()),
        "test_exporter_sha256": _sha(_safe_file(root, paths["test_exporter"]).read_bytes()),
        "test_verifier_sha256": _sha(_safe_file(root, paths["test_verifier"]).read_bytes()),
        "test_bundle_verifier_sha256": _sha(_safe_file(root, paths["test_bundle_verifier"]).read_bytes()),
        "runtime_dependency_sha256": _runtime_dependencies(root),
        "oracle_identities": copy.deepcopy(ORACLE_IDENTITIES),
    }


def _artifact_relative_path(root: Path, artifact: Path) -> str:
    root = Path(root).resolve(strict=True)
    candidate = Path(artifact).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    if candidate.is_symlink():
        raise ValueError("v15 artifact directory uses a symlink")
    try:
        lexical_relative = candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("v15 artifact directory is not repository-relative") from error
    current = root
    for component in lexical_relative.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError("v15 artifact path uses a symlink")
    resolved = candidate.resolve(strict=True)
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("v15 artifact directory escaped repository root") from error
    if not relative.parts:
        raise ValueError("v15 artifact directory cannot be repository root")
    return relative.as_posix()


def _expected_payload(root: Path, rom: bytes, artifact: Path) -> dict[str, Any]:
    _require_rom(rom)
    _assert_oracle_identity(root)
    payloads = _load_upstream_payloads(root)
    targets: list[dict[str, Any]] = []
    for index, _spec in enumerate(TARGET_SPECS):
        target = _target_worklist(rom, index)
        target["producer_membership"] = _producer_membership(root, rom, index, payloads)
        targets.append(target)
    rejected = _target_worklist_rejected(rom, payloads)
    promotion = _promotion(rom, targets, [rejected])
    source_membership = [
        member
        for target in [targets[0], rejected, *targets[1:]]
        for member in target["producer_membership"]
    ]
    return {
        "schema": SCHEMA,
        "artifact_relative_path": _artifact_relative_path(root, artifact),
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "upstream": copy.deepcopy(UPSTREAM),
        "source_membership": source_membership,
        "excluded_source_candidate": _excluded_source_candidate(rom, payloads),
        "targets": targets,
        "rejected_targets": [rejected],
        "promotion": promotion,
        "implementation": _implementation(root),
        "scope": copy.deepcopy(SCOPE),
    }


def _artifact_file(artifact: Path, name: str) -> Path:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("v15 artifact directory is missing or uses a symlink")
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("v15 artifact file set uses a symlink or is incomplete")
    return path


def _receipt_commands(root: Path, manifest: dict[str, Any], artifact: Path) -> tuple[list[str], list[str]]:
    producer = manifest.get("producer")
    verifier = manifest.get("verifier")
    if not isinstance(producer, dict) or not isinstance(verifier, dict):
        raise ValueError("v15 promotion receipt is missing")
    producer_command = producer.get("command")
    verifier_command = verifier.get("command")
    producer_prefix = ["python3", "-I", "-S", "tools/export_rom_cfg_proven_roots_v15.py", "--root", ".", "--output-dir"]
    verifier_prefix = ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v15.py", "--root", ".", "--artifact-dir"]
    if (
        not isinstance(producer_command, list) or producer_command[:-1] != producer_prefix
        or not isinstance(verifier_command, list) or verifier_command[:-1] != verifier_prefix
        or producer_command[-1] != verifier_command[-1]
    ):
        raise ValueError("v15 promotion receipt command changed")
    recorded = Path(producer_command[-1])
    if recorded.is_absolute() or ".." in recorded.parts:
        raise ValueError("v15 promotion receipt path must be repository-relative")
    target = (root / recorded).resolve(strict=False)
    allowed = (root / EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    official = (root / OFFICIAL_ARTIFACT).resolve(strict=False)
    if target != official and (target == allowed or allowed not in target.parents):
        raise ValueError("v15 promotion receipt path escaped experiment subtree")
    if target != artifact.resolve(strict=True):
        raise ValueError("v15 promotion receipt path does not match actual artifact directory")
    return producer_command, verifier_command


def _expected_manifest(root: Path, artifact: Path, manifest: dict[str, Any], payload: dict[str, Any], payload_raw: bytes, status: str) -> dict[str, Any]:
    if status not in {"candidate", "accepted"}:
        raise ValueError("v15 promotion status changed")
    producer_command, verifier_command = _receipt_commands(root, manifest, artifact)
    implementation = payload["implementation"]
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "rom": payload["rom"],
        "upstream": payload["upstream"],
        "source_membership": payload["source_membership"],
        "excluded_source_candidate": payload["excluded_source_candidate"],
        "targets": payload["targets"],
        "rejected_targets": payload["rejected_targets"],
        "promotion": payload["promotion"],
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
        "producer": {"command": producer_command, "implementation": implementation},
        "verifier": {
            "schema": VERIFY_SCHEMA,
            "command": verifier_command,
            "exit_code": 0 if status == "accepted" else None,
            "report": EXPECTED_REPORT if status == "accepted" else None,
            "verifier_sha256": implementation["verifier_sha256"],
        },
        "implementation": implementation,
        "scope": payload["scope"],
    }


def _failure(message: str) -> dict[str, Any]:
    report = copy.deepcopy(EXPECTED_REPORT)
    report["verified"] = False
    report["errors"] = [message]
    return report


def _verify_in_process(root: Path, artifact_dir: Path) -> dict[str, Any]:
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).expanduser()
        if not artifact.is_absolute():
            artifact = root / artifact
        artifact = artifact.absolute()
        if artifact.is_symlink() or not artifact.is_dir():
            raise ValueError("v15 artifact directory is missing or uses a symlink")
        members = list(artifact.rglob("*"))
        files = {path.relative_to(artifact).as_posix() for path in members if path.is_file()}
        if files != {MANIFEST_NAME, PAYLOAD_NAME} or any(path.is_symlink() for path in members):
            raise ValueError("v15 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        payload_path = _artifact_file(artifact, PAYLOAD_NAME)
        manifest_path = _artifact_file(artifact, MANIFEST_NAME)
        payload_raw = payload_path.read_bytes()
        manifest_raw = manifest_path.read_bytes()
        payload = _canonical_object(payload_raw, "v15 payload")
        manifest = _canonical_object(manifest_raw, "v15 manifest")
        expected_payload = _expected_payload(root, rom, artifact)
        if payload != expected_payload:
            raise ValueError("v15 payload contract differs from independent reconstruction")
        expected_manifest = _expected_manifest(root, artifact, manifest, expected_payload, payload_raw, manifest.get("artifact_status"))
        if manifest != expected_manifest:
            raise ValueError("v15 manifest contract differs from independent reconstruction")
        return copy.deepcopy(EXPECTED_REPORT)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return _failure(str(error))


def verify_rom_cfg_proven_roots_v15(root: Path, artifact_dir: Path) -> dict[str, Any]:
    return _verify_in_process(root, artifact_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify_rom_cfg_proven_roots_v15(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
