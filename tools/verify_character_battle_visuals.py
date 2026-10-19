#!/usr/bin/env python3
"""Independently verify the character battle visual artifact against the ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x596D5C
CHARACTER_COUNT = 62
SLOTS_PER_CHARACTER = 9
SLOT_COUNT = 558
DESCRIPTOR_SIZE = 16
TABLE_SIZE = SLOT_COUNT * DESCRIPTOR_SIZE
TABLE_SHA256 = "baa3f86793e15d0d4abd44fcf10518da15ba0d76588b918838c3660e042e01dc"
SELECTOR_OFFSET = 0x07AE04
SELECTOR_END_OFFSET = 0x07B284
SELECTOR_SHA256 = "5a0d06474ee94f5d3fd68cfe6c90224ce5a4cc8ffbb8ceeb6c4529c67ecd1b0b"
ALLOCATOR_OFFSET = 0x0625A4
ALLOCATOR_END_OFFSET = 0x0626B0
ALLOCATOR_SHA256 = "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54"
KNOWN_ANOMALOUS_TRAILER_ADDRESS = 0x0825A8E4
FBFF_TERMINATION_RESOLUTION = {
    "evidence": "artifacts/character-fbff-runtime-v1/manifest.json",
    "raw_signed_value": -1025,
    "normalization": "fffb0000 -> ffff0000",
    "control_rom_sha256": (
        "3f55e607829db4497a1f49200514777c89df01f3624fd849005b96247502507a"
    ),
}
SEMANTICS = (
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
SIZES = {
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
EXPECTED_SUMMARY = {
    "character_count": 62,
    "slots_per_character": 9,
    "slot_count": 558,
    "populated_slot_count": 342,
    "empty_slot_count": 216,
    "resource_count": 250,
    "unique_palette_count": 48,
    "unique_palette_content_count": 40,
    "frame_count": 2004,
    "component_count": 2190,
    "animation_count": 784,
    "keyframe_count": 3187,
    "resource_tile_count": 60430,
    "logical_frame_count": 2674,
    "logical_component_count": 2860,
    "logical_animation_count": 1045,
    "logical_keyframe_count": 4246,
    "populated_slots_by_visual_slot": [62, 62, 62, 62, 62, 8, 8, 8, 8],
    "renderer_terminator_frame_count": 2003,
    "anomalous_frame_trailer_count": 1,
    "verified_static_source_space_frame_count": 2004,
    "provisional_pointer_bounded_frame_count": 0,
}
EXPECTED_SCOPE = {
    "static_source_space_frames": True,
    "pointer_bounded_source_previews": False,
    "component_geometry_and_flips": True,
    "animation_holds": True,
    "screen_space_position": False,
    "camera_and_priority": False,
    "runtime_slot_selection": False,
    "blend_and_palette_transform": False,
    "all_component_termination_semantics_complete": True,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _offset(pointer: int, size: int, rom_size: int, label: str) -> int:
    result = pointer - ROM_BASE
    if pointer < ROM_BASE or size < 0 or result < 0 or result + size > rom_size:
        raise ValueError(f"{label} is outside ROM")
    return result


def _expect(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: {actual!r} != {expected!r}")


def _read_source(
    artifact_dir: Path,
    metadata: dict[str, Any],
    *,
    expected_path: str,
    expected_pointer: int,
    expected_data: bytes,
) -> None:
    _expect(metadata["file"], expected_path, f"{expected_path} path")
    _expect(
        metadata["gba_pointer"],
        _address(expected_pointer),
        f"{expected_path} pointer",
    )
    _expect(metadata["size"], len(expected_data), f"{expected_path} size")
    expected_hash = _sha256(expected_data)
    _expect(metadata["sha256"], expected_hash, f"{expected_path} hash")
    path = artifact_dir / expected_path
    if not path.is_file():
        raise ValueError(f"{expected_path} is missing")
    _expect(path.read_bytes(), expected_data, f"{expected_path} bytes")


def _parse_component(raw: bytes, index: int) -> dict[str, Any]:
    (
        tile_index,
        orientation,
        angle,
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
    if (width, height) not in SIZES:
        raise ValueError(f"component {index} shape is invalid")
    if orientation & ~3:
        raise ValueError(f"component {index} orientation is invalid")
    if (
        angle
        or scale_x != 0x100
        or scale_y != 0x100
        or control != 0xFF
        or attribute
        or reserved
    ):
        raise ValueError(f"component {index} control fields are invalid")
    tile_offset = tile_index & 0x3FF
    return {
        "component_index": index,
        "tile_index_raw": tile_index,
        "tile_offset": tile_offset,
        "orientation": orientation,
        "horizontal_flip": bool(orientation & 1),
        "vertical_flip": bool(orientation & 2),
        "affine_angle_offset": angle,
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


def _decode_tile_block(
    graphics: bytes,
    tile_offset: int,
    width: int,
    height: int,
) -> bytes:
    tiles_wide = width // 8
    tiles_high = height // 8
    start = tile_offset * 32
    end = start + tiles_wide * tiles_high * 32
    if end > len(graphics):
        raise ValueError("component tile block exceeds graphics")
    output = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            tile = (y // 8) * tiles_wide + x // 8
            packed = graphics[
                start + tile * 32 + (y & 7) * 4 + (x & 7) // 2
            ]
            output[y * width + x] = (
                packed >> (4 if x & 1 else 0)
            ) & 15
    return bytes(output)


def _flip(
    pixels: bytes,
    width: int,
    height: int,
    horizontal: bool,
    vertical: bool,
) -> bytes:
    result = bytearray(len(pixels))
    for y in range(height):
        source_y = height - 1 - y if vertical else y
        for x in range(width):
            source_x = width - 1 - x if horizontal else x
            result[y * width + x] = pixels[source_y * width + source_x]
    return bytes(result)


def _render(components: list[dict[str, Any]], graphics: bytes) -> tuple[
    bytes,
    int,
    int,
    dict[str, int],
]:
    min_x = min(component["x"] for component in components)
    min_y = min(component["y"] for component in components)
    max_x = max(component["x"] + component["width"] for component in components)
    max_y = max(component["y"] + component["height"] for component in components)
    width = max_x - min_x
    height = max_y - min_y
    output = bytearray(width * height)
    for component in components:
        pixels = _decode_tile_block(
            graphics,
            component["tile_offset"],
            component["width"],
            component["height"],
        )
        pixels = _flip(
            pixels,
            component["width"],
            component["height"],
            component["horizontal_flip"],
            component["vertical_flip"],
        )
        dx = component["x"] - min_x
        dy = component["y"] - min_y
        for y in range(component["height"]):
            for x in range(component["width"]):
                color = pixels[y * component["width"] + x]
                if color:
                    output[(dy + y) * width + dx + x] = color
    return (
        bytes(output),
        width,
        height,
        {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
    )


def _rgb_palette(palette: bytes) -> list[int]:
    result = []
    for offset in range(0, 32, 2):
        color = struct.unpack_from("<H", palette, offset)[0] & 0x7FFF
        for shift in (0, 5, 10):
            value = (color >> shift) & 31
            result.append((value << 3) | (value >> 2))
    return result


def _verify_png(
    path: Path,
    *,
    pixels: bytes,
    width: int,
    height: int,
    palette: bytes,
) -> None:
    if not path.is_file():
        raise ValueError(f"PNG is missing: {path.name}")
    try:
        with Image.open(path) as image:
            image.load()
            _expect(image.format, "PNG", f"{path.name} format")
            _expect(image.mode, "P", f"{path.name} mode")
            _expect(image.size, (width, height), f"{path.name} size")
            _expect(image.tobytes(), pixels, f"{path.name} indexed pixels")
            actual_palette = image.getpalette()
            _expect(
                actual_palette[:48],
                _rgb_palette(palette),
                f"{path.name} palette",
            )
            _expect(
                image.info.get("transparency"),
                0,
                f"{path.name} transparency",
            )
    except (OSError, SyntaxError) as error:
        raise ValueError(f"PNG decode failed for {path.name}: {error}") from error


def _verify_resource(
    rom: bytes,
    artifact_dir: Path,
    resource: dict[str, Any],
    resource_id: int,
    descriptor: tuple[int, int, int, int],
    expected_files: set[str],
) -> dict[str, int]:
    frame_table, animation_table, graphics_pointer, palette_pointer = descriptor
    prefix = f"resource-{resource_id:03d}"
    _expect(resource["resource_id"], resource_id, f"{prefix} id")
    _expect(
        resource["descriptor"],
        {
            "frame_pointer_table": _address(frame_table),
            "animation_pointer_table": _address(animation_table),
            "graphics": _address(graphics_pointer),
            "palette": _address(palette_pointer),
        },
        f"{prefix} descriptor",
    )

    animation_offset = _offset(
        animation_table,
        4,
        len(rom),
        f"{prefix} animation table",
    )
    animation_pointers = []
    for index in range(64):
        pointer = struct.unpack_from("<I", rom, animation_offset + index * 4)[0]
        if not frame_table < pointer < animation_table:
            break
        if animation_pointers and pointer <= animation_pointers[-1]:
            raise ValueError(f"{prefix} animation pointers are not increasing")
        animation_pointers.append(pointer)
    if not animation_pointers:
        raise ValueError(f"{prefix} has no animations")

    frame_table_size = animation_pointers[0] - frame_table
    if frame_table_size <= 0 or frame_table_size % 4:
        raise ValueError(f"{prefix} frame table span is invalid")
    frame_offset = _offset(
        frame_table,
        frame_table_size,
        len(rom),
        f"{prefix} frame table",
    )
    frame_pointers = list(
        struct.unpack_from(
            f"<{frame_table_size // 4}I",
            rom,
            frame_offset,
        )
    )
    if (
        not frame_pointers
        or frame_pointers != sorted(frame_pointers)
        or len(set(frame_pointers)) != len(frame_pointers)
        or frame_pointers[-1] >= frame_table
    ):
        raise ValueError(f"{prefix} frame pointers are invalid")

    frames = []
    for frame_id, (pointer, end) in enumerate(
        zip(frame_pointers, frame_pointers[1:] + [frame_table])
    ):
        span = end - pointer
        if span < 24 or (span - 4) % 20:
            raise ValueError(f"{prefix} frame {frame_id} span is invalid")
        offset = _offset(pointer, span, len(rom), f"{prefix} frame {frame_id}")
        raw = rom[offset : offset + span]
        trailer = raw[-4:]
        if trailer not in (bytes.fromhex("ffff0000"), bytes.fromhex("fffb0000")):
            raise ValueError(f"{prefix} frame {frame_id} trailer is unknown")
        runtime_resolved_anomaly = trailer == bytes.fromhex("fffb0000")
        if (
            runtime_resolved_anomaly
            and pointer + span - 4 != KNOWN_ANOMALOUS_TRAILER_ADDRESS
        ):
            raise ValueError(
                f"{prefix} frame {frame_id} has FBFF at an unverified address"
            )
        components = [
            _parse_component(raw[index * 20 : (index + 1) * 20], index)
            for index in range((span - 4) // 20)
        ]
        frame = {
                "frame_id": frame_id,
                "component_list_pointer": _address(pointer),
                "component_count": len(components),
                "components": components,
                "raw_size": len(raw),
                "raw_sha256": _sha256(raw),
                "frame_trailer_raw_hex": trailer.hex(),
                "renderer_terminator": trailer == bytes.fromhex("ffff0000"),
                "render_complete": True,
                "interpretation": (
                    "verified_renderer_terminated"
                    if trailer == bytes.fromhex("ffff0000")
                    else "runtime_verified_single_byte_corrupt_terminator"
                ),
            }
        if runtime_resolved_anomaly:
            frame["termination_resolution"] = FBFF_TERMINATION_RESOLUTION
        frames.append(frame)

    animations = []
    for animation_id, (pointer, end) in enumerate(
        zip(animation_pointers, animation_pointers[1:] + [animation_table])
    ):
        offset = _offset(pointer, end - pointer, len(rom), "timeline")
        cursor = offset
        keyframes = []
        while cursor < offset + end - pointer:
            frame_id, hold = struct.unpack_from("<HH", rom, cursor)
            cursor += 4
            if frame_id == 0xFFFF:
                if hold:
                    raise ValueError("timeline terminator hold is nonzero")
                break
            if frame_id >= len(frames) or hold == 0:
                raise ValueError("timeline keyframe is invalid")
            keyframes.append({"frame_id": frame_id, "hold_frames": hold})
        if not keyframes or ROM_BASE + cursor != end:
            raise ValueError("timeline is empty or non-contiguous")
        raw = rom[offset:cursor]
        animations.append(
            {
                "animation_id": animation_id,
                "timeline_pointer": _address(pointer),
                "keyframe_count": len(keyframes),
                "duration_frames": sum(item["hold_frames"] for item in keyframes),
                "keyframes": keyframes,
                "terminator": {"frame_id": 0xFFFF, "hold_frames": 0},
                "raw_size": len(raw),
                "raw_sha256": _sha256(raw),
            }
        )

    component_start = frame_pointers[0]
    component_offset = _offset(
        component_start,
        frame_table - component_start,
        len(rom),
        "component region",
    )
    component_region = rom[
        component_offset : component_offset + frame_table - component_start
    ]
    frame_table_bytes = rom[frame_offset : frame_offset + frame_table_size]
    timeline_start = animation_pointers[0]
    timeline_offset = _offset(
        timeline_start,
        animation_table - timeline_start,
        len(rom),
        "timeline region",
    )
    timeline_region = rom[
        timeline_offset : timeline_offset + animation_table - timeline_start
    ]
    animation_table_bytes = rom[
        animation_offset : animation_offset + len(animation_pointers) * 4
    ]
    tile_count = max(
        component["tile_end"] for frame in frames for component in frame["components"]
    )
    graphics_offset = _offset(
        graphics_pointer,
        tile_count * 32,
        len(rom),
        "graphics",
    )
    graphics = rom[graphics_offset : graphics_offset + tile_count * 32]
    if graphics_pointer + len(graphics) != frame_pointers[0]:
        raise ValueError(f"{prefix} graphics do not meet first frame")
    palette_offset = _offset(palette_pointer, 32, len(rom), "palette")
    palette = rom[palette_offset : palette_offset + 32]

    source_specs = (
        ("component_region", "component-region.bin", component_start, component_region),
        ("frame_pointer_table", "frame-pointer-table.bin", frame_table, frame_table_bytes),
        ("timeline_region", "timeline-region.bin", timeline_start, timeline_region),
        (
            "animation_pointer_table",
            "animation-pointer-table.bin",
            animation_table,
            animation_table_bytes,
        ),
        ("graphics", "graphics-4bpp.bin", graphics_pointer, graphics),
        ("palette", "palette-bgr555.bin", palette_pointer, palette),
    )
    for key, filename, pointer, data in source_specs:
        relative = f"{prefix}/{filename}"
        expected_files.add(relative)
        _read_source(
            artifact_dir,
            resource[key],
            expected_path=relative,
            expected_pointer=pointer,
            expected_data=data,
        )
    _expect(resource["graphics"]["tile_count"], tile_count, f"{prefix} tile count")
    _expect(resource["palette"]["color_count"], 16, f"{prefix} palette colors")

    _expect(resource["frame_count"], len(frames), f"{prefix} frame count")
    _expect(
        resource["component_count"],
        sum(frame["component_count"] for frame in frames),
        f"{prefix} component count",
    )
    _expect(resource["animation_count"], len(animations), f"{prefix} animation count")
    _expect(
        resource["keyframe_count"],
        sum(animation["keyframe_count"] for animation in animations),
        f"{prefix} keyframe count",
    )
    _expect(resource["animations"], animations, f"{prefix} animations")
    _expect(len(resource["frames"]), len(frames), f"{prefix} manifest frames")

    for expected, actual in zip(frames, resource["frames"]):
        _expect(
            set(actual),
            set(expected)
            | {
                "width",
                "height",
                "component_local_bounds",
                "pixel_sha256",
                "png_sha256",
                "rendering_scope",
                "png",
            },
            f"{prefix} frame schema",
        )
        for key, value in expected.items():
            _expect(actual[key], value, f"{prefix} frame {expected['frame_id']} {key}")
        pixels, width, height, bounds = _render(expected["components"], graphics)
        _expect(actual["width"], width, f"{prefix} frame width")
        _expect(actual["height"], height, f"{prefix} frame height")
        _expect(actual["component_local_bounds"], bounds, f"{prefix} frame bounds")
        _expect(actual["pixel_sha256"], _sha256(pixels), f"{prefix} pixel hash")
        _expect(
            actual["rendering_scope"],
            (
                "source-space component order with H/V flips; runtime screen "
                "position, camera, priority and affine transforms are not applied"
            ),
            f"{prefix} rendering scope",
        )
        png_relative = f"{prefix}/frame-{expected['frame_id']:03d}.png"
        _expect(actual["png"], png_relative, f"{prefix} PNG path")
        png_path = artifact_dir / png_relative
        expected_files.add(png_relative)
        _verify_png(
            png_path,
            pixels=pixels,
            width=width,
            height=height,
            palette=palette,
        )
        _expect(
            actual["png_sha256"],
            _sha256(png_path.read_bytes()),
            f"{prefix} PNG hash",
        )

    return {
        "frames": len(frames),
        "components": sum(frame["component_count"] for frame in frames),
        "animations": len(animations),
        "keyframes": sum(animation["keyframe_count"] for animation in animations),
        "tiles": tile_count,
        "renderer_terminators": sum(frame["renderer_terminator"] for frame in frames),
        "anomalies": sum(not frame["renderer_terminator"] for frame in frames),
    }


def _verify(root: Path, artifact_dir: Path) -> dict[str, int]:
    rom = (root / "rom" / "base.gba").read_bytes()
    _expect(_sha256(rom), ROM_SHA256, "ROM SHA-256")
    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _expect(manifest["schema"], "character-battle-visuals-v1", "schema")
    _expect(
        manifest["rom"],
        {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "manifest ROM identity",
    )
    table = rom[TABLE_OFFSET : TABLE_OFFSET + TABLE_SIZE]
    _expect(_sha256(table), TABLE_SHA256, "table SHA-256")
    _expect(
        manifest["table"],
        {
            "gba_start": "0x08596D5C",
            "gba_end": "0x0859903C",
            "file_offset": TABLE_OFFSET,
            "entry_size": DESCRIPTOR_SIZE,
            "entry_count": SLOT_COUNT,
            "sha256": TABLE_SHA256,
            "row_formula": "(character_id - 1) * 9 + visual_slot",
        },
        "manifest table identity",
    )
    selector = rom[SELECTOR_OFFSET:SELECTOR_END_OFFSET]
    allocator = rom[ALLOCATOR_OFFSET:ALLOCATOR_END_OFFSET]
    _expect(_sha256(selector), SELECTOR_SHA256, "selector code SHA-256")
    _expect(_sha256(allocator), ALLOCATOR_SHA256, "allocator code SHA-256")
    _expect(
        manifest["consumer"],
        {
            "prebiased_matrix_base": "0x08596CCC",
            "descriptor_formula": (
                "0x08596CCC + character_id * 0x90 + visual_slot * 0x10"
            ),
            "selector": {
                "gba_start": "0x0807AE04",
                "gba_end": "0x0807B284",
                "size": len(selector),
                "sha256": SELECTOR_SHA256,
                "opcode_domain": list(range(8)),
            },
            "sprite_task_allocator": {
                "gba_start": "0x080625A4",
                "gba_end": "0x080626B0",
                "size": len(allocator),
                "sha256": ALLOCATOR_SHA256,
            },
            "left_facing_empty_slot_fallback": {
                "from_slots": [5, 6, 7, 8],
                "to_slots": [1, 2, 3, 4],
                "horizontal_flip_flag": "0x8000",
            },
        },
        "consumer binding",
    )
    _expect(
        manifest["slot_semantics"],
        [
            {
                "visual_slot": index,
                "name": name,
                "name_basis": (
                    "existing project vocabulary; selector opcode mapping is "
                    "authoritative, natural-scene business naming remains scoped"
                ),
                **SLOT_SELECTOR_ROLES[index],
            }
            for index, name in enumerate(SEMANTICS)
        ],
        "slot semantics",
    )
    _expect(manifest["summary"], EXPECTED_SUMMARY, "summary")
    _expect(manifest["scope"], EXPECTED_SCOPE, "artifact scope")

    rows = [
        struct.unpack_from("<4I", table, row * DESCRIPTOR_SIZE)
        for row in range(SLOT_COUNT)
    ]
    descriptor_to_id: dict[tuple[int, int, int, int], int] = {}
    descriptors = []
    expected_slots = []
    for row, descriptor in enumerate(rows):
        populated = descriptor != (0, 0, 0, 0)
        if populated and any(value == 0 for value in descriptor):
            raise ValueError(f"row {row} is partially populated")
        resource_id = None
        if populated:
            resource_id = descriptor_to_id.get(descriptor)
            if resource_id is None:
                resource_id = len(descriptors)
                descriptor_to_id[descriptor] = resource_id
                descriptors.append(descriptor)
        expected_slots.append(
            {
                "row": row,
                "character_id": row // 9 + 1,
                "visual_slot": row % 9,
                "semantic": SEMANTICS[row % 9],
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
    _expect(manifest["slots"], expected_slots, "logical slot matrix")
    _expect(len(manifest["resources"]), len(descriptors), "resource count")

    expected_files = {"manifest.json"}
    totals = {
        "frames": 0,
        "components": 0,
        "animations": 0,
        "keyframes": 0,
        "tiles": 0,
        "renderer_terminators": 0,
        "anomalies": 0,
    }
    for resource_id, descriptor in enumerate(descriptors):
        resource = manifest["resources"][resource_id]
        expected_rows = [
            row
            for row, expected in enumerate(expected_slots)
            if expected["resource_id"] == resource_id
        ]
        _expect(resource["slot_rows"], expected_rows, "resource slot aliases")
        result = _verify_resource(
            rom,
            artifact_dir,
            resource,
            resource_id,
            descriptor,
            expected_files,
        )
        for key, value in result.items():
            totals[key] += value

    _expect(totals["frames"], 2004, "verified frame total")
    _expect(totals["components"], 2190, "verified component total")
    _expect(totals["animations"], 784, "verified animation total")
    _expect(totals["keyframes"], 3187, "verified keyframe total")
    _expect(totals["tiles"], 60430, "verified tile total")
    _expect(totals["renderer_terminators"], 2003, "renderer terminator total")
    _expect(totals["anomalies"], 1, "anomalous trailer total")
    actual_files = {
        path.relative_to(artifact_dir).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file()
    }
    _expect(actual_files, expected_files, "artifact file set")
    return {**totals, "slots": SLOT_COUNT, "resources": len(descriptors)}


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors = []
    totals = {
        "slots": 0,
        "resources": 0,
        "frames": 0,
        "components": 0,
        "animations": 0,
        "keyframes": 0,
        "tiles": 0,
    }
    try:
        totals.update(_verify(root.resolve(), artifact_dir.resolve()))
    except (
        IndexError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        struct.error,
        json.JSONDecodeError,
    ) as error:
        errors.append(str(error))
    return {
        "verified": not errors,
        **{
            key: totals[key]
            for key in (
                "slots",
                "resources",
                "frames",
                "components",
                "animations",
                "keyframes",
                "tiles",
            )
        },
        "expected_slots": SLOT_COUNT,
        "expected_resources": EXPECTED_SUMMARY["resource_count"],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the character battle visual artifact"
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/character-battle-visuals-v1"),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    artifact_dir = (
        args.artifact_dir
        if args.artifact_dir.is_absolute()
        else root / args.artifact_dir
    )
    report = verify_artifact(root, artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
