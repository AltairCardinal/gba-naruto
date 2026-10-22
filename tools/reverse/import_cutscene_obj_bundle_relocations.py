#!/usr/bin/env python3
"""Relocate the four fixed Cutscene OBJ bundles into expanded ROM."""

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

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import encode_gba_lz77
from tools.image_resource_regions import ImageResourceRegions
from tools.rom_layout import RomLayout


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
CATALOG_PATH = Path("artifacts/cutscene-obj-v1/manifest.json")
CATALOG_SHA256 = (
    "b8e1341172decef9f07080879cd8369bc5308274d84383d5c706de72a0b781e7"
)
REGION_REGISTRY_PATH = Path("sequel/image-resource-regions.json")
SPEC_SCHEMA = "cutscene-obj-bundle-relocation-v1"
RESOURCE_TABLE_OFFSET = 0x53DF70
SPRITE_TABLE_OFFSET = 0x53DF90
ENTRY_COUNT = 4
ENTRY_SIZE = 8
FRAME_COUNTS = (2, 2, 2, 4)
COMPONENT_SIZE = 20
TERMINATOR = bytes.fromhex("ffff0000")
RUNTIME_TILE_BASE = 0x300
MAX_GRAPHICS_TILES = 0x400 - RUNTIME_TILE_BASE
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path")
    path = Path(value)
    return path if path.is_absolute() else root / path


def _integer(
    value: object,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{label} must be in {minimum}..{maximum}")
    return value


def _rom_offset(pointer: int, rom_size: int, label: str) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"{label} pointer 0x{pointer:08X} is outside ROM")
    return offset


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


def _verify_runtime_contract(rom: bytes) -> None:
    if _thumb_bl_calls(rom, LOADER_TARGET) != set(LOADER_CALLS):
        raise ValueError("Cutscene OBJ loader call-site denominator mismatch")
    for address, (_, expected_hex) in LOADER_CALLS.items():
        offset = address - ROM_BASE
        if rom[offset - 2 : offset + 4].hex() != expected_hex:
            raise ValueError(
                f"Cutscene OBJ loader caller 0x{address:08X} mismatch"
            )
    for name, (start, end, expected_hash) in CONSUMER_RANGES.items():
        raw = rom[start - ROM_BASE : end - ROM_BASE]
        if len(raw) != end - start or _sha256(raw) != expected_hash:
            raise ValueError(f"Cutscene OBJ consumer evidence changed: {name}")
    literals = (
        (0x72F3C, ROM_BASE + RESOURCE_TABLE_OFFSET),
        (0x72F40, 0x06016000),
        (0x72F44, 0x05000380),
        (0x72FC8, ROM_BASE + SPRITE_TABLE_OFFSET),
    )
    for offset, expected in literals:
        if struct.unpack_from("<I", rom, offset)[0] != expected:
            raise ValueError(
                f"Cutscene OBJ consumer literal 0x{offset:06X} mismatch"
            )
    if rom[0x72F7A:0x72F80].hex() != "c02080000190":
        raise ValueError("Cutscene OBJ runtime tile-base contract mismatch")


