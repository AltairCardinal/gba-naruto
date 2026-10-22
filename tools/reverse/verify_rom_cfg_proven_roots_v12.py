#!/usr/bin/env python3
"""Independently verify the frozen raw-ROM CFG proven-roots v12 packet."""

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
        raise RuntimeError("CFG v12 CLI requires Python -I -S isolation")
    if "capstone" in sys.modules:
        raise RuntimeError("CFG v12 CLI rejects preloaded Capstone modules")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("CFG v12 CLI rejects LIBCAPSTONE_PATH overrides")


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
SCHEMA = "rom-cfg-proven-roots-v12"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v12"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v12.json"
MANIFEST_NAME = "manifest.json"
EXPERIMENT_OUTPUT_ROOT = Path("build/experiments/active/cfg-proven-roots-v12-20260829")

SOURCE_RANGE = (398012, 398564)
SOURCE_SLICE_SHA256 = "90568d99bb0ddfba74ce946781049494e117bd2273bd3b69843f7df420506817"
SOURCE_ROOT = 398012
SOURCE_ENTRY_RAW = "30b52348"
SOURCE_ENTRY_SHA256 = "99904dcab479f7972fa6f37a6811077635d49a4b8f6743c737fff7126fbd8ecb"
SOURCE_PRODUCER = 398358
SOURCE_STOP = 398564
SOURCE_REACHABLE_RANGE_SHA256 = "4bcf92e722093ef3fce0130a28d7708afc5572859e9cdfb671d47a17d4559624"
SOURCE_PACKED_SHA256 = "45b2ec5ee53d3583d2e641ae5d1190045a541af0877462e2f509304f592fa158"
SOURCE_SEMANTIC_SHA256 = "bede899464bca87e2fde14ff8492eadf4735538963f3c3b8e5895552aec5e576"
SOURCE_BLOCK_SHA256 = "fb3c471b6695529759b6d18103ee733a1d0b0a9a97bd9a90f62449fbcb07b4f2"
SOURCE_INTERNAL_SHA256 = "4135e4f261905b1532bf59e598ac65253bf2461e560d03d2930cf4a3ff30d1f3"
SOURCE_EXTERNAL_SHA256 = "79112a1b6ca9a9a02b82283f66ea8ddea7108d3ce200e83d05732d531e03fa8e"
SOURCE_OPAQUE_BOUNDARY_SHA256 = "2e2cb02cca25a50a6f0dff30daaae54f9d15f4ffbd40875a0f14f6503d73d734"

TARGET_ROOT = 410744
TARGET_ENVELOPE = (410744, 411248)
TARGET_ENTRY_RAW = "f0b50006"
TARGET_ENTRY_SHA256 = "a33efa7811bffe160f9df32f0892ac99fc8b5458585f096fd2b2359c1a9ac110"
TARGET_ENVELOPE_SHA256 = "0ea20a2118080d5a6255aad2e336d95a112937005a61a498f66bf6c120b8957b"
TARGET_CODE_RANGES = ((410744, 410818), (410840, 410890), (410904, 410968), (410996, 411180))
TARGET_LITERAL_RANGES = ((410820, 410840), (410892, 410904), (410968, 410996), (411180, 411248))
TARGET_HOLES = ((410818, 410820), (410890, 410892))
TARGET_BLOCK_SHA256 = "722fee7509dc5c3da7da974e3dd9854ef7dcef7390372307e141bab5b52a7419"
TARGET_CODE_RANGE_SHA256 = "74f6d97e64d21ea8ff896f1a647ae7effc8a0d90ea0ae55215ff0bf5fa4ba5ce"
TARGET_LITERAL_RANGE_SHA256 = "9dcc966d9f59ca424241e80638e31910bee375f38e73700cca15e9a25b8ab81c"
TARGET_PROMOTION_RANGE_SHA256 = "b2b985dee623ffe0c5e3139112d2021bffd3ea0dbd32f8ad90c9fe91b14928cd"
TARGET_INTERNAL_SHA256 = "339d10d1fd6e3016be13b2734479b27717bf55ac0b8e4cb4b23a0c14783ae076"
TARGET_EXTERNAL_SHA256 = "8149f4918dd3a0548e3cfbd49803c76a71f0948e42dcc17205cfb835c68f8d62"
TARGET_SEMANTIC_SHA256 = "ce073ae1c13d87e06d2d0d47ce8630662de14584d421e842c5ba85a63de35044"
TARGET_LITERAL_BINDING_SHA256 = "5ddad79a99fabe64eb491d42b4f2ec33731e069b7dae00295f5e6b7232338f73"
TARGET_PACKED_CODE_SHA256 = "654c2b08bfcf87b16b9c3f211511f1646be306952bca9d220780d9bf374b1a84"
TARGET_PACKED_LITERAL_SHA256 = "7e32235d7f70003fe683de30952b77ebe65b67b95766d44041c65b556de00d10"
TARGET_PACKED_PROMOTION_SHA256 = "a8043f37679964db642c2d743812d5aab93a7193016d3ffd14d805b9105cf8e8"
TARGET_RETURN_BX = 411178

COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "05215215595f0614f0461fa7502703ca62ccaa07159ddb27810f9903a31ef6d6"
COVERAGE_EXPECTED = {
    "path": COVERAGE_PATH.as_posix(),
    "sha256": COVERAGE_SHA256,
    "classified_bytes": 6125883,
    "unknown_bytes": 165573,
    "promotion_bytes": 500,
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
    "callee_code_abi_or_semantics_at_0x0624c0_or_0x062510",
    "semantic_expansion_of_opaque_0x09c0e0_wrapper",
    "literal_business_meaning_compiler_authorship_or_adjacent_bytes",
    "padding_nop_reserved_free_or_allocatable_status_of_holes",
    "editing_writeback_relocation_or_gameplay_graphics_audio_behavior",
]
SCOPE = {
    "source_worklist_bounded_to_accepted_slice": True,
    "source_producer_edge_rebuilt_from_raw_rom": True,
    "target_worklist_bounded_to_frozen_envelope": True,
    "target_producer_denominator_complete_for_fixed_target": True,
    "structured_return_rebuilt_from_raw_rom": True,
    "literal_bindings_rebuilt_from_raw_rom": True,
    "two_holes_excluded_from_promotion": True,
    "baseline_entries_treated_as_opaque": True,
    "promotion_window_complete": True,
    "current_known_overlap_bytes": 0,
    "runtime_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_producer_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "callee_semantics_proven": False,
    "literal_meaning_proven": False,
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
    "target_decoded_instruction_count": 182,
    "target_decoded_basic_block_count": 35,
    "target_reachable_instruction_bytes": 372,
    "target_frontier_count": 0,
    "target_internal_edge_count": 51,
    "target_external_call_edge_count": 4,
    "target_literal_reference_count": 35,
    "target_unique_literal_word_count": 32,
    "target_literal_bytes": 128,
    "promotion_range_count": 8,
    "promotion_bytes": 500,
    "hole_bytes": 4,
    "unclassified_hole_bytes": 4,
    "holes": [list(row) for row in TARGET_HOLES],
    "nonclaims": {name: False for name in NONCLAIMS},
}


def _entry(rom: bytes, offset: int, raw_hex: str, digest: str) -> dict[str, Any]:
    raw = rom[offset:offset + 4]
    if raw.hex() != raw_hex or _sha(raw) != digest:
        raise ValueError(f"entry bytes changed at 0x{offset:06X}")
    return {"mode": "thumb", "file_offset": offset, "entry_raw_hex": raw_hex, "entry_sha256": digest}


