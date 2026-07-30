#!/usr/bin/env python3
"""Independently verify the hash-bound staged RAM-to-GPU inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "rom-staged-gpu-copy-inventory-v1"
VERIFY_SCHEMA = "rom-staged-gpu-copy-inventory-verification-v1"
PAYLOAD_NAME = "rom-staged-gpu-copy-inventory.json"
ROM_PATH = Path("rom/base.gba")
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SOURCE_FILES = {
    "oam": Path(
        "artifacts/character-runtime-oam-task-bindings-v1/bindings.json"
    ),
    "oam_manifest": Path(
        "artifacts/character-runtime-oam-task-bindings-v1/manifest.json"
    ),
    "overview": Path(
        "artifacts/overview-gradient-overlay-v1/overview-gradient-overlay.json"
    ),
    "overview_manifest": Path(
        "artifacts/overview-gradient-overlay-v1/manifest.json"
    ),
    "status_bars": Path(
        "artifacts/battle-status-bars-v1/battle-status-bars.json"
    ),
    "status_bars_manifest": Path(
        "artifacts/battle-status-bars-v1/manifest.json"
    ),
}
EXPECTED_SCOPE = {
    "hash_bound_allowlisted_consumer_families_complete": True,
    "allowlisted_ram_slots_classified": True,
    "procedural_and_metadata_false_sources_excluded": True,
    "all_rom_to_ram_producers_complete": False,
    "all_ram_to_gpu_consumers_complete": False,
    "indirect_transfer_queue_abi_complete": False,
    "dialogue_tilemap_submit_complete": False,
    "custom_copy_loops_complete": False,
    "all_two_stage_copies_complete": False,
    "raw_uncompressed_graphics_complete": False,
    "generic_image_writeback_complete": False,
}
EXPECTED_SELECTION_RULE = {
    "allowlist_version": 1,
    "denominator": (
        "three previously proven consumer families whose RAM slot, GPU "
        "destination, length or formula, producer class and code hash are "
        "all fixed by accepted upstream artifacts"
    ),
    "accepted_raw_source": (
        "requires a separately proven ROM-to-RAM producer whose complete "
        "output range equals one allowlisted slot and whose downstream GPU "
        "copy is the same hash-bound contract"
    ),
    "process_generated_policy": "classify as procedural_excluded",
    "oam_metadata_policy": "classify as metadata_excluded",
    "checkpoint_byte_match_alone_is_sufficient": False,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(root: Path, path: Path) -> dict[str, Any]:
    return json.loads((root / path).read_text(encoding="utf-8"))


def _code_hash(rom: bytes, start: str, end: str) -> str:
    begin = int(start, 16) - ROM_BASE
    finish = int(end, 16) - ROM_BASE
    if begin < 0 or finish <= begin or finish > len(rom):
        raise ValueError(f"invalid code range {start}..{end}")
    return _sha(rom[begin:finish])


def _implementation(root: Path) -> dict[str, str]:
    return {
        "exporter_sha256": _sha(
            (root / "tools/export_rom_staged_gpu_copy_inventory.py").read_bytes()
        ),
        "verifier_sha256": _sha(
            (root / "tools/verify_rom_staged_gpu_copy_inventory.py").read_bytes()
        ),
        "test_sha256": _sha(
            (root / "tests/test_export_rom_staged_gpu_copy_inventory.py").read_bytes()
        ),
    }


def _expected_payload(root: Path) -> dict[str, Any]:
    rom = (root / ROM_PATH).read_bytes()
    if _sha(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    oam = _load(root, SOURCE_FILES["oam"])
    overview = _load(root, SOURCE_FILES["overview"])
    bars = _load(root, SOURCE_FILES["status_bars"])

    oam_contract = oam["static_contract"]
    oam_code = oam_contract["code_slices"]["vblank_callback"]
    if (
        oam_code
        != {
            "start": "0x080612BC",
            "end_exclusive": "0x080614EC",
            "size": 560,
            "sha256": "682fb5e1ca18c9155ce5f7541d152cb925c4046d9371b79a85cac4b12bc37d42",
        }
        or _code_hash(rom, oam_code["start"], oam_code["end_exclusive"])
        != oam_code["sha256"]
    ):
        raise ValueError("OAM callback contract mismatch")
    oam_routes = oam_contract["oam_submission"]["vblank_copy_routes"]
    expected_oam_routes = [
        {
            "kind": "cpu_fast_set",
            "callsite": "0x08061346",
            "source": "0x0300027C",
            "destination": "0x07000000",
            "control": "0x04000100",
            "size": 1024,
        },
        {
            "kind": "dma3",
            "callsite": "0x08061386",
            "source": "0x0300027C",
            "destination": "0x07000000",
            "control": "0x84000100",
            "size": 1024,
        },
    ]
    if oam_routes != expected_oam_routes:
        raise ValueError("OAM copy route mismatch")
    renderer_driver = oam_contract["code_slices"]["renderer_driver"]
    if (
        renderer_driver["start"] != "0x08062924"
        or renderer_driver["end_exclusive"] != "0x08063338"
        or _code_hash(
            rom, renderer_driver["start"], renderer_driver["end_exclusive"]
        )
        != renderer_driver["sha256"]
    ):
        raise ValueError("OAM producer contract mismatch")

    overview_code = overview["generator"]["code"]
    if (
        overview_code
        != {
            "gba_start": "0x0808D934",
            "gba_end_exclusive": "0x0808DA80",
            "size": 332,
            "sha256": "d5c6e7269c416817aae299d3d987c27abda6c1bde1a1edea0932329ce7179e96",
        }
        or _code_hash(
            rom,
            overview_code["gba_start"],
            overview_code["gba_end_exclusive"],
        )
        != overview_code["sha256"]
    ):
        raise ValueError("overview generator contract mismatch")
    overview_routes = overview["generator"]["copy_routes"]
    expected_overview_routes = [
        {
            "call": "0x0808D9C6",
            "destination": "0x06002000",
            "size": 352,
            "source": "0x02002AB0",
        },
        {
            "call": "0x0808DA0E",
            "destination": "0x050001A0",
            "size": 32,
            "source": "0x02002C10",
        },
        {
            "call": "0x0808DA6E",
            "destination": "0x06000000",
            "destination_stride_cells": 32,
            "dimensions": [30, 20],
            "source": "0x02002C30",
        },
    ]
    if (
        overview_routes != expected_overview_routes
        or overview["generated"]["tilemap"]["size"] != 1200
    ):
        raise ValueError("overview copy route mismatch")

    bars_code = bars["generator"]["code"]
    if (
        bars_code
        != {
            "gba_start": "0x08068370",
            "gba_end_exclusive": "0x08068642",
            "size": 722,
            "sha256": "13ef2ceedfe889bee6b7a6666d268246f43daa3fe5ad0be83a37f275e4ff4b20",
        }
        or _code_hash(
            rom, bars_code["gba_start"], bars_code["gba_end_exclusive"]
        )
        != bars_code["sha256"]
        or bars["generated"]["bytes_per_bar"] != 160
        or bars["generator"]["direct_calls"]
        != ["0x0806F0D6", "0x0806F0EC", "0x0807A83C", "0x0807A8A6"]
    ):
        raise ValueError("battle status generator contract mismatch")

    families = [
        {
            "id": "oam_shadow_submit_v1",
            "classification": "metadata_excluded",
            "classification_reason": (
                "The staged payload is OAM attribute metadata generated by "
                "the renderer, not tile or palette source bytes."
            ),
            "accepted_as_raw_rom_source": False,
            "code": oam_code,
            "producer": {
                "kind": "renderer_generated",
                "code": renderer_driver,
            },
            "ram_slots": [
                {
                    "name": "shadow_oam",
                    "start": "0x0300027C",
                    "end_exclusive": "0x0300067C",
                    "size": 1024,
                }
            ],
            "gpu_copy_routes": expected_oam_routes,
        },
        {
            "id": "overview_generated_bg0_v1",
            "classification": "procedural_excluded",
            "classification_reason": (
                "The generator algorithm creates tiles, palette and tilemap "
                "in EWRAM before copying them to GPU memory."
            ),
            "accepted_as_raw_rom_source": False,
            "code": {
                "start": overview_code["gba_start"],
                "end_exclusive": overview_code["gba_end_exclusive"],
                "size": overview_code["size"],
                "sha256": overview_code["sha256"],
            },
            "producer": {
                "kind": "algorithm_generated",
                "formulas": overview["generator"]["formulas"],
            },
            "ram_slots": [
                {
                    "name": "generated_tiles",
                    "start": "0x02002AB0",
                    "end_exclusive": "0x02002C10",
                    "size": 352,
                },
                {
                    "name": "generated_palette",
                    "start": "0x02002C10",
                    "end_exclusive": "0x02002C30",
                    "size": 32,
                },
                {
                    "name": "generated_tilemap",
                    "start": "0x02002C30",
                    "end_exclusive": "0x020030E0",
                    "size": 1200,
                },
            ],
            "gpu_copy_routes": [
                {
                    "kind": "cpu_copy",
                    "callsite": "0x0808D9C6",
                    "source": "0x02002AB0",
                    "destination": "0x06002000",
                    "size": 352,
                },
                {
                    "kind": "cpu_copy",
                    "callsite": "0x0808DA0E",
                    "source": "0x02002C10",
                    "destination": "0x050001A0",
                    "size": 32,
                },
                {
                    "kind": "cpu_copy",
                    "callsite": "0x0808DA6E",
                    "source": "0x02002C30",
                    "destination": "0x06000000",
                    "size": 1200,
                    "dimensions": [30, 20],
                    "destination_stride_cells": 32,
                },
            ],
        },
        {
            "id": "battle_status_bar_dynamic_bg_v1",
            "classification": "procedural_excluded",
            "classification_reason": (
                "Five output tiles are generated from an initializer template "
                "and a fill formula; the EWRAM buffer is not a ROM raw asset."
            ),
            "accepted_as_raw_rom_source": False,
            "code": {
                "start": bars_code["gba_start"],
                "end_exclusive": bars_code["gba_end_exclusive"],
                "size": bars_code["size"],
                "sha256": bars_code["sha256"],
            },
            "producer": {
                "kind": "algorithm_generated_from_vram_template",
                "formula": bars["generator"]["formula"],
                "direct_calls": bars["generator"]["direct_calls"],
            },
            "ram_slots": [
                {
                    "name": "generated_bar_tiles",
                    "start": "0x0201BD84",
                    "end_exclusive": "0x0201BE24",
                    "size": 160,
                }
            ],
            "gpu_copy_routes": [
                {
                    "kind": "five_tile_cpu_copy",
                    "source": "0x0201BD84 + tile_index*32",
                    "destination": "*0x0201BD48 + dynamic_tile_id*32",
                    "destination_kind": "dynamic_bg_vram",
                    "tile_count": 5,
                    "bytes_per_tile": 32,
                    "size": 160,
                }
            ],
        },
    ]
    summary = {
        "consumer_family_count": 3,
        "staged_ram_slot_count": 5,
        "gpu_copy_route_count": 6,
        "metadata_excluded_family_count": 1,
        "procedural_excluded_family_count": 2,
        "accepted_raw_source_count": 0,
        "new_raw_source_count": 0,
    }
    return {
        "schema": SCHEMA,
        "implementation": _implementation(root),
        "rom": {
            "path": ROM_PATH.as_posix(),
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "upstream_evidence": {
            name: {
                "path": path.as_posix(),
                "sha256": _sha((root / path).read_bytes()),
            }
            for name, path in sorted(SOURCE_FILES.items())
        },
        "selection_rule": EXPECTED_SELECTION_RULE,
        "summary": summary,
        "consumer_families": families,
        "accepted_raw_sources": [],
        "scope": EXPECTED_SCOPE,
    }


def _expected_manifest(
    payload: dict[str, Any], payload_bytes: bytes
) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {PAYLOAD_NAME: _sha(payload_bytes)},
        "scope": EXPECTED_SCOPE,
        "source": {
            "rom_sha256": ROM_SHA256,
            "upstream_evidence": payload["upstream_evidence"],
        },
        "producer": {
            "command": [
                "python3",
                "tools/export_rom_staged_gpu_copy_inventory.py",
                "--root",
                ".",
                "--output-dir",
                f"artifacts/{SCHEMA}",
            ],
            **payload["implementation"],
        },
        "verifier": {
            "command": [
                "python3",
                "tools/verify_rom_staged_gpu_copy_inventory.py",
                "--root",
                ".",
                "--artifact-dir",
                f"artifacts/{SCHEMA}",
            ],
            "verifier_sha256": payload["implementation"]["verifier_sha256"],
            "exit_code": 0,
            "report": {
                "schema": VERIFY_SCHEMA,
                "verified": True,
                "errors": [],
                "consumer_family_count": 3,
                "accepted_raw_source_count": 0,
            },
        },
    }


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    root = root.resolve()
    artifact = artifact.resolve()
    errors: list[str] = []
    try:
        if artifact.is_symlink() or not artifact.is_dir():
            raise ValueError("artifact directory is missing or unsafe")
        if any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact contains a symlink")
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_files != {PAYLOAD_NAME, "manifest.json"}:
            raise ValueError(f"unexpected artifact files: {sorted(actual_files)}")
        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_bytes)
        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        expected_payload = _expected_payload(root)
        expected_payload_bytes = (
            json.dumps(
                expected_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
        if payload != expected_payload:
            errors.append("payload does not match independently rebuilt contract")
        if payload_bytes != expected_payload_bytes:
            errors.append("payload bytes are not canonical")
        expected_manifest = _expected_manifest(
            expected_payload, expected_payload_bytes
        )
        if manifest != expected_manifest:
            errors.append("manifest does not match independently rebuilt contract")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    summary = (
        payload.get("summary", {})
        if "payload" in locals() and isinstance(payload, dict)
        else {}
    )
    return {
        "schema": VERIFY_SCHEMA,
        "verified": not errors,
        "errors": errors,
        "consumer_family_count": summary.get("consumer_family_count", 0),
        "accepted_raw_source_count": summary.get("accepted_raw_source_count", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--artifact-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    artifact = args.artifact_dir
    if not artifact.is_absolute():
        artifact = args.root / artifact
    report = verify_artifact(args.root, artifact)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.report:
        output = args.report
        if not output.is_absolute():
            output = args.root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
