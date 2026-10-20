#!/usr/bin/env python3
"""Generate ROM-backed battle sprites and timelines for all character IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.butano.indexed_bmp import write_4bpp_bmp

from tools.audit_butano_reverse_provenance import provenance_block

PROVENANCE = provenance_block(
    sources=(
        (
            "character-battle-visuals-v1",
            "a048eb6b494ceab3cee09ff3db98947ff739e750551e52d6692dc489c4c3db4c",
        ),
    ),
    roms=(
        (
            0x596D5C,
            8928,
            "baa3f86793e15d0d4abd44fcf10518da15ba0d76588b918838c3660e042e01dc",
        ),
    ),
)

# The products this generator writes.  The provenance auditor reads this
# registry to learn the product set; it never guesses the set from a file
# name pattern.
GENERATED_PRODUCTS = (
    "butano-sequel/game/include/konoha/generated_battle_unit_visual_content.h",
)


EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)
ROM_BASE = 0x08000000
VISUAL_TABLE_OFFSET = 0x596D5C
UNIT_COUNT = 62
SLOTS_PER_UNIT = 9
ROW_COUNT = UNIT_COUNT * SLOTS_PER_UNIT
ROW_SIZE = 16
FRAME_SIZE = 24
SUPPORTED_SPRITE_SIZES = {
    (8, 8),
    (16, 16),
    (32, 32),
    (64, 64),
    (16, 8),
    (32, 8),
    (32, 16),
    (64, 32),
    (8, 16),
    (8, 32),
    (16, 32),
    (32, 64),
}
SLOT_SEMANTICS = [
    "field_idle_and_movement",
    "cast_facing_right",
    "throw_facing_right",
    "melee_facing_right",
    "hit_facing_right",
    "cast_facing_left",
    "throw_facing_left",
    "melee_facing_left",
    "hit_facing_left",
]
MAX_COMPONENT_TRACKS = 5
MAX_SLOT_ASSETS = 8


def _rom_offset(
    pointer: int,
    size: int,
    rom_size: int,
    label: str,
) -> int:
    offset = pointer - ROM_BASE
    if (
        pointer < ROM_BASE
        or offset < 0
        or size < 0
        or offset + size > rom_size
    ):
        raise ValueError(
            f"{label} pointer is outside ROM: "
            f"0x{pointer:08X} size=0x{size:X}"
        )
    return offset


def _rgb555_palette(rom: bytes, pointer: int) -> list[tuple[int, int, int]]:
    offset = _rom_offset(pointer, 32, len(rom), "palette")
    result = []
    for index in range(16):
        value = struct.unpack_from("<H", rom, offset + index * 2)[0] & 0x7FFF
        result.append(
            tuple(
                ((value >> shift) & 31) * 255 // 31
                for shift in (0, 5, 10)
            )
        )
    # The field renderer reserves color 15 as a dynamic unit-selection mask.
    # The ROM table stores 0x0421, but the original resting palette writes
    # 0x0420 before display; the selected unit receives a brighter runtime
    # override.  Assets therefore carry only the state-free resting value.
    result[15] = (0, 8, 8)
    return result


def _decode_pixels(
    rom: bytes,
    tile_data_pointer: int,
    tile_index: int,
    width: int,
    height: int,
) -> bytes:
    byte_count = width * height // 2
    offset = _rom_offset(
        tile_data_pointer + tile_index * 32,
        byte_count,
        len(rom),
        "OBJ tile data",
    )
    pixels = bytearray()
    tiles_per_row = width // 8
    for y in range(height):
        for x in range(width):
            tile = (y // 8) * tiles_per_row + x // 8
            packed = rom[
                offset
                + tile * 32
                + (y & 7) * 4
                + (x & 7) // 2
            ]
            pixels.append((packed >> (4 if x & 1 else 0)) & 15)
    return bytes(pixels)


def _smallest_canvas(width: int, height: int) -> tuple[int, int]:
    candidates = [
        size
        for size in SUPPORTED_SPRITE_SIZES
        if size[0] >= width and size[1] >= height
    ]
    if not candidates:
        raise ValueError(
            f"no GBA OBJ shape can contain {width}x{height}"
        )
    return min(
        candidates,
        key=lambda size: (size[0] * size[1], size[1], size[0]),
    )


def _flip_horizontal(pixels: bytes, width: int, height: int) -> bytes:
    output = bytearray(len(pixels))
    for y in range(height):
        source = y * width
        output[source : source + width] = pixels[
            source : source + width
        ][::-1]
    return bytes(output)


def _paste(
    destination: bytearray,
    destination_width: int,
    source: bytes,
    source_width: int,
    source_height: int,
    x: int,
    y: int,
) -> None:
    for source_y in range(source_height):
        for source_x in range(source_width):
            color = source[source_y * source_width + source_x]
            if color:
                destination[
                    (y + source_y) * destination_width +
                    x + source_x
                ] = color


def _animation_pointers(
    rom: bytes,
    frame_table_pointer: int,
    animation_table_pointer: int,
) -> list[int]:
    offset = _rom_offset(
        animation_table_pointer,
        4,
        len(rom),
        "animation pointer table",
    )
    result = []
    for index in range(32):
        pointer = struct.unpack_from("<I", rom, offset + index * 4)[0]
        if not frame_table_pointer < pointer < animation_table_pointer:
            break
        result.append(pointer)
    if not result:
        raise ValueError("visual slot has no animation sequence")
    return result


def _decode_frame(
    rom: bytes,
    pointer: int,
    end_pointer: int,
    tile_data_pointer: int,
) -> dict[str, object]:
    span = end_pointer - pointer
    if span < FRAME_SIZE or (span - 4) % 20:
        raise ValueError(
            f"invalid composite frame span: 0x{pointer:08X}.."
            f"0x{end_pointer:08X}"
        )
    component_count = (span - 4) // 20
    if component_count < 1 or component_count > MAX_COMPONENT_TRACKS:
        raise ValueError(
            f"unsupported composite component count: {component_count}"
        )

    components = []
    for component_index in range(component_count):
        offset = _rom_offset(
            pointer + component_index * 20,
            FRAME_SIZE,
            len(rom),
            "frame component",
        )
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
            reserved_byte,
            reserved_12,
            next_tile_index,
            next_tile_flags,
        ) = struct.unpack_from("<HHhhHHHHBBHHH", rom, offset)
        if (width, height) not in SUPPORTED_SPRITE_SIZES:
            raise ValueError(
                f"unsupported Butano sprite size: {width}x{height}"
            )
        if scale_x != 0x100 or scale_y != 0x100:
            raise ValueError(
                f"frame has unsupported scale: {scale_x}x{scale_y}"
            )
        if tile_flags not in (0, 1):
            raise ValueError(
                f"unsupported frame tile flags: 0x{tile_flags:04X}"
            )
        if control != 0xFF or reserved_byte or reserved_12:
            raise ValueError("unexpected frame component control fields")

        pixels = _decode_pixels(
            rom,
            tile_data_pointer,
            tile_index & 0x3FF,
            width,
            height,
        )
        horizontal_flip = bool(tile_flags & 1)
        if horizontal_flip:
            pixels = _flip_horizontal(pixels, width, height)
        components.append(
            {
                "component_index": component_index,
                "tile_index": tile_index & 0x3FF,
                "tile_flags": tile_flags,
                "horizontal_flip": horizontal_flip,
                "origin": [x, y],
                "size": [width, height],
                "scale": [scale_x, scale_y],
                "pixels": pixels,
                "pixel_sha256": hashlib.sha256(pixels).hexdigest(),
                "next_tile_index": next_tile_index,
                "next_tile_flags": next_tile_flags,
                "frame_trailer_raw_hex": rom[
                    offset + 20:offset + 24
                ].hex(),
            }
        )

    for index in range(component_count - 1):
        current = components[index]
        following = components[index + 1]
        if (
            int(current["next_tile_index"]) & 0x3FF
            != int(following["tile_index"])
            or int(current["next_tile_flags"])
            != int(following["tile_flags"])
        ):
            raise ValueError("composite frame link mismatch")
    if int(components[-1]["next_tile_index"]) & 0x3FF != 0x3FF:
        raise ValueError("composite frame is not terminated")

    min_x = min(int(component["origin"][0]) for component in components)
    min_y = min(int(component["origin"][1]) for component in components)
    max_x = max(
        int(component["origin"][0]) + int(component["size"][0])
        for component in components
    )
    max_y = max(
        int(component["origin"][1]) + int(component["size"][1])
        for component in components
    )
    # The trailer of the last component is the frame's end marker.  The
    # renderer accepts -1 (0xFFFF) and nothing else, so a trailer that is
    # not -1 is a corrupt terminator: the renderer does not stop there and
    # keeps reading components behind the frame.  The original ROM carries
    # exactly one of them (character 26, visual slot 2, frame 2), and the
    # overrun is part of what the original draws, so the raw value is kept
    # and the defect is recorded instead of being silently swallowed.
    trailer = components[-1]
    trailer_raw = trailer["frame_trailer_raw_hex"]
    trailer_value = int(trailer["next_tile_index"])
    renderer_terminator = trailer_value == 0xFFFF
    return {
        "frame_pointer": pointer,
        "frame_pointer_hex": f"0x{pointer:08X}",
        "component_count": component_count,
        "components": components,
        "frame_trailer_raw_hex": trailer_raw,
        "frame_trailer_signed_value": (
            trailer_value - 0x10000 if trailer_value & 0x8000 else trailer_value
        ),
        "renderer_terminator": renderer_terminator,
        "bounds": [min_x, min_y, max_x, max_y],
        "size": [max_x - min_x, max_y - min_y],
    }


def _decode_visual_slot(
    rom: bytes,
    character_id: int,
    visual_slot: int,
    row: dict[str, int | bool],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    frame_table_pointer = int(row["frame_table_pointer"])
    animation_table_pointer = int(row["animation_table_pointer"])
    tile_data_pointer = int(row["tile_data_pointer"])
    first_animation_pointer = struct.unpack_from(
        "<I",
        rom,
        _rom_offset(
            animation_table_pointer,
            4,
            len(rom),
            "animation pointer table",
        ),
    )[0]
    frame_count_span = first_animation_pointer - frame_table_pointer
    if frame_count_span <= 0 or frame_count_span % 4:
        raise ValueError("invalid frame pointer table span")
    frame_count = frame_count_span // 4
    frame_table_offset = _rom_offset(
        frame_table_pointer,
        frame_count * 4,
        len(rom),
        "frame pointer table",
    )
    frame_pointers = list(
        struct.unpack_from(
            f"<{frame_count}I",
            rom,
            frame_table_offset,
        )
    )
    if frame_pointers != sorted(frame_pointers):
        raise ValueError("frame pointers are not ordered")
    frames = []
    for frame_index, frame_pointer in enumerate(frame_pointers):
        end_pointer = (
            frame_pointers[frame_index + 1]
            if frame_index + 1 < frame_count
            else frame_table_pointer
        )
        frame = _decode_frame(
            rom,
            frame_pointer,
            end_pointer,
            tile_data_pointer,
        )
        frame["frame_index"] = frame_index
        frames.append(frame)

    animation_pointers = _animation_pointers(
        rom,
        frame_table_pointer,
        animation_table_pointer,
    )
    animations = []
    for animation_index, pointer in enumerate(animation_pointers):
        offset = _rom_offset(pointer, 4, len(rom), "animation sequence")
        steps = []
        for step_index in range(64):
            frame_index, duration = struct.unpack_from(
                "<HH",
                rom,
                offset + step_index * 4,
            )
            if frame_index == 0xFFFF:
                break
            if frame_index >= frame_count or duration == 0:
                raise ValueError("invalid animation timeline step")
            steps.append(
                {
                    "frame_index": frame_index,
                    "duration": duration,
                }
            )
        else:
            raise ValueError("unterminated animation timeline")
        if not steps:
            raise ValueError("empty animation timeline")
        animations.append(
            {
                "animation_index": animation_index,
                "pointer": pointer,
                "pointer_hex": f"0x{pointer:08X}",
                "steps": steps,
                "total_duration": sum(step["duration"] for step in steps),
            }
        )

    component_track_count = max(
        int(frame["component_count"]) for frame in frames
    )
    component_assets = []
    frame_component_poses = [
        [
            {
                "visible": False,
                "center_offset": [0, 0],
                "asset_index": 255,
                "graphics_index": 0,
            }
            for _ in range(component_track_count)
        ]
        for _ in frames
    ]
    for component_index in range(component_track_count):
        shape_groups: dict[
            tuple[int, int],
            list[tuple[int, dict[str, object]]],
        ] = {}
        for frame_index, frame in enumerate(frames):
            if int(frame["component_count"]) <= component_index:
                continue
            component = frame["components"][component_index]
            width, height = component["size"]
            shape = _smallest_canvas(width, height)
            shape_groups.setdefault(shape, []).append(
                (frame_index, component)
            )
        for (
            canvas_width,
            canvas_height,
        ), shape_frames in shape_groups.items():
            asset_index = len(component_assets)
            sheet_pixels = bytearray(
                canvas_width *
                len(shape_frames) *
                canvas_height
            )
            for graphics_index, (
                frame_index,
                component,
            ) in enumerate(shape_frames):
                width, height = component["size"]
                component_pixels = component["pixels"]
                for y in range(height):
                    source = y * width
                    destination = (
                        (graphics_index * canvas_height + y)
                        * canvas_width
                    )
                    sheet_pixels[
                        destination : destination + width
                    ] = component_pixels[source : source + width]
                x, y = component["origin"]
                frame_component_poses[
                    frame_index
                ][component_index] = {
                    "visible": True,
                    "center_offset": [
                        x + canvas_width // 2,
                        y + canvas_height // 2,
                    ],
                    "asset_index": asset_index,
                    "graphics_index": graphics_index,
                }
            asset = (
                f"battle_unit_{character_id:02d}_slot_"
                f"{visual_slot}_part_{component_index}_"
                f"shape_{canvas_width}x{canvas_height}"
            )
            component_assets.append(
                {
                    "asset": asset,
                    "component_index": component_index,
                    "canvas_size": [
                        canvas_width,
                        canvas_height,
                    ],
                    "frame_count": len(shape_frames),
                    "pixels": bytes(sheet_pixels),
                }
            )

    if len(component_assets) > MAX_SLOT_ASSETS:
        raise ValueError(
            f"visual row {row['row']} requires "
            f"{len(component_assets)} assets"
        )

    for frame, poses in zip(frames, frame_component_poses):
        frame["component_poses"] = poses
    visual = {
        **row,
        "character_id": character_id,
        "visual_slot": visual_slot,
        "semantic": SLOT_SEMANTICS[visual_slot],
        "frame_count": frame_count,
        "animation_count": len(animations),
        "component_track_count": component_track_count,
        "frames": frames,
        "animations": animations,
        "component_assets": [
            {
                key: value
                for key, value in asset.items()
                if key != "pixels"
            }
            for asset in component_assets
        ],
    }
    return visual, component_assets


def _decode_idle(
    visual: dict[str, object],
    palette: list[tuple[int, int, int]],
) -> tuple[dict[str, object], bytes, list[tuple[int, int, int]]]:
    frame = visual["frames"][0]
    min_x, min_y, max_x, max_y = frame["bounds"]
    source_width = max_x - min_x
    source_height = max_y - min_y
    canvas_width, canvas_height = _smallest_canvas(
        source_width,
        source_height,
    )
    pixels = bytearray(canvas_width * canvas_height)
    for component in frame["components"]:
        x, y = component["origin"]
        width, height = component["size"]
        _paste(
            pixels,
            canvas_width,
            component["pixels"],
            width,
            height,
            x - min_x,
            y - min_y,
        )
    pixel_bytes = bytes(pixels)
    return (
        {
            "valid": True,
            "frame_pointer": frame["frame_pointer"],
            "frame_pointer_hex": frame["frame_pointer_hex"],
            "component_count": frame["component_count"],
            "bounds": frame["bounds"],
            "size": [source_width, source_height],
            "canvas_size": [canvas_width, canvas_height],
            "center_offset": [
                min_x + canvas_width // 2,
                min_y + canvas_height // 2,
            ],
            "pixel_sha256": hashlib.sha256(pixel_bytes).hexdigest(),
        },
        pixel_bytes,
        palette,
    )


def _load(
    rom_path: Path,
) -> tuple[
    dict[str, object],
    list[tuple[bytes, list[tuple[int, int, int]]]],
    list[dict[str, object]],
]:
    rom = Path(rom_path).read_bytes()
    source_sha256 = hashlib.sha256(rom).hexdigest()
    if source_sha256 != EXPECTED_ROM_SHA256:
        raise ValueError(f"ROM SHA-256 mismatch: {source_sha256}")
    table_size = ROW_COUNT * ROW_SIZE
    if VISUAL_TABLE_OFFSET + table_size > len(rom):
        raise ValueError("battle unit visual table exceeds ROM")

    rows: list[dict[str, int | bool]] = []
    valid_slot_count = 0
    for row_index in range(ROW_COUNT):
        values = struct.unpack_from(
            "<4I",
            rom,
            VISUAL_TABLE_OFFSET + row_index * ROW_SIZE,
        )
        if values == (0, 0, 0, 0):
            rows.append(
                {
                    "row": row_index,
                    "valid": False,
                    "frame_table_pointer": 0,
                    "animation_table_pointer": 0,
                    "tile_data_pointer": 0,
                    "palette_pointer": 0,
                }
            )
            continue
        if any(value == 0 for value in values):
            raise ValueError(
                f"visual row {row_index} is only partially populated"
            )
        for pointer_index, pointer in enumerate(values):
            _rom_offset(
                pointer,
                1,
                len(rom),
                f"visual row {row_index} pointer {pointer_index}",
            )
        valid_slot_count += 1
        rows.append(
            {
                "row": row_index,
                "valid": True,
                "frame_table_pointer": values[0],
                "animation_table_pointer": values[1],
                "tile_data_pointer": values[2],
                "palette_pointer": values[3],
            }
        )

    entries = []
    idle_assets = []
    visual_assets = []
    for character_id in range(1, UNIT_COUNT + 1):
        first_row = (character_id - 1) * SLOTS_PER_UNIT
        slots = rows[first_row : first_row + SLOTS_PER_UNIT]
        idle_row = slots[0]
        if not idle_row["valid"]:
            raise ValueError(
                f"character {character_id} has no idle visual"
            )
        visuals = []
        decoded_idle_visual = None
        idle_palette = None
        for visual_slot, row in enumerate(slots):
            if not row["valid"]:
                visuals.append(
                    {
                        **row,
                        "character_id": character_id,
                        "visual_slot": visual_slot,
                        "semantic": SLOT_SEMANTICS[visual_slot],
                    }
                )
                continue
            visual, assets = _decode_visual_slot(
                rom,
                character_id,
                visual_slot,
                row,
            )
            palette = _rgb555_palette(
                rom,
                int(row["palette_pointer"]),
            )
            for asset in assets:
                asset["palette"] = palette
            visual_assets.extend(assets)
            if visual_slot == 0:
                decoded_idle_visual = visual
                idle_palette = palette
            public_frames = []
            for frame in visual["frames"]:
                public_components = []
                for component in frame["components"]:
                    public_components.append(
                        {
                            key: value
                            for key, value in component.items()
                            if key != "pixels"
                        }
                    )
                public_frames.append(
                    {
                        **{
                            key: value
                            for key, value in frame.items()
                            if key != "components"
                        },
                        "components": public_components,
                    }
                )
            visuals.append(
                {
                    **{
                        key: value
                        for key, value in visual.items()
                        if key != "frames"
                    },
                    "frames": public_frames,
                }
            )
        if decoded_idle_visual is None or idle_palette is None:
            raise ValueError(
                f"character {character_id} has no decoded idle visual"
            )
        idle, pixels, palette = _decode_idle(
            decoded_idle_visual,
            idle_palette,
        )
        entries.append(
            {
                "character_id": character_id,
                "base_row": first_row,
                "valid_slots": [
                    index
                    for index, slot in enumerate(slots)
                    if slot["valid"]
                ],
                "slots": slots,
                "visuals": visuals,
                "idle": idle,
                "asset": f"battle_unit_{character_id:02d}_idle",
            }
        )
        idle_assets.append((pixels, palette))

    catalog = {
        "schema_version": 2,
        "source_rom_sha256": source_sha256,
        "table_offset": VISUAL_TABLE_OFFSET,
        "table_offset_hex": f"0x{VISUAL_TABLE_OFFSET:X}",
        "unit_count": UNIT_COUNT,
        "slots_per_unit": SLOTS_PER_UNIT,
        "row_count": ROW_COUNT,
        "row_size": ROW_SIZE,
        "valid_slot_count": valid_slot_count,
        "empty_slot_count": ROW_COUNT - valid_slot_count,
        "mapping": "row = (character_id - 1) * 9 + visual_slot",
        "slot_semantics": SLOT_SEMANTICS,
        "component_asset_count": len(visual_assets),
        "entries": entries,
    }
    return catalog, idle_assets, visual_assets


def load_battle_unit_visuals(
    rom_path: Path | str,
) -> dict[str, object]:
    """Load the complete sparse visual table and decoded idle metadata."""

    catalog, _, _ = _load(Path(rom_path))
    return catalog


def _generate_header(catalog: dict[str, object]) -> str:
    entries = catalog["entries"]
    idle_includes = [
        f'#include "bn_sprite_items_{entry["asset"]}.h"'
        for entry in entries
    ]
    component_includes = []
    visual_sections = []
    visual_cases = []
    for entry in entries:
        for visual in entry["visuals"]:
            if not visual["valid"]:
                continue
            for asset in visual["component_assets"]:
                component_includes.append(
                    f'#include "bn_sprite_items_{asset["asset"]}.h"'
                )
            prefix = (
                f'battle_unit_{entry["character_id"]:02d}_'
                f'slot_{visual["visual_slot"]}'
            )
            frame_lines = []
            for frame in visual["frames"]:
                poses = list(frame["component_poses"])
                while len(poses) < MAX_COMPONENT_TRACKS:
                    poses.append(
                        {
                            "visible": False,
                            "center_offset": [0, 0],
                            "asset_index": 255,
                            "graphics_index": 0,
                        }
                    )
                pose_text = ", ".join(
                    "battle_unit_visual_component_pose{ "
                    f'{pose["center_offset"][0]}, '
                    f'{pose["center_offset"][1]}, '
                    f'{"true" if pose["visible"] else "false"}, '
                    f'{pose["asset_index"]}, '
                    f'{pose["graphics_index"]}'
                    " }"
                    for pose in poses
                )
                frame_lines.append(
                    "    battle_unit_visual_frame{ { "
                    f"{pose_text}"
                    " } },"
                )
            flat_steps = []
            sequence_lines = []
            for animation in visual["animations"]:
                first_step = len(flat_steps)
                flat_steps.extend(animation["steps"])
                sequence_lines.append(
                    "    battle_unit_visual_sequence{ "
                    f"{first_step}, {len(animation['steps'])}, "
                    f"{animation['total_duration']}"
                    " },"
                )
            step_lines = [
                "    battle_unit_visual_timeline_step{ "
                f"{step['frame_index']}, {step['duration']}"
                " },"
                for step in flat_steps
            ]
            visual_sections.append(
                "inline constexpr std::array<"
                f"battle_unit_visual_frame, {visual['frame_count']}>\n"
                f"{prefix}_frames = {{{{\n"
                + "\n".join(frame_lines)
                + "\n}};\n\n"
                "inline constexpr std::array<"
                f"battle_unit_visual_timeline_step, {len(flat_steps)}>\n"
                f"{prefix}_steps = {{{{\n"
                + "\n".join(step_lines)
                + "\n}};\n\n"
                "inline constexpr std::array<"
                f"battle_unit_visual_sequence, {visual['animation_count']}>\n"
                f"{prefix}_sequences = {{{{\n"
                + "\n".join(sequence_lines)
                + "\n}};"
            )
            item_pointers = [
                f'&bn::sprite_items::{asset["asset"]}'
                for asset in visual["component_assets"]
            ]
            item_pointers.extend(
                ["nullptr"] *
                (MAX_SLOT_ASSETS - len(item_pointers))
            )
            visual_cases.append(
                f"        case {visual['row']}:\n"
                "            return battle_unit_visual_slot{\n"
                "                { "
                + ", ".join(item_pointers)
                + " },\n"
                f"                {prefix}_frames.data(),\n"
                f"                {prefix}_steps.data(),\n"
                f"                {prefix}_sequences.data(),\n"
                f"                {visual['frame_count']}, "
                f"{visual['animation_count']}, "
                f"{visual['component_track_count']}, "
                f"{len(visual['component_assets'])}\n"
                "            };"
            )
    includes = "\n".join(idle_includes + component_includes)
    idle_cases = []
    for entry in entries:
        center_x, center_y = entry["idle"]["center_offset"]
        idle_cases.append(
            "        case "
            f'{entry["character_id"]}:\n'
            "            return battle_unit_idle_visual{\n"
            "                &bn::sprite_items::"
            f'{entry["asset"]}, {center_x}, {center_y}\n'
            "            };"
        )
    idle_case_text = "\n".join(idle_cases)
    visual_section_text = "\n\n".join(visual_sections)
    visual_case_text = "\n".join(visual_cases)
    return f"""// Generated by tools/generate_butano_battle_unit_visual_content.py.
