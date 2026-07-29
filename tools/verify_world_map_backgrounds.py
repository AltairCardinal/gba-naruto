#!/usr/bin/env python3
"""Independently verify the deterministic world-map background artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import Any


ROM_BASE = 0x08000000
ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
SCHEMA = "world-map-backgrounds-v1"
BACKGROUND_TABLE_ADDRESS = 0x085A8014
BACKGROUND_TABLE_HASH = (
    "9ccd6d722b87a8bf910fb45072ad682d89b9cf3432979b163f57283902396f35"
)
LABEL_TABLE_ADDRESS = 0x085A8038
LABEL_TABLE_HASH = (
    "67b4a34289072f9a89b7f79721df851e6f23409d1c23dc4f90ae7f5d6130d052"
)
WIDTH_TILES = 30
HEIGHT_TILES = 20
PREVIEW_PALETTE = struct.pack("<4H", 0x0000, 0x294A, 0x56B5, 0x7FFF)
FONT_MANIFEST_HASH = (
    "a4b7abae4a5b2ad760b4225c514b198ddc3e2c5766e66d1e2f4e88d58575d1ef"
)

CONSUMERS = {
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

GLYPHS = {
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


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _address(value: int) -> str:
    return f"0x{value:08X}"


def _slice(rom: bytes, address: int, size: int) -> bytes:
    offset = address - ROM_BASE
    if offset < 0 or offset + size > len(rom):
        raise ValueError(f"invalid ROM range at {_address(address)}")
    return rom[offset : offset + size]


def _lz77_record_and_data(
    rom: bytes,
    pointer: int,
    expected_size: int,
) -> tuple[bytes, bytes]:
    cursor = pointer - ROM_BASE
    start = cursor
    if cursor < 0 or cursor + 4 > len(rom) or rom[cursor] != 0x10:
        raise ValueError(f"invalid LZ77 record at {_address(pointer)}")
    declared = int.from_bytes(rom[cursor + 1 : cursor + 4], "little")
    if declared != expected_size:
        raise ValueError(f"unexpected LZ77 size at {_address(pointer)}")
    cursor += 4
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
                    raise ValueError("truncated LZ77 reference")
                length = (rom[cursor] >> 4) + 3
                distance = (((rom[cursor] & 15) << 8) | rom[cursor + 1]) + 1
                cursor += 2
                if distance > len(output) or len(output) + length > declared:
                    raise ValueError("invalid LZ77 reference")
                for _ in range(length):
                    output.append(output[-distance])
            else:
                if cursor >= len(rom):
                    raise ValueError("truncated LZ77 literal")
                output.append(rom[cursor])
                cursor += 1
    return rom[start:cursor], bytes(output)


def _rgb(color: int) -> tuple[int, int, int]:
    return tuple(
        ((component << 3) | (component >> 2))
        for component in (color & 31, (color >> 5) & 31, (color >> 10) & 31)
    )


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _png(
    pixels: bytes,
    palette_raw: bytes,
    width: int,
    height: int,
    transparent: int | None = None,
) -> bytes:
    if len(pixels) != width * height:
        raise ValueError("PNG pixel size mismatch")
    palette = bytearray()
    for offset in range(0, len(palette_raw), 2):
        palette.extend(_rgb(struct.unpack_from("<H", palette_raw, offset)[0]))
    rows = b"".join(
        b"\0" + pixels[y * width : (y + 1) * width] for y in range(height)
    )
    chunks = [
        b"\x89PNG\r\n\x1a\n",
        _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)),
        _chunk(b"PLTE", bytes(palette)),
    ]
    if transparent is not None:
        alpha = bytearray([255] * (len(palette_raw) // 2))
        alpha[transparent] = 0
        chunks.append(_chunk(b"tRNS", bytes(alpha)))
    chunks.extend(
        (
            _chunk(b"IDAT", zlib.compress(rows, level=9)),
            _chunk(b"IEND", b""),
        )
    )
    return b"".join(chunks)


def _background_pixels(graphics: bytes, tilemap: bytes) -> tuple[bytes, dict[str, Any]]:
    entries = struct.unpack("<600H", tilemap)
    pixels = bytearray(240 * 160)
    referenced: set[int] = set()
    horizontal_flips = 0
    vertical_flips = 0
    banks: set[int] = set()
    for tile_y in range(20):
        for tile_x in range(30):
            entry = entries[tile_y * 30 + tile_x]
            tile_id = entry & 0x03FF
            if tile_id >= 512:
                raise ValueError("invalid tile index")
            referenced.add(tile_id)
            horizontal = bool(entry & 0x0400)
            vertical = bool(entry & 0x0800)
            horizontal_flips += int(horizontal)
            vertical_flips += int(vertical)
            banks.add(entry >> 12)
            for y in range(8):
                source_y = 7 - y if vertical else y
                for x in range(8):
                    source_x = 7 - x if horizontal else x
                    pixels[(tile_y * 8 + y) * 240 + tile_x * 8 + x] = graphics[
                        tile_id * 64 + source_y * 8 + source_x
                    ]
    missing = sorted(set(range(512)) - referenced)
    return bytes(pixels), {
        "referenced_tile_indices": sorted(referenced),
        "missing_tile_indices": missing,
        "all_tiles_referenced": not missing,
        "horizontal_flip_entry_count": horizontal_flips,
        "vertical_flip_entry_count": vertical_flips,
        "palette_bank_values": sorted(banks),
    }


def _glyph_pixels(source: bytes) -> bytes:
    output = bytearray()
    for half in range(2):
        for packed in source[half * 16 : (half + 1) * 16]:
            output.extend((packed >> shift) & 3 for shift in (0, 2, 4, 6))
    return bytes(output)


def _label_pixels(rom: bytes, codes: list[int]) -> tuple[bytes, list[dict[str, Any]]]:
    rows = [bytearray() for _ in range(16)]
    glyph_entries = []
    for code in codes:
        pointer, expected_hash = GLYPHS[code]
        source = _slice(rom, pointer, 32)
        if _hash(source) != expected_hash:
            raise ValueError("glyph source hash mismatch")
        pixels = _glyph_pixels(source)
        for y in range(16):
            rows[y].extend(pixels[y * 8 : (y + 1) * 8])
        glyph_entries.append(
            {
                "code": f"0x{code:04X}",
                "source_pointer": _address(pointer),
                "source_sha256": expected_hash,
                "source_format": "two-8x8-2bpp-half-tiles",
                "covered_by_dialogue_font_v2": True,
            }
        )
    return b"".join(rows), glyph_entries


def _expected(root: Path, rom: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    background_table = _slice(rom, BACKGROUND_TABLE_ADDRESS, 36)
    label_table = _slice(rom, LABEL_TABLE_ADDRESS, 48)
    if _hash(background_table) != BACKGROUND_TABLE_HASH:
        raise ValueError("background table hash mismatch")
    if _hash(label_table) != LABEL_TABLE_HASH:
        raise ValueError("label table hash mismatch")

    font_manifest_raw = (
        root / "artifacts/dialogue-font-v2/manifest.json"
    ).read_bytes()
    if _hash(font_manifest_raw) != FONT_MANIFEST_HASH:
        raise ValueError("font dependency manifest SHA-256 mismatch")
    font_manifest = json.loads(font_manifest_raw.decode("utf-8"))
    if (
        font_manifest.get("schema") != "dialogue-font-atlas-v2"
        or font_manifest.get("rom", {}).get("sha256") != ROM_SHA256
    ):
        raise ValueError("font dependency identity mismatch")
    covered = {
        entry["sjis_hex"]: (entry["source_pointer"], entry["source_sha256"])
        for entry in font_manifest["sjis_glyphs"]
    }
    for code, (pointer, source_hash) in GLYPHS.items():
        if covered.get(f"0x{code:04X}") != (_address(pointer), source_hash):
            raise ValueError("font dependency does not cover label glyph")

    evidence = {}
    for name, (start, end, digest) in CONSUMERS.items():
        code = _slice(rom, start, end - start)
        if _hash(code) != digest:
            raise ValueError("consumer evidence hash mismatch")
        evidence[name] = {
            "start": _address(start),
            "end_exclusive": _address(end),
            "size": len(code),
            "sha256": digest,
        }

    files: dict[str, bytes] = {}
    pages = []
    common_map: bytes | None = None
    map_hashes: set[str] = set()
    for page_id in range(3):
        entry = background_table[page_id * 12 : page_id * 12 + 12]
        graphics_pointer, map_pointer, palette_pointer = struct.unpack("<III", entry)
        compressed_graphics, graphics = _lz77_record_and_data(
            rom, graphics_pointer, 32768
        )
        compressed_map, tilemap = _lz77_record_and_data(rom, map_pointer, 1200)
        palette = _slice(rom, palette_pointer, 320)
        if common_map is None:
            common_map = tilemap
            files["shared/tilemap-30x20.bin"] = tilemap
        elif tilemap != common_map:
            raise ValueError("tilemaps are not identical")
        map_hashes.add(_hash(tilemap))
        pixels, facts = _background_pixels(graphics, tilemap)
        background_png = _png(pixels, palette, 240, 160)
        prefix = f"page-{page_id:02d}"
        graphics_file = f"{prefix}/background.8bpp.bin"
        palette_file = f"{prefix}/palette.bgr555.bin"
        background_file = f"{prefix}/background.png"
        files[graphics_file] = graphics
        files[palette_file] = palette
        files[background_file] = background_png

        label_record = label_table[page_id * 16 : page_id * 16 + 16]
        if label_record[8] != 0 or any(label_record[9:]):
            raise ValueError("invalid label terminator")
        codes = list(struct.unpack(">4H", label_record[:8]))
        label_pixels, glyph_entries = _label_pixels(rom, codes)
        label_png = _png(label_pixels, PREVIEW_PALETTE, 32, 16, 0)
        label_record_file = f"{prefix}/label-record.bin"
        label_png_file = f"{prefix}/label-preview.png"
        files[label_record_file] = label_record
        files[label_png_file] = label_png
        pages.append(
            {
                "page_id": page_id,
                "entry_gba_address": _address(BACKGROUND_TABLE_ADDRESS + page_id * 12),
                "entry_sha256": _hash(entry),
                "raw_hex": entry.hex(),
                "background": {
                    "bits_per_pixel": 8,
                    "graphics_pointer": _address(graphics_pointer),
                    "graphics_compressed_size": len(compressed_graphics),
                    "graphics_compressed_sha256": _hash(compressed_graphics),
                    "graphics_file": graphics_file,
                    "graphics_sha256": _hash(graphics),
                    "tile_count": 512,
                    "tilemap_pointer": _address(map_pointer),
                    "tilemap_compressed_size": len(compressed_map),
                    "tilemap_compressed_sha256": _hash(compressed_map),
                    "tilemap_file": "shared/tilemap-30x20.bin",
                    "tilemap_sha256": _hash(tilemap),
                    "palette_pointer": _address(palette_pointer),
                    "palette_file": palette_file,
                    "palette_sha256": _hash(palette),
                    "palette_color_count": 160,
                    "dimensions_tiles": [30, 20],
                    "maximum_pixel_index": max(pixels),
                    "minimum_pixel_index": min(pixels),
                    "palette_index_zero_used": 0 in pixels,
                    **facts,
                    "canvas": {
                        "file": background_file,
                        "dimensions": [240, 160],
                        "pixel_sha256": _hash(pixels),
                        "sha256": _hash(background_png),
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
                    "entry_gba_address": _address(LABEL_TABLE_ADDRESS + page_id * 16),
                    "entry_sha256": _hash(label_record),
                    "raw_hex": label_record.hex(),
                    "record_file": label_record_file,
                    "glyph_count": 4,
                    "glyphs": glyph_entries,
                    "font_dependency": {
                        "schema": "dialogue-font-atlas-v2",
                        "manifest": "artifacts/dialogue-font-v2/manifest.json",
                        "manifest_sha256": FONT_MANIFEST_HASH,
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
                        "pixel_sha256": _hash(label_pixels),
                        "sha256": _hash(label_png),
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
                "entry_count": 3,
                "entry_size": 12,
                "sha256": BACKGROUND_TABLE_HASH,
            },
            "labels": {
                "gba_address": _address(LABEL_TABLE_ADDRESS),
                "entry_count": 3,
                "entry_size": 16,
                "sha256": LABEL_TABLE_HASH,
            },
        },
        "consumer_evidence": evidence,
        "pages": pages,
        "summary": {
            "page_count": 3,
            "background_canvas_count": 3,
            "label_preview_count": 3,
            "unique_tilemap_count": len(map_hashes),
            "unique_label_glyph_count": len(GLYPHS),
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
    return manifest, files


def verify_artifact(
    root: Path | str,
    artifact_dir: Path | str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    artifact_dir = Path(artifact_dir).resolve()
    errors: list[str] = []
    try:
        rom = (root / "rom/base.gba").read_bytes()
        if _hash(rom) != ROM_SHA256:
            raise ValueError("base ROM SHA-256 mismatch")
        expected_manifest, expected_files = _expected(root, rom)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return {
            "verified": False,
            "page_count": 0,
            "errors": [str(error)],
        }

    actual_files = {
        path.relative_to(artifact_dir).as_posix()
        for path in artifact_dir.rglob("*")
        if path.is_file()
    }
    expected_names = set(expected_files)
    for missing in sorted(expected_names - actual_files):
        errors.append(f"missing file: {missing}")
    for unexpected in sorted(actual_files - expected_names):
        errors.append(f"unexpected file: {unexpected}")
    for relative, expected in sorted(expected_files.items()):
        path = artifact_dir / relative
        if path.is_file() and path.read_bytes() != expected:
            errors.append(f"content mismatch: {relative}")
    try:
        actual_manifest = json.loads(
            (artifact_dir / "manifest.json").read_text(encoding="utf-8")
        )
        if actual_manifest != expected_manifest:
            errors.append("manifest semantics mismatch")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"manifest parse failed: {error}")
    return {
        "verified": not errors,
        "page_count": len(expected_manifest["pages"]),
        "errors": errors,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/world-map-backgrounds-v1"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = verify_artifact(args.root, args.artifact_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
