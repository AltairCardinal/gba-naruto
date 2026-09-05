#!/usr/bin/env python3
"""Export the frozen MP2K channel-gain/note-allocator packet.

The exporter is deliberately target limited.  It uses the vendored ARM
decoder for instruction presentation, and checks every control-flow decision
with a raw/capstone cross-check before emitting a candidate.
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
from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const


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
COVERAGE_SUMMARY = {
    "classified_bytes": 6_123_937,
    "unknown_bytes": 167_519,
    "claim_count": 14_499,
    "segment_count": 16_608,
}
PROJECTED_COVERAGE_SUMMARY = {
    "classified_bytes": 6_124_499,
    "unknown_bytes": 166_957,
    "claim_count": 14_503,
    "segment_count": 16_614,
}

PROMOTION_RANGES = [
    [0x09A6D8, 0x09A708],
    [0x09A708, 0x09A8FE],
    [0x09A900, 0x09A908],
    [0x09AF24, 0x09AF28],
]
PROMOTION_RANGE_SHA256 = [
    "04988bf8e911a12b477d9aafa24342b68e83960a06796e555869cc67b24bd4d2",
    "4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e",
    "aea41d042f130b46329f8b5a5fdb976816ec280b367dc424f28bc624072867c1",
    "ee8951cbf1e4a1f69fce481a4537a84678e2615bc7e3f175ff69a97044ab7016",
]
PACKED_SHA256 = "3c3a1dab618964db40570b65c28ae08500a30392c65c25d870291ee5abb1587c"
PROMOTION_UNION_RANGES = [
    [0x09A6D8, 0x09A8FE],
    [0x09A900, 0x09A908],
    [0x09AF24, 0x09AF28],
]
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
    0x09A6D8: [
        [0x09A6D8, 0x09A6EE], [0x09A6EE, 0x09A6F0], [0x09A6F0, 0x09A702],
        [0x09A702, 0x09A704], [0x09A704, 0x09A708],
    ],
    0x09A708: [
        [0x09A708, 0x09A730], [0x09A730, 0x09A73A], [0x09A73A, 0x09A744], [0x09A744, 0x09A74C],
        [0x09A74C, 0x09A74E], [0x09A74E, 0x09A75E], [0x09A75E, 0x09A766], [0x09A766, 0x09A76E],
        [0x09A76E, 0x09A770], [0x09A770, 0x09A786], [0x09A786, 0x09A788], [0x09A788, 0x09A78E],
        [0x09A78E, 0x09A796], [0x09A796, 0x09A79C], [0x09A79C, 0x09A7A0], [0x09A7A0, 0x09A7A4],
        [0x09A7A4, 0x09A7B2], [0x09A7B2, 0x09A7B4], [0x09A7B4, 0x09A7C2], [0x09A7C2, 0x09A7CA],
        [0x09A7CA, 0x09A7CC], [0x09A7CC, 0x09A7DA], [0x09A7DA, 0x09A7E0], [0x09A7E0, 0x09A7E8],
        [0x09A7E8, 0x09A7EA], [0x09A7EA, 0x09A7EC], [0x09A7EC, 0x09A7F2], [0x09A7F2, 0x09A7F4],
        [0x09A7F4, 0x09A802], [0x09A802, 0x09A80A], [0x09A80A, 0x09A810], [0x09A810, 0x09A814],
        [0x09A814, 0x09A81C], [0x09A81C, 0x09A820], [0x09A820, 0x09A826], [0x09A826, 0x09A82C],
        [0x09A82C, 0x09A82E], [0x09A82E, 0x09A834], [0x09A834, 0x09A838], [0x09A838, 0x09A83A],
        [0x09A83A, 0x09A83C], [0x09A83C, 0x09A842], [0x09A842, 0x09A848], [0x09A848, 0x09A84E],
        [0x09A84E, 0x09A85A], [0x09A85A, 0x09A85C], [0x09A85C, 0x09A868], [0x09A868, 0x09A86E],
        [0x09A86E, 0x09A876], [0x09A876, 0x09A89C], [0x09A89C, 0x09A8A6], [0x09A8A6, 0x09A8A8],
        [0x09A8A8, 0x09A8AE], [0x09A8AE, 0x09A8BC], [0x09A8BC, 0x09A8C2], [0x09A8C2, 0x09A8C4],
        [0x09A8C4, 0x09A8D4], [0x09A8D4, 0x09A8D6], [0x09A8D6, 0x09A8E0], [0x09A8E0, 0x09A8EE],
        [0x09A8EE, 0x09A8FE],
    ],
}
ALLOWED_CALLS = {
    0x09A6D8: {},
    0x09A708: {
        0x09A84A: (0x09AE14, "opaque_external_call"),
        0x09A86A: (0x09A948, "opaque_external_call"),
        0x09A872: (0x09B3E0, "opaque_external_call"),
        0x09A898: (0x09A6D8, "included_root"),
        0x09A8D0: (0x09A684, "opaque_existing_veneer"),
        0x09A8DC: (0x09A998, "opaque_external_call"),
    },
}
EXPECTED_PRODUCERS = {
    0x09A6D8: {
        "thumb_bl": [0x09A60C, 0x09A898], "thumb_b": [], "thumb_b_conditional": [],
        "arm_b": [], "arm_bl": [], "bytewise_u32_entry": [], "bytewise_u32_thumb_pointer": [],
    },
    0x09A708: {
        "thumb_bl": [], "thumb_b": [], "thumb_b_conditional": [], "arm_b": [], "arm_bl": [],
        "bytewise_u32_entry": [], "bytewise_u32_thumb_pointer": [0x09AF24],
    },
}
PRODUCER_FORMS = tuple(next(iter(EXPECTED_PRODUCERS.values())).keys())
LITERAL_EXPECTATIONS = [
    (0x09A71A, 0x4979, 0x09A900, 0x03007FF0),
    (0x09A720, 0x4978, 0x09A904, 0x084647A8),
]
POINTER_RANGE = [0x09AF24, 0x09AF28]
POINTER_VALUE = 0x0809A709
POINTER_SHA256 = "ee8951cbf1e4a1f69fce481a4537a84678e2615bc7e3f175ff69a97044ab7016"
GAP_RANGES = [
    [0x09A6D2, 0x09A6D8],
    [0x09A8FE, 0x09A900],
    [0x09AEF4, 0x09AF24],
    [0x09AF28, 0x09AF34],
]
GAP_SHA256 = [
    "83391c178e79facc3d1c0dd948f1d4e3fc46d08591ae8929948a5e028b724daa",
    "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
    "e3f15479ef984fff85b6ec764159375c16eeecf938f7671851aaf38d2a2211ae",
    "56573725cd7c0ffc2159a0d40123cef9750f00c2f444a04492a4b32117cf4bc7",
]
SAPPY_BANK_PATH = Path("sequel/content/sappy-engine/bank.json")
SAPPY_BANK_SHA256 = "d71d8aff52746a61d59139d6ca4ccf3a9dd354b84ef90159276ca541cf82eb40"
SAPPY_RUNTIME_MANIFEST_PATH = Path("artifacts/sappy-engine-master-enable-ab-v1/manifest.json")
SAPPY_RUNTIME_MANIFEST_SHA256 = "62b97082417cc7d049b62bbb0bacfc92271e9924f674b13d6d5ee0fd8864fde8"
SAPPY_OWNER_RANGE = [0x09AE3C, 0x09AEF4]
SAPPY_OWNER_BYTES_SHA256 = "9586c815954c4b8a0c0d9872e7d500d128a540a2964a262b68da1e2df3cd9ef4"

UPSTREAM_PATHS = {
    "mplaymain": {
        "manifest": Path("artifacts/rom-mplaymain-scheduler-v1/manifest.json"),
        "payload": Path("artifacts/rom-mplaymain-scheduler-v1/rom-mplaymain-scheduler.json"),
        "exporter": Path("tools/export_rom_mplaymain_scheduler.py"),
        "verifier": Path("tools/verify_rom_mplaymain_scheduler.py"),
        "test": Path("tests/test_export_rom_mplaymain_scheduler.py"),
    },
    "initializer": {
        "manifest": Path("artifacts/rom-m4a-initializer-chain-v1/manifest.json"),
        "payload": Path("artifacts/rom-m4a-initializer-chain-v1/rom-m4a-initializer-chain.json"),
        "exporter": Path("tools/export_rom_m4a_initializer_chain.py"),
        "verifier": Path("tools/verify_rom_m4a_initializer_chain.py"),
        "test": Path("tests/test_export_rom_m4a_initializer_chain.py"),
    },
    "sappy_bank": {"bank": SAPPY_BANK_PATH},
    "sappy_runtime_manifest": {"manifest": SAPPY_RUNTIME_MANIFEST_PATH},
}
UPSTREAM_RECEIPTS = {
    "mplaymain": {
        "manifest_sha256": "43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d",
        "payload_sha256": "31bc026a8c83b3bf4af06746de2990a658bb86954a5aae31c45d63d68cf44f78",
        "exporter_sha256": "366c4e41db80c797bd01f36477a67243ac08f4d20d71e596c1332f273deed18d",
        "verifier_sha256": "c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a",
        "test_sha256": "e3804e5833b0d4249b286da8e1428397c02e8b04bd205e20c96e8ab1920b540c",
    },
    "initializer": {
        "manifest_sha256": "9b9b9f2f49a1ee8224703ca47b73dc608d75ba83d2be44564e24873c44237c9c",
        "payload_sha256": "7f019b01e800a3dd769463cbea907049429b1cad416dc17ed8719a561837babd",
        "exporter_sha256": "4e0b8743247d9098a9d72667f4b2499abee1c71c45cd5a704feaa54f17a4ced9",
        "verifier_sha256": "5cd9ccf232ebb10c69e89962e9861add7675dfb935c6e6a293b16049fd6cec31",
        "test_sha256": "b6ed2f247641c74bb1631e4bfb0e449d48ec1be03a7af08c4eecabcc8c297326",
    },
    "sappy_bank_sha256": SAPPY_BANK_SHA256,
    "sappy_runtime_manifest_sha256": SAPPY_RUNTIME_MANIFEST_SHA256,
}
EXPECTED_UPSTREAM_RECEIPTS = json.loads(json.dumps(UPSTREAM_RECEIPTS))

PAYLOAD_NAME = "rom-mp2k-note-allocator.json"
BUNDLE_NAME = "rom-mp2k-note-allocator.bin"
MANIFEST_NAME = "manifest.json"
ARTIFACT_RELATIVE = Path("build/experiments/active/mp2k-note-allocator-contract-20260829/luna-r1/candidate")

SCOPE = {
    "source_instruction_membership_complete": False,
    "natural_runtime_reachability": False,
    "global_code_producer_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_indirect_producer_denominator_complete": False,
    "global_computed_producer_denominator_complete": False,
    "global_ram_writer_denominator_complete": False,
    "literal_target_semantics_claimed": False,
    "audio_behavior_proven": False,
    "editing_relocation_writeback_safe": False,
    "allocatable_free_space_proven": False,
}
LIMITATIONS = [
    "This candidate classifies exactly 550 bounded Thumb instruction bytes, 8 consumed literal bytes, and one 4-byte initializer-consumed Thumb pointer.",
    "The target-limited raw producer denominator proves the listed source forms and mixed provenance roles only; it is not a global caller/code/indirect/computed producer proof.",
    "natural runtime reachability, global RAM writer completeness, and global producer completeness remain unproven.",
    "literal target semantics, audio behavior, editing, writeback, relocation, and allocatable/free-space safety remain outside scope.",
    "The explicitly excluded neighboring ranges remain unknown and are not padding, reserved, free, or allocatable space.",
]

_ENGINE: Cs | None = None
_EDGE_ORDER = {"branch_target": 0, "call_target": 1, "fallthrough": 2}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _bounded(rom: bytes, start: int, end: int, label: str = "ROM") -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"{label} range escapes ROM: 0x{start:06X}..0x{end:06X}")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2, "Thumb halfword"), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4, "ROM word"), "little")


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _validate_root(root: Path | str) -> Path:
    value = Path(root).expanduser().resolve(strict=True)
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


def _validate_rom(rom: bytes) -> None:
    if len(rom) != ROM_SIZE:
        raise ValueError(f"ROM size changed: {len(rom)}")
    if _sha(rom) != ROM_SHA256:
        raise ValueError("ROM SHA-256 changed")


def _engine() -> Cs:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        _ENGINE.detail = True
        _ENGINE.skipdata = False
    return _ENGINE


def _raw_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
    if len(raw) >= 4:
        first = int.from_bytes(raw[:2], "little")
        second = int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {"flow_kind": "call", "size": 4, "conditional": False, "target_offset": offset + 4 + _sign_extend(encoded, 23)}
    if len(raw) < 2:
        return None
    halfword = int.from_bytes(raw[:2], "little")
    condition = (halfword >> 8) & 0xF
    if halfword & 0xF000 == 0xD000 and condition <= 0xD:
        return {"flow_kind": "conditional_branch", "size": 2, "conditional": True, "target_offset": offset + 4 + _sign_extend((halfword & 0xFF) << 1, 9)}
    if halfword & 0xF800 == 0xE000:
        return {"flow_kind": "unconditional_branch", "size": 2, "conditional": False, "target_offset": offset + 4 + _sign_extend((halfword & 0x07FF) << 1, 12)}
    if halfword & 0xFF87 == 0x4700:
        return {"flow_kind": "bx", "size": 2, "conditional": False, "register": (halfword >> 3) & 0xF}
    return None


def _direct_target(instruction: Any) -> int:
    if len(instruction.operands) != 1 or instruction.operands[0].type != arm_const.ARM_OP_IMM:
        raise ValueError("direct branch operand changed")
    return instruction.operands[0].imm - ROM_BASE


def _decode_one(rom: bytes, root_offset: int, offset: int) -> dict[str, Any]:
    start, end = ROOT_BY_OFFSET[root_offset]["code_range"]
    if offset & 1 or not start <= offset < end:
        raise ValueError(f"invalid Thumb CFG offset: 0x{offset:06X}")
    decoded = tuple(_engine().disasm(_bounded(rom, offset, min(end, offset + 4), "instruction"), ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset:
        raise ValueError(f"Thumb CFG decode failed at 0x{offset:06X}")
    instruction = decoded[0]
    raw = _bounded(rom, offset, offset + instruction.size, "instruction")
    if instruction.size not in (2, 4) or offset + instruction.size > end:
        raise ValueError(f"Thumb instruction escapes frozen range at 0x{offset:06X}")
    raw_flow = _raw_flow(raw, offset)
    if instruction.id == arm_const.ARM_INS_BL:
        if raw_flow is None or raw_flow["flow_kind"] != "call" or raw_flow["target_offset"] != _direct_target(instruction):
            raise ValueError(f"raw/capstone control-flow mismatch at 0x{offset:06X}")
    elif instruction.id == arm_const.ARM_INS_B:
        expected_kind = "conditional_branch" if instruction.cc != arm_const.ARM_CC_AL else "unconditional_branch"
        if raw_flow is None or raw_flow["flow_kind"] != expected_kind or raw_flow["target_offset"] != _direct_target(instruction):
            raise ValueError(f"raw/capstone control-flow mismatch at 0x{offset:06X}")
    elif instruction.id == arm_const.ARM_INS_BX:
        if raw_flow is None or raw_flow["flow_kind"] != "bx":
            raise ValueError(f"raw/capstone control-flow mismatch at 0x{offset:06X}")
    elif raw_flow is not None:
        raise ValueError(f"raw/capstone control-flow mismatch at 0x{offset:06X}")

    flow_kind = "linear"
    conditional = instruction.cc not in (arm_const.ARM_CC_AL, arm_const.ARM_CC_INVALID)
    successors: list[dict[str, Any]] = []
    frontier: list[dict[str, Any]] = []
    next_offset = offset + instruction.size
    if raw_flow is not None and raw_flow["flow_kind"] in {"call", "conditional_branch", "unconditional_branch"}:
        flow_kind = {"call": "call", "conditional_branch": "conditional_branch", "unconditional_branch": "unconditional_branch"}[raw_flow["flow_kind"]]
        conditional = raw_flow["conditional"]
        successors.append({"kind": "call_target" if flow_kind == "call" else "branch_target", "target_offset": raw_flow["target_offset"], "target_mode": "thumb"})
        if flow_kind in {"call", "conditional_branch"}:
            successors.append({"kind": "fallthrough", "target_offset": next_offset, "target_mode": "thumb"})
    elif raw_flow is not None and raw_flow["flow_kind"] == "bx":
        register = raw_flow["register"]
        if offset == RETURN_OFFSETS[root_offset] and ((root_offset == 0x09A6D8 and register == 14) or (root_offset == 0x09A708 and register == 0)):
            flow_kind = "return"
        else:
            flow_kind = "indirect_branch"
            frontier.append({"reason": "indirect_branch", "register": register})
    else:
        successors.append({"kind": "fallthrough", "target_offset": next_offset, "target_mode": "thumb"})
    successors.sort(key=lambda row: (_EDGE_ORDER[row["kind"]], row["target_offset"]))
    return {
        "root": ROOT_BY_OFFSET[root_offset]["id"],
        "root_offset": root_offset,
        "offset": offset,
        "gba_address": _gba(offset),
        "mode": "thumb",
        "size": instruction.size,
        "raw_hex": raw.hex(),
        "bytes_sha256": _sha(raw),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "flow_kind": flow_kind,
        "raw_flow_kind": raw_flow["flow_kind"] if raw_flow else None,
        "conditional": conditional,
        "successors": successors,
        "frontiers": frontier,
    }


def _validate_stack_epilogue(rom: bytes) -> dict[str, Any]:
    expected = {
        0x09A8EE: bytes.fromhex("06b0"), 0x09A8F0: bytes.fromhex("ffbc"),
        0x09A8F2: bytes.fromhex("8046"), 0x09A8F4: bytes.fromhex("8946"),
        0x09A8F6: bytes.fromhex("9246"), 0x09A8F8: bytes.fromhex("9b46"),
        0x09A8FA: bytes.fromhex("01bc"), 0x09A8FC: bytes.fromhex("0047"),
    }
    if any(_bounded(rom, offset, offset + 2, "stack epilogue") != raw for offset, raw in expected.items()):
        raise ValueError("stack epilogue changed")
    return {
        "range": [0x09A8EE, 0x09A8FE],
        "steps": [
            [0x09A8EE, "add sp,#0x18"],
            [0x09A8F0, "pop {r0, r1, r2, r3, r4, r5, r6, r7}"],
            [0x09A8F2, "mov r8, r0"], [0x09A8F4, "mov sb, r1"],
            [0x09A8F6, "mov sl, r2"], [0x09A8F8, "mov fp, r3"],
            [0x09A8FA, "pop {r0}"], [0x09A8FC, "bx r0"],
        ],
        "return_offset": 0x09A8FC,
        "exact": True,
    }


def _walk_root(rom: bytes, root_offset: int) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    start, end = ROOT_BY_OFFSET[root_offset]["code_range"]
    pending = [start]
    seen: dict[int, dict[str, Any]] = {}
    calls: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in seen:
            continue
        node = _decode_one(rom, root_offset, offset)
        seen[offset] = node
        for edge in node["successors"]:
            target = edge["target_offset"]
            if edge["kind"] == "call_target":
                expected = ALLOWED_CALLS[root_offset].get(offset)
                if expected is None or expected[0] != target:
                    raise ValueError(f"direct call denominator changed at 0x{offset:06X}")
                calls.append({
                    "source_instruction_offset": offset,
                    "source_gba_address": _gba(offset),
                    "kind": "call_target",
                    "target_offset": target,
                    "target_gba_address": _gba(target),
                    "target_mode": "thumb",
                    "resolution": expected[1],
                    "target_root": ROOT_BY_OFFSET[target]["id"] if expected[1] == "included_root" else None,
                })
                if expected[1] == "included_root":
                    continue
                continue
            if not start <= target < end or target & 1:
                raise ValueError(f"CFG branch escaped frozen range from 0x{offset:06X} to 0x{target:06X}")
            heapq.heappush(pending, target)
    owners: dict[int, int] = {}
    for offset, node in seen.items():
        for byte_offset in range(offset, offset + node["size"]):
            if byte_offset in owners and owners[byte_offset] != offset:
                raise ValueError("CFG target lands in an instruction middle")
            owners[byte_offset] = offset
    if set(owners) != set(range(start, end)):
        raise ValueError(f"CFG code range is not closed for 0x{root_offset:06X}")
    if sum(node["size"] for node in seen.values()) != end - start:
        raise ValueError("CFG instruction denominator changed")
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
            if edge["kind"] != "fallthrough" or edge["target_offset"] in leaders or edge["target_offset"] != offset + node["size"]:
                break
            offset = edge["target_offset"]
        if not members:
            continue
        last = nodes[members[-1]]
        block_end = members[-1] + last["size"]
        blocks.append({
            "id": block_by_offset[leader],
            "root": ROOT_BY_OFFSET[root_offset]["id"],
            "mode": "thumb",
            "range": [leader, block_end],
            "gba_range": [_gba(leader), _gba(block_end)],
            "instruction_count": len(members),
            "bytes_sha256": _sha(_bounded(rom, leader, block_end, "block")),
            "terminator": {
                "offset": members[-1], "size": last["size"], "raw_hex": last["raw_hex"],
                "mnemonic": last["mnemonic"], "op_str": last["op_str"],
                "flow_kind": last["flow_kind"], "conditional": last["conditional"],
            },
            "successors": [],
        })
    if len(block_by_offset) != len(nodes):
        raise ValueError("CFG block partition omitted instructions")
    calls_by_source = {row["source_instruction_offset"]: row for row in calls}
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["offset"]
        node = nodes[source]
        for successor in node["successors"]:
            target = successor["target_offset"]
            if target in nodes:
                record = {
                    "source_block_id": block["id"], "source_instruction_offset": source,
                    "kind": successor["kind"], "target_offset": target, "target_mode": "thumb",
                    "target_block_id": block_by_offset[target], "target_scheduled": True,
                    "resolution": "internal",
                }
                block["successors"].append(record)
                edges.append(record)
            elif successor["kind"] == "call_target":
                call = calls_by_source.get(source)
                if call is None:
                    raise ValueError("external CFG edge binding changed")
                record = {**call, "source_block_id": block["id"]}
                block["successors"].append(record)
                # External calls are provenance, not internal control edges.
            else:
                raise ValueError("non-call CFG edge escaped root")
    blocks.sort(key=lambda row: row["range"][0])
    edges.sort(key=lambda row: (row["source_instruction_offset"], _EDGE_ORDER[row["kind"]], row["target_offset"]))
    return blocks, edges


def _analyze_cfg(rom: bytes) -> dict[str, Any]:
    stack = _validate_stack_epilogue(rom)
    all_nodes: dict[int, dict[str, Any]] = {}
    all_blocks: list[dict[str, Any]] = []
    ordinary_edges: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    for root in ROOTS:
        nodes, root_calls = _walk_root(rom, root["file_offset"])
        blocks, edges = _build_blocks(rom, root["file_offset"], nodes, root_calls)
        all_nodes.update(nodes)
        all_blocks.extend(blocks)
        ordinary_edges.extend(edges)
        calls.extend(root_calls)
        root_rows.append({
            "id": root["id"], "file_offset": root["file_offset"], "gba_address": _gba(root["file_offset"]),
            "mode": "thumb", "code_range": list(root["code_range"]),
            "block_ranges": [list(block["range"]) for block in blocks],
            "instruction_count": len(nodes), "instruction_bytes": sum(node["size"] for node in nodes.values()),
            "internal_edge_count": len(edges),
        })
    calls.sort(key=lambda row: row["source_instruction_offset"])
    all_blocks.sort(key=lambda row: row["range"][0])
    ordinary_edges.sort(key=lambda row: (row["source_instruction_offset"], _EDGE_ORDER[row["kind"]], row["target_offset"]))
    if len(all_nodes) != 269 or sum(node["size"] for node in all_nodes.values()) != 550:
        raise ValueError("CFG instruction denominator changed")
    if [row["block_ranges"] for row in root_rows] != [EXPECTED_BLOCK_RANGES[0x09A6D8], EXPECTED_BLOCK_RANGES[0x09A708]]:
        raise ValueError("CFG block denominator changed")
    if len(all_blocks) != 66 or len(ordinary_edges) != 98 or len(calls) != 6:
        raise ValueError("CFG block/edge denominator changed")
    included = [row for row in calls if row["resolution"] == "included_root"]
    if len(included) != 1:
        raise ValueError("included-root call denominator changed")
    block_map = {offset: block["id"] for block in all_blocks for offset in [block["range"][0]]}
    source_block = next(block for block in all_blocks if block["range"][0] <= included[0]["source_instruction_offset"] < block["range"][1])
    included_edge = {
        **included[0], "source_block_id": source_block["id"], "target_block_id": block_map[0x09A6D8],
        "target_scheduled": True,
    }
    all_edges = sorted(ordinary_edges + [included_edge], key=lambda row: (row["source_instruction_offset"], _EDGE_ORDER[row["kind"]], row["target_offset"]))
    returns = [node for node in all_nodes.values() if node["flow_kind"] == "return"]
    frontiers = [frontier for node in all_nodes.values() for frontier in node["frontiers"]]
    if len(returns) != 2 or frontiers:
        raise ValueError("return/frontier denominator changed")
    semantic_vector = [
        [node["offset"], node["size"], node["raw_hex"], node["flow_kind"],
         [[edge["kind"], edge["target_offset"]] for edge in node["successors"]]]
        for node in (all_nodes[offset] for offset in sorted(all_nodes))
    ]
    edge_vector = [[row["source_instruction_offset"], row["kind"], row["target_offset"], row["resolution"]] for row in all_edges]
    summary = {
        "instruction_count": len(all_nodes), "instruction_bytes": 550, "code_bytes": 550,
        "block_count": len(all_blocks), "ordinary_internal_edge_count": len(ordinary_edges),
        "internal_edge_count": len(all_edges), "external_edge_count": 5,
        "direct_call_count": len(calls), "included_root_call_edge_count": 1,
        "opaque_external_call_count": 5, "structured_return_count": len(returns),
        "frontier_count": 0, "unresolved_frontier_count": 0, "budget_exhausted": False,
    }
    return {
        "roots": root_rows,
        "code_ranges": [list(interval) for interval in CODE_RANGES],
        "instructions": [all_nodes[offset] for offset in sorted(all_nodes)],
        "blocks": all_blocks,
        "block_edges": all_edges,
        "calls": calls,
        "returns": [{"offset": node["offset"], "gba_address": _gba(node["offset"]), "mode": "thumb"} for node in sorted(returns, key=lambda item: item["offset"])],
        "frontiers": frontiers,
        "stack_epilogue": stack,
        "semantic_instruction_vector": semantic_vector,
        "semantic_instruction_vector_sha256": _sha(_canonical(semantic_vector)),
        "edge_vector_sha256": _sha(_canonical(edge_vector)),
        "summary": summary,
    }


def _literal_bindings(rom: bytes, instructions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_offsets = {row[0] for row in LITERAL_EXPECTATIONS}
    rows: list[dict[str, Any]] = []
    refs: list[tuple[int, int, int]] = []
    for node in instructions:
        if node["size"] != 2:
            continue
        raw = bytes.fromhex(node["raw_hex"])
        halfword = int.from_bytes(raw, "little")
        if halfword & 0xF800 != 0x4800:
            continue
        literal_offset = ((node["offset"] + 4) & ~3) + (halfword & 0xFF) * 4
        refs.append((node["offset"], halfword, literal_offset))
    if {offset for offset, _, _ in refs if PROMOTION_RANGES[2][0] <= _ < PROMOTION_RANGES[2][1]} != expected_offsets:
        raise ValueError("literal reference denominator changed")
    if len(refs) != 2:
        raise ValueError("literal reference denominator changed")
    for offset, raw_halfword, literal_offset, value in LITERAL_EXPECTATIONS:
        matching = [row for row in refs if row[0] == offset and row[1] == raw_halfword and row[2] == literal_offset]
        if len(matching) != 1:
            raise ValueError("literal target changed")
        actual = _u32(rom, literal_offset)
        if actual != value:
            raise ValueError("literal word changed")
        rows.append({
            "instruction_offset": offset, "raw": raw_halfword,
            "literal_offset": literal_offset, "value": value,
            "raw_hex": _bounded(rom, literal_offset, literal_offset + 4, "literal").hex(),
        })
    if _bounded(rom, 0x09A900, 0x09A908, "literal pool") != bytes.fromhex("f07f0003a8474608"):
        raise ValueError("literal pool hole or word changed")
    return rows


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


def _pointer_occurrences(rom: bytes, value: int) -> list[int]:
    needle = struct.pack("<I", value)
    found: list[int] = []
    cursor = 0
    while True:
        cursor = rom.find(needle, cursor)
        if cursor < 0:
            return found
        found.append(cursor)
        cursor += 1


def _scan_producer_forms(rom: bytes) -> dict[int, dict[str, list[int]]]:
    forms = {target: {name: [] for name in PRODUCER_FORMS} for target in ROOT_BY_OFFSET}
    for offset in range(0, len(rom) - 3, 2):
        target = _thumb_bl_target(rom, offset)
        for root_target in forms:
            if target == root_target:
                forms[root_target]["thumb_bl"].append(offset)
    for offset in range(0, len(rom) - 1, 2):
        branch = _thumb_branch_target(rom, offset)
        if branch is not None:
            name, target = branch
            if target in forms:
                forms[target][name].append(offset)
    for offset in range(0, len(rom) - 3, 4):
        branch = _arm_branch_target(rom, offset)
        if branch is not None:
            name, target = branch
            if target in forms:
                forms[target][name].append(offset)
    for target in forms:
        forms[target]["bytewise_u32_entry"] = _pointer_occurrences(rom, ROM_BASE + target)
        forms[target]["bytewise_u32_thumb_pointer"] = _pointer_occurrences(rom, ROM_BASE + target + 1)
        for values in forms[target].values():
            values.sort()
    for target, expected in EXPECTED_PRODUCERS.items():
        if forms[target] != expected:
            raise ValueError("target producer form denominator changed")
    vector = [{"target_file_offset": target, "forms": forms[target]} for target in ROOT_BY_OFFSET]
    roles = [
        {"target_offset": 0x09A6D8, "form": "thumb_bl", "source_offset": 0x09A60C, "role": "preowned_provenance", "owner_claim_id": "mplaymain-code-00-09a42c", "promoted": False},
        {"target_offset": 0x09A6D8, "form": "thumb_bl", "source_offset": 0x09A898, "role": "included_root_call_edge", "owner_claim_id": None, "promoted": True},
        {"target_offset": 0x09A708, "form": "bytewise_u32_thumb_pointer", "source_offset": 0x09AF24, "role": "promoted_entry_pointer", "owner_claim_id": None, "promoted": True},
    ]
    return {
        "scan": {"mode": "raw-rom", "alignment_bytes": 2, "range": [0, ROM_SIZE], "forms": list(PRODUCER_FORMS)},
        "thumb_bl": [0x09A60C, 0x09A898],
        "root_forms": {f"0x{target:06X}": forms[target] for target in ROOT_BY_OFFSET},
        "producer_form_vector": vector,
        "producer_form_vector_sha256": _sha(_canonical(vector)),
        "producer_roles": roles,
        "producer_source_membership_by_role": {"preowned_provenance": True, "included_root_call_edge": True, "promoted_entry_pointer": True},
        "all_producer_source_membership_proven": True,
        "all_producer_bytes_promoted": False,
        "target_limited_raw_producer_denominator_complete": True,
        "global_producer_denominator_complete": False,
        "computed_or_indirect_producer_denominator_complete": False,
    }


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
        if not isinstance(segment, dict):
            raise ValueError("coverage baseline segment changed")
        raw_range = segment.get("range")
        if not isinstance(raw_range, list) or len(raw_range) != 2 or not all(isinstance(value, int) for value in raw_range) or raw_range[1] <= raw_range[0]:
            raise ValueError("coverage baseline has invalid segment range")
        normalized.append((raw_range[0], raw_range[1], segment))
    normalized.sort()
    for left, right in zip(normalized, normalized[1:]):
        if left[1] > right[0]:
            raise ValueError("coverage baseline segments overlap")
    target_segments: list[dict[str, Any]] = []
    unknown_bytes = 0
    overlap_bytes = 0
    for start, end in PROMOTION_RANGES:
        cursor = start
        for segment_start, segment_end, segment in normalized:
            if segment_end <= start:
                continue
            if segment_start >= end:
                break
            left, right = max(start, segment_start), min(end, segment_end)
            if left != cursor or right <= left:
                raise ValueError("coverage baseline promotion ranges are not whole-range unknown")
            primary_class = segment.get("primary_class")
            claim_ids = segment.get("primary_claim_ids")
            unknown = primary_class == "unknown" and claim_ids in (None, [])
            if not unknown:
                overlap_bytes += right - left
            else:
                unknown_bytes += right - left
            target_segments.append({"range": [left, right], "primary_class": "unknown" if unknown else primary_class, "primary_claim_ids": [] if unknown else claim_ids})
            cursor = right
        if cursor != end:
            raise ValueError("coverage baseline promotion ranges are not whole-range unknown")
    if unknown_bytes != 562 or overlap_bytes != 0:
        raise ValueError("coverage baseline promotion ranges are not whole-range unknown")
    return {
        "path": COVERAGE_PATH.as_posix(), "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256,
        "summary": dict(COVERAGE_SUMMARY), "promotion_bytes": 562, "unknown_promotion_bytes": 562,
        "primary_overlap_bytes": 0, "all_promotion_bytes_unknown": True, "target_segments": target_segments,
    }


def _load_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _coverage_baseline(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    return analyze_coverage_baseline(_load_json(raw, "coverage baseline"))


def _coverage_baseline_from_artifact(root: Path, artifact: Path | str) -> tuple[dict[str, Any], dict[str, Any]]:
    requested = Path(artifact).expanduser()
    if requested.is_absolute():
        lexical = Path(os.path.abspath(requested))
        _reject_symlink_components(lexical)
        try:
            relative = lexical.relative_to(root)
        except (ValueError, FileNotFoundError) as error:
            raise ValueError("coverage baseline artifact escapes repository root") from error
    else:
        relative = requested
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("coverage baseline artifact path changed")
    manifest_path = _safe_file(root, relative / "manifest.json")
    manifest_raw = manifest_path.read_bytes()
    manifest = _load_json(manifest_raw, "coverage baseline artifact manifest")
    if _canonical(manifest) != manifest_raw or manifest.get("artifact_status") != "accepted" or manifest.get("schema") != "rom-byte-coverage-prepromotion-baseline-v1":
        raise ValueError("coverage baseline artifact manifest identity changed")
    coverage_meta = manifest.get("coverage")
    raw_meta = coverage_meta.get("raw") if isinstance(coverage_meta, dict) else None
    archive_meta = coverage_meta.get("archive") if isinstance(coverage_meta, dict) else None
    if raw_meta != {"canonical_json": True, "schema": "rom-byte-coverage-v1", "sha256": COVERAGE_SHA256, "size": raw_meta.get("size") if isinstance(raw_meta, dict) else None, "summary": dict(COVERAGE_SUMMARY)}:
        # The raw size is immutable but not supplied by the public contract;
        # validate it against the decompressed bytes below.
        if not isinstance(raw_meta, dict) or raw_meta.get("canonical_json") is not True or raw_meta.get("schema") != "rom-byte-coverage-v1" or raw_meta.get("sha256") != COVERAGE_SHA256 or raw_meta.get("summary") != dict(COVERAGE_SUMMARY) or not isinstance(raw_meta.get("size"), int):
            raise ValueError("coverage baseline artifact raw identity changed")
    if not isinstance(archive_meta, dict) or archive_meta.get("compression") != "gzip" or not isinstance(archive_meta.get("file"), str) or not isinstance(archive_meta.get("size"), int) or not isinstance(archive_meta.get("sha256"), str):
        raise ValueError("coverage baseline artifact archive identity changed")
    archive_name = Path(archive_meta["file"])
    if archive_name.is_absolute() or ".." in archive_name.parts or archive_name.name != archive_meta["file"]:
        raise ValueError("coverage baseline artifact archive path changed")
    archive_path = _safe_file(root, relative / archive_name)
    archive_raw = archive_path.read_bytes()
    if len(archive_raw) != archive_meta["size"] or _sha(archive_raw) != archive_meta["sha256"]:
        raise ValueError("coverage baseline artifact archive identity changed")
    try:
        coverage_raw = gzip.decompress(archive_raw)
    except OSError as error:
        raise ValueError("coverage baseline artifact gzip is invalid") from error
    if len(coverage_raw) != raw_meta["size"] or _sha(coverage_raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline artifact raw identity changed")
    coverage = _load_json(coverage_raw, "coverage baseline artifact raw")
    if _canonical(coverage) != coverage_raw:
        raise ValueError("coverage baseline artifact raw is not canonical")
    baseline = analyze_coverage_baseline(coverage)
    source = {
        "kind": "immutable-gzip-artifact", "artifact": relative.as_posix(),
        "manifest_sha256": _sha(manifest_raw), "archive_file": archive_name.as_posix(),
        "archive_size": len(archive_raw), "archive_sha256": _sha(archive_raw),
        "raw_size": len(coverage_raw), "raw_sha256": COVERAGE_SHA256,
        "recovery_kind": manifest.get("recovery", {}).get("kind"),
    }
    return baseline, source


def _validate_upstream_receipts(root: Path) -> None:
    if UPSTREAM_RECEIPTS != EXPECTED_UPSTREAM_RECEIPTS:
        raise ValueError("upstream receipt contract changed")
    for name in ("mplaymain", "initializer"):
        for role, path in UPSTREAM_PATHS[name].items():
            actual = _sha(_safe_file(root, path).read_bytes())
            if actual != UPSTREAM_RECEIPTS[name][f"{role}_sha256"]:
                raise ValueError(f"upstream {name} {role} receipt changed")
        manifest = _load_json(_safe_file(root, UPSTREAM_PATHS[name]["manifest"]).read_bytes(), f"upstream {name} manifest")
        if manifest.get("artifact_status") != "accepted":
            raise ValueError(f"upstream {name} artifact is not accepted")
    if _sha(_safe_file(root, SAPPY_BANK_PATH).read_bytes()) != SAPPY_BANK_SHA256:
        raise ValueError("sappy bank receipt changed")
    if _sha(_safe_file(root, SAPPY_RUNTIME_MANIFEST_PATH).read_bytes()) != SAPPY_RUNTIME_MANIFEST_SHA256:
        raise ValueError("sappy runtime manifest receipt changed")


def _pointer_binding(root: Path, rom: bytes) -> dict[str, Any]:
    raw = _bounded(rom, *POINTER_RANGE, "entry pointer")
    if _sha(raw) != POINTER_SHA256 or _u32(rom, POINTER_RANGE[0]) != POINTER_VALUE:
        raise ValueError("entry pointer bytes changed")
    occurrences = _pointer_occurrences(rom, POINTER_VALUE)
    if occurrences != [POINTER_RANGE[0]]:
        raise ValueError("entry pointer occurrence denominator changed")
    if _thumb_bl_target(rom, 0x09AA50) != 0x09AE3C:
        raise ValueError("initializer writer BL changed")
    if _u16(rom, 0x09AE40) != 0x1C05:
        raise ValueError("initializer writer r0-to-r5 copy changed")
    if _u16(rom, 0x09AEC8) != 0x4816:
        raise ValueError("initializer pointer LDR changed")
    pointer_target = ((0x09AEC8 + 4) & ~3) + ((_u16(rom, 0x09AEC8) & 0xFF) * 4)
    if pointer_target != POINTER_RANGE[0] or _u16(rom, 0x09AECA) != 0x63A8:
        raise ValueError("initializer pointer slot store changed")
    owner_raw = _bounded(rom, *SAPPY_OWNER_RANGE, "sappy owner")
    if _sha(owner_raw) != SAPPY_OWNER_BYTES_SHA256:
        raise ValueError("sappy owner bytes changed")
    if _u16(rom, 0x09A460) != 0x488A:
        raise ValueError("SoundInfo consumer base load changed")
    sound_info_cell = ((0x09A460 + 4) & ~3) + ((_u16(rom, 0x09A460) & 0xFF) * 4)
    if sound_info_cell != 0x09A68C or _u16(rom, 0x09A462) != 0x6800 or _u32(rom, sound_info_cell) != 0x03007FF0:
        raise ValueError("SoundInfo fixed cell dereference changed")
    if _u16(rom, 0x09A4EA) != 0x7811 or _u16(rom, 0x09A4F0) != 0x79E9:
        raise ValueError("u8 command source changed")
    if _u16(rom, 0x09A4FE) != 0x29CF or _u16(rom, 0x09A500) != 0xD308 or _u16(rom, 0x09A502) != 0x4640 or _u16(rom, 0x09A504) != 0x6B83 or _u16(rom, 0x09A508) != 0x38CF:
        raise ValueError("SoundInfo+0x38 consumer chain changed")
    if _thumb_bl_target(rom, 0x09A50E) != 0x09A684:
        raise ValueError("SoundInfo handler veneer call changed")
    if _u16(rom, 0x09A684) != 0x4718:
        raise ValueError("SoundInfo handler bx r3 veneer changed")
    return {
        "range": list(POINTER_RANGE), "raw_hex": raw.hex(), "value": f"0x{POINTER_VALUE:08X}",
        "occurrences": occurrences, "occurrence_count": len(occurrences),
        "writer": {
            "chain": [[0x09AA50, 0x09AE3C], [0x09AE40, "r0->r5"], [0x09AEC8, 0x09AF24], [0x09AECA, "[r5,#0x38]"],
                      [0x09AE3C, 0x09AEF4]],
            "initializer_root": 0x09AE3C, "owner_claim_id": "bank-sappy-engine-000",
            "owner_range": list(SAPPY_OWNER_RANGE), "owner_bytes_sha256": SAPPY_OWNER_BYTES_SHA256,
            "sappy_bank_sha256": SAPPY_BANK_SHA256, "runtime_manifest_sha256": SAPPY_RUNTIME_MANIFEST_SHA256,
        },
        "consumer": {
            "sound_info_load": 0x09A460,
            "sound_info_dereference": {"offset": 0x09A462, "raw": 0x6800, "kind": "ldr_word_from_fixed_cell"},
            "sound_info_fixed_cell": {"offset": sound_info_cell, "value": 0x03007FF0, "raw_hex": _bounded(rom, sound_info_cell, sound_info_cell + 4, "SoundInfo cell").hex()},
            "command_source": "u8",
            "cmp": {"offset": 0x09A4FE, "immediate": 0xCF},
            "unsigned_branch": {"offset": 0x09A500, "raw": 0xD308, "kind": "blo"},
            "accepted_argument_domain": [0, 48], "accepted_value_count": 49,
            "load_offset": 0x09A502, "load_offset_end": 0x09A504,
            "subtract": {"offset": 0x09A508, "immediate": 0xCF},
            "call_offset": 0x09A50E, "call_target": 0x09A684,
            "veneer": {"offset": 0x09A684, "raw": 0x4718, "kind": "bx_r3"},
        },
        "global_ram_writer_denominator_complete": False,
    }


def _promotion_contract_guard() -> None:
    if PROMOTION_RANGES != [[0x09A6D8, 0x09A708], [0x09A708, 0x09A8FE], [0x09A900, 0x09A908], [0x09AF24, 0x09AF28]]:
        raise ValueError("promotion range schema changed")
    if PROMOTION_RANGE_SHA256 != [
        "04988bf8e911a12b477d9aafa24342b68e83960a06796e555869cc67b24bd4d2",
        "4c78dfb62e2d92b0b0ed96c8d05e86d3d2867a1bb2a76c82818a672f380eee2e",
        "aea41d042f130b46329f8b5a5fdb976816ec280b367dc424f28bc624072867c1",
        "ee8951cbf1e4a1f69fce481a4537a84678e2615bc7e3f175ff69a97044ab7016",
    ] or PROMOTION_UNION_RANGES != [[0x09A6D8, 0x09A8FE], [0x09A900, 0x09A908], [0x09AF24, 0x09AF28]]:
        raise ValueError("promotion vector schema changed")


def _promotion_rows(rom: bytes) -> list[dict[str, Any]]:
    _promotion_contract_guard()
    specs = [
        ("mp2k-channel-gain-code-09a6d8", "bounded_thumb_code", "thumb", "armv4t_mp2k_channel_gain_thumb_code", "mp2k_channel_gain_bounded_thumb_code"),
        ("mp2k-note-allocator-code-09a708", "bounded_thumb_code", "thumb", "armv4t_mp2k_note_allocator_thumb_code", "mp2k_note_allocator_bounded_thumb_code"),
        ("mp2k-note-allocator-literals-09a900", "consumed_literals", None, "mp2k_note_allocator_consumed_literals", "mp2k_note_allocator_consumed_literals"),
        ("mp2k-note-entry-pointer-09af24", "initializer_consumed_thumb_pointer", None, "mp2k_initializer_consumed_thumb_pointer", "mp2k_note_entry_initializer_consumed_thumb_pointer"),
    ]
    rows: list[dict[str, Any]] = []
    for index, (row_id, kind, mode, semantic_class, claim_kind) in enumerate(specs):
        start, end = PROMOTION_RANGES[index]
        raw = _bounded(rom, start, end, "promotion")
        if len(raw) != end - start or _sha(raw) != PROMOTION_RANGE_SHA256[index]:
            raise ValueError(f"promotion range bytes changed: {row_id}")
        rows.append({
            "id": row_id, "kind": kind, "range": [start, end], "size": end - start,
            "sha256": PROMOTION_RANGE_SHA256[index], "mode": mode,
            "semantic_class": semantic_class, "claim_kind": claim_kind,
        })
    return rows


def _excluded_ranges(rom: bytes) -> list[dict[str, Any]]:
    rows = []
    for interval, digest in zip(GAP_RANGES, GAP_SHA256):
        raw = _bounded(rom, *interval, "excluded neighbor")
        if _sha(raw) != digest:
            raise ValueError("excluded-neighbor bytes changed")
        rows.append({"range": list(interval), "bytes": len(raw), "sha256": digest, "promoted": False, "semantic_class": "unknown", "promotion_excluded": True})
    return rows


def build_payload_from_rom(root: Path | str, rom: bytes, *, coverage_baseline_artifact: Path | str | None = None) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    data = bytes(rom)
    _validate_rom(data)
    _validate_upstream_receipts(repository)
    if coverage_baseline_artifact is None:
        coverage = _coverage_baseline(repository)
        coverage_source = None
    else:
        coverage, coverage_source = _coverage_baseline_from_artifact(repository, coverage_baseline_artifact)
    rows = _promotion_rows(data)
    excluded = _excluded_ranges(data)
    cfg = _analyze_cfg(data)
    literals = _literal_bindings(data, cfg["instructions"])
    producer = _scan_producer_forms(data)
    pointer = _pointer_binding(repository, data)
    bundle = b"".join(_bounded(data, start, end, "promotion") for start, end in PROMOTION_RANGES)
    if len(bundle) != 562 or _sha(bundle) != PACKED_SHA256:
        raise ValueError("promotion packed bytes changed")
    if _sha(_compact(PROMOTION_UNION_RANGES)) != RANGE_VECTOR_SHA256:
        raise ValueError("promotion range vector receipt changed")
    post = {"classified_bytes": coverage["summary"]["classified_bytes"] + 562, "unknown_bytes": coverage["summary"]["unknown_bytes"] - 562, "claim_count": coverage["summary"]["claim_count"] + 4, "segment_count": coverage["summary"]["segment_count"] + 6}
    if post != PROJECTED_COVERAGE_SUMMARY:
        raise ValueError("coverage post projection changed")
    claims = [{**row, "role": "primary", "promotion_batch": SCHEMA, "promoted_from_primary_class": "unknown", "non_claims": dict(SCOPE), "limitations": list(LIMITATIONS)} for row in rows]
    literal_vector = [[row["instruction_offset"], row["literal_offset"], row["value"]] for row in literals]
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(data), "sha256": BASE_ROM_SHA256},
        "coverage_baseline": coverage,
        "coverage_projection": {"pre": dict(coverage["summary"]), "post": post, "classified_delta": 562, "unknown_delta": -562, "claim_delta": 4, "segment_delta": 6},
        "upstream_receipts": json.loads(json.dumps(UPSTREAM_RECEIPTS)),
        "roots": cfg["roots"], "cfg": cfg,
        "code_ranges": [list(interval) for interval in CODE_RANGES], "literal_ranges": [list(interval) for interval in LITERAL_RANGES],
        "unclassified_unknown_ranges": [list(interval) for interval in GAP_RANGES],
        "promotion_ranges": rows, "coverage_claims": claims,
        "literal_bindings": literals, "literal_binding_vector": literal_vector, "literal_binding_vector_sha256": _sha(_canonical(literal_vector)),
        "literal_summary": {"ref_count": len(literals), "word_count": len({row["literal_offset"] for row in literals}), "bytes": 8},
        "producer_denominator": producer, "entry_pointer": pointer, "excluded_ranges": excluded,
        "promotion": {"ranges": [list(interval) for interval in PROMOTION_RANGES], "union_ranges": [list(interval) for interval in PROMOTION_UNION_RANGES], "union_range_count": 3, "union_bytes": 562, "range_count": 4, "byte_count": 562, "range_sha256": list(PROMOTION_RANGE_SHA256), "range_vector_sha256": RANGE_VECTOR_SHA256, "packed_bytes_sha256": PACKED_SHA256, "code_bytes": 550, "literal_bytes": 8, "pointer_bytes": 4},
        "packed_layout": [{"range": list(row["range"]), "kind": row["kind"], "bundle_offset": sum(item["size"] for item in rows[:index]), "size": row["size"], "sha256": row["sha256"]} for index, row in enumerate(rows)],
        "packed_binary": {"file": BUNDLE_NAME, "size": len(bundle), "sha256": _sha(bundle)},
        "scope": dict(SCOPE), "limitations": list(LIMITATIONS),
        "summary": {**cfg["summary"], "literal_ref_count": len(literals), "literal_word_count": len({row["literal_offset"] for row in literals}), "literal_bytes": 8, "pointer_bytes": 4, "promoted_bytes": len(bundle), "promotion_claim_count": len(claims), "promotion_range_count": len(rows), "producer_count": 3, "gap_exclusion_bytes": sum(row["bytes"] for row in excluded)},
    }
    if coverage_source is not None:
        payload["coverage_baseline_source"] = coverage_source
    return payload, bundle


def build_payload(root: Path | str, *, coverage_baseline_artifact: Path | str | None = None) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    return build_payload_from_rom(repository, _safe_file(repository, ROM_PATH).read_bytes(), coverage_baseline_artifact=coverage_baseline_artifact)


def _validate_output(root: Path, output: Path | str) -> Path:
    value = Path(output).expanduser()
    if not value.is_absolute():
        value = root / value
    _reject_symlink_components(value)
    value = value.resolve(strict=False)
    try:
        value.relative_to(root)
    except ValueError as error:
        raise ValueError("output must stay inside repository root") from error
    if value == root:
        raise ValueError("output must not be repository root")
    if value.exists():
        if value.is_symlink() or not value.is_dir() or any(value.iterdir()):
            raise ValueError("output directory must be new and empty")
    return value


def _implementation(root: Path) -> dict[str, dict[str, Any]]:
    paths = {"exporter": Path("tools/export_rom_mp2k_note_allocator.py"), "verifier": Path("tools/verify_rom_mp2k_note_allocator.py"), "exporter_test": Path("tests/test_export_rom_mp2k_note_allocator.py"), "verifier_test": Path("tests/test_verify_rom_mp2k_note_allocator.py")}
    return {role: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in paths.items()}


def _manifest(payload: dict[str, Any], payload_raw: bytes, bundle: bytes, output_artifact: str, implementation: dict[str, Any]) -> dict[str, Any]:
    semantic_contract = {"semantic_instruction_vector_sha256": payload["cfg"]["semantic_instruction_vector_sha256"], "edge_vector_sha256": payload["cfg"]["edge_vector_sha256"], "literal_binding_vector_sha256": payload["literal_binding_vector_sha256"], "producer_form_vector_sha256": payload["producer_denominator"]["producer_form_vector_sha256"], "range_vector_sha256": RANGE_VECTOR_SHA256, "packed_bytes_sha256": PACKED_SHA256}
    command = ["python3", "tools/export_rom_mp2k_note_allocator.py"]
    if "coverage_baseline_source" in payload:
        command += ["--coverage-baseline-artifact", payload["coverage_baseline_source"]["artifact"]]
    command += ["--output", output_artifact]
    manifest = {
        "schema": PROMOTION_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": "candidate", "rom": payload["rom"], "coverage_baseline": payload["coverage_baseline"], "coverage_projection": payload["coverage_projection"], "upstream_receipts": payload["upstream_receipts"], "promotion": payload["promotion"], "promotion_ranges": payload["promotion_ranges"], "semantic_contract": semantic_contract, "producer_denominator": payload["producer_denominator"], "entry_pointer": payload["entry_pointer"], "excluded_ranges": payload["excluded_ranges"], "scope": payload["scope"], "limitations": payload["limitations"], "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}, BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)}}, "implementation": implementation, "producer": {"kind": "artifact-candidate-construction", "output_artifact": output_artifact, "command": command}, "verification": {"status": "pending", "report": None}, "summary": payload["summary"],
    }
    if "coverage_baseline_source" in payload:
        manifest["coverage_baseline_source"] = payload["coverage_baseline_source"]
    return manifest


def write_candidate(root: Path | str, output: Path | str = ARTIFACT_RELATIVE, *, coverage_baseline_artifact: Path | str | None = None) -> dict[str, Any]:
    repository = _validate_root(root)
    target = _validate_output(repository, output)
    payload, bundle = build_payload(repository, coverage_baseline_artifact=coverage_baseline_artifact)
    implementation = _implementation(repository)
    payload["implementation"] = implementation
    payload_raw = _canonical(payload)
    output_artifact = target.relative_to(repository).as_posix()
    manifest_raw = _canonical(_manifest(payload, payload_raw, bundle, output_artifact, implementation))
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        (staging / PAYLOAD_NAME).write_bytes(payload_raw)
        (staging / BUNDLE_NAME).write_bytes(bundle)
        (staging / MANIFEST_NAME).write_bytes(manifest_raw)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
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
