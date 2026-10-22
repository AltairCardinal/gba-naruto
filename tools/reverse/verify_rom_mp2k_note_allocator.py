#!/usr/bin/env python3
"""Independently verify the frozen MP2K note allocator packet.

This verifier contains its own raw Thumb decoder and raw evidence rebuild.  It
intentionally has no dependency on the presentation decoder or on the export
module, so a candidate can be checked by a second implementation.
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
import secrets
import stat
import struct
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-mp2k-note-allocator-v1"
VERIFY_SCHEMA = "rom-mp2k-note-allocator-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
ROM_SHA256 = BASE_ROM_SHA256
COVERAGE_SHA256 = "ab315087593f23bfbcc96c66ac99b8bfd002e5c29cd462088dda343139f9ac27"
COVERAGE_SUMMARY = {"classified_bytes": 6_123_937, "unknown_bytes": 167_519, "claim_count": 14_499, "segment_count": 16_608}
PROJECTED_COVERAGE_SUMMARY = {"classified_bytes": 6_124_499, "unknown_bytes": 166_957, "claim_count": 14_503, "segment_count": 16_614}
PROMOTION_RANGES = [[0x09A6D8, 0x09A708], [0x09A708, 0x09A8FE], [0x09A900, 0x09A908], [0x09AF24, 0x09AF28]]
PROMOTION_RANGE_SHA256 = [
    "04988bf8e911a12b477d9aafa24342b68e83960a06796e555869cc67b24bd4d2",
    "4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e",
    "aea41d042f130b46329f8b5a5fdb976816ec280b367dc424f28bc624072867c1",
    "ee8951cbf1e4a1f69fce481a4537a84678e2615bc7e3f175ff69a97044ab7016",
]
PACKED_SHA256 = "3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c"
PROMOTION_UNION_RANGES = [[0x09A6D8, 0x09A8FE], [0x09A900, 0x09A908], [0x09AF24, 0x09AF28]]
RANGE_VECTOR_SHA256 = "bd9139f26305fea7813e7daf944d6a6e131861b31c3c98065b5e7d13bf65c88b"
CODE_RANGES = [PROMOTION_RANGES[0], PROMOTION_RANGES[1]]
LITERAL_RANGES = [PROMOTION_RANGES[2]]
ROOTS = [
    {"id": "ChnVolSetAsm", "file_offset": 0x09A6D8, "code_range": PROMOTION_RANGES[0]},
    {"id": "ply_note", "file_offset": 0x09A708, "code_range": PROMOTION_RANGES[1]},
]
ROOT_BY_OFFSET = {root["file_offset"]: root for root in ROOTS}
RETURN_OFFSETS = {0x09A6D8: 0x09A706, 0x09A708: 0x09A8FC}
EXPECTED_BLOCK_RANGES = {
    0x09A6D8: [[0x09A6D8, 0x09A6EE], [0x09A6EE, 0x09A6F0], [0x09A6F0, 0x09A702], [0x09A702, 0x09A704], [0x09A704, 0x09A708]],
    0x09A708: [
        [0x09A708, 0x09A730], [0x09A730, 0x09A73A], [0x09A73A, 0x09A744], [0x09A744, 0x09A74C], [0x09A74C, 0x09A74E], [0x09A74E, 0x09A75E], [0x09A75E, 0x09A766], [0x09A766, 0x09A76E], [0x09A76E, 0x09A770], [0x09A770, 0x09A786], [0x09A786, 0x09A788], [0x09A788, 0x09A78E], [0x09A78E, 0x09A796], [0x09A796, 0x09A79C], [0x09A79C, 0x09A7A0], [0x09A7A0, 0x09A7A4], [0x09A7A4, 0x09A7B2], [0x09A7B2, 0x09A7B4], [0x09A7B4, 0x09A7C2], [0x09A7C2, 0x09A7CA], [0x09A7CA, 0x09A7CC], [0x09A7CC, 0x09A7DA], [0x09A7DA, 0x09A7E0], [0x09A7E0, 0x09A7E8], [0x09A7E8, 0x09A7EA], [0x09A7EA, 0x09A7EC], [0x09A7EC, 0x09A7F2], [0x09A7F2, 0x09A7F4], [0x09A7F4, 0x09A802], [0x09A802, 0x09A80A], [0x09A80A, 0x09A810], [0x09A810, 0x09A814], [0x09A814, 0x09A81C], [0x09A81C, 0x09A820], [0x09A820, 0x09A826], [0x09A826, 0x09A82C], [0x09A82C, 0x09A82E], [0x09A82E, 0x09A834], [0x09A834, 0x09A838], [0x09A838, 0x09A83A], [0x09A83A, 0x09A83C], [0x09A83C, 0x09A842], [0x09A842, 0x09A848], [0x09A848, 0x09A84E], [0x09A84E, 0x09A85A], [0x09A85A, 0x09A85C], [0x09A85C, 0x09A868], [0x09A868, 0x09A86E], [0x09A86E, 0x09A876], [0x09A876, 0x09A89C], [0x09A89C, 0x09A8A6], [0x09A8A6, 0x09A8A8], [0x09A8A8, 0x09A8AE], [0x09A8AE, 0x09A8BC], [0x09A8BC, 0x09A8C2], [0x09A8C2, 0x09A8C4], [0x09A8C4, 0x09A8D4], [0x09A8D4, 0x09A8D6], [0x09A8D6, 0x09A8E0], [0x09A8E0, 0x09A8EE], [0x09A8EE, 0x09A8FE],
    ],
}
ALLOWED_CALLS = {
    0x09A6D8: {},
    0x09A708: {0x09A84A: (0x09AE14, "opaque_external_call"), 0x09A86A: (0x09A948, "opaque_external_call"), 0x09A872: (0x09B3E0, "opaque_external_call"), 0x09A898: (0x09A6D8, "included_root"), 0x09A8D0: (0x09A684, "opaque_existing_veneer"), 0x09A8DC: (0x09A998, "opaque_external_call")},
}
PRODUCER_FORMS = ("thumb_bl", "thumb_b", "thumb_b_conditional", "arm_b", "arm_bl", "bytewise_u32_entry", "bytewise_u32_thumb_pointer")
EXPECTED_PRODUCERS = {
    0x09A6D8: {"thumb_bl": [0x09A60C, 0x09A898], "thumb_b": [], "thumb_b_conditional": [], "arm_b": [], "arm_bl": [], "bytewise_u32_entry": [], "bytewise_u32_thumb_pointer": []},
    0x09A708: {"thumb_bl": [], "thumb_b": [], "thumb_b_conditional": [], "arm_b": [], "arm_bl": [], "bytewise_u32_entry": [], "bytewise_u32_thumb_pointer": [0x09AF24]},
}
LITERAL_EXPECTATIONS = [(0x09A71A, 0x4979, 0x09A900, 0x03007FF0), (0x09A720, 0x4978, 0x09A904, 0x084647A8)]
POINTER_RANGE = [0x09AF24, 0x09AF28]
POINTER_VALUE = 0x0809A709
POINTER_SHA256 = "ee8951cbf1e4a1f69fce481a4537a84678e2615bc7e3f175ff69a97044ab7016"
GAP_RANGES = [[0x09A6D2, 0x09A6D8], [0x09A8FE, 0x09A900], [0x09AEF4, 0x09AF24], [0x09AF28, 0x09AF34]]
GAP_SHA256 = ["83391c178e79facc3d1c0dd948f1d4e3fc46d08591ae8929948a5e028b724daa", "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7", "e3f15479ef984fff85b6ec764159375c16eeecf938f7671851aaf38d2a2211ae", "56573725cd7c0ffc2159a0d40123cef9750f00c2f444a04492a4b32117cf4bc7"]
SAPPY_BANK_PATH = Path("sequel/content/sappy-engine/bank.json")
SAPPY_BANK_SHA256 = "d71d8aff52746a61d59139d6ca4ccf3a9dd354b84ef90159276ca541cf82eb40"
SAPPY_RUNTIME_MANIFEST_PATH = Path("artifacts/sappy-engine-master-enable-ab-v1/manifest.json")
SAPPY_RUNTIME_MANIFEST_SHA256 = "62b97082417cc7d049b62bbb0bacfc92271e9924f674b13d6d5ee0fd8864fde8"
SAPPY_OWNER_RANGE = [0x09AE3C, 0x09AEF4]
SAPPY_OWNER_BYTES_SHA256 = "9586c815954c4b8a0c0d9872e7d500d128a540a2964a262b68da1e2df3cd9ef4"
UPSTREAM_PATHS = {
    "mplaymain": {"manifest": Path("artifacts/rom-mplaymain-scheduler-v1/manifest.json"), "payload": Path("artifacts/rom-mplaymain-scheduler-v1/rom-mplaymain-scheduler.json"), "exporter": Path("tools/export_rom_mplaymain_scheduler.py"), "verifier": Path("tools/verify_rom_mplaymain_scheduler.py"), "test": Path("tests/test_export_rom_mplaymain_scheduler.py")},
    "initializer": {"manifest": Path("artifacts/rom-m4a-initializer-chain-v1/manifest.json"), "payload": Path("artifacts/rom-m4a-initializer-chain-v1/rom-m4a-initializer-chain.json"), "exporter": Path("tools/export_rom_m4a_initializer_chain.py"), "verifier": Path("tools/verify_rom_m4a_initializer_chain.py"), "test": Path("tests/test_export_rom_m4a_initializer_chain.py")},
}
UPSTREAM_RECEIPTS = {
    "mplaymain": {"manifest_sha256": "43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d", "payload_sha256": "31bc026a8c83b3bf4af06746de2990a658bb86954a5aae31c45d63d68cf44f78", "exporter_sha256": "366c4e41db80c797bd01f36477a67243ac08f4d20d71e596c1332f273deed18d", "verifier_sha256": "c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a", "test_sha256": "e3804e5833b0d4249b286da8e1428397c02e8b04bd205e20c96e8ab1920b540c"},
    "initializer": {"manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c", "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd", "exporter_sha256": "4e0b8743247d9098a9d72667f4b2499abee1c71c45cd5a704feaa54f17a4ced9", "verifier_sha256": "5cd9ccf232ebb10c69e89962e9861add7675dfb935c6e6a293b16049fd6cec31", "test_sha256": "b6ed2f247641c74bb1631e4bfb0e449d48ec1be03a7af08c4eecabcc8c297326"},
    "sappy_bank_sha256": SAPPY_BANK_SHA256,
    "sappy_runtime_manifest_sha256": SAPPY_RUNTIME_MANIFEST_SHA256,
}
EXPECTED_UPSTREAM_RECEIPTS = json.loads(json.dumps(UPSTREAM_RECEIPTS))
PAYLOAD_NAME = "rom-mp2k-note-allocator.json"
BUNDLE_NAME = "rom-mp2k-note-allocator.bin"
MANIFEST_NAME = "manifest.json"
SCOPE = {"source_instruction_membership_complete": False, "natural_runtime_reachability": False, "global_code_producer_denominator_complete": False, "global_caller_denominator_complete": False, "global_indirect_producer_denominator_complete": False, "global_computed_producer_denominator_complete": False, "global_ram_writer_denominator_complete": False, "literal_target_semantics_claimed": False, "audio_behavior_proven": False, "editing_relocation_writeback_safe": False, "allocatable_free_space_proven": False}
LIMITATIONS = ["This candidate classifies exactly 550 bounded Thumb instruction bytes, 8 consumed literal bytes, and one 4-byte initializer-consumed Thumb pointer.", "The target-limited raw producer denominator proves the listed source forms and mixed provenance roles only; it is not a global caller/code/indirect/computed producer proof.", "natural runtime reachability, global RAM writer completeness, and global producer completeness remain unproven.", "literal target semantics, audio behavior, editing, writeback, relocation, and allocatable/free-space safety remain outside scope.", "The explicitly excluded neighboring ranges remain unknown and are not padding, reserved, free, or allocatable space."]
_EDGE_ORDER = {"branch_target": 0, "call_target": 1, "fallthrough": 2}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _bounded(rom: bytes, start: int, end: int, label: str = "ROM") -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"{label} range escapes ROM")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4), "little")


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _validate_root(root: Path | str) -> Path:
    value = Path(root).expanduser().resolve(strict=True)
    if not value.is_dir():
        raise ValueError("repository root is not a directory")
    return value


def _safe_file(root: Path, relative: Path | str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe repository path: {path}")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {path}")
    candidate = (root / path).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {path}") from error
    if not candidate.is_file():
        raise ValueError(f"required file missing: {path}")
    return candidate


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path.expanduser()))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {cursor}")


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
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("coverage baseline artifact path changed")
    return relative


def _validate_rom(rom: bytes) -> None:
    if len(rom) != ROM_SIZE:
        raise ValueError("ROM size changed")
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM SHA-256 changed")


def _raw_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
    if len(raw) >= 4:
        first, second = int.from_bytes(raw[:2], "little"), int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {"flow_kind": "call", "size": 4, "conditional": False, "target_offset": offset + 4 + _sign_extend(encoded, 23)}
    if len(raw) < 2:
        return None
    first = int.from_bytes(raw[:2], "little")
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        return {"flow_kind": "conditional_branch", "size": 2, "conditional": True, "target_offset": offset + 4 + _sign_extend((first & 0xFF) << 1, 9)}
    if first & 0xF800 == 0xE000:
        return {"flow_kind": "unconditional_branch", "size": 2, "conditional": False, "target_offset": offset + 4 + _sign_extend((first & 0x07FF) << 1, 12)}
    if first & 0xFF87 == 0x4700:
        return {"flow_kind": "bx", "size": 2, "conditional": False, "register": (first >> 3) & 0xF}
    return None


def _validate_stack_epilogue(rom: bytes) -> dict[str, Any]:
    expected = {0x09A8EE: "06b0", 0x09A8F0: "ffbc", 0x09A8F2: "8046", 0x09A8F4: "8946", 0x09A8F6: "9246", 0x09A8F8: "9b46", 0x09A8FA: "01bc", 0x09A8FC: "0047"}
    if any(_bounded(rom, offset, offset + 2).hex() != raw for offset, raw in expected.items()):
        raise ValueError("stack epilogue changed")
    return {"range": [0x09A8EE, 0x09A8FE], "steps": [[0x09A8EE, "add sp,#0x18"], [0x09A8F0, "pop {r0, r1, r2, r3, r4, r5, r6, r7}"], [0x09A8F2, "mov r8, r0"], [0x09A8F4, "mov sb, r1"], [0x09A8F6, "mov sl, r2"], [0x09A8F8, "mov fp, r3"], [0x09A8FA, "pop {r0}"], [0x09A8FC, "bx r0"]], "return_offset": 0x09A8FC, "exact": True}


def _decode_raw(rom: bytes, root_offset: int, offset: int) -> dict[str, Any]:
    start, end = ROOT_BY_OFFSET[root_offset]["code_range"]
    if offset & 1 or not start <= offset < end:
        raise ValueError("invalid raw Thumb offset")
    first = _u16(rom, offset)
    size = 4 if offset + 4 <= end and first & 0xF800 == 0xF000 and _u16(rom, offset + 2) & 0xF800 == 0xF800 else 2
    raw = _bounded(rom, offset, offset + size, "raw instruction")
    flow = _raw_flow(raw, offset)
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    next_offset = offset + size
    if flow and flow["flow_kind"] in {"call", "conditional_branch", "unconditional_branch"}:
        flow_kind = flow["flow_kind"]
        successors.append({"kind": "call_target" if flow_kind == "call" else "branch_target", "target_offset": flow["target_offset"], "target_mode": "thumb"})
        if flow_kind in {"call", "conditional_branch"}:
            successors.append({"kind": "fallthrough", "target_offset": next_offset, "target_mode": "thumb"})
    elif flow and flow["flow_kind"] == "bx":
        if offset == RETURN_OFFSETS[root_offset] and ((root_offset == 0x09A6D8 and flow["register"] == 14) or (root_offset == 0x09A708 and flow["register"] == 0)):
            flow_kind = "return"
        else:
            flow_kind = "indirect_branch"
            frontiers.append({"reason": "indirect_branch", "register": flow["register"]})
    else:
        flow_kind = "linear"
        successors.append({"kind": "fallthrough", "target_offset": next_offset, "target_mode": "thumb"})
    successors.sort(key=lambda row: (_EDGE_ORDER[row["kind"]], row["target_offset"]))
    return {"root": ROOT_BY_OFFSET[root_offset]["id"], "root_offset": root_offset, "offset": offset, "gba_address": _gba(offset), "mode": "thumb", "size": size, "raw_hex": raw.hex(), "bytes_sha256": _sha(raw), "flow_kind": flow_kind, "raw_flow_kind": flow["flow_kind"] if flow else None, "conditional": bool(flow and flow.get("conditional")), "successors": successors, "frontiers": frontiers}


def _walk_root(rom: bytes, root_offset: int) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    start, end = ROOT_BY_OFFSET[root_offset]["code_range"]
    pending = [start]
    seen: dict[int, dict[str, Any]] = {}
    calls: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in seen:
            continue
        node = _decode_raw(rom, root_offset, offset)
        seen[offset] = node
        for edge in node["successors"]:
            target = edge["target_offset"]
            if edge["kind"] == "call_target":
                expected = ALLOWED_CALLS[root_offset].get(offset)
                if expected is None or expected[0] != target:
                    raise ValueError(f"direct call denominator changed at 0x{offset:06X}")
                calls.append({"source_instruction_offset": offset, "source_gba_address": _gba(offset), "kind": "call_target", "target_offset": target, "target_gba_address": _gba(target), "target_mode": "thumb", "resolution": expected[1], "target_root": ROOT_BY_OFFSET[target]["id"] if expected[1] == "included_root" else None})
                continue
            if not start <= target < end or target & 1:
                raise ValueError("raw CFG escaped frozen root")
            heapq.heappush(pending, target)
    owners: dict[int, int] = {}
    for offset, node in seen.items():
        for byte_offset in range(offset, offset + node["size"]):
            if byte_offset in owners and owners[byte_offset] != offset:
                raise ValueError("raw CFG target lands in an instruction middle")
            owners[byte_offset] = offset
    if set(owners) != set(range(start, end)) or sum(node["size"] for node in seen.values()) != end - start:
        raise ValueError("raw CFG instruction denominator changed")
    if any(node["frontiers"] for node in seen.values()):
        raise ValueError("raw CFG has unresolved frontier")
    return seen, calls


def _build_blocks(rom: bytes, root_offset: int, nodes: dict[int, dict[str, Any]], calls: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predecessors: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for edge in node["successors"]:
            if edge["target_offset"] in nodes:
                predecessors[edge["target_offset"]].append((source, edge["kind"]))
    leaders = {root_offset}
    for offset, incoming in predecessors.items():
        if offset == root_offset:
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
            block_by_offset[offset] = f"block-{ROOT_BY_OFFSET[root_offset]['id']}-{leader:06x}"
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
        blocks.append({"id": block_by_offset[leader], "root": ROOT_BY_OFFSET[root_offset]["id"], "mode": "thumb", "range": [leader, block_end], "gba_range": [_gba(leader), _gba(block_end)], "instruction_count": len(members), "bytes_sha256": _sha(_bounded(rom, leader, block_end)), "terminator": {"offset": members[-1], "size": last["size"], "raw_hex": last["raw_hex"], "flow_kind": last["flow_kind"], "conditional": last["conditional"]}, "successors": []})
    if len(block_by_offset) != len(nodes):
        raise ValueError("raw CFG block partition omitted instructions")
    calls_by_source = {call["source_instruction_offset"]: call for call in calls}
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["offset"]
        for successor in nodes[source]["successors"]:
            target = successor["target_offset"]
            if target in nodes:
                record = {"source_block_id": block["id"], "source_instruction_offset": source, "kind": successor["kind"], "target_offset": target, "target_mode": "thumb", "target_block_id": block_by_offset[target], "target_scheduled": True, "resolution": "internal"}
                block["successors"].append(record)
                edges.append(record)
            elif successor["kind"] == "call_target" and source in calls_by_source:
                block["successors"].append({**calls_by_source[source], "source_block_id": block["id"]})
            else:
                raise ValueError("raw CFG non-call edge escaped root")
    edges.sort(key=lambda row: (row["source_instruction_offset"], _EDGE_ORDER[row["kind"]], row["target_offset"]))
    blocks.sort(key=lambda row: row["range"][0])
    return blocks, edges


def _rebuild_cfg(rom: bytes) -> dict[str, Any]:
    stack = _validate_stack_epilogue(rom)
    all_nodes: dict[int, dict[str, Any]] = {}
    blocks: list[dict[str, Any]] = []
    ordinary_edges: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    roots: list[dict[str, Any]] = []
    for root in ROOTS:
        nodes, root_calls = _walk_root(rom, root["file_offset"])
        root_blocks, root_edges = _build_blocks(rom, root["file_offset"], nodes, root_calls)
        all_nodes.update(nodes)
        blocks.extend(root_blocks)
        ordinary_edges.extend(root_edges)
        calls.extend(root_calls)
        roots.append({"id": root["id"], "file_offset": root["file_offset"], "gba_address": _gba(root["file_offset"]), "mode": "thumb", "code_range": list(root["code_range"]), "block_ranges": [list(block["range"]) for block in root_blocks], "instruction_count": len(nodes), "instruction_bytes": sum(node["size"] for node in nodes.values()), "internal_edge_count": len(root_edges)})
    if len(all_nodes) != 269 or sum(node["size"] for node in all_nodes.values()) != 550 or len(blocks) != 66 or len(ordinary_edges) != 98 or len(calls) != 6:
        raise ValueError("raw CFG denominator changed")
    if [root["block_ranges"] for root in roots] != [EXPECTED_BLOCK_RANGES[0x09A6D8], EXPECTED_BLOCK_RANGES[0x09A708]]:
        raise ValueError("raw CFG block ranges changed")
    calls.sort(key=lambda row: row["source_instruction_offset"])
    included = [call for call in calls if call["resolution"] == "included_root"]
    if len(included) != 1:
        raise ValueError("included-root call denominator changed")
    block_by_start = {block["range"][0]: block["id"] for block in blocks}
    source_block = next(block for block in blocks if block["range"][0] <= included[0]["source_instruction_offset"] < block["range"][1])
    all_edges = list(ordinary_edges) + [{**included[0], "source_block_id": source_block["id"], "target_block_id": block_by_start[0x09A6D8], "target_scheduled": True}]
    all_edges.sort(key=lambda row: (row["source_instruction_offset"], _EDGE_ORDER[row["kind"]], row["target_offset"]))
    returns = [{"offset": offset, "gba_address": _gba(offset), "mode": "thumb"} for offset in sorted((0x09A706, 0x09A8FC))]
    semantic = [[node["offset"], node["size"], node["raw_hex"], node["flow_kind"], [[edge["kind"], edge["target_offset"]] for edge in node["successors"]]] for node in (all_nodes[offset] for offset in sorted(all_nodes))]
    edge_vector = [[row["source_instruction_offset"], row["kind"], row["target_offset"], row["resolution"]] for row in all_edges]
    summary = {"instruction_count": 269, "instruction_bytes": 550, "code_bytes": 550, "block_count": 66, "ordinary_internal_edge_count": 98, "internal_edge_count": 99, "external_edge_count": 5, "direct_call_count": 6, "included_root_call_edge_count": 1, "opaque_external_call_count": 5, "structured_return_count": 2, "frontier_count": 0, "unresolved_frontier_count": 0, "budget_exhausted": False}
    return {"roots": roots, "code_ranges": [list(interval) for interval in CODE_RANGES], "instructions": [all_nodes[offset] for offset in sorted(all_nodes)], "blocks": blocks, "block_edges": all_edges, "calls": calls, "returns": returns, "frontiers": [], "stack_epilogue": stack, "semantic_instruction_vector": semantic, "semantic_instruction_vector_sha256": _sha(_canonical(semantic)), "edge_vector_sha256": _sha(_canonical(edge_vector)), "summary": summary}


def _thumb_bl_target(rom: bytes, offset: int) -> int | None:
    if offset < 0 or offset & 1 or offset + 4 > len(rom):
        return None
    first, second = _u16(rom, offset), _u16(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    return offset + 4 + _sign_extend(((first & 0x07FF) << 12) | ((second & 0x07FF) << 1), 23)


def _thumb_branch_target(rom: bytes, offset: int) -> tuple[str, int] | None:
    if offset < 0 or offset & 1 or offset + 2 > len(rom):
        return None
    first = _u16(rom, offset)
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        return "thumb_b_conditional", offset + 4 + _sign_extend((first & 0xFF) << 1, 9)
    if first & 0xF800 == 0xE000:
        return "thumb_b", offset + 4 + _sign_extend((first & 0x07FF) << 1, 12)
    return None


def _arm_branch_target(rom: bytes, offset: int) -> tuple[str, int] | None:
    if offset < 0 or offset & 3 or offset + 4 > len(rom):
        return None
    word = _u32(rom, offset)
    if word & 0x0E000000 != 0x0A000000:
        return None
    return ("arm_bl" if word & (1 << 24) else "arm_b", offset + 8 + _sign_extend((word & 0x00FFFFFF) << 2, 26))


def _pointer_occurrences(rom: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    result: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor < 0:
            return result
        result.append(cursor)
        cursor += 1


def _raw_producers(rom: bytes, mplay_claim_id: str) -> dict[str, Any]:
    forms = {target: {name: [] for name in PRODUCER_FORMS} for target in ROOT_BY_OFFSET}
    for offset in range(0, len(rom) - 3, 2):
        target = _thumb_bl_target(rom, offset)
        if target in forms:
            forms[target]["thumb_bl"].append(offset)
    for offset in range(0, len(rom) - 1, 2):
        branch = _thumb_branch_target(rom, offset)
        if branch and branch[1] in forms:
            forms[branch[1]][branch[0]].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        branch = _arm_branch_target(rom, offset)
        if branch and branch[1] in forms:
            forms[branch[1]][branch[0]].append(offset)
    for target in forms:
        forms[target]["bytewise_u32_entry"] = _pointer_occurrences(rom, ROM_BASE + target)
        forms[target]["bytewise_u32_thumb_pointer"] = _pointer_occurrences(rom, ROM_BASE + target + 1)
        for values in forms[target].values():
            values.sort()
    for target, expected in EXPECTED_PRODUCERS.items():
        if forms[target] != expected:
            raise ValueError("target producer form denominator changed")
    if not mplay_claim_id:
        raise ValueError("MPlayMain producer owner claim is missing")
    vector = [{"target_file_offset": target, "forms": forms[target]} for target in ROOT_BY_OFFSET]
    roles = [{"target_offset": 0x09A6D8, "form": "thumb_bl", "source_offset": 0x09A60C, "role": "preowned_provenance", "owner_claim_id": mplay_claim_id, "promoted": False}, {"target_offset": 0x09A6D8, "form": "thumb_bl", "source_offset": 0x09A898, "role": "included_root_call_edge", "owner_claim_id": None, "promoted": True}, {"target_offset": 0x09A708, "form": "bytewise_u32_thumb_pointer", "source_offset": 0x09AF24, "role": "promoted_entry_pointer", "owner_claim_id": None, "promoted": True}]
    return {"scan": {"mode": "raw-rom", "alignment_bytes": 2, "range": [0, ROM_SIZE], "forms": list(PRODUCER_FORMS)}, "thumb_bl": [0x09A60C, 0x09A898], "root_forms": {f"0x{target:06X}": forms[target] for target in ROOT_BY_OFFSET}, "producer_form_vector": vector, "producer_form_vector_sha256": _sha(_canonical(vector)), "producer_roles": roles, "producer_source_membership_by_role": {"preowned_provenance": True, "included_root_call_edge": True, "promoted_entry_pointer": True}, "all_producer_source_membership_proven": True, "all_producer_bytes_promoted": False, "target_limited_raw_producer_denominator_complete": True, "global_producer_denominator_complete": False, "computed_or_indirect_producer_denominator_complete": False}


def _load_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def analyze_coverage_baseline(coverage: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(coverage, dict) or coverage.get("schema") != "rom-byte-coverage-v1":
        raise ValueError("coverage baseline schema changed")
    summary = coverage.get("summary")
    if not isinstance(summary, dict) or {key: summary.get(key) for key in COVERAGE_SUMMARY} != COVERAGE_SUMMARY:
        raise ValueError("coverage baseline summary changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list):
        raise ValueError("coverage baseline segments missing")
    normalized: list[tuple[int, int, dict[str, Any]]] = []
    for segment in segments:
        raw_range = segment.get("range") if isinstance(segment, dict) else None
        if not isinstance(raw_range, list) or len(raw_range) != 2 or not all(isinstance(value, int) for value in raw_range) or raw_range[1] <= raw_range[0]:
            raise ValueError("coverage baseline has invalid segment range")
        normalized.append((raw_range[0], raw_range[1], segment))
    normalized.sort()
    for left, right in zip(normalized, normalized[1:]):
        if left[1] > right[0]:
            raise ValueError("coverage baseline segments overlap")
    target_segments: list[dict[str, Any]] = []
    for start, end in PROMOTION_RANGES:
        cursor = start
        for segment_start, segment_end, segment in normalized:
            if segment_end <= start:
                continue
            if segment_start >= end:
                break
            left, right = max(start, segment_start), min(end, segment_end)
            if left != cursor or right <= left or segment.get("primary_class") != "unknown" or segment.get("primary_claim_ids") not in (None, []):
                raise ValueError("coverage baseline promotion ranges are not whole-range unknown")
            target_segments.append({"range": [left, right], "primary_class": "unknown", "primary_claim_ids": []})
            cursor = right
        if cursor != end:
            raise ValueError("coverage baseline promotion ranges are not whole-range unknown")
    return {"path": COVERAGE_PATH.as_posix(), "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "summary": dict(COVERAGE_SUMMARY), "promotion_bytes": 562, "unknown_promotion_bytes": 562, "primary_overlap_bytes": 0, "all_promotion_bytes_unknown": True, "target_segments": target_segments}


def _coverage_from_file(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    return analyze_coverage_baseline(_load_object(raw, "coverage baseline"))


def _coverage_from_artifact(root: Path, artifact: Path | str) -> tuple[dict[str, Any], dict[str, Any]]:
    relative = _coverage_artifact_relative(root, artifact)
    manifest_path = _safe_file(root, relative / "manifest.json")
    manifest_raw = manifest_path.read_bytes()
    manifest = _load_object(manifest_raw, "coverage baseline artifact manifest")
    if _canonical(manifest) != manifest_raw or manifest.get("schema") != "rom-byte-coverage-prepromotion-baseline-v1" or manifest.get("artifact_status") != "accepted":
        raise ValueError("coverage baseline artifact manifest identity changed")
    coverage_meta = manifest.get("coverage")
    raw_meta = coverage_meta.get("raw") if isinstance(coverage_meta, dict) else None
    archive_meta = coverage_meta.get("archive") if isinstance(coverage_meta, dict) else None
    if not isinstance(raw_meta, dict) or raw_meta.get("canonical_json") is not True or raw_meta.get("schema") != "rom-byte-coverage-v1" or raw_meta.get("sha256") != COVERAGE_SHA256 or raw_meta.get("summary") != dict(COVERAGE_SUMMARY) or not isinstance(raw_meta.get("size"), int):
        raise ValueError("coverage baseline artifact raw identity changed")
    if not isinstance(archive_meta, dict) or archive_meta.get("compression") != "gzip" or not isinstance(archive_meta.get("file"), str) or not isinstance(archive_meta.get("size"), int) or not isinstance(archive_meta.get("sha256"), str):
        raise ValueError("coverage baseline artifact archive identity changed")
    archive_name = Path(archive_meta["file"])
    if archive_name.is_absolute() or ".." in archive_name.parts or archive_name.name != archive_meta["file"]:
        raise ValueError("coverage baseline artifact archive path changed")
    archive_raw = _safe_file(root, relative / archive_name).read_bytes()
    if len(archive_raw) != archive_meta["size"] or _sha(archive_raw) != archive_meta["sha256"]:
        raise ValueError("coverage baseline artifact archive identity changed")
    try:
        coverage_raw = gzip.decompress(archive_raw)
    except OSError as error:
        raise ValueError("coverage baseline artifact gzip is invalid") from error
    if len(coverage_raw) != raw_meta["size"] or _sha(coverage_raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline artifact raw identity changed")
    coverage = _load_object(coverage_raw, "coverage baseline artifact raw")
    if _canonical(coverage) != coverage_raw:
        raise ValueError("coverage baseline artifact raw is not canonical")
    baseline = analyze_coverage_baseline(coverage)
    return baseline, {"kind": "immutable-gzip-artifact", "artifact": relative.as_posix(), "manifest_sha256": _sha(manifest_raw), "archive_file": archive_name.as_posix(), "archive_size": len(archive_raw), "archive_sha256": _sha(archive_raw), "raw_size": len(coverage_raw), "raw_sha256": COVERAGE_SHA256, "recovery_kind": manifest.get("recovery", {}).get("kind")}


def _validate_upstream(root: Path) -> None:
    if UPSTREAM_RECEIPTS != EXPECTED_UPSTREAM_RECEIPTS:
        raise ValueError("upstream receipt contract changed")
    for name, paths in UPSTREAM_PATHS.items():
        for role, path in paths.items():
            if _sha(_safe_file(root, path).read_bytes()) != UPSTREAM_RECEIPTS[name][f"{role}_sha256"]:
                raise ValueError(f"upstream {name} {role} receipt changed")
        if _load_object(_safe_file(root, paths["manifest"]).read_bytes(), f"upstream {name} manifest").get("artifact_status") != "accepted":
            raise ValueError(f"upstream {name} artifact is not accepted")
    if _sha(_safe_file(root, SAPPY_BANK_PATH).read_bytes()) != SAPPY_BANK_SHA256 or _sha(_safe_file(root, SAPPY_RUNTIME_MANIFEST_PATH).read_bytes()) != SAPPY_RUNTIME_MANIFEST_SHA256:
        raise ValueError("sappy upstream receipt changed")


def _parse_upstream_ownership(root: Path) -> dict[str, Any]:
    mplay = _load_object(
        _safe_file(root, UPSTREAM_PATHS["mplaymain"]["payload"]).read_bytes(),
        "MPlayMain ownership payload",
    )
    claims = mplay.get("coverage_claims")
    if not isinstance(claims, list):
        raise ValueError("MPlayMain ownership claims are missing")
    source_candidates = []
    for claim in claims:
        if not isinstance(claim, dict) or claim.get("kind") != "code":
            continue
        claim_range = claim.get("range")
        if isinstance(claim_range, list) and len(claim_range) == 2 and all(isinstance(value, int) for value in claim_range) and claim_range[0] <= 0x09A60C < claim_range[1]:
            source_candidates.append(claim)
    if len(source_candidates) != 1 or not isinstance(source_candidates[0].get("id"), str) or not source_candidates[0]["id"]:
        raise ValueError("MPlayMain producer ownership is ambiguous")
    mplay_claim = source_candidates[0]
    mplay_range = list(mplay_claim["range"])

    bank = _load_object(_safe_file(root, SAPPY_BANK_PATH).read_bytes(), "sappy bank ownership")
    table_offset, entry_count, entry_size = bank.get("table_offset"), bank.get("entry_count"), bank.get("entry_size")
    entries = bank.get("entries")
    if not all(isinstance(value, int) for value in (table_offset, entry_count, entry_size)) or entry_count <= 0 or entry_size <= 0 or not isinstance(entries, list) or len(entries) != entry_count:
        raise ValueError("sappy bank ownership shape changed")
    table_offset_hex = bank.get("table_offset_hex")
    if table_offset_hex != f"0x{table_offset:06X}":
        raise ValueError("sappy bank table offset changed")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or entry.get("_index") != index or entry.get("_raw_offset") != table_offset + index * entry_size or entry.get("rom_offset") != table_offset + index * entry_size:
            raise ValueError("sappy bank ownership entry changed")
        code_hex = entry.get("code_hex")
        if not isinstance(code_hex, str) or len(code_hex) != entry_size * 2:
            raise ValueError("sappy bank owner code size changed")
        try:
            code_raw = bytes.fromhex(code_hex)
        except ValueError as error:
            raise ValueError("sappy bank owner code is invalid") from error
        if _sha(code_raw) != SAPPY_OWNER_BYTES_SHA256:
            raise ValueError("sappy bank owner bytes changed")
    owner_range = [table_offset, table_offset + entry_count * entry_size]
    if owner_range != SAPPY_OWNER_RANGE:
        raise ValueError("sappy bank owner range changed")
    owner_index = entries[0]["_index"]
    owner_claim_id = f"bank-{SAPPY_BANK_PATH.parent.name}-{owner_index:03d}"
    return {
        "mplay_claim_id": mplay_claim["id"],
        "mplay_claim_range": mplay_range,
        "sappy_owner_claim_id": owner_claim_id,
        "sappy_owner_range": owner_range,
    }


def _literal_bindings(rom: bytes, instructions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[tuple[int, int, int]] = []
    for node in instructions:
        if node["size"] != 2:
            continue
        raw = bytes.fromhex(node["raw_hex"])
        halfword = int.from_bytes(raw, "little")
        if halfword & 0xF800 == 0x4800:
            refs.append((node["offset"], halfword, ((node["offset"] + 4) & ~3) + (halfword & 0xFF) * 4))
    if len(refs) != 2:
        raise ValueError("literal reference denominator changed")
    rows = []
    for offset, raw_halfword, literal_offset, value in LITERAL_EXPECTATIONS:
        if (offset, raw_halfword, literal_offset) not in refs or _u32(rom, literal_offset) != value:
            raise ValueError("literal target or word changed")
        rows.append({"instruction_offset": offset, "raw": raw_halfword, "literal_offset": literal_offset, "value": value, "raw_hex": _bounded(rom, literal_offset, literal_offset + 4).hex()})
    if _bounded(rom, 0x09A900, 0x09A908).hex() != "f07f0003a8474608":
        raise ValueError("literal pool hole or word changed")
    return rows


def _pointer_binding(root: Path, rom: bytes, ownership: dict[str, Any]) -> dict[str, Any]:
    raw = _bounded(rom, *POINTER_RANGE)
    if _sha(raw) != POINTER_SHA256 or _u32(rom, POINTER_RANGE[0]) != POINTER_VALUE or _pointer_occurrences(rom, POINTER_VALUE) != [POINTER_RANGE[0]]:
        raise ValueError("entry pointer occurrence denominator changed")
    if _thumb_bl_target(rom, 0x09AA50) != 0x09AE3C or _u16(rom, 0x09AE40) != 0x1C05 or _u16(rom, 0x09AEC8) != 0x4816 or _u16(rom, 0x09AECA) != 0x63A8:
        raise ValueError("initializer pointer writer chain changed")
    if ((0x09AEC8 + 4) & ~3) + (_u16(rom, 0x09AEC8) & 0xFF) * 4 != 0x09AF24:
        raise ValueError("initializer pointer target changed")
    owner_range = ownership.get("sappy_owner_range")
    owner_claim_id = ownership.get("sappy_owner_claim_id")
    if owner_range != SAPPY_OWNER_RANGE or not isinstance(owner_claim_id, str) or not owner_claim_id:
        raise ValueError("sappy owner provenance changed")
    if _sha(_bounded(rom, *owner_range)) != SAPPY_OWNER_BYTES_SHA256:
        raise ValueError("sappy owner bytes changed")
    if _u16(rom, 0x09A460) != 0x488A or _u16(rom, 0x09A4EA) != 0x7811 or _u16(rom, 0x09A4F0) != 0x79E9 or _u16(rom, 0x09A4FE) != 0x29CF or _u16(rom, 0x09A502) != 0x4640 or _u16(rom, 0x09A504) != 0x6B83 or _u16(rom, 0x09A508) != 0x38CF or _thumb_bl_target(rom, 0x09A50E) != 0x09A684:
        raise ValueError("SoundInfo consumer chain changed")
    sound_info_cell = ((0x09A460 + 4) & ~3) + ((_u16(rom, 0x09A460) & 0xFF) * 4)
    if sound_info_cell != 0x09A68C or _u16(rom, 0x09A462) != 0x6800 or _u32(rom, sound_info_cell) != 0x03007FF0:
        raise ValueError("SoundInfo fixed cell dereference changed")
    if _u16(rom, 0x09A500) != 0xD308 or _u16(rom, 0x09A684) != 0x4718:
        raise ValueError("SoundInfo unsigned branch or bx r3 veneer changed")
    return {"range": list(POINTER_RANGE), "raw_hex": raw.hex(), "value": f"0x{POINTER_VALUE:08X}", "occurrences": [POINTER_RANGE[0]], "occurrence_count": 1, "writer": {"chain": [[0x09AA50, 0x09AE3C], [0x09AE40, "r0->r5"], [0x09AEC8, 0x09AF24], [0x09AECA, "[r5,#0x38]"], [0x09AE3C, 0x09AEF4]], "initializer_root": 0x09AE3C, "owner_claim_id": owner_claim_id, "owner_range": list(owner_range), "owner_bytes_sha256": SAPPY_OWNER_BYTES_SHA256, "sappy_bank_sha256": SAPPY_BANK_SHA256, "runtime_manifest_sha256": SAPPY_RUNTIME_MANIFEST_SHA256}, "consumer": {"sound_info_load": 0x09A460, "sound_info_dereference": {"offset": 0x09A462, "raw": 0x6800, "kind": "ldr_word_from_fixed_cell"}, "sound_info_fixed_cell": {"offset": sound_info_cell, "value": 0x03007FF0, "raw_hex": _bounded(rom, sound_info_cell, sound_info_cell + 4).hex()}, "command_source": "u8", "cmp": {"offset": 0x09A4FE, "immediate": 0xCF}, "unsigned_branch": {"offset": 0x09A500, "raw": 0xD308, "kind": "blo"}, "accepted_argument_domain": [0, 48], "accepted_value_count": 49, "load_offset": 0x09A502, "load_offset_end": 0x09A504, "subtract": {"offset": 0x09A508, "immediate": 0xCF}, "call_offset": 0x09A50E, "call_target": 0x09A684, "veneer": {"offset": 0x09A684, "raw": 0x4718, "kind": "bx_r3"}}, "global_ram_writer_denominator_complete": False}


def _excluded(rom: bytes) -> list[dict[str, Any]]:
    rows = []
    for interval, digest in zip(GAP_RANGES, GAP_SHA256):
        if _sha(_bounded(rom, *interval)) != digest:
            raise ValueError("excluded-neighbor bytes changed")
        rows.append({"range": list(interval), "bytes": interval[1] - interval[0], "sha256": digest, "promoted": False, "semantic_class": "unknown", "promotion_excluded": True})
    return rows


def _promotion_rows(rom: bytes) -> list[dict[str, Any]]:
    _validate_promotion_ranges(rom)
    specs = [("mp2k-channel-gain-code-09a6d8", "bounded_thumb_code", "thumb", "armv4t_mp2k_channel_gain_thumb_code", "mp2k_channel_gain_bounded_thumb_code"), ("mp2k-note-allocator-code-09a708", "bounded_thumb_code", "thumb", "armv4t_mp2k_note_allocator_thumb_code", "mp2k_note_allocator_bounded_thumb_code"), ("mp2k-note-allocator-literals-09a900", "consumed_literals", None, "mp2k_note_allocator_consumed_literals", "mp2k_note_allocator_consumed_literals"), ("mp2k-note-entry-pointer-09af24", "initializer_consumed_thumb_pointer", None, "mp2k_initializer_consumed_thumb_pointer", "mp2k_note_entry_initializer_consumed_thumb_pointer")]
    return [{"id": spec[0], "kind": spec[1], "range": list(PROMOTION_RANGES[index]), "size": PROMOTION_RANGES[index][1] - PROMOTION_RANGES[index][0], "sha256": PROMOTION_RANGE_SHA256[index], "mode": spec[2], "semantic_class": spec[3], "claim_kind": spec[4]} for index, spec in enumerate(specs)]


def _validate_promotion_ranges(rom: bytes) -> None:
    for interval, digest in zip(PROMOTION_RANGES, PROMOTION_RANGE_SHA256):
        if _sha(_bounded(rom, *interval)) != digest:
            raise ValueError("promotion range bytes changed")


def _expected_payload(root: Path, rom: bytes, *, coverage_baseline_artifact: Path | str | None = None) -> tuple[dict[str, Any], bytes]:
    _validate_rom(rom)
    _validate_promotion_ranges(rom)
    _validate_upstream(root)
    ownership = _parse_upstream_ownership(root)
    coverage, source = (_coverage_from_file(root), None) if coverage_baseline_artifact is None else _coverage_from_artifact(root, coverage_baseline_artifact)
    rows = _promotion_rows(rom)
    excluded = _excluded(rom)
    cfg = _rebuild_cfg(rom)
    literals = _literal_bindings(rom, cfg["instructions"])
    producers = _raw_producers(rom, ownership["mplay_claim_id"])
    if not ownership["mplay_claim_range"][0] <= 0x09A60C < ownership["mplay_claim_range"][1]:
        raise ValueError("MPlayMain producer source is outside its owner claim")
    pointer = _pointer_binding(root, rom, ownership)
    bundle = b"".join(_bounded(rom, *interval) for interval in PROMOTION_RANGES)
    if _sha(bundle) != PACKED_SHA256 or _sha(json.dumps(PROMOTION_UNION_RANGES, sort_keys=True, separators=(",", ":")) .encode() + b"\n") != RANGE_VECTOR_SHA256:
        raise ValueError("promotion bundle or vector changed")
    post = {"classified_bytes": coverage["summary"]["classified_bytes"] + 562, "unknown_bytes": coverage["summary"]["unknown_bytes"] - 562, "claim_count": coverage["summary"]["claim_count"] + 4, "segment_count": coverage["summary"]["segment_count"] + 6}
    if post != PROJECTED_COVERAGE_SUMMARY:
        raise ValueError("coverage post projection changed")
    claims = [{**row, "role": "primary", "promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown", "non_claims": dict(SCOPE), "limitations": list(LIMITATIONS)} for row in rows]
    literal_vector = [[row["instruction_offset"], row["literal_offset"], row["value"]] for row in literals]
    payload = {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": BASE_ROM_SHA256}, "coverage_baseline": coverage, "coverage_projection": {"pre": dict(coverage["summary"]), "post": post, "classified_delta": 562, "unknown_delta": -562, "claim_delta": 4, "segment_delta": 6}, "upstream_receipts": json.loads(json.dumps(UPSTREAM_RECEIPTS)), "roots": cfg["roots"], "cfg": cfg, "code_ranges": [list(interval) for interval in CODE_RANGES], "literal_ranges": [list(interval) for interval in LITERAL_RANGES], "unclassified_unknown_ranges": [list(interval) for interval in GAP_RANGES], "promotion_ranges": rows, "coverage_claims": claims, "literal_bindings": literals, "literal_binding_vector": literal_vector, "literal_binding_vector_sha256": _sha(_canonical(literal_vector)), "literal_summary": {"ref_count": 2, "word_count": 2, "bytes": 8}, "producer_denominator": producers, "entry_pointer": pointer, "excluded_ranges": excluded, "promotion": {"ranges": [list(interval) for interval in PROMOTION_RANGES], "union_ranges": [list(interval) for interval in PROMOTION_UNION_RANGES], "union_range_count": 3, "union_bytes": 562, "range_count": 4, "byte_count": 562, "range_sha256": list(PROMOTION_RANGE_SHA256), "range_vector_sha256": RANGE_VECTOR_SHA256, "packed_bytes_sha256": PACKED_SHA256, "code_bytes": 550, "literal_bytes": 8, "pointer_bytes": 4}, "packed_layout": [{"range": list(row["range"]), "kind": row["kind"], "bundle_offset": sum(item["size"] for item in rows[:index]), "size": row["size"], "sha256": row["sha256"]} for index, row in enumerate(rows)], "packed_binary": {"file": BUNDLE_NAME, "size": len(bundle), "sha256": _sha(bundle)}, "scope": dict(SCOPE), "limitations": list(LIMITATIONS), "summary": {**cfg["summary"], "literal_ref_count": 2, "literal_word_count": 2, "literal_bytes": 8, "pointer_bytes": 4, "promoted_bytes": 562, "promotion_claim_count": 4, "promotion_range_count": 4, "producer_count": 3, "gap_exclusion_bytes": sum(row["bytes"] for row in excluded)}}
    if source is not None:
        payload["coverage_baseline_source"] = source
    return payload, bundle


def independent_rebuild(root: Path | str, rom: bytes, *, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    repository = _validate_root(root)
    payload, bundle = _expected_payload(repository, bytes(rom), coverage_baseline_artifact=coverage_baseline_artifact)
    return {"schema": VERIFY_SCHEMA, "verified": True, "contract_ok": True, "summary": payload["summary"], "producer_denominator": payload["producer_denominator"], "literal_bindings": payload["literal_bindings"], "bundle_sha256": _sha(bundle), "bundle_size": len(bundle), "scope": payload["scope"], "limitations": payload["limitations"], "payload": payload}


def _artifact_path(root: Path, artifact_dir: Path | str) -> Path:
    requested = Path(artifact_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    absolute = Path(os.path.abspath(requested))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact path uses a symlink")
    requested = requested.resolve(strict=True)
    try:
        requested.relative_to(root)
    except ValueError as error:
        raise ValueError("artifact must stay inside repository root") from error
    if not requested.is_dir():
        raise ValueError("artifact is not a directory")
    return requested


def _implementation(root: Path) -> dict[str, dict[str, Any]]:
    paths = {"exporter": Path("tools/export_rom_mp2k_note_allocator.py"), "verifier": Path("tools/verify_rom_mp2k_note_allocator.py"), "exporter_test": Path("tests/test_export_rom_mp2k_note_allocator.py"), "verifier_test": Path("tests/test_verify_rom_mp2k_note_allocator.py")}
    return {role: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in paths.items()}


def _load_artifact(root: Path, artifact_dir: Path | str) -> tuple[Path, dict[str, Any], bytes, dict[str, Any], dict[str, bytes]]:
    artifact = _artifact_path(root, artifact_dir)
    expected_names = {MANIFEST_NAME, PAYLOAD_NAME, BUNDLE_NAME}
    entries = list(artifact.iterdir())
    entry_names = {entry.name for entry in entries}
    if entry_names not in (expected_names, expected_names | {"candidate"}):
        raise ValueError("artifact file set changed")
    for entry in entries:
        if entry.is_symlink():
            raise ValueError("artifact file set changed")
        if entry.name == "candidate":
            if not entry.is_dir():
                raise ValueError("artifact file set changed")
        elif not entry.is_file():
            raise ValueError("artifact file set changed")
    files = {name: (artifact / name).read_bytes() for name in expected_names}
    manifest, payload = _load_object(files[MANIFEST_NAME], "artifact manifest"), _load_object(files[PAYLOAD_NAME], "artifact payload")
    if _canonical(manifest) != files[MANIFEST_NAME] or _canonical(payload) != files[PAYLOAD_NAME]:
        raise ValueError("artifact JSON is not canonical")
    status = manifest.get("artifact_status")
    if status == "candidate" and "candidate" in entry_names:
        raise ValueError("candidate artifact contains an unexpected embedded candidate")
    if status == "accepted" and "candidate" not in entry_names:
        raise ValueError("accepted artifact is missing its embedded candidate")
    return artifact, payload, files[BUNDLE_NAME], manifest, files


def _validated_artifact_reference(root: Path, value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} artifact path changed")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != value:
        raise ValueError(f"{label} artifact path changed")
    resolved = (root / relative).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"{label} artifact path changed") from error
    return value


def _candidate_identity(value: Any, label: str) -> dict[str, str]:
    keys = {"artifact_status", "manifest_sha256", "payload_sha256", "bundle_sha256"}
    if not isinstance(value, dict) or set(value) != keys or value.get("artifact_status") != "candidate":
        raise ValueError(f"{label} candidate identity changed")
    for key in ("manifest_sha256", "payload_sha256", "bundle_sha256"):
        digest = value.get(key)
        if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"{label} candidate identity changed")
    return value


def _structural_cfg_matches(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    if actual.get("summary") != expected["summary"] or actual.get("roots") != expected["roots"] or actual.get("calls") != expected["calls"] or actual.get("returns") != expected["returns"] or actual.get("frontiers") != expected["frontiers"] or actual.get("stack_epilogue") != expected["stack_epilogue"]:
        raise ValueError("artifact CFG summary or roots changed")
    for key in ("semantic_instruction_vector_sha256", "edge_vector_sha256"):
        if actual.get(key) != expected[key]:
            raise ValueError("artifact CFG vector changed")
    actual_nodes, expected_nodes = actual.get("instructions"), expected.get("instructions")
    if not isinstance(actual_nodes, list) or len(actual_nodes) != len(expected_nodes):
        raise ValueError("artifact instruction evidence changed")
    for left, right in zip(actual_nodes, expected_nodes):
        if {key: left.get(key) for key in ("offset", "size", "raw_hex", "bytes_sha256", "flow_kind", "raw_flow_kind", "conditional", "successors", "frontiers")} != {key: right.get(key) for key in ("offset", "size", "raw_hex", "bytes_sha256", "flow_kind", "raw_flow_kind", "conditional", "successors", "frontiers")}:
            raise ValueError("artifact instruction evidence changed")
    if actual.get("blocks") != expected.get("blocks") or actual.get("block_edges") != expected.get("block_edges"):
        # Presentation fields are not independently decoded, but all raw block
        # boundaries, terminators, and edge vectors are checked below.
        if len(actual.get("blocks", [])) != len(expected.get("blocks", [])) or len(actual.get("block_edges", [])) != len(expected.get("block_edges", [])):
            raise ValueError("artifact block evidence changed")
        for left, right in zip(actual["blocks"], expected["blocks"]):
            block_keys = ("id", "root", "range", "instruction_count", "bytes_sha256", "successors")
            if {key: left.get(key) for key in block_keys} != {key: right.get(key) for key in block_keys}:
                raise ValueError("artifact block evidence changed")
            left_terminator, right_terminator = left.get("terminator", {}), right.get("terminator", {})
            terminator_keys = ("offset", "size", "raw_hex", "flow_kind", "conditional")
            if {key: left_terminator.get(key) for key in terminator_keys} != {key: right_terminator.get(key) for key in terminator_keys}:
                raise ValueError("artifact block evidence changed")
        for left, right in zip(actual["block_edges"], expected["block_edges"]):
            if left != right:
                raise ValueError("artifact edge evidence changed")


def _verify_artifact(root: Path | str, artifact_dir: Path | str, *, allow_candidate: bool = False, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    repository = _validate_root(root)
    artifact, payload, bundle, manifest, files = _load_artifact(repository, artifact_dir)
    status = manifest.get("artifact_status")
    if status == "candidate" and not allow_candidate:
        raise ValueError("candidate artifact requires explicit opt-in")
    if status not in ({"candidate", "accepted"} if allow_candidate else {"accepted"}):
        raise ValueError("artifact status changed")
    if status == "accepted" and coverage_baseline_artifact is not None:
        raise ValueError("accepted artifact does not accept an external coverage baseline")
    source = payload.get("coverage_baseline_source")
    explicit = _coverage_artifact_relative(repository, coverage_baseline_artifact) if coverage_baseline_artifact is not None else None
    if source is not None:
        if not isinstance(source, dict) or not isinstance(source.get("artifact"), str):
            raise ValueError("coverage baseline source metadata changed")
        source_relative = _coverage_artifact_relative(repository, source["artifact"])
        if source_relative.as_posix() != source["artifact"]:
            raise ValueError("coverage baseline source path changed")
        if explicit is not None and explicit != source_relative:
            raise ValueError("explicit coverage baseline artifact conflicts with payload source")
        effective = source_relative
    else:
        effective = explicit
    if status == "accepted" and effective is None:
        raise ValueError("accepted artifact is missing its immutable coverage baseline source")
    expected, expected_bundle = _expected_payload(repository, _safe_file(repository, ROM_PATH).read_bytes(), coverage_baseline_artifact=effective)
    if bundle != expected_bundle:
        raise ValueError("packed binary differs from raw-ROM reconstruction")
    if payload.get("implementation") != _implementation(repository):
        raise ValueError("implementation receipt changed")
    _structural_cfg_matches(payload.get("cfg", {}), expected["cfg"])
    comparable = {key: value for key, value in expected.items() if key != "cfg"}
    actual_comparable = {key: value for key, value in payload.items() if key not in {"cfg", "implementation"}}
    if actual_comparable != comparable:
        raise ValueError("payload contract changed")
    base_manifest_keys = {"schema", "artifact_schema", "artifact_status", "rom", "coverage_baseline", "coverage_projection", "upstream_receipts", "promotion", "promotion_ranges", "semantic_contract", "producer_denominator", "entry_pointer", "excluded_ranges", "scope", "limitations", "files", "implementation", "producer", "verification", "summary"}
    if source is not None:
        base_manifest_keys.add("coverage_baseline_source")
    expected_manifest_keys = base_manifest_keys if status == "candidate" else base_manifest_keys | {"acceptance", "verifier"}
    if set(manifest) != expected_manifest_keys or manifest.get("schema") != PROMOTION_SCHEMA or manifest.get("artifact_schema") != SCHEMA:
        raise ValueError("manifest schema changed")
    if manifest.get("files") != {PAYLOAD_NAME: {"size": len(files[PAYLOAD_NAME]), "sha256": _sha(files[PAYLOAD_NAME])}, BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)}}:
        raise ValueError("manifest file receipts changed")
    semantic = {"semantic_instruction_vector_sha256": expected["cfg"]["semantic_instruction_vector_sha256"], "edge_vector_sha256": expected["cfg"]["edge_vector_sha256"], "literal_binding_vector_sha256": expected["literal_binding_vector_sha256"], "producer_form_vector_sha256": expected["producer_denominator"]["producer_form_vector_sha256"], "range_vector_sha256": RANGE_VECTOR_SHA256, "packed_bytes_sha256": PACKED_SHA256}
    mirrored = {"rom": expected["rom"], "coverage_baseline": expected["coverage_baseline"], "coverage_projection": expected["coverage_projection"], "upstream_receipts": expected["upstream_receipts"], "promotion": expected["promotion"], "promotion_ranges": expected["promotion_ranges"], "semantic_contract": semantic, "producer_denominator": expected["producer_denominator"], "entry_pointer": expected["entry_pointer"], "excluded_ranges": expected["excluded_ranges"], "scope": expected["scope"], "limitations": expected["limitations"], "implementation": _implementation(repository), "summary": expected["summary"]}
    if source is not None:
        mirrored["coverage_baseline_source"] = source
    if any(manifest.get(key) != value for key, value in mirrored.items()):
        raise ValueError("manifest mirrored contract changed")
    artifact_relative = artifact.relative_to(repository).as_posix()
    acceptance_command: list[str] | None = None
    if status == "candidate":
        producer_output = artifact_relative
    else:
        acceptance = manifest.get("acceptance")
        if not isinstance(acceptance, dict):
            raise ValueError("accepted artifact acceptance receipt changed")
        candidate_artifact = _validated_artifact_reference(repository, acceptance.get("candidate_artifact"), "candidate")
        expected_candidate_artifact = (artifact / "candidate").relative_to(repository).as_posix()
        if candidate_artifact != expected_candidate_artifact:
            raise ValueError("accepted artifact candidate path changed")
        source_candidate_artifact = _validated_artifact_reference(repository, acceptance.get("source_candidate_artifact"), "source candidate")
        source_candidate_identity = _candidate_identity(acceptance.get("source_candidate_identity"), "source")
        output_artifact = _validated_artifact_reference(repository, acceptance.get("output_artifact"), "output")
        if output_artifact != artifact_relative:
            raise ValueError("accepted artifact output path changed")
        candidate_directory = _artifact_path(repository, candidate_artifact)
        if candidate_directory == artifact:
            raise ValueError("accepted artifact cannot cite itself as its candidate")
        candidate_report = _verify_artifact(repository, candidate_directory, allow_candidate=True)
        if candidate_report.get("artifact_status") != "candidate":
            raise ValueError("accepted artifact must cite a verified candidate")
        _, _, candidate_bundle, candidate_manifest, candidate_files = _load_artifact(repository, candidate_directory)
        candidate_identity = {
            "artifact_status": "candidate",
            "manifest_sha256": _sha(candidate_files[MANIFEST_NAME]),
            "payload_sha256": _sha(candidate_files[PAYLOAD_NAME]),
            "bundle_sha256": _sha(candidate_bundle),
        }
        _candidate_identity(acceptance.get("candidate_identity"), "embedded")
        if candidate_files[PAYLOAD_NAME] != files[PAYLOAD_NAME] or candidate_bundle != bundle:
            raise ValueError("accepted artifact differs from cited candidate")
        reconstructed_source_manifest = dict(candidate_manifest)
        reconstructed_source_manifest["producer"] = {
            "kind": "artifact-candidate-construction",
            "output_artifact": source_candidate_artifact,
            "command": [
                "python3",
                "tools/export_rom_mp2k_note_allocator.py",
                "--coverage-baseline-artifact",
                source["artifact"],
                "--output",
                source_candidate_artifact,
            ],
        }
        expected_source_candidate_identity = {
            "artifact_status": "candidate",
            "manifest_sha256": _sha(_canonical(reconstructed_source_manifest)),
            "payload_sha256": _sha(candidate_files[PAYLOAD_NAME]),
            "bundle_sha256": _sha(candidate_bundle),
        }
        if source_candidate_identity != expected_source_candidate_identity:
            raise ValueError("source candidate identity changed")
        acceptance_command = [
            "python3",
            "tools/verify_rom_mp2k_note_allocator.py",
            source_candidate_artifact,
            "--accept-to",
            output_artifact,
        ]
        expected_acceptance = {
            "kind": "independent-candidate-acceptance",
            "candidate_artifact": candidate_artifact,
            "source_candidate_artifact": source_candidate_artifact,
            "source_candidate_identity": source_candidate_identity,
            "output_artifact": output_artifact,
            "command": acceptance_command,
            "candidate_identity": candidate_identity,
        }
        if acceptance != expected_acceptance:
            raise ValueError("accepted artifact acceptance receipt changed")
        producer_output = candidate_artifact

    expected_producer = {
        "kind": "artifact-candidate-construction",
        "output_artifact": producer_output,
        "command": ["python3", "tools/export_rom_mp2k_note_allocator.py"]
        + (["--coverage-baseline-artifact", source["artifact"]] if source is not None else [])
        + ["--output", producer_output],
    }
    if manifest.get("producer") != expected_producer:
        raise ValueError("manifest producer command changed")
    if status == "candidate":
        if manifest.get("verification") != {"status": "pending", "report": None}:
            raise ValueError("candidate verification metadata changed")
    else:
        verifier_receipt = {
            "path": "tools/verify_rom_mp2k_note_allocator.py",
            "sha256": _implementation(repository)["verifier"]["sha256"],
            "command": acceptance_command,
        }
        if manifest.get("verifier") != verifier_receipt:
            raise ValueError("accepted verifier receipt changed")
        if manifest.get("verification") != {
            "status": "verified",
            "contract_ok": True,
            "schema": VERIFY_SCHEMA,
            "summary": expected["summary"],
        }:
            raise ValueError("accepted verification receipt changed")
    return {"schema": VERIFY_SCHEMA, "verified": True, "contract_ok": True, "artifact_status": status, "artifact": str(artifact), "summary": expected["summary"], "scope": expected["scope"], "limitations": expected["limitations"], "bundle_sha256": _sha(bundle), "payload_sha256": _sha(files[PAYLOAD_NAME]), "manifest_sha256": _sha(files[MANIFEST_NAME]), "coverage_baseline_sha256": COVERAGE_SHA256}


def verify_artifact(root: Path | str, artifact_dir: Path | str, *, allow_candidate: bool = False, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    return _verify_artifact(root, artifact_dir, allow_candidate=allow_candidate, coverage_baseline_artifact=coverage_baseline_artifact)


def _validate_output(root: Path, output: Path | str) -> Path:
    requested = Path(output).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    absolute = Path(os.path.abspath(requested))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"output path uses a symlink: {cursor}")
    try:
        parent = absolute.parent.resolve(strict=True)
    except OSError as error:
        raise ValueError("output parent must already exist") from error
    if not parent.is_dir():
        raise ValueError("output parent must be a directory")
    try:
        parent.relative_to(root)
    except ValueError as error:
        raise ValueError("output must stay inside repository root") from error
    value = parent / absolute.name
    if value == root or not absolute.name:
        raise ValueError("output must not be repository root")
    if value.exists() or value.is_symlink():
        raise ValueError("output directory must not already exist")
    return value


def _open_directory_beneath(root: Path, directory: Path) -> int:
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


def _remove_tree_at(parent_fd: int, name: str, expected_identity: tuple[int, int] | None = None) -> None:
    try:
        named_stat = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if expected_identity is not None and _identity(named_stat) != expected_identity:
        return
    if not stat.S_ISDIR(named_stat.st_mode) or stat.S_ISLNK(named_stat.st_mode):
        if expected_identity is None:
            try:
                os.unlink(name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError:
        return
    opened_identity = _identity(os.fstat(directory_fd))
    if expected_identity is not None and opened_identity != expected_identity:
        os.close(directory_fd)
        return
    try:
        for child in os.listdir(directory_fd):
            try:
                child_stat = os.stat(child, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISDIR(child_stat.st_mode) and not stat.S_ISLNK(child_stat.st_mode):
                _remove_tree_at(directory_fd, child, _identity(child_stat))
            else:
                try:
                    os.unlink(child, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
    finally:
        os.close(directory_fd)
    try:
        current_stat = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if _identity(current_stat) != opened_identity:
        return
    try:
        os.rmdir(name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


def accept_candidate(root: Path | str, candidate: Path | str, output: Path | str) -> dict[str, Any]:
    repository = _validate_root(root)
    report = verify_artifact(repository, candidate, allow_candidate=True)
    if report["artifact_status"] != "candidate":
        raise ValueError("only a candidate artifact can be accepted")
    candidate_directory, payload, bundle, manifest, files = _load_artifact(repository, candidate)
    source = payload.get("coverage_baseline_source")
    if not isinstance(source, dict) or not isinstance(source.get("artifact"), str):
        raise ValueError("candidate lacks an immutable coverage baseline source")
    source_relative = _coverage_artifact_relative(repository, source["artifact"])
    if source_relative.as_posix() != source["artifact"]:
        raise ValueError("coverage baseline source path changed")
    target = _validate_output(repository, output)
    if target == candidate_directory or target in candidate_directory.parents or candidate_directory in target.parents:
        raise ValueError("candidate and output artifacts must be independent directories")
    source_candidate_artifact = candidate_directory.relative_to(repository).as_posix()
    output_artifact = target.relative_to(repository).as_posix()
    candidate_artifact = (target / "candidate").relative_to(repository).as_posix()
    acceptance_command = [
        "python3",
        "tools/verify_rom_mp2k_note_allocator.py",
        source_candidate_artifact,
        "--accept-to",
        output_artifact,
    ]
    source_candidate_identity = {
        "artifact_status": "candidate",
        "manifest_sha256": _sha(files[MANIFEST_NAME]),
        "payload_sha256": _sha(files[PAYLOAD_NAME]),
        "bundle_sha256": _sha(bundle),
    }
    embedded_candidate = dict(manifest)
    embedded_candidate["producer"] = {
        "kind": "artifact-candidate-construction",
        "output_artifact": candidate_artifact,
        "command": [
            "python3",
            "tools/export_rom_mp2k_note_allocator.py",
            "--coverage-baseline-artifact",
            source_relative.as_posix(),
            "--output",
            candidate_artifact,
        ],
    }
    embedded_candidate_raw = _canonical(embedded_candidate)
    candidate_identity = {
        "artifact_status": "candidate",
        "manifest_sha256": _sha(embedded_candidate_raw),
        "payload_sha256": _sha(files[PAYLOAD_NAME]),
        "bundle_sha256": _sha(bundle),
    }
    accepted = dict(embedded_candidate)
    accepted["artifact_status"] = "accepted"
    accepted["acceptance"] = {
        "kind": "independent-candidate-acceptance",
        "candidate_artifact": candidate_artifact,
        "source_candidate_artifact": source_candidate_artifact,
        "source_candidate_identity": source_candidate_identity,
        "output_artifact": output_artifact,
        "command": acceptance_command,
        "candidate_identity": candidate_identity,
    }
    accepted["verifier"] = {
        "path": "tools/verify_rom_mp2k_note_allocator.py",
        "sha256": _implementation(repository)["verifier"]["sha256"],
        "command": acceptance_command,
    }
    accepted["verification"] = {
        "status": "verified",
        "contract_ok": True,
        "schema": VERIFY_SCHEMA,
        "summary": report["summary"],
    }
    accepted_raw = _canonical(accepted)
    parent_fd = _open_directory_beneath(repository, target.parent)
    staging_name: str | None = None
    published_identity: tuple[int, int] | None = None
    try:
        try:
            os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("output directory appeared during acceptance")
        for _ in range(64):
            candidate_name = f".{target.name}.{secrets.token_hex(12)}"
            try:
                os.mkdir(candidate_name, 0o700, dir_fd=parent_fd)
            except FileExistsError:
                continue
            staging_name = candidate_name
            break
        if staging_name is None:
            raise ValueError("could not reserve an anchored staging directory")
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        staging_fd = os.open(staging_name, directory_flags, dir_fd=parent_fd)
        try:
            _write_file_at(staging_fd, PAYLOAD_NAME, files[PAYLOAD_NAME])
            _write_file_at(staging_fd, BUNDLE_NAME, bundle)
            _write_file_at(staging_fd, MANIFEST_NAME, accepted_raw)
            os.mkdir("candidate", 0o700, dir_fd=staging_fd)
            embedded_fd = os.open("candidate", directory_flags, dir_fd=staging_fd)
            try:
                _write_file_at(embedded_fd, PAYLOAD_NAME, files[PAYLOAD_NAME])
                _write_file_at(embedded_fd, BUNDLE_NAME, bundle)
                _write_file_at(embedded_fd, MANIFEST_NAME, embedded_candidate_raw)
                os.fsync(embedded_fd)
            finally:
                os.close(embedded_fd)
            os.fsync(staging_fd)
        finally:
            os.close(staging_fd)
        try:
            os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("output directory appeared during acceptance")
        os.replace(staging_name, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
        published_identity = _identity(os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False))
        accepted_report = verify_artifact(repository, target)
    except Exception:
        if staging_name is not None:
            _remove_tree_at(parent_fd, staging_name)
        if published_identity is not None:
            _remove_tree_at(parent_fd, target.name, published_identity)
        raise
    finally:
        os.close(parent_fd)
    return {**accepted_report, "artifact_status": "accepted"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--allow-candidate", action="store_true")
    parser.add_argument("--coverage-baseline-artifact", type=Path)
    parser.add_argument("--accept-to", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.accept_to is not None:
            if args.allow_candidate:
                raise ValueError("--allow-candidate cannot be combined with --accept-to")
            if args.coverage_baseline_artifact is not None:
                raise ValueError("accepted MP2K artifacts use the candidate's embedded coverage baseline source")
            report = accept_candidate(args.root, args.artifact, args.accept_to)
        else:
            if args.coverage_baseline_artifact is not None and not args.allow_candidate:
                raise ValueError("--coverage-baseline-artifact requires --allow-candidate")
            report = verify_artifact(args.root, args.artifact, allow_candidate=args.allow_candidate, coverage_baseline_artifact=args.coverage_baseline_artifact)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"schema": VERIFY_SCHEMA, "verified": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
