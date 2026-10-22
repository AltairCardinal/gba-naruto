#!/usr/bin/env python3
"""Independently verify the bounded ARMv4T CFG artifact and graph closure."""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import heapq
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import capstone
from capstone import (
    CS_AC_WRITE,
    CS_ARCH_ARM,
    CS_MODE_ARM,
    CS_MODE_THUMB,
    Cs,
)
from capstone import arm_const

from tools.verify_rom_cfg_seeds import verify_rom_cfg_seeds


SCHEMA = "rom-cfg-inventory-v2"
VERIFY_SCHEMA = "rom-cfg-inventory-verification-v2"
ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "rom-cfg-inventory.json"
SEED_ARTIFACT = Path("artifacts/rom-cfg-seeds-v1")
SEED_PAYLOAD_NAME = "rom-cfg-seeds.json"
SEED_PAYLOAD_SHA256 = (
    "53960ae8e460b862bbc52d447290d988ed8a496417ccf08a810041384df1b05c"
)
SEED_PAYLOAD_SIZE = 277_537
SEED_MANIFEST_SHA256 = (
    "dafb79db7439ec73360eb069d2e8c32c9bf610116d5adf458617dd5bfac08810"
)
SEED_DENOMINATOR_SHA256 = (
    "f461fda5659657f3dd3dc0690966edb854e26dcc09e868cd8f62e8cbdae62672"
)
DISPATCH_SLOT_DENOMINATOR_SHA256 = (
    "68d94098ca8babc6706b4206e4b549b863ddfd1bd90d0a605a3be791df76a71b"
)
SEED_VERIFIER = Path("tools/verify_rom_cfg_seeds.py")
SEED_VERIFIER_SHA256 = (
    "9d566d020087e07821ca08867572ac9137997fdba6b903e8f2c7a9eba162c52b"
)
MAX_INSTRUCTION_COUNT = 1_000_000
MAX_BLOCK_INSTRUCTION_COUNT = 256

DECODER_FILES = {
    "tools/_vendor/capstone/__init__.py": (
        "17a8db1bfe9cb52a97cc89d4ddc9b3246b5d0ddd330fb592ea17060554032f8e"
    ),
    "tools/_vendor/capstone/arm.py": (
        "bd8e7a96074481a55c77192f6202f92a52e8c9022aa68c2de5736edf0e04fff0"
    ),
    "tools/_vendor/capstone/arm_const.py": (
        "ca87ac6edbf031e1eff66531743dc6f2e4ba8ea63d532da401a5d1fa28653192"
    ),
    "tools/_vendor/capstone/lib/libcapstone.dylib": (
        "00f3876991807d87ef26b6564609dd2e2c46616c476336498f33a8c8501fb35f"
    ),
}

_CLASSIC_COMMON_NAMES = (
    "ARM_INS_ADC",
    "ARM_INS_ADD",
    "ARM_INS_ADR",
    "ARM_INS_AND",
    "ARM_INS_ASR",
    "ARM_INS_B",
    "ARM_INS_BIC",
    "ARM_INS_BL",
    "ARM_INS_BX",
    "ARM_INS_CMN",
    "ARM_INS_CMP",
    "ARM_INS_EOR",
    "ARM_INS_LDM",
    "ARM_INS_LDMDA",
    "ARM_INS_LDMDB",
    "ARM_INS_LDMIB",
    "ARM_INS_LDR",
    "ARM_INS_LDRB",
    "ARM_INS_LDRBT",
    "ARM_INS_LDRH",
    "ARM_INS_LDRSB",
    "ARM_INS_LDRSH",
    "ARM_INS_LDRT",
    "ARM_INS_LSL",
    "ARM_INS_LSR",
    "ARM_INS_MLA",
    "ARM_INS_MOV",
    "ARM_INS_MOVS",
    "ARM_INS_MRS",
    "ARM_INS_MSR",
    "ARM_INS_MUL",
    "ARM_INS_MVN",
    "ARM_INS_NEG",
    "ARM_INS_NOP",
    "ARM_INS_ORR",
    "ARM_INS_POP",
    "ARM_INS_PUSH",
    "ARM_INS_ROR",
    "ARM_INS_RRX",
    "ARM_INS_RSB",
    "ARM_INS_RSC",
    "ARM_INS_SBC",
    "ARM_INS_SMLAL",
    "ARM_INS_SMULL",
    "ARM_INS_STM",
    "ARM_INS_STMDA",
    "ARM_INS_STMDB",
    "ARM_INS_STMIB",
    "ARM_INS_STR",
    "ARM_INS_STRB",
    "ARM_INS_STRBT",
    "ARM_INS_STRH",
    "ARM_INS_STRT",
    "ARM_INS_SUB",
    "ARM_INS_SUBS",
    "ARM_INS_SVC",
    "ARM_INS_SWP",
    "ARM_INS_SWPB",
    "ARM_INS_TEQ",
    "ARM_INS_TST",
    "ARM_INS_UMLAL",
    "ARM_INS_UMULL",
)
ARMV4T_INSTRUCTION_IDS = frozenset(
    getattr(arm_const, name)
    for name in _CLASSIC_COMMON_NAMES
    if hasattr(arm_const, name)
)

