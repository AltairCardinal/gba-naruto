#!/usr/bin/env python3
"""Independently verify the direct-call-proven CFG root at 0x070DF8."""

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
    _sha,
    _verify_blocks,
)
from tools.verify_rom_cfg_proven_roots_v2 import (
    _baseline_contract,
    _baseline_entries,
    _cross_records,
    _expected_frontiers_and_crosses,
    _extension_summary,
    _owner_map,
    _rebuild_delta,
    _simple_cross_vector,
)


ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v3"
VERIFY_SCHEMA = "rom-cfg-proven-roots-verification-v3"
PAYLOAD_NAME = "rom-cfg-proven-roots-v3.json"
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
        if _decode_thumb_bl(offset, first, second) == 0x70DF8:
            actual.append((offset, 0x70DF8))
    expected = [(item[1], item[4]) for item in EXPECTED_PRODUCERS]
    if actual != expected:
        raise ValueError("independent direct-call producer denominator changed")
    producers = []
    for producer_id, offset, raw_hex, digest, target in EXPECTED_PRODUCERS:
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
            "matching_producer_count": 2,
        },
        "producers": producers,
    }


def _root_seeds(rom: bytes) -> list[dict[str, Any]]:
    producers = _producer_denominator(rom)["producers"]
    offset = 0x70DF8
    raw = rom[offset : offset + 4]
    if raw.hex() != "f0b55746" or _digest(raw) != (
        "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"
    ):
        raise ValueError("independent root bytes changed")
    return [
        {
            "root_id": "root-thumb-070df8",
            "mode": "thumb",
            "file_offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}",
            "entry_size": 4,
            "entry_sha256": _digest(raw),
            "sources": [
                {"producer_id": item["producer_id"]} for item in producers
            ],
        }
    ]


def _load_payload(root: Path, path: Path, digest: str) -> dict[str, Any]:
    raw = _safe_file(root, path).read_bytes()
    if _digest(raw) != digest:
        raise ValueError(f"independent frozen payload identity changed: {path}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("independent frozen payload is not an object")
    return value


def _all_baselines(
    root: Path, rom: bytes
) -> tuple[
    dict[str, dict[tuple[str, int], dict[str, Any]]],
    dict[str, dict[tuple[str, int], dict[str, Any]]],
]:
    prior = _baseline_contract(root, rom)
    entries, owners = _baseline_entries(rom, prior)
    for label, payload in (
        (
            "proven_roots_v2",
            _load_payload(root, PROVEN_V2_PAYLOAD, PROVEN_V2_PAYLOAD_SHA256),
        ),
        (
            "battle_controller",
            _load_payload(root, CONTROLLER_PAYLOAD, CONTROLLER_PAYLOAD_SHA256),
        ),
    ):
        blocks = payload["extension"]["blocks"]
        _, _, _, decoded = _verify_blocks(rom, blocks)
        entries[label] = decoded
        owners[label] = _owner_map(blocks, decoded)
    occupied: set[int] = set()
    for label, decoded in entries.items():
        current = {
            byte
            for (_, offset), item in decoded.items()
            for byte in range(offset, offset + item["size"])
        }
        if occupied & current:
            raise ValueError(f"independent baseline bytes overlap at {label}")
        occupied.update(current)
    return entries, owners


def verify_rom_cfg_proven_roots_v3(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    summary: dict[str, Any] = {}
    rebuilt_count = 0
    cross_count = 0
    try:
        root = Path(root).resolve(strict=True)
        artifact = Path(artifact_dir).absolute()
        resolved = artifact.resolve(strict=True)
        if resolved != artifact or not artifact.is_dir():
            raise ValueError("CFG proven-root v3 artifact uses a symlink")
        members = list(artifact.iterdir())
        if (
            {item.name for item in members} != {"manifest.json", PAYLOAD_NAME}
            or any(item.is_symlink() or not item.is_file() for item in members)
        ):
            raise ValueError("CFG proven-root v3 artifact file set changed")
        rom = _safe_file(root, ROM_PATH).read_bytes()
        if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM identity changed")
        producers = _producer_denominator(rom)
        roots = _root_seeds(rom)
        baseline_entries, baseline_owners = _all_baselines(root, rom)
        rebuilt, rebuilt_crosses = _rebuild_delta(
            rom, roots, baseline_entries
        )
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
                "payload_sha256": PROVEN_V2_PAYLOAD_SHA256,
            },
            "battle_controller": {
                "schema": "rom-battle-controller-cfg-v1",
                "payload_sha256": CONTROLLER_PAYLOAD_SHA256,
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
            raise ValueError("CFG proven-root v3 top-level contract changed")
        extension = payload.get("extension")
        if not isinstance(extension, dict) or set(extension) != {
            "blocks",
            "frontiers",
            "baseline_cross_edges",
            "cross_edge_denominator_sha256",
            "summary",
        }:
            raise ValueError("CFG proven-root v3 extension contract changed")
        blocks = extension["blocks"]
        decoded_last, block_entries, by_id, artifact_entries = _verify_blocks(
            rom, blocks
        )
        if set(artifact_entries) != set(rebuilt):
            raise ValueError("CFG proven-root v3 closure differs from worklist")
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
            raise ValueError("CFG proven-root v3 cross worklists disagree")
        summary = _extension_summary(blocks, frontiers)
        expected_summary = {
            "decoded_basic_block_count": 8,
            "decoded_instruction_count": 52,
            "frontier_count": 0,
            "frontier_reasons": {},
            "reachable_instruction_bytes": 110,
        }
        if summary != expected_summary:
            raise ValueError("CFG proven-root v3 summary changed")
        cross_count = len(cross_vector)
        if cross_count != 5 or Counter(
            item["baseline"] for item in cross_vector
        ) != {"v2": 5}:
            raise ValueError("CFG proven-root v3 cross denominator changed")
        expected_roots = _expected_roots(roots, block_entries, by_id, frontiers)
        expected_extension = {
            "blocks": blocks,
            "frontiers": frontiers,
            "baseline_cross_edges": cross_records,
            "cross_edge_denominator_sha256": _canonical_sha(cross_vector),
            "summary": summary,
        }
        if (
            payload.get("roots") != expected_roots
            or extension != expected_extension
        ):
            raise ValueError("CFG proven-root v3 root or edge contract changed")
        expected_manifest = {
            "artifact_schema": SCHEMA,
            "rom": expected_rom,
            "producer_summary": {"count": 2},
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
            raise ValueError("CFG proven-root v3 manifest changed")
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
    report = verify_rom_cfg_proven_roots_v3(args.root, artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
