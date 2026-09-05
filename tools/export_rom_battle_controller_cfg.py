#!/usr/bin/env python3
"""Export the exhaustively dispatched, range-bounded battle-controller CFG."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
import shutil
from pathlib import Path
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.export_rom_cfg_inventory import (
    MAX_BLOCK_INSTRUCTION_COUNT,
    MAX_INSTRUCTION_COUNT,
    ROM_PATH,
    _assert_nonoverlapping_nodes,
    _build_blocks,
    _canonical_json,
    _canonical_sha,
    _decode_one,
    _frontier_records,
    _key,
    _reject_symlink_components,
    _replace_output_dir,
    _safe_file,
    _union_bytes,
)


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"

SCHEMA = "rom-battle-controller-cfg-v1"
PAYLOAD_NAME = "rom-battle-controller-cfg.json"
MANIFEST_NAME = "manifest.json"

CONTROLLER_RANGE = (0x732B4, 0x7509C)
CONTROLLER_SHA256 = (
    "c9bdc220590a851fa331960bcb32be90eb9ac7248a5cd3dabb9f8afa0b674bc1"
)
# Includes the default BL at 0x735C6.  The historical v1 inventory stopped just
# before this instruction and therefore could not prove the default denominator.
# The corrected range ends at 0x7509C, the entry of the next function after the
# controller's epilogue: it contains the complete 4-byte BL at 0x75080 but
# excludes the subsequent function.
DISPATCH_RANGE = (0x733A0, 0x735CA)
DISPATCH_SHA256 = "43fe396227bb6815aeedd5c48783effdb842194634360999d3e42f0ee316e2b1"
DEFAULT_TARGET = 0x7504E
DISPATCH_MAPPING_VECTOR_SHA256 = (
    "ce5e8ea24e274c4456482611609ee90144d31e064fccf0d85bf8f4643f44ac15"
)

# §9.1 #4 — frozen baseline JSON payload raw-byte identity table.
# Each entry is the SHA256 of the canonical raw bytes of one of the four
# frozen CFG baseline artifacts.  ``_baseline_occupied_bytes`` reads each
# payload's raw bytes and compares the SHA256 against this table before
# parsing JSON; any mismatch fails closed.  The verifier must expose the
# same four mappings independently (no re-export from the exporter).
FROZEN_BASELINE_PAYLOAD_SHA256: dict[str, str] = {
    "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json": (
        "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
    ),
    "artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json": (
        "596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d"
    ),
    "artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json": (
        "7fdee7d0d62d3a8c82bfe7b03804e9cb0e3d213ebdf63acce6b0533045aecf54"
    ),
    "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json": (
        "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"
    ),
}

# Eight direct-call Thumb BL producers inside the corrected controller range
# already classified by the proven-roots-v1/v2 audit batches; the new CFG must
# treat them as opaque to avoid re-claiming them as reachable code.
EXISTING_PRODUCER_RANGES: tuple[tuple[int, int], ...] = (
    (0x73688, 0x7368C),
    (0x73690, 0x73694),
    (0x7425A, 0x7425E),
    (0x7434E, 0x74352),
    (0x7443C, 0x74440),
    (0x74448, 0x7444C),
    (0x74918, 0x7491C),
    (0x74F2C, 0x74F30),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_sha(value: object) -> str:
    return _sha(_canonical_json(value))


def _u16(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError("dispatcher instruction escapes ROM")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _signed(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def _thumb_bl_target(offset: int, first: int, second: int) -> int:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError("dispatcher contains malformed Thumb BL")
    displacement = (_signed(first & 0x07FF, 11) << 12) + (
        (second & 0x07FF) << 1
    )
    return offset + 4 + displacement


def _dispatch_one(rom: bytes, state: int) -> dict[str, Any]:
    """Execute the fixed Thumb-1 dispatcher for one complete u16 input."""

    if state < 0 or state > 0xFFFF:
        raise ValueError("dispatcher input is not a u16")
    start, end = DISPATCH_RANGE
    controller_start, controller_end = CONTROLLER_RANGE
    registers: dict[int, int] = {6: state}
    compared: tuple[int, int] | None = None
    offset = start
    path: list[dict[str, Any]] = []

    for _ in range(256):
        if offset < start or offset >= end or offset % 2:
            raise ValueError("dispatcher entered an invalid instruction boundary")
        first = _u16(rom, offset)
        size = 2
        raw = rom[offset : offset + size]
        next_offset = offset + size
        operation: str

        if first & 0xF800 == 0x2000:  # MOVS Rd, #imm8
            operation = "movs_imm"
            registers[(first >> 8) & 7] = first & 0xFF
        elif first & 0xF800 == 0x0000:  # LSLS Rd, Rm, #imm5
            operation = "lsls_imm"
            immediate = (first >> 6) & 0x1F
            source = (first >> 3) & 7
            destination = first & 7
            if source not in registers:
                raise ValueError("dispatcher shift reads an unknown register")
            registers[destination] = (registers[source] << immediate) & 0xFFFFFFFF
        elif first & 0xFFC0 == 0x4280:  # CMP Rn, Rm
            operation = "cmp_reg"
            left = first & 7
            right = (first >> 3) & 7
            if left not in registers or right not in registers:
                raise ValueError("dispatcher comparison reads an unknown register")
            compared = (registers[left] & 0xFFFFFFFF, registers[right] & 0xFFFFFFFF)
        elif first & 0xF800 == 0x2800:  # CMP Rn, #imm8
            operation = "cmp_imm"
            register = (first >> 8) & 7
            if register not in registers:
                raise ValueError("dispatcher comparison reads an unknown register")
            compared = (registers[register] & 0xFFFFFFFF, first & 0xFF)
        elif first & 0xF800 in (0x3000, 0x3800):  # ADDS/SUBS Rd, #imm8
            subtract = first & 0xF800 == 0x3800
            operation = "subs_imm" if subtract else "adds_imm"
            register = (first >> 8) & 7
            if register not in registers:
                raise ValueError("dispatcher arithmetic reads an unknown register")
            delta = first & 0xFF
            registers[register] = (
                registers[register] - delta
                if subtract
                else registers[register] + delta
            ) & 0xFFFFFFFF
        elif first & 0xF800 == 0x4800:  # LDR Rt, [PC, #imm8*4]
            operation = "ldr_literal"
            register = (first >> 8) & 7
            literal = ((offset + 4) & ~3) + ((first & 0xFF) << 2)
            if literal < 0 or literal + 4 > len(rom):
                raise ValueError("dispatcher literal escapes ROM")
            registers[register] = int.from_bytes(
                rom[literal : literal + 4], "little"
            )
        elif first & 0xF000 == 0xD000:  # conditional branch
            condition = (first >> 8) & 0xF
            if compared is None:
                raise ValueError("dispatcher branch has no comparison flags")
            left, right = compared
            if condition == 0x1:  # BNE
                operation = "bne"
                take = left != right
            elif condition == 0xC:  # BGT, signed
                operation = "bgt"
                signed_left = left if left < 0x80000000 else left - 0x100000000
                signed_right = right if right < 0x80000000 else right - 0x100000000
                take = signed_left > signed_right
            else:
                raise ValueError("dispatcher uses an unsupported condition")
            if take:
                next_offset = offset + 4 + (_signed(first & 0xFF, 8) << 1)
        elif first & 0xF800 == 0xE000:  # unconditional B
            operation = "b"
            target = offset + 4 + (_signed(first & 0x07FF, 11) << 1)
            raw = rom[offset : offset + 2]
            path.append(
                {
                    "offset": offset,
                    "size": 2,
                    "raw_hex": raw.hex(),
                    "operation": operation,
                }
            )
            if start <= target < end:
                offset = target
                continue
            if target < controller_start or target >= controller_end or target % 2:
                raise ValueError("dispatcher branch target escapes the controller")
            result = {
                "target_offset": target,
                "transfer_offset": offset,
                "transfer_kind": "branch_target",
                "transfer_raw_hex": raw.hex(),
            }
            if target != DEFAULT_TARGET:
                result["decision_path_sha256"] = _canonical_sha(path)
            return result
        elif first & 0xF800 == 0xF000:  # Thumb-1 BL pair
            operation = "bl"
            second = _u16(rom, offset + 2)
            target = _thumb_bl_target(offset, first, second)
            size = 4
            raw = rom[offset : offset + size]
            path.append(
                {
                    "offset": offset,
                    "size": size,
                    "raw_hex": raw.hex(),
                    "operation": operation,
                }
            )
            if start <= target < end:
                offset = target
                continue
            if target < controller_start or target >= controller_end or target % 2:
                raise ValueError("dispatcher call target escapes the controller")
            result = {
                "target_offset": target,
                "transfer_offset": offset,
                "transfer_kind": "call_target",
                "transfer_raw_hex": raw.hex(),
            }
            if target != DEFAULT_TARGET:
                result["decision_path_sha256"] = _canonical_sha(path)
            return result
        else:
            raise ValueError(
                f"dispatcher uses unsupported Thumb encoding 0x{first:04X} "
                f"at 0x{offset:06X}"
            )

        path.append(
            {
                "offset": offset,
                "size": size,
                "raw_hex": raw.hex(),
                "operation": operation,
            }
        )
        offset = next_offset
    raise ValueError("dispatcher execution budget exhausted")


def _dispatch_denominator(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE:
        raise ValueError("base ROM size changed")
    dispatch_start, dispatch_end = DISPATCH_RANGE
    dispatch_sha = _sha(rom[dispatch_start:dispatch_end])
    if dispatch_sha != DISPATCH_SHA256:
        raise ValueError("battle-controller dispatcher changed")
    controller_start, controller_end = CONTROLLER_RANGE
    if _sha(rom[controller_start:controller_end]) != CONTROLLER_SHA256:
        raise ValueError("battle-controller body changed")
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")

    outcomes: dict[int, list[int]] = defaultdict(list)
    transfers: dict[int, dict[tuple[int, str, str], dict[str, Any]]] = defaultdict(dict)
    state_outcomes: dict[int, dict[str, Any]] = {}
    for state in range(0x10000):
        outcome = _dispatch_one(rom, state)
        target = outcome["target_offset"]
        outcomes[target].append(state)
        state_outcomes[state] = outcome
        transfer = {
            key: outcome[key]
            for key in (
                "target_offset",
                "transfer_offset",
                "transfer_kind",
                "transfer_raw_hex",
            )
        }
        transfer_key = (
            transfer["transfer_offset"],
            transfer["transfer_kind"],
            transfer["transfer_raw_hex"],
        )
        transfers[target][transfer_key] = transfer

    defaults = outcomes.pop(DEFAULT_TARGET, [])
    if len(defaults) + sum(len(values) for values in outcomes.values()) != 0x10000:
        raise ValueError("dispatcher input denominator is incomplete")
    mappings: list[dict[str, Any]] = []
    for target, states in sorted(outcomes.items()):
        if len(states) != 1:
            raise ValueError("non-default dispatcher target has an ambiguous input set")
        if len(transfers[target]) != 1:
            raise ValueError("non-default dispatcher target has ambiguous transfer sites")
        state = states[0]
        transfer = state_outcomes[state]
        entry = rom[target : target + 4]
        mappings.append(
            {
                "state": state,
                "state_hex": f"0x{state:04X}",
                "target_offset": target,
                "target_gba_address": f"0x{ROM_BASE + target:08X}",
                "entry_size": len(entry),
                "entry_sha256": _sha(entry),
                **transfer,
            }
        )
    mappings.sort(key=lambda item: item["state"])
    mapping_sha = _canonical_sha(mappings)
    if mapping_sha != DISPATCH_MAPPING_VECTOR_SHA256:
        raise ValueError("battle-controller dispatcher mapping denominator changed")
    return {
        "input_domain": [0, 0x10000],
        "input_denominator": 0x10000,
        "nondefault_state_count": len(mappings),
        "default_state_count": len(defaults),
        "default_target": DEFAULT_TARGET,
        "default_transfers": [
            transfers[DEFAULT_TARGET][key]
            for key in sorted(transfers[DEFAULT_TARGET])
        ],
        "dispatcher_range": list(DISPATCH_RANGE),
        "dispatcher_sha256": dispatch_sha,
        "mappings": mappings,
        "mapping_denominator_sha256": mapping_sha,
    }


def _dedup_roots(
    dispatcher: dict[str, Any],
) -> list[dict[str, Any]]:
    """Deduplicate dispatcher targets into one root per target.

    Each non-default state in the canonical dispatcher maps to a unique target;
    after dedup we have exactly one root per distinct target.  Source states are
    recorded as ``source_states`` so the verifier can prove the target→state
    partition is bijective.
    """

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for mapping in dispatcher["mappings"]:
        grouped[mapping["target_offset"]].append(mapping)
    roots: list[dict[str, Any]] = []
    for target in sorted(grouped):
        members = sorted(grouped[target], key=lambda item: item["state"])
        states = [item["state"] for item in members]
        if len(states) != len(members):
            raise ValueError("dedup root has duplicate state")
        entry = dispatcher["mappings"][0]
        sample = members[0]
        roots.append(
            {
                "target_offset": target,
                "gba_address": f"0x{ROM_BASE + target:08X}",
                "entry_sha256": sample["entry_sha256"],
                "entry_size": sample["entry_size"],
                "source_states": states,
                "dispatch_transfer": {
                    "transfer_offset": sample["transfer_offset"],
                    "transfer_kind": sample["transfer_kind"],
                    "transfer_raw_hex": sample["transfer_raw_hex"],
                },
            }
        )
    return roots


def _baseline_middle_error(offset: int, kind: str) -> ValueError:
    return ValueError(
        f"{kind} target 0x{offset:06X} lands inside a frozen baseline "
        "instruction middle byte; only legal baseline instruction entry "
        "points may be opaque stops"
    )


def _traverse_bounded(
    rom: bytes,
    roots: list[dict[str, Any]],
    baseline_entries: set[tuple[str, int]],
    baseline_occupied: set[int],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Bounded Thumb CFG traversal inside CONTROLLER_RANGE.

    Edges inside the range that hit a frozen baseline instruction **entry**
    (i.e. ``(mode, target_offset)`` is in ``baseline_entries``) are recorded as
    ``opaque_baseline_edge`` and not traversed.  Any other target whose bytes
    intersect ``baseline_occupied`` but is not a legal baseline instruction
    entry is a baseline-middle violation and must fail closed
    (§9.1 #4).  Direct or call targets outside the range are recorded as
    ``opaque_external_edge``.  Indirect PC and unsupported targets become
    regular frontiers.

    Roots whose target offset coincides with a frozen baseline **entry** are
    recorded as ``skipped_claimed_root`` and excluded from the worklist: those
    function entries are already classified by an earlier audit batch.  A root
    landing in the middle of a frozen baseline instruction must fail closed
    before any traversal begins.
    """

    controller_start, controller_end = CONTROLLER_RANGE
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    skipped: list[dict[str, Any]] = []
    for root in roots:
        item = ("thumb", root["target_offset"])
        if item[1] in baseline_occupied:
            if item not in baseline_entries:
                raise _baseline_middle_error(item[1], "dedup root")
            skipped.append(
                {
                    "source": {"file_offset": item[1], "mode": item[0]},
                    "edge_kind": "root_entry",
                    "target_mode": item[0],
                    "target_file_offset": item[1],
                    "reason": "frozen_baseline_entry",
                }
            )
            continue
        if item[1] < controller_start or item[1] >= controller_end:
            raise ValueError("dedup root escapes the controller range")
        if item[1] % 2:
            raise ValueError("dedup root is misaligned")
        if item not in scheduled:
            heapq.heappush(pending, _key(*item))
            scheduled.add(item)
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    incoming: dict[
        tuple[str, int], list[tuple[tuple[str, int], str]]
    ] = defaultdict(list)
    opaque_baseline: list[dict[str, Any]] = []
    opaque_external: list[dict[str, Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if offset in baseline_occupied:
            raise _baseline_middle_error(offset, "bounded traversal")
        if offset < controller_start or offset >= controller_end:
            raise ValueError("bounded traversal escaped the controller range")
        if len(nodes) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("bounded CFG instruction budget exhausted")
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        if any(
            byte in baseline_occupied
            for byte in range(offset, offset + decoded["size"])
        ):
            raise _baseline_middle_error(offset, "bounded instruction")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            target_offset = target[1]
            if not (
                controller_start <= target_offset < controller_end
                and target[0] == "thumb"
                and target_offset % 2 == 0
                and 0 <= target_offset < len(rom)
            ):
                opaque_external.append(
                    {
                        "source": {"file_offset": offset, "mode": mode},
                        "edge_kind": edge["kind"],
                        "target_mode": target[0],
                        "target_file_offset": target_offset,
                        "reason": "outside_controller_range",
                    }
                )
                continue
            if any(
                byte in baseline_occupied
                for byte in range(target_offset, target_offset + 2)
            ):
                if target not in baseline_entries:
                    raise _baseline_middle_error(target_offset, "CFG edge")
                opaque_baseline.append(
                    {
                        "source": {"file_offset": offset, "mode": mode},
                        "edge_kind": edge["kind"],
                        "target_mode": target[0],
                        "target_file_offset": target_offset,
                        "reason": "frozen_baseline_entry",
                    }
                )
                continue
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    return nodes, rejected, incoming, opaque_baseline + opaque_external, skipped


def _occupied_bytes(
    entries: dict[tuple[str, int], dict[str, Any]],
) -> set[int]:
    return {
        byte
        for (_, offset), entry in entries.items()
        for byte in range(offset, offset + entry["size"])
    }


def _summary_from_blocks(
    blocks: list[dict[str, Any]],
    frontiers: list[dict[str, Any]],
    nodes: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": len(nodes),
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(
            sorted(
                Counter(
                    item.get("reason") for item in frontiers
                    if item.get("reason") is not None
                ).items()
            )
        ),
        "reachable_instruction_bytes": _union_bytes(
            [(offset, offset + node["size"]) for (_, offset), node in nodes.items()]
        ),
    }


def _bounded_payload(root: Path, rom: bytes) -> dict[str, Any]:
    controller_start, controller_end = CONTROLLER_RANGE
    if _sha(rom[controller_start:controller_end]) != CONTROLLER_SHA256:
        raise ValueError("battle-controller body changed")
    if _sha(rom) != ROM_SHA256 or len(rom) != ROM_SIZE:
        raise ValueError("base ROM identity changed")
    dispatcher = _dispatch_denominator(rom)
    roots = _dedup_roots(dispatcher)
    if len(roots) != dispatcher["nondefault_state_count"]:
        raise ValueError(
            "dedup root count disagrees with the dispatcher mapping denominator"
        )
    # Frozen baselines: bytes already classified by existing CFG artifacts
    # are treated as opaque.  We rebuild the baseline instruction entries
    # locally using only the publicly available verifier exports so the
    # exporter remains free of audit-tool imports.  The eight direct-call
    # Thumb BL producer ranges already recorded as cfg_proven_roots_*_producer
    # claims are added to the opaque set so the new CFG never re-claims them.
    # Both the baseline artifact loader and the producer loader independently
    # rebuild (occupied bytes, legal instruction entries); only an exact
    # (mode, offset) entry may be opaque-stopped.  Jumping into the middle of
    # a frozen baseline instruction must fail closed (§9.1 #4).
    baseline_occupied, baseline_entries = _baseline_occupied_bytes(root, rom)
    producer_occupied, producer_entries = _producer_occupied_bytes()
    baseline_occupied = baseline_occupied | producer_occupied
    baseline_entries = baseline_entries | producer_entries
    nodes, rejected, incoming, opaque_edges, skipped_roots = _traverse_bounded(
        rom,
        roots,
        baseline_entries=baseline_entries,
        baseline_occupied=baseline_occupied,
    )
    _assert_nonoverlapping_nodes(nodes)
    # Convert roots into the canonical shape expected by the inventory
    # helpers (``mode`` + ``file_offset`` + ``root_id``).
    canonical_roots = [
        {
            "mode": "thumb",
            "file_offset": root["target_offset"],
            "gba_address": root["gba_address"],
            "entry_size": root["entry_size"],
            "entry_sha256": root["entry_sha256"],
            "root_id": f"root-thumb-{root['target_offset']:06x}",
            "sources": [{"source_state": state} for state in root["source_states"]],
        }
        for root in roots
    ]
    root_keys = {("thumb", root["target_offset"]) for root in roots}
    blocks, node_to_block = _build_blocks(rom, nodes, root_keys)
    frontiers = _frontier_records(
        nodes, rejected, incoming, canonical_roots, node_to_block
    )
    summary = _summary_from_blocks(blocks, frontiers, nodes)
    root_records = _bounded_root_records(roots, blocks, frontiers, node_to_block)
    # Skipped roots are still part of the dispatcher mapping denominator but
    # are not reachable in this bounded CFG; surface them in the manifest so
    # downstream audits can account for the discrepancy.
    skipped_records = sorted(skipped_roots, key=lambda item: item["target_file_offset"])
    all_opaque = list(opaque_edges) + skipped_records
    opaque_records = _opaque_edge_records(all_opaque)
    summary_with_opaque = dict(summary)
    summary_with_opaque["opaque_external_edge_count"] = sum(
        1 for item in all_opaque if item["reason"] == "outside_controller_range"
    )
    summary_with_opaque["opaque_baseline_edge_count"] = sum(
        1 for item in all_opaque if item["reason"] == "frozen_baseline_entry"
    )
    summary_with_opaque["skipped_root_count"] = len(skipped_records)
    return {
        "dispatcher": dispatcher,
        "controller": {
            "range": list(CONTROLLER_RANGE),
            "sha256": CONTROLLER_SHA256,
        },
        "roots": root_records,
        "extension": {
            "blocks": blocks,
            "frontiers": frontiers,
            "opaque_edges": opaque_records,
            "summary": summary_with_opaque,
        },
    }


def _bounded_root_records(
    roots: list[dict[str, Any]],
    blocks: list[dict[str, Any]],
    frontiers: list[dict[str, Any]],
    node_to_block: dict[tuple[str, int], str],
) -> list[dict[str, Any]]:
    """Per-root reachable instruction count from the CFG edge worklist.

    Each root's reachable set is the union of all instruction members of every
    block reachable from the root's entry block via the explicit
    ``blocks[*].successors[*].block_id`` edges.  The traversal walks block IDs
    only — it must not scan the full ``node_to_block`` map pretending every
    node is a successor (§9.1 #5).
    """

    block_members: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for key, block_id in node_to_block.items():
        block_members[block_id].append(key)

    # Build the block successor edge map from the canonical block records.
    # Each successor's ``block_id`` is the block that the CFG edge points to;
    # only edges whose ``block_id`` resolves to a known block are followed.
    block_successors: dict[str, list[str]] = defaultdict(list)
    known_block_ids = {block["id"] for block in blocks}
    for block in blocks:
        for successor in block.get("successors", []) or []:
            target_block_id = successor.get("block_id")
            if target_block_id and target_block_id in known_block_ids:
                block_successors[block["id"]].append(target_block_id)

    records: list[dict[str, Any]] = []
    for root in roots:
        target = root["target_offset"]
        entry_key = ("thumb", target)
        entry_block_id = node_to_block.get(entry_key)
        reachable_keys: set[tuple[str, int]] = set()
        if entry_block_id is not None:
            visited: set[str] = set()
            queue: list[str] = [entry_block_id]
            while queue:
                current_block_id = queue.pop(0)
                if current_block_id in visited:
                    continue
                visited.add(current_block_id)
                for member in block_members.get(current_block_id, []):
                    reachable_keys.add(member)
                for successor_block_id in block_successors.get(
                    current_block_id, []
                ):
                    if successor_block_id not in visited:
                        queue.append(successor_block_id)
        records.append(
            {
                "target_offset": target,
                "gba_address": root["gba_address"],
                "entry_sha256": root["entry_sha256"],
                "entry_size": root["entry_size"],
                "source_states": root["source_states"],
                "dispatch_transfer": root["dispatch_transfer"],
                "entry_block_id": entry_block_id,
                "reachable_instruction_count": len(reachable_keys),
            }
        )
    records.sort(key=lambda item: item["target_offset"])
    return records


def _opaque_edge_records(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = [
        {
            "source": edge["source"],
            "edge_kind": edge["edge_kind"],
            "target_mode": edge["target_mode"],
            "target_file_offset": edge["target_file_offset"],
            "reason": edge["reason"],
        }
        for edge in edges
    ]
    records.sort(
        key=lambda item: (
            item["source"]["file_offset"],
            item["source"]["mode"],
            item["edge_kind"],
            item["target_file_offset"],
            item["target_mode"],
        )
    )
    return records


def _baseline_occupied_bytes(
    root: Path, rom: bytes
) -> tuple[set[int], set[tuple[str, int]]]:
    """Load the occupied bytes and legal instruction entries of the four
    frozen CFG baselines.

    The exporter never claims these bytes: they are opaque stop targets.  The
    function is independent of the audit module and uses only the publicly
    available verifier exports for the four frozen artifacts.

    Identity contract (§9.1 #4): each payload's raw bytes are read first and
    compared against ``FROZEN_BASELINE_PAYLOAD_SHA256`` by relative path.
    Any deviation — constant key set not exactly the four expected paths,
    a missing key for a payload we look up, or a raw SHA256 mismatch — fails
    closed with ``ValueError`` before any JSON parsing happens.  Only after
    the identity check passes do we ``json.loads(raw)`` and run the per-block
    semantic validation.

    Returns ``(occupied_bytes, entries)`` where ``entries`` is the set of
    ``(mode, offset)`` tuples representing the **exact** instruction entry
    offset of every baseline block.  A CFG edge whose target sits in
    ``occupied_bytes`` but whose ``(mode, offset)`` is not in ``entries`` is
    a baseline-middle violation and must fail closed (§9.1 #4).
    """

    expected_paths = frozenset(FROZEN_BASELINE_PAYLOAD_SHA256.keys())
    canonical_paths = frozenset(
        {
            "artifacts/rom-cfg-inventory-v2/rom-cfg-inventory.json",
            "artifacts/rom-cfg-inventory-v3/rom-cfg-inventory-v3.json",
            "artifacts/rom-cfg-proven-roots-v1/rom-cfg-proven-roots.json",
            "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json",
        }
    )
    if expected_paths != canonical_paths or len(expected_paths) != 4:
        raise ValueError(
            "FROZEN_BASELINE_PAYLOAD_SHA256 must contain exactly the four "
            "frozen baseline payload paths; missing="
            f"{sorted(canonical_paths - expected_paths)}, extra="
            f"{sorted(expected_paths - canonical_paths)}"
        )

    occupied: set[int] = set()
    entries: set[tuple[str, int]] = set()
    for artifact_path, payload_name in (
        ("artifacts/rom-cfg-inventory-v2", "rom-cfg-inventory.json"),
        ("artifacts/rom-cfg-inventory-v3", "rom-cfg-inventory-v3.json"),
        ("artifacts/rom-cfg-proven-roots-v1", "rom-cfg-proven-roots.json"),
        ("artifacts/rom-cfg-proven-roots-v2", "rom-cfg-proven-roots-v2.json"),
    ):
        relative_path = f"{artifact_path}/{payload_name}"
        try:
            raw = _safe_file(root, Path(artifact_path) / payload_name).read_bytes()
        except (OSError, ValueError) as error:
            raise ValueError(
                f"frozen baseline payload is unreadable: {relative_path}"
            ) from error
        # §9.1 #4 identity check: raw SHA must match the module constant
        # BEFORE any JSON parsing.  No artefact self-reported hash, no
        # canonical-JSON normalisation before hashing.
        expected_sha = FROZEN_BASELINE_PAYLOAD_SHA256.get(relative_path)
        if expected_sha is None:
            raise ValueError(
                f"frozen baseline payload path is not in the identity table: "
                f"{relative_path}"
            )
        actual_sha = _sha(raw)
        if actual_sha != expected_sha:
            raise ValueError(
                f"frozen baseline payload SHA mismatch: {relative_path} "
                f"expected={expected_sha} actual={actual_sha}"
            )
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(
                f"frozen baseline payload is not valid JSON: {relative_path}"
            ) from error
        if payload.get("schema") in {
            "rom-cfg-inventory-v2",
            "rom-cfg-inventory-v3",
            "rom-cfg-proven-roots-v1",
            "rom-cfg-proven-roots-v2",
        }:
            blocks = payload.get("blocks") or payload.get("extension", {}).get(
                "blocks"
            )
        else:
            raise ValueError(
                f"frozen baseline payload schema is not recognised: "
                f"{payload.get('schema')}"
            )
        if not isinstance(blocks, list):
            raise ValueError(f"frozen baseline blocks missing: {artifact_path}")
        for block in blocks:
            if not isinstance(block, dict):
                raise ValueError("frozen baseline block invalid")
            value = block.get("range")
            if (
                not isinstance(value, list)
                or len(value) != 2
                or any(type(offset) is not int for offset in value)
            ):
                raise ValueError("frozen baseline block range invalid")
            start, end = value
            if start < 0 or start >= end or end > len(rom):
                raise ValueError("frozen baseline block range escapes ROM")

            mode = block.get("mode")
            if mode not in {"thumb", "arm"}:
                raise ValueError(
                    f"frozen baseline block mode invalid: {artifact_path} -> {mode!r}"
                )

            instruction_count = block.get("instruction_count")
            if type(instruction_count) is not int or instruction_count <= 0:
                raise ValueError("frozen baseline instruction_count invalid")
            bytes_sha256 = block.get("bytes_sha256")
            if (
                not isinstance(bytes_sha256, str)
                or len(bytes_sha256) != 64
                or any(character not in "0123456789abcdef" for character in bytes_sha256)
                or _sha(rom[start:end]) != bytes_sha256
            ):
                raise ValueError("frozen baseline block bytes_sha256 mismatch")

            offset = start
            decoded_count = 0
            while offset < end:
                instruction = _decode_one(rom, offset, mode)
                if not isinstance(instruction, dict) or not instruction.get("accepted"):
                    raise ValueError("frozen baseline instruction rejected")
                if instruction.get("mode") != mode:
                    raise ValueError("frozen baseline instruction mode mismatch")
                if instruction.get("file_offset") != offset:
                    raise ValueError("frozen baseline instruction offset mismatch")
                size = instruction.get("size")
                if type(size) is not int or size <= 0:
                    raise ValueError("frozen baseline instruction size invalid")
                instruction_end = offset + size
                if instruction_end > end:
                    raise ValueError("frozen baseline instruction escapes block")

                entries.add((mode, offset))
                occupied.update(range(offset, instruction_end))
                decoded_count += 1
                offset = instruction_end

            if offset != end:
                raise ValueError("frozen baseline block decode did not end exactly")
            if decoded_count != instruction_count:
                raise ValueError("frozen baseline instruction_count mismatch")
    return occupied, entries


def _producer_occupied_bytes() -> tuple[set[int], set[tuple[str, int]]]:
    """Return ``(occupied_bytes, entries)`` of the eight frozen direct-call
    Thumb BL producers.

    These bytes are already classified as cfg_proven_roots_*_direct_thumb_bl_producer
    claims by the proven-roots-v1 and proven-roots-v2 audits; the new bounded
    CFG must treat them as opaque and never re-claim them as reachable code.
    The returned ``entries`` set contains the legal ``("thumb", start)``
    instruction entry for every producer range; an edge landing in
    ``occupied_bytes`` but not in ``entries`` is a baseline-middle violation
    and must fail closed (§9.1 #4).
    """

    occupied: set[int] = set()
    entries: set[tuple[str, int]] = set()
    for start, end in EXISTING_PRODUCER_RANGES:
        if end - start != 4:
            raise ValueError(
                f"existing producer range is not a 4-byte Thumb BL: "
                f"[0x{start:06X}, 0x{end:06X})"
            )
        entries.add(("thumb", start))
        for byte in range(start, end):
            occupied.add(byte)
    return occupied, entries


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError(
            "battle-controller CFG output cannot be repository root or ancestor"
        )
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("battle-controller CFG output is not a directory")
    members = list(target.iterdir())
    if not members:
        return target
    if {member.name for member in members} != {MANIFEST_NAME, PAYLOAD_NAME} or any(
        member.is_symlink() or not member.is_file() for member in members
    ):
        raise ValueError(
            "existing directory is not a replaceable battle-controller CFG artifact"
        )
    import importlib

    try:
        verify_module = importlib.import_module("tools.verify_rom_battle_controller_cfg")
    except ImportError as error:
        raise ValueError(
            "battle-controller CFG verifier is not importable; cannot validate "
            "replaceable artifact"
        ) from error
    verify_rom_battle_controller_cfg = verify_module.verify_rom_battle_controller_cfg
    report = verify_rom_battle_controller_cfg(root, target, allow_implementation_drift=True)
    if not report.get("verified"):
        raise ValueError(
            "existing directory is not a replaceable battle-controller CFG "
            f"artifact: {report.get('errors', [])}"
        )
    return target


def export_battle_controller_cfg(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output_dir = _validate_output_dir(root, output_dir)
    rom = _safe_file(root, ROM_PATH).read_bytes()
    payload = _bounded_payload(root, rom)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".rom-battle-controller-cfg-", dir=output_dir.parent)
    )
    try:
        full_payload = {
            "schema": SCHEMA,
            "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
            "limits": {
                "max_instruction_count": MAX_INSTRUCTION_COUNT,
                "max_basic_block_instruction_count": MAX_BLOCK_INSTRUCTION_COUNT,
                "decode_window_bytes": 4,
            },
            "controller": payload["controller"],
            "dispatcher": payload["dispatcher"],
            "roots": payload["roots"],
            "extension": payload["extension"],
            "implementation": {
                "exporter_sha256": _sha((root / "tools/export_rom_battle_controller_cfg.py").read_bytes()),
                "verifier_sha256": _sha((root / "tools/verify_rom_battle_controller_cfg.py").read_bytes()),
                "test_sha256": _sha(
                    (root / "tests/test_export_rom_battle_controller_cfg.py").read_bytes()
                ),
            },
        }
        payload_raw = _canonical_json(full_payload)
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        manifest = {
            "artifact_schema": SCHEMA,
            "rom": full_payload["rom"],
            "controller": full_payload["controller"],
            "dispatch_summary": {
                "input_denominator": payload["dispatcher"]["input_denominator"],
                "nondefault_state_count": payload["dispatcher"]["nondefault_state_count"],
                "default_state_count": payload["dispatcher"]["default_state_count"],
                "default_target": payload["dispatcher"]["default_target"],
                "dispatcher_range": payload["dispatcher"]["dispatcher_range"],
                "dispatcher_sha256": payload["dispatcher"]["dispatcher_sha256"],
                "mapping_denominator_sha256": payload["dispatcher"][
                    "mapping_denominator_sha256"
                ],
            },
            "root_count": len(payload["roots"]),
            "extension_summary": payload["extension"]["summary"],
            "files": {
                PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)},
            },
            "implementation": full_payload["implementation"],
        }
        (temporary / MANIFEST_NAME).write_bytes(_canonical_json(manifest))
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
        default=Path("artifacts/rom-battle-controller-cfg-v1"),
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    manifest = export_battle_controller_cfg(args.root, output)
    print(json.dumps(manifest["extension_summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())