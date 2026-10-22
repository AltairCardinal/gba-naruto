#!/usr/bin/env python3
"""Independently verify residual text-BG tilemap resource ownership."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


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
        "97b9cdcaf6e092990995efabea800a38851f01d06ca60696906a8d5e706ba129",
    ),
    "text_bg_setup": (
        0x0808B2EA,
        0x0808B356,
        "1c06792a63713ba899c935e9862c8cc8ff54171be9b76dee5451e1dde51c1a2f",
    ),
    "text_bg_loop_link": (
        0x0808B640,
        0x0808B64E,
        "3eb118d7e7bd1903555a54065c5331d05e04b3233ab66051575a66a89977d3ba",
    ),
    "selection_entry_a": (
        0x0808F844,
        0x0808F848,
        "b54d2c5ad70dcc190b662533c5877838c7753da5395f9c274e93e8caf6ad56ff",
    ),
    "selection_entry_b": (
        0x0808FA04,
        0x0808FA08,
        "c824488f54f856316626a62f6d001f5c1125ffe715f5f3d072db8dc1b3a926d1",
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
SUMMARY = {
    "tilemap_source_count": 1,
    "bg_control_complete_count": 1,
    "graphics_ownership_complete_count": 1,
    "palette_ownership_complete_count": 1,
    "remaining_unresolved_count": 0,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _lz77(rom: bytes, pointer: int) -> tuple[bytes, bytes]:
    offset = pointer - ROM_BASE
    if rom[offset] != 0x10:
        raise ValueError(f"not LZ77: 0x{pointer:08X}")
    expected = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < expected:
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= expected:
                break
            if flags & (1 << bit):
                token = struct.unpack_from(">H", rom, cursor)[0]
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0x0FFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ77 distance")
                for _ in range(length):
                    output.append(output[-distance])
                    if len(output) >= expected:
                        break
            else:
                output.append(rom[cursor])
                cursor += 1
    return bytes(output), rom[offset:cursor]


def _u16(rom: bytes, address: int) -> int:
    return struct.unpack_from("<H", rom, address - ROM_BASE)[0]


def _u32(rom: bytes, address: int) -> int:
    return struct.unpack_from("<I", rom, address - ROM_BASE)[0]


def _thumb_bl_target(rom: bytes, address: int) -> int:
    first = _u16(rom, address)
    second = _u16(rom, address + 2)
    if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
        raise ValueError(f"not Thumb BL at 0x{address:08X}")
    high = first & 0x07FF
    if high & 0x0400:
        high -= 0x0800
    return address + 4 + (high << 12) + ((second & 0x07FF) << 1)


def _literal_value(rom: bytes, address: int, register: int) -> int:
    instruction = _u16(rom, address)
    if (
        instruction & 0xF800 != 0x4800
        or (instruction >> 8) & 7 != register
    ):
        raise ValueError(f"literal load changed at 0x{address:08X}")
    literal = ((address + 4) & ~3) + (instruction & 0xFF) * 4
    return _u32(rom, literal)


def _validate_static_semantics(rom: bytes) -> dict[str, Any]:
    entry_callers = (0x0808F844, 0x0808FA04)
    if any(
        _thumb_bl_target(rom, caller) != 0x0808B58C
        for caller in entry_callers
    ):
        raise ValueError("natural entry caller target mismatch")
    try:
        setup_target = _thumb_bl_target(rom, 0x0808B640)
    except ValueError as error:
        raise ValueError("setup link encoding mismatch") from error
    if setup_target != 0x0808B2C8:
        raise ValueError("setup link target mismatch")
    calls = {
        0x0808B5D8: 0x0809C0E8,
        0x0808B5E2: 0x0809C0E0,
        0x0808B34C: 0x0809C0E8,
    }
    for callsite, target in calls.items():
        if _thumb_bl_target(rom, callsite) != target:
            raise ValueError(f"loader target mismatch at 0x{callsite:08X}")

    graphics_source = _literal_value(rom, 0x0808B5D4, 0)
    graphics_destination = _literal_value(rom, 0x0808B5D6, 1)
    palette_source = _literal_value(rom, 0x0808B5DC, 0)
    palette_destination = _literal_value(rom, 0x0808B5DE, 1)
    tilemap_source = _literal_value(rom, 0x0808B348, 0)
    tilemap_destination = _literal_value(rom, 0x0808B34A, 1)
    if (
        graphics_source != 0x08348F00
        or graphics_destination != 0x06004000
        or palette_source != 0x0834941C
        or palette_destination != 0x05000020
        or tilemap_source != 0x08349368
        or tilemap_destination != 0x06001000
    ):
        raise ValueError("resource literal route mismatch")

    bg_base = _literal_value(rom, 0x0808B2F4, 1)
    if (
        _u16(rom, 0x0808B2F6) != 0x2003
        or _u16(rom, 0x0808B2F8) != 0x8008
        or _u16(rom, 0x0808B2FA) != 0x3104
        or _u16(rom, 0x0808B300) != 0x1C10
        or _u16(rom, 0x0808B302) != 0x8008
    ):
        raise ValueError("BG2 control instruction shape mismatch")
    move = _u16(rom, 0x0808B2FC)
    shift = _u16(rom, 0x0808B2FE)
    if move & 0xFF00 != 0x2200 or shift & 0xFFC0 != 0x0080:
        raise ValueError("BG2 control construction mismatch")
    bg2_control = (move & 0xFF) << ((shift >> 6) & 0x1F)
    if bg_base + 4 != 0x0400000C or bg2_control != 0x0204:
        raise ValueError("BG2 control semantic mismatch")

    display_shadow = _literal_value(rom, 0x0808B304, 2)
    mask_move = _u16(rom, 0x0808B308)
    mask_shift = _u16(rom, 0x0808B30A)
    if (
        display_shadow != 0x0300004C
        or mask_move & 0xFF00 != 0x2300
        or mask_shift & 0xFFC0 != 0x00C0
    ):
        raise ValueError("display enable construction mismatch")
    display_mask = (mask_move & 0xFF) << ((mask_shift >> 6) & 0x1F)
    if display_mask != 0x0500:
        raise ValueError("display enable mask mismatch")
    return {
        "entry_callers": list(entry_callers),
        "resource_setup": 0x0808B58C,
        "tilemap_setup": 0x0808B2C8,
        "setup_link": 0x0808B640,
        "graphics_source": graphics_source,
        "graphics_destination": graphics_destination,
        "palette_source": palette_source,
        "palette_destination": palette_destination,
        "tilemap_source": tilemap_source,
        "tilemap_destination": tilemap_destination,
        "bg_register": bg_base + 4,
        "bg_control": bg2_control,
        "display_shadow": display_shadow,
        "display_mask": display_mask,
    }


def _expected_record(rom: bytes) -> dict[str, Any]:
    semantics = _validate_static_semantics(rom)
    tilemap, tilemap_record = _lz77(rom, semantics["tilemap_source"])
    entries = struct.unpack("<640H", tilemap)
    graphics, graphics_record = _lz77(rom, semantics["graphics_source"])
    palette = rom[
        semantics["palette_source"]
        - ROM_BASE : semantics["palette_source"]
        - ROM_BASE
        + 32
    ]
    windows = []
    for name, (start, end, digest) in WINDOWS.items():
        data = rom[start - ROM_BASE : end - ROM_BASE]
        if _sha256(data) != digest:
            raise ValueError(f"code window changed: {name}")
        windows.append(
            {
                "name": name,
                "start": f"0x{start:08X}",
                "end_exclusive": f"0x{end:08X}",
                "sha256": digest,
            }
        )
    return {
        "tilemap_source_pointer": f"0x{semantics['tilemap_source']:08X}",
        "tilemap_classification": "text_bg_tilemap",
        "tilemap_compressed_size": len(tilemap_record),
        "tilemap_compressed_sha256": _sha256(tilemap_record),
        "tilemap_decompressed_size": len(tilemap),
        "tilemap_decompressed_sha256": _sha256(tilemap),
        "geometry": {"width_entries": 32, "height_entries": 20},
        "vram_destination": f"0x{semantics['tilemap_destination']:08X}",
        "tile_index_range": [
            min(value & 0x03FF for value in entries),
            max(value & 0x03FF for value in entries),
        ],
        "palette_banks": sorted({value >> 12 for value in entries}),
        "horizontal_flip_count": sum(bool(value & 0x0400) for value in entries),
        "vertical_flip_count": sum(bool(value & 0x0800) for value in entries),
        "bg": {
            "name": "BG2",
            "register": f"0x{semantics['bg_register']:08X}",
            "control_value": f"0x{semantics['bg_control']:04X}",
            "priority": 0,
            "charbase_index": 1,
            "charbase_address": "0x06004000",
            "screenbase_index": 2,
            "screenbase_address": "0x06001000",
            "color_mode": "4bpp",
            "size_code": 0,
            "display_shadow": f"0x{semantics['display_shadow']:08X}",
            "display_enable_or_mask": f"0x{semantics['display_mask']:04X}",
        },
        "graphics": {
            "source_pointer": f"0x{semantics['graphics_source']:08X}",
            "source_load": "0x0808B5D4",
            "load_call": "0x0808B5D8",
            "load_route": "LZ77UnCompVram_wrapper",
            "vram_destination": (
                f"0x{semantics['graphics_destination']:08X}"
            ),
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
            "source_pointer": f"0x{semantics['palette_source']:08X}",
            "source_load": "0x0808B5DC",
            "load_call": "0x0808B5E2",
            "load_route": "CpuSet_wrapper",
            "pram_destination": f"0x{semantics['palette_destination']:08X}",
            "bank": 1,
            "size": 32,
            "sha256": _sha256(palette),
            "relocation_artifact": (
                "artifacts/direct-image-palette-relocation-v1/"
                "full-relocation-spec.json"
            ),
        },
        "tilemap_source_load": "0x0808B348",
        "tilemap_load_call": "0x0808B34C",
        "tilemap_load_route": "LZ77UnCompVram_wrapper",
        "resource_setup_function": f"0x{semantics['resource_setup']:08X}",
        "tilemap_setup_function": f"0x{semantics['tilemap_setup']:08X}",
        "setup_link_call": f"0x{semantics['setup_link']:08X}",
        "natural_entry_callers": [
            f"0x{value:08X}" for value in semantics["entry_callers"]
        ],
        "scene_identity": "selection_flow_text_bg_panel",
        "evidence_level": "static_proved",
        "code_windows": windows,
    }


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = Path(root).resolve()
        artifact = Path(artifact).resolve()
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_files != {PAYLOAD_NAME, "manifest.json"}:
            raise ValueError("artifact file inventory mismatch")
        if any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact contains symbolic links")
        rom = (root / "rom/base.gba").read_bytes()
        if _sha256(rom) != ROM_SHA256:
            raise ValueError("base ROM SHA-256 changed")
        for path, digest in SOURCE_ARTIFACTS.items():
            if _sha256((root / path).read_bytes()) != digest:
                raise ValueError(f"source artifact changed: {path}")

        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_bytes)
        if payload_bytes != _canonical_json(payload):
            raise ValueError("payload canonical serialization mismatch")
        expected_sources = [
            {"path": path, "sha256": digest}
            for path, digest in SOURCE_ARTIFACTS.items()
        ]
        if (
            payload.get("schema") != SCHEMA
            or payload.get("rom")
            != {"path": "rom/base.gba", "sha256": ROM_SHA256}
            or payload.get("source_artifacts") != expected_sources
            or payload.get("summary") != SUMMARY
            or payload.get("ownership_record") != _expected_record(rom)
            or payload.get("remaining_unresolved") != []
            or payload.get("scope") != SCOPE
            or set(payload)
            != {
                "schema",
                "rom",
                "source_artifacts",
                "summary",
                "ownership_record",
                "remaining_unresolved",
                "scope",
            }
        ):
            raise ValueError("payload contract mismatch")
        record = payload["ownership_record"]
        if (
            record["tile_index_range"][0]
            < record["graphics"]["loaded_tile_index_range"][0]
            or record["tile_index_range"][1]
            > record["graphics"]["loaded_tile_index_range"][1]
            or record["palette_banks"] != [record["palette"]["bank"]]
        ):
            raise ValueError("owned tiles or palette do not cover tilemap")

        manifest = json.loads((artifact / "manifest.json").read_bytes())
        payload_hash = _sha256(payload_bytes)
        implementation = {
            relative: _sha256((root / relative).read_bytes())
            for relative in IMPLEMENTATION_PATHS
        }
        expected_verifier = {
            "command": [
                "python3",
                "tools/verify_residual_text_bg_tilemap_resource_ownership.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{SCHEMA}",
            ],
            "exit_code": 0,
        }
        if (
            manifest.get("schema") != "git-artifact-promotion-v1"
            or manifest.get("artifact_id") != SCHEMA
            or manifest.get("artifact_schema") != SCHEMA
            or manifest.get("artifact_status") != "accepted"
            or manifest.get("payload_file") != PAYLOAD_NAME
            or manifest.get("payload_sha256") != payload_hash
            or manifest.get("files") != {PAYLOAD_NAME: payload_hash}
            or manifest.get("implementation") != implementation
            or manifest.get("summary") != SUMMARY
            or manifest.get("scope") != SCOPE
            or manifest.get("verifier") != expected_verifier
        ):
            raise ValueError("manifest contract mismatch")
    except Exception as error:
        errors.append(str(error))
    return {
        "schema": (
            "residual-text-bg-tilemap-resource-ownership-verification-v1"
        ),
        "verified": not errors,
        "verified_ownership_records": 0 if errors else 1,
        "remaining_unresolved": 1 if errors else 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(f"artifacts/{SCHEMA}"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
