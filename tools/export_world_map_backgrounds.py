#!/usr/bin/env python3
"""Export the three world-map backgrounds and their encoded text labels."""

from __future__ import annotations

import argparse
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

from tools.extract_tileset import lz77_decompress
from tools.gba_image_export import (
    ROM_BASE,
    gba_pointer,
    indexed_png_from_bgr555,
    read_lz77_record,
    sha256,
)


ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "world-map-backgrounds-v1"
BACKGROUND_TABLE_ADDRESS = 0x085A8014
BACKGROUND_ENTRY_COUNT = 3
BACKGROUND_ENTRY_SIZE = 0x0C
BACKGROUND_TABLE_SHA256 = (
    "9ccd6d722b87a8bf910fb45072ad682d89b9cf3432979b163f57283902396f35"
)
LABEL_TABLE_ADDRESS = 0x085A8038
LABEL_ENTRY_SIZE = 0x10
LABEL_TABLE_SHA256 = (
    "67b4a34289072f9a89b7f79721df851e6f23409d1c23dc4f90ae7f5d6130d052"
)
WIDTH_TILES = 30
HEIGHT_TILES = 20
GRAPHICS_SIZE = 512 * 64
TILEMAP_SIZE = WIDTH_TILES * HEIGHT_TILES * 2
PALETTE_SIZE = 160 * 2
LABEL_PREVIEW_PALETTE = struct.pack("<4H", 0x0000, 0x294A, 0x56B5, 0x7FFF)
FONT_MANIFEST_SHA256 = (
    "a4b7abae4a5b2ad760b4225c514b198ddc3e2c5766e66d1e2f4e88d58575d1ef"
)

CONSUMER_RANGES = {
    "background_loader": (
        0x0808EDBC,
        0x0808EE26,
        "e66468161801a8d10f070d8d505efdfd39b966fdcd96c60fc1b6c384c7cecd12",
    ),
    "selection_and_load_calls": (
        0x0808F284,
        0x0808F2A2,
        "256b740d579cbf6f61a29c2504f7f4eb414dd9e7fbd1e21955ba520d1cf19b2c",
    ),
    "packed_tilemap_copier": (
        0x08063604,
        0x080636C0,
        "844be072d9572bd9a657357e745977ed9435c647d0ec0e811f66c953c84a1bd6",
    ),
    "text_wrapper": (
        0x08066758,
        0x0806678E,
        "2a90d5fc068dec5c806ec3c973772d726efdaa3a48ac6d2fc64a805f3c40c5ef",
    ),
    "background_loader_literal_pool": (
        0x0808EE28,
        0x0808EE40,
        "5fad3d9b96d7d52dd1f3f06892e1184a46209023f887ab25bc352f289322e19f",
    ),
    "selection_literal_pool": (
        0x0808F2F8,
        0x0808F300,
        "5c1f9eb562810b706dcf6ca68342e8fe10e7a4e9b57dcff81f885245884acc2f",
    ),
}

GLYPH_SOURCES = {
    0x8140: (
        0x0809D954,
        "42bcd694ac47d9a2a377c8a61e8fe60398a201705d1aaeba9e87e117d79e33fb",
    ),
    0x89A5: (
        0x080A39F4,
        "b99dd792f82047c9d759d71778c281e315ab3f266aa9cf8dbf6610966e94afac",
    ),
    0x8D99: (
        0x080A9874,
        "9c07ac774b8737b75793f9bf824a0aadca0c332c79b92f44b4ce527f0655f41a",
    ),
    0x90EC: (
        0x080AEAD4,
        "6c4f7f55f1ae5f5cfddbaa6ad9827ac9c2b61b8ed6357b33d9c0e72c1527725e",
    ),
    0x92BB: (
        0x080B14B4,
        "b167195ec90be190ee6de0a71edf0730a925662143503aaa40ab0b56a24a151d",
    ),
    0x954B: (
        0x080B4EB4,
        "eaabc7339e7b7ccedd0654da0bf695d4d139c6ce832bd6d88220f23513140674",
    ),
    0x965E: (
        0x080B6914,
        "902e579cbfc0337082379ee0a1f1ea06ead5553594c561ec35f854557e4771fc",
    ),
    0x99DE: (
        0x085B0D00,
        "da9b122c7cc9761309f016edc532937b82ed9d29ef191d0ca53f1bbb1e9a3c82",
    ),
    0x9BD6: (
        0x085B3B40,
        "1597a2e18dbbfe000195d548d2d59c0827c4dc2ba96376adb219a689f4f27168",
    ),
}


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _slice(rom: bytes, address: int, size: int) -> bytes:
    offset = address - ROM_BASE
    if offset < 0 or offset + size > len(rom):
        raise ValueError(f"ROM range is invalid at {_address(address)}")
    return rom[offset : offset + size]


