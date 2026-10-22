#!/usr/bin/env python3
"""Export CFG roots proven by two fixed Thumb dispatcher tables."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "tools/_vendor"
for import_root in (PROJECT_ROOT, VENDOR_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.export_rom_cfg_inventory import (
    ROM_PATH, ROM_SHA256, _assert_nonoverlapping_nodes, _build_blocks,
    _canonical_json, _canonical_sha, _frontier_records, _root_results,
    _safe_file, _replace_output_dir, _reject_symlink_components,
)
from tools.export_rom_cfg_proven_roots import _nodes_from_blocks
from tools.export_rom_cfg_proven_roots_v2 import (
    _baseline_contract, _baseline_nodes, _cross_edge_records, _traverse_delta,
)
from tools.export_rom_cfg_proven_roots_v4 import _extension_summary, _load_payload
from tools.export_rom_cfg_proven_roots_v6 import ADDITIONAL_BASELINES

ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v7"
PAYLOAD_NAME = "rom-cfg-proven-roots-v7.json"
MANIFEST_NAME = "manifest.json"
V6_BASELINE = (
    "proven_roots_v6",
    "artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json",
    "e5b27a55c77cd1df4ac5ec39f2dd05735b0b53c01b7cbbcf1620db1681a3c3ec",
)
DISPATCHERS = (
    {
        "dispatcher_id": "byte-index-minus-one-0-to-6",
        "terminal_file_offset": 0x6E84E,
        "proof_range": [0x6E83A, 0x6E850],
        "proof_sha256": "c74238ef0b90b5f251a3bf71e9cf471a187efaa32836f8e83dc292a45f142e1d",
        "index_source": "ldrb; subs #1; cmp #6; unsigned bls",
        "index_min": 0,
        "index_max": 6,
        "literal_offset": 0x6E864,
        "literal_sha256": "e4fe803292766caeeed6856a18dafdeb481e3fb798997e76370e5fdb2b562ad5",
        "table_range": [0x6E868, 0x6E884],
        "table_sha256": "2e7c3a263cf6d6410dd741d4e2439fabbc106ccca78c781bab8cd95ad998cd5d",
    },
    {
        "dispatcher_id": "masked-halfword-minus-one-0-to-37",
        "terminal_file_offset": 0x92850,
        "proof_range": [0x9283A, 0x92852],
        "proof_sha256": "e06cfe149e1bba492025792d33bf40a809e9f33d7a87ed724f6369004a5e2493",
        "index_source": "ldrh; ands #0x3f; subs #1; cmp #0x25; unsigned bls",
        "index_min": 0,
        "index_max": 37,
        "literal_offset": 0x92860,
        "literal_sha256": "f7d1e641798891c3426b45d8cc074b1e2dcf24fe9c2dd48e3b48f891b5f19abc",
        "table_range": [0x92864, 0x928FC],
        "table_sha256": "c13ef2eee340bcd853e38930a8b9037439efdcc2eff9b471f75cbdeb2fa5785f",
    },
)
SCOPE = {
    "fixed_dispatcher_denominator_complete": True,
    "baseline_entries_treated_as_opaque": True,
    "runtime_reachability_complete": False,
    "global_indirect_target_denominator_complete": False,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dispatcher_denominator(rom: bytes) -> list[dict[str, Any]]:
    if len(rom) != ROM_SIZE:
        raise ValueError("unexpected ROM size")
    rows = []
    for spec in DISPATCHERS:
        start, end = spec["proof_range"]
        table_start, table_end = spec["table_range"]
        literal = rom[spec["literal_offset"] : spec["literal_offset"] + 4]
        table = rom[table_start:table_end]
        if _sha(rom[start:end]) != spec["proof_sha256"]:
            raise ValueError("dispatcher proof bytes changed")
        if _sha(literal) != spec["literal_sha256"] or struct.unpack("<I", literal)[0] != ROM_BASE + table_start:
            raise ValueError("dispatcher literal changed")
        if _sha(table) != spec["table_sha256"]:
            raise ValueError("dispatcher table changed")
        targets = [struct.unpack_from("<I", table, offset)[0] - ROM_BASE for offset in range(0, len(table), 4)]
        if len(targets) != spec["index_max"] - spec["index_min"] + 1:
            raise ValueError("dispatcher index denominator changed")
        row = dict(spec)
        row["entry_count"] = len(targets)
        row["target_vector"] = targets
        rows.append(row)
    return rows


def _baselines(root: Path, rom: bytes):
    prior = _baseline_contract(root, rom)
    nodes, owners = _baseline_nodes(rom, prior)
    additions = []
    for label, path, digest in (*ADDITIONAL_BASELINES, V6_BASELINE):
        payload = _load_payload(root, Path(path), digest)
        current, current_owners = _nodes_from_blocks(rom, payload["extension"]["blocks"], label=label)
        nodes[label] = current
        owners[label] = current_owners
        additions.append((label, payload, digest))
    return prior, nodes, owners, additions


def _root_seeds(rom: bytes, baseline_nodes) -> list[dict[str, Any]]:
    dispatchers = _dispatcher_denominator(rom)
    baseline_entries = set().union(*(set(nodes) for nodes in baseline_nodes.values()))
    sources: dict[int, list[dict[str, Any]]] = {}
    for dispatcher in dispatchers:
        for index, target in enumerate(dispatcher["target_vector"]):
            sources.setdefault(target, []).append({"dispatcher_id": dispatcher["dispatcher_id"], "table_index": index})
    roots = []
    for offset in sorted(sources):
        if ("thumb", offset) in baseline_entries:
            continue
        raw = rom[offset:offset + 4]
        roots.append({
            "root_id": f"root-thumb-{offset:06x}", "mode": "thumb",
            "file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}",
            "entry_size": 4, "entry_sha256": _sha(raw), "sources": sources[offset],
        })
    if len(roots) != 8:
        raise ValueError("dispatcher delta-root denominator changed")
    return roots


def build_cfg_proven_roots_v7_payload(root: Path, rom: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes() if rom is None else rom
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    prior, baseline_nodes, baseline_owners, additions = _baselines(root, rom)
    dispatchers = _dispatcher_denominator(rom)
    roots = _root_seeds(rom, baseline_nodes)
    nodes, rejected, incoming, crosses = _traverse_delta(rom, roots, baseline_nodes)
    _assert_nonoverlapping_nodes(nodes)
    blocks, node_to_block = _build_blocks(rom, nodes, {("thumb", item["file_offset"]) for item in roots})
    frontiers = _frontier_records(nodes, rejected, incoming, roots, node_to_block)
    cross_records, cross_vector = _cross_edge_records(crosses, node_to_block, baseline_owners)
    frozen = {"v2": {"schema": prior["v2"]["schema"]}, "v3": {"schema": prior["v3"]["schema"]}, "proven_roots_v1": {"schema": prior["proven_roots_v1"]["schema"]}}
    for label, payload, digest in additions:
        frozen[label] = {"schema": payload["schema"], "payload_sha256": digest}
    return {
        "schema": SCHEMA,
        "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "frozen_baseline": frozen,
        "dispatcher_denominator": dispatchers,
        "roots": _root_results(roots, nodes, frontiers, node_to_block),
        "extension": {
            "blocks": blocks, "frontiers": frontiers,
            "baseline_cross_edges": cross_records,
            "cross_edge_denominator_sha256": _canonical_sha(cross_vector),
            "summary": _extension_summary(nodes, blocks, frontiers),
        },
        "scope": SCOPE,
    }


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    output = _reject_symlink_components(requested).resolve(strict=False)
    if output == root or output in root.parents:
        raise ValueError("CFG proven-root v7 output cannot be repository root or ancestor")
    if not output.exists():
        return output
    if not output.is_dir():
        raise ValueError("CFG proven-root v7 output must be a directory")
    members = list(output.iterdir())
    if members and ({item.name for item in members} != {MANIFEST_NAME, PAYLOAD_NAME} or any(item.is_symlink() or not item.is_file() for item in members)):
        raise ValueError("CFG proven-root v7 output is a foreign non-empty directory")
    return output


def export_rom_cfg_proven_roots_v7(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_v7_payload(root)
    raw = _canonical_json(payload)
    manifest = {
        "artifact_schema": SCHEMA, "rom": payload["rom"],
        "dispatcher_summary": {"count": 2, "entry_count": 45, "unique_target_count": 21},
        "root_count": 8, "extension_summary": payload["extension"]["summary"],
        "files": {PAYLOAD_NAME: {"size": len(raw), "sha256": _sha(raw)}},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-v7-", dir=output.parent))
    try:
        (temporary / PAYLOAD_NAME).write_bytes(raw)
        (temporary / MANIFEST_NAME).write_bytes(_canonical_json(manifest))
        _validate_output_dir(root, temporary)
        _replace_output_dir(output, temporary)
        return manifest
    finally:
        if temporary.exists(): shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    export_rom_cfg_proven_roots_v7(args.root, args.output_dir)
    return 0


if __name__ == "__main__": raise SystemExit(main())
