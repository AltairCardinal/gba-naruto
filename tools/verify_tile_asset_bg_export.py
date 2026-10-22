#!/usr/bin/env python3
"""Independently verify tile-assets BG layers and atlases against the ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import bgr555_to_rgb, lz77_decompress


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
TABLE_OFFSET = 0x5A320C
TABLE_ENTRY_COUNT = 79
TABLE_ENTRY_SIZE = 0x44
TABLE_SHA256 = "0db18948a6619ac723bebc60f9c2b79f1fea1786c6e80db389064c5f07655f73"
SENTINELS = (13, 31, 32, 46)
LAYER_LAYOUTS = (
    {
        "name": "A",
        "gfx_word": 3,
        "tilemap_word": 4,
        "palette_word": 5,
        "definition_word": None,
        "fixed_width": 30,
        "fixed_height": 14,
        "screen_stride_tiles": 32,
        "bits_per_pixel": 4,
        "palette_size": 32,
        "tile_base": {"kind": "consumer_argument"},
        "palette_bank": {"kind": "consumer_argument"},
    },
    {
        "name": "B",
        "gfx_word": 6,
        "tilemap_word": 7,
        "palette_word": 8,
        "definition_word": None,
        "fixed_width": 32,
        "fixed_height": 14,
        "screen_stride_tiles": 32,
        "bits_per_pixel": 4,
        "palette_size": 32,
        "tile_base": {"kind": "runtime_state"},
        "palette_bank": {"kind": "runtime_state"},
    },
    {
        "name": "C",
        "gfx_word": 10,
        "tilemap_word": 11,
        "palette_word": 12,
        "definition_word": 9,
        "fixed_width": None,
        "fixed_height": None,
        "screen_stride_tiles": 64,
        "bits_per_pixel": 8,
        "palette_size": 128,
        "tile_base": {
            "kind": "runtime_state",
            "expression": "state[0x16] >> 1",
        },
        "palette_bank": {"kind": "runtime_state"},
    },
    {
        "name": "D",
        "gfx_word": 14,
        "tilemap_word": 15,
        "palette_word": 16,
        "definition_word": 13,
        "fixed_width": None,
        "fixed_height": None,
        "screen_stride_tiles": 64,
        "bits_per_pixel": 4,
        "palette_size": 32,
        "tile_base": {
            "kind": "runtime_state",
            "expression": "u16(state[0x12] + state[0x16])",
            "consumer_gba_address": "0x080992FA",
        },
        "palette_bank": {"kind": "runtime_state"},
    },
)

EXPECTED_SUMMARY = {
    "descriptor_count": 79,
    "sentinel_descriptor_ids": [13, 31, 32, 46],
    "complete_layer_counts": {"A": 75, "B": 75, "C": 75, "D": 11},
    "complete_layer_count": 236,
    "partial_layer_count": 1,
    "unique_graphics_count": 107,
    "unique_tilemap_count": 108,
    "unique_palette_count": 107,
    "unique_atlas_count": 108,
    "unique_complete_layer_count": 108,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer 0x{pointer:08X} is outside the ROM")
    return offset


def _definition(
    words: tuple[int, ...],
    layout: dict[str, Any],
) -> dict[str, Any]:
    definition_word = layout["definition_word"]
    if definition_word is None:
        fixed_width = layout["fixed_width"]
        fixed_height = layout["fixed_height"]
        if fixed_width is None or fixed_height is None:
            raise ValueError("fixed layer dimensions are missing")
        return {
            "x_tiles": 0,
            "y_tiles": 0,
            "width_tiles": fixed_width,
            "height_tiles": fixed_height,
            "screen_stride_tiles": layout["screen_stride_tiles"],
            "source": "consumer_fixed",
        }
    data = words[definition_word].to_bytes(4, "little")
    return {
        "x_tiles": data[0],
        "y_tiles": data[1],
        "width_tiles": data[2],
        "height_tiles": data[3],
        "screen_stride_tiles": layout["screen_stride_tiles"],
        "source": "descriptor_packed_bytes",
    }


def _pointer(pointer: int) -> str | None:
    return f"0x{pointer:08X}" if pointer else None


def _read_lz_record(rom: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError("component is not a complete GBA type-0x10 stream")
    expected_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    if expected_size <= 0:
        raise ValueError("component declares an empty LZ payload")
    cursor = offset + 4
    produced = 0
    while produced < expected_size:
        if cursor >= len(rom):
            raise ValueError("component LZ flag byte is truncated")
        flags = rom[cursor]
        cursor += 1
        for bit in range(8):
            if produced >= expected_size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(rom):
                    raise ValueError("component LZ back-reference is truncated")
                first = rom[cursor]
                second = rom[cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                displacement = ((first & 0x0F) << 8 | second) + 1
                if displacement > produced:
                    raise ValueError("component LZ back-reference is invalid")
            else:
                if cursor >= len(rom):
                    raise ValueError("component LZ literal is truncated")
                cursor += 1
                length = 1
            if produced + length > expected_size:
                raise ValueError("component LZ record overruns declared size")
            produced += length
    return rom[offset:cursor]


def _load_lz(
    rom: bytes,
    pointer: int,
    *,
    expected_size: int | None = None,
) -> tuple[bytes, bytes]:
    offset = _offset(pointer, len(rom))
    compressed = _read_lz_record(rom, offset)
    payload = lz77_decompress(rom, offset)
    if expected_size is not None and len(payload) != expected_size:
        raise ValueError(
            f"component decompressed to {len(payload)}, expected {expected_size}"
        )
    return compressed, payload


def _render_tilemap(
    graphics: bytes,
    tilemap: bytes,
    *,
    bits_per_pixel: int,
    width_tiles: int,
    height_tiles: int,
) -> bytes:
    if bits_per_pixel not in (4, 8):
        raise ValueError("unsupported BG color depth")
    bytes_per_tile = bits_per_pixel * 8
    if not graphics or len(graphics) % bytes_per_tile:
        raise ValueError("graphics does not contain complete tiles")
    if len(tilemap) != width_tiles * height_tiles * 2:
        raise ValueError("tilemap size does not match its ROM definition")
    entries = struct.unpack(f"<{width_tiles * height_tiles}H", tilemap)
    tile_count = len(graphics) // bytes_per_tile
    width = width_tiles * 8
    pixels = bytearray(width * height_tiles * 8)
    for tile_y in range(height_tiles):
        for tile_x in range(width_tiles):
            entry = entries[tile_y * width_tiles + tile_x]
            if entry >> 12:
                raise ValueError("source tilemap palette bank is not zero")
            tile = entry & 0x03FF
            if tile >= tile_count:
                raise ValueError(
                    f"tilemap tile {tile} exceeds {tile_count} graphics tiles"
                )
            for local_y in range(8):
                source_y = (
                    7 - local_y if entry & (1 << 11) else local_y
                )
                for local_x in range(8):
                    source_x = (
                        7 - local_x if entry & (1 << 10) else local_x
                    )
                    if bits_per_pixel == 8:
                        color = graphics[
                            tile * 64 + source_y * 8 + source_x
                        ]
                    else:
                        packed = graphics[
                            tile * 32 + source_y * 4 + source_x // 2
                        ]
                        color = (
                            packed >> (4 if source_x & 1 else 0)
                        ) & 0x0F
                    x = tile_x * 8 + local_x
                    y = tile_y * 8 + local_y
                    pixels[y * width + x] = color
    return bytes(pixels)


def _render_atlas(
    graphics: bytes,
    *,
    bits_per_pixel: int,
) -> tuple[bytes, int, int]:
    if bits_per_pixel not in (4, 8):
        raise ValueError("unsupported atlas color depth")
    bytes_per_tile = bits_per_pixel * 8
    if not graphics or len(graphics) % bytes_per_tile:
        raise ValueError("atlas graphics does not contain complete tiles")
    tile_count = len(graphics) // bytes_per_tile
    columns = min(tile_count, 32)
    rows = (tile_count + 31) // 32
    width = columns * 8
    height = rows * 8
    pixels = bytearray(width * height)
    for tile in range(tile_count):
        tile_x = tile % 32
        tile_y = tile // 32
        for local_y in range(8):
            for local_x in range(8):
                if bits_per_pixel == 8:
                    color = graphics[
                        tile * 64 + local_y * 8 + local_x
                    ]
                else:
                    packed = graphics[
                        tile * 32 + local_y * 4 + local_x // 2
                    ]
                    color = (
                        packed >> (4 if local_x & 1 else 0)
                    ) & 0x0F
                pixels[
                    (tile_y * 8 + local_y) * width
                    + tile_x * 8
                    + local_x
                ] = color
    return bytes(pixels), width, height


def _palette_rgb(palette: bytes) -> bytes:
    if not palette or len(palette) % 2:
        raise ValueError("palette does not contain complete BGR555 colors")
    result = bytearray()
    for offset in range(0, len(palette), 2):
        result.extend(
            bgr555_to_rgb(struct.unpack_from("<H", palette, offset)[0])
        )
    return bytes(result)


def _tilemap_facts(
    tilemap: bytes,
    *,
    tile_count: int | None,
) -> dict[str, Any]:
    if not tilemap or len(tilemap) % 2:
        raise ValueError("tilemap does not contain complete entries")
    entries = struct.unpack(f"<{len(tilemap) // 2}H", tilemap)
    palette_banks = sorted({entry >> 12 for entry in entries})
    if palette_banks != [0]:
        raise ValueError("source tilemap palette bank is not zero")
    indices = [entry & 0x03FF for entry in entries]
    if tile_count is not None and max(indices) >= tile_count:
        raise ValueError(
            f"tilemap tile {max(indices)} exceeds {tile_count} graphics tiles"
        )
    return {
        "tile_index_min": min(indices),
        "tile_index_max": max(indices),
        "used_tile_count": len(set(indices)),
        "horizontal_flip_count": sum(
            bool(entry & (1 << 10)) for entry in entries
        ),
        "vertical_flip_count": sum(
            bool(entry & (1 << 11)) for entry in entries
        ),
        "source_palette_banks": palette_banks,
    }


def _verify_png(
    path: Path,
    *,
    pixels: bytes,
    palette: bytes,
    width: int,
    height: int,
    expected_sha256: str,
) -> None:
    png = path.read_bytes()
    if _sha256(png) != expected_sha256:
        raise ValueError(f"{path.name} SHA-256 does not match the manifest")
    with Image.open(path) as image:
        image.load()
        if image.mode != "P":
            raise ValueError(f"{path.name} is not an indexed PNG")
        if image.size != (width, height):
            raise ValueError(
                f"{path.name} size is {image.size}, expected {(width, height)}"
            )
        if image.info.get("transparency") != 0:
            raise ValueError(f"{path.name} transparent index is not zero")
        if image.tobytes() != pixels:
            raise ValueError(f"{path.name} pixels do not match the ROM")
        png_palette = image.getpalette()
        if png_palette is None:
            raise ValueError(f"{path.name} palette is missing")
        expected_palette = _palette_rgb(palette)
        if bytes(png_palette[: len(expected_palette)]) != expected_palette:
            raise ValueError(f"{path.name} palette does not match the ROM")


def _verify_component_manifest(
    manifest: dict[str, Any],
    *,
    pointer: int,
    payload: bytes,
    compressed_record: bytes | None,
) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("component manifest is not an object")
    offset = pointer - ROM_BASE
    if manifest.get("file_offset") != offset:
        raise ValueError("component file offset does not match the ROM")
    if manifest.get("gba_address") != f"0x{pointer:08X}":
        raise ValueError("component GBA address does not match the ROM")
    if compressed_record is not None:
        if manifest.get("compressed_size") != len(compressed_record):
            raise ValueError("compressed component size mismatch")
        if manifest.get("compressed_sha256") != _sha256(compressed_record):
            raise ValueError("compressed component hash mismatch")
        if manifest.get("decompressed_size") != len(payload):
            raise ValueError("decompressed component size mismatch")
        if manifest.get("decompressed_sha256") != _sha256(payload):
            raise ValueError("decompressed component hash mismatch")
    else:
        if manifest.get("size") != len(payload):
            raise ValueError("palette size mismatch")
        if manifest.get("sha256") != _sha256(payload):
            raise ValueError("palette hash mismatch")


def _expected_atlas_catalog(
    rom: bytes,
    artifact_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, str, str], dict[str, Any]],
    dict[str, tuple[bytes, bytes, int, int, str]],
]:
    atlases: list[dict[str, Any]] = []
    by_pair: dict[tuple[str, str, str], dict[str, Any]] = {}
    pixel_expectations: dict[
        str,
        tuple[bytes, bytes, int, int, str],
    ] = {}
    for descriptor_id in range(TABLE_ENTRY_COUNT):
        row_offset = TABLE_OFFSET + descriptor_id * TABLE_ENTRY_SIZE
        words = struct.unpack_from("<17I", rom, row_offset)
        if not any(words):
            continue
        for layout in LAYER_LAYOUTS:
            pointers = (
                words[layout["gfx_word"]],
                words[layout["tilemap_word"]],
                words[layout["palette_word"]],
            )
            if sum(bool(pointer) for pointer in pointers) != 3:
                continue
            _, graphics = _load_lz(
                rom,
                pointers[0],
                expected_size=4096 if layout["name"] == "B" else None,
            )
            palette_offset = _offset(pointers[2], len(rom))
            palette_size = layout["palette_size"]
            palette = rom[
                palette_offset : palette_offset + palette_size
            ]
            if len(palette) != palette_size:
                raise ValueError("atlas palette is truncated")
            graphics_hash = _sha256(graphics)
            palette_hash = _sha256(palette)
            bits_per_pixel = layout["bits_per_pixel"]
            bytes_per_tile = bits_per_pixel * 8
            pair = (str(bits_per_pixel), graphics_hash, palette_hash)
            atlas = by_pair.get(pair)
            if atlas is None:
                pixels, width, height = _render_atlas(
                    graphics,
                    bits_per_pixel=bits_per_pixel,
                )
                atlas_id = len(atlases)
                filename = f"atlas_{atlas_id:03d}.png"
                png_hash = _sha256((artifact_dir / filename).read_bytes())
                atlas = {
                    "atlas_id": atlas_id,
                    "png": filename,
                    "png_sha256": png_hash,
                    "width": width,
                    "height": height,
                    "bits_per_pixel": bits_per_pixel,
                    "bytes_per_tile": bytes_per_tile,
                    "tile_count": len(graphics) // bytes_per_tile,
                    "graphics_sha256": graphics_hash,
                    "palette_sha256": palette_hash,
                    "reuse_count": 0,
                }
                atlases.append(atlas)
                by_pair[pair] = atlas
                pixel_expectations[filename] = (
                    pixels,
                    palette,
                    width,
                    height,
                    png_hash,
                )
            atlas["reuse_count"] += 1
    return atlases, by_pair, pixel_expectations


def verify_tile_asset_bg_export(
    root: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Return a ROM-to-PNG verification report independent of the exporter."""
    root = Path(root).resolve()
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = root / artifact_dir

    errors: list[str] = []
    verified_descriptors = 0
    verified_complete_layers = 0
    verified_atlases = 0
    atlas_expectations: dict[str, tuple[bytes, bytes, int, int, str]] = {}
    expected_atlases: list[dict[str, Any]] = []
    expected_atlas_by_pair: dict[tuple[str, str, str], dict[str, Any]] = {}

    rom = (root / "rom/base.gba").read_bytes()
    rom_hash = _sha256(rom)
    manifest = json.loads(
        (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    )
    if rom_hash != ROM_SHA256:
        errors.append(f"ROM SHA-256 is {rom_hash}, expected {ROM_SHA256}")
    if manifest.get("schema") != "tile-assets-bg-export-v2":
        errors.append("unexpected export manifest schema")
    expected_rom = {
        "path": "rom/base.gba",
        "size": len(rom),
        "sha256": rom_hash,
    }
    if manifest.get("rom") != expected_rom:
        errors.append("manifest ROM metadata mismatch")
    if manifest.get("source_bank") != "sequel/content/tile-assets/bank.json":
        errors.append("source bank metadata mismatch")
    expected_supersedes = {
        "artifact": "artifacts/tile-assets-bg-v1",
        "reason": "v1 decoded consumer-proven 8bpp C layers as 4bpp",
    }
    if manifest.get("supersedes") != expected_supersedes:
        errors.append("superseded artifact metadata mismatch")
    expected_source_table = {
        "file_offset": TABLE_OFFSET,
        "gba_address": f"0x{ROM_BASE + TABLE_OFFSET:08X}",
        "entry_count": TABLE_ENTRY_COUNT,
        "entry_size": TABLE_ENTRY_SIZE,
        "sha256": TABLE_SHA256,
        "verification": "code_verified",
    }
    if manifest.get("source_table") != expected_source_table:
        errors.append("source table metadata mismatch")
    expected_scope = {
        "kind": "native static BG layers and complete mixed-depth atlases",
        "final_composite": False,
        "layer_color_depths": {
            "A": "4bpp",
            "B": "4bpp",
            "C": "8bpp",
            "D": "4bpp",
        },
        "runtime_tile_base_and_palette_bank_preserved_as_unknowns": True,
    }
    if manifest.get("scope") != expected_scope:
        errors.append("export scope metadata mismatch")
    summary_labels = {
        "descriptor_count": "descriptor count",
        "sentinel_descriptor_ids": "sentinel descriptor IDs",
        "complete_layer_counts": "per-layer complete counts",
        "complete_layer_count": "complete layer count",
        "partial_layer_count": "partial layer count",
        "unique_graphics_count": "unique graphics count",
        "unique_tilemap_count": "unique tilemap count",
        "unique_palette_count": "unique palette count",
        "unique_atlas_count": "unique atlas count",
        "unique_complete_layer_count": "unique complete layer count",
    }
    for key, expected in EXPECTED_SUMMARY.items():
        if manifest.get(key) != expected:
            errors.append(f"{summary_labels[key]} mismatch")
    table_end = TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    if _sha256(rom[TABLE_OFFSET:table_end]) != TABLE_SHA256:
        errors.append("tile-assets table hash mismatch")
    try:
        (
            expected_atlases,
            expected_atlas_by_pair,
            atlas_expectations,
        ) = _expected_atlas_catalog(rom, artifact_dir)
    except (OSError, TypeError, ValueError, struct.error) as error:
        errors.append(f"atlas catalog: {error}")

    descriptors = manifest.get("descriptors")
    if not isinstance(descriptors, list) or len(descriptors) != 79:
        errors.append("manifest does not contain exactly 79 descriptors")
        descriptors = [] if not isinstance(descriptors, list) else descriptors

    for index, descriptor in enumerate(descriptors[:TABLE_ENTRY_COUNT]):
        try:
            if not isinstance(descriptor, dict):
                raise ValueError("descriptor is not an object")
            row_offset = TABLE_OFFSET + index * TABLE_ENTRY_SIZE
            words = struct.unpack_from("<17I", rom, row_offset)
            expected_words = [f"0x{word:08X}" for word in words]
            if descriptor.get("raw_words") != expected_words:
                raise ValueError("raw words do not match the ROM")
            if descriptor.get("descriptor_id") != index:
                raise ValueError("descriptor ID mismatch")
            if descriptor.get("consumer_id") != index + 1:
                raise ValueError("consumer ID mismatch")
            if descriptor.get("descriptor_file_offset") != row_offset:
                raise ValueError("descriptor file offset mismatch")
            if descriptor.get("descriptor_gba_address") != (
                f"0x{ROM_BASE + row_offset:08X}"
            ):
                raise ValueError("descriptor GBA address mismatch")

            is_sentinel = not any(words)
            if is_sentinel:
                if index not in SENTINELS:
                    raise ValueError("unexpected all-zero descriptor")
                if descriptor.get("status") != "sentinel":
                    raise ValueError("sentinel status is missing")
                if descriptor.get("layers") != []:
                    raise ValueError("sentinel unexpectedly contains layers")
                verified_descriptors += 1
                continue
            if index in SENTINELS:
                raise ValueError("expected sentinel is not all zero")
            expected_descriptor_status = "partial" if index == 0 else "complete"
            if descriptor.get("status") != expected_descriptor_status:
                raise ValueError("descriptor status mismatch")

            layer_records = descriptor.get("layers")
            if not isinstance(layer_records, list) or len(layer_records) != 4:
                raise ValueError("non-sentinel does not contain four layers")
            by_name = {
                layer.get("name"): layer
                for layer in layer_records
                if isinstance(layer, dict)
            }
            if set(by_name) != {"A", "B", "C", "D"}:
                raise ValueError("layer names are not exactly A/B/C/D")
            for layout in LAYER_LAYOUTS:
                name = layout["name"]
                layer = by_name.get(name)
                if not isinstance(layer, dict):
                    raise ValueError(f"layer {name} is missing")
                definition = _definition(words, layout)
                if layer.get("definition") != definition:
                    raise ValueError(f"layer {name} definition mismatch")
                if layer.get("tile_base") != layout["tile_base"]:
                    raise ValueError(
                        f"layer {name} tile-base semantics mismatch"
                    )
                if layer.get("palette_bank") != layout["palette_bank"]:
                    raise ValueError(
                        f"layer {name} palette-bank semantics mismatch"
                    )
                bits_per_pixel = layout["bits_per_pixel"]
                bytes_per_tile = bits_per_pixel * 8
                if layer.get("bits_per_pixel") != bits_per_pixel:
                    raise ValueError(f"layer {name} color depth mismatch")
                if layer.get("bytes_per_tile") != bytes_per_tile:
                    raise ValueError(f"layer {name} bytes-per-tile mismatch")
                if (
                    layer.get("palette_color_count")
                    != layout["palette_size"] // 2
                ):
                    raise ValueError(f"layer {name} palette count mismatch")
                width_tiles = definition["width_tiles"]
                height_tiles = definition["height_tiles"]
                pointers = (
                    words[layout["gfx_word"]],
                    words[layout["tilemap_word"]],
                    words[layout["palette_word"]],
                )
                expected_pointer_fields = (
                    ("gfx_pointer", pointers[0]),
                    ("tilemap_pointer", pointers[1]),
                    ("palette_pointer", pointers[2]),
                )
                for field, pointer in expected_pointer_fields:
                    if layer.get(field) != _pointer(pointer):
                        raise ValueError(f"layer {name} {field} mismatch")
                present_count = sum(bool(pointer) for pointer in pointers)
                if present_count == 0:
                    if name != "D" or layer.get("status") != "absent":
                        raise ValueError(f"unexpected absent layer {name}")
                    continue
                expected_map_size = width_tiles * height_tiles * 2
                if expected_map_size <= 0:
                    raise ValueError(f"layer {name} dimensions are invalid")

                if present_count != 3:
                    if not (
                        index == 0
                        and name == "D"
                        and pointers[0] == 0
                        and pointers[1] != 0
                        and pointers[2] == 0
                    ):
                        raise ValueError(f"unexpected partial layer {name}")
                    if layer.get("status") != "partial":
                        raise ValueError("partial D status mismatch")
                    compressed_tilemap, tilemap = _load_lz(
                        rom,
                        pointers[1],
                        expected_size=expected_map_size,
                    )
                    _verify_component_manifest(
                        layer["tilemap"],
                        pointer=pointers[1],
                        payload=tilemap,
                        compressed_record=compressed_tilemap,
                    )
                    if layer.get("missing_components") != ["gfx", "palette"]:
                        raise ValueError("partial D missing-component list mismatch")
                    expected_facts = _tilemap_facts(
                        tilemap,
                        tile_count=None,
                    )
                    for key, expected in expected_facts.items():
                        if layer.get(key) != expected:
                            raise ValueError(f"partial D {key} mismatch")
                    continue

                if layer.get("status") != "complete":
                    raise ValueError(f"complete layer {name} status mismatch")
                expected_gfx_size = 4096 if name == "B" else None
                compressed_graphics, graphics = _load_lz(
                    rom,
                    pointers[0],
                    expected_size=expected_gfx_size,
                )
                compressed_tilemap, tilemap = _load_lz(
                    rom,
                    pointers[1],
                    expected_size=expected_map_size,
                )
                palette_offset = _offset(pointers[2], len(rom))
                palette_size = layout["palette_size"]
                palette = rom[
                    palette_offset : palette_offset + palette_size
                ]
                if len(palette) != palette_size:
                    raise ValueError("palette is truncated")
                _verify_component_manifest(
                    layer["gfx"],
                    pointer=pointers[0],
                    payload=graphics,
                    compressed_record=compressed_graphics,
                )
                _verify_component_manifest(
                    layer["tilemap"],
                    pointer=pointers[1],
                    payload=tilemap,
                    compressed_record=compressed_tilemap,
                )
                _verify_component_manifest(
                    layer["palette"],
                    pointer=pointers[2],
                    payload=palette,
                    compressed_record=None,
                )
                tile_count = len(graphics) // bytes_per_tile
                if layer.get("tile_count") != tile_count:
                    raise ValueError(f"layer {name} tile count mismatch")
                expected_facts = _tilemap_facts(
                    tilemap,
                    tile_count=tile_count,
                )
                for key, expected in expected_facts.items():
                    if layer.get(key) != expected:
                        raise ValueError(f"layer {name} {key} mismatch")

                layer_pixels = _render_tilemap(
                    graphics,
                    tilemap,
                    bits_per_pixel=bits_per_pixel,
                    width_tiles=width_tiles,
                    height_tiles=height_tiles,
                )
                layer_name = layer.get("layer_png")
                expected_layer_name = (
                    f"descriptor_{index:02d}_{name.lower()}.png"
                )
                if layer_name != expected_layer_name:
                    raise ValueError(f"layer {name} PNG name mismatch")
                _verify_png(
                    artifact_dir / layer_name,
                    pixels=layer_pixels,
                    palette=palette,
                    width=width_tiles * 8,
                    height=height_tiles * 8,
                    expected_sha256=layer["layer_png_sha256"],
                )

                atlas_pixels, atlas_width, atlas_height = _render_atlas(
                    graphics,
                    bits_per_pixel=bits_per_pixel,
                )
                graphics_hash = _sha256(graphics)
                palette_hash = _sha256(palette)
                atlas_pair = (
                    str(bits_per_pixel),
                    graphics_hash,
                    palette_hash,
                )
                expected_atlas = expected_atlas_by_pair.get(atlas_pair)
                if expected_atlas is None:
                    raise ValueError(
                        f"layer {name} atlas pair is missing from the ROM catalog"
                    )
                atlas_name = expected_atlas["png"]
                if layer.get("atlas_id") != expected_atlas["atlas_id"]:
                    raise ValueError(f"layer {name} atlas ID mismatch")
                if layer.get("atlas_png") != atlas_name:
                    raise ValueError(f"layer {name} atlas PNG name mismatch")
                if (
                    layer.get("atlas_png_sha256")
                    != expected_atlas["png_sha256"]
                ):
                    raise ValueError(f"layer {name} atlas PNG hash mismatch")
                expectation = (
                    atlas_pixels,
                    palette,
                    atlas_width,
                    atlas_height,
                    expected_atlas["png_sha256"],
                )
                if atlas_expectations.get(atlas_name) != expectation:
                    raise ValueError("reused atlas has conflicting ROM inputs")
                verified_complete_layers += 1
            verified_descriptors += 1
        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            struct.error,
        ) as error:
            errors.append(f"descriptor {index}: {error}")

    atlas_records = manifest.get("atlases")
    if not isinstance(atlas_records, list):
        errors.append("atlas index metadata is not a list")
        atlas_records = []
    if len(atlas_records) != len(expected_atlases):
        errors.append("atlas index metadata count mismatch")
    for index, expected in enumerate(expected_atlases):
        if index >= len(atlas_records) or atlas_records[index] != expected:
            errors.append(f"atlas {index} metadata mismatch")

    for atlas_name, expectation in sorted(atlas_expectations.items()):
        pixels, palette, width, height, png_hash = expectation
        try:
            _verify_png(
                artifact_dir / atlas_name,
                pixels=pixels,
                palette=palette,
                width=width,
                height=height,
                expected_sha256=png_hash,
            )
        except (OSError, TypeError, ValueError) as error:
            errors.append(f"atlas {atlas_name}: {error}")
        else:
            verified_atlases += 1

    return {
        "schema": "tile-assets-bg-verification-v2",
        "rom_sha256": rom_hash,
        "verified_descriptors": verified_descriptors,
        "verified_complete_layers": verified_complete_layers,
        "verified_atlases": verified_atlases,
        "errors": errors,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/tile-assets-bg-v2"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = verify_tile_asset_bg_export(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