def _return_record(rom: bytes, bx_offset: int) -> dict[str, Any]:
    prefix = rom[bx_offset - 2:bx_offset + 2]
    if prefix.hex() != "01bc0047" or _sha(prefix) != "15a0c45072c4f43ac42d0c62cb597469cb73ae8294c056a31dc8415af2bc0d3c":
        raise ValueError("structured return bytes changed")
    return {"kind": "bx", "mode": "thumb", "bx_file_offset": bx_offset, "prefix_range": [bx_offset - 2, bx_offset + 2], "prefix_raw_hex": "01bc0047", "prefix_sha256": "15a0c45072c4f43ac42d0c62cb597469cb73ae8294c056a31dc8415af2bc0d3c"}


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
    if raw.hex() != "03f02ff8" or _sha(raw) != "578aa67445f8dd08e4b74bc1894aab74b270fbcce71815494585f9253707a8c4":
        raise ValueError("producer bytes changed")
    record = {"file_offset": SOURCE_PRODUCER, "gba_address": f"0x{ROM_BASE + SOURCE_PRODUCER:08X}", "raw_hex": raw.hex(), "bytes_sha256": _sha(raw), "target_file_offset": TARGET_ROOT, "target_gba_address": f"0x{ROM_BASE + TARGET_ROOT:08X}", "kind": "thumb_bl", "status": "accepted_source_producer"}
    return {"scan": {"mode": "thumb", "alignment_bytes": 2, "range": [0, ROM_SIZE], "target_file_offsets": [TARGET_ROOT], "matching_producer_count": 1}, "producers": [record], "thumb_bl": [record], "thumb_bl_count": len(thumb_bl), "thumb_b_count": len(thumb_b), "thumb_bcond_count": len(thumb_bcond), "arm_b_bl_count": len(arm_b_bl), "aligned_arm_pointer_count": len(aligned_arm_pointers), "thumb_pointer_count": len(thumb_pointers), "vector_sha256": _canonical_sha([[SOURCE_PRODUCER, TARGET_ROOT, "thumb_bl"]])}


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
    return {"root": _entry(rom, SOURCE_ROOT, SOURCE_ENTRY_RAW, SOURCE_ENTRY_SHA256), "range": list(SOURCE_RANGE), "size": SOURCE_RANGE[1] - SOURCE_RANGE[0], "slice_sha256": SOURCE_SLICE_SHA256, "nodes": _nodes(nodes), "blocks": blocks, "frontiers": [], "internal_edges": internal, "external_edges": external, "opaque_boundary_edges": boundary, "reachable_ranges": _merged_ranges(nodes), "reachable_range_vector_sha256": SOURCE_REACHABLE_RANGE_SHA256, "packed_instruction_bytes_sha256": SOURCE_PACKED_SHA256, "semantic_instruction_vector_sha256": SOURCE_SEMANTIC_SHA256, "block_range_vector_sha256": SOURCE_BLOCK_SHA256, "internal_edge_vector_sha256": SOURCE_INTERNAL_SHA256, "external_call_vector_sha256": SOURCE_EXTERNAL_SHA256, "opaque_boundary_vector_sha256": boundary_digest, "accepted_producer_file_offset": SOURCE_PRODUCER, "opaque_stop": {"file_offset": SOURCE_STOP, "coverage_claim_id": UPSTREAM["opaque_stop"]["coverage_claim_id"]}, "summary": {"root_count": 1, "decoded_instruction_count": 237, "decoded_basic_block_count": 40, "reachable_instruction_bytes": 508, "frontier_count": 0, "external_call_edge_count": 17, "target_producer_edge_count": 1, "opaque_boundary_edge_count": 1}}


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
    if len(full) != 35 or len({row[1] for row in full}) != 32 or _canonical_sha(bindings) != TARGET_LITERAL_BINDING_SHA256:
        raise ValueError("target literal binding vector changed")
    return {"bindings": full, "binding_vector": bindings, "literal_reference_count": 35, "unique_literal_word_count": 32, "bytes": 128, "ranges": [list(row) for row in TARGET_LITERAL_RANGES], "range_vector_sha256": TARGET_LITERAL_RANGE_SHA256, "binding_vector_sha256": TARGET_LITERAL_BINDING_SHA256, "packed_sha256": TARGET_PACKED_LITERAL_SHA256}