EXPECTED_SEED_SUMMARY = {
    "dispatch_source_count": 23,
    "inline_dispatch_source_count": 18,
    "canonical_dispatch_source_count": 5,
    "raw_dispatch_slot_count": 829,
    "unique_dispatch_handler_count": 261,
    "root_seed_count": 263,
    "arm_root_seed_count": 2,
    "thumb_root_seed_count": 261,
}
EXPECTED_SEED_SCOPE = {
    "enumerated_proven_dispatch_root_denominator_complete": True,
    "global_dispatch_source_denominator_complete": False,
    "global_function_entry_denominator_complete": False,
    "independent_source_discovery_performed": False,
    "unbound_pointer_pools_excluded": True,
    "cfg_traversal_performed": False,
}
EXPECTED_EXCLUDED_SEED_CLASSES = [
    "unbound_thumb_code_pointer_pool",
    "map_sprite_callback_pointer_pair",
    "unclassified_code_handler_pointer_table",
    "untyped_resource_or_data_pointer_tables",
]
SCOPE = {
    "all_fixed_seed_roots_traversed": True,
    "armv4t_instruction_set_enforced": True,
    "bounded_single_instruction_decode": True,
    "cfg_traversal_performed": True,
    "global_dispatch_source_denominator_complete": False,
    "global_function_entry_denominator_complete": False,
    "indirect_target_resolution_complete": False,
    "independent_source_discovery_performed": False,
    "reachable_instruction_bytes_only": True,
    "runtime_reachability_complete": False,
    "unbound_pointer_pools_excluded": True,
}
LIMITATIONS = [
    "Only the fixed proven seed set is traversed; this is not a global function-entry or dispatch-source census.",
    "Indirect PC targets remain explicit frontiers and are not guessed.",
    "Capstone decoding is constrained by an explicit conservative ARMv4T instruction allowlist.",
    "Static CFG reachability does not prove natural gameplay or runtime reachability.",
]

