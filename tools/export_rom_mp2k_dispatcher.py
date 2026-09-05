#!/usr/bin/env python3
"""Build the candidate-only frozen MP2K dispatcher packet.

The packet is intentionally target limited.  Every accepted byte is bound to
the fixed ROM, coverage baseline, raw Thumb control-flow walk, table entries,
and the two independent initializer instructions described by CONTRACT.json.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import heapq
import json
import os
from pathlib import Path
import stat
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_RELATIVE = Path("build/experiments/active/mp2k-dispatcher-contract/codex-r1-20260829")
CONTRACT_PATH = EXPERIMENT_RELATIVE / "CONTRACT.json"
CONTRACT_SHA256 = "936f4fd2200a4ac6cbdc5641880f46585ed5722493cd6a4912632042058e154d"
SCHEMA = "rom-mp2k-dispatcher-v1"
VERIFY_SCHEMA = "rom-mp2k-dispatcher-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
BASE_ROM_SHA256 = ROM_SHA256
COVERAGE_SHA256 = "3926d1cd6e09c8b45b85cb33d0b2f77d83578ec71c17d61fa1282d863f220735"
COVERAGE_SUMMARY = {
    "claim_count": 14503,
    "classified_bytes": 6124499,
    "segment_count": 16614,
    "unknown_bytes": 166957,
}

PROMOTION_RANGES = [
    [638132, 638178],
    [638244, 638256],
    [638404, 638444],
    [638460, 638464],
]
PROMOTION_RANGE_SHA256 = [
    "d3a8d0298a139e1b02c709d08116eb3c55a835ccf69f6fc9a3957791632cc59b",
    "7d71c074f708e1abd395793f711907297dc09527cf3a9e050ce645540ba76911",
    "45103e5203193bee6f39a1533b917175c16d361b9e72bdbcdb04ec83b93eec4c",
    "48f5b6c8f55b1a8bac36a2ce2871ffc9e6e1068d808aade8c70a9afc40e2a4b0",
]
PROMOTION_UNION_RANGES = [list(interval) for interval in PROMOTION_RANGES]
RANGE_VECTOR_SHA256 = "f7621079a8d84ce92aeebf1855856f30c0d8e551aed692531139bd6dccb39171"
PACKED_SHA256 = "83f220623fff3f5effb8bf6cd21b7e7ce8d543ab660d7fa721b8632bd26b3bd5"
CODE_RANGES = [[638132, 638178], [638256, 638458], [638464, 638476]]
LITERAL_RANGES = [[638180, 638184], [638460, 638464]]
EXCLUDED_RANGES = [[638178, 638180], [638458, 638460]]
EXCLUDED_SHA256 = [
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
]

ROOTS = [
    {"id": "mp2k_dispatcher", "file_offset": 638132, "code_range": [638132, 638178]},
    {"id": "mp2k_dispatcher_handlers", "file_offset": 638256, "code_range": [638256, 638458]},
]
ROOT_BY_OFFSET = {row["file_offset"]: row for row in ROOTS}
ROOT_FOR_OFFSET = {offset: ROOTS[0]["id"] for offset in range(638132, 638178)}
ROOT_FOR_OFFSET.update({offset: ROOTS[1]["id"] for start, end in CODE_RANGES[1:] for offset in range(start, end)})

TABLE_RANGE = [638184, 638256]
TABLE_ENTRY_COUNT = 18
TABLE_TARGETS = [
    638256,
    638260,
    638268,
    638276,
    638286,
    638300,
    638314,
    638322,
    638330,
    638338,
    638346,
    638354,
    638362,
    638376,
    638390,
    638404,
    638418,
    638432,
]
TABLE_SHA256 = "38127546630d56bd867a46b250c397775b52721bdc84b6daecf0326d38ab141d"
PRODUCER_FORMS = (
    "thumb_bl",
    "thumb_b",
    "thumb_b_conditional",
    "arm_b",
    "arm_bl",
    "bytewise_u32_entry",
    "bytewise_u32_thumb_pointer",
)
BASE_LITERAL_RANGE = [638180, 638184]
BASE_LITERAL_VALUE = 0x0809BCE8
BASE_LITERAL_CONSUMER = 638170
DISPATCH_ROOT = 638132
DISPATCH_TERMINAL = 638176
DISPATCH_DEFAULT = 638470
DISPATCH_BRANCH = 638168
DISPATCH_CMP = 638162

INITIALIZER_BASE_CONSUMER = 634174
INITIALIZER_BASE_RANGE = [634324, 634328]
INITIALIZER_BASE_VALUE = 0x03007520
INITIALIZER_LOAD = 634176
INITIALIZER_POINTER_RANGE = [634328, 634332]
INITIALIZER_POINTER_VALUE = 0x0809BCB5
INITIALIZER_STORE = 634178
INITIALIZER_DESTINATION = 0x03007540
INITIALIZER_FIELD_OFFSET = 0x20

UPSTREAM_PATHS = {
    "cfg_inventory_v2": {
        "manifest": Path("artifacts/rom-cfg-inventory-v2/manifest.json"),
        "payload": Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"),
    },
    "m4a_initializer_chain": {
        "manifest": Path("artifacts/rom-m4a-initializer-chain-v1/manifest.json"),
        "payload": Path("artifacts/rom-m4a-initializer-chain-v1/rom-m4a-initializer-chain.json"),
    },
    "similar_table_adjudications": {"path": Path("sequel/similar-table-adjudications-v1.json")},
    "similar_table_verifier": {"path": Path("tools/verify_similar_table_candidates.py")},
}
UPSTREAM_RECEIPTS = {
    "cfg_inventory_v2": {
        "manifest_sha256": "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753",
        "payload_sha256": "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd",
    },
    "m4a_initializer_chain": {
        "manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c",
        "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd",
    },
    "similar_table_adjudications": {
        "path": "sequel/similar-table-adjudications-v1.json",
        "sha256": "c19ab7ee1e7b79eb6e3bc2888114336237e86a4c976bd8ee812fc251d70357d0",
    },
    "similar_table_verifier": {
        "path": "tools/verify_similar_table_candidates.py",
        "sha256": "04b9bc0b0a2d0ce22e817f590c04851fa70f712136e9c362a12dcd3aea75d86b",
    },
}

EXISTING_PRIMARY_OWNERS = [
    {"claim_id": "similar-table-candidate-027-range-050", "primary_class": "thumb_dispatch_literal_pool", "range": [638180, 638184]},
    {"claim_id": "similar-table-candidate-027-range-051", "primary_class": "thumb_pc_relative_jump_table", "range": [638184, 638244]},
    {"claim_id": "cfg-thumb-0770-09bd30", "primary_class": "armv4t_cfg_reachable_thumb_code", "range": [638256, 638404]},
    {"claim_id": "cfg-thumb-0771-09bdec", "primary_class": "armv4t_cfg_reachable_thumb_code", "range": [638444, 638458]},
    {"claim_id": "cfg-thumb-0772-09be00", "primary_class": "armv4t_cfg_reachable_thumb_code", "range": [638464, 638476]},
]
INITIALIZER_POINTER_OWNER = {
    "claim_id": "psg-initializer-literals-09adc0",
    "primary_class": "m4a_initializer_chain_consumed_literal_bytes",
    "range": [634304, 634384],
}
BASELINE_RECOVERY_KIND = "direct-frozen-prepromotion-snapshot"

SCOPE = {
    "allocatable_free_space_proven": False,
    "audio_behavior_proven": False,
    "computed_or_indirect_producer_denominator_complete": False,
    "editing_relocation_writeback_safe": False,
    "global_caller_or_code_denominator_complete": False,
    "global_ram_writer_denominator_complete": False,
    "literal_target_semantics_claimed": False,
    "natural_runtime_reachability": False,
    "target_limited_raw_producer_denominator_complete": True,
}
LIMITATIONS = [
    "This candidate classifies exactly four frozen ranges totaling 102 bytes; existing owners are provenance only and are not promoted again.",
    "The target-limited raw producer denominator covers the dispatcher, its 18 table entries, and the initializer pointer only; it is not a global caller/code/indirect/computed producer proof.",
    "Natural runtime reachability, global RAM-writer completeness, and global producer completeness remain unproven.",
    "Literal target business semantics, audio behavior, editing, writeback, relocation, and allocatable/free-space safety remain outside scope.",
    "The two explicitly excluded 0000 gaps remain unknown and are not padding, NOP, reserved, free, or allocatable space.",
]

PAYLOAD_NAME = "rom-mp2k-dispatcher.json"
BUNDLE_NAME = "rom-mp2k-dispatcher.bin"
MANIFEST_NAME = "manifest.json"
ARTIFACT_RELATIVE = EXPERIMENT_RELATIVE / "candidate"
_EDGE_ORDER = {"branch_target": 0, "dispatch_target": 1, "call_target": 2, "fallthrough": 3}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _bounded(data: bytes, start: int, end: int, label: str = "ROM") -> bytes:
    if start < 0 or end < start or end > len(data):
        raise ValueError(f"{label} range escapes input")
    return data[start:end]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 2, "Thumb instruction"), "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 4, "u32"), "little")


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _validate_root(root: Path | str) -> Path:
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("repository root uses a symlink")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    return resolved


def _safe_file(root: Path, relative: Path | str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe repository path: {path}")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {path}")
    resolved = (root / path).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {path}") from error
    if not resolved.is_file():
        raise ValueError(f"required file missing: {path}")
    return resolved


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path.expanduser()))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"path uses a symlink component: {cursor}")


def _validate_rom(rom: bytes) -> None:
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM SHA-256 changed")


def _validate_contract(root: Path) -> None:
    contract = _safe_file(root, CONTRACT_PATH).read_bytes()
    if _sha(contract) != CONTRACT_SHA256:
        raise ValueError("dispatcher contract changed")


def _raw_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
    """Decode only the ARMv4T Thumb direct-control-flow encodings in scope."""

    if len(raw) >= 4:
        first = int.from_bytes(raw[:2], "little")
        second = int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {
                "flow_kind": "call",
                "size": 4,
                "conditional": False,
                "target_offset": offset + 4 + _sign_extend(encoded, 23),
            }
    if len(raw) < 2:
        return None
    first = int.from_bytes(raw[:2], "little")
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        return {
            "flow_kind": "conditional_branch",
            "size": 2,
            "conditional": True,
            "condition": condition,
            "target_offset": offset + 4 + _sign_extend((first & 0xFF) << 1, 9),
        }
    if first & 0xF800 == 0xE000:
        return {
            "flow_kind": "unconditional_branch",
            "size": 2,
            "conditional": False,
            "target_offset": offset + 4 + _sign_extend((first & 0x07FF) << 1, 12),
        }
    if first & 0xFF87 == 0x4700:
        return {"flow_kind": "bx", "size": 2, "conditional": False, "register": (first >> 3) & 0xF}
    return None


def _in_code(offset: int) -> bool:
    return any(start <= offset < end for start, end in CODE_RANGES)


def _decode_table(rom: bytes) -> dict[str, Any]:
    if _u16(rom, BASE_LITERAL_CONSUMER) != 0x4902:
        raise ValueError("dispatcher base literal consumer changed")
    target = ((BASE_LITERAL_CONSUMER + 4) & ~3) + ((_u16(rom, BASE_LITERAL_CONSUMER) & 0xFF) << 2)
    if target != BASE_LITERAL_RANGE[0]:
        raise ValueError("dispatcher base literal address changed")
    if _u32(rom, BASE_LITERAL_RANGE[0]) != BASE_LITERAL_VALUE:
        raise ValueError("dispatcher base literal value changed")
    raw = _bounded(rom, TABLE_RANGE[0], TABLE_RANGE[1], "dispatcher table")
    if _sha(raw) != TABLE_SHA256:
        raise ValueError("dispatcher table changed")
    targets = [_u32(rom, TABLE_RANGE[0] + index * 4) - ROM_BASE for index in range(TABLE_ENTRY_COUNT)]
    if targets != TABLE_TARGETS:
        raise ValueError("dispatcher table targets changed")
    if any(target & 1 or not _in_code(target) for target in targets):
        raise ValueError("dispatcher table target mode or range changed")
    return {
        "entry_count": TABLE_ENTRY_COUNT,
        "range": list(TABLE_RANGE),
        "sha256": TABLE_SHA256,
        "targets": list(targets),
        "raw_hex": raw.hex(),
        "base_literal": {
            "consumer_offset": BASE_LITERAL_CONSUMER,
            "range": list(BASE_LITERAL_RANGE),
            "sha256": _sha(_bounded(rom, BASE_LITERAL_RANGE[0], BASE_LITERAL_RANGE[1], "base literal")),
            "value": BASE_LITERAL_VALUE,
        },
    }


def _decode_instruction(rom: bytes, offset: int, table: dict[str, Any]) -> dict[str, Any]:
    if not _in_code(offset) or offset & 1:
        raise ValueError("CFG instruction escapes frozen code ranges")
    first = _u16(rom, offset)
    is_bl = first & 0xF800 == 0xF000 and offset + 4 <= len(rom) and (_u16(rom, offset + 2) & 0xF800) == 0xF800
    size = 4 if is_bl else 2
    raw = _bounded(rom, offset, offset + size, "CFG instruction")
    flow = _raw_flow(raw, offset)
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    next_offset = offset + size
    if offset == DISPATCH_TERMINAL:
        if first != 0x4687:
            raise ValueError("dispatcher mov pc,r0 terminal changed")
        flow_kind = "resolved_dispatch"
        raw_flow_kind = "mov_pc_r0"
        for target in table["targets"]:
            successors.append({"kind": "dispatch_target", "target_offset": target, "target_mode": "thumb"})
        conditional = False
    elif flow and flow["flow_kind"] == "call":
        flow_kind = "opaque_call"
        raw_flow_kind = "call"
        target = flow["target_offset"]
        if offset != 638452 or target != 639256:
            raise ValueError("dispatcher opaque BL target changed")
        successors.append({"kind": "call_target", "target_offset": target, "target_mode": "thumb", "resolution": "opaque_thumb_bl"})
        successors.append({"kind": "fallthrough", "target_offset": next_offset, "target_mode": "thumb"})
        conditional = False
    elif flow and flow["flow_kind"] == "conditional_branch":
        flow_kind = "conditional_branch"
        raw_flow_kind = "conditional_branch"
        target = flow["target_offset"]
        successors.append({"kind": "branch_target", "target_offset": target, "target_mode": "thumb"})
        successors.append({"kind": "fallthrough", "target_offset": next_offset, "target_mode": "thumb"})
        conditional = True
    elif flow and flow["flow_kind"] == "unconditional_branch":
        flow_kind = "unconditional_branch"
        raw_flow_kind = "unconditional_branch"
        successors.append({"kind": "branch_target", "target_offset": flow["target_offset"], "target_mode": "thumb"})
        conditional = False
    elif flow and flow["flow_kind"] == "bx":
        if offset == 638474 and flow["register"] == 0 and first == 0x4700:
            flow_kind = "structured_return"
            raw_flow_kind = "bx"
            conditional = False
        else:
            flow_kind = "indirect_branch"
            raw_flow_kind = "bx"
            conditional = False
            frontiers.append({"reason": "indirect_branch", "register": flow["register"]})
    else:
        flow_kind = "linear"
        raw_flow_kind = None
        conditional = False
        successors.append({"kind": "fallthrough", "target_offset": next_offset, "target_mode": "thumb"})
    for edge in successors:
        if edge["kind"] in {"branch_target", "fallthrough", "dispatch_target"} and not _in_code(edge["target_offset"]):
            raise ValueError("CFG target escapes frozen code ranges")
    successors.sort(key=lambda row: (_EDGE_ORDER[row["kind"]], row["target_offset"]))
    return {
        "root": ROOT_FOR_OFFSET[offset],
        "root_offset": 638132 if ROOT_FOR_OFFSET[offset] == ROOTS[0]["id"] else 638256,
        "offset": offset,
        "gba_address": _gba(offset),
        "mode": "thumb",
        "size": size,
        "raw_hex": raw.hex(),
        "bytes_sha256": _sha(raw),
        "flow_kind": flow_kind,
        "raw_flow_kind": raw_flow_kind,
        "conditional": conditional,
        "successors": successors,
        "frontiers": frontiers,
    }


def _walk_cfg(rom: bytes, table: dict[str, Any]) -> dict[int, dict[str, Any]]:
    pending = [638132, 638256]
    nodes: dict[int, dict[str, Any]] = {}
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        node = _decode_instruction(rom, offset, table)
        nodes[offset] = node
        for edge in node["successors"]:
            if edge["kind"] == "call_target":
                continue
            target = edge["target_offset"]
            if not _in_code(target) or target & 1:
                raise ValueError("CFG target escapes frozen ranges or is not an even Thumb offset")
            heapq.heappush(pending, target)
    owners: dict[int, int] = {}
    for offset, node in nodes.items():
        for byte_offset in range(offset, offset + node["size"]):
            if not _in_code(byte_offset):
                raise ValueError("CFG instruction crosses an excluded gap")
            if byte_offset in owners and owners[byte_offset] != offset:
                raise ValueError("CFG target lands in an instruction middle")
            owners[byte_offset] = offset
    expected = {byte for start, end in CODE_RANGES for byte in range(start, end)}
    if set(owners) != expected or len(nodes) != 129 or sum(node["size"] for node in nodes.values()) != 260:
        raise ValueError("CFG instruction denominator changed")
    if any(node["frontiers"] for node in nodes.values()):
        raise ValueError("CFG has unresolved frontier")
    return nodes


def _build_blocks(nodes: dict[int, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predecessors: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for edge in node["successors"]:
            if edge["target_offset"] in nodes:
                predecessors[edge["target_offset"]].append((source, edge["kind"]))
    leaders = {638132, 638256}
    for offset, incoming in predecessors.items():
        if offset in leaders:
            continue
        if len(incoming) != 1:
            leaders.add(offset)
            continue
        source, kind = incoming[0]
        predecessor = nodes[source]
        if len(predecessor["successors"]) != 1 or kind != "fallthrough" or predecessor["flow_kind"] != "linear" or source + predecessor["size"] != offset:
            leaders.add(offset)
    block_by_offset: dict[int, str] = {}
    blocks: list[dict[str, Any]] = []
    for leader in sorted(leaders):
        members: list[int] = []
        offset = leader
        while offset in nodes and offset not in block_by_offset:
            members.append(offset)
            block_by_offset[offset] = f"block-mp2k-dispatcher-{leader:06x}"
            node = nodes[offset]
            if len(node["successors"]) != 1 or node["flow_kind"] != "linear":
                break
            edge = node["successors"][0]
            if edge["target_offset"] in leaders or edge["target_offset"] != offset + node["size"]:
                break
            offset = edge["target_offset"]
        if not members:
            continue
        last = nodes[members[-1]]
        block_end = members[-1] + last["size"]
        blocks.append({
            "id": block_by_offset[leader],
            "root": ROOT_FOR_OFFSET[leader],
            "mode": "thumb",
            "range": [leader, block_end],
            "gba_range": [_gba(leader), _gba(block_end)],
            "instruction_count": len(members),
            "bytes_sha256": _sha(b"".join(bytes.fromhex(nodes[item]["raw_hex"]) for item in members)),
            "terminator": {
                "offset": members[-1],
                "size": last["size"],
                "raw_hex": last["raw_hex"],
                "flow_kind": last["flow_kind"],
                "conditional": last["conditional"],
            },
            "successors": [],
        })
    if len(blocks) != 36 or len(block_by_offset) != len(nodes):
        raise ValueError("CFG block denominator changed")
    blocks_by_id = {block["id"]: block for block in blocks}
    block_last = {block["id"]: block["terminator"]["offset"] for block in blocks}
    block_edges: list[dict[str, Any]] = []
    for block in blocks:
        source_offset = block_last[block["id"]]
        for edge in nodes[source_offset]["successors"]:
            row = {
                "source_block": block["id"],
                "source_instruction_offset": source_offset,
                "kind": edge["kind"],
                "target_offset": edge["target_offset"],
                "target_mode": edge["target_mode"],
            }
            target_block = block_by_offset.get(edge["target_offset"])
            if target_block is not None:
                row["target_block"] = target_block
            if edge.get("resolution") is not None:
                row["resolution"] = edge["resolution"]
            block["successors"].append(row)
            block_edges.append(row)
    for block in blocks:
        block["successors"].sort(key=lambda row: (_EDGE_ORDER[row["kind"]], row["target_offset"]))
    block_edges.sort(key=lambda row: (row["source_instruction_offset"], _EDGE_ORDER[row["kind"]], row["target_offset"]))
    return blocks, block_edges


def _cfg(rom: bytes, table: dict[str, Any]) -> dict[str, Any]:
    nodes = _walk_cfg(rom, table)
    blocks, block_edges = _build_blocks(nodes)
    instructions = [nodes[offset] for offset in sorted(nodes)]
    calls = [
        {
            "source_instruction_offset": 638452,
            "source_gba_address": _gba(638452),
            "kind": "call_target",
            "target_offset": 639256,
            "target_gba_address": _gba(639256),
            "target_mode": "thumb",
            "resolution": "opaque_thumb_bl",
            "target_root": None,
        }
    ]
    returns = [{"offset": 638474, "gba_address": _gba(638474), "mode": "thumb"}]
    roots: list[dict[str, Any]] = []
    for root in ROOTS:
        root_blocks = [block for block in blocks if block["root"] == root["id"]]
        root_instructions = [node for node in instructions if node["root"] == root["id"]]
        roots.append({
            "id": root["id"],
            "file_offset": root["file_offset"],
            "gba_address": _gba(root["file_offset"]),
            "mode": "thumb",
            "code_range": list(root["code_range"]),
            "block_ranges": [block["range"] for block in root_blocks],
            "instruction_count": len(root_instructions),
            "instruction_bytes": sum(node["size"] for node in root_instructions),
            "internal_edge_count": sum(1 for edge in block_edges if edge["source_block"] in {block["id"] for block in root_blocks} and "target_block" in edge),
        })
    summary = {
        "instruction_count": len(instructions),
        "instruction_bytes": sum(node["size"] for node in instructions),
        "code_bytes": sum(end - start for start, end in CODE_RANGES),
        "block_count": len(blocks),
        "internal_edge_count": sum(1 for edge in block_edges if "target_block" in edge),
        "external_edge_count": sum(1 for edge in block_edges if "target_block" not in edge),
        "resolved_dispatch_edge_count": sum(1 for edge in block_edges if edge["kind"] == "dispatch_target"),
        "total_graph_edge_count": len(block_edges),
        "structured_return_count": len(returns),
        "frontier_count": 0,
        "unresolved_frontier_count": 0,
        "budget_exhausted": False,
    }
    if summary["internal_edge_count"] != 65 or summary["external_edge_count"] != 1 or summary["total_graph_edge_count"] != 66:
        raise ValueError("CFG edge denominator changed")
    semantic_vector = [[node["offset"], node["size"], node["raw_hex"], node["flow_kind"], node["raw_flow_kind"], node["conditional"]] for node in instructions]
    edge_vector = [[edge["source_instruction_offset"], edge["kind"], edge["target_offset"], edge.get("resolution")] for edge in block_edges]
    external_edges = [{
        "kind": "opaque_thumb_bl",
        "raw_hex": _bounded(rom, 638452, 638456).hex(),
        "source_offset": 638452,
        "target_offset": 639256,
    }]
    return {
        "code_ranges": [list(interval) for interval in CODE_RANGES],
        "roots": roots,
        "instructions": instructions,
        "blocks": blocks,
        "block_edges": block_edges,
        "calls": calls,
        "returns": returns,
        "return_offsets": [row["offset"] for row in returns],
        "frontiers": [],
        "external_edges": external_edges,
        "summary": summary,
        "semantic_instruction_vector": semantic_vector,
        "semantic_instruction_vector_sha256": _sha(_canonical(semantic_vector)),
        "edge_vector_sha256": _sha(_canonical(edge_vector)),
    }


def _analyze_cfg(rom: bytes, table: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rebuild the bounded CFG; retained as the explicit analysis seam."""

    return _cfg(rom, _decode_table(rom) if table is None else table)


