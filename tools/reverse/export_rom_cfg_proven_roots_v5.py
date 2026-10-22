#!/usr/bin/env python3
"""Define the fixed direct-call producers for three post-controller CFG roots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any

from tools.export_rom_cfg_inventory import (
    ROM_PATH,
    ROM_SHA256,
    _assert_nonoverlapping_nodes,
    _build_blocks,
    _canonical_sha,
    _canonical_json,
    _frontier_records,
    _root_results,
    _safe_file,
    _reject_symlink_components,
    _replace_output_dir,
)
from tools.export_rom_cfg_proven_roots import _nodes_from_blocks
from tools.export_rom_cfg_proven_roots_v2 import (
    _baseline_contract,
    _baseline_nodes,
    _cross_edge_records,
    _traverse_delta,
)
from tools.export_rom_cfg_proven_roots_v4 import _extension_summary, _load_payload


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
EXPECTED_PRODUCERS = (
    ("controller_0736de", 0x736DE, "faf753fc", "11c1d558cc3d306461a7b96ff055ebd96e7b78ad8e231497a5b37d2ee6563ba7", 0x6DF88),
    ("controller_073702", 0x73702, "16f017ff", "eddfa1a1291ea98d03e747a52a41eb926ca60874cd971ec8c84625c55d819c33", 0x8A534),
    ("controller_073780", 0x73780, "16f002ff", "b5c297eb55c167faafefc7f5eea59d0a4d6e8819e4e65bdbcfbe0c58f80ac827", 0x8A588),
)
EXPECTED_ROOTS = (
    (0x6DF88, "f0b55746", "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"),
    (0x8A534, "10b50006", "632f748fa2c479a8999dc26d67611c8121df226794205f4f8951ffd2b851d89c"),
    (0x8A588, "70b582b0", "737d21ab96d81780dcfdb407fe8c753b445433b5edeb879afa1e28f29e847bbf"),
)
SCHEMA = "rom-cfg-proven-roots-v5"
PAYLOAD_NAME = "rom-cfg-proven-roots-v5.json"
MANIFEST_NAME = "manifest.json"
ADDITIONAL_BASELINES = (
    ("proven_roots_v2", "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json", "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"),
    ("battle_controller", "artifacts/rom-battle-controller-cfg-v1/rom-battle-controller-cfg.json", "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"),
    ("proven_roots_v3", "artifacts/rom-cfg-proven-roots-v3/rom-cfg-proven-roots-v3.json", "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2"),
    ("proven_roots_v4", "artifacts/rom-cfg-proven-roots-v4/rom-cfg-proven-roots-v4.json", "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb"),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE:
        raise ValueError(f"unexpected ROM size: {len(rom)}")
    targets = {item[4] for item in EXPECTED_PRODUCERS}
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_thumb_bl(offset, first, second)
        if target in targets:
            actual.append((offset, target))
    expected = [(item[1], item[4]) for item in EXPECTED_PRODUCERS]
    if actual != expected:
        raise ValueError(
            f"direct-call producer denominator changed: {actual!r} != {expected!r}"
        )
    producers = []
    for producer_id, offset, raw_hex, digest, target in EXPECTED_PRODUCERS:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError(f"direct-call producer bytes changed at 0x{offset:06X}")
        producers.append(
            {
                "producer_id": producer_id,
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "raw_hex": raw_hex,
                "bytes_sha256": digest,
                "target_file_offset": target,
                "target_gba_address": f"0x{ROM_BASE + target:08X}",
            }
        )
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "targets": sorted(targets),
            "matching_producer_count": len(producers),
        },
        "producers": producers,
    }


def _root_seeds(rom: bytes) -> list[dict[str, Any]]:
    producers = _producer_denominator(rom)["producers"]
    by_target = {item["target_file_offset"]: item for item in producers}
    roots = []
    for offset, raw_hex, digest in EXPECTED_ROOTS:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError(f"direct-call-proven root bytes changed at 0x{offset:06X}")
        roots.append(
            {
                "root_id": f"root-thumb-{offset:06x}",
                "mode": "thumb",
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "entry_size": 4,
                "entry_sha256": digest,
                "sources": [{"producer_id": by_target[offset]["producer_id"]}],
            }
        )
    return roots


def build_cfg_proven_roots_v5_payload(
    root: Path, rom: bytes | None = None
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    producers = _producer_denominator(rom)
    roots = _root_seeds(rom)
    prior = _baseline_contract(root, rom)
    baseline_nodes, baseline_owners = _baseline_nodes(rom, prior)
    additions = []
    for label, path, digest in ADDITIONAL_BASELINES:
        payload = _load_payload(root, Path(path), digest)
        nodes, owners = _nodes_from_blocks(
            rom, payload["extension"]["blocks"], label=label
        )
        baseline_nodes[label] = nodes
        baseline_owners[label] = owners
        additions.append((label, payload, digest))
    occupied: set[int] = set()
    for label, nodes in baseline_nodes.items():
        current = {
            byte
            for (_, offset), node in nodes.items()
            for byte in range(offset, offset + node["size"])
        }
        if occupied & current:
            raise ValueError(f"frozen CFG baseline bytes overlap at {label}")
        occupied.update(current)
    nodes, rejected, incoming, crosses = _traverse_delta(
        rom, roots, baseline_nodes
    )
    _assert_nonoverlapping_nodes(nodes)
    blocks, node_to_block = _build_blocks(
        rom, nodes, {(item["mode"], item["file_offset"]) for item in roots}
    )
    frontiers = _frontier_records(nodes, rejected, incoming, roots, node_to_block)
    cross_records, cross_vector = _cross_edge_records(
        crosses, node_to_block, baseline_owners
    )
    frozen = {
        "v2": {"schema": prior["v2"]["schema"]},
        "v3": {"schema": prior["v3"]["schema"]},
        "proven_roots_v1": {"schema": prior["proven_roots_v1"]["schema"]},
    }
    for label, payload, digest in additions:
        frozen[label] = {"schema": payload["schema"], "payload_sha256": digest}
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "frozen_baseline": frozen,
        "producer_denominator": producers,
        "roots": _root_results(roots, nodes, frontiers, node_to_block),
        "extension": {
            "blocks": blocks,
            "frontiers": frontiers,
            "baseline_cross_edges": cross_records,
            "cross_edge_denominator_sha256": _canonical_sha(cross_vector),
            "summary": _extension_summary(nodes, blocks, frontiers),
        },
        "scope": {
            "fixed_direct_producer_denominator_complete": True,
            "baseline_entries_treated_as_opaque": True,
            "runtime_reachability_complete": False,
            "global_function_entry_denominator_complete": False,
        },
    }


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    target = _reject_symlink_components(requested).resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("CFG proven-root v5 output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("CFG proven-root v5 output must be a directory")
    members = list(target.iterdir())
    if members and (
        {member.name for member in members} != {MANIFEST_NAME, PAYLOAD_NAME}
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError("CFG proven-root v5 output is a foreign non-empty directory")
    return target


def export_rom_cfg_proven_roots_v5(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_v5_payload(root)
    payload_raw = _canonical_json(payload)
    manifest = {
        "artifact_schema": SCHEMA,
        "rom": payload["rom"],
        "producer_summary": {"count": 3},
        "root_count": 3,
        "extension_summary": payload["extension"]["summary"],
        "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _sha(payload_raw)}},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-v5-", dir=output.parent))
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        (temporary / MANIFEST_NAME).write_bytes(_canonical_json(manifest))
        _validate_output_dir(root, temporary)
        _replace_output_dir(output, temporary)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
