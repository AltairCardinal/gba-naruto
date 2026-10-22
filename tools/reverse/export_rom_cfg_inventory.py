#!/usr/bin/env python3
"""Export a bounded ARMv4T CFG inventory from the fixed proven root set."""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import heapq
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
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
from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory


SCHEMA = "rom-cfg-inventory-v2"
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
        raise ValueError(f"CFG inventory input escapes repository: {relative}") from error
    if resolved != candidate.absolute() or not resolved.is_file():
        raise ValueError(f"CFG inventory input is missing or uses a symlink: {relative}")
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


def _valid_armv4t_encoding(mode: str, raw: bytes, instruction: Any) -> bool:
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


def _successor(kind: str, mode: str, file_offset: int) -> dict[str, Any]:
    return {"kind": kind, "mode": mode, "file_offset": file_offset}


def _target_successor(
    rom_size: int, mode: str, target_address: int, kind: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    target = target_address - ROM_BASE
    alignment = 4 if mode == "arm" else 2
    if target < 0 or target >= rom_size:
        return None, {
            "reason": "direct_target_outside_rom",
            "target": {"mode": mode, "file_offset": target},
        }
    if target % alignment:
        return None, {
            "reason": "misaligned_direct_target",
            "target": {"mode": mode, "file_offset": target},
        }
    return _successor(kind, mode, target), None


def _fallthrough(
    rom_size: int, mode: str, end: int
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if end >= rom_size:
        return None, {
            "reason": "fallthrough_outside_rom",
            "target": {"mode": mode, "file_offset": end},
        }
    return _successor("fallthrough", mode, end), None


def _decode_one(rom: bytes, file_offset: int, mode: str) -> dict[str, Any]:
    alignment = 4 if mode == "arm" else 2
    base = {
        "accepted": False,
        "mode": mode,
        "file_offset": file_offset,
    }
    if file_offset < 0 or file_offset >= len(rom) or file_offset % alignment:
        return {**base, "frontier_reason": "misaligned_or_outside_entry"}
    window = rom[file_offset : file_offset + 4]
    instructions = tuple(
        _engine(mode).disasm(window, ROM_BASE + file_offset, count=1)
    )
    if len(instructions) != 1:
        return {**base, "frontier_reason": "decode_failure"}
    instruction = instructions[0]
    if instruction.address != ROM_BASE + file_offset:
        return {**base, "frontier_reason": "decode_failure"}
    raw = rom[file_offset : file_offset + instruction.size]
    if len(raw) != instruction.size:
        return {**base, "frontier_reason": "decode_failure"}
    if not _valid_armv4t_encoding(mode, raw, instruction):
        return {**base, "frontier_reason": "unsupported_armv4t_instruction"}

    conditional = _is_conditional(instruction)
    end = file_offset + instruction.size
    successors: list[dict[str, Any]] = []
    frontiers: list[dict[str, Any]] = []

    if instruction.id in (arm_const.ARM_INS_B, arm_const.ARM_INS_BL):
        operands = instruction.operands
        if (
            len(operands) != 1
            or operands[0].type != arm_const.ARM_OP_IMM
        ):
            flow_kind = "indirect_branch"
            frontiers.append({"reason": "invalid_direct_branch_operand"})
        else:
            edge_kind = (
                "call_target"
                if instruction.id == arm_const.ARM_INS_BL
                else "branch_target"
            )
            target, frontier = _target_successor(
                len(rom), mode, operands[0].imm, edge_kind
            )
            if target is not None:
                successors.append(target)
            if frontier is not None:
                frontiers.append(frontier)
            if instruction.id == arm_const.ARM_INS_BL:
                flow_kind = "call"
                fallthrough, frontier = _fallthrough(len(rom), mode, end)
                if fallthrough is not None:
                    successors.append(fallthrough)
                if frontier is not None:
                    frontiers.append(frontier)
            elif conditional:
                flow_kind = "conditional_branch"
                fallthrough, frontier = _fallthrough(len(rom), mode, end)
                if fallthrough is not None:
                    successors.append(fallthrough)
                if frontier is not None:
                    frontiers.append(frontier)
            else:
                flow_kind = "unconditional_branch"
    elif instruction.id == arm_const.ARM_INS_SVC:
        flow_kind = "supervisor_call"
        immediate_mask = 0x00FFFFFF if mode == "arm" else 0xFF
        frontiers.append(
            {
                "reason": "bios_swi_external",
                "swi_immediate": int.from_bytes(raw, "little") & immediate_mask,
                "target": {
                    "address_space": "bios",
                    "gba_address": "0x00000008",
                },
            }
        )
        fallthrough, frontier = _fallthrough(len(rom), mode, end)
        if fallthrough is not None:
            successors.append(fallthrough)
        if frontier is not None:
            frontiers.append(frontier)
    elif instruction.id == arm_const.ARM_INS_BX or _writes_pc(instruction):
        returning = _is_return(instruction)
        flow_kind = "return" if returning else "indirect_branch"
        if not returning:
            frontiers.append({"reason": "indirect_pc_target"})
        if conditional:
            flow_kind = f"conditional_{flow_kind}"
            fallthrough, frontier = _fallthrough(len(rom), mode, end)
            if fallthrough is not None:
                successors.append(fallthrough)
            if frontier is not None:
                frontiers.append(frontier)
    else:
        flow_kind = "linear"
        fallthrough, frontier = _fallthrough(len(rom), mode, end)
        if fallthrough is not None:
            successors.append(fallthrough)
        if frontier is not None:
            frontiers.append(frontier)

    successors.sort(
        key=lambda edge: (
            _EDGE_ORDER[edge["kind"]],
            _MODE_ORDER[edge["mode"]],
            edge["file_offset"],
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


def _key(mode: str, offset: int) -> tuple[int, int, str]:
    return offset, _MODE_ORDER[mode], mode


def _traverse(
    rom: bytes, seeds: list[dict[str, Any]]
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
]:
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for seed in seeds:
        item = (seed["mode"], seed["file_offset"])
        if item not in scheduled:
            heapq.heappush(pending, _key(*item))
            scheduled.add(item)
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    incoming: dict[
        tuple[str, int], list[tuple[tuple[str, int], str]]
    ] = defaultdict(list)
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if len(nodes) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("CFG instruction budget exhausted")
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    return nodes, rejected, incoming


def _assert_nonoverlapping_nodes(
    nodes: dict[tuple[str, int], dict[str, Any]]
) -> None:
    for mode in _MODE_ORDER:
        previous_end = -1
        for (node_mode, start), node in sorted(
            nodes.items(), key=lambda item: _key(item[0][0], item[0][1])
        ):
            if node_mode != mode:
                continue
            if start < previous_end:
                raise ValueError(
                    f"overlapping {mode} instruction decodes at 0x{start:06X}"
                )
            previous_end = start + node["size"]


def _build_blocks(
    rom: bytes,
    nodes: dict[tuple[str, int], dict[str, Any]],
    root_keys: set[tuple[str, int]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], str]]:
    resolved_successors = {
        item: [
            (edge["mode"], edge["file_offset"])
            for edge in node["successors"]
            if (edge["mode"], edge["file_offset"]) in nodes
        ]
        for item, node in nodes.items()
    }
    predecessors: dict[tuple[str, int], list[tuple[str, int]]] = defaultdict(list)
    for source, targets in resolved_successors.items():
        for target in targets:
            predecessors[target].append(source)

    starts = {item for item in root_keys if item in nodes}
    for item in nodes:
        incoming = predecessors[item]
        if len(incoming) != 1:
            starts.add(item)
            continue
        predecessor = incoming[0]
        predecessor_node = nodes[predecessor]
        if (
            len(resolved_successors[predecessor]) != 1
            or predecessor[0] != item[0]
            or predecessor[1] + predecessor_node["size"] != item[1]
            or predecessor_node["flow_kind"] != "linear"
        ):
            starts.add(item)

    pending = [_key(mode, offset) for mode, offset in starts]
    heapq.heapify(pending)
    assigned: dict[tuple[str, int], str] = {}
    raw_blocks: list[tuple[list[tuple[str, int]], dict[str, Any]]] = []
    while len(assigned) < len(nodes):
        if not pending:
            remaining = min(
                (item for item in nodes if item not in assigned),
                key=lambda item: _key(*item),
            )
            heapq.heappush(pending, _key(*remaining))
        offset, _, mode = heapq.heappop(pending)
        start = (mode, offset)
        if start in assigned:
            continue
        block_id = f"block-{mode}-{offset:06x}"
        members: list[tuple[str, int]] = []
        current = start
        while True:
            if current in assigned:
                break
            members.append(current)
            assigned[current] = block_id
            node = nodes[current]
            targets = resolved_successors[current]
            if (
                len(members) >= MAX_BLOCK_INSTRUCTION_COUNT
                and len(targets) == 1
                and node["flow_kind"] == "linear"
            ):
                next_item = targets[0]
                starts.add(next_item)
                heapq.heappush(pending, _key(*next_item))
                break
            if (
                len(targets) != 1
                or node["flow_kind"] != "linear"
                or targets[0] in starts
                or targets[0] in assigned
                or targets[0][0] != current[0]
                or targets[0][1] != current[1] + node["size"]
            ):
                break
            current = targets[0]
        last = members[-1]
        last_node = nodes[last]
        start_offset = members[0][1]
        end_offset = last[1] + last_node["size"]
        raw_blocks.append(
            (
                members,
                {
                    "id": block_id,
                    "mode": mode,
                    "range": [start_offset, end_offset],
                    "instruction_count": len(members),
                    "bytes_sha256": _sha(rom[start_offset:end_offset]),
                    "terminator": {
                        "file_offset": last[1],
                        "size": last_node["size"],
                        "mnemonic": last_node["mnemonic"],
                        "op_str": last_node["op_str"],
                        "flow_kind": last_node["flow_kind"],
                        "conditional": last_node["conditional"],
                    },
                    "successors": [],
                },
            )
        )

    blocks = []
    for members, block in raw_blocks:
        last = members[-1]
        successors = []
        for edge in nodes[last]["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in nodes:
                successors.append(
                    {
                        **edge,
                        "block_id": assigned[target],
                    }
                )
        block["successors"] = successors
        blocks.append(block)
    blocks.sort(key=lambda block: _key(block["mode"], block["range"][0]))
    return blocks, assigned


def _frontier_records(
    nodes: dict[tuple[str, int], dict[str, Any]],
    rejected: dict[tuple[str, int], dict[str, Any]],
    incoming: dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
    roots: list[dict[str, Any]],
    node_to_block: dict[tuple[str, int], str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item, node in nodes.items():
        for frontier in node["frontiers"]:
            records.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": node_to_block[item],
                        "instruction_offset": item[1],
                    },
                    **frontier,
                }
            )
    root_ids_by_key: dict[tuple[str, int], list[str]] = defaultdict(list)
    for root in roots:
        root_ids_by_key[(root["mode"], root["file_offset"])].append(root["root_id"])
    for target, rejected_record in rejected.items():
        target_record = {"mode": target[0], "file_offset": target[1]}
        for source, edge_kind in incoming.get(target, []):
            records.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": node_to_block[source],
                        "instruction_offset": source[1],
                        "edge_kind": edge_kind,
                    },
                    "reason": rejected_record["frontier_reason"],
                    "target": target_record,
                }
            )
        for root_id in root_ids_by_key.get(target, []):
            records.append(
                {
                    "source": {"kind": "root", "root_id": root_id},
                    "reason": rejected_record["frontier_reason"],
                    "target": target_record,
                }
            )
    records.sort(
        key=lambda record: json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    return [{"id": f"frontier-{index:06d}", **record} for index, record in enumerate(records)]


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


def _root_results(
    seeds: list[dict[str, Any]],
    nodes: dict[tuple[str, int], dict[str, Any]],
    frontiers: list[dict[str, Any]],
    node_to_block: dict[tuple[str, int], str],
) -> list[dict[str, Any]]:
    frontier_sources: dict[tuple[str, int], set[str]] = defaultdict(set)
    root_frontiers: dict[str, set[str]] = defaultdict(set)
    for frontier in frontiers:
        source = frontier["source"]
        if source["kind"] == "root":
            root_frontiers[source["root_id"]].add(frontier["id"])
        else:
            frontier_sources[
                (source["block_id"], source["instruction_offset"])
            ].add(frontier["id"])

    results = []
    for index, seed in enumerate(seeds):
        root_id = f"root-{seed['mode']}-{seed['file_offset']:06x}"
        start = (seed["mode"], seed["file_offset"])
        reachable: set[tuple[str, int]] = set()
        queue = deque([start] if start in nodes else [])
        reached_frontiers = set(root_frontiers[root_id])
        while queue:
            item = queue.popleft()
            if item in reachable:
                continue
            reachable.add(item)
            node = nodes[item]
            block_id = node_to_block[item]
            reached_frontiers.update(frontier_sources[(block_id, item[1])])
            for edge in node["successors"]:
                target = (edge["mode"], edge["file_offset"])
                if target in nodes and target not in reachable:
                    queue.append(target)
        reachable_bytes = sum(nodes[item]["size"] for item in reachable)
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
                "entry_block_id": node_to_block.get(start),
                "traversal_status": (
                    "closed" if not reached_frontiers else "frontier_open"
                ),
                "reachable_instruction_count": len(reachable),
                "reachable_instruction_bytes": reachable_bytes,
                "reachable_block_count": len(
                    {node_to_block[item] for item in reachable}
                ),
                "frontier_count": len(reached_frontiers),
            }
        )
    return results


