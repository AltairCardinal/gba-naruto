#!/usr/bin/env python3
"""Independently verify the frozen MPlayMain scheduler ROM packet."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import capstone
from capstone import CS_AC_WRITE, CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const


SCHEMA = "rom-mplaymain-scheduler-v1"
VERIFY_SCHEMA = "rom-mplaymain-scheduler-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ARTIFACT_RELATIVE = Path("artifacts/rom-mplaymain-scheduler-v1")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "17aa05ec2919606ac4728106daf08b3d06a033ccd3c723dc17fd7ad1bdec9ad0"

PAYLOAD_NAME = "rom-mplaymain-scheduler.json"
BUNDLE_NAME = "rom-mplaymain-scheduler.bin"
MANIFEST_NAME = "manifest.json"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, MANIFEST_NAME}

ROOT_OFFSET = 0x09A42C
ROOT_POINTER = ROM_BASE + ROOT_OFFSET + 1
CODE_RANGE = [0x09A42C, 0x09A684]
LITERAL_RANGE = [0x09A688, 0x09A694]
OWNED_RANGE = [0x09A684, 0x09A686]
UNKNOWN_RANGE = [0x09A686, 0x09A688]
CODE_SHA256 = "0603b7d7cbd42674284783b638188595f07155ec8942d0ef96137bec36b1b86c"
LITERAL_SHA256 = "d1b4099db32ee07e0e14f3d78937fcdda9ee750b9b3128d23d4d5e56df04c764"
OWNED_SHA256 = "477db9ac7ca5efc12e37f882656b8fe5a363ffeb99b2e565a953d10c3c91ab21"
UNKNOWN_SHA256 = "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"
BUNDLE_SHA256 = "8ca6a2f02cd27d46b9d0e9dbae2491672f23702ee2230eb73fc460759ef14955"
UNION_VECTOR_SHA256 = "a8e11002ba5439c3d758e03faa1850a686e749cbe3230496f871329283300b4d"

POINTER_LITERAL_RANGE = [0x09B1F0, 0x09B1F4]
POINTER_LITERAL_SHA256 = "502bedc7ad613f6c30c62152c8a7623b060d81f8c4b8b7d379088747138ff7d6"
SOUND_INFO_LITERAL_RANGE = [0x09B1E8, 0x09B1EC]
SOUND_INFO_LITERAL_SHA256 = "e47b04ebe71cb95aa7efebf2666040c297bdd758e5325d66acf08fd4cb9dc233"
WRITER_WINDOW = [0x09B1C4, 0x09B1DA]
WRITER_WINDOW_SHA256 = "d836e4a81c0f9269f141fc0fef260b2617023d6db6a4b478a9bda8ae40b81806"
CONSUMER_WINDOW = [0x099DC0, 0x099DCC]
CONSUMER_WINDOW_SHA256 = "1c6108a582e55ab5ccb0c254ecbb10b90413862ebdad4abcaf1890e93461a737"
SOUNDMAIN_THUNK_RANGE = [0x09A1AE, 0x09A1B0]
RECURSIVE_WINDOW = [0x09A43C, 0x09A448]
RECURSIVE_WINDOW_SHA256 = "b586e96a1940656f60d304400a84e6297b59bd516dc37c09a8a06d84b166bf88"

BOOT_PAYLOAD_PATH = Path("artifacts/rom-boot-thumb-handoff-cfg-v1/rom-boot-thumb-handoff-cfg.json")
BOOT_MANIFEST_PATH = Path("artifacts/rom-boot-thumb-handoff-cfg-v1/manifest.json")
BOOT_VERIFIER_PATH = Path("tools/verify_rom_boot_thumb_handoff_cfg.py")
BOOT_PAYLOAD_SHA256 = "a35b581e44b276399874a2fc393f22f3c548c6b99e053f504587bdd92fbad295"
BOOT_MANIFEST_SHA256 = "d5af12930ed8e7539396f81deda19ae938eee3f029b95c959f6fa5d57c676d74"
BOOT_VERIFIER_SHA256 = "2592e4f48f1a197e30cb4d360201228fc2bbeef5fad12879b1bbf77b29815b39"

OWNED_CLAIM_ID = "cfg-thumb-0752-09a684"
SOUNDMAIN_OWNER_CLAIM_ID = "boot-thumb-handoff-code-21-099d8c"
SOUNDMAIN_THUNK_CLAIM_ID = "boot-thumb-handoff-code-22-09a1ae"

EXTERNAL_RESOLUTIONS = {
    (0x09A444, "call_target", 0x09A684): "opaque_existing_indirect_veneer",
    (0x09A468, "call_target", 0x09B318): "opaque_direct_call",
    (0x09A4B8, "call_target", 0x09AE14): "opaque_direct_call",
    (0x09A4CC, "call_target", 0x09AE28): "opaque_direct_call",
    (0x09A50E, "call_target", 0x09A684): "opaque_existing_indirect_veneer",
    (0x09A52A, "call_target", 0x09A684): "opaque_existing_indirect_veneer",
    (0x09A5E4, "call_target", 0x09B3E0): "opaque_direct_call",
    (0x09A5F8, "call_target", 0x09AE14): "opaque_direct_call",
    (0x09A60C, "call_target", 0x09A6D8): "opaque_direct_call",
    (0x09A63E, "call_target", 0x09A684): "opaque_existing_indirect_veneer",
    (0x09A654, "call_target", 0x09A998): "opaque_direct_call",
    (0x09A682, "fallthrough", 0x09A684): "opaque_existing_indirect_veneer",
}
LITERAL_BINDINGS = [
    (0x09A536, 0x09A688, 0x084647A8),
    (0x09A460, 0x09A68C, 0x03007FF0),
    (0x09A42C, 0x09A690, 0x68736D53),
    (0x09A674, 0x09A690, 0x68736D53),
]

EXPECTED_SUMMARY = {
    "instruction_count": 289,
    "instruction_bytes": 600,
    "code_bytes": 600,
    "block_count": 81,
    "internal_edge_count": 117,
    "external_edge_count": 12,
    "external_target_count": 7,
    "literal_ref_count": 4,
    "literal_word_count": 3,
    "literal_bytes": 12,
    "frontier_count": 1,
    "return_count": 1,
    "raw_indirect_pc_count": 0,
    "owned_indirect_veneer_count": 1,
    "promoted_bytes": 612,
    "owned_provenance_bytes": 2,
    "unclassified_unknown_bytes": 2,
    "budget_exhausted": False,
}
BASELINE_SUMMARY = {
    "classified_bytes": 6_121_877,
    "unknown_bytes": 169_579,
    "claim_count": 14_482,
    "segment_count": 16_591,
}
PROJECTED_TOTALS = {
    "classified_bytes": 6_122_489,
    "unknown_bytes": 168_967,
    "claim_count": 14_484,
    "segment_count": 16_593,
}

SCOPE = {
    "additive_target_limited_cfg": True,
    "existing_owned_provenance_not_reclaimed": True,
    "direct_targets_opaque": True,
    "dynamic_callback_targets_resolved": False,
    "callback_lifecycle_closed": False,
    "global_ram_or_computed_producer_denominator_complete": False,
    "natural_runtime_reachable": False,
    "global_caller_denominator_complete": False,
    "global_code_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "scheduler_semantics_proven": False,
    "editing_relocation_writeback_safe": False,
    "allocatable_free_space_proven": False,
}
LIMITATIONS = [
    "This packet classifies exactly 600 bounded Thumb instruction bytes and 12 consumed literal bytes; two already-owned veneer bytes remain provenance and two bytes remain unknown.",
    "The unique exact 0x0809A42D ROM pointer literal, fixed SoundInfo slot writer, fixed slot consumer, and two existing BX r3 thunks are static provenance only.",
    "Dynamic callback targets and RAM values, callback lifecycle, natural runtime reachability, and global caller/code/indirect or computed-producer denominators remain unproven.",
    "Scheduler semantics, editing, relocation, writeback, and allocatable-space safety are outside scope.",
]

_EDGE_ORDER = {"branch_target": 0, "call_target": 1, "fallthrough": 2}
_THUMB_NAMES = (
    "ARM_INS_ADC", "ARM_INS_ADD", "ARM_INS_ADR", "ARM_INS_AND", "ARM_INS_ASR",
    "ARM_INS_B", "ARM_INS_BIC", "ARM_INS_BL", "ARM_INS_BX", "ARM_INS_CMN",
    "ARM_INS_CMP", "ARM_INS_EOR", "ARM_INS_LDM", "ARM_INS_LDMIA", "ARM_INS_LDMIB",
    "ARM_INS_LDR", "ARM_INS_LDRB", "ARM_INS_LDRH", "ARM_INS_LDRSB", "ARM_INS_LDRSH",
    "ARM_INS_LSL", "ARM_INS_LSR", "ARM_INS_MLA", "ARM_INS_MOV", "ARM_INS_MOVS",
    "ARM_INS_MUL", "ARM_INS_MVN", "ARM_INS_NEG", "ARM_INS_NOP", "ARM_INS_ORR",
    "ARM_INS_POP", "ARM_INS_PUSH", "ARM_INS_ROR", "ARM_INS_RSB", "ARM_INS_SBC",
    "ARM_INS_STMIA", "ARM_INS_STR", "ARM_INS_STRB", "ARM_INS_STRH", "ARM_INS_SUB",
    "ARM_INS_SUBS", "ARM_INS_SVC", "ARM_INS_TST", "ARM_INS_UXTH", "ARM_INS_REV",
)
THUMB_IDS = frozenset(
    getattr(arm_const, name) for name in _THUMB_NAMES if hasattr(arm_const, name)
)
_ENGINE: Cs | None = None


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _bounded(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"ROM range outside image: 0x{start:06X}..0x{end:06X}")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4), "little")


def _root(root: Path | str) -> Path:
    value = Path(root).resolve()
    if not value.is_dir():
        raise ValueError(f"repository root is not a directory: {value}")
    return value


def _safe_file(root: Path, relative: Path | str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe repository path: {path}")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository path uses a symlink: {cursor}")
    if not cursor.is_file():
        raise ValueError(f"required file missing: {path}")
    return cursor


def _safe_artifact(root: Path, artifact: Path | str) -> Path:
    value = Path(artifact)
    if not value.is_absolute():
        value = root / value
    absolute = value.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"artifact path uses a symlink: {cursor}")
    resolved = value.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError("artifact must stay inside repository root")
    if not resolved.is_dir():
        raise ValueError("artifact is not a directory")
    names = {item.name for item in resolved.iterdir()}
    if names != EXPECTED_FILES or any(not item.is_file() or item.is_symlink() for item in resolved.iterdir()):
        raise ValueError("artifact file set changed")
    return resolved


def _engine() -> Cs:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        _ENGINE.detail = True
        _ENGINE.skipdata = False
    return _ENGINE


def _sign(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _writes_pc(instruction: Any) -> bool:
    for operand in instruction.operands:
        if (
            operand.type == arm_const.ARM_OP_REG
            and operand.reg == arm_const.ARM_REG_PC
            and operand.access & CS_AC_WRITE
        ):
            return True
    try:
        _, writes = instruction.regs_access()
    except (AttributeError, capstone.CsError):
        writes = []
    return arm_const.ARM_REG_PC in writes


def _conditional(instruction: Any) -> bool:
    condition = getattr(instruction, "cc", arm_const.ARM_CC_AL)
    return condition not in (arm_const.ARM_CC_AL, arm_const.ARM_CC_INVALID)


def _raw_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
    first = int.from_bytes(raw[:2], "little")
    if len(raw) >= 4:
        second = int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {"kind": "call", "size": 4, "conditional": False, "target": offset + 4 + _sign(encoded, 23)}
    if first & 0xFF00 == 0xDF00:
        return {"kind": "supervisor_call", "size": 2, "conditional": False}
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        return {"kind": "conditional_branch", "size": 2, "conditional": True, "target": offset + 4 + _sign((first & 0xFF) << 1, 9)}
    if first & 0xF800 == 0xE000:
        return {"kind": "unconditional_branch", "size": 2, "conditional": False, "target": offset + 4 + _sign((first & 0x07FF) << 1, 12)}
    if first & 0xFF87 == 0x4700:
        register = (first >> 3) & 0xF
        return {"kind": "return" if register == 14 else "indirect_branch", "size": 2, "conditional": False, "register": register}
    return None


def _decode(rom: bytes, offset: int) -> dict[str, Any]:
    decoded = tuple(_engine().disasm(rom[offset : offset + 4], ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset:
        raise ValueError(f"independent Thumb decode failed: 0x{offset:06X}")
    instruction = decoded[0]
    raw = _bounded(rom, offset, offset + instruction.size)
    if instruction.id not in THUMB_IDS:
        raise ValueError(f"independent ARMv4T whitelist rejected: 0x{offset:06X}")
    if instruction.size == 4:
        if instruction.id != arm_const.ARM_INS_BL:
            raise ValueError(f"independent decoder found non-ARMv4T wide instruction: 0x{offset:06X}")
        first, second = _u16(rom, offset), _u16(rom, offset + 2)
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            raise ValueError(f"independent BL oracle mismatch: 0x{offset:06X}")
    elif instruction.size != 2:
        raise ValueError(f"independent Thumb size changed: 0x{offset:06X}")
    flow = _raw_flow(raw, offset)
    if instruction.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL, arm_const.ARM_INS_BX, arm_const.ARM_INS_SVC) and flow is None:
        raise ValueError(f"independent control-flow oracle mismatch: 0x{offset:06X}")
    end = offset + instruction.size
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    indirect = False
    if flow and flow["kind"] in {"call", "conditional_branch", "unconditional_branch"}:
        successors.append({"kind": "call_target" if flow["kind"] == "call" else "branch_target", "mode": "thumb", "file_offset": flow["target"]})
        if flow["kind"] in {"call", "conditional_branch"}:
            successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": end})
        kind = flow["kind"]
    elif flow and flow["kind"] == "supervisor_call":
        successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": end})
        frontiers.append({"reason": "bios_swi_external"})
        kind = "supervisor_call"
    elif flow and flow["kind"] in {"return", "indirect_branch"}:
        kind = flow["kind"]
        if kind == "indirect_branch":
            indirect = True
            frontiers.append({"reason": "indirect_pc_target", "register": flow["register"]})
    elif _writes_pc(instruction):
        kind = "return" if instruction.id == arm_const.ARM_INS_POP else "indirect_branch"
        if kind == "indirect_branch":
            indirect = True
            frontiers.append({"reason": "indirect_pc_target"})
    else:
        kind = "linear"
        successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": end})
    successors.sort(key=lambda item: (_EDGE_ORDER[item["kind"]], item["file_offset"]))
    return {
        "mode": "thumb",
        "file_offset": offset,
        "gba_address": _gba(offset),
        "size": instruction.size,
        "raw_hex": raw.hex(),
        "bytes_sha256": _sha(raw),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "conditional": flow["conditional"] if flow else _conditional(instruction),
        "flow_kind": kind,
        "raw_flow_kind": flow["kind"] if flow else None,
        "raw_indirect_pc": indirect,
        "successors": successors,
        "frontiers": frontiers,
    }


def _cfg(rom: bytes) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    start, end = CODE_RANGE
    pending = [ROOT_OFFSET]
    scheduled = {ROOT_OFFSET}
    nodes: dict[int, dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if not start <= offset < end:
            raise ValueError(f"independent CFG escaped code: 0x{offset:06X}")
        node = _decode(rom, offset)
        if offset + node["size"] > end:
            raise ValueError(f"independent CFG crossed code end: 0x{offset:06X}")
        nodes[offset] = node
        for edge in node["successors"]:
            target = edge["file_offset"]
            if start <= target < end:
                if target not in scheduled:
                    scheduled.add(target)
                    heapq.heappush(pending, target)
                continue
            key = (offset, edge["kind"], target)
            resolution = EXTERNAL_RESOLUTIONS.get(key)
            if resolution is None:
                raise ValueError(f"independent external edge changed: {key}")
            external.append({
                "source_instruction_offset": offset,
                "source_gba_address": _gba(offset),
                "kind": edge["kind"],
                "mode": "thumb",
                "target_offset": target,
                "target_gba_address": _gba(target),
                "target_scheduled": False,
                "resolution": resolution,
            })
    covered: set[int] = set()
    for offset, node in nodes.items():
        covered.update(range(offset, offset + node["size"]))
    if covered != set(range(start, end)):
        raise ValueError("independent CFG does not cover exact code denominator")
    observed = [(item["source_instruction_offset"], item["kind"], item["target_offset"]) for item in external]
    if observed != list(EXTERNAL_RESOLUTIONS):
        raise ValueError("independent external edge vector changed")
    return nodes, external


def _blocks(nodes: dict[int, dict[str, Any]], external: list[dict[str, Any]], rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predecessors: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for edge in node["successors"]:
            if edge["file_offset"] in nodes:
                predecessors[edge["file_offset"]].append((source, edge["kind"]))
    starts = {ROOT_OFFSET}
    for offset, incoming in predecessors.items():
        if offset in starts:
            continue
        if len(incoming) != 1:
            starts.add(offset)
            continue
        source, _ = incoming[0]
        predecessor = nodes[source]
        if len(predecessor["successors"]) != 1 or predecessor["flow_kind"] != "linear" or source + predecessor["size"] != offset:
            starts.add(offset)
    blocks: list[dict[str, Any]] = []
    block_by_offset: dict[int, str] = {}
    for start in sorted(starts):
        members: list[int] = []
        offset = start
        while offset in nodes and offset not in block_by_offset:
            members.append(offset)
            block_by_offset[offset] = f"block-thumb-{start:06x}"
            node = nodes[offset]
            if len(node["successors"]) != 1 or node["flow_kind"] != "linear":
                break
            target = node["successors"][0]["file_offset"]
            if target in starts or target != offset + node["size"]:
                break
            offset = target
        if not members:
            continue
        end = members[-1] + nodes[members[-1]]["size"]
        last = nodes[members[-1]]
        blocks.append({
            "id": block_by_offset[start],
            "mode": "thumb",
            "range": [start, end],
            "gba_range": [_gba(start), _gba(end)],
            "instruction_count": len(members),
            "bytes_sha256": _sha(_bounded(rom, start, end)),
            "terminator": {
                "file_offset": members[-1], "size": last["size"], "raw_hex": last["raw_hex"],
                "mnemonic": last["mnemonic"], "op_str": last["op_str"],
                "flow_kind": last["flow_kind"], "conditional": last["conditional"],
            },
            "successors": [],
        })
    if len(block_by_offset) != len(nodes):
        raise ValueError("independent block partition omitted instructions")
    by_source: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in external:
        by_source[item["source_instruction_offset"]].append(item)
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["file_offset"]
        for successor in nodes[source]["successors"]:
            target = successor["file_offset"]
            if target in nodes:
                record = {
                    "source_block_id": block["id"], "source_instruction_offset": source,
                    "kind": successor["kind"], "mode": "thumb", "target_offset": target,
                    "target_gba_address": _gba(target), "target_block_id": block_by_offset[target],
                    "target_scheduled": True, "resolution": "internal",
                }
            else:
                match = [item for item in by_source[source] if item["kind"] == successor["kind"] and item["target_offset"] == target]
                if len(match) != 1:
                    raise ValueError("independent external block edge changed")
                record = {**match[0], "source_block_id": block["id"]}
            block["successors"].append(record)
            edges.append(record)
    return blocks, edges


def _bl_target(rom: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(rom) or offset % 2:
        return None
    first, second = _u16(rom, offset), _u16(rom, offset + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
    return offset + 4 + _sign(encoded, 23)


def _occurrences(rom: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    result: list[int] = []
    start = 0
    while True:
        start = rom.find(needle, start)
        if start < 0:
            return result
        result.append(start)
        start += 1


def _coverage(root: Path) -> tuple[dict[str, Any], bytearray, dict[str, Any]]:
    raw = _safe_file(root, COVERAGE_PATH).read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("independent coverage baseline identity changed")
    value = json.loads(raw)
    if value.get("base_rom") != {"path": ROM_PATH.as_posix(), "sha256": ROM_SHA256, "size": ROM_SIZE}:
        raise ValueError("independent coverage ROM binding changed")
    observed = {key: value["summary"].get(key) for key in BASELINE_SUMMARY}
    if observed != BASELINE_SUMMARY:
        raise ValueError("independent coverage summary changed")
    target = [item for item in value["segments"] if item["range"][1] > 0x09A3DC and item["range"][0] < 0x09A694]
    if [(item["range"], item["primary_class"], item.get("primary_claim_ids", [])) for item in target] != [
        ([0x09A3DC, 0x09A684], "unknown", []),
        ([0x09A684, 0x09A686], "armv4t_cfg_reachable_thumb_code", [OWNED_CLAIM_ID]),
        ([0x09A686, 0x09A694], "unknown", []),
    ]:
        raise ValueError("independent target coverage partition changed")
    mask = bytearray(ROM_SIZE)
    for segment in value["segments"]:
        if segment["primary_class"] == "unknown":
            start, end = segment["range"]
            mask[start:end] = b"\x01" * (end - start)
    claims = {item.get("id"): item for item in value["claims"]}
    owner = claims.get(OWNED_CLAIM_ID)
    if owner is None or owner.get("range") != OWNED_RANGE or owner.get("bytes_sha256") != OWNED_SHA256:
        raise ValueError("independent owned veneer claim changed")
    baseline = {
        "path": COVERAGE_PATH.as_posix(), "sha256": COVERAGE_SHA256,
        "summary": BASELINE_SUMMARY,
        "target_segments": [
            {"range": [0x09A3DC, 0x09A684], "primary_class": "unknown"},
            {"range": OWNED_RANGE, "claim_id": OWNED_CLAIM_ID},
            {"range": [0x09A686, 0x09A694], "primary_class": "unknown"},
        ],
    }
    return baseline, mask, claims


def _entry(root: Path, rom: bytes, claims: dict[str, Any]) -> dict[str, Any]:
    if _sha(_bounded(rom, *POINTER_LITERAL_RANGE)) != POINTER_LITERAL_SHA256 or _u32(rom, 0x09B1F0) != ROOT_POINTER:
        raise ValueError("independent MPlayMain pointer literal changed")
    pointer_occurrences = _occurrences(rom, ROOT_POINTER)
    if pointer_occurrences != [0x09B1F0]:
        raise ValueError("independent MPlayMain pointer denominator changed")
    bl_producers = [offset for offset in range(0, len(rom) - 3, 2) if _bl_target(rom, offset) == ROOT_OFFSET]
    if bl_producers:
        raise ValueError("independent MPlayMain direct-BL denominator changed")
    writer = {
        0x09B1C4: 0x6A28, 0x09B1C6: 0x2800, 0x09B1C8: 0xD004,
        0x09B1CA: 0x63B8, 0x09B1CC: 0x6A68, 0x09B1CE: 0x63F8,
        0x09B1D0: 0x2000, 0x09B1D2: 0x6228, 0x09B1D4: 0x626F,
        0x09B1D6: 0x4806, 0x09B1D8: 0x6228,
    }
    if any(_u16(rom, offset) != expected for offset, expected in writer.items()) or _sha(_bounded(rom, *WRITER_WINDOW)) != WRITER_WINDOW_SHA256:
        raise ValueError("independent callback writer changed")
    if _u16(rom, 0x09B190) != 0x4815 or _u16(rom, 0x09B192) != 0x6805:
        raise ValueError("independent SoundInfo base load changed")
    if _u32(rom, 0x09B1E8) != 0x03007FF0 or _sha(_bounded(rom, *SOUND_INFO_LITERAL_RANGE)) != SOUND_INFO_LITERAL_SHA256:
        raise ValueError("independent SoundInfo literal changed")
    consumer = {0x099DC0: 0x6A03, 0x099DC2: 0x2B00, 0x099DC4: 0xD003, 0x099DC6: 0x6A40}
    if any(_u16(rom, offset) != expected for offset, expected in consumer.items()) or _bl_target(rom, 0x099DC8) != 0x09A1AE or _sha(_bounded(rom, *CONSUMER_WINDOW)) != CONSUMER_WINDOW_SHA256:
        raise ValueError("independent callback consumer changed")
    if _u16(rom, 0x09A1AE) != 0x4718:
        raise ValueError("independent SoundMain thunk changed")
    recursive = {0x09A43C: 0x6B83, 0x09A43E: 0x2B00, 0x09A440: 0xD002, 0x09A442: 0x6BC0}
    if any(_u16(rom, offset) != expected for offset, expected in recursive.items()) or _bl_target(rom, 0x09A444) != 0x09A684 or _sha(_bounded(rom, *RECURSIVE_WINDOW)) != RECURSIVE_WINDOW_SHA256:
        raise ValueError("independent recursive callback chain changed")
    if _u16(rom, 0x09A684) != 0x4718 or _sha(_bounded(rom, *OWNED_RANGE)) != OWNED_SHA256:
        raise ValueError("independent owned recursive veneer changed")
    for claim_id, expected_range in (
        (SOUNDMAIN_OWNER_CLAIM_ID, [0x099D8C, 0x099DF6]),
        (SOUNDMAIN_THUNK_CLAIM_ID, SOUNDMAIN_THUNK_RANGE),
        (OWNED_CLAIM_ID, OWNED_RANGE),
    ):
        if claim_id not in claims or claims[claim_id].get("range") != expected_range:
            raise ValueError(f"independent entry owner changed: {claim_id}")
    receipts = {
        "payload": {"path": BOOT_PAYLOAD_PATH.as_posix(), "sha256": BOOT_PAYLOAD_SHA256},
        "manifest": {"path": BOOT_MANIFEST_PATH.as_posix(), "sha256": BOOT_MANIFEST_SHA256},
        "verifier": {"path": BOOT_VERIFIER_PATH.as_posix(), "sha256": BOOT_VERIFIER_SHA256},
    }
    for receipt in receipts.values():
        if _sha(_safe_file(root, receipt["path"]).read_bytes()) != receipt["sha256"]:
            raise ValueError(f"independent boot receipt changed: {receipt['path']}")
    return {
        "root": {"mode": "thumb", "file_offset": ROOT_OFFSET, "gba_address": _gba(ROOT_OFFSET), "thumb_pointer": f"0x{ROOT_POINTER:08X}", "first_instruction_raw_hex": _bounded(rom, ROOT_OFFSET, ROOT_OFFSET + 2).hex()},
        "pointer_denominator": {
            "pointer_value": f"0x{ROOT_POINTER:08X}", "pointer_raw_hex": _bounded(rom, *POINTER_LITERAL_RANGE).hex(),
            "literal_range": POINTER_LITERAL_RANGE, "literal_sha256": POINTER_LITERAL_SHA256,
            "bytewise_u32_occurrences": pointer_occurrences, "aligned_thumb_bl_producers": bl_producers,
            "producer_source_instruction_membership_proven": False, "producer_bytes_promoted": False,
            "global_ram_or_computed_producer_denominator_complete": False,
        },
        "callback_writer": {
            "sound_info_global_cell": "0x03007FF0", "sound_info_literal_range": SOUND_INFO_LITERAL_RANGE,
            "writer_window": WRITER_WINDOW, "writer_window_sha256": WRITER_WINDOW_SHA256,
            "callback_slot_expression": "(*u32[0x03007FF0])+0x20", "argument_slot_expression": "(*u32[0x03007FF0])+0x24",
            "inherited_callback_slot_expression": "player+0x38", "inherited_argument_slot_expression": "player+0x3C",
            "callee_saved_r5_abi_dependency": True, "runtime_value_proven": False,
        },
        "callback_consumer": {
            "callback_window": CONSUMER_WINDOW, "callback_window_sha256": CONSUMER_WINDOW_SHA256,
            "indirect_thunk_range": SOUNDMAIN_THUNK_RANGE, "indirect_thunk_operation": "bx r3",
            "owner_claim_id": SOUNDMAIN_THUNK_CLAIM_ID, "soundmain_owner_claim_id": SOUNDMAIN_OWNER_CLAIM_ID,
            "boot_provenance_receipts": receipts, "soundmain_relocation_source_excluded": True,
        },
        "recursive_chain": {
            "window": RECURSIVE_WINDOW, "window_sha256": RECURSIVE_WINDOW_SHA256,
            "owned_veneer_range": OWNED_RANGE, "owned_veneer_operation": "bx r3", "owner_claim_id": OWNED_CLAIM_ID,
            "incoming_sites": [[0x09A444, "call_target"], [0x09A50E, "call_target"], [0x09A52A, "call_target"], [0x09A63E, "call_target"], [0x09A682, "fallthrough"]],
            "dynamic_r3_targets_resolved": False,
        },
    }


def _literal_rows(rom: bytes, nodes: dict[int, dict[str, Any]], unknown: bytearray) -> list[dict[str, Any]]:
    expected = {(consumer, literal) for consumer, literal, _ in LITERAL_BINDINGS}
    rows: list[dict[str, Any]] = []
    for consumer, literal, value in LITERAL_BINDINGS:
        if consumer not in nodes or _u16(rom, consumer) & 0xF800 != 0x4800:
            raise ValueError(f"independent literal consumer changed: 0x{consumer:06X}")
        target = ((consumer + 4) & ~3) + (_u16(rom, consumer) & 0xFF) * 4
        if target != literal or _u32(rom, literal) != value or not all(unknown[literal : literal + 4]):
            raise ValueError(f"independent literal binding changed: 0x{consumer:06X}")
        raw = _bounded(rom, consumer, consumer + 2)
        word = _bounded(rom, literal, literal + 4)
        decoded = tuple(_engine().disasm(raw, ROM_BASE + consumer, count=1))[0]
        rows.append({
            "instruction_offset": consumer, "instruction_gba_address": _gba(consumer),
            "instruction_raw_hex": raw.hex(), "instruction_sha256": _sha(raw),
            "mnemonic": decoded.mnemonic, "op_str": decoded.op_str,
            "literal_offset": literal, "literal_gba_address": _gba(literal),
            "literal_raw_hex": word.hex(), "literal_sha256": _sha(word), "value": f"0x{value:08X}",
        })
    for offset, node in nodes.items():
        if node["size"] == 2 and _u16(rom, offset) & 0xF800 == 0x4800:
            target = ((offset + 4) & ~3) + (_u16(rom, offset) & 0xFF) * 4
            if (offset, target) not in expected:
                raise ValueError(f"independent unexpected literal consumer: 0x{offset:06X}")
    rows.sort(key=lambda item: (item["literal_offset"], item["instruction_offset"]))
    return rows


def independent_rebuild(root: Path | str, rom: bytes) -> dict[str, Any]:
    repository = _root(root)
    rom = bytes(rom)
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("independent ROM identity changed")
    baseline, unknown, claims = _coverage(repository)
    entry = _entry(repository, rom, claims)
    if _sha(_bounded(rom, *CODE_RANGE)) != CODE_SHA256 or not all(unknown[slice(*CODE_RANGE)]):
        raise ValueError("independent code range changed")
    if _sha(_bounded(rom, *LITERAL_RANGE)) != LITERAL_SHA256 or not all(unknown[slice(*LITERAL_RANGE)]):
        raise ValueError("independent literal range changed")
    if _sha(_bounded(rom, *UNKNOWN_RANGE)) != UNKNOWN_SHA256 or not all(unknown[slice(*UNKNOWN_RANGE)]):
        raise ValueError("independent unknown gap changed")
    if _sha(_bounded(rom, *OWNED_RANGE)) != OWNED_SHA256 or any(unknown[slice(*OWNED_RANGE)]):
        raise ValueError("independent owned veneer range changed")
    nodes, external = _cfg(rom)
    blocks, edges = _blocks(nodes, external, rom)
    literals = _literal_rows(rom, nodes, unknown)
    bundle = _bounded(rom, *CODE_RANGE) + _bounded(rom, *LITERAL_RANGE)
    if _sha(bundle) != BUNDLE_SHA256 or _sha(_canonical([CODE_RANGE, LITERAL_RANGE])) != UNION_VECTOR_SHA256:
        raise ValueError("independent bundle identity changed")
    summary = {
        "instruction_count": len(nodes), "instruction_bytes": sum(item["size"] for item in nodes.values()),
        "code_bytes": 600, "block_count": len(blocks),
        "internal_edge_count": sum(item["resolution"] == "internal" for item in edges),
        "external_edge_count": sum(item["resolution"] != "internal" for item in edges),
        "external_target_count": len({item["target_offset"] for item in external}),
        "literal_ref_count": len(literals), "literal_word_count": len({item["literal_offset"] for item in literals}),
        "literal_bytes": 12, "frontier_count": 1,
        "return_count": sum(item["flow_kind"] == "return" for item in nodes.values()),
        "raw_indirect_pc_count": sum(bool(item["raw_indirect_pc"]) for item in nodes.values()),
        "owned_indirect_veneer_count": 1, "promoted_bytes": 612,
        "owned_provenance_bytes": 2, "unclassified_unknown_bytes": 2, "budget_exhausted": False,
    }
    if summary != EXPECTED_SUMMARY:
        raise ValueError(f"independent summary changed: {summary}")
    return {
        "summary": summary, "coverage_baseline": baseline, "entry_proof": entry,
        "instructions": [nodes[offset] for offset in sorted(nodes)], "blocks": blocks, "edges": edges,
        "external_edge_records": [item for item in edges if item["resolution"] != "internal"],
        "external_edges": [[item["source_instruction_offset"], item["kind"], item["target_offset"]] for item in external],
        "literal_rows": literals,
        "literal_bindings": [[item["instruction_offset"], item["literal_offset"], item["value"]] for item in literals],
        "bundle": bundle, "bundle_sha256": _sha(bundle), "entry_contract_ok": True,
    }


def _implementation(root: Path) -> dict[str, Any]:
    paths = {
        "exporter": Path("tools/export_rom_mplaymain_scheduler.py"),
        "verifier": Path("tools/verify_rom_mplaymain_scheduler.py"),
        "test": Path("tests/test_export_rom_mplaymain_scheduler.py"),
    }
    return {role: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in paths.items()}


def _expected_promotion() -> dict[str, Any]:
    return {
        "code_range_count": 1, "code_bytes": 600, "literal_range_count": 1, "literal_bytes": 12,
        "union_range_count": 2, "union_bytes": 612, "union_ranges": [CODE_RANGE, LITERAL_RANGE],
        "union_range_vector_sha256": UNION_VECTOR_SHA256, "union_bytes_sha256": BUNDLE_SHA256,
        "current_known_overlap_bytes": 0, "owned_provenance_ranges": [OWNED_RANGE], "owned_provenance_bytes": 2,
        "unclassified_unknown_ranges": [UNKNOWN_RANGE], "unclassified_unknown_bytes": 2,
        "projected_totals": PROJECTED_TOTALS,
        "future_coverage_claim_projection": {"code_claim_count": 1, "literal_claim_count": 1, "owned_claim_count": 0, "unclassified_claim_count": 0},
    }


def _verify_payload(root: Path, payload: dict[str, Any], bundle: bytes, rebuilt: dict[str, Any]) -> None:
    if payload.get("schema") != SCHEMA:
        raise ValueError("payload schema changed")
    if payload.get("rom") != {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:
        raise ValueError("payload ROM binding changed")
    if payload.get("summary") != rebuilt["summary"]:
        raise ValueError("payload summary changed")
    if payload.get("coverage_baseline") != rebuilt["coverage_baseline"]:
        raise ValueError("payload coverage baseline changed")
    if payload.get("entry_proof") != rebuilt["entry_proof"] or payload.get("producer_denominator") != rebuilt["entry_proof"]["pointer_denominator"]:
        raise ValueError("payload entry proof changed")
    if payload.get("roots") != [{"mode": "thumb", "file_offset": ROOT_OFFSET, "gba_address": _gba(ROOT_OFFSET), "thumb_pointer": f"0x{ROOT_POINTER:08X}"}]:
        raise ValueError("payload root changed")
    if payload.get("code_ranges") != [CODE_RANGE] or payload.get("literal_ranges") != [LITERAL_RANGE] or payload.get("owned_provenance_ranges") != [OWNED_RANGE] or payload.get("unclassified_unknown_ranges") != [UNKNOWN_RANGE]:
        raise ValueError("payload range denominator changed")
    if payload.get("instructions") != rebuilt["instructions"]:
        raise ValueError("payload instruction denominator changed")
    if payload.get("blocks") != rebuilt["blocks"] or payload.get("edges") != rebuilt["edges"] or payload.get("external_edges") != rebuilt["external_edge_records"]:
        raise ValueError("payload CFG graph changed")
    if payload.get("literal_bindings") != rebuilt["literal_rows"]:
        raise ValueError("payload literal bindings changed")
    expected_frontier = [{"reason": "opaque_indirect_r3_veneer", "veneer_range": OWNED_RANGE, "veneer_operation": "bx r3", "target_resolution": "computed_or_dynamic_unresolved", "incoming_sites": [0x09A444, 0x09A50E, 0x09A52A, 0x09A63E, 0x09A682]}]
    if payload.get("frontiers") != expected_frontier or payload.get("raw_indirect_pc_sites") != []:
        raise ValueError("payload frontier contract changed")
    if payload.get("promotion") != _expected_promotion():
        raise ValueError("payload promotion contract changed")
    expected_rows = [
        {"id": "mplaymain-code-00-09a42c", "kind": "code", "range": CODE_RANGE, "size": 600, "sha256": CODE_SHA256, "semantic_class": "armv4t_mplaymain_scheduler_thumb_code", "claim_kind": "mplaymain_scheduler_reachable_instruction_bytes", "baseline_unknown_only": True},
        {"id": "mplaymain-literal-00-09a688", "kind": "literal", "range": LITERAL_RANGE, "size": 12, "sha256": LITERAL_SHA256, "semantic_class": "mplaymain_scheduler_consumed_literals", "claim_kind": "mplaymain_scheduler_consumed_literal_bytes", "baseline_unknown_only": True},
    ]
    if payload.get("promotion_ranges") != expected_rows:
        raise ValueError("payload promotion rows changed")
    claims = payload.get("coverage_claims")
    if not isinstance(claims, list) or len(claims) != 2:
        raise ValueError("payload coverage claim denominator changed")
    for claim, row in zip(claims, expected_rows, strict=True):
        expected = {**row, "role": "primary", "promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown", "promotion_union_range_count": 2, "promotion_union_bytes": 612, "promotion_union_range_vector_sha256": UNION_VECTOR_SHA256, "non_claims": SCOPE, "limitations": LIMITATIONS}
        if claim != expected:
            raise ValueError("payload coverage claim changed")
    layout = [
        {"kind": "code", "range": CODE_RANGE, "source_offset": CODE_RANGE[0], "bundle_offset": 0, "size": 600, "sha256": CODE_SHA256},
        {"kind": "literal", "range": LITERAL_RANGE, "source_offset": LITERAL_RANGE[0], "bundle_offset": 600, "size": 12, "sha256": LITERAL_SHA256},
    ]
    if payload.get("packed_layout") != layout or payload.get("packed_binary") != {"file": BUNDLE_NAME, "size": 612, "sha256": BUNDLE_SHA256, "layout": layout}:
        raise ValueError("payload packed layout changed")
    if bundle != rebuilt["bundle"]:
        raise ValueError("packed binary differs from raw-ROM reconstruction")
    if payload.get("scope") != SCOPE or payload.get("limitations") != LIMITATIONS:
        raise ValueError("payload scope or limitations changed")
    if payload.get("implementation") != _implementation(root):
        raise ValueError("payload implementation receipts changed")


def _load_artifact(root: Path, artifact: Path | str) -> tuple[Path, dict[str, Any], bytes, dict[str, Any], dict[str, bytes]]:
    directory = _safe_artifact(root, artifact)
    files = {name: (directory / name).read_bytes() for name in EXPECTED_FILES}
    try:
        payload = json.loads(files[PAYLOAD_NAME])
        manifest = json.loads(files[MANIFEST_NAME])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("artifact JSON is invalid") from exc
    if _canonical(payload) != files[PAYLOAD_NAME] or _canonical(manifest) != files[MANIFEST_NAME]:
        raise ValueError("artifact JSON is not canonical")
    return directory, payload, files[BUNDLE_NAME], manifest, files


def verify_artifact(root: Path | str, artifact: Path | str = ARTIFACT_RELATIVE, *, allow_candidate: bool = False) -> dict[str, Any]:
    repository = _root(root)
    directory, payload, bundle, manifest, files = _load_artifact(repository, artifact)
    status = manifest.get("artifact_status")
    if status == "candidate" and not allow_candidate:
        raise ValueError("candidate artifact requires explicit opt-in")
    if status not in ({"candidate", "accepted"} if allow_candidate else {"accepted"}):
        raise ValueError("artifact status changed")
    if manifest.get("schema") != PROMOTION_SCHEMA or manifest.get("artifact_schema") != SCHEMA:
        raise ValueError("manifest schema changed")
    receipts = manifest.get("files")
    if receipts != {
        PAYLOAD_NAME: {"size": len(files[PAYLOAD_NAME]), "sha256": _sha(files[PAYLOAD_NAME])},
        BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)},
    }:
        raise ValueError("manifest file receipts changed")
    rom = _safe_file(repository, ROM_PATH).read_bytes()
    rebuilt = independent_rebuild(repository, rom)
    _verify_payload(repository, payload, bundle, rebuilt)
    mirrored = {
        "rom": payload["rom"], "coverage_baseline": payload["coverage_baseline"],
        "provenance_inputs": payload["provenance_inputs"], "entry_proof": payload["entry_proof"],
        "implementation": payload["implementation"], "promotion": payload["promotion"],
        "scope": payload["scope"], "summary": payload["summary"], "limitations": payload["limitations"],
    }
    if any(manifest.get(key) != value for key, value in mirrored.items()):
        raise ValueError("manifest mirrored contract changed")
    expected_producer = {"command": ["python3", "tools/export_rom_mplaymain_scheduler.py", "--output", ARTIFACT_RELATIVE.as_posix()]}
    if manifest.get("producer") != expected_producer:
        raise ValueError("manifest producer command changed")
    verifier_receipt = {"path": "tools/verify_rom_mplaymain_scheduler.py", "sha256": _implementation(repository)["verifier"]["sha256"], "command": ["python3", "tools/verify_rom_mplaymain_scheduler.py", "--artifact", ARTIFACT_RELATIVE.as_posix()]}
    if status == "candidate":
        if manifest.get("verification") != {"status": "pending", "report": None} or "verifier" in manifest:
            raise ValueError("candidate verification metadata changed")
    else:
        if manifest.get("verifier") != verifier_receipt:
            raise ValueError("accepted verifier receipt changed")
        verification = manifest.get("verification")
        if verification != {"status": "verified", "contract_ok": True, "schema": VERIFY_SCHEMA, "summary": EXPECTED_SUMMARY}:
            raise ValueError("accepted verification receipt changed")
    return {
        "schema": VERIFY_SCHEMA, "verified": True, "contract_ok": True,
        "artifact_status": status, "artifact": str(directory),
        "payload_sha256": _sha(files[PAYLOAD_NAME]), "bundle_sha256": _sha(bundle),
        "manifest_sha256": _sha(files[MANIFEST_NAME]), "summary": EXPECTED_SUMMARY,
        "entry_contract_ok": True, "coverage_baseline_sha256": COVERAGE_SHA256,
    }


def _validate_output(root: Path, output: Path | str) -> Path:
    value = Path(output)
    if not value.is_absolute():
        value = root / value
    absolute = value.absolute()
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"output path uses a symlink: {cursor}")
    parent = value.parent.resolve()
    if root != parent and root not in parent.parents:
        raise ValueError("output must stay inside repository root")
    if value.exists():
        if value.is_symlink() or not value.is_dir():
            raise ValueError("output must be a new directory")
        if any(value.iterdir()):
            raise ValueError("output directory must be empty")
    return value


def accept_candidate(root: Path | str, candidate: Path | str, output: Path | str = ARTIFACT_RELATIVE) -> dict[str, Any]:
    repository = _root(root)
    report = verify_artifact(repository, candidate, allow_candidate=True)
    if report["artifact_status"] != "candidate":
        raise ValueError("only a candidate artifact can be accepted")
    _, payload, bundle, manifest, files = _load_artifact(repository, candidate)
    target = _validate_output(repository, output)
    accepted = dict(manifest)
    accepted["artifact_status"] = "accepted"
    accepted["verifier"] = {
        "path": "tools/verify_rom_mplaymain_scheduler.py",
        "sha256": _implementation(repository)["verifier"]["sha256"],
        "command": ["python3", "tools/verify_rom_mplaymain_scheduler.py", "--artifact", ARTIFACT_RELATIVE.as_posix()],
    }
    accepted["verification"] = {"status": "verified", "contract_ok": True, "schema": VERIFY_SCHEMA, "summary": EXPECTED_SUMMARY}
    accepted_raw = _canonical(accepted)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        (staging / PAYLOAD_NAME).write_bytes(files[PAYLOAD_NAME])
        (staging / BUNDLE_NAME).write_bytes(bundle)
        (staging / MANIFEST_NAME).write_bytes(accepted_raw)
        if target.exists():
            target.rmdir()
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    accepted_report = verify_artifact(repository, target)
    return {**accepted_report, "artifact_status": "accepted"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--artifact", type=Path, default=ARTIFACT_RELATIVE)
    parser.add_argument("--allow-candidate", action="store_true")
    parser.add_argument("--accept-to", type=Path)
    args = parser.parse_args()
    if args.accept_to is not None:
        report = accept_candidate(args.root, args.artifact, args.accept_to)
    else:
        report = verify_artifact(args.root, args.artifact, allow_candidate=args.allow_candidate)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
