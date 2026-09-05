#!/usr/bin/env python3
"""Resolve frozen v2 Thumb dispatch frontiers and extend the CFG once."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import heapq
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.export_rom_cfg_inventory import (
    MAX_BLOCK_INSTRUCTION_COUNT,
    MAX_INSTRUCTION_COUNT,
    ROM_PATH,
    ROM_SHA256,
    _assert_nonoverlapping_nodes,
    _build_blocks,
    _canonical_json,
    _canonical_sha,
    _decoder_identity,
    _decode_one,
    _frontier_records,
    _key,
    _reject_symlink_components,
    _replace_output_dir,
    _root_results,
    _safe_file,
    _seed_payload,
    _traverse,
    _union_bytes,
)
from tools.verify_rom_cfg_inventory import verify_rom_cfg_inventory
from tools.verify_rom_cfg_inventory_v3 import verify_rom_cfg_inventory_v3


ROM_BASE = 0x08000000
SCHEMA = "rom-cfg-inventory-v3"
PAYLOAD_NAME = "rom-cfg-inventory-v3.json"
V2_ARTIFACT = Path("artifacts/rom-cfg-inventory-v2")
V2_PAYLOAD_NAME = "rom-cfg-inventory.json"
V2_MANIFEST_SHA256 = (
    "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"
)
V2_PAYLOAD_SHA256 = (
    "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
)
V2_PAYLOAD_SIZE = 5_936_694
V2_VERIFIER = Path("tools/verify_rom_cfg_inventory.py")
V2_VERIFIER_SHA256 = (
    "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"
)
V2_SCHEMA = "rom-cfg-inventory-v2"
V2_GRAPH_DENOMINATOR_SHA256 = (
    "e3f6c04ea459dbec397a9d71d6f32591ec03ed076ff8aad227277cb2b3534ba3"
)
ORDERED_TARGET_VECTOR_SHA256 = (
    "ab4572dcb948a49e6172e18f2fd9c482e61ee018c42cf0be77bd0e67f0c86615"
)

SCOPE = {
    "base_cfg_denominator_frozen": True,
    "fixed_dispatch_frontier_allowlist_complete": True,
    "indexed_dispatch_targets_derived_from_raw_rom": True,
    "one_generation_direct_cfg_extension_performed": True,
    "recursive_indirect_resolution_performed": False,
    "global_dispatch_source_denominator_complete": False,
    "global_function_entry_denominator_complete": False,
    "runtime_reachability_complete": False,
}
LIMITATIONS = [
    "The v3 delta resolves only 29 explicitly frozen v2 indexed Thumb dispatch frontiers.",
    "New indirect frontiers discovered by the extension remain unresolved in this generation.",
    "The delta references immutable v2 instruction entries instead of duplicating their bytes.",
    "Static CFG reachability does not prove natural gameplay or runtime reachability.",
]


# (frozen v2 frontier id, terminal offset, proof-window start, allowed indices)
_DISPATCH_SPECS = (
    ("frontier-000032", 0x064C98, 0x064C86, tuple(range(16))),
    ("frontier-000033", 0x064F0E, 0x064EF8, tuple(range(14))),
    ("frontier-000061", 0x06717A, 0x06716A, tuple(range(14))),
    ("frontier-000097", 0x06BBBC, 0x06BBAC, tuple(range(25))),
    ("frontier-000106", 0x06C46E, 0x06C458, tuple(range(60))),
    ("frontier-000108", 0x06D234, 0x06D220, tuple(range(20))),
    ("frontier-000112", 0x06D7AA, 0x06D79C, tuple(range(7))),
    ("frontier-000114", 0x06D886, 0x06D878, tuple(range(7))),
    ("frontier-000117", 0x06DC72, 0x06DC62, tuple(range(10))),
    ("frontier-000124", 0x06EE8C, 0x06EE7A, (0, 2, 4, 6, 8)),
    ("frontier-000127", 0x06F4E2, 0x06F4D2, tuple(range(6))),
    ("frontier-000133", 0x06FF22, 0x06FF12, tuple(range(46))),
    ("frontier-000140", 0x07098C, 0x070978, tuple(range(38))),
    ("frontier-000143", 0x071D48, 0x071D34, tuple(range(38))),
    ("frontier-000144", 0x071F4A, 0x071F3A, tuple(range(8))),
    ("frontier-000152", 0x076F3C, 0x076F26, tuple(range(63))),
    ("frontier-000169", 0x07AE4E, 0x07AE40, tuple(range(8))),
    ("frontier-000170", 0x07B13C, 0x07B130, tuple(range(8))),
    ("frontier-000176", 0x07B954, 0x07B940, tuple(range(22))),
    ("frontier-000177", 0x07BEC8, 0x07BEB6, (0, 2, 4, 6, 8)),
    ("frontier-000182", 0x07CAA0, 0x07CA8A, tuple(range(63))),
    ("frontier-000184", 0x07DD5A, 0x07DD4A, tuple(range(25))),
    ("frontier-000200", 0x0815CC, 0x0815BC, tuple(range(7))),
    ("frontier-000214", 0x086414, 0x086406, tuple(range(34))),
    ("frontier-000224", 0x088B22, 0x088B14, tuple(range(34))),
    ("frontier-000236", 0x08C2F6, 0x08C2E8, tuple(range(21))),
    ("frontier-000289", 0x096BA4, 0x096B96, tuple(range(9))),
    ("frontier-000301", 0x09722A, 0x09721E, tuple(range(6))),
    ("frontier-000308", 0x0977E8, 0x0977DA, tuple(range(58))),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _halfword(rom: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(rom):
        raise ValueError("raw Thumb dispatch window leaves the fixed ROM")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def _require_sparse_mask(
    rom: bytes, window_start: int, comparison_offset: int, index_register: int
) -> None:
    for offset in range(window_start, comparison_offset - 1, 2):
        move = _halfword(rom, offset)
        logical_and = _halfword(rom, offset + 2)
        if move & 0xF800 != 0x2000 or move & 0xFF != 0x0E:
            continue
        mask_register = (move >> 8) & 0x7
        if (
            logical_and & 0xFFC0 == 0x4000
            and logical_and & 0x7 == index_register
            and mask_register
            in (index_register, (logical_and >> 3) & 0x7)
        ):
            return
    raise ValueError("raw Thumb dispatch sparse index mask changed")


def _resolve_thumb_indexed_dispatches(
    rom: bytes, v2_payload: dict[str, Any]
) -> dict[str, Any]:
    """Derive the fixed 29 indexed Thumb dispatches from raw ROM bytes.

    The allowlist freezes only the audited v2 frontier identities, proof-window
    starts and reachable index sets.  Opcodes, registers, bounds, branch gates,
    literal locations, table bases and every target are derived from the ROM.
    """

    if (
        v2_payload.get("schema") != V2_SCHEMA
        or v2_payload.get("graph_denominator_sha256")
        != V2_GRAPH_DENOMINATOR_SHA256
    ):
        raise ValueError("frozen v2 CFG denominator changed")
    frontiers = v2_payload.get("frontiers")
    roots = v2_payload.get("roots")
    if not isinstance(frontiers, list) or not isinstance(roots, list) or len(roots) != 263:
        raise ValueError("frozen v2 CFG roots or frontiers changed")
    indirect = [item for item in frontiers if item.get("reason") == "indirect_pc_target"]
    if len(indirect) != 357:
        raise ValueError("frozen v2 indirect frontier denominator changed")
    by_id = {item.get("id"): item for item in frontiers}
    if len(by_id) != len(frontiers):
        raise ValueError("frozen v2 frontier identities are not unique")
    existing_roots = {
        (root.get("mode"), root.get("file_offset")) for root in roots
    }

    dispatches: list[dict[str, Any]] = []
    ordered_pointer_bytes: list[bytes] = []
    sources_by_target: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frontier_id, terminal, window_start, expected_indices in _DISPATCH_SPECS:
        frontier = by_id.get(frontier_id)
        source = frontier.get("source") if isinstance(frontier, dict) else None
        if (
            frontier is None
            or frontier.get("reason") != "indirect_pc_target"
            or not isinstance(source, dict)
            or source.get("kind") != "block"
            or source.get("instruction_offset") != terminal
        ):
            raise ValueError(f"frozen v2 frontier changed: {frontier_id}")

        tail_start = terminal - 8
        move_pc = _halfword(rom, terminal)
        load_target = _halfword(rom, terminal - 2)
        add_base = _halfword(rom, terminal - 4)
        load_literal = _halfword(rom, terminal - 6)
        scale_index = _halfword(rom, tail_start)
        if (
            move_pc != 0x4687
            or load_target != 0x6800
            or add_base != 0x1840
            or load_literal & 0xF800 != 0x4800
            or (load_literal >> 8) & 0x7 != 1
            or scale_index & 0xF800 != 0
            or (scale_index >> 6) & 0x1F != 2
            or scale_index & 0x7 != 0
        ):
            raise ValueError(f"raw Thumb dispatch tail changed: {frontier_id}")
        index_register = (scale_index >> 3) & 0x7

        comparisons = []
        for offset in range(window_start, tail_start, 2):
            value = _halfword(rom, offset)
            if value & 0xF800 == 0x2800 and (value >> 8) & 0x7 == index_register:
                comparisons.append((offset, value & 0xFF))
        if len(comparisons) != 1:
            raise ValueError(f"raw Thumb dispatch comparison changed: {frontier_id}")
        comparison_offset, comparison_max = comparisons[0]
        branch_offset = comparison_offset + 2
        branch = _halfword(rom, branch_offset)
        condition = (branch >> 8) & 0xF
        if branch & 0xF000 != 0xD000 or condition not in (8, 9):
            raise ValueError(f"raw Thumb dispatch bound branch changed: {frontier_id}")
        branch_target = branch_offset + 4 + _sign_extend((branch & 0xFF) << 1, 9)
        branch_direction = "outside_on_unsigned_higher"
        if condition == 9:
            if branch_target != tail_start:
                raise ValueError(f"raw Thumb dispatch BLS entry changed: {frontier_id}")
            branch_direction = "inside_on_unsigned_lower_or_same"
        elif branch_offset + 2 != tail_start or branch_target == tail_start:
            raise ValueError(f"raw Thumb dispatch BHI fallback changed: {frontier_id}")

        allowed_indices = list(expected_indices)
        if comparison_max != max(allowed_indices):
            raise ValueError(f"raw Thumb dispatch comparison maximum changed: {frontier_id}")
        contiguous = list(range(comparison_max + 1))
        if allowed_indices != contiguous:
            if allowed_indices != list(range(0, comparison_max + 1, 2)):
                raise ValueError(f"unsupported sparse Thumb dispatch set: {frontier_id}")
            _require_sparse_mask(rom, window_start, comparison_offset, index_register)

        literal_offset = (
            (terminal - 6 + 4) & ~3
        ) + (load_literal & 0xFF) * 4
        if literal_offset < 0 or literal_offset + 4 > len(rom):
            raise ValueError(f"raw Thumb dispatch literal leaves ROM: {frontier_id}")
        table_pointer = int.from_bytes(
            rom[literal_offset : literal_offset + 4], "little"
        )
        table_start = table_pointer - ROM_BASE
        table_end = table_start + (comparison_max + 1) * 4
        if (
            table_start < 0
            or table_start % 4
            or table_end > len(rom)
        ):
            raise ValueError(f"raw Thumb dispatch table leaves ROM: {frontier_id}")

        targets = []
        dispatch_pointer_bytes = []
        for slot_index in allowed_indices:
            entry_offset = table_start + slot_index * 4
            raw = rom[entry_offset : entry_offset + 4]
            pointer = int.from_bytes(raw, "little")
            target_offset = pointer - ROM_BASE
            if (
                pointer < ROM_BASE
                or pointer >= ROM_BASE + len(rom)
                or pointer & 1
                or target_offset % 2
            ):
                raise ValueError(
                    f"raw Thumb dispatch target outside fixed ROM: {frontier_id} slot {slot_index}"
                )
            target = {
                "slot_index": slot_index,
                "entry_offset": entry_offset,
                "raw_pointer": pointer,
                "mode": "thumb",
                "file_offset": target_offset,
                "gba_address": f"0x{pointer:08X}",
            }
            targets.append(target)
            dispatch_pointer_bytes.append(raw)
            ordered_pointer_bytes.append(raw)
            sources_by_target[target_offset].append(
                {
                    "source_kind": "resolved_thumb_indexed_dispatch",
                    "source_frontier_id": frontier_id,
                    "terminal_offset": terminal,
                    "slot_index": slot_index,
                    "entry_offset": entry_offset,
                }
            )

        proof_end = terminal + 2
        dispatches.append(
            {
                "source_frontier_id": frontier_id,
                "source_block_id": source["block_id"],
                "terminal_offset": terminal,
                "proof_range": [window_start, proof_end],
                "proof_sha256": _sha(rom[window_start:proof_end]),
                "index_register": f"r{index_register}",
                "comparison_offset": comparison_offset,
                "comparison_max": comparison_max,
                "bound_branch": {
                    "file_offset": branch_offset,
                    "condition": "bhi" if condition == 8 else "bls",
                    "target_offset": branch_target,
                    "direction": branch_direction,
                },
                "literal_offset": literal_offset,
                "table_pointer": f"0x{table_pointer:08X}",
                "table_range": [table_start, table_end],
                "table_sha256": _sha(rom[table_start:table_end]),
                "allowed_indices": allowed_indices,
                "ordered_target_vector_sha256": _sha(
                    b"".join(dispatch_pointer_bytes)
                ),
                "targets": targets,
            }
        )

    vector_sha = _sha(b"".join(ordered_pointer_bytes))
    if vector_sha != ORDERED_TARGET_VECTOR_SHA256:
        raise ValueError("raw Thumb dispatch ordered target vector changed")
    unique_targets = sorted(sources_by_target)
    existing_targets = [
        offset for offset in unique_targets if ("thumb", offset) in existing_roots
    ]
    new_targets = [
        offset for offset in unique_targets if ("thumb", offset) not in existing_roots
    ]
    if len(existing_targets) != 183 or len(new_targets) != 107:
        raise ValueError("raw Thumb dispatch extension-root denominator changed")
    nonfixed_root_target_seeds = []
    for offset in new_targets:
        nonfixed_root_target_seeds.append(
            {
                "mode": "thumb",
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "entry_size": 4,
                "entry_sha256": _sha(rom[offset : offset + 4]),
                "sources": sources_by_target[offset],
            }
        )
    return {
        "baseline_graph_denominator_sha256": V2_GRAPH_DENOMINATOR_SHA256,
        "baseline_indirect_frontier_count": len(indirect),
        "resolved_frontier_count": len(dispatches),
        "unresolved_baseline_indirect_frontier_count": len(indirect) - len(dispatches),
        "ordered_edge_count": sum(len(item["targets"]) for item in dispatches),
        "unique_target_count": len(unique_targets),
        "existing_fixed_root_target_count": len(existing_targets),
        "not_fixed_root_target_count": len(nonfixed_root_target_seeds),
        "ordered_target_vector_sha256": vector_sha,
        "dispatches": dispatches,
        "nonfixed_root_target_seeds": nonfixed_root_target_seeds,
    }


def _v2_artifact_contract(
    root: Path, rom: bytes
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = _safe_file(root, V2_ARTIFACT / "manifest.json")
    payload_path = _safe_file(root, V2_ARTIFACT / V2_PAYLOAD_NAME)
    verifier_path = _safe_file(root, V2_VERIFIER)
    manifest_raw = manifest_path.read_bytes()
    payload_raw = payload_path.read_bytes()
    if _sha(manifest_raw) != V2_MANIFEST_SHA256:
        raise ValueError("frozen v2 CFG manifest changed")
    if len(payload_raw) != V2_PAYLOAD_SIZE or _sha(payload_raw) != V2_PAYLOAD_SHA256:
        raise ValueError("frozen v2 CFG payload changed")
    if _sha(verifier_path.read_bytes()) != V2_VERIFIER_SHA256:
        raise ValueError("frozen v2 CFG verifier changed")
    report = verify_rom_cfg_inventory(root, root / V2_ARTIFACT)
    expected_report = {
        "verified": True,
        "root_count": 263,
        "decoded_instruction_count": 40_872,
        "decoded_basic_block_count": 7_725,
        "reachable_instruction_bytes": 86_184,
        "frontier_count": 366,
        "independently_rebuilt_instruction_count": 40_872,
        "budget_exhausted": False,
        "errors": [],
    }
    if any(report.get(key) != value for key, value in expected_report.items()):
        raise ValueError(f"frozen v2 CFG independent verification failed: {report}")
    manifest = json.loads(manifest_raw)
    payload = json.loads(payload_raw)
    if (
        payload.get("schema") != V2_SCHEMA
        or payload.get("rom")
        != {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        or payload.get("graph_denominator_sha256")
        != V2_GRAPH_DENOMINATOR_SHA256
        or manifest.get("artifact_schema") != V2_SCHEMA
    ):
        raise ValueError("frozen v2 CFG top-level contract changed")
    return payload, manifest


def _all_dispatch_target_seeds(
    rom: bytes, resolution: dict[str, Any]
) -> list[dict[str, Any]]:
    sources: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for dispatch in resolution["dispatches"]:
        for target in dispatch["targets"]:
            sources[target["file_offset"]].append(
                {
                    "source_kind": "resolved_thumb_indexed_dispatch",
                    "source_frontier_id": dispatch["source_frontier_id"],
                    "terminal_offset": dispatch["terminal_offset"],
                    "slot_index": target["slot_index"],
                    "entry_offset": target["entry_offset"],
                }
            )
    seeds = []
    for offset in sorted(sources):
        seeds.append(
            {
                "mode": "thumb",
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "entry_size": 4,
                "entry_sha256": _sha(rom[offset : offset + 4]),
                "sources": sources[offset],
            }
        )
    if len(seeds) != 290:
        raise ValueError("resolved Thumb target seed denominator changed")
    return seeds


def _traverse_extension(
    rom: bytes,
    seeds: list[dict[str, Any]],
    baseline_nodes: dict[tuple[str, int], dict[str, Any]],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], list[tuple[tuple[str, int], str]]],
    list[tuple[tuple[str, int], str, tuple[str, int]]],
]:
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for seed in seeds:
        item = (seed["mode"], seed["file_offset"])
        if item in baseline_nodes:
            raise ValueError("extension seed is already a frozen v2 instruction entry")
        if item not in scheduled:
            heapq.heappush(pending, _key(*item))
            scheduled.add(item)
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    incoming: dict[
        tuple[str, int], list[tuple[tuple[str, int], str]]
    ] = defaultdict(list)
    base_crosses: list[tuple[tuple[str, int], str, tuple[str, int]]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if item in baseline_nodes:
            raise ValueError("extension worklist attempted to duplicate a v2 entry")
        if len(nodes) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("extension CFG instruction budget exhausted")
        decoded = _decode_one(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in baseline_nodes:
                base_crosses.append((item, edge["kind"], target))
                continue
            incoming[target].append((item, edge["kind"]))
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    return nodes, rejected, incoming, base_crosses


def _assert_disjoint_from_baseline(
    baseline_nodes: dict[tuple[str, int], dict[str, Any]],
    extension_nodes: dict[tuple[str, int], dict[str, Any]],
) -> None:
    occupied = {
        (mode, byte_offset)
        for (mode, offset), node in baseline_nodes.items()
        for byte_offset in range(offset, offset + node["size"])
    }
    overlap = [
        (mode, byte_offset)
        for (mode, offset), node in extension_nodes.items()
        for byte_offset in range(offset, offset + node["size"])
        if (mode, byte_offset) in occupied
    ]
    if overlap:
        raise ValueError(f"extension CFG overlaps frozen v2 bytes: {overlap[:8]}")


def _base_block_reference(
    blocks: list[dict[str, Any]], mode: str, offset: int
) -> dict[str, Any]:
    matches = [
        block
        for block in blocks
        if block["mode"] == mode and block["range"][0] <= offset < block["range"][1]
    ]
    if len(matches) != 1:
        raise ValueError(f"v2 instruction entry has no unique block at 0x{offset:06X}")
    return {
        "block_id": matches[0]["id"],
        "instruction_offset": offset,
        "mode": mode,
    }


def _extension_summary(
    nodes: dict[tuple[str, int], dict[str, Any]],
    blocks: list[dict[str, Any]],
    frontiers: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: dict[str, int] = {}
    for frontier in frontiers:
        reason = frontier["reason"]
        reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": len(nodes),
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(sorted(reasons.items())),
        "reachable_instruction_bytes": _union_bytes(
            [(offset, offset + node["size"]) for (_, offset), node in nodes.items()]
        ),
    }


def _base_cfg_record(
    baseline: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    file_record = manifest["files"][V2_PAYLOAD_NAME]
    return {
        "path": V2_ARTIFACT.as_posix(),
        "schema": V2_SCHEMA,
        "manifest_sha256": V2_MANIFEST_SHA256,
        "payload_file": V2_PAYLOAD_NAME,
        "payload_size": file_record["size"],
        "payload_sha256": file_record["sha256"],
        "verifier_path": V2_VERIFIER.as_posix(),
        "verifier_sha256": V2_VERIFIER_SHA256,
        "graph_denominator_sha256": baseline["graph_denominator_sha256"],
        "root_count": baseline["summary"]["root_count"],
        "frontier_count": baseline["summary"]["frontier_count"],
        "indirect_frontier_count": baseline["summary"]["frontier_reasons"][
            "indirect_pc_target"
        ],
        "summary": baseline["summary"],
    }


def build_cfg_inventory_v3_payload(
    root: Path, rom: bytes | None = None
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != 6_291_456 or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    baseline, baseline_manifest = _v2_artifact_contract(root, rom)
    seed_payload, _ = _seed_payload(root, rom)
    baseline_nodes, baseline_rejected, _ = _traverse(rom, seed_payload["seeds"])
    if len(baseline_nodes) != 40_872 or len(baseline_rejected) != 2:
        raise ValueError("frozen v2 instruction closure changed")

    resolution = _resolve_thumb_indexed_dispatches(rom, baseline)
    target_seeds = _all_dispatch_target_seeds(rom, resolution)
    base_target_seeds = [
        seed
        for seed in target_seeds
        if (seed["mode"], seed["file_offset"]) in baseline_nodes
    ]
    new_target_seeds = [
        seed
        for seed in target_seeds
        if (seed["mode"], seed["file_offset"]) not in baseline_nodes
    ]
    if len(base_target_seeds) != 189 or len(new_target_seeds) != 101:
        raise ValueError("v3 base-reference/new-entry split changed")

    nodes, rejected, incoming, base_crosses = _traverse_extension(
        rom, new_target_seeds, baseline_nodes
    )
    _assert_nonoverlapping_nodes(nodes)
    _assert_disjoint_from_baseline(baseline_nodes, nodes)
    root_keys = {(seed["mode"], seed["file_offset"]) for seed in new_target_seeds}
    blocks, node_to_block = _build_blocks(rom, nodes, root_keys)
    root_shells = [
        {
            "root_id": f"root-{seed['mode']}-{seed['file_offset']:06x}",
            "mode": seed["mode"],
            "file_offset": seed["file_offset"],
        }
        for seed in new_target_seeds
    ]
    frontiers = _frontier_records(
        nodes, rejected, incoming, root_shells, node_to_block
    )
    roots = _root_results(
        new_target_seeds, nodes, frontiers, node_to_block
    )
    if any(root_record["entry_block_id"] is None for root_record in roots):
        raise ValueError("a v3 dispatch target seed is not decodable")

    base_blocks = baseline["blocks"]
    base_entry_references = [
        {
            "seed": seed,
            "base_entry": _base_block_reference(
                base_blocks, seed["mode"], seed["file_offset"]
            ),
        }
        for seed in base_target_seeds
    ]
    base_cross_edges = []
    for source, edge_kind, target in base_crosses:
        base_cross_edges.append(
            {
                "source": {
                    "block_id": node_to_block[source],
                    "instruction_offset": source[1],
                    "edge_kind": edge_kind,
                },
                "target": _base_block_reference(base_blocks, target[0], target[1]),
            }
        )
    base_cross_edges.sort(
        key=lambda record: json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )

    extension_summary = _extension_summary(nodes, blocks, frontiers)
    expected_extension_summary = {
        "decoded_basic_block_count": 891,
        "decoded_instruction_count": 4_698,
        "frontier_count": 16,
        "frontier_reasons": {
            "indirect_pc_target": 15,
            "unsupported_armv4t_instruction": 1,
        },
        "reachable_instruction_bytes": 9_902,
    }
    if extension_summary != expected_extension_summary:
        raise ValueError(
            f"v3 extension denominator changed: {extension_summary}"
        )
    base_summary = baseline["summary"]
    combined_summary = {
        "decoded_basic_block_count": base_summary["decoded_basic_block_count"]
        + extension_summary["decoded_basic_block_count"],
        "decoded_instruction_count": base_summary["decoded_instruction_count"]
        + extension_summary["decoded_instruction_count"],
        "frontier_count": base_summary["frontier_count"]
        - resolution["resolved_frontier_count"]
        + extension_summary["frontier_count"],
        "frontier_reasons": {
            "bios_swi_external": base_summary["frontier_reasons"][
                "bios_swi_external"
            ],
            "indirect_pc_target": resolution[
                "unresolved_baseline_indirect_frontier_count"
            ]
            + extension_summary["frontier_reasons"]["indirect_pc_target"],
            "unsupported_armv4t_instruction": base_summary["frontier_reasons"][
                "unsupported_armv4t_instruction"
            ]
            + extension_summary["frontier_reasons"][
                "unsupported_armv4t_instruction"
            ],
        },
        "reachable_instruction_bytes": base_summary["reachable_instruction_bytes"]
        + extension_summary["reachable_instruction_bytes"],
    }
    static_dispatches = {
        key: value
        for key, value in resolution.items()
        if key != "nonfixed_root_target_seeds"
    }
    extension_policy = {
        "dispatch_target_count": len(target_seeds),
        "base_entry_reference_count": len(base_target_seeds),
        "new_entry_seed_count": len(new_target_seeds),
        "recursive_resolution_performed": False,
        "base_bytes_duplicated": False,
    }
    extension = {
        "target_seed_count": len(target_seeds),
        "target_seed_denominator_sha256": _canonical_sha(target_seeds),
        "base_entry_reference_count": len(base_entry_references),
        "base_entry_references": base_entry_references,
        "new_entry_seed_count": len(new_target_seeds),
        "new_entry_seeds": new_target_seeds,
        "roots": roots,
        "blocks": blocks,
        "frontiers": frontiers,
        "base_cross_edges": base_cross_edges,
        "summary": extension_summary,
    }
    base_cfg = _base_cfg_record(baseline, baseline_manifest)
    graph_denominator_sha256 = _canonical_sha(
        {
            "base_cfg": base_cfg,
            "static_dispatches": static_dispatches,
            "extension_policy": extension_policy,
            "extension": extension,
            "combined_summary": combined_summary,
        }
    )
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "base_cfg": base_cfg,
        "decoder": _decoder_identity(root),
        "limits": {
            "max_instruction_count": MAX_INSTRUCTION_COUNT,
            "max_basic_block_instruction_count": MAX_BLOCK_INSTRUCTION_COUNT,
            "decode_window_bytes": 4,
            "resolver_generation_count": 1,
        },
        "static_dispatches": static_dispatches,
        "extension_policy": extension_policy,
        "extension": extension,
        "combined_summary": combined_summary,
        "graph_denominator_sha256": graph_denominator_sha256,
        "scope": SCOPE,
        "limitations": LIMITATIONS,
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            _safe_file(root, "tools/export_rom_cfg_inventory_v3.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            _safe_file(root, "tools/verify_rom_cfg_inventory_v3.py").read_bytes()
        ),
        "test_sha256": _sha(
            _safe_file(root, "tests/test_export_rom_cfg_inventory_v3.py").read_bytes()
        ),
    }


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("CFG v3 output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("CFG v3 output is not a directory")
    members = list(target.iterdir())
    if not members:
        return target
    if (
        {member.name for member in members} != {"manifest.json", PAYLOAD_NAME}
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError("existing directory is not a replaceable CFG v3 artifact")
    report = verify_rom_cfg_inventory_v3(root, target)
    if not report.get("verified"):
        raise ValueError(
            "existing directory is not a replaceable CFG v3 artifact: "
            f"{report.get('errors', [])}"
        )
    return target


def export_rom_cfg_inventory_v3(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output_dir = _validate_output_dir(root, output_dir)
    payload = build_cfg_inventory_v3_payload(root)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".rom-cfg-inventory-v3-", dir=output_dir.parent)
    )
    try:
        payload_raw = _canonical_json(payload)
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        manifest = {
            "artifact_schema": SCHEMA,
            "rom": payload["rom"],
            "base_cfg": payload["base_cfg"],
            "decoder": payload["decoder"],
            "limits": payload["limits"],
            "static_dispatch_summary": {
                key: payload["static_dispatches"][key]
                for key in (
                    "baseline_indirect_frontier_count",
                    "resolved_frontier_count",
                    "unresolved_baseline_indirect_frontier_count",
                    "ordered_edge_count",
                    "unique_target_count",
                    "ordered_target_vector_sha256",
                )
            },
            "extension_policy": payload["extension_policy"],
            "extension_summary": payload["extension"]["summary"],
            "combined_summary": payload["combined_summary"],
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
        default=Path("artifacts/rom-cfg-inventory-v3"),
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    manifest = export_rom_cfg_inventory_v3(args.root, output)
    print(json.dumps(manifest["combined_summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
