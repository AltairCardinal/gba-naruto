#!/usr/bin/env python3
"""Export the second fixed-direct-call-proven Thumb CFG root batch."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
import shutil
import struct
from pathlib import Path
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.export_rom_cfg_inventory import (
    MAX_BLOCK_INSTRUCTION_COUNT,
    MAX_INSTRUCTION_COUNT,
    ROM_PATH,
    ROM_SHA256,
    _assert_nonoverlapping_nodes,
    _build_blocks,
    _canonical_json,
    _canonical_sha,
    _decode_one,
    _decoder_identity,
    _frontier_records,
    _key,
    _root_results,
    _reject_symlink_components,
    _replace_output_dir,
    _safe_file,
    _union_bytes,
)
from tools.export_rom_cfg_proven_roots import _nodes_from_blocks
from tools.verify_rom_cfg_inventory_v3 import verify_rom_cfg_inventory_v3
from tools.verify_rom_cfg_proven_roots import verify_rom_cfg_proven_roots


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v2"
PAYLOAD_NAME = "rom-cfg-proven-roots-v2.json"

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


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    target_addresses = {ROM_BASE + spec[4] for spec in EXPECTED_PRODUCERS}
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_thumb_bl(ROM_BASE + offset, first, second)
        if target in target_addresses:
            actual.append((offset, target - ROM_BASE))
    expected_pairs = [(spec[1], spec[4]) for spec in EXPECTED_PRODUCERS]
    if actual != expected_pairs:
        raise ValueError(
            f"direct-call producer denominator changed: {actual!r} != {expected_pairs!r}"
        )
    producers = _producer_records()
    for producer in producers:
        offset = producer["file_offset"]
        raw = rom[offset : offset + 4]
        if raw.hex() != producer["raw_hex"] or _sha(raw) != producer["bytes_sha256"]:
            raise ValueError(f"direct-call producer bytes changed at 0x{offset:06X}")
    denominator_sha256 = _canonical_sha(producers)
    if denominator_sha256 != PRODUCER_VECTOR_SHA256:
        raise ValueError("direct-call producer canonical denominator changed")
    start, end = CONTROLLER_RANGE
    if _sha(rom[start:end]) != CONTROLLER_SHA256:
        raise ValueError("battle-controller producer context changed")
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "targets": [0x689A4, 0x6B49C, 0x851F8],
            "matching_producer_count": len(producers),
        },
        "producers": producers,
        "denominator_sha256": denominator_sha256,
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
            raise ValueError(f"direct-call root entry bytes changed at 0x{offset:06X}")
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
        raise ValueError("direct-call root canonical denominator changed")
    return roots


def _source_evidence_contract(root: Path) -> None:
    expected = {
        CONTROLLER_EVIDENCE_PATH: CONTROLLER_EVIDENCE_SHA256,
        V2_VERIFIER_PATH: V2_VERIFIER_SHA256,
        V3_VERIFIER_PATH: V3_VERIFIER_SHA256,
        V1_VERIFIER_PATH: V1_VERIFIER_SHA256,
    }
    for relative, digest in expected.items():
        if _sha(_safe_file(root, relative).read_bytes()) != digest:
            raise ValueError(f"source evidence identity changed: {relative}")


def _load_bound_json(
    root: Path, relative: Path, *, size: int | None, digest: str
) -> dict[str, Any]:
    raw = _safe_file(root, relative).read_bytes()
    if (size is not None and len(raw) != size) or _sha(raw) != digest:
        raise ValueError(f"frozen CFG artifact identity changed: {relative}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"frozen CFG artifact is not an object: {relative}")
    return payload


def _baseline_contract(root: Path, rom: bytes) -> dict[str, dict[str, Any]]:
    v3_report = verify_rom_cfg_inventory_v3(root, root / V3_ARTIFACT)
    expected_v3_report = {
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
    }
    if v3_report != expected_v3_report:
        raise ValueError(f"frozen v3 CFG verification failed: {v3_report}")
    v1_report = verify_rom_cfg_proven_roots(root, root / V1_ARTIFACT)
    expected_v1_report = {
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
    }
    if v1_report != expected_v1_report:
        raise ValueError(f"frozen proven-roots-v1 verification failed: {v1_report}")

    v2 = _load_bound_json(
        root,
        V2_ARTIFACT / V2_PAYLOAD_NAME,
        size=V2_PAYLOAD_SIZE,
        digest=V2_PAYLOAD_SHA256,
    )
    _load_bound_json(
        root,
        V2_ARTIFACT / "manifest.json",
        size=None,
        digest=V2_MANIFEST_SHA256,
    )
    v3 = _load_bound_json(
        root,
        V3_ARTIFACT / V3_PAYLOAD_NAME,
        size=V3_PAYLOAD_SIZE,
        digest=V3_PAYLOAD_SHA256,
    )
    _load_bound_json(
        root,
        V3_ARTIFACT / "manifest.json",
        size=None,
        digest=V3_MANIFEST_SHA256,
    )
    v1 = _load_bound_json(
        root,
        V1_ARTIFACT / V1_PAYLOAD_NAME,
        size=V1_PAYLOAD_SIZE,
        digest=V1_PAYLOAD_SHA256,
    )
    _load_bound_json(
        root,
        V1_ARTIFACT / "manifest.json",
        size=None,
        digest=V1_MANIFEST_SHA256,
    )
    expected_rom = {
        "path": ROM_PATH.as_posix(),
        "size": len(rom),
        "sha256": ROM_SHA256,
    }
    if (
        v2.get("schema") != V2_SCHEMA
        or v2.get("rom") != expected_rom
        or v2.get("graph_denominator_sha256") != V2_GRAPH_SHA256
        or v3.get("schema") != V3_SCHEMA
        or v3.get("rom") != expected_rom
        or v3.get("graph_denominator_sha256") != V3_GRAPH_SHA256
        or v1.get("schema") != V1_SCHEMA
        or v1.get("rom") != expected_rom
        or v1.get("graph_denominator_sha256") != V1_GRAPH_SHA256
    ):
        raise ValueError("frozen CFG baseline contract changed")
    return {"v2": v2, "v3": v3, "proven_roots_v1": v1}


def _baseline_record(payload: dict[str, Any], *, label: str) -> dict[str, Any]:
    specs = {
        "v2": (
            V2_ARTIFACT,
            V2_SCHEMA,
            V2_MANIFEST_SHA256,
            V2_PAYLOAD_NAME,
            V2_PAYLOAD_SIZE,
            V2_PAYLOAD_SHA256,
            V2_VERIFIER_PATH,
            V2_VERIFIER_SHA256,
            V2_GRAPH_SHA256,
            "summary",
        ),
        "v3": (
            V3_ARTIFACT,
            V3_SCHEMA,
            V3_MANIFEST_SHA256,
            V3_PAYLOAD_NAME,
            V3_PAYLOAD_SIZE,
            V3_PAYLOAD_SHA256,
            V3_VERIFIER_PATH,
            V3_VERIFIER_SHA256,
            V3_GRAPH_SHA256,
            "combined_summary",
        ),
        "proven_roots_v1": (
            V1_ARTIFACT,
            V1_SCHEMA,
            V1_MANIFEST_SHA256,
            V1_PAYLOAD_NAME,
            V1_PAYLOAD_SIZE,
            V1_PAYLOAD_SHA256,
            V1_VERIFIER_PATH,
            V1_VERIFIER_SHA256,
            V1_GRAPH_SHA256,
            "extension",
        ),
    }
    (
        path,
        schema,
        manifest_sha,
        payload_name,
        payload_size,
        payload_sha,
        verifier_path,
        verifier_sha,
        graph_sha,
        summary_key,
    ) = specs[label]
    summary = (
        payload["extension"]["summary"]
        if summary_key == "extension"
        else payload[summary_key]
    )
    return {
        "path": path.as_posix(),
        "schema": schema,
        "manifest_sha256": manifest_sha,
        "payload_file": payload_name,
        "payload_size": payload_size,
        "payload_sha256": payload_sha,
        "verifier_path": verifier_path.as_posix(),
        "verifier_sha256": verifier_sha,
        "graph_denominator_sha256": graph_sha,
        "summary": summary,
    }


def _occupied_bytes(nodes: dict[tuple[str, int], dict[str, Any]]) -> set[int]:
    return {
        byte
        for (_, offset), node in nodes.items()
        for byte in range(offset, offset + node["size"])
    }


def _baseline_nodes(
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
    nodes: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    owners: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    for label, records in blocks.items():
        nodes[label], owners[label] = _nodes_from_blocks(rom, records, label=label)
    expected_counts = {"v2": 40_872, "v3": 4_698, "proven_roots_v1": 6_166}
    if {label: len(records) for label, records in nodes.items()} != expected_counts:
        raise ValueError("frozen CFG instruction denominator changed")
    seen: set[int] = set()
    for label, records in nodes.items():
        occupied = _occupied_bytes(records)
        if seen & occupied:
            raise ValueError(f"frozen CFG baseline bytes overlap at {label}")
        seen.update(occupied)
    return nodes, owners


def _traverse_delta(
    rom: bytes,
    roots: list[dict[str, Any]],
    baseline_nodes: dict[str, dict[tuple[str, int], dict[str, Any]]],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
    list[tuple[tuple[str, int], str, str, tuple[str, int]]],
]:
    baseline_occupied = set().union(
        *(_occupied_bytes(records) for records in baseline_nodes.values())
    )
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for root in roots:
        item = (root["mode"], root["file_offset"])
        if any(item in records for records in baseline_nodes.values()):
            raise ValueError("direct-call root is already a frozen CFG entry")
        if item[1] in baseline_occupied:
            raise ValueError("direct-call root overlaps a frozen CFG baseline byte")
        heapq.heappush(pending, _key(*item))
        scheduled.add(item)
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    incoming: dict[tuple[str, int], list[tuple[tuple[str, int], str]]] = defaultdict(
        list
    )
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if offset in baseline_occupied:
            raise ValueError("new CFG traversal entered a frozen baseline byte")
        node = _decode_one(rom, offset, mode)
        if not node["accepted"]:
            rejected[item] = node
            continue
        if any(byte in baseline_occupied for byte in range(offset, offset + node["size"])):
            raise ValueError("new CFG instruction overlaps frozen baseline bytes")
        if len(nodes) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("direct-call CFG instruction budget exhausted")
        nodes[item] = node
        for edge in node["successors"]:
            target = (edge["mode"], edge["file_offset"])
            matched = [
                label for label, records in baseline_nodes.items() if target in records
            ]
            if len(matched) > 1:
                raise ValueError("CFG target is ambiguous across frozen baselines")
            if matched:
                crosses.append((item, edge["kind"], matched[0], target))
                continue
            if target[1] in baseline_occupied:
                raise ValueError("new CFG successor targets a baseline instruction middle")
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    return nodes, rejected, incoming, crosses


def _cross_edge_records(
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]],
    node_to_block: dict[tuple[str, int], str],
    baseline_owners: dict[str, dict[tuple[str, int], dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    simple = [
        {
            "source": {"mode": source[0], "file_offset": source[1]},
            "edge_kind": kind,
            "baseline": baseline,
            "target": {"mode": target[0], "file_offset": target[1]},
        }
        for source, kind, baseline, target in crosses
    ]
    simple.sort(
        key=lambda item: (
            item["source"]["file_offset"],
            item["source"]["mode"],
            item["edge_kind"],
            item["target"]["file_offset"],
            item["target"]["mode"],
        )
    )
    records = []
    for item in simple:
        source = (item["source"]["mode"], item["source"]["file_offset"])
        target = (item["target"]["mode"], item["target"]["file_offset"])
        owner = baseline_owners[item["baseline"]].get(target)
        if owner is None:
            raise ValueError("CFG cross-edge target has no owning baseline block")
        records.append(
            {
                "source": {
                    "block_id": node_to_block[source],
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
    return records, simple


def _extension_summary(
    nodes: dict[tuple[str, int], dict[str, Any]],
    blocks: list[dict[str, Any]],
    frontiers: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": len(nodes),
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(
            sorted(Counter(item["reason"] for item in frontiers).items())
        ),
        "reachable_instruction_bytes": _union_bytes(
            [(offset, offset + node["size"]) for (_, offset), node in nodes.items()]
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


def build_cfg_proven_roots_v2_payload(
    root: Path, rom: bytes | None = None
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    _source_evidence_contract(root)
    producers = _producer_denominator(rom)
    roots = _root_seeds(rom)
    baseline = _baseline_contract(root, rom)
    baseline_nodes, baseline_owners = _baseline_nodes(rom, baseline)
    nodes, rejected, incoming, crosses = _traverse_delta(
        rom, roots, baseline_nodes
    )
    _assert_nonoverlapping_nodes(nodes)
    blocks, node_to_block = _build_blocks(
        rom, nodes, {(item["mode"], item["file_offset"]) for item in roots}
    )
    frontiers = _frontier_records(nodes, rejected, incoming, roots, node_to_block)
    root_results = _root_results(roots, nodes, frontiers, node_to_block)
    cross_records, cross_vector = _cross_edge_records(
        crosses, node_to_block, baseline_owners
    )
    summary = _extension_summary(nodes, blocks, frontiers)
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
        raise ValueError(f"direct-call CFG extension denominator changed: {summary}")
    by_baseline = dict(sorted(Counter(item["baseline"] for item in cross_vector).items()))
    by_kind = dict(sorted(Counter(item["edge_kind"] for item in cross_vector).items()))
    if len(cross_vector) != 82 or by_baseline != {"v2": 82}:
        raise ValueError("direct-call CFG cross-edge denominator changed")
    frozen_baseline = {
        label: _baseline_record(payload, label=label)
        for label, payload in baseline.items()
    }
    frontier_sha = _canonical_sha(frontiers)
    cross_sha = _canonical_sha(cross_vector)
    if (
        frontier_sha != FRONTIER_VECTOR_SHA256
        or cross_sha != CROSS_EDGE_VECTOR_SHA256
    ):
        raise ValueError("direct-call CFG frontier or cross-edge denominator changed")
    if by_kind != {"call_target": 82}:
        raise ValueError("direct-call CFG cross-edge kind denominator changed")
    extension = {
        "blocks": blocks,
        "frontiers": frontiers,
        "frontier_denominator_sha256": frontier_sha,
        "baseline_cross_edges": cross_records,
        "cross_edge_denominator_sha256": cross_sha,
        "cross_edge_summary": {
            "count": len(cross_vector),
            "by_baseline": by_baseline,
            "by_kind": by_kind,
        },
        "summary": summary,
    }
    graph_sha = _canonical_sha(
        {
            "frozen_baseline": frozen_baseline,
            "producer_denominator": producers,
            "root_denominator_sha256": ROOT_VECTOR_SHA256,
            "roots": root_results,
            "extension": extension,
            "scope": SCOPE,
        }
    )
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "frozen_baseline": frozen_baseline,
        "decoder": _decoder_identity(root),
        "limits": {
            "max_instruction_count": MAX_INSTRUCTION_COUNT,
            "max_basic_block_instruction_count": MAX_BLOCK_INSTRUCTION_COUNT,
            "decode_window_bytes": 4,
        },
        "producer_denominator": producers,
        "root_denominator_sha256": ROOT_VECTOR_SHA256,
        "roots": root_results,
        "extension": extension,
        "graph_denominator_sha256": graph_sha,
        "implementation": _implementation(root),
        "scope": SCOPE,
        "limitations": LIMITATIONS,
    }


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("CFG proven-root v2 output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("CFG proven-root v2 output is not a directory")
    members = list(target.iterdir())
    if not members:
        return target
    if (
        {member.name for member in members} != {"manifest.json", PAYLOAD_NAME}
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError("existing directory is not a replaceable CFG proven-root v2 artifact")
    from tools.verify_rom_cfg_proven_roots_v2 import verify_rom_cfg_proven_roots_v2

    report = verify_rom_cfg_proven_roots_v2(
        root, target, allow_implementation_drift=True
    )
    if not report.get("verified"):
        raise ValueError(
            "existing directory is not a replaceable CFG proven-root v2 artifact: "
            f"{report.get('errors', [])}"
        )
    return target


def export_rom_cfg_proven_roots_v2(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output_dir = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_v2_payload(root)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-v2-", dir=output_dir.parent)
    )
    try:
        payload_raw = _canonical_json(payload)
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        manifest = {
            "artifact_schema": SCHEMA,
            "rom": payload["rom"],
            "frozen_baseline": payload["frozen_baseline"],
            "decoder": payload["decoder"],
            "limits": payload["limits"],
            "producer_summary": {
                "count": len(payload["producer_denominator"]["producers"]),
                "denominator_sha256": payload["producer_denominator"][
                    "denominator_sha256"
                ],
            },
            "root_count": len(payload["roots"]),
            "root_denominator_sha256": payload["root_denominator_sha256"],
            "extension_summary": payload["extension"]["summary"],
            "cross_edge_summary": payload["extension"]["cross_edge_summary"],
            "graph_denominator_sha256": payload["graph_denominator_sha256"],
            "files": {
                PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}
            },
            "implementation": payload["implementation"],
            "scope": SCOPE,
        }
        (temporary / "manifest.json").write_bytes(_canonical_json(manifest))
        _validate_output_dir(root, temporary)
        _replace_output_dir(output_dir, temporary)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/rom-cfg-proven-roots-v2")
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    manifest = export_rom_cfg_proven_roots_v2(args.root, output)
    print(json.dumps(manifest["extension_summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
