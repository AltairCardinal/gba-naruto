#!/usr/bin/env python3
"""Independently verify the direct-call-proven CFG root at 0x07305C."""

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
    ROM_PATH,
    ROM_SHA256,
    _canonical_sha,
    _expected_roots,
    _safe_file,
    _verify_blocks,
)
from tools.verify_rom_cfg_proven_roots_v2 import (
    _cross_records,
    _expected_frontiers_and_crosses,
    _extension_summary,
    _owner_map,
    _rebuild_delta,
    _simple_cross_vector,
)
from tools.verify_rom_cfg_proven_roots_v3 import _all_baselines


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
ROOT_OFFSET = 0x7305C
SCHEMA = "rom-cfg-proven-roots-v4"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v4"
PAYLOAD_NAME = "rom-cfg-proven-roots-v4.json"
PROVEN_V3_PAYLOAD = Path(
    "artifacts/rom-cfg-proven-roots-v3/rom-cfg-proven-roots-v3.json"
)
PROVEN_V3_PAYLOAD_SHA256 = (
    "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2"
)
EXPECTED_PRODUCERS = (
    (
        "controller_state_073696",
        0x73696,
        "fff7e1fc",
        "f0a7b8f93d310a6940494933b6a8fe41c0099248676effe6da1d09e15486627c",
    ),
    (
        "controller_state_0736c4",
        0x736C4,
        "fff7cafc",
        "0d07c0b3c17f125d9ebf75b68584b5f4d089b93cb8b435ea4224e97d23f2193a",
    ),
    (
        "controller_state_07444e",
        0x7444E,
        "fef705fe",
        "ca09b79bd74309ea4e4e7bc392d0e138bb72b0c49ac6efc82fa3d7ab326cdb93",
    ),
    (
        "controller_state_0749ce",
        0x749CE,
        "fef745fb",
        "fd06b7df5aa783a273bde99b30ecabceced3dbbb25a44b5ab9a6f96998bb790a",
    ),
)
SCOPE = {
    "fixed_direct_producer_denominator_complete": True,
    "baseline_entries_treated_as_opaque": True,
    "runtime_reachability_complete": False,
    "global_function_entry_denominator_complete": False,
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_thumb_bl(callsite: int, first: int, second: int) -> int | None:
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        return None
    displacement = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if displacement & 0x400000:
        displacement -= 0x800000
    return callsite + 4 + displacement


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        if _decode_thumb_bl(offset, first, second) == ROOT_OFFSET:
            actual.append((offset, ROOT_OFFSET))
    expected = [(item[1], ROOT_OFFSET) for item in EXPECTED_PRODUCERS]
    if actual != expected:
        raise ValueError("independent direct-call producer denominator changed")
    producers = []
    for producer_id, offset, raw_hex, digest in EXPECTED_PRODUCERS:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _digest(raw) != digest:
            raise ValueError("independent direct-call producer bytes changed")
        producers.append(
            {
                "producer_id": producer_id,
                "file_offset": offset,
                "gba_address": f"0x{ROM_BASE + offset:08X}",
                "raw_hex": raw_hex,
                "bytes_sha256": digest,
                "target_file_offset": ROOT_OFFSET,
                "target_gba_address": f"0x{ROM_BASE + ROOT_OFFSET:08X}",
            }
        )
    return {
        "scan": {
            "mode": "thumb",
            "alignment_bytes": 2,
            "range": [0, len(rom)],
            "targets": [ROOT_OFFSET],
            "matching_producer_count": 4,
        },
        "producers": producers,
    }


def _root_seeds(rom: bytes) -> list[dict[str, Any]]:
    producers = _producer_denominator(rom)["producers"]
    raw = rom[ROOT_OFFSET : ROOT_OFFSET + 4]
    if raw.hex() != "30b50006" or _digest(raw) != (
        "cede13811d1cad27a7d27f09911219f8c9e6560ebdc98269cf4044456f763502"
    ):
        raise ValueError("independent root bytes changed")
    return [
        {
            "root_id": "root-thumb-07305c",
            "mode": "thumb",
            "file_offset": ROOT_OFFSET,
            "gba_address": f"0x{ROM_BASE + ROOT_OFFSET:08X}",
            "entry_size": 4,
            "entry_sha256": _digest(raw),
            "sources": [{"producer_id": item["producer_id"]} for item in producers],
        }
    ]


def _load_v3_baseline(
    root: Path,
    rom: bytes,
    entries: dict[str, dict[tuple[str, int], dict[str, Any]]],
    owners: dict[str, dict[tuple[str, int], dict[str, Any]]],
) -> None:
    raw = _safe_file(root, PROVEN_V3_PAYLOAD).read_bytes()
    if _digest(raw) != PROVEN_V3_PAYLOAD_SHA256:
        raise ValueError("independent v3 baseline identity changed")
    payload = json.loads(raw)
    blocks = payload["extension"]["blocks"]
    _, _, _, decoded = _verify_blocks(rom, blocks)
    entries["proven_roots_v3"] = decoded
    owners["proven_roots_v3"] = _owner_map(blocks, decoded)


def verify_rom_cfg_proven_roots_v4(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    summary: dict[str, Any] = {}
    rebuilt_count = 0
    cross_count = 0
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        resolved = artifact.resolve(strict=True)
        if resolved != artifact or not artifact.is_dir():
            raise ValueError("CFG proven-root v4 artifact uses a symlink")
        members = list(artifact.iterdir())
        if (
            {item.name for item in members} != {"manifest.json", PAYLOAD_NAME}
            or any(item.is_symlink() or not item.is_file() for item in members)
        ):
            raise ValueError("CFG proven-root v4 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _digest(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        producers = _producer_denominator(rom)
        roots = _root_seeds(rom)
        baseline_entries, baseline_owners = _all_baselines(root, rom)
        _load_v3_baseline(root, rom, baseline_entries, baseline_owners)
        occupied: set[int] = set()
        for label, decoded in baseline_entries.items():
            current = {
                byte
                for (_, offset), item in decoded.items()
                for byte in range(offset, offset + item["size"])
            }
            if occupied & current:
                raise ValueError(f"independent baseline bytes overlap at {label}")
            occupied.update(current)
        rebuilt, rebuilt_crosses = _rebuild_delta(rom, roots, baseline_entries)
        rebuilt_count = len(rebuilt)

        payload_path = artifact / PAYLOAD_NAME
        payload_raw = payload_path.read_bytes()
        payload = json.loads(payload_raw)
        manifest = json.loads((artifact / "manifest.json").read_bytes())
        expected_rom = {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        }
        expected_frozen = {
            "v2": {"schema": "rom-cfg-inventory-v2"},
            "v3": {"schema": "rom-cfg-inventory-v3"},
            "proven_roots_v1": {"schema": "rom-cfg-proven-roots-v1"},
            "proven_roots_v2": {
                "schema": "rom-cfg-proven-roots-v2",
                "payload_sha256": "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba",
            },
            "battle_controller": {
                "schema": "rom-battle-controller-cfg-v1",
                "payload_sha256": "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a",
            },
            "proven_roots_v3": {
                "schema": "rom-cfg-proven-roots-v3",
                "payload_sha256": PROVEN_V3_PAYLOAD_SHA256,
            },
        }
        if (
            set(payload)
            != {
                "schema",
                "rom",
                "frozen_baseline",
                "producer_denominator",
                "roots",
                "extension",
                "scope",
            }
            or payload.get("schema") != SCHEMA
            or payload.get("rom") != expected_rom
            or payload.get("frozen_baseline") != expected_frozen
            or payload.get("producer_denominator") != producers
            or payload.get("scope") != SCOPE
        ):
            raise ValueError("CFG proven-root v4 top-level contract changed")
        extension = payload.get("extension")
        if not isinstance(extension, dict) or set(extension) != {
            "blocks",
            "frontiers",
            "baseline_cross_edges",
            "cross_edge_denominator_sha256",
            "summary",
        }:
            raise ValueError("CFG proven-root v4 extension contract changed")
        blocks = extension["blocks"]
        decoded_last, block_entries, by_id, artifact_entries = _verify_blocks(
            rom, blocks
        )
        if set(artifact_entries) != set(rebuilt):
            raise ValueError("CFG proven-root v4 closure differs from worklist")
        frontiers, cross_records, cross_vector = _expected_frontiers_and_crosses(
            rom,
            blocks,
            decoded_last,
            block_entries,
            artifact_entries,
            baseline_entries,
            baseline_owners,
            roots,
        )
        if _simple_cross_vector(rebuilt_crosses) != cross_vector:
            raise ValueError("CFG proven-root v4 cross worklists disagree")
        summary = _extension_summary(blocks, frontiers)
        expected_summary = {
            "decoded_basic_block_count": 118,
            "decoded_instruction_count": 486,
            "frontier_count": 6,
            "frontier_reasons": {"indirect_pc_target": 6},
            "reachable_instruction_bytes": 1_044,
        }
        if summary != expected_summary:
            raise ValueError("CFG proven-root v4 summary changed")
        cross_count = len(cross_vector)
        if cross_count != 29 or Counter(
            item["target"]["baseline_artifact"] for item in cross_records
        ) != {"v2": 29}:
            raise ValueError("CFG proven-root v4 cross denominator changed")
        expected_roots = _expected_roots(roots, block_entries, by_id, frontiers)
        expected_extension = {
            "blocks": blocks,
            "frontiers": frontiers,
            "baseline_cross_edges": cross_records,
            "cross_edge_denominator_sha256": _canonical_sha(cross_vector),
            "summary": summary,
        }
        if payload.get("roots") != expected_roots or extension != expected_extension:
            raise ValueError("CFG proven-root v4 root or edge contract changed")
        expected_manifest = {
            "artifact_schema": SCHEMA,
            "rom": expected_rom,
            "producer_summary": {"count": 4},
            "root_count": 1,
            "extension_summary": summary,
            "files": {
                PAYLOAD_NAME: {
                    "size": len(payload_raw),
                    "sha256": _digest(payload_raw),
                }
            },
        }
        if manifest != expected_manifest:
            raise ValueError("CFG proven-root v4 manifest changed")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "control_flow_oracle": "armv4t-raw-encoding",
        "independently_rebuilt_instruction_count": rebuilt_count,
        "root_count": 1 if not errors else 0,
        "decoded_instruction_count": summary.get("decoded_instruction_count", 0),
        "decoded_basic_block_count": summary.get("decoded_basic_block_count", 0),
        "reachable_instruction_bytes": summary.get("reachable_instruction_bytes", 0),
        "frontier_count": summary.get("frontier_count", 0),
        "baseline_cross_edge_count": cross_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_rom_cfg_proven_roots_v4(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
