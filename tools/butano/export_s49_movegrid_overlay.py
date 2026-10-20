#!/usr/bin/env python3
"""Export the original S49 move-range overlay (BG2) tiles and palette out of the ROM.

The move-range overlay of 《火影忍者 - 木叶战记》 stage S49 (木叶丸与野蜂) is a
dedicated GBA background layer (BG2, switched on by ``DISPCNT`` bit 10).  It owns
its own tile set and its own palette bank, and both live in the ROM as two
adjacent LZ77 records:

* ``0x080B9E94`` -> 1024 bytes = 32 tiles of 4bpp, loaded to VRAM
  ``0x06002000`` (= BG2 char base ``0x06000000`` + tile 256);
* ``0x080B9F5C`` -> 32 bytes = one 16-entry palette, loaded to PRAM
  ``0x05000180`` (= palette bank 12).

This exporter lifts both payloads into machine readable form and records every
input hash, so the export can be re-derived and re-checked without an
emulator.  It is deliberately fail-closed:

* the ROM is pinned by SHA-256 and the run is refused on any mismatch;
* the LZ77 stream is decoded with strict bounds checks and the decompressed
  length must match the expected size exactly;
* ``--verify`` re-reads the written artifacts, re-hashes them and re-decodes
  the ROM, and fails on any drift.

Nothing here is established about *runtime* behaviour: which tilemap cells the
game lights up, whether the overlay means "reachable" or "unreachable", and
whether the layer is ever reached naturally are all recorded as **not
established** in the manifest's ``scope`` block.

Usage::

    /usr/local/bin/python3 tools/butano/export_s49_movegrid_overlay.py \\
        --rom "火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba" \\
        --out-dir artifacts/s49-original-movegrid-overlay-v1 \\
        --evidence-dir artifacts/s49-original-movegrid-frame-v1 \\
        --evidence-baseline artifacts/s49-original-field-frame-v1

    /usr/local/bin/python3 tools/butano/export_s49_movegrid_overlay.py --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "konoha.s49-movegrid-overlay.v1"

EXPECTED_ROM_SHA256 = "1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b"
DEFAULT_ROM_NAME = "火影忍者 - 木叶战记[熊组](v1.3)(简)(JP)(48Mb).gba"

# --- ROM source records (see notes/s49-dispcnt-bit10-layer-20261020.md) -------
TILES_ROM_ADDRESS = 0x080B9E94
TILES_EXPECTED_BYTES = 1024  # 32 tiles x 32 bytes, 4bpp
PALETTE_ROM_ADDRESS = 0x080B9F5C
PALETTE_EXPECTED_BYTES = 32  # 16 BGR555 entries

# --- VRAM / PRAM placement ---------------------------------------------------
TILE_COUNT = 32
TILE_BYTES = 32
BASE_TILE_INDEX = 256
SHEET_COLS = 8
SHEET_ROWS = 4
SHEET_WIDTH = SHEET_COLS * 8
SHEET_HEIGHT = SHEET_ROWS * 8
BG_CHAR_BASE = 0x06000000
VRAM_TILES_DEST = 0x06002000
PRAM_PALETTE_DEST = 0x05000180
PALETTE_BANK = 12
PALETTE_ENTRIES = 16

# Byte windows inside a same-frame VRAM / PRAM dump that must carry the payload.
VRAM_TILES_WINDOW = (0x2000, 0x2400)
PRAM_PALETTE_WINDOW = (0x180, 0x1A0)
BG2_TILEMAP_WINDOW = (0x1000, 0x1800)
BG2_TILEMAP_CELLS = 1024

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "s49-original-movegrid-overlay-v1"

OUTPUT_TILES_BIN = "movegrid-tiles-4bpp.bin"
OUTPUT_TILES_INDEX_PNG = "movegrid-tiles-index.png"
OUTPUT_TILES_RENDER_PNG = "movegrid-tiles-render.png"
OUTPUT_PALETTE_BIN = "movegrid-palette.bin"
OUTPUT_PALETTE_JSON = "movegrid-palette.json"
OUTPUT_MANIFEST = "manifest.json"

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_ROM_HASH = 2
EXIT_DECODE = 3
EXIT_EVIDENCE = 4
EXIT_VERIFY = 5


class ExportError(Exception):
    """A fail-closed refusal with the process exit code it maps to."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# LZ77