_MODE_ORDER = {"arm": 0, "thumb": 1}
_EDGE_ORDER = {"branch_target": 0, "call_target": 1, "fallthrough": 2}
_ENGINES: dict[str, Cs] = {}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _canonical_sha(value: object) -> str:
    return _sha(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def _safe_file(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"CFG verifier input escapes repository: {relative}") from error
    if resolved != candidate.absolute() or not resolved.is_file():
        raise ValueError(f"CFG verifier input is missing or uses a symlink: {relative}")
    return resolved


def _engine(mode: str) -> Cs:
    if mode not in _MODE_ORDER:
        raise ValueError(f"unsupported CFG mode: {mode}")
    if mode not in _ENGINES:
        engine = Cs(CS_ARCH_ARM, CS_MODE_ARM if mode == "arm" else CS_MODE_THUMB)
        engine.detail = True
        engine.skipdata = False
        _ENGINES[mode] = engine
    return _ENGINES[mode]


def _is_conditional(instruction: Any) -> bool:
    condition = getattr(instruction, "cc", arm_const.ARM_CC_AL)
    return condition not in (arm_const.ARM_CC_AL, arm_const.ARM_CC_INVALID)


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


def _is_return(instruction: Any) -> bool:
    operands = instruction.operands
    if instruction.id == arm_const.ARM_INS_BX:
        return (
            len(operands) == 1
            and operands[0].type == arm_const.ARM_OP_REG
            and operands[0].reg == arm_const.ARM_REG_LR
        )
    if instruction.id in (arm_const.ARM_INS_MOV, arm_const.ARM_INS_MOVS):
        return (
            len(operands) >= 2
            and operands[0].type == arm_const.ARM_OP_REG
            and operands[0].reg == arm_const.ARM_REG_PC
            and operands[1].type == arm_const.ARM_OP_REG
            and operands[1].reg == arm_const.ARM_REG_LR
        )
    return instruction.id == arm_const.ARM_INS_POP and _writes_pc(instruction)


def _valid_armv4t(mode: str, raw: bytes, instruction: Any) -> bool:
    if instruction.id not in ARMV4T_INSTRUCTION_IDS:
        return False
    if mode == "arm":
        return (
            len(raw) == 4
            and instruction.size == 4
            and (int.from_bytes(raw, "little") >> 28) != 0xF
        )
    if instruction.size == 2:
        return len(raw) >= 2
    if instruction.size != 4 or len(raw) < 4:
        return False
    first = int.from_bytes(raw[:2], "little")
    second = int.from_bytes(raw[2:4], "little")
    return (
        instruction.id == arm_const.ARM_INS_BL
        and first & 0xF800 == 0xF000
        and second & 0xF800 == 0xF800
    )


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _raw_control_flow(
    mode: str, raw: bytes, offset: int
) -> dict[str, Any] | None:
    """Decode ARMv4T control flow directly from instruction bits.

    This intentionally does not use Capstone metadata.  The verifier keeps
    Capstone as an instruction-boundary/allowlist oracle, while branch, BX and
    SVC semantics come from this independent raw-encoding oracle.
    """

    if mode == "arm":
        if len(raw) != 4:
            return None
        word = int.from_bytes(raw, "little")
        condition = word >> 28
        if condition == 0xF:
            return None
        conditional = condition != 0xE
        if (word >> 25) & 0x7 == 0b101:
            link = bool(word & (1 << 24))
            displacement = _sign_extend((word & 0x00FFFFFF) << 2, 26)
            return {
                "flow_kind": (
                    "call"
                    if link
                    else "conditional_branch"
                    if conditional
                    else "unconditional_branch"
                ),
                "size": 4,
                "conditional": conditional,
                "target_mode": "arm",
                "target_file_offset": offset + 8 + displacement,
            }
        if word & 0x0FFFFFF0 == 0x012FFF10:
            register = word & 0xF
            return {
                "flow_kind": "return" if register == 14 else "indirect_branch",
                "size": 4,
                "conditional": conditional,
                "register": register,
            }
        if word & 0x0F000000 == 0x0F000000:
            return {
                "flow_kind": "supervisor_call",
                "size": 4,
                "conditional": conditional,
                "swi_immediate": word & 0x00FFFFFF,
                "external_target": {
                    "address_space": "bios",
                    "gba_address": "0x00000008",
                },
            }
        return None

    if mode != "thumb" or len(raw) not in (2, 4):
        return None
    first = int.from_bytes(raw[:2], "little")
    if len(raw) == 4:
        second = int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {
                "flow_kind": "call",
                "size": 4,
                "conditional": False,
                "target_mode": "thumb",
                "target_file_offset": offset + 4 + _sign_extend(encoded, 23),
            }
    if first & 0xFF00 == 0xDF00:
        return {
            "flow_kind": "supervisor_call",
            "size": 2,
            "conditional": False,
            "swi_immediate": first & 0xFF,
            "external_target": {
                "address_space": "bios",
                "gba_address": "0x00000008",
            },
        }
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        displacement = _sign_extend((first & 0xFF) << 1, 9)
        return {
            "flow_kind": "conditional_branch",
            "size": 2,
            "conditional": True,
            "target_mode": "thumb",
            "target_file_offset": offset + 4 + displacement,
        }
    if first & 0xF800 == 0xE000:
        displacement = _sign_extend((first & 0x07FF) << 1, 12)
        return {
            "flow_kind": "unconditional_branch",
            "size": 2,
            "conditional": False,
            "target_mode": "thumb",
            "target_file_offset": offset + 4 + displacement,
        }
    if first & 0xFF87 == 0x4700:
        register = (first >> 3) & 0xF
        return {
            "flow_kind": "return" if register == 14 else "indirect_branch",
            "size": 2,
            "conditional": False,
            "register": register,
        }
    return None


def _edge(kind: str, mode: str, offset: int) -> dict[str, Any]:
    return {"kind": kind, "mode": mode, "file_offset": offset}


def _direct_target(
    rom_size: int, mode: str, target_address: int, kind: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    offset = target_address - ROM_BASE
    alignment = 4 if mode == "arm" else 2
    if offset < 0 or offset >= rom_size:
        return None, {
            "reason": "direct_target_outside_rom",
            "target": {"mode": mode, "file_offset": offset},
        }
    if offset % alignment:
        return None, {
            "reason": "misaligned_direct_target",
            "target": {"mode": mode, "file_offset": offset},
        }
    return _edge(kind, mode, offset), None


def _linear_target(
    rom_size: int, mode: str, end: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if end >= rom_size:
        return None, {
            "reason": "fallthrough_outside_rom",
            "target": {"mode": mode, "file_offset": end},
        }
    return _edge("fallthrough", mode, end), None


def _decode(rom: bytes, offset: int, mode: str) -> dict[str, Any]:
    alignment = 4 if mode == "arm" else 2
    base = {"accepted": False, "mode": mode, "file_offset": offset}
    if offset < 0 or offset >= len(rom) or offset % alignment:
        return {**base, "frontier_reason": "misaligned_or_outside_entry"}
    instructions = tuple(
        _engine(mode).disasm(rom[offset : offset + 4], ROM_BASE + offset, count=1)
    )
    if len(instructions) != 1 or instructions[0].address != ROM_BASE + offset:
        return {**base, "frontier_reason": "decode_failure"}
    instruction = instructions[0]
    raw = rom[offset : offset + instruction.size]
    if len(raw) != instruction.size:
        return {**base, "frontier_reason": "decode_failure"}
    if not _valid_armv4t(mode, raw, instruction):
        return {**base, "frontier_reason": "unsupported_armv4t_instruction"}
    raw_flow = _raw_control_flow(mode, raw, offset)
    capstone_control_flow = instruction.id in (
        arm_const.ARM_INS_B,
        arm_const.ARM_INS_BL,
        arm_const.ARM_INS_BX,
        arm_const.ARM_INS_SVC,
    )
    if capstone_control_flow and raw_flow is None:
        return {**base, "frontier_reason": "control_flow_oracle_mismatch"}
    if raw_flow is not None:
        expected_ids = {
            "unconditional_branch": {arm_const.ARM_INS_B},
            "conditional_branch": {arm_const.ARM_INS_B},
            "call": {arm_const.ARM_INS_BL},
            "return": {arm_const.ARM_INS_BX},
            "indirect_branch": {arm_const.ARM_INS_BX},
            "supervisor_call": {arm_const.ARM_INS_SVC},
        }
        if (
            instruction.id not in expected_ids[raw_flow["flow_kind"]]
            or instruction.size != raw_flow["size"]
        ):
            return {**base, "frontier_reason": "control_flow_oracle_mismatch"}
    conditional = (
        raw_flow["conditional"] if raw_flow is not None else _is_conditional(instruction)
    )
    end = offset + instruction.size
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    if raw_flow is not None and raw_flow["flow_kind"] in (
        "unconditional_branch",
        "conditional_branch",
        "call",
    ):
        flow_kind = raw_flow["flow_kind"]
        edge_kind = "call_target" if flow_kind == "call" else "branch_target"
        target, frontier = _direct_target(
            len(rom),
            raw_flow["target_mode"],
            ROM_BASE + raw_flow["target_file_offset"],
            edge_kind,
        )
        if target is not None:
            successors.append(target)
        if frontier is not None:
            frontiers.append(frontier)
        if flow_kind in ("call", "conditional_branch"):
            target, frontier = _linear_target(len(rom), mode, end)
            if target is not None:
                successors.append(target)
            if frontier is not None:
                frontiers.append(frontier)
    elif raw_flow is not None and raw_flow["flow_kind"] == "supervisor_call":
        flow_kind = "supervisor_call"
        frontiers.append(
            {
                "reason": "bios_swi_external",
                "swi_immediate": raw_flow["swi_immediate"],
                "target": raw_flow["external_target"],
            }
        )
        target, frontier = _linear_target(len(rom), mode, end)
        if target is not None:
            successors.append(target)
        if frontier is not None:
            frontiers.append(frontier)
    elif raw_flow is not None and raw_flow["flow_kind"] in (
        "return",
        "indirect_branch",
    ):
        flow_kind = raw_flow["flow_kind"]
        returning = flow_kind == "return"
        if not returning:
            frontiers.append({"reason": "indirect_pc_target"})
        if conditional:
            flow_kind = f"conditional_{flow_kind}"
            target, frontier = _linear_target(len(rom), mode, end)
            if target is not None:
                successors.append(target)
            if frontier is not None:
                frontiers.append(frontier)
    elif _writes_pc(instruction):
        returning = _is_return(instruction)
        flow_kind = "return" if returning else "indirect_branch"
        if not returning:
            frontiers.append({"reason": "indirect_pc_target"})
        if conditional:
            flow_kind = f"conditional_{flow_kind}"
            target, frontier = _linear_target(len(rom), mode, end)
            if target is not None:
                successors.append(target)
            if frontier is not None:
                frontiers.append(frontier)
    else:
        flow_kind = "linear"
        target, frontier = _linear_target(len(rom), mode, end)
        if target is not None:
            successors.append(target)
        if frontier is not None:
            frontiers.append(frontier)
    successors.sort(
        key=lambda item: (
            _EDGE_ORDER[item["kind"]],
            _MODE_ORDER[item["mode"]],
            item["file_offset"],
        )
    )
    return {
        **base,
        "accepted": True,
        "size": instruction.size,
        "bytes_sha256": _sha(raw),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "conditional": conditional,
        "flow_kind": flow_kind,
        "successors": successors,
        "frontiers": frontiers,
    }


def _rebuild_instruction_entries(
    rom: bytes, seeds: list[dict[str, Any]]
) -> dict[tuple[str, int], dict[str, Any]]:
    """Independently rebuild the accepted entry closure from all fixed roots."""

    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for seed in seeds:
        mode = seed.get("mode")
        offset = seed.get("file_offset")
        if mode not in _MODE_ORDER or not isinstance(offset, int):
            raise ValueError("CFG seed is invalid for independent worklist traversal")
        item = (mode, offset)
        if item not in scheduled:
            heapq.heappush(pending, (offset, _MODE_ORDER[mode], mode))
            scheduled.add(item)

    entries: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: set[tuple[str, int]] = set()
    scheduled_limit = len(scheduled) + 2 * MAX_INSTRUCTION_COUNT
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in entries or item in rejected:
            continue
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            rejected.add(item)
            continue
        if len(entries) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("CFG independent instruction budget exhausted")
        entries[item] = decoded
        for edge in decoded["successors"]:
            target_mode = edge.get("mode")
            target_offset = edge.get("file_offset")
            alignment = 4 if target_mode == "arm" else 2
            if (
                target_mode not in _MODE_ORDER
                or not isinstance(target_offset, int)
                or target_offset < 0
                or target_offset >= len(rom)
                or target_offset % alignment
            ):
                raise ValueError("CFG independent worklist received an invalid successor")
            target = (target_mode, target_offset)
            if target not in scheduled:
                if len(scheduled) >= scheduled_limit:
                    raise ValueError("CFG independent scheduled-entry budget exhausted")
                heapq.heappush(
                    pending,
                    (target_offset, _MODE_ORDER[target_mode], target_mode),
                )
                scheduled.add(target)
    return entries


def _decoder_identity(root: Path) -> dict[str, Any]:
    actual = {}
    for relative, expected in DECODER_FILES.items():
        digest = _sha(_safe_file(root, relative).read_bytes())
        if digest != expected:
            raise ValueError(f"CFG decoder dependency SHA-256 changed: {relative}")
        actual[relative] = digest
    if capstone.__version__ != "5.0.7" or capstone.cs_version()[:2] != (5, 0):
        raise ValueError("vendored Capstone version changed")
    return {
        "architecture": "ARM7TDMI / ARMv4T",
        "backend": "vendored-capstone",
        "version": capstone.__version__,
        "detail": True,
        "skipdata": False,
        "decode_granularity": "one instruction, at most four input bytes",
        "files": actual,
    }


def _seed_contract(root: Path, rom: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = _safe_file(root, SEED_ARTIFACT / "manifest.json")
    payload_path = _safe_file(root, SEED_ARTIFACT / SEED_PAYLOAD_NAME)
    verifier_path = _safe_file(root, SEED_VERIFIER)
    manifest_raw = manifest_path.read_bytes()
    payload_raw = payload_path.read_bytes()
    if _sha(manifest_raw) != SEED_MANIFEST_SHA256:
        raise ValueError("CFG seed manifest SHA-256 changed")
    if len(payload_raw) != SEED_PAYLOAD_SIZE or _sha(payload_raw) != SEED_PAYLOAD_SHA256:
        raise ValueError("CFG seed payload identity changed")
    if _sha(verifier_path.read_bytes()) != SEED_VERIFIER_SHA256:
        raise ValueError("CFG seed verifier SHA-256 changed")
    report = verify_rom_cfg_seeds(root, root / SEED_ARTIFACT)
    if not report.get("verified") or report.get("root_seed_count") != 263:
        raise ValueError(f"CFG seed independent verification failed: {report}")
    manifest = json.loads(manifest_raw)
    payload = json.loads(payload_raw)
    if (
        payload.get("schema") != "rom-cfg-seeds-v1"
        or payload.get("rom")
        != {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        or payload.get("summary") != EXPECTED_SEED_SUMMARY
        or payload.get("seed_denominator_sha256") != SEED_DENOMINATOR_SHA256
        or payload.get("dispatch_slot_denominator_sha256")
        != DISPATCH_SLOT_DENOMINATOR_SHA256
        or payload.get("scope") != EXPECTED_SEED_SCOPE
        or payload.get("excluded_seed_classes") != EXPECTED_EXCLUDED_SEED_CLASSES
    ):
        raise ValueError("CFG seed contract changed")
    return payload, manifest


def _seed_artifact_record(seed_manifest: dict[str, Any]) -> dict[str, Any]:
    record = seed_manifest["files"][SEED_PAYLOAD_NAME]
    return {
        "path": SEED_ARTIFACT.as_posix(),
        "manifest_sha256": SEED_MANIFEST_SHA256,
        "payload_file": SEED_PAYLOAD_NAME,
        "payload_size": record["size"],
        "payload_sha256": record["sha256"],
        "seed_denominator_sha256": SEED_DENOMINATOR_SHA256,
        "dispatch_slot_denominator_sha256": DISPATCH_SLOT_DENOMINATOR_SHA256,
        "summary": EXPECTED_SEED_SUMMARY,
        "scope": EXPECTED_SEED_SCOPE,
        "excluded_seed_classes": EXPECTED_EXCLUDED_SEED_CLASSES,
        "verifier_path": SEED_VERIFIER.as_posix(),
        "verifier_sha256": SEED_VERIFIER_SHA256,
    }


def _verify_blocks(
    rom: bytes, blocks: object
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("CFG blocks are missing")
    expected_order = sorted(
        blocks,
        key=lambda block: (
            block.get("range", [-1])[0],
            _MODE_ORDER.get(block.get("mode"), 99),
        ),
    )
    if blocks != expected_order:
        raise ValueError("CFG block ordering changed")
    entries: dict[tuple[str, int], dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    previous_end = {"arm": -1, "thumb": -1}
    decoded_last: list[dict[str, Any]] = []
    instruction_entries: dict[tuple[str, int], dict[str, Any]] = {}
    total_instructions = 0
    for block in blocks:
        if not isinstance(block, dict) or block.get("mode") not in _MODE_ORDER:
            raise ValueError("CFG block is invalid")
        mode = block["mode"]
        value = block.get("range")
        if (
            not isinstance(value, list)
            or len(value) != 2
            or not all(isinstance(item, int) for item in value)
        ):
            raise ValueError("CFG block range is invalid")
        start, end = value
        block_id = block.get("id")
        if (
            block_id != f"block-{mode}-{start:06x}"
            or block_id in by_id
            or start < 0
            or start >= end
            or end > len(rom)
            or start % (4 if mode == "arm" else 2)
            or start < previous_end[mode]
        ):
            raise ValueError(f"CFG block identity/range is invalid: {block_id}")
        if block.get("bytes_sha256") != _sha(rom[start:end]):
            raise ValueError(f"CFG block bytes changed: {block_id}")
        offset = start
        instruction_count = 0
        last = None
        while offset < end:
            decoded = _decode(rom, offset, mode)
            if not decoded["accepted"]:
                raise ValueError(
                    f"CFG block contains rejected instruction at 0x{offset:06X}"
                )
            entry_key = (mode, offset)
            if entry_key in instruction_entries:
                raise ValueError(
                    f"CFG repeats an instruction entry at 0x{offset:06X}"
                )
            instruction_entries[entry_key] = decoded
            instruction_count += 1
            total_instructions += 1
            if total_instructions > MAX_INSTRUCTION_COUNT:
                raise ValueError("CFG instruction denominator exceeds its limit")
            next_offset = offset + decoded["size"]
            if next_offset < end:
                if (
                    decoded["flow_kind"] != "linear"
                    or decoded["frontiers"]
                    or decoded["successors"]
                    != [_edge("fallthrough", mode, next_offset)]
                ):
                    raise ValueError(
                        f"CFG block crosses a control-flow boundary at 0x{offset:06X}"
                    )
            elif next_offset != end:
                raise ValueError(f"CFG block splits an instruction: {block_id}")
            last = decoded
            offset = next_offset
        if (
            instruction_count != block.get("instruction_count")
            or instruction_count <= 0
            or instruction_count > MAX_BLOCK_INSTRUCTION_COUNT
            or last is None
        ):
            raise ValueError(f"CFG block instruction count changed: {block_id}")
        expected_terminator = {
            "file_offset": last["file_offset"],
            "size": last["size"],
            "mnemonic": last["mnemonic"],
            "op_str": last["op_str"],
            "flow_kind": last["flow_kind"],
            "conditional": last["conditional"],
        }
        if block.get("terminator") != expected_terminator:
            raise ValueError(f"CFG block terminator changed: {block_id}")
        entries[(mode, start)] = block
        by_id[block_id] = block
        previous_end[mode] = end
        decoded_last.append(last)
    return decoded_last, entries, by_id, instruction_entries


def _expected_frontiers_and_edges(
    rom: bytes,
    blocks: list[dict[str, Any]],
    decoded_last: list[dict[str, Any]],
    entries: dict[tuple[str, int], dict[str, Any]],
    roots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected_frontiers = []
    for block, decoded in zip(blocks, decoded_last, strict=True):
        expected_edges = []
        for edge in decoded["successors"]:
            target_key = (edge["mode"], edge["file_offset"])
            target_block = entries.get(target_key)
            if target_block is not None:
                expected_edges.append({**edge, "block_id": target_block["id"]})
                continue
            rejected = _decode(rom, edge["file_offset"], edge["mode"])
            if rejected["accepted"]:
                raise ValueError(
                    f"CFG omits a decodable successor at 0x{edge['file_offset']:06X}"
                )
            expected_frontiers.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": decoded["file_offset"],
                        "edge_kind": edge["kind"],
                    },
                    "reason": rejected["frontier_reason"],
                    "target": {
                        "mode": edge["mode"],
                        "file_offset": edge["file_offset"],
                    },
                }
            )
        if block.get("successors") != expected_edges:
            raise ValueError(f"CFG block successors changed: {block['id']}")
        for frontier in decoded["frontiers"]:
            expected_frontiers.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": decoded["file_offset"],
                    },
                    **frontier,
                }
            )
    for root in roots:
        key = (root["mode"], root["file_offset"])
        if key in entries:
            continue
        rejected = _decode(rom, root["file_offset"], root["mode"])
        if rejected["accepted"]:
            raise ValueError(f"CFG root does not start a block: {root['root_id']}")
        expected_frontiers.append(
            {
                "source": {"kind": "root", "root_id": root["root_id"]},
                "reason": rejected["frontier_reason"],
                "target": {
                    "mode": root["mode"],
                    "file_offset": root["file_offset"],
                },
            }
        )
    expected_frontiers.sort(
        key=lambda record: json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    return [
        {"id": f"frontier-{index:06d}", **record}
        for index, record in enumerate(expected_frontiers)
    ]


def _union_bytes(ranges: list[tuple[int, int]]) -> int:
    total = 0
    current_start = -1
    current_end = -1
    for start, end in sorted(ranges):
        if current_end < start:
            if current_start >= 0:
                total += current_end - current_start
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_start >= 0:
        total += current_end - current_start
    return total


def _expected_roots(
    seeds: list[dict[str, Any]],
    entries: dict[tuple[str, int], dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    frontiers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    adjacency = {
        block_id: [edge["block_id"] for edge in block["successors"]]
        for block_id, block in by_id.items()
    }
    block_frontiers: dict[str, set[str]] = defaultdict(set)
    root_frontiers: dict[str, set[str]] = defaultdict(set)
    for frontier in frontiers:
        source = frontier["source"]
        if source["kind"] == "root":
            root_frontiers[source["root_id"]].add(frontier["id"])
        else:
            block_frontiers[source["block_id"]].add(frontier["id"])
    results = []
    for index, seed in enumerate(seeds):
        root_id = f"root-{seed['mode']}-{seed['file_offset']:06x}"
        entry = entries.get((seed["mode"], seed["file_offset"]))
        reached_blocks: set[str] = set()
        queue = deque([entry["id"]] if entry is not None else [])
        reached_frontiers = set(root_frontiers[root_id])
        while queue:
            block_id = queue.popleft()
            if block_id in reached_blocks:
                continue
            reached_blocks.add(block_id)
            reached_frontiers.update(block_frontiers[block_id])
            for target in adjacency[block_id]:
                if target not in reached_blocks:
                    queue.append(target)
        instruction_count = sum(
            by_id[block_id]["instruction_count"] for block_id in reached_blocks
        )
        instruction_bytes = sum(
            by_id[block_id]["range"][1] - by_id[block_id]["range"][0]
            for block_id in reached_blocks
        )
        results.append(
            {
                "root_id": root_id,
                "seed_index": index,
                "file_offset": seed["file_offset"],
                "gba_address": seed["gba_address"],
                "mode": seed["mode"],
                "entry_size": seed["entry_size"],
                "entry_sha256": seed["entry_sha256"],
                "seed_provenance": seed["sources"],
                "entry_block_id": entry["id"] if entry is not None else None,
                "traversal_status": (
                    "closed" if not reached_frontiers else "frontier_open"
                ),
                "reachable_instruction_count": instruction_count,
                "reachable_instruction_bytes": instruction_bytes,
                "reachable_block_count": len(reached_blocks),
                "frontier_count": len(reached_frontiers),
            }
        )
    all_reached: set[str] = set()
    for root in results:
        if root["entry_block_id"] is None:
            continue
        queue = deque([root["entry_block_id"]])
        while queue:
            block_id = queue.popleft()
            if block_id in all_reached:
                continue
            all_reached.add(block_id)
            queue.extend(adjacency[block_id])
    if all_reached != set(by_id):
        raise ValueError("CFG contains blocks unreachable from the fixed roots")
    return results


def _summary(
    roots: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
    frontiers: list[dict[str, Any]],
) -> dict[str, Any]:
    mode_bytes = {
        mode: sum(
            block["range"][1] - block["range"][0]
            for block in blocks
            if block["mode"] == mode
        )
        for mode in _MODE_ORDER
    }
    union = _union_bytes([tuple(block["range"]) for block in blocks])
    reasons: dict[str, int] = {}
    for frontier in frontiers:
        reason = frontier["reason"]
        reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "root_count": len(roots),
        "arm_root_count": sum(root["mode"] == "arm" for root in roots),
        "thumb_root_count": sum(root["mode"] == "thumb" for root in roots),
        "closed_root_count": sum(root["traversal_status"] == "closed" for root in roots),
        "frontier_open_root_count": sum(
            root["traversal_status"] == "frontier_open" for root in roots
        ),
        "decoded_instruction_count": sum(
            block["instruction_count"] for block in blocks
        ),
        "arm_instruction_count": sum(
            block["instruction_count"] for block in blocks if block["mode"] == "arm"
        ),
        "thumb_instruction_count": sum(
            block["instruction_count"]
            for block in blocks
            if block["mode"] == "thumb"
        ),
        "decoded_basic_block_count": len(blocks),
        "arm_instruction_bytes": mode_bytes["arm"],
        "thumb_instruction_bytes": mode_bytes["thumb"],
        "reachable_instruction_bytes": union,
        "cross_mode_overlap_bytes": mode_bytes["arm"] + mode_bytes["thumb"] - union,
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(sorted(reasons.items())),
        "budget_exhausted": False,
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            _safe_file(root, "tools/export_rom_cfg_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(Path(__file__).read_bytes()),
        "test_sha256": _sha(
            _safe_file(root, "tests/test_export_rom_cfg_inventory.py").read_bytes()
        ),
    }


def verify_rom_cfg_inventory(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    rebuilt_instruction_count = 0
    summary = {
        "root_count": 0,
        "decoded_instruction_count": 0,
        "reachable_instruction_bytes": 0,
        "budget_exhausted": False,
    }
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        resolved_artifact = artifact.resolve(strict=True)
        if resolved_artifact != artifact or not artifact.is_dir():
            raise ValueError("CFG inventory artifact uses a symlink or is not a directory")
        members = list(artifact.iterdir())
        if (
            {member.name for member in members} != {"manifest.json", PAYLOAD_NAME}
            or any(member.is_symlink() or not member.is_file() for member in members)
        ):
            raise ValueError("CFG inventory artifact file set changed")

        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != 6_291_456 or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        seed_payload, seed_manifest = _seed_contract(root, rom)
        decoder = _decoder_identity(root)
        payload_path = artifact / PAYLOAD_NAME
        payload_raw = payload_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads((artifact / "manifest.json").read_bytes())

        expected_seed_artifact = _seed_artifact_record(seed_manifest)
        expected_limits = {
            "max_instruction_count": MAX_INSTRUCTION_COUNT,
            "max_basic_block_instruction_count": MAX_BLOCK_INSTRUCTION_COUNT,
            "decode_window_bytes": 4,
        }
        if (
            payload.get("schema") != SCHEMA
            or payload.get("rom")
            != {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
            or payload.get("seed_artifact") != expected_seed_artifact
            or payload.get("decoder") != decoder
            or payload.get("limits") != expected_limits
            or payload.get("scope") != SCOPE
            or payload.get("limitations") != LIMITATIONS
        ):
            raise ValueError("CFG inventory top-level contract changed")

        roots = payload.get("roots")
        if not isinstance(roots, list) or len(roots) != 263:
            raise ValueError("CFG root denominator changed")
        seeds = seed_payload["seeds"]
        rebuilt_entries = _rebuild_instruction_entries(rom, seeds)
        rebuilt_instruction_count = len(rebuilt_entries)
        for root_record, seed in zip(roots, seeds, strict=True):
            if (
                root_record.get("root_id")
                != f"root-{seed['mode']}-{seed['file_offset']:06x}"
                or root_record.get("seed_index") != seeds.index(seed)
                or root_record.get("mode") != seed["mode"]
                or root_record.get("file_offset") != seed["file_offset"]
                or root_record.get("gba_address") != seed["gba_address"]
                or root_record.get("entry_size") != seed["entry_size"]
                or root_record.get("entry_sha256") != seed["entry_sha256"]
                or root_record.get("seed_provenance") != seed["sources"]
            ):
                raise ValueError("CFG root no longer matches its fixed seed")

        blocks = payload.get("blocks")
        decoded_last, entries, by_id, artifact_entries = _verify_blocks(rom, blocks)
        rebuilt_keys = set(rebuilt_entries)
        artifact_keys = set(artifact_entries)
        if rebuilt_keys != artifact_keys:
            order = lambda item: (item[1], _MODE_ORDER[item[0]])
            missing = sorted(rebuilt_keys - artifact_keys, key=order)[:8]
            unexpected = sorted(artifact_keys - rebuilt_keys, key=order)[:8]
            raise ValueError(
                "CFG instruction-entry closure differs from independent seed worklist: "
                f"missing={missing}, unexpected={unexpected}"
            )
        expected_frontiers = _expected_frontiers_and_edges(
            rom, blocks, decoded_last, entries, roots
        )
        if payload.get("frontiers") != expected_frontiers:
            raise ValueError("CFG frontier inventory changed")
        expected_roots = _expected_roots(
            seeds, entries, by_id, expected_frontiers
        )
        if roots != expected_roots:
            raise ValueError("CFG per-root reachability summary changed")
        expected_summary = _summary(expected_roots, blocks, expected_frontiers)
        if payload.get("summary") != expected_summary:
            raise ValueError("CFG summary changed")
        denominator = _canonical_sha(
            {
                "roots": expected_roots,
                "blocks": blocks,
                "frontiers": expected_frontiers,
            }
        )
        if payload.get("graph_denominator_sha256") != denominator:
            raise ValueError("CFG graph denominator SHA-256 changed")

        expected_manifest = {
            "artifact_schema": SCHEMA,
            "rom": payload["rom"],
            "seed_artifact": expected_seed_artifact,
            "decoder": decoder,
            "limits": expected_limits,
            "summary": expected_summary,
            "graph_denominator_sha256": denominator,
            "files": {
                PAYLOAD_NAME: {
                    "size": len(payload_raw),
                    "sha256": _sha(payload_raw),
                }
            },
            "implementation": _implementation(root),
            "scope": SCOPE,
        }
        if manifest != expected_manifest:
            raise ValueError("CFG promotion manifest changed")
        summary = expected_summary
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": rebuilt_instruction_count,
        "root_count": summary.get("root_count", 0),
        "decoded_instruction_count": summary.get("decoded_instruction_count", 0),
        "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0),
        "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0),
        "frontier_count": summary.get("frontier_count", 0),
        "closed_root_count": summary.get("closed_root_count", 0),
        "frontier_open_root_count": summary.get("frontier_open_root_count", 0),
        "budget_exhausted": summary.get("budget_exhausted", False),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-cfg-inventory-v2"),
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_rom_cfg_inventory(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
