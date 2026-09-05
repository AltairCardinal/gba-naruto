#!/usr/bin/env python3
"""Export the frozen static continuation after the boot interwork Thumb BL."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
for import_root in (PROJECT_ROOT, PROJECT_ROOT / "tools/_vendor"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import capstone
from capstone import CS_AC_WRITE, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, Cs
from capstone import arm_const

from tools import rom_boot_interwork_continuation_contract as contract


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
_THUMB_IDS = frozenset(
    getattr(arm_const, name) for name in _THUMB_NAMES if hasattr(arm_const, name)
)
_ARM_NAMES = (
    "ARM_INS_ADC", "ARM_INS_ADD", "ARM_INS_ADR", "ARM_INS_AND", "ARM_INS_ASR",
    "ARM_INS_B", "ARM_INS_BIC", "ARM_INS_BL", "ARM_INS_BX", "ARM_INS_CMN",
    "ARM_INS_CMP", "ARM_INS_EOR", "ARM_INS_LDM", "ARM_INS_LDMDA", "ARM_INS_LDMDB",
    "ARM_INS_LDMIB", "ARM_INS_LDR", "ARM_INS_LDRB", "ARM_INS_LDRBT", "ARM_INS_LDRH",
    "ARM_INS_LDRSB", "ARM_INS_LDRSH", "ARM_INS_LDRT", "ARM_INS_LSL", "ARM_INS_LSR",
    "ARM_INS_MLA", "ARM_INS_MOV", "ARM_INS_MOVS", "ARM_INS_MRS", "ARM_INS_MSR",
    "ARM_INS_MUL", "ARM_INS_MVN", "ARM_INS_NEG", "ARM_INS_NOP", "ARM_INS_ORR",
    "ARM_INS_POP", "ARM_INS_PUSH", "ARM_INS_ROR", "ARM_INS_RRX", "ARM_INS_RSB",
    "ARM_INS_RSC", "ARM_INS_SBC", "ARM_INS_SMLAL", "ARM_INS_SMULL", "ARM_INS_STM",
    "ARM_INS_STMDA", "ARM_INS_STMDB", "ARM_INS_STMIB", "ARM_INS_STR", "ARM_INS_STRB",
    "ARM_INS_STRBT", "ARM_INS_STRH", "ARM_INS_STRT", "ARM_INS_SUB", "ARM_INS_SUBS",
    "ARM_INS_SVC", "ARM_INS_SWP", "ARM_INS_SWPB", "ARM_INS_TEQ", "ARM_INS_TST",
    "ARM_INS_UMLAL", "ARM_INS_UMULL",
)
_ARM_IDS = frozenset(getattr(arm_const, name) for name in _ARM_NAMES if hasattr(arm_const, name))


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _compact_sha(value: Any) -> str:
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _gba(offset: int) -> str:
    return f"0x{contract.ROM_BASE + offset:08X}"


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
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not resolved.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return resolved


def _decoder_identity(root: Path) -> dict[str, Any]:
    if capstone.__version__ != contract.DECODER_VERSION or capstone.cs_version()[:2] != (5, 0):
        raise ValueError("vendored Capstone decoder version changed")
    files = {}
    for relative, expected in contract.DECODER_FILES.items():
        actual = _sha(_safe_file(root, relative).read_bytes())
        if actual != expected:
            raise ValueError(f"vendored Capstone decoder file changed: {relative}")
        files[relative] = actual
    return {"architecture": "ARM7TDMI / ARMv4T", "backend": "vendored-capstone", "version": capstone.__version__, "files": files}


def _bounded(rom: bytes, start: int, end: int) -> bytes:
    if start < 0 or end < start or end > len(rom):
        raise ValueError(f"ROM range outside input: 0x{start:X}..0x{end:X}")
    return rom[start:end]


def _u16(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 2), "little")


def _u32(rom: bytes, offset: int) -> int:
    return int.from_bytes(_bounded(rom, offset, offset + 4), "little")


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _conditional(ins: Any) -> bool:
    return getattr(ins, "cc", arm_const.ARM_CC_AL) not in (
        arm_const.ARM_CC_AL,
        arm_const.ARM_CC_INVALID,
    )


def _writes_pc(ins: Any) -> bool:
    for operand in ins.operands:
        if (
            operand.type == arm_const.ARM_OP_REG
            and operand.reg == arm_const.ARM_REG_PC
            and operand.access & CS_AC_WRITE
        ):
            return True
    try:
        _, writes = ins.regs_access()
    except (AttributeError, capstone.CsError):
        writes = []
    return arm_const.ARM_REG_PC in writes


def _thumb_raw_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
    first = int.from_bytes(raw[:2], "little")
    if len(raw) == 4:
        second = int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {
                "flow_kind": "call",
                "size": 4,
                "conditional": False,
                "target_file_offset": offset + 4 + _sign_extend(encoded, 23),
            }
    if first & 0xFF00 == 0xDF00:
        return {
            "flow_kind": "supervisor_call",
            "size": 2,
            "conditional": False,
            "swi_immediate": first & 0xFF,
        }
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        displacement = _sign_extend((first & 0xFF) << 1, 9)
        return {
            "flow_kind": "conditional_branch",
            "size": 2,
            "conditional": True,
            "target_file_offset": offset + 4 + displacement,
        }
    if first & 0xF800 == 0xE000:
        displacement = _sign_extend((first & 0x07FF) << 1, 12)
        return {
            "flow_kind": "unconditional_branch",
            "size": 2,
            "conditional": False,
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


def _thumb_engine() -> Cs:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    engine.detail = True
    engine.skipdata = False
    return engine


def _decode_thumb(rom: bytes, offset: int, engine: Cs) -> dict[str, Any]:
    decoded = tuple(engine.disasm(_bounded(rom, offset, offset + 4), contract.ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != contract.ROM_BASE + offset:
        raise ValueError(f"Thumb decode failure at 0x{offset:06X}")
    instruction = decoded[0]
    raw = _bounded(rom, offset, offset + instruction.size)
    if instruction.id not in _THUMB_IDS or instruction.size not in (2, 4):
        raise ValueError(f"unsupported ARMv4T Thumb instruction at 0x{offset:06X}")
    if instruction.size == 4:
        first = _u16(rom, offset)
        second = _u16(rom, offset + 2)
        if not (instruction.id == arm_const.ARM_INS_BL and first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800):
            raise ValueError(f"unexpected Thumb-32 instruction at 0x{offset:06X}")
    flow = _thumb_raw_flow(raw, offset)
    if instruction.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL, arm_const.ARM_INS_BX, arm_const.ARM_INS_SVC) and flow is None:
        raise ValueError(f"Thumb control-flow oracle mismatch at 0x{offset:06X}")
    if flow is not None:
        expected = {
            "unconditional_branch": arm_const.ARM_INS_B,
            "conditional_branch": arm_const.ARM_INS_B,
            "call": arm_const.ARM_INS_BL,
            "return": arm_const.ARM_INS_BX,
            "indirect_branch": arm_const.ARM_INS_BX,
            "supervisor_call": arm_const.ARM_INS_SVC,
        }[flow["flow_kind"]]
        if instruction.id != expected or instruction.size != flow["size"]:
            raise ValueError(f"Thumb control-flow oracle mismatch at 0x{offset:06X}")
    conditional = flow["conditional"] if flow is not None else _conditional(instruction)
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    if flow is not None and flow["flow_kind"] in {"call", "conditional_branch", "unconditional_branch"}:
        target = flow["target_file_offset"]
        if 0 <= target < len(rom) and target % 2 == 0:
            successors.append({
                "kind": "call_target" if flow["flow_kind"] == "call" else "branch_target",
                "mode": "thumb",
                "file_offset": target,
            })
        else:
            frontiers.append({"reason": "direct_target_outside_or_misaligned", "target_file_offset": target})
        if flow["flow_kind"] in {"call", "conditional_branch"}:
            successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": offset + instruction.size})
        flow_kind = flow["flow_kind"]
    elif flow is not None and flow["flow_kind"] == "supervisor_call":
        frontiers.append({"reason": "bios_swi_external", "swi_immediate": flow["swi_immediate"]})
        successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": offset + instruction.size})
        flow_kind = flow["flow_kind"]
    elif flow is not None:
        flow_kind = flow["flow_kind"]
        if flow_kind == "indirect_branch":
            frontiers.append({"reason": "indirect_pc_target"})
    elif _writes_pc(instruction):
        flow_kind = "indirect_branch"
        frontiers.append({"reason": "indirect_pc_target"})
    else:
        flow_kind = "linear"
        successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": offset + instruction.size})
    successors.sort(key=lambda item: (_EDGE_ORDER[item["kind"]], item["file_offset"]))
    return {
        "mode": "thumb",
        "file_offset": offset,
        "size": instruction.size,
        "raw_hex": raw.hex(),
        "bytes_sha256": _sha(raw),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "conditional": conditional,
        "flow_kind": flow_kind,
        "raw_flow_kind": flow["flow_kind"] if flow is not None else None,
        "successors": successors,
        "frontiers": frontiers,
    }


def _merge(intervals: list[tuple[int, int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _thumb_traverse(rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    engine = _thumb_engine()
    pending = [contract.CONTINUATION_ROOT]
    scheduled = {contract.CONTINUATION_ROOT}
    nodes: dict[int, dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        if not contract.CONTINUATION_CODE_RANGE[0] <= offset < contract.CONTINUATION_CODE_RANGE[1] or offset % 2:
            raise ValueError(f"Thumb continuation escaped code range at 0x{offset:06X}")
        node = _decode_thumb(rom, offset, engine)
        end = offset + node["size"]
        if end > contract.CONTINUATION_CODE_RANGE[1]:
            raise ValueError(f"Thumb continuation instruction crosses literal pool at 0x{offset:06X}")
        if node["frontiers"]:
            raise ValueError(f"Thumb continuation decoder frontier at 0x{offset:06X}")
        nodes[offset] = node
        for edge in node["successors"]:
            target = edge["file_offset"]
            if contract.CONTINUATION_CODE_RANGE[0] <= target < contract.CONTINUATION_CODE_RANGE[1]:
                if target not in scheduled:
                    scheduled.add(target)
                    heapq.heappush(pending, target)
            else:
                external.append({
                    "source_instruction_offset": offset,
                    "kind": edge["kind"],
                    "mode": "thumb",
                    "target_offset": target,
                    "target_gba_address": _gba(target),
                    "resolution": "opaque_external_edge",
                })
    expected_offsets = []
    cursor = contract.CONTINUATION_CODE_RANGE[0]
    while cursor < contract.CONTINUATION_CODE_RANGE[1]:
        expected_offsets.append(cursor)
        cursor += nodes.get(cursor, {}).get("size", 0)
        if cursor <= expected_offsets[-1]:
            raise ValueError("Thumb continuation traversal made no progress")
    if sorted(nodes) != expected_offsets:
        raise ValueError("Thumb continuation instruction denominator changed")
    if len(nodes) != contract.CONTINUATION_INSTRUCTION_COUNT or sum(item["size"] for item in nodes.values()) != contract.CONTINUATION_CODE_BYTES:
        raise ValueError("Thumb continuation instruction count changed")
    if len(external) != contract.CONTINUATION_EXTERNAL_EDGE_COUNT:
        raise ValueError("Thumb continuation outbound edge denominator changed")
    return [nodes[offset] for offset in expected_offsets], sorted(external, key=lambda row: (row["source_instruction_offset"], _EDGE_ORDER.get(row["kind"], 99), row["target_offset"]))


def _thumb_blocks(nodes: list[dict[str, Any]], external: list[dict[str, Any]], rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_offset = {node["file_offset"]: node for node in nodes}
    predecessors: dict[int, list[int]] = {offset: [] for offset in by_offset}
    for node in nodes:
        for edge in node["successors"]:
            if edge["file_offset"] in by_offset:
                predecessors[edge["file_offset"]].append(node["file_offset"])
    starts = {contract.CONTINUATION_ROOT}
    for offset, incoming in predecessors.items():
        if offset == contract.CONTINUATION_ROOT:
            continue
        if len(incoming) != 1:
            starts.add(offset)
            continue
        predecessor = by_offset[incoming[0]]
        internal_successors = [
            edge for edge in predecessor["successors"]
            if edge["file_offset"] in by_offset
        ]
        target = internal_successors[0]["file_offset"] if len(internal_successors) == 1 else None
        if predecessor["flow_kind"] != "linear" or target != offset or predecessor["file_offset"] + predecessor["size"] != offset:
            starts.add(offset)
    blocks: list[dict[str, Any]] = []
    block_by_offset: dict[int, str] = {}
    for start in sorted(starts):
        members: list[dict[str, Any]] = []
        offset = start
        while offset in by_offset and offset not in block_by_offset:
            node = by_offset[offset]
            members.append(node)
            block_by_offset[offset] = f"block-thumb-{start:06x}"
            internal_successors = [
                edge for edge in node["successors"]
                if edge["file_offset"] in by_offset
            ]
            if len(internal_successors) != 1 or node["flow_kind"] != "linear":
                break
            target = internal_successors[0]["file_offset"]
            if target in starts or target != offset + node["size"]:
                break
            offset = target
        if not members:
            continue
        last = members[-1]
        end = last["file_offset"] + last["size"]
        blocks.append({
            "id": block_by_offset[start],
            "mode": "thumb",
            "range": [start, end],
            "gba_range": [_gba(start), _gba(end)],
            "instruction_count": len(members),
            "bytes_sha256": _sha(_bounded(rom, start, end)),
            "terminator": {
                "file_offset": last["file_offset"],
                "size": last["size"],
                "raw_hex": last["raw_hex"],
                "mnemonic": last["mnemonic"],
                "op_str": last["op_str"],
                "flow_kind": last["flow_kind"],
                "conditional": last["conditional"],
            },
            "successors": [],
        })
    if len(block_by_offset) != len(nodes) or len(blocks) != contract.CONTINUATION_BLOCK_COUNT:
        raise ValueError("Thumb continuation block denominator changed")
    external_by_source: dict[tuple[int, str, int], dict[str, Any]] = {
        (row["source_instruction_offset"], row["kind"], row["target_offset"]): row for row in external
    }
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["file_offset"]
        for edge in by_offset[source]["successors"]:
            target = edge["file_offset"]
            if target in by_offset:
                record = {
                    "source_block_id": block["id"],
                    "source_instruction_offset": source,
                    "kind": edge["kind"],
                    "mode": "thumb",
                    "target_offset": target,
                    "target_gba_address": _gba(target),
                    "target_block_id": block_by_offset[target],
                    "resolution": "internal",
                }
            else:
                try:
                    record = {**external_by_source[(source, edge["kind"], target)], "source_block_id": block["id"]}
                except KeyError as error:
                    raise ValueError("Thumb continuation external edge binding changed") from error
            block["successors"].append(record)
            edges.append(record)
    return blocks, edges


def _thumb_literals(rom: bytes, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    literal_starts = {start for start, _ in contract.CONTINUATION_LITERAL_RANGES}
    for node in nodes:
        offset = node["file_offset"]
        if node["size"] != 2 or _u16(rom, offset) & 0xF800 != 0x4800:
            continue
        literal = ((offset + 4) & ~3) + (_u16(rom, offset) & 0xFF) * 4
        if literal not in literal_starts or literal + 4 > contract.CONTINUATION_END:
            raise ValueError(f"Thumb PC-relative literal escaped continuation pool at 0x{offset:06X}")
        raw = _bounded(rom, literal, literal + 4)
        result.append({
            "load_offset": offset,
            "load_gba_address": _gba(offset),
            "literal_offset": literal,
            "literal_gba_address": _gba(literal),
            "raw_hex": raw.hex(),
            "value": f"0x{int.from_bytes(raw, 'little'):08X}",
        })
    result.sort(key=lambda row: (row["load_offset"], row["literal_offset"]))
    expected = [
        (0x0610A2, 0x0610D4), (0x0610AA, 0x0610D8), (0x0610AE, 0x0610DC),
        (0x0610BA, 0x0610E0), (0x0610CA, 0x0610E4),
    ]
    if [(row["load_offset"], row["literal_offset"]) for row in result] != expected:
        raise ValueError("Thumb continuation literal binding denominator changed")
    return result


def _decode_arm(rom: bytes, offset: int, engine: Cs) -> tuple[dict[str, Any], Any]:
    decoded = tuple(engine.disasm(_bounded(rom, offset, offset + 4), contract.ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].size != 4:
        raise ValueError(f"ARM callee decode failure at 0x{offset:06X}")
    instruction = decoded[0]
    raw = _bounded(rom, offset, offset + 4)
    if instruction.id not in _ARM_IDS or _u32(rom, offset) >> 28 == 0xF:
        raise ValueError(f"unsupported ARMv4T callee instruction at 0x{offset:06X}")
    conditional = _conditional(instruction)
    successors: list[dict[str, Any]] = []
    if instruction.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL):
        if len(instruction.operands) != 1 or instruction.operands[0].type != arm_const.ARM_OP_IMM:
            raise ValueError(f"indirect ARM callee branch at 0x{offset:06X}")
        target = instruction.operands[0].imm - contract.ROM_BASE
        successors.append({
            "kind": "call_target" if instruction.id == arm_const.ARM_INS_BL else "branch_target",
            "mode": "arm",
            "file_offset": target,
        })
        if instruction.id == arm_const.ARM_INS_BL or conditional:
            successors.append({"kind": "fallthrough", "mode": "arm", "file_offset": offset + 4})
        flow_kind = "call" if instruction.id == arm_const.ARM_INS_BL else (
            "conditional_branch" if conditional else "unconditional_branch"
        )
    elif instruction.id == arm_const.ARM_INS_BX:
        if conditional or len(instruction.operands) != 1 or instruction.operands[0].type != arm_const.ARM_OP_REG or instruction.operands[0].reg != arm_const.ARM_REG_LR:
            raise ValueError(f"non-return ARM callee BX at 0x{offset:06X}")
        flow_kind = "return"
    elif instruction.id == arm_const.ARM_INS_SVC or _writes_pc(instruction):
        raise ValueError(f"ARM callee frontier at 0x{offset:06X}")
    else:
        successors.append({"kind": "fallthrough", "mode": "arm", "file_offset": offset + 4})
        flow_kind = "linear"
    successors.sort(key=lambda item: (_EDGE_ORDER[item["kind"]], item["file_offset"]))
    return {
        "mode": "arm",
        "file_offset": offset,
        "size": 4,
        "bytes_sha256": _sha(raw),
        "mnemonic": instruction.mnemonic,
        "op_str": instruction.op_str,
        "conditional": conditional,
        "flow_kind": flow_kind,
        "successors": successors,
        "frontiers": [],
    }, instruction


def _arm_traverse(rom: bytes) -> tuple[list[dict[str, Any]], dict[int, Any]]:
    engine = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    engine.detail = True
    engine.skipdata = False
    pending = [contract.OFFICIAL_ROOT_OFFSET]
    scheduled = {contract.OFFICIAL_ROOT_OFFSET}
    nodes: dict[int, dict[str, Any]] = {}
    decoded: dict[int, Any] = {}
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        if not contract.OFFICIAL_ROOT_OFFSET <= offset < contract.OFFICIAL_ROOT_END or offset % 4:
            raise ValueError(f"ARM callee escaped fixed closure at 0x{offset:06X}")
        node, instruction = _decode_arm(rom, offset, engine)
        nodes[offset] = node
        decoded[offset] = instruction
        if len(nodes) > 1024:
            raise ValueError("ARM callee instruction budget exhausted")
        for edge in node["successors"]:
            target = edge["file_offset"]
            if not contract.OFFICIAL_ROOT_OFFSET <= target < contract.OFFICIAL_ROOT_END or target % 4:
                raise ValueError(f"ARM callee successor escaped closure at 0x{target:06X}")
            if target not in scheduled:
                scheduled.add(target)
                heapq.heappush(pending, target)
    expected_offsets = list(range(contract.OFFICIAL_ROOT_OFFSET, contract.OFFICIAL_ROOT_END, 4))
    if sorted(nodes) != expected_offsets:
        raise ValueError("ARM callee instruction denominator changed")
    return [nodes[offset] for offset in expected_offsets], decoded


def _arm_blocks(rom: bytes, nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_offset = {node["file_offset"]: node for node in nodes}
    predecessors: dict[int, list[int]] = {offset: [] for offset in by_offset}
    for node in nodes:
        for edge in node["successors"]:
            predecessors[edge["file_offset"]].append(node["file_offset"])
    starts = {contract.OFFICIAL_ROOT_OFFSET}
    for offset, incoming in predecessors.items():
        if offset == contract.OFFICIAL_ROOT_OFFSET:
            continue
        if len(incoming) != 1:
            starts.add(offset)
            continue
        predecessor = by_offset[incoming[0]]
        if len(predecessor["successors"]) != 1 or predecessor["flow_kind"] != "linear" or predecessor["file_offset"] + 4 != offset:
            starts.add(offset)
    blocks: list[dict[str, Any]] = []
    block_by_offset: dict[int, str] = {}
    for start in sorted(starts):
        members: list[dict[str, Any]] = []
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
        last = members[-1]
        end = last["file_offset"] + 4
        blocks.append({
            "id": block_by_offset[start],
            "mode": "arm",
            "range": [start, end],
            "instruction_count": len(members),
            "bytes_sha256": _sha(_bounded(rom, start, end)),
            "terminator": {
                "file_offset": last["file_offset"],
                "size": 4,
                "mnemonic": last["mnemonic"],
                "op_str": last["op_str"],
                "flow_kind": last["flow_kind"],
                "conditional": last["conditional"],
            },
            "successors": [],
        })
    if len(block_by_offset) != len(nodes) or len(blocks) != contract.OFFICIAL_ARM_BLOCK_COUNT:
        raise ValueError("ARM callee block denominator changed")
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["file_offset"]
        for edge in by_offset[source]["successors"]:
            target = edge["file_offset"]
            record = {
                "kind": edge["kind"],
                "mode": "arm",
                "file_offset": target,
                "block_id": block_by_offset[target],
            }
            block["successors"].append(record)
            edges.append({"source_block_id": block["id"], **record})
    if len(edges) != contract.OFFICIAL_ARM_EDGE_COUNT:
        raise ValueError("ARM callee edge denominator changed")
    return blocks, edges


def _arm_literals(rom: bytes, decoded: dict[int, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for load_offset, instruction in sorted(decoded.items()):
        if instruction.id != arm_const.ARM_INS_LDR:
            continue
        operands = [operand for operand in instruction.operands if operand.type == arm_const.ARM_OP_MEM and operand.mem.base == arm_const.ARM_REG_PC]
        if not operands:
            continue
        if len(operands) != 1:
            raise ValueError("ambiguous ARM callee literal load")
        literal_offset = load_offset + 8 + operands[0].mem.disp
        if literal_offset % 4 or literal_offset < contract.OFFICIAL_ROOT_END or literal_offset + 4 > 0x03E0:
            raise ValueError("ARM callee literal escaped fixed pool")
        result.append({
            "load_offset": load_offset,
            "literal_offset": literal_offset,
            "value": f"0x{_u32(rom, literal_offset):08X}",
        })
    result.sort(key=lambda row: row["literal_offset"])
    if len(result) != 9:
        raise ValueError("ARM callee literal binding denominator changed")
    return result


def _read_official_reference(root: Path, rom: bytes) -> dict[str, Any]:
    manifest_raw = _safe_file(root, contract.OFFICIAL_MANIFEST_PATH).read_bytes()
    payload_raw = _safe_file(root, contract.OFFICIAL_PAYLOAD_PATH).read_bytes()
    if _sha(manifest_raw) != contract.OFFICIAL_MANIFEST_SHA256:
        raise ValueError("official boot-interwork manifest identity changed")
    if _sha(payload_raw) != contract.OFFICIAL_PAYLOAD_SHA256:
        raise ValueError("official boot-interwork payload identity changed")
    manifest = json.loads(manifest_raw.decode("utf-8"))
    payload = json.loads(payload_raw.decode("utf-8"))
    file_record = manifest.get("files", {}).get(contract.OFFICIAL_PAYLOAD_PATH.name)
    if manifest.get("artifact_schema") != "rom-boot-interwork-v1" or file_record != {"sha256": contract.OFFICIAL_PAYLOAD_SHA256, "size": len(payload_raw)}:
        raise ValueError("official boot-interwork manifest binding changed")
    if payload.get("schema") != "rom-boot-interwork-v1" or payload.get("rom", {}).get("sha256") != contract.ROM_SHA256:
        raise ValueError("official boot-interwork payload contract changed")
    producer = payload.get("producer_chain", {}).get("interwork_spine", [])
    if not any(item.get("kind") == "thumb_bl" and item.get("range") == [contract.BL_PRODUCER_OFFSET, contract.BL_PRODUCER_END] for item in producer if isinstance(item, dict)):
        raise ValueError("official boot-interwork BL binding changed")
    official_impl = manifest.get("producer", {})
    expected_implementation = {
        "exporter": {"path": contract.OFFICIAL_EXPORTER_PATH.as_posix(), "sha256": contract.OFFICIAL_EXPORTER_SHA256},
        "verifier": {"path": contract.OFFICIAL_VERIFIER_PATH.as_posix(), "sha256": contract.OFFICIAL_VERIFIER_SHA256},
        "test": {"path": contract.OFFICIAL_TEST_PATH.as_posix(), "sha256": contract.OFFICIAL_TEST_SHA256},
    }
    if any(official_impl.get(key) != value for key, value in expected_implementation.items()):
        raise ValueError("official boot-interwork implementation identity changed")
    for relative, expected in (
        (contract.OFFICIAL_EXPORTER_PATH, contract.OFFICIAL_EXPORTER_SHA256),
        (contract.OFFICIAL_VERIFIER_PATH, contract.OFFICIAL_VERIFIER_SHA256),
        (contract.OFFICIAL_TEST_PATH, contract.OFFICIAL_TEST_SHA256),
    ):
        if _sha(_safe_file(root, relative).read_bytes()) != expected:
            raise ValueError(f"official boot-interwork file changed: {relative}")
    root_record = payload.get("root", {})
    if root_record.get("file_offset") != contract.OFFICIAL_ROOT_OFFSET or root_record.get("traversal_status") != "closed" or root_record.get("frontier_count") != 0:
        raise ValueError("official ARM callee root closure changed")
    if root_record.get("reachable_instruction_count") != contract.OFFICIAL_ARM_INSTRUCTION_COUNT or root_record.get("reachable_instruction_bytes") != contract.OFFICIAL_ARM_INSTRUCTION_BYTES:
        raise ValueError("official ARM callee denominator changed")
    return {
        "artifact_dir": contract.OFFICIAL_ARTIFACT_DIR.as_posix(),
        "manifest_path": contract.OFFICIAL_MANIFEST_PATH.as_posix(),
        "manifest_sha256": contract.OFFICIAL_MANIFEST_SHA256,
        "payload_path": contract.OFFICIAL_PAYLOAD_PATH.as_posix(),
        "payload_sha256": contract.OFFICIAL_PAYLOAD_SHA256,
        "verifier_path": contract.OFFICIAL_VERIFIER_PATH.as_posix(),
        "verifier_sha256": contract.OFFICIAL_VERIFIER_SHA256,
        "exporter_path": contract.OFFICIAL_EXPORTER_PATH.as_posix(),
        "exporter_sha256": contract.OFFICIAL_EXPORTER_SHA256,
        "test_path": contract.OFFICIAL_TEST_PATH.as_posix(),
        "test_sha256": contract.OFFICIAL_TEST_SHA256,
        "bound_root": {
            "file_offset": contract.OFFICIAL_ROOT_OFFSET,
            "gba_address": _gba(contract.OFFICIAL_ROOT_OFFSET),
            "entry_sha256": contract.OFFICIAL_ROOT_ENTRY_SHA256,
            "instruction_count": contract.OFFICIAL_ARM_INSTRUCTION_COUNT,
            "instruction_bytes": contract.OFFICIAL_ARM_INSTRUCTION_BYTES,
            "frontier_count": contract.OFFICIAL_ARM_FRONTIER_COUNT,
            "return_offsets": list(contract.OFFICIAL_ARM_RETURN_OFFSETS),
        },
    }


def _read_rom(root: Path) -> bytes:
    rom = _safe_file(root, contract.ROM_PATH).read_bytes()
    if len(rom) != contract.ROM_SIZE or _sha(rom) != contract.ROM_SHA256:
        raise ValueError("base ROM identity changed")
    return rom


def _coverage_owner(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_raw = _safe_file(root, contract.PRECOVERAGE_DIR / contract.MANIFEST_NAME).read_bytes()
    archive_raw = _safe_file(root, contract.PRECOVERAGE_DIR / "rom-byte-coverage.json.gz").read_bytes()
    if _sha(manifest_raw) != contract.PRECOVERAGE_MANIFEST_SHA256:
        raise ValueError("immutable precoverage manifest identity changed")
    if len(archive_raw) != contract.PRECOVERAGE_ARCHIVE_SIZE or _sha(archive_raw) != contract.PRECOVERAGE_ARCHIVE_SHA256:
        raise ValueError("immutable precoverage archive identity changed")
    manifest = json.loads(manifest_raw.decode("utf-8"))
    expected_file = {
        "compression": "gzip",
        "sha256": contract.PRECOVERAGE_ARCHIVE_SHA256,
        "size": contract.PRECOVERAGE_ARCHIVE_SIZE,
        "uncompressed_sha256": contract.PRECOVERAGE_RAW_SHA256,
        "uncompressed_size": contract.PRECOVERAGE_RAW_SIZE,
    }
    if manifest != {"files": {"rom-byte-coverage.json.gz": expected_file}, "schema": "rom-byte-coverage-precoverage-v1"}:
        raise ValueError("immutable precoverage manifest contract changed")
    raw = gzip.decompress(archive_raw)
    if len(raw) != contract.PRECOVERAGE_RAW_SIZE or _sha(raw) != contract.PRECOVERAGE_RAW_SHA256:
        raise ValueError("immutable precoverage payload identity changed")
    coverage = json.loads(raw.decode("utf-8"))
    if coverage.get("schema") != contract.COVERAGE_SCHEMA or coverage.get("base_rom") != {"path": contract.ROM_PATH.as_posix(), "size": contract.ROM_SIZE, "sha256": contract.ROM_SHA256}:
        raise ValueError("current canonical coverage contract changed")
    summary = coverage.get("summary", {})
    expected = {
        "accounted_bytes": contract.ROM_SIZE,
        "classified_bytes": contract.COVERAGE_CLASSIFIED_BYTES,
        "unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES,
        "claim_count": contract.COVERAGE_CLAIM_COUNT,
        "segment_count": contract.COVERAGE_SEGMENT_COUNT,
    }
    if any(summary.get(key) != value for key, value in expected.items()):
        raise ValueError("current canonical coverage summary changed")
    segments = coverage.get("segments")
    if not isinstance(segments, list) or len(segments) != contract.COVERAGE_SEGMENT_COUNT:
        raise ValueError("current canonical coverage segment denominator changed")
    cursor = 0
    owner: dict[str, Any] | None = None
    for row in segments:
        interval = row.get("range")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] != cursor or interval[1] <= cursor:
            raise ValueError("current canonical coverage segments are not contiguous")
        if interval[0] <= contract.CONTINUATION_ROOT < interval[1]:
            owner = row
        cursor = interval[1]
    if cursor != contract.ROM_SIZE or owner is None:
        raise ValueError("current continuation unknown owner missing")
    expected_owner = {
        "range": list(contract.CONTINUATION_RANGE),
        "primary_class": "unknown",
        "primary_claim_ids": [],
        "secondary_claim_ids": [],
    }
    if any(owner.get(key) != value for key, value in expected_owner.items()):
        raise ValueError("current continuation unknown owner changed")
    baseline = {
        "artifact": contract.PRECOVERAGE_DIR.as_posix(),
        "manifest_sha256": contract.PRECOVERAGE_MANIFEST_SHA256,
        "archive_sha256": contract.PRECOVERAGE_ARCHIVE_SHA256,
        "raw_sha256": contract.PRECOVERAGE_RAW_SHA256,
        "classified_bytes": contract.COVERAGE_CLASSIFIED_BYTES,
        "unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES,
    }
    denominator = {
        "schema": contract.COVERAGE_SCHEMA,
        "artifact": contract.PRECOVERAGE_DIR.as_posix(),
        "manifest_sha256": contract.PRECOVERAGE_MANIFEST_SHA256,
        "archive_sha256": contract.PRECOVERAGE_ARCHIVE_SHA256,
        "archive_size": contract.PRECOVERAGE_ARCHIVE_SIZE,
        "raw_sha256": contract.PRECOVERAGE_RAW_SHA256,
        "raw_size": contract.PRECOVERAGE_RAW_SIZE,
        "classified_bytes": contract.COVERAGE_CLASSIFIED_BYTES,
        "unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES,
        "claim_count": contract.COVERAGE_CLAIM_COUNT,
        "segment_count": contract.COVERAGE_SEGMENT_COUNT,
    }
    return {"baseline": baseline, "denominator": denominator}, expected_owner


def _implementation(root: Path) -> dict[str, Any]:
    paths = {key: path.as_posix() for key, path in contract.IMPLEMENTATION_PATHS.items()}
    hashes = {key: _sha(_safe_file(root, path).read_bytes()) for key, path in contract.IMPLEMENTATION_PATHS.items()}
    return {"binding": "contract-exporter-verifier-tests-hash-bound", "paths": paths, "sha256": hashes}


def build_payload(root: Path, rom_override: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rom = _read_rom(root) if rom_override is None else rom_override
    if len(rom) != contract.ROM_SIZE or _sha(rom) != contract.ROM_SHA256:
        raise ValueError("base ROM identity changed")
    decoder = _decoder_identity(root)
    coverage_info, owner = _coverage_owner(root)
    coverage = coverage_info["baseline"]
    coverage_denominator = coverage_info["denominator"]
    official = _read_official_reference(root, rom)
    producer_matches = []
    for offset in range(0, len(rom) - 3, 2):
        first = _u16(rom, offset)
        second = _u16(rom, offset + 2)
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            target = offset + 4 + _sign_extend(((first & 0x07FF) << 12) | ((second & 0x07FF) << 1), 23)
            if target == contract.BL_PRODUCER_TARGET:
                producer_matches.append(offset)
    if producer_matches != [contract.BL_PRODUCER_OFFSET]:
        raise ValueError("unique direct Thumb BL producer denominator changed")
    producer_raw = _bounded(rom, contract.BL_PRODUCER_OFFSET, contract.BL_PRODUCER_END)
    if producer_raw.hex() != contract.BL_PRODUCER_RAW_HEX or _sha(producer_raw) != contract.BL_PRODUCER_SHA256:
        raise ValueError("direct Thumb BL producer bytes changed")
    decoded_target = contract.BL_PRODUCER_OFFSET + 4 + _sign_extend(((_u16(rom, contract.BL_PRODUCER_OFFSET) & 0x07FF) << 12) | ((_u16(rom, contract.BL_PRODUCER_OFFSET + 2) & 0x07FF) << 1), 23)
    if decoded_target != contract.BL_PRODUCER_TARGET:
        raise ValueError("direct Thumb BL producer target changed")
    veneer_bx = _bounded(rom, contract.VENEER_BX_OFFSET, contract.VENEER_BX_END)
    veneer_arm_b = _bounded(rom, contract.VENEER_ARM_B_OFFSET, contract.VENEER_ARM_B_END)
    if veneer_bx.hex() != contract.VENEER_BX_RAW_HEX or _sha(veneer_bx) != contract.VENEER_BX_SHA256 or _u16(rom, contract.VENEER_BX_OFFSET) != 0x4778:
        raise ValueError("Thumb interwork veneer changed")
    if veneer_arm_b.hex() != contract.VENEER_ARM_B_RAW_HEX or _sha(veneer_arm_b) != contract.VENEER_ARM_B_SHA256:
        raise ValueError("ARM interwork veneer changed")
    arm_b_word = _u32(rom, contract.VENEER_ARM_B_OFFSET)
    arm_b_disp = (arm_b_word & 0x00FFFFFF) << 2
    if arm_b_disp & 0x02000000:
        arm_b_disp -= 0x04000000
    if arm_b_word & 0x0F000000 != 0x0A000000 or contract.VENEER_ARM_B_OFFSET + 8 + arm_b_disp != contract.OFFICIAL_ROOT_OFFSET:
        raise ValueError("ARM interwork veneer target changed")
    thumb_nodes, outbound = _thumb_traverse(rom)
    thumb_blocks, thumb_edges = _thumb_blocks(thumb_nodes, outbound, rom)
    thumb_literals = _thumb_literals(rom, thumb_nodes)
    code_ranges = _merge([(node["file_offset"], node["file_offset"] + node["size"]) for node in thumb_nodes])
    literal_ranges = [
        [row["literal_offset"], row["literal_offset"] + 4]
        for row in sorted(thumb_literals, key=lambda item: item["literal_offset"])
    ]
    union_ranges = _merge([(start, end) for start, end in code_ranges + literal_ranges])
    if code_ranges != [list(contract.CONTINUATION_CODE_RANGE)] or literal_ranges != [list(item) for item in contract.CONTINUATION_LITERAL_RANGES] or union_ranges != [list(contract.CONTINUATION_RANGE)]:
        raise ValueError("continuation promotion ranges changed")
    if any(start < contract.CONTINUATION_RANGE[0] or end > contract.CONTINUATION_RANGE[1] for start, end in union_ranges):
        raise ValueError("continuation promotion escaped fixed range")
    packed = b"".join(_bounded(rom, start, end) for start, end in union_ranges)
    if _sha(_bounded(rom, *contract.CONTINUATION_CODE_RANGE)) != contract.CONTINUATION_CODE_SHA256 or _sha(b"".join(_bounded(rom, start, end) for start, end in contract.CONTINUATION_LITERAL_RANGES)) != contract.CONTINUATION_LITERAL_PACKED_SHA256 or _sha(packed) != contract.CONTINUATION_UNION_PACKED_SHA256 or _compact_sha(union_ranges) != contract.CONTINUATION_UNION_RANGE_SHA256:
        raise ValueError("continuation promotion byte identity changed")
    arm_nodes, arm_decoded = _arm_traverse(rom)
    arm_blocks, arm_edges = _arm_blocks(rom, arm_nodes)
    arm_literals = _arm_literals(rom, arm_decoded)
    arm_returns = [node["file_offset"] for node in arm_nodes if node["flow_kind"] == "return"]
    if arm_returns != list(contract.OFFICIAL_ARM_RETURN_OFFSETS):
        raise ValueError("ARM callee return denominator changed")
    if len(arm_nodes) != contract.OFFICIAL_ARM_INSTRUCTION_COUNT or sum(node["size"] for node in arm_nodes) != contract.OFFICIAL_ARM_INSTRUCTION_BYTES:
        raise ValueError("ARM callee instruction denominator changed")
    if any(block["terminator"]["flow_kind"] == "return" and block["terminator"]["mnemonic"] != "bx" for block in arm_blocks) or any(not node["successors"] and node["flow_kind"] != "return" for node in arm_nodes):
        raise ValueError("ARM callee return terminator changed")
    arm_denominators = {
        "instruction_vector_sha256": _compact_sha(arm_nodes),
        "block_vector_sha256": _compact_sha(arm_blocks),
        "edge_vector_sha256": _compact_sha(arm_edges),
        "literal_binding_vector_sha256": _compact_sha(arm_literals),
    }
    if arm_denominators != {
        "instruction_vector_sha256": contract.OFFICIAL_ARM_INSTRUCTION_VECTOR_SHA256,
        "block_vector_sha256": contract.OFFICIAL_ARM_BLOCK_VECTOR_SHA256,
        "edge_vector_sha256": contract.OFFICIAL_ARM_EDGE_VECTOR_SHA256,
        "literal_binding_vector_sha256": contract.OFFICIAL_ARM_LITERAL_VECTOR_SHA256,
    }:
        raise ValueError("ARM callee canonical denominator changed")
    thumb_denominators = {
        "instruction_vector_sha256": _compact_sha(thumb_nodes),
        "block_vector_sha256": _compact_sha(thumb_blocks),
        "edge_vector_sha256": _compact_sha(thumb_edges),
        "literal_binding_vector_sha256": _compact_sha(thumb_literals),
    }
    claims = [{
        "id": "continuation-code-06108a-0610d4",
        "range": list(contract.CONTINUATION_CODE_RANGE),
        "size": contract.CONTINUATION_CODE_BYTES,
        "semantic_class": "armv4t_boot_interwork_continuation_code",
        "sha256": contract.CONTINUATION_CODE_SHA256,
        "baseline_unknown_only": True,
    }]
    claims.extend({
        "id": f"continuation-literal-{index:02d}-{start:06x}",
        "range": [start, end],
        "size": end - start,
        "semantic_class": "thumb_pc_relative_literal_word",
        "sha256": _sha(_bounded(rom, start, end)),
        "baseline_unknown_only": True,
    } for index, (start, end) in enumerate(contract.CONTINUATION_LITERAL_RANGES, 1))
    implementation = _implementation(root)
    return {
        "schema": contract.SCHEMA,
        "rom": {"path": contract.ROM_PATH.as_posix(), "size": contract.ROM_SIZE, "sha256": contract.ROM_SHA256},
        "decoder": decoder,
        "coverage_baseline": coverage,
        "coverage_denominator": coverage_denominator,
        "current_unknown_owner": owner,
        "official_boot_interwork_artifact": official,
        "producer": {
            "unique_direct_bl_offsets": producer_matches,
            "direct_bl": {
                "mode": "thumb",
                "file_offset": contract.BL_PRODUCER_OFFSET,
                "gba_address": _gba(contract.BL_PRODUCER_OFFSET),
                "range": [contract.BL_PRODUCER_OFFSET, contract.BL_PRODUCER_END],
                "raw_hex": producer_raw.hex(),
                "sha256": contract.BL_PRODUCER_SHA256,
                "target_offset": contract.BL_PRODUCER_TARGET,
                "target_gba_address": _gba(contract.BL_PRODUCER_TARGET),
                "flow_kind": "call",
            },
            "continuation_root": contract.CONTINUATION_ROOT,
            "continuation_root_gba_address": _gba(contract.CONTINUATION_ROOT),
            "continuation_mode": "thumb",
            "callee_arm_root": contract.OFFICIAL_ROOT_OFFSET,
        },
        "thumb_continuation": {
            "root": {
                "mode": "thumb",
                "file_offset": contract.CONTINUATION_ROOT,
                "gba_address": _gba(contract.CONTINUATION_ROOT),
                "entry_size": 4,
                "entry_sha256": _sha(_bounded(rom, contract.CONTINUATION_ROOT, contract.CONTINUATION_ROOT + 4)),
                "source_bl_offset": contract.BL_PRODUCER_OFFSET,
                "static_call_continuation": True,
            },
            "instructions": thumb_nodes,
            "blocks": thumb_blocks,
            "edges": thumb_edges,
            "outbound_edges": outbound,
            "frontier_count": contract.CONTINUATION_FRONTIER_COUNT,
            "frontiers": [],
            "literal_bindings": thumb_literals,
            "denominators": thumb_denominators,
        },
        "callee_arm_closure": {
            "root": {
                "mode": "arm",
                "file_offset": contract.OFFICIAL_ROOT_OFFSET,
                "gba_address": _gba(contract.OFFICIAL_ROOT_OFFSET),
                "entry_size": 4,
                "entry_sha256": contract.OFFICIAL_ROOT_ENTRY_SHA256,
            },
            "traversal_status": "closed",
            "instruction_count": len(arm_nodes),
            "instruction_bytes": sum(node["size"] for node in arm_nodes),
            "block_count": len(arm_blocks),
            "edge_count": len(arm_edges),
            "frontier_count": 0,
            "return_offsets": arm_returns,
            "all_terminal_paths_end_in_bx_lr": True,
            "instructions": arm_nodes,
            "blocks": arm_blocks,
            "edges": arm_edges,
            "literal_bindings": arm_literals,
            "denominators": arm_denominators,
        },
        "promotion": {
            "promotion_batch": contract.SCHEMA,
            "primary_class": "armv4t_boot_interwork_continuation",
            "claim_kind": "boot_interwork_continuation_current_unknown_bytes",
            "target_range": list(contract.CONTINUATION_RANGE),
            "code_ranges": code_ranges,
            "literal_ranges": literal_ranges,
            "union_ranges": union_ranges,
            "code_bytes": contract.CONTINUATION_CODE_BYTES,
            "literal_bytes": contract.CONTINUATION_LITERAL_BYTES,
            "promotion_bytes": contract.CONTINUATION_PROMOTION_BYTES,
            "code_sha256": contract.CONTINUATION_CODE_SHA256,
            "literal_packed_sha256": contract.CONTINUATION_LITERAL_PACKED_SHA256,
            "union_range_sha256": contract.CONTINUATION_UNION_RANGE_SHA256,
            "union_packed_sha256": contract.CONTINUATION_UNION_PACKED_SHA256,
            "baseline_unknown_only": True,
            "claims": claims,
        },
        "coverage_projection": {
            "baseline_unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES,
            "promoted_bytes": contract.CONTINUATION_PROMOTION_BYTES,
            "remaining_unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES - contract.CONTINUATION_PROMOTION_BYTES,
            "coverage_file_written": False,
        },
        "summary": {
            "continuation_instruction_count": len(thumb_nodes),
            "continuation_code_bytes": contract.CONTINUATION_CODE_BYTES,
            "continuation_block_count": len(thumb_blocks),
            "continuation_frontier_count": 0,
            "literal_binding_count": len(thumb_literals),
            "literal_bytes": contract.CONTINUATION_LITERAL_BYTES,
            "outbound_edge_count": len(outbound),
            "promotion_bytes": contract.CONTINUATION_PROMOTION_BYTES,
            "callee_arm_instruction_count": len(arm_nodes),
            "callee_arm_instruction_bytes": sum(node["size"] for node in arm_nodes),
            "callee_arm_block_count": len(arm_blocks),
            "callee_arm_edge_count": len(arm_edges),
            "callee_arm_frontier_count": 0,
            "callee_arm_return_count": len(arm_returns),
            "coverage_baseline_unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES,
        },
        "implementation": implementation,
        "scope": dict(contract.SCOPE),
        "limitations": list(contract.LIMITATIONS),
    }


def _validate_output(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    requested = output if output.is_absolute() else root / output
    requested = requested.absolute()
    allowed = (root / contract.EXPERIMENT_ROOT).resolve()
    official = (root / contract.OFFICIAL_OUTPUT).absolute()
    if requested == root or requested == allowed or not (allowed in requested.parents or requested == official):
        raise ValueError("candidate output must be below the experiment root")
    if requested.is_symlink():
        raise ValueError("candidate output uses a symlink")
    if requested.exists():
        if not requested.is_dir():
            raise ValueError("candidate output is not a directory")
        members = list(requested.rglob("*"))
        actual = {member.relative_to(requested).as_posix() for member in members if member.is_file()}
        if actual != {contract.MANIFEST_NAME, contract.PAYLOAD_NAME} or any(member.is_symlink() for member in members):
            raise ValueError("candidate output contains foreign files")
    return requested


def _manifest(payload: dict[str, Any], payload_raw: bytes, rel: Path) -> dict[str, Any]:
    return {
        "schema": f"{contract.SCHEMA}-artifact-manifest-v1",
        "artifact_schema": contract.SCHEMA,
        "artifact_status": "candidate",
        "rom": payload["rom"],
        "decoder": payload["decoder"],
        "coverage_baseline": payload["coverage_baseline"],
        "coverage_denominator": payload["coverage_denominator"],
        "current_unknown_owner": payload["current_unknown_owner"],
        "official_boot_interwork_artifact": payload["official_boot_interwork_artifact"],
        "promotion": payload["promotion"],
        "summary": payload["summary"],
        "scope": payload["scope"],
        "limitations": payload["limitations"],
        "implementation": payload["implementation"],
        "producer": {
            "command": ["python3", "-I", "-S", "tools/export_rom_boot_interwork_continuation.py", "--root", ".", "--output", rel.as_posix()],
        },
        "verification": {
            "schema": contract.VERIFY_SCHEMA,
            "command": ["python3", "-I", "-S", "tools/verify_rom_boot_interwork_continuation.py", "--root", ".", "--artifact", rel.as_posix()],
            "verifier_path": contract.IMPLEMENTATION_PATHS["verifier"].as_posix(),
        },
        "files": {
            contract.PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
        },
    }


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    target = _validate_output(root, Path(output))
    payload = build_payload(root)
    payload_raw = _canonical(payload)
    rel = target.relative_to(root)
    manifest = _manifest(payload, payload_raw, rel)
    manifest_raw = _canonical(manifest)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".boot-interwork-continuation-", dir=target.parent) as temp:
        stage = Path(temp) / "candidate"
        stage.mkdir()
        (stage / contract.PAYLOAD_NAME).write_bytes(payload_raw)
        (stage / contract.MANIFEST_NAME).write_bytes(manifest_raw)
        try:
            from tools import verify_rom_boot_interwork_continuation as verifier
            report = verifier.verify_artifact(root, stage)
        except Exception as error:
            raise ValueError(f"candidate independent verification failed: {error}") from error
        if not report.get("verified"):
            raise ValueError(f"candidate independent verification failed: {report.get('errors', [])}")
        manifest["artifact_status"] = "accepted"
        manifest["verification"]["exit_code"] = 0
        manifest["verification"]["report"] = report
        (stage / contract.MANIFEST_NAME).write_bytes(_canonical(manifest))
        if target.exists():
            shutil.rmtree(target)
        os.replace(stage, target)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=contract.DEFAULT_CANDIDATE)
    args = parser.parse_args()
    manifest = export_artifact(args.root, args.output)
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
