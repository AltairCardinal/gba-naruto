#!/usr/bin/env python3
"""Independently verify the battle presentation glyph artifact."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
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
RUNTIME_PALETTE_SHA256 = (
    "91469795b385e7b06edde2a8fcba8d562ddf5c2bca69350e1dc7880974419981"
)
TABLES = {
    "messages": {
        "offset": MESSAGE_TABLE_OFFSET,
        "count": MESSAGE_COUNT,
        "size": 4,
        "sha256": "a58fee3bd11fd9db198f4c93faace06c268a1243870ce755aaf060f6b7acc877",
        "file": "source/message-pointer-table.bin",
    },
    "glyphs": {
        "offset": GLYPH_TABLE_OFFSET,
        "count": GLYPH_COUNT,
        "size": 4,
        "sha256": "1061b97ae8ec9006c2a4c7f235ec795df3d7e8a40cc6f2117e5e89d7e79e3770",
        "file": "source/glyph-pointer-table.bin",
    },
    "bindings": {
        "offset": BINDING_TABLE_OFFSET,
        "count": BINDING_COUNT,
        "size": BINDING_SIZE,
        "sha256": "8b5557e99d159b2b3ea1701bc0a15d0f2acc95f766003ec706263fc62a3719e8",
        "file": "source/message-glyph-binding-table.bin",
    },
}
CODE_SLICES = (
    ("glyph_preloader", 0x09812C, 0x09819C,
     "4827abc170644bda91140d48a597cd641df061faae15e40d6a83e4b9a29d74ed"),
    ("message_measure", 0x0981AC, 0x09822A,
     "05a03ba78a859cb91cabfb865d3c58c80601054f43def714318c2124df7a9f03"),
    ("glyph_display_consumer", 0x098EDC, 0x098FBA,
     "6af0b1e7ecb858590d4dc422e1b5833f661602ff6137a65518a09aff874a32bc"),
    ("message_renderer", 0x098290, 0x098418,
     "8d599b9b21b70c455b0acb85a916806697f916b0271b8a42a7c8013ed1196804"),
    ("message_selector", 0x099564, 0x099582,
     "835b54df161608218062de4ad9743101456988d29af8fd5c0de165d0b7ebaa47"),
    ("presentation_initializer", 0x0983B8, 0x098624,
     "7a7598a7edfef279bf745897ba5ea0f94e5361e2db84acee7a84a23f06a61422"),
    ("sprite_palette_attr2_writer", 0x063108, 0x063120,
     "3a8ba305e8ed98f95bda2f6e81361571db10e20f0c2158d99930573e4d24ba83"),
)
SCHEMA = "battle-presentation-glyphs-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _read_lz77(rom: bytes, offset: int) -> tuple[bytes, bytes]:
    if not 0 <= offset <= len(rom) - 4 or rom[offset] != 0x10:
        raise ValueError("invalid LZ77 source")
    declared = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    cursor = offset + 4
    output = bytearray()
    while len(output) < declared:
        if cursor >= len(rom):
            raise ValueError("truncated LZ77 flags")
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(output) >= declared:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ValueError("truncated LZ77 back-reference")
                length = (rom[cursor] >> 4) + 3
                distance = (
                    ((rom[cursor] & 0x0F) << 8) | rom[cursor + 1]
                ) + 1
                cursor += 2
                if distance > len(output) or len(output) + length > declared:
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


def _raster(graphics: bytes) -> bytes:
    if len(graphics) != 512:
        raise ValueError("glyph is not 512 bytes")
    pixels = bytearray(1024)
    for tile_id in range(16):
        tile = graphics[tile_id * 32 : (tile_id + 1) * 32]
        base_x = (tile_id % 4) * 8
        base_y = (tile_id // 4) * 8
        for y in range(8):
            for x in range(8):
                packed = tile[y * 4 + x // 2]
                pixels[(base_y + y) * 32 + base_x + x] = (
                    packed >> (4 if x & 1 else 0)
                ) & 15
    return bytes(pixels)


def _palette() -> list[int]:
    result: list[int] = []
    for value in range(16):
        result.extend([value * 17] * 3)
    return result + [0] * (768 - len(result))


def _runtime_palette(raw: bytes) -> list[int]:
    if len(raw) != RUNTIME_PALETTE_SIZE:
        raise ValueError("runtime palette size mismatch")
    result: list[int] = []
    for color in struct.unpack("<16H", raw):
        color &= 0x7FFF
        red = color & 0x1F
        green = (color >> 5) & 0x1F
        blue = (color >> 10) & 0x1F
        result.extend(
            (
                (red << 3) | (red >> 2),
                (green << 3) | (green >> 2),
                (blue << 3) | (blue >> 2),
            )
        )
    return result + [0] * (768 - len(result))


def _png(
    pixels: bytes,
    size: tuple[int, int],
    palette: list[int] | None = None,
    transparency: int | None = None,
) -> bytes:
    image = Image.frombytes("P", size, pixels)
    image.putpalette(palette if palette is not None else _palette())
    stream = io.BytesIO()
    image.save(
        stream,
        format="PNG",
        optimize=False,
        **({"transparency": transparency} if transparency is not None else {}),
    )
    return stream.getvalue()


def _table_metadata(item: dict[str, Any]) -> dict[str, Any]:
    size = item["count"] * item["size"]
    return {
        "file_offset": item["offset"],
        "gba_address": _address(ROM_BASE + item["offset"]),
        "gba_end": _address(ROM_BASE + item["offset"] + size),
        "entry_count": item["count"],
        "entry_size": item["size"],
        "sha256": item["sha256"],
        "raw_file": item["file"],
    }


def _expected(rom: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    files: dict[str, bytes] = {}
    table_bytes: dict[str, bytes] = {}
    for name, item in TABLES.items():
        size = item["count"] * item["size"]
        raw = rom[item["offset"] : item["offset"] + size]
        if len(raw) != size or _sha256(raw) != item["sha256"]:
            raise ValueError(f"{name} table mismatch")
        table_bytes[name] = raw
        files[item["file"]] = raw
    runtime_palette_raw = rom[
        RUNTIME_PALETTE_OFFSET : RUNTIME_PALETTE_OFFSET + RUNTIME_PALETTE_SIZE
    ]
    if _sha256(runtime_palette_raw) != RUNTIME_PALETTE_SHA256:
        raise ValueError("runtime palette mismatch")
    runtime_palette = _runtime_palette(runtime_palette_raw)
    files["source/runtime-palette.bin"] = runtime_palette_raw

    binding_table = table_bytes["bindings"]
    message_pointers = struct.unpack("<79I", table_bytes["messages"])
    messages: list[dict[str, Any]] = []
    bound: set[int] = set()
    empty = 0
    for message_id, pointer in enumerate(message_pointers):
        offset = pointer - ROM_BASE
        if not 0 <= offset < MESSAGE_TABLE_OFFSET:
            raise ValueError("message pointer outside expected source region")
        end = rom.find(b"\0", offset, MESSAGE_TABLE_OFFSET)
        if end < 0:
            raise ValueError("unterminated message")
        raw = rom[offset : end + 1]
        relative = f"messages/message-{message_id:03d}.bin"
        files[relative] = raw
        binding = binding_table[
            message_id * BINDING_SIZE : (message_id + 1) * BINDING_SIZE
        ]
        count = binding[0]
        if count > 8 or binding[9] != 0:
            raise ValueError("invalid binding")
        glyph_ids = list(binding[1 : 1 + count])
        if any(value != 0xFF and value >= GLYPH_COUNT for value in glyph_ids):
            raise ValueError("binding glyph ID outside table")
        bound.update(value for value in glyph_ids if value != 0xFF)
        empty += int(count == 0)
        messages.append(
            {
                "message_id": message_id,
                "pointer": _address(pointer),
                "file_offset": offset,
                "raw_file": relative,
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

    glyph_pointers = struct.unpack("<172I", table_bytes["glyphs"])
    glyphs: list[dict[str, Any]] = []
    atlas = bytearray(512 * 352)
    unique: set[str] = set()
    for glyph_id, pointer in enumerate(glyph_pointers):
        offset = pointer - ROM_BASE
        if not 0 <= offset < len(rom):
            raise ValueError("glyph pointer outside ROM")
        compressed, graphics = _read_lz77(rom, offset)
        raster = _raster(graphics)
        compressed_file = f"glyphs/glyph-{glyph_id:03d}.lz77"
        graphics_file = f"glyphs/glyph-{glyph_id:03d}.4bpp"
        png_file = f"glyphs/glyph-{glyph_id:03d}.png"
        runtime_png_file = f"glyphs/glyph-{glyph_id:03d}.runtime.png"
        png = _png(raster, (32, 32))
        runtime_png = _png(
            raster, (32, 32), runtime_palette, transparency=0
        )
        files[compressed_file] = compressed
        files[graphics_file] = graphics
        files[png_file] = png
        files[runtime_png_file] = runtime_png
        atlas_x = (glyph_id % 16) * 32
        atlas_y = (glyph_id // 16) * 32
        for y in range(32):
            atlas[(atlas_y + y) * 512 + atlas_x :
                  (atlas_y + y) * 512 + atlas_x + 32] = raster[y * 32:(y + 1) * 32]
        graphics_hash = _sha256(graphics)
        unique.add(graphics_hash)
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
                "graphics_sha256": graphics_hash,
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
                    item["message_id"]
                    for item in messages
                    if glyph_id in item["binding"]["glyph_ids"]
                ],
            }
        )

    atlas_png = _png(bytes(atlas), (512, 352))
    runtime_atlas_png = _png(
        bytes(atlas), (512, 352), runtime_palette, transparency=0
    )
    files["glyph-atlas.png"] = atlas_png
    files["glyph-atlas-runtime.png"] = runtime_atlas_png
    code_slices = []
    for name, start, end, expected_hash in CODE_SLICES:
        if _sha256(rom[start:end]) != expected_hash:
            raise ValueError(f"{name} code slice mismatch")
        code_slices.append(
            {
                "name": name,
                "file_offset": start,
                "gba_start": _address(ROM_BASE + start),
                "gba_end": _address(ROM_BASE + end),
                "sha256": expected_hash,
            }
        )
    manifest = {
        "schema": SCHEMA,
        "rom": {"file": "rom/base.gba", "sha256": ROM_SHA256},
        "tables": {name: _table_metadata(item) for name, item in TABLES.items()},
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
            "raw_file": "source/runtime-palette.bin",
            "palette_bank": 13,
            "obj_palette_destination": "0x050003A0",
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
            "unique_glyph_count": len(unique),
            "bound_glyph_count": len(bound),
            "unbound_glyph_count": GLYPH_COUNT - len(bound),
            "empty_binding_count": empty,
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
    return manifest, files


def verify_artifact(root: Path, artifact_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        root = Path(root).resolve()
        artifact_dir = Path(artifact_dir).resolve()
        rom = (root / "rom" / "base.gba").read_bytes()
        if _sha256(rom) != ROM_SHA256:
            errors.append("ROM SHA-256 mismatch")
        expected_manifest, expected_files = _expected(rom)
        manifest_path = artifact_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest != expected_manifest:
            errors.append("manifest does not match independently derived ROM metadata")
        expected_names = set(expected_files) | {"manifest.json"}
        actual_names = {
            path.relative_to(artifact_dir).as_posix()
            for path in artifact_dir.rglob("*")
            if path.is_file()
        }
        if actual_names != expected_names:
            errors.append("artifact file set mismatch")
        for relative, expected in expected_files.items():
            path = artifact_dir / relative
            if not path.is_file():
                continue
            actual = path.read_bytes()
            if actual != expected:
                errors.append(f"{relative}: content mismatch")
        for glyph in expected_manifest["glyphs"]:
            for key, palette in (
                ("png_file", _palette()),
                ("runtime_png_file", _runtime_palette(
                    rom[
                        RUNTIME_PALETTE_OFFSET :
                        RUNTIME_PALETTE_OFFSET + RUNTIME_PALETTE_SIZE
                    ]
                )),
            ):
                path = artifact_dir / glyph[key]
                if not path.is_file():
                    continue
                try:
                    with Image.open(path) as image:
                        image.load()
                        if image.mode != "P" or image.size != (32, 32):
                            errors.append(f"{glyph[key]}: invalid image format")
                        if image.getpalette() != palette:
                            errors.append(f"{glyph[key]}: palette mismatch")
                        expected_transparency = (
                            0 if key == "runtime_png_file" else None
                        )
                        if image.info.get("transparency") != expected_transparency:
                            errors.append(
                                f"{glyph[key]}: transparency mismatch"
                            )
                except Exception as exc:
                    errors.append(f"{glyph[key]}: {exc}")
    except Exception as exc:
        errors.append(str(exc))
    return {
        "schema": "battle-presentation-glyph-verification-v1",
        "verified": not errors,
        "errors": errors,
        "messages": MESSAGE_COUNT if not errors else 0,
        "glyphs": GLYPH_COUNT if not errors else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the battle presentation glyph artifact"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/battle-presentation-glyphs-v1"),
    )
    args = parser.parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
