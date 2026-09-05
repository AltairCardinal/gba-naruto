#!/usr/bin/env python3
"""Independently verify the second direct-call-proven Thumb CFG root batch."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import heapq
import json
from pathlib import Path
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.verify_rom_cfg_inventory import (
    MAX_BLOCK_INSTRUCTION_COUNT,
    MAX_INSTRUCTION_COUNT,
    ROM_PATH,
    ROM_SHA256,
    _canonical_sha,
    _decode,
    _decoder_identity,
    _expected_roots,
    _safe_file,
    _sha,
    _union_bytes,
    _verify_blocks,
)
from tools.verify_rom_cfg_inventory_v3 import verify_rom_cfg_inventory_v3
from tools.verify_rom_cfg_proven_roots import verify_rom_cfg_proven_roots


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v2"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v2"
PAYLOAD_NAME = "rom-cfg-proven-roots-v2.json"

V2_ARTIFACT = Path("artifacts/rom-cfg-inventory-v2")
V2_PAYLOAD_NAME = "rom-cfg-inventory.json"
V2_SCHEMA = "rom-cfg-inventory-v2"
V2_MANIFEST_SHA256 = (
    "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"
)
V2_PAYLOAD_SHA256 = (
    "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
)
V2_PAYLOAD_SIZE = 5_936_694
V2_GRAPH_SHA256 = (
    "e3f6c04ea459dbec397a9d71d6f32591ec03ed076ff8aad227277cb2b3534ba3"
)
V2_VERIFIER_PATH = Path("tools/verify_rom_cfg_inventory.py")
V2_VERIFIER_SHA256 = (
    "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"
)

V3_ARTIFACT = Path("artifacts/rom-cfg-inventory-v3")
V3_PAYLOAD_NAME = "rom-cfg-inventory-v3.json"
V3_SCHEMA = "rom-cfg-inventory-v3"
V3_MANIFEST_SHA256 = (
    "6aa788611f73856e621f5c74aab544d47b034307a9dc1180f6fd8f81cb1f423b"
)
V3_PAYLOAD_SHA256 = (
    "596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d"
)
V3_PAYLOAD_SIZE = 1_322_391
V3_GRAPH_SHA256 = (
    "456545dddd3c43a5e9c19be6483871dbd333e3af3ecd1da8a9a83f762bced482"
)
V3_VERIFIER_PATH = Path("tools/verify_rom_cfg_inventory_v3.py")
V3_VERIFIER_SHA256 = (
    "46400e44866a93b571745f30779296cc5686889ac5d465891c648296d2dbe00a"
)

V1_ARTIFACT = Path("artifacts/rom-cfg-proven-roots-v1")
V1_PAYLOAD_NAME = "rom-cfg-proven-roots.json"
V1_SCHEMA = "rom-cfg-proven-roots-v1"
V1_MANIFEST_SHA256 = (
    "ea1230fe24cf111a91044c059468a1467e46c471363780b23c2a0311bab8644a"
)
V1_PAYLOAD_SHA256 = (
    "7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54"
)
V1_PAYLOAD_SIZE = 1_024_474
V1_GRAPH_SHA256 = (
    "19898402cc7c168863a61114fa6e28bef12497724b631373f75cf364d370c024"
)
V1_VERIFIER_PATH = Path("tools/verify_rom_cfg_proven_roots.py")
V1_VERIFIER_SHA256 = (
    "693d9381f429346376a6400bea20025ca0c56e1e68d0bf3164b070ea722aa4d7"
)

CONTROLLER_EVIDENCE_PATH = Path("notes/battle-controller-states-20260723.json")
CONTROLLER_EVIDENCE_SHA256 = (
    "e0157597e6d7fddb94d036ddfa7a0d2e74fa232450ad08534cd868d6c6fe1336"
)
CONTROLLER_RANGE = (0x732B4, 0x75082)
CONTROLLER_SHA256 = (
    "30c8e021502cca16fc3f569bbb21dd04f78d20bcbb8e6196550164a0d56429ff"
)

PRODUCER_VECTOR_SHA256 = (
    "8cc04030df779e573950c4d1ad00b480368444439af3cc4ec97f62624c6c76c3"
)
ROOT_VECTOR_SHA256 = (
    "36e5c9045b5d7ffb931c3dc145d790b1965c18829757bf9b8ca347ed00caae19"
)
FRONTIER_VECTOR_SHA256 = (
    "5878c2596fecd2eeabe4205f688413f03488f006491440fd71e48e404d671838"
)
CROSS_EDGE_VECTOR_SHA256 = (
    "b0123d804c3e083bcf123cece476c79f555f949f053f33a5c73b18ab0b765698"
)

EXPECTED_PRODUCERS = (
    (
        "controller_state_1100",
        0x73690,
        "f7f704ff",
        "8bec6a7f6d2368e6791b434032f9ddf2a52460fb362c4b988c57bdb5242c5b4f",
        0x6B49C,
    ),
    (
        "enemy_preparation_primary",
        0x7425A,
        "10f0cdff",
        "d6d0920cff2e69678848152e5b2a504f58a1d5f3f54e9d0aee707e53a373d3db",
        0x851F8,
    ),
    (
        "enemy_preparation_secondary",
        0x7434E,
        "10f053ff",
        "3b211d366439e34a2b302b9d6666b2e041d3c92a97864d82ad3addc7c57dc5dd",
        0x851F8,
    ),
    (
        "action_resolution",
        0x74448,
        "f7f728f8",
        "b2c0f99824a26048f8e687520bd33cc5baa53a92cc70cd3f8d60901aee08502f",
        0x6B49C,
    ),
    (
        "controller_save_wrapper",
        0x74F2C,
        "f3f73afd",
        "30abff2b65f873193c56b1bbe531ac3f297ca66f4e43aabe3fde95a1b04b8e46",
        0x689A4,
    ),
)

SCOPE = {
    "frozen_v2_v3_and_proven_roots_v1_baseline_verified": True,
    "baseline_entries_treated_as_opaque": True,
    "fixed_direct_producer_denominator_complete": True,
    "direct_call_target_roots_only": True,
    "new_root_direct_cfg_traversal_performed": True,
    "baseline_bytes_duplicated": False,
    "indirect_target_resolution_complete": False,
    "global_direct_call_root_denominator_complete": False,
    "global_function_entry_denominator_complete": False,
    "runtime_reachability_complete": False,
}

LIMITATIONS = [
    "Only three roots selected by five fixed direct Thumb BL producers are traversed.",
    "The frozen v2, v3, and proven-roots-v1 instruction entries are opaque stop targets.",
    "Twenty-seven indirect PC targets and one unsupported instruction remain frontiers.",
    "Static direct-call reachability does not prove natural gameplay reachability.",
]


def _decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _producer_records() -> list[dict[str, Any]]:
    return [
        {
            "producer_id": producer_id,
            "file_offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}",
            "raw_hex": raw_hex,
            "bytes_sha256": digest,
            "target_file_offset": target,
            "target_gba_address": f"0x{ROM_BASE + target:08X}",
        }
        for producer_id, offset, raw_hex, digest, target in EXPECTED_PRODUCERS
    ]


def _producer_denominator(root: Path, rom: bytes) -> dict[str, Any]:
    evidence = {
        CONTROLLER_EVIDENCE_PATH: CONTROLLER_EVIDENCE_SHA256,
        V2_VERIFIER_PATH: V2_VERIFIER_SHA256,
        V3_VERIFIER_PATH: V3_VERIFIER_SHA256,
        V1_VERIFIER_PATH: V1_VERIFIER_SHA256,
    }
    for relative, digest in evidence.items():
        if _sha(_safe_file(root, relative).read_bytes()) != digest:
            raise ValueError(f"source evidence identity changed: {relative}")
    target_addresses = {ROM_BASE + spec[4] for spec in EXPECTED_PRODUCERS}
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_thumb_bl(ROM_BASE + offset, first, second)
        if target in target_addresses:
            actual.append((offset, target - ROM_BASE))
    expected = [(spec[1], spec[4]) for spec in EXPECTED_PRODUCERS]
    if actual != expected:
        raise ValueError("independent direct-call producer denominator changed")
    producers = _producer_records()
    for producer in producers:
        raw = rom[producer["file_offset"] : producer["file_offset"] + 4]
        if raw.hex() != producer["raw_hex"] or _sha(raw) != producer["bytes_sha256"]:
            raise ValueError("independent direct-call producer bytes changed")
    denominator = _canonical_sha(producers)
    if denominator != PRODUCER_VECTOR_SHA256:
        raise ValueError("independent producer canonical denominator changed")
    start, end = CONTROLLER_RANGE
    if _sha(rom[start:end]) != CONTROLLER_SHA256:
        raise ValueError("independent controller context changed")
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "targets": [0x689A4, 0x6B49C, 0x851F8],
            "matching_producer_count": 5,
        },
        "producers": producers,
        "denominator_sha256": denominator,
        "context": {
            "controller_range": list(CONTROLLER_RANGE),
            "controller_sha256": CONTROLLER_SHA256,
            "controller_evidence": {
                "path": CONTROLLER_EVIDENCE_PATH.as_posix(),
                "sha256": CONTROLLER_EVIDENCE_SHA256,
            },
        },
    }


def _root_seeds(rom: bytes) -> list[dict[str, Any]]:
    specs = (
        (
            "root-thumb-0689a4",
            0x689A4,
            "70b50023",
            "e8721d0de19871efcb42bed7100a1d3da0c24289e762e9e8d543571c7eefbd4c",
            ("controller_save_wrapper",),
        ),
        (
            "root-thumb-06b49c",
            0x6B49C,
            "f0b55746",
            "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb",
            ("controller_state_1100", "action_resolution"),
        ),
        (
            "root-thumb-0851f8",
            0x851F8,
            "f0b55746",
            "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb",
            ("enemy_preparation_primary", "enemy_preparation_secondary"),
        ),
    )
    roots = []
    for root_id, offset, raw_hex, digest, sources in specs:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError("independent direct-call root entry changed")
        roots.append(
            {
                "root_id": root_id,
                "mode": "thumb",
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "entry_size": 4,
                "entry_sha256": digest,
                "sources": [{"producer_id": source} for source in sources],
            }
        )
    if _canonical_sha(roots) != ROOT_VECTOR_SHA256:
        raise ValueError("independent root canonical denominator changed")
    return roots


def _load_bound_json(
    root: Path, relative: Path, *, size: int | None, digest: str
) -> dict[str, Any]:
    raw = _safe_file(root, relative).read_bytes()
    if (size is not None and len(raw) != size) or _sha(raw) != digest:
        raise ValueError(f"frozen CFG artifact identity changed: {relative}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("frozen CFG artifact is not an object")
    return payload


def _baseline_contract(root: Path, rom: bytes) -> dict[str, dict[str, Any]]:
    v3_report = verify_rom_cfg_inventory_v3(root, root / V3_ARTIFACT)
    if v3_report != {
        "schema": "rom-cfg-inventory-verification-v3",
        "verified": True,
        "resolved_frontier_count": 29,
        "new_entry_seed_count": 101,
        "independently_rebuilt_instruction_count": 4_698,
        "decoded_basic_block_count": 891,
        "reachable_instruction_bytes": 9_902,
        "frontier_count": 16,
        "control_flow_oracle": "armv4t-raw-encoding",
        "errors": [],
    }:
        raise ValueError("independent frozen v3 verification failed")
    v1_report = verify_rom_cfg_proven_roots(root, root / V1_ARTIFACT)
    if v1_report != {
        "schema": "rom-cfg-proven-roots-verification-v1",
        "verified": True,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": 6_166,
        "root_count": 2,
        "decoded_instruction_count": 6_166,
        "decoded_basic_block_count": 1_203,
        "reachable_instruction_bytes": 12_966,
        "frontier_count": 28,
        "baseline_cross_edge_count": 259,
        "errors": [],
    }:
        raise ValueError("independent frozen proven-roots-v1 verification failed")
    specs = {
        "v2": (
            V2_ARTIFACT / V2_PAYLOAD_NAME,
            V2_PAYLOAD_SIZE,
            V2_PAYLOAD_SHA256,
            V2_ARTIFACT / "manifest.json",
            V2_MANIFEST_SHA256,
        ),
        "v3": (
            V3_ARTIFACT / V3_PAYLOAD_NAME,
            V3_PAYLOAD_SIZE,
            V3_PAYLOAD_SHA256,
            V3_ARTIFACT / "manifest.json",
            V3_MANIFEST_SHA256,
        ),
        "proven_roots_v1": (
            V1_ARTIFACT / V1_PAYLOAD_NAME,
            V1_PAYLOAD_SIZE,
            V1_PAYLOAD_SHA256,
            V1_ARTIFACT / "manifest.json",
            V1_MANIFEST_SHA256,
        ),
    }
    result = {}
    for label, (payload_path, size, payload_sha, manifest_path, manifest_sha) in specs.items():
        result[label] = _load_bound_json(
            root, payload_path, size=size, digest=payload_sha
        )
        _load_bound_json(root, manifest_path, size=None, digest=manifest_sha)
    expected_rom = {
        "path": ROM_PATH.as_posix(),
        "size": len(rom),
        "sha256": ROM_SHA256,
    }
    if (
        result["v2"].get("schema") != V2_SCHEMA
        or result["v2"].get("rom") != expected_rom
        or result["v2"].get("graph_denominator_sha256") != V2_GRAPH_SHA256
        or result["v3"].get("schema") != V3_SCHEMA
        or result["v3"].get("rom") != expected_rom
        or result["v3"].get("graph_denominator_sha256") != V3_GRAPH_SHA256
        or result["proven_roots_v1"].get("schema") != V1_SCHEMA
        or result["proven_roots_v1"].get("rom") != expected_rom
        or result["proven_roots_v1"].get("graph_denominator_sha256")
        != V1_GRAPH_SHA256
    ):
        raise ValueError("independent frozen baseline contract changed")
    return result


def _baseline_record(payload: dict[str, Any], label: str) -> dict[str, Any]:
    if label == "v2":
        identity = (
            V2_ARTIFACT,
            V2_SCHEMA,
            V2_MANIFEST_SHA256,
            V2_PAYLOAD_NAME,
            V2_PAYLOAD_SIZE,
            V2_PAYLOAD_SHA256,
            V2_VERIFIER_PATH,
            V2_VERIFIER_SHA256,
            V2_GRAPH_SHA256,
        )
        summary = payload["summary"]
    elif label == "v3":
        identity = (
            V3_ARTIFACT,
            V3_SCHEMA,
            V3_MANIFEST_SHA256,
            V3_PAYLOAD_NAME,
            V3_PAYLOAD_SIZE,
            V3_PAYLOAD_SHA256,
            V3_VERIFIER_PATH,
            V3_VERIFIER_SHA256,
            V3_GRAPH_SHA256,
        )
        summary = payload["combined_summary"]
    else:
        identity = (
            V1_ARTIFACT,
            V1_SCHEMA,
            V1_MANIFEST_SHA256,
            V1_PAYLOAD_NAME,
            V1_PAYLOAD_SIZE,
            V1_PAYLOAD_SHA256,
            V1_VERIFIER_PATH,
            V1_VERIFIER_SHA256,
            V1_GRAPH_SHA256,
        )
        summary = payload["extension"]["summary"]
    path, schema, manifest_sha, name, size, sha, verifier, verifier_sha, graph = identity
    return {
        "path": path.as_posix(),
        "schema": schema,
        "manifest_sha256": manifest_sha,
        "payload_file": name,
        "payload_size": size,
        "payload_sha256": sha,
        "verifier_path": verifier.as_posix(),
        "verifier_sha256": verifier_sha,
        "graph_denominator_sha256": graph,
        "summary": summary,
    }


def _entry_order(item: tuple[str, int]) -> tuple[int, int, str]:
    return item[1], 0 if item[0] == "arm" else 1, item[0]


def _occupied_bytes(entries: dict[tuple[str, int], dict[str, Any]]) -> set[int]:
    return {
        byte
        for (_, offset), decoded in entries.items()
        for byte in range(offset, offset + decoded["size"])
    }


def _owner_map(
    blocks: list[dict[str, Any]],
    entries: dict[tuple[str, int], dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
    owner = {}
    for block in blocks:
        mode = block["mode"]
        offset, end = block["range"]
        while offset < end:
            key = (mode, offset)
            decoded = entries.get(key)
            if decoded is None or key in owner:
                raise ValueError("independent baseline ownership changed")
            owner[key] = block
            offset += decoded["size"]
        if offset != end:
            raise ValueError("independent baseline block boundary changed")
    if set(owner) != set(entries):
        raise ValueError("independent baseline entry ownership changed")
    return owner


def _baseline_entries(
    rom: bytes, baseline: dict[str, dict[str, Any]]
) -> tuple[
    dict[str, dict[tuple[str, int], dict[str, Any]]],
    dict[str, dict[tuple[str, int], dict[str, Any]]],
]:
    blocks = {
        "v2": baseline["v2"]["blocks"],
        "v3": baseline["v3"]["extension"]["blocks"],
        "proven_roots_v1": baseline["proven_roots_v1"]["extension"]["blocks"],
    }
    entries = {}
    owners = {}
    for label, records in blocks.items():
        _, _, _, entries[label] = _verify_blocks(rom, records)
        owners[label] = _owner_map(records, entries[label])
    if {label: len(value) for label, value in entries.items()} != {
        "v2": 40_872,
        "v3": 4_698,
        "proven_roots_v1": 6_166,
    }:
        raise ValueError("independent frozen instruction denominator changed")
    seen = set()
    for label, value in entries.items():
        occupied = _occupied_bytes(value)
        if seen & occupied:
            raise ValueError(f"independent baseline bytes overlap at {label}")
        seen.update(occupied)
    return entries, owners


def _assert_nonoverlapping_entries(
    entries: dict[tuple[str, int], dict[str, Any]]
) -> None:
    for mode in ("arm", "thumb"):
        previous_end = -1
        for entry_mode, offset in sorted(entries, key=_entry_order):
            if entry_mode != mode:
                continue
            if offset < previous_end:
                raise ValueError("independent decoded entries overlap")
            previous_end = offset + entries[(entry_mode, offset)]["size"]


def _rebuild_delta(
    rom: bytes,
    roots: list[dict[str, Any]],
    baseline_entries: dict[str, dict[tuple[str, int], dict[str, Any]]],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    list[tuple[tuple[str, int], str, str, tuple[str, int]]],
]:
    occupied = set().union(
        *(_occupied_bytes(value) for value in baseline_entries.values())
    )
    pending = []
    scheduled = set()
    for root in roots:
        item = (root["mode"], root["file_offset"])
        if any(item in value for value in baseline_entries.values()) or item[1] in occupied:
            raise ValueError("independent root overlaps frozen baseline")
        heapq.heappush(pending, _entry_order(item))
        scheduled.add(item)
    entries = {}
    rejected = set()
    crosses = []
    scheduled_limit = len(scheduled) + 2 * MAX_INSTRUCTION_COUNT
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in entries or item in rejected:
            continue
        if offset in occupied:
            raise ValueError("independent worklist entered baseline byte")
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            rejected.add(item)
            continue
        if any(byte in occupied for byte in range(offset, offset + decoded["size"])):
            raise ValueError("independent instruction overlaps baseline bytes")
        if len(entries) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("independent instruction budget exhausted")
        entries[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            matched = [
                label for label, value in baseline_entries.items() if target in value
            ]
            if len(matched) > 1:
                raise ValueError("independent baseline target is ambiguous")
            if matched:
                crosses.append((item, edge["kind"], matched[0], target))
                continue
            if target[1] in occupied:
                raise ValueError("independent successor enters baseline instruction middle")
            if target not in scheduled:
                if len(scheduled) >= scheduled_limit:
                    raise ValueError("independent schedule budget exhausted")
                heapq.heappush(pending, _entry_order(target))
                scheduled.add(target)
    _assert_nonoverlapping_entries(entries)
    return entries, crosses


def _simple_cross_vector(
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]],
) -> list[dict[str, Any]]:
    result = [
        {
            "source": {"mode": source[0], "file_offset": source[1]},
            "edge_kind": kind,
            "baseline": baseline,
            "target": {"mode": target[0], "file_offset": target[1]},
        }
        for source, kind, baseline, target in crosses
    ]
    result.sort(
        key=lambda item: (
            item["source"]["file_offset"],
            item["source"]["mode"],
            item["edge_kind"],
            item["target"]["file_offset"],
            item["target"]["mode"],
        )
    )
    return result


def _cross_records(
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]],
    source_blocks: dict[tuple[str, int], str],
    baseline_owners: dict[str, dict[tuple[str, int], dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    vector = _simple_cross_vector(crosses)
    records = []
    for item in vector:
        source = (item["source"]["mode"], item["source"]["file_offset"])
        target = (item["target"]["mode"], item["target"]["file_offset"])
        owner = baseline_owners[item["baseline"]].get(target)
        if owner is None:
            raise ValueError("independent cross target has no baseline owner")
        records.append(
            {
                "source": {
                    "block_id": source_blocks[source],
                    "instruction_offset": source[1],
                    "edge_kind": item["edge_kind"],
                },
                "target": {
                    "baseline_artifact": item["baseline"],
                    "block_id": owner["id"],
                    "instruction_offset": target[1],
                    "mode": target[0],
                },
            }
        )
    return records, vector


def _expected_frontiers_and_crosses(
    rom: bytes,
    blocks: list[dict[str, Any]],
    decoded_last: list[dict[str, Any]],
    block_entries: dict[tuple[str, int], dict[str, Any]],
    instruction_entries: dict[tuple[str, int], dict[str, Any]],
    baseline_entries: dict[str, dict[tuple[str, int], dict[str, Any]]],
    baseline_owners: dict[str, dict[tuple[str, int], dict[str, Any]]],
    roots: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    occupied = set().union(
        *(_occupied_bytes(value) for value in baseline_entries.values())
    )
    frontier_records = []
    crosses = []
    source_blocks = {}
    for block, decoded in zip(blocks, decoded_last, strict=True):
        expected_successors = []
        source = (decoded["mode"], decoded["file_offset"])
        source_blocks[source] = block["id"]
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            target_block = block_entries.get(target)
            if target_block is not None:
                expected_successors.append({**edge, "block_id": target_block["id"]})
                continue
            matched = [
                label for label, value in baseline_entries.items() if target in value
            ]
            if len(matched) > 1:
                raise ValueError("independent artifact baseline target is ambiguous")
            if matched:
                crosses.append((source, edge["kind"], matched[0], target))
                continue
            if target[1] in occupied:
                raise ValueError("independent artifact successor enters baseline middle")
            if target in instruction_entries:
                raise ValueError("independent successor is not a block start")
            rejected = _decode(rom, target[1], target[0])
            if rejected["accepted"]:
                raise ValueError("independent artifact omits accepted successor")
            frontier_records.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": source[1],
                        "edge_kind": edge["kind"],
                    },
                    "reason": rejected["frontier_reason"],
                    "target": {"mode": target[0], "file_offset": target[1]},
                }
            )
        if block.get("successors") != expected_successors:
            raise ValueError(f"independent block successors changed: {block['id']}")
        for frontier in decoded["frontiers"]:
            frontier_records.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": source[1],
                    },
                    **frontier,
                }
            )
    for root in roots:
        key = (root["mode"], root["file_offset"])
        if key in block_entries:
            continue
        rejected = _decode(rom, key[1], key[0])
        if rejected["accepted"]:
            raise ValueError("independent root is not a block start")
        frontier_records.append(
            {
                "source": {"kind": "root", "root_id": root["root_id"]},
                "reason": rejected["frontier_reason"],
                "target": {"mode": key[0], "file_offset": key[1]},
            }
        )
    frontier_records.sort(
        key=lambda item: json.dumps(
            item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    frontiers = [
        {"id": f"frontier-{index:06d}", **record}
        for index, record in enumerate(frontier_records)
    ]
    cross_records, cross_vector = _cross_records(
        crosses, source_blocks, baseline_owners
    )
    return frontiers, cross_records, cross_vector


def _extension_summary(
    blocks: list[dict[str, Any]], frontiers: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": sum(block["instruction_count"] for block in blocks),
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(
            sorted(Counter(item["reason"] for item in frontiers).items())
        ),
        "reachable_instruction_bytes": _union_bytes(
            [tuple(block["range"]) for block in blocks]
        ),
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            _safe_file(root, "tools/export_rom_cfg_proven_roots_v2.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            _safe_file(root, "tools/verify_rom_cfg_proven_roots_v2.py").read_bytes()
        ),
        "test_sha256": _sha(
            _safe_file(root, "tests/test_export_rom_cfg_proven_roots_v2.py").read_bytes()
        ),
    }


def verify_rom_cfg_proven_roots_v2(
    root: Path,
    artifact_dir: Path,
    *,
    allow_implementation_drift: bool = False,
) -> dict[str, Any]:
    errors = []
    rebuilt_count = 0
    summary: dict[str, Any] = {}
    root_count = 0
    cross_count = 0
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        resolved = artifact.resolve(strict=True)
        if resolved != artifact or not artifact.is_dir():
            raise ValueError("CFG proven-root v2 artifact uses a symlink")
        members = list(artifact.iterdir())
        if (
            {member.name for member in members} != {"manifest.json", PAYLOAD_NAME}
            or any(member.is_symlink() or not member.is_file() for member in members)
        ):
            raise ValueError("CFG proven-root v2 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        producers = _producer_denominator(root, rom)
        roots = _root_seeds(rom)
        baseline = _baseline_contract(root, rom)
        baseline_entries, baseline_owners = _baseline_entries(rom, baseline)
        rebuilt_entries, rebuilt_crosses = _rebuild_delta(
            rom, roots, baseline_entries
        )
        rebuilt_count = len(rebuilt_entries)

        payload_path = artifact / PAYLOAD_NAME
        payload_raw = payload_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        frozen_baseline = {
            label: _baseline_record(value, label)
            for label, value in baseline.items()
        }
        expected_decoder = _decoder_identity(root)
        expected_limits = {
            "max_instruction_count": MAX_INSTRUCTION_COUNT,
            "max_basic_block_instruction_count": MAX_BLOCK_INSTRUCTION_COUNT,
            "decode_window_bytes": 4,
        }
        if set(payload) != {
            "schema",
            "rom",
            "frozen_baseline",
            "decoder",
            "limits",
            "producer_denominator",
            "root_denominator_sha256",
            "roots",
            "extension",
            "graph_denominator_sha256",
            "implementation",
            "scope",
            "limitations",
        }:
            raise ValueError("CFG proven-root v2 top-level field set changed")
        if (
            payload.get("schema") != SCHEMA
            or payload.get("rom")
            != {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
            or payload.get("frozen_baseline") != frozen_baseline
            or payload.get("decoder") != expected_decoder
            or payload.get("limits") != expected_limits
            or payload.get("producer_denominator") != producers
            or payload.get("root_denominator_sha256") != ROOT_VECTOR_SHA256
            or payload.get("scope") != SCOPE
            or payload.get("limitations") != LIMITATIONS
        ):
            raise ValueError("CFG proven-root v2 top-level contract changed")

        extension = payload.get("extension")
        if not isinstance(extension, dict) or set(extension) != {
            "blocks",
            "frontiers",
            "frontier_denominator_sha256",
            "baseline_cross_edges",
            "cross_edge_denominator_sha256",
            "cross_edge_summary",
            "summary",
        }:
            raise ValueError("CFG proven-root v2 extension field set changed")
        blocks = extension["blocks"]
        decoded_last, block_entries, by_id, artifact_entries = _verify_blocks(
            rom, blocks
        )
        if set(artifact_entries) != set(rebuilt_entries):
            raise ValueError("CFG proven-root v2 closure differs from independent worklist")
        frontiers, cross_records, cross_vector = _expected_frontiers_and_crosses(
            rom,
            blocks,
            decoded_last,
            block_entries,
            artifact_entries,
            baseline_entries,
            baseline_owners,
            roots,
        )
        if _simple_cross_vector(rebuilt_crosses) != cross_vector:
            raise ValueError("CFG proven-root v2 cross-edge worklists disagree")
        summary = _extension_summary(blocks, frontiers)
        expected_summary = {
            "decoded_basic_block_count": 835,
            "decoded_instruction_count": 4_809,
            "frontier_count": 28,
            "frontier_reasons": {
                "indirect_pc_target": 27,
                "unsupported_armv4t_instruction": 1,
            },
            "reachable_instruction_bytes": 9_876,
        }
        if summary != expected_summary:
            raise ValueError("CFG proven-root v2 summary changed")
        by_baseline = dict(
            sorted(Counter(item["baseline"] for item in cross_vector).items())
        )
        by_kind = dict(
            sorted(Counter(item["edge_kind"] for item in cross_vector).items())
        )
        cross_summary = {
            "count": len(cross_vector),
            "by_baseline": by_baseline,
            "by_kind": by_kind,
        }
        if len(cross_vector) != 82 or by_baseline != {"v2": 82}:
            raise ValueError("CFG proven-root v2 cross-edge denominator changed")
        frontier_sha = _canonical_sha(frontiers)
        cross_sha = _canonical_sha(cross_vector)
        if (
            frontier_sha != FRONTIER_VECTOR_SHA256
            or cross_sha != CROSS_EDGE_VECTOR_SHA256
            or by_kind != {"call_target": 82}
        ):
            raise ValueError("CFG proven-root v2 frozen frontier/cross vector changed")
        cross_count = len(cross_vector)
        expected_roots = _expected_roots(roots, block_entries, by_id, frontiers)
        root_count = len(expected_roots)
        expected_extension = {
            "blocks": blocks,
            "frontiers": frontiers,
            "frontier_denominator_sha256": frontier_sha,
            "baseline_cross_edges": cross_records,
            "cross_edge_denominator_sha256": cross_sha,
            "cross_edge_summary": cross_summary,
            "summary": summary,
        }
        if extension != expected_extension or payload.get("roots") != expected_roots:
            raise ValueError("CFG proven-root v2 frontier, cross-edge, or root changed")
        graph_sha = _canonical_sha(
            {
                "frozen_baseline": frozen_baseline,
                "producer_denominator": producers,
                "root_denominator_sha256": ROOT_VECTOR_SHA256,
                "roots": expected_roots,
                "extension": expected_extension,
                "scope": SCOPE,
            }
        )
        if payload.get("graph_denominator_sha256") != graph_sha:
            raise ValueError("CFG proven-root v2 graph denominator changed")
        expected_implementation = _implementation(root)
        artifact_implementation = payload.get("implementation")
        if allow_implementation_drift:
            if (
                not isinstance(artifact_implementation, dict)
                or set(artifact_implementation)
                != {"exporter_sha256", "verifier_sha256", "test_sha256"}
                or any(
                    not isinstance(value, str)
                    or len(value) != 64
                    or any(character not in "0123456789abcdef" for character in value)
                    for value in artifact_implementation.values()
                )
            ):
                raise ValueError("CFG proven-root v2 prior implementation identity is invalid")
        elif artifact_implementation != expected_implementation:
            raise ValueError("CFG proven-root v2 implementation identity changed")
        expected_manifest = {
            "artifact_schema": SCHEMA,
            "rom": payload["rom"],
            "frozen_baseline": frozen_baseline,
            "decoder": expected_decoder,
            "limits": expected_limits,
            "producer_summary": {
                "count": 5,
                "denominator_sha256": PRODUCER_VECTOR_SHA256,
            },
            "root_count": 3,
            "root_denominator_sha256": ROOT_VECTOR_SHA256,
            "extension_summary": summary,
            "cross_edge_summary": cross_summary,
            "graph_denominator_sha256": graph_sha,
            "files": {
                PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}
            },
            "implementation": (
                artifact_implementation
                if allow_implementation_drift
                else expected_implementation
            ),
            "scope": SCOPE,
        }
        if manifest != expected_manifest:
            raise ValueError("CFG proven-root v2 promotion manifest changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": rebuilt_count,
        "root_count": root_count,
        "decoded_instruction_count": summary.get("decoded_instruction_count", 0),
        "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0),
        "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0),
        "frontier_count": summary.get("frontier_count", 0),
        "baseline_cross_edge_count": cross_count,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path("artifacts/rom-cfg-proven-roots-v2")
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_rom_cfg_proven_roots_v2(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
