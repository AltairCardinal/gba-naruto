#!/usr/bin/env python3
"""Independently verify exported story visual layers against the ROM."""

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
TABLE_OFFSET = 0x54229C
TABLE_ENTRY_COUNT = 24
TABLE_ENTRY_SIZE = 0x10
TABLE_SHA256 = "33acbc117fa59c56d7af11728c6519367c9d5db177de75c199ec91c1c59ec289"
CHARACTER_BASE_LITERAL_OFFSET = 0x87DBC
GRAPHICS_DESTINATION_LITERAL_OFFSET = 0x87EF0
PALETTE_DESTINATION_LITERAL_OFFSET = 0x87EF4
TILEMAP_DESTINATION_LITERAL_OFFSET = 0x87EFC
CANVAS_WIDTH = 256
CANVAS_HEIGHT = 256
TILEMAP_SIZE = 32 * 32 * 2
PALETTE_SIZE = 16 * 2


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pointer_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer 0x{pointer:08X} is outside the ROM")
    return offset


def _render_indices(
    graphics: bytes,
    tilemap: bytes,
    *,
    tile_base: int,
) -> bytes:
    if not graphics or len(graphics) % 32:
        raise ValueError("graphics does not contain complete 4bpp tiles")
    if len(tilemap) != TILEMAP_SIZE:
        raise ValueError(f"tilemap size is {len(tilemap)}, expected {TILEMAP_SIZE}")

    tile_count = len(graphics) // 32
    entries = struct.unpack("<1024H", tilemap)
    pixels = bytearray(CANVAS_WIDTH * CANVAS_HEIGHT)
    for tile_y in range(32):
        for tile_x in range(32):
            entry = entries[tile_y * 32 + tile_x]
            if entry >> 12 != 15:
                raise ValueError(
                    f"tilemap entry uses palette bank {entry >> 12}, expected 15"
                )
            source_tile = (entry & 0x03FF) - tile_base
            if not 0 <= source_tile < tile_count:
                raise ValueError(
                    f"tilemap tile {entry & 0x03FF} is outside "
                    f"{tile_base}..{tile_base + tile_count - 1}"
                )
            horizontal_flip = bool(entry & (1 << 10))
            vertical_flip = bool(entry & (1 << 11))
            for local_y in range(8):
                source_y = 7 - local_y if vertical_flip else local_y
                destination_y = tile_y * 8 + local_y
                for local_x in range(8):
                    source_x = 7 - local_x if horizontal_flip else local_x
                    source = (
                        source_tile * 32
                        + source_y * 4
                        + source_x // 2
                    )
                    packed = graphics[source]
                    color = (
                        packed >> (4 if source_x & 1 else 0)
                    ) & 0x0F
                    destination_x = tile_x * 8 + local_x
                    pixels[
                        destination_y * CANVAS_WIDTH + destination_x
                    ] = color
    return bytes(pixels)


def _palette_rgb(palette: bytes) -> bytes:
    if len(palette) != PALETTE_SIZE:
        raise ValueError(
            f"palette size is {len(palette)}, expected {PALETTE_SIZE}"
        )
    rgb = bytearray()
    for offset in range(0, len(palette), 2):
        rgb.extend(
            bgr555_to_rgb(struct.unpack_from("<H", palette, offset)[0])
        )
    return bytes(rgb)


def _verify_layer(
    rom: bytes,
    artifact_dir: Path,
    layer: dict[str, Any],
    *,
    index: int,
    tile_base: int,
) -> str:
    descriptor_offset = TABLE_OFFSET + index * TABLE_ENTRY_SIZE
    gfx_pointer, palette_pointer, tilemap_pointer, config_id = (
        struct.unpack_from("<IIII", rom, descriptor_offset)
    )
    expected_descriptor = {
        "layer_id": index,
        "descriptor_file_offset": descriptor_offset,
        "descriptor_gba_address": f"0x{ROM_BASE + descriptor_offset:08X}",
        "config_id": config_id,
        "linked_visual_descriptor_id": config_id,
        "gfx_pointer": f"0x{gfx_pointer:08X}",
        "palette_pointer": f"0x{palette_pointer:08X}",
        "tilemap_pointer": f"0x{tilemap_pointer:08X}",
        "tile_base": tile_base,
    }
    for key, expected in expected_descriptor.items():
        if layer.get(key) != expected:
            raise ValueError(
                f"manifest {key} is {layer.get(key)!r}, expected {expected!r}"
            )

    components = (
        ("gfx", gfx_pointer, None),
        ("palette", palette_pointer, PALETTE_SIZE),
        ("tilemap", tilemap_pointer, TILEMAP_SIZE),
    )
    decompressed: dict[str, bytes] = {}
    for name, pointer, expected_size in components:
        offset = _pointer_offset(pointer, len(rom))
        payload = lz77_decompress(rom, offset)
        if expected_size is not None and len(payload) != expected_size:
            raise ValueError(
                f"{name} decompressed to {len(payload)}, "
                f"expected {expected_size}"
            )
        component_manifest = layer.get(name)
        if not isinstance(component_manifest, dict):
            raise ValueError(f"manifest {name} record is missing")
        if component_manifest.get("file_offset") != offset:
            raise ValueError(f"manifest {name} offset does not match the ROM")
        if component_manifest.get("decompressed_size") != len(payload):
            raise ValueError(f"manifest {name} size does not match the ROM")
        if component_manifest.get("decompressed_sha256") != _sha256(payload):
            raise ValueError(f"manifest {name} hash does not match the ROM")
        decompressed[name] = payload

    expected_pixels = _render_indices(
        decompressed["gfx"],
        decompressed["tilemap"],
        tile_base=tile_base,
    )
    filename = layer.get("png")
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise ValueError("manifest PNG name is missing or unsafe")
    png_path = artifact_dir / filename
    png_bytes = png_path.read_bytes()
    png_hash = _sha256(png_bytes)
    if layer.get("png_sha256") != png_hash:
        raise ValueError("manifest PNG hash does not match the file")

    with Image.open(png_path) as image:
        image.load()
        if image.mode != "P":
            raise ValueError(f"PNG mode is {image.mode}, expected P")
        if image.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
            raise ValueError(
                f"PNG size is {image.size}, expected "
                f"{(CANVAS_WIDTH, CANVAS_HEIGHT)}"
            )
        if image.info.get("transparency") != 0:
            raise ValueError("PNG transparent palette index is not 0")
        if image.tobytes() != expected_pixels:
            raise ValueError("PNG palette indices do not match ROM rendering")
        actual_palette = image.getpalette()
        if actual_palette is None:
            raise ValueError("PNG indexed palette is missing")
        if bytes(actual_palette[: 16 * 3]) != _palette_rgb(
            decompressed["palette"]
        ):
            raise ValueError("PNG palette does not match ROM BGR555 colors")
    return png_hash


