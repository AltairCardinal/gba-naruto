#!/usr/bin/env python3
"""Independently verify the one-generation Thumb-dispatch CFG extension."""

from __future__ import annotations

import argparse
from collections import defaultdict
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

from tools.verify_rom_cfg_inventory import (
    MAX_BLOCK_INSTRUCTION_COUNT,
    MAX_INSTRUCTION_COUNT,
    ROM_PATH,
    ROM_SHA256,
    _canonical_sha,
    _decode,
    _decoder_identity,
    _expected_roots,
    _rebuild_instruction_entries,
    _safe_file,
    _seed_contract,
    _sha,
    _verify_blocks,
    verify_rom_cfg_inventory,
)


ROM_BASE = 0x08000000
SCHEMA = "rom-cfg-inventory-v3"
VERIFY_SCHEMA = "rom-cfg-inventory-verification-v3"
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


_AUDITED_DISPATCHES = (
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


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _u16(rom: bytes, offset: int) -> int:
    if not 0 <= offset <= len(rom) - 2:
        raise ValueError("independent Thumb read leaves ROM")
    return int.from_bytes(rom[offset : offset + 2], "little")


def _signed(value: int, width: int) -> int:
    boundary = 1 << (width - 1)
    return (value ^ boundary) - boundary


def _independent_sparse_mask(
    rom: bytes, start: int, stop: int, index_register: int
) -> None:
    candidates = []
    for offset in range(start, stop - 1, 2):
        immediate_move = _u16(rom, offset)
        register_and = _u16(rom, offset + 2)
        if immediate_move & 0xF800 != 0x2000:
            continue
        if immediate_move & 0xFF != 14 or register_and & 0xFFC0 != 0x4000:
            continue
        immediate_register = (immediate_move >> 8) & 7
        source_register = (register_and >> 3) & 7
        destination_register = register_and & 7
        if (
            destination_register == index_register
            and immediate_register in (destination_register, source_register)
        ):
            candidates.append(offset)
    if len(candidates) != 1:
        raise ValueError("independent sparse-mask proof changed")


def _resolve_thumb_indexed_dispatches_independently(
    rom: bytes, baseline: dict[str, Any]
) -> dict[str, Any]:
    """Rebuild the dispatch contract without importing the exporter."""

    if baseline.get("schema") != V2_SCHEMA:
        raise ValueError("independent baseline schema changed")
    if baseline.get("graph_denominator_sha256") != V2_GRAPH_DENOMINATOR_SHA256:
        raise ValueError("independent baseline graph changed")
    frontier_list = baseline.get("frontiers")
    root_list = baseline.get("roots")
    if not isinstance(frontier_list, list) or not isinstance(root_list, list):
        raise ValueError("independent baseline lists are missing")
    if len(root_list) != 263:
        raise ValueError("independent baseline root denominator changed")
    indirect = [
        record for record in frontier_list
        if record.get("reason") == "indirect_pc_target"
    ]
    if len(indirect) != 357:
        raise ValueError("independent indirect denominator changed")
    frontier_index = {record.get("id"): record for record in frontier_list}
    if len(frontier_index) != len(frontier_list):
        raise ValueError("independent frontier ids are not unique")
    fixed_roots = {
        (record.get("mode"), record.get("file_offset")) for record in root_list
    }

    dispatch_records = []
    global_raw_targets = bytearray()
    target_sources: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for frontier_id, terminal, window_start, allowed_tuple in _AUDITED_DISPATCHES:
        frozen = frontier_index.get(frontier_id)
        source = frozen.get("source") if isinstance(frozen, dict) else None
        if (
            frozen is None
            or frozen.get("reason") != "indirect_pc_target"
            or not isinstance(source, dict)
            or source.get("kind") != "block"
            or source.get("instruction_offset") != terminal
        ):
            raise ValueError(f"independent frozen frontier changed: {frontier_id}")

        scale_offset = terminal - 8
        scale = _u16(rom, scale_offset)
        literal_load = _u16(rom, terminal - 6)
        if (
            _u16(rom, terminal) != 0x4687
            or _u16(rom, terminal - 2) != 0x6800
            or _u16(rom, terminal - 4) != 0x1840
            or literal_load & 0xF800 != 0x4800
            or (literal_load >> 8) & 7 != 1
            or scale & 0xF800
            or (scale >> 6) & 0x1F != 2
            or scale & 7
        ):
            raise ValueError(f"independent dispatch tail changed: {frontier_id}")
        index_register = (scale >> 3) & 7

        comparison_matches = []
        for offset in range(window_start, scale_offset, 2):
            opcode = _u16(rom, offset)
            if opcode & 0xF800 == 0x2800 and (opcode >> 8) & 7 == index_register:
                comparison_matches.append((offset, opcode & 0xFF))
        if len(comparison_matches) != 1:
            raise ValueError(f"independent comparison proof changed: {frontier_id}")
        comparison_offset, comparison_max = comparison_matches[0]
        bound_offset = comparison_offset + 2
        bound_opcode = _u16(rom, bound_offset)
        condition = (bound_opcode >> 8) & 15
        if bound_opcode & 0xF000 != 0xD000 or condition not in (8, 9):
            raise ValueError(f"independent bound proof changed: {frontier_id}")
        bound_target = bound_offset + 4 + _signed((bound_opcode & 255) << 1, 9)
        if condition == 9:
            if bound_target != scale_offset:
                raise ValueError(f"independent BLS entry changed: {frontier_id}")
            direction = "inside_on_unsigned_lower_or_same"
        else:
            if bound_offset + 2 != scale_offset or bound_target == scale_offset:
                raise ValueError(f"independent BHI fallback changed: {frontier_id}")
            direction = "outside_on_unsigned_higher"

        allowed = list(allowed_tuple)
        if comparison_max != max(allowed):
            raise ValueError(f"independent bound maximum changed: {frontier_id}")
        if allowed != list(range(comparison_max + 1)):
            if allowed != list(range(0, comparison_max + 1, 2)):
                raise ValueError(f"independent sparse set changed: {frontier_id}")
            _independent_sparse_mask(
                rom, window_start, comparison_offset, index_register
            )

        literal_offset = ((terminal - 2) & ~3) + (literal_load & 255) * 4
        if not 0 <= literal_offset <= len(rom) - 4:
            raise ValueError(f"independent literal leaves ROM: {frontier_id}")
        base_pointer = int.from_bytes(
            rom[literal_offset : literal_offset + 4], "little"
        )
        table_start = base_pointer - ROM_BASE
        table_stop = table_start + (comparison_max + 1) * 4
        if table_start < 0 or table_start % 4 or table_stop > len(rom):
            raise ValueError(f"independent table leaves ROM: {frontier_id}")

        target_records = []
        local_raw_targets = bytearray()
        for slot in allowed:
            table_entry = table_start + slot * 4
            raw_pointer = rom[table_entry : table_entry + 4]
            pointer = int.from_bytes(raw_pointer, "little")
            target_offset = pointer - ROM_BASE
            if (
                not ROM_BASE <= pointer < ROM_BASE + len(rom)
                or pointer & 1
                or target_offset % 2
            ):
                raise ValueError(
                    f"independent target outside fixed ROM: {frontier_id} slot {slot}"
                )
            target_records.append(
                {
                    "slot_index": slot,
                    "entry_offset": table_entry,
                    "raw_pointer": pointer,
                    "mode": "thumb",
                    "file_offset": target_offset,
                    "gba_address": f"0x{pointer:08X}",
                }
            )
            source_record = {
                "source_kind": "resolved_thumb_indexed_dispatch",
                "source_frontier_id": frontier_id,
                "terminal_offset": terminal,
                "slot_index": slot,
                "entry_offset": table_entry,
            }
            target_sources[target_offset].append(source_record)
            local_raw_targets.extend(raw_pointer)
            global_raw_targets.extend(raw_pointer)

        proof_stop = terminal + 2
        dispatch_records.append(
            {
                "source_frontier_id": frontier_id,
                "source_block_id": source["block_id"],
                "terminal_offset": terminal,
                "proof_range": [window_start, proof_stop],
                "proof_sha256": _digest(rom[window_start:proof_stop]),
                "index_register": f"r{index_register}",
                "comparison_offset": comparison_offset,
                "comparison_max": comparison_max,
                "bound_branch": {
                    "file_offset": bound_offset,
                    "condition": "bhi" if condition == 8 else "bls",
                    "target_offset": bound_target,
                    "direction": direction,
                },
                "literal_offset": literal_offset,
                "table_pointer": f"0x{base_pointer:08X}",
                "table_range": [table_start, table_stop],
                "table_sha256": _digest(rom[table_start:table_stop]),
                "allowed_indices": allowed,
                "ordered_target_vector_sha256": _digest(bytes(local_raw_targets)),
                "targets": target_records,
            }
        )

    vector_digest = _digest(bytes(global_raw_targets))
    if vector_digest != ORDERED_TARGET_VECTOR_SHA256:
        raise ValueError("independent ordered target vector changed")
    unique_offsets = sorted(target_sources)
    preexisting = [
        offset for offset in unique_offsets if ("thumb", offset) in fixed_roots
    ]
    additions = [
        offset for offset in unique_offsets if ("thumb", offset) not in fixed_roots
    ]
    if len(preexisting) != 183 or len(additions) != 107:
        raise ValueError("independent extension-root denominator changed")
    nonfixed_root_target_seeds = [
        {
            "mode": "thumb",
            "file_offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}",
            "entry_size": 4,
            "entry_sha256": _digest(rom[offset : offset + 4]),
            "sources": target_sources[offset],
        }
        for offset in additions
    ]
    return {
        "baseline_graph_denominator_sha256": V2_GRAPH_DENOMINATOR_SHA256,
        "baseline_indirect_frontier_count": len(indirect),
        "resolved_frontier_count": len(dispatch_records),
        "unresolved_baseline_indirect_frontier_count": len(indirect)
        - len(dispatch_records),
        "ordered_edge_count": sum(
            len(record["targets"]) for record in dispatch_records
        ),
        "unique_target_count": len(unique_offsets),
        "existing_fixed_root_target_count": len(preexisting),
        "not_fixed_root_target_count": len(nonfixed_root_target_seeds),
        "ordered_target_vector_sha256": vector_digest,
        "dispatches": dispatch_records,
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
        raise ValueError("independent frozen v2 manifest changed")
    if len(payload_raw) != V2_PAYLOAD_SIZE or _sha(payload_raw) != V2_PAYLOAD_SHA256:
        raise ValueError("independent frozen v2 payload changed")
    if _sha(verifier_path.read_bytes()) != V2_VERIFIER_SHA256:
        raise ValueError("independent frozen v2 verifier changed")
    report = verify_rom_cfg_inventory(root, root / V2_ARTIFACT)
    expected = {
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
    if any(report.get(key) != value for key, value in expected.items()):
        raise ValueError(f"independent frozen v2 verification failed: {report}")
    payload = json.loads(payload_raw)
    manifest = json.loads(manifest_raw)
    if (
        payload.get("schema") != V2_SCHEMA
        or payload.get("rom")
        != {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        or payload.get("graph_denominator_sha256")
        != V2_GRAPH_DENOMINATOR_SHA256
        or manifest.get("artifact_schema") != V2_SCHEMA
    ):
        raise ValueError("independent frozen v2 contract changed")
    return payload, manifest


def _target_seeds_independently(
    rom: bytes, resolution: dict[str, Any]
) -> list[dict[str, Any]]:
    provenance: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for dispatch in resolution["dispatches"]:
        for target in dispatch["targets"]:
            provenance[target["file_offset"]].append(
                {
                    "source_kind": "resolved_thumb_indexed_dispatch",
                    "source_frontier_id": dispatch["source_frontier_id"],
                    "terminal_offset": dispatch["terminal_offset"],
                    "slot_index": target["slot_index"],
                    "entry_offset": target["entry_offset"],
                }
            )
    seeds = [
        {
            "mode": "thumb",
            "file_offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}",
            "entry_size": 4,
            "entry_sha256": _digest(rom[offset : offset + 4]),
            "sources": provenance[offset],
        }
        for offset in sorted(provenance)
    ]
    if len(seeds) != 290:
        raise ValueError("independent dispatch target denominator changed")
    return seeds


def _entry_order(item: tuple[str, int]) -> tuple[int, int, str]:
    return item[1], 0 if item[0] == "arm" else 1, item[0]


def _rebuild_extension_entries(
    rom: bytes,
    seeds: list[dict[str, Any]],
    baseline_entries: dict[tuple[str, int], dict[str, Any]],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    list[tuple[tuple[str, int], str, tuple[str, int]]],
]:
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for seed in seeds:
        item = (seed["mode"], seed["file_offset"])
        if item in baseline_entries:
            raise ValueError("independent extension seed duplicates a v2 entry")
        if item not in scheduled:
            heapq.heappush(pending, _entry_order(item))
            scheduled.add(item)
    entries: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    base_crosses: list[tuple[tuple[str, int], str, tuple[str, int]]] = []
    scheduled_limit = len(scheduled) + 2 * MAX_INSTRUCTION_COUNT
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in entries or item in rejected:
            continue
        if item in baseline_entries:
            raise ValueError("independent worklist crossed into duplicated v2 code")
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        if len(entries) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("independent extension instruction budget exhausted")
        entries[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in baseline_entries:
                base_crosses.append((item, edge["kind"], target))
                continue
            if target not in scheduled:
                if len(scheduled) >= scheduled_limit:
                    raise ValueError("independent extension schedule budget exhausted")
                heapq.heappush(pending, _entry_order(target))
                scheduled.add(target)
    return entries, rejected, base_crosses


def _base_block_reference(
    blocks: list[dict[str, Any]], mode: str, offset: int
) -> dict[str, Any]:
    matches = [
        block
        for block in blocks
        if block.get("mode") == mode
        and block.get("range", [-1, -1])[0] <= offset < block["range"][1]
    ]
    if len(matches) != 1:
        raise ValueError(f"independent v2 block reference changed at 0x{offset:06X}")
    return {
        "block_id": matches[0]["id"],
        "instruction_offset": offset,
        "mode": mode,
    }


def _expected_extension_edges_and_frontiers(
    rom: bytes,
    blocks: list[dict[str, Any]],
    decoded_last: list[dict[str, Any]],
    block_entries: dict[tuple[str, int], dict[str, Any]],
    instruction_entries: dict[tuple[str, int], dict[str, Any]],
    baseline_entries: dict[tuple[str, int], dict[str, Any]],
    baseline_blocks: list[dict[str, Any]],
    roots: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    frontier_records = []
    cross_records = []
    for block, decoded in zip(blocks, decoded_last, strict=True):
        expected_edges = []
        source_key = (decoded["mode"], decoded["file_offset"])
        for edge in decoded["successors"]:
            target_key = (edge["mode"], edge["file_offset"])
            target_block = block_entries.get(target_key)
            if target_block is not None:
                expected_edges.append({**edge, "block_id": target_block["id"]})
                continue
            if target_key in baseline_entries:
                cross_records.append(
                    {
                        "source": {
                            "block_id": block["id"],
                            "instruction_offset": source_key[1],
                            "edge_kind": edge["kind"],
                        },
                        "target": _base_block_reference(
                            baseline_blocks, target_key[0], target_key[1]
                        ),
                    }
                )
                continue
            if target_key in instruction_entries:
                raise ValueError(
                    f"extension successor is not a block start at 0x{target_key[1]:06X}"
                )
            rejected = _decode(rom, target_key[1], target_key[0])
            if rejected["accepted"]:
                raise ValueError(
                    f"extension omits decodable successor at 0x{target_key[1]:06X}"
                )
            frontier_records.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": source_key[1],
                        "edge_kind": edge["kind"],
                    },
                    "reason": rejected["frontier_reason"],
                    "target": {
                        "mode": target_key[0],
                        "file_offset": target_key[1],
                    },
                }
            )
        if block.get("successors") != expected_edges:
            raise ValueError(f"extension block successors changed: {block['id']}")
        for frontier in decoded["frontiers"]:
            frontier_records.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": source_key[1],
                    },
                    **frontier,
                }
            )
    for root in roots:
        key = (root["mode"], root["file_offset"])
        if key in block_entries:
            continue
        rejected = _decode(rom, key[1], key[0])
        if rejected["accepted"]:
            raise ValueError(f"extension root is not a block start: {root['root_id']}")
        frontier_records.append(
            {
                "source": {"kind": "root", "root_id": root["root_id"]},
                "reason": rejected["frontier_reason"],
                "target": {"mode": key[0], "file_offset": key[1]},
            }
        )
    sort_key = lambda record: json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    frontier_records.sort(key=sort_key)
    cross_records.sort(key=sort_key)
    return (
        [
            {"id": f"frontier-{index:06d}", **record}
            for index, record in enumerate(frontier_records)
        ],
        cross_records,
    )


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


