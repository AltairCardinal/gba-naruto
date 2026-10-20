#!/usr/bin/env python3
"""Land the original S49 move-range overlay graphics as a Butano asset.

The original game's move-range overlay of 《火影忍者 - 木叶战记》 stage S49
(木叶丸与野蜂) is a dedicated GBA background layer (BG2) that owns its own
4bpp tile set and its own 16 colour palette.  Both payloads live in the ROM as
two adjacent LZ77 records:

* ``0x080B9E94`` -> 198 compressed bytes -> 1024 bytes = 32 tiles of 4bpp
  (SHA-256 ``0f86c803...``), resident at VRAM ``0x06002000``;
* ``0x080B9F5C`` -> 36 compressed bytes -> 32 bytes = 16 BGR555 entries
  (SHA-256 ``d198ec85...``), resident at PRAM ``0x05000180`` (palette bank 12).

This generator lifts both payloads out of the pinned ROM and writes them into
the remake's asset pipeline:

* ``butano-sequel/graphics/battle_movegrid_overlay_tiles.bmp`` -- an
  uncompressed 4bpp indexed bitmap, 64x32 pixels = 8 columns x 4 rows of 8x8
  tiles with tile 256 at the top-left;
* ``butano-sequel/graphics/battle_movegrid_overlay_tiles.json`` -- the
  Butano graphics descriptor plus the ROM provenance of every input;
* ``butano-sequel/game/include/konoha/generated_battle_movegrid_overlay_content.h``
  -- the palette (5-bit and 8-bit), the 32 tile indices and the tile bytes as
  ``constexpr`` data a C++ side can hand to Butano.

The generator is deliberately fail-closed and deterministic:

* the ROM is pinned by SHA-256 and the run is refused on any mismatch, before
  a single output file is created;
* the LZ77 records are decoded with the reverse tree's working decoder (the
  textbook GBA LZ77 layout does **not** decode these blobs) and the
  decompressed length and digest must match the expected values exactly;
* no timestamp is written anywhere, so two runs produce byte-identical files.

Nothing here establishes *which* tile the game puts in *which* tilemap cell:
the tile selection rule is owned by another agent (see
``notes/s49-movegrid-overlay-implementation-spec-20261020.md``).  This file
only carries the graphics and the palette.

Usage::

    /usr/local/bin/python3 tools/generate_butano_movegrid_overlay_assets.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit_butano_reverse_provenance import provenance_block
from tools.butano.export_s49_movegrid_overlay import lz77_decompress
from tools.butano.indexed_bmp import write_4bpp_bmp

#: The reverse result that records both LZ77 records of this overlay.  The
#: auditor resolves the family in the reverse work tree, re-hashes its signed
#: manifest and checks that the consumed ROM regions are the ones it records.
PROVENANCE = provenance_block(
    sources=(
        (
            "rom-pointer-lz77-inventory-v1",
            "d4afca9d19c3b764ce40f460d9c73d7c19f908bf25c197d4b082bd6bc5c4bb33",
        ),
    ),
    roms=(
        (
            0x0B9E94,
            198,
            "b4e197b91b4e6a3d7650a02d785af8fc37e1083c0b67d5355966b3fd8a85c733",
        ),
        (
            0x0B9F5C,
            36,
            "2e1e27099e8bbed038c35e677aefa9c90a754ea1423f7e653c5c1ba52585967b",
        ),
    ),
)

#: The products the provenance auditor reads back.  The auditor parses every
#: registered product as text and requires the C++ comment carrier in it, so
#: only the text product can be registered; the binary bitmap and the JSON
#: sidecar are declared in :data:`AUXILIARY_PRODUCTS` instead.
GENERATED_PRODUCTS = (
    "butano-sequel/game/include/konoha/"
    "generated_battle_movegrid_overlay_content.h",
)

#: The remaining files this generator writes.  They are declared here so the
#: product set of the generator stays complete and machine checkable.
AUXILIARY_PRODUCTS = (
    "butano-sequel/graphics/battle_movegrid_overlay_tiles.bmp",
    "butano-sequel/graphics/battle_movegrid_overlay_tiles.json",
)

EXPECTED_ROM_SHA256 = (
    "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
)

ROM_BASE = 0x08000000

# --- the two LZ77 records -------------------------------------------------
TILES_ROM_ADDRESS = 0x080B9E94
TILES_FILE_OFFSET = TILES_ROM_ADDRESS - ROM_BASE
TILES_COMPRESSED_BYTES = 198
TILES_DECOMPRESSED_BYTES = 1024
TILES_DECOMPRESSED_SHA256 = (
    "0f86c8032129ef1b92fb1464c516a03b1c0ca71672ac5de4d37e8b302cf6ce40"
)

PALETTE_ROM_ADDRESS = 0x080B9F5C
PALETTE_FILE_OFFSET = PALETTE_ROM_ADDRESS - ROM_BASE
PALETTE_COMPRESSED_BYTES = 36
PALETTE_DECOMPRESSED_BYTES = 32
PALETTE_DECOMPRESSED_SHA256 = (
    "d198ec85eff147b157978bb44d1948db5b9893edb5f8f63d4d9b96b5ca7e7e84"
)

# --- the tile set ---------------------------------------------------------
TILE_COUNT = 32
TILE_BYTES = 32
BASE_TILE_INDEX = 256
SHEET_COLS = 8
SHEET_ROWS = 4
SHEET_WIDTH = SHEET_COLS * 8
SHEET_HEIGHT = SHEET_ROWS * 8

# --- the palette ----------------------------------------------------------
PALETTE_ENTRIES = 16
PALETTE_BANK = 12
PRAM_PALETTE_DEST = 0x05000180
VRAM_TILES_DEST = 0x06002000

# --- the outputs ----------------------------------------------------------
GRAPHICS_BMP_NAME = "battle_movegrid_overlay_tiles.bmp"
GRAPHICS_JSON_NAME = "battle_movegrid_overlay_tiles.json"
HEADER_NAME = "generated_battle_movegrid_overlay_content.h"

DEFAULT_ROM_PATH = Path("rom") / "base.gba"
DEFAULT_GRAPHICS_DIR = Path("butano-sequel") / "graphics"
DEFAULT_HEADER_PATH = (
    Path("butano-sequel")
    / "game"
    / "include"
    / "konoha"
    / HEADER_NAME
)

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_ROM_HASH = 2
EXIT_DECODE = 3


class GenerationError(Exception):
    """A fail-closed refusal with the process exit code it maps to."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bgr555_to_rgb8(value: int) -> tuple[int, int, int]:
    """Convert one BGR555 entry to 8-bit RGB with the ``(c << 3) | (c >> 2)`` rule."""
    red = value & 0x1F
    green = (value >> 5) & 0x1F
    blue = (value >> 10) & 0x1F
    return (
        (red << 3) | (red >> 2),
        (green << 3) | (green >> 2),
        (blue << 3) | (blue >> 2),
    )


