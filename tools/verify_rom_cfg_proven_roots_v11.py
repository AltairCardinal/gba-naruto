#!/usr/bin/env python3
"""Independently verify the fixed tick-callback CFG v11 packet."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
_CLEAN_CLI_STARTUP_CONFIRMED = False


def _require_isolated_cli_runtime() -> None:
    global _CLEAN_CLI_STARTUP_CONFIRMED
    if __name__ != "__main__":
        return
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("CFG v11 CLI requires Python -I -S isolation")
    if "capstone" in sys.modules:
        raise RuntimeError("CFG v11 CLI rejects preloaded Capstone modules")
    if os.environ.get("LIBCAPSTONE_PATH"):
        raise RuntimeError("CFG v11 CLI rejects LIBCAPSTONE_PATH overrides")
    _CLEAN_CLI_STARTUP_CONFIRMED = True


_require_isolated_cli_runtime()

for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.verify_rom_cfg_inventory import _decode, _safe_file  # noqa: E402


ROM_BASE = 0x08000000
ROM_PATH = Path("rom/base.gba")
ROM_SIZE = 6_291_456
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "rom-cfg-proven-roots-v11"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v11"
PROMOTION_SCHEMA = "git-artifact-promotion-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots-v11.json"
MANIFEST_NAME = "manifest.json"

EXPECTED_REPORT = {
    "schema": VERIFY_SCHEMA,
    "verified": True,
    "errors": [],
    "control_flow_oracle": "armv4t-raw-encoding",
    "raw_target_producer_count": 9,
    "accepted_target_producer_count": 8,
    "excluded_unproven_source_count": 1,
    "source_root_count": 8,
    "source_decoded_instruction_count": 537,
    "source_decoded_basic_block_count": 92,
    "source_reachable_instruction_bytes": 1130,
    "source_frontier_count": 0,
    "source_external_call_edge_count": 28,
    "independently_rebuilt_instruction_count": 30,
    "decoded_basic_block_count": 6,
    "reachable_instruction_bytes": 62,
    "frontier_count": 0,
    "external_call_edge_count": 1,
}

SOURCE_RANGE = (0x080554, 0x080A46)
SOURCE_SLICE_SHA256 = "22aae5132d081d89b9e9315968c1d3d089131b269ae1f5cfa232d1d6d13b8c8a"
SOURCE_ROOT_VECTOR_SHA256 = "a7713d600741b0dd4c0d7ada7d59086252a9821e33436efced0e23da7c1048b4"
SOURCE_EXTERNAL_VECTOR_SHA256 = "0cb2da1c57effcb48910685b26bcc1331ecf923f34f65b9a0bb27b3be1ccb97b"
SOURCE_BLOCK_VECTOR_SHA256 = "16b4561b090a9a5cfda78923813e32c7c6c3a37fc8c67fdf7a1a63159cab3304"
SOURCE_SPECS = (
    (0x08055C, 0x08065E, 0x08064E, "f0b54f46", "8a1d56a49bd75817476a967ee4e23ecef2beeffa6748599c19bc8e7ed7620257", 118, 18, 250, "7a01382c7739a24b78e164c0eaee5367271a670b8ddfe81aa2e32adca7467855", "6b4b7326c82b01d30f7486b3ac98a158cea94b349296b888bbb71f40541cbaab"),
    (0x080670, 0x080762, 0x08072A, "f0b54746", "3e7ec2098933d96de8dc658d119ed3848ccdd7942f96f2a0d015f1e68e3c759b", 105, 16, 216, "59153c8ce6f6b295552306667c61f79d34ee452a1ef06224f533e37db2d988e1", "45102ed7d9db0d567b80b174209103bb251d4f5242804111de14d31be2f25ff7"),
    (0x080764, 0x080812, 0x0807E8, "f0b584b0", "9a03127c7ccf0b8c4ec43474f7c075704e096f385c54c0b7c78017896afb9ff1", 80, 14, 166, "02a7c6463fc9d948eeb2d221a398392369d5e356215cbc0c042322d774979c49", "d3fb9be1bfa4693ce65065e610f16f02ee1f531d50e3f3d5fc517eaaa6c32348"),
    (0x080814, 0x0808BA, 0x080892, "f0b584b0", "9a03127c7ccf0b8c4ec43474f7c075704e096f385c54c0b7c78017896afb9ff1", 77, 14, 160, "cd5e36e8e49373c003b4f1fdf27624f27904117594c8261c187489fd62454da2", "a91f164f2c83abb0190d00be3253bea1df8542ce09f0d690af68937b97ad14e7"),
    (0x0808C4, 0x080910, 0x080906, "30b584b0", "16d0e16c7269b3ae4e0b97c4aeb7103382fed757c0ee6ad513b0f7ebe3eef78e", 33, 7, 72, "b0d527d91abee77e0289b27ebb646766fc5dd4cb706e4cf6d28a7c0ebebd4d94", "c4a8e1dd07595a3fa9cf237b4c809a9d99a0622eaf1f445baa3cfc4882daedc4"),
    (0x080914, 0x080960, 0x080956, "30b584b0", "16d0e16c7269b3ae4e0b97c4aeb7103382fed757c0ee6ad513b0f7ebe3eef78e", 34, 7, 74, "33aa9c6b234de8d338d15993694ba8ba643fe4ebfa93e2921e12c8f3158cca80", "1e51f1334f8f5eddc8afbede0d56e582d5f320fd8218cbb8a741d18e39a6e547"),
    (0x080964, 0x0809F0, 0x0809E6, "30b584b0", "16d0e16c7269b3ae4e0b97c4aeb7103382fed757c0ee6ad513b0f7ebe3eef78e", 55, 9, 116, "1080c3a19046bc8c83fb1d0a73a5a6668d8a19ae0459eaece05dfb00494ff3dd", "f48d1f3aae17dec106cb35f5f4cc28fc72f792f8d019785b5de5757ece3ad497"),
    (0x0809F4, 0x080A44, 0x080A3A, "30b584b0", "16d0e16c7269b3ae4e0b97c4aeb7103382fed757c0ee6ad513b0f7ebe3eef78e", 35, 7, 76, "672b5be4716ff294b79b1a272f38400e613a69a48f252692a82173619772eadc", "852227b2a297cad00a486e58274b0733c7d4bbc95b491dcf006b4da48eeeb923"),
)
PRODUCER_SPECS = (
    (0x08064E, "e2f7b7fe", "e9569ef5f484cb3614fec0f1004df2d54775972c8fbd4c96c095ceb33bf016a5", "accepted_fixed_tick_callback_closure"),
    (0x08072A, "e2f749fe", "4c6c3403d646884caa3097d9e9732b6ac98135bf81ed7d1ea35c43996764ffd7", "accepted_fixed_tick_callback_closure"),
    (0x0807E8, "e2f7eafd", "b8df4590b05b8b4e137fb92ac8dd2578f67247c2add3ad7ae1b4412bf369c3e2", "accepted_fixed_tick_callback_closure"),
    (0x080892, "e2f795fd", "166e76fd67e3b9189f019203d188872184c09009ce26d4c65c2efd22085daa72", "accepted_fixed_tick_callback_closure"),
    (0x080906, "e2f75bfd", "be6392d8ccb6312b98222178231f8035d0a5c87578e426b75409411bd5c8cce3", "accepted_fixed_tick_callback_closure"),
    (0x080956, "e2f733fd", "48f6cd4792b0a94eb736207a3649d8ec2581b56048fbc65de382d95bb9c7859b", "accepted_fixed_tick_callback_closure"),
    (0x0809E6, "e2f7ebfc", "259386b428280f08c3c5c92ab6ad1bdf63d31bfd82a6ae37ea6431574347e4e9", "accepted_fixed_tick_callback_closure"),
    (0x080A3A, "e2f7c1fc", "ce0b0e41d69429b983a88bdafe6972e6c025537cf6df7b636f71a8074c4a49dd", "accepted_fixed_tick_callback_closure"),
    (0x080D7C, "e2f720fb", "81e18c23989b5a1c06a9d1f8a732628bc30726c1c7e76a814ec02d6fbca7c054", "excluded_unproven_source"),
)

TARGET_RANGE = (0x0633C0, 0x0633FE)
TARGET_ENVELOPE = TARGET_RANGE
TARGET_ROOT = 0x0633C0
TARGET_ROOT_RAW = "30b5051c"
TARGET_ROOT_SHA256 = "df4b34ae82a0188510cc4ac861082202afc6dda014c718f38abd68912aebdf96"
TARGET_BLOCK_RANGE_SHA256 = "4cdafc34a251971c6edec8d98dbf812042ccaab70e1ec3ee663976301a5a86c6"
ENVELOPE_SHA256 = "bce5dad093cbcf2447728c50288b94fb47140fe452f6846f83b7224220dfb5cd"
OPAQUE_BASELINE_CALLEE = 0x062788
TARGET_RETURN_BX = 0x0633FC
RETURN_PREFIX = "01bc0047"
RETURN_SHA256 = "15a0c45072c4f43ac42d0c62cb597469cb73ae8294c056a31dc8415af2bc0d3c"

COVERAGE_PATH = Path("sequel/rom-byte-coverage.json")
COVERAGE_SHA256 = "c65ec320a432681600bda916254f3265489829ee2f0b8b885b885b5436d35396"

UPSTREAM = {
    "artifact_schema": "battle-effect-sprite-animations-v1",
    "manifest_path": "artifacts/battle-effect-sprite-animations-v1/manifest.json",
    "manifest_sha256": "46403c9f070c20561862b5f4ec572a7c511aa199eb3b7b7edae37e97f4877848",
    "verifier_path": "tools/verify_battle_effect_sprite_animations.py",
    "verifier_sha256": "ba22259f41e53398a0f271f806c831b5eaf0052f17784c831d2591c0220f0c6b",
    "verification_schema": "battle-effect-sprite-animations-verification-v1",
    "consumer_slice_name": "all_effect_descriptor_callbacks",
    "consumer_slice_range": list(SOURCE_RANGE),
    "consumer_slice_sha256": SOURCE_SLICE_SHA256,
    "playback_plan_count": 22,
    "non_null_tick_slot_count": 21,
    "unique_tick_root_count": 8,
}

NONCLAIMS = [
    "natural_execution_reachability",
    "global_code_denominator",
    "global_caller_denominator",
    "global_indirect_target_denominator",
    "excluded_0x080d7c_instruction_status",
    "adjacent_target_bytes",
    "external_callee_semantics",
    "function_abi_or_business_meaning",
    "edit_relocation_or_free_space",
]
SCOPE = {
    "target_limited_raw_producer_denominator_complete": True,
    "fixed_tick_callback_source_closures_complete": True,
    "target_closure_complete": True,
    "baseline_entries_treated_as_opaque": True,
    "promotion_window_complete": True,
    "current_known_overlap_bytes": 0,
    "runtime_reachability_complete": False,
    "global_code_denominator_complete": False,
    "global_caller_denominator_complete": False,
    "global_indirect_target_denominator_complete": False,
    "excluded_unproven_source_instruction_proven": False,
    "nonclaims": NONCLAIMS,
}

CAPSTONE_RUNTIME_DIRECTORY = Path("tools/_vendor/capstone")
RUNTIME_DEPENDENCY_PATHS = (
    Path("tools/export_rom_cfg_inventory.py"),
    Path("tools/verify_rom_cfg_inventory.py"),
    Path("tools/verify_battle_effect_sprite_animations.py"),
    Path("tools/verify_rom_cfg_seeds.py"),
    Path("tools/verify_similar_table_candidates.py"),
) + tuple(
    CAPSTONE_RUNTIME_DIRECTORY / path.name
    for path in sorted(CAPSTONE_RUNTIME_DIRECTORY.glob("*.py"))
) + (CAPSTONE_RUNTIME_DIRECTORY / "lib/libcapstone.dylib",)


_MODE_RANK = {"arm": 0, "thumb": 1}
_MAX_BLOCK_INSTRUCTION_COUNT = 256


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return (rendered + "\n").encode("utf-8")


def _canonical_sha(value: object) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha(rendered)


def _key(mode: str, offset: int) -> tuple[int, int, str]:
    return (offset, _MODE_RANK[mode], mode)


def _union_bytes(ranges: list[tuple[int, int]]) -> int:
    total = 0
    start = end = None
    for left, right in sorted(ranges):
        if start is None:
            start, end = left, right
        elif left > end:
            total += end - start
            start, end = left, right
        else:
            end = max(end, right)
    if start is not None:
        total += end - start
    return total


def _build_blocks(
    rom: bytes,
    nodes: dict[tuple[str, int], dict[str, Any]],
    root_keys: set[tuple[str, int]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], str]]:
    """Reconstruct block records locally without importing an exporter helper."""

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

    starts = {item for item in root_keys if item in nodes}
    for item, node in nodes.items():
        predecessors = incoming[item]
        if len(predecessors) != 1:
            starts.add(item)
            continue
        predecessor = predecessors[0]
        predecessor_node = nodes[predecessor]
        contiguous = (
            predecessor[0] == item[0]
            and predecessor[1] + predecessor_node["size"] == item[1]
        )
        if (
            len(resolved[predecessor]) != 1
            or not contiguous
            or predecessor_node["flow_kind"] != "linear"
        ):
            starts.add(item)

    pending = [_key(*item) for item in starts]
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
        first = (mode, offset)
        if first in assigned:
            continue
        members: list[tuple[str, int]] = []
        current = first
        block_id = f"block-{mode}-{offset:06x}"
        while current not in assigned:
            members.append(current)
            assigned[current] = block_id
            node = nodes[current]
            targets = resolved[current]
            if (
                len(members) >= _MAX_BLOCK_INSTRUCTION_COUNT
                and len(targets) == 1
                and node["flow_kind"] == "linear"
            ):
                heapq.heappush(pending, _key(*targets[0]))
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
        for edge in nodes[last]["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in nodes:
                block["successors"].append({**edge, "block_id": assigned[target]})
        blocks.append(block)
    blocks.sort(key=lambda block: _key(block["mode"], block["range"][0]))
    return blocks, assigned


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
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first = int.from_bytes(rom[offset : offset + 2], "little")
        second = int.from_bytes(rom[offset + 2 : offset + 4], "little")
        if _producer_target(offset, first, second) == TARGET_ROOT:
            actual.append(offset)
    if actual != [item[0] for item in PRODUCER_SPECS]:
        raise ValueError("target-limited producer denominator changed")
    records = []
    for offset, raw_hex, digest, status in PRODUCER_SPECS:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError(f"producer bytes changed at 0x{offset:06X}")
        records.append({
            "file_offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}",
            "raw_hex": raw_hex,
            "bytes_sha256": digest,
            "target_file_offset": TARGET_ROOT,
            "target_gba_address": f"0x{ROM_BASE + TARGET_ROOT:08X}",
            "status": status,
        })
    return {
        "scan": {"mode": "thumb", "alignment_bytes": 2, "range": [0, len(rom)], "target_file_offsets": [TARGET_ROOT], "matching_producer_count": len(records)},
        "producers": records,
        "denominator_sha256": _canonical_sha(records),
    }


def _return_record(rom: bytes, bx_offset: int) -> dict[str, Any]:
    prefix = rom[bx_offset - 2 : bx_offset + 2]
    if prefix.hex() != RETURN_PREFIX or _sha(prefix) != RETURN_SHA256:
        raise ValueError(f"return idiom changed at 0x{bx_offset:06X}")
    if rom[bx_offset : bx_offset + 2] != b"\x00\x47":
        raise ValueError(f"return BX changed at 0x{bx_offset:06X}")
    return {
        "kind": "bx",
        "mode": "thumb",
        "bx_file_offset": bx_offset,
        "prefix_range": [bx_offset - 2, bx_offset + 2],
        "prefix_hex": RETURN_PREFIX,
        "prefix_sha256": RETURN_SHA256,
    }


def _merged_ranges(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted((offset, offset + node["size"]) for (_, offset), node in nodes.items()):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _bounded_worklist(
    rom: bytes,
    root: int,
    bound: tuple[int, int],
    return_bx: int,
    *,
    target_is_producer: bool,
) -> tuple[dict[tuple[str, int], dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    pending = [(root, 1, "thumb")]
    scheduled = {("thumb", root)}
    nodes: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: dict[tuple[str, int], dict[str, Any]] = {}
    external: list[dict[str, Any]] = []
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in nodes or item in rejected:
            continue
        if offset < bound[0] or offset >= bound[1]:
            raise ValueError("bounded CFG worklist escaped frozen range")
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            rejected[item] = decoded
            continue
        if offset == return_bx and mode == "thumb":
            decoded = {**decoded, "flow_kind": "return", "frontiers": [], "successors": []}
        if offset + decoded["size"] > bound[1]:
            raise ValueError("bounded CFG instruction straddles frozen range")
        nodes[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if not (bound[0] <= target[1] < bound[1]) or target[0] != "thumb":
                if edge["kind"] != "call_target":
                    raise ValueError("bounded CFG non-call edge escapes frozen range")
                if target_is_producer and target[1] == TARGET_ROOT:
                    reason = "target_producer"
                elif not target_is_producer and target[1] == OPAQUE_BASELINE_CALLEE:
                    reason = "opaque_baseline_callee"
                else:
                    reason = "opaque_external"
                external_record = {
                    "source": {"mode": mode, "file_offset": offset},
                    "source_file_offset": offset,
                    "edge_kind": edge["kind"],
                    "target_mode": target[0],
                    "target_file_offset": target[1],
                    "reason": reason,
                }
                external.append(external_record)
                continue
            if target not in scheduled:
                heapq.heappush(pending, _key(*target))
                scheduled.add(target)
    blocks, _ = _build_blocks(rom, nodes, {("thumb", root)})
    return nodes, blocks, external


def _summary(nodes: dict[tuple[str, int], dict[str, Any]], blocks: list[dict[str, Any]], external: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": len(nodes),
        "frontier_count": sum(len(node["frontiers"]) for node in nodes.values()),
        "reachable_instruction_bytes": _union_bytes(
            [(offset, offset + node["size"]) for (_, offset), node in nodes.items()]
        ),
        "external_call_edge_count": len(external),
        "external_call_edge_reasons": dict(sorted(Counter(edge["reason"] for edge in external).items())),
    }


def _node_list(nodes: dict[tuple[str, int], dict[str, Any]]) -> list[dict[str, Any]]:
    return [nodes[item] for item in sorted(nodes, key=lambda key: _key(*key))]


def _source_worklists(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    if _sha(rom[SOURCE_RANGE[0] : SOURCE_RANGE[1]]) != SOURCE_SLICE_SHA256:
        raise ValueError("source callback slice changed")
    closures = []
    all_external = []
    all_block_ranges = []
    for spec in SOURCE_SPECS:
        root, return_bx, producer, raw_hex, entry_sha, insn_count, block_count, byte_count, block_sha, external_sha = spec
        entry = rom[root : root + 4]
        if entry.hex() != raw_hex or _sha(entry) != entry_sha:
            raise ValueError(f"source root changed at 0x{root:06X}")
        nodes, blocks, external = _bounded_worklist(
            rom, root, (root, return_bx + 2), return_bx, target_is_producer=True
        )
        summary = _summary(nodes, blocks, external)
        if (summary["decoded_instruction_count"], summary["decoded_basic_block_count"], summary["reachable_instruction_bytes"], summary["frontier_count"]) != (insn_count, block_count, byte_count, 0):
            raise ValueError(f"source bounded CFG denominator changed at 0x{root:06X}: {summary}")
        if _canonical_sha([block["range"] for block in blocks]) != block_sha:
            raise ValueError(f"source block range denominator changed at 0x{root:06X}")
        canonical_external = [
            {key: value for key, value in edge.items() if key != "source_file_offset"}
            for edge in external
        ]
        if _canonical_sha(canonical_external) != external_sha:
            raise ValueError(f"source external vector changed at 0x{root:06X}")
        if [edge["source"]["file_offset"] for edge in external if edge["reason"] == "target_producer"] != [producer]:
            raise ValueError(f"source accepted producer changed at 0x{root:06X}")
        closures.append({
            "root": {"mode": "thumb", "file_offset": root, "entry_raw_hex": raw_hex, "entry_sha256": entry_sha},
            "accepted_producer_file_offset": producer,
            "return": _return_record(rom, return_bx),
            "range": [root, return_bx + 2],
            "nodes": _node_list(nodes),
            "blocks": blocks,
            "frontiers": [],
            "external_edges": external,
            "external_vector_sha256": external_sha,
            "block_range_sha256": block_sha,
            "merged_ranges": _merged_ranges(nodes),
            "summary": summary,
        })
        all_external.extend(external)
        all_block_ranges.extend(block["range"] for block in blocks)
    summary = {
        "root_count": len(closures),
        "decoded_instruction_count": sum(item["summary"]["decoded_instruction_count"] for item in closures),
        "decoded_basic_block_count": sum(item["summary"]["decoded_basic_block_count"] for item in closures),
        "reachable_instruction_bytes": sum(item["summary"]["reachable_instruction_bytes"] for item in closures),
        "frontier_count": 0,
        "external_call_edge_count": sum(item["summary"]["external_call_edge_count"] for item in closures),
    }
    if summary != {"root_count": 8, "decoded_instruction_count": 537, "decoded_basic_block_count": 92, "reachable_instruction_bytes": 1130, "frontier_count": 0, "external_call_edge_count": 28}:
        raise ValueError(f"source closure summary changed: {summary}")
    roots = [item["root"]["file_offset"] for item in closures]
    canonical_external = [
        {key: value for key, value in edge.items() if key != "source_file_offset"}
        for edge in all_external
    ]
    root_vector_sha256 = _canonical_sha(roots)
    external_vector_sha256 = _canonical_sha(canonical_external)
    block_range_vector_sha256 = _canonical_sha(all_block_ranges)
    if root_vector_sha256 != SOURCE_ROOT_VECTOR_SHA256:
        raise ValueError("source root vector changed")
    if external_vector_sha256 != SOURCE_EXTERNAL_VECTOR_SHA256:
        raise ValueError("source aggregate external vector changed")
    if block_range_vector_sha256 != SOURCE_BLOCK_VECTOR_SHA256:
        raise ValueError("source aggregate block range vector changed")
    return {
        "range": list(SOURCE_RANGE),
        "size": SOURCE_RANGE[1] - SOURCE_RANGE[0],
        "slice_sha256": SOURCE_SLICE_SHA256,
        "root_vector_sha256": root_vector_sha256,
        "external_vector_sha256": external_vector_sha256,
        "block_range_vector_sha256": block_range_vector_sha256,
        "closures": closures,
        "summary": summary,
    }


def _target_worklist(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    envelope = rom[TARGET_ENVELOPE[0] : TARGET_ENVELOPE[1]]
    if _sha(envelope) != ENVELOPE_SHA256:
        raise ValueError("target envelope changed")
    entry = rom[TARGET_ROOT : TARGET_ROOT + 4]
    if entry.hex() != TARGET_ROOT_RAW or _sha(entry) != TARGET_ROOT_SHA256:
        raise ValueError("target root changed")
    nodes, blocks, external = _bounded_worklist(
        rom, TARGET_ROOT, TARGET_RANGE, TARGET_RETURN_BX, target_is_producer=False
    )
    summary = _summary(nodes, blocks, external)
    if summary != {"decoded_basic_block_count": 6, "decoded_instruction_count": 30, "frontier_count": 0, "reachable_instruction_bytes": 62, "external_call_edge_count": 1, "external_call_edge_reasons": {"opaque_baseline_callee": 1}}:
        raise ValueError(f"target bounded CFG denominator changed: {summary}")
    block_ranges = [block["range"] for block in blocks]
    if _canonical_sha(block_ranges) != TARGET_BLOCK_RANGE_SHA256:
        raise ValueError("target block range denominator changed")
    if [(edge["source_file_offset"], edge["target_file_offset"], edge["reason"]) for edge in external] != [(0x0633EA, OPAQUE_BASELINE_CALLEE, "opaque_baseline_callee")]:
        raise ValueError("target opaque baseline call changed")
    return {
        "envelope": list(TARGET_ENVELOPE),
        "envelope_size": TARGET_ENVELOPE[1] - TARGET_ENVELOPE[0],
        "envelope_sha256": ENVELOPE_SHA256,
        "root": {"mode": "thumb", "file_offset": TARGET_ROOT, "entry_raw_hex": TARGET_ROOT_RAW, "entry_sha256": TARGET_ROOT_SHA256},
        "code_ranges": block_ranges,
        "nodes": _node_list(nodes),
        "blocks": blocks,
        "frontiers": [],
        "external_edges": external,
        "block_range_sha256": TARGET_BLOCK_RANGE_SHA256,
        "summary": summary,
        "return": _return_record(rom, TARGET_RETURN_BX),
    }


def _frozen_coverage_baseline() -> dict[str, Any]:
    return {
        "path": "sequel/rom-byte-coverage.json",
        "sha256": COVERAGE_SHA256,
        "promotion_envelope": list(TARGET_ENVELOPE),
        "promotion_bytes": 62,
        "promotion_code_bytes": 62,
        "promotion_literal_bytes": 0,
        "current_unknown_bytes": 62,
        "current_known_overlap_bytes": 0,
        "unknown_bytes": 62,
    }


def _upstream_contract(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    manifest_path = _safe_file(root, UPSTREAM["manifest_path"])
    verifier_path = _safe_file(root, UPSTREAM["verifier_path"])
    if _sha(manifest_path.read_bytes()) != UPSTREAM["manifest_sha256"]:
        raise ValueError("battle-effect upstream manifest identity changed")
    if _sha(verifier_path.read_bytes()) != UPSTREAM["verifier_sha256"]:
        raise ValueError("battle-effect upstream verifier identity changed")
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("schema") != UPSTREAM["artifact_schema"]:
        raise ValueError("battle-effect upstream schema changed")
    plans = manifest.get("sequence_playback_plans")
    if not isinstance(plans, list) or len(plans) != UPSTREAM["playback_plan_count"]:
        raise ValueError("battle-effect playback plan denominator changed")
    callbacks = [int(item["tick_callback_thumb"], 16) for item in plans]
    if sum(bool(value) for value in callbacks) != UPSTREAM["non_null_tick_slot_count"]:
        raise ValueError("battle-effect non-null tick slot denominator changed")
    roots = sorted({(value - ROM_BASE) & ~1 for value in callbacks if value})
    if roots != [item[0] for item in SOURCE_SPECS]:
        raise ValueError("battle-effect tick callback roots changed")
    slices = manifest.get("consumer_code_slices")
    if not isinstance(slices, list):
        raise ValueError("battle-effect consumer slices changed")
    matching = [item for item in slices if item.get("name") == UPSTREAM["consumer_slice_name"]]
    if len(matching) != 1:
        raise ValueError("battle-effect callback consumer slice denominator changed")
    source_slice = matching[0]
    if (
        source_slice.get("file_offset") != SOURCE_RANGE[0]
        or int(source_slice.get("gba_end", "0"), 16) - ROM_BASE != SOURCE_RANGE[1]
        or source_slice.get("sha256") != SOURCE_SLICE_SHA256
    ):
        raise ValueError("battle-effect callback consumer slice changed")
    from tools.verify_battle_effect_sprite_animations import verify_battle_effect_sprite_animations

    report = verify_battle_effect_sprite_animations(root, root / "artifacts/battle-effect-sprite-animations-v1")
    if report.get("schema") != UPSTREAM["verification_schema"] or report.get("verified") is not True or report.get("errors") != []:
        raise ValueError(f"battle-effect upstream independent verification failed: {report}")
    return dict(UPSTREAM)


def _implementation(root: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    paths = {
        "exporter": Path("tools/export_rom_cfg_proven_roots_v11.py"),
        "verifier": Path("tools/verify_rom_cfg_proven_roots_v11.py"),
        "test": Path("tests/test_export_rom_cfg_proven_roots_v11.py"),
    }
    dependencies: dict[str, str] = {}
    for relative in RUNTIME_DEPENDENCY_PATHS:
        dependencies[relative.as_posix()] = _sha(_safe_file(root, relative).read_bytes())
    return {
        "binding": "passed-root-runtime-dependency-and-test-hash-bound",
        "paths": {label: path.as_posix() for label, path in paths.items()},
        "exporter_sha256": _sha(_safe_file(root, paths["exporter"]).read_bytes()),
        "verifier_sha256": _sha(_safe_file(root, paths["verifier"]).read_bytes()),
        "test_sha256": _sha(_safe_file(root, paths["test"]).read_bytes()),
        "runtime_dependency_sha256": dependencies,
    }


def _expected_payload(root: Path, rom: bytes) -> dict[str, Any]:
    denominator = _producer_denominator(rom)
    source = _source_worklists(rom)
    target = _target_worklist(rom)
    promotion = {
        "envelope": list(TARGET_ENVELOPE),
        "envelope_sha256": ENVELOPE_SHA256,
        "promotion_bytes": 62,
        "promotion_code_bytes": 62,
        "promotion_literal_bytes": 0,
        "current_known_overlap_bytes": 0,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": ROM_SIZE, "sha256": ROM_SHA256},
        "upstream": _upstream_contract(root),
        "producer_denominator": denominator,
        "source": source,
        "target": target,
        "promotion": promotion,
        "coverage_baseline": _frozen_coverage_baseline(),
        "implementation": _implementation(root),
        "scope": dict(SCOPE),
    }


def _artifact_file(artifact: Path, name: str) -> Path:
    if artifact.is_symlink() or not artifact.is_dir():
        raise ValueError("v11 artifact directory is missing or uses a symlink")
    path = artifact / name
    if path.is_symlink() or not path.is_file():
        raise ValueError("v11 artifact file set uses a symlink or is incomplete")
    return path


def _receipt_commands(
    root: Path,
    manifest: dict[str, Any],
) -> tuple[list[str], list[str]]:
    root = Path(root).resolve(strict=True)
    producer = manifest.get("producer")
    verifier = manifest.get("verifier")
    if not isinstance(producer, dict) or not isinstance(verifier, dict):
        raise ValueError("v11 promotion receipt is missing")
    producer_command = producer.get("command")
    verifier_command = verifier.get("command")
    producer_prefix = [
        "python3",
        "-I",
        "-S",
        "tools/export_rom_cfg_proven_roots_v11.py",
        "--root",
        ".",
        "--output-dir",
    ]
    verifier_prefix = [
        "python3",
        "-I",
        "-S",
        "tools/verify_rom_cfg_proven_roots_v11.py",
        "--root",
        ".",
        "--artifact-dir",
    ]
    if (
        not isinstance(producer_command, list)
        or producer_command[:-1] != producer_prefix
        or not isinstance(verifier_command, list)
        or verifier_command[:-1] != verifier_prefix
        or producer_command[-1] != verifier_command[-1]
    ):
        raise ValueError("v11 promotion receipt command changed")
    recorded = Path(producer_command[-1])
    if recorded.is_absolute():
        raise ValueError("v11 promotion receipt path must be repository-relative")
    target = (root / recorded).resolve(strict=False)
    allowed = (root / "build/experiments/active/cfg-proven-roots-v11").resolve(strict=False)
    if target == allowed or allowed not in target.parents:
        raise ValueError("v11 promotion receipt path escaped experiment subtree")
    return producer_command, verifier_command


def _expected_manifest(
    root: Path,
    manifest: dict[str, Any],
    payload: dict[str, Any],
    payload_raw: bytes,
    *,
    status: str,
) -> dict[str, Any]:
    if status not in {"candidate", "accepted"}:
        raise ValueError("v11 promotion status changed")
    producer_command, verifier_command = _receipt_commands(root, manifest)
    implementation = payload["implementation"]
    report = EXPECTED_REPORT if status == "accepted" else None
    return {
        "schema": PROMOTION_SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": status,
        "rom": payload["rom"],
        "upstream": payload["upstream"],
        "producer_denominator": payload["producer_denominator"],
        "source": payload["source"],
        "target": payload["target"],
        "promotion": payload["promotion"],
        "coverage_baseline": payload["coverage_baseline"],
        "files": {PAYLOAD_NAME: _sha(payload_raw)},
        "producer": {
            "command": producer_command,
            "implementation": implementation,
        },
        "verifier": {
            "schema": VERIFY_SCHEMA,
            "command": verifier_command,
            "exit_code": 0 if status == "accepted" else None,
            "report": report,
            "verifier_sha256": implementation["verifier_sha256"],
        },
        "implementation": implementation,
        "scope": payload["scope"],
    }


def _verify_in_process(root: Path, artifact_dir: Path) -> dict[str, Any]:
    raw_producers = accepted_producers = excluded_producers = source_roots = 0
    source_count = target_count = 0
    source_blocks = target_blocks = 0
    source_bytes = target_bytes = 0
    source_frontiers = target_frontiers = 0
    source_external = target_external = 0
    errors: list[str] = []
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        members = list(artifact.iterdir()) if artifact.exists() and artifact.is_dir() else []
        if artifact.is_symlink() or {item.name for item in members} != {MANIFEST_NAME, PAYLOAD_NAME} or any(item.is_symlink() or not item.is_file() for item in members):
            raise ValueError("v11 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        payload_path = _artifact_file(artifact, PAYLOAD_NAME)
        manifest_path = _artifact_file(artifact, MANIFEST_NAME)
        payload_raw = payload_path.read_bytes()
        manifest_raw = manifest_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads(manifest_raw)
        if payload_raw != _canonical_json(payload) or manifest_raw != _canonical_json(manifest):
            raise ValueError("v11 payload or manifest is not canonical JSON")
        expected_payload = _expected_payload(root, rom)
        if payload != expected_payload:
            raise ValueError("v11 payload contract differs from independent reconstruction")
        status = manifest.get("artifact_status")
        expected_manifest = _expected_manifest(
            root, manifest, expected_payload, payload_raw, status=status
        )
        if manifest != expected_manifest:
            raise ValueError("v11 manifest contract differs from independent reconstruction")
        records = expected_payload["producer_denominator"]["producers"]
        raw_producers = len(records)
        accepted_producers = sum(item["status"].startswith("accepted_") for item in records)
        excluded_producers = sum(item["status"] == "excluded_unproven_source" for item in records)
        source_summary = expected_payload["source"]["summary"]
        source_roots = source_summary["root_count"]
        source_count = source_summary["decoded_instruction_count"]
        source_blocks = source_summary["decoded_basic_block_count"]
        source_bytes = source_summary["reachable_instruction_bytes"]
        source_frontiers = source_summary["frontier_count"]
        source_external = source_summary["external_call_edge_count"]
        target_summary = expected_payload["target"]["summary"]
        target_count = target_summary["decoded_instruction_count"]
        target_blocks = target_summary["decoded_basic_block_count"]
        target_bytes = target_summary["reachable_instruction_bytes"]
        target_frontiers = target_summary["frontier_count"]
        target_external = target_summary["external_call_edge_count"]
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "control_flow_oracle": "armv4t-raw-encoding",
        "raw_target_producer_count": raw_producers,
        "accepted_target_producer_count": accepted_producers,
        "excluded_unproven_source_count": excluded_producers,
        "source_root_count": source_roots,
        "source_decoded_instruction_count": source_count,
        "source_decoded_basic_block_count": source_blocks,
        "source_reachable_instruction_bytes": source_bytes,
        "source_frontier_count": source_frontiers,
        "source_external_call_edge_count": source_external,
        "independently_rebuilt_instruction_count": target_count,
        "decoded_basic_block_count": target_blocks,
        "reachable_instruction_bytes": target_bytes,
        "frontier_count": target_frontiers,
        "external_call_edge_count": target_external,
    }


def verify_rom_cfg_proven_roots_v11(root: Path, artifact_dir: Path) -> dict[str, Any]:
    return _verify_in_process(root, artifact_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    report = verify_rom_cfg_proven_roots_v11(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
