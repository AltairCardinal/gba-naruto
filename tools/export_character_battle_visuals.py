#!/usr/bin/env python3
"""Export the complete 62x9 character battle OBJ visual matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import sys
import tempfile
import uuid
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
TABLE_OFFSET = 0x596D5C
CHARACTER_COUNT = 62
SLOTS_PER_CHARACTER = 9
SLOT_COUNT = CHARACTER_COUNT * SLOTS_PER_CHARACTER
DESCRIPTOR_SIZE = 16
TABLE_SIZE = SLOT_COUNT * DESCRIPTOR_SIZE
TABLE_SHA256 = "baa3f86793e15d0d4abd44fcf10518da15ba0d76588b918838c3660e042e01dc"
SELECTOR_OFFSET = 0x07AE04
SELECTOR_END_OFFSET = 0x07B284
SELECTOR_SHA256 = "5a0d06474ee94f5d3fd68cfe6c90224ce5a4cc8ffbb8ceeb6c4529c67ecd1b0b"
ALLOCATOR_OFFSET = 0x0625A4
ALLOCATOR_END_OFFSET = 0x0626B0
ALLOCATOR_SHA256 = "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54"
COMPONENT_SIZE = 20
COMPONENT_TERMINATOR = bytes.fromhex("ffff0000")
KNOWN_ANOMALOUS_TRAILER = bytes.fromhex("fffb0000")
SLOT_SEMANTICS = (
    "field_idle_and_movement",
    "cast_facing_right",
    "throw_facing_right",
    "melee_facing_right",
    "hit_facing_right",
    "cast_facing_left",
    "throw_facing_left",
    "melee_facing_left",
    "hit_facing_left",
)
SLOT_SELECTOR_ROLES = (
    {"opcodes": [0, 1, 2], "facing": None, "counterpart": None},
    {"opcodes": [3], "facing": 0, "counterpart": 5},
    {"opcodes": [4], "facing": 0, "counterpart": 6},
    {"opcodes": [5], "facing": 0, "counterpart": 7},
    {"opcodes": [6, 7], "facing": 0, "counterpart": 8},
    {"opcodes": [3], "facing": 1, "counterpart": 1},
    {"opcodes": [4], "facing": 1, "counterpart": 2},
    {"opcodes": [5], "facing": 1, "counterpart": 3},
    {"opcodes": [6, 7], "facing": 1, "counterpart": 4},
)
SUPPORTED_SIZES = {
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _rom_offset(pointer: int, size: int, rom_size: int, label: str) -> int:
    offset = pointer - ROM_BASE
    if pointer < ROM_BASE or size < 0 or offset < 0 or offset + size > rom_size:
        raise ValueError(
            f"{label} is outside ROM: {_address(pointer)} size=0x{size:X}"
        )
    return offset


def _source_file(
    *,
    path: str,
    pointer: int,
    data: bytes,
) -> dict[str, Any]:
    return {
        "file": path,
        "gba_pointer": _address(pointer),
        "size": len(data),
        "sha256": _sha256(data),
    }


def validate_output_target(root: Path, output_dir: Path) -> Path:
    """Return a safe artifact target without following an existing symlink."""

    root = root.resolve()
    requested = output_dir.expanduser()
    if requested.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    target = requested.resolve()
    if target == root or target in root.parents:
        raise ValueError("output directory must not be the repository or its ancestor")
    if target.exists():
        if not target.is_dir():
            raise ValueError("existing output target is not a directory")
        manifest_path = target / "manifest.json"
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            ) from error
        if existing.get("schema") != "character-battle-visuals-v1":
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            )
    return target


def _replace_output_transactionally(
    output_dir: Path,
    files: dict[str, bytes],
    manifest: dict[str, Any],
) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.tmp-",
            dir=output_dir.parent,
        )
    )
    backup: Path | None = None
    try:
        for relative, data in sorted(files.items()):
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            backup = output_dir.parent / (
                f".{output_dir.name}.backup-{uuid.uuid4().hex}"
            )
            output_dir.rename(backup)
        try:
            temporary.rename(output_dir)
        except BaseException:
            if backup is not None and backup.exists() and not output_dir.exists():
                backup.rename(output_dir)
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
        if backup is not None and backup.exists() and output_dir.exists():
            shutil.rmtree(backup)


def _parse_descriptor_rows(
    rom: bytes,
) -> tuple[bytes, list[tuple[int, int, int, int]]]:
    table = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    if len(table) != TABLE_SIZE or _sha256(table) != TABLE_SHA256:
        raise ValueError("character battle visual table SHA-256 mismatch")
    rows = [
        struct.unpack_from("<4I", table, row * DESCRIPTOR_SIZE)
        for row in range(SLOT_COUNT)
    ]
    for row, values in enumerate(rows):
        if values == (0, 0, 0, 0):
            continue
        if any(value == 0 for value in values):
            raise ValueError(f"descriptor row {row} is partially populated")
        for column, pointer in enumerate(values):
            _rom_offset(
                pointer,
                1,
                len(rom),
                f"descriptor row {row} pointer {column}",
            )
    return table, rows


def _animation_pointers(
    rom: bytes,
    *,
    frame_pointer_table: int,
    animation_pointer_table: int,
) -> list[int]:
    offset = _rom_offset(
        animation_pointer_table,
        4,
        len(rom),
        "animation pointer table",
    )
    result: list[int] = []
    for index in range(64):
        pointer = struct.unpack_from("<I", rom, offset + index * 4)[0]
        if not frame_pointer_table < pointer < animation_pointer_table:
            break
        if result and pointer <= result[-1]:
            raise ValueError("animation timeline pointers are not increasing")
        result.append(pointer)
    if not result:
        raise ValueError("visual resource has no animation timeline")
    return result


def _frame_pointers(
    rom: bytes,
    *,
    frame_pointer_table: int,
    first_timeline_pointer: int,
) -> list[int]:
    span = first_timeline_pointer - frame_pointer_table
    if span <= 0 or span % 4:
        raise ValueError("frame pointer table has an invalid span")
    if span // 4 > 128:
        raise ValueError("frame pointer table exceeds the safety bound")
    offset = _rom_offset(
        frame_pointer_table,
        span,
        len(rom),
        "frame pointer table",
    )
    pointers = list(struct.unpack_from(f"<{span // 4}I", rom, offset))
    if pointers != sorted(pointers) or len(set(pointers)) != len(pointers):
        raise ValueError("frame component pointers are not strictly increasing")
    if not pointers or not all(pointer < frame_pointer_table for pointer in pointers):
        raise ValueError("frame component pointer is outside its bounded region")
    return pointers


def _parse_component(raw: bytes, index: int) -> dict[str, Any]:
    if len(raw) != COMPONENT_SIZE:
        raise ValueError("component record is truncated")
    (
        tile_index,
        orientation,
        angle_offset,
        x,
        y,
        width,
        height,
        scale_x,
        scale_y,
        control,
        attribute,
        reserved,
    ) = struct.unpack("<HBBhhHHHHBBH", raw)
    if (width, height) not in SUPPORTED_SIZES:
        raise ValueError(f"component {index} has unsupported size {width}x{height}")
    if orientation & ~0x03:
        raise ValueError(
            f"component {index} has unknown orientation 0x{orientation:02X}"
        )
    if scale_x != 0x100 or scale_y != 0x100:
        raise ValueError(
            f"component {index} has unsupported scale {scale_x}x{scale_y}"
        )
    if angle_offset or control != 0xFF or attribute or reserved:
        raise ValueError(f"component {index} has unknown control fields")
    tile_offset = tile_index & 0x03FF
    return {
        "component_index": index,
        "tile_index_raw": tile_index,
        "tile_offset": tile_offset,
        "orientation": orientation,
        "horizontal_flip": bool(orientation & 1),
        "vertical_flip": bool(orientation & 2),
        "affine_angle_offset": angle_offset,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "control": control,
        "attribute": attribute,
        "reserved": reserved,
        "tile_end": tile_offset + (width // 8) * (height // 8),
        "raw_hex": raw.hex(),
        "raw_sha256": _sha256(raw),
    }


def _parse_frames(
    rom: bytes,
    *,
    pointers: list[int],
    frame_pointer_table: int,
) -> tuple[bytes, list[dict[str, Any]]]:
    starts = pointers
    ends = pointers[1:] + [frame_pointer_table]
    region_start = starts[0]
    frames: list[dict[str, Any]] = []
    for frame_id, (pointer, end_pointer) in enumerate(zip(starts, ends)):
        span = end_pointer - pointer
        if span < len(COMPONENT_TERMINATOR) or (
            span - len(COMPONENT_TERMINATOR)
        ) % COMPONENT_SIZE:
            raise ValueError(f"frame {frame_id} has an invalid component span")
        offset = _rom_offset(pointer, span, len(rom), f"frame {frame_id}")
        raw = rom[offset : offset + span]
        trailer = raw[-4:]
        if trailer not in (COMPONENT_TERMINATOR, KNOWN_ANOMALOUS_TRAILER):
            raise ValueError(f"frame {frame_id} has an unknown component trailer")
        components = [
            _parse_component(
                raw[
                    index * COMPONENT_SIZE :
                    (index + 1) * COMPONENT_SIZE
                ],
                index,
            )
            for index in range((span - 4) // COMPONENT_SIZE)
        ]
        if not components:
            raise ValueError(f"frame {frame_id} is empty")
        frames.append(
            {
                "frame_id": frame_id,
                "component_list_pointer": _address(pointer),
                "component_count": len(components),
                "components": components,
                "raw_size": len(raw),
                "raw_sha256": _sha256(raw),
                "frame_trailer_raw_hex": trailer.hex(),
                "renderer_terminator": trailer == COMPONENT_TERMINATOR,
                "render_complete": trailer == COMPONENT_TERMINATOR,
                "interpretation": (
                    "verified_renderer_terminated"
                    if trailer == COMPONENT_TERMINATOR
                    else "provisional_pointer_bounded_preview"
                ),
            }
        )
    region_offset = _rom_offset(
        region_start,
        frame_pointer_table - region_start,
        len(rom),
        "component region",
    )
    return rom[region_offset : region_offset + frame_pointer_table - region_start], frames


def _parse_animations(
    rom: bytes,
    *,
    pointers: list[int],
    animation_pointer_table: int,
    frame_count: int,
) -> tuple[bytes, list[dict[str, Any]]]:
    animations: list[dict[str, Any]] = []
    for animation_id, (pointer, expected_end) in enumerate(
        zip(pointers, pointers[1:] + [animation_pointer_table])
    ):
        offset = _rom_offset(
            pointer,
            expected_end - pointer,
            len(rom),
            f"animation {animation_id}",
        )
        cursor = offset
        keyframes = []
        for _ in range(256):
            frame_id, hold_frames = struct.unpack_from("<HH", rom, cursor)
            cursor += 4
            if frame_id == 0xFFFF:
                if hold_frames:
                    raise ValueError("animation terminator hold is not zero")
                break
            if frame_id >= frame_count or hold_frames == 0:
                raise ValueError(f"animation {animation_id} has an invalid keyframe")
            keyframes.append(
                {
                    "frame_id": frame_id,
                    "hold_frames": hold_frames,
                }
            )
        else:
            raise ValueError(f"animation {animation_id} has no terminator")
        if not keyframes or ROM_BASE + cursor != expected_end:
            raise ValueError(f"animation {animation_id} is empty or non-contiguous")
        raw = rom[offset:cursor]
        animations.append(
            {
                "animation_id": animation_id,
                "timeline_pointer": _address(pointer),
                "keyframe_count": len(keyframes),
                "duration_frames": sum(
                    keyframe["hold_frames"] for keyframe in keyframes
                ),
                "keyframes": keyframes,
                "terminator": {"frame_id": 0xFFFF, "hold_frames": 0},
                "raw_size": len(raw),
                "raw_sha256": _sha256(raw),
            }
        )
    start = pointers[0]
    offset = _rom_offset(
        start,
        animation_pointer_table - start,
        len(rom),
        "timeline region",
    )
    return rom[offset : offset + animation_pointer_table - start], animations


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
    output = bytearray(len(pixels))
    for y in range(height):
        source_y = height - 1 - y if vertical else y
        for x in range(width):
            source_x = width - 1 - x if horizontal else x
            output[y * width + x] = pixels[source_y * width + source_x]
    return bytes(output)


def _render_frame(
    frame: dict[str, Any],
    graphics: bytes,
    palette: bytes,
) -> tuple[dict[str, Any], bytes]:
    components = frame["components"]
    min_x = min(component["x"] for component in components)
    min_y = min(component["y"] for component in components)
    max_x = max(component["x"] + component["width"] for component in components)
    max_y = max(component["y"] + component["height"] for component in components)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        raise ValueError(f"frame {frame['frame_id']} has invalid bounds")
    canvas = bytearray(width * height)
    for component in components:
        pixels, component_width, component_height = render_4bpp_tile_block_indices(
            graphics,
            tile_offset=component["tile_offset"],
            width_tiles=component["width"] // 8,
            height_tiles=component["height"] // 8,
        )
        pixels = _flip_pixels(
            pixels,
            component_width,
            component_height,
            horizontal=component["horizontal_flip"],
            vertical=component["vertical_flip"],
        )
        destination_x = component["x"] - min_x
        destination_y = component["y"] - min_y
        for local_y in range(component_height):
            for local_x in range(component_width):
                color = pixels[local_y * component_width + local_x]
                if color:
                    canvas[
                        (destination_y + local_y) * width
                        + destination_x
                        + local_x
                    ] = color
    pixel_bytes = bytes(canvas)
    png = indexed_png_from_bgr555(
        pixel_bytes,
        palette,
        width=width,
        height=height,
        transparent_index=0,
    )
    return (
        {
            "width": width,
            "height": height,
            "component_local_bounds": {
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
            },
            "pixel_sha256": _sha256(pixel_bytes),
            "png_sha256": _sha256(png),
            "rendering_scope": (
                "source-space component order with H/V flips; runtime screen "
                "position, camera, priority and affine transforms are not applied"
            ),
        },
        png,
    )


def _decode_resource(
    rom: bytes,
    resource_id: int,
    descriptor: tuple[int, int, int, int],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    (
        frame_pointer_table,
        animation_pointer_table,
        graphics_pointer,
        palette_pointer,
    ) = descriptor
    animation_pointers = _animation_pointers(
        rom,
        frame_pointer_table=frame_pointer_table,
        animation_pointer_table=animation_pointer_table,
    )
    frame_pointers = _frame_pointers(
        rom,
        frame_pointer_table=frame_pointer_table,
        first_timeline_pointer=animation_pointers[0],
    )
    component_region, frames = _parse_frames(
        rom,
        pointers=frame_pointers,
        frame_pointer_table=frame_pointer_table,
    )
    timeline_region, animations = _parse_animations(
        rom,
        pointers=animation_pointers,
        animation_pointer_table=animation_pointer_table,
        frame_count=len(frames),
    )
    frame_table_offset = _rom_offset(
        frame_pointer_table,
        len(frame_pointers) * 4,
        len(rom),
        "frame pointer table",
    )
    frame_table = rom[
        frame_table_offset : frame_table_offset + len(frame_pointers) * 4
    ]
    animation_table_offset = _rom_offset(
        animation_pointer_table,
        len(animation_pointers) * 4,
        len(rom),
        "animation pointer table",
    )
    animation_table = rom[
        animation_table_offset :
        animation_table_offset + len(animation_pointers) * 4
    ]
    tile_count = max(
        component["tile_end"]
        for frame in frames
        for component in frame["components"]
    )
    graphics_offset = _rom_offset(
        graphics_pointer,
        tile_count * 32,
        len(rom),
        "graphics",
    )
    graphics = rom[graphics_offset : graphics_offset + tile_count * 32]
    palette_offset = _rom_offset(palette_pointer, 32, len(rom), "palette")
    palette = rom[palette_offset : palette_offset + 32]

    prefix = f"resource-{resource_id:03d}"
    files = {
        f"{prefix}/component-region.bin": component_region,
        f"{prefix}/frame-pointer-table.bin": frame_table,
        f"{prefix}/timeline-region.bin": timeline_region,
        f"{prefix}/animation-pointer-table.bin": animation_table,
        f"{prefix}/graphics-4bpp.bin": graphics,
        f"{prefix}/palette-bgr555.bin": palette,
    }
    source_entries = {
        "component_region": _source_file(
            path=f"{prefix}/component-region.bin",
            pointer=frame_pointers[0],
            data=component_region,
        ),
        "frame_pointer_table": _source_file(
            path=f"{prefix}/frame-pointer-table.bin",
            pointer=frame_pointer_table,
            data=frame_table,
        ),
        "timeline_region": _source_file(
            path=f"{prefix}/timeline-region.bin",
            pointer=animation_pointers[0],
            data=timeline_region,
        ),
        "animation_pointer_table": _source_file(
            path=f"{prefix}/animation-pointer-table.bin",
            pointer=animation_pointer_table,
            data=animation_table,
        ),
        "graphics": {
            **_source_file(
                path=f"{prefix}/graphics-4bpp.bin",
                pointer=graphics_pointer,
                data=graphics,
            ),
            "tile_count": tile_count,
        },
        "palette": {
            **_source_file(
                path=f"{prefix}/palette-bgr555.bin",
                pointer=palette_pointer,
                data=palette,
            ),
            "color_count": 16,
        },
    }

    public_frames = []
    for frame in frames:
        rendered, png = _render_frame(frame, graphics, palette)
        png_path = f"{prefix}/frame-{frame['frame_id']:03d}.png"
        files[png_path] = png
        public_frames.append({**frame, **rendered, "png": png_path})
    return (
        {
            "resource_id": resource_id,
            "descriptor": {
                "frame_pointer_table": _address(frame_pointer_table),
                "animation_pointer_table": _address(animation_pointer_table),
                "graphics": _address(graphics_pointer),
                "palette": _address(palette_pointer),
            },
            **source_entries,
            "frame_count": len(frames),
            "component_count": sum(
                frame["component_count"] for frame in frames
            ),
            "animation_count": len(animations),
            "keyframe_count": sum(
                animation["keyframe_count"] for animation in animations
            ),
            "frames": public_frames,
            "animations": animations,
            "slot_rows": [],
        },
        files,
    )


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    output_dir = validate_output_target(root, output_dir)
    rom_path = root / "rom" / "base.gba"
    rom = rom_path.read_bytes()
    rom_sha256 = _sha256(rom)
    if rom_sha256 != ROM_SHA256:
        raise ValueError(f"ROM SHA-256 mismatch: {rom_sha256}")
    table, rows = _parse_descriptor_rows(rom)
    selector = rom[SELECTOR_OFFSET:SELECTOR_END_OFFSET]
    allocator = rom[ALLOCATOR_OFFSET:ALLOCATOR_END_OFFSET]
    if _sha256(selector) != SELECTOR_SHA256:
        raise ValueError("character battle visual selector SHA-256 mismatch")
    if _sha256(allocator) != ALLOCATOR_SHA256:
        raise ValueError("sprite task allocator SHA-256 mismatch")

    resource_by_descriptor: dict[tuple[int, int, int, int], int] = {}
    resources: list[dict[str, Any]] = []
    files: dict[str, bytes] = {}
    slots = []
    for row, descriptor in enumerate(rows):
        populated = descriptor != (0, 0, 0, 0)
        resource_id = None
        if populated:
            resource_id = resource_by_descriptor.get(descriptor)
            if resource_id is None:
                resource_id = len(resources)
                resource_by_descriptor[descriptor] = resource_id
                resource, resource_files = _decode_resource(
                    rom,
                    resource_id,
                    descriptor,
                )
                resources.append(resource)
                files.update(resource_files)
            resources[resource_id]["slot_rows"].append(row)
        slots.append(
            {
                "row": row,
                "character_id": row // SLOTS_PER_CHARACTER + 1,
                "visual_slot": row % SLOTS_PER_CHARACTER,
                "semantic": SLOT_SEMANTICS[row % SLOTS_PER_CHARACTER],
                "populated": populated,
                "resource_id": resource_id,
                "descriptor_raw_hex": table[
                    row * DESCRIPTOR_SIZE : (row + 1) * DESCRIPTOR_SIZE
                ].hex(),
                "descriptor": (
                    None
                    if not populated
                    else {
                        "frame_pointer_table": _address(descriptor[0]),
                        "animation_pointer_table": _address(descriptor[1]),
                        "graphics": _address(descriptor[2]),
                        "palette": _address(descriptor[3]),
                    }
                ),
            }
        )

    summary = {
        "character_count": CHARACTER_COUNT,
        "slots_per_character": SLOTS_PER_CHARACTER,
        "slot_count": SLOT_COUNT,
        "populated_slot_count": sum(slot["populated"] for slot in slots),
        "empty_slot_count": sum(not slot["populated"] for slot in slots),
        "resource_count": len(resources),
        "unique_palette_count": len(
            {resource["descriptor"]["palette"] for resource in resources}
        ),
        "unique_palette_content_count": len(
            {resource["palette"]["sha256"] for resource in resources}
        ),
        "frame_count": sum(resource["frame_count"] for resource in resources),
        "component_count": sum(
            resource["component_count"] for resource in resources
        ),
        "animation_count": sum(
            resource["animation_count"] for resource in resources
        ),
        "keyframe_count": sum(
            resource["keyframe_count"] for resource in resources
        ),
        "resource_tile_count": sum(
            resource["graphics"]["tile_count"] for resource in resources
        ),
        "logical_frame_count": sum(
            resources[slot["resource_id"]]["frame_count"]
            for slot in slots
            if slot["populated"]
        ),
        "logical_component_count": sum(
            resources[slot["resource_id"]]["component_count"]
            for slot in slots
            if slot["populated"]
        ),
        "logical_animation_count": sum(
            resources[slot["resource_id"]]["animation_count"]
            for slot in slots
            if slot["populated"]
        ),
        "logical_keyframe_count": sum(
            resources[slot["resource_id"]]["keyframe_count"]
            for slot in slots
            if slot["populated"]
        ),
        "populated_slots_by_visual_slot": [
            sum(
                slot["populated"] and slot["visual_slot"] == visual_slot
                for slot in slots
            )
            for visual_slot in range(SLOTS_PER_CHARACTER)
        ],
        "renderer_terminator_frame_count": sum(
            frame["renderer_terminator"]
            for resource in resources
            for frame in resource["frames"]
        ),
        "anomalous_frame_trailer_count": sum(
            not frame["renderer_terminator"]
            for resource in resources
            for frame in resource["frames"]
        ),
        "verified_static_source_space_frame_count": sum(
            frame["render_complete"]
            for resource in resources
            for frame in resource["frames"]
        ),
        "provisional_pointer_bounded_frame_count": sum(
            not frame["render_complete"]
            for resource in resources
            for frame in resource["frames"]
        ),
    }
    manifest = {
        "schema": "character-battle-visuals-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_sha256,
        },
        "table": {
            "gba_start": _address(ROM_BASE + TABLE_OFFSET),
            "gba_end": _address(ROM_BASE + TABLE_OFFSET + TABLE_SIZE),
            "file_offset": TABLE_OFFSET,
            "entry_size": DESCRIPTOR_SIZE,
            "entry_count": SLOT_COUNT,
            "sha256": _sha256(table),
            "row_formula": "(character_id - 1) * 9 + visual_slot",
        },
        "consumer": {
            "prebiased_matrix_base": "0x08596CCC",
            "descriptor_formula": (
                "0x08596CCC + character_id * 0x90 + visual_slot * 0x10"
            ),
            "selector": {
                "gba_start": "0x0807AE04",
                "gba_end": "0x0807B284",
                "size": len(selector),
                "sha256": _sha256(selector),
                "opcode_domain": list(range(8)),
            },
            "sprite_task_allocator": {
                "gba_start": "0x080625A4",
                "gba_end": "0x080626B0",
                "size": len(allocator),
                "sha256": _sha256(allocator),
            },
            "left_facing_empty_slot_fallback": {
                "from_slots": [5, 6, 7, 8],
                "to_slots": [1, 2, 3, 4],
                "horizontal_flip_flag": "0x8000",
            },
        },
        "slot_semantics": [
            {
                "visual_slot": index,
                "name": name,
                "name_basis": (
                    "existing project vocabulary; selector opcode mapping is "
                    "authoritative, natural-scene business naming remains scoped"
                ),
                **SLOT_SELECTOR_ROLES[index],
            }
            for index, name in enumerate(SLOT_SEMANTICS)
        ],
        "summary": summary,
        "scope": {
            "static_source_space_frames": False,
            "pointer_bounded_source_previews": True,
            "component_geometry_and_flips": True,
            "animation_holds": True,
            "screen_space_position": False,
            "camera_and_priority": False,
            "runtime_slot_selection": False,
            "blend_and_palette_transform": False,
            "all_component_termination_semantics_complete": False,
        },
        "slots": slots,
        "resources": resources,
    }

    _replace_output_transactionally(output_dir, files, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the complete character battle OBJ visual matrix"
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/character-battle-visuals-v1"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    requested_output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else root / args.output_dir
    )
    output_dir = validate_output_target(root, requested_output_dir)
    manifest = export_artifact(root, output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "slots": manifest["summary"]["slot_count"],
                "populated_slots": manifest["summary"]["populated_slot_count"],
                "resources": manifest["summary"]["resource_count"],
                "frames": manifest["summary"]["frame_count"],
                "animations": manifest["summary"]["animation_count"],
                "errors": [],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
