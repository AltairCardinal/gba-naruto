#!/usr/bin/env python3
"""Export two direct-call-proven Thumb roots as an opaque v2+v3 CFG delta."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import shutil
import struct
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
    _decoder_identity,
    _decode_one,
    _frontier_records,
    _key,
    _reject_symlink_components,
    _replace_output_dir,
    _root_results,
    _safe_file,
    _union_bytes,
)
from tools.verify_rom_cfg_inventory_v3 import verify_rom_cfg_inventory_v3


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots.json"

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

CONTROLLER_EVIDENCE_PATH = Path("notes/battle-controller-states-20260723.json")
CONTROLLER_EVIDENCE_SHA256 = (
    "e0157597e6d7fddb94d036ddfa7a0d2e74fa232450ad08534cd868d6c6fe1336"
)
CONTROLLER_RANGE = (0x732B4, 0x75082)
CONTROLLER_SHA256 = (
    "30c8e021502cca16fc3f569bbb21dd04f78d20bcbb8e6196550164a0d56429ff"
)
SIDE_END_WINDOW = (0x7367C, 0x7368C)
SIDE_END_WINDOW_SHA256 = (
    "2a0c42d909bf81f19ce2246cc1ce386bc70e97bbcf95ab0842263770d4758622"
)
SIDE_END_VERIFIER_PATH = Path("tools/verify_battlefield_object_effect_chain.py")
SIDE_END_VERIFIER_SHA256 = (
    "1d6914dd5ab444d48b08ceaa5de43fe6c35cbd07c34f75b7f0178293843b5760"
)

PRODUCER_VECTOR_SHA256 = (
    "22e76a4dc425aaf8bdf13eef2f018508093f1c2f9a0ff28b31abdf22275fa5e7"
)
ROOT_VECTOR_SHA256 = (
    "523f8662596de2a8d42df3849906a5c93841ba8575a09e94d67bcee4ece914c0"
)
FRONTIER_VECTOR_SHA256 = (
    "e426acd731a1de146e09c4446420c89a76439fba22e9db7b5238e16c532f1512"
)
CROSS_EDGE_VECTOR_SHA256 = (
    "897401ae862b45444bd17792af2331def5be3b0a3426e67dde62c53cbae38739"
)

EXPECTED_PRODUCERS = (
    (
        "side_end_expiry",
        0x73688,
        "0ef072fa",
        "0994a9f3765e80a7638b955c9ba53b42bd657ae006a5262df72a0eb2be336300",
        0x81B70,
    ),
    (
        "movedone_primary",
        0x7443C,
        "fdf734ff",
        "1b8c31ed5218ca26fd2c873d860248f682ddd2d9595083215a79ef40b0a64822",
        0x722A8,
    ),
    (
        "movedone_secondary",
        0x74918,
        "fdf7c6fc",
        "50a57e3c6daf40c655678302a3d45296aff939bb35f99a7addd3cb9b3d4dcaf1",
        0x722A8,
    ),
)

SCOPE = {
    "frozen_v2_v3_baseline_verified": True,
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
    "Only two roots selected by three fixed direct Thumb BL producers are traversed.",
    "The frozen v2 and v3 instruction entries are opaque stop targets and are not reclassified.",
    "Twenty-seven indirect PC targets and one decode failure remain explicit frontiers.",
    "Static direct-call reachability does not prove natural gameplay or runtime reachability.",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_evidence_contract(root: Path) -> None:
    expected = {
        V2_VERIFIER_PATH: V2_VERIFIER_SHA256,
        V3_VERIFIER_PATH: V3_VERIFIER_SHA256,
        CONTROLLER_EVIDENCE_PATH: CONTROLLER_EVIDENCE_SHA256,
        SIDE_END_VERIFIER_PATH: SIDE_END_VERIFIER_SHA256,
    }
    for relative, digest in expected.items():
        if _sha(_safe_file(root, relative).read_bytes()) != digest:
            raise ValueError(f"source evidence identity changed: {relative}")


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
    side_start, side_end = SIDE_END_WINDOW
    if _sha(rom[side_start:side_end]) != SIDE_END_WINDOW_SHA256:
        raise ValueError("side-end producer context changed")
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "targets": [0x722A8, 0x81B70],
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
            "side_end_window": list(SIDE_END_WINDOW),
            "side_end_window_sha256": SIDE_END_WINDOW_SHA256,
            "side_end_verifier": {
                "path": SIDE_END_VERIFIER_PATH.as_posix(),
                "sha256": SIDE_END_VERIFIER_SHA256,
            },
        },
    }


def _root_seeds(rom: bytes) -> list[dict[str, Any]]:
    entry_sha = _sha(rom[0x722A8:0x722AC])
    if entry_sha != _sha(rom[0x81B70:0x81B74]) or entry_sha != (
        "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
    ):
        raise ValueError("direct-call root entry bytes changed")
    roots = [
        {
            "root_id": "root-thumb-0722a8",
            "mode": "thumb",
            "file_offset": 0x722A8,
            "gba_address": "0x080722A8",
            "entry_size": 4,
            "entry_sha256": entry_sha,
            "sources": [
                {"producer_id": "movedone_primary"},
                {"producer_id": "movedone_secondary"},
            ],
        },
        {
            "root_id": "root-thumb-081b70",
            "mode": "thumb",
            "file_offset": 0x81B70,
            "gba_address": "0x08081B70",
            "entry_size": 4,
            "entry_sha256": entry_sha,
            "sources": [{"producer_id": "side_end_expiry"}],
        },
    ]
    if _canonical_sha(roots) != ROOT_VECTOR_SHA256:
        raise ValueError("direct-call root canonical denominator changed")
    return roots


def _load_bound_json(
    root: Path, relative: Path, *, size: int | None, digest: str
) -> tuple[dict[str, Any], bytes]:
    raw = _safe_file(root, relative).read_bytes()
    if (size is not None and len(raw) != size) or _sha(raw) != digest:
        raise ValueError(f"frozen CFG artifact identity changed: {relative}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"frozen CFG artifact is not an object: {relative}")
    return payload, raw


def _baseline_contract(root: Path, rom: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    report = verify_rom_cfg_inventory_v3(root, root / V3_ARTIFACT)
    expected_report = {
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
    if report != expected_report:
        raise ValueError(f"frozen v3 CFG verification failed: {report}")
    v2, _ = _load_bound_json(
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
    v3, _ = _load_bound_json(
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
    if (
        v2.get("schema") != V2_SCHEMA
        or v2.get("rom")
        != {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        or v2.get("graph_denominator_sha256") != V2_GRAPH_SHA256
        or v3.get("schema") != V3_SCHEMA
        or v3.get("rom") != v2.get("rom")
        or v3.get("graph_denominator_sha256") != V3_GRAPH_SHA256
        or v3.get("base_cfg", {}).get("graph_denominator_sha256") != V2_GRAPH_SHA256
    ):
        raise ValueError("frozen v2/v3 CFG contract changed")
    return v2, v3


def _baseline_record(payload: dict[str, Any], *, version: str) -> dict[str, Any]:
    if version == "v2":
        return {
            "path": V2_ARTIFACT.as_posix(),
            "schema": V2_SCHEMA,
            "manifest_sha256": V2_MANIFEST_SHA256,
            "payload_file": V2_PAYLOAD_NAME,
            "payload_size": V2_PAYLOAD_SIZE,
            "payload_sha256": V2_PAYLOAD_SHA256,
            "verifier_path": V2_VERIFIER_PATH.as_posix(),
            "verifier_sha256": V2_VERIFIER_SHA256,
            "graph_denominator_sha256": V2_GRAPH_SHA256,
            "summary": payload["summary"],
        }
    return {
        "path": V3_ARTIFACT.as_posix(),
        "schema": V3_SCHEMA,
        "manifest_sha256": V3_MANIFEST_SHA256,
        "payload_file": V3_PAYLOAD_NAME,
        "payload_size": V3_PAYLOAD_SIZE,
        "payload_sha256": V3_PAYLOAD_SHA256,
        "verifier_path": V3_VERIFIER_PATH.as_posix(),
        "verifier_sha256": V3_VERIFIER_SHA256,
        "graph_denominator_sha256": V3_GRAPH_SHA256,
        "summary": payload["combined_summary"],
    }


def _nodes_from_blocks(
    rom: bytes, blocks: object, *, label: str
) -> tuple[dict[tuple[str, int], dict[str, Any]], dict[tuple[str, int], dict[str, Any]]]:
    if not isinstance(blocks, list) or not blocks:
        raise ValueError(f"{label} CFG blocks are missing")
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    owner: dict[tuple[str, int], dict[str, Any]] = {}
    for block in blocks:
        if not isinstance(block, dict) or block.get("mode") not in {"arm", "thumb"}:
            raise ValueError(f"{label} CFG block is invalid")
        mode = block["mode"]
        start, end = block.get("range", [-1, -1])
        if block.get("bytes_sha256") != _sha(rom[start:end]):
            raise ValueError(f"{label} CFG block bytes changed")
        offset = start
        count = 0
        while offset < end:
            node = _decode_one(rom, offset, mode)
            if not node["accepted"] or (mode, offset) in nodes:
                raise ValueError(f"{label} CFG instruction entry changed")
            nodes[(mode, offset)] = node
            owner[(mode, offset)] = block
            offset += node["size"]
            count += 1
        if offset != end or count != block.get("instruction_count"):
            raise ValueError(f"{label} CFG block denominator changed")
    return nodes, owner


def _occupied_bytes(nodes: dict[tuple[str, int], dict[str, Any]]) -> set[int]:
    return {
        byte
        for (_, offset), node in nodes.items()
        for byte in range(offset, offset + node["size"])
    }


def _traverse_delta(
    rom: bytes,
    roots: list[dict[str, Any]],
    v2_nodes: dict[tuple[str, int], dict[str, Any]],
    v3_nodes: dict[tuple[str, int], dict[str, Any]],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
    list[tuple[tuple[str, int], str, str, tuple[str, int]]],
]:
    if set(v2_nodes) & set(v3_nodes):
        raise ValueError("frozen v2 and v3 instruction entries overlap")
    baseline_occupied = _occupied_bytes({**v2_nodes, **v3_nodes})
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for root in roots:
        item = (root["mode"], root["file_offset"])
        if item in v2_nodes or item in v3_nodes or item[1] in baseline_occupied:
            raise ValueError("direct-call root overlaps the frozen CFG baseline")
        heapq.heappush(pending, _key(*item))
        scheduled.add(item)
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    incoming: dict[tuple[str, int], list[tuple[tuple[str, int], str]]] = defaultdict(list)
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
            if target in v2_nodes:
                crosses.append((item, edge["kind"], "v2", target))
                continue
            if target in v3_nodes:
                crosses.append((item, edge["kind"], "v3", target))
                continue
            if target[1] in baseline_occupied:
                raise ValueError("new CFG successor targets the middle of a baseline instruction")
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    return nodes, rejected, incoming, crosses


def _block_reference(
    owner: dict[tuple[str, int], dict[str, Any]], target: tuple[str, int], label: str
) -> dict[str, Any]:
    block = owner.get(target)
    if block is None:
        raise ValueError(f"{label} cross-edge target has no owning block")
    return {
        "baseline_artifact": label,
        "block_id": block["id"],
        "instruction_offset": target[1],
        "mode": target[0],
    }


def _cross_edge_records(
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]],
    node_to_block: dict[tuple[str, int], str],
    v2_owner: dict[tuple[str, int], dict[str, Any]],
    v3_owner: dict[tuple[str, int], dict[str, Any]],
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
        records.append(
            {
                "source": {
                    "block_id": node_to_block[source],
                    "instruction_offset": source[1],
                    "edge_kind": item["edge_kind"],
                },
                "target": _block_reference(
                    v2_owner if item["baseline"] == "v2" else v3_owner,
                    target,
                    item["baseline"],
                ),
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
        "frontier_reasons": dict(sorted(Counter(x["reason"] for x in frontiers).items())),
        "reachable_instruction_bytes": _union_bytes(
            [(offset, offset + node["size"]) for (_, offset), node in nodes.items()]
        ),
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            _safe_file(root, "tools/export_rom_cfg_proven_roots.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            _safe_file(root, "tools/verify_rom_cfg_proven_roots.py").read_bytes()
        ),
        "test_sha256": _sha(
            _safe_file(root, "tests/test_export_rom_cfg_proven_roots.py").read_bytes()
        ),
    }


def build_cfg_proven_roots_payload(
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
    v2, v3 = _baseline_contract(root, rom)
    v2_nodes, v2_owner = _nodes_from_blocks(rom, v2["blocks"], label="v2")
    v3_nodes, v3_owner = _nodes_from_blocks(
        rom, v3["extension"]["blocks"], label="v3"
    )
    if len(v2_nodes) != 40_872 or len(v3_nodes) != 4_698:
        raise ValueError("frozen v2/v3 instruction denominator changed")
    nodes, rejected, incoming, crosses = _traverse_delta(
        rom, roots, v2_nodes, v3_nodes
    )
    _assert_nonoverlapping_nodes(nodes)
    blocks, node_to_block = _build_blocks(
        rom, nodes, {(root["mode"], root["file_offset"]) for root in roots}
    )
    frontiers = _frontier_records(nodes, rejected, incoming, roots, node_to_block)
    root_results = _root_results(roots, nodes, frontiers, node_to_block)
    cross_records, cross_vector = _cross_edge_records(
        crosses, node_to_block, v2_owner, v3_owner
    )
    extension_summary = _extension_summary(nodes, blocks, frontiers)
    expected_summary = {
        "decoded_basic_block_count": 1_203,
        "decoded_instruction_count": 6_166,
        "frontier_count": 28,
        "frontier_reasons": {"decode_failure": 1, "indirect_pc_target": 27},
        "reachable_instruction_bytes": 12_966,
    }
    if extension_summary != expected_summary:
        raise ValueError(f"direct-call CFG extension denominator changed: {extension_summary}")
    frontier_sha = _canonical_sha(frontiers)
    cross_sha = _canonical_sha(cross_vector)
    if frontier_sha != FRONTIER_VECTOR_SHA256 or cross_sha != CROSS_EDGE_VECTOR_SHA256:
        raise ValueError("direct-call CFG frontier or cross-edge denominator changed")
    by_baseline = dict(sorted(Counter(x["baseline"] for x in cross_vector).items()))
    by_kind = dict(sorted(Counter(x["edge_kind"] for x in cross_vector).items()))
    if by_baseline != {"v2": 256, "v3": 3} or by_kind != {
        "branch_target": 3,
        "call_target": 256,
    }:
        raise ValueError("direct-call CFG cross-edge classification changed")
    frozen_baseline = {
        "v2": _baseline_record(v2, version="v2"),
        "v3": _baseline_record(v3, version="v3"),
    }
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
        "summary": extension_summary,
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
        raise ValueError("CFG proven-root output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("CFG proven-root output is not a directory")
    members = list(target.iterdir())
    if not members:
        return target
    if (
        {member.name for member in members} != {"manifest.json", PAYLOAD_NAME}
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError("existing directory is not a replaceable CFG proven-root artifact")
    from tools.verify_rom_cfg_proven_roots import verify_rom_cfg_proven_roots

    report = verify_rom_cfg_proven_roots(root, target)
    if not report.get("verified"):
        raise ValueError(
            "existing directory is not a replaceable CFG proven-root artifact: "
            f"{report.get('errors', [])}"
        )
    return target


def export_rom_cfg_proven_roots(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output_dir = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_payload(root)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-", dir=output_dir.parent)
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
        "--output-dir", type=Path, default=Path("artifacts/rom-cfg-proven-roots-v1")
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    manifest = export_rom_cfg_proven_roots(args.root, output)
    print(json.dumps(manifest["extension_summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
