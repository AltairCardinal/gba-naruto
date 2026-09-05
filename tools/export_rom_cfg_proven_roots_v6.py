#!/usr/bin/env python3
"""Export five direct-call-proven CFG roots over the frozen v5 baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any

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
from tools.export_rom_cfg_proven_roots_v5 import _decode_thumb_bl

ROM_BASE = 0x08000000
ROM_SIZE = 6_291_456
SCHEMA = "rom-cfg-proven-roots-v6"
PAYLOAD_NAME = "rom-cfg-proven-roots-v6.json"
MANIFEST_NAME = "manifest.json"
EXPECTED_PRODUCERS = (
    ("producer_08f474", 0x8F474, "fff72cfc", "94ecb62d414de199f9dc59d857916c90742eb0b696c7e1a4fcb0d04808bd0912", 0x8ECD0),
    ("producer_08f47a", 0x8F47A, "fef74dfe", "3d642e704a4210e0b5a7ae7979e231f09379cfc0574b8b1b8c6bbf74312b875e", 0x8E118),
    ("producer_08f644", 0x8F644, "faf754fd", "b4a1c441c800d7371e4b68a369af2997af574043bae2ed813d91f7d881941e58", 0x8A0F0),
    ("producer_08f872", 0x8F872, "f8f765f8", "e58c0b31ee845816aa6682a5a62ae4e2315f75318dfb2902eec7d079a87a64cb", 0x87940),
    ("producer_08f9c0", 0x8F9C0, "faf796fb", "470fb979d1b416602b1aeda710daccfde7da131c907a109930bc58354cb18a55", 0x8A0F0),
    ("producer_08fa1c", 0x8FA1C, "f7f7e6fa", "e73c1de4ed71cea181a41722471bbc4ea9f58c8708bcd831f044919bb8a109f6", 0x86FEC),
)
EXPECTED_ROOTS = (
    (0x86FEC, "30b586b0", "1e7861e529c6093cc689c955195ffb30a3fe02486f5c7b5662e9e164d7e01d0d"),
    (0x87940, "f0b55746", "715bb484d98123291dbfc7b03e6b6d0b85d3f836d828d1f9e196c59d842415fb"),
    (0x8A0F0, "70b586b0", "ba42a0ffa6ad2f1fed1a57c4268d425270224d416926807254d0b9b20f921efc"),
    (0x8E118, "f0b54746", "3e7ec2098933d96de8dc658d119ed3848ccdd7942f96f2a0d015f1e68e3c759b"),
    (0x8ECD0, "f0b54f46", "8a1d56a49bd75817476a967ee4e23ecef2beeffa6748599c19bc8e7ed7620257"),
)
ADDITIONAL_BASELINES = (
    ("proven_roots_v2", "artifacts/rom-cfg-proven-roots-v2/rom-cfg-proven-roots-v2.json", "a58e0652da0b7825e6cb62d31ad172f681b6e99be2e6142f57471a3b7b5f7cba"),
    ("battle_controller", "artifacts/rom-battle-controller-cfg-v1/rom-battle-controller-cfg.json", "c8b1d1c2068d85912ede1fd35be31f0cf9cb43943beb10f1058d43c65c00449a"),
    ("proven_roots_v3", "artifacts/rom-cfg-proven-roots-v3/rom-cfg-proven-roots-v3.json", "f2de5ca57685e3542d5e483e5a171a30eb32bb6dc6ce9794cc683371579af9a2"),
    ("proven_roots_v4", "artifacts/rom-cfg-proven-roots-v4/rom-cfg-proven-roots-v4.json", "d14c9f4198d9209d03d8511351b5dc997ade409a3218e9f05993c8c7f11456eb"),
    ("proven_roots_v5", "artifacts/rom-cfg-proven-roots-v5/rom-cfg-proven-roots-v5.json", "680b03dffb5c3dbbca41d9a5d0872db560a1a05850d7928ce75243397a54f040"),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _producer_denominator(rom: bytes) -> dict[str, Any]:
    if len(rom) != ROM_SIZE:
        raise ValueError("unexpected ROM size")
    targets = {item[4] for item in EXPECTED_PRODUCERS}
    actual = []
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        target = _decode_thumb_bl(offset, first, second)
        if target in targets:
            actual.append((offset, target))
    expected = [(item[1], item[4]) for item in EXPECTED_PRODUCERS]
    if actual != expected:
        raise ValueError("direct-call producer denominator changed")
    producers = []
    for producer_id, offset, raw_hex, digest, target in EXPECTED_PRODUCERS:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError("direct-call producer bytes changed")
        producers.append({
            "producer_id": producer_id, "file_offset": offset,
            "gba_address": f"0x{ROM_BASE + offset:08X}", "raw_hex": raw_hex,
            "bytes_sha256": digest, "target_file_offset": target,
            "target_gba_address": f"0x{ROM_BASE + target:08X}",
        })
    return {"scan": {"mode": "thumb", "alignment_bytes": 2, "range": [0, len(rom)], "targets": sorted(targets), "matching_producer_count": 6}, "producers": producers}


def _root_seeds(rom: bytes) -> list[dict[str, Any]]:
    by_target: dict[int, list[str]] = {}
    for item in _producer_denominator(rom)["producers"]:
        by_target.setdefault(item["target_file_offset"], []).append(item["producer_id"])
    roots = []
    for offset, raw_hex, digest in EXPECTED_ROOTS:
        raw = rom[offset : offset + 4]
        if raw.hex() != raw_hex or _sha(raw) != digest:
            raise ValueError("direct-call-proven root bytes changed")
        roots.append({
            "root_id": f"root-thumb-{offset:06x}", "mode": "thumb",
            "file_offset": offset, "gba_address": f"0x{ROM_BASE + offset:08X}",
            "entry_size": 4, "entry_sha256": digest,
            "sources": [{"producer_id": value} for value in by_target[offset]],
        })
    return roots


def build_cfg_proven_roots_v6_payload(root: Path, rom: bytes | None = None) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    rom = _safe_file(root, ROM_PATH).read_bytes() if rom is None else rom
    if len(rom) != ROM_SIZE or _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM identity changed")
    producers = _producer_denominator(rom); roots = _root_seeds(rom)
    prior = _baseline_contract(root, rom)
    baseline_nodes, baseline_owners = _baseline_nodes(rom, prior)
    additions = []
    for label, path, digest in ADDITIONAL_BASELINES:
        payload = _load_payload(root, Path(path), digest)
        nodes, owners = _nodes_from_blocks(rom, payload["extension"]["blocks"], label=label)
        baseline_nodes[label] = nodes; baseline_owners[label] = owners
        additions.append((label, payload, digest))
    nodes, rejected, incoming, crosses = _traverse_delta(rom, roots, baseline_nodes)
    _assert_nonoverlapping_nodes(nodes)
    blocks, node_to_block = _build_blocks(rom, nodes, {("thumb", item["file_offset"]) for item in roots})
    frontiers = _frontier_records(nodes, rejected, incoming, roots, node_to_block)
    cross_records, cross_vector = _cross_edge_records(crosses, node_to_block, baseline_owners)
    frozen = {"v2": {"schema": prior["v2"]["schema"]}, "v3": {"schema": prior["v3"]["schema"]}, "proven_roots_v1": {"schema": prior["proven_roots_v1"]["schema"]}}
    for label, payload, digest in additions:
        frozen[label] = {"schema": payload["schema"], "payload_sha256": digest}
    return {
        "schema": SCHEMA, "rom": {"path": ROM_PATH.as_posix(), "size": len(rom), "sha256": ROM_SHA256},
        "frozen_baseline": frozen, "producer_denominator": producers,
        "roots": _root_results(roots, nodes, frontiers, node_to_block),
        "extension": {"blocks": blocks, "frontiers": frontiers, "baseline_cross_edges": cross_records, "cross_edge_denominator_sha256": _canonical_sha(cross_vector), "summary": _extension_summary(nodes, blocks, frontiers)},
        "scope": {"fixed_direct_producer_denominator_complete": True, "baseline_entries_treated_as_opaque": True, "runtime_reachability_complete": False, "global_function_entry_denominator_complete": False},
    }


def _validate_output_dir(root: Path, output_dir: Path) -> Path:
    root = Path(root).resolve(strict=True)
    requested = Path(output_dir).expanduser()
    if not requested.is_absolute():
        requested = root / requested
    output = _reject_symlink_components(requested).resolve(strict=False)
    if output == root or output in root.parents:
        raise ValueError("CFG proven-root v6 output cannot be repository root or ancestor")
    if not output.exists():
        return output
    if not output.is_dir():
        raise ValueError("CFG proven-root v6 output must be a directory")
    members = list(output.iterdir())
    if members and (
        {member.name for member in members} != {MANIFEST_NAME, PAYLOAD_NAME}
        or any(member.is_symlink() or not member.is_file() for member in members)
    ):
        raise ValueError("CFG proven-root v6 output is a foreign non-empty directory")
    return output


def export_rom_cfg_proven_roots_v6(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve(strict=True)
    output = _validate_output_dir(root, output_dir)
    payload = build_cfg_proven_roots_v6_payload(root); raw = _canonical_json(payload)
    manifest = {"artifact_schema": SCHEMA, "rom": payload["rom"], "producer_summary": {"count": 6}, "root_count": 5, "extension_summary": payload["extension"]["summary"], "files": {PAYLOAD_NAME: {"size": len(raw), "sha256": _sha(raw)}}}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".rom-cfg-proven-roots-v6-", dir=output.parent))
    try:
        (temporary / PAYLOAD_NAME).write_bytes(raw); (temporary / MANIFEST_NAME).write_bytes(_canonical_json(manifest))
        _validate_output_dir(root, temporary)
        _replace_output_dir(output, temporary); return manifest
    finally:
        if temporary.exists(): shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--root", type=Path, default=Path.cwd()); parser.add_argument("--output-dir", type=Path, required=True); args = parser.parse_args(); export_rom_cfg_proven_roots_v6(args.root, args.output_dir); return 0


if __name__ == "__main__": raise SystemExit(main())