def _decoder_identity(root: Path) -> dict[str, Any]:
    actual = {}
    for relative, expected in DECODER_FILES.items():
        path = _safe_file(root, relative)
        digest = _sha(path.read_bytes())
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


def _seed_payload(root: Path, rom: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = root / SEED_ARTIFACT
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
    report = verify_rom_cfg_seeds(root, artifact)
    if report != {
        "schema": "rom-cfg-seeds-verification-v1",
        "verified": True,
        "dispatch_source_count": 23,
        "raw_dispatch_slot_count": 829,
        "root_seed_count": 263,
        "arm_root_seed_count": 2,
        "thumb_root_seed_count": 261,
        "errors": [],
    }:
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
    seeds = payload.get("seeds")
    if not isinstance(seeds, list) or len(seeds) != 263:
        raise ValueError("CFG seed denominator changed")
    seen = set()
    for seed in seeds:
        if not isinstance(seed, dict):
            raise ValueError("CFG seed is not an object")
        mode = seed.get("mode")
        offset = seed.get("file_offset")
        entry_size = seed.get("entry_size")
        identity = (mode, offset)
        if (
            mode not in _MODE_ORDER
            or not isinstance(offset, int)
            or not isinstance(entry_size, int)
            or entry_size != 4
            or offset < 0
            or offset + entry_size > len(rom)
            or offset % (4 if mode == "arm" else 2)
            or seed.get("gba_address") != f"0x{ROM_BASE + offset:08X}"
            or seed.get("entry_sha256") != _sha(rom[offset : offset + entry_size])
            or not isinstance(seed.get("sources"), list)
            or not seed["sources"]
            or identity in seen
        ):
            raise ValueError("CFG seed identity or provenance changed")
        seen.add(identity)
    return payload, manifest


def build_cfg_inventory_payload(
    root: Path, rom: bytes | None = None
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != 6_291_456 or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    seed_payload, seed_manifest = _seed_payload(root, rom)
    decoder = _decoder_identity(root)
    seeds = seed_payload["seeds"]
    nodes, rejected, incoming = _traverse(rom, seeds)
    _assert_nonoverlapping_nodes(nodes)
    seed_root_keys = {(seed["mode"], seed["file_offset"]) for seed in seeds}
    blocks, node_to_block = _build_blocks(rom, nodes, seed_root_keys)
    root_shells = [
        {
            "root_id": f"root-{seed['mode']}-{seed['file_offset']:06x}",
            "mode": seed["mode"],
            "file_offset": seed["file_offset"],
        }
        for seed in seeds
    ]
    frontiers = _frontier_records(
        nodes, rejected, incoming, root_shells, node_to_block
    )
    roots = _root_results(seeds, nodes, frontiers, node_to_block)

    mode_bytes = {
        mode: sum(node["size"] for (node_mode, _), node in nodes.items() if node_mode == mode)
        for mode in _MODE_ORDER
    }
    union_bytes = _union_bytes(
        [(offset, offset + node["size"]) for (_, offset), node in nodes.items()]
    )
    frontier_reasons: dict[str, int] = {}
    for frontier in frontiers:
        reason = frontier["reason"]
        frontier_reasons[reason] = frontier_reasons.get(reason, 0) + 1
    summary = {
        "root_count": len(roots),
        "arm_root_count": sum(root["mode"] == "arm" for root in roots),
        "thumb_root_count": sum(root["mode"] == "thumb" for root in roots),
        "closed_root_count": sum(root["traversal_status"] == "closed" for root in roots),
        "frontier_open_root_count": sum(
            root["traversal_status"] == "frontier_open" for root in roots
        ),
        "decoded_instruction_count": len(nodes),
        "arm_instruction_count": sum(mode == "arm" for mode, _ in nodes),
        "thumb_instruction_count": sum(mode == "thumb" for mode, _ in nodes),
        "decoded_basic_block_count": len(blocks),
        "arm_instruction_bytes": mode_bytes["arm"],
        "thumb_instruction_bytes": mode_bytes["thumb"],
        "reachable_instruction_bytes": union_bytes,
        "cross_mode_overlap_bytes": mode_bytes["arm"] + mode_bytes["thumb"] - union_bytes,
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(sorted(frontier_reasons.items())),
        "budget_exhausted": False,
    }
    seed_file_record = seed_manifest["files"][SEED_PAYLOAD_NAME]
    seed_artifact = {
        "path": SEED_ARTIFACT.as_posix(),
        "manifest_sha256": SEED_MANIFEST_SHA256,
        "payload_file": SEED_PAYLOAD_NAME,
        "payload_size": seed_file_record["size"],
        "payload_sha256": seed_file_record["sha256"],
        "seed_denominator_sha256": SEED_DENOMINATOR_SHA256,
        "dispatch_slot_denominator_sha256": DISPATCH_SLOT_DENOMINATOR_SHA256,
        "summary": EXPECTED_SEED_SUMMARY,
        "scope": EXPECTED_SEED_SCOPE,
        "excluded_seed_classes": EXPECTED_EXCLUDED_SEED_CLASSES,
        "verifier_path": SEED_VERIFIER.as_posix(),
        "verifier_sha256": SEED_VERIFIER_SHA256,
    }
    limits = {
        "max_instruction_count": MAX_INSTRUCTION_COUNT,
        "max_basic_block_instruction_count": MAX_BLOCK_INSTRUCTION_COUNT,
        "decode_window_bytes": 4,
    }
    graph_denominator_sha256 = _canonical_sha(
        {"roots": roots, "blocks": blocks, "frontiers": frontiers}
    )
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "seed_artifact": seed_artifact,
        "decoder": decoder,
        "limits": limits,
        "summary": summary,
        "graph_denominator_sha256": graph_denominator_sha256,
        "roots": roots,
        "blocks": blocks,
        "frontiers": frontiers,
        "scope": SCOPE,
        "limitations": [
            "Only the fixed proven seed set is traversed; this is not a global function-entry or dispatch-source census.",
            "Indirect PC targets remain explicit frontiers and are not guessed.",
            "Capstone decoding is constrained by an explicit conservative ARMv4T instruction allowlist.",
            "Static CFG reachability does not prove natural gameplay or runtime reachability.",
        ],
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            _safe_file(root, "tools/export_rom_cfg_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            _safe_file(root, "tools/verify_rom_cfg_inventory.py").read_bytes()
        ),
        "test_sha256": _sha(
            _safe_file(root, "tests/test_export_rom_cfg_inventory.py").read_bytes()
        ),
    }


def _reject_symlink_components(path: Path) -> Path:
    requested = path.expanduser().absolute()
    cursor = Path(requested.anchor)
    for part in requested.parts[1:]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("CFG inventory output path uses a symlink")
        if not cursor.exists():
            break
    return requested


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("CFG inventory output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("CFG inventory output is not a directory")
    members = list(target.iterdir())
    if not members:
        return target
    if (
        {member.name for member in members} != {"manifest.json", PAYLOAD_NAME}
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError("existing directory is not a replaceable CFG inventory artifact")
    try:
        manifest = json.loads((target / "manifest.json").read_bytes())
        payload_path = target / PAYLOAD_NAME
        payload = json.loads(payload_path.read_bytes())
        record = manifest["files"][PAYLOAD_NAME]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(
            "existing directory is not a replaceable CFG inventory artifact"
        ) from error
    if (
        manifest.get("artifact_schema") != SCHEMA
        or manifest.get("rom", {}).get("sha256") != ROM_SHA256
        or manifest.get("seed_artifact", {}).get("manifest_sha256")
        != SEED_MANIFEST_SHA256
        or set(manifest.get("files", {})) != {PAYLOAD_NAME}
        or record.get("size") != payload_path.stat().st_size
        or record.get("sha256") != _sha(payload_path.read_bytes())
        or payload.get("schema") != SCHEMA
        or payload.get("rom", {}).get("sha256") != ROM_SHA256
    ):
        raise ValueError("existing directory is not a replaceable CFG inventory artifact")
    report = verify_rom_cfg_inventory(root, target)
    if report.get("verified") is not True:
        raise ValueError(
            "existing directory is not a replaceable CFG inventory artifact: "
            f"independent verification failed: {report.get('errors', [])}"
        )
    return target


def _replace_output_dir(output_dir: Path, temporary: Path) -> None:
    backup: Path | None = None
    try:
        if output_dir.exists():
            backup = output_dir.with_name(
                f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            )
            os.replace(output_dir, backup)
        os.replace(temporary, output_dir)
    except BaseException:
        if backup is not None and backup.exists() and not output_dir.exists():
            os.replace(backup, output_dir)
        raise
    else:
        if backup is not None:
            shutil.rmtree(backup)


def export_rom_cfg_inventory(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output_dir = _validate_output_dir(root, output_dir)
    payload = build_cfg_inventory_payload(root)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".rom-cfg-inventory-", dir=output_dir.parent)
    )
    try:
        payload_path = temporary / PAYLOAD_NAME
        payload_raw = _canonical_json(payload)
        payload_path.write_bytes(payload_raw)
        manifest = {
            "artifact_schema": SCHEMA,
            "rom": payload["rom"],
            "seed_artifact": payload["seed_artifact"],
            "decoder": payload["decoder"],
            "limits": payload["limits"],
            "summary": payload["summary"],
            "graph_denominator_sha256": payload["graph_denominator_sha256"],
            "files": {
                PAYLOAD_NAME: {
                    "size": len(payload_raw),
                    "sha256": _sha(payload_raw),
                }
            },
            "implementation": _implementation(root),
            "scope": SCOPE,
        }
        (temporary / "manifest.json").write_bytes(_canonical_json(manifest))
        _validate_output_dir(root, temporary)
        _replace_output_dir(output_dir, temporary)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/rom-cfg-inventory-v2"),
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = args.root / output_dir
    manifest = export_rom_cfg_inventory(args.root, output_dir)
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
