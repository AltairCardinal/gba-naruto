#!/usr/bin/env python3
"""Independently verify story-to-linked-BG bindings against the ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
STORY_OFFSET = 0x54229C
STORY_COUNT = 24
STORY_SIZE = 0x10
STORY_HASH = "33acbc117fa59c56d7af11728c6519367c9d5db177de75c199ec91c1c59ec289"
LINKED_OFFSET = 0x5A320C
LINKED_COUNT = 79
LINKED_SIZE = 0x44
LINKED_HASH = "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
SENTINELS = {13, 31, 32, 46}
STORY_PATH = Path("artifacts/story-visual-layers-v1")
LINKED_PATH = Path("artifacts/tile-assets-bg-v2")
SLICES = (
    ("background_initializer", 0x08065404, 0x08065554,
     "213423e70948ef3dbd91ed7854efb5c52fd7543f4b73b4a4a2219ffd89ce66f7"),
    ("story_sequence_and_overlay_resources", 0x08087C9C, 0x08087F00,
     "ade7e68ff00a726105c1df0af91315599c1dbb42402051a107e95e838adb262d"),
    ("linked_scene_install", 0x080990BC, 0x080995E8,
     "bf3db89f9e209f43a0dfe9987ff9e5c75681701317f8face799dc06523ae34ab"),
    ("linked_scene_update", 0x080995E8, 0x08099998,
     "080c71f2b421b09a1f176fd1e4d1baaa6b116068c67714616b3c4948a9c39f8a"),
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value, _sha(payload)


def _signed(value: int) -> int:
    return value - 256 if value & 0x80 else value


def _hardware(
    background: str,
    priority: int,
    charblock: int,
    screenblock: int,
    palette_bank: int,
    bits_per_pixel: int,
) -> dict[str, Any]:
    return {
        "background": background,
        "priority": priority,
        "charblock": charblock,
        "screenblock": screenblock,
        "palette_bank": palette_bank,
        "bits_per_pixel": bits_per_pixel,
    }


def _reference(
    descriptor_id: int,
    layer: dict[str, Any],
) -> dict[str, Any]:
    expected: dict[str, Any] = {
        "artifact": str(LINKED_PATH),
        "descriptor_id": descriptor_id,
        "name": layer["name"],
        "status": layer["status"],
        "bits_per_pixel": layer["bits_per_pixel"],
        "bytes_per_tile": layer["bytes_per_tile"],
        "palette_color_count": layer["palette_color_count"],
        "definition": layer["definition"],
    }
    if layer["status"] == "complete":
        expected.update(
            {
                "layer_png": layer["layer_png"],
                "layer_png_sha256": layer["layer_png_sha256"],
                "tile_count": layer["tile_count"],
                "gfx_sha256": layer["gfx"]["decompressed_sha256"],
                "tilemap_sha256": layer["tilemap"]["decompressed_sha256"],
                "palette_sha256": layer["palette"]["sha256"],
            }
        )
    return expected


def _expected_binding(
    story_index: int,
    config_id: int,
    story_layer: dict[str, Any],
    descriptor: dict[str, Any],
) -> dict[str, Any]:
    layers = {layer["name"]: layer for layer in descriptor["layers"]}
    raw = struct.pack(
        "<17I",
        *(int(word, 16) for word in descriptor["raw_words"]),
    )
    anchor_x, anchor_y, mode_x, mode_y = raw[:4]
    amplitude, flags = struct.unpack_from("<HH", raw, 4)
    swapped = bool(flags & 0x0200)
    layer_d = layers["D"]
    d_complete = layer_d["status"] == "complete"
    d_loaded = d_complete and not flags & 0x0400
    if not d_complete:
        d_state = "resource_absent"
    elif flags & 0x0400:
        d_state = "suppressed_by_descriptor_flag_0x0400"
    else:
        d_state = "loaded"

    return {
        "story_index": story_index,
        "config_id": config_id,
        "consumer_id": config_id + 1,
        "descriptor_flags": f"0x{flags:04X}",
        "motion": {
            "anchor_tiles": [anchor_x, anchor_y],
            "initial_pixels": [anchor_x * 8, anchor_y * 8],
            "direction": [_signed(mode_x), _signed(mode_y)],
            "amplitude": amplitude,
        },
        "excluded_layer_a": {
            "artifact": str(LINKED_PATH),
            "descriptor_id": config_id,
            "name": "A",
            "reason": "consumer_argument_path_not_used_by_story_installer",
        },
        "layers": [
            {
                "name": "story_overlay",
                "source": {
                    "artifact": str(STORY_PATH),
                    "layer_id": story_index,
                    "png": story_layer["png"],
                    "png_sha256": story_layer["png_sha256"],
                },
                "hardware": _hardware("BG3", 0, 3, 3, 15, 4),
                "resource_layout": {
                    "graphics_destination": "0x0600E800",
                    "tile_base": 0x140,
                    "tilemap_destination": "0x06001800",
                },
                "layout_consistency": {
                    "status": "resolved",
                    "initializer_bgcnt": "0x0300",
                    "story_override_bgcnt": "0x030C",
                    "story_override_gba_address": "0x08087CEA",
                    "configured_tile_address": "0x0600E800",
                    "graphics_destination": "0x0600E800",
                    "resource_address_implied_charblock": 3,
                    "reason": (
                        "story_override_selects_charblock_3_before_bg3_enable"
                    ),
                },
                "initially_enabled": False,
                "enabled_after_transition_frames": 90,
            },
            {
                "name": "B",
                "source": _reference(config_id, layers["B"]),
                "hardware": _hardware("BG2", 3, 3, 2, 12, 4),
                "resource_layout": {
                    "graphics_destination": "0x0600C000",
                    "tile_base": 0,
                    "tilemap_destination": "0x06001040",
                    "tilemap_size_tiles": [32, 14],
                },
                "resource_loaded": True,
                "initially_enabled": True,
            },
            {
                "name": "C",
                "source": _reference(config_id, layers["C"]),
                "hardware": _hardware(
                    "BG0", 1 if swapped else 2, 1, 0, 0, 8
                ),
                "resource_layout": {
                    "graphics_destination": "0x06004000",
                    "tile_base_expression": "state[0x16] >> 1",
                    "staging_stride_tiles": 64,
                },
                "resource_loaded": not bool(flags & 0x0100),
                "initially_enabled": not bool(flags & 0x0100),
            },
            {
                "name": "D",
                "source": _reference(config_id, layer_d),
                "hardware": _hardware(
                    "BG1", 2 if swapped else 1, 1, 1, 4, 4
                ),
                "resource_layout": {
                    "graphics_destination_base": "0x06004000",
                    "tile_base_expression": (
                        "u16(state[0x12] + state[0x16])"
                    ),
                    "staging_stride_tiles": 64,
                },
                "resource_loaded": d_loaded,
                "load_state": d_state,
                "initially_enabled": d_loaded and not flags & 0x0900,
            },
        ],
    }


def verify_story_scene_layer_bindings(
    root: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = root / artifact_dir
    errors: list[str] = []
    verified = 0

    try:
        rom = (root / "rom/base.gba").read_bytes()
        manifest = json.loads(
            (artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
        story, story_hash = _json(root / STORY_PATH / "manifest.json")
        linked, linked_hash = _json(root / LINKED_PATH / "manifest.json")
        if _sha(rom) != ROM_SHA256:
            raise ValueError("base ROM hash mismatch")
        story_table = rom[STORY_OFFSET : STORY_OFFSET + STORY_COUNT * STORY_SIZE]
        linked_table = rom[
            LINKED_OFFSET : LINKED_OFFSET + LINKED_COUNT * LINKED_SIZE
        ]
        if _sha(story_table) != STORY_HASH:
            raise ValueError("story table hash mismatch")
        if _sha(linked_table) != LINKED_HASH:
            raise ValueError("linked table hash mismatch")
        if story.get("schema") != "story-visual-layer-export-v1":
            raise ValueError("story artifact schema mismatch")
        if linked.get("schema") != "tile-assets-bg-export-v2":
            raise ValueError("linked artifact schema mismatch")
        for name, start, end, expected_hash in SLICES:
            if _sha(rom[start - ROM_BASE : end - ROM_BASE]) != expected_hash:
                raise ValueError(f"{name} consumer hash mismatch")

        expected_bindings = []
        used_sentinels = []
        for index in range(STORY_COUNT):
            row = struct.unpack_from("<4I", story_table, index * STORY_SIZE)
            config_id = row[3] & 0xFF
            if config_id >= LINKED_COUNT:
                raise ValueError("story config ID is out of range")
            if config_id in SENTINELS:
                used_sentinels.append(config_id)
            story_layer = story["layers"][index]
            descriptor = linked["descriptors"][config_id]
            if story_layer["config_id"] != config_id:
                raise ValueError("story artifact config mismatch")
            if descriptor["descriptor_id"] != config_id:
                raise ValueError("linked artifact descriptor mismatch")
            expected_bindings.append(
                _expected_binding(index, config_id, story_layer, descriptor)
            )

        expected = {
            "schema": "story-scene-layer-bindings-v1",
            "rom": {
                "path": "rom/base.gba",
                "size": len(rom),
                "sha256": _sha(rom),
            },
            "source_artifacts": {
                "story_visual_layers": {
                    "path": str(STORY_PATH),
                    "manifest_sha256": story_hash,
                    "schema": story["schema"],
                },
                "linked_tile_assets": {
                    "path": str(LINKED_PATH),
                    "manifest_sha256": linked_hash,
                    "schema": linked["schema"],
                },
            },
            "selection": {
                "story_table_gba_address": "0x0854229C",
                "linked_table_gba_address": "0x085A320C",
                "indexing": "direct_zero_based_config_id_times_0x44",
                "consumer_gba_address": "0x08087DE8",
                "consumer_slices": [
                    {
                        "name": name,
                        "start_gba_address": f"0x{start:08X}",
                        "end_gba_address_exclusive": f"0x{end:08X}",
                        "sha256": expected_hash,
                    }
                    for name, start, end, expected_hash in SLICES
                ],
            },
            "timing": {
                "linked_transition_frames_before_overlay": 90,
                "story_overlay_visible_frames": 240,
            },
            "scope": {
                "kind": "consumer-proven story scene layer bindings",
                "final_composite": False,
                "runtime_state_still_required": [
                    "scroll_and_wrap",
                    "blend_and_brightness",
                    "palette_transform",
                "dynamic_bg_enable",
                "shared_c_d_vram_state",
            ],
                "excluded_layer_a": True,
            },
            "binding_count": len(expected_bindings),
            "sentinel_config_ids": sorted(set(used_sentinels)),
            "bindings": expected_bindings,
        }
        if manifest != expected:
            errors.append("manifest does not match ROM-derived bindings")
        else:
            verified = len(expected_bindings)

        actual_files = {
            path.name for path in artifact_dir.iterdir() if path.is_file()
        }
        if actual_files != {"manifest.json"}:
            errors.append("artifact file set is not exactly manifest.json")

        for binding in expected_bindings:
            story_source = binding["layers"][0]["source"]
            story_png = root / STORY_PATH / story_source["png"]
            if _sha(story_png.read_bytes()) != story_source["png_sha256"]:
                raise ValueError("story PNG hash mismatch")
            for layer in binding["layers"][1:]:
                source = layer["source"]
                if source["status"] != "complete":
                    continue
                png = root / LINKED_PATH / source["layer_png"]
                if _sha(png.read_bytes()) != source["layer_png_sha256"]:
                    raise ValueError("linked layer PNG hash mismatch")
    except (KeyError, IndexError, OSError, TypeError, ValueError, struct.error) as error:
        errors.append(str(error))

    return {
        "schema": "story-scene-layer-bindings-verification-v1",
        "verified_bindings": verified,
        "errors": errors,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/story-scene-layer-bindings-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = verify_story_scene_layer_bindings(args.root, args.artifact_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