def _target_worklist(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256 or _sha(rom[TARGET_ENVELOPE[0]:TARGET_ENVELOPE[1]]) != TARGET_ENVELOPE_SHA256:
        raise ValueError("target identity changed")
    nodes, blocks, external, boundary = _bounded_worklist(rom, TARGET_ROOT, TARGET_ENVELOPE, TARGET_RETURN_BX)
    if len(nodes) != 182 or len(blocks) != 35 or boundary:
        raise ValueError("target CFG denominator changed")
    if _merged_ranges(nodes) != [list(row) for row in TARGET_CODE_RANGES]:
        raise ValueError("target merged code ranges changed")
    literals = _literal_projection(rom, nodes)
    internal = [[block["terminator"]["file_offset"], edge["file_offset"], edge["kind"]] for block in blocks for edge in block["successors"]]
    internal.sort(key=lambda row: (row[0], 0 if row[2] == "branch_target" else 1, row[1]))
    external_vector = [[row["source_file_offset"], row["target_file_offset"], row["edge_kind"]] for row in sorted(external, key=lambda row: row["source_file_offset"])]
    promotion_ranges = sorted([list(row) for row in TARGET_CODE_RANGES + TARGET_LITERAL_RANGES])
    if _canonical_sha([b["range"] for b in blocks]) != TARGET_BLOCK_SHA256 or _canonical_sha(internal) != TARGET_INTERNAL_SHA256 or _canonical_sha(external_vector) != TARGET_EXTERNAL_SHA256 or _canonical_sha(_semantic(nodes)) != TARGET_SEMANTIC_SHA256 or _packed(rom, TARGET_CODE_RANGES) != TARGET_PACKED_CODE_SHA256 or _packed(rom, TARGET_LITERAL_RANGES) != TARGET_PACKED_LITERAL_SHA256 or _packed(rom, promotion_ranges) != TARGET_PACKED_PROMOTION_SHA256 or _canonical_sha([list(row) for row in TARGET_CODE_RANGES]) != TARGET_CODE_RANGE_SHA256 or _canonical_sha([list(row) for row in TARGET_LITERAL_RANGES]) != TARGET_LITERAL_RANGE_SHA256 or _canonical_sha(promotion_ranges) != TARGET_PROMOTION_RANGE_SHA256:
        raise ValueError("target CFG vector changed")
    for start, end in TARGET_HOLES:
        if rom[start:end] != b"\x00\x00":
            raise ValueError("target hole bytes changed")
    return {"root": _entry(rom, TARGET_ROOT, TARGET_ENTRY_RAW, TARGET_ENTRY_SHA256), "envelope": list(TARGET_ENVELOPE), "envelope_bytes": 504, "envelope_sha256": TARGET_ENVELOPE_SHA256, "nodes": _nodes(nodes), "blocks": blocks, "block_ranges": [b["range"] for b in blocks], "code_ranges": [list(row) for row in TARGET_CODE_RANGES], "literal_ranges": [list(row) for row in TARGET_LITERAL_RANGES], "holes": [list(row) for row in TARGET_HOLES], "internal_edges": internal, "external_edges": external, "opaque_external_calls": [[r["source_file_offset"], r["target_file_offset"], r["edge_kind"]] for r in external], "structured_return": _return_record(rom, TARGET_RETURN_BX), "literal_projection": literals, "block_range_sha256": TARGET_BLOCK_SHA256, "block_range_vector_sha256": TARGET_BLOCK_SHA256, "code_range_vector_sha256": TARGET_CODE_RANGE_SHA256, "literal_range_vector_sha256": TARGET_LITERAL_RANGE_SHA256, "promotion_range_vector_sha256": TARGET_PROMOTION_RANGE_SHA256, "internal_edge_vector_sha256": TARGET_INTERNAL_SHA256, "external_call_vector_sha256": TARGET_EXTERNAL_SHA256, "semantic_instruction_vector_sha256": TARGET_SEMANTIC_SHA256, "literal_binding_vector_sha256": TARGET_LITERAL_BINDING_SHA256, "packed_code_sha256": TARGET_PACKED_CODE_SHA256, "packed_literals_sha256": TARGET_PACKED_LITERAL_SHA256, "packed_promotion_sha256": TARGET_PACKED_PROMOTION_SHA256, "promotion_ranges": promotion_ranges, "summary": {"decoded_instruction_count": 182, "decoded_basic_block_count": 35, "reachable_instruction_bytes": 372, "frontier_count": 0, "internal_edge_count": 51, "external_call_count": 4, "literal_reference_count": 35, "unique_literal_word_count": 32, "literal_bytes": 128, "promotion_range_count": 8, "promotion_bytes": 500, "hole_bytes": 4}}


def _coverage_baseline(root: Path) -> dict[str, Any]:
    path = _safe_file(root, COVERAGE_PATH)
    raw = path.read_bytes()
    if _sha(raw) != COVERAGE_SHA256:
        raise ValueError("coverage baseline identity changed")
    data = json.loads(raw)
    if data.get("summary", {}).get("classified_bytes") != 6125883 or data.get("summary", {}).get("unknown_bytes") != 165573:
        raise ValueError("coverage baseline summary changed")
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
    paths = {"exporter": Path("tools/export_rom_cfg_proven_roots_v12.py"), "verifier": Path("tools/verify_rom_cfg_proven_roots_v12.py"), "test_exporter": Path("tests/test_export_rom_cfg_proven_roots_v12.py"), "test_verifier": Path("tests/test_verify_rom_cfg_proven_roots_v12.py")}
    return {"binding": "passed-root-runtime-dependency-and-test-hash-bound", "paths": {key: value.as_posix() for key, value in paths.items()}, "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()), "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()), "test_exporter_sha256": _sha(_safe_file(root, paths["test_exporter"]).read_bytes()), "test_verifier_sha256": _sha(_safe_file(root, paths["test_verifier"]).read_bytes()), "runtime_dependency_sha256": {path.as_posix(): _sha(_safe_file(root, path).read_bytes()) for path in RUNTIME_DEPENDENCY_PATHS}}


