#!/usr/bin/env python3
"""Independently verify the frozen raw-ROM CFG proven-roots v13 packet."""

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


def _require_isolated_cli_runtime() -> None:
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("CFG v13 CLI requires Python -I -S isolation")
    if "capstone" in sys.modules:
        raise RuntimeError("CFG v13 CLI rejects preloaded Capstone modules")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("CFG v13 CLI rejects LIBCAPSTONE_PATH overrides")


_require_isolated_cli_runtime()
for _root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from tools.verify_rom_cfg_inventory import (  # noqa: E402
    _canonical_sha,
    _decode,
    _safe_file,
    _sha,
    _union_bytes,
)


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-proven-roots-v13"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v13"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v13.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path("build/experiments/active/cfg-proven-roots-v13-red-20260829")

SOURCE_RANGE = (398012, 398564)
SOURCE_SLICE_SHA256 = "90568d99bb0ddfba74ce946781049494e117bd2273bd3b69843f7df420506817"
SOURCE_ROOT = 398012
SOURCE_ENTRY_RAW = "30b52348"
SOURCE_ENTRY_SHA256 = "99904dcab479f7972fa6f37a6811077635d49a4b8f6743c737fff7126fbd8ecb"
SOURCE_PRODUCER = 398544
SOURCE_STOP = 398564
SOURCE_REACHABLE_RANGE_SHA256 = "4bcf92e722093ef3fce0130a28d7708afc5572859e9cdfb671d47a17d4559624"
SOURCE_PACKED_SHA256 = "45b2ec5ee53d3583d2e641ae5d1190045a541af0877462e2f509304f592fa158"
SOURCE_SEMANTIC_SHA256 = "bede899464bca87e2fde14ff8492eadf4735538963f3c3b8e5895552aec5e576"
SOURCE_BLOCK_SHA256 = "fb3c471b6695529759b6d18103ee733a1d0b0a9a97bd9a90f62449fbcb07b4f2"
SOURCE_INTERNAL_SHA256 = "4135e4f261905b1532bf59e598ac65253bf2461e560d03d2930cf4a3ff30d1f3"
SOURCE_EXTERNAL_SHA256 = "f41f0b5d1826f3c8d18a70e2c0959f31052b0a76a7d07b9ba38ffa0de8a3d48d"
SOURCE_OPAQUE_BOUNDARY_SHA256 = "2e2cb02cca25a50a6f0dff30daaae54f9d15f4ffbd40875a0f14f6503d73d734"

TARGET_ROOT = 414200
TARGET_ENVELOPE = (414200, 414596)
TARGET_ENTRY_RAW = "f0b54746"
TARGET_ENTRY_SHA256 = "3e7ec2098933d96de8dc658d119ed3848ccdd7942f96f2a0d015f1e68e3c759b"
TARGET_ENVELOPE_SHA256 = "838fd74b07984a3a692f3fb66e72f1b4d6d7c7c5ad791934c3827ca7e968b10e"
TARGET_CODE_RANGES = ((414200, 414268), (414284, 414430), (414472, 414570))
TARGET_LITERAL_RANGES = ((414268, 414284), (414432, 414472), (414572, 414596))
TARGET_HOLE_RANGES = ((414430, 414432), (414570, 414572))
TARGET_FRONTIERS = ((414568, "indirect_pc_target"),)
TARGET_BLOCK_SHA256 = "fae253e64395d30da0ed5988fdaa2f553dd4ac0216de710d543b03e8b57b200e"
TARGET_CODE_RANGE_SHA256 = "1eb89efbb94cb9f1a7ecbcfad992dfeb3ff49c84f918d52b715a87f25fcd89f4"
TARGET_LITERAL_RANGE_SHA256 = "f34a55f4703f8b17f969d13aa02fd9aa1b1d1264a52ca8267dbd688ee6658f88"
TARGET_PROMOTION_RANGE_SHA256 = "09f8682f0e4bab0db4108820c4034abf45e345e05f9e7bd9c4111cc2054114c0"
TARGET_INSTRUCTION_INTERNAL_SHA256 = "27ae4a890679ccafeb65a38f512757c35faf18fe4dd8540581c073468b4eb1d4"
TARGET_BLOCK_INTERNAL_SHA256 = "d71a01f074ed0b403748e311425936768ec5df8ae4971b614e66766c7c685681"
TARGET_EXTERNAL_SHA256 = "6d9235d9594d1a1124aaef710d1d29f4b2c8edc4f0f56699bc6c0d10561983aa"
TARGET_FRONTIER_SHA256 = "76d3c99e0143cccffef136d057794fe0863bb4e775b880b7d632515547b992b8"
TARGET_SEMANTIC_SHA256 = "4fe44f3fb076b347b7d641a02a01cd9978880414253ad0664f6c7a870bab449f"
TARGET_LITERAL_BINDING_SHA256 = "4eac0d84e979e591c789d522c21df22d06a8274817d0ca9943c45ea6a2f7ee84"
TARGET_PACKED_CODE_SHA256 = "c0fd79364221d43e831d33b5266bad1bc2fefe9249c10313ce06d812bd712bcb"
TARGET_PACKED_LITERAL_SHA256 = "3ad57b1bb869ecd47546e6f220201414fc68c0727742cee023e8feb640e59546"
TARGET_PACKED_PROMOTION_SHA256 = "d7449f4feb51fa169d011c0692d2009090633aa8cf7968064bd36063be491e40"

COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "96fba5e10bbef80eb0326e7dd85d07babdcffb63674a0fecd046c8b9edc427eb"
COVERAGE_EXPECTED = {
    "path": COVERAGE_PATH.as_posix(),
    "sha256": COVERAGE_SHA256,
    "classified_bytes": 6126383,
    "unknown_bytes": 165073,
    "claim_count": 14552,
    "segment_count": 16665,
    "promotion_bytes": 392,
    "known_overlap_bytes": 0,
}

UPSTREAM = {
    "artifact_schema": "battle-effect-sprite-animations-v1",
    "manifest_path": "artifacts/battle-effect-sprite-animations-v1/manifest.json",
    "manifest_sha256": "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848",
    "verifier_path": "tools/verify_battle_effect_sprite_animations.py",
    "verifier_sha256": "ba22259f41e53398a0f271f806c831b5eaf0052f17784c831d2591c0220f0c6b",
    "verification_schema": "battle-effect-sprite-animations-verification-v1",
    "consumer_slice_name": "dynamic_obj_vram_dispatch_order",
    "consumer_slice_range": list(SOURCE_RANGE),
    "consumer_slice_sha256": SOURCE_SLICE_SHA256,
    "coverage_claim_id": "consumer-code-battle_effect_sprite_animations-0612bc",
    "coverage_primary_class": "consumer_code_slice",
    "opaque_stop": {"offset": SOURCE_STOP, "coverage_claim_id": "verified-reuse-staged-oam-submit-code-0614e4"},
}

NONCLAIMS = [
    "natural_execution_or_runtime_reachability",
    "global_code_caller_producer_denominators",
    "global_indirect_computed_or_ram_target_denominators",
    "bx_r0_indirect_target_or_runtime_dispatch_denominator",
    "callee_code_abi_or_semantics_at_0x0624c0_0x062510_or_0x09c0dc",
    "literal_business_meaning_compiler_authorship_or_adjacent_bytes",
    "padding_nop_reserved_free_or_allocatable_status_of_holes",
    "editing_writeback_relocation_or_gameplay_graphics_audio_behavior",
]
SCOPE = {
    "source_worklist_bounded_to_accepted_slice": True,
    "source_producer_edge_rebuilt_from_raw_rom": True,
    "target_worklist_bounded_to_frozen_envelope": True,
    "target_producer_denominator_complete_for_fixed_target": True,
    "literal_bindings_rebuilt_from_raw_rom": True,
    "single_indirect_pc_frontier_is_explicit_and_unresolved": True,
    "two_holes_excluded_from_promotion": True,
    "baseline_entries_treated_as_opaque": True,
    "promotion_window_complete": True,
    "promotion_window_complete_except_explicit_holes": True,
    "current_known_overlap_bytes": 0,
    "runtime_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_producer_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "structured_return_proven": False,
    "callee_semantics_proven": False,
    "literal_business_meaning_proven": False,
    "hole_semantics_proven": False,
    "editing_relocation_safe": False,
    "nonclaims": NONCLAIMS,
}

RUNTIME_DEPENDENCY_PATHS = (
    Path("tools/export_rom_cfg_inventory.py"),
    Path("tools/verify_rom_cfg_inventory.py"),
    Path("tools/verify_battle_effect_sprite_animations.py"),
) + tuple(
    Path("tools/_vendor/capstone") / path.name
    for path in sorted((PROJECT_ROOT / "tools/_vendor/capstone").glob("*.py"))
) + (Path("tools/_vendor/capstone/lib/libcapstone.dylib"),)

EXPECTED_REPORT = {
    "schema": VERIFY_SCHEMA,
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "rom_sha256": ROM_SHA256,
    "source_root_count": 1,
    "source_decoded_instruction_count": 237,
    "source_decoded_basic_block_count": 40,
    "source_reachable_instruction_bytes": 508,
    "source_frontier_count": 0,
    "source_external_call_edge_count": 17,
    "source_target_producer_edge_count": 1,
    "source_opaque_boundary_edge_count": 1,
    "target_decoded_instruction_count": 153,
    "target_decoded_basic_block_count": 25,
    "target_reachable_instruction_bytes": 312,
    "target_frontier_count": 1,
    "target_frontiers": [list(row) for row in TARGET_FRONTIERS],
    "target_instruction_internal_edge_count": 164,
    "target_block_internal_edge_count": 36,
    "target_external_call_edge_count": 3,
    "target_literal_reference_count": 21,
    "target_unique_literal_word_count": 20,
    "target_literal_bytes": 80,
    "promotion_range_count": 6,
    "promotion_bytes": 392,
    "hole_bytes": 4,
    "unclassified_hole_bytes": 4,
    "holes": [
        {
            "range": list(row),
            "raw_hex": "0000",
            "sha256": "96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7",
        }
        for row in TARGET_HOLE_RANGES
    ],
    "nonclaims": {name: False for name in NONCLAIMS},
}


