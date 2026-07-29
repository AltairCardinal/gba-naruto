#!/usr/bin/env python3
"""Independently verify all battle-effect child sprite animation artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
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
RESOURCE_MANIFEST_PATH = (
    "artifacts/battle-effect-resource-pairs-v1/manifest.json"
)
SEQUENCE_MANIFEST_PATH = (
    "artifacts/battle-effect-sequence-bindings-v1/manifest.json"
)
COMPONENT_SIZE = 20
TERMINATOR = bytes.fromhex("ffff0000")
CODE_SLICES = (
    (
        "runtime_offset_table_initializer",
        0x061624,
        "0x08061624",
        "0x08061710",
        "e3ba1dadf23b428fd2a39b6d9aef48b7ba9521d825ca196b37d7a93403192dff",
    ),
    (
        "all_effect_descriptor_callbacks",
        0x080554,
        "0x08080554",
        "0x08080A46",
        "22aae5132d081d89b9e9315968c1d3d089131b269ae1f5cfa232d1d6d13b8c8a",
    ),
    (
        "child_spawn_and_busy_check",
        0x080218,
        "0x08080218",
        "0x0808041C",
        "535602dc02bcc106e0d35f04793aad246f02202ce5d409643a4ac79675044203",
    ),
    (
        "child_position_and_ballistic_callbacks",
        0x08041C,
        "0x0808041C",
        "0x08080554",
        "aa07bf4cce0e10e2786bf38371aa50dd22a9424fb62605d85de50b331b644aa2",
    ),
    (
        "effect_child_sprite_allocator_bridge",
        0x0802AE,
        "0x080802AE",
        "0x08080308",
        "53e4a757cf7d5074ea0dfdb58822c7e68b5768426facd3e5e9ec3d1e58cfcca6",
    ),
    (
        "sprite_task_allocator",
        0x0625A4,
        "0x080625A4",
        "0x080626B0",
        "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54",
    ),
    (
        "component_and_timeline_selector",
        0x06298C,
        "0x0806298C",
        "0x08062A0A",
        "722200eb6511a974b79fe00ee335f21e557cc0fc1898343a5eab4c7032e8ed2f",
    ),
    (
        "animation_frame_selector_exact",
        0x06298C,
        "0x0806298C",
        "0x080629A0",
        "62718fbb246078256e2c3344773d0ab9a0b2c10aee2fb3890d16e134b331e1ab",
    ),
    (
        "animation_hold_step_and_termination",
        0x063256,
        "0x08063256",
        "0x080632D8",
        "1ec4801f36351e56d511caaa6cc5fdf31d52142292e64d3c9cf6567eed468be0",
    ),
    (
        "attr2_and_obj_vram_path",
        0x063108,
        "0x08063108",
        "0x08063186",
        "748340bb724a0fc8a4911c8879e8fb0c1152c84bac87b910cb36b3e15d790b17",
    ),
    (
        "task_origin_and_component_position_composition",
        0x062C58,
        "0x08062C58",
        "0x08062C7C",
        "dc022a30c9ef95ab0bcb78e1a00e9cfa5c3bc4793e9c8352dd664086323e8313",
    ),
    (
        "pre_oam_offset_scale_and_visibility",
        0x062C7C,
        "0x08062C7C",
        "0x08062D92",
        "725a25fba4d30a78d197ea94b4ebf272ab03d48692e20c3e3a7bcfac82264039",
    ),
    (
        "runtime_offset_table_slot_reset",
        0x065404,
        "0x08065404",
        "0x08065554",
        "213423e70948ef3dbd91ed7854efb5c52fd7543f4b73b4a4a2219ffd89ce66f7",
    ),
    (
        "runtime_offset_table_dynamic_update",
        0x06E958,
        "0x0806E958",
        "0x0806EA96",
        "66f49791cd737c096ed6a7785591e202287b02dd679a4e2f5c095cd18c1c86a0",
    ),
    (
        "oam_shape_size_affine_and_attribute_writer",
        0x062D92,
        "0x08062D92",
        "0x08063186",
        "566415d7bf30967ce2f4228311e13e5b63e2de3d620b1d68e3622d58da9f8d23",
    ),
    (
        "dynamic_obj_vram_renderer_path",
        0x063122,
        "0x08063122",
        "0x080631F6",
        "fe6814464976f17f5e708266b02a79aaa195d1bf96985fa852b80d1f3df9afc3",
    ),
    (
        "dynamic_obj_vram_copy_queue_enqueue",
        0x0635B8,
        "0x080635B8",
        "0x08063604",
        "c72bd39f05cbff96897e1a508d02311661d11db5364d9c51525a1b2dc1562e48",
    ),
    (
        "dynamic_obj_vram_copy_queue_consumer",
        0x06365C,
        "0x0806365C",
        "0x080636DC",
        "ec7573f6149a187012c360a2755fd8336c0f496c1519d1e727e9ff582eef2203",
    ),
    (
        "dynamic_obj_vram_dispatch_order",
        0x0612BC,
        "0x080612BC",
        "0x080614E4",
        "90568d99bb0ddfba74ce946781049494e117bd2273bd3b69843f7df420506817",
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _offset(pointer: int, rom_size: int) -> int:
    result = pointer - ROM_BASE
    if not 0 <= result < rom_size:
        raise ValueError(f"pointer {_address(pointer)} is outside ROM")
    return result


def _component(raw: bytes, index: int) -> dict[str, Any]:
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
    if (
        tile_index == 0xFFFF
        or width not in (8, 16, 32, 64)
        or height not in (8, 16, 32, 64)
        or tile_flags & ~3
        or control not in (0, 0xFF)
        or affine_mode not in (0, 1)
        or reserved_12
    ):
        raise ValueError(f"invalid component {index}")
    return {
        "component_index": index,
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


def _definitions(
    rom: bytes,
    definition_pointer: int,
) -> tuple[list[dict[str, Any]], int]:
    table_offset = _offset(definition_pointer, len(rom))
    pointers = []
    while True:
        pointer = struct.unpack_from(
            "<I", rom, table_offset + len(pointers) * 4
        )[0]
        if not ROM_BASE <= pointer < definition_pointer:
            break
        if pointers and pointer <= pointers[-1]:
            raise ValueError("definition pointers are not increasing")
        pointers.append(pointer)
        if len(pointers) > 128:
            raise ValueError("definition table is unbounded")
    if not pointers:
        raise ValueError("definition table is empty")
    timeline_start = definition_pointer + len(pointers) * 4
    frames = []
    for frame_id, (pointer, expected_end) in enumerate(
        zip(pointers, pointers[1:] + [definition_pointer])
    ):
        cursor = _offset(pointer, len(rom))
        start = cursor
        components = []
        while rom[cursor : cursor + 4] != TERMINATOR:
            raw = rom[cursor : cursor + COMPONENT_SIZE]
            if len(raw) != COMPONENT_SIZE:
                raise ValueError("component is truncated")
            components.append(_component(raw, len(components)))
            cursor += COMPONENT_SIZE
            if len(components) > 32:
                raise ValueError("component list is unbounded")
        cursor += 4
        if ROM_BASE + cursor != expected_end:
            raise ValueError("definition region is not contiguous")
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
    return frames, timeline_start


def _animations(
    rom: bytes,
    timeline_start: int,
    animation_table_pointer: int,
    frame_count: int,
) -> list[dict[str, Any]]:
    table_offset = _offset(animation_table_pointer, len(rom))
    pointers = []
    while True:
        pointer = struct.unpack_from(
            "<I", rom, table_offset + len(pointers) * 4
        )[0]
        if not timeline_start <= pointer < animation_table_pointer:
            break
        if pointers and pointer <= pointers[-1]:
            raise ValueError("animation pointers are not increasing")
        pointers.append(pointer)
        if len(pointers) > 32:
            raise ValueError("animation table is unbounded")
    if not pointers:
        raise ValueError("animation table is empty")
    result = []
    for animation_id, (pointer, expected_end) in enumerate(
        zip(pointers, pointers[1:] + [animation_table_pointer])
    ):
        cursor = _offset(pointer, len(rom))
        start = cursor
        keyframes = []
        while True:
            frame_id, hold_frames = struct.unpack_from("<HH", rom, cursor)
            cursor += 4
            if frame_id == 0xFFFF:
                if hold_frames:
                    raise ValueError("animation terminator hold is not zero")
                break
            if frame_id >= frame_count or not hold_frames:
                raise ValueError("animation keyframe is invalid")
            keyframes.append(
                {"frame_id": frame_id, "hold_frames": hold_frames}
            )
            if len(keyframes) > 256:
                raise ValueError("animation is unbounded")
        if ROM_BASE + cursor != expected_end:
            raise ValueError("animation region is not contiguous")
        raw = rom[start:cursor]
        result.append(
            {
                "animation_id": animation_id,
                "timeline_pointer": _address(pointer),
                "keyframe_count": len(keyframes),
                "duration_frames": sum(
                    item["hold_frames"] for item in keyframes
                ),
                "keyframes": keyframes,
                "terminator": {"frame_id": 0xFFFF, "hold_frames": 0},
                "raw_size": len(raw),
                "raw_sha256": _sha256(raw),
            }
        )
    return result


def _flip(
    pixels: bytes,
    width: int,
    height: int,
    horizontal: bool,
    vertical: bool,
) -> bytes:
    if not horizontal and not vertical:
        return pixels
    output = bytearray(len(pixels))
    for y in range(height):
        source_y = height - 1 - y if vertical else y
        for x in range(width):
            source_x = width - 1 - x if horizontal else x
            output[y * width + x] = pixels[source_y * width + source_x]
    return bytes(output)


def _preview(
    group_id: int,
    frame: dict[str, Any],
    graphics: bytes,
    palette: bytes,
) -> tuple[dict[str, Any], bytes]:
    components = frame["components"]
    if not components:
        width = height = 1
        pixels = b"\0"
        bounds = {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1}
    else:
        min_x = min(item["x"] for item in components)
        min_y = min(item["y"] for item in components)
        max_x = max(item["x"] + item["width"] for item in components)
        max_y = max(item["y"] + item["height"] for item in components)
        width = max_x - min_x
        height = max_y - min_y
        canvas = bytearray(width * height)
        for item in components:
            block, block_width, block_height = render_4bpp_tile_block_indices(
                graphics,
                tile_offset=item["tile_index"],
                width_tiles=item["width"] // 8,
                height_tiles=item["height"] // 8,
            )
            block = _flip(
                block,
                block_width,
                block_height,
                item["horizontal_flip"],
                item["vertical_flip"],
            )
            destination_x = item["x"] - min_x
            destination_y = item["y"] - min_y
            for y in range(block_height):
                for x in range(block_width):
                    color = block[y * block_width + x]
                    if color:
                        canvas[
                            (destination_y + y) * width + destination_x + x
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
            "png": f"group-{group_id:02d}-frame-{frame['frame_id']:02d}.png",
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


def _motion_records(rom: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    size = MOTION_ENTRY_COUNT * MOTION_ENTRY_SIZE
    table = rom[MOTION_TABLE_OFFSET : MOTION_TABLE_OFFSET + size]
    if _sha256(table) != MOTION_TABLE_SHA256:
        raise ValueError("motion spawn table hash mismatch")
    records = []
    spawn_tick = 0
    for record_id in range(MOTION_ENTRY_COUNT):
        fields = struct.unpack_from(
            "<5h",
            table,
            record_id * MOTION_ENTRY_SIZE,
        )
        effect_id, x_offset, y_offset, render_attributes, delay_ticks = fields
        terminator = effect_id == -1
        if terminator and fields != (-1, 0, 0, 0, 0):
            raise ValueError("motion terminator is malformed")
        if not terminator and (effect_id not in (0, 1, 2) or delay_ticks < 0):
            raise ValueError("motion record is invalid")
        records.append(
            {
                "record_id": record_id,
                "effect_id": effect_id,
                "x_offset": x_offset,
                "y_offset": y_offset,
                "render_attributes": render_attributes,
                "delay_ticks": delay_ticks,
                "spawn_tick": None if terminator else spawn_tick,
                "is_terminator": terminator,
                "raw_hex": table[
                    record_id * MOTION_ENTRY_SIZE :
                    (record_id + 1) * MOTION_ENTRY_SIZE
                ].hex(),
            }
        )
        if not terminator:
            spawn_tick += delay_ticks
    if not records[-1]["is_terminator"]:
        raise ValueError("motion table has no terminator")
    return table, records


def _child_task_origin_model() -> dict[str, Any]:
    return {
        "task_fields": {
            "+0x00": "u32 render_flags",
            "+0x04": "s16 anchor_x",
            "+0x06": "s16 anchor_y",
            "+0x08": "s16 delta_x",
            "+0x0A": "s16 delta_y",
            "+0x2C": "s32 ballistic_x_q8_8",
            "+0x30": "s32 ballistic_y_q8_8",
            "+0x34": "s32 ballistic_angle; callback consumes low s16",
            "+0x38": "s32 ballistic_speed",
        },
        "q8_8_conversion": {
            "formula": (
                "truncate_toward_zero_q8_8(v) = "
                "s32(v + (255 if s32(v) < 0 else 0)) >> 8"
            ),
            "actor_x_source": "actor[side_id]+0x20",
            "actor_y_source": "actor[side_id]+0x24",
        },
        "constructor": {
            "parent_side_id_source": "s32(parent+0xA4)",
            "parent_x_source": "s32(parent+0x04)",
            "parent_y_source": "s32(parent+0x08)",
            "initial_anchor_x": "s16(parent_x + effective_x_offset)",
            "initial_anchor_y": "s16(parent_y + y_offset)",
            "mirrored_x_offset": "s16(-x_offset)",
            "effective_x_offset": (
                "mirrored_x_offset when side_id==0 and "
                "actor[0].orientation!=1, or side_id==1 and "
                "actor[1].orientation==0; otherwise s16(x_offset)"
            ),
            "horizontal_flip_toggle_mask": "0x8000",
            "side_unknown_render_flags": "0x40001000",
            "side_render_flags_formula": (
                "0x40001000 | (u8(side_id)<<13) | "
                "((u8(side_id)&1)<<31) | "
                "(0x20000000 if x_offset_mirrored else 0) | "
                "(u8(follow_argument)<<28)"
            ),
        },
        "actor_follow": {
            "enabled_when": (
                "parent_side_id != -1 and follow_argument != 0"
            ),
            "actor_anchor_x_formula": (
                "truncate_toward_zero_q8_8(actor_x_q8_8) when "
                "actor.orientation==side_id; otherwise "
                "240-truncate_toward_zero_q8_8(actor_x_q8_8)"
            ),
            "actor_anchor_y_formula": (
                "truncate_toward_zero_q8_8(actor_y_q8_8)"
            ),
            "delta_x_at_spawn": "s16(initial_anchor_x-actor_anchor_x(spawn))",
            "delta_y_at_spawn": "s16(initial_anchor_y-actor_anchor_y(spawn))",
            "task_origin_x_at_tick": "s16(actor_anchor_x(t) + delta_x)",
            "task_origin_y_at_tick": "s16(actor_anchor_y(t) + delta_y)",
            "consumer_code_range": "0x08062C58..0x08062C7C",
            "consumer_x_formula": (
                "s16(component_x + task.anchor_x + task.delta_x)"
            ),
            "consumer_y_formula": (
                "s16(component_y + task.anchor_y + task.delta_y)"
            ),
        },
        "rng_ballistic": {
            "sequence_id": 1,
            "child_count": 3,
            "initial_x_q8_8": "s32(parent_x<<8)",
            "initial_y_q8_8": "s32(parent_y<<8)",
            "rng_dispatch_call_target": "0x0809C110",
            "angle_jitter": "u32(rng_angle_result*7)>>15",
            "angle_when_mode_even": (
                "((parent_mode+2)<<6) + 12*child_index - 12 + angle_jitter"
            ),
            "angle_when_mode_one": (
                "192 + 12*child_index + angle_jitter"
            ),
            "angle_when_mode_other_odd": (
                "64 - angle_jitter - 12*child_index"
            ),
            "initial_speed": (
                "512 + ((child_index&1)<<6) + "
                "(u32(rng_speed_result*65)>>15)"
            ),
            "x_transition": (
                "u32(x_q8_8_t + "
                "(u32(s16(sin_rom(angle))*speed_t)>>8))"
            ),
            "y_transition": (
                "u32(y_q8_8_t - "
                "(u32(s16(cos_rom(angle))*speed_t)>>8))"
            ),
            "speed_transition": "max(0, speed_t - 24)",
            "task_origin_x_at_tick": (
                "truncate_toward_zero_q8_8(s32(x_q8_8_t))"
            ),
            "task_origin_y_at_tick": (
                "truncate_toward_zero_q8_8(s32(y_q8_8_t))"
            ),
            "concrete_boundary": (
                "parent coordinates, parent mode, RNG dispatch target/state "
                "and both RNG results per child are runtime inputs"
            ),
        },
        "model_boundaries": {
            "component_local_position_applied": False,
            "oam_attr_composition_applied": False,
            "affine_rasterization_applied": False,
            "screen_clipping_applied": False,
        },
    }


def _oam_attribute_model(
    groups: list[dict[str, Any]],
    playback_plans: list[dict[str, Any]],
) -> dict[str, Any]:
    observed_sizes = sorted({
        (component["width"], component["height"])
        for group in groups
        for frame in group["frames"]
        for component in frame["components"]
    })
    render_attribute_arguments = sorted({
        event["render_attributes_argument"]
        for plan in playback_plans
        for event in plan["spawn_events"]
    })
    return {
        "code_range": "0x08062D92..0x08063186",
        "combined_word_layout": "u32(attr1) << 16 | u16(attr0)",
        "task_fields": {
            "+0x00": "u32 render_flags",
            "+0x10": "u16 tile_base",
            "+0x12": "u8 palette_bank",
        },
        "shape_size_combined_masks": {
            "8x8": "0x00000000",
            "8x16": "0x00008000",
            "8x32": "0x40008000",
            "16x8": "0x00004000",
            "16x16": "0x40000000",
            "16x32": "0x80008000",
            "32x8": "0x40004000",
            "32x16": "0x80004000",
            "32x32": "0x80000000",
            "32x64": "0xC0008000",
            "64x32": "0xC0004000",
            "64x64": "0xC0000000",
        },
        "observed_component_sizes": [
            f"{width}x{height}" for width, height in observed_sizes
        ],
        "attr0": {
            "y_coordinate": "u8(renderer_final_y)",
            "object_mode": "task.render_flags & 0x00000C00",
            "affine_enable": "u1(component.affine_mode) << 8",
            "global_bit7": "global_obj_control_byte & 0x80",
            "shape_bits_source": "shape_size_combined_masks low u16",
        },
        "attr1": {
            "x_coordinate": "u9(renderer_final_x)",
            "non_affine_flip_bits": (
                "u2(component.tile_flags XOR "
                "((task.render_flags & 0x00018000) >> 15))"
            ),
            "non_affine_flip_placement": "flip_bits << 12",
            "non_affine_flip_placement_guard": (
                "(renderer_stack_mode_byte & 1) == 0 and "
                "task.byte_13 == 0 and task.scale_xy_q8_8 == 0x01000100 "
                "and (task.render_flags & 0x00080000) == 0"
            ),
            "size_bits_source": "shape_size_combined_masks high u16",
        },
        "attr2": {
            "applicable_path": (
                "battle-effect normal OBJ path where "
                "(task.render_flags & 0x00400000) == 0"
            ),
            "tile_index": "u16(task.tile_base + component.tile_index)",
            "palette_bank": "u4(task.palette_bank) << 12",
            "priority": "(task.render_flags & 0x000000C0) << 4",
            "formula": (
                "u16(task.tile_base + component.tile_index) | "
                "(u4(task.palette_bank) << 12) | "
                "((task.render_flags & 0x000000C0) << 4)"
            ),
        },
        "normal_path_reachability": {
            "constructor_fixed_and_side_flags_clear_bit_22": True,
            "reachable_render_attributes_arguments": render_attribute_arguments,
            "all_reachable_arguments_clear_bit_22": all(
                not value & 0x00400000
                for value in render_attribute_arguments
            ),
        },
        "model_boundaries": {
            "pre_attr_coordinate_transform_model_linked": True,
            "pre_attr_concrete_runtime_values_applied": False,
            "concrete_runtime_coordinates_applied": False,
            "affine_matrix_values_applied": False,
            "affine_rasterization_applied": False,
            "dynamic_obj_vram_model_linked": True,
            "dynamic_obj_vram_copy_execution_applied": False,
            "screen_clipping_applied": False,
        },
    }


def _dynamic_obj_vram_model(
    playback_plans: list[dict[str, Any]],
) -> dict[str, Any]:
    render_attribute_arguments = sorted({
        event["render_attributes_argument"]
        for plan in playback_plans
        for event in plan["spawn_events"]
    })
    return {
        "code_range": "0x08063122..0x080631F6",
        "activation": "(task.render_flags & 0x00400000) != 0",
        "copy_enqueue": {
            "enabled_when": (
                "(task.render_flags & 0x00800000) == 0 and "
                "(task.render_flags & 0x01000008) != 0x01000008"
            ),
            "source": (
                "task.tile_source_ptr + s16(component.tile_index) * 32"
            ),
            "destination": (
                "0x06010000 + "
                "u16(task.tile_base + running_dynamic_tile_offset) * 32"
            ),
            "size_bytes": (
                "u16(trunc0_div64("
                "s16(component.width)*s16(component.height)) * 32)"
            ),
            "enqueue_helper": "0x080635B8",
            "enqueue_return_value_ignored_by_renderer": True,
        },
        "copy_queue": {
            "iwram_address": "0x03005BBC",
            "slot_count": 16,
            "slot_stride": 16,
            "slot_fields": "u32 active, u32 source, u32 destination, u16 size",
            "enqueue_result": "1 when a free slot is reserved; 0 when full",
            "execution": {
                "consumer_code_range": "0x0806365C..0x080636DC",
                "status_1_operation": (
                    "CpuSet(source,destination,u16(size_bytes)>>1)"
                ),
                "status_1_unit": "16-bit halfwords",
                "synchronous": True,
                "completion_action": "clear queue slot active bit",
                "dispatcher_render_call": "0x08061320 -> 0x08062924",
                "dispatcher_first_flush_call": (
                    "0x080613FC -> 0x0806365C"
                ),
                "dispatcher_optional_second_flush_call": (
                    "0x080614C2 -> 0x0806365C"
                ),
                "relative_order": (
                    "sprite task/render dispatch completes before first flush"
                ),
            },
        },
        "attr2": (
            "u16(task.tile_base + running_dynamic_tile_offset) | "
            "(u4(task.palette_bank) << 12) | "
            "((task.render_flags & 0xC0) << 4)"
        ),
        "running_offset_initial": 0,
        "running_offset_after_component": (
            "u16(running_dynamic_tile_offset + "
            "trunc0_div64(s16(component.width)*s16(component.height)))"
        ),
        "current_sequence_reachability": {
            "reachable": any(
                value & 0x00400000
                for value in render_attribute_arguments
            ),
            "reachable_render_attributes_arguments": (
                render_attribute_arguments
            ),
            "all_reachable_arguments_clear_bit_22": all(
                not value & 0x00400000
                for value in render_attribute_arguments
            ),
        },
        "model_boundaries": {
            "enqueue_formula_known": True,
            "queue_full_failure_known": True,
            "queued_copy_execution_mechanism_known": True,
            "queued_copy_relative_dispatch_order_known": True,
            "dispatcher_hardware_vblank_phase_known": False,
            "current_battle_effect_sequence_runtime_instance_known": False,
        },
    }


def _pre_oam_coordinate_transform_model(
    groups: list[dict[str, Any]],
) -> dict[str, Any]:
    non_default_components = [
        {
            "group_id": group["group_id"],
            "frame_id": frame["frame_id"],
            "component_index": component["component_index"],
            "width": component["width"],
            "height": component["height"],
            "scale_x": component["scale_x"],
            "scale_y": component["scale_y"],
            "affine_mode": component["affine_mode"],
        }
        for group in groups
        for frame in group["frames"]
        for component in frame["components"]
        if (component["scale_x"], component["scale_y"]) != (0x100, 0x100)
    ]
    return {
        "code_range": "0x08062C7C..0x08062D92",
        "inputs": {
            "x_after_origin": (
                "s16 renderer x after component/task-origin composition"
            ),
            "y_after_origin": (
                "s16 renderer y after component/task-origin composition"
            ),
            "pre_scale_width": "s16 renderer extent before task/component scale",
            "pre_scale_height": "s16 renderer extent before task/component scale",
            "task_scale_x": "s16 task+0x0C Q8.8",
            "task_scale_y": "s16 task+0x0E Q8.8",
        },
        "runtime_offset_table": {
            "iwram_address": "0x03000054",
            "entry_count": 4,
            "entry_stride": 8,
            "entry_fields": "s32 x_q8_8, s32 y_q8_8",
            "enabled_when": "(task.render_flags & 0x00001000) != 0",
            "pair_index": "(task.render_flags & 0x00006000) >> 13",
            "x_after_offset": (
                "s16(x_after_origin - "
                "(s32(offset_table[pair_index*2]) >> 8))"
            ),
            "y_after_offset": (
                "s16(y_after_origin - "
                "(s32(offset_table[pair_index*2+1]) >> 8))"
            ),
            "disabled_result": (
                "x_after_offset=x_after_origin; "
                "y_after_offset=y_after_origin"
            ),
            "writer_evidence": [
                {
                    "kind": "initialize_all_entries_to_zero",
                    "code_range": "0x08061624..0x08061710",
                    "write_range": "0x080616D0..0x080616E0",
                    "direct_caller_known": False,
                },
                {
                    "kind": "reset_runtime_selected_entry_to_zero",
                    "code_range": "0x08065404..0x08065554",
                    "write_range": "0x08065528..0x0806553A",
                    "direct_caller_count": 23,
                },
                {
                    "kind": "state_driven_dynamic_update",
                    "code_range": "0x0806E958..0x0806EA96",
                    "state_1_effect": (
                        "write entry 0 x/y from runtime sources"
                    ),
                    "state_2_effect": (
                        "add/subtract runtime delta across entries 0 and 1"
                    ),
                },
            ],
        },
        "scale_and_extent": {
            "q8_8_multiply": (
                "q8_8_mul_trunc0(a,b) = "
                "s32(a*b + (255 if s32(a*b) < 0 else 0)) >> 8"
            ),
            "default_fast_path_when": (
                "component.scale_xy_q8_8 == 0x01000100 and "
                "task.scale_xy_q8_8 == 0x01000100"
            ),
            "default_fast_path_extent": (
                "scaled_width=component.width; "
                "scaled_height=component.height"
            ),
            "scaled_width": (
                "min_s16(pre_scale_width,"
                "s16(q8_8_mul_trunc0("
                "q8_8_mul_trunc0(component.width,task.scale_x),"
                "component.scale_x)))"
            ),
            "scaled_height": (
                "min_s16(pre_scale_height,"
                "s16(q8_8_mul_trunc0("
                "q8_8_mul_trunc0(component.height,task.scale_y),"
                "component.scale_y)))"
            ),
            "observed_non_default_components": non_default_components,
        },
        "visibility_gate": {
            "half_difference": (
                "trunc0_div2(v) = s32(v + (1 if s32(v) < 0 else 0)) >> 1"
            ),
            "all_required_conditions": [
                "x_after_offset + scaled_width > 0",
                "y_after_offset + scaled_height > 0",
                (
                    "x_after_offset < 240 - "
                    "trunc0_div2(pre_scale_width-scaled_width)"
                ),
                (
                    "y_after_offset < 160 - "
                    "trunc0_div2(pre_scale_height-scaled_height)"
                ),
            ],
            "failure_action": "skip component without emitting OAM",
        },
        "model_boundaries": {
            "runtime_offset_table_values_known": False,
            "runtime_offset_table_initialization_known": True,
            "runtime_offset_table_slot_reset_known": True,
            "runtime_offset_table_dynamic_writer_family_known": True,
            "runtime_offset_table_complete_schedule_known": False,
            "concrete_final_coordinates_known": False,
            "affine_matrix_and_rasterization_applied": False,
        },
    }


def _playback_plans(
    sequences: dict[str, Any],
    groups: list[dict[str, Any]],
    motion_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    group_by_id = {group["group_id"]: group for group in groups}
    plans = []
    for sequence in sequences["sequences"]:
        sequence_id = sequence["sequence_id"]
        group_id = (
            sequence["nonzero_resource_group_ids"][0]
            if sequence["nonzero_resource_group_ids"]
            else 0
        )
        events = []
        if sequence_id == 0:
            policy = "null"
            coordinates_complete = True
            origin_model_id = "none"
        elif sequence_id == 1:
            policy = "three_child_ballistic_rng"
            coordinates_complete = False
            origin_model_id = "rng_ballistic"
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
            forced = sequence_id == 18
            policy = (
                "motion_table_forced_variant_zero"
                if forced
                else "motion_table_fan_out"
            )
            coordinates_complete = False
            origin_model_id = "parent_offset_static"
            for child_index, record in enumerate(motion_records[:-1]):
                variant = 0 if forced else record["effect_id"]
                duration = group_by_id[group_id]["animations"][variant][
                    "duration_frames"
                ]
                attributes = (
                    (record["render_attributes"] << 8) | 0x400
                    if sequence_id == 2
                    else record["render_attributes"] << 8
                    if sequence_id == 3
                    else 0
                )
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
                        "render_attributes_argument": attributes,
                        "per_tick_callback_thumb": "0x0808041D",
                    }
                )
        else:
            policy = "single_child_variant_zero"
            coordinates_complete = False
            duration = group_by_id[group_id]["animations"][0][
                "duration_frames"
            ]
            callback = sequence["tick_callback_address"]
            attributes_by_callback = {
                "0x080808C4": 0,
                "0x08080914": 1 << 28,
                "0x08080964": 0x400,
                "0x080809F4": 0x310,
            }
            if callback not in attributes_by_callback:
                raise ValueError(
                    f"sequence {sequence_id} has unknown callback {callback}"
                )
            origin_model_id = (
                "actor_anchor_follow"
                if callback == "0x08080914"
                else "parent_origin_static"
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
                    "render_attributes_argument": attributes_by_callback[
                        callback
                    ],
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
                "child_task_origin_model_id": origin_model_id,
                "spawn_events": events,
                "last_child_static_completion_tick": last_completion,
                "parent_release_tick_range": (
                    [0, 0]
                    if sequence_id == 0
                    else [last_completion, last_completion + 1]
                ),
                "screen_coordinates_complete": coordinates_complete,
            }
        )
    return plans


def _expected(
    root: Path,
    rom: bytes,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    resource_path = root / RESOURCE_MANIFEST_PATH
    sequence_path = root / SEQUENCE_MANIFEST_PATH
    resources = json.loads(resource_path.read_text(encoding="utf-8"))
    sequences = json.loads(sequence_path.read_text(encoding="utf-8"))
    if (
        resources.get("schema") != "battle-effect-resource-pairs-v1"
        or resources["rom"]["sha256"] != ROM_SHA256
    ):
        raise ValueError("resource manifest identity mismatch")
    if (
        sequences.get("schema") != "battle-effect-sequence-bindings-v1"
        or sequences["rom"]["sha256"] != ROM_SHA256
    ):
        raise ValueError("sequence manifest identity mismatch")

    table_size = TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    resource_table = rom[
        RESOURCE_TABLE_OFFSET : RESOURCE_TABLE_OFFSET + table_size
    ]
    sprite_table = rom[
        SPRITE_PAIR_TABLE_OFFSET : SPRITE_PAIR_TABLE_OFFSET + table_size
    ]
    if _sha256(resource_table) != RESOURCE_TABLE_SHA256:
        raise ValueError("resource pointer table hash mismatch")
    if _sha256(sprite_table) != SPRITE_PAIR_TABLE_SHA256:
        raise ValueError("sprite pair table hash mismatch")
    motion_table, motion_records = _motion_records(rom)
    resource_entries = {
        entry["group_id"]: entry for entry in resources["entries"]
    }
    sequence_ids_by_group = {
        group_id: [] for group_id in range(1, TABLE_ENTRY_COUNT)
    }
    for sequence in sequences["sequences"]:
        for group_id in sequence["nonzero_resource_group_ids"]:
            sequence_ids_by_group[group_id].append(sequence["sequence_id"])

    outputs: dict[str, bytes] = {}
    groups = []
    for group_id in range(1, TABLE_ENTRY_COUNT):
        graphics_pointer, palette_pointer = struct.unpack_from(
            "<II", resource_table, group_id * TABLE_ENTRY_SIZE
        )
        definition_pointer, animation_pointer = struct.unpack_from(
            "<II", sprite_table, group_id * TABLE_ENTRY_SIZE
        )
        resource = resource_entries[group_id]
        if (
            resource["graphics"]["gba_address"] != _address(graphics_pointer)
            or resource["palette"]["gba_address"] != _address(palette_pointer)
        ):
            raise ValueError(f"group {group_id} resource pointers mismatch")
        asset_root = root / "artifacts/battle-effect-resource-pairs-v1"
        graphics = (
            asset_root / resource["graphics"]["output_bin"]
        ).read_bytes()
        palette = (asset_root / resource["palette"]["output_bin"]).read_bytes()
        if (
            _sha256(graphics) != resource["graphics"]["decompressed_sha256"]
            or _sha256(palette) != resource["palette"]["decompressed_sha256"]
        ):
            raise ValueError(f"group {group_id} source artifact hash mismatch")

        frames, timeline_start = _definitions(rom, definition_pointer)
        animations = _animations(
            rom,
            timeline_start,
            animation_pointer,
            len(frames),
        )
        referenced_tiles = set()
        for frame in frames:
            for item in frame["components"]:
                count = item["width"] * item["height"] // 64
                end = item["tile_index"] + count
                if end > resource["graphics"]["tile_count"]:
                    raise ValueError("component exceeds source graphics")
                referenced_tiles.update(range(item["tile_index"], end))
            preview, png = _preview(
                group_id,
                frame,
                graphics,
                palette,
            )
            frame["preview"] = preview
            outputs[preview["png"]] = png
        tile_count = resource["graphics"]["tile_count"]
        missing = sorted(set(range(tile_count)) - referenced_tiles)
        if missing:
            raise ValueError(f"group {group_id} has missing tile coverage")
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
                "animation_pointer_table": _address(animation_pointer),
                "timeline_region_start": _address(timeline_start),
                "graphics": dict(resource["graphics"]),
                "palette": dict(resource["palette"]),
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
                "definition_region_contiguous": True,
                "timeline_region_contiguous": True,
                "tile_coverage": {
                    "referenced_tile_indices": sorted(referenced_tiles),
                    "missing_tile_indices": missing,
                    "all_tiles_referenced": True,
                },
                "frames": frames,
                "animations": animations,
            }
        )

    playback_plans = _playback_plans(sequences, groups, motion_records)
    code_slices = []
    for name, start, gba_start, gba_end, digest in CODE_SLICES:
        end = int(gba_end, 16) - ROM_BASE
        if _sha256(rom[start:end]) != digest:
            raise ValueError(f"{name} code hash mismatch")
        code_slices.append(
            {
                "name": name,
                "file_offset": start,
                "gba_start": gba_start,
                "gba_end": gba_end,
                "sha256": digest,
            }
        )
    manifest = {
        "schema": "battle-effect-sprite-animations-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": _sha256(rom),
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
            "sha256": _sha256(sprite_table),
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
        "consumer_code_slices": code_slices,
        "child_task_origin_model": _child_task_origin_model(),
        "oam_attribute_model": _oam_attribute_model(groups, playback_plans),
        "dynamic_obj_vram_model": _dynamic_obj_vram_model(playback_plans),
        "pre_oam_coordinate_transform_model": (
            _pre_oam_coordinate_transform_model(groups)
        ),
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
            "child_task_origin_formulas_complete": True,
            "child_task_side_mirroring_formula_complete": True,
            "oam_shape_size_encoding_complete": True,
            "oam_coordinate_field_wrapping_complete": True,
            "normal_oam_tile_palette_priority_formula_complete": True,
            "guarded_oam_non_affine_flip_formula_complete": True,
            "pre_oam_runtime_offset_formula_complete": True,
            "pre_oam_scale_extent_formula_complete": True,
            "pre_oam_visibility_gate_complete": True,
            "concrete_runtime_offset_table_values_complete": False,
            "dynamic_obj_vram_enqueue_and_attr2_formula_complete": True,
            "dynamic_obj_vram_copy_queue_consumer_complete": True,
            "dynamic_obj_vram_hardware_frame_phase_complete": False,
            "concrete_rng_trajectory_complete": False,
            "callback_random_screen_coordinates_complete": False,
            "parent_visible_release_tick_exact": False,
            "screen_space_oam_composition_complete": False,
            "runtime_mirroring_and_affine_complete": False,
            "runtime_affine_rasterization_complete": False,
            "blend_and_audio_binding_complete": False,
        },
    }
    return manifest, outputs


def _compare(expected: Any, actual: Any, path: str, errors: list[str]) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(f"{path}: expected object")
            return
        for key in expected:
            if key not in actual:
                errors.append(f"{path}.{key}: missing")
            else:
                _compare(expected[key], actual[key], f"{path}.{key}", errors)
        for key in actual.keys() - expected.keys():
            errors.append(f"{path}.{key}: unexpected")
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            errors.append(f"{path}: expected list")
            return
        if len(expected) != len(actual):
            errors.append(f"{path}: length {len(actual)} != {len(expected)}")
        for index, (left, right) in enumerate(zip(expected, actual)):
            _compare(left, right, f"{path}[{index}]", errors)
    elif expected != actual:
        errors.append(f"{path}: {actual!r} != {expected!r}")


def verify_battle_effect_sprite_animations(
    root: Path | str,
    artifact_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root)
    artifact_dir = Path(artifact_dir)
    rom = (root / "rom/base.gba").read_bytes()
    empty = {
        "verified_groups": 0,
        "verified_frames": 0,
        "verified_components": 0,
        "verified_animations": 0,
    }
    if _sha256(rom) != ROM_SHA256:
        return {**empty, "errors": ["rom.sha256: unexpected base ROM"]}
    try:
        expected, outputs = _expected(root, rom)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return {**empty, "errors": [str(error)]}
    manifest_path = artifact_dir / "manifest.json"
    try:
        actual = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {**empty, "errors": [f"manifest.json: {error}"]}
    errors: list[str] = []
    _compare(expected, actual, "manifest", errors)
    actual_files = sorted(
        path.name for path in artifact_dir.iterdir() if path.is_file()
    )
    _compare(expected["artifact_files"], actual_files, "artifact_files", errors)
    for name, expected_bytes in outputs.items():
        path = artifact_dir / name
        try:
            actual_bytes = path.read_bytes()
        except OSError as error:
            errors.append(f"{name}: {error}")
            continue
        if _sha256(actual_bytes) != _sha256(expected_bytes):
            errors.append(
                f"{name}.png_sha256: {_sha256(actual_bytes)} "
                f"!= {_sha256(expected_bytes)}"
            )
    return {
        "verified_groups": 0 if errors else expected["group_count"],
        "verified_frames": (
            0 if errors else expected["frame_definition_count"]
        ),
        "verified_components": (
            0 if errors else expected["component_count"]
        ),
        "verified_animations": (
            0 if errors else expected["animation_count"]
        ),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/battle-effect-sprite-animations-v1"),
    )
    args = parser.parse_args()
    result = verify_battle_effect_sprite_animations(
        args.root,
        args.artifact_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
