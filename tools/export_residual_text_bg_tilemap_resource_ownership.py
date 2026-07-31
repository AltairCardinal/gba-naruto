#!/usr/bin/env python3
"""Export static ownership for the residual text-BG tilemap."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import read_lz77_record


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "residual-text-bg-tilemap-resource-ownership-v1"
PAYLOAD_NAME = "resource-ownership.json"
SOURCE_ARTIFACTS = {
    "artifacts/rom-pointer-lz77-inventory-v1/"
    "rom-pointer-lz77-inventory.json": (
        "0c4aed52328b0506e8e41afebe5e5c0ef3dccb830cf8af6c092eb1d0566581c5"
    ),
    "artifacts/rom-pointer-lz77-graphics-v1/graphics-catalog.json": (
        "9c3088165fb65004dbeaa124a800d65795395e37b2dcfb90f2d2eedfdd6cf37d"
    ),
    "artifacts/residual-lz77-graphics-relocation-v1/"
    "full-relocation-spec.json": (
        "757879fd57d32c9fd8dd7f66373b2fe533de83de0b3d3e479a6ca357f680187b"
    ),
    "artifacts/direct-image-palette-relocation-v1/"
    "full-relocation-spec.json": (
        "555724a02c1b051279245970349158c829c367439676845e570dc497ed3470fa"
    ),
}
IMPLEMENTATION_PATHS = (
    "tools/extract_tileset.py",
    "tools/gba_image_export.py",
    "tools/export_residual_text_bg_tilemap_resource_ownership.py",
    "tools/verify_residual_text_bg_tilemap_resource_ownership.py",
)
WINDOWS = {
    "selection_resource_setup": (
        0x0808B5C2,
        0x0808B5E6,
    ),
    "text_bg_setup": (
        0x0808B2EA,
        0x0808B356,
    ),
    "text_bg_loop_link": (
        0x0808B640,
        0x0808B64E,
    ),
    "selection_entry_a": (
        0x0808F844,
        0x0808F848,
    ),
    "selection_entry_b": (
        0x0808FA04,
        0x0808FA08,
    ),
}
SCOPE = {
    "bg_control_ownership_complete": True,
    "graphics_and_palette_ownership_complete": True,
    "static_natural_caller_chain_complete": True,
    "remaining_screenblock_rows_complete": False,
    "runtime_order_against_vram_reusers_complete": False,
    "runtime_reachability_complete": False,
    "exact_natural_language_screen_identity_complete": False,
    "final_screen_pixel_and_timing_equivalence_complete": False,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _code_windows(rom: bytes) -> list[dict[str, Any]]:
    result = []
    for name, (start, end) in WINDOWS.items():
        data = rom[start - ROM_BASE : end - ROM_BASE]
        result.append(
            {
                "name": name,
                "start": _address(start),
                "end_exclusive": _address(end),
                "sha256": _sha256(data),
            }
        )
    return result


def _ownership_record(rom: bytes) -> dict[str, Any]:
    tilemap_pointer = 0x08349368
    tilemap_record = read_lz77_record(
        rom,
        tilemap_pointer - ROM_BASE,
        expected_size=1280,
    )
    tilemap = lz77_decompress(rom, tilemap_pointer - ROM_BASE)
    entries = struct.unpack("<640H", tilemap)
    tile_range = [
        min(value & 0x03FF for value in entries),
        max(value & 0x03FF for value in entries),
    ]
    palette_banks = sorted({value >> 12 for value in entries})

    graphics_pointer = 0x08348F00
    graphics_record = read_lz77_record(
        rom,
        graphics_pointer - ROM_BASE,
        expected_size=2176,
    )
    graphics = lz77_decompress(rom, graphics_pointer - ROM_BASE)
    palette_pointer = 0x0834941C
    palette = rom[
        palette_pointer - ROM_BASE : palette_pointer - ROM_BASE + 32
    ]
    return {
        "tilemap_source_pointer": _address(tilemap_pointer),
        "tilemap_classification": "text_bg_tilemap",
        "tilemap_compressed_size": len(tilemap_record),
        "tilemap_compressed_sha256": _sha256(tilemap_record),
        "tilemap_decompressed_size": len(tilemap),
        "tilemap_decompressed_sha256": _sha256(tilemap),
        "geometry": {"width_entries": 32, "height_entries": 20},
        "vram_destination": "0x06001000",
        "tile_index_range": tile_range,
        "palette_banks": palette_banks,
        "horizontal_flip_count": sum(bool(value & 0x0400) for value in entries),
        "vertical_flip_count": sum(bool(value & 0x0800) for value in entries),
        "bg": {
            "name": "BG2",
            "register": "0x0400000C",
            "control_value": "0x0204",
            "priority": 0,
            "charbase_index": 1,
            "charbase_address": "0x06004000",
            "screenbase_index": 2,
            "screenbase_address": "0x06001000",
            "color_mode": "4bpp",
            "size_code": 0,
            "display_shadow": "0x0300004C",
            "display_enable_or_mask": "0x0500",
        },
        "graphics": {
            "source_pointer": _address(graphics_pointer),
            "source_load": "0x0808B5D4",
            "load_call": "0x0808B5D8",
            "load_route": "LZ77UnCompVram_wrapper",
            "vram_destination": "0x06004000",
            "compressed_size": len(graphics_record),
            "compressed_sha256": _sha256(graphics_record),
            "decompressed_size": len(graphics),
            "decompressed_sha256": _sha256(graphics),
            "tile_bytes": 32,
            "tile_count": len(graphics) // 32,
            "loaded_tile_index_range": [0, len(graphics) // 32 - 1],
            "relocation_artifact": (
                "artifacts/residual-lz77-graphics-relocation-v1/"
                "full-relocation-spec.json"
            ),
            "relocation_id": "residual-lz77-graphics-06",
        },
        "palette": {
            "source_pointer": _address(palette_pointer),
            "source_load": "0x0808B5DC",
            "load_call": "0x0808B5E2",
            "load_route": "CpuSet_wrapper",
            "pram_destination": "0x05000020",
            "bank": 1,
            "size": len(palette),
            "sha256": _sha256(palette),
            "relocation_artifact": (
                "artifacts/direct-image-palette-relocation-v1/"
                "full-relocation-spec.json"
            ),
        },
        "tilemap_source_load": "0x0808B348",
        "tilemap_load_call": "0x0808B34C",
        "tilemap_load_route": "LZ77UnCompVram_wrapper",
        "resource_setup_function": "0x0808B58C",
        "tilemap_setup_function": "0x0808B2C8",
        "setup_link_call": "0x0808B640",
        "natural_entry_callers": ["0x0808F844", "0x0808FA04"],
        "scene_identity": "selection_flow_text_bg_panel",
        "evidence_level": "static_proved",
        "code_windows": _code_windows(rom),
    }


def export_ownership(root: Path, output: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    for path, digest in SOURCE_ARTIFACTS.items():
        if _sha256((root / path).read_bytes()) != digest:
            raise ValueError(f"source artifact changed: {path}")
    record = _ownership_record(rom)
    if not (
        record["tile_index_range"][0]
        >= record["graphics"]["loaded_tile_index_range"][0]
        and record["tile_index_range"][1]
        <= record["graphics"]["loaded_tile_index_range"][1]
        and record["palette_banks"] == [record["palette"]["bank"]]
    ):
        raise ValueError("tilemap entries exceed owned graphics or palette")
    summary = {
        "tilemap_source_count": 1,
        "bg_control_complete_count": 1,
        "graphics_ownership_complete_count": 1,
        "palette_ownership_complete_count": 1,
        "remaining_unresolved_count": 0,
    }
    payload = {
        "schema": SCHEMA,
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "source_artifacts": [
            {"path": path, "sha256": digest}
            for path, digest in SOURCE_ARTIFACTS.items()
        ],
        "summary": summary,
        "ownership_record": record,
        "remaining_unresolved": [],
        "scope": SCOPE,
    }
    payload_bytes = _canonical_json(payload)
    (output / PAYLOAD_NAME).write_bytes(payload_bytes)
    payload_hash = _sha256(payload_bytes)
    implementation = {
        relative: _sha256((root / relative).read_bytes())
        for relative in IMPLEMENTATION_PATHS
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": SCHEMA,
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": payload_hash,
        "files": {PAYLOAD_NAME: payload_hash},
        "implementation": implementation,
        "summary": summary,
        "scope": SCOPE,
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_text_bg_tilemap_resource_ownership.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{SCHEMA}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_bytes(_canonical_json(manifest))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"artifacts/{SCHEMA}"),
    )
    args = parser.parse_args()
    payload = export_ownership(args.root, args.output)
    print(json.dumps(payload["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
