#!/usr/bin/env python3
"""Independently verify residual WRAM tilemap resource ownership."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "residual-wram-tilemap-resource-ownership-v1"
PAYLOAD_NAME = "resource-ownership.json"
EXPECTED_FILES = {PAYLOAD_NAME, "manifest.json"}
ABI_PATH = (
    "artifacts/residual-wram-visual-metadata-abi-v2/"
    "residual-wram-visual-metadata-abi.json"
)
ABI_SHA256 = "4cee47ab097986d50ed0d3b3017fc4fd429037405ee247876022dfd08beac260"
SOURCE_ARTIFACTS = {
    "artifacts/rom-pointer-lz77-graphics-v1/graphics-catalog.json": (
        "9c3088165fb65004dbeaa124a800d65795395e37b2dcfb90f2d2eedfdd6cf37d"
    ),
    (
        "artifacts/residual-lz77-graphics-relocation-v1/"
        "full-relocation-spec.json"
    ): "757879fd57d32c9fd8dd7f66373b2fe533de83de0b3d3e479a6ca357f680187b",
    (
        "artifacts/direct-image-palette-relocation-v1/"
        "full-relocation-spec.json"
    ): "555724a02c1b051279245970349158c829c367439676845e570dc497ed3470fa",
}
IMPLEMENTATION_PATHS = (
    "tools/extract_tileset.py",
    "tools/export_residual_wram_tilemap_resource_ownership.py",
    "tools/verify_residual_wram_tilemap_resource_ownership.py",
)
WINDOWS = {
    "selection_resource_setup": (
        0x0808B5C2,
        0x0808B5E6,
        "97b9cdcaf6e092990995efabea800a38851f01d06ca60696906a8d5e706ba129",
    ),
    "selection_bg_setup": (
        0x0808ACF2,
        0x0808AD08,
        "8320604211493d5be52f4450d2dee2fb3f418429731ef9dadb177b6326145157",
    ),
    "scene_bg_setup": (
        0x0808BAF4,
        0x0808BB0C,
        "8060a9f9ea88d19209616ea8b83183b31b3d5459f2e1e988a3939b012d6b3622",
    ),
    "scene_resource_setup": (
        0x0808BBCC,
        0x0808BC38,
        "09e0b41f0153a93aeb58590a5ce04462c37a35a2ea3eeefd81f7c7ffc75768de",
    ),
    "three_option_overlay_setup": (
        0x0809163E,
        0x08091676,
        "0790e7fa21116a9185026ee2b63df2674967730440459e710247ce8a4bbb6c24",
    ),
    "three_option_overlay_dispatch": (
        0x0808F9E2,
        0x0808FA00,
        "3c80bae909b940fb752934ed51820e7bcbad14ae9a83c242140ab076cdb561bd",
    ),
    "three_option_overlay_creator": (
        0x08091000,
        0x0809106C,
        "78031d7d87306ccc9a6753a73c94f09fe02b4572dac55df56fe446377e11bfd6",
    ),
}
EXPECTED = {
    0x0834928C: {
        "scene_identity": "selection_grid_overlay",
        "bg": ("BG0", 0x04000008, 0x0006),
        "graphics": (
            0x08348F00,
            0x0808B5D4,
            0x0808B5D8,
            0x06004000,
            2176,
            "1819e2bcbe0204fb3fe73907aab5fdbd561de0dfe7b8ccae316facc037357cae",
            "residual-lz77-graphics-06",
        ),
        "palette": (
            0x0834941C,
            1,
            0x0808B5DC,
            0x0808B5E2,
            0x05000020,
            "b5026d9f9be4c7a632a6ce2cb49b825cf6b735d60c256aeb7c1033e015379999",
        ),
        "tile_add": 0,
        "setup": 0x0808B58C,
        "callers": [0x0808F844, 0x0808FA04],
        "windows": ["selection_resource_setup", "selection_bg_setup"],
    },
    0x083F1C98: {
        "scene_identity": "scene_setup_bg1_upper_panel",
        "bg": ("BG1", 0x0400000A, 0x1F0D),
        "graphics": (
            0x085B6880,
            0x0808BBCC,
            0x0808BBD0,
            0x0600C000,
            8576,
            "6d3edca8c66980c173fcd176240a029a2de532ab5d697d6682a18a2f2d96a715",
            "residual-lz77-graphics-19",
        ),
        "palette": (
            0x083F0AF0,
            8,
            0x0808BBDC,
            0x0808BBE2,
            0x05000100,
            "b11c213e0969ea51fb69f3b7060b5efcd06ce14b5ebf5c3c15c1955d07a8b50b",
        ),
        "tile_add": 0,
        "setup": 0x0808BAB0,
        "callers": [0x0808F814],
        "windows": ["scene_bg_setup", "scene_resource_setup"],
    },
    0x085B67E0: {
        "scene_identity": "scene_setup_bg1_lower_panel",
        "bg": ("BG1", 0x0400000A, 0x1F0D),
        "graphics": (
            0x085B6880,
            0x0808BBCC,
            0x0808BBD0,
            0x0600C000,
            8576,
            "6d3edca8c66980c173fcd176240a029a2de532ab5d697d6682a18a2f2d96a715",
            "residual-lz77-graphics-19",
        ),
        "palette": (
            0x083F1E60,
            9,
            0x0808BC00,
            0x0808BC06,
            0x05000120,
            "19567cb1079d1340c6f018d9f3019069126f53f2e2577cc3a15765d96fe39de3",
        ),
        "tile_add": 0,
        "setup": 0x0808BAB0,
        "callers": [0x0808F814],
        "windows": ["scene_bg_setup", "scene_resource_setup"],
    },
    0x083F2108: {
        "scene_identity": "scene_setup_bg2_cropped_panel",
        "bg": ("BG2", 0x0400000C, 0x020F),
        "graphics": (
            0x085B6880,
            0x0808BBCC,
            0x0808BBD0,
            0x0600C000,
            8576,
            "6d3edca8c66980c173fcd176240a029a2de532ab5d697d6682a18a2f2d96a715",
            "residual-lz77-graphics-19",
        ),
        "palette": (
            0x083F1F08,
            10,
            0x0808BC20,
            0x0808BC26,
            0x05000140,
            "48847c38fed3966e5ccea283d1e0d90e464cb6acad11e5788e62a8eeaf8d7c74",
        ),
        "tile_add": 0,
        "setup": 0x0808BAB0,
        "callers": [0x0808F814],
        "windows": ["scene_bg_setup", "scene_resource_setup"],
    },
    0x084634B8: {
        "scene_identity": "state_0200_0210_three_option_overlay_phase_a",
        "bg": ("BG1", 0x0400000A, 0x0105),
        "graphics": (
            0x08463688,
            0x0809165A,
            0x0809165E,
            0x06009780,
            3072,
            "892ddfd26c50ca74564b24b32f34f14bbd20e7272c92762c72b084e32b4f55c6",
            "residual-lz77-graphics-17",
        ),
        "palette": (
            0x084638D4,
            12,
            0x08091662,
            0x08091668,
            0x05000180,
            "1a3f7ca023287acbbe2f4f7aa80e52160f687e5d791603a96e8c04ec13a155e7",
        ),
        "tile_add": 0x02BC,
        "setup": 0x080914D8,
        "callers": [0x0808F9E2, 0x0808F9EC],
        "windows": [
            "three_option_overlay_dispatch",
            "three_option_overlay_setup",
            "three_option_overlay_creator",
        ],
    },
    0x0846356C: {
        "scene_identity": (
            "state_0200_0210_three_option_overlay_phase_b_initial"
        ),
        "bg": ("BG1", 0x0400000A, 0x0105),
        "graphics": (
            0x08463688,
            0x0809165A,
            0x0809165E,
            0x06009780,
            3072,
            "892ddfd26c50ca74564b24b32f34f14bbd20e7272c92762c72b084e32b4f55c6",
            "residual-lz77-graphics-17",
        ),
        "palette": (
            0x084638F4,
            13,
            0x0809166C,
            0x08091672,
            0x050001A0,
            "107efd33b08a2dd2a61391231890a52f1be532fadcece5cc6516327d51adb3d3",
        ),
        "tile_add": 0x02BC,
        "setup": 0x080914D8,
        "callers": [0x0808F9E2, 0x0808F9EC],
        "windows": [
            "three_option_overlay_dispatch",
            "three_option_overlay_setup",
            "three_option_overlay_creator",
        ],
    },
    0x084635D8: {
        "scene_identity": (
            "state_0200_0210_three_option_overlay_phase_b_second"
        ),
        "bg": ("BG1", 0x0400000A, 0x0105),
        "graphics": (
            0x08463688,
            0x0809165A,
            0x0809165E,
            0x06009780,
            3072,
            "892ddfd26c50ca74564b24b32f34f14bbd20e7272c92762c72b084e32b4f55c6",
            "residual-lz77-graphics-17",
        ),
        "palette": (
            0x084638F4,
            13,
            0x0809166C,
            0x08091672,
            0x050001A0,
            "107efd33b08a2dd2a61391231890a52f1be532fadcece5cc6516327d51adb3d3",
        ),
        "tile_add": 0x02BC,
        "setup": 0x080914D8,
        "callers": [0x0808F9E2, 0x0808F9EC],
        "windows": [
            "three_option_overlay_dispatch",
            "three_option_overlay_setup",
            "three_option_overlay_creator",
        ],
    },
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _lz77(rom: bytes, pointer: int) -> bytes:
    offset = pointer - ROM_BASE
    if rom[offset] != 0x10:
        raise ValueError(f"not LZ77: {_address(pointer)}")
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
                displacement = (token & 0x0FFF) + 1
                if displacement > len(output):
                    raise ValueError("invalid LZ77 displacement")
                for _ in range(length):
                    output.append(output[-displacement])
                    if len(output) >= expected:
                        break
            else:
                output.append(rom[cursor])
                cursor += 1
    return bytes(output)


def _validate_record(
    rom: bytes,
    abi_record: dict[str, Any],
    record: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    expected_keys = {
        "tilemap_source_pointer",
        "tilemap_abi_sha256",
        "tilemap_classification",
        "vram_destination",
        "source_tile_index_range",
        "tile_index_add",
        "effective_tile_index_range",
        "bg",
        "graphics",
        "palettes",
        "scene_identity",
        "evidence_level",
        "setup_function",
        "natural_callers",
        "code_windows",
    }
    if set(record) != expected_keys:
        raise ValueError("ownership record field inventory mismatch")
    source = int(record["tilemap_source_pointer"], 16)
    if record["tilemap_abi_sha256"] != abi_record["decompressed_sha256"]:
        raise ValueError("tilemap ABI hash mismatch")
    if record["tilemap_classification"] != abi_record["classification"]:
        raise ValueError("tilemap classification mismatch")
    if record["vram_destination"] != abi_record["vram_destination"]:
        raise ValueError("tilemap VRAM destination mismatch")
    if record["scene_identity"] != expected["scene_identity"]:
        raise ValueError("scene identity mismatch")
    tilemap = _lz77(rom, source)
    entries = struct.unpack(f"<{len(tilemap) // 2}H", tilemap)
    source_range = [min(v & 0x03FF for v in entries), max(v & 0x03FF for v in entries)]
    banks = sorted({v >> 12 for v in entries})
    if source_range != record["source_tile_index_range"]:
        raise ValueError("source tile range mismatch")
    if record["tile_index_add"] != expected["tile_add"]:
        raise ValueError("tile index transform mismatch")
    effective = [value + expected["tile_add"] for value in source_range]
    if record["effective_tile_index_range"] != effective:
        raise ValueError("effective tile range mismatch")

    bg_name, register, control = expected["bg"]
    charbase_index = (control >> 2) & 3
    screenbase_index = (control >> 8) & 31
    bg_expected = {
        "name": bg_name,
        "register": _address(register),
        "control_value": f"0x{control:04X}",
        "priority": control & 3,
        "charbase_index": charbase_index,
        "charbase_address": _address(0x06000000 + charbase_index * 0x4000),
        "screenbase_index": screenbase_index,
        "screenbase_address": _address(0x06000000 + screenbase_index * 0x800),
        "color_mode": "4bpp",
        "size_code": (control >> 14) & 3,
    }
    if record["bg"] != bg_expected:
        raise ValueError("BG ownership mismatch")

    (
        graphics_source,
        source_load,
        load_call,
        vram_destination,
        decoded_size,
        decoded_hash,
        relocation_id,
    ) = expected["graphics"]
    graphics_data = _lz77(rom, graphics_source)
    if len(graphics_data) != decoded_size or _sha256(graphics_data) != decoded_hash:
        raise ValueError("graphics bytes mismatch")
    tile_count = decoded_size // 32
    charbase = 0x06000000 + charbase_index * 0x4000
    loaded_first = (vram_destination - charbase) // 32
    graphics_expected = {
        "source_pointer": _address(graphics_source),
        "source_load": _address(source_load),
        "load_call": _address(load_call),
        "load_route": "LZ77UnCompVram_wrapper",
        "vram_destination": _address(vram_destination),
        "decompressed_size": decoded_size,
        "decompressed_sha256": decoded_hash,
        "tile_bytes": 32,
        "tile_count": tile_count,
        "relocation_artifact": (
            "artifacts/residual-lz77-graphics-relocation-v1/"
            "full-relocation-spec.json"
        ),
        "relocation_id": relocation_id,
        "loaded_tile_index_range": [
            loaded_first,
            loaded_first + tile_count - 1,
        ],
    }
    if record["graphics"] != graphics_expected:
        raise ValueError("graphics ownership mismatch")
    if effective[0] < loaded_first or effective[1] >= loaded_first + tile_count:
        raise ValueError("effective tiles exceed owned graphics")

    (
        palette_source,
        bank,
        palette_load,
        palette_call,
        pram_destination,
        palette_hash,
    ) = expected["palette"]
    palette_data = rom[
        palette_source - ROM_BASE : palette_source - ROM_BASE + 32
    ]
    if _sha256(palette_data) != palette_hash or banks != [bank]:
        raise ValueError("palette bytes or bank mismatch")
    palette_expected = {
        "source_pointer": _address(palette_source),
        "source_load": _address(palette_load),
        "load_call": _address(palette_call),
        "load_route": "CpuSet_wrapper",
        "pram_destination": _address(pram_destination),
        "bank": bank,
        "size": 32,
        "sha256": palette_hash,
        "relocation_artifact": (
            "artifacts/direct-image-palette-relocation-v1/"
            "full-relocation-spec.json"
        ),
    }
    if record["palettes"] != [palette_expected]:
        raise ValueError("palette ownership mismatch")
    if pram_destination != 0x05000000 + bank * 32:
        raise ValueError("palette destination does not match bank")
    if record["setup_function"] != _address(expected["setup"]):
        raise ValueError("setup function mismatch")
    if record["natural_callers"] != [
        _address(value) for value in expected["callers"]
    ]:
        raise ValueError("natural caller chain mismatch")
    code_windows = record["code_windows"]
    if [row["name"] for row in code_windows] != expected["windows"]:
        raise ValueError("code window inventory mismatch")
    for row in code_windows:
        start, end, digest = WINDOWS[row["name"]]
        if row != {
            "name": row["name"],
            "start": _address(start),
            "end_exclusive": _address(end),
            "sha256": digest,
        }:
            raise ValueError("code window metadata mismatch")
        if _sha256(rom[start - ROM_BASE : end - ROM_BASE]) != digest:
            raise ValueError("code window bytes mismatch")
    if record["evidence_level"] != "static_proved":
        raise ValueError("evidence level mismatch")


def verify_artifact(root: Path, artifact: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = root.resolve()
        artifact = artifact.resolve()
        actual_files = {
            path.relative_to(artifact).as_posix()
            for path in artifact.rglob("*")
            if path.is_file()
        }
        if actual_files != EXPECTED_FILES:
            raise ValueError("artifact file inventory mismatch")
        if any(path.is_symlink() for path in artifact.rglob("*")):
            raise ValueError("artifact contains symbolic links")
        rom = (root / "rom/base.gba").read_bytes()
        if _sha256(rom) != ROM_SHA256:
            raise ValueError("base ROM SHA-256 changed")
        abi_bytes = (root / ABI_PATH).read_bytes()
        if _sha256(abi_bytes) != ABI_SHA256:
            raise ValueError("tilemap ABI changed")
        abi = json.loads(abi_bytes)
        abi_records = {
            int(row["source_pointer"], 16): row
            for row in abi["tilemap_sources"]
        }
        if set(abi_records) != set(EXPECTED):
            raise ValueError("tilemap ownership denominator changed")
        for path, digest in SOURCE_ARTIFACTS.items():
            if _sha256((root / path).read_bytes()) != digest:
                raise ValueError(f"source artifact changed: {path}")

        payload_bytes = (artifact / PAYLOAD_NAME).read_bytes()
        payload = json.loads(payload_bytes)
        if payload_bytes != _canonical_json(payload):
            raise ValueError("payload canonical serialization mismatch")
        expected_summary = {
            "tilemap_source_count": 7,
            "bg_control_complete_count": 7,
            "graphics_ownership_complete_count": 7,
            "palette_ownership_complete_count": 7,
            "remaining_unresolved_count": 0,
        }
        expected_scope = {
            "graphics_and_palette_ownership_complete": True,
            "bg_control_ownership_complete": True,
            "static_natural_caller_chain_complete": True,
            "exact_natural_language_menu_identity_complete": False,
            "queue_slot_and_natural_flush_complete": False,
            "runtime_reachability_complete": False,
            "final_screen_pixel_and_timing_equivalence_complete": False,
        }
        expected_sources = [
            {"path": path, "sha256": digest}
            for path, digest in SOURCE_ARTIFACTS.items()
        ]
        if (
            payload.get("schema") != SCHEMA
            or payload.get("rom")
            != {"path": "rom/base.gba", "sha256": ROM_SHA256}
            or payload.get("tilemap_abi")
            != {"path": ABI_PATH, "sha256": ABI_SHA256}
            or payload.get("source_artifacts") != expected_sources
            or payload.get("summary") != expected_summary
            or payload.get("scope") != expected_scope
            or payload.get("remaining_unresolved") != []
        ):
            raise ValueError("payload top-level contract mismatch")
        records = {
            int(row["tilemap_source_pointer"], 16): row
            for row in payload["ownership_records"]
        }
        if set(records) != set(EXPECTED) or len(records) != 7:
            raise ValueError("ownership record denominator mismatch")
        for pointer, expected in EXPECTED.items():
            _validate_record(
                rom,
                abi_records[pointer],
                records[pointer],
                expected,
            )

        manifest = json.loads(
            (artifact / "manifest.json").read_text(encoding="utf-8")
        )
        payload_hash = _sha256(payload_bytes)
        expected_verifier = {
            "command": [
                "python3",
                "tools/verify_residual_wram_tilemap_resource_ownership.py",
                "--root",
                ".",
                "--artifact",
                "artifacts/residual-wram-tilemap-resource-ownership-v1",
            ],
            "exit_code": 0,
        }
        implementation = {
            relative: _sha256((root / relative).read_bytes())
            for relative in IMPLEMENTATION_PATHS
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
            or manifest.get("summary") != expected_summary
            or manifest.get("scope") != expected_scope
            or manifest.get("verifier") != expected_verifier
        ):
            raise ValueError("manifest contract mismatch")
    except Exception as error:
        errors.append(str(error))
    return {
        "schema": (
            "residual-wram-tilemap-resource-ownership-verification-v1"
        ),
        "verified": not errors,
        "verified_ownership_records": 0 if errors else 7,
        "remaining_unresolved": 7 if errors else 0,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path(
            "artifacts/residual-wram-tilemap-resource-ownership-v1"
        ),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
