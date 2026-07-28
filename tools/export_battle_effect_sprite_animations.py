#!/usr/bin/env python3
"""Export every battle-effect child sprite frame and animation timeline."""

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

from tools.gba_image_export import (
    indexed_png_from_bgr555,
    render_4bpp_tile_block_indices,
)


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
RESOURCE_TABLE_OFFSET = 0x59911C
SPRITE_PAIR_TABLE_OFFSET = 0x5991B4
TABLE_ENTRY_COUNT = 19
TABLE_ENTRY_SIZE = 8
RESOURCE_TABLE_SHA256 = (
    "7d9f94e05b975940bd2e17f55681120782cb7b6f07d0ab6245adef7260d24130"
)
SPRITE_PAIR_TABLE_SHA256 = (
    "c7025f5ca83b63b21ff3bf3e3183602447d157cf6cd1e63395b918a318e74392"
)
MOTION_TABLE_OFFSET = 0x53EE98
MOTION_ENTRY_COUNT = 15
MOTION_ENTRY_SIZE = 10
MOTION_TABLE_SHA256 = (
    "d1793f9c19b046ff1f431f28da31518c2093b77914b5c1f8b13f7e01d0ff1c6d"
)
COMPONENT_SIZE = 20
TERMINATOR = bytes.fromhex("ffff0000")
RESOURCE_MANIFEST_PATH = (
    "artifacts/battle-effect-resource-pairs-v1/manifest.json"
)
SEQUENCE_MANIFEST_PATH = (
    "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
)
CODE_SLICES = (
    {
        "name": "all_effect_descriptor_callbacks",
        "file_offset": 0x080554,
        "gba_start": "0x08080554",
        "gba_end": "0x08080A46",
        "sha256": "22aae5132d081d89b9e9315968c1d3d089131b269ae1f5cfa232d1d6d13b8c8a",
    },
    {
        "name": "child_spawn_and_busy_check",
        "file_offset": 0x080218,
        "gba_start": "0x08080218",
        "gba_end": "0x0808041C",
        "sha256": "535602dc02bcc106e0d35f04793aad246f02202ce5d409643a4ac79675044203",
    },
    {
        "name": "child_position_and_ballistic_callbacks",
        "file_offset": 0x08041C,
        "gba_start": "0x0808041C",
        "gba_end": "0x08080554",
        "sha256": "aa07bf4cce0e10e2786bf38371aa50dd22a9424fb62605d85de50b331b644aa2",
    },
    {
        "name": "effect_child_sprite_allocator_bridge",
        "file_offset": 0x0802AE,
        "gba_start": "0x080802AE",
        "gba_end": "0x08080308",
        "sha256": "53e4a757cf7d5074ea0dfdb58822c7e68b5768426facd3e5e9ec3d1e58cfcca6",
    },
    {
        "name": "sprite_task_allocator",
        "file_offset": 0x0625A4,
        "gba_start": "0x080625A4",
        "gba_end": "0x080626B0",
        "sha256": "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54",
    },
    {
        "name": "component_and_timeline_selector",
        "file_offset": 0x06298C,
        "gba_start": "0x0806298C",
        "gba_end": "0x08062A0A",
        "sha256": "722200eb6511a974b79fe00ee335f21e557cc0fc1898343a5eab4c7032e8ed2f",
    },
    {
        "name": "animation_frame_selector_exact",
        "file_offset": 0x06298C,
        "gba_start": "0x0806298C",
        "gba_end": "0x080629A0",
        "sha256": "62718fbb246078256e2c3344773d0ab9a0b2c10aee2fb3890d16e134b331e1ab",
    },
    {
        "name": "animation_hold_step_and_termination",
        "file_offset": 0x063256,
        "gba_start": "0x08063256",
        "gba_end": "0x080632D8",
        "sha256": "1ec4801f36351e56d511caaa6cc5fdf31d52142292e64d3c9cf6567eed468be0",
    },
    {
        "name": "attr2_and_obj_vram_path",
        "file_offset": 0x063108,
        "gba_start": "0x08063108",
        "gba_end": "0x08063186",
        "sha256": "748340bb724a0fc8a4911c8879e8fb0c1152c84bac87b910cb36b3e15d790b17",
    },
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _rom_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer {_address(pointer)} is outside the ROM")
    return offset


def _load_inputs(root: Path, rom_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    resource_path = root / RESOURCE_MANIFEST_PATH
    sequence_path = root / SEQUENCE_MANIFEST_PATH
    resources = json.loads(resource_path.read_text(encoding="utf-8"))
    sequences = json.loads(sequence_path.read_text(encoding="utf-8"))
    if resources.get("schema") != "battle-effect-resource-pairs-v1":
        raise ValueError("unexpected battle-effect resource manifest schema")
    if sequences.get("schema") != "battle-effect-sequence-bindings-v1":
        raise ValueError("unexpected battle-effect sequence manifest schema")
    if resources["rom"]["sha256"] != rom_sha256:
        raise ValueError("resource manifest ROM hash mismatch")
    if sequences["rom"]["sha256"] != rom_sha256:
        raise ValueError("sequence manifest ROM hash mismatch")
    if [entry["group_id"] for entry in resources["entries"]] != list(
        range(1, TABLE_ENTRY_COUNT)
    ):
        raise ValueError("resource manifest does not contain groups 1..18")
    if len(sequences["sequences"]) != 22:
        raise ValueError("sequence manifest does not contain 22 descriptors")
    return resources, sequences


def _parse_component(raw: bytes, component_index: int) -> dict[str, Any]:
    if len(raw) != COMPONENT_SIZE:
        raise ValueError("component record is truncated")
    (
        tile_index,
        tile_flags,
        x,
        y,
        width,
        height,
        scale_x,
        scale_y,
        control,
        affine_mode,
        reserved_12,
    ) = struct.unpack("<HHhhHHHHBBH", raw)
    if tile_index == 0xFFFF:
        raise ValueError("component terminator was parsed as data")
    if width not in (8, 16, 32, 64) or height not in (8, 16, 32, 64):
        raise ValueError(
            f"component {component_index} has unsupported size {width}x{height}"
        )
    if tile_flags & ~0x0003:
        raise ValueError(
            f"component {component_index} has unknown tile flags "
            f"0x{tile_flags:04X}"
        )
    if control not in (0x00, 0xFF):
        raise ValueError(
            f"component {component_index} has unknown control 0x{control:02X}"
        )
    if affine_mode not in (0, 1) or reserved_12:
        raise ValueError(f"component {component_index} has unknown reserved fields")
    return {
        "component_index": component_index,
        "tile_index": tile_index,
        "tile_flags": tile_flags,
        "horizontal_flip": bool(tile_flags & 1),
        "vertical_flip": bool(tile_flags & 2),
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "control": control,
        "affine_mode": affine_mode,
        "reserved_12": reserved_12,
        "raw_hex": raw.hex(),
    }


def _frame_pointers(
    rom: bytes,
    definition_pointer: int,
) -> tuple[list[int], int]:
    cursor = _rom_offset(definition_pointer, len(rom))
    pointers: list[int] = []
    while cursor + 4 <= len(rom):
        pointer = struct.unpack_from("<I", rom, cursor)[0]
        if not ROM_BASE <= pointer < definition_pointer:
            break
        if pointers and pointer <= pointers[-1]:
            raise ValueError("frame component-list pointers are not increasing")
        pointers.append(pointer)
        cursor += 4
        if len(pointers) > 128:
            raise ValueError("frame pointer table has no bounded end")
    if not pointers:
        raise ValueError("definition table has no frame pointers")
    return pointers, ROM_BASE + cursor


def _parse_frames(
    rom: bytes,
    frame_pointers: list[int],
    definition_pointer: int,
) -> tuple[list[dict[str, Any]], bool]:
    frames: list[dict[str, Any]] = []
    expected_ends = frame_pointers[1:] + [definition_pointer]
    contiguous = True
    for frame_id, (pointer, expected_end) in enumerate(
        zip(frame_pointers, expected_ends)
    ):
        cursor = _rom_offset(pointer, len(rom))
        start = cursor
        components: list[dict[str, Any]] = []
        while cursor + 4 <= len(rom) and rom[cursor : cursor + 4] != TERMINATOR:
            if cursor + COMPONENT_SIZE > len(rom):
                raise ValueError(f"group frame {frame_id} is truncated")
            components.append(
                _parse_component(
                    rom[cursor : cursor + COMPONENT_SIZE],
                    len(components),
                )
            )
            cursor += COMPONENT_SIZE
            if len(components) > 32:
                raise ValueError(f"group frame {frame_id} has too many components")
        if rom[cursor : cursor + 4] != TERMINATOR:
            raise ValueError(f"group frame {frame_id} has no terminator")
        cursor += 4
        actual_end = ROM_BASE + cursor
        contiguous = contiguous and actual_end == expected_end
        raw = rom[start:cursor]
        frames.append(
            {
                "frame_id": frame_id,
                "component_list_pointer": _address(pointer),
                "component_count": len(components),
                "components": components,
                "terminator_raw_hex": TERMINATOR.hex(),
                "raw_size": len(raw),
                "raw_sha256": _sha256(raw),
            }
        )
    if not contiguous:
        raise ValueError("component-list region is not contiguous")
    return frames, contiguous


def _animation_pointers(
    rom: bytes,
    timeline_region_start: int,
    animation_table_pointer: int,
) -> list[int]:
    cursor = _rom_offset(animation_table_pointer, len(rom))
    pointers: list[int] = []
    while cursor + 4 <= len(rom):
        pointer = struct.unpack_from("<I", rom, cursor)[0]
        if not timeline_region_start <= pointer < animation_table_pointer:
            break
        if pointers and pointer <= pointers[-1]:
            raise ValueError("animation timeline pointers are not increasing")
        pointers.append(pointer)
        cursor += 4
        if len(pointers) > 32:
            raise ValueError("animation pointer table has no bounded end")
    if not pointers:
        raise ValueError("animation table has no timeline pointers")
    return pointers


def _parse_animations(
    rom: bytes,
    animation_pointers: list[int],
    animation_table_pointer: int,
    frame_count: int,
) -> tuple[list[dict[str, Any]], bool]:
    animations: list[dict[str, Any]] = []
    expected_ends = animation_pointers[1:] + [animation_table_pointer]
    contiguous = True
    for animation_id, (pointer, expected_end) in enumerate(
        zip(animation_pointers, expected_ends)
    ):
        cursor = _rom_offset(pointer, len(rom))
        start = cursor
        keyframes: list[dict[str, int]] = []
        while cursor + 4 <= len(rom):
            frame_id, hold_frames = struct.unpack_from("<HH", rom, cursor)
            cursor += 4
            if frame_id == 0xFFFF:
                if hold_frames:
                    raise ValueError("timeline terminator hold is not zero")
                break
            if frame_id >= frame_count:
                raise ValueError(
                    f"animation {animation_id} frame {frame_id} is out of range"
                )
            if not hold_frames:
                raise ValueError(
                    f"animation {animation_id} has a zero-frame hold"
                )
            keyframes.append(
                {
                    "frame_id": frame_id,
                    "hold_frames": hold_frames,
                }
            )
            if len(keyframes) > 256:
                raise ValueError(f"animation {animation_id} has no bounded end")
        if not keyframes:
            raise ValueError(f"animation {animation_id} is empty")
        actual_end = ROM_BASE + cursor
        contiguous = contiguous and actual_end == expected_end
        raw = rom[start:cursor]
        animations.append(
            {
                "animation_id": animation_id,
                "timeline_pointer": _address(pointer),
                "keyframe_count": len(keyframes),
                "duration_frames": sum(
                    item["hold_frames"] for item in keyframes
                ),
                "keyframes": keyframes,
                "terminator": {
                    "frame_id": 0xFFFF,
                    "hold_frames": 0,
                },
                "raw_size": len(raw),
                "raw_sha256": _sha256(raw),
            }
        )
    if not contiguous:
        raise ValueError("animation timeline region is not contiguous")
    return animations, contiguous


def _flip_pixels(
    pixels: bytes,
    width: int,
    height: int,
    *,
    horizontal: bool,
    vertical: bool,
) -> bytes:
    if not horizontal and not vertical:
        return pixels
    result = bytearray(len(pixels))
    for y in range(height):
        source_y = height - 1 - y if vertical else y
        for x in range(width):
            source_x = width - 1 - x if horizontal else x
            result[y * width + x] = pixels[source_y * width + source_x]
    return bytes(result)


def _render_frame(
    group_id: int,
    frame: dict[str, Any],
    graphics: bytes,
    palette: bytes,
) -> tuple[dict[str, Any], bytes]:
    components = frame["components"]
    png_name = f"group-{group_id:02d}-frame-{frame['frame_id']:02d}.png"
    if not components:
        pixels = b"\0"
        width = height = 1
        bounds = {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1}
    else:
        min_x = min(component["x"] for component in components)
        min_y = min(component["y"] for component in components)
        max_x = max(
            component["x"] + component["width"] for component in components
        )
        max_y = max(
            component["y"] + component["height"] for component in components
        )
        width = max_x - min_x
        height = max_y - min_y
        if width <= 0 or height <= 0:
            raise ValueError(
                f"group {group_id} frame {frame['frame_id']} has invalid bounds"
            )
        canvas = bytearray(width * height)
        for component in components:
            component_pixels, component_width, component_height = (
                render_4bpp_tile_block_indices(
                    graphics,
                    tile_offset=component["tile_index"],
                    width_tiles=component["width"] // 8,
                    height_tiles=component["height"] // 8,
                )
            )
            if (
                component_width != component["width"]
                or component_height != component["height"]
            ):
                raise ValueError("component renderer returned unexpected geometry")
            component_pixels = _flip_pixels(
                component_pixels,
                component_width,
                component_height,
                horizontal=component["horizontal_flip"],
                vertical=component["vertical_flip"],
            )
            destination_x = component["x"] - min_x
            destination_y = component["y"] - min_y
            for local_y in range(component_height):
                for local_x in range(component_width):
                    color = component_pixels[
                        local_y * component_width + local_x
                    ]
                    if color:
                        canvas[
                            (destination_y + local_y) * width
                            + destination_x
                            + local_x
                        ] = color
        pixels = bytes(canvas)
        bounds = {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
        }
    png = indexed_png_from_bgr555(
        pixels,
        palette,
        width=width,
        height=height,
        transparent_index=0,
    )
    return (
        {
            "png": png_name,
            "width": width,
            "height": height,
            "component_local_bounds": bounds,
            "pixel_sha256": _sha256(pixels),
            "png_sha256": _sha256(png),
            "rendering_scope": (
                "source-space component order with H/V tile flips; "
                "runtime affine, screen position and priority are not applied"
            ),
        },
        png,
    )


def _code_slices(rom: bytes) -> list[dict[str, Any]]:
    result = []
    for expected in CODE_SLICES:
        start = expected["file_offset"]
        end = int(expected["gba_end"], 16) - ROM_BASE
        actual = _sha256(rom[start:end])
        if actual != expected["sha256"]:
            raise ValueError(f"{expected['name']} code SHA-256 mismatch")
        result.append(dict(expected))
    return result


def _motion_spawn_records(rom: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    size = MOTION_ENTRY_COUNT * MOTION_ENTRY_SIZE
    table = rom[MOTION_TABLE_OFFSET : MOTION_TABLE_OFFSET + size]
    if _sha256(table) != MOTION_TABLE_SHA256:
        raise ValueError("motion spawn table SHA-256 mismatch")
    records = []
    spawn_tick = 0
    for record_id in range(MOTION_ENTRY_COUNT):
        fields = struct.unpack_from(
            "<5h",
            table,
            record_id * MOTION_ENTRY_SIZE,
        )
        effect_id, x_offset, y_offset, render_attributes, delay_ticks = fields
        is_terminator = effect_id == -1
        if is_terminator and fields != (-1, 0, 0, 0, 0):
            raise ValueError("motion spawn terminator is malformed")
        if not is_terminator and (effect_id not in (0, 1, 2) or delay_ticks < 0):
            raise ValueError(f"motion spawn record {record_id} is invalid")
        records.append(
            {
                "record_id": record_id,
                "effect_id": effect_id,
                "x_offset": x_offset,
                "y_offset": y_offset,
                "render_attributes": render_attributes,
                "delay_ticks": delay_ticks,
                "spawn_tick": None if is_terminator else spawn_tick,
                "is_terminator": is_terminator,
                "raw_hex": table[
                    record_id * MOTION_ENTRY_SIZE :
                    (record_id + 1) * MOTION_ENTRY_SIZE
                ].hex(),
            }
        )
        if not is_terminator:
            spawn_tick += delay_ticks
    if not records[-1]["is_terminator"]:
        raise ValueError("motion spawn table has no final terminator")
    return table, records


def _sequence_playback_plans(
    sequence_manifest: dict[str, Any],
    groups: list[dict[str, Any]],
    motion_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    group_by_id = {group["group_id"]: group for group in groups}
    plans = []
    for sequence in sequence_manifest["sequences"]:
        sequence_id = sequence["sequence_id"]
        group_id = (
            sequence["nonzero_resource_group_ids"][0]
            if sequence["nonzero_resource_group_ids"]
            else 0
        )
        events: list[dict[str, Any]] = []
        if sequence_id == 0:
            policy = "null"
            screen_coordinates_complete = True
        elif sequence_id == 1:
            policy = "three_child_ballistic_rng"
            screen_coordinates_complete = False
            duration = group_by_id[group_id]["animations"][0][
                "duration_frames"
            ]
            for child_index in range(3):
                events.append(
                    {
                        "child_index": child_index,
                        "spawn_tick": 0,
                        "group_id": group_id,
                        "animation_variant": 0,
                        "child_duration_frames": duration,
                        "static_completion_tick": duration,
                        "x_offset": None,
                        "y_offset": None,
                        "render_attributes_argument": 0,
                        "per_tick_callback_thumb": "0x080804ED",
                        "coordinate_boundary": (
                            "initial angle/position depend on RNG and parent "
                            "+0x8C runtime mode"
                        ),
                    }
                )
        elif sequence_id in (2, 3, 18):
            forced_zero = sequence_id == 18
            policy = (
                "motion_table_forced_variant_zero"
                if forced_zero
                else "motion_table_fan_out"
            )
            screen_coordinates_complete = False
            for child_index, record in enumerate(motion_records[:-1]):
                variant = 0 if forced_zero else record["effect_id"]
                duration = group_by_id[group_id]["animations"][variant][
                    "duration_frames"
                ]
                if sequence_id == 2:
                    render_attributes = (
                        record["render_attributes"] << 8
                    ) | 0x400
                elif sequence_id == 3:
                    render_attributes = record["render_attributes"] << 8
                else:
                    render_attributes = 0
                events.append(
                    {
                        "child_index": child_index,
                        "spawn_tick": record["spawn_tick"],
                        "motion_record_id": record["record_id"],
                        "group_id": group_id,
                        "animation_variant": variant,
                        "child_duration_frames": duration,
                        "static_completion_tick": (
                            record["spawn_tick"] + duration
                        ),
                        "x_offset": record["x_offset"],
                        "y_offset": record["y_offset"],
                        "render_attributes_argument": render_attributes,
                        "per_tick_callback_thumb": "0x0808041D",
                    }
                )
        else:
            policy = "single_child_variant_zero"
            screen_coordinates_complete = False
            duration = group_by_id[group_id]["animations"][0][
                "duration_frames"
            ]
            tick_callback = sequence["tick_callback_address"]
            if tick_callback == "0x08080914":
                render_attributes = 1 << 28
            elif tick_callback == "0x080809F4":
                render_attributes = 0x310
            elif tick_callback == "0x08080964":
                render_attributes = 0x400
            elif tick_callback == "0x080808C4":
                render_attributes = 0
            else:
                raise ValueError(
                    f"sequence {sequence_id} has unknown simple callback "
                    f"{tick_callback}"
                )
            events.append(
                {
                    "child_index": 0,
                    "spawn_tick": 0,
                    "group_id": group_id,
                    "animation_variant": 0,
                    "child_duration_frames": duration,
                    "static_completion_tick": duration,
                    "x_offset": 0,
                    "y_offset": 0,
                    "render_attributes_argument": render_attributes,
                    "per_tick_callback_thumb": "0x0808041D",
                }
            )
        last_completion = max(
            (event["static_completion_tick"] for event in events),
            default=0,
        )
        plans.append(
            {
                "sequence_id": sequence_id,
                "group_id": group_id,
                "init_once_callback_thumb": sequence[
                    "init_once_callback_thumb"
                ],
                "tick_callback_thumb": sequence["tick_callback_thumb"],
                "spawn_policy": policy,
                "spawn_events": events,
                "last_child_static_completion_tick": last_completion,
                "parent_release_tick_range": (
                    [0, 0]
                    if sequence_id == 0
                    else [last_completion, last_completion + 1]
                ),
                "screen_coordinates_complete": screen_coordinates_complete,
            }
        )
    return plans


def export_battle_effect_sprite_animations(
    root: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    output_dir = Path(output_dir)
    rom = (root / "rom/base.gba").read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {rom_sha256}"
        )
    resources, sequences = _load_inputs(root, rom_sha256)
    resource_path = root / RESOURCE_MANIFEST_PATH
    sequence_path = root / SEQUENCE_MANIFEST_PATH

    table_size = TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    resource_table = rom[
        RESOURCE_TABLE_OFFSET : RESOURCE_TABLE_OFFSET + table_size
    ]
    sprite_pair_table = rom[
        SPRITE_PAIR_TABLE_OFFSET : SPRITE_PAIR_TABLE_OFFSET + table_size
    ]
    if _sha256(resource_table) != RESOURCE_TABLE_SHA256:
        raise ValueError("resource pointer table SHA-256 mismatch")
    if _sha256(sprite_pair_table) != SPRITE_PAIR_TABLE_SHA256:
        raise ValueError("sprite pair table SHA-256 mismatch")
    if resource_table[:8] != b"\0" * 8 or sprite_pair_table[:8] != b"\0" * 8:
        raise ValueError("resource group zero is not the null sentinel")
    motion_table, motion_records = _motion_spawn_records(rom)

    resource_entries = {
        entry["group_id"]: entry for entry in resources["entries"]
    }
    sequence_ids_by_group: dict[int, list[int]] = {
        group_id: [] for group_id in range(1, TABLE_ENTRY_COUNT)
    }
    for sequence in sequences["sequences"]:
        for group_id in sequence["nonzero_resource_group_ids"]:
            sequence_ids_by_group[group_id].append(sequence["sequence_id"])

    groups: list[dict[str, Any]] = []
    outputs: dict[str, bytes] = {}
    for group_id in range(1, TABLE_ENTRY_COUNT):
        graphics_pointer, palette_pointer = struct.unpack_from(
            "<II",
            resource_table,
            group_id * TABLE_ENTRY_SIZE,
        )
        definition_pointer, animation_table_pointer = struct.unpack_from(
            "<II",
            sprite_pair_table,
            group_id * TABLE_ENTRY_SIZE,
        )
        resource_entry = resource_entries[group_id]
        if resource_entry["graphics"]["gba_address"] != _address(
            graphics_pointer
        ):
            raise ValueError(f"group {group_id} graphics pointer mismatch")
        if resource_entry["palette"]["gba_address"] != _address(
            palette_pointer
        ):
            raise ValueError(f"group {group_id} palette pointer mismatch")
        graphics_path = (
            root
            / "artifacts/battle-effect-resource-pairs-v1"
            / resource_entry["graphics"]["output_bin"]
        )
        palette_path = (
            root
            / "artifacts/battle-effect-resource-pairs-v1"
            / resource_entry["palette"]["output_bin"]
        )
        graphics = graphics_path.read_bytes()
        palette = palette_path.read_bytes()
        if _sha256(graphics) != resource_entry["graphics"]["decompressed_sha256"]:
            raise ValueError(f"group {group_id} graphics artifact hash mismatch")
        if _sha256(palette) != resource_entry["palette"]["decompressed_sha256"]:
            raise ValueError(f"group {group_id} palette artifact hash mismatch")

        frame_pointers, timeline_region_start = _frame_pointers(
            rom,
            definition_pointer,
        )
        frames, definition_contiguous = _parse_frames(
            rom,
            frame_pointers,
            definition_pointer,
        )
        animation_pointers = _animation_pointers(
            rom,
            timeline_region_start,
            animation_table_pointer,
        )
        animations, timeline_contiguous = _parse_animations(
            rom,
            animation_pointers,
            animation_table_pointer,
            len(frames),
        )

        referenced_tiles: set[int] = set()
        for frame in frames:
            for component in frame["components"]:
                tile_count = component["width"] * component["height"] // 64
                end_tile = component["tile_index"] + tile_count
                if end_tile > resource_entry["graphics"]["tile_count"]:
                    raise ValueError(
                        f"group {group_id} frame {frame['frame_id']} "
                        "references tiles outside its graphics"
                    )
                referenced_tiles.update(
                    range(component["tile_index"], end_tile)
                )
            preview, png = _render_frame(
                group_id,
                frame,
                graphics,
                palette,
            )
            frame["preview"] = preview
            outputs[preview["png"]] = png

        tile_count = resource_entry["graphics"]["tile_count"]
        missing_tiles = sorted(set(range(tile_count)) - referenced_tiles)
        if missing_tiles:
            raise ValueError(f"group {group_id} has unreferenced source tiles")
        groups.append(
            {
                "group_id": group_id,
                "sequence_ids": sorted(set(sequence_ids_by_group[group_id])),
                "resource_table_entry_gba_address": _address(
                    ROM_BASE
                    + RESOURCE_TABLE_OFFSET
                    + group_id * TABLE_ENTRY_SIZE
                ),
                "sprite_pair_table_entry_gba_address": _address(
                    ROM_BASE
                    + SPRITE_PAIR_TABLE_OFFSET
                    + group_id * TABLE_ENTRY_SIZE
                ),
                "definition_pointer_table": _address(definition_pointer),
                "animation_pointer_table": _address(animation_table_pointer),
                "timeline_region_start": _address(timeline_region_start),
                "graphics": dict(resource_entry["graphics"]),
                "palette": dict(resource_entry["palette"]),
                "frame_count": len(frames),
                "component_count": sum(
                    frame["component_count"] for frame in frames
                ),
                "animation_count": len(animations),
                "keyframe_count": sum(
                    animation["keyframe_count"] for animation in animations
                ),
                "animation_durations": [
                    animation["duration_frames"] for animation in animations
                ],
                "definition_region_contiguous": definition_contiguous,
                "timeline_region_contiguous": timeline_contiguous,
                "tile_coverage": {
                    "referenced_tile_indices": sorted(referenced_tiles),
                    "missing_tile_indices": missing_tiles,
                    "all_tiles_referenced": not missing_tiles,
                },
                "frames": frames,
                "animations": animations,
            }
        )

    playback_plans = _sequence_playback_plans(
        sequences,
        groups,
        motion_records,
    )
    manifest: dict[str, Any] = {
        "schema": "battle-effect-sprite-animations-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "inputs": {
            "resource_manifest": {
                "path": RESOURCE_MANIFEST_PATH,
                "sha256": _sha256(resource_path.read_bytes()),
            },
            "sequence_manifest": {
                "path": SEQUENCE_MANIFEST_PATH,
                "sha256": _sha256(sequence_path.read_bytes()),
            },
        },
        "resource_pointer_table": {
            "file_offset": RESOURCE_TABLE_OFFSET,
            "gba_address": _address(ROM_BASE + RESOURCE_TABLE_OFFSET),
            "entry_count": TABLE_ENTRY_COUNT,
            "entry_size": TABLE_ENTRY_SIZE,
            "sha256": _sha256(resource_table),
        },
        "sprite_pair_table": {
            "file_offset": SPRITE_PAIR_TABLE_OFFSET,
            "gba_address": _address(ROM_BASE + SPRITE_PAIR_TABLE_OFFSET),
            "entry_count": TABLE_ENTRY_COUNT,
            "entry_size": TABLE_ENTRY_SIZE,
            "sha256": _sha256(sprite_pair_table),
        },
        "motion_spawn_table": {
            "file_offset": MOTION_TABLE_OFFSET,
            "gba_address": _address(ROM_BASE + MOTION_TABLE_OFFSET),
            "entry_count": MOTION_ENTRY_COUNT,
            "entry_size": MOTION_ENTRY_SIZE,
            "sha256": _sha256(motion_table),
        },
        "motion_spawn_records": motion_records,
        "group_count": len(groups),
        "frame_definition_count": sum(group["frame_count"] for group in groups),
        "component_count": sum(group["component_count"] for group in groups),
        "animation_count": sum(group["animation_count"] for group in groups),
        "keyframe_count": sum(group["keyframe_count"] for group in groups),
        "artifact_file_count": len(outputs) + 1,
        "artifact_files": sorted([*outputs, "manifest.json"]),
        "runtime_golden_duration_cross_checks": {
            "group_01_action_05_dust_frames": groups[0]["animation_durations"][0],
            "group_04_bomb_projectile_frames": groups[3]["animation_durations"][0],
            "group_05_action_05_hit_frames": groups[4]["animation_durations"][0],
            "group_14_action_16_fire_hit_frames": groups[13]["animation_durations"][0],
        },
        "component_schema": {
            "record_size": COMPONENT_SIZE,
            "terminator_raw_hex": TERMINATOR.hex(),
            "fields": {
                "+0x00": "u16 tile_index",
                "+0x02": "u16 tile_flags; bit0 H-flip, bit1 V-flip",
                "+0x04": "s16 component-local x",
                "+0x06": "s16 component-local y",
                "+0x08": "u16 width",
                "+0x0A": "u16 height",
                "+0x0C": "u16 scale_x",
                "+0x0E": "u16 scale_y",
                "+0x10": "u8 control",
                "+0x11": "u8 affine_mode",
                "+0x12": "u16 reserved",
            },
        },
        "animation_schema": {
            "keyframe_size": 4,
            "fields": {
                "+0x00": "u16 frame_id; 0xFFFF terminates",
                "+0x02": "u16 hold_frames; terminator uses zero",
            },
        },
        "consumer_code_slices": _code_slices(rom),
        "groups": groups,
        "sequence_playback_plans": playback_plans,
        "parent_release_scheduler_boundary": {
            "minimum_extra_scheduler_ticks": 0,
            "maximum_extra_scheduler_ticks": 1,
            "reason": (
                "parent/child task slot order within the user-visible "
                "frame is not statically fixed"
            ),
        },
        "scope": {
            "all_nonzero_resource_groups_complete": True,
            "definition_pointer_tables_complete": True,
            "component_lists_complete": True,
            "child_animation_timelines_complete": True,
            "child_frame_hold_timing_complete": True,
            "component_local_geometry_complete": True,
            "source_tile_coverage_complete": True,
            "source_space_previews_complete": True,
            "callback_spawn_state_machines_complete": True,
            "callback_child_variant_and_hold_complete": True,
            "callback_random_screen_coordinates_complete": False,
            "parent_visible_release_tick_exact": False,
            "screen_space_oam_composition_complete": False,
            "runtime_mirroring_and_affine_complete": False,
            "blend_and_audio_binding_complete": False,
        },
    }

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    for name, payload in outputs.items():
        (output_dir / name).write_bytes(payload)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/battle-effect-sprite-animations-v1"),
    )
    args = parser.parse_args()
    manifest = export_battle_effect_sprite_animations(
        args.root,
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "groups": manifest["group_count"],
                "frames": manifest["frame_definition_count"],
                "components": manifest["component_count"],
                "animations": manifest["animation_count"],
                "errors": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
