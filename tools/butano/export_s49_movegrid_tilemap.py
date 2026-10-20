#!/usr/bin/env python3
"""Decode the original S49 move-range overlay (BG2) tilemap from VRAM receipts.

The authority for *what* the overlay is lives in
``notes/s49-dispcnt-bit10-layer-20261020.md``: ``DISPCNT`` bit 10 is
``BG2 enable`` in plain-GBA semantics, ``BG2``'s ``BGCNT`` is ``0x0202``
(screen base block 2 -> tilemap at VRAM ``0x06001000``, char base block 0 ->
tile graphics at VRAM ``0x06000000``), and the overlay tile set is the
32 tiles 256..287 resident at ``0x06002000`` with palette bank 12.

This exporter reads the *receipt* side of the evidence (the dumped
``vram``/``pram``/``io`` of the captured frames) and decodes, deterministically
and fail-closed:

* all 1024 BG2 tilemap cells (tile index, palette bank, h/v flip),
* the "lit" cells -- the cells that actually paint pixels, i.e. that
  reference a non-blank tile of the overlay tile set -- together with their
  position in map space and, where the BG2 scroll registers make it
  derivable, their position on the 240x160 GBA screen,
* the difference set against a reference receipt's BG2 tilemap,
* the 32 overlay tiles (4bpp index sheet + palette-coloured render),
* the bank-12 palette (BGR555 -> 8-bit RGB).

Nothing here is guessed: every number is derived from the receipt bytes, and
anything that cannot be derived is emitted as the string ``"unknown"``.

Usage::

    python3 tools/butano/export_s49_movegrid_tilemap.py
    python3 tools/butano/export_s49_movegrid_tilemap.py --receipt DIR --out-dir DIR

Exit codes: 0 success, 2 receipt missing/unusable (fail closed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

ARTIFACTS = ROOT / "artifacts"
DEFAULT_OUT = ARTIFACTS / "s49-original-movegrid-tilemap-v1"

# ---------------------------------------------------------------------------
# Receipt inventory.  ``s49-original-movegrid-v1`` is the GPU-state dump of the
# very same step-19 state that ``s49-original-movegrid-frame-v1`` captures, so
# it is the third overlay-bearing receipt.
# ---------------------------------------------------------------------------
RECEIPTS: tuple[tuple[str, str], ...] = (
    ("movegrid-frame-v1", "s49-original-movegrid-frame-v1"),
    ("grid16-frame-v1", "s49-original-grid16-frame-v1"),
    ("movegrid-v1", "s49-original-movegrid-v1"),
    ("field-frame-v1", "s49-original-field-frame-v1"),
    ("banner-frame-v1", "s49-original-banner-frame-v1"),
)

REFERENCE_RECEIPT = "field-frame-v1"
OVERLAY_RECEIPTS = ("movegrid-frame-v1", "grid16-frame-v1", "movegrid-v1")

# Candidate file names per memory region, in priority order.  The frame
# receipts use ``<region>-00.bin``; the GPU-state dump uses ``<region>.bin``.
VRAM_NAMES = ("vram-00.bin", "vram.bin")
PRAM_NAMES = ("pram-00.bin", "pram.bin")
IO_NAMES = ("io-00.bin", "io.bin")

VRAM_BYTES = 0x18000
PRAM_BYTES = 0x400
IO_MIN_BYTES = 0x30

BG2_SCREEN_BASE_BLOCK = 2
BG2_CHAR_BASE_BLOCK = 0
BG2_SCREEN_BASE_OFFSET = 0x1000
BG2_CHAR_BASE_OFFSET = 0x0000
PALETTE_BANK = 12
PALETTE_BANK_OFFSET = PALETTE_BANK * 0x20

TILE_COUNT = 32
TILE_BASE_INDEX = 256
TILE_SHEET_COLS = 8
TILE_SHEET_ROWS = 4

MAP_COLS = 32
MAP_ROWS = 32
SCREEN_W = 240
SCREEN_H = 160

# The two tiles of the overlay set that paint nothing (all pixel indices 0,
# which is transparent on a GBA background layer).
BLANK_TILES = frozenset({256, 257})

# Synthetic colours for the per-cell map rendering.  A cell is painted with
# the colour of its tile *family* so that the shape of the lit region is
# legible without needing the palette.
TILE_FAMILIES: dict[int, str] = {}
for _t in (256, 257, 282, 283, 284, 285, 286, 287):
    TILE_FAMILIES[_t] = "blank"
for _t in (258, 259, 260, 261):
    TILE_FAMILIES[_t] = "edge"
for _t in (262, 263, 264, 265):
    TILE_FAMILIES[_t] = "hatch"
for _t in (266, 267, 268, 269):
    TILE_FAMILIES[_t] = "line_alt"
for _t in (270, 271, 272, 273):
    TILE_FAMILIES[_t] = "band"
for _t in (274, 275, 276, 277):
    TILE_FAMILIES[_t] = "hatch_shift"
for _t in (278, 279, 280, 281):
    TILE_FAMILIES[_t] = "solid"

FAMILY_COLOURS: dict[str, tuple[int, int, int]] = {
    "blank": (24, 24, 24),
    "edge": (110, 110, 110),
    "hatch": (220, 60, 60),
    "line_alt": (70, 140, 240),
    "band": (240, 200, 40),
    "hatch_shift": (40, 200, 140),
    "solid": (150, 150, 150),
}
# Marker colour for cells that differ from the reference receipt.
CHANGED_MARK = (255, 255, 255)

# Deterministic legend palette for the 4bpp index sheet: index i gets a
# distinct synthetic colour so the raw index is visible in the PNG.
LEGEND_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0),
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 128, 0),
    (128, 255, 0),
    (0, 128, 255),
    (128, 0, 255),
    (255, 0, 128),
    (128, 128, 128),
    (192, 192, 192),
    (64, 64, 64),
    (224, 224, 224),
)


class ReceiptError(RuntimeError):
    """A receipt is missing, truncated or otherwise unusable."""


# ---------------------------------------------------------------------------
# Low level helpers
# ---------------------------------------------------------------------------
def u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "little")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expand5(value: int) -> int:
    """GBA 5-bit channel -> 8-bit channel."""
    return (value << 3) | (value >> 2)


def _pick(directory: Path, names: tuple[str, ...]) -> Path:
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    raise ReceiptError(
        f"missing {names[0]} (or {', '.join(names[1:])}) in {directory}"
    )


def _read_exact(directory: Path, names: tuple[str, ...], size: int) -> bytes:
    path = _pick(directory, names)
    data = path.read_bytes()
    if len(data) != size:
        raise ReceiptError(
            f"{path} is {len(data)} bytes, expected exactly {size}"
        )
    return data


# ---------------------------------------------------------------------------
# Receipt decoding
# ---------------------------------------------------------------------------
def read_receipt(directory: Path) -> dict[str, Any]:
    """Read one receipt and decode its registers.  Fail closed on any problem."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ReceiptError(f"receipt directory does not exist: {directory}")

    vram = _read_exact(directory, VRAM_NAMES, VRAM_BYTES)
    pram = _read_exact(directory, PRAM_NAMES, PRAM_BYTES)

    io_path = _pick(directory, IO_NAMES)
    io = io_path.read_bytes()
    if len(io) < IO_MIN_BYTES:
        raise ReceiptError(
            f"{io_path} is {len(io)} bytes, expected at least {IO_MIN_BYTES}"
        )

    dispcnt = u16(io, 0x00)
    bgcnt = [u16(io, 0x08 + 2 * index) for index in range(4)]
    bg2cnt = bgcnt[2]
    screen_base_block = (bg2cnt >> 8) & 0x1F
    char_base_block = (bg2cnt >> 2) & 0x03
    if screen_base_block != BG2_SCREEN_BASE_BLOCK:
        raise ReceiptError(
            f"{directory}: BG2 BGCNT 0x{bg2cnt:04X} has screen base block "
            f"{screen_base_block}, expected {BG2_SCREEN_BASE_BLOCK}"
        )
    if char_base_block != BG2_CHAR_BASE_BLOCK:
        raise ReceiptError(
            f"{directory}: BG2 BGCNT 0x{bg2cnt:04X} has char base block "
            f"{char_base_block}, expected {BG2_CHAR_BASE_BLOCK}"
        )

    return {
        "directory": directory,
        "vram": vram,
        "pram": pram,
        "io": io,
        "registers": {
            "dispcnt": dispcnt,
            "dispcnt_hex": f"0x{dispcnt:04X}",
            "bg2_enabled": bool((dispcnt >> 10) & 1),
            "bgcnt": bgcnt,
            "bg2cnt": bg2cnt,
            "bg2cnt_hex": f"0x{bg2cnt:04X}",
            "bg2_screen_base_block": screen_base_block,
            "bg2_char_base_block": char_base_block,
            # BG0..BG3 horizontal offsets live at 0x10/0x14/0x18/0x1C and the
            # vertical ones at 0x12/0x16/0x1A/0x1E; they are interleaved.
            "bg_hoffs": [u16(io, 0x10 + 4 * index) for index in range(4)],
            "bg_voffs": [u16(io, 0x12 + 4 * index) for index in range(4)],
        },
    }


