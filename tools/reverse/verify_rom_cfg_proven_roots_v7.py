#!/usr/bin/env python3
"""Independently verify CFG roots from two fixed Thumb dispatchers."""

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

from tools.verify_rom_cfg_inventory import ROM_PATH, ROM_SHA256, _canonical_sha, _expected_roots, _safe_file, _verify_blocks
from tools.verify_rom_cfg_proven_roots_v2 import _expected_frontiers_and_crosses, _extension_summary, _owner_map, _rebuild_delta, _simple_cross_vector
from tools.verify_rom_cfg_proven_roots_v3 import _all_baselines

ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v7"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v7"
PAYLOAD_NAME = "rom-cfg-proven-roots-v7.json"
BASELINES = (
    ("proven_roots_v4", "artifacts/rom-cfg-proven-roots-v4/rom-cfg-proven-roots-v4.json", "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb"),
    ("proven_roots_v5", "artifacts/rom-cfg-proven-roots-v5/rom-cfg-proven-roots-v5.json", "680b03dffb5c3dbbca41d9a5d0872db560a1a05850d7928ce75243397a54f040"),
    ("proven_roots_v6", "artifacts/rom-cfg-proven-roots-v6/rom-cfg-proven-roots-v6.json", "e5b27a55c77cd1df4ac5ec39f2dd05735b0b53c01b7cbbcf1620db1681a3c3ec"),
)
DISPATCHERS = (
    ("byte-index-minus-one-0-to-6", 0x6E84E, (0x6E83A, 0x6E850), "c74238ef0b90b5f251a3bf71e9cf471a187efaa32836f8e83dc292a45f142e1d", "ldrb; subs #1; cmp #6; unsigned bls", 0, 6, 0x6E864, "e4fe803292766caeeed6856a18dafdeb481e3fb798997e76370e5fdb2b562ad5", (0x6E868, 0x6E884), "2e7c3a263cf6d6410dd741d4e2439fabbc106ccca78c781bab8cd95ad998cd5d"),
    ("masked-halfword-minus-one-0-to-37", 0x92850, (0x9283A, 0x92852), "e06cfe149e1bba492025792d33bf40a809e9f33d7a87ed724f6369004a5e2493", "ldrh; ands #0x3f; subs #1; cmp #0x25; unsigned bls", 0, 37, 0x92860, "f7d1e641798891c3426b45d8cc074b1e2dcf24fe9c2dd48e3b48f891b5f19abc", (0x92864, 0x928FC), "c13ef2eee340bcd853e38930a8b9037439efdcc2eff9b471f75cbdeb2fa5785f"),
)
ROOT_BYTES = (
    (0x6E884, "21381df085d63c784de52afe8dc541c4b0edd4646a24ceb44d441eae4c1f5315"),
    (0x6E898, "3ebafc3dd9af7c16d0625b47759c2b582960b4952fe5ab4f96749bea14a08745"),
    (0x6E8C8, "a8aa250e285b665668f35d8411dbdf3d38fdd0ffc27f063e6d9c7319cd07c67c"),
    (0x6E8E4, "21381df085d63c784de52afe8dc541c4b0edd4646a24ceb44d441eae4c1f5315"),
    (0x6E8F8, "21381df085d63c784de52afe8dc541c4b0edd4646a24ceb44d441eae4c1f5315"),
    (0x6E90C, "21381df085d63c784de52afe8dc541c4b0edd4646a24ceb44d441eae4c1f5315"),
    (0x92A94, "a15544a8ab29cd07aa4ea3c0982c0a27f18bd989619ba2709e31e8441319b08c"),
    (0x92AC0, "15d745099b5c40e1f900e49ecfd277473465400277087ce2dc6edfba2130cce0"),
)
SCOPE = {"fixed_dispatcher_denominator_complete": True, "baseline_entries_treated_as_opaque": True, "runtime_reachability_complete": False, "global_indirect_target_denominator_complete": False}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dispatchers(rom: bytes) -> list[dict[str, Any]]:
    rows = []
    for dispatcher_id, terminal, proof_range, proof_sha, index_source, index_min, index_max, literal_offset, literal_sha, table_range, table_sha in DISPATCHERS:
        if _digest(rom[proof_range[0]:proof_range[1]]) != proof_sha:
            raise ValueError("independent dispatcher proof changed")
        literal = rom[literal_offset:literal_offset + 4]
        if _digest(literal) != literal_sha or struct.unpack("<I", literal)[0] != ROM_BASE + table_range[0]:
            raise ValueError("independent dispatcher literal changed")
        table = rom[table_range[0]:table_range[1]]
        if _digest(table) != table_sha:
            raise ValueError("independent dispatcher table changed")
        targets = [struct.unpack_from("<I", table, offset)[0] - ROM_BASE for offset in range(0, len(table), 4)]
        if len(targets) != index_max - index_min + 1:
            raise ValueError("independent dispatcher index denominator changed")
        rows.append({"dispatcher_id": dispatcher_id, "terminal_file_offset": terminal, "proof_range": list(proof_range), "proof_sha256": proof_sha, "index_source": index_source, "index_min": index_min, "index_max": index_max, "literal_offset": literal_offset, "literal_sha256": literal_sha, "table_range": list(table_range), "table_sha256": table_sha, "entry_count": len(targets), "target_vector": targets})
    return rows


