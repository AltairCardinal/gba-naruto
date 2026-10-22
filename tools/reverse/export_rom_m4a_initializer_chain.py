#!/usr/bin/env python3
"""Export the frozen m4a initializer-chain candidate packet.

The packet is deliberately target-limited: it proves three bounded Thumb
closures and their consumed literal pools.  The raw BL producers are retained
as provenance only; no producer bytes, RAM callback values, or literal targets
are promoted by this exporter.
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

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const


SCHEMA = "rom-m4a-initializer-chain-v1"
VERIFY_SCHEMA = "rom-m4a-initializer-chain-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
ROM_BASE = 0x08000000
ROM_SIZE = 0x600000
BASE_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
# Tests may replace this guard for a mutated in-memory ROM.  The frozen range
# hashes below remain immutable and therefore still fail closed.
ROM_SHA256 = BASE_ROM_SHA256
COVERAGE_SHA256 = "31cf4a9c14666345482cad325433814e7fe26d458327c3bc5d9a13e680616563"
COVERAGE_SUMMARY = {
    "classified_bytes": 6_123_419,
    "unknown_bytes": 168_037,
    "claim_count": 14_493,
    "segment_count": 16_600,
}
PROJECTED_COVERAGE_SUMMARY = {
    "classified_bytes": 6_123_937,
    "unknown_bytes": 167_519,
    "claim_count": 14_499,
    "segment_count": 16_608,
}
PRE_COVERAGE_ARTIFACT = Path(
    "artifacts/rom-m4a-initializer-chain-precoverage-v1"
)
PRE_COVERAGE_ARTIFACT_SCHEMA = "rom-byte-coverage-prepromotion-baseline-v1"
PRE_COVERAGE_MANIFEST_NAME = "manifest.json"
PRE_COVERAGE_ARCHIVE_NAME = "rom-byte-coverage.json.gz"
PRE_COVERAGE_MANIFEST_SIZE = 2_242
PRE_COVERAGE_MANIFEST_SHA256 = (
    "6d345594ab9278f5a098189328621af635ec17839f6ee7c5250b08bd7ed81baa"
)
PRE_COVERAGE_ARCHIVE_SIZE = 1_297_017
PRE_COVERAGE_ARCHIVE_SHA256 = (
    "9249601f241fd767ca9aa6ce583061c88686f9040ef93d6f9dab335e3cddbbac"
)
PRE_COVERAGE_RAW_SIZE = 23_097_532

PROMOTION_RANGES = [
    [0x09AA3C, 0x09AA90],
    [0x09AA90, 0x09AAB4],
    [0x09ACF8, 0x09ADC0],
    [0x09ADC0, 0x09AE10],
    [0x09B17C, 0x09B1E6],
    [0x09B1E8, 0x09B1F4],
]
PROMOTION_RANGE_SHA256 = [
    "c782ff96fc49708def45c12c5ba3c4170449390bf0ea4aa389561e09f359013b",
    "7f208987daf90cface78da36557a0773839b56b2bf1fe174358f1a56cfebbc6f",
    "b2c254e31eb7da12ddfd1a22a1fecb176659d1cc344e70cb8cad311230c84c9a",
    "5b0dd3fbbfc9f8c964f9c0f806548ccd9b72059ee6b67188c9432ac2342652b0",
    "b89251f7ae5e7e69702a82f4777b07d2a5ed1747b3aa8cfb8ea90bbfe0c7c733",
    "93fd80ddfc01693c7d0a9011380fb8fc6fe9c830809470f90cdacb2979bf0c46",
]
PACKED_SHA256 = "f5c0a94ac06bf6750edc038e0db95fc5d4e96c321129e57a11abd461aa678ea7"
RANGE_VECTOR_SHA256 = "8bcba07694e7375d59dddeb3cb12eeb4903e61147c91723482d61d06a47dbd72"
PROMOTION_UNION_RANGES = [
    [0x09AA3C, 0x09AAB4],
    [0x09ACF8, 0x09AE10],
    [0x09B17C, 0x09B1E6],
    [0x09B1E8, 0x09B1F4],
]
GAP_RANGE = [0x09B1E6, 0x09B1E8]
GAP_SHA256 = "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7"

CODE_RANGES = [PROMOTION_RANGES[0], PROMOTION_RANGES[2], PROMOTION_RANGES[4]]
LITERAL_RANGES = [PROMOTION_RANGES[1], PROMOTION_RANGES[3], PROMOTION_RANGES[5]]
ROOTS = [
    {"id": "m4aSoundInit", "file_offset": 0x09AA3C, "code_range": PROMOTION_RANGES[0]},
    {"id": "PSG initializer", "file_offset": 0x09ACF8, "code_range": PROMOTION_RANGES[2]},
    {"id": "MPlayOpen", "file_offset": 0x09B17C, "code_range": PROMOTION_RANGES[4]},
]
ROOT_BY_OFFSET = {item["file_offset"]: item for item in ROOTS}
RETURN_OFFSETS = {0x09AA3C: 0x09AA8E, 0x09ACF8: 0x09ADBE, 0x09B17C: 0x09B1E4}
EXPECTED_BLOCK_RANGES = {
    0x09AA3C: [
        [0x09AA3C, 0x09AA4E], [0x09AA4E, 0x09AA54], [0x09AA54, 0x09AA5A],
        [0x09AA5A, 0x09AA60], [0x09AA60, 0x09AA6A], [0x09AA6A, 0x09AA6E],
        [0x09AA6E, 0x09AA7A], [0x09AA7A, 0x09AA8A], [0x09AA8A, 0x09AA90],
    ],
    0x09ACF8: [
        [0x09ACF8, 0x09AD3A], [0x09AD3A, 0x09AD8A],
        [0x09AD8A, 0x09ADB8], [0x09ADB8, 0x09ADC0],
    ],
    0x09B17C: [
        [0x09B17C, 0x09B18A], [0x09B18A, 0x09B18E], [0x09B18E, 0x09B190],
        [0x09B190, 0x09B19C], [0x09B19C, 0x09B1A6], [0x09B1A6, 0x09B1B4],
        [0x09B1B4, 0x09B1B6], [0x09B1B6, 0x09B1C4], [0x09B1C4, 0x09B1CA],
        [0x09B1CA, 0x09B1D4], [0x09B1D4, 0x09B1E0], [0x09B1E0, 0x09B1E6],
    ],
}
ALLOWED_CALLS = {
    0x09AA3C: {
        0x09AA4A: (0x09C0E0, "opaque_call"),
        0x09AA50: (0x09AE3C, "opaque_call"),
        0x09AA56: (0x09ACF8, "included_root"),
        0x09AA5C: (0x09AFD8, "opaque_call"),
        0x09AA76: (0x09B17C, "included_root"),
    },
    0x09ACF8: {0x09AD86: (0x09C0E0, "opaque_call")},
    0x09B17C: {0x09B1A2: (0x09AE28, "opaque_call")},
}

LITERAL_EXPECTATIONS = [
    (0x09AA3E, 0x09AA90, 0x08099E11), (0x09AA46, 0x09AA94, 0x030077C8),
    (0x09AA48, 0x09AA98, 0x04000100), (0x09AA4E, 0x09AA9C, 0x03006570),
    (0x09AA54, 0x09AAA0, 0x030075B0), (0x09AA5A, 0x09AAA4, 0x0095FA00),
    (0x09AA60, 0x09AAA8, 0x00000004), (0x09AA6A, 0x09AAAC, 0x08465B40),
    (0x09AA7E, 0x09AAB0, 0x03007770),
    (0x09ACFE, 0x09ADC0, 0x04000084), (0x09AD04, 0x09ADC4, 0x04000080),
    (0x09AD0A, 0x09ADC8, 0x04000063), (0x09AD2E, 0x09ADCC, 0x03007FF0),
    (0x09AD34, 0x09ADD0, 0x68736D53), (0x09AD3E, 0x09ADD4, 0x03007520),
    (0x09AD40, 0x09ADD8, 0x0809BCB5), (0x09AD44, 0x09ADDC, 0x0809A971),
    (0x09AD48, 0x09ADE0, 0x0809A985), (0x09AD4C, 0x09ADE4, 0x0809BE0D),
    (0x09AD50, 0x09ADE8, 0x0809A909), (0x09AD54, 0x09ADEC, 0x0809AF35),
    (0x09AD58, 0x09ADF0, 0x0809A695), (0x09AD60, 0x09ADF4, 0x0809B319),
    (0x09AD66, 0x09ADF8, 0x0809B3E1), (0x09AD6C, 0x09ADFC, 0x0809B5F5),
    (0x09AD70, 0x09AE00, 0x0809B53D), (0x09AD74, 0x09AE04, 0x0809B495),
    (0x09AD78, 0x09AE08, 0x00000000), (0x09AD80, 0x09AE0C, 0x05000040),
    (0x09B190, 0x09B1E8, 0x03007FF0), (0x09B196, 0x09B1EC, 0x68736D53),
    (0x09B1D6, 0x09B1F0, 0x0809A42D), (0x09B1DA, 0x09B1EC, 0x68736D53),
]

UPSTREAM_PATHS = {
    "soundmain": {
        "manifest": Path("artifacts/rom-soundmain-relocated-cfg-v1/manifest.json"),
        "payload": Path("artifacts/rom-soundmain-relocated-cfg-v1/rom-soundmain-relocated-cfg.json"),
        "verifier": Path("tools/verify_rom_soundmain_relocated_cfg.py"),
    },
    "psg": {
        "manifest": Path("artifacts/rom-psg-frequency-lookup-v1/manifest.json"),
        "payload": Path("artifacts/rom-psg-frequency-lookup-v1/rom-psg-frequency-lookup.json"),
        "verifier": Path("tools/verify_rom_psg_frequency_lookup.py"),
    },
    "mplaymain": {
        "manifest": Path("artifacts/rom-mplaymain-scheduler-v1/manifest.json"),
        "payload": Path("artifacts/rom-mplaymain-scheduler-v1/rom-mplaymain-scheduler.json"),
        "verifier": Path("tools/verify_rom_mplaymain_scheduler.py"),
    },
}
UPSTREAM_RECEIPTS = {
    "soundmain": {
        "manifest_sha256": "e6b9a2cbdb439c520b5c98a422279e44e03866dbf1541810626d28eb57ce0a37",
        "payload_sha256": "63543ece1982ced20eb0818faf3b6f1848e72ba6dcdb68105fa8b2e3e07e477a",
        "verifier_sha256": "321d5ca5b7d6f887a21ec93c1bb06640f6e1397248273068bb5a13d3d7167d82",
    },
    "psg": {
        "manifest_sha256": "4fffbcc7e252595834adb368d10b3ce8f13323aee18cc518d98e0ff9c519575f",
        "payload_sha256": "d2631b1a65a2e9fa0114dbd76a4e2c89853e3b2f402a491fdbc466e79dacd733",
        "verifier_sha256": "c87ab33b067a35a0105e21967dc0caad5fe91368942f34baf91218d69258f616",
    },
    "mplaymain": {
        "manifest_sha256": "43399803451c393722522c9d2a363736541c34c37dd03d3cb2c1e292ed0b8f5d",
        "payload_sha256": "31bc026a8c83b3bf4af06746de2990a658bb86954a5aae31c45d63d68cf44f78",
        "verifier_sha256": "c064fc6a576a518cbd825630babc40d1c2dab2d369846078c3950b68748a2c2a",
    },
}
EXPECTED_UPSTREAM_RECEIPTS = json.loads(json.dumps(UPSTREAM_RECEIPTS))

PAYLOAD_NAME = "rom-m4a-initializer-chain.json"
BUNDLE_NAME = "rom-m4a-initializer-chain.bin"
MANIFEST_NAME = "manifest.json"
ARTIFACT_RELATIVE = Path("build/experiments/active/rom-m4a-initializer-chain-v1/luna-r1-20260828/candidate")

SCOPE = {
    "source_instruction_membership_complete": False,
    "producer_source_instruction_membership_proven": False,
    "producer_bytes_promoted": False,
    "dynamic_callback_values_proven": False,
    "global_ram_or_computed_producer_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_code_denominator_complete": False,
    "global_indirect_producer_denominator_complete": False,
    "natural_runtime_reachability_complete": False,
    "literal_pointer_target_semantics_claimed": False,
    "audio_behavior_proven": False,
    "editing_relocation_writeback_safe": False,
    "allocatable_free_space_proven": False,
}
LIMITATIONS = [
    "This candidate classifies exactly 390 bounded Thumb instruction bytes and 128 consumed literal bytes in three target-limited initializer roots.",
    "The three direct Thumb BL producer matches are raw provenance only; source instruction membership and producer bytes remain unpromoted.",
    "Dynamic callback/RAM values, natural runtime reachability, global caller/code/indirect/computed producer denominators, and literal target semantics remain unproven.",
    "The two bytes at 0x09B1E6..0x09B1E8 remain current unknown and are not padding, NOP, reserved, free, or allocatable space.",
    "Audio behavior, editing, writeback, relocation, and allocatable free-space safety are outside scope.",
]

_ENGINE: Cs | None = None


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
    return (
        "arm_bl" if word & (1 << 24) else "arm_b",
        offset + 8 + _sign_extend((word & 0x00FFFFFF) << 2, 26),
    )


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


def _validate_root(root: Path | str) -> Path:
    value = Path(root).expanduser().resolve(strict=True)
    if not value.is_dir():
        raise ValueError(f"repository root is not a directory: {value}")
    return value


def _safe_file(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository path: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    path = (root / relative).resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not path.is_file():
        raise ValueError(f"required file missing: {relative}")
    return path


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
    return _ENGINE


def _decode_one(rom: bytes, offset: int, end: int) -> Any:
    if offset & 1 or not (0 <= offset < end):
        raise ValueError(f"CFG decode offset invalid: 0x{offset:06X}")
    decoded = list(_engine().disasm(_bounded(rom, offset, min(end, offset + 4), "instruction"), ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset:
        raise ValueError(f"Thumb CFG decode failed at 0x{offset:06X}")
    instruction = decoded[0]
    if instruction.size not in (2, 4) or offset + instruction.size > end:
        raise ValueError(f"Thumb instruction escapes frozen range at 0x{offset:06X}")
    return instruction


def _direct_target(instruction: Any) -> int:
    if len(instruction.operands) != 1 or instruction.operands[0].type != arm_const.ARM_OP_IMM:
        raise ValueError("direct branch operand changed")
    return instruction.operands[0].imm - ROM_BASE


def _root_range(root_offset: int) -> tuple[int, int]:
    row = ROOT_BY_OFFSET[root_offset]
    return tuple(row["code_range"])


def _flow(rom: bytes, root_offset: int, offset: int, instruction: Any) -> tuple[str, list[tuple[str, int]], bool]:
    end = _root_range(root_offset)[1]
    next_offset = offset + instruction.size
    if instruction.id == arm_const.ARM_INS_B:
        target = _direct_target(instruction)
        successors = [("branch_target", target)]
        conditional = instruction.cc != arm_const.ARM_CC_AL
        if conditional:
            successors.append(("fallthrough", next_offset))
        return ("conditional_branch" if conditional else "unconditional_branch", successors, conditional)
    if instruction.id == arm_const.ARM_INS_BL:
        target = _direct_target(instruction)
        expected = ALLOWED_CALLS[root_offset].get(offset)
        if expected is None or expected[0] != target:
            raise ValueError(f"direct call denominator changed at 0x{offset:06X}")
        return "call", [("call_target", target), ("fallthrough", next_offset)], False
    if instruction.id == arm_const.ARM_INS_BX:
        if offset != RETURN_OFFSETS[root_offset] or instruction.op_str != "r0":
            raise ValueError(f"return/indirect branch changed at 0x{offset:06X}")
        return "return", [], False
    if next_offset >= end:
        raise ValueError(f"CFG falls out of frozen range at 0x{offset:06X}")
    return "linear", [("fallthrough", next_offset)], False


def _walk_root(rom: bytes, root_offset: int) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    start, end = _root_range(root_offset)
    pending = [start]
    seen: dict[int, dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in seen:
            continue
        if not (start <= offset < end) or offset & 1:
            raise ValueError(f"CFG branch escaped frozen range at 0x{offset:06X}")
        instruction = _decode_one(rom, offset, end)
        flow_kind, successors, conditional = _flow(rom, root_offset, offset, instruction)
        raw = _bounded(rom, offset, offset + instruction.size, "instruction")
        node = {
            "root": ROOT_BY_OFFSET[root_offset]["id"],
            "offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}",
            "mode": "thumb",
            "size": instruction.size,
            "raw_hex": raw.hex(),
            "bytes_sha256": _sha(raw),
            "mnemonic": instruction.mnemonic,
            "op_str": instruction.op_str,
            "flow_kind": flow_kind,
            "conditional": conditional,
            "successors": [],
        }
        for kind, target in successors:
            row = {"kind": kind, "target_offset": target, "target_mode": "thumb"}
            node["successors"].append(row)
            if kind == "call_target":
                expected_target, resolution = ALLOWED_CALLS[root_offset][offset]
                external.append({
                    "source_instruction_offset": offset,
                    "source_mode": "thumb",
                    "kind": kind,
                    "target_offset": target,
                    "target_mode": "thumb",
                    "resolution": resolution,
                    "target_root": ROOT_BY_OFFSET[target]["id"] if resolution == "included_root" else None,
                })
                continue
            if not (start <= target < end) or target & 1:
                raise ValueError(f"CFG branch escaped frozen range from 0x{offset:06X} to 0x{target:06X}")
            heapq.heappush(pending, target)
        seen[offset] = node

    owners: dict[int, int] = {}
    for offset, node in seen.items():
        for byte_offset in range(offset, offset + node["size"]):
            previous = owners.get(byte_offset)
            if previous is not None and previous != offset:
                raise ValueError("CFG target lands in an instruction middle")
            owners[byte_offset] = offset
    expected = set(range(start, end))
    if set(owners) != expected:
        raise ValueError(f"CFG code range is not closed for 0x{root_offset:06X}")
    if sum(node["size"] for node in seen.values()) != end - start:
        raise ValueError("CFG instruction byte denominator changed")
    return seen, external


def _build_blocks(rom: bytes, root_offset: int, nodes: dict[int, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predecessors: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for successor in node["successors"]:
            target = successor["target_offset"]
            if successor["kind"] != "call_target" and target in nodes:
                predecessors[target].append((source, successor["kind"]))
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
    for block_start in sorted(leaders):
        if block_start in block_by_offset:
            continue
        members: list[int] = []
        cursor = block_start
        while cursor in nodes and cursor not in block_by_offset:
            members.append(cursor)
            block_by_offset[cursor] = f"{ROOT_BY_OFFSET[root_offset]['id']}-block-{block_start:06x}"
            node = nodes[cursor]
            if len(node["successors"]) != 1 or node["flow_kind"] != "linear":
                break
            successor = node["successors"][0]
            target = successor["target_offset"]
            if successor["kind"] != "fallthrough" or target in leaders or target != cursor + node["size"]:
                break
            cursor = target
        end = members[-1] + nodes[members[-1]]["size"]
        blocks.append({
            "id": block_by_offset[block_start],
            "root": ROOT_BY_OFFSET[root_offset]["id"],
            "mode": "thumb",
            "range": [block_start, end],
            "runtime_range": [ROM_BASE + block_start, ROM_BASE + end],
            "instruction_count": len(members),
            "bytes_sha256": _sha(_bounded(rom, block_start, end, "block")),
            "terminator": nodes[members[-1]],
            "successors": [],
        })
    if len(block_by_offset) != len(nodes):
        raise ValueError("CFG block partition omitted instructions")
    edges: list[dict[str, Any]] = []
    by_id = {block["id"]: block for block in blocks}
    for block in blocks:
        terminator = block["terminator"]
        for successor in terminator["successors"]:
            target = successor["target_offset"]
            if successor["kind"] == "call_target":
                continue
            edge = {
                "source_block_id": block["id"],
                "source_instruction_offset": terminator["offset"],
                "source_mode": "thumb",
                "kind": successor["kind"],
                "target_offset": target,
                "target_mode": "thumb",
            }
            if target not in block_by_offset:
                raise ValueError("CFG internal edge escaped block partition")
            edge["target_block_id"] = block_by_offset[target]
            edge["resolution"] = "internal"
            block["successors"].append(edge)
            edges.append(edge)
    expected_ranges = EXPECTED_BLOCK_RANGES[root_offset]
    if [block["range"] for block in blocks] != expected_ranges:
        raise ValueError(f"CFG block denominator changed for 0x{root_offset:06X}")
    return blocks, edges


def _semantic_instruction_vector(instructions: list[dict[str, Any]]) -> list[list[Any]]:
    return [[row["offset"], row["size"], row["mnemonic"], row["op_str"]] for row in instructions]


def _literal_bindings(rom: bytes, instructions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actual: list[tuple[int, int, int]] = []
    for node in instructions:
        if node["size"] != 2 or node["mnemonic"] != "ldr":
            continue
        halfword = _u16(rom, node["offset"])
        if halfword & 0xF800 != 0x4800:
            continue
        literal = ((node["offset"] + 4) & ~3) + (halfword & 0xFF) * 4
        value = _u32(rom, literal)
        actual.append((node["offset"], literal, value))
    if actual != LITERAL_EXPECTATIONS:
        raise ValueError("literal binding denominator changed")
    rows: list[dict[str, Any]] = []
    for load_offset, literal_offset, value in actual:
        pool = next((rng for rng in LITERAL_RANGES if rng[0] <= literal_offset < rng[1]), None)
        if pool is None or literal_offset + 4 > pool[1]:
            raise ValueError(f"LDR literal escapes frozen pool at 0x{load_offset:06X}")
        raw = _bounded(rom, literal_offset, literal_offset + 4, "literal word")
        rows.append({
            "instruction_offset": load_offset,
            "instruction_mode": "thumb",
            "load_raw_hex": _bounded(rom, load_offset, load_offset + 2, "LDR").hex(),
            "literal_offset": literal_offset,
            "literal_range": [literal_offset, literal_offset + 4],
            "value": f"0x{value:08X}",
            "raw_hex": raw.hex(),
        })
    covered: set[int] = set()
    for row in rows:
        covered.update(range(row["literal_range"][0], row["literal_range"][1]))
    for start, end in LITERAL_RANGES:
        if covered.intersection(range(start, end)) != set(range(start, end)):
            raise ValueError("literal pool hole or unconsumed byte changed")
    return rows


def _scan_producer_forms(rom: bytes) -> dict[int, dict[str, list[int]]]:
    targets = tuple(item["file_offset"] for item in ROOTS)
    forms = {
        target: {
            "thumb_bl": [], "thumb_b": [], "thumb_b_conditional": [],
            "arm_b": [], "arm_bl": [], "bytewise_u32_entry": [],
            "bytewise_u32_thumb_pointer": [],
        }
        for target in targets
    }
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
    for target in targets:
        forms[target]["bytewise_u32_entry"] = _pointer_occurrences(rom, ROM_BASE + target)
        forms[target]["bytewise_u32_thumb_pointer"] = _pointer_occurrences(rom, ROM_BASE + target + 1)
        for values in forms[target].values():
            values.sort()
    return forms


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    expected = {
        0x09AA3C: [0x061E28], 0x09ACF8: [0x09AA56], 0x09B17C: [0x09AA76]
    }
    forms = _scan_producer_forms(rom)
    for target, target_forms in forms.items():
        if target_forms["thumb_bl"] != expected[target]:
            raise ValueError("target Thumb BL producer denominator changed")
        if any(target_forms[name] for name in target_forms if name != "thumb_bl"):
            raise ValueError("target producer form denominator changed")
    vector = [
        {"target_file_offset": target, "forms": forms[target]}
        for target in (0x09AA3C, 0x09ACF8, 0x09B17C)
    ]
    return {
        "scan": {"mode": "raw-rom", "alignment_bytes": 2, "range": [0, ROM_SIZE]},
        "thumb_bl": [0x061E28, 0x09AA56, 0x09AA76],
        "root_forms": {f"0x{target:06X}": forms[target] for target in expected},
        "producer_form_vector": vector,
        "producer_form_vector_sha256": _sha(_canonical(vector)),
        "all_non_thumb_bl_forms_empty": True,
        "producer_source_instruction_membership_proven": False,
        "producer_bytes_promoted": False,
        "target_limited_raw_producer_denominator_complete": True,
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
        raw_range = segment.get("range") if isinstance(segment, dict) else None
        if not isinstance(raw_range, list) or len(raw_range) != 2 or not all(isinstance(v, int) for v in raw_range):
            raise ValueError("coverage baseline has invalid segment range")
        normalized.append((raw_range[0], raw_range[1], segment))
    normalized.sort()
    target_segments: list[dict[str, Any]] = []
    unknown_bytes = 0
    overlap_bytes = 0
    for promotion_start, promotion_end in PROMOTION_RANGES:
        cursor = promotion_start
        for segment_start, segment_end, segment in normalized:
            if segment_end <= promotion_start:
                continue
            if segment_start >= promotion_end:
                break
            left, right = max(cursor, segment_start), min(promotion_end, segment_end)
            if left != cursor or right <= left:
                raise ValueError("coverage baseline has a partial owner or gap inside promotion range")
            unknown = segment.get("primary_class") == "unknown" and segment.get("primary_claim_ids") in (None, [])
            if unknown:
                unknown_bytes += right - left
            else:
                overlap_bytes += right - left
            target_segments.append({
                "range": [left, right],
                "primary_class": "unknown" if unknown else segment.get("primary_class"),
                "primary_claim_ids": [] if unknown else segment.get("primary_claim_ids"),
            })
            cursor = right
        if cursor != promotion_end:
            raise ValueError("coverage baseline does not cover a promotion range")
    if unknown_bytes != 518 or overlap_bytes != 0:
        raise ValueError("coverage baseline promotion ranges are not whole-range unknown")
    return {
        "path": COVERAGE_PATH.as_posix(),
        "schema": "rom-byte-coverage-v1",
        "sha256": COVERAGE_SHA256,
        "summary": dict(COVERAGE_SUMMARY),
        "promotion_bytes": 518,
        "unknown_promotion_bytes": unknown_bytes,
        "primary_overlap_bytes": overlap_bytes,
        "all_promotion_bytes_unknown": True,
        "target_segments": target_segments,
    }


def _coverage_baseline(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    try:
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("coverage baseline is not valid JSON") from error
    return analyze_coverage_baseline(coverage)


def _coverage_baseline_from_artifact(
    root: Path, artifact: Path | str
) -> tuple[dict[str, Any], dict[str, Any]]:
    requested = Path(artifact).expanduser()
    if requested.is_absolute():
        try:
            relative = requested.resolve(strict=True).relative_to(root)
        except ValueError as error:
            raise ValueError("coverage baseline artifact escapes repository root") from error
    else:
        relative = requested
    if relative != PRE_COVERAGE_ARTIFACT:
        raise ValueError("coverage baseline artifact identity changed")

    manifest_path = _safe_file(root, relative / PRE_COVERAGE_MANIFEST_NAME)
    archive_path = _safe_file(root, relative / PRE_COVERAGE_ARCHIVE_NAME)
    manifest_raw = manifest_path.read_bytes()
    archive_raw = archive_path.read_bytes()
    if (
        len(manifest_raw) != PRE_COVERAGE_MANIFEST_SIZE
        or _sha(manifest_raw) != PRE_COVERAGE_MANIFEST_SHA256
    ):
        raise ValueError("coverage baseline artifact manifest identity changed")
    if (
        len(archive_raw) != PRE_COVERAGE_ARCHIVE_SIZE
        or _sha(archive_raw) != PRE_COVERAGE_ARCHIVE_SHA256
    ):
        raise ValueError("coverage baseline artifact archive identity changed")
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        raw = gzip.decompress(archive_raw)
        coverage = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, OSError) as error:
        raise ValueError("coverage baseline artifact is invalid") from error
    if _canonical(manifest) != manifest_raw:
        raise ValueError("coverage baseline artifact manifest is not canonical JSON")
    if _canonical(coverage) != raw:
        raise ValueError("coverage baseline artifact raw JSON is not canonical")
    if (
        manifest.get("schema") != PRE_COVERAGE_ARTIFACT_SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or manifest.get("coverage", {}).get("raw")
        != {
            "canonical_json": True,
            "schema": "rom-byte-coverage-v1",
            "sha256": COVERAGE_SHA256,
            "size": PRE_COVERAGE_RAW_SIZE,
            "summary": dict(COVERAGE_SUMMARY),
        }
        or manifest.get("coverage", {}).get("archive")
        != {
            "compression": "gzip",
            "file": PRE_COVERAGE_ARCHIVE_NAME,
            "sha256": PRE_COVERAGE_ARCHIVE_SHA256,
            "size": PRE_COVERAGE_ARCHIVE_SIZE,
        }
        or manifest.get("recovery", {}).get("kind")
        != "byte-identical-inverse-promotion-projection"
    ):
        raise ValueError("coverage baseline artifact contract changed")
    if len(raw) != PRE_COVERAGE_RAW_SIZE or _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline artifact raw identity changed")
    baseline = analyze_coverage_baseline(coverage)
    source = {
        "kind": "immutable-gzip-artifact",
        "artifact": relative.as_posix(),
        "manifest_sha256": PRE_COVERAGE_MANIFEST_SHA256,
        "archive_file": PRE_COVERAGE_ARCHIVE_NAME,
        "archive_size": PRE_COVERAGE_ARCHIVE_SIZE,
        "archive_sha256": PRE_COVERAGE_ARCHIVE_SHA256,
        "raw_size": PRE_COVERAGE_RAW_SIZE,
        "raw_sha256": COVERAGE_SHA256,
        "recovery_kind": "byte-identical-inverse-promotion-projection",
    }
    return baseline, source


def _validate_upstream_receipts(root: Path) -> None:
    if UPSTREAM_RECEIPTS != EXPECTED_UPSTREAM_RECEIPTS:
        raise ValueError("upstream receipt contract changed")
    for name, paths in UPSTREAM_PATHS.items():
        expected = EXPECTED_UPSTREAM_RECEIPTS[name]
        for role, path in paths.items():
            raw = _safe_file(root, path).read_bytes()
            actual = _sha(raw)
            expected_hash = expected[f"{role}_sha256"]
            if actual != expected_hash:
                raise ValueError(f"upstream {name} {role} receipt changed")
            if role == "manifest":
                try:
                    manifest = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValueError(f"upstream {name} manifest is not JSON") from error
                if manifest.get("artifact_status") != "accepted":
                    raise ValueError(f"upstream {name} artifact is not accepted")


def _promotion_rows(rom: bytes) -> list[dict[str, Any]]:
    specs = [
        ("m4a-sound-init-code-09aa3c", "bounded_thumb_code", "thumb"),
        ("m4a-sound-init-literals-09aa90", "consumed_literals", None),
        ("psg-initializer-code-09acf8", "bounded_thumb_code", "thumb"),
        ("psg-initializer-literals-09adc0", "consumed_literals", None),
        ("mplay-open-code-09b17c", "bounded_thumb_code", "thumb"),
        ("mplay-open-literals-09b1e8", "consumed_literals", None),
    ]
    rows: list[dict[str, Any]] = []
    for index, (row_id, kind, mode) in enumerate(specs):
        start, end = PROMOTION_RANGES[index]
        raw = _bounded(rom, start, end, "promotion")
        if len(raw) != end - start or _sha(raw) != PROMOTION_RANGE_SHA256[index]:
            raise ValueError(f"promotion range bytes changed: {row_id}")
        rows.append({
            "id": row_id,
            "kind": kind,
            "range": [start, end],
            "size": end - start,
            "sha256": PROMOTION_RANGE_SHA256[index],
            "mode": mode,
            "semantic_class": "armv4t_m4a_initializer_chain_thumb_code" if mode else "m4a_initializer_chain_consumed_literal_bytes",
            "claim_kind": "m4a_initializer_chain_bounded_thumb_code" if mode else "m4a_initializer_chain_consumed_literal_bytes",
        })
    return rows


def _analyze_cfg(rom: bytes) -> dict[str, Any]:
    all_nodes: list[dict[str, Any]] = []
    all_blocks: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    external: list[dict[str, Any]] = []
    for root in ROOTS:
        nodes, calls = _walk_root(rom, root["file_offset"])
        blocks, edges = _build_blocks(rom, root["file_offset"], nodes)
        all_nodes.extend(nodes[offset] for offset in sorted(nodes))
        all_blocks.extend(blocks)
        all_edges.extend(edges)
        external.extend(calls)
    all_nodes.sort(key=lambda row: row["offset"])
    all_blocks.sort(key=lambda row: row["range"][0])
    all_edges.sort(key=lambda row: (row["source_instruction_offset"], row["kind"], row["target_offset"]))
    external.sort(key=lambda row: row["source_instruction_offset"])
    if len(all_nodes) != 188 or sum(row["size"] for row in all_nodes) != 390:
        raise ValueError("CFG instruction denominator changed")
    if len(all_blocks) != 25 or len(all_edges) != 31 or len(external) != 7:
        raise ValueError("CFG block/edge denominator changed")
    returns = [row for row in all_nodes if row["flow_kind"] == "return"]
    if len(returns) != 3:
        raise ValueError("structured return denominator changed")
    semantic_vector = _semantic_instruction_vector(all_nodes)
    edge_vector = [
        [row["source_instruction_offset"], row["kind"], row["target_offset"]]
        for row in all_edges
    ]
    return {
        "roots": [
            {"id": row["id"], "file_offset": row["file_offset"], "gba_address": f"0x{ROM_BASE + row['file_offset']:08X}", "mode": "thumb", "code_range": list(row["code_range"])}
            for row in ROOTS
        ],
        "code_ranges": [list(row) for row in CODE_RANGES],
        "instructions": all_nodes,
        "blocks": all_blocks,
        "block_edges": all_edges,
        "external_edges": external,
        "semantic_instruction_vector": semantic_vector,
        "semantic_instruction_vector_sha256": _sha(_canonical(semantic_vector)),
        "edge_vector_sha256": _sha(_canonical(edge_vector)),
        "summary": {
            "instruction_count": len(all_nodes),
            "instruction_bytes": sum(row["size"] for row in all_nodes),
            "code_bytes": sum(end - start for start, end in CODE_RANGES),
            "block_count": len(all_blocks),
            "internal_edge_count": len(all_edges),
            "internal_block_edge_count": len(all_edges),
            "external_edge_count": len(external),
            "direct_call_count": len(external),
            "structured_return_count": len(returns),
            "frontier_count": 0,
            "unresolved_frontier_count": 0,
        },
    }


def build_payload_from_rom(
    root: Path | str,
    rom: bytes,
    *,
    coverage_baseline_artifact: Path | str | None = None,
) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    data = bytes(rom)
    _validate_rom(data)
    _validate_upstream_receipts(repository)
    if coverage_baseline_artifact is None:
        coverage = _coverage_baseline(repository)
        coverage_source = None
    else:
        coverage, coverage_source = _coverage_baseline_from_artifact(
            repository, coverage_baseline_artifact
        )
    rows = _promotion_rows(data)
    gap_raw = _bounded(data, *GAP_RANGE, "unknown gap")
    if _sha(gap_raw) != GAP_SHA256 or gap_raw != b"\x00\x00":
        raise ValueError("MPlayOpen return-to-pool gap changed")
    cfg = _analyze_cfg(data)
    literals = _literal_bindings(data, cfg["instructions"])
    producer = _producer_denominator(data)
    bundle = b"".join(_bounded(data, start, end, "promotion") for start, end in PROMOTION_RANGES)
    if len(bundle) != 518 or _sha(bundle) != PACKED_SHA256:
        raise ValueError("promotion packed bytes changed")
    if _sha(_compact(PROMOTION_UNION_RANGES)) != RANGE_VECTOR_SHA256:
        raise ValueError("promotion range vector receipt changed")
    post = {
        "classified_bytes": coverage["summary"]["classified_bytes"] + 518,
        "unknown_bytes": coverage["summary"]["unknown_bytes"] - 518,
        "claim_count": coverage["summary"]["claim_count"] + 6,
        "segment_count": coverage["summary"]["segment_count"] + 8,
    }
    if post != PROJECTED_COVERAGE_SUMMARY:
        raise ValueError("coverage post projection changed")
    literal_vector = [[row["instruction_offset"], row["literal_offset"], row["value"]] for row in literals]
    claims = [
        {
            **row,
            "role": "primary",
            "promotion_batch": SCHEMA,
            "promoted_from_primary_class": "unknown",
            "non_claims": dict(SCOPE),
            "limitations": list(LIMITATIONS),
        }
        for row in rows
    ]
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(data), "sha256": BASE_ROM_SHA256},
        "coverage_baseline": coverage,
        "coverage_projection": {
            "pre": dict(coverage["summary"]),
            "post": post,
            "classified_delta": 518,
            "unknown_delta": -518,
            "claim_delta": 6,
            "segment_delta": 8,
        },
        "upstream_receipts": json.loads(json.dumps(UPSTREAM_RECEIPTS)),
        "roots": cfg["roots"],
        "cfg": cfg,
        "code_ranges": [list(row) for row in CODE_RANGES],
        "literal_ranges": [list(row) for row in LITERAL_RANGES],
        "unclassified_unknown_ranges": [list(GAP_RANGE)],
        "promotion_ranges": rows,
        "coverage_claims": claims,
        "literal_bindings": literals,
        "literal_binding_vector": literal_vector,
        "literal_binding_vector_sha256": _sha(_canonical(literal_vector)),
        "producer_denominator": producer,
        "gap_exclusion": {
            "ranges": [list(GAP_RANGE)], "bytes": 2, "sha256": GAP_SHA256,
            "promotion_excluded": True, "semantic_label": "unknown",
        },
        "promotion": {
            "ranges": [list(row) for row in PROMOTION_RANGES],
            "union_ranges": [list(row) for row in PROMOTION_UNION_RANGES],
            "union_range_count": len(PROMOTION_UNION_RANGES),
            "union_bytes": 518,
            "range_count": 6,
            "byte_count": 518,
            "range_sha256": list(PROMOTION_RANGE_SHA256),
            "range_vector_sha256": RANGE_VECTOR_SHA256,
            "packed_bytes_sha256": PACKED_SHA256,
            "code_bytes": 390,
            "literal_bytes": 128,
        },
        "packed_layout": [
            {"range": list(row["range"]), "kind": row["kind"], "bundle_offset": sum(item["size"] for item in rows[:index]), "size": row["size"], "sha256": row["sha256"]}
            for index, row in enumerate(rows)
        ],
        "packed_binary": {"file": BUNDLE_NAME, "size": len(bundle), "sha256": _sha(bundle)},
        "scope": dict(SCOPE),
        "limitations": list(LIMITATIONS),
        "summary": {
            **cfg["summary"],
            "literal_ref_count": len(literals),
            "literal_word_count": len({row["literal_offset"] for row in literals}),
            "literal_bytes": sum(end - start for start, end in LITERAL_RANGES),
            "promoted_bytes": len(bundle),
            "promotion_claim_count": len(claims),
            "promotion_range_count": len(rows),
            "producer_count": len(producer["thumb_bl"]),
            "gap_exclusion_bytes": 2,
        },
    }
    if coverage_source is not None:
        payload["coverage_baseline_source"] = coverage_source
    return payload, bundle


def build_payload(
    root: Path | str,
    *,
    coverage_baseline_artifact: Path | str | None = None,
) -> tuple[dict[str, Any], bytes]:
    repository = _validate_root(root)
    return build_payload_from_rom(
        repository,
        _safe_file(repository, ROM_PATH).read_bytes(),
        coverage_baseline_artifact=coverage_baseline_artifact,
    )


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path.expanduser()))
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"output path uses a symlink: {cursor}")


def _validate_output(root: Path, output: Path | str) -> Path:
    target = Path(output).expanduser()
    if not target.is_absolute():
        target = root / target
    _reject_symlink_components(target)
    target = target.resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ValueError("output must stay inside repository root") from error
    if target == root:
        raise ValueError("output must not be repository root")
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise ValueError("output must be a new directory")
        if any(target.iterdir()):
            raise ValueError("output directory must be empty")
    return target


def _implementation(root: Path) -> dict[str, dict[str, Any]]:
    paths = {
        "exporter": Path("tools/export_rom_m4a_initializer_chain.py"),
        "verifier": Path("tools/verify_rom_m4a_initializer_chain.py"),
        "exporter_test": Path("tests/test_export_rom_m4a_initializer_chain.py"),
        "verifier_test": Path("tests/test_verify_rom_m4a_initializer_chain.py"),
    }
    return {role: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in paths.items()}


def _manifest(payload: dict[str, Any], payload_raw: bytes, bundle: bytes, output_artifact: str, implementation: dict[str, Any]) -> dict[str, Any]:
    semantic_contract = {
        "semantic_instruction_vector_sha256": payload["cfg"]["semantic_instruction_vector_sha256"],
        "edge_vector_sha256": payload["cfg"]["edge_vector_sha256"],
        "literal_binding_vector_sha256": payload["literal_binding_vector_sha256"],
        "producer_form_vector_sha256": payload["producer_denominator"]["producer_form_vector_sha256"],
        "range_vector_sha256": payload["promotion"]["range_vector_sha256"],
        "packed_bytes_sha256": payload["promotion"]["packed_bytes_sha256"],
    }
    producer_command = [
        "python3",
        "tools/export_rom_m4a_initializer_chain.py",
    ]
    if "coverage_baseline_source" in payload:
        producer_command += [
            "--coverage-baseline-artifact",
            payload["coverage_baseline_source"]["artifact"],
        ]
    producer_command += ["--output", output_artifact]
    manifest = {
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
        "producer_denominator": payload["producer_denominator"],
        "gap_exclusion": payload["gap_exclusion"],
        "scope": payload["scope"],
        "limitations": payload["limitations"],
        "files": {
            PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
            BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)},
        },
        "implementation": implementation,
        "producer": {
            "kind": "artifact-candidate-construction",
            "output_artifact": output_artifact,
            "command": producer_command,
        },
        "verification": {"status": "pending", "report": None},
        "summary": payload["summary"],
    }
    if "coverage_baseline_source" in payload:
        manifest["coverage_baseline_source"] = payload[
            "coverage_baseline_source"
        ]
    return manifest


def write_candidate(
    root: Path | str,
    output: Path | str = ARTIFACT_RELATIVE,
    *,
    coverage_baseline_artifact: Path | str | None = None,
) -> dict[str, Any]:
    repository = _validate_root(root)
    target = _validate_output(repository, output)
    payload, bundle = build_payload(
        repository,
        coverage_baseline_artifact=coverage_baseline_artifact,
    )
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
        if target.exists():
            target.rmdir()
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
        result = write_candidate(
            args.root,
            args.output,
            coverage_baseline_artifact=args.coverage_baseline_artifact,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"schema": SCHEMA, "verified": False, "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