def _expected_payload(root: Path, rom: bytes) -> dict[str, Any]:
    promotion_ranges = [list(row) for row in sorted(TARGET_CODE_RANGES + TARGET_LITERAL_RANGES)]
    return {"schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256}, "upstream": _upstream_contract(root), "producer_denominator": _producer_denominator(rom), "source": _source_worklist(rom), "target": _target_worklist(rom), "promotion": {"batch": "cfg-proven-roots-v12", "ranges": promotion_ranges, "promotion_range_count": 8, "promotion_bytes": 500, "promotion_code_bytes": 372, "promotion_literal_bytes": 128, "hole_bytes": 4, "packed_sha256": TARGET_PACKED_PROMOTION_SHA256, "range_vector_sha256": TARGET_PROMOTION_RANGE_SHA256, "unclassified_hole_bytes": 4}, "coverage_baseline": _coverage_baseline(root), "implementation": _implementation(root), "scope": dict(SCOPE)}


def _artifact_file(artifact: Path, name: str) -> Path:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("v12 artifact directory is missing or uses a symlink")
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("v12 artifact file set uses a symlink or is incomplete")
    return path


def _receipt_commands(root: Path, manifest: dict[str, Any]) -> tuple[list[str], list[str]]:
    producer = manifest.get("producer")
    verifier = manifest.get("verifier")
    if not isinstance(producer, dict) or not isinstance(verifier, dict):
        raise ValueError("v12 promotion receipt is missing")
    producer_command = producer.get("command")
    verifier_command = verifier.get("command")
    producer_prefix = ["python3", "-I", "-S", "tools/export_rom_cfg_proven_roots_v12.py", "--root", ".", "--output-dir"]
    verifier_prefix = ["python3", "-I", "-S", "tools/verify_rom_cfg_proven_roots_v12.py", "--root", ".", "--artifact-dir"]
    if not isinstance(producer_command, list) or producer_command[:-1] != producer_prefix or not isinstance(verifier_command, list) or verifier_command[:-1] != verifier_prefix or producer_command[-1] != verifier_command[-1]:
        raise ValueError("v12 promotion receipt command changed")
    recorded = Path(producer_command[-1])
    if recorded.is_absolute():
        raise ValueError("v12 promotion receipt path must be repository-relative")
    target = (root / recorded).resolve(strict=False)
    allowed = (root / EXPERIMENT_OUTPUT_ROOT).resolve(strict=False)
    official = (root / "artifacts/rom-cfg-proven-roots-v12").resolve(strict=False)
    if target != official and (target == allowed or allowed not in target.parents):
        raise ValueError("v12 promotion receipt path escaped experiment subtree")
    return producer_command, verifier_command


def _expected_manifest(root: Path, manifest: dict[str, Any], payload: dict[str, Any], payload_raw: bytes, status: str) -> dict[str, Any]:
    if status not in {"candidate", "accepted"}:
        raise ValueError("v12 promotion status changed")
    producer_command, verifier_command = _receipt_commands(root, manifest)
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
            raise ValueError("v12 artifact directory is missing or uses a symlink")
        members = list(artifact.rglob("*"))
        if {path.relative_to(artifact).as_posix() for path in members if path.is_file()} != {MANIFEST_NAME, PAYLOAD_NAME} or any(path.is_symlink() for path in members):
            raise ValueError("v12 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        payload_path = _artifact_file(artifact, PAYLOAD_NAME)
        manifest_path = _artifact_file(artifact, MANIFEST_NAME)
        payload_raw = payload_path.read_bytes()
        manifest_raw = manifest_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads(manifest_raw)
        if payload_raw != (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode() or manifest_raw != (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode():
            raise ValueError("v12 payload or manifest is not canonical JSON")
        expected_payload = _expected_payload(root, rom)
        if payload != expected_payload:
            raise ValueError("v12 payload contract differs from independent reconstruction")
        if manifest != _expected_manifest(root, manifest, expected_payload, payload_raw, manifest.get("artifact_status")):
            raise ValueError("v12 manifest contract differs from independent reconstruction")
        return dict(EXPECTED_REPORT)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        return _failure(str(error))


def verify_rom_cfg_proven_roots_v12(root: Path, artifact_dir: Path) -> dict[str, Any]:
    return _verify_in_process(root, artifact_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify_rom_cfg_proven_roots_v12(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
