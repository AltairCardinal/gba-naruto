#!/usr/bin/env python3
"""Export the fixed direct-call-proven CFG root at ROM offset 0x070DF8."""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
from pathlib import Path
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
    _union_bytes,
)
from tools.export_rom_cfg_proven_roots import _nodes_from_blocks
from tools.export_rom_cfg_proven_roots_v2 import (
    _baseline_contract as _v2_baseline_contract,
    _baseline_nodes as _v2_baseline_nodes,
    _cross_edge_records,
    _traverse_delta,
)


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
EXPECTED_PRODUCERS = (
    (
        "target_confirmation",
        0x74192,
        "fcf731fe",
        "4fbf43b9ecefd5d5b2716fd51cf7cc4228f9fbcb4da14591b24d4d5205f60ffb",
        0x70DF8,
    ),
    (
        "technique_menu",
        0x74836,
        "fcf7dffa",
        "0b0580cb61c11e4c3481cef46a931018d0a41dff62568aa7465a62aa75e6d6c0",
        0x70DF8,
    ),
)

PROVEN_V2_PAYLOAD = Path(
    "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json"
)
PROVEN_V2_PAYLOAD_SHA256 = (
    "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"
)
CONTROLLER_PAYLOAD = Path(
    "artifacts/rom-battle-controller-cfg-v1/rom-battle-controller-cfg.json"
)
CONTROLLER_PAYLOAD_SHA256 = (
    "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"
)
SCHEMA = "rom-cfg-proven-roots-v3"
PAYLOAD_NAME = "rom-cfg-proven-roots-v3.json"
MANIFEST_NAME = "manifest.json"


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
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_thumb_bl(offset, first, second)
        if target == 0x70DF8:
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
            "targets": [0x70DF8],
            "matching_producer_count": len(producers),
        },
        "producers": producers,
    }


def _root_seeds(rom: bytes) -> list[dict[str, Any]]:
    denominator = _producer_denominator(rom)
    offset = 0x70DF8
    raw = rom[offset : offset + 4]
    if raw.hex() != "f0b55746" or _sha(raw) != (
        "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
    ):
        raise ValueError("direct-call-proven root bytes changed")
    return [
        {
            "root_id": "root-thumb-070df8",
            "mode": "thumb",
            "file_offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}",
            "entry_size": len(raw),
            "entry_sha256": _sha(raw),
            "sources": [
                {"producer_id": item["producer_id"]}
                for item in denominator["producers"]
            ],
        }
    ]