# --------------------------------------------------------------------------
def lz77_decompress(rom: bytes, offset: int, *, expected_bytes: int) -> tuple[bytes, int]:
    """Decode the LZ77 record at ``offset``.

    The token layout is the one this title's ROM actually uses and that the
    reverse tree's signed LZ77 inventory uses
    (``reverse/tools/export_rom_pointer_lz77_inventory.py``):

    * header: ``0x10`` then a 24-bit little-endian decompressed size;
    * one flag byte, bits consumed from bit 7 down to bit 0;
    * flag bit ``0`` -> one literal byte;
    * flag bit ``1`` -> two bytes ``first``/``second`` describing a back
      reference, where ``length = (first >> 4) + 3`` and
      ``distance = (((first & 0x0F) << 8) | second) + 1``.

    Returns the payload and the offset of the first byte *after* the
    compressed record.  Every failure raises :class:`ExportError`.
    """
    if offset < 0 or offset + 4 > len(rom):
        raise ExportError(
            f"LZ77 record at 0x{offset:08X} is outside the ROM", EXIT_DECODE
        )
    if rom[offset] != 0x10:
        raise ExportError(
            f"LZ77 record at 0x{offset:08X} has header byte "
            f"0x{rom[offset]:02X}, expected 0x10",
            EXIT_DECODE,
        )
    declared = int.from_bytes(rom[offset + 1 : offset + 4], "little")
    if declared != expected_bytes:
        raise ExportError(
            f"LZ77 record at 0x{offset:08X} declares {declared} decompressed "
            f"bytes, expected {expected_bytes}",
            EXIT_DECODE,
        )
    cursor = offset + 4
    out = bytearray()
    while len(out) < declared:
        if cursor >= len(rom):
            raise ExportError(
                f"LZ77 record at 0x{offset:08X} runs past the end of the ROM",
                EXIT_DECODE,
            )
        flags = rom[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if len(out) >= declared:
                break
            if flags & (1 << bit):
                if cursor + 2 > len(rom):
                    raise ExportError(
                        f"LZ77 record at 0x{offset:08X} is truncated inside a "
                        f"match token",
                        EXIT_DECODE,
                    )
                first = rom[cursor]
                second = rom[cursor + 1]
                cursor += 2
                length = (first >> 4) + 3
                distance = (((first & 0x0F) << 8) | second) + 1
                if distance > len(out):
                    raise ExportError(
                        f"LZ77 record at 0x{offset:08X} references distance "
                        f"{distance} with only {len(out)} bytes produced",
                        EXIT_DECODE,
                    )
                if len(out) + length > declared:
                    raise ExportError(
                        f"LZ77 record at 0x{offset:08X} would overrun the "
                        f"declared size {declared}",
                        EXIT_DECODE,
                    )
                for _ in range(length):
                    out.append(out[-distance])
            else:
                if cursor >= len(rom):
                    raise ExportError(
                        f"LZ77 record at 0x{offset:08X} is truncated inside a "
                        f"literal",
                        EXIT_DECODE,
                    )
                out.append(rom[cursor])
                cursor += 1
    if len(out) != expected_bytes:
        raise ExportError(
            f"LZ77 record at 0x{offset:08X} produced {len(out)} bytes, "
            f"expected {expected_bytes}",
            EXIT_DECODE,
        )
    return bytes(out), cursor


# --------------------------------------------------------------------------
# 4bpp tiles / palette
# --------------------------------------------------------------------------
def decode_tile_4bpp(payload: bytes, blob_index: int) -> list[list[int]]:
    """Return the 8x8 colour-index matrix of one 4bpp tile.

    A GBA 4bpp tile is 8 rows of 4 bytes; every byte carries two pixels and
    the high nibble comes first.
    """
    base = blob_index * TILE_BYTES
    if base + TILE_BYTES > len(payload):
        raise ExportError(
            f"tile {blob_index} is outside the {len(payload)}-byte payload",
            EXIT_DECODE,
        )
    rows: list[list[int]] = []
    for row in range(8):
        chunk = payload[base + row * 4 : base + row * 4 + 4]
        pixels: list[int] = []
        for byte in chunk:
            pixels.append(byte >> 4)
            pixels.append(byte & 0x0F)
        rows.append(pixels)
    return rows


def classify_tile(rows: list[list[int]]) -> dict[str, Any]:
    """Describe a tile from its own pixels (no hand-written per-tile table)."""
    counts: dict[int, int] = {}
    positions: dict[int, list[tuple[int, int]]] = {}
    for y, row in enumerate(rows):
        for x, value in enumerate(row):
            counts[value] = counts.get(value, 0) + 1
            positions.setdefault(value, []).append((x, y))
    non_zero = sorted(value for value in counts if value != 0)
    if not non_zero:
        return {
            "role": "empty",
            "colour_indices": [],
            "fill_index": None,
            "border_indices": [],
        }
    parts: list[str] = []
    fill_index: int | None = None
    border_indices: list[int] = []
    for value in non_zero:
        cells = positions[value]
        cols = {x for x, _ in cells}
        rows_hit = {y for _, y in cells}
        if len(cells) == 64:
            parts.append(f"fill{value:x}")
            if fill_index is None:
                fill_index = value
        elif len(cols) == 1 and len(rows_hit) == 8:
            parts.append(f"line_x{cols.pop()}")
            border_indices.append(value)
        elif len(rows_hit) == 1 and len(cols) == 8:
            parts.append(f"line_y{rows_hit.pop()}")
            border_indices.append(value)
        else:
            parts.append(f"pattern{value:x}")
            border_indices.append(value)
    return {
        "role": "+".join(parts),
        "colour_indices": non_zero,
        "fill_index": fill_index,
        "border_indices": border_indices,
    }


def build_sheet(payload: bytes) -> list[list[int]]:
    """Lay the 32 tiles out as an 8x4 grid of 8x8 tiles (64x32 pixels)."""
    sheet = [[0] * SHEET_WIDTH for _ in range(SHEET_HEIGHT)]
    for blob_index in range(TILE_COUNT):
        origin_x = (blob_index % SHEET_COLS) * 8
        origin_y = (blob_index // SHEET_COLS) * 8
        for y, row in enumerate(decode_tile_4bpp(payload, blob_index)):
            for x, value in enumerate(row):
                sheet[origin_y + y][origin_x + x] = value
    return sheet


def bgr555_to_rgb8(value: int) -> tuple[int, int, int]:
    """Convert one BGR555 entry to 8-bit RGB with the (c << 3) | (c >> 2) rule."""
    red = value & 0x1F
    green = (value >> 5) & 0x1F
    blue = (value >> 10) & 0x1F
    return (
        (red << 3) | (red >> 2),
        (green << 3) | (green >> 2),
        (blue << 3) | (blue >> 2),
    )


def decode_palette(payload: bytes) -> list[dict[str, Any]]:
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


# --------------------------------------------------------------------------
# PNG
# --------------------------------------------------------------------------
def write_pngs(out_dir: Path, sheet: list[list[int]], palette: list[dict[str, Any]]) -> None:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
        raise ExportError(f"Pillow is required to write the PNGs: {exc}", EXIT_USAGE)

    flat = bytearray()
    for entry in palette:
        flat.extend(entry["rgb8"])
    flat.extend([0, 0, 0] * (256 - PALETTE_ENTRIES))

    index_bytes = bytes(value for row in sheet for value in row)
    index_image = Image.frombytes("L", (SHEET_WIDTH, SHEET_HEIGHT), index_bytes)
    index_image.save(out_dir / OUTPUT_TILES_INDEX_PNG, format="PNG", optimize=False)

    render_image = Image.frombytes("P", (SHEET_WIDTH, SHEET_HEIGHT), index_bytes)
    render_image.putpalette(bytes(flat))
    render_image.save(out_dir / OUTPUT_TILES_RENDER_PNG, format="PNG", optimize=False)


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------
def _read_dump(path: Path) -> bytes:
    if not path.is_file():
        raise ExportError(f"evidence file is missing: {path}", EXIT_EVIDENCE)
    return path.read_bytes()


def inspect_evidence(
    directory: Path, tiles: bytes, palette: bytes, baseline: Path | None
) -> dict[str, Any]:
    """Cross-check the exported payload against one same-frame receipt."""
    vram = _read_dump(directory / "vram-00.bin")
    pram = _read_dump(directory / "pram-00.bin")
    if len(vram) < VRAM_TILES_WINDOW[1]:
        raise ExportError(
            f"VRAM dump in {directory} is too small ({len(vram)} bytes)",
            EXIT_EVIDENCE,
        )
    if len(pram) < PRAM_PALETTE_WINDOW[1]:
        raise ExportError(
            f"PRAM dump in {directory} is too small ({len(pram)} bytes)",
            EXIT_EVIDENCE,
        )

    vram_lo, vram_hi = VRAM_TILES_WINDOW
    pram_lo, pram_hi = PRAM_PALETTE_WINDOW
    tiles_match = vram[vram_lo:vram_hi] == tiles
    palette_match = pram[pram_lo:pram_hi] == palette

    tilemap_lo, tilemap_hi = BG2_TILEMAP_WINDOW
    cells = [
        int.from_bytes(vram[tile_map_offset : tile_map_offset + 2], "little")
        for tile_map_offset in range(tilemap_lo, tilemap_hi, 2)
    ]
    if len(cells) != BG2_TILEMAP_CELLS:
        raise ExportError(
            f"BG2 tilemap window in {directory} holds {len(cells)} cells, "
            f"expected {BG2_TILEMAP_CELLS}",
            EXIT_EVIDENCE,
        )
    tile_histogram: dict[int, int] = {}
    bank_histogram: dict[int, int] = {}
    for cell in cells:
        tile_index = cell & 0x3FF
        bank = (cell >> 12) & 0x0F
        tile_histogram[tile_index] = tile_histogram.get(tile_index, 0) + 1
        bank_histogram[bank] = bank_histogram.get(bank, 0) + 1

    report: dict[str, Any] = {
        "directory": str(directory),
        "vram_sha256": sha256_bytes(vram),
        "pram_sha256": sha256_bytes(pram),
        "vram_tiles_window": [f"0x{vram_lo:04X}", f"0x{vram_hi:04X}"],
        "pram_palette_window": [f"0x{pram_lo:04X}", f"0x{pram_hi:04X}"],
        "tiles_match_vram_window": tiles_match,
        "palette_match_pram_bank12": palette_match,
        "bg2_tilemap": {
            "cells": len(cells),
            "non_zero_cells": sum(1 for cell in cells if cell != 0),
            "palette_banks_used": sorted(bank_histogram),
            "tile_index_histogram": {
                str(index): tile_histogram[index] for index in sorted(tile_histogram)
            },
        },
    }

    if baseline is not None:
        base_vram = _read_dump(baseline / "vram-00.bin")
        base_cells = [
            int.from_bytes(base_vram[off : off + 2], "little")
            for off in range(tilemap_lo, tilemap_hi, 2)
        ]
        changed = sum(1 for a, b in zip(base_cells, cells) if a != b)
        report["bg2_tilemap_changed_cells_vs_baseline"] = changed
        report["bg2_tilemap_baseline"] = str(baseline)
    return report


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------
def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def _load_rom(path: Path) -> bytes:
    if not path.is_file():
        raise ExportError(f"ROM not found: {path}", EXIT_ROM_HASH)
    digest = sha256_file(path)
    if digest != EXPECTED_ROM_SHA256:
        raise ExportError(
            f"ROM SHA-256 mismatch for {path}: got {digest}, expected "
            f"{EXPECTED_ROM_SHA256}; refusing to export",
            EXIT_ROM_HASH,
        )
    return path.read_bytes()


def build_manifest(
    rom_path: Path,
    rom: bytes,
    tiles: bytes,
    tiles_end: int,
    palette: bytes,
    palette_end: int,
    sheet: list[list[int]],
    palette_entries: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    tiles_offset = TILES_ROM_ADDRESS - 0x08000000
    palette_offset = PALETTE_ROM_ADDRESS - 0x08000000
    tiles_compressed = rom[tiles_offset:tiles_end]
    palette_compressed = rom[palette_offset:palette_end]

    sheet_layout = []
    for blob_index in range(TILE_COUNT):
        info = classify_tile(decode_tile_4bpp(tiles, blob_index))
        sheet_layout.append(
            {
                "tile_index": BASE_TILE_INDEX + blob_index,
                "blob_index": blob_index,
                "sheet_col": blob_index % SHEET_COLS,
                "sheet_row": blob_index // SHEET_COLS,
                "png_x": (blob_index % SHEET_COLS) * 8,
                "png_y": (blob_index // SHEET_COLS) * 8,
                "vram_offset": VRAM_TILES_WINDOW[0] + blob_index * TILE_BYTES,
                "vram_address": f"0x{VRAM_TILES_DEST + blob_index * TILE_BYTES:08X}",
                **info,
            }
        )

    return {
        "schema": SCHEMA,
        "exported_by": "tools/butano/export_s49_movegrid_overlay.py",
        "determinism": {
            "timestamp": "omitted",
            "note": (
                "No timestamp is written into any artifact, so re-running the "
                "exporter with the same inputs reproduces every output file "
                "byte for byte."
            ),
        },
        "rom": {
            "name": rom_path.name,
            "sha256": EXPECTED_ROM_SHA256,
            "size_bytes": len(rom),
            "address_base": "0x08000000",
        },
        "blobs": {
            "tiles": {
                "rom_address": f"0x{TILES_ROM_ADDRESS:08X}",
                "file_offset": tiles_offset,
                "compressed_bytes": len(tiles_compressed),
                "compressed_span": [
                    f"0x{TILES_ROM_ADDRESS:08X}",
                    f"0x{0x08000000 + tiles_end:08X}",
                ],
                "compressed_sha256": sha256_bytes(tiles_compressed),
                "decompressed_bytes": len(tiles),
                "decompressed_sha256": sha256_bytes(tiles),
            },
            "palette": {
                "rom_address": f"0x{PALETTE_ROM_ADDRESS:08X}",
                "file_offset": palette_offset,
                "compressed_bytes": len(palette_compressed),
                "compressed_span": [
                    f"0x{PALETTE_ROM_ADDRESS:08X}",
                    f"0x{0x08000000 + palette_end:08X}",
                ],
                "compressed_sha256": sha256_bytes(palette_compressed),
                "decompressed_bytes": len(palette),
                "decompressed_sha256": sha256_bytes(palette),
            },
        },
        "lz77": {
            "header_byte": "0x10",
            "size_field": "24-bit little-endian",
            "flag_bit_order": "most significant bit first (bit 7 down to bit 0)",
            "flag_bit_0": "literal byte",
            "flag_bit_1": (
                "match token: length = (first >> 4) + 3, "
                "distance = (((first & 0x0F) << 8) | second) + 1"
            ),
            "source": (
                "reverse/tools/export_rom_pointer_lz77_inventory.py "
                "(_parse_lz77)"
            ),
        },
        "tiles": {
            "bpp": 4,
            "tile_bytes": TILE_BYTES,
            "tile_count": TILE_COUNT,
            "base_tile_index": BASE_TILE_INDEX,
            "bg_char_base": f"0x{BG_CHAR_BASE:08X}",
            "bg_char_base_block": 0,
            "vram_destination": f"0x{VRAM_TILES_DEST:08X}",
            "vram_destination_note": (
                "BG2 char base block 0 (0x06000000) + tile 256 x 32 bytes; "
                "the BG2 tilemap itself lives at VRAM 0x06001000 (screen base "
                "block 2) and is written by the game at runtime."
            ),
            "sheet": {
                "cols": SHEET_COLS,
                "rows": SHEET_ROWS,
                "pixel_width": SHEET_WIDTH,
                "pixel_height": SHEET_HEIGHT,
                "index_png": OUTPUT_TILES_INDEX_PNG,
                "render_png": OUTPUT_TILES_RENDER_PNG,
            },
            "sheet_layout": sheet_layout,
        },
        "palette": {
            "bank": PALETTE_BANK,
            "pram_destination": f"0x{PRAM_PALETTE_DEST:08X}",
            "entry_count": PALETTE_ENTRIES,
            "bytes": len(palette),
            "conversion": "8-bit = (c << 3) | (c >> 2) on each 5-bit channel",
            "entries": palette_entries,
        },
        "outputs": outputs,
        "cross_check": {
            "status": "run" if evidence else "not_run",
            "evidence": evidence,
            "note": (
                "The cross-check compares the exported payload against the "
                "VRAM / PRAM dumps of already captured same-frame receipts. "
                "It proves the payload equals what the game had resident; it "
                "does not prove the game ever draws it."
            ),
        },
        "scope": {
            "established": [
                "The 32-tile payload at ROM 0x080B9E94 is the BG2 tile set "
                "resident at VRAM 0x06002000 in the captured frames.",
                "The 32-byte payload at ROM 0x080B9F5C is palette bank 12, "
                "resident at PRAM 0x05000180 in the captured frames.",
                "The tile set is a fixed grid / highlight tile family: empty "
                "tiles, 1-pixel edge tiles and solid tiles with a 1-pixel "
                "border, in six colour families.",
                "The tile graphics and the palette are byte-identical across "
                "every captured frame of all four receipts; only the BG2 "
                "tilemap changes between states.",
            ],
            "not_established": [
                "Which tilemap cells the game lights up: the BG2 tilemap "
                "content is generated at runtime and no ROM record for it was "
                "found.",
                "Whether the overlay marks reachable or unreachable ground: "
                "the layer is identified, its meaning is not.",
                "Whether the layer is reached by natural execution: the "
                "receipts are a scripted walk, not a coverage proof.",
                "Whether the 32 tiles are all used: the captured frames "
                "reference only part of the tile set.",
                "The screen-base unit convention (mGBA's block << 11 versus "
                "the 4 KB wording in common references) was not adjudicated "
                "in this round; the payload destination 0x06002000 is "
                "confirmed from the loader literal pool and from the VRAM "
                "dump independently of that convention.",
                "The PNG screenshots of the receipts are not self-consistent "
                "with their own dumps, so no pixel-level claim about the "
                "rendered overlay is made here.",
            ],
        },
    }


def export(args: argparse.Namespace) -> int:
    rom_path = Path(args.rom)
    out_dir = Path(args.out_dir)
    rom = _load_rom(rom_path)

    tiles, tiles_end = lz77_decompress(
        rom, TILES_ROM_ADDRESS - 0x08000000, expected_bytes=TILES_EXPECTED_BYTES
    )
    palette, palette_end = lz77_decompress(
        rom, PALETTE_ROM_ADDRESS - 0x08000000, expected_bytes=PALETTE_EXPECTED_BYTES
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / OUTPUT_TILES_BIN).write_bytes(tiles)
    (out_dir / OUTPUT_PALETTE_BIN).write_bytes(palette)

    sheet = build_sheet(tiles)
    palette_entries = decode_palette(palette)
    write_pngs(out_dir, sheet, palette_entries)
    _dump_json(
        out_dir / OUTPUT_PALETTE_JSON,
        {
            "schema": "konoha.s49-movegrid-overlay-palette.v1",
            "bank": PALETTE_BANK,
            "pram_destination": f"0x{PRAM_PALETTE_DEST:08X}",
            "source_rom_address": f"0x{PALETTE_ROM_ADDRESS:08X}",
            "bytes": len(palette),
            "sha256": sha256_bytes(palette),
            "conversion": "8-bit = (c << 3) | (c >> 2) on each 5-bit channel",
            "entries": palette_entries,
        },
    )

    evidence: list[dict[str, Any]] = []
    baseline = Path(args.evidence_baseline) if args.evidence_baseline else None
    for raw in args.evidence_dir:
        evidence.append(inspect_evidence(Path(raw), tiles, palette, baseline))

    outputs: dict[str, dict[str, Any]] = {}
    for name in (
        OUTPUT_TILES_BIN,
        OUTPUT_TILES_INDEX_PNG,
        OUTPUT_TILES_RENDER_PNG,
        OUTPUT_PALETTE_BIN,
        OUTPUT_PALETTE_JSON,
    ):
        path = out_dir / name
        outputs[name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}

    manifest = build_manifest(
        rom_path,
        rom,
        tiles,
        tiles_end,
        palette,
        palette_end,
        sheet,
        palette_entries,
        evidence,
        outputs,
    )
    _dump_json(out_dir / OUTPUT_MANIFEST, manifest)

    print(f"rom            {rom_path.name}  sha256={EXPECTED_ROM_SHA256}")
    print(
        f"tiles          0x{TILES_ROM_ADDRESS:08X} -> {len(tiles)} B  "
        f"sha256={sha256_bytes(tiles)}"
    )
    print(
        f"palette        0x{PALETTE_ROM_ADDRESS:08X} -> {len(palette)} B  "
        f"sha256={sha256_bytes(palette)}"
    )
    print(f"out-dir        {out_dir}")
    print(f"manifest       {out_dir / OUTPUT_MANIFEST}")
    print(f"manifest sha256 {sha256_file(out_dir / OUTPUT_MANIFEST)}")
    return EXIT_OK


def verify(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    manifest_path = out_dir / OUTPUT_MANIFEST
    if not manifest_path.is_file():
        raise ExportError(f"manifest is missing: {manifest_path}", EXIT_VERIFY)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []

    for name, record in sorted(manifest.get("outputs", {}).items()):
        path = out_dir / name
        if not path.is_file():
            problems.append(f"missing output file: {name}")
            continue
        digest = sha256_file(path)
        if digest != record["sha256"]:
            problems.append(
                f"{name}: sha256 {digest} != manifest {record['sha256']}"
            )
        size = path.stat().st_size
        if size != record["bytes"]:
            problems.append(f"{name}: {size} bytes != manifest {record['bytes']}")

    rom_path = Path(args.rom)
    rom = _load_rom(rom_path)
    tiles, _ = lz77_decompress(
        rom, TILES_ROM_ADDRESS - 0x08000000, expected_bytes=TILES_EXPECTED_BYTES
    )
    palette, _ = lz77_decompress(
        rom, PALETTE_ROM_ADDRESS - 0x08000000, expected_bytes=PALETTE_EXPECTED_BYTES
    )
    for key, payload in (("tiles", tiles), ("palette", palette)):
        recorded = manifest.get("blobs", {}).get(key, {})
        digest = sha256_bytes(payload)
        if digest != recorded.get("decompressed_sha256"):
            problems.append(
                f"{key}: ROM decodes to {digest}, manifest says "
                f"{recorded.get('decompressed_sha256')}"
            )
    tiles_file = out_dir / OUTPUT_TILES_BIN
    if tiles_file.is_file() and tiles_file.read_bytes() != tiles:
        problems.append(f"{OUTPUT_TILES_BIN} does not match the ROM payload")
    palette_file = out_dir / OUTPUT_PALETTE_BIN
    if palette_file.is_file() and palette_file.read_bytes() != palette:
        problems.append(f"{OUTPUT_PALETTE_BIN} does not match the ROM payload")

    if problems:
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        return EXIT_VERIFY

    print(f"verified {len(manifest.get('outputs', {}))} output files in {out_dir}")
    print(f"manifest sha256 {sha256_file(manifest_path)}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export the original S49 move-range overlay (BG2) tiles and "
            "palette from the ROM into machine readable form."
        )
    )
    parser.add_argument(
        "--rom",
        default=str(REPO_ROOT / DEFAULT_ROM_NAME),
        help="path to the original ROM (default: the repository-root ROM)",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help=f"output directory (default: {DEFAULT_OUT_DIR.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--evidence-dir",
        action="append",
        default=[],
        metavar="DIR",
        help=(
            "same-frame receipt directory (vram-00.bin + pram-00.bin) to "
            "cross-check the payload against; may be repeated"
        ),
    )
    parser.add_argument(
        "--evidence-baseline",
        default=None,
        metavar="DIR",
        help=(
            "receipt directory used as the BG2 tilemap baseline for the "
            "changed-cell count"
        ),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="re-read the written artifacts, re-hash them and re-decode the ROM",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.verify:
            return verify(args)
        return export(args)
    except ExportError as error:
        print(f"refused: {error}", file=sys.stderr)
        return error.code


if __name__ == "__main__":
    raise SystemExit(main())