def decode_palette(payload: bytes) -> list[dict[str, Any]]:
    """Decode the 16 BGR555 entries of the overlay's palette bank."""
    if len(payload) != PALETTE_DECOMPRESSED_BYTES:
        raise GenerationError(
            f"the palette payload is {len(payload)} bytes, expected "
            f"{PALETTE_DECOMPRESSED_BYTES}",
            EXIT_DECODE,
        )
    entries: list[dict[str, Any]] = []
    for index in range(PALETTE_ENTRIES):
        raw = payload[index * 2] | (payload[index * 2 + 1] << 8)
        red, green, blue = bgr555_to_rgb8(raw)
        entries.append(
            {
                "index": index,
                "bgr555": f"0x{raw:04X}",
                "rgb5": [raw & 0x1F, (raw >> 5) & 0x1F, (raw >> 10) & 0x1F],
                "rgb8": [red, green, blue],
            }
        )
    return entries


def build_sheet(payload: bytes) -> list[int]:
    """Lay the 32 tiles out as an 8x4 grid of 8x8 tiles (64x32 pixels).

    The returned list is in image order (top row first), which is the order
    :func:`tools.butano.indexed_bmp.write_4bpp_bmp` expects.
    """
    if len(payload) != TILE_COUNT * TILE_BYTES:
        raise GenerationError(
            f"the tile payload is {len(payload)} bytes, expected "
            f"{TILE_COUNT * TILE_BYTES}",
            EXIT_DECODE,
        )
    sheet = [0] * (SHEET_WIDTH * SHEET_HEIGHT)
    for blob_index in range(TILE_COUNT):
        origin_x = (blob_index % SHEET_COLS) * 8
        origin_y = (blob_index // SHEET_COLS) * 8
        base = blob_index * TILE_BYTES
        for y in range(8):
            row = payload[base + y * 4 : base + y * 4 + 4]
            for x in range(8):
                packed = row[x // 2]
                value = packed >> 4 if x % 2 == 0 else packed & 0x0F
                sheet[(origin_y + y) * SHEET_WIDTH + origin_x + x] = value
    return sheet


def load_payloads(rom_path: Path | str) -> dict[str, Any]:
    """Read the ROM and lift both LZ77 records out of it.

    Every check happens before a single output byte is produced.
    """
    rom_path = Path(rom_path)
    if not rom_path.is_file():
        raise GenerationError(f"ROM not found: {rom_path}", EXIT_ROM_HASH)
    rom = rom_path.read_bytes()
    rom_sha256 = sha256_bytes(rom)
    if rom_sha256 != EXPECTED_ROM_SHA256:
        raise GenerationError(
            f"ROM SHA-256 mismatch for {rom_path}: got {rom_sha256}, expected "
            f"{EXPECTED_ROM_SHA256}; refusing to generate",
            EXIT_ROM_HASH,
        )

    try:
        tiles, tiles_end = lz77_decompress(
            rom, TILES_FILE_OFFSET, expected_bytes=TILES_DECOMPRESSED_BYTES
        )
        palette, palette_end = lz77_decompress(
            rom, PALETTE_FILE_OFFSET, expected_bytes=PALETTE_DECOMPRESSED_BYTES
        )
    except Exception as error:  # the exporter's own fail-closed error
        raise GenerationError(
            f"the overlay LZ77 records did not decode: {error}", EXIT_DECODE
        ) from error

    tiles_sha256 = sha256_bytes(tiles)
    if tiles_sha256 != TILES_DECOMPRESSED_SHA256:
        raise GenerationError(
            f"the tile payload at 0x{TILES_ROM_ADDRESS:08X} hashes to "
            f"{tiles_sha256}, expected {TILES_DECOMPRESSED_SHA256}",
            EXIT_DECODE,
        )
    palette_sha256 = sha256_bytes(palette)
    if palette_sha256 != PALETTE_DECOMPRESSED_SHA256:
        raise GenerationError(
            f"the palette payload at 0x{PALETTE_ROM_ADDRESS:08X} hashes to "
            f"{palette_sha256}, expected {PALETTE_DECOMPRESSED_SHA256}",
            EXIT_DECODE,
        )

    return {
        "rom": rom,
        "rom_sha256": rom_sha256,
        "tiles": tiles,
        "tiles_sha256": tiles_sha256,
        "tiles_end": tiles_end,
        "palette": palette,
        "palette_sha256": palette_sha256,
        "palette_end": palette_end,
    }


def _sidecar(payloads: dict[str, Any]) -> dict[str, Any]:
    """The Butano graphics descriptor plus the ROM provenance."""
    rom = payloads["rom"]
    entries = decode_palette(payloads["palette"])
    layout = []
    for blob_index in range(TILE_COUNT):
        layout.append(
            {
                "blob_index": blob_index,
                "tile_index": BASE_TILE_INDEX + blob_index,
                "sheet_col": blob_index % SHEET_COLS,
                "sheet_row": blob_index // SHEET_COLS,
                "x": (blob_index % SHEET_COLS) * 8,
                "y": (blob_index // SHEET_COLS) * 8,
            }
        )
    return {
        "type": "regular_bg_tiles",
        "bpp_mode": "bpp_4",
        "generate_palette": True,
        "palette_colors_count": PALETTE_ENTRIES,
        "compression": "none",
        "palette_compression": "none",
        "schema": "konoha.s49-movegrid-overlay-asset.v1",
        "generated_by": "tools/generate_butano_movegrid_overlay_assets.py",
        "source": f"rom/base.gba:0x{TILES_ROM_ADDRESS:08X}+{TILES_COMPRESSED_BYTES}",
        "rom": {
            "path": "rom/base.gba",
            "sha256": EXPECTED_ROM_SHA256,
        },
        "blobs": {
            "tiles": {
                "rom_address": f"0x{TILES_ROM_ADDRESS:08X}",
                "file_offset": TILES_FILE_OFFSET,
                "compressed_bytes": TILES_COMPRESSED_BYTES,
                "compressed_span": [
                    f"0x{TILES_ROM_ADDRESS:08X}",
                    f"0x{ROM_BASE + payloads['tiles_end']:08X}",
                ],
                "compressed_sha256": sha256_bytes(
                    rom[TILES_FILE_OFFSET : payloads["tiles_end"]]
                ),
                "decompressed_bytes": len(payloads["tiles"]),
                "decompressed_sha256": payloads["tiles_sha256"],
            },
            "palette": {
                "rom_address": f"0x{PALETTE_ROM_ADDRESS:08X}",
                "file_offset": PALETTE_FILE_OFFSET,
                "compressed_bytes": PALETTE_COMPRESSED_BYTES,
                "compressed_span": [
                    f"0x{PALETTE_ROM_ADDRESS:08X}",
                    f"0x{ROM_BASE + payloads['palette_end']:08X}",
                ],
                "compressed_sha256": sha256_bytes(
                    rom[PALETTE_FILE_OFFSET : payloads["palette_end"]]
                ),
                "decompressed_bytes": len(payloads["palette"]),
                "decompressed_sha256": payloads["palette_sha256"],
            },
        },
        "tiles": {
            "bpp": 4,
            "tile_count": TILE_COUNT,
            "tile_bytes": TILE_BYTES,
            "base_tile_index": BASE_TILE_INDEX,
            "vram_destination": f"0x{VRAM_TILES_DEST:08X}",
            "sheet": {
                "cols": SHEET_COLS,
                "rows": SHEET_ROWS,
                "width": SHEET_WIDTH,
                "height": SHEET_HEIGHT,
            },
            "layout": layout,
        },
        "palette": {
            "bank": PALETTE_BANK,
            "pram_destination": f"0x{PRAM_PALETTE_DEST:08X}",
            "entry_count": PALETTE_ENTRIES,
            "conversion": "8-bit = (c << 3) | (c >> 2) on each 5-bit channel",
            "entries": entries,
        },
        "scope": {
            "established": [
                "The 32 tiles and the 16 colour palette of the generated "
                "assets are the decompressed ROM payloads, byte for byte.",
                "The bitmap lays the tiles out as the original's VRAM order: "
                "tile 256 first, 8 columns by 4 rows.",
                "The 8-bit palette values keep their 5-bit channel exactly, so "
                "the bitmap's palette is the original's palette bank 12.",
            ],
            "not_established": [
                "Which tile the game puts in which tilemap cell: the tile "
                "selection rule is not derived here.",
                "Whether the overlay marks reachable or unreachable ground.",
                "Whether the layer is reached by natural execution.",
            ],
        },
    }


def _header(payloads: dict[str, Any]) -> str:
    """The generated C++ header with the palette and the tile bytes."""
    entries = decode_palette(payloads["palette"])
    tiles = payloads["tiles"]

    rgb5_lines = "\n".join(
        f"    {{ {entry['rgb5'][0]}, {entry['rgb5'][1]}, {entry['rgb5'][2]} }},"
        for entry in entries
    )
    rgb8_lines = "\n".join(
        f"    {{ {entry['rgb8'][0]}, {entry['rgb8'][1]}, {entry['rgb8'][2]} }},"
        for entry in entries
    )
    bgr555_lines = "\n".join(
        f"    0x{entry['bgr555'][4:]}," for entry in entries
    )
    index_lines = "\n".join(
        f"    {BASE_TILE_INDEX + index}," for index in range(TILE_COUNT)
    )
    byte_lines = "\n".join(
        "    "
        + ", ".join(f"0x{value:02X}" for value in tiles[offset : offset + 16])
        + ","
        for offset in range(0, len(tiles), 16)
    )
    word_lines = "\n".join(
        "    0x{:08X},".format(
            int.from_bytes(tiles[offset : offset + 4], "little")
        )
        for offset in range(0, len(tiles), 4)
    )

    return f"""// Generated by tools/generate_butano_movegrid_overlay_assets.py.
// Do not edit.
{PROVENANCE}
#ifndef KONOHA_GENERATED_BATTLE_MOVEGRID_OVERLAY_CONTENT_H
#define KONOHA_GENERATED_BATTLE_MOVEGRID_OVERLAY_CONTENT_H

#include <array>
#include <cstdint>

namespace konoha
{{

struct battle_movegrid_overlay_rgb5
{{
    int red = 0;
    int green = 0;
    int blue = 0;

    constexpr bool operator==(
            const battle_movegrid_overlay_rgb5&) const = default;
}};

struct battle_movegrid_overlay_rgb8
{{
    int red = 0;
    int green = 0;
    int blue = 0;

    constexpr bool operator==(
            const battle_movegrid_overlay_rgb8&) const = default;
}};

inline constexpr int battle_movegrid_overlay_palette_size = {PALETTE_ENTRIES};
inline constexpr int battle_movegrid_overlay_tile_count = {TILE_COUNT};
inline constexpr int battle_movegrid_overlay_tile_bytes = {TILE_BYTES};
inline constexpr int battle_movegrid_overlay_base_tile_index = {BASE_TILE_INDEX};
inline constexpr int battle_movegrid_overlay_sheet_cols = {SHEET_COLS};
inline constexpr int battle_movegrid_overlay_sheet_rows = {SHEET_ROWS};
inline constexpr int battle_movegrid_overlay_sheet_width = {SHEET_WIDTH};
inline constexpr int battle_movegrid_overlay_sheet_height = {SHEET_HEIGHT};
inline constexpr int battle_movegrid_overlay_palette_bank = {PALETTE_BANK};
inline constexpr int battle_movegrid_overlay_rom_address_tiles =
        0x{TILES_ROM_ADDRESS:08X};
inline constexpr int battle_movegrid_overlay_rom_address_palette =
        0x{PALETTE_ROM_ADDRESS:08X};
inline constexpr int battle_movegrid_overlay_vram_destination =
        0x{VRAM_TILES_DEST:08X};
inline constexpr int battle_movegrid_overlay_pram_destination =
        0x{PRAM_PALETTE_DEST:08X};

// The original palette bank 12, in 5-bit channels: these are the values a
// Butano bn::color(red, green, blue) takes.
inline constexpr std::array<battle_movegrid_overlay_rgb5, {PALETTE_ENTRIES}>
        battle_movegrid_overlay_palette_rgb5 = {{{{
{rgb5_lines}
}}}};

// The same palette widened to 8 bits with the (c << 3) | (c >> 2) rule, which
// is what the generated bitmap carries.  The 5-bit channels survive that
// widening exactly: rgb8 >> 3 == rgb5.
inline constexpr std::array<battle_movegrid_overlay_rgb8, {PALETTE_ENTRIES}>
        battle_movegrid_overlay_palette_rgb8 = {{{{
{rgb8_lines}
}}}};

// The raw palette bank, BGR555 little endian.
inline constexpr std::array<std::uint16_t, {PALETTE_ENTRIES}>
        battle_movegrid_overlay_palette_bgr555 = {{{{
{bgr555_lines}
}}}};

// The tile indices the overlay owns: 256..287, in VRAM order.
inline constexpr std::array<std::uint16_t, {TILE_COUNT}>
        battle_movegrid_overlay_tile_indices = {{{{
{index_lines}
}}}};

// The 1024 bytes of 4bpp tile data, in VRAM order: 32 tiles of 8 rows of 4
// bytes, the high nibble of every byte being the left pixel.
alignas(4) inline constexpr std::array<std::uint8_t, {len(tiles)}>
        battle_movegrid_overlay_tile_data = {{{{
{byte_lines}
}}}};

// The same 1024 bytes as 256 little endian words: 32 tiles x 8 words, which
// is the layout of bn::tile (uint32_t data[8]).  A C++ side can hand this
// array to Butano as
// bn::span<const bn::tile>(reinterpret_cast<const bn::tile*>(
//     battle_movegrid_overlay_tile_words.data()), 32).
inline constexpr std::array<std::uint32_t, {len(tiles) // 4}>
        battle_movegrid_overlay_tile_words = {{{{
{word_lines}
}}}};

[[nodiscard]] inline constexpr bool
battle_movegrid_overlay_tile_views_agree()
{{
    for(int index = 0; index < {len(tiles) // 4}; ++index)
    {{
        for(int byte = 0; byte < 4; ++byte)
        {{
            const std::uint8_t expected = static_cast<std::uint8_t>(
                    battle_movegrid_overlay_tile_words[index] >> (byte * 8));
            if(expected !=
                    battle_movegrid_overlay_tile_data[index * 4 + byte])
            {{
                return false;
            }}
        }}
    }}
    return true;
}}

static_assert(battle_movegrid_overlay_tile_views_agree());

}}

#endif
"""


def generate(
    rom_path: Path | str,
    graphics_dir: Path | str,
    header_path: Path | str,
) -> dict[str, Any]:
    """Generate the bitmap, the sidecar and the C++ header."""
    payloads = load_payloads(rom_path)
    graphics_dir = Path(graphics_dir)
    header_path = Path(header_path)

    sheet = build_sheet(payloads["tiles"])
    entries = decode_palette(payloads["palette"])
    palette_rgb8 = [tuple(entry["rgb8"]) for entry in entries]
    sidecar = _sidecar(payloads)
    header = _header(payloads)

    graphics_dir.mkdir(parents=True, exist_ok=True)
    header_path.parent.mkdir(parents=True, exist_ok=True)

    bmp_path = graphics_dir / GRAPHICS_BMP_NAME
    json_path = graphics_dir / GRAPHICS_JSON_NAME
    write_4bpp_bmp(
        bmp_path,
        SHEET_WIDTH,
        SHEET_HEIGHT,
        sheet,
        palette_rgb8,
    )
    json_path.write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    header_path.write_text(header, encoding="utf-8")

    return {
        "rom_sha256": payloads["rom_sha256"],
        "tiles_sha256": payloads["tiles_sha256"],
        "palette_sha256": payloads["palette_sha256"],
        "bmp": bmp_path,
        "json": json_path,
        "header": header_path,
        "bmp_bytes": bmp_path.stat().st_size,
        "json_bytes": json_path.stat().st_size,
        "header_bytes": header_path.stat().st_size,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        default=DEFAULT_ROM_PATH,
        help="the pinned ROM the overlay is lifted from",
    )
    parser.add_argument(
        "--graphics-dir",
        type=Path,
        default=DEFAULT_GRAPHICS_DIR,
        help="the directory the bitmap and the sidecar are written to",
    )
    parser.add_argument(
        "--header",
        type=Path,
        default=DEFAULT_HEADER_PATH,
        help="the generated C++ header",
    )
    args = parser.parse_args(argv)
    try:
        result = generate(args.rom, args.graphics_dir, args.header)
    except GenerationError as error:
        print(f"refused: {error}", file=sys.stderr)
        return error.code
    print(
        f"rom        {args.rom}  sha256={result['rom_sha256']}"
    )
    print(
        f"tiles      0x{TILES_ROM_ADDRESS:08X} -> {TILES_DECOMPRESSED_BYTES} B  "
        f"sha256={result['tiles_sha256']}"
    )
    print(
        f"palette    0x{PALETTE_ROM_ADDRESS:08X} -> {PALETTE_DECOMPRESSED_BYTES} B  "
        f"sha256={result['palette_sha256']}"
    )
    print(f"bmp        {result['bmp']}  {result['bmp_bytes']} B")
    print(f"sidecar    {result['json']}  {result['json_bytes']} B")
    print(f"header     {result['header']}  {result['header_bytes']} B")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
