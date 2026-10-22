#!/usr/bin/env python3
"""Independently verify the frozen target-limited Thumb handoff artifact."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import sys
from typing import Any


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
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_PATH = "rom/base.gba"
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "rom-boot-thumb-handoff-cfg.json"
BUNDLE_NAME = "rom-boot-thumb-handoff-cfg.bin"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_ROOT = "build/experiments/active/boot-thumb-handoff-cfg-v1/sol-r2-20260827"
FINAL_RELATIVE = f"{EXPERIMENT_ROOT}/final"

COVERAGE_PATH = "sequel/rom-byte-coverage.json"
COVERAGE_SHA256 = "4ea0496a0754d0391ae4f48e16f941d9a2241c9cc730bdf38799abde85181cbd"
COVERAGE_UNKNOWN_COUNT = 172_150
COVERAGE_CLASSIFIED_COUNT = 6_119_306
COVERAGE_SEGMENT_COUNT = 16_498
COVERAGE_CLAIM_COUNT = 14_409
COVERAGE_UNKNOWN_RANGES_SHA256 = "28dcbb67db98959bc8ca5eb7bf552e637c1a838de1d235f9325be10ce8d0cb47"

BOOT_MANIFEST_PATH = "artifacts/rom-boot-framebuffers-v1/manifest.json"
BOOT_MANIFEST_SHA256 = "ede3fa29106e8b67cc40e37746b5a44b85beddeb2750e660d5955e26d946238d"
CFG_SEEDS_PATH = "artifacts/rom-cfg-seeds-v1/rom-cfg-seeds.json"
CFG_SEEDS_SHA256 = "53960ae8e460b862bbc52d447290d988ed8a496417ccf08a810041384df1b05c"
CFG_V2_MANIFEST_PATH = "artifacts/rom-cfg-inventory-v2/manifest.json"
CFG_V2_MANIFEST_SHA256 = "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"
CFG_V2_PAYLOAD_PATH = "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json"
CFG_V2_PAYLOAD_SHA256 = "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
BOOT_INTERWORK_MANIFEST_PATH = "artifacts/rom-boot-interwork-v1/manifest.json"
BOOT_INTERWORK_MANIFEST_SHA256 = "f2673837955194f35daab4f9fb7c0b2fe2dd5967231fcd6d982d0cacb9f749be"
BOOT_INTERWORK_PAYLOAD_PATH = "artifacts/rom-boot-interwork-v1/rom-boot-interwork.json"
BOOT_INTERWORK_PAYLOAD_SHA256 = "2f78132647235ca1c9fd155b950ff4128e4b01ca10d0fa0ae0fcfa4fdd37e30d"

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
NEW_CALLSITE = 0x060FE0
NEW_CALLSITE_RAW = "00f020fb"
NEW_CALLSITE_SHA256 = "863c2fdd72169166dddf0538761736276d44edd62cad291bd254410f0d545ddf"
NEW_ENTRY_RAW = "30b5"
NEW_ENTRY_SHA256 = "0179fa50db01a670ea0d378b606928ed6b7a1f590c3fe52fcfe05a1936a84414"
NEW_OWNER_ID = "consumer-code-battle_effect_sprite_animations-061624"
NEW_OWNER_RANGE = [0x061624, 0x061710]
NEW_OWNER_CLASS = "consumer_code_slice"
NEW_OWNER_BYTES_SHA256 = "e3ba1dadf23b428fd2a39b6d9aef48b7ba9521d825ca196b37d7a93403192dff"

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

EXTERNAL_TARGETS = {
    0x60FE0: 0x61624,
    0x6101A: 0x64700,
    0x61050: 0x64C68,
    0x6105A: 0x64A48,
    0x61064: 0x65384,
    0x6106C: 0x61D7C,
    0x61082: 0x61086,
    0x61F82: 0x9B0C4,
    0x61F94: 0x9B140,
    0x62250: 0x9C0E0,
    0x62294: 0x9C110,
    0x622E0: 0x9C0E0,
    0x622F8: 0x9C0E0,
    0x646DE: 0x9C0E0,
}
ENTRY_SPECS = {
    0x61086: ("boot-interwork-thumb-direct-caller", [0x61086, 0x6108A], "boot_interwork_thumb_code", False, "boot_interwork_thumb_instruction_bytes", BOOT_INTERWORK_PAYLOAD_PATH, BOOT_INTERWORK_PAYLOAD_SHA256, "/coverage_claims/2"),
    0x64700: ("cfg-thumb-0025-064700", [0x64700, 0x6474C], "armv4t_cfg_reachable_thumb_code", False, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
    0x64A48: ("cfg-thumb-0040-064a48", [0x64A48, 0x64A5C], "armv4t_cfg_reachable_thumb_code", False, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
    0x64C68: ("cfg-thumb-0041-064c68", [0x64C68, 0x64C9A], "armv4t_cfg_reachable_thumb_code", False, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
    0x65384: ("cfg-thumb-0052-065384", [0x65384, 0x65390], "armv4t_cfg_reachable_thumb_code", False, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
    0x61D7C: ("cfg-thumb-0000-061d7c", [0x61D7C, 0x61DEA], "armv4t_cfg_reachable_thumb_code", False, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
    0x9B0C4: ("cfg-thumb-0764-09b0c4", [0x9B0C4, 0x9B122], "armv4t_cfg_reachable_thumb_code", False, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
    0x9B140: ("cfg-thumb-0765-09b140", [0x9B140, 0x9B16E], "armv4t_cfg_reachable_thumb_code", False, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
    0x9C0E0: ("cfg-thumb-0773-09c0d8", [0x9C0D8, 0x9C0F4], "armv4t_cfg_reachable_thumb_code", True, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
    0x9C110: ("cfg-thumb-0774-09c110", [0x9C110, 0x9C112], "armv4t_cfg_reachable_thumb_code", False, "cfg_reachable_instruction_bytes", CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "/blocks"),
}
OWNER_BYTES_SHA256 = {
    0x61086: "589051c73628c96114c0977c1ee91cd7446f42932dfeed31936f351e436d58b7",
    0x64700: "334b0e75f8a9a446f7139bfa982d9e3028a781c52394b9fa05363f56ac7fb59d",
    0x64A48: "b0d0974888b67db4e8896f1864e8024f39bfa52149873aceaa88609cf8b39638",
    0x64C68: "d521112d44ad39ea7bc35c91ada3d787925a030e73ed12111493ba74034a3e8f",
    0x65384: "e63125fc1969f1c80a4682255a3808df875e7cb0681683173dbcc863143923b3",
    0x61D7C: "a95b7b4ebd38bd2422bad8c1ac40a932dae4f2173577b466152c8e1f0410660d",
    0x9B0C4: "68027f22bd5da3aec90a4e113e6b077e5fd161daed18217439278cdffe298217",
    0x9B140: "b91b5fbe2179dc9a2822acdf4db99edb36ee84780d400606e318d7602a47781e",
    0x9C0E0: "6d8f673e7cf486aa2783e4ddacec4b3c6c66c84b77af3763cba303f862e207ae",
    0x9C110: "81904e68a8b9a2427e9e87e2c61b1098057608d18357d70d9281e8513941cf53",
}

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

_ENGINE: Cs | None = None
_EDGE_ORDER = {"branch_target": 0, "call_target": 1, "fallthrough": 2}
_THUMB_NAMES = (
    "ARM_INS_ADC", "ARM_INS_ADD", "ARM_INS_ADR", "ARM_INS_AND", "ARM_INS_ASR", "ARM_INS_B",
    "ARM_INS_BIC", "ARM_INS_BL", "ARM_INS_BX", "ARM_INS_CMN", "ARM_INS_CMP", "ARM_INS_EOR",
    "ARM_INS_LDM", "ARM_INS_LDMIA", "ARM_INS_LDMIB", "ARM_INS_LDR", "ARM_INS_LDRB",
    "ARM_INS_LDRH", "ARM_INS_LDRSB", "ARM_INS_LDRSH", "ARM_INS_LSL", "ARM_INS_LSR",
    "ARM_INS_MLA", "ARM_INS_MOV", "ARM_INS_MOVS", "ARM_INS_MUL", "ARM_INS_MVN", "ARM_INS_NEG",
    "ARM_INS_NOP", "ARM_INS_ORR", "ARM_INS_POP", "ARM_INS_PUSH", "ARM_INS_ROR", "ARM_INS_RSB",
    "ARM_INS_SBC", "ARM_INS_STMIA", "ARM_INS_STR", "ARM_INS_STRB", "ARM_INS_STRH", "ARM_INS_SUB",
    "ARM_INS_SUBS", "ARM_INS_SVC", "ARM_INS_TST", "ARM_INS_UXTH", "ARM_INS_REV",
)
THUMB_IDS = frozenset(getattr(arm_const, name) for name in _THUMB_NAMES if hasattr(arm_const, name))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _compact_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _root_path(root: Path) -> Path:
    requested = Path(root).expanduser()
    if requested.is_symlink():
        raise ValueError("repository root uses a symlink")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("repository root is not a directory")
    if resolved != PROJECT_ROOT.resolve(strict=True):
        raise ValueError("repository root does not match the loaded project root")
    return resolved


def _safe_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe repository-relative input")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError(f"repository input uses a symlink: {relative}")
    result = (root / path).resolve(strict=True)
    try:
        result.relative_to(root)
    except ValueError as error:
        raise ValueError(f"repository input escapes root: {relative}") from error
    if not result.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return result


def _read_json_contract(root: Path, relative: str, expected_sha: str, label: str) -> dict[str, Any]:
    raw = _safe_file(root, relative).read_bytes()
    if _sha(raw) != expected_sha:
        raise ValueError(f"{label} identity changed")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not canonical JSON input") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _load_frozen_inputs(root: Path, rom: bytes) -> set[int]:
    boot = _read_json_contract(root, BOOT_MANIFEST_PATH, BOOT_MANIFEST_SHA256, "boot manifest")
    if boot.get("schema") != "rom-boot-framebuffers-v1" or boot.get("startup_chain", {}).get("thumb_handoff") != {
        "literal": "0x080000F8", "mode": "thumb", "target": "0x08060FAD"
    }:
        raise ValueError("boot manifest contract changed")

    seeds = _read_json_contract(root, CFG_SEEDS_PATH, CFG_SEEDS_SHA256, "CFG seeds payload")
    if seeds.get("schema") != "rom-cfg-seeds-v1" or seeds.get("rom") != {
        "path": ROM_PATH, "size": ROM_SIZE, "sha256": ROM_SHA256
    }:
        raise ValueError("CFG seeds payload contract changed")

    cfg_manifest = _read_json_contract(root, CFG_V2_MANIFEST_PATH, CFG_V2_MANIFEST_SHA256, "CFG v2 manifest")
    cfg_payload = _read_json_contract(root, CFG_V2_PAYLOAD_PATH, CFG_V2_PAYLOAD_SHA256, "CFG v2 payload")
    if cfg_manifest.get("artifact_schema") != "rom-cfg-inventory-v2" or cfg_manifest.get("files", {}).get(Path(CFG_V2_PAYLOAD_PATH).name, {}).get("sha256") != CFG_V2_PAYLOAD_SHA256:
        raise ValueError("CFG v2 manifest payload binding changed")
    if cfg_payload.get("schema") != "rom-cfg-inventory-v2" or cfg_payload.get("rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("CFG v2 payload contract changed")
    blocks = cfg_payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("CFG v2 payload blocks missing")
    exact_entries: set[int] = set()
    for block in blocks:
        if not isinstance(block, dict) or block.get("mode") != "thumb":
            continue
        span = block.get("range")
        if not isinstance(span, list) or len(span) != 2 or not all(isinstance(item, int) for item in span):
            raise ValueError("CFG v2 Thumb block range changed")
        start, end = span
        if start < 0 or start >= end or end > len(rom) or start % 2:
            raise ValueError("CFG v2 Thumb block boundary changed")
        offset = start
        decoded_count = 0
        while offset < end:
            decoded = tuple(_engine().disasm(_rom_slice(rom, offset, min(offset + 4, len(rom))), ROM_BASE + offset, count=1))
            if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset or decoded[0].size not in (2, 4) or offset + decoded[0].size > end:
                raise ValueError(f"CFG v2 raw Thumb decode changed at 0x{offset:06X}")
            exact_entries.add(offset)
            offset += decoded[0].size
            decoded_count += 1
        if offset != end or block.get("instruction_count") != decoded_count or block.get("bytes_sha256") != _sha(_rom_slice(rom, start, end)):
            raise ValueError(f"CFG v2 raw block identity changed at 0x{start:06X}")
    if not (set(ENTRY_SPECS) - {0x61086}) <= exact_entries or 0x9C0E0 not in exact_entries:
        raise ValueError("CFG v2 exact Thumb entry set changed")

    inter_manifest = _read_json_contract(root, BOOT_INTERWORK_MANIFEST_PATH, BOOT_INTERWORK_MANIFEST_SHA256, "boot interwork manifest")
    inter_payload = _read_json_contract(root, BOOT_INTERWORK_PAYLOAD_PATH, BOOT_INTERWORK_PAYLOAD_SHA256, "boot interwork payload")
    if inter_manifest.get("artifact_schema") != "rom-boot-interwork-v1" or inter_manifest.get("files", {}).get(Path(BOOT_INTERWORK_PAYLOAD_PATH).name, {}).get("sha256") != BOOT_INTERWORK_PAYLOAD_SHA256:
        raise ValueError("boot interwork manifest payload binding changed")
    if inter_payload.get("schema") != "rom-boot-interwork-v1" or inter_payload.get("rom", {}).get("sha256") != ROM_SHA256:
        raise ValueError("boot interwork payload contract changed")
    expected_raw = _rom_slice(rom, 0x61086, 0x6108A)
    spine = inter_payload.get("producer_chain", {}).get("interwork_spine", [])
    if not any(
        isinstance(item, dict)
        and item.get("kind") == "thumb_bl"
        and item.get("range") == [0x61086, 0x6108A]
        and item.get("sha256") == _sha(expected_raw)
        for item in spine
    ):
        raise ValueError("boot interwork exact 0x61086 entry changed")
    return exact_entries | {0x61086}


def _rom_slice(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError("ROM range is outside the input")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_rom_slice(rom, offset, offset + 2), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_rom_slice(rom, offset, offset + 4), "little")


def _engine() -> Cs:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        _ENGINE.detail = True
        _ENGINE.skipdata = False
    return _ENGINE


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _writes_pc(ins: Any) -> bool:
    for operand in ins.operands:
        if operand.type == arm_const.ARM_OP_REG and operand.reg == arm_const.ARM_REG_PC and operand.access & CS_AC_WRITE:
            return True
    try:
        _, writes = ins.regs_access()
    except (AttributeError, capstone.CsError):
        writes = []
    return arm_const.ARM_REG_PC in writes


def _conditional(ins: Any) -> bool:
    return getattr(ins, "cc", arm_const.ARM_CC_AL) not in (arm_const.ARM_CC_AL, arm_const.ARM_CC_INVALID)


def _valid_thumb(raw: bytes, ins: Any) -> bool:
    if ins.id not in THUMB_IDS:
        return False
    if ins.size == 2:
        return len(raw) >= 2
    if ins.size != 4 or len(raw) < 4:
        return False
    first = int.from_bytes(raw[:2], "little")
    second = int.from_bytes(raw[2:4], "little")
    return ins.id == arm_const.ARM_INS_BL and first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800


def _raw_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
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


def _decode(rom: bytes, offset: int) -> dict[str, Any]:
    base = {"accepted": False, "mode": "thumb", "file_offset": offset}
    if offset < 0 or offset >= len(rom) or offset % 2:
        return {**base, "frontier_reason": "misaligned_or_outside_entry"}
    decoded = tuple(_engine().disasm(rom[offset : offset + 4], ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != ROM_BASE + offset:
        return {**base, "frontier_reason": "decode_failure"}
    ins = decoded[0]
    raw = rom[offset : offset + ins.size]
    if len(raw) != ins.size:
        return {**base, "frontier_reason": "decode_failure"}
    if not _valid_thumb(raw, ins):
        return {**base, "frontier_reason": "unsupported_armv4t_instruction"}
    flow = _raw_flow(raw, offset)
    if ins.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL, arm_const.ARM_INS_BX, arm_const.ARM_INS_SVC) and flow is None:
        return {**base, "frontier_reason": "control_flow_oracle_mismatch"}
    if flow is not None:
        expected = {"unconditional_branch": arm_const.ARM_INS_B, "conditional_branch": arm_const.ARM_INS_B, "call": arm_const.ARM_INS_BL, "return": arm_const.ARM_INS_BX, "indirect_branch": arm_const.ARM_INS_BX, "supervisor_call": arm_const.ARM_INS_SVC}[flow["flow_kind"]]
        if ins.id != expected or ins.size != flow["size"]:
            return {**base, "frontier_reason": "control_flow_oracle_mismatch"}
    conditional = flow["conditional"] if flow is not None else _conditional(ins)
    end = offset + ins.size
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    raw_indirect = False
    if flow is not None and flow["flow_kind"] in {"call", "conditional_branch", "unconditional_branch"}:
        kind = "call_target" if flow["flow_kind"] == "call" else "branch_target"
        target = flow["target_file_offset"]
        if 0 <= target < len(rom) and target % 2 == 0:
            successors.append(_edge(kind, target))
        else:
            frontiers.append({"reason": "direct_target_outside_or_misaligned", "target": {"mode": "thumb", "file_offset": target}})
        if flow["flow_kind"] in {"call", "conditional_branch"} and end < len(rom):
            successors.append(_edge("fallthrough", end))
        flow_kind = flow["flow_kind"]
    elif flow is not None and flow["flow_kind"] == "supervisor_call":
        frontiers.append({"reason": "bios_swi_external", "swi_immediate": flow["swi_immediate"], "target": {"address_space": "bios", "gba_address": "0x00000008"}})
        if end < len(rom):
            successors.append(_edge("fallthrough", end))
        flow_kind = "supervisor_call"
    elif flow is not None and flow["flow_kind"] in {"return", "indirect_branch"}:
        flow_kind = flow["flow_kind"]
        if flow_kind == "indirect_branch":
            raw_indirect = True
            frontiers.append({"reason": "indirect_pc_target"})
    elif _writes_pc(ins):
        flow_kind = "return" if ins.id == arm_const.ARM_INS_POP else "indirect_branch"
        if flow_kind == "indirect_branch":
            raw_indirect = True
            frontiers.append({"reason": "indirect_pc_target"})
    else:
        flow_kind = "linear"
        if end < len(rom):
            successors.append(_edge("fallthrough", end))
    successors.sort(key=lambda item: (_EDGE_ORDER[item["kind"]], item["file_offset"]))
    return {
        **base, "accepted": True, "mode": "thumb", "file_offset": offset, "gba_address": _gba(offset),
        "size": ins.size, "raw_hex": raw.hex(), "bytes_sha256": _sha(raw), "mnemonic": ins.mnemonic,
        "op_str": ins.op_str, "conditional": conditional, "flow_kind": flow_kind,
        "raw_flow_kind": flow["flow_kind"] if flow is not None else None, "raw_indirect_pc": raw_indirect,
        "successors": successors, "frontiers": frontiers,
    }


def _close_returns(rom: bytes, nodes: dict[int, dict[str, Any]]) -> None:
    incoming: dict[int, list[tuple[int, str]]] = {offset: [] for offset in nodes}
    for source, node in nodes.items():
        for edge in node["successors"]:
            if edge["file_offset"] in nodes:
                incoming[edge["file_offset"]].append((source, edge["kind"]))
    for offset, node in nodes.items():
        if node.get("raw_flow_kind") != "indirect_branch" or node.get("mnemonic") != "bx":
            continue
        previous = nodes.get(offset - 2)
        ins = incoming.get(offset, [])
        if previous is None or len(ins) != 1 or ins[0] != (offset - 2, "fallthrough"):
            continue
        if previous.get("flow_kind") != "linear" or previous.get("file_offset", -2) + previous.get("size", 0) != offset:
            continue
        if previous.get("successors") != [_edge("fallthrough", offset)] or node.get("successors"):
            continue
        register = (_u16(rom, offset) >> 3) & 0xF
        if register not in (0, 1):
            continue
        if _u16(rom, previous["file_offset"]) == 0xBC00 | (1 << register):
            node["flow_kind"] = "return"
            node["frontiers"] = []


def _build_unknown(payload: dict[str, Any]) -> bytearray:
    baseline = payload.get("coverage_baseline")
    if not isinstance(baseline, dict):
        raise ValueError("coverage baseline missing")
    expected = {
        "path": COVERAGE_PATH, "sha256": COVERAGE_SHA256, "schema": "rom-byte-coverage-v1",
        "classified_bytes": COVERAGE_CLASSIFIED_COUNT, "unknown_bytes": COVERAGE_UNKNOWN_COUNT,
        "segment_count": COVERAGE_SEGMENT_COUNT, "claim_count": COVERAGE_CLAIM_COUNT,
    }
    for key, value in expected.items():
        if baseline.get(key) != value:
            raise ValueError(f"coverage baseline {key} changed")
    ranges = baseline.get("unknown_ranges")
    if not isinstance(ranges, list) or _compact_sha(ranges) != COVERAGE_UNKNOWN_RANGES_SHA256:
        raise ValueError("coverage unknown range vector changed")
    unknown = bytearray(ROM_SIZE)
    previous = -1
    total = 0
    for value in ranges:
        if not isinstance(value, list) or len(value) != 2 or not all(isinstance(item, int) for item in value):
            raise ValueError("coverage unknown range malformed")
        start, end = value
        if start < 0 or start >= end or end > ROM_SIZE or start < previous:
            raise ValueError("coverage unknown ranges overlap or are unsorted")
        if any(unknown[start:end]):
            raise ValueError("coverage unknown ranges overlap")
        unknown[start:end] = b"\1" * (end - start)
        total += end - start
        previous = end
    if total != COVERAGE_UNKNOWN_COUNT:
        raise ValueError("coverage unknown byte count changed")
    return unknown


def _read_rom(root: Path) -> bytes:
    raw = _safe_file(root, ROM_PATH).read_bytes()
    if len(raw) != ROM_SIZE or _sha(raw) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    return raw


def _handoff(rom: bytes) -> dict[str, Any]:
    if _sha(_rom_slice(rom, *HANDOFF_RANGE)) != HANDOFF_SHA256:
        raise ValueError("raw ARM startup handoff changed")
    if _u32(rom, 0xE4) != 0xE59F100C or _u32(rom, 0xE8) != 0xE1A0E00F or _u32(rom, 0xEC) != 0xE12FFF11:
        raise ValueError("ARM startup handoff opcodes changed")
    pointer = _rom_slice(rom, HANDOFF_LITERAL, HANDOFF_LITERAL + 4)
    if pointer.hex() != HANDOFF_LITERAL_RAW or _u32(rom, HANDOFF_LITERAL) != HANDOFF_POINTER:
        raise ValueError("ARM startup handoff literal changed")
    occurrences = [offset for offset in range(len(rom) - 3) if rom[offset : offset + 4] == pointer]
    if occurrences != [HANDOFF_LITERAL]:
        raise ValueError("ARM startup pointer occurrence denominator changed")
    if ((HANDOFF_POINTER - ROM_BASE) & ~1) != ROOT_OFFSET or not (HANDOFF_POINTER & 1):
        raise ValueError("Thumb handoff mode or root parity changed")
    root = _rom_slice(rom, ROOT_OFFSET, ROOT_OFFSET + 4)
    if root.hex() != ROOT_RAW or _sha(root) != ROOT_SHA256:
        raise ValueError("Thumb handoff root bytes changed")
    if _sha(_rom_slice(rom, *EXCLUDED_PREFIX)) != EXCLUDED_PREFIX_SHA256:
        raise ValueError("excluded handoff prefix changed")
    return {
        "boot_manifest": {"path": BOOT_MANIFEST_PATH, "sha256": BOOT_MANIFEST_SHA256},
        "arm_handoff": {"range": list(HANDOFF_RANGE), "gba_range": [_gba(HANDOFF_RANGE[0]), _gba(HANDOFF_RANGE[1])], "raw_hex": _rom_slice(rom, *HANDOFF_RANGE).hex(), "sha256": HANDOFF_SHA256, "instructions": [{"file_offset": 0xE4, "raw_hex": "0c109fe5", "operation": "ldr_pc_relative", "literal_offset": HANDOFF_LITERAL}, {"file_offset": 0xE8, "raw_hex": "0fe0a0e1", "operation": "mov_lr_pc"}, {"file_offset": 0xEC, "raw_hex": "11ff2fe1", "operation": "bx_r1"}]},
        "literal": {"file_offset": HANDOFF_LITERAL, "gba_address": _gba(HANDOFF_LITERAL), "raw_hex": HANDOFF_LITERAL_RAW, "value": f"0x{HANDOFF_POINTER:08X}", "occurrences": occurrences},
        "root": {"mode": "thumb", "pointer": f"0x{HANDOFF_POINTER:08X}", "file_offset": ROOT_OFFSET, "gba_address": _gba(ROOT_OFFSET), "raw_hex": ROOT_RAW, "sha256": ROOT_SHA256},
        "excluded_prefix": {"range": list(EXCLUDED_PREFIX), "sha256": EXCLUDED_PREFIX_SHA256, "excluded_from_cfg": True},
    }


def _existing_entries(rom: bytes, exact_entries: set[int]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for target, (claim_id, owner_range, owner_class, interior, claim_kind, evidence_path, evidence_sha, selector) in ENTRY_SPECS.items():
        if target not in exact_entries:
            raise ValueError(f"frozen exact entry missing at 0x{target:06X}")
        if _sha(_rom_slice(rom, *owner_range)) != OWNER_BYTES_SHA256[target]:
            raise ValueError("owner byte identity changed")
        result[target] = {
            "target_offset": target, "target_gba_address": _gba(target), "mode": "thumb", "exact_entry_offset": target,
            "target_scheduled": False, "owner_claim_id": claim_id, "owner_range": owner_range,
            "owner_primary_class": owner_class, "owner_claim_kind": claim_kind, "owner_interior_entry": interior,
            "evidence_path": evidence_path, "evidence_sha256": evidence_sha, "evidence_selector": selector,
        }
    return result


def _new_proof(rom: bytes) -> dict[str, Any]:
    source = _rom_slice(rom, NEW_CALLSITE, NEW_CALLSITE + 4)
    if source.hex() != NEW_CALLSITE_RAW or _sha(source) != NEW_CALLSITE_SHA256:
        raise ValueError("0x61624 source BL bytes changed")
    first, second = _u16(rom, NEW_CALLSITE), _u16(rom, NEW_CALLSITE + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("0x61624 source BL encoding changed")
    target = NEW_CALLSITE + 4 + _sign_extend(((first & 0x7FF) << 12) | ((second & 0x7FF) << 1), 23)
    if target != NEW_ENTRY or target % 2:
        raise ValueError("0x61624 target or mode changed")
    entry = _rom_slice(rom, NEW_ENTRY, NEW_ENTRY + 2)
    if entry.hex() != NEW_ENTRY_RAW or _sha(entry) != NEW_ENTRY_SHA256:
        raise ValueError("0x61624 entry bytes changed")
    decoded = _decode(rom, NEW_ENTRY)
    if not decoded.get("accepted") or decoded.get("mnemonic") != "push" or decoded.get("size") != 2:
        raise ValueError("0x61624 first instruction decode changed")
    if _sha(_rom_slice(rom, *NEW_OWNER_RANGE)) != NEW_OWNER_BYTES_SHA256:
        raise ValueError("0x61624 raw owner bytes changed")
    return {
        "entry": {"mode": "thumb", "file_offset": NEW_ENTRY, "gba_address": _gba(NEW_ENTRY), "raw_hex": NEW_ENTRY_RAW, "sha256": NEW_ENTRY_SHA256, "decoded": "push {r4,r5,lr}"},
        "source_call": {"file_offset": NEW_CALLSITE, "gba_address": _gba(NEW_CALLSITE), "raw_hex": NEW_CALLSITE_RAW, "sha256": NEW_CALLSITE_SHA256, "decoded": "bl 0x08061624", "target_offset": NEW_ENTRY, "fallthrough_offset": NEW_CALLSITE + 4},
        "source_and_fallthrough": [NEW_CALLSITE, NEW_CALLSITE + 4], "owner_claim_id": NEW_OWNER_ID, "owner_range": list(NEW_OWNER_RANGE), "owner_primary_class": NEW_OWNER_CLASS,
        "owner_limitation": "owner boundary is not instruction-only; direct BL plus first-instruction decode proves only the exact entry", "target_scheduled": False, "edge_resolution": "opaque_external_entry",
    }


def _traverse(rom: bytes, unknown: bytearray, existing: dict[int, dict[str, Any]]) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    pending = [ROOT_OFFSET]
    scheduled = {ROOT_OFFSET}
    nodes: dict[int, dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        node = _decode(rom, offset)
        if not node.get("accepted") or not all(unknown[offset : offset + node["size"]]):
            raise ValueError(f"reachable Thumb instruction invalid at 0x{offset:06X}")
        nodes[offset] = node
        for edge in node["successors"]:
            target = edge["file_offset"]
            if target in existing or target == NEW_ENTRY:
                if target == NEW_ENTRY:
                    owner = {"owner_claim_id": NEW_OWNER_ID, "owner_range": list(NEW_OWNER_RANGE), "owner_primary_class": NEW_OWNER_CLASS, "owner_interior_entry": False}
                else:
                    owner = existing[target]
                external.append({"source_instruction_offset": offset, "source_gba_address": _gba(offset), "kind": edge["kind"], "mode": "thumb", "target_offset": target, "target_gba_address": _gba(target), "target_scheduled": False, "resolution": "opaque_external_entry", "owner_claim_id": owner["owner_claim_id"], "owner_range": owner["owner_range"], "owner_primary_class": owner["owner_primary_class"], "owner_interior_entry": owner.get("owner_interior_entry", False)})
                continue
            candidate = _decode(rom, target)
            if not candidate.get("accepted") or not all(unknown[target : target + candidate["size"]]):
                raise ValueError(f"successor invalid at 0x{target:06X}")
            if target not in scheduled:
                heapq.heappush(pending, target)
                scheduled.add(target)
    _close_returns(rom, nodes)
    if len(nodes) != 583 or sum(item["size"] for item in nodes.values()) != 1226 or len(external) != 14:
        raise ValueError("Thumb traversal denominator changed")
    rebuilt_targets = {item["source_instruction_offset"]: item["target_offset"] for item in external}
    if len(rebuilt_targets) != len(external) or rebuilt_targets != EXTERNAL_TARGETS:
        raise ValueError("complete external source-target contract changed")
    return nodes, external


def _blocks(rom: bytes, nodes: dict[int, dict[str, Any]], external: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
        blocks.append({"id": block_by_offset[start], "mode": "thumb", "range": [start, end], "gba_range": [_gba(start), _gba(end)], "instruction_count": len(members), "bytes_sha256": _sha(_rom_slice(rom, start, end)), "terminator": {"file_offset": members[-1], "size": last["size"], "raw_hex": last["raw_hex"], "mnemonic": last["mnemonic"], "op_str": last["op_str"], "flow_kind": last["flow_kind"], "conditional": last["conditional"]}, "successors": []})
    if len(block_by_offset) != len(nodes) or len(blocks) != 125:
        raise ValueError("Thumb block denominator changed")
    ext_by_source: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for edge in external:
        ext_by_source[edge["source_instruction_offset"]].append(edge)
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["file_offset"]
        for edge in nodes[source]["successors"]:
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
    if len(edges) != 178 or sum(item["resolution"] == "internal" for item in edges) != 164:
        raise ValueError("edge denominator changed")
    return blocks, edges


def _literals(rom: bytes, nodes: dict[int, dict[str, Any]], unknown: bytearray) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for offset, node in sorted(nodes.items()):
        if node["size"] != 2 or _u16(rom, offset) & 0xF800 != 0x4800:
            continue
        literal = ((offset + 4) & ~3) + (_u16(rom, offset) & 0xFF) * 4
        value = _u32(rom, literal)
        normalized = value & ~1 if literal == 0x099E00 else value
        result.append({"instruction_offset": offset, "load_offset": offset, "instruction_gba_address": _gba(offset), "literal_offset": literal, "literal_gba_address": _gba(literal), "raw_value": f"0x{value:08X}", "normalized_value": f"0x{normalized:08X}", "value": f"0x{value:08X}", "raw_hex": _rom_slice(rom, literal, literal + 4).hex(), "address_kind": "iwram_thumb" if literal == 0x099E00 else "raw_word"})
    if len(result) != 77 or len({item["literal_offset"] for item in result}) != 74:
        raise ValueError("literal denominator changed")
    for item in result:
        if item["literal_offset"] % 4 or not all(unknown[item["literal_offset"] : item["literal_offset"] + 4]):
            raise ValueError("literal word is not current unknown")
    result.sort(key=lambda item: (item["literal_offset"], item["instruction_offset"]))
    return result


def _ranges(intervals: list[tuple[int, int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(set(intervals)):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _promotion(rom: bytes, nodes: dict[int, dict[str, Any]], literals: list[dict[str, Any]], unknown: bytearray) -> tuple[dict[str, Any], list[dict[str, Any]], list[list[int]], list[list[int]], list[list[int]], bytes]:
    code = _ranges([(offset, offset + node["size"]) for offset, node in nodes.items()])
    literal = _ranges([(item["literal_offset"], item["literal_offset"] + 4) for item in literals])
    union = _ranges([(start, end) for start, end in code + literal])
    if (code, literal, union) != (CODE_RANGES, LITERAL_RANGES, UNION_RANGES):
        raise ValueError("promotion ranges changed")
    if any(not all(unknown[start:end]) for start, end in union):
        raise ValueError("promotion includes known bytes")
    if any(start < EXCLUDED_PREFIX[1] and end > EXCLUDED_PREFIX[0] for start, end in union):
        raise ValueError("promotion includes excluded bytes")
    bundle = b"".join(_rom_slice(rom, start, end) for start, end in union)
    if _sha(bundle) != UNION_BYTES_SHA256 or _compact_sha(union) != UNION_RANGE_SHA256 or len(bundle) != 1522:
        raise ValueError("promotion binary identity changed")
    records = []
    for kind, ranges in (("code", code), ("literal", literal)):
        for index, (start, end) in enumerate(ranges):
            records.append({"id": f"{kind}-{index:02d}-{start:06x}", "kind": kind, "range": [start, end], "size": end - start, "sha256": _sha(_rom_slice(rom, start, end)), "baseline_unknown_only": True})
    promotion = {"code_range_count": 27, "code_bytes": 1226, "literal_range_count": 22, "literal_bytes": 296, "union_range_count": 25, "union_bytes": 1522, "union_range_vector_sha256": UNION_RANGE_SHA256, "union_bytes_sha256": UNION_BYTES_SHA256, "current_known_overlap_bytes": 0, "wide_envelope": [ROOT_OFFSET, 0x09C098], "wide_envelope_is_claim": False, "future_coverage_claim_projection": {"code_claim_count": 27, "literal_claim_count": 22, "semantically_merged_union_claim_count": 0}}
    return promotion, records, code, literal, union, bundle


def _implementation(root: Path) -> dict[str, dict[str, str]]:
    values = {
        "exporter": "tools/export_rom_boot_thumb_handoff_cfg.py",
        "verifier": "tools/verify_rom_boot_thumb_handoff_cfg.py",
        "test": "tests/test_export_rom_boot_thumb_handoff_cfg.py",
    }
    return {role: {"path": path, "sha256": _sha(_safe_file(root, path).read_bytes())} for role, path in values.items()}


def _expected_payload(root: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    rom = _read_rom(root)
    exact_entries = _load_frozen_inputs(root, rom)
    unknown = _build_unknown(payload)
    handoff = _handoff(rom)
    existing = _existing_entries(rom, exact_entries)
    proof = _new_proof(rom)
    nodes, external = _traverse(rom, unknown, existing)
    blocks, edges = _blocks(rom, nodes, external)
    literals = _literals(rom, nodes, unknown)
    promotion, promotion_records, code, literal, union, bundle = _promotion(rom, nodes, literals, unknown)
    frontiers = [{"instruction_offset": offset, "gba_address": _gba(offset), "raw_hex": node["raw_hex"], **frontier} for offset, node in sorted(nodes.items()) for frontier in node["frontiers"] if frontier.get("reason") == "indirect_pc_target"]
    raw_indirect = [{"instruction_offset": offset, "gba_address": _gba(offset), "raw_hex": node["raw_hex"], "flow_kind": node["flow_kind"], "resolved_as_return": node["flow_kind"] == "return"} for offset, node in sorted(nodes.items()) if node.get("raw_indirect_pc")]
    summary = {"instruction_count": len(nodes), "instruction_bytes": sum(node["size"] for node in nodes.values()), "block_count": len(blocks), "internal_edge_count": sum(edge["resolution"] == "internal" for edge in edges), "external_edge_count": len(external), "external_target_count": len({edge["target_offset"] for edge in external}), "literal_ref_count": len(literals), "literal_word_count": len({item["literal_offset"] for item in literals}), "literal_bytes": len({item["literal_offset"] for item in literals}) * 4, "return_count": sum(node["flow_kind"] == "return" for node in nodes.values()), "raw_indirect_pc_count": len(raw_indirect), "frontier_count": len(frontiers), "budget_exhausted": False}
    if summary != EXPECTED_SUMMARY:
        raise ValueError("recomputed summary changed")
    claims = [{"id": f"thumb-code-{index:02d}-{start:06x}", "range": [start, end], "size": end - start, "semantic_class": "armv4t_cfg_handoff_thumb_code", "sha256": _sha(_rom_slice(rom, start, end)), "baseline_unknown_only": True} for index, (start, end) in enumerate(code)]
    claims.extend({"id": f"thumb-literal-{index:02d}-{start:06x}", "range": [start, end], "size": end - start, "semantic_class": "thumb_pc_relative_literal", "sha256": _sha(_rom_slice(rom, start, end)), "baseline_unknown_only": True} for index, (start, end) in enumerate(literal))
    expected_inputs = {"cfg_seeds_payload": {"path": CFG_SEEDS_PATH, "sha256": CFG_SEEDS_SHA256}, "cfg_v2_manifest": {"path": CFG_V2_MANIFEST_PATH, "sha256": CFG_V2_MANIFEST_SHA256}, "cfg_v2_payload": {"path": CFG_V2_PAYLOAD_PATH, "sha256": CFG_V2_PAYLOAD_SHA256}, "boot_interwork_manifest": {"path": BOOT_INTERWORK_MANIFEST_PATH, "sha256": BOOT_INTERWORK_MANIFEST_SHA256}, "boot_interwork_payload": {"path": BOOT_INTERWORK_PAYLOAD_PATH, "sha256": BOOT_INTERWORK_PAYLOAD_SHA256}}
    expected = {
        "schema": SCHEMA, "rom": {"path": ROM_PATH, "size": ROM_SIZE, "sha256": ROM_SHA256}, "handoff": handoff,
        "coverage_baseline": payload["coverage_baseline"], "frozen_inputs": expected_inputs,
        "existing_entry_claims": {f"0x{ROM_BASE + target:08X}": value for target, value in sorted(existing.items())}, "entry_proofs": {f"0x{ROM_BASE + NEW_ENTRY:08X}": proof},
        "instructions": [nodes[offset] for offset in sorted(nodes)], "blocks": blocks, "edges": edges,
        "external_edges": [edge for edge in edges if edge["resolution"] == "opaque_external_entry"], "literal_bindings": literals, "frontiers": frontiers, "raw_indirect_pc_sites": raw_indirect,
        "code_ranges": code, "literal_ranges": literal, "union_ranges": union, "promotion_ranges": promotion_records, "coverage_claims": claims, "promotion": promotion,
        "summary": summary, "scope": SCOPE, "limitations": LIMITATIONS, "implementation": _implementation(root),
    }
    # The baseline is carried by the artifact so verification remains possible
    # when a later integration replaces or removes the canonical coverage file.
    return expected, bundle


def _canonical_command(kind: str) -> list[str]:
    script = "tools/verify_rom_boot_thumb_handoff_cfg.py" if kind == "verifier" else "tools/export_rom_boot_thumb_handoff_cfg.py"
    flag = "--artifact-dir" if kind == "verifier" else "--output-dir"
    return ["python3", "-I", "-S", script, "--root", ".", flag, FINAL_RELATIVE]


def _stable_report(payload: dict[str, Any]) -> dict[str, Any]:
    return {"schema": VERIFY_SCHEMA, "verified": True, "errors": [], "summary": payload["summary"], "promotion": payload["promotion"]}


def _artifact_dir(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor /= part
        if cursor.is_symlink():
            raise ValueError("artifact path contains a symlink component")
    resolved = requested.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("artifact path is not a directory")
    for item in resolved.iterdir():
        if item.is_symlink() or not item.is_file():
            raise ValueError("artifact contains a symlink or non-file")
    if {item.name for item in resolved.iterdir()} != {PAYLOAD_NAME, BUNDLE_NAME, MANIFEST_NAME}:
        raise ValueError("artifact contains foreign files")
    return resolved


def _load_json(path: Path, label: str) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} is not JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    if raw != _canonical(value):
        raise ValueError(f"{label} JSON bytes are not canonical")
    return value, raw


def verify_artifact(root: Path, artifact: Path, *, allow_candidate: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = _root_path(root)
        directory = _artifact_dir(Path(artifact))
        manifest, manifest_raw = _load_json(directory / MANIFEST_NAME, "manifest")
        payload, payload_raw = _load_json(directory / PAYLOAD_NAME, "payload")
        bundle = (directory / BUNDLE_NAME).read_bytes()
        files = manifest.get("files")
        expected_files = {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}, BUNDLE_NAME: {"size": len(bundle), "sha256": _sha(bundle)}}
        if files != expected_files:
            raise ValueError("manifest file receipt changed")
        allowed_statuses = {"accepted", "candidate"} if allow_candidate else {"accepted"}
        if manifest.get("schema") != PROMOTION_SCHEMA or manifest.get("artifact_schema") != SCHEMA or manifest.get("artifact_status") not in allowed_statuses:
            raise ValueError("manifest schema or status changed")
        expected_payload, expected_bundle = _expected_payload(root, payload)
        # Rebuilt arrays are compared field-for-field; only the implementation
        # hashes are dynamic and are already rebuilt from the current source.
        if payload != expected_payload:
            differing = next((key for key in expected_payload if payload.get(key) != expected_payload[key]), "payload-shape")
            raise ValueError(f"payload {differing} changed")
        if bundle != expected_bundle:
            raise ValueError("packed promotion binary changed")
        if manifest.get("rom") != payload["rom"] or manifest.get("coverage_baseline") != payload["coverage_baseline"] or manifest.get("handoff") != payload["handoff"] or manifest.get("promotion") != payload["promotion"] or manifest.get("summary") != payload["summary"] or manifest.get("implementation") != payload["implementation"] or manifest.get("scope") != payload["scope"] or manifest.get("limitations") != payload["limitations"]:
            raise ValueError("manifest projection changed")
        expected_producer = {"command": _canonical_command("producer"), "implementation": payload["implementation"]}
        if manifest.get("producer") != expected_producer:
            raise ValueError("producer receipt changed")
        expected_command = _canonical_command("verifier")
        status = manifest["artifact_status"]
        report = None if status == "candidate" else _stable_report(payload)
        expected_verification = {"schema": VERIFY_SCHEMA, "command": expected_command, "exit_code": None if report is None else 0, "report": report, "verifier_sha256": payload["implementation"]["verifier"]["sha256"]}
        if manifest.get("verifier") != expected_verification or manifest.get("verification") != expected_verification:
            raise ValueError("verifier receipt changed")
        return _stable_report(payload)
    except Exception as error:
        errors.append(str(error))
        return {"schema": VERIFY_SCHEMA, "verified": False, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", "--artifact", dest="artifact", type=Path, required=True)
    parser.add_argument("--allow-candidate", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact, allow_candidate=args.allow_candidate)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if report.get("verified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