def _extension_summary(
    blocks: list[dict[str, Any]], frontiers: list[dict[str, Any]]
) -> dict[str, Any]:
    reasons: dict[str, int] = {}
    for frontier in frontiers:
        reasons[frontier["reason"]] = reasons.get(frontier["reason"], 0) + 1
    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": sum(
            block["instruction_count"] for block in blocks
        ),
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(sorted(reasons.items())),
        "reachable_instruction_bytes": _union_bytes(
            [tuple(block["range"]) for block in blocks]
        ),
    }


def _assert_no_v2_byte_overlap(
    baseline_entries: dict[tuple[str, int], dict[str, Any]],
    extension_entries: dict[tuple[str, int], dict[str, Any]],
) -> None:
    occupied = {
        (mode, position)
        for (mode, offset), decoded in baseline_entries.items()
        for position in range(offset, offset + decoded["size"])
    }
    overlap = [
        (mode, position)
        for (mode, offset), decoded in extension_entries.items()
        for position in range(offset, offset + decoded["size"])
        if (mode, position) in occupied
    ]
    if overlap:
        raise ValueError(f"independent extension overlaps v2 bytes: {overlap[:8]}")


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


def verify_rom_cfg_inventory_v3(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    rebuilt_count = 0
    summary: dict[str, Any] = {}
    resolved_count = 0
    new_seed_count = 0
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        resolved_artifact = artifact.resolve(strict=True)
        if resolved_artifact != artifact or not artifact.is_dir():
            raise ValueError("CFG v3 artifact uses a symlink or is not a directory")
        members = list(artifact.iterdir())
        if (
            {member.name for member in members} != {"manifest.json", PAYLOAD_NAME}
            or any(member.is_symlink() or not member.is_file() for member in members)
        ):
            raise ValueError("CFG v3 artifact file set changed")

        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != 6_291_456 or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        baseline, baseline_manifest = _v2_artifact_contract(root, rom)
        seed_payload, _ = _seed_contract(root, rom)
        baseline_entries = _rebuild_instruction_entries(
            rom, seed_payload["seeds"]
        )
        if len(baseline_entries) != 40_872:
            raise ValueError("independent v2 entry closure changed")
        resolution = _resolve_thumb_indexed_dispatches_independently(
            rom, baseline
        )
        static_dispatches = {
            key: value
            for key, value in resolution.items()
            if key != "nonfixed_root_target_seeds"
        }
        target_seeds = _target_seeds_independently(rom, resolution)
        base_target_seeds = [
            seed
            for seed in target_seeds
            if (seed["mode"], seed["file_offset"]) in baseline_entries
        ]
        new_target_seeds = [
            seed
            for seed in target_seeds
            if (seed["mode"], seed["file_offset"]) not in baseline_entries
        ]
        if len(base_target_seeds) != 189 or len(new_target_seeds) != 101:
            raise ValueError("independent base/new target split changed")
        extension_entries, _, _ = _rebuild_extension_entries(
            rom, new_target_seeds, baseline_entries
        )
        rebuilt_count = len(extension_entries)
        _assert_no_v2_byte_overlap(baseline_entries, extension_entries)

        payload_path = artifact / PAYLOAD_NAME
        payload_raw = payload_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        expected_base_cfg = _base_cfg_record(baseline, baseline_manifest)
        expected_decoder = _decoder_identity(root)
        expected_limits = {
            "max_instruction_count": MAX_INSTRUCTION_COUNT,
            "max_basic_block_instruction_count": MAX_BLOCK_INSTRUCTION_COUNT,
            "decode_window_bytes": 4,
            "resolver_generation_count": 1,
        }
        if set(payload) != {
            "schema",
            "rom",
            "base_cfg",
            "decoder",
            "limits",
            "static_dispatches",
            "extension_policy",
            "extension",
            "combined_summary",
            "graph_denominator_sha256",
            "scope",
            "limitations",
        }:
            raise ValueError("CFG v3 top-level field set changed")
        if (
            payload.get("schema") != SCHEMA
            or payload.get("rom")
            != {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
            or payload.get("base_cfg") != expected_base_cfg
            or payload.get("decoder") != expected_decoder
            or payload.get("limits") != expected_limits
            or payload.get("static_dispatches") != static_dispatches
            or payload.get("scope") != SCOPE
            or payload.get("limitations") != LIMITATIONS
        ):
            raise ValueError("CFG v3 top-level contract changed")
        resolved_count = static_dispatches["resolved_frontier_count"]

        expected_policy = {
            "dispatch_target_count": 290,
            "base_entry_reference_count": 189,
            "new_entry_seed_count": 101,
            "recursive_resolution_performed": False,
            "base_bytes_duplicated": False,
        }
        if payload.get("extension_policy") != expected_policy:
            raise ValueError("CFG v3 extension policy changed")
        extension = payload.get("extension")
        if not isinstance(extension, dict):
            raise ValueError("CFG v3 extension is missing")
        new_seed_count = len(new_target_seeds)
        if (
            extension.get("target_seed_count") != 290
            or extension.get("target_seed_denominator_sha256")
            != _canonical_sha(target_seeds)
            or extension.get("new_entry_seed_count") != 101
            or extension.get("new_entry_seeds") != new_target_seeds
            or extension.get("base_entry_reference_count") != 189
        ):
            raise ValueError("CFG v3 target seed contract changed")

        baseline_blocks = baseline["blocks"]
        expected_base_references = [
            {
                "seed": seed,
                "base_entry": _base_block_reference(
                    baseline_blocks, seed["mode"], seed["file_offset"]
                ),
            }
            for seed in base_target_seeds
        ]
        if extension.get("base_entry_references") != expected_base_references:
            raise ValueError("CFG v3 base entry references changed")

        blocks = extension.get("blocks")
        decoded_last, block_entries, by_id, artifact_entries = _verify_blocks(
            rom, blocks
        )
        if set(artifact_entries) != set(extension_entries):
            missing = sorted(
                set(extension_entries) - set(artifact_entries), key=_entry_order
            )[:8]
            unexpected = sorted(
                set(artifact_entries) - set(extension_entries), key=_entry_order
            )[:8]
            raise ValueError(
                "CFG v3 instruction closure differs from independent worklist: "
                f"missing={missing}, unexpected={unexpected}"
            )
        roots = extension.get("roots")
        if not isinstance(roots, list) or len(roots) != 101:
            raise ValueError("CFG v3 root denominator changed")
        expected_frontiers, expected_cross_edges = (
            _expected_extension_edges_and_frontiers(
                rom,
                blocks,
                decoded_last,
                block_entries,
                artifact_entries,
                baseline_entries,
                baseline_blocks,
                roots,
            )
        )
        if extension.get("frontiers") != expected_frontiers:
            raise ValueError("CFG v3 extension frontiers changed")
        if extension.get("base_cross_edges") != expected_cross_edges:
            raise ValueError("CFG v3 base cross edges changed")
        expected_roots = _expected_roots(
            new_target_seeds, block_entries, by_id, expected_frontiers
        )
        if roots != expected_roots:
            raise ValueError("CFG v3 per-root summaries changed")
        expected_extension_summary = _extension_summary(
            blocks, expected_frontiers
        )
        pinned_extension_summary = {
            "decoded_basic_block_count": 891,
            "decoded_instruction_count": 4_698,
            "frontier_count": 16,
            "frontier_reasons": {
                "indirect_pc_target": 15,
                "unsupported_armv4t_instruction": 1,
            },
            "reachable_instruction_bytes": 9_902,
        }
        if expected_extension_summary != pinned_extension_summary:
            raise ValueError(
                f"independent CFG v3 denominator changed: {expected_extension_summary}"
            )
        if extension.get("summary") != expected_extension_summary:
            raise ValueError("CFG v3 extension summary changed")
        expected_extension = {
            "target_seed_count": 290,
            "target_seed_denominator_sha256": _canonical_sha(target_seeds),
            "base_entry_reference_count": 189,
            "base_entry_references": expected_base_references,
            "new_entry_seed_count": 101,
            "new_entry_seeds": new_target_seeds,
            "roots": expected_roots,
            "blocks": blocks,
            "frontiers": expected_frontiers,
            "base_cross_edges": expected_cross_edges,
            "summary": expected_extension_summary,
        }
        if extension != expected_extension:
            raise ValueError("CFG v3 extension contains unexpected fields or values")

        base_summary = baseline["summary"]
        expected_combined = {
            "decoded_basic_block_count": base_summary[
                "decoded_basic_block_count"
            ]
            + expected_extension_summary["decoded_basic_block_count"],
            "decoded_instruction_count": base_summary["decoded_instruction_count"]
            + expected_extension_summary["decoded_instruction_count"],
            "frontier_count": base_summary["frontier_count"]
            - static_dispatches["resolved_frontier_count"]
            + expected_extension_summary["frontier_count"],
            "frontier_reasons": {
                "bios_swi_external": 7,
                "indirect_pc_target": static_dispatches[
                    "unresolved_baseline_indirect_frontier_count"
                ]
                + expected_extension_summary["frontier_reasons"][
                    "indirect_pc_target"
                ],
                "unsupported_armv4t_instruction": 2
                + expected_extension_summary["frontier_reasons"][
                    "unsupported_armv4t_instruction"
                ],
            },
            "reachable_instruction_bytes": base_summary[
                "reachable_instruction_bytes"
            ]
            + expected_extension_summary["reachable_instruction_bytes"],
        }
        if payload.get("combined_summary") != expected_combined:
            raise ValueError("CFG v3 combined summary changed")
        denominator = _canonical_sha(
            {
                "base_cfg": expected_base_cfg,
                "static_dispatches": static_dispatches,
                "extension_policy": expected_policy,
                "extension": expected_extension,
                "combined_summary": expected_combined,
            }
        )
        if payload.get("graph_denominator_sha256") != denominator:
            raise ValueError("CFG v3 graph denominator changed")

        expected_manifest = {
            "artifact_schema": SCHEMA,
            "rom": payload["rom"],
            "base_cfg": expected_base_cfg,
            "decoder": expected_decoder,
            "limits": expected_limits,
            "static_dispatch_summary": {
                key: static_dispatches[key]
                for key in (
                    "baseline_indirect_frontier_count",
                    "resolved_frontier_count",
                    "unresolved_baseline_indirect_frontier_count",
                    "ordered_edge_count",
                    "unique_target_count",
                    "ordered_target_vector_sha256",
                )
            },
            "extension_policy": expected_policy,
            "extension_summary": expected_extension_summary,
            "combined_summary": expected_combined,
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
            raise ValueError("CFG v3 promotion manifest changed")
        summary = expected_extension_summary
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "control_flow_oracle": "armv4t-raw-encoding",
        "resolved_frontier_count": resolved_count,
        "new_entry_seed_count": new_seed_count,
        "independently_rebuilt_instruction_count": rebuilt_count,
        "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0),
        "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0),
        "frontier_count": summary.get("frontier_count", 0),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-cfg-inventory-v3"),
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_rom_cfg_inventory_v3(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