// Do not edit.
{PROVENANCE}
#ifndef KONOHA_GENERATED_BATTLE_UNIT_VISUAL_CONTENT_H
#define KONOHA_GENERATED_BATTLE_UNIT_VISUAL_CONTENT_H

#include "bn_sprite_item.h"
#include "konoha/battle_unit_visual_animation.h"
{includes}

#include <array>
#include <cstdint>

namespace konoha
{{

struct battle_unit_idle_visual
{{
    const bn::sprite_item* item = nullptr;
    int center_offset_x = 0;
    int center_offset_y = 0;
}};

inline constexpr int battle_unit_visual_max_components =
        {MAX_COMPONENT_TRACKS};
inline constexpr int battle_unit_visual_max_assets =
        {MAX_SLOT_ASSETS};
struct battle_unit_visual_component_pose
{{
    int center_offset_x = 0;
    int center_offset_y = 0;
    bool visible = false;
    std::uint8_t asset_index = 0xFF;
    std::uint8_t graphics_index = 0;
}};

struct battle_unit_visual_frame
{{
    battle_unit_visual_component_pose
            components[battle_unit_visual_max_components] = {{}};
}};

struct battle_unit_visual_sequence
{{
    std::uint16_t first_step = 0;
    std::uint8_t step_count = 0;
    std::uint16_t total_duration = 0;
}};

struct battle_unit_visual_slot
{{
    const bn::sprite_item*
            component_items[battle_unit_visual_max_assets] = {{}};
    const battle_unit_visual_frame* frames = nullptr;
    const battle_unit_visual_timeline_step* steps = nullptr;
    const battle_unit_visual_sequence* sequences = nullptr;
    std::uint8_t frame_count = 0;
    std::uint8_t sequence_count = 0;
    std::uint8_t component_track_count = 0;
    std::uint8_t asset_count = 0;

    [[nodiscard]] constexpr explicit operator bool() const
    {{
        return component_track_count != 0;
    }}
}};

{visual_section_text}

[[nodiscard]] inline battle_unit_idle_visual
battle_unit_idle_visual_for(std::uint8_t character_id)
{{
    switch(character_id)
    {{
{idle_case_text}
        default:
            return battle_unit_idle_visual{{}};
    }}
}}

[[nodiscard]] inline battle_unit_visual_slot
battle_unit_visual_slot_for(
        std::uint8_t character_id,
        std::uint8_t visual_slot)
{{
    if(character_id < 1 || character_id > {UNIT_COUNT} ||
            visual_slot >= {SLOTS_PER_UNIT})
    {{
        return battle_unit_visual_slot{{}};
    }}
    const int row =
            (static_cast<int>(character_id) - 1) *
                    {SLOTS_PER_UNIT} +
            visual_slot;
    switch(row)
    {{
{visual_case_text}
        default:
            return battle_unit_visual_slot{{}};
    }}
}}

}}

