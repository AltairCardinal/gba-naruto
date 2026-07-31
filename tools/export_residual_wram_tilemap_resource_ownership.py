#!/usr/bin/env python3
"""Export static BG/graphics/palette ownership for residual WRAM tilemaps."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.extract_tileset import lz77_decompress


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "residual-wram-tilemap-resource-ownership-v1"
ARTIFACT_ID = SCHEMA
PAYLOAD_NAME = "resource-ownership.json"
EXPECTED_FILES = {PAYLOAD_NAME, "manifest.json"}
ABI_PATH = Path(
    "artifacts/residual-wram-visual-metadata-abi-v2/"
    "residual-wram-visual-metadata-abi.json"
)
ABI_SHA256 = "4cee47ab097986d50ed0d3b3017fc4fd429037405ee247876022dfd08beac260"
SOURCE_ARTIFACTS = (
    (
        Path("artifacts/rom-pointer-lz77-graphics-v1/graphics-catalog.json"),
        "9c3088165fb65004dbeaa124a800d65795395e37b2dcfb90f2d2eedfdd6cf37d",
    ),
    (
        Path(
            "artifacts/residual-lz77-graphics-relocation-v1/"
            "full-relocation-spec.json"
        ),
        "757879fd57d32c9fd8dd7f66373b2fe533de83de0b3d3e479a6ca357f680187b",
    ),
    (
        Path(
            "artifacts/direct-image-palette-relocation-v1/"
            "full-relocation-spec.json"
        ),
        "555724a02c1b051279245970349158c829c367439676845e570dc497ed3470fa",
    ),
)
IMPLEMENTATION_PATHS = (
    "tools/extract_tileset.py",
    "tools/export_residual_wram_tilemap_resource_ownership.py",
    "tools/verify_residual_wram_tilemap_resource_ownership.py",
)


GRAPHICS = {
    0x08348F00: {
        "source_load": 0x0808B5D4,
        "load_call": 0x0808B5D8,
        "vram_destination": 0x06004000,
        "decompressed_size": 2176,
        "decompressed_sha256": (
            "1819e2bcbe0204fb3fe73907aab5fdbd"
            "561de0dfe7b8ccae316facc037357cae"
        ),
        "relocation_id": "residual-lz77-graphics-06",
    },
    0x085B6880: {
        "source_load": 0x0808BBCC,
        "load_call": 0x0808BBD0,
        "vram_destination": 0x0600C000,
        "decompressed_size": 8576,
        "decompressed_sha256": (
            "6d3edca8c66980c173fcd176240a029a"
            "2de532ab5d697d6682a18a2f2d96a715"
        ),
        "relocation_id": "residual-lz77-graphics-19",
    },
    0x08463688: {
        "source_load": 0x0809165A,
        "load_call": 0x0809165E,
        "vram_destination": 0x06009780,
        "decompressed_size": 3072,
        "decompressed_sha256": (
            "892ddfd26c50ca74564b24b32f34f14b"
            "bd20e7272c92762c72b084e32b4f55c6"
        ),
        "relocation_id": "residual-lz77-graphics-17",
    },
}

PALETTES = {
    0x0834941C: {
        "bank": 1,
        "source_load": 0x0808B5DC,
        "load_call": 0x0808B5E2,
        "pram_destination": 0x05000020,
        "sha256": "b5026d9f9be4c7a632a6ce2cb49b825cf6b735d60c256aeb7c1033e015379999",
    },
    0x083F0AF0: {
        "bank": 8,
        "source_load": 0x0808BBDC,
        "load_call": 0x0808BBE2,
        "pram_destination": 0x05000100,
        "sha256": "b11c213e0969ea51fb69f3b7060b5efcd06ce14b5ebf5c3c15c1955d07a8b50b",
    },
    0x083F1E60: {
        "bank": 9,
        "source_load": 0x0808BC00,
        "load_call": 0x0808BC06,
        "pram_destination": 0x05000120,
        "sha256": "19567cb1079d1340c6f018d9f3019069126f53f2e2577cc3a15765d96fe39de3",
    },
    0x083F1F08: {
        "bank": 10,
        "source_load": 0x0808BC20,
        "load_call": 0x0808BC26,
        "pram_destination": 0x05000140,
        "sha256": "48847c38fed3966e5ccea283d1e0d90e464cb6acad11e5788e62a8eeaf8d7c74",
    },
    0x084638D4: {
        "bank": 12,
        "source_load": 0x08091662,
        "load_call": 0x08091668,
        "pram_destination": 0x05000180,
        "sha256": "1a3f7ca023287acbbe2f4f7aa80e52160f687e5d791603a96e8c04ec13a155e7",
    },
    0x084638F4: {
        "bank": 13,
        "source_load": 0x0809166C,
        "load_call": 0x08091672,
        "pram_destination": 0x050001A0,
        "sha256": "107efd33b08a2dd2a61391231890a52f1be532fadcece5cc6516327d51adb3d3",
    },
}

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

SPECS = (
    {
        "tilemap": 0x0834928C,
        "bg_name": "BG0",
        "bg_register": 0x04000008,
        "bg_control": 0x0006,
        "graphics": 0x08348F00,
        "palette": 0x0834941C,
        "tile_add": 0,
        "scene_identity": "selection_grid_overlay",
        "setup_function": 0x0808B58C,
        "natural_callers": [0x0808F844, 0x0808FA04],
        "windows": ["selection_resource_setup", "selection_bg_setup"],
    },
    {
        "tilemap": 0x083F1C98,
        "bg_name": "BG1",
        "bg_register": 0x0400000A,
        "bg_control": 0x1F0D,
        "graphics": 0x085B6880,
        "palette": 0x083F0AF0,
        "tile_add": 0,
        "scene_identity": "scene_setup_bg1_upper_panel",
        "setup_function": 0x0808BAB0,
        "natural_callers": [0x0808F814],
        "windows": ["scene_bg_setup", "scene_resource_setup"],
    },
    {
        "tilemap": 0x085B67E0,
        "bg_name": "BG1",
        "bg_register": 0x0400000A,
        "bg_control": 0x1F0D,
        "graphics": 0x085B6880,
        "palette": 0x083F1E60,
        "tile_add": 0,
        "scene_identity": "scene_setup_bg1_lower_panel",
        "setup_function": 0x0808BAB0,
        "natural_callers": [0x0808F814],
        "windows": ["scene_bg_setup", "scene_resource_setup"],
    },
    {
        "tilemap": 0x083F2108,
        "bg_name": "BG2",
        "bg_register": 0x0400000C,
        "bg_control": 0x020F,
        "graphics": 0x085B6880,
        "palette": 0x083F1F08,
        "tile_add": 0,
        "scene_identity": "scene_setup_bg2_cropped_panel",
        "setup_function": 0x0808BAB0,
        "natural_callers": [0x0808F814],
        "windows": ["scene_bg_setup", "scene_resource_setup"],
    },
    {
        "tilemap": 0x084634B8,
        "bg_name": "BG1",
        "bg_register": 0x0400000A,
        "bg_control": 0x0105,
        "graphics": 0x08463688,
        "palette": 0x084638D4,
        "tile_add": 0x02BC,
        "scene_identity": "state_0200_0210_three_option_overlay_phase_a",
        "setup_function": 0x080914D8,
        "natural_callers": [0x0808F9E2, 0x0808F9EC],
        "windows": [
            "three_option_overlay_dispatch",
            "three_option_overlay_setup",
            "three_option_overlay_creator",
        ],
    },
    {
        "tilemap": 0x0846356C,
        "bg_name": "BG1",
        "bg_register": 0x0400000A,
        "bg_control": 0x0105,
        "graphics": 0x08463688,
        "palette": 0x084638F4,
        "tile_add": 0x02BC,
        "scene_identity": "state_0200_0210_three_option_overlay_phase_b_initial",
        "setup_function": 0x080914D8,
        "natural_callers": [0x0808F9E2, 0x0808F9EC],
        "windows": [
            "three_option_overlay_dispatch",
            "three_option_overlay_setup",
            "three_option_overlay_creator",
        ],
    },
    {
        "tilemap": 0x084635D8,
        "bg_name": "BG1",
        "bg_register": 0x0400000A,
        "bg_control": 0x0105,
        "graphics": 0x08463688,
        "palette": 0x084638F4,
        "tile_add": 0x02BC,
        "scene_identity": "state_0200_0210_three_option_overlay_phase_b_second",
        "setup_function": 0x080914D8,
        "natural_callers": [0x0808F9E2, 0x0808F9EC],
        "windows": [
            "three_option_overlay_dispatch",
            "three_option_overlay_setup",
            "three_option_overlay_creator",
        ],
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _window(rom: bytes, name: str) -> dict[str, str]:
    start, end, expected = WINDOWS[name]
    data = rom[start - ROM_BASE : end - ROM_BASE]
    actual = _sha256(data)
    if expected is not None and actual != expected:
        raise ValueError(f"code window {name} changed")
    return {
        "name": name,
        "start": _address(start),
        "end_exclusive": _address(end),
        "sha256": actual,
    }


def _bg(name: str, register: int, value: int) -> dict[str, Any]:
    charbase_index = (value >> 2) & 3
    screenbase_index = (value >> 8) & 31
    return {
        "name": name,
        "register": _address(register),
        "control_value": f"0x{value:04X}",
        "priority": value & 3,
        "charbase_index": charbase_index,
        "charbase_address": _address(0x06000000 + charbase_index * 0x4000),
        "screenbase_index": screenbase_index,
        "screenbase_address": _address(
            0x06000000 + screenbase_index * 0x800
        ),
        "color_mode": "4bpp" if not value & 0x80 else "8bpp",
        "size_code": (value >> 14) & 3,
    }


def _build_payload(root: Path) -> dict[str, Any]:
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 changed")
    abi_bytes = (root / ABI_PATH).read_bytes()
    if _sha256(abi_bytes) != ABI_SHA256:
        raise ValueError("residual WRAM visual metadata ABI changed")
    abi = json.loads(abi_bytes)
    abi_records = {
        int(row["source_pointer"], 16): row
        for row in abi["tilemap_sources"]
    }
    if set(abi_records) != {row["tilemap"] for row in SPECS}:
        raise ValueError("tilemap ownership denominator changed")
    source_artifacts = []
    for path, expected_hash in SOURCE_ARTIFACTS:
        data = (root / path).read_bytes()
        if _sha256(data) != expected_hash:
            raise ValueError(f"source artifact changed: {path}")
        source_artifacts.append(
            {"path": path.as_posix(), "sha256": expected_hash}
        )

    windows = {name: _window(rom, name) for name in WINDOWS}
    graphics_cache: dict[int, dict[str, Any]] = {}
    for pointer, spec in GRAPHICS.items():
        decoded = lz77_decompress(rom, pointer - ROM_BASE)
        if (
            len(decoded) != spec["decompressed_size"]
            or _sha256(decoded) != spec["decompressed_sha256"]
        ):
            raise ValueError(f"graphics payload changed: {_address(pointer)}")
        graphics_cache[pointer] = {
            "source_pointer": _address(pointer),
            "source_load": _address(spec["source_load"]),
            "load_call": _address(spec["load_call"]),
            "load_route": "LZ77UnCompVram_wrapper",
            "vram_destination": _address(spec["vram_destination"]),
            "decompressed_size": len(decoded),
            "decompressed_sha256": _sha256(decoded),
            "tile_bytes": 32,
            "tile_count": len(decoded) // 32,
            "relocation_artifact": (
                "artifacts/residual-lz77-graphics-relocation-v1/"
                "full-relocation-spec.json"
            ),
            "relocation_id": spec["relocation_id"],
        }

    palette_cache: dict[int, dict[str, Any]] = {}
    for pointer, spec in PALETTES.items():
        data = rom[pointer - ROM_BASE : pointer - ROM_BASE + 32]
        if _sha256(data) != spec["sha256"]:
            raise ValueError(f"palette payload changed: {_address(pointer)}")
        palette_cache[pointer] = {
            "source_pointer": _address(pointer),
            "source_load": _address(spec["source_load"]),
            "load_call": _address(spec["load_call"]),
            "load_route": "CpuSet_wrapper",
            "pram_destination": _address(spec["pram_destination"]),
            "bank": spec["bank"],
            "size": 32,
            "sha256": spec["sha256"],
            "relocation_artifact": (
                "artifacts/direct-image-palette-relocation-v1/"
                "full-relocation-spec.json"
            ),
        }

    records = []
    for spec in SPECS:
        abi_record = abi_records[spec["tilemap"]]
        source_range = abi_record["tilemap"]["tile_index_range"]
        effective_range = [
            source_range[0] + spec["tile_add"],
            source_range[1] + spec["tile_add"],
        ]
        bg = _bg(
            spec["bg_name"],
            spec["bg_register"],
            spec["bg_control"],
        )
        graphics = graphics_cache[spec["graphics"]]
        charbase = int(bg["charbase_address"], 16)
        loaded_at = int(graphics["vram_destination"], 16)
        loaded_range = [
            (loaded_at - charbase) // 32,
            (loaded_at - charbase) // 32 + graphics["tile_count"] - 1,
        ]
        if (
            loaded_at < charbase
            or (loaded_at - charbase) % 32
            or effective_range[0] < loaded_range[0]
            or effective_range[1] > loaded_range[1]
        ):
            raise ValueError("tilemap effective range exceeds graphics load")
        palette = palette_cache[spec["palette"]]
        if (
            abi_record["tilemap"]["palette_banks"] != [palette["bank"]]
            or int(palette["pram_destination"], 16)
            != 0x05000000 + palette["bank"] * 32
        ):
            raise ValueError("tilemap palette ownership mismatch")
        record_graphics = dict(graphics)
        record_graphics["loaded_tile_index_range"] = loaded_range
        records.append(
            {
                "tilemap_source_pointer": _address(spec["tilemap"]),
                "tilemap_abi_sha256": abi_record["decompressed_sha256"],
                "tilemap_classification": abi_record["classification"],
                "vram_destination": abi_record["vram_destination"],
                "source_tile_index_range": source_range,
                "tile_index_add": spec["tile_add"],
                "effective_tile_index_range": effective_range,
                "bg": bg,
                "graphics": record_graphics,
                "palettes": [dict(palette)],
                "scene_identity": spec["scene_identity"],
                "evidence_level": "static_proved",
                "setup_function": _address(spec["setup_function"]),
                "natural_callers": [
                    _address(value) for value in spec["natural_callers"]
                ],
                "code_windows": [
                    windows[name] for name in spec["windows"]
                ],
            }
        )

    summary = {
        "tilemap_source_count": len(records),
        "bg_control_complete_count": len(records),
        "graphics_ownership_complete_count": len(records),
        "palette_ownership_complete_count": len(records),
        "remaining_unresolved_count": 0,
    }
    scope = {
        "graphics_and_palette_ownership_complete": True,
        "bg_control_ownership_complete": True,
        "static_natural_caller_chain_complete": True,
        "exact_natural_language_menu_identity_complete": False,
        "queue_slot_and_natural_flush_complete": False,
        "runtime_reachability_complete": False,
        "final_screen_pixel_and_timing_equivalence_complete": False,
    }
    return {
        "schema": SCHEMA,
        "rom": {"path": "rom/base.gba", "sha256": ROM_SHA256},
        "tilemap_abi": {
            "path": ABI_PATH.as_posix(),
            "sha256": ABI_SHA256,
        },
        "source_artifacts": source_artifacts,
        "summary": summary,
        "scope": scope,
        "ownership_records": records,
        "remaining_unresolved": [],
    }


def export_artifact(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    if output.exists():
        existing = {
            path.relative_to(output).as_posix()
            for path in output.rglob("*")
            if path.is_file()
        }
        foreign = existing - EXPECTED_FILES
        if foreign:
            raise ValueError(f"output contains foreign files: {sorted(foreign)}")
    output.mkdir(parents=True, exist_ok=True)
    payload = _build_payload(root)
    payload_bytes = _canonical_json(payload)
    (output / PAYLOAD_NAME).write_bytes(payload_bytes)
    implementation = {
        relative: _sha256((root / relative).read_bytes())
        for relative in IMPLEMENTATION_PATHS
    }
    manifest = {
        "schema": "git-artifact-promotion-v1",
        "artifact_id": ARTIFACT_ID,
        "artifact_schema": SCHEMA,
        "artifact_status": "accepted",
        "payload_file": PAYLOAD_NAME,
        "payload_sha256": _sha256(payload_bytes),
        "files": {PAYLOAD_NAME: _sha256(payload_bytes)},
        "implementation": implementation,
        "summary": payload["summary"],
        "scope": payload["scope"],
        "verifier": {
            "command": [
                "python3",
                "tools/verify_residual_wram_tilemap_resource_ownership.py",
                "--root",
                ".",
                "--artifact",
                f"artifacts/{ARTIFACT_ID}",
            ],
            "exit_code": 0,
        },
    }
    (output / "manifest.json").write_bytes(_canonical_json(manifest))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    payload = export_artifact(args.root, args.output)
    print(json.dumps(payload["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
