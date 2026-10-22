#!/usr/bin/env python3
"""Independently verify the three direct-call-proven v5 CFG roots."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
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
    ROM_PATH, ROM_SHA256, _canonical_sha, _expected_roots, _safe_file, _verify_blocks,
)
from tools.verify_rom_cfg_proven_roots_v2 import (
    _expected_frontiers_and_crosses, _extension_summary, _owner_map,
    _rebuild_delta, _simple_cross_vector,
)
from tools.verify_rom_cfg_proven_roots_v3 import _all_baselines

ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v5"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v5"
PAYLOAD_NAME = "rom-cfg-proven-roots-v5.json"
V4_PAYLOAD = Path("artifacts/rom-cfg-proven-roots-v4/rom-cfg-proven-roots-v4.json")
V4_SHA = "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb"
PRODUCERS = (
    ("controller_0736de", 0x736DE, "faf753fc", "11c1d558cc3d306461a7b96ff055ebd96e7b78ad8e231497a5b37d2ee6563ba7", 0x6DF88),
    ("controller_073702", 0x73702, "16f017ff", "eddfa1a1291ea98d03e747a52a41eb926ca60874cd971ec8c84625c55d819c33", 0x8A534),
    ("controller_073780", 0x73780, "16f002ff", "b5c297eb55c167faafefc7f5eea59d0a4d6e8819e4e65bdbcfbe0c58f80ac827", 0x8A588),
)
ROOTS = (
    (0x6DF88, "f0b55746", "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"),
    (0x8A534, "10b50006", "632f748fa2c479a8999dc26d67611c8121df226794205f4f8951ffd2b851d89c"),
    (0x8A588, "70b582b0", "737d21ab96d81780dcfdb407fe8c753b445433b5edeb879afa1e28f29e847bbf"),
)
SCOPE = {
    "fixed_direct_producer_denominator_complete": True,
    "baseline_entries_treated_as_opaque": True,
    "runtime_reachability_complete": False,
    "global_function_entry_denominator_complete": False,
}

def _digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()

def _decode_bl(o: int, a: int, b: int) -> int | None:
    if a & 0xF800 != 0xF000 or b & 0xF800 != 0xF800: return None
    d = ((a & 0x7FF) << 12) | ((b & 0x7FF) << 1)
    if d & 0x400000: d -= 0x800000
    return o + 4 + d

def _producers(rom: bytes) -> dict[str, Any]:
    targets = {x[4] for x in PRODUCERS}; actual = []
    for o in range(0, len(rom) - 3, 2):
        a, b = struct.unpack_from("<HH", rom, o); target = _decode_bl(o, a, b)
        if target in targets: actual.append((o, target))
    if actual != [(x[1], x[4]) for x in PRODUCERS]:
        raise ValueError("independent producer denominator changed")
    rows = []
    for pid, o, raw_hex, digest, target in PRODUCERS:
        raw = rom[o:o+4]
        if raw.hex() != raw_hex or _digest(raw) != digest: raise ValueError("producer bytes changed")
        rows.append({"producer_id": pid, "file_offset": o, "gba_address": f"0x{ROM_BASE+o:08X}", "raw_hex": raw_hex, "bytes_sha256": digest, "target_file_offset": target, "target_gba_address": f"0x{ROM_BASE+target:08X}"})
    return {"scan": {"mode": "thumb", "alignment_bytes": 2, "range": [0, len(rom)], "targets": sorted(targets), "matching_producer_count": 3}, "producers": rows}

def _roots(rom: bytes) -> list[dict[str, Any]]:
    by_target = {x["target_file_offset"]: x for x in _producers(rom)["producers"]}; rows = []
    for o, raw_hex, digest in ROOTS:
        raw = rom[o:o+4]
        if raw.hex() != raw_hex or _digest(raw) != digest: raise ValueError("root bytes changed")
        rows.append({"root_id": f"root-thumb-{o:06x}", "mode": "thumb", "file_offset": o, "gba_address": f"0x{ROM_BASE+o:08X}", "entry_size": 4, "entry_sha256": digest, "sources": [{"producer_id": by_target[o]["producer_id"]}]})
    return rows

def verify_rom_cfg_proven_roots_v5(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []; summary: dict[str, Any] = {}; rebuilt_count = cross_count = 0
    try:
        root = Path(root).resolve(strict=True); artifact = Path(artifact_dir).absolute()
        if artifact.resolve(strict=True) != artifact or not artifact.is_dir(): raise ValueError("artifact uses a symlink")
        members = list(artifact.iterdir())
        if {x.name for x in members} != {"manifest.json", PAYLOAD_NAME} or any(x.is_symlink() or not x.is_file() for x in members): raise ValueError("artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256: raise ValueError("base ROM identity changed")
        producers = _producers(rom); roots = _roots(rom)
        entries, owners = _all_baselines(root, rom)
        raw_v4 = _safe_file(root, V4_PAYLOAD).read_bytes()
        if _digest(raw_v4) != V4_SHA: raise ValueError("v4 baseline identity changed")
        v4 = json.loads(raw_v4); blocks_v4 = v4["extension"]["blocks"]
        _, _, _, decoded_v4 = _verify_blocks(rom, blocks_v4); entries["proven_roots_v4"] = decoded_v4; owners["proven_roots_v4"] = _owner_map(blocks_v4, decoded_v4)
        rebuilt, rebuilt_crosses = _rebuild_delta(rom, roots, entries); rebuilt_count = len(rebuilt)
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes(); payload = json.loads(payload_raw); manifest = json.loads((artifact / "manifest.json").read_bytes())
        expected_rom = {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        expected_frozen = {
            "v2": {"schema": "rom-cfg-inventory-v2"}, "v3": {"schema": "rom-cfg-inventory-v3"}, "proven_roots_v1": {"schema": "rom-cfg-proven-roots-v1"},
            "proven_roots_v2": {"schema": "rom-cfg-proven-roots-v2", "payload_sha256": "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"},
            "battle_controller": {"schema": "rom-battle-controller-cfg-v1", "payload_sha256": "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"},
            "proven_roots_v3": {"schema": "rom-cfg-proven-roots-v3", "payload_sha256": "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2"},
            "proven_roots_v4": {"schema": "rom-cfg-proven-roots-v4", "payload_sha256": V4_SHA},
        }
        if payload.get("schema") != SCHEMA or payload.get("rom") != expected_rom or payload.get("frozen_baseline") != expected_frozen or payload.get("producer_denominator") != producers or payload.get("scope") != SCOPE: raise ValueError("top-level contract changed")
        extension = payload["extension"]; blocks = extension["blocks"]
        last, block_entries, by_id, artifact_entries = _verify_blocks(rom, blocks)
        if set(artifact_entries) != set(rebuilt): raise ValueError("closure differs from worklist")
        frontiers, cross_records, cross_vector = _expected_frontiers_and_crosses(rom, blocks, last, block_entries, artifact_entries, entries, owners, roots)
        if _simple_cross_vector(rebuilt_crosses) != cross_vector: raise ValueError("cross worklists disagree")
        summary = _extension_summary(blocks, frontiers); expected_summary = {"decoded_basic_block_count": 124, "decoded_instruction_count": 576, "frontier_count": 8, "frontier_reasons": {"indirect_pc_target": 8}, "reachable_instruction_bytes": 1252}
        if summary != expected_summary: raise ValueError("summary changed")
        cross_count = len(cross_vector)
        if cross_count != 40 or Counter(x["target"]["baseline_artifact"] for x in cross_records) != {"v2": 39, "proven_roots_v1": 1}: raise ValueError("cross denominator changed")
        expected_extension = {"blocks": blocks, "frontiers": frontiers, "baseline_cross_edges": cross_records, "cross_edge_denominator_sha256": _canonical_sha(cross_vector), "summary": summary}
        if payload.get("roots") != _expected_roots(roots, block_entries, by_id, frontiers) or extension != expected_extension: raise ValueError("root or edge contract changed")
        expected_manifest = {"artifact_schema": SCHEMA, "rom": expected_rom, "producer_summary": {"count": 3}, "root_count": 3, "extension_summary": summary, "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _digest(payload_raw)}}}
        if manifest != expected_manifest: raise ValueError("manifest changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error: errors.append(str(error))
    return {"schema": VERIFY_SCHEMA, "verified": not errors, "errors": errors, "control_flow_oracle": "armv4t-raw-encoding", "independently_rebuilt_instruction_count": rebuilt_count, "root_count": 3 if not errors else 0, "decoded_instruction_count": summary.get("decoded_instruction_count", 0), "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0), "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0), "frontier_count": summary.get("frontier_count", 0), "baseline_cross_edge_count": cross_count}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--root", type=Path, default=Path.cwd()); parser.add_argument("--artifact-dir", type=Path, required=True); args = parser.parse_args(); artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir; report = verify_rom_cfg_proven_roots_v5(args.root, artifact); print(json.dumps(report, ensure_ascii=False, indent=2)); return 0 if report["verified"] else 1

if __name__ == "__main__": raise SystemExit(main())