def catalog_cutscene_obj_bundle(
    root: Path,
    rom: bytes | None = None,
) -> dict[str, Any]:
    """Rebuild the fixed IDs and all 36 exact source pointer references."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("Cutscene OBJ relocation base ROM SHA-256 mismatch")
    catalog_bytes = (root / CATALOG_PATH).read_bytes()
    if _sha256(catalog_bytes) != CATALOG_SHA256:
        raise ValueError("Cutscene OBJ source catalog SHA-256 mismatch")
    source = json.loads(catalog_bytes)
    if (
        source.get("schema") != "cutscene-obj-export-v1"
        or source.get("resource_count") != ENTRY_COUNT
        or source.get("frame_counts") != list(FRAME_COUNTS)
        or len(source.get("resources", [])) != ENTRY_COUNT
    ):
        raise ValueError("Cutscene OBJ source catalog denominator mismatch")
    _verify_runtime_contract(base)

    table_refs = {}
    for pointer, expected_offset in (
        (ROM_BASE + RESOURCE_TABLE_OFFSET, 0x72F3C),
        (ROM_BASE + SPRITE_TABLE_OFFSET, 0x72FC8),
    ):
        actual = {
            offset
            for offset in range(0, len(base) - 3, 4)
            if struct.unpack_from("<I", base, offset)[0] == pointer
        }
        if actual != {expected_offset}:
            raise ValueError(
                f"Cutscene OBJ table-base reference 0x{pointer:08X} mismatch"
            )
        table_refs[pointer] = actual

    expected: dict[int, set[int]] = {}
    reference_kinds: dict[int, set[str]] = {}
    entries = []

    def expect(pointer: int, offset: int, kind: str) -> None:
        expected.setdefault(pointer, set()).add(offset)
        reference_kinds.setdefault(pointer, set()).add(kind)

    for resource_id, row in enumerate(source["resources"]):
        if (
            not isinstance(row, dict)
            or row.get("resource_id") != resource_id
            or row.get("frame_count") != FRAME_COUNTS[resource_id]
        ):
            raise ValueError(
                f"Cutscene OBJ source resource {resource_id} mismatch"
            )
        resource_pair = RESOURCE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        sprite_pair = SPRITE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        graphics_pointer, palette_pointer = struct.unpack_from(
            "<II", base, resource_pair
        )
        definition_table_pointer, animation_table_pointer = struct.unpack_from(
            "<II", base, sprite_pair
        )
        pointers = {
            "gfx_pointer": graphics_pointer,
            "palette_pointer": palette_pointer,
            "definition_table_pointer": definition_table_pointer,
            "animation_table_pointer": animation_table_pointer,
        }
        for key, pointer in pointers.items():
            if int(row.get(key, "0"), 16) != pointer:
                raise ValueError(
                    f"Cutscene OBJ resource {resource_id} {key} mismatch"
                )
        graphics_offset = _rom_offset(
            graphics_pointer, len(base), "graphics"
        )
        palette_offset = _rom_offset(palette_pointer, len(base), "palette")
        graphics = lz77_decompress(base, graphics_offset)
        palette = lz77_decompress(base, palette_offset)
        if (
            not graphics
            or len(graphics) % 32
            or len(graphics) // 32 > MAX_GRAPHICS_TILES
            or len(palette) != 32
            or row.get("atlas", {}).get("tile_count") != len(graphics) // 32
        ):
            raise ValueError(
                f"Cutscene OBJ resource {resource_id} payload mismatch"
            )
        expect(graphics_pointer, resource_pair, "graphics")
        expect(palette_pointer, resource_pair + 4, "palette")
        expect(
            definition_table_pointer,
            sprite_pair,
            "definition_table",
        )
        expect(
            animation_table_pointer,
            sprite_pair + 4,
            "animation_table",
        )

        frame_count = FRAME_COUNTS[resource_id]
        definition_table_offset = _rom_offset(
            definition_table_pointer,
            len(base),
            "definition table",
        )
        animation_table_offset = _rom_offset(
            animation_table_pointer,
            len(base),
            "animation table",
        )
        frames = row.get("frames")
        if not isinstance(frames, list) or len(frames) != frame_count:
            raise ValueError(
                f"Cutscene OBJ resource {resource_id} frame count mismatch"
            )
        for frame_id, frame in enumerate(frames):
            definition_pointer = struct.unpack_from(
                "<I", base, definition_table_offset + frame_id * 4
            )[0]
            animation_pointer = struct.unpack_from(
                "<I", base, animation_table_offset + frame_id * 4
            )[0]
            if (
                frame.get("frame_id") != frame_id
                or int(frame.get("definition_pointer", "0"), 16)
                != definition_pointer
                or int(frame.get("animation_pointer", "0"), 16)
                != animation_pointer
            ):
                raise ValueError(
                    f"Cutscene OBJ resource {resource_id} frame {frame_id} "
                    "pointer mismatch"
                )
            definition_offset = _rom_offset(
                definition_pointer,
                len(base),
                "component list",
            )
            animation_offset = _rom_offset(
                animation_pointer,
                len(base),
                "animation sequence",
            )
            definition_raw = base[
                definition_offset : definition_offset + COMPONENT_SIZE + 4
            ]
            animation_raw = base[animation_offset : animation_offset + 8]
            if (
                definition_raw.hex() != frame.get("definition_raw_hex")
                or definition_raw[-4:] != TERMINATOR
                or animation_raw.hex() != frame.get("animation_raw_hex")
                or animation_raw[-4:] != TERMINATOR
            ):
                raise ValueError(
                    f"Cutscene OBJ resource {resource_id} frame {frame_id} "
                    "record mismatch"
                )
            expect(
                definition_pointer,
                definition_table_offset + frame_id * 4,
                "definition",
            )
            expect(
                animation_pointer,
                animation_table_offset + frame_id * 4,
                "animation",
            )
        entries.append(
            {
                "id": resource_id,
                "graphics_pointer": graphics_pointer,
                "palette_pointer": palette_pointer,
                "definition_table_pointer": definition_table_pointer,
                "animation_table_pointer": animation_table_pointer,
                "graphics_tile_count": len(graphics) // 32,
                "frame_count": frame_count,
            }
        )

    actual = {pointer: set() for pointer in expected}
    for offset in range(0, len(base) - 3, 4):
        value = struct.unpack_from("<I", base, offset)[0]
        if value in actual:
            actual[value].add(offset)
    missing = []
    unexpected = []
    for pointer in sorted(expected):
        missing.extend(sorted(expected[pointer] - actual[pointer]))
        unexpected.extend(sorted(actual[pointer] - expected[pointer]))
    if missing:
        raise ValueError(
            f"Cutscene OBJ exact pointer inventory missing {missing}"
        )

    kinds = (
        "graphics",
        "palette",
        "definition_table",
        "animation_table",
        "definition",
        "animation",
    )
    kind_counts = {
        kind: sum(
            len(expected[pointer])
            for pointer in expected
            if kind in reference_kinds[pointer]
        )
        for kind in kinds
    }
    return {
        "resource_count": ENTRY_COUNT,
        "frame_counts": list(FRAME_COUNTS),
        "frame_count": sum(FRAME_COUNTS),
        "animation_count": sum(FRAME_COUNTS),
        "runtime_tile_base": RUNTIME_TILE_BASE,
        "maximum_safe_graphics_tiles": MAX_GRAPHICS_TILES,
        "runtime_loader_call_count": len(LOADER_CALLS),
        "runtime_resource_ids": sorted(
            {resource_id for resource_id, _ in LOADER_CALLS.values()}
        ),
        "table_base_reference_count": sum(
            len(offsets) for offsets in table_refs.values()
        ),
        "pointer_reference_counts": kind_counts,
        "pointer_reference_count": sum(kind_counts.values()),
        "unexpected_pointer_offsets": unexpected,
        "entries": entries,
    }


def _encode_component(
    component: object,
    *,
    resource_id: int,
    frame_id: int,
    component_id: int,
    graphics_tiles: int,
) -> bytes:
    label = (
        f"resource {resource_id} frame {frame_id} component {component_id}"
    )
    if not isinstance(component, dict):
        raise ValueError(f"{label} must be an object")
    tile_offset = _integer(
        component.get("tile_offset"),
        f"{label} tile_offset",
        0,
        MAX_GRAPHICS_TILES - 1,
    )
    x = _integer(
        component.get("x_offset"),
        f"{label} x_offset",
        -0x8000,
        0x7FFF,
    )
    y = _integer(
        component.get("y_offset"),
        f"{label} y_offset",
        -0x8000,
        0x7FFF,
    )
    width = _integer(component.get("width"), f"{label} width", 1, 64)
    height = _integer(component.get("height"), f"{label} height", 1, 64)
    if (width, height) not in SUPPORTED_SIZES:
        raise ValueError(f"{label} is not a supported GBA OBJ shape")
    tile_end = tile_offset + width * height // 64
    if tile_end > graphics_tiles:
        raise ValueError(
            f"{label} tile range ends at {tile_end}, beyond graphics "
            f"tile count {graphics_tiles}"
        )
    return struct.pack(
        "<IhhHHHHHH",
        tile_offset,
        x,
        y,
        width,
        height,
        0x0100,
        0x0100,
        0x00FF,
        0,
    )


def _allocation(
    *,
    patch_id: str,
    offset: int,
    data: bytes,
    resource_type: str,
    region_id: str,
    region_owner: str,
    **metadata: object,
) -> dict[str, Any]:
    return {
        "id": patch_id,
        "type": "bytes",
        "offset": offset,
        "before_hex": (b"\xFF" * len(data)).hex(),
        "after_hex": data.hex(),
        "patch_class": "allocation",
        "allocation": {
            "partition": "sequel-image-assets",
            "owner": "sequel_image_assets",
            "region": region_id,
            "region_owner": region_owner,
        },
        "asset_type": "cutscene_obj_bundle_allocation",
        "resource_type": resource_type,
        **metadata,
    }


def _redirect(
    base: bytes,
    *,
    patch_id: str,
    offset: int,
    pointer: int,
    role: str,
    resource_id: int,
) -> dict[str, Any]:
    return {
        "id": patch_id,
        "type": "bytes",
        "offset": offset,
        "before_hex": base[offset : offset + 4].hex(),
        "after_hex": struct.pack("<I", pointer).hex(),
        "patch_class": "game_effective",
        "asset_type": "cutscene_obj_bundle_pointer",
        "pointer_role": role,
        "resource_id": resource_id,
        "new_pointer": pointer,
    }


def resolve_cutscene_obj_bundle_relocation_patches(
    root: Path,
    spec_path: Path,
    *,
    rom: bytes | None = None,
    layout: RomLayout | None = None,
    regions: ImageResourceRegions | None = None,
) -> list[dict[str, Any]]:
    """Build one atomic relocation for all four fixed Cutscene OBJ IDs."""
    root = Path(root).resolve()
    base = (root / "rom/base.gba").read_bytes() if rom is None else bytes(rom)
    if _sha256(base) != ROM_SHA256:
        raise ValueError("Cutscene OBJ relocation base ROM SHA-256 mismatch")
    catalog = catalog_cutscene_obj_bundle(root, base)
    if catalog["unexpected_pointer_offsets"]:
        raise ValueError("Cutscene OBJ source has unexpected references")

    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if not isinstance(spec, dict) or spec.get("schema") != SPEC_SCHEMA:
        raise ValueError("Cutscene OBJ relocation spec schema mismatch")
    required = {
        "base_rom_sha256": ROM_SHA256,
        "source_catalog": CATALOG_PATH.as_posix(),
        "source_catalog_sha256": CATALOG_SHA256,
        "partition": "sequel-image-assets",
        "owner": "sequel_image_assets",
        "region_registry": REGION_REGISTRY_PATH.as_posix(),
        "region": "cutscene-obj-bundle",
        "region_owner": "cutscene_obj_resources",
    }
    for key, expected in required.items():
        if spec.get(key) != expected:
            raise ValueError(f"Cutscene OBJ relocation {key} mismatch")
    registry_path = root / REGION_REGISTRY_PATH
    if spec.get("region_registry_sha256") != _sha256(
        registry_path.read_bytes()
    ):
        raise ValueError("Cutscene OBJ region registry SHA-256 mismatch")
    if layout is None:
        layout = RomLayout.from_path(root / "sequel/rom-layout.json", base)
    if regions is None:
        regions = ImageResourceRegions.from_path(registry_path, layout)
    region = regions.require(
        "cutscene-obj-bundle",
        "cutscene_obj_resources",
    )

    authored = spec.get("resources")
    if not isinstance(authored, list) or len(authored) != ENTRY_COUNT:
        raise ValueError("Cutscene OBJ resources must contain exactly IDs 0..3")
    ids = [row.get("id") if isinstance(row, dict) else None for row in authored]
    if (
        any(isinstance(value, bool) or not isinstance(value, int) for value in ids)
        or set(ids) != set(range(ENTRY_COUNT))
        or len(ids) != len(set(ids))
    ):
        raise ValueError("Cutscene OBJ resources must contain exactly IDs 0..3")
    authored_by_id = {row["id"]: row for row in authored}

    encoded_resources = []
    for resource_id in range(ENTRY_COUNT):
        resource = authored_by_id[resource_id]
        graphics_path = _resolve(
            root,
            resource.get("graphics_file"),
            f"resource {resource_id} graphics_file",
        )
        palette_path = _resolve(
            root,
            resource.get("palette_file"),
            f"resource {resource_id} palette_file",
        )
        graphics = graphics_path.read_bytes()
        palette = palette_path.read_bytes()
        if (
            not graphics
            or len(graphics) % 32
            or len(graphics) // 32 > MAX_GRAPHICS_TILES
        ):
            raise ValueError(
                "Cutscene OBJ graphics must contain "
                f"1..{MAX_GRAPHICS_TILES} complete 4bpp tiles"
            )
        if len(palette) != 32:
            raise ValueError(
                "Cutscene OBJ palette must contain exactly 16 colors"
            )
        graphics_tiles = len(graphics) // 32
        expected_count = FRAME_COUNTS[resource_id]
        frames = resource.get("frames")
        animations = resource.get("animations")
        if (
            not isinstance(frames, list)
            or not isinstance(animations, list)
            or len(frames) != expected_count
            or len(animations) != expected_count
        ):
            raise ValueError(
                "Cutscene OBJ resources must preserve fixed frame counts "
                "[2, 2, 2, 4]"
            )
        frame_ids = [
            frame.get("id") if isinstance(frame, dict) else None
            for frame in frames
        ]
        animation_ids = [
            animation.get("id") if isinstance(animation, dict) else None
            for animation in animations
        ]
        if frame_ids != list(range(expected_count)) or animation_ids != list(
            range(expected_count)
        ):
            raise ValueError(
                "Cutscene OBJ resources must preserve fixed frame counts "
                "[2, 2, 2, 4]"
            )

        component_lists = []
        component_counts = []
        for frame_id, frame in enumerate(frames):
            components = frame.get("components")
            if (
                not isinstance(components, list)
                or not 1 <= len(components) <= MAX_COMPONENTS
            ):
                raise ValueError(
                    f"resource {resource_id} frame {frame_id} must contain "
                    f"1..{MAX_COMPONENTS} components"
                )
            encoded = b"".join(
                _encode_component(
                    component,
                    resource_id=resource_id,
                    frame_id=frame_id,
                    component_id=component_id,
                    graphics_tiles=graphics_tiles,
                )
                for component_id, component in enumerate(components)
            )
            component_lists.append(encoded + TERMINATOR)
            component_counts.append(len(components))

        sequences = []
        keyframe_counts = []
        for animation_id, animation in enumerate(animations):
            keyframes = animation.get("keyframes")
            if not isinstance(keyframes, list) or not keyframes:
                raise ValueError(
                    f"resource {resource_id} animation {animation_id} "
                    "must contain non-empty keyframes"
                )
            sequence = bytearray()
            for keyframe_id, keyframe in enumerate(keyframes):
                if not isinstance(keyframe, dict):
                    raise ValueError(
                        f"resource {resource_id} animation {animation_id} "
                        f"keyframe {keyframe_id} must be an object"
                    )
                frame_id = _integer(
                    keyframe.get("frame_id"),
                    (
                        f"resource {resource_id} animation {animation_id} "
                        f"keyframe {keyframe_id} frame ID"
                    ),
                    0,
                    expected_count - 1,
                )
                duration = _integer(
                    keyframe.get("duration_ticks"),
                    (
                        f"resource {resource_id} animation {animation_id} "
                        f"keyframe {keyframe_id} duration_ticks"
                    ),
                    0,
                    0xFFFF,
                )
                sequence.extend(struct.pack("<HH", frame_id, duration))
            sequences.append(bytes(sequence) + TERMINATOR)
            keyframe_counts.append(len(keyframes))

        encoded_resources.append(
            {
                "id": resource_id,
                "graphics": graphics,
                "palette": palette,
                "graphics_path": graphics_path,
                "palette_path": palette_path,
                "graphics_tiles": graphics_tiles,
                "component_lists": component_lists,
                "component_counts": component_counts,
                "sequences": sequences,
                "keyframe_counts": keyframe_counts,
            }
        )

    cursor = region.start
    allocations: list[dict[str, Any]] = []

    def allocate(
        data: bytes,
        resource_type: str,
        **metadata: object,
    ) -> int:
        nonlocal cursor
        cursor = (cursor + region.alignment - 1) & -region.alignment
        offset = cursor
        cursor += len(data)
        if cursor > region.end:
            raise ValueError(
                "Cutscene OBJ relocation exceeds registered region "
                f"0x{region.start:X}..0x{region.end:X}"
            )
        allocations.append(
            _allocation(
                patch_id=f"cutscene-obj-{resource_type}-{offset:06x}",
                offset=offset,
                data=data,
                resource_type=resource_type,
                region_id=region.id,
                region_owner=region.owner,
                **metadata,
            )
        )
        return offset

    relocated = []
    for resource in encoded_resources:
        resource_id = resource["id"]
        graphics_encoded = encode_gba_lz77(resource["graphics"])
        palette_encoded = encode_gba_lz77(resource["palette"])
        graphics_offset = allocate(
            graphics_encoded,
            "graphics",
            resource_id=resource_id,
            decompressed_size=len(resource["graphics"]),
            encoded_size=len(graphics_encoded),
            replacement_sha256=_sha256(resource["graphics"]),
            tile_count=resource["graphics_tiles"],
            source_file=str(resource["graphics_path"]),
        )
        palette_offset = allocate(
            palette_encoded,
            "palette",
            resource_id=resource_id,
            decompressed_size=len(resource["palette"]),
            encoded_size=len(palette_encoded),
            replacement_sha256=_sha256(resource["palette"]),
            source_file=str(resource["palette_path"]),
        )

        cursor = (cursor + region.alignment - 1) & -region.alignment
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
        definition_table_pointer = ROM_BASE + bundle_offset + len(body)
        body.extend(
            b"".join(
                struct.pack("<I", pointer)
                for pointer in component_pointers
            )
        )
        animation_table_pointer = ROM_BASE + bundle_offset + len(body)
        body.extend(
            b"".join(
                struct.pack("<I", pointer) for pointer in sequence_pointers
            )
        )
        allocated = allocate(
            bytes(body),
            "resource_bundle",
            resource_id=resource_id,
            frame_count=FRAME_COUNTS[resource_id],
            animation_count=FRAME_COUNTS[resource_id],
            component_counts=resource["component_counts"],
            keyframe_counts=resource["keyframe_counts"],
            definition_table_pointer=definition_table_pointer,
            animation_table_pointer=animation_table_pointer,
            component_pointers=component_pointers,
            sequence_pointers=sequence_pointers,
        )
        if allocated != bundle_offset:
            raise AssertionError("Cutscene OBJ bundle alignment drift")
        relocated.append(
            {
                "id": resource_id,
                "graphics_pointer": ROM_BASE + graphics_offset,
                "palette_pointer": ROM_BASE + palette_offset,
                "definition_table_pointer": definition_table_pointer,
                "animation_table_pointer": animation_table_pointer,
            }
        )

    redirects = []
    for resource in relocated:
        resource_id = resource["id"]
        resource_pair = RESOURCE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        sprite_pair = SPRITE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        for offset, role, pointer in (
            (
                resource_pair,
                "graphics",
                resource["graphics_pointer"],
            ),
            (
                resource_pair + 4,
                "palette",
                resource["palette_pointer"],
            ),
            (
                sprite_pair,
                "definition_table",
                resource["definition_table_pointer"],
            ),
            (
                sprite_pair + 4,
                "animation_table",
                resource["animation_table_pointer"],
            ),
        ):
            redirects.append(
                _redirect(
                    base,
                    patch_id=(
                        f"cutscene-obj-{resource_id}-{role}-pointer"
                    ),
                    offset=offset,
                    pointer=pointer,
                    role=role,
                    resource_id=resource_id,
                )
            )
    return [*allocations, *redirects]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    patches = resolve_cutscene_obj_bundle_relocation_patches(
        args.root,
        args.spec,
    )
    print(json.dumps(patches, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