def _pointer_occurrences(rom: bytes, value: int) -> list[int]:
    raw = struct.pack("<I", value)
    found: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(raw, cursor)
        if cursor < 0:
            return found
        found.append(cursor)
        cursor += 1


def _initializer_binding(rom: bytes) -> dict[str, Any]:
    if _u16(rom, INITIALIZER_BASE_CONSUMER) != 0x4925:
        raise ValueError("initializer structure-base consumer changed")
    base_target = ((INITIALIZER_BASE_CONSUMER + 4) & ~3) + ((_u16(rom, INITIALIZER_BASE_CONSUMER) & 0xFF) << 2)
    if base_target != INITIALIZER_BASE_RANGE[0] or _u32(rom, base_target) != INITIALIZER_BASE_VALUE:
        raise ValueError("initializer structure-base literal changed")
    if _u16(rom, INITIALIZER_LOAD) != 0x4825:
        raise ValueError("initializer pointer load changed")
    pointer_target = ((INITIALIZER_LOAD + 4) & ~3) + ((_u16(rom, INITIALIZER_LOAD) & 0xFF) << 2)
    if pointer_target != INITIALIZER_POINTER_RANGE[0] or _u32(rom, pointer_target) != INITIALIZER_POINTER_VALUE:
        raise ValueError("initializer pointer literal changed")
    if _u16(rom, INITIALIZER_STORE) != 0x6208:
        raise ValueError("initializer field writer changed")
    occurrences = _pointer_occurrences(rom, INITIALIZER_POINTER_VALUE)
    if occurrences != [INITIALIZER_POINTER_RANGE[0]]:
        raise ValueError("initializer pointer occurrence is not unique")
    return {
        "destination_address": INITIALIZER_DESTINATION,
        "entry_pointer": INITIALIZER_POINTER_VALUE,
        "entry_pointer_occurrences": occurrences,
        "field_offset": INITIALIZER_FIELD_OFFSET,
        "load_instruction": {"offset": INITIALIZER_LOAD, "raw_hex": _bounded(rom, INITIALIZER_LOAD, INITIALIZER_LOAD + 2).hex()},
        "store_instruction": {"offset": INITIALIZER_STORE, "raw_hex": _bounded(rom, INITIALIZER_STORE, INITIALIZER_STORE + 2).hex()},
        "structure_base_literal": {"consumer_offset": INITIALIZER_BASE_CONSUMER, "range": list(INITIALIZER_BASE_RANGE), "value": INITIALIZER_BASE_VALUE},
        "entry_pointer_root_offset": DISPATCH_ROOT,
        "pointer_literal": {"range": list(INITIALIZER_POINTER_RANGE), "raw_hex": _bounded(rom, INITIALIZER_POINTER_RANGE[0], INITIALIZER_POINTER_RANGE[1]).hex()},
    }