def _resource(
    rom: bytes,
    pointer: int,
    expected_size: int,
) -> tuple[bytes, bytes]:
    offset = pointer - ROM_BASE
    compressed = read_lz77_record(rom, offset, expected_size=expected_size)
    data = lz77_decompress(rom, offset)
    if len(data) != expected_size:
        raise ValueError(f"resource size mismatch at {_address(pointer)}")
    return compressed, data


def _decode_label_glyph(source: bytes) -> bytes:
    if len(source) != 32:
        raise ValueError("encoded SJIS glyph must be 32 bytes")
    output = bytearray()
    for half in range(2):
        for packed in source[half * 16 : (half + 1) * 16]:
            output.extend((packed >> shift) & 3 for shift in (0, 2, 4, 6))
    return bytes(output)


def _render_label(
    rom: bytes,
    codes: list[int],
) -> tuple[bytes, list[dict[str, Any]], bytes]:
    pixels = bytearray()
    rows = [bytearray() for _ in range(16)]
    glyphs: list[dict[str, Any]] = []
    for code in codes:
        try:
            pointer, expected_hash = GLYPH_SOURCES[code]
        except KeyError as error:
            raise ValueError(f"unmapped label code 0x{code:04X}") from error
        source = _slice(rom, pointer, 32)
        if sha256(source) != expected_hash:
            raise ValueError(f"glyph source mismatch for 0x{code:04X}")
        glyph_pixels = _decode_label_glyph(source)
        for y in range(16):
            rows[y].extend(glyph_pixels[y * 8 : (y + 1) * 8])
        glyphs.append(
            {
                "code": f"0x{code:04X}",
                "source_pointer": _address(pointer),
                "source_sha256": expected_hash,
                "source_format": "two-8x8-2bpp-half-tiles",
                "covered_by_dialogue_font_v2": True,
            }
        )
    for row in rows:
        pixels.extend(row)
    png = indexed_png_from_bgr555(
        bytes(pixels),
        LABEL_PREVIEW_PALETTE,
        width=32,
        height=16,
        transparent_index=0,
    )
    return bytes(pixels), glyphs, png


def _render_background(
    graphics: bytes,
    tilemap: bytes,
) -> tuple[bytes, dict[str, Any]]:
    if len(graphics) != GRAPHICS_SIZE or len(tilemap) != TILEMAP_SIZE:
        raise ValueError("world-map background payload size mismatch")
    entries = struct.unpack(f"<{WIDTH_TILES * HEIGHT_TILES}H", tilemap)
    pixels = bytearray(WIDTH_TILES * 8 * HEIGHT_TILES * 8)
    referenced: set[int] = set()
    horizontal_flips = 0
    vertical_flips = 0
    palette_banks: set[int] = set()
    width = WIDTH_TILES * 8
    for tile_y in range(HEIGHT_TILES):
        for tile_x in range(WIDTH_TILES):
            entry = entries[tile_y * WIDTH_TILES + tile_x]
            tile_id = entry & 0x03FF
            if tile_id >= 512:
                raise ValueError("world-map tilemap references an invalid tile")
            referenced.add(tile_id)
            horizontal = bool(entry & 0x0400)
            vertical = bool(entry & 0x0800)
            horizontal_flips += int(horizontal)
            vertical_flips += int(vertical)
            palette_banks.add(entry >> 12)
            for local_y in range(8):
                source_y = 7 - local_y if vertical else local_y
                for local_x in range(8):
                    source_x = 7 - local_x if horizontal else local_x
                    pixels[
                        (tile_y * 8 + local_y) * width + tile_x * 8 + local_x
                    ] = graphics[
                        tile_id * 64 + source_y * 8 + source_x
                    ]
    missing = sorted(set(range(512)) - referenced)
    return bytes(pixels), {
        "referenced_tile_indices": sorted(referenced),
        "missing_tile_indices": missing,
        "all_tiles_referenced": not missing,
        "horizontal_flip_entry_count": horizontal_flips,
        "vertical_flip_entry_count": vertical_flips,
        "palette_bank_values": sorted(palette_banks),
    }


def validate_output_target(root: Path, output_dir: Path) -> Path:
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
        try:
            existing = json.loads(
                (target / "manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            ) from error
        if existing.get("schema") != SCHEMA:
            raise ValueError(
                "refusing to replace a directory that is not this artifact"
            )
    return target


def _replace_output(output_dir: Path, files: dict[str, bytes]) -> None:
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=output_dir.parent)
    )
    backup: Path | None = None
    try:
        for relative, data in sorted(files.items()):
            path = temporary / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
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


