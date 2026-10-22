#!/usr/bin/env python3
"""Independently verify the Cutscene OBJ relocation artifact."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
import sys
from collections import deque
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ARTIFACT_ID = "cutscene-obj-bundle-relocation-v1"
PAYLOAD_SCHEMA = "cutscene-obj-bundle-relocation-audit-v1"
PAYLOAD_NAME = "relocation-audit.json"
SPEC_NAME = "full-relocation-spec.json"
RAW_NAMES = tuple(
    name
    for resource_id in range(4)
    for name in (
        f"resource_{resource_id}.4bpp.bin",
        f"resource_{resource_id}.bgr555.bin",
    )
)
ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/cutscene-obj-v1/manifest.json")
CATALOG_SHA256 = (
    "b8e1341172decef9f07080879cd8369bc5308274d84383d5c706de72a0b781e7"
)
REGISTRY_PATH = Path("sequel/image-resource-regions.json")
RESOURCE_TABLE_OFFSET = 0x53DF70
SPRITE_TABLE_OFFSET = 0x53DF90
ENTRY_COUNT = 4
ENTRY_SIZE = 8
FRAME_COUNTS = (2, 2, 2, 4)
TERMINATOR = bytes.fromhex("ffff0000")
RUNTIME_TILE_BASE = 0x300
MAX_GRAPHICS_TILES = 256
MAX_COMPONENTS = 2
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
LOADER_TARGET = 0x08072EDC
LOADER_CALLS = {
    0x08073100: (1, "0120fff7ecfe"),
    0x0807314A: (2, "0220fff7c7fe"),
    0x08073196: (3, "0320fff7a1fe"),
    0x0807363A: (0, "0020fff74ffc"),
}
CONSUMER_RANGES = {
    "natural_loader": (
        0x08072EDC,
        0x08072FFE,
        "1b7427dd2ad35bb7b439de5f9f1fc6ce1e82a073d547e06eacbf8ba34e11073f",
    ),
    "sprite_task_allocator": (
        0x080625A4,
        0x080626B0,
        "e238cd1ee159265fb8b718766f336f8d5462596954f93c7805d1bf33dd6b3c54",
    ),
    "animation_frame_selector": (
        0x0806298C,
        0x080629A0,
        "62718fbb246078256e2c3344773d0ab9a0b2c10aee2fb3890d16e134b331e1ab",
    ),
    "animation_timing_consumer": (
        0x08063256,
        0x080632D8,
        "1ec4801f36351e56d511caaa6cc5fdf31d52142292e64d3c9cf6567eed468be0",
    ),
}
EXPECTED_SCOPE = {
    "proved": (
        "All four fixed Cutscene OBJ IDs, 10 source frames/components, "
        "10 source animations/keyframes and all 36 exact source pointer "
        "references are accounted for; 12 allocations and 16 root pointer "
        "patches rebuild a 16 MiB ROM."
    ),
    "editable": (
        "Each fixed ID may use 1..256 complete 4bpp tiles and one 16-color "
        "palette. The fixed 2/2/2/4 frame and animation slots each support "
        "1..2 valid GBA OBJ components and a non-empty variable keyframe "
        "timeline with u16 durations."
    ),
    "not_proved": (
        "Adding a fifth ID, changing the fixed frame/animation slot counts, "
        "more than two simultaneous components per frame, caller-level scene "
        "cleanup, or final screen-composited pixel/timing equivalence after "
        "modification."
    ),
}
IMPLEMENTATION_PATHS = (
    "tools/export_cutscene_obj_assets.py",
    "tools/verify_cutscene_obj_export.py",
    "tools/import_cutscene_obj_bundle_relocations.py",
    "tools/gba_image_export.py",
    "tools/image_resource_regions.py",
    "tools/rom_layout.py",
    "tools/patch_safety.py",
    "tools/build_mod.py",
    "tools/export_cutscene_obj_bundle_relocation_audit.py",
    "tools/verify_cutscene_obj_bundle_relocation_audit.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _decode_lz77(rom: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError("invalid LZ77 header")
    size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < size:
        if cursor >= len(rom):
            raise ValueError("truncated LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated LZ77 backreference")
                token = int.from_bytes(rom[cursor : cursor + 2], "big")
                cursor += 2
                length = (token >> 12) + 3
                distance = (token & 0xFFF) + 1
                if distance > len(output):
                    raise ValueError("invalid LZ77 distance")
                for _ in range(length):
                    if len(output) >= size:
                        break
                    output.append(output[-distance])
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated LZ77 literal")
                output.append(rom[cursor])
                cursor += 1
    return bytes(output)


def _encode_lz77(data: bytes) -> bytes:
    output = bytearray(
        (0x10, len(data) & 0xFF, (len(data) >> 8) & 0xFF, len(data) >> 16)
    )
    positions: dict[bytes, deque[int]] = {}
    cursor = 0
    while cursor < len(data):
        flag_offset = len(output)
        output.append(0)
        flags = 0
        for token in range(8):
            if cursor >= len(data):
                break
            best_length = 0
            best_distance = 0
            if cursor + 3 <= len(data):
                key = data[cursor : cursor + 3]
                for previous in reversed(positions.get(key, ())):
                    distance = cursor - previous
                    if distance > 0x1000:
                        break
                    if distance == 1:
                        continue
                    length = 3
                    while (
                        length < 18
                        and cursor + length < len(data)
                        and data[previous + length] == data[cursor + length]
                    ):
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = distance
                    if length == 18:
                        break
            if best_length >= 3:
                flags |= 1 << (7 - token)
                encoded = ((best_length - 3) << 12) | (best_distance - 1)
                output.extend((encoded >> 8, encoded & 0xFF))
                advance = best_length
            else:
                output.append(data[cursor])
                advance = 1
            for position in range(cursor, cursor + advance):
                if position + 3 > len(data):
                    continue
                key = data[position : position + 3]
                bucket = positions.setdefault(key, deque())
                bucket.append(position)
                while bucket and position - bucket[0] > 0x1000:
                    bucket.popleft()
            cursor += advance
        output[flag_offset] = flags
    return bytes(output)


def _thumb_bl_calls(rom: bytes, target: int) -> set[int]:
    calls = set()
    for offset in range(0, len(rom) - 3, 2):
        first, second = struct.unpack_from("<HH", rom, offset)
        if first & 0xF800 != 0xF000 or second & 0xF800 != 0xF800:
            continue
        displacement = ((first & 0x07FF) << 12) | (
            (second & 0x07FF) << 1
        )
        if first & 0x0400:
            displacement -= 1 << 23
        if ROM_BASE + offset + 4 + displacement == target:
            calls.add(ROM_BASE + offset)
    return calls


def _asset_path(root: Path, artifact: Path, name: str) -> str:
    path = artifact / name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _source(
    root: Path,
    artifact: Path,
    base: bytes,
) -> tuple[dict[str, Any], dict[str, bytes], int]:
    if _thumb_bl_calls(base, LOADER_TARGET) != set(LOADER_CALLS):
        raise ValueError("independent Cutscene OBJ loader denominator mismatch")
    for address, (_, expected_hex) in LOADER_CALLS.items():
        offset = address - ROM_BASE
        if base[offset - 2 : offset + 4].hex() != expected_hex:
            raise ValueError("independent Cutscene OBJ caller mismatch")
    for name, (start, end, digest) in CONSUMER_RANGES.items():
        if _sha256(base[start - ROM_BASE : end - ROM_BASE]) != digest:
            raise ValueError(
                f"independent Cutscene OBJ consumer changed: {name}"
            )
    for offset, expected in (
        (0x72F3C, ROM_BASE + RESOURCE_TABLE_OFFSET),
        (0x72F40, 0x06016000),
        (0x72F44, 0x05000380),
        (0x72FC8, ROM_BASE + SPRITE_TABLE_OFFSET),
    ):
        if struct.unpack_from("<I", base, offset)[0] != expected:
            raise ValueError("independent Cutscene OBJ literal mismatch")
    if base[0x72F7A:0x72F80].hex() != "c02080000190":
        raise ValueError("independent Cutscene OBJ tile base mismatch")
    if _sha256_file(root / CATALOG_PATH) != CATALOG_SHA256:
        raise ValueError("independent Cutscene OBJ catalog hash mismatch")
    catalog = _json(root / CATALOG_PATH)
    if (
        catalog.get("schema") != "cutscene-obj-export-v1"
        or catalog.get("resource_count") != ENTRY_COUNT
        or catalog.get("frame_counts") != list(FRAME_COUNTS)
        or len(catalog.get("resources", [])) != ENTRY_COUNT
    ):
        raise ValueError("independent Cutscene OBJ catalog mismatch")

    for pointer, expected_offset in (
        (ROM_BASE + RESOURCE_TABLE_OFFSET, 0x72F3C),
        (ROM_BASE + SPRITE_TABLE_OFFSET, 0x72FC8),
    ):
        hits = {
            offset
            for offset in range(0, len(base) - 3, 4)
            if struct.unpack_from("<I", base, offset)[0] == pointer
        }
        if hits != {expected_offset}:
            raise ValueError("independent table-base reference mismatch")

    expected: dict[int, set[int]] = {}
    raw_assets = {}
    resources = []

    def expect(pointer: int, offset: int) -> None:
        expected.setdefault(pointer, set()).add(offset)

    for resource_id, row in enumerate(catalog["resources"]):
        if (
            row.get("resource_id") != resource_id
            or row.get("frame_count") != FRAME_COUNTS[resource_id]
        ):
            raise ValueError("independent Cutscene OBJ resource mismatch")
        resource_pair = RESOURCE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        sprite_pair = SPRITE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        graphics_pointer, palette_pointer = struct.unpack_from(
            "<II", base, resource_pair
        )
        definition_pointer, animation_pointer = struct.unpack_from(
            "<II", base, sprite_pair
        )
        for key, pointer in (
            ("gfx_pointer", graphics_pointer),
            ("palette_pointer", palette_pointer),
            ("definition_table_pointer", definition_pointer),
            ("animation_table_pointer", animation_pointer),
        ):
            if int(row.get(key, "0"), 16) != pointer:
                raise ValueError("independent source pointer metadata mismatch")
        graphics = _decode_lz77(base, graphics_pointer - ROM_BASE)
        palette = _decode_lz77(base, palette_pointer - ROM_BASE)
        if (
            not graphics
            or len(graphics) % 32
            or len(graphics) // 32 > MAX_GRAPHICS_TILES
            or len(palette) != 32
        ):
            raise ValueError("independent source payload mismatch")
        graphics_name = f"resource_{resource_id}.4bpp.bin"
        palette_name = f"resource_{resource_id}.bgr555.bin"
        raw_assets[graphics_name] = graphics
        raw_assets[palette_name] = palette
        expect(graphics_pointer, resource_pair)
        expect(palette_pointer, resource_pair + 4)
        expect(definition_pointer, sprite_pair)
        expect(animation_pointer, sprite_pair + 4)
        definition_offset = definition_pointer - ROM_BASE
        animation_offset = animation_pointer - ROM_BASE
        frames = []
        animations = []
        if len(row.get("frames", [])) != FRAME_COUNTS[resource_id]:
            raise ValueError("independent source frame count mismatch")
        for frame_id, frame in enumerate(row["frames"]):
            component_pointer = struct.unpack_from(
                "<I", base, definition_offset + frame_id * 4
            )[0]
            sequence_pointer = struct.unpack_from(
                "<I", base, animation_offset + frame_id * 4
            )[0]
            component_raw = base[
                component_pointer - ROM_BASE : component_pointer - ROM_BASE + 24
            ]
            sequence_raw = base[
                sequence_pointer - ROM_BASE : sequence_pointer - ROM_BASE + 8
            ]
            if (
                frame.get("frame_id") != frame_id
                or int(frame.get("definition_pointer", "0"), 16)
                != component_pointer
                or int(frame.get("animation_pointer", "0"), 16)
                != sequence_pointer
                or frame.get("definition_raw_hex") != component_raw.hex()
                or frame.get("animation_raw_hex") != sequence_raw.hex()
                or component_raw[20:] != TERMINATOR
                or sequence_raw[4:] != TERMINATOR
            ):
                raise ValueError("independent source record mismatch")
            (
                tile_offset,
                x_offset,
                y_offset,
                width,
                height,
                transform_x,
                transform_y,
                unknown_10,
                unknown_12,
            ) = struct.unpack("<IhhHHHHHH", component_raw[:20])
            if (
                (transform_x, transform_y, unknown_10, unknown_12)
                != (0x100, 0x100, 0xFF, 0)
                or (width, height) not in SUPPORTED_SIZES
                or tile_offset + width * height // 64 > len(graphics) // 32
            ):
                raise ValueError("independent source component mismatch")
            keyframe = struct.unpack("<HH", sequence_raw[:4])
            frames.append(
                {
                    "id": frame_id,
                    "components": [
                        {
                            "tile_offset": tile_offset,
                            "x_offset": x_offset,
                            "y_offset": y_offset,
                            "width": width,
                            "height": height,
                        }
                    ],
                }
            )
            animations.append(
                {
                    "id": frame_id,
                    "keyframes": [
                        {
                            "frame_id": keyframe[0],
                            "duration_ticks": keyframe[1],
                        }
                    ],
                }
            )
            expect(component_pointer, definition_offset + frame_id * 4)
            expect(sequence_pointer, animation_offset + frame_id * 4)
        resources.append(
            {
                "id": resource_id,
                "graphics_file": _asset_path(
                    root, artifact, graphics_name
                ),
                "palette_file": _asset_path(root, artifact, palette_name),
                "frames": frames,
                "animations": animations,
            }
        )

    actual = {pointer: set() for pointer in expected}
    for offset in range(0, len(base) - 3, 4):
        value = struct.unpack_from("<I", base, offset)[0]
        if value in actual:
            actual[value].add(offset)
    if any(actual[pointer] != offsets for pointer, offsets in expected.items()):
        raise ValueError("independent Cutscene OBJ pointer inventory mismatch")
    spec = {
        "schema": "cutscene-obj-bundle-relocation-v1",
        "base_rom_sha256": _sha256(base),
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": _sha256_file(root / CATALOG_PATH),
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGISTRY_PATH.as_posix(),
        "region_registry_sha256": _sha256_file(root / REGISTRY_PATH),
        "region": "cutscene-obj-bundle",
        "region_owner": "cutscene_obj_resources",
        "resources": resources,
    }
    return spec, raw_assets, sum(len(offsets) for offsets in expected.values())


def _encode_component(
    component: dict[str, Any],
    graphics_tiles: int,
) -> bytes:
    required = {"tile_offset", "x_offset", "y_offset", "width", "height"}
    if set(component) != required:
        raise ValueError("independent component fields mismatch")
    values = [component[key] for key in required]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise ValueError("independent component value mismatch")
    tile_offset = component["tile_offset"]
    x = component["x_offset"]
    y = component["y_offset"]
    width = component["width"]
    height = component["height"]
    if (
        not 0 <= tile_offset < MAX_GRAPHICS_TILES
        or not -0x8000 <= x <= 0x7FFF
        or not -0x8000 <= y <= 0x7FFF
        or (width, height) not in SUPPORTED_SIZES
        or tile_offset + width * height // 64 > graphics_tiles
    ):
        raise ValueError("independent component range mismatch")
    return struct.pack(
        "<IhhHHHHHH",
        tile_offset,
        x,
        y,
        width,
        height,
        0x100,
        0x100,
        0xFF,
        0,
    )


def _build(
    spec: dict[str, Any],
    load_file: Callable[[str], bytes],
    base: bytes,
    layout: RomLayout,
    region_start: int,
    region_end: int,
) -> tuple[bytes, list[dict[str, Any]], int]:
    resources = spec.get("resources")
    if (
        not isinstance(resources, list)
        or [row.get("id") for row in resources] != list(range(ENTRY_COUNT))
    ):
        raise ValueError("independent authored ID mismatch")
    encoded = []
    for resource_id, resource in enumerate(resources):
        graphics = load_file(resource["graphics_file"])
        palette = load_file(resource["palette_file"])
        if (
            not graphics
            or len(graphics) % 32
            or not 1 <= len(graphics) // 32 <= MAX_GRAPHICS_TILES
            or len(palette) != 32
        ):
            raise ValueError("independent authored payload mismatch")
        count = FRAME_COUNTS[resource_id]
        frames = resource.get("frames")
        animations = resource.get("animations")
        if (
            not isinstance(frames, list)
            or not isinstance(animations, list)
            or [row.get("id") for row in frames] != list(range(count))
            or [row.get("id") for row in animations] != list(range(count))
        ):
            raise ValueError("independent authored fixed count mismatch")
        component_lists = []
        component_counts = []
        for frame in frames:
            components = frame.get("components")
            if (
                not isinstance(components, list)
                or not 1 <= len(components) <= MAX_COMPONENTS
            ):
                raise ValueError("independent component count mismatch")
            component_lists.append(
                b"".join(
                    _encode_component(component, len(graphics) // 32)
                    for component in components
                )
                + TERMINATOR
            )
            component_counts.append(len(components))
        sequences = []
        keyframe_counts = []
        for animation in animations:
            keyframes = animation.get("keyframes")
            if not isinstance(keyframes, list) or not keyframes:
                raise ValueError("independent keyframe count mismatch")
            sequence = bytearray()
            for keyframe in keyframes:
                if (
                    not isinstance(keyframe, dict)
                    or set(keyframe) != {"frame_id", "duration_ticks"}
                    or isinstance(keyframe["frame_id"], bool)
                    or not isinstance(keyframe["frame_id"], int)
                    or not 0 <= keyframe["frame_id"] < count
                    or isinstance(keyframe["duration_ticks"], bool)
                    or not isinstance(keyframe["duration_ticks"], int)
                    or not 0 <= keyframe["duration_ticks"] <= 0xFFFF
                ):
                    raise ValueError("independent keyframe value mismatch")
                sequence.extend(
                    struct.pack(
                        "<HH",
                        keyframe["frame_id"],
                        keyframe["duration_ticks"],
                    )
                )
            sequences.append(bytes(sequence) + TERMINATOR)
            keyframe_counts.append(len(keyframes))
        encoded.append(
            {
                "id": resource_id,
                "graphics": graphics,
                "palette": palette,
                "component_lists": component_lists,
                "component_counts": component_counts,
                "sequences": sequences,
                "keyframe_counts": keyframe_counts,
            }
        )

    output = bytearray(layout.expanded_base())
    cursor = region_start
    allocations = []

    def allocate(
        data: bytes,
        resource_type: str,
        **metadata: object,
    ) -> int:
        nonlocal cursor
        cursor = (cursor + 3) & ~3
        offset = cursor
        cursor += len(data)
        if cursor > region_end:
            raise ValueError("independent allocation exceeds region")
        if output[offset:cursor] != b"\xFF" * len(data):
            raise ValueError("independent allocation base is not empty")
        output[offset:cursor] = data
        allocations.append(
            {
                "id": f"cutscene-obj-{resource_type}-{offset:06x}",
                "resource_type": resource_type,
                "offset": offset,
                **metadata,
            }
        )
        return offset

    relocated = []
    for resource in encoded:
        resource_id = resource["id"]
        graphics_encoded = _encode_lz77(resource["graphics"])
        palette_encoded = _encode_lz77(resource["palette"])
        graphics_offset = allocate(
            graphics_encoded,
            "graphics",
            resource_id=resource_id,
            decompressed_size=len(resource["graphics"]),
            encoded_size=len(graphics_encoded),
            replacement_sha256=_sha256(resource["graphics"]),
            tile_count=len(resource["graphics"]) // 32,
        )
        palette_offset = allocate(
            palette_encoded,
            "palette",
            resource_id=resource_id,
            decompressed_size=len(resource["palette"]),
            encoded_size=len(palette_encoded),
            replacement_sha256=_sha256(resource["palette"]),
        )
        cursor = (cursor + 3) & ~3
        bundle_offset = cursor
        body = bytearray()
        component_pointers = []
        for component_list in resource["component_lists"]:
            component_pointers.append(ROM_BASE + bundle_offset + len(body))
            body.extend(component_list)
        sequence_pointers = []
        for sequence in resource["sequences"]:
            sequence_pointers.append(ROM_BASE + bundle_offset + len(body))
            body.extend(sequence)
        definition_pointer = ROM_BASE + bundle_offset + len(body)
        for pointer in component_pointers:
            body.extend(struct.pack("<I", pointer))
        animation_pointer = ROM_BASE + bundle_offset + len(body)
        for pointer in sequence_pointers:
            body.extend(struct.pack("<I", pointer))
        allocated = allocate(
            bytes(body),
            "resource_bundle",
            resource_id=resource_id,
            frame_count=FRAME_COUNTS[resource_id],
            animation_count=FRAME_COUNTS[resource_id],
            component_counts=resource["component_counts"],
            keyframe_counts=resource["keyframe_counts"],
            definition_table_pointer=definition_pointer,
            animation_table_pointer=animation_pointer,
            component_pointers=component_pointers,
            sequence_pointers=sequence_pointers,
        )
        if allocated != bundle_offset:
            raise ValueError("independent bundle alignment drift")
        relocated.append(
            (
                ROM_BASE + graphics_offset,
                ROM_BASE + palette_offset,
                definition_pointer,
                animation_pointer,
            )
        )
    for resource_id, pointers in enumerate(relocated):
        resource_pair = RESOURCE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        sprite_pair = SPRITE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        for offset, pointer in zip(
            (resource_pair, resource_pair + 4, sprite_pair, sprite_pair + 4),
            pointers,
            strict=True,
        ):
            output[offset : offset + 4] = struct.pack("<I", pointer)
    return bytes(output), allocations, cursor


def verify_audit(root: Path, artifact: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact = Path(artifact)
    if not artifact.is_absolute():
        artifact = root / artifact
    errors = []
    rebuilt_hash = ""
    fixture_hash = ""
    verified_resources = 0
    verified_source_pointers = 0
    fixture_tiles = 0
    fixture_components = 0
    fixture_keyframes = 0
    try:
        actual_files = {
            path.name for path in artifact.iterdir() if path.is_file()
        }
        expected_files = {"manifest.json", SPEC_NAME, PAYLOAD_NAME, *RAW_NAMES}
        if actual_files != expected_files:
            raise ValueError("artifact file set mismatch")
        manifest = _json(artifact / "manifest.json")
        payload = _json(artifact / PAYLOAD_NAME)
        spec = _json(artifact / SPEC_NAME)
        promoted = (SPEC_NAME, PAYLOAD_NAME, *RAW_NAMES)
        file_hashes = {
            name: _sha256_file(artifact / name) for name in promoted
        }
        if manifest != {
            "schema": "git-artifact-promotion-v1",
            "artifact_id": ARTIFACT_ID,
            "artifact_schema": PAYLOAD_SCHEMA,
            "artifact_status": "accepted",
            "payload_file": PAYLOAD_NAME,
            "payload_sha256": file_hashes[PAYLOAD_NAME],
            "files": file_hashes,
            "scope": EXPECTED_SCOPE,
            "summary": payload.get("summary"),
            "verifier": {
                "command": [
                    "python3",
                    "tools/verify_cutscene_obj_bundle_relocation_audit.py",
                    "--root",
                    ".",
                    "--artifact",
                    f"artifacts/{ARTIFACT_ID}",
                ],
                "exit_code": 0,
            },
        }:
            raise ValueError("promotion manifest mismatch")
        base = (root / "rom/base.gba").read_bytes()
        if _sha256(base) != ROM_SHA256:
            raise ValueError("base ROM mismatch")
        layout_path = root / "sequel/rom-layout.json"
        layout = RomLayout.from_path(layout_path, base)
        registry_path = root / REGISTRY_PATH
        regions = ImageResourceRegions.from_path(registry_path, layout)
        region = regions.require(
            "cutscene-obj-bundle",
            "cutscene_obj_resources",
        )
        expected_spec, raw_assets, source_pointer_count = _source(
            root,
            artifact,
            base,
        )
        verified_resources = ENTRY_COUNT
        verified_source_pointers = source_pointer_count
        if spec != expected_spec:
            raise ValueError("authoring spec does not match source ROM")
        for name, expected in raw_assets.items():
            if (artifact / name).read_bytes() != expected:
                raise ValueError(f"raw asset mismatch: {name}")

        def load_file(value: str) -> bytes:
            path = Path(value)
            path = path if path.is_absolute() else root / path
            return path.read_bytes()

        rebuilt, allocations, allocation_end = _build(
            spec,
            load_file,
            base,
            layout,
            region.start,
            region.end,
        )
        rebuilt_hash = _sha256(rebuilt)
        summary = {
            "resource_count": 4,
            "frame_count": 10,
            "component_count": 10,
            "animation_count": 10,
            "keyframe_count": 10,
            "frame_counts": [2, 2, 2, 4],
            "runtime_tile_base": RUNTIME_TILE_BASE,
            "maximum_safe_graphics_tiles": MAX_GRAPHICS_TILES,
            "runtime_loader_call_count": len(LOADER_CALLS),
            "source_pointer_reference_count": source_pointer_count,
            "unexpected_source_pointer_count": 0,
            "allocation_count": len(allocations),
            "pointer_patch_count": 16,
            "allocation_start": region.start,
            "allocation_end": allocation_end,
            "region_end": region.end,
            "stored_payload_bytes": 0,
            "allocation_span": allocation_end - region.start,
            "remaining_bytes": region.end - allocation_end,
            "applied_patch_count": len(allocations) + 16,
        }
        # Stored bytes are derived directly from deterministic payload lengths.
        stored_bytes = 0
        for resource in spec["resources"]:
            graphics = load_file(resource["graphics_file"])
            palette = load_file(resource["palette_file"])
            stored_bytes += len(_encode_lz77(graphics))
            stored_bytes += len(_encode_lz77(palette))
            stored_bytes += sum(
                len(frame["components"]) * 20 + 4
                for frame in resource["frames"]
            )
            stored_bytes += sum(
                len(animation["keyframes"]) * 4 + 4
                for animation in resource["animations"]
            )
            stored_bytes += 8 * len(resource["frames"])
        summary["stored_payload_bytes"] = stored_bytes
        expected_allocation_rows = allocations
        if (
            payload.get("schema") != PAYLOAD_SCHEMA
            or payload.get("base_rom")
            != {
                "path": "rom/base.gba",
                "size": len(base),
                "sha256": _sha256(base),
            }
            or payload.get("layout")
            != {
                "path": "sequel/rom-layout.json",
                "sha256": _sha256_file(layout_path),
                "target_rom_size": layout.target_rom_size,
                "partition": regions.parent.id,
                "owner": regions.parent.owner,
            }
            or payload.get("region_registry")
            != {
                "path": REGISTRY_PATH.as_posix(),
                "sha256": _sha256_file(registry_path),
                "region": region.id,
                "owner": region.owner,
                "start": region.start,
                "end": region.end,
            }
            or payload.get("catalog")
            != {
                "path": CATALOG_PATH.as_posix(),
                "sha256": _sha256_file(root / CATALOG_PATH),
            }
            or payload.get("authoring_spec")
            != {
                "file": SPEC_NAME,
                "sha256": _sha256_file(artifact / SPEC_NAME),
            }
            or payload.get("implementation")
            != {
                path: _sha256_file(root / path)
                for path in IMPLEMENTATION_PATHS
            }
            or payload.get("summary") != summary
            or payload.get("allocations") != expected_allocation_rows
            or payload.get("raw_assets")
            != {
                name: _sha256(raw_assets[name]) for name in RAW_NAMES
            }
            or payload.get("output_rom_sha256") != rebuilt_hash
            or payload.get("scope") != EXPECTED_SCOPE
        ):
            raise ValueError("audit payload mismatch")

        fixture_spec = copy.deepcopy(spec)
        original = raw_assets["resource_0.4bpp.bin"]
        extension = bytes(
            (index * 73 + 19) & 0xFF
            for index in range(
                (MAX_GRAPHICS_TILES - len(original) // 32) * 32
            )
        )
        fixture_graphics = original + extension
        added = dict(
            fixture_spec["resources"][0]["frames"][0]["components"][0]
        )
        added["tile_offset"] = 192
        added["x_offset"] = 32
        fixture_spec["resources"][0]["frames"][0]["components"].append(added)
        fixture_spec["resources"][0]["animations"][0]["keyframes"].append(
            {"frame_id": 1, "duration_ticks": 3}
        )

        def load_fixture(value: str) -> bytes:
            if value == fixture_spec["resources"][0]["graphics_file"]:
                return fixture_graphics
            return load_file(value)

        fixture_output, fixture_allocations, fixture_end = _build(
            fixture_spec,
            load_fixture,
            base,
            layout,
            region.start,
            region.end,
        )
        fixture_hash = _sha256(fixture_output)
        fixture_tiles = len(fixture_graphics) // 32
        fixture_components = sum(
            len(frame["components"])
            for resource in fixture_spec["resources"]
            for frame in resource["frames"]
        )
        fixture_keyframes = sum(
            len(animation["keyframes"])
            for resource in fixture_spec["resources"]
            for animation in resource["animations"]
        )
        expected_fixture = {
            "schema": "cutscene-obj-bundle-capability-fixture-v1",
            "construction": (
                "Extend resource 0 deterministically from 128 to 256 tiles, "
                "add a second 64x64 component at tile 192, and append a "
                "second keyframe to animation 0."
            ),
            "graphics_tile_count": fixture_tiles,
            "graphics_sha256": _sha256(fixture_graphics),
            "component_count": fixture_components,
            "keyframe_count": fixture_keyframes,
            "allocation_count": len(fixture_allocations),
            "pointer_patch_count": 16,
            "allocation_end": fixture_end,
            "output_rom_sha256": fixture_hash,
        }
        if payload.get("capability_fixture") != expected_fixture:
            raise ValueError("capability fixture mismatch")
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        struct.error,
    ) as error:
        errors.append(str(error))
    return {
        "schema": "cutscene-obj-bundle-relocation-verification-v1",
        "verified_resources": verified_resources,
        "verified_source_pointers": verified_source_pointers,
        "verified_fixture_tiles": fixture_tiles,
        "verified_fixture_components": fixture_components,
        "verified_fixture_keyframes": fixture_keyframes,
        "rebuilt_output_rom_sha256": rebuilt_hash,
        "capability_fixture_output_rom_sha256": fixture_hash,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts") / ARTIFACT_ID,
    )
    args = parser.parse_args()
    report = verify_audit(args.root, args.artifact)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