def _load_json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not valid JSON") from error


def _candidate_027_adjudication(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != "similar-table-adjudications-v1":
        raise ValueError("similar-table adjudications schema changed")
    rows = value.get("adjudications")
    if not isinstance(rows, list):
        raise ValueError("similar-table adjudications changed")
    matches = [row for row in rows if isinstance(row, dict) and row.get("candidate_id") == 27]
    if len(matches) != 1:
        raise ValueError("candidate 027 adjudication changed")
    row = matches[0]
    partitions = row.get("partitions")
    if not isinstance(partitions, list) or any(not isinstance(item, dict) for item in partitions):
        raise ValueError("candidate 027 partitions changed")
    normalized = {
        "candidate_range": row.get("candidate_range"),
        "partitions": [item.get("range") for item in partitions],
        "relation": row.get("relation"),
        "status": row.get("status"),
    }
    expected = {
        "candidate_range": [638180, 638244],
        "partitions": [[638180, 638184], [638184, 638244]],
        "relation": "crosses_canonical_table_boundary",
        "status": "rejected",
    }
    if normalized != expected:
        raise ValueError("candidate 027 adjudication changed")
    return normalized


def _validate_upstream_receipts(root: Path) -> dict[str, Any]:
    candidate_027: dict[str, Any] | None = None
    for name, paths in UPSTREAM_PATHS.items():
        receipt = UPSTREAM_RECEIPTS[name]
        if name in {"cfg_inventory_v2", "m4a_initializer_chain"}:
            for role in ("manifest", "payload"):
                path = _safe_file(root, paths[role])
                if _sha(path.read_bytes()) != receipt[f"{role}_sha256"]:
                    raise ValueError(f"upstream {name} {role} identity changed")
            manifest = _load_json(_safe_file(root, paths["manifest"]).read_bytes(), f"upstream {name} manifest")
            payload = _load_json(_safe_file(root, paths["payload"]).read_bytes(), f"upstream {name} payload")
            if not isinstance(manifest, dict) or not isinstance(payload, dict):
                raise ValueError(f"upstream {name} object changed")
            if payload.get("rom", {}).get("sha256") != BASE_ROM_SHA256:
                raise ValueError(f"upstream {name} ROM identity changed")
        else:
            path = _safe_file(root, paths["path"])
            if _sha(path.read_bytes()) != receipt["sha256"]:
                raise ValueError(f"upstream {name} identity changed")
            if name == "similar_table_adjudications":
                candidate_027 = _candidate_027_adjudication(_load_json(path.read_bytes(), name))
    if candidate_027 is None:
        raise ValueError("candidate 027 adjudication missing")
    return candidate_027


def _coverage_artifact_relative(root: Path, artifact: Path | str) -> Path:
    requested = Path(artifact).expanduser()
    if requested.is_absolute():
        lexical = Path(os.path.abspath(requested))
        _reject_symlink_components(lexical)
        try:
            relative = lexical.relative_to(root)
        except ValueError as error:
            raise ValueError("coverage baseline artifact escapes repository root") from error
    else:
        relative = requested
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("coverage baseline artifact path changed")
    return relative


def _validated_existing_owners(normalized: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    existing: list[dict[str, Any]] = []
    for expected in EXISTING_PRIMARY_OWNERS:
        matches = [
            row for row in normalized
            if row["range"] == expected["range"]
            and row["primary_class"] == expected["primary_class"]
            and row["primary_claim_ids"] == [expected["claim_id"]]
        ]
        if len(matches) != 1:
            raise ValueError("coverage baseline provenance owner changed")
        existing.append({"claim_id": expected["claim_id"], "range": list(expected["range"])})
    pointer_start, pointer_end = INITIALIZER_POINTER_RANGE
    pointer_matches = [
        row for row in normalized
        if row["range"][0] <= pointer_start
        and row["range"][1] >= pointer_end
        and row["primary_class"] == INITIALIZER_POINTER_OWNER["primary_class"]
        and row["primary_claim_ids"] == [INITIALIZER_POINTER_OWNER["claim_id"]]
    ]
    if len(pointer_matches) != 1:
        raise ValueError("coverage baseline initializer pointer owner changed")
    return existing, INITIALIZER_POINTER_OWNER["claim_id"]


def _validate_coverage_segments(coverage: Any) -> tuple[dict[str, Any], int]:
    if not isinstance(coverage, dict):
        raise ValueError("coverage baseline must be an object")
    if coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage baseline schema changed")
    summary = coverage.get("summary")
    if not isinstance(summary, dict) or any(summary.get(key) != value for key, value in COVERAGE_SUMMARY.items()):
        raise ValueError("coverage baseline summary changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list):
        raise ValueError("coverage baseline segments changed")
    normalized: list[dict[str, Any]] = []
    for row in segments:
        if not isinstance(row, dict) or not isinstance(row.get("range"), list) or len(row["range"]) != 2:
            raise ValueError("coverage baseline segment changed")
        start, end = row["range"]
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError("coverage baseline segment range changed")
        if not isinstance(row.get("primary_class"), str) or not isinstance(row.get("primary_claim_ids"), list):
            raise ValueError("coverage baseline owner changed")
        normalized.append({"range": [start, end], "primary_class": row["primary_class"], "primary_claim_ids": list(row["primary_claim_ids"])})
    existing_primary_ranges, initializer_pointer_owner_claim_id = _validated_existing_owners(normalized)
    target_segments: list[dict[str, Any]] = []
    promotion_bytes = sum(end - start for start, end in PROMOTION_RANGES)
    for start, end in PROMOTION_RANGES:
        owners = [row for row in normalized if row["range"][0] < end and row["range"][1] > start]
        covered = [0] * (end - start)
        for row in owners:
            a, b = row["range"]
            left, right = max(start, a), min(end, b)
            for byte in range(left, right):
                index = byte - start
                covered[index] += 1
                if row["primary_class"] != "unknown" or row["primary_claim_ids"]:
                    covered[index] = -100
            if row not in target_segments:
                target_segments.append(row)
        if any(value == 0 for value in covered):
            raise ValueError("promotion range is not whole-range unknown")
        if any(value < 0 for value in covered):
            raise ValueError("promotion range has a foreign owner; not whole-range unknown")
        if any(value > 1 for value in covered):
            raise ValueError("coverage baseline has duplicate owner overlap")
    target_segments.sort(key=lambda row: (row["range"][0], row["range"][1]))
    segment_delta = 0
    for start, end in PROMOTION_RANGES:
        for row in normalized:
            a, b = row["range"]
            if a < end and b > start:
                if start > a:
                    segment_delta += 1
                if end < b:
                    segment_delta += 1
    result = {
        "all_promotion_bytes_unknown": True,
        "path": COVERAGE_PATH.as_posix(),
        "primary_overlap_bytes": 0,
        "promotion_bytes": promotion_bytes,
        "schema": "rom-byte-coverage-v1",
        "sha256": None,
        "size": None,
        "summary": {key: summary[key] for key in COVERAGE_SUMMARY},
        "target_segments": target_segments,
        "unknown_promotion_bytes": promotion_bytes,
        "existing_primary_ranges": existing_primary_ranges,
        "initializer_pointer_owner_claim_id": initializer_pointer_owner_claim_id,
    }
    return result, segment_delta


def analyze_coverage_baseline(coverage: Any) -> dict[str, Any]:
    result, _ = _validate_coverage_segments(coverage)
    return result


def _coverage_from_file(root: Path) -> tuple[dict[str, Any], bytes]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    coverage = _load_json(raw, "coverage baseline")
    analyzed, _ = _validate_coverage_segments(coverage)
    analyzed["sha256"] = COVERAGE_SHA256
    analyzed["size"] = len(raw)
    return analyzed, raw


def _coverage_baseline_from_artifact(root: Path, artifact: Path | str) -> tuple[dict[str, Any], dict[str, Any]]:
    relative = _coverage_artifact_relative(root, artifact)
    directory = (root / relative)
    _reject_symlink_components(directory)
    directory = directory.resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("coverage baseline artifact is not a directory")
    manifest_path = directory / "manifest.json"
    archive_path = directory / "rom-byte-coverage.json.gz"
    if manifest_path.is_symlink() or archive_path.is_symlink() or not manifest_path.is_file() or not archive_path.is_file():
        raise ValueError("coverage baseline artifact files changed")
    manifest_raw = manifest_path.read_bytes()
    archive_raw = archive_path.read_bytes()
    manifest = _load_json(manifest_raw, "coverage baseline artifact manifest")
    if _canonical(manifest) != manifest_raw or not isinstance(manifest, dict) or manifest.get("schema") != "rom-byte-coverage-prepromotion-baseline-v1" or manifest.get("artifact_status") != "accepted":
        raise ValueError("coverage baseline artifact manifest changed")
    recovery = manifest.get("recovery")
    if not isinstance(recovery, dict) or recovery.get("kind") != BASELINE_RECOVERY_KIND:
        raise ValueError("coverage baseline recovery kind changed")
    coverage_info = manifest.get("coverage")
    if not isinstance(coverage_info, dict) or not isinstance(coverage_info.get("raw"), dict) or not isinstance(coverage_info.get("archive"), dict):
        raise ValueError("coverage baseline artifact receipt changed")
    raw_info, archive_info = coverage_info["raw"], coverage_info["archive"]
    if archive_info.get("compression") != "gzip" or archive_info.get("file") != "rom-byte-coverage.json.gz" or archive_info.get("sha256") != _sha(archive_raw) or archive_info.get("size") != len(archive_raw):
        raise ValueError("coverage baseline archive identity changed")
    try:
        raw = gzip.decompress(archive_raw)
    except OSError as error:
        raise ValueError("coverage baseline archive is not valid gzip") from error
    if raw_info.get("canonical_json") is not True or raw_info.get("schema") != "rom-byte-coverage-v1" or raw_info.get("sha256") != _sha(raw) or raw_info.get("size") != len(raw) or raw_info.get("summary") != COVERAGE_SUMMARY:
        raise ValueError("coverage baseline raw identity changed")
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline raw hash changed")
    coverage = _load_json(raw, "coverage baseline archive")
    analyzed, _ = _validate_coverage_segments(coverage)
    analyzed["sha256"] = COVERAGE_SHA256
    analyzed["size"] = len(raw)
    source = {
        "artifact": relative.as_posix(),
        "kind": "immutable-gzip-artifact",
        "archive_file": "rom-byte-coverage.json.gz",
        "archive_sha256": _sha(archive_raw),
        "archive_size": len(archive_raw),
        "manifest_sha256": _sha(manifest_raw),
        "raw_sha256": _sha(raw),
        "raw_size": len(raw),
        "recovery_kind": recovery["kind"],
    }
    return analyzed, source


def _promotion_contract_guard() -> None:
    if len(PROMOTION_RANGES) != 4 or len(PROMOTION_RANGE_SHA256) != 4 or [list(row) for row in PROMOTION_UNION_RANGES] != [list(row) for row in PROMOTION_RANGES]:
        raise ValueError("promotion range vector receipt changed")
    if _sha(_compact(PROMOTION_UNION_RANGES)) != RANGE_VECTOR_SHA256:
        raise ValueError("promotion range vector receipt changed")


def _promotion_rows(rom: bytes) -> list[dict[str, Any]]:
    _promotion_contract_guard()
    rows: list[dict[str, Any]] = []
    kinds = [
        "mp2k_dispatcher_bounded_thumb_code",
        "mp2k_dispatcher_table_tail_u32_entries",
        "mp2k_dispatcher_bounded_thumb_code",
        "mp2k_dispatcher_consumed_literal_bytes",
    ]
    for interval, expected, kind in zip(PROMOTION_RANGES, PROMOTION_RANGE_SHA256, kinds):
        start, end = interval
        raw = _bounded(rom, start, end, "promotion")
        digest = _sha(raw)
        if digest != expected:
            raise ValueError(f"promotion range changed at 0x{start:06X}")
        rows.append({"range": list(interval), "bytes": len(raw), "sha256": digest, "kind": kind, "promoted": True, "semantic_class": kind})
    bundle = b"".join(_bounded(rom, start, end, "promotion") for start, end in PROMOTION_RANGES)
    if len(bundle) != 102 or _sha(bundle) != PACKED_SHA256:
        raise ValueError("promotion packed bytes changed")
    return rows


def _excluded_ranges(rom: bytes) -> list[dict[str, Any]]:
    rows = []
    for interval, expected in zip(EXCLUDED_RANGES, EXCLUDED_SHA256):
        raw = _bounded(rom, interval[0], interval[1], "excluded gap")
        digest = _sha(raw)
        if digest != expected:
            raise ValueError("excluded gap bytes changed")
        rows.append({"range": list(interval), "bytes": len(raw), "sha256": digest, "promoted": False, "semantic_class": "unknown", "promotion_excluded": True})
    return rows


def _literal_bindings(rom: bytes) -> list[dict[str, Any]]:
    raw = _bounded(rom, BASE_LITERAL_RANGE[0], BASE_LITERAL_RANGE[1], "base literal")
    if _u32(rom, BASE_LITERAL_RANGE[0]) != BASE_LITERAL_VALUE:
        raise ValueError("dispatcher base literal bytes changed")
    return [{
        "instruction_offset": BASE_LITERAL_CONSUMER,
        "raw": _u16(rom, BASE_LITERAL_CONSUMER),
        "literal_offset": BASE_LITERAL_RANGE[0],
        "value": BASE_LITERAL_VALUE,
        "raw_hex": raw.hex(),
    }]


def _consumed_literals(rom: bytes) -> list[dict[str, Any]]:
    if _u16(rom, 638444) != 0x4803:
        raise ValueError("dispatcher consumed literal load changed")
    target = ((638444 + 4) & ~3) + ((_u16(rom, 638444) & 0xFF) << 2)
    if target != 638460 or _u32(rom, target) != 0x03007524:
        raise ValueError("dispatcher consumed literal changed")
    return [{"consumer_offset": 638444, "range": [638460, 638464], "value": 0x03007524, "raw_hex": _bounded(rom, 638460, 638464).hex()}]


def _dispatcher_semantics(rom: bytes, table: dict[str, Any]) -> dict[str, Any]:
    if _u16(rom, DISPATCH_CMP) != 0x2D11:
        raise ValueError("dispatcher cmp immediate changed")
    if _u16(rom, 638164) != 0xD900:
        raise ValueError("dispatcher unsigned bls changed")
    if _u16(rom, 638166) != 0xE096:
        raise ValueError("dispatcher default branch changed")
    if _u16(rom, 638176) != 0x4687:
        raise ValueError("dispatcher terminal changed")
    return {
        "root_offset": DISPATCH_ROOT,
        "accepted_index_domain": [0, 17],
        "accepted_value_count": 18,
        "base_literal": {
            "consumer_offset": BASE_LITERAL_CONSUMER,
            "range": list(BASE_LITERAL_RANGE),
            "sha256": _sha(_bounded(rom, BASE_LITERAL_RANGE[0], BASE_LITERAL_RANGE[1], "base literal")),
            "value": BASE_LITERAL_VALUE,
        },
        "cmp": {"offset": DISPATCH_CMP, "raw_hex": _bounded(rom, DISPATCH_CMP, DISPATCH_CMP + 2).hex(), "immediate": 17},
        "domain_branch": {"kind": "unsigned_bls", "offset": 638164, "raw_hex": _bounded(rom, 638164, 638166).hex(), "target_offset": DISPATCH_BRANCH},
        "default_branch": {"offset": 638166, "raw_hex": _bounded(rom, 638166, 638168).hex(), "target_offset": DISPATCH_DEFAULT},
        "table": table,
        "terminal": {"kind": "resolved_mov_pc_r0", "offset": DISPATCH_TERMINAL, "raw_hex": _bounded(rom, DISPATCH_TERMINAL, DISPATCH_TERMINAL + 2).hex()},
    }


def _thumb_bl_target(rom: bytes, offset: int) -> int | None:
    if offset < 0 or offset & 1 or offset + 4 > len(rom):
        return None
    first, second = _u16(rom, offset), _u16(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    return offset + 4 + _sign_extend(encoded, 23)


def _thumb_branch_target(rom: bytes, offset: int) -> tuple[str, int] | None:
    if offset < 0 or offset & 1 or offset + 2 > len(rom):
        return None
    halfword = _u16(rom, offset)
    condition = (halfword >> 8) & 0xF
    if halfword & 0xF000 == 0xD000 and condition <= 0xD:
        return "thumb_b_conditional", offset + 4 + _sign_extend((halfword & 0xFF) << 1, 9)
    if halfword & 0xF800 == 0xE000:
        return "thumb_b", offset + 4 + _sign_extend((halfword & 0x07FF) << 1, 12)
    return None


def _arm_branch_target(rom: bytes, offset: int) -> tuple[str, int] | None:
    if offset < 0 or offset & 3 or offset + 4 > len(rom):
        return None
    word = _u32(rom, offset)
    if word & 0x0E000000 != 0x0A000000:
        return None
    return ("arm_bl" if word & (1 << 24) else "arm_b", offset + 8 + _sign_extend((word & 0x00FFFFFF) << 2, 26))


def _expected_producer_forms() -> dict[int, dict[str, list[int]]]:
    expected = {target: {form: [] for form in PRODUCER_FORMS} for target in [DISPATCH_ROOT, *TABLE_TARGETS]}
    for index, target in enumerate(TABLE_TARGETS):
        expected[target]["bytewise_u32_entry"] = [TABLE_RANGE[0] + index * 4]
    expected[DISPATCH_ROOT]["bytewise_u32_thumb_pointer"] = [INITIALIZER_POINTER_RANGE[0]]
    return expected


def _scan_producer_forms(rom: bytes) -> dict[int, dict[str, list[int]]]:
    forms = {target: {form: [] for form in PRODUCER_FORMS} for target in [DISPATCH_ROOT, *TABLE_TARGETS]}
    for offset in range(0, len(rom) - 3, 2):
        target = _thumb_bl_target(rom, offset)
        if target in forms:
            forms[target]["thumb_bl"].append(offset)
    for offset in range(0, len(rom) - 1, 2):
        branch = _thumb_branch_target(rom, offset)
        if branch is not None and branch[1] in forms:
            forms[branch[1]][branch[0]].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        branch = _arm_branch_target(rom, offset)
        if branch is not None and branch[1] in forms:
            forms[branch[1]][branch[0]].append(offset)
    for target in forms:
        forms[target]["bytewise_u32_entry"] = _pointer_occurrences(rom, ROM_BASE + target)
        forms[target]["bytewise_u32_thumb_pointer"] = _pointer_occurrences(rom, ROM_BASE + target + 1)
        for offsets in forms[target].values():
            offsets.sort()
    if forms != _expected_producer_forms():
        raise ValueError("target producer form denominator changed")
    return forms


def _producer_denominator(rom: bytes, *, table_owner_claim_id: str, initializer_owner_claim_id: str) -> dict[str, Any]:
    forms = _scan_producer_forms(rom)
    roles: list[dict[str, Any]] = []
    for index, target in enumerate(TABLE_TARGETS):
        source = TABLE_RANGE[0] + index * 4
        roles.append({"target_offset": target, "form": "bytewise_u32_entry", "source_offset": source, "role": "preowned_provenance" if source < 638244 else "promoted_table_tail", "owner_claim_id": table_owner_claim_id if source < 638244 else None, "promoted": source >= 638244})
    roles.append({"target_offset": DISPATCH_ROOT, "form": "bytewise_u32_thumb_pointer", "source_offset": INITIALIZER_POINTER_RANGE[0], "role": "preowned_provenance", "owner_claim_id": initializer_owner_claim_id, "promoted": False})
    vector = [{"target_file_offset": target, "forms": forms[target]} for target in [DISPATCH_ROOT, *TABLE_TARGETS]]
    return {
        "scan": {
            "mode": "raw-rom",
            "alignment_bytes": 1,
            "alignment_bytes_by_form": {
                "thumb_bl": 2,
                "thumb_b": 2,
                "thumb_b_conditional": 2,
                "arm_b": 4,
                "arm_bl": 4,
                "bytewise_u32_entry": 1,
                "bytewise_u32_thumb_pointer": 1,
            },
            "range": [0, ROM_SIZE],
            "forms": list(PRODUCER_FORMS),
        },
        "root_forms": {f"0x{target:06X}": forms[target] for target in sorted(forms)},
        "producer_form_vector": vector,
        "producer_form_vector_sha256": _sha(_canonical(vector)),
        "producer_roles": roles,
        "producer_source_membership_by_role": {"preowned_provenance": True, "promoted_table_tail": True},
        "all_producer_source_membership_proven": True,
        "all_producer_bytes_promoted": False,
        "target_limited_raw_producer_denominator_complete": True,
        "global_producer_denominator_complete": False,
        "computed_or_indirect_producer_denominator_complete": False,
    }


def _provenance(candidate_027: dict[str, Any], existing_primary_ranges: list[dict[str, Any]], producer: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_027": candidate_027,
        "existing_primary_ranges": existing_primary_ranges,
        "target_limited_producer_forms": {
            str(target): {form: offsets for form, offsets in producer["root_forms"][f"0x{target:06X}"].items() if offsets}
            for target in [DISPATCH_ROOT, *TABLE_TARGETS]
        },
    }


def build_payload_from_rom(root: Path | str, rom: bytes, *, coverage_baseline_artifact: Path | str | None = None) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    _validate_contract(repository)
    data = bytes(rom)
    _validate_rom(data)
    candidate_027 = _validate_upstream_receipts(repository)
    if coverage_baseline_artifact is None:
        coverage, _raw = _coverage_from_file(repository)
        coverage_source = None
        _, segment_delta = _validate_coverage_segments(_load_json(_raw, "coverage baseline"))
    else:
        coverage, coverage_source = _coverage_baseline_from_artifact(repository, coverage_baseline_artifact)
        # The source helper already checks all coverage fields; recompute the
        # split count from its raw immutable archive for the projection.
        source_dir = (repository / _coverage_artifact_relative(repository, coverage_baseline_artifact)).resolve(strict=True)
        raw = gzip.decompress((source_dir / "rom-byte-coverage.json.gz").read_bytes())
        _, segment_delta = _validate_coverage_segments(_load_json(raw, "coverage baseline archive"))
    promotion_rows = _promotion_rows(data)
    excluded = _excluded_ranges(data)
    table = _decode_table(data)
    dispatcher = _dispatcher_semantics(data, table)
    cfg = _analyze_cfg(data, table)
    literals = _literal_bindings(data)
    consumed_literals = _consumed_literals(data)
    table_owner_claim_id = next(row["claim_id"] for row in coverage["existing_primary_ranges"] if row["range"] == [638184, 638244])
    producer = _producer_denominator(
        data,
        table_owner_claim_id=table_owner_claim_id,
        initializer_owner_claim_id=coverage["initializer_pointer_owner_claim_id"],
    )
    initializer = _initializer_binding(data)
    union_bytes = sum(end - start for start, end in PROMOTION_UNION_RANGES)
    post = {
        "classified_bytes": coverage["summary"]["classified_bytes"] + union_bytes,
        "unknown_bytes": coverage["summary"]["unknown_bytes"] - union_bytes,
        "claim_count": coverage["summary"]["claim_count"] + len(promotion_rows),
        "segment_count": coverage["summary"]["segment_count"] + segment_delta,
    }
    if post != {"classified_bytes": 6124601, "unknown_bytes": 166855, "claim_count": 14507, "segment_count": 16617}:
        raise ValueError("coverage post projection changed")
    claims = [{**row, "role": "primary", "promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown", "non_claims": dict(SCOPE), "limitations": list(LIMITATIONS)} for row in promotion_rows]
    bundle = b"".join(_bounded(data, start, end, "promotion") for start, end in PROMOTION_RANGES)
    literal_vector = [[row["instruction_offset"], row["literal_offset"], row["value"]] for row in literals]
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(data), "sha256": BASE_ROM_SHA256},
        "coverage_baseline": coverage,
        "coverage_projection": {"pre": dict(coverage["summary"]), "post": post, "classified_delta": union_bytes, "unknown_delta": -union_bytes, "claim_delta": len(claims), "segment_delta": segment_delta},
        "upstream_receipts": json.loads(json.dumps(UPSTREAM_RECEIPTS)),
        "roots": cfg["roots"],
        "cfg": cfg,
        "code_ranges": [list(interval) for interval in CODE_RANGES],
        "literal_ranges": [list(interval) for interval in LITERAL_RANGES],
        "unclassified_unknown_ranges": [list(interval) for interval in EXCLUDED_RANGES],
        "promotion_ranges": promotion_rows,
        "coverage_claims": claims,
        "literal_bindings": literals,
        "literal_binding_vector": literal_vector,
        "literal_binding_vector_sha256": _sha(_canonical(literal_vector)),
        "literal_summary": {"ref_count": len(literals), "word_count": len(literals), "bytes": 4},
        "consumed_literals": consumed_literals,
        "dispatcher": dispatcher,
        "initializer_binding": initializer,
        "producer_denominator": producer,
        "provenance": _provenance(candidate_027, coverage["existing_primary_ranges"], producer),
        "excluded_ranges": excluded,
        "promotion": {
            "ranges": [list(interval) for interval in PROMOTION_RANGES],
            "union_ranges": [list(interval) for interval in PROMOTION_UNION_RANGES],
            "union_range_count": len(PROMOTION_UNION_RANGES),
            "union_bytes": union_bytes,
            "range_count": len(PROMOTION_RANGES),
            "byte_count": union_bytes,
            "claim_count": len(promotion_rows),
            "total_bytes": union_bytes,
            "range_sha256": list(PROMOTION_RANGE_SHA256),
            "range_vector_sha256": RANGE_VECTOR_SHA256,
            "packed_bytes_sha256": PACKED_SHA256,
            "code_bytes": 86,
            "table_bytes": 12,
            "literal_bytes": 4,
            "pointer_bytes": 0,
        },
        "packed_layout": [{"range": list(row["range"]), "kind": row["kind"], "bundle_offset": sum(item["bytes"] for item in promotion_rows[:index]), "size": row["bytes"], "sha256": row["sha256"]} for index, row in enumerate(promotion_rows)],
        "packed_binary": {"file": BUNDLE_NAME, "size": len(bundle), "sha256": _sha(bundle)},
        "scope": dict(SCOPE),
        "limitations": list(LIMITATIONS),
        "summary": {
            **cfg["summary"],
            "literal_ref_count": len(literals),
            "literal_word_count": len(literals),
            "literal_bytes": 8,
            "pointer_bytes": 0,
            "promoted_bytes": len(bundle),
            "promotion_claim_count": len(claims),
            "promotion_range_count": len(promotion_rows),
            "producer_count": len(producer["producer_roles"]),
            "gap_exclusion_bytes": sum(row["bytes"] for row in excluded),
        },
    }
    if coverage_source is not None:
        payload["coverage_baseline_source"] = coverage_source
    return payload, bundle


def build_payload(root: Path | str, *, coverage_baseline_artifact: Path | str | None = None) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    return build_payload_from_rom(repository, _safe_file(repository, ROM_PATH).read_bytes(), coverage_baseline_artifact=coverage_baseline_artifact)


def _validate_output(root: Path, output: Path | str) -> tuple[Path, tuple[int, int]]:
    requested = Path(output).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    absolute = Path(os.path.abspath(requested))
    _reject_symlink_components(absolute)
    try:
        parent = absolute.parent.resolve(strict=True)
        parent.relative_to(root)
    except (OSError, ValueError) as error:
        raise ValueError("output parent must stay inside repository root") from error
    target = parent / absolute.name
    if target == root or not absolute.name:
        raise ValueError("output must not be repository root")
    if target.exists() or target.is_symlink():
        raise ValueError("output directory must be new and empty")
    parent_stat = os.stat(parent, follow_symlinks=False)
    return target, _identity(parent_stat)


def _open_directory_beneath(root: Path, directory: Path, expected_identity: tuple[int, int]) -> int:
    try:
        relative = directory.relative_to(root)
    except ValueError as error:
        raise ValueError("output parent escapes repository root") from error
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, flags)
    try:
        for part in relative.parts:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
    except OSError as error:
        os.close(descriptor)
        raise ValueError("output parent symlink or directory identity changed") from error
    if _identity(os.fstat(descriptor)) != expected_identity:
        os.close(descriptor)
        raise ValueError("output parent directory identity changed")
    return descriptor


def _write_file_at(directory_fd: int, name: str, raw: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, 0o644, dir_fd=directory_fd)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _remove_tree_at(parent_fd: int, name: str, expected_identity: tuple[int, int]) -> None:
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if _identity(named) != expected_identity:
        return
    if stat.S_ISLNK(named.st_mode) or not stat.S_ISDIR(named.st_mode):
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except OSError:
        try:
            os.rmdir(name, dir_fd=parent_fd)
        except OSError:
            pass
        return
    opened = _identity(os.fstat(descriptor))
    if opened != expected_identity:
        os.close(descriptor)
        return
    try:
        for child in os.listdir(descriptor):
            try:
                child_stat = os.stat(child, dir_fd=descriptor, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISDIR(child_stat.st_mode) and not stat.S_ISLNK(child_stat.st_mode):
                _remove_tree_at(descriptor, child, _identity(child_stat))
            else:
                try:
                    os.unlink(child, dir_fd=descriptor)
                except FileNotFoundError:
                    pass
    finally:
        os.close(descriptor)
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if _identity(current) == opened:
        try:
            os.rmdir(name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass


def _implementation(root: Path) -> dict[str, dict[str, Any]]:
    paths = {
        "exporter": Path("tools/export_rom_mp2k_dispatcher.py"),
        "verifier": Path("tools/verify_rom_mp2k_dispatcher.py"),
        "exporter_test": Path("tests/test_export_rom_mp2k_dispatcher.py"),
        "verifier_test": Path("tests/test_verify_rom_mp2k_dispatcher.py"),
    }
    return {role: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in paths.items()}


def _manifest(payload: dict[str, Any], payload_raw: bytes, bundle: bytes, output_artifact: str, implementation: dict[str, Any]) -> dict[str, Any]:
    semantic_contract = {
        "semantic_instruction_vector_sha256": payload["cfg"]["semantic_instruction_vector_sha256"],
        "edge_vector_sha256": payload["cfg"]["edge_vector_sha256"],
        "literal_binding_vector_sha256": payload["literal_binding_vector_sha256"],
        "producer_form_vector_sha256": payload["producer_denominator"]["producer_form_vector_sha256"],
        "range_vector_sha256": RANGE_VECTOR_SHA256,
        "packed_bytes_sha256": PACKED_SHA256,
    }
    command = ["python3", "tools/export_rom_mp2k_dispatcher.py"]
    if "coverage_baseline_source" in payload:
        command += ["--coverage-baseline-artifact", payload["coverage_baseline_source"]["artifact"]]
    command += ["--output", output_artifact]
    result = {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": "candidate",
        "rom": payload["rom"],
        "coverage_baseline": payload["coverage_baseline"],
        "coverage_projection": payload["coverage_projection"],
        "upstream_receipts": payload["upstream_receipts"],
        "promotion": payload["promotion"],
        "promotion_ranges": payload["promotion_ranges"],
        "semantic_contract": semantic_contract,
        "dispatcher": payload["dispatcher"],
        "initializer_binding": payload["initializer_binding"],
        "producer_denominator": payload["producer_denominator"],
        "provenance": payload["provenance"],
        "excluded_ranges": payload["excluded_ranges"],
        "scope": payload["scope"],
        "limitations": payload["limitations"],
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}, BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)}},
        "implementation": implementation,
        "producer": {"kind": "artifact-candidate-construction", "output_artifact": output_artifact, "command": command},
        "verification": {"status": "pending", "report": None},
        "summary": payload["summary"],
    }
    if "coverage_baseline_source" in payload:
        result["coverage_baseline_source"] = payload["coverage_baseline_source"]
    return result