def export_artifact(
    root: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_dir = validate_output_target(root, Path(output_dir))
    rom = (root / "rom/base.gba").read_bytes()
    if sha256(rom) != ROM_SHA256:
        raise ValueError("base ROM SHA-256 mismatch")

    background_table = _slice(
        rom,
        BACKGROUND_TABLE_ADDRESS,
        BACKGROUND_ENTRY_COUNT * BACKGROUND_ENTRY_SIZE,
    )
    label_table = _slice(
        rom,
        LABEL_TABLE_ADDRESS,
        BACKGROUND_ENTRY_COUNT * LABEL_ENTRY_SIZE,
    )
    if sha256(background_table) != BACKGROUND_TABLE_SHA256:
        raise ValueError("world-map background table mismatch")
    if sha256(label_table) != LABEL_TABLE_SHA256:
        raise ValueError("world-map label table mismatch")

    font_manifest_path = root / "artifacts/dialogue-font-v2/manifest.json"
    font_manifest_raw = font_manifest_path.read_bytes()
    if sha256(font_manifest_raw) != FONT_MANIFEST_SHA256:
        raise ValueError("dialogue-font-v2 manifest SHA-256 mismatch")
    font_manifest = json.loads(font_manifest_raw.decode("utf-8"))
    if (
        font_manifest.get("schema") != "dialogue-font-atlas-v2"
        or font_manifest.get("rom", {}).get("sha256") != ROM_SHA256
    ):
        raise ValueError("dialogue-font-v2 dependency mismatch")
    covered = {
        entry["sjis_hex"]: (entry["source_pointer"], entry["source_sha256"])
        for entry in font_manifest["sjis_glyphs"]
    }
    for code, (pointer, glyph_hash) in GLYPH_SOURCES.items():
        if covered.get(f"0x{code:04X}") != (_address(pointer), glyph_hash):
            raise ValueError(f"dialogue-font-v2 does not cover 0x{code:04X}")

    consumer_evidence: dict[str, dict[str, Any]] = {}
    for name, (start, end, expected_hash) in CONSUMER_RANGES.items():
        code = _slice(rom, start, end - start)
        if sha256(code) != expected_hash:
            raise ValueError(f"consumer hash mismatch: {name}")
        consumer_evidence[name] = {
            "start": _address(start),
            "end_exclusive": _address(end),
            "size": len(code),
            "sha256": expected_hash,
        }

    files: dict[str, bytes] = {}
    pages: list[dict[str, Any]] = []
    shared_map: bytes | None = None
    map_hashes: set[str] = set()
    for page_id in range(BACKGROUND_ENTRY_COUNT):
        entry_address = BACKGROUND_TABLE_ADDRESS + page_id * BACKGROUND_ENTRY_SIZE
        entry = background_table[
            page_id * BACKGROUND_ENTRY_SIZE : (page_id + 1) * BACKGROUND_ENTRY_SIZE
        ]
        graphics_pointer, map_pointer, palette_pointer = struct.unpack("<III", entry)
        graphics_compressed, graphics = _resource(
            rom, graphics_pointer, GRAPHICS_SIZE
        )
        map_compressed, tilemap = _resource(rom, map_pointer, TILEMAP_SIZE)
        palette = _slice(rom, palette_pointer, PALETTE_SIZE)
        if shared_map is None:
            shared_map = tilemap
            files["shared/tilemap-30x20.bin"] = tilemap
        elif tilemap != shared_map:
            raise ValueError("world-map tilemaps are not identical")
        map_hashes.add(sha256(tilemap))

        pixels, map_facts = _render_background(graphics, tilemap)
        if max(pixels) >= len(palette) // 2:
            raise ValueError("background references a missing palette color")
        png = indexed_png_from_bgr555(
            pixels,
            palette,
            width=WIDTH_TILES * 8,
            height=HEIGHT_TILES * 8,
        )
        prefix = f"page-{page_id:02d}"
        graphics_file = f"{prefix}/background.8bpp.bin"
        palette_file = f"{prefix}/palette.bgr555.bin"
        png_file = f"{prefix}/background.png"
        files[graphics_file] = graphics
        files[palette_file] = palette
        files[png_file] = png

        label_address = LABEL_TABLE_ADDRESS + page_id * LABEL_ENTRY_SIZE
        label_record = label_table[
            page_id * LABEL_ENTRY_SIZE : (page_id + 1) * LABEL_ENTRY_SIZE
        ]
        if label_record[8] != 0 or any(label_record[9:]):
            raise ValueError("world-map label terminator or padding mismatch")
        codes = list(struct.unpack(">4H", label_record[:8]))
        label_pixels, glyphs, label_png = _render_label(rom, codes)
        label_record_file = f"{prefix}/label-record.bin"
        label_png_file = f"{prefix}/label-preview.png"
        files[label_record_file] = label_record
        files[label_png_file] = label_png

        pages.append(
            {
                "page_id": page_id,
                "entry_gba_address": _address(entry_address),
                "entry_sha256": sha256(entry),
                "raw_hex": entry.hex(),
                "background": {
                    "bits_per_pixel": 8,
                    "graphics_pointer": gba_pointer(graphics_pointer),
                    "graphics_compressed_size": len(graphics_compressed),
                    "graphics_compressed_sha256": sha256(graphics_compressed),
                    "graphics_file": graphics_file,
                    "graphics_sha256": sha256(graphics),
                    "tile_count": len(graphics) // 64,
                    "tilemap_pointer": gba_pointer(map_pointer),
                    "tilemap_compressed_size": len(map_compressed),
                    "tilemap_compressed_sha256": sha256(map_compressed),
                    "tilemap_file": "shared/tilemap-30x20.bin",
                    "tilemap_sha256": sha256(tilemap),
                    "palette_pointer": gba_pointer(palette_pointer),
                    "palette_file": palette_file,
                    "palette_sha256": sha256(palette),
                    "palette_color_count": len(palette) // 2,
                    "dimensions_tiles": [WIDTH_TILES, HEIGHT_TILES],
                    "maximum_pixel_index": max(pixels),
                    "minimum_pixel_index": min(pixels),
                    "palette_index_zero_used": 0 in pixels,
                    **map_facts,
                    "canvas": {
                        "file": png_file,
                        "dimensions": [WIDTH_TILES * 8, HEIGHT_TILES * 8],
                        "pixel_sha256": sha256(pixels),
                        "sha256": sha256(png),
                    },
                    "hardware": {
                        "bgcnt": "0x0086",
                        "character_base": "0x06004000",
                        "screen_base": "0x06000000",
                        "hardware_canvas": [256, 256],
                        "visible_canvas": [240, 160],
                    },
                },
                "label": {
                    "entry_gba_address": _address(label_address),
                    "entry_sha256": sha256(label_record),
                    "raw_hex": label_record.hex(),
                    "record_file": label_record_file,
                    "glyph_count": len(glyphs),
                    "glyphs": glyphs,
                    "font_dependency": {
                        "schema": "dialogue-font-atlas-v2",
                        "manifest": "artifacts/dialogue-font-v2/manifest.json",
                        "manifest_sha256": FONT_MANIFEST_SHA256,
                        "rom_sha256": ROM_SHA256,
                        "all_glyphs_covered": True,
                    },
                    "preview": {
                        "file": label_png_file,
                        "dimensions": [32, 16],
                        "runtime_layout": (
                            "four 8x16 glyphs; each source record is two "
                            "vertically stacked 8x8 tiles"
                        ),
                        "palette_semantics": "palette-independent grayscale mask",
                        "pixel_sha256": sha256(label_pixels),
                        "sha256": sha256(label_png),
                    },
                },
            }
        )

    manifest = {
        "schema": SCHEMA,
        "rom": {
            "path": "rom/base.gba",
            "size": len(rom),
            "sha256": ROM_SHA256,
        },
        "source_tables": {
            "backgrounds": {
                "gba_address": _address(BACKGROUND_TABLE_ADDRESS),
                "entry_count": BACKGROUND_ENTRY_COUNT,
                "entry_size": BACKGROUND_ENTRY_SIZE,
                "sha256": BACKGROUND_TABLE_SHA256,
            },
            "labels": {
                "gba_address": _address(LABEL_TABLE_ADDRESS),
                "entry_count": BACKGROUND_ENTRY_COUNT,
                "entry_size": LABEL_ENTRY_SIZE,
                "sha256": LABEL_TABLE_SHA256,
            },
        },
        "consumer_evidence": consumer_evidence,
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "background_canvas_count": len(pages),
            "label_preview_count": len(pages),
            "unique_tilemap_count": len(map_hashes),
            "unique_label_glyph_count": len(GLYPH_SOURCES),
        },
        "scope": {
            "all_background_rows_exported": True,
            "all_label_rows_exported": True,
            "native_background_canvases_complete": True,
            "label_token_to_glyph_binding_complete": True,
            "label_font_graphics_already_covered": True,
            "runtime_label_palette_complete": False,
            "runtime_label_screen_position_complete": False,
            "selection_cursor_complete": False,
            "final_screen_composition_complete": False,
            "natural_language_label_names_complete": False,
        },
    }
    files["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    _replace_output(output_dir, files)
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/world-map-backgrounds-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manifest = export_artifact(args.root, args.output_dir)
    print(json.dumps(manifest["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