def decode_cell(value: int) -> dict[str, Any]:
    """Split a 16-bit BG tilemap entry into its fields."""
    return {
        "tile": value & 0x3FF,
        "palette_bank": (value >> 12) & 0x0F,
        "hflip": bool((value >> 11) & 1),
        "vflip": bool((value >> 10) & 1),
        "raw": value,
        "raw_hex": f"0x{value:04X}",
    }


def read_tilemap(vram: bytes, offset: int = BG2_SCREEN_BASE_OFFSET) -> list[int]:
    return [u16(vram, offset + 2 * index) for index in range(MAP_COLS * MAP_ROWS)]


def tile_pixels(vram: bytes, tile_index: int) -> list[list[int]]:
    """Decode one 4bpp tile into an 8x8 matrix of colour indices.

    GBA 4bpp stores **two pixels per byte**: the high nibble is the left
    pixel, the low nibble the right one, and a tile row is four bytes (eight
    pixels).  Reading four 2-bit groups per byte instead yields sixteen
    pixels per row, which silently turns solid fills into dashed patterns
    and mis-classifies every tile family.
    """
    base = BG2_CHAR_BASE_OFFSET + (tile_index & 0x3FF) * 32
    rows: list[list[int]] = []
    for row in range(8):
        pixels: list[int] = []
        row_base = base + row * 4
        for byte_index in range(4):
            byte = vram[row_base + byte_index]
            pixels.append((byte >> 4) & 0x0F)
            pixels.append(byte & 0x0F)
        rows.append(pixels)
    return rows


