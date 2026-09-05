#!/usr/bin/env python3
"""Export the fixed Thumb-to-ARM boot interwork root and its closed ARM CFG."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
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
from capstone import CS_AC_WRITE, CS_ARCH_ARM, CS_MODE_ARM, Cs
from capstone import arm_const


SCHEMA = "rom-boot-interwork-v1"
VERIFY_SCHEMA = "rom-boot-interwork-verification-v1"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
PAYLOAD_NAME = "rom-boot-interwork.json"
EXPECTED_FILES = {"manifest.json", PAYLOAD_NAME}

ROOT_OFFSET = 0x00024C
CODE_END = 0x0003BC
LITERAL_END = 0x0003E0
CODE_SHA256 = "b7a934aada08004fec2cd403027a1667c91d6cb93edfae149e237dd9c7908bf3"
LITERAL_POOL_SHA256 = "1f206af83e70f2bf5c7e21d4b96b42d639a75b6aa808fb975da4cc94cc41bcb3"
ROOT_REGION_SHA256 = "00fcaba38ae745f4416d9906be0d9fdec3eb1667f9a9b6fca684289287a82995"
ROOT_ENTRY_SHA256 = "8a04c2e346e7375c2cf164f2b0e91ba8c325ffdd38c50e62ec922b266aa6c4dd"

PRODUCER_SPECS = (
    {
        "kind": "thumb_bl",
        "range": (0x061086, 0x06108A),
        "sha256": "589051c73628c96114c0977c1ee91cd7446f42932dfeed31936f351e436d58b7",
        "target": 0x09C56C,
    },
    {
        "kind": "thumb_bx_pc",
        "range": (0x09C56C, 0x09C56E),
        "sha256": "aa1170db7a37e96c7cd2677a368bc6541819794ef3984f1d91b8b27914201f6e",
        "target": 0x09C570,
    },
    {
        "kind": "arm_b",
        "range": (0x09C570, 0x09C574),
        "sha256": "979a6ff29e93c31c8a5fd2a1d6502c75b4ae36e8dff16a0b6cabdd4d1a88e33e",
        "target": ROOT_OFFSET,
    },
)
VENEER_RANGE = (0x09C56C, 0x09C574)
VENEER_SHA256 = "bbf8fd2c580d0ac6a30f6022fb477322a80a12596a521f36877ea2858f6f773b"
SKIPPED_PADDING_RANGE = (0x09C56E, 0x09C570)
SKIPPED_PADDING_SHA256 = "3e39ed78e50103716c788d4147df413950e5eba73c6e33acd923f15865795676"
SIBLING_RANGE = (0x09C574, 0x09C57C)
SIBLING_SHA256 = "9da7a0a5140808bec385f359df25633c88e2af77824236cf5146be8661086e49"

EXPECTED_BLOCKS = (
    (0x24C, 0x294, 18, "123c770a668e6b87544ed2fc9f36fa1041a1d47c0c4f29ba928f8e6a2d3da94e"),
    (0x294, 0x328, 37, "1e524d95806cd937ff1d584da9cd9ed1cf8390972c2ca31f9d5aef66888dfd7e"),
    (0x328, 0x32C, 1, "c402c7ed1b0cac28463ca441dd5574cba9696725ae979ce47d0b71d0dab45da2"),
    (0x32C, 0x340, 5, "2b4f130de6415bf8acb6a2c7a469ca2c601052c2c9cb4712f81811cd3f52b520"),
    (0x340, 0x34C, 3, "1a972be8ec46452326d2110ffba4b7f0060fd000051b1963b9058aba729794e0"),
    (0x34C, 0x35C, 4, "fa989bd3ac9a381c64256ab842a5608c0b7099f5770028f089d0f5eb3946a8ef"),
    (0x35C, 0x3A8, 19, "9f8d955826095ddba631e62378b39e3bf5a5e40f996e637789e08dc7dc0beeaf"),
    (0x3A8, 0x3BC, 5, "ea608c8186d4d96305bb37df4131edb195646868103b578c209328e2da9317a1"),
)
EXPECTED_LITERAL_VALUES = (
    (0x24C, 0x3BC, 0x03000D18),
    (0x250, 0x3C0, 0x03000A88),
    (0x258, 0x3C4, 0x03002E1C),
    (0x260, 0x3C8, 0x03002E20),
    (0x278, 0x3CC, 0x03000D18),
    (0x27C, 0x3D0, 0x03000A84),
    (0x284, 0x3D4, 0xFFFFFFFF),
    (0x3A8, 0x3D8, 0x03002E20),
    (0x3B0, 0x3DC, 0x03002E1C),
)
EXPECTED_DENOMINATORS = {
    "instruction_vector_sha256": "c25c738607397cb60f90d73d7a6efe079ef52c89c11f787b0cc7d896101beebf",
    "block_vector_sha256": "1c9d08d16c2f4c3b5cdb4123d8ae94b6fd3bb4f7921c9a28a55b77f279c3af50",
    "edge_vector_sha256": "ba298a7c1f9f7811e7dd2ac899c7faa42d013599d9e94a6c41e129b34e7176e7",
    "literal_binding_vector_sha256": "1e812f886d0e0abe614780f0c4a94af1c789831fd966c59e85e0a6ef690f4e9f",
}
EXPECTED_SUMMARY = {
    "root_count": 1,
    "closed_root_count": 1,
    "producer_instruction_count": 3,
    "producer_instruction_bytes": 10,
    "arm_instruction_count": 92,
    "arm_instruction_bytes": 368,
    "basic_block_count": 8,
    "edge_count": 10,
    "frontier_count": 0,
    "literal_binding_count": 9,
    "literal_pool_bytes": 36,
    "coverage_claim_count": 5,
    "classified_bytes": 414,
    "range_overlap_bytes": 0,
}
SCOPE = {
    "fixed_interwork_spine_verified": True,
    "direct_producer_denominator_complete": True,
    "armv4t_instruction_set_enforced": True,
    "arm_root_static_cfg_closed": True,
    "consumed_literal_pool_complete": True,
    "runtime_reachability_complete": False,
    "reset_to_root_path_complete": False,
    "surrounding_40k_region_classified": False,
    "skipped_interwork_padding_classified": False,
    "ram_targets_classified_as_code": False,
    "physical_gba_verified": False,
}
LIMITATIONS = [
    "The fixed BL/BX-pc/ARM-B spine proves the ROM root, but the full reset-to-call runtime path is not established.",
    "Only the independently closed 0x24C..0x3BC ARM worklist and its nine consumed literals are classified.",
    "The skipped 0x9C56E..0x9C570 alignment bytes, sibling veneer, RAM values, and surrounding 0x24C..0x9F2E region remain outside this claim.",
    "Static reachability does not prove natural execution, timing behavior, mGBA replay, or physical-GBA behavior.",
]
DECODER_FILES = {
    "tools/_vendor/capstone/__init__.py": "17a8db1bfe9cb52a97cc89d4ddc9b3246b5d0ddd330fb592ea17060554032f8e",
    "tools/_vendor/capstone/arm.py": "bd8e7a96074481a55c77192f6202f92a52e8c9022aa68c2de5736edf0e04fff0",
    "tools/_vendor/capstone/arm_const.py": "ca87ac6edbf031e1eff66531743dc6f2e4ba8ea63d532da401a5d1fa28653192",
    "tools/_vendor/capstone/lib/libcapstone.dylib": "00f3876991807d87ef26b6564609dd2e2c46616c476336498f33a8c8501fb35f",
}
INDEPENDENT_CFG_ENGINE_PATH = "tools/verify_rom_cfg_inventory.py"
INDEPENDENT_CFG_ENGINE_SHA256 = "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"
_ARMV4T_NAMES = (
    "ARM_INS_ADC", "ARM_INS_ADD", "ARM_INS_ADR", "ARM_INS_AND", "ARM_INS_ASR",
    "ARM_INS_B", "ARM_INS_BIC", "ARM_INS_BL", "ARM_INS_BX", "ARM_INS_CMN",
    "ARM_INS_CMP", "ARM_INS_EOR", "ARM_INS_LDM", "ARM_INS_LDMDA",
    "ARM_INS_LDMDB", "ARM_INS_LDMIB", "ARM_INS_LDR", "ARM_INS_LDRB",
    "ARM_INS_LDRBT", "ARM_INS_LDRH", "ARM_INS_LDRSB", "ARM_INS_LDRSH",
    "ARM_INS_LDRT", "ARM_INS_LSL", "ARM_INS_LSR", "ARM_INS_MLA", "ARM_INS_MOV",
    "ARM_INS_MOVS", "ARM_INS_MRS", "ARM_INS_MSR", "ARM_INS_MUL", "ARM_INS_MVN",
    "ARM_INS_NEG", "ARM_INS_NOP", "ARM_INS_ORR", "ARM_INS_POP", "ARM_INS_PUSH",
    "ARM_INS_ROR", "ARM_INS_RRX", "ARM_INS_RSB", "ARM_INS_RSC", "ARM_INS_SBC",
    "ARM_INS_SMLAL", "ARM_INS_SMULL", "ARM_INS_STM", "ARM_INS_STMDA",
    "ARM_INS_STMDB", "ARM_INS_STMIB", "ARM_INS_STR", "ARM_INS_STRB",
    "ARM_INS_STRBT", "ARM_INS_STRH", "ARM_INS_STRT", "ARM_INS_SUB",
    "ARM_INS_SUBS", "ARM_INS_SVC", "ARM_INS_SWP", "ARM_INS_SWPB", "ARM_INS_TEQ",
    "ARM_INS_TST", "ARM_INS_UMLAL", "ARM_INS_UMULL",
)
ARMV4T_IDS = frozenset(
    getattr(arm_const, name) for name in _ARMV4T_NAMES if hasattr(arm_const, name)
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _canonical_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _gba(offset: int) -> str:
    return f"0x{ROM_BASE + offset:08X}"


def _safe_file(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"repository input must not be a symlink: {relative}")
    resolved = candidate.resolve(strict=True)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _bounded(data: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(data):
        raise ValueError("boot-interwork bounded slice escapes ROM")
    return data[start:end]


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 2), "little")


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(data, offset, offset + 4), "little")


def _thumb_bl_target(data: bytes, offset: int) -> int:
    high = _u16(data, offset)
    low = _u16(data, offset + 2)
    if high & 0xF800 != 0xF000 or low & 0xF800 != 0xF800:
        raise ValueError("boot-interwork Thumb BL encoding changed")
    displacement = ((high & 0x7FF) << 12) | ((low & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return offset + 4 + displacement


def _arm_b_target(data: bytes, offset: int) -> int:
    word = _u32(data, offset)
    if word & 0x0F000000 != 0x0A000000:
        raise ValueError("boot-interwork ARM B encoding changed")
    displacement = (word & 0x00FFFFFF) << 2
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return offset + 8 + displacement


def _scan_thumb_bl(data: bytes, target: int) -> list[int]:
    matches = []
    for offset in range(0, len(data) - 3, 2):
        high = _u16(data, offset)
        low = _u16(data, offset + 2)
        if high & 0xF800 == 0xF000 and low & 0xF800 == 0xF800:
            if _thumb_bl_target(data, offset) == target:
                matches.append(offset)
    return matches


def _scan_arm_b(data: bytes, target: int) -> list[int]:
    matches = []
    for offset in range(0, len(data) - 3, 4):
        word = _u32(data, offset)
        if word >> 28 != 0xF and word & 0x0F000000 == 0x0A000000:
            if _arm_b_target(data, offset) == target:
                matches.append(offset)
    return matches


def _writes_pc(instruction: Any) -> bool:
    for operand in instruction.operands:
        if operand.type == arm_const.ARM_OP_REG and operand.reg == arm_const.ARM_REG_PC and operand.access & CS_AC_WRITE:
            return True
    try:
        _, writes = instruction.regs_access()
    except (AttributeError, capstone.CsError):
        writes = []
    return arm_const.ARM_REG_PC in writes


def _decode_instruction(engine: Cs, rom: bytes, offset: int) -> tuple[dict[str, Any], Any]:
    decoded = tuple(engine.disasm(_bounded(rom, offset, offset + 4), ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].size != 4:
        raise ValueError(f"ARM decode failure at 0x{offset:X}")
    instruction = decoded[0]
    raw = _bounded(rom, offset, offset + 4)
    if instruction.id not in ARMV4T_IDS or _u32(raw, 0) >> 28 == 0xF:
        raise ValueError(f"unsupported ARMv4T instruction at 0x{offset:X}")
    condition = getattr(instruction, "cc", arm_const.ARM_CC_AL)
    conditional = condition not in (arm_const.ARM_CC_AL, arm_const.ARM_CC_INVALID)
    successors: list[dict[str, Any]] = []
    if instruction.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL):
        operands = instruction.operands
        if len(operands) != 1 or operands[0].type != arm_const.ARM_OP_IMM:
            raise ValueError(f"indirect ARM branch at 0x{offset:X}")
        target = operands[0].imm - ROM_BASE
        successors.append({"kind": "call_target" if instruction.id == arm_const.ARM_INS_BL else "branch_target", "file_offset": target})
        if instruction.id == arm_const.ARM_INS_BL or conditional:
            successors.append({"kind": "fallthrough", "file_offset": offset + 4})
        flow = "call" if instruction.id == arm_const.ARM_INS_BL else ("conditional_branch" if conditional else "unconditional_branch")
    elif instruction.id == arm_const.ARM_INS_BX:
        operands = instruction.operands
        if conditional or len(operands) != 1 or operands[0].type != arm_const.ARM_OP_REG or operands[0].reg != arm_const.ARM_REG_LR:
            raise ValueError(f"unexpected ARM BX frontier at 0x{offset:X}")
        flow = "return"
    elif instruction.id == arm_const.ARM_INS_SVC or _writes_pc(instruction):
        raise ValueError(f"unexpected ARM frontier at 0x{offset:X}")
    else:
        flow = "linear"
        successors.append({"kind": "fallthrough", "file_offset": offset + 4})
    successors.sort(key=lambda item: ({"branch_target": 0, "call_target": 1, "fallthrough": 2}[item["kind"]], item["file_offset"]))
    return {
        "mode": "arm",
        "file_offset": offset,
        "size": 4,
        "bytes_sha256": _sha(raw),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "conditional": conditional,
        "flow_kind": flow,
        "successors": [{"kind": item["kind"], "mode": "arm", "file_offset": item["file_offset"]} for item in successors],
        "frontiers": [],
    }, instruction


def _traverse_arm(rom: bytes) -> tuple[list[dict[str, Any]], dict[int, Any]]:
    engine = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    engine.detail = True
    engine.skipdata = False
    pending = [ROOT_OFFSET]
    scheduled = {ROOT_OFFSET}
    nodes: dict[int, dict[str, Any]] = {}
    instructions: dict[int, Any] = {}
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        if offset < ROOT_OFFSET or offset >= CODE_END or offset % 4:
            raise ValueError(f"ARM root escaped fixed closure at 0x{offset:X}")
        node, instruction = _decode_instruction(engine, rom, offset)
        nodes[offset] = node
        instructions[offset] = instruction
        if len(nodes) > 1_024:
            raise ValueError("ARM root instruction budget exhausted")
        for successor in node["successors"]:
            target = successor["file_offset"]
            if target < ROOT_OFFSET or target >= CODE_END or target % 4:
                raise ValueError(f"ARM successor escaped fixed closure at 0x{target:X}")
            if target not in scheduled:
                heapq.heappush(pending, target)
                scheduled.add(target)
    expected_offsets = list(range(ROOT_OFFSET, CODE_END, 4))
    if sorted(nodes) != expected_offsets:
        raise ValueError("ARM root worklist denominator changed")
    return [nodes[offset] for offset in expected_offsets], instructions


def _build_blocks(rom: bytes, nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_offset = {node["file_offset"]: node for node in nodes}
    predecessors: dict[int, list[int]] = {offset: [] for offset in by_offset}
    for node in nodes:
        for edge in node["successors"]:
            predecessors[edge["file_offset"]].append(node["file_offset"])
    starts = {ROOT_OFFSET}
    for offset, incoming in predecessors.items():
        if offset == ROOT_OFFSET:
            continue
        if len(incoming) != 1:
            starts.add(offset)
            continue
        predecessor = by_offset[incoming[0]]
        if len(predecessor["successors"]) != 1 or predecessor["flow_kind"] != "linear" or predecessor["file_offset"] + 4 != offset:
            starts.add(offset)
    blocks = []
    block_by_offset: dict[int, str] = {}
    for start in sorted(starts):
        members = []
        offset = start
        while offset in by_offset and offset not in block_by_offset:
            node = by_offset[offset]
            members.append(node)
            block_by_offset[offset] = f"block-arm-{start:06x}"
            if len(node["successors"]) != 1 or node["flow_kind"] != "linear":
                break
            target = node["successors"][0]["file_offset"]
            if target in starts or target != offset + 4:
                break
            offset = target
        if not members:
            continue
        end = members[-1]["file_offset"] + 4
        blocks.append({
            "id": f"block-arm-{start:06x}",
            "mode": "arm",
            "range": [start, end],
            "instruction_count": len(members),
            "bytes_sha256": _sha(_bounded(rom, start, end)),
            "terminator": {
                "file_offset": members[-1]["file_offset"],
                "size": 4,
                "mnemonic": members[-1]["mnemonic"],
                "op_str": members[-1]["op_str"],
                "flow_kind": members[-1]["flow_kind"],
                "conditional": members[-1]["conditional"],
            },
        })
    if len(block_by_offset) != len(nodes):
        raise ValueError("ARM block construction left unassigned instructions")
    edges = []
    for block in blocks:
        terminator = by_offset[block["terminator"]["file_offset"]]
        successors = []
        for edge in terminator["successors"]:
            target = edge["file_offset"]
            successor = {
                "kind": edge["kind"],
                "mode": "arm",
                "file_offset": target,
                "block_id": block_by_offset[target],
            }
            successors.append(successor)
            edges.append({
                "source_block_id": block["id"],
                **successor,
            })
        block["successors"] = successors
    actual_specs = [(item["range"][0], item["range"][1], item["instruction_count"], item["bytes_sha256"]) for item in blocks]
    if actual_specs != list(EXPECTED_BLOCKS) or len(edges) != 10:
        raise ValueError("ARM block or edge denominator changed")
    return blocks, edges


def _literal_bindings(rom: bytes, instructions: dict[int, Any]) -> list[dict[str, Any]]:
    bindings = []
    for load_offset, instruction in sorted(instructions.items()):
        if instruction.id != arm_const.ARM_INS_LDR:
            continue
        memory_operands = [operand for operand in instruction.operands if operand.type == arm_const.ARM_OP_MEM and operand.mem.base == arm_const.ARM_REG_PC]
        if not memory_operands:
            continue
        if len(memory_operands) != 1:
            raise ValueError("ambiguous ARM literal load")
        literal_offset = load_offset + 8 + memory_operands[0].mem.disp
        if literal_offset % 4 or literal_offset < CODE_END or literal_offset + 4 > LITERAL_END:
            raise ValueError("ARM literal load escaped fixed pool")
        value = _u32(rom, literal_offset)
        bindings.append({
            "load_offset": load_offset,
            "literal_offset": literal_offset,
            "value": f"0x{value:08X}",
        })
    bindings.sort(key=lambda item: item["literal_offset"])
    actual = [(item["load_offset"], item["literal_offset"], int(item["value"], 16)) for item in bindings]
    if actual != list(EXPECTED_LITERAL_VALUES):
        raise ValueError("ARM literal binding denominator changed")
    return bindings


def _decoder_identity(root: Path) -> dict[str, Any]:
    actual = {}
    for relative, expected in DECODER_FILES.items():
        digest = _sha(_safe_file(root, relative).read_bytes())
        if digest != expected:
            raise ValueError(f"boot-interwork decoder dependency changed: {relative}")
        actual[relative] = digest
    if capstone.__version__ != "5.0.7" or capstone.cs_version()[:2] != (5, 0):
        raise ValueError("boot-interwork Capstone version changed")
    independent_digest = _sha(_safe_file(root, INDEPENDENT_CFG_ENGINE_PATH).read_bytes())
    if independent_digest != INDEPENDENT_CFG_ENGINE_SHA256:
        raise ValueError("boot-interwork independent CFG engine changed")
    return {
        "architecture": "ARM7TDMI / ARMv4T",
        "backend": "vendored-capstone",
        "version": capstone.__version__,
        "files": actual,
        "independent_verifier_engine": {
            "path": INDEPENDENT_CFG_ENGINE_PATH,
            "sha256": independent_digest,
        },
    }


def _producer_chain(rom: bytes) -> dict[str, Any]:
    spine = []
    for spec in PRODUCER_SPECS:
        start, end = spec["range"]
        if _sha(_bounded(rom, start, end)) != spec["sha256"]:
            raise ValueError(f"boot-interwork {spec['kind']} bytes changed")
        if spec["kind"] == "thumb_bl":
            target = _thumb_bl_target(rom, start)
        elif spec["kind"] == "thumb_bx_pc":
            if _u16(rom, start) != 0x4778:
                raise ValueError("boot-interwork Thumb BX pc changed")
            target = (start + 4) & ~3
        else:
            target = _arm_b_target(rom, start)
        if target != spec["target"]:
            raise ValueError(f"boot-interwork {spec['kind']} target changed")
        spine.append({
            "kind": spec["kind"],
            "range": [start, end],
            "gba_range": [_gba(start), _gba(end)],
            "size": end - start,
            "sha256": spec["sha256"],
            "target": _gba(target),
        })
    if _scan_thumb_bl(rom, 0x09C56C) != [0x061086] or _scan_arm_b(rom, ROOT_OFFSET) != [0x09C570]:
        raise ValueError("boot-interwork direct producer denominator changed")
    if _sha(_bounded(rom, *VENEER_RANGE)) != VENEER_SHA256 or _sha(_bounded(rom, *SKIPPED_PADDING_RANGE)) != SKIPPED_PADDING_SHA256:
        raise ValueError("boot-interwork veneer bytes changed")
    if _sha(_bounded(rom, *SIBLING_RANGE)) != SIBLING_SHA256 or _u16(rom, SIBLING_RANGE[0]) != 0x4778 or _arm_b_target(rom, 0x09C578) != 0x00026C:
        raise ValueError("boot-interwork excluded sibling changed")
    return {
        "interwork_spine": spine,
        "veneer_range": list(VENEER_RANGE),
        "veneer_sha256": VENEER_SHA256,
        "skipped_padding_range": list(SKIPPED_PADDING_RANGE),
        "skipped_padding_sha256": SKIPPED_PADDING_SHA256,
        "excluded_sibling": {
            "range": list(SIBLING_RANGE),
            "sha256": SIBLING_SHA256,
            "target": _gba(0x00026C),
            "part_of_root": False,
        },
        "unique_thumb_bl_producers": [0x061086],
        "unique_arm_b_producers": [0x09C570],
    }


def _derive(root: Path, rom: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity mismatch")
    if _sha(_bounded(rom, ROOT_OFFSET, CODE_END)) != CODE_SHA256 or _sha(_bounded(rom, CODE_END, LITERAL_END)) != LITERAL_POOL_SHA256 or _sha(_bounded(rom, ROOT_OFFSET, LITERAL_END)) != ROOT_REGION_SHA256:
        raise ValueError("boot-interwork ARM root region changed")
    producer_chain = _producer_chain(rom)
    instructions, decoded = _traverse_arm(rom)
    blocks, edges = _build_blocks(rom, instructions)
    literals = _literal_bindings(rom, decoded)
    rebuilt_denominators = {
        "instruction_vector_sha256": _canonical_sha(instructions),
        "block_vector_sha256": _canonical_sha(blocks),
        "edge_vector_sha256": _canonical_sha(edges),
        "literal_binding_vector_sha256": _canonical_sha(literals),
    }
    if rebuilt_denominators != EXPECTED_DENOMINATORS:
        raise ValueError(
            f"boot-interwork canonical denominator changed: {rebuilt_denominators}"
        )
    claims = []
    for identifier, semantic_class, (start, end) in (
        ("arm-root-code", "arm_code", (ROOT_OFFSET, CODE_END)),
        ("arm-root-literal-pool", "arm_literal_pool", (CODE_END, LITERAL_END)),
        ("thumb-direct-caller", "thumb_code", PRODUCER_SPECS[0]["range"]),
        ("thumb-bx-pc", "thumb_interwork_code", PRODUCER_SPECS[1]["range"]),
        ("arm-root-branch", "arm_interwork_code", PRODUCER_SPECS[2]["range"]),
    ):
        raw = _bounded(rom, start, end)
        claims.append({"id": identifier, "range": [start, end], "size": len(raw), "semantic_class": semantic_class, "sha256": _sha(raw)})
    denominators = rebuilt_denominators
    implementation = {
        label: {"path": path, "sha256": _sha(_safe_file(root, path).read_bytes())}
        for label, path in {
            "exporter": "tools/export_rom_boot_interwork.py",
            "verifier": "tools/verify_rom_boot_interwork.py",
            "test": "tests/test_export_rom_boot_interwork.py",
        }.items()
    }
    root_record = {
        "root_id": "root-arm-00024c",
        "mode": "arm",
        "file_offset": ROOT_OFFSET,
        "gba_address": _gba(ROOT_OFFSET),
        "entry_size": 4,
        "entry_sha256": ROOT_ENTRY_SHA256,
        "traversal_status": "closed",
        "reachable_instruction_count": len(instructions),
        "reachable_instruction_bytes": len(instructions) * 4,
        "reachable_block_count": len(blocks),
        "frontier_count": 0,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "decoder": _decoder_identity(root),
        "producer_chain": producer_chain,
        "root": root_record,
        "instructions": instructions,
        "blocks": blocks,
        "edges": edges,
        "literal_bindings": literals,
        "denominators": denominators,
        "coverage_claims": claims,
        "summary": dict(EXPECTED_SUMMARY),
        "scope": dict(SCOPE),
        "limitations": list(LIMITATIONS),
        "implementation": implementation,
    }


def _manifest(payload: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    return {
        "schema": f"{SCHEMA}-artifact-manifest-v1",
        "artifact_schema": SCHEMA,
        "rom": payload["rom"],
        "summary": payload["summary"],
        "files": {name: {"size": len(content), "sha256": _sha(content)} for name, content in sorted(files.items())},
        "producer": payload["implementation"],
        "scope": payload["scope"],
        "verification": {
            "schema": VERIFY_SCHEMA,
            "command": ["python3", "tools/verify_rom_boot_interwork.py", "--root", ".", "--artifact-dir", f"artifacts/{SCHEMA}"],
            "verifier_sha256": payload["implementation"]["verifier"]["sha256"],
        },
    }


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("artifact output path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _validate_output(root: Path, output: Path) -> Path:
    requested = output.expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root:
        raise ValueError("artifact output must not be the repository root")
    if target in root.parents:
        raise ValueError("artifact output must not be an ancestor of the repository root")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("foreign artifact output is not a directory")
    members = list(target.rglob("*"))
    actual = {member.relative_to(target).as_posix() for member in members if member.is_file()}
    if actual != EXPECTED_FILES or any(member.is_symlink() for member in members):
        raise ValueError("foreign artifact output directory")
    try:
        from tools.verify_rom_boot_interwork import verify_artifact
    except ModuleNotFoundError:
        from verify_rom_boot_interwork import verify_artifact
    report = verify_artifact(root, target)
    if report.get("verified") is not True:
        raise ValueError(f"existing artifact failed independent verification: {report.get('errors', [])}")
    return target


def _replace_output(target: Path, files: dict[str, bytes]) -> None:
    _reject_symlink_components(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(target.parent)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    backup: Path | None = None
    try:
        for name, content in files.items():
            (temporary / name).write_bytes(content)
        _reject_symlink_components(target)
        if target.exists():
            backup = target.with_name(f".{target.name}.old-{uuid.uuid4().hex}")
            os.replace(target, backup)
        _reject_symlink_components(target.parent)
        os.replace(temporary, target)
        if backup is not None:
            shutil.rmtree(backup)
    except BaseException:
        if backup is not None and backup.exists():
            if target.exists():
                shutil.rmtree(target)
            os.replace(backup, target)
        raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    target = _validate_output(root, Path(output))
    payload = _derive(root)
    files = {PAYLOAD_NAME: _canonical(payload)}
    files["manifest.json"] = _canonical(_manifest(payload, files))
    _replace_output(target, files)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}"))
    args = parser.parse_args()
    output = args.output_dir if args.output_dir.is_absolute() else args.root / args.output_dir
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
