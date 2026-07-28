#!/usr/bin/env python3
"""Export the four ROM-bound cutscene OBJ bundles and ten static frames."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import (
    ROM_BASE,
    gba_address,
    gba_pointer,
    indexed_png_from_bgr555,
    read_lz77_record,
    render_4bpp_tile_atlas_indices,
    render_4bpp_tile_block_indices,
    sha256,
)


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
DEFINITION_RECORD_SIZE = 24
ANIMATION_RECORD_SIZE = 8
ATLAS_TILES_PER_ROW = 16


def _rom_offset(pointer: int, rom_size: int) -> int:
    offset = pointer - ROM_BASE
    if not 0 <= offset < rom_size:
        raise ValueError(f"pointer {gba_pointer(pointer)} is outside the ROM")
    return offset


def _lz_component(
    rom: bytes,
    pointer: int,
    *,
    expected_size: int | None = None,
) -> tuple[bytes, dict[str, Any]]:
    offset = _rom_offset(pointer, len(rom))
    compressed = read_lz77_record(
        rom,
        offset,
        expected_size=expected_size,
    )
    payload = lz77_decompress(rom, offset)
    if expected_size is not None and len(payload) != expected_size:
        raise ValueError(
            f"{gba_pointer(pointer)} decompressed to {len(payload)}, "
            f"expected {expected_size}"
        )
    return payload, {
        "file_offset": offset,
        "gba_address": gba_pointer(pointer),
        "compressed_size": len(compressed),
        "compressed_sha256": sha256(compressed),
        "decompressed_size": len(payload),
        "decompressed_sha256": sha256(payload),
    }


def _load_bank(root: Path, rom: bytes) -> dict[str, Any]:
    bank = json.loads(
        (root / "sequel/content/cutscene-scripts/bank.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        bank.get("table_offset") != RESOURCE_TABLE_OFFSET
        or bank.get("entry_count") != 8
        or bank.get("entry_size") != ENTRY_SIZE
        or bank.get("verification") != "code_verified"
    ):
        raise ValueError("unexpected cutscene visual-resource bank")
    entries = bank.get("entries")
    if not isinstance(entries, list) or len(entries) != 8:
        raise ValueError("cutscene visual-resource bank must contain eight rows")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"cutscene bank row {index} is not an object")
        row_offset = RESOURCE_TABLE_OFFSET + index * ENTRY_SIZE
        pointers = struct.unpack_from("<II", rom, row_offset)
        if (
            entry.get("_index") != index
            or entry.get("_raw_offset") != row_offset
            or (
                entry.get("primary_ptr"),
                entry.get("secondary_ptr"),
            )
            != pointers
        ):
            raise ValueError(f"cutscene bank row {index} diverges from the ROM")
        expected_kind = (
            "compressed_gfx_palette"
            if index < ENTRY_COUNT
            else "sprite_definition_animation"
        )
        if (
            entry.get("pair_kind") != expected_kind
            or entry.get("resource_id") != index % ENTRY_COUNT
        ):
            raise ValueError(f"cutscene bank row {index} has wrong semantics")
    return bank


def _read_record(
    rom: bytes,
    pointer: int,
    size: int,
) -> tuple[bytes, int]:
    offset = _rom_offset(pointer, len(rom))
    if offset + size > len(rom):
        raise ValueError(f"record at {gba_pointer(pointer)} is truncated")
    return rom[offset : offset + size], offset


def _remove_owned_outputs(output_dir: Path) -> None:
    for path in output_dir.iterdir():
        if not path.is_file():
            continue
        if path.name == "manifest.json" or (
            path.suffix == ".png"
            and path.name.startswith("resource_")
        ):
            path.unlink()


def export_cutscene_obj_assets(
    root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Export four complete atlases, ten native frames, and their manifest."""
    root = Path(root).resolve()
    output_dir = Path(output_dir)
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    rom = (root / "rom/base.gba").read_bytes()
    rom_hash = sha256(rom)
    if rom_hash != ROM_SHA256:
        raise ValueError(
            f"ROM SHA-256 mismatch: expected {ROM_SHA256}, got {rom_hash}"
        )
    _load_bank(root, rom)
    resource_table = rom[
        RESOURCE_TABLE_OFFSET : RESOURCE_TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE
    ]
    sprite_table = rom[
        SPRITE_TABLE_OFFSET : SPRITE_TABLE_OFFSET + ENTRY_COUNT * ENTRY_SIZE
    ]
    if sha256(resource_table) != RESOURCE_TABLE_SHA256:
        raise ValueError("cutscene resource table hash mismatch")
    if sha256(sprite_table) != SPRITE_TABLE_SHA256:
        raise ValueError("cutscene sprite table hash mismatch")
    if sha256(resource_table + sprite_table) != COMBINED_TABLE_SHA256:
        raise ValueError("combined cutscene table hash mismatch")

    output_dir.mkdir(parents=True, exist_ok=True)
    _remove_owned_outputs(output_dir)
    resources: list[dict[str, Any]] = []
    frame_counts: list[int] = []
    palette_hashes: set[str] = set()

    for resource_id in range(ENTRY_COUNT):
        resource_pair_offset = (
            RESOURCE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        )
        sprite_pair_offset = SPRITE_TABLE_OFFSET + resource_id * ENTRY_SIZE
        gfx_pointer, palette_pointer = struct.unpack_from(
            "<II",
            rom,
            resource_pair_offset,
        )
        definition_table_pointer, animation_table_pointer = struct.unpack_from(
            "<II",
            rom,
            sprite_pair_offset,
        )
        graphics, gfx_manifest = _lz_component(rom, gfx_pointer)
        palette, palette_manifest = _lz_component(
            rom,
            palette_pointer,
            expected_size=32,
        )
        if not graphics or len(graphics) % 32:
            raise ValueError(
                f"resource {resource_id} graphics is not complete 4bpp tiles"
            )
        palette_hashes.add(palette_manifest["decompressed_sha256"])

        pointer_delta = (
            animation_table_pointer - definition_table_pointer
        )
        if pointer_delta <= 0 or pointer_delta % 12:
            raise ValueError(
                f"resource {resource_id} table delta cannot prove frame count"
            )
        frame_count = pointer_delta // 12
        if frame_count not in (2, 4):
            raise ValueError(
                f"resource {resource_id} has unexpected frame count "
                f"{frame_count}"
            )
        frame_counts.append(frame_count)

        atlas_pixels, atlas_width, atlas_height = (
            render_4bpp_tile_atlas_indices(
                graphics,
                tiles_per_row=ATLAS_TILES_PER_ROW,
            )
        )
        atlas_png = indexed_png_from_bgr555(
            atlas_pixels,
            palette,
            width=atlas_width,
            height=atlas_height,
            transparent_index=0,
        )
        atlas_name = f"resource_{resource_id}_atlas.png"
        (output_dir / atlas_name).write_bytes(atlas_png)
        frames: list[dict[str, Any]] = []

        definition_table_offset = _rom_offset(
            definition_table_pointer,
            len(rom),
        )
        animation_table_offset = _rom_offset(
            animation_table_pointer,
            len(rom),
        )
        definition_pointer_bytes = rom[
            definition_table_offset : definition_table_offset
            + frame_count * 4
        ]
        animation_pointer_bytes = rom[
            animation_table_offset : animation_table_offset
            + frame_count * 4
        ]
        if (
            len(definition_pointer_bytes) != frame_count * 4
            or len(animation_pointer_bytes) != frame_count * 4
        ):
            raise ValueError(f"resource {resource_id} pointer table is truncated")

        animation_records_start = (
            definition_table_pointer + frame_count * 4
        )
        for frame_id in range(frame_count):
            definition_pointer = struct.unpack_from(
                "<I",
                definition_pointer_bytes,
                frame_id * 4,
            )[0]
            animation_pointer = struct.unpack_from(
                "<I",
                animation_pointer_bytes,
                frame_id * 4,
            )[0]
            expected_animation_pointer = (
                animation_records_start
                + frame_id * ANIMATION_RECORD_SIZE
            )
            if animation_pointer != expected_animation_pointer:
                raise ValueError(
                    f"resource {resource_id} animation pointer {frame_id} "
                    "does not target its adjacent record"
                )
            definition_raw, definition_offset = _read_record(
                rom,
                definition_pointer,
                DEFINITION_RECORD_SIZE,
            )
            animation_raw, animation_offset = _read_record(
                rom,
                animation_pointer,
                ANIMATION_RECORD_SIZE,
            )
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
                raise ValueError(
                    f"resource {resource_id} frame {frame_id} dimensions "
                    "are not whole positive tiles"
                )
            width_tiles = width // 8
            height_tiles = height // 8
            frame_pixels, rendered_width, rendered_height = (
                render_4bpp_tile_block_indices(
                    graphics,
                    tile_offset=tile_offset,
                    width_tiles=width_tiles,
                    height_tiles=height_tiles,
                )
            )
            if (rendered_width, rendered_height) != (width, height):
                raise ValueError(
                    f"resource {resource_id} frame {frame_id} render size "
                    "does not match its definition"
                )
            animation_words = list(struct.unpack("<4H", animation_raw))
            if (
                animation_words[0] != frame_id
                or animation_words[2:] != [0xFFFF, 0]
            ):
                raise ValueError(
                    f"resource {resource_id} animation record {frame_id} "
                    "has an unexpected static structure"
                )
            frame_png = indexed_png_from_bgr555(
                frame_pixels,
                palette,
                width=width,
                height=height,
                transparent_index=0,
            )
            frame_name = (
                f"resource_{resource_id}_frame_{frame_id:02d}.png"
            )
            (output_dir / frame_name).write_bytes(frame_png)
            frames.append(
                {
                    "frame_id": frame_id,
                    "definition_pointer": gba_pointer(definition_pointer),
                    "definition_file_offset": definition_offset,
                    "definition_raw_hex": definition_raw.hex(),
                    "definition_sha256": sha256(definition_raw),
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
                    "animation_pointer": gba_pointer(animation_pointer),
                    "animation_file_offset": animation_offset,
                    "animation_raw_hex": animation_raw.hex(),
                    "animation_sha256": sha256(animation_raw),
                    "animation_words": animation_words,
                    "animation_timing_interpreted": False,
                    "png": frame_name,
                    "png_sha256": sha256(frame_png),
                }
            )

        resources.append(
            {
                "resource_id": resource_id,
                "resource_pair_file_offset": resource_pair_offset,
                "sprite_pair_file_offset": sprite_pair_offset,
                "gfx_pointer": gba_pointer(gfx_pointer),
                "palette_pointer": gba_pointer(palette_pointer),
                "definition_table_pointer": gba_pointer(
                    definition_table_pointer
                ),
                "animation_table_pointer": gba_pointer(
                    animation_table_pointer
                ),
                "frame_count": frame_count,
                "frame_count_derivation": (
                    "(animation_table_pointer - "
                    "definition_table_pointer) / 12"
                ),
                "gfx": gfx_manifest,
                "palette": palette_manifest,
                "definition_pointer_table_sha256": sha256(
                    definition_pointer_bytes
                ),
                "animation_pointer_table_sha256": sha256(
                    animation_pointer_bytes
                ),
                "atlas": {
                    "png": atlas_name,
                    "png_sha256": sha256(atlas_png),
                    "width": atlas_width,
                    "height": atlas_height,
                    "tile_count": len(graphics) // 32,
                    "tiles_per_row": ATLAS_TILES_PER_ROW,
                },
                "frames": frames,
            }
        )

    manifest = {
        "schema": "cutscene-obj-export-v1",
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": rom_hash,
        },
        "source_bank": "sequel/content/cutscene-scripts/bank.json",
        "resource_table": {
            "file_offset": RESOURCE_TABLE_OFFSET,
            "gba_address": gba_address(RESOURCE_TABLE_OFFSET),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "sha256": RESOURCE_TABLE_SHA256,
        },
        "sprite_table": {
            "file_offset": SPRITE_TABLE_OFFSET,
            "gba_address": gba_address(SPRITE_TABLE_OFFSET),
            "entry_count": ENTRY_COUNT,
            "entry_size": ENTRY_SIZE,
            "sha256": SPRITE_TABLE_SHA256,
        },
        "combined_table_sha256": COMBINED_TABLE_SHA256,
        "consumer": {
            "loader_gba_address": "0x08072EDC",
            "resource_index_gba_address": "0x08072F0C",
            "sprite_allocator_gba_address": "0x080625A4",
            "sprite_index_gba_address": "0x08062668",
            "gfx_destination": "0x06016000",
            "palette_destination": "0x05000380",
            "direct_resource_ids": [0, 1, 2, 3],
        },
        "scope": {
            "kind": "static 4bpp OBJ atlases and definition-backed frames",
            "final_runtime_sequence": False,
            "animation_timing_interpreted": False,
            "palette_index_zero_transparent": True,
        },
        "resource_count": len(resources),
        "frame_count": sum(frame_counts),
        "frame_counts": frame_counts,
        "atlas_count": len(resources),
        "unique_palette_count": len(palette_hashes),
        "resources": resources,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/cutscene-obj-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_cutscene_obj_assets(args.root, args.output_dir)
    print(
        f"Exported {manifest['frame_count']} static OBJ frames and "
        f"{manifest['atlas_count']} atlases to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