def overlay_tiles(vram: bytes) -> list[list[list[int]]]:
    return [
        tile_pixels(vram, TILE_BASE_INDEX + index) for index in range(TILE_COUNT)
    ]


def palette_entries(pram: bytes) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index in range(16):
        word = u16(pram, PALETTE_BANK_OFFSET + index * 2)
        r5, g5, b5 = word & 0x1F, (word >> 5) & 0x1F, (word >> 10) & 0x1F
        entries.append({
            "index": index,
            "bgr555": f"0x{word:04X}",
            "rgb5": [r5, g5, b5],
            "rgb8": [expand5(r5), expand5(g5), expand5(b5)],
        })
    return entries


# ---------------------------------------------------------------------------
# Geometry: map space <-> screen space
# ---------------------------------------------------------------------------
def screen_window(hoffs: int, voffs: int) -> dict[str, Any]:
    """Which map tiles are on the 240x160 screen for the given BG2 scroll."""
    visible_cols = [
        col for col in range(MAP_COLS)
        if (col * 8 - hoffs) % 256 < SCREEN_W
    ]
    visible_rows = [
        row for row in range(MAP_ROWS)
        if (row * 8 - voffs) % 256 < SCREEN_H
    ]
    # The lists are ordered the way the window is traversed on screen (left to
    # right, top to bottom), not by map index, because the 256x256 background
    # area wraps and the first visible column is not the lowest map column.
    return {
        "bg2_hoffs": hoffs,
        "bg2_voffs": voffs,
        "map_area_px": [MAP_COLS * 8, MAP_ROWS * 8],
        "screen_px": [SCREEN_W, SCREEN_H],
        "scroll_convention": (
            "GBA background area is 256x256 px and wraps; the screen shows "
            "the 240x160 window starting at (bg2_hoffs, bg2_voffs)."
        ),
        "visible_map_cols": sorted(
            visible_cols, key=lambda col: (col * 8 - hoffs) % 256
        ),
        "visible_map_rows": sorted(
            visible_rows, key=lambda row: (row * 8 - voffs) % 256
        ),
        "visible_map_cols_by_map_index": sorted(visible_cols),
        "visible_map_rows_by_map_index": sorted(visible_rows),
        "visible_map_col_count": len(visible_cols),
        "visible_map_row_count": len(visible_rows),
    }