def write_candidate(root: Path | str, output: Path | str = ARTIFACT_RELATIVE, *, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    repository = _validate_root(root)
    target, parent_identity = _validate_output(repository, output)
    payload, bundle = build_payload(repository, coverage_baseline_artifact=coverage_baseline_artifact)
    implementation = _implementation(repository)
    payload["implementation"] = implementation
    payload_raw = _canonical(payload)
    output_artifact = target.relative_to(repository).as_posix()
    manifest_raw = _canonical(_manifest(payload, payload_raw, bundle, output_artifact, implementation))
    parent_fd = _open_directory_beneath(repository, target.parent, parent_identity)
    created_identity: tuple[int, int] | None = None
    try:
        try:
            os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("output directory appeared during candidate construction")
        os.mkdir(target.name, 0o700, dir_fd=parent_fd)
        created_identity = _identity(os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False))
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        target_fd = os.open(target.name, flags, dir_fd=parent_fd)
        try:
            if _identity(os.fstat(target_fd)) != created_identity:
                raise ValueError("candidate output directory identity changed before open")
            _write_file_at(target_fd, PAYLOAD_NAME, payload_raw)
            _write_file_at(target_fd, BUNDLE_NAME, bundle)
            _write_file_at(target_fd, MANIFEST_NAME, manifest_raw)
            os.fsync(target_fd)
        finally:
            os.close(target_fd)
        if _identity(os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)) != created_identity:
            raise ValueError("candidate output directory identity changed")
        os.fsync(parent_fd)
    except Exception:
        if created_identity is not None:
            _remove_tree_at(parent_fd, target.name, created_identity)
        raise
    finally:
        os.close(parent_fd)
    return {"artifact": str(target), "payload_sha256": _sha(payload_raw), "bundle_sha256": _sha(bundle), "manifest_sha256": _sha(manifest_raw)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--coverage-baseline-artifact", type=Path)
    parser.add_argument("--output", type=Path, default=ARTIFACT_RELATIVE)
    args = parser.parse_args(argv)
    try:
        result = write_candidate(args.root, args.output, coverage_baseline_artifact=args.coverage_baseline_artifact)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"schema": SCHEMA, "verified": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
