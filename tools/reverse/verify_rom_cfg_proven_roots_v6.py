#!/usr/bin/env python3
"""Independently verify the five direct-call-proven v6 CFG roots."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from tools.verify_rom_cfg_inventory import ROM_PATH, ROM_SHA256, _canonical_sha, _expected_roots, _safe_file, _verify_blocks
from tools.verify_rom_cfg_proven_roots_v2 import _expected_frontiers_and_crosses, _extension_summary, _owner_map, _rebuild_delta, _simple_cross_vector
from tools.verify_rom_cfg_proven_roots_v3 import _all_baselines

ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v6"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v6"
PAYLOAD_NAME = "rom-cfg-proven-roots-v6.json"
BASELINES = (
    ("proven_roots_v4", "artifacts/rom-cfg-proven-roots-v4/rom-cfg-proven-roots-v4.json", "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb"),
    ("proven_roots_v5", "artifacts/rom-cfg-proven-roots-v5/rom-cfg-proven-roots-v5.json", "680b03dffb5c3dbbca41d9a5d0872db560a1a05850d7928ce75243397a54f040"),
)
PRODUCERS = (
    ("producer_08f474", 0x8F474, "fff72cfc", "94ecb62d414de199f9dc59d857916c90742eb0b696c7e1a4fcb0d04808bd0912", 0x8ECD0),
    ("producer_08f47a", 0x8F47A, "fef74dfe", "3d642e704a4210e0b5a7ae7979e231f09379cfc0574b8b1b8c6bbf74312b875e", 0x8E118),
    ("producer_08f644", 0x8F644, "faf754fd", "b4a1c441c800d7371e4b68a369af2997af574043bae2ed813d91f7d881941e58", 0x8A0F0),
    ("producer_08f872", 0x8F872, "f8f765f8", "e58c0b31ee845816aa6682a5a62ae4e2315f75318dfb2902eec7d079a87a64cb", 0x87940),
    ("producer_08f9c0", 0x8F9C0, "faf796fb", "470fb979d1b416602b1aeda710daccfde7da131c907a109930bc58354cb18a55", 0x8A0F0),
    ("producer_08fa1c", 0x8FA1C, "f7f7e6fa", "e73c1de4ed71cea181a41722471bbc4ea9f58c8708bcd831f044919bb8a109f6", 0x86FEC),
)
ROOTS = (
    (0x86FEC, "30b586b0", "1e7861e529c6093cc689c955195ffb30a3fe02486f5c7b5662e9e164d7e01d0d"),
    (0x87940, "f0b55746", "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"),
    (0x8A0F0, "70b586b0", "ba42a0ffa6ad2f1fed1a57c4268d425270224d416926807254d0b9b20f921efc"),
    (0x8E118, "f0b54746", "3e7ec2098933d96de8dc658d119ed3848ccdd7942f96f2a0d015f1e68e3c759b"),
    (0x8ECD0, "f0b54f46", "8a1d56a49bd75817476a967ee4e23ecef2beeffa6748599c19bc8e7ed7620257"),
)
SCOPE = {"fixed_direct_producer_denominator_complete": True, "baseline_entries_treated_as_opaque": True, "runtime_reachability_complete": False, "global_function_entry_denominator_complete": False}


def _digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()


def _decode_bl(offset: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800: return None
    value = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if value & 0x400000: value -= 0x800000
    return offset + 4 + value


def _producers(rom: bytes) -> dict[str, Any]:
    targets = {item[4] for item in PRODUCERS}; actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset); target = _decode_bl(offset, first, second)
        if target in targets: actual.append((offset, target))
    if actual != [(item[1], item[4]) for item in PRODUCERS]: raise ValueError("independent producer denominator changed")
    rows = []
    for producer_id, offset, raw_hex, digest, target in PRODUCERS:
        raw = rom[offset:offset+4]
        if raw.hex() != raw_hex or _digest(raw) != digest: raise ValueError("producer bytes changed")
        rows.append({"producer_id": producer_id, "file_offset": offset, "gba_address": f"0x{ROM_BASE+offset:08X}", "raw_hex": raw_hex, "bytes_sha256": digest, "target_file_offset": target, "target_gba_address": f"0x{ROM_BASE+target:08X}"})
    return {"scan": {"mode": "thumb", "alignment_bytes": 2, "range": [0, len(rom)], "targets": sorted(targets), "matching_producer_count": 6}, "producers": rows}


def _roots(rom: bytes) -> list[dict[str, Any]]:
    by_target: dict[int, list[str]] = {}
    for item in _producers(rom)["producers"]: by_target.setdefault(item["target_file_offset"], []).append(item["producer_id"])
    rows = []
    for offset, raw_hex, digest in ROOTS:
        raw = rom[offset:offset+4]
        if raw.hex() != raw_hex or _digest(raw) != digest: raise ValueError("root bytes changed")
        rows.append({"root_id": f"root-thumb-{offset:06x}", "mode": "thumb", "file_offset": offset, "gba_address": f"0x{ROM_BASE+offset:08X}", "entry_size": 4, "entry_sha256": digest, "sources": [{"producer_id": value} for value in by_target[offset]]})
    return rows


def verify_rom_cfg_proven_roots_v6(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []; summary: dict[str, Any] = {}; rebuilt_count = cross_count = 0
    try:
        root = Path(root).resolve(strict=True); artifact = Path(artifact_dir).resolve(strict=True)
        members = list(artifact.iterdir())
        if {item.name for item in members} != {"manifest.json", PAYLOAD_NAME} or any(item.is_symlink() or not item.is_file() for item in members): raise ValueError("artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256: raise ValueError("base ROM identity changed")
        producers = _producers(rom); roots = _roots(rom); entries, owners = _all_baselines(root, rom)
        for label, path, digest in BASELINES:
            raw = _safe_file(root, Path(path)).read_bytes()
            if _digest(raw) != digest: raise ValueError(f"{label} baseline identity changed")
            payload = json.loads(raw); blocks = payload["extension"]["blocks"]
            _, _, _, decoded = _verify_blocks(rom, blocks); entries[label] = decoded; owners[label] = _owner_map(blocks, decoded)
        rebuilt, rebuilt_crosses = _rebuild_delta(rom, roots, entries); rebuilt_count = len(rebuilt)
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes(); payload = json.loads(payload_raw); manifest = json.loads((artifact / "manifest.json").read_bytes())
        expected_rom = {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        expected_frozen = {
            "v2": {"schema": "rom-cfg-inventory-v2"}, "v3": {"schema": "rom-cfg-inventory-v3"}, "proven_roots_v1": {"schema": "rom-cfg-proven-roots-v1"},
            "proven_roots_v2": {"schema": "rom-cfg-proven-roots-v2", "payload_sha256": "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"},
            "battle_controller": {"schema": "rom-battle-controller-cfg-v1", "payload_sha256": "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"},
            "proven_roots_v3": {"schema": "rom-cfg-proven-roots-v3", "payload_sha256": "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2"},
            "proven_roots_v4": {"schema": "rom-cfg-proven-roots-v4", "payload_sha256": BASELINES[0][2]},
            "proven_roots_v5": {"schema": "rom-cfg-proven-roots-v5", "payload_sha256": BASELINES[1][2]},
        }
        if payload.get("schema") != SCHEMA or payload.get("rom") != expected_rom or payload.get("frozen_baseline") != expected_frozen or payload.get("producer_denominator") != producers or payload.get("scope") != SCOPE: raise ValueError("top-level contract changed")
        extension = payload["extension"]; blocks = extension["blocks"]
        last, block_entries, by_id, artifact_entries = _verify_blocks(rom, blocks)
        if set(artifact_entries) != set(rebuilt): raise ValueError("closure differs from worklist")
        frontiers, cross_records, cross_vector = _expected_frontiers_and_crosses(rom, blocks, last, block_entries, artifact_entries, entries, owners, roots)
        if _simple_cross_vector(rebuilt_crosses) != cross_vector: raise ValueError("cross worklists disagree")
        summary = _extension_summary(blocks, frontiers)
        expected_summary = {"decoded_basic_block_count": 2305, "decoded_instruction_count": 12564, "frontier_count": 85, "frontier_reasons": {"indirect_pc_target": 85}, "reachable_instruction_bytes": 27224}
        if summary != expected_summary: raise ValueError("summary changed")
        cross_count = len(cross_vector)
        if cross_count != 916 or Counter(item["target"]["baseline_artifact"] for item in cross_records) != {"v2": 894, "proven_roots_v2": 12, "v3": 7, "battle_controller": 2, "proven_roots_v4": 1}: raise ValueError("cross denominator changed")
        expected_extension = {"blocks": blocks, "frontiers": frontiers, "baseline_cross_edges": cross_records, "cross_edge_denominator_sha256": _canonical_sha(cross_vector), "summary": summary}
        if payload.get("roots") != _expected_roots(roots, block_entries, by_id, frontiers) or extension != expected_extension: raise ValueError("root or edge contract changed")
        expected_manifest = {"artifact_schema": SCHEMA, "rom": expected_rom, "producer_summary": {"count": 6}, "root_count": 5, "extension_summary": summary, "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _digest(payload_raw)}}}
        if manifest != expected_manifest: raise ValueError("manifest changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error: errors.append(str(error))
    return {"schema": VERIFY_SCHEMA, "verified": not errors, "errors": errors, "control_flow_oracle": "armv4t-raw-encoding", "independently_rebuilt_instruction_count": rebuilt_count, "root_count": 5 if not errors else 0, "decoded_instruction_count": summary.get("decoded_instruction_count", 0), "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0), "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0), "frontier_count": summary.get("frontier_count", 0), "baseline_cross_edge_count": cross_count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--root", type=Path, default=Path.cwd()); parser.add_argument("--artifact-dir", type=Path, required=True); args = parser.parse_args(); artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir; report = verify_rom_cfg_proven_roots_v6(args.root, artifact); print(json.dumps(report, indent=2)); return 0 if report["verified"] else 1


if __name__ == "__main__": raise SystemExit(main())