def screen_position(map_x: int, map_y: int, hoffs: int, voffs: int) -> dict[str, Any]:
    sx = (map_x * 8 - hoffs) % 256
    sy = (map_y * 8 - voffs) % 256
    return {
        "map_px_x": map_x * 8,
        "map_px_y": map_y * 8,
        "screen_px_x": sx,
        "screen_px_y": sy,
        "visible": sx < SCREEN_W and sy < SCREEN_H,
    }


# ---------------------------------------------------------------------------
# Per-receipt analysis
# ---------------------------------------------------------------------------
def tile_family(tile: int) -> str:
    return TILE_FAMILIES.get(tile, "other")


def analyse_receipt(
    receipt: dict[str, Any],
    reference: dict[str, Any] | None,
) -> dict[str, Any]:
    vram = receipt["vram"]
    registers = receipt["registers"]
    hoffs = registers["bg_hoffs"][2]
    voffs = registers["bg_voffs"][2]

    raw_cells = read_tilemap(vram)
    cells: list[dict[str, Any]] = []
    lit_cells: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_cells):
        map_x, map_y = index % MAP_COLS, index // MAP_COLS
        decoded = decode_cell(raw)
        entry = {
            "index": index,
            "map_x": map_x,
            "map_y": map_y,
            "tile": decoded["tile"],
            "palette_bank": decoded["palette_bank"],
            "hflip": decoded["hflip"],
            "vflip": decoded["vflip"],
            "raw_hex": decoded["raw_hex"],
            "family": tile_family(decoded["tile"]),
        }
        entry.update(screen_position(map_x, map_y, hoffs, voffs))
        cells.append(entry)
        if decoded["tile"] >= TILE_BASE_INDEX and decoded["tile"] not in BLANK_TILES:
            lit_cells.append(entry)

    overlay_index_cells = [
        entry for entry in cells if entry["tile"] >= TILE_BASE_INDEX
    ]

    changed: list[dict[str, Any]] = []
    if reference is not None:
        reference_cells = read_tilemap(reference["vram"])
        for index, (old, new) in enumerate(zip(reference_cells, raw_cells)):
            if old == new:
                continue
            map_x, map_y = index % MAP_COLS, index // MAP_COLS
            old_decoded = decode_cell(old)
            new_decoded = decode_cell(new)
            entry = {
                "index": index,
                "map_x": map_x,
                "map_y": map_y,
                "old": {
                    "tile": old_decoded["tile"],
                    "palette_bank": old_decoded["palette_bank"],
                    "hflip": old_decoded["hflip"],
                    "vflip": old_decoded["vflip"],
                    "raw_hex": old_decoded["raw_hex"],
                },
                "new": {
                    "tile": new_decoded["tile"],
                    "palette_bank": new_decoded["palette_bank"],
                    "hflip": new_decoded["hflip"],
                    "vflip": new_decoded["vflip"],
                    "raw_hex": new_decoded["raw_hex"],
                },
            }
            entry.update(screen_position(map_x, map_y, hoffs, voffs))
            changed.append(entry)

    return {
        "cells": cells,
        "lit_cells": lit_cells,
        "overlay_index_cells": overlay_index_cells,
        "changed_cells": changed,
        "registers": registers,
        "window": screen_window(hoffs, voffs),
    }


