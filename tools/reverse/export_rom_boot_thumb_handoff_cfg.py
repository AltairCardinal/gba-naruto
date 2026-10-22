#!/usr/bin/env python3
"""Export the frozen, target-limited Thumb CFG rooted at the ARM handoff."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import capstone
from capstone import CS_AC_WRITE, CS_ARCH_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const


SCHEMA = "rom-boot-thumb-handoff-cfg-v1"
VERIFY_SCHEMA = "rom-boot-thumb-handoff-cfg-verification-v1"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
ROM_PATH = Path("rom/base.gba")
COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
BOOT_MANIFEST_PATH = Path("artifacts/rom-boot-framebuffers-v1/manifest.json")
CFG_V2_MANIFEST_PATH = Path("artifacts/rom-cfg-inventory-v2/manifest.json")
CFG_V2_PAYLOAD_PATH = Path("artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json")
CFG_SEEDS_PAYLOAD_PATH = Path("artifacts/rom-cfg-seeds-v1/rom-cfg-seeds.json")
BOOT_INTERWORK_MANIFEST_PATH = Path("artifacts/rom-boot-interwork-v1/manifest.json")
BOOT_INTERWORK_PAYLOAD_PATH = Path("artifacts/rom-boot-interwork-v1/rom-boot-interwork.json")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
COVERAGE_SHA256 = "4ea0496a0754d0391ae4f48e16f941d9a2241c9cc730bdf38799abde85181cbd"
BOOT_MANIFEST_SHA256 = "ede3fa29106e8b67cc40e37746b5a44b85beddeb2750e660d5955e26d946238d"
CFG_V2_MANIFEST_SHA256 = "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"
CFG_V2_PAYLOAD_SHA256 = "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
CFG_SEEDS_PAYLOAD_SHA256 = "53960ae8e460b862bbc52d447290d988ed8a496417ccf08a810041384df1b05c"
BOOT_INTERWORK_MANIFEST_SHA256 = "f2673837955194f35daab4f9fb7c0b2fe2dd5967231fcd6d982d0cacb9f749be"
BOOT_INTERWORK_PAYLOAD_SHA256 = "2f78132647235ca1c9fd155b950ff4128e4b01ca10d0fa0ae0fcfa4fdd37e30d"

PAYLOAD_NAME = "rom-boot-thumb-handoff-cfg.json"
BUNDLE_NAME = "rom-boot-thumb-handoff-cfg.bin"
MANIFEST_NAME = "manifest.json"
EXPECTED_FILES = {PAYLOAD_NAME, BUNDLE_NAME, MANIFEST_NAME}
EXPERIMENT_ROOT = Path("build/experiments/active/boot-thumb-handoff-cfg-v1/sol-r2-20260827")

HANDOFF_RANGE = (0xE4, 0xF0)
HANDOFF_SHA256 = "5e5a9cf5b4745dc069b58a957c7b68fe64b5aae8d528caa62fdba38f594c80ea"
HANDOFF_LITERAL = 0xF8
HANDOFF_LITERAL_RAW = "ad0f0608"
HANDOFF_POINTER = 0x08060FAD
ROOT_OFFSET = 0x060FAC
ROOT_RAW = "30b581b0"
ROOT_SHA256 = "766eede2e5578d16c3e11a092a16dd98e3716bb825b6e8009ca68c37cef8471b"
EXCLUDED_PREFIX = (0x060FA4, 0x060FAC)
EXCLUDED_PREFIX_SHA256 = "ff3c2f49e8e01470390987ec0e7978068910c45f3ea0f020c1bb0c5f588e553f"

NEW_ENTRY = 0x061624
NEW_ENTRY_RAW = "30b5"
NEW_ENTRY_SHA256 = "0179fa50db01a670ea0d378b606928ed6b7a1f590c3fe52fcfe05a1936a84414"
NEW_CALLSITE = 0x060FE0
NEW_CALLSITE_RAW = "00f020fb"
NEW_CALLSITE_SHA256 = "863c2fdd72169166dddf0538761736276d44edd62cad291bd254410f0d545ddf"
NEW_OWNER_ID = "consumer-code-battle_effect_sprite_animations-061624"
NEW_OWNER_RANGE = (0x061624, 0x061710)
NEW_OWNER_CLASS = "consumer_code_slice"

EXISTING_ENTRY_SPECS = {
    0x061086: {
        "claim_id": "boot-interwork-thumb-direct-caller",
        "range": [0x061086, 0x06108A],
        "class": "boot_interwork_thumb_code",
        "kind": "boot_interwork",
    },
    0x064700: {
        "claim_id": "cfg-thumb-0025-064700",
        "range": [0x064700, 0x06474C],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
    },
    0x064A48: {
        "claim_id": "cfg-thumb-0040-064a48",
        "range": [0x064A48, 0x064A5C],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
    },
    0x064C68: {
        "claim_id": "cfg-thumb-0041-064c68",
        "range": [0x064C68, 0x064C9A],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
    },
    0x065384: {
        "claim_id": "cfg-thumb-0052-065384",
        "range": [0x065384, 0x065390],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
    },
    0x061D7C: {
        "claim_id": "cfg-thumb-0000-061d7c",
        "range": [0x061D7C, 0x061DEA],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
    },
    0x09B0C4: {
        "claim_id": "cfg-thumb-0764-09b0c4",
        "range": [0x09B0C4, 0x09B122],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
    },
    0x09B140: {
        "claim_id": "cfg-thumb-0765-09b140",
        "range": [0x09B140, 0x09B16E],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
    },
    0x09C0E0: {
        "claim_id": "cfg-thumb-0773-09c0d8",
        "range": [0x09C0D8, 0x09C0F4],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
        "interior_entry": True,
    },
    0x09C110: {
        "claim_id": "cfg-thumb-0774-09c110",
        "range": [0x09C110, 0x09C112],
        "class": "armv4t_cfg_reachable_thumb_code",
        "kind": "cfg_v2",
    },
}
EXISTING_ENTRY_OFFSETS = frozenset(EXISTING_ENTRY_SPECS)
OPAQUE_ENTRY_OFFSETS = EXISTING_ENTRY_OFFSETS | {NEW_ENTRY}

EXPECTED_SUMMARY = {
    "instruction_count": 583,
    "instruction_bytes": 1226,
    "block_count": 125,
    "internal_edge_count": 164,
    "external_edge_count": 14,
    "external_target_count": 11,
    "literal_ref_count": 77,
    "literal_word_count": 74,
    "literal_bytes": 296,
    "return_count": 14,
    "raw_indirect_pc_count": 15,
    "frontier_count": 2,
    "budget_exhausted": False,
}

CODE_RANGES = [
    [0x060FAC, 0x061022], [0x061050, 0x06107C], [0x061080, 0x061086],
    [0x0610E8, 0x0610FE], [0x061104, 0x06111E], [0x061124, 0x06114A],
    [0x0615E4, 0x061614], [0x061824, 0x06185E], [0x061878, 0x06188A],
    [0x061F74, 0x061F8A], [0x061F90, 0x061FA2], [0x0620B4, 0x0620C6],
    [0x06211C, 0x062138], [0x062140, 0x0621B8], [0x0621D0, 0x0621F8],
    [0x0621FC, 0x062276], [0x062280, 0x06231E], [0x0646D0, 0x0646EC],
    [0x065398, 0x0653C4], [0x0653D8, 0x0653E0], [0x0653E4, 0x0653F8],
    [0x099D8C, 0x099DF6], [0x09A1AE, 0x09A1B0], [0x09AAB4, 0x09AABE],
    [0x09BFFC, 0x09C010], [0x09C01C, 0x09C046], [0x09C05C, 0x09C086],
]
LITERAL_RANGES = [
    [0x061024, 0x061050], [0x06107C, 0x061080], [0x061100, 0x061104],
    [0x061120, 0x061124], [0x06114C, 0x061150], [0x061614, 0x061624],
    [0x061860, 0x061878], [0x061F8C, 0x061F90], [0x0620C8, 0x0620CC],
    [0x062138, 0x062140], [0x0621B8, 0x0621D0], [0x0621F8, 0x0621FC],
    [0x062278, 0x062280], [0x062320, 0x062330], [0x0646EC, 0x064700],
    [0x0653C4, 0x0653D8], [0x0653E0, 0x0653E4], [0x0653F8, 0x065404],
    [0x099DF8, 0x099E10], [0x09C010, 0x09C01C], [0x09C048, 0x09C05C],
    [0x09C088, 0x09C098],
]
UNION_RANGES = [
    [0x060FAC, 0x061022], [0x061024, 0x061086],
    [0x0610E8, 0x0610FE], [0x061100, 0x06111E], [0x061120, 0x06114A], [0x06114C, 0x061150],
    [0x0615E4, 0x061624], [0x061824, 0x06185E], [0x061860, 0x06188A],
    [0x061F74, 0x061F8A], [0x061F8C, 0x061FA2], [0x0620B4, 0x0620C6], [0x0620C8, 0x0620CC],
    [0x06211C, 0x062276], [0x062278, 0x06231E], [0x062320, 0x062330], [0x0646D0, 0x064700],
    [0x065398, 0x065404], [0x099D8C, 0x099DF6], [0x099DF8, 0x099E10],
    [0x09A1AE, 0x09A1B0], [0x09AAB4, 0x09AABE], [0x09BFFC, 0x09C046],
    [0x09C048, 0x09C086], [0x09C088, 0x09C098],
]
UNION_BYTES_SHA256 = "73033e06942ec6604fe036849e40c420728f6f9bd4ae5db6c0fe49ba6eca2f22"
UNION_RANGE_SHA256 = "f8df15ea8c3feb1a9c460bd0a2aabd79572806100ed726ada64b360aabb92aa5"

SCOPE = {
    "arm_startup_handoff_rebuilt_from_raw_rom": True,
    "target_limited_thumb_cfg_complete": True,
    "existing_exact_entries_opaque": True,
    "new_61624_entry_proven_without_scheduling": True,
    "current_unknown_only_promotion": True,
    "code_and_literal_ranges_kept_separate": True,
    "runtime_reachability_complete": False,
    "natural_execution_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "dynamic_callback_targets_resolved": False,
    "iwram_contents_or_loader_classified": False,
    "callee_abi_or_semantics_proven": False,
    "owner_061624_full_range_is_code": False,
    "envelope_gaps_classified": False,
    "editing_relocation_writeback_safe": False,
    "allocatable_free_space_proven": False,
}
LIMITATIONS = [
    "This is a target-limited static Thumb worklist rooted by a raw ARM startup handoff; it does not prove complete boot runtime or natural execution.",
    "Direct calls to ten independently proven exact entries and the newly proven 0x61624 entry are opaque and are not scheduled into this packet.",
    "The 0x61624..0x61710 consumer owner is not instruction-only; only its exact entry is proven here.",
    "Indirect PC sites remain unresolved except for the exact same-register pop/BX return idiom; dynamic callback targets and IWRAM contents are not classified.",
    "The wide 0x60FAC..0x9C098 envelope, gaps, neighbouring bytes, edit/relocation safety, and allocatable space are not claims.",
]

_ENGINES: dict[str, Cs] = {}
_MODE_ORDER = {"thumb": 0}
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
THUMB_INSTRUCTION_IDS = frozenset(
    getattr(arm_const, name) for name in _THUMB_NAMES if hasattr(arm_const, name)
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _validate_root(root: Path) -> Path:
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("repository root uses a symlink")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    if resolved != PROJECT_ROOT.resolve(strict=True):
        raise ValueError("repository root does not match the loaded project root")
    return resolved


def _safe_file(root: Path, relative: str | Path) -> Path:
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe repository-relative input: {relative}")
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _bounded(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError("bounded ROM slice escapes the ROM")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4), "little")


def _engine() -> Cs:
    if "thumb" not in _ENGINES:
        engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        engine.detail = True
        engine.skipdata = False
        _ENGINES["thumb"] = engine
    return _ENGINES["thumb"]


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _writes_pc(instruction: Any) -> bool:
    for operand in instruction.operands:
        if operand.type == arm_const.ARM_OP_REG and operand.reg == arm_const.ARM_REG_PC and operand.access & CS_AC_WRITE:
            return True
    try:
        _, writes = instruction.regs_access()
    except (AttributeError, capstone.CsError):
        writes = []
    return arm_const.ARM_REG_PC in writes


def _is_conditional(instruction: Any) -> bool:
    condition = getattr(instruction, "cc", arm_const.ARM_CC_AL)
    return condition not in (arm_const.ARM_CC_AL, arm_const.ARM_CC_INVALID)


def _valid_thumb(raw: bytes, instruction: Any) -> bool:
    if instruction.id not in THUMB_INSTRUCTION_IDS:
        return False
    if instruction.size == 2:
        return len(raw) >= 2
    if instruction.size != 4 or len(raw) < 4:
        return False
    first = int.from_bytes(raw[:2], "little")
    second = int.from_bytes(raw[2:4], "little")
    return instruction.id == arm_const.ARM_INS_BL and first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def _raw_control_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
    if len(raw) not in (2, 4):
        return None
    first = int.from_bytes(raw[:2], "little")
    if len(raw) == 4:
        second = int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {"flow_kind": "call", "size": 4, "conditional": False, "target_file_offset": offset + 4 + _sign_extend(encoded, 23)}
    if first & 0xFF00 == 0xDF00:
        return {"flow_kind": "supervisor_call", "size": 2, "conditional": False, "swi_immediate": first & 0xFF}
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        return {"flow_kind": "conditional_branch", "size": 2, "conditional": True, "target_file_offset": offset + 4 + _sign_extend((first & 0xFF) << 1, 9)}
    if first & 0xF800 == 0xE000:
        return {"flow_kind": "unconditional_branch", "size": 2, "conditional": False, "target_file_offset": offset + 4 + _sign_extend((first & 0x07FF) << 1, 12)}
    if first & 0xFF87 == 0x4700:
        register = (first >> 3) & 0xF
        return {"flow_kind": "return" if register == 14 else "indirect_branch", "size": 2, "conditional": False, "register": register}
    return None


def _edge(kind: str, offset: int) -> dict[str, Any]:
    return {"kind": kind, "mode": "thumb", "file_offset": offset}


def _decode_one(rom: bytes, offset: int) -> dict[str, Any]:
    base = {"accepted": False, "mode": "thumb", "file_offset": offset}
    if offset < 0 or offset >= len(rom) or offset % 2:
        return {**base, "frontier_reason": "misaligned_or_outside_entry"}
    decoded = tuple(_engine().disasm(rom[offset : offset + 4], ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset:
        return {**base, "frontier_reason": "decode_failure"}
    instruction = decoded[0]
    raw = rom[offset : offset + instruction.size]
    if len(raw) != instruction.size:
        return {**base, "frontier_reason": "decode_failure"}
    if not _valid_thumb(raw, instruction):
        return {**base, "frontier_reason": "unsupported_armv4t_instruction"}
    raw_flow = _raw_control_flow(raw, offset)
    capstone_control = instruction.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL, arm_const.ARM_INS_BX, arm_const.ARM_INS_SVC)
    if capstone_control and raw_flow is None:
        return {**base, "frontier_reason": "control_flow_oracle_mismatch"}
    if raw_flow is not None:
        expected_ids = {
            "unconditional_branch": arm_const.ARM_INS_B,
            "conditional_branch": arm_const.ARM_INS_B,
            "call": arm_const.ARM_INS_BL,
            "return": arm_const.ARM_INS_BX,
            "indirect_branch": arm_const.ARM_INS_BX,
            "supervisor_call": arm_const.ARM_INS_SVC,
        }
        expected = expected_ids.get(raw_flow["flow_kind"])
        if instruction.id != expected or instruction.size != raw_flow["size"]:
            return {**base, "frontier_reason": "control_flow_oracle_mismatch"}
    conditional = raw_flow["conditional"] if raw_flow is not None else _is_conditional(instruction)
    end = offset + instruction.size
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    raw_indirect_pc = False
    if raw_flow is not None and raw_flow["flow_kind"] in {"call", "conditional_branch", "unconditional_branch"}:
        kind = "call_target" if raw_flow["flow_kind"] == "call" else "branch_target"
        target = raw_flow["target_file_offset"]
        if 0 <= target < len(rom) and target % 2 == 0:
            successors.append(_edge(kind, target))
        else:
            frontiers.append({"reason": "direct_target_outside_or_misaligned", "target": {"mode": "thumb", "file_offset": target}})
        if raw_flow["flow_kind"] in {"call", "conditional_branch"} and end < len(rom):
            successors.append(_edge("fallthrough", end))
        flow_kind = raw_flow["flow_kind"]
    elif raw_flow is not None and raw_flow["flow_kind"] == "supervisor_call":
        frontiers.append({"reason": "bios_swi_external", "swi_immediate": raw_flow["swi_immediate"], "target": {"address_space": "bios", "gba_address": "0x00000008"}})
        if end < len(rom):
            successors.append(_edge("fallthrough", end))
        flow_kind = "supervisor_call"
    elif raw_flow is not None and raw_flow["flow_kind"] in {"return", "indirect_branch"}:
        flow_kind = raw_flow["flow_kind"]
        if flow_kind == "indirect_branch":
            raw_indirect_pc = True
            frontiers.append({"reason": "indirect_pc_target"})
    elif _writes_pc(instruction):
        flow_kind = "return" if instruction.id == arm_const.ARM_INS_POP else "indirect_branch"
        if flow_kind == "indirect_branch":
            raw_indirect_pc = True
            frontiers.append({"reason": "indirect_pc_target"})
    else:
        flow_kind = "linear"
        if end < len(rom):
            successors.append(_edge("fallthrough", end))
    successors.sort(key=lambda item: (_EDGE_ORDER[item["kind"]], item["file_offset"]))
    return {
        **base,
        "accepted": True,
        "mode": "thumb",
        "file_offset": offset,
        "gba_address": _gba(offset),
        "size": instruction.size,
        "raw_hex": raw.hex(),
        "bytes_sha256": _sha(raw),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "conditional": conditional,
        "flow_kind": flow_kind,
        "raw_flow_kind": raw_flow["flow_kind"] if raw_flow is not None else None,
        "raw_indirect_pc": raw_indirect_pc,
        "successors": successors,
        "frontiers": frontiers,
    }


def _exact_pop_bx_return(rom: bytes, node: dict[str, Any], previous: dict[str, Any] | None, incoming: list[tuple[int, str]]) -> bool:
    """Return only for a unique, same-block pop{r0/r1};bx same-register pair."""
    if node.get("raw_flow_kind") != "indirect_branch" or node.get("mnemonic") != "bx" or previous is None:
        return False
    if len(incoming) != 1 or incoming[0][0] != previous.get("file_offset") or incoming[0][1] != "fallthrough":
        return False
    if previous.get("file_offset", -2) + previous.get("size", 0) != node["file_offset"] or previous.get("flow_kind") != "linear":
        return False
    if previous.get("successors") != [_edge("fallthrough", node["file_offset"])] or len(node.get("successors", [])) != 0:
        return False
    raw_bx = _u16(rom, node["file_offset"])
    register = (raw_bx >> 3) & 0xF
    if register not in (0, 1):
        return False
    raw_pop = _u16(rom, previous["file_offset"])
    return raw_pop == 0xBC00 | (1 << register)


def _close_exact_returns(rom: bytes, nodes: dict[int, dict[str, Any]]) -> None:
    """Apply the idiom after closure, with predecessor uniqueness proved."""
    incoming: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for edge in node.get("successors", []):
            if edge["file_offset"] in nodes:
                incoming[edge["file_offset"]].append((source, edge["kind"]))
    for offset, node in nodes.items():
        previous = nodes.get(offset - 2)
        if _exact_pop_bx_return(rom, node, previous, incoming.get(offset, [])):
            node["flow_kind"] = "return"
            node["frontiers"] = []


def _load_coverage(root: Path, rom: bytes) -> tuple[dict[str, Any], bytearray]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    coverage = json.loads(raw.decode("utf-8"))
    if coverage.get("schema") != "rom-byte-coverage-v1" or coverage.get("base_rom") != {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:
        raise ValueError("coverage baseline contract changed")
    segments = coverage.get("segments")
    claims = coverage.get("claims")
    if not isinstance(segments, list) or not isinstance(claims, list):
        raise ValueError("coverage baseline segments or claims missing")
    unknown = bytearray(ROM_SIZE)
    cursor = 0
    classified = 0
    unknown_count = 0
    unknown_ranges: list[list[int]] = []
    for segment in segments:
        value = segment.get("range")
        if not isinstance(value, list) or len(value) != 2 or value[0] != cursor or value[1] <= value[0] or value[1] > ROM_SIZE:
            raise ValueError("coverage baseline partition changed")
        start, end = value
        if segment.get("primary_class") == "unknown":
            unknown[start:end] = b"\1" * (end - start)
            unknown_count += end - start
            unknown_ranges.append([start, end])
        else:
            classified += end - start
        cursor = end
    if cursor != ROM_SIZE or (classified, unknown_count) != (6_119_306, 172_150):
        raise ValueError("coverage baseline count changed")
    if coverage.get("summary", {}).get("classified_bytes") != classified or coverage.get("summary", {}).get("unknown_bytes") != unknown_count:
        raise ValueError("coverage baseline summary changed")
    return {
        "path": COVERAGE_PATH.as_posix(),
        "sha256": COVERAGE_SHA256,
        "schema": coverage["schema"],
        "classified_bytes": classified,
        "unknown_bytes": unknown_count,
        "segment_count": len(segments),
        "claim_count": len(claims),
        "unknown_ranges": unknown_ranges,
        "claims": claims,
    }, unknown


def _claim_map(coverage: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item.get("id"): item for item in coverage["claims"] if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _read_json_contract(root: Path, path: Path, expected_sha: str, label: str) -> tuple[dict[str, Any], bytes]:
    raw = _safe_file(root, path).read_bytes()
    if _sha(raw) != expected_sha:
        raise ValueError(f"{label} identity changed")
    try:
        value = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value, raw


def _verify_handoff(root: Path, rom: bytes) -> dict[str, Any]:
    manifest, _ = _read_json_contract(root, BOOT_MANIFEST_PATH, BOOT_MANIFEST_SHA256, "boot manifest")
    if manifest.get("schema") != "rom-boot-framebuffers-v1":
        raise ValueError("boot manifest schema changed")
    thumb = manifest.get("startup_chain", {}).get("thumb_handoff", {})
    if thumb != {"literal": "0x080000F8", "mode": "thumb", "target": "0x08060FAD"}:
        raise ValueError("boot manifest Thumb handoff changed")
    raw = _bounded(rom, *HANDOFF_RANGE)
    if _sha(raw) != HANDOFF_SHA256 or raw.hex() != "0c109fe50fe0a0e111ff2fe1":
        raise ValueError("raw ARM startup handoff changed")
    if _u32(rom, 0xE4) != 0xE59F100C or _u32(rom, 0xE8) != 0xE1A0E00F or _u32(rom, 0xEC) != 0xE12FFF11:
        raise ValueError("ARM startup handoff opcode changed")
    pointer_raw = _bounded(rom, HANDOFF_LITERAL, HANDOFF_LITERAL + 4)
    if pointer_raw.hex() != HANDOFF_LITERAL_RAW or _u32(rom, HANDOFF_LITERAL) != HANDOFF_POINTER:
        raise ValueError("ARM startup handoff literal changed")
    occurrences = [offset for offset in range(0, len(rom) - 3) if rom[offset : offset + 4] == pointer_raw]
    if occurrences != [HANDOFF_LITERAL]:
        raise ValueError("Thumb handoff pointer occurrence denominator changed")
    root_offset = (HANDOFF_POINTER - ROM_BASE) & ~1
    if root_offset != ROOT_OFFSET or root_offset % 2:
        raise ValueError("Thumb handoff root mode or parity changed")
    root_raw = _bounded(rom, root_offset, root_offset + 4)
    if root_raw.hex() != ROOT_RAW or _sha(root_raw) != ROOT_SHA256:
        raise ValueError("Thumb handoff root bytes changed")
    excluded = _bounded(rom, *EXCLUDED_PREFIX)
    if _sha(excluded) != EXCLUDED_PREFIX_SHA256:
        raise ValueError("excluded handoff prefix changed")
    return {
        "boot_manifest": {"path": BOOT_MANIFEST_PATH.as_posix(), "sha256": BOOT_MANIFEST_SHA256},
        "arm_handoff": {
            "range": list(HANDOFF_RANGE), "gba_range": [_gba(HANDOFF_RANGE[0]), _gba(HANDOFF_RANGE[1])],
            "raw_hex": raw.hex(), "sha256": HANDOFF_SHA256,
            "instructions": [
                {"file_offset": 0xE4, "raw_hex": "0c109fe5", "operation": "ldr_pc_relative", "literal_offset": HANDOFF_LITERAL},
                {"file_offset": 0xE8, "raw_hex": "0fe0a0e1", "operation": "mov_lr_pc"},
                {"file_offset": 0xEC, "raw_hex": "11ff2fe1", "operation": "bx_r1"},
            ],
        },
        "literal": {"file_offset": HANDOFF_LITERAL, "gba_address": _gba(HANDOFF_LITERAL), "raw_hex": HANDOFF_LITERAL_RAW, "value": f"0x{HANDOFF_POINTER:08X}", "occurrences": occurrences},
        "root": {"mode": "thumb", "pointer": f"0x{HANDOFF_POINTER:08X}", "file_offset": ROOT_OFFSET, "gba_address": _gba(ROOT_OFFSET), "raw_hex": ROOT_RAW, "sha256": ROOT_SHA256},
        "excluded_prefix": {"range": list(EXCLUDED_PREFIX), "sha256": EXCLUDED_PREFIX_SHA256, "excluded_from_cfg": True},
    }


def _verify_existing_entries(root: Path, rom: bytes, coverage: dict[str, Any]) -> dict[int, dict[str, Any]]:
    seeds, _ = _read_json_contract(root, CFG_SEEDS_PAYLOAD_PATH, CFG_SEEDS_PAYLOAD_SHA256, "CFG seeds payload")
    if seeds.get("schema") != "rom-cfg-seeds-v1" or seeds.get("rom") != {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}:
        raise ValueError("CFG seeds payload contract changed")
    cfg_manifest, _ = _read_json_contract(root, CFG_V2_MANIFEST_PATH, CFG_V2_MANIFEST_SHA256, "CFG v2 manifest")
    cfg_payload, _ = _read_json_contract(root, CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "CFG v2 payload")
    if cfg_manifest.get("artifact_schema") != "rom-cfg-inventory-v2" or cfg_manifest.get("files", {}).get(CFG_V2_PAYLOAD_PATH.name, {}).get("sha256") != CFG_V2_PAYLOAD_SHA256:
        raise ValueError("CFG v2 artifact binding changed")
    if cfg_payload.get("schema") != "rom-cfg-inventory-v2" or cfg_payload.get("rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("CFG v2 payload contract changed")
    blocks = cfg_payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("CFG v2 blocks missing")
    # Rebuild the exact instruction-entry set from the frozen block ranges and
    # raw Thumb decoding.  A coverage owner boundary is not an instruction
    # entry, and a block start is not sufficient for the 0x09C0E0 interior
    # entry case.
    frozen_entries: set[int] = set()
    for block in blocks:
        if not isinstance(block, dict) or block.get("mode") != "thumb":
            continue
        value = block.get("range")
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("CFG v2 Thumb block range changed")
        start, end = value
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or start >= end or end > len(rom) or start % 2:
            raise ValueError("CFG v2 Thumb block boundary changed")
        offset = start
        decoded_count = 0
        while offset < end:
            decoded = tuple(_engine().disasm(rom[offset : offset + 4], ROM_BASE + offset, count=1))
            if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset or decoded[0].size not in (2, 4) or offset + decoded[0].size > end:
                raise ValueError(f"CFG v2 raw Thumb decode changed at 0x{offset:06X}")
            frozen_entries.add(offset)
            offset += decoded[0].size
            decoded_count += 1
        if offset != end or block.get("instruction_count") != decoded_count or block.get("bytes_sha256") != _sha(_bounded(rom, start, end)):
            raise ValueError(f"CFG v2 Thumb block identity changed at 0x{start:06X}")
    cfg_entry_targets = EXISTING_ENTRY_OFFSETS - {0x061086}
    if not cfg_entry_targets <= frozen_entries:
        raise ValueError("CFG v2 exact entry set changed")
    inter_manifest, _ = _read_json_contract(root, BOOT_INTERWORK_MANIFEST_PATH, BOOT_INTERWORK_MANIFEST_SHA256, "boot interwork manifest")
    inter_payload, _ = _read_json_contract(root, BOOT_INTERWORK_PAYLOAD_PATH, BOOT_INTERWORK_PAYLOAD_SHA256, "boot interwork payload")
    if inter_manifest.get("artifact_schema") != "rom-boot-interwork-v1" or inter_manifest.get("files", {}).get(BOOT_INTERWORK_PAYLOAD_PATH.name, {}).get("sha256") != BOOT_INTERWORK_PAYLOAD_SHA256:
        raise ValueError("boot interwork artifact binding changed")
    spine = inter_payload.get("producer_chain", {}).get("interwork_spine", [])
    if not any(item.get("kind") == "thumb_bl" and item.get("range") == [0x061086, 0x06108A] for item in spine if isinstance(item, dict)):
        raise ValueError("boot interwork exact entry changed")
    claim_by_id = _claim_map(coverage)
    result: dict[int, dict[str, Any]] = {}
    for target, spec in EXISTING_ENTRY_SPECS.items():
        claim = claim_by_id.get(spec["claim_id"])
        if not isinstance(claim, dict) or claim.get("range") != spec["range"] or claim.get("primary_class") != spec["class"] or claim.get("role") != "primary":
            raise ValueError(f"existing owner claim changed at 0x{target:06X}")
        if claim.get("bytes_sha256") != _sha(_bounded(rom, *spec["range"])):
            raise ValueError(f"existing owner bytes changed at 0x{target:06X}")
        if spec["kind"] == "cfg_v2" and target not in frozen_entries:
            raise ValueError(f"CFG v2 exact entry changed at 0x{target:06X}")
        result[target] = {
            "target_offset": target, "target_gba_address": _gba(target), "mode": "thumb",
            "exact_entry_offset": target, "target_scheduled": False,
            "owner_claim_id": spec["claim_id"], "owner_range": spec["range"],
            "owner_primary_class": spec["class"], "owner_claim_kind": claim.get("claim_kind"),
            "owner_interior_entry": bool(spec.get("interior_entry", False)),
            "evidence_path": claim.get("evidence_path"), "evidence_sha256": claim.get("evidence_sha256"),
            "evidence_selector": claim.get("evidence_selector"),
        }
    return result


def _verify_new_entry(root: Path, rom: bytes, coverage: dict[str, Any]) -> dict[str, Any]:
    callsite_raw = _bounded(rom, NEW_CALLSITE, NEW_CALLSITE + 4)
    if callsite_raw.hex() != NEW_CALLSITE_RAW or _sha(callsite_raw) != NEW_CALLSITE_SHA256:
        raise ValueError("0x61624 proof callsite bytes changed")
    first = _u16(rom, NEW_CALLSITE)
    second = _u16(rom, NEW_CALLSITE + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("0x61624 proof BL halfwords changed")
    target = NEW_CALLSITE + 4 + _sign_extend(((first & 0x07FF) << 12) | ((second & 0x07FF) << 1), 23)
    if target != NEW_ENTRY or target % 2:
        raise ValueError("0x61624 proof BL target or mode changed")
    target_raw = _bounded(rom, NEW_ENTRY, NEW_ENTRY + 2)
    if target_raw.hex() != NEW_ENTRY_RAW or _sha(target_raw) != NEW_ENTRY_SHA256:
        raise ValueError("0x61624 proof first instruction changed")
    target_decoded = _decode_one(rom, NEW_ENTRY)
    if not target_decoded.get("accepted") or target_decoded.get("mnemonic") != "push" or target_decoded.get("size") != 2:
        raise ValueError("0x61624 proof first instruction decode changed")
    claim = _claim_map(coverage).get(NEW_OWNER_ID)
    if not isinstance(claim, dict) or claim.get("range") != list(NEW_OWNER_RANGE) or claim.get("primary_class") != NEW_OWNER_CLASS or claim.get("role") != "primary" or claim.get("bytes_sha256") != _sha(_bounded(rom, *NEW_OWNER_RANGE)):
        raise ValueError("0x61624 owner identity or boundary changed")
    return {
        "entry": {"mode": "thumb", "file_offset": NEW_ENTRY, "gba_address": _gba(NEW_ENTRY), "raw_hex": NEW_ENTRY_RAW, "sha256": NEW_ENTRY_SHA256, "decoded": "push {r4,r5,lr}"},
        "source_call": {"file_offset": NEW_CALLSITE, "gba_address": _gba(NEW_CALLSITE), "raw_hex": NEW_CALLSITE_RAW, "sha256": NEW_CALLSITE_SHA256, "decoded": "bl 0x08061624", "target_offset": NEW_ENTRY, "fallthrough_offset": NEW_CALLSITE + 4},
        "source_and_fallthrough": [NEW_CALLSITE, NEW_CALLSITE + 4],
        "owner_claim_id": NEW_OWNER_ID, "owner_range": list(NEW_OWNER_RANGE), "owner_primary_class": NEW_OWNER_CLASS,
        "owner_limitation": "owner boundary is not instruction-only; direct BL plus first-instruction decode proves only the exact entry",
        "target_scheduled": False, "edge_resolution": "opaque_external_entry",
    }


def _traverse(rom: bytes, unknown: bytearray, existing: dict[int, dict[str, Any]], new_entry: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    pending = [ROOT_OFFSET]
    scheduled = {ROOT_OFFSET}
    nodes: dict[int, dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        node = _decode_one(rom, offset)
        if not node.get("accepted"):
            raise ValueError(f"reachable Thumb decode failed at 0x{offset:06X}")
        if not all(unknown[offset : offset + node["size"]]):
            raise ValueError(f"reachable instruction is not current unknown at 0x{offset:06X}")
        nodes[offset] = node
        for edge in node["successors"]:
            target = edge["file_offset"]
            if target in existing or target == NEW_ENTRY:
                owner = existing.get(target, new_entry)
                external.append({
                    "source_instruction_offset": offset,
                    "source_gba_address": _gba(offset),
                    "kind": edge["kind"], "mode": "thumb",
                    "target_offset": target, "target_gba_address": _gba(target),
                    "target_scheduled": False, "resolution": "opaque_external_entry",
                    "owner_claim_id": owner.get("owner_claim_id"),
                    "owner_range": owner.get("owner_range"),
                    "owner_primary_class": owner.get("owner_primary_class"),
                    "owner_interior_entry": owner.get("owner_interior_entry", False),
                })
                continue
            candidate = _decode_one(rom, target)
            if not candidate.get("accepted"):
                raise ValueError(f"successor decode failed at 0x{target:06X}")
            if not all(unknown[target : target + candidate["size"]]):
                raise ValueError(f"successor is not current unknown at 0x{target:06X}")
            if target not in scheduled:
                heapq.heappush(pending, target)
                scheduled.add(target)
    if len(nodes) != EXPECTED_SUMMARY["instruction_count"] or sum(item["size"] for item in nodes.values()) != EXPECTED_SUMMARY["instruction_bytes"]:
        raise ValueError("target-limited Thumb worklist denominator changed")
    if len(external) != EXPECTED_SUMMARY["external_edge_count"]:
        raise ValueError("target-limited external edge denominator changed")
    _close_exact_returns(rom, nodes)
    return nodes, external


def _build_blocks(rom: bytes, nodes: dict[int, dict[str, Any]], external: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    predecessors: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for edge in node["successors"]:
            if edge["file_offset"] in nodes:
                predecessors[edge["file_offset"]].append((source, edge["kind"]))
    starts = {ROOT_OFFSET}
    for offset, incoming in predecessors.items():
        if offset == ROOT_OFFSET:
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
            "id": block_by_offset[start], "mode": "thumb", "range": [start, end], "gba_range": [_gba(start), _gba(end)],
            "instruction_count": len(members), "bytes_sha256": _sha(_bounded(rom, start, end)),
            "terminator": {"file_offset": members[-1], "size": last["size"], "raw_hex": last["raw_hex"], "mnemonic": last["mnemonic"], "op_str": last["op_str"], "flow_kind": last["flow_kind"], "conditional": last["conditional"]},
            "successors": [],
        })
    if len(block_by_offset) != len(nodes) or len(blocks) != EXPECTED_SUMMARY["block_count"]:
        raise ValueError("target-limited Thumb block denominator changed")
    ext_by_source = defaultdict(list)
    for edge in external:
        ext_by_source[edge["source_instruction_offset"]].append(edge)
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["file_offset"]
        node = nodes[source]
        for edge in node["successors"]:
            target = edge["file_offset"]
            if target in nodes:
                record = {"source_block_id": block["id"], "source_instruction_offset": source, "kind": edge["kind"], "mode": "thumb", "target_offset": target, "target_gba_address": _gba(target), "target_block_id": block_by_offset[target], "target_scheduled": True, "resolution": "internal"}
            else:
                matches = [item for item in ext_by_source[source] if item["kind"] == edge["kind"] and item["target_offset"] == target]
                if len(matches) != 1:
                    raise ValueError("external edge binding changed")
                record = {**matches[0], "source_block_id": block["id"]}
            block["successors"].append(record)
            edges.append(record)
    internal = [edge for edge in edges if edge["resolution"] == "internal"]
    if len(internal) != EXPECTED_SUMMARY["internal_edge_count"]:
        raise ValueError("internal edge denominator changed")
    if len(edges) != EXPECTED_SUMMARY["internal_edge_count"] + EXPECTED_SUMMARY["external_edge_count"]:
        raise ValueError("edge denominator changed")
    return blocks, edges


def _literal_bindings(rom: bytes, nodes: dict[int, dict[str, Any]], unknown: bytearray) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    for offset, node in sorted(nodes.items()):
        if node["size"] != 2:
            continue
        halfword = _u16(rom, offset)
        if halfword & 0xF800 != 0x4800:
            continue
        literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
        value = _u32(rom, literal)
        raw_value = f"0x{value:08X}"
        normalized = value & ~1 if literal == 0x099E00 else value
        bindings.append({
            "instruction_offset": offset, "load_offset": offset, "instruction_gba_address": _gba(offset),
            "literal_offset": literal, "literal_gba_address": _gba(literal), "raw_value": raw_value,
            "normalized_value": f"0x{normalized:08X}", "value": raw_value,
            "raw_hex": _bounded(rom, literal, literal + 4).hex(),
            "address_kind": "iwram_thumb" if literal == 0x099E00 else "raw_word",
        })
    if len(bindings) != EXPECTED_SUMMARY["literal_ref_count"] or len({item["literal_offset"] for item in bindings}) != EXPECTED_SUMMARY["literal_word_count"]:
        raise ValueError("literal reference denominator changed")
    for item in bindings:
        if item["literal_offset"] % 4 or not all(unknown[item["literal_offset"] : item["literal_offset"] + 4]):
            raise ValueError("literal word is not current unknown")
    bindings.sort(key=lambda item: (item["literal_offset"], item["instruction_offset"]))
    return bindings


def _ranges_from_offsets(intervals: list[tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    # Literal references can legitimately share one pool word.  Deduplicate
    # exact intervals before coalescing adjacency so the 74-word denominator
    # cannot be inflated by the 77 reference vector.
    for start, end in sorted(set(intervals)):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _promotion(rom: bytes, nodes: dict[int, dict[str, Any]], literals: list[dict[str, Any]], unknown: bytearray) -> tuple[dict[str, Any], list[dict[str, Any]], list[list[int]], list[list[int]], list[list[int]]]:
    code_ranges = _ranges_from_offsets([(offset, offset + node["size"]) for offset, node in nodes.items()])
    literal_ranges = _ranges_from_offsets([(item["literal_offset"], item["literal_offset"] + 4) for item in literals])
    union = _ranges_from_offsets([(start, end) for start, end in code_ranges + literal_ranges])
    if (code_ranges, literal_ranges, union) != (CODE_RANGES, LITERAL_RANGES, UNION_RANGES):
        raise ValueError("promotion range vectors changed")
    if any(start < EXCLUDED_PREFIX[1] and end > EXCLUDED_PREFIX[0] for start, end in union):
        raise ValueError("excluded handoff prefix entered promotion")
    if any(not all(unknown[start:end]) for start, end in union):
        raise ValueError("promotion has current-known overlap")
    bundle = b"".join(_bounded(rom, start, end) for start, end in union)
    if len(bundle) != 1522 or _sha(bundle) != UNION_BYTES_SHA256 or _compact_sha(union) != UNION_RANGE_SHA256:
        raise ValueError("promotion union identity changed")
    records = []
    for kind, ranges in (("code", code_ranges), ("literal", literal_ranges)):
        for index, (start, end) in enumerate(ranges):
            records.append({"id": f"{kind}-{index:02d}-{start:06x}", "kind": kind, "range": [start, end], "size": end - start, "sha256": _sha(_bounded(rom, start, end)), "baseline_unknown_only": True})
    promotion = {
        "code_range_count": len(code_ranges), "code_bytes": sum(end - start for start, end in code_ranges),
        "literal_range_count": len(literal_ranges), "literal_bytes": sum(end - start for start, end in literal_ranges),
        "union_range_count": len(union), "union_bytes": sum(end - start for start, end in union),
        "union_range_vector_sha256": _compact_sha(union), "union_bytes_sha256": _sha(bundle),
        "current_known_overlap_bytes": 0, "wide_envelope": [ROOT_OFFSET, 0x09C098], "wide_envelope_is_claim": False,
        "future_coverage_claim_projection": {"code_claim_count": len(code_ranges), "literal_claim_count": len(literal_ranges), "semantically_merged_union_claim_count": 0},
    }
    return promotion, records, code_ranges, literal_ranges, union


def _implementation(root: Path) -> dict[str, Any]:
    paths = {
        "exporter": Path("tools/export_rom_boot_thumb_handoff_cfg.py"),
        "verifier": Path("tools/verify_rom_boot_thumb_handoff_cfg.py"),
        "test": Path("tests/test_export_rom_boot_thumb_handoff_cfg.py"),
    }
    return {role: {"path": path.as_posix(), "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in paths.items()}


def _build_payload(root: Path, rom: bytes | None = None) -> tuple[dict[str, Any], bytes]:
    root = _validate_root(root)
    canonical_rom = rom is None
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE:
        raise ValueError("base ROM identity mismatch")
    # The public build path loads and freezes the canonical ROM identity.  The
    # explicit byte-input hook is intentionally allowed to reach the individual
    # handoff/root leaf validators so mutation tests prove fail-closed behavior
    # at the leaf that changed, while never weakening build_payload().
    if canonical_rom and _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    handoff = _verify_handoff(root, rom)
    coverage, unknown = _load_coverage(root, rom)
    existing = _verify_existing_entries(root, rom, coverage)
    new_entry = _verify_new_entry(root, rom, coverage)
    nodes, external = _traverse(rom, unknown, existing, new_entry)
    blocks, edges = _build_blocks(rom, nodes, external)
    literals = _literal_bindings(rom, nodes, unknown)
    promotion, promotion_records, code_ranges, literal_ranges, union_ranges = _promotion(rom, nodes, literals, unknown)
    frontiers: list[dict[str, Any]] = []
    for offset, node in sorted(nodes.items()):
        for frontier in node["frontiers"]:
            if frontier.get("reason") == "indirect_pc_target":
                frontiers.append({"instruction_offset": offset, "gba_address": _gba(offset), "raw_hex": node["raw_hex"], **frontier})
    raw_indirect = [{"instruction_offset": offset, "gba_address": _gba(offset), "raw_hex": node["raw_hex"], "flow_kind": node["flow_kind"], "resolved_as_return": node["flow_kind"] == "return"} for offset, node in sorted(nodes.items()) if node.get("raw_indirect_pc")]
    if len(frontiers) != EXPECTED_SUMMARY["frontier_count"] or len(raw_indirect) != EXPECTED_SUMMARY["raw_indirect_pc_count"] or sum(node["flow_kind"] == "return" for node in nodes.values()) != EXPECTED_SUMMARY["return_count"]:
        raise ValueError("return/frontier denominator changed")
    claims = []
    for index, (start, end) in enumerate(code_ranges):
        claims.append({"id": f"thumb-code-{index:02d}-{start:06x}", "range": [start, end], "size": end - start, "semantic_class": "armv4t_cfg_handoff_thumb_code", "sha256": _sha(_bounded(rom, start, end)), "baseline_unknown_only": True})
    for index, (start, end) in enumerate(literal_ranges):
        claims.append({"id": f"thumb-literal-{index:02d}-{start:06x}", "range": [start, end], "size": end - start, "semantic_class": "thumb_pc_relative_literal", "sha256": _sha(_bounded(rom, start, end)), "baseline_unknown_only": True})
    payload = {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "handoff": handoff,
        "coverage_baseline": {key: value for key, value in coverage.items() if key != "claims"},
        "frozen_inputs": {
            "cfg_seeds_payload": {"path": CFG_SEEDS_PAYLOAD_PATH.as_posix(), "sha256": CFG_SEEDS_PAYLOAD_SHA256},
            "cfg_v2_manifest": {"path": CFG_V2_MANIFEST_PATH.as_posix(), "sha256": CFG_V2_MANIFEST_SHA256},
            "cfg_v2_payload": {"path": CFG_V2_PAYLOAD_PATH.as_posix(), "sha256": CFG_V2_PAYLOAD_SHA256},
            "boot_interwork_manifest": {"path": BOOT_INTERWORK_MANIFEST_PATH.as_posix(), "sha256": BOOT_INTERWORK_MANIFEST_SHA256},
            "boot_interwork_payload": {"path": BOOT_INTERWORK_PAYLOAD_PATH.as_posix(), "sha256": BOOT_INTERWORK_PAYLOAD_SHA256},
        },
        "existing_entry_claims": {f"0x{ROM_BASE + target:08X}": value for target, value in sorted(existing.items())},
        "entry_proofs": {f"0x{ROM_BASE + NEW_ENTRY:08X}": new_entry},
        "instructions": [nodes[offset] for offset in sorted(nodes)],
        "blocks": blocks,
        "edges": edges,
        "external_edges": [edge for edge in edges if edge["resolution"] == "opaque_external_entry"],
        "literal_bindings": literals,
        "frontiers": frontiers,
        "raw_indirect_pc_sites": raw_indirect,
        "code_ranges": code_ranges,
        "literal_ranges": literal_ranges,
        "union_ranges": union_ranges,
        "promotion_ranges": promotion_records,
        "coverage_claims": claims,
        "promotion": promotion,
        "summary": dict(EXPECTED_SUMMARY),
        "scope": dict(SCOPE),
        "limitations": list(LIMITATIONS),
        "implementation": _implementation(root),
    }
    return payload, b"".join(_bounded(rom, start, end) for start, end in union_ranges)


def build_payload(root: Path) -> tuple[dict[str, Any], bytes]:
    return _build_payload(_validate_root(root))


def build_payload_from_rom(root: Path, rom: bytes) -> tuple[dict[str, Any], bytes]:
    return _build_payload(_validate_root(root), rom)


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact output path uses a symlink")
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    requested = output.expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    experiment = (root / EXPERIMENT_ROOT).resolve(strict=False)
    final = experiment / "final"
    if target == root:
        raise ValueError("artifact output must not be the repository root")
    if target in root.parents:
        raise ValueError("artifact output must not be an ancestor of the repository root")
    if target != final:
        raise ValueError("artifact output must be this run's final directory")
    if target.exists():
        if not target.is_dir():
            raise ValueError("artifact output is not a directory")
        members = list(target.iterdir())
        if not members:
            return target
        if {item.name for item in members} != EXPECTED_FILES or any(item.is_symlink() or not item.is_file() for item in members):
            raise ValueError("foreign or non-empty artifact output directory")
        try:
            from tools.verify_rom_boot_thumb_handoff_cfg import verify_artifact
            report = verify_artifact(root, target)
        except Exception as error:
            raise ValueError(f"existing artifact failed independent verification: {error}") from error
        if report.get("verified") is not True:
            raise ValueError(f"existing artifact failed independent verification: {report.get('errors', [])}")
    return target


def _canonical_command(root: Path, artifact: Path, *, verifier: bool) -> list[str]:
    relative = artifact.resolve(strict=False).relative_to(root).as_posix()
    script = "tools/verify_rom_boot_thumb_handoff_cfg.py" if verifier else "tools/export_rom_boot_thumb_handoff_cfg.py"
    flag = "--artifact-dir" if verifier else "--output-dir"
    return ["python3", "-I", "-S", script, "--root", ".", flag, relative]


def _run_verifier(root: Path, artifact: Path, *, allow_candidate: bool = False) -> dict[str, Any]:
    command = [sys.executable, "-I", "-S", "tools/verify_rom_boot_thumb_handoff_cfg.py", "--root", str(root), "--artifact-dir", str(artifact)]
    if allow_candidate:
        command.append("--allow-candidate")
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    lines = completed.stdout.strip().splitlines()
    report: dict[str, Any] = {}
    if lines:
        try:
            report = json.loads(lines[-1])
        except json.JSONDecodeError:
            report = {"verified": False, "errors": [completed.stdout.strip()]}
    if completed.returncode != 0 or report.get("verified") is not True:
        raise ValueError(f"independent verifier rejected candidate: {completed.stderr.strip() or report}")
    return report


def _manifest(root: Path, output: Path, payload: dict[str, Any], payload_raw: bytes, bundle: bytes, *, status: str, report: dict[str, Any] | None) -> dict[str, Any]:
    implementation = payload["implementation"]
    verifier_command = _canonical_command(root, output, verifier=True)
    producer_command = _canonical_command(root, output, verifier=False)
    verification = {"schema": VERIFY_SCHEMA, "command": verifier_command, "exit_code": 0 if report is not None else None, "report": report, "verifier_sha256": implementation["verifier"]["sha256"]}
    return {
        "schema": PROMOTION_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": status,
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}, BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)}},
        "rom": payload["rom"], "coverage_baseline": payload["coverage_baseline"], "handoff": payload["handoff"], "promotion": payload["promotion"],
        "summary": payload["summary"], "implementation": implementation,
        "producer": {"command": producer_command, "implementation": implementation},
        "verifier": verification, "verification": verification,
        "scope": payload["scope"], "limitations": payload["limitations"],
    }


def _write_atomic(path: Path, raw: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = _validate_root(root)
    target = _validate_output(root, Path(output))
    payload, bundle = _build_payload(root)
    payload_raw = _canonical(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(target.parent)
    temporary = Path(tempfile.mkdtemp(prefix=f".{SCHEMA}-", dir=target.parent))
    backup: Path | None = None
    installed_new_target = False
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        (temporary / BUNDLE_NAME).write_bytes(bundle)
        (temporary / MANIFEST_NAME).write_bytes(_canonical(_manifest(root, target, payload, payload_raw, bundle, status="candidate", report=None)))
        report = _run_verifier(root, temporary, allow_candidate=True)
        accepted = _manifest(root, target, payload, payload_raw, bundle, status="accepted", report=report)
        (temporary / MANIFEST_NAME).write_bytes(_canonical(accepted))
        if target.exists():
            backup = target.with_name(f".{target.name}.old-{uuid.uuid4().hex}")
            os.replace(target, backup)
        os.replace(temporary, target)
        installed_new_target = True
        postflight = _run_verifier(root, target)
        if postflight != report:
            raise ValueError("accepted postflight verifier report changed")
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
        return accepted
    except BaseException:
        if installed_new_target and target.exists() and target.is_dir():
            failed = target.with_name(f".{target.name}.failed-{uuid.uuid4().hex}")
            os.replace(target, failed)
            shutil.rmtree(failed)
        if backup is not None and backup.exists():
            os.replace(backup, target)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", "--out-dir", dest="output", type=Path, required=True)
    args = parser.parse_args()
    manifest = export_artifact(args.root, args.output)
    print(json.dumps(manifest["promotion"], ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
