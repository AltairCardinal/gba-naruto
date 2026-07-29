#!/usr/bin/env python3
"""Independently verify cutscene OBJ artifacts against the source ROM."""

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
RESOURCE_TABLE_OFFSET = 0x53DF70
SPRITE_TABLE_OFFSET = 0x53DF90
ENTRY_COUNT = 4
ENTRY_SIZE = 8
RESOURCE_TABLE_SHA256 = (
    "16b13c432f37ba159697cd9d9d6d5d5147adc41c44c8cc0cc44ce7f2935f1401"
)
SPRITE_TABLE_SHA256 = (
    "1c76f2100b2067e78abd713e312bd845d7c874b030f51ef08f968961862e198a"
)
COMBINED_TABLE_SHA256 = (
    "1e6d5016b58d0e565c5a40791a7f2684d6129e0a1c4e85e79317af4d2b1a7f62"
)
EXPECTED_GFX_SHA256 = (
    "ff3e1b090a18378eb51b2c25ad7e9115ea33d6c9afe11ceeb09cbd392a5496c5",
    "1494d4db49423aaf026f3a1d45df4a63c70db9a0c6c7bae72621f7f7688bae0d",
    "ff180630c246cf7c9e161576b33c0e734157a2a927c07be6bc90a80619654079",
    "d2b44e9c68dc23771249bedfb7397de35f19e6769f99a91f86512b7604b43ec1",
)
EXPECTED_PALETTE_SHA256 = (
    "99d45ddc5929d60c150146f1292cd55f56d89afbff70ffd0f377128fe75352af"
)
DEFINITION_RECORD_SIZE = 24
ANIMATION_RECORD_SIZE = 8
ATLAS_TILES_PER_ROW = 16