def geometry_summary(analysis: dict[str, Any]) -> dict[str, Any]:
    """Compact shape description of the lit and the changed cell sets."""
    cells = analysis["cells"]
    lit = analysis["lit_cells"]
    changed = analysis["changed_cells"]

    def bbox(entries: list[dict[str, Any]]) -> dict[str, Any]:
        if not entries:
            return {"count": 0, "bbox": "unknown"}
        xs = [entry["map_x"] for entry in entries]
        ys = [entry["map_y"] for entry in entries]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        area = (x1 - x0 + 1) * (y1 - y0 + 1)
        return {
            "count": len(entries),
            "map_x_range": [x0, x1],
            "map_y_range": [y0, y1],
            "map_px_bbox": [x0 * 8, y0 * 8, (x1 + 1) * 8, (y1 + 1) * 8],
            "bbox_cells": area,
            "fill_ratio": round(len(entries) / area, 4),
            "aspect_width_over_height": round(
                (x1 - x0 + 1) / (y1 - y0 + 1), 4
            ),
        }

    def cell_grid(entries: list[dict[str, Any]]) -> list[list[int]]:
        """16x16 grid of 16x16-px map cells; value = touched 8x8 tile count."""
        grid = [[0] * 16 for _ in range(16)]
        for entry in entries:
            grid[entry["map_y"] // 2][entry["map_x"] // 2] += 1
        return grid

    def row_histogram(entries: list[dict[str, Any]]) -> dict[str, int]:
        histogram: dict[int, int] = {}
        for entry in entries:
            histogram[entry["map_y"]] = histogram.get(entry["map_y"], 0) + 1
        return {str(key): histogram[key] for key in sorted(histogram)}

    def col_histogram(entries: list[dict[str, Any]]) -> dict[str, int]:
        histogram: dict[int, int] = {}
        for entry in entries:
            histogram[entry["map_x"]] = histogram.get(entry["map_x"], 0) + 1
        return {str(key): histogram[key] for key in sorted(histogram)}

    palette_banks = sorted({entry["palette_bank"] for entry in lit})
    changed_banks = sorted({
        entry["new"]["palette_bank"] for entry in changed
    })
    changed_tiles = sorted({entry["new"]["tile"] for entry in changed})

    return {
        "total_cells": len(cells),
        "cells_with_tile_index_ge_256": len(analysis["overlay_index_cells"]),
        "lit_cells_non_blank": bbox(lit),
        "changed_cells_vs_reference": bbox(changed),
        "lit_rows": row_histogram(lit),
        "lit_cols": col_histogram(lit),
        "changed_rows": row_histogram(changed),
        "changed_cols": col_histogram(changed),
        "lit_cell_grid_16x16": cell_grid(lit),
        "changed_cell_grid_16x16": cell_grid(changed),
        "lit_palette_banks": palette_banks,
        "changed_new_palette_banks": changed_banks,
        "changed_new_tiles": changed_tiles,
        "changed_new_families": sorted(
            {tile_family(tile) for tile in changed_tiles}
        ),
        "map_cell_size_px": 16,
        "map_cell_grid": [16, 16],
    }


# ---------------------------------------------------------------------------
# PNG output
# ---------------------------------------------------------------------------
def _pil():
    try:
        from PIL import Image
    except ImportError as error:  # pragma: no cover - Pillow is a dependency
        raise ReceiptError(f"Pillow is required: {error}") from error
    return Image


def write_tiles_index_png(path: Path, tiles: list[list[list[int]]]) -> None:
    """32 tiles laid out 8x4; the PNG palette is a legend so indices are visible."""
    image_module = _pil()
    image = image_module.new("P", (TILE_SHEET_COLS * 8, TILE_SHEET_ROWS * 8), 0)
    palette: list[int] = []
    for r, g, b in LEGEND_PALETTE:
        palette.extend((r, g, b))
    image.putpalette(palette)
    pixels = image.load()
    for index, tile in enumerate(tiles):
        origin_x = (index % TILE_SHEET_COLS) * 8
        origin_y = (index // TILE_SHEET_COLS) * 8
        for y in range(8):
            for x in range(8):
                pixels[origin_x + x, origin_y + y] = tile[y][x]
    image.save(path, format="PNG", optimize=False)


def write_tiles_render_png(
    path: Path,
    tiles: list[list[list[int]]],
    entries: list[dict[str, Any]],
) -> None:
    image_module = _pil()
    image = image_module.new(
        "RGB", (TILE_SHEET_COLS * 8, TILE_SHEET_ROWS * 8), (0, 0, 0)
    )
    pixels = image.load()
    for index, tile in enumerate(tiles):
        origin_x = (index % TILE_SHEET_COLS) * 8
        origin_y = (index // TILE_SHEET_COLS) * 8
        for y in range(8):
            for x in range(8):
                colour_index = tile[y][x]
                if colour_index == 0:
                    # GBA background pixel index 0 is transparent; show it as
                    # a neutral dark grey so the sheet is readable.
                    pixels[origin_x + x, origin_y + y] = (24, 24, 24)
                else:
                    pixels[origin_x + x, origin_y + y] = tuple(
                        entries[colour_index]["rgb8"]
                    )
    image.save(path, format="PNG", optimize=False)


def write_palette_png(path: Path, entries: list[dict[str, Any]]) -> None:
    """One horizontal bar per palette entry (row y == entry y)."""
    image_module = _pil()
    image = image_module.new("RGB", (16, 16), (0, 0, 0))
    pixels = image.load()
    for index, entry in enumerate(entries):
        colour = tuple(entry["rgb8"])
        for x in range(16):
            pixels[x, index] = colour
    image.save(path, format="PNG", optimize=False)


def write_layer_png_for_receipt(
    path: Path,
    cells: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> None:
    """Render the BG2 layer from the decoded tilemap (not from the tiles)."""
    image_module = _pil()
    image = image_module.new("RGBA", (MAP_COLS * 8, MAP_ROWS * 8), (0, 0, 0, 0))
    pixels = image.load()
    for cell in cells:
        tile = cell["tile"]
        if tile < TILE_BASE_INDEX:
            continue
        # The tile graphics are read back from the receipt's own VRAM.
        origin_x = cell["map_x"] * 8
        origin_y = cell["map_y"] * 8
        for y in range(8):
            for x in range(8):
                source_x = x if not cell["hflip"] else 7 - x
                source_y = y if not cell["vflip"] else 7 - y
                colour_index = TILE_CACHE[tile][source_y][source_x]
                if colour_index == 0:
                    continue
                pixels[origin_x + x, origin_y + y] = tuple(
                    entries[colour_index]["rgb8"]
                ) + (255,)
    image.save(path, format="PNG", optimize=False)


# Module level cache of the 32 overlay tiles, filled once per export run.
TILE_CACHE: dict[int, list[list[int]]] = {}


def write_cells_png(
    path: Path,
    cells: list[dict[str, Any]],
    changed_indices: set[int],
    scale: int = 16,
) -> None:
    """32x32 map painted by tile family; changed cells get a white outline."""
    image_module = _pil()
    width = MAP_COLS * scale
    height = MAP_ROWS * scale
    image = image_module.new("RGB", (width, height), (0, 0, 0))
    pixels = image.load()
    for cell in cells:
        colour = FAMILY_COLOURS.get(cell["family"], (255, 0, 255))
        origin_x = cell["map_x"] * scale
        origin_y = cell["map_y"] * scale
        for y in range(scale):
            for x in range(scale):
                pixels[origin_x + x, origin_y + y] = colour
    for index in sorted(changed_indices):
        cell = cells[index]
        origin_x = cell["map_x"] * scale
        origin_y = cell["map_y"] * scale
        for offset in range(scale):
            for x, y in (
                (offset, 0), (offset, scale - 1), (0, offset), (scale - 1, offset)
            ):
                pixels[origin_x + x, origin_y + y] = CHANGED_MARK
    image.save(path, format="PNG", optimize=False)


# ---------------------------------------------------------------------------
# Export driver
# ---------------------------------------------------------------------------
def export(out_dir: Path) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    receipts: dict[str, dict[str, Any]] = {}
    for name, directory_name in RECEIPTS:
        receipts[name] = read_receipt(ARTIFACTS / directory_name)

    reference = receipts[REFERENCE_RECEIPT]

    # Shared assets, taken from the first overlay-bearing receipt.
    primary = receipts[OVERLAY_RECEIPTS[0]]
    TILE_CACHE.clear()
    for index, tile in enumerate(overlay_tiles(primary["vram"])):
        TILE_CACHE[TILE_BASE_INDEX + index] = tile
    tiles = [TILE_CACHE[TILE_BASE_INDEX + index] for index in range(TILE_COUNT)]
    entries = palette_entries(primary["pram"])

    tiles_bin = out_dir / "bg2-tiles-4bpp.bin"
    tiles_bin.write_bytes(primary["vram"][
        BG2_CHAR_BASE_OFFSET + TILE_BASE_INDEX * 32:
        BG2_CHAR_BASE_OFFSET + (TILE_BASE_INDEX + TILE_COUNT) * 32
    ])
    palette_bin = out_dir / "bg2-palette.bin"
    palette_bin.write_bytes(primary["pram"][
        PALETTE_BANK_OFFSET:PALETTE_BANK_OFFSET + 32
    ])

    write_tiles_index_png(out_dir / "bg2-tiles-index.png", tiles)
    write_tiles_render_png(out_dir / "bg2-tiles-render.png", tiles, entries)
    write_palette_png(out_dir / "bg2-palette.png", entries)
    (out_dir / "bg2-palette.json").write_text(
        json.dumps({
            "schema": "konoha.s49-movegrid-bg2-palette.v1",
            "source": {
                "receipt": str(primary["directory"].relative_to(ROOT)),
                "pram_offset": f"0x{PALETTE_BANK_OFFSET:04X}",
                "palette_bank": PALETTE_BANK,
            },
            "conversion": "8-bit = (c << 3) | (c >> 2) on each 5-bit channel",
            "entries": entries,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary: dict[str, Any] = {}
    for name, _directory_name in RECEIPTS:
        receipt = receipts[name]
        analysis = analyse_receipt(receipt, reference)
        cells = analysis["cells"]
        changed_indices = {entry["index"] for entry in analysis["changed_cells"]}

        write_cells_png(
            out_dir / f"{name}.bg2-cells.png", cells, changed_indices
        )
        write_layer_png_for_receipt(
            out_dir / f"{name}.bg2-layer.png", cells, entries
        )

        geometry = geometry_summary(analysis)
        payload = {
            "schema": "konoha.s49-movegrid-bg2-tilemap.v1",
            "receipt": name,
            "receipt_directory": str(receipt["directory"].relative_to(ROOT)),
            "reference_receipt": REFERENCE_RECEIPT,
            "registers": {
                "dispcnt": analysis["registers"]["dispcnt_hex"],
                "bg2_enabled": analysis["registers"]["bg2_enabled"],
                "bg2cnt": analysis["registers"]["bg2cnt_hex"],
                "bg2_screen_base_block": analysis["registers"]["bg2_screen_base_block"],
                "bg2_char_base_block": analysis["registers"]["bg2_char_base_block"],
                "bg_hoffs": analysis["registers"]["bg_hoffs"],
                "bg_voffs": analysis["registers"]["bg_voffs"],
            },
            "screen_window": analysis["window"],
            "overlay_tile_set": {
                "base_tile_index": TILE_BASE_INDEX,
                "tile_count": TILE_COUNT,
                "char_base_block": BG2_CHAR_BASE_BLOCK,
                "vram_window": [
                    f"0x{BG2_CHAR_BASE_OFFSET + TILE_BASE_INDEX * 32:04X}",
                    f"0x{BG2_CHAR_BASE_OFFSET + (TILE_BASE_INDEX + TILE_COUNT) * 32:04X}",
                ],
                "blank_tiles": sorted(BLANK_TILES),
            },
            "counts": {
                "cells": len(cells),
                "cells_with_tile_index_ge_256": len(analysis["overlay_index_cells"]),
                "lit_cells_non_blank": len(analysis["lit_cells"]),
                "changed_cells_vs_reference": len(analysis["changed_cells"]),
            },
            "geometry": geometry,
            "cells": cells,
            "lit_cells": analysis["lit_cells"],
            "changed_cells": analysis["changed_cells"],
            "unknowns": {
                "overlay_semantics": (
                    "unknown: whether the lit cells are the reachable range "
                    "highlight or the unreachable dim is not decidable from "
                    "the receipts"
                ),
                "lit_cell_definition": (
                    "the literal criterion 'tile index >= 256' selects all "
                    "1024 cells because the whole BG2 tilemap is built from "
                    "the overlay tile set; 'lit_cells' therefore uses the "
                    "stricter non-blank-tile rule and both counts are given"
                ),
            },
        }
        (out_dir / f"{name}.bg2-tilemap.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        summary[name] = {
            "receipt_directory": str(receipt["directory"].relative_to(ROOT)),
            "dispcnt": analysis["registers"]["dispcnt_hex"],
            "bg2_enabled": analysis["registers"]["bg2_enabled"],
            "bg2_hoffs": analysis["registers"]["bg_hoffs"][2],
            "bg2_voffs": analysis["registers"]["bg_voffs"][2],
            "overlay_receipt": name in OVERLAY_RECEIPTS,
            "counts": payload["counts"],
            "lit_cell_bbox": geometry["lit_cells_non_blank"],
            "changed_cell_bbox": geometry["changed_cells_vs_reference"],
            "changed_new_tiles": geometry["changed_new_tiles"],
            "changed_new_palette_banks": geometry["changed_new_palette_banks"],
            "changed_cell_grid_16x16": geometry["changed_cell_grid_16x16"],
        }

    outputs: dict[str, Any] = {}
    for path in sorted(out_dir.iterdir()):
        if path.name == "manifest.json" or not path.is_file():
            continue
        outputs[path.name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path.read_bytes()),
        }

    manifest = {
        "schema": "konoha.s49-movegrid-bg2-tilemap.v1",
        "exported_by": "tools/butano/export_s49_movegrid_tilemap.py",
        "source_of_truth": (
            "notes/s49-dispcnt-bit10-layer-20261020.md (DISPCNT bit 10 = "
            "BG2 enable; BGCNT 0x0202; tilemap VRAM 0x06001000; tiles 256..287 "
            "at VRAM 0x06002000; palette bank 12)"
        ),
        "receipts": {
            name: {
                "directory": str(directory_name),
                "overlay": name in OVERLAY_RECEIPTS,
            }
            for name, directory_name in RECEIPTS
        },
        "reference_receipt": REFERENCE_RECEIPT,
        "determinism": (
            "No timestamp is written into any artifact; re-running the "
            "exporter with the same receipts reproduces every output file "
            "byte for byte."
        ),
        "outputs": outputs,
        "summary": summary,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        manifest = export(args.out_dir)
    except ReceiptError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for name, entry in sorted(manifest["summary"].items()):
        print(
            f"{name}: dispcnt={entry['dispcnt']} bg2_enabled={entry['bg2_enabled']} "
            f"changed={entry['counts']['changed_cells_vs_reference']} "
            f"lit={entry['counts']['lit_cells_non_blank']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