def _roots(rom: bytes, dispatchers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: dict[int, list[dict[str, Any]]] = {}
    for dispatcher in dispatchers:
        for index, target in enumerate(dispatcher["target_vector"]):
            sources.setdefault(target, []).append({"dispatcher_id": dispatcher["dispatcher_id"], "table_index": index})
    rows = []
    for offset, expected_sha in ROOT_BYTES:
        raw = rom[offset:offset + 4]
        if _digest(raw) != expected_sha or offset not in sources:
            raise ValueError("independent delta root changed")
        rows.append({"root_id": f"root-thumb-{offset:06x}", "mode": "thumb", "file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}", "entry_size": 4, "entry_sha256": expected_sha, "sources": sources[offset]})
    return rows


def verify_rom_cfg_proven_roots_v7(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []; summary: dict[str, Any] = {}; rebuilt_count = cross_count = 0
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        if artifact.resolve(strict=True) != artifact or not artifact.is_dir():
            raise ValueError("CFG proven-root v7 artifact uses a symlink")
        members = list(artifact.iterdir())
        if {item.name for item in members} != {"manifest.json", PAYLOAD_NAME} or any(item.is_symlink() or not item.is_file() for item in members):
            raise ValueError("artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        dispatchers = _dispatchers(rom)
        roots = _roots(rom, dispatchers)
        entries, owners = _all_baselines(root, rom)
        for label, path, digest in BASELINES:
            raw = _safe_file(root, Path(path)).read_bytes()
            if _digest(raw) != digest:
                raise ValueError(f"{label} baseline identity changed")
            baseline_payload = json.loads(raw)
            blocks = baseline_payload["extension"]["blocks"]
            _, _, _, decoded = _verify_blocks(rom, blocks)
            entries[label] = decoded; owners[label] = _owner_map(blocks, decoded)
        rebuilt, rebuilt_crosses = _rebuild_delta(rom, roots, entries); rebuilt_count = len(rebuilt)
        payload_raw = (artifact / PAYLOAD_NAME).read_bytes(); payload = json.loads(payload_raw)
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        expected_rom = {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256}
        expected_frozen = {
            "v2": {"schema": "rom-cfg-inventory-v2"}, "v3": {"schema": "rom-cfg-inventory-v3"}, "proven_roots_v1": {"schema": "rom-cfg-proven-roots-v1"},
            "proven_roots_v2": {"schema": "rom-cfg-proven-roots-v2", "payload_sha256": "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"},
            "battle_controller": {"schema": "rom-battle-controller-cfg-v1", "payload_sha256": "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"},
            "proven_roots_v3": {"schema": "rom-cfg-proven-roots-v3", "payload_sha256": "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2"},
            "proven_roots_v4": {"schema": "rom-cfg-proven-roots-v4", "payload_sha256": BASELINES[0][2]},
            "proven_roots_v5": {"schema": "rom-cfg-proven-roots-v5", "payload_sha256": BASELINES[1][2]},
            "proven_roots_v6": {"schema": "rom-cfg-proven-roots-v6", "payload_sha256": BASELINES[2][2]},
        }
        if set(payload) != {"schema", "rom", "frozen_baseline", "dispatcher_denominator", "roots", "extension", "scope"} or payload.get("schema") != SCHEMA or payload.get("rom") != expected_rom or payload.get("frozen_baseline") != expected_frozen or payload.get("dispatcher_denominator") != dispatchers or payload.get("scope") != SCOPE:
            raise ValueError("top-level contract changed")
        extension = payload["extension"]; blocks = extension["blocks"]
        last, block_entries, by_id, artifact_entries = _verify_blocks(rom, blocks)
        if set(artifact_entries) != set(rebuilt):
            raise ValueError("closure differs from worklist")
        frontiers, cross_records, cross_vector = _expected_frontiers_and_crosses(rom, blocks, last, block_entries, artifact_entries, entries, owners, roots)
        if _simple_cross_vector(rebuilt_crosses) != cross_vector:
            raise ValueError("cross worklists disagree")
        summary = _extension_summary(blocks, frontiers)
        expected_summary = {"decoded_basic_block_count": 38, "decoded_instruction_count": 155, "frontier_count": 1, "frontier_reasons": {"indirect_pc_target": 1}, "reachable_instruction_bytes": 332}
        if summary != expected_summary:
            raise ValueError("summary changed")
        cross_count = len(cross_vector)
        if cross_count != 17 or Counter(item["baseline"] for item in cross_vector) != {"v2": 12, "proven_roots_v6": 5}:
            raise ValueError("cross denominator changed")
        expected_extension = {"blocks": blocks, "frontiers": frontiers, "baseline_cross_edges": cross_records, "cross_edge_denominator_sha256": _canonical_sha(cross_vector), "summary": summary}
        if payload.get("roots") != _expected_roots(roots, block_entries, by_id, frontiers) or extension != expected_extension:
            raise ValueError("root or edge contract changed")
        expected_manifest = {"artifact_schema": SCHEMA, "rom": expected_rom, "dispatcher_summary": {"count": 2, "entry_count": 45, "unique_target_count": 21}, "root_count": 8, "extension_summary": summary, "files": {PAYLOAD_NAME: {"size": len(payload_raw), "sha256": _digest(payload_raw)}}}
        if manifest != expected_manifest:
            raise ValueError("manifest changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {"schema": VERIFY_SCHEMA, "verified": not errors, "errors": errors, "control_flow_oracle": "armv4t-raw-encoding", "independently_rebuilt_instruction_count": rebuilt_count, "root_count": 8 if not errors else 0, "decoded_instruction_count": summary.get("decoded_instruction_count", 0), "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0), "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0), "frontier_count": summary.get("frontier_count", 0), "baseline_cross_edge_count": cross_count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    artifact = args.artifact_dir if args.artifact_dir.is_absolute() else args.root / args.artifact_dir
    report = verify_rom_cfg_proven_roots_v7(args.root, artifact)
    print(json.dumps(report, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__": raise SystemExit(main())