def verify_story_visual_layer_export(
    root: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Return a standalone ROM-to-PNG verification report."""
    root = Path(root).resolve()
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = root / artifact_dir

    errors: list[str] = []
    verified_layers = 0
    png_hashes: set[str] = set()
    rom = (root / "rom/base.gba").read_bytes()
    rom_sha256 = _sha256(rom)
    manifest = json.loads(
        (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    )

    if rom_sha256 != ROM_SHA256:
        errors.append(
            f"ROM SHA-256 is {rom_sha256}, expected {ROM_SHA256}"
        )
    if manifest.get("schema") != "story-visual-layer-export-v1":
        errors.append("unexpected export manifest schema")
    if manifest.get("rom", {}).get("sha256") != rom_sha256:
        errors.append("manifest ROM hash does not match the ROM")

    table = rom[
        TABLE_OFFSET : TABLE_OFFSET + TABLE_ENTRY_COUNT * TABLE_ENTRY_SIZE
    ]
    if _sha256(table) != TABLE_SHA256:
        errors.append("story visual descriptor table hash mismatch")

    character_base = struct.unpack_from(
        "<I", rom, CHARACTER_BASE_LITERAL_OFFSET
    )[0]
    graphics_destination = struct.unpack_from(
        "<I", rom, GRAPHICS_DESTINATION_LITERAL_OFFSET
    )[0]
    palette_destination = struct.unpack_from(
        "<I", rom, PALETTE_DESTINATION_LITERAL_OFFSET
    )[0]
    tilemap_destination = struct.unpack_from(
        "<I", rom, TILEMAP_DESTINATION_LITERAL_OFFSET
    )[0]
    if (character_base, graphics_destination) != (
        0x0600C000,
        0x0600E800,
    ):
        errors.append("unexpected BG3 character or graphics destination")
    if palette_destination != 0x050001E0:
        errors.append("unexpected BG3 palette destination")
    if tilemap_destination != 0x06001800:
        errors.append("unexpected BG3 tilemap destination")
    if (
        graphics_destination < character_base
        or (graphics_destination - character_base) % 32
    ):
        errors.append("BG3 tile base cannot be derived from ROM literals")
        tile_base = -1
    else:
        tile_base = (graphics_destination - character_base) // 32

    layers = manifest.get("layers")
    if not isinstance(layers, list) or len(layers) != TABLE_ENTRY_COUNT:
        errors.append(
            f"manifest has {len(layers) if isinstance(layers, list) else 0} "
            f"layers, expected {TABLE_ENTRY_COUNT}"
        )
        layers = [] if not isinstance(layers, list) else layers

    for index, layer in enumerate(layers[:TABLE_ENTRY_COUNT]):
        if not isinstance(layer, dict):
            errors.append(f"layer {index}: manifest record is not an object")
            continue
        try:
            png_hash = _verify_layer(
                rom,
                artifact_dir,
                layer,
                index=index,
                tile_base=tile_base,
            )
        except (KeyError, OSError, TypeError, ValueError, struct.error) as error:
            errors.append(f"layer {index}: {error}")
        else:
            verified_layers += 1
            png_hashes.add(png_hash)

    return {
        "schema": "story-visual-layer-verification-v1",
        "rom_sha256": rom_sha256,
        "verified_layers": verified_layers,
        "unique_png_count": len(png_hashes),
        "errors": errors,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/story-visual-layers-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = verify_story_visual_layer_export(
        args.root,
        args.artifact_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