def _load_payload(root: Path, path: Path, digest: str) -> dict[str, Any]:
    raw = _safe_file(root, path).read_bytes()
    if _sha(raw) != digest:
        raise ValueError(f"frozen CFG artifact identity changed: {path}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"frozen CFG artifact is not an object: {path}")
    return payload


def _extension_summary(
    nodes: dict[tuple[str, int], dict[str, Any]],
    blocks: list[dict[str, Any]],
    frontiers: list[dict[str, Any]],
) -> dict[str, Any]:
    from collections import Counter

    return {
        "decoded_basic_block_count": len(blocks),
        "decoded_instruction_count": len(nodes),
        "frontier_count": len(frontiers),
        "frontier_reasons": dict(
            sorted(Counter(item["reason"] for item in frontiers).items())
        ),
        "reachable_instruction_bytes": _union_bytes(
            [(offset, offset + node["size"]) for (_, offset), node in nodes.items()]
        ),
    }


def build_cfg_proven_roots_v3_payload(
    root: Path, rom: bytes | None = None
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    if rom is None:
        rom = _safe_file(root, ROM_PATH).read_bytes()
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    producers = _producer_denominator(rom)
    roots = _root_seeds(rom)

    prior = _v2_baseline_contract(root, rom)
    baseline_nodes, baseline_owners = _v2_baseline_nodes(rom, prior)
    proven_v2 = _load_payload(
        root, PROVEN_V2_PAYLOAD, PROVEN_V2_PAYLOAD_SHA256
    )
    controller = _load_payload(
        root, CONTROLLER_PAYLOAD, CONTROLLER_PAYLOAD_SHA256
    )
    expected_rom = {
        "path": ROM_PATH.as_posix(),
        "size": len(rom),
        "sha256": ROM_SHA256,
    }
    if (
        proven_v2.get("schema") != "rom-cfg-proven-roots-v2"
        or proven_v2.get("rom") != expected_rom
        or controller.get("schema") != "rom-battle-controller-cfg-v1"
        or controller.get("rom") != expected_rom
    ):
        raise ValueError("new frozen CFG baseline contract changed")
    for label, payload in (
        ("proven_roots_v2", proven_v2),
        ("battle_controller", controller),
    ):
        nodes, owners = _nodes_from_blocks(
            rom, payload["extension"]["blocks"], label=label
        )
        baseline_nodes[label] = nodes
        baseline_owners[label] = owners
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
    frontiers = _frontier_records(
        nodes, rejected, incoming, roots, node_to_block
    )
    root_results = _root_results(
        roots, nodes, frontiers, node_to_block
    )
    cross_records, cross_vector = _cross_edge_records(
        crosses, node_to_block, baseline_owners
    )
    summary = _extension_summary(nodes, blocks, frontiers)
    frozen = {
        "v2": {"schema": prior["v2"]["schema"]},
        "v3": {"schema": prior["v3"]["schema"]},
        "proven_roots_v1": {"schema": prior["proven_roots_v1"]["schema"]},
        "proven_roots_v2": {
            "schema": proven_v2["schema"],
            "payload_sha256": PROVEN_V2_PAYLOAD_SHA256,
        },
        "battle_controller": {
            "schema": controller["schema"],
            "payload_sha256": CONTROLLER_PAYLOAD_SHA256,
        },
    }
    scope = {
        "fixed_direct_producer_denominator_complete": True,
        "baseline_entries_treated_as_opaque": True,
        "runtime_reachability_complete": False,
        "global_function_entry_denominator_complete": False,
    }
    extension = {
        "blocks": blocks,
        "frontiers": frontiers,
        "baseline_cross_edges": cross_records,
        "cross_edge_denominator_sha256": _canonical_sha(cross_vector),
        "summary": summary,
    }
    return {
        "schema": SCHEMA,
        "rom": expected_rom,
        "frozen_baseline": frozen,
        "producer_denominator": producers,
        "roots": root_results,
        "extension": extension,
        "scope": scope,
    }


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    requested = _reject_symlink_components(requested)
    target = requested.resolve(strict=False)
    if target == root or target in root.parents:
        raise ValueError("CFG proven-root v3 output cannot be repository root or ancestor")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("CFG proven-root v3 output must be a directory")
    allowed = {MANIFEST_NAME, PAYLOAD_NAME}
    members = list(target.iterdir())
    if members and (
        {member.name for member in members} != allowed
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError("CFG proven-root v3 output is a foreign non-empty directory")
    return target


def export_rom_cfg_proven_roots_v3(
    root: Path, output_dir: Path
) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_v3_payload(root)
    payload_raw = _canonical_json(payload)
    manifest = {
        "artifact_schema": SCHEMA,
        "rom": payload["rom"],
        "producer_summary": {
            "count": len(payload["producer_denominator"]["producers"]),
        },
        "root_count": len(payload["roots"]),
        "extension_summary": payload["extension"]["summary"],
        "files": {
            PAYLOAD_NAME: {
                "size": len(payload_raw),
                "sha256": _sha(payload_raw),
            }
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-v3-", dir=output.parent)
    )
    try:
        (temporary / PAYLOAD_NAME).write_bytes(payload_raw)
        (temporary / MANIFEST_NAME).write_bytes(_canonical_json(manifest))
        _validate_output_dir(root, temporary)
        _replace_output_dir(output, temporary)
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
