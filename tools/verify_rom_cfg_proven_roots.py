#!/usr/bin/env python3
"""Independently verify the direct-call-proven Thumb CFG root delta."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import heapq
import json
from pathlib import Path
import struct
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
    _safe_file,
    _sha,
    _union_bytes,
    _verify_blocks,
)
from tools.verify_rom_cfg_inventory_v3 import verify_rom_cfg_inventory_v3


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v1"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v1"
PAYLOAD_NAME = "rom-cfg-proven-roots.json"

V2_ARTIFACT = Path("artifacts/rom-cfg-inventory-v2")
V2_PAYLOAD_NAME = "rom-cfg-inventory.json"
V2_SCHEMA = "rom-cfg-inventory-v2"
V2_MANIFEST_SHA256 = (
    "ee19c03c17a25a5c0492c72892f25dcbd213d3dc9413941c886dcea51bdb8753"
)
V2_PAYLOAD_SHA256 = (
    "b595e3469660d7cf0214a77cd3ebf9902f656a43d86c7ad62de0ce1ea8e4eedd"
)
V2_PAYLOAD_SIZE = 5_936_694
V2_GRAPH_SHA256 = (
    "e3f6c04ea459dbec397a9d71d6f32591ec03ed076ff8aad227277cb2b3534ba3"
)
V2_VERIFIER_PATH = Path("tools/verify_rom_cfg_inventory.py")
V2_VERIFIER_SHA256 = (
    "a23ff1915def7a55f25795ca848d63610aed730865ecfb26f4c518e509c75e93"
)

V3_ARTIFACT = Path("artifacts/rom-cfg-inventory-v3")
V3_PAYLOAD_NAME = "rom-cfg-inventory-v3.json"
V3_SCHEMA = "rom-cfg-inventory-v3"
V3_MANIFEST_SHA256 = (
    "6aa788611f73856e621f5c74aab544d47b034307a9dc1180f6fd8f81cb1f423b"
)
V3_PAYLOAD_SHA256 = (
    "596c4d8cffa57f3899858a0a59351894b1398006ee0405ce799ed9f32a81bf9d"
)
V3_PAYLOAD_SIZE = 1_322_391
V3_GRAPH_SHA256 = (
    "456545dddd3c43a5e9c19be6483871dbd333e3af3ecd1da8a9a83f762bced482"
)
V3_VERIFIER_PATH = Path("tools/verify_rom_cfg_inventory_v3.py")
V3_VERIFIER_SHA256 = (
    "46400e44866a93b571745f30779296cc5686889ac5d465891c648296d2dbe00a"
)

CONTROLLER_EVIDENCE_PATH = Path("notes/battle-controller-states-20260723.json")
CONTROLLER_EVIDENCE_SHA256 = (
    "e0157597e6d7fddb94d036ddfa7a0d2e74fa232450ad08534cd868d6c6fe1336"
)
CONTROLLER_RANGE = (0x732B4, 0x75082)
CONTROLLER_SHA256 = (
    "30c8e021502cca16fc3f569bbb21dd04f78d20bcbb8e6196550164a0d56429ff"
)
SIDE_END_WINDOW = (0x7367C, 0x7368C)
SIDE_END_WINDOW_SHA256 = (
    "2a0c42d909bf81f19ce2246cc1ce386bc70e97bbcf95ab0842263770d4758622"
)
SIDE_END_VERIFIER_PATH = Path("tools/verify_battlefield_object_effect_chain.py")
SIDE_END_VERIFIER_SHA256 = (
    "1d6914dd5ab444d48b08ceaa5de43fe6c35cbd07c34f75b7f0178293843b5760"
)

PRODUCER_VECTOR_SHA256 = (
    "22e76a4dc425aaf8bdf13eef2f018508093f1c2f9a0ff28b31abdf22275fa5e7"
)
ROOT_VECTOR_SHA256 = (
    "523f8662596de2a8d42df3849906a5c93841ba8575a09e94d67bcee4ece914c0"
)
FRONTIER_VECTOR_SHA256 = (
    "e426acd731a1de146e09c4446420c89a76439fba22e9db7b5238e16c532f1512"
)
CROSS_EDGE_VECTOR_SHA256 = (
    "897401ae862b45444bd17792af2331def5be3b0a3426e67dde62c53cbae38739"
)

EXPECTED_PRODUCERS = (
    (
        "side_end_expiry",
        0x73688,
        "0ef072fa",
        "0994a9f3765e80a7638b955c9ba53b42bd657ae006a5262df72a0eb2be336300",
        0x81B70,
    ),
    (
        "movedone_primary",
        0x7443C,
        "fdf734ff",
        "1b8c31ed5218ca26fd2c873d860248f682ddd2d9595083215a79ef40b0a64822",
        0x722A8,
    ),
    (
        "movedone_secondary",
        0x74918,
        "fdf7c6fc",
        "50a57e3c6daf40c655678302a3d45296aff939bb35f99a7addd3cb9b3d4dcaf1",
        0x722A8,
    ),
)

SCOPE = {
    "frozen_v2_v3_baseline_verified": True,
    "baseline_entries_treated_as_opaque": True,
    "fixed_direct_producer_denominator_complete": True,
    "direct_call_target_roots_only": True,
    "new_root_direct_cfg_traversal_performed": True,
    "baseline_bytes_duplicated": False,
    "indirect_target_resolution_complete": False,
    "global_direct_call_root_denominator_complete": False,
    "global_function_entry_denominator_complete": False,
    "runtime_reachability_complete": False,
}

LIMITATIONS = [
    "Only two roots selected by three fixed direct Thumb BL producers are traversed.",
    "The frozen v2 and v3 instruction entries are opaque stop targets and are not reclassified.",
    "Twenty-seven indirect PC targets and one decode failure remain explicit frontiers.",
    "Static direct-call reachability does not prove natural gameplay or runtime reachability.",
]


def _decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _producer_records() -> list[dict[str, Any]]:
    return [
        {
            "producer_id": producer_id,
            "file_offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}",
            "raw_hex": raw_hex,
            "bytes_sha256": digest,
            "target_file_offset": target,
            "target_gba_address": f"0x{ROM_BASE + target:08X}",
        }
        for producer_id, offset, raw_hex, digest, target in EXPECTED_PRODUCERS
    ]


def _producer_denominator(root: Path, rom: bytes) -> dict[str, Any]:
    target_addresses = {ROM_BASE + spec[4] for spec in EXPECTED_PRODUCERS}
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_thumb_bl(ROM_BASE + offset, first, second)
        if target in target_addresses:
            actual.append((offset, target - ROM_BASE))
    expected_pairs = [(spec[1], spec[4]) for spec in EXPECTED_PRODUCERS]
    if actual != expected_pairs:
        raise ValueError(
            f"independent direct-call producer denominator changed: "
            f"{actual!r} != {expected_pairs!r}"
        )
    producers = _producer_records()
    for producer in producers:
        offset = producer["file_offset"]
        raw = rom[offset : offset + 4]
        if raw.hex() != producer["raw_hex"] or _sha(raw) != producer["bytes_sha256"]:
            raise ValueError(
                f"independent direct-call producer bytes changed at 0x{offset:06X}"
            )
    denominator_sha256 = _canonical_sha(producers)
    if denominator_sha256 != PRODUCER_VECTOR_SHA256:
        raise ValueError("independent producer canonical denominator changed")
    start, end = CONTROLLER_RANGE
    if _sha(rom[start:end]) != CONTROLLER_SHA256:
        raise ValueError("independent battle-controller producer context changed")
    side_start, side_end = SIDE_END_WINDOW
    if _sha(rom[side_start:side_end]) != SIDE_END_WINDOW_SHA256:
        raise ValueError("independent side-end producer context changed")
    if (
        _sha(_safe_file(root, CONTROLLER_EVIDENCE_PATH).read_bytes())
        != CONTROLLER_EVIDENCE_SHA256
        or _sha(_safe_file(root, SIDE_END_VERIFIER_PATH).read_bytes())
        != SIDE_END_VERIFIER_SHA256
    ):
        raise ValueError("independent producer evidence identity changed")
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "targets": [0x722A8, 0x81B70],
            "matching_producer_count": len(producers),
        },
        "producers": producers,
        "denominator_sha256": denominator_sha256,
        "context": {
            "controller_range": list(CONTROLLER_RANGE),
            "controller_sha256": CONTROLLER_SHA256,
            "controller_evidence": {
                "path": CONTROLLER_EVIDENCE_PATH.as_posix(),
                "sha256": CONTROLLER_EVIDENCE_SHA256,
            },
            "side_end_window": list(SIDE_END_WINDOW),
            "side_end_window_sha256": SIDE_END_WINDOW_SHA256,
            "side_end_verifier": {
                "path": SIDE_END_VERIFIER_PATH.as_posix(),
                "sha256": SIDE_END_VERIFIER_SHA256,
            },
        },
    }


def _root_seeds(rom: bytes) -> list[dict[str, Any]]:
    entry_sha = _sha(rom[0x722A8:0x722AC])
    if entry_sha != _sha(rom[0x81B70:0x81B74]) or entry_sha != (
        "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
    ):
        raise ValueError("independent direct-call root entry bytes changed")
    roots = [
        {
            "root_id": "root-thumb-0722a8",
            "mode": "thumb",
            "file_offset": 0x722A8,
            "gba_address": "0x080722A8",
            "entry_size": 4,
            "entry_sha256": entry_sha,
            "sources": [
                {"producer_id": "movedone_primary"},
                {"producer_id": "movedone_secondary"},
            ],
        },
        {
            "root_id": "root-thumb-081b70",
            "mode": "thumb",
            "file_offset": 0x81B70,
            "gba_address": "0x08081B70",
            "entry_size": 4,
            "entry_sha256": entry_sha,
            "sources": [{"producer_id": "side_end_expiry"}],
        },
    ]
    if _canonical_sha(roots) != ROOT_VECTOR_SHA256:
        raise ValueError("independent root canonical denominator changed")
    return roots


def _load_bound_json(
    root: Path, relative: Path, *, size: int | None, digest: str
) -> dict[str, Any]:
    raw = _safe_file(root, relative).read_bytes()
    if (size is not None and len(raw) != size) or _sha(raw) != digest:
        raise ValueError(f"independent frozen CFG identity changed: {relative}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"independent frozen CFG is not an object: {relative}")
    return value


def _baseline_contract(root: Path, rom: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    report = verify_rom_cfg_inventory_v3(root, root / V3_ARTIFACT)
    if report != {
        "schema": "rom-cfg-inventory-verification-v3",
        "verified": True,
        "resolved_frontier_count": 29,
        "new_entry_seed_count": 101,
        "independently_rebuilt_instruction_count": 4_698,
        "decoded_basic_block_count": 891,
        "reachable_instruction_bytes": 9_902,
        "frontier_count": 16,
        "control_flow_oracle": "armv4t-raw-encoding",
        "errors": [],
    }:
        raise ValueError(f"independent frozen v3 verification failed: {report}")
    if (
        _sha(_safe_file(root, V2_VERIFIER_PATH).read_bytes()) != V2_VERIFIER_SHA256
        or _sha(_safe_file(root, V3_VERIFIER_PATH).read_bytes())
        != V3_VERIFIER_SHA256
    ):
        raise ValueError("independent frozen CFG verifier identity changed")
    v2 = _load_bound_json(
        root,
        V2_ARTIFACT / V2_PAYLOAD_NAME,
        size=V2_PAYLOAD_SIZE,
        digest=V2_PAYLOAD_SHA256,
    )
    _load_bound_json(
        root,
        V2_ARTIFACT / "manifest.json",
        size=None,
        digest=V2_MANIFEST_SHA256,
    )
    v3 = _load_bound_json(
        root,
        V3_ARTIFACT / V3_PAYLOAD_NAME,
        size=V3_PAYLOAD_SIZE,
        digest=V3_PAYLOAD_SHA256,
    )
    _load_bound_json(
        root,
        V3_ARTIFACT / "manifest.json",
        size=None,
        digest=V3_MANIFEST_SHA256,
    )
    expected_rom = {
        "path": ROM_PATH.as_posix(),
        "size": len(rom),
        "sha256": ROM_SHA256,
    }
    if (
        v2.get("schema") != V2_SCHEMA
        or v2.get("rom") != expected_rom
        or v2.get("graph_denominator_sha256") != V2_GRAPH_SHA256
        or v3.get("schema") != V3_SCHEMA
        or v3.get("rom") != expected_rom
        or v3.get("graph_denominator_sha256") != V3_GRAPH_SHA256
        or v3.get("base_cfg", {}).get("graph_denominator_sha256")
        != V2_GRAPH_SHA256
    ):
        raise ValueError("independent frozen v2/v3 CFG contract changed")
    return v2, v3


def _baseline_record(payload: dict[str, Any], *, version: str) -> dict[str, Any]:
    if version == "v2":
        return {
            "path": V2_ARTIFACT.as_posix(),
            "schema": V2_SCHEMA,
            "manifest_sha256": V2_MANIFEST_SHA256,
            "payload_file": V2_PAYLOAD_NAME,
            "payload_size": V2_PAYLOAD_SIZE,
            "payload_sha256": V2_PAYLOAD_SHA256,
            "verifier_path": V2_VERIFIER_PATH.as_posix(),
            "verifier_sha256": V2_VERIFIER_SHA256,
            "graph_denominator_sha256": V2_GRAPH_SHA256,
            "summary": payload["summary"],
        }
    return {
        "path": V3_ARTIFACT.as_posix(),
        "schema": V3_SCHEMA,
        "manifest_sha256": V3_MANIFEST_SHA256,
        "payload_file": V3_PAYLOAD_NAME,
        "payload_size": V3_PAYLOAD_SIZE,
        "payload_sha256": V3_PAYLOAD_SHA256,
        "verifier_path": V3_VERIFIER_PATH.as_posix(),
        "verifier_sha256": V3_VERIFIER_SHA256,
        "graph_denominator_sha256": V3_GRAPH_SHA256,
        "summary": payload["combined_summary"],
    }


def _entry_order(item: tuple[str, int]) -> tuple[int, int, str]:
    return item[1], 0 if item[0] == "arm" else 1, item[0]


def _occupied_bytes(entries: dict[tuple[str, int], dict[str, Any]]) -> set[int]:
    return {
        byte
        for (_, offset), decoded in entries.items()
        for byte in range(offset, offset + decoded["size"])
    }


def _owner_map(
    blocks: list[dict[str, Any]],
    entries: dict[tuple[str, int], dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
    owner: dict[tuple[str, int], dict[str, Any]] = {}
    for block in blocks:
        mode = block["mode"]
        offset, end = block["range"]
        while offset < end:
            key = (mode, offset)
            decoded = entries.get(key)
            if decoded is None or key in owner:
                raise ValueError("independent baseline block ownership changed")
            owner[key] = block
            offset += decoded["size"]
        if offset != end:
            raise ValueError("independent baseline block boundary changed")
    if set(owner) != set(entries):
        raise ValueError("independent baseline instruction ownership changed")
    return owner


def _verified_baseline_entries(
    rom: bytes, v2: dict[str, Any], v3: dict[str, Any]
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    _, _, _, v2_entries = _verify_blocks(rom, v2.get("blocks"))
    _, _, _, v3_entries = _verify_blocks(
        rom, v3.get("extension", {}).get("blocks")
    )
    if len(v2_entries) != 40_872 or len(v3_entries) != 4_698:
        raise ValueError("independent frozen CFG instruction denominator changed")
    if set(v2_entries) & set(v3_entries):
        raise ValueError("independent frozen v2/v3 instruction entries overlap")
    return (
        v2_entries,
        v3_entries,
        _owner_map(v2["blocks"], v2_entries),
        _owner_map(v3["extension"]["blocks"], v3_entries),
    )


def _assert_nonoverlapping_entries(
    entries: dict[tuple[str, int], dict[str, Any]]
) -> None:
    for mode in ("arm", "thumb"):
        previous_end = -1
        for entry_mode, offset in sorted(entries, key=_entry_order):
            if entry_mode != mode:
                continue
            if offset < previous_end:
                raise ValueError(
                    f"independent overlapping {mode} decode at 0x{offset:06X}"
                )
            previous_end = offset + entries[(entry_mode, offset)]["size"]


def _rebuild_delta(
    rom: bytes,
    roots: list[dict[str, Any]],
    v2_entries: dict[tuple[str, int], dict[str, Any]],
    v3_entries: dict[tuple[str, int], dict[str, Any]],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    list[tuple[tuple[str, int], str, str, tuple[str, int]]],
]:
    baseline_entries = {**v2_entries, **v3_entries}
    baseline_occupied = _occupied_bytes(baseline_entries)
    pending: list[tuple[int, int, str]] = []
    scheduled: set[tuple[str, int]] = set()
    for root in roots:
        item = (root["mode"], root["file_offset"])
        if item in baseline_entries or item[1] in baseline_occupied:
            raise ValueError("independent root overlaps the frozen CFG baseline")
        heapq.heappush(pending, _entry_order(item))
        scheduled.add(item)
    entries: dict[tuple[str, int], dict[str, Any]] = {}
    rejected: set[tuple[str, int]] = set()
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]] = []
    scheduled_limit = len(scheduled) + 2 * MAX_INSTRUCTION_COUNT
    while pending:
        offset, _, mode = heapq.heappop(pending)
        item = (mode, offset)
        if item in entries or item in rejected:
            continue
        if offset in baseline_occupied:
            raise ValueError("independent worklist entered a frozen baseline byte")
        decoded = _decode(rom, offset, mode)
        if not decoded["accepted"]:
            rejected.add(item)
            continue
        if any(
            byte in baseline_occupied
            for byte in range(offset, offset + decoded["size"])
        ):
            raise ValueError("independent instruction overlaps frozen baseline bytes")
        if len(entries) >= MAX_INSTRUCTION_COUNT:
            raise ValueError("independent proven-root instruction budget exhausted")
        entries[item] = decoded
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            if target in v2_entries:
                crosses.append((item, edge["kind"], "v2", target))
                continue
            if target in v3_entries:
                crosses.append((item, edge["kind"], "v3", target))
                continue
            if target[1] in baseline_occupied:
                raise ValueError(
                    "independent successor targets the middle of a baseline instruction"
                )
            if target not in scheduled:
                if len(scheduled) >= scheduled_limit:
                    raise ValueError("independent proven-root schedule budget exhausted")
                heapq.heappush(pending, _entry_order(target))
                scheduled.add(target)
    _assert_nonoverlapping_entries(entries)
    return entries, crosses


def _block_reference(
    owner: dict[tuple[str, int], dict[str, Any]],
    target: tuple[str, int],
    label: str,
) -> dict[str, Any]:
    block = owner.get(target)
    if block is None:
        raise ValueError(f"independent {label} cross target has no owning block")
    return {
        "baseline_artifact": label,
        "block_id": block["id"],
        "instruction_offset": target[1],
        "mode": target[0],
    }


def _simple_cross_vector(
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]],
) -> list[dict[str, Any]]:
    vector = [
        {
            "source": {"mode": source[0], "file_offset": source[1]},
            "edge_kind": kind,
            "baseline": baseline,
            "target": {"mode": target[0], "file_offset": target[1]},
        }
        for source, kind, baseline, target in crosses
    ]
    vector.sort(
        key=lambda item: (
            item["source"]["file_offset"],
            item["source"]["mode"],
            item["edge_kind"],
            item["target"]["file_offset"],
            item["target"]["mode"],
        )
    )
    return vector


def _cross_records(
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]],
    source_blocks: dict[tuple[str, int], str],
    v2_owner: dict[tuple[str, int], dict[str, Any]],
    v3_owner: dict[tuple[str, int], dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    simple = _simple_cross_vector(crosses)
    records = []
    for item in simple:
        source = (item["source"]["mode"], item["source"]["file_offset"])
        target = (item["target"]["mode"], item["target"]["file_offset"])
        records.append(
            {
                "source": {
                    "block_id": source_blocks[source],
                    "instruction_offset": source[1],
                    "edge_kind": item["edge_kind"],
                },
                "target": _block_reference(
                    v2_owner if item["baseline"] == "v2" else v3_owner,
                    target,
                    item["baseline"],
                ),
            }
        )
    return records, simple


def _expected_frontiers_and_crosses(
    rom: bytes,
    blocks: list[dict[str, Any]],
    decoded_last: list[dict[str, Any]],
    block_entries: dict[tuple[str, int], dict[str, Any]],
    instruction_entries: dict[tuple[str, int], dict[str, Any]],
    v2_entries: dict[tuple[str, int], dict[str, Any]],
    v3_entries: dict[tuple[str, int], dict[str, Any]],
    v2_owner: dict[tuple[str, int], dict[str, Any]],
    v3_owner: dict[tuple[str, int], dict[str, Any]],
    roots: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    baseline_occupied = _occupied_bytes({**v2_entries, **v3_entries})
    frontier_records = []
    crosses: list[tuple[tuple[str, int], str, str, tuple[str, int]]] = []
    source_blocks: dict[tuple[str, int], str] = {}
    for block, decoded in zip(blocks, decoded_last, strict=True):
        expected_successors = []
        source = (decoded["mode"], decoded["file_offset"])
        source_blocks[source] = block["id"]
        for edge in decoded["successors"]:
            target = (edge["mode"], edge["file_offset"])
            target_block = block_entries.get(target)
            if target_block is not None:
                expected_successors.append({**edge, "block_id": target_block["id"]})
                continue
            if target in v2_entries:
                crosses.append((source, edge["kind"], "v2", target))
                continue
            if target in v3_entries:
                crosses.append((source, edge["kind"], "v3", target))
                continue
            if target[1] in baseline_occupied:
                raise ValueError(
                    "independent artifact successor enters a baseline instruction"
                )
            if target in instruction_entries:
                raise ValueError(
                    f"independent successor is not a block start at 0x{target[1]:06X}"
                )
            rejected = _decode(rom, target[1], target[0])
            if rejected["accepted"]:
                raise ValueError(
                    f"independent artifact omits successor at 0x{target[1]:06X}"
                )
            frontier_records.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": source[1],
                        "edge_kind": edge["kind"],
                    },
                    "reason": rejected["frontier_reason"],
                    "target": {"mode": target[0], "file_offset": target[1]},
                }
            )
        if block.get("successors") != expected_successors:
            raise ValueError(f"independent block successors changed: {block['id']}")
        for frontier in decoded["frontiers"]:
            frontier_records.append(
                {
                    "source": {
                        "kind": "block",
                        "block_id": block["id"],
                        "instruction_offset": source[1],
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
            raise ValueError(f"independent root is not a block start: {root['root_id']}")
        frontier_records.append(
            {
                "source": {"kind": "root", "root_id": root["root_id"]},
                "reason": rejected["frontier_reason"],
                "target": {"mode": key[0], "file_offset": key[1]},
            }
        )
    frontier_records.sort(
        key=lambda value: json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    )
    frontiers = [
        {"id": f"frontier-{index:06d}", **record}
        for index, record in enumerate(frontier_records)
    ]
    cross_records, cross_vector = _cross_records(
        crosses, source_blocks, v2_owner, v3_owner
    )
    return frontiers, cross_records, cross_vector


def _extension_summary(
    blocks: list[dict[str, Any]], frontiers: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": sum(
            block["instruction_count"] for block in blocks
        ),
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(
            sorted(Counter(item["reason"] for item in frontiers).items())
        ),
        "reachable_instruction_bytes": _union_bytes(
            [tuple(block["range"]) for block in blocks]
        ),
    }


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            _safe_file(root, "tools/export_rom_cfg_proven_roots.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            _safe_file(root, "tools/verify_rom_cfg_proven_roots.py").read_bytes()
        ),
        "test_sha256": _sha(
            _safe_file(root, "tests/test_export_rom_cfg_proven_roots.py").read_bytes()
        ),
    }


def verify_rom_cfg_proven_roots(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    rebuilt_count = 0
    summary: dict[str, Any] = {}
    root_count = 0
    cross_count = 0
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        resolved_artifact = artifact.resolve(strict=True)
        if resolved_artifact != artifact or not artifact.is_dir():
            raise ValueError("CFG proven-root artifact uses a symlink or is not a directory")
        members = list(artifact.iterdir())
        if (
            {member.name for member in members} != {"manifest.json", PAYLOAD_NAME}
            or any(member.is_symlink() or not member.is_file() for member in members)
        ):
            raise ValueError("CFG proven-root artifact file set changed")

        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        producers = _producer_denominator(root, rom)
        root_seeds = _root_seeds(rom)
        v2, v3 = _baseline_contract(root, rom)
        v2_entries, v3_entries, v2_owner, v3_owner = _verified_baseline_entries(
            rom, v2, v3
        )
        rebuilt_entries, rebuilt_crosses = _rebuild_delta(
            rom, root_seeds, v2_entries, v3_entries
        )
        rebuilt_count = len(rebuilt_entries)

        payload_path = artifact / PAYLOAD_NAME
        payload_raw = payload_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        expected_baseline = {
            "v2": _baseline_record(v2, version="v2"),
            "v3": _baseline_record(v3, version="v3"),
        }
        expected_decoder = _decoder_identity(root)
        expected_limits = {
            "max_instruction_count": MAX_INSTRUCTION_COUNT,
            "max_basic_block_instruction_count": MAX_BLOCK_INSTRUCTION_COUNT,
            "decode_window_bytes": 4,
        }
        if set(payload) != {
            "schema",
            "rom",
            "frozen_baseline",
            "decoder",
            "limits",
            "producer_denominator",
            "root_denominator_sha256",
            "roots",
            "extension",
            "graph_denominator_sha256",
            "implementation",
            "scope",
            "limitations",
        }:
            raise ValueError("CFG proven-root top-level field set changed")
        if (
            payload.get("schema") != SCHEMA
            or payload.get("rom")
            != {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
            or payload.get("frozen_baseline") != expected_baseline
            or payload.get("decoder") != expected_decoder
            or payload.get("limits") != expected_limits
            or payload.get("producer_denominator") != producers
            or payload.get("root_denominator_sha256") != ROOT_VECTOR_SHA256
            or payload.get("scope") != SCOPE
            or payload.get("limitations") != LIMITATIONS
        ):
            raise ValueError("CFG proven-root top-level contract changed")

        extension = payload.get("extension")
        if not isinstance(extension, dict) or set(extension) != {
            "blocks",
            "frontiers",
            "frontier_denominator_sha256",
            "baseline_cross_edges",
            "cross_edge_denominator_sha256",
            "cross_edge_summary",
            "summary",
        }:
            raise ValueError("CFG proven-root extension field set changed")
        blocks = extension["blocks"]
        decoded_last, block_entries, by_id, artifact_entries = _verify_blocks(
            rom, blocks
        )
        if set(artifact_entries) != set(rebuilt_entries):
            missing = sorted(set(rebuilt_entries) - set(artifact_entries), key=_entry_order)[
                :8
            ]
            unexpected = sorted(
                set(artifact_entries) - set(rebuilt_entries), key=_entry_order
            )[:8]
            raise ValueError(
                "CFG proven-root closure differs from independent worklist: "
                f"missing={missing}, unexpected={unexpected}"
            )
        roots = payload.get("roots")
        if not isinstance(roots, list) or len(roots) != 2:
            raise ValueError("CFG proven-root root denominator changed")
        root_count = len(roots)
        frontiers, cross_records, cross_vector = _expected_frontiers_and_crosses(
            rom,
            blocks,
            decoded_last,
            block_entries,
            artifact_entries,
            v2_entries,
            v3_entries,
            v2_owner,
            v3_owner,
            roots,
        )
        if extension.get("frontiers") != frontiers:
            raise ValueError("CFG proven-root frontier denominator changed")
        if extension.get("baseline_cross_edges") != cross_records:
            raise ValueError("CFG proven-root baseline cross edges changed")
        if _simple_cross_vector(rebuilt_crosses) != cross_vector:
            raise ValueError("CFG proven-root independent cross-edge closure changed")
        if _canonical_sha(frontiers) != FRONTIER_VECTOR_SHA256:
            raise ValueError("CFG proven-root frontier canonical vector changed")
        if _canonical_sha(cross_vector) != CROSS_EDGE_VECTOR_SHA256:
            raise ValueError("CFG proven-root cross-edge canonical vector changed")
        if (
            extension.get("frontier_denominator_sha256") != FRONTIER_VECTOR_SHA256
            or extension.get("cross_edge_denominator_sha256")
            != CROSS_EDGE_VECTOR_SHA256
        ):
            raise ValueError("CFG proven-root vector hash binding changed")

        expected_roots = _expected_roots(
            root_seeds, block_entries, by_id, frontiers
        )
        if roots != expected_roots:
            raise ValueError("CFG proven-root per-root summaries changed")
        summary = _extension_summary(blocks, frontiers)
        pinned_summary = {
            "decoded_basic_block_count": 1_203,
            "decoded_instruction_count": 6_166,
            "frontier_count": 28,
            "frontier_reasons": {
                "decode_failure": 1,
                "indirect_pc_target": 27,
            },
            "reachable_instruction_bytes": 12_966,
        }
        if summary != pinned_summary or extension.get("summary") != summary:
            raise ValueError(f"CFG proven-root extension summary changed: {summary}")
        by_baseline = dict(
            sorted(Counter(item["baseline"] for item in cross_vector).items())
        )
        by_kind = dict(
            sorted(Counter(item["edge_kind"] for item in cross_vector).items())
        )
        expected_cross_summary = {
            "count": len(cross_vector),
            "by_baseline": by_baseline,
            "by_kind": by_kind,
        }
        if expected_cross_summary != {
            "count": 259,
            "by_baseline": {"v2": 256, "v3": 3},
            "by_kind": {"branch_target": 3, "call_target": 256},
        } or extension.get("cross_edge_summary") != expected_cross_summary:
            raise ValueError("CFG proven-root cross-edge summary changed")
        cross_count = len(cross_vector)
        expected_extension = {
            "blocks": blocks,
            "frontiers": frontiers,
            "frontier_denominator_sha256": FRONTIER_VECTOR_SHA256,
            "baseline_cross_edges": cross_records,
            "cross_edge_denominator_sha256": CROSS_EDGE_VECTOR_SHA256,
            "cross_edge_summary": expected_cross_summary,
            "summary": summary,
        }
        if extension != expected_extension:
            raise ValueError("CFG proven-root extension contains unexpected values")
        denominator = _canonical_sha(
            {
                "frozen_baseline": expected_baseline,
                "producer_denominator": producers,
                "root_denominator_sha256": ROOT_VECTOR_SHA256,
                "roots": expected_roots,
                "extension": expected_extension,
                "scope": SCOPE,
            }
        )
        if payload.get("graph_denominator_sha256") != denominator:
            raise ValueError("CFG proven-root graph denominator changed")
        expected_implementation = _implementation(root)
        if payload.get("implementation") != expected_implementation:
            raise ValueError("CFG proven-root implementation binding changed")
        expected_manifest = {
            "artifact_schema": SCHEMA,
            "rom": payload["rom"],
            "frozen_baseline": expected_baseline,
            "decoder": expected_decoder,
            "limits": expected_limits,
            "producer_summary": {
                "count": len(producers["producers"]),
                "denominator_sha256": producers["denominator_sha256"],
            },
            "root_count": len(expected_roots),
            "root_denominator_sha256": ROOT_VECTOR_SHA256,
            "extension_summary": summary,
            "cross_edge_summary": expected_cross_summary,
            "graph_denominator_sha256": denominator,
            "files": {
                PAYLOAD_NAME: {
                    "size": len(payload_raw),
                    "sha256": _sha(payload_raw),
                }
            },
            "implementation": expected_implementation,
            "scope": SCOPE,
        }
        if manifest != expected_manifest:
            raise ValueError("CFG proven-root promotion manifest changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": rebuilt_count,
        "root_count": root_count,
        "decoded_instruction_count": summary.get("decoded_instruction_count", 0),
        "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0),
        "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0),
        "frontier_count": summary.get("frontier_count", 0),
        "baseline_cross_edge_count": cross_count,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/rom-cfg-proven-roots-v1"),
    )
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_rom_cfg_proven_roots(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
