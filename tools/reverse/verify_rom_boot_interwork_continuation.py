#!/usr/bin/env python3
"""Independently verify the boot interwork call-continuation candidate.

The verifier deliberately decodes the ROM itself and never imports the
product exporter.  The accepted packet is therefore checked against raw
bytes, the frozen coverage owner, and the existing official interwork packet.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import json
from pathlib import Path
import sys
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
_THUMB_IDS = frozenset(getattr(arm_const, name) for name in _THUMB_NAMES if hasattr(arm_const, name))
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


def _vsha(value: Any) -> str:
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
    result = (root / relative).resolve(strict=True)
    if result != root and root not in result.parents:
        raise ValueError(f"repository input escapes root: {relative}")
    if not result.is_file():
        raise ValueError(f"repository input is not a file: {relative}")
    return result


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
    return getattr(ins, "cc", arm_const.ARM_CC_AL) not in (arm_const.ARM_CC_AL, arm_const.ARM_CC_INVALID)


def _writes_pc(ins: Any) -> bool:
    for operand in ins.operands:
        if operand.type == arm_const.ARM_OP_REG and operand.reg == arm_const.ARM_REG_PC and operand.access & CS_AC_WRITE:
            return True
    try:
        _, writes = ins.regs_access()
    except (AttributeError, capstone.CsError):
        writes = []
    return arm_const.ARM_REG_PC in writes


def _thumb_flow(raw: bytes, offset: int) -> dict[str, Any] | None:
    first = int.from_bytes(raw[:2], "little")
    if len(raw) == 4:
        second = int.from_bytes(raw[2:4], "little")
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            encoded = ((first & 0x07FF) << 12) | ((second & 0x07FF) << 1)
            return {"flow_kind": "call", "size": 4, "conditional": False, "target": offset + 4 + _sign_extend(encoded, 23)}
    if first & 0xFF00 == 0xDF00:
        return {"flow_kind": "supervisor_call", "size": 2, "conditional": False, "swi_immediate": first & 0xFF}
    condition = (first >> 8) & 0xF
    if first & 0xF000 == 0xD000 and condition <= 0xD:
        return {"flow_kind": "conditional_branch", "size": 2, "conditional": True, "target": offset + 4 + _sign_extend((first & 0xFF) << 1, 9)}
    if first & 0xF800 == 0xE000:
        return {"flow_kind": "unconditional_branch", "size": 2, "conditional": False, "target": offset + 4 + _sign_extend((first & 0x07FF) << 1, 12)}
    if first & 0xFF87 == 0x4700:
        register = (first >> 3) & 0xF
        return {"flow_kind": "return" if register == 14 else "indirect_branch", "size": 2, "conditional": False, "register": register}
    return None


def _decode_thumb(rom: bytes, offset: int, engine: Cs) -> dict[str, Any]:
    decoded = tuple(engine.disasm(_bounded(rom, offset, offset + 4), contract.ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].address != contract.ROM_BASE + offset:
        raise ValueError(f"Thumb decode failure at 0x{offset:06X}")
    ins = decoded[0]
    raw = _bounded(rom, offset, offset + ins.size)
    if ins.id not in _THUMB_IDS or ins.size not in (2, 4):
        raise ValueError(f"unsupported Thumb ARMv4T instruction at 0x{offset:06X}")
    if ins.size == 4 and not (ins.id == arm_const.ARM_INS_BL and _u16(rom, offset) & 0xF800 == 0xF000 and _u16(rom, offset + 2) & 0xF800 == 0xF800):
        raise ValueError(f"unexpected Thumb-32 instruction at 0x{offset:06X}")
    flow = _thumb_flow(raw, offset)
    if ins.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL, arm_const.ARM_INS_BX, arm_const.ARM_INS_SVC) and flow is None:
        raise ValueError(f"Thumb control-flow mismatch at 0x{offset:06X}")
    if flow is not None:
        expected = {"unconditional_branch": arm_const.ARM_INS_B, "conditional_branch": arm_const.ARM_INS_B, "call": arm_const.ARM_INS_BL, "return": arm_const.ARM_INS_BX, "indirect_branch": arm_const.ARM_INS_BX, "supervisor_call": arm_const.ARM_INS_SVC}[flow["flow_kind"]]
        if ins.id != expected or ins.size != flow["size"]:
            raise ValueError(f"Thumb control-flow mismatch at 0x{offset:06X}")
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []
    if flow is not None and flow["flow_kind"] in {"call", "conditional_branch", "unconditional_branch"}:
        target = flow["target"]
        if 0 <= target < len(rom) and target % 2 == 0:
            successors.append({"kind": "call_target" if flow["flow_kind"] == "call" else "branch_target", "mode": "thumb", "file_offset": target})
        else:
            frontiers.append({"reason": "direct_target_outside_or_misaligned", "target_file_offset": target})
        if flow["flow_kind"] in {"call", "conditional_branch"}:
            successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": offset + ins.size})
        flow_kind = flow["flow_kind"]
    elif flow is not None and flow["flow_kind"] == "supervisor_call":
        frontiers.append({"reason": "bios_swi_external", "swi_immediate": flow["swi_immediate"]})
        successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": offset + ins.size})
        flow_kind = flow["flow_kind"]
    elif flow is not None:
        flow_kind = flow["flow_kind"]
        if flow_kind == "indirect_branch":
            frontiers.append({"reason": "indirect_pc_target"})
    elif _writes_pc(ins):
        flow_kind = "indirect_branch"
        frontiers.append({"reason": "indirect_pc_target"})
    else:
        flow_kind = "linear"
        successors.append({"kind": "fallthrough", "mode": "thumb", "file_offset": offset + ins.size})
    successors.sort(key=lambda row: (_EDGE_ORDER[row["kind"]], row["file_offset"]))
    return {"mode": "thumb", "file_offset": offset, "size": ins.size, "raw_hex": raw.hex(), "bytes_sha256": _sha(raw), "mnemonic": ins.mnemonic, "op_str": ins.op_str, "conditional": flow["conditional"] if flow is not None else _conditional(ins), "flow_kind": flow_kind, "raw_flow_kind": flow["flow_kind"] if flow is not None else None, "successors": successors, "frontiers": frontiers}


def _thumb_rebuild(rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[list[int]]]:
    engine = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    engine.detail = True
    engine.skipdata = False
    pending = [contract.CONTINUATION_ROOT]
    scheduled = {contract.CONTINUATION_ROOT}
    nodes: dict[int, dict[str, Any]] = {}
    outbound: list[dict[str, Any]] = []
    lo, hi = contract.CONTINUATION_CODE_RANGE
    while pending:
        offset = heapq.heappop(pending)
        if offset in nodes:
            continue
        if not lo <= offset < hi or offset % 2:
            raise ValueError("Thumb continuation root escaped fixed code range")
        node = _decode_thumb(rom, offset, engine)
        if offset + node["size"] > hi or node["frontiers"]:
            raise ValueError(f"Thumb continuation frontier at 0x{offset:06X}")
        nodes[offset] = node
        for edge in node["successors"]:
            target = edge["file_offset"]
            if lo <= target < hi:
                if target not in scheduled:
                    scheduled.add(target)
                    heapq.heappush(pending, target)
            else:
                outbound.append({"source_instruction_offset": offset, "kind": edge["kind"], "mode": "thumb", "target_offset": target, "target_gba_address": _gba(target), "resolution": "opaque_external_edge"})
    cursor = lo
    offsets: list[int] = []
    while cursor < hi:
        offsets.append(cursor)
        if cursor not in nodes:
            raise ValueError("Thumb continuation instruction gap")
        cursor += nodes[cursor]["size"]
    if sorted(nodes) != offsets or len(nodes) != contract.CONTINUATION_INSTRUCTION_COUNT or sum(node["size"] for node in nodes.values()) != contract.CONTINUATION_CODE_BYTES:
        raise ValueError("Thumb continuation instruction denominator changed")
    outbound.sort(key=lambda row: (row["source_instruction_offset"], _EDGE_ORDER[row["kind"]], row["target_offset"]))
    if len(outbound) != contract.CONTINUATION_EXTERNAL_EDGE_COUNT:
        raise ValueError("Thumb continuation outbound denominator changed")
    ordered = [nodes[offset] for offset in offsets]
    blocks, edges = _thumb_blocks(ordered, outbound, rom)
    literals = _thumb_literals(rom, ordered)
    return ordered, blocks, edges, outbound, literals


def _thumb_blocks(nodes: list[dict[str, Any]], outbound: list[dict[str, Any]], rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
        internal = [edge for edge in predecessor["successors"] if edge["file_offset"] in by_offset]
        if predecessor["flow_kind"] != "linear" or len(internal) != 1 or internal[0]["file_offset"] != offset or predecessor["file_offset"] + predecessor["size"] != offset:
            starts.add(offset)
    block_ids: dict[int, str] = {}
    blocks: list[dict[str, Any]] = []
    for start in sorted(starts):
        members: list[dict[str, Any]] = []
        offset = start
        while offset in by_offset and offset not in block_ids:
            node = by_offset[offset]
            members.append(node)
            block_ids[offset] = f"block-thumb-{start:06x}"
            internal = [edge for edge in node["successors"] if edge["file_offset"] in by_offset]
            if node["flow_kind"] != "linear" or len(internal) != 1:
                break
            target = internal[0]["file_offset"]
            if target in starts or target != offset + node["size"]:
                break
            offset = target
        if not members:
            continue
        last = members[-1]
        end = last["file_offset"] + last["size"]
        blocks.append({"id": block_ids[start], "mode": "thumb", "range": [start, end], "gba_range": [_gba(start), _gba(end)], "instruction_count": len(members), "bytes_sha256": _sha(_bounded(rom, start, end)), "terminator": {"file_offset": last["file_offset"], "size": last["size"], "raw_hex": last["raw_hex"], "mnemonic": last["mnemonic"], "op_str": last["op_str"], "flow_kind": last["flow_kind"], "conditional": last["conditional"]}, "successors": []})
    if len(block_ids) != len(nodes) or len(blocks) != contract.CONTINUATION_BLOCK_COUNT:
        raise ValueError("Thumb continuation block denominator changed")
    external_by_key = {(row["source_instruction_offset"], row["kind"], row["target_offset"]): row for row in outbound}
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["file_offset"]
        for edge in by_offset[source]["successors"]:
            target = edge["file_offset"]
            if target in by_offset:
                record = {"source_block_id": block["id"], "source_instruction_offset": source, "kind": edge["kind"], "mode": "thumb", "target_offset": target, "target_gba_address": _gba(target), "target_block_id": block_ids[target], "resolution": "internal"}
            else:
                try:
                    record = {**external_by_key[(source, edge["kind"], target)], "source_block_id": block["id"]}
                except KeyError as error:
                    raise ValueError("Thumb continuation external edge binding changed") from error
            block["successors"].append(record)
            edges.append(record)
    return blocks, edges


def _thumb_literals(rom: bytes, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected = {(0x0610A2, 0x0610D4), (0x0610AA, 0x0610D8), (0x0610AE, 0x0610DC), (0x0610BA, 0x0610E0), (0x0610CA, 0x0610E4)}
    rows: list[dict[str, Any]] = []
    starts = {start for start, _ in contract.CONTINUATION_LITERAL_RANGES}
    for node in nodes:
        offset = node["file_offset"]
        if node["size"] != 2 or _u16(rom, offset) & 0xF800 != 0x4800:
            continue
        literal = ((offset + 4) & ~3) + (_u16(rom, offset) & 0xFF) * 4
        if literal not in starts or literal + 4 > contract.CONTINUATION_END:
            raise ValueError("Thumb literal escaped fixed pool")
        raw = _bounded(rom, literal, literal + 4)
        rows.append({"load_offset": offset, "load_gba_address": _gba(offset), "literal_offset": literal, "literal_gba_address": _gba(literal), "raw_hex": raw.hex(), "value": f"0x{int.from_bytes(raw, 'little'):08X}"})
    rows.sort(key=lambda row: (row["load_offset"], row["literal_offset"]))
    if {(row["load_offset"], row["literal_offset"]) for row in rows} != expected or len(rows) != contract.CONTINUATION_LITERAL_BINDING_COUNT:
        raise ValueError("Thumb literal binding denominator changed")
    return rows


def _decode_arm(rom: bytes, offset: int, engine: Cs) -> dict[str, Any]:
    decoded = tuple(engine.disasm(_bounded(rom, offset, offset + 4), contract.ROM_BASE + offset, count=1))
    if len(decoded) != 1 or decoded[0].size != 4:
        raise ValueError(f"ARM callee decode failure at 0x{offset:06X}")
    ins = decoded[0]
    raw = _bounded(rom, offset, offset + 4)
    if ins.id not in _ARM_IDS or _u32(rom, offset) >> 28 == 0xF:
        raise ValueError(f"unsupported ARM callee instruction at 0x{offset:06X}")
    conditional = _conditional(ins)
    successors: list[dict[str, Any]] = []
    if ins.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL):
        if len(ins.operands) != 1 or ins.operands[0].type != arm_const.ARM_OP_IMM:
            raise ValueError("indirect ARM callee branch")
        target = ins.operands[0].imm - contract.ROM_BASE
        successors.append({"kind": "call_target" if ins.id == arm_const.ARM_INS_BL else "branch_target", "mode": "arm", "file_offset": target})
        if ins.id == arm_const.ARM_INS_BL or conditional:
            successors.append({"kind": "fallthrough", "mode": "arm", "file_offset": offset + 4})
        flow_kind = "call" if ins.id == arm_const.ARM_INS_BL else ("conditional_branch" if conditional else "unconditional_branch")
    elif ins.id == arm_const.ARM_INS_BX:
        if conditional or len(ins.operands) != 1 or ins.operands[0].type != arm_const.ARM_OP_REG or ins.operands[0].reg != arm_const.ARM_REG_LR:
            raise ValueError("ARM callee BX is not BX lr")
        flow_kind = "return"
    elif ins.id == arm_const.ARM_INS_SVC or _writes_pc(ins):
        raise ValueError("ARM callee frontier")
    else:
        successors.append({"kind": "fallthrough", "mode": "arm", "file_offset": offset + 4})
        flow_kind = "linear"
    successors.sort(key=lambda row: (_EDGE_ORDER[row["kind"]], row["file_offset"]))
    return {"mode": "arm", "file_offset": offset, "size": 4, "bytes_sha256": _sha(raw), "mnemonic": ins.mnemonic, "op_str": ins.op_str, "conditional": conditional, "flow_kind": flow_kind, "successors": successors, "frontiers": []}


def _arm_rebuild(rom: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
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
            raise ValueError("ARM callee escaped fixed closure")
        node = _decode_arm(rom, offset, engine)
        nodes[offset] = node
        decoded[offset] = tuple(engine.disasm(_bounded(rom, offset, offset + 4), contract.ROM_BASE + offset, count=1))[0]
        for edge in node["successors"]:
            target = edge["file_offset"]
            if not contract.OFFICIAL_ROOT_OFFSET <= target < contract.OFFICIAL_ROOT_END or target % 4:
                raise ValueError("ARM callee successor escaped fixed closure")
            if target not in scheduled:
                scheduled.add(target)
                heapq.heappush(pending, target)
    offsets = list(range(contract.OFFICIAL_ROOT_OFFSET, contract.OFFICIAL_ROOT_END, 4))
    if sorted(nodes) != offsets or len(nodes) != contract.OFFICIAL_ARM_INSTRUCTION_COUNT:
        raise ValueError("ARM callee instruction denominator changed")
    ordered = [nodes[offset] for offset in offsets]
    blocks, edges = _arm_blocks(rom, ordered)
    literals = _arm_literals(rom, decoded)
    returns = [node["file_offset"] for node in ordered if node["flow_kind"] == "return"]
    if returns != list(contract.OFFICIAL_ARM_RETURN_OFFSETS) or any(block["terminator"]["flow_kind"] == "return" and block["terminator"]["mnemonic"] != "bx" for block in blocks) or any(not node["successors"] and node["flow_kind"] != "return" for node in ordered):
        raise ValueError("ARM callee return denominator changed")
    denoms = {_key: _vsha(value) for _key, value in (("instruction_vector_sha256", ordered), ("block_vector_sha256", blocks), ("edge_vector_sha256", edges), ("literal_binding_vector_sha256", literals))}
    expected = {"instruction_vector_sha256": contract.OFFICIAL_ARM_INSTRUCTION_VECTOR_SHA256, "block_vector_sha256": contract.OFFICIAL_ARM_BLOCK_VECTOR_SHA256, "edge_vector_sha256": contract.OFFICIAL_ARM_EDGE_VECTOR_SHA256, "literal_binding_vector_sha256": contract.OFFICIAL_ARM_LITERAL_VECTOR_SHA256}
    if denoms != expected:
        raise ValueError("ARM callee canonical denominator changed")
    return ordered, blocks, edges, literals


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
    block_ids: dict[int, str] = {}
    for start in sorted(starts):
        members: list[dict[str, Any]] = []
        offset = start
        while offset in by_offset and offset not in block_ids:
            node = by_offset[offset]
            members.append(node)
            block_ids[offset] = f"block-arm-{start:06x}"
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
        blocks.append({"id": block_ids[start], "mode": "arm", "range": [start, end], "instruction_count": len(members), "bytes_sha256": _sha(_bounded(rom, start, end)), "terminator": {"file_offset": last["file_offset"], "size": 4, "mnemonic": last["mnemonic"], "op_str": last["op_str"], "flow_kind": last["flow_kind"], "conditional": last["conditional"]}, "successors": []})
    if len(blocks) != contract.OFFICIAL_ARM_BLOCK_COUNT or len(block_ids) != len(nodes):
        raise ValueError("ARM callee block denominator changed")
    edges: list[dict[str, Any]] = []
    for block in blocks:
        source = block["terminator"]["file_offset"]
        for edge in by_offset[source]["successors"]:
            target = edge["file_offset"]
            record = {"kind": edge["kind"], "mode": "arm", "file_offset": target, "block_id": block_ids[target]}
            block["successors"].append(record)
            edges.append({"source_block_id": block["id"], **record})
    if len(edges) != contract.OFFICIAL_ARM_EDGE_COUNT:
        raise ValueError("ARM callee edge denominator changed")
    return blocks, edges


def _arm_literals(rom: bytes, decoded: dict[int, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset, ins in sorted(decoded.items()):
        if ins.id != arm_const.ARM_INS_LDR:
            continue
        operands = [operand for operand in ins.operands if operand.type == arm_const.ARM_OP_MEM and operand.mem.base == arm_const.ARM_REG_PC]
        if not operands:
            continue
        if len(operands) != 1:
            raise ValueError("ambiguous ARM literal binding")
        literal = offset + 8 + operands[0].mem.disp
        if literal % 4 or literal < contract.OFFICIAL_ROOT_END or literal + 4 > 0x03E0:
            raise ValueError("ARM literal escaped fixed pool")
        rows.append({"load_offset": offset, "literal_offset": literal, "value": f"0x{_u32(rom, literal):08X}"})
    rows.sort(key=lambda row: row["literal_offset"])
    if len(rows) != 9:
        raise ValueError("ARM literal denominator changed")
    return rows


def _read_rom(root: Path) -> bytes:
    raw = _safe_file(root, contract.ROM_PATH).read_bytes()
    if len(raw) != contract.ROM_SIZE or _sha(raw) != contract.ROM_SHA256:
        raise ValueError("base ROM identity changed")
    return raw


def _read_coverage(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_raw = _safe_file(root, contract.PRECOVERAGE_DIR / contract.MANIFEST_NAME).read_bytes()
    archive_raw = _safe_file(root, contract.PRECOVERAGE_DIR / "rom-byte-coverage.json.gz").read_bytes()
    if _sha(manifest_raw) != contract.PRECOVERAGE_MANIFEST_SHA256:
        raise ValueError("immutable precoverage manifest identity changed")
    if len(archive_raw) != contract.PRECOVERAGE_ARCHIVE_SIZE or _sha(archive_raw) != contract.PRECOVERAGE_ARCHIVE_SHA256:
        raise ValueError("immutable precoverage archive identity changed")
    expected_file = {"compression": "gzip", "sha256": contract.PRECOVERAGE_ARCHIVE_SHA256, "size": contract.PRECOVERAGE_ARCHIVE_SIZE, "uncompressed_sha256": contract.PRECOVERAGE_RAW_SHA256, "uncompressed_size": contract.PRECOVERAGE_RAW_SIZE}
    manifest = json.loads(manifest_raw.decode("utf-8"))
    if manifest != {"files": {"rom-byte-coverage.json.gz": expected_file}, "schema": "rom-byte-coverage-precoverage-v1"}:
        raise ValueError("immutable precoverage manifest contract changed")
    raw = gzip.decompress(archive_raw)
    if len(raw) != contract.PRECOVERAGE_RAW_SIZE or _sha(raw) != contract.PRECOVERAGE_RAW_SHA256:
        raise ValueError("immutable precoverage payload identity changed")
    value = json.loads(raw.decode("utf-8"))
    expected_base = {"path": contract.ROM_PATH.as_posix(), "size": contract.ROM_SIZE, "sha256": contract.ROM_SHA256}
    if value.get("schema") != contract.COVERAGE_SCHEMA or value.get("base_rom") != expected_base:
        raise ValueError("current canonical coverage contract changed")
    summary = value.get("summary", {})
    for key, expected in (("accounted_bytes", contract.ROM_SIZE), ("classified_bytes", contract.COVERAGE_CLASSIFIED_BYTES), ("unknown_bytes", contract.COVERAGE_UNKNOWN_BYTES), ("segment_count", contract.COVERAGE_SEGMENT_COUNT)):
        if summary.get(key) != expected:
            raise ValueError("current canonical coverage summary changed")
    if summary.get("claim_count") != contract.COVERAGE_CLAIM_COUNT:
        raise ValueError("current canonical coverage claim denominator changed")
    segments = value.get("segments")
    if not isinstance(segments, list) or len(segments) != contract.COVERAGE_SEGMENT_COUNT:
        raise ValueError("current canonical coverage segments changed")
    cursor = 0
    owner = None
    for row in segments:
        interval = row.get("range")
        if not isinstance(interval, list) or len(interval) != 2 or interval[0] != cursor or interval[1] <= cursor:
            raise ValueError("current canonical coverage segments are not contiguous")
        if interval[0] <= contract.CONTINUATION_ROOT < interval[1]:
            owner = row
        cursor = interval[1]
    if cursor != contract.ROM_SIZE or owner is None:
        raise ValueError("current continuation unknown owner missing")
    expected_owner = {"range": list(contract.CONTINUATION_RANGE), "primary_class": "unknown", "primary_claim_ids": [], "secondary_claim_ids": []}
    if any(owner.get(key) != expected for key, expected in expected_owner.items()):
        raise ValueError("current continuation unknown owner changed")
    return {"artifact": contract.PRECOVERAGE_DIR.as_posix(), "manifest_sha256": contract.PRECOVERAGE_MANIFEST_SHA256, "archive_sha256": contract.PRECOVERAGE_ARCHIVE_SHA256, "raw_sha256": contract.PRECOVERAGE_RAW_SHA256, "classified_bytes": contract.COVERAGE_CLASSIFIED_BYTES, "unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES}, expected_owner


def _official_reference(root: Path) -> dict[str, Any]:
    manifest_raw = _safe_file(root, contract.OFFICIAL_MANIFEST_PATH).read_bytes()
    payload_raw = _safe_file(root, contract.OFFICIAL_PAYLOAD_PATH).read_bytes()
    if _sha(manifest_raw) != contract.OFFICIAL_MANIFEST_SHA256 or _sha(payload_raw) != contract.OFFICIAL_PAYLOAD_SHA256:
        raise ValueError("official boot-interwork artifact identity changed")
    manifest = json.loads(manifest_raw.decode("utf-8"))
    payload = json.loads(payload_raw.decode("utf-8"))
    if manifest.get("artifact_schema") != "rom-boot-interwork-v1" or manifest.get("files", {}).get(contract.OFFICIAL_PAYLOAD_PATH.name) != {"sha256": contract.OFFICIAL_PAYLOAD_SHA256, "size": len(payload_raw)}:
        raise ValueError("official boot-interwork manifest binding changed")
    if payload.get("schema") != "rom-boot-interwork-v1" or payload.get("rom", {}).get("sha256") != contract.ROM_SHA256:
        raise ValueError("official boot-interwork payload contract changed")
    impl = manifest.get("producer", {})
    expected_implementation = {
        "exporter": {"path": contract.OFFICIAL_EXPORTER_PATH.as_posix(), "sha256": contract.OFFICIAL_EXPORTER_SHA256},
        "verifier": {"path": contract.OFFICIAL_VERIFIER_PATH.as_posix(), "sha256": contract.OFFICIAL_VERIFIER_SHA256},
        "test": {"path": contract.OFFICIAL_TEST_PATH.as_posix(), "sha256": contract.OFFICIAL_TEST_SHA256},
    }
    if any(impl.get(key) != expected for key, expected in expected_implementation.items()):
        raise ValueError("official implementation identity changed")
    for relative, expected in (
        (contract.OFFICIAL_EXPORTER_PATH, contract.OFFICIAL_EXPORTER_SHA256),
        (contract.OFFICIAL_VERIFIER_PATH, contract.OFFICIAL_VERIFIER_SHA256),
        (contract.OFFICIAL_TEST_PATH, contract.OFFICIAL_TEST_SHA256),
    ):
        if _sha(_safe_file(root, relative).read_bytes()) != expected:
            raise ValueError(f"official boot-interwork file changed: {relative}")
    root_record = payload.get("root", {})
    if root_record.get("file_offset") != contract.OFFICIAL_ROOT_OFFSET or root_record.get("traversal_status") != "closed" or root_record.get("frontier_count") != 0 or root_record.get("reachable_instruction_count") != contract.OFFICIAL_ARM_INSTRUCTION_COUNT or root_record.get("reachable_instruction_bytes") != contract.OFFICIAL_ARM_INSTRUCTION_BYTES:
        raise ValueError("official ARM callee closure changed")
    return {"artifact_dir": contract.OFFICIAL_ARTIFACT_DIR.as_posix(), "manifest_path": contract.OFFICIAL_MANIFEST_PATH.as_posix(), "manifest_sha256": contract.OFFICIAL_MANIFEST_SHA256, "payload_path": contract.OFFICIAL_PAYLOAD_PATH.as_posix(), "payload_sha256": contract.OFFICIAL_PAYLOAD_SHA256, "verifier_path": contract.OFFICIAL_VERIFIER_PATH.as_posix(), "verifier_sha256": contract.OFFICIAL_VERIFIER_SHA256, "exporter_path": contract.OFFICIAL_EXPORTER_PATH.as_posix(), "exporter_sha256": contract.OFFICIAL_EXPORTER_SHA256, "test_path": contract.OFFICIAL_TEST_PATH.as_posix(), "test_sha256": contract.OFFICIAL_TEST_SHA256, "bound_root": {"file_offset": contract.OFFICIAL_ROOT_OFFSET, "gba_address": _gba(contract.OFFICIAL_ROOT_OFFSET), "entry_sha256": contract.OFFICIAL_ROOT_ENTRY_SHA256, "instruction_count": contract.OFFICIAL_ARM_INSTRUCTION_COUNT, "instruction_bytes": contract.OFFICIAL_ARM_INSTRUCTION_BYTES, "frontier_count": 0, "return_offsets": list(contract.OFFICIAL_ARM_RETURN_OFFSETS)}}


def _implementation(root: Path) -> dict[str, Any]:
    paths = {key: path.as_posix() for key, path in contract.IMPLEMENTATION_PATHS.items()}
    hashes = {key: _sha(_safe_file(root, path).read_bytes()) for key, path in contract.IMPLEMENTATION_PATHS.items()}
    return {"binding": "contract-exporter-verifier-tests-hash-bound", "paths": paths, "sha256": hashes}


def _producer(rom: bytes) -> dict[str, Any]:
    matches: list[int] = []
    for offset in range(0, len(rom) - 3, 2):
        first = _u16(rom, offset)
        second = _u16(rom, offset + 2)
        if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
            target = offset + 4 + _sign_extend(((first & 0x07FF) << 12) | ((second & 0x07FF) << 1), 23)
            if target == contract.BL_PRODUCER_TARGET:
                matches.append(offset)
    if matches != [contract.BL_PRODUCER_OFFSET]:
        raise ValueError("unique direct BL producer denominator changed")
    raw = _bounded(rom, contract.BL_PRODUCER_OFFSET, contract.BL_PRODUCER_END)
    if raw.hex() != contract.BL_PRODUCER_RAW_HEX or _sha(raw) != contract.BL_PRODUCER_SHA256:
        raise ValueError("direct BL producer bytes changed")
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
    return {"unique_direct_bl_offsets": matches, "direct_bl": {"mode": "thumb", "file_offset": contract.BL_PRODUCER_OFFSET, "gba_address": _gba(contract.BL_PRODUCER_OFFSET), "range": [contract.BL_PRODUCER_OFFSET, contract.BL_PRODUCER_END], "raw_hex": raw.hex(), "sha256": contract.BL_PRODUCER_SHA256, "target_offset": contract.BL_PRODUCER_TARGET, "target_gba_address": _gba(contract.BL_PRODUCER_TARGET), "flow_kind": "call"}, "continuation_root": contract.CONTINUATION_ROOT, "continuation_root_gba_address": _gba(contract.CONTINUATION_ROOT), "continuation_mode": "thumb", "callee_arm_root": contract.OFFICIAL_ROOT_OFFSET}


def _check_payload(root: Path, payload: dict[str, Any], rom: bytes) -> dict[str, Any]:
    decoder = _decoder_identity(root)
    baseline, owner = _read_coverage(root)
    official = _official_reference(root)
    producer = _producer(rom)
    thumb_nodes, thumb_blocks, thumb_edges, outbound, thumb_literals = _thumb_rebuild(rom)
    arm_nodes, arm_blocks, arm_edges, arm_literals = _arm_rebuild(rom)
    arm_returns = [node["file_offset"] for node in arm_nodes if node["flow_kind"] == "return"]
    code_ranges = [[contract.CONTINUATION_CODE_RANGE[0], contract.CONTINUATION_CODE_RANGE[1]]]
    literal_ranges = [list(item) for item in contract.CONTINUATION_LITERAL_RANGES]
    union_ranges = [list(contract.CONTINUATION_RANGE)]
    packed = b"".join(_bounded(rom, start, end) for start, end in union_ranges)
    claims = [{"id": "continuation-code-06108a-0610d4", "range": list(contract.CONTINUATION_CODE_RANGE), "size": contract.CONTINUATION_CODE_BYTES, "semantic_class": "armv4t_boot_interwork_continuation_code", "sha256": contract.CONTINUATION_CODE_SHA256, "baseline_unknown_only": True}]
    claims.extend({"id": f"continuation-literal-{index:02d}-{start:06x}", "range": [start, end], "size": end - start, "semantic_class": "thumb_pc_relative_literal_word", "sha256": _sha(_bounded(rom, start, end)), "baseline_unknown_only": True} for index, (start, end) in enumerate(contract.CONTINUATION_LITERAL_RANGES, 1))
    expected_promotion = {"promotion_batch": contract.SCHEMA, "primary_class": "armv4t_boot_interwork_continuation", "claim_kind": "boot_interwork_continuation_current_unknown_bytes", "target_range": list(contract.CONTINUATION_RANGE), "code_ranges": code_ranges, "literal_ranges": literal_ranges, "union_ranges": union_ranges, "code_bytes": contract.CONTINUATION_CODE_BYTES, "literal_bytes": contract.CONTINUATION_LITERAL_BYTES, "promotion_bytes": contract.CONTINUATION_PROMOTION_BYTES, "code_sha256": contract.CONTINUATION_CODE_SHA256, "literal_packed_sha256": contract.CONTINUATION_LITERAL_PACKED_SHA256, "union_range_sha256": contract.CONTINUATION_UNION_RANGE_SHA256, "union_packed_sha256": contract.CONTINUATION_UNION_PACKED_SHA256, "baseline_unknown_only": True, "claims": claims}
    expected_coverage_denominator = {"schema": contract.COVERAGE_SCHEMA, "artifact": contract.PRECOVERAGE_DIR.as_posix(), "manifest_sha256": contract.PRECOVERAGE_MANIFEST_SHA256, "archive_sha256": contract.PRECOVERAGE_ARCHIVE_SHA256, "archive_size": contract.PRECOVERAGE_ARCHIVE_SIZE, "raw_sha256": contract.PRECOVERAGE_RAW_SHA256, "raw_size": contract.PRECOVERAGE_RAW_SIZE, "classified_bytes": contract.COVERAGE_CLASSIFIED_BYTES, "unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES, "claim_count": contract.COVERAGE_CLAIM_COUNT, "segment_count": contract.COVERAGE_SEGMENT_COUNT}
    expected_thumb = {"root": {"mode": "thumb", "file_offset": contract.CONTINUATION_ROOT, "gba_address": _gba(contract.CONTINUATION_ROOT), "entry_size": 4, "entry_sha256": _sha(_bounded(rom, contract.CONTINUATION_ROOT, contract.CONTINUATION_ROOT + 4)), "source_bl_offset": contract.BL_PRODUCER_OFFSET, "static_call_continuation": True}, "instructions": thumb_nodes, "blocks": thumb_blocks, "edges": thumb_edges, "outbound_edges": outbound, "frontier_count": 0, "frontiers": [], "literal_bindings": thumb_literals, "denominators": {"instruction_vector_sha256": _vsha(thumb_nodes), "block_vector_sha256": _vsha(thumb_blocks), "edge_vector_sha256": _vsha(thumb_edges), "literal_binding_vector_sha256": _vsha(thumb_literals)}}
    expected_callee = {"root": {"mode": "arm", "file_offset": contract.OFFICIAL_ROOT_OFFSET, "gba_address": _gba(contract.OFFICIAL_ROOT_OFFSET), "entry_size": 4, "entry_sha256": contract.OFFICIAL_ROOT_ENTRY_SHA256}, "traversal_status": "closed", "instruction_count": len(arm_nodes), "instruction_bytes": sum(node["size"] for node in arm_nodes), "block_count": len(arm_blocks), "edge_count": len(arm_edges), "frontier_count": 0, "return_offsets": arm_returns, "all_terminal_paths_end_in_bx_lr": True, "instructions": arm_nodes, "blocks": arm_blocks, "edges": arm_edges, "literal_bindings": arm_literals, "denominators": {"instruction_vector_sha256": _vsha(arm_nodes), "block_vector_sha256": _vsha(arm_blocks), "edge_vector_sha256": _vsha(arm_edges), "literal_binding_vector_sha256": _vsha(arm_literals)}}
    checks = (
        (payload.get("schema"), contract.SCHEMA, "schema"),
        (payload.get("rom"), {"path": contract.ROM_PATH.as_posix(), "size": contract.ROM_SIZE, "sha256": contract.ROM_SHA256}, "ROM identity"),
        (payload.get("decoder"), decoder, "decoder identity"),
        (payload.get("coverage_baseline"), baseline, "coverage baseline"),
        (payload.get("coverage_denominator"), expected_coverage_denominator, "coverage denominator"),
        (payload.get("current_unknown_owner"), owner, "current unknown owner"),
        (payload.get("official_boot_interwork_artifact"), official, "official artifact identity"),
        (payload.get("producer"), producer, "direct BL producer"),
        (payload.get("thumb_continuation"), expected_thumb, "Thumb continuation"),
        (payload.get("callee_arm_closure"), expected_callee, "ARM callee closure"),
        (payload.get("promotion"), expected_promotion, "promotion"),
        (payload.get("coverage_projection"), {"baseline_unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES, "promoted_bytes": contract.CONTINUATION_PROMOTION_BYTES, "remaining_unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES - contract.CONTINUATION_PROMOTION_BYTES, "coverage_file_written": False}, "coverage projection"),
        (payload.get("summary"), {"continuation_instruction_count": len(thumb_nodes), "continuation_code_bytes": contract.CONTINUATION_CODE_BYTES, "continuation_block_count": len(thumb_blocks), "continuation_frontier_count": 0, "literal_binding_count": len(thumb_literals), "literal_bytes": contract.CONTINUATION_LITERAL_BYTES, "outbound_edge_count": len(outbound), "promotion_bytes": contract.CONTINUATION_PROMOTION_BYTES, "callee_arm_instruction_count": len(arm_nodes), "callee_arm_instruction_bytes": sum(node["size"] for node in arm_nodes), "callee_arm_block_count": len(arm_blocks), "callee_arm_edge_count": len(arm_edges), "callee_arm_frontier_count": 0, "callee_arm_return_count": len(arm_returns), "coverage_baseline_unknown_bytes": contract.COVERAGE_UNKNOWN_BYTES}, "summary"),
        (payload.get("scope"), dict(contract.SCOPE), "scope"),
        (payload.get("limitations"), list(contract.LIMITATIONS), "limitations"),
        (payload.get("implementation"), _implementation(root), "implementation identities"),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ValueError(f"{label} changed")
    if _sha(_bounded(rom, *contract.CONTINUATION_CODE_RANGE)) != contract.CONTINUATION_CODE_SHA256 or _sha(b"".join(_bounded(rom, start, end) for start, end in contract.CONTINUATION_LITERAL_RANGES)) != contract.CONTINUATION_LITERAL_PACKED_SHA256 or _sha(packed) != contract.CONTINUATION_UNION_PACKED_SHA256 or _vsha(union_ranges) != contract.CONTINUATION_UNION_RANGE_SHA256:
        raise ValueError("continuation range or packed hash changed")
    return {"verified": True, "schema": contract.VERIFY_SCHEMA, "promotion_bytes": contract.CONTINUATION_PROMOTION_BYTES, "literal_binding_count": len(thumb_literals), "callee_frontier_count": 0, "callee_return_offsets": arm_returns, "errors": []}


def verify_payload(root: Path, payload: dict[str, Any], rom_override: bytes | None = None) -> dict[str, Any]:
    try:
        root = Path(root).resolve(strict=True)
        rom = _read_rom(root) if rom_override is None else rom_override
        if len(rom) != contract.ROM_SIZE or _sha(rom) != contract.ROM_SHA256:
            raise ValueError("base ROM identity changed")
        return _check_payload(root, payload, rom)
    except Exception as error:
        return {"verified": False, "schema": contract.VERIFY_SCHEMA, "promotion_bytes": None, "literal_binding_count": None, "callee_frontier_count": None, "callee_return_offsets": [], "errors": [str(error)]}


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    try:
        root = Path(root).resolve(strict=True)
        artifact_dir = Path(artifact_dir)
        if not artifact_dir.is_absolute():
            artifact_dir = root / artifact_dir
        artifact_dir = artifact_dir.resolve(strict=True)
        if artifact_dir.is_symlink() or not artifact_dir.is_dir():
            raise ValueError("candidate artifact directory is invalid")
        files = {path.name for path in artifact_dir.iterdir() if path.is_file()}
        if files != {contract.MANIFEST_NAME, contract.PAYLOAD_NAME}:
            raise ValueError("candidate artifact file set changed")
        payload_raw = (artifact_dir / contract.PAYLOAD_NAME).read_bytes()
        manifest_raw = (artifact_dir / contract.MANIFEST_NAME).read_bytes()
        manifest = json.loads(manifest_raw)
        payload = json.loads(payload_raw.decode("utf-8"))
        if _canonical(payload) != payload_raw or _canonical(manifest) != manifest_raw:
            raise ValueError("candidate artifact JSON is not canonical")
        record = manifest.get("files", {}).get(contract.PAYLOAD_NAME)
        if manifest.get("artifact_schema") != contract.SCHEMA or manifest.get("schema") != f"{contract.SCHEMA}-artifact-manifest-v1" or manifest.get("artifact_status") not in {"candidate", "accepted"} or record != {"size": len(payload_raw), "sha256": _sha(payload_raw)}:
            raise ValueError("candidate manifest binding changed")
        report = _check_payload(root, payload, _read_rom(root))
        if manifest.get("rom") != payload.get("rom") or manifest.get("decoder") != payload.get("decoder") or manifest.get("coverage_baseline") != payload.get("coverage_baseline") or manifest.get("coverage_denominator") != payload.get("coverage_denominator") or manifest.get("current_unknown_owner") != payload.get("current_unknown_owner") or manifest.get("official_boot_interwork_artifact") != payload.get("official_boot_interwork_artifact") or manifest.get("promotion") != payload.get("promotion") or manifest.get("summary") != payload.get("summary") or manifest.get("scope") != payload.get("scope") or manifest.get("limitations") != payload.get("limitations") or manifest.get("implementation") != payload.get("implementation"):
            raise ValueError("candidate manifest and payload diverge")
        producer = manifest.get("producer", {}).get("command")
        verification = manifest.get("verification", {})
        verifier_command = verification.get("command")
        if not isinstance(producer, list) or producer[:-1] != ["python3", "-I", "-S", "tools/export_rom_boot_interwork_continuation.py", "--root", ".", "--output"]:
            raise ValueError("candidate producer receipt changed")
        receipt = producer[-1]
        allowed_receipt = receipt == contract.OFFICIAL_OUTPUT.as_posix() or receipt.startswith(contract.EXPERIMENT_ROOT.as_posix() + "/")
        expected_verifier = ["python3", "-I", "-S", "tools/verify_rom_boot_interwork_continuation.py", "--root", ".", "--artifact", receipt]
        if not allowed_receipt or verifier_command != expected_verifier or verification.get("schema") != contract.VERIFY_SCHEMA or verification.get("verifier_path") != contract.IMPLEMENTATION_PATHS["verifier"].as_posix():
            raise ValueError("candidate verifier receipt changed")
        if manifest.get("artifact_status") == "candidate":
            if "exit_code" in verification or "report" in verification:
                raise ValueError("candidate verification receipt changed")
        else:
            embedded = verification.get("report", {})
            if verification.get("exit_code") != 0 or embedded.get("verified") is not True or embedded.get("promotion_bytes") != contract.CONTINUATION_PROMOTION_BYTES:
                raise ValueError("accepted verification receipt changed")
        return report
    except Exception as error:
        return {"verified": False, "schema": contract.VERIFY_SCHEMA, "promotion_bytes": None, "literal_binding_count": None, "callee_frontier_count": None, "callee_return_offsets": [], "errors": [str(error)]}


def verify_root(root: Path, artifact_dir: Path) -> dict[str, Any]:
    return verify_artifact(root, artifact_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