def _entry(rom: bytes, offset: int, raw_hex: str, digest: str) -> dict[str, Any]:
    raw = rom[offset:offset + 4]
    if raw.hex() != raw_hex or _sha(raw) != digest:
        raise ValueError(f"entry bytes changed at 0x{offset:06X}")
    return {"mode": "thumb", "file_offset": offset, "entry_raw_hex": raw_hex, "entry_sha256": digest}


def _build_blocks(rom: bytes, nodes: dict[tuple[str, int], dict[str, Any]], roots: set[tuple[str, int]]) -> tuple[list[dict[str, Any]], dict[tuple[str, int], str]]:
    resolved: dict[tuple[str, int], list[tuple[str, int]]] = {}
    incoming: dict[tuple[str, int], list[tuple[str, int]]] = defaultdict(list)
    for item, node in nodes.items():
        targets = []
        for edge in node["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in nodes:
                targets.append(target)
                incoming[target].append(item)
        resolved[item] = targets
    starts = {item for item in roots if item in nodes}
    for item, node in nodes.items():
        preds = incoming[item]
        if len(preds) != 1:
            starts.add(item)
            continue
        predecessor = preds[0]
        prior = nodes[predecessor]
        if len(resolved[predecessor]) != 1 or predecessor[0] != item[0] or predecessor[1] + prior["size"] != item[1] or prior["flow_kind"] != "linear":
            starts.add(item)
    def key(item: tuple[str, int]) -> tuple[int, int, str]:
        return (item[1], 0 if item[0] == "arm" else 1, item[0])
    pending = [key(item) for item in starts]
    heapq.heapify(pending)
    assigned: dict[tuple[str, int], str] = {}
    raw_blocks: list[tuple[list[tuple[str, int]], dict[str, Any]]] = []
    while len(assigned) < len(nodes):
        if not pending:
            heapq.heappush(pending, key(min((item for item in nodes if item not in assigned), key=key)))
        offset, _, mode = heapq.heappop(pending)
        first = (mode, offset)
        if first in assigned:
            continue
        block_id = f"block-{mode}-{offset:06x}"
        members = []
        current = first
        while current not in assigned:
            members.append(current)
            assigned[current] = block_id
            node = nodes[current]
            targets = resolved[current]
            if len(targets) != 1 or node["flow_kind"] != "linear" or targets[0] in starts or targets[0] in assigned or targets[0][0] != current[0] or targets[0][1] != current[1] + node["size"]:
                break
            current = targets[0]
        last = members[-1]
        last_node = nodes[last]
        raw_blocks.append((members, {"id": block_id, "mode": mode, "range": [members[0][1], last[1] + last_node["size"]], "instruction_count": len(members), "bytes_sha256": _sha(rom[members[0][1]:last[1] + last_node["size"]]), "terminator": {field: last_node[field] for field in ("file_offset", "size", "mnemonic", "op_str", "flow_kind", "conditional")}, "successors": []}))
    blocks = []
    for members, block in raw_blocks:
        for edge in nodes[members[-1]]["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in nodes:
                block["successors"].append({**edge, "block_id": assigned[target]})
        blocks.append(block)
    blocks.sort(key=lambda block: (block["range"][0], 0 if block["mode"] == "arm" else 1, block["mode"]))
    return blocks, assigned


def _bounded_worklist(rom: bytes, root: int, bound: tuple[int, int], stop: int | None) -> tuple[dict[tuple[str, int], dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pending = [(root, 1, "thumb")]
    heapq.heapify(pending)
    scheduled = {("thumb", root)}
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    boundary: list[dict[str, Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes:
            continue
        if mode != "thumb" or not (bound[0] <= offset < bound[1]):
            raise ValueError("bounded CFG worklist escaped frozen range")
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            raise ValueError(f"raw CFG decode frontier at 0x{offset:06X}")
        if stop is not None and offset == stop:
            decoded = {**decoded, "flow_kind": "return", "successors": [], "frontiers": []}
        if offset + decoded["size"] > bound[1]:
            raise ValueError("bounded CFG instruction straddles frozen range")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if bound[0] <= target[1] < bound[1] and target[0] == "thumb":
                if target not in scheduled:
                    scheduled.add(target)
                    heapq.heappush(pending, (target[1], 1, target[0]))
            elif edge["kind"] == "call_target":
                external.append({"source_file_offset": offset, "target_file_offset": target[1], "edge_kind": edge["kind"], "reason": "target_producer" if target[1] == TARGET_ROOT else "opaque_external"})
            elif target[1] == bound[1] and edge["kind"] == "fallthrough":
                boundary.append({"source_file_offset": offset, "target_file_offset": target[1], "edge_kind": "opaque_boundary", "reason": "accepted_owner_beginning"})
            else:
                raise ValueError("bounded CFG non-call edge escaped frozen range")
    blocks, _ = _build_blocks(rom, nodes, {("thumb", root)})
    return nodes, blocks, external, boundary


def _nodes(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[dict[str, Any]]:
    return [nodes[key] for key in sorted(nodes, key=lambda item: (item[1], 1, item[0]))]


def _merged_ranges(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted((offset, offset + node["size"]) for (_, offset), node in nodes.items()):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def _semantic(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[list[Any]]:
    return [[node["file_offset"], node["size"], node["mnemonic"], node["op_str"]] for node in _nodes(nodes)]


def _frontier_vector(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[list[Any]]:
    return [
        [node["file_offset"], frontier["reason"]]
        for node in _nodes(nodes)
        for frontier in node["frontiers"]
    ]


def _packed(rom: bytes, ranges: list[list[int] | tuple[int, int]]) -> str:
    return _sha(b"".join(rom[a:b] for a, b in sorted(ranges)))


def _producer_target(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    thumb_bl = []
    thumb_b = []
    thumb_bcond = []
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset:offset + 2], "little")
        second = int.from_bytes(rom[offset + 2:offset + 4], "little")
        if _producer_target(offset, first, second) == TARGET_ROOT:
            thumb_bl.append(offset)
        elif first & 0xF800 == 0xE000:
            displacement = (first & 0x7FF) << 1
            if displacement & 0x800:
                displacement -= 0x1000
            if offset + 4 + displacement == TARGET_ROOT:
                thumb_b.append(offset)
        elif first & 0xF000 == 0xD000 and ((first >> 8) & 0xF) <= 0xD:
            displacement = (first & 0xFF) << 1
            if displacement & 0x100:
                displacement -= 0x200
            if offset + 4 + displacement == TARGET_ROOT:
                thumb_bcond.append(offset)
    arm_b_bl = []
    aligned_arm_pointers = []
    for offset in range(0, len(rom) - 3, 4):
        word = int.from_bytes(rom[offset:offset + 4], "little")
        if word == ROM_BASE + TARGET_ROOT:
            aligned_arm_pointers.append(offset)
        if word >> 28 != 0xF and (word >> 25) & 0x7 == 0b101:
            displacement = (word & 0xFFFFFF) << 2
            if displacement & 0x02000000:
                displacement -= 0x04000000
            if offset + 8 + displacement == TARGET_ROOT:
                arm_b_bl.append(offset)
    thumb_pointers = []
    for offset in range(0, len(rom) - 3, 2):
        if int.from_bytes(rom[offset:offset + 4], "little") == ((ROM_BASE + TARGET_ROOT) | 1):
            thumb_pointers.append(offset)
    if thumb_bl != [SOURCE_PRODUCER] or thumb_b or thumb_bcond or arm_b_bl or aligned_arm_pointers or thumb_pointers:
        raise ValueError("target-limited producer denominator changed")
    raw = rom[SOURCE_PRODUCER:SOURCE_PRODUCER + 4]
    if raw.hex() != "03f092fe" or _sha(raw) != "d9bd4f7a9eef6b4224a1d630a698ccec615fc19dd002c390d3c46b047a84ba4b":
        raise ValueError("producer bytes changed")
    record = {"file_offset": SOURCE_PRODUCER, "gba_address": f"0x{ROM_BASE + SOURCE_PRODUCER:08X}", "raw_hex": raw.hex(), "bytes_sha256": _sha(raw), "target_file_offset": TARGET_ROOT, "target_gba_address": f"0x{ROM_BASE + TARGET_ROOT:08X}", "kind": "thumb_bl", "status": "accepted_source_producer"}
    vector = [[SOURCE_PRODUCER, TARGET_ROOT, "thumb_bl"]]
    return {"scan": {"mode": "thumb", "alignment_bytes": 2, "range": [0, ROM_SIZE], "target_file_offsets": [TARGET_ROOT], "matching_producer_count": 1}, "producers": [record], "thumb_bl": [record], "thumb_b": thumb_b, "thumb_bcond": thumb_bcond, "arm_b_bl": arm_b_bl, "aligned_arm_pointers": aligned_arm_pointers, "thumb_pointers": thumb_pointers, "thumb_bl_count": len(thumb_bl), "thumb_b_count": len(thumb_b), "thumb_bcond_count": len(thumb_bcond), "arm_b_bl_count": len(arm_b_bl), "aligned_arm_pointer_count": len(aligned_arm_pointers), "thumb_pointer_count": len(thumb_pointers), "vector": vector, "vector_sha256": _canonical_sha(vector), "producer_raw_hex": record["raw_hex"], "producer_sha256": record["bytes_sha256"]}


def _source_worklist(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256 or _sha(rom[SOURCE_RANGE[0]:SOURCE_RANGE[1]]) != SOURCE_SLICE_SHA256:
        raise ValueError("source identity changed")
    nodes, blocks, external, boundary = _bounded_worklist(rom, SOURCE_ROOT, SOURCE_RANGE, None)
    expected_boundary = [{"source_file_offset": 398560, "target_file_offset": SOURCE_STOP, "edge_kind": "opaque_boundary", "reason": "accepted_owner_beginning"}]
    if len(nodes) != 237 or len(blocks) != 40 or _union_bytes([(n["file_offset"], n["file_offset"] + n["size"]) for n in nodes.values()]) != 508 or boundary != expected_boundary:
        raise ValueError("source CFG denominator changed")
    internal = [[node["file_offset"], edge["file_offset"], edge["kind"]] for node in _nodes(nodes) for edge in node["successors"] if (edge["mode"], edge["file_offset"]) in nodes]
    internal.sort(key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1]))
    external_vector = [[row["source_file_offset"], row["target_file_offset"], row["reason"]] for row in sorted(external, key=lambda row: row["source_file_offset"])]
    if _canonical_sha(_merged_ranges(nodes)) != SOURCE_REACHABLE_RANGE_SHA256 or _packed(rom, [(n["file_offset"], n["file_offset"] + n["size"]) for n in _nodes(nodes)]) != SOURCE_PACKED_SHA256 or _canonical_sha(_semantic(nodes)) != SOURCE_SEMANTIC_SHA256 or _canonical_sha([b["range"] for b in blocks]) != SOURCE_BLOCK_SHA256 or _canonical_sha(internal) != SOURCE_INTERNAL_SHA256 or _canonical_sha(external_vector) != SOURCE_EXTERNAL_SHA256:
        raise ValueError("source CFG vector changed")
    boundary_vector = [[row["source_file_offset"], row["target_file_offset"], "opaque_accepted_owner"] for row in boundary]
    boundary_digest = _canonical_sha(boundary_vector)
    if boundary_digest != SOURCE_OPAQUE_BOUNDARY_SHA256:
        raise ValueError("source opaque boundary vector changed")
    accepted = [row for row in external if row["reason"] == "target_producer"]
    if [row["source_file_offset"] for row in accepted] != [SOURCE_PRODUCER]:
        raise ValueError("source producer edge changed")
    return {"root": _entry(rom, SOURCE_ROOT, SOURCE_ENTRY_RAW, SOURCE_ENTRY_SHA256), "range": list(SOURCE_RANGE), "size": SOURCE_RANGE[1] - SOURCE_RANGE[0], "slice_sha256": SOURCE_SLICE_SHA256, "nodes": _nodes(nodes), "blocks": blocks, "frontiers": [], "internal_edges": internal, "external_edges": external, "opaque_boundary_edges": boundary, "opaque_boundary": boundary[0], "reachable_ranges": _merged_ranges(nodes), "reachable_range_vector_sha256": SOURCE_REACHABLE_RANGE_SHA256, "packed_instruction_bytes_sha256": SOURCE_PACKED_SHA256, "semantic_instruction_vector_sha256": SOURCE_SEMANTIC_SHA256, "block_range_vector_sha256": SOURCE_BLOCK_SHA256, "internal_edge_vector_sha256": SOURCE_INTERNAL_SHA256, "instruction_internal_edge_vector_sha256": SOURCE_INTERNAL_SHA256, "external_call_vector_sha256": SOURCE_EXTERNAL_SHA256, "external_edge_vector_sha256": SOURCE_EXTERNAL_SHA256, "opaque_boundary_vector_sha256": boundary_digest, "accepted_producer_file_offset": SOURCE_PRODUCER, "opaque_stop": {"file_offset": SOURCE_STOP, "coverage_claim_id": UPSTREAM["opaque_stop"]["coverage_claim_id"]}, "summary": {"root_count": 1, "decoded_instruction_count": 237, "decoded_basic_block_count": 40, "reachable_instruction_bytes": 508, "frontier_count": 0, "external_call_edge_count": 17, "target_producer_edge_count": 1, "opaque_boundary_edge_count": 1, "instruction_internal_edge_count": len(internal)}}


def _literal_projection(rom: bytes, nodes: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    bindings: list[list[Any]] = []
    full: list[list[Any]] = []
    for node in _nodes(nodes):
        offset = node["file_offset"]
        decoded = node
        if decoded["mnemonic"] != "ldr" or "[pc," not in decoded["op_str"]:
            continue
        raw = rom[offset:offset + 2]
        halfword = int.from_bytes(raw, "little")
        if halfword & 0xF800 != 0x4800:
            continue
        literal = ((offset + 4) & ~3) + (halfword & 0xFF) * 4
        if not any(start <= literal and literal + 4 <= end for start, end in TARGET_LITERAL_RANGES):
            continue
        full.append([offset, literal, int.from_bytes(rom[literal:literal + 4], "little"), raw.hex(), rom[literal:literal + 4].hex()])
        bindings.append([offset, literal])
    if len(full) != 21 or len({row[1] for row in full}) != 20 or _canonical_sha(bindings) != TARGET_LITERAL_BINDING_SHA256:
        raise ValueError("target literal binding vector changed")
    return {"bindings": full, "binding_vector": bindings, "literal_reference_count": 21, "unique_literal_word_count": 20, "bytes": 80, "ranges": [list(row) for row in TARGET_LITERAL_RANGES], "range_vector_sha256": TARGET_LITERAL_RANGE_SHA256, "binding_vector_sha256": TARGET_LITERAL_BINDING_SHA256, "packed_sha256": TARGET_PACKED_LITERAL_SHA256}


def _target_worklist(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256 or _sha(rom[TARGET_ENVELOPE[0]:TARGET_ENVELOPE[1]]) != TARGET_ENVELOPE_SHA256:
        raise ValueError("target identity changed")
    nodes, blocks, external, boundary = _bounded_worklist(rom, TARGET_ROOT, TARGET_ENVELOPE, None)
    if len(nodes) != 153 or len(blocks) != 25 or boundary:
        raise ValueError("target CFG denominator changed")
    if _merged_ranges(nodes) != [list(row) for row in TARGET_CODE_RANGES]:
        raise ValueError("target merged code ranges changed")
    literals = _literal_projection(rom, nodes)
    block_internal = [[block["terminator"]["file_offset"], edge["file_offset"], edge["kind"]] for block in blocks for edge in block["successors"]]
    block_internal.sort(key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1]))
    instruction_internal = [[node["file_offset"], edge["file_offset"], edge["kind"]] for node in _nodes(nodes) for edge in node["successors"] if (edge["mode"], edge["file_offset"]) in nodes]
    instruction_internal.sort(key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1]))
    external_vector = [[row["source_file_offset"], row["target_file_offset"], row["edge_kind"]] for row in sorted(external, key=lambda row: row["source_file_offset"])]
    frontiers = _frontier_vector(nodes)
    promotion_ranges = sorted([list(row) for row in TARGET_CODE_RANGES + TARGET_LITERAL_RANGES])
    if _canonical_sha([b["range"] for b in blocks]) != TARGET_BLOCK_SHA256 or _canonical_sha(instruction_internal) != TARGET_INSTRUCTION_INTERNAL_SHA256 or _canonical_sha(block_internal) != TARGET_BLOCK_INTERNAL_SHA256 or _canonical_sha(external_vector) != TARGET_EXTERNAL_SHA256 or frontiers != [list(row) for row in TARGET_FRONTIERS] or _canonical_sha(frontiers) != TARGET_FRONTIER_SHA256 or _canonical_sha(_semantic(nodes)) != TARGET_SEMANTIC_SHA256 or _packed(rom, TARGET_CODE_RANGES) != TARGET_PACKED_CODE_SHA256 or _packed(rom, TARGET_LITERAL_RANGES) != TARGET_PACKED_LITERAL_SHA256 or _packed(rom, promotion_ranges) != TARGET_PACKED_PROMOTION_SHA256 or _canonical_sha([list(row) for row in TARGET_CODE_RANGES]) != TARGET_CODE_RANGE_SHA256 or _canonical_sha([list(row) for row in TARGET_LITERAL_RANGES]) != TARGET_LITERAL_RANGE_SHA256 or _canonical_sha(promotion_ranges) != TARGET_PROMOTION_RANGE_SHA256:
        raise ValueError("target CFG vector changed")
    frontier_node = nodes.get(("thumb", 414568))
    if frontier_node is None or frontier_node["mnemonic"] != "bx" or frontier_node["op_str"] != "r0" or frontier_node["flow_kind"] != "indirect_branch" or frontier_node["successors"]:
        raise ValueError("target indirect frontier instruction changed")
    holes = []
    for start, end in TARGET_HOLE_RANGES:
        if rom[start:end] != b"\x00\x00":
            raise ValueError("target hole bytes changed")
        holes.append({"range": [start, end], "raw_hex": "0000", "sha256": _sha(rom[start:end])})
    if external_vector != [[414260, 402624, "call_target"], [414296, 402704, "call_target"], [414532, 639196, "call_target"]]:
        raise ValueError("target opaque calls changed")
    return {"root": _entry(rom, TARGET_ROOT, TARGET_ENTRY_RAW, TARGET_ENTRY_SHA256), "envelope": list(TARGET_ENVELOPE), "envelope_bytes": 396, "envelope_sha256": TARGET_ENVELOPE_SHA256, "nodes": _nodes(nodes), "blocks": blocks, "block_ranges": [b["range"] for b in blocks], "code_ranges": [list(row) for row in TARGET_CODE_RANGES], "literal_ranges": [list(row) for row in TARGET_LITERAL_RANGES], "holes": holes, "frontiers": frontiers, "instruction_internal_edges": instruction_internal, "block_internal_edges": block_internal, "external_edges": external, "opaque_external_calls": [[r["source_file_offset"], r["target_file_offset"], r["edge_kind"]] for r in external], "literal_projection": literals, "block_range_sha256": TARGET_BLOCK_SHA256, "block_range_vector_sha256": TARGET_BLOCK_SHA256, "code_range_vector_sha256": TARGET_CODE_RANGE_SHA256, "literal_range_vector_sha256": TARGET_LITERAL_RANGE_SHA256, "promotion_range_vector_sha256": TARGET_PROMOTION_RANGE_SHA256, "instruction_internal_edge_vector_sha256": TARGET_INSTRUCTION_INTERNAL_SHA256, "block_internal_edge_vector_sha256": TARGET_BLOCK_INTERNAL_SHA256, "external_call_vector_sha256": TARGET_EXTERNAL_SHA256, "external_edge_vector_sha256": TARGET_EXTERNAL_SHA256, "frontier_vector_sha256": TARGET_FRONTIER_SHA256, "semantic_instruction_vector_sha256": TARGET_SEMANTIC_SHA256, "literal_binding_vector_sha256": TARGET_LITERAL_BINDING_SHA256, "packed_code_sha256": TARGET_PACKED_CODE_SHA256, "packed_literals_sha256": TARGET_PACKED_LITERAL_SHA256, "packed_promotion_sha256": TARGET_PACKED_PROMOTION_SHA256, "promotion_ranges": promotion_ranges, "summary": {"decoded_instruction_count": 153, "decoded_basic_block_count": 25, "reachable_instruction_bytes": 312, "frontier_count": 1, "instruction_internal_edge_count": 164, "block_internal_edge_count": 36, "external_call_edge_count": 3, "literal_reference_count": 21, "unique_literal_word_count": 20, "literal_bytes": 80, "promotion_range_count": 6, "promotion_bytes": 392, "hole_bytes": 4}}


def _coverage_baseline(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    data = json.loads(raw)
    summary = data.get("summary", {})
    if any(summary.get(key) != COVERAGE_EXPECTED[key] for key in ("classified_bytes", "unknown_bytes", "claim_count", "segment_count")):
        raise ValueError("coverage baseline summary changed")
    known_bytes = 0
    unknown_bytes = 0
    for start, end in sorted(TARGET_CODE_RANGES + TARGET_LITERAL_RANGES):
        for segment in data.get("segments", []):
            left, right = segment["range"]
            overlap_start = max(start, left)
            overlap_end = min(end, right)
            if overlap_start >= overlap_end:
                continue
            if segment["primary_class"] == "unknown":
                unknown_bytes += overlap_end - overlap_start
            else:
                known_bytes += overlap_end - overlap_start
    if known_bytes != 0 or unknown_bytes != 392:
        raise ValueError("coverage baseline promotion projection changed")
    return dict(COVERAGE_EXPECTED)


def _upstream_contract(root: Path) -> dict[str, Any]:
    manifest_path = _safe_file(root, UPSTREAM["manifest_path"])
    verifier_path = _safe_file(root, UPSTREAM["verifier_path"])
    if _sha(manifest_path.read_bytes()) != UPSTREAM["manifest_sha256"] or _sha(verifier_path.read_bytes()) != UPSTREAM["verifier_sha256"]:
        raise ValueError("accepted upstream identity changed")
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("schema") != UPSTREAM["artifact_schema"]:
        raise ValueError("accepted upstream schema changed")
    rows = [row for row in manifest.get("consumer_code_slices", []) if row.get("name") == UPSTREAM["consumer_slice_name"]]
    if len(rows) != 1:
        raise ValueError("accepted upstream source slice missing")
    row = rows[0]
    if row.get("file_offset") != SOURCE_RANGE[0] or int(row.get("gba_end", "0"), 16) - ROM_BASE != SOURCE_RANGE[1] or row.get("sha256") != SOURCE_SLICE_SHA256:
        raise ValueError("accepted upstream source slice changed")
    return dict(UPSTREAM)


def _implementation(root: Path) -> dict[str, Any]:
    paths = {"exporter": Path("tools/export_rom_cfg_proven_roots_v13.py"), "verifier": Path("tools/verify_rom_cfg_proven_roots_v13.py"), "test_exporter": Path("tests/test_export_rom_cfg_proven_roots_v13.py"), "test_verifier": Path("tests/test_verify_rom_cfg_proven_roots_v13.py")}
    return {"binding": "passed-root-runtime-dependency-and-test-hash-bound", "paths": {key: value.as_posix() for key, value in paths.items()}, "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()), "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()), "test_exporter_sha256": _sha(_safe_file(root, paths["test_exporter"]).read_bytes()), "test_verifier_sha256": _sha(_safe_file(root, paths["test_verifier"]).read_bytes()), "runtime_dependency_sha256": {path.as_posix(): _sha(_safe_file(root, path).read_bytes()) for path in RUNTIME_DEPENDENCY_PATHS}}


def _expected_payload(root: Path, rom: bytes) -> dict[str, Any]:
    promotion_ranges = [list(row) for row in sorted(TARGET_CODE_RANGES + TARGET_LITERAL_RANGES)]
    return {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}, "upstream": _upstream_contract(root), "producer_denominator": _producer_denominator(rom), "source": _source_worklist(rom), "target": _target_worklist(rom), "promotion": {"batch": "cfg-proven-roots-v13", "ranges": promotion_ranges, "promotion_range_count": 6, "promotion_bytes": 392, "promotion_code_bytes": 312, "promotion_literal_bytes": 80, "hole_bytes": 4, "packed_sha256": TARGET_PACKED_PROMOTION_SHA256, "range_vector_sha256": TARGET_PROMOTION_RANGE_SHA256, "unclassified_hole_bytes": 4}, "coverage_baseline": _coverage_baseline(root), "implementation": _implementation(root), "scope": dict(SCOPE)}


def _artifact_file(artifact: Path, name: str) -> Path:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("v13 artifact directory is missing or uses a symlink")
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("v13 artifact file set uses a symlink or is incomplete")
    return path


def _receipt_commands(
    root: Path,
    manifest: dict[str, Any],
    artifact: Path,
) -> tuple[list[str], list[str]]:
    producer = manifest.get("producer")
    verifier = manifest.get("verifier")
    if not isinstance(producer, dict) or not isinstance(verifier, dict):
        raise ValueError("v13 promotion receipt is missing")
    producer_command = producer.get("command")
    verifier_command = verifier.get("command")
    producer_prefix = ["python3", "-I", "-S", "tools/export_rom_cfg_proven_roots_v13.py", "--root", ".", "--output-dir"]
    verifier_prefix = ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v13.py", "--root", ".", "--artifact-dir"]
    if not isinstance(producer_command, list) or producer_command[:-1] != producer_prefix or not isinstance(verifier_command, list) or verifier_command[:-1] != verifier_prefix or producer_command[-1] != verifier_command[-1]:
        raise ValueError("v13 promotion receipt command changed")
    recorded = Path(producer_command[-1])
    if recorded.is_absolute():
        raise ValueError("v13 promotion receipt path must be repository-relative")
    target = (root / recorded).resolve(strict=False)
    allowed = (root / EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    official = (root / "artifacts/rom-cfg-proven-roots-v13").resolve(strict=False)
    if target != official and (target == allowed or allowed not in target.parents):
        raise ValueError("v13 promotion receipt path escaped experiment subtree")
    if target != artifact.resolve(strict=True):
        raise ValueError(
            "v13 promotion receipt path does not match actual artifact directory"
        )
    return producer_command, verifier_command


def _expected_manifest(root: Path, artifact: Path, manifest: dict[str, Any], payload: dict[str, Any], payload_raw: bytes, status: str) -> dict[str, Any]:
    if status not in {"candidate", "accepted"}:
        raise ValueError("v13 promotion status changed")
    producer_command, verifier_command = _receipt_commands(root, manifest, artifact)
    report = EXPECTED_REPORT if status == "accepted" else None
    return {"schema": PROMOTION_SCHEMA, "artifact_schema": SCHEMA, "artifact_status": status, "rom": payload["rom"], "upstream": payload["upstream"], "producer_denominator": payload["producer_denominator"], "source": payload["source"], "target": payload["target"], "promotion": payload["promotion"], "coverage_baseline": payload["coverage_baseline"], "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}}, "producer": {"command": producer_command, "implementation": payload["implementation"]}, "verifier": {"schema": VERIFY_SCHEMA, "command": verifier_command, "exit_code": 0 if status == "accepted" else None, "report": report, "verifier_sha256": payload["implementation"]["verifier_sha256"]}, "implementation": payload["implementation"], "scope": payload["scope"]}


def _failure(message: str) -> dict[str, Any]:
    report = dict(EXPECTED_REPORT)
    report["verified"] = False
    report["errors"] = [message]
    return report


def _verify_in_process(root: Path, artifact_dir: Path) -> dict[str, Any]:
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).expanduser().absolute()
        if artifact.is_symlink() or not artifact.is_dir():
            raise ValueError("v13 artifact directory is missing or uses a symlink")
        members = list(artifact.rglob("*"))
        if {path.relative_to(artifact).as_posix() for path in members if path.is_file()} != {MANIFEST_NAME, PAYLOAD_NAME} or any(path.is_symlink() for path in members):
            raise ValueError("v13 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        payload_path = _artifact_file(artifact, PAYLOAD_NAME)
        manifest_path = _artifact_file(artifact, MANIFEST_NAME)
        payload_raw = payload_path.read_bytes()
        manifest_raw = manifest_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads(manifest_raw)
        if payload_raw != (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode() or manifest_raw != (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode():
            raise ValueError("v13 payload or manifest is not canonical JSON")
        expected_payload = _expected_payload(root, rom)
        if payload != expected_payload:
            raise ValueError("v13 payload contract differs from independent reconstruction")
        if manifest != _expected_manifest(root, artifact, manifest, expected_payload, payload_raw, manifest.get("artifact_status")):
            raise ValueError("v13 manifest contract differs from independent reconstruction")
        return dict(EXPECTED_REPORT)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return _failure(str(error))


def verify_rom_cfg_proven_roots_v13(root: Path, artifact_dir: Path) -> dict[str, Any]:
    return _verify_in_process(root, artifact_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify_rom_cfg_proven_roots_v13(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
