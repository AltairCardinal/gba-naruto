#!/usr/bin/env python3
"""Export the consumer-defined battle presentation text/glyph tables."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import struct
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
MESSAGE_TABLE_OFFSET = 0x5A2B08
MESSAGE_COUNT = 79
GLYPH_TABLE_OFFSET = 0x5A2C44
GLYPH_COUNT = 172
BINDING_TABLE_OFFSET = 0x5A2EF4
BINDING_COUNT = 79
BINDING_SIZE = 10
RUNTIME_PALETTE_OFFSET = 0x3E4AF0
RUNTIME_PALETTE_SIZE = 32
RUNTIME_PALETTE_BANK = 13
OBJ_PALETTE_BASE = 0x05000200
MESSAGE_TABLE_SHA256 = (
    "a58fee3bd11fd9db198f4c93faace06c268a1243870ce755aaf060f6b7acc877"
)
GLYPH_TABLE_SHA256 = (
    "1061b97ae8ec9006c2a4c7f235ec795df3d7e8a40cc6f2117e5e89d7e79e3770"
)
BINDING_TABLE_SHA256 = (
    "8b5557e99d159b2b3ea1701bc0a15d0f2acc95f766003ec706263fc62a3719e8"
)
RUNTIME_PALETTE_SHA256 = (
    "91469795b385e7b06edde2a8fcba8d562ddf5c2bca69350e1dc7880974419981"
)
SCHEMA = "battle-presentation-glyphs-v1"
CODE_SLICES = (
    {
        "name": "glyph_preloader",
        "file_offset": 0x09812C,
        "gba_start": "0x0809812C",
        "gba_end": "0x0809819C",
        "sha256": "4827abc170644bda91140d48a597cd641df061faae15e40d6a83e4b9a29d74ed",
    },
    {
        "name": "message_measure",
        "file_offset": 0x0981AC,
        "gba_start": "0x080981AC",
        "gba_end": "0x0809822A",
        "sha256": "05a03ba78a859cb91cabfb865d3c58c80601054f43def714318c2124df7a9f03",
    },
    {
        "name": "glyph_display_consumer",
        "file_offset": 0x098EDC,
        "gba_start": "0x08098EDC",
        "gba_end": "0x08098FBA",
        "sha256": "6af0b1e7ecb858590d4dc422e1b5833f661602ff6137a65518a09aff874a32bc",
    },
    {
        "name": "message_renderer",
        "file_offset": 0x098290,
        "gba_start": "0x08098290",
        "gba_end": "0x08098418",
        "sha256": "8d599b9b21b70c455b0acb85a916806697f916b0271b8a42a7c8013ed1196804",
    },
    {
        "name": "message_selector",
        "file_offset": 0x099564,
        "gba_start": "0x08099564",
        "gba_end": "0x08099582",
        "sha256": "835b54df161608218062de4ad9743101456988d29af8fd5c0de165d0b7ebaa47",
    },
    {
        "name": "presentation_initializer",
        "file_offset": 0x0983B8,
        "gba_start": "0x080983B8",
        "gba_end": "0x08098624",
        "sha256": "7a7598a7edfef279bf745897ba5ea0f94e5361e2db84acee7a84a23f06a61422",
    },
    {
        "name": "sprite_palette_attr2_writer",
        "file_offset": 0x063108,
        "gba_start": "0x08063108",
        "gba_end": "0x08063120",
        "sha256": "3a8ba305e8ed98f95bda2f6e81361571db10e20f0c2158d99930573e4d24ba83",
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


def _read_lz77(rom: bytes, offset: int) -> tuple[bytes, bytes]:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError(f"resource is not GBA LZ77 at 0x{offset:06X}")
    output_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    output = bytearray()
    cursor = offset + 4
    while len(output) < output_size:
        if cursor >= len(rom):
            raise ValueError("truncated LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= output_size:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated LZ77 back-reference")
                first = rom[cursor]
                second = rom[cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                distance = ((first & 0x0F) << 8) + second + 1
                if distance > len(output) or len(output) + length > output_size:
                    raise ValueError("invalid LZ77 back-reference")
                source = len(output) - distance
                for _ in range(length):
                    output.append(output[source])
                    source += 1
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated LZ77 literal")
                output.append(rom[cursor])
                cursor += 1
    return rom[offset:cursor], bytes(output)


def _glyph_raster(graphics: bytes) -> bytes:
    if len(graphics) != 512:
        raise ValueError(f"glyph graphics must be 512 bytes, got {len(graphics)}")
    pixels = bytearray(32 * 32)
    for tile_id in range(16):
        tile_x = (tile_id % 4) * 8
        tile_y = (tile_id // 4) * 8
        tile = graphics[tile_id * 32 : (tile_id + 1) * 32]
        for y in range(8):
            for x in range(8):
                packed = tile[y * 4 + x // 2]
                pixels[(tile_y + y) * 32 + tile_x + x] = (
                    packed >> (4 if x & 1 else 0)
                ) & 0x0F
    return bytes(pixels)


def _diagnostic_palette() -> list[int]:
    palette: list[int] = []
    for value in range(16):
        channel = value * 17
        palette.extend((channel, channel, channel))
    palette.extend([0] * (768 - len(palette)))
    return palette


def _runtime_palette(raw: bytes) -> list[int]:
    if len(raw) != RUNTIME_PALETTE_SIZE:
        raise ValueError("runtime palette must contain 16 BGR555 colors")
    palette: list[int] = []
    for color in struct.unpack("<16H", raw):
        color &= 0x7FFF
        red = color & 0x1F
        green = (color >> 5) & 0x1F
        blue = (color >> 10) & 0x1F
        palette.extend(
            (
                (red << 3) | (red >> 2),
                (green << 3) | (green >> 2),
                (blue << 3) | (blue >> 2),
            )
        )
    palette.extend([0] * (768 - len(palette)))
    return palette


def _png_bytes(
    pixels: bytes,
    size: tuple[int, int],
    palette: list[int] | None = None,
    transparency: int | None = None,
) -> bytes:
    image = Image.frombytes("P", size, pixels)
    image.putpalette(palette if palette is not None else _diagnostic_palette())
    output = io.BytesIO()
    image.save(
        output,
        format="PNG",
        optimize=False,
        **({"transparency": transparency} if transparency is not None else {}),
    )
    return output.getvalue()


def _table_metadata(
    offset: int,
    entry_count: int,
    entry_size: int,
    sha256: str,
    raw_file: str,
) -> dict[str, Any]:
    size = entry_count * entry_size
    return {
        "file_offset": offset,
        "gba_address": _address(ROM_BASE + offset),
        "gba_end": _address(ROM_BASE + offset + size),
        "entry_count": entry_count,
        "entry_size": entry_size,
        "sha256": sha256,
        "raw_file": raw_file,
    }


def _build_artifact(rom: bytes, output: Path) -> dict[str, Any]:
    if _sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")
    message_table = rom[
        MESSAGE_TABLE_OFFSET : MESSAGE_TABLE_OFFSET + MESSAGE_COUNT * 4
    ]
    glyph_table = rom[
        GLYPH_TABLE_OFFSET : GLYPH_TABLE_OFFSET + GLYPH_COUNT * 4
    ]
    binding_table = rom[
        BINDING_TABLE_OFFSET :
        BINDING_TABLE_OFFSET + BINDING_COUNT * BINDING_SIZE
    ]
    for label, data, expected in (
        ("message table", message_table, MESSAGE_TABLE_SHA256),
        ("glyph table", glyph_table, GLYPH_TABLE_SHA256),
        ("binding table", binding_table, BINDING_TABLE_SHA256),
    ):
        if _sha256(data) != expected:
            raise ValueError(f"{label} SHA-256 mismatch")
    runtime_palette_raw = rom[
        RUNTIME_PALETTE_OFFSET : RUNTIME_PALETTE_OFFSET + RUNTIME_PALETTE_SIZE
    ]
    if _sha256(runtime_palette_raw) != RUNTIME_PALETTE_SHA256:
        raise ValueError("runtime palette SHA-256 mismatch")
    runtime_palette = _runtime_palette(runtime_palette_raw)

    (output / "source").mkdir(parents=True)
    (output / "messages").mkdir()
    (output / "glyphs").mkdir()
    source_files = (
        ("source/message-pointer-table.bin", message_table),
        ("source/glyph-pointer-table.bin", glyph_table),
        ("source/message-glyph-binding-table.bin", binding_table),
        ("source/runtime-palette.bin", runtime_palette_raw),
    )
    for relative, data in source_files:
        (output / relative).write_bytes(data)

    message_pointers = struct.unpack("<79I", message_table)
    messages: list[dict[str, Any]] = []
    bound_glyphs: set[int] = set()
    empty_binding_count = 0
    for message_id, pointer in enumerate(message_pointers):
        offset = _rom_offset(pointer, len(rom))
        end = rom.find(b"\0", offset, MESSAGE_TABLE_OFFSET)
        if end < 0:
            raise ValueError(f"message {message_id} is not NUL terminated")
        raw = rom[offset : end + 1]
        raw_file = f"messages/message-{message_id:03d}.bin"
        (output / raw_file).write_bytes(raw)

        binding = binding_table[
            message_id * BINDING_SIZE : (message_id + 1) * BINDING_SIZE
        ]
        count = binding[0]
        if count > 8 or binding[9] != 0:
            raise ValueError(f"invalid binding record {message_id}")
        glyph_ids = list(binding[1 : 1 + count])
        for glyph_id in glyph_ids:
            if glyph_id != 0xFF:
                if glyph_id >= GLYPH_COUNT:
                    raise ValueError(f"binding {message_id} has invalid glyph ID")
                bound_glyphs.add(glyph_id)
        empty_binding_count += int(count == 0)
        messages.append(
            {
                "message_id": message_id,
                "pointer": _address(pointer),
                "file_offset": offset,
                "raw_file": raw_file,
                "raw_size": len(raw),
                "raw_sha256": _sha256(raw),
                "raw_hex": raw.hex(),
                "binding": {
                    "file_offset": BINDING_TABLE_OFFSET + message_id * BINDING_SIZE,
                    "gba_address": _address(
                        ROM_BASE + BINDING_TABLE_OFFSET
                        + message_id * BINDING_SIZE
                    ),
                    "raw_size": BINDING_SIZE,
                    "raw_hex": binding.hex(),
                    "glyph_count": count,
                    "glyph_ids": glyph_ids,
                },
            }
        )

    glyph_pointers = struct.unpack("<172I", glyph_table)
    glyphs: list[dict[str, Any]] = []
    atlas_pixels = bytearray(512 * 352)
    unique_graphics: set[str] = set()
    for glyph_id, pointer in enumerate(glyph_pointers):
        offset = _rom_offset(pointer, len(rom))
        compressed, graphics = _read_lz77(rom, offset)
        if len(graphics) != 512:
            raise ValueError(f"glyph {glyph_id} has unexpected size")
        raster = _glyph_raster(graphics)
        compressed_file = f"glyphs/glyph-{glyph_id:03d}.lz77"
        graphics_file = f"glyphs/glyph-{glyph_id:03d}.4bpp"
        png_file = f"glyphs/glyph-{glyph_id:03d}.png"
        runtime_png_file = f"glyphs/glyph-{glyph_id:03d}.runtime.png"
        png = _png_bytes(raster, (32, 32))
        runtime_png = _png_bytes(
            raster, (32, 32), runtime_palette, transparency=0
        )
        (output / compressed_file).write_bytes(compressed)
        (output / graphics_file).write_bytes(graphics)
        (output / png_file).write_bytes(png)
        (output / runtime_png_file).write_bytes(runtime_png)
        atlas_x = (glyph_id % 16) * 32
        atlas_y = (glyph_id // 16) * 32
        for y in range(32):
            start = y * 32
            target = (atlas_y + y) * 512 + atlas_x
            atlas_pixels[target : target + 32] = raster[start : start + 32]
        graphics_sha256 = _sha256(graphics)
        unique_graphics.add(graphics_sha256)
        glyphs.append(
            {
                "glyph_id": glyph_id,
                "pointer": _address(pointer),
                "file_offset": offset,
                "compressed_file": compressed_file,
                "compressed_size": len(compressed),
                "compressed_sha256": _sha256(compressed),
                "graphics_file": graphics_file,
                "graphics_size": len(graphics),
                "graphics_sha256": graphics_sha256,
                "tile_count": 16,
                "pixel_mode": "4bpp",
                "width": 32,
                "height": 32,
                "raster_sha256": _sha256(raster),
                "maximum_palette_index": max(raster),
                "png_file": png_file,
                "png_sha256": _sha256(png),
                "runtime_png_file": runtime_png_file,
                "runtime_png_sha256": _sha256(runtime_png),
                "bound_message_ids": [
                    message["message_id"]
                    for message in messages
                    if glyph_id in message["binding"]["glyph_ids"]
                ],
            }
        )

    atlas_png = _png_bytes(bytes(atlas_pixels), (512, 352))
    runtime_atlas_png = _png_bytes(
        bytes(atlas_pixels), (512, 352), runtime_palette, transparency=0
    )
    (output / "glyph-atlas.png").write_bytes(atlas_png)
    (output / "glyph-atlas-runtime.png").write_bytes(runtime_atlas_png)
    code_slices = []
    for item in CODE_SLICES:
        start = item["file_offset"]
        end = int(item["gba_end"], 16) - ROM_BASE
        if _sha256(rom[start:end]) != item["sha256"]:
            raise ValueError(f"{item['name']} code SHA-256 mismatch")
        code_slices.append(dict(item))

    manifest = {
        "schema": SCHEMA,
        "rom": {"file": "rom/base.gba", "sha256": ROM_SHA256},
        "tables": {
            "messages": _table_metadata(
                MESSAGE_TABLE_OFFSET, MESSAGE_COUNT, 4,
                MESSAGE_TABLE_SHA256, source_files[0][0]
            ),
            "glyphs": _table_metadata(
                GLYPH_TABLE_OFFSET, GLYPH_COUNT, 4,
                GLYPH_TABLE_SHA256, source_files[1][0]
            ),
            "bindings": _table_metadata(
                BINDING_TABLE_OFFSET, BINDING_COUNT, BINDING_SIZE,
                BINDING_TABLE_SHA256, source_files[2][0]
            ),
        },
        "consumer": {
            "code_slices": code_slices,
            "selection": {
                "message_selector_literal": "0x080995E0",
                "message_selector_formula": (
                    "message_ptr = u32[0x085A2B08 + u8(message_id) * 4]"
                ),
                "glyph_table_literal": "0x080981A8",
                "binding_table_literals": [
                    "0x080981A4",
                    "0x08098FC4",
                ],
                "binding_formula": (
                    "binding = 0x085A2EF4 + u8(message_id) * 10"
                ),
                "glyph_formula": (
                    "glyph_stream = u32[0x085A2C44 + glyph_id * 4]"
                ),
                "display_formula": (
                    "glyph_id = binding[1 + display_slot]"
                ),
                "glyph_destination_stride": 512,
                "skip_glyph_id": 255,
                "bounds_check": False,
            },
            "palette_selection": {
                "palette_source_literal": "0x0809861C",
                "obj_palette_base_literal": "0x08098620",
                "palette_bank_assignment": "state[0x0F] = 13",
                "copy_formula": (
                    "CpuSet(0x083E4AF0, 0x05000200 + 13 * 32, 16 colors)"
                ),
                "display_palette_formula": (
                    "sprite_palette_bank = state[0x0F]"
                ),
                "attr2_palette_formula": (
                    "OAM.attr2[12:15] = sprite_task[0x12] << 12"
                ),
            },
        },
        "runtime_palette": {
            "file_offset": RUNTIME_PALETTE_OFFSET,
            "gba_address": _address(ROM_BASE + RUNTIME_PALETTE_OFFSET),
            "size": RUNTIME_PALETTE_SIZE,
            "color_count": 16,
            "format": "BGR555",
            "sha256": RUNTIME_PALETTE_SHA256,
            "raw_file": source_files[3][0],
            "palette_bank": RUNTIME_PALETTE_BANK,
            "obj_palette_destination": _address(
                OBJ_PALETTE_BASE + RUNTIME_PALETTE_BANK * 32
            ),
            "transparent_palette_index": 0,
        },
        "messages": messages,
        "glyphs": glyphs,
        "atlas": {
            "png_file": "glyph-atlas.png",
            "png_sha256": _sha256(atlas_png),
            "runtime_png_file": "glyph-atlas-runtime.png",
            "runtime_png_sha256": _sha256(runtime_atlas_png),
            "width": 512,
            "height": 352,
            "columns": 16,
            "rows": 11,
            "diagnostic_palette": True,
        },
        "summary": {
            "message_count": MESSAGE_COUNT,
            "glyph_count": GLYPH_COUNT,
            "unique_glyph_count": len(unique_graphics),
            "bound_glyph_count": len(bound_glyphs),
            "unbound_glyph_count": GLYPH_COUNT - len(bound_glyphs),
            "empty_binding_count": empty_binding_count,
        },
        "scope": {
            "all_static_messages_exported": True,
            "all_static_glyphs_exported": True,
            "all_static_bindings_exported": True,
            "glyph_geometry_static_verified": True,
            "message_character_decoding_complete": False,
            "runtime_palette_binding_complete": True,
            "message_names_complete": False,
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def export_artifact(root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent)
    )
    backup: Path | None = None
    try:
        manifest = _build_artifact(
            (root / "rom" / "base.gba").read_bytes(), temporary
        )
        if output_dir.exists():
            backup = Path(
                tempfile.mkdtemp(
                    prefix=f".{output_dir.name}-backup.",
                    dir=output_dir.parent,
                )
            )
            backup.rmdir()
            os.replace(output_dir, backup)
        try:
            os.replace(temporary, output_dir)
        except Exception:
            if backup is not None:
                os.replace(backup, output_dir)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
        return manifest
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export battle presentation messages and 32x32 glyph chunks"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/battle-presentation-glyphs-v1"),
    )
    args = parser.parse_args()
    manifest = export_artifact(args.root, args.output_dir)
    print(
        f"exported {manifest['summary']['message_count']} messages and "
        f"{manifest['summary']['glyph_count']} glyphs to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
