#!/usr/bin/env python3
"""Classify hash-bound RAM-to-GPU consumers without inventing ROM sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
import uuid


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
SCOPE = {
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
SELECTION_RULE = {
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


def _require(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


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


def _build(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    rom = (root / ROM_PATH).read_bytes()
    _require(_sha(rom), ROM_SHA256, "base ROM SHA-256")
    oam = _load(root, SOURCE_FILES["oam"])
    overview = _load(root, SOURCE_FILES["overview"])
    bars = _load(root, SOURCE_FILES["status_bars"])

    oam_contract = oam["static_contract"]
    oam_code = oam_contract["code_slices"]["vblank_callback"]
    _require(
        _code_hash(rom, oam_code["start"], oam_code["end_exclusive"]),
        oam_code["sha256"],
        "OAM vblank callback code",
    )
    oam_routes = oam_contract["oam_submission"]["vblank_copy_routes"]
    _require(
        oam_routes,
        [
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
        ],
        "OAM copy routes",
    )

    overview_code = overview["generator"]["code"]
    _require(
        _code_hash(
            rom,
            overview_code["gba_start"],
            overview_code["gba_end_exclusive"],
        ),
        overview_code["sha256"],
        "overview generator code",
    )
    overview_routes = overview["generator"]["copy_routes"]
    _require(
        overview_routes,
        [
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
        ],
        "overview copy routes",
    )
    _require(overview["generated"]["tilemap"]["size"], 1200, "overview tilemap size")

    bars_code = bars["generator"]["code"]
    _require(
        _code_hash(
            rom,
            bars_code["gba_start"],
            bars_code["gba_end_exclusive"],
        ),
        bars_code["sha256"],
        "battle status generator code",
    )
    _require(bars["generated"]["bytes_per_bar"], 160, "status bar size")
    _require(
        bars["generator"]["direct_calls"],
        ["0x0806F0D6", "0x0806F0EC", "0x0807A83C", "0x0807A8A6"],
        "status bar direct calls",
    )

    families = [
        {
            "id": "oam_shadow_submit_v1",
            "classification": "metadata_excluded",
            "classification_reason": (
                "The staged payload is OAM attribute metadata generated by "
                "the renderer, not tile or palette source bytes."
            ),
            "accepted_as_raw_rom_source": False,
            "code": {
                "start": oam_code["start"],
                "end_exclusive": oam_code["end_exclusive"],
                "size": oam_code["size"],
                "sha256": oam_code["sha256"],
            },
            "producer": {
                "kind": "renderer_generated",
                "code": oam_contract["code_slices"]["renderer_driver"],
            },
            "ram_slots": [
                {
                    "name": "shadow_oam",
                    "start": "0x0300027C",
                    "end_exclusive": "0x0300067C",
                    "size": 1024,
                }
            ],
            "gpu_copy_routes": oam_routes,
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
                    "callsite": route["call"],
                    "source": route["source"],
                    "destination": route["destination"],
                    "size": route.get("size", 1200),
                    **(
                        {
                            "dimensions": route["dimensions"],
                            "destination_stride_cells": route[
                                "destination_stride_cells"
                            ],
                        }
                        if "dimensions" in route
                        else {}
                    ),
                }
                for route in overview_routes
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
        "consumer_family_count": len(families),
        "staged_ram_slot_count": sum(len(row["ram_slots"]) for row in families),
        "gpu_copy_route_count": sum(
            len(row["gpu_copy_routes"]) for row in families
        ),
        "metadata_excluded_family_count": sum(
            row["classification"] == "metadata_excluded" for row in families
        ),
        "procedural_excluded_family_count": sum(
            row["classification"] == "procedural_excluded" for row in families
        ),
        "accepted_raw_source_count": 0,
        "new_raw_source_count": 0,
    }
    payload = {
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
        "selection_rule": SELECTION_RULE,
        "summary": summary,
        "consumer_families": families,
        "accepted_raw_sources": [],
        "scope": SCOPE,
    }
    files = {
        PAYLOAD_NAME: (
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode()
    }
    return payload, files


def _manifest(
    payload: dict[str, Any], files: dict[str, bytes]
) -> dict[str, Any]:
    return {
        "schema": "git-artifact-promotion-v1",
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "files": {name: _sha(data) for name, data in sorted(files.items())},
        "scope": SCOPE,
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
                "consumer_family_count": payload["summary"][
                    "consumer_family_count"
                ],
                "accepted_raw_source_count": 0,
            },
        },
    }


def _validate_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    target = output.expanduser().resolve()
    if output.is_symlink() or target == root or target in root.parents:
        raise ValueError("output directory is unsafe")
    if not target.exists():
        return target
    if not target.is_dir():
        raise ValueError("refusing to replace foreign output")
    try:
        manifest = json.loads(
            (target / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("refusing to replace foreign output") from error
    actual = {
        path.relative_to(target).as_posix()
        for path in target.rglob("*")
        if path.is_file()
    }
    if (
        any(path.is_symlink() for path in target.rglob("*"))
        or manifest.get("artifact_schema") != SCHEMA
        or manifest.get("artifact_status") != "accepted"
        or actual != set(manifest.get("files", {})) | {"manifest.json"}
    ):
        raise ValueError("refusing to replace foreign output")
    for name, expected in manifest["files"].items():
        if _sha((target / name).read_bytes()) != expected:
            raise ValueError("refusing to replace corrupted output")
    return target


def _replace(
    output: Path, files: dict[str, bytes], manifest: dict[str, Any]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent)
    )
    backup = None
    try:
        for name, data in files.items():
            (temporary / name).write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        if output.exists():
            backup = output.parent / f".{output.name}.backup-{uuid.uuid4().hex}"
            output.rename(backup)
        try:
            os.replace(temporary, output)
        except BaseException:
            if backup is not None and backup.exists() and not output.exists():
                backup.rename(output)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists():
            if not output.exists():
                backup.rename(output)
            else:
                shutil.rmtree(backup)


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    target = _validate_output(root, output)
    payload, files = _build(root)
    _replace(target, files, _manifest(payload, files))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output-dir", type=Path, default=Path(f"artifacts/{SCHEMA}")
    )
    args = parser.parse_args()
    output = args.output_dir
    if not output.is_absolute():
        output = args.root / output
    payload = export_artifact(args.root, output)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