EXPECTED_CONSUMER = {
    "loader_gba_address": "0x08072EDC",
    "resource_index_gba_address": "0x08072F0C",
    "sprite_allocator_gba_address": "0x080625A4",
    "sprite_index_gba_address": "0x08062668",
    "gfx_destination": "0x06016000",
    "palette_destination": "0x05000380",
    "direct_resource_ids": [0, 1, 2, 3],
}
EXPECTED_SCOPE = {
    "kind": "static 4bpp OBJ atlases and definition-backed frames",
    "final_runtime_sequence": False,
    "animation_timing_interpreted": True,
    "palette_index_zero_transparent": True,
}
ANIMATION_RUNTIME = {
    "loader_requested_flags": "0x00000008",
    "allocator_active_bit": "0x00000001",
    "initial_task_flags": "0x00000009",
    "termination_policy_bits": "0x00",
    "timer_storage": "u16",
    "timer_initial": 0,
    "timer_increment_per_update": 1,
    "duration_compare": "duration_ticks == timer_after_increment",
    "zero_duration_first_expiry_updates": 65536,
    "terminator_frame_index": -1,
    "terminator_policy": "deactivate_task",
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


def _pointer(pointer: int) -> str:
    return f"0x{pointer:08X}"


def _offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer {_pointer(pointer)} is outside the ROM")
    return offset


def _read_lz_record(rom: bytes, offset: int) -> bytes:
    if offset < 0 or offset + 4 > len(rom) or rom[offset] != 0x10:
        raise ValueError("resource is not a GBA type-0x10 LZ stream")
    expected_size = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    if expected_size <= 0:
        raise ValueError("LZ stream declares an empty payload")
    cursor = offset + 4
    produced = 0
    while produced < expected_size:
        if cursor >= len(rom):
            raise ValueError("LZ flag byte is truncated")
        flags = rom[cursor]
        cursor += 1
        for bit in range(8):
            if produced >= expected_size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(rom):
                    raise ValueError("LZ back-reference is truncated")
                first = rom[cursor]
                second = rom[cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                displacement = ((first & 0x0F) << 8 | second) + 1
                if displacement > produced:
                    raise ValueError("LZ back-reference is invalid")
            else:
                if cursor >= len(rom):
                    raise ValueError("LZ literal is truncated")
                cursor += 1
                length = 1
            if produced + length > expected_size:
                raise ValueError("LZ record overruns its declared size")
            produced += length
    return rom[offset:cursor]


def _decode_lz_record(record: bytes) -> bytes:
    if len(record) < 5 or record[0] != 0x10:
        raise ValueError("record is not a GBA type-0x10 LZ stream")
    expected_size = int.from_bytes(record[1:4], "little")
    if expected_size <= 0:
        raise ValueError("LZ stream declares an empty payload")
    cursor = 4
    output = bytearray()
    while len(output) < expected_size:
        if cursor >= len(record):
            raise ValueError("LZ flag byte is truncated")
        flags = record[cursor]
        cursor += 1
        for bit in range(8):
            if len(output) >= expected_size:
                break
            if flags & (0x80 >> bit):
                if cursor + 2 > len(record):
                    raise ValueError("LZ back-reference is truncated")
                first = record[cursor]
                second = record[cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                displacement = ((first & 0x0F) << 8 | second) + 1
                if displacement > len(output):
                    raise ValueError("LZ back-reference is invalid")
                if len(output) + length > expected_size:
                    raise ValueError("LZ output overruns its declared size")
                for _ in range(length):
                    output.append(output[-displacement])
            else:
                if cursor >= len(record):
                    raise ValueError("LZ literal is truncated")
                output.append(record[cursor])
                cursor += 1
    if cursor != len(record):
        raise ValueError("LZ record contains trailing bytes")
    return bytes(output)


def _load_lz(
    rom: bytes,
    pointer: int,
    *,
    expected_size: int | None = None,
) -> tuple[bytes, bytes, dict[str, Any]]:
    offset = _offset(pointer, len(rom))
    compressed = _read_lz_record(rom, offset)
    payload = _decode_lz_record(compressed)
    if expected_size is not None and len(payload) != expected_size:
        raise ValueError(
            f"{_pointer(pointer)} decompressed to {len(payload)}, "
            f"expected {expected_size}"
        )
    return compressed, payload, {
        "file_offset": offset,
        "gba_address": _pointer(pointer),
        "compressed_size": len(compressed),
        "compressed_sha256": _sha256(compressed),
        "decompressed_size": len(payload),
        "decompressed_sha256": _sha256(payload),
    }


def _render_block(
    graphics: bytes,
    *,
    tile_offset: int,
    width_tiles: int,
    height_tiles: int,
) -> bytes:
    if width_tiles <= 0 or height_tiles <= 0:
        raise ValueError("tile-block dimensions are invalid")
    tile_count = width_tiles * height_tiles
    if tile_offset < 0 or tile_offset + tile_count > len(graphics) // 32:
        raise ValueError("tile block exceeds the graphics payload")
    width = width_tiles * 8
    pixels = bytearray(width * height_tiles * 8)
    for relative_tile in range(tile_count):
        source_tile = tile_offset + relative_tile
        tile_x = relative_tile % width_tiles
        tile_y = relative_tile // width_tiles
        for local_y in range(8):
            for local_x in range(8):
                packed = graphics[
                    source_tile * 32 + local_y * 4 + local_x // 2
                ]
                pixels[
                    (tile_y * 8 + local_y) * width
                    + tile_x * 8
                    + local_x
                ] = (packed >> (4 if local_x & 1 else 0)) & 0x0F
    return bytes(pixels)


def _render_atlas(graphics: bytes) -> tuple[bytes, int, int]:
    if not graphics or len(graphics) % 32:
        raise ValueError("graphics does not contain complete 4bpp tiles")
    tile_count = len(graphics) // 32
    columns = min(tile_count, ATLAS_TILES_PER_ROW)
    rows = (tile_count + ATLAS_TILES_PER_ROW - 1) // ATLAS_TILES_PER_ROW
    return (
        _render_block(
            graphics,
            tile_offset=0,
            width_tiles=columns,
            height_tiles=rows,
        ),
        columns * 8,
        rows * 8,
    )


def _palette_rgb(palette: bytes) -> bytes:
    if len(palette) != 32:
        raise ValueError("OBJ palette is not exactly 16 colors")
    result = bytearray()
    for offset in range(0, 32, 2):
        color = struct.unpack_from("<H", palette, offset)[0] & 0x7FFF
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
    return bytes(result)


def _verify_png(
    path: Path,
    *,
    pixels: bytes,
    palette: bytes,
    width: int,
    height: int,
) -> str:
    png = path.read_bytes()
    with Image.open(path) as image:
        image.load()
        if image.mode != "P":
            raise ValueError(f"{path.name} is not indexed")
        if image.size != (width, height):
            raise ValueError(f"{path.name} has the wrong dimensions")
        if image.info.get("transparency") != 0:
            raise ValueError(f"{path.name} transparent index is not zero")
        if image.tobytes() != pixels:
            raise ValueError(f"{path.name} pixels do not match the ROM")
        png_palette = image.getpalette()
        if png_palette is None:
            raise ValueError(f"{path.name} has no palette")
        if bytes(png_palette[:48]) != _palette_rgb(palette):
            raise ValueError(f"{path.name} palette does not match the ROM")
    return _sha256(png)


def _verify_consumer_literals(rom: bytes) -> None:
    if rom[0x72F0C:0x72F26].hex() != (
        "0b4c4046c500281900680a4929f0e6f804342d192868084929f0"
    ):
        raise ValueError("resource-index consumer bytes changed")
    literals = (
        (0x72F3C, 0x0853DF70),
        (0x72F40, 0x06016000),
        (0x72F44, 0x05000380),
        (0x72FC8, 0x0853DF90),
    )
    for offset, expected in literals:
        if struct.unpack_from("<I", rom, offset)[0] != expected:
            raise ValueError(f"consumer literal at 0x{offset:06X} changed")
    if rom[0x62668:0x62676].hex() != "f800009940180168e16140682062":
        raise ValueError("sprite-index consumer bytes changed")
    direct_callers = {
        0x73100: "0120fff7ecfe",
        0x7314A: "0220fff7c7fe",
        0x73196: "0320fff7a1fe",
        0x7363A: "0020fff74ffc",
    }
    for call_offset, expected_hex in direct_callers.items():
        if rom[call_offset - 2 : call_offset + 4].hex() != expected_hex:
            raise ValueError(
                f"direct resource-ID caller at 0x{call_offset:06X} changed"
            )


def verify_cutscene_obj_export(
    root: Path,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Return an independent ROM-to-artifact verification report."""
    root = Path(root).resolve()
    artifact_dir = Path(artifact_dir)
    if not artifact_dir.is_absolute():
        artifact_dir = root / artifact_dir

    errors: list[str] = []
    verified_resources = 0
    verified_frames = 0
    verified_animations = 0
    verified_atlases = 0
    expected_files = {"manifest.json"}
    rom = (root / "rom/base.gba").read_bytes()
    rom_hash = _sha256(rom)
    manifest = json.loads(
        (artifact_dir / "manifest.json").read_text(encoding="utf-8")
    )

    if rom_hash != ROM_SHA256:
        errors.append("source ROM SHA-256 mismatch")
    if manifest.get("schema") != "cutscene-obj-export-v1":
        errors.append("unexpected manifest schema")
    expected_rom = {
        "path": "rom/base.gba",
        "size": len(rom),
        "sha256": rom_hash,
    }
    if manifest.get("rom") != expected_rom:
        errors.append("manifest ROM metadata mismatch")
    if manifest.get("source_bank") != (
        "sequel/content/cutscene-scripts/bank.json"
    ):
        errors.append("source-bank metadata mismatch")

    resource_table = rom[
        RESOURCE_TABLE_OFFSET : RESOURCE_TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE
    ]
    sprite_table = rom[
        SPRITE_TABLE_OFFSET : SPRITE_TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE
    ]
    expected_resource_table = {
        "file_offset": RESOURCE_TABLE_OFFSET,
        "gba_address": "0x0853DF70",
        "entry_count": ENTRY_COUNT,
        "entry_size": ENTRY_SIZE,
        "sha256": RESOURCE_TABLE_SHA256,
    }
    expected_sprite_table = {
        "file_offset": SPRITE_TABLE_OFFSET,
        "gba_address": "0x0853DF90",
        "entry_count": ENTRY_COUNT,
        "entry_size": ENTRY_SIZE,
        "sha256": SPRITE_TABLE_SHA256,
    }
    if _sha256(resource_table) != RESOURCE_TABLE_SHA256:
        errors.append("resource table hash mismatch")
    if _sha256(sprite_table) != SPRITE_TABLE_SHA256:
        errors.append("sprite table hash mismatch")
    if _sha256(resource_table + sprite_table) != COMBINED_TABLE_SHA256:
        errors.append("combined table hash mismatch")
    if manifest.get("resource_table") != expected_resource_table:
        errors.append("resource table metadata mismatch")
    if manifest.get("sprite_table") != expected_sprite_table:
        errors.append("sprite table metadata mismatch")
    if manifest.get("combined_table_sha256") != COMBINED_TABLE_SHA256:
        errors.append("combined table metadata mismatch")
    if manifest.get("consumer") != EXPECTED_CONSUMER:
        errors.append("consumer metadata mismatch")
    expected_consumer_evidence = {}
    for name, (start, end, expected_hash) in CONSUMER_RANGES.items():
        raw = rom[start - ROM_BASE : end - ROM_BASE]
        if len(raw) != end - start or _sha256(raw) != expected_hash:
            errors.append(f"consumer evidence changed: {name}")
        expected_consumer_evidence[name] = {
            "gba_range": [_pointer(start), _pointer(end)],
            "size": end - start,
            "sha256": expected_hash,
        }
    if manifest.get("consumer_evidence") != expected_consumer_evidence:
        errors.append("consumer evidence metadata mismatch")
    if manifest.get("animation_runtime") != ANIMATION_RUNTIME:
        errors.append("animation runtime metadata mismatch")
    if manifest.get("scope") != EXPECTED_SCOPE:
        errors.append("scope metadata mismatch")
    try:
        _verify_consumer_literals(rom)
    except (ValueError, struct.error) as error:
        errors.append(f"consumer: {error}")

    expected_summary = {
        "resource_count": 4,
        "frame_count": 10,
        "animation_count": 10,
        "frame_counts": [2, 2, 2, 4],
        "atlas_count": 4,
        "unique_palette_count": 1,
    }
    for key, expected in expected_summary.items():
        if manifest.get(key) != expected:
            errors.append(f"{key} mismatch")
    resources = manifest.get("resources")
    if not isinstance(resources, list) or len(resources) != ENTRY_COUNT:
        errors.append("manifest does not contain four resources")
        resources = [] if not isinstance(resources, list) else resources

    for resource_id in range(min(len(resources), ENTRY_COUNT)):
        try:
            resource = resources[resource_id]
            if not isinstance(resource, dict):
                raise ValueError("resource manifest is not an object")
            resource_pair_offset = (
                RESOURCE_TABLE_OFFSET + resource_id * ENTRY_SIZE
            )
            sprite_pair_offset = SPRITE_TABLE_OFFSET + resource_id * ENTRY_SIZE
            gfx_pointer, palette_pointer = struct.unpack_from(
                "<II",
                rom,
                resource_pair_offset,
            )
            definition_pointer, animation_pointer = struct.unpack_from(
                "<II",
                rom,
                sprite_pair_offset,
            )
            _, graphics, gfx_manifest = _load_lz(rom, gfx_pointer)
            _, palette, palette_manifest = _load_lz(
                rom,
                palette_pointer,
                expected_size=32,
            )
            if (
                gfx_manifest["decompressed_sha256"]
                != EXPECTED_GFX_SHA256[resource_id]
            ):
                raise ValueError("graphics payload hash mismatch")
            if (
                palette_manifest["decompressed_sha256"]
                != EXPECTED_PALETTE_SHA256
            ):
                raise ValueError("palette payload hash mismatch")
            delta = animation_pointer - definition_pointer
            if delta <= 0 or delta % 12:
                raise ValueError("table delta cannot prove the frame count")
            frame_count = delta // 12
            definition_offset = _offset(definition_pointer, len(rom))
            animation_offset = _offset(animation_pointer, len(rom))
            definition_pointer_bytes = rom[
                definition_offset : definition_offset + frame_count * 4
            ]
            animation_pointer_bytes = rom[
                animation_offset : animation_offset + frame_count * 4
            ]

            atlas_pixels, atlas_width, atlas_height = _render_atlas(graphics)
            atlas_name = f"resource_{resource_id}_atlas.png"
            expected_files.add(atlas_name)
            atlas_hash = _verify_png(
                artifact_dir / atlas_name,
                pixels=atlas_pixels,
                palette=palette,
                width=atlas_width,
                height=atlas_height,
            )
            verified_atlases += 1
            expected_frames: list[dict[str, Any]] = []
            animation_records_start = definition_pointer + frame_count * 4
            for frame_id in range(frame_count):
                frame_definition_pointer = struct.unpack_from(
                    "<I",
                    definition_pointer_bytes,
                    frame_id * 4,
                )[0]
                frame_animation_pointer = struct.unpack_from(
                    "<I",
                    animation_pointer_bytes,
                    frame_id * 4,
                )[0]
                if frame_animation_pointer != (
                    animation_records_start
                    + frame_id * ANIMATION_RECORD_SIZE
                ):
                    raise ValueError("animation pointer is not adjacent")
                frame_definition_offset = _offset(
                    frame_definition_pointer,
                    len(rom),
                )
                frame_animation_offset = _offset(
                    frame_animation_pointer,
                    len(rom),
                )
                definition_raw = rom[
                    frame_definition_offset : frame_definition_offset
                    + DEFINITION_RECORD_SIZE
                ]
                animation_raw = rom[
                    frame_animation_offset : frame_animation_offset
                    + ANIMATION_RECORD_SIZE
                ]
                if (
                    len(definition_raw) != DEFINITION_RECORD_SIZE
                    or len(animation_raw) != ANIMATION_RECORD_SIZE
                ):
                    raise ValueError("frame record is truncated")
                (
                    tile_offset,
                    x_offset,
                    y_offset,
                    width,
                    height,
                ) = struct.unpack_from("<IhhHH", definition_raw)
                if (
                    width <= 0
                    or height <= 0
                    or width % 8
                    or height % 8
                ):
                    raise ValueError("frame dimensions are not whole tiles")
                width_tiles = width // 8
                height_tiles = height // 8
                frame_pixels = _render_block(
                    graphics,
                    tile_offset=tile_offset,
                    width_tiles=width_tiles,
                    height_tiles=height_tiles,
                )
                animation_words = list(struct.unpack("<4H", animation_raw))
                if (
                    animation_words[0] != frame_id
                    or animation_words[2:] != [0xFFFF, 0]
                ):
                    raise ValueError("animation record structure changed")
                frame_name = (
                    f"resource_{resource_id}_frame_{frame_id:02d}.png"
                )
                expected_files.add(frame_name)
                frame_hash = _verify_png(
                    artifact_dir / frame_name,
                    pixels=frame_pixels,
                    palette=palette,
                    width=width,
                    height=height,
                )
                verified_frames += 1
                duration_ticks = animation_words[1]
                first_expiry_update = duration_ticks or 65536
                timeline_name = (
                    f"resource_{resource_id}_animation_{frame_id:02d}.json"
                )
                expected_files.add(timeline_name)
                expected_frame = {
                    "frame_id": frame_id,
                    "definition_pointer": _pointer(
                        frame_definition_pointer
                    ),
                    "definition_file_offset": frame_definition_offset,
                    "definition_raw_hex": definition_raw.hex(),
                    "definition_sha256": _sha256(definition_raw),
                    "tile_offset": tile_offset,
                    "x_offset": x_offset,
                    "y_offset": y_offset,
                    "width": width,
                    "height": height,
                    "width_tiles": width_tiles,
                    "height_tiles": height_tiles,
                    "definition_tail_words": list(
                        struct.unpack_from("<6H", definition_raw, 12)
                    ),
                    "animation_pointer": _pointer(
                        frame_animation_pointer
                    ),
                    "animation_file_offset": frame_animation_offset,
                    "animation_raw_hex": animation_raw.hex(),
                    "animation_sha256": _sha256(animation_raw),
                    "animation_words": animation_words,
                    "animation_timing_interpreted": True,
                    "duration_ticks": duration_ticks,
                    "first_expiry_update": first_expiry_update,
                    "termination_policy": "deactivate_task",
                    "playback": [
                        {
                            "frame_id": frame_id,
                            "start_update": 0,
                            "end_update_exclusive": first_expiry_update,
                        }
                    ],
                    "animation_timeline_json": timeline_name,
                    "png": frame_name,
                    "png_sha256": frame_hash,
                }
                timeline = json.loads(
                    (artifact_dir / timeline_name).read_text(encoding="utf-8")
                )
                if timeline != expected_frame:
                    raise ValueError("animation timeline does not match the ROM")
                verified_animations += 1
                expected_frames.append(expected_frame)

            expected_resource = {
                "resource_id": resource_id,
                "resource_pair_file_offset": resource_pair_offset,
                "sprite_pair_file_offset": sprite_pair_offset,
                "gfx_pointer": _pointer(gfx_pointer),
                "palette_pointer": _pointer(palette_pointer),
                "definition_table_pointer": _pointer(definition_pointer),
                "animation_table_pointer": _pointer(animation_pointer),
                "frame_count": frame_count,
                "frame_count_derivation": (
                    "(animation_table_pointer - "
                    "definition_table_pointer) / 12"
                ),
                "gfx": gfx_manifest,
                "palette": palette_manifest,
                "definition_pointer_table_sha256": _sha256(
                    definition_pointer_bytes
                ),
                "animation_pointer_table_sha256": _sha256(
                    animation_pointer_bytes
                ),
                "atlas": {
                    "png": atlas_name,
                    "png_sha256": atlas_hash,
                    "width": atlas_width,
                    "height": atlas_height,
                    "tile_count": len(graphics) // 32,
                    "tiles_per_row": ATLAS_TILES_PER_ROW,
                },
                "frames": expected_frames,
            }
            if resource != expected_resource:
                raise ValueError("resource metadata does not match the ROM")
            verified_resources += 1
        except (
            KeyError,
            OSError,
            TypeError,
            ValueError,
            struct.error,
        ) as error:
            errors.append(f"resource {resource_id}: {error}")

    actual_files = {
        path.name for path in artifact_dir.iterdir() if path.is_file()
    }
    if actual_files != expected_files:
        errors.append("artifact file set mismatch")

    return {
        "schema": "cutscene-obj-verification-v1",
        "rom_sha256": rom_hash,
        "verified_resources": verified_resources,
        "verified_frames": verified_frames,
        "verified_animations": verified_animations,
        "verified_atlases": verified_atlases,
        "errors": errors,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/cutscene-obj-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = verify_cutscene_obj_export(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
