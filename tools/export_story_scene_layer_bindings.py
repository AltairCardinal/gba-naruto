#!/usr/bin/env python3
"""Bind all 24 story overlays to their consumer-proven linked BG layers."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
STORY_TABLE_OFFSET = 0x54229C
STORY_ENTRY_COUNT = 24
STORY_ENTRY_SIZE = 0x10
STORY_TABLE_SHA256 = "33acbc117fa59c56d7af11728c6519367c9d5db177de75c199ec91c1c59ec289"
LINKED_TABLE_OFFSET = 0x5A320C
LINKED_ENTRY_COUNT = 79
LINKED_ENTRY_SIZE = 0x44
LINKED_TABLE_SHA256 = "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
SENTINEL_CONFIG_IDS = {13, 31, 32, 46}
STORY_ARTIFACT = Path("artifacts/story-visual-layers-v1")
LINKED_ARTIFACT = Path("artifacts/tile-assets-bg-v2")

CONSUMER_SLICES = (
    (
        "background_initializer",
        0x08065404,
        0x08065554,
        "213423e70948ef3dbd91ed7854efb5c52fd7543f4b73b4a4a2219ffd89ce66f7",
    ),
    (
        "story_sequence_and_overlay_resources",
        0x08087C9C,
        0x08087F00,
        "ade7e68ff00a726105c1df0af91315599c1dbb42402051a107e95e838adb262d",
    ),
    (
        "linked_scene_install",
        0x080990BC,
        0x080995E8,
        "bf3db89f9e209f43a0dfe9987ff9e5c75681701317f8face799dc06523ae34ab",
    ),
    (
        "linked_scene_update",
        0x080995E8,
        0x08099998,
        "080c71f2b421b09a1f176fd1e4d1baaa6b116068c67714616b3c4948a9c39f8a",
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value, _sha256(payload)


def _signed_byte(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def _layer_reference(
    descriptor_id: int,
    layer: dict[str, Any],
) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "artifact": str(LINKED_ARTIFACT),
        "descriptor_id": descriptor_id,
        "name": layer["name"],
        "status": layer["status"],
        "bits_per_pixel": layer["bits_per_pixel"],
        "bytes_per_tile": layer["bytes_per_tile"],
        "palette_color_count": layer["palette_color_count"],
        "definition": layer["definition"],
    }
    if layer["status"] == "complete":
        reference.update(
            {
                "layer_png": layer["layer_png"],
                "layer_png_sha256": layer["layer_png_sha256"],
                "tile_count": layer["tile_count"],
                "gfx_sha256": layer["gfx"]["decompressed_sha256"],
                "tilemap_sha256": layer["tilemap"]["decompressed_sha256"],
                "palette_sha256": layer["palette"]["sha256"],
            }
        )
    return reference


def _hardware(
    background: str,
    *,
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


def _build_manifest(
    rom: bytes,
    story_manifest: dict[str, Any],
    story_manifest_hash: str,
    linked_manifest: dict[str, Any],
    linked_manifest_hash: str,
) -> dict[str, Any]:
    story_table = rom[
        STORY_TABLE_OFFSET :
        STORY_TABLE_OFFSET + STORY_ENTRY_COUNT * STORY_ENTRY_SIZE
    ]
    linked_table = rom[
        LINKED_TABLE_OFFSET :
        LINKED_TABLE_OFFSET + LINKED_ENTRY_COUNT * LINKED_ENTRY_SIZE
    ]
    if _sha256(story_table) != STORY_TABLE_SHA256:
        raise ValueError("story descriptor table hash mismatch")
    if _sha256(linked_table) != LINKED_TABLE_SHA256:
        raise ValueError("linked descriptor table hash mismatch")
    if story_manifest.get("schema") != "story-visual-layer-export-v1":
        raise ValueError("unexpected story visual artifact schema")
    if linked_manifest.get("schema") != "tile-assets-bg-export-v2":
        raise ValueError("unexpected linked visual artifact schema")

    for name, start, end, expected_hash in CONSUMER_SLICES:
        actual_hash = _sha256(rom[start - 0x08000000 : end - 0x08000000])
        if actual_hash != expected_hash:
            raise ValueError(f"{name} consumer hash mismatch")

    story_layers = story_manifest.get("layers")
    linked_descriptors = linked_manifest.get("descriptors")
    if not isinstance(story_layers, list) or len(story_layers) != 24:
        raise ValueError("story artifact does not contain 24 layers")
    if not isinstance(linked_descriptors, list) or len(linked_descriptors) != 79:
        raise ValueError("linked artifact does not contain 79 descriptors")

    bindings: list[dict[str, Any]] = []
    used_sentinels: list[int] = []
    for story_index in range(STORY_ENTRY_COUNT):
        row = struct.unpack_from(
            "<4I",
            story_table,
            story_index * STORY_ENTRY_SIZE,
        )
        config_id = row[3] & 0xFF
        if config_id >= LINKED_ENTRY_COUNT:
            raise ValueError(f"story row {story_index} config is out of range")
        if config_id in SENTINEL_CONFIG_IDS:
            used_sentinels.append(config_id)

        story_layer = story_layers[story_index]
        if (
            story_layer.get("config_id") != config_id
            or story_layer.get("linked_visual_descriptor_id") != config_id
        ):
            raise ValueError(f"story artifact link mismatch at row {story_index}")
        descriptor = linked_descriptors[config_id]
        if descriptor.get("descriptor_id") != config_id:
            raise ValueError(f"linked descriptor ID mismatch at {config_id}")
        linked_layers = {
            layer["name"]: layer
            for layer in descriptor.get("layers", [])
            if isinstance(layer, dict) and "name" in layer
        }
        if set(linked_layers) != {"A", "B", "C", "D"}:
            raise ValueError(f"linked descriptor {config_id} lacks A/B/C/D")

        descriptor_bytes = struct.pack(
            "<17I",
            *(
                int(word, 16)
                for word in descriptor["raw_words"]
            ),
        )
        anchor_x, anchor_y, mode_x, mode_y = descriptor_bytes[:4]
        amplitude, flags = struct.unpack_from("<HH", descriptor_bytes, 4)
        priorities_swapped = bool(flags & 0x0200)

        layer_b = linked_layers["B"]
        layer_c = linked_layers["C"]
        layer_d = linked_layers["D"]
        d_complete = layer_d["status"] == "complete"
        d_loaded = d_complete and not flags & 0x0400
        if not d_complete:
            d_load_state = "resource_absent"
        elif flags & 0x0400:
            d_load_state = "suppressed_by_descriptor_flag_0x0400"
        else:
            d_load_state = "loaded"
        d_initially_enabled = d_loaded and not flags & 0x0900

        bindings.append(
            {
                "story_index": story_index,
                "config_id": config_id,
                "consumer_id": config_id + 1,
                "descriptor_flags": f"0x{flags:04X}",
                "motion": {
                    "anchor_tiles": [anchor_x, anchor_y],
                    "initial_pixels": [anchor_x * 8, anchor_y * 8],
                    "direction": [
                        _signed_byte(mode_x),
                        _signed_byte(mode_y),
                    ],
                    "amplitude": amplitude,
                },
                "excluded_layer_a": {
                    "artifact": str(LINKED_ARTIFACT),
                    "descriptor_id": config_id,
                    "name": "A",
                    "reason": (
                        "consumer_argument_path_not_used_by_story_installer"
                    ),
                },
                "layers": [
                    {
                        "name": "story_overlay",
                        "source": {
                            "artifact": str(STORY_ARTIFACT),
                            "layer_id": story_index,
                            "png": story_layer["png"],
                            "png_sha256": story_layer["png_sha256"],
                        },
                        "hardware": _hardware(
                            "BG3",
                            priority=0,
                            charblock=3,
                            screenblock=3,
                            palette_bank=15,
                            bits_per_pixel=4,
                        ),
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
                                "story_override_selects_charblock_3_before_"
                                "bg3_enable"
                            ),
                        },
                        "initially_enabled": False,
                        "enabled_at_wall_frame": 144,
                        "linked_state_frozen_at_tick": 106,
                        "visible_frames": 240,
                    },
                    {
                        "name": "B",
                        "source": _layer_reference(config_id, layer_b),
                        "hardware": _hardware(
                            "BG2",
                            priority=3,
                            charblock=3,
                            screenblock=2,
                            palette_bank=12,
                            bits_per_pixel=4,
                        ),
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
                        "source": _layer_reference(config_id, layer_c),
                        "hardware": _hardware(
                            "BG0",
                            priority=1 if priorities_swapped else 2,
                            charblock=1,
                            screenblock=0,
                            palette_bank=0,
                            bits_per_pixel=8,
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
                        "source": _layer_reference(config_id, layer_d),
                        "hardware": _hardware(
                            "BG1",
                            priority=2 if priorities_swapped else 1,
                            charblock=1,
                            screenblock=1,
                            palette_bank=4,
                            bits_per_pixel=4,
                        ),
                        "resource_layout": {
                            "graphics_destination_base": "0x06004000",
                            "tile_base_expression": (
                                "u16(state[0x12] + state[0x16])"
                            ),
                            "staging_stride_tiles": 64,
                        },
                        "resource_loaded": d_loaded,
                        "load_state": d_load_state,
                        "initially_enabled": d_initially_enabled,
                    },
                ],
            }
        )

    return {
        "schema": "story-scene-layer-bindings-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": _sha256(rom),
        },
        "source_artifacts": {
            "story_visual_layers": {
                "path": str(STORY_ARTIFACT),
                "manifest_sha256": story_manifest_hash,
                "schema": story_manifest["schema"],
            },
            "linked_tile_assets": {
                "path": str(LINKED_ARTIFACT),
                "manifest_sha256": linked_manifest_hash,
                "schema": linked_manifest["schema"],
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
                for name, start, end, expected_hash in CONSUMER_SLICES
            ],
        },
        "timing": {
            "installer_prelude_frames": 21,
            "installer_internal_update_ticks": 16,
            "controller_update_ticks": 90,
            "linked_update_ticks": 106,
            "palette_transform_frames": 16,
            "overlay_visible_frames": 240,
            "total_wall_frames": 383,
            "overlay_first_wall_frame": 144,
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
        "binding_count": len(bindings),
        "sentinel_config_ids": sorted(set(used_sentinels)),
        "bindings": bindings,
    }


def export_story_scene_layer_bindings(
    root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    rom = (root / "rom/base.gba").read_bytes()
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    story_manifest, story_hash = _load_json(
        root / STORY_ARTIFACT / "manifest.json"
    )
    linked_manifest, linked_hash = _load_json(
        root / LINKED_ARTIFACT / "manifest.json"
    )
    manifest = _build_manifest(
        rom,
        story_manifest,
        story_hash,
        linked_manifest,
        linked_hash,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output_dir / ".manifest.json.tmp"
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output_dir / "manifest.json")
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/story-scene-layer-bindings-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_story_scene_layer_bindings(args.root, args.output_dir)
    print(
        f"Exported {manifest['binding_count']} story scene bindings "
        f"to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