#endif
"""


def generate(
    rom_path: Path | str,
    graphics_directory: Path | str,
    header_path: Path | str,
    catalog_path: Path | str,
) -> dict[str, object]:
    """Generate idle sprites, complete visual slots and C++ catalogs."""

    catalog, idle_assets, visual_assets = _load(Path(rom_path))
    graphics_directory = Path(graphics_directory)
    header_path = Path(header_path)
    catalog_path = Path(catalog_path)
    graphics_directory.mkdir(parents=True, exist_ok=True)
    header_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)

    entries = catalog["entries"]
    if len(entries) != len(idle_assets):
        raise ValueError(
            f"visual entry/asset count mismatch: {len(entries)} != {len(idle_assets)}"
        )
    expected_visual_files = {
        f'{asset["asset"]}{suffix}'
        for asset in visual_assets
        for suffix in (".bmp", ".json")
    }
    for stale_path in graphics_directory.glob(
        "battle_unit_*_slot_*_part_*"
    ):
        if (
            stale_path.is_file()
            and stale_path.name not in expected_visual_files
            and stale_path.suffix in {".bmp", ".json"}
        ):
            stale_path.unlink()

    for entry, (pixels, palette) in zip(entries, idle_assets):
        asset = entry["asset"]
        width, height = entry["idle"]["canvas_size"]
        write_4bpp_bmp(
            graphics_directory / f"{asset}.bmp",
            width,
            height,
            pixels,
            palette,
        )
        (graphics_directory / f"{asset}.json").write_text(
            json.dumps(
                {
                    "type": "sprite",
                    "height": height,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    for asset in visual_assets:
        canvas_width, canvas_height = asset["canvas_size"]
        frame_count = int(asset["frame_count"])
        write_4bpp_bmp(
            graphics_directory / f'{asset["asset"]}.bmp',
            canvas_width,
            canvas_height * frame_count,
            asset["pixels"],
            asset["palette"],
        )
        (graphics_directory / f'{asset["asset"]}.json').write_text(
            json.dumps(
                {
                    "type": "sprite",
                    "height": canvas_height,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    catalog_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    header_path.write_text(
        _generate_header(catalog),
        encoding="utf-8",
    )
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        default=Path("rom/base.gba"),
    )
    parser.add_argument(
        "--graphics",
        type=Path,
        default=Path("butano-sequel/graphics"),
    )
    parser.add_argument(
        "--header",
        type=Path,
        default=Path(
            "butano-sequel/game/include/konoha/"
            "generated_battle_unit_visual_content.h"
        ),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(
            "butano-sequel/graphics/battle_unit_visual_catalog.json"
        ),
    )
    args = parser.parse_args()
    catalog = generate(
        args.rom,
        args.graphics,
        args.header,
        args.catalog,
    )
    print(
        "generated "
        f'{catalog["unit_count"]} battle unit idle sprites '
        f'from {catalog["valid_slot_count"]}/'
        f'{catalog["row_count"]} valid visual slots'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
